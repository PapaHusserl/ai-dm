# Т60 «Сеть» (docs/plan-t60.md п.1.8, Q5): лог старта попытки.
#   call_with_retries(..., on_start=None): on_start(attempt) перед КАЖДЫМ adapter.complete;
#   Journal.note_start(ts, run_id, turn_seq, role, model, attempt) -- строка
#   "ts\trun_id\tturn_seq\trole\tmodel\tattempt" в journal/attempts.log (не calls-*).
import pytest
from llm_kit import app_cfg, make_request, make_response

from ai_dm.config.app import JournalConfig
from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient, RetriesExhausted
from ai_dm.llm.journal import Journal
from ai_dm.llm.retry import call_with_retries

TS = "2026-10-03T12:00:00+00:00"


class Flaky:
    def __init__(self, results, events):
        self.results = list(results)
        self.events = events

    def complete(self, req):
        self.events.append("complete")
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result

    def info(self):
        return AdapterInfo(provider="flaky", model="m")


def run(results, on_start=None, on_attempt=None, policy=None):
    events = []
    adapter = Flaky(results, events)
    call_with_retries(
        adapter, make_request(), policy or app_cfg().retry, lambda s: None, on_attempt, on_start
    )
    return events


def test_on_start_is_called_before_complete_on_success():
    events = []
    results = [make_response()]
    adapter = Flaky(results, events)
    call_with_retries(
        adapter, make_request(), app_cfg().retry, lambda s: None, None,
        lambda n: events.append(f"start{n}"),
    )
    assert events == ["start1", "complete"]


def test_on_start_called_for_every_attempt_with_its_number():
    starts = []
    run([LlmTransient("x"), LlmTransient("x"), make_response()], on_start=starts.append)
    assert starts == [1, 2, 3]


def test_on_start_called_once_for_fatal():
    starts = []
    with pytest.raises(LlmFatal):
        run([LlmFatal("x")], on_start=starts.append)
    assert starts == [1]


def test_on_start_called_for_each_attempt_before_exhaustion():
    starts = []
    with pytest.raises(RetriesExhausted):
        run([LlmTransient("x")] * 4, on_start=starts.append)
    assert starts == [1, 2, 3, 4]


def test_on_start_with_empty_delays_is_called_once():
    policy = app_cfg().retry.model_copy(update={"delays": []})
    starts = []
    with pytest.raises(RetriesExhausted):
        run([LlmTransient("x"), make_response()], on_start=starts.append, policy=policy)
    assert starts == [1]


def test_on_start_precedes_on_attempt_and_next_start():
    events = []
    results = [LlmTransient("x"), make_response()]
    adapter = Flaky(results, events)
    call_with_retries(
        adapter, make_request(), app_cfg().retry, lambda s: None,
        lambda n, resp, err: events.append(f"attempt{n}"),
        lambda n: events.append(f"start{n}"),
    )
    assert events == ["start1", "complete", "attempt1", "start2", "complete", "attempt2"]


def test_without_on_start_works_as_before():
    assert run([LlmTransient("x"), make_response()]) == ["complete", "complete"]


# Journal.note_start

def journal_of(tmp_path):
    return Journal(tmp_path, "w1", JournalConfig(max_mb=50, segment_mb=5))


def lines_of(journal):
    return (journal.dir / "attempts.log").read_text(encoding="utf-8").splitlines()


def test_note_start_writes_tab_separated_line(tmp_path):
    journal = journal_of(tmp_path)
    journal.note_start(TS, "run-1", 7, "narrator", "gemini-3.8-flash", 2)
    assert lines_of(journal) == [f"{TS}\trun-1\t7\tnarrator\tgemini-3.8-flash\t2"]


def test_note_start_appends_in_order(tmp_path):
    journal = journal_of(tmp_path)
    journal.note_start(TS, "run-1", 1, "narrator", "m", 1)
    journal.note_start(TS, "run-1", 1, "narrator", "m", 2)
    journal.note_start(TS, "bnd-1", 1, "summarizer", "s", 1)
    rows = [line.split("\t") for line in lines_of(journal)]
    assert [(r[1], r[5]) for r in rows] == [("run-1", "1"), ("run-1", "2"), ("bnd-1", "1")]
    assert rows[2][3] == "summarizer"


def test_note_start_creates_journal_dir_and_lives_in_it(tmp_path):
    journal = journal_of(tmp_path)
    assert not journal.dir.exists()
    journal.note_start(TS, "run-1", 1, "narrator", "m", 1)
    assert (tmp_path / "w1" / "journal" / "attempts.log").is_file()


def test_attempts_log_is_not_a_call_segment(tmp_path):
    journal = journal_of(tmp_path)
    journal.note_start(TS, "run-1", 1, "narrator", "m", 1)
    assert journal.segments() == []
    assert journal.read_records() == []
    assert journal.records_for(["run-1"]) == []


def test_attempts_log_does_not_break_rotation_and_orphan_cleanup(tmp_path):
    journal = journal_of(tmp_path)
    journal.note_start(TS, "run-1", 1, "narrator", "m", 1)
    journal.record_call(
        call_id="c1", run_id="run-1", ts=TS, turn_seq=1, attempt=1, role="narrator",
        provider="p", model="m", request=make_request(), response=make_response(),
    )
    journal.note_start(TS, "run-2", 2, "narrator", "m", 1)
    journal.drop_old_segments()
    journal.drop_orphan_blobs(journal.segments())
    journal.mark_turn("run-1", "committed")
    assert [r["call_id"] for r in journal.read_records()] == ["c1"]
    assert len(lines_of(journal)) == 2
