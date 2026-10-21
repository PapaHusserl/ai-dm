# OpenAI (openai-python 3.35.1, Responses API): факты для Э10а (снимок 2026-10-20)

Источники: docs/research/openai-research.md, docs/plan-e10a.md (сверка моделей и цен 2026-10-20), установленный SDK
(`openai==3.35.1`, имена полей сверены по `model_fields` и исходникам). Живых вызовов не было — поведение API ниже
взято из документации, а не из прогона.

## Модели и цены (за 1M токенов)
- `gpt-6.1-sol`: вход 2.00, чтение кэша 0.10, запись кэша 2.50, выход 10.00; окно 1.05M, макс. вход 922K, вывод 128K;
  effort: low, medium (умолчание), high, xhigh, max; none/minimal нет. Chat Completions без tool calling → только Responses.
- `gpt-6-luna`: 0.10 / 0.01 / 0.125 / 0.50; effort none, low, medium (умолчание), high…
- Кэш неявный: префикс instructions + tools + input, минимум 1024 токена, TTL 30m; запись кэша — ставка токена, не надбавка.

## Вызов
```python
client = openai.OpenAI(api_key=..., max_retries=0, timeout=180)
response = client.responses.create(
    model=..., instructions="...", input=[...], tools=[...],
    max_output_tokens=16000, reasoning={"effort": "medium"},
    store=False, include=["reasoning.encrypted_content"],
)
```
- Сигнатура `responses.create` содержит `include`, `input`, `instructions`, `max_output_tokens`, `reasoning`, `store`,
  `tools`, `parallel_tool_calls`, `tool_choice`; `ResponseIncludable` содержит `"reasoning.encrypted_content"`.
- `parallel_tool_calls` и `tool_choice` не передаём (умолчания: параллельные вызовы разрешены, AUTO).
- `reasoning.summary` не запрашиваем (решение проектировщика 6).
- `max_output_tokens` ограничивает reasoning и текст вместе.

## input (элементы)
- user: `{"type": "message", "role": "user", "content": [{"type": "input_text", "text": ...}]}`.
- assistant без Opaque: `{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text": ...}]}`.
- вызов: `{"type": "function_call", "call_id", "name", "arguments": "<JSON-строка>"}`.
- результат: `{"type": "function_call_output", "call_id", "output": "<строка>"}`; ошибка — `output` = `{"error": ...}` JSON-строкой.
- tools: `{"type": "function", "name", "description", "parameters", "strict": bool}`.
- Между вызовами хода элементы ответа (reasoning с `encrypted_content`, function_call) возвращаются без изменений:
  у нас они лежат в `Opaque("openai", {"items": [...]})`, это `model_dump(mode="json", exclude_none=True)` каждого элемента `output`.
  Риск, проверить прогоном: с `store=False` элементы `message` несут `id`; если API отвергнет `id` несохранённых элементов,
  убирать `id` у message/function_call при отправке.

## Ответ (`Response`)
- Поля: `output`, `status` (`completed|failed|in_progress|cancelled|queued|incomplete`), `incomplete_details.reason`
  (`max_output_tokens|max_messages|content_filter|steered`), `error` (`code`, `message`; коды: `server_error`,
  `rate_limit_exceeded`, `invalid_prompt`, …), `model`, `usage`.
- Элементы `output`: `message` (`content`: части `output_text` с `text`, либо `refusal` с `refusal`), `function_call`
  (`call_id`, `name`, `arguments` — JSON-строка, `id`, `status`), `reasoning` (`summary`, `encrypted_content`).
- `response._request_id` — публичный атрибут верхнего объекта (из заголовка `x-request-id`), в `model_fields` его нет;
  у вложенных объектов не определён. Адаптер читает через `getattr(..., None)`.

## usage
- `ResponseUsage`: `input_tokens`, `input_tokens_details` (`cached_tokens`, `cache_write_tokens`), `output_tokens`,
  `output_tokens_details` (`reasoning_tokens`), `total_tokens`.
- `input_tokens` включает чтение и запись кэша; reasoning уже в `output_tokens`.
- В наш `Usage`: `input = input_tokens − cached − cache_write`, `cache_read = cached`, `cache_write = cache_write_tokens`,
  `output = output_tokens`, `cache_write_1h = 0` (иначе `cost_nano` и `api_tokens` считают запись дважды), хранения нет.

## Ошибки (исключения SDK)
- `openai.APIStatusError(message, *, response, body)`: атрибуты `status_code`, `response` (httpx2.Response, `headers`),
  `request_id`. `retry-after` читается из `error.response.headers` (`retry_after_of`).
- Сетевые: `APIConnectionError` ← `APIError` ← `OpenAIError`; `APITimeoutError` ← `APIConnectionError`. Имена совпадают
  с `llm/errors.py:NETWORK_NAMES`/`TIMEOUT_NAMES`, без кода статуса считаются временными.
- Зависимости SDK: `httpx2` (не `httpx`), `jiter`, `anyio`, `sniffio`, `typing-extensions`, `pydantic`.

## Схемы инструментов
- `strict: true` требует `additionalProperties: false` и `required` = все свойства; `protocol/schema.py:strictify` это даёт,
  в схемах только `type/enum/description/items`. NON_STRICT инструменты уходят `strict: false`.
- 33 функции в explore против рекомендации «< 20»: риск качества, не ошибка API.
