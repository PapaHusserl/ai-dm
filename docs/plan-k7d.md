# План партии К7д: монстры SRD 5.2 с ПО 0–5, черты, разгрузка smells, BACKLOG 52, сцена сетки с бюджетом (papa-kaban, 2026-10-14)

Вписано оркестратором (у papa-kaban нет Write). Груминг и решения — docs/plan-k7d.md.

**Задача.** R4 #11 / R5 #14 по решениям `docs/plan-k7d.md` («Решения проектировщика» и «Источник SRD 5.2», 2026-10-14):
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
- итог — `docs/plan-k7d.md`.

### 8. Docs и атрибуция
- `srd/data/ATTRIBUTION.md` + ссылка из README.
- `rules-adaptation.md`.
- BACKLOG: 28/44/52/125 и новые пункты — В2, повторные спасброски/Recharge, рисунки elemental/construct, размер цели у `prone`, фильтр `monster_ids` по паку.
- ROADMAP:25, ROADMAP-PLAN, ARCHITECTURE, HANDOFF.
- Чек-лист `checklist-k7d-live.md` (не коммитить). 10 пунктов: крипта, Стойкость, уязвимости скелета, стая, паралич упыря, сбивание волком, `disarmer` у Гракха, `/difficulty hard`, отказ `push` по огромному, крысы без монет.

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

## Решения: Груминг партии К7д — монстры SRD и разгрузка smells (свинопас, 2026-10-14, HEAD 187d319) (бывш. docs/decisions/k7d-grooming.md)

Вписано оркестратором (у свинопаса нет Write). Расход svinopas ~46 тыс. (субагентный счётчик).

### Источники
- ROADMAP:7, :25 (#13–16, «д», v9, общий бюджет 1,85 млн).
- roadmap-r4-unified:62 (#11 — объём и приёмка), :64 (Ж0 зависит от К7д), :76 (Ж4: таблица ПО 0–5 расширяется данными).
- roadmap-r5-proposal:162 (К7д 0,35 млн «без изменений»).
- ROADMAP-PLAN:37 (К-1: скрипт из SRD 5.2 CC-BY, атрибуция в srd/data и README), :176–177, :203, :331, :334.
- BACKLOG:28, :125 (данные иммунитетов — К7д), :497 (статблоки зверей для спутника), :525 (`nonmagical_only` — К7д+), :537–538 (п. 52).
- K7X-PLAN:117, :124 (Q1в, тег `shover`), :132–145 («Отклонения» 1–10).
- k7x-grooming:173–176 (природная броня по формуле В9(в), тег `disarmer`, пересчёт базовой линии сетки).
- k7x-review:20; k7x-audit:30, :36, :39, :51–56; k7x-cost:47–55, :59.
- k7k-review:27, :33, :41; K7K-PLAN:348; k7k-sim-grid:23–24; HANDOFF:228–229.

### Объём К7д
0. Первый шаг — разгрузка smells на −4–6. Правило нулевого баланса действует на всю партию.
1. 20–30 монстров SRD 5.2 с ПО 0–5. Генерирует скрипт из SRD 5.2 CC-BY (К-1), атрибуция в srd/data и README.
2. Сверить `individual_treasure` и клад с новыми ПО (R4:62).
3. Данные иммунитетов, сопротивлений и уязвимостей: нежить, элементали, конструкты.
4. Природная броня в `ac` по формуле В9(в).
5. Тег `disarmer` на подходящих монстрах.
6. Пересчитать базовую линию сетки и добавить сцену с бюджетом, чтобы `--difficulty` начал действовать.
7. BACKLOG 52: толчок проверяет размер цели.
8. Приёмка — живой прогон, общий на К7: бой в подвале Вейла или в «Пьяном драконе», сложность, иммунитеты. Отложен вместе с чек-листами k1, k7k и k7x.

### Smells
- Лимит в Makefile:4 (`SMELLS_MAX ?= 206`, ratchet). Подсчёт — Makefile:21–23 (`qlty smells --all`). Исключения — `.qlty/qlty.toml:16`. Сейчас 206.
- 23 из 206 приходятся на тесты и devtools: `import_dragon` 4, `sim_combat` 3, `world_run` 1, `game_kit` 4, `combat_kit` 3, `ui_kit` 3, `summarizer_kit` 2, `world_kit` 1, `memory_script` 1, `fake_miniaudio` 1.
- Кандидаты в коде продукта:
  - `combat/available.py:429` `list_options` (сложность 23) и `:136` `spell_entries` (19);
  - `combat/controllers.py:39` `choose_turn` (7 return);
  - `rules/derived.py:141` `armor_class_parts` (сложность 32). Его тронет природная броня;
  - `short_rest:41` (7 параметров) — модуль уточнить;
  - `after_damage` (~:72, три запаха) и `resolve_out_of_combat:112` — файл уточнить;
  - `combat/engine.py:111` `__init__` и `:363` `improvise`.
- Риски:
  - п. 7 добавляет ветки в `shove.perform` / `available.shove_options`;
  - скрипт импорта в devtools добавит запахи.

### Расхождения с кодом
1. `individual_treasure` уже есть: `srd/data/tables/individual_treasure.yaml`, `rules/loot.py:38–42`, `protocol/requests.py:368`. Осталось покрыть таблицей новые ПО.
2. Монстров три (`goblin_boss`, `goblin_warrior`, `guard`). Нужные поля в `Monster` есть. Поля природной брони нет — по В9(в) это вычисление.
3. Черты монстров — ссылки на id features (`content/loader.py:159`). В движке есть только `nimble_escape` (`available.py:426`). `redirect_attack` не используется. Черты из SRD (Тактика стаи, Стойкость нежити, яды, дыхание, заклинания) без кода в игре не видны. Это скрытый объём (В3).
4. BACKLOG 52 — две точки входа: `combat/shove.py` (`may_shove`/`perform`) + `available.py:351` `shove_options`, и `combat/actions/improvise.py:98` `apply_push`. Готовые помощники — `SIZES`/`target_size` в `combat/actions/attack.py:377–384`, уже используются в `disarm.py:72`.
5. `--difficulty` сетки (`devtools/sim_grid.py:46`) на `goblins3` не влияет.
6. Иммунитеты, `disarmer` и природную броню в игре не увидеть, пока новых монстров не подключат к столкновениям.

### Готовность
Не готова: блокируют В1, В3, В4.

### Вопросы
- **В1 (блок.)** Разгрузка smells. (а) −6 рефакторингом продукта: `list_options`, `choose_turn`, `armor_class_parts`, `after_damage`; (б) −4 в продукте; (в) разгрузить тесты и devtools. Рекомендация — (а).
- **В2.** Исключить tests/ и devtools/ из smells и снизить лимит на 23? (а) нет; (б) да. Рекомендация — (а), потому что вариант (б) меняет метрику.
- **В3 (блок.)** Черты новых монстров. (а) брать только монстров без черт или с реализованными чертами; (б) любых, черты — описанием для рассказчика; (в) реализовать 3–5 частых, размер вырастет до S+. Рекомендация — (а)+(б).
- **В4 (блок.)** Список 20–30. (а) papa выбирает по критериям (ПО 0–5, нежить, элементаль, конструкт, звери из BACKLOG:497); (б) список даёт проектировщик. Рекомендация — (а), список утверждается на ревью плана.
- **В5.** BACKLOG 52. (а) обе точки, включая `apply_push` героя; (б) только монстр. Рекомендация — (а).
- **В6.** Новые монстры в игре. (а) реестр и сцена сетки с бюджетом; (б) плюс столкновения «Пьяного дракона» и подвала Вейла для живого прогона. Рекомендация — (б).
- **В7.** Базовая линия сетки. (а) пересчитать в К7д; (б) отложить до К2/К3. Рекомендация — (а), если в В6 есть сцена с бюджетом.
- **В8.** `shover` и `nonmagical_only`. (а) оба не в К7д; (б) `nonmagical_only` хранить в данных уже сейчас. Рекомендация — (а).
- **В9.** Скрипт импорта SRD. (а) одноразовый в devtools/, коммитятся только YAML; (б) скрипт тоже коммитится и попадает под smells. Рекомендация — (а).

### Оценка
R5:162 — 0,35. k7x-cost:55 — 0,65–0,75 с удешевлениями. При В3(в) или В6(б) — ближе к 0,75.

### Аудит (kaban-svekrov, 2026-10-14, ~20 тыс.)
Объём не раздут: п. 0–8 прослеживаются до источников. Ссылки на код верны. Решений за проектировщика нет.
- **Критично:** не указан источник SRD 5.2 для скрипта. В репозитории нет ни PDF, ни JSON, а `import_dragon` работает с другим источником. Нужен новый вопрос В10.
- Модули уточнены:
  - `short_rest` — `rules/rests.py:41`;
  - `after_damage` — `rules/death_saves.py:72`; одноимённая функция есть в `combat/downed.py:37`;
  - `resolve_out_of_combat` — `rules/death_saves.py:112`.
- В1 не блокирует: решение «−4–6 + нулевой баланс» уже принято, выбор функций — работа papa. Остаётся уточнить, засчитывается ли разгрузка tests/devtools.
- В2 не следует из источников — перенести в BACKLOG.
- В6: вариант (б) следует из приёмки R4:62. Вопрос только в том, какие столкновения добавить.
- Новые вопросы:
  - **В10 (блок.):** источник SRD 5.2 и формат (парсинг PDF / сторонний JSON / ручная выжимка). Если парсинг PDF — оценка 0,8–0,9;
  - **В11:** бюджет К7д в ROADMAP:25 — 0,35 → 0,65–0,75.

Итоговые блоки: В3, В4, В10.

### Решения проектировщика (2026-10-14)
- В10 — сторонний JSON под SRD 5.2 (CC-BY). Источник ищет dyadya-kaban до плана.
- В3 — (в): реализовать 3–5 частых черт (Тактика стаи, Стойкость нежити, яд со спасброском и т. п.). Размер — S+.
- В4 — (а): список монстров выбирает papa по критериям; проектировщик утверждает его на ревью плана.
- В6 — новые монстры подключаются к столкновениям только подвала Вейла.
- В1 — smells снимаются только в коде продукта; выбор функций — papa.
- В2 — исключение tests/devtools из smells переносится в BACKLOG.
- В5 — (а): размер цели проверяется в обеих точках толчка.
- В7 — (а): базовая линия сетки пересчитывается в К7д на сцене с бюджетом.
- В8 — (а): ни `shover`, ни `nonmagical_only` в К7д не входят.
- В9 — (а): скрипт одноразовый, в репозиторий коммитятся только YAML.
- В11 — бюджет К7д в ROADMAP пересчитать с учётом черт; papa даёт оценку в плане.

### Источник SRD 5.2 (dyadya-kaban, 2026-10-14, ~15 тыс.)
- Источник — Open5e API v2, документ `srd-2024` («System Reference Document 5.2», лицензия `cc-by-40`, проверено curl). Адрес: https://api.open5e.com/v2/creatures/?document__key=srd-2024. Всего 331 существо, нужные поля есть.
- Фильтр по ПО на стороне API не работает — фильтровать у себя.
- В атаках встречается `damage_type: null` при заполненном `extra_damage_type` (goblin warrior) — конвертер должен это учитывать.
- Где лежат черты (traits), не проверено. Это должен проверить papa.
- Выборочно сверить с официальным PDF SRD 5.2 5–10 монстров, особенно типы урона.
- Атрибуция CC-BY-4.0 — текстом из самого SRD 5.2.

## Правки по ревью: Ревью партии К7д (mama-kaban, 2026-10-14) (бывш. docs/decisions/k7d-review.md)

Вписано оркестратором. Расход mama-kaban ~79 тыс.

### Проверено
- Шаги плана 0–8 выполнены; Q5(а) — Предсмертный взрыв сделан механикой.
- smells 200/200, `SMELLS_MAX = 200`.
- Базовая линия сетки: добавлен только блок `cellar`, `goblins3` не изменилась. Отпечаток сейва и golden не тронуты.
- Скрипт импорта в репозиторий не попал (`~/projects/ai-dm-k7d-import/`).
- Порядок урона и событий: удар → `mark_damage` → `special_damage` → `extra_damage` → `on_hit` → `log_notes` → `after_damage`. Поэтому Стойкость нежити видит весь урон.
- Стойкость нежити соответствует SRD.
- Эффект при попадании отказывает до броска, RNG не тратится.
- Сверка с PDF SRD 5.2.1:
  - ghoul, specter, gargoyle — совпадают;
  - попутно steam_mephit, black_bear, ghast — тоже совпадают.

### Обязательные правки — внесены
1. `hawk`, `homunculus` → `size: tiny`: Open5e отдаёт для них `small`. Тест добавлен.
2. `test_multiattack` / `test_shove_tactics` — переведены на босса без тега (`plain_boss`). Добавлен тест: `disarmer` выбирает disarm раньше мультиатаки.

### Желательные правки — внесены
3. Срок эффекта при попадании учитывает `provoked`, как Досада в `mastery.py`.
4. Хвост « Движок:» отрезается от описания черты до того, как оно уходит рассказчику.
5. `has_trait` возвращает `bool`.
6. Калибровка `cellar`: 0 % побед у плута, жреца и волшебника на 3–5 ур. Решение проектировщика — оставить и вернуться после живого прогона К7 (docs/plan-k7d.md).

Также добавлен комментарий в `ghast.yaml`: Коготь стоит первым намеренно.

### Отклонения кабана — приняты
1. `HitRider.exempt` — по SRD («isn't an Undead or elf»).
2. Сроки `source_turn` / `target_turn` / `minute` — с правкой 3.
3. Фиксированный урон 1 записан как `1d1`, на крите удваивается до 2 — записано в rules-adaptation.
4. Коготь вурдалака стоит первым. Упырь Когтем не бьёт — BACKLOG 58.
5. Взрыв действует на «ту же зону», один бросок урона на всех.
6. Лог «парит».
7. Нереализованные черты переданы только текстом.
8. `narrator_rules.md` не тронут — решение проектировщика: объяснять ключ не нужно.
9. `mark_damage` переведён на `merge_damage`; добавлены `content/monster_checks.py` и `downed.death_cause`.

### Тесты (kaban-doeba)
- 16056 passed, 1 xfailed. cov 97,51 %. smells 200/200. dead чисто, `sim-grid --check` = 0.
- Снимок `sheet_reference_vale` поправлен (`old_crypt`). Полного прогона после этой правки не было.
- Сиды сценариев сдвинуты из-за нового реестра:
  - `test_stage2_live_like` 7 → 1;
  - `test_stage2_done` `HONEST_SEED` 156 → 108.
- mutmut: 294 → 66 выживших. Разобраны:
  - эквивалентные: `endures` m37, `hit_while_down` m6, `pierce_parts` m2;
  - шум текста ошибок `monster_checks`, `source=` у `PackTacticsSource`;
  - `feat_ac_parts` — в SRD нет черт с эффектом на КД, кроме `defense`.
- Не покрыто:
  - отдельный замер пика WINDOW (сценарии зелёные при 25000);
  - `armor`/`shield` по Gear — ни у одного из 27 монстров нет снаряжения;
  - числа SRD сверены у 8 + 6 монстров, у остальных 13 — только разбор и согласованность.

### Расход
| Роль | Расход |
|---|---|
| svinopas | ~46 тыс. |
| svekrov | ~21 тыс. |
| dyadya | ~17 тыс. |
| papa | ~175 тыс. |
| kaban | ~296 + 4 тыс. |
| doeba | ~375 тыс. |
| mama | ~79 тыс. |

Всего ≈ **1,01 млн** при оценке 0,89 (перебор ~13 %).

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **К7д код ✅ 2026-10-14 (kaban; тесты doeba, ревью mama-kaban, mutmut и `make cov` впереди, не закоммичено):** по docs/plan-k7d.md + ответы проектировщика (Q5а — взрыв механикой). Шаг 0: разгрузка smells 206 → 200 (`death_saves.fatal/hit_while_down`, `derived.base_armor_parts/feat_ac_parts/effect_ac_parts/pierce_parts`, `available.standard_actions/bonus_actions/circle_options`, `controllers.approach`), `SMELLS_MAX = 200`. 27 монстров ПО 0–5 (`srd/data/monsters`, 21 новая feature) — импорт Open5e `srd-2024` + иммунитеты из PDF SRD 5.2.1 (в Open5e они неполны у 7 монстров), скрипт вне репозитория (`~/projects/ai-dm-k7d-import/`). Код: `combat/monster_traits.py` (Тактика стаи, Стойкость нежити, доп. урон, `on_hit`), `combat/death_burst.py`, `DamageResult.damage_types`, `Monster.fly_ft/death_burst`, `MonsterAction.extra_damage_*/on_hit`, `content/monster_checks.py`, `falling.hovers`, `loot.NO_COIN_TYPES`, `shove.size_ok` + `improvise.size_problem` (BACKLOG 52 ✅), `prompt.monster_trait_notes` → `combat.monster_traits`, `devtools/sim_cellar.py` (сцена `cellar`, пересчёт базовой линии), подвал Вейла: `old_crypt`, `disarmer` у `goblin_boss`/`wight`. Сейв v9 без изменений. Отклонения и открытые вопросы — в отчёте kaban (чат) и docs/plan-k7d.md. BACKLOG 53–58. Чек-лист — checklist-k7d-live.md (не коммитить).
- **К7д ✅ закоммичена 2026-10-14:** тесты 16056 passed, cov 97,51 %, smells 200/200 (−6, нулевой баланс соблюдён), dead чисто, sim-grid --check 0. Ревью docs/plan-k7d.md (все обязательные и желательные правки внесены, отклонения 1–9 приняты; калибровка `cellar` — после живого прогона К7; narrator_rules не трогаем). Шаг 0 отдельным коммитом не вышел — один коммит партии. Расход ≈ 1,01 млн при оценке 0,89. Живой прогон отложен (чек-листы r1-f1-r2, k1, k7k, k7x, k7d). **Дальше:** BACKLOG 59 — пустая сцена на запасной модели рассказчика (dusk_academy, ход 396): (2) повтор хода при коротком финальном тексте после инструментов, (3) разбор `refusal_fallback`/thinking в anthropic_adapter — мини-партия; затем аудит К7д (kaban-svekrov) и разбор полётов (kaban-test).

## Приложение: К7д: сцена сетки `cellar` и пересчёт базовой линии (kaban, 2026-10-14) (бывш. docs/decisions/k7d-sim-grid.md)

Сцена `cellar` (`devtools/sim_cellar.py`): подвал Вейла, три зоны (лестница → бочки с укрытием → крипта), герой на лестнице,
враги по зонам крипты и бочек, `intent = kill`. Состав — жадный набор `fill_budget(budget, CELLAR_POOL, registry, cap=6)`:
бюджет = `party_budget([уровень героя], registry, tier_of(world, cfg))`, пул (от дорогих к дешёвым) —
`wight, ghast, ghoul, shadow, skeleton, zombie, giant_rat`; каждого вида ставится сколько влезает в остаток.
`--difficulty` пишет `world.settings["difficulty"]` до набора, поэтому меняет состав; `goblins3` по-прежнему не зависит от сложности.

### Состав по уровню героя и сложности

| Ур. | easy (low) | normal (moderate) | hard (high) |
|---|---|---|---|
| 1 | скелет | скелет, гигантская крыса | тень |
| 2 | тень | тень, скелет | упырь |
| 3 | тень, скелет | упырь, гигантская крыса | упырь ×2 |
| 4 | упырь, скелет | упырь, тень, скелет, гигантская крыса | вурдалак, скелет |
| 5 | вурдалак, скелет | умертвие, скелет | умертвие, упырь ×2 |

### Базовая линия (воин/плут/жрец/волшебник/следопыт, сиды `range(200)`, `normal`)

| Класс | 1 ур. | 2 ур. | 3 ур. | 4 ур. | 5 ур. |
|---|---|---|---|---|---|
| воин | 67,5 % | 88,5 % | 69,0 % | 34,0 % | 40,5 % |
| плут | 9,0 % | 7,5 % | 5,0 % | 0,0 % | 0,0 % |
| жрец | 6,0 % | 4,5 % | 0,0 % | 0,0 % | 0,0 % |
| волшебник | 9,0 % | 1,5 % | 7,0 % | 0,0 % | 0,0 % |
| следопыт | 18,5 % | 17,5 % | 8,0 % | 0,0 % | 2,0 % |

Воин по сложностям (побед из 200): easy 92 / 100 / 97,5 / 79,5 / 97 %; normal 67,5 / 88,5 / 69 / 34 / 40,5 %;
hard 93,5 / 69 / 30,5 / 88,5 / 0,5 %.

- `goblins3` в `devtools/sim_grid_baseline.yaml` совпала с прежней (дифф файла — только добавленный блок `cellar`).
- Кривая не монотонна по уровню и сложности: набор жадный и дискретный, а ПО монстров идут ступенями (одна тень на 100 ПО
  против скелета и крысы на 75); при смене состава поведение скачет — это свойство таблицы бюджета, не баг сцены.
- Плут, жрец, волшебник и следопыт слабы по тем же причинам, что в К7к: `auto_hero` не умеет Скрытую атаку и лечение
  (BACKLOG 50); пересчёт — после К2/К3.
- Время прогона всей сетки (2 сцены × 25 клеток × 200 боёв): около 3 минут.

### Решение проектировщика (2026-10-14)

В `cellar` плут, жрец и волшебник на 3–5 ур. дают 0 % побед, следопыт — 0–2 % на 4–5 ур. Бага нет: так выходит из бюджета
боя и паралича (когти упыря и вурдалака). Оставить как есть; калибровка — по итогам живого прогона К7. `narrator_rules.md`
не трогать.
