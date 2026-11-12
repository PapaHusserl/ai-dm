from ai_dm.core.dice import roll_dice
from ai_dm.rules.creatures import live_effects

# образ принимает удар при 3 и больше на d6 (SRD 5.2.1)
IMAGE_HIT = 3


def deflect(engine, target_ref, result) -> bool:
    # Отражения: по цели с образами попало -- d6 на каждый образ, любой 3+ разбивает один и
    # удар уходит в него (вызывающий делает исход промахом)
    if result.outcome not in ("hit", "crit"):
        return False
    creature = engine.creature(target_ref)
    now_s = engine.world.clock.now_s
    found = [e for e in live_effects(creature, now_s) if e.kind == "mirror_image"]
    if not found:
        return False
    effect = found[0]
    rolls = [roll_dice("1d6", engine.rng).total for _ in range(effect.params["images"])]
    if max(rolls) < IMAGE_HIT:
        return False
    effect.params["images"] -= 1
    left = effect.params["images"]
    if left == 0:
        creature.active_effects.remove(effect)
        engine.log("  Отражения: образов не осталось")
    else:
        engine.log(f"  Отражения: образ разбит (осталось {left})")
    return True
