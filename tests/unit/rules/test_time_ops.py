# Ожидаемый API: ai_dm.rules.time_ops (cfg: RulesConfig -- обязательный аргумент, без fallback
#   на defaults.toml, аудит 1 п. 2.8; в тестах cfg передаётся по имени, фикстура cfg -- conftest)
#   rounds_to_seconds(rounds: int, cfg) -> int             -- rounds * cfg.time.round_s (6)
#   short_rest_seconds(cfg) -> int                         -- 3600
#   long_rest_seconds(cfg) -> int                          -- 28800
#   category_seconds(category: str, clock: GameClock, cfg) -> int
#       "minute" (900) | "hour" (3600, P1: не закрывает сцену) | "day" | "week" | "month";
#       minute/hour/day/week -- из
#       cfg.time.advance_categories; "month" -- clock.days_in_current_month() * 86400;
#       неизвестная категория -> ValueError
#   travel_seconds(distance_m: int, pace: str, cfg) -> int
#       ceil(distance_m * 3600 / travel_pace[pace]); плохой темп/дистанция < 0 -> ValueError
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
    ensure_min_advance,
    long_rest_seconds,
    rounds_to_seconds,
    short_rest_seconds,
    travel_seconds,
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


@pytest.mark.parametrize("category", ["minute", "hour", "day"])
def test_category_comes_from_config(category):
    cfg = load_rules_config()
    clock = GameClock(now_s=0)
    assert category_seconds(category, clock, cfg=cfg) == cfg.time.advance_categories[category]


def test_category_override_in_config():
    cfg = load_rules_config(toml_text="[time.advance_categories]\nminute = 300\n")
    assert category_seconds("minute", GameClock(now_s=0), cfg=cfg) == 300


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


def test_default_minute_and_hour_seconds(cfg):
    clock = GameClock(now_s=0)
    assert category_seconds("minute", clock, cfg=cfg) == 900
    assert category_seconds("hour", clock, cfg=cfg) == 3600


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
        travel_seconds(100, "normal")
    with pytest.raises(TypeError):
        advance_by_category(clock, "day")
    with pytest.raises(TypeError):
        ensure_min_advance(clock, 0)


@pytest.mark.parametrize("category", ["minutes", "hours"])
def test_old_plural_category_is_error(category, cfg):
    with pytest.raises(ValueError):
        category_seconds(category, GameClock(now_s=0), cfg=cfg)


def test_travel_normal_pace_one_hour(cfg):
    assert travel_seconds(4800, "normal", cfg=cfg) == 3600


def test_travel_rounds_up(cfg):
    assert travel_seconds(1, "normal", cfg=cfg) == 1


def test_travel_zero_distance(cfg):
    assert travel_seconds(0, "fast", cfg=cfg) == 0


def test_travel_unknown_pace_is_error(cfg):
    with pytest.raises(ValueError):
        travel_seconds(100, "teleport", cfg=cfg)


def test_travel_negative_distance_is_error(cfg):
    with pytest.raises(ValueError):
        travel_seconds(-1, "normal", cfg=cfg)


def test_travel_result_is_int(cfg):
    assert isinstance(travel_seconds(1000, "slow", cfg=cfg), int)


def test_travel_follows_config():
    cfg = load_rules_config(toml_text="[time.travel_pace]\nnormal = 3600\n")
    assert travel_seconds(3600, "normal", cfg=cfg) == 3600
    assert travel_seconds(1800, "normal", cfg=cfg) == 1800


# Фикс ЖП4 (132): route_path(world, from_id, to_id) -> [(id, distance_m)] без старта | None

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


def test_route_path_two_hops():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill") == [("forest", 4800), ("hill", 2400)]


def test_route_path_three_hops():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("tavern", "square", 300), ("square", "shrine", 200), ("shrine", "shop", 100))
    assert route_path(world, "tavern", "shop") == [("square", 300), ("shrine", 200), ("shop", 100)]


def test_route_path_takes_shorter_sum_not_fewer_hops():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "hill", 9000), ("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill") == [("forest", 4800), ("hill", 2400)]


def test_route_path_takes_direct_link_when_shorter():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "hill", 7000), ("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "vale", "hill") == [("hill", 7000)]


def test_route_path_uses_link_recorded_only_at_target():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("hill", "forest", 2400))
    assert route_path(world, "vale", "hill") == [("forest", 4800), ("hill", 2400)]


def test_route_path_goes_back_against_recorded_direction():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), ("forest", "hill", 2400))
    assert route_path(world, "hill", "vale") == [("forest", 2400), ("vale", 4800)]


def test_route_path_tie_goes_by_id():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "b", 100), ("b", "end", 100), ("vale", "a", 100), ("a", "end", 100))
    assert route_path(world, "vale", "end") == [("a", 100), ("end", 100)]


def test_route_path_to_isolated_place_is_none():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), isolated=["goblin_den"])
    assert route_path(world, "vale", "goblin_den") is None


def test_route_path_from_place_without_links_is_none():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800), isolated=["goblin_den"])
    assert route_path(world, "goblin_den", "vale") is None


def test_route_path_stale_queue_entry_does_not_stop_search():
    from ai_dm.rules.time_ops import route_path

    # b сначала найден по 10, затем по 2 через c; устаревшая запись (10, b) не должна
    # обрывать поиск до пути a-e-d (13), который короче a-c-b-d (22)
    world = world_of(
        ("a", "b", 10), ("a", "c", 1), ("c", "b", 1), ("b", "d", 20), ("a", "e", 12), ("e", "d", 1),
    )
    assert route_path(world, "a", "d") == [("e", 12), ("d", 1)]


def test_route_path_to_itself_is_empty():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800))
    assert route_path(world, "vale", "vale") == []


def test_route_path_ignores_link_to_missing_place():
    from ai_dm.rules.time_ops import route_path

    world = world_of(("vale", "forest", 4800))
    from ai_dm.state.world import Connection

    world.locations["vale"].connections.append(Connection(to="ghost", distance_m=1))
    assert route_path(world, "vale", "ghost") is None


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
