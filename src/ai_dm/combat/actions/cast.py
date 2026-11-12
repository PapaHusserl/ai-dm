from itertools import combinations

from ai_dm.combat import downed, sanctuary, summons, tempo, zone_effects
from ai_dm.combat.actions import (
    cast_conditions,
    cast_effects,
    cast_guards,
    cast_motion,
    cast_zones,
)
from ai_dm.combat.actions.attack import attack_event, reveal, roll_damage, split_dice
from ai_dm.combat.actions.cast_effects import push_zone
from ai_dm.combat.actions.cast_support import (
    TARGETABLE,
    damage_on_save,
    hit_damage,
    hold_concentration,
    is_potent,
    roll_spell_attack,
    scaled_dice,
    spell_expiry,
    with_variant,
)
from ai_dm.combat.area import affected_zones
from ai_dm.combat.zones import cover_dc_bonus, distance, range_band_ft
from ai_dm.core.events import DomainEvent
from ai_dm.rules.death_saves import is_dying
from ai_dm.rules.derived import (
    always_prepared,
    free_cast_pool,
    hero_feature_ids,
    spell_save_dc,
)
from ai_dm.rules.healing import heal
from ai_dm.rules.spellcasting import (
    MaxRng,
    effect_of,
    has_effect,
    modifier_params,
    reach_ft,
    roll_cast_checks,
    roll_heal,
    spell_kind,
    upcast_steps,
    usable_circles,
)
from ai_dm.rules.spellcasting import free_cast_left as rules_free_cast_left
from ai_dm.state.creature import ActiveEffect, Expiry

# виды с враждебной одиночной целью: лежащего врага по ним в меню героя нет (решение 55)
HOSTILE_KINDS = ("attack", "darts", "mark", "save", "rays", "condition", "summon")
# Доспехи мага: только на существо без доспеха
UNARMORED_ONLY = ("mage_armor",)
# подвал меню боя: заклинание без механики и герой в зоне Тишины
INERT_NOTE = "пока недоступно в бою"
SILENCE_NOTE = "Тишина — заклинания недоступны"


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


def foot_notes(engine, ref) -> list[str]:
    # готовые строки подвала меню: под Тишиной одна, иначе заклинания без механики
    if zone_effects.silenced(engine, ref):
        return [SILENCE_NOTE]
    return [f"{spell.name} — {INERT_NOTE}" for spell in inert_spells(engine, ref)]


def free_cast_left(engine, hero, spell) -> bool:
    return rules_free_cast_left(hero, engine.registry, spell)


def uses_bonus_action(spell) -> bool:
    return spell.casting_time == "bonus_action"


def in_reach(engine, p, q, spell) -> bool:
    # цель в дальности заклинания: касание и «на себя» -- своя зона
    return range_band_ft(distance(engine.state.zones, p.zone_id, q.zone_id)) <= reach_ft(spell)


def groups_of(refs, limit) -> list[str]:
    # от одной до `limit` разных целей через запятую
    return [",".join(group) for n in range(1, limit + 1) for group in combinations(refs, n)]


def targets_limit(spell, circle, *types) -> int:
    # число целей: максимум `targets` эффектов этих типов + прибавка за круг выше базового
    limit = max([e.targets or 1 for e in spell.effects if e.type in types] or [1])
    if upcast_steps(spell, circle) > 0:
        limit += upcast_steps(spell, circle) * (spell.upcast.per_slot_level.targets or 0)
    return limit


def enemy_refs(engine, ref, spell) -> list[str]:
    p = engine.part(ref)
    return [
        q.ref for q in engine.state.participants
        if q.side != p.side and q.status in TARGETABLE and in_reach(engine, p, q, spell)
    ]


def ally_refs(engine, ref, spell, statuses=("active",)) -> list[str]:
    # союзники (и сам) в дальности; «на себя» -- вокруг заклинателя в 30 фт
    p = engine.part(ref)
    reach = reach_ft(spell)
    if spell.range_kind == "self":
        reach = 30
    return [
        q.ref for q in engine.state.participants
        if q.side == p.side and q.status in statuses
        and range_band_ft(distance(engine.state.zones, p.zone_id, q.zone_id)) <= reach
    ]


def area_zones(engine, ref, spell) -> list[str]:
    # зоны, в которые можно направить область; «на себя» куб, сфера и эманация -- только своя
    p = engine.part(ref)
    area = effect_of(spell, "area")
    result = []
    for zone in engine.state.zones:
        try:
            affected_zones(engine.state.zones, p.zone_id, area.shape, area.size_ft, zone.id)
        except ValueError:
            continue
        if spell.range_kind == "self" and area.shape in ("sphere", "cube", "emanation") \
                and zone.id != p.zone_id:
            continue
        result.append(zone.id)
    return result


def ranged_zones(engine, ref, spell, reach=None) -> list[str]:
    # зоны в дальности заклинания (Туманное облако, Шипастая поросль); reach -- свой предел в
    # футах и не своя зона (Туманный шаг)
    p = engine.part(ref)
    result = []
    for zone in engine.state.zones:
        steps = distance(engine.state.zones, p.zone_id, zone.id)
        if reach is not None and (steps == 0 or range_band_ft(steps) > reach):
            continue
        if reach is None and range_band_ft(steps) > reach_ft(spell):
            continue
        result.append(zone.id)
    return result


def cure_refs(engine, ref, spell) -> list[str]:
    # союзники, с которых заклинание что-то снимет (Защита от яда помогает и здоровому)
    effect = effect_of(spell, "remove_condition")
    result = []
    for one in ally_refs(engine, ref, spell, ("active", "down")):
        present = {c.id for c in engine.creature(one).conditions}
        if present & set(effect.conditions) or has_effect(spell, "resist"):
            result.append(one)
    return result


def defense_refs(engine, ref, spell, circle) -> list[str]:
    if spell.range_kind == "self":
        return [ref]
    allies = ally_refs(engine, ref, spell)
    if spell.id in UNARMORED_ONLY:
        heroes = engine.heroes
        allies = [a for a in allies if a in heroes and heroes[a].equipped.armor is None]
    limit = targets_limit(spell, circle, "ac_bonus", "resist", "invisible", "blur")
    return groups_of(allies, limit)


def dying_refs(engine, ref, spell) -> list[str]:
    p = engine.part(ref)
    dying = [
        q for q in engine.state.participants
        if q.ref in engine.heroes and q.side == p.side and q.status == "down"
    ]
    return [
        q.ref for q in dying
        if is_dying(engine.heroes[q.ref].creature) and in_reach(engine, p, q, spell)
    ]


def condition_refs(engine, ref, spell, circle) -> list[str]:
    # условие с областью -- зоны, иначе враги (до `targets` через запятую)
    if has_effect(spell, "area"):
        return area_zones(engine, ref, spell)
    limit = targets_limit(spell, circle, "save_effect", "modifier")
    return groups_of(enemy_refs(engine, ref, spell), limit)


def tempo_refs(engine, ref, spell, circle) -> list[str]:
    # Замедление -- зоны (спасбросок), Ускорение -- союзники и сам
    if effect_of(spell, "tempo").mode == "slow":
        return condition_refs(engine, ref, spell, circle)
    return ally_refs(engine, ref, spell)


def flight_refs(engine, ref, spell, circle) -> list[str]:
    # Левитация -- только враг (Тел), Полёт и Газообразная форма -- союзники и сам
    if effect_of(spell, "flight").mode == "levitate":
        return condition_refs(engine, ref, spell, circle)
    return ally_refs(engine, ref, spell)


def heal_refs(engine, ref, spell, circle) -> list[str]:
    refs = ally_refs(engine, ref, spell, ("active", "down"))
    return groups_of(refs, targets_limit(spell, circle, "heal"))


def buff_refs(engine, ref, spell, circle) -> list[str]:
    return groups_of(ally_refs(engine, ref, spell), targets_limit(spell, circle, "modifier"))


# вид заклинания -> кто может быть целью (engine, ref, spell, circle); цель "" -- без цели
TARGETERS = {
    **dict.fromkeys(("attack", "darts", "mark", "save", "rays"),
                    lambda e, r, s, c: enemy_refs(e, r, s)),
    "condition": condition_refs, "heal": heal_refs, "buff": buff_refs,
    "area": lambda e, r, s, c: area_zones(e, r, s),
    "rider": lambda e, r, s, c: [r],
    **dict.fromkeys(("temp_hp", "utility", "create_item", "retreat"), lambda e, r, s, c: [""]),
    "cure": lambda e, r, s, c: cure_refs(e, r, s),
    "defense": defense_refs,
    **dict.fromkeys(("sanctuary", "bond", "see_invisible"), defense_refs),
    "zone": lambda e, r, s, c: ranged_zones(e, r, s),
    "tempo": tempo_refs, "flight": flight_refs,
    "size": lambda e, r, s, c: ally_refs(e, r, s) + enemy_refs(e, r, s),
    **dict.fromkeys(("mirror_image", "blink"), lambda e, r, s, c: [r]),
    "max_hp": lambda e, r, s, c: groups_of(ally_refs(e, r, s), targets_limit(s, c, "max_hp")),
    "ward": lambda e, r, s, c: ally_refs(e, r, s),
    "stabilize": lambda e, r, s, c: dying_refs(e, r, s),
    "teleport": lambda e, r, s, c: ranged_zones(e, r, s, effect_of(s, "teleport").size_ft),
    **dict.fromkeys(("fog", "hazard"), lambda e, r, s, c: ranged_zones(e, r, s)),
    "summon": lambda e, r, s, c: summons.summon_targets(e, r, s),
    "aura": lambda e, r, s, c: [""],
}


def cast_targets(engine, ref, spell, circle=None) -> list[str]:
    finder = TARGETERS.get(spell_kind(spell))
    if finder is None:
        return []
    return finder(engine, ref, spell, circle)


def cast_attack(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    effect = effect_of(spell, "damage")
    expr = effect.dice
    if not has_effect(spell, "area"):
        expr = scaled_dice(spell, hero, effect, circle)
    result = roll_spell_attack(engine, ref, spell, target_ref)
    pair = (ref, target_ref)
    events = []
    if result.outcome in ("hit", "crit"):
        crit = result.outcome == "crit"
        dealt = hit_damage(engine, pair, spell, (expr, effect.damage_type, False), crit)
        events.append(attack_event(ref, target_ref, spell.id, "spell", result.outcome, dealt.final))
        events += downed.after_damage(engine, target_ref, dealt, ref, crit=crit)
        cast_effects.attack_riders(engine, ref, target_ref, spell, dealt)
    else:
        events.append(attack_event(ref, target_ref, spell.id, "spell", "miss", 0))
        if is_potent(engine, hero, spell):
            # Мощный заговор: промах -- половина урона
            half = hit_damage(engine, pair, spell, (expr, effect.damage_type, True), False)
            events += downed.after_damage(engine, target_ref, half, ref)
    if has_effect(spell, "area"):
        events += cast_effects.cast_burst(engine, ref, spell, target_ref, circle)
    return events


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
    save = effect_of(spell, "save_effect")
    if save is not None:
        # Проклятие: цель, устоявшая в спасброске, метки не получает
        dc = spell_save_dc(hero, engine.registry)
        if engine.save(target_ref, save.ability, dc).outcome == "success":
            return []
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
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    covered = affected_zones(
        engine.state.zones, engine.part(ref).zone_id, area.shape, area.size_ft, zone_id
    )
    rolled_total = 0
    if effect is not None:
        dice, bonus = split_dice(scaled_dice(spell, hero, effect, circle))
        rolled_total = roll_damage(
            engine, ref, dice, bonus, False, label=f"Урон ({spell.name})",
            parts=[(spell.name, bonus)], damage_type=effect.damage_type,
        ).total
    dc = spell_save_dc(hero, engine.registry)
    events = []
    for q in engine.state.participants:
        if q.ref == ref or q.zone_id not in covered or q.status not in TARGETABLE:
            continue
        cover = 0
        if q.zone_id != engine.part(ref).zone_id:
            zone = [z for z in engine.state.zones if z.id == q.zone_id][0]
            cover = cover_dc_bonus(zone)
        failed = engine.save(q.ref, save.ability, dc, cover).outcome != "success"
        if effect is not None:
            events += damage_on_save(engine, (ref, q.ref), spell, rolled_total, not failed)
        if failed and has_effect(spell, "push"):
            events += push_zone(engine, ref, q.ref)
    return events


def cast_heal(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    hero = engine.heroes[ref]
    for one_ref in target_ref.split(","):
        # Маяк надежды на цели: лечение максимумом костей
        beacon = any(e.kind == "heal_max" for e in engine.creature(one_ref).active_effects)
        rng = MaxRng() if beacon else engine.rng
        amount, _ = roll_heal(spell, hero, engine.registry, rng, circle)
        healed = heal(engine.actor(one_ref), amount)
        p = engine.part(one_ref)
        if p.status == "down" and engine.creature(one_ref).hp_current > 0:
            p.status = "active"
        engine.log(f"{engine.name(ref)} лечит {engine.name(one_ref)} на {healed}: "
                   f"{engine.hp_text(one_ref)}")
    return []


def cast_buff(engine, ref, spell, target_ref, circle) -> list[DomainEvent]:
    # срок -- концентрация, иначе часы мира
    if spell.concentration:
        hold_concentration(engine, ref, spell, circle)
    # все эффекты-модификаторы заклинания (атака и спасброски) на каждую цель
    effects = [e for e in spell.effects if e.type == "modifier"]
    names = []
    for one_ref in target_ref.split(","):
        creature = engine.creature(one_ref)
        for effect in effects:
            creature.active_effects.append(
                ActiveEffect(
                    id=spell.id, source=ref, kind="modifier",
                    params=modifier_params(effect),
                    expires=spell_expiry(engine, ref, spell),
                )
            )
        if has_effect(spell, "heal_max"):
            creature.active_effects.append(
                ActiveEffect(
                    id=spell.id, source=ref, kind="heal_max",
                    expires=spell_expiry(engine, ref, spell),
                )
            )
        names.append(engine.name(one_ref))
    engine.log(f"{engine.name(ref)}: {spell.name} на {', '.join(names)}")
    return []


CASTERS = {
    "attack": cast_attack, "mark": cast_mark, "rider": cast_rider, "darts": cast_darts,
    "area": cast_area, "heal": cast_heal, "buff": cast_buff,
    "save": cast_effects.cast_save, "condition": cast_conditions.cast_condition,
    "cure": cast_conditions.cast_cure, "temp_hp": cast_effects.cast_temp_hp,
    "defense": cast_effects.cast_defense, "rays": cast_effects.cast_rays,
    "teleport": cast_effects.cast_teleport, "stabilize": cast_effects.cast_stabilize,
    "fog": cast_effects.cast_fog, "hazard": cast_effects.cast_hazard,
    "create_item": cast_effects.cast_create_item, "utility": cast_effects.cast_utility,
    "ward": cast_effects.cast_ward, "retreat": cast_effects.cast_retreat,
    "max_hp": cast_effects.cast_max_hp, "summon": summons.summon, "aura": cast_effects.cast_aura,
    "zone": cast_zones.cast_zone_spell, "sanctuary": cast_guards.cast_sanctuary,
    "bond": cast_guards.cast_guard, "see_invisible": cast_guards.cast_guard,
    "tempo": tempo.cast_tempo, "mirror_image": cast_motion.cast_mirror_image,
    "blink": cast_motion.cast_blink, "flight": cast_motion.cast_flight,
    "size": cast_motion.cast_size,
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
    if option.params.get("variant"):
        # выбранный тип урона или характеристика подставляются в эффект заклинания
        spell = with_variant(spell, option.params["variant"])
    # скрытность кончается с заклинанием; до него, чтобы Невидимость не сняла сама себя
    reveal(engine, ref)
    kind = spell_kind(spell)
    if kind in HOSTILE_KINDS:
        sanctuary.drop(engine, ref)
    return CASTERS[kind](engine, ref, spell, option.params["target"], circle)
