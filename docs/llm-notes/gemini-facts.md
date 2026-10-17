# Gemini (google-genai, Python): факты для этапа 2 (снимок 2026-10-03)

Источники: ai.google.dev/gemini-api/docs (function-calling, models, pricing), googleapis.github.io/python-genai.
Собрано оркестратором; при реализации — сверять с установленной версией SDK (`uv add google-genai`, `help(...)`).

## API: используем `generate_content` (классический), не Interactions
- В SDK есть новый Interactions API (`client.interactions.create`, шаги `function_call`/`function_result`), но его
  Python-документация неполная (system instruction, usage, отказы, stateless — не описаны). Для этапа 2 берём
  **`client.models.generate_content`** — он документирован и stateless (история передаётся целиком).
- Клиент: `from google import genai; client = genai.Client()` — ключ из `GEMINI_API_KEY`.

## Вызов
```python
from google.genai import types
response = client.models.generate_content(
    model="gemini-3.8-flash",
    contents=[...],                                  # история: types.Content(role="user"|"model", parts=[...])
    config=types.GenerateContentConfig(
        system_instruction="...",
        tools=[types.Tool(function_declarations=[...])],   # объявления: name, description, parameters (JSON Schema)
        tool_config=types.ToolConfig(function_calling_config=types.FunctionCallingConfig(mode="AUTO")),
        automatic_function_calling=types.AutomaticFunctionCallingConfig(disable=True),   # ОБЯЗАТЕЛЬНО: функции исполняет движок
        max_output_tokens=8000,
    ),
)
```
- Точные имена полей `ToolConfig`/`FunctionCallingConfig`/`thinking_config` — сверить с SDK (документация подтверждает
  `GenerateContentConfig(tools=..., automatic_function_calling=...)`; режимы AUTO/ANY/NONE описаны для function calling).
- Режим: **AUTO** (как у Claude). ANY у Gemini доступен, но протокол одинаков для всех провайдеров — используем AUTO.

## Ответ и инструменты
- Вызовы функций: `response.function_calls` → список `types.FunctionCall` (`.name`, `.args` — dict, `.id` если есть).
- Возврат результата: `types.Part.from_function_response(name=..., response={"result": ...})` в следующем `contents`
  (роль — по документации SDK; сверить: `user` или `tool`).
- Ответ модели (`response.candidates[0].content`) возвращать в историю **без изменений** (части мышления / подписи —
  наш `Opaque`), чтобы не ломать продолжение хода.
- Причина остановки: `response.candidates[0].finish_reason`; блок по безопасности — `response.prompt_feedback.block_reason`
  или `finish_reason == SAFETY` → наш `stop_reason = "refusal"`. Сверить перечень значений в SDK.

## Учёт токенов
`response.usage_metadata`: `prompt_token_count` (вход), `candidates_token_count` (выход), `cached_content_token_count`
(чтение кэша), `thoughts_token_count` (мышление — тарифицируется как выход; добавлять к выходу в учёте стоимости).

## Ошибки
`google.genai.errors.APIError` (`.code`, `.message`); подклассы `ClientError` (4xx) / `ServerError` (5xx) — сверить.
Маппинг: 429 и ≥ 500 и сетевые → `LlmTransient`; прочие 4xx → `LlmFatal`.

## Схемы функций
Параметры — подмножество JSON Schema (OpenAPI). Наши strict-схемы без union/`$ref` и без числовых/строковых ограничений
подходят; `additionalProperties` и `strict` — поля Anthropic: адаптер Gemini их **снимает**.

## Модели и цены ($ за 1M, платный тариф, на 2026-10-03)
| Роль | Модель | Вход | Выход | Чтение кэша |
|---|---|---|---|---|
| narrator (сильная) | `gemini-3.8-flash` | 0.75 (до 31.12.2026; с 01.01.2027 — 1.50) | 3.75 (→ 7.50) | 0.075 (→ 0.15) |
| world / summarizer (дешёвая) | `gemini-3.5-flash-lite` | 0.30 | 2.50 | 0.03 |
| альтернатива (Pro) | `gemini-3.1-pro-preview` (id сверить) | 2.00 (≤200k) | 12.00 (≤200k) | 0.20 |
Окна контекста в справке не указаны — для бюджета использовать консервативно 1 000 000 у Flash и сверить через SDK
(`client.models.get(...)`). Цены зависят от даты — в конфиге хранить текущие и пометить «пересмотреть с 2027-01-01».

## Сверено с SDK google-genai 2.28.0 (и anthropic 1.11.0), партия 3 этапа 2
Проверено `help`/интроспекцией установленных пакетов, сеть не вызывалась.

Подтверждено как в справке:
- `types.GenerateContentConfig` имеет `system_instruction`, `tools`, `tool_config`, `automatic_function_calling`,
  `max_output_tokens`, `thinking_config`; `types.ToolConfig(function_calling_config=...)`;
  `types.FunctionCallingConfig(mode=...)`, значения режима: `MODE_UNSPECIFIED`, `AUTO`, `ANY`, `NONE`, `VALIDATED`
  (строка `"AUTO"` принимается); `types.AutomaticFunctionCallingConfig(disable=...)`.
- `types.Part.from_function_response(*, name, response, parts=None)`; `types.FunctionDeclaration(name, description,
  parameters, ...)` (есть и `parameters_json_schema`); `types.FunctionCall(id, args, name, ...)`.
- `response.function_calls` (property, только первый кандидат), `response.response_id`, `response.prompt_feedback.block_reason`,
  `response.candidates[0].finish_reason` (enum, `.name`).
- `response.usage_metadata` -- `GenerateContentResponseUsageMetadata` с `prompt_token_count`, `cached_content_token_count`,
  `candidates_token_count`, `thoughts_token_count`, `tool_use_prompt_token_count` (не учитываем).
  Внимание: у `types.UsageMetadata` (live API) поле называется `response_token_count` -- это другой класс.
- `google.genai.errors.APIError(code, response_json, response)`: атрибуты `.code`, `.message`, `.status`, `.details`;
  подклассы `ClientError` (4xx), `ServerError` (5xx).

Расхождения / уточнения справки:
- Роль `Content` для результата функции -- адаптер шлёт `"user"` (в SDK роль свободная строка; `tool` не проверялась на API).
- Сетевые ошибки (таймаут, обрыв) -- исключения httpx, а не `APIError`, `.code` у них нет: адаптер различает по имени класса
  (`ConnectError`, `ConnectTimeout`, `ReadTimeout`, `TimeoutException`, `NetworkError`, в т.ч. по предкам) -> `LlmTransient`.
- `FinishReason` шире, чем STOP/MAX_TOKENS/SAFETY: `RECITATION`, `LANGUAGE`, `OTHER`, `BLOCKLIST`, `PROHIBITED_CONTENT`,
  `SPII`, `MALFORMED_FUNCTION_CALL`, `UNEXPECTED_TOOL_CALL`, `TOO_MANY_TOOL_CALLS` и др. Адаптер даёт
  `refusal` для SAFETY, PROHIBITED_CONTENT, BLOCKLIST, SPII, RECITATION и для блока промпта (`BlockedReason`: `SAFETY`, `OTHER`, `BLOCKLIST`, `PROHIBITED_CONTENT`,
  `IMAGE_SAFETY`, `MODEL_ARMOR`, `JAILBREAK`; `BLOCKED_REASON_UNSPECIFIED` блоком не считается); остальное (в т.ч. MALFORMED_FUNCTION_CALL) -> `other`.
- Части ответа (`Part`) содержат `thought_signature: bytes`. Для журнала и `Opaque.raw` части сохраняются как
  `part.model_dump(mode="json", exclude_none=True)` (bytes -> base64); `types.Part(**dict)` обратно восстанавливает bytes
  (`val_json_bytes="base64"`). Без `mode="json"` журнал не сериализуется.
- Модели SDK (`Part`, `UsageMetadata` и др.) -- `extra="forbid"`, поля camelCase принимают и snake_case (`populate_by_name`).
- `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=<мс>))`: адаптер ставит `retry.timeout_s * 1000`.
- `count_tokens(*, model, contents, config=None)` -- system/tools адаптер не передаёт: к `total_tokens` прибавляется
  грубая оценка `len(json(system + tools)) // 4`. Ограничение: оценка приблизительная, для бюджета, не для биллинга.
- `types.FunctionResponse(id, name, response, ...)`: если `call_id` пришёл от API (не синтезированный `gemini-...`),
  адаптер возвращает его в `FunctionResponse.id`. Риск: поведение API при наличии/отсутствии `id` вживую не проверено;
  если ответ с `id` отвергается -- вернуться к `Part.from_function_response` без `id`.
- Ошибки: 408 (как и 429, >= 500) -> `LlmTransient`; сетевые также `TransportError`, `RemoteProtocolError`,
  `ReadError`, `WriteError`. `ChatResponse.model` = `response.model_version` или запрошенная модель.
- `llm.refusal_fallback` действует только для Anthropic (серверный fallback модели); для Gemini флаг ничего не делает.
- Цены и окна Gemini в конфиге: ключи моделей с точками в TOML берутся в кавычки (`[prices."gemini-3.8-flash"]`).

anthropic 1.11.0:
- Имена ошибок как в справке: `APIStatusError` (`.status_code`, `.response.headers`), `RateLimitError`,
  `InternalServerError`, `APIConnectionError`, `APITimeoutError(APIConnectionError)`; сам SDK на `httpx2`, поэтому
  `httpx.ConnectError` из него не приходит.
- `Anthropic(api_key=, max_retries=, timeout=)`, `with_options` есть; `messages.create` принимает `output_config`, `thinking`,
  `tool_choice`; `beta.messages.create` принимает `betas` и `fallbacks`; `messages.count_tokens` -- без `max_tokens`.

## Явный кэш (stage2-live-1, раздел 6; сверено 2026-10-03, google-genai 2.28.0)
Источники: ai.google.dev/gemini-api/docs/generate-content/caching (Explicit caching, Additional considerations),
ai.google.dev/api/caching (cachedContents.create, поля CachedContent), ai.google.dev/gemini-api/docs/pricing (Context caching price);
SDK -- интроспекция установленного пакета, сеть/API-вызовы с ключом не делались (страницы документации читались без ключа).

- Создание: `client.caches.create(*, model, config=types.CreateCachedContentConfig(...)) -> types.CachedContent`.
  Поля `CreateCachedContentConfig`: `ttl` (строка секунд, напр. `"3600s"`), `expire_time`, `display_name`, `contents`,
  `system_instruction`, `tools`, `tool_config`, `kms_key_name`. `contents` необязателен -- кэшируем только system + tools (+ tool_config).
- `CachedContent`: `name` (`cachedContents/...`), `model`, `create_time`, `expire_time`, `usage_metadata`;
  `usage_metadata.total_token_count` -- число токенов кэша (документация: оно возвращается в create/get/list).
- Использование: `GenerateContentConfig(cached_content=<name>)`. Кэш -- префикс промпта; токены кэша входят в `prompt_token_count`,
  в ответе `usage_metadata.cached_content_token_count` (как и при неявном кэше).
- Ограничение: `tools` и `tool_config` в API кэша -- "Input only. Immutable" (api/caching, `toolConfig`: "shared for all tools"), поэтому
  system_instruction, tools и tool_config кэшируются целиком и в запрос с `cached_content` не передаются (иначе API отвечает ошибкой --
  это известное поведение API; явной фразы на текущих страницах не найдено, вживую не проверялось). Адаптер в таком запросе их не шлёт.
- У кэша меняется только TTL/expire_time (`caches.update`); содержимое неизменно -- новый набор system/tools = новый кэш.
- Минимальный размер кэша: 4096 токенов для Gemini 3.8 Flash, 3.7/3.6/3.5 Flash и 3.1 Pro Preview (2048 для 2.5 Flash/Pro; в таблице
  для `gemini-3.5-flash-lite` строки нет -- сверить). Максимум -- как у модели. Меньше минимума -- ошибка создания (4xx), адаптер идёт без кэша.
- TTL по умолчанию 1 час; границ TTL нет. Кэш истёк/удалён -- запрос с этим именем даёт ошибку клиента (ожидаем 403/404; вживую не
  проверялось): адаптер пересоздаёт кэш один раз и повторяет запрос.
- Биллинг: токены кэша по сниженной цене при использовании в запросах + хранение за время TTL (токены × часы); создание кэша отдельной
  строкой в справке не тарифицируется -- по решению проектировщика (X2) учитываем как вход по цене `input`.
- Цены хранения (платный тариф, $ за 1M токенов в час): `gemini-3.8-flash` 0.50 до 31.12.2026, с 01.01.2027 -- 1.00;
  `gemini-3.5-flash-lite` 1.00. Чтение кэша: 3.8 Flash 0.075 (с 2027 -- 0.15), 3.5 Flash-Lite 0.03. В конфиге: `prices.<модель>.cache_storage_hour`
  (микро-доллары за 1M токенов в час): 500000 и 1000000; пересмотреть 3.8 Flash с 2027-01-01.
- Учёт в адаптере: `Usage.cache_write` = токены созданного кэша (цена `cache_write` = `input`), `Usage.cache_storage_min` = токены × минуты
  TTL (цена `cache_storage_hour` // 60), начисляются в ответе, следующем за созданием (если создание было, а запрос упал -- в следующем успешном).

## Сеть и модели (Т60; docs/research/gemini-503-research.md, docs/plan-t60.md)
- IPv4-транспорт: `genai.Client(http_options=HttpOptions(client_args={"transport": httpx.HTTPTransport(local_address="0.0.0.0")}))` --
  сокет только по IPv4. Включается `[llm] gemini_ipv4` (по умолчанию true). Свой транспорт отключает прокси/`SSL_CERT_FILE` из окружения
  httpx -- при `false` поведение прежнее. Async-клиент не используется, `async_client_args` не задаём.
- Таймаут: `HttpOptions(timeout=<мс>)` -- httpx-таймаут на каждую фазу (connect, write, read, pool), а не на весь запрос; `[retry] gemini_timeout_s = 90`.
  Отдельного connect-таймаута нет.
- 504 DEADLINE_EXCEEDED -- «медленный» сбой (как и таймаут чтения): ответ ждали ~90 с; адаптер ставит `LlmTransient.timeout`, при `retry_timeouts = false` повтора нет, сразу меню ошибки (19ф).
- `gemini-4-argon`: явного кэша нет (`cache_storage_hour = 0`), `caches.create` отвечает 4xx -- адаптер идёт без кэша (`caches[key] = None`).
  Цена 4.0/20.0 за 1M, чтение кэша 0.2.
- `gemini-3-flash-preview`: 0.5/3.0, чтение кэша 0.05, хранение 1.0; окна моделей цепочки -- 1000000 (консервативно, сверить).
- 5xx при `create_cache` не обрабатываем отдельно (как и прочие сбои создания -- запрос без кэша).
