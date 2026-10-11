# Му-а (MU-PLAN A2, B1): ai_dm.config.user -- пользовательский конфиг. Два файла в каталоге конфига:
# config.toml (руками, любые секции) и audio.toml (пишет игра, ровно [audio] enabled/volume/ambient,
# сильнее config.toml). Каталог: AI_DM_CONFIG_DIR > XDG_CONFIG_HOME/ai-dm > ~/.config/ai-dm.
import tomllib

import pytest

from ai_dm.config.user import (
    AUDIO_FILE,
    CONFIG_FILE,
    AudioPrefs,
    audio_prefs_text,
    config_dir,
    load_user_settings,
    write_audio_prefs,
)


def env_of(folder):
    return {"AI_DM_CONFIG_DIR": str(folder)}


def put(folder, name, text):
    folder.mkdir(parents=True, exist_ok=True)
    (folder / name).write_text(text, encoding="utf-8")


# имена файлов

def test_file_names():
    assert CONFIG_FILE == "config.toml"
    assert AUDIO_FILE == "audio.toml"


# config_dir

def test_config_dir_explicit_wins(tmp_path):
    env = {"AI_DM_CONFIG_DIR": str(tmp_path / "a"), "XDG_CONFIG_HOME": str(tmp_path / "x"),
           "HOME": str(tmp_path / "h")}
    assert config_dir(env) == tmp_path / "a"


def test_config_dir_xdg_when_no_explicit(tmp_path):
    env = {"XDG_CONFIG_HOME": str(tmp_path / "x"), "HOME": str(tmp_path / "h")}
    assert config_dir(env) == tmp_path / "x" / "ai-dm"


def test_config_dir_falls_back_to_home_config(tmp_path, monkeypatch):
    monkeypatch.setenv("HOME", str(tmp_path / "h"))
    monkeypatch.delenv("XDG_CONFIG_HOME", raising=False)
    assert config_dir({"HOME": str(tmp_path / "h")}) == tmp_path / "h" / ".config" / "ai-dm"


# load_user_settings

def test_no_files_gives_defaults_and_creates_nothing(tmp_path):
    folder = tmp_path / "cfg"
    settings = load_user_settings(env_of(folder))
    assert settings.app.audio.volume == 60
    assert settings.app.audio.enabled is True
    assert not folder.exists()


def test_empty_existing_folder_gives_defaults_and_stays_empty(tmp_path):
    load_user_settings(env_of(tmp_path))
    assert list(tmp_path.iterdir()) == []


def test_config_toml_is_applied(tmp_path):
    put(tmp_path, CONFIG_FILE, "[master]\nrecent_turns = 12\n")
    assert load_user_settings(env_of(tmp_path)).app.master.recent_turns == 12


def test_config_toml_audio_section_sets_defaults(tmp_path):
    put(tmp_path, CONFIG_FILE, "[audio]\nvolume = 30\n")
    assert load_user_settings(env_of(tmp_path)).app.audio.volume == 30


def test_audio_toml_alone_is_applied(tmp_path):
    put(tmp_path, AUDIO_FILE, "[audio]\nenabled = false\nvolume = 70\nambient = false\n")
    audio = load_user_settings(env_of(tmp_path)).app.audio
    assert (audio.enabled, audio.volume, audio.ambient) == (False, 70, False)


def test_audio_toml_is_stronger_than_config_toml(tmp_path):
    put(tmp_path, CONFIG_FILE, "[audio]\nvolume = 30\ncrossfade_s = 5.0\n")
    put(tmp_path, AUDIO_FILE, "[audio]\nvolume = 70\n")
    audio = load_user_settings(env_of(tmp_path)).app.audio
    assert audio.volume == 70
    assert audio.crossfade_s == 5.0


def test_broken_config_toml_names_the_file(tmp_path):
    put(tmp_path, CONFIG_FILE, "[master\nrecent_turns = ")
    with pytest.raises(ValueError, match="config.toml"):
        load_user_settings(env_of(tmp_path))


def test_broken_audio_toml_names_the_file(tmp_path):
    put(tmp_path, AUDIO_FILE, "[audio\nvolume = ")
    with pytest.raises(ValueError, match="audio.toml"):
        load_user_settings(env_of(tmp_path))


def test_invalid_value_in_config_toml_names_the_file(tmp_path):
    put(tmp_path, CONFIG_FILE, "[audio]\nbogus = 1\n")
    with pytest.raises(ValueError, match="config.toml"):
        load_user_settings(env_of(tmp_path))


# audio_prefs_text, write_audio_prefs, AudioPrefs

def parsed(text):
    return tomllib.loads(text)


def test_audio_prefs_text_has_header_and_three_keys():
    text = audio_prefs_text(False, 35, True)
    assert parsed(text) == {"audio": {"enabled": False, "volume": 35, "ambient": True}}
    assert len(text.strip().splitlines()) == 4


def test_audio_prefs_text_is_deterministic():
    assert audio_prefs_text(True, 60, False) == audio_prefs_text(True, 60, False)


def test_audio_prefs_text_differs_by_value():
    assert audio_prefs_text(True, 60, True) != audio_prefs_text(True, 61, True)
    assert audio_prefs_text(True, 60, True) != audio_prefs_text(False, 60, True)
    assert audio_prefs_text(True, 60, True) != audio_prefs_text(True, 60, False)


def test_write_audio_prefs_creates_folder(tmp_path):
    path = tmp_path / "deep" / "ai-dm" / AUDIO_FILE
    write_audio_prefs(path, True, 40, False)
    assert parsed(path.read_text(encoding="utf-8")) == {
        "audio": {"enabled": True, "volume": 40, "ambient": False}
    }


def test_write_audio_prefs_overwrites_atomically(tmp_path):
    path = tmp_path / AUDIO_FILE
    write_audio_prefs(path, True, 40, False)
    write_audio_prefs(path, False, 10, True)
    assert parsed(path.read_text(encoding="utf-8"))["audio"] == {
        "enabled": False, "volume": 10, "ambient": True
    }
    assert [p.name for p in tmp_path.iterdir()] == [AUDIO_FILE]


def test_audio_prefs_save_writes_file(tmp_path):
    path = tmp_path / "cfg" / AUDIO_FILE
    AudioPrefs(path).save(False, 5, False)
    assert parsed(path.read_text(encoding="utf-8"))["audio"] == {
        "enabled": False, "volume": 5, "ambient": False
    }


def test_saved_prefs_survive_restart(tmp_path):
    AudioPrefs(tmp_path / AUDIO_FILE).save(True, 40, False)
    audio = load_user_settings(env_of(tmp_path)).app.audio
    assert (audio.enabled, audio.volume, audio.ambient) == (True, 40, False)


def test_invalid_value_in_audio_toml_names_the_file(tmp_path):
    put(tmp_path, AUDIO_FILE, "[audio]\nbogus = 1\n")
    with pytest.raises(ValueError, match="audio.toml"):
        load_user_settings(env_of(tmp_path))
