# Шаг 262 П1 (docs/plan-262.md): миграция v17 -> v18 -- Location.hostile / traps / hidden /
# garrison; данные не меняются, у локаций без новых ключей поля берут умолчания.
# API: ai_dm.persistence.migrations.m0018_v17_to_v18.migrate_v17_to_v18(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[17] is migrate_v17_to_v18.
#   Отпечаток: tests/schema/save_v18.schema.json; save_v17.schema.json не тронут.
import copy
import json
from pathlib import Path

import pytest

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, SaveTooNew, migrate
from ai_dm.persistence.migrations.m0018_v17_to_v18 import migrate_v17_to_v18
from ai_dm.state.save import SaveBundle
from ai_dm.state.world import Location

SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
NEW_FIELDS = {"hostile", "traps", "hidden", "garrison"}


def raw_v17():
    return {
        "manifest": {"schema_version": 17, "world_id": "w"},
        "world": {
            "world_id": "w",
            "locations": {"cellar": {"id": "cellar", "name": "Подвал", "visited": True}},
        },
        "heroes": [{"id": "h1", "inventory": []}],
        "session": {"turn_seq": 2},
    }


def load_schema(version):
    return json.loads((SCHEMA_DIR / f"save_v{version}.schema.json").read_text(encoding="utf-8"))


def test_registry_has_step_from_v17():
    assert MIGRATIONS[17] is migrate_v17_to_v18
    assert CURRENT_SCHEMA_VERSION >= 18


def test_framework_sets_schema_version_eighteen():
    assert migrate(raw_v17(), current_version=18)["manifest"]["schema_version"] == 18


def test_v17_to_v17_is_not_touched():
    assert migrate(raw_v17(), current_version=17) == raw_v17()


def test_engine_v17_refuses_a_v18_dict():
    data = raw_v17()
    data["manifest"]["schema_version"] = 18
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=17)


def test_migration_keeps_other_data_equal():
    out = migrate(raw_v17(), current_version=18)
    out["manifest"]["schema_version"] = 17
    assert out == raw_v17()


def test_migration_does_not_mutate_input():
    data = raw_v17()
    before = copy.deepcopy(data)
    migrate_v17_to_v18(data)
    assert data == before


def test_migration_returns_a_copy_sharing_no_nested_objects():
    data = raw_v17()
    out = migrate_v17_to_v18(data)
    out["heroes"][0]["inventory"].append("x")
    assert data["heroes"][0]["inventory"] == []


def test_migration_works_without_context_argument():
    assert migrate_v17_to_v18(raw_v17(), None) == migrate_v17_to_v18(raw_v17())


def test_location_without_new_keys_gets_defaults():
    location = Location.model_validate(raw_v17()["world"]["locations"]["cellar"])
    assert location.hostile is False
    assert location.traps == []
    assert location.hidden is None
    assert location.garrison == []


# отпечаток v18

def test_v18_fingerprint_file_exists():
    assert (SCHEMA_DIR / "save_v18.schema.json").is_file()


def test_v18_fingerprint_equals_current_schema():
    assert load_schema(18) == json.loads(json.dumps(SaveBundle.model_json_schema()))


def test_v18_location_has_new_fields():
    assert set(load_schema(18)["$defs"]["Location"]["properties"]) >= NEW_FIELDS


def test_v17_fingerprint_is_untouched_location_has_no_new_fields():
    assert not NEW_FIELDS & set(load_schema(17)["$defs"]["Location"]["properties"])
