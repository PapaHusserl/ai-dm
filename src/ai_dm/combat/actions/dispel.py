from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.dispel import caster_env, dispel, report


def zone_effect(thing) -> bool:
    # эффект зоны (Тьма, Тишина): лежит на заклинателе, не на существе в зоне
    return getattr(thing, "kind", None) == "zone"


def end_source(engine, spell_id, owner) -> None:
    # снято заклинание, которое держит концентрация владельца: она кончается, цели свободны
    creature = engine.creature(owner)
    held = creature.concentration
    if held is None or held.spell_id != spell_id:
        return
    end_concentration(creature)
    engine.drop_concentration_effects(owner)
    name = engine.registry.get("spell", spell_id).name
    engine.log(f"  {engine.name(owner)}: {name} кончается")


def cast_dispel(engine, ref, spell, target, circle) -> list[DomainEvent]:
    # цель -- участник или зона: заклинания не выше круга ячейки снимаются сами, выше -- проверка
    # Инт против СЛ 10 + круг; концентрация источника кончается вместе с заклинанием
    owners = dict(engine.all_creatures())

    def level_of(spell_id, owner) -> int:
        held = owners[owner].concentration if owner in owners else None
        if held is not None and held.spell_id == spell_id:
            return held.circle
        return engine.registry.get("spell", spell_id).level

    env = caster_env(
        engine.heroes[ref], engine.registry, (engine.rng, engine.modifiers),
        (engine.world.clock.now_s, circle, level_of),
    )
    if target in owners:
        name = engine.name(target)
        found = [dispel(owners[target], env, lambda thing: not zone_effect(thing))]
    else:
        name = [z.name for z in engine.state.zones if z.id == target][0]
        found = [
            dispel(c, env, lambda t: zone_effect(t) and t.params["zone"] == target)
            for c in owners.values()
        ]
    for line in report(env, spell.name, name, found):
        engine.log(line)
    for spell_id, owner in dict.fromkeys(pair for done, _ in found for pair in done):
        if owner in owners:
            end_source(engine, spell_id, owner)
    return []
