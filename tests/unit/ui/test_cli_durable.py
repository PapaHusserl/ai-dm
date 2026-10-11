# AD1, W1: ui/cli.py::prepare выставляет persistence.durable из [persistence] durable.
from ui_kit import cli, write_script

import ai_dm.ui.cli as cli_module
from ai_dm.config.app import load_settings
from ai_dm.persistence import durable

BASE = ["--new", "--hero", "arn", "--seed", "3"]


def argv(tmp_path):
    script = write_script(tmp_path / "one.yaml")
    return BASE + ["--mock", str(script), "--saves", str(tmp_path / "saves")]


def test_prepare_turns_durable_on_by_default(tmp_path):
    durable.set_durable(False)
    code, _ = cli(argv(tmp_path), ["/quit"], env={})
    assert code == 0
    assert durable.DURABLE is True


def test_prepare_turns_durable_off_from_config(tmp_path, monkeypatch):
    settings = load_settings("[persistence]\ndurable = false\n")
    monkeypatch.setattr(cli_module, "load_user_settings", lambda *a, **k: settings)
    durable.set_durable(True)
    code, _ = cli(argv(tmp_path), ["/quit"], env={})
    assert code == 0
    assert durable.DURABLE is False
