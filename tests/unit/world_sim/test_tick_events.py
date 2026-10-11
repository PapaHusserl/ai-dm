# Ожидаемый API: ai_dm.world_sim.tick.tick_days -- глобальные события (ТЗ 4.1.2): множитель
# смертности по региону и группе, срок события, сезонные природные события. Контракт в tick_kit.py.
import pytest
from tick_kit import QueueRng, entries_with, nobody, run_tick, solo_npc
from world_sim_kit import DAY, mini_bundle

from ai_dm.core.clock import GameClock
from ai_dm.rules.triggers_eval import Truth, evaluate
from ai_dm.state.triggers import EventActive
from ai_dm.state.world import GlobalEvent

PER_DAY = 20000


def event(event_id="plague1", multiplier=20, regions=("town",), affects=(), **fields):
    return GlobalEvent(
        id=event_id, type="plague", regions=list(regions), affects=list(affects),
        mortality_multiplier=multiplier, cause="trigger:morrah:x", **fields,
    )


def bundle_with(registry, cfg, *events, location="tavern", groups=()):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    npc = solo_npc(bundle)
    npc.location_id = location
    npc.groups = list(groups)
    bundle.world.events = list(events)
    return bundle


def asked_for(bundle, registry, cfg):
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg)
    return rng.asked


# множитель и регион

def test_event_in_region_divides_per_day_by_multiplier(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_event_region_hit_kills_with_raised_chance(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    run_tick(bundle, QueueRng(d1000=[1]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "dead"


def test_event_region_is_found_by_parent_chain(registry, cfg):
    # cellar -> tavern -> town
    bundle = bundle_with(registry, cfg, event(), location="cellar")
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_event_region_equal_to_npc_location_applies(registry, cfg):
    bundle = bundle_with(registry, cfg, event(regions=["tavern"]))
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_npc_outside_event_region_keeps_base_chance(registry, cfg):
    bundle = bundle_with(registry, cfg, event(regions=["cellar"]), location="town")
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


def test_parent_region_does_not_cover_child_event_only_by_name(registry, cfg):
    # событие в подвале не касается NPC в таверне (выше по цепочке)
    bundle = bundle_with(registry, cfg, event(regions=["cellar"]), location="tavern")
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


# группа

def test_event_with_group_hits_npc_in_group(registry, cfg):
    bundle = bundle_with(registry, cfg, event(affects=["бедняки"]), groups=["бедняки"])
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_event_with_group_skips_npc_outside_group(registry, cfg):
    bundle = bundle_with(registry, cfg, event(affects=["бедняки"]), groups=["купцы"])
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


def test_event_with_group_skips_npc_without_groups(registry, cfg):
    bundle = bundle_with(registry, cfg, event(affects=["бедняки"]))
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


@pytest.mark.parametrize("affects", [[], ["все"]])
def test_event_for_everyone_hits_npc_without_groups(affects, registry, cfg):
    bundle = bundle_with(registry, cfg, event(affects=affects))
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_npc_in_one_of_several_groups_is_hit(registry, cfg):
    bundle = bundle_with(
        registry, cfg, event(affects=["солдаты", "бедняки"]), groups=["бедняки", "купцы"]
    )
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


# несколько событий, сроки

def test_largest_multiplier_wins(registry, cfg):
    bundle = bundle_with(registry, cfg, event("a", 5), event("b", 20), event("c", 2))
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_multiplier_zero_does_not_change_chance(registry, cfg):
    bundle = bundle_with(registry, cfg, event(multiplier=0))
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


def test_expired_event_does_not_raise_chance(registry, cfg):
    bundle = bundle_with(registry, cfg, event(started_s=0, ends_at_s=1))
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


def test_event_not_started_yet_does_not_raise_chance(registry, cfg):
    bundle = bundle_with(registry, cfg, event(started_s=10**12))
    assert asked_for(bundle, registry, cfg) == [PER_DAY]


def test_event_ends_at_s_closes_event_in_chronicle(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    now = bundle.world.clock.now_s
    bundle.world.events[0].started_s = now
    bundle.world.events[0].ends_at_s = now + 2 * DAY
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=1)
    assert not entries_with(bundle, "plague1", "event")
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=2)
    assert len(entries_with(bundle, "plague1", "event")) == 1


def test_event_after_ends_at_s_is_not_active(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    now = bundle.world.clock.now_s
    bundle.world.events[0].started_s = now
    bundle.world.events[0].ends_at_s = now + DAY
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=3)
    result = evaluate(EventActive(event="plague1"), bundle.world)
    assert result.truth == Truth.FALSE


def test_closed_event_is_reported_once(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    now = bundle.world.clock.now_s
    bundle.world.events[0].started_s = now
    bundle.world.events[0].ends_at_s = now + DAY
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=3)
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=3)
    assert len(entries_with(bundle, "plague1", "event")) == 1


def test_ends_when_structural_condition_closes_event(registry, cfg):
    bundle = bundle_with(registry, cfg, event(ends_when={"flag": "plague_over"}))
    run_tick(bundle, QueueRng(default="high"), registry, cfg)
    assert evaluate(EventActive(event="plague1"), bundle.world).truth == Truth.TRUE
    bundle.world.flags["plague_over"] = True
    run_tick(bundle, QueueRng(default="high"), registry, cfg)
    assert evaluate(EventActive(event="plague1"), bundle.world).truth == Truth.FALSE
    assert len(entries_with(bundle, "plague1", "event")) == 1


def test_event_without_end_stays_active(registry, cfg):
    bundle = bundle_with(registry, cfg, event())
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=30)
    assert evaluate(EventActive(event="plague1"), bundle.world).truth == Truth.TRUE


# сезон

def before_summer(bundle):
    # 30 Цветеня: следующий день -- Грозовик, лето; первый тик уже сделан
    now = GameClock.from_date("0100-04-30", bundle.world.clock.calendar).now_s + 8 * 3600
    bundle.world.clock.now_s = now
    bundle.world.sim.last_day = now // DAY
    bundle.world.sim.last_season = bundle.world.clock.season()


def season_bundle(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    before_summer(bundle)
    return bundle


def natural_events(bundle):
    return [e for e in bundle.world.events if e.kind == "natural"]


def test_season_change_makes_exactly_one_roll(registry, cfg):
    bundle = season_bundle(registry, cfg)
    assert bundle.world.clock.season() == "весна"
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg)
    assert bundle.world.clock.season() == "лето"
    assert rng.asked.count(100) == 1


def test_second_day_of_same_season_has_no_roll(registry, cfg):
    bundle = season_bundle(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg)
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == []


def test_boundary_repeated_in_same_season_has_no_roll(registry, cfg):
    bundle = season_bundle(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg)
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg, days=10)
    assert rng.asked == []


def test_season_roll_hit_creates_natural_event_with_cause_and_term(registry, cfg):
    bundle = season_bundle(registry, cfg)
    before = {e.id for e in bundle.world.events}
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    new = [e for e in natural_events(bundle) if e.id not in before]
    assert len(new) == 1
    assert new[0].type == "harvest_fair"
    assert new[0].cause == "season:лето"
    assert new[0].regions == ["town"]
    assert new[0].ends_at_s - new[0].started_s == 10 * DAY
    assert DAY * (bundle.world.sim.last_day - 1) <= new[0].started_s <= bundle.world.clock.now_s


def test_season_roll_hit_is_written_to_chronicle(registry, cfg):
    bundle = season_bundle(registry, cfg)
    before = {e.id for e in bundle.world.events}
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    new = next(e for e in natural_events(bundle) if e.id not in before)
    assert entries_with(bundle, new.id, "event")


def test_season_roll_hundred_percent_always_creates_event(registry, cfg):
    bundle = season_bundle(registry, cfg)
    bundle.world.natural.chance_percent_per_season = 100
    before = len(natural_events(bundle))
    run_tick(bundle, QueueRng(d100=[100]), registry, cfg)
    assert len(natural_events(bundle)) == before + 1


def test_season_roll_miss_creates_no_event(registry, cfg):
    bundle = season_bundle(registry, cfg)
    before = len(bundle.world.events)
    run_tick(bundle, QueueRng(d100=[100]), registry, cfg)
    assert len(bundle.world.events) == before


def test_season_roll_zero_percent_never_creates_event(registry, cfg):
    bundle = season_bundle(registry, cfg)
    bundle.world.natural.chance_percent_per_season = 0
    before = len(bundle.world.events)
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    assert len(bundle.world.events) == before


def test_season_change_updates_last_season(registry, cfg):
    bundle = season_bundle(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg)
    assert bundle.world.sim.last_season == "лето"


def test_natural_event_expires_by_term(registry, cfg):
    bundle = season_bundle(registry, cfg)
    before = {e.id for e in bundle.world.events}
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    new = next(e for e in natural_events(bundle) if e.id not in before)
    assert evaluate(EventActive(event=new.id), bundle.world).truth == Truth.TRUE
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=11)
    assert evaluate(EventActive(event=new.id), bundle.world).truth == Truth.FALSE


def test_natural_event_without_kinds_is_not_created(registry, cfg):
    bundle = season_bundle(registry, cfg)
    bundle.world.natural.kinds = []
    before = len(bundle.world.events)
    run_tick(bundle, QueueRng(default="high", d100=[1]), registry, cfg)
    assert len(bundle.world.events) == before


# инициализация last_season / last_year

def migrated(bundle):
    # мир после m0003: только last_day
    bundle.world.sim.last_season = ""
    bundle.world.sim.last_year = 0


def test_first_tick_initializes_season_and_year(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    migrated(bundle)
    run_tick(bundle, QueueRng(), registry, cfg)
    clock = bundle.world.clock
    assert bundle.world.sim.last_season == clock.season()
    assert bundle.world.sim.last_year == clock.now_s // clock.calendar.seconds_in_year


def test_first_tick_does_not_roll_season(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    migrated(bundle)
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == []


def test_first_tick_does_not_make_natural_event(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    migrated(bundle)
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    assert bundle.world.events == []


def test_first_tick_does_not_age_anyone(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    migrated(bundle)
    bundle.world.npcs["old"] = bundle_old_npc(bundle)
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg)
    assert bundle.world.npcs["old"].status == "alive"
    assert 100 not in rng.asked


def bundle_old_npc(bundle):
    from tick_kit import new_npc

    now = bundle.world.clock.now_s
    return new_npc("old", species_id="human", birth_s=now - 95 * 360 * DAY)


def test_event_with_empty_regions_covers_whole_world(registry, cfg):
    bundle = bundle_with(registry, cfg, event(regions=[]), location="cellar")
    assert asked_for(bundle, registry, cfg) == [PER_DAY // 20]


def test_natural_event_id_is_not_duplicated(registry, cfg):
    bundle = season_bundle(registry, cfg)
    day = bundle.world.clock.now_s // DAY + 1
    bundle.world.events.append(
        GlobalEvent(id=f"natural:harvest_fair:{day}", type="harvest_fair", kind="natural")
    )
    run_tick(bundle, QueueRng(d100=[1]), registry, cfg)
    ids = [e.id for e in bundle.world.events]
    assert len(ids) == len(set(ids))


def test_death_and_chronicle_are_dated_by_the_day_of_death(registry, cfg):
    bundle = bundle_with(registry, cfg)
    start_day = bundle.world.sim.last_day
    run_tick(bundle, QueueRng(d20000=[2, 1]), registry, cfg, days=3)
    npc = bundle.world.npcs["aldric"]
    assert npc.death.at_s == (start_day + 2) * DAY
    entry = next(e for e in bundle.chronicle.entries if e.kind == "death")
    assert entry.at_s == (start_day + 2) * DAY
