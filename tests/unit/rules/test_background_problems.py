# Б0-П1 (B0-PLAN A5): общая проверка свободной предыстории -- путь модели и ручная правка.
# background_check(spec, registry, class_skills=()) -> (коды, тексты); background_problems удалена
# в Б1а (поглощена sheet_check/background_check), здесь -- локальный помощник по [1];
# background_skill_conflict(spec, class_skills) -> bool.
from ai_dm.rules.builder import (
    BACKGROUND_MESSAGES,
    background_check,
    background_skill_conflict,
)
from ai_dm.state.hero import BackgroundSpec

CLASS_SKILLS = ["perception", "survival"]


def background_problems(spec, registry, class_skills=()):
    return background_check(spec, registry, class_skills)[1]


def spec_of(**changes):
    spec = BackgroundSpec(
        name="Бывший цирковой акробат",
        abilities=["dex", "con", "cha"],
        skills=["acrobatics", "performance"],
        tool="thieves_tools",
        feat="alert",
        equipment=["crowbar"],
        gold_cp=1000,
    )
    return spec.model_copy(update=changes)


def test_valid_spec_has_no_problems(registry):
    assert background_problems(spec_of(), registry, CLASS_SKILLS) == []


def test_valid_spec_without_class_skills_has_no_problems(registry):
    assert background_problems(spec_of(), registry) == []


def test_budget_exactly_50_gp_is_ok(registry):
    spec = spec_of(equipment=[], gold_cp=5000)
    assert background_problems(spec, registry, CLASS_SKILLS) == []


def test_budget_over_by_one_copper_gives_budget_text(registry):
    spec = spec_of(equipment=[], gold_cp=5001)
    problems = background_problems(spec, registry, CLASS_SKILLS)
    assert problems == [BACKGROUND_MESSAGES["background_budget_invalid"]]


def test_non_origin_feat_gives_feat_text(registry):
    problems = background_problems(spec_of(feat="defense"), registry, CLASS_SKILLS)
    assert problems == [BACKGROUND_MESSAGES["background_feat"]]


def test_unknown_feat_gives_feat_text(registry):
    problems = background_problems(spec_of(feat="no_such_feat"), registry, CLASS_SKILLS)
    assert problems == [BACKGROUND_MESSAGES["background_feat"]]


def test_class_skill_in_background_gives_conflict_text(registry):
    spec = spec_of(skills=["perception", "performance"])
    problems = background_problems(spec, registry, CLASS_SKILLS)
    assert len(problems) == 1
    assert "навык класса уже даёт предыстория" in problems[0]


def test_class_skill_conflict_is_not_checked_without_class_skills(registry):
    spec = spec_of(skills=["perception", "performance"])
    assert background_problems(spec, registry) == []


def test_unknown_equipment_item_gives_item_unknown_text(registry):
    problems = background_problems(spec_of(equipment=["no_such_item"]), registry, CLASS_SKILLS)
    assert len(problems) == 1
    assert "no_such_item" in problems[0]


def test_every_unknown_equipment_item_is_reported(registry):
    spec = spec_of(equipment=["ghost_a", "crowbar", "ghost_b"])
    problems = background_problems(spec, registry, CLASS_SKILLS)
    assert len(problems) == 2
    assert "ghost_a" in problems[0]
    assert "ghost_b" in problems[1]


def test_tool_not_in_registry_gives_tool_text_with_id(registry):
    problems = background_problems(spec_of(tool="no_such_tool"), registry, CLASS_SKILLS)
    assert len(problems) == 1
    assert "нет такого инструмента: no_such_tool" in problems[0]


def test_item_that_is_not_a_tool_gives_tool_text(registry):
    problems = background_problems(spec_of(tool="crowbar"), registry, CLASS_SKILLS)
    assert len(problems) == 1
    assert "нет такого инструмента: crowbar" in problems[0]


def test_empty_tool_gives_only_the_old_tool_text(registry):
    problems = background_problems(spec_of(tool=""), registry, CLASS_SKILLS)
    assert problems == [BACKGROUND_MESSAGES["background_tool"]]


def test_bad_abilities_and_skills_texts_come_from_validation(registry):
    spec = spec_of(abilities=["dex"], skills=["acrobatics"])
    problems = background_problems(spec, registry, CLASS_SKILLS)
    assert BACKGROUND_MESSAGES["background_abilities"] in problems
    assert BACKGROUND_MESSAGES["background_skills"] in problems


def test_all_problems_are_reported_together(registry):
    spec = spec_of(
        skills=["perception", "performance"], feat="defense", equipment=["ghost"],
        tool="no_such_tool", gold_cp=9000,
    )
    problems = background_problems(spec, registry, CLASS_SKILLS)
    assert len(problems) == 5


def test_manual_edit_dict_gives_same_texts_as_model_spec(registry):
    data = {
        "name": "Бродяга", "abilities": ["dex", "con", "cha"],
        "skills": ["perception", "performance"], "tool": "thieves_tools", "feat": "defense",
        "equipment": [], "gold_cp": 6000,
    }
    from_dict = background_problems(BackgroundSpec.model_validate(data), registry, CLASS_SKILLS)
    from_spec = background_problems(BackgroundSpec(**data), registry, CLASS_SKILLS)
    assert from_dict == from_spec
    assert len(from_dict) == 3


# background_skill_conflict

def test_skill_conflict_true_when_class_skill_in_background():
    assert background_skill_conflict(spec_of(skills=["acrobatics", "survival"]), CLASS_SKILLS)


def test_skill_conflict_false_without_overlap():
    assert not background_skill_conflict(spec_of(), CLASS_SKILLS)


def test_skill_conflict_false_for_empty_class_skills():
    assert not background_skill_conflict(spec_of(), [])


def test_skill_conflict_second_class_skill_counts():
    spec = spec_of(skills=["acrobatics", "performance"])
    assert background_skill_conflict(spec, ["perception", "acrobatics"])


# описание, золото (после ревью Б0-П1)

def test_description_of_300_chars_is_ok(registry):
    assert background_problems(spec_of(description="а" * 300), registry, CLASS_SKILLS) == []


def test_description_of_301_chars_gives_text_with_length_and_limit(registry):
    problems = background_problems(spec_of(description="а" * 301), registry, CLASS_SKILLS)
    assert len(problems) == 1
    assert "301" in problems[0]
    assert "300" in problems[0]


def test_description_too_long_has_own_code(registry):
    from ai_dm.rules.builder import background_check

    codes, _ = background_check(spec_of(description="а" * 301), registry, CLASS_SKILLS)
    assert codes == ["description_too_long"]


def test_negative_gold_has_own_code_and_text(registry):
    from ai_dm.rules.builder import background_check

    codes, messages = background_check(spec_of(equipment=[], gold_cp=-1), registry, CLASS_SKILLS)
    assert codes == ["background_gold_negative"]
    assert "отрицательным" in messages[0]


def test_zero_gold_is_ok(registry):
    assert background_problems(spec_of(equipment=[], gold_cp=0), registry, CLASS_SKILLS) == []


def test_negative_gold_cannot_hide_over_budget_items(registry):
    # кольчуга 75 зм, золото -30 зм: сумма 45 зм проходит бюджет, но золото < 0 -- ошибка
    spec = spec_of(equipment=["chain_mail"], gold_cp=-3000)
    assert background_problems(spec, registry, CLASS_SKILLS) != []


def test_weapon_in_equipment_is_known(registry):
    spec = spec_of(equipment=["dagger", "spear"], gold_cp=0)
    assert background_problems(spec, registry, CLASS_SKILLS) == []
