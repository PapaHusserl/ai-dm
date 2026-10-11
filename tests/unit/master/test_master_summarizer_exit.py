# AD1, W4: роль summarizer выходит из цикла сразу после принятого required-вызова, без
# завершающего вызова модели. Нарратор и world по-прежнему делают финальный вызов.
from master_kit import (
    app_cfg,
    flag_call,
    make_ctx,
    make_session,
    player_action_call,
    scripted,
    text_step,
    tools_step,
)

from ai_dm.master.summarizer import SummarizerPromptBuilder
from ai_dm.protocol.apply import apply
from ai_dm.protocol.context import TurnContext
from ai_dm.protocol.decision import Decision
from ai_dm.state.session import ChapterState


def scene_call(summary="Выжимка сцены.", title="", call_id="ss-1"):
    return {
        "id": call_id, "name": "scene_summary",
        "input": {"type": "scene_summary", "title": title, "summary": summary},
    }


def chapter_call(summary="Выжимка главы.", call_id="cs-1"):
    return {
        "id": call_id, "name": "chapter_summary",
        "input": {"type": "chapter_summary", "title": "Глава", "summary": summary},
    }


def game_call(summary="Свёртка игры.", call_id="gs-1"):
    return {
        "id": call_id, "name": "game_summary",
        "input": {"type": "game_summary", "summary": summary},
    }


def summarize(adapter, tmp_path, registry, cfg, mode, executor=apply):
    session, journal, _, _ = make_session(
        adapter, tmp_path, role="summarizer", builder=SummarizerPromptBuilder(app_cfg()),
    )
    bundle = make_ctx(registry, cfg).bundle
    bundle.session.current_chapter = ChapterState(id="ch-1", number=1, closed_reason="end_chapter")
    ctx = TurnContext(bundle, registry, cfg, mode=mode)
    ctx.summary_max = 600
    ctx.chapter_summary_max = 1500
    ctx.game_summary_max = 3000
    result = session.run(ctx, "", executor, mode)
    return result, ctx, journal


def clamp_all(ctx, request):
    return Decision(status="clamped", result={"type": request.type})


# summarize_scene

def test_scene_summary_accepted_makes_one_model_call(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call()), text_step("Готово.")])
    summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert len(adapter.requests) == 1


def test_scene_summary_accepted_is_written_to_ctx(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call("Герой нашёл ключ.", "Ключ"))])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert ctx.summary_text == "Герой нашёл ключ."
    assert ctx.summary_title == "Ключ"


def test_scene_summary_accepted_gives_one_journal_record(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call())])
    _, _, journal = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    records = journal.read_records()
    assert [r["role"] for r in records] == ["summarizer"]


def test_scene_summary_result_keeps_round_and_decision(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call())])
    result, _, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert result.rounds == 1
    assert [d.status for d in result.decisions] == ["accepted"]
    assert result.stop_reason == "tool_use"


def test_scene_summary_text_next_to_call_goes_to_narration(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call(), text="Итог сцены.")])
    result, _, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert result.texts == ["Итог сцены."]
    assert result.narration == "Итог сцены."


def test_scene_summary_invalid_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(scene_call("", call_id="ss-1")),
        tools_step(scene_call("Нормальная выжимка.", call_id="ss-2")),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert len(adapter.requests) == 2
    assert ctx.summary_text == "Нормальная выжимка."


def test_scene_summary_too_long_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(scene_call("я" * 601, call_id="ss-1")),
        tools_step(scene_call("Короткая.", call_id="ss-2")),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert len(adapter.requests) == 2
    assert ctx.summary_text == "Короткая."


def test_scene_summary_invalid_error_is_shown_to_model(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(scene_call("", call_id="ss-1")),
        tools_step(scene_call("Нормальная выжимка.", call_id="ss-2")),
    ])
    summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    last = adapter.requests[1].messages[-1].content[0]
    assert last.is_error is True


def test_scene_summary_clamped_counts_as_accepted(tmp_path, registry, cfg):
    adapter = scripted([tools_step(scene_call()), text_step("Готово.")])
    result, _, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene", clamp_all)
    assert len(adapter.requests) == 1
    assert [d.status for d in result.decisions] == ["clamped"]


def test_wrong_tool_in_scene_mode_does_not_end_the_run(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(flag_call("met", "c1")),
        tools_step(scene_call()),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert len(adapter.requests) == 2
    assert ctx.summary_text == "Выжимка сцены."


def test_text_without_call_in_scene_mode_asks_again(tmp_path, registry, cfg):
    adapter = scripted([text_step("Просто текст."), tools_step(scene_call())])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_scene")
    assert len(adapter.requests) == 2
    assert ctx.summary_text == "Выжимка сцены."


# summarize_chapter

def test_chapter_both_tools_in_one_answer_makes_one_call(tmp_path, registry, cfg):
    adapter = scripted([tools_step(chapter_call(), game_call()), text_step("Готово.")])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 1
    assert ctx.chapter_text == "Выжимка главы."
    assert ctx.game_text == "Свёртка игры."


def test_chapter_only_chapter_summary_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 2
    assert ctx.game_text == "Свёртка игры."


def test_chapter_only_game_summary_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(game_call(call_id="gs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 2


def test_chapter_one_tool_per_round_does_not_end_the_run(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1")),
        tools_step(game_call(call_id="gs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 3


def test_chapter_invalid_game_summary_is_retried(tmp_path, registry, cfg):
    adapter = scripted([
        tools_step(chapter_call(call_id="cs-1"), game_call("", call_id="gs-1")),
        tools_step(chapter_call(call_id="cs-2"), game_call(call_id="gs-2")),
    ])
    _, ctx, _ = summarize(adapter, tmp_path, registry, cfg, "summarize_chapter")
    assert len(adapter.requests) == 2
    assert ctx.game_text == "Свёртка игры."


# нарратор и world: финальный вызов остаётся

def test_narrator_still_makes_final_call_after_tools(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1")), text_step("Готово.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="explore")
    result = session.run(ctx, "Иду.", apply, "explore")
    assert len(adapter.requests) == 2
    assert result.narration == "Готово."


def test_narrator_required_tool_accepted_still_makes_final_call(tmp_path, registry, cfg):
    adapter = scripted([tools_step(player_action_call()), text_step("Конец.")])
    session, _, _, _ = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, mode="combat_classify")
    session.run(ctx, "Бью.", lambda c, r: Decision(status="accepted", result={}), "combat_classify")
    assert len(adapter.requests) == 2


def test_world_still_makes_final_call_after_tools(tmp_path, registry, cfg):
    adapter = scripted([tools_step(flag_call("met", "c1")), text_step("Готово.")])
    session, _, _, _ = make_session(adapter, tmp_path, role="world")
    ctx = make_ctx(registry, cfg, mode="world")
    session.run(ctx, "", lambda c, r: Decision(status="accepted", result={}), "world")
    assert len(adapter.requests) == 2
