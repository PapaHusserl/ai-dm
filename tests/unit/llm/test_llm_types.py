# Ожидаемый API: ai_dm.llm.types, ai_dm.llm.adapter -- см. контракт в llm_kit.py.
# Нейтральные типы: JSON-цикл, extra=forbid, целые без float, дискриминатор блоков по type.
import pytest
from llm_kit import full_request, make_request, make_response
from pydantic import ValidationError

from ai_dm.llm.adapter import AdapterInfo, ModelAdapter
from ai_dm.llm.types import (
    ChatRequest,
    ChatResponse,
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


def test_request_json_cycle():
    req = full_request()
    assert ChatRequest.model_validate_json(req.model_dump_json()) == req


def test_request_json_cycle_keeps_block_classes():
    back = ChatRequest.model_validate_json(full_request().model_dump_json())
    assert [type(b) for b in back.messages[1].content] == [Text, ToolCall]
    assert isinstance(back.messages[2].content[0], ToolResult)


def test_response_json_cycle_with_all_blocks():
    resp = ChatResponse(
        content=[
            Opaque(provider="anthropic", raw={"type": "thinking", "signature": "s"}),
            Text(text="рассказ"),
            ToolCall(id="c1", name="end_scene", input={"a": [1, 2]}),
        ],
        stop_reason="tool_use",
        usage=Usage(input=1, output=2, cache_write=3, cache_write_1h=5, cache_read=4),
        request_id="req-9",
        model="claude-opus-5-5",
    )
    assert ChatResponse.model_validate_json(resp.model_dump_json()) == resp


def test_block_is_chosen_by_type_field():
    msg = Message.model_validate({"role": "user", "content": [
        {"type": "tool_result", "call_id": "c1", "content": "ok"},
    ]})
    assert isinstance(msg.content[0], ToolResult)


def test_tool_result_is_error_defaults_to_false():
    assert ToolResult(call_id="c1", content="ok").is_error is False


def test_unknown_block_type_is_rejected():
    with pytest.raises(ValidationError):
        Message.model_validate({"role": "user", "content": [{"type": "image", "url": "x"}]})


def test_message_role_system_is_rejected():
    with pytest.raises(ValidationError):
        Message(role="system", content=[Text(text="x")])


def test_request_forbids_extra_fields():
    with pytest.raises(ValidationError):
        ChatRequest.model_validate({**make_request().model_dump(), "bogus": 1})


def test_response_forbids_extra_fields():
    with pytest.raises(ValidationError):
        ChatResponse.model_validate({**make_response().model_dump(), "bogus": 1})


def test_text_block_forbids_extra_fields():
    with pytest.raises(ValidationError):
        Text.model_validate({"type": "text", "text": "x", "bogus": 1})


def test_system_block_forbids_extra_fields():
    with pytest.raises(ValidationError):
        SystemBlock.model_validate({"text": "x", "cache": False, "bogus": 1})


def test_system_block_cache_defaults_to_false():
    assert SystemBlock(text="x").cache is False


def test_request_requires_max_tokens():
    with pytest.raises(ValidationError):
        ChatRequest(role="narrator", model="m", messages=[])


def test_request_effort_defaults_to_none():
    assert make_request().effort is None


def test_request_system_and_tools_default_to_empty():
    req = ChatRequest(role="narrator", model="m", messages=[], max_tokens=10)
    assert (req.system, req.tools) == ([], [])


def test_usage_defaults_to_zeros():
    assert Usage().model_dump() == {
        "input": 0, "output": 0, "cache_write": 0, "cache_write_1h": 0, "cache_read": 0,
        "cache_storage_min": 0,
    }


def test_usage_rejects_float():
    with pytest.raises(ValidationError):
        Usage(input=1.5)


def test_usage_rejects_float_from_json():
    with pytest.raises(ValidationError):
        Usage.model_validate_json('{"input": 1.5}')


def test_stop_reason_accepts_all_five_values():
    for reason in ("end_turn", "tool_use", "max_tokens", "refusal", "other"):
        assert make_response(stop_reason=reason).stop_reason == reason


def test_stop_reason_rejects_unknown_value():
    with pytest.raises(ValidationError):
        make_response(stop_reason="pause_turn")


def test_response_request_id_defaults_to_none():
    resp = ChatResponse(content=[], stop_reason="end_turn", model="m")
    assert resp.request_id is None


def test_response_usage_defaults_to_zeros():
    resp = ChatResponse(content=[], stop_reason="end_turn", model="m")
    assert resp.usage == Usage()


def test_response_model_is_required():
    with pytest.raises(ValidationError):
        ChatResponse(content=[], stop_reason="end_turn")


def test_response_model_survives_json_cycle():
    resp = ChatResponse(content=[], stop_reason="end_turn", model="claude-opus-5-5-20261001")
    assert ChatResponse.model_validate_json(resp.model_dump_json()).model == resp.model


def test_response_model_is_kept_in_dump():
    assert make_response(model="m-1").model_dump(mode="json")["model"] == "m-1"


def test_tool_spec_accepts_protocol_definition():
    definition = tool_set("combat_classify")[0]
    spec = ToolSpec.model_validate(definition)
    assert spec.model_dump() == definition


def test_tool_spec_keeps_strict_false():
    definition = next(t for t in tool_set("explore") if t["name"] == "end_chapter")
    assert ToolSpec.model_validate(definition).strict is False


def test_tool_spec_strict_defaults_to_true():
    spec = ToolSpec(name="t", description="d", input_schema={"type": "object"})
    assert spec.strict is True


def test_opaque_keeps_raw_unchanged_in_cycle():
    raw = {"type": "thinking", "thinking": "..", "signature": "abc=="}
    block = Opaque(provider="anthropic", raw=raw)
    assert Opaque.model_validate_json(block.model_dump_json()).raw == raw


def test_adapter_info_has_provider_and_model():
    info = AdapterInfo(provider="anthropic", model="claude-opus-5-5")
    assert (info.provider, info.model) == ("anthropic", "claude-opus-5-5")


def test_model_adapter_declares_interface_methods():
    for name in ("complete", "info"):
        assert hasattr(ModelAdapter, name)


def test_model_adapter_has_no_count_tokens():
    # P3: бюджет контекста считается по длине запроса, живой count_tokens убран
    assert not hasattr(ModelAdapter, "count_tokens")



def test_system_block_is_stable_by_default():
    assert SystemBlock(text="правила").stable is True


def test_system_block_can_be_unstable():
    assert SystemBlock(text="память", cache=True, stable=False).stable is False
