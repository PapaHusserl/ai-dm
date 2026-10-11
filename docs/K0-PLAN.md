# План партии К0: «движок уровней до 20, сейв v9» — К0а (схема v9, m0009, `pending_level`) и К0б (потолок 20, таблицы 1–20, клад/редкость)

Автор: папа-кабан, 2026-10-11. Статус: **предложение на аппрув** (решения проектировщика из `decisions/k0-grooming.md`, раздел
«Решения проектировщика (2026-10-11)», приняты за основу: В1а, В2а, В3а, В4а (пересмотр К-3), В5а, В6а, В7а «после сверки», В8а,
В9а (расширение К-4), В10а, В11а, В12 — список спутников). Основа: `decisions/k0-grooming.md` (ТЗ свинопаса, аудит свекрови),
`D1-PLAN.md`/`B3-PLAN.md` (форма), `decisions/roadmap-r4-unified.md` (#7 К0 стр. 58, раздел 3 «Сейв» стр. 117–124),
`ROADMAP-PLAN.md` (К-1…К-7), `BACKLOG.md` 1, 11, 16 (строки Т0 и партии А), 31, HANDOFF («Инструменты качества», «Правила
экономии»). Код на main ef2ed08: `state/{hero,creature,combat,world,save}.py`, `persistence/{store,migrations/*}.py`,
`rules/{progression,derived,rests,spellcasting,builder,damage,loot,xp}.py`, `game/{app,sheet_text,combat_flow}.py`,
`combat/actions/cast.py`, `combat/{available,end}.py`, `protocol/handlers/resources.py`, `campaign/{models,build}.py`,
`config/{settings.py,defaults.toml}`, `srd/data/tables/*.yaml`, `srd/data/classes/*.yaml`, тесты `tests/unit/{persistence,rules,
game,state,content,combat,protocol}`, `tests/schema/save_v8.schema.json`, фикстуры `tests/fixtures/saves/v0…v7, v4_dragon, v5_combat`.

**Критерий К0 (груминг «Готово, когда»):** копия живого мира (в тестах — фикстура `v4_dragon`, он и есть Грей 3 ур. следопыт/
Повелитель зверей) мигрирует в v9 и после загрузки даёт те же лист (`/sheet`), меню уровня, ячейки и пулы, что на main до
партии (golden-снимки, A7); `test_classes_build`: 5 классов поднимаются 1→20 с ПХ/чертой на каждом нужном уровне; меню уровня
переживает сохранение посреди выбора и загрузку (BACKLOG 11 закрыт); сейв **v9** (`m0009`, `MigrationContext` обязателен);
старые мутанты `migrate`, `load_slot`, `check_pack_refs` разобраны; тесты `tests/unit/persistence` проходят в изоляции
(`uv run pytest tests/unit/persistence`); `make smells` ≤ 206 (лимит не поднимать), `make cov` ≥ 94 %, `make dead` чисто;
живой прогон R4: Грей 3→4 (ПХ), сохранение посреди меню и загрузка — **после К0б** (`decisions/k0-live.md`).

**Не входит** (ТЗ груминга): механика мультикласса (К-мульти #24 — только поля и адаптер чтения), умения и пулы новых классов
(К2–К6), умения 6+ имеющихся классов (К8+, ступени II/III), концентрация по времени и `until_s` в логике (К1 — поле есть,
логика нет), снаряжение монстра/NPC в бою и трофеях (К7к — только поле), временная форма в логике (К5/К13 — только поле),
эпические дары как категория черт (К14), Наложение рук ×5 и ячейки сверх максимума от очков чародейства (К3/К5 — `EffectSpec`/
`sync_resources`, не схема), заговоры/известные заклинания по уровню (К2–К3), `weapon_mastery_count` по уровню (К2/К8), промпт
со списком спутников (Ж0), перенос `level_up` в протокол, скрипт выгрузки из SRD (К-1 → К7д).

## A0. Поправки фактов (проверено по коду и прогонами, 2026-10-11)
1. **`make smells` = 206/206, запас 0** (прогнано). `rules/progression.py` (386 строк, `choice_errors` ветвистая) и `game/app.py`
   (`GameApp` ≈ 30 методов) — правки в них только заменой строк, **новые функции — в новые модули** (`rules/level_up.py`,
   `persistence/migrations/m0009_v8_to_v9.py` с мелкими хелперами ≤ 4 параметров, ≤ 5 return). Правило Б1/Б2/Д1: новый код +0.
2. **Живой мир 29a049dc — все слоты `schema_version 4`** (сохранены 2026-10-04; с v5 по v8 мир не открывался). Значит
   миграция живого прогона — цепочка **v4 → v9** (`m0005…m0009`), а `m0006`/`m0007` требуют `MigrationContext` (цены, торговцы
   пака) — он уже подставляется `GameApp.load`/`cli.prepare`. У Грея в слоте `auto`: `concentration = "hunters_mark"` вне боя
   (BACKLOG 14), `companion` Акела (волк), `resources = {hit_dice, favored_enemy, spell_slot:1}`, `feature_options = {}`,
   `spells_prepared == spells_known` (4 заклинания), `active_combat` нет, 31 NPC без `creature`. Фикстура `tests/fixtures/saves/
   v4_dragon` — тот же герой (companion есть, концентрации нет) — её хватает для нейтральности; ветку «строка концентрации»
   покрывает raw-dict тест. Копии `saves/` в тесты не кладём (живой мир пользователя).
3. **Фикстуры сейвов: v0…v7, v8 нет.** Прецедент (`test_migration_v8.py`): «v7 сгенерирован движком v7 из v6». Поэтому первый шаг
   doeba — **на main до правок** сгенерировать `tests/fixtures/saves/v8` из `v7` текущим движком (`load_slot` + `save_slot`) и
   снять golden-снимки нейтральности (A7). `v5_combat` в `session.json` боя не содержит (`active_combat` отсутствует) — ветка
   `Participant.equipment` в m0009 проверяется raw-dict тестом.
4. **`level_draft` живёт только в `game/app.py`** (15 упоминаний); `save_current` при черновике бросает `ValueError("Сначала
   закончите выборы уровня")` — это и есть BACKLOG 11. `level_up` (progression.py:65–85) сразу меняет `level`, `hp_max`,
   `hp_current` и зовёт `sync_resources`; `campaign/build.py:84–94` поднимает пресеты циклом `level_up` + `apply_level_choices`
   — этот путь остаётся атомарным (пресет), меню игры переходит на `pending_level`.
5. **Радиус `sheet.class_id` / `sheet.level` / `sheet.subclass_id`** (grep): `class_id` — 10 модулей (derived 7, progression 10,
   sheet_text 4, prompt 2, commands, hero_create, divine, inventory, rests, tui/widgets по 1); `level` — 15 модулей; `subclass_id`
   — 6. С адаптером-свойствами (В1а) **ни одно чтение не меняется**; меняются только **записи**: `sheet.level += 1`
   (progression:82), `sheet.subclass_id = …` (progression:365) и конструктор `CharacterSheet(...)` в `rules/builder.py:489`.
   Pydantic v2 на нечастичной (не frozen) модели поддерживает `@property`, в том числе с сеттерами, но сеттеры **не делаем** —
   две записи правятся явно.
6. **Форма полей, которые меняют тип, а не добавляются:** `spells_known`/`spells_prepared` (`list` → `dict[class_id, list]`;
   36 файлов тестов), `feature_options` → `feature_choices` (17 файлов), `concentration` (`str` → модель; 14 файлов тестов, в
   коде: 4 записи `caster.concentration = spell.id` — cast.py:217/236/329, spellcasting.py:149; 5 чтений id — available.py:263,
   cast.py:203, combat_flow.py:121, end.py:123, spellcasting.py:126; остальные ~20 — `is None`/`is not None`, не меняются),
   `companion` → `companions` (5 файлов), ключ пула `hit_dice` (14 файлов). Это основная цена К0а (оценка L груминга
   подтверждена).
7. **`Table.rows: dict[str, int]`** (`content/models/tables.py`) — значения только целые, поэтому кубики урона по тяжести кладутся
   как `count`/`sides` (формула клада `hoard.yaml`: `<полоса>:<ключ>:count|sides`), а не строкой `"2d10"`.
   `test_srd_minimum.test_there_are_ten_srd_tables` перечисляет таблицы точно (в списке уже 12, имя теста устарело) — две новые
   (`pact_slots`, `damage_severity`) требуют правки списка (→ 14).
8. **Данные классов беднее, чем сказано в груминге:** строка `ability_score_improvement` есть **только у следопыта** (уровень 4);
   у воина, плута, жреца, волшебника нет ПХ даже на 4-м (fighter.yaml: `fighting_style`, `second_wind`, `weapon_mastery` 1 ур.;
   rogue: `weapon_mastery`; cleric/wizard: `spellcasting`). Значит К0б добавляет строки ПХ **4/8/12/16/19 всем пяти** (+ воин
   6/14, плут 10), а не «только 6+». Умение `features/ability_score_improvement.yaml` есть (без эффектов) — ссылки валидны.
   У жреца и волшебника `prepared: 4` без `prepared_by_level` — `prepared_limit` даёт 4 на любом уровне (ошибка данных 1–5,
   трек 1.5) — Q10.
9. **Потолок 5 в коде:** `MAX_LEVEL` (progression.py:15; импорт xp.py:2, sheet_text.py:19; комментарии settings.py:158,
   encounter_budget.yaml); `hazard_dice` (damage.py:121: `level > 5` → ValueError, единственный вызов — `roll_hazard`);
   `hoard_band`/`hoard_treasure` (loot.py:42–56, две полосы); валидаторы «ровно 1..5» (settings.py:159, 190); `rarity_exceeds_cap`
   читает `cfg.loot.rarity_cap_by_level[level]` → `KeyError` на 6-м; `gold_explicit_max_cp_by_level[level]` (resources.py:573) —
   то же. «Сетки combat/sim 1–5» из груминга (п. 8) **не подтвердились**: `devtools/sim_combat.py` уровней не перебирает.
   Таблицы `xp`, `proficiency` — уже 1–20; `spell_slots_full/half`, `encounter_budget` — 1–5.
10. **`sys.path`: 71 файл тестов** (persistence 2: `test_migration_v8.py` → `game_kit`, `test_save_trophies.py` → `protocol_kit`;
    game 14, scenarios 13, ui 12, tui 11, master 6 …). `pyproject` `[tool.pytest.ini_options] pythonpath = ["src"]` — штатная ручка
    для kit-каталогов. BACKLOG 16: «`test_game_app_load_shows_the_migration_warning` падает при изолированном запуске
    tests/unit/persistence», «test_migration_v6 не входит в выборку из-за game_kit».
11. **Старые мутанты (BACKLOG 16, Т0 и партия 0):** `migrate` (тексты исключений, `copy` vs `deepcopy`, `version = 1`),
    `check_pack_refs` (26, ветка `event.cause/owners`), `load_slot` (`FileNotFoundError`/`ValueError`). R4 #7 относит их к К0 —
    это единственная партия, где выжившие на **старых** строках чинятся (исключение из правила 4 экономии по прямому указанию R4).
12. **Промпт:** `PromptBuilder.sheet_data` (prompt.py:287–308) кладёт `class`, `subclass`, `spells_prepared`,
    `spells_always_prepared`, `spell_slots`, `favored_enemy`, `companion` (словарь). `narrator_rules.md:94` описывает «спутник —
    зверь героя». WINDOW мока `memory_script.py` = 22450 (Д1). Для одноклассового героя байты `sheet_data` можно не менять
    (`class`/`subclass` — свойства, `spells_prepared` — список класса, `companion` — первый спутник) — Q4.
13. **Тестов на main — 12 437**, cov 96,83 % (Д1). `CharacterSheet(` конструируется в 27 файлах тестов + `tests/unit/persistence/
    conftest.py`, `ranger_kit.make_class_hero`, `combat_kit` — kits правятся один раз; `LevelChoices` импортируется из
    `rules.progression` в 3 файлах тестов и `campaign/models.py`.
14. **Текста SRD 5.2 в репозитории нет** (только `srd/data/*.yaml` с `source: srd-5.2` и атрибуция в LICENSE). Числа раздела A8
    выписаны из SRD 5.2 (CC-BY-4.0) по памяти папы-кабана и перепроверяются кабаном при вводе по тексту SRD; тесты doeba
    проверяют инварианты и опорные значения (A8), а не переписывают таблицу.

## A. Архитектура

### A1. Схема v9 — `state/creature.py`, `state/hero.py`, `state/combat.py`, `state/world.py`, `state/save.py` (без правок)
- `state/creature.py`: `Concentration{spell_id: str, circle: int (ge=0), until_s: int | None = None}` (В4а; `until_s` — К1);
  `CreatureState.concentration: Concentration | None = None`. `TempForm{monster_id: str, source: str, until_s: int | None = None,
  temp_hp_granted: int = 0}` (В4а, по SRD 5.2: свои хиты сохраняются, временные = уровень/хиты формы);
  `CreatureState.temp_form: TempForm | None = None`. `Equipment{armor: str | None = None, shield: str | None = None, weapons:
  list[str] = []}` (В9а; здесь — самый нижний модуль, его импортируют и `hero`, и `combat`, и `world`).
- `state/hero.py`: `ClassLevel{class_id: str, level: int = 1 (ge=1), subclass_id: str | None = None}`;
  `CharacterSheet`: **убрать** поля `class_id`, `level`, `subclass_id`; добавить `classes: list[ClassLevel]` (`min_length=1`,
  первый — стартовый класс), `level_history: list[str]` (class_id на каждом уровне персонажа); `spells_known: dict[str, list[str]]`,
  `spells_prepared: dict[str, list[str]]` (ключ — class_id); `feature_choices: dict[str, list[str]]` вместо `feature_options`
  (параметр через `:`, напр. `pact_of_the_blade:longsword` — соглашение, кода в К0 нет); `spells_always_prepared:
  list[GrantedSpell]`, `GrantedSpell{spell_id: str, source: str, class_id: str | None = None, ability: str | None = None,
  pool: str | None = None}`. **Адаптер чтения (В1а):** `@property class_id` → `classes[0].class_id`; `level` → сумма уровней;
  `subclass_id` → `classes[0].subclass_id`; `primary` → `classes[0]`; метод `class_level(class_id) -> int` (0, если класса нет);
  `prepared_of(class_id=None) -> list[str]` и `known_of(class_id=None)` → `self.spells_prepared.setdefault(cid or self.class_id,
  [])` (живой список: и чтение, и `append`). Валидатор модели: class_id в `classes` уникальны; `len(level_history) == level`
  (сторож рассинхрона; m0009 и builder заполняют, `apply_level` дописывает).
  `LevelChoices` **переезжает сюда** из `rules/progression.py` (он теперь часть сейва внутри `PendingLevel`; `state` не вправе
  импортировать `rules`): поля те же, `feature_options` → `feature_choices: dict[str, list[str]]` (Q3). `PendingLevel{class_id:
  str, hp_gain: int (ge=1), draft: LevelChoices}`; `HeroState.pending_level: PendingLevel | None = None` (В3а);
  `HeroState.companions: list[Companion]` вместо `companion` (В12); `HeroState.attuned: list[str]` (В10а, пусто).
- `state/combat.py`: `Participant.equipment: Equipment | None = None`; `state/world.py`: `NPC.equipment: Equipment | None = None`
  (`None` = «не задано, по статблоку» — Q14). Ключи пулов (соглашение, в ARCHITECTURE): кости хитов `hit_dice:d{N}` (п. 3
  груминга), ячейки договора `pact_slot` (п. 6; появится с колдуном в К6).
- `tests/schema/save_v9.schema.json` — новый отпечаток (команда из `test_schema_fingerprint.py`), `save_v8` остаётся историей.

### A2. Миграция `m0009` — `persistence/migrations/m0009_v8_to_v9.py`, `persistence/migrations/__init__.py`
- `MigrationContext` (+): `class_hit_die: dict[str, int]` и `spell_level: dict[str, int]`, заполняются в `from_registry`
  (`registry.all("class")` → `hit_die`, `registry.all("spell")` → `level`); `migrate()`: контекст обязателен и для
  `migrate_v8_to_v9` (кортеж `(migrate_v5_to_v6, migrate_v6_to_v7, migrate_v8_to_v9)`); `CURRENT_SCHEMA_VERSION = 9`,
  `MIGRATIONS[8]`. Миграция заморожена: не импортирует `ai_dm.state`/`ai_dm.content` (сторож как в v8), чистая `dict -> dict`,
  вход не мутирует, `setdefault` — идемпотентна.
- Хелперы (каждый ≤ 4 параметров): `migrate_sheet(sheet)`: `classes = [{"class_id", "level", "subclass_id"}]` из трёх скаляров
  (`pop`), `level_history = [class_id] * level`, `spells_known = {class_id: старый список}`, `spells_prepared` так же,
  `feature_options` → `feature_choices = {k: [v]}` (`pop`), `spells_always_prepared = []`; `migrate_creature(creature, context)`:
  `concentration` строка → `{"spell_id": s, "circle": context.spell_level.get(s, 1)}` (неизвестное заклинание → `circle 1` + строка
  `report`, Q2), `temp_form = None`; `migrate_hero(hero, context)`: sheet, creature, `hit_dice` → `hit_dice:d{N}` по
  `context.class_hit_die[class_id]` (нет класса → `hit_dice:d8` + `report`, Q15), `companion` → `companions = [c]`/`[]` (`pop`),
  `attuned = []`, `pending_level = None`; мир: у каждого `world.npcs[*]` `equipment = None`, у `npc.creature` — `migrate_creature`;
  сессия: `active_combat.participants[*].equipment = None`, `participant.creature` — `migrate_creature`.
- Нейтральность (риск 2 груминга): всё, что выводится (`resource_maxes`, `spell_slots`, `always_prepared`), после миграции даёт
  те же числа; `sync_resources` при первой загрузке **не должен** завести второй пул костей (ключ уже `hit_dice:dN`).

### A3. Правила: уровень как список классов — `rules/builder.py`, `rules/progression.py`, `rules/derived.py`, `rules/rests.py`, `rules/spellcasting.py`
- `builder.py:489`: `CharacterSheet(classes=[ClassLevel(class_id=choices.class_id)], level_history=[choices.class_id],
  spells_known={class_id: cantrips + level1_spells}, spells_prepared={class_id: list(choices.prepared)}, …)`.
- `progression.py`: `level_up` → `apply_level(hero, registry, gain)` (`sheet.primary.level += 1`, `level_history.append(class_id)`,
  HP, `sync_resources`) + `hp_gain(hero, registry, hp_method, rng) -> int` (вынесено из `level_up`; `level_up` сохраняет сигнатуру
  для `campaign/build.py` и тестов); `apply_level_choices`: `sheet.primary.subclass_id = …`, `sheet.feature_choices[k] = list(v)`,
  `sheet.known_of().append` / `sheet.prepared_of().append`; `missing_choices`/`next_choice`/`choice_errors`/`choice_options`:
  `choices.feature_choices` (одно значение на умение в К0 — `[key]`; `option not in options` проверяется для каждого элемента);
  `spells_left`/`spell_candidates`/`spell_errors`: `sheet.prepared_of()`. `LevelChoices` импортируется из `state.hero`
  (реэкспорта нет — `campaign/models.py` и тесты переходят на `state.hero`).
- `derived.py`: `add_amount("class_level")` → `hero.sheet.class_level(class_id)`; `hero_feature_ids`: `for options in
  sheet.feature_choices.values(): for option_id in options`; `always_prepared` += `[g.spell_id for g in sheet.spells_always_prepared]`
  (поле не мёртвое; порядок — сначала умения, потом выбранные); `resource_maxes`: кости хитов по классам —
  `result[f"hit_dice:d{hit_die}"] = сумма уровней классов с этой костью` (в К0 — один класс); `LONG_REST_FULL = ("hit_dice:",
  "spell_slot:")`. Остальные чтения `sheet.class_id`/`level`/`subclass_id` — через свойства, без правок.
- `rests.py`: `hit_dice_pools(creature) -> list[tuple[str, ResourcePool, int]]` (ключ, пул, грани; по убыванию граней);
  `short_rest`: «хватает» = сумма `current` по пулам; тратится из первого пула с `current > 0`, кость — его грани (не `hit_die`
  класса); `long_rest` — по префиксу. `protocol/handlers/resources.py:656` `rest`: `have = сумма current` по `hit_dice_pools`.
- `spellcasting.py`: `start_concentration(hero, world, spell, circle)` → `Concentration(spell_id=spell.id, circle=circle)`;
  `drop_concentration`: `old = hero.creature.concentration.spell_id`; вызов из `cast_spell` (resources.py:458/471) передаёт
  `request.circle` (у заговора 0). `combat/actions/cast.py:217/236/329`: `caster.concentration = Concentration(spell_id=spell.id,
  circle=spell.level)` (апкаста в бою нет — BACKLOG 18, cast.py:238 «circle всегда равен кругу заклинания»; К1 подставит круг ячейки); чтения id
  (`available.py:263`, `cast.py:203`, `combat_flow.py:121`, `end.py:123`) → `.spell_id`; `rules/creatures.end_concentration`,
  `damage.concentration_check`, `downed.py`, `mortality_guard` — без правок (`None`-проверки).

### A4. Меню уровня через `pending_level` — `rules/level_up.py` (новый), `game/app.py`
- `rules/level_up.py` (плоские функции, импортирует `progression`): `begin_level_up(hero, registry, *, hp_method="average",
  rng=None) -> PendingLevel` — проверяет `pending_level is None` и потолок (иначе `ValueError`), считает `hp_gain`, ставит
  `hero.pending_level = PendingLevel(class_id=sheet.class_id, hp_gain=…, draft=LevelChoices(level=sheet.level + 1))`;
  `preview_hero(hero, registry) -> HeroState` — `hero.model_copy(deep=True)` + `apply_level(copy, registry, pending.hp_gain)` +
  `copy.pending_level = None` (герой «как будто уже поднялся»; все функции `progression` работают с ним без изменения сигнатур);
  `current_step(hero, registry) -> str | None` = `next_choice(preview, registry, draft)`; `step_options(hero, registry) ->
  list[str]` = `choice_options(preview, …, step, draft)`; `commit_level_up(hero, registry) -> ValidationErrors | None` —
  `choice_errors(preview, registry, draft)` (герой не тронут при ошибке) → `apply_level(hero, …)` → `apply_level_choices(hero, …,
  draft)` → `hero.pending_level = None`; `reset_draft(hero)` — новый пустой `LevelChoices` того же уровня. Уровень и HP
  применяются **только** в `commit` (В3а); до него герой играет на старом уровне.
- `game/app.py`: поле `level_draft` **удаляется**; `menu_for("level_up")`: `pending_level` есть → `step_options(hero, registry)`,
  иначе `LEVEL_MENU`; `choose_level_up`: нет `pending_level` → `begin_level_up` (`roll` — `Rng.from_state(world.rng)`, как
  сейчас), затем `current_step is None` → `commit_level_up` + `finish_level_up`; иначе сообщение «уровень N» заменить на
  «Опыта хватает на уровень N: выберите …» (уровень ещё не присвоен — текст Q-умолчание); `record_choice` пишет в
  `hero.pending_level.draft` (`feature_choices[step] = [key]`); `choose_level_choice`: после последнего шага `commit_level_up` →
  при отказе `reset_draft` + «Выборы начаты заново»; `save_current`: **снять** `ValueError` (сохранение посреди меню —
  штатно); `load` и `__init__`: `self.pending = "level_up"` если у текущего героя `pending_level is not None` (меню продолжается
  с текущего шага); `ui/session.py:36/107` (сравнение уровня до/после) работает: уровень растёт в последнем `choose`.
- `campaign/build.py:84–94` остаётся на `level_up` + `apply_level_choices` (пресет собирается атомарно, без `pending_level`);
  `preset.companion` → `hero.companions = [preset.companion.model_copy()]` (формат пака не меняется, версии пака нет).

### A5. Показ и промпт — `game/sheet_text.py`, `master/prompt.py`, `protocol/handlers/resources.py`
- `sheet_text`: `title_line` — свойства, без правок; строки заклинаний — `sheet.prepared_of()`/`known_of()`; варианты умений —
  `feature_choices` (через запятую); «Зверь-спутник: …» — строка на каждого из `companions`.
- `prompt.sheet_data`: `spells_prepared` → `sheet.prepared_of()`; `companion` — **ключ и форма сохраняются**, значение — первый
  спутник (`companions[0]`), нет спутников — ключа нет (байты промпта и WINDOW 22450 не меняются; список — Ж0, Q4).
- `resources.cast_spell`: `result["concentration"] = spell.id` — без изменений по смыслу (берётся из `Concentration.spell_id`).

### A6. Изоляция тестов и старые мутанты (doeba; код продукта не трогается)
- `pyproject.toml` `[tool.pytest.ini_options] pythonpath` += каталоги kit-ов (`tests`, `tests/unit/{campaign,rules,reports,ui,llm,
  combat,world_sim,protocol,game,audio,master,persistence}`); в `tests/unit/persistence/*` вставки `sys.path` **убираются**
  (2 файла), остальные 69 — строка в BACKLOG 16 «механическая чистка `sys.path` после `pythonpath`» (Q5). Проверка:
  `uv run pytest tests/unit/persistence -q` зелёный сам по себе; `test_game_app_load_shows_the_migration_warning` проходит.
- Мутанты: `make mutate FUNCS="ai_dm.persistence.migrations:migrate ai_dm.persistence.store:load_slot"
  TESTS="tests/unit/persistence"` и `FUNCS="ai_dm.campaign.loader:check_pack_refs" TESTS="tests/unit/campaign"`; выжившие на
  старых строках добиваются тестами (тексты исключений `SaveTooNew`/`MigrationMissing`/`FileNotFoundError`/`ValueError`,
  `deepcopy` — входной словарь не мутируется и после двух звеньев, ветка `event.cause`/`owners` в `check_pack_refs`). Остаток с
  обоснованием «эквивалентный мутант» — BACKLOG 16 с пометкой «разобран в К0а».

### A7. Нейтральность миграции (тестовая схема, doeba)
- **До правок, на main:** `tests/fixtures/saves/v8` (из `v7` движком); golden-снимки героя `v4_dragon` после загрузки движком
  main: `tests/golden/k0_sheet_v4_dragon.txt` (`sheet_text` полного `/sheet`), `tests/golden/k0_sheet_data_v4_dragon.json`
  (`PromptBuilder.sheet_data` + `spell_slots` + `resource_maxes`), `tests/golden/k0_level_menu_v4_dragon.json` (меню уровня 3→4:
  шаги `next_choice` и `choice_options` по шагам при `LevelChoices` пустом, после `level_up(average)` на копии).
- **После правок:** те же снимки с v9 совпадают байт-в-байт (`/sheet`, `sheet_data`) и по содержанию (меню: последовательность
  шагов и варианты — через `preview_hero`/`current_step`/`step_options`). Это и есть «те же лист, меню, ячейки, пулы».
- Двойная загрузка (`load_slot` дважды — один бэкап), `resave` байт-стабилен (ключи `spells_*` и `hit_dice:dN` пишутся m0009 всегда,
  поэтому чтение `prepared_of()` не меняет сериализацию).

### A8. К0б: потолок из данных и таблицы 1–20 — `rules/{progression,xp,damage,loot}.py`, `config/{settings.py,defaults.toml}`, `srd/data/tables/*.yaml`, `srd/data/classes/*.yaml`, `game/sheet_text.py`
- **Потолок (В6а):** `max_level(registry) -> int` в `progression.py` = наибольший ключ таблицы `xp` (Q6); `MAX_LEVEL` удаляется;
  `check_level(level, registry)`, `level_for_xp` (цикл до `max_level`), `can_level_up`, `level_up`/`begin_level_up` — через
  `max_level`; `xp.quest_xp` и `sheet_text.title_line` — `max_level(registry)`; комментарии settings.py:158 и
  `encounter_budget.yaml` — убрать «MAX_LEVEL этапа 1». `choice_options("asi_or_feat")` уже режет характеристики ≤ 20.
- **Ячейки (SRD 5.2, таблицы классов; `spell_slots_full.yaml` 6–20):** 6: 4/3/3; 7: 4/3/3/1; 8: 4/3/3/2; 9: 4/3/3/3/1;
  10: 4/3/3/3/2; 11–12: 4/3/3/3/2/1; 13–14: 4/3/3/3/2/1/1; 15–16: 4/3/3/3/2/1/1/1; 17: 4/3/3/3/2/1/1/1/1; 18: 4/3/3/3/3/1/1/1/1;
  19: 4/3/3/3/3/2/1/1/1; 20: 4/3/3/3/3/2/2/1/1. **`spell_slots_half.yaml` 6–20** (паладин/следопыт 2024, ячейки с 1 ур.):
  6: 4/2; 7–8: 4/3; 9–10: 4/3/2; 11–12: 4/3/3; 13–14: 4/3/3/1; 15–16: 4/3/3/2; 17–18: 4/3/3/3/1; 19–20: 4/3/3/3/2.
  Третичной таблицы нет (В5а). **`pact_slots.yaml`** (новая, `source: srd-5.2`, ключи `'L:count'`, `'L:circle'`): 1: 1/1; 2: 2/1;
  3–4: 2/2; 5–6: 2/3; 7–8: 2/4; 9–10: 2/5; 11–16: 3/5; 17–20: 4/5.
- **Бюджет боя (`encounter_budget.yaml` 6–20, SRD 5.2 «XP Budget per Character», low/moderate/high):** 6: 600/1000/1400;
  7: 750/1300/1700; 8: 1000/1700/2100; 9: 1300/2000/2600; 10: 1600/2300/3100; 11: 1900/2900/4100; 12: 2200/3700/4700;
  13: 2600/4200/5400; 14: 2900/4900/6200; 15: 3300/5400/7800; 16: 3800/6100/9800; 17: 4500/7200/11700; 18: 5000/8700/14200;
  19: 5500/10700/17000; 20: 6400/13200/22000. Строки 1–5 в файле совпадают с SRD (проверено).
- **Урон по тяжести (`damage_severity.yaml`, новая, SRD 5.2 «Damage Severity and Level», полосы по уровню):** 1–4: 1d10 / 2d10 /
  4d10; 5–10: 2d10 / 4d10 / 10d10; 11–16: 4d10 / 10d10 / 18d10; 17–20: 10d10 / 18d10 / 24d10 (nuisance/dangerous/deadly); ключи
  `'1-4:nuisance:count': 1`, `'1-4:nuisance:sides': 10` …. `damage.py`: константы `HAZARD_DICE*` удаляются, `hazard_dice(level,
  severity, registry) -> str` читает таблицу по `level_band(level)`; `roll_hazard` передаёт `registry`. Нынешние значения 1–4 и 5
  совпадают с SRD (проверено).
- **Клад и редкость (В7а после сверки):** в тексте SRD 5.2 (CC-BY) **нет** таблиц клада/индивидуального сокровища (глава «Treasure»
  — не SRD; как и в 5.1), а таблица редкости магических предметов даёт только ценность (common 100 зм … legendary 200 000 зм), без
  столбца «уровень персонажа». Поэтому `hoard.yaml` остаётся `source: custom`, числа — по правилу проекта «≈ вдвое больше
  индивидуального за 3–5 врагов» (средние: 0-4 ≈ 98 зм, 5-10 ≈ 1015 зм — как сейчас): **11-16** — sp 2d6×20 000 мм, gp
  2d6×100 000 мм, pp 1d6×100 000 мм (≈ 11 900 зм; индивидуальное 4d6×10 000 мм ≈ 1400 зм × 4 × 2 ≈ 11 200); **17+** — gp
  2d6×300 000 мм, pp 2d6×400 000 мм (≈ 49 000 зм; 7000 × 4 × 2 = 56 000) — Q8. `loot.py`: `level_band(level)` (1–4 / 5–10 /
  11–16 / 17+, та же разметка, что `treasure_band` по CR), `hoard_band` = старшая `treasure_band` среди побеждённых,
  `hoard_treasure(level)` — `level_band`; комментарий «ждут утверждения» заменить на «утверждено К0б (дата)». Редкость
  (`defaults.toml [loot.rarity_cap_by_level]`): 1–4 `uncommon`, 5–10 `rare`, 11–16 `very_rare`, 17–20 `legendary` (полосы те же, что у
  сокровища; источник — проектное решение, не SRD) — Q8.
- **Конфиг:** `settings.py` — `LEVEL_CAP = 20`; валидаторы `LimitsConfig`/`LootConfig`: «ключи ровно 1..LEVEL_CAP» (Q7) + тест-сторож
  `LEVEL_CAP == max_level(load_registry())`; `defaults.toml [limits.gold_explicit_max_cp_by_level]` 6–20 (зм): 6: 1500, 7: 2000,
  8: 3000, 9: 4000, 10: 5000, 11: 7500, 12: 10 000, 13: 12 500, 14: 15 000, 15: 20 000, 16: 25 000, 17: 35 000, 18: 50 000, 19: 75 000,
  20: 100 000 (в мм ×100) — Q9.
- **Классы (данные, код — ноль):** строки `{level: N, feature: ability_score_improvement}` — всем пяти на 4/8/12/16/19 (следопыту
  — добавить 8/12/16/19), воину + 6/14, плуту + 10; уровень 19 — заглушка ПХ до К14 (`epic_boon`, Q11). `prepared_by_level`
  1–20 (Q10): жрец 4,5,6,7,9,10,11,12,14,15,16,16,17,17,18,18,19,20,21,22; волшебник 4,5,6,7,9,10,11,12,14,15,16,16,17,18,19,21,
  22,23,24,25; следопыт 2,3,4,5,6,6,7,7,9,9,10,10,11,11,12,12,14,14,15,15 (SRD 5.2 таблицы классов).
- `test_srd_minimum.py`: список таблиц 12 → 14 (`pact_slots`, `damage_severity`), имя теста «ten» → по числу.

### A9. Документы
ARCHITECTURE: часть A — `CharacterSheet.classes`/`level_history`/`feature_choices`/`spells_*` по классам/`spells_always_prepared`,
`HeroState.pending_level`/`companions`/`attuned`, `CreatureState.concentration: Concentration`/`temp_form`, `Participant.equipment`/
`NPC.equipment`, ключи пулов `hit_dice:dN`/`pact_slot`; раздел «E9. Сейв v9 (К0а)» по образцу E6 (m0009, контекст обязателен,
`class_hit_die`/`spell_level`, отпечаток v9); `rules/level_up.py` и правило «уровень и HP применяются при commit»; таблицы
`pact_slots`/`damage_severity`, `max_level`, полосы `level_band`. README/`--help`: ничего (поведение команд не меняется), кроме
фразы «сохранение посреди выбора уровня — штатно». BACKLOG: 1 — ✅ «потолок, таблицы ячеек/бюджета/урона, ПХ 4–19, редкость» (остаток
— умения 6+, заклинания 4–9 кругов, монстры — К8+/К7д/Ж4), 11 — последняя строка ✅, 14 — пометка «поле `until_s` есть с v9, логика
К1», 16 — мутанты Т0/партии 0 ✅ или уточнение, строки изоляции ✅ + новая строка про 69 файлов `sys.path`, 31 — ссылка «ПХ и
`prepared_by_level` 1–20 уже в данных». `decisions/roadmap-r4-unified.md` стр. 58 — пометка «ПХ: меню data-driven, только
данные; сетки sim 1–5 — не подтвердилось». HANDOFF: «Где мы», версии сейва (v9 ✅), инструменты качества (без изменений), расходы.
`decisions/k0a-review.md`, `decisions/k0b-review.md`, `decisions/k0-live.md`, `docs/checklist-k0-live.md` (не коммитить).

## B. Партии

### B1. К0а (M–L, сейв v9) — порядок шагов kaban
0. (doeba, до правок kaban, A7/A0.3) фикстура `v8`, golden-снимки `v4_dragon`, `pythonpath` + изоляция persistence (A6).
1. `state/creature.py` — `Concentration`, `TempForm`, `Equipment`, поля `CreatureState` (A1).
2. `state/hero.py` — `ClassLevel`, `GrantedSpell`, `LevelChoices`, `PendingLevel`; `CharacterSheet` (поля, свойства, `class_level`,
   `prepared_of`/`known_of`, валидатор); `HeroState.pending_level`/`companions`/`attuned` (A1). `state/combat.py`, `state/world.py`
   — `equipment` (A1). Отпечаток `tests/schema/save_v9.schema.json`.
3. `persistence/migrations/m0009_v8_to_v9.py`, `__init__.py` (`MigrationContext`, `migrate`, версия 9) (A2).
4. `rules/builder.py`, `rules/progression.py` (`apply_level`, `hp_gain`, `feature_choices`, `prepared_of`), `rules/derived.py`,
   `rules/rests.py`, `rules/spellcasting.py` (A3); `campaign/models.py` (импорт `LevelChoices`), `campaign/build.py` (`companions`).
5. `combat/actions/cast.py`, `combat/available.py`, `combat/end.py`, `game/combat_flow.py`, `protocol/handlers/resources.py`
   (`rest`, `cast_spell` — `circle`) (A3).
6. `rules/level_up.py`; `game/app.py` (A4). 7. `game/sheet_text.py`, `master/prompt.py` (A5).
8. Доки (A9), BACKLOG 11/16. `make smells` ≤ 206 после каждого шага; `make dead` (новые поля читаются: `attuned` — только
   миграцией и схемой: если vulture пометит — **не** в allowlist, а `sheet_text` строка «Настроено: …» при непустом списке).

### B2. К0б (M, v9 без миграции) — порядок шагов kaban
1. `srd/data/tables/spell_slots_full.yaml`, `spell_slots_half.yaml`, `pact_slots.yaml`, `encounter_budget.yaml`, `damage_severity.yaml`,
   `hoard.yaml` (A8). 2. `srd/data/classes/*.yaml` — ПХ, `prepared_by_level` (A8, Q10/Q11). 3. `rules/progression.py` (`max_level`,
   `check_level`), `rules/xp.py`, `game/sheet_text.py` (A8). 4. `rules/damage.py`, `rules/loot.py` (A8). 5. `config/settings.py`,
   `config/defaults.toml` (A8). 6. Доки (A9), BACKLOG 1/31, R4 стр. 58; `docs/checklist-k0-live.md`.
7. Живой прогон пользователя: копия мира 29a049dc (бэкап слотов — `backups/` делает `load_slot` сам), загрузка → предупреждения
   миграции (`report`) нет; `/sheet` как прежде; ход с опытом до 2700 (или `award_xp` по сюжету) → меню «уровень 4» → HP → ПХ
   `dex+2` → **выйти/сохранить посреди меню** (`/save`, `/quit`) → загрузить → меню продолжается с того же шага → завершить →
   `/sheet`: 4 ур., Лов +2, кости хитов `4`. Результат → `decisions/k0-live.md`.

### B3. Тесты kaban-doeba (tests/**, TDD)
**К0а**
- `tests/unit/state/test_save_bundle.py` / новый `test_hero_sheet_v9.py`: `CharacterSheet(classes=[…], level_history=[…])` —
  `class_id`/`level`/`subclass_id`/`primary` свойства; `level` = сумма при двух классах; `class_level("wizard") == 0`;
  `prepared_of()` создаёт ключ и возвращает живой список (`append` виден в `spells_prepared`); пустой `classes` → ошибка;
  повтор class_id → ошибка; `len(level_history) != level` → ошибка; `class_id=`/`level=` в конструкторе → ошибка (`extra forbid`,
  Q1а); `Concentration`, `TempForm`, `Equipment`, `GrantedSpell`, `PendingLevel` сериализуются/читаются; `HeroState.companions`
  по умолчанию `[]`, `attuned` `[]`, `pending_level` `None`. `test_schema_fingerprint.py`: v9 знает `ClassLevel`, `PendingLevel`,
  `Concentration`, `TempForm`, `Equipment`, `GrantedSpell`; у `CharacterSheet` нет `class_id`/`level`/`subclass_id`/`feature_options`;
  у `HeroState` нет `companion`.
- `tests/unit/persistence/test_migration_v9.py` (образец v8): реестр `MIGRATIONS[8]`, `CURRENT_SCHEMA_VERSION == 9`; без контекста —
  `MigrationContextRequired`; `from_registry` даёт `class_hit_die["ranger"] == 10`, `spell_level["hunters_mark"] == 1`; raw-dict
  v8 → sheet: три скаляра ушли, `classes == [{"class_id": "ranger", "level": 3, "subclass_id": "beast_master"}]`,
  `level_history == ["ranger"]*3`, `spells_known/prepared == {"ranger": [...]}` (пустой список → `{"ranger": []}`),
  `feature_options {"hunters_prey": "colossus_slayer"}` → `feature_choices {"hunters_prey": ["colossus_slayer"]}`,
  `spells_always_prepared == []`; hero: `companion` dict → `companions == [dict]`, `None` → `[]`, `attuned == []`,
  `pending_level is None`; creature: `concentration "hunters_mark"` → `{"spell_id": "hunters_mark", "circle": 1, "until_s": None}`,
  неизвестное → `circle 1` + строка `report`, `None` → `None`, `temp_form None`; `hit_dice` → `hit_dice:d10` (follower d8 → `d8`),
  неизвестный класс → `d8` + `report`; NPC с `creature.concentration` строкой и без — обе ветки; `world.npcs[*].equipment is None`;
  `session.active_combat.participants[*].equipment is None` и `participant.creature.concentration` мигрирует; словарь без
  `world`/`session`/`heroes` — не падает; вход не мутируется; идемпотентность (повторный прогон на уже-v9 словаре не ломает —
  `setdefault`); сторож импортов. Фикстура `v8`: `load_slot` → v9, бэкап байт-в-байт, перезапись слота v9 (в `hero.json` есть
  `classes`, нет `class_id`), два `load_slot` — один бэкап, resave байт-стабилен, `SaveTooNew` для движка v8; цепочка всех
  старых фикстур (`v0…v7`, `v4_dragon`, `v5_combat`) → 9. **Нейтральность (A7):** golden `/sheet`, `sheet_data`, меню уровня —
  совпадают; `resource_maxes` после `sync_resources` не заводит `hit_dice` второй раз; мок-ход на мигрированном `v4_dragon`
  (образец `played_dump`) проходит.
- `tests/unit/rules/test_progression.py` (±): `level_up` → `primary.level`, `level_history` дописан, HP, `sync_resources`;
  `apply_level_choices` пишет `subclass_id` в `primary`, `feature_choices[k] == [v]`, заклинания в `prepared_of()`;
  `choice_errors` с `feature_choices` (вариант вне списка → `option_invalid`); `spell_candidates` не предлагает уже подготовленные
  по классу; `hp_gain` average/roll/без rng → `ValueError`.
- `tests/unit/rules/test_level_up.py` (новый): `begin_level_up` → `pending_level` (class_id, `hp_gain`, `draft.level == level+1`), герой
  не изменился (уровень, HP, пулы); повторный `begin` → `ValueError`; на потолке → `ValueError`; `preview_hero` — уровень +1, HP +gain,
  `pending_level None`, исходный не тронут; `current_step`/`step_options` для следопыта 3→4 = `asi_or_feat` с вариантами
  `dex+2`, …, черты; `commit` без выбора → `ValidationErrors`, герой не тронут; `commit` с `asi {"dex": 2}` → уровень 4, HP +gain,
  Лов +2, `feats` += ASI, `pending_level None`, `hit_dice:d10` max 4; `commit` с `roll` — `hp_gain` из `begin`, не перебрасывается;
  `reset_draft`.
- `tests/unit/game/test_game_level_choices.py` (±): меню «average/roll» → `pending_level` создан, уровень
  в `/sheet` ещё старый; `save_current("manual-x")` посреди меню **не бросает**; `load("manual-x")` → `pending == "level_up"`, меню
  с того же шага; `GameApp(bundle с pending_level)` → `pending == "level_up"` сразу; ошибка выборов → «Выборы начаты заново»,
  `pending_level` остаётся; после завершения `pending_level None`, `/sheet` 4 ур.; `ui/session` показывает строку уровня после
  commit (регресс `test_ui_session`). `test_sheet_groups.py`: два спутника → две строки; `feature_choices` в выводе.
- `tests/unit/combat`, `tests/unit/rules/test_spellcasting*.py`, `tests/unit/protocol/test_cast_spell*.py` (±): после каста
  `creature.concentration == Concentration(spell_id=…, circle=…)` (в бою круг = `spell.level`; вне боя — `request.circle`, заговор 0);
  `end_concentration` → `None`; `concentration_line` берёт `spell_id`; перенос Метки (`transfer_mark`) читает `spell_id`;
  `drop_concentration` снимает эффекты по старому `spell_id`.
- `tests/unit/rules/test_rests.py` (±): `hit_dice:d10` тратится костью d10; при двух пулах (`d10` 1 и `d8` 2) — сначала d10, потом d8;
  «не хватает» по сумме; длинный отдых восстанавливает оба; `rest`-хендлер режет по сумме.
- `tests/unit/master/test_master_prompt*.py` (±): `sheet_data` байт-в-байт как golden; `companion` — первый спутник; без спутников —
  ключа нет; `tests/scenarios/test_stage4_memory.py` WINDOW 22450 без правок (если упадёт — стоп и вопрос, не подбирать окно).
- `tests/unit/campaign/test_pack_build.py` (±): пресет с `level: 3` собирается (`level_history` длины 3), `preset.companion` →
  `companions == [c]`. `test_architecture.py`: `state.hero` не импортирует `rules`; `rules/level_up.py` не импортирует `game/ui`;
  `m0009` — сторож импортов.
- Изоляция и мутанты — A6; FUNCS К0а (TESTS — только каталоги соответствующих тестов):
  `ai_dm.persistence.migrations.m0009_v8_to_v9:migrate_v8_to_v9 …:migrate_sheet …:migrate_creature …:migrate_hero`,
  `ai_dm.persistence.migrations:migrate ai_dm.persistence.migrations:MigrationContext.from_registry ai_dm.persistence.store:load_slot`,
  `ai_dm.state.hero:CharacterSheet.class_level …:CharacterSheet.prepared_of …:CharacterSheet.known_of …:CharacterSheet.<валидатор>`,
  `ai_dm.rules.level_up:begin_level_up …:preview_hero …:current_step …:step_options …:commit_level_up …:reset_draft`,
  `ai_dm.rules.progression:level_up …:apply_level …:hp_gain …:apply_level_choices …:choice_errors …:spell_candidates …:spells_left`,
  `ai_dm.rules.derived:resource_maxes …:always_prepared …:hero_feature_ids …:add_amount`, `ai_dm.rules.rests:hit_dice_pools …:short_rest
  …:long_rest`, `ai_dm.rules.spellcasting:start_concentration …:drop_concentration`, `ai_dm.rules.builder:build_character` (новые строки),
  `ai_dm.game.app:GameApp.menu_for …:choose_level_up …:record_choice …:choose_level_choice …:save_current …:load`,
  `ai_dm.game.combat_flow:concentration_line`, `ai_dm.combat.actions.cast:cast_mark …:transfer_mark` (новые строки),
  `ai_dm.protocol.handlers.resources:rest …:cast_spell` (новые строки), `ai_dm.campaign.build:build_hero`, `ai_dm.campaign.loader:check_pack_refs`.
  `ui.tui.*` не мутировать.

**К0б**
- `tests/unit/content/test_srd_minimum.py` / новый `test_tables_1_20.py`: 14 таблиц; `spell_slots_full`: ключи для всех уровней
  1–20, круги 1–9, ячеек ≤ 4, число ячеек круга не убывает с уровнем, опорные: `17:9 == 1`, `18:5 == 3`, `20:7 == 2`, `20:6 == 2`,
  `13:7 == 1`, у 6 нет 4-го круга; `spell_slots_half`: круги ≤ 5, `5:2 == 2`, `9:3 == 2`, `13:4 == 1`, `17:5 == 1`, `20:5 == 2`,
  у 19 нет 6-го; `pact_slots`: `count` 1/2/3/4 на 1/2/11/17, `circle` 1…5 на 1/3/5/7/9, далее 5; `encounter_budget`: 60 ключей,
  low < moderate < high, не убывает по уровню, `20:moderate == 13200`, `11:high == 4100`; `damage_severity`: 4 полосы × 3
  тяжести, `17-20:deadly` = 24d10, `5-10:deadly` = 10d10; `hoard`: полосы `11-16`, `17+`, средние ≈ 11 900 / 49 000 зм
  (Q8), `source: custom` сохранён; `individual_treasure` не менялась.
- `tests/unit/rules/test_progression.py` (±): `max_level(registry) == 20`; `check_level(21)` → `ValueError`; `level_for_xp(355000) ==
  20`, `(354999) == 19`; `can_level_up` на 20 → False; `level_up` на 20 → `ValueError`; `proficiency_bonus(20) == 6`.
  `test_xp.py`: `quest_xp` на 20 → 0, на 19 — доля от 50 000. `test_damage.py` (±): `hazard_dice(level, severity, registry)` по полосам
  (1, 4, 5, 10, 11, 16, 17, 20), 0 и 21 → `ValueError`, неизвестная тяжесть → `ValueError`; `roll_hazard` на 12 ур. — 4d10/10d10/18d10.
  `test_loot.py` (±): `level_band`, `hoard_band` по старшему CR (CR 12 → `11-16`, CR 20 → `17+`), `hoard_treasure(level=15)` в
  диапазоне формулы, `rarity_exceeds_cap` на 6 (rare ок, very_rare нет), 11 (very_rare ок), 17 (legendary ок, artifact нет).
  `test_settings.py` (±): ключи `1..20` обязательны (19 или 21 → ошибка), `LEVEL_CAP == max_level(registry)`, значения defaults
  по A8. `test_sheet_text.py`: `title_line` на 20 — без «/порог».
- **`test_classes_build`** (новый, `tests/unit/rules/test_classes_1_20.py`): для каждого из 5 классов герой 1 ур. (kits) →
  цикл `level_up(average)` + `required_choices` на каждом уровне: `asi_or_feat` ровно на 4/8/12/16/19 (+6/14 воин, +10 плут),
  `subclass` на 3 (только у классов с подклассами в данных — сейчас следопыт), `apply_level_choices` с `asi` по кругу
  характеристик (не выше 20) — доходит до 20 без `ValidationErrors`; `spell_slots` на 20: full → 9-й круг, half → 5-й;
  `prepared_limit` жрец 20 → 22, волшебник 20 → 25, следопыт 20 → 15 (Q10); `hero_feature_ids` без дублей ПХ-умения не требуется
  (оно повторяется по числу строк — зафиксировать как факт).
- FUNCS К0б: `ai_dm.rules.progression:max_level …:check_level …:level_for_xp …:can_level_up`, `ai_dm.rules.xp:quest_xp`,
  `ai_dm.rules.damage:hazard_dice …:roll_hazard`, `ai_dm.rules.loot:level_band …:hoard_band …:hoard_treasure …:rarity_exceeds_cap`,
  `ai_dm.config.settings:LimitsConfig.check_levels …:LootConfig.check_levels`, `ai_dm.game.sheet_text:title_line`.

## C. Качество
- `SMELLS_MAX = 206`, новый код +0: новые функции — в `rules/level_up.py` и `m0009` (плоские, ≤ 4 параметров, ≤ 5 return, без
  замыканий — mutmut); `GameApp` — замена строк, без новых методов (кроме замены `level_draft`-веток); `progression.py` —
  `apply_level`/`hp_gain` вынос **уменьшает** `level_up`. Превысили — стоп и перепланировка (не поднимать).
- `make cov` ≥ 94 %; `make dead` чисто (`attuned`, `temp_form`, `equipment`, `until_s`, `GrantedSpell.ability/pool` читаются
  миграцией/валидацией; если vulture пометит поля pydantic — это не бывает: поля моделей vulture не считает).
- Полный `pytest` и `make cov` — один раз в конце каждой партии; `make smells` — после каждого шага kaban; mutmut — фоном по FUNCS,
  узкие `TESTS` (правило Д1: `tests/unit/ui/tui` не включать).
- Коммиты — по партиям, только пути партии: К0а — `src/ai_dm/state/*`, `src/ai_dm/persistence/migrations/*`, `src/ai_dm/rules/{builder,
  progression,derived,rests,spellcasting,level_up}.py`, `src/ai_dm/combat/{available,end}.py`, `src/ai_dm/combat/actions/cast.py`,
  `src/ai_dm/game/{app,sheet_text,combat_flow}.py`, `src/ai_dm/master/prompt.py`, `src/ai_dm/protocol/handlers/resources.py`,
  `src/ai_dm/campaign/{models,build}.py`, `pyproject.toml`, `tests/**` (вкл. `tests/fixtures/saves/v8`, `tests/golden/k0_*`,
  `tests/schema/save_v9.schema.json`), `docs/{ARCHITECTURE,BACKLOG,HANDOFF,K0-PLAN}.md`, `docs/decisions/k0a-review.md`;
  К0б — `src/ai_dm/srd/data/{tables,classes}/*.yaml`, `src/ai_dm/rules/{progression,xp,damage,loot}.py`, `src/ai_dm/config/*`,
  `src/ai_dm/game/sheet_text.py`, `tests/**`, доки, `docs/decisions/{k0b-review,k0-live,roadmap-r4-unified}.md`. Без `checklist-*.md`,
  без `saves/`.

## D. Риски
1. **Радиус правок К0а** (риск 3 груминга) — ограничен адаптером: чтения не трогаются; меняются записи (2), конструктор (1),
   `spells_*` (≈ 12 строк кода), `feature_choices` (≈ 8), концентрация (9 строк), `hit_dice` (4 места), `companion` (4). Тестовый
   радиус больше (36 + 17 + 14 + 14 + 5 файлов) — работа doeba, kits правятся один раз (`ranger_kit.make_class_hero`,
   `persistence/conftest.py`, `combat_kit`).
2. **Нейтральность** (риск 2): замер — golden до правок (A7). Ловушка: `prepared_of()` с `setdefault` **на чтении** меняет
   сериализацию, если ключа нет — m0009/builder пишут ключ всегда; тест resave байт-стабилен это ловит.
3. **`pending_level` и опыт:** герой с `pending_level` в сейве, загруженный игрой, сразу получает меню; пока меню открыто, ходы
   не идут (`handle` блокирует при `pending`). `begin_level_up` не проверяет опыт (как `level_up`), а `can_level_up` — вызывающий.
   Если опыта хватает на два уровня подряд — `finish_level_up` оставляет `pending` (как сейчас).
4. **`preview_hero` — deep copy героя на каждом шаге меню:** герой ≈ десятки КБ, меню — единицы шагов, цена незаметна; важно,
   что `choice_options`/`next_choice` не мутируют героя (проверить тестом «исходный не тронут»).
5. **Форма = v12** (риск 1): все спорные формы приняты В1–В4/В8–В10/В12; остаточный риск — `Concentration.circle` при апкасте
   (К1 ставит круг ячейки) и `GrantedSpell.ability` для Посвящённого в магию (К-классы) — поля есть.
6. **Числа SRD** (A0.14): текста нет в репозитории; при вводе kaban сверяет с SRD 5.2; тесты держат инварианты и опорные точки.
   Если найдётся расхождение с планом — правит данные, а не тест, и пишет в ревью.
7. **`rarity_cap`/клад — проектные числа**, не SRD (аудит свекрови прав): в YAML/конфиге остаётся `custom` и ссылка на решение
   Q8/Q9; `hoard` «ждут утверждения» снимается только решением проектировщика.
8. **`pythonpath` для kit-ов** меняет импорт в 71 файле косвенно (вставки `sys.path` становятся лишними, но безвредными);
   конфликтов имён между kit-ами нет (`*_kit.py` уникальны), `conftest.py` через `pythonpath` не импортируются.
9. **Мутанты на старых строках** (`migrate`, `load_slot`, `check_pack_refs`) могут оказаться эквивалентными (например, `copy` vs
   `deepcopy` при входе без вложенных словарей) — допускается запись «эквивалентен» с доказательством в ревью.
10. **Живой прогон — цепочка v4→v9** на мире с 31 NPC и 4 автослотами: `load_slot` мигрирует только открываемый слот (`auto`),
    остальные остаются v4 и мигрируют при открытии; бэкап `backups/auto-v4-<ts>` — штатно. Копию мира для прогона делает
    пользователь (saves/ агентам только читать).

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1. Конструктор `CharacterSheet` без старых ключей.** **(а) `class_id=`/`level=`/`subclass_id=` в конструкторе — ошибка
  (`extra="forbid"`), kits и 27 файлов тестов переводятся на `classes=[ClassLevel(...)]`** (модель честная, миграция — только в
  m0009); (б) `model_validator(mode="before")`, принимающий старые ключи и сворачивающий их в `classes` — меньше правок тестов, но
  модель молча принимает немигрированные данные и двоит логику m0009.
- **Q2. `Concentration.circle` при миграции.** **(а) круг = уровень заклинания из реестра (`MigrationContext.spell_level`),
  неизвестное заклинание → 1 и строка предупреждения миграции**; (б) `circle: int | None`, при миграции `None` — честнее, но
  каждый потребитель К1 получает ветку `None`.
- **Q3. Форма черновика.** **(а) `LevelChoices.feature_choices: dict[str, list[str]]` — одна форма с листом (меню пишет `[key]`)**;
  (б) оставить `feature_options: dict[str, str]` в черновике и конвертировать при применении.
- **Q4. Промпт в К0.** **(а) ключ `companion` остаётся (первый спутник), `spells_prepared` — список класса: байты `sheet_data` и
  WINDOW 22450 не меняются; список спутников в промпте — Ж0 (напарник)**; (б) сразу `companions: list` + правка `narrator_rules.md`
  и WINDOW — объём К0а растёт на промпт-тесты.
- **Q5. Изоляция `sys.path`.** **(а) `pythonpath` в `pyproject` + снять вставки только в `tests/unit/persistence` (2 файла); остальные
  69 — строка BACKLOG 16 «механическая чистка»**; (б) все 71 файл в К0а (шум в диффе партии схемы).
- **Q6. Откуда потолок.** **(а) `max_level(registry)` = старший ключ таблицы `xp` (уровень существует ⇔ есть порог опыта;
  `proficiency` уже 1–20)**; (б) отдельная таблица `level_cap` (`rows: {max: 20}`) — явно, но второй источник правды.
- **Q7. Потолок в конфиге.** **(а) `LEVEL_CAP = 20` в `settings.py`, валидаторы «ровно 1..20», тест-сторож `LEVEL_CAP ==
  max_level(registry)`**; (б) валидатор «ключи 1..N подряд» без числа и поиск `by_level` (ближайший снизу) — допускает неполный
  конфиг, скрывает дыры.
- **Q8. Клад и редкость (В7а «после сверки»).** Сверка: в SRD 5.2 таблиц клада нет, уровня в таблице редкости нет (A8).
  **(а) утвердить: `hoard` 11-16 ≈ 11 900 зм (sp 2d6×200 зм, gp 2d6×1000 зм, pp 1d6×1000 зм), 17+ ≈ 49 000 зм (gp 2d6×3000 зм,
  pp 2d6×4000 зм), `source: custom`, пометка «утверждено К0б»; редкость 1–4 uncommon, 5–10 rare, 11–16 very_rare, 17–20
  legendary**; (б) другие числа (назвать); (в) полосы-заглушки «как 5-10» до К7д.
- **Q9. `gold_explicit_max_cp_by_level` 6–20.** **(а) лестница A8 (6: 1500 зм … 10: 5000 … 16: 25 000 … 20: 100 000)**;
  (б) по полосам: 6–10 = 5000 зм, 11–16 = 25 000, 17–20 = 100 000; (в) свои числа.
- **Q10. `prepared_by_level` 1–20 жреца/волшебника/следопыта.** **(а) в К0б (данные класса той же природы, что ячейки; заодно
  чинит 2–5 у жреца/волшебника — сейчас 4 на любом уровне)**; (б) в К2/К3 вместе с умениями (до тех пор на 6+ лимит 5-го уровня).
- **Q11. Уровень 19.** **(а) строка `ability_score_improvement` как заглушка; К14 заменяет на `epic_boon`** (код — ноль);
  (б) сразу умение `epic_boon` с меню как у ПХ (`required_choices` +1 условие) — К14 только добавит черты категории.
- **Q12. Замер нейтральности.** **(а) golden-снимки `/sheet`, `sheet_data`, меню уровня героя `v4_dragon`, снятые на main до
  правок (байт-в-байт после)**; (б) только сравнение отдельных полей (слабее, пропустит сдвиг формата).
- **Q13. Фикстуры.** **(а) `v8` — из `v7` движком main; ветки боя/NPC m0009 — raw-dict тесты + цепочка `v5_combat`**; (б) ещё
  фикстура `v8_combat` (генерировать нечем без мок-боя — дорого).
- **Q14. `equipment` по умолчанию.** **(а) `None` = «по статблоку»** (К7к различает «не задано» и «снято»); (б) всегда объект с
  пустыми полями.
- **Q15. Неизвестный класс при миграции костей хитов.** **(а) `hit_dice:d8` + строка предупреждения** (сейв открывается);
  (б) ошибка загрузки.

**Технические умолчания на аппрув вместе с планом:** ключи пулов `hit_dice:d{N}` и `pact_slot`; `Equipment` в `state/creature.py`;
`LevelChoices`/`PendingLevel` в `state/hero.py`, `rules/level_up.py` — новый модуль; `MigrationContext.class_hit_die`/`spell_level`;
m0009 требует контекст; `level_history` обязателен и равен уровню; текст меню «Опыта хватает на уровень N: выберите …» до commit;
`save_current` посреди меню — штатно; `preview_hero` — deep copy; `prepared_of`/`known_of` — `setdefault`; таблица
`damage_severity` в формате `count`/`sides`; `test_srd_minimum` — 12 таблиц; `LEVEL_CAP` в settings; ПХ-строки всем пяти классам
по A8; `hoard.yaml` остаётся `custom`; живой прогон — после К0б по B2.7; `SMELLS_MAX` 206.

## Решения проектировщика (2026-10-11)
Q1–Q15 — все по рекомендациям, вариант (а). Технические умолчания приняты вместе с планом.
