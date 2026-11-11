from ai_dm.rules.creatures import live_effects


def blocks(engine, ref, target_ref) -> bool:
    # Святилище на цели: враг бросает Мудрость (СЛ заклинателя), провал -- атака потеряна
    if engine.part(ref).side == engine.part(target_ref).side:
        return False
    now_s = engine.world.clock.now_s
    for effect in live_effects(engine.creature(target_ref), now_s):
        if effect.kind != "sanctuary":
            continue
        if engine.save(ref, "wis", effect.params["dc"]).outcome != "success":
            name = engine.name(target_ref)
            engine.log(f"Святилище: {engine.name(ref)} не решается напасть на {name}")
            return True
    return False


def drop(engine, ref) -> None:
    # защищаемый атаковал или прочёл вредное заклинание: охрана спадает
    creature = engine.creature(ref)
    if any(e.kind == "sanctuary" for e in creature.active_effects):
        creature.active_effects = [e for e in creature.active_effects if e.kind != "sanctuary"]
        engine.log(f"Святилище спадает с {engine.name(ref)}")
