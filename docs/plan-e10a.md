# Э10а. OpenAI как третий провайдер (BACKLOG 65)

## Суть

Третий адаптер слоя `llm` — OpenAI через Responses API (`openai_adapter.py`), профиль `profiles.openai` (narrator
`gpt-6.1-sol`, дешёвые роли `gpt-6-luna`), цены и окна в `app_defaults.toml`, ключ `OPENAI_API_KEY`, `--provider openai`,
`/model narrator openai:gpt-6.1-sol`. Протокол инструментов, журнал, replay, учёт стоимости и цепочка моделей — без изменений:
всё это уже абстрагировано (`ModelAdapter`, `ChatRequest`/`ChatResponse`, `Opaque`, `Usage`, `AdapterInfo`). Ресёрч —
docs/research/openai-research.md (2026-10-15); модели и цены сверены 2026-10-20 (раздел «Сверка» ниже).

## Решения

- 2026-10-20 (NOTES.md «2026-10-20 (BACKLOG 65, OpenAI)»): Э10а снят с ⛔ — «gemini очень плохо»; следующая партия после
  коммита 96а П1, перед 96а П2. Цена хода ≈ 2,5× gemini-3.8-flash принята к сведению.
- Проектировщик, 2026-10-20 (вопросы плана папы-кабана; груминг пропущен по просьбе проектировщика):
  1. Зависимость `openai>=3.35` — согласие дано.
  2. Провайдер по умолчанию — Gemini (как советовал папа); OpenAI — через `/model` / свой config.toml.
  3. `effort` рассказчика gpt-6.1-sol — `medium` (≈ $0,09/ход).
  4. `openai:gpt-6.1-sol` — в `narrator_chain` запасным.
  5. Роль `import` в профиле openai — `gpt-6.1-sol` low.
  6. `reasoning.summary` в журнал — не запрашивать (MVP).
  7. Смету кабана-тестя по плану не делать (проектировщик, 2026-10-20).
  8. Уточнение к 4 (вопрос свекрови, 2026-10-20): `openai:gpt-6.1-sol` в `narrator_chain` — вторым, сразу после
     `gemini:gemini-3.8-flash`.

## План (папа-кабан, 2026-10-20)

Контур: вне msa; режим: встроить. Груминг пропущен по просьбе проектировщика — неготовность не нашёл, развилки — в «Открытых
вопросах» (первый блокирующий: зависимость).

**Задача / проект:** третий провайдер OpenAI (Responses API) в слой `llm` ai-dm в стиле `GeminiAdapter`/`AnthropicAdapter`.

**Правило:** было `KEY_VARS = {"anthropic": "ANTHROPIC_API_KEY", "gemini": "GEMINI_API_KEY"}` (`llm/keys.py:4`) и
`if provider == "anthropic": return AnthropicAdapter(...)` / `return GeminiAdapter(...)` (`llm/factory.py:13–15`) → станет
`KEY_VARS` с `"openai": "OPENAI_API_KEY"` и третья ветка `if provider == "openai": return OpenAIAdapter(model, app_cfg,
api_key=key)`; `--provider` `choices=("anthropic", "gemini")` (`ui/cli.py:113`) → `("anthropic", "gemini", "openai")`.
**Поведение:** не меняется для текущих игр (по умолчанию Gemini). Меняется — появляется провайдер в меню `/model` и в
`model_options` (профиль openai попадает автоматически, `game/models.py:model_options`), `--provider openai`, выбор профиля
по наличию ключа (`cli.pick_narrator`: нет ключа Gemini — берётся первый профиль с ключом, порядок gemini → anthropic →
openai), `follow_provider` переводит world/summarizer на `profiles.openai`.
**Вне ai-dm:** OpenAI Platform — ключ `OPENAI_API_KEY` (тир Build, $5) — заводит проектировщик; живые вызовы (smoke и прогон)
— только проектировщик.

### Сверка моделей и цен (2026-10-20, developers.openai.com/api/docs/pricing, /models/gpt-6.1-sol, /models/gpt-6-luna)

| Модель | Input | Cached | Cache write | Output | Окно / макс. вход / вывод | effort |
|---|---|---|---|---|---|---|
| gpt-6.1-sol | 2.00 | 0.10 | 2.50 | 10.00 | 1.05M / 922K / 128K | low (default medium), high, xhigh, max; **none/minimal нет** |
| gpt-6-luna | 0.10 | 0.01 | 0.125 | 0.50 | 1.05M / 922K / 128K | none, low, medium (default), high… |
| gpt-6-sol | 2.00 | 0.20 | 2.50 | 10.00 | 1.05M | none…max |
| gpt-6-astra | 10.00 | 1.00 | 12.50 | 50.00 | 1.05M | low…max |

Ресёрч подтверждён; новых моделей (gpt-6.2, gpt-6.1-luna) на страницах нет. Запись в кэш 1.25× входа — не надбавка,
а ставка токена (`usage.input_tokens_details.cache_write_tokens`); чтение 0.05× у gpt-6.1-sol; минимум кэша 1024 токена,
TTL `30m`, префикс = instructions + tools + input. Chat Completions у gpt-6.1-sol — без tool calling → **только Responses**.
Reasoning-токены входят в `output_tokens` (`output_tokens_details.reasoning_tokens`), `max_output_tokens` ограничивает их
вместе с текстом. `store=false` → reasoning-элементы приходят с `encrypted_content`, их надо вернуть между вызовами хода без
изменений. Пакет `openai` — 3.35.1 от 2026-10-18 (PyPI; Python ≥ 3.10; зависимости `httpx2`, `jiter`, `anyio`, `sniffio`,
`typing-extensions`, `pydantic` — **все уже в uv.lock** через `anthropic 1.11.0`; новый пакет один — `openai`).

### Что уже есть (слой абстракции) и что нужно для третьего

- Есть: `ModelAdapter` (`complete`, `info`), типы `ChatRequest`/`ChatResponse`/`Opaque` (`llm/types.py`), ошибки с именами
  сетевых классов SDK (`llm/errors.py:NETWORK_NAMES`/`TIMEOUT_NAMES` — `APIConnectionError`, `APITimeoutError` у openai
  те же, что у anthropic), повторы (`llm/retry.py`), журнал/replay (Opaque хранится как dict — `journal.record_call`),
  стоимость (`llm/cost.py:cost_nano`: `cache_write`/`cache_read`/`cache_storage_hour` покрывают модель цен OpenAI),
  конфиг ролей/профилей (`config/app.py:RolesConfig`, `profiles`, `check_models_known`), `/model` и цепочка
  (`game/models.py`), `follow_provider` (`game/app.py:547`), оценка токенов по провайдеру (`MasterConfig.cpt_for`),
  `api_tokens` (`master/session.py:34`: ветка «не gemini» = `input + cache_read + cache_write` — для OpenAI верна, если
  адаптер отдаёт три непересекающихся числа, см. ниже).
- Нужно: адаптер, строка в `KEY_VARS`, ветка в `make_adapter`, `choices` cli, профиль + цены + окна в
  `app_defaults.toml`, `devtools/live_smoke.py` (choices и профиль), README, ARCHITECTURE (строка `llm` и E3а/E1 про
  `api_tokens`), facts-файл `docs/llm-notes/openai-facts.md` (по образцу `gemini-facts.md`), тесты.
- Не нужно: менять протокол, `master`, `game`, TUI, схемы инструментов (`protocol/schema.py:strictify` уже даёт
  `required` = все свойства и `additionalProperties: false`; в схемах только `type/enum/description/items` — проверено
  скриптом по `tool_set` всех режимов: нет `anyOf/minimum/pattern/format/minItems`, всё в подмножестве strict OpenAI).

**Модули/файлы/функции:**
- `src/ai_dm/llm/openai_adapter.py` — **новый**: `OpenAIAdapter(model, app_cfg, *, client=None, api_key=None)`;
  методы (все новые) `info`, `get_client`, `build_tools`, `build_input`, `build_kwargs`, `translate_error`, `complete`,
  `parse_response`, `stop_reason`, `stop_detail`, `usage_of`; модульные `block_to_item`, `item_from_api`.
- `src/ai_dm/llm/keys.py` — `KEY_VARS` (константа).
- `src/ai_dm/llm/factory.py` — `make_adapter` (есть).
- `src/ai_dm/ui/cli.py` — `make_parser` (есть, `choices` `--provider`).
- `src/ai_dm/config/app_defaults.toml` — `[profiles.openai.*]`, `[prices."gpt-6.1-sol"]`, `[prices."gpt-6-luna"]`,
  `[context_windows]`; код `config/app.py` не меняется.
- `devtools/live_smoke.py` — `main` (есть; `choices` и выбор профиля).
- `tests/unit/llm/test_llm_openai_adapter.py` — новый; правки: `tests/unit/llm/test_llm_factory.py`
  (`test_unknown_provider_is_value_error` использует `"openai"` как неизвестного — заменить на `"mistral"`, добавить
  `test_openai_provider_gives_openai_adapter`), `tests/unit/llm/test_llm_keys.py:113` (то же), `tests/unit/ui/test_ui_cli.py:687`
  (`test_unknown_provider_is_rejected` с `--provider openai` — заменить провайдера), `tests/unit/devtools/test_live_smoke.py:73`
  (parametrize + openai), `tests/unit/config/test_app.py` (профиль openai: модели, цены, окна, `import_`),
  `tests/unit/game/test_to_follow_provider.py` (цикл по профилям — добавить openai), `tests/unit/llm/llm_kit.py` —
  комментарий-контракт (строки про адаптеры).
- Документы: README (ключи, `--provider`), docs/ARCHITECTURE.md (`A1` строка `llm`: «Anthropic/Gemini/Mock (позже
  OpenAI-compat)» → «Anthropic/Gemini/OpenAI/Mock»; `E1` про `api_tokens`), docs/llm-notes/openai-facts.md.

**Модули (с нуля):** нет — режим «встроить».
**Стек, схема данных:** без изменений; новая зависимость — `openai>=3.35` (только с согласия, вопрос 1).

### Проект адаптера (в стиле `GeminiAdapter`/`AnthropicAdapter`)

- Клиент лениво: `openai.OpenAI(api_key=, max_retries=0, timeout=self.cfg.retry.timeout_s)` (повторы — наши `retry.py`,
  как у Anthropic; таймаут общий `timeout_s = 180`, без своего поля, в отличие от `gemini_timeout_s` — у OpenAI нет
  зависаний IPv6, и ничего не известно о нужде; добавить при необходимости по прогону).
- Запрос `client.responses.create(**kwargs)`:
  `model=req.model`; `instructions="\n\n".join(b.text for b in req.system)` (как `system_instruction` Gemini; явных
  breakpoints кэша не ставим — implicit-режим кэширует весь префикс instructions+tools+input автоматически);
  `input=build_input(req)`; `tools=build_tools(req)`; `max_output_tokens=req.max_tokens`;
  `reasoning={"effort": req.effort}` только при `req.effort is not None` (у `ModelRole.effort` — то же поле, что для
  Anthropic; `[llm] thinking` — не трогать, оно про Claude); `store=False` плюс `include=["reasoning.encrypted_content"]`
  (по документации с `store=false` уже по умолчанию, флаг — для совместимости со старыми снимками); `parallel_tool_calls`
  не передаём (по умолчанию разрешены, как у Gemini/Anthropic — протокол принимает несколько `ToolCall` в ответе);
  `tool_choice` не передаём (AUTO, C2 ARCHITECTURE).
- `build_tools`: `{"type": "function", "name", "description", "parameters": input_schema, "strict": tool.strict and
  cfg.llm.strict_tools}` — `NON_STRICT` explore (27 из 33) уходят `strict: false`, как у Anthropic; схемы без правок
  (см. «Что уже есть»). 33 функции в explore против мягкой рекомендации «< 20» — риск качества, не ошибка API.
- `build_input`: `user` Text → `{"type": "message", "role": "user", "content": [{"type": "input_text", "text"}]}`;
  `ToolResult` → `{"type": "function_call_output", "call_id": block.call_id, "output": content}` (у `is_error` —
  `output` = `{"error": content}` JSON-строкой, как ключ `error` у Gemini); assistant без `Opaque("openai")` → Text →
  `{"type": "message", "role": "assistant", "content": [{"type": "output_text", "text"}]}`, ToolCall →
  `{"type": "function_call", "call_id": id, "name", "arguments": json.dumps(input, ensure_ascii=False)}`; assistant с
  `Opaque(provider="openai", raw={"items": [...]})` → элементы `raw["items"]` как есть вместо Text/ToolCall этого сообщения
  (правило OpenAI «не менять reasoning/function_call после последнего user» — тот же приём, что `parts` у Gemini);
  `Opaque` чужих провайдеров — пропускать (как `anthropic_adapter.build_base`). Сообщения ходов прошлых — текстом в
  `messages[0]` (E2), Opaque живёт только внутри хода (`master/session.py:371,440,469,489`), так что история не распухает.
- `parse_response`: по `response.output`: `message` → `output_text` → `Text`, `refusal` → stop `refusal` +
  `stop_detail` = текст отказа; `function_call` → `ToolCall(id=call_id, name, input=json.loads(arguments))`
  (аргументы не JSON — у Gemini/Anthropic такого не бывает, схемы `ToolCall.input: dict`: поднимать
  `LlmFatal("аргументы вызова не JSON")`, тест у доебы);
  в конец — один `Opaque(provider="openai", raw={"items": [item.model_dump(mode="json", exclude_none=True) for item in
  output]})` если output непуст. `stop_reason`: есть function_call → `tool_use`; `status == "incomplete"` и
  `incomplete_details.reason == "max_output_tokens"` → `max_tokens`, `content_filter` → `refusal`; `status == "failed"`
  → исключение по `error.code` (`server_error`/`rate_limit_exceeded` → `LlmTransient`, иначе `LlmFatal`);
  `completed` без вызовов → `end_turn`; прочее → `other`. `request_id=response._request_id`, `model=response.model or req.model`.
- `usage_of`: `cached = input_tokens_details.cached_tokens`, `written = input_tokens_details.cache_write_tokens` (None → 0);
  `Usage(input=input_tokens − cached − written, cache_read=cached, cache_write=written, output=output_tokens)` —
  reasoning уже в `output_tokens`; три числа не пересекаются → `api_tokens` и `cost_nano` без правок;
  `cache_write_1h` = `cache_write` (одна ставка), `cache_storage_hour = 0`.
- `translate_error`: как у Anthropic — `status_code` (408/429/5xx → `LlmTransient`, `retry_after` из заголовков через
  `retry_after_of`, 504 → `timeout`), без кода — `is_network_error`/`is_timeout_error`; `redact(str(error), [api_key])`.
  `retry_after_of` импортировать из `anthropic_adapter` (модуль без SDK на уровне импорта; альтернатива — перенести в
  `errors.py`, на усмотрение кабана, если ревью попросит).
- `info()` → `AdapterInfo(provider="openai", model=self.model)`.

### Конфиг (`app_defaults.toml`)

```
[profiles.openai.narrator]   provider = "openai"  model = "gpt-6.1-sol"  effort = "<вопрос 3>"  max_tokens = 16000
[profiles.openai.world]      provider = "openai"  model = "gpt-6-luna"   effort = "low"  max_tokens = 8000
[profiles.openai.summarizer] provider = "openai"  model = "gpt-6-luna"   effort = "low"  max_tokens = 8000
[profiles.openai.import]     provider = "openai"  model = "<вопрос 5>"   effort = "low"  max_tokens = 32000
[prices."gpt-6.1-sol"]  input = 2000000  output = 10000000  cache_read = 100000  cache_write = 2500000  cache_write_1h = 2500000  cache_storage_hour = 0
[prices."gpt-6-luna"]   input = 100000   output = 500000    cache_read = 10000   cache_write = 125000   cache_write_1h = 125000   cache_storage_hour = 0
[context_windows]  "gpt-6.1-sol" = 922000  "gpt-6-luna" = 922000   # макс. вход (окно 1.05M); бюджет всё равно static + 16000
```
- effort у дешёвых ролей задаётся явно: без него OpenAI берёт `medium`, reasoning растёт в output. `max_tokens` 8000
  у world/summarizer (у других профилей 4000): reasoning входит в лимит, обрыв даёт `max_tokens` → запасная выжимка.
- `chars_per_token_by_provider.openai` — не задаём (общий 2.5; переоценка безопаснее — решение ЖП3 по 109); калибровка
  по журналу после прогона (как calls-013 в ЖП3) — пункт в бэклог/в фикс ЖП4, см. риски.
- `roles.*` и `narrator_chain` — по вопросам 2 и 4.

### Стоимость хода на реальных объёмах

Журнал `dusk_academy-d3de6c57` (409 ходов на gemini-3.8-flash, 2,25 вызова на ход): на ход новых входных 19,6k,
чтение кэша 33,5k, запись 2,6k, вывод 1,4k (с мышлением) → факт $0,0109/вызов ≈ **$0,025/ход**. Для OpenAI префиксный
кэш покрывает и первый вызов хода (статика ≈ 20k), и весь вход второго: вызов 1 — чтение 20k, запись ≈ 9k динамики;
вызов 2 — чтение ≈ 29k, запись ≈ 1,5k; вывод — текст ≈ 1k + reasoning (low ≈ 2k, medium ≈ 5k на ход).

| Модель рассказчика | Чтение | Запись | Вывод | Итого/ход | vs gemini-3.8-flash |
|---|---|---|---|---|---|
| gpt-6.1-sol, effort low | $0,005 | $0,026 | $0,030 | **≈ $0,06** | ≈ 2,5× |
| gpt-6.1-sol, effort medium | $0,005 | $0,026 | $0,060 | **≈ $0,09** | ≈ 3,7× |
| gpt-6-luna, low | $0,0005 | $0,0013 | $0,0015 | ≈ $0,003 | ≈ 0,13× |
| claude-sonnet-5-5 (факт, тот же мир) | | | | ≈ $0,07 | ≈ 2,9× |

Плюс раз на границе сцены (смена блока памяти в `instructions`) — перезапись статики: 20k × $2,5/M ≈ $0,05 (sol).
Дешёвые роли на luna: summarizer ≈ $0,001/вызов, world ≈ $0,001 (у gemini-3.5-flash-lite $0,002/0,0017). 100 ходов:
sol low ≈ $6, medium ≈ $9, gemini ≈ $2,5, sonnet ≈ $7. Ресёрч (2,5×) подтверждён для `low`.

**Партии / MVP по шагам:** одна партия (M); деление на две не нужно — адаптер без конфига не проверить, конфиг без
адаптера не пройдёт `make_adapter`. Калибровка cpt и подстройка effort/max_tokens — после живого прогона, не партия.
1. `pyproject.toml` — `openai>=3.35` в `dependencies`, `uv lock` (после ответа на вопрос 1; новый пакет в lock один).
2. `llm/keys.py:KEY_VARS` — `"openai": "OPENAI_API_KEY"`; `llm/factory.py:make_adapter` — ветка `openai`. Проверка:
   `make_adapter("openai", "gpt-6.1-sol", cfg, env={"OPENAI_API_KEY": "k"})` → `OpenAIAdapter`, без SDK и сети.
3. `llm/openai_adapter.py` — адаптер по проекту выше; SDK импортируется только в `get_client`. Проверка: фейковый
   клиент (`client.responses.create(**kw)`) в тестах доебы; живой — `uv run python devtools/live_smoke.py openai`
   (проектировщик).
4. `config/app_defaults.toml` — профиль, цены, окна. Проверка: `load_settings()` проходит `check_models_known`;
   `tests/unit/master/test_static_budget.py` (сторож `STATIC_MAX + context_cap ≤ window80` по моделям рассказчика —
   новый профиль попадает автоматически).
5. `ui/cli.py:make_parser` — `choices` + openai; `devtools/live_smoke.py:main` — `choices`, профиль openai.
6. Документы: README (ключи, `--provider`), ARCHITECTURE A1/E1/E3а (одна строка каждая), `docs/llm-notes/openai-facts.md`
   (снимок API: поля запроса/ответа, usage, кэш, отказы — то, что кабан сверит с установленным SDK), `llm_kit.py` контракт.
7. Проектировщик: ключ, `live_smoke.py openai`, затем игра `/model narrator openai:gpt-6.1-sol` (сохраняется в
   `models.json`, world/summarizer следуют); разбор журнала — оценка/факт токенов (`meta.context.api_tokens`), доля
   `cached_tokens`, reasoning в выводе, отказы.

**Тестовые сценарии (для кабана-доебы, TDD):** фейковый клиент с `.responses.create(**kw)`, объекты ответа — `Rec`
с `model_dump`, как в `test_llm_gemini_adapter.py`; сети и SDK нет.
- `make_adapter("openai", …, env={"OPENAI_API_KEY": "k"})` → `OpenAIAdapter`, `info() == AdapterInfo("openai", model)`;
  без ключа → `MissingKey`, в тексте «OPENAI_API_KEY»; `make_adapter("mistral", …)` → `ValueError` (замена «openai» в
  старом тесте).
- `complete(full_request())` → `kwargs`: `model`, `instructions` = тексты system через пустую строку, `tools[0] ==
  {"type": "function", "name", "description", "parameters": input_schema, "strict": True}`, `max_output_tokens == 8000`,
  `reasoning == {"effort": "medium"}`, `store is False`; без `effort` — ключа `reasoning` нет; `strict_tools = false` в
  конфиге → `strict: False` у всех; `tool["strict"] = False` из `tool_set("explore")` → `False`.
- `input`: user Text → message/input_text; assistant Text + ToolCall (без Opaque) → message/output_text +
  function_call с `arguments` JSON-строкой; ToolResult → function_call_output с тем же `call_id`; `is_error` →
  `output` содержит текст ошибки; assistant с `Opaque("openai", {"items": [...]})` → ровно эти items, Text/ToolCall того
  сообщения не дублируются; `Opaque("gemini", …)` в сообщении — пропущен.
- Ответ: `output = [reasoning(encrypted_content), message(output_text "…")]`, `status completed` → `content ==
  [Text, Opaque("openai", items=2 dump)]`, `stop_reason end_turn`; `output = [reasoning, function_call(call_id "call_1",
  name "skill_check", arguments '{"skill":"perception",...}')]` → `ToolCall(id="call_1", input=dict)`, `tool_use`; два
  `function_call` → два ToolCall по порядку; `message` с `refusal` → `refusal`, `stop_detail` = текст; `status
  incomplete, reason max_output_tokens` → `max_tokens`; `reason content_filter` → `refusal`; `status failed, error.code
  server_error` → `LlmTransient`, `invalid_prompt` → `LlmFatal`; `arguments` не JSON → `LlmFatal`.
- `usage`: `input_tokens 30000, cached 20000, cache_write 9000, output 3000 (reasoning 2000)` → `Usage(input=1000,
  cache_read=20000, cache_write=9000, output=3000)`; `input_tokens_details` без `cache_write_tokens` → 0;
  `api_tokens(usage, "openai") == 30000`; `cost_nano` по `prices["gpt-6.1-sol"]` = 1000×2 + 20000×0.1 + 9000×2.5 +
  3000×10 = $0,0565 → 56 500 000 нано.
- Ошибки: исключение с `status_code 429` и `response.headers["retry-after"] = "7"` → `LlmTransient(retry_after=7.0)`;
  504 → `timeout=True`; 400 → `LlmFatal`; класс с именем `APIConnectionError` без кода → `LlmTransient`;
  `APITimeoutError` → `timeout=True`; ключ `SECRET` в тексте ошибки → `***`.
- Клиент: `get_client()` зовёт фабрику с `api_key`, `max_retries=0`, `timeout=cfg.retry.timeout_s`; `request_id` из
  `_request_id`; `model` из ответа, иначе запрошенная.
- Конфиг: `app().profiles["openai"]` — narrator `gpt-6.1-sol`, world/summarizer `gpt-6-luna`, `import_` задан; цены и
  окна есть (`check_models_known`); `cpt_for("openai") == 2.5` (старый тест ЖП3 остаётся верным);
  `model_options(app)` содержит `"openai:gpt-6.1-sol"`; `follow_provider` на openai ставит world/summarizer из профиля.
- cli: `--provider openai` без ключа → код ≠ 0 и «OPENAI_API_KEY» в выводе; `--provider mistral` → отказ argparse.
- Журнал/replay: запись с `Opaque("openai")` → `ReplayAdapter` отдаёт тот же `ChatResponse` (round-trip через
  `model_dump`/`model_validate`), `request_fingerprint` стабилен.
- Проверка руками (проектировщик): `uv run python devtools/live_smoke.py openai` — `stop_reason tool_use`, `usage` с
  `cache_read == 0` на первом вызове; в игре `/model narrator openai:gpt-6.1-sol`, второй ход — в журнале
  `usage.cache_read > 0`, `/cost` считает по `gpt-6.1-sol`/`gpt-6-luna`.

**Развилки и риски:**
- Responses vs Chat Completions: Responses обязателен для gpt-6.1-sol (tool calling), Chat Completions — путь для
  локальных серверов Э10б (Ollama/LM Studio); в этой партии только Responses, `base_url` в конфиг не добавляем
  (предложение: `[llm] openai_base_url` — одна строка, когда дойдём до Э10б).
- Запасной провайдер: нового механизма не делаем — есть `narrator_chain` (жёсткий отказ) и меню ошибки (сеть, Т60:
  авто-переключения на сетевых сбоях нет по решению); вопрос 4 — включать ли openai в цепочку.
- Риск: 33 инструмента в explore против рекомендации «< 20» и «примеры в промпте вредят reasoning-моделям» (47 КБ правил)
  — качество следования, проверяется прогоном; лечение (tool_search/`defer_loading`, gpt-5.4+) — не в партии.
- Риск: оценка токенов (cpt 2.5) может расходиться с o200k; `meta.context.overflow`/`api_tokens` в журнале покажут,
  калибровка — мини-правка `app_defaults.toml` как 109 (пункт бэклога после прогона).
- Риск: `max_tokens 16000` рассказчика включает reasoning; при `incomplete` → `max_tokens` → движок обрабатывает как у
  Claude (там тоже мышление в лимите). У world/summarizer поднят до 8000.
- Риск: размер журнала — `encrypted_content` по несколько КБ на вызов внутри `Opaque`; ротация 5/50 МБ есть.
- Риск: тестовые имена исключений SDK (`APIStatusError.status_code`, `_request_id`) — сверить с установленным
  `openai` при реализации, записать в `openai-facts.md`.

**Открытые вопросы:**
1. Зависимость `openai>=3.35` (3.35.1 от 2026-10-18; один новый пакет в uv.lock, остальное уже есть через anthropic)
   — ставить? варианты: (1) да (2) нет — тогда партия невозможна (сырой httpx-клиент к Responses — не в стиле проекта);
   рекомендую (1); разблокирует: шаг 1; решает: проектировщик. Блокирующий.
2. Провайдер по умолчанию (`roles.*`, `app_defaults.toml:2–21`): (1) оставить Gemini, OpenAI — через `/model narrator
   openai:gpt-6.1-sol` (запоминается в `models.json` мира) или `--provider openai`; (2) `roles.* = profiles.openai`
   (новые миры и миры без `models.json` — на OpenAI; README/тесты `test_app.py:56,457` меняются); рекомендую (1) для
   партии — «gemini очень плохо» ещё не проверено прогоном на OpenAI, переключение в своём мире — одна команда;
   разблокирует: шаг 4; решает: проектировщик.
3. `effort` рассказчика gpt-6.1-sol: (1) `low` ≈ $0,06/ход (2) `medium` ≈ $0,09/ход (умолчание OpenAI; у Claude в
   профиле тоже `medium`); рекомендую (2) по правилу «не урезать мышление рассказчика» (AGENTS.md «Решения по
   экономии»), ресёрч советовал low/medium; разблокирует: шаг 4; решает: проектировщик.
4. `narrator_chain` (`app_defaults.toml:153`, авто-переключение при жёстком отказе, игроку видна строка «Модель X
   отказала — переключаюсь на Y»): (1) не трогать — openai только из меню; (2) добавить `openai:gpt-6.1-sol` первым
   после `gemini:gemini-3.8-flash` (при отказе Gemini ход уходит на OpenAI, роли следуют); (3) в конец; рекомендую (2),
   если ответ на вопрос 2 — (1): это и есть «запасной провайдер» без нового кода; решает: проектировщик.
5. Роль `import` в профиле openai (пак целиком одним вызовом, редко): (1) `gpt-6.1-sol` low (как sonnet low у
   anthropic) (2) `gpt-6-luna`; рекомендую (1) — качество пака важнее, вызов единичный; решает: проектировщик.
6. Показ мышления в журнале (`reasoning.summary = "auto"`, аналог `thinking_display`): (1) не запрашивать (MVP)
   (2) запрашивать — может требовать верификации организации, тарификация сводки не найдена; рекомендую (1);
   решает: проектировщик (можно отложить).

## Правки по ревью

Отклонения кабана от плана при реализации (2026-10-20, технические, приняты оркестратором до ревью):
- `Usage.cache_write_1h = 0` (план: = `cache_write`) — иначе запись в кэш считалась бы дважды в `cost_nano`/`api_tokens`,
  противоречие с тестовым сценарием плана ($0,0565, `api_tokens` 30000). Цена `cache_write_1h` в toml оставлена, не влияет.
- Конструктор `OpenAIAdapter(..., client=None, client_factory=None, api_key=None)` — как `AnthropicAdapter`; план давал
  только `client`, а сценарий тестов требует фабрику.
- `incomplete_details.reason` `max_messages`/`steered` (есть в SDK) → `stop_reason "other"`.
- Риск для живого прогона (кабан, в openai-facts.md): при `store=False` API может отвергнуть `id` несохранённых элементов —
  тогда убрать `id` у message/function_call при отправке; `live_smoke.py` с `max_tokens=1000` при effort medium может
  дать `max_tokens`.
- Ревью мамы-кабана (2026-10-20), исправлено кабаном по решению оркестратора: (1) `incomplete`/`max_output_tokens` —
  `function_call` не разбираются, `stop_reason max_tokens` (оборванные аргументы не дают `LlmFatal`), тест у доебы;
  (3) `retry_after_of` перенесён в `llm/errors.py` без изменений. Не правились: (2) `cache_write_tokens or 0` — оставлено
  по плану (replay); (4) `id` при `store=False` — в шпаргалку живого прогона.
- Полный прогон (2026-10-21): smells 204 > 200 (+4 в `openai_adapter.py`) — кабан разбил `parse_response`
  (`raise_failed`, `parse_call`, `parse_output`, `stop_of` вместо `stop_reason`/`stop_detail`, таблица `INCOMPLETE_STOPS`);
  порядок блоков ответа — Text, затем ToolCall (как у Gemini), Opaque последним с исходным порядком; по решению
  оркестратора убран параметр `client` — `OpenAIAdapter(model, app_cfg, *, client_factory=None, api_key=None)`, как у
  Anthropic. smells 200. 19 тестов цепочки (`test_to_chain`, `test_t60_menu`, `test_to_auto_reports`,
  `test_f1_timeout_menu`) поправлены доебой под цепочку из пяти; `test_world_and_summarizer_adapters_are_not_changed`
  переписан на переход внутри Gemini (ARGON → PREVIEW), новый
  `test_switch_to_another_provider_moves_world_and_summarizer_to_its_profile` — переход на openai переводит роли.
- Аудит свекрови: место openai в `narrator_chain` — уточнено у проектировщика (решение 8).
- Доеба: сверх плана поправлены ожидания `tests/unit/game/test_t60_models.py` под цепочку из пяти ключей.

## Итог

Закрывает BACKLOG 65. Живой smoke (`devtools/live_smoke.py openai`) и прогон — за проектировщиком.

**Тесты:** `pytest` 20128 passed; cov 97,98 %; smells 200/200; `make dead` чист; ruff — 16 старых. Мутанты: 22 убиты,
2 эквивалентные, 8 выживших на старых строках → BACKLOG 122.

**Стоимость (кабан-тесть, 2026-10-21).** Сметы не было (решение 7) — только факт.
**Источник токенов:** `metrics.py`
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/08a728fd-3fe3-4fef-ba58-27386f93da56.jsonl`;
**цены:** тариф `metrics.py` от 2026-10-17, https://platform.claude.com/docs/en/about-claude/pricing (тестем сегодня не
пересверены). Планирование папы-кабана — в предыдущей сессии 2026-10-20, сюда не входит.

| Партия | Смета | Факт |
|---|---|---|
| Э10а, одна партия (код, тесты, 3 захода ревью/аудита, мутанты) | нет (решение 7) | шаг 730 мин по часам сессии (18:24 → 06:35, с ночным перерывом); работа субагентов ≈ 51 + 32 мин; 13,67 M токенов, $6,51 |

| Роль | Модель | Токены (вход+кэш+вывод) | $ |
|---|---|---|---|
| kaban | claude-sonnet-5-5 | 2 791 588 (вывод 13 905) | 1,02 |
| kaban-doeba (тесты + разбор мутантов, 2 запуска) | claude-sonnet-5-5 | 3 058 673 (вывод 9 744) | 1,35 |
| mama-kaban (3 захода) | claude-opus-5-5 | 665 350 (вывод 560) | 0,63 |
| kaban-svekrov (3 захода) | claude-opus-5-5 | 562 498 (вывод 326) | 0,63 |
| papa-kaban (короткий вызов в этой сессии) | claude-fable-5-1 (по ценам Opus) | 33 754 | 0,10 |
| оркестратор — на момент подсчёта 11:35 | claude-opus-5-5 | 6 504 149 (вывод 20 584) | 2,69 |
| kaban-test — на момент подсчёта 11:35 | claude-opus-5-5 | 49 801 | 0,10 |

**Итого:** смета нет → факт ≈ $6,51 (13,67 M токенов, 92 % — чтение кэша). Расхождение не считается: сметы не было.
Цифры оркестратора и тестя неполные, сессия ещё идёт.

правки: Edit 1 («Итог»), из bash 0 (ожидается 0)

Разбор — кабан Декарта.
