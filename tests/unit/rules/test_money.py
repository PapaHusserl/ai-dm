# Ожидаемый API: ai_dm.rules.money (деньги -- целые медяки; 1 зм = 10 см = 100 мм)
#   to_cp(gp=0, sp=0, cp=0) -> int                      -- зм/см/мм в медяки; < 0 -> ValueError
#   split_cp(cp: int) -> tuple[int, int, int]           -- (зм, см, мм); cp < 0 -> ValueError
#   format_cp(cp: int) -> str                           -- "12 зм 3 см 5 мм" (1235); нулевые
#       разряды опускаются ("12 зм" для 1200, "1 зм 5 мм" для 105), ноль -> "0 мм";
#       cp < 0 -> ValueError
#   NotEnoughMoney(ValueError)
#   add_money(hero, cp: int) -> None                    -- hero.money_cp += cp; cp < 0 -> ValueError
#   spend_money(hero, cp: int) -> None                  -- hero.money_cp -= cp; не хватает ->
#                                                          NotEnoughMoney, деньги не меняются;
#                                                          cp < 0 -> ValueError
# ai_dm.rules.inventory
#   pick_valuables(hero, registry, rng, count: int) -> list[InventoryEntry]
#       выбор «ценных» предметов для ограбления: единицы инвентаря (стопка qty=2 -- две единицы),
#       по убыванию cost_cp (weapon/armor/item); при равной цене порядок решается через rng
#       (одинаковый сид -> одинаковый результат; порядок записей инвентаря не влияет -- ничьи
#       сортируются по id до выбора через rng); возвращает id (по одному на единицу), не больше
#       count (меньше, если единиц меньше); count=0 -> []; hero не меняет;
#       надетое (hero.equipped, все слоты включая off_hand) не берётся -- P7, аудит 1 п. 2.6;
#       у стопки надетая единица вычитается из qty;
#       неизвестный id в инвентаре -> InventoryError;
#       rng тратится только на группы ничьих (разные id с одной ценой), которые нужны до набора
#       count, поэтому «хлам» ниже отсечки не меняет ни результат, ни rng.draws; стопка одного
#       id (qty > 1) -- не ничья и rng не тратит
import pytest

from ai_dm.content.loader import load_registry
from ai_dm.core.rng import Rng
from ai_dm.rules.inventory import add_catalog_item, add_item, pick_valuables
from ai_dm.rules.money import (
    NotEnoughMoney,
    add_money,
    format_cp,
    spend_money,
    split_cp,
)
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_hero(money_cp=0):
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
        money_cp=money_cp,
    )


def write(path, text):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def make_registry_with_gems(tmp_path):
    write(tmp_path / "items" / "ruby_a.yaml", "id: ruby_a\nname: Рубин А\ncost_cp: 5000\n")
    write(tmp_path / "items" / "ruby_b.yaml", "id: ruby_b\nname: Рубин Б\ncost_cp: 5000\n")
    write(tmp_path / "items" / "pebble.yaml", "id: pebble\nname: Камешек\ncost_cp: 1\n")
    return load_registry([tmp_path])


def pick_ids(hero, registry, rng, count):
    return [entry.item_id for entry in pick_valuables(hero, registry, rng, count)]


def make_loot_hero(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "pebble")
    add_catalog_item(hero, registry, "longsword")
    add_catalog_item(hero, registry, "ruby_a")
    add_catalog_item(hero, registry, "ruby_b")
    return hero


# перевод и форматирование

def test_split_cp():
    assert split_cp(1235) == (12, 3, 5)


def test_split_cp_zero():
    assert split_cp(0) == (0, 0, 0)


def test_split_cp_below_silver():
    assert split_cp(9) == (0, 0, 9)


def test_split_cp_negative_raises_value_error():
    with pytest.raises(ValueError):
        split_cp(-1)


def test_format_cp_all_denominations():
    assert format_cp(1235) == "12 зм 3 см 5 мм"


def test_format_cp_gold_only():
    assert format_cp(1200) == "12 зм"


def test_format_cp_skips_zero_silver():
    assert format_cp(105) == "1 зм 5 мм"


def test_format_cp_silver_only():
    assert format_cp(30) == "3 см"


def test_format_cp_copper_only():
    assert format_cp(7) == "7 мм"


def test_format_cp_zero():
    assert format_cp(0) == "0 мм"


def test_format_cp_large_amount_keeps_gold_total():
    assert format_cp(1_000_000) == "10000 зм"


def test_format_cp_negative_raises_value_error():
    with pytest.raises(ValueError):
        format_cp(-5)


# деньги героя

def test_add_money_increases_balance():
    hero = make_hero(100)
    add_money(hero, 250)
    assert hero.money_cp == 350


def test_add_negative_money_raises_value_error():
    with pytest.raises(ValueError):
        add_money(make_hero(100), -1)


def test_spend_money_decreases_balance():
    hero = make_hero(100)
    spend_money(hero, 40)
    assert hero.money_cp == 60


def test_spend_all_money_leaves_zero():
    hero = make_hero(100)
    spend_money(hero, 100)
    assert hero.money_cp == 0


def test_spend_more_than_owned_raises_not_enough_money():
    with pytest.raises(NotEnoughMoney):
        spend_money(make_hero(100), 101)


def test_failed_spend_does_not_change_balance():
    hero = make_hero(100)
    with pytest.raises(NotEnoughMoney):
        spend_money(hero, 101)
    assert hero.money_cp == 100


def test_not_enough_money_is_value_error():
    assert issubclass(NotEnoughMoney, ValueError)


def test_spend_negative_money_raises_value_error():
    with pytest.raises(ValueError):
        spend_money(make_hero(100), -1)


# ценные предметы для ограбления

def test_most_valuable_item_is_picked_first(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "dagger")
    add_catalog_item(hero, registry, "longsword")
    assert pick_ids(hero, registry, Rng(1), 1) == ["longsword"]


def test_pick_order_is_by_descending_cost(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shield")
    add_catalog_item(hero, registry, "chain_mail")
    add_catalog_item(hero, registry, "longsword")
    assert pick_ids(hero, registry, Rng(1), 3) == ["chain_mail", "longsword", "shield"]


def test_pick_more_than_owned_returns_everything(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shield")
    add_catalog_item(hero, registry, "chain_mail")
    assert pick_ids(hero, registry, Rng(1), 10) == ["chain_mail", "shield"]


def test_pick_zero_returns_empty_list(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shield")
    assert pick_ids(hero, registry, Rng(1), 0) == []


def test_pick_from_empty_inventory_returns_empty_list(registry):
    assert pick_ids(make_hero(), registry, Rng(1), 3) == []


def test_stack_counts_as_several_units(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "chain_mail")
    add_catalog_item(hero, registry, "shield", 2)
    assert pick_ids(hero, registry, Rng(1), 3) == ["chain_mail", "shield", "shield"]


def test_pick_does_not_change_inventory(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "chain_mail")
    before = hero.model_dump()
    pick_ids(hero, registry, Rng(1), 1)
    assert hero.model_dump() == before


def test_equal_cost_tie_does_not_push_cheaper_item_ahead(tmp_path):
    registry = make_registry_with_gems(tmp_path)
    picked = pick_ids(make_loot_hero(registry), registry, Rng(5), 3)
    assert set(picked[:2]) == {"ruby_a", "ruby_b"}
    assert picked[2] == "longsword"


def test_equal_cost_tie_is_deterministic_for_same_seed(tmp_path):
    registry = make_registry_with_gems(tmp_path)
    first = pick_ids(make_loot_hero(registry), registry, Rng(5), 1)
    second = pick_ids(make_loot_hero(registry), registry, Rng(5), 1)
    assert first == second


def test_equal_cost_tie_uses_rng(tmp_path):
    registry = make_registry_with_gems(tmp_path)
    rng = Rng(5)
    pick_ids(make_loot_hero(registry), registry, rng, 1)
    assert rng.draws > 0


def test_equal_cost_tie_can_go_either_way_depending_on_seed(tmp_path):
    registry = make_registry_with_gems(tmp_path)
    winners = {pick_ids(make_loot_hero(registry), registry, Rng(s), 1)[0] for s in range(40)}
    assert winners == {"ruby_a", "ruby_b"}


def test_tie_result_does_not_depend_on_inventory_order(tmp_path):
    registry = make_registry_with_gems(tmp_path)
    straight = make_hero()
    for item in ["ruby_a", "ruby_b"]:
        add_catalog_item(straight, registry, item)
    reverse = make_hero()
    for item in ["ruby_b", "ruby_a"]:
        add_catalog_item(reverse, registry, item)
    assert pick_ids(straight, registry, Rng(3), 1) == pick_ids(
        reverse, registry, Rng(3), 1
    )


# ценные предметы: неизвестный id, поток rng и «хлам» ниже отсечки

def make_registry_with_junk(tmp_path):
    for name, cost in [
        ("ruby_a", 5000), ("ruby_b", 5000),
        ("opal_a", 1500), ("opal_b", 1500),
        ("junk_a", 1), ("junk_b", 1), ("junk_c", 1),
    ]:
        write(tmp_path / "items" / f"{name}.yaml", f"id: {name}\nname: {name}\ncost_cp: {cost}\n")
    return load_registry([tmp_path])


def test_pick_skips_unknown_item_id(registry):
    hero = make_hero()
    add_item(hero, "no_such_item", cost_cp=0)
    assert pick_ids(hero, registry, Rng(1), 1) == []


def test_pick_skips_unknown_item_among_known(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "longsword")
    add_item(hero, "no_such_item", cost_cp=0)
    assert pick_ids(hero, registry, Rng(1), 2) == ["longsword"]


def test_pick_with_cheap_junk_below_cutoff_gives_same_result(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    plain = make_hero()
    junky = make_hero()
    for item in ["ruby_a", "ruby_b"]:
        add_catalog_item(plain, registry, item)
        add_catalog_item(junky, registry, item)
    for item in ["junk_a", "junk_b", "junk_c"]:
        add_catalog_item(junky, registry, item)
    assert pick_ids(plain, registry, Rng(5), 1) == pick_ids(junky, registry, Rng(5), 1)


def test_pick_with_cheap_junk_below_cutoff_gives_same_rng_draws(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    plain = make_hero()
    junky = make_hero()
    for item in ["ruby_a", "ruby_b"]:
        add_catalog_item(plain, registry, item)
        add_catalog_item(junky, registry, item)
    for item in ["junk_a", "junk_b", "junk_c"]:
        add_catalog_item(junky, registry, item)
    rng_plain = Rng(5)
    rng_junky = Rng(5)
    pick_ids(plain, registry, rng_plain, 1)
    pick_ids(junky, registry, rng_junky, 1)
    assert rng_plain.draws == rng_junky.draws
    assert rng_plain.state == rng_junky.state


def test_pick_junk_tie_group_below_cutoff_does_not_touch_rng(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    hero = make_hero()
    for item in ["ruby_a", "opal_a", "opal_b", "junk_a", "junk_b"]:
        add_catalog_item(hero, registry, item)
    rng = Rng(5)
    assert pick_ids(hero, registry, rng, 1) == ["ruby_a"]
    assert rng.draws == 0


def test_pick_shuffles_only_groups_needed_for_count(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    few = make_hero()
    many = make_hero()
    for item in ["ruby_a", "ruby_b"]:
        add_catalog_item(few, registry, item)
        add_catalog_item(many, registry, item)
    for item in ["opal_a", "opal_b"]:
        add_catalog_item(many, registry, item)
    rng_few = Rng(8)
    rng_many = Rng(8)
    assert pick_ids(few, registry, rng_few, 2) == pick_ids(many, registry, rng_many, 2)
    assert rng_few.draws == rng_many.draws


def test_pick_second_tie_group_is_shuffled_when_count_reaches_it(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    hero = make_hero()
    for item in ["ruby_a", "opal_a", "opal_b"]:
        add_catalog_item(hero, registry, item)
    rng = Rng(3)
    picked = pick_ids(hero, registry, rng, 2)
    assert picked[0] == "ruby_a"
    assert picked[1] in {"opal_a", "opal_b"}
    assert rng.draws > 0


def test_pick_stack_of_one_id_does_not_use_rng(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    hero = make_hero()
    add_catalog_item(hero, registry, "ruby_a", 3)
    rng = Rng(5)
    assert pick_ids(hero, registry, rng, 2) == ["ruby_a", "ruby_a"]
    assert rng.draws == 0


def test_pick_stack_does_not_change_rng_stream_for_other_ties(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    single = make_hero()
    stacked = make_hero()
    for item in ["ruby_a", "ruby_b"]:
        add_catalog_item(single, registry, item)
    add_catalog_item(stacked, registry, "ruby_a", 4)
    add_catalog_item(stacked, registry, "ruby_b", 4)
    rng_single = Rng(11)
    rng_stacked = Rng(11)
    first = pick_ids(single, registry, rng_single, 1)
    second = pick_ids(stacked, registry, rng_stacked, 1)
    assert first == second
    assert rng_single.draws == rng_stacked.draws


def test_pick_stack_of_tied_id_returns_whole_stack_first(tmp_path):
    registry = make_registry_with_junk(tmp_path)
    hero = make_hero()
    add_catalog_item(hero, registry, "ruby_a", 2)
    add_catalog_item(hero, registry, "ruby_b", 2)
    picked = pick_ids(hero, registry, Rng(5), 2)
    assert picked in (["ruby_a", "ruby_a"], ["ruby_b", "ruby_b"])


# ограбление не берёт надетое (P7)

def test_pick_skips_equipped_armor(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "chain_mail")
    add_catalog_item(hero, registry, "dagger")
    hero.equipped.armor = "chain_mail"
    assert pick_ids(hero, registry, Rng(1), 2) == ["dagger"]


def test_pick_skips_equipped_shield(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shield")
    add_catalog_item(hero, registry, "dagger")
    hero.equipped.shield = "shield"
    assert pick_ids(hero, registry, Rng(1), 2) == ["dagger"]


def test_pick_skips_equipped_main_hand(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "longsword")
    add_catalog_item(hero, registry, "dagger")
    hero.equipped.main_hand = "longsword"
    assert pick_ids(hero, registry, Rng(1), 2) == ["dagger"]


def test_pick_skips_equipped_off_hand(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "shortsword")
    add_catalog_item(hero, registry, "dagger")
    hero.equipped.off_hand = "shortsword"
    assert pick_ids(hero, registry, Rng(1), 2) == ["dagger"]


def test_pick_with_everything_equipped_returns_empty_list(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "chain_mail")
    add_catalog_item(hero, registry, "longsword")
    hero.equipped.armor = "chain_mail"
    hero.equipped.main_hand = "longsword"
    assert pick_ids(hero, registry, Rng(1), 5) == []


def test_pick_takes_spare_copy_of_equipped_item(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "longsword", 2)
    hero.equipped.main_hand = "longsword"
    assert pick_ids(hero, registry, Rng(1), 5) == ["longsword"]


def test_pick_takes_only_unequipped_part_of_two_equipped_slots(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "dagger", 3)
    hero.equipped.main_hand = "dagger"
    hero.equipped.off_hand = "dagger"
    assert pick_ids(hero, registry, Rng(1), 5) == ["dagger"]


def test_pick_with_equipped_does_not_change_equipped_or_inventory(registry):
    hero = make_hero()
    add_catalog_item(hero, registry, "chain_mail")
    add_catalog_item(hero, registry, "dagger")
    hero.equipped.armor = "chain_mail"
    before = hero.model_dump()
    pick_ids(hero, registry, Rng(1), 2)
    assert hero.model_dump() == before


# граничные случаи

def test_spend_zero_money_is_allowed():
    hero = make_hero(100)
    spend_money(hero, 0)
    assert hero.money_cp == 100
