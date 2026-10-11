import textwrap

WIDTH = 80
ROLL_MARK = "⚄ "


def wrap_block(text, width, first, rest):
    # перенос по словам; слово длиннее строки режется, чтобы не вылезать за ширину
    lines = []
    for part in text.split("\n"):
        rows = textwrap.wrap(part, width, initial_indent=first, subsequent_indent=rest)
        lines += rows or [first.rstrip()]
        first = rest
    return lines


def note_lines(text, width=WIDTH):
    return wrap_block(text, width, "  ", "  ")


def roll_lines(text, width=WIDTH):
    return wrap_block(text, width, "  " + ROLL_MARK, "    ")


def frame_lines(text, width=WIDTH):
    inner = width - 4
    lines = ["╭" + "─" * (width - 2) + "╮"]
    for part in text.split("\n"):
        for row in textwrap.wrap(part, inner) or [""]:
            lines.append("│ " + row.ljust(inner) + " │")
    lines.append("╰" + "─" * (width - 2) + "╯")
    return lines


def menu_lines(title, labels, width=WIDTH):
    lines = [f"  {title}"]
    for number, label in enumerate(labels, start=1):
        prefix = f"    {number}. "
        lines += wrap_block(label, width, prefix, " " * len(prefix))
    return lines


COST_TITLES = {
    "action": "Действие",
    "bonus": "Бонусное действие",
    "move": "Перемещение",
    "reaction": "Реакция",
    "free": "Без затрат",
}
COMBAT_HINT = (
    "Можно словами: «стреляю в гоблина и отхожу на уступ» — ход соберётся из нескольких "
    "шагов. Номер — один шаг; после него меню покажет, что осталось."
)


def mark(has):
    return "✓" if has else "—"


def resources_line(turn, ac=""):
    action = mark(turn.action)
    if not turn.action and turn.attacks_left > 0:
        action = f"ещё атака ×{turn.attacks_left}"
    return (
        f"Твой ход — действие {action} · бонусное {mark(turn.bonus)} · "
        f"перемещение {mark(turn.move > 0)} · реакция {mark(turn.reaction)}"
        + (f" · {ac}" if ac else "")
    )


INERT_NOTE = "пока недоступно в бою"


def inert_lines(inert, width=WIDTH):
    # без номера: в выборе не участвует
    lines = []
    for name in inert:
        lines += wrap_block(f"{name} — {INERT_NOTE}", width, "    ", "      ")
    return lines


def head_lines(turn, width=WIDTH, concentration="", ac="", effects=""):
    # шапка меню хода: ресурсы, эффекты, концентрация
    lines = wrap_block(resources_line(turn, ac), width, "  ", "    ")
    if effects:
        lines += wrap_block(effects, width, "  ", "    ")
    if concentration:
        lines += wrap_block(concentration, width, "  ", "    ")
    return lines


def turn_menu_lines(options, turn, width=WIDTH, concentration="", ac="", effects="", inert=()):
    # меню хода по ресурсам; нумерация сквозная в порядке options (он уже сгруппирован)
    lines = head_lines(turn, width, concentration, ac, effects)
    last = None
    for number, option in enumerate(options, start=1):
        if option.cost != last:
            last = option.cost
            lines.append(f"  {COST_TITLES[option.cost]}:")
        prefix = f"    {number}. "
        lines += wrap_block(option.label, width, prefix, " " * len(prefix))
    return lines + inert_lines(inert, width)


def status_lines(text, width=WIDTH):
    head = f"── {text} "
    return [head + "─" * max(2, width - len(head))]
