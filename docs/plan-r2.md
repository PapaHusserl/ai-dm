# План партии Р2 «Темп и отказы» (papa-kaban, 2026-10-13; на аппрув проектировщика)

Задача: BACKLOG 38 е (темп), ж (отказ рассказчика), к (отказ summarizer) по решениям docs/plan-r2.md
(«Решения проектировщика»): **В1б** только затишье (правила «одна угроза за раз» нет, `world_rules.md` не трогаем — В4а),
**В2а** темп не настройка пресета, В3а `nudge` не трогаем, **В5а** один автоповтор хода на той же модели с припиской,
затем меню как сейчас (запасной рассказчик ROADMAP:23 отменён), В6а повтор всего хода с новой копии, В7а приписка не в
`player_input`, **В8а** только исследование и бой, В9а те же броски, **В10а** отказ summarizer → повтор на модели
рассказчика → `fallback_summary`, В11а только `refusal`/`invalid`, В12а глава той же цепочкой (последний шаг — склейка
`concat`), **В13б** отказ world — не в Р2 (BACKLOG 46), В14а тег в репорте и `source` выжимки, игроку ничего. Сейв v9,
полей и миграций нет. Размер S ≈ 0,6 млн по шкале R5. Код на fe56beb (Ф1), src чистый; smells 200/206.

## Что показал код (сверка перед планом)

- **Отказ рассказчика.** `MasterSession.run` на `stop_reason == "refusal"` бросает `TurnFailed("refusal", …, ["refusal"])`
  (`master/session.py:260–262`); `play_turn` ловит `TurnFailed` и зовёт `failed` (`game/turn.py:197–198, 207–216`):
  копия `work` выбрасывается, `result.report_tags = failure.report_tags`, меню `ERROR_MENU`, `REFUSAL_HINT`. Ход идёт на
  `work = bundle.model_copy(deep=True)`, `rng = Rng.from_state(work.world.rng)` (187–188) — повтор с новой копии даёт те
  же броски (В9а). Все вызовы модели одного хода — через `self.new_session(run_id)` (323–327; explore 363, classify 396,
  narrate 460) и дальше в `combat_flow.start_fight/make_engine(ctx, session, …)` (npc_choice) — одна точка, где можно
  подменить запрос. `call_numbers` по `run_id` нумеруют вызовы сквозь попытки; `mark_journal(run_id, …)` — один раз в
  конце (`journal.mark_turn` помечает все записи run_id).
- **Запрос рассказчика.** `PromptBuilder.request` (`master/prompt.py:192–203`): три `SystemBlock(cache=True)` + одно
  user-сообщение с JSON состояния (`player_input` внутри). Gemini: ключ явного кэша — sha256 **всех** блоков system
  (`gemini_adapter.py:119–120, 156–161`), новый ключ создаёт кэш заново и **удаляет прежний** той же модели/роли
  (`delete_replaced`, 189–200). Значит, лишний `SystemBlock` только в повторном запросе = два пересоздания кэша
  (~20 тыс. токенов записи на повтор и ещё раз на следующем ходу). User-сообщение в явный кэш Gemini не входит
  (`build_prefix_fields`: system, tools, tool_config); у Anthropic `cache_control` на последнем блоке сообщения
  (`anthropic_adapter.py:95`) — дополнительный `Text`-блок кэш префикса не ломает. → Q1.
- **Summarizer.** `SummarizerSession(adapter, app_cfg, …, model, call_numbers)` (`master/summarizer.py:141–177`),
  `run_scene`/`run_chapter` → `MasterSession(role="summarizer", builder=SummarizerPromptBuilder(model))`; результат в
  `ctx.summary_text/summary_title`, `ctx.chapter_text/game_text` (`protocol/context.py:44–50`). Сбои: `TurnFailed`
  (`refusal`, `invalid` после `invalid_retries = 2`, `network`, `fatal`) и `LlmError`. `boundary.summarize_scene`
  (59–89) и `close_chapter` (131–173) ловят `(TurnFailed, LlmError)`, ставят `result.failed_role = "summarizer"` и
  пробрасывают; `close_chapter` сам бросает `TurnFailed("invalid")` при пустом `chapter_text/game_text` (151–153).
  `finish_boundary` (189–216) ловит всё → `boundary_pending` остаётся. `fallback_summary(work, scene)` (49–56) и ветка
  `summarizer is None` (`source="fallback"`, глава — `"concat"`) — готовые последние шаги цепочки.
- **Модель рассказчика для повтора summarizer.** `TurnRunner.adapter/model` — адаптер и id модели рассказчика
  (`turn.py:98–103`); адаптеры привязаны к модели (`make_adapter(provider, model)`), поэтому «summarizer на модели
  рассказчика» = `SummarizerSession(self.adapter, …, model=self.model)`. `SummarizerPromptBuilder.find_role_cfg`
  для чужой модели вернёт `roles.summarizer` (max_tokens/effort flash-lite) — приемлемо. Смена рассказчика через
  меню (`app.set_narrator` → `runner.set_adapter`) подхватится сама, если бэкап строить лениво в
  `new_summarizer_session`.
- **Replay — ловушка.** `play_report`/старт `--replay` раздают адаптеры **по ролям**: `ReplayAdapter(records,
  role="narrator")` рассказчику, `role_replay(records, "summarizer")` summarizer'у (`ui/cli.py:328, 405–418, 686–703`);
  `ReplayAdapter.complete` идёт по записям роли последовательно и сверяет `fingerprint` (`llm/replay.py:11–34`).
  Вызов бэкапа пишется в журнал как `role: summarizer` (роль `MasterSession`), но пойдёт через адаптер рассказчика →
  при повторе это `ReplayAdapter(role="narrator")` → расхождение. Нужен явный адаптер бэкапа для replay (п. 3.3).
  Повтор хода рассказчика replay переживает: обе попытки под одним `run_id`, записи роли narrator по порядку.
- **Авторепорт.** `GameApp` пишет репорт на **любой** непустой `turn.report_tags` (`game/app.py:232`); теги —
  свободные строки (`TurnCapture.tags`, `reports/markdown.py:135`). Новые теги `refusal_retry`/`refusal_fallback`
  дадут авторепорт в `issues/` и на успешных ходах → Q3.
- **Правила.** `narrator_rules.md` 30,7 тыс. символов; о темпе ничего; `nudge` — строка 72. Мок памяти
  `tests/scenarios/memory_script.py`: `WINDOW = 24000`, бюджет 80 % = 19200, пик Ф1 18880 (запас ≈ 320 «токенов»
  = ~800 символов при `len/2.5`). Правило ≤ 400 символов в запас укладывается — подъём `WINDOW` не обязателен.
- **Тесты, которые изменят ожидание.** `tests/unit/master/test_master_session_errors.py:171`
  `test_refusal_is_not_retried` — остаётся верным для `MasterSession` (повтор делает `TurnRunner`, не сессия);
  `tests/unit/game/test_game_turn.py:205–290` (`REFUSAL` в `CASES`: один вызов → теперь два; `report_tags ==
  ["refusal"]` → плюс `refusal_retry`); `test_game_summarizer_boundary.py:248` `test_three_invalid_answers_give_error_menu`
  и `test_game_chapter_summary.py:187, 416, 426, 515, 532` (invalid ×3 → теперь цепочка, не меню); сбои `fatal`
  (`summ_fail_steps`) — без изменений (В11а). Рига `make_summ_rig` (`summarizer_kit.py:120`): рассказчик —
  `scripted(narrator_steps)`; при мягком сбое summarizer бэкап заберёт шаг из сценария рассказчика — в новых тестах
  давать ему шаги (или `ReactiveAdapter`), иначе `ScriptExhausted`.
- Мастер героя и импорт (`ui/hero_wizard.py`, `ui/import_session.py`) строят сессии сами, `TurnRunner` не трогают —
  В8а выполняется без ветвления.

## Реализация (kaban; src и docs)

### 1. Темп (В1б) — `src/ai_dm/master/prompts/narrator_rules.md`
1.1. Новый короткий раздел `## Темп` после раздела «Бой сверх бюджета, клад, редкость, подталкивание» (после строки
   про `nudge`, перед «## Сюжетные предметы»), ≤ 400 символов, одно правило: «После развязки — закрытой сюжетной линии
   или законченного боя — дай герою передышку: ближайшая сцена без новой угрозы (быт, разговоры, дорога, торговля,
   исследование). Новую опасность вводи не раньше следующей сцены. Сигнал `nudge` и слухи — фон, не угроза.»
   Формулировку финально — kaban; «одна угроза за раз» не писать (В1б). `world_rules.md`, `nudge.py`, пресеты,
   `Tone` — не трогать (В2а, В3а, В4а).
1.2. Прогнать `tests/scenarios/test_stage4_memory.py`; если пик > бюджета — поднять `WINDOW` в `memory_script.py`
   (5-й подъём, с комментарием в том же стиле) и отметить в BACKLOG 45.

### 2. Автоповтор хода рассказчика (В5а–В9а) — `src/ai_dm/game/turn.py`, `src/ai_dm/master/session.py`
2.1. `master/session.py`: `MasterSession.__init__(…, note=None)` — текст приписки; в `run` после
   `req = self.builder.build(...)`: `req = self.with_note(req)` — при `note` добавить блок с припиской к запросу
   (по Q1а — `Text(text=note)` вторым блоком в `messages[0].content`; по Q1б — `SystemBlock(text=note)` в конец
   `system`). Приписка живёт в запросе, в `TurnRecord.player_input` не попадает (В7а). Больше в сессии ничего.
2.2. `turn.py`: константа `SOFTEN_NOTE = "Системная приписка: опиши эту сцену сдержанно, без натурализма."` рядом с
   `REFUSAL_HINT`; атрибут `self.note = None` в `__init__` (в стиле `failed_role`/`deferred_input`);
   `new_session(run_id)` → `MasterSession(…, note=self.note)`. Сигнатуры `explore_turn/combat_turn/narrate_combat`
   не меняются (смеллы «много параметров» не растут).
2.3. `play_turn`: вынести тело «копия → explore/combat» в `attempt(self, player_input, run_id, result) -> tuple[work,
   rng, narration]` (≤ 5 параметров; `CombatRoundLimit` → `TurnFailed("round_limit")` как сейчас, `Exception` —
   `mark_journal aborted` + raise). В `play_turn`:
   ```
   try: work, rng, narration = self.attempt(...)
   except TurnFailed as failure:
       if failure.reason != "refusal": return self.failed(result, failure)
       result = self.retry_result(run_id, result)   # новый TurnResult, before тот же, report_tags = ["refusal_retry"]
       self.note = SOFTEN_NOTE
       try: work, rng, narration = self.attempt(...)
       except TurnFailed as again: return self.failed(result, again)
       finally: self.note = None
   ```
   Повтор ровно один (В5а), на той же модели, с новой копии бандла (В6а; запросы первой попытки в `result`
   первой попытки и выбрасываются вместе с ним), `rng` из `work.world.rng` → те же броски (В9а). Оба режима
   (`explore_turn`, `combat_turn`, включая ход цифрой без classify и npc_choice в движке) — через `attempt` (В8а).
   `time_before_s` брать внутри `attempt` или от `self.bundle` до попытки (бандл не меняется).
2.4. `failed`: `result.report_tags = list(dict.fromkeys(started.report_tags + failure.report_tags))` — чтобы при
   повторном отказе в репорте были и `refusal`, и `refusal_retry`. `REFUSAL_HINT` не менять (тест на «tone»/«модел»).
2.5. Журнал: обе попытки под одним `run_id` (нумерация `call_numbers` сквозная), статус `committed`/`aborted` — одной
   пометкой в конце, как сейчас. Replay: `ReplayAdapter(role="narrator")` отдаёт отказ, затем ответ — тот же путь.

### 3. Цепочка summarizer (В10а–В12а, В14а) — `src/ai_dm/master/summarizer.py`, `src/ai_dm/game/boundary.py`,
`src/ai_dm/game/turn.py`, `src/ai_dm/game/app.py`, `src/ai_dm/ui/cli.py`
3.1. `master/summarizer.py`: `SummarizerSession.__init__(…, backup=None)` — второй `SummarizerSession` (модель
   рассказчика) или None. `SOFT_REASONS = ("refusal", "invalid")`; `soft_failure(error) -> bool`
   (`isinstance(error, TurnFailed) and error.reason in SOFT_REASONS`). Метод `chain(self, call, ok) -> tuple[TurnContext |
   None, bool]`: для `session in (self, self.backup)` (без None): `ctx = call(session)`; `ok(ctx)` → `(ctx, fell)`;
   мягкий сбой или `not ok(ctx)` → `fell = True`, дальше; жёсткий (`network`, `fatal`, `rounds`, `LlmError`) → raise.
   Все попытки исчерпаны → `(None, True)`. Обёртки: `try_scene(bundle, registry, cfg, run_id)` =
   `chain(lambda s: s.run_scene(bundle, registry, cfg, run_id), lambda c: c.summary_text is not None)`;
   `try_chapter(…)` = `chain(lambda s: s.run_chapter(…), lambda c: bool(c.chapter_text and c.game_text))` — проверка
   «пустая выжимка главы» переезжает из `close_chapter` в `ok` и тоже ведёт по цепочке (В12а). Журнал: вызов бэкапа —
   `role: summarizer`, тот же `run_id` границы, модель рассказчика (`call_numbers` общие — нумерация сквозная).
3.2. `game/boundary.py`: `summarize_scene` — ветка `summarizer is not None`: `ctx, fell = summarizer.try_scene(work,
   registry, cfg, run_id)` в `try/except (TurnFailed, LlmError)` (как сейчас: `failed_role = "summarizer"`, raise);
   `if fell: result.report_tags.append("refusal_fallback")`; `ctx is None` → `title = scene.title`, `text =
   fallback_summary(work, scene)`, `source = "fallback"`; иначе как сейчас (`source = "summarizer"`). `close_chapter`:
   `ctx, fell = summarizer.try_chapter(...)`; `ctx is None` → та же ветка, что `summarizer is None` (склейка,
   `source="concat"`, `game_summary` не меняется — В12а); вынести склейку в `concat_chapter(work, chapter) ->
   tuple[title, text]`, чтобы не дублировать (≤ 5 return в `close_chapter`). `fallback_summary` и `finish_boundary` не
   меняются; `resume_boundary`/`retry`/загрузка застрявшего сейва (dusk_academy) достраивают границу тем же путём.
   `failed_role` теперь ставится только при жёстком сбое → меню `switch_model` как раньше.
3.3. `game/turn.py: new_summarizer_session` — строить `backup`: `SummarizerSession(self.summarizer_backup or
   self.adapter, self.app_cfg, journal=…, ledger=…, sleeper=…, now=…, model=self.model, call_numbers=self.call_numbers)`;
   **не строить** (backup=None), если адаптер/модель summarizer совпадают с рассказчиком (Q2а: `adapter is self.adapter
   and model == self.model`). Новый kwarg `TurnRunner(…, summarizer_backup=None)` — адаптер для вызова бэкапа (None —
   адаптер рассказчика); нужен только replay. `GameApp(…, summarizer_backup=None)` прокидывает в `TurnRunner`.
   `ui/cli.py`: в `play_report` и на старте с `--replay` передавать `summarizer_backup=summarizer_adapter`
   (`ReplayAdapter(role="summarizer")` — запись бэкапа лежит там по порядку, модель запроса = модель рассказчика из
   журнала, отпечаток совпадёт). В `--mock` бэкап — мок рассказчика (шаги сценария); для `--mock` без
   `--mock-summarizer` summarizer None → цепочки нет, как сейчас.
3.4. Игроку ничего не показывать (В14а): `boundary_lines` не трогать; видимость — тег `refusal_fallback` в
   `TurnResult.report_tags`/репорте и `SceneSummary.source == "fallback"` (`ChapterSummary.source == "concat"`).

### 4. Docs
`docs/BACKLOG.md` 38 е/ж/к — сделано (ссылка на план и ревью), 45 — строка про `WINDOW`, если поднимали;
`docs/ROADMAP.md` — #11 ✅, «Временные обходы»: обход `~/.config/ai-dm/config.toml` (summarizer на 3.8-flash) снять
**после живого прогона Р2** — руками проектировщика, конфиг пользователя партия не трогает; `docs/HANDOFF.md` — строка
Р2; `docs/ARCHITECTURE.md:439` (бюджеты цикла: «отказ — один автоповтор хода с припиской, затем меню»), E3 (590–594:
«сбой summarizer `refusal`/`invalid` → повтор на модели рассказчика → запасная выжимка; `network`/`fatal` — меню 2.2»),
797 (replay: `summarizer_backup`); `docs/TZ.md:605` — теги `refusal_retry`, `refusal_fallback`. Чек-лист
`checklist-r2-live.md` (не коммитить): (1) мир dusk_academy после снятия обхода — несколько ходов до границы сцены,
граница доходит до конца, в `/report` тег `refusal_fallback` при отказе flash-lite, `scenes[-1].source`; (2) grim-мир,
сцена с насилием на Gemini — при отказе в журнале два вызова под одним run_id, ход прошёл или меню после второго отказа;
(3) 15–20 ходов после развязки/боя — следующая сцена без новой угрозы (темп, субъективно).

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.game.turn:TurnRunner.play_turn ai_dm.game.turn:TurnRunner.attempt ai_dm.game.turn:TurnRunner.failed
  ai_dm.game.turn:TurnRunner.new_session ai_dm.game.turn:TurnRunner.new_summarizer_session` — TESTS
  tests/unit/game/test_game_turn.py tests/unit/game/test_game_refusal_retry.py tests/unit/game/test_game_summarizer_boundary.py
- `ai_dm.master.session:MasterSession.with_note ai_dm.master.session:MasterSession.run` — TESTS
  tests/unit/master/test_master_session_errors.py tests/unit/master/test_master_session_note.py
- `ai_dm.master.summarizer:SummarizerSession.chain ai_dm.master.summarizer:SummarizerSession.try_scene
  ai_dm.master.summarizer:SummarizerSession.try_chapter ai_dm.master.summarizer:soft_failure` — TESTS
  tests/unit/master/test_master_summarizer_chain.py tests/unit/game/test_game_summarizer_boundary.py
- `ai_dm.game.boundary:summarize_scene ai_dm.game.boundary:close_chapter ai_dm.game.boundary:concat_chapter` — TESTS
  tests/unit/game/test_game_summarizer_boundary.py tests/unit/game/test_game_chapter_summary.py tests/unit/game/test_game_boundary.py

## Тесты (kaban-doeba, TDD; параллельно с kaban)

Правка существующих: `test_game_turn.py` — для `REFUSAL` два вызова адаптера (`len(adapter.requests) == 2`), теги
`["refusal", "refusal_retry"]` (порядок — по коду), `test_abort_leaves_bundle_byte_identical` остаётся; `test_three_invalid_
answers_give_error_menu` (summarizer) и invalid-тесты главы (`test_game_chapter_summary.py:187, 426, 515, 532`) — ожидание
меняется на цепочку (бэкап → fallback/concat), рассказчику в риге дать шаги под бэкап; `test_refusal_is_not_retried`
(`MasterSession`) — остаётся; `summ_fail_steps` (fatal) тесты — без изменений; `test_turn_with_world_and_summarizer_
boundary_replays`, `test_replay_of_boundary_*` — зелёные без правок.

Темп (`tests/unit/master/test_narrator_rules_pace.py`, стиль `test_gender_rules.py`): `narrator_rules.md` содержит раздел
«Темп», слова «передышк», «без новой угрозы»; не содержит «одна угроза» (В1б); `world_rules.md` не содержит «передышк».
`tests/scenarios/test_stage4_memory.py` зелёный (при подъёме `WINDOW` — новый порог).

Приписка (`tests/unit/master/test_master_session_note.py`, через `master_kit.make_session(adapter, tmp_path, note=…)`):
- `note=None` → запрос байт-в-байт как раньше (`adapter.requests[0] == ` запрос без note); `note="…"` → блок с текстом есть
  (Q1а: `messages[0].content[1]` — `Text`; Q1б: `system[-1]`), `cache=False`, JSON состояния (`content[0]`) не изменился,
  `player_input` в JSON — строка игрока; при раундах инструментов блок остаётся в `messages[0]` всех последующих запросов.
- `summarizer`/`world`/hero-сессии приписку не получают (их `TurnRunner.note` не касается — проверка на риге ниже).

Автоповтор (`tests/unit/game/test_game_refusal_retry.py`, `game_kit.make_rig/scripted/script_then_react`, образец
`test_game_turn.py:213–290`):
- Исследование: `[{"stop":"refusal"}, text_step("Рассказ.")]` → `committed`, `narration == "Рассказ."`, `report_tags ==
  ["refusal_retry"]`, `len(adapter.requests) == 2`, второй запрос содержит `SOFTEN_NOTE`, первый — нет; `TurnRecord.
  player_input == "Иду"` (приписки нет), `recent_turns` одна запись.
- Два отказа подряд → `committed False`, `failure.reason == "refusal"`, меню `ERROR_MENU`, `REFUSAL_HINT`, теги `refusal` и
  `refusal_retry`, бандл байт-в-байт прежний, `len(requests) == 2` (повтор ровно один).
- Отказ после раунда инструментов (`[tools_step(give_item), {"stop":"refusal"}, text_step("Ок.")]`) → в итоге предмет
  **не** выдан дважды: инвентарь = один предмет из второй попытки, если она его выдаст (`[…, tools_step(give_item),
  text_step]`), или ноль, если не выдаст; `result.requests` — только второй попытки.
- Броски (В9а): `[tools_step(skill_check), {"stop":"refusal"}]` + `[tools_step(skill_check), text_step]` → `world.rng`
  после хода равен rng эталонной риги без отказа (`test_turn_runs_on_copy_original_rng_matches_state` стиль), `rolls`
  одинаковы.
- Другие сбои (`network`, `invalid`, `rounds`, `fatal`) → повтора нет (`len(requests)` как раньше), приписки нет.
- Бой: `script_then_react` — отказ на classify → повтор, ход проходит; отказ на `combat_narrate` при ходе цифрой →
  повтор, лог движка одинаков (те же кубики), `active_combat.round` как без отказа; отказ в npc_choice (`make_engine`)
  → повтор всего хода.
- `self.note` после хода (успех и двойной отказ) == None; следующий ход без приписки.
- Журнал: обе попытки под одним `run_id`, `call_id` `…-1`, `…-2`, статус `committed` у обеих; `attempt` в записях по 1.
- Replay (`test_stage6a_done.py` стиль, `--replay-report`): ход «отказ → успех» → код 0; двойной отказ (aborted) → код 0 с
  той же причиной.
- Авторепорт: на ходе с `refusal_retry` файл в `issues/` появляется (Q3а) — `test_auto_reports.py` стиль.
- Мастер героя/импорт: `{"stop":"refusal"}` по-прежнему один вызов и меню (`test_ui_hero_wizard.py:824`, `test_import_
  session.py:120` без изменений — просто прогнать).

Цепочка summarizer (`tests/unit/master/test_master_summarizer_chain.py` на `SummarizerSession` с двумя `ScriptedAdapter` и
`tests/unit/game/test_game_summarizer_boundary.py`, `make_summ_rig`; summarizer-рига с бэкапом — через
`rig.runner.summarizer_adapter` + рассказчик `scripted(end_narrator() + summ_steps("От рассказчика."))` или
`ReactiveSummarizer`):
- `soft_failure`: `TurnFailed("refusal")`, `("invalid")` → True; `("network")`, `("fatal")`, `("rounds")`, `LlmFatal` → False.
- `chain`: первый ок → `(ctx, False)`, бэкап не вызван; первый refusal, бэкап ок → `(ctx, True)`, у бэкапа один запрос с
  `role == "summarizer"` и `model == модель рассказчика`; оба refusal → `(None, True)`; первый `network` → raise, бэкап не
  вызван; бэкап `fatal` → raise; `backup=None` и refusal → `(None, True)`.
- Сцена: summarizer `[{"stop":"refusal"}]`, рассказчик даёт `scene_summary` → граница завершена, `boundary_pending False`,
  `scenes[0].summary == "От рассказчика."`, `source == "summarizer"`, `result.report_tags` содержит `refusal_fallback`,
  `boundary_failed False`, меню нет, `failed_role None`; журнал: две записи `role summarizer` под одним `bnd-…`, вторая с
  моделью рассказчика.
- Сцена, оба отказали → `scenes[0].summary == fallback_summary` (подсказка нарратора `scene.summary` или «Сцена 1: …»),
  `source == "fallback"`, `title == scene.title`, граница завершена, тик дней и world прошли, новая сцена `scene_2`,
  тег `refusal_fallback` один раз.
- `invalid` ×3 (пустая выжимка — `test_three_invalid_answers…` переписать) → цепочка, не меню.
- `fatal`/`network` summarizer → как раньше: меню, `boundary_pending True`, `failed_role == "summarizer"`, бэкап не вызван.
- Бэкап совпадает с рассказчиком (Q2а: `summarizer_adapter is narrator`, та же модель) → при отказе сразу `fallback`,
  вызовов summarizer ровно один.
- `resume_boundary`: сейв с `boundary_pending True` (как `test_save_and_quit_then_load_finishes_boundary…`), summarizer
  отказывает → достроено через fallback на первом ходу, строка игрока сыграна (не `deferred_input`). Это воспроизведение
  38 к: `test_refusal_summarizer_does_not_block_the_game` — 3 хода подряд при вечно отказывающем summarizer проходят.
- Глава (`test_game_chapter_summary.py`): summarizer сцены ок, глава refusal, рассказчик даёт оба инструмента → `chapters[0].
  source == "summarizer"`, `game_summary` обновлён, тег; глава — оба отказали → `source == "concat"`, `summary` = склейка
  выжимок сцен, `game_summary` прежний, `game_summary_chapter` прежний, новая глава открыта; пустая `chapter_text` от
  первого (`test_empty_chapter_or_game_summary_is_invalid`) → идёт по цепочке.
- `switch_model` после жёсткого сбоя по-прежнему меняет summarizer (`test_switch_model_in_menu_changes_summarizer_not_
  narrator`); после `set_narrator` бэкап строится на новой модели (адаптер из `FactorySpy`).
- Replay: ход с границей «отказ summarizer → бэкап» → `--replay-report` код 0 (`play_report` с `summarizer_backup`);
  `test_replay_of_boundary_with_chapter_gives_same_bundle_memory` стиль — второй прогон на `ReplayAdapter(role=
  "summarizer")` как `summarizer` **и** `summarizer_backup` даёт ту же память.
- `TurnRunner(summarizer_backup=X)` → бэкап использует `X`, модель `self.model`; `GameApp(summarizer_backup=X)` прокидывает.
- Мок (`--mock` + `--mock-summarizer` с refusal, `tests/unit/ui/test_ui_cli.py` стиль) — бэкап берёт шаг из мока
  рассказчика; без `--mock-summarizer` — как сейчас.
- Игроку: `reply.lines` при fallback не содержат слов про выжимку (В14а).

Общее в конце: `uv run pytest -q`, `make cov` (≥ 94 %), `make smells` (≤ 206; ожидание ≤ 203 — новые функции ≤ 5
параметров и ≤ 5 return), `make dead`, `uv run ruff check src tests`; mutmut по списку выше.

## Критерии приёмки
1. Отказ рассказчика в исследовании и бою → один автоповтор на той же модели с припиской, ход проходит, те же броски;
   повторный отказ → меню как раньше. Мастер героя, импорт, summarizer, world — без повтора. `PROHIBITED_CONTENT` — меню
   (критерий «один автоповтор», не «ход не откатывается»).
2. Отказ или невалидный ответ summarizer сцены/главы → повтор на модели рассказчика → запасная выжимка / склейка;
   граница доходит до конца, игра не встаёт; старый сейв с `boundary_pending` достраивается без миграции. `network`/
   `fatal` — меню 2.2 как раньше.
3. Видимость только в репорте (`refusal_retry`, `refusal_fallback`) и в `source` выжимки; игроку строк нет.
4. Replay (`--replay-report`, `--replay`) ходов с повтором и с бэкапом даёт код 0.
5. Правило затишья в `narrator_rules.md`, `world_rules`/`nudge`/пресеты не тронуты; `test_stage4_memory` зелёный.
6. Сейв v9, схема без правок; тесты зелёные, cov ≥ 94 %, smells ≤ 206 (ожидание ≤ 203).

## Оценка
S ≈ 0,6 млн: kaban ~80–110 тыс. (~15 мин: session ~10 строк, turn ~40, summarizer ~35, boundary ~25, app/cli ~10,
правило ~5 строк); kaban-doeba ~220–280 тыс. (~1,5 ч с mutmut: ~45 тестов, ~15 на риге); mama-kaban ~30 тыс.

## Риски / на что обратить внимание
- **`PROHIBITED_CONTENT`/`BLOCKLIST` повтором не лечатся** (риск 1 груминга): ход уйдёт в меню после двух вызовов —
  это ожидаемо; стоимость — один лишний вызов рассказчика (~$0,02).
- **Кэш Gemini при приписке.** `SystemBlock` в повторе = новый ключ кэша → пересоздание (и удаление прежнего) на
  повторе и ещё раз на следующем ходу; Q1а (блок в user-сообщении) этого избегает. Anthropic — префикс не ломается
  ни в одном варианте.
- **Бэкап summarizer тянет шаги мока рассказчика** в `--mock`/ригах — в тестах с мягким сбоем summarizer давать
  рассказчику шаги; иначе `ScriptExhausted` (не `TurnFailed`) уронит ход исключением.
- **Replay старых репортов** не меняется (отказов summarizer в `tests/fixtures`/`golden` нет; у dusk_academy ход 48 —
  aborted-граница, репорта нет). Новые репорты с бэкапом воспроизводятся только с `summarizer_backup` в `play_report`.
- **Бэкап на модели рассказчика дороже** flash-lite (3.8-flash/pro ~×5–10 за выжимку) — только при отказе, редко.
- **`invalid` в цепочке** — три невалидных ответа flash-lite + бэкап = до 4 вызовов на границе; принято В11а.
- **Запасная выжимка беднее** (риск 4): «Сцена N: место, дата» — память о сцене неполная; видно по `source`.
- **Smells 200/206.** `play_turn` с повтором — следить за сложностью (вынос `attempt`/`retry_result`); `chain` —
  одна функция на обе роли; `close_chapter` — ≤ 5 return через `concat_chapter`. Лимит не поднимать.
- **WINDOW мока** — запас ≈ 800 символов; правило ≤ 400 символов — подъём не нужен; если понадобится — 5-й подъём,
  записать в BACKLOG 45.
- **Правило затишья проверяется только живым прогоном** (15–20 ходов после развязки) — чек-лист п. 3; с grim/героикой
  может «бледнить» повторный ход (приписка) — цена, не баг.
- **Обход `~/.config/ai-dm/config.toml`** (summarizer на 3.8-flash, ROADMAP:50) снять после живого прогона Р2 —
  проектировщик руками; партия конфиг не трогает.
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS.

## Открытые вопросы
- **Q1 Куда класть приписку (В7а «в системную часть»).** (а) **рекомендация** — отдельный `Text`-блок после JSON
  состояния в user-сообщении запроса (`messages[0].content[1]`): в `player_input` и `TurnRecord` не попадает, явный кэш
  Gemini (ключ = все блоки system) не пересоздаётся, Anthropic-префикс цел; (б) буквально `SystemBlock` в конец
  `system` — чище по смыслу, но два пересоздания кэша Gemini (~20 тыс. токенов записи ×2) на каждый отказ.
- **Q2 Бэкап summarizer, когда он уже на модели рассказчика** (после `switch_model` или в профиле). (а) **рекомендация**
  — бэкап не строить: тот же вход на той же модели только что отказал, сразу `fallback_summary`; (б) всё равно один
  повтор на той же модели (как у рассказчика) — ещё один вызов ради шанса на недетерминизм.
- **Q3 Авторепорт на успешном ходе с `refusal_retry`/`refusal_fallback`.** `GameApp` пишет репорт на любой тег
  (`app.py:232`). (а) **рекомендация** — да, как `missing-mechanic`: отказ — сигнал для правки тона/правил, В14а
  «видимость в репорте»; (б) не писать — нужен белый список тегов авторепорта (новый механизм), тег только в `/report`.
- **Q4 Текст приписки.** (а) **рекомендация** — «Системная приписка: опиши эту сцену сдержанно, без натурализма.»
  (по В5а, одна строка, без «это вымысел» — такие фразы у Gemini иногда усиливают фильтр); (б) добавить «насилие и
  откровенность — за кадром или намёком» — мягче, но сильнее меняет тон повторного хода.

## Решения проектировщика (2026-10-13)
- Q1 — (а) отдельный блок после JSON состояния в user-сообщении.
- Q2 — (а) бэкап не строить, сразу `fallback_summary`.
- Q3 — (а) авторепорт писать.
- Q4 — **(б)** (не по рекомендации): `SOFTEN_NOTE` = «Системная приписка: опиши эту сцену сдержанно, без натурализма;
  насилие и откровенность — за кадром или намёком.»

## Решения: Груминг партии Р2 — «Темп и отказы» (свинопас, 2026-10-13) (бывш. docs/decisions/r2-grooming.md)

Источники: roadmap-r5-proposal «Р2 Темп и отказы — #11» и риск 3; BACKLOG 38 е, ж, к; local-llm-research §6–7;
ROADMAP (#11, S ≈ 0,6 млн, сейв v9); handoff (роли, правила); k0-fix-a-review (safety_settings). Код на 8d955a3:
`game/turn.py`, `game/boundary.py`, `game/app.py`, `master/session.py`, `master/prompt.py`, `master/summarizer.py`,
`world_sim/nudge.py`, `campaign/presets.py`, `campaign/presets.yaml`, `campaign/build.py`, `state/world.py`,
`state/memory.py`, `llm/gemini_adapter.py`, `llm/anthropic_adapter.py`, `llm/retry.py`, `config/app_defaults.toml`,
журнал мира `saves/dusk_academy-d3de6c57/journal`.

### Груминг

#### Готовность

**Не готова к плану до ответов на В1, В2, В5, В8** (блокирующие). Остальные можно закрыть по рекомендации.
Два расхождения документов с кодом:
- роадмап: «темп как поле пресета без поля сейва — пресет уже хранится по `preset_id`». В коде `preset_id` в сейве нет:
  тон пресета копируется в `world.tone` при создании мира (факт 7). Поле `pace` = изменение схемы сейва;
- BACKLOG 38 к: «ход откатан». В коде ход закоммичен, падает граница сцены; дальше игра стоит на `boundary_pending`
  (факт 3). Суть боли та же, точка правки другая.

#### Что есть в коде (факты)

1. **Отказ рассказчика.** `MasterSession.run` на `stop_reason == "refusal"` сразу бросает `TurnFailed("refusal")`
   (`master/session.py:260–262`). Повтора на отказ нет: `call_with_retries` повторяет только `LlmTransient`
   (`llm/retry.py`). Ход идёт на копии и выбрасывается (`game/turn.py:187–199`), игроку — `REFUSAL_HINT` и меню
   `retry / switch_model / save_and_quit` (`turn.py:21–24, 207–216`).
2. **Ручной фолбэк уже есть.** `switch_model` в меню ошибки меняет рассказчика (или summarizer, если упал он —
   `failed_role`) на сессию (`game/app.py:356–363, 474–520`); кандидаты — `roles.narrator`, `alternatives.narrator`
   (claude-sonnet-5-5) и профили (`game/app.py:71–72`, `app_defaults.toml:23–27`). Автоматического фолбэка нет.
   У Anthropic есть серверный фолбэк `refusal_fallback` (`anthropic_adapter.py:124–126`, по умолчанию `false`),
   у Gemini — `gemini_safety = "block_none"` (К0-фикс, `app_defaults.toml:113`, `gemini_adapter.py:134–147`).
   `PROHIBITED_CONTENT` и `BLOCKLIST` отображаются в `refusal` и настройками не снимаются (`gemini_adapter.py:13–15`).
3. **Отказ summarizer (38 к) по журналу.** dusk_academy, turn 48: пять вызовов flash-lite по одной попытке
   (`bnd-…-11…15`), `stop_reason: refusal`, `input 6102`, `output 0`, `stop_detail` пуст (до К0-фикса). Путь:
   `summarize_scene` пробрасывает `TurnFailed` (`boundary.py:72–76`) → `finish_boundary` ловит, бандл не меняется,
   `boundary_pending` остаётся (`boundary.py:189–216`) → каждый следующий ход сначала `resume_boundary`; сбой →
   строка игрока откладывается в `deferred_input`, ход `aborted` (`turn.py:182–185`). Игра встаёт.
4. **Запасная выжимка уже есть.** `fallback_summary` (`boundary.py:49–56`) — `scene.summary` нарратора или строка
   «Сцена N: место, дата»; сейчас вызывается только при `summarizer is None`. `SceneSummary.source` уже допускает
   `"fallback"` и `"narrator"` (`state/memory.py:38`); у главы — склейка `"concat"` без обновления `game_summary`
   (`boundary.py:137–141`, `memory.py:47`). Новые значения перечислений не нужны.
5. **Отказ world роняет границу так же.** `call_world` исключения не ловит (`boundary.py:104–125`), `finish_boundary`
   ловит любой `TurnFailed/LlmError` (`boundary.py:210`). В 38 к этого случая нет, но точка та же.
6. **Темп в правилах.** В `narrator_rules.md` и `world_rules.md` о темпе, затишье, числе угроз — ничего. Есть только
   сигнал `nudge` (`narrator_rules.md:72`). `narrator_rules.md` — 30,7 тыс. символов, кэшируемая часть (`prompt.py:194`);
   BACKLOG 45: `WINDOW` мока поднимали 4 раза подряд.
7. **Пресет не хранится.** `apply_preset` копирует `preset.tone` в тон мира при сборке (`campaign/presets.py:42–50`,
   `campaign/build.py:133`); в сейве — `world.tone` (`state/world.py:16–27`, `extra="forbid"`), поля `pace` нет,
   `preset_id` нет. В промпт уходит `world.tone` целиком (`prompt.py:236`). Значит: текст темпа в `tone.notes` пресета
   получат только новые миры; поле `Tone.pace` — новое поле сейва.
8. **Подталкивание.** `nudge.step` на каждой границе сцены: нет касания основной линии → `scenes_off_main += 1`,
   стадия = `min(3, scenes_off_main // nudge_scenes)` (`world_sim/nudge.py` step/apply_stage): 1 — слух, 2 — контакт
   NPC (сигнал рассказчику), 3 — событие через world. Ни один пак `nudge` не задаёт (`campaigns/*/campaign.yaml`) —
   везде 8 (`campaign/models.py:62`, `state/world.py:287`). Стадия 1 — не раньше 8 сцен без касания, 3 — 24.
   Линия есть, только если есть активные `key`-триггеры.
9. Признака «сцена затишья» в состоянии нет. Конец боя виден как `combat_ended` при закрытии сцены и `last_combat`.
10. smells 200/206 (handoff, Ф1); тестов на `refusal` — `tests/unit/llm/test_llm_gemini_safety.py` и сессии мастера.

#### Суть

Три правки. Темп: рассказчик даёт передышку после развязки и не взводит угрозы пачкой. Отказ рассказчика: ход не
теряется молча — автоматическая попытка ещё раз. Отказ summarizer: граница сцены доходит до конца, игра не встаёт.
Сейв v9, без новых полей.

#### Точки входа

1. Отказ рассказчика в ходе исследования (`turn.py:374`).
2. Отказ в бою: классификация и рассказ (`turn.py:423, 460`) — два разных режима.
3. Отказ после части раундов инструментов (запросы уже применены к копии) — повтор только с новой копии.
4. Отказ summarizer сцены — на обычной границе (`turn.py:252`) и при `resume_boundary` (`turn.py:259–266`, `retry`).
5. Отказ summarizer главы (`boundary.py:146–153`) — там же пустой ответ даёт `TurnFailed("invalid")`.
6. Отказ world на границе (факт 5).
7. Старые сейвы, застрявшие в `boundary_pending` (dusk_academy) — достраиваются через `resume_boundary`, правка
   их покроет без миграции.
8. Мастер героя и импорт (`ui/hero_wizard.py:206`, `ui/import_session.py:38`) — тоже ловят `TurnFailed`.
9. Replay и `/report`: повтор = лишние вызовы в журнале; мок должен отыграть «отказ → успех».
10. Темп: каждый ход рассказчика (правило), граница сцены (`nudge`), вердикты world (`world_rules.md`).
11. Обход в `~/.config/ai-dm/config.toml` (summarizer на 3.8-flash) — снять после Р2 (ROADMAP:50).

#### Вопросы проектировщику (рекомендация первой)

Темп (38 е)

- **В1 [блок.] Какие правила темпа.** **(а) два правила в `narrator_rules.md`: затишье — после развязки линии или
  боя одна сцена без новой угрозы (быт, разговоры, исследование); не вводить новую угрозу, пока текущая не закрыта**;
  (б) только затишье; (в) (а) + абзац в `world_rules.md` (см. В4).
- **В2 [блок.] Темп как настройка пресета.** Факт 7: без поля сейва нельзя. **(а) в Р2 не делать — правила общие
  для всех миров**; (б) фраза о темпе в `tone.notes` пресетов — только новые миры, старые без неё; (в) поле
  `Tone.pace` — новое поле сейва, это v10 и вне условия партии.
- **В3 Затишье против подталкивания (риск 3 роадмапа).** Факт 8: подталкивание считает сцены, стадии раз в 8 сцен.
  **(а) затишье — одна сцена, `nudge` не трогаем**; слух стадии 1 в затишье допустим как фон; (б) не повышать стадию
  на сцене затишья — нужен признак затишья в состоянии (факт 9), это поле сейва.
- **В4 Правило для world.** world решает вердикты триггеров, структурные (`act`) сработают всё равно.
  **(а) только рассказчик**; (б) и в `world_rules.md`: «не давать новой угрозы, пока у героя открыта текущая» — влияет
  только на нарративные вердикты.

Отказ рассказчика (38 ж)

- **В5 [блок.] Механизм.** **(а) один автоматический повтор хода на той же модели с системной припиской «опиши
  сдержанно, без натурализма»; не помог — меню как сейчас (там уже есть ручная смена модели, факт 2)**;
  (б) автофолбэк на `alternatives.narrator` (Claude) при отказе — нужен ключ Anthropic, без ключа (б) не работает;
  (в) повтор, затем автофолбэк. Цена (а) — ещё один вызов только при отказе (~$0,02).
- **В6 Где повторять.** Факт 1 и точка 3. **(а) весь ход заново с новой копии бандла** (запросы первой попытки не
  остаются); (б) повтор только последнего вызова внутри `MasterSession.run` — часть инструментов уже применена.
- **В7 Куда приписка.** **(а) в системную часть только этого запроса; в `TurnRecord.player_input` не попадает**;
  (б) дописать к строке игрока.
- **В8 [блок.] Какие режимы.** **(а) только ход рассказчика: исследование и бой (точки 1–2)**; мастер героя и импорт —
  как сейчас; (б) все режимы рассказчика.
- **В9 Новый бросок при повторе.** Повтор с новой копии берёт то же состояние ГСЧ. **(а) те же броски — детерминизм
  replay**; (б) не важно.

Отказ summarizer и world (38 к)

- **В10 [блок.] Что делать при отказе summarizer сцены.** **(а) повтор на модели рассказчика (обход Влада это и
  делает), отказ снова — `fallback_summary` (факт 4), граница доходит до конца**; (б) сразу `fallback_summary`;
  (в) пропустить выжимку сцены — память беднеет без следа.
- **В11 На что срабатывает.** **(а) отказ и пустой/невалидный ответ (`refusal`, `invalid`); сеть (`network`) — как
  сейчас, через меню**; (б) любой сбой summarizer.
- **В12 Глава.** **(а) та же цепочка; последний шаг — склейка `concat`, `game_summary` не обновляется**; (б) главу не
  трогать.
- **В13 Отказ world** (факт 5, в бэклоге нет). **(а) пропустить вызов world на этой границе, кандидаты уйдут на
  следующую; пометка в репорте**; (б) не трогать в Р2 — отдельный пункт бэклога.
- **В14 Видимость.** **(а) тег в репорте (`refusal_fallback`) и `source` выжимки; игроку ничего не показывать**;
  (б) строка игроку «выжимка сцены упрощена».

#### Оценка

**S ≈ 0,6 млн при В1а, В2а, В3а, В4а, В5а, В6а, В8а, В10а** — как в роадмапе. Два правила в `narrator_rules.md`;
повтор хода при отказе в `play_turn`; цепочка «модель рассказчика → запасная выжимка» в `summarize_scene` и
`close_chapter`; тесты: отказ в исследовании и бою, отказ после раунда инструментов, отказ summarizer на обычной
границе и в `resume_boundary`, глава, replay «отказ → успех», пересчёт `WINDOW` мока.
Сдвиги: В5б/в или В13а — S+ (≈ 0,8); В2в — M и сейв v10, отдельной партией.

#### Риски

1. **`PROHIBITED_CONTENT` повтором не лечится** (риск 4 роадмапа): откровенность на grim всё равно упирается
   в провайдера; Р2 возвращает ход в меню, а не гарантирует сцену.
2. **Мягкая приписка меняет тон** только в повторном ходе — сцена на grim может выйти бледнее; это цена, не баг.
3. **Бюджет промпта** (BACKLOG 45): два правила добавят токены в кэшируемую часть, `WINDOW` мока растёт в 5-й раз.
4. **Запасная выжимка беднее** — summarizer главы потом склеит строки «Сцена N: место»; потеря памяти на отказной
   сцене. Называю явно: игра идёт, память о сцене неполная.
5. Правило затишья — промпт, проверяется только живым прогоном (15–20 ходов после развязки).
6. smells 200/206 — запас 6.

#### Можно делать сейчас, не дожидаясь ответов

Мок «отказ → успех» для summarizer и рассказчика; тест, воспроизводящий 38 к (отказ summarizer → `boundary_pending`
навсегда); замер `make smells` и `WINDOW`. Снять обход в `~/.config` — после прогона Р2, не раньше.

Решения за проектировщика, молча не принятые: набор правил темпа (В1), поле темпа (В2), механизм повтора (В5),
режимы (В8), поведение при отказе summarizer (В10).

### Аудит

Кабан-свекровь, 2026-10-13 (вписано оркестратором — у аудитора нет Edit). Сверка: roadmap-r5-proposal (Р2, риски 3–4),
BACKLOG 38 е/ж/к, ROADMAP:23,50, код HEAD 8d955a3, журнал saves/dusk_academy-d3de6c57 (только чтение).

| Находка | Где | Вердикт |
|---|---|---|
| preset_id в сейве нет → `pace` = v10 (роадмап ошибается) | факт 7, В2 | подтверждено кодом — оставить |
| Ход 48 не откатан, падает граница сцены (refusal ×5, `boundary_pending` → `deferred_input`) | факт 3 | подтверждено журналом; формулировка BACKLOG 38 к неточна — оставить |
| Отказ world роняет границу (`call_world` не ловит) | факт 5 | подтверждено — оставить |
| file:line | факты 1–5 | расхождение ≤ 1–2 строк — оставить |
| В13 отказ world | вопросы | расширение объёма сверх 38 к/роадмапа; по умолчанию разумнее В13б (отдельный пункт BACKLOG) — к проектировщику |
| В5а против ROADMAP:23 «запасной рассказчик» | В5 | к проектировщику: явно подтвердить отказ от автофолбэка |
| Критерий прогона «ход не откатывается» | В5а, риск 1 | при `PROHIBITED_CONTENT` ход всё равно уходит в меню — принять ослабление до «один автоповтор» |
| «Можно делать сейчас» | конец груминга | только тесты и моки, без правок продукта до плана |

Решений за проектировщика молча не принято. Блокирующие В1, В2, В5, В8, В10 выбраны обоснованно; В6 и В9 закрываются
вместе (новая копия бандла → те же броски). Оценка S ≈ 0,6 реалистична; риск — запас smells 6, пятый подъём `WINDOW` мока.
Итог: факты верны, объём не раздут. Нужны решения по В1, В2, В5 (+ отказ от запасного рассказчика), В8, В10, В13.
Расход ~25 тыс.

### Решения проектировщика

2026-10-13, интерактивно:
- **В1 — (б) только затишье** (не по рекомендации): после развязки линии или боя одна сцена без новой угрозы. Правила
  «одна угроза за раз» нет; В4 — соответственно (а), в `world_rules.md` ничего.
- **В2 — (а)** в Р2 не делать.
- **В5 — (а)** один автоповтор с припиской, затем меню. Запасной рассказчик из ROADMAP:23 отменён; критерий прогона —
  «один автоповтор», а не «ход не откатывается» (при `PROHIBITED_CONTENT` — меню).
- **В8 — (а)** только исследование и бой.
- **В10 — (а)** повтор на модели рассказчика, затем `fallback_summary`.
- **В13 — (б)** не в Р2 → BACKLOG 46.
- В3, В6, В7, В9, В11, В12, В14 — по рекомендации (а), как предложено оркестратором.

## Правки по ревью: Ревью партии Р2 «Темп и отказы» (мама-кабан, 2026-10-13) (бывш. docs/decisions/r2-review.md)

Вписано оркестратором (у ревьюера нет Write). План docs/plan-r2.md, груминг docs/plan-r2.md.
Тесты: 14068 passed, 1 xfailed, 1 failed (ожидаемый `test_game_refusal_retry_calls.py`).

### Сделано по плану
- Повтор хода (`turn.py: run/attempt/retry_result`): новая глубокая копия бандла на попытку, броски из копии
  (`Rng.from_state`), `self.note` сбрасывается в `finally`; `time_before_s` снимается до первой попытки.
- Q1а: `with_note` — второй `Text` в `messages[0].content`; при `note=None` запрос прежний.
- Q2а: бэкап не строится, если summarizer = рассказчик.
- Summarizer: к запасному только `refusal`/`invalid`; `failed_role` — только при жёстком сбое; `concat` без
  обновления `game_summary`.
- Replay: `summarizer_backup` в `play_report` и на старте с `--replay`.
- Новые тесты не пустые (83 в новых файлах).

### Замечания
1. **(блокер)** `turn.py: new_session` не передаёт `call_numbers` → обе попытки пишут один `call_id`; план п. 2.5 —
   сквозная нумерация. Передать `call_numbers=self.call_numbers`, проверив, что нумерация обычных ходов не сдвинется;
   иначе — отдельный словарь на ход в `run`.
2. `turn.py: attempt` — лишний `except TurnFailed: raise`, удалить.
3. Порядок тегов при двойном отказе `["refusal_retry","refusal"]` — допустимо по плану; тест фиксирует порядок,
   формулировку TZ:605 привести в соответствие.
4. `summarizer.py: try_scene` — `summary_text is not None` пропускает `""`; глава — `bool(...)`. Согласовать
   (`bool`) и добавить тест на пустой текст.
5. `SOFTEN_NOTE` длиннее плана п. 2.2 — это решение проектировщика Q4б, правка не нужна; тесты — по константе.
6. `turn.py: new_summarizer_session` — путающий комментарий про Q2, переписать.
7. Тег `refusal_fallback` ставится и при `invalid` (по В11а/В14а) — отметить в TZ.
8. WINDOW мока 24000→24500 (пятый подъём, блок «Темп») — дописать в BACKLOG 45.

Исход (kaban): 1 ✅ (`call_numbers` в `new_session`, `pop` в `mark_journal`); 2 — **отклонено**: `TurnFailed` — подкласс
`Exception`, без ветки первая попытка ловится `except Exception` и ход помечается `aborted` до повтора (падали тесты
журнала); 3, 7 ✅ TZ; 4 ✅ `bool(...)`; 6 ✅; 8 ✅ BACKLOG 45.

Вердикт: обязательно 1, 2; желательно 4, 6; остальное — документы.
Расход ~37 тыс.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **Р2 груминг+аудит ✅ 2026-10-13** — docs/plan-r2.md (В1–В14; блок. В1, В2, В5, В8, В10 + В13 по аудиту). Решения приняты (В1б — только затишье, не по рекомендации; В13 → BACKLOG 46; остальное по рекомендациям). План papa-kaban ✅ docs/plan-r2.md (~150 тыс.); Q1–Q3 по рекомендации, Q4б (приписка с «за кадром или намёком»); ждём «окей, кабаним». Расход: svinopas ~73 тыс., svekrov ~25 тыс.
- **Р2 «Темп и отказы»:** код kaban ✅ 2026-10-13 (narrator_rules «Темп», TurnRunner.attempt/retry_result/SOFTEN_NOTE, MasterSession.note, SummarizerSession.chain/backup, boundary.concat_chapter, summarizer_backup в GameApp/cli). Тесты kaban-doeba и ревью — дальше; живой прогон — checklist-r2-live.md (папа/оркестратор).
- **Р2 ✅ закоммичена 2026-10-13:** тесты 14072 passed, cov 97 %, smells 200/206, mutmut — выжившие только эквивалентные/старый код. Ревью docs/plan-r2.md (п.2 «лишний except TurnFailed» отклонён — ветка нужна). WINDOW мока 24000→24500 (5-й подъём, BACKLOG 45). Расход: kaban ~66+78 тыс., doeba ~243+248 тыс., mama ~25 тыс., papa ~174 тыс. Дальше — живой прогон Р1+Ф1+Р2 у проектировщика по единому чек-листу checklist-r1-f1-r2-live.md (три прежних объединены 2026-10-13; обход summarizer в ~/.config/ai-dm/config.toml снимается в его п.12); затем К1 (груминг).
