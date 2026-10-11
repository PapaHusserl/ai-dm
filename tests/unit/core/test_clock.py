# Ожидаемый API: ai_dm.core.clock
#   Month(BaseModel): name: str, days: int
#   Calendar(BaseModel): months: list[Month]
#       .days_in_year -> int ; .seconds_in_year -> int
#   default_calendar() -> Calendar     -- 12 месяцев по 30 дней, уникальные русские названия
#   GameClock(BaseModel): now_s: int = 0, calendar: Calendar = default_calendar()
#       (создаётся ТОЛЬКО по ключевым аргументам: GameClock(now_s=..., calendar=...))
#       now_s = 0  <=>  "0001-01-01 00:00:00" (эпоха: год 1, месяц 1, день 1)
#       .advance(seconds: int) -> None   -- seconds >= 0, иначе ValueError
#       .to_date() -> str                -- "YYYY-MM-DD" (год 4 цифры, месяц и день по 2)
#       GameClock.from_date(text: str, calendar: Calendar | None = None) -> GameClock
#           -- начало суток (now_s кратно 86400); мусор/несуществующая дата -> ValueError
#       .days_in_current_month() -> int
import re

import pytest
from pydantic import ValidationError

from ai_dm.core.clock import Calendar, GameClock, Month, default_calendar

DAY = 86400


def test_default_calendar_12_months_of_30_days():
    cal = default_calendar()
    assert len(cal.months) == 12
    assert all(m.days == 30 for m in cal.months)


def test_default_calendar_russian_unique_names():
    names = [m.name for m in default_calendar().months]
    assert len(set(names)) == 12
    for name in names:
        assert re.fullmatch(r"[А-Яа-яЁё\- ]+", name), name


def test_default_year_length():
    cal = default_calendar()
    assert cal.days_in_year == 360
    assert cal.seconds_in_year == 360 * DAY


def test_epoch_date():
    assert GameClock(now_s=0).to_date() == "0001-01-01"


def test_new_clock_defaults_to_zero():
    assert GameClock().now_s == 0


def test_advance_one_day():
    clock = GameClock(now_s=0)
    clock.advance(DAY)
    assert clock.now_s == DAY
    assert clock.to_date() == "0001-01-02"


def test_advance_less_than_day_keeps_date():
    clock = GameClock(now_s=0)
    clock.advance(DAY - 1)
    assert clock.to_date() == "0001-01-01"


def test_advance_negative_is_error():
    with pytest.raises(ValueError):
        GameClock(now_s=100).advance(-1)


def test_month_boundary():
    clock = GameClock.from_date("1247-03-30")
    clock.advance(DAY)
    assert clock.to_date() == "1247-04-01"


def test_year_boundary():
    clock = GameClock.from_date("1247-12-30")
    clock.advance(DAY)
    assert clock.to_date() == "1248-01-01"


def test_from_date_round_trip():
    clock = GameClock.from_date("1247-03-12")
    assert clock.to_date() == "1247-03-12"


def test_from_date_value():
    expected = ((1246 * 12 + 2) * 30 + 11) * DAY
    assert GameClock.from_date("1247-03-12").now_s == expected


@pytest.mark.parametrize("text", ["1247-03-12", "0001-01-01", "0500-12-30", "2000-07-01"])
def test_round_trip_many(text):
    assert GameClock.from_date(text).to_date() == text


@pytest.mark.parametrize("bad", [
    "", "abc", "1247-13-01", "1247-00-01", "1247-01-31", "1247-01-00", "1247/01/01",
])
def test_from_date_garbage_is_error(bad):
    with pytest.raises(ValueError):
        GameClock.from_date(bad)


def test_days_in_current_month_default():
    assert GameClock.from_date("1247-03-12").days_in_current_month() == 30


# пользовательский календарь: 10 месяцев разной длины (20, 25, 30, 35, 40, 20, 25, 30, 35, 40) = 300
CUSTOM = Calendar(months=[
    Month(name="Первый", days=20),
    Month(name="Второй", days=25),
    Month(name="Третий", days=30),
    Month(name="Четвёртый", days=35),
    Month(name="Пятый", days=40),
    Month(name="Шестой", days=20),
    Month(name="Седьмой", days=25),
    Month(name="Восьмой", days=30),
    Month(name="Девятый", days=35),
    Month(name="Десятый", days=40),
])


def test_custom_calendar_year_length():
    assert CUSTOM.days_in_year == 300


def test_custom_calendar_epoch():
    assert GameClock(now_s=0, calendar=CUSTOM).to_date() == "0001-01-01"


def test_custom_calendar_short_month_boundary():
    clock = GameClock.from_date("0001-01-20", CUSTOM)
    assert clock.now_s == 19 * DAY
    clock.advance(DAY)
    assert clock.to_date() == "0001-02-01"


def test_custom_calendar_long_month_has_day_40():
    clock = GameClock.from_date("0001-05-40", CUSTOM)
    clock.advance(DAY)
    assert clock.to_date() == "0001-06-01"


def test_custom_calendar_day_31_is_valid_where_month_is_long():
    assert GameClock.from_date("0001-04-31", CUSTOM).to_date() == "0001-04-31"


def test_custom_calendar_day_out_of_month_is_error():
    with pytest.raises(ValueError):
        GameClock.from_date("0001-01-21", CUSTOM)


def test_custom_calendar_year_boundary():
    clock = GameClock.from_date("0003-10-40", CUSTOM)
    clock.advance(DAY)
    assert clock.to_date() == "0004-01-01"


def test_custom_calendar_year_starts_at_300_days():
    assert GameClock.from_date("0002-01-01", CUSTOM).now_s == 300 * DAY


def test_custom_calendar_round_trip():
    for text in ["0001-03-30", "0007-09-35", "0100-10-40"]:
        assert GameClock.from_date(text, CUSTOM).to_date() == text


def test_days_in_current_month_custom():
    assert GameClock.from_date("0001-02-10", CUSTOM).days_in_current_month() == 25
    assert GameClock.from_date("0001-05-01", CUSTOM).days_in_current_month() == 40


def test_calendar_without_months_is_error():
    with pytest.raises(ValidationError):
        Calendar(months=[])


def test_month_with_zero_days_is_error():
    with pytest.raises(ValidationError):
        Month(name="X", days=0)
