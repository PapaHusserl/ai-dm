# Ожидаемый API: ai_dm.world_sim.tick.tick_days -- смертность по дням (ТЗ 4.1 п.3, 4.1.1), контракт
# в tick_kit.py. Герой в тестах с одним существом ставится в in_afterlife (там не бросает).
import pytest
from tick_kit import QueueRng, new_npc, nobody, run_tick, solo_hero, solo_npc
from world_sim_kit import DAY, mini_bundle

from ai_dm.core.rng import Rng

PER_DAY = 20000


def bundle_of(registry, cfg, npc_id="aldric"):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    solo_npc(bundle, npc_id)
    return bundle


def test_one_roll_per_named_npc_per_day(registry, cfg):
    bundle = bundle_of(registry, cfg)
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == [PER_DAY]


def test_roll_hit_kills_npc_with_chance_record(registry, cfg):
    bundle = bundle_of(registry, cfg)
    events = run_tick(bundle, QueueRng(d20000=[1]), registry, cfg)
    npc = bundle.world.npcs["aldric"]
    assert npc.status == "dead"
    assert npc.death.cause == "chance"
    assert any(e.type == "npc_died" for e in events)


def test_death_sets_auto_flag_and_chronicle_entry(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(d20000=[1]), registry, cfg)
    assert bundle.world.flags["npc_dead:aldric"] is True
    entries = [e for e in bundle.chronicle.entries if e.kind == "death"]
    assert any("aldric" in e.refs for e in entries)


def test_roll_miss_keeps_npc_alive(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(d20000=[2]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "alive"
    assert "npc_dead:aldric" not in bundle.world.flags


def test_dead_npc_is_not_rolled_again(registry, cfg):
    bundle = bundle_of(registry, cfg)
    rng = QueueRng(d20000=[1])
    run_tick(bundle, rng, registry, cfg)
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == [PER_DAY]


def test_unnamed_npc_is_not_tracked(registry, cfg):
    bundle = bundle_of(registry, cfg, "guard")
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == []
    assert bundle.world.npcs["guard"].status == "alive"


def test_gone_npc_is_not_rolled(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].status = "gone"
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == []


def test_hero_in_afterlife_is_not_rolled(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    rng = QueueRng()
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == []


def test_hero_roll_hit_kills_hero_by_chance(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    hero = solo_hero(bundle)
    events = run_tick(bundle, QueueRng(d20000=[1]), registry, cfg)
    assert hero.status == "dead"
    assert hero.death.cause == "chance"
    assert any(e.type == "hero_died" for e in events)
    assert bundle.world.flags["hero_dead:hero"] is True


def test_hero_gets_one_roll_per_day(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    solo_hero(bundle)
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == [PER_DAY]


# благосклонность: «отвести беду»

def test_favor_ten_always_saves(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"selune": 10}
    run_tick(bundle, QueueRng(d20000=[1], d10=[10]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "alive"


def test_favor_zero_never_saves(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(d20000=[1], d10=[1]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "dead"


def test_favor_uses_the_most_favored_god(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"morrah": 2, "selune": 7}
    run_tick(bundle, QueueRng(d20000=[1], d10=[7]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "alive"


def test_favor_roll_above_favor_does_not_save(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"selune": 3}
    run_tick(bundle, QueueRng(d20000=[1], d10=[4]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "dead"


def test_favor_roll_equal_to_favor_saves(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"selune": 3}
    run_tick(bundle, QueueRng(d20000=[1], d10=[3]), registry, cfg)
    assert bundle.world.npcs["aldric"].status == "alive"


def test_saved_npc_leaves_chronicle_entry(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"selune": 10}
    run_tick(bundle, QueueRng(d20000=[1], d10=[10]), registry, cfg)
    assert any("aldric" in e.refs for e in bundle.chronicle.entries)
    assert not [e for e in bundle.chronicle.entries if e.kind == "death"]


def test_favor_does_not_save_without_roll_hit(registry, cfg):
    bundle = bundle_of(registry, cfg)
    bundle.world.npcs["aldric"].favor = {"selune": 10}
    rng = QueueRng(d20000=[2])
    run_tick(bundle, rng, registry, cfg)
    assert rng.asked == [PER_DAY]


def test_hero_favor_ten_saves_hero(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.mortality_per_day = PER_DAY
    hero = solo_hero(bundle)
    hero.favor = {"selune": 10}
    run_tick(bundle, QueueRng(d20000=[1], d10=[10]), registry, cfg)
    assert hero.status == "active"


# пресеты по сиду

def population(registry, cfg, preset):
    bundle = mini_bundle(registry, cfg)
    nobody(bundle)
    bundle.world.mortality_per_day = cfg.world.mortality_presets[preset]
    for number in range(100):
        bundle.world.npcs[f"n{number:03d}"] = new_npc(f"n{number:03d}")
    return bundle


def dead_count(bundle):
    return len([n for n in bundle.world.npcs.values() if n.status == "dead"])


def thirty_days(registry, cfg, preset, seed):
    bundle = population(registry, cfg, preset)
    run_tick(bundle, Rng(seed), registry, cfg, days=30)
    return bundle


def test_brutal_preset_deaths_are_in_expected_interval_over_50_seeds(registry, cfg):
    # 100 NPC x 30 дней при 1/500: ожидание ~5,8 смертей на прогон
    counts = [dead_count(thirty_days(registry, cfg, "brutal", seed)) for seed in range(50)]
    mean = sum(counts) / len(counts)
    assert 4.0 <= mean <= 8.0
    assert max(counts) <= 20
    assert min(counts) < max(counts)


def test_brutal_preset_is_reproducible_by_seed(registry, cfg):
    first = thirty_days(registry, cfg, "brutal", 3)
    second = thirty_days(registry, cfg, "brutal", 3)
    assert first.world.model_dump_json() == second.world.model_dump_json()
    assert first.chronicle.model_dump_json() == second.chronicle.model_dump_json()


def test_brutal_preset_other_seed_gives_other_deaths(registry, cfg):
    dead = [
        sorted(n.id for n in thirty_days(registry, cfg, "brutal", seed).world.npcs.values()
               if n.status == "dead")
        for seed in range(5)
    ]
    assert len({tuple(d) for d in dead}) > 1


def test_calm_preset_has_no_deaths_in_thirty_days(registry, cfg):
    bundle = thirty_days(registry, cfg, "calm", 1)
    assert dead_count(bundle) == 0


def test_brutal_deaths_all_have_chance_cause(registry, cfg):
    bundle = thirty_days(registry, cfg, "brutal", 1)
    dead = [n for n in bundle.world.npcs.values() if n.status == "dead"]
    assert dead
    assert {n.death.cause for n in dead} == {"chance"}


# скачок времени = дневные шаги

@pytest.mark.parametrize("days", [7, 30])
def test_jump_is_one_step_per_day(days, registry, cfg):
    bundle = bundle_of(registry, cfg)
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg, days=days)
    assert rng.asked.count(PER_DAY) == days


def test_tick_updates_last_day(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=5)
    assert bundle.world.sim.last_day == bundle.world.clock.now_s // DAY


def test_tick_without_new_day_does_not_roll(registry, cfg):
    bundle = bundle_of(registry, cfg)
    rng = QueueRng()
    from ai_dm.world_sim.tick import tick_days

    assert tick_days(bundle, rng, cfg, registry) == []
    assert rng.asked == []


def test_jump_over_max_tick_days_rolls_only_last_window(registry, cfg):
    bundle = bundle_of(registry, cfg)
    limit = cfg.world.max_tick_days
    rng = QueueRng(default="high")
    run_tick(bundle, rng, registry, cfg, days=limit + 50)
    assert rng.asked.count(PER_DAY) == limit
    assert bundle.world.sim.last_day == bundle.world.clock.now_s // DAY


def test_jump_over_max_tick_days_writes_chronicle_line(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(
        bundle, QueueRng(default="high"), registry, cfg, days=cfg.world.max_tick_days + 1
    )
    assert any("без подробностей" in e.text for e in bundle.chronicle.entries)


def test_jump_within_max_tick_days_has_no_summary_line(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=cfg.world.max_tick_days)
    assert not any("без подробностей" in e.text for e in bundle.chronicle.entries)


# mortality.affected(event, chain, groups): регион и группа риска (общая часть с hazard, Ж2)

def ev(**fields):
    from ai_dm.state.world import GlobalEvent

    return GlobalEvent(id="e", type="чума", **fields)


def affected(event, chain, groups):
    from ai_dm.world_sim.mortality import affected as fn

    return fn(event, chain, groups)


def test_affected_event_without_regions_and_affects_covers_everyone():
    assert affected(ev(), ["town"], []) is True


def test_affected_region_must_be_in_chain():
    assert affected(ev(regions=["town"]), ["tavern", "town"], []) is True
    assert affected(ev(regions=["town"]), ["cellar"], []) is False


def test_affected_any_of_regions_is_enough():
    assert affected(ev(regions=["a", "town"]), ["town"], []) is True


def test_affected_empty_chain_is_outside_regions():
    assert affected(ev(regions=["town"]), [], []) is False


def test_affected_group_must_match():
    assert affected(ev(affects=["торговцы"]), [], ["торговцы"]) is True
    assert affected(ev(affects=["торговцы"]), [], ["воины"]) is False
    assert affected(ev(affects=["торговцы"]), [], []) is False


def test_affected_all_word_covers_creature_without_groups():
    assert affected(ev(affects=["все"]), [], []) is True


def test_affected_needs_both_region_and_group():
    event = ev(regions=["town"], affects=["торговцы"])
    assert affected(event, ["town"], ["торговцы"]) is True
    assert affected(event, ["town"], ["воины"]) is False
    assert affected(event, ["cellar"], ["торговцы"]) is False


def test_multiplier_takes_maximum_over_affecting_active_events(registry, cfg):
    from ai_dm.state.world import GlobalEvent
    from ai_dm.world_sim.mortality import multiplier

    bundle = bundle_of(registry, cfg)
    npc = bundle.world.npcs["aldric"]
    bundle.world.events += [
        GlobalEvent(id="a", type="чума", mortality_multiplier=3),
        GlobalEvent(id="b", type="война", mortality_multiplier=7),
        GlobalEvent(id="c", type="голод", mortality_multiplier=50, regions=["nowhere"]),
        GlobalEvent(id="d", type="мор", mortality_multiplier=60, ends_at_s=1),
        GlobalEvent(id="e", type="гроза", mortality_multiplier=70, affects=["торговцы"]),
    ]
    assert multiplier(bundle.world, "npc", npc, bundle.world.clock.now_s) == 7


def test_multiplier_hero_ignores_group_filter(registry, cfg):
    from ai_dm.state.world import GlobalEvent
    from ai_dm.world_sim.mortality import multiplier

    bundle = bundle_of(registry, cfg)
    bundle.world.events.append(
        GlobalEvent(id="e", type="гроза", mortality_multiplier=9, affects=["торговцы"])
    )
    hero = bundle.heroes[0]
    assert multiplier(bundle.world, "hero", hero, bundle.world.clock.now_s) == 1
    bundle.world.events[-1].affects = ["все"]
    assert multiplier(bundle.world, "hero", hero, bundle.world.clock.now_s) == 9


def test_jump_of_max_tick_days_is_allowed(registry, cfg):
    bundle = bundle_of(registry, cfg)
    run_tick(bundle, QueueRng(default="high"), registry, cfg, days=cfg.world.max_tick_days)
    assert bundle.world.sim.last_day == bundle.world.clock.now_s // DAY
