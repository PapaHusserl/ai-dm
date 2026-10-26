import json

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal
from ai_dm.llm.openai_adapter import OpenAIAdapter
from ai_dm.llm.types import ChatResponse, Opaque, Text, ToolCall, ToolResult, Usage

# finish_reason -> stop_reason; остальные -- "other"; "tool_calls" сюда не входит: tool_use
# даёт только разобранный вызов, а "tool_calls" без вызовов -- ("other", "tool_calls"),
# иначе пустой tool_use сломал бы цикл хода
FINISH_STOPS = {"stop": "end_turn", "length": "max_tokens", "content_filter": "refusal"}


def parse_call(call):
    try:
        arguments = json.loads(call.function.arguments)
    except ValueError as error:
        raise LlmFatal("аргументы вызова не JSON") from error
    return ToolCall(id=call.id, name=call.function.name, input=arguments)


class ChatCompletionsAdapter(OpenAIAdapter):
    # OpenAI-совместимый хостер (Chat Completions); provider -- имя хостера из providers
    def __init__(self, provider, model, app_cfg, **options):
        super().__init__(model, app_cfg, **options)
        self.provider = provider
        self.base_url = app_cfg.providers[provider].base_url

    def info(self):
        return AdapterInfo(provider=self.provider, model=self.model)

    def build_tools(self, req):
        strict = self.cfg.llm.strict_tools
        return [
            {
                "type": "function",
                "function": {
                    "name": tool.name, "description": tool.description,
                    "parameters": tool.input_schema, "strict": tool.strict and strict,
                },
            }
            for tool in req.tools
        ]

    def build_messages(self, req):
        messages = []
        if req.system:
            messages.append(
                {"role": "system", "content": "\n\n".join(b.text for b in req.system)}
            )
        for message in req.messages:
            raw = [
                b.raw["message"] for b in message.content
                if isinstance(b, Opaque) and b.provider == self.provider
            ]
            if raw:
                # сообщение модели возвращается без изменений вместо Text / ToolCall этого сообщения
                messages.extend(raw)
            elif message.role == "assistant":
                messages.append(self.assistant_message(message))
            else:
                messages.extend(self.user_messages(message))
        return messages

    def assistant_message(self, message):
        texts = [b.text for b in message.content if isinstance(b, Text)]
        calls = [
            {
                "id": b.id, "type": "function",
                "function": {
                    "name": b.name, "arguments": json.dumps(b.input, ensure_ascii=False),
                },
            }
            for b in message.content if isinstance(b, ToolCall)
        ]
        result = {"role": "assistant", "content": "\n\n".join(texts) if texts else None}
        if calls:
            result["tool_calls"] = calls
        return result

    def user_messages(self, message):
        # результаты инструментов идут сразу за сообщением assistant, текст игрока -- после них
        results = []
        for block in message.content:
            if isinstance(block, ToolResult):
                content = block.content
                if block.is_error:
                    content = json.dumps({"error": block.content}, ensure_ascii=False)
                results.append({"role": "tool", "tool_call_id": block.call_id, "content": content})
        texts = [b.text for b in message.content if isinstance(b, Text)]
        if texts:
            results.append({"role": "user", "content": "\n\n".join(texts)})
        return results

    def build_kwargs(self, req):
        kwargs = {
            "model": req.model,
            "messages": self.build_messages(req),
            "max_tokens": req.max_tokens,
        }
        if req.tools:
            kwargs["tools"] = self.build_tools(req)
        if req.effort is not None:
            kwargs["reasoning_effort"] = req.effort
        return kwargs

    def complete(self, req):
        kwargs = self.build_kwargs(req)
        client = self.get_client()
        try:
            response = client.chat.completions.create(**kwargs)
        except Exception as error:
            raise self.translate_error(error) from error
        return self.parse_response(response, req)

    def parse_response(self, response, req):
        choice = response.choices[0]
        message = choice.message
        content = []
        if message.content:
            content.append(Text(text=message.content))
        # при обрыве по длине аргументы вызова могут быть оборваны: вызовы не разбираем
        calls = []
        if choice.finish_reason != "length":
            calls = [parse_call(call) for call in message.tool_calls or []]
        content += calls
        raw = message.model_dump(mode="json", exclude_none=True)
        content.append(Opaque(provider=self.provider, raw={"message": raw}))
        stop_reason, stop_detail = self.stop_of(choice.finish_reason, calls, message.refusal)
        return ChatResponse(
            content=content, stop_reason=stop_reason, usage=self.usage_of(response.usage),
            request_id=getattr(response, "_request_id", None),
            model=response.model or req.model, stop_detail=stop_detail,
        )

    def stop_of(self, finish_reason, calls, refusal):
        # причина остановки и деталь: текст отказа или сырая причина (content_filter и т. п.)
        if calls:
            return "tool_use", None
        if refusal is not None:
            return "refusal", refusal
        stop = FINISH_STOPS.get(finish_reason, "other")
        detail = None if finish_reason in ("stop", "length") else finish_reason
        return stop, detail

    def usage_of(self, usage):
        if usage is None:
            return Usage()
        details = usage.prompt_tokens_details
        cached = getattr(details, "cached_tokens", None) or 0
        # prompt_tokens включает чтение кэша; reasoning уже в completion_tokens
        return Usage(
            input=(usage.prompt_tokens or 0) - cached,
            output=usage.completion_tokens or 0,
            cache_read=cached,
        )
