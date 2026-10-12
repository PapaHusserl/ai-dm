# К0-фикс-б (K0-FIX-PLAN, 7.4, Q11): шаги «Пол» и «Местоимения» пошагового создания героя --
# таблица шагов, варианты, запись в черновик, сброс, сборка листа.
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent))

from test_hero_steps import draft, full_draft, step, steps, values  # noqa: E402


def keys():
    return [s.key for s in steps()]


def test_gender_and_pronouns_steps_follow_name_in_that_order():
    ks = keys()
    assert ks[ks.index("name") + 1:ks.index("name") + 4] == ["gender", "pronouns", "motive"]


def test_gender_step_is_a_pick_and_pronouns_step_is_text():
    assert step("gender").kind == "pick"
    assert step("pronouns").kind == "text"


def test_gender_and_pronouns_steps_are_always_needed():
    assert step("gender").needs is None
    assert step("pronouns").needs is None


def test_gender_step_has_four_options_with_unspecified_last(registry):
    assert values("gender", draft(), registry) == ["male", "female", "other", ""]


def test_gender_option_labels_are_russian_and_distinct(registry):
    labels = [o.label for o in step("gender").options(draft(), registry)]
    assert len(set(labels)) == 4
    assert labels[0].lower().startswith("муж")
    assert labels[1].lower().startswith("жен")
    assert labels[3] == "Не указывать"


def test_gender_step_has_no_custom_put():
    assert step("gender").put is None


def test_gender_pick_is_stored_in_draft(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft()
    assert apply_put(current, registry, step_index("gender"), "female") is None
    assert current.gender == "female"


def test_draft_has_no_gender_by_default():
    current = draft()
    assert current.gender == ""
    assert current.pronouns == ""


def test_pronouns_text_is_stored_stripped(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft()
    assert apply_put(current, registry, step_index("pronouns"), "  они  ") is None
    assert current.pronouns == "они"


def test_pronouns_dash_means_none(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft(pronouns="они")
    assert apply_put(current, registry, step_index("pronouns"), "-") is None
    assert current.pronouns == ""


def test_pronouns_empty_string_is_accepted_by_put(registry):
    from ai_dm.game.hero_steps import apply_put, step_index

    current = draft()
    assert apply_put(current, registry, step_index("pronouns"), "") is None
    assert current.pronouns == ""


# clear_from

def test_clear_from_name_resets_gender_and_pronouns():
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    current.gender = "male"
    current.pronouns = "он"
    clear_from(current, "name")
    assert (current.gender, current.pronouns) == ("", "")


def test_clear_from_gender_keeps_name():
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    current.gender = "male"
    clear_from(current, "gender")
    assert current.name == "Борин"
    assert current.gender == ""


def test_clear_from_motive_keeps_gender():
    from ai_dm.game.hero_steps import clear_from

    current = full_draft()
    current.gender = "male"
    current.pronouns = "он"
    clear_from(current, "motive")
    assert (current.gender, current.pronouns) == ("male", "он")


# to_sheet

@pytest.mark.parametrize("gender", ["male", "female", "other"])
def test_to_sheet_carries_gender(registry, gender):
    from ai_dm.game.hero_steps import to_sheet

    current = full_draft()
    current.gender = gender
    assert to_sheet(current, registry).choices.gender == gender


def test_to_sheet_empty_gender_is_none(registry):
    from ai_dm.game.hero_steps import to_sheet

    assert to_sheet(full_draft(), registry).choices.gender is None


def test_to_sheet_carries_pronouns(registry):
    from ai_dm.game.hero_steps import to_sheet

    current = full_draft()
    current.gender = "other"
    current.pronouns = "они"
    assert to_sheet(current, registry).choices.pronouns == "они"


def test_to_sheet_without_pronouns_has_empty_string(registry):
    from ai_dm.game.hero_steps import to_sheet

    assert to_sheet(full_draft(), registry).choices.pronouns == ""
