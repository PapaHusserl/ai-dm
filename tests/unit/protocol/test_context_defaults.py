# AD1: начальные значения TurnContext / TurnResult и два хвоста обработчиков world.
from protocol_kit import make_ctx, req

from ai_dm.game.turn import TurnResult
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import parse_request


def test_context_base_registry_defaults_to_registry(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.base_registry is registry


def test_context_base_registry_can_be_given(registry, cfg):
    other = object()
    ctx = make_ctx(registry, cfg, base_registry=other)
    assert ctx.base_registry is other


def test_context_combat_options_are_kept(registry, cfg):
    ctx = make_ctx(registry, cfg, combat_options=[{"id": "a", "label": "A"}])
    assert ctx.combat_options == [{"id": "a", "label": "A"}]


def test_context_world_and_summarizer_defaults(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.own_attitude_spent == {}
    assert ctx.own_favor_spent == {}
    assert ctx.candidate_refs == []
    assert ctx.verdict_refs == []
    assert ctx.verdicts is None
    assert ctx.notice_ids == []
    assert ctx.summary_text is None
    assert ctx.summary_title == ""
    assert ctx.summary_max == 0
    assert ctx.chapter_text is None
    assert ctx.chapter_title_new == ""
    assert ctx.game_text is None
    assert ctx.chapter_summary_max == 0
    assert ctx.game_summary_max == 0


def test_turn_result_defaults():
    result = TurnResult("run-1")
    assert result.run_ids == ["run-1"]
    assert result.before is None
    assert result.hint is None
    assert result.hero_dead is False
    assert result.offscreen == []
    assert result.boundary_failed is False


def test_end_chapter_logs_closing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, req("end_chapter", title="Глава 1"))
    assert decision.log == ["Глава закрыта"]


def world_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="world")
    ctx.verdict_refs = ["a"]
    return ctx


def verdict(ref="a", holds=True):
    data = {"type": "world_verdict", "items": [{"ref": ref, "holds": holds, "reason": "потому"}]}
    return parse_request(data, "world")


def test_world_verdict_accepted_logs_count(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, verdict())
    assert isinstance(decision, Decision)
    assert decision.log == ["Вердиктов: 1"]
    assert ctx.verdicts == {"a": True}


def test_world_verdict_second_call_is_rejected(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, verdict())
    second = apply(ctx, verdict())
    assert isinstance(second, Invalid)
    assert second.code == "verdict_done"
    assert "вердикты уже даны" in second.message


def test_world_verdict_wrong_refs_are_rejected_with_lists(registry, cfg):
    ctx = world_ctx(registry, cfg)
    outcome = apply(ctx, verdict("b"))
    assert isinstance(outcome, Invalid)
    assert outcome.code == "invalid_verdict_refs"
    assert "лишние ref: ['b']" in outcome.message
    assert "пропущенные ref: ['a']" in outcome.message
    assert ctx.verdicts is None
