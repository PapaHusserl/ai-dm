# Ожидаемый API: ai_dm.persistence.migrations.m0005_v4_to_v5 (этап 4, P1, STAGE4-PLAN A3)
#   migrate_v4_to_v5(data: dict) -> dict  -- чистое dict -> dict, вход не мутирует; schema_version
#       ставит фреймворк migrate(); MIGRATIONS[4] is migrate_v4_to_v5; CURRENT_SCHEMA_VERSION == 5.
#       Миграция заморожена в v5: не импортирует модели ai_dm.state.* (литералы заморожены).
#   Правила (setdefault: заданное не трогается): memory.scenes[*].source = "pack";
#       memory.chapters[*].source = "pack", at_s = 0; memory.game_summary_chapter = максимальный
#       number в chapters, если game_summary непуст, иначе 0; memory.recent_turns[*].scene_id = "".
#   Фикстуры: tests/fixtures/saves/v4 -- слот auto мира old_world (Вейл, память пуста);
#       tests/fixtures/saves/v4_dragon -- слот auto мира dd (пак «Пьяный Дракон»: game_summary,
#       главы 1 и 2, 36 выжимок сцен из start/memory.yaml) -- оба в формате v4.
import ast
import copy
import json
import shutil
from pathlib import Path

from persist_kit import load_slot

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION, MIGRATIONS, migrate
from ai_dm.persistence.migrations.m0005_v4_to_v5 import migrate_v4_to_v5

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V4 = FIXTURES / "v4"
FIXTURE_V4_DRAGON = FIXTURES / "v4_dragon"
FIXTURE_V3 = FIXTURES / "v3"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0005_v4_to_v5.py"
)


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, world_id="old_world", slot="auto"):
    target = saves / world_id / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def raw_v4(scenes=(), chapters=(), game_summary="", turns=()):
    return {
        "manifest": {"schema_version": 4, "world_id": "old_world"},
        "world": {"world_id": "old_world"},
        "heroes": [],
        "session": {"turn_seq": 2},
        "memory": {
            "scenes": list(scenes), "chapters": list(chapters), "game_summary": game_summary,
            "recent_turns": list(turns),
        },
    }


def raw_scene(scene_id="sc_1", **extra):
    data = {"id": scene_id, "chapter_id": "ch_1", "title": "", "summary": "Было.", "at_s": 0}
    return {**data, **extra}


def raw_chapter(number, **extra):
    return {"id": f"ch_{number}", "number": number, "title": "", "summary": "Глава.", **extra}


def raw_turn(seq=1, **extra):
    return {"turn_seq": seq, "at_s": 0, "player_input": "a", "narration": "b", **extra}


# реестр

def test_registry_has_step_from_v4():
    assert MIGRATIONS[4] is migrate_v4_to_v5
    assert CURRENT_SCHEMA_VERSION >= 5


def test_framework_sets_schema_version_five():
    assert migrate(raw_v4(), current_version=5)["manifest"]["schema_version"] == 5


def test_already_v5_dict_is_not_migrated_again():
    data = raw_v4()
    data["manifest"]["schema_version"] = 5
    assert migrate(data, current_version=5) == data


def test_migrate_v4_to_v5_does_not_mutate_input():
    data = raw_v4([raw_scene()], [raw_chapter(1)], "Игра.", [raw_turn()])
    before = copy.deepcopy(data)
    migrate_v4_to_v5(data)
    assert data == before


def test_migration_does_not_import_state_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert [n for n in names if n.startswith("ai_dm.state") or n == "ai_dm"] == []


# правила

def test_scenes_get_source_pack():
    scenes = migrate_v4_to_v5(raw_v4([raw_scene("a"), raw_scene("b")]))["memory"]["scenes"]
    assert [s["source"] for s in scenes] == ["pack", "pack"]


def test_chapters_get_source_pack_and_at_s_zero():
    chapters = migrate_v4_to_v5(raw_v4(chapters=[raw_chapter(1), raw_chapter(2)]))["memory"][
        "chapters"
    ]
    assert [c["source"] for c in chapters] == ["pack", "pack"]
    assert [c["at_s"] for c in chapters] == [0, 0]


def test_turns_get_empty_scene_id():
    turns = migrate_v4_to_v5(raw_v4(turns=[raw_turn(1), raw_turn(2)]))["memory"]["recent_turns"]
    assert [t["scene_id"] for t in turns] == ["", ""]


def test_game_summary_chapter_is_max_chapter_number_when_summary_exists():
    data = raw_v4(chapters=[raw_chapter(1), raw_chapter(2)], game_summary="Игра до главы 2.")
    assert migrate_v4_to_v5(data)["memory"]["game_summary_chapter"] == 2


def test_game_summary_chapter_uses_max_not_last_in_list():
    data = raw_v4(chapters=[raw_chapter(3), raw_chapter(1)], game_summary="Игра.")
    assert migrate_v4_to_v5(data)["memory"]["game_summary_chapter"] == 3


def test_game_summary_chapter_is_zero_without_game_summary():
    data = raw_v4(chapters=[raw_chapter(1), raw_chapter(2)], game_summary="")
    assert migrate_v4_to_v5(data)["memory"]["game_summary_chapter"] == 0


def test_game_summary_chapter_is_zero_without_chapters():
    assert migrate_v4_to_v5(raw_v4(game_summary="Игра."))["memory"]["game_summary_chapter"] == 0


def test_existing_values_are_not_overwritten():
    data = raw_v4(
        [raw_scene(source="narrator")], [raw_chapter(1, source="concat", at_s=500)],
        turns=[raw_turn(scene_id="scene_4")],
    )
    data["memory"]["game_summary_chapter"] = 7
    memory = migrate_v4_to_v5(data)["memory"]
    assert memory["scenes"][0]["source"] == "narrator"
    assert memory["chapters"][0]["source"] == "concat"
    assert memory["chapters"][0]["at_s"] == 500
    assert memory["recent_turns"][0]["scene_id"] == "scene_4"
    assert memory["game_summary_chapter"] == 7


def test_other_fields_stay():
    data = raw_v4([raw_scene()], [raw_chapter(1)], "Игра.", [raw_turn()])
    result = migrate_v4_to_v5(data)
    assert result["memory"]["scenes"][0]["summary"] == "Было."
    assert result["memory"]["game_summary"] == "Игра."
    assert result["memory"]["recent_turns"][0]["narration"] == "b"
    assert result["session"] == {"turn_seq": 2}
    assert result["world"] == {"world_id": "old_world"}


def test_empty_memory_is_fine():
    memory = migrate_v4_to_v5(raw_v4())["memory"]
    assert memory["scenes"] == []
    assert memory["game_summary_chapter"] == 0


# фикстуры на диске

def test_fixture_v4_is_stage4_format():
    manifest = json.loads((FIXTURE_V4 / "manifest.json").read_text(encoding="utf-8"))
    memory = json.loads((FIXTURE_V4 / "world" / "memory.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 4
    assert "game_summary_chapter" not in memory
    assert all("scene_id" not in t for t in memory["recent_turns"])


def test_fixture_v4_dragon_is_stage4_format():
    manifest = json.loads((FIXTURE_V4_DRAGON / "manifest.json").read_text(encoding="utf-8"))
    memory = json.loads((FIXTURE_V4_DRAGON / "world" / "memory.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 4
    assert [c["number"] for c in memory["chapters"]] == [1, 2]
    assert memory["game_summary"]
    assert all("source" not in s for s in memory["scenes"])


def test_load_v4_vale_returns_current_bundle(saves):
    install(saves, FIXTURE_V4)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.memory.game_summary_chapter == 0
    assert all(t.scene_id == "" for t in bundle.memory.recent_turns)
    assert bundle.heroes[0].name == "Арн"


def test_load_v4_dragon_marks_pack_memory_and_game_summary_chapter(saves):
    install(saves, FIXTURE_V4_DRAGON, "dd")
    bundle = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)
    memory = bundle.memory
    assert memory.game_summary_chapter == 2
    assert len(memory.scenes) == 36
    assert {s.source for s in memory.scenes} == {"pack"}
    assert {c.source for c in memory.chapters} == {"pack"}


def test_load_v4_dragon_keeps_text_of_memory(saves):
    install(saves, FIXTURE_V4_DRAGON, "dd")
    raw = json.loads((FIXTURE_V4_DRAGON / "world" / "memory.json").read_text(encoding="utf-8"))
    bundle = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)
    assert bundle.memory.game_summary == raw["game_summary"]
    assert [s.summary for s in bundle.memory.scenes] == [s["summary"] for s in raw["scenes"]]


def test_load_v4_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V4)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v4-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V4)


def test_load_v4_dragon_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V4_DRAGON, "dd")
    load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)
    backup = saves / "dd" / "backups" / f"auto-v4-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V4_DRAGON)


def test_load_v4_rewrites_slot_as_current(saves):
    folder = install(saves, FIXTURE_V4)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    memory = json.loads((folder / "world" / "memory.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert memory["game_summary_chapter"] == 0


def test_load_v4_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V4)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_chain_from_v3_matches_load_from_v4(saves, tmp_path):
    install(saves, FIXTURE_V4)
    from_v4 = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    other = tmp_path / "other"
    install(other, FIXTURE_V3)
    from_v3 = load_slot(other, "old_world", "auto", backup_ts=BACKUP_TS)
    assert from_v3 == from_v4
