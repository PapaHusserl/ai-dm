from ai_dm.combat import disarm
from ai_dm.combat.controllers import EngineTactics
from ai_dm.core.events import DomainEvent
from ai_dm.state.creature import ActiveEffect, Expiry


def sentient(engine, target) -> bool:
    cfg = engine.cfg.parley
    if not engine.monster_of(target):
        return False
    monster = engine.monster(target)
    return monster.abilities["int"] > cfg.min_int and monster.creature_type not in cfg.immune_types


def offend(engine, ref, target) -> None:
    # грубый провал «переходи к нам»: следующая атака цели по герою с преимуществом;
    # метка parley_offended нужна и после боя (отношение NPC падает)
    creature = engine.creature(target)
    creature.active_effects.append(ActiveEffect(id="parley_offended", source=ref, kind="flag"))
    creature.active_effects.append(
        ActiveEffect(
            id="parley_advantage", source=ref, kind="modifier",
            params={"target": "attack_roll", "mode": "advantage", "against": ref, "consume": True},
            expires=Expiry(kind="end_of_turn", owner=target),
        )
    )
    engine.log(f"  {engine.name(target)} оскорблён")


def apply_surrender(engine, ref, target, also="") -> list[DomainEvent]:
    # also="тоже " -- сдаётся по морали группы
    engine.part(target).status = "surrendered"
    engine.log(f"  {engine.name(target)} {also}сдаётся")
    disarm.surrender_drop(engine, target)
    return [DomainEvent(type="participant_surrendered", data={"id": target})]


def apply_flee(engine, ref, target, also="") -> list[DomainEvent]:
    engine.part(target).status = "fled"
    engine.log(f"  {engine.name(target)} {also}уходит")
    return [DomainEvent(type="participant_fled", data={"id": target})]


def apply_defect(engine, ref, target) -> list[DomainEvent]:
    p = engine.part(target)
    # исходная группа остаётся в метке: по ней перебежчик станет NPC мира
    flag = ActiveEffect(id="parley_defected", source=ref, kind="flag", params={"group": p.group_id})
    p.side = "heroes"
    p.controller = "engine"
    p.group_id = engine.part(ref).group_id
    p.intent = None
    engine.controllers[target] = EngineTactics(engine)
    engine.creature(target).active_effects.append(flag)
    engine.log(f"  {engine.name(target)} переходит на вашу сторону")
    return [DomainEvent(type="participant_defected", data={"id": target})]


def apply_waver(engine, ref, target) -> list[DomainEvent]:
    engine.creature(target).active_effects.append(
        ActiveEffect(id="wavering", source=ref, kind="flag")
    )
    engine.log(f"  {engine.name(target)} колеблется")
    return []


def apply_quarrel(engine, ref, target) -> list[DomainEvent]:
    # на один ход цели: метку снимает expire в конце её хода
    engine.creature(target).active_effects.append(
        ActiveEffect(
            id="quarreling", source=ref, kind="flag",
            expires=Expiry(kind="end_of_turn", owner=target),
        )
    )
    engine.log(f"  {engine.name(target)} ссорится со своими")
    return []


APPLY = {
    "surrender": apply_surrender, "flee": apply_flee, "defect": apply_defect,
    "waver": apply_waver, "quarrel": apply_quarrel,
}


def spread_morale(engine, ref, target, outcome) -> list[DomainEvent]:
    # сильный успех: раненые (HP ≤ 50 %) из группы цели, кто слышит переговоры, следуют за ней
    group_id = engine.part(target).group_id
    events = []
    for q in engine.state.participants:
        if q.ref == target or q.group_id != group_id or not engine.is_capable(q.ref):
            continue
        creature = engine.creature(q.ref)
        if creature.hp_current * 2 > creature.hp_max or not sentient(engine, q.ref):
            continue
        events += APPLY[outcome](engine, ref, q.ref, also="тоже ")
    return events


def apply_success(engine, ref, target, outcome, strong) -> list[DomainEvent]:
    # исход на цель; сильный успех «сдаться»/«отступить» ещё и мораль группы
    events = APPLY[outcome](engine, ref, target)
    if engine.cfg.parley.spread_morale and strong and outcome in ("surrender", "flee"):
        events += spread_morale(engine, ref, target, outcome)
    return events
