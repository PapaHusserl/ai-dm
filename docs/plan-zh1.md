# Ж1: выжившие боя

## Суть

ROADMAP «Ж1» (BACKLOG 20 — часть о выживших; 19 и 34 — см. «Решения»): выжившие в бою (перебежчики, сдавшиеся,
пощажённые, бежавшие) остаются в мире как NPC (`world.npcs`), со скрытым до знакомства именем (`known_name`) и памятью
о бое. Хвосты: 78 `start_combat`, 82 `commit`/`load` — при касании.

## Решения

- 2026-10-18, проектировщик (груминг свинопаса, вопросы П1–П10):
  - П1 (в): в `world.npcs` попадают все выжившие: перебежчик, сдавшийся, пощажённый и бежавший.
  - П2 (б): настоящее имя безымянному выжившему сразу придумывает рассказчик; игрок до знакомства видит вид существа.
  - П3 (б): имя открывает движок, когда настоящее имя прозвучало в тексте хода (`known_name` получает значение).
  - П4 (а): встреча в журнале Ж3 для NPC со скрытым именем засчитывается и пишется по `known_name` или виду существа;
    настоящее имя до знакомства в /lore и промпт не попадает.
  - П5 (а): память о бое пишет движок — событие `spared`, перебежчику ещё цель `life_debt`. Это явный пересмотр Q7 Ж0
    («события памяти пишет только рассказчик») для событий боя.
  - П6 (в): что перебежчик делает после боя, решает рассказчик.
  - П7 (б): BACKLOG 19 («ссорится», `spread_morale`) — не в Ж1, в Ж2 или позже.
  - П8 (б): BACKLOG 34 — вынести из Ж1 отдельным мелким шагом (состав шагов — архитектору).
  - П9 (а): хвост мутантов `start_combat` добивать, только если Ж1 трогает функцию.
  - П10 (б): допускается новая миграция m0012, если понадобятся поля (схема — архитектору: v12 была занята под М0).
- 2026-10-18, проектировщик (вопросы по аудиту груминга):
  - П11: бежавший уходит в соседнюю локацию; сдавшийся остаётся на месте боя (пленник); дальнейшую судьбу обоих
    двигает рассказчик.
  - П12 (б): начальное отношение к герою зависит от исхода: перебежчик — дружелюбен, сдавшийся — настороженно-нейтрален,
    бежавший — враждебен.
- 2026-10-18, проектировщик (вопросы по плану): пощажённый входит с отношением +20; бежавшему событие памяти `other`
  «бежал из боя» — оставить.
- 2026-10-18, проектировщик (вопросы кабана после коммита 1): пощажённый входит в мир как есть (0 HP, состояния не
  снимаются — очнётся по рассказчику); перебежчик пишется и в бестиарий (`creature`), не только MET.

## Груминг

- Свинопас (2026-10-18): вердикт до ответов — не готов. Расхождения: объём «выживших» (Ж0 п. 12 / Q5, TZ 4.1,
  ARCHITECTURE — только перебежчик; BACKLOG 20 — все) — снят П1; строка Ж1 в ROADMAP «журнал Ж3 уже пишет выживших,
  новых записей не заводить» неверна: `note_presence` (rules/knowledge.py) засчитывает встречу по настоящему `npc.name`
  и раскрыл бы скрытое имя — снят П4; `note_combat` пропускает участников, чей `ref` есть в `world.npcs`, — выжившего
  добавлять в мир после записи бестиария (порядок — в план); BACKLOG 34 не о выживших — П8; BACKLOG 20 стоит в Ж1 и Ж2
  без раздела — в Ж1 закрывается часть о выживших боя. В коде: `known_name` не читается; безымянный перебежчик после боя
  пропадает (В8 docs/plan-combat-parley.md ещё в коде); статусы `surrendered`/`fled` есть, в мир не переносятся.
  Риски: smells 200/200 (нулевой баланс), рост статики промпта.

## Аудит груминга

Кабан-свекровь (2026-10-18): решений за пользователя нет; пересмотры п. 12/Q5 и Q7 Ж0 отмечены явно. Устарело: строка
Ж1 ROADMAP (34, 19, фраза о журнале), BACKLOG 20 в Ж1 и Ж2 без раздела — архитектору; TZ 4.1, ARCHITECTURE (перебежчик,
Q7) — в план доков; хвост 82 — сначала перепрогон `commit`/`load` с `tests/unit/game` целиком. К пользователю — П11, П12
(решены). К плану: где хранить вид существа у NPC (`monster_id`, кандидат m0012); правило «имя прозвучало» без ложных
открытий (+ тесты); встреча скрытого NPC по виду засчитает любого гоблина, две записи `creature` и `npc` — что остаётся;
порядок «бестиарий, затем в мир»; видимость бежавших/сдавшихся рассказчику, рост статики и smells 200/200.

## План

Папа-кабан, 2026-10-18, версия 1. Схема v11 не меняется (вид — в `NPC.combat`, признак — `origin="engine"`).

### 0. Решения папы-кабана (в рамках П1–П12)

1. Выживший: `side="enemies"`, есть `monster_id`, `ref` не в `world.npcs`, исход `victory`/`fled`/`ended_by_master`,
   герой жив. Вид: `defected` (метку `parley_defected` читать до `finish_combat`), `surrendered`, `fled`, `spared`
   (`down`, а также `active` при `ended_by_master`). Активные враги при бегстве героя не материализуются.
2. Без m0012: `NPC.combat = {"monster_id", "label"}`, `origin="engine"`; `name_hidden(npc) = origin == "engine" and
   known_name is None`; NPC пака и ai — имя публично.
3. `rules/survivors.py` — материализация: id `<monster_id>_<n>` первый свободный; `name=label`, `named=False`,
   `means=[label]`, `creature`/`equipment` из участника, `groups=[group_id]`; локация — героя, бежавшему — первая соседняя
   (`relevance.nearby_locations`), нет соседей — остаётся; `follows` не ставится. Порядок в `end_fight`: `classify` →
   `settle_parley` → `finish_combat` → `note_combat` → `materialize` → `fold_fight`. Записи `creature` и `npc` — обе.
4. `[survivors]` в конфиге: defected 40, surrendered 0, spared 20, fled −40 (spared — решение проектировщика).
5. Память: `spared` для defected/surrendered/spared, бежавшему `other` «бежал из боя»; нет сцены — без памяти;
   перебежчику цель `life_debt`.
6. Журнал: MET по виду при материализации; `note_presence` скрытых по имени не ищет; при открытии — `rename_met`;
   `is_met`/`backfill` через `shown_name`.
7. Имя: `NpcUpdate.name` (только для `origin="engine"` и `not named`, иначе `name_locked`; занятое — `rejected`;
   `uniqueness.name_conflict`); в промпте `survivor_data`: `kind`, `unnamed` / `name_hidden`; правило в narrator_rules —
   имя в этом же ходу, до открытия звать по виду. «Сразу» = первый explore-ход после боя. Рассказчик имя видит.
8. Открытие: `reveal_names` в `commit` перед `note_presence` — по `narration`, NPC рядом или `follows`, эвристика
   `mentions` Ж3.
9. `shown_name` в `lore_text`, `battle_map`, `make_enemy`, `summarizer.state_data`, логах `handlers/world.py`
   (`npc_label`). `start_combat` не трогаем (78 остаётся).
10. smells 200/200 — мелкие функции, резерв `ui.screen:reply_blocks`.

### 0а. Дополнение папы-кабана после коммита 1 (2026-10-18)

1. id выжившего — `<monster_id>_t<turn_seq>_<n>`, занятость через `uniqueness.id_taken`; ref в бою не меняется.
2. Исходная группа перебежчика — в `params={"group": ...}` метки `parley_defected` (`apply_defect`), читает `classify`
   в поле `Survivor.group`; `make_npc` — `groups=[survivor.group]`.
3. `LIFE_DEBT_TEXT = "обязан герою жизнью: перешёл на его сторону в бою"` — текст цели `life_debt`.
4. Бестиарий перебежчика: `note_combat(..., defected=())`, `end_fight` передаёт refs перебежчиков.
mutmut — плюс `ai_dm.combat.actions.parley:apply_defect`.

### 1. Файлы

`rules/survivors.py` (новый), `config/settings.py`, `config/defaults.toml`, `game/turn.py`, `rules/knowledge.py`,
`rules/uniqueness.py`, `protocol/requests.py`, `protocol/handlers/world.py`, `protocol/handlers/combat.py`,
`master/prompt.py`, `master/summarizer.py`, `master/prompts/narrator_rules.md`, `tests/unit/master/test_static_budget.py`,
`game/lore_text.py`, `game/battle_map.py`. Доки: TZ 4.1.3, ARCHITECTURE (E11, стр. 774, A6/E1, переговоры), glossary.
BACKLOG 20 остаётся открытым (часть).

### 2. Партии

- Коммит 1 — движок (≈ 55 %): конфиг, `survivors.py`, `knowledge.py`, `turn.py`, `shown_name` в показе.
- Коммит 2 — протокол и промпт (≈ 30 %): `NpcUpdate.name`, `change_name`, `npc_label`, `survivor_data`, narrator_rules,
  `STATIC_MAX` по замеру.
- Коммит 3 — доки (≈ 15 %).

### 3. Тесты (kaban-doeba)

`tests/unit/rules/test_survivors.py` (classify, materialize, shown_name, reveal_names); `tests/unit/game` (`end_fight`
обоих путей, `commit`, `test_game_parley_after.py`, повторный бой с выжившим, battle_map без утечки);
`tests/unit/protocol` (`npc_update name`, `name_locked`, `rejected`, лог без имени, схема); `tests/unit/master`
(ключи в `scene_npcs`/`known_npcs`, правила, `STATIC_MAX`, summarizer); сценарий `tests/scenarios/test_zh1_survivors.py`.

### 4. mutmut

`ai_dm.game.turn:TurnRunner.end_fight`, `:TurnRunner.commit`, `ai_dm.rules.knowledge:note_presence`, `:is_met`,
`:backfill`, `:rename_met`, `ai_dm.rules.uniqueness:check_npc`, `:name_conflict`, `ai_dm.protocol.handlers.world:npc_update`,
`:update_problem`, `:change_name`, `:npc_label`, `ai_dm.protocol.handlers.combat:make_enemy`,
`ai_dm.master.prompt:PromptBuilder.state_data`, `ai_dm.master.summarizer:SummarizerPromptBuilder.state_data`,
`ai_dm.game.lore_text:entity_name`, `ai_dm.game.battle_map:part_name`, `:members`, `ai_dm.rules.survivors:*`.
Хвост 82: `commit` — с `tests/unit/game` целиком; `GameApp.load` — только перепрогон.

### 5. Риски

Утечка имени через логи (grep-тест); раннее произнесение имени (смотреть в ЖП3); бежавший невидим рассказчику до
именования; рост `scene_npcs`; `means`/`groups` влияют на Ж2.

### 6. Объём

L− ≈ 1,2–1,4: kaban 0,40, doeba 0,55, mama 0,15, svekrov 0,05, доки/тесть 0,08.

## Ревью и аудит

- Коммит 1, мама-кабан (2026-10-18): можно мержить; блокеров 0, важное 1, мелочей 3. Проверено: перебежчик по метке
  `parley_defected` с `params["group"]`; порядок `end_fight` по плану; `reveal_names` до `note_presence`, без ложных
  открытий; утечек имени в /lore, battle_map, `make_enemy`, summarizer нет; `reply_blocks` разбит без смены поведения.
  Замечания: (важно, процесс) кабан один раз правил импорты `sed -i` вместо Edit/Write; `landing` сам обходит соседей
  вместо `relevance.nearby_locations` (0.3); `make_npc` делит `creature`/`equipment` с участником — копировать;
  `game/shop_text.py` показывает `npc.name` без `shown_name`.
- Коммит 1, кабан-свекровь (2026-10-18): чисто; решений за пользователя нет; схема v11, m0012 нет; всё прослеживается к
  П1–П12 и §0/§0а. Мелочи: `landing` дублирует `nearby_locations`; `rules/npc_names.py` нет в §1 (вынесен из-за цикла
  импортов, оставить); `sed -i` — записать.

## Правки по ревью

- Коммит 1 (решение оркестратора — все мелочи мамы в работу, продуктовых решений нет): кабану отданы `landing` через
  `relevance.nearby_locations` (или причина, почему нельзя), копия `creature`/`equipment` в `make_npc`, `shown_name` в
  `game/shop_text.py`. Нарушение `sed -i` зафиксировано здесь; на результат не повлияло (ruff и тесты прогнаны).
  Итог правок кабана: `make_npc` копирует `creature`/`equipment` (`model_copy(deep=True)`); `shop_text` — `shown_name` в
  отказе и шапке кошелька. `landing` оставлен со своим обходом соседей: `rules` не может импортировать
  `master.relevance` (`tests/unit/test_architecture.py`) — отступление от 0.3 по слоям. smells 200. Тест `make_npc`
  (проверял тождество объектов) и тест `shop_text` — доебе.
  Повтор (2026-10-18): мама-кабан — можно мержить, новых замечаний нет; кабан-свекровь — чисто, отступление `landing`
  техническое, оставить.
  После `make dead` (решение оркестратора, без vulture_allowlist): vulture не видел полей `[survivors]`, читаемых через
  `getattr` — кабан ввёл `start_attitude(config, kind)` с явным словарём полей; `make dead` чист, smells 200.
  Качество коммита 1: 18429 passed, cov 97,74 %, smells 200/200, dead чист. mutmut по 32 функциям — 75 выживших:
  15 убиты тестами доебы (sonnet), 2 эквивалентны (`reply_blocks_4`, `make_npc_15`), 58 на старых строках — BACKLOG 84;
  повтор по `start_attitude`/`make_npc` — выжил только эквивалентный `make_npc_15`. Повтор 2: мама — можно мержить;
  свекровь — чисто, к коммиту завести BACKLOG 84 и не брать pyproject.toml (след `make mutate`, восстановлен);
  BACKLOG 83 (пользователя) — отдельным коммитом.
- Коммит 2 (2026-10-18). Ревью мамы: можно мержить после одной правки; важное — имя в `name_problem`/`change_name` не
  обрезалось и не проверялось на пустоту; мелочь — имя, совпадающее с видом, не откроется. Аудит свекрови: лишнего нет,
  отступления кабана 1–4 прослеживаются к §0 п.7; вопросы — бежавший вне промпта (риск §5) и трактовка П4.
  Решение оркестратора (важное мамы): кабан — `name_problem` обрезает имя, пустое → `Invalid(code="empty_name")`,
  занятость по обрезанному; `change_name` пишет `strip()`; тесты — доебе.
  Решения проектировщика: бежавший вне промпта — в BACKLOG 85; П4 трактуется так: рассказчик видит настоящее имя,
  скрыто оно только от игрока (показ, логи, /lore, журнал); имя, совпадающее с видом, — в BACKLOG 86.
  Повтор: мама — можно мержить; свекровь — чисто. Качество коммита 2: 18512 passed, cov 97,75 %, smells 200/200, dead
  чист. mutmut по 17 функциям — 144 выживших: на новых строках 8 — 6 убиты двумя тестами доебы (sonnet), в повторе
  выжили только тексты сообщений `name_problem` (21, 22, 33, 34 — шум); старые строки — BACKLOG 87.
