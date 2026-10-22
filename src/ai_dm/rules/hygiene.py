WASHED_FLAG = "washed"


def washed_at(world, hero_id):
    # момент последнего мытья героя (секунды мира) или None, если флага нет
    return world.flags.get(f"{WASHED_FLAG}:{hero_id}")


def mark_washed(world, hero, now_s) -> None:
    world.flags[f"{WASHED_FLAG}:{hero.id}"] = now_s
