# Ожидаемый API: ai_dm.llm.chat_adapter (шаг 184, П1) на фейковом клиенте (сети и SDK нет).
#   ChatCompletionsAdapter(provider, model, app_cfg, *, client_factory=None, api_key=None)
#       -- наследник OpenAIAdapter; base_url берёт из app_cfg.providers[provider];
#       клиент с .chat.completions.create(**kw).
#     info() -> AdapterInfo(provider=<имя хостера>, model).
#     запрос: messages = [system одной записью из склейки req.system через пустую строку, ...];
#       Text -> сообщение роли; ToolCall -> assistant.tool_calls (arguments -- JSON-строка);
#       ToolResult -> {"role": "tool", "tool_call_id", "content"} (ошибка -- {"error": ...}),
#       результаты идут перед текстом игрока; max_tokens; reasoning_effort только при effort;
#       tools -- {"type": "function", "function": {name, description, parameters, strict}};
#       Opaque(<хостер>, {"message": {...}}) -- сообщение уходит как есть вместо Text/ToolCall.
#     ответ: content = [Text, ToolCall..., Opaque(<хостер>, {"message": model_dump})];
#       finish_reason: stop -> end_turn, length -> max_tokens (вызовы не разбираем), content_filter
#       -> refusal (+ stop_detail), иное -> other; вызовы -> tool_use; message.refusal -> refusal.
#     usage: input = prompt_tokens - cached, cache_read = cached, output = completion_tokens.
#     ошибки -- как у OpenAIAdapter; ключ вычищается.
import json
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg, make_request, user

from ai_dm.config.app import ProviderHost
from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.chat_adapter import ChatCompletionsAdapter, parse_call
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.types import (
    ChatResponse,
    Message,
    Opaque,
    SystemBlock,
    Text,
    ToolCall,
    ToolResult,
    ToolSpec,
)

HOST = "openrouter"
MODEL = "deepseek/deepseek-v4-flash"
SECRET = "sk-or-FAKE-0123456789-ZZZ"


class Msg(SimpleNamespace):
    # message ответа: атрибуты как у SDK, model_dump отдаёт заранее заданный dict
    def model_dump(self, **kw):
        self.dump_kwargs = kw
        return dict(self.dump)


def tool_call(call_id="call_1", name="skill_check", arguments='{"skill": "perception"}'):
    return SimpleNamespace(
        id=call_id, type="function", function=SimpleNamespace(name=name, arguments=arguments),
    )


def msg(content="ок", calls=None, refusal=None, dump=None):
    if dump is None:
        dump = {"role": "assistant", "content": content}
        if calls:
            dump["tool_calls"] = [
                {"id": c.id, "type": "function",
                 "function": {"name": c.function.name, "arguments": c.function.arguments}}
                for c in calls
            ]
    return Msg(content=content, tool_calls=calls, refusal=refusal, dump=dump)


def usage_obj(prompt=0, completion=0, cached=None, details=True):
    fields = {} if cached is None else {"cached_tokens": cached}
    return SimpleNamespace(
        prompt_tokens=prompt, completion_tokens=completion,
        prompt_tokens_details=SimpleNamespace(**fields) if details else None,
    )


def api_response(message=None, finish="stop", usage=None, rid="gen-77", model="deepseek-2026"):
    response = SimpleNamespace(
        choices=[SimpleNamespace(message=message or msg(), finish_reason=finish)],
        usage=usage if usage is not None else usage_obj(), model=model,
    )
    response._request_id = rid
    return response


class FakeCompletions:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def create(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


def cfg_with_host(name, base_url):
    cfg = app_cfg()
    cfg.providers[name] = ProviderHost(base_url=base_url, key_env="H_KEY")
    return cfg


def make(results=None, api_key=None):
    completions = FakeCompletions(results if results is not None else [api_response()])
    client = SimpleNamespace(chat=SimpleNamespace(completions=completions))
    adapter = ChatCompletionsAdapter(
        HOST, MODEL, app_cfg(), client_factory=lambda **kw: client, api_key=api_key,
    )
    return adapter, completions


def sent(req=None):
    adapter, completions = make()
    adapter.complete(req or make_request(model=MODEL))
    return completions.calls[0]


def sent_messages(messages, **kw):
    return sent(make_request(model=MODEL, messages=messages, **kw))["messages"]


def result(message=None, **kw):
    adapter, _ = make([api_response(message, **kw)])
    return adapter.complete(make_request(model=MODEL))


def spec(strict=True):
    return ToolSpec(
        name="skill_check", description="проверка", input_schema={"type": "object"}, strict=strict,
    )


def assistant_with_call(text="проверяю"):
    return Message(role="assistant", content=[
        Text(text=text), ToolCall(id="c1", name="skill_check", input={"skill": "perception"}),
    ])


def test_info_names_the_host():
    adapter, _ = make()
    assert adapter.info() == AdapterInfo(provider=HOST, model=MODEL)


def test_info_uses_given_host_name():
    adapter = ChatCompletionsAdapter("myhost", "m", cfg_with_host("myhost", "https://h.example/v1"))
    assert adapter.info() == AdapterInfo(provider="myhost", model="m")


def test_base_url_is_taken_from_host_profile_in_config():
    cfg = cfg_with_host("myhost", "https://h.example/v1")
    assert ChatCompletionsAdapter("myhost", "m", cfg).base_url == "https://h.example/v1"


def test_default_openrouter_base_url_comes_from_config():
    adapter, _ = make()
    assert adapter.base_url == "https://openrouter.ai/api/v1"


def test_unknown_host_name_is_an_error():
    with pytest.raises(KeyError):
        ChatCompletionsAdapter("nohost", "m", app_cfg())


def test_model_is_taken_from_request():
    adapter, completions = make()
    adapter.complete(make_request(model="qwen/qwen3-235b-a22b-2507"))
    assert completions.calls[0]["model"] == "qwen/qwen3-235b-a22b-2507"


def test_max_tokens_from_request():
    assert sent(make_request(model=MODEL, max_tokens=8000))["max_tokens"] == 8000


def test_no_max_completion_tokens_key():
    assert "max_completion_tokens" not in sent()


def test_system_blocks_become_one_system_message():
    system = [SystemBlock(text="правила", cache=True), SystemBlock(text="мир", cache=True)]
    messages = sent(make_request(model=MODEL, system=system))["messages"]
    assert messages[0] == {"role": "system", "content": "правила\n\nмир"}
    assert [m["role"] for m in messages].count("system") == 1


def test_no_system_means_no_system_message():
    messages = sent(make_request(model=MODEL, system=[]))["messages"]
    assert [m["role"] for m in messages] == ["user"]


def test_user_text_becomes_user_message():
    messages = sent_messages([user("осмотрюсь")])
    assert messages[1] == {"role": "user", "content": "осмотрюсь"}


def test_assistant_text_becomes_assistant_message():
    history = [user("а"), Message(role="assistant", content=[Text(text="ответ")]), user("б")]
    assert sent_messages(history)[2] == {"role": "assistant", "content": "ответ"}


def test_assistant_message_without_calls_has_no_tool_calls_key():
    history = [user("а"), Message(role="assistant", content=[Text(text="ответ")])]
    assert "tool_calls" not in sent_messages(history)[2]


def test_tool_call_becomes_tool_calls_with_json_arguments():
    message = sent_messages([user("а"), assistant_with_call()])[2]
    assert message["role"] == "assistant"
    assert message["content"] == "проверяю"
    call = message["tool_calls"][0]
    assert call["id"] == "c1" and call["type"] == "function"
    assert call["function"]["name"] == "skill_check"
    assert json.loads(call["function"]["arguments"]) == {"skill": "perception"}


def test_tool_call_arguments_keep_non_ascii_text():
    call = ToolCall(id="c1", name="say", input={"text": "привет"})
    history = [user("а"), Message(role="assistant", content=[call])]
    arguments = sent_messages(history)[2]["tool_calls"][0]["function"]["arguments"]
    assert "привет" in arguments


def test_assistant_with_only_tool_call_has_null_content():
    call = ToolCall(id="c1", name="say", input={})
    history = [user("а"), Message(role="assistant", content=[call])]
    assert sent_messages(history)[2]["content"] is None


def test_tool_result_becomes_tool_message_with_same_call_id():
    results = Message(role="user", content=[ToolResult(call_id="c1", content='{"ok": true}')])
    got = sent_messages([user("а"), assistant_with_call(), results])[3]
    assert got == {"role": "tool", "tool_call_id": "c1", "content": '{"ok": true}'}


def test_tool_result_error_is_json_with_error_key():
    results = Message(
        role="user", content=[ToolResult(call_id="c1", content="сбой", is_error=True)],
    )
    got = sent_messages([user("а"), assistant_with_call(), results])[3]
    assert json.loads(got["content"]) == {"error": "сбой"}


def test_tool_results_come_before_player_text_in_one_user_turn():
    mixed = Message(role="user", content=[
        Text(text="ещё"), ToolResult(call_id="c1", content="r1"),
        ToolResult(call_id="c2", content="r2"),
    ])
    got = sent_messages([user("а"), assistant_with_call(), mixed])[3:]
    assert [m["role"] for m in got] == ["tool", "tool", "user"]
    assert [m.get("tool_call_id") for m in got[:2]] == ["c1", "c2"]
    assert got[2]["content"] == "ещё"


def test_assistant_text_blocks_are_joined_by_blank_line():
    two = Message(role="assistant", content=[Text(text="раз"), Text(text="два")])
    assert sent_messages([user("а"), two])[2]["content"] == "раз\n\nдва"


def test_user_text_blocks_are_joined_by_blank_line():
    two = Message(role="user", content=[Text(text="раз"), Text(text="два")])
    assert sent_messages([two])[1]["content"] == "раз\n\nдва"


def test_tool_result_error_keeps_non_ascii_text():
    results = Message(
        role="user", content=[ToolResult(call_id="c1", content="сбой", is_error=True)],
    )
    got = sent_messages([user("а"), assistant_with_call(), results])[3]
    assert "сбой" in got["content"]


def test_tool_result_only_message_has_no_user_message():
    results = Message(role="user", content=[ToolResult(call_id="c1", content="r")])
    got = sent_messages([user("а"), assistant_with_call(), results])
    assert [m["role"] for m in got] == ["system", "user", "assistant", "tool"]


def test_tool_becomes_function_spec():
    tools = sent(make_request(model=MODEL, tools=[spec()]))["tools"]
    assert tools == [{
        "type": "function",
        "function": {
            "name": "skill_check", "description": "проверка",
            "parameters": {"type": "object"}, "strict": True,
        },
    }]


def test_non_strict_tool_goes_with_strict_false():
    tools = sent(make_request(model=MODEL, tools=[spec(strict=False)]))["tools"]
    assert tools[0]["function"]["strict"] is False


def test_strict_tools_off_in_config_makes_every_tool_non_strict():
    adapter, completions = make()
    adapter.cfg.llm.strict_tools = False
    adapter.complete(make_request(model=MODEL, tools=[spec()]))
    assert completions.calls[0]["tools"][0]["function"]["strict"] is False


def test_tools_keep_order():
    second = ToolSpec(name="b", description="d", input_schema={})
    first = ToolSpec(name="a", description="d", input_schema={})
    tools = sent(make_request(model=MODEL, tools=[first, second]))["tools"]
    assert [t["function"]["name"] for t in tools] == ["a", "b"]


def test_request_without_tools_has_no_tools_key():
    assert "tools" not in sent()


def test_effort_goes_as_reasoning_effort():
    assert sent(make_request(model=MODEL, effort="medium"))["reasoning_effort"] == "medium"


def test_no_effort_means_no_reasoning_effort():
    assert "reasoning_effort" not in sent(make_request(model=MODEL, effort=None))


def test_opaque_message_replaces_text_and_tool_call_of_that_message():
    raw = {"role": "assistant", "content": "x", "reasoning": "думаю",
           "tool_calls": [{"id": "c1", "type": "function",
                           "function": {"name": "skill_check", "arguments": "{}"}}]}
    assistant = Message(role="assistant", content=[
        Text(text="x"), ToolCall(id="c1", name="skill_check", input={}),
        Opaque(provider=HOST, raw={"message": raw}),
    ])
    got = sent_messages([user("а"), assistant])
    assert got[2:] == [raw]


def test_opaque_message_is_passed_unchanged():
    raw = {"role": "assistant", "content": "x", "reasoning_details": [{"type": "r", "data": "Z"}]}
    assistant = Message(role="assistant", content=[Opaque(provider=HOST, raw={"message": raw})])
    got = sent_messages([user("а"), assistant])[2]
    assert json.dumps(got, sort_keys=True) == json.dumps(raw, sort_keys=True)


def test_foreign_opaque_is_skipped_and_text_is_used():
    assistant = Message(role="assistant", content=[
        Text(text="x"), Opaque(provider="openai", raw={"items": [{"type": "reasoning"}]}),
    ])
    got = sent_messages([user("а"), assistant])[2]
    assert got == {"role": "assistant", "content": "x"}


def test_opaque_of_another_host_is_skipped():
    assistant = Message(role="assistant", content=[
        Text(text="x"), Opaque(provider="myhost", raw={"message": {"role": "assistant"}}),
    ])
    assert sent_messages([user("а"), assistant])[2] == {"role": "assistant", "content": "x"}


def test_text_response_to_text_block():
    assert result(msg("ответ")).content[0] == Text(text="ответ")


def test_text_response_is_end_turn_without_detail():
    response = result()
    assert (response.stop_reason, response.stop_detail) == ("end_turn", None)


def test_response_ends_with_opaque_of_the_host_with_dumped_message():
    dump = {"role": "assistant", "content": "ок", "reasoning": "думал"}
    last = result(msg("ок", dump=dump)).content[-1]
    assert last == Opaque(provider=HOST, raw={"message": dump})


def test_message_is_dumped_in_json_mode_without_none_fields():
    message = msg("ок")
    result(message)
    assert message.dump_kwargs == {"mode": "json", "exclude_none": True}


def test_tool_call_becomes_tool_call_block():
    response = result(msg(None, [tool_call()]), finish="tool_calls")
    expected = ToolCall(id="call_1", name="skill_check", input={"skill": "perception"})
    assert response.content[0] == expected


def test_two_calls_keep_order():
    calls = [tool_call("c1", "a", "{}"), tool_call("c2", "b", "{}")]
    response = result(msg(None, calls), finish="tool_calls")
    assert [b.id for b in response.content if isinstance(b, ToolCall)] == ["c1", "c2"]


def test_text_with_call_order_is_text_calls_opaque():
    response = result(msg("смотрю", [tool_call()]), finish="tool_calls")
    assert [type(b) for b in response.content] == [Text, ToolCall, Opaque]


def test_empty_content_gives_no_text_block():
    response = result(msg("", None))
    assert [type(b) for b in response.content] == [Opaque]


def test_calls_give_tool_use():
    response = result(msg(None, [tool_call()]), finish="tool_calls")
    assert (response.stop_reason, response.stop_detail) == ("tool_use", None)


def test_tool_use_wins_over_finish_reason_stop():
    assert result(msg(None, [tool_call()]), finish="stop").stop_reason == "tool_use"


def test_length_is_max_tokens_without_detail():
    response = result(finish="length")
    assert (response.stop_reason, response.stop_detail) == ("max_tokens", None)


def test_content_filter_is_refusal_with_detail():
    response = result(finish="content_filter")
    assert (response.stop_reason, response.stop_detail) == ("refusal", "content_filter")


@pytest.mark.parametrize("finish", ["error", "weird", None])
def test_other_finish_reasons_are_other(finish):
    assert result(finish=finish).stop_reason == "other"


def test_other_finish_reason_is_kept_in_detail():
    assert result(finish="error").stop_detail == "error"


def test_refusal_text_is_refusal_with_detail():
    response = result(msg(None, refusal="не буду"))
    assert (response.stop_reason, response.stop_detail) == ("refusal", "не буду")


def test_refusal_wins_over_finish_reason_stop():
    assert result(msg("текст", refusal="нет"), finish="stop").stop_reason == "refusal"


def test_cut_call_with_broken_json_is_max_tokens_not_fatal():
    response = result(msg(None, [tool_call(arguments='{"skill": "perc')]), finish="length")
    assert response.stop_reason == "max_tokens"


def test_cut_call_gives_no_tool_call():
    response = result(msg("текст", [tool_call(arguments='{"skill"')]), finish="length")
    assert not [b for b in response.content if isinstance(b, ToolCall)]


def test_cut_call_with_valid_json_is_still_no_tool_call():
    response = result(msg(None, [tool_call()]), finish="length")
    assert not [b for b in response.content if isinstance(b, ToolCall)]
    assert response.stop_reason == "max_tokens"


def test_cut_response_keeps_text_and_opaque():
    response = result(msg("начало", [tool_call(arguments="{")]), finish="length")
    assert [type(b) for b in response.content] == [Text, Opaque]


def test_broken_json_in_completed_response_is_fatal():
    with pytest.raises(LlmFatal, match="не JSON"):
        result(msg(None, [tool_call(arguments="{oops")]), finish="tool_calls")


def test_parse_call_reads_json_arguments():
    got = parse_call(tool_call("c9", "n", '{"a": 1}'))
    assert got == ToolCall(id="c9", name="n", input={"a": 1})


def test_parse_call_broken_json_message_is_exact():
    with pytest.raises(LlmFatal, match=r"^аргументы вызова не JSON$"):
        parse_call(tool_call(arguments="{"))


def test_parse_call_broken_json_is_fatal_not_transient():
    with pytest.raises(LlmFatal) as info:
        parse_call(tool_call(arguments="{"))
    assert not isinstance(info.value, LlmTransient)


def test_usage_subtracts_cached_from_prompt_tokens():
    usage = result(usage=usage_obj(100, 30, cached=40)).usage
    assert (usage.input, usage.output, usage.cache_read) == (60, 30, 40)


def test_usage_has_no_cache_write():
    usage = result(usage=usage_obj(100, 30, cached=40)).usage
    assert (usage.cache_write, usage.cache_write_1h) == (0, 0)


def test_usage_without_details_is_all_input():
    usage = result(usage=usage_obj(100, 30, details=False)).usage
    assert (usage.input, usage.cache_read) == (100, 0)


def test_usage_details_without_cached_tokens_is_all_input():
    usage = result(usage=usage_obj(100, 30)).usage
    assert (usage.input, usage.cache_read) == (100, 0)


def test_usage_with_none_cached_tokens_is_all_input():
    usage = result(usage=usage_obj(100, 30, cached=None, details=True)).usage
    assert usage.input == 100


def test_usage_with_none_counts_is_zero():
    usage = result(usage=usage_obj(None, None, details=False)).usage
    assert (usage.input, usage.output) == (0, 0)


def test_missing_usage_is_zero():
    response = api_response()
    response.usage = None
    adapter, _ = make([response])
    usage = adapter.complete(make_request(model=MODEL)).usage
    assert (usage.input, usage.output, usage.cache_read) == (0, 0, 0)


def test_request_id_from_private_attribute():
    assert result(rid="gen-5").request_id == "gen-5"


def test_missing_request_id_attribute_gives_none():
    response = api_response()
    del response._request_id
    adapter, _ = make([response])
    assert adapter.complete(make_request(model=MODEL)).request_id is None


def test_response_model_is_taken_from_response():
    assert result(model="deepseek-2026").model == "deepseek-2026"


def test_response_model_falls_back_to_requested_model():
    assert result(model=None).model == MODEL


class StatusError(Exception):
    def __init__(self, code, message="ошибка", headers=None):
        super().__init__(message)
        self.status_code = code
        self.response = SimpleNamespace(headers=headers or {})


class APIConnectionError(Exception):
    pass


class APITimeoutError(APIConnectionError):
    pass


@pytest.mark.parametrize("code", [408, 429, 500, 503])
def test_status_errors_that_are_transient(code):
    adapter, _ = make([StatusError(code)])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request(model=MODEL))


@pytest.mark.parametrize("code", [400, 401, 402, 403, 404])
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


def test_connection_error_is_transient_not_timeout():
    adapter, _ = make([APIConnectionError("сеть")])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is False


def test_timeout_error_is_transient_timeout():
    adapter, _ = make([APITimeoutError("долго")])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.timeout is True


def test_unknown_exception_is_fatal():
    adapter, _ = make([RuntimeError("странное")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert not isinstance(info.value, LlmTransient)


def test_error_message_is_kept_and_original_is_cause():
    error = StatusError(400, "неверная схема")
    adapter, _ = make([error])
    with pytest.raises(LlmFatal, match="неверная схема") as info:
        adapter.complete(make_request(model=MODEL))
    assert info.value.__cause__ is error


def test_error_message_does_not_leak_the_api_key():
    adapter, _ = make([StatusError(401, f"Incorrect API key: {SECRET}")], api_key=SECRET)
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request(model=MODEL))
    assert SECRET not in str(info.value)
    assert "***" in str(info.value)


def test_adapter_makes_one_call_per_complete():
    adapter, completions = make([StatusError(503), api_response()])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request(model=MODEL))
    assert len(completions.calls) == 1


def test_client_is_created_lazily_with_key_url_no_sdk_retries_and_timeout():
    created = []

    def factory(**kw):
        created.append(kw)
        return SimpleNamespace(chat=SimpleNamespace(completions=FakeCompletions([api_response()])))

    cfg = cfg_with_host("myhost", "https://h.example/v1")
    adapter = ChatCompletionsAdapter("myhost", MODEL, cfg, client_factory=factory, api_key="k")
    assert created == []
    adapter.complete(make_request(model=MODEL))
    assert created == [{
        "api_key": "k", "max_retries": 0, "timeout": cfg.retry.timeout_s,
        "base_url": "https://h.example/v1",
    }]


def test_two_turn_tool_flow_returns_opaque_message_unchanged():
    # ход с инструментом: ответ с вызовом и reasoning -> результат -> второй запрос
    dump = {
        "role": "assistant", "content": None, "reasoning": "надо проверить",
        "reasoning_details": [{"type": "reasoning.text", "text": "т"}],
        "tool_calls": [{
            "id": "call_1", "type": "function",
            "function": {"name": "skill_check", "arguments": '{"skill": "perception"}'},
        }],
    }
    first = api_response(msg(None, [tool_call()], dump=dump), finish="tool_calls")
    adapter, completions = make([first, api_response(msg("итог"))])
    response = adapter.complete(make_request(model=MODEL))
    restored = ChatResponse.model_validate_json(response.model_dump_json())
    history = [
        user("а"),
        Message(role="assistant", content=restored.content),
        Message(role="user", content=[ToolResult(call_id="call_1", content="успех")]),
    ]
    final = adapter.complete(make_request(model=MODEL, messages=history))
    second = completions.calls[1]["messages"]
    assert second[2] == dump
    assert second[3] == {"role": "tool", "tool_call_id": "call_1", "content": "успех"}
    assert final.content[0] == Text(text="итог")
