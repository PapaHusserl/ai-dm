from ai_dm.config.settings import RulesConfig
from ai_dm.rules.time_ops import hero_transport, open_edges, route_path
from ai_dm.state.world import Location


def road_ends(world, journey, cfg: RulesConfig, transport: str | None = None) -> list:
    # выходы с ребра «дороги»: назад (узел, пройдено) и вперёд (узел, остаток) темпом пути;
    # ребра нет или оно закрыто -- только назад
    ends = [(journey.from_id, journey.edge_done_s)]
    edges = open_edges(world, cfg, transport, journey.pace).get(journey.from_id, [])
    times = [d for other, d in edges if other == journey.edge_to]
    if times:
        ends.append((journey.edge_to, min(times) - journey.edge_done_s))
    return ends


def road_path(
    world, journey, to_id: str, cfg: RulesConfig, transport: str | None = None
) -> list[tuple[str, int]] | None:
    # путь из «дороги»: выход с ребра и путь от него; меньшая сумма, при равенстве -- назад
    paths = []
    for end_id, seconds in road_ends(world, journey, cfg, transport):
        rest = route_path(world, end_id, to_id, cfg, transport, journey.pace)
        if rest is not None:
            paths.append([(end_id, seconds)] + rest)
    return min(paths, key=lambda path: sum(s for _, s in path), default=None)


def hero_route(world, hero, to_id: str, cfg: RulesConfig, pace: str):
    # путь героя к цели: из «дороги» -- road_path, из узла -- route_path (темп пути -- journey.pace)
    transport = hero_transport(hero)
    journey = hero.journey
    if journey is not None and hero.location_id == journey.road_id:
        return road_path(world, journey, to_id, cfg, transport)
    return route_path(world, hero.location_id, to_id, cfg, transport, pace)


def journey_left_s(world, hero, cfg: RulesConfig) -> int:
    # остаток пути до journey.to, секунд; пути нет -- 0
    journey = hero.journey
    return sum(s for _, s in hero_route(world, hero, journey.to, cfg, journey.pace) or [])


def leg_stop(route: list[tuple[str, int]], limit: int) -> tuple[int, int]:
    # отрезок в limit секунд по пути (он длиннее): (номер перехода, секунд пройдено по нему);
    # 0 -- отрезок кончился ровно в узле route[номер - 1]
    done = 0
    for index, (_, seconds) in enumerate(route):
        if done + seconds > limit:
            return index, limit - done
        done += seconds
    raise ValueError("путь не длиннее отрезка")


def open_road(world, journey, now_s: int) -> None:
    # временная локация пути: заведена при первой остановке между узлами, имя -- по текущей цели
    if not journey.road_id:
        shift = 0
        while f"road_{now_s + shift}" in world.locations:
            shift += 1
        journey.road_id = f"road_{now_s + shift}"
        world.locations[journey.road_id] = Location(
            id=journey.road_id, name="", temporary=True, origin="engine"
        )
    start = world.locations[journey.start_id].name
    world.locations[journey.road_id].name = f"Дорога: {start} — {world.locations[journey.to].name}"


def end_journey(world, hero) -> None:
    # путь окончен (пути нет -- ничего): journey снят; «дорога» убрана, ссылки на неё чисты,
    # вещи -- на узел героя
    journey, hero.journey = hero.journey, None
    road_id = journey and journey.road_id
    if not road_id:
        return
    del world.locations[road_id]
    for npc in world.npcs.values():
        if npc.location_id == road_id:
            npc.location_id = None
    for dead in [hero, *world.npcs.values()]:
        if dead.death is not None and dead.death.location_id == road_id:
            dead.death.location_id = None
    world.dangers = [mark for mark in world.dangers if mark.location_id != road_id]
    for item in world.custom_items.values():
        holder = item.holder
        if holder is not None and holder.location_id == road_id:
            holder.location_id = hero.location_id
            if holder.kind == "location":
                holder.ref = hero.location_id
