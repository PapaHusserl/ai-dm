# Ожидаемый API: полный репорт (этап 6а, P1) через GameApp.handle: в каталоге репорта
# before/ (снимок до хода, грузится load_slot), after/ (только у принятого хода),
# journal/calls.jsonl (записи журнала с run_id хода, с итоговым turn_status) и journal/blobs/
# (копии блобов system/tools), в report.md -- последние recent_turns ходов (ReportsConfig,
# по умолчанию 5) и вызовы хода. Журнал выключен -- нет journal/, meta.replayable=false.
import json
import shutil

import pytest
from game_kit import ReactiveAdapter, core_dump, make_app, scripted, settings, text_step
from world_kit import (
    GRAIL,
    bundle_without_candidates,
    end_turn,
    narrator_turns,
    npc_update_call,
    world_step,
)

from ai_dm.persistence.store import load_slot


def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    if not folder.exists():
        return []
    return sorted(folder.iterdir())


def meta_of(path):
    return json.loads((path / "meta.json").read_text(encoding="utf-8"))


def report_md(path):
    return (path / "report.md").read_text(encoding="utf-8")


def recent_section(path):
    # только «Последние ходы»: в сырых запросах вызова те же фразы встречаются сами по себе
    text = report_md(path)
    start = text.index("## Последние ходы")
    end = text.find("\n## ", start + 1)
    return text[start:] if end == -1 else text[start:end]


def calls_of(path):
    text = (path / "journal" / "calls.jsonl").read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def load_snapshot(path, name, tmp_path):
    # <отчёт>/<name> -- корень сейвов со слотом auto; копируем, чтобы load_slot не трогал репорт
    root = tmp_path / "snap-root" / name
    if root.exists():
        shutil.rmtree(root)
    shutil.copytree(path / name, root)
    return load_slot(root, "w1", "auto")


def phrase(n):
    return f"фраза-{n}-x"


def play(registry, tmp_path, turns, **kw):
    steps = [text_step(f"Рассказ-{n}-y.") for n in range(1, turns + 1)]
    app = make_app(registry, tmp_path, scripted(steps), **kw)
    for n in range(1, turns + 1):
        app.handle(phrase(n))
    return app


# before/ и after/

def test_report_has_before_and_after_dirs(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    assert (path / "before").is_dir()
    assert (path / "after").is_dir()


def test_before_snapshot_loads_and_equals_state_before_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    state_before = core_dump(app.bundle)
    app.handle("Иду")
    app.handle("/report баг")
    loaded = load_snapshot(issues(tmp_path)[0], "before", tmp_path)
    assert core_dump(loaded) == state_before


def test_after_snapshot_loads_and_equals_state_after_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    state_after = core_dump(app.bundle)
    app.handle("/report баг")
    loaded = load_snapshot(issues(tmp_path)[0], "after", tmp_path)
    assert core_dump(loaded) == state_after


def test_before_differs_from_after_for_committed_turn(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    app.handle("Иду")
    app.handle("/report баг")
    before = load_snapshot(issues(tmp_path)[0], "before", tmp_path)
    after = load_snapshot(issues(tmp_path)[0], "after", tmp_path)
    assert core_dump(before) != core_dump(after)


def test_aborted_turn_has_before_but_no_after(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]), auto_reports=True)
    app.handle("Иду")
    path = issues(tmp_path)[0]
    assert (path / "before").is_dir()
    assert not (path / "after").exists()


def test_aborted_turn_before_equals_state_after_rollback(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]), auto_reports=True)
    app.handle("Иду")
    loaded = load_snapshot(issues(tmp_path)[0], "before", tmp_path)
    assert core_dump(loaded) == core_dump(app.bundle)


def test_manual_report_after_abort_has_before_equal_to_live_state(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]))
    app.handle("Иду")
    app.handle("/report не отвечает")
    path = issues(tmp_path)[0]
    assert not (path / "after").exists()
    assert core_dump(load_snapshot(path, "before", tmp_path)) == core_dump(app.bundle)


def test_snapshot_is_taken_at_report_time_not_live(registry, tmp_path):
    # замечание ревью P0: before откатанного хода был живым бандлом; поздние мутации не в репорт
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]), auto_reports=True)
    app.handle("Иду")
    snapshot = core_dump(app.bundle)
    app.bundle.world.rng.draws += 100
    path = issues(tmp_path)[0]
    assert core_dump(load_snapshot(path, "before", tmp_path)) == snapshot


# journal/calls.jsonl

def test_calls_jsonl_has_exactly_turn_calls(registry, tmp_path):
    app = play(registry, tmp_path, 3)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    run_ids = meta_of(path)["run_ids"]
    records = calls_of(path)
    assert len(records) == 1
    assert {r["run_id"] for r in records} == set(run_ids)


def test_calls_jsonl_has_no_neighbour_turn_calls(registry, tmp_path):
    app = play(registry, tmp_path, 3)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    all_run_ids = {r["run_id"] for r in app.journal.read_records()}
    assert len(all_run_ids) == 3
    mine = {r["run_id"] for r in calls_of(path)}
    assert mine < all_run_ids


def test_calls_jsonl_has_retry_attempts(registry, tmp_path):
    steps = [{"error": "transient"}, text_step("Наконец-то.")]
    app = make_app(registry, tmp_path, scripted(steps))
    app.handle("Иду")
    app.handle("/report баг")
    records = calls_of(issues(tmp_path)[0])
    assert [r["attempt"] for r in records] == [1, 2]
    assert records[0]["error"]["kind"] == "transient"
    assert records[1]["error"] is None


def test_calls_jsonl_has_final_turn_status_committed(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    assert [r["turn_status"] for r in calls_of(issues(tmp_path)[0])] == ["committed"]


def test_calls_jsonl_has_final_turn_status_aborted(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([{"stop": "refusal"}]), auto_reports=True)
    app.handle("Иду")
    records = calls_of(issues(tmp_path)[0])
    assert records
    assert {r["turn_status"] for r in records} == {"aborted"}


def test_calls_jsonl_has_boundary_world_calls(registry, tmp_path):
    from game_kit import NOW
    from master_kit import flag_call  # noqa: F401

    from ai_dm.game.app import GameApp

    bundle = bundle_without_candidates(registry, settings().rules)
    world_id = bundle.world.world_id
    steps = world_step(
        npc_update_call("aldric", GRAIL, status="dead", cause="goal", evidence_ref="r42")
    )
    narrator = scripted(narrator_turns(end_turn(1, flag="grail_seen")))
    app = GameApp(
        settings(), registry, bundle, narrator, saves_root=tmp_path, sleeper=lambda s: None,
        now=lambda: NOW, run_tag="t", world_adapter=scripted(steps), auto_reports=False,
    )
    app.runner.new_summarizer_session = lambda: None
    app.handle("Иду")
    app.handle("/report баг")
    path = issues(tmp_path, world_id)[0]
    roles = {r["role"] for r in calls_of(path)}
    assert {"narrator", "world"} <= roles
    assert {r["run_id"] for r in calls_of(path)} == set(meta_of(path)["run_ids"])


def test_calls_jsonl_blobs_are_copied(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    for record in calls_of(path):
        for key in ("system_sha256", "tools_sha256"):
            sha = record["request"][key]
            copy = path / "journal" / "blobs" / f"{sha}.json"
            live = app.journal.dir / "blobs" / f"{sha}.json"
            assert copy.is_file()
            assert copy.read_bytes() == live.read_bytes()


def test_blobs_dir_has_only_mentioned_blobs(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    mentioned = set()
    for record in calls_of(path):
        mentioned |= {record["request"]["system_sha256"], record["request"]["tools_sha256"]}
    stems = {p.stem for p in (path / "journal" / "blobs").glob("*.json")}
    assert stems == mentioned


def test_turn_without_model_calls_has_empty_calls_jsonl(registry, tmp_path):
    # /report до первого хода: вызовов хода нет -- файл пустой (или не создан), это норма
    app = make_app(registry, tmp_path, ReactiveAdapter())
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    calls = path / "journal" / "calls.jsonl"
    assert not calls.exists() or calls.read_text(encoding="utf-8").strip() == ""


# ротация журнала

def test_report_stays_full_after_journal_rotation(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Раз."), text_step("Два.")]))
    app.handle(phrase(1))
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    first_run = meta_of(path)["run_ids"][0]
    files_before = {
        p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }
    app.journal.cfg.segment_mb = 0
    app.journal.cfg.max_mb = 0
    app.handle(phrase(2))
    assert first_run not in {r["run_id"] for r in app.journal.read_records()}
    files_after = {
        p.relative_to(path): p.read_bytes() for p in path.rglob("*") if p.is_file()
    }
    assert files_after == files_before
    assert {r["run_id"] for r in calls_of(path)} == {first_run}
    for record in calls_of(path):
        sha = record["request"]["system_sha256"]
        assert (path / "journal" / "blobs" / f"{sha}.json").is_file()


# последние N ходов в report.md

def test_report_has_last_five_turns_by_default(registry, tmp_path):
    app = play(registry, tmp_path, 7)
    app.handle("/report баг")
    report = recent_section(issues(tmp_path)[0])
    for n in (3, 4, 5, 6, 7):
        assert phrase(n) in report
    assert phrase(1) not in report


def test_report_has_both_phrase_and_story_of_previous_turn(registry, tmp_path):
    app = play(registry, tmp_path, 3)
    app.handle("/report баг")
    report = recent_section(issues(tmp_path)[0])
    assert phrase(2) in report
    assert "Рассказ-2-y." in report


def test_report_has_all_turns_when_fewer_than_n(registry, tmp_path):
    app = play(registry, tmp_path, 2)
    app.handle("/report баг")
    report = recent_section(issues(tmp_path)[0])
    assert phrase(1) in report
    assert phrase(2) in report


def test_report_n_follows_config(registry, tmp_path):
    app = play(registry, tmp_path, 7)
    app.settings.app.reports.recent_turns = 2
    app.handle("/report баг")
    report = recent_section(issues(tmp_path)[0])
    assert phrase(7) in report
    assert phrase(6) in report
    assert phrase(3) not in report
    assert phrase(1) not in report


def test_reports_config_default_is_five():
    assert settings().app.reports.recent_turns == 5


def test_report_has_only_kept_turns_and_note_when_keep_is_less_than_n(registry, tmp_path):
    steps = [text_step(f"Рассказ-{n}-y.") for n in range(1, 5)]
    app = make_app(registry, tmp_path, scripted(steps))
    app.settings.app.master.recent_turns_keep = 2
    for n in range(1, 5):
        app.handle(phrase(n))
    app.handle("/report баг")
    report = recent_section(issues(tmp_path)[0])
    assert phrase(4) in report
    assert phrase(3) in report
    assert phrase(2) not in report
    assert "меньше ходов, чем запрошено" in report


def test_report_has_no_note_when_enough_turns(registry, tmp_path):
    app = play(registry, tmp_path, 5)
    app.handle("/report баг")
    assert "меньше ходов, чем запрошено" not in report_md(issues(tmp_path)[0])


# вызовы хода в report.md

def test_report_md_has_call_role_model_and_stop_reason(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    report = report_md(issues(tmp_path)[0])
    record = calls_of(issues(tmp_path)[0])[0]
    assert record["role"] in report
    assert record["model"] in report
    assert record["stop_reason"] in report


def test_report_md_has_raw_response_text(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    assert "Рассказ-1-y." in report_md(issues(tmp_path)[0])


def test_report_md_references_system_blob_not_inline(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    record = calls_of(path)[0]
    report = report_md(path)
    assert record["request"]["system_sha256"] in report
    system_text = (path / "journal" / "blobs" / f"{record['request']['system_sha256']}.json")
    first_block = json.loads(system_text.read_text(encoding="utf-8"))[0]["text"]
    assert first_block not in report


def test_report_md_has_requested_model_of_call(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    assert calls_of(path)[0]["requested_model"] in report_md(path)


# /load

def test_report_after_load_has_snapshot_of_loaded_state_and_no_turn(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/save a")
    app.handle("/load a")
    app.handle("/report после загрузки")
    path = issues(tmp_path)[0]
    assert (path / "before").is_dir()
    assert not (path / "after").exists()
    assert core_dump(load_snapshot(path, "before", tmp_path)) == core_dump(app.bundle)
    assert "ходов в сессии ещё не было" in report_md(path)
    assert "Номер хода" not in report_md(path)
    assert meta_of(path)["run_ids"] == []


def test_report_after_load_has_no_calls_of_old_session(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/save a")
    app.handle("/load a")
    app.handle("/report после загрузки")
    path = issues(tmp_path)[0]
    calls = path / "journal" / "calls.jsonl"
    assert not calls.exists() or calls.read_text(encoding="utf-8").strip() == ""


# журнал выключен

def journal_off(app):
    app.journal = None
    app.runner.journal = None


def test_report_without_journal_is_written_with_replayable_false(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    journal_off(app)
    app.handle("Иду")
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    assert (path / "report.md").is_file()
    assert meta_of(path)["replayable"] is False


def test_report_without_journal_has_no_journal_dir_and_says_so(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([text_step("Рассказ.")]))
    journal_off(app)
    app.handle("Иду")
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    assert not (path / "journal").exists()
    assert "журнал отключён, воспроизведение невозможно" in report_md(path).lower()


def test_report_with_journal_is_replayable(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    path = issues(tmp_path)[0]
    assert meta_of(path)["replayable"] is True
    assert "журнал отключён" not in report_md(path).lower()


# ключи API

@pytest.mark.parametrize("manual", [False, True])
def test_full_report_files_have_no_api_keys(registry, tmp_path, monkeypatch, manual):
    anthropic = "sk-ant-MARKER-anthropic-9f3a1c"
    gemini = "AIza-MARKER-gemini-7d2b5e"
    monkeypatch.setenv("ANTHROPIC_API_KEY", anthropic)
    monkeypatch.setenv("GEMINI_API_KEY", gemini)
    steps = [{"stop": "refusal"}] if not manual else [text_step("Рассказ.")]
    app = make_app(registry, tmp_path, scripted(steps), auto_reports=True)
    app.handle("Иду")
    if manual:
        app.handle("/report баг")
    assert issues(tmp_path)
    for path in issues(tmp_path):
        files = [f for f in path.rglob("*") if f.is_file()]
        assert any(f.parent.name == "journal" for f in files)
        for file in files:
            data = file.read_bytes()
            assert anthropic.encode() not in data
            assert gemini.encode() not in data


# формат файлов

def test_meta_has_turn_seq_and_call_count(registry, tmp_path):
    app = play(registry, tmp_path, 2)
    app.handle("/report баг")
    meta = meta_of(issues(tmp_path)[0])
    assert meta["turn_seq"] == 2
    assert meta["calls"] == 1


def test_calls_jsonl_and_meta_keep_cyrillic_unescaped(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report ошибка-кириллицей")
    path = issues(tmp_path)[0]
    assert "Рассказ-1-y." in (path / "journal" / "calls.jsonl").read_text(encoding="utf-8")
    assert "фраза-1-x" in (path / "meta.json").read_text(encoding="utf-8")


def test_meta_json_is_indented_by_two(registry, tmp_path):
    app = play(registry, tmp_path, 1)
    app.handle("/report баг")
    assert '\n  "report_format"' in (issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8")
