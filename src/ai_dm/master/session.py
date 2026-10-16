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

# приписка к ответам инструментов, когда offer_choices вызван без текста рассказа
CHOICES_NOTE = (
    "Рассказа этого хода игрок ещё не видел — размышления ему не показываются. "
    "Напиши сцену полностью текстом ответа; варианты уже предложены, не повторяй их."
)

# приписка, когда рассказ кончился вопросом или списком вариантов, а offer_choices не вызван
CHOICES_ASK = (
    "Ход кончился вопросом к игроку или списком вариантов, а `offer_choices` не вызван. "
    "Вызови `offer_choices` с этими вариантами (два или три коротких, по смыслу разных); "
    "текст сцены не повторяй."
)

# строка списка с маркером: -, —, •, *, 1. / 1)
MARKED_LINE = re.compile(r"^\s*(?:[-—•*]|\d+[.)])\s")

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


def ends_with_choice(narration) -> bool:
    # рассказ кончается вопросом к игроку или списком вариантов
    lines = [line.strip() for line in narration.split("\n") if line.strip()]
    if not lines:
        return False
    if lines[-1].endswith("?") or "|" in lines[-1]:
        return True
    block = []
    for line in reversed(narration.split("\n")):
        if not line.strip():
            if block:
                break
            continue
        block.append(line.strip())
    if len(block) < 2:
        return False
    if all(MARKED_LINE.match(line) for line in block):
        return True
    return all(len(line) <= 120 and line[-1] not in '.!…»"' for line in block)


# бой начинается по тексту рассказа
COMBAT_ANNOUNCED = re.compile(
    r"\b(?:начинается|начался|начн[её]тся|завязывается)\s+бой\b"
    r"|\bбой\s+(?:начинается|начался|начн[её]тся)\b|\bк бою!|\bв бой!",
    re.I,
)

# режимы, где проверяется offer_choices
CHOICE_MODES = ("explore", "combat_narrate")
# исходы, после которых герой жив и сцена идёт дальше
COMBAT_OVER = ("victory", "fled", "ended_by_master")


def announces_combat(narration) -> bool:
    # последний абзац рассказа объявляет начало боя
    paragraphs = [p for p in narration.split("\n\n") if p.strip()]
    return bool(paragraphs) and COMBAT_ANNOUNCED.search(paragraphs[-1]) is not None


def plain_text(text) -> str:
    # модель иногда заворачивает рассказ в блок ``` -- рамку рисует игра, ограды выбрасываются
    return "\n".join(line for line in text.split("\n") if not FENCE.match(line)).strip()


class TurnFailed(Exception):
    def __init__(self, reason, message, report_tags=None, detail=None):
        super().__init__(message)
        self.reason = reason
        self.report_tags = report_tags or []
        self.detail = detail


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
        self.accepted = set()


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
        note=None, policy=None,
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
        self.policy = policy or app_cfg.retry

    def required_tool(self, ctx, mode):
        required = REQUIRED_BY_MODE.get(mode)
        if mode == "world" and ctx.verdict_refs:
            required = "world_verdict"
        if mode == "combat_narrate":
            combat = ctx.bundle.session.active_combat
            if combat is not None and combat.outcome == "defeat_pending":
                required = "defeat_outcome"
        return required

    def choices_unseen(self, done, told, accepted):
        # варианты предложены, а рассказа игрок ещё не видел
        if self.role != "narrator" or told:
            return False
        return done and "offer_choices" in accepted

    def with_note(self, req):
        if self.note is None:
            return req
        first = req.messages[0]
        content = list(first.content) + [Text(text=self.note)]
        messages = [first.model_copy(update={"content": content})] + list(req.messages[1:])
        return req.model_copy(update={"messages": messages})

    def note_start(self, ctx, run_id, info, attempt):
        # строка в journal/attempts.log перед попыткой (если есть журнал)
        if self.journal is not None:
            self.journal.note_start(
                self.now().isoformat(), run_id, ctx.turn_seq, self.role, info.model, attempt
            )

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
                self.adapter, req, self.policy, self.sleeper, on_attempt,
                lambda attempt: self.note_start(ctx, run_id, info, attempt),
            )
        except RetriesExhausted as error:
            raise TurnFailed("network", str(error)) from error
        except LlmFatal as error:
            raise TurnFailed("fatal", str(error)) from error

    def run_call(self, ctx, call, executor, result, mode="explore"):
        allowed = {d["name"] for d in tool_set(mode)}
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
            outcome = self.run_call(ctx, call, executor, result, mode)
            if isinstance(outcome, Invalid):
                has_invalid = True
            else:
                result.decisions.append(outcome)
                if outcome.status in ("accepted", "clamped"):
                    accepted_names.add(call.name)
                    result.accepted.add(call.name)
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

    def choices_missing(self, ctx, result, mode):
        # рассказ кончился вопросом или списком, а offer_choices в ходу не принят
        # (не в бою или на ходу, которым бой закончился)
        if self.role != "narrator" or mode not in CHOICE_MODES:
            return False
        if "offer_choices" in result.accepted:
            return False
        combat = ctx.bundle.session.active_combat
        if mode == "explore":
            over = combat is None
        else:
            over = combat is not None and combat.outcome in COMBAT_OVER
        return over and ends_with_choice(result.narration)

    def tag_missing_combat(self, ctx, result, mode):
        # рассказ объявил бой, а start_combat в ходу не принят: только тег для репорта
        if self.role != "narrator" or mode != "explore":
            return
        if ctx.bundle.session.active_combat is not None or "start_combat" in result.accepted:
            return
        if announces_combat(result.narration):
            result.report_tags.append("combat_announced")

    def ask_choices(self, ctx, req, response, run_id, plan, executor, mode, result):
        # один служебный вызов: рассказ уже принят, нужен только offer_choices
        messages = list(req.messages)
        messages.append(Message(role="assistant", content=response.content))
        messages.append(Message(role="user", content=[Text(text=CHOICES_ASK)]))
        req = req.model_copy(update={"messages": messages})
        result.report_tags.append("choices_retry")
        try:
            answer = self.call(ctx, req, run_id, plan)
        except TurnFailed:
            return
        result.stop_reason = answer.stop_reason
        if answer.stop_reason == "refusal":
            return
        for call in answer.content:
            if isinstance(call, ToolCall) and call.name == "offer_choices":
                self.run_round(ctx, [call], executor, result, mode)
                return

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
                message = f"Модель отказалась отвечать{detail}."
                raise TurnFailed("refusal", message, ["refusal"], detail=response.stop_detail)
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
                if self.choices_unseen(done, told, accepted):
                    blocks.append(Text(text=CHOICES_NOTE))
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
                result = self.finish(result)
                if self.choices_missing(ctx, result, mode):
                    self.ask_choices(ctx, req, response, run_id, plan, executor, mode, result)
                self.tag_missing_combat(ctx, result, mode)
                return result
            self.count_invalid(result, "Модель не смогла дать корректный ответ.")
            if response.content:
                messages.append(Message(role="assistant", content=response.content))
            messages.append(Message(role="user", content=[Text(text=note)]))
            req = req.model_copy(update={"messages": list(messages)})
