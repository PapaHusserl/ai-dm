# Этап 4, P1+: кэш tool_defs ключуется по группе режимов (world / summarize_* / обычные), а не
# по булеву «есть своя модель»: одно имя запроса в двух группах даёт разные схемы.
from ai_dm.protocol import schema
from ai_dm.protocol.requests import SceneSummaryRequest


def test_same_name_in_world_and_summary_groups_gives_own_schemas(monkeypatch):
    monkeypatch.setattr(schema, "_cache", {})
    monkeypatch.setitem(schema.SUMMARY_MODELS, "skill_check", SceneSummaryRequest)
    world = schema.tool_defs(["skill_check"], "world")[0]
    summary = schema.tool_defs(["skill_check"], "summarize_scene")[0]
    assert "summary" not in world["input_schema"]["properties"]
    assert "summary" in summary["input_schema"]["properties"]


def test_summary_first_then_world_gives_own_schemas(monkeypatch):
    monkeypatch.setattr(schema, "_cache", {})
    monkeypatch.setitem(schema.SUMMARY_MODELS, "skill_check", SceneSummaryRequest)
    summary = schema.tool_defs(["skill_check"], "summarize_scene")[0]
    world = schema.tool_defs(["skill_check"], "world")[0]
    assert "summary" in summary["input_schema"]["properties"]
    assert "summary" not in world["input_schema"]["properties"]


def test_explore_and_world_variants_stay_different():
    explore = schema.tool_defs(["skill_check"], "explore")[0]
    world = schema.tool_defs(["skill_check"], "world")[0]
    assert explore != world
