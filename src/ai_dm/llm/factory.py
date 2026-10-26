from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.chat_adapter import ChatCompletionsAdapter
from ai_dm.llm.errors import MissingKey
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
        raise MissingKey(f"нет ключа {var or KEY_VARS[provider]} (переменная окружения или .env)")
    if host is not None:
        return ChatCompletionsAdapter(provider, model, app_cfg, api_key=key)
    if provider == "anthropic":
        return AnthropicAdapter(model, app_cfg, api_key=key)
    if provider == "openai":
        return OpenAIAdapter(model, app_cfg, api_key=key)
    if provider == "gemini":
        return GeminiAdapter(model, app_cfg, api_key=key)
    raise ValueError(f"неизвестный провайдер: {provider}")
