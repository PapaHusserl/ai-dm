# Этап 5, P2 (A5): ход в worker'е обновляет панели; пока ход идёт, ввод заблокирован.
# Контракт -- в conftest.py. Ход: рассказ + skill_check (+ урон), мок-адаптер, без сети.
import asyncio
import contextlib

from textual.worker import WorkerCancelled

BUSY = "Мастер думает…"


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


# панели после хода

def test_turn_puts_narration_into_feed(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.text_of(app.query_one("#feed"))
        await tui.submit(app, pilot)
        return before, tui.text_of(app.query_one("#feed"))

    before, after = run(app, steps)
    assert tui.NARRATION not in before
    assert tui.NARRATION in after


def test_turn_puts_roll_line_into_rolls_panel(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.flat(tui.text_of(app.query_one("#rolls")))
        await tui.submit(app, pilot)
        return before, tui.flat(tui.text_of(app.query_one("#rolls")))

    before, after = run(app, steps)
    roll = game.bundle.memory.recent_turns[-1].rolls[0]
    assert tui.flat(roll) not in before
    assert tui.flat(roll) in after


def test_turn_updates_hp_in_hero_panel(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.text_of(app.query_one("#hero"))
        await tui.submit(app, pilot)
        return before, tui.text_of(app.query_one("#hero"))

    before, after = run(app, steps)
    creature = game.bundle.heroes[0].creature
    assert creature.hp_current < tui.HP
    assert f"{tui.HP}/{creature.hp_max}" in before
    assert f"{creature.hp_current}/{creature.hp_max}" in after
    assert f"{tui.HP}/{creature.hp_max}" not in after


def test_turn_updates_session_cost_in_status(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        before = tui.session_cost(app)
        await tui.submit(app, pilot)
        return before, tui.session_cost(app)

    before, after = run(app, steps)
    assert before == 0
    assert after > 0


def test_turn_panels_are_updated_in_narrow_terminal_too(registry, tmp_path, tui):
    app, game = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        await pilot.press("f2")
        await pilot.pause()
        creature = game.bundle.heroes[0].creature
        return (
            tui.NARRATION in tui.text_of(app.query_one("#feed")),
            f"{creature.hp_current}/{creature.hp_max}" in tui.visible_text(app),
        )

    assert run(app, steps, (100, 40)) == (True, True)


# ход идёт: ввод заблокирован

def test_input_is_disabled_and_status_says_thinking_while_turn_runs(
    registry, tmp_path, tui, gate_adapter
):
    app, _ = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        before = entry.disabled, BUSY in tui.text_of(app.query_one("#status"))
        entry.value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        await pilot.pause()
        busy = entry.disabled, BUSY in tui.text_of(app.query_one("#status"))
        gate_adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return before, busy

    before, busy = run(app, steps)
    assert before == (False, False)
    assert busy == (True, True)


def test_input_is_enabled_and_focused_after_turn(registry, tmp_path, tui, gate_adapter):
    app, _ = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        entry = app.query_one("#input")
        entry.value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        gate_adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        thinking = BUSY in tui.text_of(app.query_one("#status"))
        return entry.disabled, entry.has_focus, entry.value, thinking

    assert run(app, steps) == (False, True, "", False)


def test_feed_has_no_narration_until_turn_ends(registry, tmp_path, tui, gate_adapter):
    app, _ = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        await pilot.pause()
        during = tui.NARRATION in tui.text_of(app.query_one("#feed"))
        gate_adapter.release.set()
        await app.workers.wait_for_complete()
        await pilot.pause()
        return during, tui.NARRATION in tui.text_of(app.query_one("#feed"))

    assert run(app, steps) == (False, True)


def test_second_turn_works_after_first(registry, tmp_path, tui):
    steps_two = tui.TURN_STEPS + [{"text": "Тишина.", "usage": {"input": 100, "output": 10}}]
    app, _ = tui.app(registry, tmp_path, steps=steps_two)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        first = tui.session_cost(app)
        await tui.submit(app, pilot, "Жду")
        return first, tui.session_cost(app), tui.text_of(app.query_one("#feed"))

    first, second, feed = run(app, steps)
    assert second > first
    assert "Тишина." in feed


# строка состояния: лимит и общий день

def test_status_has_no_percent_when_limit_is_off(registry, tmp_path, tui):
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.percent(app)

    assert run(app, steps) is None


def test_status_shows_session_limit_percent_after_turn(registry, tmp_path, tui):
    nano = tui.spent_nano(registry, tmp_path / "probe")
    # лимит вдвое больше траты хода -- ровно 50%
    app, _ = tui.app(registry, tmp_path / "main", limits={"session": nano // 500})

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.percent(app)

    assert abs(run(app, steps) - 50) < 1


def test_status_shows_day_percent_with_spending_of_another_world(registry, tmp_path, tui):
    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.types import Usage

    # сессионный лимит выключен (0), дневной 10_000 нано; сосед за сегодня потратил 5_000 -- 50%
    app, game = tui.app(registry, tmp_path, limits={"session": 0, "day": 10})
    day = game.now().astimezone().date()
    CostLedger(tmp_path, "other-world").add(
        call_id="o-1", role="narrator", model="claude-opus-5-5", usage=Usage(input=1),
        cost_nano=5_000, day=day,
    )

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/help")
        return tui.percent(app)

    assert abs(run(app, steps) - 50) < 1


# панели между ходами

def test_rolls_are_cleared_between_turns(registry, tmp_path, tui):
    steps_two = tui.TURN_STEPS + [{"text": "Тишина.", "usage": {"input": 100, "output": 10}}]
    app, game = tui.app(registry, tmp_path, steps=steps_two)

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        first = tui.flat(tui.text_of(app.query_one("#rolls")))
        await tui.submit(app, pilot, "Жду")
        return first, tui.flat(tui.text_of(app.query_one("#rolls")))

    first, second = run(app, steps)
    roll = tui.flat(game.bundle.memory.recent_turns[0].rolls[0])
    assert roll in first
    assert roll not in second


def combat_blocks(with_map):
    from types import SimpleNamespace

    from ai_dm.ui.screen import Block

    turn = SimpleNamespace(action=True, attacks_left=0, bonus=True, move=30, reaction=True)
    option = SimpleNamespace(id="dash", kind="dash", params={}, cost="action", label="Атака мечом")
    blocks = [Block("turn_menu", items=(option,), args=(turn, "", "КД 15", "", (), ()))]
    if with_map:
        blocks.insert(0, Block("combat_map", items=("Карта: У двери",)))
    return blocks


def test_turn_menu_without_combat_map_does_not_hide_combat_panel(
    registry, tmp_path, tui, monkeypatch
):
    # боя в игре нет: карту, которую рисует панель, подменяем
    monkeypatch.setattr(
        "ai_dm.ui.tui.blocks.combat_map_lines", lambda game, width: ["Карта: У двери"]
    )
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_blocks(combat_blocks(True), refresh=True)
        await pilot.pause()
        app.show_blocks(combat_blocks(False), refresh=True)
        await pilot.pause()
        return (
            tui.shown(app.query_one("#combat")), tui.text_of(app.query_one("#combat")),
            tui.text_of(app.query_one("#actions")),
        )

    shown, text, actions = run(app, steps)
    assert shown is True
    assert "Карта: У двери" in text
    assert "Атака мечом" in actions


def test_step_without_combat_blocks_hides_combat_panel(registry, tmp_path, tui, monkeypatch):
    # боя в игре нет: карту, которую рисует панель, подменяем
    monkeypatch.setattr(
        "ai_dm.ui.tui.blocks.combat_map_lines", lambda game, width: ["Карта: У двери"]
    )
    app, _ = tui.app(registry, tmp_path)

    async def steps(app, pilot):
        app.show_blocks(combat_blocks(True), refresh=True)
        await pilot.pause()
        shown = tui.shown(app.query_one("#combat")), tui.shown(app.query_one("#actions"))
        app.show_blocks([], refresh=True)
        await pilot.pause()
        return shown, tui.shown(app.query_one("#combat")), tui.shown(app.query_one("#actions"))

    assert run(app, steps) == ((True, True), False, False)


# Ctrl+C во время хода (Q10)

def test_first_ctrl_c_waits_for_turn_and_autosaves(registry, tmp_path, tui, gate_adapter):
    from slots_kit import list_slots

    app, game = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        await pilot.press("ctrl+c")
        await pilot.pause()
        waiting = app.is_running, list_slots(game.saves_root, game.world_id)
        gate_adapter.release.set()
        # ход дошёл до конца и App завершилась -- Textual гасит worker при выходе
        with contextlib.suppress(WorkerCancelled):
            await app.workers.wait_for_complete()
        await pilot.pause()
        return waiting

    waiting = run(app, steps)
    assert waiting == (True, [])
    assert app.after_exit() == 0
    assert "auto" in list_slots(game.saves_root, game.world_id)
    assert game.bundle.session.turn_seq == 1


def test_second_ctrl_c_exits_with_130_and_no_save(registry, tmp_path, tui, gate_adapter):
    from slots_kit import list_slots

    app, game = tui.app(registry, tmp_path, adapter=gate_adapter)

    async def steps(app, pilot):
        app.query_one("#input").value = "Иду"
        await pilot.press("enter")
        await asyncio.to_thread(gate_adapter.entered.wait, 10)
        await pilot.press("ctrl+c")
        await pilot.press("ctrl+c")
        # снимок при закрытом гейте: ход ещё не применён, сейва нет
        snapshot = (
            app.return_code, list_slots(game.saves_root, game.world_id),
            game.bundle.session.turn_seq,
        )
        gate_adapter.release.set()
        await pilot.pause()
        return snapshot

    try:
        snapshot = run(app, steps)
    finally:
        gate_adapter.release.set()
    assert snapshot == (130, [], 0)
    # run вернулся после конца потока (asyncio ждёт executor), автосейва поток не делает
    assert app.after_exit() == 130
    assert list_slots(game.saves_root, game.world_id) == []


def test_second_ctrl_c_calls_hard_exit_with_130_and_does_not_save(
    registry, tmp_path, tui, gate_adapter
):
    from slots_kit import list_slots

    app, game = tui.app(registry, tmp_path, adapter=gate_adapter)
    exits = []

    def hard_exit(code):
        # снимок «в момент смерти процесса»: гейт закрыт, ход не применён; открываем только после
        slots = list_slots(game.saves_root, game.world_id)
        exits.append((code, slots, game.bundle.session.turn_seq))
        gate_adapter.release.set()

    app.hard_exit = hard_exit

    async def scenario():
        task = asyncio.create_task(app.run_async(headless=True, size=(140, 40)))
        try:
            while not (app.is_running and app.query("#input")):
                await asyncio.sleep(0.01)
            app.query_one("#input").value = "Иду"
            await app.workers.wait_for_complete()
            app.start_turn("Иду")
            await asyncio.to_thread(gate_adapter.entered.wait, 10)
            app.action_quit_game()
            app.action_quit_game()
        finally:
            gate_adapter.release.set()
        await asyncio.wait_for(task, 10)

    asyncio.run(asyncio.wait_for(scenario(), 20))
    # asyncio.run дождался потока хода; в процессе его убивает os._exit, поэтому turn_seq
    # после конца потока не утверждается -- только снимок в момент hard_exit
    assert exits == [(130, [], 0)]
    assert list_slots(game.saves_root, game.world_id) == []
