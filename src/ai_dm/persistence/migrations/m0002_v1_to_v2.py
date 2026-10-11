import copy


def is_turn(item) -> bool:
    # запись формы TurnRecord этапа 2 (литералы: миграция заморожена в v2)
    if not isinstance(item, dict):
        return False
    if not set(item) <= {"turn_seq", "at_s", "player_input", "narration", "requests", "rolls"}:
        return False
    for key in ("turn_seq", "at_s"):
        if type(item.get(key)) is not int:
            return False
    for key in ("player_input", "narration"):
        if not isinstance(item.get(key), str):
            return False
    for key in ("requests", "rolls"):
        if key in item:
            value = item[key]
            if not isinstance(value, list) or not all(isinstance(x, str) for x in value):
                return False
    return True


def migrate_v1_to_v2(data: dict, context=None) -> dict:
    # сцена этапа 1 -- голый dict, настоящих сцен не было: сбрасывается в None;
    # turn_seq / offered_choices; в recent_turns остаются только записи формы TurnRecord
    data = copy.deepcopy(data)
    session = data["session"]
    session["current_scene"] = None
    session.setdefault("turn_seq", 0)
    session.setdefault("offered_choices", [])
    turns = []
    for item in data["memory"]["recent_turns"]:
        if is_turn(item):
            item.setdefault("requests", [])
            item.setdefault("rolls", [])
            turns.append(item)
    data["memory"]["recent_turns"] = turns
    return data
