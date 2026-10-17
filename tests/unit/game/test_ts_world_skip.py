# ТС #22 (BACKLOG 46, docs/plan-ts.md §1 п.5): мягкий сбой world (refusal, invalid, network) --
# пропуск вызова: тег world_skipped, граница идёт
# дальше без вердиктов; fatal и rounds -- как раньше (граница падает, меню 2.2).
from types import SimpleNamespace

import pytest
from game_kit import text_step
from world_kit import (
    BRANN,
    GRAIL,
    OATH,
    bundle_with_brann,
    bundle_without_candidates,
    candidate_refs,
    end_turn,
    make_world_rig,
    narrator_turns,
    verdict_call,
    world_step,
)

from ai_dm.game.boundary import BoundaryResult, call_world, check_triggers
from ai_dm.master.session import TurnFailed

REFUSAL = [{"stop": "refusal"}]
NETWORK = [{"error": "transient", "message": "сеть"}] * 4
FATAL = [{"error": "fatal", "message": "сбой сети"}]


def trigger_of(bundle, owner_id, trigger_id):
    return next(t for t in bundle.world.npcs[owner_id].opportunity if t.id == trigger_id)


def play_skipped(registry, cfg, tmp_path, world_steps, narrator=None, bundle=None):
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator or narrator_turns(end_turn()), world_steps,
        bundle=bundle or bundle_with_brann(registry, cfg),
    )
    return rig, rig.play()


# весь путь: границу ведёт TurnRunner

@pytest.mark.parametrize("steps", [REFUSAL, NETWORK], ids=["refusal", "network"])
def test_soft_world_failure_finishes_boundary_without_menu(registry, cfg, tmp_path, steps):
    rig, results = play_skipped(registry, cfg, tmp_path, steps)
    result = results[0]
    bundle = rig.runner.bundle
    assert result.boundary_failed is False
    assert result.menu is None
    assert rig.runner.failed_role is None
    assert bundle.session.boundary_pending is False
    assert bundle.session.current_scene.id == "scene_2"
    assert "world_skipped" in result.report_tags


def test_world_refusal_does_not_fire_triggers_and_chronicle_is_empty(registry, cfg, tmp_path):
    rig, _ = play_skipped(registry, cfg, tmp_path, REFUSAL)
    bundle = rig.runner.bundle
    assert trigger_of(bundle, "brann", "brann_trust").fired_count == 0
    assert bundle.world.fired == []
    assert bundle.chronicle.entries == []


def test_world_refusal_keeps_scene_summary_committed(registry, cfg, tmp_path):
    rig, _ = play_skipped(registry, cfg, tmp_path, REFUSAL)
    scenes = rig.runner.bundle.memory.scenes
    assert len(scenes) == 1
    assert scenes[0].id == "scene_1"


def test_world_refusal_spends_one_daily_call(registry, cfg, tmp_path):
    rig, _ = play_skipped(registry, cfg, tmp_path, REFUSAL)
    assert rig.runner.bundle.world.sim.world_calls_today == 1


def test_world_refusal_leaves_no_deferred_input_and_next_turn_goes_at_once(
    registry, cfg, tmp_path
):
    narrator = narrator_turns(end_turn()) + [text_step("Новый ход.")]
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator, REFUSAL, bundle=bundle_with_brann(registry, cfg)
    )
    first = rig.runner.play("первый")
    assert rig.runner.deferred_input is None
    second = rig.runner.play("второй")
    assert first.committed is True
    assert second.committed is True
    assert rig.runner.bundle.memory.recent_turns[-1].player_input == "второй"
    assert rig.runner.bundle.session.boundary_pending is False


def test_world_refusal_gives_player_no_words_about_skip(registry, cfg, tmp_path):
    _, results = play_skipped(registry, cfg, tmp_path, REFUSAL)
    shown = "\n".join(results[0].lines).lower()
    assert "world_skipped" not in shown
    assert "refusal" not in shown
    assert "world" not in shown


def test_verdict_candidates_come_back_on_next_boundary_after_skip(registry, cfg, tmp_path):
    steps = REFUSAL + world_step(verdict_call([(BRANN, False), (OATH, False)], "wv-2"))
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn(1), end_turn(2)), steps,
        bundle=bundle_with_brann(registry, cfg),
    )
    results = rig.play(2)
    firsts = [r for r in rig.world.requests if len(r.messages) == 1]
    assert len(firsts) == 2
    assert BRANN in candidate_refs(firsts[1])
    assert "world_skipped" in results[0].report_tags
    assert "world_skipped" not in results[1].report_tags


def test_next_boundary_after_skip_can_fire_trigger(registry, cfg, tmp_path):
    steps = REFUSAL + world_step(verdict_call([(BRANN, True), (OATH, False)], "wv-2"))
    rig = make_world_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn(1), end_turn(2)), steps,
        bundle=bundle_with_brann(registry, cfg),
    )
    rig.play(2)
    assert trigger_of(rig.runner.bundle, "brann", "brann_trust").fired_count == 1


def test_act_candidate_is_lost_on_skipped_boundary(registry, cfg, tmp_path):
    # Q7а: act-триггер уже сработал на копии, при пропуске world его нарративная отработка теряется
    rig, results = play_skipped(
        registry, cfg, tmp_path, REFUSAL,
        narrator=narrator_turns(end_turn(1, flag="grail_seen")),
        bundle=bundle_without_candidates(registry, cfg),
    )
    first = rig.world.requests[0]
    assert GRAIL in candidate_refs(first)
    assert results[0].boundary_failed is False
    assert rig.runner.bundle.world.npcs["aldric"].location_id == "tavern"
    assert "world_skipped" in results[0].report_tags


def test_skipped_world_call_has_one_boundary_run_id_in_journal(registry, cfg, tmp_path):
    rig, _ = play_skipped(registry, cfg, tmp_path, REFUSAL)
    records = rig.world_records()
    assert records
    assert all(r["run_id"].startswith("bnd-") for r in records)
    assert len({r["run_id"] for r in records}) == 1


# fatal: прежнее поведение (M10)

def test_world_fatal_still_fails_boundary_with_menu(registry, cfg, tmp_path):
    rig, results = play_skipped(registry, cfg, tmp_path, FATAL)
    result = results[0]
    assert result.boundary_failed is True
    assert result.menu == ["retry", "switch_model", "save_and_quit"]
    assert rig.runner.bundle.session.boundary_pending is True
    assert "world_skipped" not in result.report_tags


def test_world_fatal_keeps_triggers_unfired_and_scene_open(registry, cfg, tmp_path):
    rig, _ = play_skipped(registry, cfg, tmp_path, FATAL)
    bundle = rig.runner.bundle
    assert trigger_of(bundle, "brann", "brann_trust").fired_count == 0
    assert bundle.session.current_scene.id == "scene_1"
    assert bundle.memory.scenes == []


# call_world напрямую: разбор причин

def world_raising(error):
    calls = []

    def run(work, registry, cfg, candidates, run_id):
        calls.append(candidates)
        raise error

    return calls, SimpleNamespace(run=run, max_calls_per_day=0)


def call(registry, cfg, world):
    bundle = bundle_with_brann(registry, cfg)
    check = check_triggers(bundle, cfg, registry)
    result = BoundaryResult(bundle)
    call_world(bundle, cfg, registry, check, world, "bnd-7", result)
    return bundle, result


@pytest.mark.parametrize("reason", ["refusal", "invalid", "network"])
def test_call_world_soft_reason_is_skipped_with_tag(registry, cfg, reason):
    calls, world = world_raising(TurnFailed(reason, "текст сбоя"))
    bundle, result = call(registry, cfg, world)
    assert len(calls) == 1
    assert result.report_tags == ["world_skipped"]
    assert result.world_run_id == "bnd-7"
    assert bundle.chronicle.entries == []


@pytest.mark.parametrize("reason", ["fatal", "rounds"])
def test_call_world_hard_reason_is_raised(registry, cfg, reason):
    _, world = world_raising(TurnFailed(reason, "текст сбоя"))
    with pytest.raises(TurnFailed) as error:
        call(registry, cfg, world)
    assert error.value.reason == reason


def test_call_world_foreign_exception_is_raised(registry, cfg):
    _, world = world_raising(ValueError("баг"))
    with pytest.raises(ValueError):
        call(registry, cfg, world)


def test_call_world_skip_keeps_incremented_daily_counter(registry, cfg):
    _, world = world_raising(TurnFailed("refusal", "x"))
    bundle, _ = call(registry, cfg, world)
    assert bundle.world.sim.world_calls_today == 1


def test_call_world_skip_does_not_apply_verdicts(registry, cfg):
    _, world = world_raising(TurnFailed("invalid", "x"))
    bundle, _ = call(registry, cfg, world)
    assert trigger_of(bundle, "brann", "brann_trust").fired_count == 0
    assert bundle.world.fired == []


def test_call_world_success_has_no_skip_tag(registry, cfg):
    ctx = SimpleNamespace(verdicts={}, marks=["limit-exceeded"])
    world = SimpleNamespace(run=lambda *a: ctx, max_calls_per_day=0)
    _, result = call(registry, cfg, world)
    assert result.report_tags == ["limit-exceeded"]


def test_call_world_without_world_does_nothing(registry, cfg):
    _, result = call(registry, cfg, None)
    assert result.world_run_id is None
    assert result.report_tags == []


def test_call_world_passes_cfg_registry_and_run_id_to_world(registry, cfg):
    seen = []

    def run(work, reg, config, candidates, run_id):
        seen.append((reg, config, run_id))
        return SimpleNamespace(verdicts={}, marks=[])

    call(registry, cfg, SimpleNamespace(run=run, max_calls_per_day=0))
    assert seen == [(registry, cfg, "bnd-7")]


# ТБ #71 (docs/plan-tb.md п.6): журнал при мягком сбое world -- разметка по роли.
# Записи world -- aborted (вердикты не применены), summarizer той же границы -- committed.

def summ_world_rig(registry, cfg, tmp_path, summarizer_steps, world_steps):
    from game_kit import scripted
    from summarizer_kit import make_summ_rig

    return make_summ_rig(
        registry, cfg, tmp_path, narrator_turns(end_turn()), summarizer_steps,
        bundle=bundle_with_brann(registry, cfg), world=scripted(world_steps),
    )


def role_statuses(rig, role):
    return [r["turn_status"] for r in rig.journal.read_records() if r["role"] == role]


def boundary_roles(rig):
    return {r["role"] for r in rig.journal.read_records() if r["run_id"].startswith("bnd-")}


@pytest.mark.parametrize("steps", [REFUSAL, NETWORK], ids=["refusal", "network"])
def test_soft_world_skip_marks_world_records_aborted(registry, cfg, tmp_path, steps):
    from summarizer_kit import summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), steps)
    rig.runner.play("ход")
    statuses = role_statuses(rig, "world")
    assert statuses
    assert set(statuses) == {"aborted"}


@pytest.mark.parametrize("steps", [REFUSAL, NETWORK], ids=["refusal", "network"])
def test_soft_world_skip_keeps_summarizer_records_committed(registry, cfg, tmp_path, steps):
    from summarizer_kit import summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), steps)
    rig.runner.play("ход")
    assert role_statuses(rig, "summarizer") == ["committed"]


def test_soft_world_skip_world_and_summarizer_share_one_boundary_run_id(registry, cfg, tmp_path):
    from summarizer_kit import summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), REFUSAL)
    rig.runner.play("ход")
    records = [r for r in rig.journal.read_records() if r["role"] in ("world", "summarizer")]
    assert len({r["run_id"] for r in records}) == 1


def test_soft_world_skip_leaves_no_unmarked_boundary_records(registry, cfg, tmp_path):
    from summarizer_kit import summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), REFUSAL)
    rig.runner.play("ход")
    boundary = [r for r in rig.journal.read_records() if r["run_id"].startswith("bnd-")]
    assert boundary
    assert all(r["turn_status"] is not None for r in boundary)


def test_successful_boundary_marks_world_and_summarizer_committed(registry, cfg, tmp_path):
    from summarizer_kit import summ_steps

    steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), steps)
    rig.runner.play("ход")
    assert boundary_roles(rig) == {"summarizer", "world"}
    assert set(role_statuses(rig, "world")) == {"committed"}
    assert role_statuses(rig, "summarizer") == ["committed"]


def test_fatal_world_failure_marks_world_and_summarizer_aborted(registry, cfg, tmp_path):
    from summarizer_kit import summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_steps(), FATAL)
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert set(role_statuses(rig, "world")) == {"aborted"}
    assert role_statuses(rig, "summarizer") == ["aborted"]


def test_resume_boundary_after_soft_world_skip_marks_by_role(registry, cfg, tmp_path):
    # первая попытка упала на summarizer (всё aborted); повтор: summarizer ок, world пропущен
    from summarizer_kit import summ_fail_steps, summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_fail_steps() + summ_steps(), REFUSAL)
    rig.runner.play("ход")
    assert rig.runner.bundle.session.boundary_pending is True
    rig.runner.retry()
    assert rig.runner.bundle.session.boundary_pending is False
    assert role_statuses(rig, "summarizer")[-1] == "committed"
    assert role_statuses(rig, "world")[-1] == "aborted"


def test_resume_boundary_world_skip_run_ids_differ_from_failed_attempt(registry, cfg, tmp_path):
    from summarizer_kit import summ_fail_steps, summ_steps

    rig = summ_world_rig(registry, cfg, tmp_path, summ_fail_steps() + summ_steps(), REFUSAL)
    rig.runner.play("ход")
    rig.runner.retry()
    summarizer_runs = [r["run_id"] for r in rig.journal.read_records() if r["role"] == "summarizer"]
    assert len(set(summarizer_runs)) == 2
    assert role_statuses(rig, "summarizer")[0] == "aborted"
