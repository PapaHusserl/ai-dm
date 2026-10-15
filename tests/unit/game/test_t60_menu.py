# Т60 «Сеть» (docs/T60-PLAN.md п.1.7, раздел 10): меню ошибки.
#   Авто-переключения нет -- только меню: порядок моделей (следующая по narrator_chain от текущей
#   модели меняемой роли -- первой) и роли: сеть у хода -> выбранная модель обеим ролям
#   (narrator + summarizer), refusal/fatal/invalid -> только рассказчик, сбой границы
#   (failed_role == "summarizer") -> только summarizer.
import pytest
from game_kit import FactorySpy, make_app, scripted, text_step

from ai_dm.game.models import model_options, read_models
from ai_dm.llm.errors import MissingKey
from ai_dm.llm.mock import ScriptedAdapter

FLASH = "gemini:gemini-3.8-flash"
ARGON = "gemini:gemini-4-argon"
PREVIEW = "gemini:gemini-3-flash-preview"
LITE = "gemini:gemini-3.5-flash-lite"
NETWORK = [{"error": "transient", "message": "сеть"}] * 4
FATAL = [{"error": "fatal", "message": "ключ"}]
REFUSAL = [{"stop": "refusal"}] * 2


def gemini(steps, model="gemini-3.8-flash"):
    return ScriptedAdapter(steps, provider="gemini", model=model)


def failed_app(registry, tmp_path, steps, model="gemini-3.8-flash", factory=None):
    factory = factory or FactorySpy()
    app = make_app(registry, tmp_path, gemini(steps, model), adapter_factory=factory)
    app.handle("Иду")
    assert app.pending == "error_menu"
    return app, factory


def models_of(app):
    narrator = app.runner.adapter.info()
    summarizer = app.runner.summarizer_adapter
    return (
        f"{narrator.provider}:{narrator.model}",
        None if summarizer is None else f"{summarizer.info().provider}:{summarizer.info().model}",
    )


# порядок моделей в меню

@pytest.mark.parametrize(
    ("model", "first"),
    [("gemini-3.8-flash", ARGON), ("gemini-4-argon", PREVIEW), ("gemini-3-flash-preview", LITE)],
)
def test_menu_offers_next_in_chain_first(registry, tmp_path, model, first):
    app, _ = failed_app(registry, tmp_path, NETWORK, model)
    reply = app.choose("switch_model")
    assert reply.pending == "model_choice"
    assert reply.menu[0] == first


def test_menu_is_plain_when_narrator_is_last_in_chain(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK, "gemini-3.5-flash-lite")
    assert app.choose("switch_model").menu == model_options(app.settings.app)


def test_menu_is_plain_when_narrator_is_outside_chain(registry, tmp_path):
    app = make_app(
        registry, tmp_path, scripted(FATAL), adapter_factory=FactorySpy(),
    )
    app.handle("Иду")
    assert app.choose("switch_model").menu == model_options(app.settings.app)


def test_menu_keeps_every_option_once(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    menu = app.choose("switch_model").menu
    assert sorted(menu) == sorted(model_options(app.settings.app))
    assert len(menu) == len(set(menu))


def test_menu_order_follows_the_configured_chain(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.settings.app.llm.narrator_chain = [FLASH, LITE, ARGON]
    assert app.choose("switch_model").menu[0] == LITE


def test_menu_order_for_summarizer_follows_summarizer_model(registry, tmp_path):
    factory = FactorySpy()
    app, _ = failed_app(registry, tmp_path, FATAL, factory=factory)
    app.runner.summarizer_adapter = factory(*ARGON.split(":"))
    app.runner.failed_role = "summarizer"
    assert app.choose("switch_model").menu[0] == PREVIEW


def test_model_options_method_puts_next_in_chain_first(registry, tmp_path):
    app = make_app(registry, tmp_path, gemini([text_step()]), adapter_factory=FactorySpy())
    assert app.model_options()[0] == ARGON
    assert sorted(app.model_options()) == sorted(model_options(app.settings.app))


def test_model_command_lists_next_in_chain_first(registry, tmp_path):
    app = make_app(registry, tmp_path, gemini([text_step()]), adapter_factory=FactorySpy())
    text = "\n".join(app.handle("/model").lines)
    assert "Доступно: " + ARGON + "," in text


def test_model_options_method_is_plain_for_model_outside_chain(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step()]), adapter_factory=FactorySpy())
    assert app.model_options() == model_options(app.settings.app)


def test_model_options_method_follows_narrator_after_model_command(registry, tmp_path):
    app = make_app(registry, tmp_path, gemini([text_step()]), adapter_factory=FactorySpy())
    app.handle(f"/model narrator {ARGON}")
    assert app.model_options()[0] == PREVIEW


# какие роли меняет выбор

def test_network_failure_sets_both_roles(registry, tmp_path):
    app, factory = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    assert app.switch_role == "both"
    reply = app.choose(ARGON)
    assert models_of(app) == (ARGON, ARGON)
    assert app.runner.summarizer_model == "gemini-4-argon"
    assert reply.pending == "error_menu"
    assert factory.calls == [("gemini", "gemini-4-argon")] * 2


def test_both_roles_line_names_both_and_the_key(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    reply = app.choose(ARGON)
    assert reply.lines == [f"Модели рассказчика и summarizer: {ARGON}."]


def test_both_roles_remember_only_narrator_in_models_json(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    app.choose(ARGON)
    stored = read_models(tmp_path, "w1")
    assert stored == {"narrator": {"provider": "gemini", "model": "gemini-4-argon"}}


def test_retry_after_both_switch_plays_on_new_narrator(registry, tmp_path):
    app, factory = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    app.choose(ARGON)
    app.choose("retry")
    assert factory.made[0].requests[0].model == "gemini-4-argon"


@pytest.mark.parametrize(("name", "steps"), [("refusal", REFUSAL), ("fatal", FATAL)])
def test_other_failures_set_only_narrator(registry, tmp_path, name, steps):
    app, factory = failed_app(registry, tmp_path, steps)
    app.choose("switch_model")
    assert app.switch_role == "narrator"
    reply = app.choose(ARGON)
    assert models_of(app) == (ARGON, None)
    assert reply.lines == [f"Модель рассказчика: {ARGON}."]
    assert factory.calls == [("gemini", "gemini-4-argon")]


def test_invalid_failure_sets_only_narrator(registry, tmp_path):
    from game_kit import BAD_CHECK, tools_step

    app, _ = failed_app(registry, tmp_path, [tools_step(BAD_CHECK)] * 3)
    app.choose("switch_model")
    assert app.switch_role == "narrator"


def test_summarizer_boundary_failure_sets_only_summarizer(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.runner.failed_role = "summarizer"
    app.choose("switch_model")
    assert app.switch_role == "summarizer"
    reply = app.choose(ARGON)
    assert models_of(app) == (FLASH, ARGON)
    assert reply.lines == [f"Модель summarizer: {ARGON}."]
    assert read_models(tmp_path, "w1") == {}


def test_failed_reason_is_remembered_from_the_turn(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    assert app.failed_reason == "network"


def test_failed_reason_is_cleared_by_successful_turn(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK + [text_step("Дошло.")])
    app.choose("retry")
    assert app.pending is None
    assert app.failed_reason is None


def test_old_network_reason_does_not_leak_into_next_failure(registry, tmp_path):
    steps = NETWORK + [text_step("Дошло.")] + FATAL
    app, _ = failed_app(registry, tmp_path, steps)
    app.choose("retry")
    app.handle("Дальше")
    assert app.pending == "error_menu"
    app.choose("switch_model")
    assert app.switch_role == "narrator"


# ошибки при смене

def test_both_roles_factory_error_gives_error_line_and_changes_nothing(registry, tmp_path):
    factory = FactorySpy(error=MissingKey("нет ключа"))
    app, _ = failed_app(registry, tmp_path, NETWORK, factory=factory)
    before = models_of(app)
    app.choose("switch_model")
    reply = app.choose(ARGON)
    assert "нет ключа" in "\n".join(reply.lines)
    assert reply.pending == "model_choice"
    assert models_of(app) == before
    assert read_models(tmp_path, "w1") == {}


# Q3 (б): сама игра модель не меняет

def test_network_failure_does_not_switch_model_by_itself(registry, tmp_path):
    app, factory = failed_app(registry, tmp_path, NETWORK)
    assert factory.calls == []
    assert models_of(app) == (FLASH, None)
    assert read_models(tmp_path, "w1") == {}


def test_network_failure_keeps_error_menu_and_full_delays(registry, tmp_path):
    app = make_app(registry, tmp_path, gemini(NETWORK), adapter_factory=FactorySpy())
    reply = app.handle("Иду")
    assert reply.menu == ["retry", "switch_model", "save_and_quit"]
    assert len(app.adapter.steps) == 0


# ветка both: общий адаптер, без лишнего backup

def test_both_roles_share_one_adapter(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    app.choose(ARGON)
    assert app.runner.summarizer_adapter is app.runner.adapter
    assert app.runner.summarizer_model == "gemini-4-argon"


def test_both_roles_make_no_backup_summarizer(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    app.choose(ARGON)
    app.runner.new_summarizer_session = type(app.runner).new_summarizer_session.__get__(app.runner)
    assert app.runner.new_summarizer_session().backup is None


def test_both_roles_models_json_has_only_narrator_key(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.choose("switch_model")
    app.choose(ARGON)
    assert list(read_models(tmp_path, "w1")) == ["narrator"]


def test_both_roles_failed_switch_keeps_summarizer_adapter(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK, factory=FactorySpy(error=MissingKey("x")))
    app.choose("switch_model")
    app.choose(ARGON)
    assert app.runner.summarizer_adapter is None


# load сбрасывает причину сбоя

def test_load_clears_failed_reason(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.save_current("auto")
    assert app.failed_reason == "network"
    app.load("auto")
    assert app.failed_reason is None


def test_after_load_switch_model_is_narrator_only(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.save_current("auto")
    app.load("auto")
    app.pending = "error_menu"
    app.choose("switch_model")
    assert app.switch_role == "narrator"


def test_failed_load_keeps_failed_reason(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK)
    app.load("no-such-slot")
    assert app.failed_reason == "network"


# switch_role после выбора

def summarizer_choice(registry, tmp_path, factory=None):
    factory = factory or FactorySpy()
    app, _ = failed_app(registry, tmp_path, NETWORK, factory=factory)
    app.runner.summarizer_adapter = FactorySpy()(*ARGON.split(":"))
    app.runner.failed_role = "summarizer"
    app.choose("switch_model")
    return app


def test_switch_role_returns_to_narrator_after_successful_choice(registry, tmp_path):
    app = summarizer_choice(registry, tmp_path)
    assert app.switch_role == "summarizer"
    app.choose(PREVIEW)
    assert app.switch_role == "narrator"


def test_model_command_after_summarizer_choice_is_ordered_from_narrator(registry, tmp_path):
    app = summarizer_choice(registry, tmp_path)
    app.choose(PREVIEW)
    assert app.model_options()[0] == ARGON


def test_switch_role_is_kept_when_factory_fails(registry, tmp_path):
    app = summarizer_choice(registry, tmp_path, factory=FactorySpy(error=MissingKey("x")))
    app.choose(PREVIEW)
    assert app.switch_role == "summarizer"


def test_switch_role_both_is_kept_when_factory_fails(registry, tmp_path):
    app, _ = failed_app(registry, tmp_path, NETWORK, factory=FactorySpy(error=MissingKey("x")))
    app.choose("switch_model")
    app.choose(ARGON)
    assert app.switch_role == "both"
