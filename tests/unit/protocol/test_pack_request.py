# Б3 (B3-PLAN A1): режим pack_import -- инструмент pack, разбор, apply и конвертер в файлы пака.
# Конвертер (protocol/handlers/pack.py) без диска и без campaign: словари только с заданными полями.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from import_kit import (  # noqa: E402
    PACK_ID,
    faction_input,
    god_input,
    guard_input,
    import_task,
    location_input,
    npc_input,
    pack_input,
    secret_input,
    start_input,
    tone_input,
    trigger_input,
)
from protocol_kit import req  # noqa: E402

from ai_dm.protocol import schema  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.context import CreationContext, ImportTask  # noqa: E402
from ai_dm.protocol.decision import Decision, Invalid  # noqa: E402
from ai_dm.protocol.handlers import pack as pack_handlers  # noqa: E402
from ai_dm.protocol.requests import (  # noqa: E402
    HeroTriggerSpec,
    PackLocation,
    PackRequest,
    SecretSpec,
    parse_request,
)
from ai_dm.state.world import Tone  # noqa: E402

FILE_KEYS = {
    "campaign.yaml", "world.md", "truths.md", "locations.yaml", "npcs.yaml", "factions.yaml",
    "pantheon.yaml",
}


def parsed(**changes):
    return parse_request(pack_input(**changes), "pack_import")


def creation(registry, cfg):
    return CreationContext(registry, cfg, import_task())


def run(registry, cfg, **changes):
    ctx = creation(registry, cfg)
    return ctx, apply(ctx, parsed(**changes))


def files(registry, cfg, **changes):
    ctx, result = run(registry, cfg, **changes)
    assert isinstance(result, Decision)
    return ctx.files


def entity(rows, entity_id):
    return next(row for row in rows if row["id"] == entity_id)


def tool():
    return schema.tool_set("pack_import")[0]


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


# набор инструментов режима

def test_pack_import_tool_set_is_one_strict_tool():
    tools = schema.tool_set("pack_import")
    assert [t["name"] for t in tools] == ["pack"]
    assert tools[0]["strict"] is True


def test_pack_import_mode_tools_registered():
    assert schema.MODE_TOOLS["pack_import"] == ("pack",)


def test_pack_tool_schema_has_no_ref():
    assert "$ref" not in json.dumps(tool()["input_schema"])


def test_pack_tool_has_no_free_dictionaries():
    for node in walk(tool()["input_schema"]):
        if "additionalProperties" in node:
            assert node["additionalProperties"] is False
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False


def test_pack_tool_requires_every_property_of_every_object():
    for node in walk(tool()["input_schema"]):
        if "properties" in node:
            assert node["required"] == list(node["properties"])


def test_pack_tool_description_is_docstring():
    assert tool()["description"] == PackRequest.__doc__.strip()


def test_pack_tool_has_all_top_fields():
    props = tool()["input_schema"]["properties"]
    assert set(props) == {
        "type", "name", "start", "tone", "world_text", "truths", "locations", "npcs",
        "factions", "pantheon",
    }


def test_pack_tool_has_no_id_and_version_of_manifest():
    props = tool()["input_schema"]["properties"]
    assert "id" not in props
    assert "version" not in props


def test_pack_tool_tone_has_axes_of_tone_model():
    tone = tool()["input_schema"]["properties"]["tone"]
    assert set(tone["properties"]) == set(Tone.model_fields)
    assert "мягко" in json.dumps(tone["properties"]["violence"], ensure_ascii=False)


def test_pack_tool_start_fields():
    start = tool()["input_schema"]["properties"]["start"]
    assert set(start["properties"]) == {
        "date", "time", "hero_location", "chapter_number", "chapter_title", "scene_summary",
    }


def test_pack_tool_npc_items_have_triggers_and_secrets_but_no_status_or_combat():
    items = tool()["input_schema"]["properties"]["npcs"]["items"]
    props = set(items["properties"])
    assert {"opportunity", "secrets", "species_id", "trade_kind", "means"} <= props
    assert not {"combat", "status", "attitude", "creature"} & props


def test_pack_tool_secret_items_are_flat_conditions():
    items = tool()["input_schema"]["properties"]["npcs"]["items"]["properties"]["secrets"]["items"]
    assert set(items["properties"]) == {"id", "text", "kind", "ref", "status", "gte"}
    assert items["properties"]["kind"]["enum"] == [
        "narrative", "flag", "hero_has", "hero_at", "npc_status", "attitude", "favor",
    ]


def test_pack_tool_location_items_have_connections():
    items = tool()["input_schema"]["properties"]["locations"]["items"]
    assert set(items["properties"]) == {"id", "name", "parent_id", "description", "connections"}


def test_pack_tool_set_is_stable_between_calls():
    assert schema.tool_set("pack_import") == schema.tool_set("pack_import")


def test_import_tool_is_cached_under_group_import(monkeypatch):
    monkeypatch.setattr(schema, "_cache", {})
    schema.tool_set("pack_import")
    schema.tool_set("hero_sheet")
    assert ("pack", "import") in schema._cache
    assert ("hero_sheet", "hero") in schema._cache


def test_pack_tool_is_not_in_other_groups():
    schema.tool_set("pack_import")
    assert [t["name"] for t in schema.tool_set("summarize_scene")] == ["scene_summary"]
    assert [t["name"] for t in schema.tool_set("hero_sheet")] == ["hero_sheet"]


def test_own_models_of_import_mode_is_pack():
    assert set(schema.own_models("pack_import")) == {"pack"}


# разбор

def test_parse_request_in_import_mode_takes_pack():
    request = parsed()
    assert isinstance(request, PackRequest)
    assert request.name == "Мини-импорт"


def test_pack_is_not_parsed_in_other_modes():
    for mode in ("explore", "hero_sheet", "hero_background", "world", "summarize_scene"):
        with pytest.raises(ValueError):
            parse_request(pack_input(), mode)


def test_import_mode_does_not_parse_other_requests():
    sheet = {"type": "hero_sheet"}
    with pytest.raises(ValueError):
        parse_request(sheet, "pack_import")
    with pytest.raises(ValueError):
        parse_request({"type": "set_flag", "name": "a", "value": "true"}, "pack_import")


def test_parse_rejects_unknown_tone_axis_value():
    with pytest.raises(ValueError):
        parsed(tone=tone_input(violence="ужасно"))


def test_parse_rejects_unknown_condition_kind():
    with pytest.raises(ValueError):
        parsed(npcs=[npc_input(opportunity=[trigger_input(kind="time_after")])])


def test_parse_rejects_extra_field_in_location():
    with pytest.raises(ValueError):
        parsed(locations=[location_input(color="red")])


# apply: режимы

def test_other_request_in_import_mode_is_not_available(registry, cfg):
    result = apply(creation(registry, cfg), req("set_flag", name="a", value="true"))
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_npc_create_in_import_mode_is_not_available(registry, cfg):
    request = req("npc_create", id="x", name="Икс", means=["а"])
    result = apply(creation(registry, cfg), request)
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_pack_in_hero_sheet_mode_is_not_available(registry, cfg):
    from hero_kit import sheet_task, vale_pack

    ctx = CreationContext(registry, cfg, sheet_task(vale_pack(registry)))
    result = apply(ctx, parsed())
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_import_context_defaults(registry, cfg):
    ctx = creation(registry, cfg)
    assert ctx.mode == "pack_import"
    assert ctx.files is None
    assert ctx.marks == []
    assert ctx.turn_seq == 0


def test_import_task_keeps_campaign_id():
    assert ImportTask("abc").campaign_id == "abc"
    assert ImportTask("abc").mode == "pack_import"


# хендлер

def test_valid_pack_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg)
    assert isinstance(result, Decision)
    assert result.status == "accepted"
    assert result.log == ["Пак принят"]
    assert ctx.files is not None


def test_second_call_after_accepted_is_already_done(registry, cfg):
    ctx, _ = run(registry, cfg)
    before = ctx.files
    result = apply(ctx, parsed(name="Другой"))
    assert isinstance(result, Invalid)
    assert result.code == "already_done"
    assert ctx.files is before


def test_files_have_seven_keys(registry, cfg):
    assert set(files(registry, cfg)) == FILE_KEYS


def test_manifest_gets_id_from_task_and_version_one(registry, cfg):
    manifest = files(registry, cfg)["campaign.yaml"]
    assert manifest["id"] == PACK_ID
    assert manifest["version"] == "1"
    assert manifest["name"] == "Мини-импорт"


def test_manifest_id_follows_the_task(registry, cfg):
    ctx = CreationContext(registry, cfg, ImportTask("other_id"))
    apply(ctx, parsed())
    assert ctx.files["campaign.yaml"]["id"] == "other_id"


def test_manifest_start_has_date_location_and_scene(registry, cfg):
    start = files(registry, cfg)["campaign.yaml"]["start"]
    assert start["date"] == "0100-03-01"
    assert start["time"] == "08:00"
    assert start["hero_location"] == "inn"
    assert start["scene_summary"] == "В трактире шумно, Мара считает монеты."


def test_manifest_start_chapter_is_kept(registry, cfg):
    start = files(registry, cfg, start=start_input(chapter_number=3, chapter_title="Долг"))[
        "campaign.yaml"
    ]["start"]
    assert start["chapter"] == {"number": 3, "title": "Долг"}


def test_manifest_start_has_no_heroes(registry, cfg):
    assert "heroes" not in files(registry, cfg)["campaign.yaml"]["start"]


def test_manifest_tone_keeps_filled_axes(registry, cfg):
    tone = files(registry, cfg)["campaign.yaml"]["tone"]
    assert tone["violence"] == "жестоко"
    assert tone["romance"] == "намёки"
    assert tone["mood"] == "мрачное фэнтези"
    assert tone["notes"] == "Мир суров."


def test_manifest_tone_has_no_empty_axes(registry, cfg):
    tone = files(registry, cfg, tone=tone_input(romance="", horror="", language="", notes=""))[
        "campaign.yaml"
    ]["tone"]
    assert set(tone) == {"mood", "violence"}
    assert "hard_limits" not in tone


def test_manifest_tone_keeps_limits_when_filled(registry, cfg):
    tone = files(registry, cfg, tone=tone_input(hard_limits=["пытки"], soft_limits=["яд"]))[
        "campaign.yaml"
    ]["tone"]
    assert tone["hard_limits"] == ["пытки"]
    assert tone["soft_limits"] == ["яд"]


def test_manifest_has_no_events_heroes_or_preset(registry, cfg):
    manifest = files(registry, cfg)["campaign.yaml"]
    assert set(manifest) == {"id", "name", "version", "start", "tone"}


def test_world_text_and_truths_are_strings(registry, cfg):
    result = files(registry, cfg)
    assert result["world.md"] == "Город у реки: площадь и трактир."
    assert result["truths.md"] == "Река не замерзает."


def test_empty_truths_stays_empty_string(registry, cfg):
    assert files(registry, cfg, truths="")["truths.md"] == ""


def test_locations_keep_connections_and_parent(registry, cfg):
    rows = files(registry, cfg)["locations.yaml"]
    assert [row["id"] for row in rows] == ["square", "inn"]
    inn = entity(rows, "inn")
    assert inn["parent_id"] == "square"
    assert inn["connections"] == [{"to": "square", "distance_m": 50}]
    assert entity(rows, "square")["connections"] == [{"to": "inn", "distance_m": 50}]


def test_location_without_parent_and_description_has_no_such_keys(registry, cfg):
    rows = files(registry, cfg)["locations.yaml"]
    inn = entity(rows, "inn")
    assert "description" not in inn
    assert "parent_id" not in entity(rows, "square")
    assert entity(rows, "square")["description"] == "Шумная площадь."


def test_location_without_connections_has_no_key(registry, cfg):
    rows = files(registry, cfg, locations=[location_input(connections=[])])["locations.yaml"]
    assert "connections" not in rows[0]


def test_npc_fields_are_plain_values(registry, cfg):
    mara = entity(files(registry, cfg)["npcs.yaml"], "mara")
    assert mara["name"] == "Мара"
    assert mara["means"] == ["знает все слухи"]
    assert mara["named"] is True
    assert mara["key"] is True
    assert mara["motive"] == "Хочет выкупить долг."
    assert mara["location_id"] == "inn"
    assert mara["species_id"] == "human"


def test_npc_empty_fields_are_absent(registry, cfg):
    guard = entity(files(registry, cfg)["npcs.yaml"], "guard")
    assert guard["named"] is False
    assert guard["key"] is False
    for absent in ("motive", "species_id", "trade_kind", "trade", "opportunity", "secrets"):
        assert absent not in guard


def test_npc_without_location_has_no_location_key(registry, cfg):
    rows = files(registry, cfg, npcs=[guard_input(location_id="")])["npcs.yaml"]
    assert "location_id" not in rows[0]


def test_npc_trigger_is_short_condition_once(registry, cfg):
    mara = entity(files(registry, cfg)["npcs.yaml"], "mara")
    assert mara["opportunity"] == [
        {"id": "leave", "if": {"flag": "debt_paid"}, "then": "уходит из города", "once": True}
    ]


def test_npc_secret_has_reveal_if_in_short_form(registry, cfg):
    mara = entity(files(registry, cfg)["npcs.yaml"], "mara")
    assert mara["secrets"] == [
        {"id": "debt", "text": "Мара должна гильдии.",
         "reveal_if": {"narrative": "герой завоевал её доверие"}}
    ]


def test_npc_trade_kind_goes_to_trade_profile(registry, cfg):
    rows = files(registry, cfg, npcs=[npc_input(trade_kind="smith")])["npcs.yaml"]
    assert rows[0]["trade"] == {"kind": "smith"}
    assert "trade_kind" not in rows[0]


def test_factions_keep_members_regions_and_means(registry, cfg):
    watch = entity(files(registry, cfg)["factions.yaml"], "watch")
    assert watch["name"] == "Стража"
    assert watch["motive"] == "Порядок в городе."
    assert watch["means"] == ["патрули"]
    assert watch["members"] == ["guard"]
    assert watch["regions"] == ["square"]
    assert "opportunity" not in watch


def test_faction_trigger_is_converted(registry, cfg):
    trigger = trigger_input(id="raid", kind="hero_at", ref="inn", then="обыск")
    watch = entity(files(registry, cfg, factions=[faction_input(opportunity=[trigger])])[
        "factions.yaml"], "watch")
    assert watch["opportunity"] == [
        {"id": "raid", "if": {"hero_at": "inn"}, "then": "обыск", "once": True}
    ]


def test_god_fields_are_kept(registry, cfg):
    selune = entity(files(registry, cfg)["pantheon.yaml"], "selune")
    assert selune["name"] == "Селунэ"
    assert selune["domains"] == ["луна"]
    assert selune["role"] == "богиня ночи"
    assert selune["pleased_by"] == ["милосердие"]
    assert selune["means"] == ["знамения"]
    assert selune["servants"] == ["mara"]


def test_god_empty_fields_are_absent(registry, cfg):
    selune = entity(files(registry, cfg)["pantheon.yaml"], "selune")
    for absent in ("motive", "angered_by", "rivals", "realm", "opportunity"):
        assert absent not in selune


def test_god_trigger_and_rivals_are_kept(registry, cfg):
    trigger = trigger_input(id="wrath", kind="favor", ref="selune", gte=3, then="гнев")
    god = god_input(rivals=["shar"], opportunity=[trigger])
    selune = entity(files(registry, cfg, pantheon=[god])["pantheon.yaml"], "selune")
    assert selune["rivals"] == ["shar"]
    assert selune["opportunity"][0]["if"] == {"favor": {"god": "selune", "gte": 3}}


def test_empty_entity_lists_stay_empty_lists(registry, cfg):
    result = files(registry, cfg, factions=[], pantheon=[])
    assert result["factions.yaml"] == []
    assert result["pantheon.yaml"] == []


def test_attitude_without_threshold_is_invalid_request(registry, cfg):
    trigger = trigger_input(kind="attitude", ref="mara", gte=0)
    ctx, result = run(registry, cfg, npcs=[npc_input(opportunity=[trigger])])
    assert isinstance(result, Invalid)
    assert result.code == "invalid_request"
    assert "gte" in result.message
    assert ctx.files is None


def test_secret_favor_without_threshold_is_invalid_request(registry, cfg):
    secret = secret_input(kind="favor", ref="selune", gte=0)
    _, result = run(registry, cfg, npcs=[npc_input(secrets=[secret])])
    assert isinstance(result, Invalid)
    assert result.code == "invalid_request"


def test_failed_conversion_allows_the_next_call(registry, cfg):
    ctx = creation(registry, cfg)
    bad = trigger_input(kind="attitude", ref="mara", gte=0)
    assert isinstance(apply(ctx, parsed(npcs=[npc_input(opportunity=[bad])])), Invalid)
    assert isinstance(apply(ctx, parsed()), Decision)
    assert ctx.files is not None


# чистые функции конвертера

def trigger_spec(**changes):
    return HeroTriggerSpec.model_validate(trigger_input(**changes))


def secret_spec(**changes):
    return SecretSpec.model_validate(secret_input(**changes))


def test_trigger_data_flag():
    assert pack_handlers.trigger_data(trigger_spec()) == {
        "id": "leave", "if": {"flag": "debt_paid"}, "then": "уходит из города", "once": True,
    }


def test_trigger_data_npc_status_defaults_to_alive():
    data = pack_handlers.trigger_data(trigger_spec(kind="npc_status", ref="mara"))
    assert data["if"] == {"npc_status": {"id": "mara", "is": "alive"}}


def test_trigger_data_npc_status_with_status():
    data = pack_handlers.trigger_data(trigger_spec(kind="npc_status", ref="mara", status="dead"))
    assert data["if"] == {"npc_status": {"id": "mara", "is": "dead"}}


def test_trigger_data_attitude_with_threshold():
    data = pack_handlers.trigger_data(trigger_spec(kind="attitude", ref="mara", gte=20))
    assert data["if"] == {"attitude": {"npc": "mara", "gte": 20}}


def test_secret_data_keeps_id_text_and_reveal_if():
    assert pack_handlers.secret_data(secret_spec()) == {
        "id": "debt", "text": "Мара должна гильдии.",
        "reveal_if": {"narrative": "герой завоевал её доверие"},
    }


def test_secret_data_hero_has():
    data = pack_handlers.secret_data(secret_spec(kind="hero_has", ref="crowbar"))
    assert data["reveal_if"] == {"hero_has": "crowbar"}


def test_location_data_drops_empty_fields():
    spec = PackLocation.model_validate(location_input(connections=[]))
    assert pack_handlers.location_data(spec) == {
        "id": "square", "name": "Площадь", "description": "Шумная площадь.",
    }


def test_location_data_with_parent_and_connections():
    spec = PackLocation.model_validate(
        location_input(id="inn", name="Трактир", parent_id="square", description="")
    )
    assert pack_handlers.location_data(spec) == {
        "id": "inn", "name": "Трактир", "parent_id": "square",
        "connections": [{"to": "inn", "distance_m": 50}],
    }


def test_tone_data_keeps_only_filled_fields():
    tone = Tone(violence="жестоко", notes="заметка")
    assert pack_handlers.tone_data(tone) == {"violence": "жестоко", "notes": "заметка"}


def test_tone_data_of_empty_tone_is_empty():
    assert pack_handlers.tone_data(Tone()) == {}


def test_manifest_data_has_five_keys():
    data = pack_handlers.manifest_data(parsed(), "abc")
    assert set(data) == {"id", "name", "version", "start", "tone"}
    assert data["id"] == "abc"


def test_files_from_request_keys():
    assert set(pack_handlers.files_from_request(parsed(), "abc")) == FILE_KEYS


def test_files_from_request_is_pure():
    first = pack_handlers.files_from_request(parsed(), "abc")
    second = pack_handlers.files_from_request(parsed(), "abc")
    assert first == second


# добивка по мутантам

def test_tone_axes_in_schema_are_values_plus_none():
    tone = tool()["input_schema"]["properties"]["tone"]["properties"]
    assert tone["violence"]["enum"] == ["мягко", "реалистично", "жестоко", "none"]
    assert tone["horror"]["enum"] == ["нет", "умеренно", "сильно", "none"]
    assert tone["romance"]["enum"] == ["нет", "намёки", "чувственно", "откровенно", "none"]
    assert tone["language"]["enum"] == ["сдержанно", "грубо", "none"]


@pytest.mark.parametrize("value", ["none", ""])
def test_tone_axis_none_or_empty_means_not_set(registry, cfg, value):
    manifest = files(registry, cfg, tone=tone_input(violence=value, romance=value))[
        "campaign.yaml"
    ]["tone"]
    assert "violence" not in manifest
    assert "romance" not in manifest
    assert manifest["horror"] == "умеренно"


def test_tone_axis_rejects_value_in_wrong_case():
    with pytest.raises(ValueError):
        parsed(tone=tone_input(violence="NONE"))


def test_filled_god_fields_are_all_kept(registry, cfg):
    god = god_input(motive="Хранить ночь.", angered_by=["обман"], realm="Лунный чертог")
    selune = entity(files(registry, cfg, pantheon=[god])["pantheon.yaml"], "selune")
    assert selune["motive"] == "Хранить ночь."
    assert selune["angered_by"] == ["обман"]
    assert selune["realm"] == "Лунный чертог"


def test_second_call_message_is_exact(registry, cfg):
    ctx, _ = run(registry, cfg)
    assert apply(ctx, parsed()).message == "Пак уже принят."


def test_other_request_in_import_mode_names_the_service(registry, cfg):
    result = apply(creation(registry, cfg), req("set_flag", name="a", value="true"))
    assert "import пака" in result.message


def test_pack_tool_set_returns_independent_copies():
    first = schema.tool_set("pack_import")
    first[0]["input_schema"]["properties"].clear()
    assert schema.tool_set("pack_import")[0]["input_schema"]["properties"]
