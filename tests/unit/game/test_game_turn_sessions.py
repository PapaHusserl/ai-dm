# Р2: сборка сессий TurnRunner (рассказчик с припиской, summarizer с запасным) и разбор сбоев
# попытки хода: что передаётся сессиям и как оформляется причина.
import pytest
from game_kit import make_rig, run_records, scripted, text_step
from summarizer_kit import make_summ_rig, summ_steps

from ai_dm.game.turn import SOFTEN_NOTE


def summarizer_rig(registry, cfg, tmp_path):
    return make_summ_rig(registry, cfg, tmp_path, [text_step()], summ_steps())


# new_session

def test_new_session_gets_runner_wiring(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    runner = rig.runner
    session = runner.new_session("run-77")
    assert session.run_id == "run-77"
    assert session.adapter is runner.adapter
    assert session.app_cfg is runner.app_cfg
    assert session.journal is runner.journal
    assert session.ledger is runner.ledger
    assert session.sleeper == runner.sleeper
    assert session.now == runner.now
    assert session.builder is runner.builder
    assert session.note is None


def test_new_session_carries_current_note(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    rig.runner.note = SOFTEN_NOTE
    assert rig.runner.new_session("run-1").note == SOFTEN_NOTE


# new_summarizer_session

def wiring(session, runner):
    assert session.app_cfg is runner.app_cfg
    assert session.journal is runner.journal
    assert session.ledger is runner.ledger
    assert session.sleeper == runner.sleeper
    assert session.now == runner.now
    assert session.call_numbers is runner.call_numbers


def test_summarizer_session_gets_runner_wiring(registry, cfg, tmp_path):
    rig = summarizer_rig(registry, cfg, tmp_path)
    session = rig.runner.new_summarizer_session()
    wiring(session, rig.runner)
    assert session.adapter is rig.runner.summarizer_adapter


def test_backup_session_gets_runner_wiring(registry, cfg, tmp_path):
    rig = summarizer_rig(registry, cfg, tmp_path)
    backup = rig.runner.new_summarizer_session().backup
    wiring(backup, rig.runner)


# разбор сбоев попытки

def test_round_limit_becomes_turn_failed_with_message(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.combat.engine import CombatRoundLimit

    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))

    def boom(*args):
        raise CombatRoundLimit("слишком долго")

    monkeypatch.setattr(rig.runner, "explore_turn", boom)
    result = rig.runner.play("Иду")
    assert result.committed is False
    assert result.failure.reason == "round_limit"
    assert "слишком долго" in str(result.failure)
    assert result.hint == str(result.failure)
    assert "tone" not in result.hint


@pytest.mark.parametrize("reason_steps", [[{"error": "fatal", "message": "ключ отозван"}]])
def test_non_refusal_hint_is_the_failure_text(registry, cfg, tmp_path, reason_steps):
    rig = make_rig(registry, cfg, tmp_path, scripted(reason_steps))
    result = rig.runner.play("Иду")
    assert result.hint == str(result.failure)
    assert "ключ отозван" in result.hint


def test_unexpected_exception_marks_this_run_aborted(registry, cfg, tmp_path, monkeypatch):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    original = rig.runner.explore_turn

    def late_boom(*args):
        original(*args)
        raise RuntimeError("после вызова модели")

    monkeypatch.setattr(rig.runner, "explore_turn", late_boom)
    with pytest.raises(RuntimeError):
        rig.runner.play("Иду")
    records = rig.journal.read_records()
    assert len(records) == 1
    assert run_records(rig.journal, records[0]["run_id"])[0]["turn_status"] == "aborted"


# нумерация ходов и отложенная строка

def test_run_ids_are_numbered_one_by_one(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    first = rig.runner.play("a")
    second = rig.runner.play("b")
    assert first.run_id.endswith("-t-1")
    assert second.run_id.endswith("-t-2")


def test_line_is_deferred_while_boundary_stays_broken(registry, cfg, tmp_path):
    from game_kit import end_scene_call, tools_step
    from summarizer_kit import summ_fail_steps

    narrator = [tools_step(end_scene_call(summary="П.")), text_step("Конец.")]
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, summ_fail_steps() * 2)
    rig.runner.play("ход")
    result = rig.runner.play("следующая строка")
    assert result.committed is False
    assert rig.runner.deferred_input == "следующая строка"
    assert rig.runner.bundle.session.turn_seq == 1


def test_call_numbers_of_turn_are_dropped_when_journal_is_marked(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    result = rig.runner.play("Иду")
    assert result.run_id not in rig.runner.call_numbers


def test_call_numbers_are_dropped_after_aborted_retry(registry, cfg, tmp_path):
    refusal = {"stop": "refusal"}
    rig = make_rig(registry, cfg, tmp_path, scripted([refusal, refusal]))
    result = rig.runner.play("Иду")
    assert result.run_id not in rig.runner.call_numbers
