from ai_dm.state.relations import WARM_KINDS, NpcSceneMemory


def effective_weight(entry, cfg):
    # вес для вытеснения: тёплая сцена -- не ниже warm_min_weight, хранимый weight не меняется
    warm = any(e.kind in WARM_KINDS for e in entry.events)
    return max(entry.weight, cfg.warm_min_weight if warm else 0)


def evict(npc, cfg):
    # убрать и вернуть запись с наименьшим (эффективный вес, at_s)
    victim = min(npc.memory, key=lambda s: (effective_weight(s, cfg), s.at_s))
    npc.memory.remove(victim)
    return victim


def has_kind(npc, scene, kind):
    # в записи этой сцены уже есть событие этого вида
    entry = scene_entry(npc, scene)
    return entry is not None and any(e.kind == kind for e in entry.events)


def scene_entry(npc, scene):
    return next((m for m in npc.memory if m.scene_id == scene.id), None)


def events_full(npc, scene, cfg):
    # в записи этой сцены уже максимум событий
    entry = scene_entry(npc, scene)
    return entry is not None and len(entry.events) >= cfg.max_events_per_scene


def remember(npc, scene, event, cfg):
    # событие в память NPC о герое: в запись сцены или в новую (она входит всегда; при полной
    # памяти уходит запись с наименьшим весом); лимит событий сцены -- None, иначе запись сцены
    entry = scene_entry(npc, scene)
    if entry is None:
        if len(npc.memory) >= cfg.max_scenes:
            evict(npc, cfg)
        entry = NpcSceneMemory(
            scene_id=scene.id, at_s=scene.started_at_s,
            weight=scene.attitude_spent.get(npc.id, 0), events=[event],
        )
        npc.memory.append(entry)
        return entry
    if len(entry.events) >= cfg.max_events_per_scene:
        return None
    entry.events.append(event)
    return entry


def refresh_weight(npc, scene):
    # вес записи сцены -- сколько сцена изменила отношения NPC (по модулю)
    for item in npc.memory:
        if item.scene_id == scene.id:
            item.weight = scene.attitude_spent.get(npc.id, 0)


def memory_data(npc):
    # память для промпта: сцены по времени, в них события
    return [
        {
            "scene_id": s.scene_id, "at_s": s.at_s, "weight": s.weight,
            "events": [{"kind": e.kind, "turn_seq": e.turn_seq, "text": e.text} for e in s.events],
        }
        for s in sorted(npc.memory, key=lambda s: s.at_s)
    ]


def memory_last(npc):
    # последнее событие последней по времени сцены или None
    if not npc.memory:
        return None
    event = max(npc.memory, key=lambda s: s.at_s).events[-1]
    return {"kind": event.kind, "text": event.text}


def goals_data(npc):
    return [
        {"kind": g.kind, "target": g.target, "text": g.text}
        for g in npc.goals if g.status == "active"
    ]
