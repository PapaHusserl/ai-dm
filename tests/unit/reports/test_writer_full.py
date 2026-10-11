# Ожидаемый API (этап 6а, P1): write_report(saves_root, world_id, capture, text, now, journal=None,
# recent_turns=5) -> Path. before/ -- корень сейвов (load_slot(<отчёт>/before, world_id, "auto")),
# after/ -- только у committed; journal/calls.jsonl + journal/blobs/ -- при journal != None;
# meta.json: replayable (есть журнал), calls (число записей).
import json
import shutil

from reports_kit import NOW, make_capture

from ai_dm.persistence.store import load_slot
from ai_dm.reports.writer import write_report


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def load(path, name, tmp_path):
    root = tmp_path / ("copy-" + name)
    shutil.copytree(path / name, root)
    return load_slot(root, "w1", "auto")


def test_without_journal_has_no_journal_dir_and_replayable_false(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert not (path / "journal").exists()
    assert meta_of(path)["replayable"] is False
    assert meta_of(path)["calls"] == 0


def test_without_journal_report_md_says_journal_is_off(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert "журнал отключён" in (path / "report.md").read_text(encoding="utf-8").lower()


def test_before_is_written_for_every_status(registry, tmp_path):
    for status in ("committed", "aborted", "none"):
        capture = make_capture(registry, status=status)
        path = write_report(tmp_path, "w1", capture, "текст", NOW)
        assert (path / "before").is_dir()


def test_before_snapshot_has_world_of_capture(registry, tmp_path):
    capture = make_capture(registry)
    path = write_report(tmp_path, "w1", capture, "текст", NOW)
    loaded = load(path, "before", tmp_path)
    assert loaded.world.rng == capture.before.world.rng


def test_after_is_written_only_for_committed(registry, tmp_path):
    after = make_capture(registry).before.model_copy(deep=True)
    for status, has_after in (("committed", True), ("aborted", False), ("none", False)):
        given = after if status == "committed" else None
        capture = make_capture(registry, status=status, after=given)
        path = write_report(tmp_path, "w1", capture, "текст", NOW)
        assert (path / "after").is_dir() is has_after


def test_after_snapshot_is_not_written_for_aborted_even_if_given(registry, tmp_path):
    capture = make_capture(registry, status="aborted")
    capture.after = capture.before.model_copy(deep=True)
    path = write_report(tmp_path, "w1", capture, "текст", NOW)
    assert not (path / "after").exists()


def test_no_tmp_dirs_left_after_full_report(registry, tmp_path):
    path = write_report(tmp_path, "w1", make_capture(registry), "текст", NOW)
    assert [p.name for p in path.parent.iterdir() if p.name.startswith("tmp-")] == []
