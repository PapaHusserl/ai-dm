# Ожидаемый API: ai_dm.persistence.migrations и store.load_slot (шаг 22, A3, «Критерий 3»)
#   migrations.CURRENT_SCHEMA_VERSION: int == 2 (этап 2; звенья 0 и 1, см. test_migration_v2.py)
#   migrations.MIGRATIONS: dict[int, Callable[[dict], dict]]  -- {from_version: fn(bundle_dict)}
#       в реестре есть звено 0 (m0001_v0_to_v1). Миграции чисто dict -> dict.
#   migrations.SaveTooNew(Exception), migrations.MigrationMissing(Exception)
#   migrations.migrate(data: dict, *, registry=None, current_version=None) -> dict
#       data -- «сырой» бандл-словарь {"manifest": {...}, "world": {...}, ...};
#       версия = data["manifest"].get("schema_version", 0) (нет версии = 0);
#       версия > current_version -> SaveTooNew; версия == current -> data без изменений;
#       иначе цепочка registry[v], registry[v+1], ... до current_version; нет звена ->
#       MigrationMissing (в тексте -- номер версии без звена); после каждого звена фреймворк
#       сам ставит manifest.schema_version = v + 1 (миграции этого не делают);
#       входной словарь не мутируется. registry / current_version по умолчанию -- MIGRATIONS /
#       CURRENT_SCHEMA_VERSION (параметры нужны, чтобы тест подставлял свои звенья).
#   Форма сырого v0-словаря (так его собирает чтение слота без знания версии): ключи
#       "manifest", "world", "session", а герой v0 лежит одним "hero" (корневой hero.json);
#       "chronicle" / "memory" / "heroes" нет, если нет соответствующих файлов.
#   MIGRATIONS[0] (v0 -> v1): hero -> heroes=[hero]; manifest.heroes = id героев;
#       добавляет chronicle={"entries": []}, memory={"scenes": [], "chapters": [],
#       "game_summary": "", "recent_turns": []}, world.pantheon={}, world.tone (все строки "",
#       hard_limits / soft_limits = []) -- через setdefault (D5): уже существующие в v0-словаре
#       chronicle / memory / pantheon / tone не перезаписываются; остальное не трогает.
#       Тесты сравнивают с литералами, а не с Memory() / Tone() (миграция заморожена в v1,
#       модели со временем меняются).
#   store.load_slot(root, world_id, slot, *, backup_ts=None, migrations=None,
#                   current_version=None) -> SaveBundle
#       1. читает raw: manifest.json, world/world.json, session.json, world/chronicle.json и
#          world/memory.json (если есть), heroes/*/hero.json по имени каталога (список heroes)
#          или корневой hero.json (ключ "hero");
#       2. версия из manifest; новее текущей -> SaveTooNew, файлы НЕ тронуты (проверка до
#          валидации и до бэкапа);
#       3. старее -> бэкап всего слота байт в байт в root/<world_id>/backups/<slot>-v<old>-<ts>/
#          (ts = backup_ts, по умолчанию текущее время), цепочка migrate(), валидация
#          SaveBundle, перезапись слота атомарно в раскладке текущей версии (старые файлы,
#          например корневой hero.json, исчезают; manifest.schema_version = current_version);
#       4. нет звена -> MigrationMissing; цепочка проверяется ДО бэкапа (D1): слот не изменён
#          и бэкапа нет -- повторные вызовы с тем же backup_ts тоже ничего не создают;
#       5. bundle.world.world_id или manifest.world_id != world_id -> ValueError до бэкапа и до
#          записи (B2); миграция перезаписывает именно загружаемый каталог;
#       6. коллизия имени бэкапа (D1): уже есть <slot>-v<old>-<ts> -> суффикс -2, -3, ...;
#          существующий бэкап не трогается. make_backup(root, world_id, slot, old_version,
#          ts=None) -> Path (D12; без folder: копирует slot_dir(root, world_id, slot));
#       7. после загрузки bundle.manifest.slot == имя каталога слота (D3);
#       8. при чтении heroes/ учитываются только каталоги без "." в начале (B5);
#       migrations -- инжектируемый реестр, current_version -- целевая версия (по умолчанию
#       MIGRATIONS / CURRENT_SCHEMA_VERSION). Повторная загрузка после миграции -- без
#       нового бэкапа.
import copy
import json
import re
import shutil
from pathlib import Path

import pytest
from persist_kit import load_slot

from ai_dm.persistence.backup import make_backup
from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    MigrationContext,
    MigrationMissing,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.store import save_slot
from ai_dm.state.save import SaveBundle

FIXTURE_V0 = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v0"
BACKUP_TS = "20260101T000000Z"


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install_v0(saves, slot="auto"):
    target = saves / "old_world" / "slots" / slot
    shutil.copytree(FIXTURE_V0, target)
    return target


def backups(saves):
    return sorted((saves / "old_world" / "backups").glob("auto-v0-*"))


def raw_v0():
    return {
        "manifest": {
            "engine_version": "0.0.1", "world_id": "old_world", "campaign_id": None,
            "slot": "auto", "saved_at": "2025-12-01T10:00:00Z", "current_hero_id": "h1",
        },
        "world": {
            "world_id": "old_world",
            "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0},
        },
        "session": {},
        "hero": {
            "id": "h1", "ordinal": 1, "name": "Арн",
            "sheet": {
                "species_id": "human", "class_id": "fighter",
                "background": {
                    "name": "Солдат", "abilities": ["str", "dex", "con"],
                    "skills": ["athletics", "intimidation"], "tool": "dice_set",
                    "feat": "savage_attacker",
                },
                "abilities": {"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
            },
            "creature": {"hp_current": 12, "hp_max": 12},
        },
    }


# --- migrate(): чистая цепочка на словарях ---


def step_0_to_1(data, context=None):
    data = copy.deepcopy(data)
    data["trace"].append("0to1")
    return data


def step_1_to_2(data, context=None):
    data = copy.deepcopy(data)
    data["trace"].append("1to2")
    return data


def test_current_schema_version_is_fourteen():
    assert CURRENT_SCHEMA_VERSION == 14


def test_registry_has_step_from_v0():
    assert 0 in MIGRATIONS


def test_chain_v0_to_v2_runs_steps_in_order():
    data = {"manifest": {}, "trace": []}
    result = migrate(data, registry={0: step_0_to_1, 1: step_1_to_2}, current_version=2)
    assert result["trace"] == ["0to1", "1to2"]


def test_chain_sets_schema_version_to_target():
    data = {"manifest": {}, "trace": []}
    result = migrate(data, registry={0: step_0_to_1, 1: step_1_to_2}, current_version=2)
    assert result["manifest"]["schema_version"] == 2


def test_chain_starts_from_stored_version():
    data = {"manifest": {"schema_version": 1}, "trace": []}
    result = migrate(data, registry={0: step_0_to_1, 1: step_1_to_2}, current_version=2)
    assert result["trace"] == ["1to2"]


def test_migrate_does_not_mutate_input():
    data = {"manifest": {}, "trace": []}
    migrate(data, registry={0: step_0_to_1}, current_version=1)
    assert data == {"manifest": {}, "trace": []}


def test_current_version_data_returned_unchanged():
    data = {"manifest": {"schema_version": 2}, "trace": []}
    result = migrate(data, registry={0: step_0_to_1, 1: step_1_to_2}, current_version=2)
    assert result == data


def test_missing_step_raises_migration_missing_with_version():
    data = {"manifest": {}, "trace": []}
    with pytest.raises(MigrationMissing, match="1"):
        migrate(data, registry={0: step_0_to_1}, current_version=2)


def test_empty_registry_raises_migration_missing_for_v0():
    with pytest.raises(MigrationMissing):
        migrate({"manifest": {}}, registry={}, current_version=1)


def test_newer_save_raises_save_too_new():
    data = {"manifest": {"schema_version": 3}}
    with pytest.raises(SaveTooNew):
        migrate(data, registry={}, current_version=2)


# --- MIGRATIONS[0]: v0 -> v1 ---


def test_v0_migration_result_validates_as_bundle():
    result = migrate(raw_v0(), context=MigrationContext(item_cost={}))
    bundle = SaveBundle.model_validate(result)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_v0_migration_moves_hero_into_heroes_list():
    result = migrate(raw_v0(), context=MigrationContext(item_cost={}))
    assert "hero" not in result
    assert [h["id"] for h in result["heroes"]] == ["h1"]
    assert result["manifest"]["heroes"] == ["h1"]


def test_v0_migration_adds_empty_sections():
    result = migrate(raw_v0(), registry={0: MIGRATIONS[0]}, current_version=1)
    assert result["chronicle"] == {"entries": []}
    assert result["memory"] == {
        "scenes": [], "chapters": [], "game_summary": "", "recent_turns": [],
    }
    assert result["world"]["pantheon"] == {}
    assert result["world"]["tone"] == {
        "mood": "", "violence": "", "horror": "", "romance": "", "language": "",
        "hard_limits": [], "soft_limits": [],
    }


def test_v0_migration_does_not_overwrite_existing_chronicle():
    data = raw_v0()
    data["chronicle"] = {"entries": [{"text": "запись"}]}
    result = migrate(data, registry={0: MIGRATIONS[0]}, current_version=1)
    assert result["chronicle"] == {"entries": [{"text": "запись"}]}


def test_v0_migration_does_not_overwrite_existing_memory():
    data = raw_v0()
    data["memory"] = {"scenes": [], "chapters": [], "game_summary": "кратко", "recent_turns": []}
    result = migrate(data, context=MigrationContext(item_cost={}))
    assert result["memory"]["game_summary"] == "кратко"


def test_v0_migration_does_not_overwrite_existing_pantheon_and_tone():
    data = raw_v0()
    data["world"]["pantheon"] = {"sun": {"id": "sun", "name": "Солнцеликий"}}
    data["world"]["tone"] = {"mood": "мрачный"}
    result = migrate(data, context=MigrationContext(item_cost={}))
    assert result["world"]["pantheon"] == {"sun": {"id": "sun", "name": "Солнцеликий"}}
    assert result["world"]["tone"]["mood"] == "мрачный"


def test_v0_migration_keeps_existing_data():
    data = raw_v0()
    data["world"]["flags"] = {"met_aldric": True}
    result = migrate(data, context=MigrationContext(item_cost={}))
    assert result["world"]["flags"] == {"met_aldric": True}
    assert result["world"]["rng"] == data["world"]["rng"]
    assert result["manifest"]["world_id"] == "old_world"


def test_v0_migration_does_not_mutate_input():
    data = raw_v0()
    migrate(data, context=MigrationContext(item_cost={}))
    assert data == raw_v0()


# --- загрузка фикстуры tests/fixtures/saves/v0 ---


def test_fixture_v0_has_no_schema_version_and_root_hero():
    manifest = json.loads((FIXTURE_V0 / "manifest.json").read_text(encoding="utf-8"))
    assert "schema_version" not in manifest
    assert (FIXTURE_V0 / "hero.json").is_file()
    assert not (FIXTURE_V0 / "world" / "memory.json").exists()


def test_load_v0_returns_current_version_bundle(saves):
    install_v0(saves)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.manifest.heroes == ["h1"]
    assert bundle.manifest.current_hero_id == "h1"


def test_load_v0_keeps_old_data(saves):
    install_v0(saves)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.world.world_id == "old_world"
    assert bundle.world.clock.now_s == 90000
    assert bundle.world.flags == {"met_aldric": True}
    assert bundle.world.npcs["mentor_aldric"].attitude == 15
    assert bundle.world.locations["tavern"].name == "Таверна"
    assert bundle.world.rng.seed == 7
    assert bundle.heroes[0].name == "Старый Арн"
    assert bundle.heroes[0].money_cp == 1235
    # v1 -> v2: голый dict сцены этапа 1 не переносится
    assert bundle.session.current_scene is None


def test_load_v0_adds_empty_sections(saves):
    install_v0(saves)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.world.pantheon == {}
    assert bundle.world.tone.mood == ""
    assert bundle.world.tone.hard_limits == []
    assert bundle.world.tone.soft_limits == []
    assert bundle.memory.scenes == []
    assert bundle.memory.chapters == []
    assert bundle.memory.game_summary == ""
    assert bundle.memory.recent_turns == []
    assert bundle.chronicle.entries == []


def test_load_v0_makes_byte_exact_backup(saves):
    install_v0(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    found = backups(saves)
    assert len(found) == 1
    assert found[0].name == f"auto-v0-{BACKUP_TS}"
    assert tree(found[0]) == tree(FIXTURE_V0)


def test_load_v0_rewrites_slot_in_current_layout(saves):
    folder = install_v0(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert (folder / "world" / "memory.json").is_file()
    assert (folder / "world" / "chronicle.json").is_file()
    assert (folder / "heroes" / "01_старый-арн" / "hero.json").is_file()
    assert not (folder / "hero.json").exists()


def test_load_v0_written_pantheon_and_tone_keys_exist_on_disk(saves):
    folder = install_v0(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    world = json.loads((folder / "world" / "world.json").read_text(encoding="utf-8"))
    assert world["pantheon"] == {}
    assert "tone" in world


def test_load_v0_twice_makes_no_second_backup_and_same_bundle(saves):
    install_v0(saves)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(backups(saves)) == 1


def test_load_v0_does_not_touch_fixture_itself(saves):
    before = tree(FIXTURE_V0)
    install_v0(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert tree(FIXTURE_V0) == before


# --- цепочка v0 -> v2 через инжектируемый реестр ---


def add_v2_flag(data, context=None):
    data = copy.deepcopy(data)
    data["world"]["flags"]["migrated_v2"] = True
    # как настоящее звено 1 -> 2: голый dict сцены этапа 1 новая модель не принимает
    data["session"]["current_scene"] = None
    return data


def test_load_v0_with_injected_chain_reaches_current(saves):
    folder = install_v0(saves)
    registry = {**MIGRATIONS, 1: add_v2_flag}
    bundle = load_slot(
        saves, "old_world", "auto",
        backup_ts=BACKUP_TS, migrations=registry,
    )
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.world.flags == {"met_aldric": True, "migrated_v2": True}
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION


def test_chain_backup_is_of_original_v0_slot(saves):
    install_v0(saves)
    registry = {**MIGRATIONS, 1: add_v2_flag}
    load_slot(
        saves, "old_world", "auto",
        backup_ts=BACKUP_TS, migrations=registry,
    )
    found = backups(saves)
    assert len(found) == 1
    assert tree(found[0]) == tree(FIXTURE_V0)


def make_v1_slot(saves, bundle):
    # save_slot пишет текущую версию, поэтому manifest опускаем до v1 вручную
    folder = Path(save_slot(saves, bundle, "auto", saved_at="2026-01-01T12:00:00Z"))
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    return folder


def test_v1_slot_migrates_to_v2_with_only_last_step(saves, bundle):
    make_v1_slot(saves, bundle)
    registry = {1: add_v2_flag}
    loaded = load_slot(
        saves, "w1", "auto", backup_ts=BACKUP_TS, migrations=registry, current_version=2,
    )
    assert loaded.world.flags["migrated_v2"] is True
    assert (saves / "w1" / "backups" / f"auto-v1-{BACKUP_TS}").is_dir()


# --- MigrationMissing и SaveTooNew на диске ---


def test_load_with_missing_step_raises_and_keeps_slot(saves):
    folder = install_v0(saves)
    before = tree(folder)
    with pytest.raises(MigrationMissing):
        load_slot(
            saves, "old_world", "auto",
            backup_ts=BACKUP_TS, migrations={0: MIGRATIONS[0]}, current_version=2,
        )
    assert tree(folder) == before


def test_load_with_missing_step_makes_no_backup(saves):
    install_v0(saves)
    with pytest.raises(MigrationMissing):
        load_slot(
            saves, "old_world", "auto",
            backup_ts=BACKUP_TS, migrations={0: MIGRATIONS[0]}, current_version=2,
        )
    assert not (saves / "old_world" / "backups").exists()


def test_load_with_missing_step_twice_with_same_ts_makes_no_backups(saves):
    folder = install_v0(saves)
    before = tree(folder)
    for _ in range(2):
        with pytest.raises(MigrationMissing):
            load_slot(
                saves, "old_world", "auto",
                backup_ts=BACKUP_TS, migrations={0: MIGRATIONS[0]}, current_version=2,
            )
    backups_dir = saves / "old_world" / "backups"
    assert not backups_dir.exists() or list(backups_dir.iterdir()) == []
    assert tree(folder) == before


def test_load_with_empty_registry_raises_migration_missing(saves):
    folder = install_v0(saves)
    before = tree(folder)
    with pytest.raises(MigrationMissing):
        load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS, migrations={})
    assert tree(folder) == before
    assert not (saves / "old_world" / "backups").exists()


def make_too_new_slot(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at="2026-01-01T12:00:00Z")
    manifest_path = Path(folder) / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = CURRENT_SCHEMA_VERSION + 4
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    # поле из будущего: валидация текущей схемы такой слот не пропустила бы
    world_path = Path(folder) / "world" / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world["field_from_the_future"] = 1
    world_path.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    return Path(folder)


def test_load_newer_save_raises_save_too_new(saves, bundle):
    make_too_new_slot(saves, bundle)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "w1", "auto", backup_ts=BACKUP_TS)


def test_load_newer_save_does_not_touch_files_or_make_backup(saves, bundle):
    folder = make_too_new_slot(saves, bundle)
    before = tree(saves)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "w1", "auto", backup_ts=BACKUP_TS)
    assert tree(saves) == before
    assert tree(folder)
    assert not (saves / "w1" / "backups").exists()


# --- коллизия имени бэкапа (D1) ---


def precreate_backup(saves, suffix=""):
    folder = saves / "old_world" / "backups" / f"auto-v0-{BACKUP_TS}{suffix}"
    folder.mkdir(parents=True)
    (folder / "marker.txt").write_text("не трогать", encoding="utf-8")
    return folder


def test_backup_name_collision_gets_suffix_2(saves):
    install_v0(saves)
    existing = precreate_backup(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = saves / "old_world" / "backups" / f"auto-v0-{BACKUP_TS}-2"
    assert tree(second) == tree(FIXTURE_V0)
    assert tree(existing) == {"marker.txt": "не трогать".encode()}


def test_backup_name_second_collision_gets_suffix_3(saves):
    install_v0(saves)
    precreate_backup(saves)
    precreate_backup(saves, "-2")
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    third = saves / "old_world" / "backups" / f"auto-v0-{BACKUP_TS}-3"
    assert tree(third) == tree(FIXTURE_V0)


def test_make_backup_copies_slot_byte_for_byte(saves):
    install_v0(saves)
    result = make_backup(saves, "old_world", "auto", 0, ts=BACKUP_TS)
    assert Path(result) == saves / "old_world" / "backups" / f"auto-v0-{BACKUP_TS}"
    assert tree(Path(result)) == tree(FIXTURE_V0)


def test_make_backup_twice_with_same_ts_gives_suffix_2(saves):
    install_v0(saves)
    first = make_backup(saves, "old_world", "auto", 0, ts=BACKUP_TS)
    second = make_backup(saves, "old_world", "auto", 0, ts=BACKUP_TS)
    assert Path(second).name == f"auto-v0-{BACKUP_TS}-2"
    assert tree(Path(first)) == tree(Path(second))


def test_make_backup_without_ts_uses_current_time_name(saves):
    install_v0(saves)
    result = make_backup(saves, "old_world", "auto", 0)
    assert re.fullmatch(r"auto-v0-\d{8}T\d{6}Z", Path(result).name)


# --- мир по каталогу при миграции (B2) ---


def test_v0_slot_in_renamed_world_dir_raises_and_writes_nothing(saves):
    target = saves / "renamed_world" / "slots" / "auto"
    shutil.copytree(FIXTURE_V0, target)
    before = tree(saves)
    with pytest.raises(ValueError):
        load_slot(saves, "renamed_world", "auto", backup_ts=BACKUP_TS)
    assert tree(saves) == before
    assert not (saves / "renamed_world" / "backups").exists()


def test_v0_load_rewrites_only_the_loaded_world_dir(saves):
    install_v0(saves)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert sorted(p.name for p in saves.iterdir()) == ["old_world"]


# --- manifest.slot после миграции (D3) ---


def test_loaded_v0_manifest_slot_is_the_directory_name(saves):
    install_v0(saves, slot="manual-копия")
    bundle = load_slot(saves, "old_world", "manual-копия", backup_ts=BACKUP_TS)
    assert bundle.manifest.slot == "manual-копия"
    folder = saves / "old_world" / "slots" / "manual-копия"
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["slot"] == "manual-копия"


# --- мусор в heroes/ при миграции (B5) ---


def test_ds_store_in_heroes_dir_does_not_break_migration(saves, bundle):
    folder = make_v1_slot(saves, bundle)
    (Path(folder) / "heroes" / ".DS_Store").write_bytes(b"\x00junk")
    (Path(folder) / "heroes" / ".tmp-x").mkdir()
    loaded = load_slot(
        saves, "w1", "auto", backup_ts=BACKUP_TS, migrations={1: add_v2_flag}, current_version=2,
    )
    assert [h.id for h in loaded.heroes] == ["h1", "h2"]
