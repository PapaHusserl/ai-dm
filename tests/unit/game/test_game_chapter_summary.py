# Ожидаемый API (этап 4, P2): свёртка главы на шаге 3 границы сцены. Контракт и помощники --
# chapter_kit.py и summarizer_kit.py. Мок без сети: ScriptedAdapter / ReactiveChapterSummarizer.
import pytest
from chapter_kit import (
    ReactiveChapterSummarizer,
    chapter_bundle,
    chapter_requests,
    chapter_steps,
    chapter_summary_call,
    end_scene_and_chapter,
    fresh,
    full_text,
    game_summary_call,
    only_chapter_steps,
    only_game_steps,
    scene_requests,
)
from game_kit import core_dump, end_scene_call, scripted, text_step, tools_step
from summarizer_kit import (
    dumps,
    has_tool_error,
    make_summ_rig,
    request_text,
    summ_fail_steps,
    summ_steps,
)

from ai_dm.persistence.store import load_slot, save_slot
from ai_dm.state.memory import SceneSummary

ERROR_MENU = ["retry", "switch_model", "save_and_quit"]
REFUSAL = [{"stop": "refusal"}]


def limit_cfg(cfg, n):
    cfg2 = cfg.model_copy(deep=True)
    cfg2.scene.max_per_chapter = n
    return cfg2


def close_rig(registry, cfg, tmp_path, summarizer, title="Пролог", bundle=None, backup=None):
    # backup -- шаги рассказчика для запасного вызова summarizer на модели рассказчика (Р2)
    rig = make_summ_rig(
        registry, cfg, tmp_path, end_scene_and_chapter(title) + (backup or []),
        summarizer, bundle=bundle or chapter_bundle(registry),
    )
    return rig


def failed_chapter_rig(registry, cfg, tmp_path, summarizer=None, bundle=None):
    steps = summ_steps("Сцена.") + (summarizer or summ_fail_steps())
    rig = close_rig(registry, cfg, tmp_path, steps, bundle=bundle)
    rig.runner.play("ход")
    return rig


# end_chapter -> один вызов с двумя инструментами

def test_end_chapter_calls_summarizer_for_chapter_with_both_tools(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ход")
    assert len(fresh(scene_requests(rig))) == 1
    requests = fresh(chapter_requests(rig))
    assert len(requests) == 1
    assert requests[0].role == "summarizer"


def test_end_chapter_writes_chapter_summary_with_source_summarizer(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(chapter="Итог главы.")
    )
    rig.runner.play("ход")
    chapters = rig.runner.bundle.memory.chapters
    assert len(chapters) == 1
    assert chapters[0].summary == "Итог главы."
    assert chapters[0].source == "summarizer"
    assert chapters[0].number == 1
    assert chapters[0].id == "chapter_1"


def test_end_chapter_writes_game_summary_and_chapter_number(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(game="Игра целиком.")
    )
    rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert memory.game_summary == "Игра целиком."
    assert memory.game_summary_chapter == 1


def test_game_summary_is_replaced_not_appended(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry)
    bundle.memory.game_summary = "ПРЕЖНЯЯ СВЁРТКА"
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(game="Новая."), bundle=bundle
    )
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.game_summary == "Новая."


def test_game_summary_chapter_follows_chapter_number(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry, number=3)
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(), bundle=bundle)
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.game_summary_chapter == 3
    assert rig.runner.bundle.session.current_chapter.number == 4


def test_chapter_title_of_narrator_has_priority(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(title="Название ИИ"),
        title="Пролог",
    )
    result = rig.runner.play("ход")
    assert result.chapter_title == "Пролог"
    assert rig.runner.bundle.memory.chapters[0].title == "Пролог"


def test_chapter_title_from_summarizer_when_narrator_gave_none(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(title="Название ИИ"),
        title="",
    )
    rig.runner.play("ход")
    assert rig.runner.bundle.memory.chapters[0].title == "Название ИИ"


def test_chapter_closed_and_new_scene_started_after_summary(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ход")
    session = rig.runner.bundle.session
    assert session.boundary_pending is False
    assert session.current_chapter.number == 2
    assert session.current_scene.id == "scene_2"


def test_chapter_call_goes_after_world_and_before_new_scene(
    registry, cfg, tmp_path, monkeypatch
):
    import ai_dm.game.boundary as boundary

    events = []
    start = boundary.start_scene
    world = boundary.call_world

    def spy_start(*args, **kwargs):
        events.append("start_scene")
        return start(*args, **kwargs)

    def spy_world(*args, **kwargs):
        events.append("call_world")
        return world(*args, **kwargs)

    monkeypatch.setattr(boundary, "start_scene", spy_start)
    monkeypatch.setattr(boundary, "call_world", spy_world)

    class Spying(ReactiveChapterSummarizer):
        def complete(self, request):
            names = {t.name for t in request.tools}
            if request.role == "summarizer" and "chapter_summary" in names:
                events.append("chapter")
            elif request.role == "summarizer":
                events.append("scene")
            return super().complete(request)

    rig = close_rig(registry, cfg, tmp_path, Spying())
    rig.runner.play("ход")
    deduped = [e for i, e in enumerate(events) if i == 0 or e != events[i - 1]]
    assert deduped == ["scene", "call_world", "chapter", "start_scene"]


# ответ только с одним инструментом -- невалидный

@pytest.mark.parametrize("partial", [only_chapter_steps, only_game_steps])
def test_answer_with_one_tool_is_invalid_and_retried(partial, registry, cfg, tmp_path):
    steps = summ_steps("Сцена.") + partial("1") + chapter_steps(
        chapter="После повтора.", game="Свёртка после повтора.", suffix="2"
    )
    rig = close_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("ход")
    requests = chapter_requests(rig)
    assert len(requests) >= 2
    assert rig.runner.bundle.memory.game_summary == "Свёртка после повтора."
    assert rig.runner.bundle.memory.chapters[0].summary == "После повтора."
    assert rig.runner.bundle.memory.chapters[0].source == "summarizer"


@pytest.mark.parametrize("partial", [only_chapter_steps, only_game_steps])
def test_three_one_tool_answers_go_to_concat_and_game_summary_stays(
    partial, registry, cfg, tmp_path
):
    steps = summ_steps("Сцена.") + partial("1") + partial("2") + partial("3")
    rig = close_rig(registry, cfg, tmp_path, steps, backup=REFUSAL)
    result = rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert result.boundary_failed is False
    assert result.menu is None
    assert [c.source for c in memory.chapters] == ["concat"]
    assert memory.chapters[0].summary == "Сцена."
    assert memory.game_summary == ""
    assert memory.game_summary_chapter == 0


# scope входа: выжимки сцен главы + прежний game_summary

def test_chapter_input_has_scene_summaries_of_this_chapter_and_old_game_summary(
    registry, cfg, tmp_path
):
    bundle = chapter_bundle(registry, count=3)
    bundle.memory.game_summary = "ПРЕЖНЯЯ СВЁРТКА ИГРЫ"
    bundle.memory.scenes = [
        SceneSummary(id="s_a", chapter_id="chapter_1", summary="СЦЕНА ГЛАВЫ А"),
        SceneSummary(id="s_b", chapter_id="chapter_1", summary="СЦЕНА ГЛАВЫ Б"),
        SceneSummary(id="s_x", chapter_id="chapter_0", summary="СЦЕНА ЧУЖОЙ ГЛАВЫ"),
    ]
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("СВЕЖАЯ ВЫЖИМКА ШАГА 1.") + chapter_steps(),
        title="Пролог", bundle=bundle,
    )
    rig.runner.play("ход")
    text = full_text(chapter_requests(rig)[0])
    assert "СЦЕНА ГЛАВЫ А" in text
    assert "СЦЕНА ГЛАВЫ Б" in text
    assert "СВЕЖАЯ ВЫЖИМКА ШАГА 1." in text
    assert "ПРЕЖНЯЯ СВЁРТКА ИГРЫ" in text
    assert "СЦЕНА ЧУЖОЙ ГЛАВЫ" not in text


def test_chapter_input_has_chapter_title(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(), title="Особое название"
    )
    rig.runner.play("ход")
    assert "Особое название" in full_text(chapter_requests(rig)[0])


def test_scene_request_does_not_get_chapter_tools(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ход")
    assert {t.name for t in scene_requests(rig)[0].tools} == {"scene_summary"}


# scene_limit

def test_scene_limit_closes_chapter_with_summarizer(registry, cfg, tmp_path):
    cfg2 = limit_cfg(cfg, 3)
    bundle = chapter_bundle(registry, count=3)
    rig = make_summ_rig(
        registry, cfg2, tmp_path, [tools_step(end_scene_call()), text_step("Конец.")],
        summ_steps("Сцена.") + chapter_steps(chapter="По лимиту.", game="Свёртка лимита."),
        bundle=bundle,
    )
    rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert [c.source for c in memory.chapters] == ["summarizer"]
    assert memory.chapters[0].summary == "По лимиту."
    assert memory.game_summary == "Свёртка лимита."
    assert memory.game_summary_chapter == 1
    assert len(fresh(chapter_requests(rig))) == 1


def test_scene_below_limit_does_not_call_chapter_summary(registry, cfg, tmp_path):
    cfg2 = limit_cfg(cfg, 3)
    rig = make_summ_rig(
        registry, cfg2, tmp_path, [tools_step(end_scene_call()), text_step("Конец.")],
        summ_steps("Сцена."), bundle=chapter_bundle(registry, count=1),
    )
    rig.runner.play("ход")
    assert chapter_requests(rig) == []
    assert rig.runner.bundle.memory.chapters == []
    assert rig.runner.bundle.memory.game_summary == ""


def test_default_limit_15_scenes_close_chapter_and_input_has_all_scene_summaries(
    registry, cfg, tmp_path
):
    narrator = [tools_step(end_scene_call(f"e{n}")) for n in range(15)]
    steps = []
    for step in narrator:
        steps += [step, text_step("Конец.")]
    summarizer = ReactiveChapterSummarizer()
    rig = make_summ_rig(
        registry, cfg, tmp_path, steps, summarizer, bundle=chapter_bundle(registry, count=1)
    )
    rig.play(15)
    memory = rig.runner.bundle.memory
    assert len(memory.scenes) == 15
    assert len(memory.chapters) == 1
    assert memory.chapters[0].source == "summarizer"
    assert memory.game_summary == "Свёртка 1"
    assert rig.runner.bundle.session.current_chapter.number == 2
    text = full_text(chapter_requests(rig)[0])
    for k in (1, 8, 15):
        assert f"Выжимка {k}" in text
    assert len(fresh(chapter_requests(rig))) == 1


# сбой свёртки

def test_chapter_failure_gives_error_menu_and_pending(registry, cfg, tmp_path):
    rig = failed_chapter_rig(registry, cfg, tmp_path)
    session = rig.runner.bundle.session
    assert session.boundary_pending is True
    assert session.current_scene.id == "scene_1"
    assert session.current_chapter.number == 1


def test_chapter_failure_returns_boundary_failed_with_menu(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + summ_fail_steps())
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU


def test_chapter_failure_rolls_back_scene_summary_of_step_1(registry, cfg, tmp_path):
    rig = failed_chapter_rig(registry, cfg, tmp_path)
    memory = rig.runner.bundle.memory
    assert memory.scenes == []
    assert memory.chapters == []
    assert memory.game_summary == ""
    assert memory.game_summary_chapter == 0


def test_chapter_failure_leaves_bundle_equal_to_autosave(registry, cfg, tmp_path):
    rig = failed_chapter_rig(registry, cfg, tmp_path)
    assert core_dump(rig.runner.bundle) == core_dump(load_slot(tmp_path, "w1", "auto"))


def test_retry_after_chapter_failure_calls_both_scene_and_chapter(registry, cfg, tmp_path):
    steps = summ_fail_steps()
    steps += summ_steps("Сцена после повтора.", call_id="ss-2")
    steps += chapter_steps(chapter="Глава после повтора.", game="Свёртка после повтора.")
    rig = failed_chapter_rig(registry, cfg, tmp_path, steps)
    rig.runner.retry()
    bundle = rig.runner.bundle
    assert len(fresh(scene_requests(rig))) == 2
    assert [s.summary for s in bundle.memory.scenes] == ["Сцена после повтора."]
    assert bundle.memory.chapters[0].summary == "Глава после повтора."
    assert bundle.memory.game_summary == "Свёртка после повтора."
    assert bundle.session.boundary_pending is False
    assert bundle.session.current_chapter.number == 2


def test_failure_of_scene_step_does_not_call_chapter(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_fail_steps())
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert chapter_requests(rig) == []


def test_save_and_quit_then_load_closes_chapter_before_first_turn(registry, cfg, tmp_path):
    failed_chapter_rig(registry, cfg, tmp_path)
    loaded = load_slot(tmp_path, "w1", "auto")
    assert loaded.session.boundary_pending is True
    rig = make_summ_rig(
        registry, cfg, tmp_path, [text_step("Тишина.")],
        summ_steps("Достроено.") + chapter_steps(chapter="Достроенная глава."), bundle=loaded,
    )
    rig.runner.play("новый ход")
    bundle = rig.runner.bundle
    assert bundle.memory.chapters[0].summary == "Достроенная глава."
    assert bundle.session.current_chapter.number == 2
    assert bundle.session.current_scene.id == "scene_2"
    assert bundle.session.boundary_pending is False


def test_pending_boundary_by_scene_limit_loads_and_closes_chapter(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry, count=cfg.scene.max_per_chapter)
    bundle.session.current_scene.closed_reason = "end_scene"
    bundle.session.boundary_pending = True
    save_slot(tmp_path, bundle, "auto", saved_at="2026-01-01T12:00:00Z")
    loaded = load_slot(tmp_path, "w1", "auto")
    rig = make_summ_rig(
        registry, cfg, tmp_path, [text_step("Тишина.")],
        summ_steps("Сцена.") + chapter_steps(), bundle=loaded,
    )
    rig.runner.play("ход")
    assert len(rig.runner.bundle.memory.chapters) == 1
    assert rig.runner.bundle.memory.chapters[0].source == "summarizer"


# длина

def test_game_summary_over_limit_is_invalid_and_retried(registry, cfg, tmp_path):
    steps = summ_steps("Сцена.") + chapter_steps(game="я" * 3001, suffix="1")
    steps += chapter_steps(game="Короткая свёртка.", suffix="2")
    rig = close_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("ход")
    assert has_tool_error(chapter_requests(rig)[1])
    assert rig.runner.bundle.memory.game_summary == "Короткая свёртка."


def test_game_summary_of_3000_chars_is_valid(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(game="я" * 3000)
    )
    rig.runner.play("ход")
    assert len(rig.runner.bundle.memory.game_summary) == 3000


def test_chapter_summary_over_limit_is_invalid_and_retried(registry, cfg, tmp_path):
    steps = summ_steps("Сцена.") + chapter_steps(chapter="я" * 1501, suffix="1")
    steps += chapter_steps(chapter="Короткая глава.", suffix="2")
    rig = close_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("ход")
    assert has_tool_error(chapter_requests(rig)[1])
    assert rig.runner.bundle.memory.chapters[0].summary == "Короткая глава."


def test_chapter_summary_of_1500_chars_is_valid(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(chapter="я" * 1500)
    )
    rig.runner.play("ход")
    assert len(rig.runner.bundle.memory.chapters[0].summary) == 1500


@pytest.mark.parametrize("which", ["chapter", "game"])
def test_empty_chapter_or_game_summary_is_invalid(which, registry, cfg, tmp_path):
    bad = {which: ""}
    steps = summ_steps("Сцена.") + chapter_steps(suffix="1", **bad) + chapter_steps(suffix="2")
    rig = close_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("ход")
    assert has_tool_error(chapter_requests(rig)[1])
    assert rig.runner.bundle.memory.chapters[0].summary == "Выжимка главы."
    assert rig.runner.bundle.memory.game_summary == "Новая свёртка игры."


def test_three_over_limit_answers_go_to_concat_and_chapter_is_closed(
    registry, cfg, tmp_path
):
    steps = summ_steps("Сцена.")
    for n in range(3):
        steps += chapter_steps(game="я" * 3001, suffix=str(n))
    rig = close_rig(registry, cfg, tmp_path, steps, backup=REFUSAL)
    result = rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert result.boundary_failed is False
    assert [c.source for c in memory.chapters] == ["concat"]
    assert rig.runner.bundle.session.current_chapter.number == 2
    assert [s.summary for s in memory.scenes] == ["Сцена."]


# память в следующем ходе нарратора

def test_next_narrator_request_has_game_summary_and_chapter_but_not_closed_chapter_scenes(
    registry, cfg, tmp_path
):
    narrator = end_scene_and_chapter("Пролог") + [text_step("Новый ход.")]
    rig = make_summ_rig(
        registry, cfg, tmp_path, narrator,
        summ_steps("СЦЕНА ЗАКРЫТОЙ ГЛАВЫ")
        + chapter_steps(chapter="ВЫЖИМКА ГЛАВЫ ОДИН", game="НОВАЯ СВЁРТКА ИГРЫ"),
        bundle=chapter_bundle(registry),
    )
    rig.play(2)
    system = rig.narrator.requests[-1].system
    assert len(system) == 3
    assert "НОВАЯ СВЁРТКА ИГРЫ" in system[2].text
    assert "ВЫЖИМКА ГЛАВЫ ОДИН" in system[2].text
    assert "СЦЕНА ЗАКРЫТОЙ ГЛАВЫ" not in system[2].text


# журнал и replay

def test_journal_has_two_summarizer_calls_with_one_boundary_run_id(registry, cfg, tmp_path):
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ход")
    records = rig.summarizer_records()
    assert len(records) >= 2
    assert len({r["run_id"] for r in records}) == 1
    assert all(r["run_id"].startswith("bnd-") for r in records)


def test_replay_of_boundary_with_chapter_gives_same_bundle_memory(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    first = close_rig(
        registry, cfg, tmp_path / "a", summ_steps("Сцена.") + chapter_steps(), title="Пролог"
    )
    first.runner.play("ход")
    replay = ReplayAdapter(first.journal.read_records(), role="summarizer")
    model = first.summarizer_records()[0]["requested_model"]
    second = make_summ_rig(
        registry, cfg, tmp_path / "b", end_scene_and_chapter("Пролог"), replay,
        bundle=chapter_bundle(registry), summarizer_model=model,
    )
    second.runner.play("ход")
    a = first.runner.bundle
    b = second.runner.bundle
    assert dumps(a.memory) == dumps(b.memory)
    assert dumps(a.session) == dumps(b.session)
    assert a.memory.chapters[0].source == "summarizer"


def test_request_text_helper_is_used(registry, cfg, tmp_path):
    # вход сцены главы по-прежнему в messages[0]: ходы закрытой сцены
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ПЕРВЫЙ ВВОД")
    assert "ПЕРВЫЙ ВВОД" in request_text(scene_requests(rig)[0])


# два раунда: инструменты главы в разных ответах

def test_tools_in_two_different_rounds_are_not_accepted_and_retried(registry, cfg, tmp_path):
    steps = summ_steps("Сцена.") + [
        tools_step(chapter_summary_call("Только глава.", call_id="cs-1")),
        tools_step(game_summary_call("Только игра.", call_id="gs-1")),
    ]
    steps += chapter_steps(chapter="Целая глава.", game="Целая свёртка.", suffix="2")
    rig = close_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert memory.chapters[0].summary == "Целая глава."
    assert memory.game_summary == "Целая свёртка."
    assert len(chapter_requests(rig)) >= 3


def test_tools_in_two_rounds_forever_go_to_concat(registry, cfg, tmp_path):
    steps = summ_steps("Сцена.")
    for n in range(4):
        steps += [
            tools_step(chapter_summary_call("Только глава.", call_id=f"cs-{n}")),
            tools_step(game_summary_call("Только игра.", call_id=f"gs-{n}")),
        ]
    rig = close_rig(registry, cfg, tmp_path, steps, backup=REFUSAL)
    result = rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert result.boundary_failed is False
    assert [c.source for c in memory.chapters] == ["concat"]
    assert memory.game_summary == ""


def test_valid_chapter_and_invalid_game_until_retries_exhausted_go_to_concat(
    registry, cfg, tmp_path
):
    steps = summ_steps("Сцена.")
    for n in range(4):
        steps += chapter_steps(chapter="Годная глава.", game="я" * 3001, suffix=str(n))
    rig = close_rig(registry, cfg, tmp_path, steps, backup=REFUSAL)
    result = rig.runner.play("ход")
    bundle = rig.runner.bundle
    assert result.boundary_failed is False
    assert [c.source for c in bundle.memory.chapters] == ["concat"]
    assert bundle.memory.chapters[0].summary == "Сцена."
    assert bundle.memory.game_summary == ""
    assert bundle.session.current_chapter.number == 2


# Р2: отказ и цепочка свёртки главы

def test_chapter_refusal_then_narrator_backup_writes_chapter_and_game(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + REFUSAL,
        backup=chapter_steps(chapter="От рассказчика.", game="Свёртка рассказчика."),
    )
    result = rig.runner.play("ход")
    memory = rig.runner.bundle.memory
    assert result.boundary_failed is False
    assert memory.chapters[0].source == "summarizer"
    assert memory.chapters[0].summary == "От рассказчика."
    assert memory.game_summary == "Свёртка рассказчика."
    assert memory.game_summary_chapter == 1
    assert "refusal_fallback" in result.report_tags


def test_chapter_backup_request_is_summarizer_role_on_narrator_model(registry, cfg, tmp_path):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + REFUSAL,
        backup=chapter_steps(chapter="От рассказчика."),
    )
    rig.runner.play("ход")
    backup = chapter_requests(rig.narrator_view())
    assert backup
    assert backup[0].role == "summarizer"
    assert backup[0].model == rig.narrator.requests[0].model


def test_chapter_both_refused_gives_concat_of_scene_summaries(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry, count=3)
    bundle.memory.game_summary = "ПРЕЖНЯЯ СВЁРТКА"
    bundle.memory.game_summary_chapter = 0
    bundle.memory.scenes = [
        SceneSummary(id="s_a", chapter_id="chapter_1", summary="СЦЕНА А"),
        SceneSummary(id="s_x", chapter_id="chapter_0", summary="ЧУЖАЯ"),
    ]
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + REFUSAL, bundle=bundle, backup=REFUSAL
    )
    result = rig.runner.play("ход")
    after = rig.runner.bundle
    chapter = after.memory.chapters[0]
    assert result.boundary_failed is False
    assert chapter.source == "concat"
    assert chapter.summary == "СЦЕНА А Сцена."
    assert chapter.title == "Пролог"
    assert after.memory.game_summary == "ПРЕЖНЯЯ СВЁРТКА"
    assert after.memory.game_summary_chapter == 0
    assert after.session.current_chapter.number == 2
    assert after.session.boundary_pending is False
    assert result.report_tags.count("refusal_fallback") == 1


def test_chapter_fatal_still_gives_error_menu_and_backup_is_not_called(
    registry, cfg, tmp_path
):
    rig = close_rig(
        registry, cfg, tmp_path, summ_steps("Сцена.") + summ_fail_steps(),
        backup=chapter_steps(),
    )
    result = rig.runner.play("ход")
    assert result.boundary_failed is True
    assert result.menu == ERROR_MENU
    assert rig.runner.failed_role == "summarizer"
    assert chapter_requests(rig.narrator_view()) == []


# at_s

def test_chapter_at_s_is_closing_moment_not_chapter_start(registry, cfg, tmp_path):
    bundle = chapter_bundle(registry)
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps(), bundle=bundle)
    rig.runner.play("ход")
    after = rig.runner.bundle
    chapter = after.memory.chapters[0]
    assert chapter.at_s == after.world.clock.now_s
    assert chapter.at_s > 0
    assert chapter.at_s == after.session.current_chapter.started_at_s


def test_chapter_at_s_is_after_tick_days(registry, cfg, tmp_path, monkeypatch):
    import ai_dm.game.boundary as boundary

    original = boundary.tick_days

    def shifted(work, cfg, registry):
        work.world.clock.advance(5000)
        return original(work, cfg, registry)

    monkeypatch.setattr(boundary, "tick_days", shifted)
    rig = close_rig(registry, cfg, tmp_path, summ_steps("Сцена.") + chapter_steps())
    rig.runner.play("ход")
    after = rig.runner.bundle
    saved = load_slot(tmp_path, "w1", "auto")
    assert after.memory.chapters[0].at_s >= saved.world.clock.now_s + 5000
    assert after.memory.chapters[0].at_s == after.world.clock.now_s


# replay: summarizer x2 + world

def test_replay_of_boundary_with_chapter_and_world_gives_same_bundle(registry, cfg, tmp_path):
    from world_kit import BRANN, OATH, bundle_with_brann, verdict_call, world_step

    from ai_dm.llm.replay import ReplayAdapter
    from ai_dm.state.session import ChapterState

    def make_bundle():
        bundle = bundle_with_brann(registry, cfg)
        bundle.session.current_chapter = ChapterState(
            id="chapter_1", number=1, started_at_s=0, scene_count=1
        )
        return bundle

    world_steps = world_step(verdict_call([(BRANN, False), (OATH, False)]))
    first = make_summ_rig(
        registry, cfg, tmp_path / "a", end_scene_and_chapter("Пролог"),
        summ_steps("Сцена.") + chapter_steps(), bundle=make_bundle(), world=scripted(world_steps),
    )
    first.runner.play("ход")
    records = first.journal.read_records()
    assert [r["role"] for r in records].count("world") >= 1
    summ_model = first.summarizer_records()[0]["requested_model"]
    world_model = next(r for r in records if r["role"] == "world")["requested_model"]
    second = make_summ_rig(
        registry, cfg, tmp_path / "b", end_scene_and_chapter("Пролог"),
        ReplayAdapter(records, role="summarizer"), bundle=make_bundle(),
        summarizer_model=summ_model, world=ReplayAdapter(records, role="world"),
        world_model=world_model,
    )
    second.runner.play("ход")
    a = first.runner.bundle
    b = second.runner.bundle
    assert a.memory.chapters[0].source == "summarizer"
    assert dumps(a.memory) == dumps(b.memory)
    assert dumps(a.session) == dumps(b.session)
    assert dumps(a.world) == dumps(b.world)
