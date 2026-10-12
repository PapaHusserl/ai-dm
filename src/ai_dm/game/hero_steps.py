from collections import Counter
from dataclasses import dataclass, field
from typing import NamedTuple

from ai_dm.content.models.common import ABILITIES
from ai_dm.game.hero_create import split_list
from ai_dm.rules.builder import (
    ABILITY_MESSAGES,
    CharacterChoices,
    HeroSheet,
    background_from_registry,
    feat_choice_count,
    means_problems,
    motive_problems,
    name_problems,
    origin_feat_keys,
    over_twenty_message,
    point_buy_cost,
    species_choice_keys,
)
from ai_dm.rules.hero_options import (
    background_options,
    class_options,
    class_skill_options,
    class_spells,
    feat_pick_options,
    fighting_styles,
    has_fighting_style,
    item_name,
    kit_label,
    kit_options,
    mastery_weapons,
    origin_feats,
    point_buy_table,
    species_options,
    species_skill_options,
    spell_counts,
    standard_array,
)
from ai_dm.rules.money import format_cp
from ai_dm.rules.names import ABILITY_NAMES, SKILL_NAMES
from ai_dm.state.gender import GENDER_WORDS
from ai_dm.state.hero import BackgroundSpec

# значение пункта «Описать словами» на шаге предыстории: его разбирает автомат
WORDS = "words"
WORDS_LABEL = "Описать словами"


class Option(NamedTuple):
    value: object
    label: str


@dataclass
class Draft:
    # черновик героя: поля заполняются шагами по порядку STEPS
    species_id: str = ""
    class_id: str = ""
    background: object = None
    ability_method: str = ""
    scores: dict = field(default_factory=dict)
    bonus_scheme: str = ""
    bonus: dict = field(default_factory=dict)
    class_skills: list = field(default_factory=list)
    masteries: list = field(default_factory=list)
    style: str | None = None
    cantrips: list = field(default_factory=list)
    spells: list = field(default_factory=list)
    prepared: list = field(default_factory=list)
    species_skill: str = ""
    species_feat: str = ""
    feat_picks_bg: list = field(default_factory=list)
    feat_picks_species: list = field(default_factory=list)
    kit: str | None = None
    gear: str = ""
    name: str = ""
    gender: str = ""
    pronouns: str = ""
    motive: str = ""
    means: list = field(default_factory=list)
    # занятые имена мира: служебное поле шага имени, не выбор игрока и не сбрасывается clear_from
    taken_names: list = field(default_factory=list)


@dataclass(frozen=True)
class StepDef:
    # key -- имя шага; attr -- поле Draft; kind: pick, multi, text; needs, options, count, put,
    # label -- функции модуля (draft, registry[, value]); options=None или пустой список --
    # ввод строкой; on_error -- шаг, куда вернуться при ошибке put
    key: str
    attr: str
    kind: str
    title: str
    needs: object = None
    options: object = None
    count: object = None
    put: object = None
    label: object = None
    on_error: str = ""


def draft_spec(draft, registry):
    if isinstance(draft.background, BackgroundSpec):
        return draft.background
    return background_from_registry(draft.background, registry)


def draft_class(draft, registry):
    return registry.get("class", draft.class_id)


def points_text(count) -> str:
    if count % 100 in range(11, 15) or count % 10 in (0, 5, 6, 7, 8, 9):
        return f"{count} очков"
    return f"{count} очко" if count % 10 == 1 else f"{count} очка"


def spec_skills(draft, registry):
    return list(draft_spec(draft, registry).skills)


def options_species(draft, registry):
    return [Option(s.id, s.name) for s in species_options(registry)]


def options_class(draft, registry):
    return [Option(c.id, c.name) for c in class_options(registry)]


def options_background(draft, registry):
    options = [Option(b.id, b.name) for b in background_options(registry)]
    return options + [Option(WORDS, WORDS_LABEL)]


def options_method(draft, registry):
    array = ",".join(str(v) for v in standard_array(registry))
    budget = point_buy_table(registry)[1]
    return [
        Option("standard_array", f"Стандартный набор ({array})"),
        Option("point_buy", f"Покупка очков ({budget})"),
        Option("explicit", "Свободный ввод (3..20)"),
    ]


def remaining_array(draft, registry):
    left = Counter(standard_array(registry)) - Counter(draft.scores.values())
    return sorted(left.elements(), reverse=True)


def points_left(draft, registry):
    return point_buy_table(registry)[1] - point_buy_cost(draft.scores, registry)


def count_scores(draft, registry):
    return len(ABILITIES)


def label_scores(draft, registry):
    name = ABILITY_NAMES[ABILITIES[len(draft.scores)]]
    if draft.ability_method == "point_buy":
        return f"Характеристика {name} — осталось {points_text(points_left(draft, registry))}"
    if draft.ability_method == "explicit":
        return f"Характеристика {name} — введите значение от 3 до 20"
    return f"Характеристика {name}"


def options_scores(draft, registry):
    if draft.ability_method == "standard_array":
        return [Option(v, str(v)) for v in remaining_array(draft, registry)]
    if draft.ability_method == "point_buy":
        table = point_buy_table(registry)[0]
        return [Option(v, f"{v} ({points_text(cost)})") for v, cost in table.items()]
    return []


def to_number(value):
    if isinstance(value, int):
        return value
    text = value.strip()
    return int(text) if text.lstrip("-").isdigit() else None


def score_problem(draft, number, registry):
    method = draft.ability_method
    if method == "standard_array" and number not in remaining_array(draft, registry):
        return ABILITY_MESSAGES["standard_array_invalid"]
    if method == "point_buy":
        scores = {**draft.scores, ABILITIES[len(draft.scores)]: number}
        cost = point_buy_cost(scores, registry)
        if cost is None or cost > point_buy_table(registry)[1]:
            return ABILITY_MESSAGES["point_buy_invalid"]
    if method == "explicit" and (number is None or not 3 <= number <= 20):
        return ABILITY_MESSAGES["abilities_invalid"]
    return None


def put_score(draft, value, registry):
    number = to_number(value)
    problem = score_problem(draft, number, registry)
    if problem is None:
        draft.scores[ABILITIES[len(draft.scores)]] = number
    return problem


def options_bonus_scheme(draft, registry):
    return [Option("2+1", "+2 и +1"), Option("1+1+1", "+1, +1, +1")]


def put_bonus_scheme(draft, value, registry):
    if value == "1+1+1":
        abilities = draft_spec(draft, registry).abilities
        for ability in abilities:
            if draft.scores[ability] + 1 > 20:
                return over_twenty_message(ability)
        draft.bonus = {ability: 1 for ability in abilities}
    draft.bonus_scheme = value
    return None


def needs_bonus(draft, registry):
    return draft.bonus_scheme == "2+1"


def count_bonus(draft, registry):
    return 2


def label_bonus(draft, registry):
    return "Бонус предыстории +1" if draft.bonus else "Бонус предыстории +2"


def options_bonus(draft, registry):
    abilities = draft_spec(draft, registry).abilities
    return [
        Option(a, f"{ABILITY_NAMES[a]} (сейчас {draft.scores[a]})")
        for a in abilities if a not in draft.bonus
    ]


def put_bonus(draft, value, registry):
    amount = 1 if draft.bonus else 2
    if draft.scores[value] + amount > 20:
        return over_twenty_message(value)
    draft.bonus[value] = amount
    return None


def skill_option(skill):
    return Option(skill, SKILL_NAMES[skill])


def count_class_skills(draft, registry):
    return draft_class(draft, registry).skill_choices.count


def options_class_skills(draft, registry):
    taken = set(spec_skills(draft, registry)) | set(draft.class_skills)
    return [skill_option(s) for s in class_skill_options(draft_class(draft, registry), taken)]


def count_masteries(draft, registry):
    return draft_class(draft, registry).weapon_mastery_count


def needs_masteries(draft, registry):
    return count_masteries(draft, registry) > 0


def options_masteries(draft, registry):
    weapons = mastery_weapons(registry, draft_class(draft, registry))
    return [Option(w.id, w.name) for w in weapons if w.id not in draft.masteries]


def needs_style(draft, registry):
    return has_fighting_style(draft_class(draft, registry))


def options_style(draft, registry):
    return [Option(f.id, f.name) for f in fighting_styles(registry)]


def count_cantrips(draft, registry):
    # лимит класса, но не больше заговоров в контенте
    limit = spell_counts(draft_class(draft, registry))[0]
    return min(limit, len(class_spells(registry, draft.class_id, 0)))


def count_spells(draft, registry):
    limit = spell_counts(draft_class(draft, registry))[1]
    return min(limit, len(class_spells(registry, draft.class_id, 1)))


def count_prepared(draft, registry):
    return min(spell_counts(draft_class(draft, registry))[2], len(draft.spells))


def needs_cantrips(draft, registry):
    return count_cantrips(draft, registry) > 0


def needs_spells(draft, registry):
    return count_spells(draft, registry) > 0


def needs_prepared(draft, registry):
    return count_prepared(draft, registry) > 0


def options_cantrips(draft, registry):
    spells = class_spells(registry, draft.class_id, 0)
    return [Option(s.id, s.name) for s in spells if s.id not in draft.cantrips]


def options_spells(draft, registry):
    spells = class_spells(registry, draft.class_id, 1)
    return [Option(s.id, s.name) for s in spells if s.id not in draft.spells]


def options_prepared(draft, registry):
    return [
        Option(spell_id, registry.get("spell", spell_id).name)
        for spell_id in draft.spells if spell_id not in draft.prepared
    ]


def needs_species_skill(draft, registry):
    species = registry.get("species", draft.species_id)
    return "skill" in species_choice_keys(species, registry)


def needs_species_feat(draft, registry):
    species = registry.get("species", draft.species_id)
    return "feat" in species_choice_keys(species, registry)


def options_species_skill(draft, registry):
    taken = spec_skills(draft, registry) + draft.class_skills
    return [skill_option(s) for s in species_skill_options(taken)]


def options_species_feat(draft, registry):
    feats = origin_feats(registry, draft_spec(draft, registry).feat)
    return [Option(f.id, f.name) for f in feats]


def feat_picks_count(registry, feat_id):
    if not feat_id:
        return 0
    return feat_choice_count(registry.get("feat", feat_id))


def count_feat_picks_bg(draft, registry):
    return feat_picks_count(registry, draft_spec(draft, registry).feat)


def count_feat_picks_species(draft, registry):
    return feat_picks_count(registry, draft.species_feat)


def needs_feat_picks_bg(draft, registry):
    return count_feat_picks_bg(draft, registry) > 0


def needs_feat_picks_species(draft, registry):
    return count_feat_picks_species(draft, registry) > 0


def options_feat_picks(draft, registry):
    # навыки и инструменты, ещё не освоенные героем (предыстория, класс, вид, прежние выборы черт)
    picks = draft.feat_picks_bg + draft.feat_picks_species
    taken_skills = spec_skills(draft, registry) + draft.class_skills + picks
    if draft.species_skill:
        taken_skills.append(draft.species_skill)
    taken_tools = [draft_spec(draft, registry).tool] + picks
    return [Option(v, label) for v, label in feat_pick_options(registry, taken_skills, taken_tools)]


def needs_kit(draft, registry):
    return bool(kit_options(draft_class(draft, registry)))


def options_kit(draft, registry):
    kits = kit_options(draft_class(draft, registry))
    return [Option(k.id, kit_label(registry, k)) for k in kits]


def options_gear(draft, registry):
    return [
        Option("equipment", "Снаряжение предыстории"),
        Option("gold", "50 зм вместо снаряжения"),
    ]


def put_name(draft, value, registry):
    problems = name_problems(value.strip(), draft.taken_names)
    if problems:
        return problems[0][1]
    draft.name = value.strip()
    return None


def options_gender(draft, registry):
    options = [Option(gender, word.capitalize()) for gender, word in GENDER_WORDS.items()]
    return options + [Option("", "Не указывать")]


def put_pronouns(draft, value, registry):
    # «-» -- без особых местоимений (пустой ввод экран не принимает)
    text = value.strip()
    draft.pronouns = "" if text == "-" else text
    return None


def put_motive(draft, value, registry):
    problems = motive_problems(value.strip())
    if problems:
        return problems[0][1]
    draft.motive = value.strip()
    return None


def put_means(draft, value, registry):
    means = split_list(value)
    problems = means_problems(means)
    if problems:
        return problems[0][1]
    draft.means = means
    return None


STEPS = (
    StepDef("species", "species_id", "pick", "Вид героя", options=options_species),
    StepDef("class", "class_id", "pick", "Класс героя", options=options_class),
    StepDef("background", "background", "pick", "Предыстория", options=options_background),
    StepDef("method", "ability_method", "pick", "Метод характеристик", options=options_method),
    StepDef(
        "scores", "scores", "number", "Характеристики", options=options_scores,
        count=count_scores, put=put_score, label=label_scores,
    ),
    StepDef(
        "bonus_scheme", "bonus_scheme", "pick", "Схема бонуса предыстории",
        options=options_bonus_scheme, put=put_bonus_scheme,
    ),
    StepDef(
        "bonus", "bonus", "pick", "Бонус предыстории", needs=needs_bonus,
        options=options_bonus, count=count_bonus, put=put_bonus, label=label_bonus,
        on_error="bonus_scheme",
    ),
    StepDef(
        "class_skills", "class_skills", "multi", "Навыки класса",
        options=options_class_skills, count=count_class_skills,
    ),
    StepDef(
        "masteries", "masteries", "multi", "Мастерство оружия", needs=needs_masteries,
        options=options_masteries, count=count_masteries,
    ),
    StepDef(
        "style", "style", "pick", "Боевой стиль", needs=needs_style, options=options_style,
    ),
    StepDef(
        "cantrips", "cantrips", "multi", "Заговоры", needs=needs_cantrips,
        options=options_cantrips, count=count_cantrips,
    ),
    StepDef(
        "spells", "spells", "multi", "Заклинания 1 круга", needs=needs_spells,
        options=options_spells, count=count_spells,
    ),
    StepDef(
        "prepared", "prepared", "multi", "Подготовленные заклинания", needs=needs_prepared,
        options=options_prepared, count=count_prepared,
    ),
    StepDef(
        "species_skill", "species_skill", "pick", "Умелость: навык", needs=needs_species_skill,
        options=options_species_skill,
    ),
    StepDef(
        "species_feat", "species_feat", "pick", "Универсальность: черта",
        needs=needs_species_feat, options=options_species_feat,
    ),
    StepDef(
        "feat_picks_bg", "feat_picks_bg", "multi", "Выбор черты предыстории",
        needs=needs_feat_picks_bg, options=options_feat_picks, count=count_feat_picks_bg,
    ),
    StepDef(
        "feat_picks_species", "feat_picks_species", "multi", "Выбор черты вида",
        needs=needs_feat_picks_species, options=options_feat_picks,
        count=count_feat_picks_species,
    ),
    StepDef("kit", "kit", "pick", "Набор класса", needs=needs_kit, options=options_kit),
    StepDef("gear", "gear", "pick", "Снаряжение предыстории", options=options_gear),
    StepDef("name", "name", "text", "Имя героя", put=put_name),
    StepDef("gender", "gender", "pick", "Пол героя", options=options_gender),
    StepDef(
        "pronouns", "pronouns", "text", "Местоимения или обращение («-» — по полу)",
        put=put_pronouns,
    ),
    StepDef(
        "motive", "motive", "text", "Мотив героя — чего он добивается (до 200 символов)",
        put=put_motive,
    ),
    StepDef(
        "means", "means", "text", "Средства героя через запятую — чем он располагает (1–3)",
        put=put_means,
    ),
)
KEYS = tuple(step.key for step in STEPS)

# код проблемы листа -> шаг, куда вернуться (страховка после финального sheet_check)
CODE_STEPS = {
    "class_skills_invalid": "class_skills", "spells_invalid": "cantrips",
    "species_choices_invalid": "species_skill", "feat_choices_invalid": "feat_picks_bg",
    "background_bonus_invalid": "bonus_scheme", "abilities_invalid": "bonus_scheme",
    "point_buy_invalid": "method", "standard_array_invalid": "method",
    "hero_name_empty": "name", "hero_name_taken": "name",
    "motive_empty": "motive", "motive_too_long": "motive",
    "means_count": "means", "means_too_long": "means",
}


def step_for_code(code) -> str:
    return CODE_STEPS.get(code, "species")


def step_index(key) -> int:
    return KEYS.index(key)


def next_pos(draft, registry, start) -> int:
    # первый применимый шаг с позиции start; len(STEPS) -- шаги кончились
    for pos in range(start, len(STEPS)):
        needs = STEPS[pos].needs
        if needs is None or needs(draft, registry):
            return pos
    return len(STEPS)


def step_done(draft, registry, pos) -> bool:
    # шаг набран целиком: единичный сразу, повторяемый -- когда выбрано count значений
    step = STEPS[pos]
    if step.count is None:
        return True
    return len(getattr(draft, step.attr)) >= step.count(draft, registry)


def is_text_step(draft, pos) -> bool:
    # ввод строкой: текстовые шаги и свободный ввод характеристик
    step = STEPS[pos]
    return step.kind == "text" or (step.kind == "number" and draft.ability_method == "explicit")


def step_options(draft, registry, pos):
    step = STEPS[pos]
    return step.options(draft, registry) if step.options is not None else []


def apply_put(draft, registry, pos, value):
    # записать выбор шага; текст ошибки валидатора или None
    step = STEPS[pos]
    if step.put is not None:
        return step.put(draft, value, registry)
    if step.kind == "multi":
        getattr(draft, step.attr).append(value)
    else:
        setattr(draft, step.attr, value)
    return None


def clear_from(draft, key) -> None:
    # сбросить поля шага key и всех следующих
    fresh = Draft()
    for step in STEPS[step_index(key):]:
        setattr(draft, step.attr, getattr(fresh, step.attr))


def to_sheet(draft, registry) -> HeroSheet:
    species_choices = {}
    if draft.species_skill:
        species_choices["skill"] = draft.species_skill
    if draft.species_feat:
        species_choices["feat"] = draft.species_feat
    keys = origin_feat_keys(draft_spec(draft, registry), species_choices)
    feat_choices = {}
    for (key, _), picks in zip(keys, (draft.feat_picks_bg, draft.feat_picks_species), strict=False):
        if picks:
            feat_choices[key] = list(picks)
    choices = CharacterChoices(
        name=draft.name, gender=draft.gender or None, pronouns=draft.pronouns,
        species_id=draft.species_id, class_id=draft.class_id,
        background=draft.background, ability_method=draft.ability_method,
        ability_scores=dict(draft.scores), background_bonus=dict(draft.bonus),
        class_skills=list(draft.class_skills), weapon_masteries=list(draft.masteries),
        fighting_style=draft.style, species_choices=species_choices,
        spells=draft.cantrips + draft.spells, prepared=list(draft.prepared),
        feat_choices=feat_choices, background_gear=draft.gear or "equipment",
        class_kit=draft.kit,
    )
    return HeroSheet(choices=choices, motive=draft.motive, means=list(draft.means), opportunity=[])


def background_summary_lines(spec, registry) -> list[str]:
    feat = registry.get("feat", spec.feat)
    gear = ", ".join(item_name(registry, i) for i in spec.equipment) or "нет"
    lines = [
        f"Предыстория: {spec.name}",
        "Характеристики: " + ", ".join(ABILITY_NAMES[a] for a in spec.abilities),
        "Навыки: " + ", ".join(SKILL_NAMES[s] for s in spec.skills),
        f"Инструмент: {item_name(registry, spec.tool)}",
        f"Черта: {feat.name}",
        f"Снаряжение: {gear}; {format_cp(spec.gold_cp)}",
        f"Вместо снаряжения: {format_cp(spec.gold_option_cp)}",
    ]
    if spec.description:
        lines.append(spec.description)
    return lines
