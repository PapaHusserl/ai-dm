# Ожидаемый API: ai_dm.rules.inventory (hero: HeroState, мутируется на месте; registry)
#   InventoryError(ValueError)
#   count_item(hero, item_id) -> int                    -- 0, если предмета нет
#   add_item(hero, item_id, qty=1) -> None              -- складывает в стопку (одна запись на id);
#                                                          qty < 1 -> InventoryError
#   remove_item(hero, item_id, qty=1) -> None           -- qty < 1 или больше, чем есть ->
#                                                          InventoryError, инвентарь не меняется;
#                                                          запись с qty 0 исчезает; если убрана
#                                                          последняя копия надетого -- он снимается
#   equip(hero, item_id, registry) -> None
#       предмет должен быть в инвентаре, иначе InventoryError; слот по виду:
#       доспех -> equipped.armor; щит (armor category "shield") -> equipped.shield;
#       оружие -> equipped.main_hand; другое (зелье) -> InventoryError;
#       новый предмет заменяет прежний в слоте; надетое остаётся в инвентаре;
#       двуручное оружие (свойство two_handed) при надетом щите -> InventoryError, и щит при
#       надетом двуручном -> InventoryError (слоты не меняются);
#       доспех (не щит), категории которого нет в class.armor_training героя -> InventoryError
#       (щит на владение не проверяется)
#   equip(hero, item_id, registry, slot="main_hand") -- slot только для оружия: "main_hand" |
#       "off_hand" (аудит 1 п. 2.13); в off_hand только лёгкое (свойство light), иначе
#       InventoryError; off_hand не при щите и не при двуручном в main_hand; двуручное и щит --
#       не при оружии в off_hand
#   SLOTS = ("armor", "shield", "main_hand", "off_hand")
#   unequip(hero, slot: "armor" | "shield" | "main_hand" | "off_hand") -> str
#       слот -> None, возвращает id снятого; предмет остаётся в инвентаре; неизвестный слот и
#       пустой слот -> InventoryError
#   blocking_slots(hero, item_id, registry, slot="main_hand") -> list[str]
#       занятые слоты, из-за которых equip откажет (их снимают до equip)
#   ARMOR_MINUTES: категория доспеха -> (минут надеть, минут снять), SRD 5.2
#   equip: один предмет (qty 1) нельзя взять в обе руки; при двух копиях можно
#   use_item(hero, item_id, registry, rng) -> int
#       зелье лечения: бросок effects[0].dice через core.dice.roll_dice(expr, rng) -- первое, что
#       берётся из rng; hp_current = min(hp_max, hp_current + бросок); предмет убывает на 1;
#       возвращает фактически восстановленные HP. Нет предмета / не расходник ->
#       InventoryError (rng не трогается, инвентарь не меняется)
import pytest

from ai_dm.core.dice import roll_dice
from ai_dm.core.rng import Rng
from ai_dm.rules.inventory import (
    ARMOR_MINUTES,
    SLOTS,
    InventoryError,
    add_item,
    blocking_slots,
    count_item,
    equip,
    remove_item,
    unequip,
    use_item,
)
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_hero(hp_current=12):
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
        creature=CreatureState(hp_current=hp_current, hp_max=12),
    )


# добавить / убрать

def test_new_hero_has_no_items():
    assert count_item(make_hero(), "longsword") == 0


def test_add_item_puts_one_item():
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    assert count_item(hero, "longsword") == 1


def test_add_item_with_qty():
    hero = make_hero()
    add_item(hero, "potion_of_healing", 3, cost_cp=0)
    assert count_item(hero, "potion_of_healing") == 3


def test_add_same_item_twice_stacks():
    hero = make_hero()
    add_item(hero, "potion_of_healing", cost_cp=0)
    add_item(hero, "potion_of_healing", 2, cost_cp=0)
    assert count_item(hero, "potion_of_healing") == 3
    assert len(hero.inventory) == 1


def test_add_different_items_keeps_both():
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    add_item(hero, "shield", cost_cp=0)
    assert count_item(hero, "longsword") == 1
    assert count_item(hero, "shield") == 1


def test_add_zero_items_raises_error():
    with pytest.raises(InventoryError):
        add_item(make_hero(), "longsword", 0, cost_cp=0)


def test_add_negative_items_raises_error():
    with pytest.raises(InventoryError):
        add_item(make_hero(), "longsword", -1, cost_cp=0)


def test_inventory_error_is_value_error():
    assert issubclass(InventoryError, ValueError)


def test_remove_item_decreases_count():
    hero = make_hero()
    add_item(hero, "potion_of_healing", 3, cost_cp=0)
    remove_item(hero, "potion_of_healing")
    assert count_item(hero, "potion_of_healing") == 2


def test_remove_all_copies_drops_the_entry():
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    remove_item(hero, "longsword")
    assert count_item(hero, "longsword") == 0
    assert hero.inventory == []


def test_remove_more_than_owned_raises_error():
    hero = make_hero()
    add_item(hero, "potion_of_healing", 2, cost_cp=0)
    with pytest.raises(InventoryError):
        remove_item(hero, "potion_of_healing", 3)


def test_failed_remove_does_not_change_inventory():
    hero = make_hero()
    add_item(hero, "potion_of_healing", 2, cost_cp=0)
    with pytest.raises(InventoryError):
        remove_item(hero, "potion_of_healing", 3)
    assert count_item(hero, "potion_of_healing") == 2


def test_remove_missing_item_raises_error():
    with pytest.raises(InventoryError):
        remove_item(make_hero(), "longsword")


def test_remove_zero_raises_error():
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    with pytest.raises(InventoryError):
        remove_item(hero, "longsword", 0)


# экипировка

def test_equip_armor_goes_to_armor_slot(registry):
    hero = make_hero()
    add_item(hero, "chain_mail", cost_cp=0)
    equip(hero, "chain_mail", registry)
    assert hero.equipped.armor == "chain_mail"


def test_equip_shield_goes_to_shield_slot(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    equip(hero, "shield", registry)
    assert hero.equipped.shield == "shield"
    assert hero.equipped.armor is None


def test_equip_weapon_goes_to_main_hand(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    equip(hero, "longsword", registry)
    assert hero.equipped.main_hand == "longsword"


def test_equip_keeps_item_in_inventory(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    equip(hero, "longsword", registry)
    assert count_item(hero, "longsword") == 1


def test_equip_item_not_in_inventory_raises_error(registry):
    with pytest.raises(InventoryError):
        equip(make_hero(), "longsword", registry)


def test_failed_equip_leaves_slot_empty(registry):
    hero = make_hero()
    with pytest.raises(InventoryError):
        equip(hero, "longsword", registry)
    assert hero.equipped.main_hand is None


def test_equip_potion_raises_error(registry):
    hero = make_hero()
    add_item(hero, "potion_of_healing", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "potion_of_healing", registry)


def test_equip_second_armor_replaces_first(registry):
    hero = make_hero()
    add_item(hero, "leather_armor", cost_cp=0)
    add_item(hero, "chain_mail", cost_cp=0)
    equip(hero, "leather_armor", registry)
    equip(hero, "chain_mail", registry)
    assert hero.equipped.armor == "chain_mail"
    assert count_item(hero, "leather_armor") == 1


def test_equip_second_weapon_replaces_first(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    add_item(hero, "spear", cost_cp=0)
    equip(hero, "longsword", registry)
    equip(hero, "spear", registry)
    assert hero.equipped.main_hand == "spear"


def test_armor_and_shield_and_weapon_can_be_worn_together(registry):
    hero = make_hero()
    for item in ["chain_mail", "shield", "longsword"]:
        add_item(hero, item, cost_cp=0)
        equip(hero, item, registry)
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.shield == "shield"
    assert hero.equipped.main_hand == "longsword"


def test_removing_last_copy_of_worn_item_unequips_it(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    equip(hero, "longsword", registry)
    remove_item(hero, "longsword")
    assert hero.equipped.main_hand is None


def test_removing_one_of_two_copies_keeps_item_worn(registry):
    hero = make_hero()
    add_item(hero, "longsword", 2, cost_cp=0)
    equip(hero, "longsword", registry)
    remove_item(hero, "longsword")
    assert hero.equipped.main_hand == "longsword"


# зелье лечения

def test_potion_heals_by_2d4_plus_2(registry):
    hero = make_hero(hp_current=1)
    hero.creature.hp_max = 100
    add_item(hero, "potion_of_healing", cost_cp=0)
    expected = roll_dice("2d4+2", Rng(7)).total
    use_item(hero, "potion_of_healing", registry, Rng(7))
    assert hero.creature.hp_current == 1 + expected


def test_potion_returns_restored_hp(registry):
    hero = make_hero(hp_current=1)
    hero.creature.hp_max = 100
    add_item(hero, "potion_of_healing", cost_cp=0)
    expected = roll_dice("2d4+2", Rng(7)).total
    assert use_item(hero, "potion_of_healing", registry, Rng(7)) == expected


def test_potion_heal_is_between_4_and_10(registry):
    for seed in range(30):
        hero = make_hero(hp_current=1)
        hero.creature.hp_max = 100
        add_item(hero, "potion_of_healing", cost_cp=0)
        healed = use_item(hero, "potion_of_healing", registry, Rng(seed))
        assert 4 <= healed <= 10


def test_potion_does_not_heal_above_max_hp(registry):
    hero = make_hero(hp_current=11)
    add_item(hero, "potion_of_healing", cost_cp=0)
    use_item(hero, "potion_of_healing", registry, Rng(7))
    assert hero.creature.hp_current == 12


def test_potion_returns_only_actually_restored_hp(registry):
    hero = make_hero(hp_current=11)
    add_item(hero, "potion_of_healing", cost_cp=0)
    assert use_item(hero, "potion_of_healing", registry, Rng(7)) == 1


def test_potion_at_full_hp_restores_nothing_but_is_spent(registry):
    hero = make_hero(hp_current=12)
    add_item(hero, "potion_of_healing", cost_cp=0)
    assert use_item(hero, "potion_of_healing", registry, Rng(7)) == 0
    assert count_item(hero, "potion_of_healing") == 0


def test_potion_is_consumed(registry):
    hero = make_hero(hp_current=1)
    add_item(hero, "potion_of_healing", 2, cost_cp=0)
    use_item(hero, "potion_of_healing", registry, Rng(7))
    assert count_item(hero, "potion_of_healing") == 1


def test_potion_uses_rng_deterministically(registry):
    first = make_hero(hp_current=1)
    second = make_hero(hp_current=1)
    for hero in (first, second):
        hero.creature.hp_max = 100
        add_item(hero, "potion_of_healing", cost_cp=0)
    a = use_item(first, "potion_of_healing", registry, Rng(99))
    b = use_item(second, "potion_of_healing", registry, Rng(99))
    assert a == b


def test_use_missing_potion_raises_error_without_rolling(registry):
    rng = Rng(7)
    with pytest.raises(InventoryError):
        use_item(make_hero(hp_current=1), "potion_of_healing", registry, rng)
    assert rng.draws == 0


def test_use_non_consumable_raises_error_and_keeps_item(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    with pytest.raises(InventoryError):
        use_item(hero, "longsword", registry, Rng(7))
    assert count_item(hero, "longsword") == 1


# двуручное оружие и щит

def test_equip_two_handed_weapon_with_shield_raises_error(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "shield", registry)
    with pytest.raises(InventoryError):
        equip(hero, "greatsword", registry)


def test_equip_shield_with_two_handed_weapon_raises_error(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "greatsword", registry)
    with pytest.raises(InventoryError):
        equip(hero, "shield", registry)


def test_failed_two_handed_equip_leaves_slots_unchanged(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    add_item(hero, "longsword", cost_cp=0)
    equip(hero, "longsword", registry)
    equip(hero, "shield", registry)
    with pytest.raises(InventoryError):
        equip(hero, "greatsword", registry)
    assert hero.equipped.main_hand == "longsword"
    assert hero.equipped.shield == "shield"


def test_failed_shield_equip_with_two_handed_leaves_shield_slot_empty(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "greatsword", registry)
    with pytest.raises(InventoryError):
        equip(hero, "shield", registry)
    assert hero.equipped.shield is None
    assert hero.equipped.main_hand == "greatsword"


@pytest.mark.parametrize("weapon_id", ["shortbow", "light_crossbow"])
def test_equip_two_handed_ranged_weapon_with_shield_raises_error(registry, weapon_id):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, weapon_id, cost_cp=0)
    equip(hero, "shield", registry)
    with pytest.raises(InventoryError):
        equip(hero, weapon_id, registry)


@pytest.mark.parametrize("weapon_id", ["longsword", "spear", "shortsword", "dagger"])
def test_equip_one_handed_or_versatile_weapon_with_shield_is_ok(registry, weapon_id):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, weapon_id, cost_cp=0)
    equip(hero, "shield", registry)
    equip(hero, weapon_id, registry)
    assert hero.equipped.main_hand == weapon_id


def test_equip_two_handed_weapon_without_shield_is_ok(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "greatsword", registry)
    assert hero.equipped.main_hand == "greatsword"


def test_cleared_shield_slot_then_two_handed_weapon_is_ok(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "shield", registry)
    hero.equipped.shield = None
    equip(hero, "greatsword", registry)
    assert hero.equipped.main_hand == "greatsword"


# доспех без владения

def hero_of_class(class_id):
    hero = make_hero()
    hero.sheet.primary.class_id = class_id
    return hero


def test_wizard_equip_chain_mail_raises_error(registry):
    hero = hero_of_class("wizard")
    add_item(hero, "chain_mail", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "chain_mail", registry)
    assert hero.equipped.armor is None


def test_wizard_equip_leather_armor_raises_error(registry):
    hero = hero_of_class("wizard")
    add_item(hero, "leather_armor", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "leather_armor", registry)


def test_rogue_equip_chain_mail_raises_error(registry):
    hero = hero_of_class("rogue")
    add_item(hero, "chain_mail", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "chain_mail", registry)


def test_cleric_equip_chain_mail_raises_error(registry):
    hero = hero_of_class("cleric")
    add_item(hero, "chain_mail", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "chain_mail", registry)


def test_rogue_equip_leather_armor_is_ok(registry):
    hero = hero_of_class("rogue")
    add_item(hero, "leather_armor", cost_cp=0)
    equip(hero, "leather_armor", registry)
    assert hero.equipped.armor == "leather_armor"


def test_fighter_equip_chain_mail_is_ok(registry):
    hero = make_hero()
    add_item(hero, "chain_mail", cost_cp=0)
    equip(hero, "chain_mail", registry)
    assert hero.equipped.armor == "chain_mail"


def test_failed_armor_equip_keeps_previous_armor(registry):
    hero = hero_of_class("rogue")
    add_item(hero, "leather_armor", cost_cp=0)
    add_item(hero, "chain_mail", cost_cp=0)
    equip(hero, "leather_armor", registry)
    with pytest.raises(InventoryError):
        equip(hero, "chain_mail", registry)
    assert hero.equipped.armor == "leather_armor"


# левая рука: слот off_hand (аудит 1 п. 2.13)

def test_slots_include_off_hand():
    assert SLOTS == ("armor", "shield", "main_hand", "off_hand")


def test_equipped_has_off_hand_empty_by_default():
    assert make_hero().equipped.off_hand is None


@pytest.mark.parametrize("weapon_id", ["dagger", "shortsword", "scimitar"])
def test_equip_light_weapon_in_off_hand(registry, weapon_id):
    hero = make_hero()
    add_item(hero, weapon_id, cost_cp=0)
    equip(hero, weapon_id, registry, slot="off_hand")
    assert hero.equipped.off_hand == weapon_id
    assert hero.equipped.main_hand is None


def test_equip_off_hand_keeps_main_hand(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "longsword", registry)
    equip(hero, "dagger", registry, slot="off_hand")
    assert hero.equipped.main_hand == "longsword"
    assert hero.equipped.off_hand == "dagger"


def test_equip_default_slot_is_main_hand(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry)
    assert hero.equipped.main_hand == "dagger"
    assert hero.equipped.off_hand is None


def test_equip_non_light_weapon_in_off_hand_is_error(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "longsword", registry, slot="off_hand")
    assert hero.equipped.off_hand is None


def test_equip_two_handed_weapon_in_off_hand_is_error(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "greatsword", registry, slot="off_hand")


def test_equip_off_hand_weapon_stays_in_inventory(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    assert count_item(hero, "dagger") == 1


def test_equip_off_hand_without_item_in_inventory_is_error(registry):
    with pytest.raises(InventoryError):
        equip(make_hero(), "dagger", registry, slot="off_hand")


def test_equip_armor_with_slot_off_hand_does_not_use_off_hand(registry):
    hero = make_hero()
    add_item(hero, "chain_mail", cost_cp=0)
    equip(hero, "chain_mail", registry, slot="off_hand")
    assert hero.equipped.off_hand is None


def test_equip_unknown_slot_for_weapon_is_error(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    with pytest.raises(InventoryError):
        equip(hero, "dagger", registry, slot="head")


def test_equip_off_hand_with_shield_is_error(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "shield", registry)
    with pytest.raises(InventoryError):
        equip(hero, "dagger", registry, slot="off_hand")
    assert hero.equipped.off_hand is None


def test_equip_shield_with_off_hand_weapon_is_error(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    with pytest.raises(InventoryError):
        equip(hero, "shield", registry)
    assert hero.equipped.shield is None


def test_equip_off_hand_with_two_handed_main_hand_is_error(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "greatsword", registry)
    with pytest.raises(InventoryError):
        equip(hero, "dagger", registry, slot="off_hand")
    assert hero.equipped.off_hand is None


def test_equip_two_handed_weapon_with_off_hand_weapon_is_error(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    with pytest.raises(InventoryError):
        equip(hero, "greatsword", registry)
    assert hero.equipped.main_hand is None


def test_remove_last_copy_unequips_off_hand(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    remove_item(hero, "dagger")
    assert hero.equipped.off_hand is None


# unequip (шаг 96а)

def test_unequip_shield_empties_slot_and_returns_id(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    equip(hero, "shield", registry)
    assert unequip(hero, "shield") == "shield"
    assert hero.equipped.shield is None


def test_unequip_keeps_item_in_inventory(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    equip(hero, "shield", registry)
    unequip(hero, "shield")
    assert count_item(hero, "shield") == 1


@pytest.mark.parametrize(
    ("slot", "item_id"),
    [("armor", "chain_mail"), ("main_hand", "longsword"), ("off_hand", "dagger")],
)
def test_unequip_each_slot(registry, slot, item_id):
    hero = make_hero()
    add_item(hero, item_id, cost_cp=0)
    equip(hero, item_id, registry, slot=slot if slot == "off_hand" else "main_hand")
    assert unequip(hero, slot) == item_id
    assert getattr(hero.equipped, slot) is None


def test_unequip_one_slot_leaves_the_others(registry):
    hero = make_hero()
    for item in ("chain_mail", "shield", "longsword"):
        add_item(hero, item, cost_cp=0)
        equip(hero, item, registry)
    unequip(hero, "shield")
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.main_hand == "longsword"


def test_unequip_empty_slot_is_error():
    with pytest.raises(InventoryError) as raised:
        unequip(make_hero(), "shield")
    assert str(raised.value) == "слот пуст: shield"


def test_unequip_unknown_slot_is_error():
    with pytest.raises(InventoryError) as raised:
        unequip(make_hero(), "head")
    assert str(raised.value) == "нет такого слота: head"


# часы надевания доспехов (SRD 5.2)

def test_armor_minutes_follow_srd():
    assert ARMOR_MINUTES == {"light": (1, 1), "medium": (5, 1), "heavy": (10, 5)}


# один предмет в двух руках

def test_equip_same_single_item_in_both_hands_is_error(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry)
    with pytest.raises(InventoryError):
        equip(hero, "dagger", registry, slot="off_hand")
    assert hero.equipped.off_hand is None


def test_equip_same_single_item_main_hand_after_off_hand_is_error(registry):
    hero = make_hero()
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    with pytest.raises(InventoryError):
        equip(hero, "dagger", registry)
    assert hero.equipped.main_hand is None


def test_equip_two_copies_in_both_hands_is_ok(registry):
    hero = make_hero()
    add_item(hero, "dagger", 2, cost_cp=0)
    equip(hero, "dagger", registry)
    equip(hero, "dagger", registry, slot="off_hand")
    assert hero.equipped.main_hand == "dagger"
    assert hero.equipped.off_hand == "dagger"


# blocking_slots

def test_blocking_two_handed_lists_shield_and_off_hand(registry):
    hero = make_hero()
    for item in ("shield", "dagger", "greatsword"):
        add_item(hero, item, cost_cp=0)
    hero.equipped.shield = "shield"
    hero.equipped.off_hand = "dagger"
    assert blocking_slots(hero, "greatsword", registry) == ["shield", "off_hand"]


def test_blocking_two_handed_with_free_hands_is_empty(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    assert blocking_slots(hero, "greatsword", registry) == []


def test_blocking_two_handed_lists_only_occupied_slots(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "shield", registry)
    assert blocking_slots(hero, "greatsword", registry) == ["shield"]


def test_blocking_off_hand_weapon_lists_shield(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "shield", registry)
    assert blocking_slots(hero, "dagger", registry, "off_hand") == ["shield"]


def test_blocking_off_hand_weapon_lists_two_handed_main_hand(registry):
    hero = make_hero()
    add_item(hero, "greatsword", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "greatsword", registry)
    assert blocking_slots(hero, "dagger", registry, "off_hand") == ["main_hand"]


def test_blocking_off_hand_weapon_ignores_one_handed_main_hand(registry):
    hero = make_hero()
    add_item(hero, "longsword", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "longsword", registry)
    assert blocking_slots(hero, "dagger", registry, "off_hand") == []


def test_blocking_main_hand_weapon_ignores_shield(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "shield", registry)
    assert blocking_slots(hero, "dagger", registry) == []


def test_blocking_shield_lists_off_hand_weapon(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "dagger", cost_cp=0)
    equip(hero, "dagger", registry, slot="off_hand")
    assert blocking_slots(hero, "shield", registry) == ["off_hand"]


def test_blocking_shield_lists_two_handed_main_hand(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "greatsword", registry)
    assert blocking_slots(hero, "shield", registry) == ["main_hand"]


def test_blocking_shield_ignores_one_handed_main_hand(registry):
    hero = make_hero()
    add_item(hero, "shield", cost_cp=0)
    add_item(hero, "longsword", cost_cp=0)
    equip(hero, "longsword", registry)
    assert blocking_slots(hero, "shield", registry) == []


def test_blocking_armor_is_empty(registry):
    hero = make_hero()
    add_item(hero, "chain_mail", cost_cp=0)
    add_item(hero, "greatsword", cost_cp=0)
    equip(hero, "greatsword", registry)
    assert blocking_slots(hero, "chain_mail", registry) == []


def test_blocking_unknown_item_is_empty(registry):
    assert blocking_slots(make_hero(), "no_such_item", registry) == []


def test_equip_passes_after_unequipping_the_blockers(registry):
    hero = make_hero()
    for item in ("shield", "dagger", "greatsword"):
        add_item(hero, item, cost_cp=0)
    hero.equipped.shield = "shield"
    hero.equipped.off_hand = "dagger"
    with pytest.raises(InventoryError):
        equip(hero, "greatsword", registry)
    for slot in blocking_slots(hero, "greatsword", registry):
        unequip(hero, slot)
    equip(hero, "greatsword", registry)
    assert hero.equipped.main_hand == "greatsword"

