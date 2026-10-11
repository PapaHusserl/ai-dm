from ai_dm.rules.creatures import creature_of
from ai_dm.state.creature import DeathSaves


def remove_zero_hp_unconscious(creature) -> None:
    creature.conditions = [
        c for c in creature.conditions if not (c.id == "unconscious" and c.source == "0_hp")
    ]


def heal(target, amount: int) -> int:
    if amount < 0:
        raise ValueError("лечение не может быть отрицательным")
    if getattr(target, "status", None) == "dead":
        raise ValueError("мёртвого не лечат")
    creature = creature_of(target)
    before = creature.hp_current
    creature.hp_current = min(creature.hp_max, before + amount)
    if before == 0 and amount > 0:
        # из 0 HP: спасброски от смерти и стабильность сбрасываются
        creature.death_saves = DeathSaves()
        remove_zero_hp_unconscious(creature)
    return creature.hp_current - before
