# scripts/migrate_dusk_calm.py <каталог мира|слота> -- одноразовая правка сейва dusk_academy:
# флаг pact:together=False (migrate_dusk_pact ставил True безусловно), триггеру blight_sign
# фракции pact_keepers -- cooldown "7d" всегда. stdlib, бэкап до записи, идемпотентность,
# отказ без записи на чужом мире / не той версии / без фракции. Синтетический слот во tmp_path;
# запуск отдельным процессом.
import json
import subprocess
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[3] / "scripts" / "migrate_dusk_calm.py"
WORLD_ID = "dusk_academy-d3de6c57"


def make_slot(
    root, *, version=14, world_id=WORLD_ID, faction=True, blight=True, together=True,
    cooldown=None,
):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {"schema_version": version, "world_id": world_id, "slot": "auto"}
    triggers = [
        {"id": "fortune_visit", "state": "fired", "cooldown": None},
        {
            "id": "calm_sign", "state": "active", "cooldown": "30d",
            "if_": {"type": "flag", "name": "pact:together", "value": False},
        },
    ]
    if blight:
        triggers.insert(1, {
            "id": "blight_sign", "state": "active", "cooldown": cooldown,
            "if_": {"type": "flag", "name": "pact:together", "value": True},
        })
    flags = {"met_maya": True, "pact:known": True}
    if together is not None:
        flags["pact:together"] = together
    world = {
        "world_id": world_id, "clock": {"now_s": 100}, "flags": flags,
        "factions": {"pact_keepers": {"id": "pact_keepers", "opportunity": triggers}}
        if faction else {},
        "npcs": {"lucian": {"notes": "Заметки."}},
    }
    (slot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    (slot / "session.json").write_text('{"turn_seq": 7}', encoding="utf-8")
    return slot


def run(path):
    return subprocess.run(
        [sys.executable, "-I", str(SCRIPT), str(path)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_of(slot):
    return json.loads((slot / "world" / "world.json").read_text(encoding="utf-8"))


def trigger_of(slot, trigger_id):
    triggers = world_of(slot)["factions"]["pact_keepers"]["opportunity"]
    return next(t for t in triggers if t["id"] == trigger_id)


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def backups(root, slot):
    original = slot / "world" / "world.json"
    return [p for p in root.rglob("world.json") if p != original]


# применение

def test_script_exists():
    assert SCRIPT.is_file()


def test_apply_prints_done_with_backup_path(tmp_path):
    result = run(make_slot(tmp_path))
    assert result.returncode == 0
    assert result.stdout.startswith("Готово. Бэкап слота: ")


def test_apply_sets_together_false(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["flags"]["pact:together"] is False


def test_apply_sets_together_false_when_flag_absent(tmp_path):
    slot = make_slot(tmp_path, together=None)
    run(slot)
    assert world_of(slot)["flags"]["pact:together"] is False


def test_apply_sets_blight_cooldown_when_null(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert trigger_of(slot, "blight_sign")["cooldown"] == "7d"


@pytest.mark.parametrize("old", ["1d", "2d"])
def test_apply_overrides_existing_blight_cooldown(tmp_path, old):
    slot = make_slot(tmp_path, cooldown=old)
    run(slot)
    assert trigger_of(slot, "blight_sign")["cooldown"] == "7d"
    assert world_of(slot)["flags"]["pact:together"] is False


def test_apply_keeps_the_rest_of_world_json(tmp_path):
    slot = make_slot(tmp_path)
    before = world_of(slot)
    run(slot)
    after = world_of(slot)
    for doc in (before, after):
        doc["flags"].pop("pact:together")
        next(
            t for t in doc["factions"]["pact_keepers"]["opportunity"] if t["id"] == "blight_sign"
        ).pop("cooldown")
    assert after == before
    assert after["flags"]["pact:known"] is True


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
    assert found[0].parents[2].name.startswith("backup-calm-")


def test_apply_leaves_no_tmp_file(tmp_path):
    run(make_slot(tmp_path))
    assert not list(tmp_path.rglob("*.tmp"))


def test_world_dir_argument_edits_auto_slot(tmp_path):
    slot = make_slot(tmp_path)
    assert run(tmp_path / "saves" / WORLD_ID).returncode == 0
    assert world_of(slot)["flags"]["pact:together"] is False


def test_no_argument_exits_two():
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2


# отказ без записи

def refused(tmp_path, **kwargs):
    slot = make_slot(tmp_path, **kwargs)
    before = snapshot(tmp_path)
    result = run(slot)
    assert snapshot(tmp_path) == before
    assert result.returncode == 1
    assert "Отказ" in result.stdout


def test_other_world_is_refused(tmp_path):
    refused(tmp_path, world_id="other_world-1")


def test_version_8_is_refused(tmp_path):
    refused(tmp_path, version=8)


def test_version_15_is_refused(tmp_path):
    refused(tmp_path, version=15)


def test_missing_faction_is_refused(tmp_path):
    refused(tmp_path, faction=False)


def test_missing_blight_trigger_is_refused(tmp_path):
    refused(tmp_path, blight=False)


def test_missing_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    result = run(tmp_path / "empty")
    assert result.returncode == 1
    assert "Отказ" in result.stdout


# идемпотентность

def test_flag_already_false_with_old_cooldown_is_not_already_applied(tmp_path):
    slot = make_slot(tmp_path, together=False, cooldown="1d")
    result = run(slot)
    assert result.stdout.startswith("Готово.")
    assert trigger_of(slot, "blight_sign")["cooldown"] == "7d"
    assert world_of(slot)["flags"]["pact:together"] is False
    assert len(backups(tmp_path, slot)) == 1


def test_second_run_says_already_applied_and_changes_nothing(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено: изменений нет." in result.stdout
    assert snapshot(tmp_path) == before
    assert len(backups(tmp_path, slot)) == 1
