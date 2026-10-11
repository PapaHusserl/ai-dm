# Ожидаемый API: ai_dm.world_sim.tick.tick_days -- старость (ТЗ 4.1 п.4), контракт в tick_kit.py.
# Год у мира -- 12 x 30 дней (calendar.seconds_in_year). Тик через границу года:
# at_year_end + 1 день.
import pytest
from tick_kit import (
    YEAR,
    QueueRng,
    at_year_end,
    birth_for_age,
    deaths_by,
    entries_with,
    new_npc,
    nobody,
    run_tick,
    solo_hero,
)
from world_sim_kit import DAY, mini_bundle

from ai_dm.core.rng import Rng

PER_DAY = 500000


def year_bundle(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    bundle.world.mortality_per_day = PER_DAY
    at_year_end(bundle)
    return bundle


def add_npcs(bundle, count, species, age, prefix="n", **fields):
    for number in range(count):
        npc_id = f"{prefix}{number:03d}"
        bundle.world.npcs[npc_id] = new_npc(
            npc_id, species_id=species, birth_s=birth_for_age(age), **fields
        )


def new_year(bundle, registry, cfg, rng=None):
    return run_tick(bundle, rng or Rng(5), registry, cfg)


def alive(bundle):
    return [n for n in bundle.world.npcs.values() if n.status == "alive"]


# шанс естественной смерти

@pytest.mark.parametrize(
    "species, age", [("human", 59), ("halfling", 99), ("dwarf", 249), ("elf", 499)]
)
def test_below_threshold_no_old_age_check(species, age, registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 100, species, age)
    new_year(bundle, registry, cfg)
    assert deaths_by(bundle, "old_age") == []


def test_human_75_dies_about_half(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 200, "human", 75)
    new_year(bundle, registry, cfg)
    assert 70 <= len(deaths_by(bundle, "old_age")) <= 130


def test_dwarf_300_dies_about_half(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 200, "dwarf", 300)
    new_year(bundle, registry, cfg)
    assert 70 <= len(deaths_by(bundle, "old_age")) <= 130


@pytest.mark.parametrize("age", [90, 120])
def test_human_at_limit_and_over_always_dies(age, registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 50, "human", age)
    new_year(bundle, registry, cfg)
    assert len(deaths_by(bundle, "old_age")) == 50


def test_old_age_death_has_record_flag_and_chronicle(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 1, "human", 95)
    events = new_year(bundle, registry, cfg)
    npc = bundle.world.npcs["n000"]
    assert npc.death.cause == "old_age"
    assert bundle.world.flags["npc_dead:n000"] is True
    assert any(e.type == "npc_died" for e in events)
    assert entries_with(bundle, "n000", "death")


def test_favor_does_not_save_from_old_age(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 20, "human", 95, favor={"selune": 10})
    rng = QueueRng(default="high")
    new_year(bundle, registry, cfg, rng)
    assert len(deaths_by(bundle, "old_age")) == 20
    assert 10 not in rng.asked


def test_npc_without_species_does_not_age(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 5, None, 500)
    new_year(bundle, registry, cfg)
    assert len(alive(bundle)) == 5
    assert {n.aging_steps for n in bundle.world.npcs.values()} == {0}


def test_npc_without_birth_does_not_age(registry, cfg):
    bundle = year_bundle(registry, cfg)
    bundle.world.npcs["dragon"] = new_npc("dragon", species_id="human", birth_s=None)
    new_year(bundle, registry, cfg)
    assert bundle.world.npcs["dragon"].status == "alive"
    assert bundle.world.npcs["dragon"].aging_steps == 0


def test_check_is_once_per_year_not_per_day(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 200, "human", 75)
    new_year(bundle, registry, cfg)
    survivors = len(alive(bundle))
    run_tick(bundle, Rng(6), registry, cfg, days=30)
    assert len(alive(bundle)) == survivors


def test_check_repeats_next_year(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 200, "human", 75)
    new_year(bundle, registry, cfg)
    survivors = len(alive(bundle))
    run_tick(bundle, Rng(6), registry, cfg, days=360)
    assert len(alive(bundle)) < survivors


def test_dead_npc_is_not_checked_again(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 10, "human", 95)
    new_year(bundle, registry, cfg)
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg, days=360)
    assert PER_DAY not in rng.asked


def test_old_age_does_not_check_in_afterlife_hero(registry, cfg):
    bundle = year_bundle(registry, cfg)
    bundle.heroes[0].birth_s = birth_for_age(95)
    new_year(bundle, registry, cfg)
    assert bundle.heroes[0].status == "in_afterlife"


# минусы NPC

def test_npc_aging_steps_follow_ten_percent_of_limit(registry, cfg):
    # человек 60/90: шаг 9 лет; возраст 78 -> (78 - 60) // 9 = 2
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 20, "human", 78)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert {n.aging_steps for n in alive(bundle)} == {2}


@pytest.mark.parametrize("age, steps", [(60, 0), (68, 0), (69, 1), (77, 1), (78, 2)])
def test_npc_aging_steps_boundaries(age, steps, registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 1, "human", age)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert bundle.world.npcs["n000"].aging_steps == steps


def test_npc_aging_step_leaves_chronicle_line_and_keeps_means(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 1, "human", 78)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert entries_with(bundle, "n000")
    assert bundle.world.npcs["n000"].means == ["связи"]


def test_npc_aging_below_threshold_leaves_no_line(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 1, "human", 40)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert not entries_with(bundle, "n000")


def test_aging_step_percent_comes_from_config(registry, cfg):
    bundle = year_bundle(registry, cfg)
    add_npcs(bundle, 1, "human", 69)
    wide = cfg.model_copy(deep=True)
    wide.world.aging.step_percent = 20
    new_year(bundle, registry, wide, QueueRng(default="high"))
    # шаг 18 лет: (69 - 60) // 18 = 0
    assert bundle.world.npcs["n000"].aging_steps == 0


# минусы героя

def old_hero(bundle, age):
    hero = solo_hero(bundle)
    hero.status = "active"
    hero.birth_s = birth_for_age(age)
    return hero


def old_age_effects(hero):
    return [e for e in hero.creature.active_effects if e.kind == "old_age"]


def hero_bundle(registry, cfg, age):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    at_year_end(bundle)
    hero = old_hero(bundle, age)
    return bundle, hero


@pytest.mark.parametrize("age, steps", [(69, 1), (78, 2)])
def test_hero_gets_old_age_effect_with_steps(age, steps, registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, age)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    effects = old_age_effects(hero)
    assert len(effects) == 1
    assert effects[0].id == "old_age"
    assert effects[0].params["steps"] == steps


@pytest.mark.parametrize("age", [40, 59, 68])
def test_hero_without_steps_has_no_old_age_effect(age, registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, age)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert old_age_effects(hero) == []


def test_hero_old_age_effect_is_not_duplicated_next_year(registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, 69)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=360)
    effects = old_age_effects(hero)
    assert len(effects) == 1
    assert effects[0].params["steps"] == 1


def test_hero_old_age_effect_grows_with_age(registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, 77)
    new_year(bundle, registry, cfg, QueueRng(default="high"))
    assert old_age_effects(hero)[0].params["steps"] == 1
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=360)
    assert old_age_effects(hero)[0].params["steps"] == 2


def test_hero_over_limit_dies_of_old_age(registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, 95)
    events = new_year(bundle, registry, cfg)
    assert hero.status == "dead"
    assert hero.death.cause == "old_age"
    assert any(e.type == "hero_died" for e in events)


def test_hero_favor_does_not_save_from_old_age(registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, 95)
    hero.favor = {"selune": 10}
    new_year(bundle, registry, cfg)
    assert hero.status == "dead"


def test_hero_without_birth_does_not_age(registry, cfg):
    bundle, hero = hero_bundle(registry, cfg, 95)
    hero.birth_s = None
    new_year(bundle, registry, cfg)
    assert hero.status == "active"
    assert old_age_effects(hero) == []


def test_year_constant_matches_calendar(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    assert bundle.world.clock.calendar.seconds_in_year == YEAR == 360 * DAY
