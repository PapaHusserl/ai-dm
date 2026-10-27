# Живой прогон 1: граничные случаи новых строк (закрывают выживших мутантов партии).
import asyncio
import sys
import threading
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import OPUS, ReactiveAdapter, text_step  # noqa: E402
from test_tui_spells import combat_game, grey_game, open_spells, option_texts, start_fight  # noqa
from ui_kit import menu_model_app, text_app  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.ui.format import INERT_NOTE, turn_menu_lines  # noqa: E402
from ai_dm.ui.screen import Block, scene_mark, turn_line_block  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.blocks import spell_rows  # noqa: E402

TURN = SimpleNamespace(action=True, attacks_left=0, bonus=True, move=30, reaction=True)
OPTIONS = [
    SimpleNamespace(id="dash", kind="dash", params={}, cost="action", label="Атака мечом"),
    SimpleNamespace(id="dodge", kind="dodge", params={}, cost="bonus", label="Метка охотника"),
]


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


# turn_menu_lines

def test_turn_menu_shows_armor_class_in_resources_line():
    assert "КД 15" in " ".join(turn_menu_lines(OPTIONS, TURN, 80, ac="КД 15"))


def test_turn_menu_effects_and_concentration_are_separate_indented_lines():
    lines = turn_menu_lines(
        OPTIONS, TURN, 80, concentration="Концентрация: Метка", effects="Эфф: X"
    )
    effects = next(x for x in lines if "Эфф: X" in x)
    concentration = next(x for x in lines if "Концентрация: Метка" in x)
    assert effects.startswith("  ") and not effects.startswith("   ")
    assert concentration.startswith("  ") and not concentration.startswith("   ")
    assert effects != concentration
    assert any("Твой ход" in x for x in lines)


def test_turn_menu_long_effects_wrap_with_four_space_indent():
    lines = turn_menu_lines(OPTIONS, TURN, 30, effects="Эффект " + "длинный " * 8)
    wrapped = [x for x in lines if "длинный" in x]
    assert len(wrapped) > 1
    assert all(x.startswith("    ") for x in wrapped[1:])


def test_turn_menu_long_label_wraps_under_the_text():
    options = [
        SimpleNamespace(cost="action", kind="attack", label="Очень длинная подпись варианта " * 3)
    ]
    lines = turn_menu_lines(options, TURN, 40)
    at = next(i for i, x in enumerate(lines) if x.strip().startswith("1."))
    assert lines[at + 1].startswith(" " * len("    1. ")) and lines[at + 1].strip()


def test_turn_menu_cost_group_title_is_printed_once_per_group():
    options = [
        SimpleNamespace(cost="action", kind="attack", label=f"Вариант {n}") for n in range(3)
    ]
    lines = turn_menu_lines(options, TURN, 80)
    assert len([x for x in lines if x.strip().endswith(":") and "Действие" in x]) == 1


def test_inert_line_indent_and_wrap_indent():
    lines = turn_menu_lines(OPTIONS, TURN, 24, inert=("Очень длинное название",))
    first = next(x for x in lines if "Очень" in x)
    at = lines.index(first)
    assert first.startswith("    ") and not first.startswith("     ")
    assert INERT_NOTE.split()[-1] in " ".join(lines[at:])
    assert lines[at + 1].startswith("      ")


# scene_mark, turn_line_block

def test_scene_mark_without_scene_is_none_and_empty(registry, tmp_path):
    game = text_app(registry, tmp_path, [text_step()])
    game.bundle.session.current_scene = None
    assert scene_mark(game) == (None, "")


def test_scene_mark_without_known_place_is_scene_number(registry, tmp_path):
    game = text_app(registry, tmp_path, [text_step()])
    game.bundle.session.current_scene.location_id = "нет_такого_места"
    scene_id, title = scene_mark(game)
    assert title == "Сцена " + scene_id.removeprefix("scene_")
    assert title.startswith("Сцена ") and title[6:].isdigit()


def test_turn_line_block_roll_and_note_carry_combat_flag():
    turn = SimpleNamespace(rolls=["бросок"])
    assert turn_line_block("бросок", turn, True).combat is True
    assert turn_line_block("бросок", turn).combat is False
    assert turn_line_block("лог", turn, True).combat is True
    assert turn_line_block("лог", turn).combat is False
    assert turn_line_block("бросок", turn).kind == "roll"
    assert turn_line_block("лог", turn).kind == "note"


# TUI: орнамент, рамка, лог боя

def test_ornament_between_two_replies_even_without_narration(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.write_echo("Раз")
        app.write_echo("Два")
        return [x.strip() for x in tui.text_of(app.query_one("#feed")).splitlines() if x.strip()]

    # P6: до реплик в ленте стоит заставка, проверяем хвост ленты
    assert run(app, steps)[-3:] == ["▸ Ты: Раз", "✦ ─── ✦", "▸ Ты: Два"]


def test_narration_frame_has_one_space_padding(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.write_narration("Огонь.")
        return [x.strip() for x in tui.text_of(app.query_one("#feed")).splitlines()]

    assert any(x.startswith("│ Огонь.") for x in run(app, steps))


def test_combat_log_stays_while_command_is_run_in_combat(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        app.show_blocks([Block("note", text="Справка")], refresh=False)
        await pilot.pause()
        return app.combat_log_shown, tui.shown(app.query_one("#combat-log"))

    assert run(app, steps) == (True, True)


def test_turn_menu_block_alone_turns_combat_log_on(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        block = Block("turn_menu", items=tuple(OPTIONS), args=(TURN, "", "", "", (), ()))
        app.show_blocks([block], refresh=True)
        await pilot.pause()
        return app.combat_log_shown

    assert run(app, steps) is True


# окно модели

def blocking_factory(release):
    def factory(provider, model):
        assert release.wait(10)
        return ReactiveAdapter(provider=provider, model=model)

    return factory


def test_model_switch_blocks_input_until_done_then_unblocks(registry, tmp_path, tui):
    release = threading.Event()
    game = text_app(
        registry, tmp_path, [text_step("Раз.")], adapter_factory=blocking_factory(release)
    )
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model")
        await pilot.press("2")
        await pilot.pause()
        during = (
            app.busy, app.query_one("#input").disabled, tui.text_of(app.query_one("#status")),
        )
        release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        after = (
            app.busy, app.query_one("#input").disabled, app.query_one("#input").has_focus,
            tui.text_of(app.query_one("#status")),
        )
        return during, after

    during, after = run(app, steps)
    assert during[0] is True and during[1] is True
    assert strings.THINKING in during[2]
    assert after[:3] == (False, False, True)
    assert strings.THINKING not in after[3]


def test_model_window_marks_only_current_and_has_title(registry, tmp_path, tui):
    game = menu_model_app(registry, tmp_path, [text_step()])
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model")
        menu = app.screen.query_one("#model-list")
        texts = [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]
        return texts, app.screen.query_one("#modal").border_title

    texts, title = run(app, steps)
    assert len([x for x in texts if "(текущая)" in x]) == 1
    assert title == strings.MODAL_TITLES["/model"]


def test_model_window_current_model_outside_config_is_not_marked(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step()])
    assert f"anthropic:{OPUS}" not in game.model_options()
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model")
        menu = app.screen.query_one("#model-list")
        return [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]

    texts = run(app, steps)
    assert texts
    assert not [x for x in texts if "(текущая)" in x]


def test_model_window_last_digit_picks_last_model(registry, tmp_path, tui):
    from game_kit import FactorySpy

    spy = FactorySpy()
    game = text_app(registry, tmp_path, [text_step()], adapter_factory=spy)
    last = game.model_options()[-1]
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model")
        await pilot.press(str(len(game.model_options())))
        await app.workers.wait_for_complete()
        await pilot.pause()

    run(app, steps)
    assert spy.calls == [tuple(last.split(":", 1))]


# окно заклинаний

def test_spell_window_has_title_and_last_digit_picks_last_spell(cfg, tmp_path, tui):
    app = AiDmApp(PlaySession(grey_game(cfg, tmp_path)))

    async def steps(app, pilot):
        await open_spells(tui, app, pilot)
        title = app.screen.query_one("#modal").border_title
        count = len(option_texts(app))
        await pilot.press(str(count))
        await app.workers.wait_for_complete()
        await pilot.pause()
        return title, len(app.screen_stack), tui.flat(tui.text_of(app.query_one("#feed")))

    title, depth, text = run(app, steps)
    assert title == strings.MODAL_TITLES["/spells"]
    assert depth == 1
    assert "Применяю заклинание «Туманное облако»." in text


def test_spells_with_pending_error_menu_gives_plain_reference(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        game.pending = "error_menu"
        await tui.submit(app, pilot, "/spells")
        return type(app.screen).__name__

    assert run(app, steps) == "TextModal"


def test_spells_with_limit_menu_gives_plain_reference(cfg, tmp_path, tui):
    game = grey_game(cfg, tmp_path)
    session = PlaySession(game)
    app = AiDmApp(session)

    async def steps(app, pilot):
        session.limit_menu = True
        await tui.submit(app, pilot, "/spells")
        return type(app.screen).__name__

    assert run(app, steps) == "TextModal"


# spell_rows

def test_spell_with_one_slot_left_is_selectable(cfg, tmp_path):
    game = grey_game(cfg, tmp_path)
    hero_of(game.bundle).creature.resources["spell_slot:1"].current = 1
    rows = {r[0]: r for r in spell_rows(game)}
    assert rows["Лечение ран"][2] is True


def test_spell_without_slot_row_has_empty_turn_and_echo(cfg, tmp_path):
    game = grey_game(cfg, tmp_path)
    hero_of(game.bundle).creature.resources["spell_slot:1"].current = 0
    row = next(r for r in spell_rows(game) if r[0].startswith("Лечение ран"))
    assert (row[2], row[3], row[4]) == (False, "", "")
    assert strings.SPELL_NO_SLOT in row[0]


def test_spell_rows_outside_combat_carry_cast_line_as_turn_and_echo(cfg, tmp_path):
    row = next(r for r in spell_rows(grey_game(cfg, tmp_path)) if r[0] == "Лечение ран")
    assert row[3] == row[4] == "Применяю заклинание «Лечение ран»."


def test_in_combat_rows_have_no_duplicates_and_unavailable_rows_have_no_turn(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        casts = [o for o in game.runner.preview_turn() if o.kind == "cast"]
        return spell_rows(game), len(casts), len({o.params["spell"] for o in casts})

    rows, casts, spells = run(app, steps)
    assert len([r for r in rows if r[2]]) == casts
    assert len(rows) == casts + (5 - spells)
    for row in rows:
        if not row[2]:
            assert (row[3], row[4]) == ("", "")
        else:
            assert row[3].isdigit() and row[4].startswith(row[3] + ". ")


def test_in_combat_castable_spell_without_slot_is_busy_not_inert(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        hero_of(game.bundle).creature.resources["spell_slot:1"].current = 0
        return spell_rows(game)

    rows = run(app, steps)
    cure = next(r for r in rows if r[0].startswith("Лечение ран"))
    fog = next(r for r in rows if r[0].startswith("Туманное облако"))
    assert strings.SPELL_BUSY in cure[0] and INERT_NOTE not in cure[0]
    assert INERT_NOTE in fog[0]


def test_spell_chosen_in_combat_submits_menu_number_not_echo(cfg, tmp_path, tui):
    game = combat_game(cfg, tmp_path)
    app = AiDmApp(PlaySession(game))

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        sent = []
        app.start_turn = sent.append
        row = next(r for r in spell_rows(game) if r[2])
        app.spell_chosen(row)
        return sent, row

    sent, row = run(app, steps)
    assert sent == [row[3]]
    assert sent != [row[4]]
