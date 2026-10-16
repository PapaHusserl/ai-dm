# ТО (docs/TO-PLAN.md §1 п.2, Q2б): HARD_REFUSALS и hard_refusal(failure); жёсткий отказ
# (PROHIBITED_CONTENT, BLOCKLIST, SPII) -- без SOFTEN-повтора: 1 вызов, теги ["refusal"], меню,
# бандл откатан. SAFETY/RECITATION/отказ без detail -- один повтор с припиской, как раньше (Р2).
import pytest
from game_kit import (
    core_dump,
    flag_call,
    make_rig,
    run_records,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.game.turn import ERROR_MENU, HARD_REFUSALS, REFUSAL_HINT, SOFTEN_NOTE, hard_refusal
from ai_dm.llm.types import Text
from ai_dm.master.session import TurnFailed

HARD = ["PROHIBITED_CONTENT", "BLOCKLIST", "SPII"]
SOFT = ["SAFETY", "RECITATION"]


def refusal(detail):
    return {"stop": "refusal", "stop_detail": detail}


def notes_of(request):
    return [b.text for b in request.messages[0].content[1:] if isinstance(b, Text)]


# hard_refusal

def test_hard_refusals_constant_lists_exactly_three_filters():
    assert tuple(HARD_REFUSALS) == ("PROHIBITED_CONTENT", "BLOCKLIST", "SPII")


@pytest.mark.parametrize("detail", HARD)
def test_hard_refusal_true_for_each_constant(detail):
    assert hard_refusal(TurnFailed("refusal", "x", ["refusal"], detail=detail)) is True


@pytest.mark.parametrize("detail", [*SOFT, None, "OTHER", ""])
def test_hard_refusal_false_for_soft_or_unknown_detail(detail):
    assert hard_refusal(TurnFailed("refusal", "x", ["refusal"], detail=detail)) is False


@pytest.mark.parametrize("reason", ["network", "fatal", "invalid", "rounds", "short"])
def test_hard_refusal_false_for_other_reason_even_with_hard_detail(reason):
    assert hard_refusal(TurnFailed(reason, "x", detail="PROHIBITED_CONTENT")) is False


# play_turn: жёсткий отказ

def hard_turn(registry, cfg, tmp_path, detail="PROHIBITED_CONTENT", steps=None):
    adapter = scripted((steps or [refusal(detail)]) + [text_step("не должен быть вызван")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    before = rig.runner.bundle.model_dump_json()
    return rig, adapter, before, rig.runner.play("Иду")


@pytest.mark.parametrize("detail", HARD)
def test_hard_refusal_makes_one_request(registry, cfg, tmp_path, detail):
    _, adapter, _, _ = hard_turn(registry, cfg, tmp_path, detail)
    assert len(adapter.requests) == 1


@pytest.mark.parametrize("detail", HARD)
def test_hard_refusal_fails_with_refusal_and_detail(registry, cfg, tmp_path, detail):
    _, _, _, result = hard_turn(registry, cfg, tmp_path, detail)
    assert result.committed is False
    assert result.failure.reason == "refusal"
    assert result.failure.detail == detail


def test_hard_refusal_has_only_refusal_tag(registry, cfg, tmp_path):
    _, _, _, result = hard_turn(registry, cfg, tmp_path)
    assert result.report_tags == ["refusal"]


def test_hard_refusal_gives_menu_and_hint(registry, cfg, tmp_path):
    _, _, _, result = hard_turn(registry, cfg, tmp_path)
    assert result.menu == ERROR_MENU
    assert result.hint == REFUSAL_HINT


def test_hard_refusal_leaves_bundle_byte_identical(registry, cfg, tmp_path):
    rig, _, before, _ = hard_turn(registry, cfg, tmp_path)
    assert rig.runner.bundle.model_dump_json() == before


def test_hard_refusal_marks_journal_aborted_with_one_call(registry, cfg, tmp_path):
    rig, _, _, result = hard_turn(registry, cfg, tmp_path)
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 1
    assert records[0]["turn_status"] == "aborted"


def test_hard_refusal_leaves_no_note_on_runner(registry, cfg, tmp_path):
    rig, _, _, _ = hard_turn(registry, cfg, tmp_path)
    assert rig.runner.note is None


def test_hard_refusal_on_second_tool_round_is_not_retried(registry, cfg, tmp_path):
    steps = [
        tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")),
        refusal("PROHIBITED_CONTENT"),
    ]
    rig, adapter, before, result = hard_turn(registry, cfg, tmp_path, steps=steps)
    assert len(adapter.requests) == 3
    assert result.report_tags == ["refusal"]
    assert rig.runner.bundle.model_dump_json() == before
    assert all(notes_of(r) == [] for r in adapter.requests)


def test_retry_after_hard_refusal_is_a_fresh_turn(registry, cfg, tmp_path):
    adapter = scripted([refusal("PROHIBITED_CONTENT"), text_step("Дошли.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("Иду")
    result = rig.runner.retry()
    assert result.committed is True
    assert notes_of(adapter.requests[1]) == []
    assert core_dump(rig.runner.bundle)


# play_turn: мягкий отказ -- как раньше

@pytest.mark.parametrize("detail", [*SOFT, None])
def test_soft_refusal_still_retries_once_with_note(registry, cfg, tmp_path, detail):
    first = {"stop": "refusal"} if detail is None else refusal(detail)
    adapter = scripted([first, text_step("Рассказ.")])
    result = make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert result.committed is True
    assert result.report_tags == ["refusal_retry"]
    assert len(adapter.requests) == 2
    assert notes_of(adapter.requests[1]) == [SOFTEN_NOTE]


@pytest.mark.parametrize("detail", [*SOFT, None])
def test_soft_double_refusal_gives_both_tags_and_two_requests(registry, cfg, tmp_path, detail):
    step = {"stop": "refusal"} if detail is None else refusal(detail)
    adapter = scripted([step, step, text_step("лишний")])
    result = make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert result.report_tags == ["refusal_retry", "refusal"]
    assert len(adapter.requests) == 2


def test_soft_retry_that_ends_in_hard_refusal_fails_without_third_call(registry, cfg, tmp_path):
    adapter = scripted([refusal("SAFETY"), refusal("PROHIBITED_CONTENT"), text_step("лишний")])
    result = make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert result.committed is False
    assert len(adapter.requests) == 2
