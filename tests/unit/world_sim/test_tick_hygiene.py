# У1 П3 (docs/plan-u1.md, решения 16, 23): world_sim/hygiene.py roll_day и его место в tick_days.
#   roll_day(bundle, cfg, at) -> []: для каждого активного героя (по id):
#     флага washed:<герой> нет -> flag = at, вони нет (отсчёт с первого тика, старые миры);
#     at - washed >= hygiene_days * DAY и вони нет -> AppliedCondition("smelly", source="hygiene")
#       и запись хроники kind "event" с id героя в refs; вонь уже есть -- без дубля и второй записи;
#     hygiene_days = 0 -- гигиена выключена (ни флага, ни состояния); не активный герой -- пропуск.
#   tick_days зовёт roll_day раз в день после hazard.
from tick_kit import QueueRng, run_tick, solo_hero
from world_sim_kit import DAY, mini_bundle

from ai_dm.rules.hygiene import mark_washed, washed_at
from ai_dm.world_sim import hygiene


def setup(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    return bundle, solo_hero(bundle)


def smelly(hero):
    return [c for c in hero.creature.conditions if c.id == "smelly"]


def stench_entries(bundle):
    return [e for e in bundle.chronicle.entries if "без мытья" in e.text]


# roll_day напрямую

def test_roll_day_returns_empty_list(registry, cfg):
    bundle, _ = setup(registry, cfg)
    assert hygiene.roll_day(bundle, cfg, 5 * DAY) == []


def test_first_day_without_flag_starts_the_countdown(registry, cfg):
    bundle, hero = setup(registry, cfg)
    hygiene.roll_day(bundle, cfg, 5 * DAY)
    assert washed_at(bundle.world, hero.id) == 5 * DAY
    assert smelly(hero) == []


def test_first_day_does_not_make_old_world_smelly_retroactively(registry, cfg):
    bundle, hero = setup(registry, cfg)
    bundle.world.clock.advance(300 * DAY)
    hygiene.roll_day(bundle, cfg, 300 * DAY)
    assert smelly(hero) == []
    assert stench_entries(bundle) == []


def test_fresh_wash_before_the_limit_is_not_smelly(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY - 1)
    assert smelly(hero) == []


def test_exactly_hygiene_days_without_wash_makes_smelly(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    [condition] = smelly(hero)
    assert condition.source == "hygiene"


def test_smelly_writes_one_chronicle_event_about_the_hero(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    [entry] = stench_entries(bundle)
    assert entry.kind == "event"
    assert entry.refs == [hero.id]
    assert entry.at_s == 7 * DAY
    assert entry.text == f"От {hero.name} несёт: давно без мытья"


def test_washed_at_noon_of_day_zero_is_smelly_on_the_tick_of_day_seven(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, DAY // 2)
    hygiene.roll_day(bundle, cfg, 6 * DAY)
    assert smelly(hero) == []
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert len(smelly(hero)) == 1


def test_washed_at_end_of_day_zero_is_smelly_on_the_tick_of_day_seven(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, DAY - 1)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert len(smelly(hero)) == 1


def test_smelly_keeps_the_old_washed_mark(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 100)
    hygiene.roll_day(bundle, cfg, 100 + 9 * DAY)
    assert washed_at(bundle.world, hero.id) == 100


def test_already_smelly_gets_no_duplicate_and_no_second_entry(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    hygiene.roll_day(bundle, cfg, 8 * DAY)
    assert len(smelly(hero)) == 1
    assert len(stench_entries(bundle)) == 1


def test_smelly_keeps_other_conditions(registry, cfg):
    from ai_dm.state.creature import AppliedCondition

    bundle, hero = setup(registry, cfg)
    hero.creature.conditions.append(AppliedCondition(id="poisoned"))
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert [c.id for c in hero.creature.conditions] == ["poisoned", "smelly"]


def test_limit_follows_hygiene_days(registry, cfg):
    bundle, hero = setup(registry, cfg)
    cfg3 = cfg.model_copy(deep=True)
    cfg3.services.hygiene_days = 3
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg3, 3 * DAY - 1)
    assert smelly(hero) == []
    hygiene.roll_day(bundle, cfg3, 3 * DAY)
    assert len(smelly(hero)) == 1


def test_hygiene_days_zero_disables_everything(registry, cfg):
    bundle, hero = setup(registry, cfg)
    off = cfg.model_copy(deep=True)
    off.services.hygiene_days = 0
    hygiene.roll_day(bundle, off, 50 * DAY)
    assert washed_at(bundle.world, hero.id) is None
    assert smelly(hero) == []


def test_hygiene_days_zero_does_not_smell_even_with_old_mark(registry, cfg):
    bundle, hero = setup(registry, cfg)
    off = cfg.model_copy(deep=True)
    off.services.hygiene_days = 0
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, off, 50 * DAY)
    assert smelly(hero) == []
    assert stench_entries(bundle) == []


def test_hero_in_afterlife_is_skipped(registry, cfg):
    bundle, hero = setup(registry, cfg)
    hero.status = "in_afterlife"
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 30 * DAY)
    assert smelly(hero) == []


def test_dead_hero_gets_no_flag(registry, cfg):
    bundle, hero = setup(registry, cfg)
    hero.status = "dead"
    hygiene.roll_day(bundle, cfg, 5 * DAY)
    assert washed_at(bundle.world, hero.id) is None


def add_hero_before(bundle, hero, status="active"):
    # второй герой с id, идущим раньше в сортировке
    other = hero.model_copy(deep=True)
    other.id = "aaa-" + hero.id
    other.status = status
    bundle.heroes.append(other)
    return other


def test_inactive_hero_does_not_stop_the_loop_for_the_next_hero(registry, cfg):
    bundle, hero = setup(registry, cfg)
    add_hero_before(bundle, hero, status="dead")
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert len(smelly(hero)) == 1


def test_hero_without_flag_does_not_stop_the_loop_for_the_next_hero(registry, cfg):
    bundle, hero = setup(registry, cfg)
    other = add_hero_before(bundle, hero)
    mark_washed(bundle.world, hero, 0)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert washed_at(bundle.world, other.id) == 7 * DAY
    assert len(smelly(hero)) == 1


def test_washing_again_postpones_the_stench(registry, cfg):
    bundle, hero = setup(registry, cfg)
    mark_washed(bundle.world, hero, 0)
    mark_washed(bundle.world, hero, 5 * DAY)
    hygiene.roll_day(bundle, cfg, 7 * DAY)
    assert smelly(hero) == []
    hygiene.roll_day(bundle, cfg, 12 * DAY)
    assert len(smelly(hero)) == 1


# через tick_days

def passing():
    return QueueRng(default="high")


def test_tick_first_day_sets_flag_then_week_later_smelly(registry, cfg):
    bundle, hero = setup(registry, cfg)
    run_tick(bundle, passing(), registry, cfg, days=1)
    first = washed_at(bundle.world, hero.id)
    assert first is not None
    assert smelly(hero) == []
    run_tick(bundle, passing(), registry, cfg, days=6)
    assert smelly(hero) == []
    run_tick(bundle, passing(), registry, cfg, days=1)
    assert len(smelly(hero)) == 1
    assert washed_at(bundle.world, hero.id) == first


def test_tick_eight_days_at_once_makes_hero_smelly(registry, cfg):
    bundle, hero = setup(registry, cfg)
    run_tick(bundle, passing(), registry, cfg, days=8)
    assert len(smelly(hero)) == 1
    assert len(stench_entries(bundle)) == 1


def test_tick_with_hygiene_off_leaves_hero_clean(registry, cfg):
    bundle, hero = setup(registry, cfg)
    off = cfg.model_copy(deep=True)
    off.services.hygiene_days = 0
    run_tick(bundle, passing(), registry, off, days=30)
    assert smelly(hero) == []
    assert washed_at(bundle.world, hero.id) is None


def test_tick_wash_resets_the_countdown(registry, cfg):
    bundle, hero = setup(registry, cfg)
    run_tick(bundle, passing(), registry, cfg, days=1)
    run_tick(bundle, passing(), registry, cfg, days=5)
    mark_washed(bundle.world, hero, bundle.world.clock.now_s)
    run_tick(bundle, passing(), registry, cfg, days=5)
    assert smelly(hero) == []
    run_tick(bundle, passing(), registry, cfg, days=3)
    assert len(smelly(hero)) == 1
