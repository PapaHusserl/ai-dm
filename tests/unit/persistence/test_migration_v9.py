# К0а (docs/K0-PLAN.md, A2, A7): миграция v8 -> v9 (классы списком, концентрация объектом,
# спутники списком, pending_level, equipment, кости хитов hit_dice:dN).
# Ожидаемый API: ai_dm.persistence.migrations.m0009_v8_to_v9
#   migrate_v8_to_v9(data, context) -> dict (чистое dict -> dict, вход не мутирует),
#   хелперы migrate_sheet(sheet), migrate_creature(creature, context), migrate_hero(hero, context);
#   MIGRATIONS[8] is migrate_v8_to_v9; CURRENT_SCHEMA_VERSION == 9; контекст обязателен;
#   MigrationContext.class_hit_die / spell_level заполняются в from_registry.
#   Фикстура: tests/fixtures/saves/v8 -- слот auto мира old_world (сгенерирован движком v8 из v7).
#   Нейтральность: golden-снимки tests/golden/k0_* (сняты на main до партии) совпадают.
import ast
import copy
import json
import shutil
from pathlib import Path

import pytest
from game_kit import core_dump, make_app, scripted, text_step
from k0_golden_kit import (
    GOLDEN,
    dragon_registry,
    load_dragon,
    menu_snapshot,
    old_pools,
    sheet_data_snapshot,
    sheet_snapshot,
)
from persist_kit import load_slot

from ai_dm.content.loader import load_registry
from ai_dm.persistence.migrations import (
    CURRENT_SCHEMA_VERSION,
    MIGRATIONS,
    MigrationContext,
    MigrationContextRequired,
    SaveTooNew,
    migrate,
)
from ai_dm.persistence.migrations.m0009_v8_to_v9 import (
    migrate_creature,
    migrate_hero,
    migrate_sheet,
    migrate_v8_to_v9,
)
from ai_dm.persistence.store import save_slot

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V8 = FIXTURES / "v8"
BACKUP_TS = "20260101T000000Z"
MIGRATION_FILE = (
    Path(__file__).resolve().parents[3]
    / "src" / "ai_dm" / "persistence" / "migrations" / "m0009_v8_to_v9.py"
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


def context(**fields):
    base = {
        "class_hit_die": {"ranger": 10, "fighter": 10, "cleric": 8, "wizard": 6},
        "spell_level": {"hunters_mark": 1, "fireball": 3, "light": 0},
    }
    base.update(fields)
    return MigrationContext(**base)


def raw_sheet(**fields):
    sheet = {
        "species_id": "human", "class_id": "ranger", "subclass_id": "beast_master", "level": 3,
        "abilities": {"str": 12}, "spells_known": ["fog_cloud"],
        "spells_prepared": ["hunters_mark", "cure_wounds"],
        "feature_options": {"hunters_prey": "colossus_slayer"},
    }
    sheet.update(fields)
    return sheet


def raw_creature(**fields):
    creature = {
        "hp_current": 20, "hp_max": 20, "resources": {"hit_dice": {"current": 2, "max": 3}},
        "concentration": None,
    }
    creature.update(fields)
    return creature


def raw_hero(**fields):
    hero = {
        "id": "h1", "name": "Грей", "sheet": raw_sheet(), "creature": raw_creature(),
        "companion": {"kind": "волк", "name": "Акела", "notes": ""},
    }
    hero.update(fields)
    return hero


def raw_v8(heroes=None, npcs=None, combat=None):
    data = {
        "manifest": {"schema_version": 8, "world_id": "old_world"},
        "world": {"world_id": "old_world", "npcs": npcs if npcs is not None else {}},
        "heroes": heroes if heroes is not None else [raw_hero()],
        "session": {"turn_seq": 2, "active_combat": combat},
    }
    return data


def hero_of(data):
    return data["heroes"][0]


# реестр и фреймворк

def test_registry_has_step_from_v8():
    assert MIGRATIONS[8] is migrate_v8_to_v9
    assert CURRENT_SCHEMA_VERSION == 9


def test_framework_sets_schema_version_nine():
    assert migrate(raw_v8(), context=context())["manifest"]["schema_version"] == 9


def test_chain_v8_to_v9_needs_context():
    with pytest.raises(MigrationContextRequired):
        migrate(raw_v8())


def test_v8_to_v8_is_not_touched():
    assert migrate(raw_v8(), current_version=8) == raw_v8()


def test_already_v9_dict_is_not_migrated_again():
    data = raw_v8()
    data["manifest"]["schema_version"] = 9
    assert migrate(data) == data


def test_engine_v8_refuses_a_v9_dict():
    data = raw_v8()
    data["manifest"]["schema_version"] = 9
    with pytest.raises(SaveTooNew):
        migrate(data, current_version=8)


def test_migrate_v8_to_v9_does_not_mutate_input():
    data = raw_v8(
        npcs={"n": {"id": "n", "creature": raw_creature(concentration="hunters_mark")}},
        combat={"participants": [{"ref": "n", "creature": raw_creature()}]},
    )
    before = copy.deepcopy(data)
    migrate_v8_to_v9(data, context())
    assert data == before


def test_migration_does_not_import_state_or_content_models():
    names = []
    for node in ast.walk(ast.parse(MIGRATION_FILE.read_text(encoding="utf-8"))):
        if isinstance(node, ast.Import):
            names += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            names.append(node.module or "")
    assert not [n for n in names if n.startswith(("ai_dm.state", "ai_dm.content"))]


# MigrationContext.from_registry

def test_context_from_registry_has_class_hit_dice():
    result = MigrationContext.from_registry(load_registry())
    assert result.class_hit_die["ranger"] == 10
    assert result.class_hit_die["wizard"] == 6
    assert result.class_hit_die["cleric"] == 8


def test_context_from_registry_has_one_hit_die_per_class():
    registry = load_registry()
    result = MigrationContext.from_registry(registry)
    assert result.class_hit_die == {c.id: c.hit_die for c in registry.all("class")}


def test_context_from_registry_has_spell_circles():
    result = MigrationContext.from_registry(load_registry())
    assert result.spell_level["hunters_mark"] == 1


def test_context_from_registry_has_every_spell():
    registry = load_registry()
    result = MigrationContext.from_registry(registry)
    assert result.spell_level == {s.id: s.level for s in registry.all("spell")}


def test_context_keeps_item_costs_and_trade():
    result = MigrationContext.from_registry(load_registry(), npc_trade={"n": "smith"})
    assert result.npc_trade == {"n": "smith"}
    assert result.item_cost["longsword"] > 0


def test_context_defaults_are_empty_dicts():
    result = MigrationContext()
    assert (result.class_hit_die, result.spell_level) == ({}, {})


# sheet

def test_sheet_scalars_become_classes():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert sheet["classes"] == [{"class_id": "ranger", "level": 3, "subclass_id": "beast_master"}]
    assert not {"class_id", "level", "subclass_id"} & set(sheet)


def test_sheet_without_subclass_gets_none():
    sheet = raw_sheet(subclass_id=None)
    migrate_sheet(sheet)
    assert sheet["classes"][0]["subclass_id"] is None


def test_sheet_without_subclass_key_gets_none():
    sheet = raw_sheet()
    del sheet["subclass_id"]
    migrate_sheet(sheet)
    assert sheet["classes"][0]["subclass_id"] is None


def test_sheet_level_history_repeats_class_by_level():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert sheet["level_history"] == ["ranger", "ranger", "ranger"]


def test_sheet_level_one_history_has_one_entry():
    sheet = raw_sheet(level=1)
    migrate_sheet(sheet)
    assert sheet["level_history"] == ["ranger"]


def test_sheet_spells_go_under_the_class():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert sheet["spells_known"] == {"ranger": ["fog_cloud"]}
    assert sheet["spells_prepared"] == {"ranger": ["hunters_mark", "cure_wounds"]}


def test_sheet_empty_spells_give_empty_class_key():
    sheet = raw_sheet(spells_known=[], spells_prepared=[])
    migrate_sheet(sheet)
    assert sheet["spells_known"] == {"ranger": []}
    assert sheet["spells_prepared"] == {"ranger": []}


def test_sheet_feature_options_become_feature_choices_lists():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert sheet["feature_choices"] == {"hunters_prey": ["colossus_slayer"]}
    assert "feature_options" not in sheet


def test_sheet_empty_feature_options_give_empty_choices():
    sheet = raw_sheet(feature_options={})
    migrate_sheet(sheet)
    assert sheet["feature_choices"] == {}


def test_sheet_gets_empty_always_prepared():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert sheet["spells_always_prepared"] == []


def test_sheet_without_level_key_is_level_one():
    sheet = raw_sheet()
    del sheet["level"]
    migrate_sheet(sheet)
    assert sheet["classes"][0]["level"] == 1
    assert sheet["level_history"] == ["ranger"]


def test_sheet_without_feature_options_key_gives_empty_choices():
    sheet = raw_sheet()
    del sheet["feature_options"]
    migrate_sheet(sheet)
    assert sheet["feature_choices"] == {}


def test_sheet_without_spell_keys_gives_empty_class_lists():
    sheet = raw_sheet()
    del sheet["spells_known"]
    del sheet["spells_prepared"]
    migrate_sheet(sheet)
    assert sheet["spells_known"] == {"ranger": []}
    assert sheet["spells_prepared"] == {"ranger": []}


def test_sheet_other_fields_stay():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    assert (sheet["species_id"], sheet["abilities"]) == ("human", {"str": 12})


def test_sheet_migration_is_idempotent():
    sheet = raw_sheet()
    migrate_sheet(sheet)
    once = copy.deepcopy(sheet)
    migrate_sheet(sheet)
    assert sheet == once


# creature

def test_concentration_string_becomes_object_with_spell_circle():
    creature = raw_creature(concentration="fireball")
    migrate_creature(creature, context())
    assert creature["concentration"] == {"spell_id": "fireball", "circle": 3, "until_s": None}


def test_concentration_on_level_one_spell():
    creature = raw_creature(concentration="hunters_mark")
    migrate_creature(creature, context())
    assert creature["concentration"] == {"spell_id": "hunters_mark", "circle": 1, "until_s": None}


def test_concentration_on_cantrip_keeps_circle_zero():
    creature = raw_creature(concentration="light")
    migrate_creature(creature, context())
    assert creature["concentration"]["circle"] == 0


def test_unknown_concentration_spell_is_circle_one_with_report():
    ctx = context()
    creature = raw_creature(concentration="homebrew_spell")
    migrate_creature(creature, ctx)
    assert creature["concentration"] == {"spell_id": "homebrew_spell", "circle": 1, "until_s": None}
    assert len(ctx.report) == 1
    assert "homebrew_spell" in ctx.report[0]


def test_known_concentration_spell_makes_no_report():
    ctx = context()
    migrate_creature(raw_creature(concentration="fireball"), ctx)
    assert ctx.report == []


def test_no_concentration_stays_none():
    ctx = context()
    creature = raw_creature()
    migrate_creature(creature, ctx)
    assert creature["concentration"] is None
    assert ctx.report == []


def test_creature_without_concentration_key_gets_none():
    creature = {"hp_current": 1, "hp_max": 1}
    migrate_creature(creature, context())
    assert creature["concentration"] is None


def test_creature_gets_empty_temp_form():
    creature = raw_creature()
    migrate_creature(creature, context())
    assert creature["temp_form"] is None


def test_creature_migration_is_idempotent():
    creature = raw_creature(concentration="fireball")
    migrate_creature(creature, context())
    once = copy.deepcopy(creature)
    migrate_creature(creature, context())
    assert creature == once


# hero

def test_hero_companion_becomes_list_of_one():
    hero = raw_hero()
    migrate_hero(hero, context())
    assert hero["companions"] == [{"kind": "волк", "name": "Акела", "notes": ""}]
    assert "companion" not in hero


def test_hero_companion_none_becomes_empty_list():
    hero = raw_hero(companion=None)
    migrate_hero(hero, context())
    assert hero["companions"] == []


def test_hero_without_companion_key_gets_empty_list():
    hero = raw_hero()
    del hero["companion"]
    migrate_hero(hero, context())
    assert hero["companions"] == []


def test_hero_gets_attuned_and_pending_level():
    hero = raw_hero()
    migrate_hero(hero, context())
    assert hero["attuned"] == []
    assert hero["pending_level"] is None


def test_hero_hit_dice_pool_is_renamed_by_class_die():
    hero = raw_hero()
    migrate_hero(hero, context())
    assert hero["creature"]["resources"] == {"hit_dice:d10": {"current": 2, "max": 3}}


def test_hero_hit_dice_uses_the_first_class_die():
    hero = raw_hero(sheet=raw_sheet(class_id="wizard", subclass_id=None))
    migrate_hero(hero, context())
    assert "hit_dice:d6" in hero["creature"]["resources"]
    assert "hit_dice" not in hero["creature"]["resources"]


def test_hero_cleric_hit_die_is_d8():
    hero = raw_hero(sheet=raw_sheet(class_id="cleric", subclass_id=None))
    migrate_hero(hero, context())
    assert "hit_dice:d8" in hero["creature"]["resources"]


def test_hero_unknown_class_gets_d8_and_report():
    ctx = context()
    hero = raw_hero(sheet=raw_sheet(class_id="artificer", subclass_id=None))
    migrate_hero(hero, ctx)
    assert hero["creature"]["resources"] == {"hit_dice:d8": {"current": 2, "max": 3}}
    assert len(ctx.report) == 1
    assert "artificer" in ctx.report[0]


def test_hero_known_class_makes_no_report():
    ctx = context()
    migrate_hero(raw_hero(), ctx)
    assert ctx.report == []


def test_hero_other_pools_and_their_order_stay():
    creature = raw_creature(resources={
        "favored_enemy": {"current": 2, "max": 2},
        "hit_dice": {"current": 3, "max": 3},
        "spell_slot:1": {"current": 1, "max": 3},
    })
    hero = raw_hero(creature=creature)
    migrate_hero(hero, context())
    assert list(hero["creature"]["resources"]) == ["favored_enemy", "hit_dice:d10", "spell_slot:1"]
    assert hero["creature"]["resources"]["spell_slot:1"] == {"current": 1, "max": 3}


def test_hero_creature_without_resources_key_is_fine():
    creature = {"hp_current": 1, "hp_max": 1}
    hero = raw_hero(creature=creature)
    migrate_hero(hero, context())
    assert "hit_dice:d10" not in hero["creature"].get("resources", {})


def test_hero_without_hit_dice_pool_gets_none_added():
    hero = raw_hero(creature=raw_creature(resources={}))
    migrate_hero(hero, context())
    assert hero["creature"]["resources"] == {}


def test_hero_concentration_string_is_migrated():
    hero = raw_hero(creature=raw_creature(concentration="hunters_mark"))
    migrate_hero(hero, context())
    assert hero["creature"]["concentration"]["spell_id"] == "hunters_mark"
    assert hero["creature"]["concentration"]["circle"] == 1


def test_hero_migration_is_idempotent():
    hero = raw_hero()
    migrate_hero(hero, context())
    once = copy.deepcopy(hero)
    migrate_hero(hero, context())
    assert hero == once


# мир и сессия

def test_npcs_get_empty_equipment():
    data = migrate_v8_to_v9(raw_v8(npcs={"a": {"id": "a"}, "b": {"id": "b"}}), context())
    assert [n["equipment"] for n in data["world"]["npcs"].values()] == [None, None]


def test_npc_without_creature_has_no_creature_key_added():
    data = migrate_v8_to_v9(raw_v8(npcs={"a": {"id": "a"}}), context())
    assert "creature" not in data["world"]["npcs"]["a"]


def test_npc_creature_none_is_fine():
    data = migrate_v8_to_v9(raw_v8(npcs={"a": {"id": "a", "creature": None}}), context())
    assert data["world"]["npcs"]["a"]["creature"] is None


def test_npc_creature_concentration_string_is_migrated():
    npc = {"id": "a", "creature": raw_creature(concentration="fireball")}
    data = migrate_v8_to_v9(raw_v8(npcs={"a": npc}), context())
    creature = data["world"]["npcs"]["a"]["creature"]
    assert creature["concentration"] == {"spell_id": "fireball", "circle": 3, "until_s": None}
    assert creature["temp_form"] is None


def test_npc_creature_without_concentration_is_migrated_too():
    npc = {"id": "a", "creature": raw_creature()}
    data = migrate_v8_to_v9(raw_v8(npcs={"a": npc}), context())
    assert data["world"]["npcs"]["a"]["creature"]["concentration"] is None


def test_npc_creature_resources_are_not_renamed():
    npc = {"id": "a", "creature": raw_creature()}
    data = migrate_v8_to_v9(raw_v8(npcs={"a": npc}), context())
    assert "hit_dice" in data["world"]["npcs"]["a"]["creature"]["resources"]


def test_existing_npc_equipment_is_kept():
    equipment = {"armor": "chain_mail", "shield": None, "weapons": []}
    data = migrate_v8_to_v9(raw_v8(npcs={"a": {"id": "a", "equipment": equipment}}), context())
    assert data["world"]["npcs"]["a"]["equipment"] == equipment


def test_participants_get_empty_equipment():
    combat = {"participants": [{"ref": "h1"}, {"ref": "g1"}]}
    data = migrate_v8_to_v9(raw_v8(combat=combat), context())
    participants = data["session"]["active_combat"]["participants"]
    assert [p["equipment"] for p in participants] == [None, None]


def test_participant_creature_concentration_is_migrated():
    combat = {"participants": [{"ref": "g1", "creature": raw_creature(concentration="fireball")}]}
    data = migrate_v8_to_v9(raw_v8(combat=combat), context())
    creature = data["session"]["active_combat"]["participants"][0]["creature"]
    assert creature["concentration"]["circle"] == 3


def test_active_combat_without_participants_key_is_fine():
    data = migrate_v8_to_v9(raw_v8(combat={"id": "c1"}), context())
    assert data["session"]["active_combat"] == {"id": "c1"}


def test_participant_without_creature_is_fine():
    data = migrate_v8_to_v9(raw_v8(combat={"participants": [{"ref": "h1"}]}), context())
    assert "creature" not in data["session"]["active_combat"]["participants"][0]


def test_no_active_combat_is_fine():
    data = migrate_v8_to_v9(raw_v8(combat=None), context())
    assert data["session"]["active_combat"] is None


def test_session_without_active_combat_key_is_fine():
    data = raw_v8()
    del data["session"]["active_combat"]
    assert "active_combat" not in migrate_v8_to_v9(data, context())["session"]


def test_dict_without_world_session_heroes_is_fine():
    data = {"manifest": {"schema_version": 8, "world_id": "w"}}
    assert migrate(data, context=context())["manifest"]["schema_version"] == 9


def test_other_world_and_session_fields_stay():
    data = migrate_v8_to_v9(raw_v8(), context())
    assert data["world"]["world_id"] == "old_world"
    assert data["session"]["turn_seq"] == 2


def test_two_heroes_both_migrate():
    data = migrate_v8_to_v9(raw_v8(heroes=[raw_hero(), raw_hero(id="h2")]), context())
    assert [h["sheet"]["classes"][0]["class_id"] for h in data["heroes"]] == ["ranger", "ranger"]


def test_whole_dict_migration_is_idempotent():
    once = migrate_v8_to_v9(raw_v8(npcs={"a": {"id": "a"}}), context())
    assert migrate_v8_to_v9(once, context()) == once


# фикстура v8 и загрузка слота

def test_fixture_v8_is_v8_format():
    manifest = json.loads((FIXTURE_V8 / "manifest.json").read_text(encoding="utf-8"))
    hero = json.loads((FIXTURE_V8 / "heroes" / "01_арн" / "hero.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 8
    assert hero["sheet"]["class_id"] == "fighter"
    assert "classes" not in hero["sheet"]


def test_load_v8_returns_current_bundle(saves):
    install(saves, FIXTURE_V8)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.heroes[0].name == "Арн"


def test_load_v8_hero_has_classes_and_hit_dice(saves):
    install(saves, FIXTURE_V8)
    hero = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).heroes[0]
    assert (hero.sheet.class_id, hero.sheet.level) == ("fighter", 1)
    assert hero.sheet.level_history == ["fighter"]
    assert "hit_dice:d10" in hero.creature.resources
    assert "hit_dice" not in hero.creature.resources


def test_load_v8_makes_byte_exact_backup(saves):
    install(saves, FIXTURE_V8)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v8-{BACKUP_TS}"
    assert tree(backup) == tree(FIXTURE_V8)


def test_load_v8_rewrites_slot_as_v9(saves):
    folder = install(saves, FIXTURE_V8)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    hero = json.loads((folder / "heroes" / "01_арн" / "hero.json").read_text(encoding="utf-8"))
    assert manifest["schema_version"] == 9
    assert hero["sheet"]["classes"] == [{"class_id": "fighter", "level": 1, "subclass_id": None}]
    assert "class_id" not in hero["sheet"]
    assert "companion" not in hero


def test_load_v8_twice_makes_no_second_backup(saves):
    install(saves, FIXTURE_V8)
    first = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = load_slot(saves, "old_world", "auto", backup_ts="20260202T000000Z")
    assert second == first
    assert len(list((saves / "old_world" / "backups").iterdir())) == 1


def test_resave_after_load_is_byte_stable(saves):
    folder = install(saves, FIXTURE_V8)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_reading_prepared_of_does_not_change_serialization(saves):
    folder = install(saves, FIXTURE_V8)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    migrated = tree(folder)
    bundle.heroes[0].sheet.prepared_of()
    bundle.heroes[0].sheet.known_of()
    save_slot(saves, bundle, "auto", saved_at=bundle.manifest.saved_at)
    assert tree(folder) == migrated


def test_v9_slot_is_too_new_for_engine_v8(saves):
    install(saves, FIXTURE_V8)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "auto", current_version=8)


def test_load_without_context_of_v8_slot_is_refused(saves):
    from ai_dm.persistence.store import load_slot as raw_load_slot

    install(saves, FIXTURE_V8)
    with pytest.raises(MigrationContextRequired):
        raw_load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)


@pytest.mark.parametrize(
    "name", ["v0", "v1", "v2", "v3", "v4", "v5", "v5_combat", "v6", "v7", "v8"],
)
def test_old_fixture_chain_reaches_v9(saves, name):
    install(saves, FIXTURES / name)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.manifest.schema_version == 9


def test_v4_dragon_chain_reaches_v9_with_ranger_classes(saves):
    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    bundle = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS)
    sheet = bundle.heroes[0].sheet
    assert bundle.manifest.schema_version == 9
    assert [(c.class_id, c.level, c.subclass_id) for c in sheet.classes] == [
        ("ranger", 3, "beast_master")
    ]
    assert sheet.level_history == ["ranger"] * 3
    assert len(bundle.heroes[0].companions) == 1


def test_v4_dragon_spells_move_under_ranger(saves):
    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    sheet = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS).heroes[0].sheet
    assert set(sheet.spells_known) == {"ranger"}
    assert sheet.spells_prepared["ranger"] == sheet.prepared_of()
    assert sheet.prepared_of() == [
        "cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud"
    ]


def test_v4_dragon_hit_dice_pool_is_d10(saves):
    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    resources = load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS).heroes[0].creature.resources
    assert resources["hit_dice:d10"].max == 3
    assert "hit_dice" not in resources


def test_v4_dragon_load_gives_no_migration_warning(saves):
    install(saves, FIXTURES / "v4_dragon", world_id="dd")
    ctx = MigrationContext.from_registry(load_registry())
    from ai_dm.persistence.store import load_slot as raw_load_slot

    raw_load_slot(saves, "dd", "auto", backup_ts=BACKUP_TS, context=ctx)
    assert not [line for line in ctx.report if "концентрац" in line or "кость" in line]


def test_v5_combat_fixture_loads_with_no_active_combat_equipment_problem(saves):
    install(saves, FIXTURES / "v5_combat")
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    combat = bundle.session.active_combat
    for participant in combat.participants if combat else []:
        assert participant.equipment is None


# нейтральность (A7): golden-снимки сняты на main до партии, v4_dragon = Грей из живого мира

def test_dragon_sheet_text_is_the_same_as_on_main(tmp_path):
    bundle = load_dragon(tmp_path / "saves")
    expected = (GOLDEN / "k0_sheet_v4_dragon.txt").read_text(encoding="utf-8")
    assert sheet_snapshot(dragon_registry(), tmp_path / "app", bundle) == expected


def test_dragon_sheet_data_slots_and_pools_are_the_same_as_on_main(tmp_path):
    bundle = load_dragon(tmp_path / "saves")
    expected = (GOLDEN / "k0_sheet_data_v4_dragon.json").read_text(encoding="utf-8")
    assert sheet_data_snapshot(dragon_registry(), bundle) == expected


def test_dragon_level_menu_is_the_same_as_on_main(tmp_path):
    bundle = load_dragon(tmp_path / "saves")
    expected = (GOLDEN / "k0_level_menu_v4_dragon.json").read_text(encoding="utf-8")
    assert menu_snapshot(dragon_registry(), bundle.heroes[0]) == expected


def test_golden_pools_keep_old_key_after_normalization():
    assert old_pools({"hit_dice:d10": 1, "spell_slot:1": 2}) == {"hit_dice": 1, "spell_slot:1": 2}


def test_sync_resources_does_not_add_a_second_hit_dice_pool(tmp_path):
    from ai_dm.rules.progression import sync_resources

    registry = dragon_registry()
    hero = load_dragon(tmp_path / "saves").heroes[0]
    before = {key: pool.model_copy() for key, pool in hero.creature.resources.items()}
    sync_resources(hero, registry)
    assert hero.creature.resources == before
    keys = [key for key in hero.creature.resources if key.startswith("hit_dice")]
    assert keys == ["hit_dice:d10"]


def test_one_mock_turn_on_migrated_dragon_keeps_pools_and_class(tmp_path):
    registry = dragon_registry()
    bundle = load_dragon(tmp_path / "saves")
    app = make_app(registry, tmp_path / "play", scripted([text_step("Рассказ.")]), bundle=bundle)
    app.handle("Иду")
    hero = app.bundle.heroes[0]
    assert sorted(hero.creature.resources) == ["favored_enemy", "hit_dice:d10", "spell_slot:1"]
    assert hero.sheet.level == 3
    dump = json.loads(core_dump(app.bundle))
    assert dump["heroes"][0]["sheet"]["classes"][0]["class_id"] == "ranger"
