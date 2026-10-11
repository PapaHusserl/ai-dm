from types import SimpleNamespace

from pydantic import BaseModel, Field

from ai_dm.campaign.loader import entity_refs
from ai_dm.rules.uniqueness import check_faction, check_god, check_location, check_npc
from ai_dm.state.world import NPC, Faction, GlobalEvent, God, Location


class Conflict(BaseModel):
    file: str
    kind: str
    id: str
    name: str
    reason: str

    def line(self) -> str:
        return f"{self.file}: {self.kind} {self.id!r} ({self.name}): {self.reason}"


class Accepted(BaseModel):
    # сущности пака, прошедшие проверку, в порядке файлов
    locations: list[Location] = Field(default_factory=list)
    pantheon: list[God] = Field(default_factory=list)
    factions: list[Faction] = Field(default_factory=list)
    npcs: list[NPC] = Field(default_factory=list)
    events: list[GlobalEvent] = Field(default_factory=list)


def collect_conflicts(world, heroes, pack) -> tuple[Accepted, list[Conflict]]:
    # сущности добавляются по одной: локации, боги, фракции, NPC; конфликтная не загружается.
    # Сущность, ссылающаяся на отброшенную, тоже отбрасывается (по кругу, пока есть такие)
    current = SimpleNamespace(
        npcs=dict(world.npcs), factions=dict(world.factions), pantheon=dict(world.pantheon),
        locations=dict(world.locations),
    )
    existing = {
        "location": world.locations, "god": world.pantheon, "faction": world.factions,
        "npc": world.npcs,
    }
    accepted = Accepted(events=list(pack.events))
    conflicts = []
    dropped = set()

    def reject(file, kind, id, name, reasons):
        conflicts.append(
            Conflict(file=file, kind=kind, id=id, name=name, reason="; ".join(reasons))
        )
        # сущность мира с этим id не отброшена: ссылки на неё допустимы
        if id not in existing.get(kind, {}):
            dropped.add((kind, id))

    for location in pack.locations:
        reasons = check_location(current, location, heroes)
        if reasons:
            reject("locations.yaml", "location", location.id, location.name, reasons)
        else:
            current.locations[location.id] = location
            accepted.locations.append(location)
    for god in pack.pantheon:
        reasons = check_god(current, god, heroes)
        if reasons:
            reject("pantheon.yaml", "god", god.id, god.name, reasons)
        else:
            current.pantheon[god.id] = god
            accepted.pantheon.append(god)
    for faction in pack.factions:
        reasons = check_faction(current, faction, heroes)
        if reasons:
            reject("factions.yaml", "faction", faction.id, faction.name, reasons)
        else:
            current.factions[faction.id] = faction
            accepted.factions.append(faction)
    for npc in pack.npcs:
        reasons = check_npc(current, npc, heroes)
        if reasons:
            reject("npcs.yaml", "npc", npc.id, npc.name, reasons)
        else:
            current.npcs[npc.id] = npc
            accepted.npcs.append(npc)

    groups = [
        ("location", "locations.yaml", accepted.locations),
        ("god", "pantheon.yaml", accepted.pantheon),
        ("faction", "factions.yaml", accepted.factions),
        ("npc", "npcs.yaml", accepted.npcs),
        ("event", "events.yaml", accepted.events),
    ]
    changed = True
    while changed:
        changed = False
        for kind, file, entities in groups:
            for entity in list(entities):
                refs = entity_refs(kind, entity)
                bad = [
                    ref for field, target, ref in refs
                    if field != "connections" and (target, ref) in dropped
                ]
                if bad:
                    entities.remove(entity)
                    name = getattr(entity, "name", entity.id)
                    reject(file, kind, entity.id, name, [f"ссылается на отброшенную {bad[0]}"])
                    changed = True
    # связи с отброшенными локациями не отбрасывают локацию, а просто убираются
    for number, location in enumerate(accepted.locations):
        links = [c for c in location.connections if ("location", c.to) not in dropped]
        if len(links) != len(location.connections):
            accepted.locations[number] = location.model_copy(update={"connections": links})
    return accepted, conflicts
