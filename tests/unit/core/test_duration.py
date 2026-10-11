# Ожидаемый API: ai_dm.core.duration
#   Duration(BaseModel): seconds: int
#   Duration.parse(text: str) -> Duration   -- "<целое>d|h|m", d=86400 с, h=3600 с, m=60 с;
#                                              мусор -> DurationParseError
#   DurationParseError(ValueError)
import pytest

from ai_dm.core.duration import Duration, DurationParseError


def test_parse_days():
    assert Duration.parse("7d").seconds == 7 * 86400


def test_parse_hours():
    assert Duration.parse("8h").seconds == 8 * 3600


def test_parse_minutes():
    assert Duration.parse("10m").seconds == 600


def test_parse_strips_spaces():
    assert Duration.parse(" 7d ").seconds == 7 * 86400


@pytest.mark.parametrize("bad", ["", "7", "d", "d7", "7x", "-1d", "1.5h", "7 d d", "abc", "7dd"])
def test_parse_garbage_is_error(bad):
    with pytest.raises(DurationParseError):
        Duration.parse(bad)


def test_error_is_value_error():
    assert issubclass(DurationParseError, ValueError)
