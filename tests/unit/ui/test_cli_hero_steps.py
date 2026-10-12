# Б2а (B2-PLAN, A7, «Тесты Б2а»): третий пункт choose_hero «Создать пошагово», make_hero_session,
# интерактив простого режима с пошаговым героем. Ожидаемый API (ТРЕБОВАНИЕ к коду Б2а):
# ai_dm.ui.cli.CREATE_HERO_STEPS, STEP_HERO (сентинел, рядом с NEW_HERO),
# make_hero_session(kind, deps, task, width) -> HeroWizard (STEP_HERO) | HeroSession (иначе).
# Мок-скрипт без hero_sheet: пошаговый путь модель не зовёт (кроме «описать словами»).
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import (  # noqa: E402
    deps,
    sheet_task,
    vale_pack,
    wizard_picks,
    wizard_script,
    wizard_sheet,
)
from slots_kit import ScriptedInput, list_slots  # noqa: E402
from ui_kit import SEED, PlainOutput, cli, numbered_lines, write_script  # noqa: E402

from ai_dm.game.hero_create import read_hero_sheet  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402

DESCRIPTION = "акробат из бродячего цирка"


def vale_setup():
    from ai_dm.ui.cli import Setup

    return Setup({}, Path("no.env"), None, [], Path("."), "simple")


def choose(lines):
    from ai_dm.ui.cli import choose_hero

    pack = vale_pack_for_cli()
    out = PlainOutput()
    result = choose_hero(ScriptedInput(lines), out, out, pack, vale_setup())
    return result, out


def vale_pack_for_cli():
    from ai_dm.content.loader import load_registry

    return vale_pack(load_registry())


def steps_item_number():
    # номер пункта «Создать пошагово» зависит от числа пресетов героя пака
    from ai_dm.ui.cli import hero_presets

    return str(len(hero_presets(vale_pack_for_cli())) + 2)


STEPS_NO = steps_item_number()


# choose_hero

def test_choose_hero_menu_has_five_items_with_steps_last():
    from ai_dm.ui.cli import CREATE_HERO_STEPS

    _, out = choose([])
    items = numbered_lines(out.lines)
    assert len(items) == 5
    assert items[-1] == (5, CREATE_HERO_STEPS)


def test_create_hero_steps_label_is_russian_and_distinct():
    from ai_dm.ui.cli import CREATE_HERO_STEPS
    from ai_dm.ui.hero_session import CREATE_HERO

    assert CREATE_HERO_STEPS == "Создать пошагово"
    assert CREATE_HERO_STEPS != CREATE_HERO


def test_choose_hero_fourth_item_is_still_the_on_the_fly_hero():
    from ai_dm.ui.cli import NEW_HERO

    result, out = choose(["4"])
    assert result is NEW_HERO
    assert numbered_lines(out.lines)[3][1] == "Создать героя на лету"


def test_choose_hero_fifth_item_is_the_stepwise_sentinel():
    from ai_dm.ui.cli import NEW_HERO, STEP_HERO

    result, _ = choose([STEPS_NO])
    assert result is STEP_HERO
    assert result is not NEW_HERO


def test_choose_hero_presets_still_return_ids():
    result, _ = choose(["2"])
    assert result == "liel"


def test_choose_hero_six_is_refused_and_asks_again():
    from ai_dm.ui.cli import STEP_HERO

    result, out = choose([str(int(STEPS_NO) + 1), STEPS_NO])
    assert result is STEP_HERO
    assert "Введите число от 1 до 5." in out.text


def test_choose_hero_cancel_is_none():
    result, _ = choose([])
    assert result is None


def test_pack_without_presets_still_goes_straight_to_creation():
    from types import SimpleNamespace

    from ai_dm.ui.cli import NEW_HERO, choose_hero

    pack = SimpleNamespace(heroes=[], manifest=SimpleNamespace(start=SimpleNamespace(heroes=[])))
    out = PlainOutput()
    assert choose_hero(ScriptedInput([]), out, out, pack, vale_setup()) is NEW_HERO


# make_hero_session

def make_session(kind, registry, cfg):
    from ai_dm.ui.cli import make_hero_session

    return make_hero_session(kind, deps(None, registry, cfg), sheet_task(vale_pack(registry)), 80)


def test_make_hero_session_for_step_hero_is_the_wizard(registry, cfg):
    from ai_dm.ui.cli import STEP_HERO
    from ai_dm.ui.hero_wizard import HeroWizard

    assert isinstance(make_session(STEP_HERO, registry, cfg), HeroWizard)


def test_make_hero_session_for_new_hero_is_the_describe_session(registry, cfg):
    from ai_dm.ui.cli import NEW_HERO
    from ai_dm.ui.hero_session import HeroSession
    from ai_dm.ui.hero_wizard import HeroWizard

    session = make_session(NEW_HERO, registry, cfg)
    assert isinstance(session, HeroSession)
    assert not isinstance(session, HeroWizard)


def test_make_hero_session_passes_width_and_deps(registry, cfg):
    from ai_dm.ui.cli import NEW_HERO, STEP_HERO

    for kind in (NEW_HERO, STEP_HERO):
        session = make_session(kind, registry, cfg)
        assert session.width == 80
        assert session.deps.registry is registry


# интерактив простого режима

def script_file(tmp_path, steps=None):
    if steps is None:
        return write_script(tmp_path / "turn.yaml", "Огонь в очаге трещит.")
    path = tmp_path / "script.yaml"
    path.write_text(yaml.safe_dump({"steps": steps}, allow_unicode=True), encoding="utf-8")
    return path


def argv(root, script):
    return ["--new", "--world", "w1", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(root)]


def stepwise(tmp_path, lines, steps=None):
    root = tmp_path / "saves"
    code, out = cli(argv(root, script_file(tmp_path, steps)), lines, env={})
    return code, out, root


def test_stepwise_hero_starts_the_world_with_code_0(tmp_path):
    code, _, _ = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "/quit"])
    assert code == 0


def test_stepwise_hero_is_saved_in_auto_slot_with_the_sheet_hero(tmp_path):
    _, _, root = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "/quit"])
    assert "auto" in list_slots(root, "w1")
    hero = load_slot(root, "w1", "auto").heroes[0]
    assert hero.name == "Борин"
    assert hero.sheet.class_id == "fighter"
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert hero.opportunity == []


def test_stepwise_hero_sheet_is_written_to_meta_and_equals_the_canon(tmp_path):
    _, _, root = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "/quit"])
    assert (root / "w1" / "meta" / "hero_sheet.json").is_file()
    assert read_hero_sheet(root, "w1") == wizard_sheet()


def test_stepwise_hero_is_noted_as_stepwise(tmp_path):
    _, out, _ = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "/quit"])
    assert "Герой пошагово: Борин" in out.text
    assert "Герой на лету" not in out.text


def test_stepwise_without_ai_has_no_creation_cost_line(tmp_path):
    _, out, _ = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "/quit"])
    assert "Создание героя:" not in out.text


def test_stepwise_shows_hint_and_first_menu(tmp_path):
    from ai_dm.ui.hero_wizard import WIZARD_HINT

    _, out, _ = stepwise(tmp_path, [STEPS_NO, "1", "отмена"])
    assert WIZARD_HINT in out.text
    assert "Человек" in out.text


def test_stepwise_taken_name_in_other_case_is_refused(tmp_path):
    lines = [STEPS_NO, "1", *wizard_picks(name="гракх"), "отмена"]
    code, out, _ = stepwise(tmp_path, lines)
    assert "уже занято" in out.text
    assert code == 1


def test_stepwise_cancel_is_hero_not_chosen_code_1_and_no_world(tmp_path):
    code, out, root = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks()[:5], "отмена"])
    assert code == 1
    assert "Герой не выбран" in out.text
    assert not (root / "w1").exists()


def test_stepwise_end_of_input_cancels_like_cancel(tmp_path):
    code, out, root = stepwise(tmp_path, [STEPS_NO, "1", *wizard_picks()[:3]])
    assert code == 1
    assert "Герой не выбран" in out.text
    assert not (root / "w1").exists()


def test_stepwise_error_then_fix_still_gives_a_hero(tmp_path):
    script = wizard_script()
    lines = [line for key, line in script if key != "name"]
    name_at = len(lines) - 4
    lines[name_at:name_at] = ["гракх", "Борин"]
    code, out, root = stepwise(tmp_path, [STEPS_NO, "1", *lines, "1", "/quit"])
    assert code == 0
    assert "уже занято" in out.text
    assert read_hero_sheet(root, "w1").choices.name == "Борин"


def test_stepwise_world_runs_a_turn_after_creation(tmp_path):
    code, out, _ = stepwise(
        tmp_path, [STEPS_NO, "1", *wizard_picks(), "1", "Осматриваюсь", "/quit"]
    )
    assert code == 0
    assert "Огонь в очаге трещит." in out.text


def test_stepwise_replay_without_hero_has_no_divergence(tmp_path):
    root = tmp_path / "saves"
    lines = [STEPS_NO, "1", *wizard_picks(), "1", "Осматриваюсь", "/quit"]
    code, _ = cli(argv(root, script_file(tmp_path)), lines, env={})
    assert code == 0
    replay = ["--replay", "--world", "w1", "--seed", str(SEED), "--saves", str(root)]
    code, out = cli(replay, ["Осматриваюсь", "/quit"], env={})
    assert code == 0
    assert "Расхождение" not in out.text


def test_existing_describe_menu_item_four_still_describes(tmp_path):
    from hero_kit import sheet_call

    steps = [{"tool_calls": [sheet_call()]}, {"text": "Огонь в очаге трещит."}]
    root = tmp_path / "saves"
    code, out = cli(
        argv(root, script_file(tmp_path, steps)), ["4", "1", "воин-сирота", "1", "/quit"], env={}
    )
    assert code == 0
    assert "Создание героя: $" in out.text


# «описать словами»: единственный ИИ-шаг, цена печатается

def words_lines():
    script = wizard_script()
    scores = [line for key, line in script if key == "scores"]
    keys = ("name", "gender", "pronouns", "motive", "means")
    tail = [line for key, line in script if key in keys]
    # эльф-воин: у эльфа нет выборов вида; предыстория из ИИ: dex, con, cha
    return [
        "2", "2", "5", DESCRIPTION, "1", *scores, "1", "1", "1", "1", "1", "1", "1", "1", "1",
        "1", "1", "1", *tail,
    ]


def spec_step():
    call = {
        "id": "bg-1", "name": "background_spec",
        "input": {
            "type": "background_spec", "name": "Бывший цирковой акробат",
            "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
            "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"],
            "gold_cp": 1000, "description": "Вырос в цирке.",
        },
    }
    return {"tool_calls": [call]}


def test_words_path_makes_a_hero_and_prints_the_creation_cost(tmp_path):
    steps = [spec_step(), {"text": "Огонь в очаге трещит."}]
    code, out, root = stepwise(tmp_path, [STEPS_NO, "1", *words_lines(), "1", "/quit"], steps)
    assert code == 0
    assert "Создание героя: $" in out.text
    assert "(1 вызовов)" in out.text
    sheet = read_hero_sheet(root, "w1")
    assert sheet.choices.background.name == "Бывший цирковой акробат"
    assert sheet.choices.species_id == "elf"


def test_words_path_records_hero_run_in_the_journal(tmp_path):
    steps = [spec_step(), {"text": "Огонь в очаге трещит."}]
    _, _, root = stepwise(tmp_path, [STEPS_NO, "1", *words_lines(), "1", "/quit"], steps)
    journal = (root / "w1" / "journal").rglob("*")
    text = "\n".join(p.read_text(encoding="utf-8") for p in journal if p.is_file())
    assert '"run_id": "hero-' in text


def test_review_hint_is_true_only_while_means_is_the_last_step():
    from ai_dm.game.hero_steps import STEPS
    from ai_dm.ui.hero_wizard import REVIEW_HINT

    assert "средства" in REVIEW_HINT
    assert STEPS[-1].key == "means"
