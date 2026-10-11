# Тесты выборов уровня (ai_dm.rules.progression): коды ошибок, ветки черт и ASI, сообщения о
# недостающих выборах, варианты выбора. Реестр SRD не содержит общих черт, кроме повышения
# характеристик, поэтому для веток черт реестр дополняется своими чертами (with_content).
import pytest
from ranger_kit import make_class_hero, ranger_at

from ai_dm.content.models.common import FeatureRef
from ai_dm.content.models.feats import Feat
from ai_dm.content.models.features import Feature
from ai_dm.rules.builder import ValidationErrors
from ai_dm.rules.progression import (
    ASI_FEAT,
    LevelChoices,
    apply_level_choices,
    asi_errors,
    choice_errors,
    choice_options,
    level_up,
    missing_choices,
    needed_choices,
    next_choice,
    required_choices,
    spell_errors,
    spells_left,
)

SCORES = {"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12}
ALL_TEN = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
LEVEL_3_SPELLS = ["cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud"]


def with_content(registry, feats=(), features=(), classes=(), spells=()):
    return registry.with_items(
        {"feat": feats, "feature": features, "class": classes, "spell": spells}
    )


def feats_registry(registry):
    return with_content(registry, feats=[
        Feat(id="tough", name="Крепкий", category="general"),
        Feat(id="lucky_rep", name="Везучий", category="general", repeatable=True),
    ])


def option_registry(registry, level):
    # у самого класса следопыта на уровне level появляется умение с вариантами
    ranger = registry.get("class", "ranger")
    ranger = ranger.model_copy(
        update={"features": ranger.features + [FeatureRef(level=level, feature="test_opt")]}
    )
    feature = Feature(id="test_opt", name="Тест", options=["a", "b"])
    return with_content(registry, features=[feature], classes=[ranger])


def codes(errors):
    return [code for code, _ in errors]


# choice_options: asi_or_feat

def test_asi_options_for_all_tens_are_all_pairs_without_repeats(registry):
    hero = make_class_hero("fighter", dict(ALL_TEN))
    options = choice_options(hero, registry, "asi_or_feat")
    assert options == [
        "str+2", "str+dex", "str+con", "str+int", "str+wis", "str+cha",
        "dex+2", "dex+con", "dex+int", "dex+wis", "dex+cha",
        "con+2", "con+int", "con+wis", "con+cha",
        "int+2", "int+wis", "int+cha",
        "wis+2", "wis+cha",
        "cha+2",
    ]


def test_asi_options_at_18_allow_plus_two(registry):
    abilities = dict(ALL_TEN, str=18)
    options = choice_options(make_class_hero("fighter", abilities), registry, "asi_or_feat")
    assert "str+2" in options
    assert "str+dex" in options


def test_asi_options_at_19_forbid_plus_two_but_allow_pair(registry):
    abilities = dict(ALL_TEN, str=19)
    options = choice_options(make_class_hero("fighter", abilities), registry, "asi_or_feat")
    assert "str+2" not in options
    assert "str+dex" in options


def test_asi_options_at_20_forbid_plus_two_and_pairs_with_it(registry):
    abilities = dict(ALL_TEN, str=20, wis=20)
    options = choice_options(make_class_hero("fighter", abilities), registry, "asi_or_feat")
    assert "str+2" not in options
    assert "wis+2" not in options
    assert "str+dex" not in options
    assert "dex+wis" not in options
    assert "str+wis" not in options
    assert "dex+con" in options


def test_asi_options_pair_with_second_at_19_is_allowed(registry):
    abilities = dict(ALL_TEN, dex=19, con=19)
    options = choice_options(make_class_hero("fighter", abilities), registry, "asi_or_feat")
    assert "dex+con" in options


def test_asi_options_list_only_general_feats(registry):
    reg = feats_registry(registry)
    hero = make_class_hero("fighter", dict(ALL_TEN))
    feats = [o for o in choice_options(hero, reg, "asi_or_feat") if "+" not in o]
    assert feats == ["lucky_rep", "tough"]


def test_asi_options_exclude_taken_feat_but_keep_repeatable(registry):
    reg = feats_registry(registry)
    hero = make_class_hero("fighter", dict(ALL_TEN))
    hero.sheet.feats = ["tough", "lucky_rep"]
    feats = [o for o in choice_options(hero, reg, "asi_or_feat") if "+" not in o]
    assert feats == ["lucky_rep"]


def test_asi_options_never_contain_asi_feat(registry):
    hero = make_class_hero("fighter", dict(ALL_TEN))
    assert ASI_FEAT not in choice_options(hero, registry, "asi_or_feat")


# choice_options: стили и заклинания

def test_style_options_skip_taken_style_and_non_style_feats(registry):
    hero = ranger_at(registry, 2)
    hero.sheet.feats.append("archery")
    assert choice_options(hero, registry, "fighting_style") == [
        "defense", "great_weapon_fighting", "two_weapon_fighting",
    ]


def test_spells_options_without_choices_are_candidates(registry):
    hero = ranger_at(registry, 3)
    options = choice_options(hero, registry, "spells")
    assert "cure_wounds" in options
    assert "hunters_mark" not in options
    assert "pass_without_trace" not in options


def test_spells_options_skip_prepared_spell(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.prepared_of()[:] = ["cure_wounds"]
    assert "cure_wounds" not in choice_options(hero, registry, "spells")


def test_spells_options_skip_spells_from_choices(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["cure_wounds"])
    assert "cure_wounds" not in choice_options(hero, registry, "spells", choices)


# choice_errors: коды

def test_choice_errors_level_mismatch(registry):
    hero = ranger_at(registry, 2)
    assert codes(choice_errors(hero, registry, LevelChoices(level=3))) == ["level_mismatch"]


def test_choice_errors_empty_choices_have_no_errors(registry):
    hero = ranger_at(registry, 2)
    assert choice_errors(hero, registry, LevelChoices(level=2)) == []


def test_subclass_where_it_is_not_chosen_is_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, subclass_id="hunter")
    assert codes(choice_errors(hero, registry, choices)) == ["subclass_invalid"]


def test_unknown_subclass_is_one_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, subclass_id="nope")
    assert codes(choice_errors(hero, registry, choices)) == ["subclass_invalid"]


def test_fighting_style_where_it_is_not_chosen_is_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, fighting_style="archery")
    assert codes(choice_errors(hero, registry, choices)) == ["fighting_style_invalid"]


def test_non_style_feat_as_style_is_one_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="alert")
    assert codes(choice_errors(hero, registry, choices)) == ["fighting_style_invalid"]


def test_taken_style_is_error(registry):
    hero = ranger_at(registry, 2)
    hero.sheet.feats.append("archery")
    choices = LevelChoices(level=2, fighting_style="archery")
    assert codes(choice_errors(hero, registry, choices)) == ["fighting_style_invalid"]


def test_expertise_where_it_is_not_chosen_is_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, expertise=["survival"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_two_different_expertise_picks_are_rejected(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, expertise=["survival", "stealth"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_two_equal_expertise_picks_are_rejected(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, expertise=["survival", "survival"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_expertise_without_proficiency_is_one_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, expertise=["athletics"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_expertise_in_non_skill_is_one_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, expertise=["nope"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_taken_expertise_is_one_error(registry):
    hero = ranger_at(registry, 2)
    hero.sheet.skill_expertise = ["survival"]
    choices = LevelChoices(level=2, expertise=["survival"])
    assert codes(choice_errors(hero, registry, choices)) == ["expertise_invalid"]


def test_option_of_feature_that_is_not_chosen_is_error(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["colossus_slayer"]})
    assert codes(choice_errors(hero, registry, choices)) == ["option_invalid"]


def test_unknown_option_is_error(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["nope"]})
    assert codes(choice_errors(hero, registry, choices)) == ["option_invalid"]


def test_valid_option_has_no_errors(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    choices = LevelChoices(level=3, feature_choices={"hunters_prey": ["horde_breaker"]})
    assert choice_errors(hero, registry, choices) == []


# choice_errors: ASI и черта

def test_asi_on_level_without_asi_is_one_error(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, asi={"dex": 2})
    assert codes(choice_errors(hero, registry, choices)) == ["asi_invalid"]


def test_bad_asi_on_level_without_asi_is_not_duplicated(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, asi={"dex": 3})
    assert codes(choice_errors(hero, registry, choices)) == ["asi_invalid"]


def test_feat_alone_on_level_without_asi_is_one_error(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 2)
    choices = LevelChoices(level=2, feat="tough")
    assert codes(choice_errors(hero, reg, choices)) == ["asi_invalid"]


def test_asi_and_feat_on_level_without_asi_give_two_errors(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 2)
    choices = LevelChoices(level=2, asi={"dex": 2}, feat="tough")
    assert codes(choice_errors(hero, reg, choices)) == ["asi_invalid", "asi_invalid"]


def test_asi_error_on_wrong_level_keeps_other_errors(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="alert", asi={"dex": 2})
    assert codes(choice_errors(hero, registry, choices)) == [
        "fighting_style_invalid", "asi_invalid",
    ]


def test_asi_and_feat_together_is_one_error(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 4)
    choices = LevelChoices(level=4, asi={"dex": 2}, feat="tough")
    assert codes(choice_errors(hero, reg, choices)) == ["asi_invalid"]


def test_valid_asi_has_no_errors(registry):
    hero = ranger_at(registry, 4)
    assert choice_errors(hero, registry, LevelChoices(level=4, asi={"dex": 2})) == []


def test_bad_asi_on_asi_level_gives_asi_errors_once(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, asi={"dex": 3})
    assert codes(choice_errors(hero, registry, choices)) == ["asi_invalid"]


def test_valid_general_feat_has_no_errors(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 4)
    assert choice_errors(hero, reg, LevelChoices(level=4, feat="tough")) == []


def test_unknown_feat_is_error(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, feat="nope")
    assert codes(choice_errors(hero, registry, choices)) == ["feat_invalid"]


def test_non_general_feat_is_error(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, feat="alert")
    assert codes(choice_errors(hero, registry, choices)) == ["feat_invalid"]


def test_fighting_style_feat_in_feat_field_is_error(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, feat="archery")
    assert codes(choice_errors(hero, registry, choices)) == ["feat_invalid"]


def test_asi_feat_in_feat_field_is_error(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, feat=ASI_FEAT)
    assert codes(choice_errors(hero, registry, choices)) == ["feat_invalid"]


def test_taken_non_repeatable_feat_is_error(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 4)
    hero.sheet.feats.append("tough")
    choices = LevelChoices(level=4, feat="tough")
    assert codes(choice_errors(hero, reg, choices)) == ["feat_invalid"]


def test_taken_repeatable_feat_is_allowed(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 4)
    hero.sheet.feats.append("lucky_rep")
    assert choice_errors(hero, reg, LevelChoices(level=4, feat="lucky_rep")) == []


# asi_errors

def test_asi_errors_18_plus_2_is_allowed():
    hero = make_class_hero("fighter", dict(SCORES, dex=18))
    assert asi_errors(hero, {"dex": 2}) == []


def test_asi_errors_19_plus_2_is_error():
    hero = make_class_hero("fighter", dict(SCORES, dex=19))
    assert codes(asi_errors(hero, {"dex": 2})) == ["asi_invalid"]


def test_asi_errors_19_plus_1_is_allowed():
    hero = make_class_hero("fighter", dict(SCORES, dex=19))
    assert asi_errors(hero, {"dex": 1, "wis": 1}) == []


def test_asi_errors_20_plus_1_is_error():
    hero = make_class_hero("fighter", dict(SCORES, dex=20))
    assert codes(asi_errors(hero, {"dex": 1, "wis": 1})) == ["asi_invalid"]


def test_asi_errors_both_at_20_give_two_errors():
    hero = make_class_hero("fighter", dict(SCORES, dex=20, wis=20))
    assert codes(asi_errors(hero, {"dex": 1, "wis": 1})) == ["asi_invalid", "asi_invalid"]


def test_asi_errors_unknown_ability_is_error():
    hero = make_class_hero("fighter", dict(SCORES))
    assert codes(asi_errors(hero, {"luck": 2})) == ["asi_invalid"]


@pytest.mark.parametrize("asi", [{"dex": 3}, {"dex": 1}, {"dex": 1, "wis": 1, "str": 1}, {}])
def test_asi_errors_wrong_shape_is_one_error(asi):
    hero = make_class_hero("fighter", dict(SCORES))
    assert codes(asi_errors(hero, asi)) == ["asi_invalid"]


# spell_errors

def test_spell_errors_without_adds_is_empty(registry):
    hero = ranger_at(registry, 3)
    assert spell_errors(hero, registry, LevelChoices(level=3)) == []


def test_spell_errors_only_always_prepared_is_empty(registry):
    hero = ranger_at(registry, 3)
    assert spell_errors(hero, registry, LevelChoices(level=3, spells_add=["hunters_mark"])) == []


def test_spell_errors_for_class_without_spells(registry):
    hero = make_class_hero("fighter", dict(SCORES))
    choices = LevelChoices(level=1, spells_add=["cure_wounds"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid"]


def test_spell_errors_duplicates(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["cure_wounds", "cure_wounds"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid"]


def test_spell_errors_unknown_spell_does_not_stop_checking_the_rest(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["nope", "magic_missile"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid", "spells_invalid"]


def test_spell_errors_circle_above_slots(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["pass_without_trace"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid"]


def test_spell_errors_cantrip_is_not_chosen_here(registry):
    # заговор из списка класса: свой заговор следопыта, в SRD у следопыта заговоров нет
    cantrip = registry.get("spell", "cure_wounds").model_copy(
        update={"id": "test_cantrip", "level": 0}
    )
    registry = with_content(registry, spells=[cantrip])
    hero = ranger_at(registry, 3)
    errors = spell_errors(hero, registry, LevelChoices(level=3, spells_add=["test_cantrip"]))
    assert codes(errors) == ["spells_invalid"]
    assert all(message is not None for _, message in errors)


def test_spell_errors_already_prepared(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.prepared_of()[:] = ["cure_wounds"]
    choices = LevelChoices(level=3, spells_add=["goodberry"])
    assert spell_errors(hero, registry, choices) == []
    choices = LevelChoices(level=3, spells_add=["cure_wounds"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid"]


def test_spell_errors_above_limit(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=LEVEL_3_SPELLS + ["goodberry"])
    assert codes(spell_errors(hero, registry, choices)) == ["spells_invalid"]


def test_spell_errors_exactly_limit_is_allowed(registry):
    hero = ranger_at(registry, 3)
    assert spell_errors(hero, registry, LevelChoices(level=3, spells_add=LEVEL_3_SPELLS)) == []


# apply_level_choices: коды и содержимое

def test_apply_level_mismatch_codes(registry):
    hero = ranger_at(registry, 2)
    result = apply_level_choices(hero, registry, LevelChoices(level=3))
    assert result.codes == ["level_mismatch"]
    assert len(result.messages) == 1


def test_apply_collects_codes_of_all_errors(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="alert", expertise=["athletics"])
    result = apply_level_choices(hero, registry, choices)
    assert isinstance(result, ValidationErrors)
    assert result.codes == ["fighting_style_invalid", "expertise_invalid"]
    assert len(result.messages) == 2


def test_apply_feat_is_appended_to_feats(registry):
    reg = feats_registry(registry)
    hero = ranger_at(reg, 4)
    before = list(hero.sheet.feats)
    assert apply_level_choices(hero, reg, LevelChoices(level=4, feat="tough")) is None
    assert hero.sheet.feats == before + ["tough"]


def test_apply_asi_appends_asi_feat_once(registry):
    hero = ranger_at(registry, 4)
    before = list(hero.sheet.feats)
    assert apply_level_choices(hero, registry, LevelChoices(level=4, asi={"dex": 2})) is None
    assert hero.sheet.feats == before + [ASI_FEAT]


def test_apply_style_is_appended_to_feats(registry):
    hero = ranger_at(registry, 2)
    before = list(hero.sheet.feats)
    choices = LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    assert apply_level_choices(hero, registry, choices) is None
    assert hero.sheet.feats == before + ["archery"]


def test_apply_always_prepared_spell_is_skipped_and_next_ones_are_added(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, spells_add=["hunters_mark", "cure_wounds", "goodberry"])
    assert apply_level_choices(hero, registry, choices) is None
    assert hero.sheet.prepared_of() == ["cure_wounds", "goodberry"]
    assert hero.sheet.known_of() == ["cure_wounds", "goodberry"]


# missing_choices / next_choice

def test_missing_level_2_style_and_expertise(registry):
    hero = ranger_at(registry, 2)
    assert missing_choices(hero, registry, LevelChoices(level=2)) == [
        "не выбран боевой стиль", "не выбрана экспертиза",
    ]


def test_missing_only_expertise_when_style_is_chosen(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="archery")
    assert missing_choices(hero, registry, choices) == ["не выбрана экспертиза"]


def test_missing_only_style_when_expertise_is_chosen(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, expertise=["survival"])
    assert missing_choices(hero, registry, choices) == ["не выбран боевой стиль"]


def test_missing_nothing_when_level_2_is_complete(registry):
    hero = ranger_at(registry, 2)
    choices = LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    assert missing_choices(hero, registry, choices) == []


def test_missing_subclass(registry):
    hero = ranger_at(registry, 3)
    assert missing_choices(hero, registry, LevelChoices(level=3)) == ["не выбран подкласс"]


def test_missing_asi_or_feat(registry):
    hero = ranger_at(registry, 4)
    assert missing_choices(hero, registry, LevelChoices(level=4)) == [
        "нужно выбрать повышение характеристик или черту",
    ]


def test_missing_nothing_when_asi_is_chosen(registry):
    hero = ranger_at(registry, 4)
    assert missing_choices(hero, registry, LevelChoices(level=4, asi={"dex": 2})) == []


def test_missing_nothing_when_feat_is_chosen(registry):
    hero = ranger_at(registry, 4)
    assert missing_choices(hero, registry, LevelChoices(level=4, feat="tough")) == []


def test_missing_feature_option(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.primary.subclass_id = "hunter"
    assert missing_choices(hero, registry, LevelChoices(level=3)) == [
        "не выбран вариант умения hunters_prey",
    ]


def test_missing_option_of_subclass_chosen_in_same_choices(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, subclass_id="hunter")
    assert missing_choices(hero, registry, choices) == ["не выбран вариант умения hunters_prey"]


def test_missing_nothing_when_subclass_and_option_are_chosen(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="hunter", feature_choices={"hunters_prey": ["colossus_slayer"]},
    )
    assert missing_choices(hero, registry, choices) == []


def test_next_choice_level_2_goes_style_then_expertise_then_spells(registry):
    hero = ranger_at(registry, 2)
    assert next_choice(hero, registry, LevelChoices(level=2)) == "fighting_style"
    choices = LevelChoices(level=2, fighting_style="archery")
    assert next_choice(hero, registry, choices) == "expertise"
    choices = LevelChoices(level=2, fighting_style="archery", expertise=["survival"])
    assert next_choice(hero, registry, choices) == "spells"


def test_next_choice_subclass(registry):
    hero = ranger_at(registry, 3)
    assert next_choice(hero, registry, LevelChoices(level=3)) == "subclass"


def test_next_choice_feature_option_of_chosen_subclass(registry):
    hero = ranger_at(registry, 3)
    choices = LevelChoices(level=3, subclass_id="hunter")
    assert next_choice(hero, registry, choices) == "hunters_prey"


def test_next_choice_asi_or_feat(registry):
    hero = ranger_at(registry, 4)
    assert next_choice(hero, registry, LevelChoices(level=4)) == "asi_or_feat"


def test_next_choice_after_asi_is_spells(registry):
    hero = ranger_at(registry, 4)
    assert next_choice(hero, registry, LevelChoices(level=4, asi={"dex": 2})) == "spells"


def test_next_choice_after_feat_is_spells(registry):
    hero = ranger_at(registry, 4)
    assert next_choice(hero, registry, LevelChoices(level=4, feat="tough")) == "spells"


def test_next_choice_is_none_when_everything_is_chosen(registry):
    hero = ranger_at(registry, 4)
    choices = LevelChoices(level=4, asi={"dex": 2}, spells_add=LEVEL_3_SPELLS + ["goodberry"])
    assert next_choice(hero, registry, choices) is None


# required_choices / needed_choices: умения с вариантами у самого класса

def test_required_includes_option_feature_of_class_itself(registry):
    reg = option_registry(registry, 2)
    hero = ranger_at(reg, 2)
    assert required_choices(hero, reg, 2) == {"fighting_style", "expertise", "test_opt"}


def test_required_with_subclass_keeps_class_options(registry):
    reg = option_registry(registry, 3)
    hero = ranger_at(reg, 3)
    hero.sheet.primary.subclass_id = "hunter"
    assert required_choices(hero, reg, 3) == {"test_opt", "hunters_prey"}


def test_needed_subclass_is_replaced_by_its_options_next_to_other_choices(registry):
    reg = option_registry(registry, 3)
    hero = ranger_at(reg, 3)
    choices = LevelChoices(level=3, subclass_id="hunter")
    assert needed_choices(hero, reg, choices) == {"test_opt", "hunters_prey"}


def test_needed_without_chosen_subclass_keeps_subclass(registry):
    reg = option_registry(registry, 3)
    hero = ranger_at(reg, 3)
    assert needed_choices(hero, reg, LevelChoices(level=3)) == {"test_opt", "subclass"}


# spells_left

def test_spells_left_is_zero_for_class_without_spells(registry):
    hero = make_class_hero("fighter", dict(SCORES))
    assert spells_left(hero, registry, LevelChoices(level=1)) == 0


def test_spells_left_counts_prepared_and_added(registry):
    hero = ranger_at(registry, 3)
    hero.sheet.prepared_of()[:] = ["cure_wounds"]
    choices = LevelChoices(level=3, spells_add=["goodberry"])
    assert spells_left(hero, registry, choices) == 2


# level_up: ТЕЛ и тип HP

@pytest.mark.parametrize("con, gain", [(14, 8), (13, 7), (9, 5), (7, 4)])
def test_level_up_con_modifier_rounds_down(con, gain, registry):
    hero = make_class_hero("fighter", dict(SCORES, con=con))
    hero.creature.hp_max = 12
    hero.creature.hp_current = 12
    level_up(hero, registry)
    # d10: среднее 6
    assert hero.creature.hp_max == 12 + gain


def test_level_up_hp_stays_int(registry):
    hero = make_class_hero("fighter", dict(SCORES, con=14))
    level_up(hero, registry)
    assert type(hero.creature.hp_max) is int
    assert type(hero.creature.hp_current) is int
