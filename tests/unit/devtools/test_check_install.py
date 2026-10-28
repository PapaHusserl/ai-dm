# devtools/check_install.py (make install-check): без сети и uv, run() подменён.
# Му-б (MU-PLAN B2): колесо ставится с extra audio, в окружении проверяются textual и miniaudio.
import importlib.util
import os
from pathlib import Path

import pytest

CHECK_PATH = Path(__file__).parents[3] / "devtools" / "check_install.py"


@pytest.fixture
def calls(monkeypatch, tmp_path):
    # (команда, env, остальные аргументы run) в порядке вызова
    spec = importlib.util.spec_from_file_location("check_install", CHECK_PATH)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    sent = []
    monkeypatch.setattr(
        module, "run", lambda cmd, env=None, **kw: sent.append((list(cmd), env, kw))
    )
    monkeypatch.setattr(module.glob, "glob", lambda pattern: ["dist/ai_dm-0.1.0-py3-none-any.whl"])
    monkeypatch.setattr(os, "remove", lambda path: None)
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(os, "chdir", lambda path: None)
    assert module.main() == 0
    return sent


@pytest.fixture
def commands(calls):
    return [cmd for cmd, _env, _kw in calls]


def new_world_call(calls):
    return [c for c in calls if "--new" in c[0]][0]


def test_installed_game_starts_a_new_world_on_mock(commands):
    new = [c for c in commands if "--new" in c][0]
    assert "--mock" in new
    assert "--simple" in new


def test_new_world_runs_from_a_clean_home_without_keys(calls):
    _cmd, env, kw = new_world_call(calls)
    assert env["HOME"] == str(kw["cwd"])
    assert sorted(env) == ["HOME", "PATH"]
    assert kw["input"] == "Здравствуйте\n"


def test_one_world_is_expected_in_the_user_data_dir(commands):
    check = commands[-1]
    assert "iterdir" in check[2]
    assert check[-1].endswith("home/.local/share/ai-dm/saves")


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
