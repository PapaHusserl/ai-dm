# К0-фикс, 38 ж (docs/plan-k0-fix.md, шаг 5): safety_settings Gemini и stop_detail.
#   [llm] gemini_safety = block_none (по умолчанию) | off | default; в GenerateContentConfig
#   (обе ветки: с кэшем и без) -- 4 текстовые категории SAFETY_CATEGORIES с порогом
#   BLOCK_NONE / OFF; default -- safety_settings не передаётся (None); в CreateCachedContentConfig
#   их нет. stop_detail: сырой повод отказа/обрыва (имя finish_reason / block_reason), иначе None.
from types import SimpleNamespace

import pytest
from llm_kit import app_cfg
from pydantic import ValidationError
from test_llm_gemini_adapter import (
    FAKE_SDK,
    MODEL,
    FakeModels,
    api_response,
    part,
    tools_req,
)

from ai_dm.config.app import LlmConfig
from ai_dm.llm.gemini_adapter import SAFETY_CATEGORIES, GeminiAdapter
from ai_dm.llm.types import ChatResponse
from ai_dm.protocol.schema import MODE_TOOLS, tool_set

CATEGORIES = (
    "HARM_CATEGORY_HARASSMENT", "HARM_CATEGORY_HATE_SPEECH",
    "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT",
)


def adapter_with(safety=None, results=None, caches=None):
    cfg = app_cfg()
    if safety is not None:
        cfg.llm.gemini_safety = safety
    models = FakeModels(results if results is not None else [api_response([part(text="ок")])])
    client = SimpleNamespace(models=models, caches=caches)
    return GeminiAdapter(MODEL, cfg, client=client, sdk=FAKE_SDK), models


def config_of(safety=None):
    adapter, models = adapter_with(safety)
    adapter.complete(tools_req())
    return models.calls[0]["config"]


# конфиг

def llm_with(**fields):
    return LlmConfig.model_validate({**app_cfg().llm.model_dump(), **fields})


def test_config_default_is_block_none():
    defaults = app_cfg().llm.model_dump()
    del defaults["gemini_safety"]
    assert LlmConfig.model_validate(defaults).gemini_safety == "block_none"


def test_loaded_settings_default_is_block_none():
    assert app_cfg().llm.gemini_safety == "block_none"


@pytest.mark.parametrize("value", ["BLOCK_NONE", "", "strict", "none"])
def test_config_rejects_other_values(value):
    with pytest.raises(ValidationError):
        llm_with(gemini_safety=value)


@pytest.mark.parametrize("value", ["default", "block_none", "off"])
def test_config_accepts_three_values(value):
    assert llm_with(gemini_safety=value).gemini_safety == value


# safety_settings в запросе

def test_safety_categories_are_four_text_categories():
    assert tuple(SAFETY_CATEGORIES) == CATEGORIES


def test_block_none_sends_four_settings_with_block_none():
    settings = config_of().safety_settings
    assert [s.category for s in settings] == list(CATEGORIES)
    assert {s.threshold for s in settings} == {"BLOCK_NONE"}


def test_explicit_block_none_equals_default():
    assert config_of("block_none").safety_settings == config_of().safety_settings


def test_off_sends_threshold_off():
    settings = config_of("off").safety_settings
    assert [s.category for s in settings] == list(CATEGORIES)
    assert {s.threshold for s in settings} == {"OFF"}


def test_default_does_not_send_safety_settings():
    assert getattr(config_of("default"), "safety_settings", None) is None


def test_safety_settings_method_is_none_for_default():
    adapter, _ = adapter_with("default")
    assert adapter.safety_settings() is None


def test_safety_settings_are_in_build_config_without_cache():
    adapter, _ = adapter_with()
    config = adapter.build_config(tools_req())
    assert len(config.safety_settings) == 4
    assert config.system_instruction


def test_safety_settings_are_in_build_config_with_cache_name():
    adapter, _ = adapter_with()
    config = adapter.build_config(tools_req(), cache_name="cachedContents/c1")
    assert config.cached_content == "cachedContents/c1"
    assert [s.category for s in config.safety_settings] == list(CATEGORIES)
    assert {s.threshold for s in config.safety_settings} == {"BLOCK_NONE"}


def test_off_is_kept_in_build_config_with_cache_name():
    adapter, _ = adapter_with("off")
    config = adapter.build_config(tools_req(), cache_name="cachedContents/c1")
    assert {s.threshold for s in config.safety_settings} == {"OFF"}


def test_cached_request_carries_safety_settings_and_cache_config_does_not():
    from test_llm_gemini_cache import FakeCaches

    caches = FakeCaches()
    adapter, models = adapter_with(caches=caches)
    adapter.complete(tools_req())
    sent = models.calls[0]["config"]
    assert sent.cached_content == "cachedContents/c1"
    assert len(sent.safety_settings) == 4
    assert not hasattr(caches.calls[0]["config"], "safety_settings")


# настоящие типы SDK

@pytest.mark.parametrize("mode", sorted(MODE_TOOLS))
def test_real_config_has_block_none_for_every_tool_set(mode):
    from google.genai import types
    from llm_kit import make_request

    from ai_dm.llm.types import ToolSpec

    tools = [ToolSpec.model_validate(t) for t in tool_set(mode)]
    config = GeminiAdapter(MODEL, app_cfg()).build_config(make_request(tools=tools, model=MODEL))
    assert isinstance(config, types.GenerateContentConfig)
    assert len(config.safety_settings) == 4
    assert config.safety_settings[0].threshold == types.HarmBlockThreshold.BLOCK_NONE


def test_real_categories_are_valid_sdk_categories():
    from google.genai import types
    from llm_kit import make_request

    config = GeminiAdapter(MODEL, app_cfg()).build_config(make_request(model=MODEL))
    expected = [types.HarmCategory(name) for name in CATEGORIES]
    assert [s.category for s in config.safety_settings] == expected


def test_real_off_threshold_is_sdk_off():
    from google.genai import types
    from llm_kit import make_request

    cfg = app_cfg()
    cfg.llm.gemini_safety = "off"
    config = GeminiAdapter(MODEL, cfg).build_config(make_request(model=MODEL))
    assert {s.threshold for s in config.safety_settings} == {types.HarmBlockThreshold.OFF}


def test_real_default_has_no_safety_settings():
    from llm_kit import make_request

    cfg = app_cfg()
    cfg.llm.gemini_safety = "default"
    config = GeminiAdapter(MODEL, cfg).build_config(make_request(model=MODEL))
    assert config.safety_settings is None


# stop_detail

def complete(response):
    adapter, _ = adapter_with(results=[response])
    return adapter.complete(tools_req())


REFUSALS = ["SAFETY", "PROHIBITED_CONTENT", "BLOCKLIST", "SPII", "RECITATION"]


@pytest.mark.parametrize("finish", REFUSALS)
def test_refusal_finish_reason_goes_to_stop_detail(finish):
    resp = complete(api_response([part(text="")], finish=finish))
    assert (resp.stop_reason, resp.stop_detail) == ("refusal", finish)


def test_other_finish_reason_goes_to_stop_detail():
    resp = complete(api_response([part(text="x")], finish="OTHER"))
    assert (resp.stop_reason, resp.stop_detail) == ("other", "OTHER")


def test_prompt_block_reason_goes_to_stop_detail():
    resp = complete(api_response(None, block="PROHIBITED_CONTENT"))
    assert (resp.stop_reason, resp.stop_detail) == ("refusal", "PROHIBITED_CONTENT")


def test_prompt_block_safety_goes_to_stop_detail():
    resp = complete(api_response(None, block="SAFETY"))
    assert resp.stop_detail == "SAFETY"


@pytest.mark.parametrize("finish", ["STOP", "MAX_TOKENS"])
def test_normal_finish_has_no_stop_detail(finish):
    resp = complete(api_response([part(text="x")], finish=finish))
    assert resp.stop_detail is None


def test_tool_use_has_no_stop_detail():
    from test_llm_gemini_adapter import fcall

    calls = [fcall("skill_check", {})]
    resp = complete(api_response([part(text="")], calls=calls, finish="SAFETY"))
    assert (resp.stop_reason, resp.stop_detail) == ("tool_use", None)


def test_no_candidates_and_no_block_has_no_stop_detail():
    resp = complete(api_response(None))
    assert resp.stop_detail is None


def test_stop_detail_defaults_to_none_and_old_json_loads():
    old = '{"content": [], "stop_reason": "refusal", "model": "m"}'
    assert ChatResponse.model_validate_json(old).stop_detail is None


def test_stop_detail_survives_json_roundtrip():
    resp = complete(api_response([part(text="")], finish="SAFETY"))
    restored = ChatResponse.model_validate_json(resp.model_dump_json())
    assert restored.stop_detail == "SAFETY"


def test_no_candidates_with_unspecified_block_reason_is_other_with_detail():
    resp = complete(api_response(None, block="BLOCKED_REASON_UNSPECIFIED"))
    assert (resp.stop_reason, resp.stop_detail) == ("other", "BLOCKED_REASON_UNSPECIFIED")


def test_finish_reason_other_keeps_detail_with_stop_reason_other():
    resp = complete(api_response([part(text="")], finish="OTHER"))
    assert (resp.stop_reason, resp.stop_detail) == ("other", "OTHER")
