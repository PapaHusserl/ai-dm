from ai_dm.combat.zones import distance, range_band_ft
from ai_dm.core.events import DomainEvent
from ai_dm.rules import revive
from ai_dm.rules.spellcasting import reach_ft
from ai_dm.rules.time_ops import rounds_to_seconds


def projected_now(engine) -> int:
    # часы мира в бою стоят: «сейчас» — часы + прошедшие раунды (так же пишет смерть kill_monster)
    return engine.world.clock.now_s + rounds_to_seconds(engine.state.round, engine.cfg)


def revive_refs(engine, ref, spell) -> list[str]:
    # убитые именованные NPC рядом с заклинателем, не позже окна от смерти
    p = engine.part(ref)
    now_s = projected_now(engine)
    return [
        q.ref for q in engine.state.participants
        if q.status == "dead" and q.ref in engine.world.npcs
        and revive.revivable(engine.world.npcs[q.ref], now_s)
        and range_band_ft(distance(engine.state.zones, p.zone_id, q.zone_id)) <= reach_ft(spell)
    ]


def cast_revive(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    revive.raise_npc(engine.world.npcs[target_ref])
    engine.part(target_ref).status = "active"
    engine.log(f"  {spell.name}: {engine.name(target_ref)} жив, 1 HP")
    return [DomainEvent(type="creature_revived", data={"id": target_ref})]
