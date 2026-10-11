from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.journal import request_fingerprint
from ai_dm.llm.types import ChatResponse


class ReplayDivergence(Exception):
    pass


class ReplayAdapter:
    # role: брать только записи этой роли (порядок внутри роли сохраняется); None -- все записи
    def __init__(self, records, role=None):
        self.records = [r for r in records if role is None or r["role"] == role]
        self.position = 0

    def info(self):
        return AdapterInfo(provider="replay", model="replay")

    def complete(self, req):
        if self.position >= len(self.records):
            raise ReplayDivergence(f"лишний вызов {self.position + 1}: журнал кончился")
        record = self.records[self.position]
        self.position += 1
        if record["request"]["fingerprint"] != request_fingerprint(req):
            raise ReplayDivergence(
                f"вызов {self.position} (роль {req.role}): запрос не совпал с журналом"
            )
        error = record["error"]
        if error is not None:
            if error["kind"] == "transient":
                raise LlmTransient(error["message"], retry_after=error["retry_after"])
            raise LlmFatal(error["message"])
        return ChatResponse.model_validate(record["response"])
