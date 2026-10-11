# Этап 5, P2 (A7): только русский. Сторож латиницы по ВИДИМОМУ тексту экрана (то, что нарисовано в
# терминале, включая Footer) после старта, хода и в узком режиме с правой панелью. Белый список --
# в tui.latin_words (conftest): id мира, provider:model, HP, $, метки клавиш (F2, ^q),
# запись кубиков (d20, 2d10), /команды, «vs» из строк бросков. Палитра команд не открывается.
import asyncio

from textual.command import CommandPalette
from textual.widgets import Footer


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def test_no_latin_after_start(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.visible_text(app)

    text = run(app, steps)
    assert "HP" in text
    assert tui.latin_words(text, game.world_id) == []


def test_no_latin_after_turn(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.visible_text(app)

    text = run(app, steps)
    assert tui.NARRATION in text
    assert tui.latin_words(text, game.world_id) == []


def test_no_latin_after_turn_in_narrow_terminal_with_side_panel(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        return tui.visible_text(app)

    assert tui.latin_words(run(app, steps, (100, 40)), game.world_id) == []


def test_footer_is_shown_and_has_no_latin(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.shown(app.query_one(Footer)), tui.footer_text(app)

    shown, text = run(app, steps)
    assert shown is True
    assert any("а" <= ch.lower() <= "я" for ch in text)
    assert tui.latin_words(text, game.world_id) == []


def test_footer_has_no_latin_after_turn(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.footer_text(app)

    assert tui.latin_words(run(app, steps), game.world_id) == []


def test_title_and_input_placeholder_have_no_latin(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return f"{app.title} {app.sub_title} {app.query_one('#input').placeholder}"

    text = run(app, steps)
    assert text.strip()
    assert tui.latin_words(text, game.world_id) == []


def test_command_palette_is_off(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("ctrl+p")
        await pilot.pause()
        return len(app.screen_stack), isinstance(app.screen, CommandPalette)

    assert run(app, steps) == (1, False)


def test_footer_has_no_palette_key(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.footer_text(app)

    assert "^p" not in run(app, steps).lower()


# Б1б: PickerApp (выбор героя и пресета) -- только русский (HeroCreateApp -- в test_tui_create)

def test_picker_app_has_no_latin(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Пресет мира:", ["Как в паке", "Героика (в духе «Властелин колец»)"])

    async def steps(app, pilot):
        return tui.visible_text(app)

    text = run(app, steps)
    assert "Как в паке" in text
    assert tui.latin_words(text) == []


# Б2б: PickerApp с заставкой и HeroCreateApp с STEPS_PLACEHOLDER -- без латиницы.
# Заставка -- ASCII-рисунок art/data/title.txt; сторож его не ловит (латинских слов в рисунке нет),
# поэтому строки рисунка не исключаются

def test_picker_app_with_title_art_has_no_latin(tui):
    from ai_dm.art import art_for_event
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", ["Арн", "Создать пошагово"], splash=True)

    async def steps(app, pilot):
        return tui.visible_text(app)

    text = run(app, steps, (140, 50))
    assert any(row.strip() and row.strip() in text for row in art_for_event("title").splitlines())
    assert "Создать пошагово" in text
    assert tui.latin_words(text) == []


def test_steps_create_app_with_title_art_has_no_latin(registry, cfg, tmp_path, tui):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))
    from hero_kit import deps, sheet_task, vale_pack

    from ai_dm.llm.mock import ScriptedAdapter
    from ai_dm.ui.hero_wizard import HeroWizard
    from ai_dm.ui.tui import strings
    from ai_dm.ui.tui.create import HeroCreateApp

    wizard = HeroWizard(deps(ScriptedAdapter([]), registry, cfg, tmp_path),
                        sheet_task(vale_pack(registry)), 80)
    app = HeroCreateApp(wizard, placeholder=strings.STEPS_PLACEHOLDER)

    async def steps(app, pilot):
        return tui.visible_text(app), app.query_one("#input").placeholder

    text, placeholder = run(app, steps, (140, 50))
    assert "Вид героя" in text
    # «Esc» -- название клавиши, как F2 и ^q в белом списке
    assert [w for w in tui.latin_words(text) if w != "Esc"] == []
    assert [w for w in tui.latin_words(placeholder) if w != "Esc"] == []
