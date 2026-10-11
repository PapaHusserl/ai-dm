from ai_dm.rules.creatures import is_hero
from ai_dm.rules.modifiers.base import Modifier


def species_effects(actor, registry) -> list:
    # пары (id умения, эффект) черт вида героя; у существа без листа пусто
    if not is_hero(actor) or not registry.has("species", actor.sheet.species_id):
        return []
    result = []
    for trait_id in registry.get("species", actor.sheet.species_id).traits:
        for effect in registry.get("feature", trait_id).effects:
            result.append((trait_id, effect))
    return result


class SpeciesTraitSource:
    id = "species"

    def modifiers(self, request, registry) -> list[Modifier]:
        # спасбросок от состояния: преимущество от черты вида (Brave, Dwarven Resilience, ...)
        condition = request.tags.get("vs_condition")
        if request.kind != "save" or condition is None:
            return []
        result = []
        for trait_id, effect in species_effects(request.actor, registry):
            if effect.type != "modifier" or effect.target != "saving_throw":
                continue
            if effect.mode == "advantage" and effect.condition == condition:
                result.append(Modifier(source=trait_id, advantage=True))
        return result
