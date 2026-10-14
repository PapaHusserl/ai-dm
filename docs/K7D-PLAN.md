# План партии К7д: монстры SRD 5.2 с ПО 0–5, черты, разгрузка smells, BACKLOG 52, сцена сетки с бюджетом (papa-kaban, 2026-10-14)

Вписано оркестратором (у papa-kaban нет Write). Груминг и решения — docs/decisions/k7d-grooming.md.

**Задача.** R4 #11 / R5 #14 по решениям `docs/decisions/k7d-grooming.md` («Решения проектировщика» и «Источник SRD 5.2», 2026-10-14):
- **В1:** первый шаг — −4–6 smells только в коде продукта, дальше нулевой баланс (трактовка — Q1).
- **В10, В9:** данные — Open5e v2 `srd-2024`, одноразовый скрипт вне репозитория; коммитятся только YAML.
- **В4:** список из 27 монстров ПО 0–5 — на утверждение.
- **В3(в):** 3 механики черт (Тактика стаи, Стойкость нежити, эффект при попадании с необязательным спасброском) плюс поле доп. урона второго типа в атаке. Остальные черты — текст для рассказчика.
- **В6, В7:** подключение только к подвалу Вейла; сцена сетки `cellar` с бюджетом; пересчёт базовой линии.
- **В5:** BACKLOG 52 в обеих точках.
- **В8:** без `shover` и `nonmagical_only`.
- **В11:** бюджет пересчитан.
- **В2:** исключение tests/devtools из smells уходит в BACKLOG.

Сейв v9 не меняется: новых полей в `TurnState`, `Participant`, `CombatState`, `CreatureState` нет. Схема запросов рассказчика не меняется. Меняются `Monster` и `MonsterAction` (контент) и `DamageResult` (не сейв). Код на 187d319, smells 206/206, WINDOW мока 25000.

## Что показал код (сверка перед планом)

**Монстры.**
- В `srd/data/monsters/` три монстра (`goblin_warrior`, `goblin_boss`, `guard`). Имена на русском, `source: srd-5.2`, `license: CC-BY-4.0`.
- Модель — `content/models/monsters.py`. Поле `advantage_damage_dice` у `MonsterAction` — прецедент «особого поля атаки».
- `Monster.traits` ссылается на id features (`loader.check_refs`, ~:159). Движок читает только `nimble_escape`.
- Атрибуция SRD уже есть в `LICENSE:24–35` и `README.md:215`.

**Природная броня (п. 4)** уже работает по В9(в): `engine.monster_armor_class` (`engine.py:200`) берёт `monster.ac`, а `gear_ac` подменяет только вклад статблоковых `armor`/`shield`. В данных достаточно, чтобы `ac` был числом из статблока, а `armor`/`shield` стояли только у монстров с названным в SRD снаряжением (Gear), которое есть в `srd/data/armor`. Кода не нужно, нужен тест согласованности данных. `armor_class_parts` (героя) природная броня не трогает — это расхождение груминга; разгрузка `armor_class_parts` идёт как чистый smells-рефакторинг.

**Урон и смерть монстра.**
- `engine.damage` → `apply_damage` (`rules/damage.py:54`).
- `downed.after_damage` (`downed.py:37`) получает `crit`, но в `monster_damaged` его не передаёт.
- Тип урона в `DamageResult` не хранится, а Стойкости нежити он нужен (излучение исключено).
- `merge_damage` (`attack.py:337`) складывает куски урона.

**Атака.**
- `attack()` (`attack.py:457`): `base_advantage` → `roll_attack(tags=attack_tags)` → урон, `special_damage`, `weapon_rider`, `after_damage`.
- Модификаторы броска — реестр источников (`engine.py:123–125`, `ElevationSource`/`CoverSource` в `zones.py:62–90`) по `request.tags`. Тактику стаи делать так же (источник + тег): тогда помеха «дальность» и преимущество стаи правильно гасят друг друга (`resolve_advantage`, `roll_pipeline.py:159`).

**Длительности состояний.** `Expiry` (`state/creature.py:19`): `end_of_turn` с `owner`/`value` и `rounds`. Повторных спасбросков в конце хода в движке нет.

**Толчок (BACKLOG 52).**
- `shove.may_shove`/`perform` (`combat/shove.py:38/45`), `available.shove_options` (`:351`).
- Импровизация героя: `improvise.check_request` (`:42`) → `spec_problem` (`:26`) → бросок → `apply_push` (`:98`) → `falling.push`.
- `SIZES`/`target_size` — `attack.py:376–384`; `target_size` работает и для героя, и для монстра.

**Бюджет боя.**
- `rules/encounter.py`: `party_budget`, `enemy_cost`, `tier_of`.
- `sim_combat.build_scenario` (`devtools/sim_combat.py:88`) собирает только `goblins3`, поэтому `--difficulty` ни на что не влияет. Сетка 25 клеток × 200 боёв ≈ 30 с.

**Рассказчик.**
- Видит только `monster_ids` (все id реестра, `master/prompt.py:239`) — статика каждого вызова, отсюда риск WINDOW.
- Черт и описаний монстров не видит: в `combat_data` (`prompt.py:329`) только ref/side/zone/status.
- Подвязки «монстры → пак» нет (Q8).

**Клад.**
- `individual_treasure.yaml` (`source: custom`) режет ПО по полосам 0–4/5–10/…, поэтому ПО 0–5 покрыты.
- `loot.defeated_treasure` (`rules/loot.py:34`) даёт монеты за любого побеждённого (Q2).

**Рисунки.** `art_for_monster`: id → `creature_type`. Для beast и undead рисунки есть, для elemental и construct нет (не блокирует).

**Подвал Вейла.** `campaigns/vale/locations.yaml` — `cellar`; `npcs.yaml` — Гракх (`goblin_boss`, capture).

**Smells: кандидаты в продукте:**

| Функция | Запах | Снимет |
|---|---|---|
| `rules/death_saves.py:72 after_damage` | return 12, сложность 24 (+ параметры 8) | −2 |
| `rules/derived.py:141 armor_class_parts` | сложность 32 | −1 |
| `combat/available.py:429 list_options` | сложность 23 | −1 |
| `combat/available.py:136 spell_entries` | сложность 19 | −1 |
| `combat/controllers.py:39 EngineTactics.choose_turn` | return 7 | −1 |
| `rules/rests.py:9 recover_pools` | сложность 19 | −1 (запас) |

Запахи «сложность файла» (`available.py` 175, `derived.py` 116, `attack.py` 121, `loader.py` 121) выносом функций внутри файла не снимаются. Новый файл — суммарная сложность < 50.

## Реализация (kaban)

### 0. Разгрузка smells — первым шагом, отдельным коммитом «К7д-0» (поведение не меняется, существующие тесты — оракул)
- 0.1. `death_saves.after_damage`: сигнатура прежняя; внутри `death = (cause, by, now_s, intervene)`; новые `fatal(hero, death)` (`divine_save` или `mark_dead`, сейчас трижды скопировано) и `hit_while_down(hero, result, crit, death)`. Итог: ≤ 5 return, сложность < 15.
- 0.2. `derived.armor_class_parts` — вынести `base_armor_parts`, `feat_ac_parts`, `effect_ac_parts`, `pierce_parts`. Список слагаемых — байт-в-байт тот же.
- 0.3. `available.list_options` — вынести `standard_actions(engine, ref, conditions)` и `bonus_actions(engine, ref)`. Порядок пунктов сохранить.
- 0.4. `available.spell_entries` — вынести `circle_options(engine, spell, circle, target, slots)`.
- 0.5. `controllers.EngineTactics.choose_turn` — хвост сближения вынести в `approach(options, ref)`.
- 0.6. Запас: `rests.recover_pools` → `best_recover(...)`, только если 0.1–0.5 дали меньше −5.
- 0.7. `Makefile`: `SMELLS_MAX` опустить до факта (≈ 200). Код шагов 2–7 проверять `make smells` сразу; рост компенсировать выносом, лимит не поднимать (Q1).

### 1. Импорт из Open5e — скрипт вне репозитория
- 1.1. Каталог вне дерева (scratchpad kaban или `~/projects/ai-dm-k7d-import/`): `raw/` (JSON), `tool/convert.py`, `out/`. Запуск — `python -I tool/convert.py raw/… out/`.
- 1.2. Скачать `https://api.open5e.com/v2/creatures/?document__key=srd-2024&limit=100&page=N` по `next` до `null`. **Сначала проверить, где черты:** `jq '.results[0] | keys'`. Ожидается `traits: [{name, desc}]`; если поля нет — `?depth=2`, затем фикстуры `open5e-api` `data/v2/wizards-of-the-coast/srd-2024/`, иначе Q10.
- 1.3. `convert.py`:
  - фильтр по списку 1.5;
  - соответствие полей:

    | Open5e | YAML |
    |---|---|
    | `size.key` | `size` |
    | `type.key` | `creature_type` |
    | `speed.walk` | `speed_ft` |
    | `speed.fly` | `fly_ft` (Q4) |
    | `armor_class` | `ac` |
    | `hit_points` | `hp` |
    | `hit_dice` | `hp_dice` |
    | `challenge_rating_text` | `cr` |
    | `ability_scores` | `abilities` |
    | `resistances_and_immunities.*` | `damage_*` и `condition_immunities`, ключи в нижнем регистре, проверка по `DAMAGE_TYPE_WORDS` и `conditions` |
    | `attacks` | `kind`, `reach_ft`, `range_*`, `attack_bonus`, `damage_dice`, `extra_damage_*` |

  - если `damage_type: null` при заполненном `extra_damage_type`, основной тип = `extra_damage_type`;
  - действия без атак и черты — комментариями `# TODO kaban` / `# trait: …`;
  - `source: srd-5.2`, `license: CC-BY-4.0`.
- 1.4. Контроль: прогнать три существующих монстра и сравнить с текущими YAML (не перезаписывать). Сверить с официальным PDF SRD 5.2: skeleton, zombie, ghoul, wight, wolf, giant_spider, fire_elemental, animated_armor; ещё 3 — mama-kaban на ревью.
- 1.5. **Список (27, ПО 0–5; ПО по памяти, точные — по импорту):**

  | Группа | id (ПО) |
  |---|---|
  | Нежить (8) | `skeleton` (1/4), `zombie` (1/4), `shadow` (1/2), `ghoul` (1), `specter` (1), `ghast` (2), `ogre_zombie` (2), `wight` (3) |
  | Элементали (6) | `steam_mephit` (1/4), `dust_mephit` (1/2), `magmin` (1/2), `gargoyle` (2), `fire_elemental` (5), `earth_elemental` (5) |
  | Конструкты (3) | `homunculus` (0), `animated_flying_sword` (1/4), `animated_armor` (1) |
  | Звери (10) | `hawk` (0), `giant_rat` (1/8), `mastiff` (1/8), `wolf` (1/4), `swarm_of_rats` (1/4), `boar` (1/4), `panther` (1/4), `black_bear` (1/2), `dire_wolf` (1), `giant_spider` (1) |

  Запас: `rug_of_smothering`, `warhorse_skeleton`, `ice_mephit`, `giant_wolf_spider`, `jackal`, `riding_horse`. Связь `Companion.kind → monster_id` остаётся в BACKLOG 44.
- 1.6. Доводка:
  - русские имена по `docs/glossary.md`;
  - `multiattack`;
  - `weapon_id`;
  - `armor`/`shield` только по Gear и только если `gear_ac == ac`;
  - `traits`, `on_hit`, `extra_*`;
  - тег `disarmer` (Q6).
- 1.7. Клад — проверка тестом. Новый код — только по Q2.

### 2. Механика черт — `combat/monster_traits.py` (новый, сложность < 50)
- 2.1. Features:
  - механические — `pack_tactics`, `undead_fortitude`, со строкой «Движок: …»;
  - описательные — `false_appearance`, `sunlight_sensitivity`, `spider_climb`, `keen_senses`, `flyby`, `swarm`, `death_burst`, `life_drain_note`, `incorporeal_movement`, `fire_form`, `earth_glide`, `illumination`, `water_susceptibility`, `antimagic_susceptibility` (по факту импорта), без чисел.
- 2.2. Модель:
  - `MonsterAction.extra_damage_dice`/`extra_damage_type` (оба или ни одного);
  - `HitRider`: `condition`, `save` + `dc`, `max_size`, `duration` (`target_turn` / `source_turn` / `minute`), `dice` + `damage_type`;
  - `MonsterAction.on_hit`;
  - `Monster.fly_ft` (Q4);
  - `loader.check_monster_actions` вызывается из `check_refs`.
- 2.3. `DamageResult.damage_types: list[str]`; `apply_damage` пишет тип; `merge_damage` складывает списки.
- 2.4. Тактика стаи: `has_trait`, `pack_ally` (боеспособный союзник в зоне цели, кроме самого атакующего), `PackTacticsSource` (тег `pack` → преимущество «тактика стаи»). `attack_tags` перестроить на один `return`. Регистрация в `CombatEngine.__init__`.
- 2.5. Стойкость нежити: `endures(engine, ref, dealt, crit)` срабатывает, если это не герой, есть черта, `dropped`, не крит и нет `radiant`. Тогда спас Тел СЛ 5 + урон; при успехе — 1 HP и лог. Вызов в `downed.after_damage` до `monster_damaged`.
- 2.6. Доп. урон: `monster_action`, `extra_damage` (`roll_damage` → `engine.damage` → `merge_damage`) — сразу после `special_damage`, до `after_damage`.
- 2.7. Эффект при попадании: `on_hit`:
  - если цели нет HP или `max_size` превышен — эффекта нет;
  - спасбросок;
  - урон при провале сливается в `dealt` до `after_damage`;
  - `impose` с `Expiry` по `duration`;
  - без повторных спасбросков (отметка в `rules-adaptation.md`).
- 2.8. Предсмертный взрыв — только описание (Q5б).

### 3. BACKLOG 52
- 3.1. `shove.size_ok(engine, ref, target)`: цель не больше чем на одну категорию крупнее.
- 3.2. В `shove_options` добавить условие в существующую проверку.
- 3.3. `improvise.check_request` → `spec_problem(...) or size_problem(...)` → `Rejected("target_too_large")` до броска, действие не тратится. `apply_push` не меняется (Q11). Проверить `test_import_cycles`.
- 3.4. `narrator_rules.md` не трогаем.

### 4. Подвал Вейла и рассказчик
- 4.1. (Q7а) Описание `cellar` дополнить; новая локация `old_crypt` («Старая крипта», `parent_id: cellar`, теги `[гробница, подвал]`, рисунок `tomb`); одна фраза в `world.md`.
- 4.2. (Q3а) `prompt.monster_trait_notes` → `combat_data.monster_traits` только в бою и только если не пусто; строки ≤ 100.
- 4.3. `disarmer`: `wight`, `goblin_boss` (Q6а).

### 5. Летающие (Q4а) — `falling.fall`
Монстр с `fly_ft > 0`, если не лежит и дееспособен, не падает (лог «парит»).

### 6. Монеты (Q2а) — `rules/loot.py`
`NO_COIN_TYPES = ("beast", "construct", "elemental")` в `defeated_treasure`; `hoard_treasure` не трогаем.

### 7. Сцена сетки `cellar` — `devtools/sim_cellar.py` (новый)
- `CELLAR_POOL`;
- `fill_budget` — детерминированный, жадный, `cap=6`;
- `build_cellar` (`difficulty` → `tier_of` → `party_budget`; зоны stairs/barrels/crypt);
- `SCENARIOS += cellar`, `sim_grid.SCENES += cellar`;
- пересчёт базовой линии: `goblins3` обязан совпасть с прежней;
- итог — `docs/decisions/k7d-sim-grid.md`.

### 8. Docs и атрибуция
- `srd/data/ATTRIBUTION.md` + ссылка из README.
- `rules-adaptation.md`.
- BACKLOG: 28/44/52/125 и новые пункты — В2, повторные спасброски/Recharge, рисунки elemental/construct, размер цели у `prone`, фильтр `monster_ids` по паку.
- ROADMAP:25, ROADMAP-PLAN, ARCHITECTURE, HANDOFF.
- Чек-лист `docs/checklist-k7d-live.md` (не коммитить). 10 пунктов: крипта, Стойкость, уязвимости скелета, стая, паралич упыря, сбивание волком, `disarmer` у Гракха, `/difficulty hard`, отказ `push` по огромному, крысы без монет.

## mutmut (сверено grep-ом; «новая» — пока нет в коде)

| Шаг | FUNCS | TESTS |
|---|---|---|
| 0 | `death_saves:after_damage`, `fatal`*, `hit_while_down`* | `test_death_saves`, `test_downed` |
| 0 | `derived:armor_class_parts`, `base_armor_parts`*, `feat_ac_parts`*, `effect_ac_parts`*, `pierce_parts`* | `test_derived` |
| 0 | `available:list_options`, `standard_actions`*, `bonus_actions`*, `spell_entries`, `circle_options`* | `test_available`, `test_option_cost`, `test_upcast` |
| 0 | `controllers:EngineTactics.choose_turn`, `approach`*; запас — `rests:recover_pools`, `best_recover`* | `test_controllers`, `test_rests` |
| Черты | `monster_traits:*` (новый модуль) | `test_monster_traits` |
| Черты | `attack:attack_tags`, `attack`, `merge_damage`; `downed:after_damage`; `damage:apply_damage` | `test_monster_traits`, `test_actions_attack`, `test_advantage_position`, `test_damage`, `test_downed` |
| Контент | `loader:check_monster_actions`*, `check_refs` | `test_monster_gear`, `test_srd_monsters_k7d` |
| Толчок | `shove:size_ok`*, `available:shove_options`, `improvise:check_request`, `size_problem`* | `test_shove`, `test_improvise` |
| Q2/Q3/Q4 | `falling:fall`; `loot:defeated_treasure`; `prompt:monster_trait_notes`*, `PromptBuilder.combat_data` | соответствующие тесты |
| Сетка | `sim_cellar:fill_budget`*, `build_cellar`*; `sim_combat:build_scenario` | `test_sim_cellar`, `test_sim_combat` |

\* — новая функция.

## Тесты (kaban-doeba, TDD)
**Правки существующих.**
- `test_srd_minimum` — новые ПО и XP.
- `test_master_prompt` — все id.
- Без правок: `test_art_catalog`, `test_schema_fingerprint`, golden `goblins3_win.txt`, `test_criterion1`, `test_sim_grid` (`goblins3`).
- `test_stage4_memory` — измерить пик (Q8).

**Шаг 0.**
- `fatal`/`hit_while_down`.
- `armor_class_parts`: байт-в-байт на 6 профилях.
- `list_options`: снимок порядка.
- `spell_entries`: апкаст, бесплатное применение, заряд.
- `approach`.
- `make smells`.

**Данные** (`test_srd_monsters_k7d.py`, параметризация по 27 id):
- загрузка; `source`/`license`;
- `cr`, `individual_treasure`;
- В9в: `gear_ac == ac`;
- `traits`/`on_hit` ссылаются на существующее;
- атаки разбираются;
- `multiattack` ссылается на существующие действия;
- конкретные иммунитеты — скелет, тень, огненный элементаль, анимированные доспехи;
- `disarmer`.

**Модель.** Валидаторы `HitRider`/`extra_*`; `check_monster_actions`.

**Тактика стаи:**
- союзник в зоне цели → преимущество;
- мёртвый, лежащий или недееспособный союзник → нет;
- союзник в другой зоне → нет;
- дальняя атака: преимущество стаи гасит помеху;
- без черты → нет;
- герой не считается союзником стаи;
- мутант `ally == ref`.

**Стойкость нежити:**
- успех → 1 HP, `monster_died` нет; провал → смерть и XP;
- излучение → без броска; крит → без броска;
- урон не довёл до 0 → без броска;
- `nonlethal`;
- `merge_damage` с излучением → без броска.

**Доп. урон:**
- паук — две строки урона;
- иммунитет скелета к яду;
- крит удваивает обе кости;
- смерть от второй части → `monster_died`;
- регресс у героя.

**Эффект при попадании:**
- паралич упыря: спасбросок, `Expiry`, меню, снятие;
- волк: Huge не сбивается;
- `source_turn`; `minute` → `rounds`;
- иммунитет к состоянию;
- цель на 0 HP;
- урон с событиями.

**BACKLOG 52:**
- матрица размеров `shove_options`;
- ключевой NPC;
- импровизация `push` по Huge → `Rejected`, действие и RNG не тронуты;
- по Large — бросок как раньше;
- `prone` без изменений.

**Q4.** Мефит «парит»; лежащий мефит падает; герой — без изменений.

**Q2.** Монеты только за не-зверей; RNG не тронут.

**Q3.** `monster_traits` в бою; без монстров с чертами ключа нет; вне боя нет; длина строки ≤ 100.

**Сетка:**
- `fill_budget` — по таблице, `cap`, пустой пул, детерминизм;
- `difficulty` меняет состав;
- `simulate` на 3 сидах;
- `sim_grid --scene cellar`;
- базовая линия: есть `cellar`, `goblins3` прежний.

**В конце:**
- pytest;
- `make cov` один раз (≥ 94 %);
- `make smells`, `make dead`, ruff;
- mutmut по списку;
- `make sim-grid --check`.

## Критерии приёмки
1. Smells: после шага 0 — на 4–6 ниже 206, `SMELLS_MAX` опущен; в конце партии не выше (Q1).
2. 27 монстров ПО 0–5:
   - русские имена;
   - иммунитеты, сопротивления и уязвимости из SRD 5.2;
   - `ac` по статблоку, `armor`/`shield` только по Gear;
   - атрибуция есть, скрипта в репозитории нет.
3. Работают в бою: Тактика стаи, Стойкость нежити, эффект при попадании, доп. урон второго типа. Прочие черты видны рассказчику в бою (Q3).
4. Толчок не действует на цель больше чем на одну категорию крупнее.
5. Подвал Вейла:
   - есть `old_crypt`, `disarmer` у Гракха;
   - `cellar` меняет состав по `--difficulty`;
   - базовая линия пересчитана, `goblins3` не изменилась.
6. Тесты:
   - зелёные, cov ≥ 94 %;
   - сейв v9 без правок отпечатка;
   - golden без перегенерации;
   - WINDOW — по Q8.
7. Docs обновлены (см. шаг 8).

## Оценка (шкала R6)
**S+/M− ≈ 0,85 млн** (0,8–0,95).

| Статья | Оценка |
|---|---|
| Груминг (svinopas, svekrov, dyadya) | ≈ 0,08 (факт) |
| papa | ≈ 0,17 |
| kaban: шаг 0 | ~40 тыс. |
| kaban: импорт и 27 YAML | ~100–120 тыс. |
| kaban: черты | ~50 тыс. |
| kaban: остальное | ~50 тыс. |
| doeba | ≈ 0,30–0,35 (~2 ч с mutmut) |
| mama | ≈ 0,06 |

Без Q3, Q4 и Q2 — −0,04. При Q10а — +0,04.

## Риски
- **Smells при нулевом балансе.** Логику нести в новые модули; новые функции — не больше 5 параметров и 5 return; `make smells` после каждого шага.
- **WINDOW.** +27 id ≈ +150–200 токенов статики каждого вызова. Измерить пик сразу после шага 1 (Q8).
- **`monster_ids` глобальны.** В «Пьяном драконе» рассказчик тоже может завести упыря (Q8).
- **RNG и golden.** `goblins3` не должен меняться; любое изменение — баг.
- **Open5e.**
  - Структура не проверена в сети: шаг 1.2 начинается с `jq keys`.
  - `damage_type: null`.
  - Доспех у статблоков 2024 указан в Gear.
- **Порядок урона и событий.** Доп. урон и урон эффекта должны попасть в `dealt` до `after_damage`.
- **Паралич героя** даёт автокриты вблизи: бой с двумя упырями для героя 1 ур. смертелен. Калибровать — только по решению проектировщика.
- **Цикл импортов** `shove` ↔ `improvise`. При цикле `size_ok` переносится в `attack.py`, отклонение записать.
- **`--check` сетки** — только без `--difficulty`.
- **mutmut на macOS** — только узкие TESTS.

## Открытые вопросы
- **Q1 Нулевой баланс smells.**
  - (а) **рек.** После шага 0 `SMELLS_MAX` = факт (≈ 200), партия в конце ≤ него.
  - (б) В конце ≤ 206.
- **Q2 Монеты за зверей, конструктов и элементалей.**
  - (а) **рек.** Не давать.
  - (б) Как сейчас.
- **Q3 Черты рассказчику.**
  - (а) **рек.** `combat_data.monster_traits` в бою.
  - (б) Только YAML.
- **Q4 Летающие.**
  - (а) **рек.** `fly_ft`; летающий не падает (+~15 тыс.).
  - (б) Нет.
- **Q5 Предсмертный взрыв.**
  - (а) Реализовать (+~40 тыс.).
  - (б) **рек.** Только описание.
- **Q6 `disarmer`.**
  - (а) **рек.** `wight` + `goblin_boss`.
  - (б) Только `wight`.
- **Q7 Подвал Вейла.**
  - (а) **рек.** `cellar` + `old_crypt`.
  - (б) Только описание.
- **Q8 WINDOW** при превышении.
  - (а) **рек.** +500 (7-й подъём, BACKLOG 45).
  - (б) Фильтр `monster_ids` по паку — отдельная партия.
- **Q9 Бюджет К7д в ROADMAP.** 0,35 → **0,85** — подтвердить.
- **Q10 Если в Open5e нет черт.**
  - (а) **рек.** Ручной перенос из PDF (+~40 тыс.).
  - (б) Перебрать список.
- **Q11 BACKLOG 52, импровизация.**
  - (а) **рек.** Проверка в `check_request` до броска; `prone` без проверки (BACKLOG).
  - (б) Проверка в `apply_push` после броска + `prone`.

**Ответы проектировщика (2026-10-14):**
- Список 27 монстров утверждён. Замены из запаса берутся только если монстра нет в srd-2024.
- **Q5 — (а): реализовать Предсмертный взрыв** (взрыв по зоне со спасброском у мефитов и магмина, +~40 тыс.). Шаг 2.8 меняется: механика по зоне в `monster_traits` (или отдельном модуле, если не уложится в сложность < 50), тесты и mutmut добавляются. Оценка ≈ 0,89 млн.
- Q8 — (а): если превысит, WINDOW +500.
- Q1, Q2, Q3, Q4, Q6, Q7, Q9, Q10, Q11 — (а), по рекомендациям. Q9 — бюджет 0,85 + Q5 ≈ 0,89 млн.

Расход papa-kaban ≈ 170 тыс.
