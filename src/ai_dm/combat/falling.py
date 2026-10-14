from ai_dm.combat import downed
from ai_dm.combat.actions.attack import roll_damage
from ai_dm.combat.zones import drop_steps
from ai_dm.core.events import DomainEvent
from ai_dm.state.creature import AppliedCondition

# SRD 5.2: 1d6 дробящего за каждые 10 фт (кость FALL_DIE), не больше 20d6
FALL_DIE = "d6"
FALL_MAX_DICE = 20


def fall_dice(steps, cfg) -> str | None:
    count = min(steps * cfg.combat.fall_step_ft // 10, FALL_MAX_DICE)
    if count == 0:
        return None
    return f"{count}{FALL_DIE}"


def fall(engine, target, from_zone_id, by_ref) -> list[DomainEvent]:
    steps = drop_steps(engine.state.zones, from_zone_id, engine.part(target).zone_id)
    dice = fall_dice(steps, engine.cfg)
    if dice is None:
        return []
    feet = steps * engine.cfg.combat.fall_step_ft
    engine.log(f"  {engine.name(target)} падает с высоты {feet} фт")
    rolled = roll_damage(engine, target, dice, 0, False, label="Падение", damage_type="bludgeoning")
    dealt = engine.damage(target, rolled.total, "bludgeoning")
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target)}: {engine.hp_text(target)}")
    if dealt.final > 0 and engine.impose(target, AppliedCondition(id="prone", source="fall")):
        engine.log(f"  {engine.name(target)} сбит с ног")
    return downed.after_damage(engine, target, dealt, by_ref)


def push(engine, ref, target, zone) -> list[DomainEvent]:
    from_zone = engine.part(target).zone_id
    engine.record_move(target, from_zone, zone)
    engine.part(target).zone_id = zone
    engine.log(f"  {engine.name(target)} отброшен в зону {zone}")
    return fall(engine, target, from_zone, ref)
