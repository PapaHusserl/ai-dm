# У1 П1 (docs/plan-u1.md, решение 21): бонусы услуг видны игроку.
#   sheet_text.boon_effects(hero, now_s) -> [(название, конец в секундах мира | None)]: живые
#       ActiveEffect-ы из BOONS (groomed «ухожен», со сроком) + heroic_inspiration («вдохновение»,
#       без срока); истёкшие по часам и чужие эффекты не входят.
#   sheet_text.effect_lines(hero, now_s) -> ["ухожен (до ЧЧ:ММ)", "вдохновение"]; если срок в
#       другом дне -- к «до ЧЧ:ММ» добавляется пометка дня.
#   /sheet -- строка «Эффекты: ухожен (до ...); вдохновение» после «Состояния»; без бонусов
#       строки нет.
#   inventory.effects_line («Действует: ...») бонусы услуг (kind="modifier") не показывает.
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.campaign.loader import pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import boon_effects, effect_lines
from ai_dm.rules.inventory import effects_line
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

HOUR = 3600
DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def app(registry, tmp_path):
    return make_app(registry, tmp_path, ReactiveAdapter())


def groomed(until):
    return ActiveEffect(
        id="groomed", source="service:tobb", kind="modifier",
        params={"target": "ability_check", "ability": "cha", "dice": "1d4", "consume": True},
        expires=Expiry(kind="seconds", value=until),
    )


def give(app, until=None, inspired=False):
    hero = hero_of(app.bundle)
    if until is not None:
        hero.creature.active_effects.append(groomed(until))
    hero.heroic_inspiration = inspired
    return hero


def sheet_lines(app):
    return app.handle("/sheet").lines


def effects_row(app):
    return [line for line in sheet_lines(app) if line.startswith("Эффекты")]


def now(app):
    return app.bundle.world.clock.now_s


# boon_effects

def test_boon_effects_of_plain_hero_is_empty(app):
    hero = give(app)
    assert boon_effects(hero, now(app)) == []


def test_boon_effects_lists_groomed_with_its_end(app):
    until = now(app) + 5 * HOUR
    hero = give(app, until)
    assert boon_effects(hero, now(app)) == [("ухожен", until)]


def test_boon_effects_lists_inspiration_without_end(app):
    hero = give(app, inspired=True)
    assert boon_effects(hero, now(app)) == [("вдохновение", None)]


def test_boon_effects_order_is_effects_then_inspiration(app):
    until = now(app) + HOUR
    hero = give(app, until, inspired=True)
    assert [name for name, _ in boon_effects(hero, now(app))] == ["ухожен", "вдохновение"]


def test_boon_effects_skips_expired_groomed(app):
    hero = give(app, now(app) + HOUR)
    assert boon_effects(hero, now(app) + HOUR) == []


def test_boon_effects_skips_foreign_effects(app):
    hero = give(app)
    hero.creature.active_effects.append(
        ActiveEffect(
            id="stoneskin", source="x", kind="modifier", params={},
            expires=Expiry(kind="seconds", value=now(app) + HOUR),
        )
    )
    assert boon_effects(hero, now(app)) == []


# effect_lines

def test_effect_lines_empty_without_boons(app):
    assert effect_lines(give(app), now(app)) == []


def test_effect_lines_groomed_has_clock_time(app):
    start = now(app)
    until = start + 3 * HOUR
    lines = effect_lines(give(app, until), start)
    minutes = until % 86400 // 60
    assert lines == [f"ухожен (до {minutes // 60:02d}:{minutes % 60:02d})"]


def test_effect_lines_marks_expiry_on_another_day(app):
    app.bundle.world.clock.advance(20 * HOUR)
    start = now(app)
    [line] = effect_lines(give(app, start + 10 * HOUR), start)
    assert line == "ухожен (до 06:00, завтра)"


def test_effect_lines_marks_expiry_in_several_days(app):
    start = now(app)
    [line] = effect_lines(give(app, start + 3 * 86400 + HOUR), start)
    assert line == "ухожен (до 01:00, через 3 дн.)"


def test_effect_lines_counts_days_from_today_not_from_epoch(app):
    app.bundle.world.clock.advance(86400 + 20 * HOUR)
    start = now(app)
    [line] = effect_lines(give(app, start + 10 * HOUR), start)
    assert line == "ухожен (до 06:00, завтра)"


def test_effect_lines_marks_expiry_in_two_days(app):
    start = now(app)
    [line] = effect_lines(give(app, start + 2 * 86400 + HOUR), start)
    assert line == "ухожен (до 01:00, через 2 дн.)"


def test_effect_lines_same_day_has_no_day_mark(app):
    start = now(app)
    [line] = effect_lines(give(app, start + HOUR), start)
    assert line == "ухожен (до 01:00)"


def test_effect_lines_inspiration_is_plain_word(app):
    assert effect_lines(give(app, inspired=True), now(app)) == ["вдохновение"]


# /sheet

def test_sheet_shows_effects_line_with_both_boons(app):
    give(app, now(app) + HOUR, inspired=True)
    [row] = effects_row(app)
    assert row.startswith("Эффекты: ухожен (до ")
    assert row.endswith("); вдохновение")


def test_sheet_shows_only_inspiration(app):
    give(app, inspired=True)
    assert effects_row(app) == ["Эффекты: вдохновение"]


def test_sheet_without_boons_has_no_effects_line(app):
    give(app)
    assert effects_row(app) == []


def test_sheet_drops_expired_groomed(app):
    give(app, now(app))
    assert effects_row(app) == []


def test_sheet_effects_line_follows_conditions_line(app):
    hero = give(app, inspired=True)
    hero.creature.conditions.append(AppliedCondition(id="cursed"))
    lines = sheet_lines(app)
    assert lines.index("Эффекты: вдохновение") == lines.index("Состояния: проклят") + 1


# «Действует:» (inventory.effects_line) не подхватывает бонус услуги

def test_inventory_effects_line_ignores_groomed(app):
    hero = give(app, now(app) + HOUR)
    assert effects_line(hero, app.registry, now(app)) == ""


# «Действует:» пропускает чужие эффекты, но не обрывается на них (предмет идёт после)

@pytest.fixture
def dragon_registry():
    return load_registry([pack_content_dir(DRAGON)])


def stoneskin(until):
    return ActiveEffect(
        id="stoneskin_elixir", source="hero", kind="ac", params={"amount": 2},
        expires=Expiry(kind="seconds", value=until),
    )


def effects_line_after(app, registry, skipped):
    hero = give(app)
    hero.creature.active_effects.append(skipped)
    hero.creature.active_effects.append(stoneskin(now(app) + HOUR))
    return effects_line(hero, registry, now(app))


def test_effects_line_shows_item_effect(app, dragon_registry):
    hero = give(app)
    hero.creature.active_effects.append(stoneskin(now(app) + HOUR))
    line = effects_line(hero, dragon_registry, now(app))
    assert line == "Действует: Каменная Кожа (+2 КД) до 01:00"


def test_effects_line_skips_effect_without_expiry(app, dragon_registry):
    skipped = ActiveEffect(id="ghost", source="x", kind="ac", params={"amount": 1})
    line = effects_line_after(app, dragon_registry, skipped)
    assert line == "Действует: Каменная Кожа (+2 КД) до 01:00"


def test_effects_line_skips_effect_with_non_seconds_expiry(app, dragon_registry):
    skipped = ActiveEffect(
        id="ghost", source="x", kind="ac", params={"amount": 1},
        expires=Expiry(kind="rounds", value=5),
    )
    line = effects_line_after(app, dragon_registry, skipped)
    assert line == "Действует: Каменная Кожа (+2 КД) до 01:00"


def test_effects_line_skips_spell_effect(app, dragon_registry):
    skipped = ActiveEffect(
        id="ghost", source="x", kind="spell",
        expires=Expiry(kind="seconds", value=now(app) + HOUR),
    )
    line = effects_line_after(app, dragon_registry, skipped)
    assert line == "Действует: Каменная Кожа (+2 КД) до 01:00"


def test_effects_line_skips_modifier_effect(app, dragon_registry):
    line = effects_line_after(app, dragon_registry, groomed(now(app) + HOUR))
    assert line == "Действует: Каменная Кожа (+2 КД) до 01:00"
