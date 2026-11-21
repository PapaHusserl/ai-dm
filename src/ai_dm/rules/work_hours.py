from ai_dm.core.clock import DAY
from ai_dm.rules.trade import refuses
from ai_dm.state.world import WorkHours


def from_pair(open_hour, close_hour):
    # два числа запроса (None -- не заданы) -> WorkHours или None; одно число или неверная пара --
    # ValueError (ValidationError модели -- его подкласс)
    if open_hour is None and close_hour is None:
        return None
    if open_hour is None or close_hour is None:
        raise ValueError("часы работы: нужны оба числа, open_hour и close_hour")
    return WorkHours(open_hour=open_hour, close_hour=close_hour)


def is_open(hours, now_s: int) -> bool:
    # часы работы [open_hour, close_hour) по часу суток; close < open -- через полночь;
    # None -- открыто всегда
    if hours is None:
        return True
    hour = now_s % DAY // 3600
    if hours.open_hour < hours.close_hour:
        return hours.open_hour <= hour < hours.close_hour
    return hour >= hours.open_hour or hour < hours.close_hour


def next_hour_s(now_s: int, hour: int) -> int:
    # ближайший впереди момент «hour:00» (ровно сейчас не считается)
    target = now_s - now_s % DAY + hour * 3600
    return target if target > now_s else target + DAY


def serves(npc, now_s: int, cfg) -> bool:
    # NPC принимает героя сейчас: не отказывает по отношению и открыт по часам
    return not refuses(npc.attitude, cfg) and is_open(npc.hours, now_s)


def closed_text(hours) -> str:
    return f"закрыто до {hours.open_hour}:00"


def hours_text(hours) -> str:
    # часы словом для мастера: «круглосуточно», «8-16» или «часы не заданы»
    if hours is None:
        return "часы не заданы"
    if (hours.open_hour, hours.close_hour) == (0, 24):
        return "круглосуточно"
    return f"{hours.open_hour}-{hours.close_hour}"
