from ai_dm.rules.derived import passive_perception
from ai_dm.state.world import Hidden, PlacedTrap


def is_hostile(world, location_id) -> bool:
    # метка hostile у самой локации или у предка по parent_id
    place = world.locations.get(location_id)
    seen = set()
    while place is not None and place.id not in seen:
        if place.hostile:
            return True
        seen.add(place.id)
        place = world.locations.get(place.parent_id)
    return False


def cut_route(world, route):
    # путь обрывается на первой враждебной локации, где скрытое ещё не расставлено
    for index, (location_id, _) in enumerate(route):
        if world.locations[location_id].hidden is None and is_hostile(world, location_id):
            return route[: index + 1]
    return route


def roll_traps(ctx, level) -> list[str]:
    # id ловушек реестра по броску к6 и уровню героя; без повторов
    config = ctx.cfg.traps
    roll = ctx.rng.randbelow(6) + 1
    count = 0 if roll < config.one_from else 1 if roll < config.two_from else 2
    pool = [
        trap_id for trap_id in ctx.registry.ids("trap")
        if ctx.registry.get("trap", trap_id).levels[0] <= level
        <= ctx.registry.get("trap", trap_id).levels[1]
    ]
    picked = []
    while len(picked) < min(count, len(pool)):
        trap_id = pool[ctx.rng.randbelow(len(pool))]
        if trap_id not in picked:
            picked.append(trap_id)
    return picked


def notice_traps(ctx, traps) -> None:
    # пассивная Внимательность героя против СЛ обнаружения; Анализ пассивно не находит
    passive = passive_perception(ctx.hero, ctx.registry)
    for trap in traps:
        detect = ctx.registry.get("trap", trap.trap_id).detect
        if detect.skill == "perception" and passive >= detect.dc:
            trap.state = "found"


def place(ctx, location) -> None:
    # расстановка: ловушки пака ровно как заданы, иначе бросок по таблице
    level = ctx.hero.sheet.level
    ids = location.traps or roll_traps(ctx, level)
    traps = [PlacedTrap(id=f"t{n}", trap_id=trap_id) for n, trap_id in enumerate(ids, 1)]
    notice_traps(ctx, traps)
    location.hidden = Hidden(level=level, traps=traps)


def enter(ctx, location_id) -> str:
    # первый вход героя в локацию; возвращает сигнал рассказчику о найденных ловушках ("" -- нет)
    world = ctx.bundle.world
    location = world.locations[location_id]
    if location.hidden is not None or not is_hostile(world, location_id):
        return ""
    place(ctx, location)
    names = [
        ctx.registry.get("trap", t.trap_id).name for t in location.hidden.traps
        if t.state == "found"
    ]
    if not names:
        return ""
    return "Герой сразу заметил ловушки: " + ", ".join(names) + ". Опиши, как он их заметил."
