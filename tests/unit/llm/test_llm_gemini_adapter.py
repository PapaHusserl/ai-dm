# Ожидаемый API: ai_dm.llm.gemini_adapter.GeminiAdapter -- контракт в llm_kit.py и
# docs/llm-notes/gemini-facts.md, на фейковых клиенте и «sdk» (сети нет); тесты в конце файла --
# на настоящих google.genai.types.
#   GeminiAdapter(model, app_cfg, *, client=None, sdk=None, api_key=None)
#     client -- объект с .models.generate_content(**kw); по умолчанию
#     genai.Client(api_key=..) (лениво). sdk -- пространство имён с типами google.genai.types
#     (Content, Part, Part.from_function_response, FunctionCall, Tool, FunctionDeclaration,
#     GenerateContentConfig, ToolConfig, FunctionCallingConfig, AutomaticFunctionCallingConfig);
#     по умолчанию -- настоящий google.genai.types (лениво). Адаптер создаёт все объекты ТОЛЬКО
#     через sdk.<Имя>(**поля) -- так тесты видят поля, не завися от версии SDK.
#     complete(req): client.models.generate_content(model=req.model, contents=[Content(role,
#       parts)], config=GenerateContentConfig(system_instruction=<текст system через пустую строку>,
#       tools=[Tool(function_declarations=[FunctionDeclaration(name, description, parameters)])],
#       tool_config=ToolConfig(function_calling_config=FunctionCallingConfig(mode="AUTO")),
#       automatic_function_calling=AutomaticFunctionCallingConfig(disable=True),
#       max_output_tokens=req.max_tokens)); parameters = input_schema без ключей
#       additionalProperties (на всех уровнях); поля strict в объявлении нет.
#     история: user -> Content("user"), assistant -> Content("model"); Text -> Part(text=);
#       ToolCall -> Part(function_call=FunctionCall(name, args)); ToolResult ->
#       Part.from_function_response(name=<имя ToolCall с тем же id из истории>,
#       response={"result": content}) (при is_error
#       content лежит в response под другим ключом); если в assistant-сообщении есть
#       Opaque("gemini", {"parts": [dict]}) -- Content("model", [Part(**dict), ...]) ИЗ ЭТОГО
#       Opaque вместо Text/ToolCall этого сообщения (части модели возвращаются без изменений).
#     ответ: content = [Text (не-thought части), ..., ToolCall (из response.function_calls), ...,
#       Opaque("gemini", {"parts": [part.model_dump(exclude_none=True) для всех частей
#       candidates[0].content.parts]})] -- Opaque последним, только если части есть;
#       ToolCall.id = function_call.id, а если его нет -- непустой уникальный в пределах ответа;
#       stop_reason: есть function_calls -> tool_use; finish_reason.name STOP -> end_turn,
#       MAX_TOKENS -> max_tokens, SAFETY (или prompt_feedback.block_reason) -> refusal,
#       иное -> other;
#       usage: input = prompt_token_count - cached,
#       output = candidates_token_count + thoughts_token_count,
#       cache_read = cached_content_token_count (None -> 0); request_id = response.response_id.
#     ошибки: исключение с .code (google.genai.errors.APIError): 429 и >= 500 -> LlmTransient,
#       прочие 4xx -> LlmFatal; ключ api_key из текста вычищается.
#     ревью партии 3: FunctionResponse(id, name, response) -- если call_id пришёл от API (не
#       синтезированный gemini-...); модель запроса -- из req.model; ChatResponse.model --
#       response.model_version или запрошенная; неизвестный call_id в истории -> ValueError
#       (до обращения к клиенту); genai.Client(api_key=, http_options=HttpOptions(timeout=мс)).
#     info() -> AdapterInfo("gemini", model)
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg, make_request, user

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.gemini_adapter import GeminiAdapter
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
from ai_dm.protocol.schema import MODE_TOOLS, tool_set

MODEL = "gemini-3.8-flash"
SECRET = "AIza-FAKE-0123456789-ZZZ"


class Rec:
    # любой объект SDK: хранит переданные поля как атрибуты
    def __init__(self, **kw):
        self.__dict__.update(kw)

    def __eq__(self, other):
        return type(self) is type(other) and self.__dict__ == other.__dict__

    def __repr__(self):
        return f"{type(self).__name__}({self.__dict__})"


class Content(Rec):
    pass


class Part(Rec):
    @classmethod
    def from_function_response(cls, *, name, response):
        return cls(kind="function_response", name=name, response=response)


class FunctionCall(Rec):
    pass


class FunctionResponse(Rec):
    pass


class Tool(Rec):
    pass


class FunctionDeclaration(Rec):
    pass


class GenerateContentConfig(Rec):
    pass


class ToolConfig(Rec):
    pass


class FunctionCallingConfig(Rec):
    pass


class AutomaticFunctionCallingConfig(Rec):
    pass


class CreateCachedContentConfig(Rec):
    pass


FAKE_SDK = SimpleNamespace(
    Content=Content, Part=Part, FunctionCall=FunctionCall, FunctionResponse=FunctionResponse,
    Tool=Tool,
    FunctionDeclaration=FunctionDeclaration, GenerateContentConfig=GenerateContentConfig,
    ToolConfig=ToolConfig, FunctionCallingConfig=FunctionCallingConfig,
    AutomaticFunctionCallingConfig=AutomaticFunctionCallingConfig,
    CreateCachedContentConfig=CreateCachedContentConfig,
)


class ApiError(Exception):
    def __init__(self, code, message="ошибка"):
        super().__init__(message)
        self.code = code
        self.message = message


class FakeModels:
    def __init__(self, results):
        self.results = list(results)
        self.calls = []

    def generate_content(self, **kwargs):
        self.calls.append(kwargs)
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result



def part(text=None, thought=None, call=None):
    fields = {"text": text, "thought": thought, "function_call": call}
    dumped = {k: v for k, v in fields.items() if v is not None}
    p = Part(**fields)
    p.model_dump = lambda **kw: dict(dumped)
    return p


def fcall(name, args, call_id=None):
    return SimpleNamespace(name=name, args=args, id=call_id)


def meta(prompt=0, candidates=0, thoughts=None, cached=None):
    return SimpleNamespace(
        prompt_token_count=prompt, candidates_token_count=candidates,
        thoughts_token_count=thoughts, cached_content_token_count=cached,
    )


def api_response(
    parts=None, calls=None, finish="STOP", usage=None, block=None, rid="resp-1", version=None,
):
    candidates = None
    if parts is not None:
        candidates = [SimpleNamespace(
            content=SimpleNamespace(role="model", parts=parts),
            finish_reason=SimpleNamespace(name=finish),
        )]
    feedback = SimpleNamespace(block_reason=SimpleNamespace(name=block)) if block else None
    return SimpleNamespace(
        candidates=candidates, function_calls=calls or None,
        usage_metadata=usage or meta(), prompt_feedback=feedback, response_id=rid,
        model_version=version,
    )


def make(results=None, api_key=None):
    models = FakeModels(results if results is not None else [api_response([part(text="ок")])])
    client = SimpleNamespace(models=models)
    adapter = GeminiAdapter(MODEL, app_cfg(), client=client, sdk=FAKE_SDK, api_key=api_key)
    return adapter, models


def tools_req(mode="combat_classify", **kw):
    tools = [ToolSpec.model_validate(t) for t in tool_set(mode)]
    kw.setdefault("model", MODEL)
    return make_request(tools=tools, **kw)


def sent(req=None):
    adapter, models = make()
    adapter.complete(req or tools_req())
    return models.calls[0]


def walk_keys(node):
    if isinstance(node, dict):
        for key, value in node.items():
            yield key
            yield from walk_keys(value)
    elif isinstance(node, list):
        for value in node:
            yield from walk_keys(value)


def strip_additional(node):
    if isinstance(node, dict):
        return {k: strip_additional(v) for k, v in node.items() if k != "additionalProperties"}
    if isinstance(node, list):
        return [strip_additional(v) for v in node]
    return node


def test_info_names_gemini():
    adapter, _ = make()
    assert adapter.info() == AdapterInfo(provider="gemini", model=MODEL)


def test_generate_content_gets_model():
    assert sent()["model"] == MODEL


def test_system_instruction_joins_system_blocks():
    system = [SystemBlock(text="правила", cache=True), SystemBlock(text="мир", cache=True)]
    config = sent(tools_req(system=system))["config"]
    assert config.system_instruction == "правила\n\nмир"


def test_max_output_tokens_from_request():
    assert sent(tools_req(max_tokens=1234))["config"].max_output_tokens == 1234


def test_tools_become_function_declarations():
    config = sent(tools_req("combat_classify"))["config"]
    decls = config.tools[0].function_declarations
    assert [d.name for d in decls] == [t["name"] for t in tool_set("combat_classify")]
    assert [d.description for d in decls] == [t["description"] for t in tool_set("combat_classify")]


def test_declarations_have_no_strict_field():
    decls = sent(tools_req("combat_classify"))["config"].tools[0].function_declarations
    assert all("strict" not in d.__dict__ for d in decls)


def test_parameters_have_no_additional_properties():
    decls = sent(tools_req("combat_narrate"))["config"].tools[0].function_declarations
    for decl in decls:
        assert "additionalProperties" not in set(walk_keys(decl.parameters))


def test_parameters_are_the_schema_minus_additional_properties():
    decls = sent(tools_req("combat_classify"))["config"].tools[0].function_declarations
    expected = [strip_additional(t["input_schema"]) for t in tool_set("combat_classify")]
    assert [d.parameters for d in decls] == expected


def test_function_calling_mode_is_auto():
    config = sent()["config"]
    assert config.tool_config.function_calling_config.mode == "AUTO"


def test_automatic_function_calling_is_disabled():
    assert sent()["config"].automatic_function_calling.disable is True


def test_user_text_becomes_user_content_with_text_part():
    contents = sent(tools_req(messages=[user("осмотрюсь")]))["contents"]
    assert contents == [Content(role="user", parts=[Part(text="осмотрюсь")])]


def test_assistant_history_becomes_model_content():
    req = tools_req(messages=[
        user("а"),
        Message(role="assistant", content=[Text(text="рассказ")]),
        user("б"),
    ])
    contents = sent(req)["contents"]
    assert [c.role for c in contents] == ["user", "model", "user"]
    assert contents[1].parts == [Part(text="рассказ")]


def test_tool_call_in_history_becomes_function_call_part():
    req = tools_req(messages=[
        user("а"),
        Message(role="assistant", content=[ToolCall(id="c1", name="skill_check", input={"k": 1})]),
        user("б"),
    ])
    parts = sent(req)["contents"][1].parts
    assert parts == [Part(function_call=FunctionCall(name="skill_check", args={"k": 1}))]


def history_with_result(is_error=False, call_id="c1"):
    return tools_req(messages=[
        user("убеждаю"),
        Message(role="assistant", content=[
            ToolCall(id=call_id, name="skill_check", input={"skill": "persuasion"}),
        ]),
        Message(role="user", content=[
            ToolResult(call_id=call_id, content='{"total": 17}', is_error=is_error),
        ]),
    ])


def test_tool_result_becomes_function_response_part():
    content = sent(history_with_result())["contents"][2]
    assert content.role in ("user", "tool")
    response = FunctionResponse(id="c1", name="skill_check", response={"result": '{"total": 17}'})
    assert content.parts == [Part(function_response=response)]


def test_function_response_carries_id_from_api():
    content = sent(history_with_result(call_id="fc-77"))["contents"][2]
    assert content.parts[0].function_response.id == "fc-77"


def test_function_response_of_synthesized_id_has_no_id():
    content = sent(history_with_result(call_id="gemini-resp-1-1"))["contents"][2]
    assert content.parts == [
        Part(kind="function_response", name="skill_check", response={"result": '{"total": 17}'}),
    ]


def test_tool_result_error_keeps_content_in_response():
    content = sent(history_with_result(is_error=True))["contents"][2]
    function_response = content.parts[0].function_response
    assert '{"total": 17}' in function_response.response.values()
    assert function_response.name == "skill_check"


def test_two_tool_results_resolve_names_by_call_id():
    req = tools_req(messages=[
        user("x"),
        Message(role="assistant", content=[
            ToolCall(id="c1", name="alpha", input={}), ToolCall(id="c2", name="beta", input={}),
        ]),
        Message(role="user", content=[
            ToolResult(call_id="c2", content="2"), ToolResult(call_id="c1", content="1"),
        ]),
    ])
    parts = sent(req)["contents"][2].parts
    pairs = [(p.function_response.name, p.function_response.response["result"]) for p in parts]
    assert pairs == [("beta", "2"), ("alpha", "1")]


def test_unknown_call_id_is_value_error():
    req = tools_req(messages=[
        user("x"),
        Message(role="user", content=[ToolResult(call_id="нет-такого", content="1")]),
    ])
    adapter, _ = make()
    with pytest.raises(ValueError, match="нет-такого"):
        adapter.complete(req)


def test_unknown_call_id_is_not_an_llm_error():
    req = tools_req(messages=[
        user("x"),
        Message(role="user", content=[ToolResult(call_id="нет-такого", content="1")]),
    ])
    adapter, _ = make()
    with pytest.raises(ValueError) as info:
        adapter.complete(req)
    assert not isinstance(info.value, (LlmFatal, LlmTransient))


def test_unknown_call_id_does_not_reach_the_client():
    req = tools_req(messages=[
        user("x"),
        Message(role="user", content=[ToolResult(call_id="нет-такого", content="1")]),
    ])
    adapter, models = make()
    with pytest.raises(ValueError):
        adapter.complete(req)
    assert models.calls == []


def test_opaque_parts_replace_text_and_tool_call_of_that_message():
    raw_parts = [{"thought": True, "text": "думаю"}, {"text": "рассказ"}]
    req = tools_req(messages=[
        user("а"),
        Message(role="assistant", content=[
            Text(text="рассказ"),
            Opaque(provider="gemini", raw={"parts": raw_parts}),
        ]),
        user("б"),
    ])
    model_content = sent(req)["contents"][1]
    assert model_content.role == "model"
    assert model_content.parts == [Part(**raw_parts[0]), Part(**raw_parts[1])]


def test_text_response_to_text_block():
    adapter, _ = make([api_response([part(text="Привет")])])
    assert adapter.complete(tools_req()).content[0] == Text(text="Привет")


def test_text_response_end_turn():
    adapter, _ = make([api_response([part(text="Привет")])])
    assert adapter.complete(tools_req()).stop_reason == "end_turn"


def test_function_calls_become_tool_calls():
    calls = [fcall("skill_check", {"skill": "stealth"}, "fc-1")]
    adapter, _ = make([api_response([part(call=calls[0])], calls=calls)])
    resp = adapter.complete(tools_req())
    tool_calls = [b for b in resp.content if isinstance(b, ToolCall)]
    assert tool_calls == [ToolCall(id="fc-1", name="skill_check", input={"skill": "stealth"})]
    assert resp.stop_reason == "tool_use"


def test_function_calls_without_ids_get_unique_ids():
    calls = [fcall("a", {}), fcall("b", {})]
    adapter, _ = make([api_response([part(call=c) for c in calls], calls=calls)])
    first, second = [b for b in adapter.complete(tools_req()).content if isinstance(b, ToolCall)]
    assert first.id and second.id and first.id != second.id


def test_generated_tool_call_id_resolves_the_name_in_history():
    calls = [fcall("skill_check", {"skill": "stealth"})]
    adapter, models = make([api_response([part(call=calls[0])], calls=calls),
                            api_response([part(text="готово")])])
    first = adapter.complete(tools_req())
    call = next(b for b in first.content if isinstance(b, ToolCall))
    history = [
        user("х"),
        Message(role="assistant", content=first.content),
        Message(role="user", content=[ToolResult(call_id=call.id, content="итог")]),
    ]
    adapter.complete(tools_req(messages=history))
    last_parts = models.calls[1]["contents"][-1].parts
    assert last_parts[0].name == "skill_check"


def test_text_and_tool_call_order_is_text_then_calls_then_opaque():
    calls = [fcall("end_scene", {}, "fc-1")]
    parts = [part(text="сцена кончается"), part(call=calls[0])]
    adapter, _ = make([api_response(parts, calls=calls)])
    content = adapter.complete(tools_req()).content
    assert [type(b) for b in content] == [Text, ToolCall, Opaque]


def test_response_parts_are_kept_as_opaque_unchanged():
    parts = [part(text="думаю", thought=True), part(text="рассказ")]
    adapter, _ = make([api_response(parts)])
    opaque = adapter.complete(tools_req()).content[-1]
    assert opaque == Opaque(provider="gemini", raw={"parts": [
        {"text": "думаю", "thought": True}, {"text": "рассказ"},
    ]})


def test_thought_part_is_not_narration_text():
    parts = [part(text="думаю", thought=True), part(text="рассказ")]
    adapter, _ = make([api_response(parts)])
    texts = [b.text for b in adapter.complete(tools_req()).content if isinstance(b, Text)]
    assert texts == ["рассказ"]


def test_usage_is_mapped():
    adapter, _ = make([api_response([part(text="x")], usage=meta(prompt=100, candidates=40))])
    assert adapter.complete(tools_req()).usage == Usage(input=100, output=40)


def test_thoughts_are_added_to_output():
    usage = meta(prompt=100, candidates=40, thoughts=25)
    adapter, _ = make([api_response([part(text="x")], usage=usage)])
    assert adapter.complete(tools_req()).usage.output == 65


def test_cached_content_goes_to_cache_read():
    usage = meta(prompt=100, candidates=40, cached=60)
    adapter, _ = make([api_response([part(text="x")], usage=usage)])
    assert adapter.complete(tools_req()).usage.cache_read == 60


def test_cached_tokens_are_subtracted_from_input():
    # prompt_token_count включает кэш: prompt 1000, cached 600 -> input 400, cache_read 600
    usage = meta(prompt=1000, candidates=40, cached=600)
    adapter, _ = make([api_response([part(text="x")], usage=usage)])
    resp = adapter.complete(tools_req())
    assert (resp.usage.input, resp.usage.cache_read) == (400, 600)


def test_missing_usage_metadata_is_zero():
    resp = api_response([part(text="x")])
    resp.usage_metadata = None
    adapter, _ = make([resp])
    assert adapter.complete(tools_req()).usage == Usage()


def test_request_id_from_response_id():
    adapter, _ = make([api_response([part(text="x")], rid="resp-77")])
    assert adapter.complete(tools_req()).request_id == "resp-77"


def test_finish_reason_max_tokens():
    adapter, _ = make([api_response([part(text="обор")], finish="MAX_TOKENS")])
    assert adapter.complete(tools_req()).stop_reason == "max_tokens"


def test_finish_reason_safety_is_refusal_not_error():
    adapter, _ = make([api_response([part(text="")], finish="SAFETY")])
    assert adapter.complete(tools_req()).stop_reason == "refusal"


def test_prompt_block_without_candidates_is_refusal():
    adapter, _ = make([api_response(None, block="SAFETY")])
    resp = adapter.complete(tools_req())
    assert (resp.stop_reason, resp.content) == ("refusal", [])


def test_unknown_finish_reason_is_other():
    adapter, _ = make([api_response([part(text="x")], finish="OTHER")])
    assert adapter.complete(tools_req()).stop_reason == "other"


@pytest.mark.parametrize("finish", ["PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"])
def test_blocked_finish_reasons_are_refusal(finish):
    adapter, _ = make([api_response([part(text="")], finish=finish)])
    assert adapter.complete(tools_req()).stop_reason == "refusal"


@pytest.mark.parametrize("code", [408, 429, 500, 503])
def test_api_errors_that_are_transient(code):
    adapter, _ = make([ApiError(code)])
    with pytest.raises(LlmTransient):
        adapter.complete(tools_req())


@pytest.mark.parametrize("code", [400, 401, 403, 404])
def test_api_errors_that_are_fatal(code):
    adapter, _ = make([ApiError(code)])
    with pytest.raises(LlmFatal):
        adapter.complete(tools_req())


def test_error_message_is_kept():
    adapter, _ = make([ApiError(400, "неверная схема функции")])
    with pytest.raises(LlmFatal, match="неверная схема функции"):
        adapter.complete(tools_req())


def test_error_message_does_not_leak_the_api_key():
    adapter, _ = make([ApiError(401, f"API key not valid: {SECRET}")], api_key=SECRET)
    with pytest.raises(LlmFatal) as info:
        adapter.complete(tools_req())
    assert SECRET not in str(info.value)


def test_adapter_makes_one_call_per_complete():
    adapter, models = make([ApiError(503), api_response([part(text="x")])])
    with pytest.raises(LlmTransient):
        adapter.complete(tools_req())
    assert len(models.calls) == 1


# сетевые ошибки httpx приходят без .code: по имени класса (или предка)
class ConnectError(Exception):
    pass


class ConnectTimeout(Exception):
    pass


class ReadTimeout(Exception):
    pass


class TimeoutException(Exception):
    pass


class NetworkError(Exception):
    pass


class ReadError(NetworkError):
    pass


@pytest.mark.parametrize(
    "exc_class",
    [ConnectError, ConnectTimeout, ReadTimeout, TimeoutException, NetworkError, ReadError],
)
def test_network_errors_without_code_are_transient(exc_class):
    adapter, _ = make([exc_class("сеть")])
    with pytest.raises(LlmTransient):
        adapter.complete(tools_req())


def test_unknown_exception_without_code_is_fatal():
    adapter, _ = make([RuntimeError("что-то странное")])
    with pytest.raises(LlmFatal):
        adapter.complete(tools_req())


class RemoteProtocolError(Exception):
    pass


class WriteError(NetworkError):
    pass


class TransportError(Exception):
    pass


@pytest.mark.parametrize("exc_class", [RemoteProtocolError, ReadError, WriteError, TransportError])
def test_more_network_errors_without_code_are_transient(exc_class):
    adapter, _ = make([exc_class("сеть")])
    with pytest.raises(LlmTransient):
        adapter.complete(tools_req())


def test_response_model_is_model_version_from_api():
    adapter, _ = make([api_response([part(text="x")], version="gemini-3.8-flash-002")])
    assert adapter.complete(tools_req()).model == "gemini-3.8-flash-002"


def test_response_model_falls_back_to_requested_model():
    adapter, _ = make([api_response([part(text="x")])])
    assert adapter.complete(tools_req()).model == MODEL


def test_model_is_taken_from_request_not_from_adapter():
    adapter, models = make()
    adapter.complete(tools_req(model="gemini-3.5-flash-lite"))
    assert models.calls[0]["model"] == "gemini-3.5-flash-lite"


def test_info_keeps_adapter_model_whatever_the_request():
    adapter, _ = make()
    adapter.complete(tools_req(model="gemini-3.5-flash-lite"))
    assert adapter.info().model == MODEL


def test_client_gets_http_timeout_in_milliseconds(monkeypatch):
    from google import genai
    from google.genai import types

    created = []
    monkeypatch.setattr(genai, "Client", lambda **kw: created.append(kw) or SimpleNamespace())
    cfg = app_cfg()
    GeminiAdapter(MODEL, cfg, api_key="k").get_client()
    options = created[0]["http_options"]
    assert isinstance(options, types.HttpOptions)
    assert options.timeout == cfg.retry.timeout_s * 1000
    assert created[0]["api_key"] == "k"


# настоящие типы google.genai.types (без сети): пишем объекты SDK, а не подделки

def real_adapter(models=None):
    client = SimpleNamespace(models=models) if models is not None else None
    return GeminiAdapter(MODEL, app_cfg(), client=client)


@pytest.mark.parametrize("mode", sorted(MODE_TOOLS))
def test_real_build_config_for_every_tool_set(mode):
    from google.genai import types

    tools = [ToolSpec.model_validate(t) for t in tool_set(mode)]
    config = real_adapter().build_config(tools_req_for(tools))
    assert isinstance(config, types.GenerateContentConfig)
    declared = [d.name for d in config.tools[0].function_declarations]
    assert declared == [t.name for t in tools]


def tools_req_for(tools):
    return make_request(tools=tools, model=MODEL)


def real_tool_call_response():
    from google.genai import types

    part = types.Part(
        function_call=types.FunctionCall(name="skill_check", args={"skill": "stealth"}),
        thought_signature=b"sig\xff\x00",
    )
    return types.GenerateContentResponse(
        candidates=[types.Candidate(
            content=types.Content(role="model", parts=[part]),
            finish_reason=types.FinishReason.STOP,
        )],
        response_id="r1",
    )


def test_real_parse_response_keeps_thought_signature_through_json_to_contents():
    from ai_dm.llm.types import ChatResponse

    adapter = real_adapter()
    parsed = adapter.parse_response(real_tool_call_response(), make_request(model=MODEL))
    assert parsed.stop_reason == "tool_use"
    restored = ChatResponse.model_validate_json(parsed.model_dump_json())
    call = next(b for b in restored.content if isinstance(b, ToolCall))
    req = make_request(model=MODEL, messages=[
        user("крадусь"),
        Message(role="assistant", content=restored.content),
        Message(role="user", content=[ToolResult(call_id=call.id, content="итог")]),
    ])
    contents = adapter.build_contents(req)
    assert contents[1].parts[0].thought_signature == b"sig\xff\x00"


def test_real_function_response_with_synthesized_id_is_built():
    adapter = real_adapter()
    parsed = adapter.parse_response(real_tool_call_response(), make_request(model=MODEL))
    call = next(b for b in parsed.content if isinstance(b, ToolCall))
    req = make_request(model=MODEL, messages=[
        user("а"),
        Message(role="assistant", content=[ToolCall(id=call.id, name=call.name, input=call.input)]),
        Message(role="user", content=[ToolResult(call_id=call.id, content="итог")]),
    ])
    response = adapter.build_contents(req)[2].parts[0].function_response
    assert (response.name, response.id) == ("skill_check", None)


def test_real_function_response_with_api_id_keeps_id():
    adapter = real_adapter()
    req = make_request(model=MODEL, messages=[
        user("а"),
        Message(role="assistant", content=[ToolCall(id="fc-9", name="skill_check", input={})]),
        Message(role="user", content=[ToolResult(call_id="fc-9", content="итог")]),
    ])
    response = adapter.build_contents(req)[2].parts[0].function_response
    assert (response.name, response.id) == ("skill_check", "fc-9")
