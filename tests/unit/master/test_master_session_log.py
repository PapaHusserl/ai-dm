# Ожидаемый API: ai_dm.master.session.MasterSession -- журнал и учёт стоимости (контракт в
# master_kit.py): каждая попытка вызова -- запись Journal с run_id, attempt, ролью; стоимость
# ответа -- строка CostLedger с тем же call_id.
import json

import pytest
from master_kit import (
    NOW,
    app_cfg,
    flag_call,
    make_ctx,
    make_session,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.llm.cost import cost_nano
from ai_dm.llm.journal import request_fingerprint
from ai_dm.llm.types import Usage
from ai_dm.master.session import MasterSession, TurnFailed
from ai_dm.protocol.apply import apply

USAGE = {"input": 1500, "output": 40, "cache_read": 1200}
# ручной расчёт для claude-opus-5-5: (1500*4e6 + 40*20e6 + 1200*2e5) // 1000
EXPECTED_NANO = 7_040_000


def setup(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, ledger, sleeps = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg)
    return adapter, session, journal, ledger, ctx, sleeps


def ledger_lines(ledger):
    return [json.loads(x) for x in ledger.path.read_text(encoding="utf-8").splitlines()]


def test_every_call_is_written_to_journal(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), text_step()]
    adapter, session, journal, _, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    assert len(journal.read_records()) == len(adapter.requests) == 2


def test_journal_record_has_run_id_attempt_and_role(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([text_step()], tmp_path, registry, cfg, run_id="run-42")
    session.run(ctx, "Иду.", apply, "explore")
    record = journal.read_records()[0]
    assert record["run_id"] == "run-42"
    assert record["attempt"] == 1
    assert record["role"] == "narrator"
    assert record["world_id"] == "w1"
    assert record["ts"] == NOW.isoformat()


def test_journal_turn_seq_comes_from_session_state(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([text_step()], tmp_path, registry, cfg)
    ctx.bundle.session.turn_seq = 5
    session.run(ctx, "Иду.", apply, "explore")
    assert journal.read_records()[0]["turn_seq"] == 5


def test_journal_call_ids_are_unique(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step()]
    _, session, journal, _, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    ids = [r["call_id"] for r in journal.read_records()]
    assert len(set(ids)) == 3
    assert all(ids)


def test_journal_keeps_request_and_response(tmp_path, registry, cfg):
    adapter, session, journal, _, ctx, _ = setup(
        [tools_step(flag_call("a", "c1")), text_step("Конец.")], tmp_path, registry, cfg
    )
    session.run(ctx, "Иду.", apply, "explore")
    records = journal.read_records()
    for sent, record in zip(adapter.requests, records, strict=True):
        assert record["request"]["fingerprint"] == request_fingerprint(sent)
    assert records[0]["stop_reason"] == "tool_use"
    assert records[1]["stop_reason"] == "end_turn"
    assert records[1]["response"]["content"][0]["text"] == "Конец."


def test_journal_marks_attempts_of_network_retries(tmp_path, registry, cfg):
    transient = {"error": "transient", "message": "сеть недоступна"}
    steps = [transient, transient, transient, text_step()]
    _, session, journal, _, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    records = journal.read_records()
    assert [r["attempt"] for r in records] == [1, 2, 3, 4]
    assert [r["error"] is not None for r in records] == [True, True, True, False]
    assert records[0]["error"]["kind"] == "transient"
    assert len({r["run_id"] for r in records}) == 1


def test_attempt_restarts_for_next_call_of_the_turn(tmp_path, registry, cfg):
    transient = {"error": "transient", "message": "сеть"}
    steps = [transient, tools_step(flag_call("a", "c1")), text_step()]
    _, session, journal, _, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    assert [r["attempt"] for r in journal.read_records()] == [1, 2, 1]


def test_fatal_error_is_journaled_and_fails(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup(
        [{"error": "fatal", "message": "плохой ключ"}], tmp_path, registry, cfg
    )
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    record = journal.read_records()[0]
    assert record["error"]["kind"] == "fatal"
    assert record["response"] is None


def test_refusal_is_journaled_before_failure(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([{"stop": "refusal"}], tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert journal.read_records()[0]["stop_reason"] == "refusal"


def test_ledger_gets_cost_with_call_id_of_journal(tmp_path, registry, cfg):
    steps = [text_step("Ок.") | {"usage": USAGE}]
    _, session, journal, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    line = ledger_lines(ledger)[0]
    record = journal.read_records()[0]
    assert line["call_id"] == record["call_id"]
    assert line["role"] == "narrator"
    assert line["model"] == "claude-opus-5-5"
    assert line["day"] == "2026-10-03"
    assert line["aborted"] is False


def test_ledger_day_is_local_date(tmp_path, registry, cfg, monkeypatch):
    # P14: NOW = 12:00 UTC 3 октября; в Окленде (UTC+13) уже 4 октября
    import time

    monkeypatch.setenv("TZ", "Pacific/Auckland")
    time.tzset()
    try:
        steps = [text_step("Ок.") | {"usage": USAGE}]
        _, session, _, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
        session.run(ctx, "Иду.", apply, "explore")
        assert ledger_lines(ledger)[0]["day"] == "2026-10-04"
    finally:
        monkeypatch.undo()
        time.tzset()


def test_cost_matches_hand_calculation(tmp_path, registry, cfg):
    steps = [text_step("Ок.") | {"usage": USAGE}]
    _, session, journal, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    price = app_cfg().prices["claude-opus-5-5"]
    assert cost_nano(Usage(**USAGE), price) == EXPECTED_NANO
    assert ledger_lines(ledger)[0]["cost_nano"] == EXPECTED_NANO
    assert journal.read_records()[0]["cost_nano"] == EXPECTED_NANO
    assert ledger_lines(ledger)[0]["usage"]["cache_read"] == 1200


def test_cost_prices_5m_and_1h_cache_writes_separately(tmp_path, registry, cfg):
    usage = {"input": 100, "output": 10, "cache_write": 1000, "cache_write_1h": 2000}
    steps = [text_step("Ок.") | {"usage": usage}]
    _, session, journal, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    # 100*4000 + 10*20000 + 1000*5000 + 2000*8000
    expected = 400_000 + 200_000 + 5_000_000 + 16_000_000
    line = ledger_lines(ledger)[0]
    assert line["cost_nano"] == expected
    assert (line["usage"]["cache_write"], line["usage"]["cache_write_1h"]) == (1000, 2000)
    assert journal.read_records()[0]["cost_nano"] == expected


def test_ledger_has_line_for_each_response_but_not_for_errors(tmp_path, registry, cfg):
    transient = {"error": "transient", "message": "сеть"}
    steps = [
        transient, tools_step(flag_call("a", "c1"), usage=USAGE),
        text_step() | {"usage": USAGE},
    ]
    _, session, journal, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    lines = ledger_lines(ledger)
    assert len(lines) == 2
    with_response = [r["call_id"] for r in journal.read_records() if r["response"] is not None]
    assert [x["call_id"] for x in lines] == with_response


def test_ledger_session_total_sums_calls(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1"), usage=USAGE), text_step() | {"usage": USAGE}]
    _, session, _, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    report = ledger.report(NOW.date())
    assert report.session.total_nano == 2 * EXPECTED_NANO
    assert report.session.by_role == {"narrator": 2 * EXPECTED_NANO}


def test_refused_turn_still_costs_money(tmp_path, registry, cfg):
    steps = [{"stop": "refusal", "usage": USAGE}]
    _, session, _, ledger, ctx, _ = setup(steps, tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert ledger_lines(ledger)[0]["cost_nano"] == EXPECTED_NANO


def test_session_works_without_journal_and_ledger(tmp_path, registry, cfg):
    adapter = scripted([text_step("Ок.")])
    session = MasterSession(adapter, app_cfg(), sleeper=lambda s: None)
    result = session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert result.texts == ["Ок."]


# D3: run_id и счётчик call_id

def test_two_runs_on_one_session_have_different_call_ids(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([text_step(), text_step()], tmp_path, registry, cfg)
    session.run(ctx, "Раз.", apply, "explore")
    session.run(ctx, "Два.", apply, "explore")
    ids = [r["call_id"] for r in journal.read_records()]
    assert len(ids) == 2
    assert len(set(ids)) == 2


def test_explicit_run_id_goes_to_journal_and_call_id(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([text_step()], tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore", run_id="turn-7")
    record = journal.read_records()[0]
    assert record["run_id"] == "turn-7"
    assert record["call_id"].startswith("turn-7-")


def test_run_id_defaults_to_constructor_value(tmp_path, registry, cfg):
    _, session, journal, _, ctx, _ = setup([text_step()], tmp_path, registry, cfg, run_id="run-5")
    session.run(ctx, "Иду.", apply, "explore")
    assert journal.read_records()[0]["run_id"] == "run-5"


def test_runs_with_one_explicit_run_id_have_unique_call_ids(tmp_path, registry, cfg):
    steps = [text_step(), text_step(), text_step()]
    _, session, journal, _, ctx, _ = setup(steps, tmp_path, registry, cfg)
    for mode_text in ("classify", "npc_choice", "narrate"):
        session.run(ctx, mode_text, apply, "explore", run_id="turn-1")
    records = journal.read_records()
    assert {r["run_id"] for r in records} == {"turn-1"}
    assert len({r["call_id"] for r in records}) == 3


def test_ledger_call_id_matches_journal_with_explicit_run_id(tmp_path, registry, cfg):
    _, session, journal, ledger, ctx, _ = setup(
        [{"text": "Ок.", "usage": USAGE}], tmp_path, registry, cfg
    )
    session.run(ctx, "Иду.", apply, "explore", run_id="turn-9")
    assert ledger_lines(ledger)[0]["call_id"] == journal.read_records()[0]["call_id"]


# P3: meta.context и тег context_overflow в записи журнала

class PlanBuilder:
    # настоящий PromptBuilder, но last_plan подменён заданным планом
    def __init__(self, plan, role="narrator"):
        from ai_dm.master.prompt import PromptBuilder

        self.inner = PromptBuilder(app_cfg(), role=role)
        self.plan = plan
        self.last_plan = None

    def build(self, ctx, user_input, mode, *, world_text=""):
        request = self.inner.build(ctx, user_input, mode, world_text=world_text)
        self.last_plan = self.plan
        return request


def make_plan(overflow=False, dropped=(("turns", "1"),)):
    from ai_dm.master.context import ContextPlan

    return ContextPlan(
        budget=800_000 if overflow else 30_000, cap=30_000, estimate=12_345, turns=[],
        scene_summaries=[], npc_ids=[], location_ids=[], dropped=list(dropped),
        raised=overflow, overflow=overflow,
    )


def run_with_plan(steps, tmp_path, registry, cfg, plan, role="narrator"):
    adapter = scripted(steps)
    builder = PlanBuilder(plan, role)
    session, journal, _, _ = make_session(adapter, tmp_path, builder=builder, role=role)
    result = session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    return result, journal.read_records()


def test_narrator_record_has_meta_context_of_plan(tmp_path, registry, cfg):
    plan = make_plan()
    _, records = run_with_plan([text_step()], tmp_path, registry, cfg, plan)
    context = records[0]["meta"]["context"]
    expected = plan.meta()
    assert {k: v for k, v in context.items() if k != "api_tokens"} == expected


def test_world_record_has_empty_meta_and_no_tag(tmp_path, registry, cfg):
    result, records = run_with_plan(
        [text_step()], tmp_path, registry, cfg, make_plan(overflow=True), role="world"
    )
    assert records[0]["role"] == "world"
    assert records[0]["meta"] == {}
    assert records[0]["report_tags"] == []
    assert result.report_tags == []


def test_builder_without_plan_gives_empty_meta(tmp_path, registry, cfg):
    _, records = run_with_plan([text_step()], tmp_path, registry, cfg, None)
    assert records[0]["meta"] == {}
    assert records[0]["report_tags"] == []


def test_api_tokens_is_sum_of_all_four_usage_fields(tmp_path, registry, cfg):
    usage = {
        "input": 1000, "output": 77, "cache_read": 200, "cache_write": 30, "cache_write_1h": 4,
    }
    steps = [text_step() | {"usage": usage}]
    _, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan())
    assert records[0]["meta"]["context"]["api_tokens"] == 1234


def test_api_tokens_ignores_output(tmp_path, registry, cfg):
    steps = [text_step() | {"usage": {"input": 5, "output": 1000}}]
    _, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan())
    assert records[0]["meta"]["context"]["api_tokens"] == 5


def test_failed_attempt_has_meta_without_api_tokens(tmp_path, registry, cfg):
    steps = [{"error": "transient", "message": "сеть"}, text_step()]
    _, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan())
    assert "api_tokens" not in records[0]["meta"]["context"]
    assert "api_tokens" in records[1]["meta"]["context"]


def test_overflow_tag_is_in_record_and_once_in_result(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step()]
    result, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan(overflow=True))
    assert result.report_tags.count("context_overflow") == 1
    assert records[0]["meta"]["context"]["overflow"] is True


def test_overflow_tag_is_on_every_narrator_record(tmp_path, registry, cfg):
    steps = [
        {"error": "transient", "message": "сеть"},
        tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step(),
    ]
    _, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan(overflow=True))
    assert len(records) == 4
    assert [r["report_tags"] for r in records] == [["context_overflow"]] * 4


def test_no_overflow_means_no_tag(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), text_step()]
    result, records = run_with_plan(steps, tmp_path, registry, cfg, make_plan())
    assert "context_overflow" not in result.report_tags
    assert [r["report_tags"] for r in records] == [[], []]
    assert records[0]["meta"]["context"]["overflow"] is False
