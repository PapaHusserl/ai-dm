# Этап 5, P6 (STAGE5-P6-PLAN, п. 2, 7; ответы В-2, В-4). Ожидаемое поведение (ТРЕБОВАНИЕ к коду):
#   1. при старте TUI заставка (art_for_event("title")) стоит в ленте #feed (до строк старта); в
#      #picture её нет: она шире панели (<= 76 против 58), там рисунки локаций/монстров/событий;
#   2. после хода в #picture -- рисунок локации героя (art_for_location); та же локация --
#      без замены;
#      в ленту рисунки локаций не дублируются;
#   3. (Р-2) старт боя -- рисунок первого живого врага (art_for_monster) один раз на бой в ЛЕНТУ
#      #feed; на следующих ходах боя не повторяется; #picture в бою скрыт, после боя -- локация;
#   4. узкий режим (< 120): #picture в выдвижной колонке (F2); ничего в ленту не дублируется;
#   5. рисунок не обрезан и не переносится: каждая его строка целиком в одной строке экрана,
#      при 100 (после F2) и 140 колонках;
#   6. #picture скрыт, пока рисунка нет.
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from ui_kit import DESCEND, TALK, scene_app  # noqa: E402

from ai_dm.art import art_for_event, art_for_location, art_for_monster  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def rows_of(art):
    return [line.rstrip() for line in art.splitlines() if line.strip()]


def inside(art, text):
    return [row for row in rows_of(art) if row not in text]


def hero_place(app):
    world = app.game.bundle.world
    return world.locations[hero_of(app.game.bundle).location_id]


def fight_app(registry, tmp_path):
    game, _ = scene_app(registry, tmp_path, hp=200)
    return AiDmApp(PlaySession(game))


def first_enemy_monster(app, registry):
    combat = app.game.bundle.session.active_combat
    for one in combat.participants:
        if one.side == "enemies" and one.status == "active":
            return registry.get("monster", one.monster_id)
    return None


async def start_fight(tui, app, pilot):
    await tui.submit(app, pilot, TALK)
    await tui.submit(app, pilot, "1")
    await tui.submit(app, pilot, DESCEND)


# заставка

def test_title_is_in_feed_at_start(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.text_of(app.query_one("#feed"))

    assert inside(art_for_event("title"), run(app, steps)) == []


def test_title_is_in_feed_at_start_in_narrow(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.text_of(app.query_one("#feed"))

    assert inside(art_for_event("title"), run(app, steps, size=(100, 40))) == []


def test_title_is_whole_on_screen_in_wide(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.visible_text(app)

    assert inside(art_for_event("title"), run(app, steps)) == []


def test_title_stands_before_startup_lines_in_feed(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)
    app.startup.append("Строка старта")

    async def steps(app, pilot):
        return tui.text_of(app.query_one("#feed"))

    text = run(app, steps)
    assert text.index(rows_of(art_for_event("title"))[0]) < text.index("Строка старта")


# рисунок локации

def test_picture_shows_location_drawing_after_turn(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#picture")), tui.text_of(app.query_one("#picture")), \
            hero_place(app)

    shown, text, place = run(app, steps)
    art = art_for_location(place)
    assert art is not None
    assert shown is True
    assert inside(art, text) == []


def test_location_drawing_replaces_title_in_picture(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.text_of(app.query_one("#picture"))

    text = run(app, steps)
    assert rows_of(art_for_event("title"))[0] not in text.splitlines()


def test_location_drawing_is_whole_on_screen_in_wide(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.visible_text(app), hero_place(app)

    text, place = run(app, steps)
    assert inside(art_for_location(place), text) == []


def test_location_drawing_is_whole_on_screen_in_narrow_side_panel(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        return tui.visible_text(app), hero_place(app)

    text, place = run(app, steps, size=(100, 40))
    assert inside(art_for_location(place), text) == []


def test_location_drawing_is_not_written_to_feed(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.text_of(app.query_one("#feed")), hero_place(app)

    feed, place = run(app, steps)
    art = rows_of(art_for_location(place))
    title = set(rows_of(art_for_event("title")))
    assert [row for row in art if row in feed and row not in title] == []


def test_same_location_keeps_picture_on_next_turn(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        first = tui.text_of(app.query_one("#picture"))
        await tui.submit(app, pilot)
        return first, tui.text_of(app.query_one("#picture")), tui.shown(app.query_one("#picture"))

    first, second, shown = run(app, steps)
    assert first == second
    assert shown is True


def test_picture_in_narrow_mode_is_hidden_until_f2(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        before = tui.shown(app.query_one("#picture"))
        await pilot.press("f2")
        await pilot.pause()
        return before, tui.shown(app.query_one("#picture"))

    assert run(app, steps, size=(100, 40)) == (False, True)


# бой (Р-2)

def monster_in_feed(tui, app, enemy):
    return tui.text_of(app.query_one("#feed")).count(rows_of(art_for_monster(enemy))[0])


def test_fight_start_writes_first_enemy_drawing_to_feed(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return tui.text_of(app.query_one("#feed")), first_enemy_monster(app, registry)

    feed, enemy = run(app, steps)
    art = art_for_monster(enemy)
    assert art is not None
    assert inside(art, feed) == []


def test_enemy_drawing_is_written_once_per_fight(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        enemy = first_enemy_monster(app, registry)
        first = monster_in_feed(tui, app, enemy)
        await tui.submit(app, pilot, str(len(app.game.runner.preview_turn())))
        return first, monster_in_feed(tui, app, enemy), \
            app.game.bundle.session.active_combat is not None

    first, second, fighting = run(app, steps)
    assert fighting is True
    assert first == 1
    assert second == 1


def test_picture_is_hidden_during_fight(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        first = tui.shown(app.query_one("#picture"))
        await tui.submit(app, pilot, str(len(app.game.runner.preview_turn())))
        return first, tui.shown(app.query_one("#picture"))

    assert run(app, steps) == (False, False)


def test_enemy_drawing_is_not_in_picture(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return tui.text_of(app.query_one("#picture")), first_enemy_monster(app, registry)

    text, enemy = run(app, steps)
    assert rows_of(art_for_monster(enemy))[0] not in text


def test_fight_start_keeps_combat_panels_visible(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        names = ("actions", "combat", "combat-log")
        return [tui.shown(app.query_one(f"#{name}")) for name in names]

    assert run(app, steps) == [True] * 3


def test_enemy_drawing_is_whole_in_feed_in_narrow(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return tui.visible_text(app), first_enemy_monster(app, registry)

    text, enemy = run(app, steps, size=(100, 40))
    assert inside(art_for_monster(enemy), text) == []


# старт

def test_picture_shows_hero_location_drawing_at_start(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.shown(app.query_one("#picture")), tui.text_of(app.query_one("#picture")), \
            hero_place(app)

    shown, text, place = run(app, steps)
    assert shown is True
    assert inside(art_for_location(place), text) == []


# события и возврат локации (show_picture)

def test_event_drawing_goes_to_picture(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["victory"], True)
        await pilot.pause()
        return tui.shown(app.query_one("#picture")), tui.text_of(app.query_one("#picture"))

    shown, text = run(app, steps)
    assert shown is True
    assert inside(art_for_event("victory"), text) == []


def test_event_drawing_is_replaced_by_location_on_next_turn(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["death"], True)
        app.show_picture([], True)
        await pilot.pause()
        return tui.text_of(app.query_one("#picture")), hero_place(app)

    text, place = run(app, steps)
    assert inside(art_for_location(place), text) == []
    assert rows_of(art_for_event("death"))[0] not in text.splitlines()


def test_event_drawing_stays_when_step_is_not_a_game_turn(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["victory"], True)
        app.show_picture([], False)
        await pilot.pause()
        return tui.text_of(app.query_one("#picture"))

    assert inside(art_for_event("victory"), run(app, steps)) == []


def test_location_without_drawing_hides_picture_after_event(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["victory"], True)
        place = no_art_place(game)
        app.show_picture([], True)
        await pilot.pause()
        return tui.shown(app.query_one("#picture")), place

    shown, _ = run(app, steps)
    assert shown is False


def test_picture_kind_after_event_is_event_then_location(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["victory"], True)
        first = app.picture_kind
        app.show_picture([], True)
        return first, app.picture_kind

    assert run(app, steps) == ("event", "location")


def test_picture_kind_without_drawing_after_event_is_none(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_picture(["victory"], True)
        no_art_place(game)
        app.show_picture([], True)
        return app.picture_kind

    assert run(app, steps) is None


def test_location_comes_back_after_fight_ends(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        during = app.picture_kind, tui.shown(app.query_one("#picture"))
        app.game.bundle.session.active_combat = None
        app.show_picture([], True)
        await pilot.pause()
        return during, app.picture_kind, tui.text_of(app.query_one("#picture")), hero_place(app)

    during, kind, text, place = run(app, steps)
    assert during == ("monster", False)
    assert kind == "location"
    assert inside(art_for_location(place), text) == []


def test_picture_stays_hidden_in_fight_after_monster_turn(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        app.show_picture(["level_up"], True)
        app.show_picture([], True)
        await pilot.pause()
        return tui.shown(app.query_one("#picture"))

    assert run(app, steps) is False


def no_art_place(game):
    from ai_dm.state.world import Location

    game.bundle.world.locations["no_art"] = Location(id="no_art", name="Пустошь")
    hero_of(game.bundle).location_id = "no_art"
