# Схема и запрос trade (TRADE-PLAN, разд. 3): цену мастер не передаёт (лишнее поле -> ошибка схемы),
# все поля обязательны для модели, quality "any" внутри None, инструмент виден в explore, но не в
# боевых наборах, обработчик зарегистрирован.
import pytest
from protocol_kit import req
from pydantic import ValidationError

from ai_dm.protocol.apply import HANDLERS
from ai_dm.protocol.requests import (
    REQUEST_MODELS,
    VISIBLE_TYPES,
    Haggle,
    Trade,
    parse_request,
)
from ai_dm.protocol.schema import tool_defs, tool_set

FIELDS = ["category", "direction", "item_id", "npc_id", "qty", "quality", "type"]


def tool():
    return tool_defs(["trade"])[0]


def names_of(mode):
    return [t["name"] for t in tool_set(mode)]


def trade_req(**fields):
    data = {"npc_id": "mara", "direction": "buy", "item_id": "arrows", "qty": 1}
    data.update(fields)
    return req("trade", **data)


def test_request_model_is_registered():
    assert REQUEST_MODELS["trade"] is Trade


def test_trade_is_a_visible_request():
    assert "trade" in VISIBLE_TYPES


def test_handler_is_registered():
    assert "trade" in HANDLERS


def test_price_field_is_not_allowed():
    with pytest.raises(ValidationError):
        trade_req(price=1000)


def test_total_field_is_not_allowed():
    with pytest.raises(ValidationError):
        trade_req(total_cp=1000)


def test_unknown_direction_is_not_allowed():
    with pytest.raises(ValidationError):
        trade_req(direction="steal")


def test_unknown_quality_is_not_allowed():
    with pytest.raises(ValidationError):
        trade_req(quality="shiny")


@pytest.mark.parametrize("field", ["npc_id", "direction", "item_id", "qty"])
def test_required_fields(field):
    data = {"type": "trade", "npc_id": "mara", "direction": "buy", "item_id": "arrows", "qty": 1}
    del data[field]
    with pytest.raises(ValidationError):
        parse_request(data)


def test_quality_any_becomes_none():
    assert trade_req(quality="any").quality is None


def test_quality_default_is_any():
    assert trade_req().quality is None


@pytest.mark.parametrize("quality", ["junk", "worn", "used", "new"])
def test_other_qualities_stay(quality):
    assert trade_req(quality=quality).quality == quality


def test_tool_is_strict_and_closed():
    spec = tool()
    assert spec["strict"] is True
    assert spec["input_schema"]["additionalProperties"] is False


def test_tool_has_all_fields_required_and_no_price():
    schema = tool()["input_schema"]
    assert sorted(schema["properties"]) == FIELDS
    assert sorted(schema["required"]) == FIELDS


def test_tool_field_types():
    props = tool()["input_schema"]["properties"]
    assert props["npc_id"]["type"] == "string"
    assert props["item_id"]["type"] == "string"
    assert props["qty"]["type"] == "integer"
    assert props["direction"]["enum"] == ["buy", "sell", "list"]
    assert props["quality"]["enum"] == ["junk", "worn", "used", "new", "any"]
    assert props["type"]["enum"] == ["trade"]


def test_tool_has_a_description_in_russian():
    assert any("а" <= ch <= "я" for ch in tool()["description"].lower())


def test_explore_has_the_tool():
    assert "trade" in names_of("explore")


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate", "npc_choice"])
def test_combat_modes_do_not_have_the_tool(mode):
    assert "trade" not in names_of(mode)


def test_world_role_does_not_have_the_tool():
    assert "trade" not in names_of("world")


def test_npc_create_trade_kind_none_becomes_none():
    request = req("npc_create", id="a", name="А", means=["х"], trade_kind="none")
    assert request.trade_kind is None


def test_npc_create_trade_kind_stays():
    request = req("npc_create", id="a", name="А", means=["х"], trade_kind="smith")
    assert request.trade_kind == "smith"


def test_npc_update_trade_kind_none_becomes_none():
    assert req("npc_update", npc_id="a", trade_kind="none").trade_kind is None


def test_npc_update_trade_kind_stays():
    assert req("npc_update", npc_id="a", trade_kind="smith").trade_kind == "smith"


def test_trade_kind_is_required_in_the_npc_tools():
    for name in ("npc_create", "npc_update"):
        schema = tool_defs([name])[0]["input_schema"]
        assert "trade_kind" in schema["properties"]
        assert "trade_kind" in schema["required"]


def test_take_item_tool_has_holder_npc_id():
    schema = tool_defs(["take_item"])[0]["input_schema"]
    assert "holder_npc_id" in schema["properties"]
    assert "holder_npc_id" in schema["required"]


def test_world_role_npc_update_has_no_trade_kind():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert "trade_kind" not in schema["properties"]
    assert "trade_kind" not in schema["required"]


def test_world_role_npc_update_keeps_its_own_fields():
    schema = tool_defs(["npc_update"], "world")[0]["input_schema"]
    assert "then_ref" in schema["properties"]
    assert "location_id" in schema["properties"]


def test_category_is_optional_in_requests_and_neutral_becomes_none():
    assert trade_req().category is None
    assert trade_req(direction="list", item_id="", qty=0, category="weapon").category == "weapon"


# торг Убеждением (партия Т5): инструмент haggle, поля только type и npc_id

HAGGLE_FIELDS = ["npc_id", "type"]


def haggle_tool():
    return tool_defs(["haggle"])[0]


def test_haggle_request_model_is_registered():
    assert REQUEST_MODELS["haggle"] is Haggle


def test_haggle_is_a_visible_request():
    assert "haggle" in VISIBLE_TYPES


def test_haggle_handler_is_registered():
    assert "haggle" in HANDLERS


def test_haggle_tool_has_only_type_and_npc_id():
    schema = haggle_tool()["input_schema"]
    assert sorted(schema["properties"]) == HAGGLE_FIELDS
    assert sorted(schema["required"]) == HAGGLE_FIELDS


def test_haggle_tool_is_strict_and_closed():
    spec = haggle_tool()
    assert spec["strict"] is True
    assert spec["input_schema"]["additionalProperties"] is False


def test_haggle_type_enum():
    assert haggle_tool()["input_schema"]["properties"]["type"]["enum"] == ["haggle"]


def test_haggle_tool_has_a_description_in_russian():
    assert any("а" <= ch <= "я" for ch in haggle_tool()["description"].lower())


@pytest.mark.parametrize("field", ["skill", "category", "dc", "percent"])
def test_haggle_cannot_choose_difficulty_or_percent(field):
    with pytest.raises(ValidationError):
        req("haggle", npc_id="mara", **{field: 1})


def test_haggle_requires_npc_id():
    with pytest.raises(ValidationError):
        parse_request({"type": "haggle"})


def test_haggle_is_in_explore():
    assert "haggle" in names_of("explore")


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate", "npc_choice"])
def test_haggle_is_not_in_combat_modes(mode):
    assert "haggle" not in names_of(mode)


def test_haggle_is_not_in_world_role():
    assert "haggle" not in names_of("world")
