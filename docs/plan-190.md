# Шаг 190. Первый запуск: ввод ключа в игре (BACKLOG 190)

Груминг: свинопас и свекровь, отчёты в scratchpad сессии 2026-10-28 (svinopas-190.md, svekrov-190-gruming.md).
План папы-кабана — впереди.

## Решения

Проектировщик, 2026-10-28, окна груминга (номера — вопросы свинопаса):

- 9. Мастер нужен: игрок вставляет ключ прямо в игре.
- 1. Мастер открывается при запуске, если ключа нет нигде, и в игре есть команда `/key` (добавить или сменить ключ).
- 2. В списке четыре провайдера: OpenRouter (первым), Gemini, Anthropic, OpenAI.
- 3. Провайдер из мастера запоминается и становится рассказчиком по умолчанию (меняет правило 184
  «хостер сам не выбирается»).
- 4. Ключ хранится строкой в том `.env`, который игра уже читает (`~/.config/ai-dm/.env`, права 600). Переменные
  окружения и `.env` разработчика продолжают работать: «вместе с», а не «вместо». Принятый риск: ключ на диске
  открытым текстом.
- 5. Ключ проверяется пробным запросом (бесплатный список моделей); неверный — «ключ не подошёл, ещё раз?». Живая
  приёмка — проектировщик, в тестах мок.
- 6. Ключ при вводе скрыт, после ввода видны последние 4 символа.
- 7. Ключ уже есть в окружении или `.env` — мастер не показывается, всё как сейчас.
- 8. В мастере ссылка «где взять ключ» на сайт провайдера (позже заменят на гайд 192).
- 10. В мастере только провайдер; модель — по умолчанию (OpenRouter — `deepseek/deepseek-v4-flash`), смена — `/model`.
- 11. 401/403 посреди игры — подсказка «ключ <провайдер> не принят — введите новый: /key», ход не теряется.
- 12. Нет сети при вводе — ключ сохраняется без проверки: «не проверил: нет сети, проверю на первом ходу».

- 13. В `.env` уже есть ключ этого провайдера — «ключ уже есть — заменить?»; при «да» меняется только его строка,
  остальное не трогается; пишется в тот `.env`, который игра читает.
- 14. Тест-страж: ключ-маркер через мастер, ход на моке с 401 и репортом — маркера нет в файлах мира и в выводе.
- 15. Донатов в мастере нет — целиком в 194.
- Р1–Р7 (развилки плана папы, окно 2026-10-28): приняты рекомендации — Р1 (а) `AI_DM_PROVIDER` в `.env`; Р2 с
  хвостом «затем «1. повтор»»; Р3 (а); Р4 (а); Р5 (а); Р6 (а); Р7 (а) две партии.
- Умолчание видимого текста «Ключ …abcd сохранён в <путь>» — принято (2026-10-28).

## План (папа-кабан, 2026-10-28)

Контур: вне msa; режим: встроить. Входы: решения 1–15 выше, отчёт свинопаса (5 мест запроса ключа) и аудит
свекрови (scratchpad сессии 2026-10-28). Размер — M, две партии по границе слоёв (как 164 и 188).

**Задача:** игрок без ключа вводит его прямо в игре (при старте и по `/key`), ключ проверяется пробным запросом,
ложится в тот `.env`, который игра читает, провайдер мастера становится рассказчиком по умолчанию.

### Правила, которые меняются (первым пунктом аппрува)

1. Старт без ключа. Было: `make_game_adapter` → `make_adapter` → `raise MissingKey("нет ключа …")`
   (`llm/factory.py:15-17`), `prepare` печатает и возвращает 1 (`ui/cli.py:932-934`) → станет: в `prepare` перед
   `pick_narrator` (`ui/cli.py:887`) — `if not any(setup.secrets) and not (args.mock or args.replay): мастер`;
   отмена мастера (Esc, конец ввода) — дальше как сейчас, тот же текст `MissingKey` и код 1 (тесты
   `test_ui_cli.py:51-105` не меняются).
2. Рассказчик по умолчанию, `pick_narrator` (`ui/cli.py:340-363`). Было: `--provider → models.json мира →
   roles.narrator (если ключ) → первый встроенный профиль с ключом` → станет: `--provider → models.json мира →
   профиль из AI_DM_PROVIDER (при Р1 = а) → roles.narrator (если ключ) → …`. Строка `# профили хостеров … сами не
   выбираются` (`cli.py:357`) остаётся верной для автоподбора по ключам; меняется только явная память мастера
   (решение 3 этого шага отменяет решение 7 шага 184 — `docs/plan-184.md:24`).
3. Ошибка ключа посреди игры. Было: `translate_error` → `LlmFatal(text)` без кода (`openai_adapter.py:137-147`,
   `anthropic_adapter.py:99-108`, `gemini_adapter.py:220-229`), `MasterSession.call` → `TurnFailed("fatal", …)`
   (`master/session.py:283-284`), игрок видит `str(failure)` (`game/turn.py:273`, `ui/hero_session.py:61`) →
   станет: `LlmFatal(text, status=code)`; `status in (401, 403)` (Gemini — ещё `code == 400` и «API key not valid»
   в тексте: живая проверка 2026-10-28 без ключа — Gemini отвечает 400, не 401) → `TurnFailed("auth", …,
   detail=<провайдер>)`; подсказка игроку — `AUTH_HINT` (решение 11), меню ошибки то же (`retry` остаётся — ход не
   теряется). `"auth"` нет в `SOFT_REASONS` (`master/session.py:90`) и `RETRY_NOTES` (`game/turn.py:40`) —
   повторов и смягчения нет, как у `fatal`.
4. Проверка ключа (решение 5). Новое: `Adapter.probe()` — список моделей: OpenAI `client.models.list()`,
   Anthropic `client.models.list(limit=1)`, Gemini `client.models.list(config={"page_size": 1})` (сигнатуры
   проверены в `.venv`: openai 3.35.1, anthropic 1.11.0, google-genai 2.28.0). У OpenRouter `GET /models` открыт без
   ключа (проверено curl: 200), поэтому у хостера путь проверки — поле `probe_path` в `[providers.<имя>]`
   (`config/app.py:32 ProviderHost`, умолчание `"/models"`), у openrouter в `app_defaults.toml:142` —
   `probe_path = "/key"` (без ключа — 401, проверено).

**Поведение:** меняется — старт без ключа (мастер вместо выхода), `pick_narrator`, подсказка при 401/403,
новая команда `/key`. Всё остальное (ключ в env/`.env`, `--mock`, `--replay`, `--import`) — как сейчас.
**Вне ai-dm:** нет (ссылки «где взять ключ» — страницы провайдеров, живые 2026-10-28: openrouter.ai/keys 200,
aistudio.google.com/apikey 200, console.anthropic.com/settings/keys 200, platform.openai.com/api-keys 403 — защита
от ботов, страница есть).

### Модули, файлы, функции

Партия 1 (ядро, простой режим, старт, `/key`, 401):
- `src/ai_dm/llm/keys.py` — `write_dotenv_var(path, name, value)` (новая): читает строки файла, если есть;
  заменяет первую строку с этим именем, остальные строки и комментарии не трогает; иначе дописывает; запись через
  `.tmp` + `replace`, как `write_audio_prefs` (`config/user.py:74-78`), `mkdir(parents)`, `chmod 0o600`
  (на Windows — без эффекта, это 189). `parse_dotenv` — без правок (им же проверяется «ключ уже есть»).
- `src/ai_dm/llm/errors.py` — `LlmFatal.__init__(message, status=None)` (новая, класса `LlmFatal` сейчас без
  `__init__`), `is_auth_error(error)` (новая): `status in (401, 403)` или `status == 400 and "API key not valid" in
  str(error)`.
- `src/ai_dm/llm/openai_adapter.py` `OpenAIAdapter.translate_error` (:137), `.probe` (новая); `ChatCompletionsAdapter`
  (`chat_adapter.py`) — `.probe` (новая): `client.get(self.probe_path, cast_to=object)`; `anthropic_adapter.py`
  `AnthropicAdapter.translate_error` (:99), `.probe` (новая); `gemini_adapter.py` `GeminiAdapter.translate_error`
  (:220), `.probe` (новая). `probe()` — ошибки через тот же `translate_error`, ключ в тексте уже вычищен `redact`.
- `src/ai_dm/config/app.py` `ProviderHost` — `probe_path: str = "/models"`; `app_defaults.toml:142` — у openrouter
  `probe_path = "/key"`.
- `src/ai_dm/llm/factory.py` — `make_adapter` (:9) разбивается: выбор ключа остаётся, создание класса уходит в
  `adapter_for(provider, model, app_cfg, key)` (новая); `verify_key(provider, key, app_cfg)` (новая) →
  `"ok" | "invalid" | ("unverified", текст)`: `adapter_for(...).probe()`; `LlmFatal` + `is_auth_error` → `invalid`;
  `LlmTransient` (сеть, 5xx, 429) и прочие `LlmFatal` → `unverified`. Касание `make_adapter` — хвост 213.
- `src/ai_dm/ui/key_session.py` (новый) — `KeyDeps(app_cfg, env, dotenv_path, secrets, verify=verify_key)`,
  `PROVIDERS` (порядок решения 2: openrouter, gemini, anthropic, openai; подпись, имя переменной — `KEY_VARS` или
  `providers[<имя>].key_env`, профиль для памяти — openrouter → `deepseek` (решение 10: модель
  `deepseek/deepseek-v4-flash` — это профиль `deepseek`, `app_defaults.toml:295`), остальные — одноимённый; ссылка
  «где взять»), `KeySession.start/submit` по образцу `HeroSession` (`ui/hero_session.py:87-125`): состояния
  `provider → (confirm →) key → done`; `submit(None)` — выход без записи; `submit(ключ)`: `verify` → `invalid` →
  заметка «ключ не подошёл, ещё раз?» и снова `key`; `ok`/`unverified` → `write_dotenv_var`, `secrets.append(key)`,
  при старте — ещё `AI_DM_PROVIDER` (при Р1 = а); итог в полях `saved`, `provider`, `tail` (последние 4 символа).
  Пустой ввод — повтор подсказки. `confirm` — только если `parse_dotenv(dotenv_path)` уже содержит переменную
  (решение 13): меню «да/нет», «нет» — выход без записи.
- `src/ai_dm/ui/io.py` `StdinInput.read_secret(prompt)` (новая) — `getpass.getpass`; `tests/slots_kit.py:19
  ScriptedInput` — `read_secret = read`.
- `src/ai_dm/ui/cli.py` — `prepare` (:851, хук правила 1), `pick_narrator` (:340, правило 2: `read_var("AI_DM_PROVIDER",
  env, dotenv_path)` → `profile_narrator`; неизвестный профиль — та же `ValueError`, что у `--provider`, решение 14
  шага 184), `enter_key_simple(stdin, stdout, session)` (новая, как `create_hero_simple` :302; в состоянии `key`
  читает `stdin.read_secret`), `enter_key(stdin, stdout, notes, setup, session)` (новая, как `create_hero` :311:
  TUI → `tui.enter_key`, сбой → простой режим; в П1 — только простой), `play` (:614) и `run_tui` (:654) — передают
  `key_factory` (замыкание на `KeyDeps` из `setup` и `settings`) в `run`/`tui.run_tui`. `main`, `make_parser`,
  `import_pack` — не трогаются (213/205 по ним не срабатывают).
- `src/ai_dm/game/commands.py` — `cmd_key(app, arg)` (новая): `app.reply(request="key")`; `HELP["key"]`,
  `COMMANDS["key"]` (подсказки TUI берут `HELP` — `tui/app.py:51`).
- `src/ai_dm/game/app.py` — `Reply.__init__` (:82, поле `request=None`), `GameApp.rekey(provider)` (новая): у каждой
  роли (narrator — `runner.adapter`, `world_adapter`, `summarizer_adapter`), чей `info().provider == provider`,
  адаптер пересоздаётся `adapter_factory(provider, model)` (читает `.env` заново); `set_narrator` не трогается —
  его `follow_provider` при том же профиле адаптеры world/summarizer не пересобирает (`app.py:559`), а им нужен
  новый ключ; `write_models` не вызывается. Возвращает строку игроку.
- `src/ai_dm/ui/session.py` — `Step` (:24, поле `request=None`), `PlaySession.render_step` (:149) — переносит
  `reply.request` в `step.request`.
- `src/ai_dm/ui/simple.py` `run` (:71) — параметр `key_factory=None`; после `submit`, если `step.request == "key"` и
  фабрика есть: `enter_key_simple(source, sink, key_factory())`, затем `app.rekey(...)` строкой; без фабрики —
  заметка «ввод ключа здесь недоступен».
- `src/ai_dm/master/session.py` `MasterSession.call` (:283-284) — ветка `auth`; `src/ai_dm/game/turn.py`
  `TurnRunner.failed` (:265) и `failure_hint(failure)` (новая, `REFUSAL_HINT`/`AUTH_HINT`/`str`);
  `src/ai_dm/ui/hero_session.py` `RetryMenu.fail` (:59) — тот же `failure_hint` (создание героя при 401 показывает
  ту же подсказку; сам `/key` во время создания героя — не в этом шаге).
- `README.md:20-29` — строка «первый запуск: игра сама спросит ключ; сменить — `/key`».

Партия 2 (TUI):
- `src/ai_dm/ui/tui/key_modal.py` (новый, чтобы не растить `modals.py` — 435 строк) — `KeyModal(ModalScreen)`:
  `Choices` провайдеров (как `PickerApp`, `modals.py:393`), `Input(password=True)` в состоянии `key` (Textual 8.2.8,
  `_input.py:359`), заметки сессии в `Static`; `submit` ключа — `run_worker(thread=True)` как `HeroCreateApp.start_step`
  (`create.py:87-96`); результат — `dismiss(session)`; `KeyApp(App)` — оболочка до игры: `on_mount →
  push_screen(KeyModal, exit)`.
- `src/ai_dm/ui/tui/__init__.py` — `enter_key(session)` (новая, как `create_hero` :38, `TuiStartError`).
- `src/ai_dm/ui/tui/app.py` `AiDmApp.__init__` (:77, `key_factory`), `finish_turn` (:452: `step.request == "key"` →
  `push_screen(KeyModal(key_factory()), self.key_entered)`), `key_entered` (новая: `game.rekey` в воркере →
  строка в ленту, как `finish_switch` :602); `src/ai_dm/ui/tui/strings.py` — `MODAL_TITLES["/key"]`, тексты мастера.
- `src/ai_dm/ui/cli.py` `enter_key` — ветка TUI; `run_tui` — `key_factory` в `tui.run_tui`.

### Партии по шагам

1. П1 — `keys.py:write_dotenv_var`, `errors.py`, `probe` трёх адаптеров + `probe_path`, `factory.py:adapter_for/
   verify_key` — тесты `tests/unit/llm/test_llm_keys.py` (замена строки, дописывание, комментарии целы, 600,
   `.tmp` нет), `test_llm_factory.py` (`verify_key` на фейковом клиенте: 200 → ok, 401 → invalid, Gemini 400 «API
   key not valid» → invalid, `ConnectError` → unverified; openrouter зовёт `/key`, не `/models`).
2. П1 — `ui/key_session.py` — тесты `tests/unit/ui/test_key_session.py` (сценарии ниже), `io.py:read_secret`.
3. П1 — `cli.py:prepare/pick_narrator/enter_key_simple/enter_key`, `commands.py:cmd_key`, `app.py:Reply/rekey`,
   `session.py:Step`, `simple.py:run`, `turn.py:failure_hint`, `master/session.py:call`, `hero_session.py:RetryMenu.fail`
   — тесты `tests/unit/ui/test_cli_key.py` (старт с мастером, страж решения 14 — `monkeypatch` `ai_dm.ui.cli.verify_key`
   и `ai_dm.ui.cli.make_adapter`), `tests/unit/game/test_game_commands.py` (`/key` → `request`, `rekey`),
   `tests/unit/game/test_t60_menu.py` (подсказка `auth`, меню то же). README. `make mutate FUNCS=…` по списку ниже,
   `make mutate-diff`; 213 — `make_adapter` (segfault-мутанты перепроверить узким `TESTS=tests/unit/llm`).
4. П2 — `tui/key_modal.py`, `tui/__init__.py:enter_key`, `tui/app.py`, `strings.py`, `cli.py:enter_key` — Pilot-тесты
   `tests/unit/ui/tui/test_tui_key.py` (маркер `slow`, как соседи): провайдер цифрой, поле скрывает ввод, итоговая
   строка с хвостом, Esc — отмена без записи; `/key` в игре открывает окно. Живая приёмка — проектировщик.

Список для mutmut (П1): `ai_dm.llm.keys:write_dotenv_var ai_dm.llm.factory:make_adapter ai_dm.llm.factory:adapter_for
ai_dm.llm.factory:verify_key ai_dm.llm.errors:is_auth_error ai_dm.llm.openai_adapter:OpenAIAdapter.translate_error
ai_dm.llm.openai_adapter:OpenAIAdapter.probe ai_dm.llm.chat_adapter:ChatCompletionsAdapter.probe
ai_dm.llm.anthropic_adapter:AnthropicAdapter.translate_error ai_dm.llm.anthropic_adapter:AnthropicAdapter.probe
ai_dm.llm.gemini_adapter:GeminiAdapter.translate_error ai_dm.llm.gemini_adapter:GeminiAdapter.probe
ai_dm.ui.key_session:KeySession.start ai_dm.ui.key_session:KeySession.submit ai_dm.ui.cli:prepare
ai_dm.ui.cli:pick_narrator ai_dm.ui.cli:enter_key_simple ai_dm.ui.cli:enter_key ai_dm.game.commands:cmd_key
ai_dm.game.app:GameApp.rekey ai_dm.ui.simple:run ai_dm.ui.session:PlaySession.render_step
ai_dm.game.turn:TurnRunner.failed ai_dm.game.turn:failure_hint ai_dm.master.session:MasterSession.call
ai_dm.ui.hero_session:RetryMenu.fail` (новые: `write_dotenv_var`, `adapter_for`, `verify_key`, `is_auth_error`, все
`probe`, `KeySession.*`, `enter_key_simple`, `enter_key`, `cmd_key`, `rekey`, `failure_hint`; остальные есть — grep
2026-10-28). П2: `ai_dm.ui.tui.app:AiDmApp.finish_turn ai_dm.ui.tui.app:AiDmApp.key_entered
ai_dm.ui.tui.key_modal:KeyModal.*` (`TESTS=tests/unit/ui/tui`).

### Тестовые сценарии (для кабана-доебы)

Все — ожидание, не проверено (кода нет); живых вызовов в тестах нет, `verify` — мок.
- `.env` нет; старт `--new` без ключей, ввод «1», ключ → `verify` ok → файл `<config>/.env` создан, одна строка
  `OPENROUTER_API_KEY=…`, права 600, `AI_DM_PROVIDER=deepseek` (при Р1 = а); рассказчик — `openrouter:
  deepseek/deepseek-v4-flash`; в выводе — последние 4 символа, полного ключа нет.
- `./.env` рядом есть (разработчик) без ключей → мастер пишет в `./.env`, не в `~/.config` (решение 13).
- Ключ в `env` или `.env` любого провайдера → мастера нет, вывод как сейчас (`test_key_from_env_is_enough…`).
- Старт без ключей и без строк ввода (как `test_without_key_and_mock_explains…`) → меню мастера, затем прежний текст
  «нет ключа GEMINI_API_KEY (… .env)», код 1, файлы не созданы.
- `--mock` / `--replay` без ключей → мастера нет.
- `verify` → invalid → «ключ не подошёл, ещё раз?», файл не записан; второй ввод ok → записан.
- `verify` → unverified (сеть) → файл записан, заметка «не проверил: нет сети, проверю на первом ходу».
- `/key` в игре, провайдер с ключом в `.env` → «ключ уже есть — заменить?»; «нет» → файл байт в байт прежний;
  «да» → меняется только эта строка, комментарии и другие строки те же.
- `/key` в игре для провайдера текущего рассказчика → `rekey`: адаптеры narrator и world/summarizer этого
  провайдера созданы фабрикой заново (у фейковой фабрики счётчик), `models.json` не менялся.
- Ход с адаптером, бросающим `LlmFatal(status=401)` → `failure.reason == "auth"`, подсказка содержит провайдера и
  `/key`, `pending == "error_menu"`, «1» (повтор) после `rekey` проходит ход; `status=500` → как раньше.
  Gemini: `code=400` + «API key not valid» → `auth`; `code=400` без этих слов → `fatal`.
- Страж (решение 14): маркер `KEY-MARKER-…` через мастер (`cli`, `monkeypatch` `verify_key` → ok, `make_adapter` →
  адаптер с 401), ход, репорт записан → маркера нет в `out.text` и ни в одном файле под `saves/` (rglob, включая
  `journal/calls-*.jsonl`, `attempts.log`, `issues/*/report.md`); хвост из 4 символов допустим.
- `AI_DM_PROVIDER=nope` в `.env` → «Ошибка: нет профиля nope; есть: …», код 1 (как `--provider`).
- Проверка руками (проектировщик, живые вызовы): `uv run ai-dm --new` в чистом `AI_DM_CONFIG_DIR` → мастер в TUI,
  OpenRouter, неверный ключ → отказ; верный → игра на deepseek-v4-flash; `cat $AI_DM_CONFIG_DIR/.env`, `ls -l` → 600.

### Развилки и риски

- Р1. Где помнить провайдера мастера (решение 3). (а) строка `AI_DM_PROVIDER=<профиль>` в том же `.env`, читается
  `read_var` в `pick_narrator` — одна запись, одно чтение, переменной окружения можно перекрыть, как
  `AI_DM_CONFIG_DIR`; (б) файл игры `~/.config/ai-dm/narrator.toml` слоем поверх `config.toml`, как `audio.toml`
  (`config/user.py:50-57`) — чище по смыслу («настройка, не секрет»), но третий слой в `load_user_settings` и новое
  поле конфига. Рекомендую (а). Разблокирует: `pick_narrator`, `KeySession`.
- Р2. Текст подсказки при 401 (решение 11 даёт начало): «Ключ <провайдер> не принят — введите новый: /key, затем
  «1. повтор».» Рекомендую с хвостом про повтор: иначе игрок не знает, что ход не потерян.
- Р3. `/key` в игре для провайдера, отличного от текущего: (а) только сохранить + «сменить модель — /model»
  (решение 10), память `AI_DM_PROVIDER` не трогать; (б) ещё и переключить рассказчика (`set_narrator` на профиль
  провайдера). Рекомендую (а): переключение — дело `/model`, память — дело мастера первого запуска.
- Р4. Ключ провайдера стоит в переменной окружения, игрок вводит новый через `/key`: `.env` его не перекроет
  (`read_var` — env первым, `keys.py:37`). (а) сохранить и предупредить «переменная <VAR> перекрывает .env — новый
  ключ заработает после её снятия»; (б) отказать. Рекомендую (а).
- Р5. Ошибка проверки не 401 и не сеть (404 пути, 5xx): (а) сохранить как при «нет сети» с текстом «не проверил:
  <ошибка>»; (б) считать «не подошёл». Рекомендую (а): решение 12 про сеть, остальное — не вина ключа.
- Р6. Мастер при `--import` без ключа: (а) не показывать, прежний `MissingKey` (`import_pack`, `cli.py:567`);
  (б) показывать. Рекомендую (а): `--import` — путь продвинутого игрока, `import_pack` не трогаем (205).
- Р7. Партии: (а) две — ядро/простой режим и TUI; (б) одна. Рекомендую (а): П1 закрывает поведение и стража,
  П2 — Pilot-тесты (`slow`), ревью по слоям, как 164/188.
- Риски: ключ на диске открытым текстом — принят (решение 4). Распознавание 401 по статусу — живьём не проверено
  (OpenRouter/Anthropic/OpenAI по докам 401, Gemini — 400 с текстом, проверено без ключа curl); приёмка —
  проектировщик. `getpass` вне терминала (не tty) пишет предупреждение и показывает ввод — простой режим под пайпом;
  в тестах `ScriptedInput`. `smells` 199/200 — новые функции короткие, `KeySession.submit` разбить по состояниям.
  `probe` OpenRouter `/key` — недокументированная для SDK `client.get`, при смене API хостера — `unverified`, не
  поломка. Windows: `chmod` без эффекта (189).

### Умолчания (внутреннее)

- `AUTH_HINT`, `failure_hint` — в `game/turn.py` рядом с `REFUSAL_HINT`; причина `"auth"`, `detail` — провайдер.
- `KeySession` без терминала и сети, `verify` инъекцией (`KeyDeps.verify`), как `HeroSession.deps`.
- `Reply.request`/`Step.request` — одно поле строкой (`"key"`), не флаг: место для будущих запросов UI не
  резервируется, просто имя не булево.
- Хвост ключа — `tail = key[-4:]`, формат заметки «Ключ …abcd сохранён в <путь>» (видимое — при аппрове решения 6
  уже дано: «видны последние 4 символа»).
- При Р1 = а — имя переменной `AI_DM_PROVIDER`, значение — имя профиля (как `--provider`), openrouter → `deepseek`.
- Тесты `verify_key` — фейковый клиент с `models.list`/`get`, исключения SDK имитируются классами с `status_code`/
  `code` (как в `tests/unit/llm/llm_kit.py`).

### Открытые вопросы

нет (все развилки — Р1–Р7 выше, решает проектировщик; решения 1–15 не пересматриваются).

## Правки по ревью

П1, круг 1 (мама и свекровь, 2026-10-28; решения проектировщика — окнами 2026-10-28):
- Решение 12 (свекровь, мама): вернуть текст «нет сети» — проектировщик. При `LlmTransient` `verify_key` отдаёт
  `("unverified", "нет сети")`, сырой текст — только для прочих `LlmFatal` (Р5); в `UNVERIFIED` убрать двойную точку
  (мама). Кабану.
- Тексты вне плана (INTRO, ответ `/key` «Ключ API: выберите провайдера.», «Ключ <провайдер> подключён.», «Нет такого
  варианта.») — проектировщик: оставить как есть (предложение мамы убрать строку `cmd_key` не берётся).
- `/key` в TUI до П2 только печатает строку — проектировщик: оставить до П2, закрывает П2.
- Справочно (мама, без правки): `verify_key` не ловит `ValueError` из `adapter_for` — для провайдеров `PROVIDERS` не
  случается; `cli.enter_key` не использует `notes`/`setup` — под П2, проверить `make dead`.
- Внутренние отклонения кабана (`enter_key_simple` в `ui/simple.py`, `chosen_narrator`, `fatal_failure`) — свекровь:
  оставить.

П1, круг 2 (2026-10-28): правка «нет сети» сделана (кабан); свекровь — чисто; мама — две правки тестов доебе:
`test_verify_key_network_error_is_unverified` — сообщение ошибки отличное от «нет сети»; тест на `rstrip(".")` в
`UNVERIFIED`. «Нет сети» при 429/5xx — по решению 12 и Р5, правки нет. `/key` в TUI — решение проектировщика: до П2.

П2, вопросы кабана к папе (2026-10-28):
- `MODAL_TITLES["/key"]` → `strings.KEY_TITLE` — папа: принять отклонение (`MODAL_TITLES` — признак «ответ в окно», а не
  заголовок окна; запись в нём убрала бы ответ `/key` из ленты).
- smells 201 (`tui.run_tui`, 6 параметров) — папа: убрать `secrets` из `tui.run_tui`, `PlaySession` получает
  `game.secrets` (тот же список, что у `setup.secrets`); фейки в `test_ui_cli_sound.py`, `test_ui_cli_mode.py`. Кабану.
- Список mutmut П2 дополнен (папа): `ai_dm.ui.tui:run_tui ai_dm.ui.tui:enter_key ai_dm.ui.tui.app:AiDmApp.open_key
  ai_dm.ui.tui.app:AiDmApp.rekey ai_dm.ui.tui.app:AiDmApp.finish_rekey ai_dm.ui.cli:enter_key_tui`.
- Р8 (папа, окно 2026-10-28) — проектировщик: строку «Ключ API: выберите провайдера.» в ленте TUI под окном `/key`
  оставить.

П2, ревью мамы и аудит свекрови (2026-10-28):
- Окно ключа после сохранения остаётся с кнопкой «Закрыть» (план — сразу dismiss) — проектировщик, окно: оставить.
- Подсказка поля «Вставьте ключ (ввод скрыт, Esc — отмена)» и маска «••••» — проектировщик, окно: оставить оба.
- Мама: тест посимвольного набора ключа с цифрами через `pilot.press` при открытом окне (цифры — в поле, не выбор
  варианта) — доебе.
- Мама: уточнить комментарий к `KeyModal.check_action` (цифровые биндинги выключаются через `menu.display`) — кабану.
- Тест посимвольного ввода зелёный и без `KeyModal` в `MODALS` — папа: `KeyModal` в `MODALS` оставить (через
  `menu_ready` гасятся боевые привязки); доебе — `assert KeyModal in MODALS`, как в `test_tui_shop_modal.py`.

Мутанты П1+П2 (2026-10-29): первый прогон — 46 выживших; доеба дописал тесты, повтор и узкие повторы (Gemini/Anthropic
`translate_error`, `GameApp.rekey`) — все целевые убиты. Эквивалентные (обоснование доебы по номерам): `finish_rekey`
6/7/8/14/15/16 — меняется только форма `query_one` (тип или селектор), тот же виджет; `write_dotenv_var` 6/41/43 —
кодировка не указана (utf-8-локаль), 8/49 — `"UTF-8"` алиас, 20/23 — `split` без/с иным maxsplit, `[0]` то же, 38/39 —
имя временного файла; `GameApp.rekey` 13/15/45/47 — важна только истинность счётчика. Условия мамы (круг 3: «если в
списке мутант chmod / `busy = False`») не выполняются: chmod среди них нет, `finish_rekey` 4/11 (`busy`) убиты.
Старые строки (не из диффа a2737b5): `cli.prepare__651`, `run_tui__19/20` и segfault-мутанты `render_step`,
`MasterSession.call`, `prepare`, `pick_narrator` — не разбирались.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план папы-кабана 2026-10-28 (П1 ядро + простой режим, П2 TUI). Источник масштаба — «Итог»
`docs/plan-188.md` (тоже M, но одна партия кода); у 190 две партии и Pilot-тесты, множитель ≈ ×1,3 к 188.
Цены — тариф metrics.py от 2026-10-25 (opus/fable 4 $ вход, 20 $ выход; sonnet 2 / 10 за M), с сайтом не сверял.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Продукт: пробный запрос ключа (`probe`) | 0 | список моделей бесплатен у всех 4 провайдеров (решение 5) | — | — | — |
| Продукт: ход игры | без изменений | шаг не трогает рассказчика | — | — | — |
| Цепочка шага (разово) | ≈ 18–22 $ | ×1,3 к факту 188 (15,6 $ сессия) | оркестратору — `/compact` между П1 и П2 | ≈ 2–3 $ | ничего, если состояние в документе |
| mutmut 26 функций П1 | 0 $ (локально), ≈ 30–40 мин | фоном, `MUT_CHILDREN=4` | — | — | — |

| Партия | Время |
|---|---|
| груминг + план + смета (прошло) | ≈ 15–20 мин работы |
| П1 kaban | 30–50 мин |
| П1 doeba: cov + mutate + разбор | 45–70 мин (cov ≈ 15, mutmut фоном) |
| П1 мама ‖ свекровь + коммит | 10–20 мин |
| П2 kaban (TUI) | 20–35 мин |
| П2 doeba: Pilot + mutate + cov | 30–45 мин |
| П2 мама ‖ свекровь + коммит | 10–20 мин |
| итого | ≈ 2,7–4 ч |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban (уже прошло) | fable | ≈ 1,0–1,5 M (интервал, id запуска не сверял) | 1,5–2,1 |
| svinopas (уже прошло) | opus | ≈ 0,5–1 M (интервал) | 0,3–0,6 |
| kaban × 2 | sonnet | 4–6 M | 1,3–2,0 |
| kaban-doeba × 2–3 | sonnet | 2–3 M | 1,1–1,7 |
| mama-kaban × 2 | opus | 0,6–1 M | 1,0–1,6 |
| kaban-svekrov × 2 | opus | 1–1,5 M | 1,5–2,2 |
| оркестратор | opus | 12–18 M | 5–8 |
| Декарт (вызовов = 2 партии + 1 сводный, выжимки ≤ 400 KB) | fable | 0,6–1 M | 1–1,6 (если позовут) |
| итого | | ≈ 22–33 M | ≈ 12–20 $ |

Дороже всего — оркестратор (≈ 40 %, в 188 сессия через ночь раздула контекст до 209 K): `/compact` после коммита П1.
Папа на fable — проба (memory), не трогаю. Ревью и аудит не урезаются.

Модели: `kaban.md:model: sonnet`, `kaban-doeba.md:model: sonnet`, `mama-kaban.md:model: opus`,
`kaban-svekrov.md:model: opus`, `papa-kaban.md:model: fable`, `svinopas.md:model: opus`, `kaban-dekart.md:model: fable`
(тесть — opus, совпадает с запуском).

**Вердикт:** ок по бабкам; продукт бесплатен в эксплуатации, шаг ≈ 12–20 $.

## Итог

**Источник токенов:** `metrics.py` по `~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/53afdaea-ee6a-405e-b721-abe9814d79c3.jsonl`
(П1) и `…/8916a3bc-a9de-493d-9d8f-814a2e95872f.jsonl` (П2, ревью, mutmut); **цены:** тариф metrics.py от 2026-10-25,
https://platform.claude.com/docs/en/about-claude/pricing (с сайтом сегодня не сверял; fable по ценам Opus — как в скрипте).
Вне шага и из итога исключены: кабан мини КД (ad1ea18da734d8060, пак drunk_dragon) 0,29 $; свинопас t1341
(a9266cdf292363b32) 0,37 $ — итого 0,66 $.

| Партия | Смета | Факт |
|---|---|---|
| груминг + план + смета | 15–20 мин | ≈ 30 мин работы (свинопас 8,6, папа 18, тесть 0,6) — два папы вместо одного |
| П1 kaban | 30–50 мин | 21,8 мин работы (интервал 45) |
| П1 doeba | 45–70 мин | 21,5 мин агента; mutmut отложен в общее окно П1+П2 |
| П1 мама ‖ свекровь + коммит | 10–20 мин | ≈ 2 мин агентов (интервал 5,6) |
| П2 kaban (TUI) | 20–35 мин | 17,1 мин + папа на вопросы 4 мин |
| П2 doeba: Pilot + mutate + cov | 30–45 мин | 7 + 3,2 мин агента; mutmut П1+П2 2 ч 58 мин + повтор 09:32–12:06 (2 ч 34 мин), cov 98,15 % (22584 passed) — фоном, окно Влада |
| П2 мама ‖ свекровь (3 круга) | 10–20 мин | 3,8 / 2 мин работы (интервал до утра — простой) |
| итого | 2,7–4 ч | ≈ 2 ч работы агентов + ≈ 5,5 ч mutmut фоном; сессия П2 — интервал 15,5 ч, в т. ч. ночной простой |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| оркестратор | opus | 35,97 M (17,37 + 18,60) | 13,91 — на момент подсчёта 13:33 |
| papa-kaban | fable | 3,86 M | 5,18 |
| kaban (без КД) | sonnet | 9,29 M вместе с КД (по $ КД ≈ 3 %) | 2,89 |
| kaban-doeba | sonnet | 10,20 M | 3,62 |
| mama-kaban | opus | 1,75 M | 2,01 |
| kaban-svekrov | opus | 1,61 M | 2,01 |
| svinopas (груминг, без t1341) | opus | 3,74 M | 2,78 |
| kaban-test | opus | 0,21 M | 0,35 — на момент подсчёта 13:33 |
| итого шага | | ≈ 66,3 M | 32,76 |

Расхождение: смета 12–20 $ → факт 32,8 $. Оркестратор 13,9 $ при смете 5–8 (две сессии, пик контекста 224 K в П1,
ночь между П2 и mutmut); папа 5,2 при 1,5–2,1 (три запуска: план, вопросы П1, вопросы П2 + ROADMAP);
свинопас 2,8 при 0,3–0,6 (два запуска груминга). Кабан и доеба — в смете.

**Итого:** смета ≈ 12–20 $, 2,7–4 ч → факт 32,76 $ (без 0,66 $ вне шага), ≈ 2 ч агентов + 5,5 ч mutmut фоном.
Разбор — кабан Декарта.
