# Б0-П1 (B0-PLAN A4): режим hero_background -- инструмент background_spec, разбор, apply и хендлер.
import json

import pytest
from protocol_kit import make_ctx, req

from ai_dm.protocol import schema
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import BackgroundTask, CreationContext
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.protocol.requests import BackgroundSpecRequest, parse_request

CLASS_SKILLS = ["perception", "survival"]


def spec_input(**changes):
    data = {
        "type": "background_spec", "name": "Бывший цирковой акробат",
        "abilities": ["dex", "con", "cha"], "skills": ["acrobatics", "performance"],
        "tool": "thieves_tools", "feat": "alert", "equipment": ["crowbar"], "gold_cp": 1000,
        "description": "Вырос в бродячем цирке.",
    }
    data.update(changes)
    return data


def creation(registry, cfg, class_skills=CLASS_SKILLS):
    return CreationContext(registry, cfg, BackgroundTask("fighter", class_skills))


def run(registry, cfg, **changes):
    ctx = creation(registry, cfg)
    return ctx, apply(ctx, parse_request(spec_input(**changes), "hero_background"))


# набор инструментов режима

def test_hero_background_tool_set_is_one_strict_tool():
    tools = schema.tool_set("hero_background")
    assert [t["name"] for t in tools] == ["background_spec"]
    assert tools[0]["strict"] is True


def test_hero_background_tool_schema_has_no_ref():
    tool = schema.tool_set("hero_background")[0]
    assert "$ref" not in json.dumps(tool["input_schema"])


def test_hero_background_tool_description_is_docstring():
    tool = schema.tool_set("hero_background")[0]
    assert tool["description"] == BackgroundSpecRequest.__doc__.strip()


def test_hero_background_tool_has_all_fields():
    props = schema.tool_set("hero_background")[0]["input_schema"]["properties"]
    assert set(props) == {
        "type", "name", "abilities", "skills", "tool", "feat", "equipment", "gold_cp",
        "description",
    }


def test_hero_background_tool_is_not_cached_into_other_groups():
    schema.tool_set("hero_background")
    assert [t["name"] for t in schema.tool_set("summarize_scene")] == ["scene_summary"]


# разбор

def test_parse_request_in_hero_mode_takes_background_spec():
    request = parse_request(spec_input(), "hero_background")
    assert isinstance(request, BackgroundSpecRequest)
    assert request.gold_cp == 1000


def test_parse_request_in_hero_mode_rejects_other_requests():
    with pytest.raises(ValueError):
        parse_request({"type": "set_flag", "name": "a", "value": "true"}, "hero_background")


def test_background_spec_is_not_parsed_in_explore_mode():
    with pytest.raises(ValueError):
        parse_request(spec_input())


def test_background_spec_with_unknown_skill_is_not_parsed():
    with pytest.raises(ValueError):
        parse_request(spec_input(skills=["acrobatics", "juggling"]), "hero_background")


# apply: режимы

def test_other_request_in_hero_mode_is_not_available(registry, cfg):
    ctx = creation(registry, cfg)
    result = apply(ctx, req("set_flag", name="a", value="true"))
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_background_spec_in_summarize_mode_is_not_available(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="summarize_scene")
    result = apply(ctx, parse_request(spec_input(), "hero_background"))
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


# хендлер

def test_valid_background_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg)
    assert isinstance(result, Decision)
    assert result.status == "accepted"
    assert result.log == ["Предыстория принята"]


def test_valid_background_fills_ctx_background(registry, cfg):
    ctx, _ = run(registry, cfg)
    spec = ctx.background
    assert spec.name == "Бывший цирковой акробат"
    assert spec.abilities == ["dex", "con", "cha"]
    assert spec.skills == ["acrobatics", "performance"]
    assert spec.tool == "thieves_tools"
    assert spec.feat == "alert"
    assert spec.equipment == ["crowbar"]
    assert spec.gold_cp == 1000
    assert spec.description == "Вырос в бродячем цирке."


def test_accepted_background_has_standard_gold_option(registry, cfg):
    ctx, _ = run(registry, cfg)
    assert ctx.background.gold_option_cp == 5000


def test_second_call_after_accepted_is_already_done(registry, cfg):
    ctx, _ = run(registry, cfg)
    first = ctx.background
    result = apply(ctx, parse_request(spec_input(name="Другая"), "hero_background"))
    assert isinstance(result, Invalid)
    assert result.code == "already_done"
    assert ctx.background is first


def test_invalid_background_leaves_ctx_empty(registry, cfg):
    ctx, result = run(registry, cfg, gold_cp=6000)
    assert isinstance(result, Invalid)
    assert ctx.background is None


def test_invalid_call_does_not_block_a_valid_retry(registry, cfg):
    ctx, _ = run(registry, cfg, gold_cp=6000)
    result = apply(ctx, parse_request(spec_input(), "hero_background"))
    assert result.status == "accepted"
    assert ctx.background is not None


def test_over_budget_is_invalid_with_budget_code_and_text(registry, cfg):
    _, result = run(registry, cfg, equipment=[], gold_cp=6000)
    assert result.code == "background_budget_invalid"
    assert "50 зм" in result.message


def test_class_skill_is_invalid_with_conflict_text(registry, cfg):
    _, result = run(registry, cfg, skills=["perception", "performance"])
    assert result.code == "class_skills_invalid"
    assert "навык класса уже даёт предыстория" in result.message


def test_non_origin_feat_is_invalid_with_feat_code(registry, cfg):
    _, result = run(registry, cfg, feat="defense")
    assert result.code == "background_feat"
    assert "origin" in result.message


def test_unknown_item_is_invalid_with_item_unknown_code(registry, cfg):
    _, result = run(registry, cfg, equipment=["no_such_item"])
    assert result.code == "item_unknown"
    assert "no_such_item" in result.message


def test_unknown_tool_is_invalid_with_tool_unknown_code(registry, cfg):
    _, result = run(registry, cfg, tool="no_such_tool")
    assert result.code == "background_tool_unknown"
    assert "no_such_tool" in result.message


def test_item_that_is_not_a_tool_is_invalid(registry, cfg):
    _, result = run(registry, cfg, tool="crowbar")
    assert result.code == "background_tool_unknown"


def test_all_problems_are_joined_with_semicolon_in_order(registry, cfg):
    _, result = run(registry, cfg, feat="defense", gold_cp=6000, tool="no_such_tool")
    parts = result.message.split("; ")
    assert len(parts) == 3
    assert result.code == "background_feat"
    assert "origin" in parts[0]
    assert "50 зм" in parts[1]
    assert "no_such_tool" in parts[2]


def test_two_abilities_equal_are_invalid(registry, cfg):
    _, result = run(registry, cfg, abilities=["dex", "dex", "cha"])
    assert result.code == "background_abilities"


def test_one_skill_is_invalid(registry, cfg):
    _, result = run(registry, cfg, skills=["acrobatics"])
    assert result.code == "background_skills"


def test_without_class_skills_conflict_is_not_checked(registry, cfg):
    ctx = creation(registry, cfg, class_skills=())
    data = spec_input(skills=["perception", "performance"])
    result = apply(ctx, parse_request(data, "hero_background"))
    assert result.status == "accepted"


def test_description_of_300_chars_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg, description="а" * 300)
    assert result.status == "accepted"
    assert len(ctx.background.description) == 300


def test_description_of_301_chars_is_invalid(registry, cfg):
    ctx, result = run(registry, cfg, description="а" * 301)
    assert isinstance(result, Invalid)
    assert "300" in result.message
    assert ctx.background is None


def test_empty_description_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg, description="")
    assert result.status == "accepted"
    assert ctx.background.description == ""


# контексты

def test_creation_context_turn_seq_is_zero(registry, cfg):
    assert creation(registry, cfg).turn_seq == 0


def test_creation_context_defaults(registry, cfg):
    ctx = creation(registry, cfg)
    assert ctx.mode == "hero_background"
    assert ctx.background is None
    assert ctx.marks == []
    assert ctx.task.class_id == "fighter"
    assert ctx.task.class_skills == CLASS_SKILLS
    assert ctx.sheet is None


def test_creation_context_keeps_task(registry, cfg):
    task = BackgroundTask("fighter", ["perception"])
    ctx = CreationContext(registry, cfg, task)
    assert ctx.task is task
    assert ctx.mode == task.mode == "hero_background"


def test_turn_context_turn_seq_follows_session(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.bundle.session.turn_seq = 7
    assert ctx.turn_seq == 7


def test_creation_context_keeps_cfg(registry, cfg):
    assert creation(registry, cfg).cfg is cfg


def test_too_long_description_has_own_code(registry, cfg):
    _, result = run(registry, cfg, description="а" * 301)
    assert result.code == "description_too_long"


def test_hero_tool_schema_is_cached_apart_from_summary_group(monkeypatch):
    monkeypatch.setattr(schema, "_cache", {})
    scene_model = schema.SUMMARY_MODELS["scene_summary"]
    monkeypatch.setitem(schema.SUMMARY_MODELS, "background_spec", scene_model)
    hero = schema.tool_defs(["background_spec"], "hero_background")[0]
    summary = schema.tool_defs(["background_spec"], "summarize_scene")[0]
    assert "tool" in hero["input_schema"]["properties"]
    assert "tool" not in summary["input_schema"]["properties"]


def test_negative_gold_is_invalid_with_own_code(registry, cfg):
    ctx, result = run(registry, cfg, equipment=[], gold_cp=-1)
    assert result.code == "background_gold_negative"
    assert ctx.background is None
