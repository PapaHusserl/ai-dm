from ai_dm.core.dice import roll_dice
from ai_dm.rules.creatures import end_concentration
from ai_dm.rules.derived import (
    ability_mod,
    ability_part,
    always_prepared,
    effect_amount,
    free_cast_pool,
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


def cast_problem(hero, spell, circle, free, registry, cast_checks):
    # почему герой не может сотворить заклинание: (код, сообщение) или None
    if spell.level == 0:
        if spell.id not in hero.sheet.known_of():
            return ("not_known", f"заговор {spell.name} герой не знает")
    else:
        prepared = list(hero.sheet.prepared_of()) + always_prepared(hero, registry)
        if spell.id not in prepared:
            return ("not_prepared", f"заклинание {spell.name} не подготовлено")
    if circle != spell.level:
        return (
            "bad_circle",
            f"{spell.name}: круг заклинания {spell.level}, а запрошен {circle} "
            "(0 для заговоров); повышение круга не поддерживается",
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
    pool = hero.creature.resources.get(f"spell_slot:{spell.level}")
    if pool is None or pool.current <= 0:
        return ("no_slot", f"нет ячейки {spell.level} круга для {spell.name}")
    return None


def spend_cast(hero, registry, spell, free) -> None:
    # бесплатное использование тратится первым, ячейка остаётся
    if spell.level == 0:
        return
    if free:
        hero.creature.resources[free_cast_pool(hero, registry, spell.id)].current -= 1
    else:
        hero.creature.resources[f"spell_slot:{spell.level}"].current -= 1


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


def roll_heal(spell, hero, registry, rng) -> tuple[int, str]:
    # лечение заклинания: (сколько восстановить, «2d8 (6+5) + 2 Мдр = 13»)
    effect = effect_of(spell, "heal")
    rolled = roll_dice(effect.dice, rng)
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


def start_concentration(hero, world, spell, circle) -> None:
    # новое заклинание с концентрацией сбрасывает прежнее
    if hero.creature.concentration is not None:
        drop_concentration(hero, world)
    hero.creature.concentration = Concentration(spell_id=spell.id, circle=circle)


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
