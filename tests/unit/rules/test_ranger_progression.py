# Следопыт 1-5 ур.: числа прогрессии, производные, выборы уровня (docs/decisions/ranger-2-5-plan.md,
# разд. 4-7). Ожидаемый API:
#   rules.progression.LevelChoices(level, fighting_style=None, expertise=[] (список навыков),
#       subclass_id=None, feature_options={}, asi=None, feat=None, spells_add=[], languages=[])
#   rules.progression.required_choices(hero, registry, level) -> set[str]: ключи
#       "fighting_style", "expertise", "subclass", "hunters_prey", "asi_or_feat"; level -- уровень,
#       который герой уже получил (hero.sheet.level == level)
#   rules.progression.apply_level_choices(hero, registry, choices) -> None | ValidationErrors
#       (rules.builder.ValidationErrors); при ошибке героя не меняет; успех -- None
#   rules.derived.prepared_limit(hero, registry) -> int;
#       always_prepared(hero, registry) -> list[str]
#   CharacterSheet.skill_expertise / languages / feature_options
import pytest
from ranger_kit import make_class_hero, make_ranger, ranger_at

from ai_dm.rules.builder import ValidationErrors
from ai_dm.rules.derived import (
    always_prepared,
    prepared_limit,
    skill_bonus,
)
from ai_dm.rules.progression import (
    LevelChoices,
    apply_level_choices,
    required_choices,
    sync_resources,
)

SCORES = {"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12}
LEVEL_3_SPELLS = ["cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud"]


def pool(hero, name):
    return hero.creature.resources[name]


# числа прогрессии

@pytest.mark.parametrize("level, hp", [(1, 11), (2, 18), (3, 25), (4, 32), (5, 39)])
def test_ranger_hp_by_level(registry, level, hp):
    # d10: 6 за уровень + ТЕЛ +1
    assert ranger_at(registry, level).creature.hp_max == hp


@pytest.mark.parametrize(
    "level, slots",
    [(1, {1: 2}), (2, {1: 2}), (3, {1: 3}), (4, {1: 3}), (5, {1: 4, 2: 2})],
)
def test_ranger_slots_by_level(registry, level, slots):
    hero = ranger_at(registry, level)
    for circle, count in slots.items():
        assert pool(hero, f"spell_slot:{circle}").max == count
    assert ("spell_slot:2" in hero.creature.resources) == (2 in slots)


@pytest.mark.parametrize("level, uses", [(1, 2), (2, 2), (3, 2), (4, 2), (5, 3)])
def test_favored_enemy_pool_by_level(registry, level, uses):
    assert pool(ranger_at(registry, level), "favored_enemy").max == uses


def test_favored_enemy_starts_full(registry):
    hero = make_ranger(registry)
    assert pool(hero, "favored_enemy").current == 2


def test_level_5_sync_grows_favored_enemy_current_by_one(registry):
    hero = ranger_at(registry, 4)
    pool(hero, "favored_enemy").current = 1
    hero.sheet.primary.level = 5
    sync_resources(hero, registry)
    assert pool(hero, "favored_enemy").max == 3
    assert pool(hero, "favored_enemy").current == 2


@pytest.mark.parametrize("level, limit", [(1, 2), (2, 3), (3, 4), (4, 5), (5, 6)])
def test_prepared_limit_by_level(registry, level, limit):
    assert prepared_limit(ranger_at(registry, level), registry) == limit


def test_hunters_mark_is_always_prepared_for_ranger(registry):
    assert always_prepared(make_ranger(registry), registry) == ["hunters_mark"]


def test_always_prepared_is_empty_for_fighter(registry):
    hero = make_class_hero("fighter", SCORES)
    assert always_prepared(hero, registry) == []


# required_choices

def test_level_2_requires_style_and_expertise(registry):
    assert required_choices(ranger_at(registry, 2), registry, 2) == {
        "fighting_style", "expertise",
    }


def test_level_3_without_subclass_requires_subclass(registry):
    assert required_choices(ranger_at(registry, 3), registry, 3) == {"subclass"}


def test_level_3_hunter_requires_hunters_prey(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    required = required_choices(hero, registry, 3)
    assert "hunters_prey" in required
    assert "subclass" not in required


def test_level_3_beast_master_has_nothing_more_to_choose(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "beast_master"
    assert required_choices(hero, registry, 3) == set()


def test_level_4_requires_asi_or_feat(registry):
    assert required_choices(ranger_at(registry, 4), registry, 4) == {"asi_or_feat"}


def test_level_5_requires_nothing(registry):
    assert required_choices(ranger_at(registry, 5), registry, 5) == set()


# экспертиза

def test_survival_without_expertise(registry):
    # МДР 15 +2, владение +2
    assert skill_bonus(make_ranger(registry), registry, "survival") == 4


def test_survival_with_expertise_doubles_proficiency(registry):
    hero = make_ranger(registry)
    hero.sheet.skill_expertise = ["survival"]
    assert skill_bonus(hero, registry, "survival") == 6


def test_expertise_does_not_touch_other_skills(registry):
    hero = make_ranger(registry)
    hero.sheet.skill_expertise = ["survival"]
    plain = make_ranger(registry)
    assert skill_bonus(hero, registry, "stealth") == skill_bonus(plain, registry, "stealth")


def test_expertise_choice_is_applied(registry):
    hero = ranger_at(registry, 2)
    result = apply_level_choices(
        hero, registry, LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    )
    assert result is None
    assert hero.sheet.skill_expertise == ["survival"]


def test_expertise_in_skill_without_proficiency_is_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="archery", expertise=["athletics"])
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)
    assert hero.sheet.skill_expertise == []


def test_repeated_expertise_is_error(registry):
    hero = ranger_at(registry, 2)
    hero.sheet.skill_expertise = ["survival"]
    choices = LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)


def test_languages_are_stored(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(
        level=2, fighting_style="archery", expertise=["survival"],
        languages=["celestial", "gnomish"],
    )
    assert apply_level_choices(hero, registry, choices) is None
    assert hero.sheet.languages == ["celestial", "gnomish"]


# боевой стиль

def test_fighting_style_is_added_to_feats(registry):
    hero = ranger_at(registry, 2)
    apply_level_choices(
        hero, registry, LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    )
    assert "archery" in hero.sheet.feats


def test_non_style_feat_as_fighting_style_is_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="alert", expertise=["survival"])
    before = hero.model_dump_json()
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)
    assert hero.model_dump_json() == before


def test_unknown_fighting_style_is_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="no_such_style", expertise=["survival"])
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)


# подкласс и опции

def test_subclass_is_applied(registry):
    hero = ranger_at(registry, 3)
    assert apply_level_choices(
        hero, registry, LevelChoices(level=3, subclass_id="beast_master")
    ) is None
    assert hero.sheet.subclass_id == "beast_master"


def test_unknown_subclass_is_error(registry):
    hero = ranger_at(registry, 3)
    assert isinstance(
        apply_level_choices(hero, registry, LevelChoices(level=3, subclass_id="no_such")),
        ValidationErrors,
    )
    assert hero.sheet.subclass_id is None


def test_hunters_prey_option_is_stored(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="hunter", feature_choices={"hunters_prey": ["colossus_slayer"]}
    )
    assert apply_level_choices(hero, registry, choices) is None
    assert hero.sheet.feature_choices == {"hunters_prey": ["colossus_slayer"]}


# ASI

def level_4_ranger(registry):
    hero = ranger_at(registry, 4)
    return hero


def test_asi_plus_two_raises_dex_17_to_19(registry):
    hero = level_4_ranger(registry)
    assert apply_level_choices(hero, registry, LevelChoices(level=4, asi={"dex": 2})) is None
    assert hero.sheet.abilities["dex"] == 19


def test_asi_plus_one_plus_one_is_valid(registry):
    hero = level_4_ranger(registry)
    wis = hero.sheet.abilities["wis"]
    assert apply_level_choices(
        hero, registry, LevelChoices(level=4, asi={"dex": 1, "wis": 1})
    ) is None
    assert hero.sheet.abilities["dex"] == 18
    assert hero.sheet.abilities["wis"] == wis + 1


def test_asi_above_20_is_error_and_changes_nothing(registry):
    hero = level_4_ranger(registry)
    hero.sheet.abilities["dex"] = 19
    before = hero.model_dump_json()
    result = apply_level_choices(hero, registry, LevelChoices(level=4, asi={"dex": 2}))
    assert isinstance(result, ValidationErrors)
    assert hero.model_dump_json() == before


def test_asi_with_sum_three_is_error(registry):
    hero = level_4_ranger(registry)
    result = apply_level_choices(hero, registry, LevelChoices(level=4, asi={"dex": 3}))
    assert isinstance(result, ValidationErrors)


# заклинания

def test_level_3_spells_within_limit_are_prepared(registry):
    hero = ranger_at(registry, 3)
    assert apply_level_choices(
        hero, registry, LevelChoices(level=3, spells_add=LEVEL_3_SPELLS)
    ) is None
    assert set(LEVEL_3_SPELLS) <= set(hero.sheet.prepared_of())


def test_hunters_mark_is_not_counted_in_the_limit(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=LEVEL_3_SPELLS + ["hunters_mark"])
    assert apply_level_choices(hero, registry, choices) is None


def test_second_circle_spell_at_level_3_is_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["pass_without_trace"])
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)


def test_second_circle_spell_at_level_5_is_allowed(registry):
    hero = ranger_at(registry, 5)
    choices = LevelChoices(level=5, spells_add=["pass_without_trace"])
    assert apply_level_choices(hero, registry, choices) is None


def test_spells_above_the_limit_are_error(registry):
    hero = ranger_at(registry, 3)
    five = LEVEL_3_SPELLS + ["goodberry"]
    assert isinstance(
        apply_level_choices(hero, registry, LevelChoices(level=3, spells_add=five)),
        ValidationErrors,
    )
    assert hero.sheet.prepared_of() == []


def test_spell_of_another_class_is_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["magic_missile"])
    assert isinstance(apply_level_choices(hero, registry, choices), ValidationErrors)
