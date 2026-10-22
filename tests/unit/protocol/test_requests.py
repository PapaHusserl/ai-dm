# Ожидаемый API: ai_dm.protocol.requests -- см. контракт в protocol_kit.py (шапка).
# Модели запросов ТЗ 2.1 (все 28, включая скрытые): валидный пример, JSON-цикл, extra="forbid",
# union MasterRequest по полю type, неизвестный type -> ValidationError, свободного heal нет.
import copy
import json

import pytest
from pydantic import TypeAdapter, ValidationError

from ai_dm.protocol.requests import (
    ALL_TYPES,
    HIDDEN_TYPES,
    NPC_ONLY_TYPES,
    REQUEST_MODELS,
    VISIBLE_TYPES,
    MasterRequest,
    parse_request,
)
from ai_dm.protocol.schema import tool_defs

VALID = {
    "skill_check": {"skill": "persuasion", "category": "medium"},
    "saving_throw": {"ability": "dex", "category": "hard", "stakes": "critical"},
    "start_combat": {
        "zones": [
            {"id": "door", "name": "У двери", "adjacent": ["hall"]},
            {
                "id": "hall", "name": "Зал", "adjacent": ["door"], "exit": False,
                "features": [{"kind": "cover_half"}],
            },
        ],
        "enemies": [{"ref": "g1", "monster_id": "goblin_warrior", "zone": "hall", "group": "gob"}],
        "groups": [{"id": "gob", "leader": "g1", "intent": "capture"}],
        "hero_zone": "door",
    },
    "player_action": {
        "steps": ["attack:longsword:g1"],
        "improvise": {"skill": "athletics", "category": "easy", "effect": "advantage"},
    },
    "npc_action": {"choice": "attack:scimitar:hero"},
    "defeat_outcome": {"consequences": ["rob", "scar"], "scar_ability": "str", "scar_text": "шрам"},
    "end_combat": {"reason": "враги сдались"},
    "damage": {"severity": "deadly", "damage_type": "fire", "failed_roll_ref": "r1"},
    "curse": {"failed_roll_ref": "r1", "cause": "проклятый оберег на алтаре"},
    "give_item": {"item_id": "potion_of_healing", "qty": 2},
    "give_custom_item": {
        "name": "Ржавый ключ", "description": "Ключ от ворот", "qty": 1, "weight_lb": 0.5,
        "cost_cp": 300, "quest": True,
    },
    "use_item": {"item_id": "potion_of_healing", "qty": 1},
    "cast_spell": {"spell_id": "cure_wounds", "circle": 1, "target": "hero", "free": False},
    "take_item": {"item_id": "crowbar", "qty": 1, "why": "lost"},
    "trade": {"npc_id": "mara", "direction": "buy", "item_id": "arrows", "qty": 2},
    "haggle": {"npc_id": "mara"},
    "service": {"npc_id": "grok", "direction": "buy", "service_id": "meal_modest", "qty": 2},
    "gold": {"direction": "gain", "kind": "loot_individual", "cr": "1/4"},
    "award_xp": {"scale": "medium", "reason": "нашёл тайник"},
    "advance_time": {"travel_to": "forest", "pace": "slow"},
    "rest": {"kind": "short", "hit_dice": 1},
    "warn_danger": {"location_id": "goblin_den", "text": "кости у входа"},
    "set_flag": {"name": "met_aldric", "value": "true"},
    "npc_create": {"id": "brana", "name": "Бранка", "means": ["кузница"], "named": True},
    "location_create": {
        "id": "cellar", "name": "Подвал", "parent_id": "vale_tavern",
        "connections": [{"to": "vale_tavern", "distance_m": 10}],
    },
    "npc_update": {
        "npc_id": "aldric", "status": "dead", "cause": "goal", "evidence_ref": "r1",
    },
    "favor_change": {"target": "hero", "god_id": "morrah", "delta": 1, "reason": "помог жрецу"},
    "pray": {"god_id": "selune"},
    "change_deity": {"god_id": "morrah", "reason": "сделка с жрецом"},
    "companion_update": {"action": "join", "name": "Акела", "kind": "волк"},
    "reveal_secret": {"npc_id": "aldric", "secret_id": "sister_vampire"},
    "knowledge_note": {
        "kind": "npc", "ref": "aldric", "text": "Хранит ключ от склепа", "source": "told",
        "from_ref": "mira",
    },
    "scene_mood": {"mood": "romance"},
    "event_start": {"id": "plague_1", "event_type": "plague", "cause": "trigger:morrah"},
    "event_end": {"id": "plague_1"},
    "offer_choices": {"choices": ["Войти", "Уйти"]},
    "end_scene": {"summary": "разговор окончен"},
    "end_chapter": {"title": "Глава 1"},
    "afterlife_action": {"kind": "short"},
    "unsupported_action": {"description": "игрок хочет приручить дракона"},
}


def example(type_name):
    return {"type": type_name, **copy.deepcopy(VALID[type_name])}


def test_there_are_40_request_types():
    assert len(ALL_TYPES) == 40
    assert sorted(REQUEST_MODELS) == sorted(ALL_TYPES)


def test_examples_cover_every_type():
    assert sorted(VALID) == sorted(ALL_TYPES)


def test_visible_hidden_and_npc_only_partition_all_types():
    assert len(VISIBLE_TYPES) == 38
    assert sorted(HIDDEN_TYPES) == ["afterlife_action"]
    assert NPC_ONLY_TYPES == ("npc_action",)
    assert sorted(VISIBLE_TYPES + HIDDEN_TYPES + NPC_ONLY_TYPES) == sorted(ALL_TYPES)


def test_visible_set_matches_plan():
    plan = [
        "skill_check", "saving_throw", "start_combat", "player_action", "defeat_outcome",
        "end_combat", "damage", "curse", "give_item", "give_custom_item", "use_item", "take_item",
        "gold", "trade", "haggle", "service", "award_xp",
        "advance_time",
        "rest", "set_flag", "npc_create", "location_create", "npc_update", "offer_choices",
        "end_scene", "end_chapter", "unsupported_action", "reveal_secret", "event_start",
        "event_end", "favor_change", "pray", "change_deity", "warn_danger", "cast_spell",
        "companion_update", "knowledge_note", "scene_mood",
    ]
    assert sorted(VISIBLE_TYPES) == sorted(plan)


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_valid_example_parses_to_its_model(type_name):
    model = parse_request(example(type_name))
    assert type(model) is REQUEST_MODELS[type_name]
    assert model.type == type_name


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_json_roundtrip_keeps_request(type_name):
    first = parse_request(example(type_name))
    # после нормализации «нет» хранится как None, а в JSON для модели его нет: None не пишем
    text = first.model_dump_json(exclude_none=True)
    again = TypeAdapter(MasterRequest).validate_json(text)
    assert again == first
    assert json.loads(again.model_dump_json()) == json.loads(first.model_dump_json())


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_extra_field_is_forbidden(type_name):
    with pytest.raises(ValidationError):
        parse_request({**example(type_name), "bogus": 1})


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_model_itself_forbids_extra(type_name):
    with pytest.raises(ValidationError):
        REQUEST_MODELS[type_name](**example(type_name), bogus=1)


@pytest.mark.parametrize("type_name", ALL_TYPES)
def test_missing_type_is_error(type_name):
    data = example(type_name)
    del data["type"]
    with pytest.raises(ValidationError):
        parse_request(data)


def test_unknown_type_is_error():
    with pytest.raises(ValidationError):
        parse_request({"type": "teleport", "where": "moon"})


def test_union_adapter_rejects_unknown_type():
    with pytest.raises(ValidationError):
        TypeAdapter(MasterRequest).validate_python({"type": "teleport"})


def test_there_is_no_heal_request():
    assert "heal" not in REQUEST_MODELS
    with pytest.raises(ValidationError):
        parse_request({"type": "heal", "amount": 10})
    assert not any("heal" in name for name in ALL_TYPES)


def test_skill_check_unknown_skill_is_error():
    with pytest.raises(ValidationError):
        parse_request({"type": "skill_check", "skill": "juggling", "category": "easy"})


def test_skill_check_dc_only_by_category():
    # СЛ числом назвать нельзя: поле dc лишнее, категория -- Literal
    with pytest.raises(ValidationError):
        parse_request({"type": "skill_check", "skill": "stealth", "category": "easy", "dc": 5})
    with pytest.raises(ValidationError):
        parse_request({"type": "skill_check", "skill": "stealth", "category": "15"})


def test_skill_check_stakes_is_optional_and_defaults_to_none():
    model = parse_request({"type": "skill_check", "skill": "stealth", "category": "easy"})
    assert model.stakes is None


def test_damage_severity_is_literal():
    with pytest.raises(ValidationError):
        parse_request({"type": "damage", "severity": "mega", "damage_type": "fire"})


def test_damage_failed_roll_ref_is_optional():
    model = parse_request({"type": "damage", "severity": "deadly", "damage_type": "fire"})
    assert model.failed_roll_ref is None


def test_set_flag_value_is_a_single_string_type():
    assert parse_request({"type": "set_flag", "name": "a", "value": "true"}).value == "true"
    assert parse_request({"type": "set_flag", "name": "a", "value": "x"}).value == "x"
    with pytest.raises(ValidationError):
        parse_request({"type": "set_flag", "name": "a", "value": 3})


def test_start_combat_intent_must_be_known():
    data = example("start_combat")
    data["groups"] = [{"id": "gob", "leader": "g1", "intent": "annihilate"}]
    with pytest.raises(ValidationError):
        parse_request(data)


def test_start_combat_requires_zones_enemies_groups():
    for field in ("zones", "enemies", "groups", "hero_zone"):
        data = example("start_combat")
        del data[field]
        with pytest.raises(ValidationError):
            parse_request(data)


def test_start_combat_nested_extra_is_forbidden():
    data = example("start_combat")
    data["enemies"][0]["hp"] = 100
    with pytest.raises(ValidationError):
        parse_request(data)


def test_advance_time_all_fields_optional():
    model = parse_request({"type": "advance_time"})
    assert model.category is None and model.travel_to is None
    assert model.pace in (None, "normal")


def test_advance_time_category_and_pace_are_literals():
    with pytest.raises(ValidationError):
        parse_request({"type": "advance_time", "category": "fortnight"})
    with pytest.raises(ValidationError):
        parse_request({"type": "advance_time", "travel_to": "forest", "pace": "teleport"})


def test_npc_update_status_is_dead_or_gone():
    with pytest.raises(ValidationError):
        parse_request({"type": "npc_update", "npc_id": "a", "status": "sleeping"})


def test_npc_update_cause_is_closed_list():
    with pytest.raises(ValidationError):
        parse_request({"type": "npc_update", "npc_id": "a", "status": "dead", "cause": "whim"})


def test_gold_direction_and_kind_are_literals():
    with pytest.raises(ValidationError):
        parse_request({"type": "gold", "direction": "steal", "kind": "explicit"})
    with pytest.raises(ValidationError):
        parse_request({"type": "gold", "direction": "gain", "kind": "magic"})


def test_award_xp_scale_is_literal():
    with pytest.raises(ValidationError):
        parse_request({"type": "award_xp", "scale": "huge", "reason": "x"})


# S1: необязательные поля в схеме -- обязательные не-nullable с нейтральным значением, а модель
# при разборе нормализует нейтральное значение в None (внутренний API протокола прежний).
# Какие поля необязательные -- по контракту (protocol_kit.py); нейтральное значение берём из схемы.

OPTIONAL_FIELDS = {
    "skill_check": ["stakes"],
    "saving_throw": ["stakes"],
    "player_action": ["unsupported"],
    "defeat_outcome": [
        "lair_location_id", "scar_ability", "scar_skill", "scar_text", "debt_to", "debt_text",
        "rob_items",
    ],
    "end_combat": ["reason"],
    "damage": ["failed_roll_ref"],
    "gold": ["amount_cp", "cr"],
    "advance_time": ["category", "travel_to", "pace"],
    "rest": ["hit_dice", "prey_swap"],  # prepared_swap -- вложенный объект: см. тесты cut_swap ниже
    "npc_create": ["named", "key", "motive", "location_id"],
    "location_create": ["parent_id", "description", "connections"],
    "npc_update": ["attitude_delta", "status", "cause", "evidence_ref", "by", "text"],
    "event_start": ["cause", "regions"],
    "end_scene": ["summary"],
    "end_chapter": ["title"],
}
OPTIONAL_CASES = [(name, field) for name, fields in OPTIONAL_FIELDS.items() for field in fields]
EMPTY = (None, [], False)


def candidates(prop):
    # возможные нейтральные значения поля по его схеме
    if "enum" in prop:
        return list(prop["enum"])
    return [{"string": "", "boolean": False, "integer": 0, "array": []}[prop["type"]]]


@pytest.mark.parametrize("type_name, field", OPTIONAL_CASES)
def test_optional_field_has_neutral_value_that_becomes_none(type_name, field):
    prop = tool_defs([type_name])[0]["input_schema"]["properties"][field]
    results = []
    for value in candidates(prop):
        model = parse_request({**example(type_name), field: value})
        results.append(getattr(model, field))
    assert any(result in EMPTY or result == "normal" for result in results), (field, results)


@pytest.mark.parametrize("field", ["lair_location_id", "scar_text", "debt_to", "debt_text"])
def test_defeat_outcome_empty_string_is_none(field):
    model = parse_request({**example("defeat_outcome"), field: ""})
    assert getattr(model, field) is None


def test_defeat_outcome_rob_items_zero_is_none():
    assert parse_request({**example("defeat_outcome"), "rob_items": 0}).rob_items is None


def test_skill_check_stakes_normal_is_none():
    model = parse_request({**example("skill_check"), "stakes": "normal"})
    assert model.stakes is None


def test_skill_check_stakes_critical_stays():
    assert parse_request({**example("skill_check"), "stakes": "critical"}).stakes == "critical"


def test_saving_throw_stakes_normal_is_none():
    assert parse_request({**example("saving_throw"), "stakes": "normal"}).stakes is None


def test_advance_time_pace_normal_is_none():
    # normal -- нейтральное: допустимо и None, и остаться "normal" (обработчик берёт normal)
    model = parse_request({"type": "advance_time", "category": "hour", "pace": "normal"})
    assert model.pace in (None, "normal")


def test_advance_time_travel_to_empty_is_none():
    model = parse_request({**example("advance_time"), "pace": "normal", "travel_to": ""})
    assert model.travel_to is None


def test_advance_time_travel_to_none_string_is_none():
    model = parse_request({"type": "advance_time", "category": "hour", "travel_to": "none"})
    assert model.travel_to is None
    assert model.category == "hour"


def test_advance_time_travel_to_real_location_is_kept():
    model = parse_request({"type": "advance_time", "category": "none", "travel_to": "forest"})
    assert model.travel_to == "forest"


def test_rest_hit_dice_zero_is_none():
    assert parse_request({"type": "rest", "kind": "short", "hit_dice": 0}).hit_dice is None


def test_rest_hit_dice_positive_stays():
    assert parse_request({"type": "rest", "kind": "short", "hit_dice": 2}).hit_dice == 2


def test_gold_neutral_amount_and_cr_are_none():
    model = parse_request(
        {"type": "gold", "direction": "gain", "kind": "explicit", "amount_cp": 0, "cr": ""}
    )
    assert model.amount_cp is None
    assert model.cr is None


def test_npc_update_neutral_values_are_none():
    model = parse_request({
        "type": "npc_update", "npc_id": "aldric", "attitude_delta": 5, "evidence_ref": "",
        "by": "", "text": "",
    })
    assert model.evidence_ref is None
    assert model.by is None
    assert model.text is None
    assert model.attitude_delta == 5


def test_npc_update_zero_delta_is_none():
    model = parse_request(
        {"type": "npc_update", "npc_id": "aldric", "attitude_delta": 0, "evidence_ref": "r1"}
    )
    assert model.attitude_delta is None


def test_npc_create_neutral_values_are_falsy_or_none():
    model = parse_request({
        "type": "npc_create", "id": "x", "name": "Х", "means": ["m"], "named": False, "key": False,
        "motive": "", "location_id": "",
    })
    assert not model.named
    assert not model.key
    assert model.motive is None
    assert model.location_id is None


def test_location_create_neutral_values_are_none_or_empty():
    model = parse_request({
        "type": "location_create", "id": "x", "name": "Х", "parent_id": "", "description": "",
        "connections": [],
    })
    assert model.parent_id is None
    assert model.description is None
    assert model.connections in (None, [])


def test_end_scene_and_end_chapter_empty_text_is_none():
    assert parse_request({"type": "end_scene", "summary": ""}).summary is None
    assert parse_request({"type": "end_chapter", "title": ""}).title is None


def test_end_combat_empty_reason_is_none():
    assert parse_request({"type": "end_combat", "reason": ""}).reason is None


def test_player_action_empty_unsupported_is_none():
    model = parse_request({"type": "player_action", "steps": ["end_turn"], "unsupported": ""})
    assert model.unsupported is None


def test_start_combat_nested_neutral_values():
    data = example("start_combat")
    data["zones"][0]["exit"] = False
    data["zones"][0]["features"] = []
    data["enemies"][0]["name"] = ""
    data["groups"][0]["lair_location_id"] = ""
    model = parse_request(data)
    assert not model.zones[0].exit
    assert model.zones[0].features in (None, [])
    assert model.enemies[0].name is None
    assert model.groups[0].lair_location_id is None


def test_start_combat_feature_neutral_values_are_none():
    data = example("start_combat")
    data["zones"][1]["features"] = [
        {"kind": "cover_half", "damage": "", "damage_type": "", "dc": 0}
    ]
    schema = tool_defs(["start_combat"])[0]["input_schema"]
    feature = schema["properties"]["zones"]["items"]["properties"]["features"]["items"]
    results = []
    for value in candidates(feature["properties"]["save"]):
        data["zones"][1]["features"][0]["save"] = value
        results.append(parse_request(data).zones[1].features[0])
    assert any(
        f.damage is None and f.damage_type is None and f.dc is None and f.save is None
        for f in results
    )


def test_schema_has_no_union_for_start_combat_nested_fields():
    schema = tool_defs(["start_combat"])[0]["input_schema"]
    zone = schema["properties"]["zones"]["items"]["properties"]
    assert "anyOf" not in zone["exit"]
    assert zone["exit"]["type"] == "boolean"
    assert zone["features"]["type"] == "array"


def test_take_item_without_why_is_error():
    with pytest.raises(ValidationError):
        parse_request({"type": "take_item", "item_id": "crowbar", "qty": 1})


def test_take_item_unknown_why_is_error():
    with pytest.raises(ValidationError):
        parse_request({"type": "take_item", "item_id": "crowbar", "qty": 1, "why": "eaten"})


@pytest.mark.parametrize("why", ["given", "lost", "stolen", "spent"])
def test_take_item_accepts_each_why(why):
    model = parse_request({"type": "take_item", "item_id": "crowbar", "qty": 1, "why": why})
    assert model.why == why


# К1: rest.prepared_swap -- вложенная необязательная модель; оба списка пусты -> None (cut_swap)

def test_rest_without_prepared_swap_has_none():
    assert parse_request({"type": "rest", "kind": "long"}).prepared_swap is None


def test_rest_with_empty_prepared_swap_has_none():
    data = {"type": "rest", "kind": "long", "prepared_swap": {"drop": [], "take": []}}
    assert parse_request(data).prepared_swap is None


def test_rest_with_drop_keeps_the_swap_object():
    data = {"type": "rest", "kind": "long", "prepared_swap": {"drop": ["fog_cloud"], "take": []}}
    swap = parse_request(data).prepared_swap
    assert (swap.drop, swap.take) == (["fog_cloud"], [])


def test_rest_with_take_only_keeps_the_swap_object():
    data = {"type": "rest", "kind": "long", "prepared_swap": {"drop": [], "take": ["alarm"]}}
    assert parse_request(data).prepared_swap.take == ["alarm"]


def test_rest_prepared_swap_lists_default_to_empty():
    swap = parse_request({"type": "rest", "kind": "long", "prepared_swap": {"drop": ["a"]}})
    assert swap.prepared_swap.take == []


def test_rest_prepared_swap_rejects_unknown_fields():
    data = {"type": "rest", "kind": "long", "prepared_swap": {"drop": [], "take": [], "x": 1}}
    with pytest.raises(ValidationError):
        parse_request(data)


def test_rest_schema_has_prepared_swap_as_an_inline_object_without_union():
    prop = tool_defs(["rest"])[0]["input_schema"]["properties"]["prepared_swap"]
    assert prop["type"] == "object"
    assert sorted(prop["properties"]) == ["drop", "take"]
    assert prop["properties"]["drop"]["type"] == "array"
    assert prop["properties"]["drop"]["description"]
    assert prop["properties"]["take"]["description"]
    assert "anyOf" not in prop
    assert prop["additionalProperties"] is False


def test_rest_schema_requires_prepared_swap_and_describes_it():
    schema = tool_defs(["rest"])[0]["input_schema"]
    assert "prepared_swap" in schema["required"]
    assert schema["properties"]["prepared_swap"]["description"]


def test_cast_spell_circle_description_mentions_upcast():
    prop = tool_defs(["cast_spell"])[0]["input_schema"]["properties"]["circle"]
    assert "upcast" in prop["description"]
    assert len(prop["description"]) <= 150


# К7х: rest.prey_swap -- строка; пустая = без смены (None)

def test_rest_without_prey_swap_has_none():
    assert parse_request({"type": "rest", "kind": "long"}).prey_swap is None


def test_rest_with_empty_prey_swap_has_none():
    assert parse_request({"type": "rest", "kind": "short", "prey_swap": ""}).prey_swap is None


def test_rest_prey_swap_keeps_the_option_id():
    data = {"type": "rest", "kind": "short", "prey_swap": "horde_breaker"}
    assert parse_request(data).prey_swap == "horde_breaker"


def test_rest_schema_has_a_required_string_prey_swap():
    schema_of = tool_defs(["rest"])[0]["input_schema"]
    assert schema_of["properties"]["prey_swap"]["type"] == "string"
    assert "prey_swap" in schema_of["required"]
    assert schema_of["properties"]["prey_swap"]["description"] != ""


def test_rest_prey_swap_description_names_both_options():
    prop = tool_defs(["rest"])[0]["input_schema"]["properties"]["prey_swap"]
    assert "colossus_slayer" in prop["description"]
    assert "horde_breaker" in prop["description"]


def test_improvise_push_description_mentions_the_fall():
    text = json.dumps(tool_defs(["player_action"])[0], ensure_ascii=False)
    assert "в зону ниже" in text
    assert "падени" in text
