# ТО (docs/plan-to.md §1 п.9): GameApp.set_narrator -- world и summarizer следуют за провайдером
# рассказчика (профиль нового); ошибка фабрики роли -- её текст, рассказчик не сменён.
import pytest
from game_kit import FactorySpy, ReactiveAdapter, make_app

from ai_dm.llm.errors import MissingKey
from ai_dm.llm.mock import ScriptedAdapter

WORLD = "world-model-x"
SUMMARIZER = "summarizer-model-x"


def adapter_of(provider, model):
    return ScriptedAdapter([], provider=provider, model=model)


def make(registry, tmp_path, provider, factory):
    model = "claude-opus-5-5" if provider == "anthropic" else "gemini-3.8-flash"
    narrator = ReactiveAdapter(provider=provider, model=model)
    app = make_app(
        registry, tmp_path, narrator, adapter_factory=factory, use_stored_model=False,
    )
    profiles = app.settings.app.profiles
    for name in ("anthropic", "gemini", "openai"):
        profiles[name].world.model = f"{name}-{WORLD}"
        profiles[name].summarizer.model = f"{name}-{SUMMARIZER}"
    app.runner.world_adapter = adapter_of(provider, "old-world")
    app.runner.summarizer_adapter = adapter_of(provider, "old-summarizer")
    app.runner.world_model = "old-world"
    app.runner.summarizer_model = "old-summarizer"
    return app


@pytest.mark.parametrize(
    ("start", "target", "key"),
    [
        ("anthropic", "gemini", "gemini:gemini-3.8-flash"),
        ("gemini", "anthropic", "anthropic:claude-sonnet-5-5"),
        ("gemini", "openai", "openai:gpt-6.1-sol"),
    ],
)
def test_set_narrator_moves_world_and_summarizer_to_new_provider_profile(
    registry, tmp_path, start, target, key
):
    factory = FactorySpy()
    app = make(registry, tmp_path, start, factory)
    assert app.set_narrator(key) is None
    assert app.runner.world_model == f"{target}-{WORLD}"
    assert app.runner.summarizer_model == f"{target}-{SUMMARIZER}"
    assert app.runner.world_adapter.info().model == f"{target}-{WORLD}"
    assert app.runner.summarizer_adapter.info().model == f"{target}-{SUMMARIZER}"
    assert app.runner.world_adapter.info().provider == target


def test_set_narrator_on_same_provider_keeps_world_and_summarizer(registry, tmp_path):
    app = make(registry, tmp_path, "gemini", FactorySpy())
    world, summarizer = app.runner.world_adapter, app.runner.summarizer_adapter
    assert app.set_narrator("gemini:gemini-4-argon") is None
    assert app.runner.world_adapter is world
    assert app.runner.summarizer_adapter is summarizer
    assert app.runner.world_model == "old-world"
    assert app.runner.summarizer_model == "old-summarizer"


class FailingFor(FactorySpy):
    def __init__(self, bad_model, error):
        super().__init__()
        self.bad_model = bad_model
        self.failure = error

    def __call__(self, provider, model):
        if model == self.bad_model:
            self.calls.append((provider, model))
            raise self.failure
        return super().__call__(provider, model)


@pytest.mark.parametrize("bad", [f"gemini-{WORLD}", f"gemini-{SUMMARIZER}"])
def test_role_factory_missing_key_returns_its_text_and_keeps_narrator(registry, tmp_path, bad):
    app = make(registry, tmp_path, "anthropic", FailingFor(bad, MissingKey("нет ключа роли")))
    narrator = app.runner.adapter
    error = app.set_narrator("gemini:gemini-3.8-flash")
    assert error == "нет ключа роли"
    assert app.runner.adapter is narrator
    assert not (tmp_path / "w1" / "meta" / "models.json").exists()


@pytest.mark.parametrize("bad", [f"gemini-{WORLD}", f"gemini-{SUMMARIZER}"])
def test_role_factory_value_error_returns_its_text(registry, tmp_path, bad):
    app = make(registry, tmp_path, "anthropic", FailingFor(bad, ValueError("плохая роль")))
    assert app.set_narrator("gemini:gemini-3.8-flash") == "плохая роль"
