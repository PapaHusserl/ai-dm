# Ожидаемый API: ai_dm.world_sim.triggers.check -- кандидаты для роли world (A4), контракт в
# world_sim_kit.py. Нарративное условие: структурная часть выполнена -> verdict с residual.
from world_sim_kit import field, has_ref, mini_bundle, refs_of, run_check, trigger_of


def candidate_of(result, *parts):
    return next(c for c in result.candidates if all(p in field(c, "ref") for p in parts))


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
