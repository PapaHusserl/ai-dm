# Ожидаемый API: ai_dm.llm.factory.make_adapter(provider, model, app_cfg, *, env=None,
# dotenv_path=None) -> ModelAdapter. Ключ берётся через llm.keys (env важнее .env; env=None --
# os.environ). Адаптер создаётся без обращения к SDK и сети (клиент -- лениво при первом вызове).
# Нет ключа -> MissingKey (LlmFatal); неизвестный провайдер -> ValueError.
import pytest
from llm_kit import app_cfg

from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.errors import LlmFatal, MissingKey
from ai_dm.llm.factory import make_adapter
from ai_dm.llm.gemini_adapter import GeminiAdapter

ENV = {"ANTHROPIC_API_KEY": "a-key", "GEMINI_API_KEY": "g-key"}


def test_anthropic_provider_gives_anthropic_adapter():
    adapter = make_adapter("anthropic", "claude-opus-5-5", app_cfg(), env=ENV)
    assert isinstance(adapter, AnthropicAdapter)


def test_gemini_provider_gives_gemini_adapter():
    adapter = make_adapter("gemini", "gemini-3.8-flash", app_cfg(), env=ENV)
    assert isinstance(adapter, GeminiAdapter)


def test_adapter_info_carries_provider_and_model():
    adapter = make_adapter("anthropic", "claude-sonnet-5-5", app_cfg(), env=ENV)
    info = adapter.info()
    assert (info.provider, info.model) == ("anthropic", "claude-sonnet-5-5")


def test_gemini_info_carries_provider_and_model():
    info = make_adapter("gemini", "gemini-3.8-flash", app_cfg(), env=ENV).info()
    assert (info.provider, info.model) == ("gemini", "gemini-3.8-flash")


def test_unknown_provider_is_value_error():
    with pytest.raises(ValueError):
        make_adapter("openai", "gpt", app_cfg(), env=ENV)


def test_missing_key_raises_missing_key():
    with pytest.raises(MissingKey):
        make_adapter("anthropic", "claude-opus-5-5", app_cfg(), env={})


def test_missing_key_is_fatal():
    with pytest.raises(LlmFatal):
        make_adapter("gemini", "gemini-3.8-flash", app_cfg(), env={"ANTHROPIC_API_KEY": "a"})


def test_missing_key_message_does_not_contain_other_keys():
    with pytest.raises(MissingKey) as info:
        make_adapter("gemini", "gemini-3.8-flash", app_cfg(), env={"ANTHROPIC_API_KEY": "a-key"})
    assert "a-key" not in str(info.value)


def test_key_from_dotenv_is_enough(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    adapter = make_adapter("anthropic", "claude-opus-5-5", app_cfg(), env={}, dotenv_path=dotenv)
    assert isinstance(adapter, AnthropicAdapter)


@pytest.mark.parametrize(
    "provider, model",
    [
        ("anthropic", "claude-opus-5-5"), ("anthropic", "claude-haiku-4-5"),
        ("gemini", "gemini-3.8-flash"), ("gemini", "gemini-3.5-flash-lite"),
    ],
)
def test_info_model_equals_requested_model(provider, model):
    assert make_adapter(provider, model, app_cfg(), env=ENV).info().model == model
