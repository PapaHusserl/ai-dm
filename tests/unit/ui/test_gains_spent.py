# Торговля, партия Т4 (docs/plan-trade.md, разд. 5, В-Т7): «Потрачено: −X» рядом с «Получено».
#   gains_lines(app, snapshot): деньги уменьшились -- строка «Потрачено: −<сумма>» (минус U+2212),
#   выросли -- прежняя «Деньги: +X», не изменились -- ни той ни другой.
#   Простой режим: «Получено: Колчан ×1» и отдельно «Потрачено: −1 зм»; без трат строки нет.
from ui_kit import play, text_app, text_step

from ai_dm.game.scene import hero_of
from ai_dm.rules.inventory import add_item
from ai_dm.state.world import NPC, TradeProfile
from ai_dm.ui.screen import gains_lines, loot_snapshot

MINUS = "−"
BUY = {
    "id": "tr-1", "name": "trade",
    "input": {
        "type": "trade", "npc_id": "mara", "direction": "buy", "item_id": "quiver",
        "qty": 1, "quality": "any",
    },
}


def setup(registry, tmp_path, steps=None):
    app = text_app(registry, tmp_path, steps or [text_step()])
    hero = hero_of(app.bundle)
    hero.money_cp = 1000
    hero.inventory.clear()
    return app, hero


def merchant_app(registry, tmp_path):
    app, hero = setup(registry, tmp_path, [{"tool_calls": [BUY]}, text_step("Мара кивает.")])
    app.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero.location_id,
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=10**9),
    )
    return app, hero


def test_money_decrease_gives_spent_line(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    before = loot_snapshot(app)
    hero.money_cp -= 100
    assert gains_lines(app, before) == [f"Потрачено: {MINUS}1 зм"]


def test_spent_amount_uses_money_format(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    before = loot_snapshot(app)
    hero.money_cp -= 450
    assert gains_lines(app, before) == [f"Потрачено: {MINUS}4 зм 5 см"]


def test_money_increase_gives_gain_not_spent(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    before = loot_snapshot(app)
    hero.money_cp += 100
    assert gains_lines(app, before) == ["Деньги: +1 зм"]


def test_same_money_gives_no_spent_line(registry, tmp_path):
    app, _ = setup(registry, tmp_path)
    assert gains_lines(app, loot_snapshot(app)) == []


def test_purchase_gives_item_and_spent(registry, tmp_path):
    app, hero = setup(registry, tmp_path)
    before = loot_snapshot(app)
    add_item(hero, "quiver", cost_cp=100)
    hero.money_cp -= 100
    assert gains_lines(app, before) == ["Колчан ×1", f"Потрачено: {MINUS}1 зм"]


def test_simple_mode_shows_gained_and_spent_after_purchase(registry, tmp_path):
    app, hero = merchant_app(registry, tmp_path)
    text = " ".join(play(app, ["Покупаю колчан"]).text.split())
    assert "Получено: Колчан ×1" in text
    assert f"Потрачено: {MINUS}1 зм" in text
    assert hero_of(app.bundle).money_cp == 900


def test_simple_mode_spent_is_not_inside_the_gained_line(registry, tmp_path):
    app, _ = merchant_app(registry, tmp_path)
    lines = play(app, ["Покупаю колчан"]).lines
    gained = [x for x in lines if "Получено:" in x]
    assert gained and all("Потрачено" not in x for x in gained)


def test_simple_mode_without_spending_has_no_spent_line(registry, tmp_path):
    app, _ = setup(registry, tmp_path, [text_step("Тихо.")])
    assert "Потрачено" not in play(app, ["Осматриваюсь"]).text


def test_spent_line_is_wrapped_to_the_width():
    from ai_dm.ui.screen import Block
    from ai_dm.ui.simple import gains_lines_text

    block = Block("gains", items=(f"Потрачено: {MINUS}1234 зм 5 см 6 мм",))
    assert len(gains_lines_text(block, 20)) > 1


def gains_text(block, width=80):
    from ai_dm.ui.simple import gains_lines_text

    return gains_lines_text(block, width)


def test_gained_items_are_joined_with_comma():
    from ai_dm.ui.screen import Block

    block = Block("gains", items=("Колчан ×1", "Деньги: +1 зм"))
    assert gains_text(block) == ["  Получено: Колчан ×1, Деньги: +1 зм"]


def test_gained_line_is_wrapped_to_the_width():
    from ai_dm.ui.screen import Block

    block = Block("gains", items=("Колчан ×1", "Скимитар ×1", "Деньги: +1 зм"))
    assert len(gains_text(block, 20)) > 1


def test_block_text_goes_first_then_gained_then_spent():
    from ai_dm.ui.screen import Block

    block = Block(
        "gains", text="Опыт: +5", items=(f"Потрачено: {MINUS}1 зм", "Колчан ×1")
    )
    assert gains_text(block) == [
        "  Опыт: +5", "  Получено: Колчан ×1", f"  Потрачено: {MINUS}1 зм"
    ]


def test_block_text_is_wrapped_to_the_width():
    from ai_dm.ui.screen import Block

    block = Block("gains", text="Опыт за победу над гоблинами: +50")
    assert len(gains_text(block, 20)) > 1


def test_only_spent_has_no_gained_line():
    from ai_dm.ui.screen import Block

    block = Block("gains", items=(f"Потрачено: {MINUS}1 зм",))
    assert gains_text(block) == [f"  Потрачено: {MINUS}1 зм"]
