from ai_dm.rules import goals
from ai_dm.rules.triggers_eval import is_ready


def mentions(bundle) -> str:
    # варианты ответа и ввод/рассказ последних ходов одним текстом, без регистра
    parts = list(bundle.session.offered_choices)
    for turn in bundle.memory.recent_turns:
        parts += [turn.player_input, turn.narration]
    return "\n".join(parts).lower()


def nearby_locations(world, place):
    # текущая локация и связанные с ней в любую сторону (для travel_to); расстояние в метрах
    result = [{"id": place.id, "name": place.name, "distance_m": 0}]
    distances = {c.to: c.distance_m for c in place.connections}
    for other in world.locations.values():
        for c in other.connections:
            if c.to == place.id and other.id not in distances:
                distances[other.id] = c.distance_m
    for location_id in sorted(distances):
        if location_id in world.locations:
            name = world.locations[location_id].name
            distance = distances[location_id]
            result.append({"id": location_id, "name": name, "distance_m": distance})
    return result


def npc_reason_set(bundle, npc, location_id, text, nearby_ids) -> set[str]:
    reasons = set()
    if npc.follows is not None and npc.follows == bundle.manifest.current_hero_id:
        reasons.add("with_hero")
    if location_id is not None and npc.location_id == location_id:
        reasons.add("here")
    if any(is_ready(t, bundle.world.clock.now_s) for t in npc.opportunity):
        reasons.add("active")
    if npc.key:
        reasons.add("key")
    if npc.name != "" and npc.name.lower() in text:
        reasons.add("said")
    if npc.location_id in nearby_ids and npc.location_id != location_id:
        reasons.add("nearby")
    if npc.trade is not None or npc.services:
        reasons.add("merchant")
    return reasons


def npc_reasons(bundle, nearby_ids=()) -> dict[str, set[str]]:
    # именованные живые NPC и причины релевантности: with_hero (идёт с героем), here (в локации
    # героя), active (активный триггер), key (ключевой), said (упомянут в offered_choices /
    # recent_turns по name), nearby (в соседней локации из nearby_ids), merchant (торговец: цель
    # визита, 132)
    location_id = None
    for hero in bundle.heroes:
        if hero.id == bundle.manifest.current_hero_id:
            location_id = hero.location_id
    text = mentions(bundle)
    result = {}
    for npc in bundle.world.npcs.values():
        if not (npc.named or goals.has_active_goal(npc)) or npc.status != "alive":
            continue
        reasons = npc_reason_set(bundle, npc, location_id, text, nearby_ids)
        if reasons:
            result[npc.id] = reasons
    return result


def relevant_npcs(bundle) -> list[str]:
    # то же без причины nearby: вход роли world; по id
    return sorted(npc_reasons(bundle))


def rank_npcs(reasons):
    # (неустранимые, вытесняемые): вытесняются said, затем key, затем nearby, затем merchant; id
    # по возрастанию. У NPC с несколькими причинами -- самая защищённая
    fixed = []
    order = {"said": 0, "key": 1, "nearby": 2, "merchant": 3}
    ranked = []
    for npc_id in sorted(reasons):
        found = reasons[npc_id]
        if found & {"with_hero", "here", "active"}:
            fixed.append(npc_id)
        else:
            ranked.append((max(order[r] for r in found), npc_id))
    return fixed, [npc_id for _, npc_id in sorted(ranked)]
