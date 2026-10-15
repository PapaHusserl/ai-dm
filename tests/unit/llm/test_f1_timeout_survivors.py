# 19ф Ф1, добивка мутантов: текст ошибки сохраняется в translate_error адаптеров
# для сетевого сбоя и 504; RetriesExhausted берёт timeout=False, если у last нет атрибута.
import httpx
import pytest
from llm_kit import make_request
from test_llm_anthropic_adapter import StatusError
from test_llm_anthropic_adapter import make as anthropic_make
from test_llm_gemini_adapter import ApiError
from test_llm_gemini_adapter import make as gemini_make
from test_llm_gemini_adapter import tools_req as gemini_req

from ai_dm.llm.errors import LlmTransient, RetriesExhausted


def gemini_error(error):
    adapter, _ = gemini_make([error])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(gemini_req())
    return info.value


def anthropic_error(error):
    adapter, _, _ = anthropic_make([error])
    with pytest.raises(LlmTransient) as info:
        adapter.complete(make_request())
    return info.value


def test_exhausted_last_without_timeout_attribute_is_not_slow():
    error = RetriesExhausted(2, Exception("обычная"))
    assert error.timeout is False
    assert str(error) == "повторы исчерпаны (вызовов: 2): обычная"


def test_gemini_network_error_keeps_text():
    assert str(gemini_error(httpx.ConnectError("нет сети"))) == "нет сети"


def test_gemini_504_keeps_text():
    assert str(gemini_error(ApiError(504, "шлюз молчит"))) == "шлюз молчит"


def test_anthropic_network_error_keeps_text():
    assert str(anthropic_error(httpx.ConnectError("нет сети"))) == "нет сети"


def test_anthropic_504_keeps_text():
    assert str(anthropic_error(StatusError(504, "шлюз молчит"))) == "шлюз молчит"
