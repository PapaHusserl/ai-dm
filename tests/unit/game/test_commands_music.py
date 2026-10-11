# Му-а (MU-PLAN A3, B1): /music в слое game. cmd_music(app, arg) =
# app.reply(app.audio.command(arg.strip()));
# команда есть в HELP и COMMANDS; у GameApp по умолчанию звук -- SilentSound("звук только в TUI").
import pytest
from game_kit import make_app, scripted_from_yaml

from ai_dm.game.commands import COMMANDS, HELP, cmd_music


class Recorder:
    def __init__(self, lines):
        self.args = []
        self.lines = lines

    def command(self, arg):
        self.args.append(arg)
        return self.lines


class Host:
    def __init__(self, audio):
        self.audio = audio
        self.replied = []

    def reply(self, lines=None, **fields):
        self.replied.append(lines)
        return ("reply", lines)


def test_music_is_in_help_and_commands():
    assert "music" in HELP
    assert COMMANDS["music"] is cmd_music


def test_help_text_mentions_arguments():
    text = HELP["music"]
    for part in ["on", "off", "0–100", "ambient"]:
        assert part in text


def test_cmd_music_passes_stripped_argument():
    audio = Recorder(["строка"])
    cmd_music(Host(audio), "  35 ")
    assert audio.args == ["35"]


def test_cmd_music_empty_argument():
    audio = Recorder(["строка"])
    cmd_music(Host(audio), "")
    assert audio.args == [""]


def test_cmd_music_replies_with_audio_lines():
    host = Host(Recorder(["раз", "два"]))
    assert cmd_music(host, "") == ("reply", ["раз", "два"])


def test_game_app_default_sound_is_silent_with_reason(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted_from_yaml("talk_check_fight.yaml"))
    assert app.handle("/music").lines == ["Звук выключен: звук только в TUI"]


@pytest.mark.parametrize("arg", ["on", "off", "50", "ambient off"])
def test_game_app_default_sound_ignores_arguments(registry, tmp_path, arg):
    app = make_app(registry, tmp_path, scripted_from_yaml("talk_check_fight.yaml"))
    assert app.handle("/music " + arg).lines == ["Звук выключен: звук только в TUI"]
