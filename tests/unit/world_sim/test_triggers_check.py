# Ожидаемый API: ai_dm.world_sim.triggers.check -- контракт в world_sim_kit.py.
# Структурные триггеры на границе сцены: once, cooldown, мёртвые, фракции, боги, герой.
from world_sim_kit import DAY, field, has_ref, mini_bundle, refs_of, run_check, trigger_of

from ai_dm.core.duration import Duration
from ai_dm.state.triggers import Trigger


def test_trigger_with_false_condition_does_not_fire(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    result = run_check(bundle)
    assert result.fired == []
    assert not has_ref(refs_of(result), "trigger:")


def test_flag_trigger_fires(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    result = run_check(bundle)
    assert has_ref(result.fired, "aldric", "steal_grail")


def test_fired_trigger_counts_and_becomes_fired_when_once(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    run_check(bundle)
    trigger = trigger_of(bundle, "aldric", "steal_grail")
    assert trigger.fired_count == 1
    assert trigger.state == "fired"
    assert trigger.last_fired_at == bundle.world.clock.now_s


def test_fired_trigger_is_written_to_world_fired(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    run_check(bundle)
    assert len(bundle.world.fired) == 1
    assert "steal_grail" in bundle.world.fired[0].ref
    assert bundle.world.fired[0].at_s == bundle.world.clock.now_s


def test_fired_trigger_is_written_to_chronicle(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    before = len(bundle.chronicle.entries)
    run_check(bundle)
    entries = bundle.chronicle.entries[before:]
    assert [e.kind for e in entries] == ["trigger"]
    assert entries[0].at_s == bundle.world.clock.now_s


def test_fired_trigger_gives_act_candidate_with_then(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    result = run_check(bundle)
    acts = [c for c in result.candidates if field(c, "kind") == "act"]
    assert len(acts) == 1
    assert "steal_grail" in field(acts[0], "ref")
    assert field(acts[0], "then") == "Олдрик крадёт чашу"


def test_once_trigger_does_not_fire_on_next_boundary(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    run_check(bundle)
    result = run_check(bundle)
    assert result.fired == []
    assert not has_ref(refs_of(result), "trigger:")
    assert trigger_of(bundle, "aldric", "steal_grail").fired_count == 1


def test_cooldown_trigger_does_not_fire_before_cooldown(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["alarm"] = True
    run_check(bundle)
    bundle.world.clock.now_s += 7 * DAY - 1
    result = run_check(bundle)
    assert result.fired == []
    assert trigger_of(bundle, "mara", "mara_shout").fired_count == 1


def test_cooldown_trigger_fires_again_after_cooldown(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["alarm"] = True
    run_check(bundle)
    bundle.world.clock.now_s += Duration.parse("7d").seconds
    result = run_check(bundle)
    assert has_ref(result.fired, "mara", "mara_shout")
    assert trigger_of(bundle, "mara", "mara_shout").fired_count == 2


def test_cooldown_trigger_stays_active_not_fired(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["alarm"] = True
    run_check(bundle)
    assert trigger_of(bundle, "mara", "mara_shout").state == "active"


def test_dead_npc_trigger_does_not_fire(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    bundle.world.npcs["aldric"].status = "dead"
    result = run_check(bundle)
    assert result.fired == []
    assert trigger_of(bundle, "aldric", "steal_grail").fired_count == 0


def test_gone_npc_trigger_does_not_fire(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    bundle.world.npcs["aldric"].status = "gone"
    assert run_check(bundle).fired == []


def test_disabled_trigger_does_not_fire(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    trigger_of(bundle, "aldric", "steal_grail").state = "disabled"
    assert run_check(bundle).fired == []


def test_faction_trigger_fires(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["mara"].status = "dead"
    result = run_check(bundle)
    assert has_ref(result.fired, "guild", "guild_hunt")


def test_faction_trigger_waits_while_condition_false(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    assert not has_ref(run_check(bundle).fired, "guild")


def test_god_trigger_fires_on_first_check(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["pilgrim_prayed"] = True
    assert has_ref(run_check(bundle).fired, "selune", "bless_pilgrim")


def test_god_trigger_is_not_checked_before_check_every_days(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    run_check(bundle)
    bundle.world.flags["pilgrim_prayed"] = True
    bundle.world.clock.now_s += DAY
    assert not has_ref(run_check(bundle).fired, "selune")


def test_god_trigger_is_checked_after_check_every_days(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    run_check(bundle)
    bundle.world.flags["pilgrim_prayed"] = True
    bundle.world.clock.now_s += 7 * DAY
    assert has_ref(run_check(bundle).fired, "selune", "bless_pilgrim")


def test_hero_trigger_fires(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.heroes[0].opportunity.append(
        Trigger(id="hero_cellar", **{"if": {"hero_at": "tavern"}}, then="герой замечен")
    )
    result = run_check(bundle)
    assert has_ref(result.fired, "hero_cellar")


def test_hero_trigger_with_false_condition_does_not_fire(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.heroes[0].opportunity.append(
        Trigger(id="hero_cellar", **{"if": {"hero_at": "cellar"}}, then="герой замечен")
    )
    assert run_check(bundle).fired == []


def test_event_active_condition_trigger_fires(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["guard"].opportunity.append(
        Trigger(id="guard_cold", **{"if": {"event_active": "cold_snap"}}, then="мёрзнет")
    )
    assert has_ref(run_check(bundle).fired, "guard_cold")


def test_candidates_order_is_god_faction_npc_then_ids(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags.update({"grail_seen": True, "alarm": True, "pilgrim_prayed": True})
    result = run_check(bundle)
    refs = refs_of(result, "act")
    positions = [
        next(i for i, r in enumerate(refs) if part in r)
        for part in ("selune", "aldric", "mara")
    ]
    assert positions == sorted(positions)
    assert refs[0].count("selune") == 1


def test_check_is_deterministic(registry, cfg):
    first = mini_bundle(registry, cfg)
    second = mini_bundle(registry, cfg)
    for bundle in (first, second):
        bundle.world.flags.update({"grail_seen": True, "alarm": True})
        run_check(bundle)
    assert first.model_dump_json() == second.model_dump_json()
