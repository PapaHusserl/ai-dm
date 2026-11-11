from ai_dm.combat import downed
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import live_effects

BOND_ID = "warding_bond"


def share(engine, target_ref, dealt, attacker_ref) -> list[DomainEvent]:
    # Защитные узы: цель получила урон -- заклинатель получает столько же (после сопротивления
    # цели, SRD «the same amount»); узы на себе и лежащий заклинатель не делят урон
    if dealt.final == 0:
        return []
    now_s = engine.world.clock.now_s
    events = []
    for effect in live_effects(engine.creature(target_ref), now_s):
        caster_ref = effect.source
        if effect.kind != "bond" or caster_ref == target_ref:
            continue
        if engine.part(caster_ref).status != "active":
            continue
        taken = engine.damage(caster_ref, dealt.final, dealt.damage_types[0])
        engine.log(f"Защитные узы: {engine.name(caster_ref)} тоже получает {taken.final}")
        events += downed.after_damage(engine, caster_ref, taken, attacker_ref)
        if engine.creature(caster_ref).hp_current <= 0:
            drop(engine, caster_ref)
    return events


def drop(engine, caster_ref) -> None:
    # заклинатель на 0 HP: узы рвутся у всех, кого он связал
    for _, creature in engine.all_creatures():
        creature.active_effects = [
            e for e in creature.active_effects
            if not (e.id == BOND_ID and e.source == caster_ref)
        ]
