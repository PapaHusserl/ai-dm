# ТМ (docs/plan-tm.md, §1 п.7): миграция v9 -> v10 -- итоги инструментов и дельта денег в записях
# памяти хода, отметка конца длинного отдыха героя.
# Ожидаемый API: ai_dm.persistence.migrations.m0010_v9_to_v10
#   migrate_v9_to_v10(data: dict, context=None) -> dict -- чистое dict -> dict, вход не мутирует;
#       schema_version ставит фреймворк; MIGRATIONS[9] is migrate_v9_to_v10;
#       CURRENT_SCHEMA_VERSION >= 10.
#   Правило: memory.recent_turns[*] получают outcomes=[] и money_delta_cp=0 (setdefault: заданные не
#       перезаписываются); heroes[*] получают long_rest_end_s=None (setdefault).
#   Миграция заморожена: не импортирует ai_dm.state.* и content; контекст не нужен.
#   Фикстура: tests/fixtures/saves/v9 -- слот auto мира old_world (сгенерирован движком v9).
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
from ai_dm.persistence.migrations.m0010_v9_to_v10 import migrate_v9_to_v10
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V9 = FIXTURES / "v9"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0010_v9_to_v10.py"
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


def raw_turn(seq=1, **extra):
    turn = {
        "turn_seq": seq, "at_s": 10, "player_input": "иду", "narration": "Идёшь.",
        "requests": ["gold"], "rolls": [], "scene_id": "s1",
    }
    turn.update(extra)
    return turn


def raw_v9(turns=None, heroes=None):
    return {
        "manifest": {"schema_version": 9, "world_id": "old_world"},
        "world": {"world_id": "old_world"},
        "heroes": heroes if heroes is not None else [{"id": "h1", "name": "Арн"}],
        "memory": {
            "scenes": [], "game_summary": "",
            "recent_turns": turns if turns is not None else [raw_turn(1), raw_turn(2)],
        },
        "session": {"turn_seq": 2},
    }


# реестр и фреймворк

def test_registry_has_step_from_v9():
    assert MIGRATIONS[9] is migrate_v9_to_v10
    assert CURRENT_SCHEMA_VERSION >= 10


def test_framework_sets_schema_version_ten():
    assert migrate(raw_v9(), current_version=10)["manifest"]["schema_version"] == 10


def test_chain_v9_to_v10_needs_no_context():
    result = migrate(raw_v9(), current_version=10)
    assert result["memory"]["recent_turns"][0]["outcomes"] == []


def test_v9_to_v9_is_not_touched():
    assert migrate(raw_v9(), current_version=9) == raw_v9()


def test_already_v10_dict_is_not_migrated_again():
    data = raw_v9()
    data["manifest"]["schema_version"] = 10
    assert migrate(data, current_version=10) == data


def test_engine_v9_refuses_a_v10_dict():
    data = raw_v9()
    data["manifest"]["schema_version"] = 10
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=9)


def test_migrate_v9_to_v10_does_not_mutate_input():
    data = raw_v9()
    before = copy.deepcopy(data)
    migrate_v9_to_v10(data)
    assert data == before


def test_migration_works_without_context_argument():
    assert migrate_v9_to_v10(raw_v9(), None) == migrate_v9_to_v10(raw_v9())


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# записи памяти хода

def test_turns_get_empty_outcomes():
    turns = migrate_v9_to_v10(raw_v9())["memory"]["recent_turns"]
    assert [t["outcomes"] for t in turns] == [[], []]


def test_turns_get_zero_money_delta():
    turns = migrate_v9_to_v10(raw_v9())["memory"]["recent_turns"]
    assert [t["money_delta_cp"] for t in turns] == [0, 0]


def test_outcomes_lists_are_not_shared_between_turns():
    turns = migrate_v9_to_v10(raw_v9())["memory"]["recent_turns"]
    turns[0]["outcomes"].append("x")
    assert turns[1]["outcomes"] == []


def test_existing_outcomes_and_money_delta_are_kept():
    data = raw_v9(turns=[raw_turn(1, outcomes=["Золото: +20 зм"], money_delta_cp=2000)])
    turn = migrate_v9_to_v10(data)["memory"]["recent_turns"][0]
    assert (turn["outcomes"], turn["money_delta_cp"]) == (["Золото: +20 зм"], 2000)


def test_other_turn_fields_stay():
    turn = migrate_v9_to_v10(raw_v9(turns=[raw_turn(7)]))["memory"]["recent_turns"][0]
    assert (turn["turn_seq"], turn["requests"], turn["scene_id"], turn["narration"]) == (
        7, ["gold"], "s1", "Идёшь.",
    )


def test_empty_recent_turns_is_fine():
    assert migrate_v9_to_v10(raw_v9(turns=[]))["memory"]["recent_turns"] == []


def test_memory_without_recent_turns_key_is_fine():
    data = raw_v9()
    del data["memory"]["recent_turns"]
    assert "recent_turns" not in migrate_v9_to_v10(data)["memory"]


def test_other_memory_fields_stay():
    data = raw_v9()
    data["memory"]["game_summary"] = "кратко"
    assert migrate_v9_to_v10(data)["memory"]["game_summary"] == "кратко"


# герои

def test_heroes_get_no_long_rest_mark():
    heroes = migrate_v9_to_v10(raw_v9(heroes=[{"id": "h1"}, {"id": "h2"}]))["heroes"]
    assert [h["long_rest_end_s"] for h in heroes] == [None, None]


def test_existing_long_rest_mark_is_kept():
    data = raw_v9(heroes=[{"id": "h1", "long_rest_end_s": 5000}])
    assert migrate_v9_to_v10(data)["heroes"][0]["long_rest_end_s"] == 5000


def test_other_hero_fields_stay():
    assert migrate_v9_to_v10(raw_v9())["heroes"][0]["name"] == "Арн"


def test_no_heroes_is_fine():
    assert migrate_v9_to_v10(raw_v9(heroes=[]))["heroes"] == []


# целый словарь

def test_dict_without_memory_and_heroes_is_fine():
    data = {"manifest": {"schema_version": 9, "world_id": "w"}}
    assert migrate(data, current_version=10)["manifest"]["schema_version"] == 10


def test_other_world_and_session_fields_stay():
    result = migrate_v9_to_v10(raw_v9())
    assert result["world"] == {"world_id": "old_world"}
    assert result["session"] == {"turn_seq": 2}


def test_whole_dict_migration_is_idempotent():
    once = migrate_v9_to_v10(raw_v9())
    assert migrate_v9_to_v10(once) == once


# фикстура v9 и загрузка слота

def test_fixture_v9_is_v9_format():
    manifest = json.loads((FIXTURE_V9 / "manifest.json").read_text(encoding="utf-8"))
    memory = json.loads((FIXTURE_V9 / "world" / "memory.json").read_text(encoding="utf-8"))
    hero = json.loads((FIXTURE_V9 / "heroes" / "01_арн" / "hero.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 9
    assert memory["recent_turns"]
    assert "outcomes" not in memory["recent_turns"][0]
    assert "money_delta_cp" not in memory["recent_turns"][0]
    assert "long_rest_end_s" not in hero


def test_load_v9_returns_current_bundle(saves):
    install(saves, FIXTURE_V9)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v9_turns_get_defaults(saves):
    install(saves, FIXTURE_V9)
    turns = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).memory.recent_turns
    assert turns
    assert all(t.outcomes == [] and t.money_delta_cp == 0 for t in turns)


def test_load_v9_hero_has_no_long_rest_mark(saves):
    install(saves, FIXTURE_V9)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.heroes[0].long_rest_end_s is None


def test_load_v9_keeps_turn_text(saves):
    install(saves, FIXTURE_V9)
    old = json.loads((FIXTURE_V9 / "world" / "memory.json").read_text(encoding="utf-8"))
    turns = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).memory.recent_turns
    assert [t.narration for t in turns] == [t["narration"] for t in old["recent_turns"]]


def test_load_v9_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V9)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v9-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V9)


def test_load_v9_rewrites_slot_as_v10(saves):
    folder = install(saves, FIXTURE_V9)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    memory = json.loads((folder / "world" / "memory.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert memory["recent_turns"][0]["outcomes"] == []
    assert memory["recent_turns"][0]["money_delta_cp"] == 0


def test_load_v9_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V9)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V9)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v10_slot_is_too_new_for_engine_v9(saves):
    install(saves, FIXTURE_V9)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "auto", current_version=9)


@pytest.mark.parametrize(
    "name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat", "v6", "v7", "v8", "v9"],
)
def test_old_fixture_chain_reaches_current(saves, name):
    install(saves, FIXTURES / name)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
