from pydantic import BaseModel, ConfigDict, Field

from ai_dm.state.hero import HeroState
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.session import SessionState
from ai_dm.state.world import WorldState


class Manifest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    schema_version: int
    engine_version: str
    world_id: str
    campaign_id: str | None
    slot: str
    saved_at: str
    current_hero_id: str | None
    heroes: list[str] = Field(default_factory=list)


class SaveBundle(BaseModel):
    model_config = ConfigDict(extra="forbid")
    manifest: Manifest
    world: WorldState
    chronicle: Chronicle
    memory: Memory
    heroes: list[HeroState] = Field(default_factory=list)
    session: SessionState
