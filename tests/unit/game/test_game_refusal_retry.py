# Р2 (R2-PLAN, В5а-В9а, Q1а, Q3а, Q4б): отказ рассказчика -- один автоповтор хода на той же модели
# с припиской SOFTEN_NOTE (отдельный Text-блок после JSON состояния), с новой копии бандла, те же
# броски; второй отказ -- меню как раньше. Другие сбои повтора не дают.
import pytest
from game_kit import (
    BAD_CHECK,
    ReactiveAdapter,
    core_dump,
    end_turn_number,
    flag_call,
    make_app,
    make_rig,
    player_action_input,
    run_records,
    script_then_react,
    scripted,
    skill_check_call,
    start_combat_call,
    state_of,
    text_step,
    tool_names,
    tools_step,
)

from ai_dm.game.turn import ERROR_MENU, REFUSAL_HINT, SOFTEN_NOTE
from ai_dm.llm.types import ChatResponse, Text, Usage

GIVE = {
    "id": "gi", "name": "give_item",
    "input": {"type": "give_item", "item_id": "potion_of_healing", "qty": 2},
}
REFUSAL = {"stop": "refusal"}
CLASSIFY_TOOLS = {"player_action", "unsupported_action"}
NPC_ONLY = {"npc_action"}


def notes_of(request):
    # все Text-блоки первого сообщения после JSON состояния
    return [b.text for b in request.messages[0].content[1:] if isinstance(b, Text)]


def dump(rig):
    return rig.runner.bundle.model_dump_json()


class RefuseOnce:
    # обёртка: после arm() первый запрос с нужным набором инструментов получает refusal
    def __init__(self, inner, names):
        self.inner = inner
        self.names = set(names)
        self.armed = False
        self.requests = []

    def arm(self):
        self.armed = True

    def info(self):
        return self.inner.info()

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        if self.armed and tool_names(request) == self.names:
            self.armed = False
            return ChatResponse(
                content=[], stop_reason="refusal", usage=Usage(input=10, output=0),
                request_id="refused", model=request.model,
            )
        return self.inner.complete(request)


# текст приписки (Q4б)

def test_soften_note_text_is_the_designer_decision():
    assert SOFTEN_NOTE == (
        "Системная приписка: опиши эту сцену сдержанно, без натурализма; "
        "насилие и откровенность — за кадром или намёком."
    )


# исследование: отказ -> повтор

def test_explore_refusal_then_success_commits_with_retry_tag(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    result = rig.runner.play("Иду")
    assert result.committed is True
    assert result.narration == "Рассказ."
    assert result.report_tags == ["refusal_retry"]
    assert result.failure is None
    assert result.menu is None


def test_retry_makes_exactly_two_requests(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ."), text_step("лишний")])
    make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert len(adapter.requests) == 2


def test_second_request_has_soften_note_first_has_none(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ.")])
    make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert notes_of(adapter.requests[0]) == []
    assert notes_of(adapter.requests[1]) == [SOFTEN_NOTE]


def test_retry_goes_to_same_model(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ.")])
    make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert adapter.requests[0].model == adapter.requests[1].model


def test_retry_keeps_system_blocks_for_the_cache(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ.")])
    make_rig(registry, cfg, tmp_path, adapter).runner.play("Иду")
    assert adapter.requests[1].system == adapter.requests[0].system


def test_turn_record_has_player_line_without_note(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Рассказ.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("Иду")
    records = rig.runner.bundle.memory.recent_turns
    assert len(records) == 1
    assert records[0].player_input == "Иду"
    assert state_of(adapter.requests[1])["player_input"] == "Иду"
    assert rig.runner.bundle.session.turn_seq == 1


def test_retry_turn_equals_turn_without_refusal(registry, cfg, tmp_path):
    noisy = make_rig(registry, cfg, tmp_path / "a", scripted([REFUSAL, text_step("Рассказ.")]))
    clean = make_rig(registry, cfg, tmp_path / "b", scripted([text_step("Рассказ.")]))
    noisy.runner.play("Иду")
    clean.runner.play("Иду")
    assert core_dump(noisy.runner.bundle) == core_dump(clean.runner.bundle)


# второй отказ

def double(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, REFUSAL, text_step("не должен быть вызван")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    before = dump(rig)
    return rig, adapter, before, rig.runner.play("Иду")


def test_double_refusal_fails_with_refusal(registry, cfg, tmp_path):
    _, _, _, result = double(registry, cfg, tmp_path)
    assert result.committed is False
    assert result.failure.reason == "refusal"
    assert result.narration == ""


def test_double_refusal_makes_only_two_requests(registry, cfg, tmp_path):
    _, adapter, _, _ = double(registry, cfg, tmp_path)
    assert len(adapter.requests) == 2


def test_double_refusal_gives_error_menu_and_hint(registry, cfg, tmp_path):
    _, _, _, result = double(registry, cfg, tmp_path)
    assert result.menu == ERROR_MENU
    assert result.hint == REFUSAL_HINT


def test_double_refusal_has_both_tags(registry, cfg, tmp_path):
    _, _, _, result = double(registry, cfg, tmp_path)
    assert result.report_tags == ["refusal_retry", "refusal"]
    assert len(result.report_tags) == 2


def test_double_refusal_leaves_bundle_byte_identical(registry, cfg, tmp_path):
    rig, _, before, _ = double(registry, cfg, tmp_path)
    assert dump(rig) == before


def test_double_refusal_marks_journal_aborted(registry, cfg, tmp_path):
    rig, _, _, result = double(registry, cfg, tmp_path)
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 2
    assert {r["turn_status"] for r in records} == {"aborted"}


def test_retry_after_double_refusal_is_a_fresh_turn_without_note(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, REFUSAL, text_step("Дошли.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("Иду")
    result = rig.runner.retry()
    assert result.committed is True
    assert notes_of(adapter.requests[2]) == []


# журнал

def test_both_attempts_are_committed_in_journal(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([REFUSAL, text_step("Рассказ.")]))
    result = rig.runner.play("Иду")
    records = run_records(rig.journal, result.run_id)
    assert {r["turn_status"] for r in records} == {"committed"}
    assert {r["attempt"] for r in records} == {1}


# состояние первой попытки не просачивается

def test_state_of_refused_attempt_is_not_applied_twice(registry, cfg, tmp_path):
    steps = [tools_step(GIVE), REFUSAL, tools_step(GIVE), text_step("Ок.")]
    noisy = make_rig(registry, cfg, tmp_path / "a", scripted(steps))
    clean = make_rig(
        registry, cfg, tmp_path / "b", scripted([tools_step(GIVE), text_step("Ок.")])
    )
    result = noisy.runner.play("Беру")
    clean.runner.play("Беру")
    assert core_dump(noisy.runner.bundle) == core_dump(clean.runner.bundle)
    assert result.requests == ["give_item"]


def test_second_attempt_without_the_item_leaves_inventory_untouched(registry, cfg, tmp_path):
    steps = [tools_step(GIVE), REFUSAL, text_step("Ничего.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    before = rig.runner.bundle.heroes[0].inventory
    result = rig.runner.play("Беру")
    assert result.committed is True
    assert rig.runner.bundle.heroes[0].inventory == before
    assert result.requests == []


def test_flag_of_refused_attempt_is_not_kept(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("half")), REFUSAL, text_step("Ничего.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    rig.runner.play("a")
    assert "half" not in rig.runner.bundle.world.flags


# броски (В9а)

def test_rolls_after_retry_equal_rolls_of_turn_without_refusal(registry, cfg, tmp_path):
    check = tools_step(skill_check_call())
    noisy = make_rig(
        registry, cfg, tmp_path / "a", scripted([check, REFUSAL, check, text_step("Итог.")])
    )
    clean = make_rig(registry, cfg, tmp_path / "b", scripted([check, text_step("Итог.")]))
    result = noisy.runner.play("Убеждаю")
    reference = clean.runner.play("Убеждаю")
    assert result.lines == reference.lines
    assert noisy.runner.bundle.memory.recent_turns[0].rolls == (
        clean.runner.bundle.memory.recent_turns[0].rolls
    )
    assert noisy.runner.bundle.world.rng == clean.runner.bundle.world.rng
    assert len(result.lines) == 1


def test_requests_of_result_come_from_second_attempt_only(registry, cfg, tmp_path):
    steps = [tools_step(flag_call("a", "c1")), REFUSAL, text_step("Ок.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("a")
    assert result.requests == []
    assert rig.runner.bundle.memory.recent_turns[0].requests == []


# другие сбои: повтора нет

NETWORK = [{"error": "transient", "message": "сеть"}] * 4
INVALID = [tools_step(BAD_CHECK)] * 3
ROUNDS = [tools_step(flag_call(f"f{i}")) for i in range(9)]
FATAL = [{"error": "fatal", "message": "ключ"}]
OTHERS = [
    ("network", NETWORK, 4), ("invalid", INVALID, 3), ("rounds", ROUNDS, 9), ("fatal", FATAL, 1),
]


@pytest.mark.parametrize(("reason", "steps", "calls"), OTHERS)
def test_other_failures_do_not_retry_and_have_no_note(
    registry, cfg, tmp_path, reason, steps, calls
):
    adapter = scripted(steps + [text_step("не должен быть вызван")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    result = rig.runner.play("Иду")
    assert result.failure.reason == reason
    assert len(adapter.requests) == calls
    assert all(notes_of(r) == [] for r in adapter.requests)
    assert "refusal_retry" not in result.report_tags


# self.note

def test_note_is_none_after_successful_retry(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([REFUSAL, text_step("Рассказ.")]))
    rig.runner.play("Иду")
    assert rig.runner.note is None


def test_note_is_none_after_double_refusal(registry, cfg, tmp_path):
    rig, _, _, _ = double(registry, cfg, tmp_path)
    assert rig.runner.note is None


def test_next_turn_after_retry_has_no_note(registry, cfg, tmp_path):
    adapter = scripted([REFUSAL, text_step("Раз."), text_step("Два.")])
    rig = make_rig(registry, cfg, tmp_path, adapter)
    rig.runner.play("a")
    result = rig.runner.play("b")
    assert result.report_tags == []
    assert notes_of(adapter.requests[2]) == []


def test_clean_turn_has_no_retry_tag_and_no_note(registry, cfg, tmp_path):
    adapter = scripted([text_step("Раз.")])
    result = make_rig(registry, cfg, tmp_path, adapter).runner.play("a")
    assert result.report_tags == []
    assert notes_of(adapter.requests[0]) == []


# бой (В8а)

def fight(registry, cfg, tmp_path, names, *, grakh=False, **reactive):
    steps = [
        tools_step(start_combat_call(grakh=grakh, intent="capture")), text_step("Бой начался."),
    ]
    inner = script_then_react(steps, **reactive)
    adapter = RefuseOnce(inner, names)
    rig = make_rig(registry, cfg, tmp_path, adapter)
    assert rig.runner.play("Нападаю").committed is True
    return rig, adapter


def narrate_names():
    from ai_dm.protocol.schema import tool_set

    return {d["name"] for d in tool_set("combat_narrate")}


def test_refusal_on_classify_retries_whole_turn(registry, cfg, tmp_path):
    action = player_action_input(["end_turn"])
    rig, adapter = fight(registry, cfg, tmp_path / "a", CLASSIFY_TOOLS, classify=[action])
    clean, _ = fight(registry, cfg, tmp_path / "b", {"never"}, classify=[action])
    adapter.arm()
    result = rig.runner.play("Стою и жду")
    reference = clean.runner.play("Стою и жду")
    assert result.committed is True
    assert result.report_tags == ["refusal_retry"]
    assert result.log == reference.log
    assert core_dump(rig.runner.bundle) == core_dump(clean.runner.bundle)


def test_classify_retry_request_has_note_in_the_same_message(registry, cfg, tmp_path):
    action = player_action_input(["end_turn"])
    rig, adapter = fight(registry, cfg, tmp_path, CLASSIFY_TOOLS, classify=[action])
    adapter.arm()
    rig.runner.play("Стою и жду")
    classify = [r for r in adapter.requests if tool_names(r) == CLASSIFY_TOOLS]
    assert notes_of(classify[0]) == []
    assert notes_of(classify[1]) == [SOFTEN_NOTE]


def test_refusal_on_narrate_of_numbered_turn_keeps_dice_and_round(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path / "a", narrate_names())
    clean, _ = fight(registry, cfg, tmp_path / "b", {"never"})
    adapter.arm()
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    reference = clean.runner.play(str(end_turn_number(clean.runner)))
    assert result.committed is True
    assert result.report_tags == ["refusal_retry"]
    assert result.log == reference.log
    assert result.lines == reference.lines
    assert rig.runner.bundle.session.active_combat.round == (
        clean.runner.bundle.session.active_combat.round
    )
    assert core_dump(rig.runner.bundle) == core_dump(clean.runner.bundle)


def test_numbered_turn_without_classify_gets_note_on_narrate(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path, narrate_names())
    adapter.arm()
    rig.runner.play(str(end_turn_number(rig.runner)))
    narrate = [r for r in adapter.requests if tool_names(r) == narrate_names()]
    assert notes_of(narrate[-2]) == []
    assert notes_of(narrate[-1]) == [SOFTEN_NOTE]


def test_refusal_on_npc_choice_retries_whole_turn(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path / "a", NPC_ONLY, grakh=True)
    clean, _ = fight(registry, cfg, tmp_path / "b", {"never"}, grakh=True)
    rig.runner.bundle.world.npcs["grakh"].creature.hp_current = 10
    clean.runner.bundle.world.npcs["grakh"].creature.hp_current = 10
    adapter.arm()
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    reference = clean.runner.play(str(end_turn_number(clean.runner)))
    assert result.committed is True
    assert result.report_tags == ["refusal_retry"]
    assert result.log == reference.log
    assert core_dump(rig.runner.bundle) == core_dump(clean.runner.bundle)


def test_double_refusal_in_combat_rolls_the_turn_back(registry, cfg, tmp_path):
    class Always(RefuseOnce):
        def complete(self, request):
            self.armed = True
            return super().complete(request)

    rig, _ = fight(registry, cfg, tmp_path, {"never"})
    rig.runner.adapter = Always(rig.runner.adapter, narrate_names())
    before = dump(rig)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.committed is False
    assert result.failure.reason == "refusal"
    assert dump(rig) == before
    assert rig.runner.note is None


# авторепорт (Q3а)

def issues(tmp_path, world_id="w1"):
    folder = tmp_path / world_id / "issues"
    return sorted(folder.iterdir()) if folder.exists() else []


def test_successful_retry_writes_auto_report(registry, tmp_path):
    app = make_app(
        registry, tmp_path, scripted([REFUSAL, text_step("Рассказ.")]), auto_reports=True
    )
    reply = app.handle("Иду")
    assert reply.turn.committed is True
    assert reply.turn.report_tags == ["refusal_retry"]
    assert len(issues(tmp_path)) == 1
    assert issues(tmp_path)[0].name.endswith("-refusal_retry")


def test_auto_report_off_writes_nothing_on_retry(registry, tmp_path):
    app = make_app(
        registry, tmp_path, scripted([REFUSAL, text_step("Рассказ.")]), auto_reports=False
    )
    app.handle("Иду")
    assert issues(tmp_path) == []


def test_double_refusal_report_has_both_tags(registry, tmp_path):
    import json

    app = make_app(registry, tmp_path, scripted([REFUSAL, REFUSAL]), auto_reports=True)
    reply = app.handle("Иду")
    assert reply.turn.committed is False
    assert len(issues(tmp_path)) == 1
    meta = json.loads((issues(tmp_path)[0] / "meta.json").read_text(encoding="utf-8"))
    assert meta["tags"] == ["refusal_retry", "refusal"]
    assert meta["status"] == "aborted"
    assert meta["failure_reason"] == "refusal"


# мок-адаптер из game_kit не отказывает сам: ReactiveAdapter остаётся без приписки

def test_reactive_turn_has_no_note(registry, cfg, tmp_path):
    adapter = ReactiveAdapter()
    make_rig(registry, cfg, tmp_path, adapter).runner.play("a")
    assert notes_of(adapter.requests[0]) == []


def test_combat_turn_calls_are_journaled_under_the_turn_run_id(registry, cfg, tmp_path):
    rig, adapter = fight(registry, cfg, tmp_path, narrate_names())
    start = len(rig.journal.read_records())
    adapter.arm()
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    records = rig.journal.read_records()[start:]
    assert len(records) == 2
    assert {r["run_id"] for r in records} == {result.run_id}
    assert {r["turn_status"] for r in records} == {"committed"}


def test_both_attempts_share_run_id_and_are_numbered_in_a_row(registry, cfg, tmp_path):
    rig = make_rig(registry, cfg, tmp_path, scripted([REFUSAL, text_step("Рассказ.")]))
    result = rig.runner.play("Иду")
    records = rig.journal.read_records()
    assert [r["run_id"] for r in records] == [result.run_id, result.run_id]
    assert [r["call_id"] for r in records] == [f"{result.run_id}-1", f"{result.run_id}-2"]
