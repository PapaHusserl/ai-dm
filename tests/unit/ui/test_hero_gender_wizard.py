# К0-фикс-б (K0-FIX-PLAN, 7.4): HeroWizard проходит шаги «Пол» и «Местоимения»; пол попадает в лист.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import first_option_walk, lines_before, walk, wizard_script  # noqa: E402
from test_ui_hero_wizard import key_of, make, menu_of  # noqa: E402

SCRIPT = wizard_script()


def at_gender(registry, cfg):
    wizard, _ = make(registry, cfg)
    step = walk(wizard, lines_before(SCRIPT, "gender"))
    return wizard, step


def at_pronouns(registry, cfg, gender="4"):
    wizard, _ = at_gender(registry, cfg)
    return wizard, wizard.submit(gender)


def finish(registry, cfg, gender, pronouns):
    wizard, _ = make(registry, cfg)
    lines = [line for _, line in SCRIPT]
    index = [key for key, _ in SCRIPT].index("gender")
    lines[index] = gender
    lines[index + 1] = pronouns
    walk(wizard, lines)
    return wizard


def test_gender_menu_comes_right_after_name(registry, cfg):
    wizard, step = at_gender(registry, cfg)
    assert key_of(wizard) == "gender"
    assert len(menu_of(step)) == 4


def test_gender_menu_items_are_russian(registry, cfg):
    _, step = at_gender(registry, cfg)
    items = [item.lower() for item in menu_of(step)]
    assert items[0].startswith("муж")
    assert items[1].startswith("жен")
    assert "указ" in items[3]


def test_choosing_gender_goes_to_pronouns_step(registry, cfg):
    wizard, _ = at_pronouns(registry, cfg)
    assert key_of(wizard) == "pronouns"


def test_pronouns_step_is_text_without_menu(registry, cfg):
    _, step = at_pronouns(registry, cfg)
    assert [b for b in step.blocks if b.kind == "menu"] == []


def test_pronouns_step_hint_mentions_dash(registry, cfg):
    _, step = at_pronouns(registry, cfg)
    assert "-" in "\n".join(b.text for b in step.blocks)


def test_pronouns_step_goes_on_to_motive(registry, cfg):
    wizard, _ = at_pronouns(registry, cfg)
    wizard.submit("-")
    assert key_of(wizard) == "motive"


def test_unspecified_gender_gives_none_in_sheet(registry, cfg):
    wizard = finish(registry, cfg, "4", "-")
    assert wizard.state == "review"
    assert wizard.draft.gender == ""


def test_picked_gender_reaches_the_draft(registry, cfg):
    wizard = finish(registry, cfg, "2", "-")
    assert wizard.draft.gender == "female"


def test_accepted_sheet_carries_gender_and_pronouns(registry, cfg):
    wizard = finish(registry, cfg, "3", "они")
    wizard.submit("1")
    choices = wizard.sheet.choices
    assert (choices.gender, choices.pronouns) == ("other", "они")


def test_accepted_sheet_without_gender_is_unset(registry, cfg):
    wizard = finish(registry, cfg, "4", "-")
    wizard.submit("1")
    assert wizard.sheet.choices.gender is None
    assert wizard.sheet.choices.pronouns == ""


def test_back_from_pronouns_returns_to_gender(registry, cfg):
    wizard, _ = at_pronouns(registry, cfg)
    wizard.submit("назад")
    assert key_of(wizard) == "gender"


def test_back_from_gender_returns_to_name(registry, cfg):
    wizard, _ = at_gender(registry, cfg)
    wizard.submit("назад")
    assert key_of(wizard) == "name"


def test_first_option_walk_reaches_review_with_male_hero(registry, cfg):
    wizard, _ = make(registry, cfg)
    first_option_walk(wizard)
    assert wizard.state == "review"
    assert wizard.draft.gender == "male"
