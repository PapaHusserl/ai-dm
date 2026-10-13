import re
import time
from datetime import UTC, datetime

from pydantic import ValidationError

from ai_dm.llm.cost import cost_nano, pick_price
from ai_dm.llm.errors import LlmFatal, RetriesExhausted
from ai_dm.llm.retry import call_with_retries
from ai_dm.llm.types import Message, Text, ToolCall, ToolResult
from ai_dm.master.prompt import PromptBuilder
from ai_dm.protocol.decision import Invalid
from ai_dm.protocol.render import render_tool_result
from ai_dm.protocol.requests import IMPORT_MODE, parse_request
from ai_dm.protocol.schema import tool_set

REQUIRED_BY_MODE = {
    "combat_classify": "player_action",
    "npc_choice": "npc_action",
    "summarize_scene": "scene_summary",
    "summarize_chapter": "chapter_summary",
    "hero_background": "background_spec",
    "hero_sheet": "hero_sheet",
    IMPORT_MODE: "pack",
}

# режимы, где после принятого обязательного инструмента завершающий вызов модели не нужен
SINGLE_SHOT_MODES = (
    "summarize_scene", "summarize_chapter", "hero_background", "hero_sheet", IMPORT_MODE
)

# инструменты, после которых рассказ уже можно считать законченным
FREE_TOOLS = ("offer_choices",)

# подсказка при пустом ответе по режиму (world -- по роли)
EMPTY_NOTES = {
    "world": "Пустой ответ. Вызови нужные инструменты.",
    "hero_background": "Пустой ответ. Вызови инструмент background_spec.",
    "hero_sheet": "Пустой ответ. Вызови инструмент hero_sheet.",
    IMPORT_MODE: "Пустой ответ. Вызови инструмент pack.",
    "summarize_chapter": "Пустой ответ. Вызови chapter_summary и game_summary.",
    "summarize_scene": "Пустой ответ. Вызови инструмент scene_summary.",
    "narrator": "Пустой ответ. Напиши повествование или вызови нужный инструмент.",
}

FENCE = re.compile(r"^\s*```[\w-]*\s*$")


def plain_text(text) -> str:
    # модель иногда заворачивает рассказ в блок ``` -- рамку рисует игра, ограды выбрасываются
    return "\n".join(line for line in text.split("\n") if not FENCE.match(line)).strip()


class TurnFailed(Exception):
    def __init__(self, reason, message, report_tags=None):
        super().__init__(message)
        self.reason = reason
        self.report_tags = report_tags or []


class MasterResult:
    def __init__(self):
        self.texts = []
        self.narration = ""
        self.decisions = []
        self.requests = []
        self.report_tags = []
        self.stop_reason = None
        self.rounds = 0
        self.invalid_count = 0


class MasterSession:
    """Сессия мастера: цикл инструментов одного вызова модели за ход.

    Контракт для game: создаёт PromptBuilder(app_cfg, model=<модель выбранного адаптера>) и
    передаёт его в сессию (builder=). Бюджет контекста считается в master.context по длине
    запроса (без вызовов адаптера) на первом build прогона; план вытеснения идёт в запись
    журнала narrator (meta.context), при неустранимом переполнении -- тег context_overflow.
    Все вызовы мастера одного прогона хода (classify / npc_choice / narrate) идут с одним
    run_id: run(..., run_id=...).
    """

    def __init__(
        self, adapter, app_cfg, *, journal=None, ledger=None, run_id="run-1",
        sleeper=time.sleep, now=None, builder=None, role="narrator", call_numbers=None,
        note=None,
    ):
        self.adapter = adapter
        self.app_cfg = app_cfg
        self.journal = journal
        self.ledger = ledger
        self.run_id = run_id
        self.sleeper = sleeper
        self.now = now or (lambda: datetime.now(UTC))
        self.role = role
        self.builder = builder or PromptBuilder(app_cfg, role=role)
        # run_id -> сколько вызовов уже записано; общий словарь на роли одной границы
        self.call_numbers = {} if call_numbers is None else call_numbers
        # приписка к запросу (повтор после отказа): отдельный блок после JSON состояния
        self.note = note

    def required_tool(self, ctx, mode):
        required = REQUIRED_BY_MODE.get(mode)
        if mode == "world" and ctx.verdict_refs:
            required = "world_verdict"
        if mode == "combat_narrate":
            combat = ctx.bundle.session.active_combat
            if combat is not None and combat.outcome == "defeat_pending":
                required = "defeat_outcome"
        return required

    def with_note(self, req):
        if self.note is None:
            return req
        first = req.messages[0]
        content = list(first.content) + [Text(text=self.note)]
        messages = [first.model_copy(update={"content": content})] + list(req.messages[1:])
        return req.model_copy(update={"messages": messages})

    def call(self, ctx, req, run_id, plan=None):
        info = self.adapter.info()

        def on_attempt(attempt, response, error):
            number = self.call_numbers.get(run_id, 0) + 1
            self.call_numbers[run_id] = number
            call_id = f"{run_id}-{number}"
            moment = self.now()
            cost = 0
            model = info.model
            meta = None
            tags = []
            if plan is not None:
                meta = {"context": plan.meta()}
                if plan.overflow:
                    tags = ["context_overflow"]
            note = None
            if response is not None:
                model = response.model
                price_model, price, note = pick_price(
                    self.app_cfg.prices, req.model, response.model
                )
                cost = cost_nano(response.usage, price)
                if meta is not None:
                    # калибровка оценки: реальные токены запроса по usage (без count_tokens)
                    usage = response.usage
                    meta["context"]["api_tokens"] = (
                        usage.input + usage.cache_read + usage.cache_write + usage.cache_write_1h
                    )
            if self.journal is not None:
                self.journal.record_call(
                    call_id=call_id, run_id=run_id, ts=moment.isoformat(),
                    turn_seq=ctx.turn_seq, attempt=attempt, role=self.role,
                    provider=info.provider, model=model, request=req, response=response,
                    cost_nano=cost, error=error, report_tags=tags, meta=meta,
                )
            if self.ledger is not None and response is not None:
                self.ledger.add(
                    call_id=call_id, role=self.role, model=price_model, usage=response.usage,
                    cost_nano=cost, day=moment.astimezone().date(), note=note,
                )

        try:
            return call_with_retries(
                self.adapter, req, self.app_cfg.retry, self.sleeper, on_attempt
            )
        except RetriesExhausted as error:
            raise TurnFailed("network", str(error)) from error
        except LlmFatal as error:
            raise TurnFailed("fatal", str(error)) from error

    def run_call(self, ctx, call, executor, allowed, result, mode="explore"):
        if call.name not in allowed:
            return Invalid(
                code="not_available_in_mode",
                message=f"Инструмент {call.name}: в этом режиме недоступно. "
                f"Доступны: {', '.join(sorted(allowed))}.",
            )
        # тип однозначно задан именем инструмента: модель (Gemini flash-lite) его порой опускает
        if "type" not in call.input:
            call.input["type"] = call.name
        if call.input.get("type") != call.name:
            return Invalid(
                code="invalid_request",
                message=f"Тип запроса {call.input.get('type')!r} не совпадает "
                f"с именем инструмента {call.name}.",
            )
        try:
            request = parse_request(call.input, mode)
        except ValidationError as error:
            return Invalid(code="invalid_request", message=str(error))
        result.requests.append(request)
        outcome = executor(ctx, request)
        if isinstance(outcome, Invalid) and outcome.report_tag is not None:
            result.report_tags.append(outcome.report_tag)
        return outcome

    def run_round(self, ctx, calls, executor, result, mode):
        # раунд вызовов -> (ответы инструментов, есть ли отклонённые, имена принятых инструментов)
        allowed = {d["name"] for d in tool_set(mode)}
        blocks = []
        has_invalid = False
        accepted_names = set()
        for call in calls:
            outcome = self.run_call(ctx, call, executor, allowed, result, mode)
            if isinstance(outcome, Invalid):
                has_invalid = True
            else:
                result.decisions.append(outcome)
                if outcome.status in ("accepted", "clamped"):
                    accepted_names.add(call.name)
                if outcome.report_tag is not None:
                    result.report_tags.append(outcome.report_tag)
            rendered = render_tool_result(outcome)
            blocks.append(ToolResult(
                call_id=call.id, content=rendered["content"], is_error=rendered["is_error"],
            ))
        if mode == "summarize_chapter" and accepted_names != set(allowed):
            # свёртка главы: оба инструмента в одном ответе; хендлеры пишут в ctx и в
            # отклонённом раунде, но повтор их перезаписывает -- к успеху в ctx значения
            # последнего полного ответа (close_chapter всё равно проверяет их наличие)
            if not has_invalid:
                note = "Нужны оба вызова в одном ответе: chapter_summary и game_summary."
                blocks.append(Text(text=note))
            has_invalid = True
        return blocks, has_invalid, accepted_names

    def finish(self, result):
        # рассказ — все принятые тексты хода: модель часто пишет повествование
        # в том же ответе, где вызывает инструмент, а финальный ответ — короткий
        result.narration = plain_text("\n\n".join(t.strip() for t in result.texts if t.strip()))
        return result

    def count_invalid(self, result, message):
        result.invalid_count += 1
        if result.invalid_count > self.app_cfg.retry.invalid_retries:
            raise TurnFailed("invalid", message)

    def empty_note(self, mode, result, required, required_done):
        # пустой ответ: подсказка модели или None, если пустой финал допустим
        # рассказ уже написан вместе с инструментом -- пустой финал не повторяем
        told = any(t.strip() for t in result.texts)
        if self.role == "world":
            # world рассказа не пишет: после раунда инструментов пустой финал -- конец
            told = told or result.rounds > 0
        empty_ok = required_done if required is not None else told
        if empty_ok:
            return None
        if self.role == "world":
            return EMPTY_NOTES["world"]
        if self.role == "summarizer" and mode != "summarize_chapter":
            return EMPTY_NOTES["summarize_scene"]
        return EMPTY_NOTES.get(mode, EMPTY_NOTES["narrator"])

    def run(self, ctx, user_input, executor, mode, *, world_text="", run_id=None):
        run_id = run_id or self.run_id
        result = MasterResult()
        req = self.builder.build(ctx, user_input, mode, world_text=world_text)
        req = self.with_note(req)
        # план контекста есть только у PromptBuilder нарратора (у world/summarizer builder другой);
        # фиксируется на первом build прогона, раунды инструментов его не пересчитывают
        plan = getattr(self.builder, "last_plan", None) if self.role == "narrator" else None
        if plan is not None and plan.overflow:
            result.report_tags.append("context_overflow")
        messages = list(req.messages)
        allowed = {d["name"] for d in tool_set(mode)}
        required = self.required_tool(ctx, mode)
        required_done = False
        while True:
            response = self.call(ctx, req, run_id, plan)
            result.stop_reason = response.stop_reason
            if response.stop_reason == "refusal":
                detail = f" ({response.stop_detail})" if response.stop_detail else ""
                raise TurnFailed("refusal", f"Модель отказалась отвечать{detail}.", ["refusal"])
            # пустые и пробельные текстовые блоки не считаются ответом
            texts = [b.text for b in response.content if isinstance(b, Text) and b.text.strip()]
            calls = [b for b in response.content if isinstance(b, ToolCall)]
            note = None
            if response.stop_reason == "max_tokens":
                note = "Ответ оборван по длине, повтори короче."
                if calls:
                    blocks = [
                        ToolResult(call_id=c.id, content=note, is_error=True) for c in calls
                    ]
                    blocks.append(Text(text=note))
                    messages.append(Message(role="assistant", content=response.content))
                    messages.append(Message(role="user", content=blocks))
                    self.count_invalid(result, "Модель не смогла дать корректный вызов.")
                    req = req.model_copy(update={"messages": list(messages)})
                    continue
            elif calls:
                result.rounds += 1
                if result.rounds > self.app_cfg.retry.max_tool_rounds:
                    raise TurnFailed("rounds", "Слишком много раундов вызова инструментов.")
                blocks, has_invalid, accepted = self.run_round(ctx, calls, executor, result, mode)
                if mode == "summarize_chapter" and accepted != allowed:
                    required_done = False
                elif required in accepted:
                    required_done = True
                if mode in SINGLE_SHOT_MODES and required_done and not has_invalid:
                    # выжимка (предыстория) принята -- завершающий вызов модели не нужен
                    result.texts += texts
                    return self.finish(result)
                all_free = all(c.name in FREE_TOOLS for c in calls)
                told = any(t.strip() for t in result.texts + texts)
                clean = not has_invalid and all_free and bool(accepted)
                done = required is None or required_done
                if self.role == "narrator" and clean and done and told:
                    # варианты предложены, рассказ уже есть -- завершающий вызов не нужен
                    result.texts += texts
                    return self.finish(result)
                if not has_invalid:
                    result.texts += texts
                messages.append(Message(role="assistant", content=response.content))
                messages.append(Message(role="user", content=blocks))
                if has_invalid:
                    self.count_invalid(result, "Модель не смогла дать корректный вызов.")
                req = req.model_copy(update={"messages": list(messages)})
                continue
            elif not texts:
                note = self.empty_note(mode, result, required, required_done)
            elif required is not None and not required_done:
                note = f"Нужно вызвать инструмент {required}. Вызови его."
            if note is None:
                result.texts += texts
                return self.finish(result)
            self.count_invalid(result, "Модель не смогла дать корректный ответ.")
            if response.content:
                messages.append(Message(role="assistant", content=response.content))
            messages.append(Message(role="user", content=[Text(text=note)]))
            req = req.model_copy(update={"messages": list(messages)})
