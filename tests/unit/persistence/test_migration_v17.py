# М0-П3а (docs/plan-m0.md, решение 108): миграция v16 -> v17 -- Journey.walked_s (секунд
# пройдено с начала пути); данные не меняются, в сейвах v16 hero.journey -- None.
# API: ai_dm.persistence.migrations.m0017_v16_to_v17.migrate_v16_to_v17(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[16] is migrate_v16_to_v17.
#   Отпечаток: tests/schema/save_v17.schema.json. Загрузка фикстуры v13 цепочкой до 17.
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
from ai_dm.persistence.migrations.m0017_v16_to_v17 import migrate_v16_to_v17
from ai_dm.state.save import SaveBundle

ROOT = Path(__file__).resolve().parents[3]
FIXTURE_V13 = ROOT / "tests" / "fixtures" / "saves" / "v13"
SCHEMA_DIR = ROOT / "tests" / "schema"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    ROOT / "src" / "ai_dm" / "persistence" / "migrations" / "m0017_v16_to_v17.py"
)


def raw_v16():
    return {
        "manifest": {"schema_version": 16, "world_id": "w"},
        "world": {"world_id": "w"},
        "heroes": [{"id": "h1", "inventory": [], "companions": [], "journey": None}],
        "session": {"turn_seq": 2},
    }


def test_registry_has_step_from_v16():
    assert MIGRATIONS[16] is migrate_v16_to_v17
    assert CURRENT_SCHEMA_VERSION >= 17


def test_migration_result_shares_no_nested_objects_with_the_input():
    data = raw_v16()
    out = migrate_v16_to_v17(data)
    out["heroes"][0]["inventory"].append("x")
    assert data["heroes"][0]["inventory"] == []


def test_framework_sets_schema_version_seventeen():
    assert migrate(raw_v16(), current_version=17)["manifest"]["schema_version"] == 17


def test_v16_to_v16_is_not_touched():
    assert migrate(raw_v16(), current_version=16) == raw_v16()


def test_engine_v16_refuses_a_v17_dict():
    data = raw_v16()
    data["manifest"]["schema_version"] = 17
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=16)


def test_migration_keeps_data_as_is():
    assert migrate_v16_to_v17(raw_v16()) == raw_v16()


def test_migration_does_not_mutate_input():
    data = raw_v16()
    before = copy.deepcopy(data)
    migrate_v16_to_v17(data)
    assert data == before


def test_migration_returns_a_copy():
    data = raw_v16()
    assert migrate_v16_to_v17(data) is not data


def test_migration_works_without_context_argument():
    assert migrate_v16_to_v17(raw_v16(), None) == migrate_v16_to_v17(raw_v16())


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# отпечаток v17

def test_v17_fingerprint_file_exists():
    assert (SCHEMA_DIR / "save_v17.schema.json").is_file()


def test_v17_journey_has_walked_s():
    v17 = json.loads((SCHEMA_DIR / "save_v17.schema.json").read_text(encoding="utf-8"))
    assert "walked_s" in v17["$defs"]["Journey"]["properties"]


def test_v16_fingerprint_journey_has_no_walked_s():
    v16 = json.loads((SCHEMA_DIR / "save_v16.schema.json").read_text(encoding="utf-8"))
    assert "walked_s" not in v16["$defs"]["Journey"]["properties"]


def test_current_schema_journey_has_walked_s():
    assert "walked_s" in SaveBundle.model_json_schema()["$defs"]["Journey"]["properties"]


def test_journey_walked_s_defaults_to_zero():
    from ai_dm.state.hero import Journey

    assert Journey(to="b", start_id="a", pace="normal").walked_s == 0


# загрузка слота v13 цепочкой до v17

def install(saves):
    shutil.copytree(FIXTURE_V13, saves / WORLD_ID / "slots" / "auto")
    return saves / WORLD_ID / "slots" / "auto"


def test_load_v13_hero_journey_is_none(saves):
    install(saves)
    hero = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).heroes[0]
    assert hero.journey is None


def test_load_v13_rewrites_slot_as_current_version(saves):
    folder = install(saves)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
