# scripts/migrate_dusk_vibe.py <каталог мира|слота> -- одноразовая правка сейва dusk_academy:
# в tone.notes и world_text дописывается вольный хиппово-мирный дух, Ноксу ревность со срывами
# (из migrate_dusk_ship) заменяется на спокойную, у приятелей Нокса смягчаются заметки.
# stdlib, бэкап до записи, идемпотентность, отказ без записи на чужом мире / не той версии.
# Тесты на синтетическом слоте во tmp_path; запуск отдельным процессом. Последние -- на паке.
import json
import subprocess
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).parents[3]
SCRIPT = ROOT / "scripts" / "migrate_dusk_vibe.py"
WORLD_ID = "dusk_academy-d3de6c57"
OLD_TONE = "Пиши о напряжении между людьми."
WORLD_TEXT = "Остров. Тон игры — добрая романтическая история о дружбе, доверии и первой любви."
OLD_KNOX = "Нокс любит героиню."
JEALOUSY_OLD = (
    "Ревность к старым приятелям: когда друзья с «Бродячей Луны» подкатывают к героине, "
    "Нокс ревнует. Иногда держит лицо и отшучивается, иногда срывается — резкое слово, "
    "вызов на спор, уводит героиню прочь. Друзей любит: ссорится с ними, но не до разрыва, "
    "быстро остывает и мирится."
)
HENRY_OLD = (
    "Любит Миру, старается угодить ей во всём. Нокса считает другом, "
    "но его ревность задевает Генри, и он не уступает."
)
ORLANDO_OLD = "Помогает. Нокса немного побаивается."


def make_slot(root, *, version=9, world_id=WORLD_ID, knox=True, crew=True, tone_notes=OLD_TONE):
    slot = root / "saves" / world_id / "slots" / "auto"
    (slot / "world").mkdir(parents=True)
    manifest = {"schema_version": version, "world_id": world_id, "slot": "auto"}
    world = {
        "world_id": world_id,
        "tone": {"mood": "драма", "notes": tone_notes},
        "lore": {"world_text": WORLD_TEXT, "truths": []},
        "npcs": {"maya": {"name": "Майя", "notes": "староста"}},
    }
    if knox:
        world["npcs"]["knox"] = {"name": "Нокс Велар", "notes": f"{OLD_KNOX}\n\n{JEALOUSY_OLD}"}
    if crew:
        world["npcs"]["henry"] = {
            "name": "Генри", "notes": HENRY_OLD, "motive": "быть рядом и угождать ей во всём.",
        }
        world["npcs"]["orlando"] = {"name": "Орландо", "notes": ORLANDO_OLD}
    (slot / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    (slot / "world" / "world.json").write_text(
        json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    return slot


def run(path, script=SCRIPT):
    return subprocess.run(
        [sys.executable, "-I", str(script), str(path)], capture_output=True, text=True,
        encoding="utf-8", check=False,
    )


def world_of(slot):
    return json.loads((slot / "world" / "world.json").read_text(encoding="utf-8"))


def snapshot(root):
    return {p: p.read_bytes() for p in sorted(root.rglob("*")) if p.is_file()}


def test_apply_prints_done_with_backup_path(tmp_path):
    result = run(make_slot(tmp_path))
    assert result.returncode == 0
    assert result.stdout.startswith("Готово. Бэкап слота: ")


def test_apply_appends_tone_lines_and_keeps_old(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["tone"]["notes"]
    assert notes.startswith(OLD_TONE)
    assert "хиппово-беззаботный" in notes
    assert "Флирт взаимный" in notes
    assert "Многолюбие" in notes
    assert "Ревность — обычное чувство" in notes


def test_apply_extends_world_text(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    text = world_of(slot)["lore"]["world_text"]
    assert text.startswith("Остров. Тон игры")
    assert "почти хиппи" in text


def test_knox_jealousy_becomes_calm_and_old_notes_kept(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["knox"]["notes"]
    assert notes.startswith(OLD_KNOX)
    assert "срывается" not in notes
    assert "говорит о ней спокойно" in notes


def test_knox_without_jealousy_gets_calm_line(tmp_path):
    slot = make_slot(tmp_path)
    world = world_of(slot)
    world["npcs"]["knox"]["notes"] = OLD_KNOX
    path = slot / "world" / "world.json"
    path.write_text(json.dumps(world, ensure_ascii=False), encoding="utf-8")
    run(slot)
    assert world_of(slot)["npcs"]["knox"]["notes"].startswith(f"{OLD_KNOX}\n\n")


def test_crew_notes_and_motive_are_softened(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    npcs = world_of(slot)["npcs"]
    assert "угодить" not in npcs["henry"]["notes"]
    assert "не уступает" not in npcs["henry"]["notes"]
    assert "угождать" not in npcs["henry"]["motive"]
    assert "побаивается" not in npcs["orlando"]["notes"]


def test_other_npcs_untouched(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["npcs"]["maya"] == {"name": "Майя", "notes": "староста"}


def test_apply_without_knox_and_crew_still_works(tmp_path):
    slot = make_slot(tmp_path, knox=False, crew=False)
    assert run(slot).returncode == 0
    assert "хиппово-беззаботный" in world_of(slot)["tone"]["notes"]


def test_empty_tone_notes_are_filled(tmp_path):
    slot = make_slot(tmp_path, tone_notes="")
    run(slot)
    assert world_of(slot)["tone"]["notes"].startswith("- Дух мира вольный")


def test_backup_holds_original_world(tmp_path):
    slot = make_slot(tmp_path)
    before = (slot / "world" / "world.json").read_bytes()
    run(slot)
    backups = list((tmp_path / "saves" / WORLD_ID).glob("backup-vibe-*/auto/world/world.json"))
    assert len(backups) == 1
    assert backups[0].read_bytes() == before


def test_world_dir_argument_edits_auto_slot(tmp_path):
    slot = make_slot(tmp_path)
    assert run(tmp_path / "saves" / WORLD_ID).returncode == 0
    assert "хиппово-беззаботный" in world_of(slot)["tone"]["notes"]


def test_no_argument_exits_two():
    result = subprocess.run(
        [sys.executable, "-I", str(SCRIPT)], capture_output=True, text=True, encoding="utf-8",
        check=False,
    )
    assert result.returncode == 2


@pytest.mark.parametrize("kwargs", [{"world_id": "other_world-1"}, {"version": 8}, {"version": 15}])
def test_refusal_writes_nothing(tmp_path, kwargs):
    slot = make_slot(tmp_path, **kwargs)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 1
    assert "Отказ" in result.stdout
    assert snapshot(tmp_path) == before


def test_missing_manifest_is_refused(tmp_path):
    (tmp_path / "empty").mkdir()
    assert run(tmp_path / "empty").returncode == 1


def test_second_run_is_noop(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    before = snapshot(tmp_path)
    result = run(slot)
    assert result.returncode == 0
    assert "Уже применено" in result.stdout
    assert snapshot(tmp_path) == before


def test_apply_appends_mood_once(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    assert world_of(slot)["tone"]["mood"] == "драма; вольный хиппово-мирный дух"


def test_kurt_conflict_removed(tmp_path):
    slot = make_slot(tmp_path)
    world = world_of(slot)
    world["npcs"]["kurt"] = {"name": "Курт", "notes": "Нокса уважает и не хочет с ним ссориться."}
    (slot / "world" / "world.json").write_text(json.dumps(world, ensure_ascii=False), "utf-8")
    run(slot)
    assert world_of(slot)["npcs"]["kurt"]["notes"] == "Нокса уважает."


def test_rerun_repairs_old_texts_even_if_marker_present(tmp_path):
    slot = make_slot(tmp_path)
    run(slot)
    world = world_of(slot)
    world["npcs"]["knox"]["notes"] += f"\n\n{JEALOUSY_OLD}"
    world["npcs"]["orlando"]["notes"] = ORLANDO_OLD
    (slot / "world" / "world.json").write_text(json.dumps(world, ensure_ascii=False), "utf-8")
    result = run(slot)
    assert result.stdout.startswith("Готово. Бэкап слота: ")
    npcs = world_of(slot)["npcs"]
    assert "срывается" not in npcs["knox"]["notes"]
    assert "побаивается" not in npcs["orlando"]["notes"]
    assert "хиппово-беззаботный" in world_of(slot)["tone"]["notes"]
    assert world_of(slot)["tone"]["notes"].count("хиппово-беззаботный") == 1


def test_ship_then_vibe_leaves_no_old_jealousy(tmp_path):
    # цепочка: после ship в сейве старая ревность, vibe её заменяет, а не дублирует
    slot = make_slot(tmp_path)
    run(slot)
    notes = world_of(slot)["npcs"]["knox"]["notes"]
    assert notes.count("говорит о ней спокойно") == 1
    assert "Ревность к старым приятелям" not in notes


# пак

def pack_text(name):
    return (ROOT / "campaigns" / "dusk_academy" / name).read_text(encoding="utf-8")


def test_pack_tone_has_vibe():
    campaign = yaml.safe_load(pack_text("campaign.yaml"))
    assert "хиппово" in campaign["tone"]["mood"]
    assert "Флирт взаимный" in campaign["tone"]["notes"]


def test_pack_has_no_aggressive_jealousy():
    text = pack_text("npcs.yaml") + pack_text("factions.yaml")
    for phrase in ("срывается", "угодить ей во всём", "побаивается", "не уступает",
                   "не хочет с ним ссориться"):
        assert phrase not in text


def test_pack_knox_jealousy_is_calm():
    npcs = yaml.safe_load(pack_text("npcs.yaml"))
    knox = next(n for n in npcs if n["id"] == "knox")
    assert "спокойно" in knox["notes"]
