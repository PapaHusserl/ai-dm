# Ожидаемый API: ai_dm.world_sim.triggers.check -- кандидаты для роли world (A4), контракт в
# world_sim_kit.py. Нарративное условие: структурная часть выполнена -> verdict с residual.
from world_sim_kit import field, has_ref, mini_bundle, refs_of, run_check, trigger_of


def candidate_of(result, *parts):
    return next(c for c in result.candidates if all(p in field(c, "ref") for p in parts))


def goal_bundle(registry, cfg):
    from ai_dm.rules.goals import add_goal

    bundle = mini_bundle(registry, cfg)
    add_goal(bundle.world.npcs["aldric"], "revenge", bundle.heroes[0].id, "мстит", 0)
    return bundle


def test_verdict_candidates_include_goal_trigger_by_default(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    refs = [c.ref for c in verdict_candidates(goal_bundle(registry, cfg))]
    assert has_ref(refs, "aldric", "goal:revenge:")


def test_verdict_candidates_skip_goals_hides_only_goal_triggers(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = goal_bundle(registry, cfg)
    bundle.world.flags["met_brann"] = True
    refs = [c.ref for c in verdict_candidates(bundle, skip_goals=True)]
    assert not has_ref(refs, "goal:revenge:")
    assert has_ref(refs, "brann", "brann_trust")


def test_skipped_goal_trigger_before_ordinary_one_does_not_hide_it(registry, cfg):
    from ai_dm.rules.goals import add_goal
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = mini_bundle(registry, cfg)
    brann = bundle.world.npcs["brann"]
    add_goal(brann, "revenge", bundle.heroes[0].id, "мстит", 0)
    brann.opportunity.reverse()
    assert brann.opportunity[0].id.startswith("goal:")
    bundle.world.flags["met_brann"] = True
    refs = [c.ref for c in verdict_candidates(bundle, skip_goals=True)]
    assert has_ref(refs, "brann", "brann_trust")


def test_verdict_candidates_do_not_change_state(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = goal_bundle(registry, cfg)
    before = bundle.model_dump_json()
    verdict_candidates(bundle, skip_goals=False)
    assert bundle.model_dump_json() == before


def test_mixed_condition_without_flag_is_not_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    result = run_check(bundle)
    assert not has_ref(refs_of(result), "brann_trust")


def test_mixed_condition_with_flag_is_verdict_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["met_brann"] = True
    result = run_check(bundle)
    assert has_ref(refs_of(result, "verdict"), "brann", "brann_trust")


def test_mixed_condition_candidate_has_narrative_residual(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["met_brann"] = True
    candidate = candidate_of(run_check(bundle), "brann_trust")
    residual = field(candidate, "residual")
    assert residual is not None
    assert "Бранн доверяет герою" in str(residual)


def test_mixed_condition_does_not_fire_without_verdict(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["met_brann"] = True
    result = run_check(bundle)
    assert result.fired == []
    assert trigger_of(bundle, "brann", "brann_trust").fired_count == 0


def test_mixed_condition_dead_npc_is_not_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["met_brann"] = True
    bundle.world.npcs["brann"].status = "dead"
    assert not has_ref(refs_of(run_check(bundle)), "brann_trust")


def test_secret_of_npc_in_scene_with_narrative_condition_is_verdict(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    result = run_check(bundle)
    assert has_ref(refs_of(result, "verdict"), "oath")


def test_secret_of_npc_elsewhere_is_not_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.session.current_scene.location_id = "cellar"
    assert not has_ref(refs_of(run_check(bundle)), "oath")


def test_secret_with_narrative_ok_is_not_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["aldric"].secrets[1].narrative_ok = True
    assert not has_ref(refs_of(run_check(bundle)), "oath")


def test_revealed_secret_is_not_candidate(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.npcs["aldric"].secrets[1].revealed = True
    assert not has_ref(refs_of(run_check(bundle)), "oath")


def test_structural_secret_is_not_candidate_and_not_revealed_by_engine(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.world.flags["found_letter"] = True
    result = run_check(bundle)
    assert not has_ref(refs_of(result), "sister")
    assert bundle.world.npcs["aldric"].secrets[0].revealed is False


def test_no_candidates_means_empty_list(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    bundle.session.current_scene.location_id = "cellar"
    assert run_check(bundle).candidates == []


# Ж2 (коммит 2): события с ends_when -- verdict-кандидаты event:<id>

def event_bundle(registry, cfg, ends_when, **fields):
    from ai_dm.state.world import GlobalEvent

    bundle = mini_bundle(registry, cfg)
    bundle.world.events.append(
        GlobalEvent(id="plague", type="чума", ends_when=ends_when, **fields)
    )
    return bundle


def event_cands(bundle):
    from ai_dm.world_sim.candidates import event_candidates

    return event_candidates(bundle)


def test_event_ref_format():
    from ai_dm.world_sim.candidates import event_ref

    assert event_ref("plague") == "event:plague"


def test_event_with_narrative_ends_when_is_verdict_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "чума отступила"})
    [cand] = event_cands(bundle)
    assert cand.ref == "event:plague"
    assert cand.kind == "verdict"
    assert (cand.owner_kind, cand.owner_id, cand.item_id) == ("event", "plague", "plague")
    assert cand.owner_name == "чума"
    assert cand.condition_text == "чума отступила"
    assert cand.then == "событие заканчивается"
    assert cand.residual is not None
    assert "чума отступила" in str(cand.residual)


def test_event_without_ends_when_is_not_candidate(registry, cfg):
    assert event_cands(event_bundle(registry, cfg, None)) == []


def test_event_with_unmet_structural_part_is_not_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"all": [{"flag": "calm"}, {"narrative": "чума ушла"}]})
    assert event_cands(bundle) == []


def test_event_with_met_structural_part_is_candidate_with_residual(registry, cfg):
    bundle = event_bundle(registry, cfg, {"all": [{"flag": "calm"}, {"narrative": "чума ушла"}]})
    bundle.world.flags["calm"] = True
    [cand] = event_cands(bundle)
    assert cand.condition_text == "чума ушла"
    assert "calm" not in str(cand.residual)


def test_event_with_purely_structural_ends_when_is_not_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"flag": "calm"})
    bundle.world.flags["calm"] = True
    assert event_cands(bundle) == []


def test_event_ends_when_sees_hero_conditions(registry, cfg):
    cond = {"all": [{"hero_at": "tavern"}, {"narrative": "чума ушла"}]}
    bundle = event_bundle(registry, cfg, cond)
    bundle.heroes[0].location_id = "tavern"
    assert len(event_cands(bundle)) == 1
    bundle.heroes[0].location_id = "cellar"
    assert event_cands(bundle) == []


def test_event_candidate_texts_are_joined(registry, cfg):
    cond = {"all": [{"narrative": "первое"}, {"narrative": "второе"}]}
    [cand] = event_cands(event_bundle(registry, cfg, cond))
    assert cand.condition_text == "первое; второе"


def test_ended_event_is_not_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "x"}, ends_at_s=1)
    assert bundle.world.clock.now_s > 1
    assert event_cands(bundle) == []


def test_not_started_event_is_not_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "x"})
    bundle.world.events[-1].started_s = bundle.world.clock.now_s + 1
    assert event_cands(bundle) == []


def test_event_that_ends_in_future_is_candidate(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "x"})
    bundle.world.events[-1].ends_at_s = bundle.world.clock.now_s + 1
    assert len(event_cands(bundle)) == 1


def test_event_candidates_keep_world_events_order(registry, cfg):
    from ai_dm.state.world import GlobalEvent

    bundle = event_bundle(registry, cfg, {"narrative": "x"})
    bundle.world.events.insert(0, GlobalEvent(id="war", type="война", ends_when={"narrative": "y"}))
    assert [c.owner_id for c in event_cands(bundle)] == ["war", "plague"]


def test_non_candidate_events_do_not_hide_later_ones(registry, cfg):
    from ai_dm.state.world import GlobalEvent

    bundle = event_bundle(registry, cfg, {"narrative": "чума отступила"})
    bundle.world.events[:0] = [
        GlobalEvent(id="a_no_end", type="война"),
        GlobalEvent(id="b_ended", type="голод", ends_when={"narrative": "x"}, ends_at_s=1),
        GlobalEvent(id="c_false", type="мор", ends_when={"flag": "never"}),
        GlobalEvent(id="d_true", type="гроза", ends_when={"flag": "always"}),
    ]
    bundle.world.flags["always"] = True
    assert [c.owner_id for c in event_cands(bundle)] == ["plague"]


def test_event_candidates_do_not_change_state(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "x"})
    before = bundle.model_dump_json()
    event_cands(bundle)
    assert bundle.model_dump_json() == before


def test_verdict_candidates_include_event_candidate(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = event_bundle(registry, cfg, {"narrative": "чума отступила"})
    assert "event:plague" in [c.ref for c in verdict_candidates(bundle)]


def test_event_candidate_goes_after_trigger_verdicts_and_before_secrets(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = event_bundle(registry, cfg, {"narrative": "чума отступила"})
    bundle.world.flags["met_brann"] = True
    refs = [c.ref for c in verdict_candidates(bundle)]
    brann = next(i for i, r in enumerate(refs) if "brann_trust" in r)
    oath = next(i for i, r in enumerate(refs) if "oath" in r)
    assert brann < refs.index("event:plague") < oath


def test_event_candidate_survives_skip_goals(registry, cfg):
    from ai_dm.world_sim.candidates import verdict_candidates

    bundle = event_bundle(registry, cfg, {"narrative": "x"})
    assert "event:plague" in [c.ref for c in verdict_candidates(bundle, skip_goals=True)]


def test_check_hands_event_verdict_to_world(registry, cfg):
    bundle = event_bundle(registry, cfg, {"narrative": "чума отступила"})
    assert "event:plague" in refs_of(run_check(bundle), "verdict")


def test_event_owner_ranks_last():
    from ai_dm.world_sim.candidates import OWNER_RANK

    assert OWNER_RANK["event"] > max(v for k, v in OWNER_RANK.items() if k != "event")
