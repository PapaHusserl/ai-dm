from ai_dm.combat import falling
from ai_dm.combat.actions.attack import spend_attack
from ai_dm.core.events import DomainEvent
from ai_dm.rules.derived import (
    ability_mod,
    ability_modifier,
    proficiency,
    saving_throw_bonus,
)
from ai_dm.rules.names import ABILITY_SHORT
from ai_dm.state.creature import ActiveEffect


def contest_dc(engine, ref, abilities) -> tuple[int, list]:
    # СЛ 8 + лучший мод. из abilities + БМ атакующего; вторым -- слагаемые для лога
    if engine.is_hero(ref):
        hero = engine.heroes[ref]
        mods = {a: ability_mod(hero, a) for a in abilities}
        bonus = proficiency(hero, engine.registry)
    else:
        scores = engine.monster(ref).abilities
        mods = {a: ability_modifier(scores[a]) for a in abilities}
        bonus = engine.cfg.disarm.unarmed_proficiency
    best = max(abilities, key=lambda a: mods[a])
    parts = [("", 8), (ABILITY_SHORT[best], mods[best]), ("мастерство", bonus)]
    return sum(value for _, value in parts), parts


def best_save_ability(engine, target) -> str:
    # Сил или Лов: у цели спасбросок лучше
    if engine.is_hero(target):
        hero = engine.heroes[target]
        return max(("str", "dex"), key=lambda a: saving_throw_bonus(hero, engine.registry, a))
    scores = engine.monster(target).abilities
    return max(("str", "dex"), key=lambda a: ability_modifier(scores[a]))


def may_shove(engine, ref) -> bool:
    # толчок -- вариант безоружного удара: тем же списком типов, что и кулак
    if engine.is_hero(ref) or not engine.is_capable(ref):
        return False
    return engine.monster(ref).creature_type in engine.cfg.disarm.unarmed_types


def perform(engine, ref, option) -> list[DomainEvent]:
    # атака тратится; СЛ 8 + Сил + БМ, спасбросок цели Сил/Лов; провал -- цель в соседней зоне
    target = option.params["target"]
    spend_attack(engine, ref)
    engine.creature(ref).active_effects.append(
        ActiveEffect(id="shove_used", source=ref, kind="flag")
    )
    dc, _ = contest_dc(engine, ref, ("str",))
    engine.log(f"{engine.name(ref)}: толчок → {engine.name(target)} (СЛ {dc})")
    ability = best_save_ability(engine, target)
    if engine.save(target, ability, dc).outcome == "fail":
        return falling.push(engine, ref, target, option.params["zone"])
    engine.log(f"  {engine.name(target)} устоял")
    return []
