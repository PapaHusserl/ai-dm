# Т60 «Сеть» (docs/plan-t60.md п.1.4, 1.6, 1.8, раздел 10):
#   MasterSession(..., policy=None): None -> app_cfg.retry; свой policy -- свои паузы/число попыток;
#   SummarizerSession(..., policy=None) пробрасывает policy в run_scene / run_chapter;
#   сеть у summarizer -- мягкий сбой (к запасному); journal.note_start на каждую попытку.
from datetime import timedelta

import pytest
from master_kit import (
    NOW,
    app_cfg,
    make_ctx,
    make_session,
    scripted,
    text_step,
)
from test_master_summarizer_chain import (
    chapter_bundle,
    chapter_steps,
    scene_steps,
)

from ai_dm.llm.cost import CostLedger
from ai_dm.llm.journal import Journal
from ai_dm.master.session import MasterSession, TurnFailed
from ai_dm.master.summarizer import SummarizerSession
from ai_dm.protocol.apply import apply

TRANSIENT = {"error": "transient", "message": "сеть недоступна"}
OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"


def empty_policy(app):
    return app.retry.model_copy(update={"delays": []})


def run(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, _, sleeps = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg)
    return adapter, session, journal, sleeps, ctx


# MasterSession.policy

def test_policy_defaults_to_app_retry():
    app = app_cfg()
    session = MasterSession(scripted([]), app)
    assert session.policy is app.retry


def test_explicit_policy_is_kept():
    app = app_cfg()
    policy = empty_policy(app)
    assert MasterSession(scripted([]), app, policy=policy).policy is policy


def test_empty_delays_policy_gives_single_attempt_and_network_failure(tmp_path, registry, cfg):
    app = app_cfg()
    steps = [TRANSIENT, text_step("не должен быть вызван")]
    adapter, session, _, sleeps, ctx = run(
        steps, tmp_path, registry, cfg, app=app, policy=empty_policy(app)
    )
    with pytest.raises(TurnFailed) as info:
        session.run(ctx, "Иду.", apply, "explore")
    assert info.value.reason == "network"
    assert len(adapter.requests) == 1
    assert sleeps == []


def test_default_policy_still_waits_one_three_ten(tmp_path, registry, cfg):
    steps = [TRANSIENT] * 4
    adapter, session, _, sleeps, ctx = run(steps, tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert sleeps == [1, 3, 10]
    assert len(adapter.requests) == 4


def test_custom_delays_policy_is_used(tmp_path, registry, cfg):
    app = app_cfg()
    policy = app.retry.model_copy(update={"delays": [2]})
    adapter, session, _, sleeps, ctx = run(
        [TRANSIENT, TRANSIENT, text_step()], tmp_path, registry, cfg, app=app, policy=policy
    )
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert sleeps == [2]
    assert len(adapter.requests) == 2


# attempts.log через MasterSession

def attempt_rows(journal):
    text = (journal.dir / "attempts.log").read_text(encoding="utf-8")
    return [line.split("\t") for line in text.splitlines()]


def test_session_notes_start_of_every_attempt(tmp_path, registry, cfg):
    steps = [TRANSIENT, TRANSIENT, text_step()]
    _, session, journal, _, ctx = run(steps, tmp_path, registry, cfg, run_id="run-9")
    ctx.bundle.session.turn_seq = 4
    session.run(ctx, "Иду.", apply, "explore")
    rows = attempt_rows(journal)
    assert [r[5] for r in rows] == ["1", "2", "3"]
    assert {(r[0], r[1], r[2], r[3]) for r in rows} == {(NOW.isoformat(), "run-9", "4", "narrator")}
    assert {r[4] for r in rows} == {session.adapter.info().model}


def test_session_notes_one_start_per_call_of_the_turn(tmp_path, registry, cfg):
    from master_kit import flag_call, tools_step

    steps = [tools_step(flag_call("a", "c1")), text_step()]
    _, session, journal, _, ctx = run(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    assert [r[5] for r in attempt_rows(journal)] == ["1", "1"]


def test_every_started_attempt_has_a_pair_in_calls(tmp_path, registry, cfg):
    steps = [TRANSIENT, text_step()]
    _, session, journal, _, ctx = run(steps, tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    assert len(attempt_rows(journal)) == len(journal.read_records()) == 2


# 207: duration_s = конец попытки (on_attempt) - начало (on_start), одни и те же часы self.now

def ticking_session(offsets, steps, tmp_path):
    # часы отдают метки NOW + offsets[i] по одной на каждый вызов now(): старт, конец, старт, ...
    clock = iter([NOW + timedelta(seconds=s) for s in offsets]).__next__
    app = app_cfg()
    journal = Journal(tmp_path, "w1", app.journal)
    session = MasterSession(
        scripted(steps), app, journal=journal, ledger=CostLedger(tmp_path, "w1"),
        run_id="run-1", sleeper=lambda s: None, now=clock,
    )
    return session, journal


def test_call_writes_duration_between_start_and_end_of_attempt(tmp_path, registry, cfg):
    session, journal = ticking_session([0, 3], [text_step()], tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert journal.read_records()[0]["duration_s"] == 3.0


def test_call_uses_the_same_start_mark_for_attempts_log_and_duration(tmp_path, registry, cfg):
    session, journal = ticking_session([0, 3], [text_step()], tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert attempt_rows(journal)[0][0] == NOW.isoformat()
    assert journal.read_records()[0]["ts"] == (NOW + timedelta(seconds=3)).isoformat()


def test_each_retry_attempt_gets_its_own_duration(tmp_path, registry, cfg):
    session, journal = ticking_session([0, 1, 2, 5], [TRANSIENT, text_step()], tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert [r["duration_s"] for r in journal.read_records()] == [1.0, 3.0]


def test_failed_attempt_has_duration_and_no_tokens_per_s(tmp_path, registry, cfg):
    session, journal = ticking_session([0, 1, 2, 5], [TRANSIENT, text_step()], tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    first = journal.read_records()[0]
    assert (first["error"]["kind"], first["tokens_per_s"]) == ("transient", None)


def test_attempts_log_rows_keep_their_marks_with_ticking_clock(tmp_path, registry, cfg):
    session, journal = ticking_session([0, 1, 2, 5], [TRANSIENT, text_step()], tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    marks = [r[0] for r in attempt_rows(journal)]
    assert marks == [NOW.isoformat(), (NOW + timedelta(seconds=2)).isoformat()]


def test_constant_clock_gives_zero_duration_and_no_tokens_per_s(tmp_path, registry, cfg):
    _, session, journal, _, ctx = run([text_step()], tmp_path, registry, cfg)
    session.run(ctx, "Иду.", apply, "explore")
    rec = journal.read_records()[0]
    assert (rec["duration_s"], rec["tokens_per_s"]) == (0.0, None)


def test_session_without_journal_notes_nothing(tmp_path, registry, cfg):
    adapter = scripted([TRANSIENT, text_step()])
    session = MasterSession(adapter, app_cfg(), sleeper=lambda s: None, now=lambda: NOW)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert list(tmp_path.iterdir()) == []


def test_summarizer_role_is_written_to_attempts(tmp_path, registry, cfg):
    from master_kit import make_bundle

    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.journal import Journal

    app = app_cfg()
    journal = Journal(tmp_path, "w1", app.journal)
    session = SummarizerSession(
        scripted(scene_steps()), app, journal=journal, ledger=CostLedger(tmp_path, "w1"),
        sleeper=lambda s: None, now=lambda: NOW, model=OPUS,
    )
    session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    rows = attempt_rows(journal)
    assert [(r[1], r[3], r[4]) for r in rows] == [("bnd-1", "summarizer", OPUS)]


# SummarizerSession.policy

def summarizer(steps, app, policy=None, backup=None):
    sleeps = []
    session = SummarizerSession(
        scripted(steps), app, sleeper=sleeps.append, model=OPUS, backup=backup, policy=policy,
    )
    return session, sleeps


def test_summarizer_policy_defaults_to_none():
    assert SummarizerSession(None, None).policy is None


def test_run_scene_without_policy_uses_full_delays(registry, cfg):
    session, sleeps = summarizer([TRANSIENT] * 4, app_cfg())
    from master_kit import make_bundle

    with pytest.raises(TurnFailed) as info:
        session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert info.value.reason == "network"
    assert sleeps == [1, 3, 10]


def test_run_scene_with_empty_policy_makes_one_attempt(registry, cfg):
    from master_kit import make_bundle

    app = app_cfg()
    session, sleeps = summarizer([TRANSIENT] * 4, app, policy=empty_policy(app))
    with pytest.raises(TurnFailed) as info:
        session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert info.value.reason == "network"
    assert sleeps == []
    assert len(session.adapter.requests) == 1


def test_run_chapter_without_policy_uses_full_delays(registry, cfg):
    session, sleeps = summarizer([TRANSIENT] * 4, app_cfg())
    with pytest.raises(TurnFailed):
        session.run_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert sleeps == [1, 3, 10]


def test_run_chapter_with_empty_policy_makes_one_attempt(registry, cfg):
    app = app_cfg()
    session, sleeps = summarizer([TRANSIENT] * 4, app, policy=empty_policy(app))
    with pytest.raises(TurnFailed) as info:
        session.run_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert info.value.reason == "network"
    assert sleeps == []
    assert len(session.adapter.requests) == 1


def test_fast_primary_goes_to_backup_with_full_delays(registry, cfg):
    from master_kit import make_bundle

    app = app_cfg()
    backup, backup_sleeps = summarizer([TRANSIENT] * 4, app)
    primary, primary_sleeps = summarizer(
        [TRANSIENT] * 4, app, policy=empty_policy(app), backup=backup
    )
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)
    assert primary_sleeps == []
    assert len(primary.adapter.requests) == 1
    assert backup_sleeps == [1, 3, 10]
    assert len(backup.adapter.requests) == 4


def test_chapter_network_of_primary_goes_to_backup(registry, cfg):
    app = app_cfg()
    backup, _ = summarizer(chapter_steps("Г2.", "И2."), app)
    primary, _ = summarizer([TRANSIENT] * 4, app, policy=empty_policy(app), backup=backup)
    ctx, fell = primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.chapter_text, ctx.game_text, fell) == ("Г2.", "И2.", True)
