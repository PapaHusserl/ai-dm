from typing import Literal

from pydantic import BaseModel, ConfigDict, Field


class Decision(BaseModel):
    model_config = ConfigDict(extra="forbid")
    status: Literal["accepted", "clamped", "rejected"]
    reason: str = ""
    signal_to_master: str | None = None
    report_tag: str | None = None
    result: dict = Field(default_factory=dict)
    log: list[str] = Field(default_factory=list)


class Invalid(BaseModel):
    model_config = ConfigDict(extra="forbid")
    code: str
    message: str
    # метка репорта: в ответ модели не попадает
    report_tag: str | None = Field(default=None, exclude=True)
