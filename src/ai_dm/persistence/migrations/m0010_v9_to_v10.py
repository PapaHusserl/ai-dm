import copy


def migrate_v9_to_v10(data: dict, context=None) -> dict:
    # схема v10: итоги инструментов и дельта денег в ходах памяти, отметка длинного отдыха героя
    data = copy.deepcopy(data)
    for turn in data.get("memory", {}).get("recent_turns", []):
        turn.setdefault("outcomes", [])
        turn.setdefault("money_delta_cp", 0)
    for hero in data.get("heroes", []):
        hero.setdefault("long_rest_end_s", None)
    return data
