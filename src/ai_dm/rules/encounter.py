from ai_dm.core.clock import DAY
from ai_dm.rules.derived import table_value

DIFFICULTY_TIERS = {"easy": "low", "normal": "moderate", "hard": "high"}


def tier_of(world, cfg) -> str:
    # сложность кампании из настроек мира; нет или неизвестна -- уровень из конфига
    return DIFFICULTY_TIERS.get(world.settings.get("difficulty"), cfg.encounter.tier)


def party_budget(levels, registry, tier) -> int:
    # бюджет боя в ПО: SRD 5.2, уровень сложности (low/moderate/high), по каждому герою
    return sum(table_value(registry, "encounter_budget", f"{level}:{tier}") for level in levels)


def enemy_cost(monster_id, registry) -> int:
    return table_value(registry, "cr_xp", registry.get("monster", monster_id).cr)


def danger_marked(world, location_id) -> bool:
    # warn_danger по локации боя или по её предку
    marked = {mark.location_id for mark in world.dangers}
    seen = set()
    while location_id is not None and location_id in world.locations and location_id not in seen:
        if location_id in marked:
            return True
        seen.add(location_id)
        location_id = world.locations[location_id].parent_id
    return False


def find_trigger(bundle, ref):
    # триггер по ref вида trigger:<владелец>:<id>; нет -- None
    _, owner_id, trigger_id = ref.split(":", 2)
    world = bundle.world
    owner = world.npcs.get(owner_id) or world.factions.get(owner_id) or world.pantheon.get(owner_id)
    if owner is None:
        owner = next((h for h in bundle.heroes if h.id == owner_id), None)
    if owner is None:
        return None
    return next((t for t in owner.opportunity if t.id == trigger_id), None)


def kills_hero_fired(bundle) -> bool:
    # за последние сутки сработал триггер с целью убить героя
    world = bundle.world
    for item in world.fired:
        if world.clock.now_s - item.at_s > DAY or not item.ref.startswith("trigger:"):
            continue
        trigger = find_trigger(bundle, item.ref)
        if trigger is not None and trigger.kills_hero:
            return True
    return False


def override_reason(bundle, location_id, initiated_by) -> str | None:
    # основание для боя сверх бюджета (ТЗ 2.3); None -- оснований нет
    if danger_marked(bundle.world, location_id):
        return "warn_danger"
    if initiated_by == "hero":
        return "hero"
    if kills_hero_fired(bundle):
        return "kills_hero"
    return None


def fit_to_budget(enemies, leaders, budget, registry):
    # враги убираются с конца списка, лидеры остаются; (враги, "leader" | None):
    # "leader" -- даже одни лидеры не влезают: остаются только лидеры, рядовые урезаны
    costs = [enemy_cost(spec.monster_id, registry) for spec in enemies]
    total = sum(costs)
    dropped = set()
    for index in reversed(range(len(enemies))):
        if total <= budget:
            break
        if enemies[index].ref in leaders:
            continue
        dropped.add(index)
        total -= costs[index]
    if total > budget:
        return [spec for spec in enemies if spec.ref in leaders], "leader"
    return [spec for index, spec in enumerate(enemies) if index not in dropped], None


TIER_WORDS = {"low": "лёгкий", "moderate": "умеренный", "high": "тяжёлый"}

REASON_WORDS = {
    "hero": "напал ты",
    "warn_danger": "было предупреждение об опасности",
    "kills_hero": "сюжетная угроза",
    "leader": "лидеры сильнее бюджета",
}


def counts_text(specs, registry) -> str:
    # «гоблин ×3»: враги по видам монстров, в порядке появления
    counts = {}
    for spec in specs:
        counts[spec.monster_id] = counts.get(spec.monster_id, 0) + 1
    names = []
    for monster_id, count in counts.items():
        name = monster_id
        if registry.has("monster", monster_id):
            name = registry.get("monster", monster_id).name
        names.append(f"{name} ×{count}")
    return ", ".join(names)


def budget_text(level, budget, enemies, registry, tier) -> str:
    # «Бюджет боя: 225 ПО (ур. 3, умеренный); враги: 150 ПО (гоблин 50 ×3)»
    counts = {}
    for spec in enemies:
        counts[spec.monster_id] = counts.get(spec.monster_id, 0) + 1
    parts = []
    total = 0
    for monster_id, count in counts.items():
        cost = enemy_cost(monster_id, registry)
        total += cost * count
        parts.append(f"{registry.get('monster', monster_id).name} {cost} ×{count}")
    tier = TIER_WORDS.get(tier, tier)
    return (
        f"Бюджет боя: {budget} ПО (ур. {level}, {tier}); "
        f"враги: {total} ПО ({', '.join(parts)})"
    )
