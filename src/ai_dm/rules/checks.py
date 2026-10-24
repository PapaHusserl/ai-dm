from ai_dm.content.models.common import SKILLS
from ai_dm.rules.derived import saving_throw_bonus, saving_throw_parts, skill_bonus, skill_parts
from ai_dm.rules.roll_pipeline import RollRequest, roll


def dc_for_category(category: str, registry) -> int:
    rows = registry.get("table", "dc").rows
    if category not in rows:
        raise ValueError(f"неизвестная категория сложности: {category!r}")
    return rows[category]


def pick_dc(category, dc, registry) -> int:
    # ровно одно из двух: категория или явная СЛ
    if (category is None) == (dc is None):
        raise ValueError("нужна ровно одна из двух: category или dc")
    if category is not None:
        return dc_for_category(category, registry)
    return dc


def skill_check(
    hero, registry, rng, skill, category=None, *, dc=None, tags=None,
    modifiers=None, rerollers=None, now_s=None, base_adv="normal", base_adv_label="",
):
    dc = pick_dc(category, dc, registry)
    request = RollRequest(
        kind="check",
        actor=hero,
        actor_id=hero.id,
        ability=SKILLS[skill],
        skill=skill,
        tags=tags or {},
        base_adv=base_adv,
        base_adv_label=base_adv_label,
        bonus=skill_bonus(hero, registry, skill),
        bonus_parts=skill_parts(hero, registry, skill),
        dc=dc,
        now_s=now_s,
    )
    return roll(request, rng, registry, modifiers=modifiers, rerollers=rerollers)


def saving_throw(
    hero, registry, rng, ability, category=None, *, dc=None, tags=None,
    modifiers=None, rerollers=None, now_s=None,
):
    dc = pick_dc(category, dc, registry)
    request = RollRequest(
        kind="save",
        actor=hero,
        actor_id=hero.id,
        ability=ability,
        tags=tags or {},
        bonus=saving_throw_bonus(hero, registry, ability),
        bonus_parts=saving_throw_parts(hero, registry, ability),
        dc=dc,
        now_s=now_s,
    )
    return roll(request, rng, registry, modifiers=modifiers, rerollers=rerollers)
