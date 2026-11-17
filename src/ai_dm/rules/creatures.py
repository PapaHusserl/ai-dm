# к20-тесты: единственное объявление
D20_KINDS = ("attack", "save", "check", "initiative", "death_save")


def is_hero(target) -> bool:
    return hasattr(target, "sheet")


def creature_of(target):
    # у героя состояние лежит в .creature, у существа цель и есть состояние
    if hasattr(target, "creature"):
        return target.creature
    return target


def end_concentration(creature) -> None:
    # снимает эффекты концентрации и саму концентрацию
    creature.concentration = None
    creature.active_effects = [
        e for e in creature.active_effects
        if e.expires is None or e.expires.kind != "concentration"
    ]


def live_effects(creature, now_s=None) -> list:
    # эффекты, не истёкшие по часам мира (seconds: value -- момент окончания); now_s None -- все
    return [
        e for e in creature.active_effects
        if now_s is None or e.expires is None or e.expires.kind != "seconds"
        or e.expires.value > now_s
    ]


def _alive(item, now_s) -> bool:
    return item.expires is None or item.expires.kind != "seconds" or item.expires.value > now_s


def purge_expired(bundle) -> None:
    # после сдвига часов: убирает истёкшие seconds из эффектов и состояний героев и NPC мира
    # (max_hp снимает expire_max_hp), вне боя -- и истёкших призванных (индекс в бою -- часть ref)
    now_s = bundle.world.clock.now_s
    creatures = [h.creature for h in bundle.heroes]
    creatures += [n.creature for n in bundle.world.npcs.values() if n.creature is not None]
    for creature in creatures:
        creature.active_effects = [
            e for e in creature.active_effects
            if e.kind == "max_hp" or _alive(e, now_s)
        ]
        creature.conditions = [c for c in creature.conditions if _alive(c, now_s)]
    if bundle.session.active_combat is None:
        for hero in bundle.heroes:
            hero.minions = [m for m in hero.minions if m.until_s is None or m.until_s > now_s]
