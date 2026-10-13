# К0б (K0-PLAN A8, B3): пять классов проходят уровни 1-20 по данным классов.
#   * ПХ (asi_or_feat) на 4/8/12/16/19; воину добавочно 6/14, плуту 10;
#   * подкласс на 3-м только у классов с подклассами в данных (сейчас следопыт);
#   * ячейки на 20: полный заклинатель -- 9-й круг, половинный -- 5-й;
#   * prepared_limit (Q10): жрец 22, волшебник 25, следопыт 15 на 20-м;
#   * умение «повышение характеристик» повторяется в hero_feature_ids по числу строк класса.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content"))

from test_class_kits import minimal_choices  # noqa: E402

from ai_dm.content.models.common import ABILITIES  # noqa: E402
from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.derived import (  # noqa: E402
    hero_feature_ids,
    prepared_limit,
    proficiency,
    spell_slots,
)
from ai_dm.rules.progression import (  # noqa: E402
    FIXED_CHOICES,
    apply_level_choices,
    choice_options,
    level_up,
    needed_choices,
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
