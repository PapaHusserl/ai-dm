# AD1, W2: исключение при отрисовке хода не роняет TUI: заметка в ленте, ввод снова активен.
import asyncio


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


def break_session(monkeypatch, name, message="сломалось"):
    import ai_dm.ui.session as module

    def broken(*args, **kwargs):
        raise RuntimeError(message)

    monkeypatch.setattr(module, name, broken)


def test_render_failure_puts_note_into_feed(registry, tmp_path, tui, monkeypatch):
    app, game = tui.app(registry, tmp_path)
    break_session(monkeypatch, "reply_blocks")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.flat(tui.text_of(app.query_one("#feed")))

    feed = run(app, steps)
    assert "Ход сделан, но экран не обновился: сломалось" in feed
    assert game.bundle.session.turn_seq == 1


def test_render_failure_keeps_input_active(registry, tmp_path, tui, monkeypatch):
    app, _ = tui.app(registry, tmp_path)
    break_session(monkeypatch, "reply_blocks")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return app.query_one("#input").disabled

    assert run(app, steps) is False


def test_failure_before_turn_puts_note_into_feed_and_skips_turn(
    registry, tmp_path, tui, monkeypatch
):
    app, game = tui.app(registry, tmp_path)
    break_session(monkeypatch, "loot_snapshot")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.flat(tui.text_of(app.query_one("#feed")))

    feed = run(app, steps)
    assert "Ошибка хода: сломалось" in feed
    assert game.bundle.session.turn_seq == 0


def test_secret_is_hidden_in_feed(registry, tmp_path, tui, monkeypatch):
    app, _ = tui.app(registry, tmp_path)
    app.session.secrets = ("sk-ant-secret-123",)
    break_session(monkeypatch, "reply_blocks", "ключ sk-ant-secret-123")

    async def steps(app, pilot):
        await tui.submit(app, pilot)
        return tui.text_of(app.query_one("#feed"))

    assert "sk-ant-secret-123" not in run(app, steps)
