# Партия К7к, п. 4.2: герои сетки sim_grid (docs/K7K-PLAN.md, В8а, Q5а).
#   CLASSES = ("fighter", "rogue", "cleric", "wizard", "ranger");
#   level1_choices(class_id) -> CharacterChoices (hero_id "hero"): воин / волшебник / следопыт --
#     из game.starter; жрец и плут -- свои наборы (человек, стандартный массив, class_kit "a");
#     неизвестный класс -> ValueError; build_character на них проходит без ошибок;
#   auto_level(hero, registry, level): поднимает героя до level (средние HP), в каждом выборе --
#     первый вариант (боевой стиль, экспертиза, подкласс, умения, первое заклинание-кандидат,
#     повышение характеристик "<первая>+2"); ошибка применения -> ValueError; детерминированно;
#   build_hero(class_id, level, registry) -> HeroState; ошибка сборки героя 1 ур. -> ValueError.
#   Заклинаний у жреца и волшебника берётся столько, сколько есть кандидатов в данных SRD (их
#   меньше лимита).
import pytest

from ai_dm.devtools import grid_heroes
from ai_dm.devtools.grid_heroes import CLASSES, auto_level, build_hero, level1_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.derived import armor_class

# класс: (КД, HP, доспех, щит) героя 1 уровня
LEVEL1 = {
    "fighter": (19, 12, "chain_mail", "shield"),
    "rogue": (14, 10, "leather_armor", None),
    "cleric": (13, 10, "studded_leather", "shield"),
    "wizard": (11, 8, None, None),
    "ranger": (15, 11, "studded_leather", None),
}


def test_classes_are_the_five_srd_classes():
    assert CLASSES == ("fighter", "rogue", "cleric", "wizard", "ranger")


@pytest.mark.parametrize("class_id", CLASSES)
def test_level1_choices_build_a_character(registry, class_id):
    hero = build_character(level1_choices(class_id), registry)
    assert hasattr(hero, "sheet")
    assert hero.sheet.class_id == class_id
    assert hero.sheet.level == 1
    assert hero.id == "hero"


@pytest.mark.parametrize("class_id", CLASSES)
def test_level1_hero_has_expected_ac_hp_and_gear(registry, class_id):
    ac, hit_points, armor, shield = LEVEL1[class_id]
    hero = build_hero(class_id, 1, registry)
    assert armor_class(hero, registry) == ac
    assert hero.creature.hp_max == hit_points
    assert hero.creature.hp_current == hit_points
    assert (hero.equipped.armor, hero.equipped.shield) == (armor, shield)


def test_cleric_wears_studded_leather_and_a_shield():
    choices = level1_choices("cleric")
    assert choices.class_kit == "a"
    assert choices.species_id == "human"
    assert choices.ability_method == "standard_array"


def test_cleric_knows_bless_and_cure_wounds(registry):
    hero = build_hero("cleric", 1, registry)
    assert hero.sheet.prepared_of() == ["bless", "cure_wounds"]


def test_rogue_holds_a_weapon_in_hand(registry):
    hero = build_hero("rogue", 1, registry)
    assert hero.equipped.main_hand is not None
    assert hero.equipped.armor == "leather_armor"


def test_fighter_wizard_ranger_use_the_starter_choices():
    from ai_dm.game import starter

    assert level1_choices("fighter") == starter.fighter_choices("hero")
    assert level1_choices("wizard") == starter.wizard_choices("hero")
    assert level1_choices("ranger") == starter.ranger_choices("hero")


def test_unknown_class_raises():
    with pytest.raises(ValueError):
        level1_choices("bard")


def test_build_hero_with_unknown_class_raises(registry):
    with pytest.raises(ValueError):
        build_hero("bard", 1, registry)


def test_build_hero_reports_build_errors(registry, monkeypatch):
    class Failed:
        messages = ["плохой лист"]

    monkeypatch.setattr(grid_heroes, "build_character", lambda choices, reg: Failed())
    with pytest.raises(ValueError) as exc:
        build_hero("fighter", 1, registry)
    assert "fighter" in str(exc.value)
    assert "плохой лист" in str(exc.value)


# подъём

@pytest.mark.parametrize("class_id", CLASSES)
@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_build_hero_reaches_the_level(registry, class_id, level):
    hero = build_hero(class_id, level, registry)
    assert hero.sheet.level == level
    assert hero.sheet.level_history == [class_id] * level


@pytest.mark.parametrize("class_id", CLASSES)
def test_hit_points_grow_every_level(registry, class_id):
    maxima = [build_hero(class_id, level, registry).creature.hp_max for level in range(1, 6)]
    assert maxima == sorted(set(maxima))


@pytest.mark.parametrize("class_id", CLASSES)
def test_level_up_fills_hit_points(registry, class_id):
    hero = build_hero(class_id, 5, registry)
    assert hero.creature.hp_current == hero.creature.hp_max


@pytest.mark.parametrize("class_id", CLASSES)
def test_asi_at_level_4_adds_two_to_the_first_ability(registry, class_id):
    before = build_hero(class_id, 3, registry).sheet.abilities
    after = build_hero(class_id, 4, registry).sheet.abilities
    assert after["str"] == before["str"] + 2
    assert {k: v for k, v in after.items() if k != "str"} == {
        k: v for k, v in before.items() if k != "str"
    }


@pytest.mark.parametrize("class_id", CLASSES)
def test_abilities_do_not_change_before_level_4(registry, class_id):
    one = build_hero(class_id, 1, registry).sheet.abilities
    three = build_hero(class_id, 3, registry).sheet.abilities
    assert one == three


def test_ranger_gets_the_first_subclass_at_level_3(registry):
    assert build_hero("ranger", 2, registry).sheet.subclass_id is None
    hero = build_hero("ranger", 3, registry)
    assert hero.sheet.subclass_id == sorted(
        s.id for s in registry.subclasses_of("ranger")
    )[0]


def test_ranger_gets_expertise_and_fighting_style(registry):
    sheet = build_hero("ranger", 2, registry).sheet
    assert len(sheet.skill_expertise) == 1
    assert "archery" in sheet.feats


def test_other_classes_have_no_subclass(registry):
    for class_id in ("fighter", "rogue", "cleric", "wizard"):
        assert build_hero(class_id, 5, registry).sheet.subclass_id is None


def test_wizard_and_cleric_prepare_all_available_spells(registry):
    for class_id in ("wizard", "cleric"):
        hero = build_hero(class_id, 5, registry)
        assert len(hero.sheet.prepared_of()) > len(
            build_hero(class_id, 1, registry).sheet.prepared_of()
        )


def test_cleric_prepares_every_cleric_spell_of_the_data(registry):
    hero = build_hero("cleric", 5, registry)
    assert {"bless", "cure_wounds", "lesser_restoration"} <= set(hero.sheet.prepared_of())


def test_auto_level_keeps_the_hero_when_the_level_is_reached(registry):
    hero = build_hero("fighter", 3, registry)
    before = hero.model_dump()
    auto_level(hero, registry, 3)
    assert hero.model_dump() == before


def test_auto_level_continues_from_the_current_level(registry):
    hero = build_hero("fighter", 2, registry)
    auto_level(hero, registry, 5)
    assert hero.model_dump() == build_hero("fighter", 5, registry).model_dump()


@pytest.mark.parametrize("class_id", CLASSES)
def test_build_hero_is_deterministic(registry, class_id):
    one = build_hero(class_id, 5, registry)
    two = build_hero(class_id, 5, registry)
    assert one.model_dump() == two.model_dump()


def test_auto_level_reports_apply_errors(registry, monkeypatch):
    class Failed:
        messages = ["нельзя"]

    hero = build_hero("fighter", 1, registry)
    monkeypatch.setattr(grid_heroes, "apply_level_choices", lambda *args: Failed())
    with pytest.raises(ValueError) as exc:
        auto_level(hero, registry, 2)
    assert "fighter" in str(exc.value)
    assert "нельзя" in str(exc.value)


def test_fighter_gets_the_first_fighting_style_option_at_level_1(registry):
    hero = build_hero("fighter", 1, registry)
    assert "defense" in hero.sheet.feats
