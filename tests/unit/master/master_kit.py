# Общие помощники тестов слоя master (этап 2, партия 4). Не фикстуры pytest, а обычные функции:
# тесты импортируют их напрямую (`from master_kit import ...`). Живых вызовов и сети нет.
#
# КОНТРАКТ СЛОЯ master (STAGE2-PLAN A4, ТЗ 1, 2.2, 11). Где план не даёт точных имён, они выбраны
# здесь -- это ТРЕБОВАНИЕ к реализации. master не импортирует game и ui.
#
#   ai_dm/master/prompts/narrator_rules.md -- пакетный файл
#     (importlib.resources.files("ai_dm.master") / "prompts" / "narrator_rules.md"), русский
#     текст правил: ИИ рассказывает, код считает; повествование после результатов инструментов;
#     категории сложности, а не числа;
#     unsupported_action; лечить без механики нельзя. Это текст system[0].
#
#   ai_dm.master.memory
#     context_limit(app_cfg, model) -> int         = app_cfg.context_windows[model] * 80 // 100
#     recent_window(memory, n) -> list[TurnRecord]   последние n из memory.recent_turns, порядок
#       от старых к новым (n <= 0 -> [])
#     trim_turns(turns, *, estimate, limit) -> list[TurnRecord]
#       estimate(turns) -> int (оценка запроса с этими ходами); пока estimate(turns) > limit --
#       выкидывается самый старый ход; оставшиеся -- хвост исходного списка. Строго больше:
#       estimate == limit не обрезает. Вход не меняется.
#
#   ai_dm.master.prompt.turn_data(turn: TurnRecord) -> dict   (ТМ #20, docs/plan-tm.md п.4)
#     прошлый ход для рассказчика: ровно {"turn_seq", "at_s", "player_input", "narration",
#     "outcomes"}; без requests, rolls, scene_id, money_delta_cp (модель копировала requests и
#     повторяла вызовы); outcomes -- копия списка (итог инструментов хода: log принятых и
#     «<type>: отклонено (<причина>)» отклонённых).
#     TurnRecord (state.scene): turn_seq, at_s, player_input, narration, requests: list[str],
#       rolls: list[str], scene_id: str = "", outcomes: list[str] = [], money_delta_cp: int = 0
#       (изменение денег героя за ход, медь; читает защита золота gold_repeated).
#
#   ai_dm.master.prompt.PromptBuilder(app_cfg, *, role="narrator", model=None)
#     model=None -> app_cfg.roles.<role>.model. Бюджет контекста (P3): master.context.plan по
#       длине запроса (без вызовов адаптера); итог -- builder.last_plan.
#     .build(ctx, user_input, mode, *, world_text="") -> ChatRequest
#       (ctx -- TurnContext; ctx.registry, ctx.bundle)
#       req.role == role; req.model == model; max_tokens и effort -- из роли конфига;
#       tools    == [ToolSpec.model_validate(d) for d in protocol.schema.tool_set(mode)] (порядок
#                   тот же: отсортированы по имени);
#       system   -- ровно 2 блока, оба cache=True: [0] правила (текст narrator_rules.md без
#                   изменений), [1] мир: world_id, tone, settings, world_text (текст
#                   мира, стабилен между ходами), id всех монстров и предметов
#                   реестра (registry.ids("monster"/"item")). В system нет времени, дат, UUID,
#                   состояния героя и ввода игрока;
#       messages -- ровно одно: user, один блок Text, текст = json.dumps(data, sort_keys=True,
#                   ensure_ascii=False); data -- словарь с ключами:
#         "time": {"date": clock.to_date(), "now_s": int}
#         "location": {"id", "name"} локации героя (hero.location_id) | None
#         "hero": {"name", "hp", "hp_max", "conditions": [id состояний], "inventory":
#                  [{"item_id", "qty"}], "gold_cp", "level", "xp"}
#         "scene_npcs": [{"id", "name", "attitude"}] -- NPC мира со статусом alive и
#                  location_id == локации героя, по id
#         "combat": None | {"id", "round", "outcome", "participants": [{"ref", "side", "zone_id",
#                  "status", "conditions"?}]} -- сводка session.active_combat; "conditions" --
#                  id состояний монстра/NPC, ключа нет, если состояний нет
#         "recent_turns": [turn_data(t)] -- trim_turns(recent_window(
#                  memory, app_cfg.master.recent_turns)), limit = context_limit(app_cfg, model),
#                  estimate = count_tokens от запроса с этими ходами; ключи записи -- только
#                  turn_seq, at_s, player_input, narration, outcomes (с ТМ #20, не model_dump)
#         "offered_choices": session.offered_choices;  "player_input": user_input
#
#   ai_dm.master.session
#     TurnFailed(Exception): .reason in {"invalid", "rounds", "refusal", "network", "fatal"},
#       .report_tags: list[str] (при refusal -- ["refusal"]), str(e) -- пояснение
#     MasterResult: .texts: list[str] (тексты Text-блоков ответов по порядку, финальный --
#       последний), .decisions: list[Decision] (не Invalid, по порядку), .requests: list
#       (разобранные запросы, по которым вызван executor), .report_tags: list[str] (report_tag
#       решений по порядку), .stop_reason (последнего ответа), .rounds: int (число раундов
#       инструментов), .invalid_count: int; .narration: str -- текст финального принятого ответа
#       (то, что показывает игра). .texts -- только из ПРИНЯТЫХ ответов (отбракованные по
#       пустоте / без обязательного / max_tokens сюда не попадают; текст раунда с отклонённым
#       вызовом -- принят). .accepted: set[str] -- имена принятых (accepted/clamped) инструментов
#       за весь ход. Приписка choices_retry (ask_choices): не в .texts, не в .rounds/.invalid_count.
#     MasterSession(adapter, app_cfg, *, journal=None, ledger=None, run_id="run-1",
#                   sleeper=time.sleep, now=None, builder=None, role="narrator")
#       run_id нужен и в .run(..., run_id=None): None -> из конструктора. call_id журнала =
#       f"{run_id}-{n}", счётчик n по run_id: уникален и при нескольких run() на одной сессии.
#       Все вызовы мастера одного прогона хода (classify / npc_choice / narrate) -- один run_id.
#       now -- callable() -> datetime (по умолчанию datetime.now(UTC)); ts журнала = isoformat,
#       day учёта = now().date(); builder по умолчанию PromptBuilder(app_cfg, role=role).
#     .run(ctx, user_input, executor, mode, *, run_id=None, world_text="") -> MasterResult
#       world_text уходит в builder.build(..., world_text=world_text).
#       executor(ctx, request) -> Decision | Invalid (боевой -- protocol.apply). Запрос
#       строится builder.build(ctx, user_input, mode); дальше цикл:
#         complete через call_with_retries(adapter, req, app_cfg.retry, sleeper, on_attempt);
#         tool_use: каждый ToolCall: вне tool_set(mode) -> Invalid(not_available_in_mode, текст
#           со словами «в этом режиме недоступно»); call.input.get("type") != call.name ->
#           Invalid(invalid_request) до parse_request (и при strict_tools=false); не разбирается
#           parse_request -> Invalid; иначе
#           executor. Исход -> render_tool_result. Следующий запрос = прошлый + assistant-сообщение
#           (content ответа без изменений, в том числе Opaque) + ОДНО user-сообщение со всеми
#           ToolResult в порядке вызовов (call_id вызова). Прежние сообщения не правятся.
#         end_turn без обязательного инструмента -> невалидный ответ: assistant (как есть) + user
#           Text с пояснением (в тексте имя инструмента); max_tokens -> то же, пояснение со
#           словом «короче»; Invalid от исполнителя -> tool_result is_error=True (бюджет тоже);
#         бюджет: невалидных (ответов с Invalid / без обязательного / max_tokens) не больше
#           app_cfg.retry.invalid_retries; сверх -- TurnFailed("invalid"). rejected/clamped
#           Decision бюджет не тратит. Раундов tool_use не больше retry.max_tool_rounds (8);
#           девятый -- TurnFailed("rounds") (8 раундов и затем текст -- успех).
#         refusal -> TurnFailed("refusal", report_tags ["refusal"]); RetriesExhausted ->
#           TurnFailed("network"); LlmFatal -> TurnFailed("fatal") (без повторов и sleeper).
#       Обязательные инструменты: combat_classify -- player_action; npc_choice -- npc_action;
#         combat_narrate -- defeat_outcome, если session.active_combat.outcome == "defeat_pending";
#         explore -- нет. Кэш (C1): точек кэша на сообщениях раунда нет (Message.cache=False везде),
#         cache только у двух system-блоков.
#         «Обязательный вызван» = Decision accepted/clamped (не rejected/Invalid).
#       Журнал: каждая попытка complete (и неудачная) -- journal.record_call(call_id уникален,
#         run_id, ts, turn_seq = session.turn_seq, attempt (из on_attempt), role, provider/model
#         ответа или адаптера, request, response/error, cost_nano, report_tags=[]);
#         стоимость ответа -- ledger.add(call_id той же записи, role, model, usage, cost_nano =
#         llm.cost.cost_nano(usage, app_cfg.prices[model]), day).
#         duration_s записи = self.now() в on_attempt - self.now() в on_start той же попытки
#         (одна метка старта идёт и в attempts.log); now() вызывается по разу на старт и на конец.
import sys
from datetime import UTC, datetime
from pathlib import Path

# рядом лежат kit-ы соседних слоёв: каталог теста в sys.path один, добавляем нужные явно
TESTS_UNIT = Path(__file__).resolve().parents[1]
for sub in ("protocol", "llm"):
    if str(TESTS_UNIT / sub) not in sys.path:
        sys.path.insert(0, str(TESTS_UNIT / sub))

from llm_kit import app_cfg, user  # noqa: E402, F401
from protocol_kit import (  # noqa: E402, F401
    ScriptedRng,
    combat_request,
    make_bundle,
    make_ctx,
    req,
)

from ai_dm.llm.cost import CostLedger  # noqa: E402
from ai_dm.llm.journal import Journal  # noqa: E402
from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402
from ai_dm.protocol.apply import apply  # noqa: E402
from ai_dm.protocol.decision import Decision  # noqa: E402
from ai_dm.state.scene import TurnRecord  # noqa: E402

NOW = datetime(2026, 10, 3, 12, 0, tzinfo=UTC)


class Recorder:
    # обёртка адаптера: хранит глубокие копии запросов, чтобы поздние правки списков не искажали
    def __init__(self, inner):
        self.inner = inner
        self.requests = []

    def complete(self, request):
        self.requests.append(request.model_copy(deep=True))
        return self.inner.complete(request)

    def info(self):
        return self.inner.info()


def scripted(steps):
    return Recorder(ScriptedAdapter(steps, provider="anthropic", model="claude-opus-5-5"))


def text_step(text="Рассказ."):
    return {"text": text}


def flag_call(name, call_id=None):
    call = {"name": "set_flag", "input": {"type": "set_flag", "name": name, "value": "true"}}
    if call_id:
        call["id"] = call_id
    return call


def tools_step(*calls, text=None, **extra):
    step = {"tool_calls": list(calls)}
    if text:
        step["text"] = text
    step.update(extra)
    return step


def player_action_call(call_id="pa-1"):
    return {
        "id": call_id, "name": "player_action",
        "input": {"type": "player_action", "steps": ["attack:longsword:g1"]},
    }


def accept_all(ctx, request):
    # исполнитель-заглушка: всё принимает, ничего не меняет
    return Decision(status="accepted", result={"type": request.type})


def reject_all(ctx, request):
    return Decision(
        status="rejected", reason="нельзя", signal_to_master="Так нельзя.", report_tag=None
    )


def make_session(adapter, tmp_path, app=None, **kwargs):
    from ai_dm.master.session import MasterSession

    app = app or app_cfg()
    sleeps = []
    journal = Journal(tmp_path, "w1", app.journal)
    ledger = CostLedger(tmp_path, "w1")
    session = MasterSession(
        adapter, app, journal=journal, ledger=ledger, run_id=kwargs.pop("run_id", "run-1"),
        sleeper=sleeps.append, now=lambda: NOW, **kwargs,
    )
    return session, journal, ledger, sleeps


def combat_ctx(registry, cfg, mode="combat_classify", outcome=None, **kwargs):
    ctx = make_ctx(registry, cfg, mode=mode, **kwargs)
    apply(ctx, combat_request())
    if outcome is not None:
        ctx.bundle.session.active_combat.outcome = outcome
    return ctx


def turn_record(n, narration="Ход."):
    return TurnRecord(
        turn_seq=n, at_s=n * 60, player_input=f"ввод {n}", narration=f"{narration} {n}",
        requests=[], rolls=[],
    )
