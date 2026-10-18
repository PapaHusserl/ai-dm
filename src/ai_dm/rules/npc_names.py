def name_hidden(npc) -> bool:
    # имя NPC движка скрыто от игрока, пока оно не прозвучало (known_name); пак и ai -- публично
    return npc.origin == "engine" and npc.known_name is None


def shown_name(npc) -> str:
    # имя для игрока и журнала: до знакомства -- вид существа (метка из боя)
    if npc.origin != "engine":
        return npc.name
    if npc.known_name is not None:
        return npc.known_name
    return (npc.combat or {}).get("label", npc.name)
