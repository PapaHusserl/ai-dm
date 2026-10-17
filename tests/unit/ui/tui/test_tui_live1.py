# Этап 5, живой прогон 1 (docs/plan-stage5.md). Ожидаемое поведение (ТРЕБОВАНИЕ к коду):
#   1. при смене сцены в ленту #feed пишется "─── <название места новой сцены> ───"
#      (нет места -- "Сцена N"); первую сцену не отмечаем;
#      простой режим не меняется (разделителя в его выводе нет);
#   2. в 140x40 правая колонка #side шире 46, «Бой» и «Броски» выше листа героя #hero;
#   3. /model без аргументов -- окно-выбор (ModalScreen, пункты "<n>. <provider:model>" из
#      game.model_options()): цифра, клик по пункту или Enter (подсвечена текущая) -> set_narrator,
#      окно закрывается, результат строкой в ленту ("Модель рассказчика: <key>." или текст ошибки);
#      Esc закрывает окно без смены. Точные id новых виджетов согласовать с кодом kaban.
import asyncio
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import (  # noqa: E402
    OPUS,
    FactorySpy,
    end_scene_call,
    text_step,
    tools_step,
)
from summarizer_kit import summ_steps  # noqa: E402
from ui_kit import DESCEND, TALK, play, scene_app, text_app  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.llm.errors import MissingKey  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402

OLD_SIDE_WIDTH = 46
SEPARATOR = "───"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def tui_of(game):
    return AiDmApp(PlaySession(game))


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


def feed_lines(tui, app):
    return [line for line in tui.text_of(app.query_one("#feed")).splitlines() if line.strip()]


def separators(tui, app):
    # разделитель сцен целиком "─── <место> ───"; рамки рассказа и орнамент сюда не попадают
    return [x for x in feed_lines(tui, app) if re.fullmatch(r"─── [^─]+ ───", x.strip())]


# 1. разделитель сцен

def scene_change_app(registry, tmp_path, title):
    from slots_kit import WORLD_TEXT  # noqa: F401  (мир тот же, что в text_app)

    narrator = [tools_step(end_scene_call(summary="Итог.")), text_step("Конец сцены.")]
    game = text_app(registry, tmp_path, narrator)
    # make_app подменяет сессию summarizer заглушкой; нужна настоящая, с моком summarizer
    del game.runner.new_summarizer_session
    game.runner.summarizer_adapter = ScriptedAdapter(
        summ_steps("Итог сцены.", title=title), provider="anthropic", model=OPUS
    )
    return tui_of(game)


def test_scene_change_writes_separator_with_scene_title_to_feed(registry, tmp_path, tui):
    app = scene_change_app(registry, tmp_path, "Подвал таверны")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        hero = hero_of(app.game.bundle)
        return feed_lines(tui, app), app.game.bundle.world.locations[hero.location_id].name

    lines, place = run(app, steps)
    found = [line.strip() for line in lines if line.strip() == f"{SEPARATOR} {place} {SEPARATOR}"]
    assert len(found) == 1


def test_no_separator_in_feed_without_scene_change(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return separators(tui, app)

    assert run(app, steps) == []


def test_separator_is_written_once_per_scene_change(registry, tmp_path, tui):
    app = scene_change_app(registry, tmp_path, "Подвал таверны")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "/help")
        return len(separators(tui, app))

    assert run(app, steps) == 1


def test_simple_mode_output_has_no_scene_separator(registry, tmp_path):
    narrator = [tools_step(end_scene_call(summary="Итог.")), text_step("Конец сцены.")]
    game = text_app(registry, tmp_path, narrator)
    del game.runner.new_summarizer_session
    game.runner.summarizer_adapter = ScriptedAdapter(
        summ_steps("Итог сцены.", title="Подвал таверны"), provider="anthropic", model=OPUS
    )
    assert SEPARATOR not in play(game, ["Иду"]).text


# 2. раскладка

def fight_app(registry, tmp_path):
    game, _ = scene_app(registry, tmp_path, hp=200)
    return tui_of(game)


async def start_fight(tui, app, pilot):
    await tui.submit(app, pilot, TALK)
    await tui.submit(app, pilot, "1")
    await tui.submit(app, pilot, DESCEND)


def test_side_column_is_wider_than_before_in_wide_mode(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#side").region.width

    assert run(app, steps) > OLD_SIDE_WIDTH


def test_combat_and_combat_log_are_taller_than_hero_in_wide_mode(registry, tmp_path, tui):
    # в бою на месте «Бросков» виден #combat-log
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        names = ("hero", "combat", "combat-log")
        return [app.query_one(f"#{name}").region.height for name in names]

    hero, combat, log = run(app, steps)
    assert combat > hero
    assert log > hero


def test_rolls_are_taller_than_hero_before_any_fight(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#rolls").region.height, app.query_one("#hero").region.height

    rolls, hero = run(app, steps)
    assert rolls > hero


def test_narrow_f2_shows_combat_and_combat_log_in_fight(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        names = ("side", "hero", "actions", "combat", "combat-log")
        return [tui.shown(app.query_one(f"#{name}")) for name in names]

    assert run(app, steps, size=(100, 40)) == [True] * 5


# 3. /model окном с выбором

def model_app(registry, tmp_path, error=None):
    spy = FactorySpy(error=error)
    game = text_app(registry, tmp_path, [text_step("Раз.")], adapter_factory=spy)
    return tui_of(game), game, spy


async def open_model(tui, app, pilot):
    await tui.submit(app, pilot, "/model")


async def click_modal_item(tui, app, pilot, number):
    # клик по пункту «<number>. ...»: координаты берём с экрана
    for y, row in enumerate(tui.screen_rows(app)):
        column = row.find(f"{number}. ")
        if column >= 0:
            await pilot.click(offset=(column + 3, y))
            await app.workers.wait_for_complete()
            await pilot.pause()
            return
    raise AssertionError("пункта нет на экране")


def test_model_window_digit_picks_model_via_set_narrator(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    options = game.model_options()

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("2")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app), app.query_one("#input").has_focus

    depth, text, focus = run(app, steps)
    assert depth == 1
    assert spy.calls == [tuple(options[1].split(":", 1))]
    assert f"Модель рассказчика: {options[1]}." in text
    assert focus is True


def test_model_window_click_picks_model_via_set_narrator(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    options = game.model_options()

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await click_modal_item(tui, app, pilot, 2)
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert spy.calls == [tuple(options[1].split(":", 1))]
    assert f"Модель рассказчика: {options[1]}." in text


def test_model_window_enter_picks_highlighted_current_model(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    current = f"{game.adapter.info().provider}:{game.adapter.info().model}"

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert spy.calls == [tuple(current.split(":", 1))]
    assert f"Модель рассказчика: {current}." in text


def test_model_window_down_enter_picks_next_model(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    options = game.model_options()
    current = f"{game.adapter.info().provider}:{game.adapter.info().model}"
    nxt = options[(options.index(current) + 1) % len(options)]

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("down", "enter")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return feed(tui, app)

    assert f"Модель рассказчика: {nxt}." in run(app, steps)
    assert spy.calls == [tuple(nxt.split(":", 1))]


def test_model_window_lists_all_options_numbered(registry, tmp_path, tui):
    app, game, _ = model_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        return tui.visible_text(app)

    text = run(app, steps)
    for number, key in enumerate(game.model_options(), start=1):
        assert f"{number}. {key}" in text


def test_model_window_escape_closes_without_change(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app), app.query_one("#input").has_focus

    depth, text, focus = run(app, steps)
    assert depth == 1
    assert spy.calls == []
    assert "Модель рассказчика" not in text
    assert focus is True
    assert game.adapter.info().model == OPUS


def test_model_window_digit_out_of_range_changes_nothing(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    count = len(game.model_options())

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press(str(count + 1) if count < 9 else "0")
        await pilot.pause()
        return spy.calls

    assert run(app, steps) == []


def test_model_window_error_goes_to_feed(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path, error=MissingKey("нет ключа GEMINI_API_KEY"))

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("2")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert "нет ключа GEMINI_API_KEY" in text
    assert "Модель рассказчика:" not in text
    assert game.adapter.info().model == OPUS


def test_model_window_model_without_price_goes_to_feed(registry, tmp_path, tui):
    app, game, spy = model_app(registry, tmp_path)
    key = game.model_options()[1]
    del game.settings.app.prices[key.partition(":")[2]]

    async def steps(app, pilot):
        await open_model(tui, app, pilot)
        await pilot.press("2")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert "нет цены" in text
    assert spy.calls == []


# 4-6. панель #actions, прокрутка #combat, невыбираемые заклинания

def actions_blocks(inert):
    from types import SimpleNamespace

    from ai_dm.ui.screen import Block

    turn = SimpleNamespace(action=True, attacks_left=0, bonus=True, move=30, reaction=True)
    options = (
        SimpleNamespace(id="dash", kind="dash", params={}, cost="action", label="Атака мечом"),
        SimpleNamespace(id="dodge", kind="dodge", params={}, cost="action", label="Рывок"),
    )
    return [Block("turn_menu", items=options, args=(turn, "", "КД 15", "", inert, ()))]


def test_battle_options_are_in_actions_panel_visible_in_wide(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        actions = app.query_one("#actions")
        return (
            tui.shown(actions), tui.text_of(actions), tui.text_of(app.query_one("#combat")),
            actions.region.bottom <= app.size.height, tui.visible_text(app),
        )

    shown, actions, combat, inside, screen = run(app, steps)
    assert shown is True
    assert "Закончить ход" in actions
    assert "Закончить ход" not in combat
    assert inside is True
    # варианты на экране (первые; хвост списка длиннее max-height 16 -- в прокрутке панели)
    assert "1. Атака" in screen


def test_actions_panel_is_between_hero_and_combat(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        regions = [app.query_one(f"#{name}").region for name in ("hero", "actions", "combat")]
        return [r.y for r in regions]

    hero, actions, combat = run(app, steps)
    assert hero < actions < combat


def test_actions_panel_is_hidden_outside_battle(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.shown(app.query_one("#actions"))

    assert run(app, steps) is False


def test_actions_panel_has_height_limit_and_scroll(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        actions = app.query_one("#actions")
        return actions.styles.max_height.value, actions.styles.overflow_y

    assert run(app, steps) == (24, "auto")


def test_combat_panel_scrolls(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#combat").styles.overflow_y

    assert run(app, steps) == "auto"


def test_inert_spell_is_shown_in_actions_without_number(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_blocks(actions_blocks(("Сигнал тревоги",)), refresh=True)
        await pilot.pause()
        return tui.text_of(app.query_one("#actions"))

    lines = run(app, steps).splitlines()
    line = next(x for x in lines if "Сигнал тревоги" in x)
    assert "пока недоступно в бою" in line
    assert not line.strip()[0].isdigit()
    assert any(x.strip().startswith("2.") for x in lines)
    # строки меню: 1, 2 и «Ещё…» (3); заклинание без механики номера не получает
    assert not any(x.strip().startswith("4.") for x in lines)


# 7. реплика, орнамент, рассказ в рамке

def echo_app(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path, steps=[text_step("Раз."), text_step("Два.")])
    return app


def test_player_line_is_echoed_with_marker(registry, tmp_path, tui):
    app = echo_app(registry, tmp_path, tui)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        return feed_lines(tui, app)

    assert "▸ Ты: Иду" in [x.strip() for x in run(app, steps)]


def test_first_turn_has_no_ornament_second_has(registry, tmp_path, tui):
    app = echo_app(registry, tmp_path, tui)
    ornament = "✦ ─── ✦"

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        first = tui.text_of(app.query_one("#feed")).count(ornament)
        await tui.submit(app, pilot, "Ещё")
        return first, tui.text_of(app.query_one("#feed")).count(ornament)

    assert run(app, steps) == (0, 1)


def test_ornament_stands_before_the_player_line(registry, tmp_path, tui):
    app = echo_app(registry, tmp_path, tui)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        await tui.submit(app, pilot, "Ещё")
        return [x.strip() for x in feed_lines(tui, app)]

    lines = run(app, steps)
    assert lines.index("▸ Ты: Ещё") - lines.index("✦ ─── ✦") == 1


def test_narration_is_drawn_in_a_rounded_frame(registry, tmp_path, tui):
    app = echo_app(registry, tmp_path, tui)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        return [x.strip() for x in feed_lines(tui, app)]

    lines = run(app, steps)
    at = next(i for i, x in enumerate(lines) if "Раз." in x)
    assert lines[at].startswith("│") and lines[at].endswith("│")
    assert lines[at - 1].startswith("╭") and lines[at + 1].startswith("╰")


def test_long_narration_wraps_inside_the_frame_and_keeps_all_words(registry, tmp_path, tui):
    text = " ".join(f"слово{n}" for n in range(60))
    app, _ = tui.app(registry, tmp_path, steps=[text_step(text)])

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        return tui.text_of(app.query_one("#feed"))

    feed_text = run(app, steps)
    assert " ".join(feed_text.replace("│", " ").split()).count("слово") >= 60
    assert "слово0" in feed_text and "слово59" in feed_text


# 8. лог боя в #combat-log

def test_combat_log_lines_are_not_in_feed_or_rolls(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await tui.submit(app, pilot, str(len(app.game.runner.preview_turn())))
        return (
            tui.text_of(app.query_one("#combat-log")), feed(tui, app),
            tui.text_of(app.query_one("#rolls")),
        )

    log, feed_text, rolls = run(app, steps)
    assert "против КД" in log
    assert "против КД" not in feed_text
    assert "против КД" not in rolls


def test_combat_log_replaces_rolls_during_fight(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.shown(app.query_one("#rolls")), tui.shown(app.query_one("#combat-log"))
        await start_fight(tui, app, pilot)
        during = tui.shown(app.query_one("#rolls")), tui.shown(app.query_one("#combat-log"))
        return before, during, app.combat_log_shown

    before, during, flag = run(app, steps)
    assert before == (True, False)
    assert during == (False, True)
    assert flag is True


def test_combat_log_is_hidden_and_rolls_back_on_turn_outside_combat(registry, tmp_path, tui):
    from ai_dm.ui.screen import Block

    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_blocks([Block("note", text="Атака → промах", combat=True)], refresh=True)
        await pilot.pause()
        during = tui.shown(app.query_one("#combat-log")), tui.shown(app.query_one("#rolls"))
        app.show_blocks([Block("note", text="Тихо.")], refresh=True)
        await pilot.pause()
        after = tui.shown(app.query_one("#combat-log")), tui.shown(app.query_one("#rolls"))
        return during, after, tui.text_of(app.query_one("#combat-log")), app.combat_log_shown

    during, after, text, flag = run(app, steps)
    assert during == (True, False)
    assert after == (False, True)
    assert text.strip() == ""
    assert flag is False


def test_combat_log_has_its_title(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        return app.query_one("#combat-log").border_title

    assert run(app, steps) == "Ход боя"


def test_non_combat_roll_still_goes_to_rolls_and_feed(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.text_of(app.query_one("#rolls")).strip(), tui.shown(app.query_one("#rolls"))

    text, shown = run(app, steps)
    assert shown is True
    assert text != ""


def test_simple_mode_has_no_tui_decorations_and_keeps_roll_lines(registry, tmp_path, tui):
    from slots_kit import ScriptedInput

    from ai_dm.ui.io import CaptureOutput
    from ai_dm.ui.simple import run as simple_run

    game = text_app(registry, tmp_path, tui.TURN_STEPS)
    out = CaptureOutput()
    simple_run(game, ScriptedInput(["Иду"]), out)
    assert "▸" not in out.text
    assert "✦" not in out.text
    assert "Ход боя" not in out.text
    assert "⚄ Убеждение" in out.text


# ревью: решения проектировщика 1, 2, 5

def test_scene_separator_stands_before_narration_of_the_turn_that_changed_scene(
    registry, tmp_path, tui
):
    app = scene_change_app(registry, tmp_path, "Подвал таверны")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return feed_lines(tui, app)

    lines = run(app, steps)
    marks = [i for i, x in enumerate(lines) if re.fullmatch(r"─── [^─]+ ───", x.strip())]
    narration = [i for i, x in enumerate(lines) if "Конец сцены." in x]
    assert len(marks) == 1 and len(narration) == 1
    assert marks[0] < narration[0]


def test_no_roll_of_a_fight_turn_is_written_to_feed(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        await tui.submit(app, pilot, str(len(app.game.runner.preview_turn())))
        rolls = app.game.bundle.memory.recent_turns[-1].rolls
        return rolls, feed(tui, app), tui.flat(tui.text_of(app.query_one("#combat-log")))

    rolls, feed_text, log = run(app, steps)
    assert "против КД" in log
    for roll in rolls:
        assert tui.flat(roll) not in feed_text


def test_inert_spell_line_is_grey_as_a_whole_even_when_wrapped(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)
    name = "Очень длинное название заклинания без механики боя " * 2

    async def steps(app, pilot):
        app.show_blocks(actions_blocks((name.strip(),)), refresh=True)
        await pilot.pause()
        foot = app.query_one("#menu-foot")
        # недоступные заклинания -- отдельный серый блок под меню: стиль на всём тексте
        return "dim" in str(foot.content.style), foot.content.plain.splitlines()

    dim, grey = run(app, steps)
    assert dim is True
    assert len(grey) >= 2
