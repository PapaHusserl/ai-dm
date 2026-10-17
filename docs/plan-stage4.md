# План этапа 4: память (иерархические выжимки, бюджет контекста по модели)

Автор: папа-кабан. Статус: **на аппруве проектировщика**. Основа: TZ.md (2, 2.0, 2.2, 4.0, 11, 12, 13),
`docs/plan-stage4.md` (груминг, аудит, решения Д1, Д2), ARCHITECTURE.md (части A–D, часть E — этот этап),
код после этапа 3 (`master/prompt.py`, `master/memory.py`, `master/relevance.py`, `state/memory.py`, `game/boundary.py`,
`master/world.py`, `llm/*`, `config/app_defaults.toml`).

Критерий этапа (ТЗ 13): **на мок-адаптере 50+ сцен: размер контекста не превышает лимит модели; выжимка главы 1
присутствует в контексте сцены 50; порядок вытеснения соответствует разделу 11.** Плюс живой прогон на паке «Пьяный
Дракон» (часть E).

Решения проектировщика: **Д1** бюджет на ход = `min(80% окна модели, master.context_cap)`, `context_cap = 30000`;
**Д2** сбой summarizer — по ТЗ 4.0: повторы → меню 2.2 (повторить / сменить модель / сохранить и выйти), новая сцена не
стартует. Технические решения архитектора — **[Т-N]**, собраны в части F; продуктовые вопросы — часть G.

Ядро этапов 1–3 не переделывается. Схема сейва меняется → `CURRENT_SCHEMA_VERSION = 5`, миграция `m0005_v4_to_v5`
(одна версия на весь этап, как Т-18 этапа 3), отпечаток `tests/schema/save_v5.schema.json`.

# Часть A. Архитектура этапа

## A1. Слои (новое)
```
ui → game → master → llm
       │       ├──→ protocol (режимы summarize_scene / summarize_chapter — служебные инструменты)
       │       ├──→ master.context   (единый сборщик контекста: бюджет, вытеснение, оценка токенов)
       │       └──→ master.summarizer (роль summarizer: тот же MasterSession-цикл, как master.world)
       └──→ game.boundary (вызов summarizer на границе сцены и главы)
```
Сторож импортов: `master.context` не импортирует `llm` адаптеры (только `llm.types`), `game`, `ui`;
`master.summarizer` не импортирует `game` (как `master.world`). Тесты — в `tests/unit/test_architecture.py`.

## A2. Раскладка промпта нарратора и кэш [Т-1]
```
system[0]  правила протокола (narrator_rules.md)     cache, TTL llm.cache_ttl (1h)   — НЕ МЕНЯЕТСЯ
system[1]  мир: world_id, tone, settings, world/truths, ids  cache, TTL 1h           — НЕ МЕНЯЕТСЯ
system[2]  ПАМЯТЬ (новый): game_summary, выжимки глав,         cache, TTL 5m, stable=False
           выжимки сцен текущей главы (после вытеснения)
messages[0] состояние хода (state_data): герой, сцена, NPC, локации, сырые ходы, ввод   cache 5m (как сейчас)
```
- Байты `system[0]` и `system[1]` не зависят от памяти: тест сравнивает их между сценами 1 и 50.
- `SystemBlock` получает поле `stable: bool = True`. Блок памяти — `stable=False`.
- **Anthropic:** блок памяти — третья точка кэша (`cache_control`, TTL 5m; 1h-точки идут раньше 5m — требование API
  соблюдено). Всего точек: rules, world, memory, message = 4 (лимит API — 4; новых точек больше не добавлять).
  Перезапись — раз на сцену (память меняется на границе) плюс при вытеснении выжимок сцен.
- **Gemini (пересмотрено в P1+, E1):** явный кэш строится из всех блоков `system` (память тоже) + tools; `cache_key`
  включает текст памяти, поэтому кэш пересоздаётся раз на сцену (при смене памяти): ~$0.01 на сцену против
  +$0.012 на каждый ход при памяти вне кэша. `stable` на Gemini не влияет (у Anthropic — TTL 5m для `stable=False`).
  Роль `world` — без явного кэша Gemini (`llm.gemini_cache_world = false` по умолчанию).
- Роль `world` и `summarizer` блок памяти не используют (у `world` своя раскладка, этап 3).

## A3. Память в сейве (`state/memory.py`, `state/scene.py`), схема v5 и `m0005_v4_to_v5`
```python
class SceneSummary:          # + поле
    source: Literal["summarizer", "narrator", "fallback", "pack"] = "pack"
class ChapterSummary:        # + поля
    source: Literal["summarizer", "concat", "pack"] = "pack"
    at_s: int = 0
class Memory:                # + поле
    game_summary_chapter: int = 0   # номер последней главы, свёрнутой в game_summary
class TurnRecord:            # + поле
    scene_id: str = ""              # сцена хода: вход summarizer — ходы закрытой сцены
```
Миграция `m0005`: проставить `source="pack"` существующим выжимкам (Вейл/Дракон из `start/memory.yaml`; выжимки,
записанные этапом 3 из `end_scene.summary`, — тоже `pack`: отличить нельзя, на поведение не влияет);
`game_summary_chapter` = максимальный `number` в `chapters`, если `game_summary` непуст, иначе 0; `TurnRecord.scene_id=""`.
Пак: `start/memory.yaml` валидируется теми же моделями (поля по умолчанию). Конфиг: `master.recent_turns_keep` ≥
`scene.max_turns` (иначе summarizer не увидит начало длинной сцены) — проверка при загрузке конфига.

## A4. Роль `summarizer` (`master/summarizer.py`, `protocol` режимы `summarize_scene`, `summarize_chapter`)
- Устройство как у `master.world`: `SummarizerPromptBuilder` (system[0] — `prompts/summarizer_rules.md`, system[1] —
  мир: tone, имена героя/NPC/локаций для точности; оба cache) + `SummarizerSession` поверх `MasterSession`
  (повторы 2.2, невалидный ответ — до 2 повторов с пояснением, журнал, учёт стоимости).
- Служебные инструменты [Т-2] (не входят в закрытый список 2.1, как `world_verdict`):
  - `scene_summary{title?, summary}` — режим `summarize_scene`, ровно один вызов; `summary` 1–600 символов;
  - `chapter_summary{title, summary}` + `game_summary{summary}` — режим `summarize_chapter`, оба обязательны в одном
    ответе [Т-3]; `summary` главы ≤ 1500, игры ≤ 3000 символов (пределы в конфиге `[memory]`).
- Вход сцены: ходы закрытой сцены (`recent_turns` с `scene_id`), подсказка нарратора `end_scene.summary/title` (если
  была), причина закрытия, дата. Вход главы: выжимки сцен главы, прежний `game_summary`, номер и название главы.
- Выход проверяется: пустая строка / превышение предела → невалидный ответ (повтор с пояснением).
- `title` сцены: приоритет у нарратора (`end_scene.title`), summarizer — если пусто.
- Журнал: `role: summarizer`, `run_id` = id границы (`bnd-…`), как у `world`. Replay — `ReplayAdapter(role="summarizer")`.
- Модель: `roles.summarizer` / профили; при смене провайдера нарратора `/model` summarizer следует за ним, как `world`
  (`game/app.py`, ветка смены world_adapter) [Т-4].

## A5. Граница сцены с summarizer (`game/boundary.py`)
Порядок `finish_boundary` (на копии бандла, атомарно):
```
1. summarize_scene      (обязателен; Д2: сбой → error → меню 2.2, boundary_pending остаётся)
2. tick_days → check_triggers → update_nudge → call_world        (как этап 3)
3. close_chapter: если глава закрывается → summarize_chapter (выжимка главы + свёртка game_summary; сбой → меню 2.2)
4. start_scene, deliver_notices                                   (как этап 3)
```
- `close_boundary` больше не пишет `SceneSummary` из `end_scene.summary` — это делает шаг 1 (подсказка уходит в вход
  summarizer). Ход и сцена уже в автосейве до шага 1 (ТЗ 4.0 п.1).
- Выжимка сцены пишется только в `work` → при сбое любого шага бандл неизменен; повтор (`resume_boundary`) заново
  вызывает summarizer (в журнале — новая запись того же `run_id`).
- «Сменить модель» в меню 2.2 при сбое summarizer меняет `roles.summarizer` на сессию (не нарратора) [Т-5].
- `hero_dead` → граница не идёт (как этап 3), выжимка не делается.
- Без адаптера summarizer (старые тесты этапа 3, `summarizer=None`): запасная выжимка `source="fallback"` (склейка
  `end_scene.summary` или «Сцена N: <локация>, <дата>») — только для тестов/инструментов, в игре адаптер есть всегда.

## A6. Единый сборщик контекста (`master/context.py`) [Т-6]
Заменяет `master/memory.py` (`context_limit`, `trim_turns`) и цикл `estimate` в `PromptBuilder.build`.
```python
class ContextPlan:          # результат: что вошло и что вытеснено
    budget: int; estimate: int
    turns: list[TurnRecord]; scene_summaries: list[SceneSummary]
    npc_ids: list[str]; location_ids: list[str]
    dropped: list[tuple[str, str]]   # (ступень, id) в порядке вытеснения
    overflow: bool                    # не влезло даже после всех ступеней
def budget(app_cfg, model) -> int:   # min(window*80//100, master.context_cap)  (Д1)
def estimate_tokens(text) -> int:    # детерминированно: ceil(len(text) / master.chars_per_token)
def plan(parts, budget) -> ContextPlan
```
- **Оценка токенов детерминированная, локальная** [Т-7]: по длине JSON всего запроса (system + tools + messages),
  `chars_per_token = 2.5` (кириллица; консервативно). `adapter.count_tokens` в бюджете **не используется** (иначе
  live и replay/мок дают разную обрезку → `ReplayDivergence`). Живой `count_tokens` остаётся только для калибровки
  (лог в журнале `meta.context.api_tokens` при живом вызове, опционально).
- **Никогда не вытесняются** (ТЗ 11): system[0], system[1], tools, герой, сцена (локация, время, бой, секреты, divine,
  nudge), `scene_npcs` (в локации героя), спутники (`follows`), NPC с активным триггером, `game_summary`, выжимки глав,
  ввод игрока и `offered_choices`, текущая локация.
- **Ступени вытеснения** (строго по порядку; следующая — только если предыдущей не хватило):
  1. `turns` — сырые ходы, старейший первым, до `master.recent_turns_floor` (по умолчанию 1) [Т-8];
  2. `scenes` — выжимки сцен текущей главы, старейшая первой (выжимки глав остаются);
  3. `npcs` / `locations` — неактивные: сначала NPC, релевантные только по упоминанию, затем ключевые без активного
     триггера, затем связанные с соседними локациями; затем соседние локации, дальние первыми [Т-9];
  4. `overflow` — если всё ещё больше бюджета: запрос уходит как есть, авто-репорт `context_overflow` (ТЗ 9),
     `ContextPlan.overflow=True` [Т-10, см. G1].
- **Глубина сырых ходов** [Т-8]: окно кандидатов = последние `master.recent_turns` ходов (поднять 4 → 8; через границу
  сцены — да, для связности), дальше режет бюджет. С бюджетом 30k и Flash-кэшем 8 ходов ≈ +2–3k токенов на ход.
- **«Связанные с текущей локацией» NPC** (вопрос груминга, не блокирующий) [Т-9]: живые именованные NPC, чья
  `location_id` — соседняя локация из `nearby_locations` (связь `connections` в любую сторону). Добавляется в
  `relevance.relevant_npcs` с причиной; причины возвращаются (`dict[id, set[reason]]`) — по ним ранг вытеснения.
- **Выжимки сцен в памяти**: только сцены текущей главы (`chapter_id == current_chapter.id`); старые главы
  представлены выжимкой главы и `game_summary`.
- **Пересчёт на `/model`**: `budget()` берётся от `builder.model` на каждый `build`; при `/model` runner пересоздаёт
  builder (как сейчас) → новый бюджет со следующего хода. Модель без записи в `context_windows` → ошибка конфига при
  выборе (не молчаливый 0).
- **Журнал**: каждая запись narrator получает `meta.context = {budget, estimate, dropped, overflow}` — по ней тест
  приёмки проверяет порядок вытеснения (ТЗ 13). Replay сравнивает запрос, `meta` — нет.

## A7. Стоимость и кэш (сводка)
| Что | Влияние |
|---|---|
| summarizer сцены (Flash-Lite / Haiku) | ~$0.005 за сцену (груминг); 50 сцен ≈ $0.25 |
| summarizer главы | ~$0.003 за главу |
| блок памяти Anthropic | запись 5m-кэша раз на сцену: ~3–6k ток. × 1.25 × вход; дальше чтение 0.1× |
| блок памяти Gemini | внутри явного кэша; кэш префикса пересоздаётся раз на сцену (~$0.01), не на каждый ход (P1+, E1) |
| потолок 30k (Д1) | ход нарратора не дороже ~30k входа: Flash ≤ $0.0225, Opus ≤ $0.12 (без кэша) |
| глубина ходов 4 → 8 | +2–3k ток. в messages[0] (кэш 5m у Anthropic в раундах инструментов) |
| префикс rules/world | не меняется — кэш 1h не теряется (тест байтов) |

# Часть B. Партии
Каждая партия: TDD (тесты кабана-доебы первыми), `uv run pytest -q`, `uv run ruff check src tests`, ревью мамы-кабана,
синхронизация docs. Отпечаток `save_v5.schema.json` создаётся в P1 (первая партия со схемой) и перегенерируется
сознательно.

## P0. Выжимки в контексте нарратора (без роли summarizer) — запускается сейчас («го»)
**Состав:** A2 (без вытеснения: память целиком), `SystemBlock.stable`, Gemini-кэш по stable-блокам.
**Файлы:** `llm/types.py` (`SystemBlock.stable`); `master/prompt.py` (`memory_block(ctx)` → `system[2]`);
`llm/gemini_adapter.py` (`cache_key`, `create_cache`, `build_config`: только stable; нестабильные → первый Part
user-сообщения); `llm/anthropic_adapter.py` (TTL 5m для `stable=False`); `llm/mock.py`, `llm/replay.py` — без
изменений (запрос пишется целиком); `master/prompts/narrator_rules.md` (абзац: «память — что было раньше; не
пересказывай, используй для связности; противоречие состоянию — верь состоянию»).
**Схема:** без изменений (v4).
**Готово, когда:** выжимка главы I Дракона (`start/memory.yaml`) и `game_summary` видны в `system[2]` первого хода;
выжимки сцен текущей главы — там же; префикс rules/world побайтно прежний.
**Тесты:**
- бандл Дракона → `build` → `system[2].text` содержит `game_summary`, title и summary `ch_1`, `ch_2`; выжимки только
  сцен текущей главы; `system[2].stable is False`, `cache is True`;
- `system[0]`, `system[1]` до/после добавления выжимки сцены — равны байтам; пустая память → блок `system[2]` всё равно
  есть (стабильная структура) с пустыми полями [Т-11];
- Gemini (P1+): `cache_key` меняется при смене памяти; `system_instruction` кэша включает память; без смены памяти
  кэш тот же; Anthropic: 4 `cache_control`, у памяти `ttl: 5m`, у rules/world — `cache_ttl`;
- replay старого журнала этапа 3 — **ожидаемо расходится** (запрос изменился): фикстуры журналов перезаписать
  сознательно, отметить в CHANGELOG/docs;
- golden-сцена этапа 2 на моке зелёная (мок не смотрит system).
**Стоимость/кэш:** + блок памяти (см. A7); префикс без изменений.

## P1. Роль summarizer на границе сцены
**Состав:** A3 (схема v5 + `m0005`), A4 (режим `summarize_scene`), A5 шаги 1–2, Д2.
**Файлы:** `state/memory.py`, `state/scene.py` (`TurnRecord.scene_id`); `persistence/migrations/m0005_v4_to_v5.py`,
`CURRENT_SCHEMA_VERSION=5`; `game/turn.py` (запись `scene_id` в `TurnRecord`; `summarizer_adapter`,
`resume_boundary` передаёт сессию summarizer); `master/summarizer.py` (новый); `master/prompts/summarizer_rules.md`;
`protocol/schema.py` (`MODE_TOOLS["summarize_scene"]`), `protocol/handlers/summary.py` (новый: запись в `ctx`);
`game/boundary.py` (шаг 1, `close_boundary` без записи выжимки); `game/app.py` (адаптер summarizer, `/model`
следование, меню 2.2 «сменить модель» для роли summarizer, replay по роли); `config/app.py` (`[memory]`, проверка
`recent_turns_keep`); `llm/journal.py` (роль `summarizer` в фильтрах); `devtools` (мок-сценарии: шаг `role: summarizer`).
**Готово, когда:** каждая закрытая сцена (5 причин) получает `SceneSummary(source="summarizer")`; сбой summarizer —
меню 2.2 и новая сцена не стартует; replay границы по журналу даёт тот же бандл.
**Тесты:**
- 5 причин закрытия (вкл. `turn_limit`, `time_jump` — без `end_scene.summary`) → вызов summarizer, выжимка в памяти;
- вход summarizer: ровно ходы закрытой сцены (по `scene_id`), подсказка нарратора в запросе, если была;
- порядок шпионом: автосейв → summarizer → tick → world → глава → новая сцена;
- `LlmError` после 3 повторов → `result.error`, `boundary_pending=True`, бандл = автосейв, `memory.scenes` без новой
  записи; «повторить» → выжимка есть; «сохранить и выйти» → загрузка достраивает границу до первого хода;
- невалидно: пустой summary / > 600 → повтор с пояснением, 3-й раз → меню;
- «сменить модель» → следующий вызов summarizer с новой моделью, нарратор прежний;
- `/model` на другой провайдер → summarizer по профилю провайдера (как world);
- журнал: запись `role=summarizer`, `run_id=bnd-…`; `ReplayAdapter(role="summarizer")` + сид → идентичный бандл;
- миграция: фикстура v4 (Дракон, Вейл) → бэкап, `source="pack"`, `game_summary_chapter=2` у Дракона, цепочка v0 → v5,
  отпечаток v5; конфиг `recent_turns_keep < max_turns` → ошибка;
- сторож импортов `master.summarizer`.
**Стоимость:** +1 вызов Flash-Lite на сцену (~$0.005); в `/cost` строка роли `summarizer`.

**Реализовано (P1), уточнения к коду:** `finish_boundary(..., run_id, summarizer)`: шаг 1 `summarize_scene` на копии;
`SummarizerSession` и `WorldSession` одной границы делят `run_id` и счётчик `call_numbers` (иначе совпали бы `call_id`);
`BoundaryResult.summary_run_id` / `failed_role` (по `failed_role == "summarizer"` меню 2.2 «сменить модель» меняет модель
summarizer на сессию: `GameApp.set_summarizer`, `switch_role`); принятая выжимка пишется и в `scene.summary` закрытой сцены
(world видит её); граница, начатая до v5 (выжимка сцены уже в памяти), шаг 1 пропускает; у ходов без `scene_id` (сейв v4)
вход summarizer — последние `scene.player_turns` ходов без `scene_id`. Лимиты длины — `[memory]` в `app_defaults.toml`;
CLI: `--mock-summarizer`, replay по роли `summarizer`.

## P2. Свёртка главы и `game_summary`
**Состав:** A4 (режим `summarize_chapter`), A5 шаг 3.
**Файлы:** `game/boundary.py` (`close_chapter` → summarizer; в игре склейки нет; concat остаётся только при summarizer=None (devtools/тесты) — решение проектировщика 2026-10-04: оставить, симметрично fallback сцены);
`master/summarizer.py` (режим главы); `protocol/schema.py`, `protocol/handlers/summary.py` (`chapter_summary`,
`game_summary`); `master/prompts/summarizer_rules.md` (раздел главы: сохраняй имена, клятвы, долги, открытые нити;
`game_summary` — переписать целиком, не дописывать хвост).
**Готово, когда:** закрытие главы (`end_chapter` и `scene_limit`) даёт `ChapterSummary(source="summarizer")` и новый
`game_summary`, `game_summary_chapter = номер`; сбой — меню 2.2, глава не закрыта, новая сцена не стартует.
**Тесты:**
- `end_chapter` → в одном вызове `chapter_summary` и `game_summary`; ответ только с одним → невалидно, повтор;
- 16-я сцена → `scene_limit` → свёртка; вход = выжимки сцен главы (вкл. только что сделанную на шаге 1) + прежний
  `game_summary`;
- сбой свёртки → бандл неизменен (выжимка сцены шага 1 тоже откатилась — одна транзакция), повтор делает оба вызова;
- длина `game_summary` > предела → невалидно;
- `game_summary` и выжимки глав в `system[2]` следующего хода; выжимки сцен закрытой главы — нет;
- replay границы с закрытием главы (summarizer ×2 + world) → идентично.
**Стоимость:** +1 вызов на главу (~$0.003).

**Реализовано (P2), уточнения к коду:** `close_chapter(work, cfg, registry, summarizer, run_id, result)`: при закрытой главе
`summarizer.run_chapter` (режим `summarize_chapter`, инструменты `chapter_summary` и `game_summary`, вход: выжимки сцен
главы, прежний `game_summary`, номер/название); пишет `ChapterSummary(source="summarizer")`, `game_summary`,
`game_summary_chapter = номер`; название главы — у нарратора (`end_chapter.title`), иначе от summarizer. Оба вызова в одном
ответе: `MasterSession.run` в режиме `summarize_chapter` отклоняет ответ, где принят только один (повтор с пояснением).
Пределы — `[memory] chapter_summary_max / game_summary_max`. Сбой — `failed_role="summarizer"`, меню 2.2, бандл неизменен.
Без summarizer (`summarizer=None`, только тесты/инструменты) остаётся склейка выжимок сцен `source="concat"`,
`game_summary` не меняется.

## P3. Единый сборщик контекста с бюджетом Д1 и вытеснением ТЗ 11
**Уточнённая спецификация (обязательна, заменяет расхождения ниже):** `docs/plan-stage4.md`.
**Состав:** A6 целиком.
**Файлы:** `master/context.py` (новый; `master/memory.py` удаляется, импорты переносятся); `master/prompt.py`
(`build` → `context.plan`, `state_data`/`memory_block` от `ContextPlan`; `count_tokens` из конструктора — только для
калибровки); `master/relevance.py` (причины релевантности, соседние локации); `master/session.py` (`meta.context` в
запись журнала); `game/turn.py` (авто-репорт `context_overflow`); `config/app.py`, `app_defaults.toml`
(`[master] context_cap = 30000`, `chars_per_token = 2.5`, `recent_turns = 8`, `recent_turns_floor = 1`);
`game/commands.py` (`/model` без строки в `context_windows` → отказ с текстом).
**Готово, когда:** оценка запроса ≤ бюджета при любом наполнении памяти (кроме `overflow`); порядок ступеней строго
по ТЗ 11; «никогда не выкидываемое» присутствует всегда; бюджет пересчитывается на `/model`.
**Тесты** (на синтетических бандлах, малое окно через `context_windows` тестовой модели):
- `budget`: окно 1M → 30 000; окно 20 000 → 16 000; `context_cap=0` запрещён конфигом;
- `estimate_tokens` детерминирован, не вызывает адаптер (шпион `count_tokens` — 0 вызовов в бюджете);
- ступень 1: лишнее на 3 хода → удалены 3 старейших хода, выжимки сцен целы; floor=1 — последний ход не удаляется;
- ступень 2: ходов до floor мало → удаляются старейшие выжимки сцен; выжимки глав и `game_summary` на месте;
- ступень 3: дальше → NPC «только упомянут» раньше ключевого; `scene_npcs`, `follows`, активный триггер — остаются;
  соседние локации — дальние первыми, текущая — всегда;
- `dropped` — список в точном порядке ступеней; ступень N+1 не начата, пока у N есть что удалять;
- `overflow`: «никогда не выкидываемое» > бюджета → запрос уходит, `overflow=True`, авто-репорт `context_overflow`;
- `/model` с окна 1M на тестовую модель окна 10 000 → следующий `build` с бюджетом 8 000, вытеснение сработало;
- NPC в соседней локации — релевантен с причиной `nearby`; мёртвый — нет;
- идемпотентность: один бандл → `build` дважды → байты запроса равны (replay-safe);
- `meta.context` в журнале narrator; replay с вытеснением → тот же запрос, без `ReplayDivergence`.
**Стоимость/кэш:** потолок 30k ограничивает вход нарратора; вытеснение выжимок сцен меняет `system[2]` → лишняя
запись 5m-кэша у Anthropic в такой ход (редко: сначала режутся ходы, которые в messages[0]).

## P4. Приёмка этапа
**Состав:** критерий ТЗ 13 + живой прогон.
**Файлы:** `tests/scenarios/test_stage4_memory.py`; генератор мок-сценария (`tests/scenarios/memory_script.py` —
программно строит шаги narrator/summarizer/world: каждая сцена N ходов + `end_scene`, `end_chapter` раз в 12 сцен,
summarizer отвечает детерминированными текстами «Выжимка сцены K», «Глава M», «Игра до главы M»); конфиг теста:
`context_windows.mock = 20000` (бюджет 16 000), `scene.max_per_chapter = 12`.
**Отклонение (решение проектировщика, 2026-10-05):** окно 12 000 из исходного плана невыполнимо — правила + tools
нарратора (explore) ≈12.5k ток. по len/2.5 больше бюджета 9 600 (overflow на каждом ходе); 17 400 давало нулевой запас.
Принято 20 000 с запасом ≥1.5k; при росте правил/tools окно в `tests/scenarios/memory_script.py` подобрать заново.
**Готово, когда:**
- 52 сцены, ≥ 4 главы (12 × 4 + 4), прогон детерминирован по сиду (два прогона → равные бандлы и журналы);
- `meta.context.estimate ≤ budget` на каждом ходе narrator (и `overflow` ни разу); дополнительно контроль: длина
  JSON запроса / 2.5 ≤ бюджет;
- в запросе первого хода сцены 50 (`system[2]`) есть текст «Глава 1» (выжимка ch_1) и `game_summary`;
- порядок вытеснения по журналу: в каждом ходе `dropped` — неубывающая последовательность ступеней
  `turns ≤ scenes ≤ npcs/locations`; хотя бы в одном ходе сработали все три ступени (фикстура с 6+ NPC, 4+ соседними
  локациями и длинными ходами);
- replay всего прогона (3 роли по своим адаптерам) → идентичный бандл;
- сейв в сцене 30 → загрузка → продолжение до 52 → тот же итог, что без перезапуска.
**Живой прогон** — часть E. **Стоимость** прогона на моке — 0; живой — оценка $1–2 (Flash) за 10–15 сцен.

# Часть C. Общие тесты этапа
Все тесты этапов 1–3 зелёные (журнальные фикстуры replay перезаписаны сознательно в P0/P1); сторожа импортов;
отпечаток `save_v5`; `uv run pytest -q` без сети.

# Часть D. Риски
1. **Оценка токенов «по символам»** может занижать реальное число (кириллица, JSON-экранирование): `chars_per_token`
   консервативно 2.5; калибровка живым `count_tokens` в журнале; при систематическом занижении — патч конфига.
2. **Неустранимая часть > 30k** (правила ~5k + tools ~10k? + герой с заклинаниями + бой): проверить в P0 замером на
   Драконе в бою; если близко к потолку — вопрос G1.
   **Замер P0 (Дракон, scene_6, глава II, 6 goblin_warrior в бою, оценка len/2.5):** вне боя неустранимая часть
   ~14.5k ток. (rules 11.0k симв., world 1.2k, tools 17.5k симв./26 шт., состояние 5.2k симв.), память 13.9k симв. (~5.5k ток.),
   всего без сырых ходов ~20k; в бою ~11.7k без памяти (tools 2 шт., состояние с 55 вариантами 13k симв.), ~17.3k с памятью.
   Запас до потолка 30k: вне боя ~10k, в бою ~12.7k. Потолок не под угрозой.
3. **Рост выжимок глав** без вытеснения (ТЗ 11 их не выкидывает): за 30+ глав блок памяти может съесть бюджет — G1.
4. **Качество выжимок дешёвой моделью** (теряются имена/обещания) — правила summarizer со списком «что сохранять»,
   на вход — имена NPC/локаций; проверка в живом прогоне.
5. **Replay-фикстуры** этапов 2–3 ломаются от новой раскладки — перезапись сознательная, отдельным коммитом.
6. **[Устарело после E1, docs/plan-stage4.md: память Gemini внутри явного кэша; Т-1/Т-14 в части Gemini — тоже]** **Gemini: память вне кэша** — платится каждый ход (дёшево на Flash, см. A7); если окажется дорого на Pro-моделях —
   кэш памяти отдельным явным кэшем на сцену (отложено).
7. **Двойной вызов модели на границе с главой** (сцена + глава + world) — дольше граница; приемлемо (дешёвая модель).

# Часть E. Чек-лист живого прогона на паке «Пьяный Дракон»
- [x] Новый мир Дракона, Flash: первый ход ссылается на события глав I–II (выжимки в контексте).
- [x] 10–15 сцен, ≥ 1 закрытие по страховке (`location_changed`/`turn_limit`) — у неё выжимка `source=summarizer`.
- [x] `end_chapter` → «Глава III: …», в памяти выжимка главы и переписанный `game_summary`.
- [x] `/cost`: строка `summarizer`, суммы в пределах A7; доля чтения кэша нарратора не упала против этапа 3.
- [x] `/model narrator anthropic:claude-sonnet-5-5` посреди главы → бюджет пересчитан (`meta.context.budget`),
      summarizer перешёл на Haiku.
- [x] Обрыв сети на summarizer → меню 2.2; «сохранить и выйти» → при запуске граница достроена.
- [x] Replay прогона без сети → тот же бандл.
- [x] Калибровка: `meta.context.estimate` vs `api_tokens` — расхождение в пределах 20% в безопасную сторону.
      Итог (2026-10-05): Gemini 0.76–0.90 ✓; Sonnet 1.09–1.14 — занижение ≤14%, не в безопасную сторону → BACKLOG 15.
      `/cost` прогона: $0.4314 (narrator $0.4176, summarizer $0.0071, world $0.0067).

# Часть F. Технические решения архитектора (этот план)
Т-1 Память — `system[2]` с флагом `stable=False`: Anthropic кэширует её 5m-точкой, Gemini — вне явного кэша (первый
Part сообщения); префикс rules/world не меняется. Т-2 Инструменты summarizer — служебные, вне закрытого списка 2.1.
Т-3 Выжимка главы и свёртка `game_summary` — одним вызовом. Т-4 summarizer следует за провайдером нарратора при
`/model`, как `world`. Т-5 «Сменить модель» в меню 2.2 при сбое summarizer меняет модель summarizer. Т-6 Единый сборщик
`master/context.py` вместо `master/memory.py`. Т-7 Бюджет считается локальной детерминированной оценкой
(`chars_per_token=2.5`), а не `count_tokens` API (replay-безопасность). Т-8 Окно сырых ходов 8 (было 4), через границу
сцены, вытеснение до 1 последнего хода. Т-9 «Связанные с текущей локацией» NPC = в соседних локациях; ранг вытеснения:
упомянутые → ключевые без триггера → соседние; затем соседние локации, дальние первыми. Т-10 Переполнение неустранимой
части — запрос всё равно уходит + авто-репорт `context_overflow`. Т-11 Блок памяти присутствует всегда (даже пустой).
Т-12 Схема v5 одна на этап; `TurnRecord.scene_id` — вход summarizer; `source` у выжимок — для отладки и запасного пути.
Т-13 Выжимки сцен в контексте — только текущей главы. Т-14 Запасная выжимка (`fallback`) — только без адаптера
summarizer (тесты), в игре не используется (Д2).

# Часть G. Продуктовые вопросы (на аппрув)
1. **Переполнение после всех ступеней** (риски 2–3): если «никогда не выкидываемое» + выжимки глав > 30k —
   (а) отправлять как есть + репорт (как предлагаю, Т-10); (б) пятая ступень: выкидывать старейшие выжимки глав,
   уже свёрнутые в `game_summary` (ТЗ 11 этого не разрешает явно); (в) поднять потолок для такого хода до 80% окна.
   Предлагаю (а) сейчас + (б) как следующая ступень, если репорты появятся.

## Решение проектировщика по G1 (2026-10-04: «в»)
Если неустранимая часть (вместе с выжимками глав) не влезает в потолок 30k — для такого хода потолок поднимается до 80% окна
модели; событие пишется в журнал (meta.context) и в авто-репорт для последующей настройки.

## Решения: Груминг этапа 4 — Память (мини-влад, 2026-10-04) (бывш. docs/decisions/stage4-grooming.md)

Вердикт: не готов до ответов на В1–В5; P0 можно сейчас.
Главная находка: нарратор НЕ видит выжимки — state_data не передаёт memory.scenes/chapters/game_summary; выжимка главы I
Дракона лежит в сейве, но в контекст не попадает. Выжимка сцены есть только при end_scene.summary от нарратора; у страховочных
закрытий её нет. Глава = склейка выжимок сцен. Summarizer не вызывается. Бюджет = 80% окна (1M) — вытеснение не сработает.
Вопросы: В1 кто пишет выжимку сцены (рек. summarizer всегда); В2 где выжимки в промпте (рек. system[2], кэш раз на сцену);
В3 бюджет (рек. min(80% окна, потолок в конфиге)); В4 сбой summarizer (рек. не блокировать: запасная выжимка + репорт);
В5 game_summary (рек. свёртка при закрытии главы, не вытесняется). Не блокирует: «NPC, связанные с локацией» — кто это.
Партии: P0 выжимки в контексте; P1 роль summarizer; P2 глава и игра; P3 бюджет и вытеснение; P4 приёмка (50+ сцен, мок).
Стоимость summarizer (Flash-Lite): ~$0.005 за сцену, ~$0.003 за главу.

### Аудит (кабан-свекровь)
Находки подтверждены. В1 (summarizer — ТЗ 2), В2 (раскладка — архитектор, ТЗ 12), В5 (game_summary не вытесняется, ТЗ 11)
сняты как продуктовые. Рекомендация В4 «не блокировать» противоречила ТЗ 4.0 п.2. Дополнить план: NPC/локации в бюджете
(третья ступень вытеснения), глубина сырых ходов до вытеснения, тест /model, малое окно в тесте приёмки.

### Решения проектировщика (2026-10-04: «1б 30k 2а, го»)
Д1. Бюджет контекста на ход = min(80% окна модели, потолок 30 000 токенов) — потолок в конфиге.
Д2. Сбой summarizer — по ТЗ 4.0: повторы → меню 2.2 (повторить / сменить модель / сохранить и выйти); новая сцена не стартует.
«го» — запуск P0 (выжимки в контексте нарратора) и план этапа 4.

## Решения: Этап 4, P3: единый сборщик контекста с бюджетом Д1 и вытеснением ТЗ 11 — уточнённая спецификация (папа-кабан, 2026-10-04) (бывш. docs/decisions/stage4-p3-spec.md)

Источник: STAGE4-PLAN A6, P3, «Решение проектировщика по G1» (заменяет «запрос уходит как есть»). Код сверен на c3411c1.
K — kaban (src/**, docs/**), T — kaban-doeba (tests/**). TDD: T первым, параллельно с K, затем ревью мамы-кабана.

### 1. Расхождения плана с кодом
| # | План | Код сейчас | Решение |
|---|---|---|---|
| 1 | `budget()`, `estimate_tokens`, `plan` в новом `master/context.py` | `master/memory.py`: `context_limit` (80% окна, без потолка), `recent_window`, `trim_turns`; цикл `estimate` в `PromptBuilder.build` | `memory.py` удалить, все три функции заменить `context.py` (`recent_window` переносится как есть) |
| 2 | Оценка детерминированная `ceil(len/2.5)` | `build` зовёт `adapter.count_tokens` на полном запросе (живой API в live, мок/replay — другое число) + эвристика `len//3`; `default_count_tokens` = `len(json)//3+1` | `count_tokens` из `PromptBuilder` убрать совсем (параметр конструктора, `default_count_tokens`, `turn.py:set_adapter`), докстринг `MasterSession` переписать |
| 3 | `meta.context.api_tokens` — калибровка живым `count_tokens` | — | В P3 НЕ делать отдельный вызов: калибровка — по `usage` той же записи журнала (input+cache_read+cache_write — реальные токены запроса). Лишний сетевой вызов на ход не нужен (см. вопрос В3) |
| 4 | `meta.context` в записи журнала | `Journal.record_call` не имеет поля `meta`; replay сравнивает только `request.fingerprint` | `record_call(..., meta=None)` → ключ `"meta": meta or {}`; replay не меняется |
| 5 | Авто-репорт `context_overflow` (ТЗ 9) | Модуля `reports` нет (этап 6). «Авто-репорт» сейчас = `report_tags` в записи журнала + `TurnResult.report_tags` (как `invalid-death`). `MasterResult.report_tags` в `TurnResult` НЕ попадает (в turn.py теги идут только из `executor`) | Тег `context_overflow` пишется в `report_tags` записи журнала narrator и пробрасывается в `TurnResult.report_tags` (см. шаг 6) |
| 6 | `/model` без окна → отказ (`game/commands.py`) | Уже есть: `game/app.py:check_model` отказывает при отсутствии `prices`/`context_windows`; валидатор `AppConfig.check_models_known` — для ролей/профилей | Код не трогать, только тест |
| 7 | `relevant_npcs` → `dict[id, set[reason]]` | `relevant_npcs(bundle) -> list[str]` используют `prompt.py` и `master/world.py` | Новая `npc_reasons(bundle) -> dict[str, set[str]]`; `relevant_npcs` остаётся (обёртка, тот же результат, БЕЗ причины `nearby`) — вход роли world и её replay не меняются |
| 8 | `recent_turns = 8` | `recent_turns = 4`, тест `test_default_config_window_is_4` | Поднять до 8; тест переписать сознательно |
| 9 | Блок памяти строится после вытеснения | `memory_block(ctx)` берёт все выжимки сцен текущей главы, без плана | `memory_block(ctx, plan)` — сцены из `plan.scene_summaries` |
| 10 | Gemini-кэш памяти (P1+ E1) | `GeminiAdapter.cache_key` включает весь `system` (с памятью); новый ключ той же (модель, tools, роль) удаляет старый кэш | Вытеснение выжимки сцены = новый явный кэш Gemini (~$0.01). Принимается (ступень 2 редка); см. риск Р2 |
| 11 | Инструменты качества | — | `make quality`: ruff (E,F,W,I,B,SIM,UP; 100 симв.), покрытие `fail_under = 94`, Qlty smells ≤ 210 (ratchet — не расти), vulture (min_conf 60; allowlist — только с решения пользователя), `make mutate MOD=ai_dm.master.context` |

### 2. Контракты (`src/ai_dm/master/context.py`, новый)
Импорты: только `ai_dm.llm.types`, `ai_dm.state.*`, `ai_dm.master.relevance` (сторож: не `llm`-адаптеры, не `game`, не `ui`).
```python
STAGES = ("turns", "scenes", "npcs", "locations")      # порядок вытеснения

class ContextPlan(BaseModel):                            # frozen
    budget: int            # действующий потолок хода (cap или поднятый по G1)
    cap: int               # min(80% окна, master.context_cap)
    estimate: int          # оценка итогового запроса
    turns: list[TurnRecord]
    scene_summaries: list[SceneSummary]
    npc_ids: list[str]     # known_npcs
    location_ids: list[str]# locations (текущая — всегда первая)
    dropped: list[tuple[str, str]]   # (ступень, id) в порядке вытеснения; id хода = str(turn.turn_seq), сцены = scene_id
    raised: bool           # G1: потолок поднят до 80% окна
    overflow: bool         # = raised (неустранимое > cap); оставлено ради теста P4 «overflow ни разу»
    def meta(self) -> dict  # {"budget","cap","estimate","dropped":[[s,id],...],"raised","overflow"}

def window_budget(app_cfg, model) -> int     # context_windows[model] * 80 // 100
def budget(app_cfg, model) -> int            # min(window_budget, master.context_cap)  (Д1)
def estimate_tokens(text: str, chars_per_token: float) -> int   # ceil(len(text)/cpt), чисто
def request_tokens(req: ChatRequest, cpt) -> int  # estimate_tokens(req.model_dump_json()) — весь запрос
def recent_window(memory, n) -> list[TurnRecord]  # перенос из memory.py
def plan(candidates: Candidates, render: Callable[[Candidates], ChatRequest], *, cap, window80, cpt) -> ContextPlan
```
`Candidates` — что можно урезать (списки в порядке «первым выкидывать — первым»), готовит `PromptBuilder`:
`turns` (окно `recent_turns`), `floor` (`master.recent_turns_floor`), `scenes` (выжимки текущей главы), `npcs` (ранжированные
вытесняемые NPC), `locations` (вытесняемые соседние локации, дальние первыми). Неустранимое `plan` не знает — оно в `render`.
В `Candidates` есть ещё `fixed_npcs`/`fixed_locations` (неустранимое, по умолчанию пустые): `ContextPlan.npc_ids`/`location_ids` = fixed + оставшееся вытесняемое.
Алгоритм: оценивать `request_tokens(render(c))` целиком (не разницей, как сейчас) — дорого, но детерминированно; для скорости
допустимо снимать по одному элементу и пересчитывать (≤ 8+N+M+K рендеров; N,M,K — десятки). Ступени строго по порядку; ступень
N+1 начинается только когда у N кандидатов не осталось (ходы — до `floor`).
**G1:** если после всех ступеней `estimate > cap` → `budget = window80`, `raised = overflow = True`; вытесненное не возвращается
(запрос = неустранимое + floor-ходы). Если и `estimate > window80` — запрос всё равно уходит (см. вопрос В1).
Бюджет считается только на первом `build` хода; раунды инструментов дописывают сообщения без пересчёта (как сейчас).

Ранги NPC (`relevance.npc_reasons`, причины: `with_hero`, `here`, `active`, `key`, `said`, `nearby`):
- неустранимы: `with_hero`, `here`, `active` (и все `scene_npcs` — отдельный список, не трогается);
- вытесняемы, по порядку: только `said` → `key` (без `active`) → `nearby` (только). У NPC с несколькими причинами — самая
  защищённая. Внутри ранга — по id возрастанию. `nearby` = живой именованный NPC, чья `location_id` в `nearby_locations`
  (связь в любую сторону), кроме текущей. Мёртвый/безымянный — не релевантен.
Локации: текущая неустранима; соседние — по `distance_m` убыванию, при равенстве по id.

### 3. План работ K (src/docs)
1. `config/app.py` `MasterConfig`: `context_cap: int = Field(gt=0)`, `chars_per_token: float = Field(gt=0)`,
   `recent_turns_floor: int = Field(ge=0)`; валидатор `recent_turns_floor <= recent_turns`. `app_defaults.toml [master]`:
   `recent_turns = 8`, `context_cap = 30000`, `chars_per_token = 2.5`, `recent_turns_floor = 1`.
2. `master/context.py` — §2. `master/memory.py` удалить.
3. `master/relevance.py`: `npc_reasons(bundle, nearby_ids=())`, `relevant_npcs` = обёртка без `nearby` (вход world неизменен).
   Вынести `nearby_locations` из `PromptBuilder` в `relevance` (нужен и для причин) — чистая функция, `prompt.py` зовёт её.
4. `master/prompt.py`: конструктор без `count_tokens`; `build` → собирает `Candidates`, `render`, зовёт `context.plan`,
   кладёт `self.last_plan`; `state_data(ctx, user_input, plan)` и `memory_block(ctx, plan)` берут ходы/сцены/NPC/локации из
   плана. Байты `system[0..1]` не зависят от плана. Функции держать короткими (Qlty smells ≤ 210).
5. `llm/journal.py`: `record_call(..., meta=None)` → `"meta"`. `master/session.py`: в `call` передавать
   `meta={"context": plan.meta()}` для role narrator (берётся из `builder.last_plan`, у world/summarizer — `None` → `{}`);
   при `plan.overflow` — `report_tags=["context_overflow"]` в записи и `MasterResult.report_tags.append("context_overflow")`
   (один раз за `run`). Докстринг `MasterSession` (count_tokens) обновить.
6. `game/turn.py`: `set_adapter` без `count_tokens`; после каждого `session.run(...)` narrator переносить
   `master.report_tags` в `result.report_tags` (без дублей). Проверить три места вызова (стр. ~308, 355, 383).
7. vulture: после удаления `count_tokens` из builder методы `count_tokens` адаптеров останутся без вызова в src — проверить
   `make dead`; allowlist без решения пользователя не трогать (вопрос В2).
8. Docs: STAGE4-PLAN P3 — ссылка на эту спецификацию; ARCHITECTURE (master.context вместо master.memory); HANDOFF после приёмки.
9. Replay-фикстуры этапов 2–3 (`tests/fixtures/scripts`, golden), если сломаются от `recent_turns=8` / новой оценки —
   перезапись сознательно отдельным коммитом (делает T, K сообщает).

### 4. Тесты T (tests/**)
Новый `tests/unit/master/test_master_context.py`; `test_master_memory.py` удалить/перенести; дополнить `test_master_relevance.py`,
`test_master_prompt.py`, `test_master_session_log.py`, `tests/unit/config/*`, `tests/unit/test_architecture.py`, `tests/unit/game/*`.
- config: дефолты 8/30000/2.5/1; `context_cap=0`, `chars_per_token=0`, `floor<0`, `floor>recent_turns` → ошибка.
- `budget`: окно 1M → 30 000; окно 20 000 → 16 000; cap 10 000 при окне 200k → 10 000.
- `estimate_tokens`: ceil (5 симв./2.5 → 2; 6 → 3; "" → 0); детерминирован; шпион `adapter.count_tokens` — 0 вызовов за ход.
- ступень 1: лишнее на 3 хода → `dropped` = 3 старейших `("turns", seq)`, сцены целы; floor=1 — последний ход остаётся; floor=0 — можно все.
- ступень 2 только после исчерпания ходов до floor; старейшие сцены первыми; главы и `game_summary` в `system[2]` на месте;
  сцены других глав в блок не попадают вовсе (не считаются вытесненными).
- ступень 3: `said` раньше `key`, `key` раньше `nearby`; `with_hero`/`here`/`active` и `scene_npcs` не выкидываются; NPC
  с `key`+`said` идёт как `key`; затем локации: дальние первыми, текущая всегда.
- `dropped` — точный порядок; ступени неубывающие; ни одна ступень N+1 при остатке у N.
- итог: `estimate ≤ budget` при любом наполнении (параметризовать размеры) и `estimate == request_tokens(итоговый req)`.
- G1: неустранимое > cap → `raised=overflow=True`, `budget == window80`, все вытесняемые выкинуты, запрос отправлен;
  запись журнала: `meta.context.raised`, `report_tags == ["context_overflow"]`; `TurnResult.report_tags` содержит тег ровно раз
  даже при нескольких раундах инструментов; без переполнения — тега нет, `meta.context.raised=False`.
- relevance: NPC в соседней локации (связь в любую сторону) → `nearby`; мёртвый — нет; `relevant_npcs` (вход world) не изменился.
- `/model` с 1M на тестовую модель окна 10 000 → следующий `build` с бюджетом 8 000, вытеснение есть; модель без окна → отказ `check_model`.
- идемпотентность: один бандл → `build` дважды → равные байты; `system[0]`, `system[1]` равны при разной памяти/вытеснении.
- `meta.context` только у narrator; replay прогона с вытеснением → тот же запрос, без `ReplayDivergence`.
- сторож: `master.context` не импортирует `ai_dm.llm.*_adapter`, `game`, `ui`; `master.memory` отсутствует.
- мутации: `make mutate MOD=ai_dm.master.context` (и `ai_dm.master.relevance`) — выживших добить или обосновать.

### 5. Риски
Р1. Оценка `len(JSON)/2.5` по `model_dump_json` экранирует кириллицу? Pydantic пишет UTF-8 без `\u` — проверить тестом; при
    `\uXXXX` оценка завышена в ~6 раз и вытеснение будет агрессивным.
Р2. Вытеснение выжимки сцены меняет `system[2]` → новый явный кэш Gemini и запись 5m у Anthropic. Если ступень 2 «мигает»
    между ходами (ход вырос/сократился) — кэш пересоздаётся каждый ход. Ограничение: ступень 2 срабатывает только после ходов
    до floor; на потолке 30k по замеру P0 (≈20k без ходов) — практически не сработает в Драконе.
Р3. Пересчёт рендером целиком — O(кандидатов) сериализаций запроса (~50–100 × ~80 КБ) на ход; приемлемо (<100 мс), иначе — разница.
Р4. `recent_turns` 4 → 8: +2–3k токенов входа на ход (A7) и перезапись replay-фикстур.
Р5. Qlty smells ratchet (≤ 210): `build`/`state_data` уже длинные — новый код дробить на функции, иначе `make smells` красный.
Р6. Покрытие 94% глобально: удаление `memory.py` и его тестов не должно опустить порог — тесты context.py обязательны до слияния.

### 6. Открытые вопросы (только проектировщик)
В1. G1, крайний случай: неустранимое > 80% окна (реально только у малых окон, напр. Haiku 200k → 160k — маловероятно). Отправлять
    как есть с тем же тегом (рек.) или ошибка хода → меню 2.2?
В2. После P3 `count_tokens` адаптеров в src никем не вызывается (vulture может пометить). Оставить в интерфейсе адаптера под
    будущую калибровку (внести в vulture_allowlist — нужно ваше «да») или удалить из адаптеров и протокола (рек.: удалить; калибровка — по usage журнала)?
В3. Калибровка `meta.context.api_tokens` (чек-лист E): брать из `usage` ответа (рек., бесплатно) вместо живого `count_tokens`
    (+1 сетевой вызов на ход)?
В4. При поднятом потолке (G1) вытесняемое всё равно выкидывается (рек.: запрос = неустранимое + floor-ходы, растёт только
    неизбежное) — или наоборот заполнять до 80% окна (дороже, но больше контекста)?

### Решения проектировщика по вопросам В1–В4 (2026-10-04)
- В1: неустранимая часть > 80% окна → запрос уходит как есть, тег `context_overflow`, `overflow=True`.
- В2: `count_tokens` удалить из адаптеров и интерфейса (vulture_allowlist не трогать).
- В3: калибровка — из `usage` ответа (без живого `count_tokens`), в `meta.context`.
- В4: при поднятом потолке вытесненное не возвращается.

## Правки по ревью: Этап 4: правки ревью P1 + экономия (партия «P1+», до P2) (бывш. docs/decisions/stage4-p1-review-and-cost.md)

Решения — оркестратор (технические). K — src/**, docs/**; T — tests/**. Параллельно кабан и кабан-доеба, затем ревью мамы-кабана.

### Ревью P1 (мама-кабан, P1 закоммичена d897366)
R1. Вход summarizer (master/summarizer.py state_data): не все NPC/локации мира, а известные герою — NPC с непустым
    known_to_player или упомянутые в ходах сцены / scene_npcs (по образцу relevant_npcs), локации visited=True + локация сцены.
    Цель: не тянуть в выжимку неизвестное игроку и не тратить токены (сейчас 31 NPC и 34 локации Дракона на каждую границу).
R2. config/app.py валидатор: recent_turns_keep >= max_player_turns + 1 (сцена закрывается при player_turns > max).
R3. Комментарии в ui/cli.py (make_summarizer_adapter) и game/turn.py: при None — запасная выжимка без модели, а не адаптер рассказчика.
Мелочи: fallback_summary без split по «_»; scene.title = title закрытой сцены; Literal source "narrator" — убрать или задокументировать;
ключ кэша tool_defs по группе режимов; чистка call_numbers в take_boundary.

### Экономия (кабан-тесть, 2026-10-04; решения проектировщика: «1а» — длину/мышление рассказчика не трогать)
E1. Gemini: блок памяти (system[2]) — внутри явного кэша, кэш пересоздаётся раз на сцену (при смене памяти), вместо «вне кэша каждый
    вызов» (Т-1 плана P0 пересмотрен: ~$0.01 на сцену против +$0.012 на каждый ход). Anthropic — без изменений (уже 5m точка).
E2. Проверить по журналу живых миров (saves/drunk_dragon-29a049dc, только читать), что правила и tools действительно попадают в
    кэшированный префикс Gemini (cache_read ≈ 6.5k/вызов меньше правил ~5k + tools ~7k по оценке). Если нет — исправить; отчёт с цифрами.
E3. Роль world: без явного кэша Gemini (редкие вызовы, хранение Flash-Lite дорогое) — конфигом, по умолчанию выключено для world.
    Реализация: при создании кэша, заменяющего прежний с тем же (модель, sha256 tools, роль) и другим ключом, старый
    удаляется через caches.delete(name=...) (best-effort: ошибка логируется и игнорируется) и убирается из self.caches.
    Кэши других ролей и наборов tools не трогаются. Пересоздание после 403/404 (тот же ключ) ничего не удаляет.
T. Тесты: R1 (неизвестные NPC/непосещённые локации не во входе), R2, E1 (память в кэше; смена памяти → новый кэш; без смены — тот же),
   E3 (world без caches.create), мелочи.

### E2: результат (журнал saves/drunk_dragon-29a049dc, только чтение; 95 вызовов, 2026-10-04)
Журнал записан до P0: system = 2 блока (rules 9649 симв., world 2339 симв.), памяти нет.
- Нарратор, `explore` (25 tools, 18 030 симв. JSON): `cache_write` = `cache_read` = 8618 ток.; `input` первого вызова 1845 ток.
  Сообщения этого вызова — 5868 симв. (≈3,2 симв./ток.) — то есть `input` = только messages, rules и tools в него не входят.
- `combat_narrate` (4 tools, 2703 симв.): `cache_read` 4422; `combat_classify` (2 tools, 1987 симв.): 4203.
- Решение системы по трём режимам (8618 / 4422 / 4203 при одних rules+world 11 988 симв.): rules+world ≈ 3 680 ток.
  (rules ≈ 2 960, world ≈ 720 -- пропорция по символам, не замер), tools explore ≈ 4 940 ток. (≈3,65 симв./ток.). Оценка «правила ~5k + tools ~7k» завышена:
  фактически rules ≈ 3,0k, tools ≈ 4,9k, весь кэш explore = 8,6k.
- Все вызовы нарратора (включая каждый раунд инструментов) читают из кэша 4,2–8,6k ток.; world — 4788 ток. (rules 2515 +
  world 4008 симв. + 12 tools 9471 симв.). Итог по журналу: input 442 503 ток., cache_read 597 210 ток. (57% входа из кэша).
- Создано 4 кэша (22 031 ток. записи, 1 321 860 ток.-мин хранения): explore, world, combat_narrate, combat_classify.
  Каждая смена режима (набор tools) = новый кэш (ключ включает tools); мелкие кэши боя ≈ 4,2–4,4k ток. дают
  небольшую выгоду, но допустимы.
- Вывод: правила и tools в кэшированном префиксе Gemini — исправлять нечего. Расхождение с оценкой — только размер.
  Для P0+E1: память (system[2]) теперь тоже внутри кэша; без смены памяти кэш прежний.

## Итог: Этап 4: аудит кабана-свекрови и решения проектировщика (2026-10-05) (бывш. docs/decisions/stage4-audit.md)

Аудит `stage-3..fb5e2b5`: убирать нечего. Подтверждено проектировщиком постфактум:
1. Инструменты качества кабана-кволити (Qlty, покрытие ≥94, smells ≤210, vulture, mutmut, dev-зависимости, 1a6b45b) — оставляем.
2. Исходный vulture_allowlist.py (41 имя) — да.
3. M5: фраза в narrator_rules.md (нет хода других — ход героя продолжается) и уточнения (Extra Attack, отклонённая
   импровизация) — да.
4. P1+: R1 (summarizer видит только известное герою), E1 (память Gemini в явном кэше), E3 (у world кэша нет) — да.
5. Живой прогон Дракона (часть E) — проведён проектировщиком; цифры калибровки и /cost — в STAGE4-PLAN, хвосты — BACKLOG 15.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- Этап 4 (Память): план docs/plan-stage4.md; груминг/аудит/решения docs/plan-stage4.md
  (Д1 бюджет = min(80% окна, 30 000 ток.); Д2 сбой summarizer → меню 2.2; G1 — переполнение неустранимой части → потолок 80% окна).
- P0 ✅ (a394fca, c414de1): выжимки в контексте нарратора (system[2] «память»).
- P1 ✅ (d897366): summarizer на границе сцены, схема v5.
- P1+ ✅: правки ревью P1 + экономия E1–E3 (docs/plan-stage4.md, там же отчёт E2).
- P2 ✅ (7de2bd5): свёртка главы summarizer'ом; concat при summarizer=None оставлен (решение); лишний вызов — BACKLOG 12.
- P3 ✅ (9e35c70): сборщик контекста master/context.py, вытеснение, G1; спецификация и решения В1–В4 —
  docs/plan-stage4.md. Мутации context/relevance — 0 выживших.
- P4 мок ✅ (da7ce9c): tests/scenarios/test_stage4_memory.py + memory_script.py; окно мока 20 000 (решение, см. план P4).
- Живой прогон (часть E) ✅, фикс боя M5 ✅ (fb5e2b5), аудит свекрови ✅ (docs/plan-stage4.md). Тег stage-4.
- Хвосты этапа 4 — BACKLOG 15.
