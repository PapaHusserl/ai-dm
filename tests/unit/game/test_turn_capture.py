# Ожидаемый API: TurnRunner.last_capture / TurnResult.run_ids / TurnResult.before (этап 6а, P0).
# Снимок хода для репорта: run_ids (основной run_id + bnd-* границы хода), before (бандл до хода),
# статус committed / aborted, метки без дублей; снимок до хода при недостроенной границе -- копия.
from game_kit import NOW, core_dump, make_rig, scripted, text_step, tools_step
from master_kit import flag_call
from world_kit import (
    BRANN,
    OATH,
    bundle_with_brann,
    end_turn,
    make_world_rig,
    narrator_turns,
    verdict_call,
    world_step,
)


def unsupported_call(call_id="us-1"):
    return {
        "id": call_id, "name": "unsupported_action",
        "input": {"type": "unsupported_action", "description": "верхом на медведе"},
    }


def test_no_capture_before_first_turn(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    assert rig.runner.last_capture is None


def test_result_run_ids_has_main_run_id(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    result = rig.runner.play("Иду")
    assert result.run_ids == [result.run_id]


def test_result_before_is_bundle_before_the_turn(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    before = rig.runner.bundle.model_dump_json()
    result = rig.runner.play("Иду")
    assert result.before.model_dump_json() == before
    assert result.before.session.turn_seq == 0
    assert rig.runner.bundle.session.turn_seq == 1


def test_committed_capture_fields(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    result = rig.runner.play("Иду")
    capture = rig.runner.last_capture
    assert capture.turn_seq == 1
    assert capture.run_ids == [result.run_id]
    assert capture.player_input == "Иду"
    assert capture.tags == []
    assert capture.status == "committed"
    assert capture.failure_reason is None
    assert capture.before is result.before
    assert core_dump(capture.after) == core_dump(rig.runner.bundle)
    assert capture.after is not rig.runner.bundle
    assert capture.model == rig.runner.model


def test_capture_now_iso_is_from_runner_clock(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    rig.runner.play("Иду")
    assert rig.runner.last_capture.now_iso == NOW.isoformat()


def test_capture_turn_seq_follows_turns(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    rig.runner.play("раз")
    rig.runner.play("два")
    assert rig.runner.last_capture.turn_seq == 2
    assert rig.runner.last_capture.player_input == "два"


def test_aborted_capture_has_no_after_and_failure_reason(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), {"stop": "refusal"}]))
    rig.runner.play("раз")
    result = rig.runner.play("два")
    capture = rig.runner.last_capture
    assert capture.status == "aborted"
    assert capture.after is None
    assert capture.failure_reason == "refusal"
    assert capture.tags == ["refusal"]
    assert capture.run_ids == [result.run_id]
    # номер хода, который не состоялся: следующий за последним принятым
    assert capture.turn_seq == 2
    assert capture.before.session.turn_seq == 1


def test_aborted_result_keeps_before(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([{"stop": "refusal"}]))
    before = rig.runner.bundle.model_dump_json()
    result = rig.runner.play("Иду")
    assert result.before.model_dump_json() == before
    assert result.run_ids == [result.run_id]


def test_capture_tags_have_no_duplicates(registry, cfg, tmp_path):
    steps = [tools_step(unsupported_call("u1"), unsupported_call("u2")), text_step()]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("Иду")
    assert rig.runner.last_capture.tags == ["missing-mechanic"]


def test_retry_after_failure_makes_new_capture(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([{"stop": "refusal"}, text_step()]))
    failed = rig.runner.play("Иду")
    result = rig.runner.retry()
    capture = rig.runner.last_capture
    assert result.committed is True
    assert capture.status == "committed"
    assert capture.run_ids == [result.run_id]
    assert capture.run_ids != [failed.run_id]
    assert capture.player_input == "Иду"


# граница сцены

def test_boundary_run_id_is_in_turn_run_ids(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    result = rig.play()[0]
    assert result.run_ids[0] == result.run_id
    boundary = [r for r in result.run_ids if r.startswith("bnd-")]
    assert len(boundary) == 1
    assert rig.runner.last_capture.run_ids == result.run_ids


def test_boundary_run_id_is_listed_once(registry, cfg, tmp_path):
    # summarizer и world делят id границы: в списке он один раз
    bundle = bundle_with_brann(registry, cfg)
    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)
    result = rig.play()[0]
    assert len(result.run_ids) == len(set(result.run_ids))


def failed_boundary_rig(registry, cfg, tmp_path):
    bundle = bundle_with_brann(registry, cfg)
    steps = []
    for n in range(3):
        steps.append(tools_step(verdict_call([(BRANN, True)], f"wv-{n}")))
    steps += world_step(verdict_call([(BRANN, False), (OATH, False)], "wv-ok"))
    return make_world_rig(registry, cfg, tmp_path, narrator_turns(end_turn()), steps, bundle=bundle)


def test_boundary_resume_capture_before_is_copy_with_pending(registry, cfg, tmp_path):
    rig = failed_boundary_rig(registry, cfg, tmp_path)
    first = rig.runner.play("Иду")
    assert first.boundary_failed
    assert rig.runner.bundle.session.boundary_pending is True
    result = rig.runner.retry()
    assert result.boundary_failed is False
    # граница достроена на живом бандле, а снимок «до» остался как был
    assert rig.runner.bundle.session.boundary_pending is False
    assert result.before.session.boundary_pending is True
    assert result.before is not rig.runner.bundle


def test_boundary_resume_capture_has_boundary_run_id_and_no_input(registry, cfg, tmp_path):
    rig = failed_boundary_rig(registry, cfg, tmp_path)
    rig.runner.play("Иду")
    result = rig.runner.retry()
    capture = rig.runner.last_capture
    assert capture.player_input is None
    assert capture.status == "committed"
    assert capture.run_ids[0] == result.run_id
    assert any(r.startswith("bnd-") for r in capture.run_ids[1:])


def test_plain_turn_before_is_not_a_copy(registry, cfg, tmp_path):
    # без недостроенной границы снимок -- сама ссылка: ход идёт на копии
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    start = rig.runner.bundle
    result = rig.runner.play("Иду")
    assert result.before is start


def test_empty_capture_is_snapshot_of_current_bundle(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    capture = rig.runner.empty_capture()
    assert capture.status == "none"
    assert capture.run_ids == []
    assert capture.tags == []
    assert capture.player_input is None
    assert capture.before is rig.runner.bundle
    assert capture.after is None
    assert capture.turn_seq == 0
    assert capture.model == rig.runner.model
    assert capture.now_iso == NOW.isoformat()


def test_flag_turn_capture_has_no_tags(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("met_guard")), text_step()]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("Иду")
    assert rig.runner.last_capture.tags == []
