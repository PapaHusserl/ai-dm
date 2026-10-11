from ai_dm.combat.actions import attack


def melee_attack_of(engine, ref):
    # первая ближняя атака участника или None; герой бьёт только оружием в руке:
    # сменить оружие можно лишь в действии Атака (2024); безоружный и импровизированное не берём
    hero = engine.heroes[ref] if engine.is_hero(ref) else None
    for info in attack.attacks_of(engine, ref):
        if hero is not None and info.id != hero.equipped.main_hand:
            continue
        if info.kind == "melee":
            return info
    return None


def provoke(engine, mover_ref, from_zone_id) -> list:
    # каждый боеспособный враг в зоне с нетронутой реакцией бьёт уходящего ближней атакой
    mover = engine.part(mover_ref)
    if mover.turn.disengaged:
        return []
    events = []
    for p in engine.state.participants:
        if p.side == mover.side or p.zone_id != from_zone_id:
            continue
        if not engine.is_capable(p.ref) or not p.turn.reaction:
            continue
        # мишень уже могла упасть от предыдущей провоцированной атаки
        if not engine.is_capable(mover_ref):
            break
        info = melee_attack_of(engine, p.ref)
        if info is None:
            continue
        p.turn.reaction = False
        engine.log(f"{engine.name(p.ref)}: провоцированная атака")
        events += attack.attack(engine, p.ref, mover_ref, info, provoked=True)
    return events
