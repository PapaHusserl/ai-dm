from ai_dm.content.models.items import Item
from ai_dm.state.world import ItemHolder


def as_item(custom) -> Item:
    # модель предмета реестра для сюжетного предмета мира
    category = "quest" if custom.quest else "valuable"
    return Item(
        id=custom.id, name=custom.name, description=custom.description, cost_cp=custom.cost_cp,
        category=category, source="world", weight_centilb=custom.weight_centilb,
    )


def world_registry(base, world):
    # базовый реестр + сюжетные предметы мира; последняя копия кэшируется в базовом реестре
    if not world.custom_items:
        return base
    key = frozenset(
        (c.id, c.name, c.description, c.cost_cp, c.quest, c.weight_centilb)
        for c in world.custom_items.values()
    )
    if key != base.overlay_key:
        extra = {"item": [as_item(c) for c in world.custom_items.values()]}
        base.overlay = base.with_items(extra)
        base.overlay_key = key
    return base.overlay


def hand_over(world, item_id, holder) -> None:
    # предмет ушёл от героя к держателю
    world.custom_items[item_id].holder = holder


def hand_to_npc(world, npc, given, now_s) -> None:
    # given -- InventoryEntry отданного; у того же держателя количество складывается
    holder = world.custom_items[given.item_id].holder
    if holder is not None and holder.kind == "npc" and holder.ref == npc.id:
        holder.qty += given.qty
        return
    hand_over(world, given.item_id, ItemHolder(
        kind="npc", ref=npc.id, label=npc.name, location_id=npc.location_id, since_s=now_s,
        qty=given.qty, cost_cp=given.cost_cp,
    ))


def recover(world, item_id):
    # предмет вернулся к герою; возвращает прежнего держателя (None -- не отслеживался)
    custom = world.custom_items[item_id]
    holder = custom.holder
    custom.holder = None
    return holder
