# Общие помощники тестов пакета reports (этап 6а, P0): снимок хода из бандла мира protocol_kit.
# Не фикстуры pytest, а обычные функции. Контракт: ai_dm.reports.capture.TurnCapture,
# ai_dm.reports.writer.write_report(saves_root, world_id, capture, text, now) -> Path,
# ai_dm.reports.markdown.render(capture, text) -> str.
# #21 ТО: ai_dm.reports.writer.trim_issues(saves_root, world_id, max_mb) -> list[Path]
# (лимит issues/), dir_size(path) -> int; GameApp.already_reported(capture) -- один авто-репорт
# на попытку хода.
import sys
from datetime import UTC, datetime
from pathlib import Path

TESTS_UNIT = Path(__file__).resolve().parents[1]
if str(TESTS_UNIT / "protocol") not in sys.path:
    sys.path.insert(0, str(TESTS_UNIT / "protocol"))

from protocol_kit import make_bundle  # noqa: E402

NOW = datetime(2026, 10, 7, 12, 30, 45, tzinfo=UTC)


def make_capture(registry, **fields):
    from ai_dm.reports.capture import TurnCapture

    data = {
        "turn_seq": 5, "run_ids": ["run-1"], "player_input": "Открываю дверь", "tags": [],
        "status": "committed", "failure_reason": None, "before": make_bundle(registry),
        "after": None, "now_iso": NOW.isoformat(), "model": "claude-opus-5-5",
    }
    data.update(fields)
    return TurnCapture(**data)
