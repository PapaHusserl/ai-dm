# Шаг 190, П2: окно ввода ключа API в TUI -- KeyApp (старт без ключа) и KeyModal по /key в игре.
# Ожидание -- из плана (Тестовые сценарии, П2): провайдер цифрой, поле скрывает ввод,
# итоговая строка с хвостом ключа, Esc -- отмена без записи,
# /key открывает окно, rekey после сохранения.
# Pilot через asyncio.run; сети нет: verify -- инъекция KeyDeps.verify. Живых вызовов нет.
import asyncio
import sys
import threading
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import FactorySpy  # noqa: E402
from ui_kit import build_app  # noqa: E402

from ai_dm.config.app import load_settings  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.ui.key_session import KeyDeps, KeySession  # noqa: E402
from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402
from ai_dm.ui.tui.key_modal import KeyApp, KeyModal  # noqa: E402

KEY = "sk-or-v1-abcdef1234"
OTHER_KEY = "sk-ant-zzzz9876"


class Verify:
    def __init__(self, *verdicts):
        self.verdicts = list(verdicts)

    def __call__(self, provider, key, app_cfg):
        return self.verdicts.pop(0)


class GateVerify:
    # барьер: проверка ключа сообщает «вошла» и ждёт release (с потолком, чтобы тест не завис)
    def __init__(self):
        self.entered = threading.Event()
        self.release = threading.Event()

    def __call__(self, provider, key, app_cfg):
        self.entered.set()
        assert self.release.wait(10)
        return "ok"


def key_session(tmp_path, *verdicts, verify=None, dotenv_text=None, remember=False):
    dotenv = tmp_path / "cfg" / ".env"
    if dotenv_text is not None:
        dotenv.parent.mkdir(parents=True)
        dotenv.write_text(dotenv_text, encoding="utf-8")
    deps = KeyDeps(
        load_settings().app, {}, dotenv, [], verify or Verify(*(verdicts or ("ok",)))
    )
    return KeySession(deps, remember=remember)


def run(app, steps, size=(140, 40)):
    async def scenario():
        async with app.run_test(size=size) as pilot:
            await pilot.pause()
            return await steps(app, pilot)

    return asyncio.run(scenario())


async def settle(app, pilot):
    await app.workers.wait_for_complete()
    await pilot.pause()


async def type_key(app, pilot, text):
    entry = app.screen.query_one("#key-input")
    entry.value = text
    await pilot.press("enter")
    await settle(app, pilot)


def key_text(tui, app):
    return tui.flat(tui.text_of(app.screen.query_one("#key-text")))


def game_app(registry, tmp_path, session, with_factory=True):
    adapter = ScriptedAdapter([], provider="anthropic", model="m")
    factory = FactorySpy()
    game = build_app(registry, tmp_path, adapter, adapter_factory=factory, model="m")
    app = AiDmApp(PlaySession(game), key_factory=(lambda: session) if with_factory else None)
    return app, factory


# старт без ключа: KeyApp

def test_start_shows_intro_in_text(tmp_path, tui):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        return key_text(tui, app)

    assert "Для игры нужен ключ API." in run(app, steps)


def test_start_menu_lists_providers_in_order(tmp_path):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        menu = app.screen.query_one("#key-menu")
        return [str(menu.get_option_at_index(i).prompt) for i in range(menu.option_count)]

    assert run(app, steps) == ["1. OpenRouter", "2. Gemini", "3. Anthropic", "4. OpenAI"]


def test_start_hides_key_input_and_shows_menu(tmp_path):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        return app.screen.query_one("#key-input").display, app.screen.query_one("#key-menu").display

    assert run(app, steps) == (False, True)


def test_digit_picks_provider_and_shows_masked_key_field(tmp_path, tui):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        entry = app.screen.query_one("#key-input")
        return entry.display, entry.password, app.screen.query_one("#key-menu").display, (
            key_text(tui, app)
        )

    shown, password, menu, text = run(app, steps)
    assert (shown, password, menu) == (True, True, False)
    assert "https://openrouter.ai/keys" in text


def test_digit_four_picks_openai_link(tmp_path, tui):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        await pilot.press("4")
        await settle(app, pilot)
        return key_text(tui, app)

    assert "https://platform.openai.com/api-keys" in run(app, steps)


def test_key_field_has_russian_placeholder(tmp_path):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        return app.screen.query_one("#key-input").placeholder

    assert run(app, steps) == strings.KEY_PLACEHOLDER


def test_typed_key_is_masked_in_text_and_field_cleared(tmp_path, tui):
    app = KeyApp(key_session(tmp_path, "invalid"))

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        return key_text(tui, app), app.screen.query_one("#key-input").value

    text, value = run(app, steps)
    assert KEY not in text
    assert strings.KEY_MASK in text
    assert value == ""


def test_valid_key_shows_saved_line_with_tail_only(tmp_path, tui):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        return key_text(tui, app), tui.visible_text(app)

    text, visible = run(app, steps)
    assert "Ключ …1234 сохранён в" in text
    assert KEY not in text
    assert KEY not in visible


def test_valid_key_is_written_to_dotenv(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)

    run(app, steps)
    assert (tmp_path / "cfg" / ".env").read_text(encoding="utf-8") == f"OPENROUTER_API_KEY={KEY}\n"


def test_after_save_input_and_menu_hidden_and_close_button_shown(tmp_path):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        screen = app.screen
        return (
            screen.query_one("#key-input").display,
            screen.query_one("#key-menu").display,
            screen.query_one("#modal-close").display,
        )

    assert run(app, steps) == (False, False, True)


def test_close_button_after_save_returns_saved_session(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        await pilot.press("enter")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is session
    assert session.saved is True
    assert session.provider == "openrouter"


def test_escape_after_save_still_returns_saved_session(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value.saved is True


def test_invalid_key_says_retry_and_keeps_field_open(tmp_path, tui):
    app = KeyApp(key_session(tmp_path, "invalid"))

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        return key_text(tui, app), app.screen.query_one("#key-input").display

    text, shown = run(app, steps)
    assert "Ключ не подошёл, ещё раз?" in text
    assert shown is True
    assert not (tmp_path / "cfg" / ".env").exists()


def test_invalid_then_valid_key_is_saved(tmp_path):
    session = key_session(tmp_path, "invalid", "ok")
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, "bad")
        await type_key(app, pilot, KEY)

    run(app, steps)
    assert session.saved is True
    assert KEY in (tmp_path / "cfg" / ".env").read_text(encoding="utf-8")


def test_unverified_key_is_saved_with_note(tmp_path, tui):
    app = KeyApp(key_session(tmp_path, ("unverified", "нет сети")))

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        return key_text(tui, app)

    text = run(app, steps)
    assert "Не проверил: нет сети, проверю на первом ходу." in text
    assert (tmp_path / "cfg" / ".env").exists()


def test_empty_input_is_ignored_and_stays_on_key_step(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, "   ")
        return session.state

    assert run(app, steps) == "key"
    assert not (tmp_path / "cfg" / ".env").exists()


def test_input_disabled_and_escape_ignored_while_key_is_checked(tmp_path):
    gate = GateVerify()
    session = key_session(tmp_path, verify=gate)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        entry = app.screen.query_one("#key-input")
        entry.value = KEY
        await pilot.press("enter")
        await asyncio.to_thread(gate.entered.wait, 10)
        await pilot.pause()
        await pilot.press("escape")
        await pilot.pause()
        busy = entry.disabled, isinstance(app.screen, KeyModal)
        gate.release.set()
        await settle(app, pilot)
        return busy

    assert run(app, steps) == (True, True)
    assert session.saved is True


def test_escape_at_start_returns_session_without_saved_and_no_file(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is session
    assert session.saved is False
    assert not (tmp_path / "cfg").exists()


def test_escape_at_key_step_writes_nothing(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await pilot.press("escape")
        await pilot.pause()

    run(app, steps)
    assert session.saved is False
    assert not (tmp_path / "cfg").exists()


def test_ctrl_c_returns_session_without_saved(tmp_path):
    session = key_session(tmp_path)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("ctrl+c")
        await pilot.pause()

    run(app, steps)
    assert app.return_value is session
    assert session.saved is False


def test_app_marks_shown_after_mount(tmp_path):
    app = KeyApp(key_session(tmp_path))

    async def steps(app, pilot):
        return app.shown

    assert run(app, steps) is True


def test_existing_key_asks_to_replace_and_no_leaves_file_untouched(tmp_path, tui):
    text = "# мой ключ\nOPENROUTER_API_KEY=old-key-1111\nOTHER=1\n"
    session = key_session(tmp_path, dotenv_text=text)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        asked = key_text(tui, app)
        await pilot.press("2")
        await settle(app, pilot)
        return asked

    asked = run(app, steps)
    assert "уже есть — заменить?" in asked
    assert (tmp_path / "cfg" / ".env").read_text(encoding="utf-8") == text
    assert session.saved is False


def test_existing_key_yes_replaces_only_its_line(tmp_path):
    text = "# мой ключ\nOPENROUTER_API_KEY=old-key-1111\nOTHER=1\n"
    session = key_session(tmp_path, dotenv_text=text)
    app = KeyApp(session)

    async def steps(app, pilot):
        await pilot.press("1")
        await settle(app, pilot)
        await pilot.press("1")
        await settle(app, pilot)
        await type_key(app, pilot, KEY)

    run(app, steps)
    expected = f"# мой ключ\nOPENROUTER_API_KEY={KEY}\nOTHER=1\n"
    assert (tmp_path / "cfg" / ".env").read_text(encoding="utf-8") == expected


# /key в игре: KeyModal поверх

def test_key_command_opens_key_modal(registry, tmp_path, tui):
    app, _ = game_app(registry, tmp_path, key_session(tmp_path / "k"))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        return len(app.screen_stack), isinstance(app.screen, KeyModal)

    assert run(app, steps) == (2, True)


def test_key_command_modal_has_title(registry, tmp_path, tui):
    app, _ = game_app(registry, tmp_path, key_session(tmp_path / "k"))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        return app.screen.query_one("#modal").border_title

    assert run(app, steps) == strings.KEY_TITLE


def test_key_command_keeps_reply_line_in_feed(registry, tmp_path, tui):
    app, _ = game_app(registry, tmp_path, key_session(tmp_path / "k"))

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        return tui.flat(tui.text_of(app.query_one("#feed")))

    assert "Ключ API: выберите провайдера." in run(app, steps)


def test_key_command_without_factory_says_unavailable_and_no_modal(registry, tmp_path, tui):
    app, _ = game_app(registry, tmp_path, None, with_factory=False)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        return len(app.screen_stack), tui.flat(tui.text_of(app.query_one("#feed")))

    depth, feed = run(app, steps)
    assert depth == 1
    assert strings.KEY_UNAVAILABLE in feed


def test_escape_in_game_modal_closes_without_rekey_and_focuses_input(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, factory = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("escape")
        await pilot.pause()
        return len(app.screen_stack), app.focused is app.query_one("#input")

    assert run(app, steps) == (1, True)
    assert factory.calls == []
    assert session.saved is False


def test_current_provider_key_in_game_rekeys_adapter_and_reports(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, factory = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")  # Anthropic -- провайдер рассказчика
        await settle(app, pilot)
        await type_key(app, pilot, OTHER_KEY)
        await pilot.press("escape")
        await settle(app, pilot)
        return tui.flat(tui.text_of(app.query_one("#feed"))), app.query_one("#input").disabled

    feed, disabled = run(app, steps)
    assert ("anthropic", "m") in factory.calls
    assert "Ключ anthropic подключён." in feed
    assert disabled is False


def test_rekey_does_not_leave_game_busy_and_modal_closed(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, _ = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")
        await settle(app, pilot)
        await type_key(app, pilot, OTHER_KEY)
        await pilot.press("escape")
        await settle(app, pilot)
        return app.busy, len(app.screen_stack)

    assert run(app, steps) == (False, 1)


def test_rekey_clears_busy_mark_in_status_bar(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, _ = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")
        await settle(app, pilot)
        await type_key(app, pilot, OTHER_KEY)
        await pilot.press("escape")
        await settle(app, pilot)
        return app.query_one("#status").busy

    assert run(app, steps) is False


def test_other_provider_key_in_game_is_saved_without_rekey(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, factory = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("2")  # Gemini -- не рассказчик
        await settle(app, pilot)
        await type_key(app, pilot, KEY)
        await pilot.press("escape")
        await settle(app, pilot)
        return tui.flat(tui.text_of(app.query_one("#feed")))

    feed = run(app, steps)
    assert factory.calls == []
    assert "Ключ gemini сохранён: сменить модель — /model." in feed
    assert KEY in (tmp_path / "k" / "cfg" / ".env").read_text(encoding="utf-8")


def test_key_entered_in_modal_does_not_start_a_game_turn(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, _ = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")
        await settle(app, pilot)
        await type_key(app, pilot, OTHER_KEY)
        return tui.flat(tui.text_of(app.query_one("#feed")))

    feed = run(app, steps)
    assert "Ты: " + OTHER_KEY not in feed
    assert "Ошибка хода" not in feed


def test_enter_key_runs_key_app_and_returns_its_result(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    session = key_session(tmp_path)
    monkeypatch.setattr(KeyApp, "run", lambda self: "итог")
    assert tui.enter_key(session) == "итог"


def test_enter_key_failure_before_first_frame_is_tui_start_error(tmp_path, monkeypatch):
    import pytest

    import ai_dm.ui.tui as tui

    def broken(self):
        raise RuntimeError("нет терминала")

    monkeypatch.setattr(KeyApp, "run", broken)
    with pytest.raises(tui.TuiStartError, match="нет терминала"):
        tui.enter_key(key_session(tmp_path))


def test_enter_key_failure_after_first_frame_is_reraised_as_is(tmp_path, monkeypatch):
    import pytest

    import ai_dm.ui.tui as tui

    def broken(self):
        self.shown = True
        raise RuntimeError("упало в игре")

    monkeypatch.setattr(KeyApp, "run", broken)
    with pytest.raises(RuntimeError, match="упало в игре"):
        tui.enter_key(key_session(tmp_path))


def test_enter_key_gives_the_session_to_key_app(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui

    got = []

    class SpyApp:
        shown = True

        def __init__(self, session):
            got.append(session)

        def run(self):
            return None

    monkeypatch.setattr(tui, "KeyApp", SpyApp)
    session = key_session(tmp_path)
    tui.enter_key(session)
    assert got == [session]


def spied_run_tui(monkeypatch, **kwargs):
    # PlaySession и AiDmApp -- шпионы с обязательными аргументами; возвращает, что им передали
    from types import SimpleNamespace

    import ai_dm.ui.tui as tui

    seen = {}

    class SpySession:
        def __init__(self, game, replay, secrets, opening):
            seen["session"] = {"game": game, "replay": replay, "secrets": secrets,
                               "opening": opening}

    class SpyApp:
        shown = True

        def __init__(self, session, startup, key_factory):
            seen["app"] = {"session": session, "startup": startup, "key_factory": key_factory}

        def run(self):
            return None

        def after_exit(self):
            return 0

    monkeypatch.setattr(tui, "PlaySession", SpySession)
    monkeypatch.setattr(tui, "AiDmApp", SpyApp)
    game = SimpleNamespace(secrets=["секрет"], audio=SimpleNamespace(stop=lambda: None))
    tui.run_tui(game, **kwargs)
    return game, seen


def test_run_tui_gives_game_and_its_secrets_to_session(monkeypatch):
    game, seen = spied_run_tui(monkeypatch)
    assert seen["session"]["game"] is game
    assert seen["session"]["secrets"] == ["секрет"]


def test_run_tui_replay_is_off_by_default(monkeypatch):
    _, seen = spied_run_tui(monkeypatch)
    assert seen["session"]["replay"] is False


def test_run_tui_gives_replay_and_opening_to_session(monkeypatch):
    _, seen = spied_run_tui(monkeypatch, replay=True, opening="Начало.")
    assert (seen["session"]["replay"], seen["session"]["opening"]) == (True, "Начало.")


def test_run_tui_gives_session_notes_and_key_factory_to_app(monkeypatch):
    def factory():
        return None

    _, seen = spied_run_tui(monkeypatch, notes=("заметка",), key_factory=factory)
    assert seen["app"]["key_factory"] is factory
    assert seen["app"]["startup"] == ("заметка",)


def test_digits_typed_key_by_key_go_to_field_not_to_game_choices(registry, tmp_path, tui):
    from ui_kit import OPUS, text_step

    offer = {"tool_calls": [{"id": "c1", "name": "offer_choices", "input": {
        "type": "offer_choices", "choices": ["Спросить про подвал", "Заказать эль"]}}]}
    adapter = ScriptedAdapter(
        [offer, text_step("Рассказ."), text_step("Раз."), text_step("Два.")],
        provider="anthropic", model=OPUS,
    )
    game = build_app(registry, tmp_path, adapter, adapter_factory=FactorySpy())
    session = key_session(tmp_path / "k")
    app = AiDmApp(PlaySession(game), key_factory=lambda: session)
    typed = "1ab2cd34"

    async def steps(app, pilot):
        await tui.submit(app, pilot, "Здравствуйте")
        assert tui.shown(app.query_one("#choices"))
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")
        await settle(app, pilot)
        await pilot.press(*typed)
        await pilot.pause()
        field = app.screen.query_one("#key-input").value
        return field, tui.flat(tui.text_of(app.query_one("#feed")))

    field, feed = run(app, steps)
    assert field == typed
    assert "Ты: 1" not in feed
    assert "Ты: 2" not in feed
    assert typed not in feed
    assert len(adapter.requests) == 2


def test_key_modal_is_in_modals():
    from ai_dm.ui.tui.app import MODALS

    assert KeyModal in MODALS


def test_key_never_appears_in_game_screen(registry, tmp_path, tui):
    session = key_session(tmp_path / "k")
    app, _ = game_app(registry, tmp_path, session)

    async def steps(app, pilot):
        await tui.submit(app, pilot, "/key")
        await pilot.press("3")
        await settle(app, pilot)
        await type_key(app, pilot, OTHER_KEY)
        await pilot.press("escape")
        await settle(app, pilot)
        return tui.visible_text(app) + tui.text_of(app.query_one("#feed"))

    assert OTHER_KEY not in run(app, steps)
