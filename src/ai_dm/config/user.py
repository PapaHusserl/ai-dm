import tomllib
from pathlib import Path

from ai_dm.config.app import load_settings

# config.toml правит пользователь (любые секции); audio.toml пишет только игра и применяет поверх
CONFIG_FILE = "config.toml"
AUDIO_FILE = "audio.toml"


def config_dir(env):
    if env.get("AI_DM_CONFIG_DIR"):
        return Path(env["AI_DM_CONFIG_DIR"])
    if env.get("XDG_CONFIG_HOME"):
        return Path(env["XDG_CONFIG_HOME"]) / "ai-dm"
    return Path.home() / ".config" / "ai-dm"


def read_toml(path):
    # текст файла или None; ошибку TOML называем по файлу
    if not path.exists():
        return None
    text = path.read_text(encoding="utf-8")
    try:
        tomllib.loads(text)
    except tomllib.TOMLDecodeError as error:
        raise ValueError(f"{path}: {error}") from error
    return text


def load_named(name, **layers):
    # ошибка проверки настроек называет файл, который их добавил
    try:
        return load_settings(**layers)
    except ValueError as error:
        raise ValueError(f"{name}: {error}") from error


def load_user_settings(env):
    folder = config_dir(env)
    config_text = read_toml(folder / CONFIG_FILE)
    audio_text = read_toml(folder / AUDIO_FILE)
    settings = load_named(folder / CONFIG_FILE, toml_text=config_text)
    if audio_text is None:
        return settings
    return load_named(folder / AUDIO_FILE, toml_text=config_text, path=folder / AUDIO_FILE)


def audio_prefs_text(enabled, volume, ambient):
    return (
        "[audio]\n"
        f"enabled = {str(enabled).lower()}\n"
        f"volume = {volume}\n"
        f"ambient = {str(ambient).lower()}\n"
    )


def write_audio_prefs(path, enabled, volume, ambient):
    path.parent.mkdir(parents=True, exist_ok=True)
    temp = path.with_name(path.name + ".tmp")
    temp.write_text(audio_prefs_text(enabled, volume, ambient), encoding="utf-8")
    temp.replace(path)


class AudioPrefs:
    # куда /music сохраняет настройки между запусками
    def __init__(self, path):
        self.path = path

    def save(self, enabled, volume, ambient):
        write_audio_prefs(self.path, enabled, volume, ambient)
