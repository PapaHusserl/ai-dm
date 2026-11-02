from ai_dm.rules.derived import always_prepared
from ai_dm.rules.modifiers.conditions import with_implied
from ai_dm.rules.spellcasting import usable_circles
from ai_dm.state.creature import ActiveEffect, Expiry

SHIELD_BONUS = 5


def react(engine, target_ref, result, ac) -> None:
    # Щит (Р5): попадание по герою с подготовленным Щитом, которое +5 к КД превращает в промах,
    # заклинание читает само: ячейка и реакция тратятся, КД +5 до начала хода героя
    hero = engine.heroes.get(target_ref)
    if hero is None or result.outcome != "hit" or not engine.part(target_ref).turn.reaction:
        return
    # недееспособный (парализован, без сознания) заклинание не читает
    conditions = {c.id for c in with_implied(engine.creature(target_ref))}
    if not engine.is_capable(target_ref) or "incapacitated" in conditions:
        return
    if not ac <= result.total < ac + SHIELD_BONUS:
        return
    if "shield" not in list(hero.sheet.prepared_of()) + always_prepared(hero, engine.registry):
        return
    spell = engine.registry.get("spell", "shield")
    circles = usable_circles(hero, spell)
    if not circles:
        return
    hero.creature.resources[f"spell_slot:{circles[0]}"].current -= 1
    engine.part(target_ref).turn.reaction = False
    hero.creature.active_effects.append(
        ActiveEffect(
            id="shield", source=target_ref, kind="ac",
            params={"label": spell.name, "amount": SHIELD_BONUS, "magic": True},
            expires=Expiry(kind="start_of_turn", owner=target_ref),
        )
    )
    result.outcome = "miss"
    engine.log(f"  {engine.name(target_ref)}: {spell.name} — КД {ac + SHIELD_BONUS}, промах")
