from contextlib import suppress
from dataclasses import dataclass, field

from ai_dm.game.app import LOADED_PREFIX
from ai_dm.game.scene import hero_of
from ai_dm.llm.keys import redact
from ai_dm.ui.screen import (
    LIMIT_MENU,
    Block,
    limit_state,
    loot_snapshot,
    menu_block,
    note_block,
    reply_blocks,
    screen_blocks,
    status_block,
)

# команды, после которых экран (карта, меню боя) перерисовывается
SCREEN_COMMANDS = ("/load", "/fight")


@dataclass
class Step:
    blocks: list = field(default_factory=list)
    quit: bool = False
    exit_code: int = 0
    # события хода для рисунков: death, victory, level_up
    events: list = field(default_factory=list)


def turn_events(app, reply, level_before):
    turn = reply.turn
    events = []
    if app.pending == "hero_dead" or (turn is not None and turn.hero_dead):
        events.append("death")
    if turn is not None and turn.combat_outcome == "victory":
        events.append("victory")
    if hero_of(app.bundle).sheet.level > level_before:
        events.append("level_up")
    return events


def offer_is_stale(app):
    # game не сбрасывает offered_choices после хода: варианты актуальны, только если последний
    # ход рассказчика сам вызвал offer_choices
    if app.pending is not None:
        return False
    recent = app.bundle.memory.recent_turns
    return not (recent and "offer_choices" in recent[-1].requests)


def last_narration_block(app):
    recent = app.bundle.memory.recent_turns
    if recent and recent[-1].narration:
        return Block("narration", text=recent[-1].narration)
    return None


class PlaySession:
    def __init__(self, app, replay=False, secrets=(), opening=None):
        self.app = app
        self.replay = replay
        self.secrets = secrets
        self.opening = opening
        self.warned = False
        self.asked = False
        self.limit_menu = False

    def start(self):
        app = self.app
        blocks = [note_block(line) for line in app.startup_lines]
        narration = last_narration_block(app)
        if self.opening is None and not self.replay and narration is not None:
            # продолжение мира: последний рассказ, чтобы выбор не висел без контекста
            blocks.append(narration)
        blocks.append(status_block(app))
        blocks.extend(screen_blocks(app))
        return Step(blocks)

    def take_opening(self):
        # вступительная сцена нового мира: первый ход без ввода игрока
        line, self.opening = self.opening, None
        return line

    def finish(self):
        # ввод кончился
        app = self.app
        step = Step(quit=True)
        if app.pending != "hero_dead" and not self.replay:
            try:
                app.save_current("auto")
                step.blocks.append(note_block("Сохранено: auto."))
            except ValueError as error:
                step.blocks.append(note_block(f"Не удалось сохранить: {error}"))
        return step

    def submit(self, line):
        if line is None:
            return self.finish()
        line = line.strip()
        if self.limit_menu:
            return self.limit_answer(line)
        return self.play(line)

    def play(self, line):
        app = self.app
        try:
            before = loot_snapshot(app)
            level_before = hero_of(app.bundle).sheet.level
            if line.isdigit() and app.pending is None and not offer_is_stale(app):
                offered = app.bundle.session.offered_choices
                in_combat = app.bundle.session.active_combat is not None
                if not in_combat and 1 <= int(line) <= len(offered):
                    line = offered[int(line) - 1]
        except Exception as error:
            return self.failure(f"Ошибка хода: {error}")
        reply, step = self.apply_line(line)
        if step is not None:
            return step
        try:
            return self.render_step(line, reply, before, level_before)
        except Exception as error:
            step = self.failure(f"Ход сделан, но экран не обновился: {error}")
            with suppress(Exception):
                step.blocks.append(status_block(app))
            return step

    def failure(self, text):
        step = Step([note_block(redact(text, self.secrets))])
        if self.replay:
            step.quit = True
            step.exit_code = 1
        return step

    def apply_line(self, line):
        # (reply, None) или (None, Step) -- ход не состоялся
        app = self.app
        try:
            if line.isdigit() and app.pending is not None:
                menu = app.menu_for(app.pending)
                if not 1 <= int(line) <= len(menu):
                    return None, Step([note_block("Нет такого варианта.")])
                return app.choose(menu[int(line) - 1]), None
            return app.handle(line), None
        except Exception as error:
            return None, self.failure(f"Ошибка хода: {error}")

    def render_step(self, line, reply, before, level_before):
        app = self.app
        step = Step(reply_blocks(app, reply, before[0], before))
        step.events = turn_events(app, reply, level_before)
        if reply.quit:
            step.quit = True
            return step
        first = reply.lines[0] if reply.lines else ""
        if first.startswith(LOADED_PREFIX) and not reply.narration:
            # загрузка удалась (/load или «загрузить» в меню смерти): последний рассказ мира
            narration = last_narration_block(app)
            if narration is not None:
                step.blocks.append(narration)
        # команда, сделавшая ход (/inv в бою), перерисовывает экран, как ход номером
        if not line.startswith("/") or line.startswith(SCREEN_COMMANDS) or reply.turn is not None:
            step.blocks.extend(screen_blocks(app))
        step.blocks.append(status_block(app))
        if reply.turn is None or app.pending is not None:
            return step
        state = limit_state(app)
        cfg = app.settings.app.cost_limits
        if state == "warn" and not self.warned:
            self.warned = True
            step.blocks.append(note_block(f"Потрачено {cfg.warn_percent}% лимита трат."))
        elif state == "pause" and not self.asked:
            step.blocks.append(note_block("Достигнут лимит трат (сессия или день)."))
            step.blocks.append(menu_block(LIMIT_MENU, "Выбери:"))
            self.limit_menu = True
        return step

    def limit_answer(self, line):
        app = self.app
        if line == "1":
            self.limit_menu = False
            self.asked = True
            return Step(screen_blocks(app))
        if line == "2":
            if app.pending == "hero_dead":
                return Step([note_block("Герой погиб: сохранять нельзя.")])
            try:
                app.save_current("auto")
            except ValueError as error:
                return Step([note_block(f"Не удалось сохранить: {error}")])
            return Step([note_block("Сохранено.")], quit=True)
        return Step([note_block("Нет такого варианта.")])
