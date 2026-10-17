# ТС #22 (docs/TS-PLAN.md §1 п.2, §4): граница сцены с мягким пределом выжимки. Три длинных ответа
# summarizer подряд -- третий режется движком, запасной вызов не нужен, тег summary_trimmed;
# summary_trim_after = 0 возвращает прежнее поведение (запасной -> тег summarizer_backup).
from game_kit import end_scene_call, text_step, tools_step
from summarizer_kit import (
    dumps,
    make_summ_rig,
    summ_steps,
    tool_results_text,
)

LONG = "Герой пришёл в город и встретил Бранна. " * 20


def end_narrator(summary="Подсказка."):
    return [tools_step(end_scene_call(summary=summary)), text_step("Конец.")]


def long_steps(n, text=LONG, title=""):
    steps = []
    for k in range(n):
        steps += summ_steps(text, title=title, call_id=f"ss-{k}")
    return steps


def scene(rig):
    return rig.runner.bundle.memory.scenes[0]


def test_three_long_answers_give_trimmed_summary_with_source_summarizer(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    result = rig.runner.play("ход")
    assert result.boundary_failed is False
    assert scene(rig).source == "summarizer"
    assert 0 < len(scene(rig).summary) <= 600


def test_three_long_answers_make_three_calls_under_one_boundary_run_id(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    rig.runner.play("ход")
    records = rig.summarizer_records()
    assert len(records) == 3
    assert len({r["run_id"] for r in records}) == 1
    assert records[0]["run_id"].startswith("bnd-")


def test_three_long_answers_do_not_call_narrator_backup(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    rig.runner.play("ход")
    assert rig.narrator_view().summarizer_requests() == []
    assert len(rig.summarizer_requests()) == 3


def test_three_long_answers_give_summary_trimmed_tag_without_backup_tag(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    result = rig.runner.play("ход")
    assert result.report_tags.count("summary_trimmed") == 1
    assert "summarizer_backup" not in result.report_tags


def test_trimmed_summary_ends_at_sentence_boundary(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    rig.runner.play("ход")
    assert scene(rig).summary.endswith("Бранна.")


def test_trimmed_summary_keeps_title_of_summarizer(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3, title="Город"))
    rig.runner.play("ход")
    assert scene(rig).title == "Город"


def test_boundary_finishes_with_new_scene_after_trimming(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    rig.runner.play("ход")
    session = rig.runner.bundle.session
    assert session.boundary_pending is False
    assert session.current_scene.id == "scene_2"


def test_first_overflow_answer_gets_attempt_hint_with_ratio(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(3))
    rig.runner.play("ход")
    first_result = tool_results_text(rig.summarizer_requests()[1])
    assert "Попытка 1 из 2" in first_result
    assert "предел 600" in first_result


def test_two_long_answers_then_short_one_are_not_trimmed(registry, cfg, tmp_path):
    steps = long_steps(2) + summ_steps("Короткая.", call_id="ss-9")
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), steps)
    result = rig.runner.play("ход")
    assert scene(rig).summary == "Короткая."
    assert "summary_trimmed" not in result.report_tags


def test_empty_answer_between_long_ones_does_not_count_as_overflow(registry, cfg, tmp_path):
    # длинный, пустой, длинный: переполнений два (< 3), обрезки нет; бюджет невалидных исчерпан
    steps = long_steps(1) + summ_steps("", call_id="ss-e") + long_steps(1, text=LONG)
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, steps)
    result = rig.runner.play("ход")
    assert scene(rig).summary == "От рассказчика."
    assert "summary_trimmed" not in result.report_tags
    assert "summarizer_backup" in result.report_tags


def test_trim_after_zero_goes_to_backup_with_summarizer_backup_tag(registry, cfg, tmp_path):
    narrator = end_narrator() + summ_steps("От рассказчика.")
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, long_steps(3))
    rig.runner.app_cfg.memory.summary_trim_after = 0
    result = rig.runner.play("ход")
    assert scene(rig).summary == "От рассказчика."
    assert "summarizer_backup" in result.report_tags
    assert "summary_trimmed" not in result.report_tags


def test_trim_after_zero_and_backup_also_long_gives_fallback(registry, cfg, tmp_path):
    narrator = end_narrator("Подсказка.") + long_steps(3)
    rig = make_summ_rig(registry, cfg, tmp_path, narrator, long_steps(3))
    rig.runner.app_cfg.memory.summary_trim_after = 0
    result = rig.runner.play("ход")
    assert scene(rig).source == "fallback"
    assert scene(rig).summary == "Подсказка."
    assert result.report_tags.count("summarizer_backup") == 1


def test_trim_after_one_trims_on_second_answer(registry, cfg, tmp_path):
    rig = make_summ_rig(registry, cfg, tmp_path, end_narrator(), long_steps(2))
    rig.runner.app_cfg.memory.summary_trim_after = 1
    result = rig.runner.play("ход")
    assert len(rig.summarizer_requests()) == 2
    assert 0 < len(scene(rig).summary) <= 600
    assert "summary_trimmed" in result.report_tags


def test_replay_of_trimmed_boundary_gives_same_memory(registry, cfg, tmp_path):
    from ai_dm.llm.replay import ReplayAdapter

    first = make_summ_rig(registry, cfg, tmp_path / "a", end_narrator(), long_steps(3))
    first.runner.play("ход")
    replay = ReplayAdapter(first.journal.read_records(), role="summarizer")
    model = first.summarizer_records()[0]["requested_model"]
    second = make_summ_rig(
        registry, cfg, tmp_path / "b", end_narrator(), replay, summarizer_model=model
    )
    second.runner.play("ход")
    assert dumps(first.runner.bundle.memory) == dumps(second.runner.bundle.memory)
    assert scene(second).summary == scene(first).summary
