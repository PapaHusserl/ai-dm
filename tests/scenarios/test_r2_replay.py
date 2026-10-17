# Р2 «Темп и отказы»: ходы с автоповтором после отказа рассказчика и границы с запасным вызовом
# summarizer воспроизводятся (--replay-report, код 0, «Состояние совпало»).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import (  # noqa: E402
    NOW,
    OPUS,
    end_scene_call,
    scripted,
    settings,
    text_step,
    tools_step,
)
from slots_kit import WORLD_TEXT  # noqa: E402
from summarizer_kit import summ_steps  # noqa: E402
from ui_kit import SAVED_AT, WORLD, build_app, cli  # noqa: E402

from ai_dm.game.app import GameApp  # noqa: E402
from ai_dm.game.starter import new_world  # noqa: E402

MATCH = "Состояние совпало."
REFUSAL = {"stop": "refusal"}


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def replay(path):
    return cli(["--replay-report", str(path)], env={})


def boundary_app(registry, root, narrator_steps, summarizer_steps):
    bundle = new_world(
        registry, settings().rules, hero="arn", seed=3, world_id=WORLD, saved_at=SAVED_AT
    )
    return GameApp(
        settings(), registry, bundle, scripted(narrator_steps), saves_root=root,
        world_text=WORLD_TEXT, model=OPUS, sleeper=lambda s: None, now=lambda: NOW,
        run_tag="t", summarizer_adapter=scripted(summarizer_steps), auto_reports=True,
    )


def test_turn_with_refusal_retry_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([REFUSAL, text_step("Рассказ.")]), hp=200)
    reply = app.handle("Иду")
    assert reply.turn.report_tags == ["refusal_retry"]
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines
    assert "Рассказ." in out.text


def test_turn_with_double_refusal_replays_as_aborted(registry, tmp_path):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted([REFUSAL, REFUSAL]), hp=200)
    app.handle("Иду")
    path = reports_of(root)[-1]
    assert not (path / "after").exists()
    code, out = replay(path)
    assert code == 0, out.text
    assert MATCH in out.lines


def test_boundary_with_summarizer_refusal_and_backup_replays(registry, tmp_path):
    root = tmp_path / "saves"
    narrator = [tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")]
    narrator += summ_steps("От рассказчика.")
    app = boundary_app(registry, root, narrator, [REFUSAL])
    app.handle("Прощаюсь и ухожу")
    assert app.bundle.memory.scenes[0].summary == "От рассказчика."
    path = reports_of(root)[-1]
    code, out = replay(path)
    assert code == 0, out.text
    assert MATCH in out.lines


def test_boundary_with_both_refused_fallback_replays(registry, tmp_path):
    root = tmp_path / "saves"
    narrator = [tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец."), REFUSAL]
    app = boundary_app(registry, root, narrator, [REFUSAL])
    app.handle("Прощаюсь и ухожу")
    assert app.bundle.memory.scenes[0].source == "fallback"
    code, out = replay(reports_of(root)[-1])
    assert code == 0, out.text
    assert MATCH in out.lines


def test_report_of_boundary_with_backup_names_summarizer_backup(registry, tmp_path):
    root = tmp_path / "saves"
    narrator = [tools_step(end_scene_call(summary="Подсказка.")), text_step("Конец.")]
    narrator += summ_steps("От рассказчика.")
    boundary_app(registry, root, narrator, [REFUSAL]).handle("Прощаюсь и ухожу")
    assert reports_of(root)[-1].name.endswith("summarizer_backup")
