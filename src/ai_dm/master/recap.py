from ai_dm.rules.knowledge import mentions, shorten_text

# потолок конспекта выпавших ходов сцены (знаков) и одной строки events
RECAP_MAX = 1200
RECAP_LINE_MAX = 120
REJECTED = ": отклонено ("


def dropped_turns(memory, scene, kept_seqs):
    # ходы текущей сцены, которых нет в recent_turns запроса (вытесненные и за окном)
    turns = memory.recent_turns
    return [t for t in turns if t.scene_id == scene.id and t.turn_seq not in kept_seqs]


def scene_recap(bundle, kept_seqs, *, max_chars):
    # конспект из состояния, без ИИ: какие ходы, кто в них упомянут, что движок исполнил;
    # None -- сцены нет или выпавших ходов нет
    scene = bundle.session.current_scene
    if scene is None:
        return None
    dropped = dropped_turns(bundle.memory, scene, kept_seqs)
    if not dropped:
        return None
    text = " ".join(t.narration for t in dropped).lower()
    npcs = sorted(
        n.name
        for n in bundle.world.npcs.values()
        if n.named and n.status == "alive" and mentions(n.name.lower(), text)
    )
    events = [
        shorten_text(f"t{t.turn_seq}: {line}", RECAP_LINE_MAX)
        for t in dropped
        for line in t.outcomes
        if REJECTED not in line
    ]
    # потолок max_chars -- на весь конспект: имена npcs и events; уходят старые события
    while events and sum(len(e) for e in events) + sum(len(n) for n in npcs) > max_chars:
        events.pop(0)
    first, last = dropped[0].turn_seq, dropped[-1].turn_seq
    span = f"t{first}" if first == last else f"t{first}–t{last}"
    return {"turns": f"{span} ({turns_word(len(dropped))})", "npcs": npcs, "events": events}


def turns_word(n):
    if n % 10 == 1 and n % 100 != 11:
        return f"{n} ход"
    if n % 10 in (2, 3, 4) and n % 100 not in (12, 13, 14):
        return f"{n} хода"
    return f"{n} ходов"
