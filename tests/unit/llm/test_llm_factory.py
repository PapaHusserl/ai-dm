# Ожидаемый API: ai_dm.llm.factory.make_adapter(provider, model, app_cfg, *, env=None,
# dotenv_path=None) -> ModelAdapter. Ключ берётся через llm.keys (env важнее .env; env=None --
# os.environ). Адаптер создаётся без обращения к SDK и сети (клиент -- лениво при первом вызове).
# Нет ключа -> MissingKey (LlmFatal); неизвестный провайдер -> ValueError.
import pytest
from llm_kit import app_cfg

from ai_dm.config.app import ProviderHost
from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.chat_adapter import ChatCompletionsAdapter
from ai_dm.llm.errors import LlmFatal, MissingKey
from ai_dm.llm.factory import make_adapter
from ai_dm.llm.gemini_adapter import GeminiAdapter
from ai_dm.llm.openai_adapter import OpenAIAdapter

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
        make_adapter("mistral", "m", app_cfg(), env=ENV)


def test_openai_provider_gives_openai_adapter():
    adapter = make_adapter("openai", "gpt-6.1-sol", app_cfg(), env={"OPENAI_API_KEY": "o-key"})
    assert isinstance(adapter, OpenAIAdapter)


def test_openai_info_carries_provider_and_model():
    info = make_adapter("openai", "gpt-6-luna", app_cfg(), env={"OPENAI_API_KEY": "o"}).info()
    assert (info.provider, info.model) == ("openai", "gpt-6-luna")


def test_anthropic_adapter_gets_config_and_key():
    cfg = app_cfg()
    adapter = make_adapter("anthropic", "claude-opus-5-5", cfg, env=ENV)
    assert adapter.cfg is cfg
    assert adapter.api_key == "a-key"


def test_gemini_adapter_gets_config_and_key():
    cfg = app_cfg()
    adapter = make_adapter("gemini", "gemini-3.8-flash", cfg, env=ENV)
    assert adapter.cfg is cfg
    assert adapter.api_key == "g-key"


def test_openai_adapter_gets_config_and_key():
    cfg = app_cfg()
    adapter = make_adapter("openai", "gpt-6.1-sol", cfg, env={"OPENAI_API_KEY": "o-key"})
    assert adapter.cfg is cfg
    assert adapter.api_key == "o-key"


def test_openai_without_key_names_the_variable():
    with pytest.raises(MissingKey, match="OPENAI_API_KEY"):
        make_adapter("openai", "gpt-6.1-sol", app_cfg(), env=ENV)


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


OR_ENV = {"OPENROUTER_API_KEY": "r-key"}
DEEPSEEK = "deepseek/deepseek-v4-flash"


def test_host_provider_gives_chat_completions_adapter():
    adapter = make_adapter("openrouter", DEEPSEEK, app_cfg(), env=OR_ENV)
    assert type(adapter) is ChatCompletionsAdapter


def test_host_adapter_info_carries_host_name_and_model():
    info = make_adapter("openrouter", DEEPSEEK, app_cfg(), env=OR_ENV).info()
    assert (info.provider, info.model) == ("openrouter", DEEPSEEK)


def test_host_adapter_gets_base_url_key_and_config():
    cfg = app_cfg()
    adapter = make_adapter("openrouter", DEEPSEEK, cfg, env=OR_ENV)
    assert adapter.base_url == "https://openrouter.ai/api/v1"
    assert adapter.api_key == "r-key"
    assert adapter.cfg is cfg


def test_host_without_key_names_its_variable():
    with pytest.raises(MissingKey, match="OPENROUTER_API_KEY"):
        make_adapter("openrouter", DEEPSEEK, app_cfg(), env=ENV)


def test_host_does_not_use_builtin_keys():
    env = {"OPENAI_API_KEY": "o-key", "ANTHROPIC_API_KEY": "a-key"}
    with pytest.raises(MissingKey):
        make_adapter("openrouter", DEEPSEEK, app_cfg(), env=env)


def test_host_key_from_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("OPENROUTER_API_KEY=from-file\n", encoding="utf-8")
    adapter = make_adapter("openrouter", DEEPSEEK, app_cfg(), env={}, dotenv_path=dotenv)
    assert adapter.api_key == "from-file"


def test_user_host_uses_its_own_key_env_and_url():
    cfg = app_cfg()
    cfg.providers["myhost"] = ProviderHost(base_url="https://h.example/v1", key_env="H_KEY")
    adapter = make_adapter("myhost", "m", cfg, env={"H_KEY": "h"})
    assert (adapter.provider, adapter.base_url, adapter.api_key) == (
        "myhost", "https://h.example/v1", "h",
    )


def test_host_missing_key_message_does_not_contain_other_keys():
    with pytest.raises(MissingKey) as info:
        make_adapter("openrouter", DEEPSEEK, app_cfg(), env={"OPENAI_API_KEY": "o-secret"})
    assert "o-secret" not in str(info.value)


def test_builtin_providers_stay_their_own_classes_when_host_exists():
    env = {**ENV, **OR_ENV, "OPENAI_API_KEY": "o"}
    assert type(make_adapter("openai", "gpt-6.1-sol", app_cfg(), env=env)) is OpenAIAdapter
    assert type(make_adapter("gemini", "g", app_cfg(), env=env)) is GeminiAdapter
    assert type(make_adapter("anthropic", "a", app_cfg(), env=env)) is AnthropicAdapter


def test_unknown_provider_is_value_error_even_with_hosts_configured():
    with pytest.raises(ValueError, match="mistral"):
        make_adapter("mistral", "m", app_cfg(), env={**ENV, **OR_ENV})


@pytest.mark.parametrize(
    "provider, model",
    [
        ("anthropic", "claude-opus-5-5"), ("anthropic", "claude-haiku-4-5"),
        ("gemini", "gemini-3.8-flash"), ("gemini", "gemini-3.5-flash-lite"),
    ],
)
def test_info_model_equals_requested_model(provider, model):
    assert make_adapter(provider, model, app_cfg(), env=ENV).info().model == model
