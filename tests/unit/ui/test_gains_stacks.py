# «Получено» по ключу стека (docs/plan-custom-items.md, разд. 8, партия 0).
#   loot_snapshot(app) -> (xp, items, money) -- items теперь по ключу (item_id, cost_cp, quality);
#   gains_lines(app, snapshot) -- строка на каждый выросший стек, а не на id: два стека одного
#   id не склеиваются и не теряют прирост (раньше словарь item_id -> qty ломался на них).
#   Имя в строке -- как в /inv (с пометкой качества; для worn есть корень «поношенн»), затем ×N.
from ui_kit import text_app, text_step

from ai_dm.game.scene import hero_of
from ai_dm.rules.inventory import add_item, remove_item
from ai_dm.rules.money import format_cp
from ai_dm.ui.screen import gains_lines, loot_snapshot


def setup(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    return app, hero_of(app.bundle)


def test_new_stack_of_an_existing_id_is_a_gain(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", cost_cp=2500)
    before = loot_snapshot(app)
    add_item(hero, "scimitar", cost_cp=150)
    assert gains_lines(app, before) == ["Скимитар ×1"]


def test_growth_of_one_stack_does_not_show_the_other(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", 3, cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150, quality="worn")
    before = loot_snapshot(app)
    add_item(hero, "scimitar", 2, cost_cp=150, quality="worn")
    lines = gains_lines(app, before)
    assert len(lines) == 1
    assert "поношенн" in lines[0].casefold() and lines[0].endswith("×2")


def test_two_stacks_grow_two_lines(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    before = loot_snapshot(app)
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", 2, cost_cp=150, quality="worn")
    lines = gains_lines(app, before)
    assert "Скимитар ×1" in lines
    assert len(lines) == 2
    assert [x for x in lines if x != "Скимитар ×1"][0].endswith("×2")


def test_gain_amount_is_counted_per_stack(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", 2, cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150)
    before = loot_snapshot(app)
    add_item(hero, "scimitar", cost_cp=2500)
    assert gains_lines(app, before) == ["Скимитар ×1"]


def test_unchanged_stacks_give_no_lines(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150)
    assert gains_lines(app, loot_snapshot(app)) == []


def test_removed_stack_is_not_a_gain(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", cost_cp=2500)
    add_item(hero, "scimitar", cost_cp=150)
    before = loot_snapshot(app)
    remove_item(hero, "scimitar")
    assert gains_lines(app, before) == []


def test_same_price_stack_with_other_quality_is_a_new_gain(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    add_item(hero, "scimitar", cost_cp=150)
    before = loot_snapshot(app)
    add_item(hero, "scimitar", cost_cp=150, quality="junk")
    lines = gains_lines(app, before)
    assert len(lines) == 1
    assert lines[0] != "Скимитар ×1" and lines[0].endswith("×1")


def test_gains_keep_money_and_xp_lines(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    hero.sheet.xp = 7
    hero.money_cp = 100
    before = loot_snapshot(app)
    add_item(hero, "scimitar", cost_cp=150)
    hero.money_cp += 5
    hero.sheet.xp += 10
    lines = gains_lines(app, before)
    assert lines[0] == "Опыт: +10"
    assert lines[1] == "Скимитар ×1"
    assert lines[2] == f"Деньги: +{format_cp(5)}"
