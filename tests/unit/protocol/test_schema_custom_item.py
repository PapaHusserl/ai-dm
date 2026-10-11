# Схема инструмента give_custom_item (CUSTOM-ITEMS-PLAN, разд. 2 и 4, партия Б): строгая, все поля
# обязательны, вес/цена/количество -- числа; инструмент виден в explore, но не в боевых наборах.
import pytest

from ai_dm.protocol.schema import tool_defs, tool_set

FIELDS = ["cost_cp", "description", "name", "qty", "quest", "type", "weight_lb"]


def tool():
    return tool_defs(["give_custom_item"])[0]


def names_of(mode):
    return [t["name"] for t in tool_set(mode)]


def test_tool_is_strict_and_closed():
    spec = tool()
    assert spec["strict"] is True
    assert spec["input_schema"]["additionalProperties"] is False


def test_tool_has_all_fields_required():
    schema = tool()["input_schema"]
    assert sorted(schema["properties"]) == FIELDS
    assert sorted(schema["required"]) == FIELDS


def test_tool_field_types():
    props = tool()["input_schema"]["properties"]
    assert props["name"]["type"] == "string"
    assert props["description"]["type"] == "string"
    assert props["qty"]["type"] == "integer"
    assert props["cost_cp"]["type"] == "integer"
    assert props["weight_lb"]["type"] == "number"
    assert props["quest"]["type"] == "boolean"
    assert props["type"]["enum"] == ["give_custom_item"]


def test_tool_has_a_description_in_russian():
    assert any("а" <= ch <= "я" for ch in tool()["description"].lower())


def test_explore_has_the_tool():
    assert "give_custom_item" in names_of("explore")


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate", "npc_choice"])
def test_combat_modes_do_not_have_the_tool(mode):
    assert "give_custom_item" not in names_of(mode)
