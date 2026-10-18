from ai_dm.combat.engine import participant_name
from ai_dm.rules.npc_memory import remember
from ai_dm.rules.npc_names import shown_name
from ai_dm.rules.trade import DAY_S
from ai_dm.state.relations import NPC_EVENT_TEXT_MAX, NpcEvent, NpcGoal
from ai_dm.state.triggers import Trigger

PREFIX = "goal:"
# нарративный остаток условия триггера-спутника по виду цели: его подтверждает роль world
NARRATIVE = {
    "revenge": "мститель может найти героя и отомстить",
    "life_debt": "обязанный жизнью может найти повод отплатить герою",
    "debt": "подошло время напомнить о долге",
    "gratitude": "благодарный может найти повод отплатить герою",
    "love": "влюблённый ищет встречи с героем",
    "rivalry": "соперник может дать о себе знать",
}


def trigger_id(kind, target) -> str:
    return f"{PREFIX}{kind}:{target}"


def is_goal_trigger(trigger) -> bool:
    return trigger.id.startswith(PREFIX)


def has_active_goal(npc) -> bool:
    return any(g.status == "active" for g in npc.goals)


def find_active(npc, kind, target):
    return next(
        (g for g in npc.goals if g.kind == kind and g.target == target and g.status == "active"),
        None,
    )


def skipped(trigger, goals_due) -> bool:
    # триггер цели пропускается, пока проверка целей не подошла
    return is_goal_trigger(trigger) and not goals_due


def companion(goal, alive) -> Trigger:
    # триггер-спутник цели: структурная часть (цель жива) + нарративный остаток
    return Trigger.model_validate(
        {
            "id": trigger_id(goal.kind, goal.target),
            "if": {"all": [alive, {"narrative": NARRATIVE[goal.kind]}]},
            "then": goal.text, "once": True,
        }
    )


def put_goal(npc, goal, alive) -> NpcGoal | None:
    # None -- такая цель уже активна; спутник закрытой цели с тем же id заменяется новым
    if find_active(npc, goal.kind, goal.target) is not None:
        return None
    npc.goals.append(goal)
    tid = trigger_id(goal.kind, goal.target)
    npc.opportunity = [t for t in npc.opportunity if t.id != tid]
    npc.opportunity.append(companion(goal, alive))
    return goal


def add_goal(npc, kind, target, text, now_s) -> NpcGoal | None:
    # цель на героя: спутник работает, пока герой жив
    goal = NpcGoal(kind=kind, target=target, text=text, since_s=now_s)
    return put_goal(npc, goal, {"not": {"hero_dead": True}})


def add_npc_goal(npc, kind, target, text, now_s) -> NpcGoal | None:
    # цель на NPC: спутник работает, пока мишень жива
    goal = NpcGoal(kind=kind, target=target, text=text, since_s=now_s)
    return put_goal(npc, goal, {"npc_status": {"id": target, "is": "alive"}})


def disable_companion(npc, kind, target) -> None:
    tid = trigger_id(kind, target)
    for trigger in npc.opportunity:
        if trigger.id == tid:
            trigger.state = "disabled"


def close_goal(npc, kind, target, status) -> NpcGoal | None:
    # status: done | dropped; None -- активной цели нет
    goal = find_active(npc, kind, target)
    if goal is None:
        return None
    goal.status = status
    disable_companion(npc, kind, target)
    return goal


def mark_fired(npc, trigger) -> None:
    # сработал триггер-спутник -- цель исполнена
    if not is_goal_trigger(trigger):
        return
    _, kind, target = trigger.id.split(":", 2)
    goal = find_active(npc, kind, target)
    if goal is not None:
        goal.status = "done"


def target_gone(world, heroes, target) -> bool:
    if target in world.npcs:
        return world.npcs[target].status != "alive"
    hero = next((h for h in heroes if h.id == target), None)
    return hero is not None and hero.status == "dead"


def sweep(world, heroes) -> None:
    # цели умершего (ушедшего) носителя или мёртвой (ушедшей) мишени закрываются как dropped
    for npc in world.npcs.values():
        for goal in npc.goals:
            if goal.status != "active":
                continue
            if npc.status != "alive" or target_gone(world, heroes, goal.target):
                close_goal(npc, goal.kind, goal.target, "dropped")


def due(sim, now_s, every_days) -> bool:
    # как у богов: первая проверка сразу, дальше через every_days после предыдущей
    if sim.goals_checked_s is None:
        return True
    return now_s - sim.goals_checked_s >= every_days * DAY_S


def avengers(world, hero, ref, groups, fighters) -> list:
    # живые NPC, которые мстят за убитого: родня (FamilyLink на ref) и отряд (общая группа,
    # отношение к герою <= 0, не идёт с героем); участники боя не в счёт
    found = []
    for npc in sorted(world.npcs.values(), key=lambda n: n.id):
        if npc.status != "alive" or npc.id in fighters or npc.id == ref:
            continue
        if is_kin(npc, ref) or is_squad(npc, hero, groups):
            found.append(npc)
    return found


def is_kin(npc, ref) -> bool:
    return any(link.ref == ref and link.ref_kind == "npc" for link in npc.family)


def is_squad(npc, hero, groups) -> bool:
    return bool(set(groups) & set(npc.groups)) and npc.follows != hero.id and npc.attitude <= 0


def on_kill(bundle, hero, part, state, cfg) -> list:
    # герой убил участника боя part: мстители получают цель revenge и память kin_killed
    # (если есть сцена); имя -- как в бою, участники боя мстителями не бывают.
    # Убийца другой (напарник, иной участник) -- мести нет; смерть без убийцы -- на счёт героя
    if part.last_hit_by not in (None, hero.id):
        return []
    now_s = bundle.world.clock.now_s
    scene = bundle.session.current_scene
    npc = bundle.world.npcs.get(part.ref)
    name = shown_name(npc) if npc is not None else participant_name(state, {}, part.ref)
    fighters = {p.ref for p in state.participants}
    text = f"мстит герою за гибель: {name}"
    created = []
    for npc in avengers(bundle.world, hero, part.ref, [part.group_id], fighters):
        if add_goal(npc, "revenge", hero.id, text, now_s) is None:
            continue
        created.append(npc)
        if scene is not None:
            text_kin = f"герой убил: {name}"[:NPC_EVENT_TEXT_MAX]
            event = NpcEvent(kind="kin_killed", turn_seq=bundle.session.turn_seq, text=text_kin)
            remember(npc, scene, event, cfg.npc_memory)
    return created
