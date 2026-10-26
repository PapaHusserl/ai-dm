# Му-а (MU-PLAN A4, B1): cli и звук -- флаг --mute; ai_dm.ui.cli.run_tui(args, app, opening,
# notes, setup)
# подключает app.audio (только TUI): --replay/--mock -- SilentSound с причиной режима и без строки;
# нет библиотеки -- ровно одна строка «Звук выключен: …» в notes.lines; пользовательский конфиг
# (config.toml/audio.toml) читается во всех трёх точках (prepare, --import, --replay-report) и
# переживает перезапуск. TUI не запускается: tui.run_tui подменяется записывающей функцией.
import io
import sys
import tomllib
import types
from pathlib import Path
from types import SimpleNamespace

import pytest
from ui_kit import SEED, cli, write_script

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "audio"))

from audio_kit import FakePlayer  # noqa: E402

import ai_dm.ui.cli as cli_module  # noqa: E402
from ai_dm.audio.catalog import load_audio  # noqa: E402
from ai_dm.audio.control import SilentSound, SoundController  # noqa: E402
from ai_dm.audio.player import NullPlayer  # noqa: E402
from ai_dm.config.app import load_settings  # noqa: E402
from ai_dm.config.user import AudioPrefs  # noqa: E402
from ai_dm.ui.cli import main, make_parser  # noqa: E402

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]
LIBRARY_LINE = "Звук выключен: библиотека miniaudio не установлена (uv sync --extra audio)"


@pytest.fixture(autouse=True)
def no_real_miniaudio(monkeypatch):
    monkeypatch.setitem(sys.modules, "miniaudio", None)


@pytest.fixture
def no_library(monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", None)


def fake_library(monkeypatch, player):
    module = types.ModuleType("ai_dm.audio.miniaudio_player")
    module.MiniaudioPlayer = lambda *args, **kw: player
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", module)


class Tty(io.StringIO):
    def isatty(self):
        return True


class TtyStdin:
    def isatty(self):
        return True

    def readline(self):
        return ""


def fake_terminal(monkeypatch):
    monkeypatch.setattr(sys, "stdin", TtyStdin())
    monkeypatch.setattr(sys, "stdout", Tty())


def ran_tui(monkeypatch, effect=None):
    # подмена tui.run_tui: запоминает игру и строки старта; effect(game) -- действие «внутри TUI»
    import ai_dm.ui.tui as tui

    calls = []

    def fake(game, notes=(), replay=False, secrets=(), opening=None):
        calls.append({"game": game, "notes": list(notes), "replay": replay, "secrets": secrets,
                      "opening": opening})
        if effect is not None:
            effect(game)
        return 0

    monkeypatch.setattr(tui, "run_tui", fake)
    return calls


def mock_args(tmp_path):
    script = write_script(tmp_path / "one.yaml", "Трактирщик кивает.")
    return ["--mock", str(script), "--saves", str(tmp_path / "saves")]


def real_main(argv, env):
    return main(argv, env=env, dotenv_path=None)


def put(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


# флаг --mute

def test_mute_is_in_help():
    assert "--mute" in make_parser().format_help()


def test_mute_is_off_by_default():
    assert make_parser().parse_args(BASE).mute is False


def test_mute_flag_is_parsed():
    assert make_parser().parse_args([*BASE, "--mute"]).mute is True


def test_mute_is_accepted_and_ignored_in_simple_mode(tmp_path):
    code, out = cli([*BASE, "--mute", "--simple", *mock_args(tmp_path)], lines=["/quit"], env={})
    assert code == 0
    assert "HP" in out.text


# cli.run_tui: подключение звука

def tui_setup(tmp_path):
    return SimpleNamespace(env={"AI_DM_CONFIG_DIR": str(tmp_path / "cfg")}, secrets=())


def call_run_tui(monkeypatch, tmp_path, *flags, setup=None):
    # -> (app, notes, код); настоящего TUI нет
    ran_tui(monkeypatch)
    args = make_parser().parse_args([*BASE, *flags])
    app = SimpleNamespace(settings=load_settings(), audio=None)
    notes = SimpleNamespace(lines=[])
    code, reason = cli_module.run_tui(
        args, app, None, notes, tui_setup(tmp_path) if setup is None else setup
    )
    assert reason is None
    return app, notes, code


def test_mock_mode_gives_silent_sound_with_mode_reason_and_no_line(monkeypatch, tmp_path):
    app, notes, _ = call_run_tui(monkeypatch, tmp_path, "--mock", "m.yaml")
    assert isinstance(app.audio, SilentSound)
    assert app.audio.command("") == ["Звук выключен: режим --mock"]
    assert notes.lines == []


def test_replay_mode_gives_silent_sound_with_mode_reason_and_no_line(monkeypatch, tmp_path):
    app, notes, _ = call_run_tui(monkeypatch, tmp_path, "--replay")
    assert isinstance(app.audio, SilentSound)
    assert app.audio.command("") == ["Звук выключен: режим --replay"]
    assert notes.lines == []


def test_without_library_one_line_goes_to_notes(monkeypatch, tmp_path, no_library):
    app, notes, code = call_run_tui(monkeypatch, tmp_path)
    assert notes.lines == [LIBRARY_LINE]
    assert isinstance(app.audio, SoundController)
    assert isinstance(app.audio.player, NullPlayer)
    assert code == 0


def test_with_library_no_line_and_real_player(monkeypatch, tmp_path):
    player = FakePlayer()
    fake_library(monkeypatch, player)
    app, notes, _ = call_run_tui(monkeypatch, tmp_path)
    assert notes.lines == []
    assert app.audio.player is player


def test_no_device_gives_one_line_with_reason(monkeypatch, tmp_path):
    fake_library(monkeypatch, FakePlayer(start_reason="No backend"))
    _, notes, _ = call_run_tui(monkeypatch, tmp_path)
    assert notes.lines == ["Звук выключен: No backend"]


def test_mute_gives_silent_controller_and_writes_nothing(monkeypatch, tmp_path):
    fake_library(monkeypatch, FakePlayer())
    app, notes, _ = call_run_tui(monkeypatch, tmp_path, "--mute")
    assert app.audio.enabled is False
    assert notes.lines == []
    assert not (tmp_path / "cfg").exists()


def test_music_command_writes_audio_toml_into_config_dir(monkeypatch, tmp_path, no_library):
    app, _, _ = call_run_tui(monkeypatch, tmp_path)
    app.audio.command("40")
    saved = tomllib.loads((tmp_path / "cfg" / "audio.toml").read_text(encoding="utf-8"))
    assert saved == {"audio": {"enabled": True, "volume": 40, "ambient": True}}


def test_disabled_in_settings_gives_no_line(monkeypatch, tmp_path):
    ran_tui(monkeypatch)
    args = make_parser().parse_args(BASE)
    settings = load_settings("[audio]\nenabled = false\n")
    app = SimpleNamespace(settings=settings, audio=None)
    notes = SimpleNamespace(lines=[])
    cli_module.run_tui(args, app, None, notes, tui_setup(tmp_path))
    assert notes.lines == []
    assert app.audio.enabled is False


# через main: звук доходит до игры, настройки переживают перезапуск

def test_tui_game_gets_sound_from_main(monkeypatch, tmp_path, no_library):
    fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    env = {"TERM": "xterm", "AI_DM_CONFIG_DIR": str(tmp_path / "cfg")}
    assert real_main(BASE + mock_args(tmp_path), env) == 0
    assert isinstance(calls[0]["game"].audio, SilentSound)


def test_volume_set_in_tui_survives_restart(monkeypatch, tmp_path, no_library):
    fake_terminal(monkeypatch)
    prefs = AudioPrefs(tmp_path / "cfg" / "audio.toml")

    def set_volume(game):
        # в --mock звук SilentSound (Q8): контроллер собираем напрямую
        sound = SoundController(NullPlayer(), load_audio(), game.settings.app.audio, prefs)
        sound.command("40")

    ran_tui(monkeypatch, effect=set_volume)
    env = {"TERM": "xterm", "AI_DM_CONFIG_DIR": str(tmp_path / "cfg")}
    (tmp_path / "one").mkdir()
    (tmp_path / "two").mkdir()
    real_main(BASE + mock_args(tmp_path / "one"), env)
    calls = ran_tui(monkeypatch)
    real_main(BASE + mock_args(tmp_path / "two"), env)
    assert calls[0]["game"].settings.app.audio.volume == 40


# пользовательский конфиг: prepare, --import, --replay-report

def test_config_toml_is_read_in_prepare(monkeypatch, tmp_path):
    fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    put(tmp_path / "cfg", "config.toml", "[journal]\nmax_mb = 7\n")
    env = {"TERM": "xterm", "AI_DM_CONFIG_DIR": str(tmp_path / "cfg")}
    assert real_main(BASE + mock_args(tmp_path), env) == 0
    assert calls[0]["game"].settings.app.journal.max_mb == 7


def test_audio_toml_is_read_in_prepare(monkeypatch, tmp_path):
    fake_terminal(monkeypatch)
    calls = ran_tui(monkeypatch)
    put(tmp_path / "cfg", "audio.toml", "[audio]\nenabled = true\nvolume = 25\nambient = false\n")
    env = {"TERM": "xterm", "AI_DM_CONFIG_DIR": str(tmp_path / "cfg")}
    real_main(BASE + mock_args(tmp_path), env)
    audio = calls[0]["game"].settings.app.audio
    assert (audio.volume, audio.ambient) == (25, False)


def test_config_toml_is_read_in_import(tmp_path):
    put(tmp_path / "cfg", "config.toml", "[import]\nmax_chars = 10\n")
    summary = tmp_path / "summary.txt"
    summary.write_text("а" * 11, encoding="utf-8")
    argv = ["--import", str(summary), "--campaign", "pack_x", *mock_args(tmp_path)]
    code, out = cli(argv, env={"AI_DM_CONFIG_DIR": str(tmp_path / "cfg")},
                    campaigns_dir=tmp_path / "campaigns")
    assert code == 1
    assert "Выжимка длиннее 10 символов (11)" in out.text


def test_config_dir_is_read_in_replay_report(tmp_path, monkeypatch):
    seen = []

    def spy(env):
        seen.append(env)
        raise RuntimeError("stop")

    monkeypatch.setattr(cli_module, "load_user_settings", spy)
    setup = SimpleNamespace(env={"AI_DM_CONFIG_DIR": str(tmp_path)})
    report = SimpleNamespace(records=[], now_iso="2026-01-01T00:00:00+00:00")
    with pytest.raises(RuntimeError, match="stop"):
        cli_module.play_report(report, None, tmp_path, None, setup)
    assert seen == [setup.env]


def test_play_report_gives_game_a_factory_with_config_env_and_dotenv(tmp_path, monkeypatch):
    # шаг 184 П2: /model в повторе видит ключи (в том числе из .env) и хостеры из конфига
    class Stop(Exception):
        pass

    captured = {}
    made = []

    def fake_game(*args, **kwargs):
        captured.update(kwargs)
        raise Stop

    def fake_make(provider, model, app_cfg, **kwargs):
        made.append((provider, model, app_cfg, kwargs))
        return "adapter"

    monkeypatch.setattr(cli_module, "GameApp", fake_game)
    monkeypatch.setattr(cli_module, "make_adapter", fake_make)
    setup = SimpleNamespace(
        env={"AI_DM_CONFIG_DIR": str(tmp_path)}, dotenv_path=tmp_path / ".env",
        campaigns_dir=tmp_path, secrets=[],
    )
    report = SimpleNamespace(
        records=[], now_iso="2026-01-01T00:00:00+00:00", meta={"model": "m"},
        before=SimpleNamespace(world=SimpleNamespace(lore=SimpleNamespace(world_text=""))),
    )
    with pytest.raises(Stop):
        cli_module.play_report(report, None, tmp_path, None, setup)
    result = captured["adapter_factory"]("openrouter", "deepseek/deepseek-v4-flash")
    assert result == "adapter"
    provider, model, app_cfg, kwargs = made[0]
    assert (provider, model) == ("openrouter", "deepseek/deepseek-v4-flash")
    assert "openrouter" in app_cfg.providers
    assert kwargs == {"env": setup.env, "dotenv_path": setup.dotenv_path}


def test_broken_config_toml_is_code_1_with_file_name(tmp_path):
    put(tmp_path / "cfg", "config.toml", "[journal\nmax_mb = ")
    code, out = cli([*BASE, *mock_args(tmp_path)], lines=["/quit"],
                    env={"AI_DM_CONFIG_DIR": str(tmp_path / "cfg")})
    assert code == 1
    assert "config.toml" in out.text


def test_default_cli_helper_does_not_read_home_config(tmp_path, monkeypatch):
    # conftest: HOME -- пустой каталог; env={} не должен давать ошибок конфига
    code, _ = cli([*BASE, "--simple", *mock_args(tmp_path)], lines=["/quit"], env={})
    assert code == 0


def test_tui_start_error_drops_sound_line_and_goes_silent(monkeypatch, tmp_path, no_library):
    import ai_dm.ui.tui as tui

    def boom(*args, **kwargs):
        raise tui.TuiStartError("нет кадра")

    monkeypatch.setattr(tui, "run_tui", boom)
    args = make_parser().parse_args(BASE)
    app = SimpleNamespace(settings=load_settings(), audio=None)
    notes = SimpleNamespace(lines=[])
    code, reason = cli_module.run_tui(args, app, None, notes, tui_setup(tmp_path))
    assert code is None
    assert str(reason) == "нет кадра"
    assert notes.lines == []
    assert isinstance(app.audio, SilentSound)
    assert app.audio.command("") == ["Звук выключен: звук только в TUI"]


def test_run_tui_passes_arguments_to_tui(monkeypatch, tmp_path, no_library):
    calls = ran_tui(monkeypatch)
    args = make_parser().parse_args([*BASE, "--replay"])
    app = SimpleNamespace(settings=load_settings(), audio=None)
    notes = SimpleNamespace(lines=["старт"])
    setup = SimpleNamespace(env={"AI_DM_CONFIG_DIR": str(tmp_path)}, secrets=("sk-1",))
    cli_module.run_tui(args, app, "вступление", notes, setup)
    assert calls[0]["notes"] == ["старт"]
    assert calls[0]["replay"] is True
    assert calls[0]["secrets"] == ("sk-1",)
    assert calls[0]["opening"] == "вступление"


def test_run_tui_replay_false_is_passed_as_false(monkeypatch, tmp_path, no_library):
    calls = ran_tui(monkeypatch)
    args = make_parser().parse_args(BASE)
    app = SimpleNamespace(settings=load_settings(), audio=None)
    cli_module.run_tui(args, app, None, SimpleNamespace(lines=[]), tui_setup(tmp_path))
    assert calls[0]["replay"] is False


def test_attached_sound_uses_package_audio_index(monkeypatch, tmp_path, no_library):
    from ai_dm.audio.catalog import AUDIO_DIR

    app, _, _ = call_run_tui(monkeypatch, tmp_path)
    assert app.audio.audio.folder == AUDIO_DIR
