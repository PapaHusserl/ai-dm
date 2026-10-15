# B59: рассказ короче min_narration_chars после раунда инструментов (сцену модель написала в
# мышлении) -- один автоповтор хода на той же модели с припиской TEXT_NOTE; тег short_retry.
# Только вне боя (ветка state is None в explore_turn). Повтор тоже короткий -- ход принят.
# Порог в тестах выключен conftest (min_narration_chars = 0); здесь включается явно.
import pytest
from game_kit import (
    ReactiveAdapter,
    core_dump,
    make_app,
    make_rig,
    player_action_input,
    run_records,
    script_then_react,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)
from master_kit import flag_call

from ai_dm.game.turn import ERROR_MENU, RETRY_NOTES, SOFTEN_NOTE, TEXT_NOTE
from ai_dm.llm.types import Text

LONG = "Ты идёшь по тихой улице Вейла, и ветер несёт запах дыма из труб, а в окнах гаснут огни."
GIVE = {
    "id": "gi", "name": "give_item",
    "input": {"type": "give_item", "item_id": "potion_of_healing", "qty": 2},
}
REFUSAL = {"stop": "refusal"}
FLAG = tools_step(flag_call("a"))


def notes_of(request):
    return [b.text for b in request.messages[0].content[1:] if isinstance(b, Text)]


def strict(rig, chars=80):
    rig.runner.app_cfg.master.min_narration_chars = chars
    return rig


def rig_of(registry, cfg, tmp_path, steps, chars=80):
    adapter = scripted(steps)
    return strict(make_rig(registry, cfg, tmp_path, adapter), chars), adapter


def dump(rig):
    return rig.runner.bundle.model_dump_json()


def test_long_text_is_over_the_default_threshold():
    assert len(LONG) >= 80


# константы

def test_text_note_is_the_designer_decision():
    assert TEXT_NOTE == (
        "Системная приписка: напиши сцену текстом ответа — "
        "игрок видит только текст, размышления ему не показываются."
    )


def test_retry_notes_by_reason():
    assert RETRY_NOTES == {"refusal": SOFTEN_NOTE, "short": TEXT_NOTE}


# повтор и успех

def test_short_after_tools_retries_and_commits(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.narration == LONG
    assert result.report_tags == ["short_retry"]
    assert result.failure is None
    assert result.menu is None


def test_retry_makes_two_passes_of_two_requests(registry, cfg, tmp_path):
    steps = [FLAG, text_step("Ок."), FLAG, text_step(LONG), text_step("лишний")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("Иду")
    assert len(adapter.requests) == 4


def test_text_note_only_in_second_pass(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    rig.runner.play("Иду")
    assert notes_of(adapter.requests[0]) == []
    assert notes_of(adapter.requests[1]) == []
    assert notes_of(adapter.requests[2]) == [TEXT_NOTE]
    assert notes_of(adapter.requests[3]) == [TEXT_NOTE]


def test_retry_goes_to_same_model(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    rig.runner.play("Иду")
    assert {r.model for r in adapter.requests} == {adapter.requests[0].model}


def test_retry_keeps_system_blocks_for_the_cache(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    rig.runner.play("Иду")
    assert adapter.requests[2].system == adapter.requests[0].system


def test_note_is_none_after_retry(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    rig.runner.play("Иду")
    assert rig.runner.note is None


def test_next_turn_after_retry_has_no_note_and_no_tag(registry, cfg, tmp_path):
    steps = [FLAG, text_step("Ок."), FLAG, text_step(LONG), text_step("Два.")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    rig.runner.play("a")
    result = rig.runner.play("b")
    assert result.report_tags == []
    assert notes_of(adapter.requests[4]) == []


def test_state_after_retry_equals_turn_without_short_attempt(registry, cfg, tmp_path):
    noisy, adapter = rig_of(
        registry, cfg, tmp_path / "a",
        [tools_step(GIVE), text_step("Ок."), tools_step(GIVE), text_step(LONG)],
    )
    clean, _ = rig_of(registry, cfg, tmp_path / "b", [tools_step(GIVE), text_step(LONG)])
    result = noisy.runner.play("Беру")
    clean.runner.play("Беру")
    assert core_dump(noisy.runner.bundle) == core_dump(clean.runner.bundle)
    assert result.requests == ["give_item"]
    assert noisy.runner.bundle.session.turn_seq == 1
    assert len(noisy.runner.bundle.memory.recent_turns) == 1
    assert noisy.runner.bundle.memory.recent_turns[0].player_input == "Беру"


def test_both_passes_are_committed_in_journal_under_one_run_id(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    result = rig.runner.play("Иду")
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 4
    assert {r["turn_status"] for r in records} == {"committed"}


# повтор тоже короткий

def test_second_short_is_accepted_with_short_retry_tag(registry, cfg, tmp_path):
    steps = [FLAG, text_step("Ок."), FLAG, text_step("Тоже."), text_step("лишний")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.narration == "Тоже."
    assert result.report_tags == ["short_retry"]
    assert result.failure is None
    assert len(adapter.requests) == 4
    assert rig.runner.note is None


# нет повтора

def test_text_without_tools_is_not_retried(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, [text_step("Ок."), text_step("лишний")])
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.narration == "Ок."
    assert result.report_tags == []
    assert len(adapter.requests) == 1


def test_narration_of_tool_round_text_counts_together(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("a"), text=LONG), text_step("Ок."), text_step("лишний")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Иду")
    assert result.report_tags == []
    assert len(adapter.requests) == 2
    assert LONG in result.narration


# граница порога

def test_79_chars_retry(registry, cfg, tmp_path):
    steps = [FLAG, text_step("а" * 79), FLAG, text_step(LONG)]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Иду")
    assert result.report_tags == ["short_retry"]
    assert len(adapter.requests) == 4


def test_80_chars_pass(registry, cfg, tmp_path):
    steps = [FLAG, text_step("а" * 80), text_step("лишний")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Иду")
    assert result.report_tags == []
    assert len(adapter.requests) == 2


def test_threshold_is_taken_from_config(registry, cfg, tmp_path):
    steps = [FLAG, text_step("а" * 30), FLAG, text_step(LONG)]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps, chars=31)
    result = rig.runner.play("Иду")
    assert result.report_tags == ["short_retry"]
    assert len(adapter.requests) == 4


def test_threshold_zero_disables_the_check(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, [FLAG, text_step("Ок."), text_step("x")], 0)
    result = rig.runner.play("Иду")
    assert result.report_tags == []
    assert len(adapter.requests) == 2


# бой

def fight(registry, cfg, tmp_path, **reactive):
    steps = [
        tools_step(start_combat_call(intent="capture")), text_step("Бой начался."),
    ]
    adapter = script_then_react(steps, **reactive)
    rig = strict(make_rig(registry, cfg, tmp_path, adapter))
    return rig


def test_start_combat_turn_with_short_text_is_not_retried(registry, cfg, tmp_path):
    rig = fight(registry, cfg, tmp_path)
    result = rig.runner.play("Нападаю")
    assert result.committed is True
    assert result.report_tags == []
    assert rig.runner.bundle.session.active_combat is not None


def test_combat_turns_are_not_retried(registry, cfg, tmp_path):
    action = player_action_input(["end_turn"])
    rig = fight(registry, cfg, tmp_path, classify=[action])
    rig.runner.play("Нападаю")
    result = rig.runner.play("Стою и жду")
    assert result.committed is True
    assert "short_retry" not in result.report_tags
    assert result.failure is None


def test_reactive_adapter_turn_is_not_retried(registry, cfg, tmp_path):
    rig = strict(make_rig(registry, cfg, tmp_path, ReactiveAdapter()))
    result = rig.runner.play("a")
    assert result.report_tags == []


# отказ и короткий рассказ

def test_refusal_then_short_is_accepted_without_short_retry(registry, cfg, tmp_path):
    steps = [REFUSAL, FLAG, text_step("Ок."), text_step("лишний")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.narration == "Ок."
    assert result.report_tags == ["refusal_retry"]
    assert len(adapter.requests) == 3
    assert notes_of(adapter.requests[1]) == [SOFTEN_NOTE]
    assert rig.runner.note is None


def double(registry, cfg, tmp_path):
    steps = [FLAG, text_step("Ок."), REFUSAL, text_step("не должен быть вызван")]
    rig, adapter = rig_of(registry, cfg, tmp_path, steps)
    before = dump(rig)
    return rig, adapter, before, rig.runner.play("Иду")


def test_short_then_refusal_fails_with_refusal(registry, cfg, tmp_path):
    _, adapter, _, result = double(registry, cfg, tmp_path)
    assert result.committed is False
    assert result.failure.reason == "refusal"
    assert result.narration == ""
    assert len(adapter.requests) == 3
    assert notes_of(adapter.requests[2]) == [TEXT_NOTE]


def test_short_then_refusal_has_both_tags_and_menu(registry, cfg, tmp_path):
    _, _, _, result = double(registry, cfg, tmp_path)
    assert result.report_tags == ["short_retry", "refusal"]
    assert result.menu == ERROR_MENU


def test_short_then_refusal_rolls_back_and_clears_note(registry, cfg, tmp_path):
    rig, _, before, result = double(registry, cfg, tmp_path)
    assert dump(rig) == before
    assert rig.runner.note is None
    records = run_records(rig.journal, result.run_id)
    assert {r["turn_status"] for r in records} == {"aborted"}


# автоотчёт

def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_short_retry_writes_auto_report(registry, tmp_path):
    adapter = scripted([FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    app = make_app(registry, tmp_path, adapter, auto_reports=True)
    app.runner.app_cfg.master.min_narration_chars = 80
    reply = app.handle("Иду")
    assert reply.turn.committed is True
    assert reply.turn.report_tags == ["short_retry"]
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-short_retry")


def test_short_retry_report_off_writes_nothing(registry, tmp_path):
    adapter = scripted([FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    app = make_app(registry, tmp_path, adapter, auto_reports=False)
    app.runner.app_cfg.master.min_narration_chars = 80
    app.handle("Иду")
    assert issues(tmp_path) == []


@pytest.mark.parametrize("reason", ["short", "refusal"])
def test_retry_tag_is_reason_plus_retry(registry, cfg, tmp_path, reason):
    rig, _ = rig_of(registry, cfg, tmp_path, [text_step("x")])
    started = rig.runner.play("a")
    assert rig.runner.retry_result(started, reason).report_tags == [f"{reason}_retry"]


# Т3 (мини-партия #18): сцена + отклонённый вызов + принятый offer_choices -- без short_retry

BAD_FLAG = {"id": "bf", "name": "set_flag", "input": {"type": "set_flag"}}
OFFER = {
    "id": "of", "name": "offer_choices",
    "input": {"type": "offer_choices", "choices": ["Бежать", "Драться"]},
}


def t436_steps():
    from game_kit import skill_check_call

    return [
        tools_step(skill_check_call(), BAD_FLAG, OFFER, text=LONG),
        tools_step(flag_call("a")),
        text_step("Письмо у тебя."),
    ]


def test_t436_pattern_has_one_pass_without_tags(registry, cfg, tmp_path):
    rig, adapter = rig_of(registry, cfg, tmp_path, t436_steps() + [text_step("лишний")])
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.report_tags == []
    assert result.failure is None
    assert len(adapter.requests) == 3
    assert notes_of(adapter.requests[2]) == []


def test_t436_pattern_narration_has_scene_and_final(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, t436_steps())
    result = rig.runner.play("Иду")
    assert result.narration == LONG + "\n\nПисьмо у тебя."


def test_t436_pattern_rolls_once(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, t436_steps())
    result = rig.runner.play("Иду")
    assert len(result.rolls) == 1
    assert result.requests == ["skill_check", "offer_choices", "set_flag"]


def test_t436_pattern_state_equals_single_pass(registry, cfg, tmp_path):
    from game_kit import skill_check_call

    noisy, _ = rig_of(registry, cfg, tmp_path / "a", t436_steps())
    clean_steps = [
        tools_step(skill_check_call(), OFFER, flag_call("a"), text=LONG),
        text_step("Письмо у тебя."),
    ]
    clean, _ = rig_of(registry, cfg, tmp_path / "b", clean_steps)
    noisy.runner.play("Иду")
    clean.runner.play("Иду")
    assert core_dump(noisy.runner.bundle) == core_dump(clean.runner.bundle)


def test_t436_pattern_is_one_run_with_three_journal_calls(registry, cfg, tmp_path):
    rig, _ = rig_of(registry, cfg, tmp_path, t436_steps())
    result = rig.runner.play("Иду")
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 3
    assert {r["turn_status"] for r in records} == {"committed"}


def test_t436_pattern_writes_no_auto_report(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted(t436_steps()), auto_reports=True)
    app.runner.app_cfg.master.min_narration_chars = 80
    reply = app.handle("Иду")
    assert reply.turn.committed is True
    assert issues(tmp_path) == []
