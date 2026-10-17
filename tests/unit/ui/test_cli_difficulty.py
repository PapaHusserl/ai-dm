# Партия К7к, п. 3.4: сложность боёв нового мира в CLI (docs/plan-k7k.md, В3а), по образцу
# test_cli_preset.py. Флаг --difficulty {easy,normal,hard} только с --new (иначе код 2);
# значение пишется в world.settings["difficulty"], в заметках старта «сложность <слово>»;
# интерактивный старт (герой выбран в меню): после героя и пресета меню «Сложность боёв:» --
# «Как в конфиге (умеренный)», «Лёгкая», «Обычная», «Тяжёлая»; первый пункт и конец ввода -- без
# настройки (ключа в settings нет); --hero и --hero-describe меню не показывают;
# --replay берёт тот же --difficulty, что исходный прогон (подсказка в сообщении).
import pytest
from ui_kit import SEED, cli, write_script

from ai_dm.persistence.store import load_slot

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]
TITLE = "Сложность боёв"


def argv(tmp_path, *extra):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    return [*extra, "--mock", str(script), "--saves", str(tmp_path / "saves")]


def start(tmp_path, *extra, world="w1"):
    return cli(argv(tmp_path, *BASE, "--world", world, *extra), ["/quit"], env={})


def interactive(tmp_path, lines, extra=()):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    args = ["--new", "--world", "w1", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(tmp_path / "saves"), *extra]
    return cli(args, lines, env={})


def saved_settings(tmp_path):
    return load_slot(tmp_path / "saves", "w1", "auto").world.settings


# флаг

@pytest.mark.parametrize("value", ["easy", "normal", "hard"])
def test_new_with_difficulty_writes_the_setting(tmp_path, value):
    code, _ = start(tmp_path, "--difficulty", value)
    assert code == 0
    assert saved_settings(tmp_path)["difficulty"] == value


@pytest.mark.parametrize(
    "value, word", [("easy", "лёгкая"), ("normal", "обычная"), ("hard", "тяжёлая")]
)
def test_difficulty_note_is_in_world_line(tmp_path, value, word):
    _, out = start(tmp_path, "--difficulty", value)
    line = next(line for line in out.lines if line.startswith("Мир: "))
    assert "w1" in line
    assert f"сид {SEED}" in line
    assert f"сложность {word}" in line


def test_no_flag_has_no_setting_and_no_note(tmp_path):
    _, out = start(tmp_path)
    assert "difficulty" not in saved_settings(tmp_path)
    assert "сложность" not in out.text


def test_flag_skips_the_difficulty_question(tmp_path):
    code, out = interactive(tmp_path, ["1", "1", "/quit"], extra=["--difficulty", "hard"])
    assert code == 0
    assert TITLE not in out.text
    assert saved_settings(tmp_path)["difficulty"] == "hard"


def test_difficulty_without_new_is_code_2(tmp_path):
    code, out = cli(argv(tmp_path, "--world", "some", "--difficulty", "easy"), env={})
    assert code == 2
    assert "--difficulty" in out.text
    assert not (tmp_path / "saves").exists() or not list((tmp_path / "saves").iterdir())


def test_unknown_difficulty_is_rejected(tmp_path):
    code, _ = start(tmp_path, "--difficulty", "epic")
    assert code not in (0, None)
    assert not (tmp_path / "saves").exists() or not list((tmp_path / "saves").iterdir())


def test_difficulty_with_preset_keeps_both(tmp_path):
    _, out = start(tmp_path, "--difficulty", "easy", "--preset", "grim")
    line = next(line for line in out.lines if line.startswith("Мир: "))
    assert "пресет grim" in line
    assert "сложность лёгкая" in line
    assert saved_settings(tmp_path)["difficulty"] == "easy"


# меню

def test_menu_is_asked_after_hero_and_preset(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "1", "/quit"])
    text = out.text
    assert text.index("Выберите героя") < text.index("Пресет мира") < text.index(TITLE)


def test_menu_items(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "1", "/quit"])
    text = " ".join(out.text.split())
    for item in ("1. Как в конфиге (умеренный)", "2. Лёгкая", "3. Обычная", "4. Тяжёлая"):
        assert item in text


def test_menu_first_item_leaves_no_setting(tmp_path):
    code, out = interactive(tmp_path, ["1", "1", "1", "/quit"])
    assert code == 0
    assert "difficulty" not in saved_settings(tmp_path)
    assert "сложность" not in out.text.replace("Сложность боёв", "")


@pytest.mark.parametrize(
    "answer, value", [("2", "easy"), ("3", "normal"), ("4", "hard")]
)
def test_menu_item_sets_the_difficulty(tmp_path, answer, value):
    code, out = interactive(tmp_path, ["1", "1", answer, "/quit"])
    assert code == 0
    assert saved_settings(tmp_path)["difficulty"] == value


def test_menu_item_note_in_world_line(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "2", "/quit"])
    line = next(line for line in out.lines if line.startswith("Мир: "))
    assert "сложность лёгкая" in line


def test_end_of_input_on_the_menu_means_as_in_config(tmp_path):
    code, _ = interactive(tmp_path, ["1", "1"])
    assert code == 0
    assert "difficulty" not in saved_settings(tmp_path)


def test_wrong_answer_asks_again(tmp_path):
    code, _ = interactive(tmp_path, ["1", "1", "9", "ерунда", "4", "/quit"])
    assert code == 0
    assert saved_settings(tmp_path)["difficulty"] == "hard"


def test_hero_flag_skips_the_menu(tmp_path):
    _, out = start(tmp_path)
    assert TITLE not in out.text


def test_hero_describe_skips_the_menu(tmp_path):
    from pathlib import Path

    sheet = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "hero_sheet.yaml"
    args = ["--new", "--seed", str(SEED), "--hero-describe", "воин", "--mock", str(sheet),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(args, ["/quit"], env={})
    assert code == 0
    assert TITLE not in out.text


def test_preset_flag_still_asks_the_difficulty(tmp_path):
    code, out = interactive(tmp_path, ["1", "3", "/quit"], extra=["--preset", "grim"])
    assert code == 0
    assert TITLE in out.text
    assert saved_settings(tmp_path)["difficulty"] == "normal"


def test_tui_menu_gets_the_four_names(monkeypatch):
    from pathlib import Path

    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import Setup, choose_difficulty
    from ai_dm.ui.io import CaptureOutput

    seen = []

    def fake_pick(title, names, splash=False):
        seen.append((title, names))
        return 4

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    assert choose_difficulty(None, CaptureOutput(), CaptureOutput(), setup) == "hard"
    assert seen[0][1] == ["Как в конфиге (умеренный)", "Лёгкая", "Обычная", "Тяжёлая"]


def test_choose_difficulty_simple_returns_each_value():
    from pathlib import Path

    from slots_kit import ScriptedInput

    from ai_dm.ui.cli import Setup, choose_difficulty
    from ai_dm.ui.io import CaptureOutput

    setup = Setup({}, Path("no.env"), None, [], Path("."), "simple")
    results = [
        choose_difficulty(ScriptedInput([n]), CaptureOutput(), CaptureOutput(), setup)
        for n in ("1", "2", "3", "4")
    ]
    assert results == [None, "easy", "normal", "hard"]


# replay

def played(tmp_path, *extra):
    code, _ = cli(argv(tmp_path, *BASE, "--world", "w1", *extra), ["осматриваюсь", "/quit"], env={})
    assert code == 0


def replay_args(tmp_path, *extra):
    return ["--replay", "--world", "w1", "--hero", "arn", "--seed", str(SEED), *extra,
            "--saves", str(tmp_path / "saves")]


def test_replay_hint_mentions_difficulty(tmp_path):
    code, out = cli(
        ["--replay", "--world", "w1", "--hero", "arn", "--saves", str(tmp_path)], env={}
    )
    assert code == 2
    assert "--difficulty" in out.text


def test_replay_with_same_difficulty_goes_through(tmp_path):
    played(tmp_path, "--difficulty", "hard")
    code, _ = cli(replay_args(tmp_path, "--difficulty", "hard"), ["осматриваюсь", "/quit"], env={})
    assert code == 0


def test_replay_without_the_difficulty_of_the_original_run_diverges(tmp_path):
    played(tmp_path, "--difficulty", "hard")
    code, _ = cli(replay_args(tmp_path), ["осматриваюсь", "/quit"], env={})
    assert code == 1


def test_tui_pick_gets_the_title_and_no_splash(monkeypatch):
    from pathlib import Path

    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import Setup, choose_difficulty
    from ai_dm.ui.io import CaptureOutput

    seen = []

    def fake_pick(title, names, splash=False):
        seen.append((title, splash))
        return 1

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    choose_difficulty(None, CaptureOutput(), CaptureOutput(), setup)
    assert seen == [("Сложность боёв:", False)]


def test_tui_failure_notes_it_and_falls_back_to_simple(monkeypatch):
    from pathlib import Path

    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import Setup, choose_difficulty
    from ai_dm.ui.io import CaptureOutput

    def broken(title, names, splash=False):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "pick", broken)
    notes = CaptureOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    result = choose_difficulty(ScriptedInput(["2"]), CaptureOutput(), notes, setup)
    assert result == "easy"
    assert "Выбор сложности в TUI не запустился: нет экрана" in " ".join(notes.lines)
