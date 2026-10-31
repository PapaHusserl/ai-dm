# Б1а (B1-PLAN A1, A5): стартовые наборы классов -- целостность данных и сборка героя с набором.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "rules"))

from test_builder import fighter_choices, wizard_choices  # noqa: E402

from ai_dm.game.starter import ranger_choices  # noqa: E402
from ai_dm.rules.builder import CharacterChoices, ValidationErrors, build_character  # noqa: E402
from ai_dm.rules.inventory import find_item  # noqa: E402
from ai_dm.state.hero import HeroState  # noqa: E402

CLASSES = ["fighter", "rogue", "cleric", "wizard", "ranger"]


def rogue_choices(**changes):
    return CharacterChoices(
        name="Тень", species_id="human", class_id="rogue", background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 15, "con": 14, "int": 10, "wis": 12, "cha": 13},
        background_bonus={"dex": 2, "con": 1},
        class_skills=["acrobatics", "insight", "perception", "stealth"],
        weapon_masteries=["dagger", "shortsword"], expertise=["stealth", "perception"],
        species_choices={"skill": "persuasion", "feat": "skilled"},
        feat_choices={"skilled": ["investigation", "history", "medicine"]},
    ).model_copy(update=changes)


def cleric_choices(**changes):
    return CharacterChoices(
        name="Отец Марк", species_id="human", class_id="cleric", background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 10, "dex": 8, "con": 14, "int": 12, "wis": 15, "cha": 13},
        background_bonus={"str": 2, "con": 1}, class_skills=["history", "insight"],
        weapon_masteries=[],
        species_choices={"skill": "stealth", "feat": "skilled"},
        feat_choices={"skilled": ["medicine", "religion", "nature"]},
    ).model_copy(update=changes)


def minimal_choices(class_id, kit):
    if class_id == "fighter":
        return fighter_choices(inventory=[], equip=[], class_kit=kit)
    if class_id == "wizard":
        return wizard_choices(class_kit=kit)
    if class_id == "ranger":
        return ranger_choices("hero").model_copy(
            update={"inventory": [], "equip": [], "class_kit": kit}
        )
    if class_id == "rogue":
        return rogue_choices(class_kit=kit)
    return cleric_choices(class_kit=kit)


def all_kits(registry):
    return [(cid, kit) for cid in CLASSES for kit in registry.get("class", cid).starting_kits]


@pytest.mark.parametrize("class_id", CLASSES)
def test_class_has_at_least_one_kit(registry, class_id):
    assert len(registry.get("class", class_id).starting_kits) >= 1


@pytest.mark.parametrize("class_id", CLASSES)
def test_kit_ids_are_unique_within_class(registry, class_id):
    ids = [k.id for k in registry.get("class", class_id).starting_kits]
    assert len(ids) == len(set(ids))


@pytest.mark.parametrize("class_id", CLASSES)
def test_every_class_has_kit_a(registry, class_id):
    ids = [k.id for k in registry.get("class", class_id).starting_kits]
    assert "a" in ids


def test_all_kit_items_are_found_in_catalog(registry):
    for class_id, kit in all_kits(registry):
        for item_id in kit.items:
            assert find_item(registry, item_id) is not None, (class_id, kit.id, item_id)


def test_equip_is_subset_of_items(registry):
    for class_id, kit in all_kits(registry):
        assert set(kit.equip) <= set(kit.items), (class_id, kit.id)


def test_equipped_things_are_armor_or_weapon(registry):
    for class_id, kit in all_kits(registry):
        for item_id in kit.equip:
            assert find_item(registry, item_id)[0] in ("armor", "weapon"), (class_id, item_id)


def test_gold_is_not_negative(registry):
    for class_id, kit in all_kits(registry):
        assert kit.gold_cp >= 0, (class_id, kit.id)


def test_kit_with_no_items_has_gold(registry):
    for class_id, kit in all_kits(registry):
        if not kit.items:
            assert kit.gold_cp > 0, (class_id, kit.id)


def test_plan_table_kit_counts(registry):
    counts = {c: len(registry.get("class", c).starting_kits) for c in CLASSES}
    assert counts == {"fighter": 3, "rogue": 2, "cleric": 2, "wizard": 2, "ranger": 2}


def test_plan_table_gold(registry):
    gold = {
        (c, k.id): k.gold_cp for c in CLASSES for k in registry.get("class", c).starting_kits
    }
    assert gold[("fighter", "a")] == 400
    assert gold[("fighter", "c")] == 15500
    assert gold[("rogue", "b")] == 10000
    assert gold[("cleric", "b")] == 11000
    assert gold[("wizard", "b")] == 5500
    assert gold[("ranger", "b")] == 15000


def test_every_class_builds_with_kit_a(registry):
    for class_id in CLASSES:
        hero = build_character(minimal_choices(class_id, "a"), registry)
        assert isinstance(hero, HeroState), (class_id, getattr(hero, "messages", None))


def test_every_kit_of_every_class_builds(registry):
    for class_id, kit in all_kits(registry):
        hero = build_character(minimal_choices(class_id, kit.id), registry)
        assert isinstance(hero, HeroState), (class_id, kit.id, getattr(hero, "messages", None))


def test_built_hero_has_kit_items(registry):
    for class_id, kit in all_kits(registry):
        hero = build_character(minimal_choices(class_id, kit.id), registry)
        have = {e.item_id for e in hero.inventory}
        assert set(kit.items) <= have, (class_id, kit.id)


def test_built_hero_has_kit_equipment_on(registry):
    for class_id, kit in all_kits(registry):
        hero = build_character(minimal_choices(class_id, kit.id), registry)
        worn = {hero.equipped.armor, hero.equipped.shield, hero.equipped.main_hand,
                hero.equipped.off_hand}
        assert set(kit.equip) <= worn, (class_id, kit.id)


def fighter_kit(registry, kit_id):
    kits = registry.get("class", "fighter").starting_kits
    return next(k for k in kits if k.id == kit_id)


def test_fighter_kit_a_has_flail_and_eight_javelins(registry):
    items = fighter_kit(registry, "a").items
    assert items.count("flail") == 1
    assert items.count("javelin") == 8


def test_fighter_kit_a_has_no_spear(registry):
    assert "spear" not in fighter_kit(registry, "a").items


def test_fighter_kit_a_keeps_chain_mail_greatsword_and_gold(registry):
    kit = fighter_kit(registry, "a")
    assert {"chain_mail", "greatsword", "explorers_pack"} <= set(kit.items)
    assert kit.gold_cp == 400


def test_fighter_kit_a_has_no_firearms(registry):
    items = fighter_kit(registry, "a").items
    assert "musket" not in items and "pistol" not in items


def test_minimal_rogue_without_kit_is_not_a_validation_error(registry):
    assert not isinstance(build_character(rogue_choices(), registry), ValidationErrors)
