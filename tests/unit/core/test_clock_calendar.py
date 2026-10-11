# Ожидаемый API: ai_dm.core.clock, календарь пака (этап 3, партия 1; STAGE3-PLAN A2)
#   Holiday(month: int, day: int, name: str, god_id: str | None = None)   -- month с 1
#   Season(name: str, months: list[int])                                  -- номера месяцев с 1
#   Calendar(months, holidays=[], seasons=[...], epoch_note="")  -- новые поля с умолчаниями;
#       Calendar(months=[...]) без holidays / seasons по-прежнему создаётся (совместимость).
#       Проверки (pydantic ValidationError, он же ValueError): праздник в несуществующем дне
#       (день больше days месяца, месяц вне списка); каждый месяц ровно в одном сезоне
#       (дубль, пропуск, номер вне календаря). Проверка god_id по пантеону -- в загрузчике пака.
#   default_calendar(): 12 x 30 и 4 сезона по 3 месяца, Заревень -- в первом сезоне ("зима")
#   GameClock.season() -> str  -- имя сезона текущего месяца
#   GameClock.holiday() -> Holiday | None  -- праздник текущего дня или None
import pytest
from pydantic import ValidationError

from ai_dm.core.clock import DAY, Calendar, GameClock, Holiday, Month, Season, default_calendar


def calendar_10x36(**extra):
    months = [Month(name=f"Месяц {i}", days=36) for i in range(1, 11)]
    seasons = [
        Season(name="холод", months=[1, 2, 3, 4, 5]),
        Season(name="тепло", months=[6, 7, 8, 9, 10]),
    ]
    return Calendar(months=months, seasons=seasons, **extra)


# календарь 10 x 36

def test_calendar_10x36_year_length():
    assert calendar_10x36().days_in_year == 360


def test_calendar_10x36_last_day_of_last_month_is_valid():
    clock = GameClock.from_date("0001-10-36", calendar_10x36())
    assert clock.now_s == (9 * 36 + 35) * DAY


def test_calendar_10x36_has_no_eleventh_month():
    with pytest.raises(ValueError):
        GameClock.from_date("0001-11-01", calendar_10x36())


def test_calendar_10x36_day_37_does_not_exist():
    with pytest.raises(ValueError):
        GameClock.from_date("0001-01-37", calendar_10x36())


def test_calendar_10x36_to_date_from_date_roundtrip():
    calendar = calendar_10x36()
    for text in ["0001-01-01", "0002-05-20", "0003-10-36", "0010-07-01"]:
        assert GameClock.from_date(text, calendar).to_date() == text


def test_calendar_10x36_month_boundary():
    clock = GameClock.from_date("0001-01-36", calendar_10x36())
    clock.advance(DAY)
    assert clock.to_date() == "0001-02-01"


# сезоны

def test_season_by_month():
    calendar = calendar_10x36()
    assert GameClock.from_date("0001-01-01", calendar).season() == "холод"
    assert GameClock.from_date("0001-05-36", calendar).season() == "холод"
    assert GameClock.from_date("0001-06-01", calendar).season() == "тепло"
    assert GameClock.from_date("0007-10-36", calendar).season() == "тепло"


def test_default_calendar_has_four_seasons_of_three_months():
    seasons = default_calendar().seasons
    assert len(seasons) == 4
    assert [len(s.months) for s in seasons] == [3, 3, 3, 3]


def test_default_calendar_first_month_is_in_first_season():
    first = default_calendar().seasons[0]
    assert 1 in first.months
    assert GameClock().season() == first.name


def test_default_calendar_season_changes_after_three_months():
    # зима = Морозень, Темнозим, Заревень (месяцы 11, 12, 1); со 2-го месяца -- следующий сезон
    seasons = default_calendar().seasons
    clock = GameClock.from_date("0001-01-30")
    assert clock.season() == seasons[0].name
    clock.advance(DAY)
    assert clock.to_date() == "0001-02-01"
    assert clock.season() == seasons[1].name
    assert 2 in seasons[1].months


def test_calendar_without_seasons_and_holidays_still_builds():
    calendar = Calendar(months=[Month(name="Один", days=30)])
    assert calendar.days_in_year == 30


def test_month_in_two_seasons_is_error():
    months = [Month(name="А", days=30), Month(name="Б", days=30)]
    seasons = [Season(name="x", months=[1, 2]), Season(name="y", months=[2])]
    with pytest.raises(ValidationError):
        Calendar(months=months, seasons=seasons)


def test_month_without_season_is_error():
    months = [Month(name="А", days=30), Month(name="Б", days=30)]
    with pytest.raises(ValidationError):
        Calendar(months=months, seasons=[Season(name="x", months=[1])])


def test_season_with_unknown_month_is_error():
    months = [Month(name="А", days=30), Month(name="Б", days=30)]
    with pytest.raises(ValidationError):
        Calendar(months=months, seasons=[Season(name="x", months=[1, 2, 3])])


# праздники

def test_holiday_on_existing_day():
    calendar = calendar_10x36(holidays=[Holiday(month=3, day=36, name="Конец тепла")])
    assert GameClock.from_date("0001-03-36", calendar).holiday().name == "Конец тепла"


def test_no_holiday_on_ordinary_day():
    calendar = calendar_10x36(holidays=[Holiday(month=3, day=36, name="Конец тепла")])
    assert GameClock.from_date("0001-03-35", calendar).holiday() is None


def test_holiday_repeats_every_year():
    calendar = calendar_10x36(holidays=[Holiday(month=2, day=1, name="Свеча")])
    assert GameClock.from_date("0005-02-01", calendar).holiday().name == "Свеча"


def test_holiday_keeps_god_id():
    calendar = calendar_10x36(holidays=[Holiday(month=2, day=1, name="Свеча", god_id="selune")])
    assert GameClock.from_date("0001-02-01", calendar).holiday().god_id == "selune"


def test_holiday_on_31st_in_30_day_month_is_error():
    months = [Month(name="А", days=30), Month(name="Б", days=30)]
    seasons = [Season(name="x", months=[1, 2])]
    with pytest.raises(ValidationError):
        Calendar(
            months=months, seasons=seasons,
            holidays=[Holiday(month=1, day=31, name="Не бывает")],
        )


def test_holiday_in_unknown_month_is_error():
    with pytest.raises(ValidationError):
        calendar_10x36(holidays=[Holiday(month=11, day=1, name="Нет такого месяца")])


def test_holiday_day_zero_is_error():
    with pytest.raises(ValidationError):
        calendar_10x36(holidays=[Holiday(month=1, day=0, name="Нулевой")])


def test_epoch_note_is_stored():
    assert calendar_10x36(epoch_note="от Падения Звезды").epoch_note == "от Падения Звезды"
