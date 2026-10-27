# Б1а (B1-PLAN A2): режим hero_sheet -- инструмент hero_sheet, разбор, apply и хендлер.
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import (  # noqa: E402
    HERO_NAME,
    background_input,
    known,
    sheet_input,
    trigger_input,
)
from protocol_kit import make_ctx  # noqa: E402

from ai_dm.protocol import schema  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.context import BackgroundTask, CreationContext, SheetTask  # noqa: E402
from ai_dm.protocol.decision import Decision, Invalid  # noqa: E402
from ai_dm.protocol.handlers.hero import condition_from_spec, sheet_from_request  # noqa: E402
from ai_dm.protocol.requests import (  # noqa: E402
    HERO_MODES,
    HeroSheetRequest,
    HeroTriggerSpec,
    parse_request,
)
from ai_dm.state.triggers import (  # noqa: E402
    Attitude,
    Favor,
    Flag,
    HeroAt,
    HeroHas,
    Narrative,
    NpcStatus,  # noqa: E402
)

KNOWN = known(npcs=["innkeeper", "grakh"], locations=["vale", "lame_goose", "cellar"])


def creation(registry, cfg, **kw):
    kw.setdefault("known", KNOWN)
    kw.setdefault("taken_names", ["Гарт", "Гракх"])
    return CreationContext(registry, cfg, SheetTask(**kw))


def parsed(**changes):
    return parse_request(sheet_input(**changes), "hero_sheet")


def run(registry, cfg, **changes):
    ctx = creation(registry, cfg)
    return ctx, apply(ctx, parsed(**changes))


def trigger_spec(**changes):
    return HeroTriggerSpec.model_validate(trigger_input(**changes))


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def tool():
    return schema.tool_set("hero_sheet")[0]


# набор инструментов режима

def test_hero_modes_are_both_hero_modes():
    assert HERO_MODES == ("hero_background", "hero_sheet")


def test_hero_sheet_tool_set_is_one_strict_tool():
    tools = schema.tool_set("hero_sheet")
    assert [t["name"] for t in tools] == ["hero_sheet"]
    assert tools[0]["strict"] is True


def test_hero_sheet_tool_schema_has_no_ref():
    assert "$ref" not in json.dumps(tool()["input_schema"])


def test_hero_sheet_tool_has_no_free_dictionaries():
    # additionalProperties допустим только false: свободный словарь strict не принимает
    for node in walk(tool()["input_schema"]):
        if "additionalProperties" in node:
            assert node["additionalProperties"] is False
        if node.get("type") == "object":
            assert node.get("additionalProperties") is False


def test_hero_sheet_tool_requires_every_property_of_every_object():
    for node in walk(tool()["input_schema"]):
        if "properties" in node:
            assert node["required"] == list(node["properties"])


def test_hero_sheet_tool_description_is_docstring():
    assert tool()["description"] == HeroSheetRequest.__doc__.strip()


def test_hero_sheet_tool_has_all_top_fields():
    props = tool()["input_schema"]["properties"]
    assert set(props) == {
        "type", "name", "gender", "pronouns", "species_id", "class_id", "ability_method",
        "ability_scores", "bonus_plus2", "bonus_plus1", "class_skills", "weapon_masteries",
        "fighting_style", "class_kit", "spells", "prepared", "species_skill", "species_feat",
        "feat_skills", "species_feat_skills", "background", "background_gear", "motive", "means",
        "opportunity",
    }


def test_hero_sheet_tool_has_int_ability_under_alias():
    scores = tool()["input_schema"]["properties"]["ability_scores"]
    assert set(scores["properties"]) == {"str", "dex", "con", "int", "wis", "cha"}


def test_hero_sheet_tool_background_is_nested_object_without_type():
    background = tool()["input_schema"]["properties"]["background"]
    assert background["type"] == "object"
    assert set(background["properties"]) == {
        "name", "abilities", "skills", "tool", "feat", "equipment", "gold_cp", "description",
    }


def test_hero_sheet_tool_opportunity_items_are_flat_triggers():
    items = tool()["input_schema"]["properties"]["opportunity"]["items"]
    assert set(items["properties"]) == {"id", "then", "kind", "ref", "status", "gte"}
    assert items["properties"]["kind"]["enum"] == [
        "narrative", "flag", "hero_has", "hero_at", "npc_status", "attitude", "favor",
    ]


def test_hero_sheet_method_enum_has_three_methods():
    method = tool()["input_schema"]["properties"]["ability_method"]
    assert method["enum"] == ["standard_array", "point_buy", "explicit"]


def test_hero_sheet_tool_is_not_cached_into_other_groups():
    schema.tool_set("hero_sheet")
    assert [t["name"] for t in schema.tool_set("summarize_scene")] == ["scene_summary"]


def test_hero_sheet_tool_set_is_stable_between_calls():
    assert schema.tool_set("hero_sheet") == schema.tool_set("hero_sheet")


def test_hero_sheet_tool_differs_from_background_tool():
    assert tool()["name"] != schema.tool_set("hero_background")[0]["name"]


def test_both_hero_modes_cache_their_tools_under_group_hero(monkeypatch):
    monkeypatch.setattr(schema, "_cache", {})
    schema.tool_set("hero_sheet")
    schema.tool_set("hero_background")
    assert ("hero_sheet", "hero") in schema._cache
    assert ("background_spec", "hero") in schema._cache


def test_own_models_are_split_by_hero_mode():
    assert set(schema.own_models("hero_sheet")) == {"hero_sheet"}
    assert set(schema.own_models("hero_background")) == {"background_spec"}


def test_hero_sheet_mode_tools_registered():
    assert schema.MODE_TOOLS["hero_sheet"] == ("hero_sheet",)


# разбор

def test_parse_request_in_sheet_mode_takes_hero_sheet():
    request = parsed()
    assert isinstance(request, HeroSheetRequest)
    assert request.name == HERO_NAME
    assert request.ability_scores.int_ == 8


def test_parse_request_in_sheet_mode_rejects_background_spec():
    data = {"type": "background_spec", **background_input()}
    with pytest.raises(ValueError):
        parse_request(data, "hero_sheet")


def test_parse_request_in_sheet_mode_rejects_other_requests():
    with pytest.raises(ValueError):
        parse_request({"type": "set_flag", "name": "a", "value": "true"}, "hero_sheet")


@pytest.mark.parametrize("mode", ["hero_background", "explore", "world", "summarize_scene"])
def test_hero_sheet_is_not_parsed_in_other_modes(mode):
    with pytest.raises(ValueError):
        parse_request(sheet_input(), mode)


def test_parse_rejects_unknown_skill_in_class_skills():
    with pytest.raises(ValueError):
        parsed(class_skills=["perception", "juggling"])


def test_parse_rejects_unknown_ability_method():
    with pytest.raises(ValueError):
        parsed(ability_method="roll")


def test_parse_rejects_unknown_trigger_kind():
    with pytest.raises(ValueError):
        parsed(opportunity=[trigger_input(kind="time_after")])


def test_parse_rejects_extra_field():
    with pytest.raises(ValueError):
        parsed(level=3)


def test_neutral_values_become_none():
    request = parsed(fighting_style="", species_feat="", species_skill="none", bonus_plus2="none")
    assert request.fighting_style is None
    assert request.species_feat is None
    assert request.species_skill is None
    assert request.bonus_plus2 is None


def test_neutral_trigger_values_become_none():
    spec = trigger_spec(status="", gte=0)
    assert spec.status is None
    assert spec.gte is None


def test_non_neutral_trigger_values_are_kept():
    spec = trigger_spec(kind="npc_status", status="dead", gte=5)
    assert spec.status == "dead"
    assert spec.gte == 5


def test_empty_background_description_becomes_none_and_sheet_has_empty_text(registry):
    request = parsed(background=background_input(description=""))
    assert request.background.description is None
    assert sheet_from_request(request).choices.background.description == ""


# apply: режимы

def test_other_request_in_sheet_mode_is_not_available(registry, cfg):
    from protocol_kit import req

    ctx = creation(registry, cfg)
    result = apply(ctx, req("set_flag", name="a", value="true"))
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_hero_sheet_in_summarize_mode_is_not_available(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="summarize_scene")
    result = apply(ctx, parsed())
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_sheet_context_defaults(registry, cfg):
    ctx = creation(registry, cfg)
    assert ctx.mode == "hero_sheet"
    assert ctx.sheet is None
    assert ctx.background is None
    assert ctx.marks == []
    assert ctx.turn_seq == 0
    assert ctx.cfg is cfg
    assert ctx.registry is registry


def test_sheet_task_defaults():
    task = SheetTask(known=KNOWN, taken_names=["Гарт"])
    assert task.feedback == ""
    assert task.previous is None
    assert task.mode == "hero_sheet"


def test_background_task_defaults():
    task = BackgroundTask("fighter")
    assert task.class_skills == ()
    assert task.mode == "hero_background"


# хендлер: успех

def test_valid_sheet_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg)
    assert isinstance(result, Decision)
    assert result.status == "accepted"
    assert result.log == ["Лист героя принят"]
    assert ctx.sheet is not None


def test_accepted_sheet_has_choices_from_request(registry, cfg):
    ctx, _ = run(registry, cfg)
    choices = ctx.sheet.choices
    assert choices.name == HERO_NAME
    assert choices.species_id == "human"
    assert choices.class_id == "fighter"
    assert choices.ability_method == "standard_array"
    assert choices.ability_scores == {
        "str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12,
    }
    assert choices.class_skills == ["perception", "survival"]
    assert choices.weapon_masteries == ["longsword", "greatsword", "shortsword"]
    assert choices.fighting_style == "defense"
    assert choices.class_kit == "a"
    assert choices.background_gear == "equipment"


def test_accepted_sheet_has_bonus_species_and_feat_choices(registry, cfg):
    ctx, _ = run(registry, cfg)
    choices = ctx.sheet.choices
    assert choices.background_bonus == {"dex": 2, "con": 1}
    assert choices.species_choices == {"skill": "stealth", "feat": "skilled"}
    assert choices.feat_choices == {"skilled": ["medicine", "religion", "nature"]}


def test_accepted_sheet_has_background_spec_with_standard_gold_option(registry, cfg):
    ctx, _ = run(registry, cfg)
    spec = ctx.sheet.choices.background
    assert spec.name == "Бывший цирковой акробат"
    assert spec.abilities == ["dex", "con", "cha"]
    assert spec.skills == ["acrobatics", "performance"]
    assert spec.tool == "thieves_tools"
    assert spec.feat == "alert"
    assert spec.equipment == ["crowbar"]
    assert spec.gold_cp == 1000
    assert spec.gold_option_cp == 5000
    assert spec.description == "Вырос в бродячем цирке."


def test_accepted_sheet_has_motive_means_and_once_trigger(registry, cfg):
    ctx, _ = run(registry, cfg)
    assert ctx.sheet.motive == "Найти сестру."
    assert ctx.sheet.means == ["острый ум"]
    [trigger] = ctx.sheet.opportunity
    assert trigger.id == "o1"
    assert trigger.then == "отомстить"
    assert trigger.once is True
    assert trigger.if_ == Narrative(text="герой узнаёт о сестре")


def test_sheet_without_hooks_but_with_means_is_accepted(registry, cfg):
    ctx, result = run(registry, cfg, opportunity=[])
    assert result.status == "accepted"
    assert ctx.sheet.opportunity == []


def test_second_call_after_accepted_is_already_done(registry, cfg):
    ctx, _ = run(registry, cfg)
    first = ctx.sheet
    result = apply(ctx, parsed(name="Другой"))
    assert isinstance(result, Invalid)
    assert result.code == "already_done"
    assert ctx.sheet is first


def test_invalid_sheet_leaves_ctx_empty(registry, cfg):
    ctx, result = run(registry, cfg, motive="")
    assert isinstance(result, Invalid)
    assert ctx.sheet is None


def test_invalid_call_does_not_block_a_valid_retry(registry, cfg):
    ctx, _ = run(registry, cfg, motive="")
    result = apply(ctx, parsed())
    assert result.status == "accepted"
    assert ctx.sheet is not None


def test_feedback_and_previous_do_not_change_the_handler(registry, cfg):
    plain, _ = run(registry, cfg)
    ctx = creation(registry, cfg, feedback="сделай мрачнее", previous={"name": "Старый"})
    apply(ctx, parsed())
    assert ctx.sheet == plain.sheet
    assert ctx.sheet == sheet_from_request(parsed())


# хендлер: отказы

def test_invalid_sheet_has_first_code_and_all_texts_joined(registry, cfg):
    scores = {"str": 16, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    _, result = run(registry, cfg, ability_scores=scores, motive="")
    assert isinstance(result, Invalid)
    assert result.code == "standard_array_invalid"
    parts = result.message.split("; ")
    assert len(parts) == 2
    assert "стандартный набор" in parts[0]
    assert "мотив" in parts[1]


def test_name_of_npc_is_invalid_with_taken_code(registry, cfg):
    _, result = run(registry, cfg, name="Гарт")
    assert result.code == "hero_name_taken"
    assert "'Гарт'" in result.message


def test_name_check_ignores_case(registry, cfg):
    _, result = run(registry, cfg, name="гракх")
    assert result.code == "hero_name_taken"


def test_unknown_class_kit_is_invalid(registry, cfg):
    _, result = run(registry, cfg, class_kit="z")
    assert result.code == "class_kit_unknown"
    assert "a, b, c" in result.message


def test_unknown_npc_in_trigger_is_invalid_opportunity_ref(registry, cfg):
    trigger = trigger_input(kind="npc_status", ref="ghost", status="dead")
    _, result = run(registry, cfg, opportunity=[trigger])
    assert result.code == "opportunity_ref"
    assert "ghost" in result.message


def test_known_npc_in_trigger_is_accepted(registry, cfg):
    trigger = trigger_input(kind="npc_status", ref="innkeeper", status="dead")
    ctx, result = run(registry, cfg, opportunity=[trigger])
    assert result.status == "accepted"
    assert ctx.sheet.opportunity[0].if_ == NpcStatus(id="innkeeper", is_="dead")


def test_unknown_location_in_trigger_is_invalid(registry, cfg):
    _, result = run(registry, cfg, opportunity=[trigger_input(kind="hero_at", ref="moon")])
    assert result.code == "opportunity_ref"


def test_three_triggers_are_invalid(registry, cfg):
    triggers = [trigger_input(id=f"o{i}") for i in range(3)]
    _, result = run(registry, cfg, opportunity=triggers)
    assert result.code == "opportunity_count"


def test_long_background_description_is_invalid(registry, cfg):
    _, result = run(registry, cfg, background=background_input(description="а" * 301))
    assert result.code == "description_too_long"


def test_attitude_without_gte_is_invalid_request(registry, cfg):
    trigger = trigger_input(kind="attitude", ref="innkeeper", gte=0)
    ctx, result = run(registry, cfg, opportunity=[trigger])
    assert isinstance(result, Invalid)
    assert result.code == "invalid_request"
    assert "gte" in result.message
    assert ctx.sheet is None


def test_favor_without_gte_is_invalid_request(registry, cfg):
    trigger = trigger_input(kind="favor", ref="sun", gte=0)
    _, result = run(registry, cfg, opportunity=[trigger])
    assert result.code == "invalid_request"


def test_empty_trigger_id_is_invalid_opportunity_id(registry, cfg):
    _, result = run(registry, cfg, opportunity=[trigger_input(id="")])
    assert result.code == "opportunity_id"


# sheet_from_request

def test_bonus_three_ones_when_plus2_is_none():
    sheet = sheet_from_request(parsed(bonus_plus2="none", bonus_plus1=["dex", "con", "cha"]))
    assert sheet.choices.background_bonus == {"dex": 1, "con": 1, "cha": 1}


def test_bonus_plus2_with_one_plus1():
    sheet = sheet_from_request(parsed(bonus_plus2="cha", bonus_plus1=["dex"]))
    assert sheet.choices.background_bonus == {"cha": 2, "dex": 1}


def test_no_species_choices_when_neutral():
    sheet = sheet_from_request(parsed(species_skill="none", species_feat=""))
    assert sheet.choices.species_choices == {}


def test_species_skill_alone_goes_to_species_choices():
    sheet = sheet_from_request(parsed(species_skill="stealth", species_feat=""))
    assert sheet.choices.species_choices == {"skill": "stealth"}


def test_no_fighting_style_when_neutral():
    assert sheet_from_request(parsed(fighting_style="")).choices.fighting_style is None


def test_feat_choices_are_empty_when_no_picks():
    sheet = sheet_from_request(parsed(feat_skills=[], species_feat_skills=[]))
    assert sheet.choices.feat_choices == {}


def test_background_feat_picks_go_under_its_key():
    request = parsed(
        background=background_input(feat="skilled"), species_feat="", species_skill="none",
        feat_skills=["medicine", "religion", "nature"], species_feat_skills=[],
    )
    sheet = sheet_from_request(request)
    assert sheet.choices.feat_choices == {"skilled": ["medicine", "religion", "nature"]}


def test_same_feat_twice_uses_second_key_for_species_picks():
    request = parsed(
        background=background_input(feat="skilled"), species_feat="skilled",
        feat_skills=["medicine", "religion", "nature"],
        species_feat_skills=["history", "arcana", "investigation"],
    )
    sheet = sheet_from_request(request)
    assert sheet.choices.feat_choices == {
        "skilled": ["medicine", "religion", "nature"],
        "skilled#2": ["history", "arcana", "investigation"],
    }


def test_species_picks_do_not_overwrite_background_key_when_feats_differ():
    request = parsed(
        background=background_input(feat="skilled"), species_feat="magic_initiate",
        feat_skills=["medicine", "religion", "nature"], species_feat_skills=["x"],
    )
    sheet = sheet_from_request(request)
    assert sheet.choices.feat_choices["skilled"] == ["medicine", "religion", "nature"]
    assert sheet.choices.feat_choices["magic_initiate"] == ["x"]


def test_ability_scores_use_int_key():
    sheet = sheet_from_request(parsed())
    assert set(sheet.choices.ability_scores) == {"str", "dex", "con", "int", "wis", "cha"}


def test_sheet_from_request_has_default_hero_id():
    assert sheet_from_request(parsed()).choices.hero_id == "h1"


def test_sheet_from_request_copies_lists():
    request = parsed()
    sheet = sheet_from_request(request)
    sheet.means.append("x")
    sheet.choices.class_skills.append("x")
    assert request.means == ["острый ум"]
    assert request.class_skills == ["perception", "survival"]


# condition_from_spec

def test_condition_narrative():
    spec = trigger_spec(kind="narrative", ref="текст")
    assert condition_from_spec(spec) == {"narrative": "текст"}


def test_condition_flag_hero_has_hero_at():
    assert condition_from_spec(trigger_spec(kind="flag", ref="f")) == {"flag": "f"}
    assert condition_from_spec(trigger_spec(kind="hero_has", ref="sword")) == {"hero_has": "sword"}
    assert condition_from_spec(trigger_spec(kind="hero_at", ref="cellar")) == {"hero_at": "cellar"}


def test_condition_npc_status_default_is_alive():
    spec = trigger_spec(kind="npc_status", ref="innkeeper", status="")
    assert condition_from_spec(spec) == {"npc_status": {"id": "innkeeper", "is": "alive"}}


def test_condition_npc_status_keeps_given_status():
    spec = trigger_spec(kind="npc_status", ref="innkeeper", status="dead")
    assert condition_from_spec(spec) == {"npc_status": {"id": "innkeeper", "is": "dead"}}


def test_condition_attitude_and_favor_take_gte():
    assert condition_from_spec(trigger_spec(kind="attitude", ref="grakh", gte=10)) == {
        "attitude": {"npc": "grakh", "gte": 10}
    }
    assert condition_from_spec(trigger_spec(kind="favor", ref="sun", gte=3)) == {
        "favor": {"god": "sun", "gte": 3}
    }


def test_condition_attitude_without_gte_raises():
    with pytest.raises(ValueError):
        condition_from_spec(trigger_spec(kind="attitude", ref="grakh", gte=0))


def test_condition_favor_without_gte_raises():
    with pytest.raises(ValueError):
        condition_from_spec(trigger_spec(kind="favor", ref="sun", gte=0))


@pytest.mark.parametrize(
    "kind, ref, extra, expected",
    [
        ("flag", "f", {}, Flag(name="f")),
        ("hero_has", "longsword", {}, HeroHas(item="longsword")),
        ("hero_at", "cellar", {}, HeroAt(location="cellar")),
        ("attitude", "grakh", {"gte": 4}, Attitude(npc="grakh", gte=4)),
        ("favor", "sun", {"gte": 2}, Favor(god="sun", gte=2)),
    ],
)
def test_all_structured_kinds_make_valid_triggers(registry, cfg, kind, ref, extra, expected):
    trigger = trigger_input(kind=kind, ref=ref, **extra)
    world = known(npcs=["grakh"], locations=["cellar"], pantheon=["sun"])
    ctx = creation(registry, cfg, known=world)
    result = apply(ctx, parsed(opportunity=[trigger]))
    assert result.status == "accepted"
    assert ctx.sheet.opportunity[0].if_ == expected
    assert ctx.sheet.opportunity[0].once is True


def test_hero_has_unknown_item_is_invalid_opportunity_ref(registry, cfg):
    _, result = run(registry, cfg, opportunity=[trigger_input(kind="hero_has", ref="no_such_item")])
    assert result.code == "opportunity_ref"
    assert "no_such_item" in result.message


def test_spells_prepared_and_gear_go_into_choices():
    request = parsed(
        spells=["fire_bolt", "magic_missile"], prepared=["magic_missile"],
        background_gear="gold",
    )
    choices = sheet_from_request(request).choices
    assert choices.spells == ["fire_bolt", "magic_missile"]
    assert choices.prepared == ["magic_missile"]
    assert choices.background_gear == "gold"


def test_hero_sheet_in_background_mode_is_not_available(registry, cfg):
    ctx = CreationContext(registry, cfg, BackgroundTask("fighter"))
    result = apply(ctx, parsed())
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"


def test_background_spec_in_sheet_mode_is_not_available(registry, cfg):
    ctx = creation(registry, cfg)
    request = parse_request({"type": "background_spec", **background_input()}, "hero_background")
    result = apply(ctx, request)
    assert isinstance(result, Invalid)
    assert result.code == "not_available_in_mode"
