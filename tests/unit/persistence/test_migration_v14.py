# БП (docs/plan-bp.md): миграция v13 -> v14 -- стрелы поштучно: у героев запись arrows
# qty *= 20, cost_cp //= 20 (100 -> 5, 0 -> 0); схема не меняется.
# API: ai_dm.persistence.migrations.m0014_v13_to_v14.migrate_v13_to_v14(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[13] is migrate_v13_to_v14.
#   Фикстура: tests/fixtures/saves/v13 -- слот auto мира zh0_world, собран из v11
#   (герой Арн: arrows 9x100 и 1x0).
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
from ai_dm.persistence.migrations.m0014_v13_to_v14 import migrate_v13_to_v14

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V13 = FIXTURES / "v13"
SCHEMA_DIR = Path(__file__).resolve().parents[2] / "schema"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0014_v13_to_v14.py"
)


def raw_v13():
    return {
        "manifest": {"schema_version": 13, "world_id": "w"},
        "world": {"world_id": "w"},
        "heroes": [{
            "id": "h1",
            "inventory": [
                {"item_id": "arrows", "qty": 1, "cost_cp": 100, "quality": None},
                {"item_id": "arrows", "qty": 9, "cost_cp": 100, "quality": None},
                {"item_id": "arrows", "qty": 3, "cost_cp": 0, "quality": None},
                {"item_id": "arrow_fire", "qty": 3, "cost_cp": 100, "quality": None},
                {"item_id": "longbow", "qty": 1, "cost_cp": 5000, "quality": None},
            ],
        }],
        "session": {"turn_seq": 2},
    }


def stacks(data):
    return [(e["item_id"], e["qty"], e["cost_cp"]) for e in data["heroes"][0]["inventory"]]


def test_registry_has_step_from_v13():
    assert MIGRATIONS[13] is migrate_v13_to_v14
    assert CURRENT_SCHEMA_VERSION >= 14


def test_framework_sets_schema_version_fourteen():
    assert migrate(raw_v13(), current_version=14)["manifest"]["schema_version"] == 14


def test_v13_to_v13_is_not_touched():
    assert migrate(raw_v13(), current_version=13) == raw_v13()


def test_engine_v13_refuses_a_v14_dict():
    data = raw_v13()
    data["manifest"]["schema_version"] = 14
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=13)


def test_arrows_become_single_arrows():
    assert stacks(migrate_v13_to_v14(raw_v13()))[:3] == [
        ("arrows", 20, 5), ("arrows", 180, 5), ("arrows", 60, 0),
    ]


def test_migrated_arrow_prices_stay_integers():
    entries = migrate_v13_to_v14(raw_v13())["heroes"][0]["inventory"][:3]
    assert [type(e["cost_cp"]) for e in entries] == [int, int, int]


def test_other_items_and_special_arrows_are_untouched():
    assert stacks(migrate_v13_to_v14(raw_v13()))[3:] == [
        ("arrow_fire", 3, 100), ("longbow", 1, 5000),
    ]


def test_migration_does_not_mutate_input():
    data = raw_v13()
    before = copy.deepcopy(data)
    migrate_v13_to_v14(data)
    assert data == before


def test_migration_works_without_context_argument():
    assert migrate_v13_to_v14(raw_v13(), None) == migrate_v13_to_v14(raw_v13())


def test_dict_without_heroes_is_kept():
    data = {"manifest": {"schema_version": 13}, "world": {}}
    assert migrate_v13_to_v14(data) == data


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


def test_v14_fingerprint_equals_v13_by_content():
    v13 = json.loads((SCHEMA_DIR / "save_v13.schema.json").read_text(encoding="utf-8"))
    v14 = json.loads((SCHEMA_DIR / "save_v14.schema.json").read_text(encoding="utf-8"))
    assert v13 == v14


# фикстура v13 и загрузка слота

def install(saves):
    shutil.copytree(FIXTURE_V13, saves / WORLD_ID / "slots" / "auto")
    return saves / WORLD_ID / "slots" / "auto"


def test_fixture_v13_is_v13_format():
    manifest = json.loads((FIXTURE_V13 / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 13


def read_raw(folder):
    hero = next((folder / "heroes").glob("*/hero.json"))
    return {
        "manifest": json.loads((folder / "manifest.json").read_text(encoding="utf-8")),
        "world": json.loads((folder / "world" / "world.json").read_text(encoding="utf-8")),
        "heroes": [json.loads(hero.read_text(encoding="utf-8"))],
        "session": json.loads((folder / "session.json").read_text(encoding="utf-8")),
    }


def test_fixture_v13_is_v11_fixture_migrated_plus_the_arrows():
    # связь фикстур держится кодом: v13 = migrate(v11, 13) + две записи стрел героя
    migrated = migrate(read_raw(FIXTURES / "v11"), current_version=13)
    expected = read_raw(FIXTURE_V13)
    arrows = [e for e in expected["heroes"][0]["inventory"] if e["item_id"] == "arrows"]
    assert len(arrows) == 2
    expected["heroes"][0]["inventory"] = [
        e for e in expected["heroes"][0]["inventory"] if e["item_id"] != "arrows"
    ]
    assert migrated["heroes"] == expected["heroes"]


def test_load_v13_gives_single_arrows(saves):
    install(saves)
    hero = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).heroes[0]
    arrows = [(e.qty, e.cost_cp) for e in hero.inventory if e.item_id == "arrows"]
    assert arrows == [(180, 5), (20, 0)]


def test_load_v13_rewrites_slot_as_v14(saves):
    folder = install(saves)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION


def test_load_v13_makes_backup(saves):
    install(saves)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert (saves / WORLD_ID / "backups" / f"auto-v13-{BACKUP_TS}").is_dir()
