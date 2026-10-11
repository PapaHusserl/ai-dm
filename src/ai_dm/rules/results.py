from typing import Literal

from pydantic import BaseModel


class Rejected(BaseModel):
    status: Literal["rejected"] = "rejected"
    reason: str
    report_tag: str | None
