# Приёмка этапа 5 (STAGE5-PLAN, P5, часть C п. 3): сценарий этапа 2 «разговор -> проверка -> бой ->
# победа -> повышение уровня» на моке проходит в простом режиме (ScriptedInput) и в TUI (Pilot,
# фиксированный size, без sleep) с одинаковым итоговым бандлом. Живых вызовов нет.
# Простой режим идёт первым и записывает строки ввода (бой реактивный: номера действий зависят
# от вывода); TUI получает ровно те же строки. core_dump -- без manifest (saved_at, slot).
# Остальные пункты части C покрыты в tests/unit/ui (панели -- test_tui_turn / test_tui_layout,
# HELP в обоих режимах -- test_commands_both_modes, русский -- test_tui_russian,
# fallback -- test_tui_entry_points).
import asyncio
import re
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import core_dump  # noqa: E402
from ui_kit import (  # noqa: E402
    DESCEND,
    TALK,
    WORLD,
    FightInput,
    PlainOutput,
    ReactiveAdapter,
    ScriptThenReactive,
    build_app,
    numbered_lines,
    player_action_input,
    scripted_from_yaml,
)

from ai_dm.ui.session import PlaySession  # noqa: E402
from ai_dm.ui.simple import run  # noqa: E402
from ai_dm.ui.tui.app import AiDmApp  # noqa: E402

KICK = "Опрокидываю бочку на ближнего гоблина"
IMPROVISE = {
    "skill": "athletics", "category": "medium", "effect": "prone", "target": "goblin_1",
    "zone": "",
}
SIZE = (140, 40)


class RecordingInput(FightInput):
    # FightInput, который запоминает все отданные строки и кончает ввод после выбора «среднее
    # значение HP» в меню повышения уровня
    def __init__(self, out, first):
        super().__init__(out, first)
        self.given = []
        self.leveled = False

    def read(self, prompt=""):
        if self.leveled:
            return None
        options = numbered_lines(self.out.lines[self.seen:])
        line = super().read(prompt)
        if line is not None:
            self.given.append(line)
        for number, text in options:
            if line == str(number) and "средн" in text.lower():
                self.leveled = True
        return line


def scene_app(registry, root):
    adapter = ScriptThenReactive(
        scripted_from_yaml("talk_check_fight.yaml"),
        ReactiveAdapter(classify=[player_action_input([], improvise=IMPROVISE)]),
    )
    return build_app(registry, root, adapter, hp=200)


def simple_story(registry, root):
    app = scene_app(registry, root)
    out = PlainOutput()
    source = RecordingInput(out, [TALK, "1", DESCEND, KICK])
    run(app, source, out)
    return app, out, source.given


def tui_story(registry, root, lines):
    app = scene_app(registry, root)
    tui = AiDmApp(PlaySession(app))

    async def scenario():
        async with tui.run_test(size=SIZE) as pilot:
            await pilot.pause()
            gains = []
            for line in lines:
                if line.isdigit() and tui.game.bundle.session.active_combat is not None:
                    # в бою цифра+Enter в TUI -- видимая строка меню; записанный простым режимом
                    # плоский номер отдаём в ход напрямую (тот же путь, что у выбора строки)
                    tui.start_turn(line)
                else:
                    tui.query_one("#input").value = line
                    await pilot.press("enter")
                await tui.workers.wait_for_complete()
                await pilot.pause()
                gains.append(gains_text(tui))
            return {
                "feed": "\n".join(s.text for s in tui.query_one("#feed").lines),
                "gains": gains,
            }

    return app, asyncio.run(scenario())


def gains_text(tui):
    widget = tui.query_one("#gains")
    return str(widget.render()) + "\n".join(str(c.render()) for c in widget.children)


@pytest.fixture(scope="module")
def stories(registry, tmp_path_factory):
    # один прогон на модуль: простой режим, потом TUI с теми же строками ввода
    root = tmp_path_factory.mktemp("stage5")
    simple, out, given = simple_story(registry, root / "simple")
    tui_app, shown = tui_story(registry, root / "tui", given)
    return {"simple": simple, "out": out, "given": given, "tui": tui_app, "shown": shown}


def test_simple_story_is_a_won_fight_with_level_up(stories):
    app = stories["simple"]
    assert "победа" in stories["out"].text.lower()
    assert app.bundle.heroes[0].sheet.level == 2
    assert app.bundle.session.active_combat is None
    assert len(stories["given"]) > 6


def test_tui_gives_same_bundle_as_simple_mode(stories):
    assert core_dump(stories["tui"].bundle) == core_dump(stories["simple"].bundle)


def test_tui_scene_shows_narration_in_feed(stories):
    # рассказ в рамке переносится по ширине: убираем боковые рамки и склеиваем строки
    feed = " ".join(stories["shown"]["feed"].replace("│", " ").split())
    assert "в подвале «Хромого гуся» что-то возится" in feed
    assert "Трактирщик вздыхает и кивает на дверь в подвал." in feed
    assert "Из темноты выскакивают гоблины, а за бочками ухмыляется Гракх." in feed


def test_tui_scene_shows_gains_after_victory(stories):
    # панель очищается следующим ходом (выбор уровня), поэтому смотрим после каждого хода
    assert any("300" in text for text in stories["shown"]["gains"])


def test_tui_scene_has_no_latin_words_in_feed(stories):
    from ai_dm.game.commands import HELP

    text = stories["shown"]["feed"].replace(WORLD, "")
    for name in HELP:
        text = text.replace(f"/{name}", "")
    text = re.sub(r"\b\d*d\d+\b", "", text).replace("HP", "")
    # названия клавиш в подсказке боя: Tab, F3, F4
    text = re.sub(r"\bF\d{1,2}\b", "", text).replace("Tab", "")
    assert re.findall(r"[A-Za-z]+", text) == []
