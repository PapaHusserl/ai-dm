from ai_dm.combat import downed
from ai_dm.combat.actions.attack import attack_event, roll_attack, roll_damage, split_dice
from ai_dm.combat.actions.cast_support import (
    hit_damage,
    hold_concentration,
    scaled_dice,
)
from ai_dm.combat.zones import distance
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import (
    ability_mod,
    spell_attack_bonus,
    spell_attack_parts,
    spell_save_dc,
    spellcasting_ability,
)
from ai_dm.rules.spellcasting import effect_of
from ai_dm.state.creature import ActiveEffect, Expiry

# Призванное оружие (Духовное оружие, Пылающий шар): ActiveEffect(kind="summon") на заклинателе,
# пока держится концентрация; существом-участником оно не бывает


def zone_name(engine, zone_id) -> str:
    return [z.name for z in engine.state.zones if z.id == zone_id][0]


def summon_zones(engine, ref) -> list[str]:
    # куда ставится призыв: своя зона и соседние
    zones = engine.state.zones
    here = engine.part(ref).zone_id
    return [z.id for z in zones if distance(zones, here, z.id) <= 1]


def summon_effects(engine, ref) -> list[ActiveEffect]:
    return [e for e in engine.creature(ref).active_effects if e.kind == "summon"]


def foes_near(engine, ref, zone_id) -> list[str]:
    # враги заклинателя в зоне и соседних с ней
    zones = engine.state.zones
    side = engine.part(ref).side
    return [
        q.ref for q in engine.state.participants
        # как menu_targets: лежачих в меню героя нет, их добивает рассказчик (решения 55, 75)
        if q.side != side and q.status in ("active", "surrendered")
        and distance(zones, zone_id, q.zone_id) <= 1
    ]


def summon_targets(engine, ref, spell) -> list[str]:
    # цели каста: зоны; призыв с броском атаки (Духовное оружие) бьёт сразу — враги в своей или
    # соседней зоне (SRD 5.2.1: атака в момент сотворения); зона такого призыва — цель только без
    # врага (лежачий строки не получает: его зона остаётся целью-зоной)
    zones = summon_zones(engine, ref)
    if effect_of(spell, "summon").ability is not None:
        return zones
    foes = foes_near(engine, ref, engine.part(ref).zone_id)
    busy = {engine.part(one).zone_id for one in foes}
    return [z for z in zones if z not in busy] + foes


def summon(engine, ref, spell, target, circle) -> list[DomainEvent]:
    # target — зона или враг (тогда призыв встаёт в его зону и сразу бьёт)
    hero = engine.heroes[ref]
    zone_id = target
    if target not in [z.id for z in engine.state.zones]:
        zone_id = engine.part(target).zone_id
    hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "summon")
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="summon",
            params={
                "zone": zone_id, "spell": spell.id,
                "dice": scaled_dice(spell, hero, effect, circle),
            },
            expires=Expiry(kind="concentration", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: {spell.name} — {zone_name(engine, zone_id)}")
    if zone_id == target:
        return []
    return strike(engine, ref, spell, target)


def summon_options(engine, ref) -> list:
    # бонусным действием: удар по врагу в зоне призыва или соседней, перемещение в соседнюю зону
    from ai_dm.combat.available import ActionOption

    if not engine.part(ref).turn.bonus:
        return []
    zones = engine.state.zones
    result = []
    for effect in summon_effects(engine, ref):
        name = engine.registry.get("spell", effect.id).name
        here = effect.params["zone"]
        result += [
            ActionOption(
                id=f"summon_attack:{effect.id}:{one}", kind="summon_attack",
                label=f"{name}: удар → {engine.name(one)}",
                params={"spell": effect.id, "target": one}, cost="bonus",
            )
            for one in foes_near(engine, ref, here)
        ]
        adjacent = [z for z in zones if z.id == here][0].adjacent
        result += [
            ActionOption(
                id=f"summon_move:{effect.id}:{z.id}", kind="summon_move",
                label=f"{name}: переместить → {z.name}",
                params={"spell": effect.id, "zone": z.id}, cost="bonus",
            )
            for z in zones if z.id in adjacent
        ]
    return result


def summon_effect(engine, ref, spell_id) -> ActiveEffect:
    return [e for e in summon_effects(engine, ref) if e.id == spell_id][0]


def summon_attack(engine, ref, option) -> list[DomainEvent]:
    engine.part(ref).turn.bonus = False
    spell = engine.registry.get("spell", option.params["spell"])
    return strike(engine, ref, spell, option.params["target"])


def strike(engine, ref, spell, target_ref) -> list[DomainEvent]:
    # Духовное оружие: бросок атаки заклинанием; Пылающий шар: спасбросок цели, половина при успехе
    hero = engine.heroes[ref]
    registry = engine.registry
    spec = effect_of(spell, "summon")
    dice = summon_effect(engine, ref, spell.id).params["dice"]
    bonus = 0
    if spec.add == "spellcasting_modifier":
        bonus = ability_mod(hero, spellcasting_ability(hero, registry))
    if spec.ability is None:
        result = roll_attack(
            engine, ref, target_ref, spell_attack_bonus(hero, registry), "normal", spell.name,
            spell_attack_parts(hero, registry),
        )
        if result.outcome not in ("hit", "crit"):
            return [attack_event(ref, target_ref, spell.id, "spell", "miss", 0)]
        crit = result.outcome == "crit"
        expr = f"{dice}{bonus:+d}" if bonus else dice
        dealt = hit_damage(engine, (ref, target_ref), spell, (expr, spec.damage_type, False), crit)
        events = [attack_event(ref, target_ref, spell.id, "spell", result.outcome, dealt.final)]
        return events + downed.after_damage(engine, target_ref, dealt, ref, crit=crit)
    base, _ = split_dice(dice)
    rolled = roll_damage(
        engine, ref, base, bonus, False, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=spec.damage_type,
    )
    dc = spell_save_dc(hero, registry)
    saved = engine.save(target_ref, spec.ability, dc).outcome == "success"
    amount = rolled.total // 2 if saved else rolled.total
    dealt = engine.damage(target_ref, amount, spec.damage_type)
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    events = [attack_event(ref, target_ref, spell.id, "spell", "auto", dealt.final)]
    return events + downed.after_damage(engine, target_ref, dealt, ref)


def summon_move(engine, ref, option) -> list[DomainEvent]:
    spell = engine.registry.get("spell", option.params["spell"])
    engine.part(ref).turn.bonus = False
    summon_effect(engine, ref, spell.id).params["zone"] = option.params["zone"]
    engine.log(f"{engine.name(ref)}: {spell.name} — {zone_name(engine, option.params['zone'])}")
    return []
