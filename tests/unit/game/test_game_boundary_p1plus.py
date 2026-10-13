# Этап 4, P1+: мелочи границы сцены. fallback_summary без split по «_»; scene.title закрытой
# сцены = title, попавший в память; чистка call_numbers раннера после границы.
from types import SimpleNamespace

from game_kit import end_scene_call, text_step, tools_step
from protocol_kit import make_bundle
from summarizer_kit import force_close, make_summ_rig, summ_steps

from ai_dm.game.boundary import close_chapter, fallback_summary, summarize_scene
from ai_dm.state.session import ChapterState


def fake_summarizer(title="", text="Выжимка."):
    def try_scene(work, registry, cfg, run_id):
        return SimpleNamespace(summary_title=title, summary_text=text), False

    return SimpleNamespace(try_scene=try_scene)


def run_boundary(registry, cfg, summarizer, scene_title=""):
    bundle = make_bundle(registry)
    bundle.session.current_scene.title = scene_title
    summarize_scene(bundle, cfg, registry, summarizer, "bnd-1", SimpleNamespace())
    return bundle


# fallback_summary

def test_fallback_summary_with_scene_id_without_underscore_does_not_fail(registry):
    bundle = make_bundle(registry)
    scene = bundle.session.current_scene
    scene.id = "arena"
    assert "Вейл" in fallback_summary(bundle, scene)


def test_fallback_summary_with_several_underscores_does_not_fail(registry):
    bundle = make_bundle(registry)
    scene = bundle.session.current_scene
    scene.id = "intro_part_2"
    assert "Вейл" in fallback_summary(bundle, scene)


def test_fallback_summary_for_regular_id_keeps_number(registry):
    bundle = make_bundle(registry)
    assert fallback_summary(bundle, bundle.session.current_scene).startswith("Сцена 1")


def test_fallback_summary_prefers_narrator_hint(registry):
    bundle = make_bundle(registry)
    scene = bundle.session.current_scene
    scene.summary = "Подсказка."
    assert fallback_summary(bundle, scene) == "Подсказка."


# scene.title закрытой сцены

def test_scene_title_gets_summarizer_title_when_narrator_gave_none(registry, cfg):
    bundle = run_boundary(registry, cfg, fake_summarizer(title="Ночь в таверне"))
    assert bundle.session.current_scene.title == "Ночь в таверне"
    assert bundle.memory.scenes[0].title == "Ночь в таверне"


def test_scene_title_of_narrator_wins_over_summarizer(registry, cfg):
    bundle = run_boundary(registry, cfg, fake_summarizer(title="От модели"), "От нарратора")
    assert bundle.session.current_scene.title == "От нарратора"
    assert bundle.memory.scenes[0].title == "От нарратора"


def test_scene_title_is_empty_when_nobody_gave_title(registry, cfg):
    bundle = run_boundary(registry, cfg, fake_summarizer(title=""))
    assert bundle.session.current_scene.title == ""
    assert bundle.memory.scenes[0].title == ""


def test_scene_title_equals_memory_title_in_fallback_mode(registry, cfg):
    bundle = run_boundary(registry, cfg, None, "Название нарратора")
    assert bundle.session.current_scene.title == bundle.memory.scenes[0].title


# call_numbers

def test_take_boundary_cleans_call_numbers_of_boundary_runs(registry, cfg, tmp_path, monkeypatch):
    force_close(monkeypatch, "end_scene")
    steps = [tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")]
    rig = make_summ_rig(registry, cfg, tmp_path, steps, summ_steps("Выжимка."))
    rig.runner.play("ход")
    assert rig.summarizer_records() != []
    assert [k for k in rig.runner.call_numbers if k.startswith("bnd-")] == []



# Р2: summarize_scene / close_chapter передают аргументы в цепочку и разбирают (ctx, fell)

def recording(kind, ctx, fell=False):
    seen = []

    def call(*args):
        seen.append(args)
        return ctx, fell

    return seen, SimpleNamespace(**{kind: call})


def test_summarize_scene_passes_bundle_registry_cfg_and_run_id(registry, cfg):
    bundle = make_bundle(registry)
    ctx = SimpleNamespace(summary_title="", summary_text="Текст.")
    seen, summarizer = recording("try_scene", ctx)
    result = SimpleNamespace(report_tags=[])
    summarize_scene(bundle, cfg, registry, summarizer, "bnd-9", result)
    assert seen == [(bundle, registry, cfg, "bnd-9")]
    assert result.summary_run_id == "bnd-9"


def test_summarize_scene_writes_text_title_and_time_to_scene_and_memory(registry, cfg):
    bundle = make_bundle(registry)
    bundle.world.clock.now_s = 777
    ctx = SimpleNamespace(summary_title="Имя", summary_text="Текст.")
    _, summarizer = recording("try_scene", ctx)
    summarize_scene(bundle, cfg, registry, summarizer, "bnd-9", SimpleNamespace(report_tags=[]))
    scene = bundle.session.current_scene
    assert (scene.summary, scene.title) == ("Текст.", "Имя")
    assert bundle.memory.scenes[0].at_s == 777


def test_summarize_scene_fell_adds_tag_once(registry, cfg):
    bundle = make_bundle(registry)
    ctx = SimpleNamespace(summary_title="", summary_text="Текст.")
    _, summarizer = recording("try_scene", ctx, fell=True)
    result = SimpleNamespace(report_tags=[])
    summarize_scene(bundle, cfg, registry, summarizer, "bnd-9", result)
    assert result.report_tags == ["refusal_fallback"]


def closing_bundle(registry, number=2, reason="end_chapter"):
    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id=f"ch_{number}", number=number, started_at_s=0, scene_count=1, closed_reason=reason,
    )
    return bundle


def test_close_chapter_passes_arguments_and_run_id(registry, cfg):
    bundle = closing_bundle(registry)
    ctx = SimpleNamespace(chapter_text="Г.", game_text="И.", chapter_title_new="Н")
    seen, summarizer = recording("try_chapter", ctx)
    result = SimpleNamespace(report_tags=[])
    close_chapter(bundle, cfg, registry, summarizer, "bnd-9", result)
    assert seen == [(bundle, registry, cfg, "bnd-9")]
    assert result.summary_run_id == "bnd-9"
    assert result.report_tags == []


def test_close_chapter_opens_next_chapter_and_returns_number_and_title(registry, cfg):
    bundle = closing_bundle(registry, number=2)
    bundle.session.current_chapter.title = "Название"
    ctx = SimpleNamespace(chapter_text="Г.", game_text="И.", chapter_title_new="Н")
    _, summarizer = recording("try_chapter", ctx)
    closed = close_chapter(
        bundle, cfg, registry, summarizer, "bnd-9", SimpleNamespace(report_tags=[])
    )
    assert closed == (2, "Название")
    assert bundle.session.current_chapter.id == "ch_3"
    assert bundle.session.current_chapter.number == 3
    assert bundle.memory.game_summary == "И."
    assert bundle.memory.game_summary_chapter == 2


def test_close_chapter_by_scene_limit_sets_reason(registry, cfg):
    bundle = closing_bundle(registry, reason=None)
    bundle.session.current_chapter.scene_count = cfg.scene.max_per_chapter
    ctx = SimpleNamespace(chapter_text="Г.", game_text="И.", chapter_title_new="Н")
    _, summarizer = recording("try_chapter", ctx)
    closed = close_chapter(
        bundle, cfg, registry, summarizer, "bnd-9", SimpleNamespace(report_tags=[])
    )
    assert closed is not None
    assert bundle.memory.chapters[0].id == "ch_2"


def test_close_chapter_none_ctx_gives_concat_and_tag(registry, cfg):
    bundle = closing_bundle(registry)
    bundle.memory.game_summary = "ПРЕЖНЯЯ"
    _, summarizer = recording("try_chapter", None, fell=True)
    result = SimpleNamespace(report_tags=[])
    close_chapter(bundle, cfg, registry, summarizer, "bnd-9", result)
    assert bundle.memory.chapters[0].source == "concat"
    assert bundle.memory.game_summary == "ПРЕЖНЯЯ"
    assert result.report_tags == ["refusal_fallback"]
