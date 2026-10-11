from functools import lru_cache
from pathlib import Path

import yaml
from pydantic import BaseModel, ConfigDict, Field

ART_DIR = Path(__file__).parent / "data"


class ArtIndex(BaseModel):
    model_config = ConfigDict(extra="forbid")
    source: str = "custom"
    # title, victory, death, level_up -> id рисунка
    events: dict[str, str] = Field(default_factory=dict)
    # id локации -> id рисунка (точные ссылки)
    locations: dict[str, str] = Field(default_factory=dict)
    # тег локации -> id рисунка (порядок тегов локации -- приоритет)
    location_tags: dict[str, str] = Field(default_factory=dict)
    # id монстра -> id рисунка
    monsters: dict[str, str] = Field(default_factory=dict)
    # creature_type монстра -> id рисунка
    creature_types: dict[str, str] = Field(default_factory=dict)


class Art:
    def __init__(self, index, pictures):
        self.index = index
        # id рисунка -> текст (строки через \n, без хвостового перевода строки)
        self.pictures = pictures


@lru_cache(maxsize=1)
def load_art():
    data = yaml.safe_load((ART_DIR / "index.yaml").read_text(encoding="utf-8"))
    pictures = {}
    for path in sorted(ART_DIR.glob("*.txt")):
        pictures[path.stem] = path.read_text(encoding="utf-8").removesuffix("\n")
    return Art(ArtIndex.model_validate(data), pictures)


def art_for_event(name):
    art = load_art()
    art_id = art.index.events.get(name)
    return art.pictures.get(art_id)


def art_for_location(loc):
    # точный id -> первый совпавший тег -> None
    art = load_art()
    art_id = art.index.locations.get(loc.id)
    if art_id is None:
        for tag in loc.tags:
            art_id = art.index.location_tags.get(tag)
            if art_id is not None:
                break
    return art.pictures.get(art_id)


def art_for_monster(mon):
    # точный id -> creature_type -> None
    art = load_art()
    art_id = art.index.monsters.get(mon.id)
    if art_id is None:
        art_id = art.index.creature_types.get(mon.creature_type)
    return art.pictures.get(art_id)
