# У1 П1 (docs/plan-u1.md): rules/hygiene.py -- время последнего мытья героя во флаге мира.
#   WASHED_FLAG = "washed"; флаг "washed:<hero_id>" хранит секунды мира (int).
#   washed_at(world, hero_id) -> int | None: None, если флага нет.
#   mark_washed(world, hero, now_s): пишет флаг, перезаписывает прежний.
from ai_dm.core.clock import DAY
from ai_dm.core.rng import Rng
from ai_dm.rules.auto_flags import RESERVED_FLAG_PREFIXES
from ai_dm.rules.hygiene import SMELLY, WASHED_FLAG, is_stale, mark_washed, washed_at
from ai_dm.state.world import WorldState


class Hero:
    def __init__(self, hero_id):
        self.id = hero_id


def make_world():
    return WorldState(world_id="w", rng=Rng(1).state)


def test_flag_prefix_is_washed():
    assert WASHED_FLAG == "washed"


def test_washed_at_is_none_without_flag():
    assert washed_at(make_world(), "hero") is None


def test_mark_washed_writes_flag_per_hero():
    world = make_world()
    mark_washed(world, Hero("hero"), 12345)
    assert world.flags == {"washed:hero": 12345}


def test_washed_at_reads_what_mark_washed_wrote():
    world = make_world()
    mark_washed(world, Hero("hero"), 777)
    assert washed_at(world, "hero") == 777


def test_washed_at_is_per_hero():
    world = make_world()
    mark_washed(world, Hero("hero"), 777)
    assert washed_at(world, "other") is None


def test_mark_washed_overwrites_previous_time():
    world = make_world()
    mark_washed(world, Hero("hero"), 100)
    mark_washed(world, Hero("hero"), 900)
    assert washed_at(world, "hero") == 900


def test_mark_washed_keeps_other_heroes_flag():
    world = make_world()
    mark_washed(world, Hero("a"), 1)
    mark_washed(world, Hero("b"), 2)
    assert (washed_at(world, "a"), washed_at(world, "b")) == (1, 2)


def test_washed_prefix_is_reserved_for_the_engine():
    assert "washed" in RESERVED_FLAG_PREFIXES


# У1 П3: is_stale -- с последнего мытья прошло не меньше hygiene_days суток

def stale_at(cfg, washed, at):
    world = make_world()
    if washed is not None:
        mark_washed(world, Hero("hero"), washed)
    return is_stale(world, Hero("hero"), cfg, at)


def test_smelly_constant_is_condition_id():
    assert SMELLY == "smelly"


def test_not_stale_without_washed_flag(cfg):
    assert stale_at(cfg, None, 100 * DAY) is False


def test_not_stale_one_second_before_the_limit(cfg):
    assert stale_at(cfg, 0, 7 * DAY - 1) is False


def test_stale_exactly_at_the_limit(cfg):
    assert stale_at(cfg, 0, 7 * DAY) is True


def test_count_starts_from_the_start_of_the_day_of_washing(cfg):
    # помылся в полдень дня 2: вонь на тике дня 9, не дня 10
    noon = 2 * DAY + DAY // 2
    assert stale_at(cfg, noon, 9 * DAY) is True
    assert stale_at(cfg, noon, 9 * DAY - 1) is False


def test_washed_at_the_last_second_of_a_day_counts_from_that_day(cfg):
    assert stale_at(cfg, DAY - 1, 7 * DAY) is True


def test_stale_long_after_the_limit(cfg):
    assert stale_at(cfg, 0, 30 * DAY) is True


def test_stale_limit_follows_hygiene_days(cfg):
    cfg3 = cfg.model_copy(deep=True)
    cfg3.services.hygiene_days = 3
    assert stale_at(cfg3, 0, 3 * DAY) is True
    assert stale_at(cfg3, 0, 3 * DAY - 1) is False
