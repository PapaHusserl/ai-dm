# ТМ (мини-партия #20): ход с отклонённым повтором (gold_repeat, rest_repeat) воспроизводится
# (--replay-report, код 0, «Состояние совпало»): снимок состояния перед ходом уже содержит записи
# памяти с outcomes / money_delta_cp / long_rest_end_s.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import scripted, text_step, tools_step  # noqa: E402
from ui_kit import WORLD, build_app, cli  # noqa: E402

MATCH = "Состояние совпало."
GOLD = {
    "id": "g1", "name": "gold",
    "input": {
        "type": "gold", "direction": "gain", "kind": "explicit", "amount_cp": 2000, "cr": "",
    },
}
GOLD_AGAIN = {**GOLD, "id": "g2"}
REST = {"id": "r1", "name": "rest", "input": {"type": "rest", "kind": "long"}}
REST_AGAIN = {**REST, "id": "r2"}


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def replay(path, cfg_dir):
    cfg_dir.mkdir(exist_ok=True)
    return cli(["--replay-report", str(path)], env={"AI_DM_CONFIG_DIR": str(cfg_dir)})


def played_twice(registry, tmp_path, steps):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted(steps), hp=200)
    app.handle("Первый ход")
    return root, app, app.handle("Второй ход")


def test_gold_repeat_turn_replays(registry, tmp_path):
    steps = [
        tools_step(GOLD), text_step("Находишь кошель."),
        tools_step(GOLD_AGAIN), text_step("Больше ничего нет."),
    ]
    root, _, reply = played_twice(registry, tmp_path, steps)
    assert reply.turn.report_tags == ["gold_repeat"]
    path = reports_of(root)[-1]
    assert path.name.endswith("gold_repeat")
    code, out = replay(path, tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_rest_repeat_turn_replays(registry, tmp_path):
    steps = [
        tools_step(REST), text_step("Ты просыпаешься отдохнувшим."),
        tools_step(REST_AGAIN), text_step("Ты уже выспался."),
    ]
    root, _, reply = played_twice(registry, tmp_path, steps)
    assert reply.turn.report_tags == ["rest_repeat"]
    path = reports_of(root)[-1]
    assert path.name.endswith("rest_repeat")
    code, out = replay(path, tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_replayed_rejected_turn_keeps_the_purse(registry, tmp_path):
    steps = [
        tools_step(GOLD), text_step("Находишь кошель."),
        tools_step(GOLD_AGAIN), text_step("Больше ничего нет."),
    ]
    root, app, _ = played_twice(registry, tmp_path, steps)
    purse = app.bundle.heroes[0].money_cp
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg")
    assert code == 0, out.text
    assert app.bundle.heroes[0].money_cp == purse
