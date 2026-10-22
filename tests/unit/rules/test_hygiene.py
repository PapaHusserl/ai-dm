# У1 П1 (docs/plan-u1.md): rules/hygiene.py -- время последнего мытья героя во флаге мира.
#   WASHED_FLAG = "washed"; флаг "washed:<hero_id>" хранит секунды мира (int).
#   washed_at(world, hero_id) -> int | None: None, если флага нет.
#   mark_washed(world, hero, now_s): пишет флаг, перезаписывает прежний.
from ai_dm.core.rng import Rng
from ai_dm.rules.auto_flags import RESERVED_FLAG_PREFIXES
from ai_dm.rules.hygiene import WASHED_FLAG, mark_washed, washed_at
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
