from pathlib import Path

import yaml

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient
from ai_dm.llm.types import ChatResponse, Text, ToolCall, ToolResult, Usage

STEP_KEYS = {"text", "tool_calls", "error", "stop", "usage", "message", "retry_after", "when"}
CONTENT_KEYS = {"text", "tool_calls", "error", "stop"}
WHEN_KEYS = {"role", "last_message_contains"}
CALL_KEYS = {"id", "name", "input"}


class ScriptError(Exception):
    pass


class ScriptExhausted(ScriptError):
    pass


class ScriptMismatch(ScriptError):
    pass


def check_step(step):
    if not isinstance(step, dict):
        raise ValueError(f"шаг сценария должен быть словарём: {step!r}")
    unknown = set(step) - STEP_KEYS
    if unknown:
        raise ValueError(f"неизвестные ключи шага: {sorted(unknown)}")
    if not CONTENT_KEYS & set(step):
        raise ValueError(f"пустой шаг сценария: {step!r}")
    if "error" in step and step["error"] not in ("transient", "fatal"):
        raise ValueError(f"error должен быть transient или fatal: {step['error']!r}")
    if "stop" in step and step["stop"] not in ("refusal", "max_tokens"):
        raise ValueError(f"stop должен быть refusal или max_tokens: {step['stop']!r}")
    unknown_when = set(step.get("when", {})) - WHEN_KEYS
    if unknown_when:
        raise ValueError(f"неизвестные ключи when: {sorted(unknown_when)}")
    for call in step.get("tool_calls", []):
        if set(call) - CALL_KEYS or "name" not in call:
            raise ValueError(f"плохой tool_call: {call!r}")


def load_script(path):
    data = yaml.safe_load(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or "steps" not in data:
        raise ValueError(f"в сценарии {path} нет ключа steps")
    for step in data["steps"]:
        check_step(step)
    return data["steps"]


def last_message_text(req):
    parts = []
    for block in req.messages[-1].content:
        if isinstance(block, Text):
            parts.append(block.text)
        elif isinstance(block, ToolResult):
            parts.append(block.content)
    return "\n".join(parts)


class ScriptedAdapter:
    def __init__(self, steps, provider="mock", model="mock"):
        for step in steps:
            check_step(step)
        self.steps = list(steps)
        self.provider = provider
        self.model = model
        self.requests = []

    @classmethod
    def from_yaml(cls, path):
        return cls(load_script(path))

    def info(self):
        return AdapterInfo(provider=self.provider, model=self.model)

    def complete(self, req):
        self.requests.append(req)
        number = len(self.requests)
        if not self.steps:
            raise ScriptExhausted(f"сценарий исчерпан (роль {req.role}, вызов {number})")
        step = self.steps[0]
        when = step.get("when", {})
        if "role" in when and when["role"] != req.role:
            raise ScriptMismatch(f"шаг ждёт роль {when['role']}, пришла {req.role}")
        needle = when.get("last_message_contains")
        if needle is not None and needle not in last_message_text(req):
            raise ScriptMismatch(f"в последнем сообщении нет {needle!r}")
        self.steps.pop(0)
        if "error" in step:
            message = step.get("message", "ошибка из сценария")
            if step["error"] == "transient":
                raise LlmTransient(message, retry_after=step.get("retry_after"))
            raise LlmFatal(message)
        content = []
        if "text" in step:
            content.append(Text(text=step["text"]))
        for i, call in enumerate(step.get("tool_calls", []), start=1):
            call_id = call.get("id") or f"mock-call-{number}-{i}"
            content.append(ToolCall(id=call_id, name=call["name"], input=call.get("input", {})))
        if "stop" in step:
            stop_reason = step["stop"]
        elif "tool_calls" in step:
            stop_reason = "tool_use"
        else:
            stop_reason = "end_turn"
        return ChatResponse(
            content=content, stop_reason=stop_reason,
            usage=Usage(**step.get("usage", {})), request_id=f"mock-{number}", model=req.model,
        )
