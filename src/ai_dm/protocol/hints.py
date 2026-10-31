from ai_dm.rules.services import providers_here
from ai_dm.rules.trade import assortment

LIMIT = 20


def allowed(ids, first=()):
    # подсказка для Invalid: допустимые id (до LIMIT штук); first -- впереди, остальные по алфавиту
    head = list(dict.fromkeys(first))
    ids = head + sorted(i for i in ids if i not in head)
    text = ", ".join(ids[:LIMIT])
    if len(ids) > LIMIT:
        text += f" и ещё {len(ids) - LIMIT}"
    return f"; допустимые id: {text}"


def item_ids(registry):
    # без сюжетных предметов мира: их id мастер берёт из инвентаря героя
    ids = []
    for kind in ("weapon", "armor", "item"):
        ids += [m.id for m in registry.all(kind) if m.source != "world"]
    return ids


def reachable_ids(world, location_id):
    # локации, связанные с данной, в любую сторону
    ids = set()
    here = world.locations.get(location_id)
    if here is not None:
        ids.update(c.to for c in here.connections)
    for place in world.locations.values():
        if any(c.to == location_id for c in place.connections):
            ids.add(place.id)
    return ids


def merchant_ids(world, location_id):
    # живые торговцы в локации
    return [
        npc.id for npc in world.npcs.values()
        if npc.trade is not None and npc.status == "alive" and npc.location_id == location_id
    ]


def provider_ids(world, location_id):
    # живые NPC с услугами в локации
    return [npc.id for npc in providers_here(world, location_id)]


def sold_ids(ctx, npc):
    # что торговец продаёт сейчас: сначала купленное у героя, затем ассортимент пресета
    ids = [entry.item_id for entry in npc.trade.stock]
    preset = ctx.cfg.trade.presets[npc.trade.kind]
    for item_id, _price in assortment(ctx.registry, preset, ctx.hero.sheet.level, ctx.cfg):
        if item_id not in ids:
            ids.append(item_id)
    return ids
