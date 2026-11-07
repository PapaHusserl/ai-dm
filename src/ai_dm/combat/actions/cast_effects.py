from ai_dm.combat import aura, downed, falling
from ai_dm.combat.actions import move
from ai_dm.combat.actions.attack import arrow_conditions, attack_event, roll_damage, split_dice
from ai_dm.combat.actions.cast_conditions import impose_effects
from ai_dm.combat.actions.cast_support import (
    TARGETABLE,
    damage_on_save,
    hit_damage,
    hold_concentration,
    roll_spell_attack,
    scaled_dice,
    spell_expiry,
)
from ai_dm.core.dice import roll_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import spell_save_dc
from ai_dm.rules.healing import grant_max_hp, heal
from ai_dm.rules.inventory import add_catalog_item
from ai_dm.rules.spellcasting import (
    add_spell_duration,
    defense_effect,
    effect_line,
    effect_of,
    upcast_dice,
    upcast_steps,
)
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry


def cast_save(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    save = effect_of(spell, "save_effect")
    effect = effect_of(spell, "damage")
    dice, bonus = split_dice(scaled_dice(spell, hero, effect, circle))
    rolled = roll_damage(
        engine, ref, dice, bonus, False, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=effect.damage_type,
    )
    dc = spell_save_dc(hero, engine.registry)
    saved = engine.save(target_ref, save.ability, dc).outcome == "success"
    return damage_on_save(engine, (ref, target_ref), spell, rolled.total, saved)


def cast_rays(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Палящий луч: каждый луч -- своя атака заклинанием по одной цели
    effect = effect_of(spell, "damage")
    count = effect.count
    if upcast_steps(spell, circle) > 0:
        count += upcast_steps(spell, circle) * (spell.upcast.per_slot_level.count or 0)
    events = []
    for _ in range(count):
        if engine.part(target_ref).status in ("dead", "fled"):
            break
        result = roll_spell_attack(engine, ref, spell, target_ref)
        if result.outcome not in ("hit", "crit"):
            events.append(attack_event(ref, target_ref, spell.id, "spell", "miss", 0))
            continue
        crit = result.outcome == "crit"
        damage = (effect.dice, effect.damage_type, False)
        dealt = hit_damage(engine, (ref, target_ref), spell, damage, crit)
        events.append(attack_event(ref, target_ref, spell.id, "spell", result.outcome, dealt.final))
        events += downed.after_damage(engine, target_ref, dealt, ref, crit=crit)
    return events


def cast_temp_hp(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    effect = effect_of(spell, "temp_hp")
    amount = roll_dice(effect.dice, engine.rng).total
    steps = upcast_steps(spell, circle)
    if steps > 0:
        amount += steps * (spell.upcast.per_slot_level.value or 0)
    creature = engine.creature(ref)
    creature.hp_temp = max(creature.hp_temp, amount)
    engine.log(f"{engine.name(ref)}: {spell.name}, временные HP {creature.hp_temp}")
    return []


def cast_defense(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # КД, сопротивление, невидимость, помеха атакам по цели; прежнее действие того же заклинания
    # заменяется
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    targets = target_ref.split(",")
    for one_ref in targets:
        defend(engine, ref, spell, one_ref)
    names = ", ".join(engine.name(one) for one in targets)
    engine.log(f"{engine.name(ref)}: {spell.name} на {names}")
    return []


def cast_max_hp(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Помощь: +N к максимуму и текущим HP на срок заклинания; откат по часам мира
    amount = effect_of(spell, "max_hp").value
    steps = upcast_steps(spell, circle)
    if steps > 0:
        amount += steps * (spell.upcast.per_slot_level.value or 0)
    until_s = engine.world.clock.now_s + spell.duration_s
    targets = target_ref.split(",")
    given = []
    for one_ref in targets:
        if grant_max_hp(engine.creature(one_ref), spell.id, ref, amount, until_s):
            given.append(one_ref)
        else:
            engine.log(f"  {engine.name(one_ref)}: уже под более сильной Помощью")
    names = ", ".join(f"{engine.name(one)} {engine.hp_text(one)}" for one in given)
    if given:
        engine.log(f"{engine.name(ref)}: {spell.name} (+{amount} HP) на {names}")
    return []


def defend(engine, ref, spell, target_ref) -> None:
    # эффекты защиты заклинания на одну цель
    creature = engine.creature(target_ref)
    creature.active_effects = [e for e in creature.active_effects if e.id != spell.id]
    for effect in spell.effects:
        expires = spell_expiry(engine, ref, spell)
        if effect.type == "invisible":
            engine.impose(
                target_ref, AppliedCondition(id="invisible", source=spell.id, expires=expires)
            )
            continue
        built = defense_effect(effect, spell)
        if built is None:
            continue
        kind, params = built
        creature.active_effects.append(
            ActiveEffect(id=spell.id, source=ref, kind=kind, params=params, expires=expires)
        )


def cast_ward(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # защита от существ с тегами: их атаки по цели с помехой, очарование и страх не ложатся
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "ward")
    creature = engine.creature(target_ref)
    creature.active_effects = [e for e in creature.active_effects if e.id != spell.id]
    creature.active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="ward", params={"tags": ",".join(effect.vs)},
            expires=spell_expiry(engine, ref, spell),
        )
    )
    engine.log(f"{engine.name(ref)}: {spell.name} на {engine.name(target_ref)}")
    return []


def cast_stabilize(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    saves = engine.heroes[target_ref].creature.death_saves
    saves.successes = 0
    saves.failures = 0
    saves.stable = True
    engine.log(f"{engine.name(ref)}: {spell.name}, {engine.name(target_ref)} стабилен")
    return []


def cast_teleport(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    # Туманный шаг: в соседнюю зону без провоцирования
    p = engine.part(ref)
    engine.record_move(ref, p.zone_id, zone_id)
    p.zone_id = zone_id
    name = [z.name for z in engine.state.zones if z.id == zone_id][0]
    engine.log(f"{engine.name(ref)}: {spell.name} — {name}")
    return move.hazard_check(engine, ref) + aura.on_enter(engine, ref)


def cast_retreat(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Стремительное отступление: Рывок бонусным действием каждый ход, пока держится концентрация
    hold_concentration(engine, ref, spell, circle)
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="dash_bonus",
            expires=Expiry(kind="concentration", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: {spell.name}")
    return []


def cast_zone(engine, ref, spell, zone_id, params) -> None:
    # эффект на зону лежит на заклинателе; пока держится концентрация
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="zone", params={"zone": zone_id, **params},
            expires=Expiry(kind="concentration", owner=ref),
        )
    )
    name = [z.name for z in engine.state.zones if z.id == zone_id][0]
    engine.log(f"{engine.name(ref)}: {spell.name} — {name}")


def cast_fog(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    hold_concentration(engine, ref, spell, circle)
    cast_zone(engine, ref, spell, zone_id, {"kind": "fog"})
    return []


def cast_hazard(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "hazard")
    params = {"kind": "hazard", "dice": effect.dice, "damage_type": effect.damage_type}
    cast_zone(engine, ref, spell, zone_id, params)
    return []


def cast_aura(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Духовные стражи: аура на заклинателе; конец хода врага в зоне, вход (aura.tick, on_enter)
    hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "aura")
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="aura",
            params={
                "spell": spell.id, "dice": scaled_dice(spell, engine.heroes[ref], effect, circle),
                "ability": effect.ability, "damage_type": effect.damage_type,
            },
            expires=Expiry(kind="concentration", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: {spell.name}")
    return []


def cast_create_item(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    effect = effect_of(spell, "create_item")
    add_catalog_item(engine.heroes[ref], engine.registry, effect.item, effect.count)
    name = engine.registry.get("item", effect.item).name
    engine.log(f"{engine.name(ref)}: {spell.name} — {name} ×{effect.count}")
    return []


def cast_utility(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # без боевого эффекта: трата действия и ячейки уже в perform; срок и строка эффекта
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    hero = engine.heroes[ref]
    hero.creature.active_effects = [
        e for e in hero.creature.active_effects if not (e.kind == "spell" and e.id == spell.id)
    ]
    add_spell_duration(hero, spell, engine.world.clock.now_s)
    engine.log(f"  {effect_line(spell)}")
    return []


def attack_riders(engine, ref, target_ref, spell, dealt) -> None:
    # «всадники» попавшей атаки заклинанием: замедление, горение, состояние со спасброском,
    # лечение половиной, преимущество следующей атаке
    hero = engine.heroes[ref]
    timed = [(spell.id, e) for e in spell.effects if e.type in ("burn", "slow")]
    if timed:
        arrow_conditions(engine, ref, target_ref, spell.id, timed)
    if engine.creature(target_ref).hp_current <= 0:
        return
    save = effect_of(spell, "save_effect")
    if save is not None and effect_of(spell, "apply_condition") is not None:
        dc = spell_save_dc(hero, engine.registry)
        if engine.save(target_ref, save.ability, dc).outcome != "success":
            impose_effects(engine, ref, spell, target_ref, dc)
    if effect_of(spell, "heal_half") is not None:
        healed = heal(engine.actor(ref), dealt.final // 2)
        engine.log(f"  {engine.name(ref)} исцеляется на {healed}: {engine.hp_text(ref)}")
    if effect_of(spell, "guided") is not None:
        engine.creature(target_ref).active_effects.append(
            ActiveEffect(
                id=spell.id, source=ref, kind="modifier",
                params={"target": "attack_roll", "side": "target", "mode": "advantage",
                        "consume": True},
                expires=Expiry(kind="end_of_turn", value=1, owner=ref),
            )
        )
        engine.log(f"  {engine.name(target_ref)}: следующая атака по нему с преимуществом")


def cast_burst(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # Ледяной нож: попал или нет, цель и все в её зоне -- спасбросок Лов, холод (второй урон)
    hero = engine.heroes[ref]
    save = effect_of(spell, "save_effect")
    burst = [e for e in spell.effects if e.type == "damage"][1]
    dice = burst.dice
    if upcast_steps(spell, circle) > 0:
        dice = upcast_dice(dice, spell.upcast.per_slot_level.dice, upcast_steps(spell, circle))
    dice, bonus = split_dice(dice)
    rolled = roll_damage(
        engine, ref, dice, bonus, False, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=burst.damage_type,
    )
    dc = spell_save_dc(hero, engine.registry)
    zone_id = engine.part(target_ref).zone_id
    events = []
    for q in engine.state.participants:
        if q.ref == ref or q.zone_id != zone_id or q.status not in TARGETABLE:
            continue
        saved = engine.save(q.ref, save.ability, dc).outcome == "success"
        amount = rolled.total // 2 if saved else rolled.total
        dealt = engine.damage(q.ref, amount, burst.damage_type)
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(q.ref)}: {engine.hp_text(q.ref)}")
        events += downed.after_damage(engine, q.ref, dealt, ref)
    return events


def push_zone(engine, ref, target_ref) -> list[DomainEvent]:
    # толчок в соседнюю зону: ниже по высоте, иначе первая соседняя (Толчок К2)
    if not engine.is_capable(target_ref):
        return []
    zones = engine.state.zones
    own = [z for z in zones if z.id == engine.part(target_ref).zone_id][0]
    near = [z for z in zones if z.id in own.adjacent]
    lower = [z for z in near if z.elevation < own.elevation]
    options = lower or near
    if not options:
        return []
    return falling.push(engine, ref, target_ref, options[0].id)
