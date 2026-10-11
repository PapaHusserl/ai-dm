from ai_dm.rules.loot import body_gear, quest_gear, trophy_cost, trophy_quality


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


def enemy_gear(engine, weapon_ids) -> list:
    # оружие и квестовые вещи с тел (dead/down; сбежавшие, сдавшиеся и перебежчики -- нет);
    # зовётся после раздачи выбитого оружия, пока метки disarmed ещё на существах
    bodies = []
    refs = []
    for p in engine.state.participants:
        if p.side != "enemies" or p.status not in ("dead", "down"):
            continue
        if any(e.id == "parley_defected" for e in engine.creature(p.ref).active_effects):
            continue
        refs.append(p.ref)
        if p.monster_id is not None:
            bodies.append(
                (p.monster_id, weapon_ids(engine, p.ref), is_boss(engine, p))
            )
    return body_gear(bodies, engine.registry, engine.cfg) + quest_gear(engine.world, refs)
