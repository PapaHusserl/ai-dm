from ai_dm.rules.encounter import DIFFICULTY_TIERS, TIER_WORDS, tier_of
from ai_dm.state.memory import add_entry

DIFFICULTIES = ("easy", "normal", "hard")
WORDS = {"easy": "лёгкая", "normal": "обычная", "hard": "тяжёлая"}


def current(world, cfg) -> str:
    tier = tier_of(world, cfg)
    return next(value for value, name in DIFFICULTY_TIERS.items() if name == tier)


def show_line(world, cfg) -> str:
    value = current(world, cfg)
    budget = TIER_WORDS[DIFFICULTY_TIERS[value]]
    note = f"бюджет боя {budget}"
    if world.settings.get("difficulty") not in DIFFICULTIES:
        note = f"по умолчанию, {note}"
    return f"Сложность: {WORDS[value]} ({note})"


def parse(arg):
    # (значение, ошибка): ошибка -- строка игроку
    value = arg.strip()
    if value not in DIFFICULTIES:
        return None, f"Неизвестная сложность {value!r}. Сложности: {', '.join(DIFFICULTIES)}."
    return value, None


def apply(bundle, value) -> str:
    # пишет настройку мира и хронику; возвращает строку для игрока
    bundle.world.settings["difficulty"] = value
    text = f"Сложность: {WORDS[value]}"
    add_entry(bundle, "event", text)
    return text
