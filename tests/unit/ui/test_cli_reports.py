# Этап 6а, P0 (STAGE6A-PLAN, В4): --mock и --replay не пишут авто-репорты (метка есть, файла нет);
# ручной /report в --mock пишет. Ожидаемый API: ai_dm.ui.cli.main, помощники -- ui_kit.py.
from pathlib import Path

from ui_kit import SEED, cli

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]


def issue_dirs(saves):
    return sorted(Path(saves).glob("*/issues/*"))


def unsupported_script(path):
    path.write_text(
        "steps:\n"
        "  - tool_calls:\n"
        "      - id: u-1\n"
        "        name: unsupported_action\n"
        "        input: {type: unsupported_action, description: верхом на медведе}\n"
        "  - text: Медведя нет.\n",
        encoding="utf-8",
    )
    return path


def run_mock(tmp_path, lines):
    script = unsupported_script(tmp_path / "bear.yaml")
    saves = tmp_path / "saves"
    args = BASE + ["--simple", "--mock", str(script), "--saves", str(saves)]
    code, out = cli(args, lines)
    return code, out, saves


def test_mock_turn_with_tag_writes_no_auto_report(tmp_path):
    code, out, saves = run_mock(tmp_path, ["Еду на медведе", "/quit"])
    assert code == 0
    assert "Медведя нет." in out.text
    assert issue_dirs(saves) == []


def test_mock_manual_report_writes_dir(tmp_path):
    code, out, saves = run_mock(tmp_path, ["Еду на медведе", "/report медведь не едет", "/quit"])
    assert code == 0
    assert "Записан репорт" in out.text
    assert len(issue_dirs(saves)) == 1
    assert issue_dirs(saves)[0].name.endswith("-manual")


def test_mock_empty_report_writes_nothing(tmp_path):
    _, out, saves = run_mock(tmp_path, ["Еду на медведе", "/report", "/quit"])
    assert "/report <что не так>" in out.text
    assert issue_dirs(saves) == []
