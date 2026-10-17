# ТО (docs/plan-to.md §1 п.1): TurnFailed.detail несёт повод отказа (stop_detail ответа).
# Только refusal кладёт detail; network/fatal/invalid/rounds -- None.
import pytest
from master_kit import (
    flag_call,
    make_ctx,
    make_session,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply

BAD_CHECK = {
    "id": "bad", "name": "skill_check",
    "input": {"type": "skill_check", "skill": "nope", "category": "medium", "stakes": "normal"},
}


def fail_with(steps, tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted(steps), tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    with pytest.raises(TurnFailed) as info:
        session.run(ctx, "Иду.", apply, "explore")
    return info.value


def test_turn_failed_detail_defaults_to_none():
    assert TurnFailed("network", "сеть").detail is None


def test_turn_failed_keeps_detail():
    assert TurnFailed("refusal", "x", ["refusal"], detail="SPII").detail == "SPII"


def test_refusal_puts_stop_detail_into_failure(tmp_path, registry, cfg):
    steps = [{"stop": "refusal", "stop_detail": "PROHIBITED_CONTENT"}]
    error = fail_with(steps, tmp_path, registry, cfg)
    assert error.reason == "refusal"
    assert error.detail == "PROHIBITED_CONTENT"
    assert error.report_tags == ["refusal"]


def test_refusal_without_stop_detail_has_none_detail(tmp_path, registry, cfg):
    error = fail_with([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert error.detail is None


def test_refusal_after_tool_round_keeps_detail(tmp_path, registry, cfg):
    steps = [
        tools_step(flag_call("a", "c1")),
        {"stop": "refusal", "stop_detail": "BLOCKLIST", "text": "Не могу."},
    ]
    assert fail_with(steps, tmp_path, registry, cfg).detail == "BLOCKLIST"


@pytest.mark.parametrize(
    ("reason", "steps"),
    [
        ("network", [{"error": "transient", "message": "сеть"}] * 4),
        ("fatal", [{"error": "fatal", "message": "ключ"}]),
        ("invalid", [tools_step(BAD_CHECK)] * 3),
        ("rounds", [tools_step(flag_call(f"f{i}", f"c{i}")) for i in range(9)]),
    ],
)
def test_other_failures_have_no_detail(tmp_path, registry, cfg, reason, steps):
    error = fail_with(steps + [text_step()], tmp_path, registry, cfg)
    assert error.reason == reason
    assert error.detail is None
