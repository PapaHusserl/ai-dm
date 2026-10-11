# devtools/live_smoke.py (ручной живой вызов, в pytest не запускается): здесь проверяется только
# сборка запроса -- какая роль и какой effort уходят в адаптер. Адаптер подменён, сети нет.
import importlib.util
from pathlib import Path

import pytest

from ai_dm.config.app import load_settings
from ai_dm.llm.types import ChatResponse, Text

SMOKE_PATH = Path(__file__).parents[3] / "devtools" / "live_smoke.py"


class FakeAdapter:
    def __init__(self, sent):
        self.sent = sent

    def complete(self, req):
        self.sent.append(req)
        return ChatResponse(content=[Text(text="ок")], stop_reason="end_turn", model=req.model)


def run_smoke(monkeypatch, argv):
    spec = importlib.util.spec_from_file_location("live_smoke", SMOKE_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sent = []
    made = []

    def fake_make_adapter(provider, model, cfg, **kw):
        made.append((provider, model))
        return FakeAdapter(sent)

    monkeypatch.setattr(module, "make_adapter", fake_make_adapter)
    assert module.main(argv) == 0
    return sent[0], made[0]


def cfg():
    return load_settings().app


def test_gemini_uses_narrator_of_gemini_profile(monkeypatch):
    request, made = run_smoke(monkeypatch, ["gemini"])
    assert request.model == cfg().profiles["gemini"].narrator.model
    assert made == ("gemini", request.model)


def test_gemini_default_model_has_effort_of_its_role(monkeypatch):
    request, _ = run_smoke(monkeypatch, ["gemini"])
    assert request.effort == cfg().profiles["gemini"].narrator.effort


def test_gemini_with_other_model_has_no_effort(monkeypatch):
    request, _ = run_smoke(monkeypatch, ["gemini", "--model", "gemini-3.5-flash-lite"])
    assert request.model == "gemini-3.5-flash-lite"
    assert request.effort is None


def test_anthropic_uses_narrator_role_with_effort(monkeypatch):
    request, made = run_smoke(monkeypatch, ["anthropic"])
    assert request.model == cfg().roles.narrator.model
    assert request.effort == cfg().roles.narrator.effort
    assert made == ("anthropic", request.model)


def test_anthropic_with_other_model_has_no_effort(monkeypatch):
    request, _ = run_smoke(monkeypatch, ["anthropic", "--model", "claude-haiku-4-5"])
    assert request.model == "claude-haiku-4-5"
    assert request.effort is None


@pytest.mark.parametrize("provider", ["anthropic", "gemini"])
def test_request_has_one_strict_tool_and_a_role_name(monkeypatch, provider):
    request, _ = run_smoke(monkeypatch, [provider])
    assert request.role == "narrator"
    assert len(request.tools) == 1
    assert request.tools[0].strict is True
