from ai_dm.combat import downed, mastery, monster_traits
from ai_dm.combat.actions import features
from ai_dm.combat.zones import cover_dc_bonus, distance, range_band_ft
from ai_dm.core.dice import parse_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.damage import DamageResult
from ai_dm.rules.derived import (
    ability_modifier,
    attack_bonus,
    attack_parts,
    damage_bonus,
    damage_parts,
    hero_effects,
    hero_feature_ids,
    improvised_attack,
    unarmed_attack,
)
from ai_dm.rules.inventory import equip, remove_item
from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS, RollRequest, roll
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry


class AttackInfo:
    # одна атака участника: оружие героя или действие монстра
    def __init__(
        self, id, kind, bonus, dice, damage_bonus, damage_type, weapon_id=None,
        advantage_dice=None, range_normal_ft=None, range_long_ft=None, name="",
        bonus_parts=None, damage_parts=None, action=None,
    ):
        self.id = id
        self.kind = kind
        self.bonus = bonus
        self.dice = dice
        self.damage_bonus = damage_bonus
        self.damage_type = damage_type
        # только у героя: id оружия (для мастерства)
        self.weapon_id = weapon_id
        # только у монстра: добавка к урону при броске атаки с преимуществом
        self.advantage_dice = advantage_dice
        self.range_normal_ft = range_normal_ft
        self.range_long_ft = range_long_ft
        # название оружия/действия и слагаемые бонусов (для строк броска)
        self.name = name
        self.bonus_parts = bonus_parts or []
        self.damage_parts = damage_parts or []
        # только у монстра: действие из статблока (доп. урон, эффект при попадании)
        self.action = action


def split_dice(expr: str) -> tuple[str, int]:
    # "1d6+2" -> ("1d6", 2)
    parsed = parse_dice(expr)
    return f"{parsed.count}d{parsed.sides}", parsed.modifier


def action_id(name: str) -> str:
    return name.lower().replace(" ", "_")


def attacks_of(engine, ref) -> list[AttackInfo]:
    if engine.is_hero(ref):
        hero = engine.heroes[ref]
        # любое своё оружие: оружие в руке первым, остальные из инвентаря
        weapon_ids = []
        if hero.equipped.main_hand is not None:
            weapon_ids.append(hero.equipped.main_hand)
        for entry in hero.inventory:
            if engine.registry.has("weapon", entry.item_id) and entry.item_id not in weapon_ids:
                weapon_ids.append(entry.item_id)
        result = []
        for weapon_id in weapon_ids:
            weapon = engine.registry.get("weapon", weapon_id)
            busy_hand = hero.equipped.shield is not None or hero.equipped.off_hand is not None
            two_handed = "two_handed" in weapon.properties
            if weapon_id != hero.equipped.main_hand and two_handed and busy_hand:
                continue
            result.append(
                AttackInfo(
                    weapon_id, weapon.kind, attack_bonus(hero, engine.registry, weapon_id),
                    weapon.damage_dice, damage_bonus(hero, engine.registry, weapon_id),
                    weapon.damage_type, weapon_id=weapon_id,
                    range_normal_ft=weapon.range_normal_ft, range_long_ft=weapon.range_long_ft,
                    name=weapon.name.lower(),
                    bonus_parts=attack_parts(hero, engine.registry, weapon_id),
                    damage_parts=damage_parts(hero, engine.registry, weapon_id),
                )
            )
        # безоружный и импровизированное оружие есть всегда (SRD 5.2)
        unarmed = unarmed_attack(hero, engine.registry)
        result.append(
            AttackInfo(
                "unarmed", "melee", unarmed[0], None, unarmed[2], "bludgeoning",
                name="безоружный удар", bonus_parts=unarmed[1], damage_parts=unarmed[3],
            )
        )
        strength, parts = improvised_attack(hero)
        result.append(
            AttackInfo(
                "improvised", "melee", strength, "1d4", strength, "bludgeoning",
                name="импровизированное оружие", bonus_parts=parts, damage_parts=parts,
            )
        )
        result.append(
            AttackInfo(
                "improvised_thrown", "ranged", strength, "1d4", strength, "bludgeoning",
                range_normal_ft=20, range_long_ft=60, name="бросок подручного предмета",
                bonus_parts=parts, damage_parts=parts,
            )
        )
        return result
    all_lost, lost = lost_weapons(engine, ref)
    result = []
    for action in engine.monster(ref).actions:
        if action.attack_bonus is None or action.damage_dice is None:
            continue
        if action.weapon_id is not None and (all_lost or action.weapon_id in lost):
            continue
        dice, bonus = split_dice(action.damage_dice)
        result.append(
            AttackInfo(
                action_id(action.name), action.kind, action.attack_bonus, dice, bonus,
                action.damage_type or "bludgeoning", advantage_dice=action.advantage_damage_dice,
                range_normal_ft=action.range_normal_ft, range_long_ft=action.range_long_ft,
                name=action.name.lower(), bonus_parts=[("бонус атаки", action.attack_bonus)],
                damage_parts=[("", bonus)], action=action,
            )
        )
    # бить нечем (оружие отобрано, естественных атак нет): кулак
    if (all_lost or lost) and not result:
        result += monster_unarmed(engine, ref)
    return result


def lost_weapons(engine, ref) -> tuple[bool, list[str]]:
    # (отключены ли все оружейные действия, id отобранного оружия); флаг без weapon_id --
    # старый сейв, тогда отключены все оружейные действия
    flags = [e for e in engine.creature(ref).active_effects if e.id == "disarmed"]
    all_lost = any("weapon_id" not in e.params for e in flags)
    lost = [e.params["weapon_id"] for e in flags if "weapon_id" in e.params]
    # equipment задан -- оружия действий, которого в нём нет, у существа нет
    worn = engine.equipment(ref) if engine.monster_of(ref) else None
    if worn is not None:
        for action in engine.monster(ref).actions:
            weapon_id = action.weapon_id
            if weapon_id is not None and weapon_id not in worn.weapons and weapon_id not in lost:
                lost.append(weapon_id)
    return all_lost, lost


def monster_unarmed(engine, ref) -> list[AttackInfo]:
    # оружие отобрано: гуманоид бьёт кулаком, 1 + Сила, мастерство по конфигу
    monster = engine.monster(ref)
    if monster.creature_type not in engine.cfg.disarm.unarmed_types:
        return []
    strength = ability_modifier(monster.abilities["str"])
    proficiency = engine.cfg.disarm.unarmed_proficiency
    return [
        AttackInfo(
            "unarmed", "melee", strength + proficiency, None, max(0, 1 + strength),
            "bludgeoning", name="безоружный удар",
            bonus_parts=[("Сил", strength), ("мастерство", proficiency)],
            damage_parts=[("", 1), ("Сил", strength)],
        )
    ]


def attack_targets(engine, ref) -> list[str]:
    # враги другой стороны: боеспособные и лежащие
    side = engine.part(ref).side
    return [
        p.ref for p in engine.state.participants
        if p.side != side and p.status in ("active", "down", "surrendered")
    ]


def base_advantage(engine, ref, target_ref, info) -> str | None:
    # None -- атаковать нельзя; иначе "normal" или "disadvantage"
    steps = distance(engine.state.zones, engine.part(ref).zone_id, engine.part(target_ref).zone_id)
    if info.kind == "melee":
        if steps == 0:
            return "normal"
        return None
    band = range_band_ft(steps)
    if band <= (info.range_normal_ft or 0):
        advantage = "normal"
    elif info.range_long_ft is not None and band <= info.range_long_ft:
        advantage = "disadvantage"
    else:
        return None
    if engine.enemy_nearby(ref):
        advantage = "disadvantage"
    return advantage


def base_label(engine, ref, target_ref, info) -> str:
    # откуда базовая помеха: «дальность», «враг рядом»
    if info.kind == "melee":
        return ""
    steps = distance(engine.state.zones, engine.part(ref).zone_id, engine.part(target_ref).zone_id)
    labels = []
    if range_band_ft(steps) > (info.range_normal_ft or 0):
        labels.append("дальность")
    if engine.enemy_nearby(ref):
        labels.append("враг рядом")
    return ", ".join(labels)


def reveal(engine, ref) -> None:
    # скрытность кончается с первой атакой или заклинанием
    creature = engine.creature(ref)
    hidden = [c for c in creature.conditions if c.id == "invisible" and c.source == "hidden"]
    if not hidden:
        return
    creature.conditions = [c for c in creature.conditions if c not in hidden]
    engine.log(f"  {engine.name(ref)} больше не скрыт")


def attack_tags(engine, ref, target_ref) -> dict:
    # «вплотную» = та же зона; укрытие цели работает только из другой зоны
    own = engine.part(ref).zone_id
    other = engine.part(target_ref).zone_id
    tags = {"melee": True}
    if own != other:
        zone = [z for z in engine.state.zones if z.id == other][0]
        own_zone = [z for z in engine.state.zones if z.id == own][0]
        tags = {"melee": False, "cover": cover_dc_bonus(zone)}
        height = own_zone.elevation - zone.elevation
        if height != 0:
            tags["height"] = height
    if monster_traits.pack_ally(engine, ref, target_ref) is not None:
        tags["pack"] = True
    return tags


def roll_attack(
    engine, ref, target_ref, bonus, base_adv, label="", parts=None, dc=None, dc_note="",
    base_note=""
):
    if dc is None:
        dc = engine.armor_class(target_ref)
    request = RollRequest(
        kind="attack", actor=engine.actor(ref), actor_id=ref, target=engine.actor(target_ref),
        target_id=target_ref, tags=attack_tags(engine, ref, target_ref), base_adv=base_adv,
        bonus=bonus, dc=dc, now_s=engine.world.clock.now_s,
        label=label, bonus_parts=parts or [], dc_note=dc_note, base_adv_label=base_note,
    )
    result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
    engine.log(f"{engine.name(ref)} -> {engine.name(target_ref)}: {result.log.text}")
    reveal(engine, ref)
    return result


def roll_damage(
    engine, ref, dice, bonus, crit, weapon=False, label="", parts=None, damage_type=""
):
    tags = {"crit": crit, "weapon": weapon}
    if ref in engine.state.savage_used:
        tags["savage_attacker_used"] = True
    request = RollRequest(
        kind="damage", actor=engine.actor(ref), actor_id=ref, dice=dice, bonus=bonus, tags=tags,
        label=label, bonus_parts=parts or [], damage_type=damage_type,
    )
    result = roll(request, engine.rng, engine.registry, modifiers=engine.modifiers)
    if weapon and result.rerolls:
        engine.state.savage_used.append(ref)
    engine.log(f"  {result.log.text}")
    return result


def attack_event(ref, target_ref, weapon, mode, outcome, damage) -> DomainEvent:
    data = {
        "attacker": ref, "target": target_ref, "weapon": weapon, "mode": mode,
        "outcome": outcome, "damage": damage,
    }
    return DomainEvent(type="attack", data=data)


def fixed_damage(engine, info) -> int:
    # урон без костей (безоружный удар): 1 + Сила, не ниже 0; крит ничего не удваивает
    text = ""
    for label, value in info.damage_parts:
        if text == "":
            text = str(value)
            continue
        sign = "-" if value < 0 else "+"
        text += f" {sign} {abs(value)}"
        if label:
            text += f" {label}"
    word = DAMAGE_TYPE_WORDS[info.damage_type]
    engine.log(f"  Урон ({info.name}): {text} = {info.damage_bonus} {word}")
    return info.damage_bonus


def colossus_damage(engine, ref, target_ref, crit, damage_type) -> int:
    # Убийца колоссов: тип урона оружия; раз в ход (флаг сбрасывается в начале любого хода)
    if not engine.is_hero(ref):
        return 0
    target = engine.creature(target_ref)
    turn = engine.part(ref).turn
    wounded = target.hp_current < target.hp_max
    for effect in hero_effects(engine.heroes[ref], engine.registry):
        if effect.type != "extra_damage" or effect.when != "target_wounded":
            continue
        if wounded and not turn.colossus_used:
            turn.colossus_used = True
            label = engine.registry.get("feature", "colossus_slayer").name
            return roll_damage(
                engine, ref, effect.dice, 0, crit, label=label, damage_type=damage_type
            ).total
    return 0


def mark_damage(engine, ref, target_ref, crit, dealt):
    # Метка охотника: при любом попадании броском атаки отдельный урон силовым полем;
    # возвращает общий DamageResult (основной урон + Метка)
    if not engine.is_hero(ref):
        return dealt
    for effect in engine.creature(target_ref).active_effects:
        if effect.kind != "mark" or effect.source != ref:
            continue
        name = engine.registry.get("spell", effect.id).name
        rolled = roll_damage(
            engine, ref, effect.params["dice"], 0, crit, label=name,
            damage_type=effect.params["damage_type"],
        )
        extra = engine.damage(target_ref, rolled.total, effect.params["damage_type"])
        dealt = merge_damage(dealt, extra)
    return dealt


def merge_damage(dealt, extra) -> DamageResult:
    return DamageResult(
        final=dealt.final + extra.final,
        temp_absorbed=dealt.temp_absorbed + extra.temp_absorbed,
        hp_lost=dealt.hp_lost + extra.hp_lost,
        was_down=dealt.was_down,
        dropped=dealt.dropped or extra.dropped,
        overkill=dealt.overkill + extra.overkill,
        raw=dealt.raw + extra.raw,
        notes=dealt.notes + extra.notes,
        damage_types=dealt.damage_types + extra.damage_types,
    )


def special_effects(engine, info, ammo) -> list[tuple[str, object]]:
    # эффекты оружия героя и выбранной стрелы: (название источника, эффект)
    result = []
    if info.weapon_id is not None and engine.registry.has("weapon", info.weapon_id):
        weapon = engine.registry.get("weapon", info.weapon_id)
        result += [(weapon.name, e) for e in weapon.effects]
    if ammo is not None:
        item = engine.registry.get("item", ammo)
        result += [(item.name, e) for e in item.effects]
    return result


def special_damage(engine, ref, target_ref, crit, dealt, effects):
    # доп. урон оружия и стрелы отдельными строками; vs -- только по целям с тегом
    for name, effect in effects:
        if effect.type != "extra_damage":
            continue
        if effect.vs and not set(effect.vs) & engine.tags(target_ref):
            continue
        rolled = roll_damage(
            engine, ref, effect.dice, 0, crit, label=name, damage_type=effect.damage_type
        )
        extra = engine.damage(target_ref, rolled.total, effect.damage_type)
        dealt = merge_damage(dealt, extra)
    return dealt


SIZES = ["tiny", "small", "medium", "large", "huge", "gargantuan"]


def target_size(engine, target_ref) -> str:
    if engine.is_hero(target_ref):
        species_id = engine.heroes[target_ref].sheet.species_id
        return engine.registry.get("species", species_id).size
    return engine.monster(target_ref).size


def weapon_rider(engine, ref, target_ref, info) -> None:
    # Опутывающий удар: заряд срабатывает на попадание оружием; безоружный удар -- не оружие
    if not engine.is_hero(ref) or info.id == "unarmed":
        return
    caster = engine.creature(ref)
    charges = [e for e in caster.active_effects if e.kind == "weapon_rider"]
    target = engine.creature(target_ref)
    if not charges or target.hp_current <= 0:
        return
    charge = charges[0]
    caster.active_effects.remove(charge)
    name = engine.registry.get("spell", charge.id).name
    params = charge.params
    engine.log(f"  {name}: лозы оплетают {engine.name(target_ref)}")
    # Большие и крупнее проходят спасбросок с преимуществом (SRD 5.2)
    base_adv = "normal"
    if SIZES.index(target_size(engine, target_ref)) >= SIZES.index("large"):
        base_adv = "advantage"
    saved = engine.save(target_ref, params["ability"], params["dc"], base_adv=base_adv)
    if saved.outcome == "success":
        engine.log(f"  {engine.name(target_ref)} стряхивает лозы, {name} кончается")
        end_concentration(caster)
        engine.drop_concentration_effects(ref)
        return
    expires = Expiry(kind="concentration", owner=ref)
    condition = AppliedCondition(id=params["condition"], source=ref, expires=expires)
    if not engine.impose(target_ref, condition):
        engine.log(f"  {name} кончается")
        end_concentration(caster)
        engine.drop_concentration_effects(ref)
        return
    target.active_effects.append(
        ActiveEffect(
            id=charge.id, source=ref, kind="ensnared",
            params={"dice": params["dice"], "damage_type": params["damage_type"],
                    "dc": params["dc"]},
            expires=expires,
        )
    )
    engine.log(f"  {engine.name(target_ref)} опутан")


def poison_immune(engine, target_ref) -> bool:
    # монстр или NPC со статблоком: иммунитет к состоянию «отравлен» или к урону ядом
    if not engine.monster_of(target_ref):
        return False
    monster = engine.monster(target_ref)
    return "poisoned" in monster.condition_immunities or "poison" in monster.damage_immunities


def sleep_arrow(engine, ref, target_ref, effect) -> None:
    # сонный яд: спасбросок Тел, провал -- отравлен и без сознания на срок в раундах
    name = engine.name(target_ref)
    if poison_immune(engine, target_ref):
        engine.log(f"  {name}: иммунитет к яду")
        return
    if engine.save(target_ref, "con", effect.dc).outcome == "success":
        engine.log(f"  {name} стряхивает сонный яд")
        return
    rounds = effect.duration_s // engine.cfg.time.round_s
    expires = Expiry(kind="rounds", value=rounds)
    engine.impose(target_ref, AppliedCondition(id="poisoned", source=ref, expires=expires))
    # отдельный срок: tick_rounds уменьшает value у каждого состояния
    engine.impose(
        target_ref,
        AppliedCondition(id="unconscious", source=ref, expires=expires.model_copy()),
    )
    engine.log(f"  {name}: отравлен, засыпает (без сознания до урона или {rounds} раундов)")


def arrow_conditions(engine, ref, target_ref, ammo, effects) -> None:
    # горение, замедление и сон от стрелы; на упавшую цель не накладываются
    if engine.creature(target_ref).hp_current <= 0:
        return
    target = engine.creature(target_ref)
    for _, effect in effects:
        if effect.type == "burn":
            target.active_effects.append(
                ActiveEffect(
                    id=ammo, source=ref, kind="burning",
                    params={"dice": effect.dice, "damage_type": effect.damage_type},
                    expires=Expiry(kind="start_of_turn", owner=target_ref),
                )
            )
            engine.log(f"  {engine.name(target_ref)} горит: ещё {effect.dice} огнём в начале хода")
        if effect.type == "slow":
            target.active_effects.append(
                ActiveEffect(
                    id=ammo, source=ref, kind="speed", params={"amount": -effect.value},
                    expires=Expiry(kind="end_of_turn", owner=target_ref),
                )
            )
            engine.log(
                f"  {engine.name(target_ref)}: скорость -{effect.value} фт "
                "до конца своего следующего хода"
            )
        if effect.type == "sleep":
            sleep_arrow(engine, ref, target_ref, effect)


def attack(
    engine, ref, target_ref, info, nonlethal=False, provoked=False, ammo=None
) -> list[DomainEvent]:
    base_adv = base_advantage(engine, ref, target_ref, info)
    effects = special_effects(engine, info, ammo)
    kinds = [e.type for _, e in effects]
    pierce = "pierce_armor" in kinds
    ac = engine.armor_class(target_ref, pierce, "ignore_magic_ac" in kinds)
    notes = []
    if pierce:
        notes.append("бронебойная")
    if ac != engine.armor_class(target_ref, pierce):
        notes.append("рассекает магические щиты")
    if ammo is not None:
        remove_item(engine.heroes[ref], ammo)
    result = roll_attack(
        engine, ref, target_ref, info.bonus, base_adv, info.name, info.bonus_parts, ac,
        ", ".join(notes), base_label(engine, ref, target_ref, info),
    )
    events = []
    if result.outcome in ("hit", "crit"):
        crit = result.outcome == "crit"
        if info.dice is None:
            total = fixed_damage(engine, info)
        else:
            rolled = roll_damage(
                engine, ref, info.dice, info.damage_bonus, crit, engine.is_hero(ref),
                label=f"Урон ({info.name})", parts=info.damage_parts,
                damage_type=info.damage_type,
            )
            total = rolled.total
        total += colossus_damage(engine, ref, target_ref, crit, info.damage_type)
        if result.advantage == "advantage" and info.advantage_dice is not None:
            total += roll_damage(
                engine, ref, info.advantage_dice, 0, crit, label=f"Урон ({info.name}, доп.)",
                damage_type=info.damage_type,
            ).total
        dealt = engine.damage(target_ref, total, info.damage_type)
        dealt = mark_damage(engine, ref, target_ref, crit, dealt)
        dealt = special_damage(engine, ref, target_ref, crit, dealt, effects)
        dealt = monster_traits.extra_damage(engine, (ref, target_ref), crit, dealt, info)
        dealt = monster_traits.on_hit(engine, (ref, target_ref), info, dealt, provoked)
        engine.log_notes(dealt)
        engine.log(f"  {engine.name(target_ref)}: {engine.hp_text(target_ref)}")
        events.append(
            attack_event(ref, target_ref, info.id, info.kind, result.outcome, dealt.final)
        )
        weapon_rider(engine, ref, target_ref, info)
        events += downed.after_damage(
            engine, target_ref, dealt, ref, crit=crit, nonlethal=nonlethal
        )
        # после урона: сон от стрелы не снимается её же попаданием
        arrow_conditions(engine, ref, target_ref, ammo, effects)
        events += mastery.on_hit(engine, ref, target_ref, info, dealt.final, provoked)
        return events
    graze, graze_events = mastery.on_miss(engine, ref, target_ref, info)
    events.append(attack_event(ref, target_ref, info.id, info.kind, "miss", graze))
    return events + graze_events


def spend_attack(engine, ref) -> None:
    # одна атака из действия Атака: первая тратит действие, вторая (Доп. атака) -- attacks_left
    turn = engine.part(ref).turn
    if turn.action:
        turn.action = False
        if engine.is_hero(ref) and "extra_attack" in hero_feature_ids(
            engine.heroes[ref], engine.registry
        ):
            turn.attacks_left = 1
    else:
        turn.attacks_left -= 1


def perform(engine, ref, option) -> list[DomainEvent]:
    spend_attack(engine, ref)
    info = [i for i in attacks_of(engine, ref) if i.id == option.params["weapon"]][0]
    holds_other = engine.is_hero(ref) and engine.heroes[ref].equipped.main_hand != info.id
    if holds_other and info.weapon_id is not None:
        # достать оружие -- часть действия Атака
        equip(engine.heroes[ref], info.id, engine.registry)
    events = attack(
        engine, ref, option.params["target"], info, option.params["nonlethal"],
        ammo=option.params.get("ammo"),
    )
    features.horde_mark(engine, ref, info, option.params["target"])
    return events
