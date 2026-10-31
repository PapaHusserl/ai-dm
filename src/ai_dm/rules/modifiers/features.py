from ai_dm.rules.creatures import is_hero
from ai_dm.rules.derived import hero_feature_ids
from ai_dm.rules.modifiers.base import Modifier


def effect_modifier(effect, feature_id, request) -> Modifier | None:
    # эффект умения героя -> поправка к броску: диапазон крита (атака), преимущество на
    # инициативу и на проверки навыка
    if effect.type == "crit_range" and request.kind == "attack":
        return Modifier(source=feature_id, crit_min=effect.value)
    if effect.type != "modifier" or effect.mode != "advantage":
        return None
    if effect.target == "initiative" and request.kind == "initiative":
        return Modifier(source=feature_id, advantage=True)
    if effect.target == "skill" and request.kind == "check" and effect.skill == request.skill:
        return Modifier(source=feature_id, advantage=True)
    return None


class FeatureSource:
    id = "features"

    def modifiers(self, request, registry) -> list[Modifier]:
        # умения героя (Улучшенный критический удар, Выдающийся атлет); у существа без листа пусто
        if not is_hero(request.actor):
            return []
        result = []
        for feature_id in hero_feature_ids(request.actor, registry):
            for effect in registry.get("feature", feature_id).effects:
                found = effect_modifier(effect, feature_id, request)
                if found is not None:
                    result.append(found)
        return result
