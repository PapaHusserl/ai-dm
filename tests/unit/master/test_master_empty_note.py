# AD1 (W4/W7): подсказка модели на пустой ответ зависит от роли и режима; required_tool; хвосты
# run_round (свёртка главы: оба инструмента, clamped, пустой финал после неполного раунда).
import pytest
from master_kit import (
    flag_call,
    make_ctx,
    make_session,
    scripted,
    text_step,
    tools_step,
)
from test_master_summarizer_exit import chapter_call, clamp_all, game_call, scene_call, summarize

from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision
from ai_dm.state.combat import CombatState

EMPTY = {"text": ""}
NOTE_NARRATOR = "Пустой ответ. Напиши повествование или вызови нужный инструмент."
NOTE_WORLD = "Пустой ответ. Вызови нужные инструменты."
NOTE_SCENE = "Пустой ответ. Вызови инструмент scene_summary."
NOTE_CHAPTER = "Пустой ответ. Вызови chapter_summary и game_summary."


def accept(ctx, request):
    return Decision(status="accepted", result={})


def last_user_text(adapter, index):
    blocks = adapter.requests[index].messages[-1].content
    return "\n".join(b.text for b in blocks if hasattr(b, "text"))


def run_role(adapter, tmp_path, registry, cfg, role, mode):
    session, _, _, _ = make_session(adapter, tmp_path, role=role)
    ctx = make_ctx(registry, cfg, mode=mode)
    return session.run(ctx, "", accept, mode)


# тексты подсказок

def test_empty_answer_of_narrator_gets_narrator_note(tmp_path, registry, cfg):
    adapter = scripted([EMPTY, text_step("Рассказ.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert last_user_text(adapter, 1) == NOTE_NARRATOR


def test_empty_answer_of_world_gets_world_note(tmp_path, registry, cfg):
    adapter = scripted([EMPTY, tools_step(flag_call("a", "c1")), EMPTY])
    run_role(adapter, tmp_path, registry, cfg, "world", "world")
    assert last_user_text(adapter, 1) == NOTE_WORLD


def test_empty_answer_of_summarizer_scene_gets_scene_note(tmp_path, registry, cfg):
    adapter = scripted([EMPTY, tools_step(scene_call())])
    summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert last_user_text(adapter, 1) == NOTE_SCENE


def test_empty_answer_of_summarizer_chapter_gets_chapter_note(tmp_path, registry, cfg):
    adapter = scripted([EMPTY, tools_step(chapter_call(), game_call())])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert last_user_text(adapter, 1) == NOTE_CHAPTER


# world: пустой финал после раунда инструментов -- конец

def test_world_empty_final_after_tool_round_is_success(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("a", "c1")), EMPTY])
    result = run_role(adapter, tmp_path, registry, cfg, "world", "world")
    assert len(adapter.requests) == 2
    assert result.invalid_count == 0


def test_world_empty_first_answer_is_retried(tmp_path, registry, cfg):
    adapter = scripted([EMPTY, EMPTY, EMPTY, EMPTY])
    session, _, _, _ = make_session(adapter, tmp_path, role="world")
    ctx = make_ctx(registry, cfg, mode="world")
    with pytest.raises(TurnFailed):
        session.run(ctx, "", accept, "world")
    assert len(adapter.requests) == 3


# required_tool

def test_required_tool_of_world_with_verdict_refs(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path, role="world")
    ctx = make_ctx(registry, cfg, mode="world")
    ctx.verdict_refs = {"x"}
    assert session.required_tool(ctx, "world") == "world_verdict"


def test_required_tool_of_world_without_verdict_refs_is_none(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path, role="world")
    ctx = make_ctx(registry, cfg, mode="world")
    ctx.verdict_refs = set()
    assert session.required_tool(ctx, "world") is None


def test_required_tool_verdict_refs_do_not_matter_outside_world(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = make_ctx(registry, cfg)
    ctx.verdict_refs = {"x"}
    assert session.required_tool(ctx, "explore") is None


def test_required_tool_by_mode(tmp_path, registry, cfg):
    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = make_ctx(registry, cfg)
    assert session.required_tool(ctx, "combat_classify") == "player_action"
    assert session.required_tool(ctx, "npc_choice") == "npc_action"
    assert session.required_tool(ctx, "summarize_scene") == "scene_summary"
    assert session.required_tool(ctx, "summarize_chapter") == "chapter_summary"
    assert session.required_tool(ctx, "explore") is None


def test_required_tool_combat_narrate_defeat_pending(tmp_path, registry, cfg):
    from master_kit import combat_ctx

    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_narrate", outcome="defeat_pending")
    assert session.required_tool(ctx, "combat_narrate") == "defeat_outcome"
    assert isinstance(ctx.bundle.session.active_combat, CombatState)


def test_required_tool_combat_narrate_without_defeat_is_none(tmp_path, registry, cfg):
    from master_kit import combat_ctx

    session, _, _, _ = make_session(scripted([]), tmp_path)
    ctx = combat_ctx(registry, cfg, "combat_narrate")
    assert session.required_tool(ctx, "combat_narrate") is None


# свёртка главы

def test_chapter_clamped_tools_count_as_accepted(tmp_path, registry, cfg):
    adapter = scripted([tools_step(chapter_call(), game_call())])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter", clamp_all)
    assert len(adapter.requests) == 1


def test_chapter_incomplete_round_tells_model_to_send_both(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    note = last_user_text(adapter, 1)
    assert "Нужны оба вызова в одном ответе: chapter_summary и game_summary." in note


def test_chapter_incomplete_round_with_invalid_call_has_no_both_note(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call("", call_id="cs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert "Нужны оба вызова" not in last_user_text(adapter, 1)


def test_chapter_empty_final_after_incomplete_round_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1")),
        EMPTY,
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 3
    assert ctx.game_text == "Свёртка игры."


# тексты раундов копятся

def test_texts_of_several_rounds_are_all_in_narration(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(flag_call("a", "c1"), text="Первый кусок."),
        tools_step(flag_call("b", "c2"), text="Второй кусок."),
        text_step("Третий кусок."),
    ])
    session, _, _, _ = make_session(adapter, tmp_path)
    result = session.run(make_ctx(registry, cfg), "Иду.", apply, "explore")
    assert result.texts == ["Первый кусок.", "Второй кусок.", "Третий кусок."]
    assert result.narration == "Первый кусок.\n\nВторой кусок.\n\nТретий кусок."


# мутанты ТВ (партия #18): неполный раунд свёртки и тексты раундов выжимки

def test_chapter_incomplete_round_counts_as_invalid(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    result, _, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert result.invalid_count == 1


def test_single_shot_texts_of_earlier_rounds_are_kept(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(scene_call(""), text="Первый."),
        tools_step(scene_call(), text="Второй."),
    ])
    result, _, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert result.texts == ["Первый.", "Второй."]
