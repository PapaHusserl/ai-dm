# План партии К7к «Бой: иммунитеты, снаряжение монстров, сложность» (papa-kaban, 2026-10-14; на аппрув проектировщика)

Вписано оркестратором (у papa-kaban нет Write).

Задача: R4 #9 / R5 #13 по решениям `docs/plan-k7k.md` («Решения проектировщика», 2026-10-13): **В1а** порог К-6
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
4.4. Первый прогон (200 сидов, 25 клеток) → `--write-baseline` и таблица в `docs/plan-k7k.md` (вместе с
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
пересчёт КД по `equipment` (В6), чтение `equipment.weapons` в бою, + уровни 2–5 сетки, если перенесены». `docs/plan-roadmap-r2.md`:
:41 «К-6: порог снят 2026-10-13 (В1а)»; :202 убрать «мелочи следопыта (перенос Метки охотника, Истребитель орд, смена
Добычи)» из К7к (в R4 они в К7х, строка :203 — оставить); строка К7х — «+ пересчёт КД по `equipment`». `docs/HANDOFF.md`:
строка К7к. `docs/ARCHITECTURE.md`: модель монстра (поля 1.1, 2.1, «КД — число»), «урон в бою — только `engine.damage`,
состояния на монстра — `engine.impose`», трофеи (доспех/щит, `body_equipment`, семантика `equipment` None/задано/пусто),
D6 — сложность (`settings.difficulty` → tier), п. 23 Devtools — `sim_grid`, `make sim-grid`, базовая линия. `docs/TZ.md:102`
— «бюджет по уровню героя и сложности кампании». Чек-лист `checklist-k7k-live.md` (не коммитить; живой прогон — общий
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
   `make test`; `S_WIN`, golden и `test_criterion1` без изменений; таблица в `docs/plan-k7k.md`.
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

## Отклонения при реализации (2026-10-14, ревью docs/plan-k7k.md)
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

## Решения: Груминг партии К7к — бой: иммунитеты, снаряжение монстров, сложность (свинопас, 2026-10-13) (бывш. docs/decisions/k7k-grooming.md)

Вписано оркестратором (у свинопаса нет Write).

Источники:
- roadmap-r4-unified #9 «К7к» (строка 60), #10–11 (К7х, К7д — для границ);
- roadmap-r5-proposal #13 (строка 160, «без изменений»), К7х — строки 127–132;
- ROADMAP #13–16 (M, v9, вместе с К7х/К7д/5а — 1,85 млн по шкале R6);
- BACKLOG 6 (сложность), 11 (иммунитеты в данных, зверь-спутник в бою), 22 (В14 — доспехи и щиты с тел), 44 (зверь — «механика в бою — К7»);
- ROADMAP-PLAN К-6 (строки 41, 373), k0-grooming В9 (поле `equipment`), docs/plan-k1.md (решение проектировщика о сложности);
- HANDOFF (роли, правила).

Код на ec5faef: `rules/damage.py`, `content/models/monsters.py`, `srd/data/monsters/*`, `srd/data/armor/*`, `state/creature.py`, `state/combat.py`, `state/world.py`, `state/hero.py`, `combat/end.py`, `combat/trophies.py`, `combat/disarm.py`, `rules/loot.py`, `protocol/handlers/loot_gear.py`, `protocol/handlers/combat.py`, `protocol/handlers/world.py`, `rules/encounter.py`, `config/settings.py`, `devtools/sim_combat.py`, `master/prompts/narrator_rules.md`.

### Груминг

#### Готовность

**Не готова к плану до ответов на В1, В2, В4** (блокирующие). Остальное закрывается по рекомендации.

Расхождения роадмапа с кодом:
- **Порог К-6 противоречит принятому решению.** К-6 требует не меньше 80 % побед героя 1-го уровня. Проектировщик 2026-10-13 принял, что воин в goblins3 побеждает в 32 % боёв, и сказал «бой не подкручивать» (docs/plan-k1.md). Оба решения сразу выполнить нельзя (В1).
- **`warn_danger` уже сделан полностью.** Есть запрос, отметка на локации и её предках, основание боя сверх бюджета и правило рассказчика (факт 7). Что К7к должна сделать по п. 6, неясно (В4).
- **Иммунитеты, сопротивления и уязвимости в движке уже есть, но их никто не использует.** `apply_damage` их принимает, ни один вызов их не передаёт. Монстров во всём контенте три, и по SRD таких свойств у них нет (факт 1). Без К7д механика в живой игре не проявится (В2).

#### Что есть в коде (факты)

1. **Урон по типам.**
   - У `apply_damage` есть параметры `resistances`, `vulnerabilities`, `immunities` (`rules/damage.py:54–90`). Порядок обработки: иммунитет, затем сопротивление (половина), затем уязвимость (×2). Каждый шаг даёт строку в журнал.
   - Сопротивления берутся также из черт вида и из эффектов `resist`.
   - Ни один из 10 вызовов (`combat/mastery.py:73`, `engine.py:385`, `move.py:24`, `attack.py:314/366/488`, `improvise.py:93`, `cast.py:177/271/307`, `damage.py:131`) эти три параметра не передаёт.
   - У модели `Monster` таких полей нет (`content/models/monsters.py`). `ContentModel` неизвестных ключей, скорее всего, не пропускает (`extra=forbid`), поэтому данные без правки модели не загрузятся.
   - Монстров во всём контенте три: `goblin_warrior`, `goblin_boss`, `guard`. В паках `campaigns/*` своих монстров нет. По SRD ни у одного из трёх иммунитетов и сопротивлений нет.
   - Иммунитет к состояниям (`condition_immunities`) не моделируется нигде. Есть только `parley.immune_types` по типу существа (`config/settings.py:60`).
2. **Снаряжение монстра (поле К0, В9а).**
   - `Equipment{armor, shield, weapons}` объявлен в `state/creature.py:60`. Поле `equipment: Equipment | None` («None — по статблоку») есть у `Participant` (`state/combat.py:102`) и у `NPC` (`state/world.py:101`).
   - Поле никто не читает и не пишет: grep `.equipment` в `combat/`, `game/`, `protocol/` находит только героя и предысторию.
   - В статблоке `Monster` доспеха и щита нет, КД задан числом (`ac: 15`). По SRD у воина-гоблина кожаный доспех и щит, у стражника кольчужная рубаха и щит.
   - В `srd/data/armor/` есть `chain_mail`, `leather_armor`, `shield`, `studded_leather`. **Кольчужной рубахи (`chain_shirt`) нет**, это пробел данных.
3. **Трофеи с тел.**
   - После победы `settle_ground` (`combat/end.py:87`) пишет `state.gear = trophies.enemy_gear(...)` (`combat/trophies.py`).
   - Сейчас это только оружие из `action.weapon_id` (через `disarm.weapon_ids`) плюс квестовые предметы.
   - Цену и качество трофея задают `body_gear` и `trophy_quality` по ПО (`rules/loot.py:106`, `LootConfig.trophy_quality`). Босс отдаёт вещь по полной цене.
   - Герой забирает добычу через `gold_loot` → `loot_gear` (`protocol/handlers/loot_gear.py`), один раз.
   - Доспех и щит сюда добавляются тем же путём, нужен только источник «что надето».
4. **Мутации из роадмапа:**
   - `gold_loot` (`protocol/handlers/loot_gear.py:8`);
   - `finish_combat` (`game/combat_flow.py:210`);
   - `strip_weapon` (`combat/disarm.py:108`);
   - `settle_ground` (`combat/end.py:87`);
   - `pick_valuables` (`rules/inventory.py:245`).
5. **Бюджет боя.**
   - `party_budget` (`rules/encounter.py:5`) считается по уровню героя и `cfg.encounter.tier` (`low/moderate/high`, по умолчанию moderate, `config/settings.py:167`). Это глобальный конфиг, у кампании своего значения нет.
   - Лишних врагов `fit_to_budget` срезает с конца списка. Основание для боя сверх бюджета: `warn_danger`, бой начал герой или сработал `kills_hero` (`encounter.override_reason`).
   - Бюджет считается на одного героя, спутник в нём не учитывается.
6. **Место под параметр кампании без новых полей есть:** `WorldState.settings: dict[str, int|str|bool]` (`state/world.py:282`). Это поле уже уходит в контекст мастера (`master/prompt.py:237`). Значит, сложность кампании укладывается в сейв v9 без миграции.
7. **`warn_danger`:**
   - запрос (`protocol/requests.py:521`);
   - обработчик (`protocol/handlers/world.py:441`: `DangerMark` и флаг `danger:<loc>`);
   - учёт в бюджете (`encounter.danger_marked`, с проверкой предков локации);
   - правило рассказчика (`narrator_rules.md:68`).

   Игроку отметка опасности отдельно не показывается: есть только строка журнала «Опасность в …».
8. **sim_combat** (`devtools/sim_combat.py`, 146 строк).
   - Сценарий один (`goblins3`), варианта два: `default` — воин 1-го уровня, `weak` — волшебник 1-го уровня.
   - Герой собирается через `game/starter.fighter_choices/wizard_choices`. Перебора уровней и классов нет (пометка К0б это подтверждает).
   - Для сетки «класс × 1–5 × стартовая сцена» нужны: сборка героя любого из 5 классов, подъём на 2–5 уровень (готовые выборы ПХ, подкласса, заклинаний), стартовые сцены каждого пака.
   - Сейчас (docs/plan-k1.md): воин 32 % побед, волшебник 0 %.
9. **Зверь-спутник.**
   - `Companion{name, kind, notes}` (`state/hero.py:135`). Статблока нет, в `combat/` спутник не упоминается вовсе.
   - Статблоков зверей в контенте нет.
   - BACKLOG 11 и 44 относят «зверя в бою» к К7, но в строке К7к R4 его нет.

#### Вопросы

**В1 (блокирующий). Порог К-6 (≥ 80 %) против решения 2026-10-13 (32 % принято).**
- (а) Порог К-6 снять. Сетка sim_combat только измеряет и печатает таблицу, тест проверяет «не хуже базовой линии − допуск», чтобы ловить случайные регрессии баланса.
- (б) Порог 80 % оставить для сложности «лёгкая» параметра кампании (В3): на ней стартовая сцена проходится в 80 % случаев, «обычная» остаётся как есть.
- (в) Добиваться 80 % на обычной сложности: правка стартовых сцен и бюджета. Это противоречит решению 2026-10-13.

Рекомендация: **(б)**. Принятое решение остаётся в силе, у К-6 появляется смысл, а у параметра кампании — проверяемое назначение.

**В2 (блокирующий). Данные для иммунитетов, сопротивлений и уязвимостей.**
- (а) В К7к: поля модели `Monster` (`damage_immunities`, `damage_resistances`, `damage_vulnerabilities`; `condition_immunities` — см. В5), передача во все 10 вызовов `apply_damage` через одну функцию движка, тесты на подставных монстрах. Настоящие данные — в К7д (20–30 монстров SRD, там они будут: нежить, элементали).
- (б) То же, плюс 1–2 монстра SRD с сопротивлениями прямо в К7к (например, скелет и зомби), чтобы показать механику в живом прогоне К7к.
- (в) Перенести механику целиком в К7д: без данных она мертва.

Рекомендация: **(а)**. Живой прогон и так общий на К7 (после К7д, R4 #11). Размер К7к не растёт.

**В3. Параметр сложности кампании.**
- (а) `world.settings["difficulty"]` = `easy` / `normal` / `hard`, соответствует `tier` low / moderate / high бюджета. Значение по умолчанию берётся из `cfg.encounter.tier`. Выбор в меню нового мира и командой (например, `/сложность`). Без полей сейва.
- (б) Только конфиг (как сейчас), без выбора в мире.
- (в) (а) плюс множитель HP и урона монстров.

Рекомендация: **(а)**. Укладывается в v9, (в) меняет SRD-статблоки.

**В4 (блокирующий). Что остаётся от `warn_danger` п. 6** (факт 7: механика готова).
- (а) Ничего, пункт снять как сделанный.
- (б) Показывать игроку отметку опасности: в описании локации или карте и в `/journal` («здесь опасно: …»), чтобы предупреждение не жило только в одной строке журнала.
- (в) Рассказчик обязан ставить `warn_danger` перед боем сверх бюджета на сложности `easy` (правило промпта).

Рекомендация: **(б)**, S внутри партии. Без этого «предупреждение» видно, только если рассказчик сам его пересказал. Нужно подтверждение, что это и имелось в виду.

**В5. Иммунитеты к состояниям.**
- (а) В К7к только поле в модели и проверка при наложении состояния (`condition_immunities`).
- (б) Отложить в К7д вместе с данными.

Рекомендация: **(а)**. Это та же правка модели, наложение состояний идёт через одну точку.

**В6. Доспех и щит с тел (В14 CUSTOM-ITEMS).**
- Источник «что надето»:
  - (а) поля статблока `Monster.armor` и `Monster.shield` (данные SRD), `Participant/NPC.equipment` переопределяет их;
  - (б) только `equipment` экземпляра, заполняемое рассказчиком при `start_combat`.
- Пересчитывать ли КД по `equipment`:
  - (в) нет, КД берётся из статблока;
  - (г) да, если `equipment` задан.
- Данные: добавить `chain_shirt` (стражник).

Рекомендация: **(а) + (в)**. Трофеи идут тем же путём, что оружие (`body_gear`, качество по ПО). Пересчёт КД — новые правила, их лучше делать в К7х, вместе с отбором оружия, где `equipment.weapons` тоже нужен.

**В7. Зверь-спутник в бою (BACKLOG 11, 44: «К7»).**
- (а) Не в К7к. Отдельной строкой в К3 (следопыт 3–5, Повелитель зверей) или своей S-партией. Нужны статблоки зверей (данные К7д) и связь `Companion.kind` → `monster_id`.
- (б) В К7к: участник `side=heroes`, `controller=auto_hero`, статблок по `kind`. Партия вырастает до M+/L.

Рекомендация: **(а)**. В строке К7к R4 зверя нет, данных зверей нет. Записать в BACKLOG 44, куда именно.

**В8. Сетка sim_combat «класс × 1–5 × стартовая сцена» — объём.**
- (а) 5 классов × уровни 1–5 × сцена goblins3 плюс по одной стартовой сцене на каждый пак. Готовые выборы уровней — фикстуры в `devtools`. Прогон через `make sim-grid`, не в общем `make test`.
- (б) Только 5 классов на 1-м уровне в goblins3.

Рекомендация: **(а)**. Это суть К-6, но сетка ощутимо раздувает партию: оценить в плане papa-kaban. Если не влезает в M — (б) в К7к, уровни 2–5 в К7д.

**В9. Бюджет боя и спутник.** `party_budget` считает одного героя.
- (а) Без изменений до В7.
- (б) Сразу учитывать спутника.

Рекомендация: **(а)**.

**В10. Иммунитет к немагическому оружию** (SRD 5.2: «сопротивление дробящему, колющему, рубящему от немагических атак»).
- (а) В К7к не делать: магического оружия в механике нет. Запись в BACKLOG.
- (б) Поле `nonmagical_only`.

Рекомендация: **(а)**.

#### Риски

- Передача иммунитетов в 10 точках урона: легко пропустить одну. В плане нужна одна обёртка движка и тест «каждый путь урона учитывает иммунитет» (по одному на путь).
- Сетка sim_combat долгая: держать её отдельно от `make test`. Golden `goblins3_win.txt` не трогать.
- `narrator_rules` растёт (В3, В4): седьмой подъём WINDOW мока (BACKLOG 45). В плане предусмотреть ужимку правил на столько же строк, сколько добавлено.
- Мутации по 5 функциям роадмапа: `settle_ground` и `gold_loot` правятся этой партией (трофеи), их тестировать обязательно.

Расход свинопаса: ~50 тыс. токенов.

### Аудит (кабан-свекровь)

Кабан-свекровь, 2026-10-13 (вписано оркестратором). Код смотрела на рабочем дереве при HEAD ec5faef. Источники для сверки: roadmap-r4-unified:60–62, ROADMAP-PLAN:41, 196–203, 373, ROADMAP:25, K0-PLAN:462 (Q14), docs/plan-k1.md:16, 23. BACKLOG и roadmap-r5 не перечитывала.

| Находка | Вердикт |
|---|---|
| `apply_damage` принимает resist/vuln/immun, ни один из 10 вызовов их не передаёт (список мест верный) | подтверждено |
| `ContentModel` с `extra="forbid"` (common.py:105). В груминге написано «скорее всего» | подтверждено, оговорка лишняя |
| Монстров три, `chain_shirt` нет в srd/data/armor | подтверждено |
| `condition_immunities` нет, есть только `parley.immune_types` | подтверждено |
| `WorldState.settings` (world.py:282), 5 мутируемых функций и `party_budget` на указанных строках | подтверждено |
| К-6 ≥ 80 % (PLAN:41) против решения «32 % принято, не подкручивать» (k1-sim-combat:23) | подтверждено. В1 блокирующий обоснованно |
| В1(б): «лёгкая» сложность ради 80 % | новое значение параметра, которого нет ни в одном источнике. Чтобы получить 80 %, `low`-бюджет, скорее всего, придётся подстраивать, а это и есть «подкрутка». К проектировщику, рекомендацию по умолчанию не принимать |
| В3(а): пункт в меню нового мира и команда `/сложность` | в R4 сказано только «параметр сложности кампании», про интерфейс ничего. Расширение, к проектировщику |
| В4(б): показывать отметку опасности на карте и в `/journal` | новая функция интерфейса, в R4 её нет. Вопрос задан честно, нужен явный ответ. Вариант (а) «снять как сделанный» равноправен |
| В6(а): новые поля статблока `Monster.armor/shield` | прослеживается к п. 22 (В14), оставить |
| В6: «пересчёт КД — в К7х» | в строке К7х R4 (#10) пересчёта КД нет. Груминг молча добавляет объём в соседнюю партию. Убрать или к проектировщику |
| В6 не учитывает K0-PLAN Q14: «К7к различает "не задано" и "снято"» | пропущен вопрос: кто и когда пишет `equipment` (снятое оружие через `strip_weapon`, снятый доспех) и не выдаст ли тело повторный трофей |
| В8 запасной вариант «уровни 2–5 — в К7д» | К7д — партия данных («д»), код сетки в неё не по профилю. Нужна К7х или своя партия, к проектировщику |
| В8(а): новая цель `make sim-grid` и фикстуры уровней | прослеживается к п. 6. Цель make не согласована, но по сути мелочь, оставить |
| В2(а): механика без живых данных до К7д | соответствует R4 (живой прогон К7 после К7д). Блокирующий статус спорный, рекомендация разумная |
| В7 (зверь вне К7к), В9, В10 | соответствуют границам R4, оставить. В10: «запись в BACKLOG» допустима |
| Мелочи следопыта в ROADMAP-PLAN:202 числятся в К7к, а в R4 вынесены в К7х | груминг верно идёт по R4. Стоит поправить PLAN:202, иначе источники расходятся |
| Оценка M при сетке 5×5×паки | риск того, что партия вырастет до L, назван. Оценку проверить в плане |

**Решения за проектировщика:** молча ничего не принято, всё вынесено в вопросы. Но рекомендации В1(б), В3(а) и В4(б) вместе добавляют новый смысл «лёгкой» сложности и два элемента интерфейса, которых нет в источниках. Их нельзя закрывать «по рекомендации», нужен явный ответ. Перенос пересчёта КД в К7х тоже требует ответа.

**Итог:** факты по коду верны. Блокирующие В1 и В4 обоснованы, В2 можно закрыть по рекомендации. Добавить вопрос по Q14 («снято» против «не задано»). Убрать или согласовать перенос КД в К7х и запасной вариант «код сетки в К7д».

Расход: svinopas ~63 тыс., svekrov ~25 тыс.

### Решения проектировщика (2026-10-13)

- **В1 — (а):** порог К-6 ≥ 80 % снят. Сетка sim_combat измеряет и печатает таблицу; тест — «не хуже базовой линии − допуск».
- **В2 — (а):** поля и передача во все пути урона, тесты на подставных монстрах; данные — К7д.
- **В3 — (а):** `world.settings["difficulty"]` easy/normal/hard ↔ tier low/moderate/high, по умолчанию из `cfg.encounter.tier`; выбор в меню нового мира и командой `/сложность`.
- **В4 — (а):** пункт `warn_danger` снят как сделанный.
- **В5 — (а)**, **В7 — (а)** (зверь — не в К7к, записать в BACKLOG 44), **В9 — (а)**, **В10 — (а)** (запись в BACKLOG).
- **В6:** (а)+(в) — доспех/щит из статблока, `equipment` переопределяет, КД в К7к не пересчитывается; `chain_shirt` в данные. **Пересчёт КД по `equipment` — добавить в К7х.**
- **В8 — (а)**; если сетка не влезает в M — уровни 2–5 переносятся в **К7х** (не в К7д).
- **В11 (новый, по аудиту, K0-PLAN Q14) — ок:** различать «не задано» (по статблоку) и «снято»; снятие отмечается у существа, трофеи из статблока исключают снятое — без повторного трофея.
- ROADMAP-PLAN:202 — мелочи следопыта перенести в К7х (как в R4).

## Правки по ревью: Ревью партии К7к «Бой: иммунитеты, снаряжение монстров, сложность» (мама-кабан, 2026-10-14) (бывш. docs/decisions/k7k-review.md)

Вписано оркестратором (у mama-kaban нет Write).

План: docs/plan-k7k.md (решения проектировщика Q1а–Q7а) и груминг docs/plan-k7k.md. Смотрел незакоммиченный код kaban в src/, srd/data, devtools, Makefile и docs. Тесты kaban-doeba не смотрел, `make test` не запускал. `make smells` показал 206 при лимите 206: лимит соблюдён, но запаса не осталось (до партии было 204).

### Сделано по плану
- Урон. Все девять путей урона в бою идут через `CombatEngine.damage`: царапина, `burn`, три пути `cast`, опасная зона, метка, особый урон оружия, основной удар и `improvise`. В src остались ровно два вызова `apply_damage(`: внутри `engine.damage` и `roll_hazard` (герой вне боя, по плану не трогаем). Пропущенных путей урона нет.
- Состояния. Все три места, где состояние кладётся на монстра, идут через `engine.impose`: Topple, `apply_prone` и Опутывающий удар. `downed`, `death_saves`, `stealth` и `hidden` обходят `impose`, как и задумано.
- Модель и данные. В `Monster` добавлены поля трёх списков урона, `condition_immunities`, `armor` и `shield`. В `loader.check_refs` проверяются состояния и что доспех не щит, а щит — щит. Добавлен `chain_shirt.yaml` (13 / dex_cap 2 / 5000 cp). У трёх монстров прописаны доспех и щит, значения `ac` сходятся.
- Трофеи. Есть `body_equipment`, `enemy_gear` берёт оружие, доспех и щит, `loot.gear_cost` через `find_item`. Босс получает полную цену.
- Сложность. Добавлены `tier_of`, `party_budget/budget_text(…, tier)` и `game/difficulty.py` по образцу `tone.py`. Есть команда `/difficulty` (Q1), меню и флаг `--difficulty` в духе `--preset`, `new_world_from_pack(difficulty=)`. Подсказка в `--replay` дополнена.
- Сетка. Есть `sim_grid` и `grid_heroes`, `make sim-grid` в `.PHONY`, но не в `quality`. Базовая линия лежит в `devtools/sim_grid_baseline.yaml`.
- Документы. ARCHITECTURE описывает семантику `equipment` (None / задано / пусто), строка К7х есть в ROADMAP-PLAN.

### Отклонения kaban — оценка
- `body_equipment(engine, ref, weapon_ids)` с параметром из-за цикла импорта (`disarm` → `trophies`). Принять. Минус: `weapon_ids` берётся из параметра, а `lost_weapons` импортируется напрямую из `attack`. Источник «выбитого» один и тот же, так что терпимо.
- `body_refs` и `mark_looted` вынесены отдельно. Принять: `body_refs` убрал дубль фильтра тел, по смыслу это пункт 2.5 плана.
- `hero/difficulty` в `build_scenario`, а не в `build_goblins3`. Принять: поведение по умолчанию прежнее, сигнатура `build_goblins3` не тронута.
- Запись в хронику с kind `"event"` вместо `"difficulty"`. Принять. `ChronicleEntry.kind` — это Literal, и новое значение было бы правкой схемы сейва, которой план запрещает. Отметить отклонение в плане или HANDOFF.
- Плут и жрец заданы фиксированными `CharacterChoices`, а не «первыми по списку». Принять: так детерминированнее, состав соответствует Q5а.
- Флаг `sim_grid --baseline PATH`. Принять: нужен тестам, чтобы не трогать файл в репозитории.

### Замечания
1. **Слой content импортирует rules.** В `content/models/monsters.py` добавлен импорт `from ai_dm.rules.roll_pipeline import DAMAGE_TYPE_WORDS`. Это первый импорт rules в `content`, и он тянет `rules.creatures`, `modifiers` и `state.*` в загрузку моделей. Предлагаю убрать `field_validator check_damage_types` из модели и проверять типы урона в `loader.check_refs` рядом с проверкой `condition_immunities`, с той же строкой `bad(...)`. Проверку повторов можно оставить в модели без импорта.
2. **Опутывающий удар при иммунитете** (`attack.py: weapon_rider`). Код сначала пишет в лог «лозы оплетают», затем бросает спасбросок и только после провала проверяет иммунитет. Концентрация снимается молча, без строки «{name} кончается», которая есть в ветке успеха. Поведение по SRD верное, но лог рвётся. Минимальная правка: в ветке `if not engine.impose(...)` добавить `engine.log(f"  {name} кончается")`, как в ветке `success`. Порядок «спасбросок, потом иммунитет» не трогать: так ГСЧ и replay остаются прежними.
3. **`--difficulty` в сетке ничего не меняет.** `goblins3` собирает врагов фиксированно, через `start_combat` и `fit_to_budget` бой не проходит. Поэтому `world.settings["difficulty"]` в `build_scenario` и флаг `sim_grid --difficulty` на результат не влияют. План (4.1/4.3) этого требовал, так что kaban всё сделал правильно; вопрос — убрать параметр или записать, что он «на будущее, для сцен с бюджетом (К7д)».
4. **Дубль списка сложностей.** В `sim_grid.py` стоит `choices=("easy", "normal", "hard")`, хотя рядом есть `game.difficulty.DIFFICULTIES`. Нужно импортировать `DIFFICULTIES`.
5. **Подпись меню не следует конфигу.** В `cli.py` `DIFFICULTY_AS_CONFIG = "Как в конфиге (умеренный)"` захардкожено. Если `cfg.encounter.tier = "high"`, меню соврёт. Собирать подпись по `TIER_WORDS[settings.rules.encounter.tier]` или убрать скобку.
6. **В11, где граница поведения.** `mark_looted` очищает `npc.equipment`, даже если игрок не забрал `gear`: вещи пропадают. По В11 это верно. Отметить в ARCHITECTURE рядом с `mark_looted`, что «снято» означает «посчитано в трофеи боя», а не «взято игроком».
7. **Smells 206/206.** Запаса нет. Вынести три новые проверки монстра из `check_refs` в отдельный `check_monster_gear(...)` по образцу соседей и проверить, вернётся ли 204–205. Если нет — причину в HANDOFF; лимит не поднимать.
8. **Мелочь.** `difficulty.current` при `tier`, которого нет в `DIFFICULTY_TIERS`, упадёт с `StopIteration`. Сейчас невозможно (конфиг — Literal), правка не нужна.
9. **Базовая линия сетки.** У плута, жреца и волшебника на уровнях 1–3 доля побед 0–1,5 %, допуск 10 п.п. там ничего не проверяет. Наблюдение для docs/plan-k7k.md и К7д.

**Вердикт:** нужны правки. Замечания 1, 2 и 4 мелкие, 5 и 7 желательны, 3 — вопрос к плану, 6 — строка в документах. Блокирующих багов в путях урона, иммунитетах и трофеях нет.

Расход mama-kaban: ~51 тыс.

### Решения
- Замечания 1, 2, 4, 5, 6, 7 — править (оркестратор по рекомендации ревью).
- Замечание 3 — (а), проектировщик 2026-10-14: параметр `difficulty` в сетке оставить, пометить «на будущее, для сцен с бюджетом (К7д)» в K7K-PLAN/ARCHITECTURE и `sim_grid --help`.
- 8, 9 — к сведению (9 — строкой в docs/plan-k7k.md).

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **К7к груминг+аудит+решения ✅ 2026-10-13** — docs/plan-k7k.md (живой прогон по-прежнему отложен проектировщиком). Решения: В1а (порог 80 % снят), В3а, В4а (warn_danger сделан), В6 — пересчёт КД в К7х, В8 — запас уровней 2–5 в К7х, В11 (снято/не задано) — ок; прочее по рекомендациям. Расход: svinopas ~63 тыс., svekrov ~25 тыс. Дальше — план papa-kaban docs/plan-k7k.md (в работе), затем аппрув.
- **К7к план papa-kaban ✅ 2026-10-14** — docs/plan-k7k.md (≈0,85–0,9 млн; расход papa ~187 тыс.). Ждём ответы на Q1–Q7 и «окей, кабаним».
- **К7к код ✅ 2026-10-14 (kaban; ревью mama-kaban и тесты doeba впереди, не закоммичено):** `engine.damage`/`engine.impose` (иммунитеты/сопротивления/уязвимости и иммунитет к состояниям), `Monster.armor/shield` + `chain_shirt`, трофеи доспех/щит (`trophies.body_equipment`, `mark_looted`), сложность (`/difficulty`, `--difficulty`, меню, `encounter.tier_of`), сетка `sim_grid` + `make sim-grid` + `devtools/sim_grid_baseline.yaml` (docs/plan-k7k.md). smells 206/206, ruff/dead чисто. Чек-лист живого прогона — checklist-k7k-live.md.
- **К7к ✅ закоммичена 2026-10-14:** тесты 14829 passed, cov 97,35 %, smells 204/206, dead чисто; mutmut — K7k-строки убиты. Ревью docs/plan-k7k.md (все правки внесены; 3а — difficulty в сетке «на будущее, К7д»), отклонения — K7K-PLAN «Отклонения при реализации», сетка — docs/plan-k7k.md. BACKLOG 50, 51. Расход: svinopas ~63, svekrov ~25, papa ~187, kaban ~160+180+190, doeba ~347, mama ~55 тыс. (субагентные счётчики). Му-р вставлен в роадмап (поле в Ж0, код хвостом Ж3; замер BACKLOG 45 в Ж0; papa ~75 тыс.). Живой прогон по-прежнему отложен проектировщиком (чек-листы r1-f1-r2, k1, k7k). **Дальше:** груминг К7х (svinopas + kaban-svekrov).

## Приложение: К7к: сетка sim_combat «класс × уровень × сцена» — базовая линия (шаг 4.4) (бывш. docs/decisions/k7k-sim-grid.md)

Сцена `goblins3` (воин/жрец/плут/волшебник/следопыт против трёх гоблинов, `intent = kill`), сиды `range(200)`, герои из
`devtools/grid_heroes.py` (1 ур. — пресеты арн/лиэль/грей и свои наборы `a` для плута и жреца; 2–5 ур. — `auto_level`:
средние HP, первый вариант в каждом выборе, ASI `+2` к первой характеристике из списка). Код: расширение К7к поверх ec5faef
(движок К7к не меняет исходы: воин 1 ур. = 64/200, как в `docs/plan-k1.md`). Время прогона всей сетки (25 клеток × 200
боёв = 5000 боёв): ≈ 30 с.

| Класс | 1 ур. | 2 ур. | 3 ур. | 4 ур. | 5 ур. |
|---|---|---|---|---|---|
| воин | 64/200 (32,0 %) | 139 (69,5 %) | 174 (87,0 %) | 195 (97,5 %) | 199 (99,5 %) |
| плут | 0 (0,0 %) | 2 (1,0 %) | 3 (1,5 %) | 15 (7,5 %) | 34 (17,0 %) |
| жрец | 0 (0,0 %) | 0 (0,0 %) | 2 (1,0 %) | 10 (5,0 %) | 22 (11,0 %) |
| волшебник | 0 (0,0 %) | 16 (8,0 %) | 54 (27,0 %) | 104 (52,0 %) | 135 (67,5 %) |
| следопыт | 3 (1,5 %) | 12 (6,0 %) | 28 (14,0 %) | 44 (22,0 %) | 176 (88,0 %) |

Средние раунды — в `make sim-grid` (печатается таблицей). Базовая линия — `devtools/sim_grid_baseline.yaml` (доля побед в
процентах, допуск 10 п.п.); `make sim-grid` возвращает 1, если клетка хуже базовой − допуск. Порог К-6 ≥ 80 % снят (В1а),
сетка только измеряет.

### Факты сетки (не баги К7к)

- Допуск 10 п.п. не проверяет клетки с долей 0–1,5 % (плут, жрец, волшебник на 1–3 ур.): хуже нуля не бывает. Пересчитать базовую линию после К2/К3 и в К7д (замечание 9 ревью).
- Параметр `--difficulty` сетки пишет `world.settings["difficulty"]`, но `goblins3` собирает врагов фиксированно (мимо `start_combat` и бюджета) -- на результат он не влияет; оставлен на будущее, для сцен с бюджетом боя (К7д).

- Плут и жрец почти не побеждают: `auto_hero` не умеет скрытую атаку плута и лечение/боевые молитвы жреца (К2/К3 —
  BACKLOG). Низкие числа — факт данных, а не регрессия.
- Волшебник 1 ур. — 0 %: один выстрел заклинания против трёх гоблинов, как в К1 (`weak` = 0/200).
- Следопыт: резкий скачок на 5 ур. (14 % → 88 %) — второй удар/подкласс в `auto_level`; поведение `auto_hero` не калибровалось.
- Автоподъём детерминирован (первый вариант выбора), ASI `+2` даже волшебнику/жрецу достаётся первой характеристике из списка.
