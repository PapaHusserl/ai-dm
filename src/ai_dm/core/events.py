from pydantic import BaseModel, ConfigDict


class DomainEvent(BaseModel):
    model_config = ConfigDict(extra="forbid")
    type: str
    data: dict[str, int | str | bool | None]
