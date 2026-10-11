# Ожидаемый API: ai_dm.llm.journal (Journal, request_fingerprint) -- контракт в llm_kit.py.
# ТЗ 11: журнал вызовов рядом с сейвом (saves/<world>/journal/), статические блоки -- в blobs/ по
# sha256, ротация по segment_mb с gzip, общий предел max_mb, turn_status целого хода.
import gzip
import hashlib
import json
import os

import pytest
from llm_kit import full_request, make_request, make_response

from ai_dm.config.app import JournalConfig
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.journal import Journal, request_fingerprint
from ai_dm.llm.types import ChatResponse, SystemBlock, Text, ToolSpec, Usage
from ai_dm.protocol.schema import tool_set

CFG = JournalConfig(max_mb=50, segment_mb=5)
TS = "2026-10-03T12:00:00+00:00"
FIELDS = {
    "call_id", "run_id", "ts", "world_id", "turn_seq", "attempt", "role", "provider", "model",
    "request", "response", "usage", "cost_nano", "request_id", "stop_reason", "error",
    "report_tags", "turn_status", "meta",
}


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def make_journal(tmp_path, cfg=CFG, world="w1"):
    return Journal(tmp_path / "saves", world, cfg)


def record(journal, n=1, *, turn_seq=1, attempt=1, req=None, resp=None, run_id=None, **kw):
    # run_id по умолчанию -- свой на каждый ход: run-<turn_seq>
    journal.record_call(
        call_id=f"c{n}", run_id=run_id or f"run-{turn_seq}", ts=TS,
        turn_seq=turn_seq, attempt=attempt, role="narrator",
        provider="anthropic", model="claude-opus-5-5",
        request=req or make_request(), response=resp or make_response(), **kw,
    )


def big_response(n):
    # несжимаемый текст ~120 КБ, чтобы сегменты быстро наполнялись
    return ChatResponse(
        content=[Text(text=os.urandom(60_000).hex())], stop_reason="end_turn",
        usage=Usage(input=1, output=1), request_id=f"r{n}", model="claude-opus-5-5",
    )


def disk_size(journal):
    return sum(p.stat().st_size for p in journal.dir.glob("calls-*"))


def test_journal_dir_is_saves_world_journal(tmp_path):
    journal = make_journal(tmp_path)
    assert journal.dir == tmp_path / "saves" / "w1" / "journal"


def test_first_record_creates_first_segment(tmp_path):
    journal = make_journal(tmp_path)
    record(journal)
    assert (journal.dir / "calls-001.jsonl").is_file()


def test_segment_is_json_lines(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    record(journal, 2)
    lines = (journal.dir / "calls-001.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(line)["call_id"] for line in lines] == ["c1", "c2"]


def test_record_has_all_fields(tmp_path):
    journal = make_journal(tmp_path)
    record(journal)
    assert set(journal.read_records()[0]) >= FIELDS


def test_record_basic_values(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 7, turn_seq=3, attempt=2, cost_nano=1234)
    rec = journal.read_records()[0]
    assert (rec["call_id"], rec["world_id"], rec["turn_seq"], rec["attempt"]) == ("c7", "w1", 3, 2)
    assert (rec["role"], rec["provider"], rec["model"]) == (
        "narrator", "anthropic", "claude-opus-5-5",
    )
    assert rec["cost_nano"] == 1234


def test_record_response_usage_and_stop_reason(tmp_path):
    journal = make_journal(tmp_path)
    resp = make_response(usage=Usage(input=10, output=5, cache_read=3), request_id="req-42")
    record(journal, resp=resp)
    rec = journal.read_records()[0]
    assert rec["response"] == resp.model_dump(mode="json")
    assert rec["usage"] == {
        "input": 10, "output": 5, "cache_write": 0, "cache_write_1h": 0, "cache_read": 3,
        "cache_storage_min": 0,
    }
    assert (rec["request_id"], rec["stop_reason"]) == ("req-42", "end_turn")


def test_record_defaults_error_tags_and_status(tmp_path):
    journal = make_journal(tmp_path)
    record(journal)
    rec = journal.read_records()[0]
    assert (rec["error"], rec["report_tags"], rec["turn_status"]) == (None, [], None)


def test_record_keeps_report_tags(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, report_tags=["refusal"])
    assert journal.read_records()[0]["report_tags"] == ["refusal"]


def test_transient_error_record(tmp_path):
    journal = make_journal(tmp_path)
    journal.record_call(
        call_id="c1", run_id="run-1", ts=TS, turn_seq=1, attempt=1, role="narrator",
        provider="anthropic", model="claude-opus-5-5", request=make_request(),
        error=LlmTransient("сеть", retry_after=4),
    )
    rec = journal.read_records()[0]
    assert rec["error"] == {"kind": "transient", "message": "сеть", "retry_after": 4}
    assert (rec["response"], rec["stop_reason"], rec["request_id"]) == (None, None, None)
    assert rec["usage"] == {
        "input": 0, "output": 0, "cache_write": 0, "cache_write_1h": 0, "cache_read": 0,
        "cache_storage_min": 0,
    }


def test_fatal_error_record(tmp_path):
    journal = make_journal(tmp_path)
    journal.record_call(
        call_id="c1", run_id="run-1", ts=TS, turn_seq=1, attempt=1, role="narrator",
        provider="anthropic", model="claude-opus-5-5", request=make_request(),
        error=LlmFatal("400"),
    )
    err = journal.read_records()[0]["error"]
    assert (err["kind"], err["message"], err["retry_after"]) == ("fatal", "400", None)


def test_refusal_response_is_logged_as_response_not_error(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, resp=make_response(text="нет", stop_reason="refusal"))
    rec = journal.read_records()[0]
    assert (rec["stop_reason"], rec["error"]) == ("refusal", None)


def test_request_messages_are_stored_inline(tmp_path):
    journal = make_journal(tmp_path)
    req = full_request()
    record(journal, req=req)
    stored = journal.read_records()[0]["request"]
    assert stored["messages"] == [m.model_dump(mode="json") for m in req.messages]
    assert (stored["max_tokens"], stored["effort"]) == (8000, "medium")


def test_request_fingerprint_is_stored(tmp_path):
    journal = make_journal(tmp_path)
    req = full_request()
    record(journal, req=req)
    assert journal.read_records()[0]["request"]["fingerprint"] == request_fingerprint(req)


def test_fingerprint_is_sha256_of_canonical_request():
    req = full_request()
    expected = hashlib.sha256(canon(req.model_dump(mode="json"))).hexdigest()
    assert request_fingerprint(req) == expected


def test_fingerprint_changes_with_message():
    assert request_fingerprint(make_request("а")) != request_fingerprint(make_request("б"))


def test_fingerprint_same_for_equal_requests():
    assert request_fingerprint(make_request("а")) == request_fingerprint(make_request("а"))


def static_req():
    tools = [ToolSpec.model_validate(t) for t in tool_set("combat_classify")]
    system = [SystemBlock(text="правила", cache=True), SystemBlock(text="мир", cache=True)]
    return make_request(system=system, tools=tools)


def test_system_and_tools_go_to_blobs_by_sha256(tmp_path):
    journal = make_journal(tmp_path)
    req = static_req()
    record(journal, req=req)
    stored = journal.read_records()[0]["request"]
    system_bytes = canon([b.model_dump(mode="json") for b in req.system])
    tools_bytes = canon([t.model_dump(mode="json") for t in req.tools])
    assert stored["system_sha256"] == hashlib.sha256(system_bytes).hexdigest()
    assert stored["tools_sha256"] == hashlib.sha256(tools_bytes).hexdigest()
    assert (journal.dir / "blobs" / f"{stored['system_sha256']}.json").read_bytes() == system_bytes
    assert (journal.dir / "blobs" / f"{stored['tools_sha256']}.json").read_bytes() == tools_bytes


def test_static_blocks_are_not_inlined_in_the_record(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, req=static_req())
    stored = journal.read_records()[0]["request"]
    assert "system" not in stored and "tools" not in stored


def test_identical_static_blocks_make_one_blob_each(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, req=static_req())
    record(journal, 2, req=static_req())
    assert len(list((journal.dir / "blobs").iterdir())) == 2


def test_different_messages_share_blobs(tmp_path):
    journal = make_journal(tmp_path)
    first = static_req()
    second = first.model_copy(update={"messages": make_request("другое").messages})
    record(journal, 1, req=first)
    record(journal, 2, req=second)
    assert len(list((journal.dir / "blobs").iterdir())) == 2


def test_changed_tools_add_a_new_blob(tmp_path):
    journal = make_journal(tmp_path)
    first = static_req()
    other_tools = [ToolSpec.model_validate(t) for t in tool_set("npc_choice")]
    record(journal, 1, req=first)
    record(journal, 2, req=first.model_copy(update={"tools": other_tools}))
    assert len(list((journal.dir / "blobs").iterdir())) == 3


def test_turn_status_is_none_until_marked(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=4)
    assert journal.read_records()[0]["turn_status"] is None


def test_mark_turn_committed_marks_all_records_of_turn(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=4)
    record(journal, 2, turn_seq=4)
    journal.mark_turn("run-4", "committed")
    assert [r["turn_status"] for r in journal.read_records()] == ["committed", "committed"]


def test_mark_turn_aborted_touches_only_that_turn(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=3)
    record(journal, 2, turn_seq=4)
    journal.mark_turn("run-3", "committed")
    journal.mark_turn("run-4", "aborted")
    assert [r["turn_status"] for r in journal.read_records()] == ["committed", "aborted"]


def test_retry_of_aborted_turn_gets_its_own_status(tmp_path):
    # откат хода и «повторить»: тот же turn_seq, новые вызовы, новый итог
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=5, run_id="run-5a")
    journal.mark_turn("run-5a", "aborted")
    record(journal, 2, turn_seq=5, run_id="run-5b")
    assert [r["turn_status"] for r in journal.read_records()] == ["aborted", None]
    journal.mark_turn("run-5b", "committed")
    assert [r["turn_status"] for r in journal.read_records()] == ["aborted", "committed"]


def test_record_keeps_actual_and_requested_models(tmp_path):
    journal = make_journal(tmp_path)
    journal.record_call(
        call_id="c1", run_id="r", ts=TS, turn_seq=1, attempt=1, role="narrator",
        provider="anthropic", model="claude-opus-5-5-20261001",
        request=make_request(model="claude-opus-5-5"), response=make_response(),
    )
    rec = journal.read_records()[0]
    assert (rec["model"], rec["requested_model"]) == (
        "claude-opus-5-5-20261001", "claude-opus-5-5",
    )


def test_record_keeps_run_id_and_ts(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, run_id="run-xyz")
    rec = journal.read_records()[0]
    assert (rec["run_id"], rec["ts"]) == ("run-xyz", TS)


def test_ts_is_taken_from_the_parameter(tmp_path):
    journal = make_journal(tmp_path)
    journal.record_call(
        call_id="c1", run_id="r", ts="тестовая-метка", turn_seq=1, attempt=1, role="narrator",
        provider="anthropic", model="claude-opus-5-5", request=make_request(),
        response=make_response(),
    )
    assert journal.read_records()[0]["ts"] == "тестовая-метка"


def test_two_runs_of_the_same_turn_seq_are_told_apart(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=7, run_id="run-a")
    record(journal, 2, turn_seq=7, run_id="run-b")
    assert [(r["turn_seq"], r["run_id"]) for r in journal.read_records()] == [
        (7, "run-a"), (7, "run-b"),
    ]


def test_mark_turn_marks_only_its_run_of_the_same_turn_seq(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=7, run_id="run-a")
    record(journal, 2, turn_seq=7, run_id="run-b")
    journal.mark_turn("run-b", "committed")
    assert [r["turn_status"] for r in journal.read_records()] == [None, "committed"]


def test_mark_turn_marks_all_records_of_the_run(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=7, run_id="run-a")
    record(journal, 2, turn_seq=7, attempt=2, run_id="run-a")
    journal.mark_turn("run-a", "aborted")
    assert [r["turn_status"] for r in journal.read_records()] == ["aborted", "aborted"]


def test_mark_turn_of_unknown_run_changes_nothing(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=7, run_id="run-a")
    journal.mark_turn("run-zzz", "committed")
    assert journal.read_records()[0]["turn_status"] is None


def test_mark_turn_does_not_override_already_set_status(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, run_id="run-a")
    journal.mark_turn("run-a", "aborted")
    journal.mark_turn("run-a", "committed")
    assert journal.read_records()[0]["turn_status"] == "aborted"


def test_mark_turn_rejects_unknown_status(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=4)
    with pytest.raises(ValueError):
        journal.mark_turn("run-4", "pending")


def test_records_survive_reopening(tmp_path):
    first = make_journal(tmp_path)
    record(first, 1)
    first.mark_turn("run-1", "committed")
    second = make_journal(tmp_path)
    record(second, 2, turn_seq=2)
    recs = second.read_records()
    assert [(r["call_id"], r["turn_status"]) for r in recs] == [("c1", "committed"), ("c2", None)]


def test_old_segments_are_gzipped_and_one_plain_remains(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=50, segment_mb=1))
    for n in range(30):
        record(journal, n, resp=big_response(n))
    names = sorted(p.name for p in journal.dir.glob("calls-*"))
    plain = [n for n in names if n.endswith(".jsonl")]
    zipped = [n for n in names if n.endswith(".jsonl.gz")]
    assert len(zipped) >= 2
    assert len(plain) == 1
    assert plain[0] > max(zipped)


def test_gzipped_segment_is_valid_json_lines(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=50, segment_mb=1))
    for n in range(30):
        record(journal, n, resp=big_response(n))
    first = journal.dir / "calls-001.jsonl.gz"
    lines = gzip.decompress(first.read_bytes()).decode("utf-8").splitlines()
    assert json.loads(lines[0])["call_id"] == "c0"


def test_read_records_spans_segments_in_order(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=50, segment_mb=1))
    for n in range(30):
        record(journal, n, resp=big_response(n))
    assert [r["call_id"] for r in journal.read_records()] == [f"c{n}" for n in range(30)]


def test_total_size_is_limited_by_max_mb(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    for n in range(100):
        record(journal, n, resp=big_response(n))
    assert disk_size(journal) <= 3_000_000


def test_limit_drops_oldest_and_keeps_newest(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    for n in range(100):
        record(journal, n, resp=big_response(n))
    ids = [int(r["call_id"][1:]) for r in journal.read_records()]
    assert ids[-1] == 99
    assert ids[0] > 0
    assert ids == list(range(ids[0], 100))


def test_small_journal_below_limit_loses_nothing(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    for n in range(5):
        record(journal, n)
    assert len(journal.read_records()) == 5


# обрыв записи (ревью партии 3, D8): последняя строка сегмента может быть оборвана

def cut_tail(journal, n=20):
    path = journal.dir / "calls-001.jsonl"
    path.write_bytes(path.read_bytes()[:-n])
    return path


def test_truncated_last_line_is_skipped_on_read(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    record(journal, 2)
    cut_tail(journal)
    assert [r["call_id"] for r in journal.read_records()] == ["c1"]


def test_truncated_last_line_without_newline_is_skipped(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    path = journal.dir / "calls-001.jsonl"
    with path.open("a", encoding="utf-8") as f:
        f.write('{"call_id": "c2", "run_i')
    assert [r["call_id"] for r in journal.read_records()] == ["c1"]


def test_mark_turn_survives_truncated_last_line(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    cut_tail(journal)
    journal.mark_turn("run-1", "committed")
    assert [(r["call_id"], r["turn_status"]) for r in journal.read_records()] == [
        ("c1", "committed"),
    ]


def test_mark_turn_of_cut_run_does_not_crash(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    cut_tail(journal)
    journal.mark_turn("run-2", "aborted")
    assert [r["turn_status"] for r in journal.read_records()] == [None]


def test_mark_turn_rewrites_through_os_replace(tmp_path, monkeypatch):
    journal = make_journal(tmp_path)
    record(journal, 1)
    calls = []
    real_replace = os.replace

    def spy(src, dst):
        calls.append(dst)
        real_replace(src, dst)

    monkeypatch.setattr(os, "replace", spy)
    journal.mark_turn("run-1", "committed")
    assert [os.fspath(c) for c in calls] == [os.fspath(journal.dir / "calls-001.jsonl")]


def test_failed_rewrite_leaves_the_segment_unchanged(tmp_path, monkeypatch):
    journal = make_journal(tmp_path)
    record(journal, 1)
    path = journal.dir / "calls-001.jsonl"
    before = path.read_bytes()

    def boom(src, dst):
        raise OSError("обрыв")

    monkeypatch.setattr(os, "replace", boom)
    with pytest.raises(OSError):
        journal.mark_turn("run-1", "committed")
    assert path.read_bytes() == before


def test_mark_turn_leaves_no_temporary_files(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    journal.mark_turn("run-1", "committed")
    assert [p.name for p in journal.dir.iterdir() if p.is_file()] == ["calls-001.jsonl"]


def test_mark_turn_keeps_gz_segment_readable(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=50, segment_mb=1))
    record(journal, 0, run_id="run-old")
    for n in range(1, 30):
        record(journal, n, resp=big_response(n), run_id="run-new")
    journal.mark_turn("run-old", "aborted")
    records = journal.read_records()
    assert records[0]["turn_status"] == "aborted"
    assert len(records) == 30


# осиротевшие blobs (ревью партии 3, D10)

def blob_names(journal):
    return {p.stem for p in (journal.dir / "blobs").iterdir()}


def test_orphan_blobs_are_removed_with_dropped_segments(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    old_req = make_request(system=[SystemBlock(text="старые правила", cache=True)])
    record(journal, 0, req=old_req, resp=big_response(0))
    old_sha = journal.read_records()[0]["request"]["system_sha256"]
    for n in range(1, 100):
        record(journal, n, resp=big_response(n))
    assert journal.read_records()[0]["call_id"] != "c0"
    assert old_sha not in blob_names(journal)


def test_blobs_of_remaining_records_are_kept(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    for n in range(100):
        record(journal, n, resp=big_response(n))
    shas = {
        sha
        for r in journal.read_records()
        for sha in (r["request"]["system_sha256"], r["request"]["tools_sha256"])
    }
    assert shas <= blob_names(journal)


def test_blob_shared_with_remaining_segment_is_not_removed(tmp_path):
    journal = make_journal(tmp_path, JournalConfig(max_mb=3, segment_mb=1))
    record(journal, 0, resp=big_response(0))
    shared = journal.read_records()[0]["request"]["system_sha256"]
    for n in range(1, 100):
        record(journal, n, resp=big_response(n))
    assert shared in blob_names(journal)


def test_blobs_are_not_removed_while_nothing_is_dropped(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, req=make_request(system=[SystemBlock(text="а")]))
    record(journal, 2, req=make_request(system=[SystemBlock(text="б")]))
    assert len(blob_names(journal)) == 3


# meta записи (P3: план контекста narrator)

def test_record_meta_defaults_to_empty_dict(tmp_path):
    journal = make_journal(tmp_path)
    record(journal)
    assert journal.read_records()[0]["meta"] == {}


def test_record_meta_is_written(tmp_path):
    journal = make_journal(tmp_path)
    meta = {"context": {"budget": 100, "raised": False, "dropped": [["turns", "1"]]}}
    record(journal, meta=meta)
    assert journal.read_records()[0]["meta"] == meta


def test_record_meta_none_gives_empty_dict(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, meta=None)
    assert journal.read_records()[0]["meta"] == {}


def test_meta_does_not_change_fingerprint(tmp_path):
    journal = make_journal(tmp_path)
    request = make_request()
    record(journal, 1, req=request, meta={"context": {"budget": 1}})
    record(journal, 2, req=request)
    first, second = journal.read_records()
    assert first["request"]["fingerprint"] == second["request"]["fingerprint"]


# К0-фикс: stop_detail (сырой повод отказа) попадает в запись журнала

def test_stop_detail_is_written_to_the_response_record(tmp_path):
    journal = make_journal(tmp_path)
    resp = make_response(text="", stop_reason="refusal")
    resp.stop_detail = "PROHIBITED_CONTENT"
    record(journal, resp=resp)
    rec = journal.read_records()[0]
    assert rec["response"]["stop_detail"] == "PROHIBITED_CONTENT"
    assert rec["stop_reason"] == "refusal"


def test_stop_detail_is_none_in_record_when_not_set(tmp_path):
    journal = make_journal(tmp_path)
    record(journal)
    assert journal.read_records()[0]["response"]["stop_detail"] is None
