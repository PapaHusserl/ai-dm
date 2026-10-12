# Б2а (B2-PLAN, A5): game.hero_steps -- черновик, таблица шагов, сборка листа (без UI).
# Ожидаемый API (ТРЕБОВАНИЕ к коду Б2а): Draft (dataclass: species_id, class_id, background,
#   ability_method, scores, bonus_scheme, bonus, class_skills, masteries, style, cantrips, spells,
#   prepared, species_skill, species_feat, feat_picks_bg, feat_picks_species, kit, gear, name,
#   motive, means, taken_names), StepDef (key, attr, kind, title, needs, options, count, put,
#   label, on_error), Option(value, label), STEPS (порядок В1а), clear_from(draft, key),
#   to_sheet(draft, registry) -> HeroSheet, step_for_code(code) -> key шага.
# Тексты ошибок ввода (put) проверяются на уровне HeroWizard (test_ui_hero_wizard): там видно,
# что получает игрок. Свойство валидности: любой путь «всегда первый пункт» проходит sheet_check.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from hero_kit import (  # noqa: E402
    SCORES,
    deps,
    first_option_walk,
    sheet_task,
    vale_pack,
    wizard_sheet,
)

from ai_dm.rules.builder import sheet_check  # noqa: E402
from ai_dm.state.hero import BackgroundSpec  # noqa: E402

KEYS = [
    "species", "class", "background", "method", "scores", "bonus_scheme", "bonus", "class_skills",
    "masteries", "style", "cantrips", "spells", "prepared", "species_skill", "species_feat",
    "feat_picks_bg", "feat_picks_species", "kit", "gear", "name", "gender", "pronouns", "motive",
    "means",
]


def steps():
    from ai_dm.game.hero_steps import STEPS

    return STEPS


def step(key):
    return next(s for s in steps() if s.key == key)


def draft(**kw):
    from ai_dm.game.hero_steps import Draft

    return Draft(**kw)


def keys_for(registry, **kw):
    # ключи шагов, которые нужны при таком черновике
    current = draft(**kw)
    return [s.key for s in steps() if s.needs is None or s.needs(current, registry)]


def values(key, current, registry):
    return [option.value for option in step(key).options(current, registry)]


def labels(key, current, registry):
    return [option.label for option in step(key).options(current, registry)]


# таблица шагов

def test_steps_follow_the_srd_order_with_technical_inserts():
    assert [s.key for s in steps()] == KEYS


def test_steps_are_a_tuple_of_frozen_records():
    from dataclasses import FrozenInstanceError

    assert isinstance(steps(), tuple)
    with pytest.raises(FrozenInstanceError):
        steps()[0].key = "other"


def test_step_kinds():
    kinds = {s.key: s.kind for s in steps()}
    assert kinds["species"] == "pick"
    assert kinds["class_skills"] == "multi"
    assert kinds["masteries"] == "multi"
    assert kinds["cantrips"] == "multi"
    assert kinds["spells"] == "multi"
    assert kinds["prepared"] == "multi"
    assert kinds["name"] == "text"
    assert kinds["motive"] == "text"
    assert kinds["means"] == "text"


def test_basic_steps_are_always_needed():
    for key in ("species", "class", "background", "method", "scores", "class_skills", "gear"):
        assert step(key).needs is None
    for key in ("name", "motive", "means"):
        assert step(key).needs is None


# условные шаги: из реестра, не из id классов

def test_fighter_human_soldier_has_masteries_style_species_choices(registry):
    keys = keys_for(registry, species_id="human", class_id="fighter", background="soldier")
    for key in ("masteries", "style", "species_skill", "species_feat"):
        assert key in keys
    for key in ("cantrips", "spells", "prepared"):
        assert key not in keys


def test_soldier_background_feat_has_no_picks(registry):
    keys = keys_for(registry, species_id="human", class_id="fighter", background="soldier")
    assert "feat_picks_bg" not in keys
    assert "feat_picks_species" not in keys


def test_skilled_species_feat_adds_feat_picks_of_species(registry):
    keys = keys_for(
        registry, species_id="human", class_id="fighter", background="soldier",
        species_skill="stealth", species_feat="skilled",
    )
    assert "feat_picks_species" in keys
    assert "feat_picks_bg" not in keys


def test_alert_species_feat_has_no_picks(registry):
    keys = keys_for(
        registry, species_id="human", class_id="fighter", background="soldier",
        species_skill="stealth", species_feat="alert",
    )
    assert "feat_picks_species" not in keys


def test_free_background_with_skilled_feat_adds_feat_picks_of_background(registry):
    spec = BackgroundSpec(
        name="Ученик", abilities=["int", "wis", "cha"], skills=["history", "insight"],
        tool="calligraphers_supplies", feat="skilled",
    )
    keys = keys_for(registry, species_id="elf", class_id="fighter", background=spec)
    assert "feat_picks_bg" in keys


def test_wizard_elf_sage_has_spell_steps_and_no_weapon_steps(registry):
    keys = keys_for(
        registry, species_id="elf", class_id="wizard", background="sage", spells=["alarm"],
    )
    for key in ("cantrips", "spells", "prepared"):
        assert key in keys
    for key in ("masteries", "style", "species_skill", "species_feat"):
        assert key not in keys


def test_ranger_has_spells_but_no_cantrips_and_no_style_at_level_1(registry):
    keys = keys_for(
        registry, species_id="elf", class_id="ranger", background="soldier", spells=["alarm"],
    )
    assert "cantrips" not in keys
    assert "spells" in keys
    assert "prepared" in keys
    assert "style" not in keys
    assert "masteries" in keys


def test_prepared_step_waits_for_chosen_spells(registry):
    empty = keys_for(registry, species_id="elf", class_id="wizard", background="sage")
    assert "prepared" not in empty


def test_rogue_has_masteries_but_no_style_and_no_spells(registry):
    keys = keys_for(registry, species_id="elf", class_id="rogue", background="criminal")
    assert "masteries" in keys
    assert "style" not in keys
    for key in ("cantrips", "spells", "prepared"):
        assert key not in keys


def test_cleric_has_spell_steps_and_no_masteries(registry):
    # в контенте у жреца нет заговоров (лимит 3, список пуст): шага заговоров нет
    keys = keys_for(
        registry, species_id="dwarf", class_id="cleric", background="acolyte", spells=["bless"],
    )
    assert "cantrips" not in keys
    for key in ("spells", "prepared"):
        assert key in keys
    assert "masteries" not in keys


# меню шагов

def test_species_options_are_the_four_species_with_russian_labels(registry):
    current = draft()
    assert sorted(values("species", current, registry)) == ["dwarf", "elf", "halfling", "human"]
    assert "Человек" in labels("species", current, registry)


def test_class_options_are_the_five_classes_with_russian_labels(registry):
    current = draft()
    assert len(values("class", current, registry)) == 5
    assert "Воин" in labels("class", current, registry)


def test_background_options_are_four_srd_backgrounds_and_describe_in_words(registry):
    current = draft(class_id="fighter")
    shown = values("background", current, registry)
    assert shown[:4] != []
    assert sorted(shown[:4]) == ["acolyte", "criminal", "sage", "soldier"]
    assert shown[4] == "words"
    assert "Солдат" in labels("background", current, registry)


def test_method_options_are_three_methods(registry):
    current = draft(class_id="fighter")
    assert values("method", current, registry) == ["standard_array", "point_buy", "explicit"]


def test_class_skill_count_comes_from_the_class(registry):
    current = draft(species_id="human", class_id="rogue", background="criminal")
    assert step("class_skills").count(current, registry) == 4


def test_class_skills_exclude_background_skills(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    shown = values("class_skills", current, registry)
    assert "athletics" not in shown
    assert "intimidation" not in shown
    assert "perception" in shown


def test_class_skills_exclude_background_skills_of_free_background(registry):
    spec = BackgroundSpec(
        name="Ученик", abilities=["int", "wis", "cha"], skills=["history", "insight"],
        tool="calligraphers_supplies", feat="alert",
    )
    current = draft(species_id="elf", class_id="fighter", background=spec)
    shown = values("class_skills", current, registry)
    assert "history" not in shown
    assert "insight" not in shown


def test_species_skill_excludes_background_and_class_skills(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier",
        class_skills=["perception", "survival"],
    )
    shown = values("species_skill", current, registry)
    for taken in ("athletics", "intimidation", "perception", "survival"):
        assert taken not in shown
    assert "stealth" in shown


def test_species_feat_excludes_background_feat_unless_repeatable(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    shown = values("species_feat", current, registry)
    assert "savage_attacker" not in shown
    assert "skilled" in shown
    sage = draft(species_id="human", class_id="fighter", background="sage")
    assert "magic_initiate" in values("species_feat", sage, registry)


def test_feat_picks_exclude_taken_skills_and_tool(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier",
        class_skills=["perception", "survival"],
        species_skill="stealth", species_feat="skilled",
    )
    shown = values("feat_picks_species", current, registry)
    for taken in ("athletics", "intimidation", "perception", "survival", "stealth", "gaming_set"):
        assert taken not in shown
    assert "medicine" in shown
    assert "thieves_tools" in shown
    assert step("feat_picks_species").count(current, registry) == 3


def test_mastery_weapons_are_class_weapons_and_count_is_three_for_fighter(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert "longsword" in values("masteries", current, registry)
    assert step("masteries").count(current, registry) == 3


def test_style_options_are_the_four_fighting_styles(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert sorted(values("style", current, registry)) == [
        "archery", "defense", "great_weapon_fighting", "two_weapon_fighting",
    ]


def test_spell_steps_of_wizard_are_in_class_limits_and_content(registry):
    # лимиты класса 3/6/4, но в контенте у волшебника 1 заговор и 5 заклинаний 1 круга
    current = draft(species_id="elf", class_id="wizard", background="sage")
    assert step("cantrips").count(current, registry) == 1
    assert step("spells").count(current, registry) == 5
    cantrips = values("cantrips", current, registry)
    spells = values("spells", current, registry)
    assert "fire_bolt" in cantrips
    assert "magic_missile" in spells
    assert not set(cantrips) & set(spells)


def test_prepared_options_come_from_chosen_spells_and_count_is_limited(registry):
    chosen = ["alarm", "burning_hands", "fog_cloud", "longstrider", "magic_missile"]
    current = draft(
        species_id="elf", class_id="wizard", background="sage", spells=chosen,
    )
    assert sorted(values("prepared", current, registry)) == sorted(chosen)
    assert step("prepared").count(current, registry) == 4


def test_prepared_count_is_the_class_limit_when_enough_spells_are_chosen(registry):
    current = draft(
        species_id="elf", class_id="wizard", background="sage",
        spells=["alarm", "burning_hands", "fog_cloud", "longstrider", "magic_missile"],
    )
    assert step("prepared").count(current, registry) == 4


def test_prepared_count_is_not_above_number_of_chosen_spells(registry):
    current = draft(species_id="elf", class_id="ranger", background="soldier", spells=["alarm"])
    assert step("prepared").count(current, registry) == 1


def test_kit_options_are_class_kits_with_item_names(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert values("kit", current, registry) == ["a", "b", "c"]
    assert "кольчуга" in labels("kit", current, registry)[0].lower()


def test_gear_options_are_equipment_or_gold(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert values("gear", current, registry) == ["equipment", "gold"]
    assert "50 зм" in labels("gear", current, registry)[1]


# характеристики

def test_standard_array_scores_offer_only_remaining_values(registry):
    current = draft(ability_method="standard_array", scores={"str": 15, "dex": 13})
    assert sorted(values("scores", current, registry)) == [8, 10, 12, 14]


def test_standard_array_first_ability_offers_all_six_values(registry):
    current = draft(ability_method="standard_array")
    assert sorted(values("scores", current, registry)) == [8, 10, 12, 13, 14, 15]


def test_point_buy_offers_8_to_15_with_prices_in_labels(registry):
    current = draft(ability_method="point_buy")
    assert sorted(values("scores", current, registry)) == list(range(8, 16))
    shown = labels("scores", current, registry)
    assert any("13" in label and "(5 очков)" in label for label in shown)
    assert any("15" in label and "(9 очков)" in label for label in shown)


def test_point_buy_keeps_over_budget_values_in_the_menu(registry):
    current = draft(
        ability_method="point_buy", scores={"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8},
    )
    assert 15 in values("scores", current, registry)


def test_explicit_scores_are_a_number_step(registry):
    current = draft(ability_method="explicit")
    assert step("scores").kind in ("number", "pick")
    assert step("scores").count(current, registry) == 6


def test_bonus_scheme_options(registry):
    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert values("bonus_scheme", current, registry) == ["2+1", "1+1+1"]


def test_bonus_offers_abilities_of_the_background(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        scores=dict(SCORES),
    )
    assert sorted(values("bonus", current, registry)) == ["con", "dex", "str"]


def test_second_bonus_excludes_the_first_ability(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        bonus={"dex": 2}, scores=dict(SCORES),
    )
    assert sorted(values("bonus", current, registry)) == ["con", "str"]


def test_bonus_of_one_one_one_asks_nothing(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="1+1+1",
    )
    assert step("bonus").count(current, registry) == 0 or not step("bonus").needs(
        current, registry
    )


# put: тексты ошибок валидатора

def put(key, current, value, registry):
    return step(key).put(current, value, registry)


def test_explicit_score_above_20_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="explicit")
    assert put("scores", current, "21", registry) == ABILITY_MESSAGES["abilities_invalid"]
    assert current.scores == {}


def test_explicit_score_below_3_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="explicit")
    assert put("scores", current, "2", registry) == ABILITY_MESSAGES["abilities_invalid"]


def test_explicit_score_not_a_number_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="explicit")
    assert put("scores", current, "много", registry) == ABILITY_MESSAGES["abilities_invalid"]


def test_explicit_score_borders_3_and_20_are_accepted(registry):
    current = draft(ability_method="explicit")
    assert put("scores", current, "3", registry) is None
    assert put("scores", current, " 20 ", registry) is None
    assert current.scores == {"str": 3, "dex": 20}


def test_scores_are_stored_by_ability_in_order(registry):
    current = draft(ability_method="explicit")
    for value in ("10", "11", "12", "13", "14", "15"):
        put("scores", current, value, registry)
    assert current.scores == {
        "str": 10, "dex": 11, "con": 12, "int": 13, "wis": 14, "cha": 15,
    }


def test_point_buy_over_remaining_budget_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="point_buy", scores={"str": 15, "dex": 15, "con": 15})
    assert put("scores", current, 15, registry) == ABILITY_MESSAGES["point_buy_invalid"]
    assert len(current.scores) == 3


def test_point_buy_exactly_the_remaining_budget_is_accepted(registry):
    current = draft(ability_method="point_buy", scores={"str": 15, "dex": 15, "con": 15})
    assert put("scores", current, 8, registry) is None
    assert current.scores["int"] == 8


def test_point_buy_value_outside_the_table_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="point_buy")
    assert put("scores", current, 16, registry) == ABILITY_MESSAGES["point_buy_invalid"]
    assert put("scores", current, 7, registry) == ABILITY_MESSAGES["point_buy_invalid"]


def test_standard_array_value_already_used_gives_validator_text(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    current = draft(ability_method="standard_array", scores={"str": 15})
    assert put("scores", current, 15, registry) == ABILITY_MESSAGES["standard_array_invalid"]
    assert put("scores", current, 14, registry) is None


def test_bonus_over_20_gives_over_twenty_text_and_changes_nothing(registry):
    from ai_dm.rules.builder import over_twenty_message

    scores = {**SCORES, "str": 19}
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        scores=scores,
    )
    assert put("bonus", current, "str", registry) == over_twenty_message("str")
    assert current.bonus == {}


def test_bonus_plus_two_then_plus_one_are_stored(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        scores=dict(SCORES),
    )
    assert put("bonus", current, "dex", registry) is None
    assert put("bonus", current, "con", registry) is None
    assert current.bonus == {"dex": 2, "con": 1}


def test_plus_one_to_19_is_accepted_but_plus_two_is_not(registry):
    from ai_dm.rules.builder import over_twenty_message

    scores = {**SCORES, "str": 18}
    current = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        scores=scores,
    )
    assert put("bonus", current, "str", registry) is None
    assert current.bonus == {"str": 2}
    assert put("bonus", current, "dex", registry) is None
    over = draft(
        species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1",
        scores={**SCORES, "str": 19},
    )
    assert put("bonus", over, "dex", registry) is None
    assert put("bonus", over, "str", registry) is None
    assert over.bonus == {"dex": 2, "str": 1}
    assert over_twenty_message("str")


def test_bonus_scheme_two_plus_one_is_only_remembered(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", scores=dict(SCORES),
    )
    assert put("bonus_scheme", current, "2+1", registry) is None
    assert current.bonus_scheme == "2+1"
    assert current.bonus == {}


def test_bonus_scheme_one_one_one_puts_ones_on_all_background_abilities(registry):
    current = draft(
        species_id="human", class_id="fighter", background="soldier", scores=dict(SCORES),
    )
    assert put("bonus_scheme", current, "1+1+1", registry) is None
    assert current.bonus == {"str": 1, "dex": 1, "con": 1}


def test_bonus_scheme_one_one_one_over_20_gives_text_and_changes_nothing(registry):
    from ai_dm.rules.builder import over_twenty_message

    current = draft(
        species_id="human", class_id="fighter", background="soldier",
        scores={**SCORES, "con": 20},
    )
    assert put("bonus_scheme", current, "1+1+1", registry) == over_twenty_message("con")
    assert current.bonus == {}
    assert current.bonus_scheme == ""


def test_needs_bonus_only_for_two_plus_one(registry):
    two = draft(species_id="human", class_id="fighter", background="soldier", bonus_scheme="2+1")
    ones = draft(species_id="human", class_id="fighter", background="soldier", bonus_scheme="1+1+1")
    assert step("bonus").needs(two, registry) is True
    assert step("bonus").needs(ones, registry) is False
    assert step("bonus").count(two, registry) == 2


def test_empty_name_gives_hero_name_empty_text(registry):
    current = draft()
    assert put("name", current, "  ", registry) == "имя героя не может быть пустым"
    assert current.name == ""


def test_taken_name_gives_hero_name_taken_text_in_any_case(registry):
    current = draft(taken_names=["Гракх", "Гарт"])
    assert put("name", current, "ГРАКХ", registry) == (
        "имя 'ГРАКХ' уже занято (NPC, бог, фракция или герой)"
    )
    assert current.name == ""


def test_free_name_is_stored_stripped(registry):
    current = draft(taken_names=["Гракх"])
    assert put("name", current, "  Борин ", registry) is None
    assert current.name == "Борин"


def test_empty_motive_gives_text(registry):
    current = draft()
    assert put("motive", current, " ", registry) == "мотив героя не может быть пустым"
    assert current.motive == ""


def test_motive_of_201_characters_is_too_long_200_is_fine(registry):
    current = draft()
    assert put("motive", current, "м" * 201, registry) == "мотив длиннее 200 символов: сократи"
    assert put("motive", current, "м" * 200, registry) is None
    assert current.motive == "м" * 200


def test_means_are_split_and_stripped(registry):
    current = draft()
    assert put("means", current, " лук ,смелость, ,друзья", registry) is None
    assert current.means == ["лук", "смелость", "друзья"]


def test_zero_means_give_count_text(registry):
    current = draft()
    expected = "средства героя: от одного до трёх средств"
    assert put("means", current, " , ", registry) == expected
    assert current.means == []


def test_four_means_give_count_text(registry):
    current = draft()
    expected = "средства героя: от одного до трёх средств"
    assert put("means", current, "а, б, в, г", registry) == expected
    assert current.means == []


def test_three_means_and_120_characters_are_accepted(registry):
    current = draft()
    assert put("means", current, "а, б, " + "с" * 120, registry) is None


def test_mean_of_121_characters_gives_too_long_text(registry):
    current = draft()
    assert put("means", current, "с" * 121, registry) == (
        "средство длиннее 120 символов: сократи"
    )


# общие помощники таблицы шагов

def test_apply_put_sets_single_value_and_appends_to_multi(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft()
    assert apply_put(current, registry, step_index("species"), "elf") is None
    assert current.species_id == "elf"
    assert apply_put(current, registry, step_index("class_skills"), "perception") is None
    assert apply_put(current, registry, step_index("class_skills"), "survival") is None
    assert current.class_skills == ["perception", "survival"]


def test_apply_put_returns_the_put_error(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft()
    assert apply_put(current, registry, step_index("name"), "") is not None


def test_step_done_for_single_and_counted_steps(registry):
    from ai_dm.game.hero_steps import step_done, step_index

    current = draft(species_id="human", class_id="fighter", background="soldier")
    assert step_done(current, registry, step_index("species")) is True
    pos = step_index("class_skills")
    assert step_done(current, registry, pos) is False
    current.class_skills = ["perception"]
    assert step_done(current, registry, pos) is False
    current.class_skills = ["perception", "survival"]
    assert step_done(current, registry, pos) is True


def test_next_pos_skips_unneeded_steps_and_ends_at_len(registry):
    from ai_dm.game.hero_steps import next_pos, step_index

    wizard = draft(species_id="elf", class_id="wizard", background="sage")
    assert next_pos(wizard, registry, step_index("masteries")) == step_index("cantrips")
    fighter = draft(species_id="elf", class_id="fighter", background="soldier")
    assert next_pos(fighter, registry, step_index("cantrips")) == step_index("kit")
    assert next_pos(fighter, registry, len(steps())) == len(steps())


def test_step_index_matches_the_table_order():
    from ai_dm.game.hero_steps import step_index

    assert [step_index(key) for key in KEYS] == list(range(len(KEYS)))


def test_points_text_declension():
    from ai_dm.game.hero_steps import points_text

    assert points_text(0) == "0 очков"
    assert points_text(1) == "1 очко"
    assert points_text(2) == "2 очка"
    assert points_text(4) == "4 очка"
    assert points_text(5) == "5 очков"
    assert points_text(9) == "9 очков"
    assert points_text(11) == "11 очков"
    assert points_text(14) == "14 очков"
    assert points_text(21) == "21 очко"
    assert points_text(22) == "22 очка"
    assert points_text(27) == "27 очков"


def test_scores_label_names_the_ability_and_points_left(registry):
    current = draft(ability_method="point_buy", scores={"str": 15})
    label = step("scores").label(current, registry)
    assert "Ловкость" in label
    assert "осталось 18 очков" in label


def test_scores_label_of_first_ability_has_full_budget(registry):
    label = step("scores").label(draft(ability_method="point_buy"), registry)
    assert "Сила" in label
    assert "осталось 27 очков" in label


def test_scores_label_of_explicit_asks_for_3_to_20(registry):
    label = step("scores").label(draft(ability_method="explicit"), registry)
    assert "3 до 20" in label


def test_scores_label_of_standard_array_names_the_ability(registry):
    label = step("scores").label(draft(ability_method="standard_array"), registry)
    assert label == "Характеристика Сила"


def test_bonus_label_tells_plus_two_then_plus_one(registry):
    assert "+2" in step("bonus").label(draft(), registry)
    assert "+1" in step("bonus").label(draft(bonus={"dex": 2}), registry)


def test_bonus_on_error_goes_back_to_scheme():
    assert step("bonus").on_error == "bonus_scheme"


# clear_from

def full_draft():
    return draft(
        species_id="human", class_id="fighter", background="soldier",
        ability_method="standard_array", scores=dict(SCORES), bonus_scheme="2+1",
        bonus={"dex": 2, "con": 1}, class_skills=["perception", "survival"],
        masteries=["longsword", "greatsword", "shortsword"], style="defense",
        species_skill="stealth", species_feat="skilled",
        feat_picks_species=["medicine", "religion", "nature"], kit="a", gear="equipment",
        name="Борин", motive="Найти сестру.", means=["острый ум"],
    )


def test_clear_from_class_resets_everything_after_class(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "class")
    assert current.class_id == ""
    assert current.background in (None, "")
    assert current.ability_method == ""
    assert current.scores == {}
    assert current.bonus == {}
    assert current.bonus_scheme == ""
    assert current.class_skills == []
    assert current.masteries == []
    assert current.style is None
    assert current.species_skill == ""
    assert current.species_feat == ""
    assert current.feat_picks_species == []
    assert current.kit is None
    assert current.name == ""
    assert current.motive == ""
    assert current.means == []


def test_clear_from_class_keeps_species(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "class")
    assert current.species_id == "human"


def test_clear_from_species_resets_species_too(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "species")
    assert current.species_id == ""
    assert current.class_id == ""


def test_clear_from_class_skills_keeps_scores_and_bonus(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "class_skills")
    assert current.scores == SCORES
    assert current.bonus == {"dex": 2, "con": 1}
    assert current.bonus_scheme == "2+1"
    assert current.class_skills == []
    assert current.masteries == []
    assert current.species_skill == ""


def test_clear_from_scores_keeps_method_and_clears_bonus(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "scores")
    assert current.ability_method == "standard_array"
    assert current.scores == {}
    assert current.bonus == {}
    assert current.bonus_scheme == ""


def test_clear_from_name_keeps_everything_before(registry):
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    clear_from(current, "name")
    assert current.kit == "a"
    assert current.gear == "equipment"
    assert current.name == ""
    assert current.motive == ""
    assert current.means == []


# to_sheet

def test_to_sheet_of_the_canonical_draft_equals_b1_canon(registry):
    from ai_dm.game.hero_steps import to_sheet

    assert to_sheet(full_draft(), registry) == wizard_sheet()


def test_to_sheet_has_empty_opportunity_and_no_inventory(registry):
    from ai_dm.game.hero_steps import to_sheet

    sheet = to_sheet(full_draft(), registry)
    assert sheet.opportunity == []
    assert sheet.choices.inventory == []
    assert sheet.choices.equip == []


def test_to_sheet_joins_cantrips_and_spells_into_spells(registry):
    from ai_dm.game.hero_steps import to_sheet

    current = draft(
        species_id="elf", class_id="wizard", background="sage", ability_method="standard_array",
        scores={"str": 8, "dex": 13, "con": 14, "int": 15, "wis": 12, "cha": 10},
        bonus_scheme="2+1", bonus={"int": 2, "con": 1}, class_skills=["arcana", "history"],
        cantrips=["fire_bolt"], spells=["alarm", "magic_missile"], prepared=["alarm"],
        kit="a", gear="equipment", name="Лиэль", motive="Учиться.", means=["книги"],
    )
    choices = to_sheet(current, registry).choices
    assert choices.spells == ["fire_bolt", "alarm", "magic_missile"]
    assert choices.prepared == ["alarm"]
    assert choices.species_choices == {}
    assert choices.feat_choices == {}


def test_to_sheet_species_choices_are_skill_and_feat(registry):
    from ai_dm.game.hero_steps import to_sheet

    choices = to_sheet(full_draft(), registry).choices
    assert choices.species_choices == {"skill": "stealth", "feat": "skilled"}
    assert choices.feat_choices == {"skilled": ["medicine", "religion", "nature"]}


def test_to_sheet_bonus_one_one_one_is_ones(registry):
    from ai_dm.game.hero_steps import to_sheet

    current = full_draft()
    current.bonus = {"str": 1, "dex": 1, "con": 1}
    current.bonus_scheme = "1+1+1"
    assert to_sheet(current, registry).choices.background_bonus == {"str": 1, "dex": 1, "con": 1}


def test_to_sheet_keeps_free_background_spec(registry):
    from ai_dm.game.hero_steps import to_sheet

    spec = BackgroundSpec(
        name="Ученик", abilities=["str", "dex", "con"], skills=["history", "insight"],
        tool="calligraphers_supplies", feat="alert",
    )
    current = full_draft()
    current.background = spec
    assert to_sheet(current, registry).choices.background == spec


def test_to_sheet_feat_choices_use_origin_keys_for_same_feat_twice(registry):
    from ai_dm.game.hero_steps import to_sheet

    spec = BackgroundSpec(
        name="Ученик", abilities=["str", "dex", "con"], skills=["history", "insight"],
        tool="calligraphers_supplies", feat="skilled",
    )
    current = full_draft()
    current.background = spec
    current.feat_picks_bg = ["arcana", "deception", "persuasion"]
    assert to_sheet(current, registry).choices.feat_choices == {
        "skilled": ["arcana", "deception", "persuasion"],
        "skilled#2": ["medicine", "religion", "nature"],
    }


def test_to_sheet_builds_a_valid_sheet_for_free_background_with_skilled(registry):
    from ai_dm.game.hero_steps import to_sheet

    spec = BackgroundSpec(
        name="Ученик", abilities=["str", "dex", "con"], skills=["history", "insight"],
        tool="calligraphers_supplies", feat="skilled",
    )
    current = full_draft()
    current.background = spec
    current.feat_picks_bg = ["arcana", "deception", "persuasion"]
    assert sheet_check(to_sheet(current, registry), registry) == ([], [])


# step_for_code

@pytest.mark.parametrize(
    ("code", "key"),
    [
        ("class_skills_invalid", "class_skills"),
        ("spells_invalid", "cantrips"),
        ("species_choices_invalid", "species_skill"),
        ("feat_choices_invalid", "feat_picks_bg"),
        ("background_bonus_invalid", "bonus_scheme"),
        ("abilities_invalid", "bonus_scheme"),
        ("point_buy_invalid", "method"),
        ("standard_array_invalid", "method"),
        ("hero_name_empty", "name"),
        ("hero_name_taken", "name"),
        ("motive_empty", "motive"),
        ("motive_too_long", "motive"),
        ("means_count", "means"),
        ("means_too_long", "means"),
        ("unknown_class", "species"),
    ],
)
def test_step_for_code_points_to_the_step_to_return_to(code, key):
    from ai_dm.game.hero_steps import step_for_code

    assert step_for_code(code) == key


def test_step_for_code_gives_existing_step_keys():
    from ai_dm.game.hero_steps import step_for_code

    for code in ("class_skills_invalid", "hero_name_taken", "motive_empty", "no_such_code"):
        assert step_for_code(code) in KEYS


# background_summary_lines

def test_background_summary_lines_show_the_background_in_russian(registry):
    from ai_dm.game.hero_steps import background_summary_lines

    spec = BackgroundSpec(
        name="Бывший цирковой акробат", abilities=["dex", "con", "cha"],
        skills=["acrobatics", "performance"], tool="thieves_tools", feat="alert",
        equipment=["crowbar"], gold_cp=1000, description="Вырос в бродячем цирке.",
    )
    text = "\n".join(background_summary_lines(spec, registry))
    assert "Бывший цирковой акробат" in text
    assert "Ловкость" in text
    assert "Акробатика" in text
    assert "Выступление" in text
    assert "Вырос в бродячем цирке." in text
    assert "acrobatics" not in text
    assert "dex" not in text


# свойство валидности: меню разрешило -- валидатор принимает

def accepted_sheet(registry, cfg, **walk_kw):
    from ai_dm.ui.hero_wizard import HeroWizard

    pack = vale_pack(registry)
    task = sheet_task(pack)
    wizard = HeroWizard(deps(None, registry, cfg), task, 80)
    first_option_walk(wizard, **walk_kw)
    wizard.submit("1")
    return wizard.sheet, task


@pytest.mark.parametrize("species", [1, 2, 3, 4])
@pytest.mark.parametrize("cls", [1, 2, 3, 4, 5])
def test_first_option_walk_is_valid_for_every_background_and_method(
    registry, cfg, species, cls
):
    # 4 вида x 5 классов x 4 предыстории x 3 метода = 240 комбинаций, без ИИ
    for background in (1, 2, 3, 4):
        for method in (1, 2, 3):
            sheet, task = accepted_sheet(
                registry, cfg, species=species, cls=cls, background=background, method=method
            )
            assert sheet is not None
            found = sheet_check(
                sheet, registry, known=task.known, taken_names=task.taken_names
            )
            assert found == ([], []), (species, cls, background, method)


# добивка по выжившим мутантам mutmut (Б2а)

def test_points_text_remaining_endings():
    from ai_dm.game.hero_steps import points_text

    for count in (6, 7, 8, 10, 12, 13, 15, 16, 20, 25, 26):
        assert points_text(count) == f"{count} очков"
    assert points_text(23) == "23 очка"
    assert points_text(24) == "24 очка"


def test_method_labels_are_exact(registry):
    assert labels("method", draft(), registry) == [
        "Стандартный набор (15,14,13,12,10,8)", "Покупка очков (27)", "Свободный ввод (3..20)",
    ]


def test_bonus_scheme_labels_are_exact(registry):
    assert labels("bonus_scheme", draft(), registry) == ["+2 и +1", "+1, +1, +1"]


def test_gear_labels_are_exact(registry):
    assert labels("gear", draft(), registry) == [
        "Снаряжение предыстории", "50 зм вместо снаряжения",
    ]


def test_bonus_labels_are_exact(registry):
    assert step("bonus").label(draft(), registry) == "Бонус предыстории +2"
    assert step("bonus").label(draft(bonus={"dex": 2}), registry) == "Бонус предыстории +1"


def test_spell_menus_show_russian_names(registry):
    current = draft(species_id="elf", class_id="wizard", background="sage")
    assert labels("cantrips", current, registry) == [registry.get("spell", "fire_bolt").name]
    assert registry.get("spell", "alarm").name in labels("spells", current, registry)
    current.spells = ["alarm", "magic_missile"]
    assert labels("prepared", current, registry) == [
        registry.get("spell", "alarm").name, registry.get("spell", "magic_missile").name,
    ]


def test_to_sheet_gear_gold_is_kept_and_empty_gear_means_equipment(registry):
    from ai_dm.game.hero_steps import to_sheet

    current = full_draft()
    current.gear = "gold"
    assert to_sheet(current, registry).choices.background_gear == "gold"
    current.gear = ""
    assert to_sheet(current, registry).choices.background_gear == "equipment"


def test_to_sheet_without_species_feat_has_no_feat_choices_for_extra_picks(registry):
    from ai_dm.game.hero_steps import to_sheet

    current = full_draft()
    current.species_feat = ""
    current.species_skill = ""
    current.feat_picks_species = []
    assert to_sheet(current, registry).choices.feat_choices == {}


def test_background_summary_lines_exact(registry):
    from ai_dm.game.hero_steps import background_summary_lines

    spec = BackgroundSpec(
        name="Бывший цирковой акробат", abilities=["dex", "con", "cha"],
        skills=["acrobatics", "performance"], tool="thieves_tools", feat="alert",
        equipment=["crowbar"], gold_cp=1000, gold_option_cp=5000,
        description="Вырос в бродячем цирке.",
    )
    assert background_summary_lines(spec, registry) == [
        "Предыстория: Бывший цирковой акробат",
        "Характеристики: Ловкость, Телосложение, Харизма",
        "Навыки: Акробатика, Выступление",
        "Инструмент: Воровские инструменты",
        "Черта: Бдительность",
        "Снаряжение: Лом; 10 зм",
        "Вместо снаряжения: 50 зм",
        "Вырос в бродячем цирке.",
    ]


def test_background_summary_lines_without_gear_and_description(registry):
    from ai_dm.game.hero_steps import background_summary_lines

    spec = BackgroundSpec(
        name="Ученик", abilities=["int", "wis", "cha"], skills=["history", "insight"],
        tool="thieves_tools", feat="alert", gold_cp=1000, gold_option_cp=5000,
    )
    lines = background_summary_lines(spec, registry)
    assert lines[-2] == "Снаряжение: нет; 10 зм"
    assert lines[-1] == "Вместо снаряжения: 50 зм"
    assert len(lines) == 7


def test_background_summary_lines_join_several_items_with_comma(registry):
    from ai_dm.game.hero_steps import background_summary_lines

    spec = BackgroundSpec(
        name="Ученик", abilities=["int", "wis", "cha"], skills=["history", "insight"],
        tool="thieves_tools", feat="alert", equipment=["crowbar", "dagger"], gold_cp=1000,
    )
    gear_line = background_summary_lines(spec, registry)[5]
    assert gear_line == "Снаряжение: Лом, Кинжал; 10 зм"


# правки по ревью Б2а: ввод строкой решает вид шага

def test_is_text_step_for_text_steps_and_explicit_scores_only():
    from ai_dm.game.hero_steps import is_text_step, step_index

    for key in ("name", "motive", "means"):
        assert is_text_step(draft(), step_index(key)) is True
    scores = step_index("scores")
    assert is_text_step(draft(ability_method="explicit"), scores) is True
    assert is_text_step(draft(ability_method="standard_array"), scores) is False
    assert is_text_step(draft(ability_method="point_buy"), scores) is False
    for key in ("species", "class_skills", "kit", "bonus"):
        assert is_text_step(draft(ability_method="explicit"), step_index(key)) is False
