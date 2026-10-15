# 19ф Ф1 (docs/19F-PLAN.md п.1 Ф1) на уровне MasterSession: таймаут/504 -- первый сбой сразу
# TurnFailed("network") без повторов; 503 -- полные delays; retry_timeouts=true возвращает повторы.
import pytest
from master_kit import app_cfg, make_ctx, make_session, scripted, text_step

from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply

TIMEOUT = {"error": "transient", "message": "The read operation timed out", "timeout": True}
UNAVAILABLE = {"error": "transient", "message": "503 UNAVAILABLE"}


def run(steps, tmp_path, registry, cfg, **kw):
    adapter = scripted(steps)
    session, journal, _, sleeps = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg)
    return adapter, session, journal, sleeps, ctx


def test_timeout_fails_turn_after_one_call(tmp_path, registry, cfg):
    adapter, session, _, sleeps, ctx = run(
        [TIMEOUT, text_step("не должен быть вызван")], tmp_path, registry, cfg
    )
    with pytest.raises(TurnFailed) as info:
        session.run(ctx, "Иду.", apply, "explore")
    assert info.value.reason == "network"
    assert len(adapter.requests) == 1
    assert sleeps == []


def test_timeout_failure_text_mentions_timeout(tmp_path, registry, cfg):
    _, session, _, _, ctx = run([TIMEOUT], tmp_path, registry, cfg)
    with pytest.raises(TurnFailed) as info:
        session.run(ctx, "Иду.", apply, "explore")
    assert "таймаут" in str(info.value)


def test_timeout_writes_one_row_in_attempts_log(tmp_path, registry, cfg):
    _, session, journal, _, ctx = run([TIMEOUT, text_step()], tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    text = (journal.dir / "attempts.log").read_text(encoding="utf-8")
    assert len(text.splitlines()) == 1


def test_timeout_is_recorded_in_calls_journal(tmp_path, registry, cfg):
    _, session, journal, _, ctx = run([TIMEOUT, text_step()], tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    records = journal.read_records()
    assert len(records) == 1
    assert records[0]["error"]["timeout"] is True


def test_503_503_then_timeout_stops_on_third_call(tmp_path, registry, cfg):
    steps = [UNAVAILABLE, UNAVAILABLE, TIMEOUT, text_step()]
    adapter, session, _, sleeps, ctx = run(steps, tmp_path, registry, cfg)
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert len(adapter.requests) == 3
    assert sleeps == [1, 3]


def test_four_503_still_use_all_attempts(tmp_path, registry, cfg):
    adapter, session, _, sleeps, ctx = run([UNAVAILABLE] * 4, tmp_path, registry, cfg)
    with pytest.raises(TurnFailed) as info:
        session.run(ctx, "Иду.", apply, "explore")
    assert len(adapter.requests) == 4
    assert sleeps == [1, 3, 10]
    assert "таймаут" not in str(info.value)


def test_retry_timeouts_policy_brings_back_all_attempts(tmp_path, registry, cfg):
    app = app_cfg()
    policy = app.retry.model_copy(update={"retry_timeouts": True})
    adapter, session, _, sleeps, ctx = run(
        [TIMEOUT] * 4, tmp_path, registry, cfg, app=app, policy=policy
    )
    with pytest.raises(TurnFailed):
        session.run(ctx, "Иду.", apply, "explore")
    assert len(adapter.requests) == 4
    assert sleeps == [1, 3, 10]
