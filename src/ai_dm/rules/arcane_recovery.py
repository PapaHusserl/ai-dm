POOL = "arcane_recovery"
MAX_CIRCLE = 5


def recover(hero, registry) -> list[str]:
    # Магическое восстановление на коротком отдыхе: ячейки суммарным кругом до половины уровня
    # волшебника (вверх), не выше 5 круга, старший круг первым; строки лога, пусто -- нечего
    # возвращать или пул потрачен
    pool = hero.creature.resources.get(POOL)
    if pool is None or pool.current <= 0:
        return []
    budget = (hero.sheet.class_level("wizard") + 1) // 2
    restored = []
    for circle in range(MAX_CIRCLE, 0, -1):
        slots = hero.creature.resources.get(f"spell_slot:{circle}")
        if slots is None:
            continue
        while slots.current < slots.max and budget >= circle:
            slots.current += 1
            budget -= circle
            restored.append(circle)
    if not restored:
        return []
    pool.current -= 1
    words = []
    for circle in sorted(set(restored), reverse=True):
        count = restored.count(circle)
        words.append(f"ячейка {circle} круга" if count == 1 else f"ячейки {circle} круга ×{count}")
    return ["Магическое восстановление: " + ", ".join(words)]
