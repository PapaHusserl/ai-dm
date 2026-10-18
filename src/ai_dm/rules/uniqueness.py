def norm(name: str) -> str:
    return name.strip().casefold()


def name_taken(name: str, taken) -> bool:
    return any(norm(other) == norm(name) for other in taken)


def id_taken(world, heroes, new_id) -> bool:
    if new_id in world.npcs or new_id in world.factions or new_id in world.pantheon:
        return True
    if new_id in world.locations:
        return True
    return any(hero.id == new_id for hero in heroes)


def check_npc(world, npc, heroes) -> list[str]:
    conflicts = []
    if id_taken(world, heroes, npc.id):
        conflicts.append(f"id {npc.id!r} уже занят (NPC, фракция, бог, локация или герой)")
    if npc.named and name_conflict(world, heroes, npc.name):
        conflicts.append(f"имя {npc.name!r} уже занято (NPC, бог, фракция или герой)")
    return conflicts


def name_conflict(world, heroes, new_name) -> bool:
    # имя совпадает с именем именованного NPC, бога, фракции или героя (без регистра)
    name = norm(new_name)
    taken = [other.name for other in world.npcs.values() if other.named]
    taken += [god.name for god in world.pantheon.values()]
    taken += [faction.name for faction in world.factions.values()]
    taken += [hero.name for hero in heroes]
    return any(norm(other) == name for other in taken)


def check_location(world, location, heroes) -> list[str]:
    conflicts = []
    if id_taken(world, heroes, location.id):
        conflicts.append(f"id {location.id!r} уже занят (NPC, фракция, бог, локация или герой)")
    name = norm(location.name)
    for other in world.locations.values():
        if other.parent_id == location.parent_id and norm(other.name) == name:
            conflicts.append(f"в этом месте уже есть локация с именем {location.name!r}")
            break
    return conflicts


def check_faction(world, faction, heroes) -> list[str]:
    conflicts = []
    if id_taken(world, heroes, faction.id):
        conflicts.append(f"id {faction.id!r} уже занят (NPC, фракция, бог, локация или герой)")
    name = norm(faction.name)
    taken = [other.name for other in world.factions.values()]
    taken += [god.name for god in world.pantheon.values()]
    taken += [npc.name for npc in world.npcs.values() if npc.named]
    taken += [hero.name for hero in heroes]
    if any(norm(other) == name for other in taken):
        conflicts.append(f"имя {faction.name!r} уже занято (NPC, бог, фракция или герой)")
    return conflicts


def check_god(world, god, heroes) -> list[str]:
    conflicts = []
    if id_taken(world, heroes, god.id):
        conflicts.append(f"id {god.id!r} уже занят (NPC, фракция, бог, локация или герой)")
    name = norm(god.name)
    taken = [other.name for other in world.pantheon.values()]
    taken += [faction.name for faction in world.factions.values()]
    taken += [npc.name for npc in world.npcs.values() if npc.named]
    taken += [hero.name for hero in heroes]
    if any(norm(other) == name for other in taken):
        conflicts.append(f"имя {god.name!r} уже занято (NPC, бог, фракция или герой)")
    return conflicts


def check_hero(world, hero, heroes) -> list[str]:
    # heroes -- остальные герои мира (сам hero в списке не нужен)
    conflicts = []
    if id_taken(world, heroes, hero.id):
        conflicts.append(f"id {hero.id!r} уже занят (NPC, фракция, бог, локация или герой)")
    taken = [npc.name for npc in world.npcs.values() if npc.named]
    taken += [god.name for god in world.pantheon.values()]
    taken += [faction.name for faction in world.factions.values()]
    taken += [other.name for other in heroes]
    if name_taken(hero.name, taken):
        conflicts.append(f"имя {hero.name!r} уже занято (NPC, бог, фракция или герой)")
    return conflicts
