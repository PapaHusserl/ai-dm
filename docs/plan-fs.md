# Шаг ФС — Фикс сцены: контекст и NPC

BACKLOG 134, 214, 145; при касании 135, 137. Строка ФС в docs/ROADMAP.md; решения 2026-10-28 — NOTES.md.

## Решения

Решения проектировщика на груминге 2026-10-29. Груминг вёл свинопас, аудит груминга — кабан-свекровь.

1. 214, перенос NPC: рассказчик получает `location_id` в своём `npc_update` (`NpcUpdate`) с той же проверкой,
   что у мира (`world.py:68`). Это расширение протокола рассказчика (вариант а).
2. 145: у `gone` не нужны ни причина, ни бросок-доказательство; оба обязательны только у `dead` (вариант а).
3. 145: правило одно и для хода рассказчика (`world.py:505`), и для событий за кадром (`offscreen.py:140`),
   через общий `death_refused`.
4. Конспект выпавших ходов текущей сцены собирает движок из состояния: кто здесь, имена, что найдено.
   ИИ-вызова нет, summarizer не трогаем, поэтому 163/126 в шаг не входят.
5. Формат конспекта: строгие строки с потолком знаков. Пересчитывается каждый ход, поля в сейве нет.
6. Сигнал 214 приходит подсказкой на следующий ход через state_data, как `nudge`. Если рассказчик
   сигнал проигнорировал, создаётся авто-репорт с новым `report_tag`.
7. Детектор 214 ловит падежи имени. Для `master/relevance.py` и детектора 214 — одна функция, поэтому
   137 входит в шаг.
8. `context_cap = 32000` — умолчание для всех игроков (`app_defaults.toml`). Конспект делаем в ФС,
   хотя на t1379 при 32000 ходы не выпадали.
9. Аппрув плана 2026-10-29: развилки Р1–Р4 — рекомендации папы: Р1 (2) — все ходы сцены вне `context_plan.turns`;
   Р2 (1) — один матчер `rules/knowledge.py:mentions`; Р3 (1) — все outcomes; Р4 (1) — спутник вне локации получает
   сигнал.
10. Умолчания У2–У7 приняты как в плане (окно 2026-10-29).

Груминг: /private/tmp/claude-501/-Users-vladislavahtamov-projects-ai-dm/92726265-d425-4604-96fe-dc1d8049e8e3/scratchpad/svinopas-fs.md,
аудит: …/scratchpad/svekrov-fs-gruming.md (scratchpad сессии, не в репо).

## План (папа-кабан, 2026-10-29)

Контур: вне msa; режим: встроить. Входы: решения 1–8 выше, NOTES.md 2026-10-28, груминг свинопаса и аудит свекрови.
«Уже сделано» и «Расхождения с ТЗ» в груминге: адреса `app_defaults.toml:176` и `world.py:509` подтверждены по коду
(в ROADMAP устарели — `:174`, `requests.py:518`); у рассказчика `location_id` в `npc_update` действительно нет
(`requests.py:595`, только `WorldNpcUpdate` `:786`). Размер — M, три партии по файлам: П1 контекст (134, 135) →
П2 конспект (решения 4–5) → П3 NPC (214, 145, 137). Замеры на HEAD 03893fa: `make smells` = 200 (ровно потолок —
нулевой баланс), статика explore 23906 при `STATIC_MAX` 23940 (`make prompt-budget`, запас 34 токена).

**Задача:** рассказчик перестаёт терять сцену (`context_cap` 32000 + конспект выпавших ходов) и NPC (сигнал об
отсутствующем NPC с инструментом переноса; уход `gone` без причины и броска; падежи имён в поиске упоминаний).

### Правила, которые меняются (первым пунктом аппрува)

1. 134 — `src/ai_dm/config/app_defaults.toml:176`: было `context_cap = 16000` → станет `context_cap = 32000`.
   Формула сторожа `master/context.py:64` `min(window_budget, static + context_cap)` не меняется; сторож тестов
   `STATIC_MAX + context_cap ≤ window80` (`test_static_budget.py:162-163`) при 23940 + 32000 = 55940 проходит для всех
   окон `[context_windows]` (минимум haiku 200000 → 160000).
2. 135 — `master/context.py:11`: было `STAGES = ("turns", "scenes", "npcs", "locations", "chapters")` → станет
   `("turns", "scenes", "npcs", "chapters")`; поле `Candidates.locations` (`:21`) убирается, `ContextPlan.location_ids`
   = `fixed_locations` (`:123`). У рассказчика ступень мертва: `prompt.py:364` всегда `locations=[]`.
3. Конспект (решения 4–5) — новое: в `state_data` ключ `scene_recap` (только когда есть выпавшие ходы текущей
   сцены), собирается движком из `memory.recent_turns` и состояния; поля сейва нет; ИИ-вызова нет.
4. 145 — `protocol/handlers/world.py:331 death_refused`: было `cause not in MASTER_DEATH_CAUSES or evidence is None →
   True; иначе evidence_ref in used_rolls` → станет: первой строкой `if request.status == "gone": return False`
   (уход — без причины и броска), для `dead` — как было. За кадром (`offscreen.py:140`): было `status is not None and
   (not own_roll or death_refused(...))` → станет `status is not None and death_refused(ctx, npc, request,
   own_roll=own_roll)` — проверка «бросок этого же NPC» переезжает внутрь `death_refused` параметром и действует
   только для `dead` (решение 3: одно правило, общий `death_refused`).
   Текст отказа `world.py:509` и `offscreen.py:142`: «у смерти должна быть причина…» — без слова «уход».
   Движок (`rules/mortality_guard.py:56 remove_creature`) по-прежнему требует причину в `DeathRecord`: для `gone` без
   причины обработчик передаёт новую причину `left` (умолчание У6).
5. 137 + 214 (решение 7) — `master/relevance.py:39`: было `npc.name.lower() in text` → станет
   `mentions(npc.name.lower(), text)` — общий матчер с падежами (Р2: какой именно). Тот же матчер — у детектора 214.
6. 214 (решения 1, 6) — новое: `NpcUpdate` рассказчика получает `location_id` с проверкой `world.py:68`
   (`unknown_location`); в `state_data` ключ `absent_npcs` — NPC, названные в рассказе прошлого хода этой сцены, но не в
   локации героя; если в этом ходу рассказчик снова назвал такого NPC и не перенёс — тег авто-репорта
   `npc_absent_ignored`.

**Поведение:** меняется — (а) при 32000 ходы рассказчика не выпадают (t1379: dropped []); (б) рассказчик видит
`scene_recap`, когда ходы сцены не вошли в `recent_turns`; (в) `npc_update status=gone` без причины и броска
принимается, NPC уходит из `scene_npcs` (и за кадром тоже); (г) упоминание NPC в косвенном падеже делает его
«said»-релевантным; (д) рассказчик получает `absent_npcs` и может перенести NPC `npc_update.location_id`; (е) новый
авто-репорт `npc_absent_ignored`. Остальное (порядок вытеснения ходов/сцен/NPC/глав, `dead`, `follows`) — как сейчас.
**Вне ai-dm:** `~/.config/ai-dm/config.toml:7` `[master] context_cap = 32000` — снять при закрытии шага (ROADMAP,
NOTES 2026-10-28) — Влад. Сейвы не мигрируются: новых полей нет, `DeathRecord.cause` расширяется (старые сейвы читаются).

### Модули, файлы, функции

П1 — контекст (134, 135):
- `src/ai_dm/config/app_defaults.toml:176` — `context_cap = 32000`.
- `src/ai_dm/master/context.py` — `STAGES` (:11), `Candidates` (:14, убрать `locations` :21), `plan` (:97,
  `location_ids` :123); `_has_candidates`/`_item_id` (:83/:89) без правок.
- `src/ai_dm/master/prompt.py` — `PromptBuilder.candidates` (:341, убрать `locations=[]` :364).
- Тесты: `tests/unit/config/test_app.py:163` (16000 → 32000; `:906` ≥ 8000 остаётся);
  `tests/unit/master/test_master_context.py` (:4 комментарий, `make_render` :192, `cands` :203-209, `trimmed` :232-236,
  `STAGES` :242, `location_ids` :256/:304); `tests/unit/master/test_master_context_build.py:275-277` (цикл по ступеням),
  `:408-410` (`dropped locations == []` — тавтология после 135, удалить).
- Документы: `docs/ARCHITECTURE.md:639, :689, :692` (16000 → 32000, ступень `locations` убрана), `docs/TZ.md:738`.
- `grep -rn '"16000"\|16000' tests/`: кроме `test_app.py:163` — только `max_tokens` рассказчика
  (`test_master_prompt.py:687-692`, `test_t60_config.py:115`), не трогать.

П2 — конспект (решения 4–5, Р1, Р3):
- `src/ai_dm/master/recap.py` — новый модуль (чтобы не растить `prompt.py`, 636 строк):
  - `dropped_turns(memory, scene, kept_seqs)` — новая: ходы `recent_turns` с `scene_id == scene.id`, чьих `turn_seq`
    нет в `kept_seqs` (при Р1 = (1) — только `turn_seq` из `ContextPlan.dropped`; fallback `summarizer.scene_turns`
    для сейвов до v5 не повторяем — у открытой сцены старого сейва ходов без `scene_id` быть не должно).
  - `scene_recap(bundle, kept_seqs, *, max_chars)` — новая: `None`, если сцены нет или выпавших ходов нет; иначе
    `{"turns": "t<first>–t<last> (<n> ходов)", "npcs": [имена именованных живых NPC, упомянутых в `narration`
    выпавших ходов — `rules.knowledge.mentions`], "events": ["t<seq>: <строка outcomes>", …]}`; строки принятых
    запросов (без `<type>: отклонено (…)`), старые первыми, каждая ≤ `RECAP_LINE_MAX`, всего ≤ `RECAP_MAX`; при
    переполнении отбрасываются старые.
- `src/ai_dm/master/prompt.py` — `PromptBuilder.state_data` (:531): после `known_locations` (:630-631) —
  `recap = scene_recap(ctx.bundle, {t.turn_seq for t in context_plan.turns}, max_chars=RECAP_MAX)`;
  `if recap: data["scene_recap"] = recap`. В `render` (:290) план черновой (`draft_plan` :250, `dropped=[]`), поэтому
  «выпавшие» считаются от `context_plan.turns`, а не от `dropped` — работает и внутри цикла `plan`.
- `src/ai_dm/master/prompts/narrator_rules.md:46` — одна фраза после `recent_turns`: «`scene_recap` — конспект ходов
  этой сцены, которых уже нет в `recent_turns`: `turns` — какие, `npcs` — кто в них упоминался, `events` — что движок
  исполнил; это прошлое, как `recent_turns`: не пересказывай, вызовы не повторяй».
- `tests/unit/master/test_static_budget.py` — `STATIC_MAX` 23940: запас 34 токена, фраза правил его съест —
  поднять по правилу файла (замер + запас, строка причины «ФС П2»). Ожидание, не проверено.
- Тесты: новый `tests/unit/master/test_recap.py` (функции), `test_master_context_build.py` (ключ при малом cap, нет
  ключа без выпавших, монотонность оценки — см. риск), `test_master_prompt.py:755-758` `STATE_TOP_KEYS` не меняется
  (ключ только при непустом конспекте).
- Документы: `docs/ARCHITECTURE.md` E4 (:684) — абзац о `scene_recap`.

П3 — NPC (214, 145, 137; Р2, Р4):
- `src/ai_dm/protocol/requests.py` — `NpcUpdate` (:595): поле `location_id: str = Field("", …)` + `NEUTRAL`;
  докстринг `NpcUpdate` и описание `cause` (:560-562: «Причина смерти; … none без смерти») — без «уход только с
  причиной». `WorldNpcUpdate` (:786) — без правок (поле уже есть).
- `src/ai_dm/protocol/handlers/world.py`:
  - `death_refused` (:331) — п. 4 правил, параметр `own_roll=True`.
  - `death_problem` (:504), текст отказа (:509-511) — без «уход».
  - `change_status` (:339) — `cause = request.cause or "left"` при `gone`; `used_rolls.add` только при `evidence_ref`.
  - `location_problem(world, npc, request)` — новая: `None`/`Invalid(unknown_location)`/`Invalid(npc_not_alive)`
    (сейчас это инлайн в `offscreen.py:130-137`).
  - `change_location(ctx, npc, request, decision)` — новая: `npc.location_id = …`, строка лога, `result["location_id"]`
    (сейчас инлайн `offscreen.py:148-150`).
  - `update_problem` (:431) — `"location_id"` в `nothing_to_change`; `merchant_goal_problem` (:452) — четвёртый операнд
    `location_problem` (пятый в `update_problem` даёт smell, см. комментарий :453-454).
  - `npc_update` (:516) — вызов `change_location` первым после `Decision`.
- `src/ai_dm/protocol/handlers/offscreen.py` — `npc_update` (:117): `location_problem`/`change_location` из `world`,
  `death_refused(..., own_roll=own_roll)`; текст отказа (:142-144) без «уход». `basic_problem` (:105) без правок.
- `src/ai_dm/rules/mortality_guard.py:6` `CAUSES` + `left`; `remove_creature` (:56): `left` только при `status ==
  "gone"`, иначе `Rejected(invalid-death)`. `src/ai_dm/state/death.py:8` — `Literal[…, "left"]`.
- `src/ai_dm/rules/knowledge.py:56 mentions` — при Р2 = (1): по словам имени, основа слова ≥ 4 знаков + русское
  окончание ≤ 3 букв из закрытого списка, короткие слова (`SHORT_NAME` :14) — целиком, как сейчас.
  При Р2 = (2) — новая `name_mentioned` в `master/relevance.py`, `knowledge.mentions` не трогать.
- `src/ai_dm/master/relevance.py` — `npc_reason_set` (:29, строка :39 → матчер); `absent_mentions(bundle, text)` —
  новая: именованные живые NPC с `location_id != hero.location_id`, чьё имя матчер находит в `text.lower()`;
  отсортировано по id.
- `src/ai_dm/master/prompt.py` — `PromptBuilder.candidates` (:341): id из `absent_mentions` по рассказу последнего хода
  в `fixed_npcs` (чтобы NPC с `location_id` был в `known_npcs`); `state_data` (:531): помощник `absent_data(ctx)` —
  новый: `[{"id","name","location_id"}]` по `memory.recent_turns[-1].narration`, только если `scene_id` того хода ==
  текущей сцене и `hero.location_id` не `None`; ключ `absent_npcs` только при непустом списке.
- `src/ai_dm/game/turn.py` — `TurnRunner.explore_turn` (:461): после `session.run` — `self.note_absent(work,
  narration, result)` — новая: `before = absent_mentions(work, <рассказ прошлого хода той же сцены>)`, `now =
  absent_mentions(work, narration)` (оба на `work` после запросов хода: перенесённый NPC выпадает из обоих);
  пересечение по id непусто → `result.report_tags.append("npc_absent_ignored")` (авто-репорт пишет `GameApp.auto_report`,
  `game/app.py:274`, по непустым тегам — механизм 217/`sleep_not_rest`). `commit` (:291), `recording` (:440) —
  без правок. Бой (`combat_turn`) не проверяется: рассказ там по логу движка.
- `src/ai_dm/master/prompts/narrator_rules.md` — `:46` фраза про `absent_npcs` и перенос `npc_update.location_id`
  (текст — «Умолчания» У3); `:141` правило «Чего нельзя»: «Смерть NPC … только с `cause` goal/hazard и ссылкой на
  бросок; уход (`status: gone`) — без причины, когда NPC по сюжету ушёл». `world_rules.md:13` — то же для `dead`,
  `gone` без броска.
- `tests/unit/master/test_static_budget.py` — `STATIC_MAX` поднять по правилу файла (схема +1 поле, две фразы правил).
- Тесты: `tests/unit/protocol/test_apply_world.py:379` (`test_gone_without_cause_is_rejected_too` → принимается,
  `status == "gone"`, `death.cause == "left"`, `follows` снят), новые: `gone` с причиной и броском по-прежнему
  принимается (:410), `dead` без причины — отказ (:350-375 как есть), `location_id` неизвестный → `unknown_location`,
  мёртвый NPC → `npc_not_alive`, перенос в локацию героя → NPC в `scene_npcs` следующего промпта;
  `tests/unit/protocol/test_requests.py:309` — `location_id` в `OPTIONAL_FIELDS["npc_update"]`;
  `tests/unit/game/test_game_world_boundary.py:378-391` (за кадром: `dead` чужим броском — отказ как было; новый:
  `gone` без броска — принят); `tests/unit/rules/test_mortality_guard.py:14, :77` (спека и тест: `left` принимается
  только с `gone`); `tests/unit/master/test_master_relevance.py:196-245` + новые на падежи («у Бранки», «Бранке»;
  «Матушка Грета» ↔ «у матушки Греты»; короткое «Ян» не в «Яндексе» — `test_knowledge.py:372`);
  `tests/unit/rules/test_knowledge.py:265-295`, `test_survivors.py:678-715` при Р2 = (1) — не ломаются (ожидание,
  прогнать); новые в `test_master_prompt.py`: `absent_npcs` есть/нет (прошлый ход другой сцены — нет; NPC в локации
  героя — нет), id в `known_npcs`; `tests/unit/game/test_game_turn.py` или `test_auto_reports.py`: два хода с
  упоминанием далёкого NPC без переноса → тег `npc_absent_ignored` и каталог `issues/`; с переносом
  `npc_update location_id` — тега нет; комментарий-шапка `test_auto_reports.py:1-5` — новый тег в список.
- Документы: `docs/ARCHITECTURE.md:305` (правило смерти: `gone` без причины, `left`), E4 — `absent_npcs`;
  `docs/rules-adaptation.md:49` — граница 4.1 для NPC.

### Партии по шагам

1. П1 (S) — `app_defaults.toml`, `context.py`, `prompt.py:364`, тесты и документы выше. На выходе:
   `uv run pytest tests/unit/master tests/unit/config -q` зелёный, `test_static_budget` сторож проходит при 32000;
   `make smells` ≤ 200 (убираем поле и ступень — smells не растут).
2. П2 (S–M) — `master/recap.py`, `state_data`, фраза правил, `STATIC_MAX`, тесты, ARCHITECTURE E4. На выходе: при
   `context_cap = 1` в `test_master_context_build` промпт содержит `scene_recap` с выпавшими `turn_seq`; при большом cap
   ключа нет.
3. П3 (M) — протокол, обработчики, матчер, детектор, тег, правила, тесты, документы. На выходе: сценарии ниже.
   После П3 — `make cov` ≥ 94 %, `make smells` ≤ 200, `make dead`, mutmut по списку.

mutmut (`make mutate FUNCS=… TESTS=<каталог модуля>`, правило AGENTS.md «TESTS — каталог целиком», решение 16 шага 202):
- П1: `ai_dm.master.context:plan ai_dm.master.prompt:PromptBuilder.candidates` TESTS=`tests/unit/master`.
- П2: `ai_dm.master.recap:dropped_turns ai_dm.master.recap:scene_recap ai_dm.master.prompt:PromptBuilder.state_data`
  TESTS=`tests/unit/master`.
- П3: `ai_dm.protocol.handlers.world:death_refused ai_dm.protocol.handlers.world:death_problem
  ai_dm.protocol.handlers.world:change_status ai_dm.protocol.handlers.world:location_problem
  ai_dm.protocol.handlers.world:change_location ai_dm.protocol.handlers.world:npc_update
  ai_dm.protocol.handlers.world:merchant_goal_problem ai_dm.protocol.handlers.offscreen:npc_update`
  TESTS=`tests/unit/protocol tests/unit/game`; `ai_dm.rules.mortality_guard:remove_creature ai_dm.rules.knowledge:mentions`
  TESTS=`tests/unit/rules`; `ai_dm.master.relevance:npc_reason_set ai_dm.master.relevance:absent_mentions
  ai_dm.master.prompt:PromptBuilder.candidates ai_dm.master.prompt:absent_data` TESTS=`tests/unit/master`;
  `ai_dm.game.turn:TurnRunner.note_absent` TESTS=`tests/unit/game`. Время — ожидание, не проверено (каталог game
  с Pilot-тестами не нужен: `tests/unit/game` без `ui`).

### Тестовые сценарии (для кабана-доебы)

- `app().master.context_cap == 32000`; `STATIC_MAX + 32000 ≤ window80` для всех моделей `[context_windows]` —
  проверено: окна прочитаны (`app_defaults.toml:127-138`, минимум 200000), арифметика 55940 ≤ 160000.
- `plan` с `Candidates` без `locations`: порядок вытеснения turns → scenes → npcs → chapters, `location_ids ==
  fixed_locations` — ожидание (тесты `test_master_context.py` после правки).
- Конспект: 10 ходов сцены, окно 8, cap малый → `scene_recap.turns` = «t1–t9 (9 ходов)» (при Р1 = (2)) или только
  вытесненные (Р1 = (1)); `events` без строк «отклонено»; при 1 выпавшем ходе и длинных outcomes — общая длина ≤
  `RECAP_MAX`; ход другой (закрытой) сцены в конспект не входит — ожидание, не проверено.
- Монотонность: оценка запроса после выброса хода не больше, чем до (конспект растёт на ≤ `RECAP_LINE_MAX` на ход, ход
  — на весь `narration`) — ожидание; тест на `plan` с реальным `render`.
- 145: `npc_update(status=gone)` без `cause`/`evidence_ref` → accepted, `npc.status == "gone"`, `death.cause ==
  "left"`, `follows is None`, в `scene_npcs` следующего промпта NPC нет, `ctx.used_rolls` не пополнен; `status=dead`
  без причины → rejected `invalid-death` (как было); за кадром `gone` без броска → accepted, `dead` чужим броском →
  rejected — ожидание, не проверено.
- 137: `far_npc` «Бранка»; рассказ «подошёл к Бранке» → `"branka" in relevant_npcs`; «у матушки Греты» ↔ «Матушка
  Грета»; «Ян» не находится в «Яндексе» — ожидание.
- 214: прошлый ход той же сцены с «Ольгерд» при `olgerd.location_id != hero.location_id` → `state_data["absent_npcs"]
  == [{"id": "olgerd", "name": …, "location_id": …}]`, `olgerd` в `known_npcs`; прошлый ход другой сцены → ключа нет;
  Ольгерд в локации героя → ключа нет; `npc_update(npc_id=olgerd, location_id=<локация героя>)` → accepted, NPC в
  `scene_npcs`; `location_id="nowhere"` → `Invalid unknown_location` — ожидание.
- 214 репорт: ходы 1 и 2 с «Ольгерд» в рассказе без переноса → в ходе 2 `result.report_tags` содержит
  `npc_absent_ignored`, `issues/` получает каталог; ход 2 с `npc_update location_id` → тега нет — ожидание.
- Проверка руками (живой прогон drunk_dragon): `journal/calls-*.jsonl` `meta.context.dropped == []` при 32000;
  `scene_recap` в `messages[0]` при сцене длиннее 8 ходов; после упоминания далёкого NPC — `absent_npcs` в следующем
  запросе; репорт `issues/<время>-t<ход>-npc_absent_ignored/`.

### Развилки и риски

- Р1 «Выпавшие ходы» сцены: (1) только вытесненные планом по cap; (2) все ходы текущей сцены, которых нет в
  `context_plan.turns` — вытесненные и за окном `recent_turns = 8`. Рекомендую (2): симптом «не помнит сцену» один и
  тот же, а при 32000 ходы выпадают только за окном (t1379: dropped []), иначе конспект при умолчаниях не сработает
  никогда (решение 8). Видно рассказчику → игроку. Решает Влад; разблокирует П2.
- Р2 Матчер имён с падежами (решение 7): (1) один матчер — расширить `rules/knowledge.py:56 mentions` (уже ловит
  «Олдрику» по началу слова, но не «Греты»/«у матушки Греты»), им пользуются relevance, детектор 214, `note_presence`
  (:87, запись «знакомство» в журнал героя) и `reveal_names` (`survivors.py:153`); (2) стемминг только в
  relevance + 214 (новая функция), `knowledge.mentions` как есть. Рекомендую (1): одна правда об упоминании имени,
  BACKLOG 137 закрывается целиком; побочно журнал героя чуть чаще отметит знакомство (видно игроку в журнале знаний).
  Решает Влад; разблокирует П3.
- Р3 Состав `scene_recap.events`: (1) все строки `outcomes` принятых запросов выпавших ходов; (2) только «что найдено»
  — строки `give_item`/`give_custom_item`/`gold`/`knowledge_note`/`award_xp` по префиксам лога. Рекомендую (1): решение 4
  говорит «что найдено», но строки лога короткие, потолок держит объём, а фильтр по префиксам хрупок (тексты логов
  живут в обработчиках). Решает Влад; разблокирует П2.
- Р4 `absent_npcs` и спутник не в локации героя (`follows == hero`, `location_id` другой — рассинхрон после `follows`
  без переноса): (1) считать отсутствующим — сигнал и перенос, как у любого NPC; (2) исключать из сигнала. Рекомендую
  (1): присутствие в сцене = локация (`game/scene.py:14 scene_npc_ids`), а `follows` локацию не трогает
  (`world.py:296`). Решает Влад; П3.
- Риск: `make smells` = 200 = потолок. Новые функции — короткие и плоские; `update_problem` не получает пятый операнд
  (`world.py:453`), `state_data` растёт на две строки вызовов помощников. Партия, поднявшая smells, чинит их у себя.
- Риск: `STATIC_MAX` (запас 34 токена) превысится в П2 и П3 — поднимать по правилу файла, с причиной.
- Риск: конспект внутри цикла `plan` растёт при выбросе хода; если ход короче строки конспекта, оценка может не
  уменьшиться — цикл всё равно конечен (кандидаты кончаются), покрыть тестом монотонности на реальных размерах.
- Риск 145 (груминг): уход без броска — ослабление 4.1 для любого NPC, включая ключевых; принято решением 2.
- Риск 214: сигнал на следующий ход — игрок прочтёт ход с «Ольгердом в пещере» прежде, чем рассказчик перенесёт
  или объяснит (решение 6).
- Регресс в области: `test_auto_reports.py`, `test_game_turn.py` ставят `context_cap = 1` сами — умолчание их не
  трогает; `test_master_context_build.py:100` «динамика без статики» — проверить при 32000.

### Умолчания (внутреннее)

- У1 Имена: модуль `master/recap.py`, функции `dropped_turns`, `scene_recap`, константы `RECAP_MAX = 1200`,
  `RECAP_LINE_MAX = 120`; помощники `absent_data` (prompt), `absent_mentions` (relevance), `note_absent` (turn),
  `location_problem`, `change_location` (handlers/world); тег `npc_absent_ignored`.
- У2 При переполнении `RECAP_MAX` отбрасываются старые строки (новые ближе к текущему ходу).
- У3 Текст правила 214 (`narrator_rules.md:46`): «`absent_npcs` — NPC, которых ты назвал в прошлом ходу, а они не в
  локации героя (их `location_id` — в `known_npcs`): если по сюжету NPC пришёл к герою — в этом ходу `npc_update` с
  `location_id` локации героя (`location.id`); иначе объясни его отсутствие и не описывай его рядом; одного текста
  мало». Описание поля: «Id локации, куда NPC перешёл (пришёл к герою — id локации героя); пусто = не менять».
- У4 Детектор берёт только `narration` прошлого хода (не `player_input`: в t1310 игрок сам написал «Ольгерд пропал»),
  только если `scene_id` того хода — текущая сцена; `absent_npcs` считается в любом режиме промпта (в бою — пусто
  или без вреда), репорт — только в `explore_turn`.
- У5 Матчер (при Р2 = (1)): слово имени ≥ 4 знаков — основа без последней гласной (а, я, о, е, ё, й, ь, ы, и) +
  окончание из закрытого списка (а, я, у, ю, ы, и, е, о, ой, ей, ою, ею, ом, ем, ам, ям, ах, ях, ами, ями, ов, ев) +
  граница слова; все слова имени должны найтись; ≤ 3 знаков — целиком (`SHORT_NAME`). Регистр — `lower`, как сейчас.
- У6 `gone` без причины пишет `DeathRecord(cause="left")`; `left` в `CAUSES` принимается только со `status == "gone"`
  (`remove_creature`), в `NpcUpdateBase.cause` рассказчику недоступен; `goals.on_npc_killed` только для `dead`.
- У7 Перенос `location_id` рассказчиком — в любую локацию мира (решение 1: «та же проверка, что у мира»).
- У8 Тесты: `test_recap.py` новый; тавтологию `test_neighbor_locations_are_never_dropped` (:408) удалить.

### Открытые вопросы

1. Р1 — что считать выпавшими ходами сцены (`master/recap.py:dropped_turns`, новая): (1) только вытесненные по cap;
   (2) все вне `context_plan.turns`; рекомендую (2) — при 32000 иначе конспект не сработает; разблокирует П2;
   решает Влад.
2. Р2 — один матчер в `rules/knowledge.py:56 mentions` или отдельный для relevance + 214 (`relevance.py:39`);
   рекомендую один; разблокирует П3; решает Влад.
3. Р3 — `scene_recap.events`: все строки outcomes или только находки; рекомендую все; разблокирует П2; решает Влад.
4. Р4 — спутник не в локации героя в `absent_npcs`: сигналить (рекомендую) или исключать; П3; решает Влад.

## Правки по ревью

П1 (мама: замечаний нет; свекровь: чисто, решений за пользователя нет). Адреса вне плана — прямые следствия
правила 1 (поле `Candidates.locations` убрано), решение кабана, приняты мамой:
- `prompt.py` `draft_plan` — убрано `c.locations` (иначе `AttributeError` в `render`).
- `tests/scenarios/test_stage4_memory.py`, `tests/unit/game/test_game_commands.py:565` (16_000 → 32_000) — ожидания
  под новое умолчание.
- Удалён `test_candidates_have_no_removable_locations` — тавтология после удаления ступени (как У8).

П2 (мама: можно мержить, три необязательных замечания; свекровь: чисто). Адреса вне плана — решения кабана,
приняты мамой и свекровью:
- `tests/scenarios/memory_script.py` `MEMORY_CONTEXT_CAP` 2950 → 3020 — окно сценария сдвинуто полем
  `scene_recap` (рабочее 3010 < x < 3030, границы в комментарии).
- `STATIC_MAX` 24030 (замер 23997, +91 токен от фразы в `narrator_rules.md`).
- Тесты конспекта и промпта — в `tests/unit/master/test_recap.py`, а не в `test_master_context_build.py`;
  `test_master_rules.py` — `scene_recap` в списке полей.
- Р1 реализован как (2) — по решению 9; оговорка о (1) в «Модулях» — текст до аппрува.
Правки по замечаниям мамы (кабан тем же id): `turns_word(n)` — «t3 (1 ход)», склонение 1/2–4/5+/11–14;
потолок `RECAP_MAX` кабан сначала сделал только на `events`; свекровь (повтор): план — «всего ≤ RECAP_MAX».
Решение Влада 2026-10-29 (окно): потолок на весь конспект, вместе с `npcs`, как в плане; при переполнении
выпадают старые события. Доеба добавил по повтору мамы значения 3/13/14 в `test_turns_word_declension`. Мама и свекровь (повтор 2):
чисто; по замечанию мамы в ARCHITECTURE E4 дописано, что имена `npcs` не режутся (код не менялся).

П3 (мама: можно мержить, четыре необязательных замечания; свекровь: чисто, отклонения — по плану: `STATIC_MAX`
24240 по правилу файла (замер 24212), `left` — У6, текст отказа без «уход» — правило 4). Правки по замечаниям
мамы (кабан и доеба тем же id):
- `mortality_guard.py`: `CAUSES` снова из четырёх, `NPC_CAUSES = (*CAUSES, "left")`; `left` принимает только
  `remove_creature` при `gone`, `mark_dead` и `remove_hero` — нет (как У6 и ARCHITECTURE).
- `world.py` `change_status`: `gone` без `evidence_ref` всегда пишет причину `left`, даже при `goal|hazard` от
  рассказчика; с броском — своя причина (по У6 и решению 2, решение кабана).
- `absent_mentions` при NPC с `location_id=None`: поведение по плану (`location_id != hero.location_id`), У4 о
  нём молчит — закреплено тестом, код не менялся.
- Шапка `test_auto_reports.py` — тег `npc_absent_ignored`; тесты на `left` и на `gone` без броска / с броском.
Мама (повтор): чисто. Свекровь (повтор): `gone` с броском, но без причины давал `cause=None`, `remove_creature`
отклонял, NPC не уходил — нарушение решения 2. Кабан: в `change_status` `gone` без броска или без причины
пишет `left`, бросок при этом не тратится; доеба — тест `test_gone_with_roll_but_without_cause_is_left_and_roll_is_not_spent`.
Мама (повтор 2): можно мержить; два необязательных — условие траты броска упрощено до `if not left:` (кабан);
`gone` с чужим/неизвестным броском писал причину без проверки — вопрос к папе. Решение папы (архитектор,
2026-10-29, вариант 2; причину `gone` никто не читает — не продукт): помощник `evidence_ok(ctx, request,
own_roll)` в `world.py`; `death_refused` = `dead` и не `evidence_ok`; у `gone` причина из запроса только при
`evidence_ok`, иначе `left`, бросок тратится только тогда; `offscreen.py` передаёт `own_roll`. Доеба — тесты
на неизвестный, потраченный и чужой (за кадром) бросок; «бросок не потрачен» за кадром не покрыт (не виден
из теста уровня игры).
`make cov` после П3: 98,16 %, упал `test_save_bundle_schema_matches_fingerprint` — `DeathRecord.cause` + `left`
меняет схему сейва («без полей сейва» — оценка архитектора, не решение Влада). Решение папы (архитектор,
2026-10-29, вариант 1; версия схемы внутренняя, не продукт): `CURRENT_SCHEMA_VERSION = 13`, миграция-пустышка
`m0013_v12_to_v13`, отпечаток `save_v13.schema.json`; полей сейва нет, расширен Literal. Сейв v13 старым кодом
не откроется (SaveTooNew); живые миры мигрируют при первой загрузке. Кабан: `m0013_v12_to_v13.py`, версия 13,
`save_v13.schema.json`, раздел «Сейв v13» в ARCHITECTURE; следствие — 13 в `SCHEMA_VERSIONS` скриптов
`scripts/migrate_dusk_{18plus,ferry,pact}.py` (как при v12). Доеба: проверки версии 12 → 13 (в т.ч.
`test_companion.py:238`), `test_migration_v13.py`, шапка отпечатка, отказ скриптов — на версии 14.
Мама (повтор 4): нумерация версий сейва в планах сдвинулась — ARCHITECTURE `:757`, `:916` (М0 → v14, С0 → v15)
правит кабан (сделано); ROADMAP `:13`, `:170`, `:172`, `:177`, `:178` — архитектору при закрытии шага.
Свекровь (повтор 4): план (строка 76) говорил «сейвы не мигрируются» — решение Влада 2026-10-29 (окно): да, v13;
живые миры мигрируют при первой загрузке, откат на старый код — из бэкапа. Мелочь свекрови про проверку
отпечатка v12 уже закрыта (`test_schema_fingerprint.py:199`).

Проверки шага (оркестратор): `make cov` 98,16 %, 22687 passed (1 упал — Pilot-тест меню ошибки TUI под нагрузкой,
повтор файла 91 passed; это BACKLOG 216, ui шаг не трогал); smells 200; `make dead` чист. mutmut по спискам П1–П3
(+ `world:evidence_ok`): в диффе 9 выживших, доеба (sonnet) убил 7 тестами, повтор — выжили 2 эквивалентных:
`recap.scene_recap _24` (проверка `name != ""` лишняя — `mentions("")` и так False), `offscreen.npc_update _33`
(параметр `npc` в `death_refused` не используется). Старые строки — BACKLOG 221.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план ФС (партии П1–П3, развилки Р1–Р4); эксплуатационные расходы игры от правок шага.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| Вход рассказчика, `context_cap` 16000 → 32000 (134) | у Влада 0 (в `~/.config/ai-dm/config.toml:7` уже 32000); у нового игрока — до +16k входных токенов на ход, только когда история > 16k | цены рассказчика (deepinfra/gemini) не сверял — не проверено; объём — по формуле `static + context_cap` | оставить 16000 умолчанием | до 16k ток/ход | решение 8 Влада и симптом «теряет сцену» (t1379); не предлагаю |
| `scene_recap` + `absent_npcs` в `state_data` | ≤ 1200 знаков (≈ 300–400 ток) на ход с выпавшими ходами | `RECAP_MAX = 1200` (У1); ИИ-вызова нет (решение 4) | — | — | — |
| Подписки, хостинг, БД, железо | 0 | новых зависимостей и сервисов в плане нет | — | — | — |

Прогон цепочки (разовый). Масштаб — от «Итога» шага 217 (`docs/plan-217.md`, одна партия S): в ФС три партии
(S, S–M, M), коэффициент ≈ ×4 к ролям исполнения, ×2,5 к оркестратору. Допущение, не замер.

| Партия | Время |
|---|---|
| груминг + аудит + план (прошло) | 16,8 мин работы (свинопас 3,2, свекровь 0,6, папа 13,0 — metrics.py) |
| П1 (S) | kaban 2–5 мин, doeba 2–5 мин; mutmut ≈ 20–25 мин фоном (2 функции) |
| П2 (S–M) | kaban 5–10 мин, doeba 3–6 мин; mutmut ≈ 20–30 мин фоном (3 функции) |
| П3 (M) | kaban 10–20 мин, doeba 5–10 мин; `make cov` ≈ 22 мин + mutmut ≈ 45–70 мин фоном (≈ 14 функций, 4 каталога) |
| мама ‖ свекровь | 3 × (2–4 мин) + круги правок |
| Декарт (3 + 1 сводный) | 4 × 2–4 мин |
| итого | ≈ 1–1,5 ч агентов + ≈ 2–2,5 ч cov/mutmut фоном |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`):
```
kaban.md:model: sonnet
kaban-doeba.md:model: sonnet
mama-kaban.md:model: opus
kaban-svekrov.md:model: opus
kaban-dekart.md:model: fable
papa-kaban.md:model: fable
```
Свинопас и оркестратор — opus (metrics.py); мой запуск — Opus 5.5, в смету не включён.

| Роль | Модель | Токены | $ (тариф metrics.py от 2026-10-25) |
|---|---|---|---|
| svinopas (прошло) | opus | 1,08 M | 0,81 — metrics.py |
| kaban-svekrov, груминг (прошло) | opus | 0,09 M | 0,20 — metrics.py |
| papa-kaban (прошло) | fable | 1,99 M | 2,20 — metrics.py |
| kaban | sonnet | ≈ 3 M (217: 0,74 × 4) | ≈ 1,3 |
| kaban-doeba (+ разбор мутантов sonnet/haiku) | sonnet | ≈ 1,2 M | ≈ 0,9 |
| mama-kaban | opus | ≈ 1,6 M | ≈ 2,2 |
| kaban-svekrov, П1–П3 | opus | ≈ 2,4 M | ≈ 2,5 |
| kaban-dekart (4 вызова, выжимки ≤ 400 KB) | fable | ≈ 1,2 M | ≈ 1,6 |
| оркестратор | opus | ≈ 20–25 M | ≈ 9–11 |
| итого шага | | ≈ 32–37 M | ≈ 21–23 (диапазон 18–28) |

Дешевле: оркестратор — главная статья (≈ 45 %): `/compact` между партиями, субагентам ссылки на файлы
(экономия ≈ 2–3 $; теряем ничего, если состояние записано в документ). Kaban и doeba уже на sonnet; ревью,
аудит, маму, свекровь, оркестратор не трогаю. Вердикт: ок по бабкам.

## Итог

Закрыты BACKLOG 134, 135, 137, 145, 214. Мутанты по старым строкам — BACKLOG 221.

**Источник токенов:** `metrics.py` по `~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/92726265-d425-4604-96fe-dc1d8049e8e3.jsonl`
(id ролей — scratchpad `agents.md`); **цены:** тариф metrics.py от 2026-10-25,
https://platform.claude.com/docs/en/about-claude/pricing (с сайтом не сверял — не проверено; fable — по ценам Opus).

| Партия | Смета | Факт |
|---|---|---|
| груминг + аудит + план | 16,8 мин (прошло) | 16,8 мин работы (свинопас 3,2, свекровь 0,6, папа 13,0) |
| П1 (S) | kaban 2–5, doeba 2–5 мин | kaban 4,7, doeba 1,2, мама 1,2, свекровь 1,3 мин — в смете |
| П2 (S–M) | kaban 5–10, doeba 3–6 мин | kaban 13,2, doeba 2,3, мама 2,2, свекровь 2,3 мин (сегменты в интервале 56 мин) — выше сметы: круг правок `RECAP_MAX` и склонения |
| П3 (M) | kaban 10–20, doeba 5–10 мин | kaban 28,0, doeba 23,5, мама 9,0, свекровь 7,9 мин — выше: 4 круга ревью, `evidence_ok` и сейв v13 (в плане не было) |
| cov + mutmut | ≈ 2–2,5 ч фоном | cov 13 + 17 мин, mutmut ≈ 46 мин (23:08–23:54), доеба-мутанты 1,0 мин — ниже сметы |
| папа-архитектор (решения П3, закрытие) | не было | ≈ 4,9 мин сверх плана (17,9 − 13,0) |
| Декарт (3 + 1) | 4 × 2–4 мин | не запускался на момент подсчёта |
| итого | ≈ 1–1,5 ч агентов + 2–2,5 ч фоном | ≈ 2,1 ч агентов + ≈ 1,3 ч фоном; сессия — интервал 506 мин, в т. ч. окна Влада |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| оркестратор | opus | 22,70 M | 9,56 — на момент подсчёта 00:38 |
| svinopas | opus | 1,08 M | 0,81 |
| papa-kaban (план + архитектор ×2) | fable | 4,51 M | 5,85 |
| kaban | sonnet | 8,77 M | 3,15 |
| kaban-doeba (+ мутанты) | sonnet | 6,07 M | 2,34 |
| mama-kaban | opus | 3,75 M | 4,28 |
| kaban-svekrov (груминг + П1–П3) | opus | 3,30 M | 3,59 |
| kaban-test (режим 1) | opus | 0,50 M | 0,67 — на момент подсчёта 00:38, режим 3 не входит |
| kaban-dekart | fable | — | не запускался |
| итого шага | | 50,67 M | 30,26 |

Расхождение: смета ≈ 21–23 $ (18–28) → факт 30,26 $. Выше сметы — папа (5,85 при 2,20 прошедших: два решения
архитектора по П3 — `evidence_ok` и сейв v13), мама (4,28 при 2,2) и свекровь (3,59 при 2,7) — 4 круга ревью П3,
kaban (3,15 при 1,3) — 8,8 M токенов, чтение кэша на длинных сегментах П2–П3. Оркестратор — 9,56, в смете.

**Проблемы:**
- Действие проектировщика: снять `context_cap = 32000` из `~/.config/ai-dm/config.toml:7` — теперь это умолчание
  (замечание архитектора).
- План говорил «сейвы не мигрируются» — `DeathRecord.cause` + `left` сменил схему: сейв v13, миграция-пустышка
  (решение Влада 2026-10-29); откат на старый код — из бэкапа.
- ROADMAP `:13`, `:170`, `:172`, `:177`, `:178` — нумерация версий сейва сдвинулась, правит архитектор.
- 2 эквивалентных мутанта (`recap.scene_recap _24`, `offscreen.npc_update _33`); Pilot-тест TUI под нагрузкой — BACKLOG 216.

**Итого:** смета ≈ 21–23 $, 1–1,5 ч + 2–2,5 ч фоном → факт 30,26 $ (без Декарта), ≈ 2,1 ч агентов + ≈ 1,3 ч фоном.
Разбор — кабан Декарта.
