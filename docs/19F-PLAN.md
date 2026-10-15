# План партии 19ф «Фикс ЖП1» (papa-kaban, 2026-10-16; на аппрув проектировщика)

Задача: находки живого прогона ЖП1 — Ф1 (меню ошибки через 4,5 мин при 503/504/таймауте), Ф2 (а: «начинается бой!» без
`start_combat`; б: ход, которым бой закончился, кончается вопросом без меню), Ф4 (отладочный старт боя с заданным составом).
Ф3 → ТМ (#20), не трогаем. Груминга нет (R5 для фиксов). Сейв v9 без изменений (новых полей состояния нет). Smells 200/200 —
нулевой баланс. Оценка ≈ 0,4 млн (ROADMAP 19ф). Источники: docs/decisions/zhp1-findings.md, docs/T60-PLAN.md §10,
docs/TV-PLAN.md, docs/decisions/tv-review.md, saves/vale-cd40a140 (journal/calls-001.jsonl, attempts.log — только чтение).

## 0. Что показали журнал и код (офлайн-проверка гипотез)

**Ф1 — ход 23 vale** (attempts.log + calls-001.jsonl, `run-20261015T163810-bdcaa3-25`): старт 17:06:30; попытка 1 — read timeout
92 с («The read operation timed out», код None → `is_network_error` → `LlmTransient`); попытка 2 — 504 DEADLINE_EXCEEDED 90 с;
попытка 3 — 504 89 с; попытка 4 — 503 за 3 с; меню в 17:11:18 → **4 мин 48 с**, из них паузы `delays=[1,3,10]` — 14 с, остальное —
три ожидания по ~90 с (`gemini_timeout_s`). Ход 25 (`run-…-ecb3e6-1`): 503, 503, таймаут 100 с, 503 — 2 мин. Ход 0: 503 ×3 + 504 —
ровно 4 попытки, 1 мин. Вывод: время до меню делают не повторы как таковые, а **повторы после таймаута/504** (каждый — ещё 90 с);
503 отбивается за секунды и повторять его дёшево. Ни разу после 504/таймаута ход на той же модели не прошёл.
Код: `llm/retry.py call_with_retries` различает только transient/fatal; `LlmTransient` не знает, был ли это таймаут;
`RetryConfig` (config/app.py:53) — `delays`, `chain_delays`, `gemini_timeout_s`. Политика рассказчика — полные `delays` (Q3(б) Т60).

**Ф2а — ход 5 vale** (`run-…-7-1`, flash-lite, explore): один ответ текстом, вызовов нет, последняя строка «*(В этот момент
начинается бой!)*» — не вопрос и не список → `ends_with_choice` False, `CHOICES_ASK` не сработала; бой начался на ходу 6 по
`start_combat`. Скрипт по всем журналам `saves/*/journal/calls-*.jsonl`: 321 explore-прогон рассказчика, фраза
«начинается бой / бой начался / в бой!» в тексте — 3, из них **без `start_combat` — 1** (этот). Частота ≈ 0,3 %.
Правило «Бой» (`narrator_rules.md:26`) говорит «Начинай бой через `start_combat`», но не говорит «в этом же ходу, где бой
начинается по тексту».

**Ф2б — ходы 9–10 vale.** Ход 9 (`run-…-11-1`, `combat_narrate`, бой идёт, `outcome: null`) кончается «Что ты будешь делать
дальше?» — меню действий даёт движок, приписка не нужна (по плану ТВ). Ход 10 (`run-…-12-1`, `combat_narrate`,
`combat.outcome: "victory"`, `options: []`) кончается «Что ты делаешь дальше?» без `offer_choices` → после `end_fight`
`active_combat = None`, `offered_choices` пуст → экран без меню (`ui/screen.py screen_blocks`). **По коду подтверждено:**
`MasterSession.choices_missing` (master/session.py:289) требует `mode == "explore"` и `active_combat is None`; в
`combat_narrate` проверка не идёт никогда. При этом `offer_choices` в наборе `combat_narrate` есть
(`protocol/schema.py MODE_TOOLS["combat_narrate"] = ("offer_choices", "end_combat", "defeat_outcome")`, ход 8 журнала это
же показывает), исполнитель `narrate_combat` — `self.recording(result, apply)`, тот же `run_round` исполнит `offer_choices`,
`offered_choices` ляжет в `bundle.session`, `TurnRecord.requests` получит `offer_choices` → `ui/session.py offer_is_stale`
False → меню на экране. Правило «Выбор игроку» (`narrator_rules.md:108`) кончается «в бою список действий даёт движок» — на
ходу победы модель этому и следует.

**Ф4.** `protocol/handlers/combat.py start_combat(ctx, request)` принимает `StartCombat` (зоны 2–5, `EnemySpec`, `GroupSpec`,
`hero_zone`, `initiated_by`), сам проверяет монстров по `registry.ids("monster")`, режет сверх `limits.max_enemies = 6` и сверх
бюджета — кроме `override_reason` (`rules/encounter.py:57`: `warn_danger` / `initiated_by == "hero"` / `kills_hero`). После
принятого `start_combat` ход делает `combat_flow.start_fight(ctx, session, run_id, world_text)` (инициатива, ходы врагов до
героя); `session` нужен только `MasterChoiceController` ключевых NPC (`controller == "external"`), у монстров из реестра его нет.
Команды — `game/commands.py COMMANDS` + `HELP`; `/tone`, `/difficulty` правят `app.bundle` на месте. После команды экран
(карта и меню боя) перерисовывается только для `/load` (`ui/session.py PlaySession.render_step`:
`if not line.startswith("/") or line.startswith("/load")`). Монстры SRD: goblin_warrior, goblin_boss, skeleton, zombie, ghoul,
ghast, shadow, specter, wight, wolf, dire_wolf, giant_rat, swarm_of_rats, giant_spider, dust_mephit, steam_mephit, magmin,
ogre_zombie, guard и др. (`src/ai_dm/srd/data/monsters/`).

## 1. Решения (архитектура)

### Ф1 — меню после первого таймаута/504 (Q1, рек. (а))
1. `llm/errors.py`: `LlmTransient(message, retry_after=None, timeout=False)` → атрибут `timeout` («медленная» ошибка: ответ
   не пришёл за таймаут или сервер отдал 504). `TIMEOUT_NAMES = {"ReadTimeout", "WriteTimeout", "ConnectTimeout",
   "PoolTimeout", "TimeoutException", "APITimeoutError", "TimeoutError"}` и `is_timeout_error(error)` — по MRO, как
   `is_network_error` (httpx.ReadTimeout → TimeoutException → TransportError: в `NETWORK_NAMES` уже есть, значит ход 23
   прошёл этой веткой). `RetriesExhausted.__init__`: `timeout` берётся у `last`; текст при таймауте —
   «ответ не пришёл вовремя (таймаут или 504; вызовов: N): …», иначе как сейчас (это `hint` меню ошибки через
   `TurnFailed("network", str(error))` → `TurnRunner.failed`).
2. `llm/gemini_adapter.py GeminiAdapter.translate_error`: ветка `code is None` → `LlmTransient(text,
   timeout=is_timeout_error(error))`; ветка `code in (408, 429) or code >= 500` → `timeout=(code == 504)`.
   `llm/anthropic_adapter.py AnthropicAdapter.translate_error` — то же (`retry_after` сохраняется).
3. `config/app.py RetryConfig.retry_timeouts: bool = False`; `config/app_defaults.toml [retry] retry_timeouts = false`
   с комментарием («повторять ли после таймаута/504: false — первый такой сбой сразу в меню ошибки; 503/429/5xx — по
   delays»).
4. `llm/retry.py call_with_retries`: сдаться, если `attempt > len(policy.delays)` **или** `error.timeout and not
   policy.retry_timeouts` — вынести в `give_up(policy, attempt, error) -> bool` (новая, ≤ 3 условий; защищает
   `call_with_retries` от «high complexity»). Паузы, `retry_after`, `on_attempt`/`on_start` не меняются. Действует на все
   роли (world, summarizer, рассказчик, hero-сессии): у primary summarizer с backup `chain_delays=[]` и так одна попытка.
5. Журнал и воспроизведение: `llm/journal.py Journal.record_call` — в `error_dump` ключ `"timeout": getattr(error,
   "timeout", False)`; `llm/replay.py ReplayAdapter.complete` — `LlmTransient(..., timeout=error.get("timeout", False))`
   (старые журналы без ключа → False → реплей старых ходов не меняется); `llm/mock.py`: `STEP_KEYS` + `"timeout"`,
   `ScriptedAdapter.complete` → `LlmTransient(message, retry_after=…, timeout=bool(step.get("timeout", False)))`
   (для тестов и YAML-сценариев).
6. Итог по времени: таймаут → меню через ≈ `gemini_timeout_s` (92 с вместо 288); 504 → ≈ 90 с; 503 ×3 + 504 (ход 0) —
   как было (4-я попытка и так последняя); 503 ×4 — как было (≈ 30 с). Авто-переключения нет (Q3(б) Т60 в силе): игрок
   видит меню, первой в нём — следующая модель цепочки.
7. Доки: ARCHITECTURE.md раздел C4/E3 (абзац «рассказчик повторяет по полным `retry.delays`») — дописать исключение по
   `retry_timeouts`; `docs/llm-notes/gemini-facts.md` — строка про 504 DEADLINE_EXCEEDED как «медленный» сбой (если файла
   нет — не создавать).

### Ф2а — правило + тег без служебного вызова (Q2, рек. (б))
1. `master/prompts/narrator_rules.md`, раздел «Бой» (стр. 26), после «Начинай бой через `start_combat`.» одна фраза:
   «Если по твоему рассказу бой начинается (враг нападает, бросается, обнажает оружие), вызови `start_combat` в этом же
   ходу, а сцену пиши после результата движка; фраза «начинается бой» текстом без вызова — ошибка: бой не начнётся и
   игрок не получит действий.» Меняет `system_sha256` — реплеи старых ходов рассказчика расходятся (прецедент B59 В1/ТВ,
   принято).
2. `master/session.py`: `COMBAT_ANNOUNCED = re.compile(r"\b(?:начинается|начался|начнётся|идёт)\s+бой\b|\bбой\s+(?:начинается|начался)\b|\bк бою!|\bв бой!", re.I)`
   и `announces_combat(narration) -> bool` (новая, уровня модуля, рядом с `ends_with_choice`): проверяет **последний абзац**
   (как `ends_with_choice`). `MasterSession.tag_missing_combat(ctx, result, mode)` (новая): `role == "narrator"`,
   `mode == "explore"`, `active_combat is None`, `"start_combat" not in result.accepted`, `announces_combat` →
   `result.report_tags.append("combat_announced")`. Точка вызова — `run`, ветка `if note is None:` рядом с
   `choices_missing` (одна строка в уже помеченном `run`). Тег → `TurnRunner.take_master_tags` → `GameApp.auto_report`
   (любой тег → репорт) — ЖП2 измерит частоту; служебного вызова и повтора хода нет (1 случай на 321 ход — приписка
   с конструированием `start_combat` слабой моделью не окупается, см. Q2(в)).

### Ф2б — приписка на ходу, которым бой закончился (Q3, рек. (а))
1. `master/session.py`: `COMBAT_OVER = ("victory", "fled", "ended_by_master")` (исходы, после которых герой жив и сцена
   идёт дальше; `hero_dying`/`defeat_pending`/`hero_dead` — нет: там обязателен `defeat_outcome` или меню смерти).
   `MasterSession.choices_missing(ctx, result, mode)` переписать (2 return, без роста smells):
   ```
   if self.role != "narrator" or "offer_choices" in result.accepted: return False
   combat = ctx.bundle.session.active_combat
   if mode == "explore": over = combat is None
   else: over = mode == "combat_narrate" and combat is not None and combat.outcome in COMBAT_OVER
   return over and ends_with_choice(result.narration)
   ```
   `ask_choices` без изменений: `run_round(ctx, [call], executor, result, mode)` с `mode="combat_narrate"` исполняет
   `offer_choices` (он в наборе режима), исполнитель — `recording(result, apply)` из `narrate_combat` → `offered_choices`
   в бандле, `offer_choices` в `result.requests` → `TurnRecord.requests` → `offer_is_stale` False → `screen_blocks`
   рисует меню после `end_fight`. Путь «герой упал до первого решения» в `explore_turn` (narrate внутри того же хода) —
   тот же код. Ход в бою с `outcome None` — как раньше, без приписки.
2. Правила: абзац «Рассказ о бое (режим combat_narrate)» (`narrator_rules.md:38`) + фраза: «Если по логу бой закончился
   (победа, враги бежали, бой завершён), ход кончается как вне боя: вопрос игроку или развилка — вызови `offer_choices`.»
   В «Выбор игроку» (стр. 108) хвост «в бою список действий даёт движок» → «пока бой идёт, список действий даёт движок;
   на ходу, которым бой закончился, варианты снова за тобой».
3. ARCHITECTURE.md:475 (абзац `CHOICES_ASK`): «рассказ explore вне боя» → «рассказ explore вне боя **или `combat_narrate`
   на ходу, которым бой закончился (`victory`/`fled`/`ended_by_master`)**»; там же строка 466 (набор `combat_narrate`)
   устарела — `unsupported_action` там нет, есть `defeat_outcome` — поправить попутно.

### Ф4 — `/fight` (Q4, Q5)
1. Синтаксис: `/fight <monster_id>[ xN][, <monster_id>[ xN]]` — `/fight goblin_warrior x3`, `/fight skeleton x2, zombie`.
   Без аргумента — строка-подсказка с синтаксисом и списком `registry.ids("monster")`. N — 1..6, суммарно ≤
   `cfg.limits.max_enemies` (6), иначе отказ до хендлера.
2. Новый модуль `game/fight_debug.py` (чтобы не растить `commands.py`/`app.py`):
   - `parse_fight(arg, limit) -> (list[(monster_id, count)], error | None)`;
   - `fight_request(monsters) -> StartCombat`: две зоны `here` («Здесь», `exit=True`, adjacent `there`) и `there`
     («Поодаль», adjacent `here`); `hero_zone="here"`; враги в `there`, ref `f"{monster_id}_{i}"` (нумерация в пределах
     вида), `name` пустой (имя из реестра), одна группа `debug` (leader — первый ref, `intent="kill"`);
     `initiated_by="hero"` — основание боя сверх бюджета без `warn_danger` (`override_reason` → «hero»), чтобы состав не
     резался; побочный эффект — `scene.hero_initiated_combat = True` (поле есть в сейве v9, нигде не читается);
   - `run_fight(app, request) -> list[str]`: отказ при `app.pending` («Сначала нужно сделать выбор в меню.») и
     `bundle.session.boundary_pending` («Граница сцены не достроена: сначала сделайте ход.»); иначе на `app.bundle`
     **на месте** (как `tone.apply`): `rng = Rng.from_state(bundle.world.rng)`, `ctx = TurnContext(bundle, runner.registry,
     runner.cfg, rng, mode="explore", base_registry=runner.base_registry)`, `outcome = apply(ctx, request)`;
     `Invalid` → `["Бой не начат: {message}"]` (неизвестный монстр — список допустимых id из хендлера; «бой уже идёт» —
     `combat_already_active`); `Decision` → `lines = outcome.log + combat_flow.start_fight(ctx, None, "", "")`,
     `bundle.world.rng = rng.state`. Без автосейва и без записи в журнал/recent_turns (модель не вызывается). Следующая
     строка игрока идёт в `TurnRunner.combat_turn` как обычно.
3. `game/commands.py`: `cmd_fight(app, arg)` — `parse_fight` → `fight_request` → `app.reply(run_fight(...))`;
   `HELP["fight"] = "<монстр xN, …> отладка: бой с заданным составом"`; `COMMANDS["fight"]`.
4. `ui/session.py PlaySession.render_step`: `SCREEN_COMMANDS = ("/load", "/fight")`; условие
   `line.startswith(SCREEN_COMMANDS)` вместо `startswith("/load")` → после `/fight` в simple и TUI сразу карта, меню
   действий и `COMBAT_HINT` (`combat_blocks`). Рельеф (`elevation`), засада, именованные NPC — не поддерживаются
   (просить рассказчика); для чек-листа ЖП1 п. 14–18, 22–24, 27–35 команды достаточно.
5. Доки: ARCHITECTURE.md — раздел команд (где `/difficulty`): `/fight` с пометкой «отладка»; README, если там список команд.

## 2. Затронутые файлы
`llm/errors.py` (`LlmTransient.__init__`, `RetriesExhausted.__init__`, `TIMEOUT_NAMES`, `is_timeout_error` — новая);
`llm/retry.py` (`call_with_retries`, `give_up` — новая); `llm/gemini_adapter.py` (`GeminiAdapter.translate_error`);
`llm/anthropic_adapter.py` (`AnthropicAdapter.translate_error`); `llm/journal.py` (`Journal.record_call`); `llm/replay.py`
(`ReplayAdapter.complete`); `llm/mock.py` (`STEP_KEYS`, `ScriptedAdapter.complete`); `config/app.py` (`RetryConfig`);
`config/app_defaults.toml`; `master/session.py` (`COMBAT_OVER`, `COMBAT_ANNOUNCED`, `announces_combat` — новая,
`MasterSession.tag_missing_combat` — новая, `MasterSession.choices_missing`, `MasterSession.run` — две строки);
`master/prompts/narrator_rules.md` (стр. 26, 38, 108); `game/fight_debug.py` — новый (`parse_fight`, `fight_request`,
`run_fight`); `game/commands.py` (`cmd_fight` — новая, `HELP`, `COMMANDS`); `ui/session.py` (`SCREEN_COMMANDS`,
`PlaySession.render_step`). Без изменений: `game/turn.py`, `game/app.py`, `game/combat_flow.py`,
`protocol/handlers/combat.py`, `protocol/schema.py`, `master/summarizer.py`.
Документы: ARCHITECTURE.md (C4/E3 повторы; 466, 475; команды), BACKLOG (новый пункт «Ф2а: тег `combat_announced` —
по частоте в ЖП2 решить про приписку»), ROADMAP (19ф ✅), HANDOFF; docs/decisions/zhp1-findings.md — строка «→ 19ф» у
Ф1/Ф2/Ф4; `docs/checklist-19f-live.md` (не коммитить).

## 3. Шаги kaban
1. Ф1 код: errors → адаптеры → config/defaults → retry (`give_up`) → journal/replay/mock. `make smells` после llm.
2. Ф2б: `COMBAT_OVER`, `choices_missing`; Ф2а: `COMBAT_ANNOUNCED`, `announces_combat`, `tag_missing_combat`, вызов в `run`.
   Правила (стр. 26, 38, 108). `make smells`.
3. Ф4: `game/fight_debug.py`, `cmd_fight`, `HELP`/`COMMANDS`, `SCREEN_COMMANDS` в `ui/session.py`. `make smells`.
4. Офлайн-проверки (не коммитить): (а) одноразовый скрипт по `saves/vale-cd40a140/journal/calls-001.jsonl` — 4 записи
   ошибок `run-…-25` прогнать через `call_with_retries` с `ReplayAdapter`-подобной заглушкой: с ключом `timeout` (как
   записал бы новый журнал) — 1 вызов, без ключа — 4 (старый реплей не ломается); (б) `announces_combat` → True на тексте
   хода 5 vale и False на всех остальных 320 explore-финалах без `start_combat` (скрипт §0 — расширить проверкой
   функции); (в) `choices_missing` → True на тексте хода 10 vale при `outcome="victory"`.
5. Доки (§2), BACKLOG/ROADMAP/HANDOFF; чек-лист `docs/checklist-19f-live.md`: 3.8-flash при 503/504 → меню ≤ 2 мин, в
   меню первой следующая модель; `/fight goblin_warrior x3` на «лёгкой» → все трое в бою, «Бой сверх бюджета: герой напал
   первым», карта и меню сразу; бой до победы → финальный ход с меню вариантов, тег `choices_retry` если приписка
   понадобилась; пункты 14–18, 24, 28–33 ЖП1 через `/fight` (гоблины, skeleton, zombie, ghoul, wolf x2, giant_rat x2).

## 4. kaban-doeba (TDD; cov/mutmut — оркестратор фоном)
Ф1 (`tests/unit/llm/test_llm_errors_retry.py`, `test_llm_gemini_adapter.py`, `test_llm_anthropic_adapter.py`,
`test_llm_journal.py`, `test_llm_replay.py`, `test_llm_mock.py`, `tests/unit/config/test_t60_config.py`,
`tests/unit/master/test_t60_network.py`, `tests/unit/game/test_game_app.py` или новый `test_game_timeout_menu.py`):
- `LlmTransient().timeout is False`; `timeout=True` сохраняется; `RetriesExhausted` берёт `timeout` у `last`, текст при
  таймауте содержит «таймаут», без — прежний «повторы исчерпаны»; `is_timeout_error`: httpx `ReadTimeout`,
  `ConnectTimeout`, `TimeoutException`, anthropic `APITimeoutError`, builtin `TimeoutError` → True; `ConnectError`,
  `RemoteProtocolError`, `ValueError` → False;
- Gemini `translate_error`: `ApiError(504)` → transient, `timeout True`; 408/429/500/503 → `timeout False`; `ReadTimeout`
  без кода → True; `ConnectError` → False; 400–404 → fatal как раньше. Anthropic: статус 504 → True, 503 → False,
  `APITimeoutError` → True, `retry_after` на 504 сохраняется;
- `call_with_retries`: таймаут на 1-й попытке, `delays=[1,3,10]`, `retry_timeouts=False` → `RetriesExhausted` после
  **1** вызова, пауз нет, `attempts == 1`, `on_attempt` вызван раз; `retry_timeouts=True` → 4 вызова, как раньше;
  503, 503, 504 → 3 вызова, 2 паузы (1, 3); 503 → ответ — как раньше; `delays=[]` + таймаут → 1 вызов (и так);
  `give_up` таблично;
- config: дефолт False; `[retry] retry_timeouts = true` из toml; не-bool → ошибка валидации;
- journal: `error` в записи = `{kind, message, retry_after, timeout}` (поправить `test_transient_error_record`,
  `test_fatal_error_record` — у fatal `timeout False`); replay: запись с `timeout: true` → поднятый `LlmTransient.timeout`
  True; запись без ключа → False; mock: шаг `{error: transient, timeout: true}` → True, неизвестные ключи по-прежнему
  `ValueError`;
- master/game: `ScriptedAdapter` с таймаут-шагом → `TurnFailed("network")` после одного вызова, в `attempts.log` одна
  строка, `result.menu == ERROR_MENU`, `hint` содержит «таймаут»; `GameApp.after_turn` → `failed_reason == "network"`,
  `choose_error("switch_model")` → `switch_role == "both"` (регресс Т60); summarizer primary+backup — одна попытка как
  раньше (есть `test_run_scene_with_empty_policy_makes_one_attempt`).

Ф2а (`tests/unit/master/test_master_choices_ask.py` или новый `test_master_combat_announced.py`,
`test_narrator_choices_rules.py` → добавить «Бой»):
- `announces_combat`: «…поднимая оружие.\n\n*(В этот момент начинается бой!)*» → True; «Бой начался.» → True; «В бой!» →
  True; «боярин начинается с…»/«бойня» → False (границы слова); фраза не в последнем абзаце → False; пусто → False;
- сессия explore: текст с фразой, без вызовов → `result.report_tags == ["combat_announced"]`, лишних вызовов нет
  (`len(adapter.requests) == 1`); с принятым `start_combat` в том же ходу → тега нет; `combat_narrate` → нет; роль world
  → нет; game-уровень: тег в `TurnResult.report_tags`, авто-репорт записан (как `test_choices_retry_writes_auto_report`);
- правила: в разделе «Бой» есть «в этом же ходу» и «без вызова — ошибка»; `system_sha256` старого реплея меняется —
  существующие тесты на правила не ломаются (проверить `test_master_rules.py`).

Ф2б (`tests/unit/master/test_master_choices_ask.py`, `tests/unit/game/test_game_choices_ask.py`, `game_kit.py`):
- `choices_missing`: `combat_ctx` с `outcome="victory"`, `mode="combat_narrate"`, текст с «?» → True; `outcome None` →
  False; `hero_dying`, `defeat_pending`, `hero_dead` → False; `fled`, `ended_by_master` → True; `combat_classify` → False;
  `offer_choices` принят → False; explore + `active_combat None` → как раньше; explore + бой начат в этом ходу → False;
- game-уровень: `fight()` + `drive(rig.runner, attack_or_move_number)` до победы с `ReactiveAdapter`, у которого текст
  `combat_narrate` кончается «Что ты делаешь дальше?» и на `CHOICES_ASK` в последнем сообщении — вызов `offer_choices`
  (расширить kit: `narrate_text=`, ответ на приписку): на ходу победы `choices_retry` в тегах, один дополнительный вызов,
  `bundle.session.offered_choices == [...]`, `recent_turns[-1].requests` содержит `offer_choices`, `offer_is_stale(app)`
  False, `screen_blocks(app)` — `menu`; на промежуточных ходах боя приписки нет (`test_combat_turn_is_not_asked`
  остаётся); при `end_combat=True` (ended_by_master) — то же; если ответ на приписку текстом — ход принят, меню нет;
- правила: абзац `combat_narrate` упоминает `offer_choices` при законченном бое; строка «Выбор игроку» — «пока бой идёт».

Ф4 (`tests/unit/game/test_game_fight_debug.py` — новый, `test_game_commands.py`, `tests/unit/ui/test_ui_session.py`):
- `parse_fight`: «goblin_warrior x3» → [("goblin_warrior", 3)]; «goblin_warrior x2, skeleton» → два; «skeleton» → 1;
  «x0», «x7», семь суммарно, «goblin x3 x4», пусто → ошибка (текст с синтаксисом); регистр/пробелы вокруг запятых;
- `fight_request`: 2 зоны, `hero_zone == "here"`, `exit` у `here`, враги в `there`, refs `goblin_warrior_1..3` + `skeleton_1`,
  группа `debug`, leader — первый ref, `intent kill`, `initiated_by hero`; Pydantic-валидно;
- `run_fight` через `app.handle("/fight goblin_warrior x2")`: `active_combat` не None, 2 участника-врага с
  `monster_id`, в reply.lines «Бой: врагов 2, зон 2» и строки инициативы, `adapter.requests == []` (модель не звали),
  `world.rng` изменился, журнал пуст, recent_turns не выросли; затем `handle("1")`/текст идёт в `combat_turn` (бой
  продолжается); 3 гоблина на «лёгкой» → все трое, строка «Бой сверх бюджета»; `/fight` в бою → «бой уже идёт», состояние
  нетронуто; неизвестный монстр → «нет монстра», в тексте допустимые id, `active_combat None`; `pending` (меню) → отказ;
  `boundary_pending` → отказ; `/fight` без аргумента → подсказка со списком монстров;
- `/help` содержит `fight`; `ALL_COMMANDS` + «fight»; `test_commands_do_not_call_model_or_touch_state` — `/fight` в
  параметры не добавлять (он меняет состояние) — отдельный тест выше;
- UI: `make_session(app).submit("/fight goblin_warrior")` → в `kinds(step)` есть `combat_map` и `turn_menu`, последний —
  `status`; `/help` по-прежнему без экрана (регресс `test_help_…`).

## 5. Smells (200/200, нулевой баланс)
Новые функции простые: `is_timeout_error` (1 условие), `give_up` (≤ 3), `announces_combat` (≤ 4),
`tag_missing_combat` (≤ 5, 1 return), `choices_missing` (2 return, ≤ 5), `parse_fight` (≤ 5 условий, не больше 3 return),
`fight_request` (линейная), `run_fight` (≤ 4 условий, ≤ 3 return), `cmd_fight` (2–3 return). Изменения в уже
помеченных `MasterSession.run` и `Journal.record_call` (many parameters) новых smells не дают. `render_step` — замена
литерала на кортеж, без новых ветвей. Правки `translate_error` — выражениями, без новых `if`. Если `make smells` даст
201: компенсация — вынести из `TurnRunner.combat_turn` ветку цифрового ввода (`text.strip().isdigit()` → `steps, hold`)
в `digit_steps(work, registry, cfg, text)`; не нужна — не трогать.

## 6. mutmut (`модуль:функция`, сверено grep-ом)
`ai_dm.llm.errors:is_timeout_error` (новая), `ai_dm.llm.errors:LlmTransient.__init__`,
`ai_dm.llm.errors:RetriesExhausted.__init__`, `ai_dm.llm.retry:call_with_retries`, `ai_dm.llm.retry:give_up` (новая),
`ai_dm.llm.gemini_adapter:GeminiAdapter.translate_error`, `ai_dm.llm.anthropic_adapter:AnthropicAdapter.translate_error`,
`ai_dm.llm.journal:Journal.record_call`, `ai_dm.llm.replay:ReplayAdapter.complete`, `ai_dm.llm.mock:ScriptedAdapter.complete`,
`ai_dm.master.session:announces_combat` (новая), `ai_dm.master.session:MasterSession.tag_missing_combat` (новая),
`ai_dm.master.session:MasterSession.choices_missing`, `ai_dm.game.fight_debug:parse_fight` (новая),
`ai_dm.game.fight_debug:fight_request` (новая), `ai_dm.game.fight_debug:run_fight` (новая), `ai_dm.game.commands:cmd_fight`
(новая), `ai_dm.ui.session:PlaySession.render_step`. TESTS для mutmut — узкие файлы §4 (правило Makefile).

## 7. Риски
- Ф1: класс исключения таймаута у google-genai/httpx — по MRO (`ReadTimeout`/`TimeoutException`); если SDK когда-нибудь
  обернёт таймаут в свой класс без кода, флаг не встанет и поведение вернётся к прежнему (безопасно). `TimeoutError`
  builtin в `TIMEOUT_NAMES` — `socket.timeout` его алиас.
- Ф1: 504 от Gemini без перегрузки (очень длинный ответ) тоже уйдёт в меню — «повторить» в меню есть; `[retry]
  retry_timeouts = true` возвращает старое поведение.
- Ф1: журналы, записанные до 19ф, в реплее повторяют 4 попытки (нет ключа `timeout`) — так и задумано; журналы после —
  одну.
- Ф2: правки `narrator_rules.md` меняют `system_sha256` → `--replay` старых ходов рассказчика расходится (принято ранее).
- Ф2б: один лишний вызов (приписка) на ходах победы у моделей, не вызывающих `offer_choices` в бою (flash-lite); у
  3.8-flash/sonnet по корпусу ТВ приписка на explore почти не нужна — ожидание то же.
- Ф2а: тег без действия — только измерение; ложные тревоги («В бой!» в реплике NPC при уже идущем бое исключены режимом,
  вне боя — репорт лишний, не вред).
- Ф4: `initiated_by="hero"` ставит `scene.hero_initiated_combat` (не читается); бой начат без рассказа — рассказчик на
  следующем ходу видит `combat` в состоянии, но без завязки; для отладки допустимо. Команда доступна игроку всегда (Q4).
- Сейв v9: новых полей нет; `/fight` не пишет автосейв — при выходе бой теряется (ожидаемо для отладки).

## 8. Оценка
≈ 0,4–0,45 млн: kaban ≈ 0,13 (три независимых куска, один вызов), doeba ≈ 0,17 (четыре файла тестов + kit), mama ≈ 0,03,
svekrov ≈ 0,03, оркестратор ≈ 0,05; план (papa) ≈ 0,17 сверх. Миграций нет, импорта данных нет.

## 9. Открытые вопросы (Q с рекомендацией)
1. **Ф1 — как сократить ожидание меню:** (а) **первый таймаут/504 — сразу меню** (`[retry] retry_timeouts = false`), 503/429
   — полные повторы, как сейчас; (б) укоротить `delays` рассказчика (напр. `[1]`) — не решает: худший случай всё равно
   2 × 90 с + 1 с ≈ 3 мин; (в) общий бюджет времени на вызов (`retry.budget_s`) — при 90-с таймауте эквивалентно (а), но
   сложнее и менее прозрачно; (г) авто-переключение по цепочке — отвергнуто Q3(б) Т60. **Рек.: (а).**
2. **Ф2а — «начинается бой!» без `start_combat`:** (а) только правило; (б) **правило + тег `combat_announced` с
   авто-репортом, без вызова модели** — ЖП2 измерит частоту; (в) правило + приписка `COMBAT_ASK` со служебным вызовом
   `start_combat` (как `ask_choices`) — слабая модель должна сконструировать зоны/врагов одним вызовом, +1 вызов, +риск
   невалидного старта; при 1/321 не окупается. **Рек.: (б).**
3. **Ф2б — исходы, на которых проверять варианты:** (а) **`victory`, `fled`, `ended_by_master`**; (б) + `defeat_pending`
   (плен/ограбление: герой жив) — там ход и так занят обязательным `defeat_outcome`, следующий explore-ход проверится сам.
   **Рек.: (а).**
4. **Ф4 — доступность `/fight`:** (а) **команда всегда доступна, в `/help` помечена «отладка»**; (б) только с флагом CLI
   `--dev` (новый аргумент, `GameApp(debug=…)`, прокидка через cli — ≈ +40 строк и тесты). Игра одиночная, «чит» вредит
   только самому игроку. **Рек.: (а).**
5. **Ф4 — автосейв после `/fight`:** (а) **нет** (как после обычного хода: сейв только на границе сцены); (б) да, как
   `/tone`/`/difficulty`. **Рек.: (а).**

**Решения проектировщика (2026-10-16):** «окей, кабаним» — Q1–Q5 по рекомендациям: Q1а, Q2б, Q3а, Q4а, Q5а.

## 10. Модель и расход papa-kaban
Fable 5.1 (`claude-fable-5-1`); расход ≈ 175 тыс. токенов (чтение журнала vale, кода llm/master/game/ui, планов Т60/ТВ,
два скрипта офлайн-проверки в scratchpad). Фактически по счётчику субагента ≈ 234 тыс.
