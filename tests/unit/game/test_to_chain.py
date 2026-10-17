# ТО (docs/plan-to.md §1 п.3, Q1а): GameApp.chain_turn -- жёсткий отказ (PROHIBITED_CONTENT/
# BLOCKLIST/SPII) переключает рассказчика на следующую модель по narrator_chain (постоянно,
# models.json) и повторяет ход; цепочка кончилась / вне цепочки / refusal_chain=False -- меню.
import pytest
from game_kit import FactorySpy, make_app, scripted, text_step

from ai_dm.game.models import read_models
from ai_dm.game.turn import ERROR_MENU, REFUSAL_HINT
from ai_dm.llm.errors import MissingKey
from ai_dm.llm.mock import ScriptedAdapter

FLASH = "gemini-3.8-flash"
ARGON = "gemini-4-argon"
PREVIEW = "gemini-3-flash-preview"
LITE = "gemini-3.5-flash-lite"
HARD = {"stop": "refusal", "stop_detail": "PROHIBITED_CONTENT"}
SOFT = {"stop": "refusal"}
NETWORK = [{"error": "transient", "message": "сеть"}] * 4


class ChainFactory:
    # adapter_factory: на каждую модель -- свой ScriptedAdapter по шагам из steps (иначе рассказ)
    def __init__(self, steps=None):
        self.steps = steps or {}
        self.calls = []
        self.made = {}

    def __call__(self, provider, model):
        self.calls.append((provider, model))
        steps = list(self.steps.get(model, [text_step(f"Рассказ {model}.")]))
        adapter = ScriptedAdapter(steps, provider=provider, model=model)
        self.made[model] = adapter
        return adapter


def app_on(registry, tmp_path, steps, factory, model=FLASH, chain=True):
    adapter = ScriptedAdapter(steps, provider="gemini", model=model)
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory, auto_reports=False)
    app.refusal_chain = chain
    return app, adapter


def switch_lines(reply):
    return [line for line in reply.lines if "переключаюсь" in line]


def current_model(app):
    return app.runner.adapter.info().model


# успешный переход

def test_hard_refusal_switches_to_next_model_and_plays_the_turn(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [HARD], factory)
    reply = app.handle("Иду")
    assert reply.narration == f"Рассказ {ARGON}."
    assert app.pending is None
    assert reply.turn.committed is True
    assert current_model(app) == ARGON
    assert len(flash.requests) == 1
    assert factory.calls == [("gemini", ARGON)]


def test_switch_is_permanent_in_models_json(registry, tmp_path):
    app, _ = app_on(registry, tmp_path, [HARD], ChainFactory())
    app.handle("Иду")
    stored = read_models(tmp_path, "w1")
    assert stored["narrator"] == {"provider": "gemini", "model": ARGON}


def test_switch_line_names_old_new_model_and_detail(registry, tmp_path):
    app, _ = app_on(registry, tmp_path, [HARD], ChainFactory())
    lines = switch_lines(app.handle("Иду"))
    assert len(lines) == 1
    assert FLASH in lines[0]
    assert ARGON in lines[0]
    assert "PROHIBITED_CONTENT" in lines[0]


@pytest.mark.parametrize("detail", ["BLOCKLIST", "SPII"])
def test_other_hard_details_switch_too(registry, tmp_path, detail):
    step = {"stop": "refusal", "stop_detail": detail}
    app, _ = app_on(registry, tmp_path, [step], ChainFactory())
    reply = app.handle("Иду")
    assert current_model(app) == ARGON
    assert detail in switch_lines(reply)[0]


def test_retry_request_goes_to_new_model(registry, tmp_path):
    factory = ChainFactory()
    app, _ = app_on(registry, tmp_path, [HARD], factory)
    app.handle("Иду")
    assert factory.made[ARGON].requests[0].model == ARGON


def test_refused_turn_leaves_no_trace_in_bundle(registry, tmp_path):
    app, _ = app_on(registry, tmp_path, [HARD], ChainFactory())
    app.handle("Иду")
    assert app.bundle.session.turn_seq == 1
    assert len(app.bundle.memory.recent_turns) == 1


def test_two_models_refuse_third_plays(registry, tmp_path):
    factory = ChainFactory({ARGON: [HARD]})
    app, _ = app_on(registry, tmp_path, [HARD], factory)
    reply = app.handle("Иду")
    assert len(switch_lines(reply)) == 2
    assert current_model(app) == PREVIEW
    assert reply.narration == f"Рассказ {PREVIEW}."
    assert read_models(tmp_path, "w1")["narrator"]["model"] == PREVIEW


def test_model_options_count_from_new_model(registry, tmp_path):
    app, _ = app_on(registry, tmp_path, [HARD], ChainFactory())
    app.handle("Иду")
    assert app.model_options()[0] == f"gemini:{PREVIEW}"


def test_world_and_summarizer_adapters_are_not_changed(registry, tmp_path):
    factory = ChainFactory()
    app, _ = app_on(registry, tmp_path, [HARD], factory)
    world = ScriptedAdapter([], provider="gemini", model="gemini-w")
    summarizer = ScriptedAdapter([], provider="gemini", model="gemini-s")
    app.runner.world_adapter = world
    app.runner.summarizer_adapter = summarizer
    app.handle("Иду")
    assert app.runner.world_adapter is world
    assert app.runner.summarizer_adapter is summarizer
    assert factory.calls == [("gemini", ARGON)]


# цепочка исчерпана

def test_all_models_refuse_gives_four_calls_three_lines_and_menu(registry, tmp_path):
    factory = ChainFactory({ARGON: [HARD], PREVIEW: [HARD], LITE: [HARD]})
    app, flash = app_on(registry, tmp_path, [HARD], factory)
    reply = app.handle("Иду")
    calls = len(flash.requests) + sum(len(a.requests) for a in factory.made.values())
    assert calls == 4
    assert len(switch_lines(reply)) == 3
    assert app.pending == "error_menu"
    assert reply.turn.menu == ERROR_MENU
    assert reply.hint == REFUSAL_HINT
    assert current_model(app) == LITE


def test_last_model_in_chain_refusing_gives_menu_without_line(registry, tmp_path):
    factory = ChainFactory()
    app, _ = app_on(registry, tmp_path, [HARD], factory, model=LITE)
    reply = app.handle("Иду")
    assert switch_lines(reply) == []
    assert app.pending == "error_menu"
    assert reply.hint == REFUSAL_HINT
    assert factory.calls == []


def test_model_outside_chain_gives_menu_at_once(registry, tmp_path):
    factory = ChainFactory()
    adapter = scripted([HARD])
    app = make_app(registry, tmp_path, adapter, adapter_factory=factory, auto_reports=False)
    app.refusal_chain = True
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert switch_lines(reply) == []
    assert factory.calls == []
    assert len(adapter.requests) == 1


# выключено / другие сбои

def test_refusal_chain_off_gives_menu_at_once(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [HARD], factory, chain=False)
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert switch_lines(reply) == []
    assert factory.calls == []
    assert len(flash.requests) == 1


def test_refusal_chain_is_on_by_default(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([HARD]), adapter_factory=ChainFactory())
    assert app.refusal_chain is True


def test_soft_refusal_retries_with_note_and_does_not_switch(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [SOFT, SOFT], factory)
    reply = app.handle("Иду")
    assert len(flash.requests) == 2
    assert app.pending == "error_menu"
    assert switch_lines(reply) == []
    assert factory.calls == []


def test_safety_refusal_does_not_switch(registry, tmp_path):
    safety = {"stop": "refusal", "stop_detail": "SAFETY"}
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [safety, safety], factory)
    app.handle("Иду")
    assert len(flash.requests) == 2
    assert factory.calls == []


def test_network_failure_does_not_switch(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, NETWORK, factory)
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert switch_lines(reply) == []
    assert factory.calls == []


# сбой самого перехода

def test_missing_key_shows_error_and_stops_the_loop(registry, tmp_path):
    factory = FactorySpy(error=MissingKey("нет ключа Gemini"))
    app, flash = app_on(registry, tmp_path, [HARD], factory)
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert any("нет ключа Gemini" in line for line in reply.lines)
    assert switch_lines(reply) == []
    assert len(factory.calls) == 1
    assert current_model(app) == FLASH
    assert read_models(tmp_path, "w1") == {}
    assert reply.hint == REFUSAL_HINT


def test_model_without_price_shows_error_and_stops(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [HARD], factory)
    del app.settings.app.prices[ARGON]
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert any(ARGON in line and "нет цены" in line for line in reply.lines)
    assert switch_lines(reply) == []
    assert current_model(app) == FLASH
    assert len(flash.requests) == 1


# повтор из меню

def test_retry_from_menu_after_hard_refusal_switches(registry, tmp_path):
    factory = ChainFactory()
    app, flash = app_on(registry, tmp_path, [HARD, HARD], factory, chain=False)
    app.handle("Иду")
    assert app.pending == "error_menu"
    app.refusal_chain = True
    reply = app.choose("retry")
    assert app.pending is None
    assert current_model(app) == ARGON
    assert len(switch_lines(reply)) == 1
    assert reply.narration == f"Рассказ {ARGON}."


def test_retry_from_menu_after_exhausted_chain_gives_menu_again(registry, tmp_path):
    factory = ChainFactory()
    app, _ = app_on(registry, tmp_path, [HARD, HARD], factory, model=LITE)
    app.handle("Иду")
    reply = app.choose("retry")
    assert app.pending == "error_menu"
    assert reply.hint == REFUSAL_HINT
