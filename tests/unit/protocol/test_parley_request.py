# player_action.parley (docs/plan-combat-parley.md, п. 3): ParleySpec{skill, outcome, target};
#   skill: intimidation|persuasion|deception|none; outcome: surrender|flee|defect|waver|none;
#   target: ref врага, пусто = нет. Все три пусты -> parley None; частично -> ValidationError;
#   parley вместе с improvise -> ValidationError. Категорию СЛ мастер не передаёт
#   (СЛ считает движок).
#   Обработчик кладёт parley в result["parley"]; improvise работает как раньше.
import pytest
from protocol_kit import req
from pydantic import ValidationError
from test_apply_combat import start

from ai_dm.protocol.apply import apply
from ai_dm.protocol.requests import PlayerAction, parse_request
from ai_dm.protocol.schema import tool_defs

FULL = {"skill": "intimidation", "outcome": "surrender", "target": "g1"}
IMPROVISE = {"skill": "athletics", "category": "easy", "effect": "advantage"}


def action(**fields):
    return parse_request({"type": "player_action", "steps": [], **fields})


def test_parley_spec_is_kept():
    spec = action(parley=FULL).parley
    assert (spec.skill, spec.outcome, spec.target) == ("intimidation", "surrender", "g1")


def test_missing_parley_becomes_none():
    assert action().parley is None


def test_neutral_parley_becomes_none():
    assert action(parley={"skill": "none", "outcome": "none", "target": ""}).parley is None


def test_parley_without_target_is_invalid():
    with pytest.raises(ValidationError):
        action(parley={"skill": "intimidation", "outcome": "surrender", "target": ""})


def test_parley_without_skill_is_invalid():
    with pytest.raises(ValidationError):
        action(parley={"skill": "none", "outcome": "surrender", "target": "g1"})


def test_parley_without_outcome_is_invalid():
    with pytest.raises(ValidationError):
        action(parley={"skill": "deception", "outcome": "none", "target": "g1"})


def test_parley_together_with_improvise_is_invalid():
    with pytest.raises(ValidationError):
        action(parley=FULL, improvise=IMPROVISE)


def test_improvise_alone_still_works():
    request = action(improvise=IMPROVISE)
    assert request.improvise.effect == "advantage"
    assert request.parley is None


@pytest.mark.parametrize("skill", ["athletics", "stealth"])
def test_parley_rejects_a_foreign_skill(skill):
    with pytest.raises(ValidationError):
        action(parley={**FULL, "skill": skill})


def test_parley_rejects_an_unknown_outcome():
    with pytest.raises(ValidationError):
        action(parley={**FULL, "outcome": "quarrel"})


def test_parley_has_no_dc_category_field():
    with pytest.raises(ValidationError):
        action(parley={**FULL, "category": "easy"})


def test_player_action_json_roundtrip_keeps_parley():
    first = action(parley=FULL)
    again = PlayerAction.model_validate_json(first.model_dump_json(exclude_none=True))
    assert again == first


def test_handler_returns_parley_in_result(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = apply(ctx, req("player_action", steps=[], parley=FULL))
    assert d.status == "accepted"
    assert d.result["parley"] == FULL


def test_handler_has_no_parley_key_without_it(registry, cfg):
    ctx, _ = start(registry, cfg)
    d = apply(ctx, req("player_action", steps=["move:hall"]))
    assert "parley" not in d.result


def test_player_action_tool_schema_mentions_parley():
    tool = [t for t in tool_defs(["player_action"])][0]
    assert "parley" in tool["input_schema"]["properties"]
