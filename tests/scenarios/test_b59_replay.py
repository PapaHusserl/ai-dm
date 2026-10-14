# B59: ход с автоповтором короткого рассказа воспроизводится (--replay-report, код 0, «Состояние
# совпало»). Порог в тестах выключен conftest; для игры и для реплея включается явно
# (пользовательский config.toml в AI_DM_CONFIG_DIR).
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import scripted, text_step, tools_step  # noqa: E402
from master_kit import flag_call  # noqa: E402
from ui_kit import WORLD, build_app, cli  # noqa: E402

MATCH = "Состояние совпало."
LONG = "Ты идёшь по тихой улице Вейла, и ветер несёт запах дыма из труб, а в окнах гаснут огни."
FLAG = tools_step(flag_call("a"))


def reports_of(root):
    return sorted((Path(root) / WORLD / "issues").glob("*"))


def replay(path, cfg_dir=None, min_chars=80):
    env = {}
    if cfg_dir is not None:
        cfg_dir.mkdir(exist_ok=True)
        (cfg_dir / "config.toml").write_text(
            f"[master]\nmin_narration_chars = {min_chars}\n", encoding="utf-8"
        )
        env["AI_DM_CONFIG_DIR"] = str(cfg_dir)
    return cli(["--replay-report", str(path)], env=env)


def played(registry, tmp_path, steps):
    root = tmp_path / "saves"
    app = build_app(registry, root, scripted(steps), hp=200)
    app.runner.app_cfg.master.min_narration_chars = 80
    return root, app.handle("Иду")


def test_turn_with_short_retry_replays(registry, tmp_path):
    root, reply = played(registry, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    assert reply.turn.report_tags == ["short_retry"]
    path = reports_of(root)[-1]
    assert path.name.endswith("short_retry")
    code, out = replay(path, tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines
    assert "Ты идёшь по тихой улице Вейла" in out.text


def test_turn_with_short_retry_replays_with_short_second_text(registry, tmp_path):
    root, reply = played(registry, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step("Тоже.")])
    assert reply.turn.report_tags == ["short_retry"]
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines


def test_replay_without_the_check_diverges_on_extra_call(registry, tmp_path):
    root, _ = played(registry, tmp_path, [FLAG, text_step("Ок."), FLAG, text_step(LONG)])
    code, out = replay(reports_of(root)[-1], tmp_path / "cfg", min_chars=0)
    assert code == 1
