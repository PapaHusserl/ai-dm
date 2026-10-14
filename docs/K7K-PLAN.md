# План партии К7к «Бой: иммунитеты, снаряжение монстров, сложность» (papa-kaban, 2026-10-14; на аппрув проектировщика)

Вписано оркестратором (у papa-kaban нет Write).

Задача: R4 #9 / R5 #13 по решениям `docs/decisions/k7k-grooming.md` («Решения проектировщика», 2026-10-13): **В1а** порог К-6
≥ 80 % снят, сетка sim_combat только измеряет, тест «не хуже базовой линии − допуск»; **В2а** поля иммунитетов/сопротивлений/
уязвимостей в `Monster` и передача во все пути урона, тесты на подставных монстрах, данные — К7д; **В3а**
`world.settings["difficulty"]` easy/normal/hard ↔ tier low/moderate/high, по умолчанию из `cfg.encounter.tier`, выбор в меню
нового мира и командой; **В4а** `warn_danger` снят как сделанный; **В5а** `condition_immunities` — поле и проверка при наложении;
**В6 (а)+(в)** доспех/щит из статблока, `equipment` переопределяет, КД не пересчитывается (пересчёт — К7х), `chain_shirt` в
данные; **В7а/В9а/В10а** — зверь, бюджет спутника и немагическое оружие не в К7к (записи в BACKLOG); **В8а** сетка «класс ×
1–5 × стартовая сцена», `make sim-grid`, не в `make test`; при перерасходе уровни 2–5 → К7х; **В11** «не задано» ≠ «снято»,
без повторного трофея. Сейв v9, новых полей сейва и миграций нет (`Participant/NPC.equipment` и `WorldState.settings` уже есть).
Схема запросов рассказчика без правок (replay старых репортов не ломается). Код на ec5faef, smells 204/206, WINDOW мока
25000 (пик 19666, бюджет 20000 — запас ≈ 330 токенов).

## Что показал код (сверка перед планом)

- **Урон.** `apply_damage` (`rules/damage.py:54`) уже принимает `resistances/vulnerabilities/immunities`; сопротивления вида и
  эффектов `resist` добавляет сам. Вызовов из боя девять, все через `engine.actor(ref)` и `now_s=engine.world.clock.now_s`,
  ни один не передаёт списки: `mastery.py:73` (царапина), `engine.py:385` (`burn`: горение/лозы), `cast.py:177/271/307`
  (атака, дротики, область), `move.py:24` (опасная зона), `attack.py:314/366/488` (метка, особый урон оружия, основной удар),
  `improvise.py:93`. Десятый — `roll_hazard` (`damage.py:131`), герой вне боя, монстра там нет — без правок. Нужна одна обёртка
  движка; `engine.log_notes` уже печатает строки «Иммунитет/Сопротивление/Уязвимость».
- **Модель монстра.** `Monster` (`content/models/monsters.py:27`): `ac`, `hp`, `cr`, `traits`, `tags`, `actions`, без
  доспеха/щита/иммунитетов; `ContentModel` `extra=forbid`. Валидатор реестра (`content/loader.py:137–143`) проверяет `traits`
  и `weapon_id` — туда же проверку доспеха/щита/состояний. Типы урона — ключи `DAMAGE_TYPE_WORDS` (`rules/roll_pipeline.py`).
  Данных три монстра; по SRD: воин-гоблин — кожаный доспех + щит (КД 15 = 11+2+2 ✓), босс — кольчужная рубаха + щит (17 =
  13+2+2 ✓), стражник — кольчужная рубаха + щит (16 = 13+1+2 ✓): числа `ac` в данных сходятся с доспехом, пересчёт не нужен.
  `srd/data/armor/`: `chain_mail`, `leather_armor`, `shield`, `studded_leather`; **`chain_shirt` нет** (SRD 5.2: medium, КД 13,
  dex_cap 2, 50 зм = 5000 cp).
- **Состояния на монстров кладут три места** движка: `mastery.py:58` (Topple → prone), `improvise.py:85` (prone),
  `attack.py:409` (Опутывающий удар → условие `params["condition"]`). Остальные `conditions.append` — на себя/героя
  (`stealth.py:37`, `handlers/combat.py:191`, `downed.py:34`/`death_saves.py:107` — unconscious при 0 HP). Общего помощника
  нет. Иммунитет по типу есть только у переговоров (`cfg.parley.immune_types`).
- **Трофеи.** `settle_ground` (`combat/end.py:87`) → `state.gear = trophies.enemy_gear(engine, disarm.weapon_ids)`;
  `enemy_gear` собирает `(monster_id, weapon_ids, boss)` по телам dead/down без перебежчиков → `loot.body_gear` (цена по
  `registry.get("weapon")`, качество `trophy_quality(cr)`, босс — полная цена) + `quest_gear`. `finish_combat`
  (`game/combat_flow.py:210`) переносит `state.gear` в `LastCombat.gear`; `gold_loot/loot_gear`
  (`handlers/loot_gear.py`) выдаёт один раз (`gear_looted`), `add_item`/`entry_name` работают по `find_item` (weapon|armor|
  item) — доспех ляжет в инвентарь без правок инвентаря. `Equipment{armor, shield, weapons}` (`state/creature.py:60`), поле
  `equipment` у `Participant` (`combat.py:102`) и `NPC` (`world.py:101`) никто не читает и не пишет. Выбитое оружие помечает
  `disarmed` на существе до конца `settle_ground` (`weapon_ids` его исключает). Именованный NPC со статусом `down` после боя
  жив и может драться снова — отсюда В11 (повторный трофей).
- **Бюджет и сложность.** `party_budget(levels, registry, cfg)` берёт `cfg.encounter.tier` (`rules/encounter.py:5`),
  `budget_text` (`:104`) — тоже; единственный вызов — `handlers/combat.py:148/199`. `WorldState.settings: dict[str,
  int|str|bool]` (`world.py:282`) никто не пишет, он уходит рассказчику в `world_block` (`master/prompt.py:237`). Образец
  команды-настройки — `/tone`: `game/tone.py` (`show_lines/parse/apply` + `add_entry` в хронику) и `cmd_tone`
  (`commands.py:201`, `app.save_current("auto")`); команды — `COMMANDS`/`HELP` (`commands.py:31, 279`), TUI свой список не
  держит. Меню нового мира — `cli.py:898` `choose_preset` после выбора героя (`choose_number`, в TUI — экран), флаг
  `--preset` (`:102`); `new_world_from_pack` (`game/starter.py:33`). В тестах `protocol_kit`/`test_apply_budget.py` держат
  контракт «ур. 1 — 75 ПО moderate».
- **sim_combat** (`devtools/sim_combat.py`): `build_goblins3` собирает героя из `fighter_choices/wizard_choices`
  (пресеты arn/liel пака Вейл), сценарий один; `test_criterion1.py` (200 сидов × 2 варианта, golden `goblins3_win.txt`,
  `S_WIN = 2`) и `test_sim_combat.py` (26 тестов, контракт в шапке). Классов в данных пять (`fighter, rogue, cleric, wizard,
  ranger`), подклассы — только у следопыта (`subclasses_of` пуст для остальных → на 3 ур. выбора подкласса нет); пресетов
  героев для жреца и плута нет ни в одном паке (arn, liel, grey); у классов есть `starting_kits` (`a`). Подъём уровня:
  `progression.level_up(hp_method="average")` + `LevelChoices` через `next_choice/choice_options/apply_level_choices`
  (`progression.py:166–240, 347`) — всё, что нужно для автоматического подъёма 2–5. **Стартовых боёв в паках нет**
  (`campaign.yaml.start` — локация и герои; монстр в паках один — `goblin_boss` в `vale/npcs.yaml`): «стартовая сцена каждого
  пака» данными не обеспечена (Q2).
- **Промпт.** `narrator_rules.md:84` — обыск тел «деньги и снаряжение с тел», доспех под это подходит; правила про сложность
  нет и не нужно (В4а; `settings` уже в `world_block`). Мок-миры сценария памяти `settings` не задают — рост WINDOW нулевой.

## Реализация (kaban; src, data, docs)

### 1. Иммунитеты, сопротивления, уязвимости и иммунитет к состояниям (В2а, В5а) — `content/models/monsters.py`, `content/loader.py`, `combat/engine.py`, 9 вызовов урона, 3 точки состояний
1.1. `Monster`: `damage_immunities: list[str] = []`, `damage_resistances: list[str] = []`, `damage_vulnerabilities:
   list[str] = []`, `condition_immunities: list[str] = []`; `field_validator` на три списка урона — значения из
   `DAMAGE_TYPE_WORDS` (неизвестный тип → `ValueError`), повторы запрещены. `loader.check_refs`: `condition_immunities` —
   `has("condition", id)`, иначе `bad("monster", id, "condition_immunities", …)`. Данные трёх монстров — без изменений
   (по SRD у них ничего нет).
1.2. `CombatEngine.damage(target_ref, amount, damage_type) -> DamageResult` — единственный путь урона в бою: для
   `monster_of(ref)` берёт три списка статблока, для героя — пустые; вызывает `apply_damage(self.actor(ref), amount,
   damage_type, self.registry, resistances=…, vulnerabilities=…, immunities=…, now_s=self.world.clock.now_s)`. Заменить все
   девять вызовов (`mastery.graze`, `engine.burn`, `cast_attack/cast_darts/cast_area`, `move.hazard_check`,
   `attack.mark_damage/special_damage/perform-удар`, `improvise.apply_extra_damage`); прямой импорт `apply_damage` в
   `combat/` после правки остаётся только в `engine.py` (проверка `grep` в ревью). Лог «Иммунитет: 7 → 0 огонь» печатает
   `log_notes` — как сейчас.
1.3. `CombatEngine.impose(ref, condition: AppliedCondition) -> bool`: монстр с `condition.id` в `condition_immunities` —
   лог «  {имя}: иммунитет к состоянию {слово}» (слова — `registry.get("condition", id).name`), `False`; иначе
   `creature.conditions.append`, `True`. Перевести три точки: `mastery.py:58`, `improvise.py:85`, `attack.py:409` (при
   `False` у Опутывающего удара — не класть `ensnared`-эффект, концентрация снимается как при успешном спасброске).
   Состояния «на себя» и `unconscious` при 0 HP — не через `impose` (Q4а).
1.4. Для `condition_immunities` хватает пути движка: вне боя состояния на NPC никто не кладёт (`grep` подтверждает).

### 2. Снаряжение монстра и трофеи с тел (В6 а+в, В11) — `content/models/monsters.py`, `content/loader.py`, `srd/data/armor/chain_shirt.yaml`, `srd/data/monsters/*.yaml`, `combat/trophies.py`, `combat/end.py`, `rules/loot.py`
2.1. `Monster.armor: str | None = None`, `Monster.shield: str | None = None` (комментарий «что надето по SRD; КД —
   число `ac`, по снаряжению не пересчитывается (К7х)»). `loader`: `armor` — `has("armor")` и `category != "shield"`;
   `shield` — `has("armor")` и `category == "shield"`.
2.2. Данные: `armor/chain_shirt.yaml` (`id: chain_shirt`, «Кольчужная рубаха», medium, `ac: 13`, `dex_cap: 2`,
   `cost_cp: 5000`, `strength_min: 0`, source/license как у соседей); `goblin_warrior`: `armor: leather_armor`, `shield:
   shield`; `goblin_boss`: `armor: chain_shirt`, `shield: shield`; `guard`: `armor: chain_shirt`, `shield: shield`.
2.3. `trophies.body_equipment(engine, ref) -> Equipment` — источник «что надето»: `part.equipment` (безымянный) или
   `world.npcs[ref].equipment` (именованный), если не `None`; иначе из статблока: `Equipment(armor=monster.armor,
   shield=monster.shield, weapons=weapon_ids(engine, ref))`. Если `equipment` задан — `weapons` = `equipment.weapons` минус
   выбитое (`lost_weapons`). Параметр `weapon_ids` у `enemy_gear` остаётся (его передаёт `settle_ground`).
2.4. `enemy_gear`: тело → `(monster_id, item_ids, boss)`, где `item_ids = weapons + [armor] + [shield]` без `None`.
   `loot.body_gear` принимает любые id оружия/доспеха: цена через `gear_cost(registry, item_id)` (`find_item` → `cost_cp`;
   неизвестный id → `ValueError`). Качество по ПО как у оружия (кожаный доспех гоблина — `junk`, 10 %: 100 cp; щит 100 cp;
   босс — полная цена). `add_stack` — как сейчас.
2.5. В11 «снято»: в `settle_ground` после подсчёта `state.gear` для каждого тела из `world.npcs` (именованный NPC, он
   переживает бой) — `npc.equipment = Equipment()` (пусто: доспех, щит и оружие учтены трофеями, повторно с тела не берутся).
   Безымянному участнику ничего не пишется (бой не переживает). Семантика поля для ARCHITECTURE: «`None` — по статблоку;
   задано — полная правда об экипировке, пустое — снято». В К7к оружие такого NPC в бою по-прежнему из `actions`
   (`equipment.weapons` читает К7х — отметить в ROADMAP-PLAN строкой К7х).
2.6. `gold_loot`/`loot_gear`, `finish_combat`, `strip_weapon`, `pick_valuables` — без правок кода (мутмут по списку R4
   прогнать: поведение зависит от состава `gear`).

### 3. Сложность кампании (В3а) — `rules/encounter.py`, `protocol/handlers/combat.py`, `game/difficulty.py` (новый), `game/commands.py`, `game/starter.py`, `ui/cli.py`
3.1. `encounter.py`: `DIFFICULTY_TIERS = {"easy": "low", "normal": "moderate", "hard": "high"}`; `tier_of(world, cfg) ->
   str` — `world.settings.get("difficulty")` через словарь, нет/неизвестно → `cfg.encounter.tier`; `party_budget(levels,
   registry, tier)` и `budget_text(level, budget, enemies, registry, tier)` получают tier строкой вместо `cfg`
   (`TIER_WORDS` как есть). `start_combat`: `tier = encounter.tier_of(world, ctx.cfg)` один раз, в оба вызова.
3.2. `game/difficulty.py` по образцу `tone.py`: `DIFFICULTIES = ("easy", "normal", "hard")`, `WORDS = {"easy": "лёгкая",
   "normal": "обычная", "hard": "тяжёлая"}`, `current(world, cfg) -> str` (значение или обратное отображение
   `cfg.encounter.tier`), `show_line(world, cfg)` («Сложность: обычная (бюджет боя умеренный)»; без явного значения — «по
   умолчанию»), `parse(arg) -> (value, error)`, `apply(bundle, value) -> str` (пишет `world.settings["difficulty"]`,
   `add_entry(bundle, "difficulty", "Сложность: лёгкая")`).
3.3. `commands.cmd_difficulty(app, arg)`: без аргумента — `show_line`; с аргументом — `parse`/`apply`, `app.save_current
   ("auto")`. `HELP["difficulty"] = "[easy|normal|hard] сложность боёв (бюджет врагов)"`, `COMMANDS`. Имя команды — Q1.
3.4. Новый мир: `new_world_from_pack(..., difficulty=None)` — если задано, `bundle.world.settings["difficulty"] = …` (до
   `start_scene`); `cli.py`: флаг `--difficulty {easy,normal,hard}` (только с `--new`, как `--preset`), `choose_difficulty
   (stdin, stdout, notes, setup)` сразу после `choose_preset` — `choose_number` с пунктами «Как в конфиге (умеренный)»,
   «Лёгкая», «Обычная», «Тяжёлая» (первый/Esc → `None`); в заметках старта «сложность <слово>», в `--replay` — как
   `--preset` (подсказка). Импорт (`--import`) и `--hero-describe` — без меню (значение по умолчанию).
3.5. Промпт — без правок (Q6а): `settings.difficulty` рассказчик и так видит в `world_block`.

### 4. Сетка sim_combat (В1а, В8а) — `devtools/sim_combat.py`, `devtools/sim_grid.py` (новый), `devtools/grid_heroes.py` (новый), `devtools/sim_grid_baseline.yaml` (корень репозитория, новый), `Makefile`
4.1. `sim_combat.build_goblins3(registry, cfg, seed, variant, intent, hero=None, difficulty=None)`: при `hero` —
   использовать его (variant игнорируется), `difficulty` → `world.settings`. `build_scenario(..., hero=None,
   difficulty=None)` пробрасывает. Поведение по умолчанию, `S_WIN`, golden — **не меняются**.
4.2. `grid_heroes.py`: `CLASSES = ("fighter", "rogue", "cleric", "wizard", "ranger")`; `level1_choices(class_id) ->
   CharacterChoices`: воин/волшебник/следопыт — `starter.fighter/wizard/ranger_choices("hero")`; жрец и плут — свои
   `CharacterChoices` (человек, стандартный массив: основная характеристика 15, `class_kit="a"`, первые N навыков класса,
   первые мастерства, жрец — подготовленные первые по лимиту, `background` — тот же, что у arn) (Q5а). `auto_level(hero,
   registry, level)`: цикл `level_up(hero, registry, hp_method="average")` → `choices = LevelChoices(level=…)` → пока
   `next_choice(hero, registry, choices)` не `None`: ключ `fighting_style/expertise/subclass/<умение>` — первый из
   `choice_options`; `asi_or_feat` — первый вариант ASI (`+2` к первой характеристике из списка — детерминированно);
   `spells` — первый кандидат; `apply_level_choices` (ошибка → `ValueError`, чтобы сетка не молчала). `build_hero(class_id,
   level, registry) -> HeroState`.
4.3. `sim_grid.py`: `SCENES = {"goblins3": …}` (структура под добавление сцен в К7д, Q2а), `LEVELS = range(1, 6)`;
   `run_cell(class_id, level, scene, registry, cfg, seeds, difficulty=None) -> Cell(wins, deaths, other, mean_rounds)`;
   `run_grid(registry, cfg, *, classes, levels, scenes, seeds) -> list[Row]`; `table_lines(rows)` (класс × уровень: «побед
   N/M (p %), ср. раундов»); `compare(rows, baseline, tolerance) -> list[str]` (строки «класс L ур.: 20 % < базовой 32 % −
   10 п.п.»); CLI `python -m ai_dm.devtools.sim_grid [--seeds 200] [--classes …] [--levels …] [--scene …] [--difficulty …]
   [--check] [--write-baseline]`; `--check` читает `devtools/sim_grid_baseline.yaml` ({scene: {class: {level: win_share}},
   seeds, tolerance_pp: 10}) и возвращает 1, если хоть одна клетка хуже базовой − допуск (Q3а). `Makefile`: `sim-grid: uv run
   python -m ai_dm.devtools.sim_grid --check` (в `.PHONY`, не в `quality`/`make test`).
4.4. Первый прогон (200 сидов, 25 клеток) → `--write-baseline` и таблица в `docs/decisions/k7k-sim-grid.md` (вместе с
   временем прогона; воин 1 ур. должен совпасть с k1-sim-combat: 64/200). Если `auto_hero` не умеет жреца/плута (не
   лечится, не колдует) — это факт сетки, не баг К7к: в таблицу с пометкой, в BACKLOG строкой К2/К3.
4.5. Если шаги 4.2–4.4 по факту выходят за оценку (п. «Оценка»), уровни 2–5 (`auto_level`) переносятся в К7х; в К7к
   остаётся 5 классов × 1 ур. (В8, решение проектировщика).

### 5. Docs
`docs/BACKLOG.md`: 6 — «параметр сложности ✅ К7к (`/difficulty`, меню, `settings.difficulty`); порог К-6 снят (В1а), сетка
`make sim-grid`»; 11 — «иммунитеты/сопротивления/уязвимости: механика ✅ К7к, данные — К7д; зверь-спутник в бою → п. 44»;
22 — «доспехи и щиты с тел ✅ К7к»; 44 — дописать: «механика зверя в бою — не К7к (В7а, 2026-10-13): К3 (следопыт 3–5,
Повелитель зверей) или своя S-партия; нужны статблоки зверей (К7д) и связь `Companion.kind → monster_id`; бюджет боя
спутника не учитывает (В9а)»; **новая 49** — «Иммунитет/сопротивление к немагическому оружию (В10а, 2026-10-13): нужен
признак магического оружия в механике; поле вроде `nonmagical_only` у списков монстра — после появления магического оружия»;
45 — строка только если WINDOW поднимали (план: не поднимать). `docs/ROADMAP.md`: #13 ✅ факт расхода; строка К7х — «+
пересчёт КД по `equipment` (В6), чтение `equipment.weapons` в бою, + уровни 2–5 сетки, если перенесены». `docs/ROADMAP-PLAN.md`:
:41 «К-6: порог снят 2026-10-13 (В1а)»; :202 убрать «мелочи следопыта (перенос Метки охотника, Истребитель орд, смена
Добычи)» из К7к (в R4 они в К7х, строка :203 — оставить); строка К7х — «+ пересчёт КД по `equipment`». `docs/HANDOFF.md`:
строка К7к. `docs/ARCHITECTURE.md`: модель монстра (поля 1.1, 2.1, «КД — число»), «урон в бою — только `engine.damage`,
состояния на монстра — `engine.impose`», трофеи (доспех/щит, `body_equipment`, семантика `equipment` None/задано/пусто),
D6 — сложность (`settings.difficulty` → tier), п. 23 Devtools — `sim_grid`, `make sim-grid`, базовая линия. `docs/TZ.md:102`
— «бюджет по уровню героя и сложности кампании». Чек-лист `docs/checklist-k7k-live.md` (не коммитить; живой прогон — общий
на К7 после К7д): (1) новый мир → меню сложности «Лёгкая» → `/difficulty` показывает «лёгкая»; бой с 3 гоблинами на ур. 1
(лёгкий бюджет 50 ПО) без `warn_danger` → `clamped`, в логе «Бюджет боя: 50 ПО (ур. 1, лёгкий)»; `/difficulty hard` → тот же
бой проходит; (2) победа над гоблином → обыск → в инвентаре кожаный доспех (junk) и щит; (3) бой с именованным NPC-стражником,
который выжил (down) → второй бой → трофеев с него нет; (4) иммунитеты — на монстрах К7д (нежить); (5) `--replay-report` ходов
1–3 → код 0.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.combat.engine:CombatEngine.damage ai_dm.combat.engine:CombatEngine.impose` — TESTS
  tests/unit/combat/test_damage_types.py tests/unit/combat/test_condition_immunity.py
- `ai_dm.combat.mastery:graze ai_dm.combat.engine:CombatEngine.burn ai_dm.combat.actions.cast:cast_attack
  ai_dm.combat.actions.cast:cast_darts ai_dm.combat.actions.cast:cast_area ai_dm.combat.actions.move:hazard_check
  ai_dm.combat.actions.attack:mark_damage ai_dm.combat.actions.attack:special_damage ai_dm.combat.actions.attack:perform
  ai_dm.combat.actions.improvise:apply_extra_damage` — TESTS tests/unit/combat/test_damage_types.py + существующие файлы
  каждого модуля (test_mastery, test_dragon_arrows, test_actions_cast, test_area, test_actions_attack, test_improvise)
- `ai_dm.content.models.monsters:Monster.check_damage_types ai_dm.content.loader:check_refs` — TESTS
  tests/unit/content/test_monster_defenses.py tests/unit/content/test_monster_gear.py tests/unit/content/test_content_loader.py
- `ai_dm.combat.trophies:body_equipment ai_dm.combat.trophies:enemy_gear ai_dm.combat.end:settle_ground
  ai_dm.rules.loot:body_gear ai_dm.rules.loot:gear_cost` — TESTS tests/unit/combat/test_trophy_gear.py
  tests/unit/combat/test_trophy_armor.py tests/unit/rules/test_loot_trophy.py
- `ai_dm.protocol.handlers.loot_gear:gold_loot ai_dm.protocol.handlers.loot_gear:loot_gear
  ai_dm.game.combat_flow:finish_combat ai_dm.combat.disarm:strip_weapon ai_dm.rules.inventory:pick_valuables` (R4) — TESTS
  tests/unit/protocol/test_apply_loot_gear.py tests/unit/game/test_game_combat_flow.py tests/unit/combat/test_disarm.py
  tests/unit/rules/test_inventory.py
- `ai_dm.rules.encounter:tier_of ai_dm.rules.encounter:party_budget ai_dm.rules.encounter:budget_text
  ai_dm.protocol.handlers.combat:start_combat` — TESTS tests/unit/protocol/test_apply_budget.py
  tests/unit/rules/test_encounter_difficulty.py
- `ai_dm.game.difficulty:current ai_dm.game.difficulty:show_line ai_dm.game.difficulty:parse ai_dm.game.difficulty:apply
  ai_dm.game.commands:cmd_difficulty` — TESTS tests/unit/game/test_game_difficulty.py
- `ai_dm.game.starter:new_world_from_pack ai_dm.ui.cli:choose_difficulty` — TESTS tests/unit/ui/test_cli_difficulty.py
  tests/unit/game/test_game_starter.py (если есть; иначе в test_cli_difficulty)
- `ai_dm.devtools.sim_combat:build_goblins3 ai_dm.devtools.sim_combat:build_scenario ai_dm.devtools.grid_heroes:level1_choices
  ai_dm.devtools.grid_heroes:auto_level ai_dm.devtools.grid_heroes:build_hero ai_dm.devtools.sim_grid:run_cell
  ai_dm.devtools.sim_grid:run_grid ai_dm.devtools.sim_grid:compare ai_dm.devtools.sim_grid:main` — TESTS
  tests/unit/devtools/test_sim_combat.py tests/unit/devtools/test_sim_grid.py tests/unit/devtools/test_grid_heroes.py

## Тесты (kaban-doeba, TDD; параллельно с kaban)

Правка существующих: `test_sim_combat.py` шапка (новые параметры `hero`, `difficulty`; поведение по умолчанию прежнее);
`test_apply_budget.py` шапка и `protocol_kit` (бюджет по `tier_of`: без `settings` — как раньше); `test_trophy_gear.py`
шапка (трофеи = оружие + доспех + щит, `body_equipment`); `test_loot_trophy.py` (`body_gear` с id доспеха); тесты
`golden`/`test_criterion1.py` — зелёные без правок (проверить: порядок бросков не меняется, `engine.damage` — та же
`apply_damage`); `test_srd_minimum.py`/`test_content_loader.py` — новые поля и `chain_shirt`.

Урон по типам (`tests/unit/combat/test_damage_types.py`, подставной монстр через `registry.with_items({"monster":
[Monster(...)]})` или YAML в tmp как в `test_monster_weapon_id.py`; `combat_kit.make_engine`, `ScriptedRng`):
- Монстр с `damage_immunities: [slashing]`: удар длинным мечом → `final 0`, HP целы, в логе «Иммунитет: N → 0 рубящий»;
  `damage_resistances: [piercing]` → половина вниз (7 → 3); `damage_vulnerabilities: [fire]` → ×2; сопротивление + уязвимость
  к одному типу → `(n // 2) * 2`; герой-цель — списков нет, вид (дварф: яд) как раньше.
- По одному тесту на каждый из девяти путей (иммунитет к типу пути → 0 HP потерь): царапина (`graze`), горение в начале хода
  (`burn`), лозы (`ensnared`), `cast_attack` (`fire_bolt` против иммунного к огню), `cast_darts`, `cast_area` (область: один
  участник иммунен, второй нет), опасная зона (`hazard_check`, `damage_type` зоны), метка охотника (`mark_damage` —
  дополнительный урон того же типа 0), особый урон оружия (`special_damage`), основной удар, `improvise extra_damage`
  (bludgeoning). Мутант «списки не переданы» умирает каждым из них.
- Иммунный к урону не падает (`after_damage` не вызывает `dropped`), событие `attack` с `damage 0`.
- `grep`-тест (как в проекте для латиницы): в `src/ai_dm/combat/` `apply_damage(` встречается только в `engine.py`.

Иммунитет к состояниям (`tests/unit/combat/test_condition_immunity.py`): монстр `condition_immunities: [prone]` — Topple
(мастерство) → лог «иммунитет к состоянию сбит с ног», `prone` нет, урон прошёл; `improvise prone` → проверка удалась, но
состояние не легло; `condition_immunities: [restrained]` — Опутывающий удар: спасбросок не бросается (или бросается — решить в
тестах по коду), лоз нет, концентрация снята, `ensnared` нет; без иммунитета — всё как раньше; `impose` на героя — всегда
`True`; `unconscious` при 0 HP ложится и на «иммунного» (Q4а).

Контент (`tests/unit/content/test_monster_defenses.py`, `test_monster_gear.py`): поля по умолчанию пусты; неизвестный тип
урона (`"frost"`) → `ValidationError`; повтор → ошибка; `condition_immunities: [sleepy]` → `ContentError` загрузчика;
`armor: shield` / `shield: leather_armor` / `armor: nope` → `ContentError`; `chain_shirt` в реестре (medium, 13, cap 2, 5000);
три монстра: `armor/shield` по данным и **сверка** `ac == armor.ac + min(dex mod, dex_cap or 99) + shield.ac` (документирует,
что КД и снаряжение согласованы, пересчёта нет).

Трофеи (`tests/unit/combat/test_trophy_armor.py`, `tests/unit/rules/test_loot_trophy.py`): победа над 2 безымянными
гоблинами → `gear`: скимитар ×2 (junk), кожаный доспех ×2 (junk, 100 cp), щит ×2 (junk, 100 cp) — стеки; босс (`goblin_boss`,
named лидер) → кольчужная рубаха 5000 cp, щит 1000 cp, quality None; выбитое оружие в `gear` не дублируется, доспех есть;
`Participant.equipment = Equipment(armor=None, shield="shield", weapons=["scimitar"])` переопределяет статблок (доспеха нет,
щит есть); `Equipment()` (пусто) → с тела ничего; именованный NPC после победы: `npc.equipment == Equipment()`; второй бой с
тем же NPC (down → снова active) → `gear` без его вещей (В11), квестовые вещи — как раньше; поражение/бегство — `gear` пуст,
`npc.equipment` не тронут; `gear_cost` неизвестного id → `ValueError`. Протокол (`test_apply_loot_gear.py`): `gold
loot_individual` после боя с доспехом → `items` с доспехом и щитом, `add_item` в инвентарь, `/inv` показывает группу доспехов,
второй вызов — `rejected`; replay хода с таким обыском → код 0.

Сложность (`tests/unit/rules/test_encounter_difficulty.py`, `tests/unit/game/test_game_difficulty.py`,
`tests/unit/ui/test_cli_difficulty.py` по образцу `test_cli_preset.py`/`test_game_tone.py`): `tier_of`: нет настройки →
`cfg.encounter.tier`; `easy/normal/hard` → `low/moderate/high`; мусор в `settings` → конфиг; `party_budget([1], …, "low")` ==
таблица `1:low` (25 ПО), `"high"` — `1:high`; `start_combat` с `settings.difficulty = easy` и 3 гоблинами (150 > 25) →
`clamped`, лог «Бюджет боя: 25 ПО (ур. 1, лёгкий)»; `hard` → без урезания; `warn_danger` на easy — как раньше (основание
есть). Команда: `/difficulty` без аргумента → «Сложность: обычная (по умолчанию…)»; `/difficulty easy` → `settings`,
хроника «Сложность: лёгкая», автосейв, ответ; `/difficulty epic` → ошибка со списком; `/help` содержит строку. CLI: `--new
--difficulty hard` → в сейве `settings.difficulty == "hard"`, заметка старта; без флага и меню (ввод «1») → ключа нет; меню
пункт «2» → `easy`; `--difficulty` без `--new` → код 2; `--replay` — как `--preset`. Промпт: `world_block` содержит
`settings: {difficulty: easy}` (существующий тест `world_block`); `test_stage4_memory` зелёный без подъёма WINDOW.

Сетка (`tests/unit/devtools/test_grid_heroes.py`, `test_sim_grid.py`): `level1_choices` для пяти классов проходит
`build_character` (`validate` без ошибок), класс/КД/HP ожидаемые (жрец — studded + щит, плут — leather, два кинжала);
`auto_level(hero, 5)` для каждого класса → `level == 5`, `missing_choices` пусто на каждом уровне, следопыт получил подкласс
(первый — `beast_master` или `hunter` по сортировке) и `feature_choices`, волшебник/жрец — заклинания до лимита, 4 ур. —
ASI применён; детерминизм: два вызова → одинаковые листы; `build_scenario(..., hero=…)` ставит героя в `door` c
`auto_hero`, `difficulty` → `world.settings`; `run_cell` на `seeds=range(3)` → `wins + deaths + other == 3`,
`mean_rounds > 0`; `run_grid` — 25 строк при полной сетке (в тесте — 2 класса × 2 уровня × 2 сида); `compare`: клетка ниже
базовой − допуск → строка, ровно на границе → пусто, нет клетки в базовой → строка «нет базовой линии»; `main --check` с
подставной базовой (tmp) → 0/1; `--write-baseline` пишет YAML с `seeds` и `tolerance_pp`; `make sim-grid` цель есть в
Makefile (grep). Базовую линию на 200 сидах генерирует kaban (п. 4.4), doeba — проверяет повторяемость одной клетки (воин 1 ур.
= 64/200, как k1-sim-combat).

Общее в конце: `uv run pytest -q`, `make cov` (≥ 94 %), `make smells` (≤ 206; `engine.damage`/`impose` убирают девять
дублей — ожидание ≤ 204), `make dead` (новые функции devtools — в `vulture_allowlist` только с согласия), `uv run ruff check
src tests`; mutmut по списку выше; `make sim-grid` один раз (время прогона — в ревью).

## Критерии приёмки
1. Все пути урона в бою идут через `engine.damage` и учитывают три списка статблока; иммунитет к состоянию — через
   `engine.impose` в трёх точках движка; данные трёх монстров без иммунитетов (К7д), подставные — в тестах.
2. `Monster.armor/shield` + `chain_shirt`; трофеи с тел — оружие, доспех, щит по тому же пути (`body_gear`, качество по ПО,
   босс — полная цена); `equipment` переопределяет статблок; именованный NPC после обыска помечен «снято», повторного трофея
   нет; КД не пересчитывается.
3. Бюджет боя — по `settings.difficulty` (easy/normal/hard ↔ low/moderate/high), по умолчанию из конфига; меню нового мира,
   `--difficulty`, `/difficulty`; хроника и автосейв; сейв v9, схема запросов без правок.
4. Сетка 5 классов × 1–5 ур. × goblins3: `make sim-grid` печатает таблицу и проверяет «не хуже базовой − 10 п.п.», не входит в
   `make test`; `S_WIN`, golden и `test_criterion1` без изменений; таблица в `docs/decisions/k7k-sim-grid.md`.
5. Тесты зелёные, cov ≥ 94 %, smells ≤ 206, WINDOW мока не поднят (при превышении — ужимка правил, п. «Риски»).
6. Docs: BACKLOG 6/11/22/44 + 49, ROADMAP #13 и строка К7х, ROADMAP-PLAN :41/:202, ARCHITECTURE, TZ, HANDOFF.

## Оценка
M ≈ 0,85–0,9 млн по шкале R6: kaban ~200–250 тыс. (~25 мин; 9 замен урона, трофеи, сложность в трёх слоях, сетка с
автоподъёмом); kaban-doeba ~450–550 тыс. (~2,5 ч с mutmut: ~120 тестов, 9 путей урона, CLI-тесты, сетка); mama-kaban
~45 тыс. Прогон сетки 25 × 200 = 5000 боёв — ориентировочно 3–6 мин (criterion1 гоняет 400 за секунды), поэтому только в
`make sim-grid`. Если шаг 4 (уровни 2–5) выходит за ~100 тыс. у kaban — перенос в К7х (В8), партия ≈ 0,75 млн.

## Риски / на что обратить внимание
- **Пропуск пути урона** — главный брак: страховка — grep-тест «`apply_damage(` только в `engine.py`» и по тесту на путь.
  `roll_hazard` вне боя — герой, без изменений.
- **Опутывающий удар и иммунитет к restrained**: при отказе `impose` снять концентрацию и не класть `ensnared`, иначе урон лоз
  пойдёт без состояния; покрыть тестом.
- **Именованный NPC «снято»**: после обыска `equipment == Equipment()`, но в бою К7к он по-прежнему бьёт оружием из
  `actions` (чтение `equipment.weapons` — К7х). Записать в ROADMAP-PLAN строку К7х, чтобы не потерялось.
- **Replay старых живых репортов** с обыском тел: `after` теперь содержит доспех/щит — расхождение, как прецедент AD1 Q4;
  новые репорты штатно. Схемы запросов не меняются — `request_fingerprint` цел.
- **Контракт бюджета в тестах** (`protocol_kit`, `test_apply_budget`): без `settings` всё как раньше — старые тесты должны
  остаться зелёными; менять только шапки.
- **auto_hero для жреца и плута** не калиброван (лечение, скрытая атака не реализованы): низкая доля побед — факт данных
  сетки, не баг К7к; записать в таблицу и BACKLOG (К2/К3).
- **Автоподъём**: `asi_or_feat` первый вариант — `str+2` даже волшебнику (детерминизм важнее оптимальности); если
  `choice_errors` ругается на какой-то класс — чинить фикстуру, не правила.
- **Smells 204/206**: `engine.damage` и `impose` уменьшают дубли; `cmd_difficulty`, `choose_difficulty`, `sim_grid.main` —
  держать плоскими (сложность ≤ порога qlty). Лимит не поднимать.
- **WINDOW мока**: план без роста правил; если `test_stage4_memory` всё же превысит бюджет (пик 19666/20000) — ужать
  `narrator_rules.md:44` (три повторяющихся предложения про `follows` → одно, ≈ 60–80 токенов) и `:64` (дубль про
  `take_item`), не поднимать WINDOW (седьмой подъём, BACKLOG 45).
- **Golden и S_WIN не трогать**: сетка живёт в `sim_grid`, `sim_combat` по умолчанию без изменений; падение golden — баг.
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS.

## Открытые вопросы
- **Q1 Имя команды.** (а) **рекомендация** — `/difficulty [easy|normal|hard]` (все команды латиницей, как `/tone`; значения
  те же, что в `settings`), подписи по-русски; (б) `/сложность` с русскими значениями — единственная кириллическая команда,
  парсер `/help` и `COMMANDS` её примут, но стиль ломается.
- **Q2 Сцены сетки.** (а) **рекомендация** — только `goblins3` (паки стартовых боёв не задают, монстров нет), структура
  `SCENES` под добавление; сцены других паков — в К7д вместе с монстрами; (б) придумать по сцене на пак сейчас (стражники ×2 и
  т.п.) — данные без основания в паках.
- **Q3 Как проверять «не хуже базовой − допуск».** (а) **рекомендация** — `sim_grid --check` с `devtools/sim_grid_baseline.yaml`
  (200 сидов, допуск 10 п.п.) в `make sim-grid`, логика `compare` покрыта unit-тестами на синтетических строках; (б) pytest с
  маркером `grid` и исключением из `make test` — маркеров в `pyproject` сейчас нет, конфигурация растёт.
- **Q4 Границы иммунитета к состояниям.** (а) **рекомендация** — только состояния, которые движок кладёт на монстра
  (prone от Topple/импровизации, restrained от лоз); `unconscious` при 0 HP и `invisible` не проверяются; (б) проверять всё,
  включая 0 HP (конструкты SRD) — семантика падения ломается, не К7к.
- **Q5 Герои жреца и плута для сетки.** (а) **рекомендация** — `CharacterChoices` в `devtools/grid_heroes.py` (стандартный
  массив, набор `a`), в паки не попадают; (б) добавить пресеты в пак Вейл — появятся в меню игрока, это продуктовое решение.
- **Q6 Сложность в правилах рассказчика.** (а) **рекомендация** — ничего не добавлять (`settings.difficulty` уже в
  `world_block`, бюджет считает движок); (б) одно предложение «на easy сильный отряд — только после `warn_danger`» —
  +WINDOW ради правила, которое движок и так обеспечивает.
- **Q7 Когда помечать «снято» у именованного NPC.** (а) **рекомендация** — в `settle_ground` при подсчёте `gear` (вещи
  ушли с тела в `last_combat`, не взятые — потеряны, как сейчас оружие); (б) в `loot_gear` при фактическом обыске — нужен
  ref тела в `LastCombat.gear` (поле сейва, v9 ломать нельзя).

Расход papa-kaban ≈ 115 тыс.

## Отклонения при реализации (2026-10-14, ревью docs/decisions/k7k-review.md)
- Запись в хронику о сложности — kind `"event"`, не `"difficulty"`: новое значение `Literal` меняет отпечаток схемы сейва.
- Лёгкий бюджет на ур. 1 — 50 ПО (таблица SRD `1:low`), не 25, как в тексте плана и тестов-примеров.
- Тесты протокола обыска — `tests/unit/protocol/test_gold_loot_gear.py` (в плане назван `test_apply_loot_gear.py`).
- `body_equipment(engine, ref, weapon_ids)` с третьим параметром (цикл импорта `disarm` ↔ `trophies`); `body_refs`, `mark_looted` в `trophies.py`.
- `hero/difficulty` обрабатывает `build_scenario`, сигнатура `build_goblins3` прежняя.
- Параметр `difficulty` сетки (`build_scenario`, `run_cell`, `sim_grid --difficulty`) — на будущее, для сцен с бюджетом боя (К7д): на `goblins3` не влияет.
- Проверки монстра (типы урона, состояния, доспех, щит) — `loader.check_monster_gear`; в модели остался только запрет повторов.
- Подпись пункта меню «Как в конфиге (…)» берётся из `cfg.encounter.tier`.

## Решения проектировщика (2026-10-14)
- Q1 — (а) `/difficulty [easy|normal|hard]` (вместо `/сложность` из В3а).
- Q2–Q7 — (а) по рекомендациям. План принят («окей, кабаним», 2026-10-14).
- Сигнатуры сетки сокращены ради smells (≤5 параметров): `run_cell(cell, context, seeds, difficulty=None)` (`cell` = `(класс, уровень, сцена)`, `context` = `(registry, cfg)`), `run_grid(context, grid, seeds, difficulty=None)` (`grid` = `(классы, уровни, сцены)`); тесты `test_sim_grid.py` поправлены под них.
