# Помощники тестов роли summarizer (этап 4, партия P1; контракт обновлён партией #22 ТС). Не
# фикстуры pytest, а функции. Импорты ai_dm.* для новых модулей -- внутри функций: пока кода нет,
# тесты падают по одному (red).
#
# КОНТРАКТ (STAGE4-PLAN A3-A5, P1; Р2, Т60, ТС). Где план не даёт имён, они выбраны здесь -- это
# ТРЕБОВАНИЕ:
#   TurnRunner(..., summarizer_adapter=None, summarizer_model=None) и GameApp(...,
#     summarizer_adapter=None, summarizer_model=None) -- по образцу world_adapter / world_model.
#     summarizer_adapter=None -- тот же адаптер, что у нарратора. Модель по умолчанию --
#     профиль провайдера адаптера (app.profiles[provider].summarizer.model), иначе roles.summarizer.
#   Запросы роли: req.role == "summarizer", набор инструментов == {"scene_summary"}.
#   Инструмент scene_summary: {type, title: str ("" = нет), summary: str}; ровно один
#     вызов, summary не пустая. Пустая -- ответ инструмента is_error=True (повтор с пояснением).
#     Длиннее app.memory.scene_summary_max (600) -- тоже is_error=True с кратностью сокращения и
#     «Попытка k из N» (N = app.memory.summary_trim_after, по умолчанию 2); после N отклонений
#     следующая длинная выжимка принимается обрезанной по границе предложения (метка отчёта
#     summary_trimmed, SceneSummary.source == "summarizer"). summary_trim_after = 0 -- движок не
#     режет: длинные ответы идут в бюджет невалидных (retry.invalid_retries).
#   Бюджет невалидных исчерпан (3-й неверный ответ при invalid_retries = 2) -- не сбой границы, а
#     мягкий сбой: запасной вызов на модели рассказчика (Р2), затем fallback-выжимка
#     (source "fallback", метка отчёта summarizer_backup). Меню 2.2 -- только на fatal/rounds.
#   Как у world, ответ модели = шаг с вызовом инструмента + шаг с итоговым текстом.
#   Вход: messages[0].content[0].text содержит player_input и narration ходов закрытой сцены
#     (TurnRecord.scene_id == id закрытой сцены), подсказку (scene.summary / scene.title от
#     нарратора), причину закрытия. title: приоритет у scene.title нарратора.
#   Журнал: записи role "summarizer", run_id "bnd-..." (общий с world границы).
#   Сбой summarizer (fatal): TurnResult.boundary_failed, menu ["retry", "switch_model",
#     "save_and_quit"], session.boundary_pending True, бандл как после автосейва закрытой сцены.
#   Выжимка: SceneSummary(source="summarizer"). Меню 2.2 «сменить модель» при сбое границы
#     меняет модель (и адаптер из adapter_factory) роли summarizer, нарратор не трогает.
import json

from game_kit import (
    NOW,
    OPUS,
    ReactiveAdapter,
    scripted,
    settings,
    tools_step,
)

from ai_dm.llm.cost import CostLedger
from ai_dm.llm.journal import Journal
from ai_dm.llm.types import ChatResponse, Text, ToolCall, ToolResult, Usage


def scene_summary_call(summary="Выжимка сцены.", title="", call_id="ss-1"):
    data = {"type": "scene_summary", "title": title, "summary": summary}
    return {"id": call_id, "name": "scene_summary", "input": data}


def summ_steps(summary="Выжимка сцены.", title="", call_id="ss-1"):
    # один ответ summarizer целиком: вызов инструмента (после принятия вызова модели больше нет)
    return [tools_step(scene_summary_call(summary, title, call_id))]


def summ_fail_steps():
    return [{"error": "fatal", "message": "сбой сети"}]


def request_text(request):
    return "\n".join(b.text for m in request.messages for b in m.content if isinstance(b, Text))


def tool_results_text(request):
    parts = []
    for message in request.messages:
        for block in message.content:
            if isinstance(block, ToolResult):
                parts.append(block.content)
    return "\n".join(parts)


def has_tool_error(request):
    return any(
        isinstance(b, ToolResult) and b.is_error for m in request.messages for b in m.content
    )


class ReactiveSummarizer:
    # детерминированный summarizer: «Выжимка K» на каждую границу; остальные роли -- ReactiveAdapter
    def __init__(self, provider="anthropic", model=OPUS):
        self.inner = ReactiveAdapter(provider=provider, model=model)
        self.provider = provider
        self.model = model
        self.requests = []
        self.count = 0

    def info(self):
        return self.inner.info()

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        if {t.name for t in request.tools} != {"scene_summary"}:
            return self.inner.complete(request)
        number = len(self.requests)
        self.count += 1
        data = {"type": "scene_summary", "title": "", "summary": f"Выжимка {self.count}"}
        content = [ToolCall(id=f"rs-{number}", name="scene_summary", input=data)]
        return ChatResponse(
            content=content, stop_reason="tool_use", usage=Usage(input=100, output=20),
            request_id=f"rs-{number}", model=request.model,
        )


class SummRig:
    def __init__(self, runner, narrator, summarizer, journal):
        self.runner = runner
        self.narrator = narrator
        self.summarizer = summarizer
        self.journal = journal

    def play(self, n=1):
        return [self.runner.play(f"ход {i}") for i in range(n)]

    def summarizer_records(self):
        return [r for r in self.journal.read_records() if r["role"] == "summarizer"]

    def summarizer_requests(self):
        return [r for r in self.summarizer.requests if r.role == "summarizer"]

    def narrator_view(self):
        # запасные вызовы summarizer (Р2) идут через адаптер рассказчика: те же запросы роли,
        # но из narrator.requests
        return SummRig(self.runner, self.narrator, self.narrator, self.journal)


def make_summ_rig(
    registry, cfg, tmp_path, narrator_steps, summarizer, *, bundle=None, summarizer_model=None,
    world=None, world_model=None,
):
    # summarizer: список шагов (scripted) или готовый адаптер (есть complete)
    from game_kit import make_bundle

    from ai_dm.game.turn import TurnRunner

    app = settings().app
    if bundle is None:
        bundle = make_bundle(registry)
    narrator = scripted(narrator_steps)
    adapter = summarizer if hasattr(summarizer, "complete") else scripted(summarizer)
    journal = Journal(tmp_path, bundle.world.world_id, app.journal)
    ledger = CostLedger(tmp_path, bundle.world.world_id)
    extra = {}
    if world is not None:
        extra["world_adapter"] = world
        extra["world_model"] = world_model
    runner = TurnRunner(
        bundle, registry, cfg, app, narrator, saves_root=tmp_path, journal=journal,
        ledger=ledger, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        summarizer_adapter=adapter, summarizer_model=summarizer_model, **extra,
    )
    return SummRig(runner, narrator, adapter, journal)


def make_summ_app(
    registry, tmp_path, narrator, summarizer, *, adapter_factory=None, use_stored_model=False
):
    from game_kit import make_bundle

    from ai_dm.game.app import GameApp

    return GameApp(
        settings(), registry, make_bundle(registry), narrator, saves_root=tmp_path,
        adapter_factory=adapter_factory, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        use_stored_model=use_stored_model, summarizer_adapter=summarizer,
    )


def force_close(monkeypatch, reason):
    # причина закрытия сцены на каждом ходе (check_close как его импортирует game.turn)
    import ai_dm.game.turn as turn

    monkeypatch.setattr(turn, "check_close", lambda *args, **kwargs: reason)


def dumps(model):
    return json.dumps(model.model_dump(mode="json"), ensure_ascii=False, sort_keys=True)
