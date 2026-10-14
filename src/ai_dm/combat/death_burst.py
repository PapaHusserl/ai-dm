from ai_dm.core.events import DomainEvent


def explode(engine, ref) -> list[DomainEvent]:
    # Предсмертный взрыв: один бросок урона, спасбросок каждого в зоне (кроме самого),
    # успех -- половина
    # локальные импорты: цикл импортов с downed и attack
    from ai_dm.combat import downed
    from ai_dm.combat.actions.attack import roll_damage, split_dice

    if not engine.monster_of(ref) or engine.monster(ref).death_burst is None:
        return []
    burst = engine.monster(ref).death_burst
    zone = engine.part(ref).zone_id
    victims = [
        q.ref for q in engine.state.participants
        if q.ref != ref and q.zone_id == zone and q.status in ("active", "down")
    ]
    engine.log(f"  {engine.name(ref)} взрывается")
    dice, bonus = split_dice(burst.dice)
    rolled = roll_damage(
        engine, ref, dice, bonus, False, label="Предсмертный взрыв", damage_type=burst.damage_type
    )
    events = []
    for victim in victims:
        amount = rolled.total
        if engine.save(victim, burst.save, burst.dc).outcome == "success":
            amount //= 2
        dealt = engine.damage(victim, amount, burst.damage_type)
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(victim)}: {engine.hp_text(victim)}")
        events += downed.after_damage(engine, victim, dealt, ref)
    return events
