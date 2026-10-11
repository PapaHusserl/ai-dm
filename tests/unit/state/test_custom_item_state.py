# Сюжетные предметы, партия А (CUSTOM-ITEMS-PLAN, разд. 1, 5, 6, 7): модели сейва.
#   ai_dm.state.world.CustomItem(id, name, description="", weight_centilb=None (сотые доли фунта),
#       cost_cp=0, quest=False, created_s, holder=None) -- extra=forbid
#   ai_dm.state.world.ItemHolder(kind: npc|band|faction|location, ref, label (<= 80),
#       location_id=None, since_s, qty=1, cost_cp=0) -- extra=forbid
#   WorldState.custom_items: dict[str, CustomItem] (ключ == id), WorldState.custom_item_seq = 0
#   SceneState.custom_created = 0
#   LastCombat.gear: list[InventoryEntry] = [], LastCombat.gear_looted = False
import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.scene import SceneState
from ai_dm.state.session import LastCombat
from ai_dm.state.world import CustomItem, ItemHolder, WorldState


def world():
    return WorldState(world_id="w1", rng=Rng(1).state)


def key_item(**extra):
    return CustomItem(id="custom_1", name="Ржавый ключ", created_s=0, **extra)


def holder(**extra):
    fields = {"kind": "npc", "ref": "npc_klyk", "label": "вожак Клык", "since_s": 10}
    fields.update(extra)
    return ItemHolder(**fields)


# CustomItem

def test_custom_item_defaults():
    item = key_item()
    assert item.description == ""
    assert item.weight_centilb is None
    assert item.cost_cp == 0
    assert item.quest is False
    assert item.holder is None


def test_custom_item_keeps_the_given_fields():
    item = CustomItem(
        id="custom_2", name="Перстень", description="Старый", weight_centilb=10, cost_cp=500,
        quest=True, created_s=77,
    )
    assert (item.weight_centilb, item.cost_cp, item.quest, item.created_s) == (10, 500, True, 77)


def test_custom_item_requires_created_s():
    with pytest.raises(ValidationError):
        CustomItem(id="custom_1", name="Ключ")


def test_custom_item_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        key_item(color="red")


# ItemHolder

def test_holder_defaults():
    item = holder()
    assert item.location_id is None
    assert item.qty == 1
    assert item.cost_cp == 0


@pytest.mark.parametrize("kind", ["npc", "band", "faction", "location"])
def test_holder_accepts_every_kind(kind):
    assert holder(kind=kind).kind == kind


def test_holder_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        holder(kind="dragon")


def test_holder_label_up_to_80_chars():
    assert holder(label="я" * 80).label == "я" * 80


def test_holder_label_over_80_chars_is_rejected():
    with pytest.raises(ValidationError):
        holder(label="я" * 81)


def test_holder_requires_since_s():
    with pytest.raises(ValidationError):
        ItemHolder(kind="npc", ref="npc_klyk", label="Клык")


def test_holder_rejects_unknown_fields():
    with pytest.raises(ValidationError):
        holder(owner="x")


def test_custom_item_holds_a_holder():
    item = key_item(holder=holder(location_id="goblin_den"))
    assert item.holder.ref == "npc_klyk"
    assert item.holder.location_id == "goblin_den"


# WorldState

def test_world_has_empty_catalog_and_zero_seq_by_default():
    state = world()
    assert state.custom_items == {}
    assert state.custom_item_seq == 0


def test_world_catalog_key_must_equal_the_id():
    with pytest.raises(ValidationError):
        WorldState(world_id="w1", rng=Rng(1).state, custom_items={"custom_9": key_item()})


def test_world_catalog_accepts_matching_key():
    state = WorldState(world_id="w1", rng=Rng(1).state, custom_items={"custom_1": key_item()})
    assert state.custom_items["custom_1"].name == "Ржавый ключ"


def test_world_with_catalog_survives_a_json_round_trip():
    where = holder(location_id="goblin_den", cost_cp=70)
    item = key_item(quest=True, weight_centilb=50, holder=where)
    state = WorldState(
        world_id="w1", rng=Rng(1).state, custom_items={"custom_1": item}, custom_item_seq=1
    )
    back = WorldState.model_validate_json(state.model_dump_json())
    assert back == state
    assert back.custom_items["custom_1"].holder.cost_cp == 70


# SceneState / LastCombat

def test_scene_counts_created_items_from_zero():
    assert SceneState(id="s1", started_at_s=0).custom_created == 0


def test_last_combat_gear_is_empty_and_not_looted_by_default():
    last = LastCombat()
    assert last.gear == []
    assert last.gear_looted is False


def test_last_combat_gear_holds_inventory_entries():
    entry = InventoryEntry(item_id="scimitar", qty=3, cost_cp=250, quality="junk")
    last = LastCombat(gear=[entry], gear_looted=True)
    back = LastCombat.model_validate_json(last.model_dump_json())
    assert back.gear == [entry]
    assert back.gear_looted is True


def test_last_combat_default_gear_lists_are_not_shared():
    first = LastCombat()
    first.gear.append(InventoryEntry(item_id="scimitar", cost_cp=1))
    assert LastCombat().gear == []
