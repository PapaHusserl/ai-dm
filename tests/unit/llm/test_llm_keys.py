# Ожидаемый API: ai_dm.llm.keys (parse_dotenv, load_key, redact) -- контракт в llm_kit.py.
# ТЗ 11: ключи из env или .env (свой парсер), env важнее .env; ключи никогда не попадают в
# сейвы, журнал и репорты (сторож в конце файла прогоняет ход на моке).
import gzip
from pathlib import Path
from types import SimpleNamespace

import pytest
from llm_kit import DAY, app_cfg, make_request

from ai_dm.config.app import JournalConfig
from ai_dm.core.rng import Rng
from ai_dm.llm.anthropic_adapter import AnthropicAdapter
from ai_dm.llm.cost import CostLedger, cost_nano
from ai_dm.llm.errors import LlmError, LlmTransient
from ai_dm.llm.gemini_adapter import GeminiAdapter
from ai_dm.llm.journal import Journal
from ai_dm.llm.keys import load_key, parse_dotenv, read_var, redact, write_dotenv_var
from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.llm.retry import call_with_retries
from ai_dm.persistence.store import save_slot
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.world import WorldState

SECRET = "sk-ant-FAKE-0123456789-ZZZ"


def test_parse_simple_pair():
    assert parse_dotenv("ANTHROPIC_API_KEY=abc") == {"ANTHROPIC_API_KEY": "abc"}


def test_parse_skips_comments_and_blank_lines():
    text = "# ключи\n\nA=1\n   # ещё комментарий\nB=2\n"
    assert parse_dotenv(text) == {"A": "1", "B": "2"}


def test_parse_double_quotes_are_stripped():
    assert parse_dotenv('A="значение с пробелом"') == {"A": "значение с пробелом"}


def test_parse_single_quotes_are_stripped():
    assert parse_dotenv("A='abc'") == {"A": "abc"}


def test_parse_hash_inside_quotes_stays():
    assert parse_dotenv('A="x # y"') == {"A": "x # y"}


def test_parse_value_may_contain_equals():
    assert parse_dotenv("A=abc==") == {"A": "abc=="}


def test_parse_spaces_around_equals_are_trimmed():
    assert parse_dotenv("  A  =  abc  ") == {"A": "abc"}


def test_parse_empty_value():
    assert parse_dotenv("A=") == {"A": ""}


def test_parse_ignores_lines_without_equals():
    assert parse_dotenv("мусор\nA=1") == {"A": "1"}


def test_parse_later_line_wins():
    assert parse_dotenv("A=1\nA=2") == {"A": "2"}


def test_parse_handles_crlf():
    assert parse_dotenv("A=1\r\nB=2\r\n") == {"A": "1", "B": "2"}


def test_parse_empty_text():
    assert parse_dotenv("") == {}


def test_load_key_from_env():
    assert load_key("anthropic", env={"ANTHROPIC_API_KEY": "from-env"}) == "from-env"


def test_load_key_gemini_variable():
    assert load_key("gemini", env={"GEMINI_API_KEY": "g-key"}) == "g-key"


def test_load_key_does_not_mix_providers():
    assert load_key("gemini", env={"ANTHROPIC_API_KEY": "a"}) is None


def test_load_key_from_dotenv_file(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text('ANTHROPIC_API_KEY="from-file"\n', encoding="utf-8")
    assert load_key("anthropic", env={}, dotenv_path=dotenv) == "from-file"


def test_env_wins_over_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=from-file\n", encoding="utf-8")
    env = {"ANTHROPIC_API_KEY": "from-env"}
    assert load_key("anthropic", env=env, dotenv_path=dotenv) == "from-env"


def test_missing_dotenv_file_is_not_an_error(tmp_path):
    assert load_key("anthropic", env={}, dotenv_path=tmp_path / ".env") is None


def test_missing_key_returns_none():
    assert load_key("anthropic", env={}) is None


def test_unknown_provider_is_value_error():
    with pytest.raises(ValueError):
        load_key("mistral", env={})


def test_unknown_provider_error_names_the_provider():
    with pytest.raises(ValueError, match="mistral"):
        load_key("mistral", env={})


def test_dotenv_is_read_as_utf8(tmp_path, monkeypatch):
    dotenv = tmp_path / ".env"
    dotenv.write_text("H_KEY=from-file\n", encoding="utf-8")
    encodings = []
    original = Path.read_text

    def spy(self, encoding=None, errors=None, newline=None):
        encodings.append(encoding)
        return original(self, encoding="utf-8", errors=errors, newline=newline)

    monkeypatch.setattr(Path, "read_text", spy)
    read_var("H_KEY", env={}, dotenv_path=dotenv)
    assert [e.lower() for e in encodings] == ["utf-8"]


def test_openai_key_is_read_from_openai_api_key():
    assert load_key("openai", env={"OPENAI_API_KEY": "o-key"}) == "o-key"


def test_load_key_with_var_reads_that_variable():
    assert load_key("openrouter", env={"OPENROUTER_API_KEY": "r"}, var="OPENROUTER_API_KEY") == "r"


def test_load_key_with_var_accepts_unknown_provider():
    assert load_key("myhost", env={"H_KEY": "h"}, var="H_KEY") == "h"


def test_load_key_with_var_ignores_builtin_variable_of_same_provider():
    assert load_key("openai", env={"OPENAI_API_KEY": "o"}, var="H_KEY") is None


def test_load_key_with_var_env_wins_over_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("H_KEY=from-file\n", encoding="utf-8")
    assert load_key("h", env={"H_KEY": "from-env"}, dotenv_path=dotenv, var="H_KEY") == "from-env"


def test_load_key_with_var_from_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("H_KEY=from-file\n", encoding="utf-8")
    assert load_key("h", env={}, dotenv_path=dotenv, var="H_KEY") == "from-file"


def test_load_key_with_var_empty_in_both_is_none(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("H_KEY=\n", encoding="utf-8")
    assert load_key("h", env={"H_KEY": ""}, dotenv_path=dotenv, var="H_KEY") is None


def test_read_var_from_env():
    assert read_var("X", env={"X": "1"}) == "1"


def test_read_var_missing_is_none():
    assert read_var("X", env={}) is None


def test_read_var_empty_env_falls_back_to_dotenv(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("X=file\n", encoding="utf-8")
    assert read_var("X", env={"X": ""}, dotenv_path=dotenv) == "file"


def test_read_var_default_env_is_os_environ(monkeypatch):
    monkeypatch.setenv("AI_DM_TEST_VAR", "from-os")
    assert read_var("AI_DM_TEST_VAR") == "from-os"


def test_write_dotenv_var_creates_missing_file_with_parents(tmp_path):
    path = tmp_path / "cfg" / "sub" / ".env"
    write_dotenv_var(path, "A", "1")
    assert path.read_text(encoding="utf-8") == "A=1\n"


def test_write_dotenv_var_file_mode_is_600(tmp_path):
    path = tmp_path / ".env"
    write_dotenv_var(path, "A", "1")
    assert path.stat().st_mode & 0o777 == 0o600


def test_write_dotenv_var_leaves_no_tmp_file(tmp_path):
    write_dotenv_var(tmp_path / ".env", "A", "1")
    assert [p.name for p in tmp_path.iterdir()] == [".env"]


def test_write_dotenv_var_appends_new_name_keeping_the_rest(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# ключи\nA=1\n", encoding="utf-8")
    write_dotenv_var(path, "B", "2")
    assert path.read_text(encoding="utf-8") == "# ключи\nA=1\nB=2\n"


def test_write_dotenv_var_replaces_only_its_line(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# комментарий\nA=1\n\nB=2\nмусор\nC=3\n", encoding="utf-8")
    write_dotenv_var(path, "B", "новое")
    assert path.read_text(encoding="utf-8") == "# комментарий\nA=1\n\nB=новое\nмусор\nC=3\n"


def test_write_dotenv_var_replaces_the_first_of_duplicates(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=1\nA=2\n", encoding="utf-8")
    write_dotenv_var(path, "A", "9")
    assert path.read_text(encoding="utf-8") == "A=9\nA=2\n"


def test_write_dotenv_var_ignores_commented_line_with_the_name(tmp_path):
    path = tmp_path / ".env"
    path.write_text("# A=старое\n", encoding="utf-8")
    write_dotenv_var(path, "A", "1")
    assert path.read_text(encoding="utf-8") == "# A=старое\nA=1\n"


def test_write_dotenv_var_skips_line_without_equals_even_if_it_is_the_name(tmp_path):
    path = tmp_path / ".env"
    path.write_text("мусор\n", encoding="utf-8")
    write_dotenv_var(path, "мусор", "1")
    assert path.read_text(encoding="utf-8") == "мусор\nмусор=1\n"


def test_write_dotenv_var_skips_comment_even_if_it_looks_like_the_name(tmp_path):
    path = tmp_path / ".env"
    path.write_text("#A=старое\n", encoding="utf-8")
    write_dotenv_var(path, "#A", "1")
    assert path.read_text(encoding="utf-8") == "#A=старое\n#A=1\n"


def test_write_dotenv_var_replaces_line_whose_value_contains_equals(tmp_path):
    path = tmp_path / ".env"
    path.write_text("A=x=y\nB=2\n", encoding="utf-8")
    write_dotenv_var(path, "A", "1")
    assert path.read_text(encoding="utf-8") == "A=1\nB=2\n"


def test_write_dotenv_var_does_not_match_name_prefix(tmp_path):
    path = tmp_path / ".env"
    path.write_text("AB=1\n", encoding="utf-8")
    write_dotenv_var(path, "A", "2")
    assert parse_dotenv(path.read_text(encoding="utf-8")) == {"AB": "1", "A": "2"}


def test_write_dotenv_var_value_is_readable_back(tmp_path):
    path = tmp_path / ".env"
    write_dotenv_var(path, "OPENROUTER_API_KEY", "sk-or-abc==")
    assert read_var("OPENROUTER_API_KEY", env={}, dotenv_path=path) == "sk-or-abc=="


def test_redact_replaces_secret():
    assert SECRET not in redact(f"ключ {SECRET} неверен", [SECRET])


def test_redact_keeps_the_rest_of_text():
    out = redact(f"ключ {SECRET} неверен", [SECRET])
    assert out.startswith("ключ ") and out.endswith(" неверен")


def test_redact_replaces_every_occurrence():
    assert SECRET not in redact(f"{SECRET} и {SECRET}", [SECRET])


def test_redact_handles_several_secrets():
    out = redact("a-secret b-secret", ["a-secret", "b-secret"])
    assert "a-secret" not in out and "b-secret" not in out


def test_redact_without_secret_in_text_changes_nothing():
    assert redact("обычный текст", [SECRET]) == "обычный текст"


def test_redact_ignores_empty_secret():
    assert redact("текст", ["", None]) == "текст"


def empty_bundle():
    manifest = Manifest(
        schema_version=3, engine_version="0.1.0", world_id="w1", campaign_id="vale", slot="auto",
        saved_at="2026-01-01T12:00:00Z", current_hero_id=None, heroes=[],
    )
    return SaveBundle(
        manifest=manifest,
        world=WorldState(world_id="w1", campaign_id="vale", rng=Rng(1).state),
        chronicle=Chronicle(), memory=Memory(), heroes=[], session=SessionState(),
    )


def all_text_under(root):
    # содержимое всех файлов (gz -- распакованное), чтобы искать значение ключа
    chunks = []
    for path in sorted(root.rglob("*")):
        if path.is_file():
            data = path.read_bytes()
            if path.suffix == ".gz":
                data = gzip.decompress(data)
            chunks.append(data)
    return b"\n".join(chunks)


def test_watchdog_key_value_is_not_written_anywhere_after_mock_turn(tmp_path):
    # ключ живёт в .env игры; прогон хода на моке: вызовы с повтором, журнал, учёт, сейв
    dotenv = tmp_path / ".env"
    dotenv.write_text(f"ANTHROPIC_API_KEY={SECRET}\n", encoding="utf-8")
    assert load_key("anthropic", env={}, dotenv_path=dotenv) == SECRET

    saves = tmp_path / "saves"
    cfg = app_cfg()
    steps = [{"error": "transient"}, {"text": "Ход мастера.", "usage": {"input": 9}}]
    adapter = ScriptedAdapter(steps)
    journal = Journal(saves, "w1", JournalConfig(max_mb=50, segment_mb=1))
    ledger = CostLedger(saves, "w1")
    attempts = []

    def on_attempt(n, resp, err):
        attempts.append(n)
        journal.record_call(
            call_id=f"c{n}", run_id="run-1", ts="2026-10-03T12:00:00Z", turn_seq=1, attempt=n,
            role="narrator", provider="mock",
            model="claude-opus-5-5", request=make_request(), response=resp, error=err,
        )

    resp = call_with_retries(adapter, make_request(), cfg.retry, lambda s: None, on_attempt)
    ledger.add(
        call_id="c2", role="narrator", model="claude-opus-5-5", usage=resp.usage,
        cost_nano=cost_nano(resp.usage, cfg.prices["claude-opus-5-5"]), day=DAY,
    )
    journal.mark_turn("run-1", "committed")
    save_slot(saves, empty_bundle(), "auto", saved_at="2026-10-03T12:00:00Z")

    assert attempts == [1, 2]
    assert (saves / "w1" / "journal").is_dir()
    assert (saves / "w1" / "meta" / "costs.jsonl").is_file()
    assert SECRET.encode() not in all_text_under(saves)


def test_watchdog_even_a_transient_error_with_key_text_is_not_logged(tmp_path):
    # адаптер, по ошибке вставивший ключ в сообщение, не должен протащить его в журнал:
    # журнал пишет только то, что прислал адаптер, поэтому защита -- на стороне адаптеров
    # (см. test_llm_anthropic_adapter.py); здесь проверяем, что redact применим к тексту ошибки.
    err = LlmTransient(redact(f"Incorrect API key: {SECRET}", [SECRET]))
    journal = Journal(tmp_path / "saves", "w1", JournalConfig(max_mb=50, segment_mb=1))
    journal.record_call(
        call_id="c1", run_id="run-1", ts="2026-10-03T12:00:00Z", turn_seq=1, attempt=1,
        role="narrator", provider="mock", model="m", request=make_request(), error=err,
    )
    assert SECRET.encode() not in all_text_under(tmp_path)


# сквозной сторож (ревью партии 3, D11): настоящие адаптеры на фейковых клиентах, ошибка с
# ключом в тексте -> call_with_retries -> журнал; ключа нет ни в одном файле

class ProviderError(Exception):
    # ошибка SDK: и status_code (Anthropic), и code (Gemini)
    def __init__(self, code, message):
        super().__init__(message)
        self.status_code = code
        self.code = code
        self.response = SimpleNamespace(headers={})


class FailingMessages:
    def __init__(self, error):
        self.error = error

    def create(self, **kwargs):
        raise self.error


class FailingModels:
    def __init__(self, error):
        self.error = error

    def generate_content(self, **kwargs):
        raise self.error


def anthropic_adapter(error):
    client = SimpleNamespace(messages=FailingMessages(error))
    return AnthropicAdapter(
        "claude-opus-5-5", app_cfg(), client_factory=lambda **kw: client, api_key=SECRET,
    )


def gemini_adapter(error):
    client = SimpleNamespace(models=FailingModels(error))
    return GeminiAdapter("gemini-3.8-flash", app_cfg(), client=client, api_key=SECRET)


MODELS = {anthropic_adapter: "claude-opus-5-5", gemini_adapter: "gemini-3.8-flash"}


def run_failing_turn(tmp_path, adapter, req):
    saves = tmp_path / "saves"
    journal = Journal(saves, "w1", JournalConfig(max_mb=50, segment_mb=1))
    raised = []

    def on_attempt(n, resp, err):
        journal.record_call(
            call_id=f"c{n}", run_id="run-1", ts="2026-10-03T12:00:00Z", turn_seq=1, attempt=n,
            role="narrator", provider="p", model=req.model, request=req, response=resp, error=err,
        )

    try:
        call_with_retries(adapter, req, app_cfg().retry, lambda s: None, on_attempt)
    except LlmError as error:
        raised.append(error)
    journal.mark_turn("run-1", "aborted")
    return raised


@pytest.mark.parametrize("code", [401, 429, 503])
@pytest.mark.parametrize("make_adapter", [anthropic_adapter, gemini_adapter])
def test_watchdog_provider_error_with_key_is_not_written_anywhere(tmp_path, make_adapter, code):
    error = ProviderError(code, f"Incorrect API key provided: {SECRET}")
    req = make_request(model=MODELS[make_adapter])
    raised = run_failing_turn(tmp_path, make_adapter(error), req)
    assert (tmp_path / "saves" / "w1" / "journal").is_dir()
    assert SECRET.encode() not in all_text_under(tmp_path)
    assert SECRET not in str(raised[0])


@pytest.mark.parametrize("make_adapter", [anthropic_adapter, gemini_adapter])
def test_watchdog_error_is_really_journaled_without_the_key(tmp_path, make_adapter):
    # сторож не должен быть пустым: ошибка в журнале есть, ключ в ней заменён
    error = ProviderError(401, f"Incorrect API key provided: {SECRET}")
    req = make_request(model=MODELS[make_adapter])
    run_failing_turn(tmp_path, make_adapter(error), req)
    journal = Journal(tmp_path / "saves", "w1", JournalConfig(max_mb=50, segment_mb=1))
    records = journal.read_records()
    assert len(records) == 1
    assert "Incorrect API key provided" in records[0]["error"]["message"]
    assert "***" in records[0]["error"]["message"]


@pytest.mark.parametrize("make_adapter", [anthropic_adapter, gemini_adapter])
def test_watchdog_original_error_is_in_cause(tmp_path, make_adapter):
    # исходное исключение лежит в __cause__ (для этапа 6: в репорт его не выводить)
    error = ProviderError(401, f"Incorrect API key provided: {SECRET}")
    adapter = make_adapter(error)
    req = make_request(model=MODELS[make_adapter])
    with pytest.raises(LlmError) as info:
        adapter.complete(req)
    assert info.value.__cause__ is error
