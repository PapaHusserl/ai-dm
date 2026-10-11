# Помощники тестов свёртки главы (этап 4, партия P2). Поверх summarizer_kit.py.
#
# КОНТРАКТ (STAGE4-PLAN A4, A5 шаг 3, P2). Где план не даёт имён, они выбраны здесь -- это
# ТРЕБОВАНИЕ:
#   Запрос свёртки главы: req.role == "summarizer", набор инструментов ==
#     {"chapter_summary", "game_summary"}.
#   chapter_summary: {type, title: str, summary: str}; game_summary: {type, summary: str}.
#     Оба вызова обязательны В ОДНОМ ответе: ответ только с одним -- невалидный (повтор с
#     пояснением, ничего не принимается). Пределы: summary главы <= 1500, игры <= 3000 символов
#     (app.memory.chapter_summary_max / game_summary_max); пустая строка -- невалидно.
#   Вход главы (system + messages) содержит выжимки сцен ЭТОЙ главы (вкл. только что сделанную на
#     шаге 1), прежний memory.game_summary, название главы; выжимок сцен других глав нет.
#   Результат: memory.chapters[-1] == ChapterSummary(source="summarizer", summary из
#     chapter_summary), memory.game_summary из game_summary, memory.game_summary_chapter == номер
#     закрытой главы. Название: если нарратор не дал (end_chapter.title пуст) -- title из
#     chapter_summary.
#   Сбой свёртки: одна транзакция с шагом 1 -- бандл как после автосейва (memory.scenes без новой
#     выжимки, глава не закрыта), TurnResult.boundary_failed, меню 2.2; retry делает оба вызова.
#   TurnRunner без адаптера summarizer на закрытии главы: запасной склейки больше нет -- эти случаи
#     в тестах не проверяются.
from game_kit import text_step, tools_step
from summarizer_kit import ReactiveSummarizer, request_text

from ai_dm.llm.types import ChatResponse, ToolCall, ToolResult, Usage
from ai_dm.state.session import ChapterState


def chapter_bundle(registry, count=1, number=1):
    from game_kit import make_bundle

    bundle = make_bundle(registry)
    bundle.session.current_chapter = ChapterState(
        id=f"chapter_{number}", number=number, started_at_s=0, scene_count=count
    )
    return bundle


def end_chapter_call(title="Конец пролога", call_id="ec-1"):
    return {
        "id": call_id, "name": "end_chapter",
        "input": {"type": "end_chapter", "title": title},
    }


def chapter_summary_call(summary="Выжимка главы.", title="Название ИИ", call_id="cs-1"):
    data = {"type": "chapter_summary", "title": title, "summary": summary}
    return {"id": call_id, "name": "chapter_summary", "input": data}


def game_summary_call(summary="Новая свёртка игры.", call_id="gs-1"):
    return {
        "id": call_id, "name": "game_summary", "input": {"type": "game_summary", "summary": summary}
    }


def chapter_steps(
    chapter="Выжимка главы.", game="Новая свёртка игры.", title="Название ИИ", suffix="1"
):
    # один ответ summarizer целиком: оба вызова в одном шаге (модель больше не зовут)
    calls = [
        chapter_summary_call(chapter, title, f"cs-{suffix}"),
        game_summary_call(game, f"gs-{suffix}"),
    ]
    return [tools_step(*calls)]


def only_chapter_steps(suffix="1"):
    return [tools_step(chapter_summary_call(call_id=f"cs-{suffix}"))]


def only_game_steps(suffix="1"):
    return [tools_step(game_summary_call(call_id=f"gs-{suffix}"))]


def chapter_requests(rig):
    names = {"chapter_summary", "game_summary"}
    return [r for r in rig.summarizer_requests() if {t.name for t in r.tools} == names]


def scene_requests(rig):
    return [r for r in rig.summarizer_requests() if {t.name for t in r.tools} == {"scene_summary"}]


def fresh(requests):
    # первые запросы вызова (без результатов инструментов): по одному на вызов роли, не на раунд
    return [
        r for r in requests
        if not any(isinstance(b, ToolResult) for m in r.messages for b in m.content)
    ]


def full_text(request):
    # system + messages: куда именно кладётся вход главы, тест не навязывает
    return "\n".join(b.text for b in request.system) + "\n" + request_text(request)


def end_scene_and_chapter(title="Пролог", summary=""):
    from game_kit import end_scene_call

    calls = [end_scene_call(summary=summary), end_chapter_call(title)]
    return [tools_step(*calls), text_step("Конец.")]


class ReactiveChapterSummarizer(ReactiveSummarizer):
    # «Выжимка K» на сцену, «Выжимка главы K» и «Свёртка K» на главу
    def __init__(self, provider="anthropic", model=None):
        from game_kit import OPUS

        super().__init__(provider=provider, model=model or OPUS)
        self.chapters = 0

    def complete(self, request):
        names = {t.name for t in request.tools}
        if names != {"chapter_summary", "game_summary"}:
            return super().complete(request)
        self.requests.append(request.model_copy(deep=True))
        number = len(self.requests)
        self.chapters += 1
        n = self.chapters
        content = [
            ToolCall(id=f"rc-{number}", name="chapter_summary", input={
                "type": "chapter_summary", "title": f"Глава ИИ {n}",
                "summary": f"Выжимка главы {n}",
            }),
            ToolCall(id=f"rg-{number}", name="game_summary", input={
                "type": "game_summary", "summary": f"Свёртка {n}",
            }),
        ]
        return ChatResponse(
            content=content, stop_reason="tool_use", usage=Usage(input=100, output=20),
            request_id=f"rs-{number}", model=request.model,
        )
