from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_dm.state.scene import TurnRecord


class ChronicleEntry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    at_s: int
    kind: Literal["death", "event", "trigger", "tone", "pack_update", "favor", "imported"]
    text: str
    refs: list[str] = Field(default_factory=list)


def add_entry(bundle, kind, text, refs=None, at_s=None) -> None:
    # единственный путь записи в хронику: время -- at_s, по умолчанию текущее время мира
    if at_s is None:
        at_s = bundle.world.clock.now_s
    bundle.chronicle.entries.append(
        ChronicleEntry(at_s=at_s, kind=kind, text=text, refs=list(refs or []))
    )


class Chronicle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    entries: list[ChronicleEntry] = Field(default_factory=list)


class SceneSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    chapter_id: str = ""
    title: str = ""
    summary: str
    at_s: int = 0
    # "narrator" не пишется (выжимку даёт summarizer или запасной вариант), оставлен для схемы v5
    source: Literal["summarizer", "narrator", "fallback", "pack"] = "pack"


class ChapterSummary(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    number: int
    title: str = ""
    summary: str = ""
    source: Literal["summarizer", "concat", "pack"] = "pack"
    at_s: int = 0


class Memory(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenes: list[SceneSummary] = Field(default_factory=list)
    chapters: list[ChapterSummary] = Field(default_factory=list)
    game_summary: str = ""
    # номер последней главы, свёрнутой в game_summary
    game_summary_chapter: int = 0
    recent_turns: list[TurnRecord] = Field(default_factory=list)
