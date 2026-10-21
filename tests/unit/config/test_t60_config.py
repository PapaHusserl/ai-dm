# Т60 «Сеть» (docs/plan-t60.md п.1, раздел 10): настройки сети и цепочки рассказчика.
#   [llm] gemini_ipv4 = true, narrator_chain = 4 ключа "провайдер:модель";
#   [retry] gemini_timeout_s = 90 (> 0), chain_delays = [] (паузы primary summarizer с запасным);
#   AppConfig.check_models_known: модели цепочки обязаны иметь цену и окно, ключ -- вида a:b.
import pytest
from pydantic import ValidationError

from ai_dm.config.app import load_settings

CHAIN = [
    "gemini:gemini-3.8-flash", "openai:gpt-6.1-sol", "gemini:gemini-4-argon",
    "gemini:gemini-3-flash-preview", "gemini:gemini-3.5-flash-lite",
]


def app(toml=None):
    return load_settings(toml).app


def test_default_gemini_ipv4_is_on():
    assert app().llm.gemini_ipv4 is True


def test_default_narrator_chain_has_five_keys_in_order():
    assert app().llm.narrator_chain == CHAIN


def test_default_gemini_timeout_is_ninety_seconds():
    assert app().retry.gemini_timeout_s == 90


def test_default_common_timeout_stays_180():
    assert app().retry.timeout_s == 180


def test_default_chain_delays_are_empty():
    assert app().retry.chain_delays == []


def test_default_delays_stay_full():
    assert app().retry.delays == [1, 3, 10]


@pytest.mark.parametrize("model", ["gemini-4-argon", "gemini-3-flash-preview"])
def test_chain_models_have_price_and_window_in_defaults(model):
    cfg = app()
    assert model in cfg.prices
    assert model in cfg.context_windows


def test_argon_has_no_explicit_cache():
    assert app().prices["gemini-4-argon"].cache_storage_hour == 0


def test_chain_model_without_price_is_rejected():
    with pytest.raises(ValidationError):
        app('[llm]\nnarrator_chain = ["gemini:no-such-model"]\n')


def test_chain_model_with_price_but_without_window_is_rejected():
    toml = (
        '[llm]\nnarrator_chain = ["gemini:only-price"]\n'
        '[prices."only-price"]\ninput = 1\noutput = 1\ncache_read = 1\ncache_write = 1\n'
    )
    with pytest.raises(ValidationError):
        app(toml)


def test_chain_model_with_window_but_without_price_is_rejected():
    toml = '[llm]\nnarrator_chain = ["gemini:only-window"]\n[context_windows]\nonly-window = 1000\n'
    with pytest.raises(ValidationError):
        app(toml)


def test_chain_model_with_price_and_window_is_accepted():
    toml = (
        '[llm]\nnarrator_chain = ["gemini:new-one"]\n'
        '[prices."new-one"]\ninput = 1\noutput = 1\ncache_read = 1\ncache_write = 1\n'
        '[context_windows]\nnew-one = 1000\n'
    )
    assert app(toml).llm.narrator_chain == ["gemini:new-one"]


@pytest.mark.parametrize("key", ["gemini-3.8-flash", "gemini:", ":gemini-3.8-flash", ""])
def test_chain_key_without_provider_or_model_is_rejected(key):
    with pytest.raises(ValidationError):
        app(f'[llm]\nnarrator_chain = ["{key}"]\n')


def test_empty_chain_is_allowed():
    assert app("[llm]\nnarrator_chain = []\n").llm.narrator_chain == []


@pytest.mark.parametrize("value", [0, -5])
def test_gemini_timeout_must_be_positive(value):
    with pytest.raises(ValidationError):
        app(f"[retry]\ngemini_timeout_s = {value}\n")


def test_gemini_timeout_can_be_overridden():
    assert app("[retry]\ngemini_timeout_s = 30\n").retry.gemini_timeout_s == 30


def test_chain_delays_can_be_overridden():
    assert app("[retry]\nchain_delays = [2]\n").retry.chain_delays == [2]


def test_ipv4_can_be_turned_off():
    assert app("[llm]\ngemini_ipv4 = false\n").llm.gemini_ipv4 is False


def test_user_config_with_alternatives_narrator_table_still_loads():
    toml = (
        '[alternatives.narrator]\nprovider = "gemini"\nmodel = "gemini-4-argon"\n'
        "max_tokens = 16000\n"
    )
    cfg = app(toml)
    assert cfg.alternatives.narrator.model == "gemini-4-argon"
    assert cfg.llm.narrator_chain == CHAIN
