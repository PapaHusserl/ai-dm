from typing import get_args

from ai_dm.state.memory import add_entry
from ai_dm.state.world import Tone

LIST_SCALES = ["hard_limits", "soft_limits"]
TYPED_SCALES = ["violence", "horror", "romance", "language"]
ALL_SCALES = ["mood", *TYPED_SCALES, *LIST_SCALES, "notes"]


def allowed_values(scale) -> list[str]:
    return [v for v in get_args(Tone.model_fields[scale].annotation) if v != ""]


def show_lines(tone) -> list[str]:
    lines = []
    for scale in ALL_SCALES:
        value = getattr(tone, scale)
        if isinstance(value, list):
            value = ", ".join(value)
        lines.append(f"{scale}: {value or 'не задано'}")
    return lines


def parse(tone, arg):
    # (изменение, ошибка): изменение -- (шкала, значение, ослабление); ошибка -- строка игроку
    scale, _, value = arg.partition(" ")
    value = value.strip()
    if scale not in ALL_SCALES:
        return None, f"Неизвестная шкала {scale!r}. Шкалы: {', '.join(ALL_SCALES)}."
    if not value:
        return None, f"Не указано значение для {scale}."
    if scale in TYPED_SCALES and value not in allowed_values(scale):
        return None, f"Значение {value!r} не из шкалы {scale}: {', '.join(allowed_values(scale))}."
    if scale in LIST_SCALES:
        sign, item = value[:1], value[1:].strip()
        if sign not in ("+", "-") or not item:
            return None, f"Для {scale}: +<пункт> добавить, -<пункт> убрать."
        current = getattr(tone, scale)
        if sign == "-" and item not in current:
            return None, f"Пункта {item!r} нет в {scale}."
        if sign == "+" and item in current:
            return None, f"Пункт {item!r} уже есть в {scale}."
        return (scale, value, sign == "-" and scale == "hard_limits"), None
    return (scale, value, False), None


def apply(bundle, scale, value) -> str:
    # меняет тон, пишет хронику; возвращает строку для игрока
    tone = bundle.world.tone
    if scale in LIST_SCALES:
        item = value[1:].strip()
        items = getattr(tone, scale)
        if value[0] == "+":
            items.append(item)
        else:
            items.remove(item)
        text = f"Тон: {scale} {value[0]}{item}"
    else:
        setattr(tone, scale, value)
        text = f"Тон: {scale} = {value}"
    add_entry(bundle, "tone", text)
    return text
