# План этапа 2: протокол мастера, адаптеры, игровой цикл (простой режим)

Автор: папа-кабан. Статус: принят 2026-10-03 (решения — decisions/stage2-plan.md). Основа: TZ.md, ARCHITECTURE.md, decisions/*, llm-notes/claude-api-facts.md,
код этапа 1 (тег `stage-1`).

Ядро этапа 1 не переделывается — только добавления: `rules/xp.py` (опыт за бой — сейчас не начисляется), `rules/loot.py`,
`rules/uniqueness.py` (5.3), `death_saves.resolve_out_of_combat`. Действия игрока в бою — через существующий `Controller.choose`.
Изменение формата сейва: типизированные `current_scene` и `recent_turns` → `CURRENT_SCHEMA_VERSION=2` + миграция `m0002` (ТЗ 5.3).

# Часть A. Архитектура

## A0. Протокол с моделью — tool use со `strict`
- Каждый запрос ТЗ 2.1 — отдельный инструмент (`strict: true`, `additionalProperties: false`), `tool_choice: auto`.
  Повествование — текст финального ответа (`end_turn`).
- Почему: ход = «запрос → движок бросает → мастер узнаёт результат → рассказывает» = цикл `tool_use` → `tool_result`
  (`Decision`) → продолжение; сигнал об урезании (2.3) — следующий раунд того же цикла. Structured outputs дают один JSON —
  нужен второй вызов. Форсированный `tool_choice`/префилл у Opus/Sonnet 5.5 → 400, поэтому `auto` + промпт; не вызвал
  обязательный инструмент → невалидный ответ → повтор по 2.2. У Gemini — тот же function calling (AUTO).
- `strict` гарантирует форму; смысл (id, варианты, лимиты) проверяют Pydantic и обработчики протокола.
- Две неудачи: **Invalid** (схема/ссылки → `tool_result is_error` с пояснением, бюджет «невалидный ≤ 2») и
  **Decision rejected** (бизнес-исключения 2.1 — сигнал мастеру, бюджет не тратит). Не больше `max_tool_rounds` (8) раундов на ход.

## A1. Слои
```
ui → game → master → llm
       │       └──→ protocol → [движок]
       ├──→ protocol, persistence, combat (контроллеры)
llm: только pydantic/SDK
```
Сторож: `llm` не импортирует protocol/master/game/ui/движок; `protocol` — llm/master/game/ui; `master` — game/ui; движок — новых слоёв.

## A2. `protocol`
- `requests.py` — Pydantic-модели всех запросов 2.1, union `MasterRequest` по `type`; категории — `Literal` из
  `content/models/common.py`. Ключевые: `skill_check`, `saving_throw` (category, stakes), `start_combat` (зоны, враги, группы
  с лидером и намерением), `player_action{steps:[option_id], improvise?, unsupported?}`, `npc_action{choice}`,
  `defeat_outcome`, `end_combat`, `damage{severity, failed_roll_ref?}`, `give_item`, `take_item`, `gold{direction, kind…}`,
  `award_xp{scale}`, `advance_time{category | travel_to, pace}` (перемещение героя здесь), `rest`, `warn_danger`, `set_flag`,
  `npc_create`, `location_create`, `npc_update{attitude_delta, status, cause, evidence_ref…}`, `favor_change`,
  `reveal_secret`, `event_start/end`, `offer_choices`, `end_scene`, `end_chapter`, `afterlife_action`, `unsupported_action`.
  Свободного `heal` нет.
- `schema.py` — strict-совместимая схема без union (лимиты strict: 20 инструментов, 24 необязательных, 16 union; решение
  `decisions/stage2-batch2-review.md`): всё required, необязательное — обязательное поле с нейтральным значением («» / 0 / `"none"` /
  `[]` / `"normal"` = «нет»; `set_flag.value` — строка, `"true"`/`"false"` → bool), инлайн `$defs`, сортировка по имени. Pydantic при
  разборе превращает нейтральные значения в `None`. Наборы инструментов по режиму — `tool_set(mode)` (≤ 16 strict каждый):
  `explore` (18 инструментов, `end_chapter` и `location_create` без strict — Pydantic проверяет их всё равно), `combat_classify`
  (`player_action`, `unsupported_action`), `combat_narrate` (`offer_choices`, `unsupported_action`, `end_combat`, `defeat_outcome`),
  `npc_choice` (`npc_action`).
- Видимые модели на этапе 2: `skill_check, saving_throw, start_combat, player_action, defeat_outcome, end_combat, damage,
  give_item, take_item, gold, award_xp, advance_time, rest, set_flag, npc_create, location_create, npc_update, offer_choices,
  end_scene, end_chapter, unsupported_action`; `npc_action` — только в вызове контроллера NPC; `warn_danger, favor_change,
  reveal_secret, event_*, afterlife_action` — модели и тесты есть, модели не показываются (этапы 3, 8), вызов → invalid.
- `decision.py` — `Decision{status: accepted|clamped|rejected, reason, signal_to_master, report_tag, result, log}`, `Invalid`.
- `context.py` — `TurnContext` (рабочая копия бандла, Rng, registry, cfg, журнал бросков хода `roll_ref`, накопители сцены, метки).
- `apply.py` + `handlers/*` — `apply(ctx, request) -> Decision | Invalid`, таблица `HANDLERS` (включая `npc_action`; контроль режима — в обработчике).
- Лимиты (числа в `RulesConfig`; отдельного `limits.py` нет, проверки живут в обработчиках `handlers/*`): СЛ категорией; `damage(deadly)` без ссылки на проваленный бросок → `dangerous` +
  `limit-exceeded`; опыт за квест — доля из конфига; опыт за бой — автоматически при победе (`cr_xp`); `give_item` — id в реестре,
  кол-во урезается; `gold` — потолок по уровню, `lose` не больше остатка, `loot_individual` — таблица; `attitude` ±10/±20;
  смерть NPC — только `cause ∈ {goal, hazard}` + `evidence_ref`, иначе `invalid-death`; зарезервированные префиксы флагов → invalid;
  `start_combat` — `validate_start`, врагов > `max_enemies` (6) → урезание (временная страховка, бюджет боя 2.3 — этап 3).
- `render.py` — `Decision` → `tool_result` (JSON, сортировка ключей, строки бросков ТЗ 6).

## A3. `llm`
- `types.py` — нейтральные `ChatRequest`, блоки `Text | ToolCall | ToolResult | Opaque` (мышление/подписи — без изменений
  внутри хода), `ChatResponse{content, stop_reason, usage{input, output, cache_write, cache_read}, request_id}`.
- `adapter.py` — `ModelAdapter`: `complete`, `count_tokens`, `info`.
- `anthropic_adapter.py` — `Anthropic(max_retries=0)`, strict, `cache_control`, effort из конфига, `thinking` не передаётся,
  ошибки → `LlmTransient` (429/≥500/connection/timeout, `retry-after`) / `LlmFatal`; `refusal` — ответ, не исключение.
- `gemini_adapter.py` — `google-genai`, AUTO; SDK сверяется при реализации → `docs/llm-notes/gemini-facts.md`.
- `mock.py` — `ScriptedAdapter` (YAML-сценарии `tests/fixtures/scripts/`), `replay.py` — `ReplayAdapter` + `ReplayDivergence`.
- `retry.py` — 3 повтора 1 → 3 → 10 с (`sleeper` внедряется). `cost.py` — цены из конфига, стоимость в нано-долларах (int),
  `CostLedger` в `saves/<world>/meta/costs.jsonl` вне слотов (откат и загрузка деньги не возвращают), агрегаты, мягкий лимит
  (выключен). `journal.py` — `saves/<world>/journal/calls-NNN.jsonl`, статические блоки в `blobs/` по sha256, ротация + gzip,
  `turn_status committed|aborted`, без ключей. `keys.py` — env / `.env` (свой парсер), `redact()`. `factory.py`.

## A4. `master`
- Роли (`AppConfig`): на этапе 2 работает только narrator (по умолчанию Gemini `gemini-3.8-flash`; профиль `profiles.anthropic`: `claude-opus-5-5`, effort `low` (живой прогон 1, C3), `max_tokens` 16000);
  world/summarizer описаны, не вызываются (`claude-haiku-4-5`); альтернатива narrator — `claude-sonnet-5-5`; профиль gemini —
  id после сверки SDK; цены из справки; окна контекста для бюджета.
- `prompt.py` — `tools` (сорт.) → `system[0]` (кэш: правила протокола и стиля, `master/prompts/narrator_rules.md`) →
  `system[1]` (кэш: мир, истины, tone, id монстров/предметов) → `messages[0]` (переменное: время, локация, герой, NPC сцены,
  бой, последние N ходов, варианты, ввод). В `system` нет времени и UUID (тест).
- Память этапа 2 — окно `recent_turns` (4, живой прогон 2: L3); страховка бюджета: >80% окна → выкидываются старые ходы.
- `session.py` — `MasterSession.run` (цикл инструментов): бюджеты (невалидные ≤ 2, раунды ≤ 8), `refusal` → `TurnFailed`,
  `max_tokens` → invalid; режимы `explore`, `combat_classify` (обязателен `player_action`), `combat_narrate`
  (`offer_choices`, `unsupported_action`, `end_combat`, `defeat_outcome` — обязателен при `defeat_pending`), `npc_choice`
  (обязателен `npc_action`). Ход собирается заново из состояния — сохранённое мышление не ломается.
- Контракт для партии 5: game создаёт `PromptBuilder(app_cfg, model=<модель выбранного адаптера>,
  count_tokens=<адаптер.count_tokens>)` и передаёт в сессию. `count_tokens` зовётся один раз на запрос (полный), дальше
  выкидывание ходов — по эвристике (`len // 3` для кириллицы); ошибка `count_tokens` → эвристика. Все вызовы мастера одного
  прогона хода (classify / npc_choice / narrate) идут с одним `run_id` (`run(..., run_id=...)`).
- Кэш в цикле инструментов: точка `cache_control` на последнем сообщении раунда убрана (живой прогон 1, C1: при 2 вызовах на ход запись не окупается); кэшируется только префикс (system), TTL `llm.cache_ttl = "1h"`.
- Живой прогон 2 (L1): кэш-точка (TTL 5m) стоит на сообщении хода (state) — раунды 2…n хода читают его из кэша; точка на последнем сообщении раунда по-прежнему не ставится. `Usage.cache_write` — запись 5m (1.25× входа), `Usage.cache_write_1h` — запись 1h (2×), цены `cache_write` / `cache_write_1h`. L2: пустой финальный текст принимается без повтора, если в ходе уже есть принятый рассказ (и нет незавершённого обязательного инструмента). G1: герой `grey` (следопыт).
- Риски для живого smoke (партия 6): два `user` подряд у Gemini; ответ только из thinking (Opaque) у Anthropic;
  `cache_read > 0` на втором ходу explore.

## A5. `game`
- `turn.py` — `TurnRunner`: ход на `bundle.model_copy(deep=True)`, `Rng.from_state`; commit (синхронизация `world.rng`,
  `turn_seq += 1`, `TurnRecord`) / abort (копия выбрасывается, журнал `aborted`, меню: повторить / сменить модель / сохранить и выйти).
- Вне боя: ввод → `MasterSession(explore)` → `protocol.apply` → повествование → закрытие сцены → commit → автосейв.
- `combat_flow.py` — граница хода = решение героя. `start_combat` строит `CombatState` (герой и ключевые NPC — `external`,
  остальные — `engine`), `advance_until_player()`; `preview_turn` — список действий на одноразовой копии; ход: снимок →
  движок на копии → ход героя (`PlayerController`) → NPC до следующего хода героя → `MasterSession(combat_narrate)` → commit.
  Конец боя: опыт, сброс `active_combat`, закрытие сцены; `hero_dead` → предложение загрузить сейв (временное правило 2–7).
- `controllers.py` — `PlayerController` (номер → план без модели; текст → `combat_classify`; `improvise` через `engine.improvise`),
  `MasterChoiceController` (ключевые NPC: `intent_reconsider` через `npc_action`; ход — модель только в первый ход NPC с HP ≤ 50%
  (конфиг), иначе `EngineTactics`; невалидно ×3 → `TurnFailed`).
- `scene.py` — `SceneState`; закрытие по `end_scene` / смене локации / скачку > 1 ч / концу боя / > 30 ходов; `ensure_min_advance`,
  автосейв, новая сцена; граница сцены — пустая точка расширения (выжимки, триггеры — этапы 3–4).
- `commands.py` — работают `/help /save /load /model /cost /sheet /inv /quit`; `/report` — этап 6, `/tone` — 3, `/retire` — 9.
- `starter.py` — новый мир, сид, захардкоженный герой, стартовая сцена (`fighter_choices`/`wizard_choices` переезжают сюда).
- Повышение уровня на границе хода: «среднее / бросок».

## A6. `ui`
- `io.py` (`InputSource`/`OutputSink`, тестовые), `simple.py` (повествование, `[бросок]`-строки ТЗ 6, нумерованные варианты,
  список действий в бою, строка состояния `HP · дата · $ сессии`, меню ошибки, мягкий лимит), `cli.py` (`--world --new --seed
  --mock --replay`, script `ai-dm`).

# Часть B. План по партиям

1. **Фундамент:** `AppConfig` + `load_settings`; новые секции `RulesConfig` (`scene`, `attitude`, `limits`); `SceneState`,
   `TurnRecord`, `turn_seq`, `offered_choices`, `recent_turns`; миграция v1 → v2 + отпечаток `save_v2`; `rules/xp.py`,
   `rules/loot.py` (+ таблица `individual_treasure` — сверить SRD 5.2), `rules/uniqueness.py`, `resolve_out_of_combat`.
2. **Протокол (без LLM):** requests, decision, context, render, schema (strict + линтер), apply + handlers, скрытые запросы → invalid.
3. **llm:** types, adapter, errors, retry; mock, journal, replay, cost, keys; anthropic-адаптер (фейковый клиент); gemini-адаптер
   (после сверки SDK); `devtools/live_smoke.py` — ручной живой вызов (не pytest).
4. **master:** правила narrator + prompt builder (стабильность префикса), session (цикл, режимы, бюджеты), memory (окно).
5. **game:** turn runner, combat_flow + контроллеры, scene, starter, commands, app (главный цикл, временное правило смерти, уровни).
6. **ui и приёмка:** io/simple/cli; `tests/scenarios/test_stage2_done.py` на `talk_check_fight.yaml`; ARCHITECTURE часть C,
   README (запуск, ключи, `.env`), чек-лист ручной живой сцены для Claude и Gemini.

## Тестовые сценарии (живых вызовов нет — Mock, Replay, фейковые клиенты SDK)
- **Критерий «готово» — «разговор → проверка → бой» на моке** (сид N, герой Арн): ход 1 — текст + `offer_choices`; ход 2 —
  `skill_check(persuasion, medium)` → `tool_result` с СЛ 15 и строкой броска, `rng.draws` растёт, бросок в UI; ход 3 —
  `start_combat` (3 зоны, 2 гоблина + Гракх, `capture`), ходы до героя выполнены; бой (ввод номером без модели и текстом с
  `improvise`) → `victory`, опыт = сумма `cr_xp`, флаг `combat_ended`, сцена закрыта, автосейв, `active_combat=None`;
  детерминизм (два прогона — побайтно равные бандлы и запросы); поражение → обязательный `defeat_outcome`; replay → тот же
  бандл, изменённый ввод → `ReplayDivergence`.
- **Ошибки 2.2 и атомарность:** transient ×3 → успех (паузы 1/3/10); ×4 → `TurnFailed`, бандл и RNG не изменились, журнал
  `aborted`, «повторить» даёт те же броски; невалидный ×2 → успех, ×3 → откат; > 8 раундов → откат; `refusal` → откат +
  метка; `max_tokens` → invalid; `LlmFatal` → меню без повторов; сбой посреди хода → инвентарь и RNG прежние; `npc_action` ×3 → откат.
- **Лимиты 2.3:** deadly без провала → clamped; give_item/gold/attitude — урезания; смерть NPC без причины → `invalid-death`;
  уникальность; зарезервированные флаги; несвязные зоны → invalid; > 6 врагов → урезание; `unsupported_action` →
  `missing-mechanic`; инструмента лечения нет.
- **Протокол/кэш:** strict-линтер схем; стабильность порядка и байтов префикса между ходами; общий префикс до `cache_control`;
  JSON-цикл всех моделей запросов.
- **llm и учёт:** `cost_nano` = ручной расчёт (int); `/cost` по ролям/моделям/периодам, откат не обнуляет; мягкий лимит;
  журнал (ротация, gzip, blobs); сторож ключей; адаптеры на фейковых клиентах (Anthropic: `max_retries=0`, strict, без
  форсирования и префилла, перевод ошибок, refusal, usage; Gemini — аналогично + `Opaque`).
- **Сейв:** v1 → v2; сейв посреди боя на границе хода → доигрыш на моке идентичен; `/load`; `hero_dead` → предложение загрузки.
- **Сцена и время:** day → закрытие; hour → нет; 31-й ход → закрытие; `travel_to` → время по дистанции, `visited`, закрытие;
  без сдвига времени → +600 с.
- **Архитектура и UI:** сторож импортов; `ScriptedInput`/`CaptureOutput` (строка состояния, варианты, `[бросок]`); команды.

## Риски
Strict может не принять отдельные конструкции схем (проверить smoke-тестом; флаг `strict_tools=false` на инструмент);
Gemini — сверить SDK до кода; `auto` вместо форсирования — модель может «забыть» инструмент (промпт, режимы, бюджет повторов,
доля невалидных в журнале); синхронизация RNG на commit (тест «ход → сейв → загрузка → бросок совпадает»); импровизация из
`PlayerController` в обход `run_controller`; кэш может не включиться при малом префиксе; Opus 5.5 всегда думает (задержка,
стоимость — effort/Sonnet в конфиге); отпечаток схемы + снять xfail; сверка таблицы сокровищ; не тянуть этапы 3–4.

## Открытые вопросы — см. ответы проектировщика (decisions/stage2-plan.md после аппрува)

# Часть D. Чек-лист ручной живой сцены (Claude и Gemini)

Автотесты живых вызовов не делают. Перед закрытием этапа вручную один прогон на каждого провайдера: «разговор → проверка
→ бой». Риски — из D6 партии 4 (`docs/decisions/stage2-batch4-review.md`) и партии 3 (`stage2-batch3-review.md`).
Ключ в окружении или `.env`; заранее — `uv run python devtools/live_smoke.py anthropic` (и `gemini`): один вызов с одним
strict-инструментом, схема принята, `tool_use` разобран, стоимость посчитана.

Запуск: `uv run ai-dm --new --hero arn --seed 1`. Для Gemini: `/model narrator gemini:<id модели из конфига>` до первого
хода (выбор запоминается в мире; для чистого прогона — новый мир).

## Прогон

1. Разговор: «Спрашиваю трактирщика, что слышно в округе» (ход explore), потом ещё один ход explore.
2. Проверка: действие, требующее проверки (например, убедить трактирщика), в выводе строка `[бросок] ... vs СЛ ...`.
3. Бой: «Спускаюсь в подвал» → `start_combat`; пара ходов номером и текстом (с импровизацией), победа или поражение,
   меню повышения уровня при достаточном опыте.
4. `/cost`, затем `/quit`, затем `uv run ai-dm --world <id>` — мир продолжается с автосохранения.

## Что проверить (оба провайдера)

- [ ] Схемы инструментов приняты API: нет 400 «Schema is too complex» / ошибок strict (Anthropic) и ошибок схемы (Gemini).
- [ ] `tool_use` / вызовы функций разбираются: ход завершается, повествование и `[бросок]`-строки выводятся.
- [ ] Модель не «забывает» инструмент: доля невалидных ответов в журнале небольшая (`invalid` в `report_tags`).
- [ ] `cache_read > 0` на втором ходу explore (Anthropic: журнал `usage.cache_read`; Gemini: неявный кэш, `cache_read` может
      быть 0 при малом префиксе, это не ошибка, но записать).
- [ ] Gemini: два `user` подряд (результат инструмента, затем текст) не ломают запрос; Anthropic: n/a.
- [ ] Anthropic: ответ только из thinking (блок `Opaque` без текста) не приводит к пустому ходу или падению цикла.
- [ ] Refusal, если случился, даёт меню ошибки с подсказкой про тон и модель, а не трейсбек.
- [ ] Стоимость: `/cost` показывает ненулевые «сессию», «день», «мир» с ролью narrator и моделью; сумма в строке состояния
      растёт; значения правдоподобны для цен из `app_defaults.toml`.
- [ ] Журнал пишется: `saves/<id>/journal/calls-NNN.jsonl` есть, у ходов `turn_status` committed, `request_id` заполнен.
- [ ] Ключ нигде не печатается: ни в выводе игры и ошибок, ни в `saves/<id>/journal/`, ни в `meta/`
      (`grep -r "<начало ключа>" saves/<id>` пусто).
- [ ] id мира выведен при старте: `Мир: <id> (продолжить: ai-dm --world <id>)`.
- [ ] `/model narrator gemini:gemini-3.8-flash` с ключом только в `.env` (не в окружении) подключает Gemini.
- [ ] Replay живого прогона (`ai-dm --replay --world <id> --hero arn --seed N`) проходит без сети.
- [ ] Сбой посреди хода (например, отключить сеть на ход): меню ошибки, бандл прежний, «повторить» после возврата сети
      проходит.

Результат прогона (дата, модель, что не сошлось) записать в `docs/decisions/stage2-acceptance.md`.
