from typing import Protocol

from pydantic import BaseModel, ConfigDict

from ai_dm.llm.types import ChatRequest, ChatResponse


class AdapterInfo(BaseModel):
    model_config = ConfigDict(extra="forbid")
    provider: str
    model: str


class ModelAdapter(Protocol):
    def complete(self, req: ChatRequest) -> ChatResponse: ...

    def info(self) -> AdapterInfo: ...
