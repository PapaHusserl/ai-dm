import re

from pydantic import BaseModel, ConfigDict, Field, model_validator

DAY = 86400
DATE_RE = re.compile(r"([0-9]{4})-([0-9]{2})-([0-9]{2})")

MONTH_NAMES = [
    "Заревень", "Капельник", "Ветролом", "Цветень", "Грозовик", "Золотень",
    "Жарынь", "Сенокос", "Дожинник", "Листопад", "Морозень", "Темнозим",
]


class Month(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    days: int = Field(ge=1)


class Holiday(BaseModel):
    model_config = ConfigDict(extra="forbid")
    month: int
    day: int
    name: str
    god_id: str | None = None


class Season(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str
    # номера месяцев (с 1)
    months: list[int]


# для календаря 12 месяцев: зима = Морозень, Темнозим, Заревень
DEFAULT_SEASONS = [
    Season(name="зима", months=[11, 12, 1]),
    Season(name="весна", months=[2, 3, 4]),
    Season(name="лето", months=[5, 6, 7]),
    Season(name="осень", months=[8, 9, 10]),
]


class Calendar(BaseModel):
    model_config = ConfigDict(extra="forbid")
    months: list[Month] = Field(min_length=1)
    holidays: list[Holiday] = Field(default_factory=list)
    # пусто: у календаря из 12 месяцев берутся сезоны по умолчанию, у другого -- сезонов нет
    seasons: list[Season] = Field(default_factory=list)
    epoch_note: str = ""

    @model_validator(mode="after")
    def check_calendar(self):
        for holiday in self.holidays:
            if not 1 <= holiday.month <= len(self.months):
                raise ValueError(f"праздник {holiday.name!r}: нет месяца {holiday.month}")
            if not 1 <= holiday.day <= self.months[holiday.month - 1].days:
                raise ValueError(
                    f"праздник {holiday.name!r}: в месяце {holiday.month} нет дня {holiday.day}"
                )
        if not self.seasons and len(self.months) == 12:
            self.seasons = [s.model_copy(deep=True) for s in DEFAULT_SEASONS]
        if self.seasons:
            seen = []
            for season in self.seasons:
                seen += season.months
            for number in range(1, len(self.months) + 1):
                if seen.count(number) != 1:
                    raise ValueError(f"месяц {number} должен быть ровно в одном сезоне")
            if len(seen) != len(self.months):
                raise ValueError("в сезонах есть несуществующие месяцы")
        return self

    @property
    def days_in_year(self) -> int:
        return sum(m.days for m in self.months)

    @property
    def seconds_in_year(self) -> int:
        return self.days_in_year * DAY


def default_calendar() -> Calendar:
    return Calendar(months=[Month(name=name, days=30) for name in MONTH_NAMES])


class GameClock(BaseModel):
    now_s: int = 0
    calendar: Calendar = default_calendar()

    def advance(self, seconds: int) -> None:
        if seconds < 0:
            raise ValueError("время нельзя отматывать назад")
        self.now_s += seconds

    def _year_month_day(self) -> tuple[int, int, int]:
        # возвращает год (с 1), индекс месяца (с 0), день (с 1)
        days = self.now_s // DAY
        year = days // self.calendar.days_in_year
        days = days % self.calendar.days_in_year
        month = 0
        while days >= self.calendar.months[month].days:
            days -= self.calendar.months[month].days
            month += 1
        return year + 1, month, days + 1

    def to_date(self) -> str:
        year, month, day = self._year_month_day()
        return f"{year:04d}-{month + 1:02d}-{day:02d}"

    @classmethod
    def from_date(cls, text: str, calendar: Calendar | None = None) -> "GameClock":
        if calendar is None:
            calendar = default_calendar()
        m = DATE_RE.fullmatch(text)
        if m is None:
            raise ValueError(f"неверная дата: {text!r}")
        year, month, day = int(m.group(1)), int(m.group(2)), int(m.group(3))
        if year < 1 or month < 1 or month > len(calendar.months):
            raise ValueError(f"несуществующая дата: {text!r}")
        if day < 1 or day > calendar.months[month - 1].days:
            raise ValueError(f"несуществующая дата: {text!r}")
        days = (year - 1) * calendar.days_in_year
        days += sum(mo.days for mo in calendar.months[:month - 1])
        days += day - 1
        return cls(now_s=days * DAY, calendar=calendar)

    def days_in_current_month(self) -> int:
        _, month, _ = self._year_month_day()
        return self.calendar.months[month].days

    def season(self) -> str:
        # имя сезона текущего месяца; "" если сезонов нет
        _, month, _ = self._year_month_day()
        for season in self.calendar.seasons:
            if month + 1 in season.months:
                return season.name
        return ""

    def holiday(self) -> Holiday | None:
        _, month, day = self._year_month_day()
        for holiday in self.calendar.holidays:
            if holiday.month == month + 1 and holiday.day == day:
                return holiday
        return None
