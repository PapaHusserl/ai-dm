from collections.abc import Callable
from dataclasses import dataclass

from ai_dm.rules.creatures import live_effects
from ai_dm.rules.derived import ability_part, spellcasting_ability
from ai_dm.rules.roll_pipeline import RollRequest, roll

# заклинания до этого круга снимаются сами, выше -- проверка характеристики против СЛ 10 + круг
CHECK_BASE_DC = 10


@dataclass
class DispelEnv:
    # registry, now_s -- реестр и часы мира; circle -- круг ячейки Рассеивания;
    # level_of(spell_id, owner) -- круг заклинания на цели (концентрация владельца или базовый);
    # check(dc) -- проверка заклинателя: результат броска; ability -- «Инт» для строки лога
    registry: object
    now_s: int
    circle: int
    level_of: Callable[[str, str | None], int]
    check: Callable[[int], object]
    ability: str


def owner_of(thing) -> str | None:
    # чья концентрация держит заклинание
    if thing.expires is not None and thing.expires.kind == "concentration":
        return thing.expires.owner
    return None


def spells_on(creature, env) -> list[tuple[str, object]]:
    # (id заклинания, состояние или эффект): состояние -- по source, эффект -- по id
    found = [
        (c.source, c) for c in creature.conditions
        if c.source is not None and env.registry.has("spell", c.source)
    ]
    found += [
        (e.id, e) for e in live_effects(creature, env.now_s) if env.registry.has("spell", e.id)
    ]
    return found


def dispel(creature, env, pick) -> tuple[list[tuple[str, str | None]], list[tuple[str, int]]]:
    # снимает с существа заклинания, подходящие под pick(состояние или эффект);
    # возвращает ([(заклинание, владелец концентрации)] снятых, [(заклинание, СЛ, итог)] устоявших)
    groups = {}
    for spell_id, thing in spells_on(creature, env):
        if pick(thing):
            groups.setdefault((spell_id, owner_of(thing)), []).append(thing)
    removed, kept, gone = [], [], []
    for (spell_id, owner), things in groups.items():
        level = env.level_of(spell_id, owner)
        dc = CHECK_BASE_DC + level
        result = None if level <= env.circle else env.check(dc)
        if result is None or result.outcome == "success":
            removed.append((spell_id, owner))
            gone += [id(t) for t in things]
        else:
            kept.append((spell_id, dc, result.total))
    creature.conditions = [c for c in creature.conditions if id(c) not in gone]
    creature.active_effects = [e for e in creature.active_effects if id(e) not in gone]
    return removed, kept


def report(env, spell_name, target_name, found) -> list[str]:
    # строки лога Рассеивания по итогам dispel (found -- список его результатов)
    removed = list(dict.fromkeys(pair for done, _ in found for pair in done))
    kept = [pair for _, left in found for pair in left]
    prefix = f"  {spell_name}:"
    if not removed and not kept:
        return [f"{prefix} на {target_name} нет заклинаний"]
    lines = []
    if removed:
        names = ", ".join(env.registry.get("spell", s).name for s, _ in removed)
        lines.append(f"{prefix} снято {names} с {target_name}")
    for spell_id, dc, total in kept:
        held = env.registry.get("spell", spell_id).name
        lines.append(f"{prefix} {held} держится ({env.ability} {total} против СЛ {dc})")
    return lines


def caster_env(hero, registry, rolling, when) -> DispelEnv:
    # окружение Рассеивания героя: проверка его заклинательной характеристикой против СЛ;
    # rolling = (rng, modifiers; None -- по умолчанию), when = (часы мира, круг ячейки, level_of)
    rng, modifiers = rolling
    now_s, circle, level_of = when
    ability = spellcasting_ability(hero, registry)
    part = ability_part(hero, ability)

    def check(dc):
        request = RollRequest(
            kind="check", actor=hero, actor_id=hero.id, ability=ability, bonus=part[1],
            bonus_parts=[part], dc=dc,
        )
        return roll(request, rng, registry, modifiers=modifiers)

    return DispelEnv(registry, now_s, circle, level_of, check, part[0])
