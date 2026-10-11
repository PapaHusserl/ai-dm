# Ожидаемый API: ai_dm.game.turn (TurnRunner, TurnResult) -- контракт в game_kit.py.
# Атомарный ход: commit (RNG, turn_seq, TurnRecord, журнал), abort при TurnFailed, меню 2.2,
# «повторить», ход -> сейв -> загрузка -> тот же следующий бросок.
import json

import pytest
from game_kit import (
    BAD_CHECK,
    SAVED_AT,
    CountingAdapter,
    core_dump,
    damage_call,
    flag_call,
    make_rig,
    run_records,
    scripted,
    skill_check_call,
    state_of,
    text_step,
    tool_names,
    tools_step,
)
from protocol_kit import make_bundle, make_ctx, req
from slots_kit import saved_close_reason

from ai_dm.core.rng import Rng
from ai_dm.protocol.apply import apply
from ai_dm.protocol.schema import tool_set

MENU = ["retry", "switch_model", "save_and_quit"]


def dump(rig):
    return rig.runner.bundle.model_dump_json()


# commit

def test_text_turn_commits_narration(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Стражник кивает.")]))
    result = rig.runner.play("Здороваюсь")
    assert result.committed is True
    assert result.narration == "Стражник кивает."
    assert result.failure is None
    assert result.menu is None


def test_tool_effects_are_applied_on_commit(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("met_guard")), text_step("Стражник кивает вам.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("Здороваюсь")
    assert rig.runner.bundle.world.flags["met_guard"] is True
    assert result.requests == ["set_flag"]
    assert result.narration == "Стражник кивает вам."


def test_commit_increments_turn_seq(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Раз."), text_step("Два.")]))
    rig.runner.play("a")
    assert rig.runner.bundle.session.turn_seq == 1
    rig.runner.play("b")
    assert rig.runner.bundle.session.turn_seq == 2


def test_commit_adds_turn_record(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("f1")), text_step("Рассказ.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("Осматриваюсь")
    records = rig.runner.bundle.memory.recent_turns
    assert len(records) == 1
    record = records[0]
    assert record.turn_seq == 1
    assert record.player_input == "Осматриваюсь"
    assert record.narration == "Рассказ."
    assert record.requests == ["set_flag"]
    assert record.at_s == rig.runner.bundle.world.clock.now_s


def test_turn_record_keeps_roll_lines(registry, cfg, tmp_path):
    steps = [tools_step(skill_check_call()), text_step("Итог.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("Убеждаю")
    record = rig.runner.bundle.memory.recent_turns[0]
    assert len(record.rolls) == 1
    assert "СЛ 15" in record.rolls[0]
    assert record.requests == ["skill_check"]
    assert record.rolls[0] in result.lines


def test_commit_counts_scene_turn(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    rig.runner.play("a")
    rig.runner.play("b")
    assert rig.runner.bundle.session.current_scene.player_turns == 2


def test_commit_syncs_world_rng_with_turn_rng(registry, cfg, tmp_path):
    steps = [tools_step(skill_check_call()), text_step("Итог.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    before = rig.runner.bundle.world.rng
    ref = make_ctx(registry, cfg, bundle=make_bundle(registry))
    apply(ref, req("skill_check", skill="persuasion", category="medium", stakes="normal"))
    rig.runner.play("Убеждаю")
    after = rig.runner.bundle.world.rng
    assert after.draws > before.draws
    assert after == ref.rng.state


def test_turn_without_rolls_keeps_rng(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    before = rig.runner.bundle.world.rng
    rig.runner.play("Молчу")
    assert rig.runner.bundle.world.rng == before


def test_commit_marks_journal_records_committed(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("f1")), text_step("Рассказ.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("Осматриваюсь")
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 2
    assert {r["turn_status"] for r in records} == {"committed"}


def test_run_id_is_new_for_every_turn(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    first = rig.runner.play("a")
    second = rig.runner.play("b")
    assert first.run_id
    assert second.run_id
    assert first.run_id != second.run_id


def test_all_calls_of_a_turn_share_run_id(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("a")), tools_step(flag_call("b")), text_step()]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("a")
    records = rig.journal.read_records()
    assert len(records) == 3
    assert {r["run_id"] for r in records} == {result.run_id}


def test_journal_turn_seq_is_value_before_commit(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    rig.runner.play("a")
    rig.runner.play("b")
    assert [r["turn_seq"] for r in rig.journal.read_records()] == [0, 1]


def test_cost_is_written_to_ledger(registry, cfg, tmp_path):
    steps = [{"text": "Рассказ.", "usage": {"input": 1000, "output": 100}}]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("a")
    assert len(rig.ledger.session_lines) == 1
    assert rig.ledger.session_lines[0]["role"] == "narrator"


# запрос к модели

def test_explore_request_uses_explore_tools_and_player_text(registry, cfg, tmp_path):
    adapter = scripted([text_step()])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("Иду в лес")
    request = adapter.requests[0]
    assert tool_names(request) == {d["name"] for d in tool_set("explore")}
    assert state_of(request)["player_input"] == "Иду в лес"


def test_request_model_is_adapter_model(registry, cfg, tmp_path):
    adapter = scripted([text_step()])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("a")
    assert adapter.requests[0].model == adapter.info().model


def test_world_text_goes_to_system_prompt(registry, cfg, tmp_path):
    adapter = scripted([text_step()])
    rig = make_rig(registry, cfg, tmp_path, adapter, world_text="Деревня Вейл у реки.")
    rig.runner.play("a")
    assert "Деревня Вейл у реки." in adapter.requests[0].system[1].text


def test_turn_does_not_call_adapter_count_tokens(registry, cfg, tmp_path):
    adapter = CountingAdapter(scripted([text_step(), text_step()]))
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("a")
    rig.runner.play("b")
    assert adapter.count_calls == 0


def test_recent_turns_reach_next_request(registry, cfg, tmp_path):
    adapter = scripted([text_step("Первый рассказ."), text_step()])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("первый ввод")
    rig.runner.play("b")
    turns = state_of(adapter.requests[1])["recent_turns"]
    assert [t["narration"] for t in turns] == ["Первый рассказ."]


# abort: причины

NETWORK = [{"error": "transient", "message": "сеть"}] * 4
INVALID = [tools_step(BAD_CHECK)] * 3
ROUNDS = [tools_step(flag_call(f"f{i}")) for i in range(9)]
REFUSAL = [{"stop": "refusal"}]
FATAL = [{"error": "fatal", "message": "ключ отозван"}]
CASES = [
    ("network", NETWORK), ("invalid", INVALID), ("rounds", ROUNDS), ("refusal", REFUSAL),
    ("fatal", FATAL),
]


def failed(registry, cfg, tmp_path, steps):
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    before = dump(rig)
    result = rig.runner.play("Иду")
    return rig, before, result


@pytest.mark.parametrize(("reason", "steps"), CASES)
def test_failure_reason_and_no_commit(registry, cfg, tmp_path, reason, steps):
    _, _, result = failed(registry, cfg, tmp_path, steps)
    assert result.committed is False
    assert result.failure.reason == reason
    assert result.narration == ""


@pytest.mark.parametrize(("reason", "steps"), CASES)
def test_abort_leaves_bundle_byte_identical(registry, cfg, tmp_path, reason, steps):
    rig, before, _ = failed(registry, cfg, tmp_path, steps)
    assert dump(rig) == before


@pytest.mark.parametrize(("reason", "steps"), CASES)
def test_abort_marks_journal_aborted(registry, cfg, tmp_path, reason, steps):
    rig, _, result = failed(registry, cfg, tmp_path, steps)
    records = run_records(rig.journal, result.run_id)
    assert records
    assert {r["turn_status"] for r in records} == {"aborted"}


@pytest.mark.parametrize(("reason", "steps"), CASES)
def test_abort_returns_error_menu(registry, cfg, tmp_path, reason, steps):
    _, _, result = failed(registry, cfg, tmp_path, steps)
    assert result.menu == MENU


def test_network_failure_pauses_one_three_ten(registry, cfg, tmp_path):
    rig, _, _ = failed(registry, cfg, tmp_path, NETWORK)
    assert rig.sleeps == [1, 3, 10]


def test_three_transient_errors_then_success_commits(registry, cfg, tmp_path):
    steps = [{"error": "transient"}] * 3 + [text_step("Наконец-то ответ.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("a")
    assert result.committed is True
    assert rig.sleeps == [1, 3, 10]
    assert result.narration == "Наконец-то ответ."


def test_two_invalid_answers_then_success_commits(registry, cfg, tmp_path):
    steps = [tools_step(BAD_CHECK), tools_step(BAD_CHECK), text_step("Ну ладно.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    assert rig.runner.play("a").committed is True


def test_fatal_does_not_retry_or_sleep(registry, cfg, tmp_path):
    adapter = scripted(FATAL + [text_step()])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    result = rig.runner.play("a")
    assert result.failure.reason == "fatal"
    assert len(adapter.requests) == 1
    assert rig.sleeps == []


def test_refusal_adds_hint_about_model_and_tone_and_tag(registry, cfg, tmp_path):
    _, _, result = failed(registry, cfg, tmp_path, REFUSAL)
    assert "tone" in result.hint
    assert "модел" in result.hint
    assert result.report_tags == ["refusal"]


def test_other_failures_have_no_tone_hint(registry, cfg, tmp_path):
    for _, steps in CASES:
        if steps is REFUSAL:
            continue
        _, _, result = failed(registry, cfg, tmp_path / str(id(steps)), steps)
        assert "tone" not in (result.hint or "")


def test_failure_after_state_change_rolls_back_inventory_and_rng(registry, cfg, tmp_path):
    # первый ответ меняет состояние (предмет, бросок), второй -- fatal: ничего не применено
    give = {
        "id": "gi", "name": "give_item",
        "input": {"type": "give_item", "item_id": "potion_of_healing", "qty": 2},
    }
    steps = [tools_step(give, skill_check_call(), flag_call("half_done"))] + FATAL
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    before = dump(rig)
    rng_before = rig.runner.bundle.world.rng
    result = rig.runner.play("a")
    assert result.committed is False
    assert dump(rig) == before
    assert rig.runner.bundle.world.rng == rng_before
    assert "half_done" not in rig.runner.bundle.world.flags


def test_deadly_damage_failure_leaves_hero_alive_after_abort(registry, cfg, tmp_path):
    steps = [tools_step(damage_call())] + FATAL
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    hp = rig.runner.bundle.heroes[0].creature.hp_current
    rig.runner.play("a")
    assert rig.runner.bundle.heroes[0].creature.hp_current == hp


def test_unexpected_exception_aborts_and_reraises(registry, cfg, tmp_path):
    from ai_dm.llm.mock import ScriptExhausted

    rig = make_rig(registry, cfg, tmp_path, scripted([]))
    before = dump(rig)
    with pytest.raises(ScriptExhausted):
        rig.runner.play("a")
    assert dump(rig) == before


def test_failed_turn_does_not_count_for_scene(registry, cfg, tmp_path):
    rig, _, _ = failed(registry, cfg, tmp_path, FATAL)
    assert rig.runner.bundle.session.current_scene.player_turns == 0
    assert rig.runner.bundle.session.turn_seq == 0


# «повторить»

def test_retry_gives_same_rolls_as_turn_without_failure(registry, cfg, tmp_path):
    good = [tools_step(skill_check_call()), text_step("Стражник кивает.")]
    # сбой после того, как бросок уже сделан на рабочей копии
    bad = [tools_step(skill_check_call())] + NETWORK
    rig = make_rig(registry, cfg, tmp_path / "a", scripted(bad))
    failed_result = rig.runner.play("Убеждаю")
    assert failed_result.committed is False
    rig.runner.set_adapter(scripted(good))
    retried = rig.runner.retry()
    reference = make_rig(registry, cfg, tmp_path / "b", scripted(good))
    reference.runner.play("Убеждаю")
    assert retried.committed is True
    assert core_dump(rig.runner.bundle) == core_dump(reference.runner.bundle)
    assert rig.runner.bundle.world.rng == reference.runner.bundle.world.rng


def test_retry_uses_new_run_id(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted(FATAL))
    first = rig.runner.play("Иду")
    rig.runner.set_adapter(scripted([text_step("Дошли.")]))
    second = rig.runner.retry()
    assert second.run_id != first.run_id
    assert {r["turn_status"] for r in run_records(rig.journal, first.run_id)} == {"aborted"}
    assert {r["turn_status"] for r in run_records(rig.journal, second.run_id)} == {"committed"}


def test_retry_repeats_same_player_input(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted(FATAL))
    rig.runner.play("Иду в Лес")
    adapter = scripted([text_step("Дошли.")])
    rig.runner.set_adapter(adapter)
    rig.runner.retry()
    assert state_of(adapter.requests[0])["player_input"] == "Иду в Лес"


def test_set_adapter_switches_request_model(registry, cfg, tmp_path):
    from game_kit import SONNET, ReactiveAdapter

    rig = make_rig(registry, cfg, tmp_path, scripted(FATAL))
    rig.runner.play("a")
    other = ReactiveAdapter(model=SONNET)
    rig.runner.set_adapter(other)
    rig.runner.retry()
    assert other.requests[0].model == SONNET


# ход -> сейв -> загрузка -> следующий бросок

def test_save_load_next_roll_matches_continuous_play(registry, cfg, tmp_path):
    from ai_dm.persistence.store import load_slot, save_slot

    step_a = [tools_step(skill_check_call("a")), text_step("Первый.")]
    step_b = [tools_step(skill_check_call("b", skill="perception")), text_step("Второй.")]
    live = make_rig(registry, cfg, tmp_path / "live", scripted(step_a + step_b))
    live.runner.play("первый")
    save_slot(tmp_path, live.runner.bundle, "manual-t", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "w1", "manual-t")
    assert loaded.world.rng == live.runner.bundle.world.rng
    resumed = make_rig(registry, cfg, tmp_path / "res", scripted(step_b), bundle=loaded)
    live.runner.play("второй")
    resumed.runner.play("второй")
    assert core_dump(resumed.runner.bundle) == core_dump(live.runner.bundle)
    assert resumed.runner.bundle.world.rng.draws > loaded.world.rng.draws


def test_turn_runs_on_copy_original_rng_matches_state(registry, cfg, tmp_path):
    # RNG хода собирается из world.rng: те же исходные данные -- те же броски
    steps = [tools_step(skill_check_call()), text_step()]
    one = make_rig(registry, cfg, tmp_path / "1", scripted(steps))
    two = make_rig(registry, cfg, tmp_path / "2", scripted(steps))
    one.runner.play("a")
    two.runner.play("a")
    assert one.runner.bundle.world.rng == two.runner.bundle.world.rng
    assert Rng.from_state(one.runner.bundle.world.rng).draws == one.runner.bundle.world.rng.draws


def test_tool_result_carries_roll_line_and_dc(registry, cfg, tmp_path):
    adapter = scripted([tools_step(skill_check_call()), text_step("Итог.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("Убеждаю")
    block = adapter.requests[1].messages[-1].content[0]
    body = json.loads(block.content)
    assert body["result"]["dc"] == 15
    assert "СЛ 15" in body["log"][0]


# B3: run_id уникален между перезапусками

def test_run_id_differs_between_runners_with_same_clock_without_tag(registry, cfg, tmp_path):
    one = make_rig(registry, cfg, tmp_path, scripted([text_step()]), run_tag=None)
    two = make_rig(registry, cfg, tmp_path, scripted([text_step()]), run_tag=None)
    first = one.runner.play("a")
    second = two.runner.play("a")
    assert first.run_id != second.run_id
    assert len(run_records(two.journal, first.run_id)) == 1
    assert len(run_records(two.journal, second.run_id)) == 1


def test_fixed_run_tag_makes_run_ids_deterministic(registry, cfg, tmp_path):
    one = make_rig(registry, cfg, tmp_path / "a", scripted([text_step()]), run_tag="fix")
    two = make_rig(registry, cfg, tmp_path / "b", scripted([text_step()]), run_tag="fix")
    first = one.runner.play("a")
    second = two.runner.play("a")
    assert first.run_id == second.run_id
    assert "fix" in first.run_id


def test_different_run_tags_give_different_run_ids(registry, cfg, tmp_path):
    one = make_rig(registry, cfg, tmp_path, scripted([text_step()]), run_tag="aa")
    two = make_rig(registry, cfg, tmp_path, scripted([text_step()]), run_tag="bb")
    assert one.runner.play("a").run_id != two.runner.play("a").run_id


# B5: в сейве последние recent_turns_keep записей, окно промпта отдельно

def test_51st_turn_pushes_out_the_first(registry, cfg, tmp_path):
    from game_kit import ReactiveAdapter

    rig = make_rig(registry, cfg, tmp_path, ReactiveAdapter())
    for number in range(1, 52):
        rig.runner.play(f"ход {number}")
    records = rig.runner.bundle.memory.recent_turns
    assert len(records) == 50
    assert records[0].turn_seq == 2
    assert records[0].player_input == "ход 2"
    assert records[-1].turn_seq == 51
    assert rig.runner.bundle.session.turn_seq == 51


def test_prompt_window_stays_8_with_50_records(registry, cfg, tmp_path):
    from game_kit import ReactiveAdapter

    adapter = ReactiveAdapter()
    rig = make_rig(registry, cfg, tmp_path, adapter)
    for number in range(1, 52):
        rig.runner.play(f"ход {number}")
    turns = state_of(adapter.requests[-1])["recent_turns"]
    assert [t["turn_seq"] for t in turns] == list(range(43, 51))


def test_recent_turns_keep_comes_from_config(registry, cfg, tmp_path):
    from game_kit import ReactiveAdapter

    rig = make_rig(registry, cfg, tmp_path, ReactiveAdapter())
    rig.runner.app_cfg.master.recent_turns_keep = 3
    for number in range(1, 6):
        rig.runner.play(f"ход {number}")
    assert [r.turn_seq for r in rig.runner.bundle.memory.recent_turns] == [3, 4, 5]


# B1: смерть героя вне боя

def test_hero_death_outside_combat_does_not_close_scene_or_autosave(registry, cfg, tmp_path):
    from slots_kit import list_slots

    bundle = make_bundle(registry)
    bundle.heroes[0].creature.hp_max = 1
    bundle.heroes[0].creature.hp_current = 1
    steps = [tools_step(damage_call()), text_step("Огонь поглотил вас.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    result = rig.runner.play("Прыгаю в огонь")
    assert result.hero_dead is True
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.current_scene.closed_reason is None
    assert list_slots(tmp_path, "w1") == []


# D7: итоги сцены и главы из TurnContext

def test_end_scene_summary_reaches_turn_result(registry, cfg, tmp_path):
    from game_kit import end_scene_call

    call = end_scene_call(summary="Герой договорился со стражей.")
    steps = [tools_step(call), text_step("Конец.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("закончим")
    assert result.scene_summary == "Герой договорился со стражей."


def test_turn_without_summary_has_none(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    result = rig.runner.play("a")
    assert result.scene_summary is None
    assert result.chapter_title is None


# P3: бюджет контекста в ходе, meta и тег context_overflow

def narrator_records(rig):
    return [r for r in rig.journal.read_records() if r["role"] == "narrator"]


def test_roomy_turn_has_meta_without_overflow_tag(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    result = rig.runner.play("a")
    record = narrator_records(rig)[0]
    assert record["meta"]["context"]["raised"] is False
    assert record["meta"]["context"]["overflow"] is False
    assert record["report_tags"] == []
    assert "context_overflow" not in result.report_tags


def test_overflow_turn_has_tag_in_journal_and_result(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]))
    rig.app_cfg.master.context_cap = 1
    result = rig.runner.play("a")
    record = narrator_records(rig)[0]
    assert record["meta"]["context"]["raised"] is True
    assert record["report_tags"] == ["context_overflow"]
    assert result.report_tags == ["context_overflow"]
    assert result.committed is True


def test_overflow_tag_is_once_with_several_tool_rounds(registry, cfg, tmp_path):
    steps = [
        tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step("Конец."),
    ]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.app_cfg.master.context_cap = 1
    result = rig.runner.play("a")
    assert result.report_tags.count("context_overflow") == 1
    assert result.requests == ["set_flag", "set_flag"]


def test_journal_meta_has_budget_and_dropped(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step(), text_step()]))
    rig.app_cfg.master.context_cap = 1
    rig.runner.play("a")
    rig.runner.play("b")
    meta = narrator_records(rig)[1]["meta"]["context"]
    assert meta["cap"] == 1
    assert meta["budget"] == 800_000
    assert meta["estimate"] > 1


def test_meta_has_api_tokens_from_usage(registry, cfg, tmp_path):
    usage = {"input": 100, "output": 5, "cache_read": 20, "cache_write": 7}
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step() | {"usage": usage}]))
    rig.runner.play("a")
    assert narrator_records(rig)[0]["meta"]["context"]["api_tokens"] == 127


def test_turn_with_dropped_turns_replays_without_divergence(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    live = make_rig(registry, cfg, tmp_path / "live", scripted([text_step()] * 4))
    live.app_cfg.master.context_cap = 1
    for number in range(4):
        live.runner.play(f"ход {number}")
    assert narrator_records(live)[-1]["meta"]["context"]["dropped"]
    replay = ReplayAdapter(live.journal.read_records(), role="narrator")
    again = make_rig(
        registry, cfg, tmp_path / "again", replay, model="claude-opus-5-5",
    )
    again.app_cfg.master.context_cap = 1
    for number in range(4):
        assert again.runner.play(f"ход {number}").committed is True
