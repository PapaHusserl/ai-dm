import json

from ai_dm.protocol.decision import Invalid


def render_tool_result(outcome) -> dict:
    content = json.dumps(outcome.model_dump(), sort_keys=True, ensure_ascii=False)
    return {"content": content, "is_error": isinstance(outcome, Invalid)}
