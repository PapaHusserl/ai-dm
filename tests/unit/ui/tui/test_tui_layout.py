# Этап 5, P2 (A8): раскладка. Две колонки при ширине >= 120, иначе одна; F2 показывает #side;
# ресайз перестраивает; место под рисунок существует и скрыто. Контракт -- в conftest.py.
import asyncio

from textual.widgets import Footer

IDS = ["feed", "choices", "input", "status", "side", "picture", "hero", "combat", "rolls", "gains"]


def run(app, size, steps):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def test_all_panels_exist(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return [name for name in IDS if not app.query(f"#{name}")]

    assert run(app, (140, 40), steps) == []


def test_wide_terminal_has_two_columns(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        feed, side = app.query_one("#feed"), app.query_one("#side")
        return tui.shown(feed), tui.shown(side), side.region.x >= feed.region.right, \
            side.region.y == feed.region.y

    assert run(app, (140, 40), steps) == (True, True, True, True)


def test_narrow_terminal_has_one_column(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.shown(app.query_one("#feed")), tui.shown(app.query_one("#side")), \
            app.query_one("#feed").region.width, app.size.width

    shown_feed, shown_side, width, screen = run(app, (100, 40), steps)
    assert shown_feed is True
    assert shown_side is False
    assert width == screen


def test_border_width_is_119_narrow_and_120_wide(registry, tmp_path, tui):
    async def steps(app, pilot):
        return tui.shown(app.query_one("#side"))

    narrow, _ = tui.app(registry, tmp_path / "a")
    wide, _ = tui.app(registry, tmp_path / "b")
    assert run(narrow, (119, 40), steps) is False
    assert run(wide, (120, 40), steps) is True


def test_f2_shows_side_panel_in_narrow_terminal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.shown(app.query_one("#side"))
        await pilot.press("f2")
        await pilot.pause()
        return before, tui.shown(app.query_one("#side")), tui.shown(app.query_one("#hero"))

    assert run(app, (100, 40), steps) == (False, True, True)


def test_resize_from_wide_to_narrow_rebuilds_layout(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        wide = tui.shown(app.query_one("#side")), app.query_one("#feed").region.width
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        narrow = tui.shown(app.query_one("#side")), app.query_one("#feed").region.width
        return wide, narrow

    wide, narrow = run(app, (140, 40), steps)
    assert wide[0] is True
    assert narrow[0] is False
    assert narrow[1] > wide[1]


def test_resize_from_narrow_to_wide_rebuilds_layout(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.resize_terminal(140, 40)
        await pilot.pause()
        feed, side = app.query_one("#feed"), app.query_one("#side")
        return tui.shown(side), side.region.x >= feed.region.right

    assert run(app, (100, 40), steps) == (True, True)


def no_art_place(game):
    from ai_dm.game.scene import hero_of
    from ai_dm.state.world import Location

    game.bundle.world.locations["no_art"] = Location(id="no_art", name="Пустошь")
    hero_of(game.bundle).location_id = "no_art"


def test_picture_place_is_hidden_without_picture_in_wide(registry, tmp_path, tui):
    # P6: у стартовой локации героя рисунок есть, поэтому переносим героя в локацию без рисунка
    app, game = tui.app(registry, tmp_path)
    no_art_place(game)

    async def steps(app, pilot):
        return tui.shown(app.query_one("#side")), tui.shown(app.query_one("#picture"))

    assert run(app, (140, 40), steps) == (True, False)


def test_picture_place_is_hidden_without_picture_in_narrow_side_panel(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)
    no_art_place(game)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        return tui.shown(app.query_one("#side")), tui.shown(app.query_one("#picture"))

    assert run(app, (100, 40), steps) == (True, False)


def test_input_status_and_footer_are_shown_in_both_sizes(registry, tmp_path, tui):
    async def steps(app, pilot):
        return [tui.shown(app.query_one(sel)) for sel in ("#input", "#status", Footer)]

    wide, _ = tui.app(registry, tmp_path / "a")
    narrow, _ = tui.app(registry, tmp_path / "b")
    assert run(wide, (140, 40), steps) == [True, True, True]
    assert run(narrow, (100, 40), steps) == [True, True, True]


def test_input_has_focus_after_start(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#input").has_focus

    assert run(app, (140, 40), steps) is True


# К0-фикс, 38 г: F2 в широком окне прячет и возвращает #side; смена режима сбрасывает ручное F2

def test_f2_hides_side_panel_in_wide_terminal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        side = app.query_one("#side")
        before = tui.shown(side), app.query_one("#feed").region.width
        await pilot.press("f2")
        await pilot.pause()
        after = tui.shown(side), app.query_one("#feed").region.width
        return before, after

    before, after = run(app, (140, 40), steps)
    assert before[0] is True
    assert after[0] is False
    assert after[1] > before[1]


def test_second_f2_in_wide_terminal_shows_side_panel_again(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        widths = [app.query_one("#feed").region.width]
        for _ in range(2):
            await pilot.press("f2")
            await pilot.pause()
        widths.append(app.query_one("#feed").region.width)
        return tui.shown(app.query_one("#side")), widths

    shown, widths = run(app, (140, 40), steps)
    assert shown is True
    assert widths[0] == widths[1]


def test_f2_in_wide_terminal_does_not_use_open_class(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        side = app.query_one("#side")
        return side.has_class("closed"), side.has_class("open")

    assert run(app, (140, 40), steps) == (True, False)


def test_f2_in_narrow_terminal_does_not_use_closed_class(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        side = app.query_one("#side")
        return side.has_class("open"), side.has_class("closed")

    assert run(app, (100, 40), steps) == (True, False)


def test_resize_to_narrow_clears_manual_f2_of_wide_mode(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        side = app.query_one("#side")
        narrow = tui.shown(side), side.has_class("closed")
        await pilot.resize_terminal(140, 40)
        await pilot.pause()
        return narrow, tui.shown(side), side.has_class("closed")

    narrow, wide_shown, wide_closed = run(app, (140, 40), steps)
    assert narrow == (False, False)
    assert wide_shown is True
    assert wide_closed is False


def test_resize_to_wide_clears_manual_f2_of_narrow_mode(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        await pilot.resize_terminal(140, 40)
        await pilot.pause()
        side = app.query_one("#side")
        wide = tui.shown(side), side.has_class("open")
        await pilot.resize_terminal(100, 40)
        await pilot.pause()
        return wide, tui.shown(side), side.has_class("open")

    wide, narrow_shown, narrow_open = run(app, (100, 40), steps)
    assert wide == (True, False)
    assert narrow_shown is False
    assert narrow_open is False


def test_resize_inside_the_same_mode_keeps_manual_f2(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        await pilot.resize_terminal(150, 40)
        await pilot.pause()
        return tui.shown(app.query_one("#side")), app.query_one("#side").has_class("closed")

    assert run(app, (140, 40), steps) == (False, True)


def test_resize_exactly_to_120_columns_is_a_mode_change_and_clears_f2(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("f2")
        await pilot.pause()
        await pilot.resize_terminal(120, 40)
        await pilot.pause()
        side = app.query_one("#side")
        return app.has_class("wide"), side.has_class("open"), tui.shown(side)

    assert run(app, (100, 40), steps) == (True, False, True)
