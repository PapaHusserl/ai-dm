# Общие помощники тестов «героя на лету» (Б1а, B1-PLAN, раздел B). Не фикстуры, а функции.
#   sheet_input(**changes)     -- канонический валидный ввод инструмента hero_sheet (словарь):
#                                 человек-воин, standard_array, набор класса "a", предыстория как
#                                 в spec_call Б0, motive, одно средство, один narrative-триггер;
#   sheet_call(call_id, **ch)  -- то же вызовом инструмента для ScriptedAdapter;
#   base_sheet(**changes)      -- тот же лист как HeroSheet (без протокола);
#   sheet_task(pack, **kw)     -- SheetTask по паку (known_ids / taken_names);
#   deps(adapter, registry, cfg, tmp_path=None, **kw) -- HeroCreateDeps с журналом и леджером;
#   vale_pack(registry)        -- пак Вейл (npc innkeeper «Гарт», grakh «Гракх»; локации vale,
#                                 lame_goose, cellar; богов и фракций нет).
import sys
from datetime import UTC, datetime
from pathlib import Path

TESTS_UNIT = Path(__file__).resolve().parents[1]
for sub in ("master", "protocol", "llm", "rules", "game"):
    if str(TESTS_UNIT / sub) not in sys.path:
        sys.path.insert(0, str(TESTS_UNIT / sub))

from master_kit import app_cfg  # noqa: E402

from ai_dm.llm.cost import CostLedger  # noqa: E402
from ai_dm.llm.journal import Journal  # noqa: E402
from ai_dm.rules.builder import CharacterChoices, HeroSheet  # noqa: E402
from ai_dm.rules.triggers_eval import KnownIds  # noqa: E402
from ai_dm.state.hero import BackgroundSpec  # noqa: E402
from ai_dm.state.triggers import Trigger  # noqa: E402

NOW = datetime(2026, 10, 8, 12, 0, tzinfo=UTC)
HERO_NAME = "Борин"
SCORES = {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}


def background_input(**changes):
    data = {
        "name": "Бывший цирковой акробат", "abilities": ["dex", "con", "cha"],
        "skills": ["acrobatics", "performance"], "tool": "thieves_tools", "feat": "alert",
        "equipment": ["crowbar"], "gold_cp": 1000, "description": "Вырос в бродячем цирке.",
    }
    data.update(changes)
    return data


def trigger_input(**changes):
    data = {
        "id": "o1", "then": "отомстить", "kind": "narrative", "ref": "герой узнаёт о сестре",
        "status": "", "gte": 0,
    }
    data.update(changes)
    return data


def sheet_input(**changes):
    data = {
        "type": "hero_sheet", "name": HERO_NAME, "species_id": "human", "class_id": "fighter",
        "ability_method": "standard_array", "ability_scores": dict(SCORES),
        "bonus_plus2": "dex", "bonus_plus1": ["con"],
        "class_skills": ["perception", "survival"],
        "weapon_masteries": ["longsword", "greatsword", "shortsword"],
        "fighting_style": "defense", "class_kit": "a", "spells": [], "prepared": [],
        "species_skill": "stealth", "species_feat": "skilled", "feat_skills": [],
        "species_feat_skills": ["medicine", "religion", "nature"],
        "background": background_input(), "background_gear": "equipment",
        "motive": "Найти сестру.", "means": ["острый ум"], "opportunity": [trigger_input()],
    }
    data.update(changes)
    return data


def sheet_call(call_id="sheet-1", **changes):
    return {"id": call_id, "name": "hero_sheet", "input": sheet_input(**changes)}


def base_choices(**changes):
    choices = CharacterChoices(
        name=HERO_NAME, species_id="human", class_id="fighter",
        background=BackgroundSpec(**background_input(), gold_option_cp=5000),
        ability_method="standard_array", ability_scores=dict(SCORES),
        background_bonus={"dex": 2, "con": 1}, class_skills=["perception", "survival"],
        weapon_masteries=["longsword", "greatsword", "shortsword"], fighting_style="defense",
        species_choices={"skill": "stealth", "feat": "skilled"},
        feat_choices={"skilled": ["medicine", "religion", "nature"]}, class_kit="a",
        hero_id="hero",
    )
    return choices.model_copy(update=changes)


def narrative_trigger(trigger_id="o1", text="герой узнаёт о сестре", then="отомстить"):
    return Trigger.model_validate(
        {"id": trigger_id, "if": {"narrative": text}, "then": then, "once": True}
    )


def base_sheet(**changes):
    sheet = HeroSheet(
        choices=base_choices(), motive="Найти сестру.", means=["острый ум"],
        opportunity=[narrative_trigger()],
    )
    return sheet.model_copy(update=changes)


def known(npcs=(), locations=(), pantheon=()):
    return KnownIds(npcs=set(npcs), locations=set(locations), pantheon=set(pantheon))


def vale_pack(registry):
    from ai_dm.campaign.loader import load_pack
    from ai_dm.game.starter import VALE_DIR

    return load_pack(VALE_DIR, registry)


def sheet_task(pack, **kw):
    from ai_dm.campaign.build import known_ids, taken_names
    from ai_dm.protocol.context import SheetTask

    return SheetTask(known=known_ids(pack), taken_names=taken_names(pack), **kw)


def deps(adapter, registry, cfg, tmp_path=None, **kw):
    from ai_dm.game.hero_create import HeroCreateDeps

    extra = {}
    if tmp_path is not None:
        extra["journal"] = Journal(tmp_path, "w1", app_cfg().journal)
        extra["ledger"] = CostLedger(tmp_path, "w1")
    kw.setdefault("now", lambda: NOW)
    return HeroCreateDeps(
        adapter=adapter, app_cfg=app_cfg(), registry=registry, cfg=cfg, **extra, **kw
    )


# Б2а (B2-PLAN, раздел B): помощники пошагового создания героя (HeroWizard).
#   wizard_script(**kw)   -- канонические ответы [(ключ шага, строка)] для человека-воина/солдата,
#                            стандартного набора: воспроизводят base_sheet() Б1 с
#                            background="soldier"; kw: name, motive, means -- тексты шагов;
#   wizard_picks(**kw)    -- то же списком строк (цифры считаются по тем же запросам
#                            rules.hero_options, что строят меню шагов, поэтому порядок пунктов
#                            не зашит в тесты);
#   wizard_sheet(**kw)    -- HeroSheet, который должен получиться (канон Б1, без opportunity);
#   lines_before(script, key) / lines_after(script, key) -- срезы сценария по ключу шага;
#   walk(wizard, lines)   -- start() и submit() каждой строки; возвращает последний Step;
#   first_option_walk(wizard, **fixed)
#                            -- политика «всегда 1», кроме выбора вида/класса/предыстории/метода и
#                            текстовых шагов (имя, мотив, средства, свободный ввод
#                            характеристик); доходит до ревью; started=True -- продолжить мастер.
FIRST_OPTION_TEXTS = {"name": "Борин", "motive": "Найти сестру.", "means": "острый ум"}
FIRST_OPTION_LIMIT = 200


def number_in(values, value):
    return str(list(values).index(value) + 1)


def number_in_rest(values, chosen, value):
    # номер среди оставшихся (шаг с повтором показывает список без уже выбранных)
    rest = [v for v in values if v not in chosen]
    return number_in(rest, value)


def multi_numbers(values, picked):
    chosen = []
    lines = []
    for value in picked:
        lines.append(number_in_rest(values, chosen, value))
        chosen.append(value)
    return lines


def wizard_script(**kw):
    from ai_dm.content.loader import load_registry
    from ai_dm.rules import hero_options as opts

    registry = load_registry()
    choices = base_choices()
    char_class = registry.get("class", "fighter")
    soldier = registry.get("background", "soldier")
    texts = {**{"name": HERO_NAME, "motive": "Найти сестру.", "means": "острый ум"}, **kw}
    script = [
        ("species", number_in([s.id for s in opts.species_options(registry)], "human")),
        ("class", number_in([c.id for c in opts.class_options(registry)], "fighter")),
        ("background", number_in([b.id for b in opts.background_options(registry)], "soldier")),
        ("method", "1"),
    ]
    array = opts.standard_array(registry)
    used = []
    for ability in ("str", "dex", "con", "int", "wis", "cha"):
        value = SCORES[ability]
        script.append(("scores", number_in_rest(array, used, value)))
        used.append(value)
    script.append(("bonus_scheme", "1"))
    script.append(("bonus", number_in(soldier.abilities, "dex")))
    rest = [a for a in soldier.abilities if a != "dex"]
    script.append(("bonus", number_in(rest, "con")))
    taken = set(soldier.skills)
    skills = opts.class_skill_options(char_class, taken)
    script += [("class_skills", n) for n in multi_numbers(skills, choices.class_skills)]
    weapons = [w.id for w in opts.mastery_weapons(registry, char_class)]
    script += [("masteries", n) for n in multi_numbers(weapons, choices.weapon_masteries)]
    styles = [f.id for f in opts.fighting_styles(registry)]
    script.append(("style", number_in(styles, "defense")))
    taken |= set(choices.class_skills)
    script.append(("species_skill", number_in(opts.species_skill_options(taken), "stealth")))
    feats = [f.id for f in opts.origin_feats(registry, soldier.feat)]
    script.append(("species_feat", number_in(feats, "skilled")))
    taken.add("stealth")
    picks = [v for v, _ in opts.feat_pick_options(registry, taken, {soldier.tool})]
    skilled = choices.feat_choices["skilled"]
    script += [("feat_picks_species", n) for n in multi_numbers(picks, skilled)]
    kits = [k.id for k in opts.kit_options(char_class)]
    script.append(("kit", number_in(kits, "a")))
    script.append(("gear", "1"))
    script += [("name", texts["name"]), ("motive", texts["motive"]), ("means", texts["means"])]
    return script


def wizard_picks(**kw):
    return [line for _, line in wizard_script(**kw)]


def lines_before(script, key):
    result = []
    for step_key, line in script:
        if step_key == key:
            break
        result.append(line)
    return result


def lines_after(script, key):
    # строки после последней строки шага key
    last = max(i for i, (step_key, _) in enumerate(script) if step_key == key)
    return [line for _, line in script[last + 1:]]


def wizard_sheet(**changes):
    sheet = HeroSheet(
        choices=base_choices(background="soldier", hero_id="h1"), motive="Найти сестру.",
        means=["острый ум"], opportunity=[],
    )
    return sheet.model_copy(update=changes)


def walk(wizard, lines):
    step = wizard.start()
    for line in lines:
        step = wizard.submit(line)
    return step


def first_option_walk(wizard, **fixed):
    # fixed: species, cls, background, method -- номера пунктов (по умолчанию 1);
    # started=True -- продолжить уже начатый мастер (без start())
    from ai_dm.game.hero_steps import STEPS

    started = fixed.pop("started", False)
    numbers = {
        "species": fixed.get("species", 1), "class": fixed.get("cls", 1),
        "background": fixed.get("background", 1), "method": fixed.get("method", 1),
    }
    step = None if started else wizard.start()
    for _ in range(FIRST_OPTION_LIMIT):
        if wizard.state == "review":
            return step
        key = STEPS[wizard.pos].key
        if key in FIRST_OPTION_TEXTS:
            line = FIRST_OPTION_TEXTS[key]
        elif key == "scores" and wizard.draft.ability_method == "explicit":
            line = "10"
        else:
            line = str(numbers.get(key, 1))
        step = wizard.submit(line)
    raise AssertionError("мастер шагов не дошёл до ревью")
