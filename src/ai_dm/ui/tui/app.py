import os
import sys

from rich import box
from rich.panel import Panel as Frame
from rich.text import Text
from textual.app import App
from textual.binding import Binding
from textual.containers import Horizontal, Vertical
from textual.suggester import SuggestFromList
from textual.widgets import Footer, Input, RichLog

from ai_dm.art import art_for_event, art_for_location, pick_picture
from ai_dm.combat.available import HIDDEN_KINDS
from ai_dm.game.commands import HELP, cost_report
from ai_dm.game.lore_text import find_entity, lore_groups
from ai_dm.game.scene import hero_of
from ai_dm.ui.combat_menu import MenuState
from ai_dm.ui.format import head_lines, inert_lines
from ai_dm.ui.screen import limit_percent, picture_state, scene_mark, sound_state
from ai_dm.ui.session import offer_is_stale
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.blocks import inv_rows, map_lines, modal_lines, pickable, spell_rows
from ai_dm.ui.tui.modals import (
    CostModal,
    InvModal,
    LoreModal,
    ModelModal,
    MoreModal,
    SpellModal,
    TextModal,
)
from ai_dm.ui.tui.widgets import (
    Choices,
    CombatLog,
    CombatMenu,
    Entry,
    Panel,
    Rolls,
    StatusBar,
    hero_lines,
)

COMMAND_SUGGESTER = SuggestFromList([f"/{name}" for name in HELP], case_sensitive=True)
WIDE = 120
PANEL_WIDTH = 54
MODALS = (TextModal, ModelModal, SpellModal, InvModal, MoreModal, LoreModal)


class AiDmApp(App):
    ENABLE_COMMAND_PALETTE = False
    TITLE = strings.TITLE
    CSS_PATH = "app.tcss"
    BINDINGS = [
        Binding("f2", "toggle_side", strings.KEY_SIDE, key_display="F2"),
        Binding("ctrl+q", "quit_game", strings.KEY_QUIT, priority=True),
        Binding("ctrl+c", "quit_game", strings.KEY_QUIT, show=False, priority=True),
        Binding("tab", "next_target", show=False, priority=True),
        Binding("shift+tab", "prev_target", show=False, priority=True),
        Binding("f3", "toggle_nonlethal", strings.KEY_NONLETHAL, key_display="F3"),
        Binding("f4", "more_menu", strings.KEY_MORE, key_display="F4"),
        Binding("escape", "menu_back", show=False),
    ] + [
        Binding(str(n), f"pick({n})", show=False, priority=True) for n in range(1, 10)
    ] + [Binding("0", "pick(10)", show=False, priority=True)]

    def __init__(self, session, startup=()):
        super().__init__()
        self.session = session
        self.game = session.app
        self.startup = list(startup)
        self.shown = False
        self.exit_code = 0
        self.closing = False
        self.hard_exit = os._exit
        self.prev_menu = None
        self.quit_by_step = False
        self.busy = False
        self.quit_requested = False
        self.abandon = False
        self.status_text = ""
        self.scene_id = None
        self.feed_turns = False
        self.combat_log_shown = False
        self.picture_state = None
        self.picture_kind = None
        self.menu = MenuState()
        self.menu_args = None

    async def run_async(self, *args, **kwargs):
        result = await super().run_async(*args, **kwargs)
        if self.abandon:
            # второй Ctrl+C: терминал уже восстановлен, поток хода не прервать, а обычный выход
            # ждал бы его -- выходим сразу. hard_exit -- точка подмены для тестов.
            # os._exit может оборвать хвост журнала, который пишет поток хода
            sys.stdout.flush()
            sys.stderr.flush()
            self.hard_exit(130)
        return result

    def compose(self):
        with Horizontal(id="main"):
            with Vertical(id="left"):
                yield RichLog(wrap=True, markup=False, id="feed")
                yield Choices(id="choices")
            with Vertical(id="side"):
                yield Panel(strings.TITLE_PICTURE, id="picture")
                yield Panel(strings.TITLE_HERO, hide_empty=False, id="hero")
                yield CombatMenu(id="actions")
                yield Panel(strings.TITLE_COMBAT, id="combat")
                yield Rolls(id="rolls")
                yield CombatLog(id="combat-log")
                yield Panel(strings.TITLE_GAINS, id="gains")
        yield Entry(placeholder=strings.PLACEHOLDER, suggester=COMMAND_SUGGESTER, id="input")
        yield StatusBar(id="status")
        yield Footer()

    def on_mount(self):
        self.shown = True
        self.scene_id = scene_mark(self.game)[0]
        self.apply_width(self.size.width)
        title = art_for_event("title")
        if title is not None:
            # заставка: в ленту (до строк старта); в узкий #picture она не влезает
            self.write_feed(title.split("\n"))
        for line in self.startup:
            self.write_feed([line])
        self.show_step(self.session.start(), refresh=True)
        line = self.session.take_opening()
        if line is not None:
            self.start_turn(line)
        else:
            self.query_one("#input", Input).focus()

    def on_resize(self, event):
        self.apply_width(event.size.width)

    def apply_width(self, width):
        if self.has_class("wide") != (width >= WIDE):
            # смена режима сбрасывает ручное F2
            self.query_one("#side").remove_class("open", "closed")
        self.set_class(width >= WIDE, "wide")

    def action_toggle_side(self):
        side = self.query_one("#side")
        side.toggle_class("closed" if self.has_class("wide") else "open")

    def close(self, return_code=None):
        # публичный признак выхода для тестов: closing выставляется до App.exit
        self.closing = True
        self.exit(return_code=return_code)

    def action_quit_game(self):
        if not self.busy:
            self.close()
        elif self.quit_requested:
            # второй Ctrl+C: выход без сохранения; процесс завершает run_app (hard_exit)
            self.abandon = True
            self.close(130)
        else:
            self.quit_requested = True
            self.query_one("#status", StatusBar).set_note(strings.QUIT_WAITING)

    def menu_ready(self):
        return self.menu.active and not self.busy and not isinstance(self.screen, MODALS)

    def can_pick(self, number):
        choices = self.query_one("#choices", Choices)
        if self.busy or isinstance(self.screen, MODALS) or self.query_one("#input", Input).value:
            return False
        if self.menu.active and not choices.display:
            return number <= len(self.menu.view().rows)
        return choices.display and number <= len(pickable(self.game, self.session, choices))

    def check_action(self, action, parameters):
        # цифра выбирает вариант, только пока есть меню (под лентой или в бою) и поле ввода пустое
        if action == "pick":
            return self.can_pick(parameters[0])
        if action in ("next_target", "prev_target"):
            return self.menu_ready() and not self.query_one("#input", Input).value
        if action in ("toggle_nonlethal", "more_menu"):
            return self.menu_ready()
        if action == "menu_back":
            return self.menu_ready() and self.menu.expanded is not None
        return True

    def action_pick(self, number):
        if self.menu.active and not self.query_one("#choices", Choices).display:
            self.activate_row(self.menu.row(number))
        else:
            self.pick_choice(number)

    def action_next_target(self):
        self.menu.shift(1)
        self.show_menu()

    def action_prev_target(self):
        self.menu.shift(-1)
        self.show_menu()

    def action_toggle_nonlethal(self):
        self.menu.nonlethal = not self.menu.nonlethal
        self.show_menu()

    def action_more_menu(self):
        shown = [o for o in self.menu.options if o.kind not in HIDDEN_KINDS]
        self.push_screen(MoreModal(strings.MORE_TITLE, shown), self.more_chosen)

    def action_menu_back(self):
        self.menu.expanded = None
        self.show_menu()

    def more_chosen(self, option_id):
        self.query_one("#input", Input).focus()
        if option_id is not None:
            self.choose_option(option_id)

    def on_combat_menu_picked(self, event):
        if self.menu_ready():
            self.activate_row(self.menu.row(event.number))

    def on_combat_menu_target_picked(self, event):
        if self.menu_ready():
            self.menu.set_target(event.ref)
            self.show_menu()

    def activate_row(self, row):
        if row.kind == "option":
            self.choose_option(row.option_id)
        elif row.kind == "more":
            self.action_more_menu()
        else:
            # раскрыть группу или вернуться (у «назад» группы нет)
            self.menu.expanded = row.group
            self.show_menu()

    def choose_option(self, option_id):
        found = self.menu.find(option_id)
        if found is None:
            self.write_feed([strings.MENU_GONE])
            return
        self.write_echo(found[1].label)
        self.start_turn(str(found[0]))

    def show_menu(self):
        turn, concentration, ac, effects, inert = self.menu_args
        head = head_lines(turn, PANEL_WIDTH, concentration, ac, effects)
        foot = inert_lines(inert, PANEL_WIDTH)
        menu = self.query_one("#actions", CombatMenu)
        menu.show(self.menu.view(), head, self.menu.nonlethal, foot)

    def on_choices_picked(self, event):
        if not self.busy:
            self.pick_choice(event.number)

    def pick_choice(self, number):
        label = self.query_one("#choices", Choices).items[number - 1]
        self.write_echo(f"{number}. {label}")
        self.start_turn(str(number))

    def write_feed(self, lines):
        feed = self.query_one("#feed", RichLog)
        for line in lines:
            feed.write(Text(line))

    def write_echo(self, line):
        # реплика игрока: цветом темы; между ходами орнамент
        feed = self.query_one("#feed", RichLog)
        if self.feed_turns:
            feed.write(Text(strings.ORNAMENT, style="dim", justify="center"))
        self.feed_turns = True
        accent = self.current_theme.accent
        feed.write(Text(strings.ECHO.format(line=line), style=f"bold {accent}"))

    def write_narration(self, text):
        # рассказ мастера в рамке; рамка мягкая, чтобы не сливалась с рамкой ленты
        self.feed_turns = True
        feed = self.query_one("#feed", RichLog)
        feed.write(Frame(Text(text), box=box.ROUNDED, border_style="dim", padding=(0, 1)))

    def show_step(self, step, refresh):
        # refresh: ход обычной строки (не команды): меню и «Бой» обновляются
        # состояние уже после хода: линия сцены -- до рассказа хода, на котором сцена сменилась
        self.show_scene_line()
        self.show_blocks(step.blocks, refresh)
        self.show_picture(step.events, refresh)
        self.game.audio.update(sound_state(self.game))
        self.query_one("#hero", Panel).show(hero_lines(self.game))
        percent = limit_percent(self.game)
        self.query_one("#status", StatusBar).set_status(self.status_text, percent)
        if step.quit:
            self.quit_by_step = True
            self.exit_code = step.exit_code
            self.close(step.exit_code)

    def show_picture(self, events, refresh):
        # рисунок локации и события -- в #picture, висит до следующего; рисунок монстра -- крупный,
        # в ленту, один раз на бой (#picture в бою скрыт, после боя возвращается локация)
        state = picture_state(self.game)
        picture = pick_picture(self.picture_state, state, events)
        panel = self.query_one("#picture", Panel)
        if picture is not None and picture.kind == "monster":
            self.write_feed(picture.text.split("\n"))
            panel.show([])
            self.picture_kind = "monster"
        elif picture is not None:
            panel.show(picture.text.split("\n"))
            self.picture_kind = picture.kind
        elif refresh and self.picture_kind in ("monster", "event"):
            if state.combat_id is not None:
                panel.show([])
            else:
                self.restore_location_picture(state, panel)
        self.picture_state = state

    def restore_location_picture(self, state, panel):
        text = art_for_location(state.location)
        panel.show([] if text is None else text.split("\n"))
        self.picture_kind = None if text is None else "location"

    def show_scene_line(self):
        # новая сцена -- разделитель с названием до рассказа хода; первую сцену не отмечаем
        scene_id, title = scene_mark(self.game)
        if scene_id != self.scene_id:
            if self.scene_id is not None:
                self.write_feed(["", strings.SCENE_LINE.format(title=title)])
            self.scene_id = scene_id

    def show_blocks(self, blocks, refresh):
        kinds = [block.kind for block in blocks]
        choices = self.query_one("#choices", Choices)
        combat = self.query_one("#combat", Panel)
        gains = self.query_one("#gains", Panel)
        if refresh and "menu" not in kinds:
            choices.clear()
            if self.prev_menu and (self.session.limit_menu or self.game.pending is not None):
                # выбор не принят (нет такого варианта и т.п.): меню остаётся
                choices.show(*self.prev_menu)
        if refresh and "combat_map" not in kinds and "turn_menu" not in kinds:
            combat.show([])
            self.menu.active = False
            self.query_one("#actions", CombatMenu).display = False
        if refresh:
            # «Получено» и «Броски» -- только последнего хода
            gains.show([])
            self.query_one("#rolls", Rolls).clear()
        self.show_combat_log(blocks, refresh)
        combat_lines = []
        for block in blocks:
            self.show_block(block, choices, gains, combat_lines)
        if combat_lines:
            combat.show(combat_lines)

    def show_combat_log(self, blocks, refresh):
        # «Ход боя» занимает место «Бросков», пока бой идёт и сразу после него (до следующего хода)
        log = self.query_one("#combat-log", CombatLog)
        if any(block.combat or block.kind == "turn_menu" for block in blocks):
            self.combat_log_shown = True
        elif refresh and self.game.bundle.session.active_combat is None:
            self.combat_log_shown = False
            log.clear()
        log.display = self.combat_log_shown
        self.query_one("#rolls", Rolls).display = not self.combat_log_shown

    def show_block(self, block, choices, gains, combat_lines):
        kind = block.kind
        if kind == "narration":
            self.write_narration(block.text)
        elif kind in ("roll", "note") and block.combat:
            self.query_one("#combat-log", CombatLog).write(Text(block.text))
        elif kind == "roll":
            self.query_one("#rolls", Rolls).write(Text(block.text))
            self.write_feed([block.text])
        elif kind == "combat_hint":
            self.write_feed([strings.COMBAT_HINT_TUI])
        elif kind in ("note", "boundary", "hint"):
            self.write_feed([block.text])
        elif kind == "raw":
            self.write_feed(list(block.items))
        elif kind == "menu":
            if not self.stale_offer():
                choices.show(block.title, block.items)
        elif kind == "combat_map":
            # карта перерисовывается под ширину панели, а не берётся готовой на 80 колонок
            combat_lines.extend(map_lines(self.game, PANEL_WIDTH))
        elif kind == "turn_menu":
            # действия -- отдельным виджетом без прокрутки, чтобы были видны всегда
            *self.menu_args, roster = block.args
            combat = self.game.bundle.session.active_combat
            self.menu.load(combat and combat.id, block.items, roster)
            self.show_menu()
        elif kind == "status":
            self.status_text = block.text
        elif kind == "gains":
            gains.show(([block.text] if block.text else []) + list(block.items))

    def on_input_submitted(self, event):
        event.input.value = ""
        if not event.value.strip():
            return
        text = event.value.strip()
        if self.menu.active and text.isdigit() and not self.query_one("#choices", Choices).display:
            # цифра+Enter в бою -- номер видимой строки меню; чужой номер в ход не уходит
            row = self.menu.row(int(text) or 10)
            if row is None:
                self.write_feed([strings.NO_ROW])
            else:
                self.activate_row(row)
            return
        self.write_echo(event.value)
        self.start_turn(event.value)

    def stale_offer(self):
        # только на экране TUI: во время меню лимита варианты не прячем
        return not self.session.limit_menu and offer_is_stale(self.game)

    def is_game_line(self, line):
        # ход обычной строки (и /load), а не справочная команда
        words = line.split()
        command = words[0] if words else ""
        if command == "/inv" and len(words) > 1 and self.game.bundle.session.active_combat:
            # смена оружия/щита в бою -- шаг хода
            return True
        return not command.startswith("/") or command == "/load"

    def start_turn(self, line):
        if self.is_game_line(line):
            # варианты пропадают с началом хода; новые покажет ответ
            choices = self.query_one("#choices", Choices)
            self.prev_menu = choices.shown()
            choices.clear()
        self.busy = True
        self.query_one("#input", Input).disabled = True
        self.query_one("#status", StatusBar).set_busy(True)
        self.run_worker(lambda: self.turn(line), thread=True, exclusive=True)

    def turn(self, line):
        step = self.session.submit(line)
        if not self.abandon:
            self.call_from_thread(self.finish_turn, step, line)

    def finish_turn(self, step, line):
        self.busy = False
        words = line.split()
        command = words[0] if words else ""
        title = strings.MODAL_TITLES.get(command)
        if command in ("/model", "/inv") and len(words) > 1:
            # смена модели и действие с предметом -- строками в ленту, окно только без аргументов
            title = None
        modal_text = []
        if title is not None:
            # справочные команды: ответ -- окном, остальное (строка состояния) -- как обычно
            modal_text = modal_lines(step.blocks)
            step.blocks = [b for b in step.blocks if b.kind not in ("note", "raw")]
        # отказ `/inv …` в бою ходом не стал (в ответе нет меню хода): боевое меню остаётся
        refused = command == "/inv" and not any(b.kind == "turn_menu" for b in step.blocks)
        self.show_step(step, self.is_game_line(line) and not refused)
        self.query_one("#status", StatusBar).set_busy(False)
        entry = self.query_one("#input", Input)
        entry.disabled = False
        entry.focus()
        lore = self.lore_modal(title, words) if modal_text and command == "/lore" else None
        # отчёт /cost считаем повторно сознательно: так не трогаем Reply
        if modal_text and command == "/cost":
            self.push_screen(CostModal(title, cost_report(self.game)), lambda _: entry.focus())
        elif modal_text and command == "/spells" and self.can_cast_by_menu():
            self.push_screen(SpellModal(title, spell_rows(self.game)), self.spell_chosen)
        elif modal_text and command == "/inv" and self.can_pick_item():
            self.push_screen(InvModal(title, inv_rows(self.game)), self.inv_chosen)
        elif modal_text and command == "/model":
            # выбор модели рассказчика: окно со списком; ответ -- ключ или None (Esc)
            info = self.game.adapter.info()
            current = f"{info.provider}:{info.model}"
            modal = ModelModal(title, self.game.model_options(), current)
            self.push_screen(modal, self.model_chosen)
        elif lore is not None:
            self.push_screen(lore, lambda _: entry.focus())
        elif modal_text:
            self.push_screen(TextModal(title, modal_text), lambda _: entry.focus())
        # если шаг сам quit (меню «сохранить и выйти», смерть героя), выход уже пошёл по show_step
        # со своим кодом и без лишнего автосейва -- так задумано
        if self.quit_requested and not step.quit:
            self.close()

    def lore_modal(self, title, words):
        # окно журнала знаний; None при пустом журнале -- тогда ответ идёт обычным окном
        groups = lore_groups(hero_of(self.game.bundle), self.game.bundle.world, self.game.registry)
        if not groups:
            return None
        hit = find_entity(groups, " ".join(words[1:])) if len(words) > 1 else None
        selected = None if hit is None else hit[:2]
        return LoreModal(title, groups, self.game.bundle.world, selected)

    def can_cast_by_menu(self):
        # окно выбора -- только когда ход можно начать; у героя без заклинаний остаётся справка
        if self.game.pending is not None or self.session.limit_menu:
            return False
        return bool(spell_rows(self.game))

    def spell_chosen(self, row):
        if row is None:
            self.query_one("#input", Input).focus()
            return
        self.write_echo(row[4])
        self.start_turn(row[3])

    def can_pick_item(self):
        # окно действий -- только когда ход можно начать; пустой инвентарь остаётся справкой
        if self.game.pending is not None or self.session.limit_menu:
            return False
        return bool(inv_rows(self.game))

    def inv_chosen(self, action):
        if action is None:
            self.query_one("#input", Input).focus()
            return
        self.write_echo(action[3])
        self.start_turn(action[2])

    def model_chosen(self, key):
        if key is None:
            self.query_one("#input", Input).focus()
            return
        self.busy = True
        self.query_one("#input", Input).disabled = True
        self.query_one("#status", StatusBar).set_busy(True)
        self.run_worker(lambda: self.switch_model(key), thread=True, exclusive=True)

    def switch_model(self, key):
        error = self.game.set_narrator(key)
        if not self.abandon:
            self.call_from_thread(self.finish_switch, key, error)

    def finish_switch(self, key, error):
        # как /model narrator <ключ>: результат или ошибка -- строкой в ленту
        self.busy = False
        self.write_feed([error if error is not None else strings.MODEL_CHANGED.format(key=key)])
        self.query_one("#status", StatusBar).set_busy(False)
        entry = self.query_one("#input", Input)
        entry.disabled = False
        entry.focus()
        if self.quit_requested:
            self.close()

    def after_exit(self):
        # выход не по /quit: автосейв, как при конце ввода в простом режиме
        if self.abandon:
            return 130
        if self.quit_by_step:
            return self.exit_code
        return self.session.finish().exit_code
