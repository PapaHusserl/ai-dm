from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field


class LlmModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class SystemBlock(LlmModel):
    text: str
    cache: bool = False
    # False -- блок меняется по ходу игры (память): у Anthropic TTL 5m; в явный кэш Gemini входит
    # (кэш создаётся заново при смене блока)
    stable: bool = True


class ToolSpec(LlmModel):
    name: str
    description: str
    input_schema: dict
    strict: bool = True


class Text(LlmModel):
    type: Literal["text"] = "text"
    text: str


class ToolCall(LlmModel):
    type: Literal["tool_call"] = "tool_call"
    id: str
    name: str
    input: dict


class ToolResult(LlmModel):
    type: Literal["tool_result"] = "tool_result"
    call_id: str
    content: str
    is_error: bool = False


class Opaque(LlmModel):
    # части ответа провайдера (мышление, подписи): хранятся и возвращаются без изменений
    type: Literal["opaque"] = "opaque"
    provider: str
    raw: dict


Block = Annotated[Text | ToolCall | ToolResult | Opaque, Field(discriminator="type")]


class Message(LlmModel):
    role: Literal["user", "assistant"]
    content: list[Block]
    cache: bool = False


class ChatRequest(LlmModel):
    role: str
    model: str
    system: list[SystemBlock] = []
    tools: list[ToolSpec] = []
    messages: list[Message]
    max_tokens: int
    effort: str | None = None


class Usage(LlmModel):
    model_config = ConfigDict(extra="forbid", strict=True)
    input: int = 0
    output: int = 0
    cache_write: int = 0
    cache_write_1h: int = 0
    cache_read: int = 0
    # хранение явного кэша: токены × минуты TTL (цена -- за токен-час)
    cache_storage_min: int = 0


class ChatResponse(LlmModel):
    content: list[Block]
    stop_reason: Literal["end_turn", "tool_use", "max_tokens", "refusal", "other"]
    stop_detail: str | None = None
    usage: Usage = Usage()
    request_id: str | None = None
    model: str
