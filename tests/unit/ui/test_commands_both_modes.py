# Этап 5, P4 (STAGE5-PLAN, «P4»): каждая команда из HELP отвечает в простом режиме (ScriptedInput)
# и в TUI (Pilot): непустой ответ без ошибки; /retire -- заглушка.
# Список команд берётся из HELP: новая команда без теста роняет test_every_help_command_is_covered.
# Допущения: ответ команды (первые слова reply.lines[0]) виден на экране TUI (лента или модалка);
# /quit закрывает TUI (app.closing). Хелперы свои -- фикстура tui живёт в tui/conftest.py.
import asyncio

import pytest
from ui_kit import play, text_app, text_step

from ai_dm.game.commands import HELP

COMMANDS = ["/" + name for name in HELP]
STUBS = {"/retire": "этапе 9"}
ERROR = "Ошибка хода"
SIZE = (140, 40)


def reference(registry, tmp_path, command):
    # ответ игры на команду в чистом GameApp, отдельный каталог
    return text_app(registry, tmp_path / "ref", [text_step()]).handle(command)


def first_words(reply, count=3):
    if reply.lines[0].startswith("Сессия"):
        return "Сессия"  # /cost в TUI -- таблица, строка итога разбита по столбцам
    return " ".join(reply.lines[0].split()[:count])


def flat(text):
    return " ".join(text.split())


def simple_text(registry, tmp_path, command):
    app = text_app(registry, tmp_path / "simple", [text_step()])
    return flat(play(app, [command]).text)


def tui_run(registry, tmp_path, command):
    # -> (видимый текст экрана + лента, closing)
    from ai_dm.ui.session import PlaySession
    from ai_dm.ui.tui.app import AiDmApp

    app = AiDmApp(PlaySession(text_app(registry, tmp_path / "tui", [text_step()])))

    async def scenario():
        async with app.run_test(size=SIZE) as pilot:
            await pilot.pause()
            app.query_one("#input").value = command
            await pilot.press("enter")
            await app.workers.wait_for_complete()
            await pilot.pause()
            rows = [strip.text for strip in app.screen._compositor.render_strips()]
            lines = "\n".join(strip.text for strip in app.query_one("#feed").lines)
            return flat("\n".join(rows) + "\n" + lines), app.closing

    return asyncio.run(scenario())


def test_every_help_command_is_covered():
    from ai_dm.game.commands import COMMANDS as HANDLERS

    assert sorted(HANDLERS) == sorted(HELP)
    assert set(STUBS) <= set(COMMANDS)


@pytest.mark.parametrize("command", COMMANDS)
def test_command_answers_in_simple_mode(registry, tmp_path, command):
    expected = reference(registry, tmp_path, command)
    text = simple_text(registry, tmp_path, command)
    assert expected.lines
    assert first_words(expected) in text
    assert ERROR not in text


@pytest.mark.parametrize("command", COMMANDS)
def test_command_answers_in_tui(registry, tmp_path, command):
    expected = reference(registry, tmp_path, command)
    text, closing = tui_run(registry, tmp_path, command)
    # живой прогон 1: окно /model в TUI -- список выбора, а не справка
    words = {"/model": "Модель рассказчика", "/inv": "Предмет (Enter"}.get(command)
    # 96а П2: окно /inv -- список предметов с действиями, а не справка
    words = words or first_words(expected)
    assert words in text
    assert ERROR not in text
    assert closing is (command == "/quit")


@pytest.mark.parametrize("command", sorted(STUBS))
def test_stub_is_the_same_in_both_modes(registry, tmp_path, command):
    simple = simple_text(registry, tmp_path, command)
    tui, _ = tui_run(registry, tmp_path, command)
    stub = flat(reference(registry, tmp_path, command).lines[0])
    assert STUBS[command] in stub
    assert stub in simple
    assert stub in tui
