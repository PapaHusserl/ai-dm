# Ж2 коммит 2, вариант Б (BACKLOG 46): TurnContext.applied_refs -- then_ref запросов роли world, по
# которым что-то применилось. protocol.apply.note_applied зовётся из apply после каждого запроса:
#   accepted и clamped с непустым then_ref -- добавляют; Invalid, rejected, пустой/отсутствующий
#   then_ref -- нет. TurnFailed.applied_refs по умолчанию пуст (его ставит WorldSession.run).
from types import SimpleNamespace

import pytest
from protocol_kit import make_ctx, req

from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply, note_applied
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import parse_request


def decision(status, **fields):
    if status in ("clamped", "rejected"):
        fields.setdefault("signal_to_master", "сигнал")
    return Decision(status=status, **fields)


def world_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="world")
    ctx.candidate_refs = ["cand-1"]
    ctx.verdict_refs = []
    return ctx


def world_update(**fields):
    data = {"type": "npc_update", "npc_id": "aldric", "then_ref": "cand-1"}
    data.update(fields)
    return parse_request(data, "world")


def test_applied_refs_start_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert ctx.applied_refs == set()


def test_applied_refs_are_not_shared_between_contexts(registry, cfg):
    first, second = make_ctx(registry, cfg), make_ctx(registry, cfg)
    first.applied_refs.add("x")
    assert second.applied_refs == set()


@pytest.mark.parametrize("status", ["accepted", "clamped"])
def test_note_applied_adds_ref_of_accepted_and_clamped(registry, cfg, status):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(then_ref="cand-1"), decision(status))
    assert ctx.applied_refs == {"cand-1"}


def test_note_applied_ignores_rejected(registry, cfg):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(then_ref="cand-1"), decision("rejected"))
    assert ctx.applied_refs == set()


def test_note_applied_ignores_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(then_ref="cand-1"), Invalid(code="x", message="y"))
    assert ctx.applied_refs == set()


@pytest.mark.parametrize("then_ref", ["", None])
def test_note_applied_ignores_empty_then_ref(registry, cfg, then_ref):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(then_ref=then_ref), decision("accepted"))
    assert ctx.applied_refs == set()


def test_note_applied_ignores_request_without_then_ref_field(registry, cfg):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(), decision("accepted"))
    assert ctx.applied_refs == set()


def test_note_applied_keeps_several_refs(registry, cfg):
    ctx = make_ctx(registry, cfg)
    note_applied(ctx, SimpleNamespace(then_ref="a"), decision("accepted"))
    note_applied(ctx, SimpleNamespace(then_ref="b"), decision("accepted"))
    note_applied(ctx, SimpleNamespace(then_ref="a"), decision("accepted"))
    assert ctx.applied_refs == {"a", "b"}


# через apply

def test_apply_notes_accepted_world_request(registry, cfg):
    ctx = world_ctx(registry, cfg)
    assert apply(ctx, world_update(attitude_delta=1)).status == "accepted"
    assert ctx.applied_refs == {"cand-1"}


def test_apply_does_not_note_invalid_world_request(registry, cfg):
    ctx = world_ctx(registry, cfg)
    assert isinstance(apply(ctx, world_update(location_id="nowhere")), Invalid)
    assert ctx.applied_refs == set()


def test_apply_does_not_note_rejected_world_request(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, world_update(status="dead", cause="goal", evidence_ref="r1"))
    assert result.status == "rejected"
    assert ctx.applied_refs == set()


def test_apply_does_not_note_wrong_then_ref(registry, cfg):
    ctx = world_ctx(registry, cfg)
    assert isinstance(apply(ctx, world_update(attitude_delta=1, then_ref="other")), Invalid)
    assert ctx.applied_refs == set()


def test_apply_notes_world_request_after_invalid_one(registry, cfg):
    ctx = world_ctx(registry, cfg)
    apply(ctx, world_update(location_id="nowhere"))
    apply(ctx, world_update(location_id="forest"))
    assert ctx.applied_refs == {"cand-1"}


def test_apply_in_narrator_mode_notes_nothing(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert apply(ctx, req("npc_update", npc_id="aldric", attitude_delta=1)).status == "accepted"
    assert ctx.applied_refs == set()


def test_apply_notes_not_available_in_mode_as_nothing(registry, cfg):
    ctx = world_ctx(registry, cfg)
    result = apply(ctx, req("end_scene"))
    assert isinstance(result, Invalid)
    assert ctx.applied_refs == set()


# TurnFailed

def test_turn_failed_applied_refs_default_is_empty_frozenset():
    error = TurnFailed("refusal", "x")
    assert error.applied_refs == frozenset()
    assert isinstance(error.applied_refs, frozenset)


def test_turn_failed_keeps_other_fields_with_applied_refs():
    error = TurnFailed("invalid", "текст", report_tags=["t"], detail="d")
    assert (error.reason, str(error), error.report_tags, error.detail) == (
        "invalid", "текст", ["t"], "d"
    )
