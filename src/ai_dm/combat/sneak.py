from ai_dm.combat.actions import rogue
from ai_dm.rules.derived import by_level
from ai_dm.state.creature import ActiveEffect, Expiry

# флаг: Скрытая атака в этом ходу уже была (раз в ход для всех, снимается в start_turn любого хода)
USED = "sneak_used"


def reset(engine) -> None:
    # новый ход: Скрытая атака снова доступна всем
    for _, creature in engine.all_creatures():
        creature.active_effects = [e for e in creature.active_effects if e.id != USED]


def ally_near(engine, ref, target_ref) -> bool:
    # боеспособный союзник героя в зоне цели
    side = engine.part(ref).side
    zone = engine.part(target_ref).zone_id
    return any(
        p.side == side and p.ref != ref and p.zone_id == zone and engine.is_capable(p.ref)
        for p in engine.state.participants
    )


def eligible(engine, ref, target_ref, info, result) -> bool:
    # плут, оружие фехтовальное или дальнобойное, в этом ходу ещё не было; преимущество на атаку
    # или союзник у цели без помехи
    if info.weapon_id is None or not rogue.has(engine, ref, "sneak_attack"):
        return False
    if any(e.id == USED for e in engine.creature(ref).active_effects):
        return False
    weapon = engine.registry.get("weapon", info.weapon_id)
    if "finesse" not in weapon.properties and weapon.kind != "ranged":
        return False
    if result.advantage == "advantage":
        return True
    return result.advantage != "disadvantage" and ally_near(engine, ref, target_ref)


def dice_count(engine, ref) -> int:
    rows = engine.registry.get("table", "sneak_attack").rows
    levels = {int(level): count for level, count in rows.items()}
    return by_level(levels, engine.heroes[ref].sheet.level)


def damage(engine, ref, target_ref, info, result) -> int:
    # Скрытая атака: кости по таблице, на одну меньше, если выбран Хитрый удар и он действует
    # (сам эффект -- после урона, rogue.resolve_pending); крит (result.outcome) удваивает кости
    if not eligible(engine, ref, target_ref, info, result):
        return 0
    # локальный импорт: цикл импортов attack <-> sneak
    from ai_dm.combat.actions.attack import roll_damage

    count = dice_count(engine, ref)
    effect = rogue.strike_effect(engine, ref, target_ref)
    if effect is not None:
        count -= 1
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=USED, source=ref, kind="flag", expires=Expiry(kind="end_of_turn", value=0, owner=ref)
        )
    )
    total = roll_damage(
        engine, ref, f"{count}d6", 0, result.outcome == "crit", label=f"Скрытая атака +{count}d6",
        damage_type=info.damage_type,
    ).total
    return total
