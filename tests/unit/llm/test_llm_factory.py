# Ожидаемый API: ai_dm.llm.factory.make_adapter(provider, model, app_cfg, *, env=None,
# dotenv_path=None) -> ModelAdapter. Ключ берётся через llm.keys (env важнее .env; env=None --
# os.environ). Адаптер создаётся без обращения к SDK и сети (клиент -- лениво при первом вызове).
# Нет ключа -> MissingKey (LlmFatal); неизвестный провайдер -> ValueError.
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg

from ai_dm.config.app import ProviderHost
from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.chat_adapter import ChatCompletionsAdapter
from ai_dm.llm.errors import LlmFatal, MissingKey
from ai_dm.llm.factory import adapter_for, make_adapter, verify_key
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


def test_missing_key_message_names_default_dotenv():
    with pytest.raises(MissingKey, match=r"или \.env\)"):
        make_adapter("anthropic", "claude-opus-5-5", app_cfg(), env={}, dotenv_path=None)


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


@pytest.mark.parametrize(
    "provider, cls",
    [
        ("openrouter", ChatCompletionsAdapter), ("anthropic", AnthropicAdapter),
        ("gemini", GeminiAdapter), ("openai", OpenAIAdapter),
    ],
)
def test_adapter_for_gives_class_and_key(provider, cls):
    cfg = app_cfg()
    adapter = adapter_for(provider, "m", cfg, "the-key")
    assert (type(adapter), adapter.api_key, adapter.cfg) == (cls, "the-key", cfg)


def test_adapter_for_unknown_provider_is_value_error():
    with pytest.raises(ValueError, match="mistral"):
        adapter_for("mistral", "m", app_cfg(), "k")


def test_adapter_for_user_host_gives_chat_adapter():
    cfg = app_cfg()
    cfg.providers["myhost"] = ProviderHost(base_url="https://h.example/v1", key_env="H_KEY")
    assert type(adapter_for("myhost", "m", cfg, "h")) is ChatCompletionsAdapter


def test_openrouter_probe_path_is_key():
    assert app_cfg().providers["openrouter"].probe_path == "/key"


def test_provider_host_probe_path_defaults_to_models():
    assert ProviderHost(base_url="https://h.example", key_env="K").probe_path == "/models"


class StatusError(Exception):
    def __init__(self, status=None, message="ошибка", code=None):
        super().__init__(message)
        self.status_code = status
        self.code = code
        self.response = SimpleNamespace(headers={})


class ConnectError(Exception):
    pass


class FakeModels:
    # list() у клиентов openai / anthropic / gemini; get() у хостера
    def __init__(self, error=None):
        self.error = error
        self.calls = []

    def list(self, *args, **kwargs):
        return self.get("/models")

    def get(self, path, **kwargs):
        self.calls.append(path)
        if self.error is not None:
            raise self.error
        return []


def verified(monkeypatch, provider, error=None):
    # настоящий адаптер провайдера на фейковом клиенте; verify_key получает его от adapter_for
    client = FakeModels(error)
    client.models = client
    cfg = app_cfg()
    key = "sec-1234"
    if provider == "gemini":
        adapter = GeminiAdapter("m", cfg, client=client, sdk=object(), api_key=key)
    elif provider == "anthropic":
        adapter = AnthropicAdapter("m", cfg, client_factory=lambda **kw: client, api_key=key)
    elif provider == "openai":
        adapter = OpenAIAdapter("m", cfg, client_factory=lambda **kw: client, api_key=key)
    else:
        adapter = ChatCompletionsAdapter(
            provider, "m", cfg, client_factory=lambda **kw: client, api_key=key,
        )
    made = []

    def fake_adapter_for(*args):
        made.append(args)
        return adapter

    monkeypatch.setattr("ai_dm.llm.factory.adapter_for", fake_adapter_for)
    return verify_key(provider, key, cfg), client, made


@pytest.mark.parametrize("provider", ["openrouter", "anthropic", "gemini", "openai"])
def test_verify_key_ok_on_200(monkeypatch, provider):
    assert verified(monkeypatch, provider)[0] == "ok"


@pytest.mark.parametrize("provider", ["openrouter", "anthropic", "openai"])
@pytest.mark.parametrize("status", [401, 403])
def test_verify_key_invalid_on_401_403(monkeypatch, provider, status):
    assert verified(monkeypatch, provider, StatusError(status))[0] == "invalid"


def test_verify_key_gemini_400_invalid_key_is_invalid(monkeypatch):
    error = StatusError(None, "API key not valid. Please pass a valid API key.", code=400)
    assert verified(monkeypatch, "gemini", error)[0] == "invalid"


def test_verify_key_gemini_plain_400_is_unverified(monkeypatch):
    error = StatusError(None, "bad request", code=400)
    assert verified(monkeypatch, "gemini", error)[0] == ("unverified", "bad request")


def test_verify_key_network_error_is_unverified(monkeypatch):
    verdict = verified(monkeypatch, "openrouter", ConnectError("connection refused"))[0]
    assert verdict == ("unverified", "нет сети")


@pytest.mark.parametrize("status", [429, 500, 503])
def test_verify_key_transient_status_is_unverified(monkeypatch, status):
    verdict = verified(monkeypatch, "anthropic", StatusError(status, "сбой"))[0]
    assert verdict == ("unverified", "нет сети")


def test_verify_key_builds_adapter_with_empty_model(monkeypatch):
    _, _, made = verified(monkeypatch, "openrouter")
    assert made[0][:2] == ("openrouter", "")


def test_verify_key_404_is_unverified_not_invalid(monkeypatch):
    verdict = verified(monkeypatch, "openrouter", StatusError(404, "нет пути"))[0]
    assert verdict == ("unverified", "нет пути")


def test_verify_key_unknown_error_is_unverified(monkeypatch):
    verdict = verified(monkeypatch, "openai", ValueError("странное"))[0]
    assert verdict == ("unverified", "странное")


def test_verify_key_openrouter_asks_key_path(monkeypatch):
    assert verified(monkeypatch, "openrouter")[1].calls == ["/key"]


def test_verify_key_openai_asks_models_list(monkeypatch):
    assert verified(monkeypatch, "openai")[1].calls == ["/models"]


def test_verify_key_builds_adapter_with_provider_and_key(monkeypatch):
    _, _, made = verified(monkeypatch, "anthropic")
    assert [(args[0], args[3]) for args in made] == [("anthropic", "sec-1234")]


def test_verify_key_error_text_has_no_key(monkeypatch):
    verdict = verified(monkeypatch, "openrouter", ConnectError("fail sec-1234"))[0]
    assert "sec-1234" not in verdict[1]


def test_verify_key_real_adapter_for_unknown_provider_is_value_error():
    with pytest.raises(ValueError):
        verify_key("mistral", "k", app_cfg())
