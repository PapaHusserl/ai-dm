# ТО (docs/plan-to.md Q4б): scripts/migrate_dusk_18plus.py <каталог слота> -- одноразовая правка
# world.lore.world_text и world.tone.notes сейва dusk_academy (текст 18+). stdlib, бэкап до записи,
# идемпотентность («уже применено»), отказ без записи на не-v10 сейве и чужом мире.
# Тесты на синтетической копии сейва во tmp_path; запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_18plus.py"
WORLD_ID = "dusk_academy-d3de6c57"  # id мира зашит в скрипте; каталог -- синтетический, во tmp_path
WORLD_TEXT = (
    "Академия Сумеречного Мыса — старая школа магии со шпилями, оранжереей и библиотекой, "
    "где свечи никогда не гаснут. Здесь вместе учатся дети людей, потомки оборотней и "
    "несколько юных представителей ночного народа."
)
NOTES = "Пиши о напряжении между людьми."


def make_slot(root, *, version=10, world_id=WORLD_ID, campaign="dusk_academy"):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {
        "schema_version": version, "engine_version": "0.1.0", "world_id": world_id,
        "campaign_id": campaign, "slot": "auto", "saved_at": "2026-10-15T15:38:18+00:00",
        "current_hero_id": "hero", "heroes": ["hero"],
    }
    world = {
        "world_id": world_id, "campaign_id": campaign, "flags": {"met_maya": True},
        "tone": {"mood": "драма", "romance": "чувственно", "notes": NOTES},
        "lore": {"world_text": WORLD_TEXT, "truths": ["правда 1", "правда 2"]},
        "npcs": {"maya": {"name": "Майя"}},
    }
    (slot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (slot / "session.json").write_text('{"turn_seq": 7}', encoding="utf-8")
    return slot


def run(slot):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(slot)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_of(slot):
    return json.loads((slot / "world" / "world.json").read_text(encoding="utf-8"))


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def backups(root, slot):
    original = slot / "world" / "world.json"
    return [p for p in root.rglob("world.json") if p != original]


# применение

def test_script_exists():
    assert SCRIPT.is_file()


def test_apply_exits_zero(tmp_path):
    assert run(make_slot(tmp_path)).returncode == 0


def test_apply_changes_world_text_and_notes_to_18plus(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    world = world_of(slot)
    assert world["lore"]["world_text"] != WORLD_TEXT
    assert "18+" in world["lore"]["world_text"]
    assert world["tone"]["notes"] != NOTES
    assert "18+" in world["tone"]["notes"]


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        del doc["lore"]["world_text"]
        del doc["tone"]["notes"]
    assert after == before


def test_apply_does_not_touch_manifest_and_session(tmp_path):
    slot = make_slot(tmp_path)
    manifest = (slot / "manifest.json").read_bytes()
    session = (slot / "session.json").read_bytes()
    run(slot)
    assert (slot / "manifest.json").read_bytes() == manifest
    assert (slot / "session.json").read_bytes() == session


def test_apply_creates_backup_with_original_world(tmp_path):
    slot = make_slot(tmp_path)
    original = (slot / "world" / "world.json").read_bytes()
    run(slot)
    found = backups(tmp_path, slot)
    assert len(found) == 1
    assert found[0].read_bytes() == original


def test_apply_does_not_create_files_outside_the_world_dir(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    world_dir = tmp_path / "saves" / WORLD_ID
    extra = [p for p in tmp_path.rglob("*") if p.is_file() and world_dir not in p.parents]
    assert extra == []


# идемпотентность

def test_second_run_says_already_applied_and_changes_nothing(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    state = snapshot(tmp_path)
    again = run(slot)
    assert again.returncode == 0
    assert "уже применено" in (again.stdout + again.stderr).lower()
    assert snapshot(tmp_path) == state


def test_second_run_makes_no_second_backup(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    run(slot)
    assert len(backups(tmp_path, slot)) == 1


# отказы без записи

def test_v9_save_is_accepted_and_patched(tmp_path):
    slot = make_slot(tmp_path, version=9)
    result = run(slot)
    assert result.returncode == 0
    assert "18+" in world_of(slot)["lore"]["world_text"]
    assert "18+" in world_of(slot)["tone"]["notes"]


def test_v9_save_gets_a_backup(tmp_path):
    slot = make_slot(tmp_path, version=9)
    run(slot)
    assert len(backups(tmp_path, slot)) == 1


def test_apply_replaces_human_children_with_young_people(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    text = world_of(slot)["lore"]["world_text"]
    assert "дети людей" not in text
    assert "молодые люди" in text


def test_v11_save_is_accepted_and_patched(tmp_path):
    slot = make_slot(tmp_path, version=11)
    result = run(slot)
    assert result.returncode == 0
    assert "18+" in world_of(slot)["lore"]["world_text"]
    assert "18+" in world_of(slot)["tone"]["notes"]


def test_v12_save_is_accepted_and_patched(tmp_path):
    slot = make_slot(tmp_path, version=12)
    result = run(slot)
    assert result.returncode == 0
    assert "18+" in world_of(slot)["lore"]["world_text"]
    assert "18+" in world_of(slot)["tone"]["notes"]


@pytest.mark.parametrize("version", [8, 14])
def test_refuses_unsupported_version_without_writing(tmp_path, version):
    slot = make_slot(tmp_path, version=version)
    state = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode != 0
    assert snapshot(tmp_path) == state


def test_refuses_foreign_world_without_writing(tmp_path):
    slot = make_slot(tmp_path, world_id="drunk_dragon-bbbbbbbb", campaign="drunk_dragon")
    state = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode != 0
    assert snapshot(tmp_path) == state


def test_refuses_missing_path(tmp_path):
    assert run(tmp_path / "nope").returncode != 0


def test_refusal_prints_a_reason(tmp_path):
    result = run(make_slot(tmp_path, version=8))
    assert (result.stdout + result.stderr).strip() != ""


# каталог мира вместо каталога слота

def test_world_dir_argument_patches_auto_slot(tmp_path):
    slot = make_slot(tmp_path)
    result = run(tmp_path / "saves" / WORLD_ID)
    assert result.returncode == 0
    assert "18+" in world_of(slot)["lore"]["world_text"]


# неожиданный текст -- отказ без записи

def test_refuses_when_world_text_has_no_expected_fragment(tmp_path):
    slot = make_slot(tmp_path)
    world = world_of(slot)
    world["lore"]["world_text"] = "Совсем другой текст."
    (slot / "world" / "world.json").write_text(json.dumps(world, ensure_ascii=False), "utf-8")
    state = snapshot(tmp_path)
    assert run(slot).returncode != 0
    assert snapshot(tmp_path) == state
