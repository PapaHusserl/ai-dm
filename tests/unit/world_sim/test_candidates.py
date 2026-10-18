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
