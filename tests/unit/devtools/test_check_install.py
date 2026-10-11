# devtools/check_install.py (make install-check): без сети и uv, run() подменён.
# Му-б (MU-PLAN B2): колесо ставится с extra audio, в окружении проверяются textual и miniaudio.
import importlib.util
import os
from pathlib import Path

import pytest

CHECK_PATH = Path(__file__).parents[3] / "devtools" / "check_install.py"


@pytest.fixture
def commands(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location("check_install", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sent = []
    monkeypatch.setattr(module, "run", lambda cmd, env=None: sent.append(list(cmd)))
    monkeypatch.setattr(module.glob, "glob", lambda pattern: ["dist/ai_dm-0.1.0-py3-none-any.whl"])
    monkeypatch.setattr(os, "remove", lambda path: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "chdir", lambda path: None)
    assert module.main() == 0
    return sent


def test_install_command_requests_audio_extra(commands):
    install = [c for c in commands if "install" in c]
    assert len(install) == 1
    source = install[0][install[0].index("--from") + 1]
    assert source.startswith("ai-dm[audio]")


def test_install_command_takes_the_wheel(commands):
    install = [c for c in commands if "install" in c][0]
    assert install[install.index("--from") + 1].endswith(".whl")


def test_installed_python_imports_textual(commands):
    assert any(c[-2:] == ["-c", "import textual"] for c in commands)


def test_installed_python_imports_miniaudio(commands):
    assert any(c[-2:] == ["-c", "import miniaudio"] for c in commands)
