from ai_dm.state.world import Notice
from ai_dm.world_sim.candidates import OWNER_RANK, make_candidate, sort_key
from ai_dm.world_sim.verdicts import find_owner

NOT_PARTICIPATING = "герой не участвует: "


def condition_flags(condition) -> list[str]:
    # имена флагов в условии
    if condition.type == "flag":
        return [condition.name]
    if condition.type in ("all", "any"):
        return [name for item in condition.items for name in condition_flags(item)]
    if condition.type == "not":
        return condition_flags(condition.item)
    return []


def main_line(bundle) -> list[tuple]:
    # основная линия (Т-7): активные триггеры key: true владельцев key: true; у фракций,
    # богов и героя поля key нет -- они ключевые (триггеры героя -- его мотив);
    # (вид, владелец, триггер), порядок как у кандидатов
    world = bundle.world
    owners = [("god", g) for g in world.pantheon.values() if g.status == "alive"]
    owners += [("faction", f) for f in world.factions.values()]
    owners += [("npc", n) for n in world.npcs.values() if n.status == "alive" and n.key]
    owners += [("hero", h) for h in bundle.heroes if h.status == "active"]
    owners.sort(key=lambda item: (OWNER_RANK[item[0]], item[1].id))
    result = []
    for kind, owner in owners:
        for trigger in owner.opportunity:
            # сработавший на этой границе триггер ещё входит в линию (граница его только что снял)
            on_line = trigger.state == "active" or trigger.last_fired_at == world.clock.now_s
            if trigger.key and on_line:
                result.append((kind, owner, trigger))
    return result


def touched(bundle, line) -> bool:
    # касание основной линии за закрытую сцену: ключевой NPC в её локации или изменение флага,
    # на который ссылается условие триггера основной линии (с прошлой границы); на первой
    # границе (флаги ещё не запомнены) флаги только запоминаются
    world = bundle.world
    scene = bundle.session.current_scene
    names = sorted({name for _, _, trigger in line for name in condition_flags(trigger.if_)})
    seen = world.sim.nudge.flags_seen
    changed = any(name in seen and world.flags.get(name) != seen[name] for name in names)
    world.sim.nudge.flags_seen = {name: world.flags.get(name) for name in names}
    if changed:
        return True
    if scene is None or scene.location_id is None:
        return False
    return any(
        npc.status == "alive" and npc.key and npc.location_id == scene.location_id
        for npc in world.npcs.values()
    )


def contact_of(world, kind, owner) -> str:
    # NPC, который выходит на героя (ступень 2): сам владелец-NPC, первый живой член фракции
    # или слуга бога; нет -- пусто
    if kind == "npc":
        return owner.id
    if kind == "hero":
        return ""
    ids = owner.members if kind == "faction" else owner.servants
    for npc_id in ids:
        npc = world.npcs.get(npc_id)
        if npc is not None and npc.status == "alive":
            return npc.id
    return ""


def step(bundle, check) -> None:
    # граница сцены: счёт сцен без касания, ступени подталкивания (ТЗ 4); кандидат ступени 3
    # и пометка «герой не участвует» добавляются в check.candidates
    world = bundle.world
    nudge = world.sim.nudge
    scene = bundle.session.current_scene
    line = main_line(bundle)
    # слух и событие -- только про не-героев: линия из одного героя подталкивания не даёт
    targets = [item for item in line if item[0] != "hero"]
    if not targets:
        nudge.flags_seen = {}
        nudge.scenes_off_main = 0
        nudge.stage = 0
        nudge.contact_npc = ""
    elif touched(bundle, line):
        if scene is not None:
            scene.touched_main = True
        nudge.scenes_off_main = 0
        nudge.stage = 0
        nudge.contact_npc = ""
        nudge.waiting = True
    else:
        nudge.scenes_off_main += 1
        target = min(3, nudge.scenes_off_main // world.nudge_scenes)
        if target > nudge.stage:
            nudge.stage = target
            apply_stage(bundle, check, targets[0])
    if not nudge.waiting:
        mark_not_participating(bundle, check)


def apply_stage(bundle, check, first) -> None:
    world = bundle.world
    nudge = world.sim.nudge
    kind, owner, trigger = first
    now_s = world.clock.now_s
    if nudge.stage == 1:
        # слух
        world.notices.append(
            Notice(
                id=f"nudge_{now_s}_1", at_s=now_s, deliver_at_s=now_s, visibility="rumor",
                text="До тебя доходят слухи: где-то что-то затевается.", refs=[owner.id],
            )
        )
    elif nudge.stage == 2:
        # контакт: сигнал нарратору (master.prompt читает contact_npc)
        nudge.contact_npc = contact_of(world, kind, owner)
    else:
        # событие находит героя; мир перестаёт ждать
        ref = f"nudge:{owner.id}:{trigger.id}"
        candidate = make_candidate(
            "act", kind, owner, trigger.id, ref,
            condition_text=NOT_PARTICIPATING + "герой долго не касался основной линии",
            then="событие, связанное с этой линией, находит героя: " + trigger.then,
        )
        check.candidates = sorted(check.candidates + [candidate], key=sort_key)
        nudge.waiting = False


def mark_not_participating(bundle, check) -> None:
    # мир не ждёт героя: ключевые триггеры с нарративной частью уходят в world с пометкой
    for candidate in check.candidates:
        if candidate.kind != "verdict" or candidate.ref.startswith(("secret:", "event:")):
            continue
        if candidate.condition_text.startswith(NOT_PARTICIPATING):
            continue
        owner = find_owner(bundle, candidate)
        if owner is None or not getattr(owner, "key", True):
            continue
        trigger = next((t for t in owner.opportunity if t.id == candidate.item_id), None)
        if trigger is not None and trigger.key:
            candidate.condition_text = NOT_PARTICIPATING + candidate.condition_text
