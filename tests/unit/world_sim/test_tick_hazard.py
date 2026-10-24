# Ж2 (docs/plan-zh2.md, п. 0.8, коммит 2): hazard событий -- раз в день активный герой в зоне
# события с hazard бросает спасбросок; провал = +1 истощение (cause hazard); шестой уровень
# убивает, если бог не вмешался (ТЗ 4.2); хроника "event" на провал, "death" на смерть, событие
# hero_died в результате тика.
# Зона: регион события (с родителями локаций героя) и affects (у героя групп нет: только пусто
# или "все").
import pytest
from tick_kit import QueueRng, run_tick, solo_hero
from world_sim_kit import DAY, mini_bundle

from ai_dm.state.creature import ActiveEffect, Expiry
from ai_dm.state.world import EventHazard, GlobalEvent
from ai_dm.world_sim import hazard


def plague(event_id="plague", dc="nearly_impossible", **fields):
    return GlobalEvent(
        id=event_id, type="чума", hazard=EventHazard(save="con", dc_category=dc), **fields
    )


def setup(registry, cfg, *events):
    bundle = mini_bundle(registry, cfg)
    hero = solo_hero(bundle)
    bundle.world.events.extend(events)
    return bundle, hero


def failing():
    return QueueRng(d20=[1], default="high")


def passing():
    return QueueRng(d20=[20], default="high")


def saves(rng):
    return rng.asked.count(20)


def event_entries(bundle):
    return [e for e in bundle.chronicle.entries if e.kind == "event"]


# зона

def test_hero_in_zone_rolls_one_save_per_day(registry, cfg):
    bundle, _ = setup(registry, cfg, plague())
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 1


def test_event_without_hazard_gives_no_save(registry, cfg):
    bundle, hero = setup(registry, cfg, GlobalEvent(id="war", type="война"))
    rng = failing()
    assert run_tick(bundle, rng, registry, cfg) == []
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_two_hazard_events_roll_two_saves(registry, cfg):
    bundle, hero = setup(registry, cfg, plague("a"), plague("b"))
    rng = QueueRng(d20=[1, 1], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 2
    assert hero.creature.exhaustion == 2


def test_each_day_rolls_its_own_save(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    rng = QueueRng(d20=[1, 1, 1], default="high")
    run_tick(bundle, rng, registry, cfg, days=3)
    assert saves(rng) == 3
    assert hero.creature.exhaustion == 3


def test_region_of_hero_location_is_in_zone(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(regions=[hero_location(registry, cfg)]))
    run_tick(bundle, failing(), registry, cfg)
    assert hero.creature.exhaustion == 1


def hero_location(registry, cfg):
    return mini_bundle(registry, cfg).heroes[0].location_id


def test_parent_region_of_hero_location_is_in_zone(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(regions=["town"]))
    bundle.world.locations["tavern"].parent_id = "town"
    hero.location_id = "tavern"
    run_tick(bundle, failing(), registry, cfg)
    assert hero.creature.exhaustion == 1


def test_other_region_gives_no_save(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(regions=["cellar"]))
    hero.location_id = "tavern"
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_affects_all_includes_hero(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(affects=["все"]))
    run_tick(bundle, failing(), registry, cfg)
    assert hero.creature.exhaustion == 1


def test_affects_group_does_not_include_hero(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(affects=["торговцы"]))
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_ended_event_gives_no_save(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(ends_at_s=1))
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_not_started_event_gives_no_save(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(started_s=10**12))
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 0


def test_event_ending_after_the_day_start_still_rolls(registry, cfg):
    bundle, hero = setup(registry, cfg)
    bundle.world.events.append(plague())
    at = bundle.world.clock.now_s + DAY
    bundle.world.events[0].ends_at_s = at + 1
    run_tick(bundle, failing(), registry, cfg)
    assert hero.creature.exhaustion == 1


@pytest.mark.parametrize("status", ["in_afterlife", "dead"])
def test_hero_not_active_gives_no_save(registry, cfg, status):
    bundle, hero = setup(registry, cfg, plague())
    hero.status = status
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_every_active_hero_rolls_own_save(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(dc="medium"))
    second = hero.model_copy(deep=True)
    second.id = "zed"
    bundle.heroes.append(second)
    rng = QueueRng(d20=[1, 20], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 2
    # герои идут по id: "hero" бросает первым (провал), "zed" вторым (успех)
    assert (hero.creature.exhaustion, second.creature.exhaustion) == (1, 0)


# спасбросок

def test_failed_save_adds_one_exhaustion(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    run_tick(bundle, failing(), registry, cfg)
    assert hero.creature.exhaustion == 1
    assert hero.status == "active"


def test_failed_hazard_save_does_not_spend_inspiration(registry, cfg):
    # трата была бы немой (строка броска не печатается): переброса нет, истощение +1
    bundle, hero = setup(registry, cfg, plague())
    hero.heroic_inspiration = True
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert hero.heroic_inspiration is True
    assert saves(rng) == 1
    assert hero.creature.exhaustion == 1


def test_savable_failure_keeps_inspiration_and_still_fails(registry, cfg):
    # переброс спас бы (dc medium, на перебросе 20), но вдохновение здесь не тратится
    bundle, hero = setup(registry, cfg, plague(dc="medium"))
    hero.heroic_inspiration = True
    rng = QueueRng(d20=[2], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.heroic_inspiration is True
    assert saves(rng) == 1
    assert hero.creature.exhaustion == 1


def test_expired_effect_is_ignored_by_hazard_save(registry, cfg):
    # помеха истекла к моменту тика: бросается одна d20, не две
    bundle, hero = setup(registry, cfg, plague(dc="medium"))
    hero.creature.active_effects.append(
        ActiveEffect(
            id="curse", source="x", kind="modifier",
            params={"target": "saving_throw", "mode": "disadvantage"},
            expires=Expiry(kind="seconds", value=1),
        )
    )
    rng = passing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 1


def test_passed_save_keeps_exhaustion(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(dc="very_easy"))
    events = run_tick(bundle, passing(), registry, cfg)
    assert hero.creature.exhaustion == 0
    assert events == []
    assert event_entries(bundle) == []


def test_failed_save_writes_event_chronicle_with_refs(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    run_tick(bundle, failing(), registry, cfg)
    entry = event_entries(bundle)[0]
    assert entry.text == f"{hero.name}: чума, истощение 1"
    assert entry.refs == ["plague", hero.id]


def test_chronicle_entry_has_day_time(registry, cfg):
    bundle, _ = setup(registry, cfg, plague())
    run_tick(bundle, failing(), registry, cfg)
    assert event_entries(bundle)[0].at_s == bundle.world.clock.now_s // DAY * DAY


def test_failed_save_returns_no_events_while_alive(registry, cfg):
    bundle, _ = setup(registry, cfg, plague())
    assert run_tick(bundle, failing(), registry, cfg) == []


# смерть на шестом уровне

def dying(registry, cfg, **kw):
    bundle, hero = setup(registry, cfg, plague(), **kw)
    hero.creature.exhaustion = 5
    return bundle, hero


def test_sixth_level_kills_hero_with_hazard_cause(registry, cfg):
    bundle, hero = dying(registry, cfg)
    run_tick(bundle, failing(), registry, cfg)
    assert hero.status == "dead"
    assert hero.death.cause == "hazard"
    assert hero.death.by is None


def test_death_returns_hero_died_event(registry, cfg):
    bundle, hero = dying(registry, cfg)
    events = run_tick(bundle, failing(), registry, cfg)
    died = [e for e in events if e.type == "hero_died"]
    assert len(died) == 1
    assert died[0].data == {"id": hero.id, "cause": "hazard", "by": None}


def test_death_sets_hero_dead_flag(registry, cfg):
    bundle, hero = dying(registry, cfg)
    run_tick(bundle, failing(), registry, cfg)
    assert bundle.world.flags[f"hero_dead:{hero.id}"] is True


def test_death_writes_death_chronicle_entry(registry, cfg):
    bundle, hero = dying(registry, cfg)
    run_tick(bundle, failing(), registry, cfg)
    deaths = [e for e in bundle.chronicle.entries if e.kind == "death"]
    assert [(e.text, e.refs) for e in deaths] == [(f"Смерть: {hero.name} (опасность)", [hero.id])]


def test_death_keeps_event_chronicle_with_level_six(registry, cfg):
    bundle, hero = dying(registry, cfg)
    run_tick(bundle, failing(), registry, cfg)
    assert event_entries(bundle)[0].text == f"{hero.name}: чума, истощение 6"


def test_dead_hero_does_not_roll_second_event(registry, cfg):
    bundle, hero = dying(registry, cfg)
    bundle.world.events.append(plague("b"))
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert saves(rng) == 1


def test_dead_hero_does_not_roll_next_day(registry, cfg):
    bundle, hero = dying(registry, cfg)
    rng = QueueRng(d20=[1, 1], default="high")
    run_tick(bundle, rng, registry, cfg, days=2)
    assert saves(rng) == 1


def test_fifth_level_does_not_kill(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    hero.creature.exhaustion = 4
    run_tick(bundle, failing(), registry, cfg)
    assert (hero.status, hero.creature.exhaustion) == ("active", 5)


def test_death_record_and_chronicle_carry_the_day_time(registry, cfg):
    bundle, hero = dying(registry, cfg)
    run_tick(bundle, failing(), registry, cfg)
    day_start = bundle.world.clock.now_s // DAY * DAY
    assert hero.death.at_s == day_start
    deaths = [e for e in bundle.chronicle.entries if e.kind == "death"]
    assert [e.at_s for e in deaths] == [day_start]


def test_two_heroes_dying_on_the_same_day_give_two_events(registry, cfg):
    bundle, hero = dying(registry, cfg)
    second = hero.model_copy(deep=True)
    second.id = "zed"
    bundle.heroes.append(second)
    rng = QueueRng(d20=[1, 1], default="high")
    events = run_tick(bundle, rng, registry, cfg)
    assert sorted(e.data["id"] for e in events if e.type == "hero_died") == ["hero", "zed"]


def test_hit_chronicle_uses_given_time(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    hero.creature.exhaustion = 5
    hazard.hit(bundle, hero, bundle.world.events[0], 12345, None)
    assert [e.at_s for e in bundle.chronicle.entries] == [12345, 12345]
    assert hero.death.at_s == 12345


# вмешательство бога

def blessed(registry, cfg):
    bundle, hero = dying(registry, cfg)
    hero.favor = {"morrah": 10}
    return bundle, hero


def test_intervention_saves_hero_and_lowers_exhaustion(registry, cfg):
    bundle, hero = blessed(registry, cfg)
    rng = QueueRng(d20=[1], d100=[1], default="high")
    events = run_tick(bundle, rng, registry, cfg)
    assert events == []
    assert (hero.status, hero.creature.exhaustion) == ("active", 5)
    assert hero.divine.intervention_god == "morrah"
    assert hero.death is None


def test_intervention_is_tied_to_current_chapter(registry, cfg):
    bundle, hero = blessed(registry, cfg)
    rng = QueueRng(d20=[1], d100=[1], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.divine.intervention_chapter == bundle.session.current_chapter.id


def test_intervention_without_chapter_uses_empty_id(registry, cfg):
    bundle, hero = blessed(registry, cfg)
    bundle.session.current_chapter = None
    rng = QueueRng(d20=[1], d100=[1], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.divine.intervention_chapter == ""
    assert hero.status == "active"


def test_failed_intervention_roll_leaves_hero_dead(registry, cfg):
    bundle, hero = blessed(registry, cfg)
    rng = QueueRng(d20=[1], d100=[100], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.status == "dead"


def test_intervention_once_per_chapter(registry, cfg):
    bundle, hero = blessed(registry, cfg)
    hero.divine.intervention_chapter = bundle.session.current_chapter.id
    rng = QueueRng(d20=[1], d100=[1], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.status == "dead"


def test_low_favor_gives_no_intervention(registry, cfg):
    bundle, hero = dying(registry, cfg)
    hero.favor = {"morrah": 8}
    rng = QueueRng(d20=[1], d100=[1], default="high")
    run_tick(bundle, rng, registry, cfg)
    assert hero.status == "dead"


# место в дне тика: после смертности, до закрытия событий

def test_mortality_roll_precedes_hazard_save(registry, cfg):
    bundle, _ = setup(registry, cfg, plague())
    rng = failing()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == [bundle.world.mortality_per_day, 20]


def test_hero_dead_by_chance_does_not_roll_hazard(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    rng = QueueRng(default="high", **{f"d{bundle.world.mortality_per_day}": [1]})
    run_tick(bundle, rng, registry, cfg)
    assert hero.death.cause == "chance"
    assert saves(rng) == 0
    assert hero.creature.exhaustion == 0


def test_tick_returns_hazard_death_after_mortality_events(registry, cfg):
    bundle, hero = dying(registry, cfg)
    events = run_tick(bundle, failing(), registry, cfg, days=2)
    assert [e.type for e in events] == ["hero_died"]


# функции модуля напрямую

def test_zone_events_returns_only_hazard_events_in_zone(registry, cfg):
    bundle, hero = setup(
        registry, cfg, plague("a"), GlobalEvent(id="war", type="война"), plague("b", regions=["x"])
    )
    ids = [e.id for e in hazard.zone_events(bundle.world, hero, 0)]
    assert ids == ["a"]


def test_failed_save_is_true_only_for_fail(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(dc="medium"))
    event = bundle.world.events[0]
    assert hazard.failed_save(hero, event, registry, QueueRng(d20=[1]), 0) is True
    assert hazard.failed_save(hero, event, registry, QueueRng(d20=[20]), 0) is False


def test_failed_save_uses_event_dc_category(registry, cfg):
    bundle, hero = setup(registry, cfg, plague(dc="very_easy"))
    event = bundle.world.events[0]
    assert hazard.failed_save(hero, event, registry, QueueRng(d20=[10]), 0) is False


def test_hit_returns_empty_for_alive_hero(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    event = bundle.world.events[0]
    assert hazard.hit(bundle, hero, event, 0, None) == []
    assert hero.creature.exhaustion == 1


def test_hit_uses_given_intervene_callback(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    hero.creature.exhaustion = 5
    assert hazard.hit(bundle, hero, bundle.world.events[0], 0, lambda target: "morrah") == []
    assert hero.status == "active"


def test_hit_death_has_no_intervene_without_callback(registry, cfg):
    bundle, hero = setup(registry, cfg, plague())
    hero.creature.exhaustion = 5
    done = hazard.hit(bundle, hero, bundle.world.events[0], 0, None)
    assert [e.type for e in done] == ["hero_died"]


def test_intervener_returns_god_for_blessed_hero(registry, cfg):
    bundle, hero = setup(registry, cfg)
    hero.favor = {"morrah": 10}
    rng = QueueRng(d100=[1])
    assert hazard.intervener(bundle, rng, cfg)(hero) == "morrah"


def test_intervener_returns_none_without_favor(registry, cfg):
    bundle, hero = setup(registry, cfg)
    assert hazard.intervener(bundle, QueueRng(d100=[1]), cfg)(hero) is None


def test_roll_hazards_without_heroes_is_empty(registry, cfg):
    bundle, _ = setup(registry, cfg, plague())
    bundle.heroes.clear()
    assert hazard.roll_hazards(bundle, failing(), cfg, registry, 0) == []
