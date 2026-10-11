import re
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ai_dm.core.clock import Calendar
from ai_dm.rules.builder import CharacterChoices
from ai_dm.state.hero import Companion, Equipped, LevelChoices
from ai_dm.state.memory import ChapterSummary, ChronicleEntry, SceneSummary
from ai_dm.state.world import (
    NPC,
    Faction,
    GlobalEvent,
    God,
    Location,
    NaturalEventKind,
    NaturalEventsSpec,
    Tone,
)

TIME_RE = re.compile(r"([0-9]{2}):([0-9]{2})")

__all__ = ["NaturalEventKind", "NaturalEventsSpec"]


class ChapterSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    number: int = Field(default=1, ge=1)
    title: str = ""


class StartSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # "YYYY-MM-DD" в календаре пака
    date: str
    time: str = "08:00"
    hero_location: str
    # id пресетов героев; пусто -- все пресеты пака
    heroes: list[str] = Field(default_factory=list)
    chapter: ChapterSpec = Field(default_factory=ChapterSpec)
    # выжимка стартовой сцены
    scene_summary: str = ""

    @field_validator("time")
    @classmethod
    def check_time(cls, value):
        m = TIME_RE.fullmatch(value)
        if m is None or int(m.group(1)) > 23 or int(m.group(2)) > 59:
            raise ValueError(f"неверное время: {value!r}")
        return value


class MortalitySpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    preset: Literal["calm", "peaceful", "normal", "harsh", "brutal"] = "normal"
    # N в «1/N в день»; если задан, перекрывает пресет
    per_day: int | None = Field(default=None, ge=1)


class NudgeSpec(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenes: int = Field(default=8, ge=1)


class CampaignManifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    name: str
    version: str
    calendar: Calendar | None = None
    start: StartSpec
    mortality: MortalitySpec = Field(default_factory=MortalitySpec)
    natural_events: NaturalEventsSpec = Field(default_factory=NaturalEventsSpec)
    nudge: NudgeSpec = Field(default_factory=NudgeSpec)
    tone: Tone = Field(default_factory=Tone)
    # id пресета мира по умолчанию; пусто -- тон пака как есть
    preset: str = ""
    flags: dict[str, bool | int | str] = Field(default_factory=dict)


class PackItem(BaseModel):
    model_config = ConfigDict(extra="forbid")
    item_id: str
    qty: int = 1


class HeroPreset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    choices: CharacterChoices
    inventory_extra: list[PackItem] = Field(default_factory=list)
    equipped: Equipped | None = None
    money_cp: int | None = None
    location_id: str | None = None
    motive: str = ""
    level: int = Field(default=1, ge=1)
    xp: int = Field(default=0, ge=0)
    # выборы по уровням 2..level (стиль, экспертиза, подкласс); без них пресет выше 1 ур. не собрать
    level_choices: list[LevelChoices] = Field(default_factory=list)
    companion: Companion | None = None
    favor: dict[str, int] = Field(default_factory=dict)
    deity_id: str | None = None
    # "YYYY-MM-DD" в календаре пака
    birth_date: str | None = None


class StartMemory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    game_summary: str = ""
    chapters: list[ChapterSummary] = Field(default_factory=list)
    scenes: list[SceneSummary] = Field(default_factory=list)


class StartChronicle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[ChronicleEntry] = Field(default_factory=list)


class Pack(BaseModel):
    # загруженный и проверенный пак: сущности списками в порядке файлов
    path: str
    manifest: CampaignManifest
    world_text: str
    truths: str = ""
    npcs: list[NPC] = Field(default_factory=list)
    factions: list[Faction] = Field(default_factory=list)
    pantheon: list[God] = Field(default_factory=list)
    locations: list[Location] = Field(default_factory=list)
    events: list[GlobalEvent] = Field(default_factory=list)
    heroes: list[HeroPreset] = Field(default_factory=list)
    start_memory: StartMemory = Field(default_factory=StartMemory)
    start_chronicle: StartChronicle = Field(default_factory=StartChronicle)
    # каталог слоя контента пака или None
    content_dir: str | None = None
