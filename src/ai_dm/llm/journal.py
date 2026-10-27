import gzip
import hashlib
import json
import os

from ai_dm.llm.errors import LlmTransient

MB = 1_000_000


def canon(obj):
    return json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).encode()


def request_fingerprint(req):
    return hashlib.sha256(canon(req.model_dump(mode="json"))).hexdigest()


def segment_number(path):
    # calls-007.jsonl / calls-007.jsonl.gz -> 7
    return int(path.name.split(".")[0].split("-")[1])


def read_lines(path):
    if path.name.endswith(".gz"):
        text = gzip.decompress(path.read_bytes()).decode("utf-8")
    else:
        text = path.read_text(encoding="utf-8")
    lines = text.splitlines()
    records = []
    for i, line in enumerate(lines):
        try:
            records.append(json.loads(line))
        except json.JSONDecodeError:
            # обрыв записи: нечитаемой может быть только последняя строка
            if i != len(lines) - 1:
                raise
    return records


def dump_lines(records):
    return "".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records).encode("utf-8")


class Journal:
    def __init__(self, saves_root, world_id, cfg):
        self.world_id = world_id
        self.cfg = cfg
        self.dir = saves_root / world_id / "journal"

    def segments(self):
        return sorted(self.dir.glob("calls-*"), key=segment_number)

    def write_blob(self, obj):
        data = canon(obj)
        sha = hashlib.sha256(data).hexdigest()
        path = self.dir / "blobs" / f"{sha}.json"
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_bytes(data)
        return sha

    def current_segment(self):
        # открытый (не сжатый) сегмент; если последний сжат или сегментов нет -- следующий номер
        segments = self.segments()
        if not segments:
            return self.dir / "calls-001.jsonl"
        last = segments[-1]
        if last.name.endswith(".gz"):
            return self.dir / f"calls-{segment_number(last) + 1:03d}.jsonl"
        if last.stat().st_size >= self.cfg.segment_mb * MB:
            last.with_name(last.name + ".gz").write_bytes(gzip.compress(last.read_bytes()))
            last.unlink()
            return self.dir / f"calls-{segment_number(last) + 1:03d}.jsonl"
        return last

    def drop_old_segments(self):
        segments = self.segments()
        total = sum(p.stat().st_size for p in segments)
        # последний (открытый) сегмент не удаляем
        dropped = False
        while total > self.cfg.max_mb * MB and len(segments) > 1:
            oldest = segments.pop(0)
            total -= oldest.stat().st_size
            oldest.unlink()
            dropped = True
        if dropped:
            self.drop_orphan_blobs(segments)

    def drop_orphan_blobs(self, segments):
        used = set()
        for path in segments:
            for record in read_lines(path):
                used.add(record["request"]["system_sha256"])
                used.add(record["request"]["tools_sha256"])
        for blob in (self.dir / "blobs").glob("*.json"):
            if blob.stem not in used:
                blob.unlink()

    def record_call(
        self, *, call_id, run_id, ts, turn_seq, attempt, role, provider, model, request,
        response=None, cost_nano=0, error=None, report_tags=(),
        meta=None, duration_s=None,
    ):
        system_sha = self.write_blob([b.model_dump(mode="json") for b in request.system])
        tools_sha = self.write_blob([t.model_dump(mode="json") for t in request.tools])
        if response is None:
            usage = {
                "input": 0, "output": 0, "cache_write": 0, "cache_write_1h": 0, "cache_read": 0,
                "cache_storage_min": 0,
            }
        else:
            usage = response.usage.model_dump()
        if error is None:
            error_dump = None
        else:
            kind = "transient" if isinstance(error, LlmTransient) else "fatal"
            error_dump = {
                "kind": kind, "message": str(error),
                "retry_after": getattr(error, "retry_after", None),
                "timeout": getattr(error, "timeout", False),
            }
        speed = None
        if duration_s is not None:
            duration_s = round(duration_s, 3)
            if response is not None and duration_s > 0:
                speed = round(response.usage.output / duration_s, 1)
        record = {
            "call_id": call_id,
            "run_id": run_id,
            "ts": ts,
            "world_id": self.world_id,
            "turn_seq": turn_seq,
            "attempt": attempt,
            "role": role,
            "provider": provider,
            "model": model,
            "requested_model": request.model,
            "request": {
                "system_sha256": system_sha,
                "tools_sha256": tools_sha,
                "messages": [m.model_dump(mode="json") for m in request.messages],
                "max_tokens": request.max_tokens,
                "effort": request.effort,
                "fingerprint": request_fingerprint(request),
            },
            "response": None if response is None else response.model_dump(mode="json"),
            "usage": usage,
            "cost_nano": cost_nano,
            "request_id": None if response is None else response.request_id,
            "stop_reason": None if response is None else response.stop_reason,
            "error": error_dump,
            "report_tags": list(report_tags),
            "meta": meta or {},
            "turn_status": None,
            "duration_s": duration_s,
            "tokens_per_s": speed,
        }
        path = self.current_segment()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
        self.drop_old_segments()

    def note_start(self, *fields):
        # fields: ts, run_id, turn_seq, role, model, attempt (через табуляцию);
        # висящая попытка -- последняя строка без парной записи в calls-*
        self.dir.mkdir(parents=True, exist_ok=True)
        line = "\t".join(str(f) for f in fields)
        with (self.dir / "attempts.log").open("a", encoding="utf-8") as f:
            f.write(line + "\n")

    def mark_turn(self, run_id, status, role=None):
        # role задана -- только записи этой роли (у границы общий run_id: world и summarizer)
        if status not in ("committed", "aborted"):
            raise ValueError(f"неизвестный статус хода: {status}")
        # с конца: записи прогона лежат в последних сегментах
        for path in reversed(self.segments()):
            records = read_lines(path)
            changed = False
            first = None
            for i, record in enumerate(records):
                if record["run_id"] != run_id:
                    continue
                if first is None:
                    first = i
                if record["turn_status"] is None and role in (None, record["role"]):
                    record["turn_status"] = status
                    changed = True
            if changed:
                data = dump_lines(records)
                tmp = path.with_name("tmp-" + path.name)
                tmp.write_bytes(gzip.compress(data) if path.name.endswith(".gz") else data)
                os.replace(tmp, path)
            # прогон начался внутри этого сегмента: раньше искать нечего
            # (предпосылка: прогоны хода идут в журнале подряд, чужой между ними не вклинивается)
            if first is not None and first > 0:
                break

    def records_for(self, run_ids):
        # записи этих прогонов по порядку; с конца, как mark_turn, чтобы не разжимать весь журнал;
        # предпосылка (проверена в ТБ): записи прогона идут подряд, чужой между ними не вклинивается
        wanted = set(run_ids)
        found = []
        if not wanted:
            return found
        for path in reversed(self.segments()):
            records = read_lines(path)
            mine = [r for r in records if r["run_id"] in wanted]
            found = mine + found
            # прогон начался внутри этого сегмента: раньше искать нечего
            if mine and records[0]["run_id"] not in wanted:
                break
        return found

    def read_records(self):
        records = []
        for path in self.segments():
            records.extend(read_lines(path))
        return records
