# Ожидаемый API: ai_dm.persistence.store (шаг 22, ARCHITECTURE A3, «Критерий 2»)
#   save_slot(root: Path, bundle: SaveBundle, slot: str, *, saved_at: str) -> Path
#       root -- каталог сохранений, слот лежит в root/<bundle.world.world_id>/slots/<slot>/.
#       saved_at -- строка времени сохранения, передаётся параметром (time.time() в тестах нет).
#       В manifest попадают slot и saved_at из параметров, schema_version = текущая,
#       heroes = id героев бандла по порядку. Возвращает Path каталога слота.
#       Имя слота: "auto", "auto-<число>" или "manual-<имя>" (имя непустое, строчное -- заглавные
#       буквы, в т.ч. кириллические, -> ValueError (D12); без "/", "\\" и "..", не начинается
#       с "."; кириллица и пробелы можно); иное -> ValueError до записи.
#       world_id обязан пройти layout.check_world_id (B1) -- иначе ValueError до записи.
#       Герои бандла: повтор hero.id или имени каталога hero_dir_name -> ValueError до записи,
#       слот не тронут (B3).
#   write_slot(root, world_id, bundle, slot, *, saved_at) -> Path       (B2)
#       то же, но world_id (каталог мира) -- явным аргументом, а не из bundle.world.
#   При падении второго os.replace (tmp -> final) старый слот возвращается (old -> final), в
#   slots/ нет ни .tmp-*, ни .old-* (D4).
#       Запись атомарна: файлы пишутся в slots/.tmp-<uuid>/, затем os.replace (через
#       os.replace как атрибут модуля os -- чтобы тест мог его подменить); старый слот
#       при сбое остаётся целым. Файлы -- model_dump_json(indent=2) (чтобы сбой можно было
#       вызвать подменой model_dump_json). После успеха в slots/ нет ни .tmp-*, ни .old.
#       Повторный save в тот же слот заменяет его.
#   save_auto(root, bundle, *, saved_at, cfg, keep: int | None = None) -> Path
#       ротация автосейвов; cfg обязателен (конфиг явно), число хранимых = cfg.saves.autosave_keep
#       (по умолчанию 3), явный keep важнее cfg: перед
#       записью auto -> auto-1, auto-1 -> auto-2, ..., auto-<keep-1> -> auto-<keep>;
#       auto-<keep> удаляется; затем пишется новый auto. Всего слотов не больше keep + 1.
#       Ручные слоты (manual-*) не трогает. Возвращает Path слота auto.
#   load_slot(root, world_id, slot, *, backup_ts=None, migrations=None, current_version=None)
#       -> SaveBundle
#       нет слота -> FileNotFoundError. Миграции и бэкап -- test_migrations.py.
#       bundle.world.world_id или manifest.world_id != world_id (каталог мира переименован) ->
#       ValueError до бэкапа и до записи (B2). После загрузки bundle.manifest.slot == slot --
#       истина в имени каталога, а не в manifest.json (D3).
#       В начале вызывается recover_slots (D2).
#   recover_slots(root, world_id) -> None                               (D2)
#       slots/.old-*: если слота с именем из его manifest.slot (сырой JSON) нет -- вернуть на
#       место, иначе удалить; slots/.tmp-* с manifest.json (запись полная): поставить на место,
#       если слота нет, иначе удалить; .tmp-* без manifest.json -- удалить.
#   Каталоги слотов, имя которых начинается с ".", и файлы (.DS_Store) при чтении slots/ и
#   heroes/ игнорируются (B5).
#   move_slot правит manifest.json как сырой JSON, не читая его моделями (B4).
#   list_slots(root, world_id) -> list[str]
#       отсортированные имена слотов; скрытые (.tmp-*, .old) не показываются; нет мира -> [].
import json
import os
import shutil
from pathlib import Path

import pytest
from persist_kit import srd_context
from slots_kit import list_slots

from ai_dm.config.settings import load_rules_config
from ai_dm.core.rng import Rng
from ai_dm.persistence.backup import make_backup
from ai_dm.persistence.layout import slot_dir
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import (
    load_slot,
    move_slot,
    recover_slots,
    save_auto,
    save_slot,
    write_slot,
)
from ai_dm.state.session import SessionState

SAVED_AT = "2026-01-01T12:00:00Z"
LATER = "2026-03-03T09:30:00Z"


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def boom(*args, **kwargs):
    raise RuntimeError("disk full")


def test_save_then_load_gives_equal_bundle(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert load_slot(saves, "w1", "auto") == bundle


def test_loaded_models_have_right_types(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert [h.name for h in loaded.heroes] == ["Арн", "Бранка Рыжая"]
    assert loaded.world.npcs["mentor_aldric"].opportunity[0].if_.type == "all"


def test_load_takes_slot_and_saved_at_from_save_call(saves, bundle):
    save_slot(saves, bundle, "manual-перед-боем", saved_at=LATER)
    loaded = load_slot(saves, "w1", "manual-перед-боем")
    assert loaded.manifest.slot == "manual-перед-боем"
    assert loaded.manifest.saved_at == LATER


def test_save_does_not_change_the_bundle_object(saves, bundle):
    before = bundle.model_dump_json()
    save_slot(saves, bundle, "manual-x", saved_at=LATER)
    assert bundle.model_dump_json() == before


def test_second_save_is_byte_identical_except_saved_at(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    first = tree(slot_dir(saves, "w1", "auto"))
    save_slot(saves, bundle, "auto", saved_at=LATER)
    second = tree(slot_dir(saves, "w1", "auto"))
    assert sorted(second) == sorted(first)
    for name in first:
        if name != "manifest.json":
            assert second[name] == first[name]
    assert second["manifest.json"].decode().replace(LATER, SAVED_AT) == (
        first["manifest.json"].decode()
    )


def test_second_save_with_same_time_is_fully_byte_identical(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    first = tree(slot_dir(saves, "w1", "auto"))
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert tree(slot_dir(saves, "w1", "auto")) == first


def test_save_load_save_is_byte_identical(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    first = tree(slot_dir(saves, "w1", "auto"))
    save_slot(saves, load_slot(saves, "w1", "auto"), "auto", saved_at=SAVED_AT)
    assert tree(slot_dir(saves, "w1", "auto")) == first


def test_empty_sections_stay_empty_after_cycle(saves, empty_bundle):
    save_slot(saves, empty_bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert loaded == empty_bundle
    assert loaded.world.pantheon == {}
    assert loaded.world.events == []
    assert loaded.memory.scenes == []
    assert loaded.memory.chapters == []
    assert loaded.memory.recent_turns == []
    assert loaded.memory.game_summary == ""
    assert loaded.chronicle.entries == []
    assert loaded.heroes == []


def test_heroes_load_in_ordinal_order(saves, bundle):
    bundle.heroes.reverse()
    bundle.manifest.heroes = ["h2", "h1"]
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert [h.id for h in loaded.heroes] == ["h1", "h2"]


def test_rng_continues_same_sequence_after_load(saves, bundle):
    rng = Rng.from_state(bundle.world.rng)
    for _ in range(5):
        rng.d(20)
    bundle.world.rng = rng.state
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    restored = Rng.from_state(loaded.world.rng)
    assert loaded.world.rng == rng.state
    assert [restored.d(20) for _ in range(10)] == [rng.d(20) for _ in range(10)]


def test_load_missing_slot_raises_file_not_found(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    with pytest.raises(FileNotFoundError):
        load_slot(saves, "w1", "manual-нет-такого")


def test_load_of_current_version_slot_changes_no_files_and_makes_no_backup(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(saves)
    load_slot(saves, "w1", "auto")
    assert tree(saves) == before
    assert not (saves / "w1" / "backups").exists()


# --- слоты ---


def test_list_slots_empty_for_unknown_world(saves):
    assert list_slots(saves, "w1") == []


def test_list_slots_returns_sorted_names(saves, bundle):
    save_slot(saves, bundle, "manual-б", saved_at=SAVED_AT)
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    save_slot(saves, bundle, "manual-а", saved_at=SAVED_AT)
    assert list_slots(saves, "w1") == ["auto", "manual-а", "manual-б"]


def test_manual_slot_with_cyrillic_name_roundtrips(saves, bundle):
    save_slot(saves, bundle, "manual-перед боссом", saved_at=SAVED_AT)
    assert load_slot(saves, "w1", "manual-перед боссом").world == bundle.world


def test_manual_and_auto_slots_are_independent(saves, bundle):
    save_slot(saves, bundle, "manual-a", saved_at=SAVED_AT)
    bundle.world.flags["later"] = True
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert "later" not in load_slot(saves, "w1", "manual-a").world.flags
    assert load_slot(saves, "w1", "auto").world.flags["later"] is True


@pytest.mark.parametrize(
    "slot", [
        "slot1", "manual-", "manual-../x", "manual-a/b", "manual-..", "auto-x", "", "../auto",
        "manual-A", "manual-Б", "manual-аБ",
    ],
)
def test_save_rejects_bad_slot_name(saves, bundle, slot):
    with pytest.raises(ValueError):
        save_slot(saves, bundle, slot, saved_at=SAVED_AT)
    assert not saves.exists() or list_slots(saves, "w1") == []


def test_save_accepts_rotated_auto_slot_name(saves, bundle):
    save_slot(saves, bundle, "auto-1", saved_at=SAVED_AT)
    assert list_slots(saves, "w1") == ["auto-1"]


def mark(bundle, number):
    bundle.world.flags["n"] = number


def saved_numbers(saves):
    return {
        slot: load_slot(saves, "w1", slot).world.flags["n"] for slot in list_slots(saves, "w1")
    }


def test_save_auto_first_time_makes_only_auto(cfg, saves, bundle):
    save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=2)
    assert list_slots(saves, "w1") == ["auto"]


def test_save_auto_rotates_previous_autosaves(cfg, saves, bundle):
    for number in (1, 2, 3):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=2)
    assert saved_numbers(saves) == {"auto": 3, "auto-1": 2, "auto-2": 1}


def test_save_auto_drops_oldest_beyond_keep(cfg, saves, bundle):
    for number in (1, 2, 3, 4, 5):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=2)
    assert saved_numbers(saves) == {"auto": 5, "auto-1": 4, "auto-2": 3}


def test_save_auto_keep_zero_keeps_only_latest(cfg, saves, bundle):
    for number in (1, 2):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=0)
    assert saved_numbers(saves) == {"auto": 2}


def test_save_auto_default_keep_is_three(cfg, saves, bundle):
    for number in range(1, 8):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg)
    assert list_slots(saves, "w1") == ["auto", "auto-1", "auto-2", "auto-3"]


def test_save_auto_does_not_touch_manual_slots(cfg, saves, bundle):
    mark(bundle, 0)
    save_slot(saves, bundle, "manual-a", saved_at=SAVED_AT)
    for number in (1, 2, 3, 4):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=1)
    assert saved_numbers(saves) == {"auto": 4, "auto-1": 3, "manual-a": 0}


def test_save_auto_default_keep_comes_from_the_config(saves, bundle):
    custom = load_rules_config(toml_text="[saves]\nautosave_keep = 1\n")
    for number in range(1, 6):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=custom)
    assert saved_numbers(saves) == {"auto": 5, "auto-1": 4}


def test_save_auto_explicit_keep_beats_the_config(saves, bundle):
    custom = load_rules_config(toml_text="[saves]\nautosave_keep = 1\n")
    for number in range(1, 6):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=custom, keep=2)
    assert saved_numbers(saves) == {"auto": 5, "auto-1": 4, "auto-2": 3}


def test_save_auto_without_cfg_is_an_error(saves, bundle):
    with pytest.raises(TypeError):
        save_auto(saves, bundle, saved_at=SAVED_AT)


def test_save_auto_returns_auto_slot_dir(cfg, saves, bundle):
    result = save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg)
    assert result == slot_dir(saves, "w1", "auto")


# --- атомарность ---


def test_failure_in_the_middle_of_writing_keeps_old_slot_loadable(saves, bundle, monkeypatch):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(slot_dir(saves, "w1", "auto"))
    bundle.world.flags["new"] = True
    monkeypatch.setattr(SessionState, "model_dump_json", boom)
    with pytest.raises(RuntimeError):
        save_slot(saves, bundle, "auto", saved_at=LATER)
    monkeypatch.undo()
    assert tree(slot_dir(saves, "w1", "auto")) == before
    loaded = load_slot(saves, "w1", "auto")
    assert "new" not in loaded.world.flags
    assert loaded.manifest.saved_at == SAVED_AT


def test_failure_at_final_replace_keeps_old_slot_loadable(saves, bundle, monkeypatch):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    bundle.world.flags["new"] = True
    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(RuntimeError):
        save_slot(saves, bundle, "auto", saved_at=LATER)
    monkeypatch.undo()
    loaded = load_slot(saves, "w1", "auto")
    assert "new" not in loaded.world.flags
    assert list_slots(saves, "w1") == ["auto"]


def test_failed_first_save_leaves_no_slot(saves, bundle, monkeypatch):
    monkeypatch.setattr(SessionState, "model_dump_json", boom)
    with pytest.raises(RuntimeError):
        save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    monkeypatch.undo()
    assert list_slots(saves, "w1") == []
    with pytest.raises(FileNotFoundError):
        load_slot(saves, "w1", "auto")


def test_failed_save_can_be_repeated_successfully(saves, bundle, monkeypatch):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    monkeypatch.setattr(SessionState, "model_dump_json", boom)
    with pytest.raises(RuntimeError):
        save_slot(saves, bundle, "auto", saved_at=LATER)
    monkeypatch.undo()
    bundle.world.flags["new"] = True
    save_slot(saves, bundle, "auto", saved_at=LATER)
    assert load_slot(saves, "w1", "auto").world.flags["new"] is True


def test_leftover_tmp_dir_does_not_break_save_load_or_listing(saves, bundle):
    junk = saves / "w1" / "slots" / ".tmp-deadbeef"
    (junk / "world").mkdir(parents=True)
    (junk / "world" / "world.json").write_text("{ обрыв", encoding="utf-8")
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert load_slot(saves, "w1", "auto") == bundle
    assert list_slots(saves, "w1") == ["auto"]


def test_successful_save_leaves_no_tmp_or_old_dirs(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    save_slot(saves, bundle, "auto", saved_at=LATER)
    names = sorted(p.name for p in (saves / "w1" / "slots").iterdir())
    assert names == ["auto"]


# --- world_id (B1) ---

BAD_WORLD_IDS = ["", "..", "../escaped", "a/b", "a\\b", "/abs/escaped", ".hidden", "w 1"]


def bundle_of_world(bundle, world_id):
    bundle.world.world_id = world_id
    bundle.manifest.world_id = world_id
    return bundle


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_save_slot_rejects_bad_world_id(saves, bundle, world_id):
    with pytest.raises(ValueError):
        save_slot(saves, bundle_of_world(bundle, world_id), "auto", saved_at=SAVED_AT)
    assert not saves.exists()
    assert not (saves.parent / "escaped").exists()


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_write_slot_rejects_bad_world_id(saves, bundle, world_id):
    with pytest.raises(ValueError):
        write_slot(saves, world_id, bundle, "auto", saved_at=SAVED_AT)
    assert not saves.exists()
    assert not (saves.parent / "escaped").exists()


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_save_auto_rejects_bad_world_id(cfg, saves, bundle, world_id):
    with pytest.raises(ValueError):
        save_auto(saves, bundle_of_world(bundle, world_id), saved_at=SAVED_AT, cfg=cfg)
    assert not saves.exists()


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_load_slot_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        load_slot(saves, world_id, "auto")


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_list_slots_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        list_slots(saves, world_id)


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_move_slot_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        move_slot(saves, world_id, "auto", "auto-1")


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_recover_slots_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        recover_slots(saves, world_id)


@pytest.mark.parametrize("world_id", BAD_WORLD_IDS)
def test_make_backup_rejects_bad_world_id(saves, world_id):
    with pytest.raises(ValueError):
        make_backup(saves, world_id, "auto", 0, ts="20260101T000000Z")


def test_write_slot_puts_slot_under_given_world_dir(saves, bundle):
    write_slot(saves, "w1", bundle, "auto", saved_at=SAVED_AT)
    assert list_slots(saves, "w1") == ["auto"]
    assert load_slot(saves, "w1", "auto") == bundle


# --- мир по каталогу (B2) ---


def test_load_of_renamed_world_dir_raises_value_error(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (saves / "w1").rename(saves / "w2")
    before = tree(saves)
    with pytest.raises(ValueError):
        load_slot(saves, "w2", "auto")
    assert tree(saves) == before


def test_load_with_foreign_manifest_world_id_raises_value_error(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    manifest_path = Path(folder) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["world_id"] = "other"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    before = tree(saves)
    with pytest.raises(ValueError):
        load_slot(saves, "w1", "auto")
    assert tree(saves) == before


def test_load_with_foreign_world_json_world_id_raises_value_error(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    world_path = Path(folder) / "world" / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world["world_id"] = "other"
    world_path.write_text(json.dumps(world, ensure_ascii=False), encoding="utf-8")
    before = tree(saves)
    with pytest.raises(ValueError):
        load_slot(saves, "w1", "auto")
    assert tree(saves) == before


# --- уникальность героев (B3) ---


def test_save_rejects_two_heroes_with_same_id(saves, bundle):
    bundle.heroes[1].id = "h1"
    with pytest.raises(ValueError):
        save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert not saves.exists()


def test_save_rejects_two_heroes_with_same_ordinal_and_name(saves, bundle):
    bundle.heroes[1].ordinal = 1
    bundle.heroes[1].name = bundle.heroes[0].name
    with pytest.raises(ValueError):
        save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert not saves.exists()


def test_save_rejects_heroes_with_same_dir_name_but_different_names(saves, bundle):
    bundle.heroes[1].ordinal = 1
    bundle.heroes[1].name = "арн!"
    with pytest.raises(ValueError):
        save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert not saves.exists()


def test_duplicate_heroes_leave_existing_slot_untouched(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(saves)
    bundle.heroes[1].id = "h1"
    with pytest.raises(ValueError):
        save_slot(saves, bundle, "auto", saved_at=LATER)
    assert tree(saves) == before


def test_write_slot_rejects_duplicate_hero_ids(saves, bundle):
    bundle.heroes[1].id = "h1"
    with pytest.raises(ValueError):
        write_slot(saves, "w1", bundle, "auto", saved_at=SAVED_AT)


def test_same_name_with_different_ordinals_is_allowed(saves, bundle):
    bundle.heroes[1].name = bundle.heroes[0].name
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    assert len(load_slot(saves, "w1", "auto").heroes) == 2


# --- мусор в каталогах (B5) ---


def test_ds_store_in_slots_dir_is_ignored(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (saves / "w1" / "slots" / ".DS_Store").write_bytes(b"\x00junk")
    assert list_slots(saves, "w1") == ["auto"]
    assert load_slot(saves, "w1", "auto") == bundle


def test_ds_store_in_heroes_dir_is_ignored_on_load(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (Path(folder) / "heroes" / ".DS_Store").write_bytes(b"\x00junk")
    assert load_slot(saves, "w1", "auto") == bundle


def test_hidden_dirs_in_heroes_dir_are_ignored_on_load(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (Path(folder) / "heroes" / ".tmp-x").mkdir()
    (Path(folder) / "heroes" / ".old-x").mkdir()
    assert load_slot(saves, "w1", "auto") == bundle


def test_plain_file_in_heroes_dir_is_ignored_on_load(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (Path(folder) / "heroes" / "notes.txt").write_text("заметка", encoding="utf-8")
    assert load_slot(saves, "w1", "auto") == bundle


def test_hidden_dir_in_slots_dir_is_not_a_slot(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    (saves / "w1" / "slots" / ".cache").mkdir()
    assert list_slots(saves, "w1") == ["auto"]


# --- manifest.slot после загрузки (D3) ---


def test_loaded_manifest_slot_is_the_directory_name_not_the_file_value(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    manifest_path = Path(folder) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["slot"] = "manual-liar"
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    assert load_slot(saves, "w1", "auto").manifest.slot == "auto"


def test_loaded_manifest_slot_matches_dir_after_copying_slot_dir(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    shutil.copytree(folder, saves / "w1" / "slots" / "manual-копия")
    assert load_slot(saves, "w1", "manual-копия").manifest.slot == "manual-копия"


# --- ротация: удаление последнего через os.replace (D3) ---


def test_save_auto_drops_oldest_through_os_replace_into_old_dir(cfg, saves, bundle, monkeypatch):
    for number in (1, 2, 3):
        mark(bundle, number)
        save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=1)
    real_replace = os.replace
    calls = []

    def spy(src, dst, *args, **kwargs):
        calls.append((Path(src).name, Path(dst).name))
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", spy)
    mark(bundle, 4)
    save_auto(saves, bundle, saved_at=SAVED_AT, cfg=cfg, keep=1)
    monkeypatch.undo()
    assert any(src == "auto-1" and dst.startswith(".old-") for src, dst in calls)
    assert sorted(p.name for p in (saves / "w1" / "slots").iterdir()) == ["auto", "auto-1"]
    assert saved_numbers(saves) == {"auto": 4, "auto-1": 3}


# --- ротация сырых слотов старых версий (B4) ---


FIXTURE_V0 = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v0"


def v0_bundle(bundle):
    return bundle_of_world(bundle, "old_world")


def install_v0(saves, slot):
    target = saves / "old_world" / "slots" / slot
    shutil.copytree(FIXTURE_V0, target)
    return target


def test_rotation_moves_v0_slot_from_auto_to_auto_1_without_models(cfg, saves, bundle):
    install_v0(saves, "auto")
    save_auto(saves, v0_bundle(bundle), saved_at=SAVED_AT, cfg=cfg)
    moved = saves / "old_world" / "slots" / "auto-1"
    manifest = json.loads((moved / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["slot"] == "auto-1"
    assert "schema_version" not in manifest
    assert (moved / "hero.json").is_file()
    assert list_slots(saves, "old_world") == ["auto", "auto-1"]


def test_rotation_moves_v0_slot_from_auto_1_to_auto_2_without_models(cfg, saves, bundle):
    install_v0(saves, "auto-1")
    save_auto(saves, v0_bundle(bundle), saved_at=SAVED_AT, cfg=cfg)
    moved = saves / "old_world" / "slots" / "auto-2"
    manifest = json.loads((moved / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["slot"] == "auto-2"
    assert "schema_version" not in manifest
    assert list_slots(saves, "old_world") == ["auto", "auto-2"]


def test_rotation_keeps_other_manifest_keys_of_v0_slot(cfg, saves, bundle):
    install_v0(saves, "auto")
    original = json.loads((FIXTURE_V0 / "manifest.json").read_text(encoding="utf-8"))
    save_auto(saves, v0_bundle(bundle), saved_at=SAVED_AT, cfg=cfg)
    moved = saves / "old_world" / "slots" / "auto-1" / "manifest.json"
    manifest = json.loads(moved.read_text(encoding="utf-8"))
    original["slot"] = "auto-1"
    assert manifest == original


def test_move_slot_works_on_manifest_with_unknown_future_field(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    manifest_path = Path(folder) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["field_from_the_future"] = 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    move_slot(saves, "w1", "auto", "auto-1")
    moved = json.loads(
        (saves / "w1" / "slots" / "auto-1" / "manifest.json").read_text(encoding="utf-8")
    )
    assert moved["slot"] == "auto-1"
    assert moved["field_from_the_future"] == 1


def test_rotated_v0_slot_still_migrates_on_load(cfg, saves, bundle):
    install_v0(saves, "auto")
    save_auto(saves, v0_bundle(bundle), saved_at=SAVED_AT, cfg=cfg)
    loaded = load_slot(
        saves, "old_world", "auto-1", backup_ts="20260101T000000Z", context=srd_context(),
    )
    assert loaded.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert loaded.manifest.slot == "auto-1"
    assert loaded.heroes[0].name == "Старый Арн"


# --- второй os.replace падает (D4) ---


def flaky_second_replace(monkeypatch):
    real_replace = os.replace

    def flaky(src, dst, *args, **kwargs):
        if Path(src).name.startswith(".tmp-"):
            raise OSError("replace failed")
        return real_replace(src, dst, *args, **kwargs)

    monkeypatch.setattr(os, "replace", flaky)


def test_failure_at_second_replace_rolls_back_old_slot(saves, bundle, monkeypatch):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(saves)
    bundle.world.flags["new"] = True
    flaky_second_replace(monkeypatch)
    with pytest.raises(OSError):
        save_slot(saves, bundle, "auto", saved_at=LATER)
    monkeypatch.undo()
    assert tree(saves) == before
    assert sorted(p.name for p in (saves / "w1" / "slots").iterdir()) == ["auto"]
    loaded = load_slot(saves, "w1", "auto")
    assert "new" not in loaded.world.flags
    assert loaded.manifest.saved_at == SAVED_AT


def test_failure_at_second_replace_of_first_save_leaves_nothing(saves, bundle, monkeypatch):
    flaky_second_replace(monkeypatch)
    with pytest.raises(OSError):
        save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    monkeypatch.undo()
    assert list_slots(saves, "w1") == []
    assert not any(slot_dir(saves, "w1", "auto").parent.glob(".*"))


# --- восстановление после сбоя (D2) ---


def slots_names(saves):
    return sorted(p.name for p in (saves / "w1" / "slots").iterdir())


def test_recover_returns_orphan_old_dir_to_its_slot(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(folder)
    os.replace(folder, saves / "w1" / "slots" / ".old-abc")
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]
    assert tree(slot_dir(saves, "w1", "auto")) == before


def test_recover_removes_old_dir_when_slot_exists(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    shutil.copytree(folder, saves / "w1" / "slots" / ".old-abc")
    before = tree(folder)
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]
    assert tree(folder) == before


def test_recover_puts_complete_tmp_dir_in_place_when_slot_missing(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    before = tree(folder)
    os.replace(folder, saves / "w1" / "slots" / ".tmp-abc")
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]
    assert tree(slot_dir(saves, "w1", "auto")) == before


def test_recover_prefers_complete_tmp_over_old_when_slot_missing(saves, bundle):
    # процесс упал между replace(final -> old) и replace(tmp -> final):
    # полный .tmp — новое сохранение, его и ставим; .old того же слота удаляется
    old_folder = save_slot(saves, bundle, "auto", saved_at="2026-01-01T00:00:00Z")
    old_tree = tree(old_folder)
    os.replace(old_folder, saves / "w1" / "slots" / ".old-abc")
    new_folder = save_slot(saves, bundle, "auto", saved_at="2026-01-02T00:00:00Z")
    new_tree = tree(new_folder)
    assert new_tree != old_tree
    os.replace(new_folder, saves / "w1" / "slots" / ".tmp-def")
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]
    assert tree(slot_dir(saves, "w1", "auto")) == new_tree


def test_recover_removes_complete_tmp_dir_when_slot_exists(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    shutil.copytree(folder, saves / "w1" / "slots" / ".tmp-abc")
    before = tree(folder)
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]
    assert tree(folder) == before


def test_recover_removes_tmp_dir_without_manifest(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    junk = saves / "w1" / "slots" / ".tmp-abc"
    (junk / "world").mkdir(parents=True)
    (junk / "world" / "world.json").write_text("{ обрыв", encoding="utf-8")
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["auto"]


def test_recover_removes_tmp_dir_without_manifest_even_if_no_slots(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    shutil.rmtree(saves / "w1" / "slots" / "auto")
    (saves / "w1" / "slots" / ".tmp-abc" / "world").mkdir(parents=True)
    recover_slots(saves, "w1")
    assert slots_names(saves) == []


def test_recover_for_unknown_world_does_nothing(saves):
    recover_slots(saves, "w1")
    assert not saves.exists()


def test_recover_restores_slot_under_name_from_manifest_not_dir_name(saves, bundle):
    folder = save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    os.replace(folder, saves / "w1" / "slots" / ".old-zzz")
    recover_slots(saves, "w1")
    assert slots_names(saves) == ["manual-x"]


def test_list_slots_recovers_orphan_old_dir(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    os.replace(folder, saves / "w1" / "slots" / ".old-abc")
    assert list_slots(saves, "w1") == ["auto"]


def test_load_slot_recovers_orphan_old_dir(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    os.replace(folder, saves / "w1" / "slots" / ".old-abc")
    assert load_slot(saves, "w1", "auto") == bundle


def test_load_slot_recovers_complete_tmp_dir(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    os.replace(folder, saves / "w1" / "slots" / ".tmp-abc")
    assert load_slot(saves, "w1", "auto") == bundle
