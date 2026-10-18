def looks_like_kind(registry, npc, name) -> bool:
    # имя совпадает с видом существа: меткой боя (с номером и без) или названием монстра реестра
    wanted = name.strip().casefold()
    label = (npc.combat or {}).get("label", "").strip().casefold()
    kinds = {label, label.rstrip("0123456789 ")}
    kinds |= {monster.name.strip().casefold() for monster in registry.all("monster")}
    kinds.discard("")
    return wanted in kinds


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
