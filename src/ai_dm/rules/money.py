class NotEnoughMoney(ValueError):
    pass


def split_cp(cp: int) -> tuple[int, int, int]:
    if cp < 0:
        raise ValueError("сумма не может быть отрицательной")
    return cp // 100, cp % 100 // 10, cp % 10


def format_cp(cp: int) -> str:
    gp, sp, rest = split_cp(cp)
    parts = []
    if gp:
        parts.append(f"{gp} зм")
    if sp:
        parts.append(f"{sp} см")
    if rest:
        parts.append(f"{rest} мм")
    if not parts:
        return "0 мм"
    return " ".join(parts)


def add_money(hero, cp: int) -> None:
    if cp < 0:
        raise ValueError("сумма не может быть отрицательной")
    hero.money_cp += cp


def spend_money(hero, cp: int) -> None:
    if cp < 0:
        raise ValueError("сумма не может быть отрицательной")
    if cp > hero.money_cp:
        raise NotEnoughMoney(f"не хватает денег: нужно {cp}, есть {hero.money_cp}")
    hero.money_cp -= cp
