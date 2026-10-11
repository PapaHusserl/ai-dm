from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class DeathSaves(BaseModel):
    model_config = ConfigDict(extra="forbid")
    successes: int = 0
    failures: int = 0
    stable: bool = False


class ResourcePool(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current: int
    max: int


class Expiry(BaseModel):
    model_config = ConfigDict(extra="forbid")
    kind: Literal["rounds", "end_of_turn", "start_of_turn", "seconds", "concentration"]
    value: int = 0
    owner: str | None = None


class ActiveEffect(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source: str
    kind: str
    params: dict[str, int | str | bool] = Field(default_factory=dict)
    expires: Expiry | None = None


class AppliedCondition(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    source: str | None = None
    expires: Expiry | None = None
    # СЛ обнаружения скрытого существа (результат Скрытности)
    dc: int | None = None


class Concentration(BaseModel):
    model_config = ConfigDict(extra="forbid")
    spell_id: str
    circle: int = Field(ge=0)
    # игровые секунды конца концентрации (логика -- К1)
    until_s: int | None = None


class TempForm(BaseModel):
    model_config = ConfigDict(extra="forbid")
    monster_id: str
    source: str
    until_s: int | None = None
    temp_hp_granted: int = 0


class Equipment(BaseModel):
    model_config = ConfigDict(extra="forbid")
    armor: str | None = None
    shield: str | None = None
    weapons: list[str] = Field(default_factory=list)


class CreatureState(BaseModel):
    model_config = ConfigDict(extra="forbid")
    hp_current: int
    hp_max: int
    hp_temp: int = 0
    conditions: list[AppliedCondition] = Field(default_factory=list)
    exhaustion: int = 0
    active_effects: list[ActiveEffect] = Field(default_factory=list)
    death_saves: DeathSaves = Field(default_factory=DeathSaves)
    resources: dict[str, ResourcePool] = Field(default_factory=dict)
    concentration: Concentration | None = None
    temp_form: TempForm | None = None
