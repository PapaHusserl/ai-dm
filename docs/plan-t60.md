# План мини-партии #17 «Т60 Сеть» (BACKLOG 60, T2)

Автор: papa-kaban, 2026-10-15. Статус: ждёт аппрува проектировщика (Q1–Q9 в конце, рекомендации papa).
Груминга нет (R6 §10 п.2а: техдолг по правилу фикса). Сейв v9 без изменений. Оценка ≈ 0,5 млн. Smells 200/200 — нулевой баланс.
Источники: BACKLOG 60; docs/research/gemini-503-research.md; docs/plan-roadmap-r6.md §2 «Т60», §10 (11а — таймаут 90 с);
docs/plan-techdebt.md T2.

## 0. Что в коде сейчас (проверено)
- `llm/gemini_adapter.py:58 get_client` — `HttpOptions(timeout=retry.timeout_s*1000)`, общий 180 с (Anthropic тот же ключ,
  `anthropic_adapter.py:67`). У `HttpOptions` (google-genai 2.28.0) есть `client_args: dict` → `SyncHttpxClient(**client_args)`;
  `_ensure_httpx_ssl_ctx` добавляет в `client_args` только `verify`/`timeout`, свой `transport` не перебивает; httpx 0.28.1
  при заданном `transport` игнорирует `verify` (`_init_transport`). `httpx` в pyproject не объявлен (транзитивно через SDK).
- `llm/retry.py call_with_retries(adapter, req, policy, sleeper, on_attempt)` — `policy = app_cfg.retry` из `MasterSession.call`
  (`master/session.py:176`), 4 попытки `[1,3,10]`; `RetriesExhausted` → `TurnFailed("network")`.
- `master/summarizer.py:12 SOFT_REASONS = ("refusal","invalid")`; `SummarizerSession.chain` → backup (модель рассказчика,
  `game/turn.py:339–346`) → `(None, True)` → `boundary.fallback_summary`/`concat_chapter`, тег `refusal_fallback`.
  `network` сейчас — наверх, `failed_role="summarizer"`, меню 2.2 (`boundary.py:74–76`).
- Запасной рассказчик — одна запись `AlternativesConfig.narrator` (`config/app.py:29`); меню `game/app.py:70 model_options`
  (roles + alternatives + profiles); `find_role_cfg` в `master/prompt.py:181` и `master/hero.py:68` ищут max_tokens/effort
  по модели, иначе `roles.narrator`.
- Меню ошибки: `GameApp.choose_error` → `switch_role` («summarizer», если `runner.failed_role`), `choose_model` меняет одну роль;
  `set_narrator` сам переводит world/summarizer на профиль нового провайдера и пишет `meta/models.json`.
- Журнал: запись только по завершении попытки (`MasterSession.call.on_attempt` → `Journal.record_call`); висящая попытка
  следа не оставляет. `ReplayAdapter` читает `calls-*.jsonl` по роли и воспроизводит transient-ошибки из записей.
- Пользовательский `~/.config/ai-dm/config.toml` (не трогаем): `[roles.summarizer]` = 3-flash-preview, `[alternatives.narrator]`
  = argon (таблица!), цены/окна argon и 3-flash-preview.

## 1. Решения (архитектура)
1. **IPv4** — `[llm] gemini_ipv4 = true` (`LlmConfig`, рядом с `gemini_safety`). `GeminiAdapter.get_client`: при флаге
   `client_args={"transport": httpx.HTTPTransport(local_address="0.0.0.0")}` (ленивый `import httpx` внутри метода, как SDK).
   Только Gemini (Anthropic работал; свой httpx-клиент SDK — Q9).
2. **Таймаут Gemini** — `[retry] gemini_timeout_s = 90` (`RetryConfig`, рядом с `timeout_s`; 180 остаётся Anthropic).
   Адаптер: `HttpOptions(timeout=gemini_timeout_s*1000)`. Отдельного connect-таймаута нет (решение BACKLOG 60, вариант А).
3. **Цепочка рассказчика** — `[llm] narrator_chain = ["gemini:gemini-3.8-flash", "gemini:gemini-4-argon",
   "gemini:gemini-3-flash-preview", "gemini:gemini-3.5-flash-lite"]` — список ключей «провайдер:модель» в формате меню (Q1).
   Основная модель — первый элемент. `alternatives.narrator` не трогаем (совместимость с config.toml пользователя, ручной
   запасной Claude). Новый модуль `game/models.py`: `next_in_chain(app_cfg, provider, model) -> str | None` (следующий ключ
   после текущего; модели нет в цепочке или она последняя → None), сюда же переезжают `model_options` (+ ключи цепочки без
   повторов), `check_model`, чтение/запись `models.json` (`read_models`, `write_models`) — разгрузка `game/app.py` под нулевой
   баланс smells; в `app.py` оставить реэкспорт `model_options`, `check_model` (тесты и `ui/hero_session.py` импортируют оттуда).
   `AppConfig.check_models_known`: модели цепочки должны иметь цену и окно; формат ключа — `provider:model`.
   `find_role_cfg` (prompt/hero) не меняем: у моделей цепочки max_tokens от `roles.narrator` (16000), effort у Gemini не нужен.
4. **Переключение по цепочке без ожидания 4 попыток** — `[retry] chain_delays = []` (Q2): политика повторов для вызова,
   у которого есть запасной путь (следующая модель цепочки / backup summarizer). Плечо: `MasterSession(..., policy=None)` →
   `self.policy = policy or app_cfg.retry`, `call` использует `self.policy`; `SummarizerSession(..., policy=None)` → в
   `run_scene`/`run_chapter`; `TurnRunner`: флаг `chain_next: bool` (ставит GameApp) и `fast_policy()` =
   `app_cfg.retry.model_copy(update={"delays": chain_delays})`; `new_session` → `policy=fast_policy() if chain_next else retry`;
   `new_summarizer_session` → primary с `fast_policy()` когда есть backup, backup — полные delays. `WorldSession` — без изменений.
5. **Авто-переключение рассказчика** (Q3) — `GameApp.after_turn`: ход не commit, `failure.reason == "network"`, `auto_chain`
   включён и `next_in_chain(...)` не None → строка игроку «Модель {старая} недоступна (сеть), переключаюсь на {новая}.»,
   `set_narrator(new)` (пишет models.json; world/summarizer по профилю — провайдер тот же, не меняются), **summarizer тоже на
   новую, если `runner.summarizer_model` равен упавшей модели** (иначе каждая граница — лишний 503, тег `refusal_fallback` и
   авто-репорт), затем `runner.retry()`; цикл, пока сеть и есть следующая. Цепочка исчерпана → меню ошибки как сейчас.
   `GameApp(auto_chain=True)`; cli передаёт `not (args.mock or args.replay)` (как `auto_reports`) — в replay/mock не стреляет.
   `sync_chain()` после `__init__`/`restore_model` и в `set_narrator`: `runner.chain_next = next_in_chain(...) is not None`.
6. **`network` в SOFT_REASONS** — `SOFT_REASONS = ("refusal", "invalid", "network")`; `boundary.py` без изменений
   (`None, True` → fallback-выжимка, тег `refusal_fallback`; переименование — BACKLOG 61, не здесь).
7. **Обе роли в меню ошибки** (Q4) — `choose_error("switch_model")`: `switch_role = "both"`, если ход упал по `network`
   (`runner.last_capture.failure_reason`/`turn.failure.reason` — хранить в `GameApp.failed_reason` из `after_turn`);
   `choose_model`: `both` → `set_narrator(key)` + `set_summarizer(key)`, строка «Модели рассказчика и summarizer: {key}.».
   Граница (`failed_role`) — как сейчас (summarizer теперь до меню по сети не доходит; остаётся world/fatal).
8. **Лог старта попытки** (Q5) — `call_with_retries(..., on_start=None)`: перед `adapter.complete` зовёт `on_start(attempt)`.
   `MasterSession.call`: `on_start = lambda attempt: journal.note_start(run_id, ctx.turn_seq, self.role, info.model, attempt,
   self.now())` (если журнал есть). `Journal.note_start` — строка `ts\trun_id\tturn_seq\trole\tmodel\tattempt` в
   `saves/<world>/journal/attempts.log` (не `calls-*` — `segments()`, blobs, replay и репорты его не видят). Висящая попытка —
   последняя строка без парной записи в `calls-*.jsonl`.
9. `create_cache` при 5xx — не трогаем (Q6).
10. Дефолты (`app_defaults.toml`): цены/окна `gemini-4-argon` (4.0/20/0.2/4.0, `cache_storage_hour = 0` — явного кэша нет,
    create даст 4xx → `caches[key]=None`, уже так) и `gemini-3-flash-preview` (0.5/3.0/0.05/0.5, хранение 1.0) — из config.toml
    пользователя; `narrator_chain`, `gemini_ipv4`, `gemini_timeout_s`, `chain_delays`. `roles.summarizer` — Q8.
    pyproject: `httpx>=0.28` явной зависимостью (Q7), `uv lock`.
11. Миграция пользовательского config.toml (делает пользователь после коммита, в плане — памятка): убрать `[prices."gemini-4-argon"]`,
    `[prices."gemini-3-flash-preview"]`, `[context_windows]` (теперь в дефолтах; оставить — не ошибка, deep_merge);
    `[alternatives.narrator]` argon → убрать (цепочка покрывает; вернётся Claude sonnet как ручной запасной) или оставить;
    `[roles.summarizer]` — по Q8. `meta/models.json` миров на 3.8-flash — не трогать: цепочка сработает на лету.

## 2. Затронутые файлы
`config/app.py` (`LlmConfig.gemini_ipv4`, `LlmConfig.narrator_chain`, `RetryConfig.gemini_timeout_s`, `RetryConfig.chain_delays`,
`AppConfig.check_models_known`); `config/app_defaults.toml`; `llm/gemini_adapter.py` (`get_client`); `llm/retry.py`
(`call_with_retries`); `llm/journal.py` (`Journal.note_start` — новая); `master/session.py` (`MasterSession.__init__`, `call`);
`master/summarizer.py` (`SOFT_REASONS`, `SummarizerSession.__init__`, `run_scene`, `run_chapter`); `game/turn.py`
(`TurnRunner.__init__`, `fast_policy` — новая, `new_session`, `new_summarizer_session`); `game/models.py` — новый
(`next_in_chain`, `model_options`, `check_model`, `read_models`, `write_models`); `game/app.py` (`GameApp.__init__`, `after_turn`,
`auto_switch` — новая, `sync_chain` — новая, `choose_error`, `choose_model`, `set_narrator`, `restore_model`); `ui/cli.py`
(`auto_chain=`); `ui/hero_session.py` (импорт из `game.models` или реэкспорт); pyproject.toml, uv.lock.
Документы: ARCHITECTURE.md E3 (стр. 628: `network` → backup → fallback), абзац «Сеть и цепочка» рядом с меню 2.2 (стр. 742/752),
комментарии `app_defaults.toml`, docs/llm-notes/gemini-facts.md (IPv4-транспорт, таймаут на фазу, argon без кэша), BACKLOG 60
закрыть (61 оставить), ROADMAP #17, tests/unit/game/game_kit.py и master_kit.py (шапки-контракты), HANDOFF (оркестратор),
checklist-t60-live.md (не коммитить).

## 3. Шаги kaban
1. `config/app.py` + `app_defaults.toml`: поля из §1 п.1–4, 10; валидация цепочки (формат `provider:model`, цена+окно);
   `chain_delays: list[int] = []`, `gemini_timeout_s: int = 90` (`Field(gt=0)`), `gemini_ipv4: bool = True`.
2. `llm/gemini_adapter.py get_client`: `gemini_timeout_s`; при `gemini_ipv4` — `client_args` с `HTTPTransport(local_address="0.0.0.0")`.
3. `llm/retry.py`: параметр `on_start`; `llm/journal.py Journal.note_start`.
4. `master/session.py`: `policy=`, `on_start` в `call` (одна лямбда — не раздувать `call`, иначе smell).
5. `master/summarizer.py`: `"network"` в `SOFT_REASONS`; `policy=` в `SummarizerSession` → `MasterSession`.
6. `game/turn.py`: `chain_next`, `fast_policy`, подстановка политики в `new_session`/`new_summarizer_session`.
7. `game/models.py` (новый): перенос `model_options`/`check_model`/models.json из `app.py`, `next_in_chain`; реэкспорт в `app.py`.
8. `game/app.py`: `auto_chain`, `failed_reason`, `sync_chain`, `auto_switch` (цикл по цепочке), `switch_role == "both"`.
   `ui/cli.py`: `auto_chain=not (args.mock or args.replay)` в обоих `GameApp(...)` (игра и `play_report`).
9. pyproject `httpx>=0.28` + `uv lock`; документы и чек-лист живого прогона (curl -4 по четырём моделям; ход на 3.8-flash → при 503
   строка переключения и `models.json`; граница при 503 summarizer → выжимка fallback + репорт; `/model narrator gemini:gemini-3.8-flash`
   обратно; `attempts.log`; длинный ответ argon не обрывается по 90 с; `gemini_ipv4 = false` — старое поведение).
10. `make smells` после каждого файла; при переборе — п.7 даёт запас (app.py −~60 строк).

## 4. kaban-doeba (TDD)
Config: дефолты (цепочка из 4 ключей, ipv4 true, 90, chain_delays []); цепочка с моделью без цены/окна → `ValidationError`;
ключ без «:» → ошибка; пользовательский toml с `[alternatives.narrator]` таблицей по-прежнему грузится (совместимость config.toml).
Gemini adapter: `HttpOptions.timeout == gemini_timeout_s*1000` (не `timeout_s`); при `gemini_ipv4` `client_args["transport"]` —
`httpx.HTTPTransport` с `local_address="0.0.0.0"` (monkeypatch `httpx.HTTPTransport` фейком, сеть не трогать); при `false` —
`client_args` нет/без transport; Anthropic по-прежнему `timeout_s`.
retry: `on_start` зовётся перед каждой попыткой с номером (1..n), и при успехе, и при transient, и при fatal; без `on_start` — как раньше;
порядок `on_start(1), on_attempt(1), on_start(2)…`.
Journal: `note_start` пишет строку в `journal/attempts.log`, `segments()` его не видит, `drop_orphan_blobs`/`records_for` не ломаются;
MasterSession с журналом — строка на каждую попытку, без журнала — ничего; replay-репорт с `attempts.log` в каталоге — код 0.
MasterSession policy: `policy=None` → `app_cfg.retry`; с `delays=[]` — одна попытка и `TurnFailed("network")`.
Summarizer: `soft_failure(TurnFailed("network"))` True (`fatal`, `rounds` — False); `try_scene` при сети у primary → backup; оба по сети →
`(None, True)` → `fallback_summary`, тег `refusal_fallback`, граница завершена, `failed_role is None`
(перевернуть `test_network_summarizer_still_gives_menu…`); fatal — по-прежнему меню; primary с backup идёт на `chain_delays`
(1 попытка), backup — полные delays.
models/next_in_chain: середина → следующий; последний → None; не в цепочке (Claude, mock) → None; пустая цепочка → None;
`model_options` содержит ключи цепочки без повторов и прежний порядок первых трёх.
GameApp auto_switch: ход `network` на модели цепочки → `adapter_factory(next)`, строка игроку, `models.json`, `chain_next` обновлён,
`runner.retry()` и commit; две модели подряд по сети → третья; вся цепочка по сети → меню ошибки, `models.json` = последняя;
summarizer на упавшей модели → переведён, на другой — нет; `auto_chain=False` → меню сразу; `refusal`/`invalid`/`fatal` → без переключения;
фабрика бросила `MissingKey` → строка ошибки и меню; после ручного `/model` на модель вне цепочки `chain_next` False.
Меню: `network` + «сменить модель» → выбранная ставится обеим ролям, строка про обе; `refusal` → как раньше одна роль;
`failed_role == "summarizer"` → только summarizer; TUI-пикер `/model` — без изменений (`test_tui_live1`, `test_tui_entry_points`
с 6 пунктами меню).
Архитектурный сторож: `httpx` импортируется в `get_client` лениво (`test_llm_imports_sdks_only_lazily…` не про httpx, но стиль тот же).
mutmut (сверено grep-ом; «новая» — создаётся в партии): `ai_dm.llm.gemini_adapter:GeminiAdapter.get_client`;
`ai_dm.llm.retry:call_with_retries`; `ai_dm.llm.journal:Journal.note_start` (новая); `ai_dm.master.session:MasterSession.call`;
`ai_dm.master.summarizer:soft_failure`, `SummarizerSession.run_scene`, `SummarizerSession.run_chapter`;
`ai_dm.game.turn:TurnRunner.fast_policy` (новая), `TurnRunner.new_session`, `TurnRunner.new_summarizer_session`;
`ai_dm.game.models:next_in_chain` (новая), `model_options` (переезд); `ai_dm.game.app:GameApp.after_turn`, `GameApp.auto_switch` (новая),
`GameApp.sync_chain` (новая), `GameApp.choose_error`, `GameApp.choose_model`, `GameApp.set_narrator`;
`ai_dm.config.app:AppConfig.check_models_known`. `make cov` один раз в конце; TUI-флак `test_second_ctrl_c…` известен.

## 5. Критерии готовности
Тесты зелёные, cov ≥ 97 %, smells ≤ 200, ruff/dead чисто, mutmut по списку без живых (кроме эквивалентных/текста);
`ai-dm --mock` и `--replay-report` старого репорта без сетевых сбоев — код 0; живые вызовы в партии не делаются;
ревью mama-kaban; чек-лист checklist-t60-live.md для ЖП1 (#18п).

## 6. Smells (нулевой баланс)
Рост: `auto_switch` (цикл), `choose_model` (третья ветка), `get_client` (ветка), `call` (+лямбда), `check_models_known` (+цикл).
Компенсация: вынос `model_options`/`check_model`/models.json в `game/models.py` (app.py 529 строк → ~470) и `write_models` вместо
хвоста `set_narrator` (сейчас 46 строк). Если всё равно 201+ — упростить `set_narrator`: общий `follow_profile(role)` для world и summarizer
(две одинаковые ветки — готовый кандидат «similar code»).

## 7. Оценка
papa ~110 тыс. (факт); kaban 100–130; doeba 200–250; mama ~30. Итого ≈ 0,45–0,5 млн.

## 8. Риски
- Репорты с сетевыми сбоями (t396: 503 ×4 summarizer) при `--replay-report` расходятся: с `chain_delays=[]` вторая transient-запись
  не читается (прецедент AD1 Q4) — код 1 ожидаем, остальные репорты не задеты (схема запросов и `request_fingerprint` не меняются).
- `local_address="0.0.0.0"` отключает IPv6 целиком; если провайдер даст только IPv6 — ошибка connect → меню; флаг выключается
  в config.toml. При своём transport httpx игнорирует `verify` из SDK → `SSL_CERT_FILE`/`SSL_CERT_DIR` не учитываются (certifi по умолчанию).
- 90 с на фазу: ответ argon/3.8-flash на 16000 токенов дольше 90 с без байта — ReadTimeout → следующая модель (сервер режет на 180 с
  `X-Server-Timeout`). Следить в ЖП1.
- `chain_delays=[]` игнорирует `retry_after` у 429 — переключение вместо ожидания; для платного тарифа приемлемо.
- World-роль (flash-lite) по сети — по-прежнему меню, цепочки нет (кандидат в BACKLOG при ЖП1).
- Авто-переключение пишет `models.json` навсегда — вернуться на 3.8-flash руками (`/model`); строка игроку это говорит.
- `attempts.log` без ротации (~100 Б/попытка; 10 тыс. попыток ≈ 1 МБ).
- Создание героя (`ui/hero_session.RetryMenu`) и `/import` — без цепочки и IPv4-переключения ролей; только адаптер (IPv4/таймаут
  действуют, т.к. это тот же `GeminiAdapter`).

## 9. Вопросы проектировщику (рекомендации papa)
1. Форма цепочки: (а) `[llm] narrator_chain = ["provider:model", …]` — ключи меню, max_tokens от `roles.narrator`, `alternatives.narrator`
   не трогается; (б) `[[chain.narrator]]` таблицы `ModelRole`. Рек.: (а).
2. Повторы при наличии следующей модели/backup: (а) `[retry] chain_delays = []` — переключение после первой сетевой ошибки;
   (б) полные `[1,3,10]` (≈30 с на модель при быстрых 503). Рек.: (а).
3. Авто-переключение рассказчика по цепочке с записью `models.json`, строкой игроку и переводом summarizer, если он на упавшей модели;
   не в mock/replay: (а) да; (б) только через меню. Рек.: (а).
4. «Обе роли» в меню ошибки: (а) при `network` выбранная модель ставится narrator и summarizer; (б) считать покрытым цепочкой и backup,
   меню не менять. Рек.: (а) (дёшево, по роадмапу).
5. Лог старта попытки: (а) `journal/attempts.log` строкой на старте (`Journal.note_start`, `on_start` в retry); (б) не делать
   (достаточно IPv4+90 с). Рек.: (а).
6. `create_cache` при 5xx: (а) оставить (после переключения упавшая модель не зовётся; кэш восстановится в сцене);
   (б) `caches[key] = None` до смены ключа. Рек.: (а).
7. `httpx>=0.28` явной зависимостью в pyproject: (а) да; (б) нет (транзитивно). Рек.: (а).
8. Дефолт summarizer после миграции: (а) оставить `gemini-3.5-flash-lite`, пользователь держит `[roles.summarizer]` = 3-flash-preview
   в config.toml (отказы flash-lite 12.10 — тема ТО/ТС); (б) `gemini-3-flash-preview` в дефолты (`roles` и `profiles.gemini`),
   +0.2/+0.5 $ за 1M. Рек.: (а) — дисциплина объёма партии.
9. IPv4-транспорт и для Anthropic (`http_client=` SDK): (а) нет — только Gemini, как `gemini_*` флаги; (б) да. Рек.: (а).

## 10. Решения проектировщика (2026-10-15)
Q1 (а), Q2 (а), **Q3 (б) — переключение рассказчика только через меню ошибки**, Q4 (а), Q5 (а), Q6 (а), Q7 (а), Q8 (а), Q9 (а).
Следствие Q3 (б): п.1.5 (`auto_switch`, `auto_chain`, строка игроку) не делается; уточнение по цепочке и повторам рассказчика — ниже.
Уточнение (проектировщик, 2026-10-15): рассказчик — полные повторы `delays` (флаг `chain_next`/`fast_policy` у `MasterSession` не нужен);
`chain_delays = []` — только для primary summarizer при наличии backup. `narrator_chain` остаётся и задаёт порядок моделей в меню
ошибки: первой предлагается следующая по цепочке от текущей модели (`next_in_chain`). Шаги kaban/doeba и mutmut-список про
`auto_switch`/`auto_chain`/`sync_chain` вычеркнуть, smells пересчитать.

## Правки по ревью: Ревью Т60 «Сеть» (мама-кабан, 2026-10-15) (бывш. docs/decisions/t60-review.md)

Проверено: `git diff` по src/ и pyproject.toml, новый `src/ai_dm/game/models.py`, сверка с docs/plan-t60.md (с учётом раздела 10). tests/** не ревьюились.

### Хорошо
- Авто-переключения нет, у MasterSession нет `chain_next`/`fast_policy` — по разделу 10.
- `chain_delays` применяется только к primary summarizer при наличии backup (turn.py `new_summarizer_session`); backup идёт с полной политикой.
- `narrator_chain` валидируется (формат ключа, цена, окно) в AppConfig.
- Вынос models.json/check_model/model_options в `game/models.py` — чисто, поведение то же.

### Обязательные правки
1. **Порядок по цепочке не доходит до TUI и /model.** `GameApp.model_options()` (app.py:166) зовёт `model_options(self.settings.app)` без `current`. Им пользуются `ui/tui/app.py:454` (ModelModal — основной путь выбора модели в TUI после меню ошибки) и `game/commands.py:80`. Значит в TUI первой в списке НЕ будет `next_in_chain` — главная цель п. narrator_chain из раздела 10 не выполнена. Предложение: `GameApp.model_options()` возвращает `model_options(self.settings.app, self.current_key())` и `menu_for` зовёт его же (убрать дубль).

### Желательные правки
2. `ui/hero_session.py:4` импортирует `check_model, model_options` из `ai_dm.game.app` — работает только как побочный реимпорт. Импортировать из `ai_dm.game.models`.
3. `switch_role == "both"`: `set_narrator(key)` и `set_summarizer(key)` создают два разных адаптера одной модели; в `new_summarizer_session` проверка `adapter is not self.adapter` истинна, и создаётся бесполезный backup на той же модели (primary с `chain_delays=[]` → одна попытка, затем backup с полными повторами). По сути работает, но лучше в ветке both после `set_narrator` ставить `self.runner.summarizer_adapter = self.runner.adapter` (или сравнивать в turn.py по `info()` provider+model, а не по identity).
4. `gemini_adapter.py`: при `gemini_ipv4=true` свой `httpx.HTTPTransport` теряет SSL-контекст genai (SSL_CERT_FILE) — в комментарии toml это сказано, ок; но `async_client_args` не задан — если где-то используется async-клиент genai, IPv4 на него не распространится. Проверить, что async не используется, либо дописать комментарий.
5. `GameApp.failed_reason` выставляется в `after_turn` до проверки committed — ок, но не сбрасывается при загрузке сейва/новом ходе вне after_turn; убедиться, что `choose_error` недостижим без свежего after_turn (сейчас похоже так).

### Оценка заявленных отклонений
- `Journal.note_start(*fields)` позиционно — приемлемо: порядок полей задокументирован в комментарии, вызов один (MasterSession.note_start). Минус — нет проверки числа полей; не критично.
- `menu_for` словарём — ок, поведение то же (None для прочих). Небольшой минус: списки создаются на каждый вызов, неважно.
- Удаление `GameApp.models_path`/`read_models` — ок, внешних вызовов в src нет (проверить, что тесты doeba не на них).
- Политика summarizer в `new_summarizer_session` без `fast_policy` — соответствует разделу 10, ок. `MasterSession(policy=...)` с `policy or app_cfg.retry` — ок.
- `both` только если failed_role не summarizer — разумно: если упал именно summarizer на границе, менять рассказчика незачем. Соответствует п.7 плана по смыслу.

### Вопросы проектировщику
- В ветке `both` при сбое сети модель рассказчика пишется в models.json, а summarizer — только на сессию. Это ожидаемо?
- `SOFT_REASONS` теперь включает `network` — сетевой сбой summarizer при наличии backup больше не валит ход (уходит в backup/запасную выжимку). Подтвердить, что так задумано (план Q-решения, вероятно, да).

**Вердикт:** нужны правки (п.1 обязательно).

### Решения проектировщика (2026-10-15)
- Правка 1: порядок `narrator_chain` везде. `GameApp.model_options()` передаёт `current=self.current_key()`, `menu_for` зовёт этот же метод, так что `/model` и TUI-пикер тоже начинают со следующей по цепочке модели.
- Summarizer в ветке `both` меняется только на сессию, `models.json` не трогаем (как сейчас).
- `network` в `SOFT_REASONS` подтверждён планом (раздел 10).

### Сделано по правкам 2-5
- 2: `ui/hero_session.py` импортирует `check_model`, `model_options` из `ai_dm.game.models`.
- 3: в ветке `both` после `set_narrator` и `set_summarizer` стоит `runner.summarizer_adapter = runner.adapter`: лишний backup на той же модели не создаётся.
- 4: async-клиент genai в `src/ai_dm/llm` не используется; комментарий в `GeminiAdapter.get_client`.
- 5: меню ошибки достижимо без `after_turn` только через `load()` (недостроенная граница); `GameApp.load` сбрасывает `failed_reason`.
- 1: сделана (см. выше).

### Раунд 2 (мама-кабан, 2026-10-15)
Проверен текущий `git diff` src/.
- 1: ок. `GameApp.model_options()` передаёт `current_key()`, `menu_for` (model_choice) вызывает этот метод, TUI-пикер и `/model` получают тот же порядок.
- 2: ок, `hero_session` импортирует из `game.models`.
- 3: ок. В ветке `both` `summarizer_adapter = runner.adapter` ставится только при `error is None`. `summarizer_model` уже выставлен в `set_summarizer` и совпадает с моделью рассказчика, поэтому `new_summarizer_session` не создаёт backup.
- 4: ок, комментарий есть.
- 5: ок, `load()` сбрасывает `failed_reason`.

Мелочь (желательно, не блокирует): после `choose_model` поле `switch_role` не возвращается в `"narrator"`. Если после сбоя summarizer игрок откроет `/model` или TUI-пикер вне меню ошибки, `current_key()` возьмёт ключ summarizer, и порядок в списке будет от него. На поведение (какую роль меняет `/model`) это не влияет. Можно сбрасывать `switch_role = "narrator"` в конце `choose_model`.

**Вердикт раунда 2:** можно мержить.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **Т60 «Сеть» ✅ закоммичена 2026-10-15:** план docs/plan-t60.md (решения проектировщика — §10: Q3 (б) авто-переключения нет, рассказчик с полными повторами, `chain_delays=[]` только у primary summarizer с backup; `narrator_chain` — порядок моделей в меню ошибки, `/model` и TUI). Код: `[llm] gemini_ipv4` (IPv4-транспорт httpx), `[retry] gemini_timeout_s=90`, `chain_delays`, `narrator_chain` (4 модели), `network` в SOFT_REASONS, при network-сбое хода меню ставит модель обеим ролям (summarizer — только на сессию), `journal/attempts.log` (`on_start`), новый модуль game/models.py, `httpx>=0.28`. Ревью 2 раунда — docs/plan-t60.md. Тесты 16290 passed, cov 97,55 %, smells 200/200, dead чисто. Расход ≈ 0,48 млн. Живой прогон — в ЖП1 (чек-лист checklist-t60-live.md, не коммитить); пользовательский config.toml можно упростить (argon/3-flash-preview цены/окна теперь в дефолтах). **Дальше:** 17а аудит К7д+B59+Т60 (kaban-svekrov) и разбор полётов (kaban-test), затем 18 ТВ, 18п ЖП1.
