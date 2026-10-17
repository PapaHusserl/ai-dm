# Ж0 п. 11 (docs/plan-zh0.md): миграция v10 -> v11 -- память и цели NPC, known_name, связи, услуги,
# журнал знаний и связи героя, scene_mood, WorldSim.pending_acts; NPC.relations_text удалён.
# API: ai_dm.persistence.migrations.m0011_v10_to_v11.migrate_v10_to_v11(data, context=None) -> dict
#   -- чистое dict -> dict, вход не мутирует; MIGRATIONS[10] is migrate_v10_to_v11;
#   CURRENT_SCHEMA_VERSION >= 11.
#   Правило: setdefault (заданные значения не перезаписываются); relations_text удаляется.
#   Миграция заморожена: не импортирует ai_dm.state.* и content.
#   Фикстура: tests/fixtures/saves/v10 -- слот auto мира zh0_world.
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
from ai_dm.persistence.migrations.m0011_v10_to_v11 import migrate_v10_to_v11
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V10 = FIXTURES / "v10"
WORLD_ID = "zh0_world"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0011_v10_to_v11.py"
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


def raw_v10(npcs=None, heroes=None, scene=..., sim=...):
    return {
        "manifest": {"schema_version": 10, "world_id": "w"},
        "world": {
            "world_id": "w",
            "npcs": npcs if npcs is not None else {
                "a": {"id": "a", "relations_text": "Брат Б.", "attitude": 3},
                "b": {"id": "b", "relations_text": "", "attitude": -1},
            },
            "sim": {"last_day": 2} if sim is ... else sim,
        },
        "heroes": heroes if heroes is not None else [{"id": "h1", "name": "Арн"}],
        "session": {
            "turn_seq": 2,
            "current_scene": {"id": "s1", "player_turns": 1} if scene is ... else scene,
        },
    }


# реестр и фреймворк

def test_registry_has_step_from_v10():
    assert MIGRATIONS[10] is migrate_v10_to_v11
    assert CURRENT_SCHEMA_VERSION >= 11


def test_framework_sets_schema_version_eleven():
    assert migrate(raw_v10(), current_version=11)["manifest"]["schema_version"] == 11


def test_v10_to_v10_is_not_touched():
    assert migrate(raw_v10(), current_version=10) == raw_v10()


def test_already_v11_dict_is_not_migrated_again():
    data = raw_v10()
    data["manifest"]["schema_version"] = 11
    assert migrate(data, current_version=11) == data


def test_engine_v10_refuses_a_v11_dict():
    data = raw_v10()
    data["manifest"]["schema_version"] = 11
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=10)


def test_migration_does_not_mutate_input():
    data = raw_v10()
    before = copy.deepcopy(data)
    migrate_v10_to_v11(data)
    assert data == before


def test_migration_works_without_context_argument():
    assert migrate_v10_to_v11(raw_v10(), None) == migrate_v10_to_v11(raw_v10())


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


def test_whole_dict_migration_is_idempotent():
    once = migrate_v10_to_v11(raw_v10())
    assert migrate_v10_to_v11(once) == once


def test_result_is_a_deep_copy():
    data = raw_v10()
    result = migrate_v10_to_v11(data)
    result["world"]["npcs"]["a"]["attitude"] = 99
    assert data["world"]["npcs"]["a"]["attitude"] == 3


# NPC

def test_npcs_get_empty_memory_and_goals():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    assert [npcs[k]["memory"] for k in "ab"] == [[], []]
    assert [npcs[k]["goals"] for k in "ab"] == [[], []]


def test_npcs_get_no_known_name():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    assert [npcs[k]["known_name"] for k in "ab"] == [None, None]


def test_npcs_get_empty_family_and_services():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    assert [npcs[k]["family"] for k in "ab"] == [[], []]
    assert [npcs[k]["services"] for k in "ab"] == [[], []]


def test_npc_lists_are_not_shared_between_npcs():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    for field in ("memory", "goals", "family", "services"):
        npcs["a"][field].append("x")
        assert npcs["b"][field] == []


def test_relations_text_is_removed():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    assert "relations_text" not in npcs["a"]
    assert "relations_text" not in npcs["b"]


def test_relations_text_moves_to_notes_verbatim():
    npcs = migrate_v10_to_v11(raw_v10())["world"]["npcs"]
    assert npcs["a"]["notes"] == "Брат Б."


def test_empty_relations_text_gives_empty_notes():
    assert migrate_v10_to_v11(raw_v10())["world"]["npcs"]["b"]["notes"] == ""


def test_missing_relations_text_gives_empty_notes():
    npcs = migrate_v10_to_v11(raw_v10(npcs={"a": {"id": "a"}}))["world"]["npcs"]
    assert npcs["a"]["notes"] == ""


def test_non_empty_notes_are_not_overwritten_by_relations_text():
    npc = {"id": "a", "notes": "своё", "relations_text": "старое"}
    result = migrate_v10_to_v11(raw_v10(npcs={"a": npc}))["world"]["npcs"]["a"]
    assert result["notes"] == "своё"
    assert "relations_text" not in result


def test_empty_notes_are_replaced_by_relations_text():
    npc = {"id": "a", "notes": "", "relations_text": "старое"}
    assert migrate_v10_to_v11(raw_v10(npcs={"a": npc}))["world"]["npcs"]["a"]["notes"] == "старое"


def test_npc_without_relations_text_is_fine():
    npcs = migrate_v10_to_v11(raw_v10(npcs={"a": {"id": "a"}}))["world"]["npcs"]
    assert npcs["a"]["memory"] == []


def test_existing_npc_values_are_kept():
    memory = [{"scene_id": "s", "at_s": 1, "weight": 2, "events": []}]
    family = [{"kind": "parent", "ref": "x", "ref_kind": "npc"}]
    npc = {
        "id": "a", "memory": memory, "goals": [{"kind": "debt"}], "known_name": "Гарт",
        "family": family, "services": ["rest"],
    }
    result = migrate_v10_to_v11(raw_v10(npcs={"a": npc}))["world"]["npcs"]["a"]
    assert result["memory"] == memory
    assert result["goals"] == [{"kind": "debt"}]
    assert result["known_name"] == "Гарт"
    assert result["family"] == family
    assert result["services"] == ["rest"]


def test_other_npc_fields_stay():
    npc = migrate_v10_to_v11(raw_v10())["world"]["npcs"]["a"]
    assert (npc["id"], npc["attitude"]) == ("a", 3)


def test_no_npcs_is_fine():
    assert migrate_v10_to_v11(raw_v10(npcs={}))["world"]["npcs"] == {}


# мир, герои, сцена

def test_sim_gets_empty_pending_acts():
    assert migrate_v10_to_v11(raw_v10())["world"]["sim"]["pending_acts"] == []


def test_existing_pending_acts_are_kept():
    data = raw_v10(sim={"pending_acts": ["x"]})
    assert migrate_v10_to_v11(data)["world"]["sim"]["pending_acts"] == ["x"]


def test_other_sim_fields_stay():
    assert migrate_v10_to_v11(raw_v10())["world"]["sim"]["last_day"] == 2


def test_heroes_get_empty_family_and_knowledge():
    heroes = migrate_v10_to_v11(raw_v10(heroes=[{"id": "h1"}, {"id": "h2"}]))["heroes"]
    assert [h["family"] for h in heroes] == [[], []]
    assert [h["knowledge"] for h in heroes] == [[], []]


def test_hero_lists_are_not_shared():
    heroes = migrate_v10_to_v11(raw_v10(heroes=[{"id": "h1"}, {"id": "h2"}]))["heroes"]
    heroes[0]["family"].append("x")
    heroes[0]["knowledge"].append("x")
    assert heroes[1]["family"] == []
    assert heroes[1]["knowledge"] == []


def test_existing_hero_family_and_knowledge_are_kept():
    hero = {"id": "h1", "family": [{"kind": "spouse"}], "knowledge": [{"kind": "fact"}]}
    result = migrate_v10_to_v11(raw_v10(heroes=[hero]))["heroes"][0]
    assert result["family"] == [{"kind": "spouse"}]
    assert result["knowledge"] == [{"kind": "fact"}]


def test_other_hero_fields_stay():
    assert migrate_v10_to_v11(raw_v10())["heroes"][0]["name"] == "Арн"


def test_no_heroes_is_fine():
    assert migrate_v10_to_v11(raw_v10(heroes=[]))["heroes"] == []


def test_current_scene_gets_empty_mood():
    scene = migrate_v10_to_v11(raw_v10())["session"]["current_scene"]
    assert scene["scene_mood"] == ""


def test_existing_scene_mood_is_kept():
    data = raw_v10(scene={"id": "s1", "scene_mood": "tense"})
    assert migrate_v10_to_v11(data)["session"]["current_scene"]["scene_mood"] == "tense"


def test_other_scene_fields_stay():
    scene = migrate_v10_to_v11(raw_v10())["session"]["current_scene"]
    assert (scene["id"], scene["player_turns"]) == ("s1", 1)


def test_null_current_scene_stays_null():
    assert migrate_v10_to_v11(raw_v10(scene=None))["session"]["current_scene"] is None


def test_dict_without_world_heroes_and_session_is_fine():
    data = {"manifest": {"schema_version": 10, "world_id": "w"}}
    assert migrate(data, current_version=11)["manifest"]["schema_version"] == 11


def test_world_without_sim_gets_no_sim():
    data = raw_v10()
    del data["world"]["sim"]
    assert "sim" not in migrate_v10_to_v11(data)["world"]


def test_session_without_scene_key_gets_no_scene():
    data = raw_v10()
    del data["session"]["current_scene"]
    assert "current_scene" not in migrate_v10_to_v11(data)["session"]


def test_manifest_is_untouched_by_the_step():
    assert migrate_v10_to_v11(raw_v10())["manifest"] == {"schema_version": 10, "world_id": "w"}


# фикстура v10 и загрузка слота

def test_fixture_v10_is_v10_format():
    folder = FIXTURE_V10
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((folder / "world" / "world.json").read_text(encoding="utf-8"))
    hero = json.loads((folder / "heroes" / "01_арн" / "hero.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 10
    assert all("relations_text" in n and "memory" not in n for n in world["npcs"].values())
    assert "pending_acts" not in world["sim"]
    assert "family" not in hero


def test_load_v10_returns_current_bundle(saves):
    install(saves, FIXTURE_V10)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v10_npcs_get_defaults(saves):
    install(saves, FIXTURE_V10)
    npcs = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).world.npcs
    assert set(npcs) == {"innkeeper", "mira", "old_tam", "grakh"}
    for npc in npcs.values():
        assert (npc.memory, npc.goals, npc.family, npc.services) == ([], [], [], [])
        assert npc.known_name is None


def test_load_v10_moves_relations_text_to_notes(saves):
    install(saves, FIXTURE_V10)
    npcs = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).world.npcs
    assert npcs["innkeeper"].notes == "Брат Мирры; старый друг Тама."
    assert npcs["mira"].notes == "Сестра Гарта; недолюбливает чужаков с оружием."
    assert npcs["old_tam"].notes == "Друг Гарта."
    assert npcs["grakh"].notes == "Враг таверны."


def test_load_v10_keeps_npc_names_and_attitudes(saves):
    install(saves, FIXTURE_V10)
    npcs = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).world.npcs
    assert (npcs["innkeeper"].name, npcs["innkeeper"].attitude) == ("Гарт", 10)
    assert npcs["mira"].attitude == -5


def test_load_v10_world_sim_and_hero_get_defaults(saves):
    install(saves, FIXTURE_V10)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    assert bundle.world.sim.pending_acts == []
    assert bundle.heroes[0].family == []
    assert bundle.heroes[0].knowledge == []


def test_load_v10_scene_gets_empty_mood(saves):
    install(saves, FIXTURE_V10)
    scene = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS).session.current_scene
    assert scene.id == "scene_2"
    assert scene.scene_mood == ""


def test_load_v10_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V10)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    backup = saves / WORLD_ID / "backups" / f"auto-v10-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V10)


def test_load_v10_rewrites_slot_as_v11_without_relations_text(saves):
    folder = install(saves, FIXTURE_V10)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((folder / "world" / "world.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert all("relations_text" not in n for n in world["npcs"].values())
    assert world["npcs"]["innkeeper"]["memory"] == []


def test_load_v10_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V10)
    first = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, WORLD_ID, "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / WORLD_ID / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V10)
    bundle = load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v11_slot_is_too_new_for_engine_v10(saves):
    install(saves, FIXTURE_V10)
    load_slot(saves, WORLD_ID, "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, WORLD_ID, "auto", current_version=10)


@pytest.mark.parametrize(
    "name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat", "v6", "v7", "v8", "v9"],
)
def test_old_fixture_chain_reaches_current(saves, name):
    install(saves, FIXTURES / name, world_id="old_world")
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
