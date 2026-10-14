from itertools import combinations

from ai_dm.combat import downed
from ai_dm.combat.actions.attack import (
    attack_event,
    mark_damage,
    reveal,
    roll_attack,
    roll_damage,
    split_dice,
)
from ai_dm.combat.area import affected_zones
from ai_dm.combat.zones import cover_dc_bonus, distance, range_band_ft
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.derived import (
    always_prepared,
    free_cast_pool,
    hero_feature_ids,
    spell_attack_bonus,
    spell_attack_parts,
    spell_save_dc,
)
from ai_dm.rules.healing import heal
from ai_dm.rules.spellcasting import (
    effect_of,
    roll_cast_checks,
    roll_heal,
    spell_kind,
    upcast_dice,
    upcast_steps,
    usable_circles,
)
from ai_dm.rules.spellcasting import free_cast_left as rules_free_cast_left
from ai_dm.state.creature import ActiveEffect, Concentration, Expiry

# по кому бьют: боеспособные, лежащие и сдавшиеся (лежачего бить можно)
TARGETABLE = ("active", "down", "surrendered")


def castable_spells(engine, ref) -> list:
    # заговоры из известных; заклинания 1+ круга из подготовленных, пока есть ячейка
    hero = engine.heroes[ref]
    result = []
    for spell_id in hero.sheet.known_of():
        spell = engine.registry.get("spell", spell_id)
        if spell.level == 0 and spell not in result:
            result.append(spell)
    prepared = list(hero.sheet.prepared_of())
    for spell_id in always_prepared(hero, engine.registry):
        if spell_id not in prepared:
            prepared.append(spell_id)
    for spell_id in prepared:
        spell = engine.registry.get("spell", spell_id)
        usable = bool(usable_circles(hero, spell)) or free_cast_left(engine, hero, spell)
        if spell.level >= 1 and usable and spell not in result:
            checks = engine.cast_checks.check(hero, spell.id, engine.registry)
            if not any(c.kind == "forbidden" for c in checks):
                result.append(spell)
    return [s for s in result if spell_kind(s) is not None]


def inert_spells(engine, ref) -> list:
    # заклинания героя без механики в бою (spell_kind is None): в меню -- невыбираемой строкой
    hero = engine.heroes[ref]
    ids = list(hero.sheet.known_of()) + list(hero.sheet.prepared_of())
    ids += always_prepared(hero, engine.registry)
    result = []
    for spell_id in ids:
        spell = engine.registry.get("spell", spell_id)
        if spell_kind(spell) is None and spell not in result:
            result.append(spell)
    return result


def free_cast_left(engine, hero, spell) -> bool:
    return rules_free_cast_left(hero, engine.registry, spell)


def uses_bonus_action(spell) -> bool:
    return spell.casting_time == "bonus_action"


def cast_targets(engine, ref, spell, circle=None) -> list[str]:
    p = engine.part(ref)
    zones = engine.state.zones
    kind = spell_kind(spell)
    result = []
    if kind in ("attack", "darts", "mark"):
        for p_target in engine.state.participants:
            if p_target.side == p.side or p_target.status not in TARGETABLE:
                continue
            steps = distance(zones, p.zone_id, p_target.zone_id)
            band = range_band_ft(steps)
            if band <= spell.range_ft:
                result.append(p_target.ref)
    elif kind == "rider":
        result.append(ref)
    elif kind == "area":
        area = effect_of(spell, "area")
        for zone in zones:
            try:
                affected_zones(zones, p.zone_id, area.shape, area.size_ft, zone.id)
            except ValueError:
                continue
            result.append(zone.id)
    elif kind == "heal":
        for q in engine.state.participants:
            if q.side == p.side and q.status in ("active", "down") and q.zone_id == p.zone_id:
                result.append(q.ref)
    elif kind == "buff":
        allies = []
        for q in engine.state.participants:
            if q.side != p.side or q.status != "active":
                continue
            if range_band_ft(distance(zones, p.zone_id, q.zone_id)) <= spell.range_ft:
                allies.append(q.ref)
        # цель варианта -- от одной до `targets` разных союзников через запятую
        limit = max([e.targets or 1 for e in spell.effects if e.type == "modifier"])
        if upcast_steps(spell, circle) > 0:
            limit += upcast_steps(spell, circle) * (spell.upcast.per_slot_level.targets or 0)
        for count in range(1, limit + 1):
            for group in combinations(allies, count):
                result.append(",".join(group))
    return result


def scaled_dice(spell, hero, effect, circle) -> str:
    # заговоры растут с уровнем героя, заклинания -- с кругом ячейки
    dice = effect.dice
    if spell.cantrip_scaling is not None:
        for level in sorted(spell.cantrip_scaling):
            if level <= hero.sheet.level:
                dice = spell.cantrip_scaling[level]
    steps = upcast_steps(spell, circle)
    if steps > 0 and spell.upcast.per_slot_level.dice is not None:
        dice = upcast_dice(dice, spell.upcast.per_slot_level.dice, steps)
    return dice


def hold_concentration(engine, ref, spell, circle) -> None:
    # новая концентрация сбрасывает прежнюю; срок -- по часам мира
    caster = engine.creature(ref)
    if caster.concentration is not None:
        end_concentration(caster)
        engine.drop_concentration_effects(ref)
    until_s = None
    if spell.duration_s is not None:
        until_s = engine.world.clock.now_s + spell.duration_s
    caster.concentration = Concentration(spell_id=spell.id, circle=circle, until_s=until_s)


def cast_attack(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    effect = effect_of(spell, "damage")
    base_adv = "normal"
    if engine.enemy_nearby(ref):
        base_adv = "disadvantage"
    bonus = spell_attack_bonus(hero, engine.registry)
    parts = spell_attack_parts(hero, engine.registry)
    base_note = ""
    if base_adv == "disadvantage":
        base_note = "враг рядом"
    result = roll_attack(
        engine, ref, target_ref, bonus, base_adv, spell.name, parts, base_note=base_note
    )
    if result.outcome not in ("hit", "crit"):
        return [attack_event(ref, target_ref, spell.id, "spell", "miss", 0)]
    crit = result.outcome == "crit"
    dice, bonus = split_dice(scaled_dice(spell, hero, effect, circle))
    rolled = roll_damage(
        engine, ref, dice, bonus, crit, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=effect.damage_type,
    )
    dealt = engine.damage(target_ref, rolled.total, effect.damage_type)
    dealt = mark_damage(engine, ref, target_ref, crit, dealt)
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    events = [attack_event(ref, target_ref, spell.id, "spell", result.outcome, dealt.final)]
    return events + downed.after_damage(engine, target_ref, dealt, ref, crit=crit)


def place_mark(engine, ref, spell, target_ref) -> None:
    effect = effect_of(spell, "extra_damage")
    engine.creature(target_ref).active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="mark",
            params={"dice": effect.dice, "damage_type": effect.damage_type},
            expires=Expiry(kind="concentration", owner=ref),
        )
    )


def convert_pending_marks(engine) -> None:
    # метка, наложенная вне боя (kind mark_pending на герое), ложится на цель, когда та в бою
    refs = [p.ref for p in engine.state.participants]
    for ref, hero in engine.heroes.items():
        left = []
        for effect in hero.creature.active_effects:
            if effect.kind == "mark_pending" and effect.params["target"] in refs:
                spell = engine.registry.get("spell", effect.id)
                place_mark(engine, ref, spell, effect.params["target"])
            else:
                left.append(effect)
        hero.creature.active_effects = left


def transfer_mark(engine, ref, option) -> list[DomainEvent]:
    # SRD 5.2: помеченная цель упала, концентрация держится -- бонусным действием метка на
    # новую цель, без ячейки
    spell = engine.registry.get("spell", engine.creature(ref).concentration.spell_id)
    engine.part(ref).turn.bonus = False
    target_ref = option.params["target"]
    place_mark(engine, ref, spell, target_ref)
    engine.log(f"{engine.name(ref)}: {spell.name} переходит на {engine.name(target_ref)}")
    return []


def cast_mark(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    hold_concentration(engine, ref, spell, circle)
    place_mark(engine, ref, spell, target_ref)
    engine.log(f"{engine.name(ref)}: {spell.name} на {engine.name(target_ref)}")
    if "hunters_lore" in hero_feature_ids(hero, engine.registry):
        # TODO: иммунитеты и сопротивления монстров движок пока не хранит; строка-заглушка,
        # пока их нет в данных монстров (docs/BACKLOG.md, раздел 11)
        name = engine.name(target_ref)
        engine.log(f"  Знания охотника: у {name} нет известных иммунитетов, "
                   "сопротивлений и уязвимостей")
    return []


def cast_rider(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # заряд на следующее попадание оружием: срабатывает в attack.weapon_rider
    hero = engine.heroes[ref]
    hold_concentration(engine, ref, spell, circle)
    effect = effect_of(spell, "rider")
    dice = scaled_dice(spell, hero, effect, circle)
    hero.creature.active_effects.append(
        ActiveEffect(
            id=spell.id, source=ref, kind="weapon_rider",
            params={
                "dice": dice, "damage_type": effect.damage_type,
                "condition": effect.condition, "ability": effect.ability,
                "dc": spell_save_dc(hero, engine.registry), "circle": circle,
            },
            expires=Expiry(kind="concentration", owner=ref),
        )
    )
    engine.log(f"{engine.name(ref)}: оружие оплетено лозами до следующего попадания")
    return []


def cast_darts(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    effect = effect_of(spell, "damage")
    dice, bonus = split_dice(effect.dice)
    count = effect.count
    if upcast_steps(spell, circle) > 0:
        count += upcast_steps(spell, circle) * (spell.upcast.per_slot_level.count or 0)
    total = 0
    for _ in range(count):
        total += roll_damage(
            engine, ref, dice, bonus, False, label=f"Урон ({spell.name})",
            parts=[(spell.name, bonus)], damage_type=effect.damage_type,
        ).total
    dealt = engine.damage(target_ref, total, effect.damage_type)
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
    events = [attack_event(ref, target_ref, spell.id, "spell", "auto", dealt.final)]
    return events + downed.after_damage(engine, target_ref, dealt, ref)


def cast_area(engine, ref, spell, zone_id, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    area = effect_of(spell, "area")
    save = effect_of(spell, "save_effect")
    effect = effect_of(spell, "damage")
    covered = affected_zones(
        engine.state.zones, engine.part(ref).zone_id, area.shape, area.size_ft, zone_id
    )
    dice, bonus = split_dice(scaled_dice(spell, hero, effect, circle))
    rolled = roll_damage(
        engine, ref, dice, bonus, False, label=f"Урон ({spell.name})",
        parts=[(spell.name, bonus)], damage_type=effect.damage_type,
    )
    dc = spell_save_dc(hero, engine.registry)
    events = []
    for q in engine.state.participants:
        if q.ref == ref or q.zone_id not in covered or q.status not in TARGETABLE:
            continue
        cover = 0
        if q.zone_id != engine.part(ref).zone_id:
            zone = [z for z in engine.state.zones if z.id == q.zone_id][0]
            cover = cover_dc_bonus(zone)
        saved = engine.save(q.ref, save.ability, dc, cover).outcome == "success"
        amount = rolled.total
        if saved:
            amount = rolled.total // 2 if save.mode == "half" else 0
        dealt = engine.damage(q.ref, amount, effect.damage_type)
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(q.ref)}: {engine.hp_text(q.ref)}")
        events.append(attack_event(ref, q.ref, spell.id, "spell", "auto", dealt.final))
        events += downed.after_damage(engine, q.ref, dealt, ref)
    return events


def cast_heal(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    amount, _ = roll_heal(spell, hero, engine.registry, engine.rng, circle)
    healed = heal(engine.actor(target_ref), amount)
    p = engine.part(target_ref)
    if p.status == "down" and engine.creature(target_ref).hp_current > 0:
        p.status = "active"
    engine.log(f"{engine.name(ref)} лечит {engine.name(target_ref)} на {healed}: "
               f"{engine.hp_text(target_ref)}")
    return []


def cast_buff(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hold_concentration(engine, ref, spell, circle)
    # все эффекты-модификаторы заклинания (атака и спасброски) на каждую цель
    effects = [e for e in spell.effects if e.type == "modifier"]
    names = []
    for one_ref in target_ref.split(","):
        for effect in effects:
            engine.creature(one_ref).active_effects.append(
                ActiveEffect(
                    id=spell.id, source=ref, kind="modifier",
                    params={"target": effect.target, "dice": effect.dice},
                    expires=Expiry(kind="concentration", owner=ref),
                )
            )
        names.append(engine.name(one_ref))
    engine.log(f"{engine.name(ref)}: {spell.name} на {', '.join(names)}")
    return []


CASTERS = {
    "attack": cast_attack, "mark": cast_mark, "rider": cast_rider, "darts": cast_darts,
    "area": cast_area, "heal": cast_heal, "buff": cast_buff,
}


def cast_wasted(engine, hero, spell) -> bool:
    # проверки перед сотворением (жрец и бог, ТЗ 4.2): провал -- ячейка уже потрачена
    wasted, lines = roll_cast_checks(
        hero, spell, engine.cast_checks, engine.registry, engine.rng, engine.modifiers,
        engine.world.clock.now_s,
    )
    for line in lines:
        engine.log(line)
    return wasted


def perform(engine, ref, option) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    spell = engine.registry.get("spell", option.params["spell"])
    if uses_bonus_action(spell):
        engine.part(ref).turn.bonus = False
    else:
        engine.part(ref).turn.action = False
    free = spell.level > 0 and option.params.get("free", False)
    circle = option.params["circle"]
    if free:
        # бесплатное использование тратится первым, ячейка остаётся
        hero.creature.resources[free_cast_pool(hero, engine.registry, spell.id)].current -= 1
    elif spell.level > 0:
        hero.creature.resources[f"spell_slot:{circle}"].current -= 1
    higher = ""
    if circle > spell.level:
        higher = f" ({circle} круг)"
    engine.log(f"{engine.name(ref)} читает {spell.name}{higher}")
    if spell.level > 0 and cast_wasted(engine, hero, spell):
        engine.log("  заклинание не удалось, ячейка потрачена впустую")
        reveal(engine, ref)
        return [DomainEvent(type="spell_wasted", data={"id": ref, "spell": spell.id})]
    events = CASTERS[spell_kind(spell)](
        engine, ref, spell, option.params["target"], circle
    )
    # скрытность кончается с заклинанием (атака заклинанием уже раскрыла)
    reveal(engine, ref)
    return events
