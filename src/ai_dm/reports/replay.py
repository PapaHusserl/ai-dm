import json
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

from ai_dm.persistence.layout import slot_dir
from ai_dm.persistence.store import load_slot, peek_campaign_id

# поля времени реального мира в дампе бандла (путь от корня); всё прочее -- состояние игры
TIME_FIELDS = (("manifest", "saved_at"),)
MAX_DIFFS = 20
MISSING = "<нет>"


@dataclass
class ReportReplay:
    # то, что нужно прогнать ход заново: бандл до хода, записи журнала, фраза, now, ожидание
    meta: dict
    before: object
    expected: object | None
    records: list
    player_input: str | None
    now_iso: str
    failure_reason: str | None
    # версия схемы снимка before до миграции (для сообщения о расхождении)
    schema_version: int = 0


def load_bundle(root, world_id, context_for):
    # слот копируется во временную папку: load_slot может мигрировать и писать
    temp = Path(tempfile.mkdtemp(prefix="ai-dm-report-"))
    try:
        shutil.copytree(root, temp / "slots-root", dirs_exist_ok=True)
        folder = temp / "slots-root"
        context = None
        if context_for is not None:
            context = context_for(peek_campaign_id(folder, world_id, "auto"))
        return load_slot(folder, world_id, "auto", context=context)
    finally:
        shutil.rmtree(temp, ignore_errors=True)


def load_records(path):
    file = path / "journal" / "calls.jsonl"
    if not file.is_file():
        return []
    return [json.loads(line) for line in file.read_text(encoding="utf-8").splitlines() if line]


def load_report(path, context_for=None) -> ReportReplay:
    # context_for(campaign_id) -> MigrationContext для миграций снимков; None -- без контекста
    path = Path(path)
    meta = json.loads((path / "meta.json").read_text(encoding="utf-8"))
    world_id = meta["world_id"]
    before = load_bundle(path / "before", world_id, context_for)
    expected = None
    if meta["status"] == "committed" and (path / "after").is_dir():
        expected = load_bundle(path / "after", world_id, context_for)
    manifest = slot_dir(path / "before", world_id, "auto") / "manifest.json"
    schema_version = json.loads(manifest.read_text(encoding="utf-8")).get("schema_version", 0)
    return ReportReplay(
        meta=meta, before=before, expected=expected, records=load_records(path),
        player_input=meta["player_input"], now_iso=meta["now"],
        failure_reason=meta["failure_reason"], schema_version=schema_version,
    )


def dump(bundle) -> dict:
    data = bundle.model_dump(mode="json")
    for field in TIME_FIELDS:
        data[field[0]].pop(field[1], None)
    return data


def diff(path, expected, actual, lines) -> None:
    if isinstance(expected, dict) and isinstance(actual, dict):
        for key in sorted(expected.keys() | actual.keys()):
            diff(f"{path}.{key}", expected.get(key, MISSING), actual.get(key, MISSING), lines)
    elif isinstance(expected, list) and isinstance(actual, list) and len(expected) == len(actual):
        for number, pair in enumerate(zip(expected, actual, strict=True)):
            diff(f"{path}[{number}]", pair[0], pair[1], lines)
    elif expected != actual:
        lines.append(f"{path}: ожидалось {repr(expected)[:80]}, получено {repr(actual)[:80]}")


def compare(expected, actual) -> list[str]:
    # расхождения двух бандлов без полей времени; пустой список -- состояние совпало
    lines = []
    diff("", dump(expected), dump(actual), lines)
    if len(lines) > MAX_DIFFS:
        lines = lines[:MAX_DIFFS] + [f"... и ещё {len(lines) - MAX_DIFFS}"]
    return [line.removeprefix(".") for line in lines]
