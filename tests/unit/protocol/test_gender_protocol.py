# К0-фикс-б (K0-FIX-PLAN, шаг 7, BACKLOG 39): пол и местоимения в протоколе -- npc_create,
# npc_update (explore и world), hero_sheet, pack (схемы и обработчики).
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import sheet_input  # noqa: E402
from import_kit import guard_input, import_task, npc_input, pack_input  # noqa: E402
from protocol_kit import dump, make_ctx, req  # noqa: E402

from ai_dm.protocol import schema  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.context import CreationContext  # noqa: E402
from ai_dm.protocol.decision import Decision, Invalid  # noqa: E402
from ai_dm.protocol.handlers.hero import sheet_from_request  # noqa: E402
from ai_dm.protocol.requests import parse_request  # noqa: E402

ENUM = ["male", "female", "other", "none"]


def walk(node):
    if isinstance(node, dict):
        yield node
        for value in node.values():
            yield from walk(value)
    elif isinstance(node, list):
        for item in node:
            yield from walk(item)


def tool_named(mode, name):
    return next(t for t in schema.tool_set(mode) if t["name"] == name)


def props_of(mode, name):
    return tool_named(mode, name)["input_schema"]["properties"]


# схемы

@pytest.mark.parametrize(
    ("mode", "name"), [("explore", "npc_create"), ("world", "npc_create")]
)
def test_npc_create_tools_have_gender_enum_without_unset(mode, name):
    props = props_of(mode, name)
    assert props["gender"]["enum"] == ENUM
    assert props["pronouns"]["type"] == "string"


@pytest.mark.parametrize("mode", ["explore", "world"])
def test_npc_update_tools_have_gender_enum_with_unset(mode):
    props = props_of(mode, "npc_update")
    assert props["gender"]["enum"] == [*ENUM, "unset"]
    assert props["pronouns"]["type"] == "string"


def test_hero_sheet_tool_has_gender_enum_and_pronouns():
    props = props_of("hero_sheet", "hero_sheet")
    assert props["gender"]["enum"] == ENUM
    assert props["pronouns"]["type"] == "string"


def test_pack_tool_npc_items_have_gender_enum_and_pronouns():
    props = props_of("pack_import", "pack")["npcs"]["items"]["properties"]
    assert props["gender"]["enum"] == ENUM
    assert props["pronouns"]["type"] == "string"


def test_hero_sheet_still_requires_every_property():
    for node in walk(tool_named("hero_sheet", "hero_sheet")["input_schema"]):
        if "properties" in node:
            assert node["required"] == list(node["properties"])


# старые вызовы (журналы до К0-фикс-б, replay): без новых полей разбираются с дефолтами

def test_old_npc_create_call_without_gender_parses():
    request = parse_request(
        {"type": "npc_create", "id": "a", "name": "А", "means": ["м"], "named": False}
    )
    assert request.gender in (None, "none")
    assert request.pronouns in (None, "")


def test_old_npc_update_call_without_gender_parses_and_is_not_empty_by_gender():
    request = parse_request({"type": "npc_update", "npc_id": "aldric", "attitude_delta": 3})
    assert request.gender in (None, "none")


def test_old_world_npc_update_call_without_gender_parses():
    data = {"type": "npc_update", "npc_id": "aldric", "then_ref": "c", "location_id": "vale"}
    assert parse_request(data, "world").type == "npc_update"


def test_old_hero_sheet_call_without_gender_parses():
    request = parse_request(sheet_input(), "hero_sheet")
    assert request.gender in (None, "none")


# npc_create

def new_npc(**fields):
    data = {"id": "brana", "name": "Бранка", "means": ["кузница"], "named": True}
    data.update(fields)
    return req("npc_create", **data)


def test_npc_create_sets_gender(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert apply(ctx, new_npc(gender="female")).status == "accepted"
    assert ctx.bundle.world.npcs["brana"].gender == "female"


def test_npc_create_sets_pronouns(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc(gender="other", pronouns="они"))
    npc = ctx.bundle.world.npcs["brana"]
    assert (npc.gender, npc.pronouns) == ("other", "они")


def test_npc_create_without_gender_leaves_it_unset(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc())
    npc = ctx.bundle.world.npcs["brana"]
    assert npc.gender is None
    assert npc.pronouns == ""


def test_npc_create_none_gender_is_unset(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, new_npc(gender="none", pronouns=""))
    assert ctx.bundle.world.npcs["brana"].gender is None


def test_npc_create_log_mentions_gender_word(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, new_npc(gender="female"))
    assert "женский" in " ".join(decision.log)


# npc_update

def update(**fields):
    return req("npc_update", npc_id="aldric", **fields)


def test_npc_update_with_only_gender_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, update(gender="male"))
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].gender == "male"


def test_npc_update_with_only_pronouns_is_accepted(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, update(pronouns="он, господин"))
    assert decision.status == "accepted"
    assert ctx.bundle.world.npcs["aldric"].pronouns == "он, господин"


def test_npc_update_gender_log_names_npc_and_gender_word(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, update(gender="female"))
    text = " ".join(decision.log)
    assert ctx.bundle.world.npcs["aldric"].name in text
    assert "женский" in text


def test_npc_update_empty_pronouns_does_not_change(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, update(gender="other", pronouns="они"))
    apply(ctx, update(gender="female", pronouns=""))
    npc = ctx.bundle.world.npcs["aldric"]
    assert (npc.gender, npc.pronouns) == ("female", "они")


def test_npc_update_none_gender_does_not_change(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, update(gender="female"))
    apply(ctx, update(gender="none", pronouns="она"))
    npc = ctx.bundle.world.npcs["aldric"]
    assert (npc.gender, npc.pronouns) == ("female", "она")


def test_npc_update_none_and_empty_only_is_still_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    before = dump(ctx)
    decision = apply(ctx, update(gender="none", pronouns=""))
    assert isinstance(decision, Invalid)
    assert decision.code == "empty_update"
    assert dump(ctx) == before


def test_npc_update_gender_together_with_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, update(gender="male", attitude_delta=5))
    npc = ctx.bundle.world.npcs["aldric"]
    assert (npc.gender, npc.attitude) == ("male", 5)


def test_npc_update_unknown_npc_with_gender_is_invalid(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, req("npc_update", npc_id="nobody", gender="male"))
    assert isinstance(decision, Invalid)
    assert decision.code == "unknown_npc"


def test_npc_update_gender_does_not_touch_other_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, update(gender="male"))
    assert ctx.bundle.world.npcs["grakh"].gender is None


# npc_update роли world

def world_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg, mode="world")
    ctx.candidate_refs = ["cand-1"]
    ctx.verdict_refs = []
    return ctx


def world_update(**fields):
    data = {"type": "npc_update", "npc_id": "aldric", "then_ref": "cand-1"}
    data.update(fields)
    return parse_request(data, "world")


def test_world_npc_update_with_only_gender_is_accepted(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(gender="female"))
    assert isinstance(decision, Decision)
    assert ctx.bundle.world.npcs["aldric"].gender == "female"


def test_world_npc_update_with_only_pronouns_is_accepted(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(pronouns="они"))
    assert isinstance(decision, Decision)
    assert ctx.bundle.world.npcs["aldric"].pronouns == "они"


def test_world_npc_update_without_changes_is_still_empty(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(gender="none", pronouns=""))
    assert isinstance(decision, Invalid)
    assert decision.code == "empty_update"


def test_world_npc_update_gender_still_needs_a_candidate(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(gender="female", then_ref="other"))
    assert isinstance(decision, Invalid)
    assert decision.code == "invalid_then_ref"
    assert ctx.bundle.world.npcs["aldric"].gender is None


@pytest.mark.parametrize(
    "fields",
    [{"attitude_delta": 5}, {"location_id": "forest"}, {"follows": "hero"}],
)
def test_world_npc_update_with_only_old_fields_is_still_accepted(registry, cfg, fields):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(npc_id="grakh", **fields))
    assert isinstance(decision, Decision)
    assert decision.status == "accepted"


def test_world_npc_update_with_only_status_is_judged_not_empty(registry, cfg):
    ctx = world_ctx(registry, cfg)
    decision = apply(ctx, world_update(status="dead", cause="goal"))
    assert getattr(decision, "code", None) != "empty_update"
    assert decision.status == "rejected"


def test_npc_update_pronouns_log_names_npc_and_pronouns(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, update(pronouns="они"))
    text = " ".join(decision.log)
    assert "Олдрик" in text
    assert "они" in text


# сброс пола и местоимений (решение В-1)

def reset_ctx(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, update(gender="female", pronouns="она"))
    return ctx


def test_npc_update_unset_clears_gender(registry, cfg):
    ctx = reset_ctx(registry, cfg)
    decision = apply(ctx, update(gender="unset"))
    assert decision.status == "accepted"
    npc = ctx.bundle.world.npcs["aldric"]
    assert npc.gender is None
    assert npc.pronouns == "она"


def test_npc_update_unset_log(registry, cfg):
    ctx = reset_ctx(registry, cfg)
    decision = apply(ctx, update(gender="unset"))
    assert "Олдрик: пол не задан" in decision.log


def test_npc_update_dash_clears_pronouns(registry, cfg):
    ctx = reset_ctx(registry, cfg)
    decision = apply(ctx, update(pronouns="-"))
    assert decision.status == "accepted"
    npc = ctx.bundle.world.npcs["aldric"]
    assert npc.pronouns == ""
    assert npc.gender == "female"
    assert "Олдрик: местоимения не заданы" in decision.log


def test_npc_update_unset_and_dash_clear_both(registry, cfg):
    ctx = reset_ctx(registry, cfg)
    apply(ctx, update(gender="unset", pronouns="-"))
    npc = ctx.bundle.world.npcs["aldric"]
    assert (npc.gender, npc.pronouns) == (None, "")


def test_npc_update_unset_is_not_empty(registry, cfg):
    ctx = make_ctx(registry, cfg)
    assert apply(ctx, update(gender="unset")).status == "accepted"


def test_npc_update_set_log_and_pronouns_log(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = apply(ctx, update(gender="male", pronouns="он"))
    assert "Олдрик: пол мужской" in decision.log
    assert "Олдрик: местоимения он" in decision.log


def test_world_npc_update_unset_and_dash(registry, cfg):
    ctx = world_ctx(registry, cfg)
    ctx.bundle.world.npcs["aldric"].gender = "male"
    ctx.bundle.world.npcs["aldric"].pronouns = "он"
    decision = apply(ctx, world_update(gender="unset", pronouns="-"))
    assert isinstance(decision, Decision)
    npc = ctx.bundle.world.npcs["aldric"]
    assert (npc.gender, npc.pronouns) == (None, "")


@pytest.mark.parametrize("kind", ["npc_create", "hero_sheet", "pack"])
def test_unset_is_not_a_gender_outside_npc_update(kind):
    with pytest.raises(ValueError):
        if kind == "npc_create":
            parse_request(
                {"type": "npc_create", "id": "a", "name": "А", "means": ["м"], "gender": "unset"}
            )
        elif kind == "hero_sheet":
            parse_request(sheet_input(gender="unset"), "hero_sheet")
        else:
            parse_request(pack_input(npcs=[npc_input(gender="unset")]), "pack_import")


def test_hero_sheet_and_pack_schemas_have_no_unset():
    assert "unset" not in props_of("hero_sheet", "hero_sheet")["gender"]["enum"]
    npc = props_of("pack_import", "pack")["npcs"]["items"]["properties"]
    assert "unset" not in npc["gender"]["enum"]


# hero_sheet

def test_hero_sheet_request_gender_goes_to_choices():
    request = parse_request(sheet_input(gender="female", pronouns="она"), "hero_sheet")
    choices = sheet_from_request(request).choices
    assert (choices.gender, choices.pronouns) == ("female", "она")


def test_hero_sheet_request_without_gender_has_unset_choices():
    request = parse_request(sheet_input(), "hero_sheet")
    choices = sheet_from_request(request).choices
    assert choices.gender is None
    assert choices.pronouns == ""


def test_hero_sheet_request_none_gender_is_unset():
    request = parse_request(sheet_input(gender="none", pronouns=""), "hero_sheet")
    assert sheet_from_request(request).choices.gender is None


def test_hero_sheet_request_rejects_unknown_gender():
    with pytest.raises(ValueError):
        parse_request(sheet_input(gender="x"), "hero_sheet")


# pack: конвертер в файлы

def pack_rows(registry, cfg, npcs):
    ctx = CreationContext(registry, cfg, import_task())
    decision = apply(ctx, parse_request(pack_input(npcs=npcs), "pack_import"))
    assert isinstance(decision, Decision)
    return {row["id"]: row for row in ctx.files["npcs.yaml"]}


def test_pack_npc_gender_goes_to_npcs_yaml(registry, cfg):
    rows = pack_rows(registry, cfg, [npc_input(gender="female", pronouns="она")])
    assert rows["mara"]["gender"] == "female"
    assert rows["mara"]["pronouns"] == "она"


def test_pack_npc_without_gender_has_no_such_keys(registry, cfg):
    rows = pack_rows(registry, cfg, [guard_input()])
    assert "gender" not in rows["guard"]
    assert "pronouns" not in rows["guard"]


def test_pack_npc_none_gender_has_no_key(registry, cfg):
    rows = pack_rows(registry, cfg, [npc_input(gender="none", pronouns="")])
    assert "gender" not in rows["mara"]


def test_pack_npc_pronouns_without_gender_are_kept(registry, cfg):
    rows = pack_rows(registry, cfg, [npc_input(pronouns="они")])
    assert rows["mara"]["pronouns"] == "они"
    assert "gender" not in rows["mara"]
