# API (этап 6а, P2): ai_dm.reports.replay.load_report(path) -> ReportReplay: meta (dict из
# meta.json), before (SaveBundle из <отчёт>/before, слот auto, загружен из КОПИИ во временную папку:
# каталог отчёта не меняется), records (список записей journal/calls.jsonl), player_input,
# now_iso (= meta.now), expected (SaveBundle из after/ или None у откатанного хода),
# failure_reason (из meta).
import shutil
from datetime import UTC, datetime, timedelta

import pytest
from reports_kit import make_capture

from ai_dm.persistence.store import load_slot
from ai_dm.reports.replay import load_report
from ai_dm.reports.writer import write_report

# время записи репорта позже времени хода (reports_kit.NOW)
NOW = datetime(2026, 10, 7, 12, 30, 45, tzinfo=UTC) + timedelta(hours=1)


class FakeJournal:
    # то, что писателю нужно от журнала: dir/blobs/<sha>.json и records_for
    def __init__(self, folder, records):
        self.dir = folder
        self.records = records

    def records_for(self, run_ids):
        return self.records


def record(sha="aa", tools="bb"):
    return {
        "call_id": "run-1-1", "run_id": "run-1", "role": "narrator", "attempt": 1,
        "model": "claude-opus-5-5", "requested_model": "claude-opus-5-5",
        "stop_reason": "end_turn", "error": None,
        "request": {"system_sha256": sha, "tools_sha256": tools, "messages": []},
        "response": {"content": [], "stop_reason": "end_turn"}, "turn_status": "committed",
    }


def make_journal(tmp_path, blobs=("aa", "bb")):
    folder = tmp_path / "live-journal"
    (folder / "blobs").mkdir(parents=True)
    for sha in blobs:
        (folder / "blobs" / f"{sha}.json").write_text("{}", encoding="utf-8")
    return FakeJournal(folder, [record()])


def tree(path):
    files = sorted(p for p in path.rglob("*") if p.is_file())
    return {str(p.relative_to(path)): p.read_bytes() for p in files}


def written(registry, tmp_path, campaign_id=None, **fields):
    after = make_capture(registry).before.model_copy(deep=True)
    capture = make_capture(registry, after=after, **fields)
    capture.before.manifest.campaign_id = campaign_id
    capture.after.manifest.campaign_id = campaign_id
    journal = make_journal(tmp_path)
    return write_report(tmp_path / "saves", "w1", capture, "текст", NOW, journal=journal), capture


def test_load_report_reads_meta_and_player_input(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    replay = load_report(path)
    assert replay.meta["turn_seq"] == 5
    assert replay.player_input == "Открываю дверь"


def test_load_report_now_iso_is_turn_time_not_report_time(registry, tmp_path):
    path, capture = written(registry, tmp_path)
    assert load_report(path).now_iso == capture.now_iso
    assert load_report(path).now_iso != NOW.isoformat()


def test_load_report_before_equals_captured_before(registry, tmp_path):
    path, capture = written(registry, tmp_path)
    replay = load_report(path)
    assert replay.before.world.rng == capture.before.world.rng
    hero = replay.before.heroes[0].creature
    assert hero.hp_current == capture.before.heroes[0].creature.hp_current


def test_load_report_expected_is_after_for_committed(registry, tmp_path):
    path, capture = written(registry, tmp_path)
    replay = load_report(path)
    assert replay.expected is not None
    assert replay.expected.world.rng == capture.after.world.rng


def test_load_report_expected_is_none_for_aborted(registry, tmp_path):
    path, _ = written(registry, tmp_path, status="aborted", failure_reason="refusal")
    replay = load_report(path)
    assert replay.expected is None
    assert replay.failure_reason == "refusal"


def test_load_report_records_are_calls_jsonl(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    records = load_report(path).records
    assert [r["call_id"] for r in records] == ["run-1-1"]
    assert records[0]["response"]["stop_reason"] == "end_turn"


def test_load_report_does_not_touch_report_dir(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    before = tree(path)
    load_report(path)
    assert tree(path) == before


def test_load_report_works_on_read_only_copy_of_the_report(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    copy = tmp_path / "moved" / path.name
    shutil.copytree(path, copy)
    shutil.rmtree(path)
    assert load_report(copy).player_input == "Открываю дверь"


def test_load_report_before_loads_via_load_slot_equal(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    root = tmp_path / "manual"
    shutil.copytree(path / "before", root)
    loaded = load_slot(root, "w1", "auto")
    assert load_report(path).before.world.rng == loaded.world.rng


def test_load_report_missing_dir_raises(tmp_path):
    with pytest.raises(OSError):
        load_report(tmp_path / "nope")


# контекст миграций и временные папки

def test_context_for_gets_campaign_id_of_the_snapshot_and_context_goes_to_load_slot(
    registry, tmp_path, monkeypatch
):
    import ai_dm.reports.replay as replay_module

    path, _ = written(registry, tmp_path, campaign_id="camp-x")
    seen = {}
    real = replay_module.load_slot

    def spy(folder, world_id, slot, context=None):
        seen.setdefault("contexts", []).append(context)
        return real(folder, world_id, slot, context=context)

    monkeypatch.setattr(replay_module, "load_slot", spy)
    asked = []

    def context_for(campaign_id):
        asked.append(campaign_id)
        return None

    load_report(path, context_for)
    assert asked == ["camp-x", "camp-x"]
    assert seen["contexts"] == [None, None]


def test_context_for_result_is_passed_to_load_slot(registry, tmp_path, monkeypatch):
    import ai_dm.reports.replay as replay_module

    path, _ = written(registry, tmp_path)
    given = []
    real = replay_module.load_slot
    marker = object()

    def spy(folder, world_id, slot, context=None):
        given.append(context)
        return real(folder, world_id, slot)

    monkeypatch.setattr(replay_module, "load_slot", spy)
    load_report(path, lambda campaign_id: marker)
    assert given == [marker, marker]


def test_without_context_for_load_slot_gets_no_context(registry, tmp_path, monkeypatch):
    import ai_dm.reports.replay as replay_module

    path, _ = written(registry, tmp_path)
    given = []
    real = replay_module.load_slot

    def spy(folder, world_id, slot, context=None):
        given.append(context)
        return real(folder, world_id, slot)

    monkeypatch.setattr(replay_module, "load_slot", spy)
    load_report(path)
    assert given == [None, None]


def test_aborted_status_ignores_after_dir_even_if_present(registry, tmp_path):
    path, _ = written(registry, tmp_path, status="aborted", failure_reason="refusal")
    shutil.copytree(path / "before", path / "after")
    assert load_report(path).expected is None


def test_committed_without_after_dir_has_no_expected(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    shutil.rmtree(path / "after")
    assert load_report(path).expected is None


def test_report_without_journal_dir_has_empty_records(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    shutil.rmtree(path / "journal")
    assert load_report(path).records == []


def test_blank_lines_in_calls_jsonl_are_skipped(registry, tmp_path):
    path, _ = written(registry, tmp_path)
    calls = path / "journal" / "calls.jsonl"
    calls.write_text("\n" + calls.read_text(encoding="utf-8") + "\n\n", encoding="utf-8")
    assert len(load_report(path).records) == 1


def test_temp_folders_are_removed(registry, tmp_path, monkeypatch):
    import tempfile

    path, _ = written(registry, tmp_path)
    made = []
    real = tempfile.mkdtemp

    def spy(*args, **kwargs):
        folder = real(*args, **kwargs)
        made.append(folder)
        return folder

    monkeypatch.setattr(tempfile, "mkdtemp", spy)
    load_report(path)
    assert len(made) == 2
    assert not any(shutil.os.path.exists(folder) for folder in made)


def test_temp_folder_is_removed_when_load_fails(registry, tmp_path, monkeypatch):
    import tempfile

    path, _ = written(registry, tmp_path)
    shutil.rmtree(path / "before" / "w1" / "slots" / "auto" / "world")
    made = []
    real = tempfile.mkdtemp

    def spy(*args, **kwargs):
        folder = real(*args, **kwargs)
        made.append(folder)
        return folder

    monkeypatch.setattr(tempfile, "mkdtemp", spy)
    with pytest.raises(OSError):
        load_report(path)
    assert made
    assert not any(shutil.os.path.exists(folder) for folder in made)
