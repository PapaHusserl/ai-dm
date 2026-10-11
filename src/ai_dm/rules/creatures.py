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
