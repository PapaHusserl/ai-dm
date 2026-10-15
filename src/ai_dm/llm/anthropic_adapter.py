from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient, is_network_error, is_timeout_error
from ai_dm.llm.keys import redact
from ai_dm.llm.types import ChatResponse, Opaque, Text, ToolCall, ToolResult, Usage

# модели без adaptive thinking (старый режим budget_tokens): thinking не передаём
NO_ADAPTIVE_PREFIXES = ("claude-haiku-4",)
STOP_REASONS = ("end_turn", "tool_use", "max_tokens", "refusal")


def block_to_api(block):
    if isinstance(block, Text):
        return {"type": "text", "text": block.text}
    if isinstance(block, ToolCall):
        return {"type": "tool_use", "id": block.id, "name": block.name, "input": block.input}
    if isinstance(block, ToolResult):
        result = {"type": "tool_result", "tool_use_id": block.call_id, "content": block.content}
        if block.is_error:
            result["is_error"] = True
        return result
    return block.raw


def block_from_api(block):
    if block.type == "text":
        return Text(text=block.text)
    if block.type == "tool_use":
        return ToolCall(id=block.id, name=block.name, input=block.input)
    return Opaque(provider="anthropic", raw=block.model_dump(mode="json", exclude_none=True))


def retry_after_of(error):
    response = getattr(error, "response", None)
    if response is None:
        return None
    millis = response.headers.get("retry-after-ms")
    try:
        return float(millis) / 1000
    except (TypeError, ValueError):
        pass
    try:
        return float(response.headers.get("retry-after"))
    except (TypeError, ValueError):
        return None


class AnthropicAdapter:
    def __init__(self, model, app_cfg, *, client_factory=None, api_key=None):
        self.model = model
        self.cfg = app_cfg
        self.client_factory = client_factory
        self.api_key = api_key
        self.client = None

    def info(self):
        return AdapterInfo(provider="anthropic", model=self.model)

    def get_client(self):
        if self.client is None:
            factory = self.client_factory
            if factory is None:
                import anthropic

                factory = anthropic.Anthropic
            # повторы -- наши (retry.py), у SDK их нет
            self.client = factory(
                api_key=self.api_key, max_retries=0, timeout=self.cfg.retry.timeout_s,
            )
        return self.client

    def build_tools(self, req):
        tools = []
        for tool in req.tools:
            data = tool.model_dump()
            if not self.cfg.llm.strict_tools:
                data["strict"] = False
            tools.append(data)
        return tools

    def build_base(self, req):
        # не больше 4 точек cache_control (лимит Anthropic): rules, world, память, сообщение
        system = []
        for block in req.system:
            item = {"type": "text", "text": block.text}
            if block.cache:
                ttl = self.cfg.llm.cache_ttl if block.stable else "5m"
                item["cache_control"] = {"type": "ephemeral", "ttl": ttl}
            system.append(item)
        messages = []
        for message in req.messages:
            content = [
                block_to_api(b) for b in message.content
                if not (isinstance(b, Opaque) and b.provider != "anthropic")
            ]
            if content and message.cache:
                content[-1] = {
                    **content[-1], "cache_control": {"type": "ephemeral", "ttl": "5m"},
                }
            if content:
                messages.append({"role": message.role, "content": content})
        base = {"model": req.model, "messages": messages}
        if system:
            base["system"] = system
        if req.tools:
            base["tools"] = self.build_tools(req)
        return base

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

    def thinking_of(self, req):
        mode = self.cfg.llm.thinking.get(req.role)
        if mode is None or req.model.startswith(NO_ADAPTIVE_PREFIXES):
            return None
        return {"type": "adaptive", "display": self.cfg.llm.thinking_display}

    def usage_of(self, usage):
        # запись кэша по TTL: 5m и 1h стоят по-разному; нет разбивки -- всё считаем как 5m
        created = getattr(usage, "cache_creation", None)
        if created is None:
            write_5m = usage.cache_creation_input_tokens or 0
            write_1h = 0
        else:
            write_5m = created.ephemeral_5m_input_tokens or 0
            write_1h = created.ephemeral_1h_input_tokens or 0
        return Usage(
            input=usage.input_tokens or 0,
            output=usage.output_tokens or 0,
            cache_write=write_5m,
            cache_write_1h=write_1h,
            cache_read=usage.cache_read_input_tokens or 0,
        )

    def complete(self, req):
        kwargs = self.build_base(req)
        kwargs["max_tokens"] = req.max_tokens
        thinking = self.thinking_of(req)
        if thinking is not None:
            kwargs["thinking"] = thinking
        if req.effort is not None:
            kwargs["output_config"] = {"effort": req.effort}
        client = self.get_client()
        messages_api = client.messages
        if self.cfg.llm.refusal_fallback:
            kwargs["betas"] = ["server-side-fallback-2026-07-01"]
            kwargs["fallbacks"] = "default"
            messages_api = client.beta.messages
        try:
            response = messages_api.create(**kwargs)
        except Exception as error:
            raise self.translate_error(error) from error
        stop_reason = response.stop_reason if response.stop_reason in STOP_REASONS else "other"
        return ChatResponse(
            content=[block_from_api(b) for b in response.content],
            stop_reason=stop_reason,
            usage=self.usage_of(response.usage),
            request_id=getattr(response, "_request_id", None),
            model=response.model or req.model,
        )
