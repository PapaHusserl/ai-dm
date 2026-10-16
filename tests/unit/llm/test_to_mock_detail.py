# ТО (docs/TO-PLAN.md §1 п.6): ключ шага мока stop_detail -> ChatResponse.stop_detail;
# только вместе со stop; ReplayAdapter отдаёт stop_detail из журнала.
import pytest
from llm_kit import make_request, make_response

from ai_dm.config.app import JournalConfig
from ai_dm.llm.journal import Journal
from ai_dm.llm.mock import ScriptedAdapter, check_step, load_script
from ai_dm.llm.replay import ReplayAdapter


def test_stop_detail_goes_into_response():
    step = {"stop": "refusal", "stop_detail": "PROHIBITED_CONTENT"}
    resp = ScriptedAdapter([step]).complete(make_request())
    assert resp.stop_reason == "refusal"
    assert resp.stop_detail == "PROHIBITED_CONTENT"


def test_stop_detail_is_none_without_the_key():
    resp = ScriptedAdapter([{"stop": "refusal"}]).complete(make_request())
    assert resp.stop_detail is None


def test_stop_detail_works_with_max_tokens_stop_too():
    resp = ScriptedAdapter([{"stop": "max_tokens", "stop_detail": "x"}]).complete(make_request())
    assert resp.stop_detail == "x"


def test_stop_detail_without_stop_is_rejected():
    with pytest.raises(ValueError, match="stop_detail"):
        check_step({"text": "x", "stop_detail": "PROHIBITED_CONTENT"})


def test_stop_detail_without_stop_is_rejected_by_adapter_constructor():
    with pytest.raises(ValueError):
        ScriptedAdapter([{"text": "x", "stop_detail": "SPII"}])


def test_stop_detail_alone_is_still_an_empty_step():
    with pytest.raises(ValueError):
        check_step({"stop_detail": "SPII"})


def test_stop_detail_is_a_known_key_in_yaml(tmp_path):
    path = tmp_path / "s.yaml"
    path.write_text(
        "steps:\n  - stop: refusal\n    stop_detail: BLOCKLIST\n", encoding="utf-8"
    )
    assert load_script(path)[0]["stop_detail"] == "BLOCKLIST"


def test_replay_returns_stop_detail_from_journal(tmp_path):
    journal = Journal(tmp_path / "saves", "w1", JournalConfig(max_mb=50, segment_mb=5))
    req = make_request("раз")
    resp = make_response("", stop_reason="refusal").model_copy(
        update={"stop_detail": "PROHIBITED_CONTENT"}
    )
    journal.record_call(
        call_id="c1", run_id="run-1", ts="2026-10-03T12:00:00", turn_seq=1, attempt=1,
        role=req.role, provider="gemini", model=req.model, request=req, response=resp,
    )
    got = ReplayAdapter(journal.read_records()).complete(req)
    assert got.stop_detail == "PROHIBITED_CONTENT"
    assert got.stop_reason == "refusal"
