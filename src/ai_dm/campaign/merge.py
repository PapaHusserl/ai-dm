from pydantic import BaseModel, Field

from ai_dm.campaign.uniqueness import Conflict, collect_conflicts
from ai_dm.state.memory import ChronicleEntry

KIND_NAMES = {
    "location": "локация",
    "god": "бог",
    "faction": "фракция",
    "npc": "NPC",
    "event": "событие",
}


class MergeReport(BaseModel):
    # added -- "вид:id" добавленных сущностей
    added: list[str] = Field(default_factory=list)
    conflicts: list[Conflict] = Field(default_factory=list)


def is_new(entity, existing) -> bool:
    # новая: id нет в мире (сущность мира с таким id любого происхождения остаётся как есть)
    return entity.id not in existing


def new_part(world, pack):
    # копия пака только с сущностями, которых нет в мире
    event_ids = {event.id for event in world.events}
    return pack.model_copy(update={
        "locations": [e for e in pack.locations if is_new(e, world.locations)],
        "pantheon": [e for e in pack.pantheon if is_new(e, world.pantheon)],
        "factions": [e for e in pack.factions if is_new(e, world.factions)],
        "npcs": [e for e in pack.npcs if is_new(e, world.npcs)],
        "events": [e for e in pack.events if e.id not in event_ids],
    })


def merge_new(bundle, pack) -> MergeReport:
    # добавляет в идущий мир новые сущности пака; существующие не меняет
    world = bundle.world
    accepted, conflicts = collect_conflicts(world, bundle.heroes, new_part(world, pack))
    report = MergeReport(conflicts=conflicts)
    adds = [
        ("location", accepted.locations, world.locations),
        ("god", accepted.pantheon, world.pantheon),
        ("faction", accepted.factions, world.factions),
        ("npc", accepted.npcs, world.npcs),
    ]
    for kind, entities, target in adds:
        for entity in entities:
            target[entity.id] = entity.model_copy(deep=True)
            report.added.append(f"{kind}:{entity.id}")
            text = f"Пак {pack.manifest.version}: добавлено ({KIND_NAMES[kind]}) {entity.name}"
            bundle.chronicle.entries.append(
                ChronicleEntry(
                    at_s=world.clock.now_s, kind="pack_update", text=text, refs=[entity.id]
                )
            )
    for event in accepted.events:
        world.events.append(event.model_copy(deep=True))
        report.added.append(f"event:{event.id}")
        text = f"Пак {pack.manifest.version}: добавлено ({KIND_NAMES['event']}) {event.type}"
        bundle.chronicle.entries.append(
            ChronicleEntry(at_s=world.clock.now_s, kind="pack_update", text=text, refs=[event.id])
        )
    # теги существ пака (mor): у существующих NPC пака дополняем только пустое поле
    for npc in pack.npcs:
        old = world.npcs.get(npc.id)
        if old is not None and old.origin == "pack" and not old.tags and npc.tags:
            old.tags = list(npc.tags)
            report.added.append(f"tags:{npc.id}")
    world.campaign_version = pack.manifest.version
    # миры этапа 2 мигрируют с пустым текстом мира: берём из пака, только если пуст
    if not world.lore.world_text:
        world.lore.world_text = pack.world_text
    return report
