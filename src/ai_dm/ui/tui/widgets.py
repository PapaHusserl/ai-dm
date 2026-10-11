from rich.text import Text
from textual.actions import SkipAction
from textual.binding import Binding
from textual.containers import Vertical
from textual.message import Message
from textual.widgets import Input, RichLog, Static

from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import slots_lines, title_line
from ai_dm.rules.derived import ac_summary
from ai_dm.rules.inventory import effects_line
from ai_dm.ui.combat_menu import clip
from ai_dm.ui.tui import strings

BAR_WIDTH = 54
CHIP_NAME = 12
LINE_WIDTH = 51


def hero_lines(game):
    # лист героя для правой панели; читать только когда ход не идёт
    hero = hero_of(game.bundle)
    registry = game.registry
    now_s = game.bundle.world.clock.now_s
    lines = [
        title_line(hero, registry),
        f"HP {hero.creature.hp_current}/{hero.creature.hp_max}",
        ac_summary(hero, registry, now_s),
    ]
    effects = effects_line(hero, registry, now_s)
    if effects:
        lines.append(effects)
    concentration = game.runner.concentration_line()
    if concentration:
        lines.append(concentration)
    if registry.get("class", hero.sheet.class_id).spellcasting is not None:
        lines += slots_lines(hero, registry)
    return lines


class Panel(Static):
    # блок с текстом; без текста скрыт (hide_empty)
    def __init__(self, title, hide_empty=True, **kwargs):
        super().__init__(**kwargs)
        self.border_title = title
        self.hide_empty = hide_empty
        self.text = ""

    def show(self, lines):
        self.text = "\n".join(str(line) for line in lines)
        text = Text()
        for number, line in enumerate(lines):
            # строка может быть готовым Text со своим стилем (серые недоступные заклинания)
            text.append("\n" if number else "")
            text.append_text(line if isinstance(line, Text) else Text(line))
        self.update(text)
        if self.hide_empty:
            self.display = bool(self.text)


class Choice(Static):
    # один вариант; клик отправляет его номер
    def __init__(self, number, **kwargs):
        super().__init__(**kwargs)
        self.number = number
        self.display = False

    def on_click(self):
        self.post_message(Choices.Picked(self.number))


class Choices(Vertical):
    # меню под лентой: варианты, меню 2.2, лимит; выбор кликом или цифрой
    MAX_ITEMS = 24

    class Picked(Message):
        def __init__(self, number):
            super().__init__()
            self.number = number

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.title = ""
        self.items = []
        self.display = False

    def compose(self):
        yield Static(id="choices-title")
        for number in range(1, self.MAX_ITEMS + 1):
            yield Choice(number, id=f"choice-{number}")

    def show(self, title, items):
        self.title = title
        self.items = list(items)[: self.MAX_ITEMS]
        self.query_one("#choices-title", Static).update(Text(title))
        for choice in self.query(Choice):
            if choice.number <= len(self.items):
                choice.update(Text(f"{choice.number}. {self.items[choice.number - 1]}"))
            choice.display = choice.number <= len(self.items)
        self.display = True

    def shown(self):
        # (заголовок, пункты) того, что на экране, или None
        return (self.title, self.items) if self.display else None

    def clear(self):
        self.items = []
        for choice in self.query(Choice):
            choice.display = False
        self.display = False


class MenuLine(Static):
    # строка меню боя; клик отправляет её номер
    def __init__(self, number, **kwargs):
        super().__init__(**kwargs)
        self.number = number
        self.display = False

    def on_click(self):
        self.post_message(CombatMenu.Picked(self.number))


class TargetBar(Static):
    # цели боя чипами «[Гоблин 7/7]»; не влезли -- одна цель и Tab; клик по чипу выбирает цель
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.spans = []
        self.text = ""

    def show(self, chips, target):
        text = Text()
        self.spans = []
        for chip in chips:
            start = len(text)
            style = "reverse" if chip.ref == target else ""
            text.append(f"[{clip(chip.name, CHIP_NAME)} {chip.hp_text}]", style=style)
            self.spans.append((start, len(text), chip.ref))
            text.append(" ")
        if not chips:
            text = Text(strings.NO_TARGET)
        elif len(text) > BAR_WIDTH:
            text = self.one_target(chips, target)
        self.text = text.plain
        self.update(text)

    def one_target(self, chips, target):
        # клик по такой строке -- следующая цель
        refs = [chip.ref for chip in chips]
        index = refs.index(target)
        chip = chips[index]
        line = strings.TARGET_ONE.format(
            name=chip.name, hp=chip.hp_text, number=index + 1, total=len(chips)
        )
        self.spans = [(0, len(line), refs[(index + 1) % len(refs)])]
        return Text(line)

    def on_click(self, event):
        for start, end, ref in self.spans:
            if start <= event.x < end:
                self.post_message(CombatMenu.TargetPicked(ref))


class CombatMenu(Vertical):
    # меню хода в бою: шапка, цели, строки меню (выбор цифрой или кликом), недоступное серым
    MAX_LINES = 24

    class Picked(Message):
        def __init__(self, number):
            super().__init__()
            self.number = number

    class TargetPicked(Message):
        def __init__(self, ref):
            super().__init__()
            self.ref = ref

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.border_title = strings.TITLE_ACTIONS
        self.text = ""
        self.display = False

    def compose(self):
        yield Static(id="menu-head")
        yield TargetBar(id="menu-targets")
        for number in range(1, self.MAX_LINES + 1):
            yield MenuLine(number, id=f"menu-line-{number}")
        yield Static(id="menu-foot")

    def show(self, view, head, nonlethal, foot):
        head = list(head)
        if nonlethal:
            head.append("  " + strings.NONLETHAL_ON)
        if view.header:
            head.append("  " + view.header)
        self.query_one("#menu-head", Static).update(Text("\n".join(head)))
        self.query_one("#menu-head").display = bool(head)
        self.query_one("#menu-targets", TargetBar).show(view.targets, view.target)
        rows = view.rows[: self.MAX_LINES]
        texts = []
        for line in self.query(MenuLine):
            row = rows[line.number - 1] if line.number <= len(rows) else None
            if row is not None:
                prefix = f"{row.key}. " if row.key else "   "
                texts.append(prefix + clip(row.label, LINE_WIDTH))
                line.update(Text(texts[-1]))
            line.display = row is not None
        inert = "\n".join(foot)
        self.query_one("#menu-foot", Static).update(Text(inert, style="dim"))
        self.query_one("#menu-foot").display = bool(foot)
        bar = self.query_one("#menu-targets", TargetBar).text
        self.text = "\n".join(head + [bar] + texts + list(foot))
        self.display = True


class Entry(Input):
    BINDINGS = [Binding("tab", "complete", show=False)]

    def action_complete(self):
        # Tab дополняет команду, только когда есть подсказка; иначе обычное переключение фокуса
        if not self._suggestion:
            raise SkipAction()
        self.action_cursor_right()

    # поле ввода: цифру не съедает, если ею можно выбрать вариант (её ловит привязка приложения)
    def check_consume_key(self, key, character):
        number = int(character) or 10 if character in tuple("1234567890") else 0
        if number and self.app.check_action("pick", (number,)):
            return False
        return super().check_consume_key(key, character)


class StatusBar(Static):
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.status = ""
        self.percent = None
        self.busy = False
        self.note = ""
        self.text = ""

    def set_status(self, status, percent):
        self.status = status
        self.percent = percent
        self.redraw()

    def set_busy(self, busy):
        self.busy = busy
        self.redraw()

    def set_note(self, note):
        self.note = note
        self.redraw()

    def redraw(self):
        parts = []
        if self.busy:
            parts.append(strings.THINKING)
        if self.note:
            parts.append(self.note)
        if self.status:
            parts.append(self.status)
        if self.percent is not None:
            parts.append(strings.LIMIT.format(percent=self.percent))
        self.text = " · ".join(parts)
        self.update(Text(self.text))


class CombatLog(RichLog):
    # лог боя: атаки, урон, эффекты; прокрутка, автоскролл вниз
    def __init__(self, **kwargs):
        super().__init__(wrap=True, markup=False, auto_scroll=True, **kwargs)
        self.border_title = strings.TITLE_COMBAT_LOG
        self.display = False


class Rolls(RichLog):
    def __init__(self, **kwargs):
        super().__init__(wrap=True, markup=False, **kwargs)
        self.border_title = strings.TITLE_ROLLS
