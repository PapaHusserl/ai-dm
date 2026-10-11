# Ожидаемый API: ai_dm.llm.mock (ScriptedAdapter, load_script, ScriptError...) -- контракт в
# llm_kit.py. Сценарии YAML лежат в tests/fixtures/scripts/.
from pathlib import Path

import pytest
from llm_kit import app_cfg, make_request, user

from ai_dm.llm.errors import LlmError, LlmFatal, LlmTransient
from ai_dm.llm.mock import (
    ScriptedAdapter,
    ScriptError,
    ScriptExhausted,
    ScriptMismatch,
    load_script,
)
from ai_dm.llm.retry import call_with_retries
from ai_dm.llm.types import Message, Text, ToolCall, ToolResult, Usage

SCRIPTS = Path(__file__).resolve().parents[2] / "fixtures" / "scripts"


def test_text_step_gives_text_response():
    resp = ScriptedAdapter([{"text": "Привет, путник."}]).complete(make_request())
    assert resp.content == [Text(text="Привет, путник.")]


def test_text_step_stops_with_end_turn():
    resp = ScriptedAdapter([{"text": "x"}]).complete(make_request())
    assert resp.stop_reason == "end_turn"


def test_default_usage_is_zero():
    resp = ScriptedAdapter([{"text": "x"}]).complete(make_request())
    assert resp.usage == Usage()


def test_step_usage_is_passed_through():
    step = {"text": "x", "usage": {"input": 100, "output": 20, "cache_read": 50}}
    resp = ScriptedAdapter([step]).complete(make_request())
    assert resp.usage == Usage(input=100, output=20, cache_read=50)


def test_request_id_is_numbered_from_one():
    adapter = ScriptedAdapter([{"text": "a"}, {"text": "b"}])
    ids = [adapter.complete(make_request()).request_id for _ in range(2)]
    assert ids == ["mock-1", "mock-2"]


def test_tool_calls_step_gives_tool_call_blocks():
    step = {"tool_calls": [{"id": "c1", "name": "skill_check", "input": {"skill": "stealth"}}]}
    resp = ScriptedAdapter([step]).complete(make_request())
    assert resp.content == [ToolCall(id="c1", name="skill_check", input={"skill": "stealth"})]


def test_tool_calls_step_stops_with_tool_use():
    step = {"tool_calls": [{"name": "end_scene", "input": {}}]}
    resp = ScriptedAdapter([step]).complete(make_request())
    assert resp.stop_reason == "tool_use"


def test_text_and_tool_calls_go_text_first():
    step = {"text": "бросаю", "tool_calls": [{"name": "rest", "input": {}}]}
    resp = ScriptedAdapter([step]).complete(make_request())
    assert [type(b) for b in resp.content] == [Text, ToolCall]


def test_missing_tool_call_ids_are_generated_unique():
    step = {"tool_calls": [{"name": "a", "input": {}}, {"name": "b", "input": {}}]}
    first, second = ScriptedAdapter([step]).complete(make_request()).content
    assert first.id and second.id and first.id != second.id


def test_transient_step_raises_transient_with_message():
    adapter = ScriptedAdapter([{"error": "transient", "message": "сеть упала"}])
    with pytest.raises(LlmTransient, match="сеть упала"):
        adapter.complete(make_request())


def test_transient_step_carries_retry_after():
    adapter = ScriptedAdapter([{"error": "transient", "retry_after": 5}])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.retry_after == 5


def test_fatal_step_raises_fatal():
    adapter = ScriptedAdapter([{"error": "fatal", "message": "ключ неверный"}])
    with pytest.raises(LlmFatal, match="ключ неверный"):
        adapter.complete(make_request())


def test_error_step_is_consumed_so_next_call_gets_next_step():
    adapter = ScriptedAdapter([{"error": "transient"}, {"text": "после сбоя"}])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())
    assert adapter.complete(make_request()).content == [Text(text="после сбоя")]


def test_refusal_step_is_a_response_not_an_error():
    resp = ScriptedAdapter([{"stop": "refusal", "text": "не буду"}]).complete(make_request())
    assert (resp.stop_reason, resp.content) == ("refusal", [Text(text="не буду")])


def test_max_tokens_step_is_a_response_not_an_error():
    resp = ScriptedAdapter([{"stop": "max_tokens", "text": "обор"}]).complete(make_request())
    assert (resp.stop_reason, resp.content) == ("max_tokens", [Text(text="обор")])


def test_requests_are_recorded_in_order():
    adapter = ScriptedAdapter([{"text": "a"}, {"text": "b"}])
    first, second = make_request("раз"), make_request("два")
    adapter.complete(first)
    adapter.complete(second)
    assert adapter.requests == [first, second]


def test_request_with_error_step_is_recorded_too():
    adapter = ScriptedAdapter([{"error": "fatal"}])
    req = make_request()
    with pytest.raises(LlmFatal):
        adapter.complete(req)
    assert adapter.requests == [req]


def test_exhausted_script_raises_script_exhausted():
    adapter = ScriptedAdapter([{"text": "единственный"}])
    adapter.complete(make_request())
    with pytest.raises(ScriptExhausted):
        adapter.complete(make_request())


def test_exhausted_message_names_the_role():
    adapter = ScriptedAdapter([])
    with pytest.raises(ScriptExhausted) as info:
        adapter.complete(make_request(role="narrator"))
    assert "narrator" in str(info.value)


def test_exhausted_request_is_still_recorded():
    adapter = ScriptedAdapter([])
    req = make_request()
    with pytest.raises(ScriptExhausted):
        adapter.complete(req)
    assert adapter.requests == [req]


def test_script_errors_are_not_llm_errors():
    # иначе повторы и «сеть» спрятали бы ошибку сценария
    assert issubclass(ScriptExhausted, ScriptError)
    assert issubclass(ScriptMismatch, ScriptError)
    assert not issubclass(ScriptError, LlmError)


def test_exhaustion_passes_through_retries_unretried():
    adapter = ScriptedAdapter([])
    sleeps = []
    with pytest.raises(ScriptExhausted):
        call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert sleeps == []


def test_when_role_matches():
    adapter = ScriptedAdapter([{"when": {"role": "world"}, "text": "хроника"}])
    resp = adapter.complete(make_request(role="world"))
    assert resp.content == [Text(text="хроника")]


def test_when_role_mismatch_raises_script_mismatch():
    adapter = ScriptedAdapter([{"when": {"role": "world"}, "text": "хроника"}])
    with pytest.raises(ScriptMismatch):
        adapter.complete(make_request(role="narrator"))


def test_mismatch_does_not_consume_the_step():
    adapter = ScriptedAdapter([{"when": {"role": "world"}, "text": "хроника"}])
    with pytest.raises(ScriptMismatch):
        adapter.complete(make_request(role="narrator"))
    assert adapter.complete(make_request(role="world")).content == [Text(text="хроника")]


def test_when_last_message_contains_matches_text():
    adapter = ScriptedAdapter([{"when": {"last_message_contains": "дверь"}, "text": "скрип"}])
    resp = adapter.complete(make_request("Я открываю дверь"))
    assert resp.content == [Text(text="скрип")]


def test_when_last_message_contains_mismatch():
    adapter = ScriptedAdapter([{"when": {"last_message_contains": "дверь"}, "text": "скрип"}])
    with pytest.raises(ScriptMismatch):
        adapter.complete(make_request("Я иду к окну"))


def test_when_last_message_contains_looks_at_tool_result():
    adapter = ScriptedAdapter([{"when": {"last_message_contains": "СЛ 15"}, "text": "итог"}])
    req = make_request(messages=[
        user("убеждаю"),
        Message(role="assistant", content=[ToolCall(id="c1", name="skill_check", input={})]),
        Message(role="user", content=[ToolResult(call_id="c1", content="бросок 12 против СЛ 15")]),
    ])
    assert adapter.complete(req).content == [Text(text="итог")]


def test_when_checks_only_the_last_message():
    adapter = ScriptedAdapter([{"when": {"last_message_contains": "дверь"}, "text": "x"}])
    req = make_request(messages=[
        user("дверь"),
        Message(role="assistant", content=[Text(text="ок")]),
        user("окно"),
    ])
    with pytest.raises(ScriptMismatch):
        adapter.complete(req)


def test_when_with_both_conditions_needs_both():
    when = {"role": "narrator", "last_message_contains": "дверь"}
    adapter = ScriptedAdapter([{"when": when, "text": "x"}])
    with pytest.raises(ScriptMismatch):
        adapter.complete(make_request("дверь", role="world"))


def test_info_names_mock_provider():
    info = ScriptedAdapter([]).info()
    assert (info.provider, info.model) == ("mock", "mock")


def test_load_script_reads_fixture():
    steps = load_script(SCRIPTS / "talk_check.yaml")
    assert len(steps) == 2
    assert steps[0]["tool_calls"][0]["name"] == "skill_check"


def test_from_yaml_runs_fixture_steps_in_order():
    adapter = ScriptedAdapter.from_yaml(SCRIPTS / "talk_check.yaml")
    first = adapter.complete(make_request())
    second = adapter.complete(make_request())
    assert (first.stop_reason, second.stop_reason) == ("tool_use", "end_turn")
    assert second.usage == Usage(input=1200, output=80, cache_read=900)


def test_fixture_tool_call_input_survives_yaml():
    adapter = ScriptedAdapter.from_yaml(SCRIPTS / "talk_check.yaml")
    call = adapter.complete(make_request()).content[1]
    assert (call.id, call.input["skill"], call.input["category"]) == (
        "call-1", "persuasion", "medium",
    )


def test_transient_fixture_works_with_retries():
    adapter = ScriptedAdapter.from_yaml(SCRIPTS / "transient_x3.yaml")
    sleeps = []
    resp = call_with_retries(adapter, make_request(), app_cfg().retry, sleeps.append)
    assert (resp.content, sleeps, len(adapter.requests)) == (
        [Text(text="Наконец-то ответ.")], [1, 3, 10], 4,
    )


def write_yaml(tmp_path, text):
    path = tmp_path / "script.yaml"
    path.write_text(text, encoding="utf-8")
    return path


def test_load_script_rejects_unknown_key(tmp_path):
    path = write_yaml(tmp_path, "steps:\n  - text: x\n    bogus: 1\n")
    with pytest.raises(ValueError):
        load_script(path)


def test_load_script_rejects_empty_step(tmp_path):
    path = write_yaml(tmp_path, "steps:\n  - {}\n")
    with pytest.raises(ValueError):
        load_script(path)


def test_load_script_rejects_unknown_error_kind(tmp_path):
    path = write_yaml(tmp_path, "steps:\n  - error: boom\n")
    with pytest.raises(ValueError):
        load_script(path)


def test_load_script_rejects_unknown_stop(tmp_path):
    path = write_yaml(tmp_path, "steps:\n  - stop: pause_turn\n")
    with pytest.raises(ValueError):
        load_script(path)
