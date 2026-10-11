import copy


def migrate_v0_to_v1(data: dict, context=None) -> dict:
    # герой v0 лежит одним "hero"; в v1 -- список heroes, chronicle, memory, pantheon, tone
    data = copy.deepcopy(data)
    hero = data.pop("hero", None)
    data["heroes"] = [hero] if hero is not None else []
    data["manifest"]["heroes"] = [h["id"] for h in data["heroes"]]
    data.setdefault("chronicle", {"entries": []})
    data.setdefault(
        "memory", {"scenes": [], "chapters": [], "game_summary": "", "recent_turns": []}
    )
    data["world"].setdefault("pantheon", {})
    data["world"].setdefault("tone", {
        "mood": "",
        "violence": "",
        "horror": "",
        "romance": "",
        "language": "",
        "hard_limits": [],
        "soft_limits": [],
    })
    return data
