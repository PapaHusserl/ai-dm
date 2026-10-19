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


def test_fire_trigger_fires_records_and_returns_ref_and_act(registry, cfg):
    from ai_dm.world_sim.triggers import fire_trigger

    bundle = mini_bundle(registry, cfg)
    owner = bundle.world.npcs["aldric"]
    trigger = next(t for t in owner.opportunity if t.id == "steal_grail")
    before = len(bundle.chronicle.entries)
    ref, act = fire_trigger(bundle, "npc", owner, trigger)
    assert "steal_grail" in ref
    assert (field(act, "kind"), field(act, "ref"), field(act, "then")) == (
        "act", ref, "Олдрик крадёт чашу",
    )
    assert trigger.fired_count == 1
    assert [f.ref for f in bundle.world.fired] == [ref]
    assert [e.kind for e in bundle.chronicle.entries[before:]] == ["trigger"]


def test_fire_trigger_chronicle_entry_refers_to_trigger_ref(registry, cfg):
    from ai_dm.world_sim.triggers import fire_trigger

    bundle = mini_bundle(registry, cfg)
    owner = bundle.world.npcs["aldric"]
    trigger = next(t for t in owner.opportunity if t.id == "steal_grail")
    before = len(bundle.chronicle.entries)
    ref, _ = fire_trigger(bundle, "npc", owner, trigger)
    assert bundle.chronicle.entries[before].refs == [ref]


def test_skipped_goal_trigger_before_ordinary_one_does_not_stop_it_firing(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    aldric = bundle.world.npcs["aldric"]
    aldric.opportunity.reverse()
    assert aldric.opportunity[0].id == goal_ref(bundle)
    bundle.world.flags["grail_seen"] = True
    bundle.world.clock.now_s += 60
    assert has_ref(run_check(bundle, cfg).fired, "aldric", "steal_grail")


def test_fire_trigger_closes_goal_of_goal_trigger(registry, cfg):
    from ai_dm.world_sim.triggers import fire_trigger

    bundle = goal_bundle(registry, cfg)
    owner = bundle.world.npcs["aldric"]
    trigger = next(t for t in owner.opportunity if t.id == goal_ref(bundle))
    fire_trigger(bundle, "npc", owner, trigger)
    assert owner.goals[0].status == "done"


def test_fire_trigger_of_ordinary_trigger_leaves_goals_alone(registry, cfg):
    from ai_dm.world_sim.triggers import fire_trigger

    bundle = goal_bundle(registry, cfg)
    owner = bundle.world.npcs["aldric"]
    trigger = next(t for t in owner.opportunity if t.id == "steal_grail")
    fire_trigger(bundle, "npc", owner, trigger)
    assert owner.goals[0].status == "active"


# Ж2 (docs/plan-zh2.md, пп. 0.3, 0.4): триггеры целей NPC -- редкая проверка (goals_checked_s,
# [world] goals_check_every_days), закрытие цели по fire, sweep в начале check.

def goal_bundle(registry, cfg, owner="aldric"):
    from ai_dm.rules.goals import add_goal

    bundle = mini_bundle(registry, cfg)
    add_goal(bundle.world.npcs[owner], "revenge", bundle.heroes[0].id, "мстит", 0)
    return bundle


def goal_ref(bundle):
    return f"goal:revenge:{bundle.heroes[0].id}"


def make_structural(bundle, owner="aldric"):
    # условие спутника без нарративной части: триггер срабатывает самим check
    from ai_dm.state.triggers import Trigger

    npc = bundle.world.npcs[owner]
    npc.opportunity = [
        Trigger(id=goal_ref(bundle), **{"if": {"flag": "go"}}, then="мститель пришёл", once=True)
    ]


def at(cfg, days):
    copy = cfg.model_copy(deep=True)
    copy.world.goals_check_every_days = days
    return copy


def test_goal_trigger_is_verdict_candidate_on_first_check(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    result = run_check(bundle, cfg)
    assert has_ref(refs_of(result, "verdict"), "aldric", goal_ref(bundle))


def test_check_sets_goals_checked_s_to_now(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    bundle.world.clock.now_s = 5 * DAY
    run_check(bundle, cfg)
    assert bundle.world.sim.goals_checked_s == 5 * DAY


def test_check_without_any_goals_still_marks_the_check(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    run_check(bundle, cfg)
    assert bundle.world.sim.goals_checked_s == bundle.world.clock.now_s


def test_second_boundary_the_same_day_skips_goal_triggers(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    bundle.world.clock.now_s += 3600
    result = run_check(bundle, cfg)
    assert not has_ref(refs_of(result), goal_ref(bundle))


def test_skipped_check_does_not_move_goals_checked_s(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    first = bundle.world.sim.goals_checked_s
    bundle.world.clock.now_s += DAY - 1
    run_check(bundle, cfg)
    assert bundle.world.sim.goals_checked_s == first


def test_goal_trigger_is_checked_again_after_a_day(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    bundle.world.clock.now_s += DAY
    result = run_check(bundle, cfg)
    assert has_ref(refs_of(result, "verdict"), goal_ref(bundle))
    assert bundle.world.sim.goals_checked_s == bundle.world.clock.now_s


def test_check_every_days_comes_from_config(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    three = at(cfg, 3)
    run_check(bundle, three)
    bundle.world.clock.now_s += 2 * DAY
    assert not has_ref(refs_of(run_check(bundle, three)), goal_ref(bundle))
    bundle.world.clock.now_s += DAY
    assert has_ref(refs_of(run_check(bundle, three)), goal_ref(bundle))


def test_ordinary_triggers_are_checked_every_boundary(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    bundle.world.flags["grail_seen"] = True
    bundle.world.clock.now_s += 60
    assert has_ref(run_check(bundle, cfg).fired, "aldric", "steal_grail")


def test_ordinary_verdict_candidate_stays_when_goals_are_not_due(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    bundle.world.flags["met_brann"] = True
    result = run_check(bundle, cfg)
    assert has_ref(refs_of(result, "verdict"), "brann", "brann_trust")


def test_structural_goal_trigger_fires_and_goal_becomes_done(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    make_structural(bundle)
    bundle.world.flags["go"] = True
    result = run_check(bundle, cfg)
    assert has_ref(result.fired, "aldric", goal_ref(bundle))
    [goal] = bundle.world.npcs["aldric"].goals
    assert goal.status == "done"
    assert has_ref(refs_of(result, "act"), "aldric", goal_ref(bundle))


def test_structural_goal_trigger_does_not_fire_when_goals_not_due(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    make_structural(bundle)
    run_check(bundle, cfg)
    bundle.world.flags["go"] = True
    bundle.world.clock.now_s += 60
    result = run_check(bundle, cfg)
    assert result.fired == []
    assert bundle.world.npcs["aldric"].goals[0].status == "active"


def test_fired_goal_trigger_is_not_a_candidate_next_time(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    make_structural(bundle)
    bundle.world.flags["go"] = True
    run_check(bundle, cfg)
    bundle.world.clock.now_s += DAY
    result = run_check(bundle, cfg)
    assert result.fired == []
    assert not has_ref(refs_of(result), goal_ref(bundle))


def test_ordinary_trigger_fire_does_not_close_goals(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    bundle.world.flags["grail_seen"] = True
    run_check(bundle, cfg)
    assert bundle.world.npcs["aldric"].goals[0].status == "active"


def test_check_drops_goal_when_hero_is_dead(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    bundle.heroes[0].status = "dead"
    result = run_check(bundle, cfg)
    assert bundle.world.npcs["aldric"].goals[0].status == "dropped"
    assert not has_ref(refs_of(result), goal_ref(bundle))


def test_check_drops_goal_even_when_goals_are_not_due(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    run_check(bundle, cfg)
    bundle.heroes[0].status = "dead"
    bundle.world.clock.now_s += 60
    run_check(bundle, cfg)
    assert bundle.world.npcs["aldric"].goals[0].status == "dropped"


def test_check_drops_goal_of_dead_carrier(registry, cfg):
    bundle = goal_bundle(registry, cfg)
    bundle.world.npcs["aldric"].status = "dead"
    run_check(bundle, cfg)
    assert bundle.world.npcs["aldric"].goals[0].status == "dropped"


def test_goal_trigger_is_not_a_candidate_for_a_dead_target_npc(registry, cfg):
    from ai_dm.rules.goals import add_npc_goal

    bundle = mini_bundle(registry, cfg)
    add_npc_goal(bundle.world.npcs["aldric"], "love", "mara", "x", 0)
    bundle.world.npcs["mara"].status = "dead"
    result = run_check(bundle, cfg)
    assert not has_ref(refs_of(result), "goal:love:mara")
    assert bundle.world.npcs["aldric"].goals[0].status == "dropped"


def test_pack_preset_hero_trigger_fires_in_new_world(tmp_path, registry, cfg):
    # шаг 34: opportunity пресета героя из пака доходит до мира и срабатывает на границе сцены
    from campaign_kit import SAVED_AT, default_files, load, write_pack

    from ai_dm.game.starter import new_world_from_pack

    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [
        {"id": "preset_hook", "if": {"hero_at": "tavern"}, "then": "Арн берётся за дело",
         "once": True}
    ]
    pack = load(write_pack(tmp_path, files), registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="arn", seed=1, world_id="w1", saved_at=SAVED_AT
    )
    result = run_check(bundle)
    assert has_ref(result.fired, "preset_hook")
    assert bundle.heroes[0].opportunity[0].fired_count == 1
