from typing import Literal

from pydantic import BaseModel, ConfigDict, Field

from ai_dm.state.combat import CombatState, DecisionPoint
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.scene import SceneState


class LastCombat(BaseModel):
    model_config = ConfigDict(extra="forbid")
    # monster_id побеждённых врагов последнего завершённого боя; добычу берут один раз
    defeated: list[str] = Field(default_factory=list)
    looted: bool = False
    # логово группы врагов (Group.lair_location_id): клад выдаётся один раз
    lair_location_id: str | None = None
    hoard_looted: bool = False
    # снаряжение с тел (записи инвентаря); выдаётся один раз
    gear: list[InventoryEntry] = Field(default_factory=list)
    gear_looted: bool = False


class ChapterState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    number: int
    title: str = ""
    started_at_s: int = 0
    scene_count: int = 0
    closed_reason: Literal["end_chapter", "scene_limit"] | None = None


class SessionState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_scene: SceneState | None = None
    current_chapter: ChapterState | None = None
    # граница сцены не завершена: достроить при загрузке
    boundary_pending: bool = False
    active_combat: CombatState | None = None
    pending_decision: DecisionPoint | None = None
    turn_seq: int = 0
    offered_choices: list[str] = Field(default_factory=list)
    last_combat: LastCombat | None = None
