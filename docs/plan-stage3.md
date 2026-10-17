# План этапа 3: паки кампаний, ход мира, сцены и главы, боги, бюджет боя

Автор: папа-кабан. Статус: **на аппруве проектировщика**. Основа: TZ.md (2.0, 2.1, 2.3, 3, 4 целиком, 4.2, 5.3, 11, 13),
`docs/plan-stage3.md` (решения 1в 2б 3а 4а 5а 6а 7), ARCHITECTURE.md (части A–C, часть D — этот этап), BACKLOG.md,
код после этапа 2 (тег `stage-2`), импорт `saves/drunk_dragon/`.

Критерий этапа (ТЗ 13): **триггер NPC по флагу срабатывает на границе сцены; ход мира на 30 дней с мок-моделью `world`
по сиду даёт идентичный результат.** Плюс ручная живая сцена на паке «Пьяный Дракон» (часть E).

Ядро этапов 1–2 не переделывается — добавления. Формат сейва меняется → `CURRENT_SCHEMA_VERSION = 3`, миграция `m0003`,
отпечаток `tests/schema/save_v3.schema.json`. Решения, принятые мной (технические), помечены **[Т-N]** и собраны в части F;
продуктовые вопросы — часть G.

# Часть A. Архитектура этапа

## A1. Слои (новое)
```
ui → game → master → llm
       │       └──→ protocol → [движок]
       ├──→ world_sim → [движок]          (структурный ход мира: без llm/master/protocol)
       ├──→ campaign  → [движок]          (пак: чтение, проверка, сборка мира, догрузка)
       ├──→ master.world (роль world)     (через protocol, как narrator)
       └──→ protocol, persistence, combat
```
Сторож импортов: `world_sim` и `campaign` не импортируют `llm`, `master`, `protocol`, `game`, `ui` (как движок);
`master.world` не импортирует `game`. Новые тесты — в `tests/unit/test_architecture.py`.

## A2. Пак кампании (`campaign`)
Раскладка (ТЗ 3; имена файлов — решение архитектора, ТЗ 12):
```
campaigns/<campaign_id>/
  campaign.yaml      id, name, version, calendar, start, mortality, natural_events, nudge, tone, flags   [обяз.]
  world.md           мир, атмосфера → system[1] нарратора и world                                         [обяз.]
  truths.md          неизменные факты                                                                     [опц.]
  npcs.yaml  factions.yaml  pantheon.yaml  locations.yaml  events.yaml                                    [опц., список]
  heroes/<id>.yaml   готовые герои (пресеты) — CharacterChoices + стартовое состояние                      [≥1]
  start/             стартовое состояние «середины игры» (решение 1в): memory.yaml, chronicle.yaml        [опц.]
  content/           слой контента пака (weapons/ armor/ items/ monsters/ …) — третий слой A5            [опц.]
```
`character.yaml` из ТЗ = частный случай `heroes/` с одним файлом **[Т-1]** (Вейл несёт трёх пресетов arn/liel/grey).

**Модели** (`campaign/models.py`, `extra="forbid"`): сущности пака — **те же модели сейва** (`NPC`, `Faction`, `God`,
`Location`, `GlobalEvent`, `Trigger`, `Secret`) — ТЗ 4: «в том же формате»; в YAML — списки, в мире — dict по id **[Т-2]**.
Свои модели только у метаданных:
- `CampaignManifest {id, name, version, calendar: Calendar | None, start: StartSpec, mortality: MortalitySpec,
  natural_events: NaturalEventsSpec, nudge: NudgeSpec, tone: Tone, flags: dict}`;
- `StartSpec {date: "YYYY-MM-DD", time: "HH:MM" = "08:00", hero_location: str, heroes: list[str] (пресеты),
  chapter: {number, title} = {1, ""}, scene_summary: str = ""}` — `scene_summary` = выжимка стартовой сцены (2б);
- `MortalitySpec {preset: calm|peaceful|normal|harsh|brutal = normal, per_day: int | None}` — `per_day` = N в «1/N»;
  пресеты 500000 / 50000 / 20000 / 5000 / 500 в `defaults.toml [world.mortality_presets]` (ТЗ 4.1.1);
- `NaturalEventsSpec {chance_percent_per_season: int = 5, kinds: list[NaturalEventKind{type, mortality_multiplier,
  hazard?, duration: "30d", regions: list[str]}]}` — «по умолчанию редко» = 5% **[Т-3]**;
- `NudgeSpec {scenes: int = 8}` (ТЗ 4: N = 8, в настройках);
- `HeroPreset {id, choices: CharacterChoices, inventory_extra, equipped, money_cp, location_id, level, xp, favor,
  deity_id, birth_date}` — сборка штатным `build_character` + наложение состояния;
- `StartMemory {game_summary, chapters: [ChapterSummary], scenes: [SceneSummary]}`, `StartChronicle {entries}`.

**Календарь пака** (`core/clock.py`): `Calendar` + `holidays: [Holiday{month, day, name, god_id?}]`,
`seasons: [Season{name, months: [номера]}]` (по умолчанию 4 сезона по 3 месяца, Заревень = зима… — для 12 × 30),
`epoch_note: str`. Нет календаря в паке → `default_calendar()`. Проверки: праздник в существующем дне, каждый месяц в
ровно одном сезоне, `god_id` праздника есть в пантеоне. `GameClock.season()` и `holiday()` — чистые функции.

**Загрузчик** (`campaign/loader.py`): `load_pack(path, registry) -> Pack | PackError(lines)`. Ошибки — построчно с путём
файла и полем (как `content.loader.read_file`). Порядок: YAML → модели → проверка ссылок (`validate_refs` триггеров и
секретов; `location.parent_id/connections`; `npc.location_id/species_id`; `faction.members/regions`; `god.rivals`;
`event.regions` = id локаций **[Т-4]**; `event.cause`) → уникальность. Слой `content/` пака подключается к
`load_registry([..., pack/content])` — конфликты id со SRD/`content/` — ошибка списком (A5, уже есть).

**Уникальность** (`rules/uniqueness.py` расширяется): `check_faction`, `check_god`, `check_hero` (+ имеющиеся
`check_npc`, `check_location`). `campaign/uniqueness.py: collect_conflicts(world, heroes, pack) -> (accepted, conflicts)`:
сущности добавляются по одной в порядке файлов (локации → боги → фракции → NPC; внутри — порядок файла), конфликтная
**не загружается** и попадает в список `Conflict{file, kind, id, name, reason}`; сущности, ссылающиеся на
отброшенную, тоже отбрасываются со строкой «ссылается на отброшенную X» (транзитивно) **[Т-5]**. Новый мир: список
конфликтов печатается, мир стартует без них (ТЗ 5.3) — если отброшена стартовая локация или герой-пресет, старт
отказывается с кодом 1.

**Догрузка в идущий мир** (`campaign/merge.py: merge_new(bundle, pack) -> MergeReport`): при каждой загрузке мира с
`campaign_id` (если каталог пака есть; нет — предупреждение, игра продолжается). Новые = id нет в `world.npcs|factions|
pantheon|locations|events`; существующие не меняются (мир живёт своей версией). Новые проходят ту же уникальность
против текущего мира (включая сущности `origin: ai`) — конфликт → список игроку. Добавленные — запись в хронику
(`kind: pack_update`), `world.campaign_version` = версия пака. Ссылки новых триггеров на уже существующие id мира
допустимы. Идемпотентно (вторая загрузка — пустой отчёт). Текст `world.md`/`truths.md` копируется в сейв при создании
мира и **не** обновляется догрузкой **[Т-6]**.

**Вейл → пак** `campaigns/vale/`: всё из `game/starter.py` (WORLD_TEXT, локации, Гарт, Гракх, tone, три пресета
героев) переносится данными; `starter.py` становится `new_world_from_pack(pack, hero_preset, seed, …)`;
`fighter_choices`/`wizard_choices`/`ranger_choices` остаются только в тестах как фабрики (или читаются из пака).
CLI: `--campaign <id>` (по умолчанию `vale`), `--hero` — из пресетов пака (без захардкоженного `choices`).

**Предметы Грея (BACKLOG 7)**: в `srd/data` — `longbow`, `studded_leather`, `explorers_pack`, `druidic_focus` (данные
SRD 5.2, `source: srd`); пресет `grey` в Вейле получает стандартный набор следопыта; безоружный удар — трек 1.5.

## A3. Схема сейва v3 (`state/*`) и миграция `m0003_v2_to_v3`
Все новые поля с нейтральными значениями по умолчанию (пустые секции не `None`, A2 этапа 1).

| Модель | Изменение |
|---|---|
| `SessionState.current_chapter` | `dict | None` → `ChapterState | None {id: "ch_<n>", number, title, started_at_s, scene_count, closed_reason: end_chapter|scene_limit|None}` |
| `SessionState` | `+ boundary_pending: bool = False` (граница сцены не завершена — достроить при загрузке, A5) |
| `SceneState` | `+ summary: str = ""`, `+ title: str = ""`, `+ favor_spent: dict[god, int]`, `+ touched_main: bool`, `+ hero_initiated_combat: bool` |
| `WorldState` | `+ lore: Lore{world_text, truths}`, `+ sim: WorldSim{last_day: int, last_season: str, last_year: int, nudge: NudgeState{scenes_off_main, stage 0..3, waiting: bool}, world_calls_today: int}`, `+ mortality_per_day: int = 20000`, `+ natural: NaturalEventsSpec`, `+ nudge_scenes: int = 8`, `+ dangers: list[DangerMark{location_id, text, at_s}]`, `+ notices: list[Notice{id, at_s, deliver_at_s, visibility: visible|rumor|hidden, text, refs}]`, `+ fired: list[FiredTrigger{ref, at_s}]` |
| `Tone` | шкалы ТЗ 3 типизируются: `violence: ""|мягко|реалистично|жестоко`, `horror: ""|нет|умеренно|сильно`, `romance: ""|нет|намёки|есть`, `language: ""|сдержанно|грубо`; `mood: str` (расширяемо); `+ notes: str` (свободный текст стиля). `""` = не задано |
| `NPC` | `+ groups: list[str]` (для `affects` событий), `+ aging_steps: int = 0`; `birth_s` используется |
| `HeroState` | `+ deity_id: str | None`, `+ divine: DivineState{frozen: list[god], debts: list[str], intervention_chapter: str | None, prayer_day: int | None, curse_day_used: int | None}`, `+ birth_s: int | None` |
| `God` | `+ servants: list[str]` (id NPC), `+ check_every_days: int = 7` (ТЗ 4.2 «проверяются реже») |
| `Trigger` | `+ kills_hero: bool = False` (2.3: «триггер NPC с целью убить героя»); «основная линия» не хранится — вычисляется из `key` владельца и триггера **[Т-7]** |
| `Secret` | `+ narrative_ok: bool = False` (нарративная часть подтверждена `world`, A4) |
| `GlobalEvent` | `regions` — id локаций; `+ kind: natural|caused = caused`; `cause` для war/plague — `trigger:<owner>:<id>` |
| `Memory.scenes/chapters` | `list[dict]` → `list[SceneSummary{id, chapter_id, title, summary, at_s}]` / `list[ChapterSummary{id, number, title, summary}]` |
| `Chronicle.entries` | `list[dict]` → `list[ChronicleEntry{at_s, kind, text, refs: list[str]}]`, `kind`: death, event, trigger, tone, pack_update, favor, imported |
| `Calendar` | `+ holidays`, `+ seasons` (A2) |

`m0003_v2_to_v3` (сырой dict, литералы заморожены): `current_chapter` dict → `ChapterState` если форма совпала, иначе
`None` (игра откроет главу 1 при загрузке); `boundary_pending=False`; все `+` поля — по умолчанию; `Tone`: значение шкалы
вне списка → `""`, исходный текст всех шкал → `notes` («violence: …; language: …»), `language: "русский"` → `""`
(решение 3а: настоящие значения Дракона ставит пак); `memory.scenes/chapters`: элементы с `summary` → типизированные
(`id` = `sc_<i>`/`ch_<i>` если нет), остальные выкидываются; `chronicle.entries`: `{at_s|day, text}` → `ChronicleEntry
(kind="imported")`, `day` → `at_s=(day-1)*86400`; `lore` = `world_text` из `settings` если был, иначе пусто;
`events.regions` с неизвестными id не трогаются (миграция не знает пака). Тест-фикстура: `tests/fixtures/saves/v2/`
(сейв Вейла этапа 2 из `saves/vale-*`, обезличенный) → v3 → валидация → повторный save побайтно стабилен.
Импорт Дракона (`manual-import`, v1 с невалидным `pending_decision`) **через миграции не грузится** — его заменяет пак
(П7); `load_slot` на нём даёт понятную ошибку, а не молчаливое обнуление **[Т-8]**.

## A4. Роль `world` (`master/world.py`, `protocol` режим `world`)
**Когда:** один пакетный вызов на границе сцены (ТЗ 2.0), только если есть кандидаты; иначе без вызова. Потолок вызовов
в день — `world.max_calls_per_day` (0 = выключено, по умолчанию 0; лимиты 2.0 мягкие); при потолке — нарративные
условия откладываются до следующей границы, структурные `then` всё равно идут **[Т-9]**.

**Кандидаты** (`world_sim/candidates.py`, чистая функция, сортировка: вид владельца (god, faction, npc), id, id триггера):
1. `verdict` — триггеры с `is_ready` и `evaluate == NEEDS_NARRATIVE` (структурная часть выполнена, остаток — `residual`);
   боги — только если прошло `god.check_every_days` с прошлой проверки;
2. `verdict` — секреты NPC текущей (закрытой) сцены с `NEEDS_NARRATIVE` и `narrative_ok=False`;
3. `act` — триггеры, сработавшие структурно на этой границе (`TRUE`) — их `then` надо превратить в запросы;
4. `act` — ступень подталкивания 3 «событие находит героя» и «мир перестал ждать» (A6);
5. `act` — изменение благосклонности NPC (ТЗ 4.2) — только в составе `act` по сработавшему триггеру/событию.

**Вход вызова** (`messages[0]`, JSON, сорт. ключей): время/дата/сезон, выжимка закрытой сцены, герой (локация,
известность), список кандидатов `{ref, kind, owner{id, name, motive, means}, condition_text, then}`, релевантные NPC
и локации (A7), активные события, `dangers`. `system[0]` — `master/prompts/world_rules.md` (кэш), `system[1]` — lore,
пантеон, tone (кэш).

**Инструменты** (`tool_set("world")`, ≤ 16 strict):
`world_verdict{items: [{ref, holds: bool, reason}]}` (обязателен, если есть `verdict`-кандидаты; лишние/пропущенные ref →
invalid), `world_notice{text, visibility: visible|rumor|hidden, delay: none|day|week, refs}` (заметное герою — в
закадровый блок или слух), и обычные запросы 2.1 из закрытого списка: `set_flag, npc_update, favor_change,
event_start, event_end, npc_create, location_create, skill_check, saving_throw, warn_danger`. В режиме `world`:
- `npc_update` получает `location_id` (перемещение NPC за кадром) **[Т-10]** и `then_ref` (какой кандидат исполняет —
  обязателен: действия без ссылки на кандидат → invalid);
- `skill_check`/`saving_throw` получают `actor` (id NPC; по умолчанию герой) — закадровое противостояние «тем же броском
  движка» (ТЗ 4.1 п.2); `npc_update(status=dead|gone, cause=goal|hazard)` требует `evidence_ref` броска этого вызова,
  как у нарратора;
- `favor_change` разрешён для NPC (`target` = id NPC), лимиты 4.2;
- `then` в `npc_update` и `world_notice` не может затрагивать героя напрямую (урон, предметы, деньги — нет в наборе).
Бюджеты: те же (невалидные ≤ 2, раунды ≤ 8). Неудача → 2.2: повтор/смена модели/сохранить и выйти;
`boundary_pending` остаётся `True`.

**Применение:** `verdict holds=true` → `fire(trigger)` + `world.fired` + хроника (`kind: trigger`); `secret` → `narrative_ok`;
`holds=false` → ничего (будет спрошен на следующей границе, если условие всё ещё открыто). `world_notice` →
`world.notices` (`deliver_at_s` = now + delay). Результат вызова попадает в `TurnResult.offscreen`.

**Журнал и replay:** вызовы `world` пишутся в тот же `journal/calls-NNN.jsonl` с `role: "world"` и `run_id` границы
(`bnd-<stamp>-<n>`). `ReplayAdapter` разбивается по ролям: `ReplayAdapter(records, role=...)` берёт только записи своей
роли (порядок внутри роли сохраняется), `--replay` создаёт по адаптеру на роль **[Т-11]**. Расхождение → `ReplayDivergence`.
Мок: `ScriptedAdapter` для роли world — `tests/fixtures/scripts/world_*.yaml`.

**Стоимость:** `CostLedger` уже ведёт роль; `/cost` покажет world отдельно.

## A5. Сцены, главы и граница (`game/scene.py`, `game/boundary.py`)
Страховки закрытия сцены (есть): смена локации, скачок > 1 ч, конец боя, > 30 ходов; `end_scene`. Новое:
- `SceneState.summary` = `end_scene.summary` (если дал нарратор) → `memory.scenes` (`SceneSummary`); полные выжимки —
  этап 4 (BACKLOG 4);
- **Глава:** `ChapterState` открывается при старте мира (из `StartSpec.chapter`) и после закрытия предыдущей;
  `end_chapter{title}` закрывает главу на ближайшей границе; страховка — `scene.max_per_chapter = 15` сцен
  (`defaults.toml [scene]`); при закрытии — `ChapterSummary` (title, summary = склейка `summary` сцен главы; свёртка
  моделью — этап 4); `+ intervention_chapter` сбрасывает лимит вмешательства бога;
- `ensure_min_advance` вызывается в `close_scene` (уже есть) — тест на +600 с.

**Порядок на границе** (`boundary.run(bundle, …) -> BoundaryResult`), ТЗ 4.0:
1. `close_scene(reason)` + `ensure_min_advance`; `memory.scenes` += выжимка; `boundary_pending = True`;
2. **автосейв закрытой сцены** (как сейчас);
3. на копии бандла (атомарно, как ход): `world_sim.tick_days` (A6) → структурные триггеры (`world_sim.triggers.check`)
   → подталкивание (счётчик, ступень; кандидат ступени 3 идёт в вызов) → вызов `world` (A4) → применение → закрытие главы (если `end_chapter` или 15 сцен)
   → `boundary_pending = False` → `start_scene` → доставка `notices` с `deliver_at_s <= now` и `visibility != hidden`;
4. commit копии; при сбое `world` — откат копии, меню 2.2, автосейв из п.2 уже с `boundary_pending=True`: следующий
   запуск/«повторить» достраивает границу до первого хода.
Закадровый блок выводится, **только если** есть доставленные заметки (ТЗ 4.0 п.3). Смерть героя: граница не идёт
(временное правило этапа 2 сохраняется).

## A6. Структурный ход мира (`world_sim`)
- `world_sim/tick.py: tick_days(bundle, rng, cfg, registry) -> list[DomainEvent]` — шаг = игровой день (ТЗ 4.1): для каждого
  полного дня от `sim.last_day + 1` до текущего: (1) смертность, (2) истечение событий (`ends_at_s`) и `ends_when`
  (структурная часть — `evaluate`; нарративная — кандидат `world`), (3) смена сезона → бросок природного события,
  (4) смена года → старость. Порядок существ — по id. Скачок > 365 дней — по годам (этап 9); на этапе 3 — потолок
  `world.max_tick_days = 400`: при скачке больше прокручиваются подробно только последние `max_tick_days` дней, остальные
  пропускаются записью в хронике («Мир прожит без подробностей: N дн.»), ошибки нет; годовой бросок за пропущенное — этап 9
  (BACKLOG) **[Т-12]**.
- `world_sim/mortality.py`: каждый `alive` именованный NPC и герой (не `in_afterlife`): `rng.randbelow(per_day_eff) == 0`,
  `per_day_eff = per_day // max(1, multiplier)`, где `multiplier` — максимум `mortality_multiplier` активных событий, в
  регионе которых его локация (по цепочке `parent_id`) и в `affects` которых его `groups` (`[]`/`все` = все).
  Выпало → «отвести беду» (4.2): самый благосклонный бог существа, `d10 <= favor` (favor × 10%) → спасён (хроника);
  иначе `remove_creature(cause=chance)`. Безымянные — не отслеживаются.
- `world_sim/aging.py`: таблица `srd/data/tables/lifespan.yaml` (`species_id → threshold, limit` лет: human 60/90,
  halfling 100/150, dwarf 250/350, elf 500/750); возраст из `birth_s`; раз в игровой год после порога шанс
  `(age − threshold) / (limit − threshold) × 100%` (≥ limit → 100%) → `remove_creature(cause=old_age)`; благосклонность не
  защищает. Минусы: `aging_steps = floor((age − threshold) / (limit × 10%))`; у героя — `ActiveEffect(old_age)` −1 СИЛ/ЛОВ/ТЕЛ
  за шаг (`defaults.toml [world.aging] step_percent = 10`), у NPC — строка в хронике и `means` не меняются автоматически
  (меняет `world` по заметке) **[Т-13]**. Нет `species_id`/`birth_s` — существо не стареет (Дракон: birth_s = null).
- `world_sim/events.py`: природное событие раз в сезон (`chance_percent_per_season`, `kind` из пака — `rng` по порядку),
  `cause = "season:<name>"`, `kind=natural`; закрытие по сроку; события на старте — из `events.yaml`.
- `world_sim/triggers.py: check(bundle) -> CheckResult{fired: [ref], candidates: [...]}`: все `opportunity` NPC/фракций/
  богов (мёртвый NPC не срабатывает, ТЗ 4), героя (`hero.opportunity`), `Secret` — через `is_ready`/`evaluate`; `TRUE` →
  `fire` + `fired` + хроника; `then` → кандидат `act` для `world`. Флаги ставятся автофлагами (уже) и `set_flag`.
- `world_sim/nudge.py`: основная линия = активные (`state=active`) триггеры `key: true` владельцев `key: true` + мотив героя;
  «касание» в сцене = ключевая сущность в сцене (NPC в локации героя / упомянута запросом мастера) или изменение флага,
  на который ссылается условие такого триггера (дифф флагов сцены). Нет касания `nudge_scenes` сцен подряд → ступень +1:
  1 слух (`world_notice rumor`), 2 контакт (сигнал нарратору `nudge: contact <npc>` в `state_data`), 3 событие находит
  героя (кандидат `act` для `world`); после 3 → `sim.nudge.waiting = False`: ключевые триггеры с нарративной частью
  отдаются `world` с пометкой «герой не участвует» **[Т-14]**. Касание сбрасывает счётчик и ступень. Сигнал нарратору —
  как сигналы 2.3 (поле `nudge` в состоянии хода, без нового инструмента).

## A7. Релевантные NPC в контексте (перенос из этапа 4 по решению 5а)
`master/relevance.py: relevant_npcs(bundle) -> list[id]` = NPC в локации героя ∪ `key: true` (живые) ∪ владельцы активных
триггеров (`is_ready`, не `fired`); сортировка по id. `state_data.known_npcs` (сейчас «все именованные живые») заменяется
этим списком; секреты — только у NPC сцены, с пометкой «скрыто: играй с учётом, не раскрывай» (ТЗ 4). Бюджет вытеснения
неактивных NPC (ТЗ 11, пп. 2–3) — этап 4. В ARCHITECTURE и ТЗ 13 пометить «перенесено из этапа 4 в 3 (решение 5а)».

## A8. Боги и жрец (`rules/divine.py`, `combat`, `game/commands.py`)
- `favor_change{target: "hero"|npc_id, god_id, delta, reason}` (модель запроса меняется: сейчас `npc_id`) — нарратор:
  только `hero`; `world`: NPC. Лимиты: шаг ±2 (`[favor] step`), ±3 к богу за сцену (`scene.favor_spent`) — урезание +
  `limit-exceeded`; `frozen` бог → rejected «долг не выполнен». Соперник автоматически **не** меняется — нарратор/world шлёт
  второй `favor_change` (подсказка в правилах промпта) **[Т-15]**. Пороги — `rules/divine.py: tier(favor) -> -3..3`.
- Эффекты (зеркально): ±3 — сигнал нарратору в `state_data.divine` («знамения/дурные знамения»); +6 — запрос
  `pray{god_id}` по фразе игрока взводит `prayer_day`, ближайший **критический** бросок героя за день — преимущество (`ModifierSource`
  `divine_favor`); −6 — первый критический бросок за день — помеха автоматически (`curse_day_used`); +9 — при
  неминуемой смерти (третий проваленный death save / убивающий урон при 0 HP / `hero_died` в `downed`) — бросок 50% (+9)
  / 75% (+10), не чаще раза за главу → герой стабилизирован на 1 HP, богу добавляется триггер-долг
  (`debt:<hero>:<n>`, `then` из шаблона), бог в `frozen` до `set_flag debt_paid:<id>`; −9 — богу добавляется триггер
  «послать слугу» (`kills_hero: false`, `then: послать слугу`) — дальше `world`. **Критический момент** — флаг
  `critical_moment` в `RollRequest.tags`: death save, спасбросок от эффекта с `can_kill|can_remove`, проверки
  `stakes: critical` (ТЗ 4.2).
- Благосклонность игроку — приблизительно: `/sheet` и строка «Селунэ: благосклонна / равнодушна / гневается» (≥ 3 / −2..2 /
  ≤ −3).
- **Жрец:** `HeroState.deity_id`; `CastCheck` источники в `rules/cast_checks.py`: ≤ −3 — заклинание 1+ круга → проверка
  МДР СЛ 10, провал — ячейка потрачена; ≤ −6 — Channel Divinity недоступен, ячейки высшего доступного круга не
  восстанавливаются длинным отдыхом (`rests.py` спрашивает `divine`); ≤ −9 — только заговоры. Смена бога — через триггер-
  сделку пака (данными), стартовая у нового +1 (`rules/divine.change_deity`).

## A9. Бюджет боя, `warn_danger`, сокровища, `/tone` (2.3, 3)
- **Бюджет:** `srd/data/tables/encounter_budget.yaml` (SRD 5.2: XP-бюджет на персонажа по уровню 1–5, Low/Moderate/High);
  потолок = **Moderate** (решение G2а, вместо High) × число героев/напарников (сложность = 1.0, решение 7) **[Т-16]**; стоимость врагов = сумма
  `cr_xp`. Сверх бюджета разрешено, если: `warn_danger` по локации боя или её предку (`world.dangers`), или
  `start_combat.initiated_by = "hero"` (новое поле, нейтральное `"enemies"`), или в `world.fired` есть триггер с
  `kills_hero: true` за последние сутки. Иначе — урезание: убираются враги с конца списка (самые поздние), пока не
  влезут, лидер группы остаётся (если лидер один не влезает — бой без урезания + `budget_override_reason="leader"`) →
  `clamped`, сигнал мастеру, `limit-exceeded`. `max_enemies = 6` остаётся вторым пределом. `CombatState.
  budget_override_reason` заполняется причиной.
- **`warn_danger{location_id, text}`** → `DangerMark` + флаг `danger:<loc>` (префикс `danger:` зарезервирован).
- **Hoard и редкость (6а):** `gold{kind: "hoard"}` — таблица клада SRD 5.2 по ПО (для ур. 1–5 — CR 0–4, 5–10) в
  `srd/data/tables/hoard.yaml`; только при `last_combat` с лидером-логовом (`lair_location_id`) или по сцене в
  локации-логове, один раз (`looted`). `Item` в контенте получает `rarity: common|uncommon|rare|very_rare|legendary|
  artifact | None` и `magic: bool`; `give_item` магического предмета выше предела уровня (`[loot.rarity_cap_by_level]`:
  1–4 → uncommon, 5 → rare; уточнить по SRD при реализации) → не выдаётся, `clamped` + сигнал. Особые свойства предметов
  Дракона — текстом в `description` (решение 7).
- **`/tone`**: `/tone` — показать; `/tone <шкала> <значение>` — изменить (значение из списка шкалы; `mood` — свободно);
  `/tone hard_limits -<x>` — ослабление → подтверждение «да/нет»; `+<x>` — без подтверждения. Изменение → хроника
  (`kind: tone`) и автосейв; `system[1]` пересобирается (кэш префикса сбрасывается — ожидаемо).

## A10. Видимость запросов и инструменты
В `explore` открываются `warn_danger`, `favor_change`, `reveal_secret`, `event_start`, `event_end` — **без strict**
(как `end_chapter`, `location_create`: `STRICT_IN_EXPLORE` не расширяется, форму проверяет Pydantic) **[Т-17]**.
`reveal_secret`: `TRUE` → раскрытие; `NEEDS_NARRATIVE` и `narrative_ok` → раскрытие; иначе rejected «ещё рано».
`event_start` war/plague без `cause` = id сработавшего триггера из `world.fired` → rejected (2.1); прочие типы — `cause`
обязателен для war/plague, для остальных свободен. `afterlife_action` — скрыт (этап 8).

# Часть B. Партии

Каждая партия: TDD (тесты кабана-доебы первыми), `uv run pytest -q`, `uv run ruff check src tests`, ревью мамы-кабана,
синхронизация docs. Отпечаток `save_v3.schema.json` создаётся в П1 и перегенерируется сознательно в партиях, меняющих
схему (до закрытия этапа версия одна — v3) **[Т-18]**.

## П1. Пак кампании, календарь, уникальность, догрузка, Вейл → пак
**Состав:** A2, A3 (вся схема v3 + `m0003`), BACKLOG 7.
**Файлы:** `campaign/{__init__,models,loader,uniqueness,merge,build}.py`; `core/clock.py` (holidays, seasons);
`rules/uniqueness.py` (+ `check_faction/check_god/check_hero`); `state/{world,session,scene,memory,hero,triggers}.py` (v3);
`persistence/migrations/m0003_v2_to_v3.py`, `CURRENT_SCHEMA_VERSION=3`; `game/starter.py` → `new_world_from_pack`;
`game/app.py` (догрузка при загрузке, вывод конфликтов); `ui/cli.py` (`--campaign`); `campaigns/vale/*`;
`srd/data/{weapons/longbow,armor/studded_leather,items/explorers_pack,items/druidic_focus}.yaml`.
**Готово, когда:** новый мир Вейла собирается из пака и побайтно равен миру этапа 2 по сущностям (кроме новых полей);
все тесты этапа 2 зелёные с паком; v2 → v3; догрузка; конфликты.
**Тесты:**
- пак: минимальный валидный пак грузится; битая ссылка триггера → строка с файлом и полем; неизвестный ключ → ошибка
  (`extra=forbid`); календарь пака: 10 × 36, праздник 31-го в 30-дневном месяце → ошибка, `to_date/from_date`, `season()`;
- уникальность: id NPC = id локации → конфликт, сущность не загружена, список; два NPC с одним именем; NPC с именем героя;
  «Таверна» в двух родителях — можно, в одном — нельзя; бог/фракция с одинаковым именем; транзитивный отброс
  (триггер на отброшенного NPC); отброшена стартовая локация → старт отказан;
- догрузка: в пак добавлен NPC → появился в мире, хроника `pack_update`; изменён существующий NPC в паке → в мире
  прежний; новый NPC пака с id, занятым NPC `origin: ai` → конфликт; повторная загрузка — пустой отчёт;
- миграция: фикстура v2 (Вейл) → бэкап байт в байт, v3 валиден, tone `language: "русский"` → `""` + `notes`;
  `current_chapter` None; цепочка v0 → v3; отпечаток v3;
- Грей Вейла: длинный лук, проклёпанная кожа (КД 12 + Лов), набор путешественника, druidic focus — `build_character` ок;
- сторож импортов `campaign`.

## П2. Сцены и главы, граница сцены
**Состав:** A5 (без `world` — точка вызова с пустым набором кандидатов; `tick` — заглушка, заполняется в П3/П5).
**Файлы:** `game/scene.py`, `game/boundary.py` (новый), `game/turn.py` (`close_scene_if_needed` → `boundary.run`),
`game/app.py` (достройка `boundary_pending` при загрузке), `protocol/handlers/world.py` (`end_scene`, `end_chapter`),
`defaults.toml [scene] max_per_chapter = 15`, `ui/simple.py` (вывод закадрового блока и «Глава N: …»).
**Готово, когда:** сцена закрывается по всем 5 причинам, глава — по `end_chapter` и 15 сценам, порядок границы
соблюдён, сбой на границе откатывается и достраивается при загрузке.
**Тесты:** каждая страховка (location_changed / time_jump > 3600 с / hour — не закрывает / combat_ended / 31-й ход /
end_scene) → `closed_reason`, автосейв закрытой сцены **до** хода мира (порядок вызовов фиксируется шпионом);
`ensure_min_advance` +600 с; `end_chapter` → `ChapterSummary` с title, новая `ChapterState(number+1)`; 16-я сцена → глава
закрыта `scene_limit`; `summary` из `end_scene` в `memory.scenes`; исключение в шаге 3 → бандл как после автосейва,
`boundary_pending=True`, меню 2.2; загрузка такого сейва → граница достроена до первого хода; закадровый блок пуст → не
выводится; `hero_dead` → граница не идёт.

## П3. Структурный ход мира: триггеры, автофлаги, хроника, секреты
**Состав:** A6 (`triggers`, без смертности/событий), `reveal_secret` (A10), подсказка по секретам в контексте, A7.
**Файлы:** `world_sim/{__init__,triggers,candidates,chronicle}.py`; `protocol/handlers/world.py` (`reveal_secret`);
`protocol/schema.py` (видимость `reveal_secret`); `master/relevance.py`, `master/prompt.py` (`known_npcs` → релевантные,
секреты сцены); `master/prompts/narrator_rules.md` (секреты, reveal_secret).
**Готово, когда:** **критерий 1 этапа** — триггер NPC по флагу срабатывает на границе сцены.
**Тесты:**
- **критерий 1:** пак-фикстура: NPC `aldric`, триггер `{flag: grail_seen}`, `once`; ход мока `set_flag grail_seen` +
  `end_scene` → на границе `fired_count=1`, `state=fired`, хроника `trigger`, кандидат `act` с `then`; следующая граница —
  не срабатывает; `cooldown: 7d` — срабатывает снова через 7 дней, не раньше; мёртвый NPC — не срабатывает;
  триггеры фракции, бога (с `check_every_days`), героя;
- автофлаги: `npc_dead`, `visited`, `combat_ended`, `item_gained` (выдача `give_item` шлёт событие) → триггеры по ним;
- смешанное условие `all[flag, narrative]`: флага нет — не кандидат; флаг есть — кандидат `verdict` с `residual`;
- секреты: `reveal_secret` при FALSE → rejected «ещё рано» (бюджет невалидных не тратится); TRUE → `known_to_player`;
  NEEDS_NARRATIVE без `narrative_ok` → rejected; с `narrative_ok` → раскрыт; секреты в промпте — только NPC сцены, с
  пометкой «скрыто»;
- релевантные NPC: в сцене + key + с активным триггером; неключевой без триггера в другой локации — не в контексте;
  стабильность порядка (байты префикса не меняются между ходами).

## П4. Роль `world`
**Состав:** A4 целиком; подключение к шагу 3 границы.
**Файлы:** `master/world.py` (`WorldSession` поверх цикла `MasterSession` с `role="world"`), `master/prompts/
world_rules.md`, `protocol/requests.py` (`WorldVerdict`, `WorldNotice`; `actor` у проверок; `location_id`, `then_ref` у
`npc_update`), `protocol/schema.py` (`tool_set("world")`), `protocol/handlers/world.py` (verdict, notice),
`config/app.py` + `app_defaults.toml` (`[world] max_calls_per_day = 0`), `llm/replay.py` (по ролям), `ui/cli.py`
(`--replay` с двумя адаптерами), `world_sim/candidates.py`, `game/boundary.py`.
**Готово, когда:** **критерий 2 этапа** — 30 дней хода мира с мок-`world` по сиду воспроизводимы.
**Тесты:**
- нет кандидатов → нет вызова (журнал пуст); кандидаты из 3 NPC → **один** вызов; порядок кандидатов стабилен;
- `world_verdict` с лишним/пропущенным ref → invalid → повтор; ×3 → откат границы, `boundary_pending`;
- `holds=true` → `fire`; `false` → кандидат снова на следующей границе;
- `act`: `npc_update(location_id)` перемещает NPC; `npc_update(status=dead, cause=goal)` без `evidence_ref` броска этого
  вызова → rejected `invalid-death`; с `saving_throw(actor=npc)` → принято; `npc_update` без `then_ref` → invalid;
  запрос вне набора (`damage`, `give_item`) → `not_available_in_mode`;
- `world_notice visible` → закадровый блок на старте новой сцены; `rumor` + `delay: day` → доставка через сутки; `hidden` —
  только хроника;
- потолок `max_calls_per_day=1`: вторая граница за день — нарративные отложены, структурные `then` идут;
- **критерий 2:** `devtools/world_run.py` (в коде — `src/ai_dm/devtools/world_run.py`) `--pack tests/fixtures/packs/mini --days 30 --seed N --mock world_30d.yaml` (и
  pytest-обёртка): 30 границ по 1 дню (`advance_time day` + `end_scene`), смертность «Жестокий», событие сезона, 2
  нарративных триггера → два прогона: побайтно равные бандлы, хроника, журнал запросов; другой сид — другая хроника;
  replay записи → тот же бандл, изменённый пак → `ReplayDivergence`;
- журнал: записи `role: world`, `run_id` границы, `turn_status committed|aborted`; `/cost` показывает роль world.

## П5. Смертность, старость, глобальные события
**Состав:** A6 (`tick`, `mortality`, `aging`, `events`), `event_start/event_end` (A10).
**Файлы:** `world_sim/{tick,mortality,aging,events}.py`; (при первом тике П5 инициализирует `sim.last_season`/`last_year`: m0003 ставит только `last_day`); `srd/data/tables/lifespan.yaml`; `defaults.toml [world]`
(`mortality_presets`, `aging.step_percent`, `max_tick_days`); `protocol/handlers/world.py` (`event_start`, `event_end`);
`rules/modifiers/effects.py` (`old_age`).
**Готово, когда:** шаг мира — день; все 4 причины 4.1 работают за кадром детерминированно.
**Тесты:** пресет «Жестокий» на 100 NPC × 30 дней — число смертей в ожидаемом интервале (свойство на 50 сидах) и
воспроизводимо; «Спокойный» — 0 за 30 дней при фиксированном сиде; смерть → `DeathRecord(chance)`, `npc_dead:<id>`,
хроника; «отвести беду» при favor 10 → всегда спасён, при 0 — никогда; событие `plague ×20` в регионе → шанс NPC
в регионе и группе выше, вне региона — прежний; регион по цепочке `parent_id`; старость: человек 59 лет — нет проверки,
75 лет — шанс 50%, 90 — 100%; благосклонность не спасает; минусы героя −1 за шаг; NPC без `species_id` не стареет;
сезон: смена сезона → ровно один бросок, при 100% — событие `natural` с `cause season:<name>` и сроком; повторная граница в
тот же сезон — без броска; `event_start war` без `cause` → rejected; с `cause` = несработавший триггер → rejected; с
сработавшим → принят; `event_end` неизвестного → invalid; `ends_at_s` → событие закрыто тиком, `event_active` = FALSE;
скачок `month` → 30 дневных шагов, `week` → 7; `> max_tick_days` → прокручиваются последние `max_tick_days` дней, в хронике запись
«прожит без подробностей»; `event_start war|plague` с пустым `regions` → rejected `regions_required` (D3).

## П6а. Боги и благосклонность, жрец
**Состав:** A8.
**Файлы:** `rules/divine.py`; `rules/modifiers/` (`divine_favor` источник); `rules/roll_pipeline.py` (тег
`critical_moment` для death save/опасных спасбросков/`stakes: critical`); `combat/downed.py`, `rules/death_saves.py`
(хук вмешательства); `rules/cast_checks.py` (3 источника жреца); `rules/rests.py`; `protocol/requests.py`
(`FavorChange.target`, `reason`); `protocol/handlers/world.py` (`favor_change`); `game/commands.py` (`/sheet`
приблизительно); `master/prompt.py` (`divine` в состоянии).
**Готово, когда:** вся таблица 4.2 покрыта тестами на `ScriptedRng`.
**Тесты:** шаг ±2 и ±3/сцену урезаются; нарратор с `target=npc` → invalid; world с NPC → ок; `frozen` → rejected;
tier-границы −9/−6/−3/3/6/9; +6: запрос `pray{god_id}` по фразе игрока → первый критический бросок дня с преимуществом, второй — без, новый день — снова;
некритический не тратит; −6: первый критический за день — помеха; +9: смерть героя → 50% (ScriptedRng обе ветки), +10 —
75%, второй раз в главе — нет, после спасения — долг-триггер и `frozen`, `debt_paid` снимает; −9 → триггер «слуга»;
случайная смерть + favor (П5) — самый благосклонный бог; жрец: −3 провал МДР → ячейка потрачена; −6 Channel Divinity
недоступен и высший круг не восстановлен; −9 → только заговоры; смена бога → +1; `/sheet` — «гневается» при −4.

## П6б. Бюджет боя, `warn_danger`, сокровища, `/tone`, подталкивание
**Состав:** A9, A6 (`nudge`).
**Файлы:** `srd/data/tables/{encounter_budget,hoard}.yaml`; `rules/encounter.py` (бюджет), `rules/loot.py` (hoard,
rarity); `content/models/items.py` (`rarity`, `magic`); `protocol/handlers/combat.py` (`start_combat` бюджет,
`initiated_by`); `protocol/handlers/world.py` (`warn_danger`); `protocol/handlers/resources.py` (`gold hoard`,
`give_item` rarity); `rules/auto_flags.py`/`set_flag` (префикс `danger:`); `game/commands.py` (`/tone`);
`world_sim/nudge.py`; `master/prompt.py` (`nudge`, `tone`); `defaults.toml [loot] [encounter]`.
**Готово, когда:** 2.3 «Бой» и «Добыча» полностью; `/tone` по ТЗ 3; подталкивание по 3 ступеням.
**Тесты:** ур. 1, 4 гоблина (сумма > High) без оснований → урезание до бюджета, лидер остаётся, `clamped`, сигнал,
`limit-exceeded`; тот же бой после `warn_danger` по локации (или её родителю) → без урезания, `budget_override_reason=
warn_danger`; `initiated_by=hero` → без урезания; сработавший `kills_hero` → без урезания; `max_enemies` остаётся;
`set_flag danger:x` → reserved; hoard: CR 0–4 по таблице на `ScriptedRng`, второй раз → отказ (`looted`), без логова →
rejected; `give_item` rare на ур. 3 → clamped, uncommon — ок, немагический — без проверки; `/tone` показать; изменить
`violence жестоко` → хроника + сейв; значение вне шкалы → ошибка; ослабление `hard_limits` без «да» — не применено;
подталкивание: 8 сцен без касания → ступень 1 (rumor), 16 → 2 (сигнал `nudge` в состоянии), 24 → 3 (кандидат `act`),
касание (ключевой NPC в сцене / флаг условия) → сброс; после 3 — `waiting=False`, ключевой триггер уходит `world` с
пометкой.

## П7. Пак «Пьяный Дракон»
**Состав:** конвертер импорта + черновики ИИ + утверждение проектировщиком (решения 1в, 2б, 3а, 4а, 7); пак в репо.
**Файлы:** `devtools/import_dragon.py` (одноразовый конвертер сырого слота `saves/drunk_dragon/slots/manual-import` →
`campaigns/drunk_dragon/`), `campaigns/drunk_dragon/*`, `docs/plan-stage3.md` (что утверждено),
тест-фикстура — урезанная копия слота в `tests/fixtures/import/drunk_dragon/`.
**Конвертер (детерминированный, без модели):**
- `world.json` → `npcs.yaml`, `factions.yaml`, `pantheon.yaml`, `locations.yaml`, `events.yaml` (списки, порядок по id),
  флаги → `campaign.yaml.flags`, `clock.now_s` → `start.date/time` (0001-10-05 23:50), календарь — стандартный
  (Листопад = месяц 10); `settings.narration_style` → `truths.md`/`world.md` раздел «стиль» не переносится в tone, а в
  `tone.notes` (стиль вывода — этап 5, BACKLOG 5);
- `events[].regions` (имена) → id локаций по точному/нормализованному совпадению `name`; не найдено → строка в отчёте
  конвертера, регион выкинут (правит проектировщик); `type` свободный текст → оставить, `kind: caused`,
  `cause` — текст сохраняется (на старте пака события задаются паком, ТЗ 4.1.2 — `cause` не проверяется);
- **выжимка сцены (2б):** `session.current_scene` (title, situation, party, enemies_known, deadlines) +
  `pending_decision` (варианты, `player_choice`, неотвеченные реплики) + `memory.recent_turns` (8 × {player, dm_short}) →
  один текст `start.scene_summary` по шаблону: «Ситуация… / Отряд… / Известно о враге… / Сроки… / Последние ходы
  (кратко, 8 строк player → dm_short) / Незакрытый выбор: варианты 1–4, игрок выбрал «2 и 3» и спросил «статус?» —
  мастер ещё не ответил»; `offered_choices = []`, `recent_turns = []` (не переносятся);
- `current_chapter {ch2, title, scene_index 12}` → `start.chapter = {number: 2, title}`; `memory.chapters/scenes/
  game_summary` → `start/memory.yaml`; `chronicle` → `start/chronicle.yaml` (`day` → `at_s`);
- герой Грей → `heroes/grey.yaml` (choices + инвентарь, экипировка, 5400 мм, локация `iron_ridge_foothills`); предметы
  `saves/drunk_dragon/content/` → `campaigns/drunk_dragon/content/` (свойства — текстом, решение 7);
- `birth_s` и `combat: null` остаются пустыми; `origin` всех сущностей пака → `pack` (в импорте стоит `ai`) **[Т-19]**.
**Черновики ИИ (агент, не код игры) → утверждение проектировщика:** tone по шкалам ТЗ 3 (3а; предложение: mood
«мрачное героическое фэнтези», violence `жестоко`, horror `умеренно`, romance `есть`, language `сдержанно`, hard/soft —
пусто, на утверждение); мотивы 9 NPC без мотива, `key: true`, `opportunity` (структурные условия предпочтительно, ТЗ 4.01)
у ключевых NPC и всех 6 фракций, `pleased_by/angered_by/rivals` и `opportunity` 6 богов (4а); `deity_id` Грея — нет
(не жрец); `servants` богов. Каждый черновик — отдельный YAML-дифф в PR, проектировщик правит руками.
**Готово, когда:** `uv run ai-dm --new --campaign drunk_dragon --hero grey` стартует в главе II, сцена с выжимкой,
дата 0001-10-05 23:50, конфликтов нет, все триггеры валидны; утверждение проектировщика записано.
**Тесты:** конвертер на фикстуре — побайтно стабильный результат (golden), регионы-имена → id, нераспознанный → отчёт;
выжимка содержит все 4 варианта, «2 и 3», «статус?» и 8 строк ходов; `recent_turns`/`offered_choices` пусты; пак
`campaigns/drunk_dragon` грузится без ошибок и конфликтов (CI-тест на реальный пак); новый мир: глава 2 с title, хроника
дней 1–5, Ольбрехт `dead`, Варен `alive`, ритуал `nazir_ritual` активен, 54 кроны; мок-ход: нарратор видит выжимку в
состоянии (поле `scene_summary` в `state_data` для первой сцены мира); Вейл и Дракон сосуществуют (разные `campaign_id`).

**Порядок и зависимости:** П1 → П2 → П3 → П4 → П5 → П6а ∥ П6б → П7 (конвертер П7 можно начать после П1; черновики ИИ —
сразу после П1, утверждение — параллельно П3–П6). Без ответов проектировщика — П1–П3 (как в груминге).

# Часть C. Общие тесты этапа
- `tests/scenarios/test_stage3_done.py`: критерий 1 (П3) и критерий 2 (П4, 30 дней) на мини-паке
  `tests/fixtures/packs/mini/` (3 локации, 4 NPC, 1 фракция, 2 бога, событие сезона, триггеры структурные и нарративные).
- Все сценарии этапа 2 (`test_stage2_*`) зелёные на паке Вейла (без правок ожиданий, кроме новых полей).
- Детерминизм: ход + граница дважды → побайтно равные бандлы и журналы; сейв посреди главы → загрузка → продолжение
  идентично.
- Сторож архитектуры: `world_sim`, `campaign` — без llm/master/protocol/game/ui.
- Отпечаток `save_v3`; цепочка v0 → v3.

# Часть D. Риски
- Объём снимка: Дракон — 31 NPC, тик по дням на сотнях NPC — бенчмарк `devtools/world_run.py` 400 дней × 300 NPC
  (< 2 с) в П5.
- Кэш префикса: `/tone`, догрузка пака и новые NPC в `system[1]` сбрасывают кэш; `known_npcs` перенесён в `messages[0]` —
  проверить, что `system` между ходами байт в байт стабилен (тест есть).
- Роль `world` дешёвой модели (Haiku/Flash-Lite) может путать ref кандидатов — `world_verdict` строго проверяется,
  повторы 2.2; живой прогон проверит долю invalid.
- Strict: новые инструменты explore без strict — модель может ошибаться в форме чаще; Pydantic + пояснения.
- Replay по ролям: изменение порядка вызовов внутри хода (narrator ↔ world) не ломает replay, но изменение границы
  (ещё один вызов world) — `ReplayDivergence` (это правильно).
- Достройка границы при загрузке: не потерять `notices`/хронику при откате — граница целиком на копии.
- Дракон: противоречия источника (IMPORT_NOTES) остаются; «таверна внутри/у города», расстояния — грубые.
- Таблицы SRD (бюджет, hoard, редкость по уровню) — сверить с SRD 5.2 при вводе, `source: srd`; при сомнении — как
  `individual_treasure` (`source: custom` + BACKLOG).
- Не тянуть этап 4 (свёртка выжимок, вытеснение) и этап 9 (скачок по годам).

# Часть E. Чек-лист ручной живой сцены на паке «Пьяный Дракон»

Перед закрытием этапа — прогон на Claude (narrator Opus 5.5, world Haiku 4.5) и на Gemini (профиль gemini). Ключи в
окружении или `.env`. Результат — `docs/plan-stage3.md`.

Запуск: `uv run ai-dm --new --campaign drunk_dragon --hero grey --seed 1` (Gemini: `/model narrator gemini:<id>` и
`/model world gemini:<id>` до первого хода).

## Прогон
1. Старт: заголовок «Глава II: Отголоски Мора», дата 0001-10-05 23:50, локация — предгорья Железного Кряжа.
2. Ход 1: «2 и 3» — мастер отыгрывает привал и расспросы Эдрина (продолжение незакрытого выбора из выжимки).
3. Ход 2: «статус?» — числа HP, снаряжение, время до смены часовых, срок ритуала.
4. `/tone`, затем `/tone horror сильно` → хроника; `/tone hard_limits -<x>` → запрос подтверждения.
5. Движение к Восточной шахте (`travel_to` / `advance_time`) → закрытие сцены → граница: вызов world (если есть кандидаты),
   закадровый блок только при заметном событии.
6. Стычка с часовыми: бой в бюджете (2 орка) и попытка мастера выставить гарнизон (≈30 орков) без `warn_danger` →
   урезание с сигналом.
7. Разговор с Эдрином о культе → `reveal_secret` (рано → «ещё рано»).
8. Молитва Селунэ: запрос `pray{god_id}` по фразе игрока (если благосклонность ≥ 6 — иначе отказ с причиной).
9. `/cost`, `/quit`, `uv run ai-dm --world <id>` — продолжение с автосейва; `--replay` живого прогона.

## Что проверить
- [ ] Старт из пака: выжимка видна нарратору (рассказ продолжает привал, не начинает с нуля), `recent_turns` пусты.
- [ ] Схемы `world` и новых инструментов explore приняты API (Anthropic strict/без strict, Gemini).
- [ ] На границе ровно один вызов `world` (журнал `role: world`), или ноль, если кандидатов нет.
- [ ] Закадровый блок не выводится без заметного события; при событии — выводится один раз.
- [ ] Хроника пополняется (триггеры, tone); `/cost` показывает роль world отдельно.
- [ ] Урезание боя по бюджету: сигнал мастеру, рассказ подстроен, `limit-exceeded` в журнале.
- [ ] `reveal_secret` «ещё рано» не тратит бюджет невалидных и не ломает ход.
- [ ] Релевантные NPC: в `messages[0]` — Бран, Йорген, Лира, Эдрин, ключевые; не все 31.
- [ ] `cache_read > 0` на втором ходу (system стабилен; после `/tone` — один промах кэша, дальше снова чтение).
- [ ] Догрузка: добавить в `campaigns/drunk_dragon/npcs.yaml` нового NPC → перезапуск мира → NPC в мире, хроника
      `pack_update`; изменить мотив существующего → в мире прежний.
- [ ] Replay прогона без сети (оба адаптера ролей) → тот же бандл.
- [ ] Доля invalid у `world` (Haiku/Flash-Lite) небольшая; refusal на мрачном тоне (violence `жестоко`) — меню и подсказка.
- [ ] Сбой сети на границе → меню 2.2; «сохранить и выйти» → при следующем запуске граница достраивается.

# Часть F. Технические решения архитектора (этот план)
Т-1 `heroes/` вместо одного `character.yaml`. Т-2 сущности пака = модели сейва. Т-3 природные события 5% за сезон по
умолчанию. Т-4 `event.regions` — id локаций, регион по цепочке `parent_id`. Т-5 конфликтная сущность и всё, что на неё
ссылается, не грузятся (транзитивно). Т-6 `world.md`/`truths.md` копируются в сейв, догрузкой не обновляются. Т-7 «основная
линия» вычисляется, в схеме только `Trigger.kills_hero`. Т-8 слот `manual-import` не мигрируется — Дракон стартует из пака.
Т-9 потолок `world` откладывает только нарративные проверки. Т-10 `npc_update.location_id` и `then_ref` в режиме world;
закадровые проверки — `skill_check/saving_throw` с `actor` (закрытый список 2.1 не расширяется, кроме служебных
`world_verdict`/`world_notice`). Т-11 replay по ролям. Т-12 тик по дням, потолок 400 дней: последние 400 подробно, остальное — запись в хронике. Т-13 старость NPC — без
автоматической правки `means`. Т-14 «мир перестал ждать» = ключевые триггеры отдаются world без героя. Т-15 соперник бога
не меняется автоматически. Т-16 бюджет боя = Moderate SRD 5.2 (G2а). Т-17 новые инструменты explore без strict. Т-18 одна версия
схемы v3 на весь этап. Т-19 сущности пака Дракона получают `origin: pack`. Также: граница сцены — отдельная атомарная
транзакция с `boundary_pending`; секреты с нарративным условием подтверждает `world` (`narrative_ok`), а не нарратор;
молитва — запрос `pray{god_id}` по фразе игрока (G3б); релевантные NPC перенесены из этапа 4 (5а).

# Часть G. Продуктовые вопросы (на аппрув)
1. **Соперники богов (Т-15):** угодил богу → автоматически −1 его соперникам, или только явным `favor_change` мастера?
   Предлагаю явно (проще, без сюрпризов).
2. **Бюджет боя (Т-16):** потолок «High» SRD 5.2 при сложности 1.0 — подтвердить (BACKLOG 6: Арн/Грей проигрывают гоблинам
   — может, «Moderate»?).
3. **Молитва +6:** команда `/pray <бог>` (как предлагаю) или фраза игрока, которую распознаёт нарратор?
4. **Природные события:** 5% за сезон по умолчанию — ок?
5. **Дракон, предметы главы I** (`chapter_I_items_unaccounted`): не переносить (как сейчас) или вернуть часть в инвентарь?

## Решения проектировщика по части G (2026-10-03: «1а 2а 3б 4 нормально 5 а 6 романтики добавить можно»)
G1а. Благосклонность соперников бога — только явным `favor_change`, автоматически не меняется.
G2а. Бюджет боя — уровень «Moderate» SRD 5.2 (не «High»; проигрыши гоблинам, BACKLOG 6).
G3б. Молитва — фразой игрока, нарратор распознаёт и вызывает запрос молитвы (не команда `/pray`); Т-решение про `/pray` отменено.
G4.  Природные события — 5% за сезон по умолчанию (параметр пака).
G5а. Пропавшие предметы главы I Дракона не переносятся.
G6.  Тон Дракона: violence `жестоко`, horror `умеренно`, romance `есть` (уточнено проектировщиком; откровенное — за кадром, ТЗ 3), language `сдержанно`.

## Решения: Груминг этапа 3 (мини-влад + аудит кабана-свекрови, 2026-10-03) (бывш. docs/decisions/stage3-grooming.md)

### Снято ТЗ (не вопросы)
- Первый пак — «Пьяный Дракон» (ТЗ 14); Вейл тоже переводится в пак (stage2-plan п.3).
- `world`: один пакетный вызов на границе сцены на нарративные условия с выполненной структурной частью (ТЗ 2.0, 4.01);
  `then` → обычные запросы из закрытого списка (4.01, 2.1); шаг хода мира — день (4.1); подталкивание — сигнал нарратору (как 2.3).
- Потолок вызовов `world` — параметр конфига, по умолчанию выключен (лимиты 2.0 мягкие).

### Партии (черновик для папы-кабана)
П1 пак: схема, загрузчик, календарь пака, уникальность со списком конфликтов, догрузка новых сущностей (5.3), Вейл → пак,
   предметы Грея (BACKLOG 7). П2 сцены и главы: страховки (локация, >1 ч, конец боя, 30 ходов; глава — 15 сцен), ensure_min_advance,
   end_chapter, порядок на границе. П3 структурный ход мира: триггеры NPC/фракций/богов, once/cooldown, автофлаги, хроника; секреты
   и `reveal_secret`. П4 роль `world`. П5 смертность, старость, события (в т.ч. сезонные природные). П6а боги и жрец (4.2 целиком,
   благосклонность NPC через world). П6б бюджет боя/`warn_danger`, hoard и редкость, `/tone`, подталкивание. П7 пак «Пьяный Дракон».
Без ответов проектировщика можно П1–П3.

### Импорт Дракона (проверено на копии)
`load_slot` падает на `session.pending_decision` (kind offer_choices вне Literal, нет actor, лишние поля); m0002 молча обнуляет
`current_scene` и 8 `recent_turns` формы {player, dm_short} — нужен конвертер импорта. Мотив заполнен у 22/31 NPC, key у 10;
opportunity пусты у всех NPC и фракций; у богов пусты pleased_by/angered_by/rivals; birth_s/combat = null; тон — свободный текст
(`language: "русский"` — ошибка смысла); события — свободный type, regions именами.

### Решения проектировщика (2026-10-03: «1в 2б 3а 4а 5а 6а 8 ок»; «8 ок» = пункт 7)
1в. Пак «Пьяный Дракон» = текущее состояние: старт сразу с главы II (без пака с дня 1).
2б. Незакрытый выбор и 8 последних ходов импорта сжимаются в выжимку текущей сцены (не offered_choices/recent_turns).
3а. Тон Дракона под шкалы ТЗ 3: агент предлагает значения, проектировщик утверждает.
4а. Мотивы/триггеры/opportunity NPC и фракций, pleased_by/angered_by/rivals богов: черновик ИИ, проектировщик правит.
5а. Минимальный фильтр релевантных NPC (в сцене + key + с активным триггером) переносится из этапа 4 в этап 3 (пометить перенос).
6а. Hoard и предел редкости для ур. 1–5 — по таблицам SRD.
7.  Особые свойства предметов Дракона — текстом, механика с треком 1.5; бюджет боя по SRD, сложность = 1.0 без настройки.

## Правки по ревью: Ревью П1 этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p1-review.md)

Решения — оркестратор (технические). K — src/**, campaigns/**, docs/**; T — tests/**. Параллельно.

R1. **Старые миры Вейла → пак:** m0003 ставит `campaign_id = "vale"` (world и manifest), если `campaign_id is None` и `world_id`
    начинается с `vale-` (все миры этапа 2 — Вейл); `lore.world_text` пустой → заполняется при догрузке из пака (только если пуст).
R2. **«Новая» сущность при догрузке = id нет в мире (любого origin)** — буквально по плану; занятый ИИ id → не новая, без конфликта
    (идемпотентно, отчёт пустеет). Конфликт по *имени* у новой сущности с любой сущностью мира — как прежде. Явное `current.origin`
    вместо getattr. Тест «id занят NPC origin: ai → конфликт» переписать на «→ не добавляется, отчёт пуст».
R3. Транзитивный отброс не задевает существующие сущности мира: в `dropped` не кладутся id, которые есть в мире; ссылка на них
    допустима. Игнор `connections` при отбросе + вырезание связей — записать (это решение).
R4. Тесты: `game/app.merge_pack` — все ветки (нет campaign_id, нет каталога, PackError → предупреждение, added, conflicts, вызов при
    /load); CLI — `--campaign`, `--hero` не из пресетов (код 2), PackError (код 1), «Старт отказан» (код 1), печать конфликтов,
    догрузка при `--world`, запрет `--campaign` без `--new`. Для этого `campaigns_dir` — параметр `main(..., campaigns_dir=None)`
    (по умолчанию CAMPAIGNS_DIR).
R5. Ленивая загрузка текста Вейла (`vale_world_text()`), импорт `ui/cli.py`/`game/starter.py` не читает файлы.
R6. m0003: `sim.last_day = clock.now_s // 86400` (литерал); `last_season`/`last_year` — инициализирует П5 при первом тике (записать
    в STAGE3-PLAN П5).
R7. Грей: `money_cp: 700` (7 зм стандартного набора следопыта — решение проектировщика «стандартный набор»).
Мелочи: `pack_content_dir` один раз; m0003 дописывает к существующему `tone.notes`; список пресетов через `', '.join`.

## Правки по ревью: П2 этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p2-notes.md)

- `scene_count` считает сцены главы, включая текущую: +1 при `start_scene` на границе; новая глава начинается с 1.
  Глава закрывается на границе, если `end_chapter` или `scene_count >= scene.max_per_chapter` (15).
- `end_chapter` помечает `current_chapter.closed_reason="end_chapter"` (+ title) сразу в ходе: ждёт ближайшей границы.
- `end_scene` пишет `summary` прямо в `SceneState.summary`; в `memory.scenes` попадает только непустая выжимка.
- Закадровые заметки доставляются и удаляются из `world.notices` (флага «доставлено» в схеме нет); `hidden` остаются.
- Сбой шага 3 (любое `Exception`) — копия выбрасывается, меню `error_menu`; «Повторить» достраивает границу, ход не повторяет.
  `run_turn` при `boundary_pending` сначала достраивает границу; `load` тоже (сцену при этом не стартует до достройки).
- `ensure_chapter` (глава 1 для сейвов без главы) вызывается при достройке границы, а не при каждой загрузке.
- `on_scene_boundary` удалён (заменён `game.boundary`).
- Ревью П2: `finish_boundary` ловит только `TurnFailed`/`LlmError`; строка игрока при упавшей достройке хранится в
  `runner.deferred_input` и играется при `retry`; `ensure_chapter` — в `load` и в начале `close_boundary`; `scene_count=1` — в `campaign/build.py`.
- Не чиним: если `save_auto` (шаг 2) бросил `OSError` после того, как ход уже закоммичен, исключение уходит наверх: `boundary_pending=True`
  в памяти, но автосейва закрытой сцены нет; ход игрока в бандле есть, граница не достроена до следующего хода/загрузки.

## Правки по ревью: Ревью П2 этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p2-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
(15 failed в первом прогоне ревьюера — моя ошибочная правка tests/unit/game/test_game_scene.py, откачена; не дефект кода.)

B1. `ensure_chapter(bundle)` — в `GameApp.load` сразу после загрузки (до достройки границы) и в начале `close_boundary`;
    в `close_chapter` — страховка. `started_at_s` восстановленной главы = `current_scene.started_at_s`, если сцена есть.
    Тест: старый сейв без главы → load → глава 1; `end_chapter` при этом пишет title/closed_reason; выжимка первой сцены входит
    в ChapterSummary.
D2. `finish_boundary` ловит только ожидаемые сбои (`TurnFailed`, `LlmError` и будущие ошибки роли world) → меню; прочие исключения
    пробрасываются (бандл не тронут — работа на копии; `boundary_pending` уже в автосейве).
D3. Ввод игрока не теряется: `run_turn` при `boundary_pending` сначала достраивает границу; если достройка упала — строка игрока
    сохраняется как отложенная (`runner.deferred_input`), меню ошибки; `retry` достраивает границу и, если есть отложенная
    строка, играет её как обычный ход. Тест: сбой достройки в run_turn → retry → граница достроена и ход сыгран (turn_seq +1,
    выжимка сцены одна).
D4. `scene_count=1` ставится при создании ChapterState в `campaign/build.py`; костыль в starter убрать.
D5. `retry` при pending вызывает `mark_journal(run_id, committed|aborted)`.
D6. Ветка «save_auto бросил OSError после commit» — описать в docs/plan-stage3.md (не чиним сейчас).
M7–M9. Комментарий TurnResult про on_scene_boundary/этап 4 обновить; ранний return в `load` после упавшей достройки.
T. Тесты UI: вывод «Глава N: …» и блока «За кадром» (и отсутствие пустого блока); retry после сбоя границы через GameApp.

## Правки по ревью: П3 этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p3-notes.md)

- `world_sim/triggers.check(bundle) -> CheckResult{fired, candidates}`: владельцы по порядку god, faction, npc, hero (по id).
  `TRUE` -> `fire` + `world.fired` (ref `trigger:<owner>:<id>`) + хроника `trigger` + кандидат `act`; `NEEDS_NARRATIVE` ->
  кандидат `verdict` с `residual`. Кандидаты отсортированы: verdict-триггеры, verdict-секреты, act; внутри -- вид владельца, id
  владельца, id триггера. Кандидат -- плоская модель (`owner_kind/owner_id/owner_name/motive/means`), не вложенный `owner`.
- NPC не `alive` (dead/gone/changed) не срабатывает и не даёт кандидатов; герой -- только `status == "active"`;
  бог -- только `status == "alive"`.
- Боги проверяются реже: схема WorldSim получила `god_checked_s: dict[god_id, секунды]` (время последней проверки, со
  срабатыванием или без). Первая проверка сразу, дальше -- не раньше `check_every_days` суток после предыдущей. Отпечаток
  `save_v3.schema.json` надо перегенерировать (Т-18).
- Секрет-кандидат: нераскрытый, `narrative_ok=False`, условие `NEEDS_NARRATIVE`, NPC жив и стоит в локации закрытой сцены
  (`current_scene.location_id`, не `hero.location_id`: при `location_changed` герой уже ушёл).
- `game/boundary.check_triggers` возвращает `CheckResult`; `finish_boundary` его пока не использует (вызов `world` -- П4).
- `reveal_secret`: открыт в explore (без strict), убран из `HIDDEN_TYPES`. FALSE и `NEEDS_NARRATIVE` без `narrative_ok` --
  `rejected` «ещё рано» (не `Invalid`, бюджет невалидных не тратится); уже раскрытый -- `accepted` без изменений; в `result` --
  текст секрета для рассказа.
- `relevant_npcs`: из NPC берутся только `named` и `alive` (как прежний `known_npcs`), затем в локации героя ∪ `key` ∪ с
  `is_ready`-триггером. В состоянии хода добавлено поле `secrets` (нераскрытые секреты живых NPC локации героя, с пометкой
  «скрыто: играй с учётом, не раскрывай»); `scene_npcs` не менялся.
- Ревью П3, R1: нераскрытые секреты живых NPC в локации -- общий хелпер `rules/secrets.hidden_secrets(world, location_id)`.
  Источник локации различается: промпт берёт локацию героя (ход идёт), кандидаты границы -- локацию закрытой сцены
  (`current_scene.location_id`; при `location_changed` герой уже ушёл).
- R2: `relevant_npcs` дополнительно включает именованных живых NPC, чьё `name` (без регистра) встречается в
  `session.offered_choices` или в `player_input`/`narration` всех `recent_turns` бандла.
- R4: секрет с нарративной частью условия до П4 всегда «ещё рано» (`reveal` при `NEEDS_NARRATIVE` без `narrative_ok`); в П4 роль
  `world` выставляет `narrative_ok` вердиктом.
- У `Faction` поля статуса нет, фильтр по статусу не нужен.
- Сторож архитектуры: только `game` импортирует `world_sim`, поэтому хелпер лежит в `rules/secrets.py`, а `relevance` не использует `candidates.current_hero` (свой цикл по героям).

## Правки по ревью: Ревью П3 этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p3-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**.
R1. Общий хелпер «нераскрытые секреты живых NPC в локации X» (world_sim или rules) для промпта (локация героя — ход идёт)
    и кандидатов границы (локация закрытой сцены); различие источника записать в docs/plan-stage3.md.
R2. `relevant_npcs` дополнительно включает именованных живых NPC, чьё имя встречается в `offered_choices` или в рассказе/вводе
    последних `recent_turns` (сравнение по `name` без учёта регистра, детерминированно) — фильтр 5а не должен обрывать линию.
    Тест: NPC вне локации, не key, без триггера, упомянут в последнем ходе/варианте → в known_npcs; не упомянут → нет.
R3. Тест отката: сбой после check_triggers (монкипатч update_nudge/close_chapter → TurnFailed) → в исходном бандле world.fired,
    chronicle, sim.god_checked_s пусты, fired_count 0, boundary_pending True.
R4. В notes: секрет с нарративной частью до П4 всегда «ещё рано»; в П4 world выставляет `narrative_ok` вердиктом.
Мелочи: фильтр статуса фракции, если поле есть; комментарий «результат check_triggers — в П4» в finish_boundary; в пометке
секрета «раскрытие — только через reveal_secret»; relevance использует `candidates.current_hero`.

## Правки по ревью: П4 этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p4-notes.md)

- Набор инструментов `world` (8): `world_verdict`, `world_notice`, `skill_check`, `saving_throw`, `set_flag`, `npc_create`,
  `location_create`, `npc_update`. `favor_change`, `event_start/event_end`, `warn_danger` из закрытого списка плана в набор
  пока не входят: их обработчики появляются в П5/П6 (в `HIDDEN_TYPES` они остаются), тогда же добавляются в `MODE_TOOLS["world"]`.
  Strict: `world_verdict`, `world_notice`, `skill_check`, `saving_throw`, `set_flag`; без strict -- `npc_create`, `location_create`,
  `npc_update` (как в explore).
- Схемы нарратора не менялись: закадровые версии запросов (`actor` у проверок, `location_id` и `then_ref` у `npc_update`) --
  отдельные модели `WORLD_MODELS` в `protocol/requests.py`; `REQUEST_MODELS`/`ALL_TYPES` (28) нетронуты. `parse_request(data, mode)`,
  `tool_defs(exposed, mode)`; `WORLD_HANDLERS` в `protocol/apply.py`, обработчики -- `protocol/handlers/offscreen.py`.
- `then_ref` обязателен только у `npc_update` и должен быть ref любого кандидата вызова (act или verdict): `then` подтверждённого
  вердиктом триггера world исполняет в том же вызове. Иначе `Invalid(invalid_then_ref)`.
- `world_verdict`: `Invalid(invalid_verdict_refs)` при лишних/пропущенных/повторных ref; повторный вызов после принятого --
  `Invalid(verdict_done)`. Обязательность при verdict-кандидатах -- через `MasterSession.required_tool("world")`. Применение
  вердиктов (fire, `world.fired`, хроника `trigger`, `narrative_ok`) -- в `world_sim/verdicts.apply_verdicts` после вызова, не в обработчике
  (protocol не знает world_sim).
- Закадровая проверка NPC (`actor`): d20 без бонуса (у NPC нет листа характеристик), СЛ по категории; состояние -- `NPC.creature` или временное.
  Мёртвый/неизвестный NPC -- Invalid.
- `world_notice`: все заметки в `world.notices` (`deliver_at_s = now + delay`: none 0, day 86400, week 604800); `hidden` дополнительно
  пишет хронику `kind: event`. Доставка (`visible|rumor`) -- прежний `deliver_notices` на границе.
- Потолок `world.max_calls_per_day` (`[world]` в `app_defaults.toml`, `AppConfig.world`): при достижении из кандидатов остаются только
  `act` (их `then` всё равно исполняются вызовом); без `act` вызова нет. Счёт дня -- `sim.world_calls_today` + новое поле
  `sim.world_calls_day` (день `now_s // 86400`, -1 = счёта нет); пишется только когда вызов состоялся. Отпечаток `save_v3.schema.json`
  надо перегенерировать (вместе с `god_checked_s` из П3).
- Вход вызова: `master/world.py: WorldPromptBuilder` (`system[0]` -- `prompts/world_rules.md`, `system[1]` -- tone, lore, truths, пантеон;
  `messages[0]` -- JSON: время/сезон/праздник, закрытая сцена, герой, кандидаты, релевантные NPC и их локации, `location_ids`,
  активные события, `dangers`). «Известность героя» из плана в схеме не существует -- не передаётся. Модель запроса -- `roles.world`
  (или профиль по модели адаптера). `master` не импортирует `world_sim`: кандидаты приходят объектами из `game`.
- `WorldSession.run` работает на копии границы, rng берёт из бандла и возвращает обратно. Журнал: `role: world`, `run_id = bnd-<stamp>-<n>`
  (`TurnRunner.next_boundary_id`), `turn_status` ставит `TurnRunner.take_boundary` по `BoundaryResult.world_run_id`.
- `finish_boundary(bundle, cfg, registry, world=None, run_id=None)`: `world=None` -- вызова нет (старые вызовы без изменений).
  `TurnRunner(world_adapter=None)` -- адаптер нарратора (контракт `world_kit`); в CLI адаптер world всегда свой.
- Пустой финал роли `world` после раунда инструментов -- нормальный конец (рассказа она не пишет).
- Replay по ролям: `ReplayAdapter(records, role=None)`; CLI: `--replay` создаёт два адаптера (narrator, world). Новый флаг `--mock-world PATH`;
  `--mock` без него -- world идёт через мок рассказчика. Профиль world для CLI -- `pick_world` (тот же провайдер, что у рассказчика).
- `devtools/world_run.py` лежит в `src/ai_dm/devtools/` (рядом с `sim_combat.py`): `run_world(...)`, `main(argv)`. «Нарратор» без модели:
  `clock.advance(DAY)` + `close_boundary("end_scene")` + `finish_boundary`. Дневной тик (смертность, сезон) -- П5; до неё сид на хронику не влияет.
- Журнал: `report_tags` записей world пустой (запись пишется до исполнения запросов, как у нарратора).

### Ревью П4
- B1: у броска хранится бросавший (`ctx.roll_actors`); смерть/уход за кадром принимается только с `evidence_ref` броска этого же NPC.
- B2: `then_ref` на verdict-кандидата -- только после `world_verdict` с `holds=true` по нему (`verdict_not_confirmed`).
- D3: в режиме world `actor` у проверок обязателен (`actor_required`), бросков героя за кадром нет.
- D4: без отдельного адаптера world модель = `profiles[провайдер адаптера].world` (нет профиля, например мок, -- `roles.world`);
  `/model narrator` при смене провайдера пересоздаёт адаптер world на профиль нового провайдера (если world был настоящим).
- D5: `then_ref` необязателен у `set_flag` и `world_notice` (отдельные модели `WorldSetFlag`, `WorldNotice.then_ref`); указан на verdict --
  правило B2. Принятый риск: без `then_ref` модель может творить свободные закадровые события, не привязанные к кандидату.
- D6: `apply_verdicts` пропускает кандидата, чей триггер/секрет исчез. D7: запись хроники -- `state/memory.add_entry`
  (`world_sim.chronicle` её реэкспортирует).
- M8: `messages[0]` у world с `cache=True` -- осознанно (повторяется в раундах инструментов одного вызова). M9: `user_input`/`world_text`
  в `WorldPromptBuilder.build` не используются (общий интерфейс). M11: отпечаток `save_v3.schema.json` перегенерируется отдельным шагом (тесты).

## Правки по ревью: Ревью П4 этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p4-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
B1. Страж 4.1: смерть/уход NPC за кадром — `evidence_ref` должен быть броском этого же NPC (`actor_id == npc.id`, хранить actor в
    `add_roll`), иначе rejected `invalid-death`. Тест: бросок героя / чужого NPC → отказ, NPC жив.
B2. `then_ref` на verdict-кандидата — только после `world_verdict` с `holds=true` по нему, иначе Invalid `verdict_not_confirmed`;
    в world_rules.md «сначала world_verdict». Тест: npc_update до вердикта / по отклонённому → invalid, состояние без изменений.
D3. В режиме world `actor` у skill_check/saving_throw обязателен (`actor_required`); бросков героя за кадром нет.
D4. Без отдельного world-адаптера модель world = профиль провайдера рассказчика (`profiles[provider].world`); `/model narrator`
    при смене провайдера переключает и world на профиль нового провайдера; записать в notes.
D5. `then_ref` (необязательный) у `set_flag` и `world_notice` в режиме world; если указан на verdict — то же правило B2.
    Без `then_ref` — допустимо (свободные закадровые события), принятый риск записать.
D6. `apply_verdicts`: `next(..., None)` + пропуск, без StopIteration.
D7. Хроника из protocol — через общий помощник в `state/memory` (вынести из world_sim.add_entry), один путь записи.
M8–M11. Notes: кэш messages[0] у world — осознанно; комментарий про неиспользуемые параметры build; тест replay достройки после
    сбоя world (две world-записи, первая aborted); формулировка про отпечаток схемы.

### Наблюдение оркестратора после ревью
- CLI replay world: модель world берётся из текущего профиля, не из журнала (requested_model). При смене конфига между игрой и
  replay — расхождение отпечатка. Брать модель из записи журнала — в П5 (мелкая правка ui/cli).

## Правки по ревью: П5 этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p5-notes.md)

- `world_sim/{tick,mortality,aging,events}.py`; `game/boundary.tick_days` вызывает `world_sim.tick.tick_days(bundle, rng, cfg, registry)` с rng бандла
  и пишет состояние rng обратно (нет дней -- состояние не меняется). Дни: от `sim.last_day + 1` до текущего включительно; время дня `at = день * 86400`
  (события и возраст считаются на `at`, а запись смерти/хроники берёт текущее время мира).
- Первый тик: если `last_season == ""` и `last_year == 0`, сезон и год берутся на день `last_day` (m0003 ставит только `last_day`); смена сезона
  и года дальше считается по дням, так что пропущенный интервал даёт свои переходы.
- Порядок существ: именованные живые NPC по id, затем активные герои по id. Один бросок `randbelow(N)` на существо в день; `N = per_day // множитель`.
  «Отвести беду»: лучший бог по благосклонности (при равенстве меньший id), бросок d10 только при благосклонности > 0; членство бога в пантеоне не проверяется.
  Хроника спасения -- `kind: favor`.
- Множитель события: событие активно на `at`, локация существа или её предок по `parent_id` в `regions` (пустые `regions` = везде), группы NPC пересекаются с
  `affects` (пусто или «все» = все; у героя групп нет, значит попадает только под «все»/пусто). Берётся максимум.
- Старость: таблица `lifespan.yaml` (ключи `вид:threshold` и `вид:limit`; только человек, полурослик, дварф, эльф); при смене года возраст `> порога` -- шанс
  `(возраст - порог) / (предел - порог)` одним `randbelow(предел - порог)`, `>= предела` -- смерть без броска. Шаги: `(возраст - порог) * 100 // (предел * step_percent)`;
  у NPC `aging_steps` + запись в хронике, у героя `ActiveEffect(id="old_age", kind="old_age", params={steps})`; штраф на броски СИЛ/ЛОВ/ТЕЛ даёт `EffectSource`
  (разница модификаторов при характеристике на `steps` ниже; `sheet.abilities` не меняется; КД, хиты и т.п. не пересчитываются).
- События: закрытие по сроку -- сутки `(at - DAY, at]`, запись в хронику один раз; `ends_when` -- только структурная часть (`evaluate == TRUE` закрывает
  событие `ends_at_s = at`); нарративный `ends_when` кандидатом `world` не стал (в A4 такого вида кандидата нет). Закрытые события остаются в `world.events`.
- Природное событие на смене сезона: один бросок `randbelow(100) < chance`, при попадании и непустых `kinds` ещё `randbelow(len(kinds))`; id `natural:<тип>:<день>`,
  `kind=natural`, `cause=season:<имя>`, срок из `duration`, `hazard` копируется из вида. Автоматических бросков `hazard` в тике нет (по плану это закадровый
  `saving_throw` модели world).
- `event_start/event_end`: открыты в explore (без strict, `STRICT_IN_EXPLORE` не менялся) и в world; `HIDDEN_TYPES` теперь `warn_danger, favor_change, afterlife_action`.
  war/plague требуют `cause` из `world.fired` (иначе `rejected`, без метки авто-репорта); у запроса нет множителя, поэтому `mortality_multiplier` = 1
  (кроме событий из пака и природных). Неизвестный регион -- Invalid, дубль id -- Invalid, `event_end` неизвестного -- Invalid, уже закрытого -- accepted без изменений.
- `game/turn.take_boundary`: `result.hero_dead` ставится, если герой умер за кадром при тике.
- CLI replay: модель world берётся из `requested_model` первой записи роли world журнала (иначе из профиля).
- Конфиг: `defaults.toml [world] max_tick_days = 400`, `[world.aging] step_percent = 10`; тик на больше дней -- `ValueError`.

### Ревью П5
- B1: тик длиннее `max_tick_days` прокручивает только последние `max_tick_days` дней; пропущенные -- запись хроники «Мир прожит без подробностей: N дн.»
  (N -- число пропущенных дней), `last_day` = сегодня, исключения нет.
- D2: `[world.event_multipliers]` (plague 20, war 5, famine 5, прочие 1) -- множитель событий от модели; значения на проверку проектировщику.
- D3: пустые `regions` = весь мир; war/plague от модели требуют непустые `regions` (`Invalid regions_required`).
- D4: `event_end` хронику не пишет, закрытие пишет тик один раз.
- D5: уведомление о смерти героя за кадром (`hero_dead` в `take_boundary`) -- только для текущего героя (один активный герой до этапа 7).
- M6: смерть и записи хроники тика датируются `at` дня события. M7: убран лишний `max(1, multiplier)`. M8: id природного события не дублируется (добавляется `_`).
- Бэклог: нарративный `ends_when` как кандидат world; старение прочих видов (сейчас 4).

## Правки по ревью: Ревью П5 этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p5-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
B1. Потолок тика: при скачке больше `max_tick_days` прокручиваются только последние `max_tick_days` дней (смертность, события,
    сезоны, годы внутри окна), `last_day` → сегодня, хроника «Мир прожит без подробностей: N дней». Без исключения. Тест.
D2. Множитель смертности для событий от модели — по `event_type` из конфига `[world.event_multipliers]`: plague = 20 (план),
    war = 5, famine = 5, прочие = 1 (настраиваемо; значения — на проверку проектировщику при приёмке).
D3. `regions` события: пусто = весь мир (description поправить); war/plague от модели требуют непустые `regions` (Invalid).
D4. `event_end` не пишет хронику — закрытие пишет тик один раз. Тест «event_end → тик → одна запись».
D5. В notes: уведомление о смерти героя за кадром — только для текущего героя (один активный герой до этапа 7).
M6. Смерть и хроника тика — с `at` дня смерти. M7. убрать лишний max(1, …). M8. защита от дубля id natural-события.
Бэклог: нарративный `ends_when` как кандидат world; старение прочих видов (сейчас 4).

## Правки по ревью: П6а этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p6a-notes.md)

- `rules/divine.py`: `tier`, `approx_label`, `best_favor` (перенесён из `world_sim/mortality`, там реэкспорт импортом), `change_favor` (шаг ±2 `[favor] step`, ±3 за сцену
  `[favor] per_scene`, сумма модулей по фактическому сдвигу, шкала −10..10), `try_intervention`, `pay_debt`, `add_servant_trigger`, `can_pray/pray`, `change_deity`,
  `channel_divinity_blocked`, `locked_slot_pool`. Конфиг `[favor]` (`FavorConfig`, значения по умолчанию в самой модели).
- `favor_change{target, god_id, delta, reason}`: нарратор -- только `target=hero`, иначе Invalid `hero_only`; роль world -- только id NPC (без `then_ref`, одна модель
  на обе роли). Лимит сцены: герой -- ключ `god_id` в `scene.favor_spent`, NPC -- `npc_id:god_id`. Каждый ненулевой сдвиг пишется в хронику (`kind: favor`).
  `delta=0` -- Invalid. Заморозка (`hero.divine.frozen`) -- rejected. Соперник бога не меняется (G1а).
- `pray{god_id}` (видимый нарратору, G3б): favor >= 6, бог не заморожен, сегодня ещё не молились -- `prayer_day = день`; бог неизвестен -- Invalid; иначе rejected с сигналом.
  Первый критический бросок героя за день (`critical_moment` или `stakes=critical`, у RollRequest задан `now_s`) снимает `prayer_day` в None и ставит `prayer_used_day`
  (новое поле `DivineState`), поэтому повторно в тот же день помолиться нельзя. Помеха −6 -- `curse_day_used`. Источник модификаторов `DivineFavorSource`
  (`rules/modifiers/divine_favor.py`) зарегистрирован в `default_modifier_registry`; он сам тратит дневной запас (как реролл-эффекты мутирует актёра).
- `critical_moment`: `stakes_tags` добавляет флаг при `stakes=critical`; death save его уже имел. Спасбросков боя от «эффектов, способных убить/вывести» (`can_kill|can_remove`)
  в контенте нет -- не размечены.
- Вмешательство +9: хук `intervene(hero) -> god_id|None` в `death_saves.{check_three,roll_death_save,after_damage,resolve_out_of_combat}` и исход `"saved"`; вызывается
  перед каждым `mark_dead` (3-й провал, убивающий урон при 0 HP, мгновенная смерть по overkill). Бросок `rng.d(100) <= 50/75` (`[favor] intervention_percent_9/10`),
  только если есть бог с favor >= 9 из пантеона, не замороженный. `intervention_chapter` = id текущей главы (`""` -- только в тестах без главы; после П2 глава есть всегда), `intervention_god` -- кто вмешался (новое поле).
  Герой 1 HP в сознании; бог получает триггер `debt:<hero>:<n>` (`if: flag debt_paid:<hero>:<n> = false`, `once`, then из `[favor] debt_then`), `frozen` +бог, `debts` +id.
  Выплата -- `set_flag debt_paid:<hero>:<n>` (обработчик `set_flag` вызывает `divine.pay_debt`): триггер выключается, бог размораживается, если других долгов ему нет.
- Слуга −9: после `favor_change` героя, если tier = −3, богу добавляется триггер `servant:<hero>:<god>` (`if: favor god lte −9`, `then: "послать слугу"`, cooldown `[favor] servant_cooldown`);
  «бог-враг» понят как бог, чья благосклонность упала до −9.
- Жрец: `DivineCastSource` в `default_cast_check_registry()` (только герой-жрец с `deity_id`): ≤ −3 -- `CastCheck(ability_check wis, dc 10)` для 1+ круга, ≤ −9 -- `forbidden`.
  Бой: `castable_spells` не предлагает 1+ круг при `forbidden`; `cast.perform` после траты ячейки бросает проверку, провал -- событие `spell_wasted`. `rests.long_rest`: при ≤ −6 пул
  высшего круга (наибольший `spell_slot:N` с max > 0) не восстанавливается. Божественный канал: в контенте нет такого умения, есть только `divine.channel_divinity_blocked(hero)`.
- Игроку: `/sheet` -- строки «Бог: благосклонна/равнодушна/гневается»; `state_data.divine` -- `gods` (mood, omens от ±3, frozen), `can_pray`, `debts`.
- Смена бога: только `divine.change_deity` (favor нового +1, старые не трогаются); вызова из запросов/триггеров пака нет.
- Ревью: D1 -- `debt_scene` (id долга -> сцена вмешательства), `set_flag debt_paid` в той же сцене -- rejected «долг ещё не исполнен». D2 -- `add_exhaustion(..., intervene=)`: на 6-й степени
  вмешательство вместо смерти, степень 5 (путь `defeat_outcome exhaustion`; HP при вмешательстве ставится в 1 только при 0 HP). D3 -- `prayer_god`: преимущество только если у бога
  favor >= 6 и он не заморожен. `favor_change` отдаёт модели `mood` и `applied`, а не число шкалы.

## Правки по ревью: Ревью П6а этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p6a-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
D1. Долг снимается не раньше следующей сцены после вмешательства: `set_flag debt_paid:…` в сцене вмешательства → rejected
    «долг ещё не исполнен»; дальше — нарратором или world. В narrator_rules: номер долга — из `divine.debts`.
D2. Истощение 6-й степени — тоже путь вмешательства (`divine_save` перед `mark_dead`; при спасении степень истощения −1).
D3. Преимущество молитвы — только от бога, которому молились: хранить `prayer_god`; нужно `favor[prayer_god] >= 6` и бог не frozen.
D4. STAGE3-PLAN: заменить устаревшие `/pray` (строки ~231, 379, 383, 489, 520) на «запрос `pray{god_id}` по фразе игрока».
M. `favor_change` отдаёт модели `approx_label` и фактический сдвиг, не число шкалы; `now_s` в cast_wasted; notes: «раз за главу»
   при chapter_id "" (главы есть всегда после П2).

## Правки по ревью: П6б этапа 3: решения при реализации (кабан-разработчик) (бывш. docs/decisions/stage3-p6b-notes.md)

- Бюджет боя: `rules/encounter.py`, таблица `srd/data/tables/encounter_budget.yaml` (SRD 5.2, ур. 1-5, low/moderate/high), потолок `[encounter] tier = "moderate"` (G2а), на героя. Урезание: с конца списка, лидеры групп остаются; одни лидеры не влезают -> без урезания, `budget_override_reason="leader"`. Основания (порядок проверки): `warn_danger` (локация героя или предок), `initiated_by=hero` -> "hero", `kills_hero` за последние сутки -> "kills_hero". Причина пишется только если без неё было бы урезание. `initiated_by` взводит `scene.hero_initiated_combat`.
- `warn_danger`: открыт нарратору (без strict) и роли world; одна `DangerMark` на локацию (повтор обновляет текст); флаг `danger:<loc>`; префикс зарезервирован (`auto_flags.RESERVED_FLAG_PREFIXES`).
- Клад: `gold{kind: hoard}`; `LastCombat.lair_location_id` (из `Group.lair_location_id`) и `hoard_looted` (отдельно от `looted`). Условия: нет боя в ходе, last_combat с логовом, один раз. Ветка «по сцене в локации-логове» не сделана (в тестах без боя -- Invalid). Таблица `hoard.yaml` -- `source: custom` (в SRD 5.2 денежной таблицы клада не нашлось; числа по схеме прошлой редакции, не сверены); магические предметы в кладе не бросаются.
- Редкость: `Item.rarity`, `Item.magic`; предел `[loot.rarity_cap_by_level]` (1-4 uncommon, 5 rare) -- custom, не сверен с SRD 5.2. `give_item` выше предела -> clamped, предмет не выдан. Зелье лечения: common, magic.
- `/tone`: `game/tone.py`; шкалы mood/notes -- свободный текст, violence/horror/romance/language -- из типов `Tone`, hard_limits/soft_limits -- `+x`/`-x`; ослабление hard_limits -- `app.pending="tone_confirm"`, меню `["да","нет"]`; изменение -> хроника `tone` и автосейв.
- Подталкивание: `world_sim/nudge.py`, вызывается из `boundary.update_nudge(work, cfg, check)` ДО вызова world (кандидат ступени 3 уходит в тот же вызов). Касание считается на границе: ключевой живой NPC в локации закрытой сцены или изменение флага условия ключевого триггера с прошлой границы (`NudgeState.flags_seen`). Ступени: слух (структурный Notice rumor, без модели), контакт (`NudgeState.contact_npc` -> `state_data.nudge = "contact <npc>"`), событие (кандидат `act`, `waiting=False`). Касание сбрасывает счётчик, ступень, контакт и `waiting=True`. Основная линия: активные key-триггеры владельцев key (NPC.key; у фракций, богов, героя ключевость владельца не проверяется).
- Схема сейва изменилась (`LastCombat`, `NudgeState`): отпечаток `tests/schema/save_v3.schema.json` надо перегенерировать.
- Ревью П6б: D1 лог «Бой сверх бюджета: основание»; D2 ветка leader -- остаются только лидеры; D3 первая граница только запоминает флаги (`flags_seen` хранит и отсутствующие как None, пусто при пустой линии); D4 герой не цель слуха/события, слух без имени; D5 клад по сцене в локации-логове (тег `lair` у локации героя или предка, либо логово последнего боя), один раз на логово -- флаг `hoard:<loc>` (резерв префикса), после боя тоже ставится; M единый сигнал урезания бюджета и max_enemies. Отпечаток схемы перегенерирован доебой.

## Правки по ревью: Ревью П6б этапа 3 (мама-кабан): спецификация правок (бывш. docs/decisions/stage3-p6b-review.md)

Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
Таблицы: encounter_budget = SRD 5.2 (ур.1–5: 50/75/100, 100/150/200, 150/225/400, 250/375/500, 500/750/1100) — сверено
ревьюером по памяти, совпадает с кодом; hoard — custom (в SRD 5.2 нет); предел редкости — по DMG 2024 (комментарий).
D1. Бой сверх бюджета пишет в лог «Бой сверх бюджета: основание {reason}»; narrator_rules: `initiated_by=hero` — только если игрок
    своей репликой в этом ходу нападает первым; засада/встреча/нападение врагов — `enemies`.
D2. Ветка `leader`: если не влезают даже лидеры — остаются только лидеры (рядовые урезаются), reason `leader`.
D3. Подталкивание: на первой границе (пустой `flags_seen`) — только запомнить флаги, не касание; `flags_seen` обновлять и при пустой линии.
D4. Владельцы-герои не выбираются для слуха/события; если в линии только герой — подталкивания нет. Слух без имени владельца.
D5. Клад по сцене в локации-логове (план A9): без боя, если локация сцены (или предок) — логово группы; один раз на логово —
    флаг `hoard:<loc>` (и после боя тоже ставится, чтобы не взять дважды).
M. Объединить сигналы урезания по бюджету и по max_enemies; STAGE3-PLAN: A5 — порядок (подталкивание перед world), A9 — Moderate (G2а);
   notes: отпечаток выполнен.

## Правки по ревью: П7: правки по черновикам Дракона (решения проектировщика, 2026-10-04) (бывш. docs/decisions/stage3-p7-review.md)

### Мотивы богов — корыстные (направление проектировщика; черновики, # draft)
«Мотивы богов — более корыстные. Селунэ — покровительство жизни, каждая живая душа священна, богиня жизни; радует,
когда всё цветёт и живёт; с весной силы возрастают, с осенью убывают.»
- Селунэ (жизнь): motive «Каждая живая душа священна; её сила — в живом и цветущем: чем больше жизни в её землях, тем она
  сильнее»; pleased_by: спасённая жизнь, рождение, исцеление, посеянное и выращенное, цветущая земля; angered_by: напрасная
  смерть, нежить, Мор, убийство сдавшихся; rivals: shar, abyss_demon; сила по сезонам (S1).
- Латандр: motive «Всё новое должно начинаться под его именем — храмы, клятвы, первые шаги — его слава»; pleased_by: дела,
  начатые с его именем, восстановленные святилища, уничтоженная нежить (оскорбляет рассвет); angered_by: благословение без
  благодарности, брошенные начинания.
- Шар: motive «Питается утратами и забытым; хочет, чтобы её боялись и почитали тайно, а свет Селунэ погас»; pleased_by:
  предательство, утрата, забытые имена; angered_by: возвращённая память, знаки Селунэ.
- Безликий: motive «Копит секреты: каждое скрытое знание — его сила»; pleased_by: хранимая тайна, сделка в тени, украденное
  знание; angered_by: раскрытые тайны и имена его служителей.
- Ильматер: motive «Набирает силу от тех, кто принимает чужую боль; ему нужны мученики»; pleased_by: стойкость в страдании,
  боль, взятая за другого; angered_by: спасение себя ценой чужой боли, лёгкие пути.
- Демон Бездны — без изменений.
Триггеры богов переписать под новые мотивы (структурные условия, нарратив только со структурной частью), # draft.

### S1. Сила богов по сезонам — формат пака (решение «в»)
`God.season_power: dict[str, int]` (имя сезона календаря → поправка в процентных пунктах, по умолчанию пусто).
Действует: шанс вмешательства (+9: 50%, +10: 75%) ± поправка текущего сезона, ограничено 0..100. Мастеру в
`state_data.divine.gods[]` — `power: растёт|обычна|убывает` (знак поправки). Знамения — по-прежнему триггерами.
Селунэ в паке Дракона: весна +15, лето 0, осень −15, зима −25 (# draft — числа на утверждение).
Схема v3 (не выпущена) — поле с дефолтом, без миграции; отпечаток перегенерировать.

### Решения проектировщика (2026-10-04)
- Боги — новые мотивы и триггеры приняты (остаются # draft до приёмки этапа). Селунэ: лето **+25** (весна +15, осень −15, зима −25).
- Исправление оркестратора: `selune.omen_for_the_living` — условие «знамение ещё НЕ было» (`not flag selune_owl_omen_seen`).
- Q1. Ольбрехт и Верховный Иерарх остаются `key: true` (триггер мёртвым не нужен).
- Q2. Мотив героя: поле `motive` у пресета героя → в состояние героя (если поля нет — добавить с дефолтом ""), видно мастеру
  в state_data героя; подталкивание учитывает мотив героя как прежде (через триггеры героя). Грей: «Поддерживать баланс мира:
  как охотник жить в гармонии с природой и беречь жизнь в любом её виде».
- Q3. Добавить локации «Предгорья Кряжа» (`iron_ridge_foothills_villages` или ближайший id по раскладке) и «Серый Квартал»
  (в городе, parent — город); регионы событий `harvest_raids` и `city_council_conspiracy` — на них.

## Итог: Аудит этапа 3 (кабан-свекровь, 2026-10-04): решения проектировщика (бывш. docs/decisions/stage3-audit.md)

Проектировщик: «делай всё по рекомендациям».
В1б. Скачок > max_tick_days: последние дни подробно, остальное — запись в хронике; годовой бросок за пропуск — этап 9 (BACKLOG).
     План (Т-12, A6) и ARCHITECTURE синхронизировать.
В2а. Множители смертности событий: plague 20, war 5, famine 5 — утверждены.
В3.  War/plague от модели — только с непустыми regions — утверждено.
В4а. Клад логова: своя таблица (не DMG — лицензия), числа предлагает ИИ, source: custom.
В5.  Предел редкости по уровню: сверить с SRD 5.2 (Magic Items); нет в SRD → своё правило, source: custom с пометкой.
В6.  Слуга враждебного бога — не чаще раза в 30 дней — утверждено.
В7а. «Бог-враг» при −9 — бог, у которого благосклонность героя −9.
В8.  Старость героя — −1 к броскам СИЛ/ЛОВ/ТЕЛ без изменения характеристик, КД, хитов — утверждено.
В9а. Свободные закадровые флаги и заметки мира (без триггера) — разрешены.
В10. Выжимка Дракона очищена от служебного (dm_hint, мета-вопросы, «по шагу»); notes тона — только стиль текста; правило
     рассказчика «только обычный текст» + игра выбрасывает блоки ```. (живой прогон: Gemini рисовал рамки и колонки)

### Клад: предложение (В4а, на утверждение проектировщику)
Таблица `srd/data/tables/hoard.yaml`, source: custom. Формула монеты: count d sides x множитель (в монетах).
Среднее — в золотых (1 зм = 100 медных). Для сравнения: индивидуальное сокровище 0-4 = 4d6 x 1 зм (в среднем 14 зм) за одного
побеждённого, 5-10 = 4d6 x 10 зм (140 зм).
| Полоса (макс. CR) | Монета | Кости | Множитель (в медных) | Среднее |
|---|---|---|---|---|
| 0-4 | медные | 3d6 | x 100 | 10,5 зм |
| 0-4 | серебряные | 2d6 | x 500 | 35 зм |
| 0-4 | золотые | 3d6 | x 500 | 52,5 зм |
| 0-4 | итого | | | около 98 зм |
| 5-10 | серебряные | 2d6 | x 2000 | 140 зм |
| 5-10 | золотые | 3d6 | x 5000 | 525 зм |
| 5-10 | платиновые | 1d6 | x 10000 | 350 зм |
| 5-10 | итого | | | около 1015 зм |
(1 зм = 100 медных, 1 платиновая = 10 зм.)
Полоса выше 5-10 берётся как 5-10 (уровни героя 1-5). Клад — раз на логово.

### Сверка с SRD 5.2.1 (В5), источник: SRD_CC_v5.2.1.pdf (CC-BY-4.0, media.dndbeyond.com/compendium-images/srd/5.2/)
- Предел редкости по уровню: в разделе «Magic Items» / «Magic Item Rarity» (с. 204-206) редкость описана как «rough measure of power»,
  таблица «Magic Item Rarities and Values» даёт только цены (Common 100 зм, Uncommon 400, Rare 4000, Very Rare 40000, Legendary 200000).
  Привязки редкости к уровню героя в SRD нет. Решение: оставить своё правило `loot.rarity_cap_by_level` (1-4 -- uncommon, 5 -- rare),
  source: custom, в defaults.toml помечено; прежняя ссылка на DMG 2024 убрана.
- `encounter_budget.yaml`: сверена таблица «XP Budget per Character» (Step 2: Determine Your XP Budget), уровни 1-5, Low/Moderate/High:
  50/75/100, 100/150/200, 150/225/400, 250/375/500, 500/750/1100 -- совпадает с файлом полностью, правок нет.

### Клад: утверждено проектировщиком (2026-10-04)
Таблица клада (~98 зм при ПО 0–4, ~1015 зм при ПО 5+) — утверждена.

### Грей: уровень 3, Повелитель зверей (решение проектировщика, 2026-10-04)
- Грей в паке Дракона — следопыт 3 уровня, подкласс «Повелитель зверей» (своя редакция: в SRD 5.2 его нет, текст PHB не берём,
  source: custom). Зверь-спутник есть в истории и помогает вне боя (след, разведка); в бой вступает на этапе 7 (напарники).
- Сначала умения следопыта 2–5 ур. по SRD 5.2 (кусок трека 1.5): стиль боя, умения 2–5 ур., заклинания следопыта до 2 круга,
  ячейки полузаклинателя, подкласс Охотник (SRD) и Повелитель зверей (custom); затем Грей → 3 ур. в пресете пака.

## Итог: Живой прогон Дракона: преимущество и помеха от позиции и скрытности (2026-10-04) (бывш. docs/decisions/stage3-live-advantage.md)

Проектировщик: «Если персонаж выше цели или бьёт скрытно — преимущество. Если атакующий ниже атакуемого — помеха.»
Сейчас: преимущество/помеха есть только от состояний (невидимый, ослеплён, лежит и т.п.), Спрятаться нет, высоты зон нет.
Высота — домашнее правило проектировщика (в SRD 5.2 нет), скрытность — по SRD 5.2 (действие Спрятаться → Невидимый).

V1. Высота: у зоны боя поле `elevation: int` (0 — уровень земли; >0 — выше: стена, крыша, уступ; <0 — ниже: яма, овраг),
    мастер задаёт в `start_combat` (описание поля + правила рассказчика). Атака из зоны выше зоны цели — преимущество
    «высота»; из зоны ниже — помеха «ниже цели»; в одной зоне — без эффекта. Для монстров — так же.
V2. Скрытность (SRD 5.2): действие «Спрятаться» в бою — доступно, если в зоне героя есть укрытие (cover_*) или зона сильно
    затенена/заслонена (ZoneFeature `obscured`), и ни один враг в его зоне не видит его прямо (упрощение: врагов в зоне нет).
    Проверка Скрытности (Лов) СЛ 15 → состояние Невидимый (`hidden`) до первой атаки/заклинания или пока враг не обнаружит
    (Внимательность врага ≥ результата Скрытности на его ходу — проверку бросает движок у врага, ищущего героя).
    Атака из укрытия — преимущество «скрытно», после атаки скрытность снимается. Вне боя — удар из засады: если мастер
    начинает бой по успешной Скрытности героя (`start_combat` c `hero_hidden=true`), первая атака героя с преимуществом.
V3. Преимущество и помеха отменяют друг друга (SRD): в строке броска указано, откуда каждое: «d20 (7, 15 → преим.: высота,
    скрытно)»; при взаимной отмене — «преимущество и помеха гасят друг друга (высота / яд)».
V4. Пункты действий в бою: «Спрятаться (Скрытность СЛ 15)», когда доступно.
T. Тесты: выше → преимущество, ниже → помеха, одна высота → нет; монстр сверху; Спрятаться (успех/провал, недоступно без
   укрытия), атака из скрытности с преимуществом и снятие; обнаружение врагом; засада; взаимная отмена с подписями.

### Реализация (2026-10-04)
- Высота: `Zone.elevation` (дефолт 0), `ZoneSpec.elevation`; `ElevationSource` в combat/zones.py читает `tags["height"]` (выше минус ниже; тег ставится, только если не 0). Только зоны разной высоты, т.е. дальний бой.
- Скрытность: состояние `invisible` с `source="hidden"` и `dc` (результат Скрытности; у засады 15) — преимущество на атаку и помеха атакующим по SRD. `combat/stealth.py`: Спрятаться (действие, Скрытность СЛ 15; нужны `cover_*`/`obscured` в зоне и нет врагов в зоне), поиск врагом в начале его хода (Мдр-проверка против dc). Скрытность снимается первой атакой/заклинанием и концом боя.
- `start_combat.hero_hidden` — засада.
- Подписи: `Modifier.label`, `RollRequest.base_adv_label` («дальность», «враг рядом»); строка: «d20 (7, 15 → 15, преим.: высота, скрытно)», «d20 (9, 14 → 9, помеха: ниже цели)», при отмене «d20 (12; преимущество и помеха гасят друг друга (высота / яд))».
- Сейв: аддитивно (`Zone.elevation`, `AppliedCondition.dc`), версия не поднята.

## Итог: Живой прогон Дракона: КД в листе и особые стрелы (2026-10-04) (бывш. docs/decisions/stage3-live-arrows.md)

Проектировщик: «не понимаю, почему КД у Грея 15, что на нём надето»; «зажигательные, бронебойные, серебряные стрелы не дают эффекта».
Решения проектировщика: эффекты — вариант «Сильнее»; боезапас — «выбор + расход».
(Меняет решение 7 груминга этапа 3 для стрел: механика стрел — сейчас; прочие предметы Дракона — по-прежнему текстом.)

A1. `/sheet` показывает экипировку (доспех, щит, оружие в руках, надетые вещи) и раскладку КД:
    «КД 15 = Мифриловая кольчужная рубаха 13 + Лов 2 (предел средн. доспеха 2)»; эффекты (+2 «Каменная кожа» и т.п.) — слагаемыми.
A2. Особые стрелы (эффекты в данных предмета, не в коде; источник campaign:drunk_dragon):
    - Зажигательная: +1d6 огнём; цель горит — ещё 1d6 огнём в начале её следующего хода.
    - Бронебойная: при расчёте попадания игнорирует бонус КД от щита и часть доспеха выше 12 (итог КД цели не выше 12 +
      бонус Лов цели и прочие эффекты; если КД цели ≤ 12 — без изменений). В строке атаки — «vs КД 12 (бронебойная)».
    - Морозная: +1d8 холодом; скорость цели −10 фт до конца её следующего хода.
    - Серебряная: +2d6 против нежити и тварей Мора; считается серебряным оружием (обходит сопротивление к немагическому урону).
      «Твари Мора» — тег монстра/NPC `mor` в данных (добавить тег существам Мора в паке Дракона).
A3. Бой: отдельные пункты действий «Длинный лук — зажигательная стрела (осталось 10)» для каждого вида особых стрел в инвентаре
    (только для оружия, которым они стреляются: лук; композитный лук — тоже); выстрел тратит 1 стрелу; 0 — пункта нет.
    Обычные стрелы не считаются. Доп. урон — отдельной строкой: «Зажигательная стрела: 1d6 (4) огненный».
T. Тесты: раскладка КД в /sheet (Грей); каждый эффект стрелы (урон/горение/скорость/бронебойность/серебро против тега mor
   и нежити, без бонуса против прочих); расход и исчезновение пункта на 0; детерминизм.

### Клинок и «Каменная Кожа» (проектировщик: «клинок и каменную кожу тоже оживи»; эффекты — из описаний пака)
A4. Клинок Северного Ветра: +2d6 (тип урона клинка) против нежити и тварей Мора (тег `mor`), отдельной строкой
    «Клинок Северного Ветра: 2d6 (…) рубящий»; «рассекает магические щиты» — при расчёте попадания клинком игнорируются бонусы КД
    цели от заклинаний и магических эффектов (Щит, Щит веры и т.п.), в строке атаки — пометка.
A5. Эликсир «Каменная Кожа» (2 шт.): выпить — бонусное действие в бою (пункт «Выпить: Каменная Кожа (осталось 2)»), вне боя —
    через мастера (запрос использования предмета; если такого нет — тем же путём, что зелье лечения); эффект на 1 час
    (ActiveEffect с истечением по часам мира): +2 КД, сопротивление рубящему и дробящему урону; в /sheet — слагаемым КД
    «Каменная Кожа +2 (до HH:MM)». Расход 1 шт.
T. Тесты: бонус клинка против mor/нежити и не против прочих; игнор магического КД; эликсир — +2 КД, сопротивление (урон вдвое),
   истечение через 1 час, расход, пункт в бою бонусным действием.

## Итог: Живой прогон Дракона: заклинания вне боя (2026-10-04) (бывш. docs/decisions/stage3-live-cast-explore.md)

Проектировщик: «Нет механики: Сотворение заклинания „Лечение ран“ вне боя для восстановления здоровья».
Причина: у рассказчика нет запроса на сотворение заклинания вне боя (в бою — пункты cast:…).
C1. Запрос нарратора `cast_spell{spell_id, circle, target, free}` (explore, не strict; target — "hero" | id NPC | "" (на себя/без цели);
    circle — 0 для заговоров; free — бесплатное применение умения, напр. Избранный враг). Проверки как в бою: заклинание
    известно/подготовлено, есть ячейка нужного круга (или бесплатное применение), жрец/немилость (P6а), концентрация
    (новое заклинание с К сбрасывает прежнее). Нет — Invalid с понятным кодом (`no_slot`, `not_prepared`, …).
C2. Эффект по данным заклинания, тем же кодом, что в бою: лечение (Лечение ран и т.п.) — восстанавливает HP, строка
    «Лечение ран: 2d8 (…) + 2 Мдр = 11 → Грей HP 25/25»; Метка охотника вне боя — концентрация на цели (если цель — NPC
    в локации; переходит в бой, если бой с этой целью начнётся в течение длительности); прочие — трата ячейки, концентрация
    и длительность (ActiveEffect по часам мира), результат — в рассказе. Лог: «Грей читает Туманное облако (1 круг, ячейки 1/3)».
C3. Правила рассказчика: заклинание героя вне боя — только через cast_spell.
T. Тесты: Лечение ран вне боя лечит и тратит ячейку; без ячеек → Invalid no_slot; неизвестное → Invalid; концентрация
   сбрасывает прежнюю; Метка вне боя — free тратит Избранного врага, ячейку нет; немилость жреца (если применимо); лог.

## Итог: Живой прогон Дракона: понятное меню хода в бою (2026-10-04) (бывш. docs/decisions/stage3-live-combat-menu.md)

Проектировщик: «в D&D у меня перемещение, действие, бонусное действие, а здесь много атомарных опций, как будто я больше
ничего не могу сделать; либо я синтаксис не понимаю».
Факт: экономия хода в движке есть (после выбора меню показывается снова с оставшимся, ход кончается «Закончить ход»),
и свободный текст уже работает («стреляю в гоблина и отхожу» → несколько шагов). Но меню плоское и этого не объясняет.
M1. Меню хода сгруппировано по ресурсу, сверху — что осталось:
      Твой ход — действие ✓ · бонусное ✓ · перемещение ✓ · реакция ✓        (потраченное — «—»)
      Действие:            1. Атака: композитный лук → Воин-гоблин 1 …
      Бонусное действие:   7. Метка охотника → … ; 8. Выпить: Каменная Кожа (осталось 2)
      Перемещение:         9. Перейти: Уступ
      Без затрат:          10. Закончить ход
    Нумерация сквозная; группы без пунктов не печатаются; заклинания — по своему времени накладывания.
    Атака при Extra Attack / мульти — «Атака (ещё 1 из 2)».
M2. Подсказка под меню (один раз за бой и по /help): «Можно словами: „стреляю в гоблина и отхожу на уступ“ — ход соберётся из
    нескольких шагов. Номер — один шаг; после него меню покажет, что осталось.»
M3. Каждый пункт помечен ресурсом в данных (`ActionOption.cost`: action | bonus | move | free | reaction); тот же признак
    уходит модели в combat.options (для разбора фраз).
M4. После шага меню печатается снова только с оставшимися ресурсами; если не осталось ничего, кроме «Закончить ход», — ход
    заканчивается сам.
T. Тесты: группы и заголовок ресурсов; потраченное «—»; пустые группы не печатаются; сквозная нумерация и выбор по номеру;
   подсказка один раз за бой; автоконец хода; ширина ≤ 80.

### Дополнение (живой прогон этапа 4, 2026-10-05)
Проектировщик: «выполнил только бонусное действие, а основное ещё не сделал, и программа посчитала, что я завершил ход».
Факт: свободный текст («бегу на карниз и ставлю метку» → `move`, `cast:hunters_mark`) закрывал ход, когда шаги кончились,
хотя действие не потрачено (hold был только у номера).
M5. Свободный текст: после шагов ход остаётся открытым (меню с оставшимся), если основное действие героя не потрачено и
    ему есть что предложить; если действие потрачено — ход закрывается сам, как раньше (неистраченные бонусное/перемещение
    не держат ход). Номер — без изменений (M4).
    Уточнения ревью: ход держит любой оставшийся пункт с `cost == "action"`, в т. ч. вторая атака Extra Attack
    («ещё 1 из 2»); отклонённая импровизация и пропущенные недоступные шаги действие не тратят — ход тоже открыт.
    Рассказчику (narrator_rules): если в логе нет хода других участников — ход героя продолжается, ответ врагов не описывать.

## Итог: Живой прогон Дракона: «Каменная Кожа» не видна (2026-10-04) (бывш. docs/decisions/stage3-live-effects-visible.md)

Проектировщик: «применял Каменную Кожу 2 раза, но не видел +2 к КД».
Журнал drunk_dragon-ee8aa926: в последнем бою все атаки врагов шли «vs КД 17» (15 + 2) — эффект действовал. Но:
- первый раз мастер списал эликсир через take_item («Отдано: …») — без эффекта (до появления use_item);
- второй раз эликсир выпит в бою поверх действующего — эффект не складывается, эликсир потрачен впустую, лог «+2 КД до 03:12»
  без пометки «уже действовал»;
- КД 17 виден только в строках атак врагов; ни в заголовке хода, ни в строке состояния эффекта нет.
E1. Заголовок хода и строка состояния: «КД 17 (Каменная Кожа до 03:12)»; активные эффекты героя с временем окончания —
    строкой «Действует: Каменная Кожа (+2 КД, сопр. рубящему/дробящему) до 03:12; Метка охотника → …».
E2. Повторное применение действующего эффекта: пункт «Выпить: Каменная Кожа (уже действует до 03:12)»; при выборе — эффект
    не складывается, длительность продлевается, лог «Каменная Кожа уже действовала — продлена до ЧЧ:ММ». То же для use_item.
E3. У take_item появляется поле `why: "given" | "lost" | "stolen" | "spent"` (обязательное в схеме, нейтрального значения нет —
    «spent» = израсходован не применением). take_item расходника с эффектом применения (эликсир, зелье) с любым `why` кроме
    given/lost/stolen → rejected с сигналом «герой применяет предмет — вызови use_item». Правило рассказчика: пить/применять —
    только use_item.
T. Тесты: E1 строки; E2 повтор — один эффект, продлён, лог; E3 take_item эликсира why=spent → rejected с сигналом; why=given → принято.

## Итог: Живой прогон Дракона: спутники отстают от героя (2026-10-04) (бывш. docs/decisions/stage3-live-followers.md)

Проектировщик: «до боя Йорген, Бран и Эдрин шли со мной, Лирой и Акелой по шахте, а после боя оказывается, что они в шахту
не заходили».
Причина (сейв drunk_dragon-ee8aa926): Грей и сцена — `east_shaft`, а Бран, Йорген, Эдрин, Лира — `iron_ridge_foothills`.
`travel_to` двигает только героя; понятия «идёт с героем» нет; после границы сцены модель видит их location_id и пишет,
что их там не было. (Полноценные напарники в бою — этап 7; здесь только «кто идёт с героем».)
F1. У NPC поле `follows: str | None` (id героя). `travel_to` героя перемещает и всех `follows == hero`; лог
    «С тобой: Бран Седогрив, Йорген, …». Смерть/уход NPC — `follows = None`.
F2. `npc_update` получает `follows: "hero" | "none" | ""` (присоединился / отстал / без изменений); правила рассказчика:
    когда NPC присоединяется к герою или остаётся/уходит — отметить это запросом, а не только текстом.
F3. Промпт: у NPC в known_npcs/scene_npcs признак «с тобой»; спутники всегда релевантны (фильтр 5а).
F4. Пак Дракона: в стартовом состоянии главы II Бран, Йорген, Лира, Эдрин — `follows: grey` (отряд у подъёма к шахте).
F5. Живой мир: спутники уже отстали — исправление сейва только с согласия проектировщика (разовый скрипт: follows + локация
    героя для четырёх NPC). Догрузка пака существующих NPC не меняет (5.3).
F6. Бой: спутники мех. в бою не участвуют (этап 7); в state боя/рассказа — список «рядом спутники» для повествования.
T. Тесты: travel_to переносит спутников, не трогает прочих; npc_update follows hero/none; лог «С тобой»; признак в промпте и
   релевантность; пак Дракона — четверо с follows; смерть снимает follows.

## Итог: Живой прогон Дракона: карта боя (2026-10-04) (бывш. docs/decisions/stage3-live-map.md)

Проектировщик: «во время боя очень важно понимать, где находятся и как перемещаются союзники и враги».
Решения проектировщика: схема зон (не клетки); показывать в начале хода игрока и по /map.
K1. Карта — псевдографика ≤ 80 колонок: зоны — рамки с названием и пометками (▲N высота / ▼N ниже, «укр.½», «укр.¾»,
    «темно», «труднопрох.», «опасно», «выход»); переходы между соседними зонами — линии ─ │; в зоне — участники:
    «● Грей 18/25», «◆ Акела», «○ Бран» (спутник, без механики боя), «✕ Воин-гоблин 1 7/11» (враги; HP врагов — словом
    «ранен/тяжело ранен» если игрок не знает точных HP: показывать ровно то, что уже видно по логу — сейчас HP врагов
    в выводе есть, значит числа). Упавшие — «† …». Скрытый герой — «(скрыт)».
K2. Раскладка: по графу смежности, детерминированно — раскладка по слоям BFS от зоны героя на старте боя (слева направо),
    внутри слоя — по порядку зон; мастер может задать `pos: [ряд, колонка]` у зоны в start_combat (необязательно) — тогда
    берётся она. Схема фиксируется на весь бой (не прыгает между ходами).
K3. Перемещения с прошлого хода игрока: под картой строка «Движение: Воин-гоблин 2 Штольня → Уступ; Бран Вход → Штольня».
K4. Показ: перед меню хода игрока; команда /map в бою — карта сейчас; вне боя /map — «Сейчас не бой» (карта локаций — бэклог).
    Легенда — одной строкой под картой.
K5. Узкие места: если карта не помещается в 80 колонок (много зон) — переносить слои вниз; >8 зон — списком
    «Зона: кто» вместо рамок.
T. Тесты: раскладка детерминирована и стабильна весь бой; pos мастера учитывается; пометки высоты/укрытия/темноты; участники и
   значки; упавшие и скрытый; строка движений; ширина ≤ 80 на 2/4/6/8 зонах; >8 зон — список; /map вне боя.

## Итог: Живой прогон Дракона: «Метка охотника и атака зажигательной» → «Нет механики» (2026-10-04) (бывш. docs/decisions/stage3-live-mark-option.md)

Мир drunk_dragon-29a049dc, ход 5. Ввод: «метка охотника на гоблине лучнике и атака луком с зажигательной стрелой».
Журнал: в combat.options НЕТ ни одного cast:hunters_mark (и других бонусных заклинаний: Опутывающий удар), хотя бонусное
действие свободно, ячейки 2/3 и «Избранный враг» 2/2. Герой в зоне gallery_stairs (▲1), гоблины в lower_arch (через platform).
Классификатор отдал player_action только с атакой, Метку — в unsupported. Затем в режиме combat_narrate модель вызвала
unsupported_action «player_action не предоставлен» — игрок увидел «Нет механики».
B1. Найти, почему cast_options не даёт hunters_mark (castable_spells / cast_targets / дальность по зонам / Избранный враг без
    ячейки) — и исправить: Метка должна предлагаться на каждого видимого врага в пределах 90 фт (бонусное, с ячейкой и без
    ячейки по Избранному врагу — отдельными пунктами «(без ячейки, 2/2)»). То же для прочих бонусных заклинаний.
B2. В режиме combat_narrate инструмента unsupported_action нет (или он отбрасывается без вывода игроку): рассказчик боя не
    исполняет действия. Правила: в combat_narrate — только рассказ по логу.
B3. Если классификатор положил часть фразы в unsupported, а действие на самом деле есть в combat.options — это ошибка
    классификатора; правила combat_classify: сначала искать по options, включая бонусные заклинания.
T. Тесты: на позиции из журнала (герой ▲1, враги через зону) есть cast:hunters_mark на обоих гоблинов, бонусное; без ячеек,
   но с Избранным врагом — пункт «без ячейки»; набор combat_narrate без unsupported_action; классификация фразы
   «метка на X и атака зажигательной» мок-моделью → два шага.

### Причина и решение (оркестратор)
Дальность зон: range_band_ft даёт 10/30/120 фт (0 / 1 / ≥2 шага). Герой и гоблины через зону — 120 фт > 90 фт Метки.
Временно: для заклинаний (attack/darts/mark) 2 шага = 60 фт, оружие не менялось. Несоответствие оружия и заклинаний
по дальности — пересмотреть единым правилом дальности зон при аудите этапа 3 (BACKLOG).

## Итог: Живой прогон Дракона: «Метка охотника не держится» (2026-10-04) (бывш. docs/decisions/stage3-live-mark.md)

Журнал мира drunk_dragon-ee8aa926 (ходы 11, 13): метка снималась по правилам — Грей получал урон и проваливал
спасбросок концентрации Тел (d20 + 1 против СЛ 10). Но игроку это не видно: строка «концентрация Грей: Спасбросок Тел …»
непонятна, о снятии метки ничего не пишется; переноса метки на новую цель нет.
H1. Потеря концентрации — понятной строкой: «Концентрация (Спасбросок Тел): d20 (4) + 1 Тел = 5 vs СЛ 10 → провал» и
    «Грей теряет концентрацию — Метка охотника снята со Стражника с рожком». Удачный спасбросок — строкой «концентрация удержана».
H2. Перенос метки (SRD 5.2): если помеченная цель упала на 0 HP, а концентрация держится — бонусным действием пункт
    «Перенести Метку охотника → <цель>» без траты ячейки (в группе «Бонусное действие» нового меню).
H3. В заголовке хода и в /sheet: «Концентрация: Метка охотника → <цель>», пока держится.
T. Тесты: строки H1 (провал и успех); снятие эффекта с цели при провале; пункт переноса появляется только после падения
   помеченной цели и при живой концентрации, переносит эффект без расхода ячейки, тратит бонусное действие; H3.

## Итог: Живой прогон Дракона: сопротивление не видно в логе (2026-10-04) (бывш. docs/decisions/stage3-live-resist-line.md)

Проектировщик: «Рубящий/дробящий урон вдвое меньше — не получилось». Лог: «Урон (скимитар): 1d6 (1) + 2 = 3 рубящий» →
«Грей: HP 24/25» (было 25) — сопротивление сработало (3 // 2 = 1), но в логе об этом ни слова.
R1. Если итоговый урон отличается от брошенного (сопротивление / уязвимость / иммунитет / временные HP), под строкой урона —
    строка «Сопротивление (Каменная Кожа): 3 → 1 рубящий» / «Уязвимость (…): 4 → 8» / «Иммунитет (…): 5 → 0» /
    «Временные HP поглотили 2». Источник — имя эффекта/вида/черты. Для героя и для монстров, в бою и вне боя (damage).
T. Тесты: эликсир — строка сопротивления с источником и итогом; без сопротивления строки нет; временные HP; монстр с
   сопротивлением (тестовый контент); вне боя через damage.

## Итог: Живой прогон Дракона: расшифровка бонусов в строках бросков (2026-10-04) (бывш. docs/decisions/stage3-live-rolls.md)

Проектировщик: «непонятно, как складывается мой бонус — где мастерство, где Стрельба, где ловкость, просто какие-то +».
Решение оркестратора (формат — на подтверждение проектировщику по живому прогону):
R1. Бонус броска атаки/проверки/спасброска хранится как список слагаемых с подписью, а не одним числом
    (`RollRequest.bonus_parts: list[(label, value)]`, сумма = прежний `bonus`; прежнее поле остаётся для совместимости).
    Подписи: «Лов»/«Сил»/… (модификатор характеристики), «мастерство» (бонус мастерства), «Стрельба» (боевой стиль),
    «Мдр»… у заклинаний, «+1 оружие», «укрытие» и т.п.; нулевые слагаемые не печатаются.
R2. Строка атаки начинается с названия: «Атака (длинный лук): d20 (14) + 4 Лов + 2 мастерство + 2 Стрельба = 22 vs КД 13 → попадание».
    Модификаторы из пайплайна (благословение, молитва и т.п.) — тоже с подписью: «+ 1d4 (3) Благословение».
R3. Урон: «Урон (длинный лук): 1d8 (5) + 4 Лов = 9 колющий»; дополнительный урон — отдельной строкой со своим источником:
    «Метка охотника: 1d6 (3) силовой». Крит — «(крит, кубики ×2)».
R4. То же для проверок/спасбросков: «Выживание (Мдр): d20 (11) + 2 Мдр + 2 мастерство = 15 vs СЛ 12 → успех».
R5. Монстры: их бонус из статблока — одним слагаемым «бонус атаки» (раскладки в SRD нет).
T. Тесты: раскладка сумм = итог; подписи для героя (Грей: длинный лук, Стрельба, Метка охотника); монстр — одно слагаемое;
   нулевые не печатаются; ширина ≤ 80 с переносом; сценарные тесты, разбирающие строки бросков, — через plain_lines.

### Бюджет боя — видно игроку (проектировщик: «непонятно, как оценить»)
B1. При старте боя строка лога: «Бюджет боя: 225 ПО (ур. 3, умеренный); враги: 150 ПО (гоблин 50 ×3)».
B2. Если урезано: «Не вступили в бой (сверх бюджета): гоблин ×2» (и/или «(больше 6 врагов)»).
B3. Если бой сверх бюджета по основанию — вместо «основание hero» понятным текстом: «Бой сверх бюджета: напал ты /
    было предупреждение об опасности / сюжетная угроза / лидеры сильнее бюджета».

## Итог: Живой прогон Дракона: инвентарь по группам, заклинания и умения на виду (2026-10-04) (бывш. docs/decisions/stage3-live-sheet.md)

Проектировщик: «Инвентарь не сгруппирован… Плюс я не знаю, какие заклинания и умения у меня есть, чтобы их применять».
Сейчас: /inv — плоский список «имя xN»; /sheet — класс сырым id (ranger), без характеристик, навыков, умений, заклинаний,
ячеек. Группировку в ТЗ отдельно не планировали (панели — этап 5); делаем сейчас, текстом, ширина ≤ 80.
S1. /inv по группам (пустые не печатаются): «Оружие» (★ в руках), «Доспехи и одежда» (★ надето), «Боеприпасы»
    (особые стрелы с эффектом кратко), «Зелья и расходники» (эффект кратко: «+2 КД, сопр. … 1 ч»), «Снаряжение и инструменты»,
    «Ценности и прочее» (ключи, кольца, документы); в каждой — по имени; «Деньги: …» в конце.
    Группа определяется по типу контента (weapon/armor/ammo_for/эффекты использования) и, для прочего, по категории/тегу
    предмета; без категории — «Снаряжение и инструменты».
S2. /sheet: «Грей — человек, следопыт 3 ур. (Повелитель зверей), опыт N/следующий»; характеристики «Сил 12 (+1) · Лов 17 (+3) …»;
    бонус мастерства; спасброски с владением; навыки с бонусами (владеемые — ★, экспертиза — ★★); черты; боевой стиль;
    скорость; пассивная Внимательность; зверь-спутник (Акела: HP, КД) — если есть.
S3. Новая команда /spells (и раздел в /sheet коротко): ячейки «1 круг: ●●○ (2/3)»; заклинания по кругам — имя, время
    («действие / бонусное / реакция / 1 мин»), концентрация (К), дальность, одна строка сути; бесплатные применения
    («Метка охотника без ячейки: 2/2 до долгого отдыха»). Подсказка: «В бою — пункт меню; вне боя — скажи мастеру
    „читаю Лечение ран на себя“».
S4. Новая команда /abilities (умения): умения класса, подкласса, вида и черт — имя, когда работает (пассивно / действие /
    бонусное / реакция / раз за отдых), остаток ресурса, одна строка сути. Подсказка как в S3.
S5. /help — новые команды; описания берутся из данных контента (description), сокращаются до одной строки.
T. Тесты: группировка Грея (лук ★, рубаха ★, стрелы с эффектами, эликсир с эффектом, ключи/кольцо — в «ценности»); пустые
   группы не печатаются; /sheet — русские названия класса/вида/подкласса, характеристики с модами, навыки ★; /spells — ячейки,
   Метка охотника, бесплатные применения; /abilities — умения следопыта 1–3 и Повелителя зверей; ширина ≤ 80.

## Итог: Живой прогон Дракона: предметы вне боя (2026-10-04) (бывш. docs/decisions/stage3-live-use-item.md)

Проектировщик: «Каменная Кожа не работает до боя: выпил до начала боя, действие так и не началось».
Причина: у мастера нет запроса «использовать предмет» (было в бэклоге), вне боя эффект не применялся.
U1. Новый запрос нарратора `use_item{item_id, qty=1}` (explore; не strict): применяет эффект расходника по данным предмета
    (`rules/inventory.drink_item`: «Каменная Кожа» — ActiveEffect на 1 час по часам мира; зелье лечения — лечение по его данным),
    тратит предмет; нет предмета → Invalid `no_item`; предмет без эффекта использования → rejected «нечего применить».
    Лимит расходников за сцену (P16) — как у give_item для heal.
U2. Эффект, начатый вне боя, действует и в бою (тот же ActiveEffect; истечение по часам мира) — проверить.
U3. narrator_rules: когда игрок пьёт/применяет предмет из своего инвентаря — вызвать use_item (не просто описать).
U4. Строка в логе: «Грей: Эликсир «Каменная Кожа» — +2 КД, сопротивление рубящему и дробящему до ЧЧ:ММ».
T. Тесты: use_item эликсира вне боя → эффект, расход, /sheet КД 17; затем start_combat — КД 17 в бою, сопротивление работает;
   через час эффект снят; зелье лечения вне боя лечит; нет предмета → Invalid; лимит за сцену.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- Решения живых прогонов этапа 3: docs/plan-stage3.md.

## Приложение: П7: черновики ИИ для пака «Пьяный Дракон» (на утверждение проектировщику) (бывш. docs/decisions/stage3-p7-drafts.md)

Решение 4а (grooming): мотивы, триггеры, opportunity NPC и фракций, pleased_by/angered_by/rivals
богов -- черновик ИИ, проектировщик правит. В паке `campaigns/drunk_dragon/` каждое такое поле
помечено комментарием `# draft`. Файл собран из `devtools/dragon_drafts.yaml` (тот же источник,
что у конвертера `devtools/import_dragon.py`). Правка -- в YAML пака руками (и в
`dragon_drafts.yaml`, если конвертер будет запускаться снова).

Всего черновых полей: 50.

Не draft (утверждено): шкалы тона (3а, G6) и всё, что перенесено из источника как есть.
Не заполнено намеренно: `servants` богов (слуг-охотников в источнике нет), `means` богов,
новые `key: true` (10 ключевых NPC источника остаются как есть, решение Q1).
Ссылки на источник: `ch1` = `saves/drunk_dragon/_import/source/chapter1_gemini_web.txt`,
`ch2` = `chapter2_agy.txt` (число после двоеточия -- номер строки); `world.json`, `session.json` --
`saves/drunk_dragon/slots/manual-import/`.

### NPC

#### ethan

- **motive**
  ```yaml
  motive: Выследить и выбить гончих Топкого болота, чтобы деревне было безопасно
  ```
  Почему: Мотива в источнике нет. Итан -- охотник, сын Ольгерда, погиб у логова гончих; мотив выведен из роли.
  Источник: world.json npcs.ethan.relations_text; ch1 -- сюжет Ольгерда и Итана (Чёртов Затон)

#### bloodfang

- **motive**
  ```yaml
  motive: Охранять логово у Чёртова Затона и кормить стаю
  ```
  Почему: Мотива в источнике нет. Вожак (альфа) болотных гончих; мотив выведен из роли.
  Источник: world.json npcs.bloodfang.means

#### second_hierarch

- **motive**
  ```yaml
  motive: Доставить синий кристалл Ордена на Гадючий Остров и дальше по цепочке культа
  ```
  Почему: Мотива в источнике нет. Ритуалист вёл обоз с синим кристаллом (Ключом); мотив выведен из этого.
  Источник: world.json npcs.second_hierarch.means; ch1 -- обоз на Гадючьем Острове

#### third_hierarch

- **motive**
  ```yaml
  motive: Хранить Второе Святилище и архив Ордена на Мёртвом Кургане
  ```
  Почему: Мотива в источнике нет. Хранитель Второго Святилища; архив, которым культ шантажировал Варена, лежал там же.
  Источник: world.json npcs.third_hierarch.means; memory.json chapters.ch1 (Мёртвый Курган)

#### warlock_viper

- **motive**
  ```yaml
  motive: Удержать заслон на Гадючьем Острове и не пропустить чужих к обозу
  ```
  Почему: Мотива в источнике нет. Командир заслона на Гадючьем Острове; мотив выведен из роли.
  Источник: world.json npcs.warlock_viper.means; locations.viper_island

#### abbey_tracker

- **motive**
  ```yaml
  motive: Выследить чужаков гончими и защитить Аббатство
  ```
  Почему: Мотива в источнике нет. Командир загонщиков с гончими; мотив выведен из роли.
  Источник: world.json npcs.abbey_tracker.means

#### abbey_captain

- **motive**
  ```yaml
  motive: Удержать Аббатство Алого Тумана, пока Иерарх ведёт ритуал
  ```
  Почему: Мотива в источнике нет. Командир гарнизона Аббатства; Верховный Иерарх вёл в нём ритуал.
  Источник: world.json npcs.abbey_captain.means, npcs.supreme_hierarch.means

#### plague_brute

- **motive**
  ```yaml
  motive: Охранять пленных в казематах Ратуши по воле Братства Мора
  ```
  Почему: Мотива в источнике нет. Мутировавший старший тюремщик; мотив выведен из роли (тюремщик).
  Источник: world.json npcs.plague_brute.means; ch2 -- бой в Ратуше

#### sickle_executioner

- **motive**
  ```yaml
  motive: Освободить Ольбрехта и посеять панику в Ратуше
  ```
  Почему: Мотива в источнике нет. Культист в костяной маске среди диверсантов, освободивших Ольбрехта в Ратуше.
  Источник: IMPORT_NOTES, противоречие «Ольбрехт» (шаги 126-130); world.json npcs.sickle_executioner

#### nazir

- **opportunity**
  ```yaml
  opportunity:
  - id: ritual_at_dawn
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
    then: Начинает ритуал у саркофага над трещиной -- вскрыть Могильник кровавой жертвой и пробудить Мор-Владыку
    once: true
    key: true
  - id: answers_black_spring_alarm
    if:
      flag: alarm_raised_at_black_spring
    then: Узнав о налёте у Чёрного Истока, усиливает охрану верхнего яруса и ждёт у алтаря
    once: true
  ```
  Почему: Основная линия главы II: ритуал на рассвете (срок -- по событию nazir_ritual). Условие структурное: время + Назир жив. Второй триггер -- на флаг тревоги, который сейчас false (тревога культу не поднята).
  Источник: world.json events.nazir_ritual (ends_at_s); session.json current_scene.deadlines; ch2:938 (записка Назира «Владыка просыпается»); ch2:1807 (ритуал на рассвете)

#### mor_lord

- **opportunity**
  ```yaml
  opportunity:
  - id: awakens
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Кровавая жертва принесена у саркофага в Древнем Могильнике
    then: Печати Могильника трескаются -- Мор-Владыка просыпается
    once: true
    key: true
  ```
  Почему: Пробуждение Мор-Владыки -- цель Назира. Структурная часть (срок, Назир жив) отсекает лишние вызовы world; нарративная часть -- факт жертвы.
  Источник: world.json events.mor_lord_awakening; ch2:938; npcs.mor_lord.motive

#### captain_of_guard

- **opportunity**
  ```yaml
  opportunity:
  - id: advance_on_forge
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
    then: Не дождавшись вестей от Грея, выводит заслон из предгорных деревень к Кузнице Пепла
    once: true
  ```
  Почему: Мотив -- защитить город и деревни; заслон стоит в предгорьях (сотня-две стражи и ополчения). Если на рассвете Назир жив, Капитан действует сам -- по плану «Щит и Клинок».
  Источник: flags.war_council_plan; npcs.captain_of_guard.relations_text; IMPORT_NOTES, противоречие «Силы Капитана»

#### bran_sedogriv

- **opportunity**
  ```yaml
  opportunity:
  - id: kills_edrin_if_betrays
    if:
      all:
      - flag: edrin_joined_as_guide
      - narrative: Эдрин предаёт отряд или пытается предупредить часовых
    then: Бран без колебаний убивает Эдрина (месть за перебитых егерей Ложи)
    once: true
  ```
  Почему: Мотив Брана -- не дать пробудить Мор-Владыку и отомстить за егерей. Бран не доверяет культисту; триггер срабатывает только при предательстве Эдрина.
  Источник: npcs.bran_sedogriv.motive; ch2:480 (Бран о перебитых егерях); ch2:1975 (условие Грея для Эдрина)

#### edrin

- **opportunity**
  ```yaml
  opportunity:
  - id: changes_mind
    if:
      all:
      - flag: edrin_joined_as_guide
      - narrative: Эдрин говорит вслух, что передумал
    then: Остаётся у подножия и не идёт к шахте -- Грей обещал не принуждать
    once: true
    key: true
  ```
  Почему: Грей поставил условие: если Эдрин передумает -- сказать вслух. Триггер на это условие; Эдрин -- ключевой проводник к Восточной шахте.
  Источник: ch2:1975 («скажи мне вслух. Просто скажи»); ch2:1912 (Эдрин обещает провести к шахте); flags.edrin_joined_as_guide

#### milo

- **opportunity**
  ```yaml
  opportunity:
  - id: waits_in_ratusha
    if:
      npc_status:
        id: nazir
        is: dead
    then: Мило встречает Грея в Ратуше; Капитан пристраивает его учеником в гильдию оружейников, как обещал
    once: true
  ```
  Почему: Мотив -- верность Грею. Капитан обещал пристроить Мило в гильдию оружейников после похода; триггер -- победа над Назиром.
  Источник: ch2:1032 (Мило в гильдию оружейников); npcs.milo.relations_text

#### father_mark

- **opportunity**
  ```yaml
  opportunity:
  - id: reads_folio_with_hero
    if:
      all:
      - hero_at: sanctuary_of_dawn
      - flag: abyss_keys_folio_stored_with_father_mark
    then: Предлагает вскрыть печать на фолианте «Ключи Бездны» вместе с героем -- в нём могут быть сведения о печатях Могильника
    once: true
  ```
  Почему: Мотив -- противостоять тьме Бездны. Фолиант лежит у него под печатью, герой в Святилище -- повод вернуться к нему. Содержимое фолианта в источнике не раскрыто -- это допущение.
  Источник: ch1:1039 (отец Марк о фолианте); ch1:1071 (запечатал ларец); flags.abyss_keys_folio_stored_with_father_mark

#### varen

- **opportunity**
  ```yaml
  opportunity:
  - id: bargains_in_casemates
    if:
      all:
      - hero_at: city_ratusha
      - flag: varen_in_casemates
    then: Торгуется -- за смягчение приговора выдаёт всё, что знает о Магистре Второго Круга
    once: true
  ```
  Почему: Мотив Варена -- власть и заметание следов. Он в казематах и «раскололся», но личность Магистра не раскрыта (секрет magister_secret_1). Триггер даёт повод её раскрыть.
  Источник: ch2:224 (допросы Варена и Ольбрехта); ch1:858 (записка о Магистре); npcs.magister.secrets

### Фракции

#### broken_key_brotherhood

- **opportunity**
  ```yaml
  opportunity:
  - id: goes_underground
    if:
      npc_status:
        id: nazir
        is: dead
    then: Остатки Братства уходят в подполье; Магистр Второго Круга берёт руководство и ищет новые Ключи
    once: true
  ```
  Почему: Магистр в источнике -- глава ордена с мотивом «закончить ритуал»; без Назира Братство не исчезает. «Ищет новые Ключи» -- допущение.
  Источник: ch1:858, ch1:1039 (Магистр); world.json npcs.magister.motive

#### lodge_north_wind

- **opportunity**
  ```yaml
  opportunity:
  - id: returns_to_city
    if:
      all:
      - npc_status:
          id: olbrecht
          is: dead
      - npc_status:
          id: nazir
          is: dead
    then: Ложа открыто возвращается в Город; указ о «диких бандах» отменён Советом
    once: true
  ```
  Почему: Ложа объявлена браконьерами по указу Ольбрехта. Ольбрехт мёртв; после победы над Назиром у Ложи нет причин скрываться.
  Источник: ch2:480 (указ Ольбрехта о «диких бандах»); world.json factions.lodge_north_wind.motive

#### city_guard

- **opportunity**
  ```yaml
  opportunity:
  - id: intercepts_raiders
    if:
      all:
      - event_active: harvest_raids
      - flag: captain_screens_villages
    then: Заслон перехватывает рейдовые группы орков и сопровождает жителей деревень в город
    once: true
  ```
  Почему: Заслон Капитана для того и поставлен: событие harvest_raids заканчивается, когда заслон перехватывает рейды.
  Источник: world.json events.harvest_raids.ends_when; flags.captain_screens_villages, signal_fires_lit

#### city_council_conspiracy

- **opportunity**
  ```yaml
  opportunity:
  - id: silences_varen
    if:
      all:
      - flag: varen_in_casemates
      - npc_status:
          id: olbrecht
          is: dead
    then: Уцелевшие заговорщики пытаются освободить Варена или заставить его замолчать
    once: true
  ```
  Почему: Варен в казематах, Ольбрехт мёртв. Диверсанты уже освобождали Ольбрехта из казематов Ратуши -- такой ход Совета в духе источника.
  Источник: IMPORT_NOTES, противоречие «Ольбрехт» (шаги 126-130); flags.varen_in_casemates

#### nazir_orcs

- **opportunity**
  ```yaml
  opportunity:
  - id: doubles_watch
    if:
      flag: alarm_raised_at_black_spring
    then: Орки удваивают караулы у вентиляционных шахт и отменяют «мёртвое окно» смены часовых
    once: true
  ```
  Почему: Сейчас тревога не поднята (флаг false), и отряд рассчитывает на смену часовых. Если её поднять, орки реагируют.
  Источник: session.json current_scene.enemies_known.schedule; flags.alarm_raised_at_black_spring

#### chernolesye_village

- **opportunity**
  ```yaml
  opportunity:
  - id: bars_the_gates
    if:
      event_active: harvest_raids
    then: Деревня запирает ворота, ополчение встаёт на частокол, староста Тобин просит помощи у Города
    once: true
  ```
  Почему: Мотив -- выжить у болот. Набеги за жертвами идут на деревни предгорий (событие harvest_raids). Чернолесье -- деревня за частоколом с ополчением.
  Источник: world.json events.harvest_raids; factions.chernolesye_village.means; npcs.tobin.means

### Боги

#### selune

- **motive**
  ```yaml
  motive: 'Каждая живая душа священна; её сила -- в живом и цветущем: чем больше жизни в её землях, тем она сильнее'
  ```
  Почему: Текст проектировщика (корыстный мотив: покровительство жизни, сила растёт с жизнью).
  Источник: docs/plan-stage3.md, «Мотивы богов»
- **pleased_by**
  ```yaml
  pleased_by:
  - спасённая жизнь
  - рождение
  - исцеление
  - посеянное и выращенное
  - цветущая земля
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **angered_by**
  ```yaml
  angered_by:
  - напрасная смерть
  - нежить
  - Мор
  - убийство сдавшихся
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **rivals**
  ```yaml
  rivals:
  - shar
  - abyss_demon
  ```
  Почему: Текст проектировщика: соперники Шар и демон Бездны (Мор -- порождение культа демона).
  Источник: docs/plan-stage3.md; ch1:160 (Шар -- враг Селунэ)
- **season_power**
  ```yaml
  season_power:
    весна: 15
    лето: 25
    осень: -15
    зима: -25
  ```
  Почему: S1: с весной силы Селунэ возрастают, с осенью убывают. Поправка к шансу божественного вмешательства в процентных пунктах. Числа -- на утверждение проектировщику. Лето +25 (решение проектировщика), сейчас осень (-15).
  Источник: docs/plan-stage3.md, «S1»; имена сезонов -- стандартный календарь (зима, весна, лето, осень)
- **opportunity**
  ```yaml
  opportunity:
  - id: omen_for_the_living
    if:
      all:
      - not:
          flag: selune_owl_omen_seen
      - npc_status:
          id: edrin
          is: alive
      - hero_at: east_shaft
    then: Посылает отряду знамение (белая сова) -- её взгляд на тех, кто идёт спасать живых
    once: true
  - id: weakens_as_mor_spreads
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Мор разошёлся по долине и губит живое
    then: Сила Селунэ в этих землях тает -- знамения слабеют, молитвы доходят хуже
    once: true
  ```
  Почему: Мотив Селунэ -- жизнь в её землях. Первый триггер -- знамение у шахты, пока знамения ещё не было (условие «не было», решение проектировщика; Эдрин жив -- повод для её внимания). Второй -- Мор отнимает жизнь: структурная часть (срок ритуала, Назир жив) отсекает лишние вызовы world, нарратив -- сам факт распространения Мора.
  Источник: ch2:1874-1890 (белая сова); ch2:1983; world.json events.nazir_ritual

#### lathander

- **motive**
  ```yaml
  motive: Всё новое должно начинаться под его именем -- храмы, клятвы, первые шаги -- его слава
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **pleased_by**
  ```yaml
  pleased_by:
  - дела, начатые с его именем
  - восстановленные святилища
  - уничтоженная нежить (оскорбляет рассвет)
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **angered_by**
  ```yaml
  angered_by:
  - благословение без благодарности
  - брошенные начинания
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **opportunity**
  ```yaml
  opportunity:
  - id: demands_thanks
    if:
      all:
      - hero_at: sanctuary_of_dawn
      - flag: lathander_blessing_used
    then: Через отца Марка напоминает герою о благодарности за Благословение -- новое начинание под его именем, тогда благословение возобновится
    once: false
    cooldown: 7d
  ```
  Почему: Мотив -- слава начинаний. Благословение в главе I использовано (флаг); без благодарности Латандр сердится (angered_by). Структурные условия, срок 7d -- допущение.
  Источник: ch1:1085; flags.lathander_blessing_used; docs/plan-stage3.md

#### shar

- **motive**
  ```yaml
  motive: Питается утратами и забытым; хочет, чтобы её боялись и почитали тайно, а свет Селунэ погас
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **pleased_by**
  ```yaml
  pleased_by:
  - предательство
  - утрата
  - забытые имена
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **angered_by**
  ```yaml
  angered_by:
  - возвращённая память
  - знаки Селунэ
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **rivals**
  ```yaml
  rivals:
  - selune
  ```
  Почему: Взаимно с Селунэ: источник называет Шар её врагом.
  Источник: ch1:160
- **opportunity**
  ```yaml
  opportunity:
  - id: feeds_on_loss
    if:
      npc_status:
        id: milo
        is: dead
    then: Шепчет Грею в час утраты -- толкает к отчаянию и тайному поклонению Шар
    once: true
  ```
  Почему: Мотив -- питаться утратами. Самая личная утрата Грея в источнике -- Мило (дважды спасён, молится Селунэ, враг Шар). Мило жив, триггер спящий. Слабый черновик: у Шар в источнике нет действий.
  Источник: ch1:160; world.json npcs.milo; docs/plan-stage3.md

#### faceless

- **motive**
  ```yaml
  motive: 'Копит секреты: каждое скрытое знание -- его сила'
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **pleased_by**
  ```yaml
  pleased_by:
  - хранимая тайна
  - сделка в тени
  - украденное знание
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **angered_by**
  ```yaml
  angered_by:
  - раскрытые тайны и имена его служителей
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **opportunity**
  ```yaml
  opportunity:
  - id: wants_the_folio
    if:
      all:
      - hero_at: dead_barrow
      - flag: abyss_keys_folio_stored_with_father_mark
    then: Предлагает герою сделку в тени -- тайна за тайну; его интересует фолиант «Ключи Бездны»
    once: true
  ```
  Почему: Мотив -- копить секреты. Самое ценное скрытое знание в источнике -- фолиант «Ключи Бездны», спрятанный у отца Марка; часовня Безликого стоит на Мёртвом Кургане. Слабый черновик.
  Источник: ch1:4674 (часовня Безликого); ch1:1039, ch1:1071 (фолиант); docs/plan-stage3.md

#### ilmater

- **motive**
  ```yaml
  motive: Набирает силу от тех, кто принимает чужую боль; ему нужны мученики
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **pleased_by**
  ```yaml
  pleased_by:
  - стойкость в страдании
  - боль, взятая за другого
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **angered_by**
  ```yaml
  angered_by:
  - спасение себя ценой чужой боли
  - лёгкие пути
  ```
  Почему: Текст проектировщика.
  Источник: docs/plan-stage3.md
- **opportunity**
  ```yaml
  opportunity:
  - id: seeks_a_martyr
    if:
      all:
      - flag: edrin_joined_as_guide
      - hero_at: east_shaft
    then: Обращает внимание на того, кто готов взять удар за других -- знамение стойкости для героя или Эдрина
    once: true
  ```
  Почему: Мотив -- мученики. Эдрин идёт искупать вину и рискует собой у шахты -- ближайший кандидат в источнике. Слабый черновик: Ильматер упомянут один раз.
  Источник: ch2:428; ch2:1912 (Эдрин обещает провести к шахте); docs/plan-stage3.md

#### abyss_demon

- **motive**
  ```yaml
  motive: Прорваться в мир через Врата Бездны, которые открывает Орден Разбитого Ключа
  ```
  Почему: Источник: культ поклоняется высшему демону Бездны и ищет печати; мотив бога выведен из цели культа. Связь с Мор-Владыкой не подтверждена.
  Источник: ch1:1029 (слова отца Марка); world.json gods.abyss_demon.role
- **pleased_by**
  ```yaml
  pleased_by:
  - вскрытие печатей и Врат
  - кровавые жертвы
  - служение Братству Мора
  ```
  Почему: Выведено из целей и обрядов культа.
  Источник: ch1:1029; world.json factions.broken_key_brotherhood.motive
- **angered_by**
  ```yaml
  angered_by:
  - уничтожение Кристаллов-Ключей
  - запечатывание Врат и Могильника
  - убийство иерархов Ордена
  ```
  Почему: Выведено из того, что Грей уже сделал: все три Кристалла уничтожены, иерархи убиты.
  Источник: flags.all_crystals_destroyed, abbey_hierarch_dead, second_hierarch_dead, third_hierarch_dead
- **opportunity**
  ```yaml
  opportunity:
  - id: answers_awakening
    if:
      all:
      - time_after: 23781600
      - npc_status:
          id: nazir
          is: alive
      - narrative: Мор-Владыка пробуждается
    then: Откликается на пробуждение Мор-Владыки и тянется к Вратам Бездны
    once: true
  ```
  Почему: Связь демона с Мор-Владыкой источник не подтверждает (role: «возможно связан»). Слабый черновик: структурное условие то же, что у Назира.
  Источник: world.json gods.abyss_demon.role; ch1:1029

### Герои (решения проектировщика)

#### grey

- **level**
  ```yaml
  level: 3
  ```
  Почему: Решение проектировщика: Грей начинает на 3 ур., Повелитель зверей.
  Источник: docs/plan-stage3.md (решение «Грей: уровень 3»); docs/plan-ranger-2-5.md, решения
- **xp**
  ```yaml
  xp: 900
  ```
  Почему: Опыт 3 ур. по таблице (xp.yaml).
  Источник: srd/data/tables/xp.yaml
- **level_choices**
  ```yaml
  level_choices:
  - level: 2
    fighting_style: archery
    expertise:
    - survival
    languages:
    - celestial
    - gnomish
  - level: 3
    subclass_id: beast_master
    spells_add:
    - cure_wounds
    - ensnaring_strike
    - speak_with_animals
    - fog_cloud
  ```
  Почему: Решения проектировщика 2-4: стиль «Стрельба», экспертиза в Выживании, Повелитель зверей, 4 заклинания 1 круга (Метка охотника подготовлена всегда). Языки (2) -- Великаний и Гномий (рекомендация папы-кабана, пункт В4).
  Источник: docs/plan-ranger-2-5.md, разд. 8 (В2-В4) и решения проектировщика
- **companion**
  ```yaml
  companion:
    name: Акела
    kind: волк
    notes: Серый волк; перед походом его доверил Грею Йорген-зверолов. Идёт по следу, чует ветер, сторожит стоянку; в бою пока не участвует.
  ```
  Почему: Решение проектировщика 1: зверь Грея -- волк Акела, введён через Йоргена-зверолова, прошлые сцены не переписываются.
  Источник: docs/plan-ranger-2-5.md, В1 и решение 1

### Отчёт конвертера (не draft, правит проектировщик)

- Локации «Предгорья Кряжа» и «Серый Квартал» добавлены конвертером (решение Q3); на них
  ссылаются регионы `harvest_raids` и `city_council_conspiracy`.
- Мотив Грея взят из решения проектировщика (Q2), а не из `hero.json`; средства героя не перенесены.
