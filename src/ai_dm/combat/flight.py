from ai_dm.rules.creatures import live_effects


def has(engine, ref, kind) -> bool:
    # на существе живой эффект вида kind: flying (Полёт), levitating (Левитация), gaseous
    now_s = engine.world.clock.now_s
    return any(e.kind == kind for e in live_effects(engine.creature(ref), now_s))


def levitating(engine, *refs) -> bool:
    # хоть один из участников поднят Левитацией: в ближнем бою до него не достать
    return any(has(engine, ref, "levitating") for ref in refs)
