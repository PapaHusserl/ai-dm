from pydantic import BaseModel

from ai_dm.rules import divine


class CastCheck(BaseModel):
    # kind: "forbidden" -- заклинание недоступно; "ability_check" -- проверка перед сотворением,
    # провал тратит ячейку впустую
    kind: str
    ability: str | None = None
    dc: int | None = None
    reason: str = ""


class CastCheckRegistry:
    def __init__(self):
        self._sources = []

    def register(self, source) -> None:
        self._sources.append(source)

    def check(self, caster, spell_id, registry) -> list:
        result = []
        for source in self._sources:
            result += source.check(caster, spell_id, registry)
        return result


def default_cast_check_registry() -> CastCheckRegistry:
    # новый экземпляр со встроенными источниками
    result = CastCheckRegistry()
    result.register(DivineCastSource())
    return result


class DivineCastSource:
    # жрец и благосклонность своего бога (ТЗ 4.2)
    id = "divine_cleric"

    def check(self, caster, spell_id, registry) -> list:
        favor = divine.own_favor(caster)
        if favor is None or favor > -3:
            return []
        if registry.get("spell", spell_id).level < 1:
            return []
        if favor <= -9:
            return [CastCheck(kind="forbidden", reason="отлучение: только заговоры")]
        return [CastCheck(kind="ability_check", ability="wis", dc=10, reason="сомнение")]
