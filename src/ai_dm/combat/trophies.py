from ai_dm.combat.actions.attack import lost_weapons
from ai_dm.rules.loot import body_gear, quest_gear, trophy_cost, trophy_quality
from ai_dm.state.creature import Equipment


def is_boss(engine, p) -> bool:
    # лидер группы, он же именованный NPC, либо тег boss
    npc = engine.world.npcs.get(p.ref)
    group = engine.state.groups.get(p.group_id)
    leader = group is not None and group.leader_id == p.ref
    named = npc is not None and bool(npc.named or npc.key)
    return (leader and named) or "boss" in engine.tags(p.ref)


def weapon_price(engine, target, weapon_id) -> tuple[int, str | None]:
    # оружие монстра стоит как трофей с его тела (босс -- полную цену)
    base = engine.registry.get("weapon", weapon_id).cost_cp
    quality = None
    if not is_boss(engine, engine.part(target)):
        quality = trophy_quality(engine.monster(target).cr, engine.cfg)
    return trophy_cost(base, quality, engine.cfg), quality


def body_equipment(engine, ref, weapon_ids) -> Equipment:
    # что надето на теле: equipment существа (None -- по статблоку), оружие минус выбитое
    npc = engine.world.npcs.get(ref)
    worn = engine.part(ref).equipment
    if worn is None and npc is not None:
        worn = npc.equipment
    if worn is None:
        monster = engine.monster(ref)
        weapons = weapon_ids(engine, ref)
        return Equipment(armor=monster.armor, shield=monster.shield, weapons=weapons)
    all_lost, lost = lost_weapons(engine, ref)
    weapons = [w for w in worn.weapons if not all_lost and w not in lost]
    return Equipment(armor=worn.armor, shield=worn.shield, weapons=weapons)


def body_refs(engine) -> list[str]:
    # тела врагов, с которых берут трофеи: dead/down без перебежчиков
    refs = []
    for p in engine.state.participants:
        if p.side != "enemies" or p.status not in ("dead", "down"):
            continue
        if any(e.id == "parley_defected" for e in engine.creature(p.ref).active_effects):
            continue
        refs.append(p.ref)
    return refs


def mark_looted(engine) -> None:
    # именованный NPC бой переживает: с тела всё взято в трофеи, повторно не берётся
    for ref in body_refs(engine):
        if ref in engine.world.npcs:
            engine.world.npcs[ref].equipment = Equipment()


def enemy_gear(engine, weapon_ids) -> list:
    # оружие, доспех, щит и квестовые вещи с тел (dead/down; сбежавшие, сдавшиеся,
    # перебежчики -- нет);
    # зовётся после раздачи выбитого оружия, пока метки disarmed ещё на существах
    bodies = []
    refs = body_refs(engine)
    for p in engine.state.participants:
        if p.ref in refs and p.monster_id is not None:
            worn = body_equipment(engine, p.ref, weapon_ids)
            item_ids = worn.weapons + [i for i in (worn.armor, worn.shield) if i is not None]
            bodies.append((p.monster_id, item_ids, is_boss(engine, p)))
    return body_gear(bodies, engine.registry, engine.cfg) + quest_gear(engine.world, refs)
