import re

from pydantic import BaseModel, model_validator

from ai_dm.core.rng import Rng

DICE_RE = re.compile(r"([0-9]*)d([0-9]+)(?:(kh|kl)([0-9]+))?([+-][0-9]+)?")


class DiceParseError(ValueError):
    pass


class DiceExpr(BaseModel):
    count: int
    sides: int
    modifier: int = 0
    keep_highest: int | None = None
    keep_lowest: int | None = None

    @model_validator(mode="after")
    def check_keep(self):
        if self.keep_highest is not None and self.keep_lowest is not None:
            raise ValueError("нельзя одновременно keep_highest и keep_lowest")
        return self


class DiceRoll(BaseModel):
    expr: str
    rolls: list[int]
    kept: list[int]
    modifier: int
    total: int


def parse_dice(expr: str) -> DiceExpr:
    text = expr.strip()
    m = DICE_RE.fullmatch(text)
    if m is None:
        raise DiceParseError(f"не кубики: {expr!r}")
    count = int(m.group(1)) if m.group(1) else 1
    sides = int(m.group(2))
    if count < 1 or sides < 1:
        raise DiceParseError(f"count и sides должны быть >= 1: {expr!r}")
    result = DiceExpr(count=count, sides=sides)
    if m.group(3):
        keep = int(m.group(4))
        if keep < 1 or keep > count:
            raise DiceParseError(f"неверное число оставляемых костей: {expr!r}")
        if m.group(3) == "kh":
            result.keep_highest = keep
        else:
            result.keep_lowest = keep
    if m.group(5):
        result.modifier = int(m.group(5))
    return result


def format_expr(e: DiceExpr) -> str:
    text = f"{e.count}d{e.sides}"
    if e.keep_highest is not None:
        text += f"kh{e.keep_highest}"
    if e.keep_lowest is not None:
        text += f"kl{e.keep_lowest}"
    if e.modifier > 0:
        text += f"+{e.modifier}"
    elif e.modifier < 0:
        text += str(e.modifier)
    return text


def roll_dice(expr: str | DiceExpr, rng: Rng) -> DiceRoll:
    if isinstance(expr, str):
        expr = parse_dice(expr)
    rolls = [rng.d(expr.sides) for _ in range(expr.count)]
    if expr.keep_highest is not None:
        kept = sorted(rolls, reverse=True)[:expr.keep_highest]
    elif expr.keep_lowest is not None:
        kept = sorted(rolls)[:expr.keep_lowest]
    else:
        kept = list(rolls)
    return DiceRoll(
        expr=format_expr(expr),
        rolls=rolls,
        kept=kept,
        modifier=expr.modifier,
        total=sum(kept) + expr.modifier,
    )


def roll_damage_dice(dice: str, bonus: int, rng: Rng, crit: bool = False) -> DiceRoll:
    expr = parse_dice(dice)
    if crit:
        # крит удваивает число кубиков, бонус не удваивается
        expr.count *= 2
    rolled = roll_dice(expr, rng)
    rolled.modifier += bonus
    rolled.total += bonus
    return rolled

