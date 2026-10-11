# Ожидаемый API: ai_dm.protocol.context.TurnContext -- см. контракт в protocol_kit.py.
#   TurnContext(bundle, registry, cfg, rng=None, *, mode="explore", npc_options=None)
#   .bundle (is тот же объект, копии нет), .registry, .cfg, .rng, .hero, .scene, .rolls, .add_roll,
#   .events, .marks, .attitude_spent, .chapter_ended, .mode, .npc_options
from protocol_kit import ScriptedRng, make_bundle, make_ctx, req

from ai_dm.core.rng import Rng
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.rules.checks import skill_check


def test_context_keeps_given_bundle_without_copy(registry, cfg):
    bundle = make_bundle(registry)
    ctx = TurnContext(bundle, registry, cfg)
    assert ctx.bundle is bundle
    assert ctx.registry is registry
    assert ctx.cfg is cfg


def test_context_rng_is_built_from_world_state(registry, cfg):
    bundle = make_bundle(registry)
    ctx = TurnContext(bundle, registry, cfg)
    assert ctx.rng.state == Rng.from_state(bundle.world.rng).state


def test_context_uses_given_rng(registry, cfg):
    rng = ScriptedRng(d20=[10])
    assert make_ctx(registry, cfg, rng).rng is rng


def test_context_does_not_sync_world_rng(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = ctx.bundle.world.rng.model_copy(deep=True)
    ctx.rng.d(20)
    assert ctx.bundle.world.rng == before


def test_context_hero_is_current_hero(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.hero is ctx.bundle.heroes[0]
    assert ctx.hero.id == "hero"


def test_context_scene_is_current_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.scene is ctx.bundle.session.current_scene


def test_context_scene_is_none_without_scene(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=make_bundle(registry, with_scene=False))
    assert ctx.scene is None


def test_context_starts_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.rolls == {}
    assert ctx.events == []
    assert ctx.marks == []
    assert ctx.attitude_spent == {}


def test_context_default_mode_is_explore(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.mode == "explore"
    assert not ctx.npc_options


def test_context_mode_and_npc_options_are_kept(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="npc_choice", npc_options=["a", "end_turn"])
    assert ctx.mode == "npc_choice"
    assert list(ctx.npc_options) == ["a", "end_turn"]


def test_add_roll_gives_sequential_refs(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10, 11]))
    first = skill_check(ctx.hero, registry, ctx.rng, "athletics", "easy")
    second = skill_check(ctx.hero, registry, ctx.rng, "athletics", "easy")
    assert ctx.add_roll(first) == "r1"
    assert ctx.add_roll(second) == "r2"
    assert list(ctx.rolls) == ["r1", "r2"]
    assert ctx.rolls["r1"] is first


def test_roll_journal_is_filled_by_checks_in_order(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[10, 12]))
    d1 = apply(ctx, req("skill_check", skill="athletics", category="easy"))
    d2 = apply(ctx, req("saving_throw", ability="dex", category="hard"))
    assert d1.result["roll_ref"] == "r1"
    assert d2.result["roll_ref"] == "r2"
    assert list(ctx.rolls) == ["r1", "r2"]
    assert ctx.rolls["r1"].kind == "check"
    assert ctx.rolls["r2"].kind == "save"


def test_two_contexts_have_independent_journals(registry, cfg):
    a = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    b = make_ctx(registry, cfg, ScriptedRng(d20=[10]))
    apply(a, req("skill_check", skill="athletics", category="easy"))
    assert b.rolls == {}


def test_attitude_accumulator_lives_in_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=5))
    assert ctx.attitude_spent == {"aldric": 5}
    assert ctx.bundle.session.current_scene.attitude_spent == {"aldric": 5}


def test_marks_collect_report_tags_in_order(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=999))
    apply(ctx, req("unsupported_action", description="полёт на луну"))
    assert ctx.marks == ["limit-exceeded", "missing-mechanic"]


def test_events_are_collected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=1))
    assert [e.type for e in ctx.events] == ["item_gained"]
