# Ж0 Поля и память NPC (BACKLOG 63, 20, 42, 19, 32, 33, 15, 77, 79; хвосты 46, 78)

R7 #3, M, сейв v10 → v11, смета 0,95 млн. Груминг — svinopas + kaban-svekrov по блоку Ж0–Ж3, 2026-10-17.
Статус: решения проектировщика собраны, план — papa-kaban.

## Суть
- Подшаг 0 — BACKLOG 77 первым: anthropic cpt 2.2, `context_cap` без кэшируемой статики, пересчёт WINDOW, пятая ступень
  вытеснения (15). Без полей сейва.
- Подшаг 1 — поля v11 одной миграцией: память и цели NPC, `known_name`, связи, задел под Ж1–Ж3, У0, Н5.

## Решения (проектировщик, 2026-10-17)
0. **Принцип v11 — (б):** поля под Ж1–Ж3, У0, Н5 закладываются в v11 сразу, чтобы не плодить миграций (v12 занята М0).
1. **`context_cap`** — кэшируемая статика в потолок не входит; запас под динамику не меньше 8k.
2. **Память NPC о герое** — список событий (вид из перечня, ход, короткий текст) + `attitude` + долгие цели (месть, долг
   жизни) отдельным полем.
3. **`known_name`** — в Ж0 (v11).
4. **Журнал знаний героя (21)** — пустая структура в v11, наполнение — Ж3.
5. **Жизненный цикл (42)** — только семейные связи (родитель/супруг/ребёнок) и имеющийся `birth_s`; детские события — нет.
6. **Группа боя (19)** — существующее `NPC.groups`, если боевая группа совпадает с группой мира.
7. **Услуги (32)** — только поле `NPC.services`; код — У0.
8. **Пятая ступень вытеснения (15)** — в Ж0 вместе с 77.
9. **Отношения (63)** — Ж0 сам пишет события через `npc_update` и показывает известных NPC рассказчику, не только поле.
10. **Музыка сцены (33)** — поле `SceneState.scene_mood` (не `mood`: есть `Tone.mood`) заводится в Ж0, логика — Ж3.
    Сцена главнее тона: тема `romance` играет на помеченной сцене и при `tone.romance` = «нет» (вариант б).
11. **Лимит памяти NPC (79)** — до 20 сцен на NPC в отношении героя, у каждой вес; новая сцена вытесняет сцену с
    наименьшим весом. Вес — по тому, насколько сцена изменила отношения (улучшила или ухудшила). Мок на 50 сцен проверяет
    лимит и вытеснение.
12. **Перебежчик (пересмотр В8)** — остаётся в `world.npcs`, а не исчезает.

### Решения по плану papa-kaban (2026-10-17)
- Q1 `context_cap` (потолок динамики) = 16 000.
- Q2 виды событий `memory_kind`: `spared, saved, helped, gift, promise, betrayal, insult, threat, theft, harm, kin_killed,
  romance, deal, other`.
- Q3 виды целей `NpcGoal.kind`: `revenge, life_debt, debt, gratitude, love, rivalry`.
- Q4 `relations_text` удалить в v11 (миграция `pop`).
- Q5 перебежчик в `world.npcs` — код в Ж1; в Ж0 только поля.
- Q6 `known_npcs` — только `goals` и последнее событие (`memory_last`); полная память — у `scene_npcs`.
- Q7 события памяти пишет только рассказчик; `WorldNpcUpdate` без полей памяти.

### Решения по подшагу 0 (проектировщик, 2026-10-17)
- `ContextPlan.cap` = потолок динамики `max(context_cap − static, 0)` (отклонение kaban от п. 3) — принято.
- Общий `chars_per_token` слоя настроек перекрывает `chars_per_token_by_provider` нижних слоёв (в т. ч. дефолт
  anthropic 2.2); перекрытие по провайдеру в том же слое — сильнее общего (`config/app.py:merge_layer`).

### Решения по подшагу 1 (проектировщик, 2026-10-17) — допущения kaban приняты
- `KNOWLEDGE_KINDS` = fact, rumor, secret, person, place; `KNOWLEDGE_SOURCES` = seen, told, read, deduced (константы,
  уточняются в Ж3).
- `NpcSceneMemory.weight` — изменение отношений сценой по модулю (улучшение и ухудшение равноценны).
- `WorldSim.pending_acts: list[str]` — содержимое определит 46.
- `NpcGoal.text` по умолчанию "".
- Пересмотр Q4: `relations_text` не удаляется без следа — новое поле `NPC.notes: str` (свободные заметки о NPC),
  миграция v11 и паки переносят текст туда целиком (в паке drunk_dragon и живых сейвах это роль/вид/связи NPC).
- Показ `notes` рассказчику (раньше `relations_text` в промпт не шёл) — в подшаге 2, вместе с показом памяти (п. 17).
- vulture_allowlist: задел v11 (13 имён) — блок с пометкой этапа, строку убрать, когда поле начнут читать; устаревшая
  строка `relations_text` удалена (согласие проектировщика 2026-10-17).

### Решения по подшагу 2 (проектировщик, 2026-10-18)
- Лимит событий памяти проверяется до изменения отношения (`memory_problem`): при `limit-exceeded` запрос не
  применяется целиком.
- `notes` показываются и у `known_npcs`, не только у `scene_npcs`.
- `memory_last`, `goals_data` (kaban сверх плана) — по Q6 и п. 17.
- `memory_text` длиннее 120 знаков (вариант б): обрезать по последнему пробелу до предела с «…» (итог ≤ 120),
  рассказчику — пометка в ответе «текст укорочен до 120», в decision.log — запись; запрос не отклоняется.
- По аудиту: обрезка — `clamped` с отдельной меткой `text-shortened` (при урезанном отношении остаётся
  `limit-exceeded`); рассказчику — только активные цели NPC; неиспользуемый параметр мока `turns_per_scene` удалён.

## План (papa-kaban, 2026-10-17)
Находка: `PromptBuilder.static_tokens` (master/prompt.py:217) считает схемы через `json.dumps` с `ensure_ascii=True` —
кириллица ×2. Реальная статика explore ≈ 17,7k при cpt 2,5 и ≈ 20,1k при 2,2 (не 28k/32k).

### Подшаг 0 — 77 + 15 + хвост 78 (без полей сейва; отдельный коммит)
1. `static_tokens` — `ensure_ascii=False`; `STATIC_MAX` = новый `explore.total` + 3 % (≈ 18 200), причина в шапке теста.
2. `app_defaults.toml`: `[master.chars_per_token_by_provider] anthropic = 2.2`.
3. `context.py`: `budget(app_cfg, model, static)` = `min(window80, static + context_cap)`; статика — оценка
   `ChatRequest(system=[rules, world_block], tools, messages=[])` через `request_tokens`; новый
   `PromptBuilder.static_estimate(ctx, tools, world_text, cpt)`, вызов из `build` до `plan`. `plan(..., static=0)`;
   `ContextPlan.budget`, `ContextPlan.cap = context_cap` (потолок динамики), новое `ContextPlan.static`, `meta()["static"]`.
   Тесты `test_game_commands.py:424–430`, `test_master_context_build.py:131` — под новую семантику. Сторож
   `context_cap ≥ 8000` — тестом.
4. Пятая ступень (15): `STAGES += "chapters"`; `Candidates.chapters` — главы с `number ≤ game_summary_chapter`, старшие
   первыми; `fixed_chapters` — остальные; `ContextPlan.chapters`; `memory_block` берёт план; `draft_plan` переносит.
5. `memory_script.py:WINDOW` — пересчитать, все пять ступеней срабатывают; причина в шапке.
6. Хвост 78: выжившие `world_block`, `build`, `take_boundary`, `mark_journal`, `mark_turn`; `start_combat` — Ж1.

### Подшаг 1 — поля v11 одной миграцией
7. Новый `state/relations.py`: `NPC_EVENT_TEXT_MAX = 120`; `NpcEvent(kind: str, turn_seq, text ≤ 120)`;
   `NpcSceneMemory(scene_id, at_s, weight ≥ 0, events min 1)`; `NpcGoal(kind: str, target, text, since_s,
   status: active|done|dropped)`; `FamilyLink(kind: parent|spouse|child, ref, ref_kind: npc|hero)`. Открытые перечни —
   `str` (иначе расширение = новая версия сейва из-за отпечатка схемы), закрытые — Literal; все `extra=forbid`.
8. `state/knowledge.py`: `KnowledgeEntry(kind, ref, text, source, from_ref, at_s)`, перечни — константы; наполнение Ж3.
9. `NPC`: `memory`, `goals`, `known_name: str | None`, `family`, `services: list[str]`; `relations_text` удалить.
   `WorldSim.pending_acts: list[str]` (46). 19 — комментарий у `NPC.groups`.
10. `HeroState`: `family`, `knowledge`. `SceneState.scene_mood: str = ""`.
11. `m0011_v10_to_v11.py` — чистая `dict -> dict`, deepcopy, setdefault (образец m0010), `pop("relations_text")`;
    `CURRENT_SCHEMA_VERSION = 11`; `tests/schema/save_v11.schema.json`; `scripts/migrate_dusk_18plus.py` — +11.
12. До правок кабана (doeba, на main): фикстура `tests/fixtures/saves/v10` и золотой ход `tests/golden/zh0_turn.json`
    (ScriptedAdapter, ход со `skill_check`); после Ж0 тот же ход на мигрированной фикстуре — тот же снимок.

### Подшаг 2 — память NPC (79) и запись/показ (63)
13. `[npc_memory] max_scenes = 20`, `max_events_per_scene = 5`; `NpcMemoryConfig` в `RulesConfig`.
14. `rules/npc_memory.py`: `remember` (запись сцены или событие в неё; лимит событий → None; полная память → `evict`),
    `evict` (наименьший `(weight, at_s)`; новая сцена входит всегда), `refresh_weight` (`weight =
    scene.attitude_spent[npc]`), `memory_data` (для промпта).
15. Протокол: `NpcUpdate.memory_kind` (Literal из Q2 + "none"), `memory_text`; `memory_text` без вида → Invalid;
    `remember` после `change_attitude`; лимит → rejected `limit-exceeded`; без сцены → Invalid `no_scene`;
    `refresh_weight` в `change_attitude`. Память — отдельной функцией `change_memory` (smells).
16. `combat_flow.settle_parley` → `refresh_weight`.
17. `state_data`: `scene_npcs` — `memory`, `goals` (если непусто); `known_npcs` — по Q6.
18. `narrator_rules.md`: «Формат входа» и «Память» — правило записи значимых поступков; `STATIC_MAX` поднять с причиной.
19. `MemoryMock(npc_memory=True)` + `tests/scenarios/test_zh0_npc_memory.py` на 50 сцен.

### Подшаг 3 — доки
20. ARCHITECTURE (E1, E4, новый E11 «Сейв v11»), TZ 4.1/11, BACKLOG-пометки, handoff; ROADMAP — архитектор.

### Тесты (doeba, TDD) — ключевое
- Статика: `tools` = оценка без экранирования; `total ≤ STATIC_MAX`; `cpt_for("anthropic") == 2.2`.
- `budget`/`plan` со статикой: граница `S + cap`, `meta()["static"]`, `raised`; сторож `STATIC_MAX + context_cap ≤
  window80` для моделей рассказчика.
- Пятая ступень: порядок стадий, неподвижные главы, `dropped` с `chapters`; `test_stage4_memory.py` — все пять ступеней.
- Миграция v11 по образцу v10; фикстура v10 → v11; золотой ход; отпечаток схемы; валидации новых моделей.
- `remember`/`evict`/`refresh_weight`/`memory_data`; `npc_update` с памятью; `settle_parley`; `state_data`;
  схема режима `world` без полей памяти.
- Мок 50 сцен: ровно 20 записей = 20 старших по `(weight, at_s)`, `overflow False`, детерминизм, сейв на сцене 30.

### mutmut
FUNCS: `ai_dm.master.context:plan ai_dm.master.context:budget ai_dm.master.context:_has_candidates
ai_dm.master.context:_item_id ai_dm.master.context:ContextPlan.meta ai_dm.master.prompt:PromptBuilder.build
ai_dm.master.prompt:PromptBuilder.static_tokens ai_dm.master.prompt:PromptBuilder.static_estimate
ai_dm.master.prompt:PromptBuilder.candidates ai_dm.master.prompt:PromptBuilder.memory_block
ai_dm.master.prompt:PromptBuilder.state_data ai_dm.master.prompt:PromptBuilder.world_block ai_dm.master.prompt:draft_plan
ai_dm.protocol.handlers.world:npc_update ai_dm.protocol.handlers.world:update_problem
ai_dm.protocol.handlers.world:change_attitude ai_dm.game.combat_flow:settle_parley ai_dm.rules.npc_memory:remember
ai_dm.rules.npc_memory:evict ai_dm.rules.npc_memory:refresh_weight ai_dm.rules.npc_memory:memory_data
ai_dm.persistence.migrations.m0011_v10_to_v11:migrate_v10_to_v11 ai_dm.game.turn:TurnRunner.take_boundary
ai_dm.game.turn:TurnRunner.mark_journal ai_dm.llm.journal:Journal.mark_turn`.
TESTS — по подшагам: tests/unit/{master,protocol,rules,persistence,config,state,llm} и затронутые tests/unit/game/*.

### Риски
1. Тесты с `provider="anthropic"` — оценки +14 % при 2,2 (`test_master_session_log.py:299`).
2. Смысл `meta.context.cap` меняется — grep `["cap"]` в `reports/`.
3. `NpcSceneMemory.events min_length=1` — ручные конструкторы в тестах.
4. Память в `scene_npcs` ≈ 1–1,5k ток. на NPC при 20 сценах.
5. Smells 200/200 — `npc_update` уже длинный.
6. Фикстуру v10 и золотой ход снимать строго до правок кабана.
7. `WINDOW` мока пересматривается дважды (п. 5 и п. 18).

Смета ≈ 0,95 млн: подшаг 0 — 0,25, 1 — 0,30, 2 — 0,30, доки/ревью/mutmut — 0,10. Три коммита (0, 1, 2+3).

## Правки по ревью — подшаг 0
- Сделано: explore.total 28022 → 17666, `STATIC_MAX` 18200, `context_cap` 16000, anthropic 2.2, `WINDOW` мока 25400
  (рабочая полоса ≈ 25340–25490). Фикстура v10 и золотой ход сняты doeba на чистом main до кода kaban.
- mama-kaban (блокеров нет): общий `PromptBuilder.static_system` для запроса и оценки статики (effort в оценку не
  добавлен — расходится с `request_tokens`); `candidates` — единообразно `memory`; рендер-тест `draft_plan` с обеими
  группами глав есть. Выжившие мутанты (mark_turn 6/10/37/38/54, take_boundary 32, world_block 7–9, static_tokens
  11–13/20, draft_plan 23–29) — эквивалентные/шумовые, приняты.
- Находки: модели с окном < ≈ 25k после шага непригодны (одна статика > 8000, динамика вытесняется целиком);
  схема `context_cap` — `gt=0`, сторож ≥ 8000 только на дефолте (вопрос папе-кабану); в подшаге 2 мок памяти — большое
  окно + фиксированный `context_cap` вместо подбора `WINDOW`.
- kaban-svekrov: лишнего нет; процессные нарушения — `sed -i` у kaban (6 строк, проверено ревью), тесты сверх плана
  (вынужденно), mutmut запускал doeba, а не оркестратор.
- Расход: doeba (фикстура) 66k, kaban 94k, doeba (тесты+mutmut) 149k, mama-kaban 40k, svekrov 32k.

## Правки по ревью — подшаг 1
- Сделано: `relations.py`, `knowledge.py`, поля v11 (NPC, HeroState, SceneState, WorldSim), `NPC.notes` с переносом
  `relations_text` (миграция, пак drunk_dragon — 31 NPC, `import_dragon.py`, фикстура vale_stage2), m0011,
  `save_v11.schema.json`, dusk-скрипт +11; 129 новых тестов.
- mama-kaban: `make dead` падал на 14 заделах v11 → allowlist по решению проектировщика; пробел в
  `import_dragon.py:259` — исправлен оркестратором; m0011 при непустых и `notes`, и `relations_text` теряет старый текст
  (в v10 `notes` нет — принято); ссылки `relations_text` в `devtools/dragon_drafts.yaml` — пути источника, оставлены.
- mutmut m0011: 107, убито 106; выжил `setdefault("known_name", )` — эквивалентный.
- kaban-svekrov: партия чистая; MEMORY_KINDS/GOAL_KINDS — из Q2/Q3; согласие на allowlist и раздел «Решения по
  подшагу 1» подтверждены проектировщиком.
- Расход: kaban 49k + 64k, doeba 79k + 86k, mama-kaban 30k, svekrov 29k.

## Правки по ревью — подшаг 2
- Сделано: `[npc_memory]`/`NpcMemoryConfig`, `rules/npc_memory.py`, поля памяти `NpcUpdate`, `change_memory`/
  `memory_problem`, `refresh_weight` в `change_attitude` и `settle_parley`, `npc_memory_data` в `state_data` (память,
  цели, `notes`), правило записи в `narrator_rules.md`, `STATIC_MAX` 18700, мок 50 сцен; из allowlist — `MEMORY_KINDS`,
  `goals` (`GOAL_KINDS` остаётся: цели пока никто не пишет).
- mama-kaban: (а) `memory_text` без вида → `memory_text_without_kind` — исправлено оркестратором; (б) лимит событий
  проверялся после `change_attitude` — перенесён в `memory_problem` (решение 2026-10-18); WINDOW мока 26000 принят,
  перевод на большое окно — BACKLOG 81; `memory_last`/`goals_data` приняты.
- kaban-svekrov: лишнего нет; три мелочи вынесены проектировщику и приняты (метка `text-shortened`, только активные
  цели, удалён параметр мока `turns_per_scene`).
- mutmut (17 функций): 708, убито 572, выжило 136; на новых строках 2 — закрыты тестами, `memory_problem` 9/10/18–20 —
  тексты сообщений; старые строки — BACKLOG 80.
- Проверки: 17701 passed, cov 97,67 %, smells 200/200, dead чист; ruff — 18 старых E501, новых нет.
- Расход: kaban 90k + 27k + 25k, doeba 142k + 35k + 40k + 30k + 37k (sonnet), mama-kaban 32k, svekrov 36k;
  архитектор (R9) 85k + 108k + 120k.

## Находки груминга
- В R7 (docs/plan-roadmap-r7.md:136) состав Ж0 шире ROADMAP: бестиарий, поля напарника и У2 — по 0б решает архитектор.
- `NPC.relations_text` (state/world.py:94) объявлен, но нигде не пишется.
- BACKLOG 33 говорил «v10» — исправлено на v11.
- Риск бюджета: статика ≈ 28k при cap 30k; тест «тот же ход по сиду» дополнить проверкой `STATIC_MAX`.
