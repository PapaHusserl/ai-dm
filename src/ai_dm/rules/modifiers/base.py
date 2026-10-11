from pydantic import BaseModel

from ai_dm.state.creature import ActiveEffect


class Modifier(BaseModel):
    source: str
    # подпись источника преимущества/помехи в строке броска; пусто -- по source
    label: str = ""
    advantage: bool = False
    disadvantage: bool = False
    flat: int = 0
    dice: str | None = None
    auto_fail: bool = False
    auto_crit: bool = False
    # прибавляется к цели броска (КД или СЛ), например укрытие
    dc_bonus: int = 0
    # с какого значения d20 атака критическая; итоговое -- минимум из источников (по умолчанию 20)
    crit_min: int | None = None
    # эффект, который конвейер снимает с актёра после броска (Sap, Vex)
    consumes: ActiveEffect | None = None


class ModifierRegistry:
    def __init__(self):
        self._sources = []

    def register(self, source) -> None:
        self._sources.append(source)

    def collect(self, request, registry) -> list[Modifier]:
        result = []
        for source in self._sources:
            result += source.modifiers(request, registry)
        return result
