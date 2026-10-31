from ai_dm.combat.actions.standard import spend_action
from ai_dm.combat.zones import has_hiding_place
from ai_dm.rules.checks import skill_check
from ai_dm.rules.derived import ability_modifier
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import AppliedCondition

HIDE_DC = 15


def hidden_condition(creature):
    # скрытность -- состояние «невидимый» от действия Спрятаться
    for c in creature.conditions:
        if c.id == "invisible" and c.source == "hidden":
            return c
    return None


def can_hide(engine, ref) -> bool:
    # герой не скрыт, в его зоне есть укрытие или затенение, и враги в зоне его не видят
    if not engine.is_hero(ref) or hidden_condition(engine.creature(ref)) is not None:
        return False
    p = engine.part(ref)
    zone = [z for z in engine.state.zones if z.id == p.zone_id][0]
    if not has_hiding_place(zone):
        return False
    return not engine.enemy_nearby(ref)


def hide(engine, ref, option) -> list:
    spend_action(engine, ref, option)
    result = skill_check(
        engine.heroes[ref], engine.registry, engine.rng, "stealth", dc=HIDE_DC,
        now_s=engine.world.clock.now_s,
    )
    engine.log(f"{engine.name(ref)} прячется: {result.log.text}")
    if result.outcome == "success":
        engine.creature(ref).conditions.append(
            AppliedCondition(id="invisible", source="hidden", dc=result.total)
        )
    return []


def search(engine, enemy_ref) -> None:
    # в начале хода врага: он ищет скрытых героев (Внимательность против результата Скрытности)
    for p in engine.state.participants:
        if p.side != "heroes":
            continue
        creature = engine.creature(p.ref)
        condition = hidden_condition(creature)
        if condition is None:
            continue
        dc = condition.dc or HIDE_DC
        bonus = ability_modifier(engine.monster(enemy_ref).abilities["wis"])
        request = RollRequest(
            kind="check", actor=engine.actor(enemy_ref), actor_id=enemy_ref, ability="wis",
            skill="perception", bonus=bonus, bonus_parts=[("Мдр", bonus)], dc=dc,
        )
        result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
        engine.log(f"  {engine.name(enemy_ref)} ищет {engine.name(p.ref)}: {result.log.text}")
        if result.total >= dc:
            creature.conditions = [c for c in creature.conditions if c is not condition]
            engine.log(f"  {engine.name(enemy_ref)} замечает {engine.name(p.ref)}")
