# Ожидаемый API (П2 этапа 3, STAGE3-PLAN A5, ARCHITECTURE D3): ai_dm.game.boundary.
# Граница сцены внутри TurnRunner: close_scene -> save_auto (boundary_pending=True) -> на копии
# start_scene и глава -> boundary_pending=False. Шпионы ставятся на имена модуля
# ai_dm.game.boundary: close_scene, save_auto, start_scene (как их импортирует game.turn).
# Допущения: ChapterState.scene_count считает сцены главы, включая текущую (у scene_1 главы -- 1);
# сцена закрывает главу, когда scene_count == cfg.scene.max_per_chapter; пустой summary
# в memory.scenes запись не добавляет.
import pytest
from game_kit import (
    advance_call,
    end_scene_call,
    make_app,
    make_rig,
    scripted,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle
from slots_kit import list_slots, saved_close_reason

from ai_dm.persistence.store import load_slot, save_slot
from ai_dm.state.session import ChapterState

ERROR_MENU = ["retry", "switch_model", "save_and_quit"]


def chapter_bundle(registry, count=1):
    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id="chapter_1", number=1, started_at_s=0, scene_count=count
    )
    return bundle


def end_chapter_call(title="Конец пролога", call_id="ec-1"):
    return {
        "id": call_id, "name": "end_chapter",
        "input": {"type": "end_chapter", "title": title},
    }


def play_many(registry, cfg, tmp_path, steps, turns, bundle=None):
    rig = make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)
    results = [rig.runner.play(f"ход {n}") for n in range(turns)]
    return rig, results


# порядок границы

def test_boundary_order_close_then_autosave_then_new_scene(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary

    calls = []

    def spy(name, original, *, pending=False):
        def wrapper(*args, **kwargs):
            if pending:
                calls.append((name, args[1].session.boundary_pending))
            else:
                calls.append((name, None))
            return original(*args, **kwargs)

        return wrapper

    monkeypatch.setattr(boundary, "close_scene", spy("close", boundary.close_scene))
    monkeypatch.setattr(boundary, "save_auto", spy("save", boundary.save_auto, pending=True))
    monkeypatch.setattr(boundary, "start_scene", spy("start", boundary.start_scene))
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    play_many(registry, cfg, tmp_path, steps, 1)
    assert [name for name, _ in calls] == ["close", "save", "start"]
    assert calls[1][1] is True


def test_autosave_of_closed_scene_has_boundary_pending(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    play_many(registry, cfg, tmp_path, steps, 1)
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.session.boundary_pending is True
    assert saved.session.current_scene.closed_reason == "end_scene"


def test_finished_boundary_clears_pending_and_opens_scene(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1)
    session = rig.runner.bundle.session
    assert session.boundary_pending is False
    assert session.current_scene.id == "scene_2"


def test_quiet_turn_has_no_boundary(registry, cfg, tmp_path):
    rig, _ = play_many(registry, cfg, tmp_path, [text_step()], 1)
    assert rig.runner.bundle.session.boundary_pending is False
    assert rig.runner.bundle.memory.scenes == []


# выжимка сцены

def test_scene_summary_goes_to_memory_scenes(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call(summary="Герой договорился с трактирщиком.")), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    scenes = rig.runner.bundle.memory.scenes
    assert len(scenes) == 1
    assert scenes[0].id == "scene_1"
    assert scenes[0].summary == "Герой договорился с трактирщиком."
    assert scenes[0].chapter_id == "chapter_1"


def test_autosave_of_closed_scene_has_hint_not_memory_summary(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call(summary="Выжимка.")), text_step()]
    play_many(registry, cfg, tmp_path, steps, 1)
    # этап 4: выжимку пишет шаг 1 границы после автосейва; в сейве -- подсказка нарратора
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.memory.scenes == []
    assert saved.session.current_scene.summary == "Выжимка."


def test_scene_without_summary_gets_fallback_summary(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1)
    scenes = rig.runner.bundle.memory.scenes
    assert len(scenes) == 1
    assert scenes[0].source == "fallback"
    assert scenes[0].summary.startswith("Сцена 1")


def test_safety_closing_scene_without_summary_gets_fallback(registry, cfg, tmp_path):
    steps = [tools_step(advance_call(category="day")), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1)
    assert saved_close_reason(tmp_path, "w1") == "time_jump"
    assert [s.source for s in rig.runner.bundle.memory.scenes] == ["fallback"]


# главы

def test_end_chapter_with_end_scene_closes_chapter(registry, cfg, tmp_path):
    steps = [
        tools_step(end_scene_call(summary="Раз."), end_chapter_call("Пролог")), text_step(),
    ]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    bundle = rig.runner.bundle
    assert len(bundle.memory.chapters) == 1
    summary = bundle.memory.chapters[0]
    assert summary.id == "chapter_1"
    assert summary.number == 1
    assert summary.title == "Пролог"
    assert "Раз." in summary.summary
    chapter = bundle.session.current_chapter
    assert chapter.number == 2
    assert chapter.closed_reason is None
    assert chapter.id != "chapter_1"
    assert chapter.started_at_s == bundle.world.clock.now_s


def test_chapter_summary_joins_summaries_of_its_scenes(registry, cfg, tmp_path):
    steps = [
        tools_step(end_scene_call("e1", summary="Первая сцена.")), text_step(),
        tools_step(end_scene_call("e2", summary="Вторая сцена."), end_chapter_call("Глава")),
        text_step(),
    ]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 2, bundle=chapter_bundle(registry))
    summary = rig.runner.bundle.memory.chapters[0].summary
    assert "Первая сцена." in summary
    assert "Вторая сцена." in summary
    assert summary.index("Первая сцена.") < summary.index("Вторая сцена.")


def test_end_chapter_alone_does_not_close_scene(registry, cfg, tmp_path):
    steps = [tools_step(end_chapter_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.current_scene.id == "scene_1"


def test_end_chapter_waits_for_nearest_boundary(registry, cfg, tmp_path):
    steps = [
        tools_step(end_chapter_call("Позже")), text_step(),
        tools_step(end_scene_call()), text_step(),
    ]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 2, bundle=chapter_bundle(registry))
    bundle = rig.runner.bundle
    assert [chapter.title for chapter in bundle.memory.chapters] == ["Позже"]
    assert bundle.session.current_chapter.number == 2


def test_chapter_stays_open_before_scene_limit(registry, cfg, tmp_path):
    cfg2 = cfg.model_copy(deep=True)
    cfg2.scene.max_per_chapter = 3
    steps = [tools_step(end_scene_call("e1")), text_step()]
    steps += [tools_step(end_scene_call("e2")), text_step()]
    rig, _ = play_many(registry, cfg2, tmp_path, steps, 2, bundle=chapter_bundle(registry))
    assert rig.runner.bundle.memory.chapters == []
    assert rig.runner.bundle.session.current_chapter.number == 1


def test_scene_limit_closes_chapter(registry, cfg, tmp_path):
    cfg2 = cfg.model_copy(deep=True)
    cfg2.scene.max_per_chapter = 3
    steps = []
    for n in range(3):
        steps += [tools_step(end_scene_call(f"e{n}", summary=f"Сцена {n}.")), text_step()]
    rig, _ = play_many(registry, cfg2, tmp_path, steps, 3, bundle=chapter_bundle(registry))
    bundle = rig.runner.bundle
    assert len(bundle.memory.chapters) == 1
    assert bundle.memory.chapters[0].number == 1
    assert bundle.session.current_chapter.number == 2
    assert bundle.session.current_scene.id == "scene_4"


def test_scene_limit_is_15_by_default(cfg):
    assert cfg.scene.max_per_chapter == 15


def test_scene_limit_chapter_closes_after_autosave(registry, cfg, tmp_path):
    # глава закрывается в шаге 3, после автосейва: в сейве она ещё прежняя
    cfg2 = cfg.model_copy(deep=True)
    cfg2.scene.max_per_chapter = 1
    steps = [tools_step(end_scene_call()), text_step()]
    rig, _ = play_many(registry, cfg2, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.session.current_chapter.number == 1
    assert saved.session.boundary_pending is True
    assert rig.runner.bundle.session.current_chapter.number == 2


def test_new_chapter_starts_scene_count_with_new_scene(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call(), end_chapter_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    assert rig.runner.bundle.session.current_chapter.scene_count == 1


def test_scene_count_grows_with_scenes(registry, cfg, tmp_path):
    steps = [tools_step(end_scene_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    assert rig.runner.bundle.session.current_chapter.scene_count == 2


# сбой границы и достройка

def test_failure_in_step_3_keeps_state_as_after_autosave(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(bundle, npcs_before=None):
        raise TurnFailed("fatal", "сбой границы")

    monkeypatch.setattr(boundary, "start_scene", broken)
    steps = [tools_step(end_scene_call(summary="Выжимка.")), text_step("Конец.")]
    rig, result = play_many(registry, cfg, tmp_path, steps, 1)
    bundle = rig.runner.bundle
    assert result[0].menu == ERROR_MENU
    assert bundle.session.boundary_pending is True
    assert bundle.session.current_scene.id == "scene_1"
    assert bundle.session.current_scene.closed_reason == "end_scene"
    assert bundle.session.turn_seq == 1
    assert load_slot(tmp_path, "w1", "auto").session.boundary_pending is True


def test_failure_in_step_3_keeps_the_clock_of_the_autosave(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(bundle, npcs_before=None):
        raise TurnFailed("fatal", "сбой границы")

    monkeypatch.setattr(boundary, "start_scene", broken)
    steps = [tools_step(end_scene_call(summary="Выжимка.")), text_step("Конец.")]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1)
    assert rig.runner.bundle.world.clock.now_s == load_slot(
        tmp_path, "w1", "auto"
    ).world.clock.now_s


def test_turn_interrupted_on_pending_boundary_does_not_move_the_clock(
    registry, cfg, tmp_path, monkeypatch
):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(bundle, npcs_before=None):
        raise TurnFailed("fatal", "сбой границы")

    monkeypatch.setattr(boundary, "start_scene", broken)
    steps = [tools_step(end_scene_call(summary="Выжимка.")), text_step("Конец."), text_step("Ещё.")]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1)
    assert rig.runner.bundle.session.boundary_pending is True
    after_first = rig.runner.bundle.world.clock.now_s
    result = rig.runner.play("ещё ход")
    assert result.committed is False
    assert rig.runner.bundle.session.boundary_pending is True
    assert rig.runner.bundle.world.clock.now_s == after_first


def test_failure_in_step_3_rolls_back_chapter(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(bundle, npcs_before=None):
        raise TurnFailed("fatal", "сбой границы")

    monkeypatch.setattr(boundary, "start_scene", broken)
    steps = [tools_step(end_scene_call(), end_chapter_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=chapter_bundle(registry))
    bundle = rig.runner.bundle
    assert bundle.session.current_chapter.number == 1
    assert bundle.memory.chapters == []


# Фикс dusk П2 (173): множество NPC сцены снимается до tick_days/call_world, метка переносится

def mood_pending(registry, cfg, mood="romance"):
    from ai_dm.game.boundary import close_boundary

    bundle = chapter_bundle(registry)
    bundle.session.current_scene.scene_mood = mood
    close_boundary(bundle, cfg, "end_scene")
    return bundle


def test_finish_boundary_passes_scene_npcs_to_start_scene(registry, cfg, monkeypatch):
    import ai_dm.game.boundary as boundary

    seen = {}

    def spy(bundle, npcs_before=None):
        seen["npcs"] = npcs_before
        return boundary_start(bundle, npcs_before=npcs_before)

    boundary_start = boundary.start_scene
    monkeypatch.setattr(boundary, "start_scene", spy)
    bundle = mood_pending(registry, cfg)
    boundary.finish_boundary(bundle, cfg, registry)
    assert seen["npcs"] == {"grakh"}


def test_finish_boundary_carries_mood_to_new_scene(registry, cfg):
    from ai_dm.game.boundary import finish_boundary

    bundle = mood_pending(registry, cfg)
    result = finish_boundary(bundle, cfg, registry)
    assert result.error is None
    assert result.bundle.session.current_scene.id == "scene_2"
    assert result.bundle.session.current_scene.scene_mood == "romance"


def test_finish_boundary_without_mood_leaves_new_scene_empty(registry, cfg):
    from ai_dm.game.boundary import finish_boundary

    bundle = mood_pending(registry, cfg, mood="")
    assert finish_boundary(bundle, cfg, registry).bundle.session.current_scene.scene_mood == ""


def test_npc_leaving_during_boundary_drops_mood(registry, cfg, monkeypatch):
    # снимок NPC взят до tick_days: ушедший за границу NPC снимает метку
    import ai_dm.game.boundary as boundary

    def tick(work, cfg, registry):
        work.world.npcs["grakh"].location_id = "forest"

    monkeypatch.setattr(boundary, "tick_days", tick)
    bundle = mood_pending(registry, cfg)
    scene = boundary.finish_boundary(bundle, cfg, registry).bundle.session.current_scene
    assert scene.scene_mood == ""


def test_npc_killed_during_boundary_drops_mood(registry, cfg, monkeypatch):
    import ai_dm.game.boundary as boundary

    def tick(work, cfg, registry):
        work.world.npcs["grakh"].status = "dead"

    monkeypatch.setattr(boundary, "tick_days", tick)
    bundle = mood_pending(registry, cfg)
    scene = boundary.finish_boundary(bundle, cfg, registry).bundle.session.current_scene
    assert scene.scene_mood == ""


def test_npc_arriving_during_boundary_keeps_mood(registry, cfg, monkeypatch):
    import ai_dm.game.boundary as boundary

    def tick(work, cfg, registry):
        work.world.npcs["aldric"].location_id = "vale"

    monkeypatch.setattr(boundary, "tick_days", tick)
    bundle = mood_pending(registry, cfg)
    scene = boundary.finish_boundary(bundle, cfg, registry).bundle.session.current_scene
    assert scene.scene_mood == "romance"


def test_hero_moving_during_boundary_drops_mood(registry, cfg, monkeypatch):
    import ai_dm.game.boundary as boundary

    def tick(work, cfg, registry):
        work.heroes[0].location_id = "forest"

    monkeypatch.setattr(boundary, "tick_days", tick)
    bundle = mood_pending(registry, cfg)
    scene = boundary.finish_boundary(bundle, cfg, registry).bundle.session.current_scene
    assert scene.scene_mood == ""


def pending_slot(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry)
    bundle.session.current_scene.closed_reason = "end_scene"
    bundle.session.boundary_pending = True
    bundle.world.clock.advance(600)
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")


def test_load_finishes_pending_boundary(registry, cfg, tmp_path):
    pending_slot(registry, cfg, tmp_path)
    app = make_app(registry, tmp_path, scripted([text_step()]))
    app.load("auto")
    session = app.bundle.session
    assert session.boundary_pending is False
    assert session.current_scene.id == "scene_2"
    assert session.current_scene.closed_reason is None


def test_load_pending_boundary_closes_chapter_by_limit(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry, count=cfg.scene.max_per_chapter)
    bundle.session.current_scene.closed_reason = "end_scene"
    bundle.session.boundary_pending = True
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")
    app = make_app(registry, tmp_path, scripted([text_step()]))
    app.load("auto")
    assert app.bundle.session.current_chapter.number == 2
    assert len(app.bundle.memory.chapters) == 1


def test_load_without_pending_boundary_changes_no_chapter(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry)
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")
    app = make_app(registry, tmp_path, scripted([text_step()]))
    app.load("auto")
    assert app.bundle.session.current_chapter.number == 1
    assert app.bundle.session.current_scene.id == "scene_1"


# смерть героя

def test_hero_dead_runs_no_boundary(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    bundle.heroes[0].status = "dead"
    steps = [tools_step(end_scene_call()), text_step()]
    rig, _ = play_many(registry, cfg, tmp_path, steps, 1, bundle=bundle)
    assert saved_close_reason(tmp_path, "w1") is None
    assert rig.runner.bundle.session.boundary_pending is False
    assert rig.runner.bundle.session.current_scene.id == "scene_1"
    assert list_slots(tmp_path, "w1") == []


# ревью П2: B1, D2, D3, D5

def break_tick(monkeypatch, error):
    import ai_dm.game.boundary as boundary

    state = {"broken": True}

    def tick(work, cfg, registry):
        if state["broken"]:
            raise error

    monkeypatch.setattr(boundary, "tick_days", tick)
    return state


def pending_bundle(registry, cfg, summary="Выжимка первой."):
    from ai_dm.game.boundary import close_boundary

    bundle = chapter_bundle(registry)
    bundle.session.current_scene.summary = summary
    close_boundary(bundle, cfg, "end_scene")
    return bundle


def old_save_without_chapter(registry, tmp_path):
    bundle = make_bundle(registry)
    bundle.world.clock.advance(500)
    bundle.session.current_scene.started_at_s = 100
    assert bundle.session.current_chapter is None
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")


def test_old_save_without_chapter_gets_chapter_1_on_load(registry, cfg, tmp_path):
    old_save_without_chapter(registry, tmp_path)
    app = make_app(registry, tmp_path, scripted([text_step()]))
    app.load("auto")
    chapter = app.bundle.session.current_chapter
    assert chapter.number == 1
    assert chapter.id == "ch_1"
    assert chapter.started_at_s == 100
    assert chapter.scene_count == 1


def test_end_chapter_after_loading_old_save_writes_title_and_reason(registry, cfg, tmp_path):
    old_save_without_chapter(registry, tmp_path)
    steps = [tools_step(end_chapter_call("Старая")), text_step()]
    app = make_app(registry, tmp_path, scripted(steps))
    app.load("auto")
    app.runner.play("ход")
    chapter = app.bundle.session.current_chapter
    assert chapter.number == 1
    assert chapter.title == "Старая"
    assert chapter.closed_reason == "end_chapter"


def test_first_scene_summary_enters_summary_of_restored_chapter(registry, cfg, tmp_path):
    old_save_without_chapter(registry, tmp_path)
    steps = [
        tools_step(end_scene_call(summary="Первая сцена старого мира."), end_chapter_call("Т")),
        text_step(),
    ]
    app = make_app(registry, tmp_path, scripted(steps))
    app.load("auto")
    app.runner.play("ход")
    summary = app.bundle.memory.chapters[0]
    assert summary.number == 1
    assert "Первая сцена старого мира." in summary.summary
    assert app.bundle.session.current_chapter.number == 2


def test_close_boundary_restores_missing_chapter(registry, cfg):
    from ai_dm.game.boundary import close_boundary

    bundle = make_bundle(registry)
    close_boundary(bundle, cfg, "end_scene")
    assert bundle.session.current_chapter.number == 1
    assert bundle.session.boundary_pending is True


def test_unexpected_error_in_boundary_propagates(registry, cfg, tmp_path, monkeypatch):
    break_tick(monkeypatch, RuntimeError("баг"))
    steps = [tools_step(end_scene_call(summary="Выжимка.")), text_step("Конец.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    with pytest.raises(RuntimeError):
        rig.runner.play("ход")
    session = rig.runner.bundle.session
    assert session.boundary_pending is True
    assert session.current_scene.id == "scene_1"
    assert session.current_scene.closed_reason == "end_scene"
    assert load_slot(tmp_path, "w1", "auto").session.boundary_pending is True


def test_expected_error_in_boundary_goes_to_menu(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.master.session import TurnFailed

    break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    steps = [tools_step(end_scene_call()), text_step("Конец.")]
    rig = make_rig(registry, cfg, tmp_path, scripted(steps))
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.bundle.session.boundary_pending is True


def test_input_is_not_lost_when_resume_fails_in_run_turn(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.master.session import TurnFailed

    state = break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    bundle = pending_bundle(registry, cfg)
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Ход сыгран.")]), bundle=bundle)
    result = rig.runner.play("Иду дальше")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.deferred_input == "Иду дальше"
    assert rig.runner.bundle.session.turn_seq == 0
    state["broken"] = False
    retried = rig.runner.retry()
    session = rig.runner.bundle.session
    assert retried.committed is True
    assert retried.narration == "Ход сыгран."
    assert session.boundary_pending is False
    assert session.current_scene.id == "scene_2"
    assert session.turn_seq == 1
    assert session.current_scene.player_turns == 1
    assert len(rig.runner.bundle.memory.scenes) == 1
    assert rig.runner.deferred_input is None


def test_retry_after_boundary_failure_marks_journal(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.master.session import TurnFailed

    state = break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    bundle = pending_bundle(registry, cfg)
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step("Ход сыгран.")]), bundle=bundle)
    rig.runner.play("Иду")
    state["broken"] = False
    retried = rig.runner.retry()
    records = [r for r in rig.journal.read_records() if r["run_id"] == retried.run_id]
    assert records
    assert {r["turn_status"] for r in records} == {"committed"}


def test_retry_with_failing_boundary_stays_pending(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.master.session import TurnFailed

    break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    bundle = pending_bundle(registry, cfg)
    rig = make_rig(registry, cfg, tmp_path, scripted([text_step()]), bundle=bundle)
    rig.runner.play("Иду")
    retried = rig.runner.retry()
    assert retried.boundary_failed is True
    assert retried.menu == ERROR_MENU
    assert rig.runner.bundle.session.boundary_pending is True
    assert rig.runner.bundle.session.turn_seq == 0


def test_retry_through_game_app_finishes_boundary_and_plays_input(
    registry, cfg, tmp_path, monkeypatch
):
    from ai_dm.master.session import TurnFailed

    state = break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    bundle = pending_bundle(registry, cfg)
    app = make_app(registry, tmp_path, scripted([text_step("Ход сыгран.")]), bundle=bundle)
    reply = app.handle("Иду")
    assert app.pending == "error_menu"
    assert reply.menu == ERROR_MENU
    state["broken"] = False
    reply = app.choose("retry")
    assert app.pending is None
    assert reply.narration == "Ход сыгран."
    assert app.bundle.session.boundary_pending is False
    assert app.bundle.session.turn_seq == 1


def test_load_with_failing_resume_shows_error_menu(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.master.session import TurnFailed

    break_tick(monkeypatch, TurnFailed("fatal", "нет связи"))
    save_slot(tmp_path, pending_bundle(registry, cfg), "auto", saved_at="2026-01-01T12:00:00Z")
    app = make_app(registry, tmp_path, scripted([text_step()]))
    app.load("auto")
    assert app.pending == "error_menu"
    assert app.bundle.session.boundary_pending is True


# откат: сбой после check_triggers (update_nudge / close_chapter) не оставляет следов триггеров
# в исходном бандле (граница идёт на копии)

def mini_for_rollback(registry, cfg):
    import sys
    from pathlib import Path

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "world_sim"))
    from world_sim_kit import mini_bundle

    bundle = mini_bundle(registry, cfg)
    bundle.world.flags.update({"grail_seen": True, "pilgrim_prayed": True})
    return bundle


@pytest.mark.parametrize("step", ["update_nudge", "close_chapter"])
def test_failure_after_check_triggers_leaves_no_trigger_traces(
    registry, cfg, tmp_path, monkeypatch, step
):
    import ai_dm.game.boundary as boundary
    from ai_dm.master.session import TurnFailed

    def broken(*args, **kwargs):
        raise TurnFailed("network", "обрыв")

    monkeypatch.setattr(boundary, step, broken)
    bundle = mini_for_rollback(registry, cfg)
    boundary.close_boundary(bundle, cfg, "end_scene")
    result = boundary.finish_boundary(bundle, cfg, registry)
    assert result.error
    assert result.bundle is bundle
    assert bundle.world.fired == []
    assert bundle.chronicle.entries == []
    assert bundle.world.sim.god_checked_s == {}
    assert bundle.world.npcs["aldric"].opportunity[0].fired_count == 0
    assert bundle.world.pantheon["selune"].opportunity[0].fired_count == 0
    assert bundle.session.boundary_pending is True
