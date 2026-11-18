# К3б-П4 (docs/plan-k3b.md): миграция v14 -> v15 -- HeroState.minions (призванные существа:
# Minion(monster_id, spell_id, hp_current, until_s)); данные не меняются, поле героя -- [].
# API: ai_dm.persistence.migrations.m0015_v14_to_v15.migrate_v14_to_v15(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[14] is migrate_v14_to_v15.
#   Отпечаток: tests/schema/save_v15.schema.json. Загрузка фикстуры v13 цепочкой до 15.
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
from ai_dm.persistence.migrations.m0015_v14_to_v15 import migrate_v14_to_v15
from ai_dm.state.save import SaveBundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V13 = FIXTURES / "v13"
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0015_v14_to_v15.py"
)


def raw_v14():
    return {
        "manifest": {"schema_version": 14, "world_id": "w"},
        "world": {"world_id": "w"},
        "heroes": [{"id": "h1", "inventory": [], "companions": []}],
        "session": {"turn_seq": 2},
    }


def test_registry_has_step_from_v14():
    assert MIGRATIONS[14] is migrate_v14_to_v15
    assert CURRENT_SCHEMA_VERSION >= 15


def test_framework_sets_schema_version_fifteen():
    assert migrate(raw_v14(), current_version=15)["manifest"]["schema_version"] == 15


def test_v14_to_v14_is_not_touched():
    assert migrate(raw_v14(), current_version=14) == raw_v14()


def test_engine_v14_refuses_a_v15_dict():
    data = raw_v14()
    data["manifest"]["schema_version"] = 15
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=14)


def test_migration_keeps_data_as_is():
    assert migrate_v14_to_v15(raw_v14()) == raw_v14()


def test_migration_does_not_mutate_input():
    data = raw_v14()
    before = copy.deepcopy(data)
    migrate_v14_to_v15(data)
    assert data == before


def test_migration_returns_a_copy():
    data = raw_v14()
    assert migrate_v14_to_v15(data) is not data


def test_migration_works_without_context_argument():
    assert migrate_v14_to_v15(raw_v14(), None) == migrate_v14_to_v15(raw_v14())


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# отпечаток v15

def test_v15_fingerprint_file_exists():
    assert (SCHEMA_DIR / "save_v15.schema.json").is_file()


def test_v15_hero_has_minions():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "minions" in defs["HeroState"]["properties"]


def test_v15_minion_fields():
    minion = SaveBundle.model_json_schema()["$defs"]["Minion"]["properties"]
    assert {"monster_id", "spell_id", "hp_current", "until_s"} <= set(minion)


def test_v14_fingerprint_has_no_minions():
    v14 = json.loads((SCHEMA_DIR / "save_v14.schema.json").read_text(encoding="utf-8"))
    assert "minions" not in v14["$defs"]["HeroState"]["properties"]


# загрузка слота v13 цепочкой до v15

def install(saves):
    shutil.copytree(FIXTURE_V13, saves / WORLD_ID / "slots" / "auto")
    return saves / WORLD_ID / "slots" / "auto"


def test_load_v13_gives_empty_minions(saves):
    install(saves)
    hero = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).heroes[0]
    assert hero.minions == []


def test_load_v13_rewrites_slot_as_current_version(saves):
    folder = install(saves)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
