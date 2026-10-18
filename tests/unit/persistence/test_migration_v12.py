# Ж2 (docs/plan-zh2.md, п. 0.12): миграция v11 -> v12 -- WorldSim.goals_checked_s (время последней
# проверки триггеров целей NPC; None -- ещё не проверялись).
# API: ai_dm.persistence.migrations.m0012_v11_to_v12.migrate_v11_to_v12(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[11] is migrate_v11_to_v12;
#   CURRENT_SCHEMA_VERSION >= 12. Правило: setdefault (заданное значение не перезаписывается).
#   Миграция заморожена: не импортирует ai_dm.state.* и content.
#   Фикстура: tests/fixtures/saves/v11 -- слот auto мира zh0_world (снята до правок кода Ж2).
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
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0012_v11_to_v12 import migrate_v11_to_v12
from ai_dm.persistence.store import save_slot
from ai_dm.state.save import SaveBundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V11 = FIXTURES / "v11"
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0012_v11_to_v12.py"
)


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, slot="auto", world_id=WORLD_ID):
    target = saves / world_id / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def raw_v11(sim=...):
    return {
        "manifest": {"schema_version": 11, "world_id": "w"},
        "world": {
            "world_id": "w",
            "npcs": {"a": {"id": "a", "goals": [], "attitude": 3}},
            "sim": {"last_day": 2, "pending_acts": []} if sim is ... else sim,
        },
        "heroes": [{"id": "h1", "name": "Арн"}],
        "session": {"turn_seq": 2},
    }


# реестр и фреймворк

def test_registry_has_step_from_v11():
    assert MIGRATIONS[11] is migrate_v11_to_v12
    assert CURRENT_SCHEMA_VERSION >= 12


def test_framework_sets_schema_version_twelve():
    assert migrate(raw_v11(), current_version=12)["manifest"]["schema_version"] == 12


def test_v11_to_v11_is_not_touched():
    assert migrate(raw_v11(), current_version=11) == raw_v11()


def test_already_v12_dict_is_not_migrated_again():
    data = raw_v11()
    data["manifest"]["schema_version"] = 12
    assert migrate(data, current_version=12) == data


def test_engine_v11_refuses_a_v12_dict():
    data = raw_v11()
    data["manifest"]["schema_version"] = 12
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=11)


def test_migration_does_not_mutate_input():
    data = raw_v11()
    before = copy.deepcopy(data)
    migrate_v11_to_v12(data)
    assert data == before


def test_migration_works_without_context_argument():
    assert migrate_v11_to_v12(raw_v11(), None) == migrate_v11_to_v12(raw_v11())


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


def test_whole_dict_migration_is_idempotent():
    once = migrate_v11_to_v12(raw_v11())
    assert migrate_v11_to_v12(once) == once


def test_result_is_a_deep_copy():
    data = raw_v11()
    result = migrate_v11_to_v12(data)
    result["world"]["npcs"]["a"]["attitude"] = 99
    result["world"]["sim"]["pending_acts"].append("x")
    assert data["world"]["npcs"]["a"]["attitude"] == 3
    assert data["world"]["sim"]["pending_acts"] == []


# поле sim.goals_checked_s

def test_sim_gets_null_goals_checked_s():
    sim = migrate_v11_to_v12(raw_v11())["world"]["sim"]
    assert "goals_checked_s" in sim
    assert sim["goals_checked_s"] is None


def test_existing_goals_checked_s_is_kept():
    data = raw_v11(sim={"goals_checked_s": 86400})
    assert migrate_v11_to_v12(data)["world"]["sim"]["goals_checked_s"] == 86400


def test_existing_zero_goals_checked_s_is_kept():
    data = raw_v11(sim={"goals_checked_s": 0})
    assert migrate_v11_to_v12(data)["world"]["sim"]["goals_checked_s"] == 0


def test_other_sim_fields_stay():
    sim = migrate_v11_to_v12(raw_v11())["world"]["sim"]
    assert (sim["last_day"], sim["pending_acts"]) == (2, [])


def test_other_parts_of_the_save_stay():
    result = migrate_v11_to_v12(raw_v11())
    assert result["world"]["npcs"] == raw_v11()["world"]["npcs"]
    assert result["heroes"] == raw_v11()["heroes"]
    assert result["session"] == raw_v11()["session"]
    assert result["manifest"] == {"schema_version": 11, "world_id": "w"}


def test_world_without_sim_gets_no_sim():
    data = raw_v11()
    del data["world"]["sim"]
    assert "sim" not in migrate_v11_to_v12(data)["world"]


def test_dict_without_world_is_fine():
    data = {"manifest": {"schema_version": 11, "world_id": "w"}}
    assert migrate(data, current_version=12)["manifest"]["schema_version"] == 12


# схема v12

def test_v12_schema_has_goals_checked_s_integer_or_null():
    sim = SaveBundle.model_json_schema()["$defs"]["WorldSim"]["properties"]
    assert {"type": "integer"} in sim["goals_checked_s"]["anyOf"]
    assert {"type": "null"} in sim["goals_checked_s"]["anyOf"]
    assert sim["goals_checked_s"]["default"] is None


def test_v11_fingerprint_is_kept_as_history_without_goals_checked_s():
    stored = json.loads((SCHEMA_DIR / "save_v11.schema.json").read_text(encoding="utf-8"))
    assert "goals_checked_s" not in stored["$defs"]["WorldSim"]["properties"]


# фикстура v11 и загрузка слота

def test_fixture_v11_is_v11_format():
    manifest = json.loads((FIXTURE_V11 / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((FIXTURE_V11 / "world" / "world.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 11
    assert "goals_checked_s" not in world["sim"]


def test_load_v11_returns_current_bundle(saves):
    install(saves, FIXTURE_V11)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v11_sim_has_no_goals_check_yet(saves):
    install(saves, FIXTURE_V11)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert bundle.world.sim.goals_checked_s is None


def test_load_v11_keeps_npcs(saves):
    install(saves, FIXTURE_V11)
    npcs = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).world.npcs
    assert set(npcs) == {"innkeeper", "mira", "old_tam", "grakh"}
    assert (npcs["innkeeper"].name, npcs["innkeeper"].attitude) == ("Гарт", 10)


def test_load_v11_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V11)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    backup = saves / WORLD_ID / "backups" / f"auto-v11-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V11)


def test_load_v11_rewrites_slot_as_v12_with_null_field(saves):
    folder = install(saves, FIXTURE_V11)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((folder / "world" / "world.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert world["sim"]["goals_checked_s"] is None


def test_load_v11_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V11)
    first = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, WORLD_ID, "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / WORLD_ID / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V11)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v12_slot_is_too_new_for_engine_v11(saves):
    install(saves, FIXTURE_V11)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, WORLD_ID, "auto", current_version=11)


def test_goals_checked_s_survives_save_and_load(saves):
    install(saves, FIXTURE_V11)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    bundle.world.sim.goals_checked_s = 172800
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert load_slot(saves, WORLD_ID, "auto").world.sim.goals_checked_s == 172800


@pytest.mark.parametrize(
    "name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat", "v6", "v7", "v8", "v9"],
)
def test_old_fixture_chain_reaches_current(saves, name):
    install(saves, FIXTURES / name, world_id="old_world")
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.world.sim.goals_checked_s is None


def test_v10_fixture_chain_reaches_current(saves):
    install(saves, FIXTURES / "v10")
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.world.sim.goals_checked_s is None
