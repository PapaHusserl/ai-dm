# План этапа 2: протокол мастера, адаптеры, игровой цикл (простой режим)

Автор: папа-кабан. Статус: принят 2026-10-03 (решения — docs/plan-stage2.md). Основа: TZ.md, ARCHITECTURE.md, llm-notes/claude-api-facts.md,
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
  `docs/plan-stage2.md`): всё required, необязательное — обязательное поле с нейтральным значением («» / 0 / `"none"` /
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

## Открытые вопросы — см. ответы проектировщика (docs/plan-stage2.md после аппрува)

# Часть D. Чек-лист ручной живой сцены (Claude и Gemini)

Автотесты живых вызовов не делают. Перед закрытием этапа вручную один прогон на каждого провайдера: «разговор → проверка
→ бой». Риски — из D6 партии 4 (`docs/plan-stage2.md`) и партии 3 (`docs/plan-stage2.md`).
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

Результат прогона (дата, модель, что не сошлось) записать в `docs/plan-stage2.md`.

## Решения: Решения проектировщика по плану этапа 2 (2026-10-03) (бывш. docs/decisions/stage2-plan.md)

План: docs/plan-stage2.md — принят («окей, кабаним»).

| # | Вопрос | Решение |
|---|---|---|
| 1 | Серверный fallback модели при отказе | **флаг в конфиге `llm.refusal_fallback`, по умолчанию выключен**; при выключенном — как ТЗ 2.2 (без автосмены) |
| 2 | Герой этапа 2 | **выбор из двух при старте**: Арн (человек-воин, солдат) или Лиэль (волшебница) |
| 3 | Первая сцена | **мини-завязка в коде** (Вейл → таверна «Хромой гусь» → подвал, трактирщик, Гракх `goblin_boss`, `capture`) — заглушка до паков этапа 3, оформить данными |
| 4 | Narrator по умолчанию | **`claude-opus-5-5`**; Sonnet 5.5 — альтернатива в конфиге и через `/model` |
| 5 | Модели Gemini | без предпочтений — кабан выбирает по документации SDK, фиксирует в `docs/llm-notes/gemini-facts.md` |
| 6 | Повествование в бою | **после каждого хода героя** |

### Дополнения по ревью партии 1 (2026-10-03)

| # | Вопрос | Решение |
|---|---|---|
| 7 | Уникальность id | **строго**: единое пространство id для NPC, фракций, богов, локаций и героев; имена именованных NPC не совпадают с именами героев (`check_npc`/`check_location` получают героев) |
| 8 | Опыт за квест | доля от **размера уровня** (как реализовано) |
| 9 | Предметов за одну выдачу | 20 (как в конфиге) |
| 10 | Потолок золота за награду | 50 / 100 / 250 / 500 / 1000 зм для уровней 1–5 (как в конфиге) |

### Решения при приёмке этапа 2 (аудит кабана-свекрови, 2026-10-03)

| # | Вопрос | Решение |
|---|---|---|
| 11 | Завязка Вейла (WORLD_TEXT, «Гарт», мотивы, tone) | принять как заглушку до паков этапа 3 |
| 12 | Стиль рассказчика (`narrator_rules.md`) | **развёрнуто** (разумный предел 3–6 абзацев), обращение на **«ты»**, **атмосферно и образно**, реплики NPC — **прямой речью** |
| 13 | `/quit` и EOF | **автосохранение** в `auto` при выходе (состояние после последнего завершённого хода; не при `hero_dead`) |
| 14 | Дневной лимит трат | **общий для всех миров и по местному времени** |
| 15 | Опыт при завершении боя мастером (сдача) | **полный опыт за всех побеждённых** — убитые, выбывшие, сбежавшие, сдавшиеся/пленные (как в 5e); нет опыта только при поражении/смерти героя |
| 16 | Экономика наград | `loot_individual` — только по побеждённым в последнем бою, с их CR; лимит расходников за сцену (конфиг) |
| 17 | Ключевой NPC и модель | раз за бой, как сейчас (вернуться после живой игры) |

## Правки по ревью: Ревью партии 1 этапа 2: технические правки (оркестратор) (бывш. docs/decisions/stage2-batch1-review.md)

Вердикт мамы-кабана: можно мержить. Правки до партии 2:
1. `m0002.is_turn` — запись с ключами вне `{turn_seq, at_s, player_input, narration, requests, rolls}` отбрасывается (+ тест).
2. `individual_treasure.yaml` — комментарий «числа не сверены с SRD 5.2 (трек 1.5); если таблицы нет в SRD — source: custom».
3. `AppConfig` — `model_validator(after)`: модель каждой роли и `alternatives.narrator` есть в `prices` и `context_windows`,
   иначе ValueError (+ тест на пользовательский TOML).
4. `ModelPrice` — `strict=True` (float отвергается) (+ тест).
5. `LimitsConfig.gold_explicit_max_cp_by_level` — ключи ровно 1..5 (комментарий: MAX_LEVEL этапа 1) (+ тест).
6. `load_rules_config` — комментарий «внутренний загрузчик для devtools; игра использует `load_settings`».
7. Сторож архитектуры: пакеты движка (включая config) не импортируют `anthropic`, `google.genai`, `google`.
8. `app_defaults.toml` — комментарий: цены кэша Haiku выведены из правила ~0.1×/~1.25× входа (сверить с прайсом).
Исполнители: K — пункты 1–8 в `src/**` и `docs/**`; T — тесты к 1, 3, 4, 5, 7.

## Правки по ревью: Ревью партии 2 этапа 2 (протокол): спецификация правок (бывш. docs/decisions/stage2-batch2-review.md)

Источник: ревью мамы-кабана + официальные лимиты strict (docs/llm-notes/claude-api-facts.md). Решения — оркестратор.
Исполнители: K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

### S. Лимиты strict-схем (блокирующее для партии 3)
Сейчас: 21 strict-инструмент в видимом наборе и 45 union-параметров → 400 «Schema is too complex».
S1. **Без union вообще.** Необязательные поля в схеме для модели — обязательные НЕ-nullable с нейтральным значением:
    bool → `false`; списки → `[]`; enum → значение-«ничего» в enum (`stakes: "normal"`, `pace: "normal"`, и т.п.);
    строковые ссылки (`failed_roll_ref`, `evidence_ref`, `npc_id`, `travel_to`, `debt_to`, `lair_location_id`, …) → `""`
    означает «нет»; числа → `0` означает «нет», где это однозначно. `set_flag.value` — один тип: строка (`"true"`/`"false"`
    или текст) либо два отдельных поля `value_bool` / `value_text` — выбери простое, чтобы не было union.
    Pydantic-модели запросов при разборе нормализуют нейтральные значения в `None` (внутренний API протокола не меняется).
    Схема выводится так, чтобы `anyOf`/массивов типов не было нигде.
S2. **Наборы инструментов по режиму** (`protocol.schema.tool_set(mode)`), каждый ≤ 16 strict-инструментов:
    - `explore`: skill_check, saving_throw, start_combat, damage, give_item, take_item, gold, award_xp, advance_time, rest,
      set_flag, npc_create, location_create, npc_update, offer_choices, end_scene, end_chapter, unsupported_action
      — если больше 16, вынести редкие (end_chapter, location_create, set_flag) без strict (`strict: false`, Pydantic
      проверяет всё равно) и зафиксировать в отчёте, какие;
    - `combat_classify`: player_action, unsupported_action;
    - `combat_narrate`: offer_choices, unsupported_action, end_combat, defeat_outcome;
    - `npc_choice`: npc_action.
    `tool_defs(exposed)` остаётся; `apply` по-прежнему принимает любой видимый запрос (контроль режима — MasterSession, партия 4).
S3. **Тест-сторож**: для каждого режима — strict-инструментов ≤ 20, union-параметров = 0, необязательных = 0, нет
    неподдерживаемых ключевых слов (список из справки). План A2 («`["T","null"]`») — поправить в docs/plan-stage2.md.

### Блокирующие (по ревью)
B1. `start_combat`: после среза до `max_enemies` убрать группы без участников; выпал лидер → лидер = первый оставшийся член
    группы; результат clamped + `limit-exceeded`, бой создан. Пустой `enemies` → Invalid `no_enemies`.
B2. `start_combat`: NPC мира со статусом ≠ `alive` → Invalid `npc_unavailable`.
B3. `npc_update`: сначала проверка условий смерти (причина, ссылка); не выполнены → rejected `invalid-death` **до любых
    мутаций** (отношение не меняется). Метки урезания и отказа не затирают друг друга: в `ctx.marks` попадают обе.
    Пустой запрос (нет ни `attitude_delta`, ни `status`, ни `location_id`) → Invalid `empty_update`.
B4. `defeat_outcome`: `lair_location_id` ∉ `world.locations` → Invalid `unknown_location`; `debt_to` ∉ `world.npcs` → Invalid
    `unknown_npc`; `rob_items` урезается до 1..2 → clamped + `limit-exceeded`.
B5. `defeat_outcome`: `Rejected` из `apply_defeat_outcome` (ошибки формы) → `Invalid(code="invalid_defeat", message=reason)`.
B6. `damage`: если `after_damage` вернул `"down"` **или** `"failure"` (герой уже лежал) → `resolve_out_of_combat`.
    Урон по мёртвому герою → Invalid `hero_dead` (без второго `hero_died`). `result` содержит `hero_status` и исход
    спасбросков; `resolve_out_of_combat` возвращает строки бросков (каждый спасбросок — строка в формате ТЗ 6) —
    сигнатура: возвращает `(outcome, logs)` или объект; обнови вызовы. `failed_save=(severity == "deadly")`.

### Желательные (делаются сейчас)
D1. `rest(short, hit_dice > доступных)` → clamped до доступного + `limit-exceeded` (как take_item).
D2. `roll_ref` «тратится»: один проваленный бросок — одно смертельное последствие (`damage(deadly)` или смерть NPC);
    повторное использование → clamped (урон) / rejected `invalid-death` (смерть). Множество использованных в `TurnContext`.
D3. Отношение у предела ±100: лог и списание из лимита сцены — по фактическому изменению.
D4. id боя: первое `n ≥ 1`, для которого нет флага `combat_ended:combat_{n}` и нет активного боя с таким id.
D5. Invalid от `validate_start` — все коды с русскими подсказками и id сущностей (словарь «код → подсказка»).
D6. `npc_action` — в `HANDLERS` (контроль режима остаётся в обработчике).
D7. Синхронизировать docs/plan-stage2.md: лимиты в обработчиках (нет `limits.py`), union → нейтральные значения, наборы по режимам.
Вне партии (записано для этапа 3): уникальность при загрузке пака; пробуждение стабильного героя вне боя (SRD: 1 HP через
1d4 часа) — этап 2 партия 5 (game) или этап 3 — решит план партии 5.

### Тесты (T)
S3-сторож; обновить тесты под S1 (нейтральные значения в схемах; Pydantic нормализует в None) и S2 (наборы по режимам);
B1–B6, D1–D6 — по тесту на каждый пункт (7 врагов с лидером второй группы седьмым → clamped, бой создан; мёртвый NPC в бою;
комбинированный npc_update `attitude_delta=50, status=dead, cause=chance` → rejected, отношение прежнее; defeat_outcome со
ссылками и rob_items=50; damage: down→stable/revived/dead, уже лежащий, мгновенная смерть от массивного урона, урон по мёртвому;
повторное использование roll_ref; rest clamp; id боя с заранее существующим флагом; подсказки validate_start).

## Правки по ревью: Партия 2 этапа 2 (протокол): решения оркестратора и проектировщика (бывш. docs/decisions/stage2-batch2.md)

1. `event_start`: поле типа события — `event_type` (поле `type` занято дискриминатором запроса).
2. `give_item`: лимит `give_item_max_qty` — на одну выдачу (на запрос), не на итоговый стек.
3. `advance_time(travel_to)`: связи между локациями **двусторонние** — маршрут ищется и в `connections` целевой локации
   (обратная связь не обязательна).
4. `take_item` с `qty` больше имеющегося → **clamped** до имеющегося + `limit-exceeded` (как `gold lose`, ТЗ 2.3), не Invalid.
5. `player_action.unsupported` → `report_tag = missing-mechanic` (ТЗ 7).
6. **Строгая уникальность (решение проектировщика 7):** `rules.uniqueness.check_npc(world, npc, heroes)` и
   `check_location(world, location, heroes)` — id уникален среди NPC, фракций, богов, локаций и героев; имя именованного NPC не
   совпадает с именем героя; имена NPC/богов/фракций — общее пространство (как раньше); локации — в пределах родителя.
   Протокол передаёт героев бандла.
Исполнители: K — 3, 4, 5, 6 в `src/**`; T — 1, 2 (правка тестов) и тесты к 3–6.

## Правки по ревью: Ревью партии 3 этапа 2 (слой llm): спецификация правок (бывш. docs/decisions/stage2-batch3-review.md)

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `devtools/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

### Блокирующие
B1. Gemini `FINISH_REASONS`: `PROHIBITED_CONTENT`, `BLOCKLIST`, `SPII`, `RECITATION` → `refusal` (как SAFETY); строка в gemini-facts.
B2. Конфиг Gemini (`app_defaults.toml`, `config/app.py`):
    - `[prices.gemini-3.8-flash]` input 750000, output 3750000, cache_read 75000, cache_write = input (комментарий: неявный кэш
      Gemini, адаптер cache_write не заполняет; «пересмотреть с 2027-01-01: 1.50/7.50/0.15»);
      `[prices.gemini-3.5-flash-lite]` 300000 / 2500000 / 30000, cache_write = input;
    - `[context_windows]` обеим 1000000 (комментарий «консервативно, сверить»);
    - `AppConfig.profiles: dict[str, RolesConfig] = {}`; `[profiles.gemini.narrator|world|summarizer]` (narrator —
      gemini-3.8-flash, world/summarizer — gemini-3.5-flash-lite; effort для Gemini не используется — допустимо поле, игнорируется);
      `check_models_known` проверяет и роли профилей.
B3. `devtools/live_smoke.py`: для `gemini` роль из `cfg.profiles["gemini"].narrator`; effort передаётся, только если модель =
    модели роли (иначе — без effort).
B4. Gemini-клиент с таймаутом: `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=cfg.retry.timeout_s * 1000))` (мс).

### Желательные (делаются сейчас)
D5. Gemini `FunctionResponse` с `id`, если `call_id` пришёл от API (не синтезированный `gemini-…`):
    `Part(function_response=FunctionResponse(id=..., name=..., response=...))`; иначе — как сейчас. Риск в gemini-facts.
D6. Gemini: сборка `contents`/`config` до `try` (как у Anthropic); неизвестный `call_id` → понятный `ValueError`.
D7. `errors.NETWORK_NAMES` + `"TransportError"` (общий предок транспортных ошибок httpx), `RemoteProtocolError`, `ReadError`, `WriteError`.
D8. Журнал устойчив к обрыву: нечитаемая последняя строка сегмента пропускается при чтении; перезапись сегмента в `mark_turn` —
    через временный файл и `os.replace`.
D9. **Формат журнала (до этапа 6):** поле `run_id` (передаёт вызывающий, один на прогон хода; повтор того же хода — новый
    `run_id`) и `ts` (передаётся параметром — без `time.time()` в llm; если нужно, вызывающий передаёт строку); `mark_turn(run_id, status)`
    помечает записи этого прогона; Replay группирует по `run_id` в порядке записей. В ledger — поле `call_id`.
D10. Чистка `blobs/`, на которые не ссылается ни один оставшийся сегмент, при удалении сегментов по `max_mb`.
D11. (T) сквозной сторож ключей: фейковый клиент Anthropic и Gemini бросает ошибку с ключом в тексте → `call_with_retries` →
     `journal` → ключа нет ни в одном файле. Комментарий-напоминание для этапа 6 в errors.py: исходное исключение в `__cause__`,
     трейсбек в репорт не выводить.
D12. (T) 2–3 теста Gemini на настоящих `google.genai.types`: `build_config` для всех `tool_set`; `parse_response` → JSON →
     `build_contents` с `thought_signature` (bytes). Убрать устаревший комментарий «SDK не установлен».
D13. `retry_after_of`: `float`, учитывать `retry-after-ms`; **408 → transient** в обоих адаптерах.
D14. `ChatResponse.model` из ответа провайдера (Anthropic `response.model`, Gemini `model_version` или запрошенная); учёт стоимости
     и журнал — по фактической модели (если нет цены — по запрошенной + метка).
D15. Gemini `count_tokens`: + оценка system+tools (`len(json) // 4`); ограничение — в gemini-facts.
D16. Модель — из `req.model`; `self.model` только для `info()`; тест фабрики — равенство.
D17. Лимиты стоимости в микро-долларах, как цены: `session_limit_micro`, `day_limit_micro` (0 = нет); перевод в нано внутри `check_limit`.

## Правки по ревью: Ревью партии 4 этапа 2 (master): спецификация правок (бывш. docs/decisions/stage2-batch4-review.md)

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

### Блокирующие
B1. `max_tokens` + `tool_use`: вызовы не исполняются; в следующее user-сообщение — `ToolResult(call_id, content=<пояснение
    «ответ оборван по длине, повтори короче»>, is_error=True)` на каждый вызов, Text-пояснение — последним блоком;
    `invalid_count += 1`.
B2. `run_call`: `call.input.get("type") != call.name` → `Invalid(code="invalid_request", message=...)` до `parse_request`.

### Желательные (делаются сейчас)
D1. `MasterSession.run(..., *, world_text="")` → `build(..., world_text=world_text)`.
D2. **Контракт для партии 5 (записать в docstring и в STAGE2-PLAN A4):** game создаёт `PromptBuilder(app_cfg, model=<модель выбранного
    адаптера>, count_tokens=<адаптер.count_tokens>)` и передаёт в сессию. Оценка бюджета: `count_tokens` адаптера вызывается
    **один раз** на запрос (полный), дальше выкидывание ходов — по эвристике; эвристика для кириллицы `len // 3` (вместо `// 4`).
    Ошибка `count_tokens` → эвристика (не падать).
D3. `run_id` передаётся в `run(..., run_id=...)` (по умолчанию — из конструктора); счётчик `call_id` — по run_id
    (`{run_id}-{n}` уникален в пределах run_id даже при нескольких вызовах `run`). Правило: все вызовы мастера одного прогона хода
    (classify / npc_choice / narrate) используют один `run_id`.
D4. `MasterResult.texts` — только из принятых ответов; добавить `MasterResult.narration` = текст финального принятого ответа
    (то, что показывает игра).
D5. Пустой ответ при `required is not None and required_done` → успех (не тратит бюджет).
D6. Риски для живого smoke (партия 6, в STAGE2-PLAN): два user подряд у Gemini; ответ только из thinking (Opaque) у Anthropic;
    `cache_read > 0` на втором ходу explore.
D7. Кэш внутри цикла инструментов — третья точка `cache_control` на последнем сообщении истории раунда (лимит 4 точки).
D8. `narrator_rules.md`:
    - раздел о режимах: «в бою фразу игрока передай через `player_action`; при поражении героя обязателен `defeat_outcome`; ход NPC —
      `npc_action`; набор инструментов в запросе — всё, что доступно сейчас»;
    - формат входа: сообщение — JSON, `player_input` — ввод игрока, остальное — состояние; system[1] — данные мира;
    - «в инструментах используй только id из `monster_ids`/`item_ids`» (вместо «нельзя называть id»);
    - «лечение — только `rest`; иное лечение — `unsupported_action`»;
    - «смерть NPC через `npc_update` — только с `cause` goal/hazard и ссылкой на бросок этого хода».
D9. Мелочи: «Инструмент X: в этом режиме недоступно.»; убрать дубль `role_cfg`.

### Тесты (T)
B1 (`max_tokens` с tool_calls → у каждого ToolCall есть ToolResult is_error, executor не вызывался, invalid_count 1); B2 (рассогласование
name/type у нестрогого инструмента и при strict_tools=false — Invalid, ничего не исполнено); D1 (`world_text` в system[1], стабилен между
ходами); D2 (count_tokens зовётся один раз; ошибка count_tokens → эвристика); D3 (два `run()` на одной сессии — разные call_id; явный
run_id); D4 (texts/narration без отбракованных ответов); D5 (пустой ответ после accepted player_action — успех); два Invalid в одном ответе —
одна единица бюджета; D7 (cache-точка на последнем сообщении раунда, ≤ 4 точек); D8 (правила упоминают `player_action`, `defeat_outcome`,
`npc_action`, `rest`, `monster_ids`).

## Правки по ревью: Ревью партии 5 этапа 2 (game): спецификация правок (бывш. docs/decisions/stage2-batch5-review.md)

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

### Блокирующие
B1. **Смерть в бою и временное правило:** `TurnRunner.close_scene_if_needed` при `result.hero_dead` — не закрывать сцену и не
    делать автосейв; `GameApp.load`: если у загруженного героя `status == "dead"` — `pending = "hero_dead"`.
B2. **Битый `models.json`:** общая `check_model(provider, model) -> str | None` (цена, окно, фабрика, MissingKey/ValueError) —
    используется в `set_narrator` и при старте; `read_models` и доступ к ключам — в `try (ValueError, KeyError, OSError)`;
    ошибка → `startup_lines` «Сохранённая модель не подключена: …», остаётся переданный адаптер. Запись `models.json` —
    атомарно (tmp + `os.replace`).
B3. **run_id уникален между перезапусками:** `TurnRunner(..., run_tag=None)`; метка `f"{now:%Y%m%dT%H%M%S}-{tag}"`,
    `tag = run_tag or uuid4().hex[:6]`; тесты передают фиксированный `run_tag`.
B4. **Варианты боя в промпте:** `TurnContext(..., combat_options=None)` — game заполняет из `combat_flow.preview_options`
    (`[{id, label}]`); `PromptBuilder` кладёт `combat.options` в state-JSON при `combat_classify` (варианты на границе хода) и
    `combat_narrate` (варианты следующего хода героя после `advance_until_player`; бой кончился → `[]`); в system вариантов нет.
    `narrator_rules.md`: «в `player_action.steps` используй только id из `combat.options`».
B5. **История в сейве:** `MasterConfig.recent_turns_keep: int = 50`; `TurnRunner.commit` оставляет последние N записей.

### Желательные (делаются сейчас)
D1. `CombatRoundLimit` в ходе → `TurnFailed("round_limit", ...)` → обычное меню ошибки.
D2. **Нат-20 во время фазы NPC:** если герой пришёл в сознание в своём шаге (спасбросок от смерти), `advance_until_player`
    останавливается и ход переходит к игроку (герой действует в этот же ход, по SRD и batch5-review этапа 1 п.12).
D3. `protocol/handlers/combat.player_action`: при наличии `ctx.combat_options` первый шаг обязан быть из них, иначе
    `Invalid(code="unknown_step")` (модель переспросят); последующие шаги (могут появиться после первого) — как сейчас
    (пропуск с пометкой).
D4. `GameApp(..., use_stored_model=True)`; CLI (партия 6) выключает для `--mock`/`--replay`.
D5. `hero_of` — одна функция в `game/scene.py`, используется везде (без фолбэка на `heroes[0]`).
D6. `starter.new_world` вызывает `start_scene(bundle)` вместо ручной сборки `SceneState`.
D7. `TurnResult.scene_summary` / `chapter_title` (из `TurnContext`) — пробрасываются; комментарий в `on_scene_boundary` (этап 4).
D8. **Опыт за бой:** при завершении боя с живым героем (`victory` или `ended_by_master`) — за врагов `dead`/`down`;
    за `fled` и оставшихся на ногах при `ended_by_master` — нет. Комментарий в `finish_combat`.
D9. Комментарий в `MasterChoiceController`: модель выбирает первое действие раненого хода, остальное — `EngineTactics`.
D10. (T) сторож `test_lower_layers_do_not_import_game` — учитывать относительные импорты.
D11. `/save` при `pending == "hero_dead"` — запрещён с сообщением.

### Тесты (T)
B1 (смерть в бою → `load_last_save` → герой active, в `auto` — сейв до боя; загрузка слота с мёртвым героем → pending hero_dead);
B2 (битый JSON / без ключей / модель без цены → старт с переданным адаптером + строка в startup_lines; атомарная запись);
B3 (два раннера с одинаковым `now` на одном журнале → разные run_id; фиксированный run_tag → детерминизм);
B4 (`combat.options` в classify совпадает с `preview_turn()`, в narrate — следующий ход; system без вариантов — префикс стабилен);
B5 (51-й ход вытесняет первый, turn_seq растёт, окно промпта 8); D1 (CombatRoundLimit → меню ошибки); D2 (нат-20 в фазе NPC →
ход у игрока); D3 (первый шаг не из options → Invalid unknown_step); D4; D8 (опыт при ended_by_master за dead/down, не за fled);
D10; D11. Обновить существующие тесты под изменения.

## Правки по ревью: Ревью партии 6 этапа 2 (ui + приёмка): спецификация правок (бывш. docs/decisions/stage2-batch6-review.md)

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `docs/**` кроме TZ, `README.md`; T — `tests/**`. Параллельно.

### Блокирующие
B1. **Replay изолирован:** при `--replay` записи журнала читаются из настоящего `saves_root/<world>`, а `GameApp` работает в отдельном
    корне `tempfile.mkdtemp(prefix="ai-dm-replay-")` (путь — одной строкой при запуске). Живой мир (journal, meta/costs.jsonl,
    slots, models.json) не меняется. Фразу README «берите копию журнала» убрать.
B2. **Replay требует `--seed` и `--hero`** (иначе код 2 + сообщение); `--new` подразумевается; пустой журнал → «Журнал мира X пуст»,
    код 1, до создания мира.
B3. **`--new --world <существующий id>`** (без replay) → «Мир X уже есть: продолжить — ai-dm --world X», код 1.
B4. **Вывод хода:** в `show_reply` строки `turn.lines`, которые есть в `turn.log`, не печатаются повторно; префикс `[бросок]` — только для
    строк из `turn.rolls`; служебные строки протокола (`Действие игрока: …`, `Варианты ответа предложены`) не печатаются.
B5. **Мягкий лимит по сессии и по дню:** худшее из `check_limit(session, session_limit_micro)` и `check_limit(day, day_limit_micro)`;
    дата — как в `cmd_cost` (`app.now().astimezone(UTC).date()`) в `status_line` и `limit_state`.
B6. **id мира выводится при старте:** `Мир: <id> (продолжить: ai-dm --world <id>)`.

### Желательные (делаются сейчас)
D1. **Начальный автосейв:** после `new_world` (не replay) — `save_current("auto")` (начало мира = граница сцены). Сообщение при
    `--world X` без автосейва: «нет автосохранения мира X».
D2. **Ошибка посреди хода в живой игре:** `simple.run` ловит `Exception` вокруг `handle`/`choose` (кроме replay — там выход с кодом 1):
    «Ошибка хода: …» (с redact), цикл продолжается (бандл прежний).
D3. Лимит проверяется только при `app.pending is None` (не два меню сразу).
D4. «Сохранить и выйти» из меню лимита — запрещено при `pending == "hero_dead"`; `ValueError` от `save_current` ловится как в `cmd_save`.
D5. «Продолжить» в паузе лимита отключает паузы до конца сессии — записать здесь (решение оркестратора, ТЗ 2.0 допускает) и строкой в README.
D6. Чтение ключей — внутри `try` в `main`; `redact` и в `play` («Не удалось подготовить модель: …»).
D7. `--hero`/`--seed` с `--world` без `--new` (и без replay) → код 2 + сообщение.
D8. `ask_hero` переспрашивает при неверном ответе до EOF.
D9. `status_line` использует `DAY` из `core/clock.py`.
D10. Документы: ARCHITECTURE C4 — ограничения replay (обязательны `--seed`/`--hero`, временный каталог, живой мир не меняется);
     STAGE2-PLAN часть D — пункты «id мира выведен при старте», «`/model narrator gemini:gemini-3.8-flash` с ключом только в `.env`»,
     «replay живого прогона (`ai-dm --replay --world <id> --hero arn --seed N`) проходит без сети»; README — где взять id.

### Тесты (T)
B1 (два replay подряд на той же папке: оба код 0, journal/, meta/costs.jsonl, slots/ побайтно прежние; путь temp выведен);
B2 (replay без seed/hero → код 2; пустой журнал → код 1 до создания мира); B3; B4 (строки инициативы на ходу старта боя — ровно
по одному разу; `[бросок]` только у бросков; служебных строк нет); B5 (дневной лимит срабатывает при выключенном сессионном);
B6; D1 (после `--new` и `/quit` — `--world X` продолжает); D2 (исключение в ходе живой игры → «Ошибка хода», цикл жив; в replay — код 1);
D3; D4; D6 (mock_factory бросает `RuntimeError(f"bad {key}")` → в выводе `***`, ключа нет; Ctrl-C → код 130); D7; D8.
**Честная победа через `main`:** подобрать сид (как `sim_combat --find-outcome`), на котором Арн с родными HP побеждает, и пройти
«разговор → проверка → бой → победа → автосейв → меню уровня» через `main(..., mock_factory=lambda p: ScriptThenReactive(...))` с
`FightInput`; `test_cli_world_resumes_*` — на этом CLI-прогоне. Тесты на `run()` с героем 200 HP можно оставить как дополнительные.

### Решение по D5
«Продолжить» в меню лимита отключает паузы до конца сессии (флаг `asked` в `ui/simple.run`); предупреждение `warn` тоже
показывается один раз за сессию. ТЗ 2.0 это допускает. Строка про это есть в README.

## Итог: Аудит этапа 2 (кабан-свекровь): спецификация правок перед приёмкой (бывш. docs/decisions/stage2-audit.md)

Решения проектировщика 11–17 — docs/plan-stage2.md. Технические — оркестратор.
K — `src/**`, `docs/**` кроме TZ, `README.md`; T — `tests/**`. Параллельно. Стиль рассказчика (решение 12) — отдельной правкой
после описания проектировщика, сейчас `narrator_rules.md` по стилю не трогать.

### Препятствия живому запуску (технические)
E1. **Старт только с ключом Gemini:** CLI создаёт адаптер по выбранному провайдеру: сначала сохранённая модель мира (`models.json`),
    затем `roles.narrator`; если ключа для narrator нет, но есть ключ другого провайдера с ролью в профиле — предложить/использовать
    профиль этого провайдера (`profiles.gemini.narrator`) с сообщением; мир, сохранённый под Gemini, открывается без ключа Anthropic.
    Флаг CLI `--provider anthropic|gemini` (явный выбор профиля для нового мира).
E2. **Модель видит нужные id:** в state-JSON промпта:
    - `locations`: текущая локация + связанные с ней (`id`, `name`, расстояние) — для `travel_to`;
    - `known_npcs`: именованные живые NPC мира с `id`, `name`, `location_id`, `key` (мотивы/секреты — нет; секреты — этап 3);
    - сообщения Invalid про неизвестный id (локация, NPC, предмет, монстр) перечисляют допустимые id (до ~20).
    Мир «Вейл» в state-JSON помещается целиком; при больших мирах (этап 3) — релевантные (этап 4).
E3. `max_tokens` narrator: 16000 (мышление Opus 5.5 входит в лимит); для Gemini — тот же `max_tokens`.

### Решения проектировщика
P13. `/quit` и EOF → `save_current("auto")` (кроме `pending == "hero_dead"`); сообщение «Сохранено: auto».
P14. Дневной лимит и «день» в `/cost` — общий для всех миров (ledger-агрегат по всем `saves/*/meta/costs.jsonl`) и по местному
     времени (`app.now().astimezone()` — локальная зона ОС).
P15. Опыт за бой при любом исходе без поражения/смерти героя — за всех врагов: `dead`, `down`, `fled`, и оставшихся на ногах при
     `ended_by_master` (сдались). Поражение героя (`defeat_*`, `hero_dead`) — без опыта.
P16. `gold loot_individual`: параметр `cr` от модели игнорируется/запрещён — добыча считается по побеждённым врагам последнего
     завершённого боя этой сцены (их ПО), один раз на бой (повтор → rejected); вне боя/без боя → Invalid. Лимит расходников за
     сцену: `limits.consumables_per_scene = 3` (предметы с эффектом heal или категорией расходника) → сверх — clamped.

### Технические (аудит A–C)
T1. `PromptBuilder` берёт effort/max_tokens роли выбранной модели (narrator / alternatives.narrator / profiles.<p>.narrator).
T2. `refusal_fallback` для Gemini — строка в gemini-facts («флаг действует только для Anthropic»).
T3. README: «номер в бою — без вызова модели на разбор; рассказ после хода — вызов модели»; ручной мок-прогон — ограничение
    (мок-сценарий кончается на начале боя) или CLI-флаг `--mock-reactive` с реактивным моком для ручной проверки боя (выбери простое).
T4. Сид нового мира печатается рядом с id мира.
T5. `individual_treasure.yaml`: `source: custom` (числа не сверены с SRD 5.2; сверка — трек 1.5).
T6. ARCHITECTURE C7 — ссылки на `docs/plan-stage2.md`, `docs/plan-stage2.md`.
T7. В план/бэклог: сокровища логова (hoard) и ограничение редкости магпредметов по уровню (ТЗ 2.3) — этап 3; выжимки сцен
    (`end_scene.summary`) — этап 4.

### Тесты (T)
E1 (только `GEMINI_API_KEY` → старт через профиль gemini; мир под Gemini открывается без ключа Anthropic; `--provider`);
E2 (state-JSON содержит связанные локации и известных NPC с id; Invalid перечисляет допустимые id; живой сценарий «Спускаюсь в подвал»
без знания id в моке: модель берёт id из state); E3; P13 (`/quit` и EOF сохраняют; при hero_dead — нет); P14 (лимит дня суммирует
два мира; граница дня по локальному времени); P15 (опыт за fled и сдавшихся; нет при поражении); P16 (loot только по побеждённым
последнего боя, повтор rejected, без боя Invalid; 4-е зелье за сцену clamped); T1; T4.

## Итог: Живой прогон 1: стоимость и оформление вывода (2026-10-03) (бывш. docs/decisions/stage2-live-1.md)

### 1. Разбор стоимости (журналы миров vale-be63e7c3, vale-ea0ddaed; Opus 5.5)
Ход вне боя = 2 вызова (раунд с инструментом + финальный текст). Типичный ход ≈ $0.034, первый ход сессии ≈ $0.07.
| Статья | Токены | $ | Доля |
|---|---|---|---|
| Запись кэша префикса (tools+правила+мир) | ~7 800 × 1.25 × $4/M | ~$0.039 | раз на сессию / после 5 мин простоя |
| Запись кэша истории раунда (точка на последнем сообщении, D7 партии 4) | ~2 000–2 200 × $5/M | ~$0.010–0.011 | **каждый ход, не переиспользуется** |
| Выход (рассказ + мышление Opus, effort medium) | ~860–890 × $20/M | ~$0.017 | каждый ход |
| Чтение кэша, вход | ~7 800 × $0.2/M + ~800 × $4/M | ~$0.005 | каждый ход |

### 2. Спецификация (K — src/docs; T — tests)
C1. **Убрать точку кэша на последнем сообщении раунда** (D7 партии 4): при 2 вызовах на ход запись не окупается.
C2. **TTL кэша префикса — 1 час** (`cache_control: {type: ephemeral, ttl: "1h"}` для блоков system; запись дороже ×2, но не
    повторяется после 5 минут раздумий игрока). Параметр `llm.cache_ttl = "1h"` в app_defaults (значения "5m" | "1h").
C3. **effort narrator по умолчанию — `low`** (мышление Opus 5.5 — основная часть выхода сверх рассказа); в конфиге.
C4. `/cost` и строка состояния — без изменений. Ожидание после C1–C3: ход Opus ≈ $0.015–0.02; Sonnet 5.5 ≈ вдвое дешевле.

### 3. Оформление вывода (решение проектировщика)
U1. Ширина строки ≤ 80 символов везде (перенос по словам, `textwrap`); ширина — константа/конфиг `ui.width = 80`.
U2. **Повествование — в рамке** из псевдографики:
    ```
    ╭──────────────────────────────────────────────────────────────────────────────╮
    │ Ты спускаешься по скрипучим ступеням. Пахнет сыростью и прогорклым жиром…    │
    │                                                                              │
    │ — Ещё эля? — хрипло спрашивает трактирщик.                                   │
    ╰──────────────────────────────────────────────────────────────────────────────╯
    ```
    Абзацы сохраняются (пустая строка внутри рамки), перенос внутри рамки по словам, рамка ровно 80 символов.
U3. **Броски** — отдельным блоком с отступом и маркером: `  🎲 d20 (14) + 5 = 19 vs КД 15 → попадание` (если эмодзи
    ломают ширину — `  ⚄ ` или `  [d20] `; выбери надёжно моноширинное и обоснуй); лог боя — с отступом 2 пробела.
U4. **Варианты / действия / меню** — заголовок и список с отступом:
    ```
      Что делаешь?
        1. Согласиться и сразу спуститься в подвал
        2. Сначала расспросить Гарта
    ```
    длинные пункты переносятся с отступом под текст пункта.
U5. **Строка состояния** — разделитель на всю ширину: `── HP 12/12 · 1 Заревня 0001, 00:00 · сессия $0.0150 ──`.
U6. Служебные сообщения (сохранено, ошибки, мир/сид) — с отступом, без рамки.
U7. Тесты ui проверяют содержимое без учёта рамки/переносов (хелпер «снять оформление»), плюс отдельные тесты оформления:
    ни одна строка вывода не длиннее 80; рамка закрыта; абзацы сохранены; перенос не рвёт слова.

### 4. Живой прогон 2 (мир vale-f82f1cca, Opus, $0.70 за 7 ходов до поражения у гоблинов)
Разбор 21 вызова: вход без кэша 95 476 ток. ≈ $0.38 (55%), выход 9 017 ≈ $0.18, запись кэша ≈ $0.11.
Причина: сообщение хода (state-JSON с `recent_turns` — 8 развёрнутых рассказов) растёт до ~6 000 ток. и в каждом раунде хода
(2–5 вызовов) идёт без кэша; плюс лишний вызов «Пустой ответ», когда рассказ уже написан вместе с инструментом.
L1. **Кэш-точка на сообщении хода** (state) с TTL **5m** (system — 1h; порядок «длинный TTL раньше» соблюдён). Раунды 2…n читают его
    из кэша. Учёт: запись 5m = 1.25× входа, 1h = 2× — `Usage` различает (`cache_creation.ephemeral_5m_input_tokens` /
    `ephemeral_1h_input_tokens` в SDK — сверить с установленным anthropic), цены: `cache_write` (5m) и `cache_write_1h`.
L2. Пустой/пробельный финальный текст **принимается без повтора**, если в ходе уже есть принятый рассказ (текст при вызовах инструментов).
L3. `recent_turns = 4` (решение проектировщика: 4 хода целиком).
### 5. Герой Грей (решение проектировщика)
G1. Третий готовый герой «Грей» (`--hero grey`, пункт меню 3): как в импорте `saves/drunk_dragon/.../heroes/01_grey/hero.json` —
    человек, следопыт 1 ур., Сил 12 Лов 17 Тел 13 Инт 10 Мдр 15 Хар 8, навыки/черты/предыстория «Егерь-одиночка» как там,
    без заклинаний; **снаряжение — стандартное SRD следопыта** (стартовый набор класса, вариант A), предметы кампании — этап 3.
    Мастерства оружия — по SRD-оружию набора (длинный лук + основное оружие ближнего боя). Если движок чего-то для следопыта
    не поддерживает — не выдумывать, перечислить в отчёте.
G2. **Атака любым своим оружием** (правило 2024: достать/убрать одно оружие — часть действия Атака): `attacks_of` предлагает атаку
    каждым оружием из инвентаря героя (не только `main_hand`), с учётом владения/мастерства этого оружия; выбранное оружие
    становится оружием в руке. Дальнее/ближнее — по дистанции, как сейчас. Для монстров — без изменений.
    Допущение: провоцированная атака героя с дальним оружием в руке идёт ближним оружием из инвентаря (строго по 2024 — без
    смены оружия вне действия Атака); сверить при приёмке боевых правил.

### 6. Явный кэш Gemini (решение проектировщика, 2026-10-03)
Прогон vale-54a9cf01: неявный кэш сработал в 3 вызовах из 15, вход ~5–8 тыс. ток. по полной цене.
X1. Адаптер Gemini создаёт явный кэш (`client.caches.create`: system_instruction + tools набора режима, TTL из `llm.cache_ttl`)
    и передаёт `cached_content=<name>` в запросе (без повторной передачи system/tools — сверить ограничения SDK).
    Ключ кэша — (модель, sha256 system, sha256 tools); имя держится в памяти адаптера на сессию; кэш истёк/не найден → пересоздать
    один раз и повторить запрос; ниже минимального размера кэша модели или ошибка создания → запрос без явного кэша (как сейчас).
X2. Учёт: `cached_content_token_count` → `cache_read`; создание кэша — `cache_write` по цене входа; хранение кэша (за 1M ток. в час)
    — цена `cache_storage_hour` в `prices.<gemini-модель>`, начисляется при создании за весь TTL (записью в ledger).
X3. Факты (минимальный размер, цена хранения, ограничения `cached_content` с tools/system) — в gemini-facts.md с источником; сверка по
    установленному google-genai и официальной документации (WebFetch можно). Ключи не логировать; имя кэша можно.
X4. Тесты на фейковом клиенте: создание один раз на (модель, system, tools); повторное использование; пересоздание при истечении;
    откат без кэша; учёт стоимости; новый набор режима → свой кэш.

### 7. Модель по умолчанию — Gemini (решение проектировщика, 2026-10-03)
«Gemini по тексту нравится больше Sonnet, Opus сильнее; пока по умолчанию Gemini.»
M1. `roles.*` по умолчанию = профиль Gemini (narrator `gemini-3.8-flash`, world/summarizer `gemini-3.5-flash-lite`).
M2. Набор Anthropic — `profiles.anthropic` (narrator `claude-opus-5-5` effort low max_tokens 16000, world/summarizer Haiku);
    `alternatives.narrator` — Sonnet 5.5 без изменений. `profile_narrator` единообразно берёт `profiles[provider]`.
M3. Есть только ключ Anthropic → профиль anthropic с сообщением (как E1 зеркально). Сохранённые миры — на своей модели.
M4. README, STAGE2-PLAN — модель по умолчанию; тесты, завязанные на Opus по умолчанию, — явный профиль/конфиг.

### 8. Две колонки и ASCII-арт (решение проектировщика, 2026-10-03) — ОТЛОЖЕНО до этапа 5 (TUI) по решению проектировщика
«Красивый терминальный вывод: ASCII-арт, две колонки, слева нарратив (~80 символов), справа — рисунки, механика, броски, трофеи.»
Выбор проектировщика: рисунки — заготовки в контенте; узкий терминал — одна колонка; экран — лента (ход печатается ниже предыдущего).
V1. Вывод хода — блок из двух колонок: слева рамка рассказа (80), зазор 2, справа панель ~38 (ширина = ширина терминала − 82,
    не больше 48). Колонки склеиваются построчно; короче — добивается пробелами. Ширина терминала — `shutil.get_terminal_size`,
    пересчитывается на каждом ходу; < 120 → одна колонка (текущий вид U1–U6, без рисунков).
V2. Правая панель сверху вниз, каждый раздел в своей рамке с заголовком: рисунок (если есть), «Броски», «Бой» (лог/инициатива/HP
    врагов), «Получено» (предметы, золото, опыт, трофеи). Пустые разделы не печатаются. Варианты/меню и строка состояния — под
    блоком на всю ширину, как сейчас.
V3. Рисунки — заготовки ASCII в контенте: `ascii` (необязательное многострочное поле, ≤ 36 колонок × ≤ 14 строк, только печатные
    ASCII/псевдографика ширины 1 — валидация при загрузке) у локаций мира, монстров и (опционально) предметов.
    Выбор рисунка на ход: старт боя/бой → монстр (первый живой враг); смена локации или первый ход → локация; иначе без рисунка.
    Нарисовать заготовки для мира «Вейл»: таверна, подвал, Вейл (деревня у реки), гоблин, гоблин-босс (Гракх) — тон «старой книжной
    гравюры», без чужих узнаваемых работ.
V4. Цвет не вводим (только псевдографика); внешние библиотеки — не добавлять (свой рендер на textwrap/str).
V5. Тесты: склейка колонок (каждая строка ровно ширины терминала, при 120/140/200), выбор рисунка, переход в одну колонку при < 120,
    валидация `ascii` (ширина/высота/символы), пустые разделы не печатаются, кириллица и рамки — по ширине без сдвигов.

### 9. Аудит живых правок (кабан-свекровь, 2026-10-03): технические решения оркестратора
- strict в explore — только `STRICT_IN_EXPLORE` (skill_check, saving_throw, damage, advance_time, offer_choices,
  unsupported_action); остальные — `strict: false` + Pydantic (живая ошибка «compiled grammar is too large», c. d4a47f0).
- Рассказ хода — склейка всех принятых текстов хода через пустую строку (c1c0a4c): модель пишет рассказ вместе с инструментом.
- Маркер броска `⚄` (U+2684): ширина 1 в моноширинных шрифтах; 🎲 — две ячейки, ломает ширину 80.
- `cache_write_1h` необязательный: не задан → равен `cache_write` (пользовательские конфиги цен не ломаются).
- Ошибки создания явного кэша Gemini не логируются (нет утечки, нет диагностики) — диагностика в журнал вызовов — бэклог.
Решения проектировщика по аудиту («1а 2а 3б 4 ок»):
1а. Снаряжение Грея — временная замена (короткий лук, кожаный доспех, скимитар, короткий меч); длинный лук, проклёпанная кожа,
    набор путешественника — этап 3 (BACKLOG).
2а. Вступительная сцена нового мира (OPENING в ui/cli.py) — остаётся.
3б. Провоцированная атака героя — только оружием в руке (смена оружия лишь в действии Атака); с дальним в руке — атаки нет
    (безоружного удара в движке нет).
4.  Заголовки меню («Что делаешь?» / «Выбери:» / «Выберите героя:») и effort low у Sonnet — утверждены.
