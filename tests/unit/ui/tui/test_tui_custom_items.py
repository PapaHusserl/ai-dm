# Партия Б (CUSTOM-ITEMS-PLAN, разд. 3): панель «Получено» (#gains) после хода с give_custom_item
# показывает «Ржавый ключ ×1»; следующий ход без выдачи -- панель без ключа.
import asyncio

from ui_kit import text_app, text_step

from ai_dm.ui.session import PlaySession
from ai_dm.ui.tui.app import AiDmApp


def give_step(name="Ржавый ключ", **fields):
    data = {
        "type": "give_custom_item", "name": name, "description": "Ключ от ворот", "qty": 1,
        "weight_lb": 0, "cost_cp": 0, "quest": True,
    }
    data.update(fields)
    return {"tool_calls": [{"id": "gc-1", "name": "give_custom_item", "input": data}]}


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def tui_of(registry, tmp_path, steps):
    return AiDmApp(PlaySession(text_app(registry, tmp_path, steps)))


def test_gains_panel_shows_the_custom_item(registry, tmp_path, tui):
    app = tui_of(registry, tmp_path, [give_step(), text_step("Вам вручают ключ.")])

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Беру ключ")
        return tui.shown(app.query_one("#gains")), tui.flat(tui.text_of(app.query_one("#gains")))

    shown, text = run(app, steps)
    assert shown is True
    assert "Ржавый ключ ×1" in text


def test_gains_panel_clears_on_the_next_turn(registry, tmp_path, tui):
    script = [give_step(), text_step("Вам вручают ключ."), text_step("Тихо.")]
    app = tui_of(registry, tmp_path, script)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Беру ключ")
        await tui.submit(app, pilot, "Жду")
        return tui.flat(tui.text_of(app.query_one("#gains")))

    assert "Ржавый ключ" not in run(app, steps)
