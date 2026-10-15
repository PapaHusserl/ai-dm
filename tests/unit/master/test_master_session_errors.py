# Ожидаемый API: ai_dm.master.session (MasterSession, TurnFailed) -- контракт в master_kit.py.
# Ошибки 2.2: невалидные ответы (бюджет 2), раунды (8), refusal, max_tokens, сеть, fatal.
import json

import pytest
from master_kit import (
    flag_call,
    make_ctx,
    make_session,
    reject_all,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.llm.types import Text, ToolResult
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply

BAD_CHECK = {
    "id": "bad", "name": "skill_check",
    "input": {"type": "skill_check", "skill": "nope", "category": "medium", "stakes": "normal"},
}
GHOST_ITEM = {
    "id": "ghost", "name": "give_item",
    "input": {"type": "give_item", "item_id": "no_such_item", "qty": 1},
}


def run(steps, tmp_path, registry, cfg, executor=apply, mode="explore", **kw):
    adapter = scripted(steps)
    session, journal, ledger, sleeps = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg, mode=mode)
    return adapter, ctx, session, sleeps, lambda: session.run(ctx, "Иду.", executor, mode)


def failure_of(call):
    with pytest.raises(TurnFailed) as info:
        call()
    return info.value


# невалидные ответы

def test_invalid_schema_gives_error_tool_result(tmp_path, registry, cfg):
    adapter, _, _, _, go = run([tools_step(BAD_CHECK), text_step()], tmp_path, registry, cfg)
    go()
    block = adapter.requests[1].messages[-1].content[0]
    assert isinstance(block, ToolResult)
    assert block.call_id == "bad"
    assert block.is_error is True
    assert json.loads(block.content)["message"]


def test_unknown_item_from_executor_gives_error_tool_result_with_hint(tmp_path, registry, cfg):
    adapter, _, _, _, go = run([tools_step(GHOST_ITEM), text_step()], tmp_path, registry, cfg)
    result = go()
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert json.loads(block.content)["code"] == "unknown_item"
    assert result.invalid_count == 1
    assert result.decisions == []


def test_two_invalid_then_success(tmp_path, registry, cfg):
    steps = [tools_step(BAD_CHECK), tools_step(GHOST_ITEM), text_step("Всё хорошо.")]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.texts[-1] == "Всё хорошо."
    assert result.invalid_count == 2


def test_third_invalid_fails_with_invalid(tmp_path, registry, cfg):
    steps = [tools_step(BAD_CHECK), tools_step(GHOST_ITEM), tools_step(BAD_CHECK), text_step()]
    adapter, _, _, _, go = run(steps, tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "invalid"
    assert len(adapter.requests) == 3


def test_invalid_budget_comes_from_config(tmp_path, registry, cfg):
    from master_kit import app_cfg

    app = app_cfg().model_copy(deep=True)
    app.retry.invalid_retries = 0
    adapter, _, _, _, go = run(
        [tools_step(BAD_CHECK), text_step()], tmp_path, registry, cfg, app=app
    )
    assert failure_of(go).reason == "invalid"
    assert len(adapter.requests) == 1


def test_rejected_decision_does_not_spend_invalid_budget(tmp_path, registry, cfg):
    steps = [tools_step(flag_call(f"f{n}", f"c{n}")) for n in range(4)] + [text_step("Ок.")]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg, executor=reject_all)
    result = go()
    assert result.invalid_count == 0
    assert all(d.status == "rejected" for d in result.decisions)
    assert result.texts[-1] == "Ок."


def test_rejected_decision_result_is_not_an_error_for_the_model(tmp_path, registry, cfg):
    adapter, _, _, _, go = run(
        [tools_step(flag_call("a", "c1")), text_step()], tmp_path, registry, cfg,
        executor=reject_all,
    )
    go()
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is False
    assert json.loads(block.content)["status"] == "rejected"


def test_rejected_between_invalid_does_not_reset_or_add(tmp_path, registry, cfg):
    # два невалидных и сколько угодно отказов не ломают ход
    rejected = tools_step(flag_call("a", "c9"))
    steps = [tools_step(BAD_CHECK), rejected, tools_step(GHOST_ITEM), rejected, text_step()]

    def executor(ctx, request):
        if request.type == "set_flag":
            return reject_all(ctx, request)
        return apply(ctx, request)

    _, _, _, _, go = run(steps, tmp_path, registry, cfg, executor=executor)
    assert go().invalid_count == 2


# раунды

def test_eight_rounds_then_text_is_ok(tmp_path, registry, cfg):
    steps = [tools_step(flag_call(f"f{n}", f"c{n}")) for n in range(8)] + [text_step("Конец.")]
    adapter, _, _, _, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.rounds == 8
    assert len(adapter.requests) == 9
    assert result.texts[-1] == "Конец."


def test_ninth_round_fails_with_rounds(tmp_path, registry, cfg):
    steps = [tools_step(flag_call(f"f{n}", f"c{n}")) for n in range(12)] + [text_step()]
    adapter, _, _, _, go = run(steps, tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "rounds"
    assert len(adapter.requests) <= 9


def test_round_limit_comes_from_config(tmp_path, registry, cfg):
    from master_kit import app_cfg

    app = app_cfg().model_copy(deep=True)
    app.retry.max_tool_rounds = 2
    steps = [tools_step(flag_call(f"f{n}", f"c{n}")) for n in range(3)] + [text_step()]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg, app=app)
    assert failure_of(go).reason == "rounds"


# отказ и max_tokens

def test_refusal_fails_with_refusal_and_tag(tmp_path, registry, cfg):
    _, _, _, _, go = run([{"stop": "refusal"}], tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "refusal"
    assert error.report_tags == ["refusal"]


def test_refusal_after_tool_round_is_still_refusal(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), {"stop": "refusal", "text": "Не могу."}]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    assert failure_of(go).reason == "refusal"


def test_refusal_is_not_retried(tmp_path, registry, cfg):
    adapter, _, _, _, go = run([{"stop": "refusal"}, text_step()], tmp_path, registry, cfg)
    failure_of(go)
    assert len(adapter.requests) == 1


def test_max_tokens_is_invalid_with_explanation_to_shorten(tmp_path, registry, cfg):
    steps = [{"stop": "max_tokens", "text": "Очень длинный рассказ, который оборвался"},
             text_step("Коротко.")]
    adapter, _, _, _, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.invalid_count == 1
    assert result.texts[-1] == "Коротко."
    second = adapter.requests[1]
    assert second.messages[-2].role == "assistant"
    note = second.messages[-1]
    assert note.role == "user"
    assert "короче" in " ".join(b.text for b in note.content if isinstance(b, Text)).lower()


def test_max_tokens_spends_invalid_budget(tmp_path, registry, cfg):
    steps = [{"stop": "max_tokens", "text": "а"}] * 3 + [text_step()]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    assert failure_of(go).reason == "invalid"


# сеть и fatal

TRANSIENT = {"error": "transient", "message": "сеть недоступна"}


def test_network_three_retries_then_success(tmp_path, registry, cfg):
    steps = [TRANSIENT, TRANSIENT, TRANSIENT, text_step("Дошло.")]
    adapter, _, _, sleeps, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.texts == ["Дошло."]
    assert sleeps == [1, 3, 10]
    assert len(adapter.requests) == 4


def test_network_exhausted_gives_network_failure(tmp_path, registry, cfg):
    steps = [TRANSIENT] * 4 + [text_step()]
    adapter, _, _, sleeps, go = run(steps, tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "network"
    assert sleeps == [1, 3, 10]
    assert len(adapter.requests) == 4


def test_network_error_after_tool_round_is_network_failure(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1"))] + [TRANSIENT] * 4
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    assert failure_of(go).reason == "network"


def test_retry_after_is_respected_through_sleeper(tmp_path, registry, cfg):
    steps = [{"error": "transient", "message": "лимит", "retry_after": 7}, text_step()]
    _, _, _, sleeps, go = run(steps, tmp_path, registry, cfg)
    go()
    assert sleeps == [7]


def test_fatal_gives_fatal_failure_without_retries(tmp_path, registry, cfg):
    steps = [{"error": "fatal", "message": "плохой ключ"}, text_step()]
    adapter, _, _, sleeps, go = run(steps, tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "fatal"
    assert sleeps == []
    assert len(adapter.requests) == 1


def test_turn_failed_has_message(tmp_path, registry, cfg):
    _, _, _, _, go = run([{"error": "fatal", "message": "плохой ключ"}], tmp_path, registry, cfg)
    assert str(failure_of(go))


# B1: max_tokens вместе с tool_use

def test_max_tokens_with_tool_calls_gives_error_result_for_each_call(tmp_path, registry, cfg):
    cut = tools_step(flag_call("a", "c1"), flag_call("b", "c2"), stop="max_tokens")
    adapter, _, _, _, go = run([cut, text_step("Коротко.")], tmp_path, registry, cfg)
    go()
    answer = adapter.requests[1].messages[-1]
    assert answer.role == "user"
    results = [b for b in answer.content if isinstance(b, ToolResult)]
    assert [b.call_id for b in results] == ["c1", "c2"]
    assert all(b.is_error for b in results)


def test_max_tokens_with_tool_calls_does_not_run_executor(tmp_path, registry, cfg):
    called = []

    def executor(ctx, request):
        called.append(request)
        return apply(ctx, request)

    cut = tools_step(flag_call("a", "c1"), stop="max_tokens")
    _, ctx, _, _, go = run([cut, text_step()], tmp_path, registry, cfg, executor=executor)
    result = go()
    assert called == []
    assert "a" not in ctx.bundle.world.flags
    assert result.decisions == []
    assert result.requests == []


def test_max_tokens_with_tool_calls_spends_one_invalid(tmp_path, registry, cfg):
    cut = tools_step(flag_call("a", "c1"), flag_call("b", "c2"), stop="max_tokens")
    _, _, _, _, go = run([cut, text_step()], tmp_path, registry, cfg)
    assert go().invalid_count == 1


def test_max_tokens_with_tool_calls_has_shorten_text_as_last_block(tmp_path, registry, cfg):
    cut = tools_step(flag_call("a", "c1"), stop="max_tokens")
    adapter, _, _, _, go = run([cut, text_step()], tmp_path, registry, cfg)
    go()
    answer = adapter.requests[1].messages[-1]
    assert isinstance(answer.content[-1], Text)
    assert "короче" in answer.content[-1].text.lower()
    assert adapter.requests[1].messages[-2].role == "assistant"


# B2: имя инструмента и type во входе

def mismatch_call():
    return {
        "id": "m1", "name": "skill_check",
        "input": {"type": "set_flag", "name": "x", "value": "true"},
    }


def test_name_and_type_mismatch_is_invalid_and_not_executed(tmp_path, registry, cfg):
    called = []

    def executor(ctx, request):
        called.append(request)
        return apply(ctx, request)

    adapter, ctx, _, _, go = run(
        [tools_step(mismatch_call()), text_step()], tmp_path, registry, cfg, executor=executor
    )
    result = go()
    block = adapter.requests[1].messages[-1].content[0]
    assert block.is_error is True
    assert json.loads(block.content)["code"] == "invalid_request"
    assert called == []
    assert "x" not in ctx.bundle.world.flags
    assert result.requests == []
    assert result.invalid_count == 1


def test_missing_type_in_input_is_taken_from_tool_name(tmp_path, registry, cfg):
    # живой прогон: Gemini flash-lite опускал поле type -- тип однозначно задан именем инструмента
    call = {"id": "m2", "name": "set_flag", "input": {"name": "x", "value": "true"}}
    adapter, ctx, _, _, go = run([tools_step(call), text_step()], tmp_path, registry, cfg)
    go()
    assert adapter.requests[1].messages[-1].content[0].is_error is False
    assert "x" in ctx.bundle.world.flags


def test_name_and_type_mismatch_is_invalid_with_strict_tools_off(tmp_path, registry, cfg):
    from ai_dm.config.app import load_settings

    app = load_settings("[llm]\nstrict_tools = false\n").app
    adapter, ctx, _, _, go = run(
        [tools_step(mismatch_call()), text_step()], tmp_path, registry, cfg, app=app
    )
    result = go()
    assert adapter.requests[1].messages[-1].content[0].is_error is True
    assert "x" not in ctx.bundle.world.flags
    assert result.requests == []


def test_mismatch_does_not_block_other_calls_of_the_response(tmp_path, registry, cfg):
    steps = [tools_step(mismatch_call(), flag_call("ok", "c2")), text_step()]
    adapter, ctx, _, _, go = run(steps, tmp_path, registry, cfg)
    go()
    answer = adapter.requests[1].messages[-1]
    assert [b.is_error for b in answer.content] == [True, False]
    assert ctx.bundle.world.flags["ok"] is True


# бюджет: два Invalid в одном ответе -- одна единица

def test_two_invalid_in_one_response_spend_one_budget_unit(tmp_path, registry, cfg):
    steps = [tools_step(BAD_CHECK, GHOST_ITEM), text_step("Ок.")]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    assert go().invalid_count == 1


def test_two_invalid_in_one_response_then_one_more_invalid_is_still_ok(tmp_path, registry, cfg):
    steps = [tools_step(BAD_CHECK, GHOST_ITEM), tools_step(BAD_CHECK), text_step("Ок.")]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.invalid_count == 2
    assert result.texts[-1] == "Ок."


# К0-фикс (Q7): сырой повод отказа попадает в сообщение игроку

def refusal_with_detail(detail, tmp_path, registry, cfg):
    adapter = scripted([{"stop": "refusal"}])
    complete = adapter.complete

    def with_detail(req):
        response = complete(req)
        response.stop_detail = detail
        return response

    adapter.complete = with_detail
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    return failure_of(lambda: session.run(ctx, "Иду.", apply, "explore"))


def test_refusal_message_names_the_detail(tmp_path, registry, cfg):
    error = refusal_with_detail("SAFETY", tmp_path, registry, cfg)
    assert error.reason == "refusal"
    assert "(SAFETY)" in str(error)
    assert error.report_tags == ["refusal"]


def test_refusal_message_names_prohibited_content(tmp_path, registry, cfg):
    error = refusal_with_detail("PROHIBITED_CONTENT", tmp_path, registry, cfg)
    assert "(PROHIBITED_CONTENT)" in str(error)


def test_refusal_message_without_detail_is_plain(tmp_path, registry, cfg):
    _, _, _, _, go = run([{"stop": "refusal"}], tmp_path, registry, cfg)
    assert str(failure_of(go)) == "Модель отказалась отвечать."


# Т3 (мини-партия #18): текст раунда с invalid сохраняется, бюджет invalid прежний

def test_third_invalid_after_saved_text_still_fails_with_invalid(tmp_path, registry, cfg):
    steps = [
        tools_step(BAD_CHECK, text="Сцена."), tools_step(GHOST_ITEM), tools_step(BAD_CHECK),
        text_step(),
    ]
    adapter, _, _, _, go = run(steps, tmp_path, registry, cfg)
    error = failure_of(go)
    assert error.reason == "invalid"
    assert len(adapter.requests) == 3


def test_text_with_invalid_call_does_not_spend_extra_budget(tmp_path, registry, cfg):
    steps = [tools_step(BAD_CHECK, text="Сцена."), tools_step(GHOST_ITEM), text_step("Итог.")]
    _, _, _, _, go = run(steps, tmp_path, registry, cfg)
    result = go()
    assert result.invalid_count == 2
    assert result.texts == ["Сцена.", "Итог."]
