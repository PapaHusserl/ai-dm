# ТБ #45 (docs/plan-tb.md п.3): замер статики запроса рассказчика -- правила (narrator_rules.md)
# и схемы инструментов режима -- с порогом STATIC_MAX (ratchet). Замер:
# PromptBuilder.static_tokens(mode) -> {rules, tools, total} по общему chars_per_token (не по
# провайдеру); реестр пака не участвует (monster_ids и world.md паков в статику не входят).
#
# STATIC_MAX = текущий explore.total после ТБ #56 + ~3 %. Поднимать порог только с причиной здесь:
#   ТБ (2026-10-17): порог введён, 28900 = 28022 + 3 %.
import json
from importlib import resources

import pytest
from master_kit import app_cfg

from ai_dm.config.app import load_settings
from ai_dm.llm.types import ToolSpec
from ai_dm.master.context import estimate_tokens
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.schema import MODE_TOOLS, tool_set

# ТБ: замер кабана после #56 -- explore.total 28022 (rules 8167, tools 19855) + 3 %.
STATIC_MAX = 28900

MODES = sorted(MODE_TOOLS)


def builder(app=None):
    return PromptBuilder(app or load_settings().app)


def rules_text():
    return (resources.files("ai_dm.master") / "prompts" / "narrator_rules.md").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize("mode", MODES)
def test_static_total_is_within_threshold(mode):
    assert builder().static_tokens(mode)["total"] <= STATIC_MAX


@pytest.mark.parametrize("mode", MODES)
def test_static_total_is_rules_plus_tools(mode):
    tokens = builder().static_tokens(mode)
    assert tokens["total"] == tokens["rules"] + tokens["tools"]


@pytest.mark.parametrize("mode", MODES)
def test_static_parts_are_positive(mode):
    tokens = builder().static_tokens(mode)
    assert tokens["rules"] > 0
    assert tokens["tools"] > 0


@pytest.mark.parametrize("mode", MODES)
def test_static_result_has_exactly_three_keys(mode):
    assert set(builder().static_tokens(mode)) == {"rules", "tools", "total"}


def test_explore_is_the_largest_static_mode():
    totals = {mode: builder().static_tokens(mode)["total"] for mode in MODES}
    assert totals["explore"] == max(totals.values())


def test_rules_tokens_are_the_same_in_every_mode():
    rules = {builder().static_tokens(mode)["rules"] for mode in MODES}
    assert len(rules) == 1


def test_rules_tokens_are_estimate_of_rules_file_by_common_cpt():
    app = load_settings().app
    expected = estimate_tokens(rules_text(), app.master.chars_per_token)
    assert builder(app).static_tokens("explore")["rules"] == expected


@pytest.mark.parametrize("mode", MODES)
def test_tools_tokens_are_estimate_of_serialized_tool_schemas(mode):
    app = load_settings().app
    specs = [ToolSpec.model_validate(d) for d in tool_set(mode)]
    dumped = json.dumps([s.model_dump(mode="json") for s in specs])
    expected = estimate_tokens(dumped, app.master.chars_per_token)
    assert builder(app).static_tokens(mode)["tools"] == expected


def test_static_tokens_follow_common_chars_per_token():
    loose = load_settings().app
    loose.master.chars_per_token = 5.0
    tight = load_settings().app
    tight.master.chars_per_token = 2.5
    for part in ("rules", "tools"):
        fine = builder(tight).static_tokens("explore")[part]
        coarse = builder(loose).static_tokens("explore")[part]
        assert 2 * coarse - 1 <= fine <= 2 * coarse


def test_static_tokens_do_not_depend_on_role_provider():
    anthropic = app_cfg()
    gemini = app_cfg()
    gemini.roles = gemini.profiles["gemini"]
    assert builder(anthropic).static_tokens("explore") == builder(gemini).static_tokens("explore")


def test_static_tokens_ignore_per_provider_cpt():
    app = app_cfg()
    base = builder(app).static_tokens("explore")
    app.master.chars_per_token_by_provider = {"anthropic": 1.0, "gemini": 9.0}
    assert builder(app).static_tokens("explore") == base
