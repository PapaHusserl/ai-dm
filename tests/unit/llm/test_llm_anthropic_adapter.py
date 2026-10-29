# Ожидаемый API: ai_dm.llm.anthropic_adapter.AnthropicAdapter -- контракт в llm_kit.py, на
# фейковом клиенте (сети нет, SDK не нужен).
#   AnthropicAdapter(model, app_cfg, *, client_factory=None, api_key=None)
#     клиент создаётся вызовом client_factory(**kwargs) с max_retries=0 (повторы -- наши, 2.2),
#     api_key=<ключ> среди kwargs; по умолчанию фабрика -- anthropic.Anthropic (импорт лениво).
#     complete(req) -> client.messages.create(**kwargs) (или client.beta.messages.create при
#     llm.refusal_fallback=true), kwargs:
#       model, max_tokens,
#       system=[{"type":"text","text":.., "cache_control": {"type":"ephemeral"} если cache}],
#       tools=[{"name","description","input_schema","strict"}] как ToolSpec.model_dump(),
#       messages=[{"role","content":[блоки API]}], output_config={"effort":..} если effort задан;
#       без thinking, без tool_choice (допустим только {"type":"auto"}), без префилла.
#     блоки: Text -> {"type":"text","text"}; ToolCall -> {"type":"tool_use","id","name","input"};
#       ToolResult -> {"type":"tool_result","tool_use_id","content",["is_error": True]};
#       Opaque(provider="anthropic") -> raw как есть.
#     ответ: text -> Text, tool_use -> ToolCall, прочие блоки (thinking, redacted_thinking) ->
#       Opaque("anthropic", block.model_dump()), порядок сохраняется; stop_reason: end_turn,
#       tool_use, max_tokens, refusal как есть, прочее (pause_turn, stop_sequence) -> "other";
#       usage: input_tokens, output_tokens, cache_creation_input_tokens -> cache_write,
#       cache_read_input_tokens (None -> 0); request_id = response._request_id.
#     ошибки по status_code: 429, >= 500 (в т.ч. 529) -> LlmTransient (retry_after из заголовка
#       response.headers["retry-after"], целые секунды, иначе None); прочие 4xx -> LlmFatal;
#       без status_code, класс (или предок) называется APIConnectionError / APITimeoutError ->
#       LlmTransient. В тексте ошибок ключ api_key вычищается (redact).
#     fallback: при llm.refusal_fallback=true в kwargs betas=["server-side-fallback-2026-07-01"]
#       и fallbacks="default"; при false ни betas, ни fallbacks.
#     info() -> AdapterInfo("anthropic", model)
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg, make_request, user

from ai_dm.config.app import load_settings
from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.errors import LlmFatal, LlmTransient
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
from ai_dm.protocol.schema import tool_set

MODEL = "claude-opus-5-5"
SECRET = "sk-ant-FAKE-0123456789-ZZZ"


class Block(SimpleNamespace):
    def model_dump(self, **kwargs):
        return dict(self.__dict__)


class APIConnectionError(Exception):
    pass


class APITimeoutError(APIConnectionError):
    pass


class StatusError(Exception):
    def __init__(self, status, message="ошибка", headers=None):
        super().__init__(message)
        self.status_code = status
        self.response = SimpleNamespace(headers=headers or {})


def api_usage(**kw):
    base = dict(
        input_tokens=0, output_tokens=0, cache_creation_input_tokens=0, cache_read_input_tokens=0,
    )
    return SimpleNamespace(**{**base, **kw})


def api_response(
    content=None, stop_reason="end_turn", usage=None, request_id="req_abc", model=None,
):
    return SimpleNamespace(
        model=model,
        content=content if content is not None else [Block(type="text", text="ответ")],
        stop_reason=stop_reason,
        usage=usage or api_usage(),
        _request_id=request_id,
    )


class FakeMessages:
    def __init__(self, client):
        self.client = client

    def create(self, **kwargs):
        self.client.calls.append(kwargs)
        result = self.client.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result



class FakeClient:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []
        self.messages = FakeMessages(self)
        self.beta = SimpleNamespace(messages=FakeMessages(self))


def make(results=None, cfg=None, api_key=None):
    client = FakeClient(results if results is not None else [api_response()])
    factory_calls = []

    def factory(**kwargs):
        factory_calls.append(kwargs)
        return client

    adapter = AnthropicAdapter(
        MODEL, cfg or app_cfg(), client_factory=factory, api_key=api_key
    )
    return adapter, client, factory_calls


def tools_req(mode="combat_classify", **kw):
    tools = [ToolSpec.model_validate(t) for t in tool_set(mode)]
    return make_request(tools=tools, effort="medium", **kw)


def sent(req=None, cfg=None):
    adapter, client, _ = make(cfg=cfg)
    adapter.complete(req or tools_req())
    return client.calls[0]


def test_client_is_created_with_max_retries_zero():
    adapter, _, factory_calls = make()
    adapter.complete(make_request())
    assert factory_calls[0]["max_retries"] == 0


def test_api_key_goes_to_client_factory():
    adapter, _, factory_calls = make(api_key=SECRET)
    adapter.complete(make_request())
    assert factory_calls[0]["api_key"] == SECRET


def test_info_names_anthropic():
    adapter, _, _ = make()
    assert adapter.info() == AdapterInfo(provider="anthropic", model=MODEL)


def test_model_and_max_tokens_are_sent():
    kwargs = sent(tools_req())
    assert (kwargs["model"], kwargs["max_tokens"]) == (MODEL, 8000)


def test_tools_are_sent_with_strict_as_in_definitions():
    kwargs = sent(tools_req("combat_classify"))
    assert kwargs["tools"] == tool_set("combat_classify")
    assert all(t["strict"] is True for t in kwargs["tools"])


def test_non_strict_tool_stays_non_strict():
    kwargs = sent(tools_req("explore"))
    by_name = {t["name"]: t for t in kwargs["tools"]}
    assert by_name["end_chapter"]["strict"] is False
    assert by_name["skill_check"]["strict"] is True


def test_tool_choice_is_not_forced():
    kwargs = sent()
    assert kwargs.get("tool_choice") in (None, {"type": "auto"})


def test_no_prefill_last_message_is_not_assistant():
    kwargs = sent(tools_req())
    assert kwargs["messages"][-1]["role"] == "user"


def test_thinking_is_not_sent_for_other_roles():
    for role in ("world", "summarizer", "import"):
        assert "thinking" not in sent(make_request(role=role))


def test_narrator_thinking_adaptive_summarized_by_default():
    assert sent()["thinking"] == {"type": "adaptive", "display": "summarized"}


def test_narrator_thinking_adaptive_omitted():
    cfg = load_settings('[llm]\nthinking_display = "omitted"\n').app
    assert sent(cfg=cfg)["thinking"] == {"type": "adaptive", "display": "omitted"}


def test_haiku_4_narrator_gets_no_thinking():
    req = make_request(model="claude-haiku-4-5")
    assert "thinking" not in sent(req)
    adapter, _, _ = make()
    assert adapter.thinking_of(req) is None


def test_other_models_narrator_keeps_thinking():
    req = make_request(model="claude-sonnet-5-5")
    assert sent(req)["thinking"] == {"type": "adaptive", "display": "summarized"}


def test_no_narrator_key_sends_no_thinking():
    cfg = app_cfg()
    cfg.llm.thinking = {}
    assert "thinking" not in sent(cfg=cfg)


def test_thinking_goes_to_beta_path_too():
    cfg = load_settings("[llm]\nrefusal_fallback = true\n").app
    adapter, client, _ = make(cfg=cfg)
    adapter.complete(make_request())
    assert client.calls[0]["thinking"] == {"type": "adaptive", "display": "summarized"}
    assert client.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]


def test_thinking_of_by_role():
    adapter, _, _ = make()
    assert adapter.thinking_of(make_request(role="narrator")) == {
        "type": "adaptive", "display": "summarized",
    }
    assert adapter.thinking_of(make_request(role="world")) is None


def test_thinking_block_with_signature_goes_back_unchanged_next_round():
    raw = {"type": "thinking", "thinking": "", "signature": "sig=="}
    block = Block(type="thinking", thinking="", signature="sig==")
    adapter, client, _ = make([api_response([block, Block(type="text", text="т")])])
    response = adapter.complete(make_request())
    follow = make_request(
        messages=[user("привет"), Message(role="assistant", content=response.content)]
    )
    adapter.client.results.append(api_response())
    adapter.complete(follow)
    assert client.calls[1]["messages"][1]["content"][0] == raw


def test_effort_goes_to_output_config():
    kwargs = sent(tools_req())
    assert kwargs["output_config"] == {"effort": "medium"}


def test_effort_comes_from_the_request_role():
    kwargs = sent(make_request(effort="high"))
    assert kwargs["output_config"] == {"effort": "high"}


def test_no_effort_means_no_output_config():
    kwargs = sent(make_request())
    assert "output_config" not in kwargs


CACHE_1H = {"type": "ephemeral", "ttl": "1h"}
CACHE_5M = {"type": "ephemeral", "ttl": "5m"}


def test_cache_control_only_on_marked_system_blocks():
    system = [
        SystemBlock(text="правила", cache=True),
        SystemBlock(text="мир", cache=True),
        SystemBlock(text="без кэша", cache=False),
    ]
    kwargs = sent(make_request(system=system))
    assert kwargs["system"] == [
        {"type": "text", "text": "правила", "cache_control": CACHE_1H},
        {"type": "text", "text": "мир", "cache_control": CACHE_1H},
        {"type": "text", "text": "без кэша"},
    ]


def test_message_cache_gets_5m_ttl_on_last_block():
    blocks = [Text(text="a"), Text(text="состояние хода")]
    message = Message(role="user", content=blocks, cache=True)
    kwargs = sent(make_request(messages=[message]))
    content = kwargs["messages"][0]["content"]
    assert content[0] == {"type": "text", "text": "a"}
    assert content[-1] == {
        "type": "text", "text": "состояние хода", "cache_control": CACHE_5M,
    }


def test_message_cache_ttl_is_5m_even_when_system_is_1h():
    system = [SystemBlock(text="правила", cache=True)]
    message = Message(role="user", content=[Text(text="ход")], cache=True)
    kwargs = sent(make_request(system=system, messages=[message]))
    assert kwargs["system"][0]["cache_control"] == CACHE_1H
    assert kwargs["messages"][0]["content"][-1]["cache_control"] == CACHE_5M


def test_message_without_cache_has_no_cache_control():
    kwargs = sent(make_request(messages=[Message(role="user", content=[Text(text="x")])]))
    assert "cache_control" not in kwargs["messages"][0]["content"][-1]


def test_user_text_message_is_converted():
    kwargs = sent(make_request("осмотрюсь"))
    assert kwargs["messages"] == [
        {"role": "user", "content": [{"type": "text", "text": "осмотрюсь"}]},
    ]


def test_tool_call_and_result_are_converted():
    req = make_request(messages=[
        user("убеждаю"),
        Message(role="assistant", content=[
            Text(text="бросаю"),
            ToolCall(id="toolu_1", name="skill_check", input={"skill": "persuasion"}),
        ]),
        Message(role="user", content=[
            ToolResult(call_id="toolu_1", content='{"total": 17}'),
        ]),
    ])
    messages = sent(req)["messages"]
    assert messages[1]["content"] == [
        {"type": "text", "text": "бросаю"},
        {"type": "tool_use", "id": "toolu_1", "name": "skill_check",
         "input": {"skill": "persuasion"}},
    ]
    assert messages[2]["content"] == [
        {"type": "tool_result", "tool_use_id": "toolu_1", "content": '{"total": 17}'},
    ]


def test_tool_result_error_flag_is_sent():
    req = make_request(messages=[
        user("x"),
        Message(role="assistant", content=[ToolCall(id="t1", name="a", input={})]),
        Message(role="user", content=[ToolResult(call_id="t1", content="плохо", is_error=True)]),
    ])
    assert sent(req)["messages"][2]["content"][0]["is_error"] is True


def test_all_tool_results_go_in_one_user_message():
    req = make_request(messages=[
        user("x"),
        Message(role="assistant", content=[
            ToolCall(id="t1", name="a", input={}), ToolCall(id="t2", name="b", input={}),
        ]),
        Message(role="user", content=[
            ToolResult(call_id="t1", content="1"), ToolResult(call_id="t2", content="2"),
        ]),
    ])
    messages = sent(req)["messages"]
    assert len(messages) == 3
    assert [b["tool_use_id"] for b in messages[2]["content"]] == ["t1", "t2"]


def test_opaque_block_goes_back_unchanged():
    raw = {"type": "thinking", "thinking": "думаю", "signature": "sig=="}
    req = make_request(messages=[
        user("x"),
        Message(role="assistant", content=[
            Opaque(provider="anthropic", raw=raw), Text(text="ответ"),
        ]),
        user("дальше"),
    ])
    assert sent(req)["messages"][1]["content"][0] == raw


def test_text_response_to_text_block():
    adapter, _, _ = make([api_response([Block(type="text", text="Привет")])])
    assert adapter.complete(make_request()).content == [Text(text="Привет")]


def test_tool_use_response_to_tool_call():
    block = Block(type="tool_use", id="toolu_9", name="skill_check", input={"skill": "stealth"})
    adapter, _, _ = make([api_response([block], stop_reason="tool_use")])
    resp = adapter.complete(make_request())
    assert resp.content == [ToolCall(id="toolu_9", name="skill_check", input={"skill": "stealth"})]
    assert resp.stop_reason == "tool_use"


def test_thinking_response_to_opaque_in_order():
    thinking = Block(type="thinking", thinking="думаю", signature="sig==")
    text = Block(type="text", text="ответ")
    adapter, _, _ = make([api_response([thinking, text])])
    content = adapter.complete(make_request()).content
    assert content == [
        Opaque(provider="anthropic", raw={"type": "thinking", "thinking": "думаю",
                                          "signature": "sig=="}),
        Text(text="ответ"),
    ]


def test_redacted_thinking_to_opaque():
    block = Block(type="redacted_thinking", data="zzz")
    adapter, _, _ = make([api_response([block])])
    assert adapter.complete(make_request()).content == [
        Opaque(provider="anthropic", raw={"type": "redacted_thinking", "data": "zzz"}),
    ]


def test_usage_fields_are_mapped():
    # запись кэша SDK делится на ephemeral_5m_input_tokens и ephemeral_1h_input_tokens
    creation = SimpleNamespace(ephemeral_5m_input_tokens=30, ephemeral_1h_input_tokens=3)
    usage = api_usage(
        input_tokens=11, output_tokens=22, cache_creation_input_tokens=33,
        cache_creation=creation, cache_read_input_tokens=44,
    )
    adapter, _, _ = make([api_response(usage=usage)])
    assert adapter.complete(make_request()).usage == Usage(
        input=11, output=22, cache_write=30, cache_write_1h=3, cache_read=44,
    )


def test_usage_cache_creation_only_5m():
    creation = SimpleNamespace(ephemeral_5m_input_tokens=50, ephemeral_1h_input_tokens=0)
    usage = api_usage(cache_creation_input_tokens=50, cache_creation=creation)
    adapter, _, _ = make([api_response(usage=usage)])
    result = adapter.complete(make_request()).usage
    assert (result.cache_write, result.cache_write_1h) == (50, 0)


def test_usage_cache_creation_only_1h():
    creation = SimpleNamespace(ephemeral_5m_input_tokens=0, ephemeral_1h_input_tokens=70)
    usage = api_usage(cache_creation_input_tokens=70, cache_creation=creation)
    adapter, _, _ = make([api_response(usage=usage)])
    result = adapter.complete(make_request()).usage
    assert (result.cache_write, result.cache_write_1h) == (0, 70)


def test_usage_none_cache_fields_become_zero():
    usage = api_usage(
        input_tokens=5, output_tokens=6, cache_creation_input_tokens=None,
        cache_read_input_tokens=None,
    )
    adapter, _, _ = make([api_response(usage=usage)])
    assert adapter.complete(make_request()).usage == Usage(input=5, output=6)


def test_request_id_is_passed_through():
    adapter, _, _ = make([api_response(request_id="req_XYZ")])
    assert adapter.complete(make_request()).request_id == "req_XYZ"


@pytest.mark.parametrize("reason", ["end_turn", "tool_use", "max_tokens", "refusal"])
def test_stop_reason_passes_through(reason):
    adapter, _, _ = make([api_response(stop_reason=reason)])
    assert adapter.complete(make_request()).stop_reason == reason


@pytest.mark.parametrize("reason", ["pause_turn", "stop_sequence"])
def test_other_stop_reasons_become_other(reason):
    adapter, _, _ = make([api_response(stop_reason=reason)])
    assert adapter.complete(make_request()).stop_reason == "other"


def test_refusal_is_a_response_not_an_exception():
    adapter, _, _ = make([api_response([Block(type="text", text="не могу")], "refusal")])
    resp = adapter.complete(make_request())
    assert (resp.stop_reason, resp.content) == ("refusal", [Text(text="не могу")])


def test_refusal_with_empty_content_is_still_a_response():
    adapter, _, _ = make([api_response([], "refusal")])
    resp = adapter.complete(make_request())
    assert (resp.stop_reason, resp.content) == ("refusal", [])


def test_max_tokens_is_a_response_not_an_exception():
    adapter, _, _ = make([api_response([Block(type="text", text="обор")], "max_tokens")])
    assert adapter.complete(make_request()).stop_reason == "max_tokens"


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 529])
def test_status_errors_that_are_transient(status):
    adapter, _, _ = make([StatusError(status)])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())


@pytest.mark.parametrize("status", [400, 401, 403, 404])
def test_status_errors_that_are_fatal(status):
    adapter, _, _ = make([StatusError(status)])
    with pytest.raises(LlmFatal):
        adapter.complete(make_request())


def test_error_without_status_code_is_fatal_and_keeps_message():
    adapter, _, _ = make([ValueError("странное")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request())
    assert str(info.value) == "странное"


def test_fatal_is_not_transient():
    adapter, _, _ = make([StatusError(400)])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request())
    assert not isinstance(info.value, LlmTransient)


def test_rate_limit_retry_after_is_passed():
    adapter, _, _ = make([StatusError(429, headers={"retry-after": "7"})])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.retry_after == 7


def retry_after_for(headers):
    adapter, _, _ = make([StatusError(429, headers=headers)])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    return info.value.retry_after


def test_retry_after_may_be_fractional_seconds():
    assert retry_after_for({"retry-after": "1.5"}) == 1.5


def test_retry_after_ms_is_converted_to_seconds():
    assert retry_after_for({"retry-after-ms": "1500"}) == 1.5


def test_retry_after_ms_wins_over_retry_after():
    assert retry_after_for({"retry-after-ms": "250", "retry-after": "7"}) == 0.25


def test_retry_after_garbage_is_none():
    assert retry_after_for({"retry-after": "скоро"}) is None


def test_request_timeout_408_is_transient_without_retry_after():
    adapter, _, _ = make([StatusError(408)])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.retry_after is None


def test_transient_without_retry_after_header():
    adapter, _, _ = make([StatusError(529)])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert info.value.retry_after is None


def test_connection_error_is_transient():
    adapter, _, _ = make([APIConnectionError("сеть")])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())


def test_timeout_is_transient():
    adapter, _, _ = make([APITimeoutError("долго")])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())


def test_unknown_exception_without_status_is_fatal():
    adapter, _, _ = make([RuntimeError("что-то странное")])
    with pytest.raises(LlmFatal):
        adapter.complete(make_request())


def test_error_message_keeps_the_original_text():
    adapter, _, _ = make([StatusError(400, "messages.0: плохая схема")])
    with pytest.raises(LlmFatal, match="плохая схема"):
        adapter.complete(make_request())


def test_error_message_does_not_leak_the_api_key():
    message = f"invalid x-api-key: {SECRET}"
    adapter, _, _ = make([StatusError(401, message)], api_key=SECRET)
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request())
    assert SECRET not in str(info.value)


def test_transient_message_does_not_leak_the_api_key():
    adapter, _, _ = make([StatusError(500, f"сбой для {SECRET}")], api_key=SECRET)
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    assert SECRET not in str(info.value)


def test_adapter_makes_one_call_per_complete_no_own_retries():
    adapter, client, _ = make([StatusError(500), api_response()])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())
    assert len(client.calls) == 1


def test_fallback_disabled_by_default_sends_no_fallbacks_or_betas():
    adapter, client, _ = make()
    adapter.complete(make_request())
    assert app_cfg().llm.refusal_fallback is False
    assert "fallbacks" not in client.calls[0]
    assert "betas" not in client.calls[0]


def test_fallback_enabled_sends_beta_and_fallbacks():
    cfg = load_settings("[llm]\nrefusal_fallback = true\n").app
    adapter, client, _ = make(cfg=cfg)
    adapter.complete(make_request())
    assert client.calls[0]["fallbacks"] == "default"
    assert client.calls[0]["betas"] == ["server-side-fallback-2026-07-01"]


def test_strict_tools_false_sends_every_tool_non_strict():
    cfg = load_settings("[llm]\nstrict_tools = false\n").app
    kwargs = sent(tools_req("explore"), cfg=cfg)
    assert len(kwargs["tools"]) == len(tool_set("explore"))
    assert all(t["strict"] is False for t in kwargs["tools"])


def test_strict_tools_false_keeps_other_tool_fields():
    cfg = load_settings("[llm]\nstrict_tools = false\n").app
    kwargs = sent(tools_req("combat_classify"), cfg=cfg)
    expected = [{**t, "strict": False} for t in tool_set("combat_classify")]
    assert kwargs["tools"] == expected


def test_strict_tools_true_takes_strict_from_definition():
    assert app_cfg().llm.strict_tools is True
    by_name = {t["name"]: t for t in sent(tools_req("explore"))["tools"]}
    assert by_name["end_chapter"]["strict"] is False
    assert by_name["skill_check"]["strict"] is True


def test_response_model_is_the_actual_model_from_api():
    adapter, _, _ = make([api_response(model="claude-opus-5-5-20261001")])
    assert adapter.complete(make_request()).model == "claude-opus-5-5-20261001"


def test_response_model_falls_back_to_requested_model():
    adapter, _, _ = make([api_response(model=None)])
    assert adapter.complete(make_request()).model == MODEL


def test_model_is_taken_from_request_not_from_adapter():
    adapter, client, _ = make()
    adapter.complete(make_request(model="claude-haiku-4-5"))
    assert client.calls[0]["model"] == "claude-haiku-4-5"


def test_info_keeps_adapter_model_whatever_the_request():
    adapter, _, _ = make()
    adapter.complete(make_request(model="claude-haiku-4-5"))
    assert adapter.info().model == MODEL


class RemoteProtocolError(Exception):
    pass


class ReadError(Exception):
    pass


class WriteError(Exception):
    pass


class TransportError(Exception):
    pass


@pytest.mark.parametrize("exc_class", [RemoteProtocolError, ReadError, WriteError, TransportError])
def test_more_network_errors_without_status_are_transient(exc_class):
    adapter, _, _ = make([exc_class("сеть")])
    with pytest.raises(LlmTransient):
        adapter.complete(make_request())


def test_cache_ttl_of_system_blocks_is_one_hour_by_default():
    kwargs = sent(make_request(system=[SystemBlock(text="правила", cache=True)]))
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "1h"}


def test_cache_ttl_comes_from_llm_cache_ttl_config():
    cfg = app_cfg().model_copy(update={"llm": app_cfg().llm.model_copy(update={"cache_ttl": "5m"})})
    kwargs = sent(make_request(system=[SystemBlock(text="правила", cache=True)]), cfg=cfg)
    assert kwargs["system"][0]["cache_control"] == {"type": "ephemeral", "ttl": "5m"}


def test_message_blocks_have_no_cache_control():
    kwargs = sent(make_request("осмотрюсь"))
    for message in kwargs["messages"]:
        assert all("cache_control" not in block for block in message["content"])


def memory_system():
    return [
        SystemBlock(text="правила", cache=True),
        SystemBlock(text="мир", cache=True),
        SystemBlock(text="память", cache=True, stable=False),
    ]


def test_unstable_system_block_gets_5m_ttl():
    kwargs = sent(make_request(system=memory_system()))
    assert kwargs["system"][2] == {"type": "text", "text": "память", "cache_control": CACHE_5M}


def test_stable_system_blocks_keep_cache_ttl():
    kwargs = sent(make_request(system=memory_system()))
    assert kwargs["system"][0]["cache_control"] == CACHE_1H
    assert kwargs["system"][1]["cache_control"] == CACHE_1H


def test_four_cache_points_with_memory():
    message = Message(role="user", content=[Text(text="ход")], cache=True)
    kwargs = sent(make_request(system=memory_system(), messages=[message]))
    points = [b for b in kwargs["system"] if "cache_control" in b]
    points += [b for b in kwargs["messages"][0]["content"] if "cache_control" in b]
    assert len(points) == 4


def test_refusal_has_no_stop_detail():
    adapter, _, _ = make([api_response([Block(type="text", text="не могу")], "refusal")])
    assert adapter.complete(make_request()).stop_detail is None


def test_none_input_and_output_tokens_count_as_zero():
    usage = api_usage(input_tokens=None, output_tokens=None)
    adapter, _, _ = make([api_response(usage=usage)])
    result = adapter.complete(make_request()).usage
    assert (result.input, result.output) == (0, 0)


def test_response_without_request_id_attribute_gives_none():
    response = api_response()
    del response._request_id
    adapter, _, _ = make([response])
    assert adapter.complete(make_request()).request_id is None


class FakeModelsList:
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def list(self, **kwargs):
        self.calls.append(kwargs)
        if self.error is not None:
            raise self.error
        return []


def probing(error=None, api_key="k"):
    models = FakeModelsList(error)
    adapter = AnthropicAdapter(
        MODEL, app_cfg(), client_factory=lambda **kw: SimpleNamespace(models=models),
        api_key=api_key,
    )
    return adapter, models


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_fatal_status_error_keeps_status(code):
    adapter, _, _ = make([StatusError(code)])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request())
    assert info.value.status == code


def test_fatal_error_without_status_code_has_no_status():
    adapter, _, _ = make([ValueError("странное")])
    with pytest.raises(LlmFatal) as info:
        adapter.complete(make_request())
    assert info.value.status is None


def test_probe_lists_one_model():
    adapter, models = probing()
    adapter.probe()
    assert models.calls == [{"limit": 1}]


def test_probe_auth_error_is_fatal_with_status():
    adapter, _ = probing(StatusError(401, "invalid x-api-key"))
    with pytest.raises(LlmFatal) as info:
        adapter.probe()
    assert info.value.status == 401


def test_probe_overloaded_is_transient():
    adapter, _ = probing(StatusError(529))
    with pytest.raises(LlmTransient):
        adapter.probe()


def test_probe_error_text_has_no_key():
    adapter, _ = probing(StatusError(401, "bad sk-ant-SECRET-77"), api_key="sk-ant-SECRET-77")
    with pytest.raises(LlmFatal) as info:
        adapter.probe()
    assert "sk-ant-SECRET-77" not in str(info.value)
