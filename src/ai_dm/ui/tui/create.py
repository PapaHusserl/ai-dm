from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.widgets import Footer, Input, RichLog

from ai_dm.art import art_for_event
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.widgets import Choices, Entry, StatusBar


class HeroCreateApp(App):
    # создание героя на лету до игры: описание, лист, замечание или правка; результат --
    # HeroSheet или None (отмена); ходы сессии идут в потоке, как в AiDmApp
    ENABLE_COMMAND_PALETTE = False
    TITLE = strings.TITLE
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("escape", "cancel", strings.KEY_QUIT, show=False),
        Binding("ctrl+c", "cancel", strings.KEY_QUIT, show=False, priority=True),
        Binding("ctrl+q", "cancel", strings.KEY_QUIT, show=False, priority=True),
    ] + [
        Binding(str(n), f"pick({n})", show=False, priority=True) for n in range(1, 10)
    ]

    def __init__(self, session, placeholder=strings.CREATE_PLACEHOLDER):
        super().__init__()
        self.session = session
        self.placeholder = placeholder
        self.shown = False
        self.busy = False
        self.cancel_requested = False

    def compose(self):
        yield RichLog(wrap=True, markup=False, id="feed")
        yield Choices(id="choices")
        yield Entry(placeholder=self.placeholder, id="input")
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self):
        self.shown = True
        title = art_for_event("title")
        if title is not None:
            self.write_feed(title.split("\n"))
        self.show_step(self.session.start())
        self.query_one("#input", Input).focus()

    def can_pick(self, number):
        choices = self.query_one("#choices", Choices)
        if self.busy or self.query_one("#input", Input).value:
            return False
        return choices.display and number <= len(choices.items)

    def check_action(self, action, parameters):
        if action == "pick":
            return self.can_pick(parameters[0])
        return True

    def action_pick(self, number):
        label = self.query_one("#choices", Choices).items[number - 1]
        self.write_feed([strings.ECHO.format(line=f"{number}. {label}")])
        self.start_step(str(number))

    def on_choices_picked(self, event):
        if not self.busy:
            self.action_pick(event.number)

    def on_input_submitted(self, event):
        event.input.value = ""
        if not event.value.strip():
            return
        self.write_feed([strings.ECHO.format(line=event.value)])
        self.start_step(event.value)

    def action_cancel(self):
        if self.busy:
            self.cancel_requested = True
            self.query_one("#status", StatusBar).set_note(strings.CREATE_CANCELLING)
        else:
            self.exit(result=None)

    def write_feed(self, lines):
        feed = self.query_one("#feed", RichLog)
        for line in lines:
            feed.write(Text(line))

    def start_step(self, line):
        self.query_one("#choices", Choices).clear()
        self.busy = True
        self.query_one("#input", Input).disabled = True
        self.query_one("#status", StatusBar).set_busy(True)
        self.run_worker(lambda: self.run_step(line), thread=True, exclusive=True)

    def run_step(self, line):
        step = self.session.submit(line)
        self.call_from_thread(self.finish_step, step)

    def finish_step(self, step):
        self.busy = False
        self.query_one("#status", StatusBar).set_busy(False)
        if self.cancel_requested:
            self.exit(result=None)
            return
        self.show_step(step)
        entry = self.query_one("#input", Input)
        entry.disabled = False
        entry.focus()
        if step.quit:
            self.exit(result=self.session.sheet)

    def show_step(self, step):
        choices = self.query_one("#choices", Choices)
        for block in step.blocks:
            if block.kind == "menu":
                choices.show(block.title, block.items)
            elif block.kind == "raw":
                self.write_feed(list(block.items))
            else:
                self.write_feed([block.text])
