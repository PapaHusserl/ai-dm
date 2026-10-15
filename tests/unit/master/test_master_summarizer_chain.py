# Р2 (R2-PLAN, В10а-В12а): цепочка SummarizerSession -- сам, затем запасной на модели рассказчика,
# затем (None, True). Мягкие сбои: refusal, invalid и network (Т60); остальное поднимается наверх.
from types import SimpleNamespace

import pytest
from master_kit import app_cfg as make_app_cfg
from master_kit import make_bundle, scripted

from ai_dm.llm.errors import LlmFatal
from ai_dm.master.session import TurnFailed
from ai_dm.master.summarizer import SummarizerSession, soft_failure
from ai_dm.state.session import ChapterState

OPUS = "claude-opus-5-5"
SONNET = "claude-sonnet-5-5"
REFUSAL = [{"stop": "refusal"}]


@pytest.fixture
def app_cfg():
    return make_app_cfg()


def scene_call(summary="Выжимка.", call_id="ss-1"):
    data = {"type": "scene_summary", "title": "", "summary": summary}
    return {"id": call_id, "name": "scene_summary", "input": data}


def scene_steps(summary="Выжимка."):
    return [{"tool_calls": [scene_call(summary)]}]


def chapter_steps(chapter="Глава.", game="Игра."):
    calls = [
        {"id": "cs-1", "name": "chapter_summary",
         "input": {"type": "chapter_summary", "title": "Т", "summary": chapter}},
        {"id": "gs-1", "name": "game_summary", "input": {"type": "game_summary", "summary": game}},
    ]
    return [{"tool_calls": calls}]


def chapter_bundle(registry):
    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id="chapter_1", number=1, started_at_s=0, scene_count=1, closed_reason="end_chapter"
    )
    return bundle


def make_chain(app, primary_steps, backup_steps, with_backup=True):
    primary_adapter = scripted(primary_steps)
    backup_adapter = scripted(backup_steps)
    backup = None
    if with_backup:
        backup = SummarizerSession(backup_adapter, app, sleeper=lambda s: None, model=SONNET)
    primary = SummarizerSession(
        primary_adapter, app, sleeper=lambda s: None, model=OPUS, backup=backup
    )
    return primary, primary_adapter, backup_adapter


# soft_failure

@pytest.mark.parametrize("reason", ["refusal", "invalid", "network"])
def test_soft_failure_true_for_refusal_invalid_and_network(reason):
    assert soft_failure(TurnFailed(reason, "x")) is True


@pytest.mark.parametrize("reason", ["fatal", "rounds"])
def test_soft_failure_false_for_other_turn_failures(reason):
    assert soft_failure(TurnFailed(reason, "x")) is False


def test_soft_failure_false_for_llm_error():
    assert soft_failure(LlmFatal("x")) is False


def test_soft_failure_false_for_foreign_exception():
    assert soft_failure(ValueError("x")) is False


# chain: заглушки сессий

class Boom:
    def __init__(self, error):
        self.error = error


def chain_of(primary_result, backup_result, ok=lambda c: c is not None, with_backup=True):
    # результат -- контекст или исключение; журнал вызовов в calls
    calls = []

    def handler(name, result):
        def run():
            calls.append(name)
            if isinstance(result, Exception):
                raise result
            return result

        return run

    backup = None
    if with_backup:
        backup = SimpleNamespace(run=handler("backup", backup_result))
    primary = SummarizerSession(None, None, backup=backup)
    primary.run = handler("primary", primary_result)
    outcome = primary.chain(lambda s: s.run(), ok)
    return outcome, calls


def test_chain_first_ok_returns_ctx_without_fall_and_skips_backup():
    outcome, calls = chain_of("ctx1", "ctx2")
    assert outcome == ("ctx1", False)
    assert calls == ["primary"]


def test_chain_first_refusal_backup_ok_marks_fall():
    outcome, calls = chain_of(TurnFailed("refusal", "x"), "ctx2")
    assert outcome == ("ctx2", True)
    assert calls == ["primary", "backup"]


def test_chain_first_invalid_backup_ok_marks_fall():
    outcome, calls = chain_of(TurnFailed("invalid", "x"), "ctx2")
    assert outcome == ("ctx2", True)


def test_chain_bad_ctx_of_first_goes_to_backup():
    outcome, calls = chain_of("", "ctx2", ok=bool)
    assert outcome == ("ctx2", True)
    assert calls == ["primary", "backup"]


def test_chain_both_soft_gives_none_and_fall():
    outcome, calls = chain_of(TurnFailed("refusal", "x"), TurnFailed("invalid", "x"))
    assert outcome == (None, True)
    assert calls == ["primary", "backup"]


def test_chain_both_bad_ctx_gives_none_and_fall():
    outcome, _ = chain_of("", "", ok=bool)
    assert outcome == (None, True)


def test_chain_without_backup_and_refusal_gives_none_and_fall():
    outcome, calls = chain_of(TurnFailed("refusal", "x"), "ctx2", with_backup=False)
    assert outcome == (None, True)
    assert calls == ["primary"]


def test_chain_without_backup_and_bad_ctx_gives_none_and_fall():
    outcome, _ = chain_of("", "ctx2", ok=bool, with_backup=False)
    assert outcome == (None, True)


HARD = [
    TurnFailed("fatal", "x"), TurnFailed("rounds", "x"), LlmFatal("x"),
]


@pytest.mark.parametrize("error", HARD)
def test_chain_hard_failure_of_first_raises_and_skips_backup(error):
    calls = []
    backup = SimpleNamespace(run=lambda: calls.append("backup"))
    primary = SummarizerSession(None, None, backup=backup)

    def boom():
        raise error

    primary.run = boom
    with pytest.raises(type(error)):
        primary.chain(lambda s: s.run(), lambda c: True)
    assert calls == []


def test_chain_hard_failure_of_backup_raises():
    with pytest.raises(TurnFailed) as info:
        chain_of(TurnFailed("refusal", "x"), TurnFailed("fatal", "x"))
    assert info.value.reason == "fatal"


# try_scene / try_chapter на настоящих сессиях

def test_try_scene_first_ok_does_not_touch_backup(registry, cfg, app_cfg):
    primary, first, second = make_chain(app_cfg, scene_steps("Сама."), scene_steps("Бэкап."))
    ctx, fell = primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.summary_text, fell) == ("Сама.", False)
    assert second.requests == []


def test_try_scene_refusal_goes_to_backup_with_summarizer_role_and_its_model(
    registry, cfg, app_cfg
):
    primary, first, second = make_chain(app_cfg, REFUSAL, scene_steps("Бэкап."))
    ctx, fell = primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.summary_text, fell) == ("Бэкап.", True)
    assert len(first.requests) == 1
    assert len(second.requests) == 1
    assert second.requests[0].role == "summarizer"
    assert second.requests[0].model == SONNET
    assert first.requests[0].model == OPUS
    assert {t.name for t in second.requests[0].tools} == {"scene_summary"}


def test_try_scene_both_refused_gives_none(registry, cfg, app_cfg):
    primary, _, _ = make_chain(app_cfg, REFUSAL, REFUSAL)
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_scene_without_backup_and_refusal_gives_none(registry, cfg, app_cfg):
    primary, _, _ = make_chain(app_cfg, REFUSAL, [], with_backup=False)
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_scene_network_goes_to_backup(registry, cfg, app_cfg):
    network = [{"error": "transient", "message": "сеть"}] * 4
    primary, _, second = make_chain(app_cfg, network, scene_steps("Бэкап."))
    ctx, fell = primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.summary_text, fell) == ("Бэкап.", True)
    assert len(second.requests) == 1


def test_try_scene_network_of_both_gives_none(registry, cfg, app_cfg):
    network = [{"error": "transient", "message": "сеть"}] * 4
    primary, _, _ = make_chain(app_cfg, network, network)
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_scene_network_without_backup_gives_none(registry, cfg, app_cfg):
    network = [{"error": "transient", "message": "сеть"}] * 4
    primary, _, _ = make_chain(app_cfg, network, [], with_backup=False)
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_scene_backup_fatal_raises(registry, cfg, app_cfg):
    primary, _, _ = make_chain(app_cfg, REFUSAL, [{"error": "fatal", "message": "x"}])
    with pytest.raises(TurnFailed) as info:
        primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert info.value.reason == "fatal"


def test_try_scene_empty_summary_text_goes_to_backup(registry, cfg, app_cfg, monkeypatch):
    primary, _, second = make_chain(app_cfg, [], scene_steps("Бэкап."))
    monkeypatch.setattr(
        primary, "run_scene", lambda *a: SimpleNamespace(summary_text=None, summary_title="")
    )
    ctx, fell = primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.summary_text, fell) == ("Бэкап.", True)


def test_try_scene_empty_string_summary_is_a_soft_failure(registry, cfg, app_cfg, monkeypatch):
    primary, _, second = make_chain(app_cfg, [], scene_steps("Бэкап."))
    monkeypatch.setattr(
        primary, "run_scene", lambda *a: SimpleNamespace(summary_text="", summary_title="")
    )
    ctx, fell = primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.summary_text, fell) == ("Бэкап.", True)
    assert len(second.requests) == 1


def test_try_scene_empty_text_of_both_gives_none(registry, cfg, app_cfg, monkeypatch):
    primary, _, _ = make_chain(app_cfg, [], [])
    empty = lambda *a: SimpleNamespace(summary_text="", summary_title="")  # noqa: E731
    monkeypatch.setattr(primary, "run_scene", empty)
    monkeypatch.setattr(primary.backup, "run_scene", empty)
    assert primary.try_scene(make_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_chapter_first_ok(registry, cfg, app_cfg):
    primary, _, second = make_chain(app_cfg, chapter_steps("Г1.", "И1."), chapter_steps())
    ctx, fell = primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.chapter_text, ctx.game_text, fell) == ("Г1.", "И1.", False)
    assert second.requests == []


def test_try_chapter_refusal_goes_to_backup(registry, cfg, app_cfg):
    primary, _, second = make_chain(app_cfg, REFUSAL, chapter_steps("Г2.", "И2."))
    ctx, fell = primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.chapter_text, ctx.game_text, fell) == ("Г2.", "И2.", True)
    assert second.requests[0].model == SONNET
    assert {t.name for t in second.requests[0].tools} == {"chapter_summary", "game_summary"}


def test_try_chapter_both_refused_gives_none(registry, cfg, app_cfg):
    primary, _, _ = make_chain(app_cfg, REFUSAL, REFUSAL)
    assert primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1") == (None, True)


@pytest.mark.parametrize(("chapter", "game"), [("", "И"), ("Г", ""), ("", "")])
def test_try_chapter_empty_text_of_first_goes_to_backup(
    registry, cfg, app_cfg, monkeypatch, chapter, game
):
    primary, _, second = make_chain(app_cfg, [], chapter_steps("Г2.", "И2."))
    monkeypatch.setattr(
        primary, "run_chapter",
        lambda *a: SimpleNamespace(chapter_text=chapter, game_text=game),
    )
    ctx, fell = primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert (ctx.chapter_text, fell) == ("Г2.", True)


def test_try_chapter_empty_text_of_both_gives_none(registry, cfg, app_cfg, monkeypatch):
    primary, _, _ = make_chain(app_cfg, [], [])
    empty = lambda *a: SimpleNamespace(chapter_text="", game_text="")  # noqa: E731
    monkeypatch.setattr(primary, "run_chapter", empty)
    monkeypatch.setattr(primary.backup, "run_chapter", empty)
    assert primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1") == (None, True)


def test_try_chapter_fatal_raises(registry, cfg, app_cfg):
    primary, _, second = make_chain(app_cfg, [{"error": "fatal", "message": "x"}], chapter_steps())
    with pytest.raises(TurnFailed):
        primary.try_chapter(chapter_bundle(registry), registry, cfg, "bnd-1")
    assert second.requests == []


# аргументы доходят до run_scene / run_chapter без подмен

def test_try_scene_passes_all_arguments_to_run_scene(monkeypatch):
    seen = []
    primary = SummarizerSession(None, None)
    monkeypatch.setattr(
        primary, "run_scene",
        lambda *args: seen.append(args) or SimpleNamespace(summary_text="x"),
    )
    primary.try_scene("B", "R", "C", "bnd-7")
    assert seen == [("B", "R", "C", "bnd-7")]


def test_try_chapter_passes_all_arguments_to_run_chapter(monkeypatch):
    seen = []
    primary = SummarizerSession(None, None)
    monkeypatch.setattr(
        primary, "run_chapter",
        lambda *args: seen.append(args) or SimpleNamespace(chapter_text="a", game_text="b"),
    )
    primary.try_chapter("B", "R", "C", "bnd-7")
    assert seen == [("B", "R", "C", "bnd-7")]


def test_try_scene_passes_the_same_arguments_to_backup(monkeypatch):
    seen = []
    backup = SummarizerSession(None, None)
    monkeypatch.setattr(
        backup, "run_scene",
        lambda *args: seen.append(args) or SimpleNamespace(summary_text="x"),
    )
    primary = SummarizerSession(None, None, backup=backup)
    monkeypatch.setattr(
        primary, "run_scene", lambda *args: (_ for _ in ()).throw(TurnFailed("refusal", "x"))
    )
    primary.try_scene("B", "R", "C", "bnd-7")
    assert seen == [("B", "R", "C", "bnd-7")]
