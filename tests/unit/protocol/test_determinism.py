# Ожидаемый API: ai_dm.protocol.apply.apply, ai_dm.protocol.render.render_tool_result -- см.
# контракт в protocol_kit.py. Детерминизм (ARCHITECTURE A1): одинаковый сид + одинаковая
# последовательность запросов -> побайтно равные бандлы, логи, метки, события и состояние rng;
# другой сид -> другое состояние rng. Все броски идут только через ctx.rng.
from protocol_kit import combat_request, make_bundle, make_ctx, req

from ai_dm.core.rng import Rng
from ai_dm.protocol.apply import apply
from ai_dm.protocol.render import render_tool_result
from ai_dm.state.session import LastCombat


def sequence():
    return [
        req("skill_check", skill="persuasion", category="medium"),
        req("saving_throw", ability="dex", category="hard", stakes="critical"),
        req("damage", severity="dangerous", damage_type="fire"),
        req("gold", direction="gain", kind="loot_individual"),
        req("give_item", item_id="crowbar", qty=2),
        req("npc_update", npc_id="aldric", attitude_delta=15),
        req("rest", kind="short", hit_dice=1),
        req("advance_time", travel_to="forest", pace="slow"),
        req("award_xp", scale="major", reason="клад"),
        combat_request(),
    ]


def run(registry, cfg, seed):
    bundle = make_bundle(registry)
    bundle.world.rng = Rng(seed).state
    bundle.session.last_combat = LastCombat(defeated=["goblin_warrior"])
    ctx = make_ctx(registry, cfg, bundle=bundle)
    outputs = [render_tool_result(apply(ctx, r)) for r in sequence()]
    return ctx, outputs


def test_same_seed_gives_equal_bundles_and_logs(registry, cfg):
    first, out1 = run(registry, cfg, 5)
    second, out2 = run(registry, cfg, 5)
    assert first.bundle.model_dump_json() == second.bundle.model_dump_json()
    assert out1 == out2
    assert first.marks == second.marks
    assert [e.model_dump_json() for e in first.events] == [
        e.model_dump_json() for e in second.events
    ]
    assert first.rng.state == second.rng.state


def test_rolls_journal_is_equal_for_same_seed(registry, cfg):
    first, _ = run(registry, cfg, 5)
    second, _ = run(registry, cfg, 5)
    assert list(first.rolls) == list(second.rolls)
    assert [r.log.text for r in first.rolls.values()] == [r.log.text for r in second.rolls.values()]


def test_different_seed_gives_different_rng_state(registry, cfg):
    first, _ = run(registry, cfg, 5)
    second, _ = run(registry, cfg, 6)
    assert first.rng.state != second.rng.state


def test_sequence_really_uses_rng(registry, cfg):
    ctx, _ = run(registry, cfg, 5)
    assert ctx.rng.draws > 5


def test_replay_on_deep_copy_gives_same_result(registry, cfg):
    # ход идёт на копии бандла: результат не зависит от того, что исходник не тронут
    original = make_bundle(registry)
    before = original.model_dump_json()
    ctx = make_ctx(registry, cfg, bundle=original.model_copy(deep=True))
    for r in sequence():
        apply(ctx, r)
    assert original.model_dump_json() == before
    assert ctx.bundle.model_dump_json() != before
