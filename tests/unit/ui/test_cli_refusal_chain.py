# ТО (docs/plan-to.md §1 п.3): cli передаёт GameApp refusal_chain=False при --mock/--replay
# (как auto_reports). Живой режим (True) без сети не запустить -- проверяется в ЖП.
from pathlib import Path

from ui_kit import SEED, cli

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]


def test_mock_run_passes_refusal_chain_false(tmp_path, monkeypatch):
    from ai_dm.game.app import GameApp

    seen = []
    original = GameApp.__init__

    def spy(self, *args, **kwargs):
        seen.append(kwargs.get("refusal_chain"))
        original(self, *args, **kwargs)

    monkeypatch.setattr(GameApp, "__init__", spy)
    script = Path(tmp_path) / "s.yaml"
    script.write_text("steps:\n  - text: Привет.\n", encoding="utf-8")
    args = BASE + ["--simple", "--mock", str(script), "--saves", str(tmp_path / "saves")]
    code, _ = cli(args, ["/quit"])
    assert code == 0
    assert seen == [False]
