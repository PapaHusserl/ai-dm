# 19ф Ф1 (docs/19F-PLAN.md п.1 Ф1) на уровне GameApp: таймаут -- меню ошибки после одного вызова,
# в подсказке «таймаут», сеть как и раньше -- обе роли при смене модели (регресс Т60).
from game_kit import FactorySpy, make_app, text_step
from test_t60_menu import ARGON, gemini

from ai_dm.game.turn import ERROR_MENU

TIMEOUT = {"error": "transient", "message": "The read operation timed out", "timeout": True}


def timeout_app(registry, tmp_path, steps=None):
    adapter = gemini(steps or [TIMEOUT, text_step("не должен быть вызван")])
    app = make_app(registry, tmp_path, adapter, adapter_factory=FactorySpy())
    return app, adapter


def test_timeout_opens_error_menu_after_one_call(registry, tmp_path):
    app, adapter = timeout_app(registry, tmp_path)
    reply = app.handle("Иду")
    assert reply.pending == "error_menu"
    assert reply.menu == ERROR_MENU
    assert len(adapter.requests) == 1


def test_timeout_menu_hint_mentions_timeout(registry, tmp_path):
    app, _ = timeout_app(registry, tmp_path)
    assert "таймаут" in app.handle("Иду").hint


def test_timeout_turn_is_not_committed(registry, tmp_path):
    app, _ = timeout_app(registry, tmp_path)
    reply = app.handle("Иду")
    assert reply.turn.committed is False
    assert reply.turn.failure.reason == "network"


def test_timeout_remembers_network_reason(registry, tmp_path):
    app, _ = timeout_app(registry, tmp_path)
    app.handle("Иду")
    assert app.failed_reason == "network"


def test_timeout_switch_model_changes_both_roles(registry, tmp_path):
    app, _ = timeout_app(registry, tmp_path)
    app.handle("Иду")
    app.choose("switch_model")
    assert app.switch_role == "both"
    app.choose(ARGON)
    assert app.runner.summarizer_model == "gemini-4-argon"


def test_timeout_menu_offers_next_model_first(registry, tmp_path):
    app, _ = timeout_app(registry, tmp_path)
    app.handle("Иду")
    assert app.choose("switch_model").menu[0] == ARGON


def test_retry_after_timeout_repeats_input(registry, tmp_path):
    app, adapter = timeout_app(registry, tmp_path, [TIMEOUT, text_step("Дошли.")])
    app.handle("Иду в лес")
    reply = app.choose("retry")
    assert reply.narration == "Дошли."
    assert len(adapter.requests) == 2
