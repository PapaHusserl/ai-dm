# У0 П3 (docs/plan-u0.md, Р10): состояния героя видны игроку.
#   sheet_text.condition_names(hero, registry) -- названия состояний строчными, без повторов,
#       в порядке наложения.
#   /sheet -- строка «Состояния: проклят» (через запятую, если несколько); без состояний строки нет.
import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import condition_names
from ai_dm.state.creature import AppliedCondition


@pytest.fixture
def app(registry, tmp_path):
    return make_app(registry, tmp_path, ReactiveAdapter())


def add(app, *ids):
    hero = hero_of(app.bundle)
    hero.creature.conditions.extend(AppliedCondition(id=i) for i in ids)
    return hero


def sheet_lines(app):
    return app.handle("/sheet").lines


def test_condition_names_of_healthy_hero_is_empty(app):
    assert condition_names(hero_of(app.bundle), app.registry) == []


def test_condition_names_gives_lowercase_card_name(app):
    hero = add(app, "cursed")
    assert condition_names(hero, app.registry) == ["проклят"]


def test_condition_names_keeps_application_order(app):
    hero = add(app, "cursed", "poisoned")
    names = condition_names(hero, app.registry)
    assert names == [
        app.registry.get("condition", "cursed").name.lower(),
        app.registry.get("condition", "poisoned").name.lower(),
    ]
    assert names[0] == "проклят"


def test_condition_names_has_no_repeats(app):
    hero = add(app, "cursed", "cursed")
    assert condition_names(hero, app.registry) == ["проклят"]


def test_sheet_shows_cursed_line(app):
    add(app, "cursed")
    assert "Состояния: проклят" in sheet_lines(app)


def test_sheet_lists_several_conditions_with_comma(app):
    add(app, "cursed", "poisoned")
    poisoned = app.registry.get("condition", "poisoned").name.lower()
    assert f"Состояния: проклят, {poisoned}" in sheet_lines(app)


def test_sheet_without_conditions_has_no_conditions_line(app):
    assert not [line for line in sheet_lines(app) if line.startswith("Состояния")]


def test_sheet_conditions_line_is_a_separate_line(app):
    add(app, "cursed")
    lines = [line for line in sheet_lines(app) if "проклят" in line]
    assert lines == ["Состояния: проклят"]


def test_sheet_condition_disappears_after_removal(app):
    hero = add(app, "cursed")
    hero.creature.conditions.clear()
    assert "Состояния: проклят" not in sheet_lines(app)
