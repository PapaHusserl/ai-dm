# Этап 5, P2 (STAGE5-PLAN A5, A7, A8): TUI-каркас. Ожидаемый API (ТРЕБОВАНИЕ к коду P2):
#   ai_dm.ui.tui.app.AiDmApp(session: PlaySession, startup=...) -- App на Textual;
#   id виджетов: #feed #choices #input #status #side #picture (скрыт без рисунка)
#   #hero #combat #rolls #gains;
#   ширина >= 120 -- две колонки, иначе одна, F2 показывает #side; палитра команд выключена;
#   ход -- в thread-worker: пока идёт, #input disabled и «Мастер думает…» в #status; потом #input
#   снова активен и в фокусе; #hero показывает "<hp>/<hp_max>", #rolls -- строки бросков хода,
#   #status -- строка состояния (сессия $X) и процент лимита "N%", если лимит трат включён.
# Тесты без сети: мок-адаптер, фиксированный размер, Pilot через asyncio.run (без плагина), без сна.
# Хелперы -- через фикстуру tui (conftest не импортируют).
import re
import sys
import threading
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from game_kit import OPUS, damage_call, skill_check_call  # noqa: E402
from ui_kit import WORLD, build_app, text_app  # noqa: E402

from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402

HP = 30
# ход «рассказ + skill_check» (+ урон, чтобы менялся HP); у обоих шагов ненулевая стоимость
NARRATION = "Огонь."
TURN_STEPS = [
    {"tool_calls": [skill_check_call(), damage_call()], "usage": {"input": 10, "output": 1}},
    {"text": NARRATION, "usage": {"input": 1500, "output": 60}},
]
STATUS_COST = re.compile(r"сессия \$(\d+(?:\.\d+)?)")
PERCENT = re.compile(r"(\d+(?:[.,]\d+)?)\s*%")


class GateAdapter(ScriptedAdapter):
    # барьер: первый вызов модели сообщает «вошёл» и ждёт release (с потолком, чтобы тест не завис)
    def __init__(self, steps):
        super().__init__(steps, provider="anthropic", model=OPUS)
        self.entered = threading.Event()
        self.release = threading.Event()

    def complete(self, req):
        self.entered.set()
        assert self.release.wait(10)
        return super().complete(req)


class Tui:
    TURN_STEPS = TURN_STEPS
    NARRATION = NARRATION
    HP = HP

    def app(self, registry, root, steps=None, adapter=None, limits=None):
        # -> (AiDmApp, GameApp); limits={"session": micro, "day": micro} включает лимит трат
        from ai_dm.ui.session import PlaySession
        from ai_dm.ui.tui.app import AiDmApp

        if adapter is None:
            game = text_app(registry, root, TURN_STEPS if steps is None else steps, hp=HP)
        else:
            game = build_app(registry, root, adapter, hp=HP)
        if limits is not None:
            cfg = game.settings.app.cost_limits
            cfg.enabled = True
            cfg.session_limit_micro = limits.get("session", 0)
            cfg.day_limit_micro = limits.get("day", 0)
        return AiDmApp(PlaySession(game)), game

    def spent_nano(self, registry, root):
        # сколько стоит ход TURN_STEPS на моке (пробный прогон в отдельном каталоге)
        from ai_dm.ui.session import PlaySession

        probe = text_app(registry, root, TURN_STEPS, hp=HP)
        PlaySession(probe).submit("Иду")
        return probe.ledger.report(probe.now().astimezone().date()).session.total_nano

    def text_of(self, widget):
        # текст виджета: RichLog -- lines, остальные -- render(); плюс текст потомков
        if hasattr(widget, "lines"):
            parts = ["\n".join(strip.text for strip in widget.lines)]
        else:
            parts = [str(widget.render())]
        parts += [self.text_of(child) for child in widget.children]
        return "\n".join(parts)

    def flat(self, text):
        return " ".join(text.split())

    def shown(self, widget):
        # виджет реально на экране: у скрытого (display: none) области нет
        return widget.region.area > 0

    def screen_rows(self, app):
        return [strip.text for strip in app.screen._compositor.render_strips()]

    def visible_text(self, app):
        return "\n".join(self.screen_rows(app))

    def footer_text(self, app):
        from textual.widgets import Footer

        region = app.query_one(Footer).region
        rows = self.screen_rows(app)
        return "\n".join(rows[region.y:region.bottom])

    def latin_words(self, text, world_id=WORLD):
        # белый список A7: id мира, фактический provider:model игры, HP, $ (не латиница), метки
        # клавиш F2 / ^q, /команды из HELP (подсказка ввода), а также то, что приходит из слоя
        # game в строках бросков: запись кубиков d20 / 2d10
        from ai_dm.game.commands import HELP

        text = text.replace(world_id, "")
        text = text.replace(f"anthropic:{OPUS}", "")
        for name in HELP:
            text = text.replace(f"/{name}", "")
        text = re.sub(r"\b\d*d\d+\b", "", text)
        text = re.sub(r"\bF\d{1,2}\b", "", text)
        text = re.sub(r"\^[A-Za-z]", "", text)
        text = text.replace("HP", "")
        return re.findall(r"[A-Za-z]+", text)

    async def submit(self, app, pilot, line="Иду"):
        # ввод строки в поле + Enter + ждём конец worker'а
        entry = app.query_one("#input")
        entry.value = line
        await pilot.press("enter")
        await app.workers.wait_for_complete()
        await pilot.pause()

    def session_cost(self, app):
        match = STATUS_COST.search(self.text_of(app.query_one("#status")))
        return float(match.group(1))

    def percent(self, app):
        match = PERCENT.search(self.text_of(app.query_one("#status")))
        return None if match is None else float(match.group(1).replace(",", "."))


@pytest.fixture
def tui():
    return Tui()


@pytest.fixture
def gate_adapter():
    return GateAdapter(TURN_STEPS)
