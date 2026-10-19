from ai_dm.combat import death_burst, monster_traits
from ai_dm.combat.actions import parley
from ai_dm.core.events import DomainEvent
from ai_dm.rules import death_saves
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.damage import concentration_check
from ai_dm.rules.mortality_guard import remove_creature
from ai_dm.rules.results import Rejected
from ai_dm.state.combat import DecisionPoint
from ai_dm.state.creature import AppliedCondition, DeathSaves

INTENTS = ("kill", "capture", "rob", "drive_off", "spare")
# подписи намерений в логе
INTENT_WORDS = {
    "kill": "убить", "capture": "взять в плен", "rob": "ограбить", "drive_off": "прогнать",
    "spare": "пощадить",
}
INTENT_OPTIONS = ["keep"] + [f"intent:{name}" for name in INTENTS]


def hero_died_event(hero) -> DomainEvent:
    # mark_dead уже сделан правилами (спасбросок / урон), событие собираем по записи о смерти
    data = {"id": hero.id, "cause": hero.death.cause, "by": hero.death.by}
    return DomainEvent(type="hero_died", data=data)


def intervention_event(hero) -> DomainEvent:
    # бог уже вмешался (divine.try_intervention): герой на 1 HP, долг записан
    data = {"id": hero.id, "god": hero.divine.intervention_god}
    return DomainEvent(type="divine_intervention", data=data)


def death_cause(by) -> str:
    # причина смерти: от чужого удара (goal) или от опасности без автора (hazard)
    return "hazard" if by is None else "goal"


def add_unconscious(creature) -> None:
    if not any(c.id == "unconscious" and c.source == "0_hp" for c in creature.conditions):
        creature.conditions.append(AppliedCondition(id="unconscious", source="0_hp"))


def wake_sleeping(engine, target_ref, dealt) -> None:
    # урон будит: «без сознания» не от 0 HP (сонный яд) снимается, отравление остаётся, цель лежит
    creature = engine.creature(target_ref)
    asleep = [c for c in creature.conditions if c.id == "unconscious" and c.source != "0_hp"]
    if not asleep or dealt.final <= 0:
        return
    creature.conditions = [c for c in creature.conditions if c not in asleep]
    engine.log(f"  {engine.name(target_ref)} просыпается от боли")
    engine.impose(target_ref, AppliedCondition(id="prone", source=asleep[0].source))


def after_damage(
    engine, target_ref, dealt, attacker_ref, *, crit=False, nonlethal=False
) -> list[DomainEvent]:
    # вызывается после apply_damage: сон, 0 HP, смерть, концентрация
    wake_sleeping(engine, target_ref, dealt)
    if target_ref in engine.heroes:
        return hero_damaged(engine, target_ref, dealt, attacker_ref, crit)
    if monster_traits.endures(engine, target_ref, dealt, crit):
        return []
    return monster_damaged(engine, target_ref, dealt, attacker_ref, nonlethal)


# монстры и NPC

def monster_damaged(engine, ref, dealt, attacker_ref, nonlethal) -> list[DomainEvent]:
    p = engine.part(ref)
    creature = engine.creature(ref)
    if p.status == "dead" or creature.hp_current > 0 or dealt.final == 0:
        return []
    if p.status == "down" and nonlethal:
        return []
    if nonlethal:
        # без сознания, не убит
        end_concentration(creature)
        add_unconscious(creature)
        p.status = "down"
        engine.log(f"  {engine.name(ref)} без сознания")
        return []
    return kill_monster(engine, ref, attacker_ref)


def kill_monster(engine, ref, attacker_ref) -> list[DomainEvent]:
    p = engine.part(ref)
    p.status = "dead"
    p.last_hit_by = attacker_ref
    end_concentration(engine.creature(ref))
    engine.log(f"  {engine.name(ref)} убит")
    cause = death_cause(attacker_ref)
    if ref in engine.world.npcs:
        # именованный NPC: смерть только через страж причин
        events = remove_creature(engine.world, ref, "dead", cause, by=attacker_ref)
        if isinstance(events, Rejected):
            raise ValueError(f"смерть NPC {ref!r} отклонена: {events.reason}")
        return events + death_burst.explode(engine, ref)
    data = {"id": ref, "monster_id": engine.part(ref).monster_id, "by": attacker_ref}
    return [DomainEvent(type="monster_died", data=data)] + death_burst.explode(engine, ref)


# герои

def hero_damaged(engine, ref, dealt, attacker_ref, crit) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    p = engine.part(ref)
    if hero.status == "dead":
        return []
    had_concentration = hero.creature.concentration is not None
    held = engine.concentration_targets(ref)
    if attacker_ref is not None:
        p.last_hit_by = attacker_ref
    cause = death_cause(attacker_ref)
    now_s = engine.world.clock.now_s
    events = []
    if dealt.dropped:
        if drops_to_death_saves(engine, ref, attacker_ref):
            outcome = death_saves.after_damage(
                hero, dealt, crit=crit, cause=cause, by=attacker_ref, now_s=now_s,
                intervene=engine.intervene,
            )
        else:
            outcome = knock_out(hero)
        events += settle(engine, ref, outcome)
    elif dealt.was_down:
        # удар по лежащему: последним ударил его автор
        if attacker_ref is not None:
            engine.state.defeat_group_id = engine.part(attacker_ref).group_id
        outcome = death_saves.after_damage(
            hero, dealt, crit=crit, cause=cause, by=attacker_ref, now_s=now_s,
            intervene=engine.intervene,
        )
        events += settle(engine, ref, outcome)
    elif hero.creature.concentration is not None and dealt.final > 0:
        result = concentration_check(hero, dealt.final, engine.registry, engine.rng)
        engine.log(f"  Концентрация ({result.log.text.replace(': ', '): ', 1)}")
        if hero.creature.concentration is not None:
            engine.log("  концентрация удержана")
    if had_concentration and hero.creature.concentration is None:
        engine.log(f"  {engine.name(ref)} теряет концентрацию{lost_text(engine, held)}")
        engine.drop_concentration_effects(ref)
    return events


def lost_text(engine, held) -> str:
    # « — «Метка охотника» снята (цель: Стражник)»
    parts = []
    for spell_id, names in held.items():
        name = engine.registry.get("spell", spell_id).name
        parts.append(f"«{name}» снята (цель: {', '.join(names)})")
    return "".join(" — " + part for part in parts)


def settle(engine, ref, outcome) -> list[DomainEvent]:
    # outcome из death_saves.after_damage / knock_out:
    # dead | saved | down | down_stable | failure | none
    hero = engine.heroes[ref]
    p = engine.part(ref)
    if outcome == "saved":
        p.status = "active"
        return [intervention_event(hero)]
    if outcome == "dead":
        p.status = "dead"
        engine.log(f"  {engine.name(ref)} погибает")
        return [hero_died_event(hero)]
    if outcome == "down":
        p.status = "down"
        engine.log(f"  {engine.name(ref)} без сознания, умирает")
    if outcome == "down_stable":
        p.status = "down"
        engine.log(f"  {engine.name(ref)} выбывает из боя без сознания")
    if outcome == "failure":
        engine.log(f"  {engine.name(ref)}: провал спасброска от смерти")
    return []


def drops_to_death_saves(engine, ref, attacker_ref) -> bool:
    # намерение группы атакующего; перед применением лидер может передумать
    if attacker_ref is None:
        # падение от опасности: группы последнего удара нет
        engine.state.defeat_group_id = None
        return True
    group_id = engine.part(attacker_ref).group_id
    engine.state.defeat_group_id = group_id
    group = engine.state.groups[group_id]
    ask_leader(engine, group, ref, attacker_ref)
    return group.intent is None or group.intent == "kill"


def ask_leader(engine, group, hero_ref, attacker_ref) -> None:
    leader_ref = group.leader_id
    if not parley.leads(engine, leader_ref, engine.part(attacker_ref).group_id):
        return
    point = DecisionPoint(
        kind="intent_reconsider", actor=leader_ref, options=list(INTENT_OPTIONS),
        subject=hero_ref, attacker=attacker_ref,
    )
    choice = engine.controllers[leader_ref].choose([], point)
    if choice == "keep":
        return
    if choice not in INTENT_OPTIONS:
        raise ValueError(f"нет такого решения о намерении: {choice!r}")
    group.intent = choice.split(":")[1]
    engine.log(f"  {engine.name(leader_ref)} меняет намерение: {INTENT_WORDS[group.intent]}")


def knock_out(hero) -> str:
    # не kill: герой выбывает без спасбросков от смерти
    end_concentration(hero.creature)
    add_unconscious(hero.creature)
    hero.creature.death_saves = DeathSaves(stable=True)
    return "down_stable"


def stabilize_all(engine) -> None:
    # победа союзников: умирающие герои стабилизируются
    for p in engine.state.participants:
        hero = engine.heroes.get(p.ref)
        if hero is None or p.side != "heroes" or p.status != "down" or hero.status != "active":
            continue
        if death_saves.is_dying(hero.creature):
            hero.creature.death_saves = DeathSaves(stable=True)


def death_save(engine, ref) -> list[DomainEvent]:
    # в начале хода упавшего героя: спасбросок от смерти (контроллер не спрашивается)
    hero = engine.heroes.get(ref)
    p = engine.part(ref)
    if hero is None or p.status != "down" or hero.status != "active":
        return []
    if not death_saves.is_dying(hero.creature):
        return []
    by = p.last_hit_by
    cause = death_cause(by)
    result = death_saves.roll_death_save(
        hero, engine.registry, engine.rng, now_s=engine.world.clock.now_s, cause=cause, by=by,
        intervene=engine.intervene,
    )
    engine.log(f"{engine.name(ref)}: спасбросок от смерти: {result}")
    events = [DomainEvent(type="death_save", data={"id": ref, "result": result})]
    if result == "dead":
        p.status = "dead"
        events.append(hero_died_event(hero))
    if result == "revived":
        p.status = "active"
    if result == "saved":
        p.status = "active"
        events.append(intervention_event(hero))
    return events
