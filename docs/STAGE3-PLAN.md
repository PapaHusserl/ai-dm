# План этапа 3: паки кампаний, ход мира, сцены и главы, боги, бюджет боя

Автор: папа-кабан. Статус: **на аппруве проектировщика**. Основа: TZ.md (2.0, 2.1, 2.3, 3, 4 целиком, 4.2, 5.3, 11, 13),
`decisions/stage3-grooming.md` (решения 1в 2б 3а 4а 5а 6а 7), ARCHITECTURE.md (части A–C, часть D — этот этап), BACKLOG.md,
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
`campaigns/drunk_dragon/`), `campaigns/drunk_dragon/*`, `docs/decisions/stage3-dragon-pack.md` (что утверждено),
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
окружении или `.env`. Результат — `docs/decisions/stage3-acceptance.md`.

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
