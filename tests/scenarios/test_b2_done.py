# Критерий Б2а (B2-PLAN, раздел B): пошаговый герой тремя методами на мок-модели.
# Ошибка (покупка очков > 27, свободный ввод 21, бонус выше 20, занятое имя) -- тем же текстом,
# что у sheet_check на листе с тем же дефектом -> исправление -> ревью -> принять -> мир с пресетом
# -> мок-ход -> сейв -> загрузка (лист, motive/means целы, opportunity пуст) -> replay без
# расхождения. Заклинатели (волшебник, жрец) собираются пошагово, заклинания в лимите.
# ИИ в пошаговом пути нет: сценарий идёт без мока модели (кроме текста хода).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))

from game_kit import SAVED_AT, core_dump, make_app  # noqa: E402
from hero_kit import (  # noqa: E402
    deps,
    first_option_walk,
    lines_after,
    lines_before,
    sheet_task,
    vale_pack,
    walk,
    wizard_script,
    wizard_sheet,
)
from master_kit import scripted, text_step  # noqa: E402
from ui_kit import SEED, cli, write_script  # noqa: E402

from ai_dm.campaign.presets import apply_preset, load_presets  # noqa: E402
from ai_dm.game.hero_create import edit_sheet, read_hero_sheet  # noqa: E402
from ai_dm.game.starter import new_world_from_pack  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.rules.builder import (  # noqa: E402
    ABILITY_MESSAGES,
    HeroSheet,
    over_twenty_message,
    sheet_check,
)
from ai_dm.ui.hero_wizard import WIZARD_REVIEW_MENU, HeroWizard  # noqa: E402

TURN_TEXT = "Огонь в очаге трещит, и трактирщик поднимает глаза."
SCRIPT = wizard_script()


def steps_item_number():
    # номер пункта «Создать пошагово» зависит от числа пресетов героя пака
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import hero_presets

    return str(len(hero_presets(vale_pack(load_registry()))) + 2)


def make(registry, cfg):
    task = sheet_task(vale_pack(registry))
    return HeroWizard(deps(None, registry, cfg), task, 80), task


def texts(step):
    parts = []
    for block in step.blocks:
        parts.append(block.text)
        parts.extend(block.items)
    return "\n".join(parts)


def menu_of(step):
    return [item for block in step.blocks if block.kind == "menu" for item in block.items]


def number_of(step, text):
    for number, item in enumerate(menu_of(step), start=1):
        if item.startswith(text):
            return str(number)
    raise AssertionError(f"нет пункта {text!r} в {menu_of(step)}")


def edited(sheet, *lines):
    for line in lines:
        sheet = edit_sheet(sheet, line)
        assert isinstance(sheet, HeroSheet), sheet
    return sheet


def messages_of(sheet, registry, task):
    return sheet_check(sheet, registry, known=task.known, taken_names=task.taken_names)[1]


def accept(wizard, registry, task):
    # ревью -> принять; лист обязан пройти sheet_check
    assert wizard.state == "review"
    step = wizard.submit("1")
    assert step.quit is True
    sheet = wizard.sheet
    assert sheet_check(sheet, registry, known=task.known, taken_names=task.taken_names) == (
        [], [],
    )
    return sheet


def play_and_reload(registry, cfg, tmp_path, sheet):
    # мир с пресетом -> мок-ход -> сейв -> загрузка
    pack = vale_pack(registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT,
        preset_id="heroic",
    )
    assert bundle.world.tone == apply_preset(pack.manifest.tone, load_presets()["heroic"])
    app = make_app(registry, tmp_path, scripted([text_step(TURN_TEXT)]), bundle=bundle)
    assert app.handle("Осматриваюсь").narration == TURN_TEXT
    app.save_current("auto")
    loaded = load_slot(tmp_path, "w1", "auto")
    assert core_dump(loaded) == core_dump(app.bundle)
    return loaded.heroes[0]


# метод 1: стандартный набор; ошибка -- занятое имя

def test_standard_array_hero_with_taken_name_error(registry, cfg, tmp_path):
    wizard, task = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "name"))
    assert "Имя героя" in texts(step)
    step = wizard.submit("гракх")
    defect = edited(wizard_sheet(), "name = гракх")
    [expected] = messages_of(defect, registry, task)
    assert expected in texts(step)
    assert "уже занято" in expected
    keys = ("name", "gender", "pronouns", "motive", "means")
    walk_rest = [line for key, line in SCRIPT if key in keys]
    for line in walk_rest:
        step = wizard.submit(line)
    assert menu_of(step) == list(WIZARD_REVIEW_MENU)
    sheet = accept(wizard, registry, task)
    assert sheet == wizard_sheet()
    hero = play_and_reload(registry, cfg, tmp_path, sheet)
    assert hero.name == "Борин"
    assert hero.sheet.class_id == "fighter"
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert hero.opportunity == []
    assert {e.item_id for e in hero.inventory} >= {"chain_mail", "greatsword", "explorers_pack"}
    assert hero.equipped.armor == "chain_mail"


# метод 2: покупка очков; ошибка -- больше 27

def test_point_buy_hero_with_over_budget_error(registry, cfg, tmp_path):
    wizard, task = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "method") + ["2"])
    for _ in range(3):
        step = wizard.submit(number_of(step, "15"))
    step = wizard.submit(number_of(step, "15"))
    defect = edited(
        wizard_sheet(), "method = point_buy", "str = 15", "dex = 15", "con = 15", "int = 15",
        "wis = 8", "cha = 8",
    )
    [expected] = messages_of(defect, registry, task)
    assert expected == ABILITY_MESSAGES["point_buy_invalid"]
    assert expected in texts(step)
    for value in ("8", "8", "8"):
        step = wizard.submit(number_of(step, value))
    for line in lines_after(SCRIPT, "scores"):
        step = wizard.submit(line)
    sheet = accept(wizard, registry, task)
    assert sheet.choices.ability_method == "point_buy"
    assert sheet.choices.ability_scores == {
        "str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8,
    }
    hero = play_and_reload(registry, cfg, tmp_path, sheet)
    assert hero.sheet.abilities["dex"] == 17
    assert hero.sheet.abilities["con"] == 16
    assert hero.motive == "Найти сестру."


# метод 3: свободный ввод; ошибки -- 21 и бонус выше 20

def test_explicit_hero_with_21_and_bonus_over_20_errors(registry, cfg, tmp_path):
    wizard, task = make(registry, cfg)
    walk(wizard, lines_before(SCRIPT, "method") + ["3"])
    step = wizard.submit("21")
    defect = edited(wizard_sheet(), "method = explicit", "str = 21")
    [expected] = messages_of(defect, registry, task)
    assert expected == ABILITY_MESSAGES["abilities_invalid"]
    assert expected in texts(step)
    for value in ("19", "14", "13", "12", "10", "8"):
        step = wizard.submit(value)
    step = wizard.submit("1")
    step = wizard.submit(number_of(step, "Сила"))
    defect = edited(
        wizard_sheet(), "method = explicit", "str = 19", "bonus = str+2, con+1",
    )
    [expected] = messages_of(defect, registry, task)
    assert expected == over_twenty_message("str")
    assert expected in texts(step)
    # исправление: схема +1, +1, +1 -- 19 доходит до 20
    step = wizard.submit("2")
    for line in lines_after(SCRIPT, "bonus"):
        step = wizard.submit(line)
    sheet = accept(wizard, registry, task)
    assert sheet.choices.ability_method == "explicit"
    assert sheet.choices.background_bonus == {"str": 1, "dex": 1, "con": 1}
    hero = play_and_reload(registry, cfg, tmp_path, sheet)
    assert hero.sheet.abilities["str"] == 20


# все три метода дают принимаемый лист без модели

def test_three_methods_make_no_model_calls(registry, cfg, tmp_path):
    for method in (1, 2, 3):
        wizard, task = make(registry, cfg)
        first_option_walk(wizard, method=method)
        sheet = accept(wizard, registry, task)
        assert sheet.choices.ability_method == (
            "standard_array", "point_buy", "explicit"
        )[method - 1]
        assert wizard.run_ids == []


# заклинатели

def class_number(registry, class_id):
    from ai_dm.rules.hero_options import class_options

    return [c.id for c in class_options(registry)].index(class_id) + 1


def caster_hero(registry, cfg, tmp_path, class_id):
    wizard, task = make(registry, cfg)
    first_option_walk(wizard, cls=class_number(registry, class_id), background=3)
    sheet = accept(wizard, registry, task)
    return sheet, play_and_reload(registry, cfg, tmp_path, sheet)


def test_wizard_hero_has_spells_and_prepared_within_limits(registry, cfg, tmp_path):
    sheet, hero = caster_hero(registry, cfg, tmp_path, "wizard")
    limits = registry.get("class", "wizard").spellcasting
    assert hero.sheet.class_id == "wizard"
    assert hero.sheet.known_of() == sheet.choices.spells
    assert hero.sheet.prepared_of() == sheet.choices.prepared
    assert len(hero.sheet.prepared_of()) == limits.prepared
    assert set(hero.sheet.prepared_of()) <= set(hero.sheet.known_of())
    assert len([s for s in hero.sheet.known_of() if registry.get("spell", s).level == 0]) <= (
        limits.cantrips
    )
    assert len([s for s in hero.sheet.known_of() if registry.get("spell", s).level == 1]) <= (
        limits.spells
    )
    assert hero.creature.resources["spell_slot:1"].max == 2
    assert hero.creature.resources["spell_slot:1"].current == 2


def test_cleric_hero_has_spells_and_prepared_within_limits(registry, cfg, tmp_path):
    sheet, hero = caster_hero(registry, cfg, tmp_path, "cleric")
    limits = registry.get("class", "cleric").spellcasting
    assert hero.sheet.class_id == "cleric"
    assert hero.sheet.known_of() == sheet.choices.spells
    assert 0 < len(hero.sheet.prepared_of()) <= limits.prepared
    assert set(hero.sheet.prepared_of()) <= set(hero.sheet.known_of())
    assert hero.creature.resources["spell_slot:1"].max == 2


# replay пошагового героя в простом режиме (через main)

def test_stepwise_hero_world_replays_without_divergence(tmp_path):
    from hero_kit import wizard_picks

    root = tmp_path / "saves"
    script = write_script(tmp_path / "turn.yaml", TURN_TEXT)
    argv = ["--new", "--world", "w1", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(root)]
    lines = [steps_item_number(), "1", *wizard_picks(), "1", "Осматриваюсь", "/quit"]
    code, out = cli(argv, lines, env={})
    assert code == 0
    assert TURN_TEXT in out.text
    assert read_hero_sheet(root, "w1") == wizard_sheet()
    replay = ["--replay", "--world", "w1", "--seed", str(SEED), "--saves", str(root)]
    code, out = cli(replay, ["Осматриваюсь", "/quit"], env={})
    assert code == 0
    assert "Расхождение" not in out.text
    assert TURN_TEXT in out.text


# TUI (HeroCreateApp, Pilot) и простой режим дают одного и того же героя от одних ответов

def hero_dump(bundle):
    import json

    return json.dumps(
        [json.loads(h.model_dump_json()) for h in bundle.heroes], sort_keys=True,
        ensure_ascii=False,
    )


def simple_stepwise_hero(tmp_path):
    root = tmp_path / "simple"
    script = write_script(tmp_path / "turn.yaml", TURN_TEXT)
    argv = ["--new", "--world", "w1", "--seed", "7", "--mock", str(script), "--saves", str(root)]
    from hero_kit import wizard_picks

    code, _ = cli(argv, [steps_item_number(), "1", *wizard_picks(), "1", "/quit"], env={})
    assert code == 0
    return load_slot(root, "w1", "auto")


def tui_stepwise_sheet(registry, cfg, tmp_path):
    import asyncio

    from hero_kit import wizard_picks

    from ai_dm.ui.tui import strings
    from ai_dm.ui.tui.create import HeroCreateApp

    wizard = HeroWizard(deps(None, registry, cfg), sheet_task(vale_pack(registry)), 80)
    app = HeroCreateApp(wizard, placeholder=strings.STEPS_PLACEHOLDER)

    async def scenario():
        async with app.run_test(size=(140, 40)) as pilot:
            await pilot.pause()
            for line in (*wizard_picks(), "1"):
                app.query_one("#input").value = line
                await pilot.press("enter")
                await app.workers.wait_for_complete()
                await pilot.pause()

    asyncio.run(scenario())
    return app.return_value


def test_tui_and_simple_stepwise_give_the_same_hero(registry, cfg, tmp_path):
    simple = simple_stepwise_hero(tmp_path)
    sheet = tui_stepwise_sheet(registry, cfg, tmp_path)
    assert isinstance(sheet, HeroSheet)
    assert sheet == read_hero_sheet(tmp_path / "simple", "w1")
    bundle = new_world_from_pack(
        registry, cfg, vale_pack(registry), hero=sheet, seed=7, world_id="w1", saved_at=SAVED_AT
    )
    assert hero_dump(bundle) == hero_dump(simple)
