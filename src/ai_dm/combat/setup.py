class CombatSetupError(ValueError):
    def __init__(self, codes):
        super().__init__("плохой старт боя: " + ", ".join(codes))
        self.codes = codes


def add_code(codes, code):
    if code not in codes:
        codes.append(code)


def check_zones(zones, codes):
    ids = [z.id for z in zones]
    names = [z.name for z in zones]
    if not 2 <= len(zones) <= 5:
        add_code(codes, "zones_count")
    if len(set(ids)) != len(ids):
        add_code(codes, "zone_ids_duplicate")
    if len(set(names)) != len(names):
        add_code(codes, "zone_names_duplicate")
    by_id = {z.id: z for z in zones}
    for zone in zones:
        for other_id in zone.adjacent:
            if other_id not in by_id:
                add_code(codes, "graph_unknown_zone")
            elif zone.id not in by_id[other_id].adjacent:
                add_code(codes, "graph_asymmetric")
    if not is_connected(zones, by_id):
        add_code(codes, "graph_disconnected")


def is_connected(zones, by_id) -> bool:
    # связность считаем по рёбрам в обе стороны, неизвестные зоны пропускаем
    if not zones:
        return True
    neighbours = {z.id: [] for z in zones}
    for zone in zones:
        for other_id in zone.adjacent:
            if other_id in by_id:
                neighbours[zone.id].append(other_id)
                neighbours[other_id].append(zone.id)
    seen = [zones[0].id]
    queue = [zones[0].id]
    while queue:
        current = queue.pop(0)
        for other_id in neighbours[current]:
            if other_id not in seen:
                seen.append(other_id)
                queue.append(other_id)
    return len(seen) == len(neighbours)


def check_participants(state, codes):
    zone_ids = [z.id for z in state.zones]
    refs = []
    for p in state.participants:
        if p.ref in refs:
            add_code(codes, "participant_duplicate")
        refs.append(p.ref)
        if p.zone_id is None:
            add_code(codes, "participant_unplaced")
        elif p.zone_id not in zone_ids:
            add_code(codes, "participant_zone_unknown")
        if p.group_id not in state.groups:
            add_code(codes, "group_unknown")


def check_groups(state, codes):
    for group_id, group in state.groups.items():
        members = [p for p in state.participants if p.group_id == group_id]
        has_enemies = any(p.side == "enemies" for p in members)
        if has_enemies and group.intent is None:
            add_code(codes, "group_intent_missing")
        if group.leader_id not in [p.ref for p in members]:
            add_code(codes, "group_leader_invalid")


def validate_start(state) -> list[str]:
    # все найденные ошибки, [] -- старт корректен
    codes = []
    check_zones(state.zones, codes)
    check_participants(state, codes)
    check_groups(state, codes)
    return codes
