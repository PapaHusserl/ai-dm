# Ф1 (F1-PLAN п.2, BACKLOG 44): запрос companion_update -- зверь-спутник Повелителя зверей.
# join / dead / gone; Invalid: no_beast_feature, companion_exists, companion_fields, no_companion;
# инструмент только в explore и не strict; журнал хода, /sheet, сохранение и загрузка.
import sys
from pathlib import Path

import pytest
from protocol_kit import make_bundle, make_ctx, req
from pydantic import ValidationError

from ai_dm.game.starter import ranger_choices
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import load_slot, save_auto
from ai_dm.protocol.apply import HANDLERS, apply
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.requests import REQUEST_MODELS, VISIBLE_TYPES, CompanionUpdate, parse_request
from ai_dm.protocol.schema import tool_set
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import sync_resources
from ai_dm.state.hero import Companion

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))
from game_kit import SAVED_AT, make_app, make_rig, scripted, settings  # noqa: E402
from master_kit import text_step, tools_step  # noqa: E402


def ranger_bundle(registry, subclass="beast_master", level=3, companions=()):
    bundle = make_bundle(registry)
    old = bundle.heroes[0]
    hero = build_character(ranger_choices("hero"), registry)
    hero.location_id = old.location_id
    hero.sheet.primary.level = level
    hero.sheet.level_history = ["ranger"] * level
    hero.sheet.primary.subclass_id = subclass
    sync_resources(hero, registry)
    hero.companions = list(companions)
    bundle.heroes[0] = hero
    return bundle


def ranger_ctx(registry, cfg, **kwargs):
    return make_ctx(registry, cfg, bundle=ranger_bundle(registry, **kwargs))


def join(ctx, **fields):
    data = {"action": "join", "name": "Акела", "kind": "волк", "notes": "из леса"}
    data.update(fields)
    return apply(ctx, req("companion_update", **data))


def leave(ctx, action):
    return apply(ctx, req("companion_update", action=action))


def wolf():
    return Companion(name="Акела", kind="волк", notes="из леса")


def companion_call(**fields):
    data = {"type": "companion_update", "action": "join", "name": "Акела", "kind": "волк"}
    data.update(fields)
    return {"name": "companion_update", "input": data}


# join

def test_join_sets_the_companion(registry, cfg):
    ctx = ranger_ctx(registry, cfg)
    decision = join(ctx)
    assert decision.status == "accepted"
    assert ctx.hero.companions == [wolf()]


def test_join_result_lists_one_companion(registry, cfg):
    decision = join(ranger_ctx(registry, cfg))
    assert decision.result == {
        "companions": [{"name": "Акела", "kind": "волк", "notes": "из леса"}]
    }


def test_join_log_has_name_and_kind(registry, cfg):
    decision = join(ranger_ctx(registry, cfg))
    assert decision.log == ["Зверь-спутник: Акела (волк) с героем"]


def test_join_without_notes_gives_empty_notes(registry, cfg):
    ctx = ranger_ctx(registry, cfg)
    join(ctx, notes="")
    assert ctx.hero.companions[0].notes == ""


def test_join_with_existing_companion_is_invalid_and_keeps_list(registry, cfg):
    ctx = ranger_ctx(registry, cfg, companions=[wolf()])
    decision = join(ctx, name="Рекс", kind="пёс")
    assert isinstance(decision, Invalid)
    assert decision.code == "companion_exists"
    assert ctx.hero.companions == [wolf()]


@pytest.mark.parametrize("field", ["name", "kind"])
def test_join_without_name_or_kind_is_invalid(registry, cfg, field):
    ctx = ranger_ctx(registry, cfg)
    decision = join(ctx, **{field: ""})
    assert isinstance(decision, Invalid)
    assert decision.code == "companion_fields"
    assert ctx.hero.companions == []


# герой без умения

@pytest.mark.parametrize("action", ["join", "dead", "gone"])
def test_hunter_gets_no_beast_feature(registry, cfg, action):
    ctx = ranger_ctx(registry, cfg, subclass="hunter", companions=[wolf()])
    decision = apply(ctx, req("companion_update", action=action, name="Рекс", kind="пёс"))
    assert isinstance(decision, Invalid)
    assert decision.code == "no_beast_feature"
    assert ctx.hero.companions == [wolf()]


def test_beast_master_below_level_3_has_no_feature(registry, cfg):
    ctx = ranger_ctx(registry, cfg, subclass=None, level=2)
    decision = join(ctx)
    assert isinstance(decision, Invalid)
    assert decision.code == "no_beast_feature"


def test_fighter_gets_no_beast_feature(registry, cfg):
    ctx = make_ctx(registry, cfg)
    decision = leave(ctx, "dead")
    assert isinstance(decision, Invalid)
    assert decision.code == "no_beast_feature"
    assert isinstance(join(ctx), Invalid)
    assert ctx.hero.companions == []


# dead / gone

def test_dead_clears_the_companion_and_logs_death(registry, cfg):
    ctx = ranger_ctx(registry, cfg, companions=[wolf()])
    decision = leave(ctx, "dead")
    assert decision.status == "accepted"
    assert ctx.hero.companions == []
    assert decision.result == {"companions": []}
    assert decision.log == ["Зверь-спутник Акела погиб"]


def test_gone_clears_the_companion_and_logs_leaving(registry, cfg):
    ctx = ranger_ctx(registry, cfg, companions=[wolf()])
    decision = leave(ctx, "gone")
    assert decision.status == "accepted"
    assert ctx.hero.companions == []
    assert decision.log == ["Зверь-спутник Акела ушёл"]


@pytest.mark.parametrize("action", ["dead", "gone"])
def test_leaving_without_companion_is_invalid(registry, cfg, action):
    ctx = ranger_ctx(registry, cfg)
    decision = leave(ctx, action)
    assert isinstance(decision, Invalid)
    assert decision.code == "no_companion"


def test_new_companion_is_accepted_after_death(registry, cfg):
    ctx = ranger_ctx(registry, cfg, companions=[wolf()])
    leave(ctx, "dead")
    decision = join(ctx, name="Бурый", kind="медведь")
    assert decision.status == "accepted"
    assert [c.name for c in ctx.hero.companions] == ["Бурый"]


def test_invalid_request_leaves_state_untouched(registry, cfg):
    ctx = ranger_ctx(registry, cfg, subclass="hunter")
    before = ctx.bundle.model_dump_json()
    join(ctx)
    assert ctx.bundle.model_dump_json() == before


# модель и инструмент

def test_model_is_registered_and_visible():
    assert REQUEST_MODELS["companion_update"] is CompanionUpdate
    assert "companion_update" in VISIBLE_TYPES
    assert "companion_update" in HANDLERS


def test_unknown_action_is_rejected():
    with pytest.raises(ValidationError):
        req("companion_update", action="tame")


def test_request_without_optional_fields_parses():
    model = parse_request({"type": "companion_update", "action": "dead"})
    assert (model.name, model.kind, model.notes) == (None, None, None)


def test_extra_field_is_rejected():
    with pytest.raises(ValidationError):
        req("companion_update", action="dead", hp=5)


def test_tool_is_in_explore_and_not_strict():
    tools = {t["name"]: t for t in tool_set("explore")}
    assert "companion_update" in tools
    assert tools["companion_update"]["strict"] is False


@pytest.mark.parametrize("mode", ["combat_classify", "combat_narrate", "npc_choice", "world"])
def test_tool_is_not_in_other_modes(mode):
    assert "companion_update" not in [t["name"] for t in tool_set(mode)]


# ход: журнал, /sheet, сохранение

def test_turn_record_has_companion_update_and_hero_gets_beast(registry, cfg, tmp_path):
    steps = [tools_step(companion_call()), text_step("Из чащи выходит волк.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=ranger_bundle(registry))
    result = rig.runner.play("Жду у костра")
    assert result.requests == ["companion_update"]
    record = rig.runner.bundle.memory.recent_turns[-1]
    assert record.requests == ["companion_update"]
    assert rig.runner.bundle.heroes[0].companions[0].name == "Акела"


def test_sheet_shows_companion_after_turn(registry, cfg, tmp_path):
    steps = [tools_step(companion_call()), text_step("Из чащи выходит волк.")]
    app = make_app(registry, tmp_path, scripted(steps), bundle=ranger_bundle(registry))
    app.handle("Жду у костра")
    text = "\n".join(app.handle("/sheet").lines)
    assert "Зверь-спутник: Акела (волк)" in text


def test_companion_survives_save_and_load(registry, cfg, tmp_path):
    bundle = ranger_bundle(registry)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    join(ctx)
    save_auto(tmp_path, bundle, saved_at=SAVED_AT, cfg=settings().rules)
    loaded = load_slot(tmp_path, bundle.world.world_id, "auto")
    assert loaded.manifest.schema_version == CURRENT_SCHEMA_VERSION == 13
    assert loaded.heroes[0].companions == [wolf()]
