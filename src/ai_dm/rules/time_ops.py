import heapq

from ai_dm.config.settings import RulesConfig
from ai_dm.core.clock import DAY, GameClock


def rounds_to_seconds(rounds: int, cfg: RulesConfig) -> int:
    return rounds * cfg.time.round_s


def short_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.short_rest_s


def long_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.long_rest_s


def category_seconds(category: str, clock: GameClock, cfg: RulesConfig) -> int:
    if category == "month":
        return clock.days_in_current_month() * DAY
    if category not in cfg.time.advance_categories:
        raise ValueError(f"неизвестная категория времени: {category!r}")
    return cfg.time.advance_categories[category]


DAY_PART_NAMES = {"morning": "утро", "day": "день", "evening": "вечер", "night": "ночь"}


def day_part(now_s: int, cfg: RulesConfig) -> str:
    # часть суток словом; ночь -- с часа night и до утра
    hour = now_s % DAY // 3600
    starts = cfg.time.day_parts
    if hour >= starts["night"] or hour < starts["morning"]:
        return DAY_PART_NAMES["night"]
    for key in ("evening", "day"):
        if hour >= starts[key]:
            return DAY_PART_NAMES[key]
    return DAY_PART_NAMES["morning"]


def travel_seconds(distance_m: int, pace: str, cfg: RulesConfig) -> int:
    if pace not in cfg.time.travel_pace:
        raise ValueError(f"неизвестный темп: {pace!r}")
    if distance_m < 0:
        raise ValueError("дистанция не может быть отрицательной")
    return -(-(distance_m * 3600) // cfg.time.travel_pace[pace])


def route_path(world, from_id: str, to_id: str) -> list[tuple[str, int]] | None:
    # кратчайший путь по карте (сумма distance_m, связи в обе стороны); при равной длине
    # остаётся первый найденный путь. Ответ -- переходы (id, distance_m) без старта:
    # [] -- старт и есть цель, None -- пути нет
    edges: dict[str, list[tuple[str, int]]] = {}
    for place in world.locations.values():
        for c in place.connections:
            if c.to in world.locations:
                edges.setdefault(place.id, []).append((c.to, c.distance_m))
                edges.setdefault(c.to, []).append((place.id, c.distance_m))
    best = {from_id: 0}
    came: dict[str, tuple[str, int]] = {}
    queue = [(0, from_id)]
    while queue:
        dist, here = heapq.heappop(queue)
        if dist > best[here]:
            continue
        if here == to_id:
            break
        for other, d in edges.get(here, []):
            if dist + d < best.get(other, dist + d + 1):
                best[other] = dist + d
                came[other] = (here, d)
                heapq.heappush(queue, (dist + d, other))
    if to_id not in best:
        return None
    path = []
    current = to_id
    while current != from_id:
        previous, d = came[current]
        path.append((current, d))
        current = previous
    return path[::-1]


def advance_by_category(clock: GameClock, category: str, cfg: RulesConfig) -> int:
    seconds = category_seconds(category, clock, cfg)
    clock.advance(seconds)
    return seconds


def ensure_min_advance(clock: GameClock, scene_start_s: int, cfg: RulesConfig) -> int:
    if clock.now_s != scene_start_s:
        return 0
    clock.advance(cfg.time.min_advance_s)
    return cfg.time.min_advance_s
