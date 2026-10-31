# К0б (K0-PLAN A8, B3): пять классов проходят уровни 1-20 по данным классов.
#   * ПХ (asi_or_feat) на 4/8/12/16/19; воину добавочно 6/14, плуту 10;
#   * подкласс на 3-м только у классов с подклассами в данных (сейчас следопыт);
#   * ячейки на 20: полный заклинатель -- 9-й круг, половинный -- 5-й;
#   * prepared_limit (Q10): жрец 22, волшебник 25, следопыт 15 на 20-м;
#   * умение «повышение характеристик» повторяется в hero_feature_ids по числу строк класса.
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content"))

from test_class_kits import minimal_choices, rogue_choices  # noqa: E402

from ai_dm.content.models.common import ABILITIES  # noqa: E402
from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.derived import (  # noqa: E402
    ability_mod,
    hero_feature_ids,
    prepared_limit,
    proficiency,
    resource_maxes,
    skill_bonus,
    spell_slots,
    weapon_proficient,
)
from ai_dm.rules.inventory import add_item  # noqa: E402
from ai_dm.rules.progression import (  # noqa: E402
    FIXED_CHOICES,
    apply_level_choices,
    choice_errors,
    choice_options,
    expertise_due,
    expertise_total,
    level_up,
    mastery_candidates,
    missing_choices,
    needed_choices,
    next_choice,
    required_choices,
)
from ai_dm.state.hero import LevelChoices  # noqa: E402

CLASSES = ["fighter", "rogue", "cleric", "wizard", "ranger"]
ASI_LEVELS = {
    "fighter": [4, 6, 8, 12, 14, 16, 19],
    "rogue": [4, 8, 10, 12, 16, 19],
    "cleric": [4, 8, 12, 16, 19],
    "wizard": [4, 8, 12, 16, 19],
    "ranger": [4, 8, 12, 16, 19],
}
PREPARED = {
    "cleric": [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 17, 18, 18, 19, 20, 21, 22],
    "wizard": [4, 5, 6, 7, 9, 10, 11, 12, 14, 15, 16, 16, 17, 18, 19, 21, 22, 23, 24, 25],
    "ranger": [2, 3, 4, 5, 6, 6, 7, 7, 9, 9, 10, 10, 11, 11, 12, 12, 14, 14, 15, 15],
}


def make_hero(registry, class_id):
    kit = registry.get("class", class_id).starting_kits[0].id
    return build_character(minimal_choices(class_id, kit), registry)


def pick_choices(hero, registry, level):
    # выборы уровня: первые доступные варианты, ПХ -- в самую слабую характеристику
    needed = required_choices(hero, registry, level)
    choices = LevelChoices(level=level)
    if "fighting_style" in needed:
        choices.fighting_style = choice_options(hero, registry, "fighting_style")[0]
    if "expertise" in needed:
        choices.expertise = choice_options(hero, registry, "expertise")[:1]
    if "weapon_mastery" in needed:
        options = choice_options(hero, registry, "weapon_mastery", choices)
        choices.feature_choices["weapon_mastery"] = options[:1]
    if "subclass" in needed:
        choices.subclass_id = choice_options(hero, registry, "subclass")[0]
    for feature_id in sorted(needed_choices(hero, registry, choices) - FIXED_CHOICES):
        choices.feature_choices[feature_id] = choice_options(hero, registry, feature_id)[:1]
    if "asi_or_feat" in needed:
        weakest = min(ABILITIES, key=lambda name: hero.sheet.abilities[name])
        choices.asi = {weakest: 2}
    return choices


def climb(registry, class_id):
    # уровни 2..20 через level_up(average) + apply_level_choices
    hero = make_hero(registry, class_id)
    needed_by_level = {}
    errors = []
    while hero.sheet.level < 20:
        level_up(hero, registry, hp_method="average")
        level = hero.sheet.level
        needed_by_level[level] = required_choices(hero, registry, level)
        result = apply_level_choices(hero, registry, pick_choices(hero, registry, level))
        if result is not None:
            errors.append((level, result.codes))
    return hero, needed_by_level, errors


@pytest.fixture(scope="module")
def climbs(registry):
    return {class_id: climb(registry, class_id) for class_id in CLASSES}


@pytest.mark.parametrize("class_id", CLASSES)
def test_class_reaches_level_20(class_id, climbs):
    assert climbs[class_id][0].sheet.level == 20


@pytest.mark.parametrize("class_id", CLASSES)
def test_climb_to_20_has_no_validation_errors(class_id, climbs):
    assert climbs[class_id][2] == []


@pytest.mark.parametrize("class_id", CLASSES)
def test_asi_is_required_exactly_on_asi_levels(class_id, climbs):
    needed = climbs[class_id][1]
    levels = [level for level, keys in sorted(needed.items()) if "asi_or_feat" in keys]
    assert levels == ASI_LEVELS[class_id]


@pytest.mark.parametrize("class_id", CLASSES)
def test_no_ability_goes_above_20(class_id, climbs):
    assert max(climbs[class_id][0].sheet.abilities.values()) <= 20


@pytest.mark.parametrize("class_id", CLASSES)
def test_asi_levels_raise_abilities_by_two_points_each(class_id, climbs, registry):
    base = sum(make_hero(registry, class_id).sheet.abilities.values())
    now = sum(climbs[class_id][0].sheet.abilities.values())
    assert now - base == 2 * len(ASI_LEVELS[class_id])


@pytest.mark.parametrize("class_id", CLASSES)
def test_subclass_is_required_on_level_3_only_with_subclasses_in_data(class_id, climbs, registry):
    has_subclasses = bool(registry.subclasses_of(class_id))
    assert ("subclass" in climbs[class_id][1][3]) is has_subclasses


def test_ranger_has_subclasses_in_data(registry):
    assert registry.subclasses_of("ranger")


@pytest.mark.parametrize("class_id", CLASSES)
def test_subclass_is_not_required_on_other_levels(class_id, climbs):
    others = [lvl for lvl, keys in climbs[class_id][1].items() if "subclass" in keys and lvl != 3]
    assert others == []


@pytest.mark.parametrize("class_id", ["cleric", "wizard"])
def test_full_caster_gets_9th_circle_at_20(class_id, climbs, registry):
    assert max(spell_slots(climbs[class_id][0], registry)) == 9


def test_ranger_gets_5th_circle_at_20(climbs, registry):
    assert max(spell_slots(climbs["ranger"][0], registry)) == 5


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
def test_non_caster_has_no_slots_at_20(class_id, climbs, registry):
    assert spell_slots(climbs[class_id][0], registry) == {}


@pytest.mark.parametrize("class_id, limit", [("cleric", 22), ("wizard", 25), ("ranger", 15)])
def test_prepared_limit_at_20(class_id, limit, climbs, registry):
    assert prepared_limit(climbs[class_id][0], registry) == limit


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
def test_non_caster_has_no_prepared_limit(class_id, climbs, registry):
    assert prepared_limit(climbs[class_id][0], registry) is None


@pytest.mark.parametrize("class_id", sorted(PREPARED))
@pytest.mark.parametrize("level", range(1, 21))
def test_prepared_limit_by_level(class_id, level, registry):
    hero = make_hero(registry, class_id)
    hero.sheet.primary.level = level
    assert prepared_limit(hero, registry) == PREPARED[class_id][level - 1]


@pytest.mark.parametrize("class_id", CLASSES)
def test_proficiency_bonus_is_6_at_20(class_id, climbs, registry):
    assert proficiency(climbs[class_id][0], registry) == 6


@pytest.mark.parametrize("class_id", CLASSES)
def test_asi_feature_repeats_by_number_of_class_rows(class_id, climbs, registry):
    hero = climbs[class_id][0]
    ids = hero_feature_ids(hero, registry)
    assert ids.count("ability_score_improvement") == len(ASI_LEVELS[class_id])


@pytest.mark.parametrize("class_id", CLASSES)
def test_class_data_has_asi_rows_exactly_on_asi_levels(class_id, registry):
    rows = registry.get("class", class_id).features
    levels = sorted(r.level for r in rows if r.feature == "ability_score_improvement")
    assert levels == ASI_LEVELS[class_id]


@pytest.mark.parametrize("class_id", CLASSES)
def test_hp_max_grows_every_level(class_id, climbs, registry):
    start = make_hero(registry, class_id).creature.hp_max
    assert climbs[class_id][0].creature.hp_max >= start + 19


# К2 П1: воин и плут -- мастерство оружия по уровням, экспертиза плута, умения, ресурсы


def hero_at(registry, class_id, level, apply_last=True):
    # герой на level: выборы прошлых уровней применены; последнего -- только если apply_last
    hero = make_hero(registry, class_id)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
        if hero.sheet.level < level or apply_last:
            apply_level_choices(hero, registry, pick_choices(hero, registry, hero.sheet.level))
    return hero


def mastery_codes(hero, registry, picks, level):
    choices = LevelChoices(level=level, feature_choices={"weapon_mastery": picks})
    errors = choice_errors(hero, registry, choices)
    return [code for code, _ in errors if code.startswith("mastery")]


def test_fighter_level_4_requires_asi_and_weapon_mastery(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert required_choices(hero, registry, 4) == {"asi_or_feat", "weapon_mastery"}


@pytest.mark.parametrize("level", [10, 16])
def test_fighter_weapon_mastery_is_required_on_growth_levels(level, climbs):
    assert "weapon_mastery" in climbs["fighter"][1][level]


@pytest.mark.parametrize("level", [2, 3, 5, 6, 8, 12])
def test_fighter_weapon_mastery_is_not_required_on_other_levels(level, climbs):
    assert "weapon_mastery" not in climbs["fighter"][1][level]


def test_fighter_has_four_masteries_after_level_4(registry):
    assert len(hero_at(registry, "fighter", 4).sheet.weapon_masteries) == 4


def test_fighter_has_six_masteries_at_20(climbs):
    assert len(climbs["fighter"][0].sheet.weapon_masteries) == 6


def test_fighter_masteries_have_no_repeats_at_20(climbs):
    masteries = climbs["fighter"][0].sheet.weapon_masteries
    assert len(set(masteries)) == len(masteries)


def test_rogue_masteries_do_not_grow(climbs):
    assert len(climbs["rogue"][0].sheet.weapon_masteries) == 2


def test_missing_choices_at_level_4_name_the_mastery(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert "не выбрано мастерство оружия" in missing_choices(hero, registry, LevelChoices(level=4))


def test_next_choice_at_level_4_is_mastery_before_asi(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert next_choice(hero, registry, LevelChoices(level=4)) == "weapon_mastery"


def test_next_choice_at_level_4_moves_to_asi_after_the_mastery_is_picked(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    choices = LevelChoices(level=4, feature_choices={"weapon_mastery": ["battleaxe"]})
    assert next_choice(hero, registry, choices) == "asi_or_feat"


def weapon(weapon_id, source="srd-5.2", mastery="cleave"):
    return SimpleNamespace(
        id=weapon_id, source=source, mastery=mastery, world_only=False,
        category="martial", properties=[],
    )


def test_mastery_candidates_skip_world_weapons_even_with_mastery():
    char_class = SimpleNamespace(weapon_training=["martial"], weapon_training_properties=[])
    stub = StubRegistry(
        char_class=char_class, weapons=[weapon("axe"), weapon("blaster", source="world")],
    )
    hero = SimpleNamespace(
        sheet=SimpleNamespace(class_id="fighter", weapon_masteries=[]), inventory=[],
    )
    assert mastery_candidates(hero, stub, None) == ["axe"]


def test_new_mastery_of_another_weapon_is_accepted(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert mastery_codes(hero, registry, ["battleaxe"], 4) == []


def test_repeated_mastery_is_an_error(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    taken = hero.sheet.weapon_masteries[0]
    assert mastery_codes(hero, registry, [taken], 4) == ["mastery_weapon_invalid"]


def test_two_new_masteries_on_level_4_are_too_many(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert "mastery_count_invalid" in mastery_codes(hero, registry, ["battleaxe", "mace"], 4)


def test_duplicate_picks_in_one_choice_are_an_error(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert "mastery_count_invalid" in mastery_codes(hero, registry, ["mace", "mace"], 4)


def test_mastery_on_a_level_without_growth_is_an_error(registry):
    hero = hero_at(registry, "fighter", 5, apply_last=False)
    assert mastery_codes(hero, registry, ["battleaxe"], 5) == ["mastery_count_invalid"]


def test_mastery_of_unknown_weapon_is_an_error(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert mastery_codes(hero, registry, ["no_such_weapon"], 4) == ["mastery_weapon_invalid"]


def test_firearm_mastery_without_the_weapon_in_inventory_is_an_error(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert mastery_codes(hero, registry, ["musket"], 4) == ["mastery_weapon_invalid"]


def test_firearm_mastery_with_the_weapon_in_inventory_is_accepted(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    add_item(hero, "musket", cost_cp=0)
    assert mastery_codes(hero, registry, ["musket"], 4) == []


def test_mastery_options_hide_firearm_not_in_inventory(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    assert "musket" not in choice_options(hero, registry, "weapon_mastery")


def test_mastery_options_show_firearm_from_inventory(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    add_item(hero, "pistol", cost_cp=0)
    assert "pistol" in choice_options(hero, registry, "weapon_mastery")


def test_mastery_options_skip_taken_weapons(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    options = choice_options(hero, registry, "weapon_mastery")
    assert not set(options) & set(hero.sheet.weapon_masteries)


def test_mastery_options_skip_weapons_picked_in_this_choice(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    choices = LevelChoices(level=4, feature_choices={"weapon_mastery": ["battleaxe"]})
    assert "battleaxe" not in choice_options(hero, registry, "weapon_mastery", choices)


def test_apply_moves_picked_mastery_to_the_sheet_and_not_to_feature_choices(registry):
    hero = hero_at(registry, "fighter", 4, apply_last=False)
    choices = LevelChoices(
        level=4, feature_choices={"weapon_mastery": ["battleaxe"]}, asi={"str": 2},
    )
    assert apply_level_choices(hero, registry, choices) is None
    assert "battleaxe" in hero.sheet.weapon_masteries
    assert "weapon_mastery" not in hero.sheet.feature_choices


def test_rogue_has_no_weapon_mastery_choice(climbs):
    assert all("weapon_mastery" not in keys for keys in climbs["rogue"][1].values())


@pytest.mark.parametrize("level, pool", [(1, 2), (2, 2), (3, 2), (4, 3), (5, 3)])
def test_second_wind_pool_by_level(registry, level, pool):
    hero = make_hero(registry, "fighter")
    hero.sheet.primary.level = level
    assert resource_maxes(hero, registry)["second_wind"] == pool


def test_action_surge_appears_on_level_2_with_one_use(registry):
    hero = make_hero(registry, "fighter")
    assert "action_surge" not in resource_maxes(hero, registry)
    hero.sheet.primary.level = 2
    assert resource_maxes(hero, registry)["action_surge"] == 1


def test_fighter_level_5_has_extra_attack_and_tactical_shift(registry):
    ids = hero_feature_ids(hero_at(registry, "fighter", 5), registry)
    assert {"extra_attack", "tactical_shift", "action_surge", "tactical_mind"} <= set(ids)


def test_fighter_level_4_has_no_extra_attack(registry):
    assert "extra_attack" not in hero_feature_ids(hero_at(registry, "fighter", 4), registry)


def test_champion_on_level_3_gets_improved_critical_and_remarkable_athlete(registry):
    hero = hero_at(registry, "fighter", 3)
    assert hero.sheet.subclass_id == "champion"
    ids = hero_feature_ids(hero, registry)
    assert {"improved_critical", "remarkable_athlete"} <= set(ids)


def test_fighter_level_2_requires_nothing(registry):
    hero = hero_at(registry, "fighter", 2, apply_last=False)
    assert required_choices(hero, registry, 2) == set()


def test_fighter_level_3_requires_only_subclass(registry):
    hero = hero_at(registry, "fighter", 3, apply_last=False)
    assert required_choices(hero, registry, 3) == {"subclass"}


def test_rogue_level_3_requires_only_subclass(registry):
    hero = hero_at(registry, "rogue", 3, apply_last=False)
    assert required_choices(hero, registry, 3) == {"subclass"}


def test_thief_on_level_3_gets_fast_hands(registry):
    hero = hero_at(registry, "rogue", 3)
    assert hero.sheet.subclass_id == "thief"
    assert "fast_hands" in hero_feature_ids(hero, registry)


def test_rogue_level_5_has_cunning_strike_and_uncanny_dodge(registry):
    ids = hero_feature_ids(hero_at(registry, "rogue", 5), registry)
    assert {"cunning_strike", "uncanny_dodge", "steady_aim", "cunning_action"} <= set(ids)


def test_rogue_level_5_has_no_choice_for_cunning_strike(registry):
    hero = hero_at(registry, "rogue", 5, apply_last=False)
    assert required_choices(hero, registry, 5) == set()


def test_rogue_has_two_expertise_skills_after_building(registry):
    assert len(make_hero(registry, "rogue").sheet.skill_expertise) == 2


def test_rogue_keeps_two_expertise_skills_to_level_20(climbs):
    assert len(climbs["rogue"][0].sheet.skill_expertise) == 2


def test_rogue_level_2_requires_no_expertise_when_it_was_chosen(registry):
    hero = hero_at(registry, "rogue", 2, apply_last=False)
    assert "expertise" not in required_choices(hero, registry, 2)


def test_fighter_never_requires_expertise(climbs):
    assert all("expertise" not in keys for keys in climbs["fighter"][1].values())


def test_rogue_without_expertise_gets_two_picks_on_level_2_then_nothing(registry):
    hero = make_hero(registry, "rogue")
    hero.sheet.skill_expertise = []
    level_up(hero, registry, hp_method="average")
    choices = LevelChoices(level=2)
    assert next_choice(hero, registry, choices) == "expertise"
    choices.expertise = ["stealth"]
    assert next_choice(hero, registry, choices) == "expertise"
    choices.expertise = ["stealth", "perception"]
    assert next_choice(hero, registry, choices) is None


def test_rogue_with_one_expertise_gets_one_pick_on_level_2(registry):
    hero = make_hero(registry, "rogue")
    hero.sheet.skill_expertise = ["stealth"]
    level_up(hero, registry, hp_method="average")
    choices = LevelChoices(level=2, expertise=["perception"])
    assert next_choice(hero, registry, choices) is None


def test_rogue_expertise_options_skip_taken_and_picked(registry):
    hero = make_hero(registry, "rogue")
    hero.sheet.skill_expertise = []
    level_up(hero, registry, hp_method="average")
    choices = LevelChoices(level=2, expertise=["stealth"])
    options = choice_options(hero, registry, "expertise", choices)
    assert "stealth" not in options
    assert "perception" in options


def test_rogue_three_expertise_picks_on_level_2_are_too_many(registry):
    hero = make_hero(registry, "rogue")
    hero.sheet.skill_expertise = []
    level_up(hero, registry, hp_method="average")
    choices = LevelChoices(level=2, expertise=["stealth", "perception", "acrobatics"])
    assert "expertise_invalid" in [code for code, _ in choice_errors(hero, registry, choices)]


def test_stealth_with_expertise_is_dex_plus_double_proficiency(registry):
    hero = make_hero(registry, "rogue")
    assert "stealth" in hero.sheet.skill_expertise
    expected = ability_mod(hero, "dex") + 2 * proficiency(hero, registry)
    assert skill_bonus(hero, registry, "stealth") == expected


def test_skill_without_expertise_is_dex_plus_single_proficiency(registry):
    hero = make_hero(registry, "rogue")
    assert "acrobatics" not in hero.sheet.skill_expertise
    assert skill_bonus(hero, registry, "acrobatics") == (
        ability_mod(hero, "dex") + proficiency(hero, registry)
    )


def test_building_rogue_without_expertise_is_an_error(registry):
    result = build_character(rogue_choices(expertise=[]), registry)
    assert "expertise_invalid" in result.codes


def test_building_rogue_with_one_expertise_is_an_error(registry):
    result = build_character(rogue_choices(expertise=["stealth"]), registry)
    assert "expertise_invalid" in result.codes


def test_building_rogue_with_expertise_in_unowned_skill_is_an_error(registry):
    result = build_character(rogue_choices(expertise=["stealth", "nature"]), registry)
    assert "expertise_invalid" in result.codes


def test_building_rogue_with_repeated_expertise_is_an_error(registry):
    result = build_character(rogue_choices(expertise=["stealth", "stealth"]), registry)
    assert "expertise_invalid" in result.codes


def test_building_fighter_with_expertise_is_an_error(registry):
    choices = minimal_choices("fighter", "a").model_copy(update={"expertise": ["perception"]})
    assert "expertise_invalid" in build_character(choices, registry).codes


def test_building_rogue_with_one_expertise_names_the_needed_count(registry):
    result = build_character(rogue_choices(expertise=["stealth"]), registry)
    assert "экспертиза: нужно навыков — 2, без повторов" in result.messages


class StubRegistry:
    # реестр из готовых умений и оружия: get("feature", id) / get("class", id) / all("weapon")
    def __init__(self, features=None, char_class=None, weapons=()):
        self.features = features or {}
        self.char_class = char_class
        self.weapon_list = list(weapons)

    def get(self, kind, key):
        return self.char_class if kind == "class" else self.features[key]

    def all(self, kind):
        return self.weapon_list


def feature_with(*effects):
    return SimpleNamespace(effects=list(effects))


def effect(type_="proficiency", mode="expertise", count=2):
    return SimpleNamespace(type=type_, mode=mode, count=count)


def refs(*pairs):
    return [SimpleNamespace(level=level, feature=feature) for level, feature in pairs]


def two_features():
    return StubRegistry({"a": feature_with(effect(count=2)), "b": feature_with(effect(count=1))})


def test_expertise_total_sums_features_up_to_the_level():
    registry = two_features()
    char_class = SimpleNamespace(features=refs((1, "a"), (3, "b")))
    assert expertise_total(registry, char_class, 3) == 3


def test_expertise_total_skips_features_of_higher_levels():
    registry = two_features()
    char_class = SimpleNamespace(features=refs((1, "a"), (3, "b")))
    assert expertise_total(registry, char_class, 2) == 2


def test_expertise_total_does_not_depend_on_feature_order():
    registry = two_features()
    char_class = SimpleNamespace(features=refs((5, "b"), (1, "a")))
    assert expertise_total(registry, char_class, 1) == 2


def test_expertise_total_ignores_other_proficiency_modes():
    registry = StubRegistry({"a": feature_with(effect(mode="proficiency", count=3))})
    assert expertise_total(registry, SimpleNamespace(features=refs((1, "a"))), 1) == 0


def test_expertise_total_ignores_other_effect_types():
    registry = StubRegistry({"a": feature_with(effect(type_="bonus", count=3))})
    assert expertise_total(registry, SimpleNamespace(features=refs((1, "a"))), 1) == 0


def test_expertise_total_adds_several_effects_of_one_feature():
    registry = StubRegistry({"a": feature_with(effect(count=2), effect(count=1))})
    assert expertise_total(registry, SimpleNamespace(features=refs((1, "a"))), 1) == 3


def test_expertise_total_counts_effect_without_count_as_zero():
    registry = StubRegistry({"a": feature_with(effect(count=None))})
    assert expertise_total(registry, SimpleNamespace(features=refs((1, "a"))), 1) == 0


def test_expertise_may_use_a_background_skill(registry):
    result = build_character(rogue_choices(expertise=["athletics", "stealth"]), registry)
    assert result.sheet.skill_expertise == ["athletics", "stealth"]


@pytest.mark.parametrize("weapon_id", ["musket", "pistol"])
def test_fighter_is_proficient_with_firearms(registry, weapon_id):
    char_class = registry.get("class", "fighter")
    assert weapon_proficient(char_class, registry.get("weapon", weapon_id))


@pytest.mark.parametrize("weapon_id", ["musket", "pistol"])
def test_rogue_is_not_proficient_with_firearms(registry, weapon_id):
    char_class = registry.get("class", "rogue")
    assert not weapon_proficient(char_class, registry.get("weapon", weapon_id))


def test_rogue_is_proficient_with_hand_crossbow(registry):
    char_class = registry.get("class", "rogue")
    assert weapon_proficient(char_class, registry.get("weapon", "hand_crossbow"))


def test_ranger_is_proficient_with_firearms(registry):
    char_class = registry.get("class", "ranger")
    assert weapon_proficient(char_class, registry.get("weapon", "musket"))


def test_ranger_level_2_still_requires_style_and_expertise(registry):
    hero = hero_at(registry, "ranger", 2, apply_last=False)
    assert required_choices(hero, registry, 2) == {"fighting_style", "expertise"}


def test_ranger_level_2_requires_expertise_even_with_one_already_chosen(registry):
    # ветка «новое на этом уровне» в expertise_due: Ловкий исследователь даёт навык сверх имеющихся
    hero = hero_at(registry, "ranger", 2, apply_last=False)
    hero.sheet.skill_expertise = ["stealth"]
    assert expertise_due(hero, registry, 2) == 1
    assert "expertise" in required_choices(hero, registry, 2)
