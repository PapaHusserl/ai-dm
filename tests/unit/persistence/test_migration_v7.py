# Торговля, партия Т0 (TRADE-PLAN, разд. 7): миграция v6 -> v7.
# Ожидаемый API: ai_dm.persistence.migrations.m0007_v6_to_v7
#   migrate_v6_to_v7(data: dict, context: MigrationContext) -> dict -- чистое dict -> dict, вход не
#       мутирует; schema_version ставит фреймворк; MIGRATIONS[6] is migrate_v6_to_v7;
#       CURRENT_SCHEMA_VERSION == 7. Миграция заморожена: не импортирует ai_dm.state.* и content.
#   MigrationContext.npc_trade: dict[str, str] -- id NPC -> kind торговца (из пака); по умолч. {}.
#   Правила: у каждого NPC мира trade = None (если не задан); NPC из npc_trade получает профиль
#       {"kind": <kind>} (остальное -- умолчания модели); уже заданный trade не трогается; id из
#       npc_trade, которого нет в мире, игнорируется; session.current_scene (если есть) получает
#       trades = 0 и merchants_created = 0 (заданное не трогается).
#   Фикстура: tests/fixtures/saves/v6 -- слот auto мира old_world (NPC innkeeper и grakh; сейв
#       сгенерирован движком v6 из v5_combat).
import ast
import copy
import json
import shutil
from pathlib import Path

import pytest
from persist_kit import load_slot

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    MigrationContext,
    MigrationContextRequired,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0007_v6_to_v7 import migrate_v6_to_v7
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V6 = FIXTURES / "v6"
BACKUP_TS = "20260101T000000Z"
SAVED_AT = "2026-01-01T12:00:00Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0007_v6_to_v7.py"
)


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, slot="auto", world_id="old_world"):
    target = saves / world_id / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def ctx(npc_trade=None):
    return MigrationContext(item_cost={}, npc_trade=dict(npc_trade or {}))


def raw_npc(npc_id, **extra):
    return {"id": npc_id, "name": npc_id, "means": ["товары"], **extra}


def raw_v6(npcs=(), scene=None):
    session = {"turn_seq": 2, "active_combat": None, "current_scene": scene}
    return {
        "manifest": {"schema_version": 6, "world_id": "old_world"},
        "world": {"world_id": "old_world", "npcs": {n["id"]: n for n in npcs}},
        "heroes": [],
        "session": session,
    }


def raw_scene(**extra):
    return {"id": "scene_1", "started_at_s": 0, "player_turns": 1, **extra}


def npcs_of(data):
    return data["world"]["npcs"]


# реестр и фреймворк

def test_registry_has_step_from_v6():
    assert MIGRATIONS[6] is migrate_v6_to_v7
    assert CURRENT_SCHEMA_VERSION >= 7


def test_framework_sets_schema_version_seven():
    assert migrate(raw_v6(), context=ctx(), current_version=7)["manifest"]["schema_version"] >= 7


def test_v6_to_v6_is_not_touched():
    assert migrate(raw_v6(), current_version=6) == raw_v6()


def test_already_v7_dict_is_not_migrated_again():
    data = raw_v6([raw_npc("mara")])
    data["manifest"]["schema_version"] = 7
    assert migrate(data, context=ctx({"mara": "general"}), current_version=7) == data


def test_engine_v6_refuses_a_v7_dict():
    data = raw_v6()
    data["manifest"]["schema_version"] = 7
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=6)


def test_migrate_v6_to_v7_does_not_mutate_input():
    data = raw_v6([raw_npc("mara")], raw_scene())
    before = copy.deepcopy(data)
    migrate_v6_to_v7(data, ctx({"mara": "general"}))
    assert data == before


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


def test_context_npc_trade_is_empty_by_default():
    assert MigrationContext().npc_trade == {}


def test_context_npc_trade_is_not_shared_between_instances():
    first = MigrationContext()
    first.npc_trade["mara"] = "general"
    assert MigrationContext().npc_trade == {}


# NPC

def test_npc_without_pack_entry_gets_no_trade():
    result = migrate(raw_v6([raw_npc("guard")]), context=ctx(), current_version=7)
    assert npcs_of(result)["guard"].get("trade") is None


def test_every_npc_stays_without_trade_when_context_is_empty():
    result = migrate(raw_v6([raw_npc("a"), raw_npc("b")]), context=ctx(), current_version=7)
    assert [n.get("trade") for n in npcs_of(result).values()] == [None, None]


def test_pack_merchant_gets_profile_with_kind():
    result = migrate(raw_v6([raw_npc("mara")]), context=ctx({"mara": "general"}), current_version=7)
    assert npcs_of(result)["mara"]["trade"]["kind"] == "general"


def test_kind_comes_from_the_context_not_from_a_constant():
    result = migrate(raw_v6([raw_npc("mara")]), context=ctx({"mara": "smith"}), current_version=7)
    assert npcs_of(result)["mara"]["trade"]["kind"] == "smith"


def test_only_listed_npc_become_merchants():
    data = raw_v6([raw_npc("mara"), raw_npc("guard")])
    result = migrate(data, context=ctx({"mara": "general"}), current_version=7)
    assert npcs_of(result)["mara"]["trade"] is not None
    assert npcs_of(result)["guard"].get("trade") is None


def test_each_merchant_gets_its_own_kind():
    data = raw_v6([raw_npc("mara"), raw_npc("bron")])
    result = migrate(data, context=ctx({"mara": "general", "bron": "smith"}), current_version=7)
    assert [npcs_of(result)[i]["trade"]["kind"] for i in ("mara", "bron")] == ["general", "smith"]


def test_existing_trade_is_not_overwritten():
    data = raw_v6([raw_npc("mara", trade={"kind": "fence", "purse_cp": 7})])
    result = migrate(data, context=ctx({"mara": "general"}), current_version=7)
    assert npcs_of(result)["mara"]["trade"] == {"kind": "fence", "purse_cp": 7}


def test_context_id_missing_in_world_is_ignored():
    result = migrate(raw_v6([raw_npc("guard")]), context=ctx({"ghost": "general"}),
        current_version=7)
    assert list(npcs_of(result)) == ["guard"]


def test_other_npc_fields_stay():
    data = raw_v6([raw_npc("mara", attitude=30, location_id="town")])
    result = migrate(data, context=ctx({"mara": "general"}), current_version=7)
    npc = npcs_of(result)["mara"]
    assert (npc["name"], npc["attitude"], npc["location_id"]) == ("mara", 30, "town")


def test_world_without_npcs_is_fine():
    data = raw_v6()
    data["world"].pop("npcs")
    assert migrate(data, context=ctx({"mara": "general"}),
        current_version=7)["world"]["world_id"] == "old_world"


# сцена

def test_scene_gets_zero_counters():
    result = migrate(raw_v6(scene=raw_scene()), context=ctx(), current_version=7)
    scene = result["session"]["current_scene"]
    assert (scene["trades"], scene["merchants_created"]) == (0, 0)


def test_scene_counters_are_not_overwritten():
    data = raw_v6(scene=raw_scene(trades=3, merchants_created=1))
    scene = migrate(data, context=ctx(), current_version=7)["session"]["current_scene"]
    assert (scene["trades"], scene["merchants_created"]) == (3, 1)


def test_no_scene_stays_none():
    assert migrate(raw_v6(), context=ctx(), current_version=7)["session"]["current_scene"] is None


def test_other_scene_fields_stay():
    scene = migrate(raw_v6(scene=raw_scene()), context=ctx(),
        current_version=7)["session"]["current_scene"]
    assert (scene["id"], scene["player_turns"]) == ("scene_1", 1)


# фикстура v6 и загрузка слота

def test_fixture_v6_is_v6_format_without_trade():
    manifest = json.loads((FIXTURE_V6 / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((FIXTURE_V6 / "world" / "world.json").read_text(encoding="utf-8"))
    session = json.loads((FIXTURE_V6 / "session.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 6
    assert all("trade" not in n for n in world["npcs"].values())
    assert "trades" not in session["current_scene"]


def test_load_v6_returns_current_bundle(saves):
    install(saves, FIXTURE_V6)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v6_gives_every_npc_no_trade(saves):
    install(saves, FIXTURE_V6)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert {n.id: n.trade for n in bundle.world.npcs.values()} == {
        "innkeeper": None, "grakh": None,
    }


def test_load_v6_gives_scene_zero_counters(saves):
    install(saves, FIXTURE_V6)
    scene = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).session.current_scene
    assert (scene.trades, scene.merchants_created) == (0, 0)


def test_load_v6_with_pack_merchant_gets_profile(saves):
    install(saves, FIXTURE_V6)
    context = ctx({"innkeeper": "general"})
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    assert bundle.world.npcs["innkeeper"].trade.kind == "general"
    assert bundle.world.npcs["grakh"].trade is None


def test_loaded_pack_merchant_has_empty_stock(saves):
    install(saves, FIXTURE_V6)
    context = ctx({"innkeeper": "general"})
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    assert bundle.world.npcs["innkeeper"].trade.stock == []


def test_load_v6_keeps_heroes_and_last_combat(saves):
    install(saves, FIXTURE_V6)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert {e.item_id: e.qty for e in bundle.heroes[0].inventory}["scimitar"] == 2
    assert bundle.session.last_combat.defeated == ["goblin", "goblin"]


def test_load_v6_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V6)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v6-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V6)


def test_load_v6_rewrites_slot_as_v7(saves):
    folder = install(saves, FIXTURE_V6)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] >= 7


def test_load_v6_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V6)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V6)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v7_slot_is_too_new_for_engine_v6(saves):
    install(saves, FIXTURE_V6)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "auto", current_version=6)


def test_v7_save_and_load_round_trip_keeps_trade(saves):
    install(saves, FIXTURE_V6)
    context = ctx({"innkeeper": "general"})
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert again.world.npcs["innkeeper"].trade == bundle.world.npcs["innkeeper"].trade


@pytest.mark.parametrize("name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat"])
def test_old_fixture_chain_reaches_v7(saves, name):
    install(saves, FIXTURES / name)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version >= 7


# контекст обязателен (как у v5 -> v6)

def test_v6_without_context_is_refused():
    with pytest.raises(MigrationContextRequired):
        migrate(raw_v6([raw_npc("mara")]))


def test_v6_without_context_is_refused_even_without_npcs():
    with pytest.raises(MigrationContextRequired):
        migrate(raw_v6())


def test_explicit_none_trade_is_filled_from_the_context():
    data = raw_v6([raw_npc("mara", trade=None)])
    result = migrate(data, context=ctx({"mara": "general"}), current_version=7)
    assert npcs_of(result)["mara"]["trade"]["kind"] == "general"


def test_from_registry_passes_npc_trade_to_the_context(registry):
    context = MigrationContext.from_registry(registry, {"mara": "general"})
    assert context.npc_trade == {"mara": "general"}
    assert context.item_cost["longsword"] > 0


def test_from_registry_without_npc_trade_gives_empty_dict(registry):
    assert MigrationContext.from_registry(registry).npc_trade == {}


# пак не загрузился: context.npc_trade is None

def raw_context_without_pack():
    context = ctx()
    context.npc_trade = None
    return context


def test_unloaded_pack_gives_no_merchants():
    result = migrate(raw_v6([raw_npc("mara")]), context=raw_context_without_pack())
    assert npcs_of(result)["mara"].get("trade") is None


def test_unloaded_pack_goes_to_the_report():
    context = raw_context_without_pack()
    migrate(raw_v6([raw_npc("mara")]), context=context, current_version=7)
    assert context.report == ["пак не загружен — торговцы пака не проставлены"]


def test_unloaded_pack_still_migrates_scene_and_version():
    result = migrate(raw_v6(scene=raw_scene()), context=raw_context_without_pack())
    assert result["session"]["current_scene"]["trades"] == 0
    assert result["manifest"]["schema_version"] >= 7


def test_loaded_pack_without_merchants_leaves_report_empty():
    context = ctx()
    migrate(raw_v6([raw_npc("mara")]), context=context, current_version=7)
    assert context.report == []


def test_unloaded_pack_report_reaches_the_warning():
    context = raw_context_without_pack()
    migrate(raw_v6(), context=context, current_version=7)
    assert "торговцы пака не проставлены" in context.warning()


def test_load_v6_with_unloaded_pack_reports_and_has_no_trade(saves):
    install(saves, FIXTURE_V6)
    context = raw_context_without_pack()
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, context=context)
    assert all(n.trade is None for n in bundle.world.npcs.values())
    assert len([line for line in context.report if "пак не загружен" in line]) == 1


# неполные словари

def test_dict_without_session_is_fine():
    data = {"manifest": {"schema_version": 6, "world_id": "w"}, "world": {"npcs": {}}}
    assert migrate(data, context=ctx(), current_version=7)["manifest"]["schema_version"] >= 7


def test_dict_without_world_is_fine():
    data = {"manifest": {"schema_version": 6, "world_id": "w"}, "session": {}}
    assert migrate(data, context=ctx(), current_version=7)["manifest"]["schema_version"] >= 7
