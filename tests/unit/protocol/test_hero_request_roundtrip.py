# Б1б (дозадача аудита): request_from_sheet / trigger_spec -- обратные к sheet_from_request /
# condition_from_spec. Круг лист -> аргументы инструмента -> лист; previous пригоден как вызов.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import base_choices, base_sheet, sheet_input, trigger_input  # noqa: E402

from ai_dm.protocol.handlers.hero import (  # noqa: E402
    request_from_sheet,
    sheet_from_request,
    trigger_spec,
)
from ai_dm.protocol.requests import HeroSheetRequest  # noqa: E402
from ai_dm.rules.builder import HeroSheet  # noqa: E402
from ai_dm.state.triggers import Trigger  # noqa: E402

KINDS = {
    "narrative": {"ref": "герой узнаёт о сестре"},
    "flag": {"ref": "grail_seen"},
    "hero_has": {"ref": "crowbar"},
    "hero_at": {"ref": "cellar"},
    "npc_status": {"ref": "grakh", "status": "dead"},
    "attitude": {"ref": "innkeeper", "gte": 2},
    "favor": {"ref": "selune", "gte": 3},
}


def trigger_of(kind):
    spec = trigger_input(kind=kind, **KINDS[kind])
    from ai_dm.protocol.handlers.hero import condition_from_spec
    from ai_dm.protocol.requests import HeroTriggerSpec

    cond = condition_from_spec(HeroTriggerSpec.model_validate(spec))
    return Trigger.model_validate({"id": "o1", "if": cond, "then": "отомстить", "once": True})


def roundtrip(sheet):
    request = HeroSheetRequest.model_validate(request_from_sheet(sheet))
    return sheet_from_request(request)


def same(a, b):
    # hero_id в инструмент не входит (его ставит сборка мира)
    left, right = a.model_dump(mode="json"), b.model_dump(mode="json")
    left["choices"]["hero_id"] = right["choices"]["hero_id"] = None
    return left == right


def test_request_from_sheet_is_valid_hero_sheet_request():
    request = HeroSheetRequest.model_validate(request_from_sheet(base_sheet()))
    assert request.type == "hero_sheet"
    assert request.name == "Борин"


def test_request_from_sheet_matches_canonical_tool_input():
    # sheet_input (hero_kit) несёт все поля инструмента, в том числе expertise
    assert request_from_sheet(base_sheet()) == sheet_input()


def test_request_is_json_serializable():
    import json

    json.dumps(request_from_sheet(base_sheet()), ensure_ascii=False)


def test_roundtrip_gives_same_sheet():
    sheet = base_sheet()
    assert same(roundtrip(sheet), sheet)


@pytest.mark.parametrize("kind", list(KINDS))
def test_roundtrip_for_every_trigger_kind(kind):
    sheet = base_sheet(opportunity=[trigger_of(kind)])
    assert same(roundtrip(sheet), sheet)


@pytest.mark.parametrize("kind", list(KINDS))
def test_trigger_spec_kind_and_id(kind):
    spec = trigger_spec(trigger_of(kind))
    assert spec["kind"] == kind
    assert spec["id"] == "o1"
    assert spec["then"] == "отомстить"
    assert spec["ref"] == KINDS[kind]["ref"]


def test_trigger_spec_npc_status_keeps_status():
    assert trigger_spec(trigger_of("npc_status"))["status"] == "dead"


@pytest.mark.parametrize("kind", ["attitude", "favor"])
def test_trigger_spec_keeps_threshold(kind):
    assert trigger_spec(trigger_of(kind))["gte"] == KINDS[kind]["gte"]


@pytest.mark.parametrize("kind", ["narrative", "flag", "hero_has", "hero_at"])
def test_trigger_spec_plain_kinds_have_neutral_status_and_gte(kind):
    spec = trigger_spec(trigger_of(kind))
    assert spec["status"] == ""
    assert spec["gte"] == 0


def test_roundtrip_with_two_triggers_keeps_order():
    sheet = base_sheet(opportunity=[trigger_of("flag"), trigger_of("favor")])
    assert [t.if_.type for t in roundtrip(sheet).opportunity] == ["flag", "favor"]


def test_roundtrip_without_opportunity_and_with_three_means():
    sheet = base_sheet(opportunity=[], means=["а", "б", "в"])
    again = roundtrip(sheet)
    assert again.opportunity == []
    assert again.means == ["а", "б", "в"]


def test_roundtrip_keeps_expertise():
    choices = base_choices(expertise=["stealth", "perception"])
    sheet = HeroSheet(choices=choices, motive="м", means=["с"], opportunity=[])
    assert request_from_sheet(sheet)["expertise"] == ["stealth", "perception"]
    assert roundtrip(sheet).choices.expertise == ["stealth", "perception"]


def test_roundtrip_plus_one_each_bonus():
    choices = base_choices(background_bonus={"dex": 1, "con": 1, "cha": 1})
    sheet = HeroSheet(choices=choices, motive="м", means=["с"], opportunity=[])
    request = request_from_sheet(sheet)
    assert request["bonus_plus2"] == "none"
    assert request["bonus_plus1"] == ["dex", "con", "cha"]
    assert same(roundtrip(sheet), sheet)


def test_roundtrip_without_style_feat_and_kit():
    choices = base_choices(
        fighting_style=None, species_choices={"skill": "stealth"}, feat_choices={},
    )
    sheet = HeroSheet(choices=choices, motive="м", means=["с"], opportunity=[])
    request = request_from_sheet(sheet)
    assert request["fighting_style"] == ""
    assert request["species_feat"] == ""
    assert request["species_feat_skills"] == []
    assert same(roundtrip(sheet), sheet)


def test_roundtrip_without_species_skill_gives_none_marker():
    choices = base_choices(species_choices={"feat": "skilled"})
    sheet = HeroSheet(choices=choices, motive="м", means=["с"], opportunity=[])
    assert request_from_sheet(sheet)["species_skill"] == "none"


def test_feat_skills_go_to_their_own_fields():
    choices = base_choices(feat_choices={"skilled": ["medicine", "religion", "nature"]})
    request = request_from_sheet(HeroSheet(choices=choices, motive="м", means=["с"]))
    assert request["species_feat_skills"] == ["medicine", "religion", "nature"]
    assert request["feat_skills"] == []


def test_missing_class_kit_becomes_empty_string():
    sheet = HeroSheet(choices=base_choices(class_kit=None), motive="м", means=["с"])
    assert request_from_sheet(sheet)["class_kit"] == ""


def test_condition_without_gte_gives_zero_threshold():
    # gte=0 в инструменте значит «не задан»; у условия без порога (только lte) -- тоже 0
    cond = {"attitude": {"npc": "innkeeper", "lte": 1}}
    trigger = Trigger.model_validate({"id": "o1", "if": cond, "then": "т", "once": True})
    assert trigger_spec(trigger)["gte"] == 0
