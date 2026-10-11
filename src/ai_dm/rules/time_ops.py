from ai_dm.config.settings import RulesConfig
from ai_dm.core.clock import DAY, GameClock


def rounds_to_seconds(rounds: int, cfg: RulesConfig) -> int:
    return rounds * cfg.time.round_s


def short_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.short_rest_s


def long_rest_seconds(cfg: RulesConfig) -> int:
    return cfg.time.long_rest_s


def category_seconds(category: str, clock: GameClock, cfg: RulesConfig) -> int:
    if category == "month":
        return clock.days_in_current_month() * DAY
    if category not in cfg.time.advance_categories:
        raise ValueError(f"неизвестная категория времени: {category!r}")
    return cfg.time.advance_categories[category]


def travel_seconds(distance_m: int, pace: str, cfg: RulesConfig) -> int:
    if pace not in cfg.time.travel_pace:
        raise ValueError(f"неизвестный темп: {pace!r}")
    if distance_m < 0:
        raise ValueError("дистанция не может быть отрицательной")
    return -(-(distance_m * 3600) // cfg.time.travel_pace[pace])


def advance_by_category(clock: GameClock, category: str, cfg: RulesConfig) -> int:
    seconds = category_seconds(category, clock, cfg)
    clock.advance(seconds)
    return seconds


def ensure_min_advance(clock: GameClock, scene_start_s: int, cfg: RulesConfig) -> int:
    if clock.now_s != scene_start_s:
        return 0
    clock.advance(cfg.time.min_advance_s)
    return cfg.time.min_advance_s
