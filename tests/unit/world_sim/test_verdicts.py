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


# Ж2 (коммит 2): вердикт по событию (event:<id>) -- holds=true заканчивает событие

def event_candidate(bundle, ends_at_s=None):
    from ai_dm.state.world import GlobalEvent

    bundle.world.events.append(
        GlobalEvent(id="plague", type="чума", ends_at_s=ends_at_s, ends_when={"narrative": "x"})
    )
    return candidate("event:plague", "event", "plague", "plague")


def event_of(bundle):
    return next(e for e in bundle.world.events if e.id == "plague")


def test_find_owner_returns_event_by_id(registry, cfg):
    from ai_dm.world_sim.verdicts import find_owner

    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle)
    assert find_owner(bundle, cand) is event_of(bundle)


def test_find_owner_of_unknown_event_is_none(registry, cfg):
    from ai_dm.world_sim.verdicts import find_owner

    bundle = mini_bundle(registry, cfg)
    assert find_owner(bundle, candidate("event:ghost", "event", "ghost", "ghost")) is None


def test_find_owner_of_unknown_hero_is_none(registry, cfg):
    from ai_dm.world_sim.verdicts import find_owner

    bundle = mini_bundle(registry, cfg)
    assert find_owner(bundle, candidate("trigger:ghost:t", "hero", "ghost", "t")) is None


def test_find_owner_returns_hero_by_id(registry, cfg):
    from ai_dm.world_sim.verdicts import find_owner

    bundle = mini_bundle(registry, cfg)
    hero = bundle.heroes[0]
    assert find_owner(bundle, candidate("trigger:h:t", "hero", hero.id, "t")) is hero


def test_find_owner_event_id_is_not_confused_with_hero_or_npc(registry, cfg):
    from ai_dm.world_sim.verdicts import find_owner

    bundle = mini_bundle(registry, cfg)
    event_candidate(bundle)
    assert find_owner(bundle, candidate("event:aldric", "event", "aldric", "aldric")) is None


def test_confirmed_event_verdict_ends_event_now(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle)
    assert apply(bundle, [cand], {cand.ref: True}) == ["event:plague"]
    assert event_of(bundle).ends_at_s == bundle.world.clock.now_s


def test_confirmed_event_verdict_overrides_later_end(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle, ends_at_s=bundle.world.clock.now_s + 10**6)
    apply(bundle, [cand], {cand.ref: True})
    assert event_of(bundle).ends_at_s == bundle.world.clock.now_s


def test_denied_event_verdict_keeps_event_running(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle)
    assert apply(bundle, [cand], {cand.ref: False}) == []
    assert event_of(bundle).ends_at_s is None


def test_missing_event_verdict_keeps_event_running(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle)
    assert apply(bundle, [cand], {}) == []
    assert event_of(bundle).ends_at_s is None


def test_event_verdict_fires_no_trigger_and_writes_no_chronicle(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    cand = event_candidate(bundle)
    before = len(bundle.chronicle.entries)
    apply(bundle, [cand], {cand.ref: True})
    assert bundle.world.fired == []
    assert len(bundle.chronicle.entries) == before


def test_unknown_event_verdict_is_skipped_and_next_one_applies(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    ghost = candidate("event:ghost", "event", "ghost", "ghost")
    cand = event_candidate(bundle)
    assert apply(bundle, [ghost, cand], {ghost.ref: True, cand.ref: True}) == [cand.ref]


def test_confirmed_ordinary_verdict_does_not_touch_goals(registry, cfg):
    bundle = mini_bundle(registry, cfg)
    goal_candidate(bundle)
    good = candidate("trigger:brann:brann_trust", "npc", "brann", "brann_trust")
    apply(bundle, [good], {good.ref: True})
    assert bundle.world.npcs["aldric"].goals[0].status == "active"
