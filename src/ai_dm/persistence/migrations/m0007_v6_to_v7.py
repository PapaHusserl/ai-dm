import copy


def migrate_v6_to_v7(data: dict, context) -> dict:
    # торговля: у NPC появляется trade (из пака по id, context.npc_trade), у сцены -- счётчики
    data = copy.deepcopy(data)
    world = data.get("world")
    npc_trade = context.npc_trade
    if npc_trade is None:
        context.report.append("пак не загружен — торговцы пака не проставлены")
        npc_trade = {}
    if world is not None:
        for npc_id, npc in world.get("npcs", {}).items():
            if npc.get("trade") is None and npc_id in npc_trade:
                npc["trade"] = {"kind": npc_trade[npc_id]}
            npc.setdefault("trade", None)
    scene = data.get("session", {}).get("current_scene")
    if scene is not None:
        scene.setdefault("trades", 0)
        scene.setdefault("merchants_created", 0)
    return data
