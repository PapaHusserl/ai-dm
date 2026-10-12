# План партии Р1 «Память боя» (papa-kaban, 2026-10-12; на аппрув проектировщика)

Задача: BACKLOG 38 д (t113) по решениям docs/decisions/r1-grooming.md («Решения проектировщика»): В1а свёртка в
`memory.recent_turns` при конце боя, В2а старт и финал дословно, В3а текст детерминированно из состояния, **В3-доп б**
потери (урон герою, упавшие союзники), В4а границы при начале боя нет, В5а порог ≥ 2 промежуточных ходов, **В6б**
сворачивать и при смерти героя, **В7б** старт не найден → свернуть ходы сцены, В8а без настройки, В9а имена противников
в тексте. Сейв v9, полей в `TurnRecord`/`SessionState`/`CombatState` нет, миграций нет. Размер S ≈ 0,8–0,9 млн по шкале
R5. Код на 3ae371f (П37), рабочее дерево чистое по src.

## Что показал код (сверка перед планом)

- **Запись хода.** `TurnRecord(turn_seq, at_s, player_input, narration, requests, rolls, scene_id)` (`state/scene.py:36–45`,
  `extra="forbid"`), пишется в `TurnRunner.commit` (`game/turn.py:222–238`) после `explore_turn`/`combat_turn`;
  `recent_turns_keep = 50`. Окно рассказчика `recent_window(memory, n)` (`master/context.py:68–71`) — последние 8.
- **Конец боя.** `finish_combat(work, registry)` (`game/combat_flow.py:209–247`) зовётся в `combat_turn`
  (`turn.py:444–446`) и в `explore_turn`, если бой начался и кончился в том же ходу (`turn.py:385–391`); оба раза
  `settle_parley` перед ним. `finish_combat` обнуляет `active_combat` (247) и ставит `last_combat` только при
  victory/fled/ended_by_master и живом герое (228–245); `state.gear` считается в `settle_ground` (`combat/end.py:108`)
  только при победе — иначе пуст. Локальная `state = work.session.active_combat` в обоих местах (381, 434) переживает
  `finish_combat` — `CombatState` для текста доступен после него.
- **Исход словами.** `OUTCOME_WORDS` (`combat/end.py:11–15`): победа / бегство / герой погиб / герой умирает /
  поражение / завершён мастером. Последняя строка лога: «Бой окончен: <исход>, раундов: N» (137).
- **Имена участников.** `CombatEngine.name(ref)` (`combat/engine.py:160–173`): герой — `hero.name`; иначе
  `Participant.name` (пусто → `ref`), одинаковые имена нумеруются по порядку участников («гоблин 1», «гоблин 2»).
  `Participant.name` заполняет `start_combat` (`protocol/handlers/combat.py:100`: `spec.name or npc.name or monster.name`).
  Движка при `finish_combat` уже нет — правило имён нужно вынести в функцию (п. 1).
- **Маркер начала боя.** `start_combat` в `requests` записи хода исследования (`turn.py:350–352, 370`); статусы
  accepted/clamped. Вне `requests` маркеров нет.
- **`rolls` в бою пустые.** `result.rolls` пополняется только при `"roll_ref"` в `outcome.result` (`turn.py:352`) —
  это `skill_check` (`protocol/handlers/checks.py:9`) и торг (`handlers/trade.py:66`). Инструменты боя:
  `combat_classify` = player_action/unsupported_action, `combat_narrate` = offer_choices/end_combat/defeat_outcome
  (`protocol/schema.py:26–27`) — `roll_ref` не дают. Броски движка идут в `result.log`/`lines`, в `TurnRecord` не
  попадают. **Критерий В7б «ходы сцены с бросками» в данных отсутствует** → Q1.
- **Лог боя без базы HP.** `engine.start()` пишет только «Бой начался» и строки инициативы (`engine.py:306–319`,
  `initiative.py:27`); HP героя на старте боя нигде не логируется и не хранится. Строки HP: «  <имя>: HP a/b» после
  урона (`attack.py:495`, `cast.py:170,270,306`, `move.py:29` «опасная зона, HP a/b», `engine.py:389` горение),
  «<имя>: <лечение> +N, HP a/b» (`features.py:17`, `item.py:21`), «  Царапина: N урона, HP a/b» (без имени,
  `mastery.py:78`); поправки урона — «Сопротивление (…): 7 → 3 рубящий» (`rules/damage.py:42–46`), «Временные HP
  поглотили N» (95). Выбывание: «  <имя> без сознания», «погибает», «без сознания, умирает», «выбывает из боя без
  сознания», «убит» (`downed.py:60,69,147–154`). Точный урон герою из лога не выводится (нет базы) → Q2.
- **Союзники.** Участники `side == "heroes"` с `ref != hero.id` (спутники); их статус `down`/`dead` после боя — в
  `state.participants`, то же, что строки лога выше.
- **Сцена и смерть.** `check_close` (`game/scene.py:26–40`) не смотрит `active_combat`: `turn_limit`
  (`max_player_turns = 30`, `config/defaults.toml:62`) может закрыть сцену **посреди боя** — тогда старт боя остаётся в
  прошлой сцене (точка 9 груминга, реальный случай длинного боя). Смерть героя: `close_scene_if_needed` выходит
  (`turn.py:241–244`) — ни границы, ни автосейва; `pending = "hero_dead"` (`game/app.py:215–217`), меню
  load_last_save/quit (`DEAD_MENU`), `/save` запрещён (`game/commands.py:57`), автосейв при выходе и в лимит-меню
  запрещён (`ui/session.py:87, 182`); «загрузить последнее» = `load("auto")` (`app.py:381–384, 397–436`).
- **Кто читает `recent_turns`.** UI: `last_narration_block` и `offer_is_stale` смотрят `recent_turns[-1]`
  (`ui/session.py:41–54`). Summarizer: `scene_turns` по `scene_id` (`master/summarizer.py:13–20`), в запрос —
  `player_input/narration/requests/rolls` каждого хода (113–118). `relevance.mentions` — ввод и рассказ всех записей
  (`master/relevance.py:4–9`). `/report`: `recent_lines` (`reports/markdown.py:114–126`) — «### Ход N / Фраза игрока:
  … / рассказ / Броски». Replay сравнивает снимки `before/after` (`reports/replay.py`).
- **Тесты.** Мок памяти `tests/scenarios/memory_script.py` (`WINDOW = 23500`) боя не содержит — окно не плывёт;
  других `WINDOW` в сценариях нет. Бои с концом: `tests/unit/game/test_game_combat_flow.py` (383–571: `drive` до
  победы/поражения/смерти, `end_combat`), `tests/scenarios/test_stage2_flow.py` (`victory_story`),
  `test_stage2_live_like.py`, `test_stage6a_done.py` (replay ходов боя — репорты строятся в тесте, детерминизм),
  `tests/scenarios/test_criterion1.py` (golden stdout `goblins3_win.txt` — stdout, не память). Записи
  `recent_turns[-1]` проверяют только посреди боя (154, 257) и после `honest_run` (`test_stage2_done.py:443`).
  Счёт записей после боя не проверяет никто. `tests/unit/ui/test_offer_stale.py` строит записи руками.
- `make smells` — **205/206** (замер 2026-10-12 на 3ae371f).

## Как сочетаются решения не по рекомендации (проверено по коду)

- **В6б (смерть героя — сворачивать).** Свёртка делается на рабочей копии `work` до `commit`; после commit при
  `hero_dead` — ни границы, ни автосейва; сохранить вручную нельзя. Свёртка живёт только в памяти сессии и в снимке
  `after` последнего хода (`/report` после гибели покажет свёртку + финальный ход). «Загрузить последнее» грузит
  auto-слот (до боя или последняя граница) — свёртки там нет и быть не должно. Конфликта с незакрытой сценой нет:
  записи сцены продолжают лежать в `recent_turns`, сцена не закрывается, summarizer не зовётся. Итог: В6б —
  безусловный вызов, без ветки по `hero_dead`; отличие от В6а видно только в `/report` и в тесте.
- **В7б (старт не найден).** Критерий «с бросками» пуст (см. выше). Когда старт не найден: (1) обрезан
  `recent_turns_keep` (бой ≥ 49 записей) — тогда все записи в памяти и есть ходы боя; (2) старт в прошлой сцене после
  `turn_limit`-границы посреди боя — тогда все записи текущей сцены — ходы боя. В обоих случаях «все записи текущей
  сцены» = «все ходы боя». Предлагаю искать старт **по всему `recent_turns`** (не только в сцене) — случай (2)
  сворачивается штатно, старт остаётся дословно в прошлой сцене; а при отсутствии старта сворачивать все записи текущей
  сцены (намерение В7б без критерия «броски») → Q1.
- **В3-доп б (потери из лога).** Союзники и HP героя к концу боя из лога и из состояния совпадают (строки лога пишутся
  из тех же статусов и `hp_text`); числа урона за бой из лога нет (нет HP на старте). Предлагаю «потери» = HP героя на
  конец боя + выбывшие союзники; источник — состояние (эквивалент лога, без регулярок) → Q2.

## Реализация (kaban)

### 1. Имя участника без движка — `src/ai_dm/combat/engine.py`
1.1. Вынести тело `CombatEngine.name` в модульную функцию `participant_name(state, heroes, ref) -> str` (та же
   логика: герой → `heroes[ref].name`; `part.name or ref`; нумерация одинаковых имён среди не-героев по порядку
   `state.participants`). `CombatEngine.name` → `return participant_name(self.state, self.heroes, ref)`. Поведение
   лога не меняется (golden `goblins3_win.txt` остаётся).

### 2. Свёртка — новый модуль `src/ai_dm/game/combat_fold.py` (чистые функции на бандле, в стиле `game/boundary.py`)
2.1. `fight_start(turns) -> int | None` — индекс **последней** записи `recent_turns` с `"start_combat"` в `requests`
   (по всему списку, Q1а).
2.2. `fight_tail(turns, scene_id) -> int` — индекс первой сворачиваемой записи: `start + 1`, если старт найден; иначе
   индекс первой записи с `scene_id == scene_id` (все записи текущей сцены; нет таких → `len(turns)`). Сворачиваемые —
   `turns[tail:]` (хвост списка; финальный ход боя в `recent_turns` ещё не записан — он придёт через `commit`).
2.3. `enemy_names(state, hero) -> list[str]`, `defeated_text(state, hero) -> str` — противники (`side == "enemies"`)
   по порядку участников через `participant_name(state, {hero.id: hero}, ref)`; побеждённые — по статусу:
   «убит» (dead), «без сознания» (down), «бежал» (fled), «сдался» (surrendered); при `ended_by_master` стоящие на
   ногах — «сдался» (как в `finish_combat`). Статус `active` при других исходах — не упоминается.
2.4. `losses_text(state, hero) -> str` (Q2а): «<герой> HP a/b» из `hero.creature` (hp_current/hp_max) — только если
   герой ранен (`hp_current < hp_max`; решение проектировщика по ревью, 2026-10-12 — по состоянию, не по логу);
   спутники (`side == "heroes"`, `ref != hero.id`) со статусом `down` → «<имя> без сознания», `dead` → «<имя>
   погиб(ла)» — без пола, слово «выбыл(а)»: «<имя> — без сознания» / «<имя> — погиб»; формулировку финально — kaban.
   При Q2б — вместо HP героя число урона: сумма «= N» строк урона между предыдущей HP-строкой любого участника и
   HP-строкой героя (приближение).
2.5. `trophies_text(last_combat, registry) -> str` — `entry_name(entry, registry)` (`rules/inventory.py:26`) с
   «×qty» при qty > 1; `last_combat is None` → пусто (В3а: трофеи только при `LastCombat`).
2.6. `fold_text(state, hero, last_combat, registry, first_seq, last_seq) -> str` — одна строка, части через «; »,
   пустые части опускаются: `Свёрнуты ходы {first}–{last}. Бой: {противники} — {OUTCOME_WORDS[outcome]}, раундов:
   {state.round}; побеждены: …; потери: …; трофеи: …` Импорт `OUTCOME_WORDS` из `ai_dm.combat.end`. Детерминировано:
   только состояние, без времени и rng.
2.7. `fold_fight(bundle, state, registry) -> bool` — вход: `scene = bundle.session.current_scene`; `tail =
   fight_tail(turns, scene.id)`; `folded = turns[tail:]`; `len(folded) < 2` → `False`, ничего не менять (В5а);
   иначе запись `TurnRecord(turn_seq=folded[-1].turn_seq, at_s=folded[-1].at_s, scene_id=folded[-1].scene_id,
   player_input="", narration=fold_text(…), requests=[], rolls=[])`, `bundle.memory.recent_turns = turns[:tail] +
   [record]`, `True`. `hero = hero_of(bundle)`, `last_combat = bundle.session.last_combat`.

### 3. Вызов — `src/ai_dm/game/turn.py`
3.1. Новый метод `TurnRunner.end_fight(self, work, result, fold)`: `state = work.session.active_combat`;
   `combat_flow.settle_parley(work, self.cfg)`; `result.combat_outcome = combat_flow.finish_combat(work,
   self.registry)`; `if fold: combat_fold.fold_fight(work, state, self.registry)`. Свёртка **после** `finish_combat`
   (нужен `last_combat` для трофеев) и **до** `commit` (финальный ход встанет после свёртки) и до
   `close_scene_if_needed` (автосейв закрытой сцены и summarizer видят свёртку). Без ветки по смерти (В6б).
3.2. `combat_turn` (444–446) → `self.end_fight(work, result, fold=True)`; `explore_turn` (390–391) →
   `self.end_fight(work, result, fold=False)` — бой начался и кончился в одном ходу: его единственная запись ещё не
   записана, сворачивать нечего, а поиск старта нашёл бы старт **прошлого** боя и свернул бы сюжет текущей сцены.
   Дубликат двух строк уходит → smells не растут.
3.3. Ничего в `commit`, `close_scene_if_needed`, `boundary`, `summarizer`, `context`, `relevance`, UI и `reports` не
   меняется: все они читают `recent_turns` как есть. Финальный ход боя остаётся последней записью → `last_narration_block`
   и `offer_is_stale` после загрузки работают как прежде (В2а).

### 4. Docs
`docs/BACKLOG.md` п.38 д — сделано (ссылка на план и ревью); `docs/HANDOFF.md` — строка Р1; `docs/ROADMAP.md` перед
коммитом. Чек-лист `docs/checklist-r1-live.md` (не коммитить), на `--mock` (бои идут без сети): бой ≥ 4 ходов героя →
после победы `/report` показывает «Свёрнуты ходы …» между стартом и финалом, после `/load auto` виден финальный
рассказ, цифры вариантов работают; бой на 2 хода — свёртки нет; смерть героя → меню, «загрузить последнее» — мир до боя.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.game.combat_fold:fight_start ai_dm.game.combat_fold:fight_tail ai_dm.game.combat_fold:enemy_names
  ai_dm.game.combat_fold:defeated_text ai_dm.game.combat_fold:losses_text ai_dm.game.combat_fold:trophies_text
  ai_dm.game.combat_fold:fold_text ai_dm.game.combat_fold:fold_fight` — TESTS tests/unit/game/test_combat_fold.py
- `ai_dm.game.turn:TurnRunner.end_fight` — TESTS tests/unit/game/test_game_combat_flow.py tests/unit/game/test_combat_fold_flow.py
- `ai_dm.combat.engine:participant_name` — TESTS tests/unit/combat/test_engine_names.py (или существующий файл с тестами `name`)

## Тесты (kaban-doeba, TDD)

Правка существующих: ожидаемо **ничего не ломается** (счёт записей после боя никто не проверяет; `recent_turns[-1]`
смотрят посреди боя или вне боя). Проверить полным прогоном; если упадёт `test_stage2_live_like`/`test_stage6a_done`
по снимкам — это детерминизм свёртки, не менять ожидание, а чинить код.

Новые — чистые (`tests/unit/game/test_combat_fold.py`; записи через `TurnRecord(...)` как в `test_offer_stale.py`,
`CombatState` через `start_combat_input`/`game_kit.make_bundle` или вручную):
- `fight_start`: нет `start_combat` → `None`; один → его индекс; два (старый бой + новый) → индекс последнего;
  `requests=["skill_check","start_combat"]` считается.
- `fight_tail`: старт на i → i+1; старта нет, записи сцен `[s1, s1, s2, s2]`, scene_id s2 → 2; старта нет и записей
  сцены нет → `len`; старт в прошлой сцене (`[s1 start, s1, s2, s2]`) → 1 (сворачиваются и записи s1 после старта).
- `fold_fight`: 0 и 1 промежуточных → `False`, список не тронут; 2 → `True`, список = префикс + одна запись;
  поля записи: `turn_seq/at_s/scene_id` последней свёрнутой, `player_input == ""`, `requests == []`, `rolls == []`;
  старт остаётся дословно; вызов дважды подряд — второй раз `False` (запись-свёртка без `start_combat`, промежуточных
  меньше 2) — детерминизм; тот же вход → байт-в-байт тот же текст.
- `fold_text`: содержит имена всех противников (В9а), слово исхода из `OUTCOME_WORDS` для каждого из 6 исходов,
  «раундов: N», диапазон ходов; побеждены — по статусам (dead/down/fled/surrendered + `ended_by_master` стоящие);
  `last_combat=None` → нет «трофеи»; `gear` с qty 2 → «×2» и имя через `entry_name` (качество приставкой); потери: герой
  без урона → нет «HP», с уроном → «HP a/b» = `hero.creature`; спутник `down`/`dead` → в потерях, спутник `active` —
  нет; два одноимённых гоблина → «гоблин 1», «гоблин 2» как в логе.
- `participant_name`: совпадает с `CombatEngine.name` на одном состоянии (герой, именованный NPC, пустое имя → ref,
  дубли с номерами).

Новые — сквозные на риге (`tests/unit/game/test_combat_fold_flow.py`, `game_kit.start_fight`/`drive`/`make_app`):
- Победа за ≥ 4 хода героя (`attack_or_move_number`; при коротком бою — ослабить гоблинов через `creature.hp_current`
  или усилить, чтобы ходов было ≥ 4): `recent_turns` = […, старт (`"start_combat"` в requests), свёртка, финал];
  финал — `narration == result.narration`, его `requests` — из narrate-хода; `turn_seq` свёртки = turn_seq
  предпоследнего хода; в свёртке — `combat_xp`-независимо: «победа», «гоблин», «раундов».
- Короткий бой (`end_combat` на первом ходу героя — `start_fight(..., end_combat=True)`, 0 промежуточных) → записей
  ровно старт + финал, свёртки нет (В5а). Бой с ровно 1 промежуточным → тоже нет.
- `explore_turn` со стартом и концом в одном ходе (герой падает до своего решения, `turn.py:385–391`; есть ли такой
  рецепт в `test_game_combat_flow`/`test_game_turn` — поискать `hero_dying`/weaken до старта) → одна запись, прошлый
  бой/сюжет сцены не свёрнут.
- `ended_by_master` после ≥ 3 ходов → свёртка «завершён мастером», сдавшиеся названы.
- `defeat_pending` (intent capture, `weaken_hero`, `drive(end_turn_number)`) → свёртка есть, «поражение», трофеев нет,
  потери: «HP 0/…» или «без сознания» героя (по тексту kaban).
- **В6б**: `intent="kill"`, `weaken_hero`, бой ≥ 3 ходов до смерти → в `rig.runner.bundle.memory.recent_turns`
  свёртка есть («герой погиб»), `scene.closed_reason is None`, `list_slots == []` (автосейва нет), а через `make_app`:
  после `choose("load_last_save")` (с заранее сделанным `save_auto` до боя) в загруженном бандле свёртки нет и
  `recent_turns` равны сохранённым. `/report` после гибели (`capture.after`) содержит «Свёрнуты ходы».
- **Q1а**: старт в прошлой сцене — довести `scene.player_turns` до `max_player_turns` перед боем (или `cfg.scene.
  max_player_turns = 2` в риге), бой ≥ 4 ходов → граница посреди боя, затем победа → свёртка одна, в текущей сцене,
  старт остался в записи прошлой сцены, записей прошлой сцены после старта нет. Старт обрезан (`recent_turns_keep = 3`
  как в `test_recent_turns_keep_comes_from_config`) → свёрнуты все записи текущей сцены, финал дословно.
- Граница после боя: автосейв `auto` после победы содержит свёртку (`load_slot(...).memory.recent_turns`); с
  `new_summarizer_session` на мок — вход summarizer (`state_data["turns"]`) содержит запись с `player_input == ""`
  и текстом свёртки и не содержит промежуточных ходов (`tests/unit/master/test_master_summarizer_input.py` стиль).
- Сбой границы (summarizer бросает `TurnFailed`, как в `test_game_summarizer_boundary.py`) → бандл с `boundary_pending`
  уже содержит свёртку; `retry` достраивает границу, свёртка одна.
- UI после загрузки (`tests/unit/ui`, `ui_kit`): мир с боем ≥ 4 ходов сохранён → `PlaySession.start()` показывает
  финальный рассказ, не свёртку; `offer_is_stale` зависит от финального хода (с `offer_choices` в narrate — свежо).
- `/report` (`reports/markdown.recent_lines`): запись-свёртка печатается как «### Ход N», «Фраза игрока: » пустая,
  текст свёртки, без «Броски:».
- Replay (`test_stage6a_done` стиль): репорт хода, закончившего бой с ≥ 2 промежуточными, → `--replay-report` код 0.
- Relevance: именованный NPC-противник (grakh), упомянутый только в свёрнутых ходах, после свёртки остаётся в
  `npc_reasons` с `said` (текст свёртки содержит имя).
- Рассказчик: `recent_turns` в запросе следующего хода после боя (`state_of(adapter.requests[-1])["recent_turns"]`)
  содержит старт, свёртку, финал и не содержит промежуточных.
- Общее в конце: `uv run pytest -q`, `make cov` (≥94 %), `make smells` (≤206; сейчас 205), `make dead`, `uv run ruff
  check src tests`; mutmut по списку выше.

## Критерии приёмки
1. После боя с ≥ 2 промежуточными ходами в `recent_turns`: старт дословно, одна запись-свёртка, финал дословно;
   никакие другие записи не тронуты. Короткие бои — без изменений.
2. Текст свёртки детерминирован (replay код 0), содержит противников, исход, раунды, побеждённых, потери, трофеи
   (при `LastCombat`).
3. После загрузки мира UI показывает финальный рассказ боя; цифры вариантов работают как раньше.
4. Summarizer и рассказчик получают свёртку вместо промежуточных ходов; `/report` показывает её.
5. Смерть героя: свёртка в памяти сессии и в `/report`; автосейв/слоты не тронуты; «загрузить последнее» — мир до боя.
6. Сейв v9, схемы `tests/schema/save_v9.schema.json` без правок; тесты зелёные, cov ≥ 94 %, smells ≤ 206.

## Оценка
S ≈ 0,8–0,9 млн: kaban ~100–130 тыс. (~15 мин: модуль ~80 строк, 2 правки turn.py, 1 вынос в engine.py); kaban-doeba
~220–300 тыс. (~1–1,5 ч с mutmut: ~35 тестов, из них ~12 на риге); mama-kaban ~35 тыс. Дозадачи — по Q1/Q2.

## Риски / на что обратить внимание
- **Replay старых репортов.** Репорт хода, закончившего бой до Р1, при `--replay-report` даст другой `after`
  (свёртка) → код 1 «расхождение» — как прецедент AD1 Q4. В `tests/fixtures`/`tests/golden` репортов с концом боя нет
  (replay-тесты строят репорт в тесте). Написать в HANDOFF.
- **Поиск старта по всему списку (Q1а).** Безопасен только в `combat_turn`: текущий бой всегда моложе старого старта.
  В `explore_turn` свёртку не звать (3.2) — иначе свернёт сюжет сцены. Тест обязателен.
- **Текст свёртки — в запрос рассказчика и summarizer.** Длина ~150–300 символов при 3–5 противниках; при 10+
  безымянных участниках список имён растёт — ограничить список побеждённых группировкой «гоблин ×4» kaban может, но
  тогда имена перестанут совпадать с логом; оставить поимённо (В9а), проверить на прогоне.
- **`/report` и summarizer видят `player_input == ""`.** `summarizer_rules.md` на пустой ввод не завязан; `recent_lines`
  напечатает «Фраза игрока: » — косметика, не трогаем.
- **Смерть героя (В6б) и `last_capture.after`** — `/report` после гибели покажет свёртку; это единственное место,
  где В6б отличим; если прогон покажет, что это сбивает, вернуться к В6а одной строкой (`fold = not result.hero_dead`
  нельзя — `hero_dead` ставится в commit; брать `hero_of(work).status`).
- **smells 205/206.** Модуль из 8 коротких функций; `end_fight` убирает дубль. Если qlty посчитает лишнее — слить
  `enemy_names`/`defeated_text` в одну; лимит не поднимать.
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS, выживших перепроверять другим файлом.
- Mid-fight граница по `turn_limit` — существующее поведение (не чиним; `boundary.py` без проверки `active_combat`),
  Р1 только делает так, чтобы свёртка её переживала (Q1а). Если проектировщик захочет запрет границы в бою — отдельная
  партия (это как раз В4-территория).

## Открытые вопросы
- **Q1 В7б без критерия «броски».** В `TurnRecord.rolls` в бою пусто (`roll_ref` дают только skill_check/торг), ходы
  боя от ходов сюжета по записи не отличить. (а) **рекомендация** — старт искать по всему `recent_turns` (покрывает
  границу посреди боя: старт в прошлой сцене остаётся дословно, хвост после него сворачивается), а при отсутствии
  старта сворачивать **все записи текущей сцены** (в обоих реальных случаях — обрезка `keep` и граница посреди боя —
  это ровно ходы боя); (б) В7а — не сворачивать молча; (в) при отсутствии старта сворачивать весь `recent_turns`
  (и записи прошлых сцен) — те всё равно вне окна 8, разницы для рассказчика нет, но `/report` «последние 5» пустеет.
- **Q2 «Потери» (В3-доп б): урон как число невозможен точно.** Лог не содержит HP героя на старте боя (только
  «Бой начался» и инициатива), поле хранить нельзя. (а) **рекомендация** — «потери: <герой> HP a/b» (HP к концу
  боя; опускается, если герой не был ранен) + выбывшие спутники («без сознания»/«погиб»); брать из состояния
  (`hero.creature`, статусы `participants`) — эквивалент строк лога, без регулярок; (б) оценка урона суммой «= N»
  строк урона перед HP-строками героя — приближение (сопротивления, временные HP, «Царапина» без имени), ломкое к
  форматам лога, не рекомендую; (в) точный урон — хранить HP на старте в `CombatState` → новое поле, v10 — не Р1.
- **Q3 Префикс «Свёрнуты ходы N–M».** (а) **рекомендация** — оставить: в `/report` и рассказчику видно, что это
  свёртка, а не ход; (б) убрать — чище текст, но в `/report` запись выглядит как ход с пустой фразой игрока.
- **Q4 Побеждённые при `ended_by_master`.** В `finish_combat` стоящие на ногах считаются побеждёнными (опыт как за
  сдавшихся). (а) **рекомендация** — в тексте «сдался» для них, как в XP-логике; (б) перечислять только по фактическим
  статусам (стоящие — «уцелел») — честнее к рассказу, но расходится с опытом/лутом.

## Решения проектировщика по Q1–Q4 (2026-10-12)
Q1а — старт ищется по всему `recent_turns`, не найден → свернуть записи текущей сцены; Q2а — «потери» из состояния
(HP героя к концу боя, если ранен, + выбывшие спутники); Q3а — префикс «Свёрнуты ходы N–M» оставить; Q4а — при
`ended_by_master` стоящие на ногах — «сдался».
