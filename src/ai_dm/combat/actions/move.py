from ai_dm.combat import downed, opportunity
from ai_dm.combat.actions.attack import roll_damage, split_dice
from ai_dm.combat.zones import hazards, is_difficult
from ai_dm.core.events import DomainEvent
from ai_dm.rules.damage import apply_damage


def zone_of(engine, zone_id):
    return [z for z in engine.state.zones if z.id == zone_id][0]


def hazard_check(engine, ref) -> list[DomainEvent]:
    # при входе в зону и в начале хода: спасбросок, при провале урон целиком
    events = []
    p = engine.part(ref)
    for feature in hazards(zone_of(engine, p.zone_id)):
        if not engine.is_capable(ref):
            break
        saved = engine.save(ref, feature.save, feature.dc)
        if saved.outcome == "success":
            continue
        dice, bonus = split_dice(feature.damage)
        rolled = roll_damage(engine, ref, dice, bonus, False)
        dealt = apply_damage(
            engine.actor(ref), rolled.total, feature.damage_type, engine.registry,
            now_s=engine.world.clock.now_s,
        )
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(ref)}: опасная зона, {engine.hp_text(ref)}")
        events += downed.after_damage(engine, ref, dealt, None)
    return events


def perform(engine, ref, option) -> list[DomainEvent]:
    p = engine.part(ref)
    new_zone = option.params["zone"]
    events = opportunity.provoke(engine, ref, p.zone_id)
    if not engine.is_capable(ref):
        # атака уронила уходящего: он остаётся на месте
        return events
    p.turn.move -= 1
    engine.record_move(ref, p.zone_id, new_zone)
    p.zone_id = new_zone
    engine.log(f"{engine.name(ref)} идёт: {zone_of(engine, new_zone).name}")
    if is_difficult(zone_of(engine, new_zone)):
        p.turn.move = 0
    return events + hazard_check(engine, ref)
