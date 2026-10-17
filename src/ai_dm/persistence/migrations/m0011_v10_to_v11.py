import copy


def migrate_v10_to_v11(data: dict, context=None) -> dict:
    # схема v11: память и цели NPC, known_name, связи, услуги, журнал знаний героя, scene_mood,
    # pending_acts; NPC.relations_text переехал в NPC.notes
    data = copy.deepcopy(data)
    world = data.get("world", {})
    for npc in world.get("npcs", {}).values():
        old_text = npc.pop("relations_text", "")
        if not npc.get("notes"):
            npc["notes"] = old_text
        npc.setdefault("memory", [])
        npc.setdefault("goals", [])
        npc.setdefault("known_name", None)
        npc.setdefault("family", [])
        npc.setdefault("services", [])
    world.get("sim", {}).setdefault("pending_acts", [])
    for hero in data.get("heroes", []):
        hero.setdefault("family", [])
        hero.setdefault("knowledge", [])
    scene = data.get("session", {}).get("current_scene")
    if scene:
        scene.setdefault("scene_mood", "")
    return data
