# Ожидаемый API: ai_dm.llm.openai_adapter.OpenAIAdapter -- контракт в llm_kit.py и
# docs/llm-notes/openai-facts.md, на фейковом клиенте (сети и SDK нет).
#   OpenAIAdapter(model, app_cfg, *, client_factory=None, api_key=None)
#     клиент -- объект с .responses.create(**kw); создаётся лениво: client_factory(api_key=,
#     max_retries=0, timeout=cfg.retry.timeout_s), по умолчанию openai.OpenAI.
#     complete(req): responses.create(model=req.model, instructions=<system через пустую строку>,
#       input=[...], tools=[{type: function, name, description, parameters, strict}],
#       max_output_tokens=req.max_tokens, reasoning={"effort"} только при effort, store=False,
#       include=["reasoning.encrypted_content"]).
#     input: user Text -> message/input_text; assistant Text -> message/output_text; ToolCall ->
#       function_call (arguments -- JSON-строка); ToolResult -> function_call_output (is_error --
#       {"error": content}); assistant с Opaque("openai", {"items": [...]}) -- ровно эти items
#       вместо Text/ToolCall сообщения; Opaque чужих провайдеров пропускаются.
#     ответ: content = [Text, ToolCall..., Opaque("openai", {"items": [dump всех output]})];
#       stop_reason: есть function_call -> tool_use; refusal -> refusal (+ stop_detail);
#       incomplete max_output_tokens -> max_tokens, content_filter -> refusal, иное -> other;
#       completed -> end_turn; failed -> LlmTransient (server_error, rate_limit_exceeded) или
#       LlmFatal.
#     usage: input = input_tokens - cached - cache_write; cache_read = cached;
#       cache_write = cache_write_tokens (None -> 0); cache_write_1h = 0; output = output_tokens.
#     ошибки: status_code 408/429/>=500 -> LlmTransient (retry_after из заголовков, 504 -> timeout),
#       прочие -> LlmFatal; без кода -- сетевые по имени класса; ключ вычищается.
#     info() -> AdapterInfo("openai", model)
import json
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg, full_request, make_request, user

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.cost import cost_nano
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.openai_adapter import OpenAIAdapter
from ai_dm.llm.types import (
    Message,
    Opaque,
    SystemBlock,
    Text,
    ToolCall,
    ToolResult,
    ToolSpec,
    Usage,
)
from ai_dm.master.session import api_tokens
from ai_dm.protocol.schema import tool_set

MODEL = "gpt-6.1-sol"
SECRET = "sk-FAKE-0123456789-ZZZ"


class Item(SimpleNamespace):
    # элемент output: атрибуты как у SDK, model_dump отдаёт заранее заданный dict
    def model_dump(self, **kw):
        return dict(self.dump)


def reasoning(enc="ZW5j"):
    dump = {"type": "reasoning", "id": "rs_1", "encrypted_content": enc, "summary": []}
    return Item(type="reasoning", dump=dump)


def message(text):
    dump = {"type": "message", "role": "assistant",
            "content": [{"type": "output_text", "text": text}]}
    part = SimpleNamespace(type="output_text", text=text)
    return Item(type="message", content=[part], dump=dump)


def refusal(text):
    dump = {"type": "message", "role": "assistant",
            "content": [{"type": "refusal", "refusal": text}]}
    part = SimpleNamespace(type="refusal", refusal=text)
    return Item(type="message", content=[part], dump=dump)


def function_call(call_id="call_1", name="skill_check", arguments='{"skill": "perception"}'):
    dump = {"type": "function_call", "call_id": call_id, "name": name, "arguments": arguments}
    return Item(type="function_call", call_id=call_id, name=name, arguments=arguments, dump=dump)


def usage_obj(inp=0, out=0, cached=0, written=0, details=True):
    fields = {"cached_tokens": cached}
    if written is not None:
        fields["cache_write_tokens"] = written
    return SimpleNamespace(
        input_tokens=inp, output_tokens=out,
        input_tokens_details=SimpleNamespace(**fields) if details else None,
    )


def api_response(
    output=None, status="completed", usage=None, rid="req-77", model="gpt-6.1-sol-2026",
    reason=None, error=None,
):
    details = SimpleNamespace(reason=reason) if reason else None
    response = SimpleNamespace(
        output=output if output is not None else [message("ок")], status=status,
        usage=usage or usage_obj(), model=model, incomplete_details=details, error=error,
    )
    response._request_id = rid
    return response


class FakeResponses:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def make(results=None, api_key=None):
    responses = FakeResponses(results if results is not None else [api_response()])
    adapter = OpenAIAdapter(
        MODEL, app_cfg(), client_factory=lambda **kw: SimpleNamespace(responses=responses),
        api_key=api_key,
    )
    return adapter, responses


def tools_req(mode="explore", **kw):
    tools = [ToolSpec.model_validate(t) for t in tool_set(mode)]
    kw.setdefault("model", MODEL)
    return make_request(tools=tools, **kw)


def sent(req=None):
    adapter, responses = make()
    adapter.complete(req or full_request())
    return responses.calls[0]


def sent_input(messages):
    return sent(make_request(model=MODEL, messages=messages))["input"]


def result(output=None, **kw):
    adapter, _ = make([api_response(output, **kw)])
    return adapter.complete(make_request(model=MODEL))


def test_info_names_openai():
    adapter, _ = make()
    assert adapter.info() == AdapterInfo(provider="openai", model=MODEL)


def test_model_is_taken_from_request_not_from_adapter():
    adapter, responses = make()
    adapter.complete(make_request(model="gpt-6-luna"))
    assert responses.calls[0]["model"] == "gpt-6-luna"


def test_info_keeps_adapter_model_whatever_the_request():
    adapter, _ = make()
    adapter.complete(make_request(model="gpt-6-luna"))
    assert adapter.info().model == MODEL


def test_instructions_join_system_blocks_with_blank_line():
    system = [SystemBlock(text="правила", cache=True), SystemBlock(text="мир", cache=True)]
    assert sent(make_request(model=MODEL, system=system))["instructions"] == "правила\n\nмир"


def test_max_output_tokens_from_request():
    assert sent(make_request(model=MODEL, max_tokens=8000))["max_output_tokens"] == 8000


def test_reasoning_effort_from_request():
    assert sent(full_request())["reasoning"] == {"effort": "medium"}


def test_no_effort_means_no_reasoning_key():
    assert "reasoning" not in sent(make_request(model=MODEL))


def test_store_is_false():
    assert sent()["store"] is False


def test_encrypted_reasoning_is_requested():
    assert sent()["include"] == ["reasoning.encrypted_content"]


def test_tool_choice_and_parallel_calls_are_not_passed():
    kwargs = sent(tools_req())
    assert "tool_choice" not in kwargs
    assert "parallel_tool_calls" not in kwargs


def test_tool_becomes_strict_function():
    tool = tool_set("combat_classify")[0]
    first = sent(tools_req("combat_classify"))["tools"][0]
    assert first == {
        "type": "function", "name": tool["name"], "description": tool["description"],
        "parameters": tool["input_schema"], "strict": True,
    }


def test_tools_keep_order_of_the_set():
    tools = sent(tools_req("combat_classify"))["tools"]
    assert [t["name"] for t in tools] == [t["name"] for t in tool_set("combat_classify")]


def test_non_strict_tool_goes_with_strict_false():
    spec = [ToolSpec.model_validate({**t, "strict": False}) for t in tool_set("combat_classify")]
    tools = sent(make_request(model=MODEL, tools=spec))["tools"]
    assert all(t["strict"] is False for t in tools)


def test_explore_non_strict_tools_keep_their_flag():
    expected = [t["strict"] for t in tool_set("explore")]
    assert False in expected
    assert [t["strict"] for t in sent(tools_req("explore"))["tools"]] == expected


def test_strict_tools_off_in_config_makes_every_tool_non_strict():
    adapter, responses = make()
    adapter.cfg.llm.strict_tools = False
    adapter.complete(tools_req("combat_classify"))
    assert all(t["strict"] is False for t in responses.calls[0]["tools"])


def test_request_without_tools_has_no_tools_key():
    assert "tools" not in sent(make_request(model=MODEL))


def test_user_text_becomes_input_text_message():
    assert sent_input([user("осмотрюсь")]) == [{
        "type": "message", "role": "user",
        "content": [{"type": "input_text", "text": "осмотрюсь"}],
    }]


def test_assistant_text_becomes_output_text_message():
    items = sent_input([user("а"), Message(role="assistant", content=[Text(text="рассказ")])])
    assert items[1] == {
        "type": "message", "role": "assistant",
        "content": [{"type": "output_text", "text": "рассказ"}],
    }


def test_tool_call_becomes_function_call_with_json_arguments():
    call = ToolCall(id="c1", name="skill_check", input={"skill": "проверка"})
    items = sent_input([user("а"), Message(role="assistant", content=[call])])
    assert items[1]["type"] == "function_call"
    assert (items[1]["call_id"], items[1]["name"]) == ("c1", "skill_check")
    assert json.loads(items[1]["arguments"]) == {"skill": "проверка"}


def test_function_call_arguments_keep_non_ascii_text():
    call = ToolCall(id="c1", name="x", input={"k": "рассказ"})
    items = sent_input([user("а"), Message(role="assistant", content=[call])])
    assert "рассказ" in items[1]["arguments"]


def test_tool_result_becomes_function_call_output_with_same_call_id():
    items = sent(full_request())["input"]
    assert items[-1] == {"type": "function_call_output", "call_id": "c1", "output": '{"ok": true}'}


def test_full_request_history_order():
    items = sent(full_request())["input"]
    kinds = ["message", "message", "function_call", "function_call_output"]
    assert [i["type"] for i in items] == kinds


def test_tool_result_error_keeps_the_text():
    block = ToolResult(call_id="c1", content="нет цели", is_error=True)
    items = sent_input([user("а"), Message(role="user", content=[block])])
    assert "нет цели" in items[-1]["output"]
    assert items[-1]["call_id"] == "c1"


def test_tool_result_error_is_marked_apart_from_success():
    ok = sent_input([Message(role="user", content=[ToolResult(call_id="c", content="x")])])
    bad = sent_input([
        Message(role="user", content=[ToolResult(call_id="c", content="x", is_error=True)]),
    ])
    assert ok[-1]["output"] != bad[-1]["output"]


def opaque_history(raw_items, extra=None):
    blocks = [Text(text="рассказ"), ToolCall(id="c1", name="skill_check", input={})]
    blocks.append(Opaque(provider="openai", raw={"items": raw_items}))
    blocks += extra or []
    return [user("а"), Message(role="assistant", content=blocks), user("б")]


def test_opaque_items_replace_text_and_tool_call_of_that_message():
    raw = [{"type": "reasoning", "id": "rs_1", "encrypted_content": "e", "summary": []},
           {"type": "function_call", "call_id": "c1", "name": "skill_check", "arguments": "{}"}]
    items = sent_input(opaque_history(raw))
    assert items[1:3] == raw
    assert len(items) == 4


def test_opaque_items_are_passed_unchanged():
    raw = [{"type": "reasoning", "id": "rs_9", "encrypted_content": "ZZ", "summary": [], "x": 1}]
    assert sent_input(opaque_history(raw))[1] == raw[0]


def test_foreign_opaque_is_skipped():
    history = [
        user("а"),
        Message(role="assistant", content=[
            Opaque(provider="gemini", raw={"parts": [{"text": "чужое"}]}), Text(text="рассказ"),
        ]),
    ]
    items = sent_input(history)
    assert len(items) == 2
    assert items[1]["content"] == [{"type": "output_text", "text": "рассказ"}]


def test_text_response_to_text_block():
    assert result([message("Привет")]).content[0] == Text(text="Привет")


def test_text_response_is_end_turn():
    assert result([message("Привет")]).stop_reason == "end_turn"


def test_reasoning_and_message_give_text_then_opaque_with_both_items():
    items = [reasoning(), message("рассказ")]
    content = result(items).content
    assert content == [
        Text(text="рассказ"),
        Opaque(provider="openai", raw={"items": [i.dump for i in items]}),
    ]


def test_function_call_becomes_tool_call():
    response = result([reasoning(), function_call()])
    calls = [b for b in response.content if isinstance(b, ToolCall)]
    assert calls == [ToolCall(id="call_1", name="skill_check", input={"skill": "perception"})]
    assert response.stop_reason == "tool_use"


def test_two_function_calls_keep_order():
    output = [function_call("call_1", "a", "{}"), function_call("call_2", "b", "{}")]
    calls = [b for b in result(output).content if isinstance(b, ToolCall)]
    assert [(c.id, c.name) for c in calls] == [("call_1", "a"), ("call_2", "b")]


def test_text_with_tool_call_order_is_text_calls_opaque():
    content = result([message("иду"), function_call()]).content
    assert [type(b) for b in content] == [Text, ToolCall, Opaque]


def test_tool_use_wins_over_text():
    assert result([message("иду"), function_call()]).stop_reason == "tool_use"


def test_arguments_that_are_not_json_are_fatal():
    with pytest.raises(LlmFatal):
        result([function_call(arguments="{не json")])


def test_function_call_item_dump_is_kept_in_opaque():
    call = function_call()
    assert result([call]).content[-1].raw == {"items": [call.dump]}


def test_empty_output_has_no_opaque():
    assert result([]).content == []


def test_refusal_is_refusal_with_detail():
    response = result([refusal("не могу")])
    assert response.stop_reason == "refusal"
    assert response.stop_detail == "не могу"


def test_refusal_gives_no_text_block():
    assert not [b for b in result([refusal("не могу")]).content if isinstance(b, Text)]


def test_normal_answer_has_no_stop_detail():
    assert result([message("ок")]).stop_detail is None


def test_incomplete_max_output_tokens_is_max_tokens():
    response = result([message("обор")], status="incomplete", reason="max_output_tokens")
    assert response.stop_reason == "max_tokens"
    assert response.stop_detail is None


def test_incomplete_content_filter_is_refusal():
    response = result([], status="incomplete", reason="content_filter")
    assert response.stop_reason == "refusal"
    assert response.stop_detail == "content_filter"


def cut_response(*extra):
    call = function_call(arguments='{"skill": "perce')
    return call, result([message("иду"), call, *extra], status="incomplete",
                        reason="max_output_tokens")


def test_cut_function_call_with_broken_json_is_max_tokens_not_fatal():
    _, response = cut_response()
    assert response.stop_reason == "max_tokens"


def test_cut_function_call_gives_no_tool_call():
    _, response = cut_response()
    assert not [b for b in response.content if isinstance(b, ToolCall)]


def test_cut_function_call_with_valid_json_is_still_no_tool_call():
    response = result([function_call()], status="incomplete", reason="max_output_tokens")
    assert not [b for b in response.content if isinstance(b, ToolCall)]
    assert response.stop_reason == "max_tokens"


def test_cut_response_keeps_all_items_in_opaque():
    call, response = cut_response()
    assert response.content[-1].raw["items"][-1] == call.dump
    assert len(response.content[-1].raw["items"]) == 2


def test_cut_response_keeps_text_before_the_cut():
    _, response = cut_response()
    assert response.content[0] == Text(text="иду")


def test_refusal_wins_over_cut_max_tokens():
    response = result([refusal("не могу")], status="incomplete", reason="max_output_tokens")
    assert response.stop_reason == "refusal"


def test_broken_json_in_completed_response_is_still_fatal():
    with pytest.raises(LlmFatal):
        result([function_call(arguments='{"skill": "perce')])


def test_retry_after_of_lives_in_errors_module():
    from ai_dm.llm.errors import retry_after_of

    error = StatusError(429, headers={"retry-after": "3"})
    assert retry_after_of(error) == 3.0


@pytest.mark.parametrize("reason", ["max_messages", "steered"])
def test_incomplete_other_reasons_are_other(reason):
    assert result([], status="incomplete", reason=reason).stop_reason == "other"


def test_unknown_status_is_other():
    assert result([], status="cancelled").stop_reason == "other"


def failed(code, message="сбой"):
    return api_response([], status="failed", error=SimpleNamespace(code=code, message=message))


@pytest.mark.parametrize("code", ["server_error", "rate_limit_exceeded"])
def test_failed_response_with_transient_code_is_transient(code):
    adapter, _ = make([failed(code)])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request(model=MODEL))


def test_failed_response_with_other_code_is_fatal():
    adapter, _ = make([failed("invalid_prompt")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert not isinstance(info.value, LlmTransient)


def test_failed_response_keeps_message():
    adapter, _ = make([failed("invalid_prompt", "промпт отклонён")])
    with pytest.raises(LlmFatal, match="промпт отклонён"):
        adapter.complete(make_request(model=MODEL))


def test_failed_response_without_error_is_fatal():
    adapter, _ = make([api_response([], status="failed")])
    with pytest.raises(LlmFatal):
        adapter.complete(make_request(model=MODEL))


def test_usage_is_mapped_without_overlap():
    usage = usage_obj(inp=30000, out=3000, cached=20000, written=9000)
    got = result(usage=usage).usage
    assert got == Usage(input=1000, cache_read=20000, cache_write=9000, output=3000)


def test_zero_usage_stays_zero():
    assert result(usage=usage_obj(inp=0, out=0)).usage == Usage()


def test_item_from_api_dumps_json_mode_without_none_fields():
    from datetime import datetime

    from pydantic import BaseModel

    from ai_dm.llm.openai_adapter import item_from_api

    class Dummy(BaseModel):
        when: datetime
        empty: str | None = None

    assert item_from_api(Dummy(when=datetime(2026, 1, 2, 3, 4, 5))) == {
        "when": "2026-01-02T03:04:05",
    }


def test_tool_result_error_is_json_with_error_key():
    block = ToolResult(call_id="c1", content="нет цели", is_error=True)
    items = sent_input([user("а"), Message(role="user", content=[block])])
    assert json.loads(items[-1]["output"]) == {"error": "нет цели"}


def test_broken_arguments_error_names_the_problem():
    with pytest.raises(LlmFatal, match="^аргументы вызова не JSON$"):
        result([function_call(arguments="{не json")])


def test_missing_request_id_attribute_gives_none():
    response = api_response()
    del response._request_id
    adapter, _ = make([response])
    assert adapter.complete(make_request(model=MODEL)).request_id is None


def test_completed_response_ignores_stray_incomplete_details():
    response = result([function_call()], status="completed", reason="max_output_tokens")
    assert [b for b in response.content if isinstance(b, ToolCall)]
    assert response.stop_reason == "tool_use"


def test_incomplete_without_details_is_other():
    assert result([], status="incomplete").stop_reason == "other"


def test_failed_response_without_error_text_is_none_code_and_empty_message():
    adapter, _ = make([api_response([], status="failed")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert str(info.value) == "None: "


def test_failed_transient_response_keeps_message():
    adapter, _ = make([failed("server_error", "сервер упал")])
    with pytest.raises(LlmTransient, match="сервер упал"):
        adapter.complete(make_request(model=MODEL))


def test_transient_status_error_keeps_message():
    adapter, _ = make([StatusError(503, "перегрузка")])
    with pytest.raises(LlmTransient, match="перегрузка"):
        adapter.complete(make_request(model=MODEL))


def test_network_error_keeps_message():
    adapter, _ = make([APIConnectionError("обрыв сети")])
    with pytest.raises(LlmTransient, match="обрыв сети"):
        adapter.complete(make_request(model=MODEL))


def test_unknown_exception_keeps_message():
    adapter, _ = make([RuntimeError("что-то странное")])
    with pytest.raises(LlmFatal, match="что-то странное"):
        adapter.complete(make_request(model=MODEL))


def test_usage_cache_write_1h_is_zero():
    usage = usage_obj(inp=30000, out=3000, cached=20000, written=9000)
    assert result(usage=usage).usage.cache_write_1h == 0


def test_usage_without_cache_write_field_is_zero():
    got = result(usage=usage_obj(inp=100, out=10, cached=40, written=None)).usage
    assert (got.input, got.cache_read, got.cache_write) == (60, 40, 0)


def test_usage_with_none_cache_write_is_zero():
    usage = usage_obj(inp=100, out=10, cached=40)
    usage.input_tokens_details.cache_write_tokens = None
    assert result(usage=usage).usage == Usage(input=60, cache_read=40, output=10)


def test_usage_without_details_is_all_input():
    got = result(usage=usage_obj(inp=100, out=10, details=False)).usage
    assert got == Usage(input=100, output=10)


def test_missing_usage_is_zero():
    response = api_response()
    response.usage = None
    adapter, _ = make([response])
    assert adapter.complete(make_request(model=MODEL)).usage == Usage()


def test_api_tokens_of_openai_usage_is_input_tokens():
    usage = usage_obj(inp=30000, out=3000, cached=20000, written=9000)
    assert api_tokens(result(usage=usage).usage, "openai") == 30000


def test_cost_of_openai_usage():
    usage = usage_obj(inp=30000, out=3000, cached=20000, written=9000)
    price = app_cfg().prices[MODEL]
    assert cost_nano(result(usage=usage).usage, price) == 56_500_000


def test_request_id_from_private_attribute():
    assert result(rid="req-5").request_id == "req-5"


def test_response_model_is_taken_from_response():
    assert result(model="gpt-6.1-sol-2026").model == "gpt-6.1-sol-2026"


def test_response_model_falls_back_to_requested_model():
    assert result(model=None).model == MODEL


class StatusError(Exception):
    def __init__(self, code, message="ошибка", headers=None):
        super().__init__(message)
        self.status_code = code
        self.response = SimpleNamespace(headers=headers or {})


@pytest.mark.parametrize("code", [408, 429, 500, 503])
def test_status_errors_that_are_transient(code):
    adapter, _ = make([StatusError(code)])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request(model=MODEL))


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_status_errors_that_are_fatal(code):
    adapter, _ = make([StatusError(code)])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert not isinstance(info.value, LlmTransient)


def test_retry_after_header_goes_to_error():
    adapter, _ = make([StatusError(429, headers={"retry-after": "7"})])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.retry_after == 7.0


def test_gateway_timeout_is_marked_timeout():
    adapter, _ = make([StatusError(504)])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is True


def test_server_error_is_not_marked_timeout():
    adapter, _ = make([StatusError(503)])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is False


def test_error_message_is_kept():
    adapter, _ = make([StatusError(400, "неверная схема функции")])
    with pytest.raises(LlmFatal, match="неверная схема функции"):
        adapter.complete(make_request(model=MODEL))


def test_error_message_does_not_leak_the_api_key():
    adapter, _ = make([StatusError(401, f"Incorrect API key: {SECRET}")], api_key=SECRET)
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert SECRET not in str(info.value)
    assert "***" in str(info.value)


def test_failed_response_message_does_not_leak_the_api_key():
    adapter, _ = make([failed("invalid_prompt", f"ключ {SECRET}")], api_key=SECRET)
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert SECRET not in str(info.value)


class APIConnectionError(Exception):
    pass


class APITimeoutError(APIConnectionError):
    pass


def test_connection_error_without_code_is_transient_not_timeout():
    adapter, _ = make([APIConnectionError("сеть")])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is False


def test_timeout_error_without_code_is_transient_timeout():
    adapter, _ = make([APITimeoutError("долго")])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is True


def test_unknown_exception_without_code_is_fatal():
    adapter, _ = make([RuntimeError("что-то странное")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert not isinstance(info.value, LlmTransient)


def test_adapter_makes_one_call_per_complete():
    adapter, responses = make([StatusError(503), api_response()])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request(model=MODEL))
    assert len(responses.calls) == 1


def test_client_is_created_lazily_with_key_no_sdk_retries_and_timeout():
    created = []

    def factory(**kw):
        created.append(kw)
        return SimpleNamespace(responses=FakeResponses([api_response()]))

    cfg = app_cfg()
    adapter = OpenAIAdapter(MODEL, cfg, client_factory=factory, api_key="k")
    assert created == []
    adapter.complete(make_request(model=MODEL))
    assert created == [{"api_key": "k", "max_retries": 0, "timeout": cfg.retry.timeout_s}]


def test_client_gets_base_url_when_set():
    created = []

    def factory(**kw):
        created.append(kw)
        return SimpleNamespace()

    adapter = OpenAIAdapter(MODEL, app_cfg(), client_factory=factory, api_key="k")
    adapter.base_url = "https://h.example/v1"
    adapter.get_client()
    assert created[0]["base_url"] == "https://h.example/v1"


def test_openai_adapter_has_no_base_url_by_default():
    assert OpenAIAdapter(MODEL, app_cfg()).base_url is None


def test_client_has_no_base_url_argument_by_default():
    created = []
    adapter = OpenAIAdapter(
        MODEL, app_cfg(), client_factory=lambda **kw: created.append(kw), api_key="k",
    )
    adapter.get_client()
    assert "base_url" not in created[0]


def test_client_is_created_once():
    created = []

    def factory(**kw):
        created.append(kw)
        return SimpleNamespace(responses=FakeResponses([api_response(), api_response()]))

    adapter = OpenAIAdapter(MODEL, app_cfg(), client_factory=factory, api_key="k")
    adapter.complete(make_request(model=MODEL))
    adapter.complete(make_request(model=MODEL))
    assert len(created) == 1


def test_default_client_is_the_openai_sdk(monkeypatch):
    import openai

    created = []
    monkeypatch.setattr(openai, "OpenAI", lambda **kw: created.append(kw) or SimpleNamespace())
    OpenAIAdapter(MODEL, app_cfg(), api_key="k").get_client()
    assert created[0]["api_key"] == "k"
    assert created[0]["max_retries"] == 0


def test_response_round_trips_through_json_into_next_input():
    # Opaque живёт в журнале как dict: после model_dump_json -> model_validate_json items те же
    from ai_dm.llm.types import ChatResponse

    items = [reasoning(), function_call()]
    parsed = result(items)
    restored = ChatResponse.model_validate_json(parsed.model_dump_json())
    history = [
        user("а"),
        Message(role="assistant", content=restored.content),
        Message(role="user", content=[ToolResult(call_id="call_1", content="итог")]),
    ]
    got = sent_input(history)
    assert got[1:3] == [i.dump for i in items]
    assert got[3] == {"type": "function_call_output", "call_id": "call_1", "output": "итог"}


class FakeModelsList:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def list(self, *args, **kwargs):
        self.calls.append((args, kwargs))
        if self.error is not None:
            raise self.error
        return []


def probing(error=None, api_key="k"):
    models = FakeModelsList(error)
    adapter = OpenAIAdapter(
        MODEL, app_cfg(), client_factory=lambda **kw: SimpleNamespace(models=models),
        api_key=api_key,
    )
    return adapter, models


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_fatal_status_error_keeps_status(code):
    adapter, _ = make([StatusError(code)])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.status == code


def test_fatal_error_without_status_code_has_no_status():
    adapter, _ = make([ValueError("странное")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.status is None


def test_probe_lists_models():
    adapter, models = probing()
    adapter.probe()
    assert models.calls == [((), {})]


def test_probe_auth_error_is_fatal_with_status():
    adapter, _ = probing(StatusError(401, "Incorrect API key"))
    with pytest.raises(LlmFatal) as info:
        adapter.probe()
    assert info.value.status == 401


def test_probe_server_error_is_transient():
    adapter, _ = probing(StatusError(503))
    with pytest.raises(LlmTransient):
        adapter.probe()


def test_probe_error_text_has_no_key():
    adapter, _ = probing(StatusError(401, "bad key sk-SECRET-1234"), api_key="sk-SECRET-1234")
    with pytest.raises(LlmFatal) as info:
        adapter.probe()
    assert "sk-SECRET-1234" not in str(info.value)
