from typing import Literal

from pydantic import BaseModel, ConfigDict


class DeathRecord(BaseModel):
    model_config = ConfigDict(extra="forbid")
    cause: Literal["goal", "hazard", "chance", "old_age"]
    by: str | None = None
    at_s: int
    location_id: str | None = None
    text: str = ""
