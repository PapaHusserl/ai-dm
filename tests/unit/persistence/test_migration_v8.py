# Б0-П0 (docs/plan-b0.md, A1): миграция v7 -> v8, шкала Tone.romance расширена до четырёх значений.
# Ожидаемый API: ai_dm.persistence.migrations.m0008_v7_to_v8
#   migrate_v7_to_v8(data: dict, context=None) -> dict -- чистое dict -> dict, вход не мутирует;
#       schema_version ставит фреймворк; MIGRATIONS[7] is migrate_v7_to_v8;
#       CURRENT_SCHEMA_VERSION == 8.
#       Миграция заморожена: не импортирует ai_dm.state.* и content; контекст не нужен.
#   Правило: world.tone.romance == "есть" -> "откровенно" (Q1); "нет" / "намёки" / "" не меняются;
#       значение вне списка -> "". Остальное (notes, прочие шкалы, лимиты) не трогается.
#   Фикстура: tests/fixtures/saves/v7 -- слот auto мира old_world (сгенерирован движком v7 из v6,
#       tone.romance = "есть").
import ast
import copy
import json
import shutil
from pathlib import Path

import pytest
from game_kit import core_dump, make_app, scripted, text_step
from persist_kit import load_slot

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0008_v7_to_v8 import migrate_v7_to_v8
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V7 = FIXTURES / "v7"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0008_v7_to_v8.py"
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


def raw_tone(romance="", **extra):
    tone = {
        "mood": "мрачно", "violence": "жестоко", "horror": "умеренно", "romance": romance,
        "language": "грубо", "hard_limits": ["пытки"], "soft_limits": ["кровь"], "notes": "голос",
    }
    tone.update(extra)
    return tone


def raw_v7(romance="", tone=None):
    return {
        "manifest": {"schema_version": 7, "world_id": "old_world"},
        "world": {"world_id": "old_world", "tone": tone if tone is not None else raw_tone(romance)},
        "heroes": [],
        "session": {"turn_seq": 2},
    }


def romance_of(data):
    return data["world"]["tone"]["romance"]


# реестр и фреймворк

def test_registry_has_step_from_v7():
    assert MIGRATIONS[7] is migrate_v7_to_v8
    assert CURRENT_SCHEMA_VERSION >= 8


def test_framework_sets_schema_version_eight():
    assert migrate(raw_v7(), current_version=8)["manifest"]["schema_version"] == 8


def test_chain_v7_to_v8_needs_no_context():
    assert romance_of(migrate(raw_v7("есть"), current_version=8)) == "откровенно"


def test_v7_to_v7_is_not_touched():
    assert migrate(raw_v7("есть"), current_version=7) == raw_v7("есть")


def test_already_v8_dict_is_not_migrated_again():
    data = raw_v7("откровенно")
    data["manifest"]["schema_version"] = 8
    assert migrate(data, current_version=8) == data


def test_engine_v7_refuses_a_v8_dict():
    data = raw_v7()
    data["manifest"]["schema_version"] = 8
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=7)


def test_migrate_v7_to_v8_does_not_mutate_input():
    data = raw_v7("есть")
    before = copy.deepcopy(data)
    migrate_v7_to_v8(data)
    assert data == before


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# шкала romance

def test_yes_becomes_explicit():
    assert romance_of(migrate_v7_to_v8(raw_v7("есть"))) == "откровенно"


@pytest.mark.parametrize("value", ["нет", "намёки", ""])
def test_other_old_values_stay(value):
    assert romance_of(migrate_v7_to_v8(raw_v7(value))) == value


@pytest.mark.parametrize("value", ["страстно", "ЕСТЬ", "yes"])
def test_garbage_value_becomes_empty(value):
    assert romance_of(migrate_v7_to_v8(raw_v7(value))) == ""


def test_other_tone_fields_stay():
    tone = migrate_v7_to_v8(raw_v7("есть"))["world"]["tone"]
    assert tone == raw_tone("откровенно")


def test_notes_are_not_touched_even_if_they_mention_the_word():
    data = raw_v7(tone=raw_tone("есть", notes="romance: есть; голос"))
    assert migrate_v7_to_v8(data)["world"]["tone"]["notes"] == "romance: есть; голос"


def test_other_scales_with_the_same_word_are_not_touched():
    data = raw_v7(tone=raw_tone("есть", language="есть"))
    tone = migrate_v7_to_v8(data)["world"]["tone"]
    assert (tone["romance"], tone["language"]) == ("откровенно", "есть")


def test_tone_without_romance_is_fine():
    data = raw_v7(tone={"mood": "x"})
    assert migrate_v7_to_v8(data)["world"]["tone"] == {"mood": "x"}


def test_other_world_and_session_fields_stay():
    result = migrate_v7_to_v8(raw_v7("есть"))
    assert result["world"]["world_id"] == "old_world"
    assert result["session"] == {"turn_seq": 2}


def test_dict_without_tone_is_fine():
    data = raw_v7()
    del data["world"]["tone"]
    assert migrate(data, current_version=8)["manifest"]["schema_version"] == 8


def test_dict_without_world_is_fine():
    data = {"manifest": {"schema_version": 7, "world_id": "w"}, "session": {}}
    assert migrate(data, current_version=8)["manifest"]["schema_version"] == 8


# фикстура v7 и загрузка слота

def test_fixture_v7_is_v7_format_with_old_romance():
    manifest = json.loads((FIXTURE_V7 / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((FIXTURE_V7 / "world" / "world.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 7
    assert world["tone"]["romance"] == "есть"


def test_load_v7_returns_current_bundle(saves):
    install(saves, FIXTURE_V7)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v7_gives_new_romance_value(saves):
    install(saves, FIXTURE_V7)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.world.tone.romance == "откровенно"


def test_load_v7_keeps_the_rest_of_tone(saves):
    install(saves, FIXTURE_V7)
    tone = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).world.tone
    assert (tone.mood, tone.violence, tone.notes) == (
        "приключенческое фэнтези", "реалистично",
        "violence: реалистично; horror: кровавый; language: русский",
    )


def test_load_v7_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V7)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v7-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V7)


def test_load_v7_rewrites_slot_as_v8(saves):
    folder = install(saves, FIXTURE_V7)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    world = json.loads((folder / "world" / "world.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert world["tone"]["romance"] == "откровенно"


def test_load_v7_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V7)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V7)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v8_slot_is_too_new_for_engine_v7(saves):
    install(saves, FIXTURE_V7)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "auto", current_version=7)


@pytest.mark.parametrize("name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat", "v6"])
def test_old_fixture_chain_reaches_current(saves, name):
    install(saves, FIXTURES / name)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION


# нейтральность: один мок-ход на мигрированном бандле не зависит от старого значения шкалы

def played_dump(registry, tmp_path, romance):
    saves = tmp_path / "saves"
    folder = install(saves, FIXTURE_V7, slot="auto")
    world_path = folder / "world" / "world.json"
    world = json.loads(world_path.read_text(encoding="utf-8"))
    world["tone"]["romance"] = romance
    world_path.write_text(json.dumps(world, ensure_ascii=False, indent=2), encoding="utf-8")
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]), bundle=bundle)
    app.handle("Иду")
    return json.loads(core_dump(app.bundle))


def test_one_mock_turn_is_the_same_before_and_after_migration_except_romance(registry, tmp_path):
    old = played_dump(registry, tmp_path / "a", "нет")
    new = played_dump(registry, tmp_path / "b", "есть")
    assert old["world"]["tone"]["romance"] == "нет"
    assert new["world"]["tone"]["romance"] == "откровенно"
    old["world"]["tone"]["romance"] = new["world"]["tone"]["romance"] = ""
    assert old == new


# BackgroundSpec.description (Q4): новое поле v8

def test_load_v7_hero_without_description_gets_empty_string(saves):
    install(saves, FIXTURE_V7)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.heroes[0].sheet.background.description == ""


def test_background_description_survives_save_and_load(saves):
    install(saves, FIXTURE_V7)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    bundle.heroes[0].sheet.background.description = "Бывший стражник из Вейла"
    save_slot(saves, bundle, "manual-x", saved_at=bundle.manifest.saved_at)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert again.heroes[0].sheet.background.description == "Бывший стражник из Вейла"
