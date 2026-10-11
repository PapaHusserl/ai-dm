# Живой прогон 1, п. 10-11: подсказка команд (Tab) и окно выбора заклинания по /spells.
# Заклинатель -- настоящий Грей (следопыт 3 ур., кампания drunk_dragon), не подмена spell_rows.
# Метка охотника, Лечение ран, Опутывающий удар, Разговор с животными, Туманное облако.
import asyncio
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import (  # noqa: E402
    ReactiveAdapter,
    make_app,
    script_then_react,
    start_combat_call,
    text_step,
    tools_step,
)

from ai_dm.campaign.loader import load_pack, pack_content_dir  # noqa: E402
from ai_dm.content.loader import load_registry  # noqa: E402
from ai_dm.game import combat_flow  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.starter import new_world_from_pack  # noqa: E402
from ai_dm.state.creature import ResourcePool  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.modals import SpellModal, TextModal  # noqa: E402

DRAGON = Path(__file__).resolve().parents[4] / "campaigns" / "drunk_dragon"
HUNTERS_MARK = "Метка охотника"
CURE = "Лечение ран"
FOG = "Туманное облако"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


def grey_game(cfg, tmp_path, adapter=None):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, adapter or ReactiveAdapter(), bundle=bundle)


def combat_game(cfg, tmp_path):
    call = start_combat_call()
    call["input"]["enemies"] = [
        {"ref": "g1", "monster_id": "goblin_warrior", "zone": "hall", "group": "goblins"}
    ]
    steps = [tools_step(call), text_step("Гоблин бросается на вас.")]
    return grey_game(cfg, tmp_path, script_then_react(steps))


async def open_spells(tui, app, pilot):
    await tui.submit(app, pilot, "/spells")


async def start_fight(tui, app, pilot):
    await tui.submit(app, pilot, "Бью ногой дверь")
    assert app.game.bundle.session.active_combat is not None


def option_texts(app):
    menu = app.screen.query_one("#spell-list")
    return [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]


# подсказка команд

def test_tab_completes_command_from_prefix(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = "/sp"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        return entry.value

    assert run(app, steps) == "/spells"


def test_right_arrow_completes_command_from_prefix(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = "/sp"
        await pilot.pause()
        await pilot.press("right")
        await pilot.pause()
        return entry.value

    assert run(app, steps) == "/spells"


def test_ordinary_text_gets_no_completion(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = "Иду"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        return entry.value

    assert run(app, steps) == "Иду"


def test_every_help_command_is_suggested(registry, tmp_path, tui):
    from ai_dm.game.commands import HELP

    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        found = []
        for name in HELP:
            entry = app.query_one("#input")
            entry.value = "/" + name[:1]
            await pilot.pause()
            found.append(entry._suggestion.startswith("/") or entry.value == "/" + name)
        return found

    assert all(run(app, steps))


# окно /spells вне боя

def test_spells_opens_selection_window_for_a_caster(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        return len(app.screen_stack), isinstance(app.screen, SpellModal), option_texts(app)

    depth, is_spell, texts = run(app, steps)
    assert (depth, is_spell) == (2, True)
    assert len(texts) == 5
    assert texts[0] == f"1. {HUNTERS_MARK}"
    assert texts[1] == f"2. {CURE}"


def test_spells_window_shows_description_of_highlighted_spell(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        first = tui.flat(str(app.screen.query_one("#spell-description").render()))
        seen = []
        for _ in range(2):
            await pilot.press("down")
            await pilot.pause()
            seen.append(tui.flat(str(app.screen.query_one("#spell-description").render())))
        return first, seen

    first, seen = run(app, steps)
    assert "помечаете существо" in first
    assert any("2d8" in text for text in seen)


def test_spells_digit_outside_combat_sends_cast_line(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("2")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app), before, game.bundle.session.turn_seq

    depth, text, before, after = run(app, steps)
    assert depth == 1
    assert f"▸ Ты: Применяю заклинание «{CURE}»." in text
    assert after == before + 1


def test_spells_enter_picks_highlighted_spell(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert f"Применяю заклинание «{HUNTERS_MARK}»." in text


def test_spells_click_picks_spell(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        for y, row in enumerate(tui.screen_rows(app)):
            column = row.find(f"2. {CURE}")
            if column >= 0:
                await pilot.click(offset=(column + 3, y))
                break
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert f"Применяю заклинание «{CURE}»." in text


def test_spells_escape_closes_without_cast(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await pilot.press("escape")
        await pilot.pause()
        return (
            len(app.screen_stack), feed(tui, app), before, game.bundle.session.turn_seq,
            app.query_one("#input").has_focus,
        )

    depth, text, before, after, focus = run(app, steps)
    assert depth == 1
    assert "Применяю" not in text
    assert after == before
    assert focus is True


def test_spells_digit_out_of_range_changes_nothing(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        await pilot.press("9")
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 2
    assert "Применяю" not in text


def test_spell_without_slot_is_not_selectable(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    hero_of(game.bundle).creature.resources["spell_slot:1"].current = 0
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        texts = option_texts(app)
        await pilot.press("2")
        await pilot.pause()
        return texts, len(app.screen_stack), feed(tui, app)

    texts, depth, text = run(app, steps)
    assert texts[1] == f"2. {CURE} — нет ячейки"
    assert depth == 2
    assert "Применяю" not in text


def test_hunters_mark_without_slots_but_with_free_use_is_selectable(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    resources = hero_of(game.bundle).creature.resources
    resources["spell_slot:1"].current = 0
    assert resources["favored_enemy"].current > 0
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        texts = option_texts(app)
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return texts, len(app.screen_stack), feed(tui, app)

    texts, depth, text = run(app, steps)
    assert texts[0] == f"1. {HUNTERS_MARK}"
    assert depth == 1
    assert f"Применяю заклинание «{HUNTERS_MARK}»." in text


def test_non_caster_gets_plain_reference_window(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/spells")
        return len(app.screen_stack), isinstance(app.screen, SpellModal), \
            isinstance(app.screen, TextModal)

    assert run(app, steps) == (2, False, True)


# окно /spells в бою

def test_in_combat_spell_pick_sends_menu_number(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        options = game.runner.preview_turn()
        number = next(i for i, o in enumerate(options, 1) if o.kind == "cast")
        label = options[number - 1].label
        await open_spells(tui, app, pilot)
        rows = app.screen.rows
        picked = next(r for r in rows if r[2])
        await pilot.press(str(rows.index(picked) + 1))
        await app.workers.wait_for_complete()
        await pilot.pause()
        return number, label, picked, feed(tui, app), len(app.screen_stack)

    number, label, picked, text, depth = run(app, steps)
    assert depth == 1
    assert picked[3] == str(number)
    assert f"▸ Ты: {number}. {label}" in text


def test_in_combat_inert_spells_are_listed_but_not_selectable(cfg, tmp_path, tui):
    from ai_dm.ui.format import INERT_NOTE

    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await open_spells(tui, app, pilot)
        rows = list(app.screen.rows)
        index = next(i for i, r in enumerate(rows) if r[0].startswith(FOG))
        turn_before = game.bundle.session.turn_seq
        await pilot.press(str(index + 1))
        await pilot.pause()
        return rows[index], len(app.screen_stack), turn_before, game.bundle.session.turn_seq

    row, depth, before, after = run(app, steps)
    assert INERT_NOTE in row[0]
    assert row[2] is False
    assert depth == 2
    assert after == before


def test_in_combat_escape_casts_nothing(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = game.bundle.session.turn_seq
        await open_spells(tui, app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), before, game.bundle.session.turn_seq

    depth, before, after = run(app, steps)
    assert depth == 1
    assert after == before


# ревью: решения проектировщика 3, 4, 5

def test_tab_without_suggestion_moves_focus_away_from_input(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = "Иду"
        await pilot.pause()
        await pilot.press("tab")
        await pilot.pause()
        return entry.value, app.focused is entry

    assert run(app, steps) == ("Иду", False)


def test_spell_is_selectable_outside_combat_with_slot_of_higher_circle(cfg, tmp_path):
    from ai_dm.ui.tui.blocks import spell_rows

    game = grey_game(cfg, tmp_path)
    resources = hero_of(game.bundle).creature.resources
    resources["spell_slot:1"].current = 0
    resources["spell_slot:2"] = ResourcePool(current=1, max=1)
    row = next(r for r in spell_rows(game) if r[0].startswith(CURE))
    assert row[2] is True
    assert row[3] == f"Применяю заклинание «{CURE}»."


def test_spell_without_any_slot_is_still_not_selectable(cfg, tmp_path):
    from ai_dm.ui.tui.blocks import spell_rows

    game = grey_game(cfg, tmp_path)
    resources = hero_of(game.bundle).creature.resources
    for key in list(resources):
        if key.startswith("spell_slot:"):
            resources[key].current = 0
    row = next(r for r in spell_rows(game) if r[0].startswith(CURE))
    assert row[2] is False


def test_preview_screen_matches_separate_previews(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(combat_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        runner = app.game.runner
        options, turn, inert = runner.preview_screen()
        return (
            [o.id for o in options] == [o.id for o in runner.preview_turn()],
            turn == combat_flow.preview_turn(runner.bundle, runner.registry, runner.cfg)[1],
            inert == runner.inert_spells(),
        )

    assert run(app, steps) == (True, True, True)
