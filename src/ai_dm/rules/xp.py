from ai_dm.rules.derived import table_value
from ai_dm.rules.progression import max_level, xp_for_level


def combat_xp(defeated_monster_ids: list[str], registry) -> int:
    total = 0
    for monster_id in defeated_monster_ids:
        monster = registry.get("monster", monster_id)
        total += table_value(registry, "cr_xp", monster.cr)
    return total


def quest_xp(hero, scale: str, registry, cfg) -> int:
    # доля от размера текущего уровня; на максимальном уровне -- 0
    if scale not in ("minor", "medium", "major"):
        raise ValueError(f"неизвестный масштаб награды: {scale!r}")
    percent = getattr(cfg.xp, f"quest_{scale}_percent")
    level = hero.sheet.level
    if level >= max_level(registry):
        return 0
    span = xp_for_level(level + 1, registry) - xp_for_level(level, registry)
    return span * percent // 100
