# Ожидаемый API: Journal.records_for(run_ids) -> list записей журнала с run_id из списка, в порядке
# записи (этап 6а, P1). Читает с конца, как mark_turn; видит сжатые сегменты; пустой список или
# неизвестные run_id -- пустой результат; turn_status -- итоговый (после mark_turn).
from test_llm_journal import CFG, make_journal, record

from ai_dm.config.app import JournalConfig

ONE_PER_SEGMENT = JournalConfig(max_mb=50, segment_mb=0)


def ids(records):
    return [r["call_id"] for r in records]


def test_records_for_returns_records_of_one_run(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    assert ids(journal.records_for(["run-2"])) == ["c2"]


def test_records_for_skips_other_runs(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    record(journal, 3, turn_seq=3)
    assert ids(journal.records_for(["run-1", "run-3"])) == ["c1", "c3"]


def test_records_for_keeps_write_order_not_argument_order(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    assert ids(journal.records_for(["run-2", "run-1"])) == ["c1", "c2"]


def test_records_for_has_all_attempts_of_run(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1, run_id="run-a", attempt=1)
    record(journal, 2, turn_seq=1, run_id="run-a", attempt=2)
    assert [r["attempt"] for r in journal.records_for(["run-a"])] == [1, 2]


def test_records_for_empty_ids_is_empty(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    assert journal.records_for([]) == []


def test_records_for_unknown_run_is_empty(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1)
    assert journal.records_for(["run-zzz"]) == []


def test_records_for_empty_journal_is_empty(tmp_path):
    assert make_journal(tmp_path).records_for(["run-1"]) == []


def test_records_for_has_final_turn_status(tmp_path):
    journal = make_journal(tmp_path)
    record(journal, 1, turn_seq=1)
    journal.mark_turn("run-1", "aborted")
    assert [r["turn_status"] for r in journal.records_for(["run-1"])] == ["aborted"]


def test_records_for_reads_gzipped_segments(tmp_path):
    journal = make_journal(tmp_path, ONE_PER_SEGMENT)
    record(journal, 1, turn_seq=1)
    record(journal, 2, turn_seq=2)
    record(journal, 3, turn_seq=3)
    assert any(p.name.endswith(".gz") for p in journal.segments())
    assert ids(journal.records_for(["run-1"])) == ["c1"]


def test_records_for_finds_run_in_oldest_segment_after_many_others(tmp_path):
    journal = make_journal(tmp_path, ONE_PER_SEGMENT)
    for n in range(1, 6):
        record(journal, n, turn_seq=n)
    assert ids(journal.records_for(["run-1", "run-5"])) == ["c1", "c5"]


def test_records_for_run_split_across_segments_returns_all_records(tmp_path):
    journal = make_journal(tmp_path, ONE_PER_SEGMENT)
    record(journal, 1, turn_seq=1, run_id="run-a", attempt=1)
    record(journal, 2, turn_seq=1, run_id="run-a", attempt=2)
    record(journal, 3, turn_seq=2, run_id="run-b")
    assert ids(journal.records_for(["run-a"])) == ["c1", "c2"]


def test_records_for_does_not_change_journal(tmp_path):
    journal = make_journal(tmp_path, CFG)
    record(journal, 1)
    before = journal.read_records()
    journal.records_for(["run-1"])
    assert journal.read_records() == before
