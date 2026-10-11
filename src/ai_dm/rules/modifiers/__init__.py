from ai_dm.rules.modifiers.base import Modifier, ModifierRegistry
from ai_dm.rules.modifiers.conditions import ConditionSource
from ai_dm.rules.modifiers.divine_favor import DivineFavorSource
from ai_dm.rules.modifiers.effects import EffectSource
from ai_dm.rules.modifiers.species import SpeciesTraitSource

__all__ = ["Modifier", "ModifierRegistry", "default_modifier_registry"]


def default_modifier_registry() -> ModifierRegistry:
    # новый экземпляр со встроенными источниками
    result = ModifierRegistry()
    result.register(ConditionSource())
    result.register(SpeciesTraitSource())
    result.register(EffectSource())
    result.register(DivineFavorSource())
    return result
