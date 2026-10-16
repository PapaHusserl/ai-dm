import json
import os
import shutil
import uuid
from pathlib import Path

from ai_dm.persistence.store import write_slot
from ai_dm.reports.markdown import render

REPORT_FORMAT = 1
MB = 1_000_000


def meta_of(world_id, capture, text, calls, complete=True) -> dict:
    return {
        "report_format": REPORT_FORMAT,
        "world_id": world_id,
        "manual": bool(text),
        "turn_seq": capture.turn_seq,
        "run_ids": capture.run_ids,
        "player_input": capture.player_input,
        "tags": capture.tags,
        "status": capture.status,
        "failure_reason": capture.failure_reason,
        "now": capture.now_iso,
        "model": capture.model,
        "replayable": calls is not None and complete,
        "calls": 0 if calls is None else len(calls),
    }


def free_dir(path) -> Path:
    # при коллизии имени -- суффикс -2, -3, ...
    result = path
    number = 1
    while result.exists():
        number += 1
        result = path.with_name(f"{path.name}-{number}")
    return result


def write_snapshots(tmp, world_id, capture, now) -> None:
    # before/ и after/ -- корни сейвов: load_slot(<отчёт>/before, world_id, "auto")
    write_slot(tmp / "before", world_id, capture.before, "auto", saved_at=now.isoformat())
    if capture.status == "committed" and capture.after is not None:
        write_slot(tmp / "after", world_id, capture.after, "auto", saved_at=now.isoformat())


def write_journal(tmp, journal, calls) -> bool:
    # записи хода и их блобы копией: журнал мира ротируется; False -- какого-то блоба нет
    complete = True
    folder = tmp / "journal"
    (folder / "blobs").mkdir(parents=True)
    lines = [json.dumps(record, ensure_ascii=False) + "\n" for record in calls]
    (folder / "calls.jsonl").write_text("".join(lines), encoding="utf-8")
    for record in calls:
        for key in ("system_sha256", "tools_sha256"):
            blob = journal.dir / "blobs" / f"{record['request'][key]}.json"
            if blob.exists():
                shutil.copyfile(blob, folder / "blobs" / blob.name)
            else:
                complete = False
    return complete


def write_report(saves_root, world_id, capture, text, now, journal=None, recent_turns=5) -> Path:
    issues = Path(saves_root) / world_id / "issues"
    issues.mkdir(parents=True, exist_ok=True)
    label = "manual" if text else "+".join(capture.tags)
    final = free_dir(issues / f"{now:%Y%m%dT%H%M%S}-t{capture.turn_seq}-{label}")
    tmp = issues / f"tmp-{uuid.uuid4().hex[:8]}"
    try:
        tmp.mkdir()
        calls = None
        complete = True
        if journal is not None:
            calls = journal.records_for(capture.run_ids)
            complete = write_journal(tmp, journal, calls)
        write_snapshots(tmp, world_id, capture, now)
        (tmp / "report.md").write_text(render(capture, text, calls, recent_turns), encoding="utf-8")
        meta = meta_of(world_id, capture, text, calls, complete)
        meta = json.dumps(meta, ensure_ascii=False, indent=2)
        (tmp / "meta.json").write_text(meta, encoding="utf-8")
        os.replace(tmp, final)
    except OSError:
        shutil.rmtree(tmp, ignore_errors=True)
        raise
    return final


def dir_size(path) -> int:
    return sum(f.stat().st_size for f in Path(path).rglob("*") if f.is_file())


def is_manual(path) -> bool:
    try:
        return bool(json.loads((path / "meta.json").read_text(encoding="utf-8")).get("manual"))
    except (OSError, ValueError, AttributeError):
        return False


def trim_issues(saves_root, world_id, max_mb) -> list[Path]:
    # удаляет самые старые авто-репорты, пока issues/ больше max_mb; самый новый и manual целы
    issues = Path(saves_root) / world_id / "issues"
    if max_mb == 0 or not issues.is_dir():
        return []
    folders = sorted(p for p in issues.iterdir() if p.is_dir() and not p.name.startswith("tmp-"))
    sizes = {p: dir_size(p) for p in folders}
    total = sum(sizes.values())
    removed = []
    for path in folders[:-1]:
        if total <= max_mb * MB:
            break
        if is_manual(path):
            continue
        shutil.rmtree(path)
        total -= sizes[path]
        removed.append(path)
    return removed
