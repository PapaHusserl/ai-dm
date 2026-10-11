# Му-а (MU-PLAN B1): ai_dm.audio.control -- next_switch (гистерезис), SoundController на
# FakePlayer/FakeClock,
# SilentSound, make_sound. Настоящего плеера и miniaudio нет (автофикстура в conftest.py).
# Допущения: SoundController(player, audio, cfg, prefs, *, now); поля enabled/volume/ambient/player;
# gain = (volume/100) ** 2; пользовательские изменения -> prefs.save(enabled, volume, ambient).
import sys
import tomllib
import types

import pytest
from audio_kit import (
    FakePlayer,
    RecordingPrefs,
    audio,
    audio_config,
    controller,
    file_names,
    state,
)

from ai_dm.audio.control import SilentSound, SoundController, make_sound, next_switch
from ai_dm.audio.player import NullPlayer

LIBRARY_LINE = "Звук выключен: библиотека miniaudio не установлена (uv sync --extra audio)"
TAVERN = {"tags": ("таверна",)}
TOWN = {"tags": ("город",)}


def folder_of(tmp_path):
    return tmp_path / "audio"


# next_switch

def test_next_switch_same_theme_is_false():
    assert next_switch("tavern", "tavern", 0, 100, 20) is False


def test_next_switch_same_combat_is_false():
    assert next_switch("combat", "combat", 0, 100, 20) is False


def test_next_switch_enter_combat_is_immediate():
    assert next_switch("tavern", "combat", 0, 0, 20) is True


def test_next_switch_leave_combat_is_immediate():
    assert next_switch("combat", "tavern", 0, 0, 20) is True


def test_next_switch_other_theme_before_min_is_false():
    assert next_switch("tavern", "town", 0, 5, 20) is False


def test_next_switch_just_before_min_is_false():
    assert next_switch("tavern", "town", 0, 19.9, 20) is False


def test_next_switch_exactly_min_is_true():
    assert next_switch("tavern", "town", 0, 20, 20) is True


def test_next_switch_after_min_is_true():
    assert next_switch("tavern", "town", 0, 25, 20) is True


def test_next_switch_counts_from_last_switch():
    assert next_switch("tavern", "town", 100, 110, 20) is False
    assert next_switch("tavern", "town", 100, 120, 20) is True


def test_next_switch_zero_min_is_always_true():
    assert next_switch("tavern", "town", 7, 7, 0) is True


# SoundController: выбор и смена

def test_first_update_sets_both_layers(tmp_path):
    sound, player, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    folder = folder_of(tmp_path)
    assert ("layer", "music", folder / "tavern.ogg", 2.0) in player.calls
    assert ("layer", "ambient", folder / "crowd.ogg", 2.0) in player.calls


def test_crossfade_comes_from_config(tmp_path):
    sound, player, *_ = controller(tmp_path, crossfade_s=3.5)
    sound.update(state(**TAVERN))
    assert {c[3] for c in player.calls if c[0] == "layer"} == {3.5}


def test_same_state_again_sends_nothing(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    before = list(player.calls)
    clock.advance(100)
    sound.update(state(**TAVERN))
    assert player.calls == before


def test_other_location_too_soon_is_suppressed(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    before = list(player.calls)
    clock.advance(5)
    sound.update(state(**TOWN))
    assert player.calls == before


def test_suppressed_switch_applies_on_next_update_after_min(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(5)
    sound.update(state(**TOWN))
    clock.advance(15)
    sound.update(state(**TOWN))
    assert player.last_path("music") == folder_of(tmp_path) / "town.ogg"
    assert player.last_path("ambient") == folder_of(tmp_path) / "street.ogg"


def test_switch_just_before_min_still_suppressed(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(19.9)
    sound.update(state(**TOWN))
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"


def test_min_switch_comes_from_config(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path, min_switch_s=0)
    sound.update(state(**TAVERN))
    sound.update(state(**TOWN))
    assert player.last_path("music") == folder_of(tmp_path) / "town.ogg"


def test_suppressed_switch_dropped_when_state_returns(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    before = list(player.calls)
    clock.advance(5)
    sound.update(state(**TOWN))
    clock.advance(30)
    sound.update(state(**TAVERN))
    assert player.calls == before


def test_switch_time_resets_hysteresis(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(25)
    sound.update(state(**TOWN))
    clock.advance(5)
    sound.update(state(tags=("лес",)))
    assert player.last_path("music") == folder_of(tmp_path) / "town.ogg"


def test_combat_starts_immediately_and_drops_ambient(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(1)
    sound.update(state(in_combat=True, **TAVERN))
    assert player.last_path("music") == folder_of(tmp_path) / "combat.ogg"
    assert player.last_path("ambient") is None


def test_after_combat_current_location_theme_returns_immediately(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(1)
    sound.update(state(in_combat=True, **TAVERN))
    clock.advance(1)
    sound.update(state(**TAVERN))
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert player.last_path("ambient") == folder_of(tmp_path) / "crowd.ogg"


def test_after_combat_location_changed_in_fight_gives_new_theme(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    clock.advance(1)
    sound.update(state(in_combat=True, **TAVERN))
    clock.advance(1)
    sound.update(state(in_combat=True, **TOWN))
    clock.advance(1)
    sound.update(state(**TOWN))
    assert player.last_path("music") == folder_of(tmp_path) / "town.ogg"


def test_start_of_session_in_combat_plays_combat(tmp_path):
    sound, player, *_ = controller(tmp_path)
    sound.update(state(in_combat=True))
    assert player.last_path("music") == folder_of(tmp_path) / "combat.ogg"


def test_ambient_false_keeps_ambient_layer_empty(tmp_path):
    sound, player, *_ = controller(tmp_path, ambient=False)
    sound.update(state(**TAVERN))
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert all(c[2] is None for c in player.layer_calls("ambient"))


def test_disabled_config_does_not_touch_player(tmp_path):
    sound, player, *_ = controller(tmp_path, enabled=False)
    sound.update(state(**TAVERN))
    assert player.calls == []


def test_missing_music_file_gives_none_layer_without_error(tmp_path):
    data = audio(tmp_path, files=[n for n in file_names() if n != "tavern.ogg"])
    player = FakePlayer()
    sound = SoundController(player, data, audio_config(), RecordingPrefs(), now=lambda: 0.0)
    sound.update(state(**TAVERN))
    assert player.last_path("music") is None


def test_initial_fields_come_from_config(tmp_path):
    sound, *_ = controller(tmp_path, volume=33, ambient=False)
    assert (sound.enabled, sound.volume, sound.ambient) == (True, 33, False)
    assert sound.reason is None


# /music: состояние

def test_command_empty_shows_state_theme_and_files(tmp_path):
    sound, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    text = "\n".join(sound.command(""))
    assert "вкл" in text
    assert "60" in text
    assert "tavern" in text
    assert "tavern.ogg" in text
    assert "crowd.ogg" in text


def test_command_empty_shows_ambient_state(tmp_path):
    sound, *_ = controller(tmp_path, ambient=False)
    sound.update(state(**TAVERN))
    assert "эмбиент: выкл" in "\n".join(sound.command(""))


def test_command_empty_does_not_change_anything(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    before = list(player.calls)
    sound.command("")
    assert player.calls == before
    assert prefs.saves == []


# /music off, on

def test_command_off_clears_both_layers_and_saves(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("off")
    assert player.last_path("music") is None
    assert player.last_path("ambient") is None
    assert sound.enabled is False
    assert prefs.saves == [(False, 60, True)]


def test_update_after_off_does_not_touch_player(tmp_path):
    sound, player, _, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("off")
    before = list(player.calls)
    clock.advance(100)
    sound.update(state(**TOWN))
    assert player.calls == before


def test_command_on_applies_theme_immediately(tmp_path):
    sound, player, prefs, clock, _ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("off")
    clock.advance(1)
    sound.command("on")
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert player.last_path("ambient") == folder_of(tmp_path) / "crowd.ogg"
    assert sound.enabled is True
    assert prefs.saves == [(False, 60, True), (True, 60, True)]


def test_command_on_after_off_in_config_plays(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path, enabled=False)
    sound.update(state(**TAVERN))
    sound.command("on")
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert prefs.saves == [(True, 60, True)]


def test_command_off_reply_is_not_empty(tmp_path):
    sound, *_ = controller(tmp_path)
    assert sound.command("off")


# /music <0-100>

def test_command_volume_sets_gain_and_saves(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.command("35")
    assert ("volume", pytest.approx(0.35 ** 2)) in player.calls
    assert sound.volume == 35
    assert prefs.saves == [(True, 35, True)]


def test_command_volume_zero(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.command("0")
    assert ("volume", 0.0) in player.calls
    assert prefs.saves == [(True, 0, True)]


def test_command_volume_hundred(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.command("100")
    assert ("volume", pytest.approx(1.0)) in player.calls
    assert prefs.saves == [(True, 100, True)]


def test_command_volume_reply_mentions_value(tmp_path):
    sound, *_ = controller(tmp_path)
    assert "35" in "\n".join(sound.command("35"))


@pytest.mark.parametrize("arg", ["101", "-1", "abc", "ambient maybe", "ambient", "3.5", "on off"])
def test_bad_argument_gives_usage_and_changes_nothing(tmp_path, arg):
    sound, player, prefs, *_ = controller(tmp_path)
    reply = sound.command(arg)
    assert "Использование: /music [on|off|0–100|ambient on|off]" in "\n".join(reply)
    assert prefs.saves == []
    assert player.calls == []
    assert (sound.enabled, sound.volume, sound.ambient) == (True, 60, True)


# /music ambient

def test_ambient_off_clears_layer_and_saves(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("ambient off")
    assert player.last_path("ambient") is None
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert sound.ambient is False
    assert prefs.saves == [(True, 60, False)]


def test_ambient_on_restores_layer_and_saves(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path, ambient=False)
    sound.update(state(**TAVERN))
    sound.command("ambient on")
    assert player.last_path("ambient") == folder_of(tmp_path) / "crowd.ogg"
    assert sound.ambient is True
    assert prefs.saves == [(True, 60, True)]


def test_ambient_command_keeps_other_prefs(tmp_path):
    sound, _, prefs, *_ = controller(tmp_path, volume=40)
    sound.command("ambient off")
    assert prefs.saves == [(True, 40, False)]


# /music пишет настоящий audio.toml (через AudioPrefs)

def test_off_writes_audio_toml_with_three_keys(tmp_path):
    from ai_dm.config.user import AudioPrefs

    path = tmp_path / "cfg" / "audio.toml"
    sound, *_ = controller(tmp_path, prefs=AudioPrefs(path))
    sound.command("off")
    assert tomllib.loads(path.read_text(encoding="utf-8")) == {
        "audio": {"enabled": False, "volume": 60, "ambient": True}
    }


def test_volume_command_overwrites_audio_toml(tmp_path):
    from ai_dm.config.user import AudioPrefs

    path = tmp_path / "audio.toml"
    sound, *_ = controller(tmp_path, prefs=AudioPrefs(path))
    sound.command("off")
    sound.command("35")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["audio"] == {
        "enabled": False, "volume": 35, "ambient": True
    }


# stop

def test_stop_stops_player(tmp_path):
    sound, player, *_ = controller(tmp_path)
    sound.stop()
    assert player.calls[-1] == ("stop",)


# SilentSound

@pytest.mark.parametrize("arg", ["", "on", "off", "50", "ambient off"])
def test_silent_sound_command_always_gives_reason(arg):
    sound = SilentSound("звук только в TUI")
    assert sound.command(arg) == ["Звук выключен: звук только в TUI"]


def test_silent_sound_reason_is_in_the_line():
    assert SilentSound("режим --replay").command("") == ["Звук выключен: режим --replay"]


def test_silent_sound_update_and_stop_are_noops():
    sound = SilentSound("x")
    assert sound.update(state(**TAVERN)) is None
    assert sound.stop() is None


# make_sound

def make(tmp_path, *, prefs=None, mute=False, **cfg):
    prefs = RecordingPrefs() if prefs is None else prefs
    return make_sound(audio_config(**cfg), prefs, audio(tmp_path), mute=mute), prefs


def fake_player_module(monkeypatch, player):
    module = types.ModuleType("ai_dm.audio.miniaudio_player")
    module.MiniaudioPlayer = lambda *args, **kw: player
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", module)


def test_disabled_config_gives_null_player_without_line(tmp_path, monkeypatch):
    player = FakePlayer()
    fake_player_module(monkeypatch, player)
    (sound, line), _ = make(tmp_path, prefs=RecordingPrefs(enabled=False), enabled=False)
    assert isinstance(sound, SoundController)
    assert isinstance(sound.player, NullPlayer)
    assert line is None
    assert player.started == 0


def test_missing_library_gives_null_player_and_one_line(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", None)
    (sound, line), _ = make(tmp_path)
    assert isinstance(sound, SoundController)
    assert isinstance(sound.player, NullPlayer)
    assert line == LIBRARY_LINE


def test_missing_library_command_shows_reason(tmp_path, monkeypatch):
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", None)
    (sound, _), _ = make(tmp_path)
    assert "Звук выключен: библиотека miniaudio не установлена" in "\n".join(sound.command(""))
    assert sound.reason is not None


def test_player_start_failure_gives_null_player_and_line_with_reason(tmp_path, monkeypatch):
    player = FakePlayer(start_reason="No backend")
    fake_player_module(monkeypatch, player)
    (sound, line), _ = make(tmp_path)
    assert isinstance(sound.player, NullPlayer)
    assert line == "Звук выключен: No backend"
    assert player.started == 1


def test_player_started_ok_gives_real_player_without_line(tmp_path, monkeypatch):
    player = FakePlayer()
    fake_player_module(monkeypatch, player)
    (sound, line), _ = make(tmp_path)
    assert sound.player is player
    assert line is None
    assert player.started == 1
    assert sound.reason is None


def test_mute_disables_session_without_saving(tmp_path, monkeypatch):
    fake_player_module(monkeypatch, FakePlayer())
    (sound, _), prefs = make(tmp_path, mute=True)
    assert sound.enabled is False
    assert prefs.saves == []


def test_mute_sound_does_not_play(tmp_path, monkeypatch):
    player = FakePlayer()
    fake_player_module(monkeypatch, player)
    (sound, _), _ = make(tmp_path, mute=True)
    sound.update(state(**TAVERN))
    assert player.calls == []


def test_make_sound_passes_config_values_to_controller(tmp_path, monkeypatch):
    fake_player_module(monkeypatch, FakePlayer())
    (sound, _), _ = make(tmp_path, volume=25, ambient=False)
    assert (sound.volume, sound.ambient) == (25, False)


# отложенное открытие плеера: звук был выключен при старте, /music on открывает его

def deferred_sound(tmp_path, monkeypatch, result, **kw):
    # -> (звук, prefs, список вызовов open_player)
    import ai_dm.audio.control as control

    opened = []

    def fake_open(cfg):
        opened.append(cfg)
        return result

    monkeypatch.setattr(control, "open_player", fake_open)
    prefs = RecordingPrefs(enabled=False)
    sound, _ = make_sound(audio_config(**kw), prefs, audio(tmp_path), mute=False)
    return sound, prefs, opened


def test_disabled_config_defers_player(tmp_path, monkeypatch):
    sound, _, opened = deferred_sound(tmp_path, monkeypatch, (FakePlayer(), None), enabled=False)
    assert sound.deferred is True
    assert isinstance(sound.player, NullPlayer)
    assert opened == []


def test_mute_defers_player(tmp_path):
    (sound, _), _ = make(tmp_path, mute=True)
    assert sound.deferred is True
    assert isinstance(sound.player, NullPlayer)


def test_enabled_sound_is_not_deferred(tmp_path, monkeypatch):
    fake_player_module(monkeypatch, FakePlayer())
    (sound, _), _ = make(tmp_path)
    assert sound.deferred is False


def test_on_opens_player_and_sets_volume(tmp_path, monkeypatch):
    player = FakePlayer()
    sound, prefs, opened = deferred_sound(tmp_path, monkeypatch, (player, None), enabled=False)
    sound.update(state(**TAVERN))
    reply = sound.command("on")
    assert sound.player is player
    assert ("volume", pytest.approx(0.36)) in player.calls
    assert sound.reason is None
    assert "Звук выключен" not in "\n".join(reply)
    assert player.last_path("music") == folder_of(tmp_path) / "tavern.ogg"
    assert prefs.saves == [(True, 60, True)]
    assert len(opened) == 1


def test_on_with_failed_open_reports_reason_first(tmp_path, monkeypatch):
    sound, prefs, _ = deferred_sound(
        tmp_path, monkeypatch, (NullPlayer(), "нет устройства"), enabled=False
    )
    reply = sound.command("on")
    assert reply[0] == "Звук выключен: нет устройства"
    assert sound.deferred is False
    assert sound.reason == "нет устройства"
    assert prefs.saves == [(True, 60, True)]


def test_second_on_does_not_open_player_again(tmp_path, monkeypatch):
    sound, _, opened = deferred_sound(tmp_path, monkeypatch, (FakePlayer(), None), enabled=False)
    sound.command("on")
    sound.command("off")
    sound.command("on")
    assert len(opened) == 1


# правки ревью Му-а

def test_mute_then_volume_keeps_enabled_true_in_audio_toml(tmp_path, monkeypatch):
    from ai_dm.config.user import AudioPrefs

    fake_player_module(monkeypatch, FakePlayer())
    path = tmp_path / "cfg" / "audio.toml"
    (sound, _), _ = make(tmp_path, prefs=AudioPrefs(path), mute=True)
    sound.command("40")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["audio"]["enabled"] is True


def test_off_and_on_write_enabled_to_audio_toml(tmp_path):
    from ai_dm.config.user import AudioPrefs

    path = tmp_path / "audio.toml"
    sound, *_ = controller(tmp_path, prefs=AudioPrefs(path))
    sound.command("off")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["audio"]["enabled"] is False
    sound.command("on")
    assert tomllib.loads(path.read_text(encoding="utf-8"))["audio"]["enabled"] is True


def test_mute_then_on_saves_enabled_true(tmp_path, monkeypatch):
    fake_player_module(monkeypatch, FakePlayer())
    (sound, _), prefs = make(tmp_path, mute=True)
    sound.command("on")
    assert prefs.saves == [(True, 60, True)]


def test_make_sound_gives_initial_volume_to_open_player(tmp_path, monkeypatch):
    player = FakePlayer()
    fake_player_module(monkeypatch, player)
    make(tmp_path)
    assert ("volume", pytest.approx(0.36)) in player.calls


def test_make_sound_initial_volume_follows_config(tmp_path, monkeypatch):
    player = FakePlayer()
    fake_player_module(monkeypatch, player)
    make(tmp_path, volume=50)
    assert ("volume", pytest.approx(0.25)) in player.calls


def test_status_theme_without_files_has_no_brackets(tmp_path):
    from ai_dm.audio.control import SoundController

    data = audio(tmp_path, files=[])
    sound = SoundController(FakePlayer(), data, audio_config(), RecordingPrefs())
    sound.update(state())
    lines = sound.command("")
    assert "Тема: explore" in lines
    assert not any("(" in line for line in lines)


def test_status_without_ambient_does_not_name_ambient_file(tmp_path):
    sound, *_ = controller(tmp_path, ambient=False)
    sound.update(state(**TAVERN))
    text = "\n".join(sound.command(""))
    assert "tavern.ogg" in text
    assert "crowd.ogg" not in text


def test_on_when_already_on_with_same_theme_sends_nothing(tmp_path):
    sound, player, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    before = list(player.calls)
    sound.command("on")
    assert player.calls == before


def test_ambient_command_while_off_does_not_touch_layers(tmp_path):
    sound, player, prefs, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("off")
    before = list(player.calls)
    sound.command("ambient on")
    assert player.calls == before
    assert sound.ambient is True
    assert prefs.saves[-1] == (False, 60, True)


def test_status_line_exact_when_on(tmp_path):
    sound, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    assert sound.command("") == [
        "Звук: вкл, громкость 60, эмбиент: вкл", "Тема: tavern (tavern.ogg + crowd.ogg)"
    ]


def test_status_line_exact_when_off_and_ambient_off(tmp_path):
    sound, *_ = controller(tmp_path, enabled=False, ambient=False)
    assert sound.command("") == ["Звук: выкл, громкость 60, эмбиент: выкл"]


def test_status_after_off_has_no_theme_line(tmp_path):
    sound, *_ = controller(tmp_path)
    sound.update(state(**TAVERN))
    sound.command("off")
    assert sound.command("") == ["Звук: выкл, громкость 60, эмбиент: вкл"]


def test_off_uses_configured_crossfade(tmp_path):
    sound, player, *_ = controller(tmp_path, crossfade_s=3.5)
    sound.update(state(**TAVERN))
    sound.command("off")
    assert player.layer_calls("music")[-1] == ("layer", "music", None, 3.5)
    assert player.layer_calls("ambient")[-1] == ("layer", "ambient", None, 3.5)


def test_ambient_command_uses_configured_crossfade(tmp_path):
    sound, player, *_ = controller(tmp_path, crossfade_s=3.5)
    sound.update(state(**TAVERN))
    sound.command("ambient off")
    assert player.layer_calls("ambient")[-1][3] == 3.5


def test_deferred_open_receives_config(tmp_path, monkeypatch):
    sound, _, opened = deferred_sound(tmp_path, monkeypatch, (FakePlayer(), None), enabled=False)
    sound.command("on")
    assert opened == [sound.cfg]


def test_open_player_passes_config_to_library_player(monkeypatch):
    from ai_dm.audio.control import open_player

    seen = []
    module = types.ModuleType("ai_dm.audio.miniaudio_player")
    module.MiniaudioPlayer = lambda cfg: seen.append(cfg) or FakePlayer()
    monkeypatch.setitem(sys.modules, "ai_dm.audio.miniaudio_player", module)
    cfg = audio_config(volume=11)
    open_player(cfg)
    assert seen == [cfg]
