# Ожидаемый API: ai_dm.rules.builder
#   CharacterChoices(BaseModel, extra="forbid"):
#     name: str, species_id: str, class_id: str,
#     background: str | BackgroundSpec          -- id предыстории SRD или произвольная (нарративная)
#     ability_method: "standard_array" | "point_buy" | "explicit"
#     ability_scores: dict[str, int]            -- ключи str/dex/con/int/wis/cha:
#         standard_array -- каждое из 15,14,13,12,10,8 ровно по разу (таблица реестра
#                     standard_array, а не константа в коде -- аудит 1 п. 2.10);
#         point_buy -- каждое 8..15, сумма стоимости <= 27 (таблица реестра point_buy:
#                     8:0 9:1 10:2 11:3 12:4 13:5 14:7 15:9, rows["budget"] == 27);
#         explicit -- каждое 3..20 до бонуса предыстории и не больше 20 после бонуса
#                     (иначе abilities_invalid; для остальных методов выше 20 после бонуса тоже);
#                     explicit доступен и при создании на лету -- со своей BackgroundSpec (P8)
#     background_bonus: dict[str, int]          -- {a: 2, b: 1} или {a: 1, b: 1, c: 1}, ключи --
#                                                  из abilities предыстории; прибавляется
#     class_skills: list[str]                   -- ровно class.skill_choices.count из options;
#                                                  не пересекаются с навыками предыстории
#     weapon_masteries: list[str]               -- id оружия с мастерством, ровно
#                                                  class.weapon_mastery_count штук, без повторов,
#                                                  только оружие, которым класс владеет
#     fighting_style: str | None = None         -- id черты category=fighting_style; только если у
#                                                  класса есть умение fighting_style
#     spells: list[str] = []                    -- заклинания героя: из списка класса, круг не выше
#                                                  доступного на 1 уровне; -> sheet.spells_known
#     prepared: list[str] = []                  -- подготовленные (P4): подмножество выбранных
#                                                  заклинаний 1+ круга без повторов, не больше
#                                                  Spellcasting.prepared; -> sheet.spells_prepared
#                                                  как выбрано, без «первые N»; иначе spells_invalid
#     feat_choices: dict[str, list[str]] = {}   -- выбор черт происхождения (п. 2.1): Одарённый --
#                                                  3 навыка из Skill или id инструментов; ключ --
#                                                  id черты, у второй такой же черты (предыстория +
#                                                  Универсальность) -- "<id>#2"; навык, который уже
#                                                  есть (предыстория, класс, вид, другая черта) или
#                                                  повтор внутри выбора, а также лишний/недостающий
#                                                  ключ или не 3 элемента -> feat_choices_invalid
#     inventory: list[str] = [], equip: list[str] = []   -- id предметов; equip -- подмножество
#     species_choices: dict = {}                -- выборы вида; человеку обязательны:
#                                                  {"skill": <новый навык>, "feat": <черта origin;
#                                                  та же, что у предыстории, -- только Repeatable
#                                                  (skilled, magic_initiate), P5>}
#     background_gear: "equipment" | "gold" = "equipment"  -- вариант A (предметы и золото
#                                                  предыстории) или B (5000 мм)
#     hero_id: str = "h1", ordinal: int = 1
#   ValidationErrors: .codes: list[str] (все найденные ошибки, не только первая), .messages
#       (человекочитаемые по-русски, по одному на код; сам код в тексте не показывается)
#   build_character(choices, registry) -> HeroState | ValidationErrors   (исключений не бросает)
#   validate_background(spec: BackgroundSpec, registry) -> list[str]     -- коды ошибок, [] = ок
#   Коды: unknown_class, unknown_species, unknown_background, background_bonus_invalid,
#     background_abilities, background_skills, background_tool, background_feat,
#     standard_array_invalid, point_buy_invalid, abilities_invalid, class_skills_invalid,
#     mastery_count_invalid, mastery_weapon_invalid, fighting_style_invalid, spells_invalid,
#     species_choices_invalid, feat_choices_invalid,
#     background_budget_invalid -- свободная предыстория: цены предметов + gold_cp > 5000 мм (P3),
#     item_unknown  -- предмета нет в контенте (в choices.inventory или в снаряжении предыстории),
#     equip_invalid -- надеваемого нет в инвентаре, предмет нельзя надеть (зелье), двуручное
#                      оружие со щитом, доспех без владения.
#   Результат (HeroState): sheet.abilities -- итоговые (с background_bonus); creature.hp_max ==
#     hp_current == hit_die + мод. ТЕЛ на 1 уровне; sheet.skill_proficiencies = навыки предыстории +
#     class_skills (+ species_choices["skill"]); sheet.feats = черта предыстории (+ fighting_style)
#     (+ species_choices["feat"]); sheet.tool_proficiencies содержит инструмент предыстории;
#     sheet.weapon_masteries; sheet.spells_known; creature.resources -- пулы: second_wind
#     (воин, 2/2), spell_slot:N (заклинатели); inventory -- снаряжение предыстории + choices;
#     money_cp -- золото предыстории (вариант B: gold_option_cp предыстории); equipped из choices.
import re

import pytest

from ai_dm.content.loader import load_registry
from ai_dm.content.registry import ContentRegistry
from ai_dm.rules.builder import (
    CharacterChoices,
    ValidationErrors,
    background_from_registry,
    build_character,
    validate_background,
)
from ai_dm.rules.derived import armor_class, proficiency
from ai_dm.rules.inventory import count_item
from ai_dm.state.hero import BackgroundSpec


def fighter_choices(**changes):
    choices = CharacterChoices(
        name="Арн",
        species_id="human",
        class_id="fighter",
        background="soldier",
        ability_method="standard_array",
        ability_scores={"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12},
        background_bonus={"str": 2, "con": 1},
        class_skills=["perception", "survival"],
        weapon_masteries=["longsword", "greatsword", "shortsword"],
        fighting_style="defense",
        inventory=["chain_mail", "shield", "longsword"],
        equip=["chain_mail", "shield", "longsword"],
        species_choices={"skill": "stealth", "feat": "skilled"},
        feat_choices={"skilled": ["medicine", "religion", "nature"]},
    )
    return choices.model_copy(update=changes)


def wizard_choices(**changes):
    choices = CharacterChoices(
        name="Лиэль",
        species_id="elf",
        class_id="wizard",
        background="sage",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 13, "con": 14, "int": 15, "wis": 12, "cha": 10},
        background_bonus={"int": 2, "con": 1},
        class_skills=["investigation", "medicine"],
        weapon_masteries=[],
    )
    return choices.model_copy(update=changes)


def custom_background(**changes):
    spec = BackgroundSpec(
        name="Бывший цирковой акробат",
        abilities=["dex", "con", "cha"],
        skills=["acrobatics", "performance"],
        tool="disguise_kit",
        feat="alert",
    )
    return spec.model_copy(update=changes)


# сценарий «человек-воин-солдат»

def test_fighter_is_built(registry):
    assert not isinstance(build_character(fighter_choices(), registry), ValidationErrors)


def test_fighter_keeps_name_species_class(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.name == "Арн"
    assert hero.sheet.species_id == "human"
    assert hero.sheet.class_id == "fighter"
    assert hero.sheet.level == 1


def test_fighter_abilities_include_background_bonus(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.sheet.abilities == {
        "str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12,
    }


def test_fighter_hp_is_hit_die_plus_con_modifier(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.creature.hp_max == 10 + 2
    assert hero.creature.hp_current == 12


def test_wizard_hp_is_d6_plus_con_modifier(registry):
    hero = build_character(wizard_choices(), registry)
    # ТЕЛ 14 + 1 = 15 -> +2
    assert hero.creature.hp_max == 6 + 2


def test_fighter_proficiency_bonus_is_2(registry):
    assert proficiency(build_character(fighter_choices(), registry), registry) == 2


def test_fighter_with_chain_mail_and_shield_has_ac_18(registry):
    hero = build_character(fighter_choices(fighting_style=None), registry)
    assert armor_class(hero, registry) == 18


def test_fighter_with_defense_style_has_ac_19(registry):
    # ВНИМАНИЕ: в плане написано 18, по SRD 5.2 Defense даёт +1 к КД в доспехе (см. отчёт)
    hero = build_character(fighter_choices(), registry)
    assert armor_class(hero, registry) == 19


def test_fighter_has_background_and_class_skills(registry):
    hero = build_character(fighter_choices(), registry)
    assert set(hero.sheet.skill_proficiencies) == {
        "athletics", "intimidation", "perception", "survival", "stealth",
        "medicine", "religion", "nature",
    }


def test_fighter_gets_origin_feat_from_background(registry):
    hero = build_character(fighter_choices(fighting_style=None), registry)
    assert hero.sheet.feats[0] == "savage_attacker"
    assert "defense" not in hero.sheet.feats


def test_fighter_gets_fighting_style_feat(registry):
    hero = build_character(fighter_choices(), registry)
    assert "defense" in hero.sheet.feats
    assert "savage_attacker" in hero.sheet.feats


def test_fighter_has_three_weapon_masteries(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.sheet.weapon_masteries == ["longsword", "greatsword", "shortsword"]


def test_fighter_gets_tool_from_background(registry):
    hero = build_character(fighter_choices(), registry)
    assert registry.get("background", "soldier").tool in hero.sheet.tool_proficiencies


def test_fighter_inventory_and_equipment_follow_choices(registry):
    hero = build_character(fighter_choices(), registry)
    items = [e.item_id for e in hero.inventory]
    assert {"chain_mail", "longsword", "shield"} <= set(items)
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.shield == "shield"
    assert hero.equipped.main_hand == "longsword"


def test_built_hero_has_given_id_and_active_status(registry):
    hero = build_character(fighter_choices(hero_id="h7", ordinal=3), registry)
    assert hero.id == "h7"
    assert hero.ordinal == 3
    assert hero.status == "active"


def test_human_builds_with_species_choices(registry):
    assert not isinstance(build_character(fighter_choices(), registry), ValidationErrors)


def test_elf_wizard_is_built(registry):
    hero = build_character(wizard_choices(), registry)
    assert hero.sheet.class_id == "wizard"
    assert hero.sheet.abilities["int"] == 17


# ошибки: предыстория

def test_background_bonus_2_2_is_error(registry):
    result = build_character(fighter_choices(background_bonus={"str": 2, "con": 2}), registry)
    assert isinstance(result, ValidationErrors)
    assert "background_bonus_invalid" in result.codes


def test_background_bonus_1_1_1_is_ok(registry):
    choices = fighter_choices(background_bonus={"str": 1, "dex": 1, "con": 1})
    assert not isinstance(build_character(choices, registry), ValidationErrors)


def test_background_bonus_1_1_1_adds_one_to_each(registry):
    choices = fighter_choices(background_bonus={"str": 1, "dex": 1, "con": 1})
    hero = build_character(choices, registry)
    assert (hero.sheet.abilities["str"], hero.sheet.abilities["dex"]) == (16, 14)
    assert hero.sheet.abilities["con"] == 15


def test_background_bonus_on_ability_outside_background_is_error(registry):
    result = build_character(fighter_choices(background_bonus={"int": 2, "con": 1}), registry)
    assert isinstance(result, ValidationErrors)
    assert "background_bonus_invalid" in result.codes


def test_background_bonus_2_only_is_error(registry):
    result = build_character(fighter_choices(background_bonus={"str": 2}), registry)
    assert "background_bonus_invalid" in result.codes


def test_background_bonus_3_1_is_error(registry):
    result = build_character(fighter_choices(background_bonus={"str": 3, "con": 1}), registry)
    assert "background_bonus_invalid" in result.codes


def test_unknown_background_id_is_error(registry):
    result = build_character(fighter_choices(background="pirate"), registry)
    assert isinstance(result, ValidationErrors)
    assert "unknown_background" in result.codes


# ошибки: набор характеристик, навыки, мастерства

def test_standard_array_with_repeated_value_is_error(registry):
    scores = {"str": 15, "dex": 15, "con": 13, "int": 12, "wis": 10, "cha": 8}
    result = build_character(fighter_choices(ability_scores=scores), registry)
    assert isinstance(result, ValidationErrors)
    assert "standard_array_invalid" in result.codes


def test_standard_array_with_foreign_value_is_error(registry):
    scores = {"str": 16, "dex": 14, "con": 13, "int": 12, "wis": 10, "cha": 8}
    result = build_character(fighter_choices(ability_scores=scores), registry)
    assert "standard_array_invalid" in result.codes


def test_standard_array_with_missing_ability_is_error(registry):
    scores = {"str": 15, "dex": 14, "con": 13, "int": 12, "wis": 10}
    result = build_character(fighter_choices(ability_scores=scores), registry)
    assert "standard_array_invalid" in result.codes


def test_point_buy_within_27_points_is_ok(registry):
    scores = {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}
    choices = fighter_choices(ability_method="point_buy", ability_scores=scores)
    assert not isinstance(build_character(choices, registry), ValidationErrors)


def test_point_buy_over_27_points_is_error(registry):
    scores = {"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 8, "cha": 8}
    choices = fighter_choices(ability_method="point_buy", ability_scores=scores)
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "point_buy_invalid" in result.codes


def test_point_buy_score_above_15_is_error(registry):
    scores = {"str": 16, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}
    choices = fighter_choices(ability_method="point_buy", ability_scores=scores)
    assert "point_buy_invalid" in build_character(choices, registry).codes


def test_explicit_scores_are_taken_as_is(registry):
    scores = {"str": 16, "dex": 12, "con": 14, "int": 10, "wis": 10, "cha": 9}
    choices = fighter_choices(ability_method="explicit", ability_scores=scores)
    hero = build_character(choices, registry)
    assert hero.sheet.abilities["str"] == 18
    assert hero.sheet.abilities["wis"] == 10


def test_class_skill_outside_options_is_error(registry):
    result = build_character(fighter_choices(class_skills=["arcana", "survival"]), registry)
    assert isinstance(result, ValidationErrors)
    assert "class_skills_invalid" in result.codes


def test_wrong_number_of_class_skills_is_error(registry):
    result = build_character(fighter_choices(class_skills=["perception"]), registry)
    assert "class_skills_invalid" in result.codes


def test_fighter_with_four_masteries_is_error(registry):
    masteries = ["longsword", "greatsword", "shortsword", "spear"]
    result = build_character(fighter_choices(weapon_masteries=masteries), registry)
    assert isinstance(result, ValidationErrors)
    assert "mastery_count_invalid" in result.codes


def test_fighter_with_two_masteries_is_error(registry):
    result = build_character(
        fighter_choices(weapon_masteries=["longsword", "greatsword"]), registry
    )
    assert "mastery_count_invalid" in result.codes


def test_wizard_with_mastery_is_error(registry):
    result = build_character(wizard_choices(weapon_masteries=["dagger"]), registry)
    assert "mastery_count_invalid" in result.codes


def test_mastery_for_unknown_weapon_is_error(registry):
    masteries = ["longsword", "greatsword", "no_such_weapon"]
    result = build_character(fighter_choices(weapon_masteries=masteries), registry)
    assert "mastery_weapon_invalid" in result.codes


def test_unknown_fighting_style_is_error(registry):
    result = build_character(fighter_choices(fighting_style="no_such_style"), registry)
    assert "fighting_style_invalid" in result.codes


def test_origin_feat_as_fighting_style_is_error(registry):
    result = build_character(fighter_choices(fighting_style="alert"), registry)
    assert "fighting_style_invalid" in result.codes


# ошибки: неизвестный класс/вид

def test_unknown_class_is_error(registry):
    result = build_character(fighter_choices(class_id="bard_of_doom"), registry)
    assert isinstance(result, ValidationErrors)
    assert "unknown_class" in result.codes


def test_unknown_species_is_error(registry):
    result = build_character(fighter_choices(species_id="orc"), registry)
    assert isinstance(result, ValidationErrors)
    assert "unknown_species" in result.codes


def test_several_errors_are_reported_together(registry):
    choices = fighter_choices(species_id="orc", background_bonus={"str": 2, "con": 2})
    result = build_character(choices, registry)
    assert "unknown_species" in result.codes
    assert "background_bonus_invalid" in result.codes


# произвольная (нарративная) предыстория по структуре 5.2

def test_custom_background_is_valid(registry):
    assert validate_background(custom_background(), registry) == []


def test_srd_background_as_spec_is_valid(registry):
    soldier = registry.get("background", "soldier")
    spec = BackgroundSpec(
        name=soldier.name, abilities=soldier.abilities, skills=soldier.skills,
        tool=soldier.tool, feat=soldier.feat,
    )
    assert validate_background(spec, registry) == []


def test_custom_background_with_three_skills_is_error(registry):
    spec = custom_background(skills=["acrobatics", "performance", "stealth"])
    assert "background_skills" in validate_background(spec, registry)


def test_custom_background_with_one_skill_is_error(registry):
    spec = custom_background(skills=["acrobatics"])
    assert "background_skills" in validate_background(spec, registry)


def test_custom_background_with_repeated_skill_is_error(registry):
    spec = custom_background(skills=["acrobatics", "acrobatics"])
    assert "background_skills" in validate_background(spec, registry)


def test_custom_background_with_unknown_skill_is_error(registry):
    spec = custom_background(skills=["acrobatics", "juggling"])
    assert "background_skills" in validate_background(spec, registry)


def test_custom_background_with_two_abilities_is_error(registry):
    spec = custom_background(abilities=["dex", "con"])
    assert "background_abilities" in validate_background(spec, registry)


def test_custom_background_with_four_abilities_is_error(registry):
    spec = custom_background(abilities=["dex", "con", "cha", "wis"])
    assert "background_abilities" in validate_background(spec, registry)


def test_custom_background_with_repeated_ability_is_error(registry):
    spec = custom_background(abilities=["dex", "dex", "cha"])
    assert "background_abilities" in validate_background(spec, registry)


def test_custom_background_with_unknown_ability_is_error(registry):
    spec = custom_background(abilities=["dex", "con", "luck"])
    assert "background_abilities" in validate_background(spec, registry)


def test_custom_background_without_tool_is_error(registry):
    spec = custom_background(tool="")
    assert "background_tool" in validate_background(spec, registry)


def test_custom_background_with_unknown_feat_is_error(registry):
    spec = custom_background(feat="no_such_feat")
    assert "background_feat" in validate_background(spec, registry)


def test_custom_background_with_non_origin_feat_is_error(registry):
    spec = custom_background(feat="defense")
    assert "background_feat" in validate_background(spec, registry)


def test_custom_background_with_all_problems_reports_all_codes(registry):
    spec = custom_background(abilities=["dex"], skills=[], tool="", feat="no_such_feat")
    codes = validate_background(spec, registry)
    assert {
        "background_abilities", "background_skills", "background_tool", "background_feat",
    } <= set(codes)


def test_hero_with_custom_background_is_built(registry):
    choices = fighter_choices(
        background=custom_background(),
        background_bonus={"dex": 2, "cha": 1},
        class_skills=["perception", "survival"],
    )
    hero = build_character(choices, registry)
    assert not isinstance(hero, ValidationErrors)
    assert "alert" in hero.sheet.feats
    assert "acrobatics" in hero.sheet.skill_proficiencies
    assert hero.sheet.background.name == "Бывший цирковой акробат"


def test_hero_with_invalid_custom_background_is_error(registry):
    choices = fighter_choices(background=custom_background(skills=["acrobatics"]))
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "background_skills" in result.codes


def test_custom_background_bonus_must_follow_its_abilities(registry):
    choices = fighter_choices(background=custom_background(), background_bonus={"str": 2, "con": 1})
    result = build_character(choices, registry)
    assert "background_bonus_invalid" in result.codes


@pytest.mark.parametrize("background_id", ["acolyte", "criminal", "sage", "soldier"])
def test_srd_backgrounds_pass_validation_as_specs(registry, background_id):
    b = registry.get("background", background_id)
    spec = BackgroundSpec(
        name=b.name, abilities=b.abilities, skills=b.skills, tool=b.tool, feat=b.feat
    )
    assert validate_background(spec, registry) == []


# вспомогательные наборы для других классов

def rogue_choices(**changes):
    choices = CharacterChoices(
        name="Тень",
        species_id="elf",
        class_id="rogue",
        background="criminal",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 15, "con": 14, "int": 13, "wis": 10, "cha": 12},
        background_bonus={"dex": 2, "con": 1},
        class_skills=["acrobatics", "athletics", "deception", "insight"],
        weapon_masteries=["dagger", "shortsword"],
        expertise=["acrobatics", "athletics"],
    )
    return choices.model_copy(update=changes)


def cleric_choices(**changes):
    choices = CharacterChoices(
        name="Брат Анселм",
        species_id="elf",
        class_id="cleric",
        background="acolyte",
        ability_method="standard_array",
        ability_scores={"str": 8, "dex": 10, "con": 14, "int": 12, "wis": 15, "cha": 13},
        background_bonus={"wis": 2, "cha": 1},
        class_skills=["medicine", "persuasion"],
        weapon_masteries=[],
    )
    return choices.model_copy(update=changes)


# боевой стиль только у класса с умением fighting_style

def test_wizard_with_fighting_style_is_error(registry):
    result = build_character(wizard_choices(fighting_style="defense"), registry)
    assert isinstance(result, ValidationErrors)
    assert "fighting_style_invalid" in result.codes


def test_cleric_with_fighting_style_is_error(registry):
    result = build_character(cleric_choices(fighting_style="defense"), registry)
    assert "fighting_style_invalid" in result.codes


def test_rogue_with_fighting_style_is_error(registry):
    result = build_character(rogue_choices(fighting_style="defense"), registry)
    assert "fighting_style_invalid" in result.codes


def test_wizard_without_fighting_style_is_ok(registry):
    assert not isinstance(build_character(wizard_choices(), registry), ValidationErrors)


def test_fighter_with_fighting_style_is_ok(registry):
    hero = build_character(fighter_choices(fighting_style="defense"), registry)
    assert "defense" in hero.sheet.feats


# мастерство оружия: повторы и владение

def test_repeated_weapon_in_masteries_is_error(registry):
    masteries = ["longsword", "longsword", "greatsword"]
    result = build_character(fighter_choices(weapon_masteries=masteries), registry)
    assert isinstance(result, ValidationErrors)
    assert "mastery_weapon_invalid" in result.codes


def test_rogue_repeated_weapon_in_masteries_is_error(registry):
    result = build_character(rogue_choices(weapon_masteries=["dagger", "dagger"]), registry)
    assert "mastery_weapon_invalid" in result.codes


def test_rogue_mastery_for_weapon_without_training_is_error(registry):
    result = build_character(rogue_choices(weapon_masteries=["dagger", "longsword"]), registry)
    assert isinstance(result, ValidationErrors)
    assert "mastery_weapon_invalid" in result.codes


def test_rogue_mastery_for_martial_weapon_with_finesse_is_ok(registry):
    hero = build_character(rogue_choices(weapon_masteries=["dagger", "shortsword"]), registry)
    assert hero.sheet.weapon_masteries == ["dagger", "shortsword"]


def test_rogue_mastery_for_martial_weapon_with_two_handed_only_is_error(registry):
    result = build_character(rogue_choices(weapon_masteries=["dagger", "greatsword"]), registry)
    assert "mastery_weapon_invalid" in result.codes


def test_fighter_mastery_for_any_weapon_with_mastery_is_ok(registry):
    masteries = ["longsword", "greatsword", "spear"]
    hero = build_character(fighter_choices(weapon_masteries=masteries), registry)
    assert hero.sheet.weapon_masteries == masteries


# навыки класса и предыстории не пересекаются

def test_class_skill_that_background_already_gives_is_error(registry):
    # солдат даёт athletics и intimidation, воин может выбрать athletics
    result = build_character(fighter_choices(class_skills=["athletics", "perception"]), registry)
    assert isinstance(result, ValidationErrors)
    assert "class_skills_invalid" in result.codes


def test_class_skill_overlap_with_custom_background_is_error(registry):
    choices = fighter_choices(
        background=custom_background(),
        background_bonus={"dex": 2, "cha": 1},
        class_skills=["acrobatics", "perception"],
    )
    result = build_character(choices, registry)
    assert "class_skills_invalid" in result.codes


def test_class_skills_without_overlap_are_ok(registry):
    hero = build_character(fighter_choices(class_skills=["history", "perception"]), registry)
    assert not isinstance(hero, ValidationErrors)


# explicit: 3..20 до бонуса, не больше 20 после бонуса

def explicit(**scores):
    base = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10, "cha": 10}
    base.update(scores)
    return fighter_choices(ability_method="explicit", ability_scores=base)


@pytest.mark.parametrize("value", [2, 21, 0, -1, 30])
def test_explicit_score_outside_3_20_is_error(registry, value):
    result = build_character(explicit(wis=value), registry)
    assert isinstance(result, ValidationErrors)
    assert "abilities_invalid" in result.codes


@pytest.mark.parametrize("value", [3, 20])
def test_explicit_score_at_edge_is_ok(registry, value):
    assert not isinstance(build_character(explicit(wis=value), registry), ValidationErrors)


def test_explicit_20_plus_2_bonus_is_error(registry):
    result = build_character(explicit(str=20), registry)
    assert isinstance(result, ValidationErrors)
    assert "abilities_invalid" in result.codes


def test_explicit_20_plus_1_bonus_is_error(registry):
    bonus = {"str": 1, "dex": 1, "con": 1}
    choices = explicit(str=20).model_copy(update={"background_bonus": bonus})
    result = build_character(choices, registry)
    assert "abilities_invalid" in result.codes


def test_explicit_18_plus_2_bonus_is_20_and_ok(registry):
    hero = build_character(explicit(str=18), registry)
    assert hero.sheet.abilities["str"] == 20


def test_explicit_20_without_bonus_on_it_is_ok(registry):
    hero = build_character(explicit(wis=20), registry)
    assert hero.sheet.abilities["wis"] == 20


def test_explicit_with_missing_ability_is_error(registry):
    scores = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 10}
    choices = fighter_choices(ability_method="explicit", ability_scores=scores)
    result = build_character(choices, registry)
    assert "abilities_invalid" in result.codes


# заклинания героя

def test_wizard_spells_are_kept_as_known(registry):
    hero = build_character(wizard_choices(spells=["fire_bolt", "magic_missile"]), registry)
    assert not isinstance(hero, ValidationErrors)
    assert set(hero.sheet.known_of()) == {"fire_bolt", "magic_missile"}


def test_wizard_without_spells_knows_none(registry):
    hero = build_character(wizard_choices(), registry)
    assert hero.sheet.known_of() == []


def test_spell_from_another_class_list_is_error(registry):
    result = build_character(wizard_choices(spells=["cure_wounds"]), registry)
    assert isinstance(result, ValidationErrors)
    assert "spells_invalid" in result.codes


def test_cleric_spell_from_wizard_list_is_error(registry):
    result = build_character(cleric_choices(spells=["magic_missile"]), registry)
    assert "spells_invalid" in result.codes


def test_cleric_own_spells_are_ok(registry):
    hero = build_character(cleric_choices(spells=["bless", "cure_wounds"]), registry)
    assert not isinstance(hero, ValidationErrors)
    assert set(hero.sheet.known_of()) == {"bless", "cure_wounds"}


def test_unknown_spell_is_error(registry):
    result = build_character(wizard_choices(spells=["no_such_spell"]), registry)
    assert "spells_invalid" in result.codes


def test_fighter_with_spells_is_error(registry):
    result = build_character(fighter_choices(spells=["fire_bolt"]), registry)
    assert "spells_invalid" in result.codes


def test_spell_of_too_high_circle_is_error(tmp_path):
    (tmp_path / "spells").mkdir()
    (tmp_path / "spells" / "big_boom.yaml").write_text(
        "id: big_boom\nname: Большой бабах\nlevel: 3\nschool: evocation\n"
        "range_kind: ranged\nrange_ft: 150\nclasses: [wizard]\n",
        encoding="utf-8",
    )
    registry = load_registry([tmp_path])
    result = build_character(wizard_choices(spells=["big_boom"]), registry)
    assert isinstance(result, ValidationErrors)
    assert "spells_invalid" in result.codes


# пулы ресурсов

def test_fighter_gets_second_wind_pool(registry):
    hero = build_character(fighter_choices(), registry)
    pool = hero.creature.resources["second_wind"]
    assert (pool.current, pool.max) == (2, 2)


def test_fighter_has_no_spell_slot_pools(registry):
    hero = build_character(fighter_choices(), registry)
    assert "spell_slot:1" not in hero.creature.resources


def test_wizard_gets_first_circle_slot_pool(registry):
    hero = build_character(wizard_choices(), registry)
    pool = hero.creature.resources["spell_slot:1"]
    assert (pool.current, pool.max) == (2, 2)


def test_wizard_has_no_second_wind_pool(registry):
    hero = build_character(wizard_choices(), registry)
    assert "second_wind" not in hero.creature.resources


def test_cleric_gets_first_circle_slot_pool(registry):
    hero = build_character(cleric_choices(), registry)
    assert hero.creature.resources["spell_slot:1"].max == 2


def test_rogue_gets_only_hit_dice_pool(registry):
    # у плута нет ячеек и second_wind — только кости хитов (max = уровень)
    hero = build_character(rogue_choices(), registry)
    assert set(hero.creature.resources) == {"hit_dice:d8"}
    assert hero.creature.resources["hit_dice:d8"].max == 1


# снаряжение и золото предыстории

def test_hero_gets_background_equipment(registry):
    hero = build_character(fighter_choices(inventory=[], equip=[]), registry)
    for item_id in set(registry.get("background", "soldier").equipment):
        assert count_item(hero, item_id) >= 1


def test_hero_gets_background_gold(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.money_cp == registry.get("background", "soldier").gold_cp


def test_background_equipment_repeated_id_means_quantity(registry):
    equipment = registry.get("background", "soldier").equipment
    hero = build_character(fighter_choices(inventory=[], equip=[]), registry)
    for item_id in set(equipment):
        assert count_item(hero, item_id) == equipment.count(item_id)


def test_choices_inventory_is_added_to_background_equipment(registry):
    hero = build_character(fighter_choices(), registry)
    assert count_item(hero, "chain_mail") == 1
    assert count_item(hero, "longsword") == 1


def test_background_gold_variant_gives_gold_and_no_equipment(registry):
    hero = build_character(
        fighter_choices(background_gear="gold", inventory=[], equip=[]), registry
    )
    assert hero.money_cp == 5000
    assert hero.inventory == []


def test_custom_background_equipment_and_gold_are_given(registry):
    spec = custom_background(equipment=["dagger"], gold_cp=1500)
    choices = fighter_choices(
        background=spec, background_bonus={"dex": 2, "cha": 1}, inventory=[], equip=[]
    )
    hero = build_character(choices, registry)
    assert count_item(hero, "dagger") == 1
    assert hero.money_cp == 1500


# человек: Skillful и Versatile через species_choices

def test_human_skillful_choice_adds_skill(registry):
    hero = build_character(fighter_choices(), registry)
    assert "stealth" in hero.sheet.skill_proficiencies


def test_human_versatile_choice_adds_origin_feat(registry):
    hero = build_character(fighter_choices(), registry)
    assert "skilled" in hero.sheet.feats


def test_human_without_species_choices_is_error(registry):
    result = build_character(fighter_choices(species_choices={}), registry)
    assert isinstance(result, ValidationErrors)
    assert "species_choices_invalid" in result.codes


def test_human_skillful_with_unknown_skill_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "juggling", "feat": "skilled"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_skillful_with_skill_already_owned_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "athletics", "feat": "skilled"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_skillful_with_class_skill_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "perception", "feat": "skilled"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_versatile_with_non_origin_feat_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "stealth", "feat": "defense"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_versatile_with_unknown_feat_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "stealth", "feat": "no_such_feat"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_versatile_with_background_feat_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "stealth", "feat": "savage_attacker"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_human_with_only_skill_choice_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "stealth"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


def test_elf_needs_no_species_choices(registry):
    assert not isinstance(build_character(wizard_choices(), registry), ValidationErrors)


# коды item_unknown и equip_invalid

def test_unknown_item_in_inventory_is_item_unknown(registry):
    result = build_character(fighter_choices(inventory=["no_such_item"], equip=[]), registry)
    assert isinstance(result, ValidationErrors)
    assert "item_unknown" in result.codes


def test_equip_item_not_in_inventory_is_equip_invalid(registry):
    result = build_character(fighter_choices(inventory=[], equip=["dagger"]), registry)
    assert "equip_invalid" in result.codes


def test_equip_potion_is_equip_invalid(registry):
    choices = fighter_choices(inventory=["potion_of_healing"], equip=["potion_of_healing"])
    assert "equip_invalid" in build_character(choices, registry).codes


def test_equip_two_handed_weapon_with_shield_is_equip_invalid(registry):
    choices = fighter_choices(inventory=["greatsword", "shield"], equip=["greatsword", "shield"])
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "equip_invalid" in result.codes


def test_wizard_equip_chain_mail_is_equip_invalid_not_exception(registry):
    choices = wizard_choices(inventory=["chain_mail"], equip=["chain_mail"])
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "equip_invalid" in result.codes


# сообщения об ошибках человекочитаемые

def test_error_messages_do_not_show_raw_codes(registry):
    spec = custom_background(abilities=["dex"], skills=[], tool="", feat="no_such_feat")
    result = build_character(fighter_choices(background=spec), registry)
    assert result.codes
    for code in result.codes:
        for message in result.messages:
            assert code not in message


def test_background_messages_are_not_code_with_prefix(registry):
    spec = custom_background(abilities=["dex"], skills=[], tool="", feat="no_such_feat")
    result = build_character(fighter_choices(background=spec), registry)
    for code in ["background_abilities", "background_skills", "background_tool", "background_feat"]:
        assert f"предыстория: {code}" not in result.messages


def test_every_error_has_one_russian_message(registry):
    choices = fighter_choices(species_id="orc", background_bonus={"str": 2, "con": 2})
    result = build_character(choices, registry)
    assert len(result.messages) == len(result.codes)
    for message in result.messages:
        assert re.search("[а-яё]", message, re.IGNORECASE)


# Одарённый механически: три навыка/инструмента (аудит 1 п. 2.1)

def test_skilled_from_species_adds_three_skills(registry):
    hero = build_character(fighter_choices(), registry)
    assert {"medicine", "religion", "nature"} <= set(hero.sheet.skill_proficiencies)


def test_skilled_skills_are_not_duplicated_in_proficiencies(registry):
    hero = build_character(fighter_choices(), registry)
    skills = hero.sheet.skill_proficiencies
    assert len(skills) == len(set(skills))


def test_skilled_tool_choice_goes_to_tool_proficiencies(registry):
    choices = fighter_choices(
        feat_choices={"skilled": ["thieves_tools", "medicine", "religion"]}
    )
    hero = build_character(choices, registry)
    assert not isinstance(hero, ValidationErrors)
    assert "thieves_tools" in hero.sheet.tool_proficiencies
    assert "thieves_tools" not in hero.sheet.skill_proficiencies
    assert {"medicine", "religion"} <= set(hero.sheet.skill_proficiencies)


def test_skilled_non_tool_item_is_error(registry):
    # лом и зелье — не инструменты (Item.tool == False)
    for pick in ("crowbar", "potion_of_healing"):
        choices = fighter_choices(feat_choices={"skilled": [pick, "medicine", "religion"]})
        result = build_character(choices, registry)
        assert isinstance(result, ValidationErrors)
        assert "feat_choices_invalid" in result.codes


def test_skilled_without_feat_choices_is_error(registry):
    result = build_character(fighter_choices(feat_choices={}), registry)
    assert isinstance(result, ValidationErrors)
    assert "feat_choices_invalid" in result.codes


@pytest.mark.parametrize(
    "picks", [["medicine", "religion"], ["medicine", "religion", "nature", "arcana"], []]
)
def test_skilled_with_wrong_number_of_choices_is_error(registry, picks):
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_skilled_skill_already_from_background_is_error(registry):
    picks = ["athletics", "religion", "nature"]
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_skilled_skill_already_from_class_is_error(registry):
    picks = ["perception", "religion", "nature"]
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_skilled_skill_already_from_humans_skillful_is_error(registry):
    picks = ["stealth", "religion", "nature"]
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_skilled_repeated_skill_inside_one_choice_is_error(registry):
    picks = ["medicine", "medicine", "nature"]
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_skilled_unknown_skill_or_tool_is_error(registry):
    picks = ["juggling", "religion", "nature"]
    result = build_character(fighter_choices(feat_choices={"skilled": picks}), registry)
    assert "feat_choices_invalid" in result.codes


def test_feat_choices_for_feat_without_choice_is_error(registry):
    choices = fighter_choices(
        feat_choices={"skilled": ["medicine", "religion", "nature"], "savage_attacker": ["arcana"]}
    )
    assert "feat_choices_invalid" in build_character(choices, registry).codes


def test_feat_choices_for_absent_feat_is_error(registry):
    choices = wizard_choices(feat_choices={"skilled": ["history", "religion", "nature"]})
    assert "feat_choices_invalid" in build_character(choices, registry).codes


def test_feat_choices_error_does_not_raise(registry):
    result = build_character(fighter_choices(feat_choices={"skilled": ["x"]}), registry)
    assert isinstance(result, ValidationErrors)
    assert len(result.codes) == len(result.messages)


def skilled_twice_choices(**changes):
    # предыстория со своей чертой skilled + Универсальность -> тоже skilled: два отдельных выбора
    choices = fighter_choices(
        background=custom_background(feat="skilled"),
        background_bonus={"dex": 2, "cha": 1},
        feat_choices={
            "skilled": ["medicine", "religion", "nature"],
            "skilled#2": ["history", "arcana", "sleight_of_hand"],
        },
    )
    return choices.model_copy(update=changes)


def test_skilled_twice_with_separate_choices_gives_six_skills(registry):
    hero = build_character(skilled_twice_choices(), registry)
    assert not isinstance(hero, ValidationErrors)
    assert {
        "medicine", "religion", "nature", "history", "arcana", "sleight_of_hand",
    } <= set(hero.sheet.skill_proficiencies)


def test_skilled_twice_gives_feat_twice(registry):
    hero = build_character(skilled_twice_choices(), registry)
    assert hero.sheet.feats.count("skilled") == 2


def test_skilled_twice_without_second_choice_is_error(registry):
    choices = skilled_twice_choices(
        feat_choices={"skilled": ["medicine", "religion", "nature"]}
    )
    assert "feat_choices_invalid" in build_character(choices, registry).codes


def test_skilled_twice_with_same_skill_in_both_choices_is_error(registry):
    choices = skilled_twice_choices(
        feat_choices={
            "skilled": ["medicine", "religion", "nature"],
            "skilled#2": ["medicine", "arcana", "history"],
        }
    )
    assert "feat_choices_invalid" in build_character(choices, registry).codes


def test_skilled_twice_does_not_make_species_choice_invalid(registry):
    # P5: skilled повторяемая черта -- Универсальность поверх предыстории разрешена
    result = build_character(skilled_twice_choices(), registry)
    assert not isinstance(result, ValidationErrors)


# повтор черты через Универсальность (P5)

def human_wizard_choices(feat, **changes):
    choices = wizard_choices(
        species_id="human",
        species_choices={"skill": "insight", "feat": feat},
    )
    return choices.model_copy(update=changes)


def test_versatile_magic_initiate_over_sage_is_allowed(registry):
    # мудрец получает magic_initiate от предыстории, Универсальность повторяет его (Repeatable)
    hero = build_character(human_wizard_choices("magic_initiate"), registry)
    assert not isinstance(hero, ValidationErrors)
    assert hero.sheet.feats.count("magic_initiate") == 2


def test_versatile_alert_over_criminal_is_error(registry):
    choices = rogue_choices(
        species_id="human",
        species_choices={"skill": "history", "feat": "alert"},
    )
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "species_choices_invalid" in result.codes


def test_versatile_non_repeatable_other_feat_is_still_ok(registry):
    hero = build_character(human_wizard_choices("alert"), registry)
    assert not isinstance(hero, ValidationErrors)
    assert "alert" in hero.sheet.feats


def test_versatile_savage_attacker_over_soldier_is_error(registry):
    choices = fighter_choices(species_choices={"skill": "stealth", "feat": "savage_attacker"})
    assert "species_choices_invalid" in build_character(choices, registry).codes


# бюджет 50 зм свободной предыстории (P3)

@pytest.mark.parametrize("background_id", ["acolyte", "criminal", "sage", "soldier"])
def test_srd_background_with_equipment_and_gold_passes_budget(registry, background_id):
    spec = background_from_registry(background_id, registry)
    assert validate_background(spec, registry) == []


def test_background_gold_exactly_50_gp_is_ok(registry):
    assert validate_background(custom_background(gold_cp=5000), registry) == []


def test_background_gold_51_gp_is_budget_error(registry):
    codes = validate_background(custom_background(gold_cp=5100), registry)
    assert "background_budget_invalid" in codes


def test_background_equipment_alone_over_budget_is_error(registry):
    # кольчуга стоит 75 зм
    codes = validate_background(custom_background(equipment=["chain_mail"]), registry)
    assert "background_budget_invalid" in codes


def test_background_items_plus_gold_are_summed(registry):
    # кинжал 2 зм: 2 + 48 = 50 -- можно, 2 + 49 -- нельзя
    ok = custom_background(equipment=["dagger"], gold_cp=4800)
    over = custom_background(equipment=["dagger"], gold_cp=4900)
    assert validate_background(ok, registry) == []
    assert "background_budget_invalid" in validate_background(over, registry)


def test_background_repeated_item_costs_per_unit(registry):
    over = custom_background(equipment=["dagger"] * 3, gold_cp=4500)
    assert "background_budget_invalid" in validate_background(over, registry)


def test_build_with_over_budget_background_reports_budget_code(registry):
    choices = fighter_choices(
        background=custom_background(gold_cp=5100), background_bonus={"dex": 2, "cha": 1},
    )
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "background_budget_invalid" in result.codes


def test_build_with_budget_background_exactly_50_gp_is_ok(registry):
    choices = fighter_choices(
        background=custom_background(gold_cp=5000), background_bonus={"dex": 2, "cha": 1},
    )
    assert not isinstance(build_character(choices, registry), ValidationErrors)


def test_gold_variant_gives_gold_option_of_background(registry):
    hero = build_character(
        fighter_choices(background_gear="gold", inventory=[], equip=[]), registry
    )
    assert hero.money_cp == registry.get("background", "soldier").gold_option_cp


# явный выбор подготовленных заклинаний (P4)

def extra_spells_registry(tmp_path):
    (tmp_path / "spells").mkdir()
    for number in range(1, 5):
        (tmp_path / "spells" / f"wiz_spell_{number}.yaml").write_text(
            f"id: wiz_spell_{number}\nname: Заклинание {number}\nlevel: 1\nschool: evocation\n"
            "range_kind: ranged\nrange_ft: 60\nclasses: [wizard]\n",
            encoding="utf-8",
        )
    return load_registry([tmp_path])


def test_prepared_is_taken_as_chosen(registry):
    choices = wizard_choices(spells=["magic_missile", "burning_hands"], prepared=["burning_hands"])
    hero = build_character(choices, registry)
    assert not isinstance(hero, ValidationErrors)
    assert hero.sheet.prepared_of() == ["burning_hands"]


def test_prepared_both_chosen_spells_are_kept(registry):
    choices = wizard_choices(
        spells=["magic_missile", "burning_hands"], prepared=["magic_missile", "burning_hands"]
    )
    hero = build_character(choices, registry)
    assert set(hero.sheet.prepared_of()) == {"magic_missile", "burning_hands"}


def test_without_prepared_nothing_is_prepared_automatically(registry):
    # раньше брались «первые N» -- теперь только явный выбор игрока
    hero = build_character(wizard_choices(spells=["magic_missile", "burning_hands"]), registry)
    assert not isinstance(hero, ValidationErrors)
    assert hero.sheet.prepared_of() == []


def test_prepared_outside_chosen_spells_is_error(registry):
    choices = wizard_choices(spells=["magic_missile"], prepared=["burning_hands"])
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "spells_invalid" in result.codes


def test_prepared_without_any_spells_chosen_is_error(registry):
    result = build_character(wizard_choices(prepared=["magic_missile"]), registry)
    assert "spells_invalid" in result.codes


def test_prepared_cantrip_is_error(registry):
    choices = wizard_choices(spells=["fire_bolt", "magic_missile"], prepared=["fire_bolt"])
    assert "spells_invalid" in build_character(choices, registry).codes


def test_prepared_repeated_spell_is_error(registry):
    choices = wizard_choices(
        spells=["magic_missile", "burning_hands"], prepared=["magic_missile", "magic_missile"]
    )
    assert "spells_invalid" in build_character(choices, registry).codes


def test_prepared_over_class_limit_is_error(tmp_path):
    # у волшебника prepared == 4: пять подготовленных из шести известных -- ошибка
    custom = extra_spells_registry(tmp_path)
    five = ["magic_missile", "wiz_spell_1", "wiz_spell_2", "wiz_spell_3", "wiz_spell_4"]
    result = build_character(wizard_choices(spells=five, prepared=five), custom)
    assert isinstance(result, ValidationErrors)
    assert "spells_invalid" in result.codes


def test_prepared_exactly_at_class_limit_is_ok(tmp_path):
    custom = extra_spells_registry(tmp_path)
    five = ["magic_missile", "wiz_spell_1", "wiz_spell_2", "wiz_spell_3", "wiz_spell_4"]
    hero = build_character(wizard_choices(spells=five, prepared=five[:4]), custom)
    assert not isinstance(hero, ValidationErrors)
    assert hero.sheet.prepared_of() == five[:4]


def test_prepared_is_not_cut_to_first_n_of_known(tmp_path):
    # выбрано последнее из известных: «первые N» дали бы другой список
    custom = extra_spells_registry(tmp_path)
    known = ["magic_missile", "wiz_spell_1", "wiz_spell_2", "wiz_spell_3", "wiz_spell_4"]
    hero = build_character(wizard_choices(spells=known, prepared=["wiz_spell_4"]), custom)
    assert hero.sheet.prepared_of() == ["wiz_spell_4"]


def test_prepared_for_non_caster_is_error(registry):
    assert "spells_invalid" in build_character(fighter_choices(prepared=["bless"]), registry).codes


def test_cleric_prepared_subset_is_ok(registry):
    choices = cleric_choices(spells=["bless", "cure_wounds"], prepared=["cure_wounds"])
    hero = build_character(choices, registry)
    assert hero.sheet.prepared_of() == ["cure_wounds"]


# константы SRD берутся из реестра, а не из кода (аудит 1 п. 2.10)

def registry_with_table(registry, table):
    items = {}
    for kind in ("class", "species", "background", "feat", "weapon", "armor", "item", "spell",
                 "feature", "table", "mastery", "condition", "monster", "subclass"):
        try:
            items[kind] = {i: registry.get(kind, i) for i in registry.ids(kind)}
        except KeyError:
            continue
    items["table"][table.id] = table
    return ContentRegistry(items)


def test_standard_array_is_read_from_registry_table(registry):
    table = registry.get("table", "standard_array").model_copy(
        update={"rows": {"1": 16, "2": 14, "3": 13, "4": 12, "5": 10, "6": 8}}
    )
    custom = registry_with_table(registry, table)
    srd = {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    result = build_character(fighter_choices(ability_scores=srd), custom)
    assert "standard_array_invalid" in result.codes


def test_point_buy_budget_is_read_from_registry_table(registry):
    rows = dict(registry.get("table", "point_buy").rows)
    rows["budget"] = 10
    table = registry.get("table", "point_buy").model_copy(update={"rows": rows})
    custom = registry_with_table(registry, table)
    scores = {"str": 15, "dex": 15, "con": 15, "int": 8, "wis": 8, "cha": 8}
    choices = fighter_choices(ability_method="point_buy", ability_scores=scores)
    assert "point_buy_invalid" in build_character(choices, custom).codes


def test_point_buy_cost_is_read_from_registry_table(registry):
    rows = dict(registry.get("table", "point_buy").rows)
    rows["15"] = 1
    table = registry.get("table", "point_buy").model_copy(update={"rows": rows})
    custom = registry_with_table(registry, table)
    scores = {"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 15, "cha": 15}
    choices = fighter_choices(ability_method="point_buy", ability_scores=scores)
    assert not isinstance(build_character(choices, custom), ValidationErrors)


# explicit при создании на лету (P8)

def test_explicit_scores_work_with_custom_background(registry):
    scores = {"str": 12, "dex": 16, "con": 14, "int": 10, "wis": 10, "cha": 11}
    choices = fighter_choices(
        background=custom_background(),
        background_bonus={"dex": 2, "cha": 1},
        ability_method="explicit",
        ability_scores=scores,
    )
    hero = build_character(choices, registry)
    assert not isinstance(hero, ValidationErrors)
    assert hero.sheet.abilities["dex"] == 18
    assert hero.sheet.abilities["cha"] == 12


def test_explicit_20_with_bonus_and_custom_background_is_error(registry):
    scores = {"str": 12, "dex": 20, "con": 14, "int": 10, "wis": 10, "cha": 11}
    choices = fighter_choices(
        background=custom_background(),
        background_bonus={"dex": 2, "cha": 1},
        ability_method="explicit",
        ability_scores=scores,
    )
    assert "abilities_invalid" in build_character(choices, registry).codes


def test_explicit_below_3_with_custom_background_is_error(registry):
    scores = {"str": 2, "dex": 16, "con": 14, "int": 10, "wis": 10, "cha": 11}
    choices = fighter_choices(
        background=custom_background(),
        background_bonus={"dex": 2, "cha": 1},
        ability_method="explicit",
        ability_scores=scores,
    )
    assert "abilities_invalid" in build_character(choices, registry).codes


# Б1а (B1-PLAN A1, A5): стартовый набор класса -- CharacterChoices.class_kit

def kit_choices(kit, **changes):
    changes = {"inventory": [], "equip": [], **changes}
    return fighter_choices(class_kit=kit, **changes)


def kit_delta(registry, kit, item_id):
    # сколько предметов добавил набор поверх героя без набора (снаряжение предыстории общее)
    with_kit = build_character(kit_choices(kit), registry)
    without = build_character(kit_choices(None), registry)
    return count_item(with_kit, item_id) - count_item(without, item_id)


def test_class_kit_defaults_to_none():
    assert fighter_choices().class_kit is None


def test_class_kit_a_puts_kit_items_into_inventory(registry):
    assert kit_delta(registry, "a", "chain_mail") == 1
    assert kit_delta(registry, "a", "greatsword") == 1
    assert kit_delta(registry, "a", "flail") == 1
    assert kit_delta(registry, "a", "javelin") == 8
    assert kit_delta(registry, "a", "explorers_pack") == 1


def test_class_kit_repeat_means_quantity(registry):
    rogue_kit = registry.get("class", "rogue").starting_kits[0]
    assert rogue_kit.items.count("dagger") == 2


def test_class_kit_a_equips_what_kit_says(registry):
    hero = build_character(kit_choices("a"), registry)
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.main_hand == "greatsword"
    assert hero.equipped.shield is None


def test_class_kit_adds_gold_to_background_gold(registry):
    hero = build_character(kit_choices("a"), registry)
    assert hero.money_cp == registry.get("background", "soldier").gold_cp + 400


def test_class_kit_gold_only_has_no_kit_items_but_gold(registry):
    hero = build_character(kit_choices("c"), registry)
    assert count_item(hero, "chain_mail") == 0
    assert count_item(hero, "greatsword") == 0
    assert kit_delta(registry, "c", "spear") == 0
    assert hero.money_cp == registry.get("background", "soldier").gold_cp + 15500


def test_class_kit_gold_variant_of_background_adds_kit_gold(registry):
    choices = kit_choices("a", background_gear="gold")
    hero = build_character(choices, registry)
    assert hero.money_cp == registry.get("background", "soldier").gold_option_cp + 400


def test_class_kit_is_added_to_explicit_inventory(registry):
    hero = build_character(kit_choices("a", inventory=["shield"]), registry)
    assert count_item(hero, "shield") == 1
    assert kit_delta(registry, "a", "chain_mail") == 1
    assert hero.equipped.armor == "chain_mail"
    assert hero.equipped.shield is None


def test_class_kit_b_of_fighter_has_a_longbow_and_arrows(registry):
    hero = build_character(kit_choices("b"), registry)
    assert count_item(hero, "longbow") == 1
    assert count_item(hero, "arrows") >= 1
    assert hero.equipped.armor == "studded_leather"
    assert hero.money_cp == registry.get("background", "soldier").gold_cp + 1100


def test_unknown_class_kit_is_class_kit_unknown_with_list(registry):
    result = build_character(kit_choices("z"), registry)
    assert isinstance(result, ValidationErrors)
    assert result.codes == ["class_kit_unknown"]
    assert result.messages == ["неизвестный набор класса: z; доступны: a, b, c"]


def test_wizard_has_only_kits_a_and_b(registry):
    assert [k.id for k in registry.get("class", "wizard").starting_kits] == ["a", "b"]
    bad = build_character(wizard_choices(class_kit="c"), registry)
    assert bad.codes == ["class_kit_unknown"]
    assert bad.messages == ["неизвестный набор класса: c; доступны: a, b"]


def test_wizard_kit_a_equips_quarterstaff(registry):
    hero = build_character(wizard_choices(class_kit="a"), registry)
    assert hero.equipped.main_hand == "quarterstaff"
    assert count_item(hero, "dagger") == 2


def test_class_kit_none_keeps_inventory_as_before(registry):
    hero = build_character(fighter_choices(), registry)
    assert count_item(hero, "greatsword") == 0
    assert hero.equipped.shield == "shield"
    assert hero.money_cp == registry.get("background", "soldier").gold_cp


def test_class_kit_error_is_reported_with_other_errors(registry):
    result = build_character(kit_choices("z", class_skills=["perception"]), registry)
    assert "class_kit_unknown" in result.codes
    assert "class_skills_invalid" in result.codes


def test_class_kit_wizard_quantity_of_daggers(registry):
    with_kit = build_character(wizard_choices(class_kit="a"), registry)
    without = build_character(wizard_choices(), registry)
    assert count_item(with_kit, "dagger") - count_item(without, "dagger") == 2


# Б2а (A3): тексты валидатора доступны по частям; build_character берёт их оттуда

def point_buy_scores(**changes):
    scores = {"str": 8, "dex": 8, "con": 8, "int": 8, "wis": 8, "cha": 8}
    scores.update(changes)
    return scores


def test_build_character_point_buy_text_equals_ability_message(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    scores = {"str": 15, "dex": 15, "con": 15, "int": 15, "wis": 8, "cha": 8}
    result = build_character(
        fighter_choices(ability_method="point_buy", ability_scores=scores), registry
    )
    assert result.messages == [ABILITY_MESSAGES["point_buy_invalid"]]


def test_build_character_standard_array_text_equals_ability_message(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    scores = {"str": 16, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    result = build_character(fighter_choices(ability_scores=scores), registry)
    assert result.messages == [ABILITY_MESSAGES["standard_array_invalid"]]


def test_build_character_explicit_text_equals_ability_message(registry):
    from ai_dm.rules.builder import ABILITY_MESSAGES

    scores = {"str": 21, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    result = build_character(
        fighter_choices(ability_method="explicit", ability_scores=scores), registry
    )
    assert result.messages == [ABILITY_MESSAGES["abilities_invalid"]]


def test_build_character_over_twenty_text_equals_over_twenty_message(registry):
    from ai_dm.rules.builder import over_twenty_message

    scores = {"str": 19, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}
    result = build_character(
        fighter_choices(ability_method="explicit", ability_scores=scores), registry
    )
    assert result.codes == ["abilities_invalid"]
    assert result.messages == [over_twenty_message("str")]


def test_build_character_bonus_text_equals_bonus_message(registry):
    from ai_dm.rules.builder import BONUS_MESSAGE

    result = build_character(fighter_choices(background_bonus={"str": 2, "dex": 2}), registry)
    assert result.messages == [BONUS_MESSAGE]


def test_ability_messages_keep_the_b1_texts():
    from ai_dm.rules.builder import ABILITY_MESSAGES, BONUS_MESSAGE, over_twenty_message

    assert ABILITY_MESSAGES == {
        "point_buy_invalid": "покупка очков: неверные значения или больше 27 очков",
        "standard_array_invalid": "стандартный набор: нужны 15,14,13,12,10,8 по разу",
        "abilities_invalid": "нужны все шесть характеристик со значениями от 3 до 20",
    }
    assert BONUS_MESSAGE == "бонус предыстории: +2/+1 или +1/+1/+1"
    assert over_twenty_message("dex") == "характеристика выше 20 после бонуса: dex"


def test_point_buy_cost_of_all_eights_is_zero(registry):
    from ai_dm.rules.builder import point_buy_cost

    assert point_buy_cost(point_buy_scores(), registry) == 0


def test_point_buy_cost_of_all_fifteens_is_54(registry):
    from ai_dm.rules.builder import point_buy_cost

    assert point_buy_cost({k: 15 for k in point_buy_scores()}, registry) == 54


def test_point_buy_cost_sums_table_values(registry):
    from ai_dm.rules.builder import point_buy_cost

    assert point_buy_cost(point_buy_scores(str=15, dex=14, con=13), registry) == 9 + 7 + 5


def test_point_buy_cost_of_value_outside_table_is_none(registry):
    from ai_dm.rules.builder import point_buy_cost

    assert point_buy_cost(point_buy_scores(str=16), registry) is None
    assert point_buy_cost(point_buy_scores(str=7), registry) is None


def test_point_buy_cost_of_partial_scores_counts_given_ones(registry):
    from ai_dm.rules.builder import point_buy_cost

    assert point_buy_cost({"str": 15}, registry) == 9


def kit_base_sheet(**changes):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))
    from hero_kit import base_sheet

    return base_sheet(**changes)


def name_sheet(name):
    sheet = kit_base_sheet()
    return sheet.model_copy(
        update={"choices": sheet.choices.model_copy(update={"name": name})}
    )


@pytest.mark.parametrize("name", ["", "   ", "Гракх", "ГРАКХ", "Борин"])
def test_name_problems_equal_sheet_name_problems(name):
    from ai_dm.rules.builder import name_problems, sheet_name_problems

    taken = ["Гракх", "Гарт"]
    assert name_problems(name, taken) == sheet_name_problems(name_sheet(name), taken)


def test_name_problems_codes_and_texts():
    from ai_dm.rules.builder import name_problems

    assert name_problems("", []) == [("hero_name_empty", "имя героя не может быть пустым")]
    assert name_problems("Гарт", ["гарт"]) == [
        ("hero_name_taken", "имя 'Гарт' уже занято (NPC, бог, фракция или герой)")
    ]
    assert name_problems("Борин", ["Гарт"]) == []


def hooks_sheet(motive, means):
    return kit_base_sheet(motive=motive, means=means, opportunity=[])


@pytest.mark.parametrize(
    ("motive", "means"),
    [
        ("Найти сестру.", ["острый ум"]),
        ("", ["острый ум"]),
        ("   ", ["острый ум"]),
        ("м" * 200, ["острый ум"]),
        ("м" * 201, ["острый ум"]),
        ("Найти сестру.", []),
        ("Найти сестру.", ["а", "б", "в"]),
        ("Найти сестру.", ["а", "б", "в", "г"]),
        ("Найти сестру.", ["с" * 120]),
        ("Найти сестру.", ["с" * 121]),
        ("", []),
    ],
)
def test_hooks_problems_equal_sheet_hooks_problems(registry, motive, means):
    from ai_dm.rules.builder import hooks_problems, sheet_hooks_problems

    sheet = hooks_sheet(motive, means)
    assert hooks_problems(motive, means) == sheet_hooks_problems(sheet, None, registry)


def test_hooks_problems_codes():
    from ai_dm.rules.builder import hooks_problems

    assert [c for c, _ in hooks_problems("", ["а"])] == ["motive_empty"]
    assert [c for c, _ in hooks_problems("м" * 201, ["а"])] == ["motive_too_long"]
    assert [c for c, _ in hooks_problems("м", [])] == ["means_count"]
    assert [c for c, _ in hooks_problems("м", ["а"] * 4)] == ["means_count"]
    assert [c for c, _ in hooks_problems("м", ["с" * 121])] == ["means_too_long"]
    assert hooks_problems("м" * 200, ["с" * 120]) == []


# К0а: схема v9 -- классы списком, история уровней, заклинания по классу

def test_built_hero_has_one_class_entry_at_level_one(registry):
    hero = build_character(fighter_choices(), registry)
    assert [(c.class_id, c.level, c.subclass_id) for c in hero.sheet.classes] == [
        ("fighter", 1, None)
    ]


def test_built_hero_has_level_history_of_its_class(registry):
    assert build_character(wizard_choices(), registry).sheet.level_history == ["wizard"]


def test_built_wizard_known_spells_are_under_the_class_key(registry):
    hero = build_character(wizard_choices(spells=["fire_bolt", "magic_missile"]), registry)
    assert hero.sheet.spells_known == {"wizard": ["fire_bolt", "magic_missile"]}


def test_built_wizard_prepared_spells_are_under_the_class_key(registry):
    hero = build_character(
        wizard_choices(spells=["fire_bolt", "magic_missile"], prepared=["magic_missile"]), registry,
    )
    assert hero.sheet.spells_prepared == {"wizard": ["magic_missile"]}


def test_built_fighter_has_empty_class_spell_lists(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.sheet.spells_known == {"fighter": []}
    assert hero.sheet.spells_prepared == {"fighter": []}


def test_built_hero_has_no_feature_choices_always_prepared_or_pending_level(registry):
    hero = build_character(fighter_choices(), registry)
    assert hero.sheet.feature_choices == {}
    assert hero.sheet.spells_always_prepared == []
    assert (hero.pending_level, hero.companions, hero.attuned) == (None, [], [])


def test_built_hero_hit_dice_pool_is_by_class_die(registry):
    resources = build_character(wizard_choices(), registry).creature.resources
    assert resources["hit_dice:d6"].max == 1
    assert "hit_dice" not in resources


def test_prepared_list_of_the_hero_is_a_copy_of_the_choices(registry):
    choices = wizard_choices(spells=["fire_bolt", "magic_missile"], prepared=["magic_missile"])
    hero = build_character(choices, registry)
    hero.sheet.prepared_of().append("burning_hands")
    assert choices.prepared == ["magic_missile"]


def test_empty_species_skill_is_not_a_proficiency_for_expertise(registry):
    # пустой навык вида не засчитывается как владение: экспертиза «на пустое» отвергается
    choices = rogue_choices(
        species_id="human",
        species_choices={"skill": "", "feat": "skilled"},
        expertise=["acrobatics", ""],
    )
    result = build_character(choices, registry)
    assert isinstance(result, ValidationErrors)
    assert "expertise_invalid" in result.codes
