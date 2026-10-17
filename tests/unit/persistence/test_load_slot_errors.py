# К0а (docs/plan-k0.md, A6): старые мутанты migrate / load_slot (BACKLOG 16) -- тексты ошибок,
# deepcopy входа, версия переписанного слота, проверка сейва и чужого мира.
import copy
import json

import pytest

from ai_dm.persistence.migrations import (
    MigrationContextRequired,
    MigrationMissing,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.store import load_slot, save_slot


def raw(version, extra=None):
    data = {"manifest": {"schema_version": version, "world_id": "w"}, "inner": {"items": [1]}}
    if extra:
        data.update(extra)
    return data


def touch_nested(data, context):
    data["inner"]["items"].append(2)
    return data


# migrate

def test_migrate_does_not_mutate_nested_input_with_a_one_step_chain():
    data = raw(1)
    before = copy.deepcopy(data)
    result = migrate(data, registry={1: touch_nested}, current_version=2)
    assert data == before
    assert result["inner"]["items"] == [1, 2]


def test_migrate_does_not_mutate_nested_input_with_two_steps():
    data = raw(0)
    before = copy.deepcopy(data)
    migrate(data, registry={0: touch_nested, 1: touch_nested}, current_version=2)
    assert data == before


def test_save_too_new_message_names_both_versions():
    with pytest.raises(SaveTooNew) as error:
        migrate(raw(7), current_version=3)
    assert "7" in str(error.value)
    assert "3" in str(error.value)


def test_missing_step_message_names_the_version():
    with pytest.raises(MigrationMissing) as error:
        migrate(raw(1), registry={}, current_version=2)
    assert "1" in str(error.value)


def test_context_required_message_names_the_version():
    with pytest.raises(MigrationContextRequired) as error:
        migrate(raw(8))
    assert "8" in str(error.value)


def test_migrate_stamps_each_step_version():
    result = migrate(raw(0), registry={0: lambda d, c: d, 1: lambda d, c: d}, current_version=2)
    assert result["manifest"]["schema_version"] == 2


# load_slot: ошибки

def test_missing_slot_error_names_the_folder(saves):
    with pytest.raises(FileNotFoundError) as error:
        load_slot(saves, "w1", "auto")
    assert "w1" in str(error.value)
    assert "auto" in str(error.value)


def test_too_new_slot_error_names_both_versions(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    with pytest.raises(SaveTooNew) as error:
        load_slot(saves, "w1", "auto", current_version=1)
    assert "1" in str(error.value)
    assert str(bundle.manifest.schema_version) in str(error.value)


def break_hero(folder):
    path = next((folder / "heroes").glob("*/hero.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["sheet"]["species_id"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")


def test_invalid_slot_error_has_header_and_field_lines(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    break_hero(folder)
    with pytest.raises(ValueError) as error:
        load_slot(saves, "w1", "auto")
    text = str(error.value)
    assert text.startswith("сейв w1/auto (версия ")
    assert "не проходит проверку:\n" in text
    assert "поле heroes.0.sheet.species_id: " in text


def test_invalid_slot_error_has_one_line_per_problem(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    path = next((folder / "heroes").glob("*/hero.json"))
    data = json.loads(path.read_text(encoding="utf-8"))
    del data["sheet"]["species_id"]
    del data["sheet"]["abilities"]
    path.write_text(json.dumps(data, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError) as error:
        load_slot(saves, "w1", "auto")
    lines = str(error.value).split("\n")
    assert len([line for line in lines if line.startswith("поле ")]) == 2


def test_slot_of_another_world_is_refused_with_the_world_id(saves, bundle):
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    (saves / "w1").rename(saves / "other")
    with pytest.raises(ValueError) as error:
        load_slot(saves, "other", "auto")
    assert "'other'" in str(error.value)


# load_slot: переписанный слот несёт версию движка

def test_rewritten_slot_has_the_version_of_the_current_version_argument(saves, bundle):
    folder = save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    manifest_path = folder / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["schema_version"] = 1
    manifest_path.write_text(json.dumps(manifest, ensure_ascii=False), encoding="utf-8")
    load_slot(
        saves, "w1", "auto", migrations={1: lambda data, context: data}, current_version=2,
        backup_ts="20260101T000000Z",
    )
    rewritten = json.loads(manifest_path.read_text(encoding="utf-8"))
    assert rewritten["schema_version"] == 2
