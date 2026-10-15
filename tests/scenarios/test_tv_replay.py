# ТВ (мини-партия #18): ходы с T3 (текст + отклонённый вызов) и T5 (приписка choices_retry)
# воспроизводятся (--replay-report, код 0, «Состояние совпало»); цифра игрока подставляет
# вариант, предложенный после приписки.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import scripted, text_step, tools_step  # noqa: E402
from master_kit import flag_call  # noqa: E402
from ui_kit import WORLD, build_app, cli  # noqa: E402

MATCH = "Состояние совпало."
LONG = "Ты идёшь по тихой улице Вейла, и ветер несёт запах дыма из труб, а в окнах гаснут огни."
QUESTION = "Ты стоишь у двери.\n\nОткрыть её?"
BAD_FLAG = {"id": "bf", "name": "set_flag", "input": {"type": "set_flag"}}
OFFER = {
    "id": "of", "name": "offer_choices",
    "input": {"type": "offer_choices", "choices": ["Открыть", "Уйти"]},
}


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def replay(path, cfg_dir):
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.toml").write_text("[master]\nmin_narration_chars = 80\n", encoding="utf-8")
    return cli(["--replay-report", str(path)], env={"AI_DM_CONFIG_DIR": str(cfg_dir)})


def played(registry, tmp_path, steps, line="Иду"):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted(steps), hp=200)
    app.runner.app_cfg.master.min_narration_chars = 80
    return root, app, app.handle(line)


def test_choices_retry_turn_replays(registry, tmp_path):
    root, _, reply = played(registry, tmp_path, [text_step(QUESTION), tools_step(OFFER)])
    assert reply.turn.report_tags == ["choices_retry"]
    path = reports_of(root)[-1]
    assert path.name.endswith("choices_retry")
    code, out = replay(path, tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_choices_retry_with_text_answer_replays(registry, tmp_path):
    root, _, reply = played(registry, tmp_path, [text_step(QUESTION), text_step("Ладно.")])
    assert reply.turn.report_tags == ["choices_retry"]
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_choices_retry_after_tool_round_replays(registry, tmp_path):
    steps = [tools_step(flag_call("a")), text_step(LONG + "\n\nОткрыть её?"), tools_step(OFFER)]
    root, _, reply = played(registry, tmp_path, steps)
    assert reply.turn.report_tags == ["choices_retry"]
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_digit_after_ask_picks_the_offered_choice(registry, tmp_path):
    from ai_dm.ui.session import PlaySession

    steps = [text_step(QUESTION), tools_step(OFFER), text_step("Дверь открыта.")]
    _, app, _ = played(registry, tmp_path, steps)
    PlaySession(app).submit("1")
    assert app.bundle.memory.recent_turns[-1].player_input == "Открыть"


def test_t436_pattern_turn_replays_from_manual_report(registry, tmp_path):
    # сцена + отклонённый вызов + принятый offer_choices: один проход, тегов нет -- репорт ручной
    steps = [
        tools_step(BAD_FLAG, OFFER, text=LONG), tools_step(flag_call("a")),
        text_step("Письмо у тебя."),
    ]
    root, app, reply = played(registry, tmp_path, steps)
    assert reply.turn.report_tags == []
    assert reply.turn.narration == LONG + "\n\nПисьмо у тебя."
    assert reports_of(root) == []
    app.handle("/report t436")
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines
    assert "Письмо у тебя." in out.text
