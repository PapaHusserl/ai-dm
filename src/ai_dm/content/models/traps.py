from typing import Literal

from pydantic import field_validator

from ai_dm.content.models.common import Ability, ContentModel, ContentObject, Skill

Severity = Literal["nuisance", "dangerous", "deadly"]
# полосы уровня героя (как HAZARD_BANDS в rules/damage.py)
BANDS = ("1-4", "5-10", "11-16", "17-20")


class TrapTrigger(ContentModel):
    # path -- растяжка, плита, крышка (страховка на выходе); object -- замок и т. п.
    kind: Literal["path", "object"]
    text: str


class TrapDetect(ContentModel):
    skill: Skill
    dc: int


class TrapDisarm(ContentModel):
    text: str
    # нет skill и dc -- снимается без броска
    skill: Skill | None = None
    dc: int | None = None


class TrapSave(ContentModel):
    ability: Ability
    # СЛ по полосам уровня героя 1-4, 5-10, 11-16, 17-20; один элемент -- на все полосы
    dc: list[int]
    # при успехе половина урона
    half: bool = False

    @field_validator("dc")
    @classmethod
    def check_dc(cls, value):
        if len(value) not in (1, 4):
            raise ValueError("dc: один элемент или четыре (по полосам уровня)")
        return value


class Trap(ContentObject):
    severity: Severity
    # уровни героя [от, до], на которых ловушка выпадает по таблице
    levels: list[int]
    trigger: TrapTrigger
    detect: TrapDetect
    disarm: TrapDisarm
    save: TrapSave | None = None
    damage_type: str | None = None
    condition: str | None = None
    resets: bool = False
    # тяжесть на отдельных полосах уровня, если она не равна severity
    severity_by_level: dict[str, Severity] = {}

    @field_validator("severity_by_level")
    @classmethod
    def check_severity_by_level(cls, value):
        bad = [key for key in value if key not in BANDS]
        if bad:
            raise ValueError(f"severity_by_level: полосы только {', '.join(BANDS)}, получено {bad}")
        return value

    @field_validator("levels")
    @classmethod
    def check_levels(cls, value):
        if len(value) != 2 or not 1 <= value[0] <= value[1] <= 20:
            raise ValueError("levels: [от, до], 1..20")
        return value
