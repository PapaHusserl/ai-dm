import copy


def migrate_v4_to_v5(data: dict, context=None) -> dict:
    # память этапа 4: источник выжимок, глава, свёрнутая в game_summary, сцена хода
    data = copy.deepcopy(data)
    memory = data.get("memory")
    if memory is None:
        return data
    for scene in memory.get("scenes", []):
        scene.setdefault("source", "pack")
    chapters = memory.get("chapters", [])
    for chapter in chapters:
        chapter.setdefault("source", "pack")
        chapter.setdefault("at_s", 0)
    if "game_summary_chapter" not in memory:
        last = 0
        if memory.get("game_summary"):
            last = max((c["number"] for c in chapters), default=0)
        memory["game_summary_chapter"] = last
    for turn in memory.get("recent_turns", []):
        turn.setdefault("scene_id", "")
    return data
