# Claude API: факты для этапа 2 (снимок 2026-10-03)

Источник: справка claude-api (Anthropic). При реализации — сверяться с официальной документацией SDK, не с памятью.

## SDK и клиент
- Пакет `anthropic` (1.x, на `httpx2`). `anthropic.Anthropic()` берёт ключ из `ANTHROPIC_API_KEY` (или профиля `ant auth login`).
- Таймаут по умолчанию 10 мин; SDK сам ретраит 408/409/429/5xx и сетевые ошибки (`max_retries`, по умолчанию 2).
  Политика ТЗ 2.2 (3 повтора 1→3→10 с, затем откат хода) → у клиента `max_retries=0`, повторы — наши, чтобы политика была одна.
- Типизированные ошибки (ловить цепочкой от частного к общему): `BadRequestError`, `AuthenticationError`,
  `PermissionDeniedError`, `NotFoundError`, `RateLimitError` (заголовок `retry-after`), `APIStatusError` (>=500 — ретраить),
  `APIConnectionError`, `APITimeoutError`. 4xx кроме 429 — не ретраить.
- `response._request_id` — логировать в журнал вызовов и репорты.

## Модели и цены ($ за 1M токенов, вход / выход)
| Модель | id | Цена | Заметки |
|---|---|---|---|
| Claude Opus 5.5 | `claude-opus-5-5` | 4 / 20, чтение кэша 0.20 | по умолчанию; контекст 1M |
| Claude Sonnet 5.5 | `claude-sonnet-5-5` | 2 / 10, чтение кэша 0.20 | контекст 1M |
| Claude Haiku 4.5 | `claude-haiku-4-5` | 1 / 5 | контекст 200K |
id использовать ровно так, без суффиксов дат. Таблица цен — в конфиге (ТЗ 2.0), не в коде.

## Важные особенности Opus 5.5 / Sonnet 5.5
- **Форсированный `tool_choice` (`any` / `tool`) → 400.** Только `auto` + инструкция в промпте + `strict: true` на инструменте,
  либо structured outputs.
- **Префилл ответа ассистента → 400.** Формат — через structured outputs или инструкции.
- **Мышление:** у Opus 5.5 всегда включено (`thinking` не передавать или `{"type": "adaptive"}`; `disabled` → 400);
  глубина — `output_config: {"effort": "low"|"medium"|"high"|"xhigh"|"max"}`, у Opus 5.5 по умолчанию `medium`.
  В adapter `thinking` задаётся конфигом `[llm] thinking` (только роль narrator): `{"type": "adaptive", "display": thinking_display}`; `disabled` не поддерживается (Opus 5.5 → 400); claude-haiku-4* — без параметра. Приём `display` не проверен живым вызовом.
  У Sonnet 5.5 выключить мышление — только `{"type": "between_tools"}`. Haiku 4.5 — старый режим `budget_tokens`.
- **`stop_reason`:** `end_turn`, `max_tokens`, `tool_use`, `pause_turn`, `refusal` (+ `stop_details.category`). Проверять
  `stop_reason` до чтения `content`. `refusal` = отказ модели (ТЗ 2.2 → выбор игрока + авто-репорт `refusal`).
- **Серверный fallback при отказе** (Claude API): beta `server-side-fallback-2026-07-01` + `fallbacks: "default"`.
  По ТЗ 2.2 автоматической смены модели нет — НЕ включать без решения проектировщика (вопрос в план этапа 2).
- **Сохранённое мышление (preserved thinking):** блоки мышления привязаны к модели и разговору; правка ранних ходов
  истории их инвалидирует. Если каждый вызов собирается заново из состояния (без переигрывания длинной истории) —
  проблемы нет. Не редактировать отправленную историю «задним числом».

## Tool use (протокол «мастер → движок», ТЗ 2.1)
- Инструмент: `{"name", "description", "input_schema": JSON Schema}`; `strict: true` (поле инструмента, не `tool_choice`) +
  `additionalProperties: false` + `required` → `tool_use.input` гарантированно валиден по схеме.
- В одном ответе может быть несколько `tool_use` (параллельно); все `tool_result` возвращать **одним** user-сообщением;
  ошибка инструмента — `tool_result` с `is_error: true`.
- Входы инструментов парсить как JSON (не сравнивать строки).
- Pydantic-модели запросов → JSON Schema (`model_json_schema()`), валидация ответа — нашим Pydantic поверх `strict`.

## Лимиты strict tool use / structured outputs (официальная документация, 2026-10-03)
На запрос с `strict: true` или `output_config.format`:
| Лимит | Значение |
|---|---|
| strict-инструментов в запросе | **20** |
| необязательных параметров (сумма по всем схемам) | **24** |
| параметров с union-типом (`anyOf` или массив типов) | **16** |
- Не поддерживаются: рекурсивные схемы, сложные типы внутри enum, внешний `$ref`, `minimum`/`maximum`/`multipleOf`,
  `minLength`/`maxLength`, ограничения массивов кроме `minItems` 0/1, `additionalProperties` ≠ `false`.
- `anyOf` поддерживается, но «особенно дорог» (экспоненциальная стоимость компиляции).
- Превышение внутренней сложности → `400 "Schema is too complex for compilation"` (даже если таблица соблюдена);
  таймаут компиляции 180 с.

## Structured outputs
- `output_config: {"format": {...}}` на `messages.create()` (старый `output_format` устарел) или `client.messages.parse()`
  с валидацией по схеме. Альтернатива tool use для «один JSON-ответ».

## Кэширование промптов (ТЗ 2.0)
- Кэш — совпадение префикса; порядок рендера `tools` → `system` → `messages`. Любой изменившийся байт инвалидирует всё после.
- Стабильное вперёд: правила протокола, список инструментов (детерминированный порядок), мир/истины. Переменное (состояние,
  последние ходы, время) — после последней точки `cache_control`.
- `cache_control: {"type": "ephemeral"}` (TTL 5 мин; `"ttl": "1h"` — час, проверено по типам SDK: `ttl: Literal["5m", "1h"]`; запись 1h ≈ 2× входа); максимум 4 точки; минимальный префикс 512–4096 токенов.
- Невидимые инвалидаторы: время/UUID в system, несортированный `json.dumps`, меняющийся набор инструментов.
- Mid-conversation system messages (`{"role": "system"}` в `messages`) — у Opus 5.5 / Sonnet 5.5 есть; не трогают кэш префикса.

## Учёт токенов и стоимости (ТЗ 2.0)
- `response.usage`: `input_tokens` (некэшированный вход), `output_tokens`, `cache_creation_input_tokens` (~1.25× цены входа),
  `cache_read_input_tokens` (~0.1×). Стоимость = сумма по полям × цены модели из конфига.
- Разбивка записи кэша по TTL: `usage.cache_creation.ephemeral_5m_input_tokens` / `ephemeral_1h_input_tokens` (проверено по типам SDK, `CacheCreation`); адаптер кладёт их в `Usage.cache_write` / `cache_write_1h`. Порядок точек: длинный TTL раньше короткого (system 1h, затем сообщение 5m).
- `client.messages.count_tokens(...)` — оценка до запроса (бюджет контекста ТЗ 11).

## Прочее
- Длинные ответы — стриминг (`messages.stream(...)` + `get_final_message()`); без стриминга `max_tokens` ~16000.
- Gemini (`google-genai`) — фактов в этой справке нет; адаптер проектировать за общим интерфейсом и сверить SDK при реализации.

## Правки партии 3 (ревью)
- `retry_after_of` возвращает `float` секунд: сначала `retry-after-ms` (мс / 1000), затем `retry-after`.
- 408 -> `LlmTransient` (как 429 и >= 500). `ChatResponse.model` = `response.model` (фактическая модель).

## Живой прогон 2026-10-03: «compiled grammar is too large»
16 strict-инструментов в explore (start_combat, npc_create, npc_update и др.) → 400
`The compiled grammar is too large… Simplify your tool schemas or reduce the number of strict tools`
(request_id req_011CffR44i9CNbiNtFz1ANsv). Табличные лимиты (20/16/24) при этом соблюдались. Исправление: в explore strict
только у малых частых инструментов (`protocol/schema.STRICT_IN_EXPLORE`), остальные — `strict: false` + Pydantic.
