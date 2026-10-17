# Трофеи с тел (docs/plan-custom-items.md, разд. 7, партия В; В14, В17, В18).
#   trophy_quality(cr: str, cfg) -> "junk" | "worn" | "used" | None
#       полосы [loot].trophy_quality: ПО 0-1/4 junk, 1/2-2 worn, 3-4 used, 5+ -- None (полная цена).
#   trophy_cost(base: int, quality, cfg) -> int
#       junk x0.1, worn x0.25, used x0.5, None -- base; округление вниз, не меньше 1 мм.
#   gear_cost(registry, item_id) -> int -- цена оружия, доспеха, щита или предмета; неизвестный
#       id -- ValueError (К7к)
#   body_gear(bodies, registry, cfg) -> list[InventoryEntry]  (К7к: id -- оружие, доспех или щит)
#       bodies -- список (monster_id, [weapon_id, ...], boss); одинаковые (id, цена, качество) --
#       один стек; босс -- исходное оружие по полной цене (quality None); пустой список оружия --
#       ничего.
#   quest_gear(world, refs) -> list[InventoryEntry]
#       квестовые кастомные предметы с держателем kind "npc", чей ref среди refs -- как есть
#       (qty и cost_cp держателя, без качества).
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.loot import body_gear, gear_cost, quest_gear, trophy_cost, trophy_quality
from ai_dm.state.world import CustomItem, ItemHolder, WorldState

# trophy_quality

@pytest.mark.parametrize("cr", ["0", "1/8", "1/4"])
def test_low_cr_gives_junk(cr, cfg):
    assert trophy_quality(cr, cfg) == "junk"


@pytest.mark.parametrize("cr", ["1/2", "1", "2"])
def test_middle_cr_gives_worn(cr, cfg):
    assert trophy_quality(cr, cfg) == "worn"


@pytest.mark.parametrize("cr", ["3", "4"])
def test_high_cr_gives_used(cr, cfg):
    assert trophy_quality(cr, cfg) == "used"


@pytest.mark.parametrize("cr", ["5", "10", "30"])
def test_cr_five_and_above_gives_full_price(cr, cfg):
    assert trophy_quality(cr, cfg) is None


# trophy_cost

def test_junk_costs_a_tenth(cfg):
    assert trophy_cost(2500, "junk", cfg) == 250


def test_worn_costs_a_quarter(cfg):
    assert trophy_cost(2500, "worn", cfg) == 625


def test_used_costs_a_half(cfg):
    assert trophy_cost(2500, "used", cfg) == 1250


def test_no_quality_costs_full_price(cfg):
    assert trophy_cost(2500, None, cfg) == 2500


def test_cost_is_rounded_down(cfg):
    assert trophy_cost(15, "worn", cfg) == 3


def test_cost_is_rounded_down_for_used(cfg):
    assert trophy_cost(7, "used", cfg) == 3


def test_cost_is_at_least_one(cfg):
    assert trophy_cost(5, "junk", cfg) == 1


def test_free_item_costs_one_with_quality(cfg):
    assert trophy_cost(0, "junk", cfg) == 1


def test_one_copper_item_with_quality_costs_one(cfg):
    assert trophy_cost(1, "used", cfg) == 1


# body_gear

def test_five_goblins_give_one_junk_stack(registry, cfg):
    bodies = [("goblin_warrior", ["scimitar"], False)] * 5
    gear = body_gear(bodies, registry, cfg)
    assert len(gear) == 1
    assert (gear[0].item_id, gear[0].qty, gear[0].quality) == ("scimitar", 5, "junk")


def test_junk_scimitar_cost_follows_the_formula(registry, cfg):
    gear = body_gear([("goblin_warrior", ["scimitar"], False)], registry, cfg)
    base = registry.get("weapon", "scimitar").cost_cp
    assert gear[0].cost_cp == max(1, base * 10 // 100)


def test_two_weapons_of_one_body_are_two_stacks(registry, cfg):
    gear = body_gear([("goblin_warrior", ["scimitar", "shortbow"], False)], registry, cfg)
    assert [(e.item_id, e.qty) for e in gear] == [("scimitar", 1), ("shortbow", 1)]


def test_weapons_of_different_bodies_with_same_price_share_a_stack(registry, cfg):
    bodies = [("goblin_warrior", ["shortbow"], False), ("goblin_warrior", ["shortbow"], False)]
    gear = body_gear(bodies, registry, cfg)
    assert [(e.item_id, e.qty) for e in gear] == [("shortbow", 2)]


def test_different_quality_gives_separate_stacks(registry, cfg):
    bodies = [("goblin_warrior", ["scimitar"], False), ("goblin_boss", ["scimitar"], False)]
    gear = body_gear(bodies, registry, cfg)
    assert sorted((e.quality, e.qty) for e in gear) == [("junk", 1), ("worn", 1)]


def test_boss_gives_original_weapon_at_full_price(registry, cfg):
    gear = body_gear([("goblin_boss", ["scimitar"], True)], registry, cfg)
    assert (gear[0].item_id, gear[0].quality) == ("scimitar", None)
    assert gear[0].cost_cp == registry.get("weapon", "scimitar").cost_cp


def test_non_boss_of_cr_one_gives_worn(registry, cfg):
    gear = body_gear([("goblin_boss", ["scimitar"], False)], registry, cfg)
    assert gear[0].quality == "worn"
    assert gear[0].cost_cp == registry.get("weapon", "scimitar").cost_cp * 25 // 100


def test_body_without_weapons_gives_nothing(registry, cfg):
    assert body_gear([("goblin_warrior", [], False)], registry, cfg) == []


def test_no_bodies_gives_nothing(registry, cfg):
    assert body_gear([], registry, cfg) == []


def test_body_gear_does_not_touch_registry_weapon(registry, cfg):
    before = registry.get("weapon", "scimitar").cost_cp
    body_gear([("goblin_warrior", ["scimitar"], False)], registry, cfg)
    assert registry.get("weapon", "scimitar").cost_cp == before


# quest_gear

def world_with(holder, quest=True):
    world = WorldState(world_id="w1", rng=Rng(1).state)
    world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", quest=quest, created_s=0, holder=holder
    )
    return world


def holder_of(kind="npc", ref="npc_klyk", qty=1, cost_cp=900):
    return ItemHolder(kind=kind, ref=ref, label="Клык", since_s=0, qty=qty, cost_cp=cost_cp)


def test_quest_item_of_defeated_npc_holder_is_returned_as_is():
    gear = quest_gear(world_with(holder_of(qty=2)), ["npc_klyk"])
    assert [(e.item_id, e.qty, e.cost_cp, e.quality) for e in gear] == [
        ("custom_1", 2, 900, None)
    ]


def test_quest_item_of_another_holder_is_not_returned():
    assert quest_gear(world_with(holder_of(ref="npc_other")), ["npc_klyk"]) == []


def test_band_holder_is_not_returned():
    assert quest_gear(world_with(holder_of(kind="band")), ["npc_klyk"]) == []


def test_location_holder_is_not_returned():
    assert quest_gear(world_with(holder_of(kind="location")), ["npc_klyk"]) == []


def test_non_quest_item_is_not_returned():
    assert quest_gear(world_with(holder_of(), quest=False), ["npc_klyk"]) == []


def test_item_without_holder_is_not_returned():
    assert quest_gear(world_with(None), ["npc_klyk"]) == []


def test_no_bodies_return_no_quest_items():
    assert quest_gear(world_with(holder_of()), []) == []


# К7к: доспех и щит с тел, gear_cost

def test_gear_cost_of_a_weapon(registry):
    assert gear_cost(registry, "scimitar") == registry.get("weapon", "scimitar").cost_cp


def test_gear_cost_of_an_armor(registry):
    assert gear_cost(registry, "chain_shirt") == 5000


def test_gear_cost_of_a_shield(registry):
    assert gear_cost(registry, "shield") == 1000


def test_gear_cost_of_a_plain_item(registry):
    item_id = registry.ids("item")[0]
    assert gear_cost(registry, item_id) == registry.get("item", item_id).cost_cp


def test_gear_cost_of_an_unknown_id_raises(registry):
    with pytest.raises(ValueError):
        gear_cost(registry, "no_such_thing")


def test_body_gear_takes_armor_and_shield_ids(registry, cfg):
    gear = body_gear(
        [("goblin_warrior", ["scimitar", "leather_armor", "shield"], False)], registry, cfg
    )
    assert [(e.item_id, e.qty, e.quality) for e in gear] == [
        ("scimitar", 1, "junk"), ("leather_armor", 1, "junk"), ("shield", 1, "junk"),
    ]


def test_junk_armor_costs_a_tenth(registry, cfg):
    gear = body_gear([("goblin_warrior", ["leather_armor", "shield"], False)], registry, cfg)
    assert [e.cost_cp for e in gear] == [100, 100]


def test_boss_armor_is_at_full_price(registry, cfg):
    gear = body_gear([("goblin_boss", ["chain_shirt", "shield"], True)], registry, cfg)
    assert [(e.item_id, e.cost_cp, e.quality) for e in gear] == [
        ("chain_shirt", 5000, None), ("shield", 1000, None),
    ]


def test_armor_of_a_non_boss_follows_the_cr_band(registry, cfg):
    # ПО 1 -- worn, четверть цены
    gear = body_gear([("goblin_boss", ["chain_shirt"], False)], registry, cfg)
    assert (gear[0].cost_cp, gear[0].quality) == (1250, "worn")


def test_three_bodies_make_stacks_of_armor(registry, cfg):
    bodies = [("goblin_warrior", ["leather_armor", "shield"], False)] * 3
    gear = body_gear(bodies, registry, cfg)
    assert [(e.item_id, e.qty) for e in gear] == [("leather_armor", 3), ("shield", 3)]


def test_unknown_gear_id_raises(registry, cfg):
    with pytest.raises(ValueError):
        body_gear([("goblin_warrior", ["no_such_thing"], False)], registry, cfg)
