# Этап 5, P3 (STAGE5-PLAN, P3 «Меню и режимы: все точки входа»): по Pilot-тесту на точки входа 1-10.
# Ожидаемый API (ТРЕБОВАНИЕ к коду P3; где кода ещё нет, тест красный):
#   ai_dm.ui.tui.modals.PickerApp(title, names) -- App выбора героя/пресета ДО GameApp (T-4):
#     виджет #choices с пунктами «1. <имя>», выбор цифрой или кликом, App.return_value --
#     номер выбранного имени с 1 (сверено с кодом kaban);
#   /sheet /inv /spells /abilities /cost /model -- ModalScreen поверх (len(app.screen_stack) == 2)
#     с текстом ответа команды; Esc закрывает; /help и остальные команды -- в ленту без модалки;
#   меню хода (2.2, model_choice, level_up, hero_dead, лимит) -- в #choices под лентой, цифрой
#     в поле ввода или кликом по пункту; #combat -- «Бой» (карта + действия), #gains -- «Получено».
# Тесты без сети: мок-адаптеры, фиксированный size, Pilot через asyncio.run, без сна (повторы --
# sleeper=список). Ctrl+C во время хода (первый -- ждать и автосейв, второй -- 130) уже покрыт в
# test_tui_turn.py; здесь Ctrl+C только в простое и в hero_dead.
import asyncio
import contextlib
import sys
import threading
from pathlib import Path

import pytest
from textual.worker import WorkerCancelled

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "protocol"))

from game_kit import (  # noqa: E402
    OPUS,
    FactorySpy,
    ReactiveAdapter,
    core_dump,
    end_scene_call,
    make_app,
    text_step,
    tools_step,
)
from slots_kit import list_slots  # noqa: E402
from summarizer_kit import summ_fail_steps, summ_steps  # noqa: E402
from ui_kit import (  # noqa: E402
    DESCEND,
    SEED,
    TALK,
    build_app,
    cli,
    scene_app,
    state_of,
    text_app,
    write_script,
)

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402

FATAL = [{"error": "fatal", "message": "ключ отозван"}]
NETWORK = [{"error": "transient", "message": "сеть"}] * 4
PAID = {"text": "Рассказ.", "usage": {"input": 1500, "output": 60}}
OFFER = {
    "tool_calls": [
        {"id": "c1", "name": "offer_choices",
         "input": {"type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}},
    ]
}
SCRIPTS = Path(__file__).resolve().parents[3] / "fixtures" / "scripts"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def tui_of(game, **kw):
    from ai_dm.ui.session import PlaySession
    from ai_dm.ui.tui.app import AiDmApp

    startup = kw.pop("startup", ())
    return AiDmApp(PlaySession(game, **kw), startup=startup)


def closed(app):
    # App попросили выйти: публичный флаг AiDmApp.closing
    return app.closing


def choices(tui, app):
    return tui.text_of(app.query_one("#choices"))


def feed(tui, app):
    return tui.flat(tui.text_of(app.query_one("#feed")))


async def click_item(tui, app, pilot, number, selector="#choices"):
    # клик по пункту «<number>. ...»: координаты берём с экрана, а не из внутренностей виджета
    region = app.query_one(selector).region
    rows = tui.screen_rows(app)
    for y in range(region.y, region.bottom):
        column = rows[y].find(f"{number}. ")
        if column >= 0:
            await pilot.click(offset=(column + 3, y))
            await app.workers.wait_for_complete()
            await pilot.pause()
            return
    raise AssertionError(f"пункта {number} нет на экране: {rows[region.y:region.bottom]}")


# 1. старт нового мира и продолжение

def test_hero_picker_shows_numbered_names(tui):
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return choices(tui, app)

    text = run(PickerApp("Выберите героя:", ["Арн", "Лиэль"]), steps)
    assert "1. Арн" in text
    assert "2. Лиэль" in text


def test_hero_picker_digit_picks_hero(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", ["Арн", "Лиэль"])

    async def steps(app, pilot):
        await pilot.press("2")
        await pilot.pause()

    run(app, steps)
    assert app.return_value == 2


def test_hero_picker_click_picks_hero(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", ["Арн", "Лиэль"])

    async def steps(app, pilot):
        await click_item(tui, app, pilot, 2)

    run(app, steps)
    assert app.return_value == 2


def test_start_notes_are_in_the_feed(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, [text_step()]), startup=["Мир: vale-1, сид 3"])

    async def steps(app, pilot):
        return feed(tui, app)

    assert "Мир: vale-1, сид 3" in run(app, steps)


def test_continued_world_shows_last_narration_in_the_feed(registry, tmp_path, tui):
    from ai_dm.ui.session import PlaySession

    game = text_app(registry, tmp_path, [text_step("Прошлый рассказ.")])
    PlaySession(game).submit("Иду")
    app = tui_of(game)

    async def steps(app, pilot):
        return feed(tui, app)

    assert "Прошлый рассказ." in run(app, steps)


def test_load_command_shows_last_narration_in_the_feed(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step("Рассказ до сохранения.")])
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        game.save_current("auto")
        await tui.submit(app, pilot, "/load")
        return feed(tui, app)

    # один раз после хода, второй -- после /load
    assert run(app, steps).count("Рассказ до сохранения.") == 2


def test_load_command_in_tui_feed_has_loaded_note_before_narration(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step("Рассказ до сохранения.")])
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Иду")
        game.save_current("auto")
        await tui.submit(app, pilot, "/load")
        return feed(tui, app)

    text = run(app, steps)
    assert text.rindex("Загружено: auto") < text.rindex("Рассказ до сохранения.")


def test_new_world_opening_is_the_first_turn_without_input(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step("Таверна гудит.")])
    app = tui_of(game, opening="(Начало игры.)")

    async def steps(app, pilot):
        await app.workers.wait_for_complete()
        await pilot.pause()
        return feed(tui, app), app.query_one("#input").disabled

    text, disabled = run(app, steps)
    assert "Таверна гудит." in text
    assert disabled is False
    assert game.bundle.session.turn_seq == 1


# 2. обычный ход: варианты под лентой

def offer_app(registry, tmp_path):
    steps = [OFFER, text_step("Трактирщик косится."), text_step("Раз."), text_step("Два.")]
    return tui_of(text_app(registry, tmp_path, steps))


def test_offered_choices_are_shown_under_the_feed(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        box = app.query_one("#choices")
        under = box.region.y >= app.query_one("#feed").region.bottom
        return tui.shown(box), under, choices(tui, app)

    shown, under, text = run(app, steps)
    assert shown is True
    assert under is True
    assert "1. Спросить про подвал" in text
    assert "2. Заказать эль" in text


def test_digit_picks_offered_choice(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        await tui.submit(app, pilot, "2")

    run(app, steps)
    assert state_of(app.game.adapter.requests[2])["player_input"] == "Заказать эль"


def test_digit_key_with_empty_input_picks_offered_choice(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        await pilot.press("2")
        await app.workers.wait_for_complete()
        await pilot.pause()

    run(app, steps)
    assert state_of(app.game.adapter.requests[2])["player_input"] == "Заказать эль"


def test_digit_key_with_text_in_input_is_just_text(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        app.query_one("#input").value = "Беру "
        app.query_one("#input").cursor_position = 5
        await pilot.press("2")
        await pilot.pause()
        return app.query_one("#input").value

    assert run(app, steps) == "Беру 2"
    assert app.game.bundle.session.turn_seq == 1


def test_click_picks_offered_choice(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        await click_item(tui, app, pilot, 2)

    run(app, steps)
    assert state_of(app.game.adapter.requests[2])["player_input"] == "Заказать эль"


def test_free_text_is_sent_as_is_while_choices_are_shown(registry, tmp_path, tui):
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        await tui.submit(app, pilot, "Сам решу")

    run(app, steps)
    assert state_of(app.game.adapter.requests[2])["player_input"] == "Сам решу"


# 3. бой

def fight_app(registry, tmp_path):
    game, _ = scene_app(registry, tmp_path, hp=200)
    return tui_of(game)


async def start_fight(tui, app, pilot):
    await tui.submit(app, pilot, TALK)
    await tui.submit(app, pilot, "1")
    await tui.submit(app, pilot, DESCEND)


def test_combat_panel_has_map_and_actions(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return (
            tui.shown(app.query_one("#combat")), tui.text_of(app.query_one("#combat")),
            tui.text_of(app.query_one("#actions")),
        )

    shown, text, actions = run(app, steps)
    assert shown is True
    assert "Закончить ход" in actions
    assert "Атака" in actions
    assert "Земляной пол" in text
    assert "Закончить ход" not in text


def test_combat_hint_is_in_the_feed_once_per_combat(registry, tmp_path, tui):
    from ai_dm.ui.tui.strings import COMBAT_HINT_TUI

    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        # «Закончить ход» -- строка меню; её номер в меню виден, а не плоский
        rows = [x.strip() for x in app.query_one("#actions").text.splitlines()]
        row = next(x for x in rows if x.endswith("Закончить ход"))
        await tui.submit(app, pilot, row.split(".")[0])
        return feed(tui, app)

    text = run(app, steps)
    assert text.count(tui.flat(COMBAT_HINT_TUI)) == 1


def test_enemy_turn_lines_come_to_the_combat_log(registry, tmp_path, tui):
    # живой прогон 1, п. 8: лог боя -- в #combat-log, не в ленту
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        log = app.query_one("#combat-log")
        before = tui.text_of(log).count("против КД")
        rows = [x.strip() for x in app.query_one("#actions").text.splitlines()]
        row = next(x for x in rows if x.endswith("Закончить ход"))
        await tui.submit(app, pilot, row.split(".")[0])
        return before, tui.text_of(log).count("против КД")

    before, after = run(app, steps)
    assert after > before


def test_combat_panel_is_hidden_outside_combat(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, [text_step()]))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#combat"))

    assert run(app, steps) is False


def test_victory_puts_xp_into_gains_panel(registry, tmp_path, tui):
    from ai_dm.game.app import Reply
    from ai_dm.game.turn import TurnResult

    game = text_app(registry, tmp_path, [text_step()])

    def handle(line):
        hero_of(game.bundle).sheet.xp += 75
        turn = TurnResult("r1")
        turn.committed = True
        turn.combat_outcome = "victory"
        return Reply(turn=turn, narration="Бой окончен.")

    game.handle = handle
    app = tui_of(game)

    async def steps(app, pilot):
        before = tui.shown(app.query_one("#gains"))
        await tui.submit(app, pilot, "Добиваю")
        after = tui.shown(app.query_one("#gains")), tui.text_of(app.query_one("#gains"))
        return before, after, feed(tui, app).lower()

    before, (shown, text), lines = run(app, steps)
    assert before is False
    assert shown is True
    assert "75" in text
    assert "победа" in lines


# 4. сбой адаптера: меню 2.2

def test_fatal_error_shows_menu_under_the_feed(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, FATAL))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower(), feed(tui, app)

    shown, text, lines = run(app, steps)
    assert shown is True
    assert "1. повтор" in text
    assert "2. сменить модель" in text
    assert "3. сохранить и выйти" in text
    assert "ключ отозван" in lines


def test_network_failure_after_retries_gives_error_menu_on_mock_clock(registry, tmp_path, tui):
    adapter = ScriptedAdapter(NETWORK, provider="anthropic", model=OPUS)
    app, game = tui.app(registry, tmp_path, adapter=adapter)
    sleeps = []
    game.runner.sleeper = sleeps.append

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower()

    shown, text = run(app, steps)
    assert shown is True
    assert "повтор" in text
    assert sleeps == [1, 3, 10]
    assert game.pending == "error_menu"


def test_refusal_gives_error_menu_with_hint(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, [{"stop": "refusal"}] * 2))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), feed(tui, app).lower()

    shown, lines = run(app, steps)
    assert shown is True
    assert "tone" in lines
    assert "модел" in lines


def test_error_menu_retry_by_digit_plays_the_turn(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, FATAL + [text_step("Починилось.")]))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "1")
        return tui.shown(app.query_one("#choices")), feed(tui, app)

    shown, lines = run(app, steps)
    assert shown is False
    assert "Починилось." in lines
    assert app.game.pending is None


def test_error_menu_retry_by_click_plays_the_turn(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, FATAL + [text_step("Починилось.")]))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await click_item(tui, app, pilot, 1)
        return feed(tui, app)

    assert "Починилось." in run(app, steps)


def test_switch_model_shows_model_choice_list_under_the_feed(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, FATAL, adapter_factory=FactorySpy())
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "2")
        return len(app.screen_stack), tui.shown(app.query_one("#choices")), choices(tui, app)

    depth, shown, text = run(app, steps)
    assert depth == 1
    assert shown is True
    for model in game.model_options():
        assert model in text


def test_picked_model_is_visible_in_model_command(registry, tmp_path, tui):
    spy = FactorySpy()
    game = text_app(registry, tmp_path, FATAL, adapter_factory=spy)
    options = game.model_options()
    other = next(key for key in options if key != f"anthropic:{OPUS}")
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "2")
        await tui.submit(app, pilot, str(options.index(other) + 1))
        await tui.submit(app, pilot, "1")
        await tui.submit(app, pilot, "/model")
        text = tui.flat(tui.visible_text(app))
        await pilot.press("escape")
        await pilot.pause()
        return text

    text = run(app, steps)
    assert spy.calls == [tuple(other.split(":", 1))]
    assert f"{other} (текущая)" in text


def test_error_menu_save_and_quit_ends_app_and_saves(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, FATAL)
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "3")
        return closed(app)

    assert run(app, steps) is True
    assert "auto" in list_slots(tmp_path, game.world_id)


def summ_fail_app(registry, tmp_path, summarizer):
    narrator = [tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")]
    game = text_app(registry, tmp_path, narrator)
    # make_app подменяет сессию summarizer заглушкой; нужна настоящая, с моком summarizer
    del game.runner.new_summarizer_session
    game.runner.summarizer_adapter = ScriptedAdapter(
        summarizer, provider="anthropic", model=OPUS
    )
    return tui_of(game)


def test_summarizer_failure_at_scene_boundary_gives_the_same_error_menu(registry, tmp_path, tui):
    app = summ_fail_app(registry, tmp_path, summ_fail_steps())

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower()

    shown, text = run(app, steps)
    assert shown is True
    assert "1. повтор" in text
    assert "2. сменить модель" in text
    assert "3. сохранить и выйти" in text
    assert app.game.runner.failed_role == "summarizer"


def test_summarizer_retry_closes_the_menu_and_writes_summary(registry, tmp_path, tui):
    app = summ_fail_app(registry, tmp_path, summ_fail_steps() + summ_steps("После повтора."))

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "1")
        return tui.shown(app.query_one("#choices"))

    assert run(app, steps) is False
    assert [s.summary for s in app.game.bundle.memory.scenes] == ["После повтора."]


# 5. мягкий лимит

def paid_nano(registry, root):
    from ai_dm.ui.session import PlaySession

    probe = text_app(registry, root, [PAID])
    PlaySession(probe).submit("Иду")
    return probe.ledger.report(probe.now().astimezone().date()).session.total_nano


def limited(tui, registry, tmp_path, micro, turns=12):
    app, game = tui.app(registry, tmp_path, steps=[PAID] * turns, limits={"session": micro})
    return app, game


def test_soft_limit_warns_once_at_warn_percent(registry, tmp_path, tui):
    nano = paid_nano(registry, tmp_path / "probe")
    # лимит = 11 ходов: девятый ход -- 81%, десятый -- 90%, одиннадцатый -- 100%
    app, game = limited(tui, registry, tmp_path / "main", nano * 11 // 1000)
    warn = game.settings.app.cost_limits.warn_percent

    async def steps(app, pilot):
        for _ in range(10):
            await tui.submit(app, pilot)
        return feed(tui, app), tui.percent(app), tui.shown(app.query_one("#choices"))

    text, percent, shown = run(app, steps)
    assert text.count(f"Потрачено {warn}% лимита трат.") == 1
    assert percent == 90
    assert shown is False


def test_soft_limit_pause_opens_continue_or_save_and_quit_menu(registry, tmp_path, tui):
    app, _ = limited(tui, registry, tmp_path, 1)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower(), feed(tui, app)

    shown, text, lines = run(app, steps)
    assert shown is True
    assert "1. продолжить" in text
    assert "2. сохранить и выйти" in text
    assert "лимит" in lines.lower()


def test_soft_limit_continue_plays_on_and_does_not_ask_again(registry, tmp_path, tui):
    app, game = limited(tui, registry, tmp_path, 1)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "1")
        await tui.submit(app, pilot, "Иду дальше")
        return tui.shown(app.query_one("#choices"))

    assert run(app, steps) is False
    assert game.bundle.session.turn_seq == 2


def test_soft_limit_continue_by_click(registry, tmp_path, tui):
    app, game = limited(tui, registry, tmp_path, 1)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await click_item(tui, app, pilot, 1)
        return tui.shown(app.query_one("#choices"))

    assert run(app, steps) is False
    assert app.session.limit_menu is False


def test_soft_limit_save_and_quit_saves_and_ends_app(registry, tmp_path, tui):
    app, game = limited(tui, registry, tmp_path, 1)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "2")
        return closed(app)

    assert run(app, steps) is True
    assert "auto" in list_slots(game.saves_root, game.world_id)


# 6. повышение уровня

def test_level_up_menu_is_shown_under_the_feed(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step()])
    hero_of(game.bundle).sheet.xp = 300
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower()

    shown, text = run(app, steps)
    assert shown is True
    assert "1. средн" in text
    assert "2. бросок" in text


def test_level_up_digit_applies_and_closes_menu(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step()])
    hero_of(game.bundle).sheet.xp = 300
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "1")
        return tui.shown(app.query_one("#choices"))

    assert run(app, steps) is False
    assert hero_of(game.bundle).sheet.level == 2
    assert game.pending is None


def test_level_up_by_click_applies(registry, tmp_path, tui):
    game = text_app(registry, tmp_path, [text_step()])
    hero_of(game.bundle).sheet.xp = 300
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await click_item(tui, app, pilot, 1)

    run(app, steps)
    assert hero_of(game.bundle).sheet.level == 2


def test_level_up_with_choices_goes_step_by_step(registry, tmp_path, tui):
    from test_game_level_choices import ranger_bundle

    from ai_dm.rules.progression import xp_for_level

    bundle = ranger_bundle(registry, xp_for_level(2, registry))
    game = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Осматриваюсь")
        seen = [choices(tui, app)]
        await tui.submit(app, pilot, "1")
        seen.append(choices(tui, app))
        menu = game.menu_for(game.pending)
        await tui.submit(app, pilot, str(menu.index("archery") + 1))
        seen.append(choices(tui, app))
        menu = game.menu_for(game.pending)
        await tui.submit(app, pilot, str(menu.index("survival") + 1))
        for _ in range(20):
            if game.pending is None:
                break
            await tui.submit(app, pilot, "1")
        return seen, tui.shown(app.query_one("#choices"))

    seen, shown = run(app, steps)
    hero = game.bundle.heroes[0]
    assert game.menu_label("archery") in seen[1]
    assert game.menu_label("survival") in seen[2]
    assert game.menu_label("archery") not in seen[2]
    assert shown is False
    assert game.pending is None
    assert hero.sheet.level == 2
    assert "archery" in hero.sheet.feats


# 7. смерть героя

def dead_app(registry, tmp_path):
    game = text_app(registry, tmp_path, [text_step()])
    game.pending = "hero_dead"
    return tui_of(game), game


def test_hero_dead_menu_is_shown_under_the_feed(registry, tmp_path, tui):
    app, _ = dead_app(registry, tmp_path)

    async def steps(app, pilot):
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower()

    shown, text = run(app, steps)
    assert shown is True
    assert "1. загруз" in text
    assert "2. выйти" in text


def test_hero_dead_load_without_save_keeps_menu(registry, tmp_path, tui):
    app, game = dead_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "1")
        return tui.shown(app.query_one("#choices")), feed(tui, app)

    shown, text = run(app, steps)
    assert shown is True
    assert "нет сохранений" in text
    assert game.pending == "hero_dead"


def test_hero_dead_quit_ends_app_without_save(registry, tmp_path, tui):
    app, game = dead_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "2")
        return closed(app)

    assert run(app, steps) is True
    assert app.after_exit() == 0
    assert list_slots(tmp_path, game.world_id) == []


def test_hero_dead_ctrl_c_does_not_save(registry, tmp_path, tui):
    app, game = dead_app(registry, tmp_path)

    async def steps(app, pilot):
        await pilot.press("ctrl+c")
        await pilot.pause()
        return closed(app)

    assert run(app, steps) is True
    app.after_exit()
    assert list_slots(tmp_path, game.world_id) == []


def test_idle_ctrl_c_exits_and_autosaves(registry, tmp_path, tui):
    app = tui_of(text_app(registry, tmp_path, [text_step()]))
    game = app.game

    async def steps(app, pilot):
        await pilot.press("ctrl+c")
        await pilot.pause()
        return closed(app)

    assert run(app, steps) is True
    assert app.after_exit() == 0
    assert "auto" in list_slots(tmp_path, game.world_id)


# 8. модалки и /help

@pytest.mark.parametrize("command", ["/sheet", "/inv", "/spells", "/abilities", "/cost", "/model"])
def test_info_command_opens_modal_with_reply_and_esc_closes_it(registry, tmp_path, tui, command):
    from textual.screen import ModalScreen

    expected = text_app(registry, tmp_path / "ref", [text_step()]).handle(command).lines
    words = " ".join(expected[0].split()[:3])
    if command == "/cost":
        words = "Сессия"  # Q5: окно /cost -- таблица, итог разбит по столбцам
    if command == "/model":
        words = "Модель рассказчика"  # живой прогон 1: окно /model -- список выбора
    if command == "/inv":
        words = "Предмет (Enter"  # 96а П2: окно /inv -- список предметов с действиями
    app, _ = tui.app(registry, tmp_path / "main")

    async def steps(app, pilot):
        await tui.submit(app, pilot, command)
        opened = len(app.screen_stack), isinstance(app.screen, ModalScreen)
        shown = tui.flat(tui.visible_text(app))
        lines = feed(tui, app)
        await pilot.press("escape")
        await pilot.pause()
        return opened, shown, lines, len(app.screen_stack), app.query_one("#input").has_focus

    opened, shown, lines, depth, focus = run(app, steps)
    assert opened == (2, True)
    assert words in shown
    assert words not in lines
    assert depth == 1
    assert focus is True


def test_help_goes_to_the_feed_without_modal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/help")
        return len(app.screen_stack), feed(tui, app)

    depth, text = run(app, steps)
    assert depth == 1
    assert "/save" in text
    assert "/quit" in text


def test_quit_command_ends_app(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/quit")
        return closed(app)

    assert run(app, steps) is True


# 9. --mock и --replay

def prepared(argv, tmp_path, replay=False):
    # то же, что делает cli.play перед запуском режима: GameApp + opening + строки старта
    from slots_kit import ScriptedInput

    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup, make_parser, prepare
    from ai_dm.ui.io import CaptureOutput

    args = make_parser().parse_args(argv)
    notes = CaptureOutput()
    setup = Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "tui")
    result = prepare(args, ScriptedInput([]), CaptureOutput(), notes, setup)
    assert not isinstance(result, int)
    game, opening = result
    return game, opening, notes.lines


def test_mock_script_plays_in_tui_and_world_line_is_in_the_feed(tmp_path, tui):
    script = write_script(tmp_path / "one.yaml", "Трактирщик кивает.")
    argv = ["--new", "--hero", "arn", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(tmp_path / "saves")]
    game, opening, notes = prepared(argv, tmp_path)
    app = tui_of(game, opening=opening, startup=notes)

    async def steps(app, pilot):
        before = feed(tui, app)
        await tui.submit(app, pilot, "Иду")
        return before, feed(tui, app)

    before, after = run(app, steps)
    assert opening is None
    assert "Мир: " in before
    assert "Трактирщик кивает." in after


def live_world(root):
    argv = ["--new", "--hero", "arn", "--seed", str(SEED), "--mock",
            str(SCRIPTS / "talk_check_fight.yaml"), "--saves", str(root)]
    code, _ = cli(argv, [TALK, "1", DESCEND, "/quit"], env={})
    assert code == 0
    return next(p.name for p in root.iterdir() if p.is_dir())


def replay_argv(root, world):
    return ["--replay", "--world", world, "--hero", "arn", "--seed", str(SEED),
            "--saves", str(root)]


def test_replay_in_tui_shows_temp_dir_and_gives_same_bundle_as_simple(registry, tmp_path, tui):
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.simple import run as run_simple

    root = tmp_path / "saves"
    world = live_world(root)
    inputs = [TALK, "1", DESCEND]
    simple_game, opening, _ = prepared(replay_argv(root, world), tmp_path)
    run_simple(simple_game, ScriptedInput(inputs), PlainOutput(), replay=True, opening=opening)
    game, opening, notes = prepared(replay_argv(root, world), tmp_path)
    app = tui_of(game, replay=True, opening=opening, startup=notes)

    async def steps(app, pilot):
        before = feed(tui, app)
        for line in inputs:
            await tui.submit(app, pilot, line)
        return before

    before = run(app, steps)
    assert opening is None
    assert "ai-dm-replay-" in before
    assert core_dump(game.bundle) == core_dump(simple_game.bundle)


# 10. ход не блокирует UI

def test_f2_works_while_the_turn_is_running(registry, tmp_path, tui, gate_adapter):
    app, _ = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        before = tui.shown(app.query_one("#side"))
        await pilot.press("f2")
        await pilot.pause()
        during = tui.shown(app.query_one("#side")), app.query_one("#input").disabled
        gate_adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return before, during

    before, during = run(app, steps, size=(100, 40))
    assert before is False
    assert during == (True, True)


def test_feed_scrolls_while_the_turn_is_running(registry, tmp_path, tui, gate_adapter):
    lines = [f"Старая строка {n}" for n in range(80)]
    from ai_dm.ui.session import PlaySession
    from ai_dm.ui.tui.app import AiDmApp

    game = build_app(registry, tmp_path, gate_adapter, hp=30)
    app = AiDmApp(PlaySession(game), startup=lines)

    async def steps(app, pilot):
        box = app.query_one("#feed")
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        bottom = box.scroll_y
        box.focus()
        await pilot.press("pageup")
        await pilot.pause()
        up = box.scroll_y
        gate_adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return bottom, up

    bottom, up = run(app, steps)
    assert bottom > 0
    assert up < bottom


# правки по ревью P3

def test_first_ctrl_c_during_turn_shows_waiting_note_and_app_stays(
    registry, tmp_path, tui, gate_adapter
):
    # сам ход «Ctrl+C -> ждать -> автосейв» и второй Ctrl+C (130, без сейва) -- в test_tui_turn.py
    app, _ = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        await pilot.press("ctrl+c")
        await pilot.pause()
        waiting = tui.text_of(app.query_one("#status")), closed(app)
        gate_adapter.release.set()
        with contextlib.suppress(WorkerCancelled):
            await app.workers.wait_for_complete()
        await pilot.pause()
        return waiting, closed(app)

    (status, before), after = run(app, steps)
    assert "Ctrl+C" in status
    assert before is False
    assert after is True


def test_hero_screen_failure_falls_back_to_ask_choice_with_one_note(tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup, make_parser, prepare
    from ai_dm.ui.io import CaptureOutput

    def broken(title, names, splash=False):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "pick", broken)
    args = make_parser().parse_args(
        ["--new", "--seed", str(SEED), "--saves", str(tmp_path / "saves"),
         "--mock", str(write_script(tmp_path / "one.yaml"))]
    )
    notes, out = CaptureOutput(), CaptureOutput()
    setup = Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "tui")
    result = prepare(args, ScriptedInput(["1"]), out, notes, setup)
    assert not isinstance(result, int)
    failed = [line for line in notes.lines if "Выбор героя в TUI не запустился" in line]
    assert len(failed) == 1
    assert "нет экрана" in failed[0]
    assert any("Выберите героя" in line for line in out.lines)


def test_combat_panel_lines_fit_panel_width(registry, tmp_path, tui):
    from ai_dm.ui.tui.app import PANEL_WIDTH

    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        return tui.text_of(app.query_one("#combat"))

    text = run(app, steps)
    assert "Карта боя" in text
    wide = [line for line in text.splitlines() if len(line) > PANEL_WIDTH]
    assert wide == []


def test_digit_in_combat_does_not_pick_an_old_offered_choice(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        before = app.game.bundle.session.turn_seq
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()
        key = before, app.game.bundle.session.turn_seq, app.query_one("#input").value
        return key, feed(tui, app)

    # цифра в бою -- строка меню боя (ход), но не вариант старого ответа рассказчика
    (before, after_key, typed), text = run(app, steps)
    assert after_key == before + 1
    assert typed == ""
    assert "Спросить про подвал" not in text.split("> Спускаюсь в подвал")[-1]


def test_digit_key_in_combat_with_choices_on_screen_starts_no_turn(registry, tmp_path, tui):
    app = fight_app(registry, tmp_path)

    async def steps(app, pilot):
        await start_fight(tui, app, pilot)
        app.query_one("#choices").show("Что делаешь?", ["Спросить про подвал", "Заказать эль"])
        await pilot.pause()
        before = app.game.bundle.session.turn_seq
        await pilot.press("1")
        await app.workers.wait_for_complete()
        await pilot.pause()
        return before, app.game.bundle.session.turn_seq, app.busy

    before, after, busy = run(app, steps)
    assert after == before
    assert busy is False


# решения проектировщика по P3: варианты после выбора, /model

class GateOfferAdapter(ScriptedAdapter):
    # первый вызов хода ждёт release (с потолком, чтобы тест не завис)
    def __init__(self, steps):
        super().__init__(steps, provider="anthropic", model=OPUS)
        self.entered = threading.Event()
        self.release = threading.Event()

    def complete(self, req):
        self.entered.set()
        assert self.release.wait(10)
        return super().complete(req)


def test_choices_are_hidden_while_next_turn_runs(registry, tmp_path, tui):
    adapter = GateOfferAdapter([OFFER, text_step("Трактирщик косится."), text_step("Раз.")])
    adapter.release.set()
    app, _ = tui.app(registry, tmp_path, adapter=adapter)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        before = tui.shown(app.query_one("#choices"))
        adapter.release.clear()
        adapter.entered.clear()
        app.query_one("#input").value = "Сам решу"
        await pilot.press("enter")
        await asyncio.to_thread(adapter.entered.wait, 10)
        await pilot.pause()
        during = tui.shown(app.query_one("#choices"))
        adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return before, during

    assert run(app, steps) == (True, False)


def test_choices_stay_hidden_after_turn_without_new_offer(registry, tmp_path, tui):
    # красный: game не сбрасывает offered_choices после хода (BACKLOG 16), блок menu приходит снова
    app = offer_app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        await tui.submit(app, pilot, "Сам решу")
        return tui.shown(app.query_one("#choices"))

    assert run(app, steps) is False


def test_choices_come_back_on_no_such_option_while_error_menu_is_pending(
    registry, tmp_path, tui
):
    game = text_app(registry, tmp_path, FATAL)
    app = tui_of(game)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "9")
        return tui.shown(app.query_one("#choices")), choices(tui, app), feed(tui, app)

    shown, text, lines = run(app, steps)
    assert game.pending == "error_menu"
    assert "Нет такого варианта." in lines
    assert shown is True
    assert "1." in text


def test_choices_come_back_on_no_such_option_while_limit_menu_is_active(registry, tmp_path, tui):
    app, _ = limited(tui, registry, tmp_path, 1)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "9")
        return tui.shown(app.query_one("#choices")), choices(tui, app).lower(), feed(tui, app)

    shown, text, lines = run(app, steps)
    assert app.session.limit_menu is True
    assert "Нет такого варианта." in lines
    assert shown is True
    assert "1. продолжить" in text


def test_model_with_arguments_goes_to_the_feed_without_modal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model world x")
        return len(app.screen_stack), feed(tui, app)

    depth, lines = run(app, steps)
    assert depth == 1
    assert "Неизвестная роль" in lines


def test_model_without_arguments_opens_modal(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/model")
        return len(app.screen_stack), feed(tui, app)

    depth, lines = run(app, steps)
    assert depth == 2
    assert "Доступно" not in lines


def test_cost_modal_table_cells_match_cost_rows(registry, tmp_path, tui):
    from ai_dm.game.commands import cost_report, cost_rows, money_text
    from ai_dm.ui.tui import strings

    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await tui.submit(app, pilot, "/cost")
        table = app.screen.query_one("#modal-table")
        header = [str(column.label) for column in table.columns.values()]
        cells = [[str(cell) for cell in table.get_row_at(i)] for i in range(table.row_count)]
        return header, cells

    header, cells = run(app, steps)
    rows = cost_rows(cost_report(game))
    assert header == list(strings.COST_COLUMNS) == ["Период", "Роль", "Модель", "Сумма"]
    assert cells == [[p, r, m, money_text(c)] for p, r, m, c in rows]
    assert any(row[1] == "narrator" for row in cells)


# Б1б: PickerApp (герой, пресет), «Создать героя на лету», сбой экрана создания

def test_picker_shows_title_and_numbered_items(tui):
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return choices(tui, app)

    text = run(PickerApp("Пресет мира:", ["Как в паке", "Героика"]), steps)
    assert "Пресет мира:" in text
    assert "1. Как в паке" in text
    assert "2. Героика" in text


def test_picker_digit_outside_the_list_does_nothing(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Т:", ["а", "б"])

    async def steps(app, pilot):
        await pilot.press("5")
        await pilot.pause()
        return app.return_value, app.is_running

    assert run(app, steps) == (None, True)


def test_picker_escape_returns_none(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Т:", ["а", "б"])

    async def steps(app, pilot):
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is None


def test_picker_with_create_item_last_returns_its_number(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", ["Арн", "Лиэль", "Грей", "Создать героя на лету"])

    async def steps(app, pilot):
        await pilot.press("4")
        await pilot.pause()

    run(app, steps)
    assert app.return_value == 4


def test_picker_click_on_last_item_returns_its_number(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Т:", ["а", "б", "в"])

    async def steps(app, pilot):
        await click_item(tui, app, pilot, 3)

    run(app, steps)
    assert app.return_value == 3


def fake_pick(title, names, splash=False):
    # «Создать героя на лету» (предпоследний, последний -- «Создать пошагово») в меню героя,
    # иначе первый (пресет «как в паке»)
    return len(names) - 1 if names[-1] == "Создать пошагово" else 1


def test_create_screen_failure_falls_back_to_simple_with_one_note(tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup, make_parser, prepare
    from ai_dm.ui.io import CaptureOutput

    def broken(session, placeholder):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    monkeypatch.setattr(tui_module, "create_hero", broken)
    args = make_parser().parse_args(
        ["--new", "--seed", str(SEED), "--saves", str(tmp_path / "saves"),
         "--mock", str(SCRIPTS / "hero_sheet.yaml")]
    )
    notes, out = CaptureOutput(), CaptureOutput()
    setup = Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "tui")
    result = prepare(args, ScriptedInput(["воин-сирота ищет сестру", "1"]), out, notes, setup)
    assert not isinstance(result, int)
    failed = [line for line in notes.lines if "Создание героя в TUI не запустилось" in line]
    assert len(failed) == 1
    assert "нет экрана" in failed[0]
    assert any("Опишите героя" in line for line in out.lines)
    assert result[0].bundle.heroes[0].name == "Борин"


def test_create_screen_result_sheet_starts_world_without_simple_dialog(tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup, make_parser, prepare
    from ai_dm.ui.io import CaptureOutput

    sheets = []

    def create(session, placeholder):
        session.submit("воин-сирота ищет сестру")
        session.submit("1")
        sheets.append(session.sheet)
        return session.sheet

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    monkeypatch.setattr(tui_module, "create_hero", create)
    args = make_parser().parse_args(
        ["--new", "--seed", str(SEED), "--saves", str(tmp_path / "saves"),
         "--mock", str(SCRIPTS / "hero_sheet.yaml")]
    )
    notes, out = CaptureOutput(), CaptureOutput()
    setup = Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "tui")
    result = prepare(args, ScriptedInput([]), out, notes, setup)
    assert result[0].bundle.heroes[0].name == "Борин"
    assert not any("Опишите героя" in line for line in out.lines)
    assert len(sheets) == 1


# Б1-фикс п.5: PickerApp с реальными подписями пресетов в окне 80x24

def preset_names():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import PRESET_AS_PACK, preset_label

    return [PRESET_AS_PACK] + [preset_label(p) for p in load_presets().values()]


def test_preset_picker_digit_three_returns_three(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Пресет мира:", preset_names())

    async def steps(app, pilot):
        await pilot.press("3")
        await pilot.pause()

    run(app, steps, size=(80, 24))
    assert app.return_value == 3


def test_preset_picker_digit_two_returns_two(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Пресет мира:", preset_names())

    async def steps(app, pilot):
        await pilot.press("2")
        await pilot.pause()

    run(app, steps, size=(80, 24))
    assert app.return_value == 2


def test_preset_picker_click_on_item_three_returns_three(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Пресет мира:", preset_names())

    async def steps(app, pilot):
        await click_item(tui, app, pilot, 3)

    run(app, steps, size=(80, 24))
    assert app.return_value == 3


def test_preset_picker_click_on_wrapped_line_of_item_three_returns_three(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Пресет мира:", preset_names())

    async def steps(app, pilot):
        region = app.query_one("#choices").region
        rows = tui.screen_rows(app)
        y = next(y for y in range(region.y, region.bottom) if "3. " in rows[y])
        wrapped = rows[y + 1]
        assert wrapped.strip("│ ") and "4. " not in wrapped
        await pilot.click(offset=(wrapped.index(wrapped.strip("│ ")[0]) + 1, y + 1))
        await pilot.pause()

    run(app, steps, size=(80, 24))
    assert app.return_value == 3


# Б2б: placeholder по типу сессии, заставка в PickerApp (пункт «Создать пошагово» -- в test_cli_hero_steps)

def make_sessions(registry, cfg):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))
    from hero_kit import deps, sheet_task, vale_pack

    from ai_dm.ui.hero_session import HeroSession
    from ai_dm.ui.hero_wizard import HeroWizard

    hero_deps = deps(None, registry, cfg)
    task = sheet_task(vale_pack(registry))
    return HeroSession(hero_deps, task, 80), HeroWizard(hero_deps, task, 80)


def test_create_hero_tui_gives_steps_placeholder_to_wizard(registry, cfg, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import create_hero_tui
    from ai_dm.ui.tui import strings

    seen = []
    monkeypatch.setattr(tui_module, "create_hero", lambda session, placeholder: seen.append(placeholder))
    _, wizard = make_sessions(registry, cfg)
    assert create_hero_tui(wizard) == (None, None)
    assert seen == [strings.STEPS_PLACEHOLDER]


def test_create_hero_tui_gives_create_placeholder_to_describe_session(registry, cfg, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import create_hero_tui
    from ai_dm.ui.tui import strings

    seen = []
    monkeypatch.setattr(tui_module, "create_hero", lambda session, placeholder: seen.append(placeholder))
    session, _ = make_sessions(registry, cfg)
    assert create_hero_tui(session) == (None, None)
    assert seen == [strings.CREATE_PLACEHOLDER]


def test_create_hero_tui_passes_the_same_session_and_returns_its_sheet(registry, cfg, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import create_hero_tui

    seen = []

    def create(session, placeholder):
        seen.append(session)
        return "лист"

    monkeypatch.setattr(tui_module, "create_hero", create)
    _, wizard = make_sessions(registry, cfg)
    assert create_hero_tui(wizard) == ("лист", None)
    assert seen == [wizard]


def test_create_hero_tui_returns_start_error_as_reason(registry, cfg, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import create_hero_tui

    def broken(session, placeholder):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "create_hero", broken)
    _, wizard = make_sessions(registry, cfg)
    sheet, reason = create_hero_tui(wizard)
    assert sheet is None
    assert "нет экрана" in str(reason)


def picker_feed_lines(app):
    return [strip.text.rstrip() for strip in app.query_one("#feed").lines]


def test_picker_shows_title_art_above_the_items(tui):
    from ai_dm.art import art_for_event
    from ai_dm.ui.tui.modals import PickerApp

    rows = [line.rstrip() for line in art_for_event("title").splitlines() if line.strip()]

    async def steps(app, pilot):
        screen = [row.rstrip() for row in tui.screen_rows(app)]
        feed_y = app.query_one("#feed").region.y
        choices_y = app.query_one("#choices").region.y
        return picker_feed_lines(app), screen, feed_y, choices_y

    lines, screen, feed_y, choices_y = run(PickerApp("Выберите героя:", ["Арн", "Лиэль"], splash=True), steps)
    assert len(rows) == 16
    assert [row for row in rows if row not in lines] == []
    assert [row for row in rows if not any(row in line for line in screen)] == []
    assert feed_y < choices_y


def test_picker_art_does_not_hide_the_items(tui):
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return tui.flat(tui.visible_text(app))

    text = run(PickerApp("Выберите героя:", ["Арн", "Лиэль"]), steps, size=(100, 40))
    assert "1. Арн" in text
    assert "2. Лиэль" in text


def test_picker_digit_still_picks_with_art(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", ["Арн", "Лиэль"])

    async def steps(app, pilot):
        await pilot.press("2")
        await pilot.pause()

    run(app, steps)
    assert app.return_value == 2



def test_picker_without_splash_has_no_title_art(tui):
    from ai_dm.art import art_for_event
    from ai_dm.ui.tui.modals import PickerApp

    rows = [line.rstrip() for line in art_for_event("title").splitlines() if line.strip()]

    async def steps(app, pilot):
        return tui.visible_text(app)

    screen = run(PickerApp("Пресет мира:", ["Как в паке", "Героика"]), steps)
    assert rows[0] not in screen
    assert "1. Как в паке" in screen


def test_picker_with_splash_false_is_default_in_tui_pick(monkeypatch):
    import ai_dm.ui.tui as tui_module

    seen = []

    class Fake:
        def __init__(self, title, names, splash=False):
            seen.append(splash)

        def run(self):
            return 1

    monkeypatch.setattr(tui_module, "PickerApp", Fake)
    tui_module.pick("Т:", ["а"])
    tui_module.pick("Т:", ["а"], True)
    assert seen == [False, True]


def test_picker_without_splash_has_no_feed_widget():
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return len(app.query("#feed"))

    assert run(PickerApp("Пресет мира:", ["Как в паке", "Героика"]), steps) == 0


def test_picker_with_splash_has_feed_widget():
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return len(app.query("#feed"))

    assert run(PickerApp("Выберите героя:", ["Арн", "Лиэль"], splash=True), steps) == 1


def hero_names():
    return ["Арн", "Лиэль", "Грей", "Создать героя на лету", "Создать пошагово"]


def test_hero_picker_with_splash_in_80x24_shows_all_items(tui):
    from ai_dm.ui.tui.modals import PickerApp

    async def steps(app, pilot):
        return tui.visible_text(app)

    text = run(PickerApp("Выберите героя:", hero_names(), splash=True), steps, size=(80, 24))
    for number, name in enumerate(hero_names(), 1):
        assert f"{number}. {name}" in text


def test_hero_picker_with_splash_in_80x24_digit_picks_last(tui):
    from ai_dm.ui.tui.modals import PickerApp

    app = PickerApp("Выберите героя:", hero_names(), splash=True)

    async def steps(app, pilot):
        await pilot.press("5")
        await pilot.pause()

    run(app, steps, size=(80, 24))
    assert app.return_value == 5
