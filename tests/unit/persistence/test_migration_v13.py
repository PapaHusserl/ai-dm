# ФС (docs/plan-fs.md, П3): миграция v12 -> v13 -- DeathRecord.cause + "left" (уход NPC без
# причины); данные не меняются.
# API: ai_dm.persistence.migrations.m0013_v12_to_v13.migrate_v12_to_v13(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[12] is migrate_v12_to_v13;
#   CURRENT_SCHEMA_VERSION >= 13. Миграция заморожена: не импортирует ai_dm.state.* и content.
import ast
import copy
from pathlib import Path

import pytest

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0013_v12_to_v13 import migrate_v12_to_v13

MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0013_v12_to_v13.py"
)


def raw_v12():
    return {
        "manifest": {"schema_version": 12, "world_id": "w"},
        "world": {
            "world_id": "w",
            "npcs": {"a": {"id": "a", "status": "alive", "attitude": 3, "death": None}},
            "sim": {"last_day": 2, "goals_checked_s": None},
        },
        "heroes": [{"id": "h1", "name": "Арн"}],
        "session": {"turn_seq": 2},
    }


def test_registry_has_step_from_v12():
    assert MIGRATIONS[12] is migrate_v12_to_v13
    assert CURRENT_SCHEMA_VERSION >= 13


def test_framework_sets_schema_version_thirteen():
    assert migrate(raw_v12(), current_version=13)["manifest"]["schema_version"] == 13


def test_v12_to_v12_is_not_touched():
    assert migrate(raw_v12(), current_version=12) == raw_v12()


def test_already_v13_dict_is_not_migrated_again():
    data = raw_v12()
    data["manifest"]["schema_version"] = 13
    assert migrate(data, current_version=13) == data


def test_engine_v12_refuses_a_v13_dict():
    data = raw_v12()
    data["manifest"]["schema_version"] = 13
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=12)


def test_migration_does_not_mutate_input():
    data = raw_v12()
    before = copy.deepcopy(data)
    migrate_v12_to_v13(data)
    assert data == before


def test_migration_works_without_context_argument():
    assert migrate_v12_to_v13(raw_v12(), None) == migrate_v12_to_v13(raw_v12())


def test_migration_keeps_data_unchanged():
    assert migrate_v12_to_v13(raw_v12()) == raw_v12()


def test_result_is_a_deep_copy():
    data = raw_v12()
    result = migrate_v12_to_v13(data)
    result["world"]["npcs"]["a"]["attitude"] = 99
    assert data["world"]["npcs"]["a"]["attitude"] == 3


def test_whole_dict_migration_is_idempotent():
    once = migrate_v12_to_v13(raw_v12())
    assert migrate_v12_to_v13(once) == once


def test_dict_without_world_is_fine():
    data = {"manifest": {"schema_version": 12, "world_id": "w"}}
    assert migrate(data, current_version=13)["manifest"]["schema_version"] == 13


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]
