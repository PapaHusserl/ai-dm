# Ожидаемый API: ai_dm.protocol.render.render_tool_result(outcome)
#   -> {"content": str, "is_error": bool}
#   Decision -> is_error False; Invalid -> is_error True. content -- JSON, ключи отсортированы на
#   всех уровнях, ensure_ascii=False (русский текст читаем), строки бросков ТЗ 6 -- в "log".
import json

from protocol_kit import ScriptedRng, make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.render import render_tool_result


def key_orders(node):
    # порядок ключей каждого словаря в дереве
    if isinstance(node, dict):
        yield list(node)
        for value in node.values():
            yield from key_orders(value)
    elif isinstance(node, list):
        for value in node:
            yield from key_orders(value)


def test_render_result_shape():
    out = render_tool_result(Decision(status="accepted"))
    assert sorted(out) == ["content", "is_error"]
    assert isinstance(out["content"], str)


def test_render_decision_is_not_error():
    rejected = Decision(status="rejected", signal_to_master="нельзя")
    clamped = Decision(status="clamped", signal_to_master="урезано")
    assert render_tool_result(rejected)["is_error"] is False
    assert render_tool_result(clamped)["is_error"] is False


def test_render_invalid_is_error_with_code_and_message():
    out = render_tool_result(Invalid(code="unknown_item", message="нет предмета"))
    assert out["is_error"] is True
    data = json.loads(out["content"])
    assert data["code"] == "unknown_item"
    assert data["message"] == "нет предмета"


def test_render_decision_json_has_all_fields():
    d = Decision(
        status="clamped", reason="много", signal_to_master="урезано", report_tag="limit-exceeded",
        result={"qty": 20}, log=["строка"],
    )
    data = json.loads(render_tool_result(d)["content"])
    assert data == d.model_dump()


def test_render_sorts_keys_on_all_levels():
    d = Decision(status="accepted", result={"z": 1, "a": {"y": 2, "b": 3}})
    data = json.loads(render_tool_result(d)["content"])
    for order in key_orders(data):
        assert order == sorted(order)


def test_render_sorts_keys_of_invalid():
    data = json.loads(render_tool_result(Invalid(code="x", message="y"))["content"])
    assert list(data) == sorted(data)


def test_render_keeps_russian_text_unescaped():
    out = render_tool_result(Decision(status="accepted", reason="получилось"))
    assert "получилось" in out["content"]
    assert "\\u" not in out["content"]


def test_render_is_stable_between_calls():
    d = Decision(status="accepted", result={"b": 1, "a": 2}, log=["x"])
    assert render_tool_result(d) == render_tool_result(d)


def test_render_does_not_depend_on_result_insertion_order():
    a = Decision(status="accepted", result={"a": 1, "b": 2})
    b = Decision(status="accepted", result={"b": 2, "a": 1})
    assert render_tool_result(a)["content"] == render_tool_result(b)["content"]


def test_render_check_contains_roll_line_and_dc(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[20]))
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    data = json.loads(render_tool_result(d)["content"])
    assert data["status"] == "accepted"
    assert data["result"]["dc"] == 15
    line = data["log"][0]
    # строка называет проверку (живой прогон: было непонятно, что бросается)
    assert line.startswith("Убеждение (Хар): d20 (20)")
    assert "против СЛ 15" in line
    assert "→ успех" in line


def test_render_failed_check_line_says_fail(registry, cfg):
    ctx = make_ctx(registry, cfg, ScriptedRng(d20=[1]))
    d = apply(ctx, req("skill_check", skill="persuasion", category="medium"))
    assert "→ провал" in json.loads(render_tool_result(d)["content"])["log"][0]
