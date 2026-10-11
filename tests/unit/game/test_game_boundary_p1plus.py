# Этап 4, P1+: мелочи границы сцены. fallback_summary без split по «_»; scene.title закрытой
# сцены = title, попавший в память; чистка call_numbers раннера после границы.
from types import SimpleNamespace

from game_kit import end_scene_call, text_step, tools_step
from protocol_kit import make_bundle
from summarizer_kit import force_close, make_summ_rig, summ_steps

from ai_dm.game.boundary import fallback_summary, summarize_scene


def fake_summarizer(title="", text="Выжимка."):
    def run_scene(work, registry, cfg, run_id):
        return SimpleNamespace(summary_title=title, summary_text=text)

    return SimpleNamespace(run_scene=run_scene)


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

