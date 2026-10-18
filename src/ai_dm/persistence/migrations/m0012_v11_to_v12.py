import copy


def migrate_v11_to_v12(data: dict, context=None) -> dict:
    # схема v12: WorldSim.goals_checked_s -- время последней проверки триггеров целей NPC (Ж2)
    data = copy.deepcopy(data)
    data.get("world", {}).get("sim", {}).setdefault("goals_checked_s", None)
    return data
