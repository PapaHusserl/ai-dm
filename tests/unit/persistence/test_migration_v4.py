# Ожидаемый API: ai_dm.persistence.migrations.m0004_v3_to_v4 (следопыт 2-5,
# docs/decisions/ranger-2-5-plan.md, разд. 4 п. 6)
#   migrate_v3_to_v4(data: dict) -> dict  -- чистое dict -> dict, вход не мутирует; schema_version
#       ставит фреймворк migrate(); MIGRATIONS[3] is migrate_v3_to_v4; CURRENT_SCHEMA_VERSION == 4.
#       Миграция заморожена в v4: не импортирует модели ai_dm.state.* (литералы заморожены).
#   Правила: у каждого героя sheet.skill_expertise = [], sheet.languages = [],
#       sheet.feature_options = {}, companion = None (setdefault: уже заданное не трогается);
#       всё остальное не меняется.
#   Фикстура tests/fixtures/saves/v3/ -- слот auto мира old_world (сейв v2-фикстуры в формате v3,
#       один герой Арн-воин без новых полей).
import ast
import copy
import json
import shutil
from pathlib import Path

from persist_kit import load_slot

from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    MigrationContext,
    migrate,
)
from ai_dm.persistence.migrations.m0004_v3_to_v4 import migrate_v3_to_v4
from ai_dm.persistence.store import save_slot
from ai_dm.state.hero import Companion
from ai_dm.state.save import SaveBundle

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V3 = FIXTURES / "v3"
FIXTURE_V2 = FIXTURES / "v2"
BACKUP_TS = "20260101T000000Z"
SAVED_AT = "2026-01-01T12:00:00Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0004_v3_to_v4.py"
)


def tree(folder):
    return {
        p.relative_to(folder).as_posix(): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file()
    }


def install(saves, fixture, slot="auto"):
    target = saves / "old_world" / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def raw_v3_hero(**sheet):
    return {
        "id": "hero", "ordinal": 1, "name": "Грей",
        "sheet": {"species_id": "human", "class_id": "ranger", "level": 3, **sheet},
    }


def raw_v3(heroes=()):
    return {
        "manifest": {"schema_version": 3, "world_id": "old_world"},
        "world": {"world_id": "old_world"},
        "heroes": list(heroes),
        "session": {"turn_seq": 2},
    }


# реестр

def test_registry_has_step_from_v3():
    assert MIGRATIONS[3] is migrate_v3_to_v4
    assert CURRENT_SCHEMA_VERSION >= 4


def test_framework_sets_schema_version_four():
    assert migrate(raw_v3(), current_version=4)["manifest"]["schema_version"] == 4


def test_already_v4_dict_is_not_migrated_again():
    data = raw_v3()
    data["manifest"]["schema_version"] = 4
    assert migrate(data, current_version=4) == data


def test_migrate_v3_to_v4_does_not_mutate_input():
    data = raw_v3([raw_v3_hero()])
    before = copy.deepcopy(data)
    migrate_v3_to_v4(data)
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

def test_new_hero_fields_are_empty():
    hero = migrate_v3_to_v4(raw_v3([raw_v3_hero()]))["heroes"][0]
    assert hero["sheet"]["skill_expertise"] == []
    assert hero["sheet"]["languages"] == []
    assert hero["sheet"]["feature_options"] == {}
    assert hero["companion"] is None


def test_every_hero_gets_the_fields():
    data = raw_v3([raw_v3_hero(), {**raw_v3_hero(), "id": "second", "ordinal": 2}])
    heroes = migrate_v3_to_v4(data)["heroes"]
    assert [h["companion"] for h in heroes] == [None, None]
    assert all(h["sheet"]["skill_expertise"] == [] for h in heroes)


def test_existing_values_are_not_overwritten():
    data = raw_v3([raw_v3_hero(skill_expertise=["survival"])])
    data["heroes"][0]["companion"] = {"name": "Акела", "kind": "волк", "notes": ""}
    hero = migrate_v3_to_v4(data)["heroes"][0]
    assert hero["sheet"]["skill_expertise"] == ["survival"]
    assert hero["companion"]["name"] == "Акела"


def test_other_hero_and_session_fields_stay():
    result = migrate_v3_to_v4(raw_v3([raw_v3_hero()]))
    assert result["heroes"][0]["name"] == "Грей"
    assert result["heroes"][0]["sheet"]["level"] == 3
    assert result["session"] == {"turn_seq": 2}
    assert result["world"] == {"world_id": "old_world"}


def test_world_without_heroes_is_fine():
    assert migrate_v3_to_v4(raw_v3())["heroes"] == []


# фикстура v3 на диске

def test_fixture_v3_is_stage3_format():
    manifest = json.loads((FIXTURE_V3 / "manifest.json").read_text(encoding="utf-8"))
    hero_file = next((FIXTURE_V3 / "heroes").glob("*/hero.json"))
    hero = json.loads(hero_file.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 3
    assert "skill_expertise" not in hero["sheet"]
    assert "companion" not in hero


def test_load_v3_returns_current_bundle_with_empty_new_fields(saves):
    install(saves, FIXTURE_V3)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    hero = bundle.heroes[0]
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert hero.sheet.skill_expertise == []
    assert hero.sheet.languages == []
    assert hero.sheet.feature_choices == {}
    assert hero.companions == []


def test_load_v3_keeps_hero_world_and_session(saves):
    install(saves, FIXTURE_V3)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert [h.id for h in bundle.heroes] == ["hero"]
    assert bundle.heroes[0].name == "Арн"
    assert bundle.heroes[0].sheet.class_id == "fighter"
    assert "grakh" in bundle.world.npcs
    assert bundle.session.turn_seq == 17


def test_load_v3_matches_chain_from_v2(saves, tmp_path):
    install(saves, FIXTURE_V3)
    from_v3 = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    other = tmp_path / "other"
    install(other, FIXTURE_V2)
    from_v2 = load_slot(other, "old_world", "auto", backup_ts=BACKUP_TS)
    assert from_v3 == from_v2


def test_load_v3_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V3)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v3-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V3)


def test_load_v3_rewrites_slot_as_v4(saves):
    folder = install(saves, FIXTURE_V3)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    hero_file = next((folder / "heroes").glob("*/hero.json"))
    hero = json.loads(hero_file.read_text(encoding="utf-8"))
    assert manifest["schema_version"] == CURRENT_SCHEMA_VERSION
    assert hero["sheet"]["skill_expertise"] == []
    assert hero["companions"] == []


def test_load_v3_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V3)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_load_v3_does_not_touch_fixture_itself(saves):
    before = tree(FIXTURE_V3)
    install(saves, FIXTURE_V3)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert tree(FIXTURE_V3) == before


def test_resave_of_migrated_v3_is_byte_stable(saves):
    install(saves, FIXTURE_V3)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    save_slot(saves, bundle, "manual-a", saved_at=SAVED_AT)
    first = tree(saves / "old_world" / "slots" / "manual-a")
    again = load_slot(saves, "old_world", "manual-a", backup_ts=BACKUP_TS)
    save_slot(saves, again, "manual-a", saved_at=SAVED_AT)
    assert tree(saves / "old_world" / "slots" / "manual-a") == first


def test_ranger_with_companion_survives_save_and_load(saves):
    install(saves, FIXTURE_V3)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    hero = bundle.heroes[0]
    hero.sheet.skill_expertise = ["survival"]
    hero.sheet.feature_choices = {"hunters_prey": ["colossus_slayer"]}
    hero.companions = [Companion(name="Акела", kind="волк", notes="след")]
    save_slot(saves, bundle, "manual-b", saved_at=SAVED_AT)
    loaded = load_slot(saves, "old_world", "manual-b", backup_ts=BACKUP_TS)
    assert loaded.heroes[0].companions == hero.companions
    assert loaded.heroes[0].sheet.skill_expertise == ["survival"]
    assert loaded.heroes[0].sheet.feature_choices == {"hunters_prey": ["colossus_slayer"]}


# цепочка до v4

def test_load_v2_chain_reaches_v4_with_single_backup(saves):
    install(saves, FIXTURE_V2)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].companions == []
    backups = sorted((saves / "old_world" / "backups").iterdir())
    assert [b.name for b in backups] == [f"auto-v2-{BACKUP_TS}"]


def test_migrated_dict_validates_as_current_bundle():
    data = migrate(
        {
            "manifest": {"engine_version": "0.0.1", "world_id": "old_world", "campaign_id": None,
                         "slot": "auto", "saved_at": "2025-12-01T10:00:00Z",
                         "current_hero_id": None},
            "world": {"world_id": "old_world",
                      "rng": {"algo": "pcg32", "seed": 7, "state": 5, "inc": 109, "draws": 0}},
            "session": {"current_scene": {"id": "tavern"}},
        },
        context=MigrationContext(item_cost={}),
    )
    assert SaveBundle.model_validate(data).manifest.schema_version == CURRENT_SCHEMA_VERSION
