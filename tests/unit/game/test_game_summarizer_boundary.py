# Ожидаемый API (этап 4, P1): роль summarizer на шаге 1 границы сцены. Контракт и помощники --
# summarizer_kit.py. Мок без сети: ScriptedAdapter / ReactiveSummarizer / ReplayAdapter.
import pytest
from game_kit import (
    FactorySpy,
    advance_call,
    core_dump,
    end_scene_call,
    make_bundle,
    settings,
    text_step,
    tools_step,
)
from slots_kit import saved_close_reason
from summarizer_kit import (
    ReactiveSummarizer,
    dumps,
    force_close,
    has_tool_error,
    make_summ_app,
    make_summ_rig,
    request_text,
    summ_fail_steps,
    summ_steps,
)

from ai_dm.persistence.store import load_slot

REASONS = ["end_scene", "location_changed", "time_jump", "combat_ended", "turn_limit"]
ERROR_MENU = ["retry", "switch_model", "save_and_quit"]
SONNET = "claude-sonnet-5-5"


def quiet_narrator(n=1):
    return [text_step(f"Рассказ {i}.") for i in range(n)]


def end_narrator(summary=""):
    return [tools_step(end_scene_call(summary=summary)), text_step("Конец.")]


def failed_rig(registry, cfg, tmp_path, summarizer=None, narrator=None, bundle=None):
    rig = make_summ_rig(
        registry, cfg, tmp_path, narrator or end_narrator("Подсказка."),
        summarizer or summ_fail_steps(), bundle=bundle,
    )
    rig.runner.play("ход")
    return rig


# все причины закрытия

@pytest.mark.parametrize("reason", REASONS)
def test_every_close_reason_calls_summarizer_and_writes_summary(
    reason, registry, cfg, tmp_path, monkeypatch
):
    force_close(monkeypatch, reason)
    rig = make_summ_rig(
        registry, cfg, tmp_path, quiet_narrator(), summ_steps("Герой сделал дело.")
    )
    rig.runner.play("ход")
    scenes = rig.runner.bundle.memory.scenes
    assert saved_close_reason(tmp_path, "w1") == reason
    assert len(rig.summarizer_requests()) == 1
    assert len(scenes) == 1
    assert scenes[0].id == "scene_1"
    assert scenes[0].summary == "Герой сделал дело."
    assert scenes[0].source == "summarizer"


def test_end_scene_without_summary_hint_still_gets_summary(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(""), summ_steps("Сама выжимка."))
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].summary == "Сама выжимка."


def test_time_jump_without_end_scene_summary_gets_summary(registry, cfg, tmp_path):
    narrator = [tools_step(advance_call(category="day")), text_step("Прошёл день.")]
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, summ_steps("За день многое было."))
    rig.runner.play("ход")
    assert saved_close_reason(tmp_path, "w1") == "time_jump"
    assert rig.runner.bundle.memory.scenes[0].source == "summarizer"


def test_quiet_turn_does_not_call_summarizer(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), summ_steps())
    rig.runner.play("ход")
    assert rig.summarizer_requests() == []
    assert rig.runner.bundle.memory.scenes == []


def test_summary_is_not_the_narrator_hint(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator("Подсказка."), summ_steps("Итог."))
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].summary == "Итог."


def test_summary_is_written_in_the_scene_chapter(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps("Итог."))
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].chapter_id == "ch_1"


# title

def test_narrator_title_has_priority(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    bundle.session.current_scene.title = "Название нарратора"
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_narrator(), summ_steps("Итог.", title="Название ИИ"),
        bundle=bundle,
    )
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].title == "Название нарратора"


def test_summarizer_title_is_used_when_narrator_gave_none(registry, cfg, tmp_path):
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_narrator(), summ_steps("Итог.", title="Название ИИ")
    )
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].title == "Название ИИ"


# вход summarizer

def test_turn_record_gets_scene_id(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(2), summ_steps())
    rig.play(2)
    records = rig.runner.bundle.memory.recent_turns
    assert [r.scene_id for r in records] == ["scene_1", "scene_1"]


def test_turn_after_boundary_belongs_to_new_scene(registry, cfg, tmp_path):
    steps = end_narrator() + quiet_narrator()
    rig = make_summ_rig(registry, cfg, tmp_path, steps, summ_steps())
    rig.play(2)
    records = rig.runner.bundle.memory.recent_turns
    assert [r.scene_id for r in records] == ["scene_1", "scene_2"]


def test_summarizer_input_has_only_turns_of_closed_scene(registry, cfg, tmp_path):
    from ai_dm.state.scene import TurnRecord

    bundle = make_bundle(registry)
    bundle.memory.recent_turns.append(
        TurnRecord(
            turn_seq=0, at_s=0, player_input="СТАРЫЙ ВВОД", narration="СТАРЫЙ РАССКАЗ",
            scene_id="scene_0",
        )
    )
    steps = quiet_narrator() + end_narrator()
    rig = make_summ_rig(registry, cfg, tmp_path, steps, summ_steps(), bundle=bundle)
    rig.runner.play("ПЕРВЫЙ ВВОД")
    rig.runner.play("ВТОРОЙ ВВОД")
    text = request_text(rig.summarizer_requests()[0])
    assert "ПЕРВЫЙ ВВОД" in text
    assert "ВТОРОЙ ВВОД" in text
    assert "Рассказ 0." in text
    assert "СТАРЫЙ ВВОД" not in text
    assert "СТАРЫЙ РАССКАЗ" not in text


def test_narrator_hint_is_in_summarizer_request(registry, cfg, tmp_path):
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_narrator("Подсказка про Бранна."), summ_steps()
    )
    rig.runner.play("ход")
    assert "Подсказка про Бранна." in request_text(rig.summarizer_requests()[0])


def test_summarizer_request_has_role_and_only_summary_tool(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps())
    rig.runner.play("ход")
    request = rig.summarizer_requests()[0]
    assert request.role == "summarizer"
    assert {t.name for t in request.tools} == {"scene_summary"}


def test_summarizer_request_has_closed_reason(registry, cfg, tmp_path, monkeypatch):
    force_close(monkeypatch, "turn_limit")
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), summ_steps())
    rig.runner.play("ход")
    assert "turn_limit" in request_text(rig.summarizer_requests()[0])


# порядок

def test_boundary_order_autosave_summarizer_tick_world_chapter_new_scene(
    registry, cfg, tmp_path, monkeypatch
):
    import ai_dm.game.boundary as boundary

    events = []

    def spy(name):
        original = getattr(boundary, name)

        def wrapper(*args, **kwargs):
            events.append(name)
            return original(*args, **kwargs)

        monkeypatch.setattr(boundary, name, wrapper)

    for name in ("save_auto", "tick_days", "call_world", "close_chapter", "start_scene"):
        spy(name)

    class Spying(ReactiveSummarizer):
        def complete(self, request):
            if request.role == "summarizer":
                events.append("summarizer")
            return super().complete(request)

    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), Spying())
    rig.runner.play("ход")
    deduped = [e for i, e in enumerate(events) if i == 0 or e != events[i - 1]]
    assert deduped == [
        "save_auto", "summarizer", "tick_days", "call_world", "close_chapter", "start_scene",
    ]


def test_autosave_is_written_before_summarizer_call(registry, cfg, tmp_path):
    seen = []

    class Looking(ReactiveSummarizer):
        def complete(self, request):
            if request.role == "summarizer":
                saved = load_slot(tmp_path, "w1", "auto")
                seen.append((saved.session.boundary_pending, len(saved.memory.scenes)))
            return super().complete(request)

    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), Looking())
    rig.runner.play("ход")
    assert seen[0] == (True, 0)


# сбой summarizer (Д2)

def test_llm_failure_gives_boundary_failed_and_error_menu(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_fail_steps())
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU


def test_failure_keeps_boundary_pending_and_no_new_scene(registry, cfg, tmp_path):
    rig = failed_rig(registry, cfg, tmp_path)
    session = rig.runner.bundle.session
    assert session.boundary_pending is True
    assert session.current_scene.id == "scene_1"
    assert session.current_scene.closed_reason == "end_scene"


def test_failure_leaves_bundle_equal_to_autosave_and_no_summary(registry, cfg, tmp_path):
    rig = failed_rig(registry, cfg, tmp_path)
    bundle = rig.runner.bundle
    assert bundle.memory.scenes == []
    assert core_dump(bundle) == core_dump(load_slot(tmp_path, "w1", "auto"))


def test_failure_does_not_tick_the_world(registry, cfg, tmp_path):
    rig = failed_rig(registry, cfg, tmp_path)
    after = rig.runner.bundle.world.clock.now_s
    saved = load_slot(tmp_path, "w1", "auto").world.clock.now_s
    assert after == saved


def test_retry_after_failure_writes_summary_and_opens_scene(registry, cfg, tmp_path):
    rig = failed_rig(
        registry, cfg, tmp_path, summ_fail_steps() + summ_steps("После повтора.")
    )
    rig.runner.retry()
    bundle = rig.runner.bundle
    assert bundle.session.boundary_pending is False
    assert bundle.session.current_scene.id == "scene_2"
    assert [s.summary for s in bundle.memory.scenes] == ["После повтора."]
    assert bundle.memory.scenes[0].source == "summarizer"


def test_retry_after_failure_keeps_input_of_the_failed_scene(registry, cfg, tmp_path):
    rig = failed_rig(
        registry, cfg, tmp_path, summ_fail_steps() + summ_steps("После повтора.")
    )
    rig.runner.retry()
    assert "ход" in request_text(rig.summarizer_requests()[-1])


def test_save_and_quit_then_load_finishes_boundary_before_first_turn(registry, cfg, tmp_path):
    failed_rig(registry, cfg, tmp_path)
    loaded = load_slot(tmp_path, "w1", "auto")
    assert loaded.session.boundary_pending is True
    rig = make_summ_rig(
        registry, cfg, tmp_path, quiet_narrator(), summ_steps("Достроено."), bundle=loaded
    )
    rig.runner.play("новый ход")
    bundle = rig.runner.bundle
    assert [s.summary for s in bundle.memory.scenes] == ["Достроено."]
    assert bundle.session.current_scene.id == "scene_2"
    assert bundle.session.boundary_pending is False
    assert bundle.memory.recent_turns[-1].scene_id == "scene_2"


# невалидный ответ

def test_empty_summary_is_invalid_and_retried(registry, cfg, tmp_path):
    steps = summ_steps("") + summ_steps("Нормальная выжимка.", call_id="ss-2")
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), steps)
    rig.runner.play("ход")
    assert has_tool_error(rig.summarizer_requests()[1])
    assert rig.runner.bundle.memory.scenes[0].summary == "Нормальная выжимка."


def test_summary_over_600_is_invalid_and_retried(registry, cfg, tmp_path):
    steps = summ_steps("я" * 601) + summ_steps("Короткая.", call_id="ss-2")
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), steps)
    rig.runner.play("ход")
    assert has_tool_error(rig.summarizer_requests()[1])
    assert rig.runner.bundle.memory.scenes[0].summary == "Короткая."


def test_summary_of_600_chars_is_valid(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps("я" * 600))
    rig.runner.play("ход")
    assert len(rig.runner.bundle.memory.scenes[0].summary) == 600


def empty_answers(n=3):
    steps = []
    for k in range(n):
        steps += summ_steps("", call_id=f"ss-{k}")
    return steps


def test_three_invalid_answers_go_to_narrator_backup(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, empty_answers())
    result = rig.runner.play("ход")
    assert result.boundary_failed is False
    assert result.menu is None
    assert rig.runner.bundle.session.boundary_pending is False
    assert rig.runner.bundle.memory.scenes[0].summary == "От рассказчика."
    assert rig.runner.bundle.memory.scenes[0].source == "summarizer"


def test_three_invalid_answers_and_invalid_backup_give_fallback(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + empty_answers()
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, empty_answers())
    result = rig.runner.play("ход")
    scene = rig.runner.bundle.memory.scenes[0]
    assert result.boundary_failed is False
    assert scene.source == "fallback"
    assert scene.summary == "Подсказка."


# Р2: отказ summarizer -> повтор на модели рассказчика -> запасная выжимка

REFUSAL = [{"stop": "refusal"}]


def test_refusal_goes_to_narrator_backup_and_boundary_finishes(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL)
    result = rig.runner.play("ход")
    bundle = rig.runner.bundle
    assert result.boundary_failed is False
    assert result.menu is None
    assert rig.runner.failed_role is None
    assert bundle.session.boundary_pending is False
    assert bundle.session.current_scene.id == "scene_2"
    assert bundle.memory.scenes[0].summary == "От рассказчика."
    assert bundle.memory.scenes[0].source == "summarizer"
    assert "refusal_fallback" in result.report_tags


def test_backup_request_is_summarizer_role_on_narrator_model(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL)
    rig.runner.play("ход")
    backup = rig.narrator_view().summarizer_requests()
    assert len(backup) == 1
    assert backup[0].role == "summarizer"
    assert {t.name for t in backup[0].tools} == {"scene_summary"}
    assert backup[0].model == rig.narrator.requests[0].model
    assert len(rig.summarizer.requests) == 1


def test_journal_has_two_summarizer_records_under_one_boundary_run_id(
    registry, cfg, tmp_path
):
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL)
    rig.runner.play("ход")
    records = rig.summarizer_records()
    assert len(records) == 2
    assert len({r["run_id"] for r in records}) == 1
    assert records[0]["run_id"].startswith("bnd-")
    assert records[1]["requested_model"] == rig.narrator.requests[0].model
    assert records[0]["requested_model"] != records[1]["requested_model"]
    assert [r["call_id"] for r in records] == [
        f"{records[0]['run_id']}-1", f"{records[0]['run_id']}-2"
    ]


def test_both_refused_give_fallback_with_hint_title_and_one_tag(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    bundle.session.current_scene.title = "Название нарратора"
    narrator = end_narrator("Подсказка.") + REFUSAL
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL, bundle=bundle)
    result = rig.runner.play("ход")
    after = rig.runner.bundle
    assert result.boundary_failed is False
    assert result.menu is None
    assert after.memory.scenes[0].summary == "Подсказка."
    assert after.memory.scenes[0].source == "fallback"
    assert after.memory.scenes[0].title == "Название нарратора"
    assert after.session.boundary_pending is False
    assert after.session.current_scene.id == "scene_2"
    assert result.report_tags.count("refusal_fallback") == 1


def test_both_refused_without_hint_give_numbered_scene_line(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator("") + REFUSAL, REFUSAL)
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.scenes[0].summary.startswith("Сцена 1")
    assert rig.runner.bundle.memory.scenes[0].source == "fallback"


def test_both_refused_still_ticks_the_world_day(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary

    calls = []
    original = boundary.tick_days
    monkeypatch.setattr(
        boundary, "tick_days", lambda *a, **k: calls.append(1) or original(*a, **k)
    )
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator("П.") + REFUSAL, REFUSAL)
    rig.runner.play("ход")
    assert calls == [1]


def test_clean_summary_has_no_fallback_tag(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps("Итог."))
    result = rig.runner.play("ход")
    assert "refusal_fallback" not in result.report_tags


def test_fatal_summarizer_still_gives_menu_and_backup_is_not_called(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, summ_fail_steps())
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.failed_role == "summarizer"
    assert rig.runner.bundle.session.boundary_pending is True
    assert rig.narrator_view().summarizer_requests() == []
    assert "refusal_fallback" not in result.report_tags


def test_network_summarizer_still_gives_menu_and_backup_is_not_called(registry, cfg, tmp_path):
    network = [{"error": "transient", "message": "сеть"}] * 4
    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, network)
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert rig.runner.failed_role == "summarizer"
    assert rig.narrator_view().summarizer_requests() == []


def test_backup_fatal_gives_error_menu(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + summ_fail_steps()
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL)
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.bundle.session.boundary_pending is True


def test_no_backup_when_summarizer_is_the_narrator_itself(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator("Подсказка.") + REFUSAL, [])
    rig.runner.summarizer_adapter = rig.narrator
    rig.runner.summarizer_model = rig.runner.model
    result = rig.runner.play("ход")
    assert len(rig.narrator_view().summarizer_requests()) == 1
    assert rig.runner.bundle.memory.scenes[0].source == "fallback"
    assert result.boundary_failed is False


def test_session_has_no_backup_when_adapter_and_model_equal_narrator(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), [])
    rig.runner.summarizer_adapter = rig.narrator
    rig.runner.summarizer_model = rig.runner.model
    assert rig.runner.new_summarizer_session().backup is None


def test_same_adapter_but_other_model_still_has_backup(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), [])
    rig.runner.summarizer_adapter = rig.narrator
    rig.runner.summarizer_model = SONNET
    assert rig.runner.new_summarizer_session().backup is not None


def test_session_without_summarizer_adapter_has_no_session(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), [])
    rig.runner.summarizer_adapter = None
    assert rig.runner.new_summarizer_session() is None


def test_backup_is_built_on_narrator_adapter_and_model(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), summ_steps())
    backup = rig.runner.new_summarizer_session().backup
    assert backup.adapter is rig.narrator
    assert backup.model == rig.runner.model
    assert backup.backup is None


def test_explicit_summarizer_backup_adapter_is_used_with_narrator_model(
    registry, cfg, tmp_path
):
    from game_kit import scripted

    other = scripted(summ_steps("Из явного бэкапа."))
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator("Подсказка."), REFUSAL)
    rig.runner.summarizer_backup = other
    result = rig.runner.play("ход")
    assert result.boundary_failed is False
    assert rig.runner.bundle.memory.scenes[0].summary == "Из явного бэкапа."
    assert other.requests[0].model == rig.runner.model
    assert rig.narrator_view().summarizer_requests() == []


def test_game_app_passes_summarizer_backup_to_runner(registry, tmp_path):
    from game_kit import scripted

    from ai_dm.game.app import GameApp

    other = scripted(summ_steps())
    app = GameApp(
        settings(), registry, make_bundle(registry), scripted([]), saves_root=tmp_path,
        sleeper=lambda s: None, use_stored_model=False, summarizer_backup=other,
    )
    assert app.runner.summarizer_backup is other


def test_default_summarizer_backup_is_none(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), [])
    assert rig.runner.summarizer_backup is None


def test_backup_follows_narrator_changed_by_set_adapter(registry, cfg, tmp_path):
    from game_kit import scripted

    rig = make_summ_rig(registry, cfg, tmp_path, quiet_narrator(), summ_steps())
    new = scripted([])
    rig.runner.set_adapter(new, SONNET)
    backup = rig.runner.new_summarizer_session().backup
    assert backup.adapter is new
    assert backup.model == SONNET


def test_refusing_summarizer_does_not_block_three_turns_in_a_row(registry, cfg, tmp_path):
    narrator = []
    for _ in range(3):
        narrator += end_narrator("Подсказка.") + REFUSAL
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, REFUSAL * 3)
    results = rig.play(3)
    scenes = rig.runner.bundle.memory.scenes
    assert all(r.committed and not r.boundary_failed for r in results)
    assert [s.source for s in scenes] == ["fallback"] * 3
    assert rig.runner.bundle.session.current_scene.id == "scene_4"
    assert rig.runner.bundle.session.turn_seq == 3


def test_pending_boundary_is_finished_by_fallback_on_first_turn(registry, cfg, tmp_path):
    failed_rig(registry, cfg, tmp_path)
    loaded = load_slot(tmp_path, "w1", "auto")
    assert loaded.session.boundary_pending is True
    rig = make_summ_rig(
        registry, cfg, tmp_path, REFUSAL + quiet_narrator(), REFUSAL, bundle=loaded
    )
    result = rig.runner.play("новый ход")
    bundle = rig.runner.bundle
    assert result.committed is True
    assert result.boundary_failed is False
    assert rig.runner.deferred_input is None
    assert bundle.memory.scenes[0].source == "fallback"
    assert bundle.session.current_scene.id == "scene_2"
    assert bundle.session.boundary_pending is False
    assert bundle.memory.recent_turns[-1].player_input == "новый ход"


def test_retry_after_menu_finishes_boundary_with_fallback(registry, cfg, tmp_path):
    rig = failed_rig(
        registry, cfg, tmp_path, summ_fail_steps() + REFUSAL,
        narrator=end_narrator("Подсказка.") + REFUSAL,
    )
    result = rig.runner.retry()
    assert rig.runner.bundle.session.boundary_pending is False
    assert rig.runner.bundle.memory.scenes[0].source == "fallback"
    assert result.boundary_failed is False


def test_player_gets_no_words_about_summary_on_fallback(registry, tmp_path, monkeypatch):
    force_close(monkeypatch, "end_scene")
    narrator = ReactiveNarrator([text_step("Ты идёшь дальше."), REFUSAL[0]])
    app = make_summ_app(registry, tmp_path, narrator, make_scripted_refusal())
    reply = app.handle("Иду")
    shown = "\n".join(reply.lines + [reply.narration]).lower()
    assert reply.turn.boundary_failed is False
    assert "выжимк" not in shown
    assert app.bundle.memory.scenes[0].source == "fallback"


def test_narrator_set_by_model_command_becomes_the_backup(registry, tmp_path, monkeypatch):
    force_close(monkeypatch, "end_scene")
    factory = SummFactory()
    narrator = ReactiveSummarizer()
    app = make_summ_app(
        registry, tmp_path, narrator, make_scripted_refusal(), adapter_factory=factory
    )
    app.handle(f"/model narrator anthropic:{SONNET}")
    reply = app.handle("Иду")
    new = factory.made[0]
    backup = [r for r in new.requests if r.role == "summarizer"]
    assert backup
    assert backup[0].model == SONNET
    assert reply.turn.boundary_failed is False
    assert app.bundle.memory.scenes[0].source == "summarizer"


# модель summarizer

def test_summarizer_model_is_provider_profile(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps())
    rig.runner.play("ход")
    expected = settings().app.profiles["anthropic"].summarizer.model
    assert rig.summarizer_requests()[0].model == expected


def test_explicit_summarizer_model_is_used(registry, cfg, tmp_path):
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_narrator(), summ_steps(), summarizer_model=SONNET
    )
    rig.runner.play("ход")
    assert rig.summarizer_requests()[0].model == SONNET


def test_switch_model_in_menu_changes_summarizer_not_narrator(
    registry, tmp_path, monkeypatch
):
    force_close(monkeypatch, "end_scene")
    narrator = ReactiveSummarizer()
    factory = SummFactory()
    app = make_summ_app(
        registry, tmp_path, narrator, make_scripted_failing(), adapter_factory=factory
    )
    app.handle("Иду")
    assert app.pending == "error_menu"
    app.choose("switch_model")
    app.choose(f"anthropic:{SONNET}")
    reply = app.choose("retry")
    new = factory.made[0]
    summ_requests = [r for r in new.requests if r.role == "summarizer"]
    assert summ_requests[0].model == SONNET
    assert app.runner.adapter is narrator
    assert app.runner.model == narrator.model
    assert reply.turn.boundary_failed is False
    assert app.bundle.memory.scenes[0].source == "summarizer"


def test_model_command_to_other_provider_switches_summarizer_profile(
    registry, tmp_path, monkeypatch
):
    force_close(monkeypatch, "end_scene")
    factory = SummFactory()
    gemini = ReactiveSummarizer(provider="gemini", model="gemini-3.8-flash")
    summarizer = ReactiveSummarizer(provider="gemini", model="gemini-3.8-flash")
    app = make_summ_app(registry, tmp_path, gemini, summarizer, adapter_factory=factory)
    app.handle("/model narrator anthropic:claude-sonnet-5-5")
    app.handle("Иду")
    anthropic_summarizer = settings().app.profiles["anthropic"].summarizer.model
    made = [r for a in factory.made for r in a.requests if r.role == "summarizer"]
    assert made[0].model == anthropic_summarizer
    assert summarizer.requests == []


# журнал

def test_journal_has_summarizer_record_with_boundary_run_id(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), summ_steps())
    rig.runner.play("ход")
    records = rig.summarizer_records()
    assert len(records) == 1
    assert all(r["run_id"].startswith("bnd-") for r in records)
    assert all(r["role"] == "summarizer" for r in records)


def test_failed_boundary_retry_logs_aborted_then_committed(registry, cfg, tmp_path):
    rig = failed_rig(registry, cfg, tmp_path, summ_fail_steps() + summ_steps("Ок."))
    rig.runner.retry()
    statuses = [r["turn_status"] for r in rig.summarizer_records()]
    assert statuses[0] == "aborted"
    assert statuses[-1] == "committed"
    assert len({r["run_id"] for r in rig.summarizer_records()}) == 2


def test_replay_of_boundary_by_role_gives_same_memory(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    first = make_summ_rig(
        registry, cfg, tmp_path / "a", end_narrator("Подсказка."), summ_steps("Выжимка.", "Т")
    )
    first.runner.play("ход")
    records = first.journal.read_records()
    replay = ReplayAdapter(records, role="summarizer")
    model = first.summarizer_records()[0]["requested_model"]
    second = make_summ_rig(
        registry, cfg, tmp_path / "b", end_narrator("Подсказка."), replay,
        summarizer_model=model,
    )
    second.runner.play("ход")
    assert dumps(first.runner.bundle.memory) == dumps(second.runner.bundle.memory)
    assert dumps(first.runner.bundle.session) == dumps(second.runner.bundle.session)


# мок-сценарий из tests/fixtures/scripts

def test_yaml_script_gives_three_summaries(registry, cfg, tmp_path):
    from game_kit import SCRIPTS, Recorder

    from ai_dm.llm.mock import ScriptedAdapter, load_script

    adapter = Recorder(
        ScriptedAdapter(
            load_script(SCRIPTS / "summarizer_scene.yaml"), provider="anthropic",
            model="claude-opus-5-5",
        )
    )
    steps = end_narrator() * 3
    rig = make_summ_rig(registry, cfg, tmp_path, steps, adapter)
    rig.play(3)
    scenes = rig.runner.bundle.memory.scenes
    assert [s.summary for s in scenes] == [
        "Выжимка первой сцены.", "Выжимка второй сцены.", "Выжимка третьей сцены.",
    ]
    assert scenes[0].title == "Первая сцена"


# помощники этого файла

class SummFactory(FactorySpy):
    # адаптеры /model и меню 2.2: ReactiveSummarizer с запрошенными provider/model
    def __call__(self, provider, model):
        self.calls.append((provider, model))
        adapter = ReactiveSummarizer(provider=provider, model=model)
        self.made.append(adapter)
        return adapter


def make_scripted_failing():
    from game_kit import scripted

    return scripted(summ_fail_steps())


def make_scripted_refusal():
    from game_kit import scripted

    return scripted([{"stop": "refusal"}])


class ReactiveNarrator(ReactiveSummarizer):
    # рассказчик по шагам для app-тестов: сначала шаги, затем (запасной вызов summarizer) отказ
    def __init__(self, steps):
        super().__init__()
        from game_kit import scripted

        self.script = scripted(steps)

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        return self.script.complete(request)


def test_meta_context_is_only_on_narrator_records(registry, cfg, tmp_path):
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_narrator("Подсказка."), summ_steps("Выжимка.", "Т")
    )
    rig.runner.app_cfg.master.context_cap = 1
    rig.runner.play("ход")
    records = rig.journal.read_records()
    narrator = [r for r in records if r["role"] == "narrator"]
    others = [r for r in records if r["role"] != "narrator"]
    assert narrator
    assert all("context" in r["meta"] for r in narrator)
    assert rig.summarizer_records()
    assert all(r["meta"] == {} for r in others)
    assert all("context_overflow" not in r["report_tags"] for r in others)


def test_replay_of_boundary_with_backup_gives_same_memory(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    narrator = end_narrator("Подсказка.") + summ_steps("От рассказчика.")
    first = make_summ_rig(registry, cfg, tmp_path / "a", narrator, REFUSAL)
    first.runner.play("ход")
    replay = ReplayAdapter(first.journal.read_records(), role="summarizer")
    model = first.summarizer_records()[0]["requested_model"]
    second = make_summ_rig(
        registry, cfg, tmp_path / "b", end_narrator("Подсказка."), replay,
        summarizer_model=model,
    )
    second.runner.summarizer_backup = replay
    second.runner.play("ход")
    assert dumps(first.runner.bundle.memory) == dumps(second.runner.bundle.memory)
    assert dumps(first.runner.bundle.session) == dumps(second.runner.bundle.session)
    assert second.runner.bundle.memory.scenes[0].summary == "От рассказчика."
