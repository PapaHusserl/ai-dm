# Ревью P1 -> P2: блоб записи журнала не найден при записи репорта -- meta.replayable=false
# (раньше блоб молча пропускался, и репорт выглядел воспроизводимым).
import json
from datetime import UTC, datetime

from reports_kit import make_capture
from test_replay_load import make_journal

from ai_dm.reports.writer import write_report

NOW = datetime(2026, 10, 7, 12, 30, 45, tzinfo=UTC)


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def test_all_blobs_present_is_replayable(registry, tmp_path):
    journal = make_journal(tmp_path)
    path = write_report(tmp_path / "s", "w1", make_capture(registry), "т", NOW, journal=journal)
    assert meta_of(path)["replayable"] is True


def test_missing_system_blob_makes_report_not_replayable(registry, tmp_path):
    journal = make_journal(tmp_path, blobs=("bb",))
    path = write_report(tmp_path / "s", "w1", make_capture(registry), "т", NOW, journal=journal)
    assert meta_of(path)["replayable"] is False


def test_missing_tools_blob_makes_report_not_replayable(registry, tmp_path):
    journal = make_journal(tmp_path, blobs=("aa",))
    path = write_report(tmp_path / "s", "w1", make_capture(registry), "т", NOW, journal=journal)
    assert meta_of(path)["replayable"] is False


def test_missing_blob_still_writes_the_report(registry, tmp_path):
    journal = make_journal(tmp_path, blobs=())
    path = write_report(tmp_path / "s", "w1", make_capture(registry), "т", NOW, journal=journal)
    assert (path / "report.md").is_file()
    assert (path / "before").is_dir()
    assert meta_of(path)["calls"] == 1


def test_present_blob_is_still_copied_when_other_is_missing(registry, tmp_path):
    journal = make_journal(tmp_path, blobs=("aa",))
    path = write_report(tmp_path / "s", "w1", make_capture(registry), "т", NOW, journal=journal)
    assert (path / "journal" / "blobs" / "aa.json").is_file()
