import json

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import (
    LlmFatal,
    LlmTransient,
    is_network_error,
    is_timeout_error,
    retry_after_of,
)
from ai_dm.llm.keys import redact
from ai_dm.llm.types import ChatResponse, Opaque, Text, ToolCall, ToolResult, Usage

# коды ошибки упавшего ответа, после которых повтор имеет смысл
TRANSIENT_CODES = ("server_error", "rate_limit_exceeded")
# причина обрыва (incomplete_details.reason) -> stop_reason; остальные -- "other"
INCOMPLETE_STOPS = {"max_output_tokens": "max_tokens", "content_filter": "refusal"}


def block_to_item(block, role):
    if isinstance(block, Text):
        kind = "output_text" if role == "assistant" else "input_text"
        return {"type": "message", "role": role, "content": [{"type": kind, "text": block.text}]}
    if isinstance(block, ToolCall):
        arguments = json.dumps(block.input, ensure_ascii=False)
        return {
            "type": "function_call", "call_id": block.id, "name": block.name,
            "arguments": arguments,
        }
    if isinstance(block, ToolResult):
        output = block.content
        if block.is_error:
            output = json.dumps({"error": block.content}, ensure_ascii=False)
        return {"type": "function_call_output", "call_id": block.call_id, "output": output}
    return None


def item_from_api(item):
    return item.model_dump(mode="json", exclude_none=True)


def parse_call(item):
    try:
        arguments = json.loads(item.arguments)
    except ValueError as error:
        raise LlmFatal("аргументы вызова не JSON") from error
    return ToolCall(id=item.call_id, name=item.name, input=arguments)


def parse_output(output, cut):
    # (блоки Text и ToolCall, вызовы, текст отказа)
    content = []
    calls = []
    refusal = None
    parts = [p for item in output if item.type == "message" for p in item.content]
    for part in parts:
        if part.type == "output_text":
            content.append(Text(text=part.text))
        elif part.type == "refusal":
            refusal = part.refusal
    if not cut:
        calls = [parse_call(item) for item in output if item.type == "function_call"]
    return content + calls, calls, refusal


class OpenAIAdapter:
    # адрес API хостера; у OpenAI не задан (ChatCompletionsAdapter берёт из providers)
    base_url = None

    def __init__(self, model, app_cfg, *, client_factory=None, api_key=None):
        self.model = model
        self.cfg = app_cfg
        self.client_factory = client_factory
        self.api_key = api_key
        self.client = None

    def info(self):
        return AdapterInfo(provider="openai", model=self.model)

    def get_client(self):
        if self.client is None:
            factory = self.client_factory
            if factory is None:
                import openai

                factory = openai.OpenAI
            # повторы -- наши (retry.py), у SDK их нет
            options = {}
            if self.base_url is not None:
                options["base_url"] = self.base_url
            self.client = factory(
                api_key=self.api_key, max_retries=0, timeout=self.cfg.retry.timeout_s, **options,
            )
        return self.client

    def build_tools(self, req):
        strict = self.cfg.llm.strict_tools
        return [
            {
                "type": "function", "name": tool.name, "description": tool.description,
                "parameters": tool.input_schema, "strict": tool.strict and strict,
            }
            for tool in req.tools
        ]

    def build_input(self, req):
        items = []
        for message in req.messages:
            raw = [
                b.raw["items"] for b in message.content
                if isinstance(b, Opaque) and b.provider == "openai"
            ]
            if raw:
                # элементы модели возвращаются без изменений вместо Text / ToolCall этого сообщения
                items.extend(item for chunk in raw for item in chunk)
            else:
                blocks = (block_to_item(b, message.role) for b in message.content)
                items.extend(item for item in blocks if item is not None)
        return items

    def build_kwargs(self, req):
        kwargs = {
            "model": req.model,
            "input": self.build_input(req),
            "max_output_tokens": req.max_tokens,
            "store": False,
            "include": ["reasoning.encrypted_content"],
        }
        if req.system:
            kwargs["instructions"] = "\n\n".join(b.text for b in req.system)
        if req.tools:
            kwargs["tools"] = self.build_tools(req)
        if req.effort is not None:
            kwargs["reasoning"] = {"effort": req.effort}
        return kwargs

    def translate_error(self, error):
        text = redact(str(error), [self.api_key])
        code = getattr(error, "status_code", None)
        if code is None:
            if is_network_error(error):
                return LlmTransient(text, timeout=is_timeout_error(error))
            return LlmFatal(text)
        if code in (408, 429) or code >= 500:
            return LlmTransient(text, retry_after=retry_after_of(error), timeout=(code == 504))
        return LlmFatal(text)

    def complete(self, req):
        kwargs = self.build_kwargs(req)
        client = self.get_client()
        try:
            response = client.responses.create(**kwargs)
        except Exception as error:
            raise self.translate_error(error) from error
        return self.parse_response(response, req)

    def raise_failed(self, response):
        error = response.error
        code = None if error is None else error.code
        text = redact(f"{code}: {'' if error is None else error.message}", [self.api_key])
        if code in TRANSIENT_CODES:
            raise LlmTransient(text)
        raise LlmFatal(text)

    def parse_response(self, response, req):
        if response.status == "failed":
            self.raise_failed(response)
        # при обрыве по max_output_tokens аргументы вызова могут быть оборваны: вызовы не разбираем
        cut = self.incomplete_reason(response) == "max_output_tokens"
        content, calls, refusal = parse_output(response.output, cut)
        if response.output:
            raw = [item_from_api(item) for item in response.output]
            content.append(Opaque(provider="openai", raw={"items": raw}))
        stop_reason, stop_detail = self.stop_of(response, calls, refusal)
        return ChatResponse(
            content=content, stop_reason=stop_reason, usage=self.usage_of(response.usage),
            request_id=getattr(response, "_request_id", None),
            model=response.model or req.model, stop_detail=stop_detail,
        )

    def incomplete_reason(self, response):
        if response.status != "incomplete" or response.incomplete_details is None:
            return None
        return response.incomplete_details.reason

    def stop_of(self, response, calls, refusal):
        # причина остановки и деталь: текст отказа или сырая причина обрыва (content_filter и т. п.)
        if calls:
            return "tool_use", None
        if refusal is not None:
            return "refusal", refusal
        if response.status == "incomplete":
            reason = self.incomplete_reason(response)
            detail = None if reason == "max_output_tokens" else reason
            return INCOMPLETE_STOPS.get(reason, "other"), detail
        return ("end_turn" if response.status == "completed" else "other"), None

    def usage_of(self, usage):
        if usage is None:
            return Usage()
        details = usage.input_tokens_details
        cached = getattr(details, "cached_tokens", None) or 0
        written = getattr(details, "cache_write_tokens", None) or 0
        # input_tokens включает чтение и запись кэша; reasoning уже в output_tokens
        return Usage(
            input=(usage.input_tokens or 0) - cached - written,
            output=usage.output_tokens or 0,
            cache_read=cached,
            cache_write=written,
        )
