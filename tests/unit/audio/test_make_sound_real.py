# Му-б (MU-PLAN B2): make_sound с настоящим MiniaudioPlayer на поддельном miniaudio
# (fake_miniaudio.py). Устройства и нативного кода нет.
from audio_kit import RecordingPrefs, audio, audio_config

from ai_dm.audio.control import make_sound
from ai_dm.audio.miniaudio_player import MiniaudioPlayer
from ai_dm.audio.player import NullPlayer


def make(tmp_path, **kw):
    return make_sound(audio_config(), RecordingPrefs(), audio(tmp_path), mute=False, **kw)


def test_make_sound_creates_real_player_without_line(fake_miniaudio, tmp_path):
    sound, line = make(tmp_path)
    assert isinstance(sound.player, MiniaudioPlayer)
    assert line is None
    assert sound.reason is None


def test_make_sound_opens_device_once(fake_miniaudio, tmp_path):
    make(tmp_path)
    assert len(fake_miniaudio.devices) == 1


def test_make_sound_gives_volume_to_real_device(fake_miniaudio, tmp_path):
    fake_miniaudio.sounds["tavern.ogg"] = (10000, 10**6)
    sound, _ = make(tmp_path)
    sound.player.set_layer("music", tmp_path / "tavern.ogg", 0.0)
    # громкость 60 -> gain 0.36
    assert list(fake_miniaudio.devices[0].pull(10)) == [3600] * 20


def test_device_error_gives_null_player_and_line(fake_miniaudio, tmp_path):
    fake_miniaudio.device_error = fake_miniaudio.MiniaudioError("No backend")
    sound, line = make(tmp_path)
    assert isinstance(sound.player, NullPlayer)
    assert line == "Звук выключен: No backend"


def test_device_error_keeps_controller_working(fake_miniaudio, tmp_path):
    fake_miniaudio.device_error = fake_miniaudio.MiniaudioError("No backend")
    sound, _ = make(tmp_path)
    assert sound.command("")[0] == "Звук выключен: No backend"


def test_mute_does_not_open_device(fake_miniaudio, tmp_path):
    sound, line = make_sound(
        audio_config(), RecordingPrefs(), audio(tmp_path), mute=True
    )
    assert line is None
    assert fake_miniaudio.devices == []
