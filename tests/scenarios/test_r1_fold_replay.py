# Р1 «Память боя»: ход, закончивший бой со свёрткой, воспроизводится (--replay-report, код 0,
# текст свёртки детерминирован), а /report показывает запись-свёртку как обычную запись хода.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import (  # noqa: E402
    ReactiveAdapter,
    ScriptThenReactive,
    attack_or_move_number,
    player_action_input,
    scripted_from_yaml,
)
from ui_kit import DESCEND, TALK, WORLD, build_app, cli, play  # noqa: E402

COMBAT_SCRIPT = "talk_check_fight.yaml"
KICK = "Опрокидываю бочку на ближнего гоблина"
IMPROVISE = {
    "skill": "athletics", "category": "medium", "effect": "prone", "target": "goblin_1",
    "zone": "",
}
MATCH = "Состояние совпало."
FOLD = "Свёрнуты ходы"


def fight_app(registry, root):
    adapter = ScriptThenReactive(
        scripted_from_yaml(COMBAT_SCRIPT),
        ReactiveAdapter(classify=[player_action_input([], improvise=IMPROVISE)]),
    )
    return build_app(registry, root, adapter, hp=200)


def fought(registry, root):
    app = fight_app(registry, root)
    play(app, [TALK, "1", DESCEND])
    app.handle(KICK)
    for _ in range(60):
        if app.bundle.session.active_combat is None:
            break
        app.handle(str(attack_or_move_number(app.runner)))
    assert app.bundle.session.active_combat is None
    return app


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def test_fold_is_in_memory_after_the_fight(registry, tmp_path):
    app = fought(registry, tmp_path / "saves")
    texts = [t.narration for t in app.bundle.memory.recent_turns]
    assert sum(text.startswith(FOLD) for text in texts) == 1
    assert not texts[-1].startswith(FOLD)


def test_report_prints_fold_as_a_turn_without_player_phrase(registry, tmp_path):
    root = tmp_path / "saves"
    app = fought(registry, root)
    app.handle("/report бой")
    report = (reports_of(root)[-1] / "report.md").read_text(encoding="utf-8")
    assert f"Фраза игрока: \n\n{FOLD}" in report
    fold_block = report.split(FOLD)[1].split("### Ход")[0]
    assert "Броски:" not in fold_block


def test_turn_that_ended_the_fight_with_fold_replays(registry, tmp_path):
    root = tmp_path / "saves"
    app = fought(registry, root)
    app.handle("/report конец боя")
    code, out = cli(["--replay-report", str(reports_of(root)[-1])], env={})
    assert code == 0, out.text
    assert MATCH in out.lines
