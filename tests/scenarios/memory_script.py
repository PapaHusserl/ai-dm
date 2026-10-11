# Генератор мок-сценария приёмки этапа 4 (STAGE4-PLAN, P4): 52 сцены по несколько ходов, глава
# закрывается сама на 12-й сцене (scene.max_per_chapter = 12), память копится. Живых вызовов и сети
# нет: один детерминированный мок-адаптер отвечает за три роли (narrator, summarizer, world).
# Контракт kit-ов: tests/unit/game/game_kit.py, summarizer_kit.py.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "game"))

from game_kit import NOW, make_bundle, settings  # noqa: E402

from ai_dm.llm.adapter import AdapterInfo  # noqa: E402
from ai_dm.llm.cost import CostLedger  # noqa: E402
from ai_dm.llm.journal import Journal  # noqa: E402
from ai_dm.llm.types import ChatResponse, Text, ToolCall, ToolResult, Usage  # noqa: E402
from ai_dm.state.world import NPC, Connection, Location  # noqa: E402

MODEL = "mock"
# окно мок-модели: бюджет хода = 80% окна = 16 000 (меньше потолка 30 000). План P4 называл 12 000,
# но одни правила + tools нарратора (~12.5k ток. по len/2.5) не влезают в бюджет 9 600: overflow
# на каждом ходе. При 20 000 неустранимое к концу прогона ~14.4k (запас бюджета ~1.6k), а давление
# дают длинные имена NPC/локаций, выжимки глав и свёртка: вытесняются все четыре ступени.
# Если правила нарратора заметно выросли -- подобрать заново (филлеры, LONG_NAME).
# 20500 -> 20650: схема trade и поля trade_kind/holder_npc_id (торговля, Т2) дали +99 ток. оценки.
# 20650 -> 21470: раздел «Торговля» в narrator_rules и схема trade list (торговля, Т3):
# пик оценки 16520 -> 17244 ток. (+724), окно +820 (21450 падает; дубли схема↔правила убраны).
# 21470 -> 21900: абзац про торг в «Торговле» и схема haggle (торговля, Т5): пик 17201 -> 17520.
# 21900 -> 21910: на чистом 39a9b80 пик неустранимого 17526 > бюджета 17520
# (не дата/TZ/HOME/хеш-сид: оценка детерминирована; вероятно окружение, не код); запас 2 ток.
# 21910 -> 22070: раздел «Тон» в narrator_rules (Б0-П0, романтика 1-4): пик 17526 -> 17654
# (с ростом окна меньше вытеснения); бюджет 80% окна = 17656, запас 2 ток.
# 22070 -> 22450: Б1-фикс пп.3-4 в narrator_rules (рассуждения, выдача вещей): пик 17654 -> 17902
# (бюджет 80% окна = 17960, запас 58 ток.).
# 22450 -> 23000: К0-фикс (правила effect, offer_choices, scene_npcs): пик 17986 > 17960;
# при 22600-22800 пик растёт вместе с окном (меньше вытеснения), проходит 23000 (бюджет 18400).
WINDOW = 23000
SCENES = 52
TURNS_PER_SCENE = 3
SCENES_PER_CHAPTER = 12
NARRATION_FILLER = "Ветер шумит над крышами, и город живёт своей жизнью. " * 6
SUMMARY_FILLER = " Герой помнит имена, долги и обещания этой сцены." * 2
CHAPTER_FILLER = " В этой главе герой нажил врагов и союзников, и мир ответил." * 12
GAME_FILLER = " Игра идёт, обещания копятся." * 40
LONG_NAME = "Достопочтенный хранитель дальних дорог и старых обещаний " * 14


def memory_settings():
    # (app_cfg, rules_cfg) под мок-модель: окно WINDOW, 12 сцен в главе
    base = settings()
    app = base.app.model_copy(deep=True)
    app.context_windows[MODEL] = WINDOW
    app.prices[MODEL] = next(iter(app.prices.values())).model_copy()
    rules = base.rules.model_copy(deep=True)
    rules.scene.max_per_chapter = SCENES_PER_CHAPTER
    return app, rules


def memory_bundle(registry):
    # 6 NPC вне сцены (3 ключевых, 3 в соседних локациях) и 6 соседних локаций вокруг Вейла
    bundle = make_bundle(registry)
    world = bundle.world
    vale = world.locations["vale"]
    for place_id, distance in (("mid", 100), ("far", 9000), ("tie_a", 700), ("tie_b", 700)):
        world.locations[place_id] = Location(id=place_id, name=f"{LONG_NAME}{place_id}")
        vale.connections.append(Connection(to=place_id, distance_m=distance))
    world.locations["rev"] = Location(
        id="rev", name=f"{LONG_NAME}rev", connections=[Connection(to="vale", distance_m=500)]
    )
    for npc_id in ("keyer_a", "keyer_b", "keyer_c"):
        world.npcs[npc_id] = NPC(
            id=npc_id, name=f"{LONG_NAME}{npc_id}", named=True, key=True, means=["m"],
            location_id="goblin_den",
        )
    for npc_id, place_id in (("near_a", "forest"), ("near_b", "mid"), ("near_c", "tie_a")):
        world.npcs[npc_id] = NPC(
            id=npc_id, name=f"{LONG_NAME}{npc_id}", named=True, means=["m"], location_id=place_id
        )
    return bundle


def end_scene_call(call_id):
    return ToolCall(
        id=call_id, name="end_scene", input={"type": "end_scene", "summary": ""}
    )


def answered(request):
    return any(isinstance(b, ToolResult) for m in request.messages for b in m.content)


class MemoryMock:
    # один адаптер на три роли; ответы зависят только от роли, набора инструментов и счётчиков
    # (turns_done, scenes_done, chapters_done -- стартовое состояние при продолжении после загрузки)
    def __init__(self, *, turns_done=0, scenes_done=0, chapters_done=0, turns_per_scene=None):
        self.turns_done = turns_done
        self.scenes_done = scenes_done
        self.chapters_done = chapters_done
        self.turns_per_scene = turns_per_scene or TURNS_PER_SCENE
        self.requests = []
        # первые запросы нарратора каждого хода (без раундов инструментов), по порядку
        self.narrator_turns = []

    def info(self):
        return AdapterInfo(provider="mock", model=MODEL)

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        names = {t.name for t in request.tools}
        if request.role == "summarizer" and names == {"scene_summary"}:
            return self.scene_summary(request)
        if request.role == "summarizer" and names == {"chapter_summary", "game_summary"}:
            return self.chapter_summary(request)
        if request.role == "narrator":
            return self.narrate(request)
        return self.reply(request, [Text(text="Принято.")], "end_turn")

    def reply(self, request, content, stop):
        number = len(self.requests)
        return ChatResponse(
            content=content, stop_reason=stop, usage=Usage(input=100, output=20),
            request_id=f"mem-{number}", model=request.model,
        )

    def narrate(self, request):
        if answered(request):
            return self.reply(request, [Text(text="Сцена кончилась.")], "end_turn")
        self.narrator_turns.append(request.model_copy(deep=True))
        self.turns_done += 1
        number = self.turns_done
        if number % self.turns_per_scene == 0:
            call = end_scene_call(f"es-{number}")
            return self.reply(request, [call], "tool_use")
        text = f"Ход {number}. {NARRATION_FILLER}"
        return self.reply(request, [Text(text=text)], "end_turn")

    def scene_summary(self, request):
        self.scenes_done += 1
        k = self.scenes_done
        text = f"Выжимка сцены {k}.{SUMMARY_FILLER}"
        data = {"type": "scene_summary", "title": "", "summary": text}
        call = ToolCall(id=f"ss-{k}", name="scene_summary", input=data)
        return self.reply(request, [call], "tool_use")

    def chapter_summary(self, request):
        self.chapters_done += 1
        m = self.chapters_done
        chapter = {
            "type": "chapter_summary", "title": f"Название главы {m}",
            "summary": f"Глава {m}.{CHAPTER_FILLER}",
        }
        game = {"type": "game_summary", "summary": f"Игра до главы {m}.{GAME_FILLER}"}
        calls = [
            ToolCall(id=f"cs-{m}", name="chapter_summary", input=chapter),
            ToolCall(id=f"gs-{m}", name="game_summary", input=game),
        ]
        return self.reply(request, calls, "tool_use")


class MemoryRun:
    def __init__(self, runner, journal, mock):
        self.runner = runner
        self.journal = journal
        self.mock = mock
        self.first_turn = mock.turns_done + 1
        self.results = []

    def play_scenes(self, count):
        # по TURNS_PER_SCENE ходов; последний ход сцены закрывает её (end_scene)
        for _ in range(count * self.mock.turns_per_scene):
            # после загрузки счёт ходов продолжается (turns_done мока), а не идёт с 1
            n = self.first_turn + len(self.results)
            self.results.append(self.runner.play(f"Ход {n}: иду дальше."))

    def narrator_records(self):
        return [r for r in self.journal.read_records() if r["role"] == "narrator"]


def new_run(
    registry, root, *, bundle=None, mock=None, adapters=None, run_tag="t",
):
    # adapters: (narrator, summarizer, world) для replay; по умолчанию один MemoryMock на всех
    from ai_dm.game.turn import TurnRunner

    app, rules = memory_settings()
    bundle = bundle or memory_bundle(registry)
    mock = mock or MemoryMock()
    narrator, summarizer, world = adapters or (mock, mock, mock)
    journal = Journal(root, bundle.world.world_id, app.journal)
    ledger = CostLedger(root, bundle.world.world_id)
    runner = TurnRunner(
        bundle, registry, rules, app, narrator, saves_root=root, journal=journal, ledger=ledger,
        sleeper=lambda s: None, now=lambda: NOW, run_tag=run_tag, model=MODEL,
        world_adapter=world, summarizer_adapter=summarizer,
    )
    return MemoryRun(runner, journal, mock)


def play_memory(registry, root, scenes=SCENES, **kwargs):
    run = new_run(registry, root, **kwargs)
    run.play_scenes(scenes)
    return run

