# Шаг 184 — профиль OpenAI-совместимого провайдера с настраиваемым адресом

BACKLOG 184. Груминг: свинопас + аудит свекрови (2026-10-26), ресёрч — docs/research/hosters-api-184.md.

## Суть

Игра ходит к дешёвым open-weight моделям (DeepSeek V4, Qwen3-235B) через OpenAI-совместимых хостеров; этап 0
бизнес-плана (docs/business-plan.md), вход для живой пробы 185.

## Решения

Проектировщик, 2026-10-26 (окна груминга, варианты и рекомендации свинопаса):

1. API — новый адаптер на Chat Completions (не Responses Э10а): Responses есть только у OpenRouter (бета), Chat
   Completions — у всех трёх хостеров. Зашифрованных рассуждений между ходами нет; влияние на протокол покажет 185.
2. Хостер задаётся профилем по имени в `config.toml` (адрес, имя переменной ключа, …); в `/model` —
   `openrouter:<модель>`; хостеров может быть несколько.
3. Ключ до шага 190 — переменная окружения или `.env`, имя переменной — в профиле хостера.
4. Цены и окна контекста моделей пробы вписываются в игру (в $, по ресёрчу); игрок может поправить их в своём
   `config.toml`.
5. Правила рассказчика и символов на токен — в профиле хостера, по умолчанию как у openai
   (`narrator_rules_openai.md`, 3.5).
6. Шаг закрыт, когда игра работает на OpenRouter; остальные хостеры — профилем по факту.
7. Модель хостера рассказчиком по умолчанию не становится: до 187 — только явный выбор (`/model`, `--provider`).
8. OpenRouter — главный хостер этапа 0 (проба 185, гайд 192).
9. Cloud.ru из 184 убран; вернуться при оплате в рублях (этап 2).
10. Два готовых профиля моделей — «deepseek» (deepseek-v4-flash) и «qwen» (qwen3-235b-a22b-2507), в каждом все роли
    (narrator, world, summarizer, import) на одной модели.
11. Развилки плана Р1–Р4 — по рекомендациям папы (проектировщик, 2026-10-26, одним окном): секция
    `[providers.<имя>]`; `--provider` принимает имена профилей; deepseek/qwen в меню `/model` всегда; `effort`/
    `max_tokens` deepseek как у openai, qwen — те же лимиты без `effort`.
12. Экономия цепочки по смете тестя — принята (проектировщик, 2026-10-26, «пошли сэкономим»): `/compact`
    оркестратора между П1 и П2; маме и свекрови — SendMessage в тот же контекст; свекровь после 3-го круга —
    новый запуск со ссылкой на прошлый отчёт.
13. Открытый вопрос 5 (П2): неизвестный провайдер роли профиля — ошибка при загрузке конфига, игра не стартует и
    называет профиль и роль (проектировщик, 2026-10-26, по рекомендации папы).
14. `--provider` с неизвестным профилем — «Ошибка: нет профиля X; есть: …», код выхода 1, без `choices` argparse;
    в `--help` — «имя профиля из config (profiles)», без списка; ошибка — до создания мира и TUI (проектировщик,
    2026-10-26, по рекомендации папы на вопрос кабана).
15. Хостер в `[roles.narrator]` конфига игрока ведёт себя как встроенный провайдер: ключ проверяется по `key_env`
    хостера; нет ключа — «Нет ключа <VAR>: беру профиль <X>.» и переход на профиль с ключом (проектировщик,
    2026-10-26, по рекомендации папы на замечание мамы П2).
16. Проверка провайдера при загрузке конфига (решение 13) — и для `roles.*`, `alternatives.narrator` и ключей
    `llm.narrator_chain`: «roles.narrator: неизвестный провайдер foo», игра не стартует (проектировщик, 2026-10-26,
    по рекомендации папы на замечание мамы П2 круг 2).
17. П3: OpenRouter отклонил оплату («посчитали что я из РФ. ну либо у них санкции и против Уз тоже») — проектировщик
    сам пробует DeepInfra (регистрация, оплата картой); профиль — в своём config.toml, без кода. Вопрос о главном
    хостере (решения 6, 8) — после попытки (проектировщик, 2026-10-26; рекомендация папы была — сначала ресёрч оплаты).
18. После П3 («мне не оч нравится, нам возможно стоит поискать другие модели, котоыре могут конкурировать с gemini»;
    проектировщик, 2026-10-26, «принять рекомендации 1–3» папы):
    - 184 закрывается как механизм хостера: условие решения 6 — «работает на OpenAI-совместимом хостере (DeepInfra)»;
      бой/`strict` и выбор модели — в 185; профили OpenRouter живьём не проверены — риск в «Итог»;
    - ресёрч дяди-кабана «модели против gemini» (BACKLOG 206) — состав пробы 185 вместо DeepSeek/Qwen; профиль qwen
      в поставке остаётся, в пробу не идёт; главный хостер (решение 8) — после ресёрча;
    - время до первого токена и токены/с в журнале — BACKLOG 207.

## План (папа-кабан, 2026-10-26)

Входы: груминг свинопаса и аудит свекрови (scratchpad сессии 2026-10-26), docs/research/hosters-api-184.md,
BACKLOG 184, 122, docs/plan-e10a.md. Цены и окна сверены живым `GET https://openrouter.ai/api/v1/models` 2026-10-26.
Размер — не S (ROADMAP R12 «S на вид» — догадка, свекровь): две партии.

### Правила, которые меняются (первым пунктом аппрува)

1. `make_adapter`, factory.py:9–18: было `if provider not in KEY_VARS: raise ValueError` … последняя ветка
   `return GeminiAdapter(...)` без проверки → станет: `provider in app_cfg.providers` → `ChatCompletionsAdapter`
   (адрес и имя переменной ключа из профиля хостера); `anthropic | openai | gemini` — каждый явной веткой;
   прочее → `ValueError("неизвестный провайдер")`.
2. Ключ, keys.py:26 `load_key`: было имя переменной только из `KEY_VARS[provider]` → станет: у хостера —
   `providers.<имя>.key_env` (env важнее `.env`, как сейчас).
3. Правила рассказчика, prompt.py:270: было `(provider or self.role_cfg.provider) == "openai"` → станет: правила
   openai, если провайдер `openai` или хостер с `narrator_rules = "openai"` (по умолчанию так, реш. 5).
4. Символов на токен, app.py:108 `cpt_for`: было `chars_per_token_by_provider.get(provider, chars_per_token)` →
   станет: для хостера без своей записи — `providers.<имя>.chars_per_token`, по умолчанию 3.5 (как openai, реш. 5).
5. Выбор ролей по профилю: было `profiles.get(<провайдер адаптера>)` (turn.py:341, 357; cli.py:365, 378, 392;
   app.py:550–557 `follow_provider`) — имя профиля = имя провайдера → станет: профиль ищется по провайдеру
   и модели рассказчика (`profile_for`, новая). Почему: реш. 10 даёт профили «deepseek»/«qwen» с провайдером
   `openrouter`; сейчас world и summarizer у них откатились бы на `roles.*` (Gemini) и потребовали бы ключ Gemini.
6. Автовыбор без ключа, cli.py:333–336: было `for provider in profiles: if load_key(provider) …` → станет: перебор
   только встроенных провайдеров (профили хостеров пропускаются, реш. 7). Без правки `load_key("deepseek")`
   упал бы с `ValueError`.

**Поведение:** меняется только при выборе модели хостера (`/model openrouter:…`, `--provider`); для
anthropic/openai/gemini — не меняется (дефолты, `narrator_chain`, реш. 7).
**Вне ai-dm:** OpenRouter — аккаунт, баланс и ключ `OPENROUTER_API_KEY` в env/.env — проектировщику (живая
проверка, реш. 6).

### Модули/файлы/функции

- `config/app.py`: `ProviderHost` (новая модель: `base_url`, `key_env`, `chars_per_token: float = 3.5`; поле
  `narrator_rules: Literal["openai","base"] = "openai"` — в П2 вместе с правилом 3, его читателем: в П1 `make dead`
  ловит неиспользуемое поле; решение Влада 2026-10-26); `AppConfig.providers: dict[str, ProviderHost]` (новое поле);
  `AppConfig.check_models_known` — + проверка: имя хостера не `anthropic|openai|gemini` (П1); роль профиля с
  провайдером не из встроенных и не из `providers` → ошибка (П2, вопрос 5; решение Влада 2026-10-26: в П1 она
  ломала тестовые конфиги с `profiles.other`); `MasterConfig.cpt_for` — см. правило 4 (хостеры ему передаёт
  валидатор `AppConfig`, заполняя `chars_per_token_by_provider` через `setdefault`); `profile_for(app_cfg,
  provider, model)` — новая.
- `config/app_defaults.toml`: `[providers.openrouter]` (`base_url = "https://openrouter.ai/api/v1"`,
  `key_env = "OPENROUTER_API_KEY"`); `[prices."deepseek/deepseek-v4-flash"]`, `[prices."qwen/qwen3-235b-a22b-2507"]`;
  две записи `context_windows` (П1); `[profiles.deepseek.*]`, `[profiles.qwen.*]` × 4 роли — в П2 (в П1 автовыбор
  без ключей доходил до них и давал «неизвестный провайдер: deepseek» вместо «нет ключа»; решение Влада
  2026-10-26). `narrator_chain` не трогаем.
- `llm/keys.py`: `load_key` — + `var=None` (имя переменной хостера); `read_var` — новая (тело `load_key` после
  выбора имени), чтобы не дублировать разбор `.env`.
- `llm/openai_adapter.py`: `OpenAIAdapter.__init__` — без правки (6-й параметр дал smell 201 > 200; решение Влада
  2026-10-26); атрибут класса `base_url = None`; `OpenAIAdapter.get_client` — передаёт `base_url`, если задан.
- `llm/chat_adapter.py` (новый): `ChatCompletionsAdapter(OpenAIAdapter)` — `__init__` (после `super().__init__`
  берёт `self.base_url = app_cfg.providers[provider].base_url`; `make_adapter` `base_url` не передаёт; тесты —
  через конфиг с `providers`), `info` (provider = имя хостера),
  `build_messages`, `build_tools`, `build_kwargs`, `complete` (`client.chat.completions.create`), `parse_response`,
  `stop_of`, `usage_of` — все новые; `translate_error`, `get_client` — наследуются.
- `llm/factory.py`: `make_adapter` (правило 1; хвост 122).
- `master/prompt.py`: `PromptBuilder.__init__` (правило 3).
- `ui/cli.py`: `main` (`secrets` — + ключи хостеров для `redact`, стр. 467); `pick_narrator` (правило 6),
  `pick_world`, `pick_summarizer`, `pick_import` (правило 5); `build_parser`/аргумент `--provider` стр. 113 —
  без `choices`, проверка в `profile_narrator`, «Ошибка: …», код 1 (решение 14); `replay_report` стр. 719 — передать `adapter_factory` (риск
  game/app.py:114, ниже).
- `game/turn.py`: `TurnRunner.new_world_session`, `TurnRunner.new_summarizer_session` (правило 5).
- `game/app.py`: `GameApp.follow_provider` (правило 5).
- `game/models.py`: `check_model` — без правки (цена+окно уже проверяются; записи дают defaults).

Проверено grep-ом 2026-10-26: `make_adapter`, `load_key`, `parse_dotenv`, `OpenAIAdapter.get_client`,
`translate_error`, `PromptBuilder` (prompt.py:259), `cpt_for` (app.py:107), `check_models_known` (app.py:207),
`profile_narrator`/`pick_narrator`/`pick_world`/`pick_summarizer`/`pick_import` (cli.py:305–384), `main` (cli.py:452),
`replay_report` (cli.py:680), `new_world_session`/`new_summarizer_session` (turn.py:336, 349), `follow_provider`
(app.py:548). Имя функции парсера в cli.py не сверено — кабану найти по `"--provider"` (cli.py:113).

### Проект адаптера Chat Completions

- Запрос: `system` — одно сообщение `{"role": "system"}` из склейки `req.system` (как `instructions` у Э10а);
  `Text` → сообщение роли; `ToolCall` → `assistant.tool_calls` (`arguments` — JSON); `ToolResult` →
  `{"role": "tool", "tool_call_id", "content"}` (ошибка — `{"error": …}`, как `block_to_item`); инструменты —
  `{"type": "function", "function": {name, description, parameters, strict}}`; `max_tokens` (не
  `max_completion_tokens`: у qwen в `supported_parameters` только `max_tokens` — проверено живым /models);
  `effort` → `reasoning_effort`, только если не `None`.
- Ответ: `choices[0].message` → `Text`/`ToolCall`; сообщение целиком (`model_dump`) — в
  `Opaque(provider=<хостер>, raw={"message": …})` и возвращается назад без изменений (стиль Э10а: так сохраняются
  `reasoning`/`reasoning_details` OpenRouter между вызовами инструментов). `finish_reason`: `stop` → end_turn,
  `tool_calls` → tool_use, `length` → max_tokens (вызовы не разбираем, как `cut`), `content_filter` → refusal,
  прочее → other; `message.refusal` → refusal.
- Usage: `input = prompt_tokens − cached`, `cache_read = prompt_tokens_details.cached_tokens`, `output =
  completion_tokens`, запись кэша 0.
- `stream` нет, повторы — наши (`max_retries=0`), таймаут `retry.timeout_s`.

### Цены и окна (живой /models OpenRouter, 2026-10-26; единица — микро-$ за 1M, app.py:35)

- `deepseek/deepseek-v4-flash`: input 91000, output 182000, cache_read 18200, cache_write 0; окно 1048576.
- `qwen/qwen3-235b-a22b-2507`: input 90000, output 550000, cache_read 90000 (цены кэша нет — без скидки),
  cache_write 0; окно 262144. `reasoning_effort` у qwen в `supported_parameters` нет → `effort` в профиле не задаём.

### Партии

1. **П1 — слой llm и конфиг** (без проводки в игру): `ProviderHost`, `providers`, `read_var`/`load_key(var=)`,
   атрибут класса `base_url` у `OpenAIAdapter`, `ChatCompletionsAdapter`, `make_adapter` (правила 1, 2), записи
   `app_defaults.toml` (хостер, цены, окна; без профилей), проверка имени хостера. Выход: `make_adapter("openrouter",
   "deepseek/deepseek-v4-flash", cfg, env={"OPENROUTER_API_KEY": "k"})` даёт адаптер с `info().provider ==
   "openrouter"`; фейковый клиент проходит ход с инструментом; `/model openrouter:deepseek/deepseek-v4-flash`
   меняет только рассказчика (world/summarizer — прежние: профиля `openrouter` нет), тесты ui не трогаются. Проверка: `uv run pytest -q tests/unit/llm
   tests/unit/config`, mutmut П1.
2. **П2 — проводка в игру**: правила 3–6 (с полем `ProviderHost.narrator_rules`), `profile_for`, профили
   `[profiles.deepseek.*]`/`[profiles.qwen.*]`, проверка провайдера роли в `check_models_known` (по вопросу 5) и
   правка тестовых конфигов с `profiles.other` (tests/unit/ui/test_cli_import.py и др. — по логу П1), `--provider`, `secrets`, `replay_report`. Выход:
   `--provider deepseek` (при Р2 = а) и `/model openrouter:deepseek/deepseek-v4-flash` поднимают все четыре роли
   на хостере, ключ хостера маскируется. Проверка: тесты ui/game/master затронутых модулей, `make test-fast`, в
   конце — `make cov`, `make smells`, `make dead`, mutmut П2.
3. **Живая проверка** (реш. 6) — проектировщик: несколько ходов на OpenRouter (deepseek и qwen); итог — в «Итог».
   Это не проба 185.

`make mutate` FUNCS (П1): `ai_dm.llm.factory:make_adapter ai_dm.llm.keys:load_key ai_dm.llm.keys:read_var
ai_dm.llm.openai_adapter:OpenAIAdapter.get_client ai_dm.llm.chat_adapter:ChatCompletionsAdapter.__init__
ai_dm.llm.chat_adapter:ChatCompletionsAdapter.build_messages
…build_kwargs …parse_response …stop_of …usage_of …assistant_message …user_messages ai_dm.llm.chat_adapter:parse_call
ai_dm.config.app:AppConfig.check_models_known` (дополнено по аудиту свекрови, «Правки по ревью» п. 4),
TESTS=`tests/unit/llm tests/unit/config`. Хвост 122: выжившие `make_adapter`
2, 16, 17, 20, 31, 32, 35 — номера старые, после переписи функции разбирать заново всех выживших `make_adapter`
как «в диффе»; `retry_after_of` не трогаем — 122 остаётся по нему открытым.
FUNCS (П2): `ai_dm.ui.cli:pick_narrator ai_dm.ui.cli:pick_world ai_dm.ui.cli:pick_summarizer ai_dm.ui.cli:pick_import
ai_dm.game.turn:TurnRunner.new_world_session ai_dm.game.turn:TurnRunner.new_summarizer_session
ai_dm.game.app:GameApp.follow_provider ai_dm.master.prompt:PromptBuilder.__init__ ai_dm.config.app:profile_for
ai_dm.config.app:MasterConfig.cpt_for ai_dm.config.app:AppConfig.check_models_known`, TESTS — каталоги
`tests/unit/{ui,game,master,config}`.

### Тестовые сценарии (кабану-доебе, TDD; все — ожидание, не проверено)

- `make_adapter` по каждой ветке: anthropic/openai/gemini — свой класс; `openrouter` — `ChatCompletionsAdapter`,
  `base_url` из профиля; `"mistral"` → `ValueError`; хостер без ключа → `MissingKey` с `OPENROUTER_API_KEY` в тексте.
- Ключ хостера: env важнее `.env`; пусто в обоих → `None`.
- Конфиг: хостер с именем `openai` → ошибка; роль профиля с провайдером `foo` (ни встроенный, ни хостер) → ошибка;
  пользовательский `[prices."deepseek/deepseek-v4-flash"]` перекрывает дефолт (реш. 4).
- Адаптер (фейковый клиент): system одной записью; `ToolCall`/`ToolResult` → `tool_calls`/`role: tool`;
  `effort=None` — без `reasoning_effort`; `finish_reason` каждой ветки; `length` с оборванным `arguments` — без
  вызова и без `LlmFatal`; неверный JSON аргументов → `LlmFatal`; usage с `cached_tokens` и без
  `prompt_tokens_details`; `Opaque` второго хода уходит назад байт-в-байт; ошибки 429/500/400 и сеть — как у Э10а;
  ключ в тексте ошибки маскируется.
- Игра: `--provider deepseek` → world/summarizer/import на `deepseek/deepseek-v4-flash` провайдера `openrouter`;
  `/model openrouter:qwen/qwen3-235b-a22b-2507` с deepseek → world/summarizer следуют за qwen; без ключа Gemini
  и с ключом OpenRouter автовыбор не берёт профиль хостера (правило 6); рассказчик хостера получает
  `narrator_rules_openai.md`, `narrator_rules = "base"` — нет; `cpt_for("openrouter") == 3.5`.
- Руками: `ai-dm --world <копия> --provider deepseek`, `/model` — модели хостера в меню, ход проходит, `/cost`
  ненулевой; в `saves/<копия>/journal/calls-*.jsonl` нет ключа.

### Развилки (решает проектировщик)

- **Р1. Имя секции хостера в `config.toml`** (видно игроку): (а) `[providers.openrouter]` — так в окне свинопаса
  вопрос 2; (б) `[hosts.openrouter]` — не путается с `profiles`. Рекомендую а — проектировщик уже видел это имя.
- **Р2. Что принимает `--provider`** (видно): (а) имена профилей (`anthropic|gemini|openai|deepseek|qwen`) —
  `choices` из `profiles`; (б) `--provider openrouter --model …` — новый флаг. Рекомендую а — минимум кода,
  реш. 7 «`--provider`».
- **Р3. Профили хостера в меню `/model`** (видно): `model_options` (models.py:7) уже добавляет нарраторов всех
  профилей — deepseek и qwen появятся в меню у всех игроков, и без ключа OpenRouter. (а) так и оставить — выбор
  явный (реш. 7), ошибка ключа покажется при выборе; (б) показывать только при наличии ключа хостера. Рекомендую а.
- **Р4. `effort` и `max_tokens` профилей** (влияет на прозу и $): (а) deepseek как openai — narrator medium/16000,
  world и summarizer low/8000, import low/32000; qwen — те же `max_tokens`, `effort` нет; (б) без `effort` у обоих.
  Рекомендую а; лимит выхода qwen на OpenRouter не сверен.
- **Р5. `narrator_rules_openai.md` для open-weight моделей**: реш. 5 уже задаёт «как openai»; уточнить не нужно,
  если 185 не покажет вреда — отмечено как риск.

### Риски

- game/app.py:114 (свинопас): фабрика по умолчанию без `env`/`dotenv_path`. В игре cli передаёт свою фабрику
  (cli.py:943, 1008) — для `.env` риска нет; без фабрики создаётся только `replay_report` (cli.py:719): `/model`
  в повторе не увидит ключ из `.env` ни у одного провайдера. Чиним в П2 одной строкой.
- Последняя ветка `make_adapter` → Gemini (свинопас): закрывается правилом 1.
- Нет зашифрованных рассуждений между ходами (реш. 1): `Opaque` сохраняет то, что вернул хостер, но перенос
  рассуждений у DeepSeek/Qwen на OpenRouter не проверен; смена модели внутри хостера отдаёт чужие `reasoning_details`
  — ожидание: хостер их игнорирует, не проверено.
- Кэш Qwen только по `cache_control` (ресёрч, разд. 2) — в 184 не делаем, это 186; $ за час qwen в 185 будет без кэша.
- BACKLOG 125 (склейка system сбрасывает кэш) повторится и здесь: system одним сообщением.
- `strict` у инструментов: OpenRouter заявляет `structured_outputs` у обеих моделей, соблюдение не проверено.
- Цены хостера меняются — правятся в `config.toml` игрока (реш. 4).

### Умолчания (внутреннее)

Имена `ChatCompletionsAdapter`, `llm/chat_adapter.py`, `ProviderHost`, `read_var`, `profile_for`; адаптер —
наследник `OpenAIAdapter` (общие `get_client`, `translate_error`); `Opaque.raw = {"message": …}`; профиль ищется
сначала по провайдеру и модели рассказчика, затем первый с тем же провайдером; при Р1 = а поле
`AppConfig.providers`, при Р1 = б — `hosts`.

### Открытые вопросы

1. Р1 — имя секции хостера (`app.py:186`): (1) `providers` (2) `hosts`; рекомендую 1; разблокирует П1; решает
   проектировщик. Блокирующий.
2. Р2 — форма `--provider` (`cli.py:113`): (1) имена профилей (2) новый `--model`; рекомендую 1; разблокирует П2.
3. Р3 — меню `/model` (`models.py:7`): (1) всегда (2) только с ключом; рекомендую 1; разблокирует П2.
4. Р4 — `effort`/`max_tokens` профилей (`app_defaults.toml:243–266` как образец): (1) как openai (2) без effort;
   рекомендую 1; разблокирует П1.
5. П2 — провайдер роли профиля не встроенный и не хостер (`check_models_known`, `config/app.py`; видно игроку):
   (1) ошибка при загрузке конфига — игра не стартует, опечатка видна сразу; (2) как раньше — ошибка только при
   выборе модели; рекомендую 1; цена — тестовые конфиги с `other` переводятся на встроенный провайдер или хостер;
   разблокирует П2; решает Влад.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план папы-кабана 2026-10-26 (2 партии + живая проверка); база масштаба — «Итог» docs/plan-202.md
(4 партии, факт ≈ $21,4 / 38,5 M / 3,75 ч). 184 — 2 партии кода, но больше нового src (адаптер + проводка в 6 модулях),
поэтому ≈ 0,7–0,9 от 202.

Модели ролей (`grep -H '^model:' ~/.claude/agents/<роль>.md`, 2026-10-26):
kaban, kaban-doeba — sonnet; mama-kaban, kaban-svekrov, svinopas — opus; papa-kaban — fable (по ценам Opus).
Совпадает с запуском тестя (opus 5.5).

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| OpenRouter (живая проверка, П3) | ≈ 0,05 разово | ~20 ходов на deepseek и qwen, ~30k вход + 1,5k выход на ход; цены из плана (живой /models 2026-10-26): deepseek $0,091/$0,182, qwen $0,09/$0,55 за 1M | — | — | — (платит проектировщик, баланс OpenRouter; минимальное пополнение — со страницы openrouter.ai, не сверял) |
| Игра на OpenRouter после 184 | ≈ 0,2–0,5 за час игры (deepseek), qwen ≈ ×1,5–3 без кэша | ~60 ходов/ч × 30–60k вход; кэш qwen не делаем (186) | кэш qwen (`cache_control`) — шаг 186 | у qwen вход ×1 → со скидкой | ничего в 184; это план 186 |
| Цепочка шага (Claude, ниже) | ≈ 15–22 разово | см. таблицы ниже | /compact оркестратора между П1 и П2; маме и свекрови — SendMessage в один контекст; cov только в конце П2 (уже в плане) | ≈ 3–6 | ничего; ревью и аудит не сокращаем |
| Свекровь, растущий контекст | ≈ 2,5–3,7 | в 202 — 6 кругов в одном контексте ($3,7) | после 3-го круга — новый запуск со ссылкой на отчёт | ≈ 1 | связность контекста аудита (решает пользователь) |

| Партия | Время |
|---|---|
| груминг + план + смета (уже прошло) | ≈ 30–60 мин интервала |
| П1: слой llm и конфиг | ≈ 1–1,5 ч (kaban + doeba ~15 мин работы, ревью 2–3 круга, mutmut ~3–5 мин) |
| П2: проводка в игру | ≈ 1,5–2 ч (6 модулей, `make cov` ≈ 15 мин, mutmut по 4 каталогам ~10–15 мин) |
| П3: живая проверка | ≈ 20–30 мин проектировщика |
| итого | ≈ 3,5–5 ч интервала |

| Роль | Модель | Токены | $ (тариф metrics.py от 2026-10-25) |
|---|---|---|---|
| оркестратор | opus 5.5 | ≈ 20–30 M (по 202, с /compact) | ≈ 7–11 |
| papa-kaban (уже прошло) | fable → цены Opus | id не сверял, интервал по 202 | ≈ 1–2 |
| svinopas (уже прошло) | opus | id не сверял, интервал по 202 + окна груминга | ≈ 0,5–1,5 |
| kaban | sonnet | 2 запуска | ≈ 0,8–1,5 |
| kaban-doeba | sonnet | 2 запуска + разбор мутантов | ≈ 1–2 |
| mama-kaban | opus | 2 партии, 2–3 круга | ≈ 2–3 |
| kaban-svekrov | opus | груминг + 2 партии | ≈ 2,5–4 |
| Декарт | — | вызовов = 2 партии + 1 сводный, выжимки до 400 KB | ≈ 0,5–1 |
| итого | | ≈ 30–45 M | ≈ 15–26 |

Вердикт: ок по бабкам. Оплатная статья вне Claude — только баланс OpenRouter у проектировщика (центы на проверку).

## Правки по ревью

П1, круг 1 (2026-10-26; мама — нужны правки, свекровь — сверх плана нет):
1. `make_adapter`: явная ветка gemini и `ValueError` в конце (правило 1 плана; мама, свекровь) — кабан.
2. `check_models_known`: стиль `models = [` (мама) — кабан.
3. `chat_adapter.FINISH_STOPS`: комментарий, почему без "tool_calls" (мама, на выбор — принято) — кабан.
5. `make dead`/`make smells` (2026-10-26, Влад — «принять рекомендации 1–2» папы): поле `ProviderHost.narrator_rules`
   переносится в П2 (вместе с чтением в prompt.py); `base_url` — атрибут класса `OpenAIAdapter`, его ставит
   `ChatCompletionsAdapter.__init__` из профиля, `OpenAIAdapter.__init__` без нового параметра — кабан; «Модули» и
   FUNCS (+ `ChatCompletionsAdapter.__init__`) — папа.
   Долг П2 (свекровь, круг 3): вернуть тест «narrator_rules — только openai|base» вместе с полем.
6. `make cov` П1: 18 failed в ui/scenarios — профили deepseek/qwen ломают автовыбор без ключей («неизвестный
   провайдер: deepseek»), проверка провайдера роли в `check_models_known` отвергает тестовые `profiles.other`
   (2026-10-26, Влад — вариант «а» папы): профили `[profiles.deepseek|qwen.*]` и проверка провайдера роли — в П2
   вместе с `profile_for` и фильтром автовыбора — кабан; «Модули»/«Партии» — папа. Открыто к П2 (окно Владу):
   жёсткая проверка провайдера роли при загрузке конфига или, как раньше, при выборе модели (папа рекомендует первое).
   Долг П2 (доеба): вернуть в tests/unit/config/test_app.py `test_profile_role_with_unknown_provider_is_rejected`
   (хелпер `host_profile` оставлен), `test_default_hoster_profile_runs_all_roles_on_openrouter[deepseek|qwen]`,
   `test_qwen_profile_has_no_effort`.
4. FUNCS mutmut П1 дополнены `assistant_message`, `user_messages`, `parse_call`, `check_models_known` (свекровь) — оркестратор.

П2, круг 1 (2026-10-26; мама — нужны правки, свекровь — чисто):
1. `pick_narrator`: хостер в `[roles.narrator]` падал «неизвестный провайдер» — имя переменной ключа брать у хостера
   (`providers[...].key_env`, тот же источник, что у `make_adapter`), решение 15 — кабан; тест «ключ есть / нет» — доеба.
2. `main`: конфиг читается дважды — передать settings через Setup (мама, на выбор; оркестратор передал кабану по правилу семьи «неблокирующее — кабану», без окна Владу) — кабан.
3. `pick_narrator`: проверка ключа в цикле — `is not None`, как строкой выше (мама) — кабан.
4. FUNCS mutmut П2 дополнены `ai_dm.ui.cli:main`, `profile_narrator`, `play_report`, `make_parser` (мама) — оркестратор.

П2, круг 2 (2026-10-26; мама — можно мержить, два мелких; свекровь — чисто):
1. Опечатка провайдера в `roles.narrator` давала «Ошибка: 'foo'» (регресс П2): `check_models_known` проверяет
   провайдер `roles.*`, `alternatives.narrator`, ключей `narrator_chain`, решение 16 — кабан; тесты — доеба.
2. `settings_of`: `getattr(setup, "settings", None)` → `setup.settings`, если старые тесты не строят Setup без поля
   (мама, на выбор; передано кабану с тем же «если») — кабан. Условие не выполнено: тесты test_ui_cli.py (стр. 911,
   932, 983, 1027) и test_ui_cli_sound.py строят Setup как `SimpleNamespace` без поля — `getattr` оставлен (кабан).

П2, круг 3 (2026-10-26; мама — можно мержить, одна мелочь; свекровь — чисто):
1. `check_models_known`: метка роли профиля — явная пара `("import", "import_")` вместо `rstrip('_')` (мама, на
   выбор; оркестратор передал кабану по правилу семьи «неблокирующее — кабану») — кабан.
Круг 4 (мама — можно мержить; свекровь — чисто): вынести кортеж `pairs` из цикла (мама, косметика) — не делаем
(Влад, окно 2026-10-26: «Нет, идём к mutmut»).

## Итог

П3 — живая проверка (2026-10-26; разбор свинопаса по журналам saves/vale-43cd433c, saves/vale-93828c0f):
- OpenRouter: оплата отклонена (решение 17) — профили deepseek/qwen на OpenRouter живьём не проверены (риск).
- DeepInfra, deepseek-v4-flash (3 хода): ошибок API и 400 по `effort` нет; `cached_tokens` приходит, $ по ценам
  конфига верен (≈ $0,004 за прогон); ход 21–56 с; обратный `reasoning_content` принят. Один повтор шага игры
  (4 варианта в `offer_choices`). Отзыв: проза неплохая, дёшево, текст медленнее gemini, быстрее sonnet.
- DeepInfra, qwen3-235b-2507 (3 хода): ×4,5 дороже deepseek ($0,017), кэша нет, вход ×2,5; ход 34–75 с
  (~11 ток/с); на 2 ходах из 3 нет `offer_choices` (доборы choices_retry). Отзыв: долгий, дороже, проза не нравится.
- world, summarizer, бой и броски не вызывались — в 185 (решение 18).
- mutmut П2: `ui.cli.prepare`, `make_parser` не гонялись (окно Влада, > 1 ч); остался эквивалентный
  `pick_narrator_20`; старые выжившие — BACKLOG 205.

### Стоимость (кабан-тесть, режим 3)

**Источник токенов:** `metrics.py` по
`~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/51041c22-15ec-4cf9-a679-64e08933dbfd.jsonl`;
время — agents.md оркестратора; **цены:** тариф metrics.py 2026-10-25
(https://platform.claude.com/docs/en/about-claude/pricing), fable — по ценам Opus (запуск fable упал на 429, $0).

| Партия | Смета | Факт |
|---|---|---|
| груминг + план + смета | 30–60 мин | ≈ 40 мин (10:15–10:54); папа fable — 429, перезапуск на opus |
| П1: llm и конфиг | 1–1,5 ч | ≈ 1,9 ч (10:56–12:48, в т. ч. простой): cov 18 failed → вопрос папе/Владу, 4-й круг свекрови, cov ×2 по 11 мин |
| П2: проводка в игру | 1,5–2 ч | ≈ 4,1 ч (13:03–17:07, в т. ч. простой): 4 круга ревью, mutmut ≈ 2,5 ч (остановлен на 730/1700, перезапуск 50 мин, повтор 30 мин) |
| П3: живая проверка | 20–30 мин | ≈ 1 ч (17:07–18:06): OpenRouter не принял оплату → DeepInfra, разбор свинопаса, ресёрч 206 |
| итого | 3,5–5 ч | ≈ 7,8 ч интервала (оркестратор 491 мин) |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| оркестратор (на момент подсчёта 18:25) | opus 5.5 | 33,02 M | 12,21 |
| papa-kaban (2 запуска, 1 — 429) | opus (fable — 0) | 4,05 M | 6,70 |
| kaban-doeba (2) | sonnet 5.5 | 8,32 M | 3,06 |
| mama-kaban | opus | 2,73 M | 2,59 |
| kaban-svekrov (3) | opus | 2,36 M | 2,30 |
| kaban | sonnet 5.5 | 5,45 M | 2,03 |
| svinopas (2) | opus | 1,13 M | 0,77 |
| dyadya-kaban (2, вне сметы: ресёрч хостеров и 206) | opus | 0,65 M | 0,72 |
| kaban-test (р.1 + р.3 на момент подсчёта 18:25) | opus | 0,22 M | 0,34 |
| Декарт | — | не запускался в сессии | 0 |
| итого | | 57,94 M | 30,71 |

Расхождения: папа $6,7 против 1–2 — 14 хэнд-бэков (вопросы по cov, --provider, развилки П3) в одном контексте с
записью кэша 1,17 M; оркестратор выше (33 M против 20–30) — 7,8 ч и 2 compact; дядя-кабан в смету не входил.
Свекровь уложилась (новый запуск после 3-го круга сработал: $2,3 против 2,5–4).

**Итого:** смета ≈ $15–26 / 30–45 M / 3,5–5 ч → факт $30,71 / 57,9 M / ≈ 7,8 ч (выше: папа, долгий mutmut П2, смена хостера в П3).
Разбор — кабан Декарта.
