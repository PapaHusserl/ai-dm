import heapq

from ai_dm.config.settings import RulesConfig
from ai_dm.core.clock import DAY, GameClock


def rounds_to_seconds(rounds: int, cfg: RulesConfig) -> int:
    return rounds * cfg.time.round_s


def short_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.short_rest_s


def long_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.long_rest_s


def turn_tick(clock: GameClock, start_s: int, cfg: RulesConfig) -> None:
    # ход без сдвига часов мастером -- четверть часа от движка
    if clock.now_s == start_s:
        clock.advance(cfg.time.turn_s)


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


def linked_edges(world, place) -> dict[str, list]:
    # рёбра места в обе стороны по id соседа (существующие локации): исходящие и входящие
    edges: dict[str, list] = {}
    for c in place.connections:
        edges.setdefault(c.to, []).append(c)
    for other in world.locations.values():
        for c in other.connections:
            if c.to == place.id:
                edges.setdefault(other.id, []).append(c)
    return {i: cs for i, cs in edges.items() if i in world.locations}


def hero_transport(hero) -> str | None:
    # род транспорта героя для route_path и nearby_locations; транспорта нет -- None
    return None if hero.transport is None else hero.transport.kind


def edge_seconds(distance_m: int, kind: str, pace: str, cfg: RulesConfig) -> int:
    # время ребра: метры пешком темпом pace, помноженные на процент рода пути; одно округление вверх
    percent = cfg.time.route_kinds[kind].percent
    return -(-(distance_m * 3600 * percent) // (cfg.time.travel_pace[pace] * 100))


def edge_open(c, cfg: RulesConfig, transport: str | None) -> bool:
    # ребро открыто: транспорт не нужен или это род транспорта его рода пути
    return not c.needs_transport or transport == cfg.time.route_kinds[c.kind].transport


def open_edges(world, cfg: RulesConfig, transport: str | None, pace: str) -> dict:
    # {id: [(сосед, секунды)]} по открытым рёбрам в обе стороны; рёбра к несуществующим пропущены
    edges: dict[str, list[tuple[str, int]]] = {}
    for place in world.locations.values():
        for c in place.connections:
            if c.to in world.locations and edge_open(c, cfg, transport):
                d = edge_seconds(c.distance_m, c.kind, pace, cfg)
                edges.setdefault(place.id, []).append((c.to, d))
                edges.setdefault(c.to, []).append((place.id, d))
    return edges


def route_path(
    world, from_id: str, to_id: str, cfg: RulesConfig, transport: str | None = None,
    pace: str = "normal",
) -> list[tuple[str, int]] | None:
    # быстрейший путь по карте (сумма секунд рёбер, связи в обе стороны); при равном времени
    # остаётся первый найденный путь. Ребро с needs_transport открыто, только если transport --
    # род транспорта его рода пути. Ответ -- переходы (id, seconds) без старта:
    # [] -- старт и есть цель, None -- пути нет
    edges = open_edges(world, cfg, transport, pace)
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


def closing_transport(
    world, from_id: str, to_id: str, cfg: RulesConfig, pace: str = "normal"
) -> str | None:
    # род транспорта, без которого пути нет: первый из [time.transports] по порядку конфига,
    # с которым route_path даёт путь; ни с одним -- None
    for transport in cfg.time.transports:
        if route_path(world, from_id, to_id, cfg, transport, pace) is not None:
            return transport
    return None


def minutes_text(seconds: int) -> str:
    # до часа -- «41 мин», от часа -- «1 ч 1 мин», ровно часы -- «2 ч»; минуты округляются вверх
    minutes = max(1, -(-seconds // 60))
    hours, minutes = divmod(minutes, 60)
    if not hours:
        return f"{minutes} мин"
    return f"{hours} ч" + (f" {minutes} мин" if minutes else "")


def advance_by_category(clock: GameClock, category: str, cfg: RulesConfig) -> int:
    seconds = category_seconds(category, clock, cfg)
    clock.advance(seconds)
    return seconds


def ensure_min_advance(clock: GameClock, scene_start_s: int, cfg: RulesConfig) -> int:
    if clock.now_s != scene_start_s:
        return 0
    clock.advance(cfg.time.min_advance_s)
    return cfg.time.min_advance_s
