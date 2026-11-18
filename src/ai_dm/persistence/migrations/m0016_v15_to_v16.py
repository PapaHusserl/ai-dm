import copy

# часы работы торговцев при подъёме (М0, решения 42, 59); конфиг миграция не читает
TRADER_HOURS = {"open_hour": 8, "close_hour": 16}


def migrate_v15_to_v16(data: dict, context=None) -> dict:
    # схема v16 (М0 П1): рёбрам kind="road" и needs_transport=False; торговцам часы 8-16;
    # остальные поля -- значения по умолчанию
    data = copy.deepcopy(data)
    world = data.get("world", {})
    for location in world.get("locations", {}).values():
        for edge in location.get("connections", []):
            edge.setdefault("kind", "road")
            edge.setdefault("needs_transport", False)
    for npc in world.get("npcs", {}).values():
        if npc.get("trade") and npc.get("hours") is None:
            npc["hours"] = dict(TRADER_HOURS)
    return data
