from ai_dm.rules.mortality_guard import mark_dead

MAX_EXHAUSTION = 6


def exhaustion_penalty(level: int) -> int:
    return -2 * level


def add_exhaustion(hero, levels: int = 1, *, now_s: int = 0, cause: str, intervene=None) -> int:
    if levels < 1:
        raise ValueError("levels должно быть >= 1")
    level = min(MAX_EXHAUSTION, hero.creature.exhaustion + levels)
    hero.creature.exhaustion = level
    if level == MAX_EXHAUSTION:
        # божественное вмешательство (ТЗ 4.2): бог спасает, истощение снижается на 1
        if intervene is not None and intervene(hero) is not None:
            hero.creature.exhaustion = MAX_EXHAUSTION - 1
            return hero.creature.exhaustion
        mark_dead(hero, cause, None, now_s)
    return level


def remove_exhaustion(creature, levels: int = 1) -> int:
    creature.exhaustion = max(0, creature.exhaustion - levels)
    return creature.exhaustion
