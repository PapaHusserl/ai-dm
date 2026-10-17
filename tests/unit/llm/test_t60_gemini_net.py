# Т60 «Сеть» (docs/plan-t60.md п.1.1-1.2): GeminiAdapter.get_client -- таймаут gemini_timeout_s
# (не общий timeout_s) и IPv4-транспорт httpx.HTTPTransport(local_address="0.0.0.0").
# Сеть не трогаем: genai.Client и httpx.HTTPTransport подменены фейками.
import ast
from pathlib import Path
from types import SimpleNamespace

from llm_kit import app_cfg

from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.gemini_adapter import GeminiAdapter

MODEL = "gemini-3.8-flash"


class FakeTransport:
    made = []

    def __init__(self, *args, **kwargs):
        self.args = args
        self.kwargs = kwargs
        FakeTransport.made.append(self)


def client_options(monkeypatch, cfg):
    import httpx
    from google import genai

    FakeTransport.made = []
    created = []
    monkeypatch.setattr(httpx, "HTTPTransport", FakeTransport)
    monkeypatch.setattr(genai, "Client", lambda **kw: created.append(kw) or SimpleNamespace())
    GeminiAdapter(MODEL, cfg, api_key="k").get_client()
    return created[0]["http_options"]


def test_timeout_is_gemini_timeout_in_milliseconds(monkeypatch):
    cfg = app_cfg()
    cfg.retry.gemini_timeout_s = 37
    options = client_options(monkeypatch, cfg)
    assert options.timeout == 37_000


def test_default_timeout_is_ninety_seconds(monkeypatch):
    assert client_options(monkeypatch, app_cfg()).timeout == 90_000


def test_timeout_does_not_follow_common_timeout(monkeypatch):
    cfg = app_cfg()
    cfg.retry.timeout_s = 500
    assert client_options(monkeypatch, cfg).timeout == 90_000


def test_ipv4_flag_adds_transport_bound_to_zero_address(monkeypatch):
    options = client_options(monkeypatch, app_cfg())
    transport = options.client_args["transport"]
    assert isinstance(transport, FakeTransport)
    assert transport.kwargs == {"local_address": "0.0.0.0"}
    assert transport.args == ()
    assert len(FakeTransport.made) == 1


def test_ipv4_transport_is_not_in_async_args(monkeypatch):
    options = client_options(monkeypatch, app_cfg())
    assert not options.async_client_args


def test_without_ipv4_flag_no_transport_is_made(monkeypatch):
    cfg = app_cfg()
    cfg.llm.gemini_ipv4 = False
    options = client_options(monkeypatch, cfg)
    assert "transport" not in (options.client_args or {})
    assert FakeTransport.made == []


def test_without_ipv4_flag_timeout_still_applies(monkeypatch):
    cfg = app_cfg()
    cfg.llm.gemini_ipv4 = False
    assert client_options(monkeypatch, cfg).timeout == 90_000


def test_injected_client_is_used_without_building_transport(monkeypatch):
    import httpx

    FakeTransport.made = []
    monkeypatch.setattr(httpx, "HTTPTransport", FakeTransport)
    client = SimpleNamespace()
    assert GeminiAdapter(MODEL, app_cfg(), client=client).get_client() is client
    assert FakeTransport.made == []


def test_anthropic_still_uses_common_timeout():
    cfg = app_cfg()
    cfg.retry.timeout_s = 123
    cfg.retry.gemini_timeout_s = 7
    created = []
    adapter = AnthropicAdapter(
        "claude-opus-5-5", cfg, client_factory=lambda **kw: created.append(kw) or object(),
        api_key="k",
    )
    adapter.get_client()
    assert created[0]["timeout"] == 123


def test_httpx_is_imported_lazily_in_gemini_adapter():
    path = Path(__file__).resolve().parents[3] / "src" / "ai_dm" / "llm" / "gemini_adapter.py"
    tree = ast.parse(path.read_text(encoding="utf-8"))
    top = []
    for node in tree.body:
        if isinstance(node, ast.Import):
            top += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            top.append(node.module or "")
    assert not [n for n in top if n.split(".")[0] == "httpx"]
