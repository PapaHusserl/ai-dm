# Общие помощники тестов слоя llm (этап 2, партия 3). Не фикстуры pytest, а обычные функции:
# тесты импортируют их напрямую (`from llm_kit import ...`). Живых вызовов и сети нет.
#
# КОНТРАКТ СЛОЯ llm (STAGE2-PLAN A3, ТЗ 2.0/2.2/11, llm-notes). Где план не даёт точных имён,
# они выбраны здесь -- это ТРЕБОВАНИЕ к реализации. llm не импортирует protocol/master/game/ui и
# движок (config можно); импорты SDK (anthropic, google) -- только внутри функций адаптеров
# (тесты на фейках; настоящие типы google.genai -- только где сказано).
#
#   ai_dm.llm.types  (Pydantic, extra="forbid", целые строгие, float нигде нет)
#     SystemBlock{text: str, cache: bool = False}
#     ToolSpec{name, description: str, input_schema: dict, strict: bool = True}
#       ToolSpec.model_validate(определение из protocol.schema.tool_set(mode)) работает как есть
#     блоки с полем type-литералом: Text{type="text", text}, ToolCall{type="tool_call", id, name,
#       input: dict}, ToolResult{type="tool_result", call_id, content: str, is_error=False},
#       Opaque{type="opaque", provider: str, raw: dict}; Block = union по type
#     Message{role: "user"|"assistant", content: list[Block]}
#     ChatRequest{role: str, model: str, system: list[SystemBlock] = [], tools: list[ToolSpec] = [],
#       messages: list[Message], max_tokens: int, effort: str | None = None}
#     Usage{input=0, output=0, cache_write=0, cache_read=0} (int)
#     (ревью партии 3: у ChatResponse есть обязательное поле model: str -- фактическая модель)
#     ChatResponse{content: list[Block], stop_reason: "end_turn"|"tool_use"|"max_tokens"|
#       "refusal"|"other", usage: Usage = Usage(), request_id: str | None = None}
#   ai_dm.llm.adapter: AdapterInfo{provider: str, model: str}; ModelAdapter (Protocol или ABC):
#       complete(req) -> ChatResponse, info() -> AdapterInfo
#   ai_dm.llm.errors: LlmError(Exception); LlmTransient(LlmError)(message, retry_after: int | None
#       = None) -- атрибут .retry_after; LlmFatal(LlmError); RetriesExhausted(LlmTransient) с
#       .attempts (число вызовов) и .last (последняя LlmTransient); MissingKey(LlmFatal)
#   ai_dm.llm.retry.call_with_retries(adapter, req, policy, sleeper, on_attempt=None)
#       -> ChatResponse
#       policy -- RetryConfig (AppConfig.retry): delays=[1,3,10]. LlmTransient -> sleeper(пауза),
#       повтор; пауз не больше len(delays); пауза = max(delays[i], retry_after), но не больше
#       max(delays); после исчерпания -- RetriesExhausted. LlmFatal и любые не-LlmError
#       исключения -- наружу сразу, без пауз. refusal / max_tokens -- обычные ответы.
#       on_attempt(attempt: int (с 1), response | None, error | None) -- после каждой попытки
#   ai_dm.llm.mock: ScriptedAdapter(steps: list[dict], provider="mock", model="mock"),
#       ScriptedAdapter.from_yaml(path), load_script(path) -> list[dict], ScriptError(Exception),
#       ScriptExhausted(ScriptError), ScriptMismatch(ScriptError) (не LlmError)
#       Формат шага (YAML: верхний ключ steps: [...]; неизвестный ключ / пустой шаг / error не
#       transient|fatal -> ValueError):
#         text: str; tool_calls: [{name, input: dict, id?}]; error: transient|fatal (+ message,
#         retry_after); stop: refusal|max_tokens; usage: {input, output, cache_write, cache_read};
#         when: {role?: str, last_message_contains?: str}
#       text и tool_calls можно вместе (Text, затем ToolCall); stop_reason: tool_calls -> tool_use,
#       stop -> он, иначе end_turn; request_id "mock-<N>" (N -- номер вызова с 1); id вызова без
#       id -- непустой, уникальный. Шаг расходуется вызовом (error тоже); шаг с неподошедшим when
#       -> ScriptMismatch и НЕ расходуется. Нет шагов -> ScriptExhausted (текст с ролью запроса).
#       .requests -- все полученные ChatRequest по порядку (и те, что кончились ошибкой).
#   ai_dm.llm.journal: request_fingerprint(req) -> sha256-hex канонического JSON запроса;
#       канон = json.dumps(obj, sort_keys=True, ensure_ascii=False, separators=(",", ":")).
#       Journal(saves_root, world_id, cfg: JournalConfig); .dir = saves_root/world_id/journal;
#       .record_call(*, call_id, turn_seq, attempt, role, provider, model, request, response=None,
#         cost_nano=0, error: LlmError | None = None, report_tags=(), duration_s=None) -> None
#         duration_s (сек, round 3 | None) и tokens_per_s = usage.output / duration_s (round 1;
#         None, если нет ответа, duration_s не задан или <= 0) -- поля записи, не в отпечатке
#       .mark_turn(turn_seq, status: "committed"|"aborted") -- ставит статус всем записям хода
#         без статуса (иначе ValueError); .read_records() -> list[dict] по порядку записи (gz тоже)
#       запись: call_id, world_id, turn_seq, attempt, role, provider, model, request, response
#         (ChatResponse.model_dump(mode="json") | None), usage (dict | нули), cost_nano, request_id,
#         stop_reason, error (None | {kind: transient|fatal, message, retry_after}), report_tags
#         (list), turn_status (None до mark_turn)
#       request = {system_sha256, tools_sha256, messages (dump), max_tokens, effort, fingerprint};
#         blobs/<sha256>.json = канонические байты system (список dump) / tools; одинаковые -- один
#       сегменты calls-001.jsonl ...; заполненный (>= segment_mb МБ) -> calls-NNN.jsonl.gz,
#       пишется следующий; сумма размеров calls-* <= max_mb МБ (старые сегменты удаляются)
#   ai_dm.llm.replay: ReplayAdapter(records), ReplayDivergence(Exception, не LlmError);
#       complete отдаёт response записей по порядку, сверяя request_fingerprint; запись с error
#       поднимает ту же LlmTransient/LlmFatal; расхождение или лишний вызов -> ReplayDivergence;
#       info().provider == "replay"
#   ai_dm.llm.cost: cost_nano(usage, price: ModelPrice) -> int = (in*P.input + out*P.output +
#       cw*P.cache_write + cr*P.cache_read) // 1000 (микро-$ за 1М токенов -> нано-$);
#       CostLedger(saves_root, world_id) -- экземпляр = сессия; файл root/world/meta/costs.jsonl;
#       .add(*, role, model, usage, cost_nano, day: date, aborted=False); .report(today: date) ->
#       объект с .session/.day/.world, у каждого .total_nano, .by_role, .by_model (dict[str, int]);
#       check_limit(cfg: CostLimitsConfig, spent_nano, limit_nano | None) -> "ok"|"warn"|"pause"
#   ai_dm.llm.keys: parse_dotenv(text) -> dict; load_key(provider, *, env, dotenv_path=None) ->
#       str | None; redact(text, secrets) -> str (секрет -> "***")
#   ai_dm.llm.anthropic_adapter.AnthropicAdapter(model, app_cfg, *, client_factory=None,
#       api_key=None); ai_dm.llm.gemini_adapter.GeminiAdapter(model, app_cfg, *, client=None,
#       sdk=None, api_key=None); ai_dm.llm.openai_adapter.OpenAIAdapter(model, app_cfg, *,
#       client_factory=None, api_key=None); ai_dm.llm.factory.make_adapter(provider,
#       model, app_cfg, *, env=None, dotenv_path=None) -- детали в соответствующих тестах.
from datetime import date

from ai_dm.config.app import load_settings
from ai_dm.llm.types import (
    ChatRequest,
    ChatResponse,
    Message,
    SystemBlock,
    Text,
    ToolCall,
    ToolResult,
    Usage,
)

OPUS = "claude-opus-5-5"
DAY = date(2026, 10, 3)


def app_cfg():
    # тесты на Opus: явный профиль anthropic (по умолчанию в конфиге Gemini)
    app = load_settings().app
    app.roles = app.profiles["anthropic"]
    return app


def user(text):
    return Message(role="user", content=[Text(text=text)])


def make_request(text="привет", role="narrator", model=OPUS, **kw):
    kw.setdefault("messages", [user(text)])
    kw.setdefault("max_tokens", 8000)
    kw.setdefault("system", [SystemBlock(text="правила мастера", cache=True)])
    return ChatRequest(role=role, model=model, **kw)


def make_response(
    text="ответ", usage=None, request_id="req-1", stop_reason="end_turn", model=OPUS,
):
    return ChatResponse(
        content=[Text(text=text)],
        stop_reason=stop_reason,
        usage=usage or Usage(input=10, output=5),
        request_id=request_id,
        model=model,
    )


def full_request():
    # запрос со всеми видами блоков
    return make_request(
        messages=[
            user("осмотрюсь"),
            Message(role="assistant", content=[
                Text(text="проверяю"),
                ToolCall(id="c1", name="skill_check", input={"skill": "perception"}),
            ]),
            Message(role="user", content=[
                ToolResult(call_id="c1", content='{"ok": true}', is_error=False),
            ]),
        ],
        effort="medium",
    )
