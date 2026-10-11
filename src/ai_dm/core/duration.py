import re

from pydantic import BaseModel

UNITS = {"d": 86400, "h": 3600, "m": 60}
DURATION_RE = re.compile(r"([0-9]+)([dhm])")


class DurationParseError(ValueError):
    pass


class Duration(BaseModel):
    seconds: int

    @classmethod
    def parse(cls, text: str) -> "Duration":
        m = DURATION_RE.fullmatch(text.strip())
        if m is None:
            raise DurationParseError(f"не длительность: {text!r}")
        return cls(seconds=int(m.group(1)) * UNITS[m.group(2)])
