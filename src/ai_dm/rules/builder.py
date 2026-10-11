from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_dm.content.models.common import ABILITIES, SKILLS
from ai_dm.rules.derived import ability_modifier, spell_slots_for, weapon_proficient
from ai_dm.rules.inventory import InventoryError, add_catalog_item, equip, find_item
from ai_dm.rules.progression import sync_resources
from ai_dm.rules.triggers_eval import validate_refs
from ai_dm.rules.uniqueness import name_taken
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.triggers import Trigger

# бюджет свободной предыстории (Аудит 1, P3): предметы + золото не дороже 50 зм
BACKGROUND_BUDGET_CP = 5000

BACKGROUND_MESSAGES = {
    "background_abilities": "предыстория: нужны три разные характеристики",
    "background_skills": "предыстория: нужны два разных существующих навыка",
    "background_tool": "предыстория: не указан инструмент",
    "background_feat": "предыстория: черта должна существовать и быть категории origin",
    "background_budget_invalid": "предыстория: предметы и золото дороже 50 зм",
}

BACKGROUND_DESCRIPTION_MAX = 300

SKILL_CONFLICT_MESSAGE = "навык класса уже даёт предыстория: выберите другой"

# тексты арифметических ошибок характеристик и бонуса: одни для build_character и шагов мастера
ABILITY_MESSAGES = {
    "point_buy_invalid": "покупка очков: неверные значения или больше 27 очков",
    "standard_array_invalid": "стандартный набор: нужны 15,14,13,12,10,8 по разу",
    "abilities_invalid": "нужны все шесть характеристик со значениями от 3 до 20",
}
BONUS_MESSAGE = "бонус предыстории: +2/+1 или +1/+1/+1"

# пределы мотива, средств и возможностей героя на лету
MOTIVE_MAX = 200
MEANS_MAX = 3
MEANS_ITEM_MAX = 120
OPPORTUNITY_MAX = 2
OPPORTUNITY_THEN_MAX = 200


class CharacterChoices(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    species_id: str
    class_id: str
    background: str | BackgroundSpec
    ability_method: Literal["standard_array", "point_buy", "explicit"]
    ability_scores: dict[str, int]
    background_bonus: dict[str, int]
    class_skills: list[str]
    weapon_masteries: list[str]
    fighting_style: str | None = None
    inventory: list[str] = Field(default_factory=list)
    equip: list[str] = Field(default_factory=list)
    species_choices: dict = Field(default_factory=dict)
    spells: list[str] = Field(default_factory=list)
    # подготовленные заклинания: подмножество выбранных заклинаний 1+ круга, не больше лимита класса
    prepared: list[str] = Field(default_factory=list)
    # выборы черт происхождения (Одарённый: три навыка из Skill или id инструментов).
    # Ключ — id черты; у второй черты с тем же id (предыстория и Универсальность) — "<id>#2".
    # Порядок черт: сначала предыстория, затем Универсальность.
    feat_choices: dict[str, list[str]] = Field(default_factory=dict)
    # вариант предыстории: "equipment" (A: предметы и золото) или "gold" (B: 50 зм)
    background_gear: Literal["equipment", "gold"] = "equipment"
    # id стартового набора класса (starting_kits класса); None -- без набора
    class_kit: str | None = None
    hero_id: str = "h1"
    ordinal: int = 1


class HeroSheet(BaseModel):
    # итог создания героя на лету: выборы, мотив, средства, возможности (сериализуется в meta)
    model_config = ConfigDict(extra="forbid")
    choices: CharacterChoices
    motive: str = ""
    means: list[str] = Field(default_factory=list)
    opportunity: list[Trigger] = Field(default_factory=list)


class ValidationErrors:
    def __init__(self, codes: list[str], messages: list[str]):
        self.codes = codes
        self.messages = messages


def validate_background(spec: BackgroundSpec, registry) -> list[str]:
    codes = []
    if (
        len(spec.abilities) != 3
        or len(set(spec.abilities)) != 3
        or any(a not in ABILITIES for a in spec.abilities)
    ):
        codes.append("background_abilities")
    if (
        len(spec.skills) != 2
        or len(set(spec.skills)) != 2
        or any(s not in SKILLS for s in spec.skills)
    ):
        codes.append("background_skills")
    if not spec.tool:
        codes.append("background_tool")
    if not registry.has("feat", spec.feat) or registry.get("feat", spec.feat).category != "origin":
        codes.append("background_feat")
    cost = spec.gold_cp
    for item_id in spec.equipment:
        found = find_item(registry, item_id)
        if found is not None:
            cost += found[1].cost_cp
    if cost > BACKGROUND_BUDGET_CP or spec.gold_option_cp > BACKGROUND_BUDGET_CP:
        codes.append("background_budget_invalid")
    return codes


def background_skill_conflict(spec: BackgroundSpec, class_skills) -> bool:
    return any(s in spec.skills for s in class_skills)


def background_check(spec: BackgroundSpec, registry, class_skills=()):
    # коды и тексты проблем свободной предыстории: путь модели и ручная правка (Б-2)
    codes = validate_background(spec, registry)
    messages = [BACKGROUND_MESSAGES[code] for code in codes]
    tool_known = registry.has("item", spec.tool) and registry.get("item", spec.tool).tool
    if spec.tool and not tool_known:
        codes.append("background_tool_unknown")
        messages.append(f"предыстория: нет такого инструмента: {spec.tool}")
    if background_skill_conflict(spec, class_skills):
        codes.append("class_skills_invalid")
        messages.append(SKILL_CONFLICT_MESSAGE)
    for item_id in spec.equipment:
        if find_item(registry, item_id) is None:
            codes.append("item_unknown")
            messages.append(f"неизвестный предмет предыстории: {item_id}")
    if spec.gold_cp < 0:
        codes.append("background_gold_negative")
        messages.append("предыстория: золото набора не может быть отрицательным")
    if len(spec.description) > BACKGROUND_DESCRIPTION_MAX:
        codes.append("description_too_long")
        messages.append(
            f"описание {len(spec.description)} символов, предел {BACKGROUND_DESCRIPTION_MAX}: "
            "сократи"
        )
    return codes, messages


def background_from_registry(background_id: str, registry) -> BackgroundSpec:
    b = registry.get("background", background_id)
    return BackgroundSpec(
        name=b.name,
        abilities=list(b.abilities),
        skills=list(b.skills),
        tool=b.tool,
        feat=b.feat,
        equipment=list(b.equipment),
        gold_cp=b.gold_cp,
        gold_option_cp=b.gold_option_cp,
    )


def over_twenty_message(ability) -> str:
    return f"характеристика выше 20 после бонуса: {ability}"


def point_buy_cost(scores, registry) -> int | None:
    # очки покупки за значения; None -- значение вне таблицы
    rows = registry.get("table", "point_buy").rows
    cost = {int(k): v for k, v in rows.items() if k != "budget"}
    if any(v not in cost for v in scores.values()):
        return None
    return sum(cost[v] for v in scores.values())


def check_ability_scores(choices, registry) -> bool:
    scores = choices.ability_scores
    if set(scores) != set(ABILITIES):
        return False
    if choices.ability_method == "standard_array":
        array = registry.get("table", "standard_array").rows.values()
        return sorted(scores.values(), reverse=True) == sorted(array, reverse=True)
    if choices.ability_method == "point_buy":
        total = point_buy_cost(scores, registry)
        return total is not None and total <= registry.get("table", "point_buy").rows["budget"]
    return all(3 <= v <= 20 for v in scores.values())


def species_choice_keys(species, registry) -> list[str]:
    # какие выборы требует вид: "skill" (Умелость), "feat" (Универсальность)
    keys = []
    for trait in species.traits:
        for effect in registry.get("feature", trait).effects:
            if effect.type == "proficiency" and effect.target == "skill":
                keys.append("skill")
            if effect.type == "feat_choice" and effect.target == "origin_feat":
                keys.append("feat")
    return keys


def origin_feat_keys(spec, species_choices) -> list[tuple[str, str]]:
    # черты происхождения героя с ключами для feat_choices: предыстория, затем Универсальность
    feat_ids = [spec.feat]
    if "feat" in species_choices:
        feat_ids.append(species_choices["feat"])
    result = []
    for feat_id in feat_ids:
        key = feat_id
        if any(k == feat_id for k, _ in result):
            key = f"{feat_id}#2"
        result.append((key, feat_id))
    return result


def feat_choice_count(feat) -> int:
    # сколько навыков/инструментов выбирает черта (Одарённый — 3)
    count = 0
    for e in feat.effects:
        if e.type == "proficiency" and e.target == "skill_or_tool":
            count += e.count or 0
    return count


def check_background_bonus(bonus: dict[str, int], spec: BackgroundSpec) -> bool:
    if any(a not in spec.abilities for a in bonus):
        return False
    return sorted(bonus.values()) in ([1, 2], [1, 1, 1])


def class_kit_problem(choices, char_class) -> str | None:
    # текст проблемы с class_kit или None
    if choices.class_kit is None or char_class is None:
        return None
    ids = [kit.id for kit in char_class.starting_kits]
    if choices.class_kit in ids:
        return None
    return f"неизвестный набор класса: {choices.class_kit}; доступны: {', '.join(ids)}"


def apply_class_kit(hero, choices, registry) -> None:
    # стартовый набор класса: предметы, надетое, золото (после class_kit_problem набор есть)
    if choices.class_kit is None:
        return
    char_class = registry.get("class", choices.class_id)
    kit = next(k for k in char_class.starting_kits if k.id == choices.class_kit)
    for item_id in kit.items:
        add_catalog_item(hero, registry, item_id)
    for item_id in kit.equip:
        equip(hero, item_id, registry)
    hero.money_cp += kit.gold_cp


def build_character(choices: CharacterChoices, registry) -> HeroState | ValidationErrors:
    """Собирает героя 1 уровня или возвращает ValidationErrors (коды и сообщения по-русски).

    Коды ошибок: unknown_class, unknown_species, unknown_background, background_abilities,
    background_skills, background_tool, background_feat, point_buy_invalid,
    standard_array_invalid, abilities_invalid, background_bonus_invalid, class_skills_invalid,
    mastery_count_invalid, mastery_weapon_invalid, fighting_style_invalid, spells_invalid
    (в т.ч. подготовленные вне выбранных или сверх лимита), feat_choices_invalid,
    background_budget_invalid (предметы + золото свободной предыстории дороже 50 зм),
    class_kit_unknown (нет набора с таким id у класса),
    species_choices_invalid, item_unknown (предмета нет в контенте), equip_invalid (надеваемого
    нет в инвентаре, предмет нельзя надеть, двуручное со щитом, доспех без владения).
    """
    codes = []
    messages = []

    def error(code, message):
        codes.append(code)
        messages.append(message)

    char_class = None
    if registry.has("class", choices.class_id):
        char_class = registry.get("class", choices.class_id)
    else:
        error("unknown_class", f"неизвестный класс: {choices.class_id}")
    species = None
    if registry.has("species", choices.species_id):
        species = registry.get("species", choices.species_id)
    else:
        error("unknown_species", f"неизвестный вид: {choices.species_id}")

    kit_problem = class_kit_problem(choices, char_class)
    if kit_problem is not None:
        error("class_kit_unknown", kit_problem)

    spec = None
    if isinstance(choices.background, BackgroundSpec):
        spec = choices.background
        for code in validate_background(spec, registry):
            error(code, BACKGROUND_MESSAGES[code])
    elif registry.has("background", choices.background):
        spec = background_from_registry(choices.background, registry)
    else:
        error("unknown_background", f"неизвестная предыстория: {choices.background}")

    scores_ok = check_ability_scores(choices, registry)
    if not scores_ok:
        if choices.ability_method == "point_buy":
            error("point_buy_invalid", ABILITY_MESSAGES["point_buy_invalid"])
        elif choices.ability_method == "standard_array":
            error("standard_array_invalid", ABILITY_MESSAGES["standard_array_invalid"])
        else:
            error("abilities_invalid", ABILITY_MESSAGES["abilities_invalid"])

    bonus_ok = spec is not None and check_background_bonus(choices.background_bonus, spec)
    if spec is not None and not bonus_ok:
        error("background_bonus_invalid", BONUS_MESSAGE)

    if scores_ok and bonus_ok:
        for ability, value in choices.background_bonus.items():
            if choices.ability_scores[ability] + value > 20:
                error("abilities_invalid", over_twenty_message(ability))

    if char_class is not None:
        options = char_class.skill_choices.options
        skills = choices.class_skills
        if (
            len(skills) != char_class.skill_choices.count
            or len(set(skills)) != len(skills)
            or any(s not in options for s in skills)
        ):
            error("class_skills_invalid", "навыки класса: неверное число или не из списка")
        if spec is not None and background_skill_conflict(spec, skills):
            error("class_skills_invalid", SKILL_CONFLICT_MESSAGE)
        if len(choices.weapon_masteries) != char_class.weapon_mastery_count:
            error("mastery_count_invalid", "неверное число мастерств оружия")

    if len(set(choices.weapon_masteries)) != len(choices.weapon_masteries):
        error("mastery_weapon_invalid", "мастерство оружия: повторяющееся оружие")
    for weapon_id in choices.weapon_masteries:
        weapon = registry.get("weapon", weapon_id) if registry.has("weapon", weapon_id) else None
        if weapon is None or weapon.mastery is None:
            error("mastery_weapon_invalid", f"у оружия нет мастерства: {weapon_id}")
        elif char_class is not None and not weapon_proficient(char_class, weapon):
            error("mastery_weapon_invalid", f"нет владения оружием для мастерства: {weapon_id}")

    style = choices.fighting_style
    if style is not None:
        feat = registry.get("feat", style) if registry.has("feat", style) else None
        has_style = char_class is not None and any(
            r.feature == "fighting_style" and r.level <= 1 for r in char_class.features
        )
        if char_class is not None and not has_style:
            error("fighting_style_invalid", "у класса нет боевого стиля")
        elif feat is None or feat.category != "fighting_style":
            error("fighting_style_invalid", f"не боевой стиль: {style}")

    cantrips = []
    level1_spells = []
    if choices.spells and char_class is not None:
        spellcasting = char_class.spellcasting
        if spellcasting is None:
            error("spells_invalid", "класс не владеет заклинаниями")
        else:
            max_circle = max(spell_slots_for(registry, spellcasting.progression, 1))
            if len(set(choices.spells)) != len(choices.spells):
                error("spells_invalid", "заклинания: есть повторы")
            for spell_id in choices.spells:
                if not registry.has("spell", spell_id):
                    error("spells_invalid", f"неизвестное заклинание: {spell_id}")
                    continue
                spell = registry.get("spell", spell_id)
                if choices.class_id not in spell.classes:
                    error("spells_invalid", f"заклинание не из списка класса: {spell_id}")
                elif spell.level > max_circle:
                    error("spells_invalid", f"круг заклинания недоступен: {spell_id}")
                elif spell.level == 0:
                    cantrips.append(spell_id)
                else:
                    level1_spells.append(spell_id)
            if spellcasting.cantrips is not None and len(cantrips) > spellcasting.cantrips:
                error("spells_invalid", f"заговоров больше {spellcasting.cantrips}")
            if spellcasting.spells is not None and len(level1_spells) > spellcasting.spells:
                error("spells_invalid", f"заклинаний 1 круга больше {spellcasting.spells}")

    if choices.prepared:
        spellcasting = char_class.spellcasting if char_class is not None else None
        if spellcasting is None:
            error("spells_invalid", "подготовленные заклинания: класс не владеет заклинаниями")
        else:
            if len(set(choices.prepared)) != len(choices.prepared):
                error("spells_invalid", "подготовленные заклинания: есть повторы")
            if any(p not in level1_spells for p in choices.prepared):
                error("spells_invalid", "подготовлены не выбранные заклинания 1+ круга")
            limit = spellcasting.prepared
            if limit is not None and len(choices.prepared) > limit:
                error("spells_invalid", f"подготовленных заклинаний больше {limit}")

    feat_skills = []
    feat_tools = []
    needed = {}
    if spec is not None:
        for key, feat_id in origin_feat_keys(spec, choices.species_choices):
            if registry.has("feat", feat_id):
                count = feat_choice_count(registry.get("feat", feat_id))
                if count:
                    needed[key] = count
    given_choices = choices.feat_choices
    if set(given_choices) != set(needed) or any(
        len(given_choices[k]) != needed[k] for k in needed
    ):
        error("feat_choices_invalid", "выбор черты: не хватает, лишний или неверное число выборов")
    else:
        taken_skills = list(spec.skills) + choices.class_skills if spec is not None else []
        if "skill" in choices.species_choices:
            taken_skills.append(choices.species_choices["skill"])
        taken_tools = [spec.tool] if spec is not None else []
        for key in needed:
            for pick in given_choices[key]:
                if pick in SKILLS and pick not in taken_skills:
                    taken_skills.append(pick)
                    feat_skills.append(pick)
                elif (
                    pick not in SKILLS
                    and registry.has("item", pick)
                    and registry.get("item", pick).tool
                    and pick not in taken_tools
                ):
                    taken_tools.append(pick)
                    feat_tools.append(pick)
                else:
                    error("feat_choices_invalid", f"выбор черты: недопустимый или повтор: {pick}")

    if species is not None:
        keys = species_choice_keys(species, registry)
        given = choices.species_choices
        if set(given) != set(keys):
            error("species_choices_invalid", "выбор вида: не хватает или лишний выбор")
        else:
            if "skill" in given:
                skill = given["skill"]
                taken = (spec.skills if spec is not None else []) + choices.class_skills
                taken = taken + feat_skills
                if skill not in SKILLS or skill in taken:
                    error("species_choices_invalid", "умелость: нужен новый навык из списка")
            if "feat" in given:
                feat_id = given["feat"]
                origin = registry.has("feat", feat_id) and (
                    registry.get("feat", feat_id).category == "origin"
                )
                if not origin:
                    error("species_choices_invalid", "универсальность: нужна черта происхождения")
                elif (
                    spec is not None
                    and feat_id == spec.feat
                    and not registry.get("feat", feat_id).repeatable
                ):
                    # повтор разрешён только для черт со свойством Repeatable (SRD)
                    error("species_choices_invalid", "универсальность: черта уже у предыстории")

    gear = spec.equipment if spec is not None and choices.background_gear == "equipment" else []
    if spec is not None:
        for item_id in spec.equipment:
            if find_item(registry, item_id) is None:
                error("item_unknown", f"неизвестный предмет предыстории: {item_id}")
    for item_id in choices.inventory:
        if find_item(registry, item_id) is None:
            error("item_unknown", f"неизвестный предмет: {item_id}")
    for item_id in choices.equip:
        found = find_item(registry, item_id)
        if item_id not in choices.inventory and item_id not in gear:
            error("equip_invalid", f"надеваемого нет в инвентаре: {item_id}")
        elif found is not None and found[0] == "item":
            error("equip_invalid", f"предмет нельзя надеть: {item_id}")

    if codes:
        return ValidationErrors(codes, messages)

    abilities = dict(choices.ability_scores)
    for ability, value in choices.background_bonus.items():
        abilities[ability] += value

    skill_proficiencies = list(spec.skills)
    for skill in choices.class_skills:
        if skill not in skill_proficiencies:
            skill_proficiencies.append(skill)
    feats = [spec.feat]
    if style is not None:
        feats.append(style)
    if "skill" in choices.species_choices:
        skill_proficiencies.append(choices.species_choices["skill"])
    skill_proficiencies += feat_skills
    if "feat" in choices.species_choices:
        feats.append(choices.species_choices["feat"])

    sheet = CharacterSheet(
        species_id=choices.species_id,
        classes=[ClassLevel(class_id=choices.class_id)],
        level_history=[choices.class_id],
        background=spec,
        abilities=abilities,
        skill_proficiencies=skill_proficiencies,
        tool_proficiencies=[spec.tool] + feat_tools,
        feats=feats,
        weapon_masteries=list(choices.weapon_masteries),
        spells_known={choices.class_id: cantrips + level1_spells},
        spells_prepared={choices.class_id: list(choices.prepared)},
    )
    hp = max(1, char_class.hit_die + ability_modifier(abilities["con"]))
    hero = HeroState(
        id=choices.hero_id,
        ordinal=choices.ordinal,
        name=choices.name,
        sheet=sheet,
        creature=CreatureState(hp_current=hp, hp_max=hp),
    )
    sync_resources(hero, registry)
    if choices.background_gear == "equipment":
        hero.money_cp = spec.gold_cp
    else:
        hero.money_cp = spec.gold_option_cp
    for item_id in gear:
        add_catalog_item(hero, registry, item_id)
    for item_id in choices.inventory:
        add_catalog_item(hero, registry, item_id)
    apply_class_kit(hero, choices, registry)
    for item_id in choices.equip:
        try:
            equip(hero, item_id, registry)
        except InventoryError as err:
            return ValidationErrors(["equip_invalid"], [f"нельзя надеть: {err}"])
    return hero


def name_problems(name, taken_names) -> list[tuple[str, str]]:
    # имя героя: не пустое и не занятое (NPC, бог, фракция)
    if not name.strip():
        return [("hero_name_empty", "имя героя не может быть пустым")]
    if name_taken(name, taken_names):
        return [("hero_name_taken", f"имя {name!r} уже занято (NPC, бог, фракция или герой)")]
    return []


def sheet_name_problems(sheet, taken_names) -> list[tuple[str, str]]:
    return name_problems(sheet.choices.name, taken_names)


def opportunity_problems(sheet, known, registry) -> list[tuple[str, str]]:
    # возможности героя: число, id, намерение, ссылки условий (ссылки -- только при known)
    problems = []
    if len(sheet.opportunity) > OPPORTUNITY_MAX:
        problems.append(("opportunity_count", f"возможностей героя не больше {OPPORTUNITY_MAX}"))
    seen = set()
    for trigger in sheet.opportunity:
        if not trigger.id.strip() or trigger.id in seen:
            message = f"возможность: пустой или повторный id {trigger.id!r}"
            problems.append(("opportunity_id", message))
        seen.add(trigger.id)
        if not trigger.then.strip() or len(trigger.then) > OPPORTUNITY_THEN_MAX:
            problems.append((
                "opportunity_then",
                f"возможность {trigger.id!r}: намерение от 1 до {OPPORTUNITY_THEN_MAX} символов",
            ))
        if known is not None:
            for text in validate_refs(trigger.if_, known, registry):
                problems.append(("opportunity_ref", f"возможность {trigger.id!r}: {text}"))
    return problems


def motive_problems(motive) -> list[tuple[str, str]]:
    problems = []
    if not motive.strip():
        problems.append(("motive_empty", "мотив героя не может быть пустым"))
    if len(motive) > MOTIVE_MAX:
        problems.append(("motive_too_long", f"мотив длиннее {MOTIVE_MAX} символов: сократи"))
    return problems


def means_problems(means) -> list[tuple[str, str]]:
    problems = []
    if not 1 <= len(means) <= MEANS_MAX:
        problems.append(("means_count", "средства героя: от одного до трёх средств"))
    if any(len(m) > MEANS_ITEM_MAX for m in means):
        problems.append(("means_too_long", f"средство длиннее {MEANS_ITEM_MAX} символов: сократи"))
    return problems


def hooks_problems(motive, means) -> list[tuple[str, str]]:
    # мотив и средства героя без возможностей
    return motive_problems(motive) + means_problems(means)


def sheet_hooks_problems(sheet, known, registry) -> list[tuple[str, str]]:
    # мотив, средства, возможности героя
    problems = hooks_problems(sheet.motive, sheet.means)
    return problems + opportunity_problems(sheet, known, registry)


def sheet_check(sheet, registry, *, known=None, taken_names=()):
    # единый валидатор листа героя: путь модели и ручная правка; (коды, тексты) в стабильном порядке
    built = build_character(sheet.choices, registry)
    pairs = []
    if isinstance(built, ValidationErrors):
        pairs = list(zip(built.codes, built.messages, strict=True))
    spec = sheet.choices.background
    if isinstance(spec, BackgroundSpec):
        extra = background_check(spec, registry, sheet.choices.class_skills)
        pairs += [pair for pair in zip(*extra, strict=True) if pair not in pairs]
    pairs += sheet_name_problems(sheet, taken_names)
    pairs += sheet_hooks_problems(sheet, known, registry)
    return [code for code, _ in pairs], [message for _, message in pairs]
