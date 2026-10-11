import hashlib
import json
import logging

from ai_dm.llm.adapter import AdapterInfo
from ai_dm.llm.errors import LlmFatal, LlmTransient, is_network_error
from ai_dm.llm.keys import redact
from ai_dm.llm.types import ChatResponse, Opaque, Text, ToolCall, ToolResult, Usage

log = logging.getLogger(__name__)

FINISH_REASONS = {
    "STOP": "end_turn", "MAX_TOKENS": "max_tokens", "SAFETY": "refusal",
    "PROHIBITED_CONTENT": "refusal", "BLOCKLIST": "refusal", "SPII": "refusal",
    "RECITATION": "refusal",
}


def strip_additional(node):
    # у Gemini схема функции -- подмножество OpenAPI: additionalProperties не нужен
    if isinstance(node, dict):
        return {k: strip_additional(v) for k, v in node.items() if k != "additionalProperties"}
    if isinstance(node, list):
        return [strip_additional(v) for v in node]
    return node


class GeminiAdapter:
    def __init__(self, model, app_cfg, *, client=None, sdk=None, api_key=None):
        self.model = model
        self.cfg = app_cfg
        self.client = client
        self.sdk = sdk
        self.api_key = api_key
        # явные кэши: (модель, sha256 system, sha256 tools) -> имя кэша; None -- кэш не получился
        self.caches = {}
        # (модель, sha256 tools, роль) -> (ключ, имя) последнего созданного кэша: его заменяет новый
        self.latest = {}
        # токены и токен-минуты созданных кэшей, ещё не попавшие в учёт ответа
        self.pending_write = 0
        self.pending_minutes = 0

    def info(self):
        return AdapterInfo(provider="gemini", model=self.model)

    def get_sdk(self):
        if self.sdk is None:
            from google.genai import types

            self.sdk = types
        return self.sdk

    def get_client(self):
        if self.client is None:
            from google import genai

            options = self.get_sdk().HttpOptions(timeout=self.cfg.retry.timeout_s * 1000)
            self.client = genai.Client(api_key=self.api_key, http_options=options)
        return self.client

    def build_contents(self, req):
        sdk = self.get_sdk()
        call_names = {}
        contents = []
        for message in req.messages:
            role = "model" if message.role == "assistant" else "user"
            opaque = [
                b for b in message.content if isinstance(b, Opaque) and b.provider == "gemini"
            ]
            parts = []
            if opaque:
                # части модели возвращаются без изменений вместо Text / ToolCall этого сообщения
                for block in message.content:
                    if isinstance(block, ToolCall):
                        call_names[block.id] = block.name
                for block in opaque:
                    parts.extend(sdk.Part(**raw) for raw in block.raw["parts"])
            else:
                for block in message.content:
                    if isinstance(block, Text):
                        parts.append(sdk.Part(text=block.text))
                    elif isinstance(block, ToolCall):
                        call_names[block.id] = block.name
                        call = sdk.FunctionCall(name=block.name, args=block.input)
                        parts.append(sdk.Part(function_call=call))
                    elif isinstance(block, ToolResult):
                        key = "error" if block.is_error else "result"
                        if block.call_id not in call_names:
                            raise ValueError(f"результат для неизвестного вызова {block.call_id}")
                        name = call_names[block.call_id]
                        response = {key: block.content}
                        if block.call_id.startswith("gemini-"):
                            parts.append(sdk.Part.from_function_response(
                                name=name, response=response,
                            ))
                        else:
                            # id пришёл от API -- возвращаем его
                            result = sdk.FunctionResponse(
                                id=block.call_id, name=name, response=response,
                            )
                            parts.append(sdk.Part(function_response=result))
            if parts:
                contents.append(sdk.Content(role=role, parts=parts))
        return contents

    def build_prefix_fields(self, req):
        # то, что кэшируется: system, tools и tool_config
        sdk = self.get_sdk()
        fields = {
            "tool_config": sdk.ToolConfig(
                function_calling_config=sdk.FunctionCallingConfig(mode="AUTO")
            ),
        }
        # все блоки system, и память тоже: при смене памяти ключ меняется и кэш создаётся заново
        texts = [b.text for b in req.system]
        if texts:
            fields["system_instruction"] = "\n\n".join(texts)
        if req.tools:
            declarations = [
                sdk.FunctionDeclaration(
                    name=t.name, description=t.description,
                    parameters=strip_additional(t.input_schema),
                )
                for t in req.tools
            ]
            fields["tools"] = [sdk.Tool(function_declarations=declarations)]
        return fields

    def build_config(self, req, cache_name=None):
        sdk = self.get_sdk()
        fields = {
            "automatic_function_calling": sdk.AutomaticFunctionCallingConfig(disable=True),
            "max_output_tokens": req.max_tokens,
        }
        if cache_name is None:
            fields.update(self.build_prefix_fields(req))
        else:
            # с cached_content system, tools и tool_config уже в кэше и в запросе не передаются
            fields["cached_content"] = cache_name
        return sdk.GenerateContentConfig(**fields)

    def cache_key(self, req):
        system = json.dumps([b.text for b in req.system], ensure_ascii=False)
        tools = json.dumps([t.model_dump(mode="json") for t in req.tools], ensure_ascii=False)
        return (
            req.model,
            hashlib.sha256(system.encode()).hexdigest(),
            hashlib.sha256(tools.encode()).hexdigest(),
        )

    def create_cache(self, req, key):
        # имя нового кэша или None (ниже минимального размера, ошибка): тогда запрос без кэша
        sdk = self.get_sdk()
        minutes = 5 if self.cfg.llm.cache_ttl == "5m" else 60
        config = sdk.CreateCachedContentConfig(
            ttl=f"{minutes * 60}s", **self.build_prefix_fields(req),
        )
        try:
            cache = self.get_client().caches.create(model=req.model, config=config)
        except Exception as error:
            code = getattr(error, "code", None)
            if code is not None and 400 <= code < 500:
                # по ошибке клиента (например, мало токенов) повторять смысла нет
                self.caches[key] = None
            return None
        tokens = 0
        if cache.usage_metadata is not None:
            tokens = cache.usage_metadata.total_token_count or 0
        self.delete_replaced(req, key, cache.name)
        self.pending_write += tokens
        self.pending_minutes += tokens * minutes
        self.caches[key] = cache.name
        return cache.name

    def delete_replaced(self, req, key, name):
        # новый кэш (сменилась память) заменяет прежний той же модели, tools и роли: старый удаляем
        group = (key[0], key[2], req.role)
        old = self.latest.get(group)
        self.latest[group] = (key, name)
        if old is None or old[0] == key:
            return
        self.caches.pop(old[0], None)
        try:
            self.get_client().caches.delete(name=old[1])
        except Exception as error:
            text = redact(str(error), [self.api_key])
            log.warning("не удалось удалить старый кэш Gemini: %s", text)

    def get_cache(self, req):
        if not req.system and not req.tools:
            return None
        if req.role == "world" and not self.cfg.llm.gemini_cache_world:
            # роль world зовётся редко, хранение кэша дороже повторной отправки префикса
            return None
        key = self.cache_key(req)
        if key in self.caches:
            return self.caches[key]
        return self.create_cache(req, key)

    def translate_error(self, error):
        text = redact(str(error), [self.api_key])
        code = getattr(error, "code", None)
        if code is None:
            if is_network_error(error):
                return LlmTransient(text)
            return LlmFatal(text)
        if code in (408, 429) or code >= 500:
            return LlmTransient(text)
        return LlmFatal(text)

    def complete(self, req):
        contents = self.build_contents(req)
        cache_name = self.get_cache(req)
        recreated = False
        while True:
            config = self.build_config(req, cache_name)
            try:
                response = self.get_client().models.generate_content(
                    model=req.model, contents=contents, config=config,
                )
                break
            except Exception as error:
                code = getattr(error, "code", None)
                if cache_name is None or code not in (403, 404) or recreated:
                    raise self.translate_error(error) from error
                # кэш истёк или удалён: пересоздаём один раз и повторяем запрос
                del self.caches[self.cache_key(req)]
                recreated = True
                cache_name = self.get_cache(req)
        result = self.parse_response(response, req)
        result.usage.cache_write += self.pending_write
        result.usage.cache_storage_min += self.pending_minutes
        self.pending_write = 0
        self.pending_minutes = 0
        return result

    def parse_response(self, response, req):
        candidate = response.candidates[0] if response.candidates else None
        parts = []
        if candidate is not None and candidate.content is not None:
            parts = candidate.content.parts or []
        request_id = response.response_id
        content = []
        for part in parts:
            if part.text and not part.thought:
                content.append(Text(text=part.text))
        calls = response.function_calls or []
        for i, call in enumerate(calls, start=1):
            call_id = call.id or f"gemini-{request_id or 'call'}-{i}"
            content.append(ToolCall(id=call_id, name=call.name, input=dict(call.args or {})))
        if parts:
            raw = [p.model_dump(mode="json", exclude_none=True) for p in parts]
            content.append(Opaque(provider="gemini", raw={"parts": raw}))
        return ChatResponse(
            content=content, stop_reason=self.stop_reason(response, candidate, calls),
            usage=self.usage(response), request_id=request_id,
            model=response.model_version or req.model,
        )

    def stop_reason(self, response, candidate, calls):
        if calls:
            return "tool_use"
        if candidate is None:
            feedback = response.prompt_feedback
            reason = None if feedback is None else feedback.block_reason
            if reason is not None and reason.name != "BLOCKED_REASON_UNSPECIFIED":
                return "refusal"
            return "other"
        if candidate.finish_reason is None:
            return "other"
        return FINISH_REASONS.get(candidate.finish_reason.name, "other")

    def usage(self, response):
        meta = response.usage_metadata
        if meta is None:
            return Usage()
        # prompt_token_count включает кэш; мышление тарифицируется как выход
        cached = meta.cached_content_token_count or 0
        return Usage(
            input=(meta.prompt_token_count or 0) - cached,
            output=(meta.candidates_token_count or 0) + (meta.thoughts_token_count or 0),
            cache_read=cached,
        )
