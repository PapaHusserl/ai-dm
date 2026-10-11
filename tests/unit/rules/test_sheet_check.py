# Б1а (B1-PLAN A1): sheet_check -- единый валидатор листа героя (путь модели и ручная правка).
#   sheet_check(sheet, registry, *, known=None, taken_names=()) -> (codes, messages)
#   порядок групп: build_character, лишнее из background_check, имя, крючки (мотив/средства/
#   возможности).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import base_sheet, known, narrative_trigger  # noqa: E402

from ai_dm.rules.builder import (  # noqa: E402
    SKILL_CONFLICT_MESSAGE,
    ValidationErrors,
    build_character,
    sheet_check,
)
from ai_dm.rules.uniqueness import norm  # noqa: E402
from ai_dm.state.triggers import Trigger  # noqa: E402

SCORES = {"str": 15, "dex": 13, "con": 14, "int": 8, "wis": 10, "cha": 12}


def with_choices(**changes):
    sheet = base_sheet()
    return sheet.model_copy(update={"choices": sheet.choices.model_copy(update=changes)})


def with_background(**changes):
    sheet = base_sheet()
    spec = sheet.choices.background.model_copy(update=changes)
    return with_choices(background=spec)


def trigger(trigger_id, condition, then="отомстить"):
    return Trigger.model_validate({"id": trigger_id, "if": condition, "then": then, "once": True})


def check(sheet, registry, **kw):
    return sheet_check(sheet, registry, **kw)


def test_valid_sheet_has_no_problems(registry):
    assert check(base_sheet(), registry) == ([], [])


def test_valid_sheet_builds_a_hero(registry):
    assert not isinstance(build_character(base_sheet().choices, registry), ValidationErrors)


# группа 1: build_character, тексты как есть

def test_bad_standard_array_gives_code_and_build_character_text(registry):
    sheet = with_choices(ability_scores={**SCORES, "str": 16})
    codes, messages = check(sheet, registry)
    built = build_character(sheet.choices, registry)
    assert codes == ["standard_array_invalid"]
    assert messages == built.messages


def test_point_buy_over_27_is_point_buy_invalid(registry):
    scores = {a: 15 for a in SCORES}
    sheet = with_choices(ability_method="point_buy", ability_scores=scores)
    codes, messages = check(sheet, registry)
    assert codes == ["point_buy_invalid"]
    assert "27" in messages[0]


def test_explicit_21_is_abilities_invalid(registry):
    sheet = with_choices(ability_method="explicit", ability_scores={**SCORES, "str": 21})
    codes, _ = check(sheet, registry)
    assert codes == ["abilities_invalid"]


def test_bonus_outside_background_abilities_is_invalid(registry):
    sheet = with_choices(background_bonus={"str": 2, "con": 1})
    codes, _ = check(sheet, registry)
    assert codes == ["background_bonus_invalid"]


def test_skill_conflict_is_reported_once_with_known_text(registry):
    sheet = with_choices(class_skills=["acrobatics", "survival"])
    codes, messages = check(sheet, registry)
    assert codes.count("class_skills_invalid") == 1
    assert messages.count(SKILL_CONFLICT_MESSAGE) == 1


def test_unknown_class_kit_lists_available_kits(registry):
    codes, messages = check(with_choices(class_kit="z"), registry)
    assert codes == ["class_kit_unknown"]
    assert "z" in messages[0]
    assert "a, b, c" in messages[0]


# группа 2: лишнее из background_check

def test_unknown_tool_comes_from_background_check(registry):
    codes, messages = check(with_background(tool="no_such_tool"), registry)
    assert codes == ["background_tool_unknown"]
    assert "no_such_tool" in messages[0]


def test_long_description_comes_from_background_check(registry):
    codes, messages = check(with_background(description="а" * 301), registry)
    assert codes == ["description_too_long"]
    assert "300" in messages[0]


def test_negative_gold_comes_from_background_check(registry):
    codes, _ = check(with_background(equipment=[], gold_cp=-1), registry)
    assert codes == ["background_gold_negative"]


def test_item_unknown_is_not_duplicated(registry):
    codes, messages = check(with_background(equipment=["no_such_item"]), registry)
    assert codes == ["item_unknown"]
    assert len(messages) == 1


def test_background_budget_is_reported_once(registry):
    codes, _ = check(with_background(equipment=[], gold_cp=6000), registry)
    assert codes == ["background_budget_invalid"]


# группа 3: имя

def test_empty_name_is_hero_name_empty(registry):
    codes, _ = check(with_choices(name=""), registry)
    assert codes == ["hero_name_empty"]


def test_blank_name_is_hero_name_empty(registry):
    codes, _ = check(with_choices(name="   "), registry)
    assert codes == ["hero_name_empty"]


def test_taken_name_is_hero_name_taken_with_check_hero_text(registry):
    codes, messages = check(base_sheet(), registry, taken_names=["Борин"])
    assert codes == ["hero_name_taken"]
    assert messages == ["имя 'Борин' уже занято (NPC, бог, фракция или герой)"]


def test_taken_name_ignores_case_and_edge_spaces(registry):
    sheet = with_choices(name="  борин ")
    codes, _ = check(sheet, registry, taken_names=["БОРИН"])
    assert codes == ["hero_name_taken"]
    assert norm("  борин ") == norm("БОРИН")


def test_other_name_is_not_taken(registry):
    assert check(base_sheet(), registry, taken_names=["Гарт", "Гракх"]) == ([], [])


def test_taken_names_default_is_empty(registry):
    assert check(base_sheet(), registry)[0] == []


# группа 4: motive / means / opportunity

def test_empty_motive_is_motive_empty(registry):
    codes, _ = check(base_sheet(motive=""), registry)
    assert codes == ["motive_empty"]


def test_zero_means_is_means_count_with_npc_create_text(registry):
    codes, messages = check(base_sheet(means=[]), registry)
    assert codes == ["means_count"]
    assert "от одного до трёх средств" in messages[0]


def test_motive_over_200_chars_is_motive_too_long(registry):
    assert check(base_sheet(motive="а" * 200), registry) == ([], [])
    codes, _ = check(base_sheet(motive="а" * 201), registry)
    assert codes == ["motive_too_long"]


def test_means_item_over_120_chars_is_means_too_long(registry):
    assert check(base_sheet(means=["а" * 120]), registry) == ([], [])
    codes, _ = check(base_sheet(means=["а" * 121]), registry)
    assert codes == ["means_too_long"]


def test_then_over_200_chars_is_opportunity_then(registry):
    assert check(base_sheet(opportunity=[narrative_trigger(then="а" * 200)]), registry)[0] == []
    codes, _ = check(base_sheet(opportunity=[narrative_trigger(then="а" * 201)]), registry)
    assert codes == ["opportunity_then"]


def test_blank_motive_is_motive_empty(registry):
    codes, _ = check(base_sheet(motive="   "), registry)
    assert codes == ["motive_empty"]


def test_four_means_is_means_count(registry):
    codes, _ = check(base_sheet(means=["а", "б", "в", "г"]), registry)
    assert codes == ["means_count"]


def test_three_means_are_fine(registry):
    assert check(base_sheet(means=["а", "б", "в"]), registry) == ([], [])


def test_no_opportunity_is_fine(registry):
    assert check(base_sheet(opportunity=[]), registry) == ([], [])


def test_two_opportunities_are_fine(registry):
    opportunity = [narrative_trigger("o1"), narrative_trigger("o2")]
    assert check(base_sheet(opportunity=opportunity), registry) == ([], [])


def test_three_opportunities_are_opportunity_count(registry):
    opportunity = [narrative_trigger(f"o{i}") for i in range(3)]
    codes, _ = check(base_sheet(opportunity=opportunity), registry)
    assert codes == ["opportunity_count"]


def test_repeated_trigger_id_is_opportunity_id(registry):
    opportunity = [narrative_trigger("o1"), narrative_trigger("o1")]
    codes, _ = check(base_sheet(opportunity=opportunity), registry)
    assert codes == ["opportunity_id"]


def test_empty_trigger_id_is_opportunity_id(registry):
    codes, _ = check(base_sheet(opportunity=[narrative_trigger("")]), registry)
    assert codes == ["opportunity_id"]


def test_empty_trigger_then_is_opportunity_then(registry):
    codes, _ = check(base_sheet(opportunity=[narrative_trigger(then="")]), registry)
    assert codes == ["opportunity_then"]


def test_unknown_npc_in_trigger_gives_validate_refs_text(registry):
    sheet = base_sheet(opportunity=[trigger("o1", {"npc_status": {"id": "ghost", "is": "dead"}})])
    codes, messages = check(sheet, registry, known=known(npcs=["innkeeper"]))
    assert codes == ["opportunity_ref"]
    assert len(messages) == 1
    assert "npc_status: неизвестный NPC 'ghost'" in messages[0]


def test_known_npc_in_trigger_is_fine(registry):
    sheet = base_sheet(
        opportunity=[trigger("o1", {"npc_status": {"id": "innkeeper", "is": "dead"}})]
    )
    assert check(sheet, registry, known=known(npcs=["innkeeper"])) == ([], [])


def test_hero_at_with_known_location_is_fine(registry):
    sheet = base_sheet(opportunity=[trigger("o1", {"hero_at": "cellar"})])
    assert check(sheet, registry, known=known(locations=["cellar"])) == ([], [])


def test_hero_at_with_unknown_location_is_opportunity_ref(registry):
    sheet = base_sheet(opportunity=[trigger("o1", {"hero_at": "moon"})])
    codes, messages = check(sheet, registry, known=known(locations=["cellar"]))
    assert codes == ["opportunity_ref"]
    assert "moon" in messages[0]


def test_unknown_god_in_favor_is_opportunity_ref(registry):
    sheet = base_sheet(opportunity=[trigger("o1", {"favor": {"god": "void", "gte": 1}})])
    codes, _ = check(sheet, registry, known=known())
    assert codes == ["opportunity_ref"]


def test_without_known_refs_are_not_checked(registry):
    sheet = base_sheet(opportunity=[trigger("o1", {"npc_status": {"id": "ghost", "is": "dead"}})])
    assert check(sheet, registry) == ([], [])


# порядок

def test_groups_go_in_fixed_order(registry):
    sheet = with_choices(ability_scores={**SCORES, "str": 16}, name="Гарт")
    sheet = sheet.model_copy(update={"motive": ""})
    codes, messages = check(sheet, registry, taken_names=["Гарт"])
    assert codes == ["standard_array_invalid", "hero_name_taken", "motive_empty"]
    assert len(messages) == 3


def test_extra_background_check_comes_after_build_character_group(registry):
    sheet = with_background(tool="no_such_tool")
    bad = sheet.choices.model_copy(update={"ability_scores": {**SCORES, "str": 16}})
    sheet = sheet.model_copy(update={"choices": bad})
    codes, _ = check(sheet, registry, taken_names=["Борин"])
    assert codes == ["standard_array_invalid", "background_tool_unknown", "hero_name_taken"]


def test_codes_and_messages_are_parallel(registry):
    sheet = base_sheet(motive="", means=[], opportunity=[narrative_trigger("")])
    codes, messages = check(sheet, registry)
    assert codes == ["motive_empty", "means_count", "opportunity_id"]
    assert len(messages) == 3


def test_user_texts_of_name_motive_and_means(registry):
    assert check(with_choices(name=""), registry)[1] == ["имя героя не может быть пустым"]
    assert check(base_sheet(motive=""), registry)[1] == ["мотив героя не может быть пустым"]
    assert check(base_sheet(means=[]), registry)[1] == ["средства героя: от одного до трёх средств"]
