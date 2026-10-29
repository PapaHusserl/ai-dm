# Этап 5, P1: выбор режима (простой / TUI) и fallback. Ожидаемый API (по коду P1):
#   cli.main(..., stdin=, stdout=) -- подменённый ввод/вывод всегда даёт простой режим;
#   --simple; не-tty и TERM=dumb -- простой;
#   ai_dm.ui.tui.run_tui(game, notes, replay, opening, key_factory) -> int;
#   ai_dm.ui.tui.TuiStartError -- ошибка до первого кадра;
#   ai_dm.ui.tui.AiDmApp(game, session, notes).
# Режим TUI в тестах не запускается по-настоящему: run_tui подменяется записывающей функцией.
# Pilot -- через asyncio.run (без плагина), фиксированный размер, без сна.
import asyncio
import io
import shutil
import sys

import pytest
from slots_kit import ScriptedInput
from test_cli_migration import FIXTURE_V5
from ui_kit import SEED, cli, text_app, text_step, write_script

import ai_dm.ui
import ai_dm.ui.cli as cli_module
from ai_dm.ui.cli import Setup, choose_mode, main, make_parser, play, say
from ai_dm.ui.io import CaptureOutput
from ai_dm.ui.session import PlaySession

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]


class Tty(io.StringIO):
    def isatty(self):
        return True


class TtyStdin:
    def isatty(self):
        return True

    def readline(self):
        return ""


def mock_args(tmp_path, text="Трактирщик кивает."):
    script = write_script(tmp_path / "one.yaml", text)
    return ["--mock", str(script), "--saves", str(tmp_path / "saves")]


def fake_terminal(monkeypatch):
    out = Tty()
    monkeypatch.setattr(sys, "stdin", TtyStdin())
    monkeypatch.setattr(sys, "stdout", out)
    return out


def real_main(argv, env):
    # main без подмены stdin/stdout -- как из терминала
    return main(argv, env=env, dotenv_path=None)


def ran_tui(monkeypatch):
    # подмена run_tui: записывает вызовы, возвращает 0
    import ai_dm.ui.tui as tui

    calls = []

    def fake(game, notes=(), replay=False, opening=None, key_factory=None):
        calls.append({"notes": list(notes), "replay": replay, "opening": opening})
        return 0

    monkeypatch.setattr(tui, "run_tui", fake)
    return calls


# choose_mode

def args_of(*argv):
    return make_parser().parse_args(list(argv))


def test_choose_mode_tui_in_real_terminal():
    assert choose_mode(args_of(), False, {"TERM": "xterm"}, True, True) == "tui"


def test_choose_mode_simple_flag():
    assert choose_mode(args_of("--simple"), False, {"TERM": "xterm"}, True, True) == "simple"


def test_choose_mode_injected_io_is_simple():
    assert choose_mode(args_of(), True, {"TERM": "xterm"}, True, True) == "simple"


def test_choose_mode_stdin_not_tty_is_simple():
    assert choose_mode(args_of(), False, {"TERM": "xterm"}, False, True) == "simple"


def test_choose_mode_stdout_not_tty_is_simple():
    assert choose_mode(args_of(), False, {"TERM": "xterm"}, True, False) == "simple"


def test_choose_mode_term_dumb_is_simple():
    assert choose_mode(args_of(), False, {"TERM": "dumb"}, True, True) == "simple"


def test_choose_mode_without_term_is_not_dumb():
    assert choose_mode(args_of(), False, {}, True, True) == "tui"


def test_simple_flag_is_parsed():
    assert args_of("--simple").simple is True
    assert args_of().simple is False


# main -> режим

def test_scripted_stdin_gives_simple_mode_even_in_terminal(tmp_path, monkeypatch):
    fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    code, out = cli(BASE + mock_args(tmp_path), lines=["/quit"], env={})
    assert code == 0
    assert calls == []
    assert "HP" in out.text


def test_simple_flag_gives_simple_mode_in_terminal(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    code = real_main(BASE + mock_args(tmp_path) + ["--simple"], {"TERM": "xterm"})
    assert code == 0
    assert calls == []
    assert "HP" in out.getvalue()


def test_not_tty_gives_simple_mode(tmp_path, monkeypatch):
    # под pytest stdin/stdout не tty
    calls = ran_tui(monkeypatch)
    monkeypatch.setattr(sys, "stdin", io.StringIO(""))
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert code == 0
    assert calls == []


def test_term_dumb_gives_simple_mode(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "dumb"})
    assert code == 0
    assert calls == []
    assert "HP" in out.getvalue()


def test_terminal_starts_tui_with_start_notes(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert code == 0
    assert len(calls) == 1
    assert any("Мир:" in note for note in calls[0]["notes"])
    assert "Мир:" not in out.getvalue()


def test_tui_exit_code_is_returned(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    fake_terminal(monkeypatch)
    monkeypatch.setattr(tui, "run_tui", lambda *a, **k: 7)
    assert real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"}) == 7


# fallback

def assert_fallback(out, code):
    text = out.getvalue()
    assert code == 0
    assert "Traceback" not in text
    assert text.count("TUI не запустился") == 1
    assert "HP" in text  # дальше пошёл простой режим


def test_tui_import_failure_falls_back_to_simple(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    monkeypatch.setitem(sys.modules, "ai_dm.ui.tui", None)
    monkeypatch.delattr(ai_dm.ui, "tui", raising=False)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert_fallback(out, code)


def test_tui_import_failure_keeps_start_notes(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    monkeypatch.setitem(sys.modules, "ai_dm.ui.tui", None)
    monkeypatch.delattr(ai_dm.ui, "tui", raising=False)
    real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert "Мир:" in out.getvalue()


def test_tui_start_error_falls_back_to_simple(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    out = fake_terminal(monkeypatch)

    def broken(*args, **kwargs):
        raise tui.TuiStartError("нет терминала")

    monkeypatch.setattr(tui, "run_tui", broken)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert_fallback(out, code)
    assert "нет терминала" in out.getvalue()


def test_app_run_failure_before_first_frame_falls_back(tmp_path, monkeypatch):
    # исключение в App.run до первого кадра (on_mount не вызван) -> TuiStartError -> простой режим
    import ai_dm.ui.tui as tui

    out = fake_terminal(monkeypatch)

    def broken(self, *args, **kwargs):
        raise RuntimeError("терминал не отвечает")

    monkeypatch.setattr(tui.AiDmApp, "run", broken)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert_fallback(out, code)


def test_fallback_message_hides_keys(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    out = fake_terminal(monkeypatch)
    monkeypatch.setattr(tui.AiDmApp, "run", lambda self: (_ for _ in ()).throw(
        RuntimeError("sk-secret-key-123")))
    real_main(BASE + mock_args(tmp_path), {"TERM": "xterm", "GEMINI_API_KEY": "sk-secret-key-123"})
    assert "sk-secret-key-123" not in out.getvalue()


# Pilot: заглушка на моке

def feed_text(app):
    feed = app.query_one("#feed")
    return "\n".join(strip.text for strip in feed.lines)


def test_pilot_stub_starts_on_mock(registry, tmp_path):
    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            return app.query_one("#hero").text, app.query_one("#input").has_focus

    text, focused = asyncio.run(scenario())
    assert "HP" in text
    assert focused


def test_pilot_help_writes_lines_to_feed(registry, tmp_path):
    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            before = len(app.query_one("#feed").lines)
            await pilot.press(*"/help", "enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            return before, feed_text(app), len(app.query_one("#feed").lines)

    before, text, after = asyncio.run(scenario())
    assert after > before
    assert "/quit" in text
    assert "/help" in text


def test_pilot_input_is_enabled_after_turn(registry, tmp_path):
    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press(*"/help", "enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            entry = app.query_one("#input")
            return entry.disabled, entry.value

    disabled, value = asyncio.run(scenario())
    assert disabled is False
    assert value == ""


def test_pilot_start_notes_are_in_feed(registry, tmp_path):
    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game), ["Мир: тестовый"])

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            return feed_text(app)

    assert "Мир: тестовый" in asyncio.run(scenario())


def test_pilot_quit_ends_app(registry, tmp_path):
    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press(*"/quit", "enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
        return app.return_code

    assert asyncio.run(scenario()) == 0


def test_pilot_exit_not_by_quit_saves_auto(registry, tmp_path):
    from slots_kit import list_slots

    from ai_dm.ui.tui import AiDmApp

    game = text_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def scenario():
        async with app.run_test(size=(100, 30)) as pilot:
            await pilot.pause()
            await pilot.press("ctrl+q")
            await pilot.pause()
        return app.after_exit()

    assert asyncio.run(scenario()) == 0
    assert "auto" in list_slots(game.saves_root, game.world_id)


def test_import_error_from_running_tui_does_not_restart_game(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    out = fake_terminal(monkeypatch)

    def broken(*args, **kwargs):
        raise ImportError("позднее")

    monkeypatch.setattr(tui, "run_tui", broken)
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert code == 1
    assert "TUI не запустился" not in out.getvalue()
    assert "HP" not in out.getvalue()


# Д1, A1: Ctrl+C и ошибка при подготовке мира -- строки старта не теряются

START_LINE = "строка старта"


def failing_narrator(error):
    def pick(args, settings, setup, saves_root, notes):
        say(notes, START_LINE)
        raise error

    return pick


def test_ctrl_c_in_prepare_keeps_start_notes_in_tui(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    monkeypatch.setattr(cli_module, "pick_narrator", failing_narrator(KeyboardInterrupt()))
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    text = out.getvalue()
    assert code == 130
    assert START_LINE in text
    assert "Прервано." in text
    assert text.index(START_LINE) < text.index("Прервано.")
    assert "Traceback" not in text


def test_ctrl_c_in_prepare_of_old_world_keeps_migration_warning_in_tui(tmp_path, monkeypatch):
    root = tmp_path / "saves"
    shutil.copytree(FIXTURE_V5, root / "old_world" / "slots" / "auto")
    out = fake_terminal(monkeypatch)

    def interrupted(*args, **kwargs):
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "make_game_adapter", interrupted)
    argv = ["--world", "old_world", "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(root)]
    code = real_main(argv, {"TERM": "xterm"})
    text = out.getvalue()
    assert code == 130
    assert "ghost_relic" in text
    assert text.index("ghost_relic") < text.index("Прервано.")
    assert "Traceback" not in text


def test_ctrl_c_in_prepare_prints_start_notes_once_in_simple_mode(tmp_path, monkeypatch):
    monkeypatch.setattr(cli_module, "pick_narrator", failing_narrator(KeyboardInterrupt()))
    code, out = cli(BASE + mock_args(tmp_path), env={})
    assert code == 130
    assert out.lines.count(START_LINE) == 1
    assert out.lines.count("Прервано.") == 1


def test_error_in_prepare_keeps_start_notes_in_tui(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    monkeypatch.setattr(cli_module, "pick_narrator", failing_narrator(RuntimeError("сломалось")))
    code = real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    text = out.getvalue()
    assert code == 1
    assert text.index(START_LINE) < text.index("Ошибка: сломалось")


def test_start_notes_are_not_printed_twice_on_tui_fallback(tmp_path, monkeypatch):
    out = fake_terminal(monkeypatch)
    monkeypatch.setitem(sys.modules, "ai_dm.ui.tui", None)
    monkeypatch.delattr(ai_dm.ui, "tui", raising=False)
    real_main(BASE + mock_args(tmp_path), {"TERM": "xterm"})
    assert out.getvalue().count("Мир:") == 1


def test_play_in_tui_mode_flushes_notes_and_reraises_ctrl_c(tmp_path, monkeypatch):
    def prepare(args, stdin, stdout, notes, setup):
        say(notes, START_LINE)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "prepare", prepare)
    args = make_parser().parse_args(BASE + mock_args(tmp_path))
    out = CaptureOutput()
    setup = Setup({}, tmp_path / ".env", None, [], tmp_path / "campaigns", "tui")
    with pytest.raises(KeyboardInterrupt):
        play(args, ScriptedInput([]), out, setup)
    assert any(START_LINE in line for line in out.lines)


def test_play_in_simple_mode_does_not_duplicate_notes_on_ctrl_c(tmp_path, monkeypatch):
    def prepare(args, stdin, stdout, notes, setup):
        say(notes, START_LINE)
        raise KeyboardInterrupt

    monkeypatch.setattr(cli_module, "prepare", prepare)
    args = make_parser().parse_args(BASE + mock_args(tmp_path))
    out = CaptureOutput()
    setup = Setup({}, tmp_path / ".env", None, [], tmp_path / "campaigns", "simple")
    with pytest.raises(KeyboardInterrupt):
        play(args, ScriptedInput([]), out, setup)
    assert sum(START_LINE in line for line in out.lines) == 1


# play: opening из prepare доходит до TUI и до простого режима при фолбэке

def play_with_opening(tmp_path, monkeypatch, tui_result):
    calls = {}

    def prepare(args, stdin, stdout, notes, setup):
        return "app", "Начало."

    def run_tui(args, app, opening, notes, setup):
        calls["tui_opening"] = opening
        return tui_result

    def simple_run(app, stdin, stdout, **kwargs):
        calls["simple"] = kwargs
        return 5

    monkeypatch.setattr(cli_module, "prepare", prepare)
    monkeypatch.setattr(cli_module, "run_tui", run_tui)
    monkeypatch.setattr(cli_module, "run", simple_run)
    args = make_parser().parse_args(BASE + mock_args(tmp_path))
    setup = Setup({}, tmp_path / ".env", None, ["секрет"], tmp_path / "campaigns", "tui")
    code = play(args, ScriptedInput([]), CaptureOutput(), setup)
    return code, calls


def test_play_gives_opening_to_tui(tmp_path, monkeypatch):
    code, calls = play_with_opening(tmp_path, monkeypatch, (0, None))
    assert code == 0
    assert calls["tui_opening"] == "Начало."
    assert "simple" not in calls


def test_play_fallback_to_simple_keeps_opening_and_secrets(tmp_path, monkeypatch):
    code, calls = play_with_opening(tmp_path, monkeypatch, (0, "сломалось"))
    assert code == 5
    assert calls["simple"].pop("key_factory") is not None
    assert calls["simple"] == {"replay": False, "secrets": ["секрет"], "opening": "Начало."}


# Р2: --mock + --mock-summarizer с отказом -- запасной вызов берёт шаг из сценария рассказчика

def write_steps(path, steps):
    import yaml

    path.write_text(yaml.safe_dump({"steps": steps}, allow_unicode=True), encoding="utf-8")
    return path


def summary_step(text):
    call = {"id": "ss-1", "name": "scene_summary",
            "input": {"type": "scene_summary", "title": "", "summary": text}}
    return {"tool_calls": [call]}


def end_scene_step():
    call = {"id": "es-1", "name": "end_scene", "input": {"type": "end_scene", "summary": "П."}}
    return {"tool_calls": [call]}


def last_auto_scenes(saves):
    from ai_dm.persistence.store import load_slot

    world = [p for p in saves.iterdir() if p.is_dir()][0].name
    return load_slot(saves, world, "auto").memory.scenes


def test_mock_summarizer_refusal_takes_backup_step_from_narrator_mock(tmp_path):
    narrator = write_steps(
        tmp_path / "n.yaml",
        [end_scene_step(), {"text": "Конец."}, summary_step("От мока рассказчика.")],
    )
    summarizer = write_steps(tmp_path / "s.yaml", [{"stop": "refusal"}])
    argv = BASE + ["--mock", str(narrator), "--mock-summarizer", str(summarizer),
                   "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["Иду"], env={})
    assert code == 0, out.text
    scenes = last_auto_scenes(tmp_path / "saves")
    assert [s.summary for s in scenes] == ["От мока рассказчика."]
    assert scenes[0].source == "summarizer"


def test_mock_without_mock_summarizer_still_uses_plain_fallback(tmp_path):
    narrator = write_steps(tmp_path / "n.yaml", [end_scene_step(), {"text": "Конец."}])
    argv = BASE + ["--mock", str(narrator), "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["Иду"], env={})
    assert code == 0, out.text
    scenes = last_auto_scenes(tmp_path / "saves")
    assert [s.source for s in scenes] == ["fallback"]


# шаг 190, П2: ввод ключа окном TUI

def tui_setup(tmp_path, mode, secrets=None):
    return Setup({}, tmp_path / ".env", None, [] if secrets is None else secrets,
                 tmp_path / "campaigns", mode)


def test_enter_key_in_tui_mode_opens_tui_window_and_returns_its_session(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    seen = []
    monkeypatch.setattr(tui, "enter_key", lambda session: seen.append(session) or "окно")
    notes = CaptureOutput()
    result = cli_module.enter_key(
        ScriptedInput([]), CaptureOutput(), notes, tui_setup(tmp_path, "tui"), "сессия"
    )
    assert (result, seen, notes.lines) == ("окно", ["сессия"], [])


def test_enter_key_tui_start_failure_falls_back_to_simple_with_note(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    def broken(session):
        raise tui.TuiStartError("нет терминала")

    monkeypatch.setattr(tui, "enter_key", broken)
    simple = []
    monkeypatch.setattr(
        cli_module, "enter_key_simple", lambda stdin, stdout, session: simple.append(session) or "п"
    )
    notes = CaptureOutput()
    result = cli_module.enter_key(
        ScriptedInput([]), CaptureOutput(), notes, tui_setup(tmp_path, "tui"), "сессия"
    )
    assert result == "п"
    assert simple == ["сессия"]
    assert "Ввод ключа в TUI не запустился: нет терминала, простой режим." in notes.text


def test_enter_key_in_simple_mode_does_not_touch_tui(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    monkeypatch.setattr(tui, "enter_key", lambda session: pytest.fail("TUI не нужен"))
    monkeypatch.setattr(cli_module, "enter_key_simple", lambda stdin, stdout, session: "п")
    notes = CaptureOutput()
    result = cli_module.enter_key(
        ScriptedInput([]), CaptureOutput(), notes, tui_setup(tmp_path, "simple"), "сессия"
    )
    assert (result, notes.lines) == ("п", [])


def test_enter_key_tui_returns_session_and_no_reason(monkeypatch):
    import ai_dm.ui.tui as tui

    monkeypatch.setattr(tui, "enter_key", lambda session: "окно")
    assert cli_module.enter_key_tui("с") == ("окно", None)


def test_enter_key_tui_returns_start_error_as_reason(monkeypatch):
    import ai_dm.ui.tui as tui

    error = tui.TuiStartError("нет терминала")

    def broken(session):
        raise error

    monkeypatch.setattr(tui, "enter_key", broken)
    assert cli_module.enter_key_tui("с") == (None, error)


def test_run_tui_gives_key_factory_without_secrets(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    got = {}

    def fake(game, **kwargs):
        got.update(kwargs)
        return 0

    monkeypatch.setattr(tui, "run_tui", fake)
    setup = tui_setup(tmp_path, "tui", secrets=["секрет"])
    args = make_parser().parse_args(BASE + mock_args(tmp_path))
    code, reason = cli_module.run_tui(args, type("A", (), {"audio": None})(), None,
                                      CaptureOutput(), setup)
    assert (code, reason) == (0, None)
    assert got["key_factory"] is not None
    assert "secrets" not in got


def test_run_tui_key_factory_builds_session_sharing_setup_secrets(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    got = {}
    monkeypatch.setattr(tui, "run_tui", lambda game, **kwargs: got.update(kwargs) or 0)
    setup = tui_setup(tmp_path, "tui", secrets=["секрет"])
    args = make_parser().parse_args(BASE + mock_args(tmp_path))
    cli_module.run_tui(args, type("A", (), {"audio": None})(), None, CaptureOutput(), setup)
    session = got["key_factory"]()
    assert session.deps.secrets is setup.secrets
    assert session.deps.dotenv_path == setup.dotenv_path
