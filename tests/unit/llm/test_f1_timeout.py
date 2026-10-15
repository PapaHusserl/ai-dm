# 19ф Ф1 (docs/19F-PLAN.md п.1 Ф1): «медленная» ошибка -- таймаут или 504 -- не повторяется
# (retry_timeouts = false), первый такой сбой сразу уходит наружу; 503/429/5xx -- по delays.
#   LlmTransient.timeout, RetriesExhausted(timeout от last), is_timeout_error, translate_error
#   адаптеров, give_up, journal/replay/mock со своим ключом timeout.
import httpx
import pytest
from llm_kit import app_cfg, make_request, make_response
from test_llm_anthropic_adapter import StatusError
from test_llm_anthropic_adapter import make as anthropic_make
from test_llm_errors_retry import Flaky
from test_llm_gemini_adapter import ApiError
from test_llm_gemini_adapter import make as gemini_make
from test_llm_gemini_adapter import tools_req as gemini_req

from ai_dm.config.app import JournalConfig
from ai_dm.llm.errors import (
    LlmFatal,
    LlmTransient,
    RetriesExhausted,
    is_timeout_error,
)
from ai_dm.llm.journal import Journal
from ai_dm.llm.mock import ScriptedAdapter, load_script
from ai_dm.llm.replay import ReplayAdapter
from ai_dm.llm.retry import call_with_retries, give_up


def slow(text="таймаут"):
    return LlmTransient(text, timeout=True)


def policy(**kw):
    return app_cfg().retry.model_copy(update=kw)


def run(results, **kw):
    adapter = Flaky(results)
    sleeps = []
    attempts = []
    try:
        call_with_retries(
            adapter, make_request(), policy(**kw), sleeps.append,
            on_attempt=lambda n, resp, err: attempts.append(n),
        )
    except RetriesExhausted as error:
        return adapter, sleeps, attempts, error
    return adapter, sleeps, attempts, None


# LlmTransient / RetriesExhausted

def test_transient_timeout_defaults_to_false():
    assert LlmTransient("x").timeout is False


def test_transient_keeps_timeout_true():
    assert LlmTransient("x", timeout=True).timeout is True


def test_transient_timeout_does_not_break_retry_after():
    error = LlmTransient("x", retry_after=5, timeout=True)
    assert (error.retry_after, error.timeout) == (5, True)


def test_exhausted_takes_timeout_from_last():
    assert RetriesExhausted(1, slow()).timeout is True


def test_exhausted_not_timeout_when_last_is_not():
    assert RetriesExhausted(4, LlmTransient("503")).timeout is False


def test_exhausted_timeout_text_mentions_timeout_and_calls():
    text = str(RetriesExhausted(1, slow("ждали")))
    assert "таймаут" in text
    assert "вызовов: 1" in text
    assert "ждали" in text


def test_exhausted_plain_text_stays_as_before():
    text = str(RetriesExhausted(4, LlmTransient("503")))
    assert text == "повторы исчерпаны (вызовов: 4): 503"


# is_timeout_error

@pytest.mark.parametrize("error", [
    httpx.ReadTimeout("x"), httpx.ConnectTimeout("x"), httpx.WriteTimeout("x"),
    httpx.PoolTimeout("x"), httpx.TimeoutException("x"), TimeoutError("x"),
])
def test_timeout_errors_are_detected(error):
    assert is_timeout_error(error) is True


def test_anthropic_timeout_error_is_detected():
    import anthropic

    error = anthropic.APITimeoutError(request=httpx.Request("POST", "http://x"))
    assert is_timeout_error(error) is True


@pytest.mark.parametrize("error", [
    httpx.ConnectError("x"), httpx.RemoteProtocolError("x"), ValueError("x"),
])
def test_non_timeout_errors_are_not_detected(error):
    assert is_timeout_error(error) is False


# Gemini translate_error

def gemini_error(error):
    adapter, _ = gemini_make([error])
    with pytest.raises((LlmTransient, LlmFatal)) as info:
        adapter.complete(gemini_req())
    return info.value


def test_gemini_504_is_slow_transient():
    error = gemini_error(ApiError(504))
    assert isinstance(error, LlmTransient)
    assert error.timeout is True


@pytest.mark.parametrize("code", [408, 429, 500, 502, 503])
def test_gemini_other_transient_codes_are_not_slow(code):
    error = gemini_error(ApiError(code))
    assert isinstance(error, LlmTransient)
    assert error.timeout is False


def test_gemini_read_timeout_without_code_is_slow():
    error = gemini_error(httpx.ReadTimeout("The read operation timed out"))
    assert isinstance(error, LlmTransient)
    assert error.timeout is True


def test_gemini_connect_error_is_not_slow():
    error = gemini_error(httpx.ConnectError("нет сети"))
    assert isinstance(error, LlmTransient)
    assert error.timeout is False


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_gemini_client_errors_stay_fatal(code):
    assert isinstance(gemini_error(ApiError(code)), LlmFatal)


# Anthropic translate_error

def anthropic_error(error):
    adapter, _, _ = anthropic_make([error])
    with pytest.raises((LlmTransient, LlmFatal)) as info:
        adapter.complete(make_request())
    return info.value


def test_anthropic_504_is_slow_transient():
    error = anthropic_error(StatusError(504))
    assert isinstance(error, LlmTransient)
    assert error.timeout is True


def test_anthropic_503_is_not_slow():
    assert anthropic_error(StatusError(503)).timeout is False


def test_anthropic_504_keeps_retry_after():
    error = anthropic_error(StatusError(504, headers={"retry-after": "7"}))
    assert (error.retry_after, error.timeout) == (7, True)


def test_anthropic_api_timeout_error_is_slow():
    import anthropic

    error = anthropic_error(anthropic.APITimeoutError(request=httpx.Request("POST", "http://x")))
    assert isinstance(error, LlmTransient)
    assert error.timeout is True


def test_anthropic_connect_error_is_not_slow():
    assert anthropic_error(httpx.ConnectError("x")).timeout is False


# give_up

@pytest.mark.parametrize(("attempt", "timeout", "retry_timeouts", "expected"), [
    (1, False, False, False),
    (3, False, False, False),
    (4, False, False, True),
    (1, True, False, True),
    (1, True, True, False),
    (3, True, True, False),
    (4, True, True, True),
])
def test_give_up_table(attempt, timeout, retry_timeouts, expected):
    error = LlmTransient("x", timeout=timeout)
    assert give_up(policy(retry_timeouts=retry_timeouts), attempt, error) is expected


def test_give_up_with_empty_delays_after_first_attempt():
    assert give_up(policy(delays=[]), 1, LlmTransient("x")) is True


# call_with_retries

def test_timeout_on_first_attempt_gives_up_after_one_call():
    adapter, sleeps, attempts, error = run([slow(), make_response()])
    assert error is not None
    assert (adapter.calls, sleeps, attempts) == (1, [], [1])


def test_exhausted_on_timeout_is_marked_slow():
    _, _, _, error = run([slow()])
    assert (error.attempts, error.timeout) == (1, True)


def test_retry_timeouts_true_retries_as_before():
    adapter, sleeps, _, error = run([slow()] * 4, retry_timeouts=True)
    assert (adapter.calls, sleeps, error.attempts) == (4, [1, 3, 10], 4)


def test_503_503_then_504_makes_three_calls_and_two_pauses():
    adapter, sleeps, attempts, error = run(
        [LlmTransient("503"), LlmTransient("503"), slow("504"), make_response()]
    )
    assert (adapter.calls, sleeps, attempts) == (3, [1, 3], [1, 2, 3])
    assert error.timeout is True


def test_503_then_success_is_as_before():
    adapter, sleeps, _, error = run([LlmTransient("503"), make_response()])
    assert (adapter.calls, sleeps, error) == (2, [1], None)


def test_four_503_still_exhaust_after_four_calls():
    adapter, sleeps, _, error = run([LlmTransient("503")] * 4)
    assert (adapter.calls, sleeps, error.attempts, error.timeout) == (4, [1, 3, 10], 4, False)


def test_timeout_with_empty_delays_is_one_call():
    adapter, sleeps, _, error = run([slow()], delays=[])
    assert (adapter.calls, sleeps, error.attempts) == (1, [], 1)


# journal

def make_journal(tmp_path):
    return Journal(tmp_path / "saves", "w1", JournalConfig(max_mb=50, segment_mb=5))


def record_error(journal, error):
    journal.record_call(
        call_id="c1", run_id="run-1", ts="2026-10-16T12:00:00", turn_seq=1, attempt=1,
        role="narrator", provider="gemini", model="gemini-3.8-flash", request=make_request(),
        error=error,
    )
    return journal.read_records()[-1]["error"]


def test_journal_records_timeout_true(tmp_path):
    err = record_error(make_journal(tmp_path), slow("504"))
    assert err == {"kind": "transient", "message": "504", "retry_after": None, "timeout": True}


def test_journal_records_timeout_false_for_plain_transient(tmp_path):
    assert record_error(make_journal(tmp_path), LlmTransient("503"))["timeout"] is False


def test_journal_records_timeout_false_for_fatal(tmp_path):
    assert record_error(make_journal(tmp_path), LlmFatal("400"))["timeout"] is False


# replay

def log_error(journal, error):
    req = make_request()
    record_error(journal, error)
    return req


def replayed(tmp_path, error=None, raw=None):
    journal = make_journal(tmp_path)
    req = log_error(journal, error or LlmTransient("x"))
    records = journal.read_records()
    if raw is not None:
        records[0]["error"] = raw
    with pytest.raises(LlmTransient) as info:
        ReplayAdapter(records).complete(req)
    return info.value


def test_replay_restores_timeout_true(tmp_path):
    assert replayed(tmp_path, slow()).timeout is True


def test_replay_record_without_timeout_key_is_not_slow(tmp_path):
    raw = {"kind": "transient", "message": "x", "retry_after": None}
    assert replayed(tmp_path, raw=raw).timeout is False


def test_replay_of_old_timeout_run_still_retries_to_the_end(tmp_path):
    journal = make_journal(tmp_path)
    req = make_request()
    for n in range(4):
        journal.record_call(
            call_id=f"c{n}", run_id="run-1", ts="2026-10-16T12:00:00", turn_seq=1, attempt=n + 1,
            role="narrator", provider="gemini", model="m", request=req, error=slow(),
        )
    records = journal.read_records()
    for rec in records:
        del rec["error"]["timeout"]
    adapter = ReplayAdapter(records)
    with pytest.raises(RetriesExhausted) as info:
        call_with_retries(adapter, req, policy(), lambda s: None)
    assert info.value.attempts == 4


# mock

def test_mock_transient_step_timeout_true():
    adapter = ScriptedAdapter([{"error": "transient", "timeout": True}])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.timeout is True


def test_mock_transient_step_timeout_defaults_to_false():
    adapter = ScriptedAdapter([{"error": "transient"}])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.timeout is False


def test_mock_yaml_accepts_timeout_key(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text("steps:\n  - error: transient\n    timeout: true\n", encoding="utf-8")
    assert load_script(path) == [{"error": "transient", "timeout": True}]


def test_mock_unknown_key_is_still_rejected(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text("steps:\n  - error: transient\n    bogus: 1\n", encoding="utf-8")
    with pytest.raises(ValueError):
        load_script(path)
