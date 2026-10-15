# Т60 «Сеть»: journal/attempts.log (строки о начале попыток) не мешает --replay-report: отчёт
# хода воспроизводится, код 0, «Состояние совпало.»
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


def played_report(registry, tmp_path):
    root = tmp_path / "saves"
    steps = [FLAG, text_step("Ок."), FLAG, text_step(LONG)]
    app = build_app(registry, root, scripted(steps), hp=200)
    app.runner.app_cfg.master.min_narration_chars = 80
    app.handle("Иду")
    return root, app, sorted((root / WORLD / "issues").glob("*"))[-1]


def replay(path, cfg_dir):
    cfg_dir.mkdir(exist_ok=True)
    (cfg_dir / "config.toml").write_text("[master]\nmin_narration_chars = 80\n", encoding="utf-8")
    return cli(["--replay-report", str(path)], env={"AI_DM_CONFIG_DIR": str(cfg_dir)})


def test_game_writes_attempts_log_for_every_started_call(registry, tmp_path):
    root, app, _ = played_report(registry, tmp_path)
    rows = (root / WORLD / "journal" / "attempts.log").read_text(encoding="utf-8").splitlines()
    assert len(rows) == len(app.journal.read_records()) == 4


def test_replay_report_with_attempts_log_around_gives_code_zero(registry, tmp_path):
    root, _, path = played_report(registry, tmp_path)
    assert (root / WORLD / "journal" / "attempts.log").is_file()
    (path / "journal").mkdir(exist_ok=True)
    (path / "journal" / "attempts.log").write_text("x\ty\t1\tnarrator\tm\t1\n", encoding="utf-8")
    code, out = replay(path, tmp_path / "cfg")
    assert code == 0, out.text
    assert MATCH in out.lines
