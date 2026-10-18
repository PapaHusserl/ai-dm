# Ж3: база знаний игрока

## Суть

ROADMAP «Ж3» (BACKLOG 21, 41, 33 хвост Му-р): у героя появляется журнал знаний `HeroState.knowledge` (записи
`KnowledgeEntry`, бестиарий — одна из записей), команда `/lore` и окно-справочник в TUI. Логика `scene_mood`: запрос
мастера и уровень «сцена» в `pick_theme`. Флак 41. Схема сейва остаётся v11.

## Решения

- 2026-10-18, проектировщик (груминг свинопаса, вопросы П1–П10):
  - П1: `kind` означает, о ком запись: npc/location/faction/god/creature/situation. «Слух», «видел», «рассказал X» —
    это `source`. Бестиарий — `creature`.
  - П2: журнал пополняют двое: движок по событиям и рассказчик запросом протокола.
  - П3: ответ строится только по журналу. Выжимки сцен и глав и хроника world_sim не используются.
  - П4: ответ — шаблон из журнала, без LLM.
  - П5: только команда; свободную фразу «что я знаю о…» не распознаём.
  - П6: в уже идущих мирах журнал при загрузке достраивается кодом из встреченных NPC, `known_to_player`
    и посещённых локаций.
  - П7: в TUI отдельное окно-справочник (тогда флак 41 остаётся в Ж3 как первой партии, трогающей TUI).
  - П8: не больше 5 записей на сущность.
  - П9: перечень `scene_mood` — только `romance`; метка снимается с концом сцены.
  - П10: команда — `/lore`, без русского имени.
  - Вне Ж3 (уточнено после аудита, первая запись была неточной): забывание по TZ 440 относится к посмертию
    (блок С, потеря нитей), `known_name` — к Ж1.
  - Спойлеры: если рассказчик пытается записать нераскрытый секрет (не из `known_to_player`), обработчик отклоняет запись.
  - Окно-справочник: открывается по `/lore` и по клавише; слева сущности по видам, справа записи выбранной;
    закрывается по Esc.
  - По какому признаку NPC считается «встреченным» при достройке журнала, решает папа-кабан по имеющимся данным;
    если понадобится новый флаг в сейве — вопрос к архитектору.
  - Текст пункта 33 в BACKLOG не правим: решение 10 Ж0 записано в docs/plan-zh0.md и в ROADMAP.
  - Ключ `ref` для situation/faction/god выбирает папа-кабан в плане.
- 2026-10-18, проектировщик (вопросы по плану папы-кабана):
  - Окно открывается только командой `/lore`, отдельной клавиши нет (уточняет решение «по `/lore` и по клавише»).
  - Журнал знаний показывается рассказчику в промпте.
  - Мастер может досрочно снять метку внутри сцены: `scene_mood` принимает `romance` или `none`.
  - При достройке старого мира NPC считается встреченным, если его имя есть в выжимках сцен и глав; текст выжимок
    в журнал не попадает.
- 2026-10-18, проектировщик (по плану, версия 2): бестиарий виден рассказчику только в бою; записи движка
  о встречах и посещениях в промпт не идут, в `/lore` идут; `[master] knowledge_max = 30`.

## Груминг

- Свинопас (2026-10-18): до ответов на П1–П6 шаг к плану не был готов; теперь ответы получены. Расхождения
  в документах: BACKLOG 33 устарел («игнорировать romance при tone.romance = нет»; по решению 10 Ж0 сцена главнее
  тона); в R8 указан «Му-р на dusk_academy», в ROADMAP — «свой мир», верен ROADMAP. Риски: smells 200/200
  (правило нулевого баланса); статика промпта растёт, поэтому `STATIC_MAX` придётся поднять с указанием причины.

## План

Папа-кабан, 2026-10-18, версия 2 (после ответов проектировщика, см. «Решения»): клавиши F5 нет — окно только по
`/lore`; журнал показывается рассказчику (п. 0.7, шаг 8а); `scene_mood none` — да; выжимки как признак встречи — да.

**Задача:** оживить поля v11 `HeroState.knowledge` и `SceneState.scene_mood`: журнал знаний героя (пишут движок по
событиям и рассказчик запросом `knowledge_note`), команда `/lore` (текст в простом режиме, окно-справочник в TUI,
открывается только командой), журнал в промпте рассказчика, уровень «сцена» в `pick_theme` по запросу `scene_mood`
(только `romance`), флак 41. Схема сейва v11 не меняется (все нужные данные есть — `known_to_player`, `memory`,
`follows`, `attitude`, `visited`, `recent_turns`, `memory.scenes/chapters`; нового поля не нужно).

Аналоги в коде: память NPC Ж0 (`rules/npc_memory.py` + `change_memory`/`memory_problem` в `handlers/world.py`), `/shop` +
`game/shop_text.py` (команда = тонкая обёртка над текстовым модулем), `SpellModal` (список слева, описание справа),
`SoundState`/`pick_theme` (Му), `apply_events`/`location_visited`.

### 0. Решения папы-кабана (в рамках ТЗ; продуктовых решений нет)

1. **Перечни** (П1): `KNOWLEDGE_KINDS = ("npc", "location", "faction", "god", "creature", "situation")`,
   `KNOWLEDGE_SOURCES = ("seen", "told", "rumor", "read", "deduced")` (`seen` видел сам; `told` рассказал NPC —
   `from_ref`; `rumor` слух; `read` прочитал; `deduced` понял сам / узнал по ходу дела). Старые fact/rumor/secret/
   person/place никто не писал — замена без миграции (поле `str`).
2. **Ключ `ref`:** `npc` → `NPC.id`, `location` → `Location.id`, `faction` → `Faction.id`, `god` → `God.id` (ключи
   словарей `WorldState.npcs/locations/factions/pantheon`); `creature` → id монстра реестра; `situation` → свободный
   слаг латиницей от рассказчика (`^[a-z0-9_]{2,40}$`), дубли — по точному `ref`. Одна проверка существования на вид,
   `allowed(...)` подсказывает id при ошибке; по `ref` считаются дубли и лимит П8.
3. **«Встреченный» NPC** (П6, достройка при загрузке; нового флага не нужно): живой или мёртвый NPC встречен, если
   выполнено любое из: `known_to_player` непуст; `memory` непуст; `follows == hero.id`; `attitude != 0`; NPC `named` и его
   имя (без регистра) встречается в тексте `recent_turns` или в выжимках `memory.scenes`/`memory.chapters`/`game_summary`.
   Выжимки — только признак факта встречи (запись «seen», текст из выжимок не берётся), П3 не нарушается. Признак «в
   локации героя» сам по себе встречей не считается. Текущая запись по ходу игры (движок, П2): в `TurnRunner.commit` —
   живой NPC в локации героя или идущий с ним, чьё имя есть в `narration`/`player_input` этого хода → первая запись
   `seen` (один раз на NPC).
4. **Лимит и дубли** (П8): `[knowledge] max_per_ref = 5` (`KnowledgeConfig` в `RulesConfig`); при превышении уходит
   самая старая по `(at_s, порядок)` запись этой сущности (FIFO). Дубль = та же `(kind, ref)` и тот же нормализованный
   текст → для рассказчика `rejected` («уже записано», без `report_tag`), для движка — тихий пропуск. Запись `seen`
   движка для npc/location — одна на сущность.
5. **Спойлеры:** рассказчик секреты не пишет — их пишет движок при принятом `reveal_secret` (`source="deduced"`, текст
   секрета). Страховка в обработчике `knowledge_note`: если текст заметки покрывает нераскрытый секрет любого NPC (доля
   значимых слов секрета длиной ≥ 4, найденных в тексте, ≥ 0,6) → `rejected` «секрет ещё не раскрыт»,
   `report_tag="spoiler"`.
6. **Что пишет движок (П2):** первая встреча NPC и первое посещение локации (из `hero.location_id` на коммите); бестиарий
   — в `end_fight` по безымянным врагам (`ref` не в `world.npcs`, есть `monster_id`): `creature`/`monster_id`/`seen`, текст
   «Бой: <имя монстра> — победа|бегство|поражение|прерван»; бог — при принятом `favor_change` героя: `god`/`god_id`/
   `deduced`, текст «<бог>: <approx_label> (<reason>)»; секрет — при принятом `reveal_secret`.
7. **Журнал рассказчику показывается** (решение проектировщика) — блок `knowledge` в `state_data` (вход каждого хода).
   Отбор по сцене и потолок:
   - **что входит** (по `ref`): `npc` — NPC сцены и `known_npcs`; `location` — локация героя и соседние из
     `context_plan.location_ids`; `god` — боги из `hero.favor`; `faction` и `situation` — все; `creature` — только в
     режимах боя (`combat_classify`/`combat_narrate`) по `monster_id` участников;
   - **что не входит**: записи движка о встрече/посещении (`seen` с префиксами `MET`/`VISITED`); записи бестиария/бога/
     секрета и все записи рассказчика — идут;
   - **потолок**: `[master] knowledge_max = 30` записей (новейшие по `at_s`, при равенстве — порядок журнала), 0 — блок
     выключен; текст записи ≤ 160 знаков → худший случай ≈ 2,1k токенов, типичный ≈ 0,4–0,8k; блока нет, если отбор пуст;
   - **формат**: `"knowledge": {"npc": {"aldric": ["Хранит ключ от склепа (told: mira)"]}, "location": {...}, ...}` — вид →
     ref → строки «текст (источник[: id рассказавшего])»;
   - **кэш**: журнал в `state_data` (не в `system[2]`): проще и детерминированно, бюджет держит потолок; если ЖП3 покажет
     заметный рост входа — перенос в память как отдельный хвост.
   Текст заметки ≤ `KNOWLEDGE_TEXT_MAX = 160`, длиннее — обрезка по последнему пробелу с «…», `clamped`, метка
   `text-shortened`.
8. **`scene_mood`** (П9): запрос с `mood: Literal["romance", "none"]`; `none` — снять раньше конца сцены; с концом сцены
   метка снимается сама (у новой `SceneState` `scene_mood = ""`). Запрос только в режиме explore. Приоритет темы: бой >
   сцена > локация (id, теги) > тон; вариант `romance_sensual` при `tone.romance = откровенно` — существующей
   `romance_variants`.
9. **`/lore`** (П4, П5, П10): без аргумента — перечень сущностей по видам с числом записей; с аргументом — поиск по
   имени/`ref` (подстрока без регистра), записи «— текст (источник, дата)». В TUI любая форма открывает `LoreModal`
   (аргумент — предвыбор); клавиши нет; Esc закрывает. Команда вне хода, время мира не тратит, в бою доступна.
10. **Смеллы:** новые модули маленькие; `cmd_lore` — три строки, тело в `game/lore_text.py`. Резерв на нулевой баланс (если
    `make smells` покажет 201): разбить `ui.screen:reply_blocks` на `turn_line_blocks` + `gains_block`; второй резерв —
    `game.app:GameApp.handle` (6 return → 5, вынос диспетчера команд в `command_reply`).

### 1. Затронутые модули/файлы

- `state/knowledge.py` — перечни, `KNOWLEDGE_TEXT_MAX`; модель не меняется.
- `rules/knowledge.py` — **новый**: чистые функции над `HeroState`/`WorldState`.
- `config/settings.py`, `config/defaults.toml` — `KnowledgeConfig`/`[knowledge]`.
- `protocol/requests.py` — `KnowledgeNote`, `SceneMood`, `REQUEST_MODELS`, `MasterRequest`.
- `protocol/handlers/knowledge.py` — **новый**: `knowledge_note`, `scene_mood`; `protocol/schema.py` —
  `MODE_TOOLS["explore"]` (+2, не strict).
- `protocol/handlers/world.py` — `reveal_secret` (запись секрета), `favor_change` (запись бога), `shorten_memory_text` →
  `shorten_text(text, limit)`.
- `game/turn.py` — `TurnRunner.commit` (встреча NPC, посещение локации), `TurnRunner.end_fight` (бестиарий);
  `game/app.py` — `GameApp.__init__` и `GameApp.load` (достройка журнала).
- `master/prompts/narrator_rules.md` — раздел «Журнал знаний и настроение сцены»; `master/prompt.py` —
  `PromptBuilder.state_data` (+ блок `knowledge`), `PromptBuilder.knowledge_refs`; `config/app.py` / `app_defaults.toml` —
  `MasterConfig.knowledge_max`; `tests/unit/master/test_static_budget.py` — `STATIC_MAX`.
- `audio/select.py` — `SoundState.scene_mood`, `pick_theme`; `ui/screen.py` — `sound_state`.
- `game/commands.py` — `HELP["lore"]`, `cmd_lore`, `COMMANDS`; `game/lore_text.py` — **новый**.
- `ui/tui/modals.py` — `LoreModal`; `ui/tui/app.py` — `finish_turn`, `MODALS`; `ui/tui/strings.py`; `ui/tui/app.tcss`.
- `vulture_allowlist.py` — снять строки `knowledge`, `KNOWLEDGE_KINDS`, `KNOWLEDGE_SOURCES`, `from_ref`, `scene_mood`.
- Доки: `docs/ARCHITECTURE.md` (E12, F8, F5), `docs/TZ.md` (4.1.3, 10), `docs/glossary.md`, `README.md`, `docs/done/`
  (021, 041, 033), `docs/plan-zh3.md`. ROADMAP — архитектор.

### 2. План реализации (три коммита)

**Коммит 1 — движок, протокол, музыка (kaban).**

1. `state/knowledge.py` — перечни по п. 0.1, `KNOWLEDGE_TEXT_MAX = 160`.
2. `config/settings.py` — `KnowledgeConfig(max_per_ref: int = Field(5, gt=0))`, поле `RulesConfig.knowledge`;
   `defaults.toml` — `[knowledge] max_per_ref = 5`.
3. `rules/knowledge.py` (новый), только чистые функции: `has_entry`, `normalize`, `remember_fact`, `entries_for`,
   `evict_oldest`, `shorten_text`, `note_presence`, `note_combat`, `note_favor`, `note_secret`, `met_npc_ids`,
   `backfill` (идемпотентна; `at_s` = `started_at_s` текущей сцены), `spoils`. Тексты движка — константы-префиксы
   (`MET`, `VISITED`, `FOUGHT`).
4. `protocol/requests.py` — `KnowledgeNote` (`kind`, `ref`, `text`, `source`, `from_ref`) и `SceneMood`; оба в
   `REQUEST_MODELS` и `MasterRequest`; `schema.py` — в `MODE_TOOLS["explore"]` (не strict).
5. `protocol/handlers/knowledge.py` (новый): проверки `empty_text`, `unknown_ref` (+`allowed`), `bad_ref`, `unknown_npc`,
   `told_without_from`, спойлер → `rejected`; обрезка (`clamped`, `text-shortened`); дубль → `rejected` «уже записано»;
   `scene_mood`: нет сцены → `Invalid no_scene`.
6. `handlers/world.py` — `reveal_secret` → `note_secret`; `favor_change` (герой) → `note_favor`; `change_memory` →
   `shorten_text(text, NPC_EVENT_TEXT_MAX)`.
7. `game/turn.py` — `commit` → `note_presence`; `end_fight` → `note_combat` (сигнатуру `finish_combat` не менять);
   `game/app.py` — `backfill` в `__init__` и `load`.
8. `narrator_rules.md` — раздел «Журнал знаний и настроение сцены» (≈ 1 300 знаков).
8а. Показ журнала рассказчику (п. 0.7): `MasterConfig.knowledge_max = 30`; `rules/knowledge.py:prompt_entries`;
    `PromptBuilder.knowledge_refs`; `state_data` — одна строка `data.update(...)`. Роль `world` и summarizer журнал не
    получают.
9. `test_static_budget.py` — замер `make prompt-budget`, поднять `STATIC_MAX = total + 3 %`, причина в шапке.
10. `audio/select.py` — `SoundState.scene_mood` (последним, с умолчанием); `pick_theme`: после боя тема `scene_mood`, если
    она есть в `index.themes`; `ui/screen.py:sound_state` — `scene_mood` из `current_scene`.
11. `vulture_allowlist.py` — снять 5 строк задела Ж3. `make smells` после каждого файла.

**Коммит 2 — `/lore`, TUI, флак 41.**

12. `game/lore_text.py` (новый): `KIND_TITLES`, `SOURCE_WORDS`, `entity_name`, `lore_groups`, `find_entity`, `date_of`,
    `entry_lines`, `lore_lines`. В `/lore` идут все записи, включая `MET`/`VISITED`.
13. `game/commands.py` — `HELP["lore"]`, `cmd_lore`, `COMMANDS["lore"]` (после `shop`).
14. TUI: `strings.py`, `modals.py` (`LoreModal`: `OptionList #lore-list` с заголовками видов `disabled`, справа
    `VerticalScroll #lore-body`), `app.py` (`MODALS`, ветка в `finish_turn`), `app.tcss`; клавиши и `action_lore` не
    заводить. `README.md` — `/lore`.
15. Флак 41 (kaban-doeba, `tests/unit/ui/tui/test_tui_turn.py`): гонка в самом тесте — `release.set()` в `finally`
    сценария срабатывает до `hard_exit`. Правка: убрать из сценария, страховку — в `try/finally` вокруг
    `asyncio.run(...)`. Проверка: 20 прогонов подряд и под нагрузкой.

**Коммит 3 — доки (kaban).**

16. ARCHITECTURE E12, F8, E1; TZ 4.1.3 и 10; glossary; README; карточки `docs/done/` 021, 041, 033; `docs/plan-zh3.md`.

### 3. Тестовые сценарии (kaban-doeba, TDD)

- `rules/knowledge`: `remember_fact` (дубль, лимит, FIFO, `max_per_ref = 1`, разные `kind` с одним `ref`);
  `note_presence` (имя в тексте, второй ход без новой записи, спутник, мёртвый, локация); `note_combat`; `note_favor`/
  `note_secret`; `backfill` (признаки встречи, идемпотентность, `at_s`, новый мир → 0); `spoils`; `shorten_text`.
- `protocol`: `knowledge_note` (accepted, `told` с `from_ref`, все Invalid, `clamped`, дубль, спойлер, режимы);
  `reveal_secret` и `favor_change` пишут журнал; `scene_mood`; схема (`REQUEST_MODELS`/`ALL_TYPES`/`VISIBLE_TYPES`,
  `tool_set`, `NEUTRAL`).
- `audio`/`ui.screen`: `pick_theme` со `scene_mood` (бой, откровенная романтика, тема не из индекса); `sound_state`.
- `game`/`commands`: `lore_lines`, `cmd_lore`, `ALL_COMMANDS`, `test_commands_both_modes`, `backfill` в `__init__`/`load`,
  запись в `commit`/`end_fight`, золотой ход Ж0 остаётся зелёным.
- `TUI`: `/lore` → `LoreModal`, `/lore Гарт` — предвыбор, Esc, цифры не выбирают ход, пустой журнал, `BINDINGS` без новой
  клавиши; флак 41 — 20 прогонов.
- `master`: `test_narrator_knowledge_rules`, `test_prompt_knowledge` (все случаи отбора и потолка), `knowledge_max` в
  `MasterConfig`, `KnowledgeConfig`.
- Мок-сценарий `tests/scenarios/test_zh3_knowledge.py` (ScriptedAdapter): `knowledge_note told`, попытка записать секрет,
  `reveal_secret`, `scene_mood`, `/lore`, сейв/загрузка, `backfill` на `tests/fixtures/saves/v10`.

### 4. mutmut (kaban-doeba)

Существующие: `ai_dm.audio.select:pick_theme`, `ai_dm.ui.screen:sound_state`, `ai_dm.protocol.handlers.world:reveal_secret`,
`:favor_change`, `:change_memory`, `ai_dm.game.turn:TurnRunner.end_fight`, `:TurnRunner.commit`, `ai_dm.game.app:GameApp.load`.
Новые: `ai_dm.rules.knowledge:*` (remember_fact, has_entry, entries_for, evict_oldest, note_presence, note_combat,
note_favor, note_secret, backfill, met_npc_ids, spoils, shorten_text, prompt_entries), `ai_dm.protocol.handlers.knowledge:*`,
`ai_dm.game.lore_text:*`, `ai_dm.game.commands:cmd_lore`, `ai_dm.master.prompt:PromptBuilder.knowledge_refs`. TUI
(`LoreModal`) — без mutmut.

### 5. Риски

- `STATIC_MAX` растёт (+2 схемы и раздел правил ≈ +900–1 100 токенов); порог — только после замера `make prompt-budget`.
- Динамика растёт на блок `knowledge` (≤ ≈ 2,1k, типично 0,4–0,8k на ход); при переполнении `context_cap` первыми уходят
  старые `turns`. Рычаг — `knowledge_max`. Замер входа в ЖП3: ход с блоком vs без.
- Мок памяти (`tests/scenarios/test_stage4_memory`): ступени вытеснения могут сдвинуться; константы подбирает doeba один
  раз, код не правит.
- Смеллы 200/200: `cmd_lore` — 3 строки; `note_problem` ≤ 5 `return`; резерв — п. 0.10.
- Бестиарий — в `end_fight`, не в `finish_combat` (сигнатуру зовут 9 тестов); запись идёт в обоих путях `fold`.
- `test_ui_sound_state.py` строит `session` без `current_scene` — обновить кит.
- Достройка при загрузке меняет бандл до первого хода; журнал в промпт `--replay-report` не расходится (детерминизм:
  `at_s` из сцены, обход `world.npcs` по `sorted(id)`).
- Ложные встречи по имени («Мор», «Лес») — приемлемо (та же эвристика `said`).
- Спойлер-страховка словесная: ловит близкий пересказ, не перефраз; метка `spoiler` покажет частоту в ЖП3.
- Флак 41 может иметь второй слой; если падает под нагрузкой — правка `AiDmApp.turn`/`run_async` у kaban.
- Правила промпта меняют fingerprint — старые `--replay-report` расходятся (как в ТХ).
- vulture: после снятия строк `make dead` должен быть чист.

### 6. Оценка объёма

L− ≈ 1,35 млн: kaban ≈ 0,42, doeba ≈ 0,58, mama ≈ 0,15, svekrov ≈ 0,05, доки/тесть ≈ 0,10; по фактору ×1,4 ≈ 1,6–1,8.
Ревью — по коммитам 1 и 2 (третий — доки, аудит свекрови).

### 7. Открытые вопросы

Закрыты, см. Решения.

## Правки по ревью

Ревью мамы-кабана, круг 1 (2026-10-18). Все пункты отданы кабану по решению оркестратора, в рамках плана, без
продуктовых решений:
1. Вытеснение по кругу: запись движка `MET`/`VISITED` вытесняется заметкой и снова пишется на следующем ходу,
   вытесняя заметку. Нарушает п. 0.4: одна запись движка на сущность.
2. `has_entry` проверяет `source="seen"`: заметка рассказчика с `seen` блокирует запись о знакомстве. Проверять
   по префиксу.
3. `note_secret`/`note_favor` не обрезают текст до `KNOWLEDGE_TEXT_MAX`, из-за этого не держится оценка бюджета
   промпта.
4. Две `hidden_secrets` с разным смыслом: переименовать версию в `handlers/knowledge.py`.
5. Имя NPC ищется подстрокой: проверять по границам слов.
6. `/lore <имя>` без совпадения в TUI открывает первую сущность: в чек-лист ЖП3, кода не меняем.

Исправлено кабаном (решения в рамках пунктов ревью): п. 1 — `evict_oldest` выбирает жертву среди записей
не-движка (`is_engine`: `seen` + префикс `MET`/`VISITED`), если других нет — любую; п. 2 — `has_entry(..., prefix)`;
п. 3 — обрезка через `shorten_text`; п. 4 — `unrevealed_texts`; п. 5 — `mentions`: имя с начала слова, окончания
допускаются (русские падежи), имена из ≤ 3 знаков — целым словом. Тесты на правки — kaban-doeba
(`tests/unit/rules/test_knowledge.py`).

Мутанты (kaban-doeba на sonnet): из 152 выживших 44 убиты тестами, 3 эквивалентны (`significant_6`,
`prompt_entries_23`, `prompt_entries_25`), 105 — на старых строках (`favor_change`, `reveal_secret`,
`TurnRunner.commit`, `GameApp.load`): идут в BACKLOG 82.

Ревью, круг 2: принято; мелочь — `SHORT_NAME` перенесена под свой комментарий (кабан). Аудит свекрови: по содержанию
чисто; доделать карточки done/ и пункт BACKLOG (сделано оркестратором). П. 6 подтвердил проектировщик 2026-10-18:
оставить, проверить в ЖП3.

## Итог

- Закрыты BACKLOG 21, 41, 33 (хвост Му-р): карточки в docs/done/. Новый пункт — BACKLOG 82 (старые мутанты).
- Тесты: 18259 passed, 1 xfailed; cov 97,71 %; smells 200/200; `make dead` чист; ruff — 18 старых E501.
  `STATIC_MAX` 18700 → 20050 (explore.total 19462).
- В чек-лист ЖП3: `/lore <имя>` без совпадения в TUI; спойлер-страховка (метка `spoiler`); ложные встречи по имени;
  рост входа от блока `knowledge` (`meta.context.estimate`).
- Расход (subagent_tokens, сводно): свинопас 71k; свекровь (груминг) 31k; папа-кабан 321k; кабан 255k;
  кабан-доеба 259k; доеба-мутанты (sonnet) 105k; мама-кабан 50k; свекровь (аудит) 40k — итого ≈ 1,13 млн без
  оркестратора. Модели ролей — по описаниям агентов, кроме доебы-мутантов (sonnet). Кабан-тесть не вызывался
  (бюджет не ориентир, NOTES.md 2026-10-18).
