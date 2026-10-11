from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

AUDIO_DIR = Path(__file__).parent / "data"


class Theme(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # имена файлов в папке данных; пустое имя -- слоя нет
    music: str
    ambient: str = ""


class ToneThemes(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # horror = «сильно»
    horror_strong: str = "dark"
    default: str = "explore"
    # при horror = «сильно»: выбранная тема -> её мрачный вариант (nature -> wilds)
    horror_variants: dict[str, str] = Field(default_factory=dict)
    # уровень romance -> {тема -> её вариант} (откровенно: romance -> romance_sensual)
    romance_variants: dict[str, dict[str, str]] = Field(default_factory=dict)


class AudioIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")
    themes: dict[str, Theme] = Field(default_factory=dict)
    # id локации -> id темы (точные ссылки)
    locations: dict[str, str] = Field(default_factory=dict)
    # тег локации -> id темы (порядок тегов локации -- приоритет)
    location_tags: dict[str, str] = Field(default_factory=dict)
    tone: ToneThemes = Field(default_factory=ToneThemes)
    combat: str = "combat"


class Audio:
    def __init__(self, index, folder):
        self.index = index
        self.folder = folder


@lru_cache(maxsize=8)
def load_audio(folder=AUDIO_DIR):
    data = yaml.safe_load((folder / "index.yaml").read_text(encoding="utf-8"))
    return Audio(AudioIndex.model_validate(data), folder)


def theme_for_tags(index, tags):
    # первый тег, у которого есть тема
    for tag in tags:
        theme = index.location_tags.get(tag)
        if theme is not None:
            return theme
    return None


def theme_files(index, folder, theme):
    # (музыка, эмбиент): путь или None, если темы нет или файла нет в папке
    entry = index.themes.get(theme)
    if entry is None:
        return None, None
    paths = []
    for name in (entry.music, entry.ambient):
        path = folder / name
        paths.append(path if name and path.is_file() else None)
    return paths[0], paths[1]
