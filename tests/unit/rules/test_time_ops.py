# Ожидаемый API: ai_dm.rules.time_ops (cfg: RulesConfig -- обязательный аргумент, без fallback
#   на defaults.toml, аудит 1 п. 2.8; в тестах cfg передаётся по имени, фикстура cfg -- conftest)
#   rounds_to_seconds(rounds: int, cfg) -> int             -- rounds * cfg.time.round_s (6)
#   short_rest_seconds(cfg) -> int                         -- 3600
#   long_rest_seconds(cfg) -> int                          -- 28800
#   category_seconds(category: str, clock: GameClock, cfg) -> int
#       "hour" (3600, P1: не закрывает сцену) | "day" | "week" | "month";
#       hour/day/week -- из
#       cfg.time.advance_categories; "month" -- clock.days_in_current_month() * 86400;
#       неизвестная категория -> ValueError
#   edge_seconds(distance_m: int, kind: str, pace: str, cfg) -> int
#       ceil(distance_m * 3600 * percent[kind] / (travel_pace[pace] * 100)); "road" -- 100 %
#   advance_by_category(clock: GameClock, category: str, cfg) -> int
#       сдвигает часы и возвращает на сколько секунд сдвинул
#   ensure_min_advance(clock: GameClock, scene_start_s: int, cfg) -> int
#       если clock.now_s == scene_start_s -- сдвигает на cfg.time.min_advance_s (10 мин) и
#       возвращает это число; если время уже сдвинулось -- ничего не делает, возвращает 0
import pytest

from ai_dm.config.settings import load_rules_config
from ai_dm.core.clock import Calendar, GameClock, Month
from ai_dm.rules.time_ops import (
    advance_by_category,
    category_seconds,
    day_part,
    edge_seconds,
    ensure_min_advance,
    long_rest_seconds,
    rounds_to_seconds,
    short_rest_seconds,
    turn_tick,
)

DAY = 86400


def test_round_is_6_seconds(cfg):
    assert rounds_to_seconds(1, cfg=cfg) == 6


def test_rounds_multiply(cfg):
    assert rounds_to_seconds(10, cfg=cfg) == 60
    assert rounds_to_seconds(0, cfg=cfg) == 0


def test_short_rest_is_one_hour(cfg):
    assert short_rest_seconds(cfg=cfg) == 3600


def test_long_rest_is_eight_hours(cfg):
    assert long_rest_seconds(cfg=cfg) == 8 * 3600


def test_rest_and_round_follow_config():
    toml = "[time]\nround_s = 10\nshort_rest_s = 1800\nlong_rest_s = 3600\n"
    cfg = load_rules_config(toml_text=toml)
    assert rounds_to_seconds(3, cfg=cfg) == 30
    assert short_rest_seconds(cfg=cfg) == 1800
    assert long_rest_seconds(cfg=cfg) == 3600


@pytest.mark.parametrize("category", ["hour", "day"])
def test_category_comes_from_config(category):
    cfg = load_rules_config()
    clock = GameClock(now_s=0)
    assert category_seconds(category, clock, cfg=cfg) == cfg.time.advance_categories[category]


def test_category_override_in_config():
    cfg = load_rules_config(toml_text="[time.advance_categories]\nhour = 300\n")
    assert category_seconds("hour", GameClock(now_s=0), cfg=cfg) == 300


def test_day_is_86400(cfg):
    assert category_seconds("day", GameClock(now_s=0), cfg=cfg) == DAY


def test_week_is_seven_days(cfg):
    assert category_seconds("week", GameClock(now_s=0), cfg=cfg) == 7 * DAY


def test_month_is_length_of_current_month_default(cfg):
    assert category_seconds("month", GameClock.from_date("1247-03-12"), cfg=cfg) == 30 * DAY


def test_month_depends_on_current_month_of_custom_calendar(cfg):
    cal = Calendar(months=[Month(name="Короткий", days=20), Month(name="Длинный", days=40)])
    short = GameClock.from_date("0001-01-05", cal)
    long = GameClock.from_date("0001-02-05", cal)
    assert category_seconds("month", short, cfg=cfg) == 20 * DAY
    assert category_seconds("month", long, cfg=cfg) == 40 * DAY


def test_unknown_category_is_error(cfg):
    with pytest.raises(ValueError):
        category_seconds("century", GameClock(now_s=0), cfg=cfg)


def test_advance_by_category_moves_clock(cfg):
    clock = GameClock.from_date("1247-03-12")
    start = clock.now_s
    moved = advance_by_category(clock, "week", cfg=cfg)
    assert moved == 7 * DAY
    assert clock.now_s == start + 7 * DAY
    assert clock.to_date() == "1247-03-19"


def test_advance_by_month_lands_on_same_day_next_month(cfg):
    clock = GameClock.from_date("1247-03-12")
    advance_by_category(clock, "month", cfg=cfg)
    assert clock.to_date() == "1247-04-12"


def test_ensure_min_advance_adds_ten_minutes_if_time_stood_still(cfg):
    clock = GameClock(now_s=5000)
    added = ensure_min_advance(clock, scene_start_s=5000, cfg=cfg)
    assert added == 600
    assert clock.now_s == 5600


def test_ensure_min_advance_does_nothing_if_time_moved(cfg):
    clock = GameClock(now_s=5001)
    added = ensure_min_advance(clock, scene_start_s=5000, cfg=cfg)
    assert added == 0
    assert clock.now_s == 5001


def test_ensure_min_advance_uses_config_value():
    cfg = load_rules_config(toml_text="[time]\nmin_advance_s = 60\n")
    clock = GameClock(now_s=0)
    ensure_min_advance(clock, scene_start_s=0, cfg=cfg)
    assert clock.now_s == 60


def test_default_hour_seconds(cfg):
    assert category_seconds("hour", GameClock(now_s=0), cfg=cfg) == 3600


def test_minute_is_no_longer_a_category(cfg):
    with pytest.raises(ValueError):
        category_seconds("minute", GameClock(now_s=0), cfg=cfg)


def test_turn_tick_adds_turn_s_if_clock_stood_still(cfg):
    clock = GameClock(now_s=5000)
    turn_tick(clock, 5000, cfg)
    assert clock.now_s == 5900


def test_turn_tick_does_nothing_if_clock_moved(cfg):
    clock = GameClock(now_s=5001)
    turn_tick(clock, 5000, cfg)
    assert clock.now_s == 5001


def test_turn_tick_uses_config_value():
    cfg = load_rules_config(toml_text="[time]\nturn_s = 60\n")
    clock = GameClock(now_s=0)
    turn_tick(clock, 0, cfg)
    assert clock.now_s == 60


def test_hour_is_exactly_one_hour_and_does_not_close_scene(cfg):
    # P1: порог ТЗ 4.0 -- "больше часа"; категория hour ровно час
    assert category_seconds("hour", GameClock(now_s=0), cfg=cfg) == 3600
    assert cfg.time.advance_categories["hour"] == 3600


def test_hour_category_advances_clock_by_3600(cfg):
    clock = GameClock(now_s=0)
    assert advance_by_category(clock, "hour", cfg=cfg) == 3600
    assert clock.now_s == 3600


@pytest.mark.parametrize("name", ["rounds_to_seconds", "short_rest_seconds", "long_rest_seconds"])
def test_cfg_is_required_without_fallback(name):
    import ai_dm.rules.time_ops as time_ops

    args = (1,) if name == "rounds_to_seconds" else ()
    with pytest.raises(TypeError):
        getattr(time_ops, name)(*args)


def test_cfg_is_required_for_category_and_travel_and_advance():
    clock = GameClock(now_s=0)
    with pytest.raises(TypeError):
        category_seconds("day", clock)
    with pytest.raises(TypeError):
        edge_seconds(100, "road", "normal")
    with pytest.raises(TypeError):
        advance_by_category(clock, "day")
    with pytest.raises(TypeError):
        ensure_min_advance(clock, 0)


@pytest.mark.parametrize("category", ["minutes", "hours"])
def test_old_plural_category_is_error(category, cfg):
    with pytest.raises(ValueError):
        category_seconds(category, GameClock(now_s=0), cfg=cfg)


def test_travel_normal_pace_one_hour(cfg):
    assert edge_seconds(4800, "road", "normal", cfg=cfg) == 3600


def test_travel_rounds_up(cfg):
    assert edge_seconds(1, "road", "normal", cfg=cfg) == 1


def test_travel_zero_distance(cfg):
    assert edge_seconds(0, "road", "fast", cfg=cfg) == 0


def test_travel_result_is_int(cfg):
    assert isinstance(edge_seconds(1000, "road", "slow", cfg=cfg), int)


def test_travel_follows_config():
    cfg = load_rules_config(toml_text="[time.travel_pace]\nnormal = 3600\n")
    assert edge_seconds(3600, "road", "normal", cfg=cfg) == 3600
    assert edge_seconds(1800, "road", "normal", cfg=cfg) == 1800


# Фикс ЖП4 (132), М0 П2: route_path(world, from_id, to_id, cfg) -> [(id, seconds)] | None
# (без старта); дорога: 1 м = 0,75 с (округление вверх на каждом ребре)

def world_of(*links, isolated=()):
    # links: (from, to, distance_m) -- связь записана только у from
    from types import SimpleNamespace

    from ai_dm.state.world import Connection, Location

    locations = {}
    for place_id in [x for a, b, _ in links for x in (a, b)] + list(isolated):
        locations.setdefault(place_id, Location(id=place_id, name=place_id))
    for a, b, distance in links:
        locations[a].connections.append(Connection(to=b, distance_m=distance))
    return SimpleNamespace(locations=locations)


def test_route_path_two_hops(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill", cfg) == [("forest", 3600), ("hill", 1800)]


def test_route_path_three_hops(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("tavern", "square", 300), ("square", "shrine", 200), ("shrine", "shop", 100))
    expected = [("square", 225), ("shrine", 150), ("shop", 75)]
    assert route_path(world, "tavern", "shop", cfg) == expected


def test_route_path_takes_shorter_sum_not_fewer_hops(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "hill", 9000), ("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill", cfg) == [("forest", 3600), ("hill", 1800)]


def test_route_path_takes_direct_link_when_shorter(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "hill", 7000), ("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill", cfg) == [("hill", 5250)]


def test_route_path_uses_link_recorded_only_at_target(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("hill", "forest", 2400))
    assert route_path(world, "vale", "hill", cfg) == [("forest", 3600), ("hill", 1800)]


def test_route_path_goes_back_against_recorded_direction(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "hill", "vale", cfg) == [("forest", 1800), ("vale", 3600)]


def test_route_path_tie_goes_by_id(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "b", 100), ("b", "end", 100), ("vale", "a", 100), ("a", "end", 100))
    assert route_path(world, "vale", "end", cfg) == [("a", 75), ("end", 75)]


def test_route_path_to_isolated_place_is_none(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), isolated=["goblin_den"])
    assert route_path(world, "vale", "goblin_den", cfg) is None


def test_route_path_from_place_without_links_is_none(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), isolated=["goblin_den"])
    assert route_path(world, "goblin_den", "vale", cfg) is None


def test_route_path_stale_queue_entry_does_not_stop_search(cfg):
    from ai_dm.rules.time_ops import route_path

    # b сначала найден за 8 с, затем за 2 через c; устаревшая запись (8, b) не должна
    # обрывать поиск до пути a-e-d (10 с), который короче a-c-b-d (17 с)
    world = world_of(
        ("a", "b", 10), ("a", "c", 1), ("c", "b", 1), ("b", "d", 20), ("a", "e", 12), ("e", "d", 1),
    )
    assert route_path(world, "a", "d", cfg) == [("e", 9), ("d", 1)]


def test_route_path_to_itself_is_empty(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800))
    assert route_path(world, "vale", "vale", cfg) == []


def test_route_path_ignores_link_to_missing_place(cfg):
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800))
    from ai_dm.state.world import Connection

    world.locations["vale"].connections.append(Connection(to="ghost", distance_m=1))
    assert route_path(world, "vale", "ghost", cfg) is None


# М0 П2 (docs/plan-m0.md, «Тесты» П2): род пути и время ребра, закрытые транспортом рёбра.
# Ожидаемый API (имена и форма — предположение доебы, вопрос к папе):
#   edge_seconds(distance_m, kind, pace, cfg) -> int
#       ceil(distance_m * 3600 * процент_рода / (темп * 100)); роды: tract 80, road 100, trail 150,
#       offroad 200, mine 150, water 50, air 25 (Приложение А)
#   route_path(world, from_id, to_id, cfg, transport=None) -> [(id, seconds)] | None
#       вес ребра — время; ребро с needs_transport без транспорта подходящего рода пропускается

def kinded_world(*edges, isolated=()):
    # edges: (from, to, distance_m, kind[, needs_transport]); ребро записано только у from
    from types import SimpleNamespace

    from ai_dm.state.world import Connection, Location

    locations = {}
    names = [x for e in edges for x in e[:2]] + list(isolated)
    for place_id in names:
        locations.setdefault(place_id, Location(id=place_id, name=place_id))
    for a, b, distance, kind, *rest in edges:
        locations[a].connections.append(
            Connection(to=b, distance_m=distance, kind=kind, needs_transport=bool(rest and rest[0]))
        )
    return SimpleNamespace(locations=locations)


@pytest.mark.parametrize(
    ("kind", "seconds"),
    [
        ("tract", 2880), ("road", 3600), ("trail", 5400), ("offroad", 7200),
        ("mine", 5400), ("water", 1800), ("air", 900),
    ],
)
def test_edge_seconds_by_route_kind(cfg, kind, seconds):
    from ai_dm.rules.time_ops import edge_seconds

    assert edge_seconds(4800, kind, "normal", cfg) == seconds


def test_edge_seconds_follows_pace(cfg):
    from ai_dm.rules.time_ops import edge_seconds

    assert edge_seconds(4800, "trail", "fast", cfg) == 4050


def test_edge_seconds_rounds_up(cfg):
    from ai_dm.rules.time_ops import edge_seconds

    # 3218 м по тропе: 3620,25 с
    assert edge_seconds(3218, "trail", "normal", cfg) == 3621


def test_route_path_takes_faster_not_shorter(cfg):
    from ai_dm.rules.time_ops import route_path

    # 1000 м бездорожья = 1500 с, 1500 м дороги = 1125 с
    world = kinded_world(("a", "goal", 1000, "offroad"), ("a", "goal", 1500, "road"))
    assert route_path(world, "a", "goal", cfg) == [("goal", 1125)]


def test_route_path_returns_seconds_per_hop(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("a", "b", 4800, "road"), ("b", "c", 4800, "trail"))
    assert route_path(world, "a", "c", cfg) == [("b", 3600), ("c", 5400)]


def test_route_path_time_is_same_both_directions_for_unequal_pair(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("a", "b", 4800, "road"), ("b", "a", 4800, "trail"))
    forward = route_path(world, "a", "b", cfg)
    back = route_path(world, "b", "a", cfg)
    assert [s for _, s in forward] == [s for _, s in back] == [3600]


def test_route_path_unequal_lengths_both_directions_take_the_faster(cfg):
    from ai_dm.rules.time_ops import route_path

    # как old_tower / tavern_drunken_dragon: 3218 м и 48270 м
    world = kinded_world(("tower", "tavern", 3218, "road"), ("tavern", "tower", 48270, "road"))
    forward = route_path(world, "tavern", "tower", cfg)
    back = route_path(world, "tower", "tavern", cfg)
    assert forward == [("tower", 2414)]
    assert back == [("tavern", 2414)]


def test_route_path_water_edge_without_transport_is_closed(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("shore", "isle", 1000, "water", True))
    assert route_path(world, "shore", "isle", cfg) is None


def test_route_path_water_edge_with_water_transport_is_open(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("shore", "isle", 4800, "water", True))
    assert route_path(world, "shore", "isle", cfg, transport="water") == [("isle", 1800)]


def test_route_path_water_edge_is_closed_for_other_transport(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("shore", "isle", 4800, "water", True))
    assert route_path(world, "shore", "isle", cfg, transport="air") is None


def test_route_path_goes_by_land_when_water_is_closed(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(
        ("shore", "isle", 1000, "water", True), ("shore", "bridge", 9600, "road"),
        ("bridge", "isle", 9600, "road"),
    )
    assert route_path(world, "shore", "isle", cfg) == [("bridge", 7200), ("isle", 7200)]


def test_closing_transport_names_the_transport_that_opens_the_edge(cfg):
    from ai_dm.rules.time_ops import closing_transport

    world = kinded_world(("shore", "isle", 4800, "water", True))
    assert closing_transport(world, "shore", "isle", cfg) == "water"


def test_closing_transport_default_pace_is_a_valid_one(cfg):
    from ai_dm.rules.time_ops import closing_transport

    world = kinded_world(("shore", "isle", 4800, "water", True), ("shore", "hill", 100, "road"))
    assert closing_transport(world, "shore", "isle", cfg) == "water"
    assert closing_transport(world, "shore", "isle", cfg, "fast") == "water"


def test_closing_transport_is_none_when_no_transport_opens_the_way(cfg):
    from ai_dm.rules.time_ops import closing_transport

    world = kinded_world(("shore", "isle", 4800, "water", True), isolated=["far"])
    assert closing_transport(world, "shore", "far", cfg) is None


def test_route_path_mine_without_needs_transport_is_open(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("forge", "shaft", 4800, "mine", False))
    assert route_path(world, "forge", "shaft", cfg) == [("shaft", 5400)]


def test_route_path_place_without_edges_has_no_implicit_link_to_parent(cfg):
    from ai_dm.rules.time_ops import route_path

    world = kinded_world(("vale", "forest", 4800, "road"), isolated=["cabin"])
    world.locations["cabin"].parent_id = "vale"
    assert route_path(world, "cabin", "vale", cfg) is None
    assert route_path(world, "vale", "cabin", cfg) is None


# М0 П3а (docs/plan-m0.md, «Тесты» П3; умолчания п. 23): путь из «дороги» -- герой на ребре
# vale -> tower (24000 м, «дорога», обычный темп 18000 с), вышел из vale, прошёл 7200 с.
#   road_ends(world, journey, cfg, transport=None) -> [(from_id, edge_done_s), (edge_to, остаток)]
#   road_path(world, journey, to_id, cfg, transport=None) -> [(id, seconds)] | None
#   journey_left_s(world, hero, cfg) -> int (секунды до journey.to; пути нет -- 0)
# Темп -- journey.pace у всех трёх; route_path не меняется.

def on_edge(pace="normal", **fields):
    from ai_dm.state.hero import Journey

    values = {
        "to": "tower", "pace": pace, "start_id": "vale", "road_id": "road_x",
        "from_id": "vale", "edge_to": "tower", "edge_done_s": 7200,
    }
    return Journey(**{**values, **fields})


def test_road_ends_gives_the_way_back_and_the_rest_of_the_edge(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(("vale", "tower", 24000, "road"))
    assert road_ends(world, on_edge(), cfg) == [("vale", 7200), ("tower", 10800)]


def test_road_ends_rest_of_the_edge_follows_the_journey_pace(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(("vale", "tower", 24000, "road"))
    assert road_ends(world, on_edge("fast"), cfg) == [("vale", 7200), ("tower", 13500 - 7200)]


def test_road_ends_edge_removed_from_the_map_leaves_only_the_way_back(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(isolated=["vale", "tower"])
    assert road_ends(world, on_edge(), cfg) == [("vale", 7200)]


def test_road_ends_edge_closed_by_transport_leaves_only_the_way_back(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(("vale", "tower", 24000, "water", True))
    assert road_ends(world, on_edge(), cfg) == [("vale", 7200)]


def test_road_ends_edge_opens_with_the_transport(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(("vale", "tower", 24000, "water", True))
    ends = road_ends(world, on_edge(), cfg, transport="water")
    assert [place for place, _ in ends] == ["vale", "tower"]


def test_road_ends_reverse_recorded_edge_gives_the_same_answer(cfg):
    from ai_dm.rules.journey import road_ends

    world = kinded_world(("tower", "vale", 24000, "road"))
    assert road_ends(world, on_edge(), cfg) == [("vale", 7200), ("tower", 10800)]


def test_road_path_to_the_far_end_is_the_rest_of_the_edge(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"))
    assert road_path(world, on_edge(), "tower", cfg) == [("tower", 10800)]


def test_road_path_to_the_start_is_the_way_already_walked(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"))
    assert road_path(world, on_edge(), "vale", cfg) == [("vale", 7200)]


def test_road_path_third_place_behind_the_start_goes_back_first(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"), ("vale", "spur", 1200, "road"))
    assert road_path(world, on_edge(), "spur", cfg) == [("vale", 7200), ("spur", 900)]


def test_road_path_third_place_behind_the_far_end_goes_forward_first(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"), ("tower", "spur", 1200, "road"))
    assert road_path(world, on_edge(), "spur", cfg) == [("tower", 10800), ("spur", 900)]


def test_road_path_place_reachable_from_both_ends_takes_the_smaller_sum(cfg):
    from ai_dm.rules.journey import road_path

    # от vale 9600 м (7200 с): назад 14400; от tower 1200 м (900 с): вперёд 11700
    world = kinded_world(
        ("vale", "tower", 24000, "road"), ("vale", "far", 9600, "road"),
        ("tower", "far", 1200, "road"),
    )
    assert road_path(world, on_edge(), "far", cfg) == [("tower", 10800), ("far", 900)]


def test_road_path_equal_sums_go_back_through_the_start(cfg):
    from ai_dm.rules.journey import road_path

    # назад 7200 + 4500 = вперёд 10800 + 900
    world = kinded_world(
        ("vale", "tower", 24000, "road"), ("vale", "far", 6000, "road"),
        ("tower", "far", 1200, "road"),
    )
    assert road_path(world, on_edge(), "far", cfg) == [("vale", 7200), ("far", 4500)]


def test_road_path_place_without_edges_is_none(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"), isolated=["lost"])
    assert road_path(world, on_edge(), "lost", cfg) is None


def test_road_path_behind_a_water_edge_is_none_without_transport(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"), ("vale", "isle", 4800, "water", True))
    assert road_path(world, on_edge(), "isle", cfg) is None


def test_road_path_behind_a_water_edge_exists_with_water_transport(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "road"), ("vale", "isle", 4800, "water", True))
    path = road_path(world, on_edge(), "isle", cfg, transport="water")
    assert path == [("vale", 7200), ("isle", 1800)]


def test_road_path_forward_along_a_water_edge_needs_the_transport_for_the_edge_itself(cfg):
    from ai_dm.rules.journey import road_path

    world = kinded_world(("vale", "tower", 24000, "water", True))
    path = road_path(world, on_edge(), "tower", cfg, transport="water")
    assert [place for place, _ in path] == ["tower"]


def test_road_path_rest_of_the_way_follows_the_journey_pace(cfg):
    from ai_dm.rules.journey import road_path

    # от tower до far 12800 м: быстрым темпом 7200 с, обычным 9600 с
    world = kinded_world(("vale", "tower", 24000, "road"), ("tower", "far", 12800, "road"))
    path = road_path(world, on_edge("fast"), "far", cfg)
    assert path == [("tower", 13500 - 7200), ("far", 7200)]


def hero_on(location_id, journey):
    from types import SimpleNamespace

    return SimpleNamespace(location_id=location_id, journey=journey, transport=None)


def test_journey_left_in_the_road_is_the_rest_of_the_edge(cfg):
    from ai_dm.rules.journey import journey_left_s

    world = kinded_world(("vale", "tower", 24000, "road"))
    assert journey_left_s(world, hero_on("road_x", on_edge()), cfg) == 10800


def test_journey_left_in_a_route_node_is_the_path_from_the_node(cfg):
    from ai_dm.rules.journey import journey_left_s

    world = kinded_world(("black", "tower", 12000, "road"))
    journey = on_edge(road_id="road_x", from_id="", edge_to="", edge_done_s=0)
    assert journey_left_s(world, hero_on("black", journey), cfg) == 9000


def test_journey_left_is_zero_when_the_target_is_cut_off(cfg):
    from ai_dm.rules.journey import journey_left_s

    world = kinded_world(isolated=["vale", "tower"])
    assert journey_left_s(world, hero_on("road_x", on_edge()), cfg) == 0


# М0 П3а, сверка кода: minutes_text живёт в rules/time_ops.py (перенос из game/travel_actions.py)

@pytest.mark.parametrize(
    ("seconds", "text"),
    [
        (60, "1 мин"), (61, "2 мин"), (3600, "1 ч"), (7200, "2 ч"),
        (3660, "1 ч 1 мин"), (3601, "1 ч 1 мин"),
    ],
)
def test_minutes_text_forms(seconds, text):
    from ai_dm.rules.time_ops import minutes_text

    assert minutes_text(seconds) == text


# leg_stop(route, limit) -> (номер перехода, секунд пройдено по нему);
# 0 секунд -- ровно в узле route[номер - 1]

def test_leg_stop_inside_the_second_hop():
    from ai_dm.rules.journey import leg_stop

    assert leg_stop([("a", 3600), ("b", 7200)], 7200) == (1, 3600)


def test_leg_stop_exactly_in_a_node():
    from ai_dm.rules.journey import leg_stop

    assert leg_stop([("a", 7200), ("b", 3600)], 7200) == (1, 0)


def test_leg_stop_inside_the_first_hop():
    from ai_dm.rules.journey import leg_stop

    assert leg_stop([("a", 9000)], 7200) == (0, 7200)


def test_leg_stop_route_not_longer_than_the_limit_is_an_error():
    from ai_dm.rules.journey import leg_stop

    with pytest.raises(ValueError):
        leg_stop([("a", 10)], 20)


# hero_route(world, hero, to_id, cfg, pace): из «дороги» -- road_path темпом journey.pace,
# из узла (в том числе с journey и записью «дороги») -- route_path темпом аргумента

def test_hero_route_from_a_node_is_route_path_with_the_argument_pace(cfg):
    from ai_dm.rules.journey import hero_route

    world = kinded_world(("black", "tower", 12000, "road"))
    assert hero_route(world, hero_on("black", None), "tower", cfg, "fast") == [("tower", 6750)]
    assert hero_route(world, hero_on("black", None), "tower", cfg, "normal") == [("tower", 9000)]


def test_hero_route_in_the_road_is_road_path_with_the_journey_pace_not_the_argument(cfg):
    from ai_dm.rules.journey import hero_route

    world = kinded_world(("vale", "tower", 24000, "road"))
    hero = hero_on("road_x", on_edge("fast"))
    assert hero_route(world, hero, "tower", cfg, "slow") == [("tower", 13500 - 7200)]


def test_hero_route_in_a_node_with_a_journey_goes_from_the_node(cfg):
    from ai_dm.rules.journey import hero_route

    world = kinded_world(("black", "tower", 12000, "road"))
    journey = on_edge(road_id="road_x", from_id="", edge_to="", edge_done_s=0)
    assert hero_route(world, hero_on("black", journey), "tower", cfg, "normal") == [("tower", 9000)]


def test_hero_route_in_the_road_uses_the_hero_transport(cfg):
    from types import SimpleNamespace

    from ai_dm.rules.journey import hero_route

    world = kinded_world(("vale", "tower", 24000, "water", True))
    hero = hero_on("road_x", on_edge())
    hero.transport = SimpleNamespace(kind="water")
    route = hero_route(world, hero, "tower", cfg, "normal")
    assert [place for place, _ in route] == ["tower"]


# open_road: занятый id не перезаписывается (правка 3, умолчания п. 7)

def test_open_road_takes_the_next_free_id_when_the_first_is_taken(cfg):
    from types import SimpleNamespace

    from ai_dm.rules.journey import open_road
    from ai_dm.state.world import Connection, Location

    taken = Location(
        id="road_5000", name="Тракт мастера", connections=[Connection(to="vale", distance_m=100)]
    )
    world = SimpleNamespace(locations={
        "vale": Location(id="vale", name="Вейл"), "tower": Location(id="tower", name="Башня"),
        "road_5000": taken,
    })
    journey = on_edge(road_id="")
    open_road(world, journey, 5000)
    assert journey.road_id == "road_5001"
    assert journey.road_id in world.locations
    assert world.locations[journey.road_id].temporary is True
    assert world.locations["road_5000"] is taken
    assert taken.name == "Тракт мастера"
    assert taken.temporary is False
    assert len(taken.connections) == 1


def test_open_road_skips_every_taken_id_in_a_row(cfg):
    from types import SimpleNamespace

    from ai_dm.rules.journey import open_road
    from ai_dm.state.world import Location

    world = SimpleNamespace(locations={
        "vale": Location(id="vale", name="Вейл"), "tower": Location(id="tower", name="Башня"),
        "road_5000": Location(id="road_5000", name="Один"),
        "road_5001": Location(id="road_5001", name="Два"),
    })
    journey = on_edge(road_id="")
    open_road(world, journey, 5000)
    assert journey.road_id == "road_5002"


def test_open_road_free_id_is_by_the_clock(cfg):
    from types import SimpleNamespace

    from ai_dm.rules.journey import open_road
    from ai_dm.state.world import Location

    world = SimpleNamespace(locations={
        "vale": Location(id="vale", name="Вейл"), "tower": Location(id="tower", name="Башня"),
    })
    journey = on_edge(road_id="")
    open_road(world, journey, 5000)
    assert journey.road_id == "road_5000"


# end_journey

def road_world(npcs=()):
    from types import SimpleNamespace

    from ai_dm.state.world import Location

    return SimpleNamespace(
        locations={
            "vale": Location(id="vale", name="Вейл"),
            "road_x": Location(id="road_x", name="Дорога", temporary=True, origin="engine"),
        },
        npcs={n.id: n for n in npcs}, dangers=[], custom_items={},
    )


def test_end_journey_without_a_journey_changes_nothing():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey

    world = road_world()
    hero = SimpleNamespace(journey=None, location_id="vale", death=None)
    end_journey(world, hero)
    assert set(world.locations) == {"vale", "road_x"}
    assert hero.journey is None


def test_end_journey_without_a_road_record_only_drops_the_journey():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey

    world = road_world()
    hero = SimpleNamespace(
        journey=on_edge(road_id="", from_id="", edge_to=""), location_id="vale", death=None
    )
    end_journey(world, hero)
    assert hero.journey is None
    assert set(world.locations) == {"vale", "road_x"}


def test_end_journey_clears_the_hero_death_place_of_the_road():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey
    from ai_dm.state.death import DeathRecord

    world = road_world()
    death = DeathRecord(cause="hazard", at_s=10, location_id="road_x")
    hero = SimpleNamespace(journey=on_edge(), location_id="vale", death=death)
    end_journey(world, hero)
    assert hero.death is death
    assert hero.death.location_id is None


def test_end_journey_keeps_the_hero_death_place_elsewhere():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey
    from ai_dm.state.death import DeathRecord

    world = road_world()
    hero = SimpleNamespace(
        journey=on_edge(), location_id="vale",
        death=DeathRecord(cause="hazard", at_s=10, location_id="vale"),
    )
    end_journey(world, hero)
    assert hero.death.location_id == "vale"


def test_end_journey_item_without_a_holder_is_left_alone():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey

    world = road_world()
    world.custom_items["coin"] = SimpleNamespace(holder=None)
    hero = SimpleNamespace(journey=on_edge(), location_id="vale", death=None)
    end_journey(world, hero)
    assert "road_x" not in world.locations
    assert world.custom_items["coin"].holder is None


def test_end_journey_dead_companion_with_follows_loses_the_place():
    from types import SimpleNamespace

    from ai_dm.rules.journey import end_journey
    from ai_dm.state.world import NPC

    npc = NPC(
        id="lira", name="Лира", means=["меч"], location_id="road_x", follows="hero",
        status="dead"
    )
    world = road_world([npc])
    hero = SimpleNamespace(journey=on_edge(), location_id="vale", death=None)
    end_journey(world, hero)
    assert npc.location_id is None
    assert "road_x" not in world.locations


# day_part: утро с 6, день с 12, вечер с 18, ночь с 21 (до утра)

@pytest.mark.parametrize(
    ("hour", "minute", "part"),
    [
        (0, 0, "ночь"), (5, 59, "ночь"), (6, 0, "утро"), (11, 59, "утро"),
        (12, 0, "день"), (17, 59, "день"), (18, 0, "вечер"), (20, 59, "вечер"),
        (21, 0, "ночь"), (23, 59, "ночь"),
    ],
)
def test_day_part_boundaries(cfg, hour, minute, part):
    assert day_part(hour * 3600 + minute * 60, cfg) == part


def test_day_part_ignores_whole_days(cfg):
    assert day_part(5 * DAY + 13 * 3600, cfg) == "день"


def test_day_part_follows_config_boundaries():
    cfg = load_rules_config(toml_text="[time.day_parts]\nmorning = 5\nnight = 22\n")
    assert day_part(5 * 3600, cfg) == "утро"
    assert day_part(21 * 3600, cfg) == "вечер"
    assert day_part(22 * 3600, cfg) == "ночь"
