# Ожидаемый API: ai_dm.persistence.layout и ai_dm.persistence.store.save_slot (шаг 22, A3)
#   layout.slugify(name: str) -> str
#       нижний регистр, кириллица сохраняется, любая серия не-букв/не-цифр -> один "-",
#       "-" по краям обрезаются; пустой результат -> "hero".
#       "Арн" -> "арн"; "Бранка Рыжая" -> "бранка-рыжая"; "Арн!!  Ловкий" -> "арн-ловкий"
#   layout.hero_dir_name(hero: HeroState) -> str      f"{ordinal:02d}_{slugify(name)}"
#   layout.slot_dir(root: Path, world_id: str, slot: str) -> Path   root/<world_id>/slots/<slot>
#       вызывает check_world_id и check_slot_name: плохие -> ValueError (значит, и все входы
#       store / backup)
#   layout.check_world_id(world_id: str) -> None   (B1)
#       непустой, только символы [\w-] (юникодные буквы, цифры, "_", "-"), не начинается с ".",
#       без "/", "\\", ".."; иначе ValueError. Абсолютный путь невозможен ("/" запрещён).
#   layout.check_slot_name(slot: str) -> None   (D12)
#       "auto", "auto-<число>" или "manual-<имя>"; имя непустое, строчное (заглавные, в т.ч.
#       кириллические -> ValueError), без "/", "\\", "..", не с ".".
#   store.save_slot(root, bundle, slot, *, saved_at) -> Path     (подробно -- test_store.py)
#   Раскладка слота ровно такая (и никаких других файлов):
#       manifest.json
#       session.json
#       world/world.json
#       world/chronicle.json
#       world/memory.json
#       heroes/01_<slug>/hero.json, heroes/02_<slug>/hero.json, ...
#   Файлы -- UTF-8, model_dump_json(indent=2) (кириллица не экранируется).
#   manifest.json: схема версии, slot и saved_at из параметров, heroes -- id героев по порядку.
#   manifest.json пишется ПОСЛЕДНИМ (его mtime не меньше mtime любого другого файла слота).
import json
import os
from pathlib import Path

import pytest

from ai_dm.persistence.layout import (
    check_slot_name,
    check_world_id,
    hero_dir_name,
    slot_dir,
    slugify,
)
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import save_slot

SAVED_AT = "2026-02-02T08:00:00Z"


def files_in(folder):
    return sorted(
        p.relative_to(folder).as_posix() for p in folder.rglob("*") if p.is_file()
    )


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_slugify_keeps_cyrillic_lowercase():
    assert slugify("Арн") == "арн"


def test_slugify_replaces_space_with_dash():
    assert slugify("Бранка Рыжая") == "бранка-рыжая"


def test_slugify_collapses_punctuation_and_spaces():
    assert slugify("Арн!!  Ловкий") == "арн-ловкий"


def test_slugify_trims_dashes_at_edges():
    assert slugify("  Арн?? ") == "арн"


def test_slugify_latin_name():
    assert slugify("Sir Bob") == "sir-bob"


def test_slugify_empty_result_falls_back_to_hero():
    assert slugify("!!!") == "hero"


def test_hero_dir_name_has_two_digit_ordinal_and_slug(bundle):
    assert hero_dir_name(bundle.heroes[0]) == "01_арн"
    assert hero_dir_name(bundle.heroes[1]) == "02_бранка-рыжая"


def test_slot_dir_path(saves):
    assert slot_dir(saves, "w1", "auto") == saves / "w1" / "slots" / "auto"


def test_save_creates_exact_file_layout(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert files_in(slot_dir(saves, "w1", "auto")) == [
        "heroes/01_арн/hero.json",
        "heroes/02_бранка-рыжая/hero.json",
        "manifest.json",
        "session.json",
        "world/chronicle.json",
        "world/memory.json",
        "world/world.json",
    ]


def test_save_returns_slot_dir(saves, bundle):
    result = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert Path(result) == slot_dir(saves, "w1", "auto")


def test_world_json_matches_world_model(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    data = read_json(slot_dir(saves, "w1", "auto") / "world" / "world.json")
    assert data == bundle.world.model_dump(mode="json")


def test_world_json_is_indented_and_keeps_cyrillic_unescaped(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    text = (slot_dir(saves, "w1", "auto") / "world" / "world.json").read_text(encoding="utf-8")
    assert text.strip() == bundle.world.model_dump_json(indent=2)
    assert "Олдрик" in text


def test_hero_json_matches_hero_model(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    folder = slot_dir(saves, "w1", "auto")
    first = read_json(folder / "heroes" / "01_арн" / "hero.json")
    second = read_json(folder / "heroes" / "02_бранка-рыжая" / "hero.json")
    assert first == bundle.heroes[0].model_dump(mode="json")
    assert second == bundle.heroes[1].model_dump(mode="json")


def test_chronicle_memory_and_session_json_match_models(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    folder = slot_dir(saves, "w1", "auto")
    chronicle = read_json(folder / "world" / "chronicle.json")
    assert chronicle == bundle.chronicle.model_dump(mode="json")
    assert read_json(folder / "world" / "memory.json") == bundle.memory.model_dump(mode="json")
    assert read_json(folder / "session.json") == bundle.session.model_dump(mode="json")


def test_manifest_json_has_version_slot_time_and_heroes(saves, bundle):
    save_slot(saves, bundle, "manual-перед-боем", saved_at=SAVED_AT)
    data = read_json(slot_dir(saves, "w1", "manual-перед-боем") / "manifest.json")
    assert data["schema_version"] == CURRENT_SCHEMA_VERSION
    assert data["slot"] == "manual-перед-боем"
    assert data["saved_at"] == SAVED_AT
    assert data["world_id"] == "w1"
    assert data["current_hero_id"] == "h1"
    assert data["heroes"] == ["h1", "h2"]


def test_manifest_is_written_last(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    folder = slot_dir(saves, "w1", "auto")
    manifest_time = os.stat(folder / "manifest.json").st_mtime_ns
    others = [p for p in folder.rglob("*") if p.is_file() and p.name != "manifest.json"]
    assert others
    for path in others:
        assert os.stat(path).st_mtime_ns <= manifest_time


def test_empty_sections_are_written_as_empty_containers_not_missing(saves, empty_bundle):
    save_slot(saves, empty_bundle, "auto", saved_at=SAVED_AT)
    folder = slot_dir(saves, "w1", "auto")
    world = read_json(folder / "world" / "world.json")
    assert world["pantheon"] == {}
    assert world["events"] == []
    assert world["flags"] == {}
    assert world["npcs"] == {}
    memory = read_json(folder / "world" / "memory.json")
    assert memory["scenes"] == []
    assert memory["chapters"] == []
    assert memory["recent_turns"] == []
    assert read_json(folder / "world" / "chronicle.json")["entries"] == []


def test_empty_session_keys_are_present_as_null(saves, empty_bundle):
    save_slot(saves, empty_bundle, "auto", saved_at=SAVED_AT)
    session = read_json(slot_dir(saves, "w1", "auto") / "session.json")
    assert session == {
        "current_scene": None,
        "current_chapter": None,
        "active_combat": None,
        "pending_decision": None,
        "boundary_pending": False,
        "turn_seq": 0,
        "offered_choices": [],
        "last_combat": None,
    }


def test_bundle_without_heroes_writes_no_hero_files(saves, empty_bundle):
    save_slot(saves, empty_bundle, "auto", saved_at=SAVED_AT)
    names = files_in(slot_dir(saves, "w1", "auto"))
    assert [n for n in names if n.endswith("hero.json")] == []
    assert read_json(slot_dir(saves, "w1", "auto") / "manifest.json")["heroes"] == []


# --- world_id (B1) и имя слота (D12) ---

BAD_WORLD_IDS = ["", "..", "../x", "a/b", "a\\b", "/abs/path", "/", ".x", ".", "a..b", "w 1", "w.1"]


@pytest.mark.parametrize("world_id", ["w1", "old_world", "мир-1", "World_2", "a-b_c"])
def test_check_world_id_accepts_good_ids(world_id):
    check_world_id(world_id)


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_check_world_id_rejects_bad_ids(world_id):
    with pytest.raises(ValueError):
        check_world_id(world_id)


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_slot_dir_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        slot_dir(saves, world_id, "auto")


def test_slot_dir_rejects_bad_slot_name(saves):
    with pytest.raises(ValueError):
        slot_dir(saves, "w1", "manual-../x")


@pytest.mark.parametrize("slot", ["auto", "auto-1", "auto-12", "manual-a", "manual-перед боем"])
def test_check_slot_name_accepts_good_names(slot):
    check_slot_name(slot)


@pytest.mark.parametrize("slot", ["manual-A", "manual-Б", "manual-аБ", "manual-aB", "Auto"])
def test_check_slot_name_rejects_uppercase(slot):
    with pytest.raises(ValueError):
        check_slot_name(slot)
