from ai_dm.rules.creatures import creature_of
from ai_dm.rules.derived import ability_modifier
from ai_dm.rules.modifiers.base import Modifier

# характеристики, которые снижает старость (ТЗ 4.1 п.4)
OLD_AGE_ABILITIES = ("str", "dex", "con")

# params["target"] эффекта -> виды бросков
EFFECT_TARGETS = {
    "attack_roll": ("attack",),
    "saving_throw": ("save", "death_save"),
}


class EffectSource:
    id = "effects"

    def modifiers(self, request, registry) -> list[Modifier]:
        result = []
        holders = [("actor", creature_of(request.actor))]
        if request.target is not None:
            holders.append(("target", creature_of(request.target)))
        for side, creature in holders:
            for effect in creature.active_effects:
                if effect.kind == "old_age":
                    # -1 к характеристике за шаг старости: штраф -- разница модификаторов
                    holder = request.actor
                    if (
                        side == "actor" and request.ability in OLD_AGE_ABILITIES
                        and hasattr(holder, "sheet")
                    ):
                        score = holder.sheet.abilities[request.ability]
                        penalty = ability_modifier(score - effect.params["steps"])
                        result.append(
                            Modifier(source=effect.id, flat=penalty - ability_modifier(score))
                        )
                    continue
                if effect.kind != "modifier":
                    continue
                params = effect.params
                # side: чей это эффект -- бросающего (по умолчанию) или цели броска
                if params.get("side", "actor") != side:
                    continue
                if request.kind not in EFFECT_TARGETS.get(params.get("target"), ()):
                    continue
                # ability: эффект только для спасбросков этой характеристики (Уклонение -- Ловкость)
                if "ability" in params and params["ability"] != request.ability:
                    continue
                against = params.get("against")
                if against is not None and against != request.target_id:
                    continue
                result.append(
                    Modifier(
                        source=effect.id,
                        advantage=params.get("mode") == "advantage",
                        disadvantage=params.get("mode") == "disadvantage",
                        dice=params.get("dice"),
                        consumes=effect if params.get("consume") else None,
                    )
                )
        return result
