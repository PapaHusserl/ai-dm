from typing import Literal

from pydantic import model_validator

from ai_dm.content.models.common import Behavior, ContentModel
from ai_dm.core.duration import Duration

INSTANT = ("instant", "instantaneous")


class UpcastStep(ContentModel):
    dice: str | None = None
    count: int | None = None
    # прибавка к числу целей (Благословение)
    targets: int | None = None


class Upcast(ContentModel):
    per_slot_level: UpcastStep


class Spell(Behavior):
    level: int
    school: str
    range_kind: Literal["self", "touch", "ranged"]
    range_ft: int | None = None
    casting_time: str = "action"
    # формат Duration ("1m"); "instant" / "instantaneous" -> duration_s = None
    duration: str = "instant"
    duration_s: int | None = None
    concentration: bool = False
    classes: list[str] = []
    upcast: Upcast | None = None
    # уровень героя -> кости заговора
    cantrip_scaling: dict[int, str] | None = None

    @model_validator(mode="after")
    def check_spell(self):
        if self.range_kind == "ranged" and self.range_ft is None:
            raise ValueError("range_ft обязателен для range_kind == ranged")
        if self.range_kind != "ranged" and self.range_ft is not None:
            raise ValueError("range_ft только для range_kind == ranged")
        if self.duration in INSTANT:
            self.duration_s = None
        else:
            self.duration_s = Duration.parse(self.duration).seconds
        return self
