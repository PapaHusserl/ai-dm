from typing import Annotated, Literal, Union

from pydantic import BaseModel, BeforeValidator, ConfigDict, Field, field_validator

from ai_dm.core.duration import Duration

# короткая запись {вид: значение} -> имя поля, куда кладётся значение
SHORT_FIELDS = {
    "flag": "name",
    "hero_has": "item",
    "hero_at": "location",
    "event_active": "event",
    "narrative": "text",
    "time_after": "seconds",
    "all": "items",
    "any": "items",
    "not": "item",
}
# виды без полей: {hero_dead: true}
SHORT_NO_FIELDS = ["hero_dead"]
# виды, у которых в короткой записи значение -- словарь с полями
SHORT_DICT = ["npc_status", "npc_at", "attitude", "favor"]


def expand_condition(value):
    if not isinstance(value, dict) or "type" in value:
        return value
    if len(value) != 1:
        raise ValueError(f"условие должно иметь один вид, получено: {list(value)}")
    kind, body = next(iter(value.items()))
    if kind in SHORT_FIELDS:
        return {"type": kind, SHORT_FIELDS[kind]: body}
    if kind in SHORT_NO_FIELDS:
        return {"type": kind}
    if kind in SHORT_DICT:
        if not isinstance(body, dict):
            raise ValueError(f"условие {kind!r}: ожидался словарь, получено {body!r}")
        return {"type": kind, **body}
    raise ValueError(f"неизвестный вид условия: {kind!r}")


class AllOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["all"] = "all"
    items: list["Condition"]


class AnyOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["any"] = "any"
    items: list["Condition"]


class NotOf(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["not"] = "not"
    item: "Condition"


class Flag(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["flag"] = "flag"
    name: str
    value: bool = True


class HeroHas(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["hero_has"] = "hero_has"
    item: str


class NpcStatus(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    type: Literal["npc_status"] = "npc_status"
    id: str
    is_: str = Field(alias="is")


class HeroAt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["hero_at"] = "hero_at"
    location: str


class NpcAt(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["npc_at"] = "npc_at"
    id: str
    at: str


class TimeAfter(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["time_after"] = "time_after"
    seconds: int


class Attitude(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["attitude"] = "attitude"
    npc: str
    gte: int | None = None
    lte: int | None = None


class Favor(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["favor"] = "favor"
    god: str
    gte: int | None = None
    lte: int | None = None


class EventActive(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["event_active"] = "event_active"
    event: str


class HeroDead(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["hero_dead"] = "hero_dead"


class Narrative(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: Literal["narrative"] = "narrative"
    text: str


Condition = Annotated[
    Union[  # noqa: UP007
        AllOf, AnyOf, NotOf, Flag, HeroHas, NpcStatus, HeroAt, NpcAt, TimeAfter,
        Attitude, Favor, EventActive, HeroDead, Narrative,
    ],
    Field(discriminator="type"),
    BeforeValidator(expand_condition),
]

AllOf.model_rebuild()
AnyOf.model_rebuild()
NotOf.model_rebuild()


class Trigger(BaseModel):
    model_config = ConfigDict(extra="forbid", populate_by_name=True)
    id: str
    if_: Condition = Field(alias="if")
    then: str
    once: bool = False
    state: Literal["active", "fired", "disabled"] = "active"
    cooldown: str | None = None
    key: bool = False
    # цель -- убить героя (ТЗ 2.3): снимает бюджет боя
    kills_hero: bool = False
    fired_count: int = 0
    last_fired_at: int | None = None

    @field_validator("cooldown")
    @classmethod
    def check_cooldown(cls, value):
        if value is not None:
            Duration.parse(value)
        return value


class Secret(BaseModel):
    model_config = ConfigDict(extra="forbid")
    id: str
    text: str
    reveal_if: Condition
    revealed: bool = False
    # нарративную часть условия подтвердила роль world
    narrative_ok: bool = False
