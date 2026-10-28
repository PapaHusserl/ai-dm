# Ожидаемый API: ai_dm.llm.errors, ai_dm.llm.retry.call_with_retries -- контракт в llm_kit.py.
# ТЗ 2.2: сеть / таймаут / rate limit -- 3 повтора с паузами 1 -> 3 -> 10 с, дальше исключение
# (наружу идёт RetriesExhausted, подкласс LlmTransient). refusal и max_tokens -- ответы, не ошибки.
import pytest
from llm_kit import app_cfg, make_request, make_response

from ai_dm.config.app import RetryConfig
from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import (
    LlmError,
    LlmFatal,
    LlmTransient,
    RetriesExhausted,
    is_auth_error,
)
from ai_dm.llm.retry import call_with_retries


class Flaky:
    # адаптер, отдающий по очереди исключения / ответы
    def __init__(self, results):
        self.results = list(results)
        self.calls = 0

    def complete(self, req):
        self.calls += 1
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def info(self):
        return AdapterInfo(provider="flaky", model="m")


def run(results, policy=None):
    adapter = Flaky(results)
    sleeps = []
    resp = call_with_retries(
        adapter, make_request(), policy or app_cfg().retry, sleeps.append
    )
    return adapter, sleeps, resp


def test_error_hierarchy():
    assert issubclass(LlmTransient, LlmError)
    assert issubclass(LlmFatal, LlmError)
    assert not issubclass(LlmFatal, LlmTransient)
    assert not issubclass(LlmTransient, LlmFatal)


def test_retries_exhausted_is_transient():
    assert issubclass(RetriesExhausted, LlmTransient)


def test_transient_retry_after_defaults_to_none():
    assert LlmTransient("x").retry_after is None


def test_transient_keeps_retry_after():
    assert LlmTransient("x", retry_after=7).retry_after == 7


def test_success_first_try_has_no_pauses():
    ok = make_response()
    adapter, sleeps, resp = run([ok])
    assert (resp, sleeps, adapter.calls) == (ok, [], 1)


def test_three_transient_then_success_returns_response():
    ok = make_response()
    _, _, resp = run([LlmTransient("a"), LlmTransient("b"), LlmTransient("c"), ok])
    assert resp == ok


def test_three_transient_then_success_pauses_are_1_3_10():
    ok = make_response()
    _, sleeps, _ = run([LlmTransient("a"), LlmTransient("b"), LlmTransient("c"), ok])
    assert sleeps == [1, 3, 10]


def test_one_transient_then_success_pauses_once():
    _, sleeps, _ = run([LlmTransient("a"), make_response()])
    assert sleeps == [1]


def test_four_transient_raises_retries_exhausted():
    errors = [LlmTransient(str(i)) for i in range(4)]
    with pytest.raises(RetriesExhausted):
        run(errors)


def test_four_transient_is_catchable_as_transient():
    errors = [LlmTransient(str(i)) for i in range(4)]
    with pytest.raises(LlmTransient):
        run(errors)


def test_four_transient_makes_four_calls_and_three_pauses():
    adapter = Flaky([LlmTransient(str(i)) for i in range(4)])
    sleeps = []
    with pytest.raises(RetriesExhausted) as info:
        call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert (adapter.calls, sleeps, info.value.attempts) == (4, [1, 3, 10], 4)


def test_retries_exhausted_keeps_last_error():
    last = LlmTransient("последняя")
    adapter = Flaky([LlmTransient("a"), LlmTransient("b"), LlmTransient("c"), last])
    with pytest.raises(RetriesExhausted) as info:
        call_with_retries(adapter, make_request(), app_cfg().retry, lambda s: None)
    assert info.value.last is last


def test_fatal_is_not_retried():
    adapter = Flaky([LlmFatal("плохой ключ"), make_response()])
    sleeps = []
    with pytest.raises(LlmFatal):
        call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert (adapter.calls, sleeps) == (1, [])


def test_fatal_after_transient_stops_retrying():
    adapter = Flaky([LlmTransient("a"), LlmFatal("b"), make_response()])
    sleeps = []
    with pytest.raises(LlmFatal):
        call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert (adapter.calls, sleeps) == (2, [1])


def test_foreign_exception_propagates_without_retry():
    adapter = Flaky([ValueError("баг"), make_response()])
    sleeps = []
    with pytest.raises(ValueError):
        call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert (adapter.calls, sleeps) == (1, [])


def test_refusal_is_returned_as_is():
    refusal = make_response(text="не могу", stop_reason="refusal")
    adapter, sleeps, resp = run([refusal])
    assert (resp, sleeps, adapter.calls) == (refusal, [], 1)


def test_max_tokens_is_returned_as_is():
    cut = make_response(text="обрыв", stop_reason="max_tokens")
    adapter, sleeps, resp = run([cut])
    assert (resp, sleeps, adapter.calls) == (cut, [], 1)


def test_retry_after_larger_than_pause_is_used():
    _, sleeps, _ = run([LlmTransient("a", retry_after=7), make_response()])
    assert sleeps == [7]


def test_fractional_retry_after_larger_than_pause_is_used():
    _, sleeps, _ = run([LlmTransient("a", retry_after=2.5), make_response()])
    assert sleeps == [2.5]


def test_fractional_retry_after_smaller_than_pause_is_ignored():
    _, sleeps, _ = run([LlmTransient("a", retry_after=0.25), make_response()])
    assert sleeps == [1]


def test_retry_after_is_capped_at_ten():
    _, sleeps, _ = run([LlmTransient("a", retry_after=30), make_response()])
    assert sleeps == [10]


def test_retry_after_smaller_than_pause_is_ignored():
    _, sleeps, _ = run([LlmTransient("a", retry_after=0), make_response()])
    assert sleeps == [1]


def test_retry_after_applies_only_to_its_attempt():
    errors = [LlmTransient("a", retry_after=7), LlmTransient("b"), make_response()]
    _, sleeps, _ = run(errors)
    assert sleeps == [7, 3]


def test_pauses_follow_policy_delays():
    policy = RetryConfig(delays=[2, 4], invalid_retries=2, max_tool_rounds=8, timeout_s=180)
    _, sleeps, _ = run([LlmTransient("a"), LlmTransient("b"), make_response()], policy)
    assert sleeps == [2, 4]


def test_policy_with_two_delays_gives_up_after_three_calls():
    policy = RetryConfig(delays=[2, 4], invalid_retries=2, max_tool_rounds=8, timeout_s=180)
    adapter = Flaky([LlmTransient(str(i)) for i in range(3)])
    with pytest.raises(RetriesExhausted):
        call_with_retries(adapter, make_request(), policy, lambda s: None)
    assert adapter.calls == 3


def test_on_attempt_sees_every_attempt_with_error_then_response():
    ok = make_response()
    seen = []
    adapter = Flaky([LlmTransient("a"), ok])
    call_with_retries(
        adapter, make_request(), app_cfg().retry, lambda s: None,
        on_attempt=lambda n, resp, err: seen.append((n, resp, type(err).__name__)),
    )
    assert seen == [(1, None, "LlmTransient"), (2, ok, "NoneType")]


def test_on_attempt_sees_fatal_attempt():
    seen = []
    adapter = Flaky([LlmFatal("x")])
    with pytest.raises(LlmFatal):
        call_with_retries(
            adapter, make_request(), app_cfg().retry, lambda s: None,
            on_attempt=lambda n, resp, err: seen.append((n, resp, type(err).__name__)),
        )
    assert seen == [(1, None, "LlmFatal")]


def test_fatal_status_defaults_to_none():
    assert LlmFatal("x").status is None


def test_fatal_keeps_status_and_message():
    error = LlmFatal("текст", status=401)
    assert (error.status, str(error)) == (401, "текст")


@pytest.mark.parametrize("status", [401, 403])
def test_is_auth_error_for_401_and_403(status):
    assert is_auth_error(LlmFatal("x", status=status))


@pytest.mark.parametrize("status", [None, 404, 429, 500])
def test_is_auth_error_false_for_other_status(status):
    assert not is_auth_error(LlmFatal("x", status=status))


def test_is_auth_error_gemini_400_with_invalid_key_text():
    assert is_auth_error(LlmFatal("400 API key not valid. Please pass a valid API key", status=400))


def test_is_auth_error_400_without_those_words_is_not_auth():
    assert not is_auth_error(LlmFatal("400 bad request", status=400))


def test_is_auth_error_text_without_400_is_not_auth():
    assert not is_auth_error(LlmFatal("API key not valid", status=404))


def test_is_auth_error_for_error_without_status_attribute():
    assert not is_auth_error(ValueError("API key not valid"))
