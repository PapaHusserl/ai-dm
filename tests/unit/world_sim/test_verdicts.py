# Ожидаемый API: ai_dm.world_sim.verdicts.apply_verdicts(bundle, candidates, verdicts) -> list[ref].
# Кандидат без владельца или без триггера/секрета не роняет применение вердиктов (ревью П4, D6).
from world_sim_kit import mini_bundle, trigger_of


def candidate(ref, owner_kind, owner_id, item_id):
    from ai_dm.world_sim.candidates import Candidate

    return Candidate(
        ref=ref, kind="verdict", owner_kind=owner_kind, owner_id=owner_id, owner_name="x",
        item_id=item_id,
    )


def apply(bundle, candidates, verdicts):
    from ai_dm.world_sim.verdicts import apply_verdicts

    return apply_verdicts(bundle, candidates, verdicts)


def test_candidate_without_owner_is_skipped(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = candidate("trigger:ghost:t", "npc", "ghost", "t")
    assert apply(bundle, [cand], {cand.ref: True}) == []


def test_trigger_candidate_without_trigger_is_skipped(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = candidate("trigger:brann:nope", "npc", "brann", "nope")
    assert apply(bundle, [cand], {cand.ref: True}) == []
    assert bundle.world.fired == []


def test_secret_candidate_without_secret_is_skipped(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = candidate("secret:aldric:nope", "npc", "aldric", "nope")
    assert apply(bundle, [cand], {cand.ref: True}) == []


def test_valid_candidate_after_broken_one_is_still_applied(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    broken = candidate("trigger:ghost:t", "npc", "ghost", "t")
    good = candidate("trigger:brann:brann_trust", "npc", "brann", "brann_trust")
    result = apply(bundle, [broken, good], {broken.ref: True, good.ref: True})
    assert result == [good.ref]
    assert trigger_of(bundle, "brann", "brann_trust").fired_count == 1


# Ж2: подтверждённый вердикт по триггеру-спутнику закрывает цель как done

def goal_candidate(bundle):
    from ai_dm.rules.goals import add_goal

    hero_id = bundle.heroes[0].id
    add_goal(bundle.world.npcs["aldric"], "revenge", hero_id, "мстит", 0)
    tid = f"goal:revenge:{hero_id}"
    return candidate(f"trigger:aldric:{tid}", "npc", "aldric", tid)


def test_confirmed_goal_verdict_closes_goal_as_done(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = goal_candidate(bundle)
    assert apply(bundle, [cand], {cand.ref: True}) == [cand.ref]
    assert bundle.world.npcs["aldric"].goals[0].status == "done"
    assert bundle.world.npcs["aldric"].opportunity[-1].fired_count == 1


def test_denied_goal_verdict_keeps_goal_active(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = goal_candidate(bundle)
    assert apply(bundle, [cand], {cand.ref: False}) == []
    assert bundle.world.npcs["aldric"].goals[0].status == "active"


def test_confirmed_ordinary_verdict_does_not_touch_goals(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    goal_candidate(bundle)
    good = candidate("trigger:brann:brann_trust", "npc", "brann", "brann_trust")
    apply(bundle, [good], {good.ref: True})
    assert bundle.world.npcs["aldric"].goals[0].status == "active"
