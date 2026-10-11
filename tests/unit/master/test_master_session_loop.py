# Ожидаемый API: ai_dm.master.session.MasterSession.run -- контракт в master_kit.py.
# Цикл инструментов на ScriptedAdapter: текст, tool_use -> tool_result, несколько вызовов,
# история внутри хода (в том числе Opaque), сценарий из YAML.
import json
from pathlib import Path

from master_kit import (
    Recorder,
    accept_all,
    flag_call,
    make_ctx,
    make_session,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.llm.types import ChatResponse, Message, Opaque, Text, ToolCall, ToolResult, Usage
from ai_dm.master.session import MasterResult
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision
from ai_dm.protocol.render import render_tool_result

SCRIPTS = Path(__file__).resolve().parents[2] / "fixtures" / "scripts"


def run(adapter, tmp_path, registry, cfg, executor=apply, mode="explore", text="Иду.", **kw):
    session, _, _, _ = make_session(adapter, tmp_path, **kw)
    ctx = make_ctx(registry, cfg, mode=mode)
    return session.run(ctx, text, executor, mode), ctx


def test_text_answer_gives_result_with_text(tmp_path, registry, cfg):
    result, _ = run(scripted([text_step("Ветер шумит.")]), tmp_path, registry, cfg)
    assert isinstance(result, MasterResult)
    assert result.texts == ["Ветер шумит."]
    assert result.stop_reason == "end_turn"


def test_text_answer_makes_one_call_and_no_decisions(tmp_path, registry, cfg):
    adapter = scripted([text_step()])
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1
    assert result.decisions == []
    assert result.rounds == 0
    assert result.report_tags == []


def test_first_request_is_built_by_prompt_builder(tmp_path, registry, cfg):
    adapter = scripted([text_step()])
    run(adapter, tmp_path, registry, cfg, text="Привет, стражник")
    request = adapter.requests[0]
    assert request.role == "narrator"
    assert [b.cache for b in request.system] == [True, True, True]
    assert "Привет, стражник" in request.messages[0].content[0].text
    assert [t.name for t in request.tools] == sorted(t.name for t in request.tools)


def test_tool_use_goes_to_executor_and_result_comes_back(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1")), text_step("Готово.")])
    result, ctx = run(adapter, tmp_path, registry, cfg)
    assert ctx.bundle.world.flags["met"] is True
    assert len(adapter.requests) == 2
    assert result.texts[-1] == "Готово."
    assert result.rounds == 1
    assert len(result.decisions) == 1
    assert result.decisions[0].status == "accepted"
    assert result.requests[0].type == "set_flag"


def test_second_request_has_assistant_call_and_tool_result(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1")), text_step()])
    run(adapter, tmp_path, registry, cfg)
    first, second = adapter.requests
    assert second.messages[: len(first.messages)] == first.messages
    assert len(second.messages) == len(first.messages) + 2
    assistant, answer = second.messages[-2:]
    assert assistant.role == "assistant"
    assert isinstance(assistant.content[0], ToolCall)
    assert assistant.content[0].id == "c1"
    assert answer.role == "user"
    assert len(answer.content) == 1
    assert isinstance(answer.content[0], ToolResult)
    assert answer.content[0].call_id == "c1"
    assert answer.content[0].is_error is False


def test_tool_result_content_is_rendered_decision(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1")), text_step()])
    result, _ = run(adapter, tmp_path, registry, cfg)
    block = adapter.requests[1].messages[-1].content[0]
    assert block.content == render_tool_result(result.decisions[0])["content"]
    assert json.loads(block.content)["status"] == "accepted"


def test_tools_and_system_are_the_same_in_all_requests(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("a", "c1")), text_step()])
    run(adapter, tmp_path, registry, cfg)
    first, second = adapter.requests
    assert first.tools == second.tools
    assert first.system == second.system


def test_several_tool_calls_give_one_user_message_in_order(tmp_path, registry, cfg):
    calls = [flag_call("a", "c1"), flag_call("b", "c2"), flag_call("c", "c3")]
    adapter = scripted([tools_step(*calls), text_step()])
    result, ctx = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    answer = adapter.requests[1].messages[-1]
    assert answer.role == "user"
    assert [b.call_id for b in answer.content] == ["c1", "c2", "c3"]
    assert all(isinstance(b, ToolResult) for b in answer.content)
    assert [r.name for r in result.requests] == ["a", "b", "c"]
    assert set(ctx.bundle.world.flags) == {"a", "b", "c"}
    assert result.rounds == 1


def test_text_before_tool_calls_is_kept_in_texts(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1"), text="Сейчас проверю."), text_step("Итог.")]
    result, _ = run(scripted(steps), tmp_path, registry, cfg)
    assert result.texts == ["Сейчас проверю.", "Итог."]


def test_text_before_tool_calls_stays_in_assistant_message(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1"), text="Сейчас проверю."), text_step()]
    adapter = scripted(steps)
    run(adapter, tmp_path, registry, cfg)
    assistant = adapter.requests[1].messages[-2]
    assert assistant.content[0] == Text(text="Сейчас проверю.")
    assert isinstance(assistant.content[1], ToolCall)


def test_decision_report_tags_are_collected(tmp_path, registry, cfg):
    call = {
        "id": "u1", "name": "unsupported_action",
        "input": {"type": "unsupported_action", "description": "приручить дракона"},
    }
    result, ctx = run(scripted([tools_step(call), text_step()]), tmp_path, registry, cfg)
    assert result.report_tags == ["missing-mechanic"]
    assert "missing-mechanic" in ctx.marks


def test_clamped_decision_tag_limit_exceeded(tmp_path, registry, cfg):
    call = {
        "id": "g1", "name": "give_item",
        "input": {"type": "give_item", "item_id": "crowbar", "qty": 500},
    }
    result, _ = run(scripted([tools_step(call), text_step()]), tmp_path, registry, cfg)
    assert result.decisions[0].status == "clamped"
    assert result.report_tags == ["limit-exceeded"]


def test_invalid_death_tag_is_collected(tmp_path, registry, cfg):
    call = {
        "id": "n1", "name": "npc_update",
        "input": {"type": "npc_update", "npc_id": "aldric", "status": "dead", "cause": "chance"},
    }
    result, _ = run(scripted([tools_step(call), text_step()]), tmp_path, registry, cfg)
    assert result.decisions[0].status == "rejected"
    assert result.report_tags == ["invalid-death"]


def test_skill_check_result_has_roll_line_for_the_model(tmp_path, registry, cfg):
    call = {
        "id": "k1", "name": "skill_check",
        "input": {
            "type": "skill_check", "skill": "persuasion", "category": "medium",
            "stakes": "normal",
        },
    }
    adapter = scripted([tools_step(call), text_step()])
    result, ctx = run(adapter, tmp_path, registry, cfg)
    data = json.loads(adapter.requests[1].messages[-1].content[0].content)
    assert data["result"]["dc"] == 15
    assert data["log"]
    assert ctx.rolls
    assert result.decisions[0].result["dc"] == 15


def test_executor_gets_ctx_and_parsed_request(tmp_path, registry, cfg):
    seen = []

    def executor(ctx, request):
        seen.append((ctx, request))
        return accept_all(ctx, request)

    adapter = scripted([tools_step(flag_call("x", "c1")), text_step()])
    result, ctx = run(adapter, tmp_path, registry, cfg, executor=executor)
    assert seen[0][0] is ctx
    assert seen[0][1].type == "set_flag"
    assert seen[0][1].name == "x"
    assert isinstance(result.decisions[0], Decision)


# история внутри хода

def history_of(adapter):
    return [r.messages for r in adapter.requests]


def test_history_only_grows_and_earlier_messages_are_untouched(tmp_path, registry, cfg):
    steps = [
        tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")),
        tools_step(flag_call("c", "c3")), text_step(),
    ]
    adapter = scripted(steps)
    run(adapter, tmp_path, registry, cfg)
    histories = history_of(adapter)
    assert [len(h) for h in histories] == [1, 3, 5, 7]
    for earlier, later in zip(histories, histories[1:], strict=False):
        assert later[: len(earlier)] == earlier


def test_assistant_content_is_the_response_content_unchanged(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1"), text="Начало."), text_step()]
    inner = ScriptedAdapter(steps, provider="anthropic", model="claude-opus-5-5")
    adapter = Recorder(inner)
    run(adapter, tmp_path, registry, cfg)
    sent = adapter.requests[1].messages[-2]
    assert sent.role == "assistant"
    call = ToolCall(**flag_call("a", "c1"))
    assert sent.content == [Text(text="Начало."), call]


class OpaqueAdapter:
    # адаптер с блоками мышления: ScriptedAdapter Opaque не умеет
    def __init__(self):
        self.requests = []
        self.thinking = Opaque(
            provider="anthropic", raw={"type": "thinking", "thinking": "...", "signature": "AbC=="}
        )

    def info(self):
        from ai_dm.llm.adapter import AdapterInfo

        return AdapterInfo(provider="anthropic", model="claude-opus-5-5")

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        if len(self.requests) == 1:
            call = ToolCall(id="c1", name="set_flag", input={
                "type": "set_flag", "name": "a", "value": "true"})
            return ChatResponse(
                content=[self.thinking, call], stop_reason="tool_use", usage=Usage(),
                request_id="r1", model="claude-opus-5-5",
            )
        return ChatResponse(
            content=[Text(text="Конец.")], stop_reason="end_turn", usage=Usage(),
            request_id="r2", model="claude-opus-5-5",
        )


def test_opaque_blocks_are_returned_as_is(tmp_path, registry, cfg):
    adapter = OpaqueAdapter()
    run(adapter, tmp_path, registry, cfg)
    assistant = adapter.requests[1].messages[-2]
    assert assistant.content[0] == adapter.thinking
    assert isinstance(assistant.content[0], Opaque)
    assert assistant.content[0].raw["signature"] == "AbC=="


def test_opaque_is_not_in_texts(tmp_path, registry, cfg):
    result, _ = run(OpaqueAdapter(), tmp_path, registry, cfg)
    assert result.texts == ["Конец."]


def test_messages_are_message_objects(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("a", "c1")), text_step()])
    run(adapter, tmp_path, registry, cfg)
    assert all(isinstance(m, Message) for m in adapter.requests[1].messages)


# YAML-сценарий

def test_yaml_script_set_flag_then_text(tmp_path, registry, cfg):
    adapter = Recorder(ScriptedAdapter.from_yaml(SCRIPTS / "master_tool_loop.yaml"))
    result, ctx = run(adapter, tmp_path, registry, cfg)
    assert ctx.bundle.world.flags["met_guard"] is True
    assert result.texts[-1] == "Стражник кивает вам."


# D4: texts и narration только из принятых ответов

def test_narration_is_text_of_final_answer(tmp_path, registry, cfg):
    result, _ = run(scripted([text_step("Ветер шумит.")]), tmp_path, registry, cfg)
    assert result.narration == "Ветер шумит."


def test_narration_includes_text_written_alongside_tools(tmp_path, registry, cfg):
    # живой прогон: модель пишет рассказ в ответе с вызовом инструмента, финал короткий
    steps = [tools_step(flag_call("a", "c1"), text="Сцена в таверне."), text_step("Итог.")]
    result, _ = run(scripted(steps), tmp_path, registry, cfg)
    assert result.narration == "Сцена в таверне.\n\nИтог."


def test_rejected_max_tokens_text_is_not_in_texts_and_narration(tmp_path, registry, cfg):
    steps = [{"stop": "max_tokens", "text": "Длинный обрывок"}, text_step("Коротко.")]
    result, _ = run(scripted(steps), tmp_path, registry, cfg)
    assert result.texts == ["Коротко."]
    assert result.narration == "Коротко."


def test_text_without_required_tool_is_not_in_texts(tmp_path, registry, cfg):
    from master_kit import combat_ctx, player_action_call

    ctx = combat_ctx(registry, cfg, "combat_classify")
    steps = [text_step("Болтовня."), tools_step(player_action_call()), text_step("Принято.")]
    session, _, _, _ = make_session(scripted(steps), tmp_path)
    result = session.run(ctx, "Бью.", apply, "combat_classify")
    assert result.texts == ["Принято."]
    assert result.narration == "Принято."


# D1: world_text

def test_run_passes_world_text_to_system_1(tmp_path, registry, cfg):
    adapter = scripted([text_step()])
    session, _, _, _ = make_session(adapter, tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore", world_text="Лор Вейла")
    assert "Лор Вейла" in adapter.requests[0].system[1].text


def test_world_text_defaults_to_empty(tmp_path, registry, cfg):
    adapter = scripted([text_step()])
    session, _, _, _ = make_session(adapter, tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert "Лор Вейла" not in adapter.requests[0].system[1].text


def test_system_is_the_same_between_turns_with_world_text(tmp_path, registry, cfg):
    adapter = scripted([text_step(), text_step()])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg)
    session.run(ctx, "Первый ход.", apply, "explore", world_text="Лор Вейла")
    ctx.bundle.world.clock.advance(5000)
    session.run(ctx, "Второй ход.", apply, "explore", world_text="Лор Вейла")
    assert adapter.requests[0].system == adapter.requests[1].system


# L1: точка кэша на сообщении хода (первое), на сообщениях раундов её нет

def cache_points(request):
    system = sum(1 for b in request.system if b.cache)
    return system + sum(1 for m in request.messages if getattr(m, "cache", False))


def test_turn_message_has_cache_point_in_first_request(tmp_path, registry, cfg):
    adapter = scripted([text_step()])
    run(adapter, tmp_path, registry, cfg)
    assert [m.cache for m in adapter.requests[0].messages] == [True]


def test_cache_point_only_on_turn_message_in_every_round(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), tools_step(flag_call("b", "c2")), text_step()]
    adapter = scripted(steps)
    run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 3
    for request in adapter.requests:
        assert request.messages[0].cache is True
        assert [m for m in request.messages[1:] if m.cache] == []


def test_turn_message_is_unchanged_between_rounds(tmp_path, registry, cfg):
    steps = [tools_step(flag_call("a", "c1")), text_step()]
    adapter = scripted(steps)
    run(adapter, tmp_path, registry, cfg)
    assert adapter.requests[0].messages[0] == adapter.requests[1].messages[0]


def test_four_cache_points_in_every_round(tmp_path, registry, cfg):
    steps = [tools_step(flag_call(f"f{n}", f"c{n}")) for n in range(6)] + [text_step()]
    adapter = scripted(steps)
    run(adapter, tmp_path, registry, cfg)
    # три system-блока (rules, world 1h; память 5m) + сообщение хода (5m)
    assert [cache_points(r) for r in adapter.requests] == [4] * 7


def test_no_cache_point_after_invalid_retry_note(tmp_path, registry, cfg):
    adapter = scripted([{"text": "   "}, text_step()])
    run(adapter, tmp_path, registry, cfg)
    messages = adapter.requests[1].messages
    assert len(messages) == 3
    assert [m.cache for m in messages] == [True, False, False]


def test_narration_drops_code_fences():
    from ai_dm.master.session import plain_text
    assert plain_text("```text\nСцена.\n```") == "Сцена."
    assert plain_text("Текст с `кодом` внутри.") == "Текст с `кодом` внутри."


# Б1-фикс п.1: рассказ уже есть, варианты предложены -- завершающий вызов не нужен

def offer_call(call_id="o1", choices=("Бежать", "Драться")):
    return {
        "id": call_id, "name": "offer_choices",
        "input": {"type": "offer_choices", "choices": list(choices)},
    }


def test_text_with_offer_choices_makes_one_call(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call(), text="Стражник хмурится."), text_step("Лишнее.")])
    run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 1


def test_text_with_offer_choices_has_no_duplicate_text(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call(), text="Стражник хмурится.")])
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert result.texts == ["Стражник хмурится."]
    assert result.narration == "Стражник хмурится."


def test_text_with_offer_choices_sets_choices_and_decision(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call(), text="Стражник хмурится.")])
    result, ctx = run(adapter, tmp_path, registry, cfg, executor=apply)
    assert ctx.bundle.session.offered_choices == ["Бежать", "Драться"]
    assert [d.status for d in result.decisions] == ["accepted"]
    assert result.rounds == 1


def test_offer_choices_without_text_asks_model_again(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call()), text_step("Что дальше?")])
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.texts == ["Что дальше?"]


def test_whitespace_text_with_offer_choices_asks_model_again(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call(), text="   "), text_step("Что дальше?")])
    run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2


def test_text_with_offer_choices_and_other_tool_asks_model_again(tmp_path, registry, cfg):
    steps = [tools_step(offer_call(), flag_call("met", "c1"), text="Сцена."), text_step("Итог.")]
    adapter = scripted(steps)
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.texts == ["Сцена.", "Итог."]


def test_text_with_only_other_tool_asks_model_again(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1"), text="Сцена."), text_step("Итог.")])
    run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2


def test_rejected_offer_choices_with_text_asks_model_again(tmp_path, registry, cfg):
    from master_kit import reject_all

    adapter = scripted([tools_step(offer_call(), text="Сцена."), text_step("Итог.")])
    result, _ = run(adapter, tmp_path, registry, cfg, executor=reject_all)
    assert len(adapter.requests) == 2
    assert result.texts == ["Сцена.", "Итог."]


def test_invalid_offer_choices_with_text_counts_invalid_as_before(tmp_path, registry, cfg):
    bad = {"id": "o1", "name": "offer_choices", "input": {"type": "offer_choices"}}
    adapter = scripted([tools_step(bad, text="Сцена."), text_step("Итог.")])
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.invalid_count == 1
    assert result.texts == ["Итог."]


def test_offer_choices_with_text_but_required_not_done_asks_model_again(tmp_path, registry, cfg):
    from master_kit import combat_ctx

    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="defeat_pending")
    defeat = {
        "id": "d1", "name": "defeat_outcome",
        "input": {"type": "defeat_outcome", "consequences": ["left_to_die"]},
    }
    steps = [tools_step(offer_call(), text="Тьма."), tools_step(defeat), text_step("Конец.")]
    adapter = scripted(steps)
    session, _, _, _ = make_session(adapter, tmp_path)
    session.run(ctx, "Падаю.", apply, "combat_narrate")
    assert len(adapter.requests) == 3


def test_offer_choices_with_text_and_required_done_earlier_finishes(tmp_path, registry, cfg):
    from master_kit import combat_ctx

    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="victory")
    adapter = scripted([tools_step(offer_call(), text="Победа."), text_step("Лишнее.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    result = session.run(ctx, "Добиваю.", apply, "combat_narrate")
    assert len(adapter.requests) == 1
    assert result.texts == ["Победа."]


def test_offer_choices_with_text_for_world_role_asks_model_again(tmp_path, registry, cfg):
    adapter = scripted([tools_step(offer_call(), text="Сцена."), text_step("Итог.")])
    run(adapter, tmp_path, registry, cfg, role="world")
    assert len(adapter.requests) == 2


def test_offer_choices_with_text_max_tokens_is_not_early_exit(tmp_path, registry, cfg):
    steps = [tools_step(offer_call(), text="Сцена.", stop="max_tokens"), text_step("Коротко.")]
    adapter = scripted(steps)
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.texts == ["Коротко."]


def test_early_exit_with_offer_keeps_texts_of_earlier_rounds(tmp_path, registry, cfg):
    steps = [
        tools_step(flag_call("a", "c1"), text="Сцена."),
        tools_step(offer_call(), text="Что дальше?"),
        text_step("Лишнее."),
    ]
    adapter = scripted(steps)
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.texts == ["Сцена.", "Что дальше?"]
    assert result.narration == "Сцена.\n\nЧто дальше?"


def test_early_exit_with_offer_after_earlier_text_only_round_one_text_counts(
    tmp_path, registry, cfg
):
    # текст раньше, а в раунде с offer_choices текста нет: рассказ уже есть -- выход
    steps = [
        tools_step(flag_call("a", "c1"), text="Сцена."),
        tools_step(offer_call()),
        text_step("Лишнее."),
    ]
    adapter = scripted(steps)
    result, _ = run(adapter, tmp_path, registry, cfg)
    assert len(adapter.requests) == 2
    assert result.texts == ["Сцена."]
