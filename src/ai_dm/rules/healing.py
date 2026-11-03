from ai_dm.rules.creatures import creature_of
from ai_dm.state.creature import ActiveEffect, DeathSaves, Expiry


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


def revert_max_hp(creature, effect) -> None:
    # откат прибавки Помощи: максимум падает на amount, текущие HP не выше нового максимума
    creature.active_effects.remove(effect)
    creature.hp_max -= effect.params["amount"]
    creature.hp_current = min(creature.hp_current, creature.hp_max)


def grant_max_hp(creature, spell_id, source, amount, until_s) -> bool:
    # Помощь: +amount к максимуму и текущим HP до until_s; повтор не складывается: равная или
    # сильнее прибавка заменяет старую (срок заново), слабее -- не действует (False)
    olds = [e for e in creature.active_effects if e.kind == "max_hp" and e.id == spell_id]
    if any(old.params["amount"] > amount for old in olds):
        return False
    for old in olds:
        revert_max_hp(creature, old)
    creature.hp_max += amount
    creature.hp_current += amount
    creature.active_effects.append(
        ActiveEffect(
            id=spell_id, source=source, kind="max_hp", params={"amount": amount},
            expires=Expiry(kind="seconds", value=until_s),
        )
    )
    return True


def expire_max_hp(hero, world) -> list[str]:
    # срок Помощи вышел по часам мира: откат у героя и NPC мира; строки лога
    lines = []
    owners = [(hero.name, hero.creature)]
    owners += [(n.name, n.creature) for n in world.npcs.values() if n.creature is not None]
    for name, creature in owners:
        for effect in [e for e in creature.active_effects if e.kind == "max_hp"]:
            if effect.expires.value > world.clock.now_s:
                continue
            revert_max_hp(creature, effect)
            lines.append(f"Помощь кончилась: {name} HP {creature.hp_current}/{creature.hp_max}")
    return lines
