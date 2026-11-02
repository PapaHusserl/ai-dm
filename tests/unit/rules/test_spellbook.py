# К3 П2 (docs/plan-k3.md, «Тесты» П2): книга заклинаний волшебника, rules.spellbook, выборы уровня.
#   * выборы PICK_KEYS = cantrip, spellbook, savant_spell лежат в LevelChoices.feature_choices;
#   * книга: 6 на 1 ур. + 2 за уровень + 2 (3 ур.) и 1 (5 ур.) от Знатока воплощения = 17 на 5 ур.;
#   * подготовка (`spells`) -- только из книги, в том числе из внесённого на этом же уровне (Р34 а);
#   * Учёный: экспертиза только из шести навыков Учёного (2 ур.).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import pytest  # noqa: E402
from test_builder import wizard_choices  # noqa: E402

from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.progression import (  # noqa: E402
    apply_level_choices,
    choice_errors,
    choice_options,
    level_up,
    missing_choices,
    needed_choices,
    next_choice,
    required_choices,
)
from ai_dm.rules.spellbook import (  # noqa: E402
    PICK_KEYS,
    book_errors,
    book_growth,
    cantrip_growth,
    known_cantrips,
    max_circle,
    picked,
    picks_due,
    picks_missing,
)
from ai_dm.state.hero import LevelChoices  # noqa: E402

CANTRIPS = ["fire_bolt", "light", "mage_hand"]
BOOK = ["alarm", "burning_hands", "magic_missile", "shield", "sleep", "detect_magic"]
PREPARED = ["magic_missile", "shield", "sleep", "detect_magic"]
SCHOLAR = ["arcana", "history", "investigation", "medicine", "nature", "religion"]


def wizard(registry, level=1):
    # волшебник с полной книгой 1 ур. (6 заклинаний + 3 заговора), подготовлено 4
    hero = build_character(wizard_choices(spells=CANTRIPS + BOOK, prepared=PREPARED), registry)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
    return hero


def codes(errors):
    return [code for code, _ in errors]


def book_spells(hero, registry):
    return [s for s in hero.sheet.known_of() if registry.get("spell", s).level >= 1]


def grow(registry, level):
    # волшебник на уровне level: выборы всех прошлых уровней применены, текущий -- нет
    hero = wizard(registry, 1)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
        if hero.sheet.level < level:
            apply_level_choices(hero, registry, fill(hero, registry, hero.sheet.level))
    return hero


def fill(hero, registry, level):
    # выборы уровня: первые варианты из меню, Воплотитель на 3 ур., ПХ в слабую характеристику
    needed = required_choices(hero, registry, level)
    choices = LevelChoices(level=level)
    if "expertise" in needed:
        choices.expertise = choice_options(hero, registry, "expertise")[:1]
    if "subclass" in needed:
        choices.subclass_id = "evoker"
    for key in ("cantrip", "spellbook"):
        if key in needed:
            due = picks_due(hero, registry, key, level)
            choices.feature_choices[key] = choice_options(hero, registry, key, choices)[:due]
    if "savant_spell" in needed_choices(hero, registry, choices):
        pool = choice_options(hero, registry, "savant_spell", choices)
        choices.feature_choices["savant_spell"] = pool[: picks_due(
            hero, registry, "savant_spell", level, choices.subclass_id)]
    if "asi_or_feat" in needed:
        weakest = min(hero.sheet.abilities, key=lambda a: hero.sheet.abilities[a])
        choices.asi = {weakest: 2}
    return choices


# 1 уровень

def test_level_1_wizard_knows_nine_spells_and_prepares_four(registry):
    hero = wizard(registry)
    known = hero.sheet.known_of()
    assert len([s for s in known if registry.get("spell", s).level == 0]) == 3
    assert len(book_spells(hero, registry)) == 6
    assert len(hero.sheet.prepared_of()) == 4


# 2 уровень: книга и экспертиза Учёного

def test_level_2_requires_the_spellbook_and_expertise(registry):
    hero = grow(registry, 2)
    assert required_choices(hero, registry, 2) == {"spellbook", "expertise"}


def test_spellbook_options_at_level_2_are_first_circle_spells_not_in_the_book(registry):
    hero = grow(registry, 2)
    options = choice_options(hero, registry, "spellbook", LevelChoices(level=2))
    assert len(options) == 24
    assert not set(options) & set(hero.sheet.known_of())
    assert {registry.get("spell", s).level for s in options} == {1}


def test_spellbook_options_at_level_3_include_second_circle(registry):
    hero = grow(registry, 3)
    options = choice_options(hero, registry, "spellbook", LevelChoices(level=3))
    assert "scorching_ray" in options
    assert max(registry.get("spell", s).level for s in options) == 2


def test_spellbook_options_exclude_picks_made_on_the_same_level(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, feature_choices={"spellbook": ["grease"]})
    assert "grease" not in choice_options(hero, registry, "spellbook", choices)


def test_spellbook_takes_two_spells_per_level(registry):
    hero = grow(registry, 2)
    assert picks_due(hero, registry, "spellbook", 2) == 2
    ok = LevelChoices(level=2, expertise=["arcana"],
                      feature_choices={"spellbook": ["grease", "jump"]})
    assert choice_errors(hero, registry, ok) == []


def test_three_spells_into_the_book_at_level_2_is_error(registry):
    hero = grow(registry, 2)
    picks = ["grease", "jump", "thunderwave"]
    choices = LevelChoices(level=2, expertise=["arcana"], feature_choices={"spellbook": picks})
    assert "spellbook_invalid" in codes(choice_errors(hero, registry, choices))


def test_spell_already_in_the_book_is_not_added_again(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, expertise=["arcana"],
                           feature_choices={"spellbook": ["alarm", "grease"]})
    assert "spellbook_invalid" in codes(choice_errors(hero, registry, choices))


def test_second_circle_spell_into_the_book_at_level_2_is_error(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, expertise=["arcana"],
                           feature_choices={"spellbook": ["grease", "scorching_ray"]})
    assert "spellbook_invalid" in codes(choice_errors(hero, registry, choices))


def test_same_spell_twice_in_one_pick_is_error(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, expertise=["arcana"],
                           feature_choices={"spellbook": ["grease", "grease"]})
    assert "spellbook_invalid" in codes(choice_errors(hero, registry, choices))


def test_cleric_spell_cannot_go_into_the_wizard_book(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, expertise=["arcana"],
                           feature_choices={"spellbook": ["grease", "healing_word"]})
    assert "spellbook_invalid" in codes(choice_errors(hero, registry, choices))


def test_expertise_options_are_proficient_scholar_skills_only(registry):
    hero = grow(registry, 2)
    hero.sheet.skill_proficiencies.append("stealth")
    options = choice_options(hero, registry, "expertise")
    assert options
    assert set(options) <= set(SCHOLAR)
    assert "stealth" not in options
    assert set(options) <= set(hero.sheet.skill_proficiencies)


def test_expertise_in_a_skill_outside_the_scholar_list_is_error(registry):
    hero = grow(registry, 2)
    hero.sheet.skill_proficiencies.append("stealth")
    choices = LevelChoices(level=2, expertise=["stealth"],
                           feature_choices={"spellbook": ["grease", "jump"]})
    assert "expertise_invalid" in codes(choice_errors(hero, registry, choices))


def test_expertise_in_a_scholar_skill_is_ok(registry):
    hero = grow(registry, 2)
    skill = choice_options(hero, registry, "expertise")[0]
    choices = LevelChoices(level=2, expertise=[skill],
                           feature_choices={"spellbook": ["grease", "jump"]})
    assert choice_errors(hero, registry, choices) == []


def test_applied_level_2_choices_put_book_spells_into_known_not_prepared(registry):
    hero = grow(registry, 2)
    before = list(hero.sheet.prepared_of())
    choices = fill(hero, registry, 2)
    assert apply_level_choices(hero, registry, choices) is None
    picks = choices.feature_choices["spellbook"]
    assert set(picks) <= set(hero.sheet.known_of())
    assert hero.sheet.prepared_of() == before
    assert len(book_spells(hero, registry)) == 8
    assert hero.sheet.skill_expertise == choices.expertise


# подготовка: только из книги

def test_prepare_options_are_book_spells_not_yet_prepared(registry):
    hero = grow(registry, 2)
    options = choice_options(hero, registry, "spells", LevelChoices(level=2))
    assert sorted(options) == sorted(set(BOOK) - set(PREPARED))
    assert all(registry.get("spell", s).level >= 1 for s in options)


def test_preparing_a_spell_outside_the_book_is_spells_invalid(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, spells_add=["grease"])
    assert "spells_invalid" in codes(choice_errors(hero, registry, choices))


def test_preparing_a_cantrip_is_spells_invalid(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, spells_add=["fire_bolt"])
    assert "spells_invalid" in codes(choice_errors(hero, registry, choices))


def test_preparing_a_book_spell_within_the_limit_is_ok(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, expertise=["arcana"],
                           feature_choices={"spellbook": ["grease", "jump"]},
                           spells_add=["alarm"])
    assert choice_errors(hero, registry, choices) == []


def test_preparing_over_the_level_limit_is_spells_invalid(registry):
    hero = grow(registry, 2)  # лимит 5, подготовлено 4
    choices = LevelChoices(level=2, spells_add=["alarm", "burning_hands"])
    assert "spells_invalid" in codes(choice_errors(hero, registry, choices))


def test_prepared_spell_is_not_offered_again(registry):
    hero = grow(registry, 2)
    options = choice_options(hero, registry, "spells", LevelChoices(level=2))
    assert not set(options) & set(PREPARED)


# Р34 (а): внесённое на этом уровне можно подготовить сразу

def test_spell_added_to_the_book_this_level_is_a_prepare_option(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(level=3, feature_choices={"spellbook": ["scorching_ray", "web"]})
    assert "scorching_ray" in choice_options(hero, registry, "spells", choices)


def test_spell_not_picked_for_the_book_is_not_a_prepare_option(registry):
    hero = grow(registry, 3)
    assert "scorching_ray" not in choice_options(hero, registry, "spells", LevelChoices(level=3))


def test_new_book_spell_can_be_prepared_on_the_same_level(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    choices.feature_choices["spellbook"] = ["scorching_ray", "web"]
    choices.spells_add = ["scorching_ray"]
    assert "spells_invalid" not in codes(choice_errors(hero, registry, choices))
    assert apply_level_choices(hero, registry, choices) is None
    assert "scorching_ray" in hero.sheet.prepared_of()
    assert hero.sheet.known_of().count("scorching_ray") == 1


def test_savant_spell_of_this_level_can_be_prepared_at_once(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(level=3, subclass_id="evoker",
                           feature_choices={"savant_spell": ["scorching_ray", "darkness"]})
    assert "scorching_ray" in choice_options(hero, registry, "spells", choices)


def test_preparing_a_non_book_second_circle_spell_is_still_error(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    choices.spells_add = ["web"]
    assert "spells_invalid" in codes(choice_errors(hero, registry, choices))


# 3 уровень: подкласс и Знаток воплощения

def test_level_3_requires_subclass_and_spellbook(registry):
    hero = grow(registry, 3)
    assert required_choices(hero, registry, 3) == {"subclass", "spellbook"}


def test_savant_spell_is_needed_only_with_the_evoker(registry):
    hero = grow(registry, 3)
    assert "savant_spell" not in needed_choices(hero, registry, LevelChoices(level=3))
    evoker = LevelChoices(level=3, subclass_id="evoker")
    assert "savant_spell" in needed_choices(hero, registry, evoker)


def test_savant_options_are_evocation_spells_up_to_second_circle(registry):
    hero = grow(registry, 3)
    options = choice_options(hero, registry, "savant_spell",
                             LevelChoices(level=3, subclass_id="evoker"))
    assert options
    assert {registry.get("spell", s).school for s in options} == {"evocation"}
    assert max(registry.get("spell", s).level for s in options) <= 2
    assert not set(options) & set(hero.sheet.known_of())


def test_savant_takes_two_spells_at_level_3(registry):
    hero = grow(registry, 3)
    assert picks_due(hero, registry, "savant_spell", 3, "evoker") == 2
    assert picks_due(hero, registry, "savant_spell", 3) == 0


def test_third_savant_spell_at_level_3_is_error(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    choices.feature_choices["savant_spell"] = ["scorching_ray", "shatter", "flaming_sphere"]
    assert "savant_spell_invalid" in codes(choice_errors(hero, registry, choices))


def test_non_evocation_savant_spell_is_error(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    choices.feature_choices["savant_spell"] = ["web", "shatter"]
    assert "savant_spell_invalid" in codes(choice_errors(hero, registry, choices))


def test_savant_spell_without_the_evoker_is_error(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(level=3, feature_choices={"savant_spell": ["shatter", "scorching_ray"]})
    assert "savant_spell_invalid" in codes(choice_errors(hero, registry, choices))


def test_spell_from_the_book_picks_cannot_repeat_in_savant(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    choices.feature_choices["spellbook"] = ["scorching_ray", "web"]
    choices.feature_choices["savant_spell"] = ["scorching_ray", "shatter"]
    assert "savant_spell_invalid" in codes(choice_errors(hero, registry, choices))


def test_level_3_filled_choices_are_valid_and_grow_the_book_by_four(registry):
    hero = grow(registry, 3)
    choices = fill(hero, registry, 3)
    assert choice_errors(hero, registry, choices) == []
    assert apply_level_choices(hero, registry, choices) is None
    assert hero.sheet.subclass_id == "evoker"
    # 6 + 2 (2 ур.) + 2 (3 ур.) + 2 Знатока воплощения
    assert len(book_spells(hero, registry)) == 12


def test_next_choice_asks_the_subclass_first_then_savant_before_spellbook(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(level=3)
    assert next_choice(hero, registry, choices) == "subclass"
    choices.subclass_id = "evoker"
    assert next_choice(hero, registry, choices) == "savant_spell"
    choices.feature_choices["savant_spell"] = ["scorching_ray", "shatter"]
    assert next_choice(hero, registry, choices) == "spellbook"
    choices.feature_choices["spellbook"] = ["web", "grease"]
    assert next_choice(hero, registry, choices) != "spellbook"


# 4 и 5 уровни

def test_level_4_requires_a_cantrip_and_asi_without_spellbook_pick_growth(registry):
    hero = grow(registry, 4)
    needed = required_choices(hero, registry, 4)
    assert {"cantrip", "asi_or_feat"} <= needed


def test_wizard_cantrip_grows_at_level_4_only(registry):
    char_class = registry.get("class", "wizard")
    assert [cantrip_growth(char_class, n) for n in (2, 3, 4, 5, 10)] == [0, 0, 1, 0, 1]


def test_cantrip_options_exclude_known_cantrips(registry):
    hero = grow(registry, 4)
    options = choice_options(hero, registry, "cantrip", LevelChoices(level=4))
    assert options
    assert not set(options) & set(CANTRIPS)
    assert {registry.get("spell", s).level for s in options} == {0}


def test_second_cantrip_at_level_4_is_error(registry):
    hero = grow(registry, 4)
    choices = fill(hero, registry, 4)
    choices.feature_choices["cantrip"] = ["acid_splash", "ray_of_frost"]
    assert "cantrip_invalid" in codes(choice_errors(hero, registry, choices))


def test_foreign_cantrip_from_a_feat_does_not_count_against_the_class_limit(registry):
    hero = grow(registry, 4)
    foreign = "sacred_flame"
    assert "wizard" not in registry.get("spell", foreign).classes
    hero.sheet.known_of().append(foreign)
    choices = fill(hero, registry, 4)
    assert "cantrip_invalid" not in codes(choice_errors(hero, registry, choices))
    assert known_cantrips(hero, registry) == CANTRIPS


def test_foreign_cantrip_is_not_a_cantrip_candidate_and_does_not_hide_class_ones(registry):
    hero = grow(registry, 4)
    hero.sheet.known_of().append("sacred_flame")
    options = choice_options(hero, registry, "cantrip", LevelChoices(level=4))
    assert "sacred_flame" not in options
    assert "acid_splash" in options


def test_cantrip_pick_goes_into_known_spells(registry):
    hero = grow(registry, 4)
    choices = fill(hero, registry, 4)
    assert apply_level_choices(hero, registry, choices) is None
    picked_cantrip = choices.feature_choices["cantrip"][0]
    assert picked_cantrip in hero.sheet.known_of()
    assert "cantrip" not in hero.sheet.feature_choices


def test_level_5_takes_one_savant_spell_of_third_circle_range(registry):
    hero = grow(registry, 5)
    needed = required_choices(hero, registry, 5)
    assert "spellbook" in needed
    assert picks_due(hero, registry, "savant_spell", 5) == 1
    assert max_circle(hero, registry) == 3


def test_book_has_seventeen_spells_at_level_5(registry):
    hero = grow(registry, 5)
    choices = fill(hero, registry, 5)
    assert choice_errors(hero, registry, choices) == []
    assert apply_level_choices(hero, registry, choices) is None
    assert len(book_spells(hero, registry)) == 17


# рабочие функции модуля

def test_picked_joins_keys_and_tolerates_missing_choices():
    choices = LevelChoices(level=2, feature_choices={"spellbook": ["a"], "savant_spell": ["b"]})
    assert picked(choices, "spellbook", "savant_spell") == ["a", "b"]
    assert picked(choices, "cantrip") == []
    assert picked(None, *PICK_KEYS) == []


def test_picks_missing_until_the_due_number_is_chosen(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2)
    assert picks_missing(hero, registry, choices, "spellbook") is True
    choices.feature_choices["spellbook"] = ["grease"]
    assert picks_missing(hero, registry, choices, "spellbook") is True
    choices.feature_choices["spellbook"] = ["grease", "jump"]
    assert picks_missing(hero, registry, choices, "spellbook") is False


def test_picks_due_for_non_book_class_is_zero(registry):
    hero = grow(registry, 2)
    hero.sheet.classes[0].class_id = "cleric"
    assert hero.sheet.class_id == "cleric"
    assert picks_due(hero, registry, "spellbook", 2) == 0


def test_missing_choices_name_the_book_and_cantrip_picks(registry):
    hero = grow(registry, 4)
    text = " ".join(missing_choices(hero, registry, LevelChoices(level=4)))
    assert "заговор" in text
    hero = grow(registry, 2)
    assert "заклинание в книгу" in " ".join(missing_choices(hero, registry, LevelChoices(level=2)))


def test_max_circle_follows_the_slots(registry):
    assert [max_circle(grow(registry, n), registry) for n in (1, 2, 3, 5)] == [1, 1, 2, 3]


@pytest.mark.parametrize("level", [1, 2, 3, 4, 5])
def test_non_caster_has_no_max_circle(registry, level):
    from test_classes_1_20 import hero_at

    assert max_circle(hero_at(registry, "fighter", level), registry) == 0


def test_caster_with_no_slot_row_for_the_level_has_max_circle_zero(registry):
    from test_classes_1_20 import hero_at

    ranger = hero_at(registry, "ranger", 2)
    ranger.sheet.classes[0].level = 21  # за таблицей ячеек: строки уровня нет
    assert registry.get("class", "ranger").spellcasting is not None
    assert max_circle(ranger, registry) == 0


def test_book_growth_is_two_for_the_wizard_and_zero_for_others(registry):
    assert book_growth(registry.get("class", "wizard")) == 2
    assert book_growth(registry.get("class", "cleric")) == 0
    assert book_growth(registry.get("class", "fighter")) == 0


def test_picks_due_for_cantrips_follows_the_class_table(registry):
    hero = grow(registry, 1)
    assert [picks_due(hero, registry, "cantrip", n) for n in (3, 4, 5)] == [0, 1, 0]


def test_picks_due_for_the_book_ignores_the_level_and_savant_needs_the_subclass(registry):
    hero = grow(registry, 1)
    assert picks_due(hero, registry, "spellbook", 7) == 2
    assert picks_due(hero, registry, "savant_spell", 3) == 0


def test_picks_due_for_savant_uses_the_subclass_of_the_hero_sheet(registry):
    hero = grow(registry, 3)
    hero.sheet.classes[0].subclass_id = "evoker"
    assert picks_due(hero, registry, "savant_spell", 3) == 2
    assert picks_due(hero, registry, "savant_spell", 5) == 1


def test_cantrip_options_exclude_cantrips_picked_on_this_level(registry):
    hero = grow(registry, 4)
    choices = LevelChoices(level=4, feature_choices={"cantrip": ["acid_splash"]})
    options = choice_options(hero, registry, "cantrip", choices)
    assert "acid_splash" not in options
    assert "ray_of_frost" in options


def test_book_errors_check_later_keys_after_a_key_without_picks(registry):
    hero = grow(registry, 2)
    choices = LevelChoices(level=2, feature_choices={"savant_spell": ["shatter"]})
    assert "savant_spell_invalid" in codes(book_errors(hero, registry, choices, set()))


def test_book_errors_check_later_keys_after_a_key_not_needed(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(
        level=3,
        feature_choices={"cantrip": ["acid_splash"], "spellbook": ["web", "grease", "jump"]},
    )
    errors = book_errors(hero, registry, choices, {"spellbook"})
    assert "cantrip_invalid" in codes(errors)
    assert "spellbook_invalid" in codes(errors)


def test_book_errors_keep_errors_of_earlier_keys(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="evoker",
        feature_choices={"spellbook": ["web", "grease", "jump"],
                         "savant_spell": ["scorching_ray", "shatter"]},
    )
    errors = book_errors(hero, registry, choices, {"spellbook", "savant_spell"})
    assert codes(errors) == ["spellbook_invalid"]


def test_book_errors_find_a_repeat_between_cantrip_and_savant_picks(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="evoker",
        feature_choices={"cantrip": ["acid_splash"], "spellbook": ["grease"],
                         "savant_spell": ["acid_splash"]},
    )
    errors = book_errors(hero, registry, choices, set(PICK_KEYS))
    assert ("savant_spell_invalid", "заклинание выбрано дважды: acid_splash") in errors


def test_book_errors_cantrip_total_over_the_class_limit(registry):
    hero = grow(registry, 4)
    hero.sheet.known_of().append("ray_of_frost")  # заговоров класса уже 4 из 4
    choices = LevelChoices(level=4, feature_choices={"cantrip": ["acid_splash"]})
    assert book_errors(hero, registry, choices, {"cantrip"}) == [
        ("cantrip_invalid", "заговоров больше 4")]


def test_book_errors_cantrip_within_the_class_limit_is_ok(registry):
    hero = grow(registry, 4)
    choices = LevelChoices(level=4, feature_choices={"cantrip": ["acid_splash"]})
    assert book_errors(hero, registry, choices, {"cantrip"}) == []


def test_next_choice_at_level_4_asks_the_cantrip_then_the_asi(registry):
    hero = grow(registry, 4)
    choices = LevelChoices(level=4)
    assert next_choice(hero, registry, choices) == "cantrip"
    choices.feature_choices["cantrip"] = ["acid_splash"]
    assert next_choice(hero, registry, choices) == "spellbook"
    choices.feature_choices["spellbook"] = ["grease", "jump"]
    assert next_choice(hero, registry, choices) == "asi_or_feat"


def test_savant_spell_of_this_level_can_be_prepared_without_errors(registry):
    hero = grow(registry, 3)
    choices = LevelChoices(
        level=3, subclass_id="evoker", spells_add=["scorching_ray"],
        feature_choices={"spellbook": ["web", "grease"],
                         "savant_spell": ["scorching_ray", "shatter"]},
    )
    assert "spells_invalid" not in codes(choice_errors(hero, registry, choices))
