# Торговля, партия Т4 (docs/plan-trade.md, разд. 5): /shop в TUI -- модалка с заголовком «Торговля»;
# без торговца -- справочная TextModal «Здесь никто не торгует», с одним торговцем (164 П2) --
# окно ShopModal; остальные случаи окна -- в test_tui_shop_modal.py.
# После покупки в панели «Получено» (#gains) есть «Потрачено: −1 зм».
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from test_gains_spent import MINUS, merchant_app  # noqa: E402
from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.modals import ShopModal, TextModal  # noqa: E402


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def shop_in_tui(game, tui):
    async def steps(app, pilot):
        await tui.submit(app, pilot, "/shop")
        modal = isinstance(app.screen, TextModal)
        title = app.screen.query_one("#modal").border_title if modal else None
        return modal, title, tui.flat(tui.visible_text(app))

    return run(AiDmApp(PlaySession(game)), steps)


def test_shop_title_is_in_modal_titles():
    assert strings.MODAL_TITLES["/shop"] == "Торговля"


def test_shop_without_merchant_opens_modal(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step()])
    modal, title, text = shop_in_tui(game, tui)
    assert modal is True
    assert title == "Торговля"
    assert "Здесь никто не торгует" in text


def test_shop_with_one_merchant_opens_shop_window_with_assortment(registry, tmp_path, tui):
    game, _ = merchant_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/shop")
        window = isinstance(app.screen, ShopModal)
        title = app.screen.query_one("#modal").border_title if window else None
        return window, title, tui.flat(tui.visible_text(app))

    window, title, text = run(AiDmApp(PlaySession(game)), steps)
    assert window is True
    assert title == "Торговля"
    assert strings.SHOP_PICK in text
    assert "Стрелы — 5 мм" in text


def test_shop_modal_is_not_a_turn(registry, tmp_path, tui):
    game, _ = merchant_app(registry, tmp_path)
    now = game.bundle.world.clock.now_s
    shop_in_tui(game, tui)
    assert game.bundle.world.clock.now_s == now
    assert game.adapter.requests == []


def test_gains_panel_shows_spent_after_purchase(registry, tmp_path, tui):
    game, _ = merchant_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Покупаю колчан")
        return tui.shown(app.query_one("#gains")), tui.flat(tui.text_of(app.query_one("#gains")))

    shown, text = run(AiDmApp(PlaySession(game)), steps)
    assert shown is True
    assert "Колчан ×1" in text
    assert f"Потрачено: {MINUS}1 зм" in text
