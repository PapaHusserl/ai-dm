from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, DataTable, Input, OptionList, RichLog, Static, Tab, Tabs
from textual.widgets.option_list import Option

from ai_dm.art import art_for_event
from ai_dm.game.commands import cost_rows, money_text
from ai_dm.game.lore_text import KIND_TITLES, entry_lines
from ai_dm.ui.format import COST_TITLES
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.widgets import Choices


class TextModal(ModalScreen):
    # справочный ответ команды (/sheet /inv /spells /abilities /cost /model) окном; Esc закрывает
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)]

    def __init__(self, title, lines):
        super().__init__()
        self.title_text = title
        self.lines = list(lines)

    def compose(self):
        with Vertical(id="modal"):
            with VerticalScroll(id="modal-body"):
                yield Static(Text("\n".join(self.lines)), id="modal-text")
            yield Button(strings.CLOSE, id="modal-close")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text

    def on_button_pressed(self):
        self.dismiss()

    def action_close(self):
        self.dismiss()


class CostModal(TextModal):
    # /cost таблицей: период, роль, модель, сумма; данные -- та же cost_rows, что и в простом
    def __init__(self, title, report):
        super().__init__(title, [])
        self.report = report

    def compose(self):
        with Vertical(id="modal"):
            yield DataTable(id="modal-table")
            yield Button(strings.CLOSE, id="modal-close")

    def on_mount(self):
        super().on_mount()
        table = self.query_one("#modal-table", DataTable)
        table.add_columns(*strings.COST_COLUMNS)
        for period, role, model, cost in cost_rows(self.report):
            table.add_row(period, role, model, money_text(cost))


class ModelModal(ModalScreen):
    # выбор модели рассказчика: клик, цифра или Enter; результат -- ключ, Esc -- None
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)] + [
        Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)
    ]

    def __init__(self, title, options, current):
        super().__init__()
        self.title_text = title
        self.options = list(options)
        self.current = current

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(strings.MODEL_PICK), id="model-title")
            yield OptionList(id="model-list")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        menu = self.query_one("#model-list", OptionList)
        for number, key in enumerate(self.options, 1):
            label = strings.MODEL_CURRENT.format(key=key) if key == self.current else key
            menu.add_option(Text(f"{number}. {label}"))
        if self.current in self.options:
            menu.highlighted = self.options.index(self.current)
        menu.focus()

    def on_option_list_option_selected(self, event):
        self.dismiss(self.options[event.option_index])

    def action_pick(self, number):
        if number <= len(self.options):
            self.dismiss(self.options[number - 1])

    def action_close(self):
        self.dismiss(None)


class SpellModal(ModalScreen):
    # выбор заклинания: клик, цифра или Enter; результат -- строка rows или None
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)] + [
        Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)
    ]

    def __init__(self, title, rows):
        super().__init__()
        self.title_text = title
        self.rows = list(rows)

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(strings.SPELL_PICK), id="spell-title")
            yield OptionList(id="spell-list")
            with VerticalScroll(id="spell-body"):
                yield Static(id="spell-description")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        menu = self.query_one("#spell-list", OptionList)
        for number, row in enumerate(self.rows, 1):
            menu.add_option(Option(Text(f"{number}. {row[0]}"), disabled=not row[2]))
        menu.focus()
        enabled = [number for number, row in enumerate(self.rows) if row[2]]
        if enabled:
            menu.highlighted = enabled[0]
        if self.rows:
            self.show_description(enabled[0] if enabled else 0)

    def show_description(self, index):
        text = self.rows[index][1] or strings.SPELL_NO_DESCRIPTION
        self.query_one("#spell-description", Static).update(Text(text))

    def on_option_list_option_highlighted(self, event):
        self.show_description(event.option_index)

    def on_option_list_option_selected(self, event):
        self.dismiss(self.rows[event.option_index])

    def action_pick(self, number):
        if number <= len(self.rows) and self.rows[number - 1][2]:
            self.dismiss(self.rows[number - 1])

    def action_close(self):
        self.dismiss(None)


class InvModal(ModalScreen):
    # инвентарь: вкладки-разделы, список предметов и описание; ←/→ -- раздел,
    # Enter -- первое действие предмета, e/l/u/r/d -- своё;
    # результат -- действие (клавиша, подсказка, строка /inv, эхо) или None
    BINDINGS = [
        Binding("escape", "close", strings.KEY_CLOSE, show=False),
        Binding("left", "tab(-1)", show=False),
        Binding("right", "tab(1)", show=False),
    ] + [Binding(key, f"act('{key}')", show=False) for key in ("e", "l", "u", "r", "d")]
    PICK = strings.INV_PICK

    def __init__(self, title, tabs):
        super().__init__()
        self.title_text = title
        self.tabs = list(tabs)
        self.rows = []

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(self.PICK), id="inv-title")
            names = enumerate(name for name, _ in self.tabs)
            yield Tabs(*(Tab(name, id=f"inv-tab-{index}") for index, name in names), id="inv-tabs")
            yield OptionList(id="inv-list")
            with VerticalScroll(id="inv-body"):
                yield Static(id="inv-description")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        self.query_one("#inv-list", OptionList).focus()
        self.fill(0)

    def fill(self, index):
        # список -- строки вкладки index; подсветка и описание первой строки
        self.rows = list(self.tabs[index][1]) if self.tabs else []
        menu = self.query_one("#inv-list", OptionList)
        menu.clear_options()
        for number, row in enumerate(self.rows, 1):
            menu.add_option(Text(f"{number}. {row[0]}"))
        if self.rows:
            menu.highlighted = 0
            self.show_description(0)

    def on_tabs_tab_activated(self, event):
        self.fill(int(event.tab.id.removeprefix("inv-tab-")))

    def action_tab(self, step):
        tabs = self.query_one("#inv-tabs", Tabs)
        if step > 0:
            tabs.action_next_tab()
        else:
            tabs.action_previous_tab()

    def show_description(self, index):
        _, description, actions, _ = self.rows[index]
        hints = " · ".join(f"{key} — {hint}" for key, hint, *_ in actions)
        text = "\n\n".join(part for part in (description, hints) if part)
        self.query_one("#inv-description", Static).update(Text(text))

    def on_option_list_option_highlighted(self, event):
        self.show_description(event.option_index)

    def on_option_list_option_selected(self, event):
        actions = self.rows[event.option_index][2]
        if actions:
            self.dismiss(actions[0])

    def action_act(self, key):
        index = self.query_one("#inv-list", OptionList).highlighted
        for action in self.rows[index][2] if index is not None else ():
            if action[0] == key:
                self.dismiss(action)
                return

    def action_close(self):
        self.dismiss(None)


class ShopModal(InvModal):
    # торговля: те же вкладки и список, что у инвентаря; у строки одно действие -- Enter;
    # результат -- действие (клавиша, подсказка, команда с {qty}, эхо, потолок количества) или None
    BINDINGS = [
        Binding("escape", "close", strings.KEY_CLOSE, show=False),
        Binding("left", "tab(-1)", show=False),
        Binding("right", "tab(1)", show=False),
    ]
    PICK = strings.SHOP_PICK


class NpcModal(ModalScreen):
    # у кого торговать: клик, цифра или Enter; rows -- (id NPC, подпись); результат -- id или None
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)] + [
        Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)
    ]

    def __init__(self, title, rows):
        super().__init__()
        self.title_text = title
        self.rows = list(rows)

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(strings.SHOP_NPC_PICK), id="npc-title")
            yield OptionList(id="npc-list")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        menu = self.query_one("#npc-list", OptionList)
        for number, row in enumerate(self.rows, 1):
            menu.add_option(Text(f"{number}. {row[1]}"))
        menu.highlighted = 0
        menu.focus()

    def on_option_list_option_selected(self, event):
        self.dismiss(self.rows[event.option_index][0])

    def action_pick(self, number):
        if number <= len(self.rows):
            self.dismiss(self.rows[number - 1][0])

    def action_close(self):
        self.dismiss(None)


class QtyModal(ModalScreen):
    # сколько покупать, продавать или оплачивать: целое в 1..cap; Enter -- число, Esc -- None
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)]

    def __init__(self, title, name, cap):
        super().__init__()
        self.title_text = title
        self.label = name
        self.cap = cap

    def compose(self):
        with Vertical(id="modal"):
            text = f"{self.label}\n{strings.SHOP_QTY.format(cap=self.cap)}"
            yield Static(Text(text), id="qty-title")
            yield Input(value="1", type="integer", id="qty-input")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        self.query_one("#qty-input", Input).focus()

    def on_input_submitted(self, event):
        # событие не уходит к полю ввода хода в приложении
        event.stop()
        if event.value.isdigit() and 1 <= int(event.value) <= self.cap:
            self.dismiss(int(event.value))

    def action_close(self):
        self.dismiss(None)


class LoreModal(ModalScreen):
    # журнал знаний героя (/lore): слева сущности по видам, справа записи выбранной; ничего не
    # запускает, Esc закрывает; selected -- (вид, ref) для предвыбора
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)]

    def __init__(self, title, groups, world, selected=None):
        super().__init__()
        self.title_text = title
        self.groups = list(groups)
        self.world = world
        self.selected = selected
        # индекс строки списка -> записи сущности; у заголовков видов записей нет
        self.index_to_entries = {}

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(strings.LORE_PICK), id="lore-title")
            yield OptionList(id="lore-list")
            with VerticalScroll(id="lore-body"):
                yield Static(id="lore-text")
            yield Button(strings.CLOSE, id="modal-close")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        menu = self.query_one("#lore-list", OptionList)
        first = None
        for kind, items in self.groups:
            menu.add_option(Option(Text(f"{KIND_TITLES[kind]}:"), disabled=True))
            for ref, name, entries in items:
                if first is None or (kind, ref) == self.selected:
                    first = menu.option_count
                self.index_to_entries[menu.option_count] = entries
                menu.add_option(Text(f"  {name} ({len(entries)})"))
        menu.highlighted = first
        menu.focus()
        self.show_entries(first)

    def show_entries(self, index):
        lines = entry_lines(self.index_to_entries[index], self.world)
        self.query_one("#lore-text", Static).update(Text("\n".join(lines)))

    def on_option_list_option_highlighted(self, event):
        self.show_entries(event.option_index)

    def on_button_pressed(self):
        self.dismiss()

    def action_close(self):
        self.dismiss()


class MoreModal(ModalScreen):
    # «Ещё…»: все варианты хода, сгруппированные по затратам; результат -- id варианта, Esc -- None
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)] + [
        Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)
    ] + [Binding("0", "pick(10)", show=False)]

    def __init__(self, title, options):
        super().__init__()
        self.title_text = title
        self.options = list(options)
        # индекс строки списка -> номер варианта с 0; у заголовков групп номера нет
        self.index_to_option = {}

    def compose(self):
        with Vertical(id="modal"):
            yield Static(Text(strings.MORE_PICK), id="more-title")
            yield OptionList(id="more-list")

    def on_mount(self):
        self.query_one("#modal").border_title = self.title_text
        menu = self.query_one("#more-list", OptionList)
        cost = None
        for number, option in enumerate(self.options):
            if option.cost != cost:
                cost = option.cost
                menu.add_option(Option(Text(COST_TITLES[cost]), disabled=True))
            self.index_to_option[menu.option_count] = number
            menu.add_option(Text(f"{number + 1}. {option.label}"))
        menu.highlighted = min(self.index_to_option)
        menu.focus()

    def on_option_list_option_selected(self, event):
        self.dismiss(self.options[self.index_to_option[event.option_index]].id)

    def action_pick(self, number):
        if number <= len(self.options):
            self.dismiss(self.options[number - 1].id)

    def action_close(self):
        self.dismiss(None)


class PickerApp(App):
    # выбор пункта до старта игры (герой, пресет мира): цифра или клик; результат -- номер с 1,
    # None при отмене
    ENABLE_COMMAND_PALETTE = False
    TITLE = strings.TITLE
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("escape", "cancel", strings.KEY_QUIT, show=False),
        Binding("ctrl+c", "cancel", strings.KEY_QUIT, show=False, priority=True),
        Binding("ctrl+q", "cancel", strings.KEY_QUIT, show=False, priority=True),
    ] + [Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)]

    def __init__(self, title, names, splash=False):
        super().__init__()
        self.title_text = title
        self.names = list(names)
        self.splash = splash

    def compose(self):
        if self.splash:
            yield RichLog(wrap=False, markup=False, id="feed")
        yield Choices(id="choices")

    def on_mount(self):
        art = art_for_event("title") if self.splash else None
        if art is not None:
            for line in art.split("\n"):
                self.query_one("#feed", RichLog).write(Text(line))
        title = f"{self.title_text} {strings.PICK_HINT}"
        self.query_one("#choices", Choices).show(title, self.names)

    def on_choices_picked(self, event):
        self.action_pick(event.number)

    def action_pick(self, number):
        if 1 <= number <= len(self.names):
            self.exit(result=number)

    def action_cancel(self):
        self.exit(result=None)
