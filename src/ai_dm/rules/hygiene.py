from ai_dm.core.clock import DAY

WASHED_FLAG = "washed"
SMELLY = "smelly"


def washed_at(world, hero_id):
    # момент последнего мытья героя (секунды мира) или None, если флага нет
    return world.flags.get(f"{WASHED_FLAG}:{hero_id}")


def mark_washed(world, hero, now_s) -> None:
    world.flags[f"{WASHED_FLAG}:{hero.id}"] = now_s


def is_stale(world, hero, cfg, at) -> bool:
    # с последнего мытья прошло не меньше hygiene_days суток; без флага отсчёта нет
    washed = washed_at(world, hero.id)
    # отсчёт от начала суток мытья: тик идёт в полночь, вонь приходит ровно через hygiene_days
    return washed is not None and at - washed // DAY * DAY >= cfg.services.hygiene_days * DAY
