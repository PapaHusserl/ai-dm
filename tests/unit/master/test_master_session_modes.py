# Ожидаемый API: ai_dm.master.session.MasterSession.run(..., mode) -- контракт в master_kit.py.
# Режимы: набор инструментов tool_set(mode), обязательные инструменты, чужой инструмент.
import contextlib
import json

import pytest
from master_kit import (
    Recorder,
    accept_all,
    combat_ctx,
    flag_call,
    make_ctx,
    make_session,
    player_action_call,
    reject_all,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.llm.types import Text, ToolResult
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply
from ai_dm.protocol.schema import tool_set

NPC_CALL = {
    "id": "n1", "name": "npc_action", "input": {"type": "npc_action", "choice": "end_turn"},
}
DEFEAT_CALL = {
    "id": "d1", "name": "defeat_outcome",
    "input": {"type": "defeat_outcome", "consequences": ["left_to_die"]},
}
OFFER_CALL = {
    "id": "o1", "name": "offer_choices",
    "input": {"type": "offer_choices", "choices": ["Бежать", "Драться"]},
}


EMPTY = {"text": ""}


class EmptyAnswers(Recorder):
    # ScriptedAdapter пустой content не умеет: шаг {"text": ""} превращаем в ответ без блоков
    def complete(self, request):
        response = super().complete(request)
        if [b for b in response.content if isinstance(b, Text) and b.text == ""]:
            response = response.model_copy(update={"content": []})
        return response


def run(steps, tmp_path, ctx, executor, mode, **kw):
    adapter = scripted(steps)
    if EMPTY in steps:
        adapter = EmptyAnswers(adapter.inner)
    session, _, _, _ = make_session(adapter, tmp_path, **kw)
    return adapter, lambda: session.run(ctx, "Действую.", executor, mode)


def texts_of(message):
    return " ".join(b.text for b in message.content if isinstance(b, Text))


# наборы инструментов

@pytest.mark.parametrize("mode", ["explore", "combat_classify", "combat_narrate", "npc_choice"])
def test_request_tools_are_tool_set_of_mode(tmp_path, registry, cfg, mode):
    ctx = make_ctx(registry, cfg, mode=mode, npc_options=["end_turn"])
    # ответ без обязательного инструмента здесь не важен: смотрим только первый запрос
    adapter, go = run([text_step()] * 3, tmp_path, ctx, accept_all, mode)
    with contextlib.suppress(TurnFailed):
        go()
    assert [t.name for t in adapter.requests[0].tools] == [d["name"] for d in tool_set(mode)]


def test_explore_needs_no_required_tool(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    _, go = run([text_step("Просто рассказ.")], tmp_path, ctx, apply, "explore")
    assert go().texts == ["Просто рассказ."]


# combat_classify: обязателен player_action

def test_classify_with_player_action_is_ok(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    _, go = run(
        [tools_step(player_action_call()), text_step("Принято.")], tmp_path, ctx, apply,
        "combat_classify",
    )
    result = go()
    assert result.requests[0].type == "player_action"
    assert result.decisions[0].result["steps"] == ["attack:longsword:g1"]


def test_classify_text_without_player_action_is_invalid_with_hint(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    steps = [text_step("Герой бьёт."), tools_step(player_action_call()), text_step()]
    adapter, go = run(steps, tmp_path, ctx, apply, "combat_classify")
    result = go()
    assert result.invalid_count == 1
    note = adapter.requests[1].messages[-1]
    assert note.role == "user"
    assert "player_action" in texts_of(note)
    assert adapter.requests[1].messages[-2].role == "assistant"


def test_classify_never_calls_player_action_fails_with_invalid(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    _, go = run([text_step()] * 3, tmp_path, ctx, apply, "combat_classify")
    with pytest.raises(TurnFailed) as info:
        go()
    assert info.value.reason == "invalid"


def test_classify_rejected_player_action_does_not_count_as_called(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    steps = [tools_step(player_action_call()), text_step("Ну вот."), text_step("Ещё."), text_step()]
    _, go = run(steps, tmp_path, ctx, reject_all, "combat_classify")
    # отказ -- не вызов: текст после него невалиден, три невалидных подряд -- провал
    with pytest.raises(TurnFailed) as info:
        go()
    assert info.value.reason == "invalid"


def test_classify_unsupported_action_alone_is_not_enough(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    unsupported = {
        "id": "u1", "name": "unsupported_action",
        "input": {"type": "unsupported_action", "description": "укусить луну"},
    }
    steps = [tools_step(unsupported), text_step("Не умею."), tools_step(player_action_call()),
             text_step("Теперь да.")]
    _, go = run(steps, tmp_path, ctx, apply, "combat_classify")
    result = go()
    assert result.invalid_count == 1
    assert "missing-mechanic" in result.report_tags


# combat_narrate: defeat_outcome при defeat_pending

def test_narrate_without_defeat_pending_needs_no_tool(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome=None)
    _, go = run([text_step("Бой идёт.")], tmp_path, ctx, apply, "combat_narrate")
    assert go().texts == ["Бой идёт."]


def test_narrate_victory_needs_no_tool(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="victory")
    _, go = run([text_step("Победа.")], tmp_path, ctx, apply, "combat_narrate")
    assert go().texts == ["Победа."]


def test_narrate_defeat_pending_text_only_is_invalid_with_hint(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="defeat_pending")
    steps = [text_step("Герой падает."), tools_step(DEFEAT_CALL), text_step("Тьма.")]
    adapter, go = run(steps, tmp_path, ctx, accept_all, "combat_narrate")
    result = go()
    assert result.invalid_count == 1
    assert "defeat_outcome" in texts_of(adapter.requests[1].messages[-1])
    assert result.requests[0].type == "defeat_outcome"


def test_narrate_defeat_pending_without_outcome_fails(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="defeat_pending")
    _, go = run([text_step()] * 3, tmp_path, ctx, accept_all, "combat_narrate")
    with pytest.raises(TurnFailed) as info:
        go()
    assert info.value.reason == "invalid"


def test_narrate_offer_choices_is_allowed(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="victory")
    _, go = run([tools_step(OFFER_CALL), text_step("Что дальше?")], tmp_path, ctx, apply,
                "combat_narrate")
    assert go().requests[0].type == "offer_choices"
    assert ctx.bundle.session.offered_choices == ["Бежать", "Драться"]


# npc_choice: обязателен npc_action

def npc_ctx(registry, cfg):
    return make_ctx(registry, cfg, mode="npc_choice", npc_options=["end_turn", "attack"])


def test_npc_choice_with_npc_action_is_ok(tmp_path, registry, cfg):
    ctx = npc_ctx(registry, cfg)
    _, go = run([tools_step(NPC_CALL), text_step()], tmp_path, ctx, apply, "npc_choice")
    result = go()
    assert result.decisions[0].result["choice"] == "end_turn"


def test_npc_choice_text_only_is_invalid(tmp_path, registry, cfg):
    ctx = npc_ctx(registry, cfg)
    steps = [text_step("Гоблин думает."), tools_step(NPC_CALL), text_step()]
    adapter, go = run(steps, tmp_path, ctx, apply, "npc_choice")
    result = go()
    assert result.invalid_count == 1
    assert "npc_action" in texts_of(adapter.requests[1].messages[-1])


def test_npc_choice_three_times_without_action_fails(tmp_path, registry, cfg):
    ctx = npc_ctx(registry, cfg)
    _, go = run([text_step()] * 3, tmp_path, ctx, apply, "npc_choice")
    with pytest.raises(TurnFailed) as info:
        go()
    assert info.value.reason == "invalid"


def test_npc_choice_unknown_option_is_invalid_result(tmp_path, registry, cfg):
    ctx = npc_ctx(registry, cfg)
    wrong = {"id": "n0", "name": "npc_action", "input": {"type": "npc_action", "choice": "fly"}}
    steps = [tools_step(wrong), tools_step(NPC_CALL), text_step()]
    adapter, go = run(steps, tmp_path, ctx, apply, "npc_choice")
    go()
    assert adapter.requests[1].messages[-1].content[0].is_error is True


# инструмент не из набора режима

def test_tool_outside_mode_set_is_invalid_not_available(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    steps = [tools_step(player_action_call("p1")), text_step("Ладно.")]
    called = []

    def executor(ctx, request):
        called.append(request)
        return accept_all(ctx, request)

    adapter, go = run(steps, tmp_path, ctx, executor, "explore")
    result = go()
    block = adapter.requests[1].messages[-1].content[0]
    assert isinstance(block, ToolResult)
    assert block.is_error is True
    assert "в этом режиме недоступно" in json.loads(block.content)["message"]
    assert called == []
    assert result.invalid_count == 1


def test_explore_tool_in_combat_narrate_is_not_available(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="victory")
    steps = [tools_step(flag_call("a", "c1")), text_step()]
    adapter, go = run(steps, tmp_path, ctx, accept_all, "combat_narrate")
    go()
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert "в этом режиме недоступно" in json.loads(block.content)["message"]


def test_hidden_tool_in_explore_is_invalid(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    hidden = {
        "id": "h1", "name": "afterlife_action",
        "input": {"type": "afterlife_action", "kind": "short"},
    }
    adapter, go = run([tools_step(hidden), text_step()], tmp_path, ctx, apply, "explore")
    go()
    assert adapter.requests[1].messages[-1].content[0].is_error is True


def test_one_bad_call_among_good_ones_still_one_user_message(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    steps = [tools_step(flag_call("a", "c1"), player_action_call("c2"), flag_call("b", "c3")),
             text_step()]
    adapter, go = run(steps, tmp_path, ctx, apply, "explore")
    go()
    answer = adapter.requests[1].messages[-1]
    assert [b.call_id for b in answer.content] == ["c1", "c2", "c3"]
    assert [b.is_error for b in answer.content] == [False, True, False]


# D5: пустой ответ после выполненного обязательного инструмента

def test_empty_answer_after_accepted_player_action_is_success(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    steps = [tools_step(player_action_call()), EMPTY]
    adapter, go = run(steps, tmp_path, ctx, apply, "combat_classify")
    result = go()
    assert result.invalid_count == 0
    assert len(adapter.requests) == 2
    assert result.decisions[0].status == "accepted"


def test_empty_answer_after_accepted_npc_action_is_success(tmp_path, registry, cfg):
    ctx = npc_ctx(registry, cfg)
    _, go = run([tools_step(NPC_CALL), EMPTY], tmp_path, ctx, apply, "npc_choice")
    assert go().invalid_count == 0


def test_empty_answer_without_required_done_still_spends_budget(tmp_path, registry, cfg):
    ctx = combat_ctx(registry, cfg, "combat_classify")
    _, go = run(
        [EMPTY, tools_step(player_action_call()), text_step()], tmp_path, ctx, apply,
        "combat_classify",
    )
    assert go().invalid_count == 1


def test_empty_answer_in_explore_is_still_invalid(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    _, go = run([EMPTY, text_step("Рассказ.")], tmp_path, ctx, apply, "explore")
    assert go().invalid_count == 1


# L2: пустой финал после рассказа при инструменте принимается без повтора

def test_empty_final_after_narration_with_tool_in_explore_is_success(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    steps = [tools_step(flag_call("a", "c1"), text="Ты входишь в зал."), EMPTY]
    adapter, go = run(steps, tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 0
    assert len(adapter.requests) == 2
    assert result.narration == "Ты входишь в зал."


def test_whitespace_final_after_narration_with_tool_is_success(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    steps = [tools_step(flag_call("a", "c1"), text="Ты входишь в зал."), {"text": "  \n "}]
    adapter, go = run(steps, tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 0
    assert len(adapter.requests) == 2
    assert result.narration == "Ты входишь в зал."


def test_narration_with_offer_in_combat_narrate_is_success_without_final_call(
    tmp_path, registry, cfg
):
    # Б1-фикс п.1: текст + offer_choices -- завершающий вызов не нужен (раньше было 2 запроса)
    ctx = combat_ctx(registry, cfg, "combat_narrate")
    steps = [tools_step(OFFER_CALL, text="Меч свистит."), EMPTY]
    adapter, go = run(steps, tmp_path, ctx, apply, "combat_narrate")
    result = go()
    assert result.invalid_count == 0
    assert len(adapter.requests) == 1
    assert result.narration == "Меч свистит."


def test_empty_final_after_tool_without_narration_still_retries(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    steps = [tools_step(flag_call("a", "c1")), EMPTY, text_step("Рассказ.")]
    adapter, go = run(steps, tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 1
    assert len(adapter.requests) == 3
    assert result.narration == "Рассказ."


def test_narration_with_invalid_round_excuses_empty_final(tmp_path, registry, cfg):
    # Т3: текст раунда с Invalid-вызовом принят -- пустой финал не повторяется
    ctx = make_ctx(registry, cfg)
    bad = {"id": "b1", "name": "set_flag", "input": {"type": "wrong"}}
    steps = [tools_step(bad, text="Принятый рассказ."), EMPTY, text_step("лишний")]
    adapter, go = run(steps, tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 1
    assert len(adapter.requests) == 2
    assert result.narration == "Принятый рассказ."


def test_invalid_round_without_text_does_not_excuse_empty_final(tmp_path, registry, cfg):
    ctx = make_ctx(registry, cfg)
    bad = {"id": "b1", "name": "set_flag", "input": {"type": "wrong"}}
    steps = [tools_step(bad), EMPTY, text_step("Рассказ.")]
    _, go = run(steps, tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 2
    assert result.narration == "Рассказ."


def test_whitespace_only_text_block_counts_as_empty_answer(tmp_path, registry, cfg):
    # ответ из одного пустого/пробельного текстового блока — тоже пустой ответ (без EmptyAnswers)
    ctx = make_ctx(registry, cfg)
    _, go = run([{"text": "   "}, text_step("Рассказ.")], tmp_path, ctx, apply, "explore")
    result = go()
    assert result.invalid_count == 1
    assert result.narration == "Рассказ."
