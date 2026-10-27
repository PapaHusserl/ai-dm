# Ожидаемый API: ai_dm.llm.replay (ReplayAdapter, ReplayDivergence) -- контракт в llm_kit.py.
# Воспроизведение (ТЗ 11): ответы из журнала вместо живых вызовов по порядку записей; запрос
# сверяется по отпечатку; ход, который был откачен (aborted), в журнале остаётся и воспроизводится.
import pytest
from llm_kit import app_cfg, make_request, make_response

from ai_dm.config.app import JournalConfig
from ai_dm.llm.errors import LlmError, LlmFatal, LlmTransient
from ai_dm.llm.journal import Journal
from ai_dm.llm.replay import ReplayAdapter, ReplayDivergence
from ai_dm.llm.retry import call_with_retries
from ai_dm.llm.types import ChatResponse, Opaque, ToolCall, Usage


def make_journal(tmp_path):
    return Journal(tmp_path / "saves", "w1", JournalConfig(max_mb=50, segment_mb=5))


def log(journal, n, req, resp=None, *, turn_seq=1, attempt=1, error=None, run_id=None):
    # run_id по умолчанию -- свой на каждый ход: run-<turn_seq>
    journal.record_call(
        call_id=f"c{n}", run_id=run_id or f"run-{turn_seq}", ts="2026-10-03T12:00:00",
        turn_seq=turn_seq, attempt=attempt, role=req.role,
        provider="anthropic", model=req.model, request=req, response=resp, error=error,
    )


def group_runs(records):
    # записи журнала по run_id, в порядке первого появления
    runs = {}
    for record in records:
        runs.setdefault(record["run_id"], []).append(record)
    return runs


def test_replay_returns_recorded_responses_in_order(tmp_path):
    journal = make_journal(tmp_path)
    r1, r2 = make_request("раз"), make_request("два")
    a1, a2 = make_response("первый"), make_response("второй")
    log(journal, 1, r1, a1)
    log(journal, 2, r2, a2)
    adapter = ReplayAdapter(journal.read_records())
    assert [adapter.complete(r1), adapter.complete(r2)] == [a1, a2]


def test_replay_returns_response_with_openai_opaque_unchanged(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request("раз")
    items = [
        {"type": "reasoning", "id": "rs_1", "encrypted_content": "ZW5j", "summary": []},
        {"type": "function_call", "call_id": "call_1", "name": "skill_check", "arguments": "{}"},
    ]
    resp = ChatResponse(
        content=[ToolCall(id="call_1", name="skill_check", input={}),
                 Opaque(provider="openai", raw={"items": items})],
        stop_reason="tool_use", usage=Usage(input=1, cache_read=2, cache_write=3, output=4),
        request_id="req-o", model="gpt-6.1-sol",
    )
    log(journal, 1, req, resp)
    assert ReplayAdapter(journal.read_records()).complete(req) == resp


def test_replay_diverges_when_request_text_changed(tmp_path):
    journal = make_journal(tmp_path)
    log(journal, 1, make_request("раз"), make_response())
    adapter = ReplayAdapter(journal.read_records())
    with pytest.raises(ReplayDivergence):
        adapter.complete(make_request("изменённый ввод"))


def test_replay_diverges_when_system_changed(tmp_path):
    journal = make_journal(tmp_path)
    log(journal, 1, make_request("раз"), make_response())
    other = make_request("раз", system=[])
    with pytest.raises(ReplayDivergence):
        ReplayAdapter(journal.read_records()).complete(other)


def test_replay_diverges_when_max_tokens_changed(tmp_path):
    journal = make_journal(tmp_path)
    log(journal, 1, make_request("раз"), make_response())
    other = make_request("раз", max_tokens=100)
    with pytest.raises(ReplayDivergence):
        ReplayAdapter(journal.read_records()).complete(other)


def test_replay_diverges_on_extra_call(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request("раз")
    log(journal, 1, req, make_response())
    adapter = ReplayAdapter(journal.read_records())
    adapter.complete(req)
    with pytest.raises(ReplayDivergence):
        adapter.complete(req)


def test_replay_of_empty_journal_diverges_on_first_call():
    with pytest.raises(ReplayDivergence):
        ReplayAdapter([]).complete(make_request())


def test_divergence_is_not_an_llm_error():
    # иначе повторы приняли бы расхождение за сбой сети
    assert not issubclass(ReplayDivergence, LlmError)


def test_replay_reraises_recorded_transient_error(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request()
    log(journal, 1, req, error=LlmTransient("сеть", retry_after=4))
    with pytest.raises(LlmTransient) as info:
        ReplayAdapter(journal.read_records()).complete(req)
    assert (str(info.value), info.value.retry_after) == ("сеть", 4)


def test_replay_reraises_recorded_fatal_error(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request()
    log(journal, 1, req, error=LlmFatal("400"))
    with pytest.raises(LlmFatal):
        ReplayAdapter(journal.read_records()).complete(req)


def test_replay_of_failed_attempt_then_success_through_retries(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request()
    ok = make_response("с повтора")
    log(journal, 1, req, error=LlmTransient("сеть"), attempt=1)
    log(journal, 2, req, ok, attempt=2)
    sleeps = []
    resp = call_with_retries(
        ReplayAdapter(journal.read_records()), req, app_cfg().retry, sleeps.append
    )
    assert (resp, sleeps) == (ok, [1])


def test_replay_serves_aborted_attempts_in_record_order(tmp_path):
    # ход 3 откатили (два вызова), «повторить» дал третий: воспроизводятся все три по порядку
    journal = make_journal(tmp_path)
    r1, r2, r3 = make_request("а"), make_request("б"), make_request("в")
    a1, a2, a3 = make_response("1"), make_response("2"), make_response("3")
    log(journal, 1, r1, a1, turn_seq=3, run_id="run-3a")
    log(journal, 2, r2, a2, turn_seq=3, run_id="run-3a")
    journal.mark_turn("run-3a", "aborted")
    log(journal, 3, r3, a3, turn_seq=3, run_id="run-3b")
    journal.mark_turn("run-3b", "committed")
    adapter = ReplayAdapter(journal.read_records())
    assert [adapter.complete(r1), adapter.complete(r2), adapter.complete(r3)] == [a1, a2, a3]


def test_replay_of_retried_turn_diverges_if_order_swapped(tmp_path):
    journal = make_journal(tmp_path)
    r1, r2 = make_request("а"), make_request("б")
    log(journal, 1, r1, make_response("1"), turn_seq=3, run_id="run-3a")
    journal.mark_turn("run-3a", "aborted")
    log(journal, 2, r2, make_response("2"), turn_seq=3, run_id="run-3b")
    adapter = ReplayAdapter(journal.read_records())
    with pytest.raises(ReplayDivergence):
        adapter.complete(r2)


def test_replay_info_names_replay_provider():
    assert ReplayAdapter([]).info().provider == "replay"


def test_replay_works_from_a_second_journal_instance(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request("раз")
    ok = make_response("записано")
    log(journal, 1, req, ok)
    reopened = make_journal(tmp_path)
    assert ReplayAdapter(reopened.read_records()).complete(req) == ok


# Replay по run_id (ревью партии 3, D9): повтор того же turn_seq -- другой прогон

def test_replay_of_one_run_ignores_other_runs_of_same_turn(tmp_path):
    journal = make_journal(tmp_path)
    r1, r2 = make_request("а"), make_request("б")
    a1, a2 = make_response("1"), make_response("2")
    log(journal, 1, r1, a1, turn_seq=3, run_id="run-3a")
    journal.mark_turn("run-3a", "aborted")
    log(journal, 2, r2, a2, turn_seq=3, run_id="run-3b")
    runs = group_runs(journal.read_records())
    assert ReplayAdapter(runs["run-3b"]).complete(r2) == a2
    assert ReplayAdapter(runs["run-3a"]).complete(r1) == a1


def test_replay_of_one_run_diverges_on_request_of_another_run(tmp_path):
    journal = make_journal(tmp_path)
    r1, r2 = make_request("а"), make_request("б")
    log(journal, 1, r1, make_response("1"), turn_seq=3, run_id="run-3a")
    log(journal, 2, r2, make_response("2"), turn_seq=3, run_id="run-3b")
    runs = group_runs(journal.read_records())
    with pytest.raises(ReplayDivergence):
        ReplayAdapter(runs["run-3b"]).complete(r1)


# по ролям (П4 этапа 3, Т-11): ReplayAdapter(records, role=...) берёт только записи своей роли

def test_replay_by_role_takes_only_own_records_in_order(tmp_path):
    journal = make_journal(tmp_path)
    narrator, world = make_request("рассказ"), make_request("мир", role="world")
    a_narrator, a_world = make_response("нарратор"), make_response("мир")
    log(journal, 1, narrator, a_narrator, turn_seq=1)
    log(journal, 2, world, a_world, turn_seq=1, run_id="bnd-1")
    adapter = ReplayAdapter(journal.read_records(), role="world")
    assert adapter.complete(world) == a_world


def test_replay_by_role_diverges_when_role_has_no_more_records(tmp_path):
    journal = make_journal(tmp_path)
    narrator, world = make_request("рассказ"), make_request("мир", role="world")
    log(journal, 1, narrator, make_response("нарратор"))
    adapter = ReplayAdapter(journal.read_records(), role="world")
    with pytest.raises(ReplayDivergence):
        adapter.complete(world)


def test_replay_without_role_keeps_all_records(tmp_path):
    journal = make_journal(tmp_path)
    narrator, world = make_request("рассказ"), make_request("мир", role="world")
    log(journal, 1, narrator, make_response("нарратор"))
    log(journal, 2, world, make_response("мир"), run_id="bnd-1")
    adapter = ReplayAdapter(journal.read_records())
    adapter.complete(narrator)
    adapter.complete(world)


def test_replay_keeps_stop_detail(tmp_path):
    journal = make_journal(tmp_path)
    resp = make_response(text="", stop_reason="refusal")
    resp.stop_detail = "SAFETY"
    log(journal, 1, make_request("раз"), resp)
    got = ReplayAdapter(journal.read_records()).complete(make_request("раз"))
    assert got.stop_detail == "SAFETY"


def test_replay_of_record_without_stop_detail_key_gives_none(tmp_path):
    # старые журналы: в response поля stop_detail нет
    journal = make_journal(tmp_path)
    log(journal, 1, make_request("раз"), make_response("старый"))
    records = journal.read_records()
    del records[0]["response"]["stop_detail"]
    got = ReplayAdapter(records).complete(make_request("раз"))
    assert (got.text if hasattr(got, "text") else got.content[0].text) == "старый"
    assert got.stop_detail is None


# 207: поля duration_s / tokens_per_s не в отпечатке; записи с ними и без них воспроизводятся

def test_replay_of_record_with_timing_fields_returns_response(tmp_path):
    journal = make_journal(tmp_path)
    req, resp = make_request("раз"), make_response("с замером")
    journal.record_call(
        call_id="c1", run_id="run-1", ts="2026-10-03T12:00:00", turn_seq=1, attempt=1,
        role=req.role, provider="anthropic", model=req.model, request=req, response=resp,
        duration_s=4.2,
    )
    records = journal.read_records()
    assert records[0]["duration_s"] == 4.2
    assert ReplayAdapter(records).complete(req) == resp


def test_replay_of_record_without_timing_keys_returns_response(tmp_path):
    # старые журналы: полей duration_s / tokens_per_s в записи нет
    journal = make_journal(tmp_path)
    req, resp = make_request("раз"), make_response("старый")
    log(journal, 1, req, resp)
    records = journal.read_records()
    records[0].pop("duration_s", None)
    records[0].pop("tokens_per_s", None)
    assert ReplayAdapter(records).complete(req) == resp
