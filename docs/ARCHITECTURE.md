# Архитектура AI-DM и план этапа 1

Автор: папа-кабан (архитектор). Основа: `docs/TZ.md` v3. Статус: принят («окей, кабаним»). Уточнения по ходу — в docs/plan-*.md.

# ЧАСТЬ A. Архитектура проекта

## A1. Слои и направление зависимостей

Пакет `ai_dm` (src-layout). Зависимости только сверху вниз:

```
ui ──> game ──> master ──> llm
         │        └──────> protocol
         ├──> protocol ──> [ДВИЖОК]
         ├──> world_sim ─> [ДВИЖОК]
         ├──> campaign ──> [ДВИЖОК]
         ├──> reports
         └──> persistence ─> state
[ДВИЖОК] = combat -> rules -> state -> content -> core     (+ config)
```

| Пакет | Ответственность | Этап |
|---|---|---|
| `core` | RNG, кубики, игровые часы/календарь, длительности, id, доменные события, ошибки. Ни от чего не зависит. | 1 |
| `config` | `RulesConfig`/`AppConfig` (Pydantic) из `defaults.toml` в пакете + пользовательский `~/.config/ai-dm/config.toml` (stdlib `tomllib`; только app-секции из `app_defaults.toml`, rules-секции `defaults.toml` в нём отвергаются). Все «в конфиге» из ТЗ — здесь. | 1 (rules), 2 (app) |
| `content` | Pydantic-схемы контента (класс, подкласс, вид/раса, предыстория, черта, умение, оружие, доспех, предмет, заклинание, монстр, состояние), загрузчик YAML, реестр по id с наложением слоёв, реестр именованных обработчиков. | 1 |
| `srd` | Данные SRD 5.2 в YAML (package data). | 1 (минимум), далее трек контента |
| `state` | Модели runtime-состояния: герой, существо, NPC, фракция, бог, локация, триггеры, мир, бой, сессия, сейв-бандл. Только данные, без логики. | 1 |
| `rules` | Чистая механика: производные, сборщик/валидатор персонажа, конвейер бросков с модификаторами/перебросами, проверки/спасброски, урон/лечение, состояния, death saves, истощение, отдых, инвентарь, опыт, вычисление триггеров, страж причин смерти 4.1, время. | 1 |
| `combat` | Бой на зонах: валидация старта, инициатива, экономия хода, действия, дистанции, площади, мастерство оружия, провоцированные атаки, контроллеры участников, список доступных действий, 0 HP/намерения, последствия поражения, конец боя. | 1 |
| `persistence` | Раскладка сейва, атомарная запись, слоты, версия схемы, миграции, бэкапы; позже журнал вызовов модели. | 1 / 2 |
| `protocol` | Pydantic-модели запросов мастера (2.1), валидация, урезание/отклонение, перевод в вызовы движка, сигналы мастеру, метки авто-репортов. | 2 |
| `llm` | `ModelAdapter`, адаптеры Anthropic/Gemini/OpenAI (Responses API)/Mock, повторы, учёт токенов и стоимости. | 2 / 10 |
| `master` | Роли narrator/world/summarizer, сборка промпта, кэшируемый префикс, бюджет контекста, память. | 2 / 4 |
| `world_sim` | Ход мира: сцены/главы, проверка триггеров на границе сцены, смертность, старость, события, благосклонность, подталкивание, скачок времени. | 3 / 9 |
| `campaign` | Загрузка пака, проверка уникальности, догрузка новых сущностей в идущий мир. | 3 |
| `game` | Сессия/игровой цикл, атомарный ход, служебные команды. | 2 |
| `ui` | Простой построчный режим (2) и Textual TUI (5). | 2 / 5 |
| `reports` | Ищью-репорты, режим воспроизведения. | 6 |

**Граница «движок ↔ мастер»** — пакет `protocol`.
- Движок (`core…combat`, структурная часть `world_sim`) не импортирует `llm`/`master`/`protocol`
  (тест-сторож: обход импортов через `ast`).
- Мастер общается с движком только через `MasterRequest`, ответ —
  `Decision {status: accepted|clamped|rejected, reason, signal_to_master?, report_tag?}`.
- Все точки выбора (действие героя, ключевого NPC, переброс по вдохновению, «враг передумал») —
  через единый интерфейс `Controller` / `DecisionProvider`:
  - этап 1: `ScriptedController` (тесты), `EngineTactics` (рядовые враги);
  - этап 2: `PlayerController`, `MasterChoiceController` (`npc_action` выбирает из `available_actions`) — без изменения ядра.

**Атомарность хода (2.2):** `game` выполняет ход на `state.model_copy(deep=True)`, commit при успехе.
Функции движка мутируют переданное состояние и возвращают список доменных событий.

**Детерминизм — правила кода движка:** нет `random`, `time.time()`, `hash()` строк, обхода `set`;
коллекции — в порядке вставки или по id; время — целые секунды, float в состоянии нет.

## A2. Ключевые модели (Pydantic, верхний уровень)

`ConfigDict(extra="forbid")` для сейва и контента. Id — lowercase `\w` (SRD латиница, в паках допустима
кириллица). Деньги — целые медяки.

- **`CreatureState`** (общая часть героя / NPC в бою / монстра): `hp_current`, `hp_max`, `hp_temp`,
  `conditions`, `exhaustion`, `active_effects` (`id, source, kind, params, expires`), `death_saves`,
  `resources: dict[str, ResourcePool]` (кости хитов — `hit_dice:d{N}`, ячейки договора — `pact_slot`),
  `concentration: Concentration | None` (`spell_id`, `circle`, `until_s` -- конец концентрации по часам мира, `None` = бессрочно), `temp_form: TempForm | None`.
- **`HeroState`**: `id`, `ordinal`, `name`, `status: active|dead|retired|in_afterlife|ascended`, `fate`,
  `death`, `sheet: CharacterSheet` (вид, `classes: list[ClassLevel]` + `level_history`, `BackgroundSpec` 5.2,
  характеристики, владения, черты, мастерства, `spells_known`/`spells_prepared` по class_id,
  `spells_always_prepared: list[GrantedSpell]`, `feature_choices`, опыт; `class_id`/`level`/`subclass_id` — свойства
  чтения), `creature`, `companions`, `attuned`, `pending_level: PendingLevel | None`, `inventory`, `equipped`, `money_cp`,
  `motive`/`means`/`opportunity`, `favor`, `scars`, `heroic_inspiration`, `location_id`,
  `afterlife` (поле есть с этапа 1), `legacy_links`.
- **`NPC`**: `id`, `name`, `named`, `key`, `status`, `death`, `motive`, `means[1..3]`, `opportunity`,
  `attitude (−100..100)`, `known_to_player`, `secrets`, `combat`, `creature`, `location_id`,
  `species_id`, `birth_date`, `favor`, `relations_text`, `origin: pack|ai|engine`, `equipment: Equipment | None`
  (`None` — по статблоку).
- **`Faction`**: мотив/средства/возможность + `members`, `regions`.
- **`God`**: `id`, `name`, `domains`, `role`, `motive`, `pleased_by`, `angered_by`, `rivals`, `means`,
  `opportunity`, `realm`, `status`, `origin: pack|ascended`. Пантеон — в мире, изменяем.
- **`Location`**: `id`, `name`, `parent_id`, `description`, `tags`, `connections: list[Connection]`,
  `visited`, `origin`. `Connection {to, distance_m: int}` — метры, как в `travel_seconds`.
- **`Trigger`**: `id`, `if_` (alias `if`), `then`, `once`, `cooldown`, `key`, `state`, `fired_count`,
  `last_fired_at`. `Condition` — discriminated union: `All/Any/Not`, `Flag`, `HeroHas`, `NpcStatus`,
  `HeroAt`, `NpcAt`, `TimeAfter`, `Attitude`, `Favor`, `EventActive`, `HeroDead`, `Narrative`.
  Короткая запись `{hero_has: x}` разворачивается в `model_validator(mode="before")`.
  `Secret`: `id`, `text`, `reveal_if`, `revealed`.
- **`WorldState`**: `world_id`, `campaign_id`, `campaign_version`, `clock {now_s, calendar}`, `npcs`,
  `factions`, `pantheon`, `locations`, `flags`, `events` (`GlobalEvent`), `tone`, `settings`, `rng`.
  Отдельные файлы: `chronicle`, `memory` (`scenes`, `chapters`, `game_summary`, `recent_turns`).
- **`SessionState`**: `current_scene: dict | None`, `current_chapter: dict | None` (типизация — этапы 2–3),
  `active_combat: CombatState | None`, `pending_decision: DecisionPoint | None`.
- **`CombatState`**: `id`, `zones: list[Zone]` (`id, name, adjacent, features: list[ZoneFeature], exit`),
  `participants: list[Participant]`, `groups: dict[str, Group]` (`leader_id, intent, lair_location_id?`), `round`,
  `turn_index`, `initiative_order`, `budget_override_reason`,
  `outcome: None|victory|defeat_pending|hero_dying|hero_dead|fled|ended_by_master`, `log: list[str]`,
  `defeat_group_id` (группа последнего удара по герою), `savage_used: list[str]` (герои, уже использовавшие
  Savage Attacker в этом ходу).
- **`Participant`**: `ref`, `side: heroes|enemies`, `group_id`, `zone_id`, `initiative`, `turn: TurnState`
  (`action, bonus, reaction, move, disengaged`), `controller: engine|auto_hero|external`,
  `status: active|down|dead|fled`, `monster_id`, `intent`, `surprised`, `last_hit_by`, `name`,
  `equipment: Equipment | None`, `creature: CreatureState | None` — состояние безымянного монстра (герой и именованный NPC хранят своё в
  `heroes` / `world.npcs`, у них `creature = None`).
- **`DecisionPoint`**: `kind: turn_action|intent_reconsider`, `actor`, `options: list[str]`, `subject?`, `attacker?`.
- **`SaveBundle`**: `manifest` (`schema_version`, `engine_version`, `world_id`, `campaign_id`, `slot`,
  `saved_at`, `current_hero_id`, `heroes[]`), `world`, `chronicle`, `memory`, `heroes`, `session`.
- **Запросы мастера (этап 2)**: `MasterTurn {narration, requests: list[MasterRequest]}`, union по `type`,
  по модели на каждый запрос 2.1. Ответ — `Decision`.

### Контракт доменных событий

`DomainEvent {type: str, data: dict[str, int | str | bool | None]}` (`core/events.py`). Функции движка
возвращают списки событий; `rules/auto_flags.apply_events` ставит по ним флаги мира. События, которые
реально шлёт код этапа 1:

| `type` | `data` | Источник | Флаг |
|---|---|---|---|
| `creature_removed` | `id, status, cause, by` | `rules/mortality_guard` (герой и NPC) | нет |
| `hero_died` | `id, cause, by` | `mortality_guard`, `combat/downed` | `hero_dead:<id>` |
| `npc_died` | `id, cause, by` | `mortality_guard.remove_creature` | `npc_dead:<id>` |
| `monster_died` | `id, monster_id, by` | `combat/downed` (безымянный монстр) | нет |
| `secret_revealed` | `npc, secret` | `rules/secrets` | нет |
| `combat_ended` | `id` | `combat/end` | `combat_ended:<id>` |
| `location_visited` | `id` | `combat/defeat` (плен) | `visited:<id>` |
| `defeat_applied` | `consequence` | `combat/defeat` | нет |
| `turn_started` | `round, id` | `combat/engine` | нет |
| `attack` | `attacker, target, weapon, mode, outcome, damage` | `combat/actions/attack` | нет |
| `death_save` | `id, result` | `combat/downed` | нет |
| `participant_fled` | `id` | `combat/actions/standard` | нет |

`item_gained {hero, item}` (флаг `item_gained:<item>`) в таблице флагов `auto_flags` есть, но движок этапа 1
его не шлёт: источник — выдача предметов мастером (этап 2).

## A3. Хранение: JSON, не SQLite

Сейв — каталог JSON (`model_dump_json(indent=2)`). Обоснование: один агрегат целиком в памяти,
снимок на границе сцены, запросов нет; человекочитаемо (репорты, диффы); Pydantic нативно;
миграция = `dict -> dict`; слот = копия каталога. `memory`/`chronicle` — отдельные файлы; журнал
модели (этап 2) — JSONL с ротацией/gzip. К SQLite вернуться, если снимок мира — десятки МБ.

```
saves/<world_id>/
  slots/<slot>/            # auto, auto-1..N (ротация), manual-<имя>
    manifest.json          # schema_version, метаданные; пишется последним
    world/world.json
    world/chronicle.json
    world/memory.json
    heroes/01_<slug>/hero.json
    heroes/02_<slug>/hero.json
    session.json
  backups/<slot>-v<old>-<ts>/
  journal/                 # этап 2
```

**Атомарная запись:** `slots/.tmp-<uuid>/` → `os.replace`; старый → `.old-<uuid>` → удаление.
Хвосты упавшей записи подбирает `recover_slots` (в начале `list_slots` и `load_slot`). Служебные
каталоги (имя с `.`) при чтении `heroes/` и `slots/` игнорируются. `world_id` — только `[\w-]`,
не с точки; имена слотов — строчные. Мир определяется каталогом: `world_id` в сейве обязан совпасть.

**Миграции:** `CURRENT_SCHEMA_VERSION` в `persistence/migrations/__init__.py`; реестр
`{from_version: fn(bundle_dict) -> bundle_dict}`, файлы `m0001_v0_to_v1.py`… Загрузка: raw → нет
версии = 0 → больше текущей = `SaveTooNew` → меньше = бэкап, цепочка, валидация, перезапись →
нет звена = `MigrationMissing` (до бэкапа). Тест-отпечаток: `tests/schema/save_v<N>.schema.json` =
`SaveBundle.model_json_schema()`; изменение модели без подъёма версии ломает тест.

**Принцип:** persistence никогда не читает файлы старой версии текущими моделями — только сырой
dict до миграции (поэтому ротация слотов правит `manifest.json` как сырой JSON).

## A4. RNG и точки расширения бросков

PCG32 в `core/rng.py` (не `random.Random`): состояние — два int, одинаков на всех версиях Python,
ограниченные целые — rejection sampling. `RngState {algo, seed, state, inc, draws}` в `WorldState.rng`.
`Rng.fork(label)` — позже.

Конвейер бросков `rules/roll_pipeline.py`:

```
RollRequest {kind, actor, target?, ability?, skill?, tags: {critical_moment, stakes_critical,...}, base_adv}
  -> ModifierSource-ы (реестр по kind + ActiveEffect-ы + состояния + зона):
     adv/dis, плоские бонусы, бонусные кубики, auto_fail/auto_crit, диапазон крита
  -> бросок (любое adv + любое dis = обычный)
  -> Reroller-ы по приоритету (удача полурослика, черта, героическое вдохновение через
     DecisionProvider; позже «отвести беду», молитва +6)
  -> RollResult (терм за термом) -> RollLogEntry "d20 (14) + 5 = 19 vs КД 15 → попадание"
```

`CastCheck` (вето/цена перед сотворением) — под жреца этапа 3, на этапе 1 реестр пуст.

## A5. Контент как данные

YAML (`safe_load`) → Pydantic. Слои: `srd/data` → `content/` (репо) → `campaigns/<id>/content/` (этап 3).
Совпадение id между слоями — ошибка со списком конфликтов.

Поведение — данными: умение/черта/заклинание = список `EffectSpec` (`modifier`, `resource`, `action`,
`damage`, `heal`, `save_effect`, `apply_condition`, `area`, `crit_range`, `extra_damage`,
`proficiency`, `spell_access`, `reroll`, `feat_choice`) + экранирующий `handler {name, params}` из
`content/handlers.py` (имя проверяется загрузчиком).
`Subclass {id, class_id, name, source, license, features: [{level, feature}]}`.

Константы SRD — `srd/data/tables/`; параметры ТЗ «в конфиге» — `config/defaults.toml`.
Id латиницей snake_case, `name`/описания по-русски; `docs/glossary.md`; атрибуция SRD — `LICENSE`.

## A6. Раскладка репозитория

```
ai-dm/
  pyproject.toml  uv.lock  LICENSE  README.md  .gitignore(.env, saves/, issues/, journal)
  docs/ TZ.md  ARCHITECTURE.md  BACKLOG.md  glossary.md  rules-adaptation.md  plan-*.md
  src/ai_dm/
    core/        rng.py dice.py clock.py duration.py events.py
    config/      settings.py defaults.toml
    content/     models/{common,features,classes,species,backgrounds,feats,items,spells,monsters,conditions,tables}.py
                 loader.py registry.py handlers.py
    srd/data/    <вид>/<id>.yaml — по файлу на объект: classes/ species/ backgrounds/ feats/ features/
                 weapons/ armor/ items/ masteries/ spells/ monsters/ conditions/ tables/{xp,proficiency,dc,cr_xp,
                 standard_array,point_buy,spell_slots_full,spell_slots_half}.yaml
    state/       creature.py hero.py triggers.py world.py (NPC, Faction, God, Location, GlobalEvent, Tone)
                 memory.py session.py death.py save.py (Manifest, SaveBundle)
                 combat.py (CombatState, Participant, Zone, Group, DecisionPoint)
    rules/       derived.py builder.py roll_pipeline.py modifiers/{base,conditions,species,effects}.py
                 cast_checks.py results.py (Rejected)
                 checks.py damage.py healing.py death_saves.py exhaustion.py rests.py
                 inventory.py money.py progression.py mortality_guard.py creatures.py
                 triggers_eval.py secrets.py time_ops.py auto_flags.py
                 goals.py survivors.py npc_names.py npc_memory.py knowledge.py divine.py
    combat/      setup.py zones.py initiative.py engine.py available.py controllers.py
                 actions/{attack,multiattack,cast,move,standard,item,improvise,parley,features}.py
                 disarm.py mastery.py area.py opportunity.py downed.py defeat.py end.py
    persistence/ layout.py store.py backup.py migrations/{__init__,m0001_v0_to_v1}.py
    devtools/    sim_combat.py sim_grid.py grid_heroes.py
    protocol/ llm/ master/ campaign/ game/ ui/ reports/   # этапы 2+, на этапе 1 не создаются
    world_sim/   tick.py triggers.py candidates.py verdicts.py nudge.py mortality.py aging.py events.py chronicle.py
                 pending.py hazard.py
  content/       subclasses/<class_id>/*.yaml  feats/  monsters/
  campaigns/     # этап 3
  tests/         unit/<пакет>/  scenarios/  fixtures/saves/v0  golden/  schema/
```

Отдельных `core/ids.py`, `core/errors.py`, `rules/modifiers/feats.py` нет: логика черт — в `rules/derived.py`
(`feat_effects`, `hero_effects`) и `rules/roll_pipeline.py`; ошибки — стандартные исключения и `Rejected`.

---

# ЧАСТЬ B. План этапа 1

**Статус этапа 1 (ТЗ, раздел 13): **принят проектировщиком 2026-10-03**.** Шаги 1–24 плана реализованы.

**Задача:** движок правил без ИИ — персонаж, RNG с сидом, проверки, бой на зонах с несколькими
участниками и намерениями, 0 HP/поражение, время/календарь, модификаторы/перебросы, сейв
«мир + герои» с версией и миграциями, схема NPC с триггерами 4.01 и их структурное вычисление.

**Минимальный контент SRD этапа 1:**

| Что | Входит |
|---|---|
| Классы | Воин 1 ур. полностью (Fighting Style: Defense, Second Wind, Weapon Mastery). Волшебник 1 ур.: ячейки, заклинательная характеристика, СЛ/атака заклинаний. Жрец, плут, следопыт — каркас (кость хитов, спасброски, навыки, владения). |
| Таблицы | Опыт и бонус мастерства 1–5, ПО → опыт, СЛ по категориям. |
| Виды | Все 4 с механическими чертами: человек (Resourceful, Skillful, Versatile), эльф (Fey Ancestry), дварф (Dwarven Resilience), полурослик (Luck, Brave). |
| Предыстории | 4 SRD как данные + валидатор структуры 5.2 для произвольной. |
| Черты происхождения | Alert, Savage Attacker, Skilled — механически; Magic Initiate — только данные. |
| Мастерство оружия | Механизм + Graze, Sap, Vex, Topple. Nick и Slow — данными (для точности оружия SRD), механика — позже; Push/Cleave — позже. |
| Оружие и доспехи | Длинный меч, двуручный меч, скимитар, короткий меч, кинжал, короткий лук, лёгкий арбалет, копьё; кожаный, кольчуга, щит. |
| Расходники | Зелье лечения. |
| Заклинания | Fire Bolt, Magic Missile, Burning Hands, Cure Wounds, Bless. |
| Состояния | Все 15 из SRD 5.2, истощение по правилам 2024. |
| Монстры | Goblin Warrior, Goblin Boss, Guard. |

**План реализации:**

1. **Каркас** — `pyproject.toml`, `uv`, src-layout. Зависимости: `pydantic>=2`, `pyyaml`; dev: `pytest`,
   `ruff`. `git init`, `.gitignore`, `LICENSE` (атрибуция SRD 5.2 CC-BY-4.0). Тест-сторож импортов.
2. **RNG** — `core/rng.py`: PCG32, `RngState`, `randint`/`randbelow` без смещения, `d(n)`, `draws`.
3. **Кубики** — `core/dice.py`: парсер `NdM±K` (в т.ч. `2d20kh1`), `DiceRoll`, строка лога по ТЗ 6.
4. **Время** — `core/clock.py`, `core/duration.py`, `rules/time_ops.py`: календарь (по умолчанию
   12 × 30, русские названия), `GameClock`, `Duration` (`7d`, `8h`, `10m`); раунд 6 с, отдых 1 ч / 8 ч,
   путешествие по расстоянию/темпу; категории `advance_time` из конфига; `ensure_min_advance` (вызов — этап 3).
   - Категории `advance_time` — единственное число: `minute | hour | day | week | month`;
     значения по умолчанию: minute = 15 мин (900 с), hour = 1 ч (3600 с), day = сутки,
     week = 7 суток, month = длина текущего месяца календаря. (Аудит 1, P1: hour = 1 ч, 3600 с.)
   - Путешествие: `travel_seconds(distance_m: int, pace: str, cfg) -> int`, темпы SRD в конфиге
     `[time.travel_pace]` целыми метрами в час: slow = 3200, normal = 4800, fast = 6400
     (≈ 2 / 3 / 4 мили в час); результат округляется вверх до целой секунды; неизвестный темп — ошибка.
     Дневной лимит марша и усталость — не на этапе 1.
5. **Конфиг** — `RulesConfig`: категории времени, параметры поражения, лимит раундов (100), доля опыта
   10/25/50 %. Внедряется аргументом, без глобального состояния.
6. **Контент** — схемы, загрузка слоёв, конфликты id, проверка ссылок (оружие → мастерство, класс →
   умения, `handler` → реестр). Минимум SRD из таблицы.
7. **Модели состояния** — `state/*` по A2. Секции этапов 3–9 есть, по умолчанию пустые (не `None`).
8. **Персонаж** — `rules/derived.py`, `rules/builder.py` (`build_character(choices) -> HeroState |
   ValidationErrors`, валидация предыстории 5.2, стандартный набор / покупка очков / явные значения,
   3 мастерства у воина), `rules/progression.py`.
9. **Конвейер бросков** — источники: 15 состояний, черты видов, Alert, Bless, Sap/Vex, укрытие зоны;
   перебросы: Luck, героическое вдохновение (`DecisionProvider`), Savage Attacker; флаг
   `critical_moment`; пустой реестр `CastCheck`.
10. **Проверки** — категории → СЛ 5/10/15/20/25/30, `skill_check`, `saving_throw`, пассивные значения.
11. **Урон и жизнь** — типы, сопротивления, временные HP, крит, концентрация (СЛ max(10, урон/2), ≤30);
    лечение; death saves 5e (nat 20 → 1 HP, nat 1 → 2 провала, урон при 0 HP → провал/2 при крите,
    массивный урон); истощение (−2 × уровень, 6 → смерть); короткий/длинный отдых.
12. **Страж 4.1** — `remove_creature(state, id, status, cause)`, `DeathCause` = `Goal` / `Hazard` /
    `Chance` / `OldAge`; без причины — `Rejected(invalid-death)`.
13. **Инвентарь и деньги** — экипировка, расходники, медяки, выбор ценных предметов для ограбления.
14. **Триггеры и секреты** — трёхзначная логика `TRUE | FALSE | NEEDS_NARRATIVE`; 10 структурных
    условий; `validate_refs`; `is_ready` (`once`/`cooldown`); `check_reveal`; авто-флаги
    (`npc_dead:<id>`, `visited:<loc>`, `combat_ended:<id>`, `item_gained:<item>`).
    Контракт событий для авто-флагов (партия 5): `location_visited {id}`, `combat_ended {id}`,
    `item_gained {hero, item}` — ровно эти ключи; `hero_died` → флаг `hero_dead:<id>`.
15. **Зоны** — валидация старта (2–5 зон, уникальные имена, связный симметричный граф, все размещены,
    у каждой группы `intent` и лидер), BFS → полосы 10/30/60/120 фт (одна шкала для оружия и заклинаний), механические особенности
    (`cover_half`, `cover_three_quarters`, `difficult`, `hazard`).
16. **Инициатива и цикл** — `CombatEngine.step()`, `run_to_end(max_rounds)`, экономия хода.
17. **Действия** — атака (ближняя/дальняя, помеха при враге в зоне, `nonlethal`), заклинания (ячейки,
    площади, союзники задеваются), зелье (бонусное действие), Disengage/Dodge/Help/Dash/Second Wind/
    стабилизация, импровизация (фиксированный набор эффектов), провоцированная атака, Nimble Escape;
    безоружный удар (`unarmed`, урон без костей) и импровизированное оружие (`improvised`, `improvised_thrown`) --
    всегда в `attacks_of` героя; заряд-«всадник» (`spell_kind == "rider"`, Опутывающий удар): `weapon_rider` на
    герое (кости заряда по кругу ячейки через `upcast`), срабатывает в `attack.weapon_rider`, опутанная цель -- `ensnared` + `restrained` до конца концентрации,
    вырваться -- вариант `escape:<заклинание>`.
    Апкаст: у заклинаний с `upcast` (лечение, стрела, огненные руки, благословение, опутывающий удар) пункт меню на каждый
    круг с ячейкой, `usable_circles`, id `cast:<id>:<круг>:<цель>`, базовый круг первым; бесплатное применение и Метка --
    только базовый круг; вне боя `cast_spell.circle` выше базового принимается у тех же заклинаний (Благословение --
    `bad_circle`). Эффект растёт по `per_slot_level` (`upcast_dice`, `upcast_steps`).
    Концентрация по часам: `until_s` ставится при касте (`hold_concentration` в бою, `start_concentration(now_s)` вне боя);
    `expire_concentration` зовётся после каждого сдвига часов -- `rest`, `advance_time`, `travel`, `end.conclude`
    (`release_concentration`), конец хода (`TurnRunner.attempt`), граница сцены (`close_scene`); новый сдвиг часов обязан
    звать её же. Старый сейв с `until_s=None` -- бессрочно до следующего заклинания.
    Смена подготовленных: `rest` `long` с `prepared_swap{drop, take}` (`swap_problem` до отдыха, `swap_prepared` после);
    лимит смены -- `Spellcasting.prepared_swap` класса (`1` или `all`).
    Переговоры (`actions/parley.py`, `PlayerAction.parley: ParleySpec{skill, outcome, target}` и пункты меню
    `parley:<цель>:<навык>:<исход>`): навык intimidation/persuasion/deception × исход surrender/flee/defect/waver/quarrel
    (quarrel -- только фразой Обмана, в меню нет), СЛ и допустимость считает движок (`parley_dc`, `[parley]` в конфиге), враг без отношения NPC -- помеха
    (`skill_check(..., base_adv=)`); одна попытка на цель за бой (метка `parley_tried`). Исходы: `status="surrendered"`
    (не боеспособен, ход пропускается, бить можно), `fled`, `defect` (сторона heroes, `EngineTactics`),
    `wavering` (теряет один ход), `quarreling` (один ход цели бьёт союзника по группе, иначе по стороне:
    `controllers.quarrel_targets`, метка снимается `expire` в конце её хода). Мораль (`spread_morale`, `[parley]`):
    сильный успех (итог ≥ СЛ + `strong_margin` или натуральная 20) «сдаться»/«отступить» применяет тот же исход без
    броска к раненым (HP ≤ 50 %) разумным боеспособным группы цели. Итоги для именованных NPC после боя -- `game/combat_flow.settle_parley`.
    Сдавшийся, бежавший и перебежчик после боя становятся NPC мира (Ж1, см. подраздел «Выжившие боя»).
    Отбор оружия (`combat/disarm.py`, пункт меню `disarm:<цель>:<оружие>`, `pickup:<номер>`): бросок атаки текущим
    ближним оружием против проверки цели (Атлетика/Акробатика героя, лучший мод. Сил/Лов монстра; двуручный хват и
    размер больше -- преимущество цели, меньше -- помеха), тратит одну атаку. Оружейность действия монстра --
    `MonsterAction.weapon_id` (контент); у монстра выбитое оружие = метка `disarmed{weapon_id}` (отключает только это
    действие; без weapon_id -- старый сейв, отключены все оружейные; нет атак и тип в `[disarm].unarmed_types` --
    «безоружный удар»), у героя -- `main_hand=None` и предмет уходит из инвентаря. Оружие падает в зону цели
    (`CombatState.ground_items: GroundItem`) или сразу в руки героя без оружия; подбор -- свободное взаимодействие
    (`TurnState.free_interaction`), иначе действие. Сдавшийся роняет оружие; цель без оружия -- СЛ переговоров −2.
    В `end.conclude`: после победы выбитое достаётся героям (своё -- владельцу), иначе теряется; метки снимаются.
    Монстр обезоруживает героя только с тегом `disarmer` (в контенте пока нет) или с флагом-ролью `disarmer`
    (`[disarm].enemy_chance`, %: бросок раз за бой в `engine.start()` -- `roles.assign_roles`, при 0 RNG не тратится).
    `[disarm].mode`: `check` (по умолчанию) -- состязание выше; `save` -- спасбросок цели Сил/Лов (лучший) против
    СЛ 8 + Сил/Лов + БМ атакующего (`disarm.contest`, `shove.contest_dc`), хват/размер -- преимущество/помеха.
    Падение (`combat/falling.py`): `push` в зону ниже -- 1d6 дробящего за каждые 10 фт (ступень `elevation` =
    `[combat].fall_step_ft`, потолок 20d6) через `engine.damage`, при уроне > 0 `prone` (`source="fall"`), яма
    (отрицательная `elevation`) считается так же, выход -- обычным движением. Толчок монстров (`combat/shove.py`):
    пункт `shove:<цель>:<зона>` у монстров из `[disarm].unarmed_types`, СЛ 8 + Сил + БМ, спас цели Сил/Лов,
    флаг `shove_used`; героя толкает `improvise push`. `equipment` в бою: `NPC.equipment` копируется в
    `Participant` при старте; КД монстра = `ac` минус вклад доспеха/щита статблока плюс надетого
    (`engine.monster_armor_class`, `derived.gear_ac`); оружия нет в `equipment.weapons` -- оно потеряно
    (`lost_weapons`), подбор возвращает его в `equipment`. Истребитель орд: флаг `horde_breaker` после первой
    атаки оружием за ход (до конца хода) и пункт `horde_breaker:<цель>` (бесплатная атака по другой цели в зоне
    первой). Смена Добычи: `rest.prey_swap` (короткий и длинный, проверка до отдыха).
18. **Контроллеры и тактика** — `Controller.choose(options, ctx)`, `available_actions` со стабильными id,
    `EngineTactics` (детерминированная; порядок: `pick_special`, `pick_shove` -- толчок вниз раз за бой при kill/drive_off,
    `step_to_weapon` -- шаг к своему выбитому оружию в соседней зоне), `ScriptedController`, `AutoHeroController`.
19. **0 HP и намерения** — `combat/downed.py`: монстр погибает (`Goal`) или без сознания при `nonlethal`;
    герой — намерение группы атакующего (решает лидер), `DecisionPoint(intent_reconsider)`;
    `kill` → death saves, атаки по лежащему в зоне — автокрит; не `kill` → выбывает без спасбросков,
    сторона пала → `defeat_pending`; союзники победили → стабилизирован на 0 HP.
20. **Последствия поражения** — `apply_defeat_outcome(state, consequences[1..2], params)` по таблице 5.1.
21. **Конец боя** — условия, авто-флаги, `advance_time(раунды × 6 с)`, `outcome`. События для
    авто-флагов: `combat_ended {id}`, `item_gained {hero, item}`, `location_visited {id}` (ключи ровно
    эти), `hero_died {id, ...}` → `hero_dead:<id>`.
22. **Сейв** — слоты, атомарная запись, бэкап, миграции, `m0001_v0_to_v1` (v0 — «досхемный» формат),
    фикстура v0, отпечаток схемы.
23. **Devtools** — `python -m ai_dm.devtools.sim_combat --seed N --scenario goblins3`; сетка `sim_grid` («класс × уровень 1–5 ×
    сцена», герои `grid_heroes`: пресеты и наборы `a`, `auto_level`), `make sim-grid` (не в `make test`) сравнивает с базовой
    линией `devtools/sim_grid_baseline.yaml` (допуск 10 п.п.); таблица — docs/plan-k7k.md.
    **Монстр (К7к):** `Monster.damage_immunities/resistances/vulnerabilities` (типы из `DAMAGE_TYPE_WORDS`),
    `condition_immunities`, `armor`/`shield` (что надето по SRD; КД — число `ac`, по снаряжению не пересчитывается, К7х).
    Урон в бою — только `CombatEngine.damage` (списки статблока в `apply_damage`), состояния на монстра — только
    `CombatEngine.impose` (иммунитет к состоянию; «на себя» и `unconscious` при 0 HP — мимо). Трофеи с тел: оружие, доспех,
    щит (`trophies.body_equipment`, цена `loot.gear_cost`, качество по ПО); `Participant/NPC.equipment`: `None` — по
    статблоку, задано — полная правда об экипировке, пусто — снято (именованный NPC после боя, `trophies.mark_looted`; «снято» = посчитано в трофеи боя, а не взято игроком — не взятое пропадает, В11). Параметр `difficulty` сетки — на будущее, для сцен с бюджетом боя (К7д): на `goblins3` не влияет.
24. **Документация** — `docs/rules-adaptation.md`, `docs/glossary.md`.

**Тестовые сценарии (кабан-доеба, TDD):**

Фикстура «гоблины-3»: зоны «у двери» — «центр зала» — «балкон» (`cover_half`); герой — человек-воин
1 ур., солдат, кольчуга, щит, длинный меч, Defense; два Goblin Warrior в центре, один с луком на
балконе; группа `goblins`, лидер — гоблин 1. Вариант «слабый герой» — волшебник 1 ур.

- **Критерий 1 — бой детерминирован:** бой завершается ≤ 100 раундов; два прогона по сиду —
  побайтно одинаковые лог, состояние и `rng.state`; другой сид — другой лог; golden `S_WIN`;
  `S_DOWN_CAPTURE` → `defeat_pending` → `apply_defeat_outcome([rob, left_to_die])`; `S_DOWN_KILL` →
  death saves, автокрит, `hero_dead` с `DeathRecord(Goal)`; ScriptedRng: 3 успеха → стабилизирован,
  nat 20 → 1 HP; смешанная группа (лидер `capture`, рядовой `kill`) → `capture`; две группы →
  намерение группы последнего удара; герой + Guard vs 3 гоблина → `victory`, герой стабилизирован;
  свойства на 200 сидах; сейв посреди боя → загрузка → доигрыш идентичен непрерывному.
- **Критерий 2 — сейв/загрузка:** полный бандл равен после цикла, повторный save побайтно тот же
  (кроме `saved_at`); пустые секции остаются пустыми, не `None`; раскладка файлов; кириллический слаг;
  атомарность при сбое записи; RNG продолжает последовательность.
- **Критерий 3 — миграции:** v0 → бэкап байт в байт, v1, пустые секции; цепочка v0 → v2 через
  инжектируемый реестр; `MigrationMissing`; `SaveTooNew`; отпечаток схемы.
- **Критерий 4 — триггеры:** `steal_grail` (TRUE/FALSE по граалю и статусу Олдрика); каждый из 10 видов
  условий; смешанные `all`/`any`/`not` с `narrative`; короткая и полная запись эквивалентны; неизвестный
  вид — ошибка с путём; `validate_refs`; `once` и `cooldown: 7d` на границе; секреты; авто-флаги.
- **Ядро:** эталон PCG32, сериализация посреди потока, `randbelow`, распределение d20; парсер кубиков,
  точная строка лога; конвейер (adv+dis, Bless, Poisoned, Prone, Paralyzed, Unconscious, истощение);
  перебросы (Luck, Savage Attacker, вдохновение); внешний `ModifierSource` без правки ядра; валидация
  персонажа (КД 18 у воина в кольчуге со щитом, 19 со стилем Defense; ошибки предыстории/набора/мастерств); зоны (невалидные старты, дистанции
  оружия, провоцированная атака, Burning Hands по зоне, `difficult`); ресурсы и отдых; время (границы
  месяца/года, формат даты, календарь пака); страж 4.1; конфликты контента; сторож архитектуры.

**Риски:**
- Golden-тесты хрупкие — перегенерировать сознательно через devtools; детерминизм — парными прогонами.
- Адаптации 5e к зонам — проектные решения; фиксировать в `docs/rules-adaptation.md`.
- Сползание объёма: механизмы общие, контент минимальный; новое умение не должно требовать правки ядра.
- Сообщения об ошибках discriminated union / короткой записи триггеров — с путём.
- Скрытый недетерминизм: `set`, внешние `dict`, `hash`, float в уроне (урон — целочисленный, вниз).
- Термины 2024 сразу в глоссарий.
- Объём снимка при сотнях NPC — бенчмарк на этапе 3.

**Решения по открытым вопросам (проектировщик):**
1. Полное наполнение SRD — отдельный трек «1.5» параллельно этапам 2–3, закрыть до этапа 6.
   Этап 1 — механизмы + минимум из таблицы.
2. Лицензия кода — **MIT**. `LICENSE`: MIT для кода + атрибуция SRD 5.2 (CC-BY-4.0) для данных `srd/`.

**Примечание:** дальности оружия в тестах — строго по таблице ТЗ 7 (обычная дистанция без штрафа,
дальняя — с помехой).

## Чек-лист релиза этапа 1

Проверяется перед закрытием этапа 1 (не бэклог). Отмечено: [x] выполнено, [ ] осталось.

- [x] В `SaveBundle.session` нет голых `dict` там, где этап 1 их требует: `active_combat` (`CombatState | None`) и
  `pending_decision` (`DecisionPoint | None`) типизированы; схема `tests/schema/save_v1.schema.json` перегенерирована
  без подъёма версии.
- [ ] `current_scene` / `current_chapter` остаются `dict | None` — типизация в этапах 2–3; за этим следит
  strict-xfail сторож в `tests/unit/state/test_save_bundle.py` (при типизации станет XPASS, метку снять).
- [x] Шаги 1–24 плана: каркас, RNG, кубики, время, конфиг, контент, состояние, персонаж, конвейер бросков, проверки,
  урон и жизнь, страж 4.1, инвентарь, триггеры, бой на зонах, поражение, сейв и миграции, devtools, документы.
- [x] Документы синхронизированы с кодом: `README.md`, `docs/ARCHITECTURE.md` (A2, A6, контракт событий),
  `docs/rules-adaptation.md`, `docs/glossary.md`.
- [ ] Приёмка этапа 1 (критерии 1–4 из «Тестовых сценариев», `uv run pytest -q`, `uv run ruff check src tests`).

# ЧАСТЬ C. Этап 2: ИИ-мастер и простой интерфейс

План и состав — `docs/plan-stage2.md`; решения по ревью партий — разделы ревью в `docs/plan-stage2.md`.

## C1. Слои и направление зависимостей

```
ui ──> game ──> master ──> llm
         │        └──────> protocol ──> [ДВИЖОК]
         ├──> protocol
         ├──> persistence ─> state
         └──> llm (журнал, стоимость)
```

| Слой | Что делает |
|---|---|
| `protocol` | Pydantic-модели запросов мастера, `tool_set(mode)` (JSON-схемы инструментов), `apply` (запрос → вызов движка), `Decision` → `tool_result` (строки бросков ТЗ 6). |
| `llm` | `ModelAdapter` (Anthropic, Gemini, Mock, Replay), повторы, журнал вызовов, стоимость, ключи. Ничего не знает об игре. |
| `master` | `PromptBuilder` (стабильный кэшируемый префикс) и `MasterSession.run` (цикл инструментов с бюджетами). |
| `game` | `TurnRunner` (атомарный ход), бой (`combat_flow`, `controllers`), сцены, команды, `GameApp` (меню, `Reply`). Синхронный, без ввода-вывода. |
| `ui` | `io` (`InputSource` / `OutputSink`, тестовые `ScriptedInput` / `CaptureOutput`), `simple` (цикл `run`, вывод ответов), `cli` (`main`, скрипт `ai-dm`). Верхний слой: его импортирует только он сам. |

Нижние слои не импортируют `game` и `ui` (тесты-сторожа в `tests/unit/test_architecture.py`, обход импортов через `ast`).

## C2. Протокол мастера

- Инструменты вызываются через tool use, `strict: true` на инструменте. Форсированный `tool_choice` не используется
  (Anthropic отвечает 400), только `auto` плюс инструкция в промпте. Форму ответа дополнительно проверяет Pydantic.
- Набор инструментов зависит от режима: `explore` (мир: проверки, бой, предметы, время, варианты), `combat_classify`
  (`player_action`, `unsupported_action`), `combat_narrate` (`offer_choices`, `end_combat`,
  `defeat_outcome`), `npc_choice` (`npc_action`). Недоступный в режиме запрос — `invalid`.
- Лимиты strict у Anthropic (20 strict-инструментов, 24 необязательных параметра, 16 union-типов на запрос;
  `docs/llm-notes/claude-api-facts.md`) проверяет линтер схем; редкие инструменты `explore` (`end_chapter`,
  `location_create`) идут без strict.
- Бюджеты цикла: невалидных ответов не больше 2 на ход, раундов инструментов не больше 8. Отказ модели (`refusal`) —
  один автоповтор хода с припиской (тег `refusal_retry`), затем откат хода и подсказка про тон и модель. Исключение — жёсткий отказ Gemini (#21 ТО: `TurnFailed.detail` = `stop_detail`, `game/turn.py HARD_REFUSALS` = `PROHIBITED_CONTENT`/`BLOCKLIST`/`SPII`, `hard_refusal(failure)`): приписка заведомо бесполезна, повтора нет (1 вызов, тег `refusal`); `SAFETY`/`RECITATION`/отказ Claude — как раньше. Ответ `max_tokens` с вызовами — невалидный.
  Короткий рассказ вне боя (`[master] min_narration_chars`, по умолчанию 80; 0 = выкл.) после раунда инструментов — один автоповтор с припиской «напиши сцену текстом» (тег `short_retry`); если и повтор короткий — ход принимается как есть. В бою не проверяется.
  Приписка `CHOICES_NOTE`: если рассказчик вызвал `offer_choices` без текста рассказа (все провайдеры), к ответам инструментов добавляется Text «сцену полностью текстом ответа, варианты уже предложены» (механизм как у `max_tokens`; лог «Варианты ответа предложены» не меняется). Правила и docstring `OfferChoices`: `offer_choices` — в последнем ответе, после результатов механики и текста сцены; приписка только когда обязательные инструменты режима уже вызваны (`done`) и работает и при отклонённом вызове в том же раунде. Текст раунда с отклонённым вызовом сохраняется (не теряется, `short_retry` по нему не нужен); текст раунда с `max_tokens` по-прежнему отбрасывается.
  Приписка `CHOICES_ASK` (T5): рассказ explore вне боя **или `combat_narrate` на ходу, которым бой закончился (`victory`/`fled`/`ended_by_master`, `COMBAT_OVER`)** кончился вопросом или списком вариантов (`ends_with_choice`), а `offer_choices` в ходу не принят — один служебный вызов в том же цикле (тег `choices_retry`), исполняется только `offer_choices` из ответа; тексты ответа, `rounds` и `invalid_count` не меняются; сбой вызова (сеть, отказ) ход не откатывает; `offer_choices` из ответа, оборванного по `max_tokens`, тоже исполняется (обрезанный JSON отсеет `parse_request`). `effort` рассказчика Claude (`[alternatives.narrator]`, `[profiles.anthropic.narrator]`) — `medium`.
  Thinking рассказчика Claude — `[llm] thinking = { narrator = "adaptive" }`, показ — `thinking_display` (`summarized`/`omitted`); другие роли и Gemini — без параметра.

## C3. Атомарный ход

`TurnRunner.play` работает на `bundle.model_copy(deep=True)` и `Rng.from_state`. Успех (commit): синхронизация
`world.rng`, `turn_seq += 1`, запись в `memory.recent_turns`, закрытие сцены и автосохранение на её границе.
Сбой (`TurnFailed` или любое исключение): копия выбрасывается, бандл и RNG прежние, журнал помечает ход `aborted`;
игрок видит меню «повторить / сменить модель / сохранить и выйти». Повтор идёт с новым `run_id` и теми же бросками.
В бою граница хода — решение героя: номер действия выполняется без вызова модели, текст разбирает `combat_classify`.
Запись хода `TurnRecord` (ТМ, v10): кроме `requests`/`rolls` — `outcomes` (лог accepted/clamped вызовов и строки
«`<type>`: отклонено (`<reason>`)» для rejected; Invalid не пишутся) и `money_delta_cp` (разница кошелька героя за ход;
свёрнутая запись боя — сумма свёрнутых). Рассказчику в `recent_turns` идёт `master/prompt.turn_data`: `turn_seq`, `at_s`,
`player_input`, `narration`, `outcomes` — без `requests`/`rolls`/`scene_id` (summarizer видит запись целиком).
Защиты от копирования прошлых ходов (rejected с тегом в авто-репорт): `gold` explicit gain — отказ `gold_repeat`, если
та же сумма (после капа) была дельтой хода за последние `[limits] gold_repeat_turns` (3); `rest long` — отказ
`rest_repeat`, пока не прошло `[limits] long_rest_cooldown` (12h) от `HeroState.long_rest_end_s` (герой с 0 HP —
прежний Invalid `rest_impossible`); `award_xp` — отказ `xp_repeat`, если в `recent_turns` текущей сцены уже `[limits]
xp_awards_per_scene` (1) записей с outcome «Опыт: +» (0 — выкл.); `advance_time` с `category: hour` — отказ
`time_repeat`, если за последние `[limits] time_repeat_turns` (2) ходов был тот же сдвиг («Время идёт: 3600 с») на ходу
без дела (в `requests` только `advance_time`/`offer_choices`; путь `travel_to` не затрагивается; 0 — выкл.). Строки
лога — константы `XP_LOG`, `TIME_LOG` в `protocol/handlers/resources.py`.

## C4. Журнал и Replay

Каждый вызов модели пишется в `saves/<world>/journal/calls-NNN.jsonl` (статические блоки в `blobs/` по sha256, ротация и
gzip, `turn_status committed|aborted`, без ключей). У границы сцены world и summarizer пишут под одним `run_id`: при мягком сбое world (`world_skipped`)
`Journal.mark_turn(run_id, status, role="world")` метит его записи `aborted`, остальное — `committed`. `ReplayAdapter`
отдаёт записанные ответы по порядку и проверяет
отпечаток запроса: изменённый ввод или промпт — `ReplayDivergence`. `ai-dm --replay` воспроизводит бой и броски без сети.
Ограничения replay: обязательны `--world`, `--seed` и `--hero` исходного прогона (`--new` подразумевается); записи
читаются из `saves/<world>/journal`, а игра идёт во временном каталоге `ai-dm-replay-*` (путь печатается при запуске),
поэтому живой мир (journal, meta, slots, models.json) не меняется; пустой журнал — отказ с кодом 1 до создания мира.

## C5. Учёт стоимости

`CostLedger` пишет `saves/<world>/meta/costs.jsonl` вне слотов: откат хода и загрузка сейва деньги не возвращают.
Стоимость считается в нано-долларах (int) по ценам модели из конфига (цена по фактической модели ответа). `/cost` —
сессия, день, мир, по ролям и моделям; строка состояния показывает сумму сессии. Мягкий лимит (выключен по умолчанию):
предупреждение на `warn_percent`, на лимите меню «продолжить / сохранить и выйти».

## C6. Что в ui

Цикл `run(app, source, sink)`: строки запуска, строка состояния, текущий экран (меню или список действий боя); дальше
ввод, ответ `GameApp`, строка состояния. Броски выводятся с префиксом `[бросок]`, меню нумеруются. Ошибки `main`
печатаются сообщением с кодом выхода, без трейсбека; ключи в вывод не попадают (`redact`).

## C7. Решения этапа 2

`docs/plan-stage2.md`, `docs/plan-stage2.md`, `docs/plan-stage2.md`, `docs/plan-stage2.md`,
`docs/plan-stage2.md`, `docs/plan-stage2.md`, `docs/plan-stage2.md`, `docs/plan-stage2.md`,
`docs/plan-stage2.md`.

# ЧАСТЬ D. Этап 3: паки, ход мира, сцены и главы, боги

План и состав — `docs/plan-stage3.md` (статус: на аппруве); решения — разделы ревью в `docs/plan-stage3.md`.

## D1. Слои и направление зависимостей

```
ui ──> game ──> master ──> llm
         │        ├──────> protocol ──> [ДВИЖОК]
         │        └─ world (роль world: тот же цикл инструментов, режим "world")
         ├──> world_sim ─> [ДВИЖОК]     (структурный ход мира)
         ├──> campaign ──> [ДВИЖОК]     (пак: загрузка, уникальность, догрузка)
         └──> persistence ─> state
```

| Слой | Что делает |
|---|---|
| `campaign` | Чтение пака `campaigns/<id>/` (YAML → модели сейва), проверка ссылок, уникальность со списком конфликтов, сборка нового мира из пака и пресета героя, лёгкие пресеты мира (`presets.yaml`: тон и голос поверх тона пака, ограничения пака сохраняются), догрузка новых сущностей в идущий мир. |
| `world_sim` | Шаг мира — день: смертность, старость, истечение и сезонные события; проверка триггеров NPC/фракций/богов/героя и секретов; кандидаты для роли `world`; подталкивание. Без модели, детерминированно по сиду. |
| `master.world` | Один пакетный вызов роли `world` на границе сцены: вердикты по нарративным условиям, исполнение `then` запросами закрытого списка, закадровые заметки. |
| `game.boundary` | Граница сцены как отдельная атомарная транзакция: закрытие → автосейв → тик → триггеры → `world` → глава → новая сцена → закадровый блок. |

Сторож: `campaign`, `world_sim` не импортируют `llm`, `master`, `protocol`, `game`, `ui`.

## D2. Пак кампании

`campaign.yaml` (метаданные, календарь, старт, `mortality`, природные события, подталкивание, tone, флаги,
`monsters` — монстры пака для `monster_ids` рассказчика: пусто — все; реестр остаётся полным,
`ContentRegistry.narrator_monster_ids()`), `world.md`,
`truths.md`, `npcs.yaml`, `factions.yaml`, `pantheon.yaml`, `locations.yaml`, `events.yaml`, `heroes/<id>.yaml`
(пресеты), `start/` (память и хроника «середины игры»), `content/` (третий слой контента). Сущности пака — те же модели,
что в сейве. Конфликтная сущность (5.3) не загружается и попадает в список игроку; ссылающиеся на неё — тоже. Догрузка:
новые id добавляются при каждой загрузке мира, существующие не меняются. Первые паки: `vale` (бывшая заглушка этапа 2),
`drunk_dragon` (старт с главы II, выжимка сцены вместо незакрытого выбора).
Пресет героя несёт `motive`/`means`/`opportunity` как лист героя на лету; при загрузке пака они проверяются по
правилам листа (`means` 0..3, `opportunity` ≤ 2, ссылки условий по id пака); лист главнее пресета.

## D3. Граница сцены и глава

Сцену закрывает `end_scene` или страховка (локация, > 1 ч, конец боя, > 30 ходов); главу — `end_chapter` или 15 сцен.
Порядок: закрытие + `ensure_min_advance` → автосейв закрытой сцены (`boundary_pending=True`) → на копии: тик дней →
триггеры → `world` → глава → новая сцена → доставка заметок → commit. Сбой `world` — меню 2.2; незавершённая граница
достраивается при загрузке до первого хода.

## D4. Роль `world`

Вызывается только при наличии кандидатов (нарративный остаток с выполненной структурной частью; сработавшие `then`;
ступени подталкивания), одним вызовом. Инструменты: `world_verdict`, `world_notice` и запросы 2.1 (`set_flag`,
`npc_update` с перемещением, `favor_change` для NPC, `event_start/end`, `npc_create`, `location_create`, проверки с
`actor`-NPC, `warn_danger`). Смерть за кадром — только `goal|hazard` с броском этого вызова. Журнал общий, `role: world`;
replay — по адаптеру на роль. Потолок вызовов в день — конфиг, по умолчанию выключен. Закадровые версии запросов
(`actor`, `location_id`, `then_ref`) — отдельные модели режима `world`; `favor_change`, `event_*`, `warn_danger` входят в набор
вместе с обработчиками (П5, П6). Детали — `docs/plan-stage3.md`.

## D5. Мир по дням

Смертность: бросок `1/N` в день на именованное существо (пресеты 4.1.1, множитель событий региона и группы), «отвести
беду» самым благосклонным богом. Старость: таблица продолжительности жизни по виду, проверка раз в год после порога,
минусы героя −1 СИЛ/ЛОВ/ТЕЛ за шаг. Природные события — бросок на смене сезона календаря пака. Войны и чума — только
`event_start` с `cause` = сработавший триггер и непустым `regions`. Скачок времени больше `world.max_tick_days` (400):
прокручиваются подробно последние `max_tick_days` дней, остальное — запись в хронике; годовой бросок за пропуск — этап 9. Детали П5 — `docs/plan-stage3.md`.

## D6. Боги, бюджет боя, tone

Благосклонность −10..+10, шаг ±2, ±3 к богу за сцену; пороги ±3/±6/±9 (знамения, молитва (запрос `pray`, фраза игрока, G3б) и помеха в критический
момент, вмешательство и долг/слуга); жрец — `CastCheck` по порогам −3/−6/−9. Бюджет боя — таблица SRD 5.2 по уровню;
сверх — после `warn_danger`, нападения героя или триггера `kills_hero`, иначе урезание с сигналом. Клад логова и предел
редкости — таблицы SRD. Сложность кампании — `world.settings["difficulty"]` (easy/normal/hard ↔ tier low/moderate/high, `encounter.tier_of`; по умолчанию `cfg.encounter.tier`), `/difficulty`, меню нового мира. `/fight <монстр xN, …>` (отладка, 19ф; `game/fight_debug.py`) — бой с заданным составом без модели: `start_combat` на двух зонах (`initiated_by=hero`, без урезания по бюджету) + `combat_flow.start_fight`, без автосейва. Тег `combat_announced` (19ф): рассказ explore объявил бой («начинается бой»), а `start_combat` не принят — только авто-репорт для измерения частоты. `/tone` меняет шкалы ТЗ 3 (ослабление `hard_limits` — с подтверждением), пишет хронику.
Контекст нарратора: релевантные NPC (в сцене, ключевые, с активным триггером) — перенесено из этапа 4 (решение 5а).

## D7. Сейв v3

`CURRENT_SCHEMA_VERSION = 3`, миграция `m0003_v2_to_v3`: типизированные `current_chapter`, выжимки сцен/глав, хроника;
шкалы tone (старый свободный текст → `tone.notes`); состояние хода мира (`sim`, `dangers`, `notices`, `fired`); `divine`
и `deity_id` героя; календарь с праздниками и сезонами. Импорт Дракона (`manual-import`, v1) не мигрируется — его
заменяет пак `campaigns/drunk_dragon`.

# ЧАСТЬ E. Этап 4: память (иерархические выжимки, бюджет контекста)

План и состав — `docs/plan-stage4.md` (статус: на аппруве); решения — разделы ревью в `docs/plan-stage4.md`.

## E1. Слои и направление зависимостей

```
ui ──> game ──> master ──> llm
         │        ├─ context     (сборщик контекста: бюджет, вытеснение, оценка токенов)
         │        ├─ summarizer  (роль summarizer: тот же цикл инструментов, режимы summarize_*)
         │        └──────> protocol ──> [ДВИЖОК]
         └──> game.boundary (summarizer на границе сцены и главы)
```

| Слой | Что делает |
|---|---|
| `master.context` | Бюджет `min(80% окна, static + master.context_cap=16000)` (Ж0: кэшируемая статика в потолок динамики не входит; `static` — оценка `ChatRequest(system=[правила, мир], tools, messages=[])` через `PromptBuilder.static_estimate`, `ContextPlan.cap` = потолок динамики, `ContextPlan.static`, `meta.context.static`); детерминированная оценка токенов по длине запроса (`chars_per_token` с перекрытием по провайдеру роли, `MasterConfig.cpt_for`; по умолчанию перекрытий нет, anthropic 2.2 — Ж0, BACKLOG 77); замер статики правил и схем инструментов — `PromptBuilder.static_tokens(mode)` (схемы через `json.dumps(ensure_ascii=False)`: кириллица не удваивается; explore ≈ 19,7k после Ж1), порог `STATIC_MAX` (20050, Ж3) в `tests/unit/master/test_static_budget.py`, `make prompt-budget`; `meta.context.api_tokens` у Gemini без `cache_write`, у OpenAI `input + cache_read + cache_write` (три непересекающихся числа адаптера); вытеснение по ТЗ 11; `ContextPlan` с `dropped` в журнал. |
| `master.summarizer` | Выжимка сцены (каждая граница) и свёртка главы + `game_summary` (закрытие главы); служебные инструменты `scene_summary`, `chapter_summary`, `game_summary`. |

| `master.hero` | Создание героя (Б0, Б1а): `HeroPromptBuilder` роли narrator, два режима (`protocol.requests.HERO_MODES`). `hero_background` — один инструмент `background_spec` (свободная предыстория под выбранный класс; остаётся под пошаговый режим Б2); system[0] — `prompts/background_rules.md`, system[1] — справочник id. `hero_sheet` — один strict-инструмент `hero_sheet` (лист героя 1 уровня целиком, предыстория вложена, плоские триггеры `opportunity` 0–2 по одному условию); system[0] — `prompts/hero_sheet_rules.md`, system[1] — `sheet_reference_block` (классы с наборами `kits`, виды, черты origin, таблицы трёх методов характеристик, мир и пределы), оба в кэш; messages[0] — описание, замечание игрока (`feedback`) и прошлый лист (`previous`). Контекст — `protocol.context.CreationContext(registry, cfg, task)` без бандла; задача — `BackgroundTask` или `SheetTask` (`known`, `taken_names`, `feedback`, `previous`). |
| `game.hero_create` | `HeroCreateDeps` (зависимости объектом), `run_creation`, `propose_background`, `propose_hero_sheet` — вызов модели и `HeroSheet` (сбои — `TurnFailed` наверх, `run_id` `hero-…`, журнал и `/cost` под narrator); `preview_lines` (показ листа как `/sheet`, `hooks_lines` — предыстория, мотив, средства, возможности — общие с `cmd_sheet`); `edit_sheet` + `sheet_fields_lines` (ручная правка «поле = значение»; содержимое проверяет тот же `rules.builder.sheet_check`, что и путь модели); `write_hero_sheet`/`read_hero_sheet` (`saves/<мир>/meta/hero_sheet.json`, лист для replay); `creation_cost_line`. Проверки — `rules.builder.sheet_check` (= `build_character` + `background_check` + имя героя + мотив, средства, возможности), `sheet_name_problems`, `sheet_hooks_problems`; ссылки условий возможностей — `rules.triggers_eval.validate_refs` по `KnownIds`. Вызывающий — меню героя (Б1б). |
| `master.importer` | Import пака (Б3): `ImportPromptBuilder` роли `import` (`roles.import_`, профили `profiles[*].import_`), один strict-инструмент `pack`; system[0] — `prompts/import_rules.md`, system[1] — `reference_block` (виды, предметы, типы торговцев, виды условий, оси тона из `Tone`, календарь 12×30, пределы), оба в кэш; messages[0] — `campaign_id` и выжимка. Режим `protocol.requests.IMPORT_MODE = "pack_import"`; задача — `protocol.context.ImportTask(campaign_id)` на том же `CreationContext` (поле `files`). |
| `protocol.handlers.pack` | Конвертер запроса `pack` в файлы пака без диска и без `campaign`: `trigger_data`, `secret_data`, `location_data`, `npc_data`, `faction_data`, `god_data`, `tone_data`, `manifest_data` (`id`/`version` ставит движок), `files_from_request`; хендлер `pack_spec` (повтор после принятого — `already_done`, `ValueError` конвертера — `invalid_request`). В YAML попадают только заданные поля. Условия — плоские, через `condition_from_spec`. |
| `campaign.importer` | `PACK_FILES`, `write_pack_files` (пустые списковые файлы и `truths.md` не пишутся), `clear_pack_files`, `check_pack_dir` (`load_pack` + `collect_conflicts` на пустом мире; пусто = пак годен), `relabel` (путь staging → id кампании в строках ошибок). Пак без пресетов героя допустим (запрет в `loader.load_pack` снят): старт только героем на лету/пошагово. |
| `game.pack_import` | `stage_dir`/`finish_import`/`discard_import` (staging `campaigns/.import-<id>-…` → атомарный `rename` в `campaigns/<id>`), `ImportExecutor` (`apply` + запись файлов + проверка загрузчиком; ошибки — `Invalid(pack_invalid)` со всеми строками «файл: поле: что не так», файлы при ошибке удаляются), `run_import` (`MasterSession`, роль `import`, `run_id` `import-…`, зависимости — `HeroCreateDeps` «зависимости вызова ИИ вне мира»), `check_summary`, `calls_cost_line` (общая строка цены, `creation_cost_line` — её частный случай), `pack_report_lines`. |
| `rules.hero_options` | Допустимые множества создания героя (Б2а), чистые запросы к реестру: виды, классы, предыстории, навыки класса без занятых, оружие с мастерством, боевые стили, заклинания класса по кругу, лимиты `spell_counts`, черты происхождения (`origin_feats`), выборы черт (`feat_pick_options`), навыки вида, стандартный набор, таблица покупки очков, наборы класса и `kit_label`. Один источник «что разрешено» для справочника модели (`master.hero.class_data`, вывод `sheet_reference_block` не менялся) и шагов мастера. |
| `rules.builder` (тексты по частям, Б2а) | `ABILITY_MESSAGES`, `BONUS_MESSAGE`, `over_twenty_message` — тексты арифметических ошибок, общие для `build_character` и шагов; `point_buy_cost`, `name_problems`, `motive_problems`/`means_problems`/`hooks_problems` — проверки по значениям, через них работают `check_ability_scores`, `sheet_name_problems`, `sheet_hooks_problems` (сигнатуры не менялись). |
| `game.hero_steps` | Пошаговое создание героя (Б2а), без UI: `Draft` (черновик), `StepDef`/`STEPS` (22 шага в порядке SRD 2024; функции `needs_*`/`options_*`/`count_*`/`put_*`/`label_*` — функции модуля, не замыкания), `apply_put`, `step_done`, `next_pos`, `clear_from`, `to_sheet(draft, registry)` (итог — тот же `HeroSheet`, мотив и средства от игрока, `opportunity` пуст), `step_for_code`, `background_summary_lines`. Тексты ошибок шагов — из `rules.builder`. |
| `campaign.build` | Герой на лету: `build_world(hero_id=HeroSheet)` — `resolve_hero_preset` (пресет `custom`, старт в локации манифеста, деньги от набора класса), `apply_hooks` (мотив, средства, возможности); `known_ids(pack)` и `taken_names(pack)` — для `SheetTask`. Пресет пака: `build_hero` переносит те же три поля. |
| `content` (классы) | `CharacterClass.starting_kits` (`StartingKit`: `id`, `items`, `equip`, `gold_cp`; SRD 5.2 варианты A/B/C, замены — `rules-adaptation.md`); выбор набора — `CharacterChoices.class_kit` (схема пака, не сейва; сейв остаётся v8), применение — `rules.builder.apply_class_kit`. |

Сторож: `master.context` не импортирует адаптеры `llm`, `game`, `ui`; `master.summarizer` и `master.hero` не импортируют `game`.

## E2. Раскладка промпта нарратора

`system[0]` правила и `system[1]` мир — кэш 1h, не зависят от памяти. `system[2]` — память (`game_summary`, выжимки
глав, выжимки сцен текущей главы), `stable=False`: у Anthropic — отдельная 5m-точка кэша, у Gemini — вне явного кэша
(первый Part сообщения). `messages[0]` — состояние хода и сырые ходы; в состоянии хода при непустом отборе есть блок
`knowledge` — журнал знаний героя (E12).

## E3. Граница сцены с summarizer

Закрытие → автосейв → на копии: **выжимка сцены** → тик → триггеры → `world` → глава (**выжимка главы + свёртка
`game_summary`**) → новая сцена → заметки → commit. Сбой summarizer `refusal`/`invalid`/`network` (`SOFT_REASONS`) — повтор на модели рассказчика → запасная выжимка (`fallback`/`concat`, тег `summarizer_backup`, до #22 назывался `refusal_fallback`; выжимка длиннее предела не отклоняется бесконечно: после `[memory] summary_trim_after` = 2 переполнений движок режет её по границе предложения, тег `summary_trimmed`); мягкий сбой world (`refusal`/`invalid`/`network`) — вызов world на границе пропускается, тег `world_skipped` (причина — в записи журнала); `fatal`/`rounds` — как раньше; `fatal` — меню 2.2, новая сцена не стартует (Д2);
незавершённая граница достраивается при загрузке. Журнал `role: summarizer`, `run_id` границы; replay по роли.

## E3а. Сеть и цепочка (Т60)

Gemini ходит по IPv4 (`[llm] gemini_ipv4`, `httpx.HTTPTransport(local_address="0.0.0.0")` в `GeminiAdapter.get_client`; при
`false` — как раньше, `SSL_CERT_FILE` учитывается) с таймаутом `[retry] gemini_timeout_s = 90` на фазу (у Anthropic остаётся `timeout_s = 180`).
`[llm] narrator_chain` — порядок моделей рассказчика (ключи `провайдер:модель`) только для меню ошибки: `game/models.py`
`model_options(app_cfg, current)` ставит первой следующую после текущей (`next_in_chain`), остальные ключи — как раньше, без повторов;
авто-переключения на сетевых сбоях нет (кроме жёсткого отказа, ниже), рассказчик повторяет по полным `retry.delays`, кроме «медленных» сбоев (19ф: таймаут или 504 → `LlmTransient.timeout`, `retry.give_up`): при `[retry] retry_timeouts = false` (по умолчанию) первый такой сбой сразу уходит в меню ошибки (≈ `gemini_timeout_s` вместо 3 × 90 с), 503/429/5xx повторяются по `delays`; `true` возвращает старое поведение; журнал пишет `error.timeout`, старые журналы без ключа реплеятся как раньше. Primary summarizer при наличии backup идёт по `retry.chain_delays`
(`[]` — без повторов, сразу запасной; `TurnRunner.new_summarizer_session` → `SummarizerSession(policy=)` → `MasterSession.policy`),
сетевой сбой summarizer — мягкий (запасная выжимка), в меню не попадает. Сетевой сбой хода (`failed_reason == "network"`) — в меню
«Сменить модель» меняются обе роли (`switch_role = "both"`: `set_narrator` + `set_summarizer`). `Journal.note_start` пишет
`saves/<world>/journal/attempts.log` (`ts, run_id, turn_seq, role, model, attempt` через табуляцию) перед каждой попыткой
(`call_with_retries(on_start=)`); висящая попытка — последняя строка без парной записи в `calls-*.jsonl`; файл не читают `segments()`,
replay и репорты. `game/models.py` — также `check_model`, `read_models`, `write_models` (`game/app.py` реэкспортирует `model_options`, `check_model`).
Жёсткий отказ (#21 ТО): `GameApp.after_turn` → `chain_turn(turn)` — пока `refusal_chain` (по умолчанию True; cli даёт False при `--mock`/`--replay`) и `hard_refusal(turn.failure)` и есть `next_in_chain(текущая)`: репорт отказавшей модели, `set_narrator(следующая)` (постоянно, `models.json`; world/summarizer следуют за провайдером через `follow_provider`), строка игроку «Модель X отказала (D) — переключаюсь на Y.», `runner.retry()`. Цепочка исчерпана, модель вне цепочки (Claude/mock) или `set_narrator` вернул ошибку — меню ошибки с `REFUSAL_HINT`, как раньше; `network` не переключает (Т60). Повтор из меню (`choose_error("retry")`) идёт через тот же `after_turn`.

## E4. Бюджет и вытеснение

Никогда не выкидываются: правила, мир/истины, tools, герой и сцена, NPC сцены (с памятью, целями и заметками, E11),
спутники, NPC с активным триггером, `game_summary` и выжимки глав, ещё не свёрнутые в него (`fixed_chapters`).
По порядку (`STAGES`): сырые ходы (до 1 последнего) → выжимки сцен текущей главы → неактивные NPC
(упомянутые → ключевые → соседние) → соседние локации → выжимки глав с `number ≤ game_summary_chapter` (пятая ступень,
Ж0, BACKLOG 15; самые ранние первыми; `Candidates.chapters`, `ContextPlan.chapters`). Не влезло — запрос уходит,
авто-репорт `context_overflow`. Потолок: `static + context_cap` (16000, динамика без кэшируемой статики), не больше 80%
окна; сторож в тестах — `STATIC_MAX + context_cap ≤ window80` для моделей рассказчика (модель с окном < ≈ 25k после
Ж0 непригодна: одна статика больше 8000 и динамика вытесняется целиком).
Бюджет пересчитывается на каждый ход от текущей модели (`/model`). Оценка — локальная, одинаковая в live/replay/моке.

## E5. Сейв v5

`CURRENT_SCHEMA_VERSION = 5`, миграция `m0005_v4_to_v5`: `source` у выжимок сцен и глав, `Memory.game_summary_chapter`,
`TurnRecord.scene_id`.

## E6. Сейв v8 (Б0-П0)

`CURRENT_SCHEMA_VERSION = 8`, миграция `m0008_v7_to_v8` (чистая `dict -> dict`, контекст не нужен): шкала `Tone.romance`
стала четырёхступенчатой — `нет | намёки | чувственно | откровенно` (решение 2026-10-08); старое `есть` -> `откровенно`,
значение вне шкалы -> `""`. Сам акт — всегда за кадром на обоих верхних уровнях (раздел «Тон» в `narrator_rules.md`).
Заодно `BackgroundSpec.description: str = ""` (текст свободной предыстории; используется с Б1). Отпечаток —
`tests/schema/save_v8.schema.json`.

## E9. Сейв v9 (К0а)

`CURRENT_SCHEMA_VERSION = 9`, миграция `m0009_v8_to_v9` (чистая `dict -> dict`, не импортирует `state`/`content`;
`MigrationContext` обязателен, в нём `class_hit_die` и `spell_level` из реестра). Класс героя — `classes` (адаптер чтения
`class_id`/`level`/`subclass_id`/`primary`, `class_level()`, `prepared_of()`/`known_of()`); `spells_*` и `feature_options`
(теперь `feature_choices`, списки) — по классам; `concentration` — объект (круг из реестра, неизвестное заклинание —
круг 1 и строка в `context.report`); `hit_dice` -> `hit_dice:d{N}` (неизвестный класс — `d8` и строка в `report`);
`companion` -> `companions`; `attuned`, `pending_level`, `temp_form`, `equipment` у NPC и участников боя.

Уровень повышается в два шага: `rules/level_up.py` — `begin_level_up` создаёт `pending_level` (HP считаются сразу),
меню строится по `preview_hero` (копия «как будто уже поднялся»), а уровень и HP применяются только в
`commit_level_up`. Поэтому сохранение посреди меню штатно, меню продолжается после загрузки (`GameApp` ставит
`pending = "level_up"`). Пресеты пака поднимаются атомарно (`level_up` + `apply_level_choices`).

К0б (v9 без миграции): потолок уровня — данные, `rules/progression.max_level(registry)` = старший ключ таблицы `xp`
(`check_level(level, registry)`, `level_for_xp`, `can_level_up`, `level_up`, `begin_level_up`, `quest_xp`, `title_line`);
в конфиге `settings.LEVEL_CAP = 20` (валидаторы `gold_explicit_max_cp_by_level` и `rarity_cap_by_level` — ключи ровно
1..`LEVEL_CAP`; тест-сторож `LEVEL_CAP == max_level(registry)`). Таблицы `srd/data/tables`: `spell_slots_full`/
`spell_slots_half`/`encounter_budget` — 1–20; `pact_slots` (ключ `L:count|circle`, колдун — К6); `damage_severity`
(ключ `полоса:тяжесть:count|sides`, полосы 1-4/5-10/11-16/17-20; `damage.hazard_dice(level, severity, registry)`);
`hoard` — полосы 0-4/5-10/11-16/17+ (`source: custom`), `loot.level_band(level)` и `hoard_band` по старшей полосе
побеждённых. Предел редкости по полосам уровней: uncommon / rare / very_rare / legendary. В данных классов — строки
`ability_score_improvement` на 4/8/12/16/19 (воин +6/14, плут +10; 19 — заглушка до К14) и `prepared_by_level` 1–20.

## E10. Сейв v10 (ТМ)

`CURRENT_SCHEMA_VERSION = 10`, миграция `m0010_v9_to_v10` (чистая `dict -> dict`, контекст не нужен): `setdefault`
`outcomes = []` и `money_delta_cp = 0` в записях `memory.recent_turns`, `long_rest_end_s = None` у героев. Отпечаток —
`tests/schema/save_v10.schema.json`, фикстура `tests/fixtures/saves/v9`. Смысл полей — C3. Старые записи защиту золота
не питают, первый длинный отдых после миграции всегда принят.

## E11. Сейв v11 (Ж0)

`CURRENT_SCHEMA_VERSION = 11`, миграция `m0011_v10_to_v11` (чистая `dict -> dict`, `deepcopy`, `setdefault`, контекст не
нужен). Отпечаток — `tests/schema/save_v11.schema.json`, фикстура `tests/fixtures/saves/v10`, золотой ход
`tests/golden/zh0_turn.json` (тот же ход на мигрированной фикстуре даёт тот же снимок). Принцип (решение 0): поля под
Ж1–Ж3, У0, Н5 заложены сразу одной миграцией (v12 в итоге ушла Ж2 — «Цели NPC (Ж2)» ниже; М0 → v13, С0 → v14).

| Где | Поле | Смысл |
|---|---|---|
| `NPC` | `memory: list[NpcSceneMemory]` | память о герое: сцены (`scene_id`, `at_s`, `weight ≥ 0`, `events` ≥ 1) |
| `NPC` | `goals: list[NpcGoal]` | долгие цели: `kind`, `target`, `text`, `since_s`, `status` (`active`/`done`/`dropped`); код — Ж2 (`rules/goals.py`, ниже) |
| `NPC` | `known_name: str \| None` | имя, под которым NPC известен герою; для `origin="engine"` скрыто, пока `None` (Ж1, см. ниже) |
| `NPC` | `family: list[FamilyLink]` | `kind` (`parent`/`spouse`/`child`), `ref`, `ref_kind` (`npc`/`hero`) |
| `NPC` | `notes: str` | свободные заметки рассказчику; бывший `relations_text` |
| `NPC` | `services: list[str]` | id услуг; код — У0 |
| `HeroState` | `family`, `knowledge: list[KnowledgeEntry]` | связи героя; журнал знаний (`kind`, `ref`, `text`, `source`, `from_ref`, `at_s`), наполнение — Ж3 (E12) |
| `SceneState` | `scene_mood: str` | настроение сцены для музыки (не `Tone.mood`); ставит запрос `scene_mood`, уровень «сцена» в `pick_theme` — Ж3 (F8) |
| `WorldSim` | `pending_acts: list[str]` | действия мира (`act`), отложенные до границы (46); код — Ж2 (`world_sim/pending.py`) |

Миграция: `NPC.relations_text` убирается (`pop`), текст переезжает в `notes` целиком, если `notes` пуст (в v10 `notes`
нет; пак `drunk_dragon`, `import_dragon.py` и фикстура `vale_stage2` переведены на `notes`); остальные поля —
`setdefault` пустыми, `scene_mood` — только у текущей сцены. Модели — `state/relations.py` (`NpcEvent`, `NpcSceneMemory`,
`NpcGoal`, `FamilyLink`, `NPC_EVENT_TEXT_MAX = 120`) и `state/knowledge.py`. Открытые перечни — `str` в моделях
(`MEMORY_KINDS`, `GOAL_KINDS`, `KNOWLEDGE_KINDS`, `KNOWLEDGE_SOURCES` — константы: расширение перечня не меняет схему и
не требует новой версии), закрытые — `Literal`; все модели `extra="forbid"`. `scripts/migrate_dusk_18plus.py` принимает
сейвы v9–v11 (с Ж2 — до v12).

### Память NPC (`rules/npc_memory.py`, BACKLOG 79)

Лимиты — `[npc_memory]` (`NpcMemoryConfig` в `RulesConfig`): `max_scenes = 20`, `max_events_per_scene = 5`, `warm_min_weight = 10` (Ж8). Чистые
функции над `NPC` и `SceneState`:

- `remember(npc, scene, event, cfg)` — событие в запись сцены; новой записи нет — создаётся (`at_s` = начало сцены, вес =
  `scene.attitude_spent[npc.id]`), при полной памяти до этого `evict`; новая сцена входит всегда. Лимит событий в
  записи — `None`.
- `evict(npc, cfg)` — убрать запись с наименьшим `(effective_weight, at_s)`; `effective_weight(entry, cfg)` —
  `max(weight, cfg.warm_min_weight)`, если в записи есть событие вида из `WARM_KINDS` (`state/relations.py`: `romance`,
  `friendship`, `joke`, `shared_deed`, `battle`), иначе `weight`; хранимый `weight` не меняется (Ж8).
  `events_full` — в записи сцены уже максимум событий. `has_kind(npc, scene, kind)` — есть ли в записи сцены событие
  вида.
- `refresh_weight(npc, scene)` — `weight = scene.attitude_spent[npc.id]`: вес — модуль изменения отношений за сцену
  (улучшение и ухудшение равноценны). Зовут `change_attitude` и `combat_flow.settle_parley`.
- `memory_data`, `memory_last`, `goals_data` (только активные) — данные для промпта.

Запись — рассказчиком, через `npc_update`; исключения — события боя выживших, их пишет движок
(`survivors.remember_fight`, Ж1; пересмотр Q7 Ж0), и память общего боя спутникам (`rules/battle_memory.py`, Ж8:
`nearby_companions` — живые, `follows == hero.id`; `battle_text`; `remember_battle` — `battle` каждому спутнику,
один на сцену, нет сцены или герой мёртв — ничего) (`NpcUpdate.memory_kind` из `MEMORY_KINDS` или `none`, `memory_text`;
`WorldNpcUpdate` полей памяти не имеет). `update_problem` → `memory_problem` до любых изменений: `memory_text` без вида —
`Invalid memory_text_without_kind`; нет сцены — `Invalid no_scene`; в сцене уже 5 событий — `rejected`
(`limit-exceeded`), запрос не применяется целиком, в том числе `attitude_delta`. Далее `change_attitude`, затем
`change_memory` (вес новой записи берёт потраченное отношение); для вида из `WARM_KINDS`, уже записанного в сцене,
`change_memory` память не пишет: `clamped`, метка `duplicate-kind`, отношение применено (Ж8). Текст длиннее 120 знаков не отклоняется: обрезка по
последнему пробелу с «…» (итог ≤ 120), статус `clamped`, метка `text-shortened`, запись в `decision.log`, рассказчику —
пометка «текст укорочен до 120».

Показ рассказчику — `PromptBuilder.state_data`/`npc_memory_data`: у `scene_npcs` — `notes`, полная `memory` и активные
`goals` (ключи только если непусты); у `known_npcs` — `notes`, `goals` и `memory_last` (последнее событие). Правило
записи значимых поступков — в `narrator_rules.md` («Формат входа», «Память»). Цена: память 20 сцен ≈ 1–1,5k токенов на
NPC сцены. Мок на 50 сцен — `MemoryMock(npc_memory=True)`, `tests/scenarios/test_zh0_npc_memory.py` (ровно 20 записей =
20 старших по `(weight, at_s)`, детерминизм, сейв на сцене 30).

Решение 12 (перебежчик остаётся в `world.npcs`) — выполнено в Ж1 для всех выживших (раздел ниже).

### Выжившие боя (Ж1, схема v11 без миграции)

Признак выжившего — `NPC.origin == "engine"`, вид существа — `NPC.combat = {"monster_id", "label"}` (`label` — имя
участника боя с номером, «Гоблин 1»). Скрытое имя: `rules/npc_names.py` — `name_hidden(npc)` (`origin == "engine"` и
`known_name is None`) и `shown_name(npc)` (пак и ai — `name`; engine — `known_name`, иначе `label`). Модуль
листовой: `rules/knowledge.py` импортирует его, а `rules/survivors.py` импортирует `knowledge`, так что имена в
`survivors` дали бы цикл.

`rules/survivors.py`: `classify(bundle, hero)` (до `finish_combat`: он снимает метки переговоров) → список `Survivor(part,
kind, label, group)`; `kind_of`: `defected` (метка `parley_defected`, статус не `dead`; исходная группа лежит в
`params["group"]` метки, пишет `apply_defect`), `surrendered`, `fled`, `spared` (`down`, а при `ended_by_master` и
`active`). Выживший — безымянный участник (`creature` есть, `ref` не в `world.npcs`), исход `victory`/`fled`/
`ended_by_master`, герой жив. `materialize(bundle, hero, survivors, cfg)` создаёт NPC: id
`<monster_id>_t<turn_seq>_<n>` (первый свободный по `uniqueness.id_taken`), `named=False`, `means=[label]`, копии
`creature`/`equipment`, `groups=[исходная группа]`, локация героя (бежавшему — первая соседняя по id, считается локально:
слой `rules` не видит `master.relevance`), отношение из `[survivors]` (`start_attitude`), событие памяти и цель
`life_debt` (`LIFE_DEBT_TEXT`), запись журнала `MET` по виду (`note_met`). Порядок в `TurnRunner.end_fight`: `classify` →
`settle_parley` → `finish_combat` → `note_combat` (перебежчики идут в бестиарий через `defected=`) → `materialize` →
`remember_battle` (Ж8, `rules/battle_memory.py`) → `fold_fight`.

Открытие имени: `TurnRunner.commit` зовёт `reveal_names(hero, world, narration)` перед `note_presence`: NPC рядом или с
`follows`, `name != shown_name` (имя назначено), `mentions` (эвристика Ж3) → `known_name = name` и
`knowledge.rename_met`. `note_presence` скрытых по имени не ищет; `is_met`/`backfill` читают `shown_name`.

Протокол: `NpcUpdate.name` (у `WorldNpcUpdate` его нет). `handlers/world.py`: `name_problem` (`name_locked` — не engine или
уже `named`; `empty_name`; занятое — `rejected` по `uniqueness.name_conflict`; с Ж2 — и имя, совпадающее с видом
существа, `npc_names.looks_like_kind`: метка боя с номером и без, название монстра реестра — BACKLOG 86), `change_name` (`name`, `named=True`,
лог без имени), `npc_label` (= `shown_name`) во всех логах и сообщениях пути `npc_update`. Промпт: `survivor_data(npc)` —
ключи `kind`, `unnamed`, `name_hidden` в `scene_npcs` и `known_npcs` (только у engine-NPC); рассказчик настоящее имя
видит. Показ игроку идёт через `shown_name`: `lore_text`, `battle_map`, `shop_text`, `make_enemy`,
`summarizer.state_data`. Конфиг — `[survivors]` (`SurvivorsConfig`). Хвост: `start_combat` не трогали (BACKLOG 78).

### Цели NPC (Ж2)

**Цель ↔ триггер.** `rules/goals.py`: `add_goal(npc, kind, target, text, now_s)` (цель на героя) и `add_npc_goal` (на NPC)
создают `NpcGoal` и триггер-спутник `Trigger(id="goal:<kind>:<target>", if={"all": [структура, {"narrative": NARRATIVE[kind]}]},
then=текст цели, once=True)` в `npc.opportunity`. Структура: для героя `{"not": {"hero_dead": true}}`, для NPC
`{"npc_status": {"id": target, "is": "alive"}}`. Связь цель↔триггер — только по id (поля в `NpcGoal` нет). Одна активная цель
на `(kind, target)`: повтор → `None`; спутник закрытой цели с тем же id заменяется. Близости к герою в `if` нет: приход
мстителя решает world (`WorldNpcUpdate(location_id, then_ref)`). Отдельного вида кандидата нет — работает прежняя цепочка
`candidates.verdict_candidates` → вердикт world → `fire` → `act` → `then_ref`.

**Закрытие.** `mark_fired` после `fire` (в `triggers.check` через `fire_trigger` и в `verdicts.apply_verdicts`) → `done`;
`sweep(world, heroes)` в начале `triggers.check`: носитель не `alive` или мишень мертва/ушла → `dropped` и спутник
`disabled`; `close_goal(npc, kind, target, status)` — запросом.

**Редкая проверка.** `WorldSim.goals_checked_s`; `goals.due(sim, now_s, every_days)` — первая проверка сразу, далее через
`[world] goals_check_every_days` (1) от предыдущей (как `god_due` у богов, но одна метка на мир). `triggers.check(bundle, cfg)`
считает `due` один раз, передаёт `skip_goals=not due` в `verdict_candidates`, пропускает спутников (`goals.skipped`), после
проверки пишет метку. Обычные триггеры не затронуты; `max_calls_per_day` world — второй потолок.

**Факты, по которым движок ставит цели.** `survivors.remember_fight`: бежавший/сдавшийся с отношением ≤
`[survivors] revenge_attitude_max` (−40) → `revenge`; пощажённый → `gratitude`; перебежчик → `life_debt` (через
`add_goal`). `goals.on_kill` (из `TurnRunner.end_fight`) и `goals.on_npc_killed` (из `change_status` при
`by=<герой>`) → `avenge`: мстители — живые NPC с `FamilyLink.ref` = убитый или с группой убитого в `npc.groups`
(не участники боя, не `follows` героя, отношение ≤ 0); цель `revenge` на героя и память `kin_killed` (при наличии сцены).
Убийца пишется в `Participant.last_hit_by` (`downed.kill_monster`); убил не герой — мести нет, без убийцы — на героя.
`combat/defeat.do_debt` ставит кредитору цель `debt` вместо прямого триггера (флаг `world.flags["debt:<hero>"]` остаётся).

**Протокол.** `NpcUpdateBase`: `goal_kind` (`GOAL_KINDS` или `none`), `goal_target` (пусто = текущий герой),
`goal_text`, `goal_status` (`none`/`done`/`dropped`); оба пути `npc_update` (рассказчик и `offscreen`), у `WorldNpcUpdate`
те же поля. `handlers/world.goal_problem` → `Invalid`: `goal_fields_without_kind` (раньше `empty_update`),
`unknown_goal_target`, `goal_exists`, `no_such_goal`, `goal_kind_with_status` (постановка и `status` в одном запросе),
`npc_not_alive` (цель мёртвому/уходящему NPC; закрытие разрешено); `change_goal` — `add_goal`/`close_goal`, лог через
`npc_label`. Цель применяется раньше `status=dead`. Мститель у world — `location_id` + обязательный `then_ref`.

**Показ.** `master/relevance.npc_reasons`: `npc.named or goals.has_active_goal(npc)` — безымянный выживший с активной целью
попадает в `known_npcs` (BACKLOG 85). Правила: `narrator_rules.md` (когда ставить и закрывать цели, `change_deity`),
`world_rules.md` (вердикт на `event:`, `goal_*` при исполнении `then`, приход мстителя). Статика: `STATIC_MAX` 20960.

**46 `pending_acts`.** `world_sim/pending.py`: `stash_acts` — при `world_skipped` кандидаты `act` (сериализованный
`Candidate.model_dump_json()`, не ref) откладываются в `WorldSim.pending_acts` без дублей по ref, потолок `PENDING_MAX = 20`;
`take_acts` перед вызовом world возвращает отложенные (владелец жив: `owner_present`) вместе с новыми, отсортированные
`sort_key`, и очищает очередь; `load_acts` молча отбрасывает битые записи. Мягкий сбой world (откатов нет) — `stash_unapplied`:
откладываются только `act`, по чьему `then_ref` не прошёл ни один запрос (`TurnContext.applied_refs`,
`protocol.apply.note_applied`, `TurnFailed.applied_refs`). Вызов — `game/boundary.call_world`.

**9 `ends_when`.** `candidates.event_candidates`: активное событие с `ends_when`, у которого структура выполнена, а остаток
нарративный → вердикт-кандидат `ref="event:<id>"`, `owner_kind="event"` (`OWNER_RANK["event"] = 4`); `verdicts.apply_verdicts`
при «выполнено» ставит `event.ends_at_s = now_s` (хронику пишет тик, `close_events` не менялся);
`nudge.mark_not_participating` `event:` пропускает.

**Hazard в тике.** `world_sim/hazard.py`: `roll_hazards(bundle, rng, cfg, registry, at)` — `tick.tick_days` вызывает раз в
день после `mortality.roll_day`; для активных героев (по id) в зоне события с `hazard` (`zone_events`: `event_active` и
`mortality.affected`) — `saving_throw`; провал → `add_exhaustion(+1, cause="hazard")` с вмешательством бога на шестом
уровне (`intervener` → `try_intervention`), запись `event` в хронике, при смерти — `hero_died` и запись `death`.
Не больше одного hazard от события на героя в день (внутри тика). Запрос рассказчика с событием не связан.

**Смена бога.** Запрос `ChangeDeity(god_id, reason)` в `MODE_TOOLS["explore"]`; `handlers/world.change_deity`: `unknown_god` /
`same_deity`, затем `divine.change_deity(hero, god_id)` — прежний бог получает ключ `favor` (0), новый +1 только без
ключа в `hero.favor` (возврат — 0); возвращает фактический сдвиг. Хроника `favor`, запись журнала знаний `note_favor`
(`deduced`), лог «благосклонность +1» только при прибавке. `PromptBuilder.divine_data` — поле `deity`.

### Сейв v12 (Ж2)

`CURRENT_SCHEMA_VERSION = 12`, миграция `m0012_v11_to_v12` (чистая `dict -> dict`, `deepcopy`, контекст не нужен):
`world["sim"].setdefault("goals_checked_s", None)`. Отпечаток — `tests/schema/save_v12.schema.json`, фикстура
`tests/fixtures/saves/v11`; `scripts/migrate_dusk_18plus.py` принимает сейвы v9–v12. Единственное новое поле —
`WorldSim.goals_checked_s: int | None` (время последней проверки триггеров целей, смысл — «Редкая проверка» выше).
`WorldSim.pending_acts` существовало в v11 (Ж0) и получило код в Ж2; поля запросов `goal_*`, смена бога и hazard полей
сейва не добавляли. Старые триггеры `debt_<hero>` миграцией не переводятся: остаются как есть, без цели. М0 → v13, С0 → v14.

## E12. Журнал знаний героя (Ж3)

Схема сейва журналом не меняется (v11, с Ж2 — v12 по другой причине, см. выше): `HeroState.knowledge: list[KnowledgeEntry]` (`state/knowledge.py`) и
`SceneState.scene_mood` заложены в Ж0, в Ж3 получили код.

**Модель и перечни.** `kind` — о ком запись (`KNOWLEDGE_KINDS`: `npc`, `location`, `faction`, `god`, `creature`,
`situation`), `source` — откуда (`KNOWLEDGE_SOURCES`: `seen` видел сам, `told` рассказал NPC, `rumor` слух, `read`
прочитал, `deduced` понял сам). Перечни открыты (поля `str`). `ref`: у `npc`/`location`/`faction`/`god` — id сущности
(ключ словаря мира), у `creature` — id монстра реестра, у `situation` — слаг латиницей `^[a-z0-9_]{2,40}$` от рассказчика.
`from_ref` — id NPC, рассказавшего (`told`). `KNOWLEDGE_TEXT_MAX = 160`.

**Чистые функции** — `rules/knowledge.py`: `remember_fact` (дубль по `(kind, ref, normalize(text))` → `False`; лимит
`[knowledge] max_per_ref = 5` (`KnowledgeConfig` в `RulesConfig`) — уходит старейшая запись сущности по `at_s`),
`note_presence`, `note_combat`, `note_favor`, `note_secret`, `backfill`, `spoils`, `shorten_text`, `prompt_entries`.
Тексты записей движка начинаются с констант `MET` («Знакомство: »), `VISITED` («Место: »), `FOUGHT` («Бой: »).

**Кто пишет.** Движок: первая встреча NPC (`TurnRunner.commit` → `note_presence`: живой NPC в локации героя или идущий с
ним, чьё имя есть в вводе или рассказе хода; NPC со скрытым именем (`name_hidden`) по тексту не ищутся) и первое
посещение локации героя (`seen`); бестиарий (`TurnRunner.end_fight` → `note_combat`: безымянные враги боя и перебежчики
(`defected=`), текст «Бой: <монстр> — победа|бегство|поражение|прерван»); знакомство с выжившим по виду
(`survivors.materialize` → `note_met`, текст «Знакомство: <вид>») и его переименование при открытии имени
(`reveal_names` → `knowledge.rename_met`); милость бога (`favor_change` героя → `note_favor`, `deduced`) и смена бога (`change_deity` → `note_favor`, Ж2); раскрытый
секрет (`reveal_secret` → `note_secret`, `deduced`).
Рассказчик: запрос `knowledge_note` (`protocol/handlers/knowledge.py`, только explore, без strict).

**Отказы `knowledge_note`.** `Invalid`: `empty_text`, `unknown_ref` (с `allowed(...)`), `bad_ref` (ситуация не слаг),
`unknown_npc` (`from_ref`), `told_without_from`. `rejected`: дубль («уже записано», без метки); спойлер — текст покрывает
нераскрытый секрет (доля значимых слов секрета длиной ≥ 4 в тексте ≥ 0,6), метка `spoiler`. Текст длиннее 160 знаков
обрезается по последнему пробелу с «…»: `clamped`, метка `text-shortened`. Секреты рассказчик не пишет — их записывает
движок при принятом `reveal_secret`.

**Достройка старого мира.** `backfill(bundle, cfg)` в `GameApp.__init__` и `GameApp.load` (после старта сцены):
записи `seen` для встреченных NPC (любой признак: `known_to_player`, `memory`, `follows`, `attitude != 0`, имя в
`recent_turns` или выжимках сцен, глав и `game_summary` — выжимки только признак, текст не берётся), секреты из
`known_to_player`, посещённые локации и текущая. `at_s` — начало текущей сцены; идемпотентна.

**Показ рассказчику.** Блок `knowledge` в `PromptBuilder.state_data` (`messages[0]`, не `system[2]`): вид → ref → строки
«текст (источник[: кто рассказал])». Отбор (`PromptBuilder.knowledge_refs`): `npc` — NPC сцены и `known_npcs`; `location`
— локация героя и соседние; `god` — из `hero.favor`; `faction`, `situation` — все; `creature` — только в режимах боя по
`monster_id` участников. Записи движка `MET`/`VISITED` не идут. Потолок `[master] knowledge_max = 30` (новейшие по `at_s`;
0 — блок выключен); блока нет, если отбор пуст. Стоимость: худший случай ≈ 2,1k токенов, типично 0,4–0,8k на ход, внутри
`context_cap`; роли `world` и summarizer журнал не получают. Статика: два запроса и раздел правил «Журнал знаний и
настроение сцены» подняли `explore.total` до ≈ 19,5k (`STATIC_MAX` 20050); после Ж1 замер 19736.

**`/lore`.** `game/lore_text.py` (`lore_groups`, `find_entity`, `entry_lines`, `lore_lines`): без аргумента — виды и
сущности с числом записей, с аргументом — записи найденной сущности (подстрока имени или `ref`, без регистра) «— текст
(источник[: имя рассказавшего], дата)». В `/lore` идут все записи, включая `MET`/`VISITED`; ответ строится только по
журналу, без модели; время мира команда не тратит, в бою доступна. `cmd_lore` в `game/commands.py` общая для обоих
режимов. TUI: `LoreModal` (F5).

**`scene_mood`.** Запрос `scene_mood` (`romance` или `none`, только explore) ставит `SceneState.scene_mood`; метка слетает с
концом сцены (у новой сцены `""`). Влияние на музыку — F8.

# ЧАСТЬ F. Этап 5: TUI (Textual), модель экрана

## F1. Слои ui

```
ui.cli ──> ui.simple ─┐
       └─> ui.tui ────┼──> ui.screen (Reply → блоки) ──> game (GameApp, Reply)
                      └──> ui.session (PlaySession: ввод игрока) 
```

`ui` остаётся верхним слоем. `textual` импортируют только `ai_dm.ui.tui*` (и `ui.cli` лениво); `ui.screen`, `ui.session`,
`ui.simple` его не знают.

## F2. Модель экрана `ui.screen`

Функции без ввода-вывода: из `GameApp` и `Reply` строят список `Block(kind, text, items, title, args)`.
`kind`: `narration`, `roll`, `note`, `boundary`, `raw`, `hint`, `menu`, `combat_map`, `turn_menu`, `combat_hint`, `status`,
`gains`. Здесь же `status_line`, `limit_state`, `LABELS`, `screen_blocks` (pending-меню / бой / варианты), `reply_blocks`
(порядок вывода хода: броски и заметки, рассказ, границы, `reply.lines`, `raw`, `hint`, итог боя, «Получено»).
`gains`: `text` — «Получено опыта: N» (только при победе), `items` — разница предметов и денег героя до и после хода
и опыта (опыт в `items` не пишется при победе, чтобы не дублировать `text`).
Побочный эффект: `screen_blocks` в бою ставит `app.hinted_combat` (подсказка один раз за бой). Вызывать один раз за ход,
перерисовку (F2, ресайз) делать из сохранённых блоков, а не повторным вызовом.
`turn_menu.args` = `(turn, concentration, ac, effects, inert, roster)`; `roster` — `TargetChip` живых врагов (`screen.roster_of`),
простой режим его игнорирует.
Простой режим `simple.render(block, width)` печатает блоки через `ui.format.*` тем же текстом, что и раньше; `gains` в нём — только `text`.

## F3. Контроллер `ui.session`

`PlaySession(app, replay, secrets, opening)`: `start()`, `submit(line)`, `finish()` (= `submit(None)`), `take_opening()` →
`Step(blocks, quit, exit_code)`. Держит то, чего нет в `GameApp`: меню мягкого лимита (`warned/asked/limit_menu`), разбор цифры
(pending-меню / варианты вне боя), автосейв при конце ввода, отказ сохранять при смерти, перехват исключений хода с `redact`
(в replay — `exit_code = 1`). `simple.run` — тонкий цикл «read → submit → render»; TUI вызывает тот же `submit`.

## F4. Каркас TUI (P2)

`ui/tui/app.py` — `AiDmApp(session, startup=())`, `ui/tui/widgets.py` (`Panel`, `Choices`, `StatusBar`, `Rolls`, `hero_lines`),
`ui/tui/strings.py` (все русские строки), `ui/tui/app.tcss`. Публичные id: `#feed` (лента), `#choices` (варианты/меню под лентой),
`#input`, `#status`, `#side` (правая панель) с `#picture` (скрыт, пока нет рисунка), `#hero`, `#combat`, `#rolls`, `#gains`.
- Блоки `Step` раскладываются по виджетам: `narration`/`note`/`boundary`/`hint`/`raw` → лента (рассказ без рамок), `roll` → «Броски» и
  лента, `menu` → `#choices`, `combat_map`/`turn_menu` → «Бой», `gains` → «Получено», `status` → строка состояния.
  После обычной строки (не `/команды`, кроме `/load`) меню, «Бой» и «Получено» очищаются и перерисовываются из блоков шага.
- Ход: `run_worker(thread=True, exclusive=True)`, пока он идёт, `#input` disabled и в `#status` «Мастер думает…»; результат —
  `call_from_thread`; после хода ввод включён и в фокусе. Лист героя и процент лимита (`screen.limit_percent`: большее из сессии и
  дня, только при включённом лимите) читаются в главном потоке после хода.
- Раскладка: ширина ≥ 120 — класс `wide` на App, `#side` справа; уже — одна колонка, F2 переключает класс `open` у `#side`
  (панель поверх ленты, `dock: right`). Ресайз пересчитывает класс.
- Русский: палитра команд выключена, свои `BINDINGS` (F2 «Панель героя», Ctrl+Q и Ctrl+C «Выход»), строки только из `strings.py`.
- Ctrl+C / Ctrl+Q: вне хода — выход с автосейвом (`after_exit` → `session.finish()`); во время хода первый ждёт конца хода и
  выходит с автосейвом, второй — выход без сохранения (код 130; поток хода дорабатывает сам). При подготовке мира в TUI-режиме
  накопленные строки старта печатаются (`flush_notes` в `cli.play`) в обоих случаях: Ctrl+C — «Прервано.», код 130; прочая ошибка — «Ошибка: …», код 1.

## F5. Выбор режима, модалки, `/cost` (P3-P5)

- Выбор режима: `cli.choose_mode(args, injected, env, stdin_tty, stdout_tty)` даёт `tui` только при настоящем терминале на вводе и
  выводе, без `--simple`, без подмены stdin/stdout (тесты) и без `TERM=dumb`; иначе `simple`. В режиме TUI строки старта копятся
  (`CaptureOutput`) и попадают в ленту.
- Fallback: `ai_dm.ui.tui` импортируется лениво; `ImportError` или `TuiStartError` (ошибка до первого кадра, `app.shown` ещё ложно;
  то же для `pick` и `create_hero`) — печатается «TUI не запустился: …, простой режим» и та же игра идёт через `simple.run`. Ошибка после
  первого кадра пробрасывается.
- `ui.tui.modals`: `TextModal` (ответы `/sheet /inv /spells /abilities /model`, Esc или кнопка закрывают), `CostModal` (`/cost`
  таблицей из `game.commands.cost_rows`, те же строки роль × модель, что печатает простой режим), `PickerApp(title, names)` (выбор героя и пресета мира до игры:
  цифра или клик). Цифра выбирает вариант/пункт меню через `check_action`, пока нет хода, модалки и текста в поле ввода.
  `LoreModal(title, groups, world, selected)` (Ж3, `/lore`): слева `OptionList #lore-list` (заголовки видов — `disabled`
  строки, сущности с числом записей), справа `VerticalScroll #lore-body` с записями выбранной; `/lore <имя>` предвыбирает
  сущность; ничего не запускает, клавиши и `action_lore` нет (открывается только командой), Esc или кнопка закрывают,
  цифры в окне не выбирают ход (`MODALS`). Пустой журнал — обычный `TextModal`.
- Команды из `HELP` отвечают в обоих режимах, `/retire` — одинаковая заглушка; `/report` — см. раздел «Репорты (6а, P0)».
- Приёмка: сценарий этапа 2 на моке даёт одинаковый бандл в простом режиме (ScriptedInput) и в TUI (Pilot);
  `tests/scenarios/test_stage5_tui.py`. Проверка Linux: `make linux-check` (`devtools/linux_check.sh`), установки колеса: `make install-check`.
- Герой на лету (Б1б): `ui/hero_session.py` — `HeroSession(deps, task, width)`, машина состояний создания без терминала
  (`describe → review → remark | edit`, сбой `TurnFailed` → меню 2.2 «повторить / сменить модель / выйти», `refusal` — `REFUSAL_HINT`;
  итог — `sheet`, `run_ids` для `creation_cost_line`); блоки те же `ui.screen`. Простой режим: `simple.emit_blocks`,
  `cli.create_hero_simple`; TUI: `ui/tui/create.py` `HeroCreateApp` (отдельный App до основного, как `PickerApp`; шаг сессии
  в thread-worker, `#feed/#choices/#input/#status`), точка входа `tui.create_hero(session, placeholder)`; сбой запуска → простой режим.
  `cli`: `choose_hero` (пресеты пака + «Создать героя на лету», `NEW_HERO`; пак без пресетов героев — сразу создание),
  `choose_preset` (меню пресета мира после героя; «Как в паке» и конец ввода — тон пака; `codename` пресета — только в меню),
  `ask_choice`, `--hero-describe` (без меню: один вызов, годный лист принимается; `hero_flag_refusal`), `replay_records`
  (записи `hero-…` не идут рассказчику при повторе; лист героя для повтора — `meta/hero_sheet.json`), `discard_world` (отмена
  создания удаляет каталог мира без слотов). `game.app.model_options/check_model` — общие для меню `/model` и `HeroSession`.
- Import пака (Б3): `ui/import_session.py` — `ImportSession(deps, task, text, folder)` (прогон `run_import`, сбой `TurnFailed` → `RetryMenu`
  меню 2.2 «повторить / сменить модель / выйти», `refusal` — `REFUSAL_HINT`; итог — `ctx.files`, `run_ids`). `cli`: флаг `--import FILE`
  (`dest="import_file"`) вне игры, как `--replay-report` — вывод прямо в stdout без TUI; `import_refusal` (несовместимые флаги и
  нет `--campaign` → 2), `import_text` (id занят, файл не читается, `check_summary` → 1), `pick_import`, `import_pack`/`import_run`
  (staging, журнал `Journal(staging, ".import", …)` → `campaigns/<id>/.import/journal/`, строка «Импорт пака: $…» печатается до
  переименования, успех → `finish_import` и `pack_report_lines`, код 0; отмена → `discard_import`, код 1). Конфиг: роль `import`
  (`[roles.import]`, `[profiles.*.import]`, `max_tokens = 32000`), `[import] max_chars = 60000`. Сейв остаётся v8.
- Пошаговое создание героя (Б2а): `ui/hero_wizard.py` — `HeroWizard(deps, task, width)` с тем же интерфейсом, что у `HeroSession`
  (`start`, `submit`, `.sheet`, `.run_ids`, `.width`), поэтому TUI и простой режим работают без нового App. Состояния `step`,
  `words`, `error_menu`, `model_choice`, `review`; «назад» — снимки `(pos, draft)` перед каждым принятым значением, «отмена» —
  выход без листа. Предыстория «Описать словами» — один вызов `propose_background` (`run_id` `hero-…`, роль narrator); сбой —
  `RetryMenu` (меню 2.2 «Повторить / Сменить модель / Выбрать из списка»). По окончании шагов лист проходит `sheet_check` и
  передаётся в `HeroSession` на ревью (меню `WIZARD_REVIEW_MENU`: принять, вернуться к шагам, править поля вручную).
  `ui/hero_session.py`: `RetryMenu` (вынесено меню 2.2), `HeroSession.review_menu`. `cli`: третий пункт `choose_hero`
  «Создать пошагово» (`STEP_HERO`), `make_hero_session`; строка «Создание героя: $…» — только если были вызовы ИИ.
  TUI (Б2б): `HeroCreateApp(session, placeholder)` — `cli.create_hero_tui` передаёт `strings.STEPS_PLACEHOLDER` для `HeroWizard`
  и `CREATE_PLACEHOLDER` для `HeroSession`; заставка `art_for_event("title")` выводится в `#feed` экрана создания и в новом
  `#feed` над `#choices` у `PickerApp` (выбор героя; флаг `splash`; пикер пресета мира — без заставки, `splash=False`, виджета `#feed` в нём нет); в ревью пошагового героя —
  строка-подсказка `REVIEW_HINT` про откат последнего шага.

## F6. Рисунки (P6)

Каталог `src/ai_dm/art/` (сейвы и схема `Location`/`Monster` не меняются): `data/<id>.txt` (один рисунок — один файл) и
`data/index.yaml` (`ArtIndex`, `extra="forbid"`, `source: custom`): `events` (title, victory, death, level_up), `locations`
(точный id локации), `location_tags` (тег локации; порядок тегов локации — приоритет), `monsters` (id монстра),
`creature_types` (фолбэк по `Monster.creature_type`). Лимиты: обычные рисунки ≤ 36×14, заставка ≤ 76×16; символы 0x20–0x7E и `░▒▓`
(ширина 1), без табов и хвостовых пробелов. Файлы идут в колесо сами (hatch берёт всё внутри пакета).
- `art.catalog`: `load_art()` (кэш; `Art.index`, `Art.pictures`), `art_for_location(loc)`, `art_for_monster(mon)`,
  `art_for_event(name)` -> `str | None` (точный id → тег/тип → None).
- `art.pick`: `pick_picture(prev_state, state, events)` -> `Picture(kind, text) | None` (чистая, без Textual). `PictureState(location,
  monster, combat_id)`; `prev_state` None — старт игры. Приоритет: событие (death > victory > level_up) → старт боя (рисунок
  первого живого врага) → смена локации; иначе None («оставить как есть»). `ui.screen.picture_state(app)` собирает состояние,
  `ui.session.Step.events` несёт события хода (death, victory, level_up).
- TUI: рисунок выводится как `Text` (не markup). `Picture.kind == "monster"` app печатает в ленту `#feed` (крупный, ≤ 36×14,
  один раз на бой, при начале боя); `#picture` в бою скрыт. `"location"` и `"event"` идут в `#picture` (рамка, `max-height: 16`).
  Рисунок события временный: на следующем ходу панель возвращает локацию (в бою остаётся скрытой, после боя локация возвращается).
  Заставка — в ленту при старте TUI (в узкий `#picture` она не влезает).
- События рисунков (death, victory, level_up) считаются только для обычного хода, не для команд (`/...`).
- Простой режим: из рисунков только заставка при старте (решение В-2).
- Оверлей `art/` паков пользователя — не сделан, место в API (`ART_DIR`, `load_art`) есть.

## F5. Меню боя «сначала цель» (`ui/combat_menu.py`, TUI)

Слой отображения поверх плоского `available_actions`: движок, `option_list`, промпты и простой режим не меняются (плоская
нумерация). `ui/combat_menu.py` (без Textual): `target_of`, `targets`, `default_target`, `short_label`, `fit`, `build_view`
→ `MenuView{target, targets, header, target_rows, free_rows, more}`, `CATEGORY_BY_KIND`/`RANK_BY_KIND` (новый kind без записи
— в «Ещё…»), `MAX_ROWS = 10`, `MenuState` (цель помнится между шагами боя, оглушающий, раскрытая группа). Блок цели: вся
доступная атака по цели (оружие вытесняется последним), переговоры, обезоруживание, заклинания (>2 — «Заклинания на цель ▸»);
бесцелевой: «Идти», Рывок, Уклонение, Отход, Второе дыхание, Стабилизировать, «Заклинания без цели ▸», «Закончить ход»;
последняя строка — «Ещё…» (`MoreModal`: полный плоский список). В TUI `CombatMenu` (`#actions`) с `TargetBar` и `MenuLine`:
цифры 1–9, 0 — строки, Tab/Shift+Tab — цель, F3 — оглушающий, F4 — «Ещё…», Esc — назад из группы; «цифра+Enter» в поле —
номер видимой строки. Выбор → `start_turn(плоский номер)`, эхо — полный label варианта.

## F7. Репорты (этап 6а, P0)

Пакет `src/ai_dm/reports/` (схема сейва не меняется): `capture.TurnCapture` (dataclass: номер хода, run_id хода и границы, фраза,
метки, статус `committed|aborted|none`, причина сбоя, бандл до и после хода, время, модель рассказчика), `markdown.render(capture, text)`
(чистая функция: текст игрока, метки, ход, мир/кампания, сид и состояние RNG до хода, модель), `writer.write_report(saves_root, world_id,
capture, text, now)` -> `saves/<мир>/issues/<YYYYMMDDTHHMMSS>-t<ход>-<метки через +|manual>/` с `report.md` и `meta.json`
(`report_format: 1`). Имя уникально (суффикс `-2`), запись через `tmp-*` и `os.replace`; `OSError` пробрасывается, `GameApp` превращает её
в строку «Репорт не записан: …». #21 ТО: один авто-репорт на попытку хода — `GameApp.already_reported(capture)` (ключ `turn_seq`, теги, `failure_reason`, модель; только `aborted`; `retry` на той же модели репорт не пишет, после смены модели — пишет; `load()` сбрасывает); лимит объёма: `[reports] max_mb = 200` (0 — без лимита), `reports/writer.py trim_issues(saves_root, world_id, max_mb)` после записи репорта удаляет самые старые каталоги `issues/` (кроме `tmp-*`, `manual` и самого нового), ошибки обрезки молча (`suppress(OSError)`). `reports` не импортирует `game`, `ui`, `master`.
- P1, полный репорт: `config.reports.recent_turns` (по умолчанию 5, `[reports]` в `app_defaults.toml`). `write_report(..., journal=None, recent_turns=5)`
  кладёт в каталог репорта: `before/` и `after/` (только у принятого хода) -- корни сейва, `load_slot(<отчёт>/before, world_id, "auto")`;
  `journal/calls.jsonl` -- записи журнала хода и границы (`Journal.records_for(run_ids)`, чтение с конца) и `journal/blobs/` --
  их блобы `system`/`tools` копией (журнал мира ротируется, репорт остаётся полным). `report.md`: последние N ходов (вместе с самим
  ходом, из `after`, иначе из `before`; меньше N в памяти -- пометка), модели по ролям из вызовов, по каждому вызову роль/модель/попытка/
  stop_reason/сообщения запроса и ответ (system и tools -- ссылкой на блоб). Ход без вызовов -- пустой `calls.jsonl`. `journal=None` --
  без `journal/`, в `report.md` «журнал отключён», `meta.json.replayable=false` (иначе true; `meta.calls` -- число записей).
  `TurnCapture.before/after` -- копии на момент хода (`TurnRunner.capture_of`), поэтому ручной `/report` после отката и выбора уровня
  видит состояние хода; у `status=none` `before` -- живой бандл, пишется сразу.
- `TurnRunner`: `TurnResult.run_ids` (основной run_id и `bnd-*` границы) и `before` (бандл до хода: ссылка, ход идёт на копии, а `finish_boundary`
  работает на своей копии); `last_capture` после каждого хода (`run_turn`, достройка границы в `retry`); метки границы сцены (`BoundaryResult.report_tags`
  из запросов world) попадают в итог хода без дублей, при сбое границы — тоже сохраняются (take_tags до проверки ошибки, решение ревью P0).
- `GameApp(auto_reports=True)`: если у хода есть метки — репорт и строка «Записан репорт: <путь>» в ответе, в том числе у откатанного хода.
  `ui.cli` ставит `auto_reports=False` при `--mock` и `--replay`. `/report <текст>` пишет всегда, относится к последнему ходу
  (`last_capture`; после `/load` сбрасывается и репорт — снимок текущего состояния без раздела хода); пустой текст — подсказка, файла нет.
- P2, `ai-dm --replay-report <каталог>`: `reports/replay.py` -- `load_report(path, context_for=None) -> ReportReplay` (`meta`, `before`, `expected`
  = `after/` или None у откатанного, `records` = `journal/calls.jsonl`, `player_input`, `now_iso` = `meta.now`, `failure_reason`; слоты
  грузятся `load_slot` из копии во временной папке, репорт не меняется), `compare(expected, actual) -> list[str]` (построчные расхождения
  дампов бандлов; из сравнения исключены только `TIME_FIELDS` = `manifest.saved_at`; не более 20 строк). Ход крутит `ui.cli.replay_report`
  (`reports` не импортирует `game`): `GameApp(auto_reports=False, use_stored_model=False, now=meta.now, sleeper=без паузы)` во временном
  `saves_root`, `ReplayAdapter` по ролям narrator/world/summarizer (нет записей роли -- адаптер None; `summarizer_backup` -- адаптер запасного вызова summarizer), модели запросов -- `requested_model`
  из записей (рассказчик -- `meta.model`), `app.handle(player_input)` или `choose("retry")` для достройки границы (`player_input=None`).
  Детерминизм: `run_id`/`stamp` в сообщения запроса не входят (отпечаток от них не зависит), `run_ids` границы идут отсортированно,
  `saved_at` -- единственное поле реального времени. Коды: 0 -- совпало; 1 -- расхождение состояния, причины сбоя или `ReplayDivergence`;
  2 -- несовместимые флаги, репорт нечитаем, `replayable=false` или `status=none`. Откатанный ход: ожидается та же `failure.reason`,
  состояние == `before`. `meta.replayable=false` и при пропавшем блобе system/tools.

## F8. Музыка и эмбиент (партия Му)

Пакет `src/ai_dm/audio/` (уровень `art`: не импортирует `game`, `ui`, `llm`, `master`, `protocol`; сейв v8 не меняется).
- `catalog`: `data/index.yaml` -> `AudioIndex` (`extra="forbid"`): `themes` (id -> `Theme(music, ambient)`, имена файлов в `data/`), `location_tags`
  (тег -> тема; порядок тегов локации -- приоритет), `locations` (точный id), `tone` (`horror_strong`, `default`), `combat`. `load_audio(folder)` -> `Audio(index,
  folder)`; `theme_for_tags`; `theme_files(index, folder, theme)` -> (музыка, эмбиент), нет файла -> `None`.
- `select`: `SoundState(location_id, tags, in_combat, horror, romance, scene_mood)`, `pick_theme(index, state)`: бой > сцена (`scene_mood`, если такая тема
  есть в `index.themes`) > id локации > первый тег > `horror == "сильно"` (мрачная) > «исследование». Настроение сцены
  ставит рассказчик запросом `scene_mood` (Ж3, BACKLOG 33): `romance` — по сюжету, независимо от `tone.romance`;
  `ui.screen.sound_state` берёт его из `current_scene`.
  Варианты по тону -- в `index.yaml`, не в коде: `tone.horror_variants` (при `horror == "сильно"` выбранная `nature` -> `wilds`; теги «чаща», «тёмный лес», «топь» ведут в `wilds` сразу) и
  `tone.romance_variants` (`romance == "откровенно"`: `romance` -> `romance_sensual`). Вариант по тону применяется и к теме сцены.
- `control`: `next_switch` (чистая: бой -- сразу, остальное -- не чаще `min_switch_s`), `SoundController(player, audio, cfg, prefs)` (`update(state)`, `command(arg)` --
  `/music`, `stop()`; `Lock`), `SilentSound(reason)` (простой режим, replay, mock), `make_sound(...)` -> (звук, строка ленты). Эмбиент привязан к теме
  (в бою его нет). Подавленная гистерезисом смена применяется на следующем шаге, таймера нет.
- `player`: `Player` (Protocol: `start() -> причина | None`, `set_layer(layer, path, fade_s)`, `set_volume`, `stop`), `NullPlayer`. Реальный плеер на miniaudio
  (`audio/miniaudio_player.py`, ленивый импорт внутри функций, extra `audio`): `PlaybackDevice` + бесконечный генератор-колбэк `generator()`;
  два `Layer` (музыка, эмбиент), у слоя текущий `Stream` и уходящие (линейная рампа гейна `gain_ramp` за `crossfade_s`, файл по кругу, позиция не
  хранится); `mix_chunk` -- сумма с клиппингом в `array("h")` (чистый Python, без numpy/audioop); эмбиент × `ambient_percent`, всё × громкость
  (`(volume/100)**2`). Колбэк и `set_layer` работают под одним `Lock`; `stop()` останавливает устройство вне lock. Ошибки декодирования --
  слой молчит; файл открывается вне `Lock` (под ним только перестановка ссылок); при `crossfade_s = 0` уходящий поток гаснет за ~10 мс.
  Известное ограничение: шов лупа -- файл переоткрывается прямо в колбэке (проверить на живом прогоне; при щелчке держать следующий генератор открытым заранее). `mix_chunk(parts, n)`: n -- сэмплы (кадры × 2). Ошибка устройства -- `start()` возвращает причину, `control` ставит `NullPlayer`.
- Подключение: `GameApp.audio` (по умолчанию `SilentSound("звук только в TUI")`; команда `/music` в `game/commands.py` общая для обоих режимов);
  `ui.screen.sound_state(app)` + `location_tag_chain`; `AiDmApp.show_step` зовёт `game.audio.update(...)` после каждого шага; `ui.cli.attach_sound`
  (из `cli.run_tui`) создаёт звук только в TUI; `ui.tui.run_tui` в `finally` зовёт `game.audio.stop()`.
- Настройки: `[audio]` в `app_defaults.toml` (`AudioConfig`); пользовательские -- `config/user.py`: `config_dir(env)` (`AI_DM_CONFIG_DIR` > `XDG_CONFIG_HOME/ai-dm` >
  `~/.config/ai-dm`), `config.toml` (руками) и `audio.toml` (пишет игра, поверх), `load_user_settings(env)` во всех точках входа cli (`prepare`, `--import`,
  `--replay-report`).
- Теги паков: `vale` (долина, таверна, подвал), `drunk_dragon/deep_shaft` (шахта); остальные локации берут тему родителя.

## К7д. Монстры SRD 5.2 ПО 0–5 и их черты (сейв v9 не меняется)

- Данные: `srd/data/monsters` (30 монстров), `srd/data/features` (механические черты `pack_tactics`, `undead_fortitude`,
  `death_burst` и описательные для рассказчика); происхождение — `srd/data/ATTRIBUTION.md`. Скрипт импорта вне репозитория.
- Модель (`content/models/monsters.py`): `MonsterAction.extra_damage_dice/extra_damage_type` (доп. урон другого типа),
  `MonsterAction.on_hit: HitRider` (состояние, необязательный спасбросок, `max_size`, `exempt`, длительность
  `target_turn`/`source_turn`/`minute`, урон при провале), `Monster.fly_ft`, `Monster.death_burst: DeathBurst`.
  Проверка ссылок и типов — `content/monster_checks.py` (из `loader.check_refs`).
- `rules/damage.DamageResult.damage_types` — типы урона, из которых сложен результат (пишет `apply_damage`, складывает
  `attack.merge_damage`).
- `combat/monster_traits.py`: `has_trait`, `pack_ally`, `PackTacticsSource` (регистрируется в `CombatEngine.__init__`, тег
  `pack` ставит `attack.attack_tags`), `endures` (зовёт `downed.after_damage` до `monster_damaged`), `extra_damage` и
  `on_hit` (зовёт `attack.attack` после `special_damage`, до `after_damage`; `AttackInfo.action` несёт действие монстра).
- Сонная стрела: `attack.arrow_conditions` → `attack.sleep_arrow` (`poison_immune`; спасбросок через `engine.save`, состояния
  через `engine.impose`); `downed.wake_sleeping` — первая строка `after_damage`, будит любым уроном > 0;
  `CombatEngine.start_turn` не зовёт `stealth.search` у недееспособного; `end.settle_ground` снимает у не-героев
  состояния с `Expiry rounds`; `PromptBuilder.combat_data` отдаёт монстрам `conditions`.
- `combat/death_burst.explode` — зовёт `downed.kill_monster` после события смерти; урон идёт через `engine.damage` и
  `downed.after_damage` (цепочка взрывов возможна).
- `combat/falling.hovers`: монстр с `fly_ft` не падает, пока дееспособен и не лежит. `rules/loot.NO_COIN_TYPES`: монет за
  зверей, конструктов и элементалей нет.
- Толчок: `shove.size_ok` (цель не больше чем на категорию крупнее) — `available.shove_options` и
  `improvise.size_problem` (`Rejected("target_too_large")` до броска).
- Рассказчик: `master/prompt.monster_trait_notes` → `combat.monster_traits` (только в бою, строки ≤ 100 символов); схема
  запросов не менялась.
- Сетка: `devtools/sim_cellar.py` (`CELLAR_POOL`, `fill_budget` — жадный набор по бюджету боя, `build_cellar`), сцена
  `cellar` в `sim_combat.SCENARIOS` и `sim_grid.SCENES`; `--difficulty` меняет её состав (`tier_of` → `party_budget`).
  Подвал Вейла: локация `old_crypt` (родитель `cellar`), тег `disarmer` у `goblin_boss` и `wight`.
