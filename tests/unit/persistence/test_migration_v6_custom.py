# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 6 и 7): то, что v5 -> v6 добавляет к ценам.
#   world: custom_items = {} и custom_item_seq = 0 (уже заданное не трогается)
#   session.current_scene (если есть): custom_created = 0
#   session.last_combat (если не None): gear = [], gear_looted = True -- бой уже завершён без
#       трофеев, задним числом не выдаём (заданное не трогается); last_combat None остаётся None
#   Вход не мутируется; v6-слот с каталогом, держателем, счётчиком сцены и трофеями боя
#   переживает save -> load без потерь.
import copy
import json
import shutil
from pathlib import Path

import pytest
from persist_kit import load_slot

from ai_dm.persistence.migrations import MigrationContext, SaveTooNew, migrate
from ai_dm.persistence.migrations.m0006_v5_to_v6 import migrate_v5_to_v6
from ai_dm.persistence.store import save_slot
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.world import CustomItem, ItemHolder

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "saves"
FIXTURE_V5 = FIXTURES / "v5"
FIXTURE_V5_COMBAT = FIXTURES / "v5_combat"
BACKUP_TS = "20260101T000000Z"
SAVED_AT = "2026-01-01T12:00:00Z"


def install(saves, fixture, slot="auto", world_id="old_world"):
    target = saves / world_id / "slots" / slot
    shutil.copytree(fixture, target)
    return target


def ctx():
    return MigrationContext(item_cost={})


def raw_v5(scene=None, last_combat=None, world=None):
    return {
        "manifest": {"schema_version": 5, "world_id": "old_world"},
        "world": {"world_id": "old_world"} if world is None else world,
        "heroes": [],
        "session": {"turn_seq": 2, "active_combat": None, "current_scene": scene,
                    "last_combat": last_combat},
    }


def last_combat(**extra):
    return {"defeated": ["goblin"], "looted": False, "lair_location_id": None,
            "hoard_looted": False, **extra}


def migrated(**kwargs):
    return migrate_v5_to_v6(raw_v5(**kwargs), ctx())


# world

def test_world_gets_an_empty_catalog_and_zero_seq():
    world = migrated()["world"]
    assert world["custom_items"] == {}
    assert world["custom_item_seq"] == 0


def test_world_keeps_its_other_fields():
    assert migrated()["world"]["world_id"] == "old_world"


def test_existing_catalog_is_kept():
    item = {"id": "custom_1", "name": "Ключ", "created_s": 0}
    world = {"world_id": "old_world", "custom_items": {"custom_1": item}, "custom_item_seq": 4}
    result = migrated(world=world)["world"]
    assert result["custom_items"] == {"custom_1": item}
    assert result["custom_item_seq"] == 4


def test_every_migration_makes_its_own_catalog():
    first = migrated()["world"]["custom_items"]
    first["custom_1"] = {}
    assert migrated()["world"]["custom_items"] == {}


def test_dict_without_world_is_fine():
    data = raw_v5()
    del data["world"]
    assert "world" not in migrate_v5_to_v6(data, ctx())


def test_dict_without_session_is_fine():
    data = raw_v5()
    del data["session"]
    result = migrate_v5_to_v6(data, ctx())
    assert "session" not in result
    assert result["world"]["custom_items"] == {}


# сцена

def test_scene_gets_a_zero_counter():
    scene = {"id": "scene_1", "started_at_s": 0}
    assert migrated(scene=scene)["session"]["current_scene"]["custom_created"] == 0


def test_existing_scene_counter_is_kept():
    scene = {"id": "scene_1", "started_at_s": 0, "custom_created": 3}
    assert migrated(scene=scene)["session"]["current_scene"]["custom_created"] == 3


def test_no_scene_stays_none():
    assert migrated()["session"]["current_scene"] is None


# last_combat

def test_last_combat_gets_empty_gear_and_is_marked_looted():
    result = migrated(last_combat=last_combat())["session"]["last_combat"]
    assert result["gear"] == []
    assert result["gear_looted"] is True


def test_last_combat_keeps_its_other_fields():
    result = migrated(last_combat=last_combat(looted=True))["session"]["last_combat"]
    assert result["defeated"] == ["goblin"]
    assert result["looted"] is True


def test_no_last_combat_stays_none():
    assert migrated()["session"]["last_combat"] is None


def test_last_combat_key_is_not_created_when_absent():
    data = raw_v5()
    del data["session"]["last_combat"]
    assert "last_combat" not in migrate_v5_to_v6(data, ctx())["session"]


def test_existing_gear_is_kept():
    gear = [{"item_id": "scimitar", "qty": 2, "cost_cp": 250, "quality": "junk"}]
    result = migrated(last_combat=last_combat(gear=gear, gear_looted=False))
    assert result["session"]["last_combat"]["gear"] == gear
    assert result["session"]["last_combat"]["gear_looted"] is False


def test_every_migration_makes_its_own_gear_list():
    first = migrated(last_combat=last_combat())["session"]["last_combat"]["gear"]
    first.append({})
    assert migrated(last_combat=last_combat())["session"]["last_combat"]["gear"] == []


# вход не мутируется, цепочка

def test_input_is_not_mutated():
    data = raw_v5(scene={"id": "s", "started_at_s": 0}, last_combat=last_combat())
    before = copy.deepcopy(data)
    migrate_v5_to_v6(data, ctx())
    assert data == before


def test_framework_chain_adds_the_fields():
    data = raw_v5(scene={"id": "s", "started_at_s": 0}, last_combat=last_combat())
    result = migrate(data, context=ctx())
    assert result["world"]["custom_items"] == {}
    assert result["session"]["current_scene"]["custom_created"] == 0
    assert result["session"]["last_combat"]["gear_looted"] is True


def test_migrating_twice_by_hand_changes_nothing_more():
    once = migrated(scene={"id": "s", "started_at_s": 0}, last_combat=last_combat())
    assert migrate_v5_to_v6(once, ctx()) == once


# фикстуры v5

def test_load_v5_gives_an_empty_catalog(saves):
    install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.world.custom_items == {}
    assert bundle.world.custom_item_seq == 0


def test_load_v5_gives_the_scene_a_zero_counter(saves):
    install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.session.current_scene.custom_created == 0


def test_load_v5_without_last_combat_keeps_none(saves):
    install(saves, FIXTURE_V5)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    assert bundle.session.last_combat is None


def test_load_v5_combat_marks_the_old_fight_as_looted(saves):
    install(saves, FIXTURE_V5_COMBAT)
    last = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS).session.last_combat
    assert last.gear == []
    assert last.gear_looted is True
    assert last.looted is False


def test_load_v5_backup_has_no_new_fields(saves):
    # бэкап слота -- v5 байт в байт, без полей v6
    install(saves, FIXTURE_V5)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    backup = saves / "old_world" / "backups" / f"auto-v5-{BACKUP_TS}"
    world = json.loads((backup / "world" / "world.json").read_text(encoding="utf-8"))
    assert "custom_items" not in world


def test_v5_resave_is_byte_stable_with_the_new_fields(saves):
    install(saves, FIXTURE_V5_COMBAT)
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    slot = saves / "old_world" / "slots" / "auto"
    first = {p.name: p.read_bytes() for p in sorted(slot.rglob("*.json"))}
    load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    second = {p.name: p.read_bytes() for p in sorted(slot.rglob("*.json"))}
    assert first == second


# v6 с кастомными предметами

def loaded_with_items(saves):
    install(saves, FIXTURE_V5_COMBAT)
    bundle = load_slot(saves, "old_world", "auto", backup_ts=BACKUP_TS)
    holder = ItemHolder(
        kind="band", ref="goblin_1", label="Воин-гоблин, банда", location_id="goblin_den",
        since_s=500, qty=2, cost_cp=700,
    )
    bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ от ворот", weight_centilb=50,
        cost_cp=700, quest=True, created_s=100, holder=holder,
    )
    bundle.world.custom_items["custom_2"] = CustomItem(id="custom_2", name="Записка", created_s=200)
    bundle.world.custom_item_seq = 2
    bundle.session.current_scene.custom_created = 2
    bundle.session.last_combat.gear = [
        InventoryEntry(item_id="scimitar", qty=3, cost_cp=250, quality="junk")
    ]
    bundle.session.last_combat.gear_looted = False
    return bundle


def test_v6_save_with_custom_items_loads_the_same_catalog(saves):
    bundle = loaded_with_items(saves)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert again.world.custom_items == bundle.world.custom_items
    assert again.world.custom_item_seq == 2


def test_v6_save_keeps_the_holder(saves):
    bundle = loaded_with_items(saves)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    holder = again.world.custom_items["custom_1"].holder
    assert (holder.kind, holder.ref, holder.label) == ("band", "goblin_1", "Воин-гоблин, банда")
    assert (holder.location_id, holder.since_s, holder.qty, holder.cost_cp) == (
        "goblin_den", 500, 2, 700,
    )
    assert again.world.custom_items["custom_2"].holder is None


def test_v6_save_keeps_the_scene_counter_and_the_gear(saves):
    bundle = loaded_with_items(saves)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    again = load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert again.session.current_scene.custom_created == 2
    assert again.session.last_combat.gear == bundle.session.last_combat.gear
    assert again.session.last_combat.gear_looted is False


def test_v6_save_with_items_is_not_loaded_by_engine_v5(saves):
    bundle = loaded_with_items(saves)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    with pytest.raises(SaveTooNew):
        load_slot(saves, "old_world", "manual-x", current_version=5)


def test_v6_save_with_items_makes_no_backup_on_load(saves):
    bundle = loaded_with_items(saves)
    save_slot(saves, bundle, "manual-x", saved_at=SAVED_AT)
    before = sorted((saves / "old_world" / "backups").iterdir())
    load_slot(saves, "old_world", "manual-x", backup_ts=BACKUP_TS)
    assert sorted((saves / "old_world" / "backups").iterdir()) == before
