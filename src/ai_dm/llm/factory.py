from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.errors import MissingKey
from ai_dm.llm.gemini_adapter import GeminiAdapter
from ai_dm.llm.keys import KEY_VARS, load_key
from ai_dm.llm.openai_adapter import OpenAIAdapter


def make_adapter(provider, model, app_cfg, *, env=None, dotenv_path=None):
    if provider not in KEY_VARS:
        raise ValueError(f"неизвестный провайдер: {provider}")
    key = load_key(provider, env=env, dotenv_path=dotenv_path)
    if key is None:
        raise MissingKey(f"нет ключа {KEY_VARS[provider]} (переменная окружения или .env)")
    if provider == "anthropic":
        return AnthropicAdapter(model, app_cfg, api_key=key)
    if provider == "openai":
        return OpenAIAdapter(model, app_cfg, api_key=key)
    return GeminiAdapter(model, app_cfg, api_key=key)
