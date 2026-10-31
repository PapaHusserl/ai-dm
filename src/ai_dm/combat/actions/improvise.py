from typing import get_args

from ai_dm.combat import disarm, downed, falling, shove
from ai_dm.combat.actions.attack import roll_damage, split_dice
from ai_dm.core.events import DomainEvent
from ai_dm.rules.checks import dc_for_category, skill_check
from ai_dm.rules.names import SKILL_NAMES
from ai_dm.rules.results import Rejected
from ai_dm.state.combat import ImproviseEffect
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

# фиксированный набор эффектов (ТЗ 7); какие из них требуют цель и зону
EFFECTS = get_args(ImproviseEffect)
NEEDS_TARGET = ("prone", "extra_damage", "push", "disarm")
# подписи эффектов в логе; «prone» берётся из названия состояния в реестре
EFFECT_WORDS = {
    "advantage": "преимущество", "extra_damage": "доп. урон", "push": "толчок",
    "disarm": "обезоруживание",
}


# отказы движка, понятные рассказчику (в лог боя вместо кода)
REJECT_WORDS = {
    "target_too_large": "Слишком велик, чтобы сбить с ног или оттолкнуть: "
    "цель больше героя минимум на два размера",
}


def rejected(reason) -> Rejected:
    return Rejected(reason=reason, report_tag=None)


def spec_problem(state, effect, target, zone) -> str | None:
    # проверка эффекта, цели и зоны по состоянию боя; код отказа или None
    if effect not in EFFECTS:
        return "unknown_effect"
    zones = {q.ref: q.zone_id for q in state.participants}
    if effect in NEEDS_TARGET and (target is None or target not in zones):
        return "target_required"
    if effect == "push":
        if zone is None:
            return "zone_required"
        target_zone = [z for z in state.zones if z.id == zones[target]][0]
        if zone not in target_zone.adjacent:
            return "zone_not_adjacent"
    return None


def size_problem(engine, ref, effect, target) -> str | None:
    # толчок и «сбить с ног» -- только цели не больше чем на одну категорию размера крупнее
    if effect in ("push", "prone") and not shove.size_ok(engine, ref, target):
        return "target_too_large"
    return None


def check_request(engine, ref, effect, target, zone):
    # возвращает Rejected или None; ничего не бросает и не тратит
    p = engine.part(ref)
    if ref not in engine.heroes:
        return rejected("not_a_hero")
    if p.status != "active" or not p.turn.action:
        return rejected("not_available")
    problem = spec_problem(engine.state, effect, target, zone) or size_problem(
        engine, ref, effect, target
    )
    return None if problem is None else rejected(problem)


def improvise(engine, ref, *, skill, category, effect, target=None, zone=None):
    bad = check_request(engine, ref, effect, target, zone)
    if bad is not None:
        return bad
    # неизвестная категория -- ValueError до броска
    dc_for_category(category, engine.registry)
    engine.part(ref).turn.action = False
    hero = engine.heroes[ref]
    result = skill_check(hero, engine.registry, engine.rng, skill, category)
    word = EFFECT_WORDS.get(effect) or engine.registry.get("condition", effect).name
    skill_word = SKILL_NAMES[skill]
    engine.log(f"{engine.name(ref)}: импровизация ({word}), {skill_word}: {result.log.text}")
    events = []
    if result.outcome == "success":
        events += APPLY[effect](engine, ref, target, zone)
    return engine.finish(events)


def apply_advantage(engine, ref, target, zone) -> list[DomainEvent]:
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id="improvised_advantage", source=ref, kind="modifier",
            params={"target": "attack_roll", "mode": "advantage", "consume": True},
            # до конца следующего хода героя: этот конец хода пропускается
            expires=Expiry(kind="end_of_turn", value=1, owner=ref),
        )
    )
    return []


def apply_prone(engine, ref, target, zone) -> list[DomainEvent]:
    if engine.impose(target, AppliedCondition(id="prone", source=ref)):
        engine.log(f"  {engine.name(target)} сбит с ног")
    return []


def apply_extra_damage(engine, ref, target, zone) -> list[DomainEvent]:
    dice, bonus = split_dice(engine.cfg.combat.improvise_damage_dice)
    rolled = roll_damage(engine, ref, dice, bonus, False)
    dealt = engine.damage(target, rolled.total, "bludgeoning")
    engine.log_notes(dealt)
    engine.log(f"  {engine.name(target)}: {engine.hp_text(target)}")
    return downed.after_damage(engine, target, dealt, ref)


def apply_push(engine, ref, target, zone) -> list[DomainEvent]:
    return falling.push(engine, ref, target, zone)


def apply_disarm(engine, ref, target, zone) -> list[DomainEvent]:
    # исход общий с действием disarm; выбивается первое оружие цели
    weapons = disarm.weapon_ids(engine, target)
    if not weapons:
        engine.log(f"  {engine.name(target)}: нечего выбивать")
        return []
    grab = engine.heroes[ref].equipped.main_hand is None
    disarm.disarm_target(engine, ref, target, weapons[0], grab)
    return []


APPLY = {
    "advantage": apply_advantage, "prone": apply_prone, "extra_damage": apply_extra_damage,
    "push": apply_push, "disarm": apply_disarm,
}
