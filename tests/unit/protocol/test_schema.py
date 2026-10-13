# Ожидаемый API: ai_dm.protocol.schema.tool_defs(exposed) -- см. контракт в protocol_kit.py.
# Strict-линтер (STAGE2-PLAN A0/A2, S1/S3 ревью партии 2): на всех уровнях additionalProperties:
# false, все свойства в required, union нет нигде (необязательные поля -- обязательные не-nullable
# с нейтральным значением, Pydantic нормализует их в None), нет $ref/$defs/definitions, нет
# ограничений,
# которые strict не принимает (minimum/maximum/minLength/maxLength/maxItems/uniqueItems/default,
# minItems > 1). Описания непустые и русские. Порядок инструментов -- по имени, байты стабильны.
# Видимый набор этапа 2 -- из плана; инструмента лечения нет; npc_action -- отдельно.
import json
import re

import pytest

from ai_dm.protocol import schema
from ai_dm.protocol.requests import (
    ALL_TYPES,
    HIDDEN_TYPES,
    NPC_ONLY_TYPES,
    REQUEST_MODELS,
    VISIBLE_TYPES,
    parse_request,
)
from ai_dm.protocol.schema import tool_defs, tool_set

BANNED = [
    "$ref", "$defs", "definitions", "minimum", "maximum", "exclusiveMinimum", "exclusiveMaximum",
    "multipleOf", "minLength", "maxLength", "maxItems", "uniqueItems", "default",
]
CYRILLIC = re.compile("[а-яА-ЯёЁ]")


def all_tools():
    return tool_defs(ALL_TYPES)


def by_name(name):
    return tool_defs([name])[0]


def walk(node, path="$"):
    # все узлы схемы: (путь, узел-словарь)
    if isinstance(node, dict):
        yield path, node
        for key, value in node.items():
            yield from walk(value, f"{path}.{key}")
    elif isinstance(node, list):
        for i, value in enumerate(node):
            yield from walk(value, f"{path}[{i}]")


def is_object(node):
    kind = node.get("type")
    return kind == "object" or (isinstance(kind, list) and "object" in kind)


def allows_null(prop):
    kind = prop.get("type")
    if kind == "null" or (isinstance(kind, list) and "null" in kind):
        return True
    return any(
        isinstance(option, dict) and option.get("type") == "null"
        for option in prop.get("anyOf", [])
    )


def test_tool_shape():
    for tool in all_tools():
        assert sorted(tool) == ["description", "input_schema", "name", "strict"]
        assert tool["strict"] is True
        assert tool["input_schema"]["type"] == "object"


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_name_matches_type(type_name):
    tool = by_name(type_name)
    assert tool["name"] == type_name
    assert tool["input_schema"]["properties"]["type"]["enum"] == [type_name]


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_every_object_is_closed_and_fully_required(type_name):
    for path, node in walk(by_name(type_name)["input_schema"]):
        if is_object(node) and "properties" in node:
            assert node.get("additionalProperties") is False, path
            assert sorted(node.get("required", [])) == sorted(node["properties"]), path


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_no_refs_or_unsupported_keywords(type_name):
    for path, node in walk(by_name(type_name)["input_schema"]):
        for word in BANNED:
            assert word not in node, f"{path}: {word}"
        if "minItems" in node:
            assert node["minItems"] in (0, 1), path


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_no_field_allows_null_anywhere(type_name):
    for path, node in walk(by_name(type_name)["input_schema"]):
        assert not allows_null(node), path
        assert "anyOf" not in node, path
        assert "oneOf" not in node, path
        assert "allOf" not in node, path
        assert not isinstance(node.get("type"), list), path


def test_schema_properties_match_model_fields():
    for type_name in ALL_TYPES:
        properties = by_name(type_name)["input_schema"]["properties"]
        assert sorted(properties) == sorted(REQUEST_MODELS[type_name].model_fields)


def test_nested_models_are_inlined_in_start_combat():
    schema = by_name("start_combat")["input_schema"]
    enemies = schema["properties"]["enemies"]
    assert enemies["type"] == "array"
    assert enemies["items"]["type"] == "object"
    assert "ref" in enemies["items"]["properties"]


def test_failed_roll_ref_in_damage_is_plain_string_with_empty_as_none():
    prop = by_name("damage")["input_schema"]["properties"]["failed_roll_ref"]
    assert prop["type"] == "string"
    assert not allows_null(prop)
    assert parse_request(
        {"type": "damage", "severity": "nuisance", "damage_type": "fire", "failed_roll_ref": ""}
    ).failed_roll_ref is None


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_descriptions_are_non_empty_and_russian(type_name):
    tool = by_name(type_name)
    assert CYRILLIC.search(tool["description"])
    for name, prop in tool["input_schema"]["properties"].items():
        if name == "type":
            continue
        assert prop.get("description", "").strip(), name


def test_tools_are_sorted_by_name():
    names = [t["name"] for t in all_tools()]
    assert names == sorted(names)


def test_order_does_not_depend_on_input_order():
    forward = [t["name"] for t in tool_defs(list(VISIBLE_TYPES))]
    backward = [t["name"] for t in tool_defs(list(reversed(VISIBLE_TYPES)))]
    assert forward == backward == sorted(VISIBLE_TYPES)


def test_bytes_are_stable_between_calls():
    first = json.dumps(tool_defs(VISIBLE_TYPES), ensure_ascii=False)
    second = json.dumps(tool_defs(VISIBLE_TYPES), ensure_ascii=False)
    assert first == second


def test_bytes_do_not_depend_on_input_order():
    first = json.dumps(tool_defs(list(VISIBLE_TYPES)), ensure_ascii=False)
    second = json.dumps(tool_defs(list(reversed(VISIBLE_TYPES))), ensure_ascii=False)
    assert first == second


def test_returned_tools_are_fresh_copies():
    tools = tool_defs(VISIBLE_TYPES)
    tools[0]["description"] = "испорчено"
    assert tool_defs(VISIBLE_TYPES)[0]["description"] != "испорчено"


MODES = ["explore", "combat_classify", "combat_narrate", "npc_choice"]
STRICT_BANNED = ["$ref", "minimum", "maximum", "multipleOf", "minLength", "maxLength", "maxItems"]


def mode_tools(mode):
    # tool_set отдаёт имена или готовые определения: приводим к определениям
    items = list(tool_set(mode))
    if items and isinstance(items[0], str):
        return tool_defs(items)
    return items


def strict_tools(mode):
    return [tool for tool in mode_tools(mode) if tool["strict"]]


# S3: сторож лимитов strict-схем по режимам (docs/llm-notes/claude-api-facts.md)

@pytest.mark.parametrize("mode", MODES)
def test_mode_has_at_most_20_strict_tools(mode):
    assert len(strict_tools(mode)) <= 20


@pytest.mark.parametrize("mode", MODES)
def test_mode_set_is_not_empty_and_has_unique_known_names(mode):
    names = [tool["name"] for tool in mode_tools(mode)]
    assert names
    assert len(names) == len(set(names))
    assert set(names) <= set(REQUEST_MODELS)


@pytest.mark.parametrize("mode", MODES)
def test_mode_has_no_union_parameters(mode):
    for tool in strict_tools(mode):
        for path, node in walk(tool["input_schema"]):
            assert "anyOf" not in node, f"{tool['name']} {path}"
            assert not isinstance(node.get("type"), list), f"{tool['name']} {path}"


@pytest.mark.parametrize("mode", MODES)
def test_mode_has_no_optional_parameters(mode):
    for tool in strict_tools(mode):
        for path, node in walk(tool["input_schema"]):
            if "properties" in node:
                assert sorted(node.get("required", [])) == sorted(node["properties"]), (
                    f"{tool['name']} {path}"
                )


@pytest.mark.parametrize("mode", MODES)
def test_mode_has_no_unsupported_keywords(mode):
    for tool in strict_tools(mode):
        for path, node in walk(tool["input_schema"]):
            for word in STRICT_BANNED:
                assert word not in node, f"{tool['name']} {path}: {word}"
            if "additionalProperties" in node:
                assert node["additionalProperties"] is False, f"{tool['name']} {path}"


@pytest.mark.parametrize("mode", MODES)
def test_mode_has_no_union_even_through_null_type(mode):
    for tool in strict_tools(mode):
        for path, node in walk(tool["input_schema"]):
            assert not allows_null(node), f"{tool['name']} {path}"


# S2: наборы по режимам

def names_of(mode):
    return sorted(tool["name"] for tool in mode_tools(mode))


def test_combat_classify_set():
    assert names_of("combat_classify") == ["player_action", "unsupported_action"]


def test_combat_narrate_set():
    assert names_of("combat_narrate") == ["defeat_outcome", "end_combat", "offer_choices"]


def test_npc_choice_set():
    assert names_of("npc_choice") == ["npc_action"]


def test_explore_set_is_visible_minus_combat_only_tools():
    names = names_of("explore")
    for name in ("skill_check", "saving_throw", "start_combat", "damage", "give_item", "take_item",
                 "gold", "award_xp", "advance_time", "rest", "npc_create", "npc_update",
                 "offer_choices", "end_scene", "unsupported_action"):
        assert name in names
    for name in ("player_action", "npc_action", "defeat_outcome", "end_combat"):
        assert name not in names
    for hidden in HIDDEN_TYPES:
        assert hidden not in names


def test_explore_set_has_at_most_16_strict_tools():
    assert len(strict_tools("explore")) <= 16


@pytest.mark.parametrize("mode", MODES)
def test_mode_tools_are_sorted_and_stable(mode):
    names = [tool["name"] for tool in mode_tools(mode)]
    assert names == sorted(names)
    assert json.dumps(mode_tools(mode)) == json.dumps(mode_tools(mode))


def test_unknown_mode_is_error():
    with pytest.raises((ValueError, KeyError)):
        tool_set("flying")


def test_visible_set_has_33_tools_from_plan():
    names = [t["name"] for t in tool_defs(VISIBLE_TYPES)]
    assert len(names) == 33
    assert names == sorted(VISIBLE_TYPES)
    assert "npc_action" not in names
    for hidden in HIDDEN_TYPES:
        assert hidden not in names


def test_npc_action_is_available_separately():
    tools = tool_defs(NPC_ONLY_TYPES)
    assert [t["name"] for t in tools] == ["npc_action"]
    assert "npc_action" not in VISIBLE_TYPES


def test_hidden_schemas_exist_and_are_strict_too():
    tools = tool_defs(HIDDEN_TYPES)
    assert len(tools) == 1
    for tool in tools:
        assert tool["input_schema"]["additionalProperties"] is False


def test_no_heal_tool_anywhere():
    for tool in all_tools():
        assert "heal" not in tool["name"]
    assert "heal" not in [t["name"] for t in tool_defs(VISIBLE_TYPES)]


def test_unknown_tool_name_is_error():
    with pytest.raises(ValueError):
        tool_defs(["teleport"])


def test_empty_exposed_gives_empty_list():
    assert tool_defs([]) == []


# этап 3, партия 3: reveal_secret открыт в explore без strict (STAGE3-PLAN A10, Т-17)

def test_reveal_secret_is_in_explore_set_and_not_strict():
    tools = {t["name"]: t for t in tool_set("explore")}
    assert "reveal_secret" in tools
    assert tools["reveal_secret"]["strict"] is False


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate", "npc_choice"])
def test_reveal_secret_is_not_in_combat_modes(mode):
    assert "reveal_secret" not in [t["name"] for t in tool_set(mode)]


def test_no_empty_string_in_any_enum():
    # Gemini отвергает пустую строку в enum (живой прогон: npc_update.follows)
    def walk(node, path, out):
        if isinstance(node, dict):
            if "" in node.get("enum", []):
                out.append(path)
            for key, value in node.items():
                walk(value, f"{path}.{key}", out)
        elif isinstance(node, list):
            for i, value in enumerate(node):
                walk(value, f"{path}[{i}]", out)

    bad = []
    for mode in schema.MODE_TOOLS:
        for tool in schema.tool_set(mode):
            walk(tool, f"{mode}:{tool['name']}", bad)
    assert bad == []
