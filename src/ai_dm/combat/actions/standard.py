from ai_dm.core.events import DomainEvent
from ai_dm.rules.checks import skill_check
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.derived import ability_modifier
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import ActiveEffect, Expiry


def dash(engine, ref, option) -> list[DomainEvent]:
    p = engine.part(ref)
    p.turn.action = False
    p.turn.move += 1
    engine.log(f"{engine.name(ref)}: рывок")
    return []


def disengage(engine, ref, option) -> list[DomainEvent]:
    p = engine.part(ref)
    if option.params.get("bonus"):
        p.turn.bonus = False
    else:
        p.turn.action = False
    p.turn.disengaged = True
    engine.log(f"{engine.name(ref)}: отход")
    return []


def dodge(engine, ref, option) -> list[DomainEvent]:
    engine.part(ref).turn.action = False
    # помеха атакующим по уклоняющемуся и преимущество на его спасброски Ловкости
    effects = engine.creature(ref).active_effects
    effects.append(
        ActiveEffect(
            id="dodge", source=ref, kind="modifier",
            params={"target": "attack_roll", "mode": "disadvantage", "side": "target"},
            expires=Expiry(kind="start_of_turn", owner=ref),
        )
    )
    effects.append(
        ActiveEffect(
            id="dodge", source=ref, kind="modifier",
            params={"target": "saving_throw", "mode": "advantage", "ability": "dex"},
            expires=Expiry(kind="start_of_turn", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: уклонение")
    return []


def help_ally(engine, ref, option) -> list[DomainEvent]:
    engine.part(ref).turn.action = False
    ally = option.params["ally"]
    enemy = option.params["enemy"]
    engine.creature(ally).active_effects.append(
        ActiveEffect(
            id="help", source=ref, kind="modifier",
            params={
                "target": "attack_roll", "mode": "advantage", "against": enemy, "consume": True,
            },
            expires=Expiry(kind="start_of_turn", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)} помогает {engine.name(ally)} против {engine.name(enemy)}")
    return []


def stabilize(engine, ref, option) -> list[DomainEvent]:
    engine.part(ref).turn.action = False
    target_ref = option.params["target"]
    hero = engine.heroes[ref]
    result = skill_check(hero, engine.registry, engine.rng, "medicine", dc=10)
    engine.log(f"{engine.name(ref)} -> {engine.name(target_ref)}: стабилизация: {result.log.text}")
    if result.outcome == "success":
        saves = engine.heroes[target_ref].creature.death_saves
        saves.successes = 0
        saves.failures = 0
        saves.stable = True
    return []


def flee(engine, ref, option) -> list[DomainEvent]:
    p = engine.part(ref)
    p.turn.action = False
    p.status = "fled"
    engine.log(f"{engine.name(ref)} убегает")
    return [DomainEvent(type="participant_fled", data={"id": ref})]


def escape(engine, ref, option) -> list[DomainEvent]:
    # опутанный лозами: проверка Силы (Атлетика) против СЛ заклинателя; успех -- конец заклинания
    engine.part(ref).turn.action = False
    effect = [e for e in engine.creature(ref).active_effects if e.kind == "ensnared"][0]
    dc = effect.params["dc"]
    if engine.is_hero(ref):
        result = skill_check(
            engine.heroes[ref], engine.registry, engine.rng, "athletics", dc=dc,
            modifiers=engine.modifiers,
        )
    else:
        mod = ability_modifier(engine.monster(ref).abilities["str"])
        request = RollRequest(
            kind="check", actor=engine.actor(ref), actor_id=ref, ability="str", bonus=mod,
            dc=dc, bonus_parts=[("Сил", mod)],
        )
        result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
    engine.log(f"{engine.name(ref)}: вырывается из лоз: {result.log.text}")
    if result.outcome == "success":
        caster_ref = effect.source
        end_concentration(engine.creature(caster_ref))
        engine.drop_concentration_effects(caster_ref)
        engine.log(f"  {engine.name(ref)} свободен, заклинание кончается")
    return []
