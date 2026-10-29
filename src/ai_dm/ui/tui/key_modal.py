from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Vertical, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Input, OptionList, Static

from ai_dm.ui.tui import strings


class KeyModal(ModalScreen):
    # ввод ключа API: провайдер (и «заменить?») цифрой, щелчком или Enter, ключ -- в скрытом поле;
    # шаги KeySession идут в потоке (проверка ключа ходит в сеть); результат -- сессия
    # (saved -- ключ записан), Esc до конца -- сессия без saved
    BINDINGS = [Binding("escape", "close", strings.KEY_CLOSE, show=False)] + [
        Binding(str(number), f"pick({number})", show=False) for number in range(1, 10)
    ]

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.lines = []
        self.items = []
        self.busy = False
        self.done = False

    def compose(self):
        with Vertical(id="modal"):
            with VerticalScroll(id="modal-body"):
                yield Static(id="key-text")
            yield OptionList(id="key-menu")
            yield Input(password=True, placeholder=strings.KEY_PLACEHOLDER, id="key-input")
            yield Button(strings.CLOSE, id="modal-close")

    def on_mount(self):
        self.query_one("#modal").border_title = strings.KEY_TITLE
        self.query_one("#modal-close").display = False
        self.show_step(self.session.start())

    def show_step(self, step):
        menu = self.query_one("#key-menu", OptionList)
        entry = self.query_one("#key-input", Input)
        for block in step.blocks:
            if block.kind == "menu":
                self.lines.append(block.title)
                self.items = list(block.items)
                menu.clear_options()
                for number, label in enumerate(self.items, 1):
                    menu.add_option(Text(f"{number}. {label}"))
                menu.highlighted = 0
            else:
                self.lines.append(block.text)
        self.query_one("#key-text", Static).update(Text("\n".join(self.lines)))
        asking = self.session.state == "key" and not step.quit
        menu.display = not asking and not step.quit
        entry.display = asking
        if step.quit:
            self.finish()
        elif asking:
            entry.focus()
        else:
            menu.focus()

    def finish(self):
        # без записи окно закрывается сразу; с записью остаётся итоговая строка до «Закрыть»
        if not self.session.saved:
            self.dismiss(self.session)
            return
        self.done = True
        self.query_one("#key-menu").display = False
        self.query_one("#key-input").display = False
        button = self.query_one("#modal-close", Button)
        button.display = True
        button.focus()

    def check_action(self, action, parameters):
        # цифровые биндинги окна выключаются через menu.display: пока меню скрыто (поле ключа,
        # итог), цифры не выбирают пункт, а идут в Input; занятое окно цифр тоже не принимает
        if action == "pick":
            menu = self.query_one("#key-menu", OptionList)
            return menu.display and not self.busy and parameters[0] <= len(self.items)
        return True

    def action_pick(self, number):
        self.lines.append(strings.ECHO.format(line=f"{number}. {self.items[number - 1]}"))
        self.start_step(str(number))

    def on_option_list_option_selected(self, event):
        if not self.busy:
            self.action_pick(event.option_index + 1)

    def on_input_submitted(self, event):
        # ключ не должен всплыть в AiDmApp.on_input_submitted и уйти в игру ходом
        event.stop()
        value = event.value
        event.input.value = ""
        if not self.busy and value.strip():
            self.lines.append(strings.ECHO.format(line=strings.KEY_MASK))
            self.start_step(value)

    def start_step(self, line):
        self.busy = True
        self.query_one("#key-menu", OptionList).disabled = True
        self.query_one("#key-input", Input).disabled = True
        self.run_worker(lambda: self.run_step(line), thread=True, exclusive=True)

    def run_step(self, line):
        step = self.session.submit(line)
        self.app.call_from_thread(self.finish_step, step)

    def finish_step(self, step):
        self.busy = False
        self.query_one("#key-menu", OptionList).disabled = False
        self.query_one("#key-input", Input).disabled = False
        self.show_step(step)

    def on_button_pressed(self):
        self.dismiss(self.session)

    def action_close(self):
        # пока идёт проверка ключа, окно не закрывается: запись ключа не должна потеряться
        if not self.busy:
            self.dismiss(self.session)


class KeyApp(App):
    # окно ключа до игры (старт без ключа): результат -- сессия (saved -- ключ записан)
    ENABLE_COMMAND_PALETTE = False
    TITLE = strings.TITLE
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("ctrl+c", "cancel", strings.KEY_QUIT, show=False, priority=True),
        Binding("ctrl+q", "cancel", strings.KEY_QUIT, show=False, priority=True),
    ]

    def __init__(self, session):
        super().__init__()
        self.session = session
        self.shown = False

    def on_mount(self):
        self.shown = True
        self.push_screen(KeyModal(self.session), self.exit)

    def action_cancel(self):
        self.exit(self.session)
