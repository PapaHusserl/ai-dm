def zone_effects(engine, zone_id, kind) -> list:
    # эффекты заклинаний на зоне (лежат на заклинателе): ActiveEffect(kind="zone",
    # params={"zone", "kind"})
    return [
        effect for _, creature in engine.all_creatures() for effect in creature.active_effects
        if effect.kind == "zone" and effect.params["zone"] == zone_id
        and effect.params["kind"] == kind
    ]


def obscured(engine, zone_id) -> bool:
    # зона скрыта (Туманное облако): атаки в неё и из неё с помехой
    return bool(zone_effects(engine, zone_id, "fog"))
