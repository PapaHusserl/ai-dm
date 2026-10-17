# ТС #22 (docs/TS-PLAN.md §1 п.2, п.5, §4): run_scene / run_chapter берут summary_trim_after из
# app_cfg.memory; TurnContext по умолчанию не режет; soft_failure живёт в master.session и
# по-прежнему доступен из master.summarizer.
from types import SimpleNamespace

import pytest
from master_kit import app_cfg as make_app_cfg
from master_kit import make_bundle, scripted

from ai_dm.llm.errors import LlmFatal
from ai_dm.master import session as session_module
from ai_dm.master import summarizer as summarizer_module
from ai_dm.master.session import SOFT_REASONS, TurnFailed, soft_failure
from ai_dm.master.summarizer import SummarizerSession
from ai_dm.protocol.context import TurnContext
from ai_dm.state.session import ChapterState

OPUS = "claude-opus-5-5"


@pytest.fixture
def app_cfg():
    return make_app_cfg()


def scene_steps(*texts):
    steps = []
    for n, text in enumerate(texts):
        data = {"type": "scene_summary", "title": "", "summary": text}
        steps.append({"tool_calls": [{"id": f"ss-{n}", "name": "scene_summary", "input": data}]})
    return steps


def chapter_steps(chapter, game, suffix="1"):
    calls = [
        {"id": f"cs-{suffix}", "name": "chapter_summary",
         "input": {"type": "chapter_summary", "title": "Т", "summary": chapter}},
        {"id": f"gs-{suffix}", "name": "game_summary",
         "input": {"type": "game_summary", "summary": game}},
    ]
    return [{"tool_calls": calls}]


def chapter_bundle(registry):
    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id="chapter_1", number=1, started_at_s=0, scene_count=1, closed_reason="end_chapter"
    )
    return bundle


def make_session(app_cfg, steps):
    return SummarizerSession(scripted(steps), app_cfg, sleeper=lambda s: None, model=OPUS)


# TurnContext

def test_context_summary_trim_defaults(registry, cfg):
    ctx = TurnContext(make_bundle(registry), registry, cfg)
    assert ctx.summary_overflows == {}
    assert ctx.summary_trim_after == 0


def test_context_overflows_dict_is_not_shared_between_contexts(registry, cfg):
    first = TurnContext(make_bundle(registry), registry, cfg)
    second = TurnContext(make_bundle(registry), registry, cfg)
    first.summary_overflows["scene"] = 1
    assert second.summary_overflows == {}


# run_scene / run_chapter ставят порог из конфига

def test_run_scene_sets_trim_after_from_memory_config(registry, cfg, app_cfg):
    app_cfg.memory.summary_trim_after = 4
    session = make_session(app_cfg, scene_steps("Выжимка."))
    ctx = session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert ctx.summary_trim_after == 4


def test_run_scene_default_trim_after_is_two(registry, cfg, app_cfg):
    session = make_session(app_cfg, scene_steps("Выжимка."))
    ctx = session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert ctx.summary_trim_after == 2


def test_run_chapter_sets_trim_after_from_memory_config(registry, cfg, app_cfg):
    app_cfg.memory.summary_trim_after = 3
    session = make_session(app_cfg, chapter_steps("Глава.", "Игра."))
    ctx = session.run_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert ctx.summary_trim_after == 3


def test_run_chapter_default_trim_after_is_two(registry, cfg, app_cfg):
    session = make_session(app_cfg, chapter_steps("Глава.", "Игра."))
    ctx = session.run_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert ctx.summary_trim_after == 2


def test_run_scene_trims_third_overflow_to_scene_limit(registry, cfg, app_cfg):
    text = "Герой пришёл в город. " * 40
    session = make_session(app_cfg, scene_steps(text, text, text))
    ctx = session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert 0 < len(ctx.summary_text) <= app_cfg.memory.scene_summary_max
    assert ctx.marks == ["summary_trimmed"]


def test_run_scene_with_trim_after_zero_raises_after_invalid_budget(registry, cfg, app_cfg):
    app_cfg.memory.summary_trim_after = 0
    text = "Герой пришёл в город. " * 40
    session = make_session(app_cfg, scene_steps(text, text, text))
    with pytest.raises(TurnFailed) as error:
        session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert error.value.reason == "invalid"


def test_run_scene_with_trim_after_one_trims_on_second_answer(registry, cfg, app_cfg):
    app_cfg.memory.summary_trim_after = 1
    text = "Герой пришёл в город. " * 40
    session = make_session(app_cfg, scene_steps(text, text))
    ctx = session.run_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert 0 < len(ctx.summary_text) <= app_cfg.memory.scene_summary_max


def test_run_chapter_trims_game_and_chapter_to_their_limits(registry, cfg, app_cfg):
    chapter = "Глава началась в городе. " * 100
    game = "Игра началась в городе. " * 200
    steps = []
    for n in range(3):
        steps += chapter_steps(chapter, game, suffix=str(n))
    session = make_session(app_cfg, steps)
    ctx = session.run_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert 0 < len(ctx.chapter_text) <= app_cfg.memory.chapter_summary_max
    assert 0 < len(ctx.game_text) <= app_cfg.memory.game_summary_max


def test_try_scene_with_trimming_has_no_fall(registry, cfg, app_cfg):
    text = "Герой пришёл в город. " * 40
    session = make_session(app_cfg, scene_steps(text, text, text))
    ctx, fell = session.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert fell is False
    assert ctx.summary_text


# soft_failure перенесён в session

def test_soft_reasons_are_in_session_module():
    assert SOFT_REASONS == ("refusal", "invalid", "network")


def test_soft_failure_is_the_same_function_in_summarizer_and_session():
    assert summarizer_module.soft_failure is session_module.soft_failure
    assert summarizer_module.soft_failure is soft_failure


@pytest.mark.parametrize("reason", ["refusal", "invalid", "network"])
def test_session_soft_failure_true_for_soft_reasons(reason):
    assert soft_failure(TurnFailed(reason, "x")) is True


@pytest.mark.parametrize("reason", ["fatal", "rounds"])
def test_session_soft_failure_false_for_hard_reasons(reason):
    assert soft_failure(TurnFailed(reason, "x")) is False


def test_session_soft_failure_false_for_llm_error():
    assert soft_failure(LlmFatal("x")) is False


def test_session_soft_failure_false_for_foreign_exception():
    assert soft_failure(ValueError("x")) is False


def test_session_soft_failure_false_for_none_and_namespace():
    assert soft_failure(None) is False
    assert soft_failure(SimpleNamespace(reason="refusal")) is False
