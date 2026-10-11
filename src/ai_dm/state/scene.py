from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class SceneState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    started_at_s: int
    player_turns: int = 0
    location_id: str | None = None
    # npc_id -> сколько отношения уже потрачено за сцену
    attitude_spent: dict[str, int] = Field(default_factory=dict)
    # сколько расходников (лечебных предметов) выдано за сцену
    consumables_given: int = 0
    # сколько лечебных расходников применено (use_item) за сцену
    consumables_used: int = 0
    # сколько новых сюжетных предметов создано за сцену
    custom_created: int = 0
    # сделок (trade) за сцену
    trades: int = 0
    # новых торговцев, назначенных мастером за сцену
    merchants_created: int = 0
    summary: str = ""
    title: str = ""
    # god_id -> сколько благосклонности уже потрачено за сцену
    favor_spent: dict[str, int] = Field(default_factory=dict)
    # в сцене была ключевая сущность или изменился флаг основной линии
    touched_main: bool = False
    hero_initiated_combat: bool = False
    closed_reason: (
        Literal["end_scene", "location_changed", "time_jump", "combat_ended", "turn_limit"] | None
    ) = None


class TurnRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    turn_seq: int
    at_s: int
    player_input: str
    narration: str
    requests: list[str] = Field(default_factory=list)
    rolls: list[str] = Field(default_factory=list)
    # сцена хода: вход summarizer -- ходы закрытой сцены
    scene_id: str = ""
