# Цена у каждого экземпляра (docs/CUSTOM-ITEMS-PLAN.md, разд. 8, партия 0; В19, В22).
#   InventoryEntry(item_id, qty, cost_cp: int, quality: "junk" | "worn" | "used" | None = None)
#   Стек = одинаковые (item_id, cost_cp, quality); разная цена или качество -- отдельные строки.
#   add_item(hero, item_id, qty=1, *, cost_cp, quality=None) -- cost_cp обязательный keyword
#       (без него TypeError); qty < 1 -> InventoryError.
#   add_catalog_item(hero, registry, item_id, qty=1) -- цена из реестра, quality None.
#   remove_item(hero, item_id, qty=1, *, cost_cp=None) -> list[InventoryEntry] (снятое):
#       cost_cp None -- с самого дешёвого стека (при нехватке -- со следующего по цене);
#       cost_cp задан -- только со стека этой цены; нет стека или в нём мало -> InventoryError
#       (инвентарь не меняется). Надетое снимается, только когда count_item(id) == 0.
#   count_item -- сумма по стекам.
#   pick_valuables(hero, registry, rng, count) -> list[InventoryEntry]: по убыванию entry.cost_cp;
#       надетый экземпляр берётся из самого дорогого стека этого id и не отдаётся.
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.inventory import (
    InventoryError,
    add_catalog_item,
    add_item,
    count_item,
    equip,
    pick_valuables,
    remove_item,
)
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState, InventoryEntry


def make_hero():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def two_stacks():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=1500)
    add_item(hero, "scimitar", cost_cp=150)
    return hero


def stacks(hero):
    return [(e.item_id, e.cost_cp, e.quality, e.qty) for e in hero.inventory]


def totals(entries):
    # итог по (id, цена): работает и для записей с qty > 1, и для списка по одной штуке
    result = {}
    for e in entries:
        result[(e.item_id, e.cost_cp)] = result.get((e.item_id, e.cost_cp), 0) + e.qty
    return result


# add_item

def test_add_item_keeps_the_price_in_the_entry():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=1500)
    assert stacks(hero) == [("scimitar", 1500, None, 1)]


def test_add_item_without_cost_is_a_type_error():
    with pytest.raises(TypeError):
        add_item(make_hero(), "scimitar")


def test_add_item_cost_must_be_a_keyword():
    with pytest.raises(TypeError):
        add_item(make_hero(), "scimitar", 1, 1500)


def test_add_item_with_zero_cost_is_allowed():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=0)
    assert stacks(hero) == [("scimitar", 0, None, 1)]


def test_add_item_keeps_the_quality():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    assert stacks(hero) == [("scimitar", 150, "worn", 1)]


def test_add_item_with_zero_qty_is_an_error():
    with pytest.raises(InventoryError):
        add_item(make_hero(), "scimitar", 0, cost_cp=1500)


def test_add_item_same_id_and_cost_grows_the_stack():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=1500)
    add_item(hero, "scimitar", 2, cost_cp=1500)
    assert stacks(hero) == [("scimitar", 1500, None, 3)]


def test_add_item_other_cost_makes_a_new_stack():
    assert stacks(two_stacks()) == [("scimitar", 1500, None, 1), ("scimitar", 150, None, 1)]


def test_add_item_other_quality_makes_a_new_stack():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "scimitar", cost_cp=150, quality="junk")
    assert stacks(hero) == [("scimitar", 150, None, 1), ("scimitar", 150, "junk", 1)]


def test_add_item_same_cost_but_other_id_is_other_stack():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "longsword", cost_cp=150)
    assert len(hero.inventory) == 2


def test_add_item_same_quality_and_cost_grows_the_stack():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    assert stacks(hero) == [("scimitar", 150, "worn", 2)]


def test_count_item_sums_the_stacks():
    hero = two_stacks()
    add_item(hero, "scimitar", 2, cost_cp=150)
    assert count_item(hero, "scimitar") == 4


def test_count_item_ignores_other_ids():
    hero = two_stacks()
    add_item(hero, "longsword", cost_cp=1500)
    assert count_item(hero, "scimitar") == 2


# add_catalog_item

def test_add_catalog_item_takes_the_registry_price(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "longsword")
    assert stacks(hero) == [("longsword", registry.get("weapon", "longsword").cost_cp, None, 1)]


def test_add_catalog_item_takes_the_price_of_an_item_kind(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "potion_of_healing", 2)
    assert stacks(hero) == [
        ("potion_of_healing", registry.get("item", "potion_of_healing").cost_cp, None, 2)
    ]


def test_add_catalog_item_takes_the_price_of_an_armor_kind(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shield")
    assert hero.inventory[0].cost_cp == registry.get("armor", "shield").cost_cp


def test_add_catalog_item_joins_the_stack_of_the_same_price(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "longsword")
    add_catalog_item(hero, registry, "longsword")
    assert stacks(hero)[0][3] == 2


def test_add_catalog_item_beside_a_cheaper_stack_is_a_new_row(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=150)
    add_catalog_item(hero, registry, "longsword")
    assert len(hero.inventory) == 2


# remove_item

def test_remove_item_without_cost_takes_the_cheapest_stack():
    hero = two_stacks()
    remove_item(hero, "scimitar")
    assert stacks(hero) == [("scimitar", 1500, None, 1)]


def test_remove_item_cheapest_does_not_depend_on_the_order():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "scimitar", cost_cp=1500)
    remove_item(hero, "scimitar")
    assert stacks(hero) == [("scimitar", 1500, None, 1)]


def test_remove_item_without_cost_spills_over_to_the_next_stack():
    hero = two_stacks()
    add_item(hero, "scimitar", cost_cp=800)
    remove_item(hero, "scimitar", 2)
    assert stacks(hero) == [("scimitar", 1500, None, 1)]


def test_remove_item_takes_part_of_the_cheapest_stack():
    hero = make_hero()
    add_item(hero, "scimitar", 3, cost_cp=150)
    add_item(hero, "scimitar", cost_cp=1500)
    remove_item(hero, "scimitar", 2)
    assert stacks(hero) == [("scimitar", 150, None, 1), ("scimitar", 1500, None, 1)]


def test_remove_item_with_cost_takes_exactly_that_stack():
    hero = two_stacks()
    remove_item(hero, "scimitar", cost_cp=1500)
    assert stacks(hero) == [("scimitar", 150, None, 1)]


def test_remove_item_with_unknown_cost_is_an_error():
    hero = two_stacks()
    with pytest.raises(InventoryError):
        remove_item(hero, "scimitar", cost_cp=999)


def test_remove_item_with_unknown_cost_changes_nothing():
    hero = two_stacks()
    before = hero.model_dump()
    with pytest.raises(InventoryError):
        remove_item(hero, "scimitar", cost_cp=999)
    assert hero.model_dump() == before


def test_remove_item_with_cost_does_not_borrow_from_other_stacks():
    hero = two_stacks()
    with pytest.raises(InventoryError):
        remove_item(hero, "scimitar", 2, cost_cp=150)
    assert count_item(hero, "scimitar") == 2


def test_remove_item_more_than_all_stacks_is_an_error_and_changes_nothing():
    hero = two_stacks()
    before = hero.model_dump()
    with pytest.raises(InventoryError):
        remove_item(hero, "scimitar", 3)
    assert hero.model_dump() == before


def test_remove_item_with_zero_qty_is_an_error():
    with pytest.raises(InventoryError):
        remove_item(two_stacks(), "scimitar", 0)


def test_remove_item_of_missing_id_is_an_error():
    with pytest.raises(InventoryError):
        remove_item(two_stacks(), "longsword")


def test_remove_item_returns_the_removed_entry_with_its_price():
    hero = two_stacks()
    removed = remove_item(hero, "scimitar")
    assert totals(removed) == {("scimitar", 150): 1}


def test_remove_item_returns_all_removed_stacks():
    hero = two_stacks()
    removed = remove_item(hero, "scimitar", 2)
    assert totals(removed) == {("scimitar", 150): 1, ("scimitar", 1500): 1}


def test_remove_item_returns_the_quality_of_the_removed_entry():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    removed = remove_item(hero, "scimitar")
    assert [e.quality for e in removed] == ["worn"]


def test_remove_item_returns_inventory_entries():
    hero = two_stacks()
    removed = remove_item(hero, "scimitar", cost_cp=1500)
    assert all(isinstance(e, InventoryEntry) for e in removed)


def test_remove_item_of_the_exact_stack_returns_that_price():
    hero = two_stacks()
    assert totals(remove_item(hero, "scimitar", cost_cp=1500)) == {("scimitar", 1500): 1}


def test_remove_item_empties_a_stack_and_drops_the_row():
    hero = two_stacks()
    remove_item(hero, "scimitar", cost_cp=150)
    assert [e.cost_cp for e in hero.inventory] == [1500]


# надетое и стеки

def test_equipped_stays_while_a_stack_remains(registry):
    hero = two_stacks()
    equip(hero, "scimitar", registry)
    remove_item(hero, "scimitar")
    assert hero.equipped.main_hand == "scimitar"


def test_equipped_is_cleared_only_when_the_last_copy_leaves(registry):
    hero = two_stacks()
    equip(hero, "scimitar", registry)
    remove_item(hero, "scimitar", 2)
    assert hero.equipped.main_hand is None


def test_equipped_stays_when_removing_by_cost_while_another_stack_remains(registry):
    hero = two_stacks()
    equip(hero, "scimitar", registry)
    remove_item(hero, "scimitar", cost_cp=1500)
    assert hero.equipped.main_hand == "scimitar"


def test_equipped_is_cleared_after_removing_both_stacks_one_by_one(registry):
    hero = two_stacks()
    equip(hero, "scimitar", registry)
    remove_item(hero, "scimitar", cost_cp=1500)
    remove_item(hero, "scimitar", cost_cp=150)
    assert hero.equipped.main_hand is None


# pick_valuables

def picked(hero, registry, count):
    return pick_valuables(hero, registry, Rng(1), count)


def test_pick_valuables_sorts_by_the_entry_price(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "longsword", cost_cp=1500)
    assert totals(picked(hero, registry, 1)) == {("longsword", 1500): 1}


def test_pick_valuables_cheap_trophy_loses_to_a_srd_price(registry):
    # скимитар по реестру дороже, но у этого экземпляра цена трофея
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=10, quality="junk")
    add_item(hero, "spear", cost_cp=100)
    assert totals(picked(hero, registry, 1)) == {("spear", 100): 1}


def test_pick_valuables_expensive_entry_beats_the_registry_order(registry):
    # копьё по реестру дешевле скимитара, но у записи цена выше
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=100)
    add_item(hero, "spear", cost_cp=9000)
    assert totals(picked(hero, registry, 1)) == {("spear", 9000): 1}


def test_pick_valuables_takes_the_expensive_stack_of_one_id_first(registry):
    hero = two_stacks()
    assert totals(picked(hero, registry, 1)) == {("scimitar", 1500): 1}


def test_pick_valuables_takes_both_stacks_when_asked(registry):
    hero = two_stacks()
    assert totals(picked(hero, registry, 2)) == {("scimitar", 1500): 1, ("scimitar", 150): 1}


def test_pick_valuables_returns_no_more_than_count(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 5, cost_cp=150)
    assert sum(totals(picked(hero, registry, 3)).values()) == 3


def test_pick_valuables_returns_entries_with_the_quality(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    assert [e.quality for e in picked(hero, registry, 1)] == ["worn"]


def test_pick_valuables_does_not_change_the_inventory(registry):
    hero = two_stacks()
    before = hero.model_dump()
    picked(hero, registry, 2)
    assert hero.model_dump() == before


def test_pick_valuables_skips_the_only_worn_copy(registry):
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=1500)
    equip(hero, "scimitar", registry)
    assert picked(hero, registry, 1) == []


def test_pick_valuables_worn_copy_comes_from_the_most_expensive_stack(registry):
    hero = two_stacks()
    equip(hero, "scimitar", registry)
    assert totals(picked(hero, registry, 2)) == {("scimitar", 150): 1}


def test_pick_valuables_leaves_the_worn_copy_in_a_big_expensive_stack(registry):
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=1500)
    add_item(hero, "scimitar", cost_cp=150)
    equip(hero, "scimitar", registry)
    assert totals(picked(hero, registry, 5)) == {("scimitar", 1500): 1, ("scimitar", 150): 1}


def test_pick_valuables_worn_off_hand_copy_is_also_kept(registry):
    hero = make_hero()
    add_item(hero, "shortsword", 2, cost_cp=1000)
    equip(hero, "shortsword", registry)
    equip(hero, "shortsword", registry, slot="off_hand")
    assert picked(hero, registry, 5) == []


def test_pick_valuables_with_nothing_is_empty(registry):
    assert picked(make_hero(), registry, 2) == []


def test_remove_item_returns_the_removed_qty():
    hero = make_hero()
    add_item(hero, "scimitar", 5, cost_cp=150)
    removed = remove_item(hero, "scimitar", 3)
    assert totals(removed) == {("scimitar", 150): 3}
    assert stacks(hero) == [("scimitar", 150, None, 2)]


def test_remove_item_does_not_return_stacks_it_did_not_touch():
    hero = make_hero()
    add_item(hero, "scimitar", 2, cost_cp=150)
    add_item(hero, "scimitar", 2, cost_cp=1500)
    removed = remove_item(hero, "scimitar", 1)
    assert totals(removed) == {("scimitar", 150): 1}


# quality в точечном снятии: remove_item(..., cost_cp=, quality="any" по умолчанию)

def same_price_stacks():
    hero = make_hero()
    add_item(hero, "scimitar", cost_cp=150)
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    return hero


def test_remove_item_by_cost_and_quality_takes_only_that_stack():
    hero = same_price_stacks()
    remove_item(hero, "scimitar", cost_cp=150, quality="worn")
    assert stacks(hero) == [("scimitar", 150, None, 1)]


def test_remove_item_with_quality_none_takes_only_the_plain_stack():
    hero = same_price_stacks()
    remove_item(hero, "scimitar", cost_cp=150, quality=None)
    assert stacks(hero) == [("scimitar", 150, "worn", 1)]


def test_remove_item_by_cost_without_quality_takes_any_stack_of_that_price():
    hero = same_price_stacks()
    remove_item(hero, "scimitar", 2, cost_cp=150)
    assert hero.inventory == []


def test_remove_item_with_missing_quality_is_an_error_and_changes_nothing():
    hero = same_price_stacks()
    before = hero.model_dump()
    with pytest.raises(InventoryError):
        remove_item(hero, "scimitar", cost_cp=150, quality="junk")
    assert hero.model_dump() == before


def test_remove_item_returns_the_quality_of_the_chosen_stack():
    hero = same_price_stacks()
    removed = remove_item(hero, "scimitar", cost_cp=150, quality="worn")
    assert [e.quality for e in removed] == ["worn"]


def test_pick_valuables_skips_an_unknown_id(registry):
    hero = make_hero()
    add_item(hero, "ghost_relic", cost_cp=0)
    add_item(hero, "spear", cost_cp=100)
    assert totals(picked(hero, registry, 5)) == {("spear", 100): 1}
