from ai_dm.core.dice import format_expr, parse_dice, roll_dice
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.derived import (
    ability_mod,
    ability_part,
    always_prepared,
    effect_amount,
    free_cast_pool,
    prepared_limit,
    spell_slots_for,
    spellcasting_ability,
)
from ai_dm.rules.names import ABILITY_SHORT
from ai_dm.rules.roll_pipeline import RollRequest, roll
from ai_dm.state.creature import ActiveEffect, Concentration, Expiry


def effect_of(spell, effect_type):
    for effect in spell.effects:
        if effect.type == effect_type:
            return effect
    return None


def spell_kind(spell) -> str | None:
    # вид заклинания по его данным; неизвестный вид в бою не используется
    if effect_of(spell, "rider") is not None:
        return "rider"
    if effect_of(spell, "extra_damage") is not None:
        return "mark"
    if effect_of(spell, "area") is not None:
        return "area"
    if effect_of(spell, "heal") is not None:
        return "heal"
    if effect_of(spell, "modifier") is not None:
        return "buff"
    damage = effect_of(spell, "damage")
    if damage is not None and damage.count:
        return "darts"
    if damage is not None:
        return "attack"
    return None


def free_cast_left(hero, registry, spell) -> bool:
    # есть бесплатное использование (Избранный враг для Метки охотника)
    pool_id = free_cast_pool(hero, registry, spell.id)
    pool = hero.creature.resources.get(pool_id)
    return pool is not None and pool.current > 0


def circle_allowed(spell, circle, free) -> bool:
    # круг заклинания, либо выше у заклинаний с усилением (не для бесплатного применения)
    if circle == spell.level:
        return True
    return spell.upcast is not None and not free and circle > spell.level


def upcast_steps(spell, circle) -> int:
    # на сколько кругов выше базового (0 без усиления)
    if spell.upcast is None or circle is None or circle <= spell.level:
        return 0
    return circle - spell.level


def upcast_dice(base, step, steps) -> str:
    # «2d8» + 2 x «2d8» = «6d8»; модификатор базы сохраняется
    one = parse_dice(base)
    extra = parse_dice(step)
    if one.sides != extra.sides:
        raise ValueError(f"разные грани костей: {base!r} и {step!r}")
    one.count += extra.count * steps
    return format_expr(one)


def usable_circles(hero, spell) -> list[int]:
    # круги, которыми герой может сотворить заклинание сейчас: [0] для заговора,
    # иначе круги с ячейкой
    if spell.level == 0:
        return [0]
    result = []
    # круги ячеек -- до 9
    for circle in range(spell.level, 10):
        pool = hero.creature.resources.get(f"spell_slot:{circle}")
        if pool is not None and pool.current > 0:
            result.append(circle)
    if spell.upcast is None:
        return [c for c in result if c == spell.level]
    return result


def cast_problem(hero, spell, circle, free, registry, cast_checks):
    # почему герой не может сотворить заклинание: (код, сообщение) или None
    if spell.level == 0:
        if spell.id not in hero.sheet.known_of():
            return ("not_known", f"заговор {spell.name} герой не знает")
    else:
        prepared = list(hero.sheet.prepared_of()) + always_prepared(hero, registry)
        if spell.id not in prepared:
            return ("not_prepared", f"заклинание {spell.name} не подготовлено")
    if not circle_allowed(spell, circle, free):
        return (
            "bad_circle",
            f"{spell.name}: круг {spell.level}, запрошен {circle}; повышение — только у "
            "заклинаний с усилением и не для бесплатного применения (0 для заговоров)",
        )
    for check in cast_checks.check(hero, spell.id, registry):
        if check.kind == "forbidden":
            return ("forbidden", f"{spell.name} недоступно: {check.reason}")
    if spell.level == 0:
        return None
    if free:
        if not free_cast_left(hero, registry, spell):
            return ("no_free_cast", f"нет бесплатных применений для {spell.name}")
        return None
    pool = hero.creature.resources.get(f"spell_slot:{circle}")
    if pool is None or pool.current <= 0:
        return ("no_slot", f"нет ячейки {circle} круга для {spell.name}")
    return None


def spend_cast(hero, registry, spell, free, circle) -> None:
    # бесплатное использование тратится первым, ячейка остаётся
    if spell.level == 0:
        return
    if free:
        hero.creature.resources[free_cast_pool(hero, registry, spell.id)].current -= 1
    else:
        hero.creature.resources[f"spell_slot:{circle}"].current -= 1


def roll_cast_checks(hero, spell, cast_checks, registry, rng, modifiers, now_s):
    # проверки перед сотворением (жрец и бог, ТЗ 4.2): (провалена ли, строки лога)
    lines = []
    for check in cast_checks.check(hero, spell.id, registry):
        if check.kind != "ability_check":
            continue
        request = RollRequest(
            kind="check", actor=hero, actor_id=hero.id, ability=check.ability,
            bonus=ability_mod(hero, check.ability), dc=check.dc, now_s=now_s,
            bonus_parts=[ability_part(hero, check.ability)],
        )
        result = roll(request, rng, registry, modifiers=modifiers)
        lines.append(f"  проверка {check.reason}: {result.log.text}")
        if result.outcome == "fail":
            return True, lines
    return False, lines


def roll_heal(spell, hero, registry, rng, circle=None) -> tuple[int, str]:
    # лечение заклинания: (сколько восстановить, «2d8 (6+5) + 2 Мдр = 13»)
    effect = effect_of(spell, "heal")
    dice = effect.dice
    steps = upcast_steps(spell, circle)
    if steps > 0:
        dice = upcast_dice(dice, spell.upcast.per_slot_level.dice, steps)
    rolled = roll_dice(dice, rng)
    bonus = effect_amount(effect, hero, registry)
    total = rolled.total + bonus
    text = f"{rolled.expr} ({'+'.join(str(n) for n in rolled.rolls)})"
    if effect.add == "spellcasting_modifier":
        label = ABILITY_SHORT[spellcasting_ability(hero, registry)]
        text += f" {'+' if bonus >= 0 else '-'} {abs(bonus)} {label}"
    elif bonus:
        text += f" {'+' if bonus > 0 else '-'} {abs(bonus)}"
    return total, f"{text} = {total}"


def drop_concentration(hero, world) -> None:
    # прежняя концентрация героя кончилась: снимаем её эффекты у героя и у NPC мира;
    # заряд weapon_rider на самом герое снимает end_concentration (expires -- concentration)
    old = hero.creature.concentration.spell_id
    end_concentration(hero.creature)
    hero.creature.active_effects = [
        e for e in hero.creature.active_effects if not (e.kind == "spell" and e.id == old)
    ]
    for npc in world.npcs.values():
        if npc.creature is None:
            continue
        npc.creature.active_effects = [
            e for e in npc.creature.active_effects
            if not (e.expires is not None and e.expires.kind == "concentration"
                    and e.expires.owner == hero.id)
        ]
        npc.creature.conditions = [
            c for c in npc.creature.conditions
            if not (c.expires is not None and c.expires.kind == "concentration"
                    and c.expires.owner == hero.id)
        ]


def start_concentration(hero, world, spell, circle, now_s=None) -> None:
    # новое заклинание с концентрацией сбрасывает прежнее; until_s -- конец по часам мира
    if hero.creature.concentration is not None:
        drop_concentration(hero, world)
    until_s = None
    if now_s is not None and spell.duration_s is not None:
        until_s = now_s + spell.duration_s
    hero.creature.concentration = Concentration(spell_id=spell.id, circle=circle, until_s=until_s)


def expire_concentration(hero, world) -> str | None:
    # срок концентрации вышел по часам мира (ровно в срок -- кончилась): снять, вернуть id
    concentration = hero.creature.concentration
    if concentration is None or concentration.until_s is None:
        return None
    if concentration.until_s > world.clock.now_s:
        return None
    drop_concentration(hero, world)
    return concentration.spell_id


def add_spell_duration(hero, spell, now_s) -> None:
    # длительность заклинания по часам мира: метка на герое до now_s + duration_s
    if spell.duration_s is None:
        return
    hero.creature.active_effects.append(
        ActiveEffect(
            id=spell.id, source=hero.id, kind="spell",
            expires=Expiry(kind="seconds", value=now_s + spell.duration_s),
        )
    )


def swap_problem(hero, registry, drop, take):
    # почему нельзя сменить подготовленные после длинного отдыха: (код, сообщение) или None
    sheet = hero.sheet
    spellcasting = registry.get("class", sheet.class_id).spellcasting
    if spellcasting is None or spellcasting.prepared_swap is None:
        return ("no_spellcasting", "у класса героя нет смены подготовленных заклинаний")
    swap = spellcasting.prepared_swap
    if swap != "all" and (len(drop) > swap or len(take) > swap):
        return ("swap_limit", f"за длинный отдых можно сменить не больше {swap} (следопыт — одно)")
    if len(set(drop)) != len(drop) or len(set(take)) != len(take):
        return ("bad_swap", "в списках drop и take есть повторы")
    max_circle = max(spell_slots_for(registry, spellcasting.progression, sheet.level), default=0)
    class_ids = [
        s.id for s in registry.all("spell")
        if sheet.class_id in s.classes and 1 <= s.level <= max_circle
    ]
    for spell_id in take:
        if not registry.has("spell", spell_id):
            ids = ", ".join(sorted(class_ids)[:20])
            return ("unknown_spell", f"нет заклинания {spell_id!r}; допустимые id: {ids}")
    always = always_prepared(hero, registry)
    for spell_id in drop:
        if spell_id not in sheet.prepared_of() or spell_id in always:
            return ("not_prepared", f"заклинание {spell_id} не подготовлено или снимать нельзя")
    for spell_id in take:
        spell = registry.get("spell", spell_id)
        if spell_id in sheet.prepared_of() or spell_id in always:
            return ("already_prepared", f"заклинание {spell.name} уже подготовлено")
        if sheet.class_id not in spell.classes or spell.level < 1 or spell.level > max_circle:
            return ("bad_spell", f"{spell.name}: не из списка класса, заговор или круг недоступен")
    limit = prepared_limit(hero, registry)
    if limit is not None and len(sheet.prepared_of()) - len(drop) + len(take) > limit:
        return ("prepared_limit", f"подготовленных заклинаний больше {limit}")
    return None


def swap_prepared(hero, registry, drop, take) -> None:
    # смена подготовленных (проверена swap_problem): источник -- список класса, как на уровне
    prepared = hero.sheet.prepared_of()
    prepared[:] = [s for s in prepared if s not in drop]
    for spell_id in take:
        prepared.append(spell_id)
        if spell_id not in hero.sheet.known_of():
            hero.sheet.known_of().append(spell_id)
