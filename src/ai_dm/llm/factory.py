from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.chat_adapter import ChatCompletionsAdapter
from ai_dm.llm.errors import LlmFatal, LlmTransient, MissingKey, is_auth_error
from ai_dm.llm.gemini_adapter import GeminiAdapter
from ai_dm.llm.keys import KEY_VARS, load_key
from ai_dm.llm.openai_adapter import OpenAIAdapter


def make_adapter(provider, model, app_cfg, *, env=None, dotenv_path=None):
    host = app_cfg.providers.get(provider)
    if host is None and provider not in KEY_VARS:
        raise ValueError(f"неизвестный провайдер: {provider}")
    var = None if host is None else host.key_env
    key = load_key(provider, env=env, dotenv_path=dotenv_path, var=var)
    if key is None:
        name = var or KEY_VARS[provider]
        raise MissingKey(f"нет ключа {name} (переменная окружения или {dotenv_path or '.env'})")
    return adapter_for(provider, model, app_cfg, key)


def adapter_for(provider, model, app_cfg, key):
    if provider in app_cfg.providers:
        return ChatCompletionsAdapter(provider, model, app_cfg, api_key=key)
    if provider == "anthropic":
        return AnthropicAdapter(model, app_cfg, api_key=key)
    if provider == "openai":
        return OpenAIAdapter(model, app_cfg, api_key=key)
    if provider == "gemini":
        return GeminiAdapter(model, app_cfg, api_key=key)
    raise ValueError(f"неизвестный провайдер: {provider}")


def verify_key(provider, key, app_cfg):
    # "ok" | "invalid" | ("unverified", текст): ошибка не по ключу (сеть, 5xx, 404) ключ не браковит
    adapter = adapter_for(provider, "", app_cfg, key)
    try:
        adapter.probe()
    except LlmFatal as error:
        if is_auth_error(error):
            return "invalid"
        return ("unverified", str(error))
    except LlmTransient:
        return ("unverified", "нет сети")
    return "ok"
