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
# окно мока большое, поэтому бюджет хода = статика + context_cap (master.context.budget):
# переполнение зависит только от динамики > MEMORY_CONTEXT_CAP, а не от роста правил/схем.
# Давление дают длинные имена NPC/локаций, выжимки глав и свёртка: вытесняются все ступени.
NPC_MEMORY_WINDOW = 400_000
# 2775: подобрано один раз (проходят 2750-2800: все пять ступеней, главы 1-4 на сцене 50
# на месте; ниже главы уходят раньше, выше ступень chapters не срабатывает)
MEMORY_CONTEXT_CAP = 2_775
MEMORY_NPC = "witness"
SCENES = 52
TURNS_PER_SCENE = 3
SCENES_PER_CHAPTER = 12
NARRATION_FILLER = "Ветер шумит над крышами, и город живёт своей жизнью. " * 6
SUMMARY_FILLER = " Герой помнит имена, долги и обещания этой сцены." * 2
CHAPTER_FILLER = " В этой главе герой нажил врагов и союзников, и мир ответил." * 12
GAME_FILLER = " Игра идёт, обещания копятся." * 40
LONG_NAME = "Достопочтенный хранитель дальних дорог и старых обещаний " * 14


def memory_delta(scene_number):
    # изменение отношения MEMORY_NPC в сцене scene_number (нумерация сцен прогона с 1):
    # модуль 1..9 по кругу (есть равные веса -- при вытеснении решает at_s), знак чередуется
    size = (scene_number * 7) % 9 + 1
    return size if scene_number % 2 else -size


def memory_settings():
    # (app_cfg, rules_cfg) под мок-модель: большое окно, фиксированный context_cap, 12 сцен в главе
    base = settings()
    app = base.app.model_copy(deep=True)
    app.context_windows[MODEL] = NPC_MEMORY_WINDOW
    app.master.context_cap = MEMORY_CONTEXT_CAP
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


def npc_memory_bundle(registry):
    # memory_bundle + NPC MEMORY_NPC в локации героя (он в scene_npcs, на нём копится память)
    bundle = memory_bundle(registry)
    bundle.world.npcs[MEMORY_NPC] = NPC(
        id=MEMORY_NPC, name="Свидетель", named=True, means=["m"],
        location_id=bundle.heroes[0].location_id,
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
    # npc_memory=True: первый ход каждой сцены -- npc_update MEMORY_NPC с отношением
    # memory_delta(k) и событием памяти «Сцена k» (k -- номер сцены прогона)
    def __init__(self, *, turns_done=0, scenes_done=0, chapters_done=0, npc_memory=False):
        self.npc_memory = npc_memory
        self.turns_done = turns_done
        self.scenes_done = scenes_done
        self.chapters_done = chapters_done
        self.turns_per_scene = TURNS_PER_SCENE
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
        if self.npc_memory and (number - 1) % self.turns_per_scene == 0:
            return self.reply(request, [self.memory_call(number)], "tool_use")
        text = f"Ход {number}. {NARRATION_FILLER}"
        return self.reply(request, [Text(text=text)], "end_turn")

    def memory_call(self, number):
        k = (number - 1) // self.turns_per_scene + 1
        data = {
            "type": "npc_update", "npc_id": MEMORY_NPC, "attitude_delta": memory_delta(k),
            "memory_kind": "helped", "memory_text": f"Сцена {k}",
        }
        return ToolCall(id=f"nm-{number}", name="npc_update", input=data)

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

    mock = mock or MemoryMock()
    app, rules = memory_settings()
    bundle = bundle or (npc_memory_bundle if mock.npc_memory else memory_bundle)(registry)
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

