# План мини-партии #22 «ТС Summarizer и границы» (T7 + BACKLOG 61 + BACKLOG 46)

Автор: papa-kaban (fable), 2026-10-16. Статус: **на аппрув** (Q1–Q8 в §8). Груминга нет (техдолг по правилу фикса, прецеденты TV/TM/TO-PLAN). Smells 200/200 — нулевой баланс. Сейв: **v10 без изменений** (строка ROADMAP #22 «v9» устарела — поправить).
Источники: ROADMAP #22; docs/plan-roadmap-r6.md §2 «ТС»; BACKLOG 46, 61, 64 (T7); docs/plan-techdebt.md T7, §4 п.5; R2-PLAN (В13а, В14а, Q3), T60-PLAN, B59-PLAN п.7; ARCHITECTURE E3 (стр. 637), TZ.md:606.

Ключевые файлы: `src/ai_dm/master/summarizer.py`, `src/ai_dm/game/boundary.py`, `src/ai_dm/protocol/handlers/summary.py`, `src/ai_dm/master/prompts/summarizer_rules.md`, `src/ai_dm/protocol/context.py`, `src/ai_dm/config/app.py`, `src/ai_dm/config/app_defaults.toml`.

## 0. Офлайн-проверка гипотез (saves/ только чтение, сети нет)
**T7 — подтверждён** (`saves/dusk_academy-d3de6c57/issues/*-refusal_fallback`, журналы `role: summarizer`, один `bnd-…` на границу):
- t396: haiku 1389→1030→861 симв. (3 вызова, все `summary_too_long`) → 3-й invalid > `retry.invalid_retries = 2` → `TurnFailed("invalid")` → бэкап sonnet 751→543. Итого 5.
- t418: haiku 1456→982→743; sonnet 1233→586. Итого 5. t429: haiku 1568→990→704; sonnet 1327→675→580. Итого 6. t442: haiku 1088→776→618; sonnet 1182→609→589. Итого 6.
- Каждая попытка короче предыдущей на ~25–35 %, «сократи» ни разу не дало ×2; 3-я попытка haiku — 618–861. Sonnet тоже переполняет 1–2 раза.
- Предел попадает в модель только как JSON-поле `limit` и фразой «не длиннее лимита в поле limit» (`summarizer_rules.md:9`); ответ инструмента — «Выжимка N символов, предел 600: сократи.» (`handlers/summary.py:14`).
- Цикл: `MasterSession.count_invalid` (session.py:351) — бюджет 2 невалидных; `SummarizerSession.chain` (summarizer.py:160) — `invalid` мягкий (`SOFT_REASONS`) → бэкап на модели рассказчика → `fallback_summary`; тег `refusal_fallback` (boundary.py:78/161).
- t397 (Gemini): flash-preview отдал пустой ответ → бэкап 3.8-flash → тот же тег `refusal_fallback` без отказа (61 подтверждён ещё раз).

**61 — подтверждён**: в `src/` тег только в `boundary.py:78,161`; доки — ARCHITECTURE.md:637, TZ.md:606; тесты — `test_game_boundary_p1plus.py:131,188`, `test_game_chapter_summary.py:564,601`, `test_t60_summarizer_net.py`, `test_game_summarizer_boundary.py`, `test_r2_replay.py:94`. Флаг `[llm] refusal_fallback` (anthropic_adapter.py:152, config) не трогать. Старые каталоги `…-refusal_fallback` остаются.

**46 — подтверждён по коду** (живых случаев нет): `call_world` (boundary.py:111–130) исключений не ловит; `TurnFailed` с `reason` ∈ {refusal, invalid, network, fatal, rounds} (`except LlmError` в boundary — наследие). `finish_boundary` (201–228) оставляет `boundary_pending`; `TurnRunner.play_turn` (turn.py:204–206) кладёт каждый ввод в `deferred_input` и зовёт `resume_boundary` — игра стоит до меню. Прецедент пропуска — дневной потолок (boundary.py:120–122). `verdict`-кандидаты пересчитываются на каждой границе; `act` — триггер уже сработал на копии, нарративную отработку при пропуске не повторить (Q7).

## 1. Решения (архитектура)
1. **T7а — предел явнее.** `summarizer_rules.md:9` → абзац: предел в символах с пробелами; ориентир «≈ limit/7 слов, 4–6 коротких предложений»; «лучше 450, чем 650»; порядок: сначала итог, обещания и открытые нити, потом подробности. То же для `chapter_limit`/`game_limit`. Ответ инструмента через `fit_text`: «{label} {n} симв., предел {limit}: сократи примерно в {n/limit:.1f} раза — убери подробности, оставь факты, обещания и открытые нити. Попытка {k} из {trim_after}; дальше движок обрежет по предложению.» (Q5).
2. **T7б — мягкий предел.** `handlers/summary.py`: `trim_text(text, limit)` (обрезка по последней границе предложения `.`/`!`/`?`/`…` с закрывающими кавычками/скобками; если нет или короче `limit // 2` — по последнему пробелу + «…», как `master/prompt.py clip`) и `fit_text(ctx, key, text, limit, label) -> str | Invalid` (пустой → `empty_summary`; длиннее → `ctx.summary_overflows[key] += 1`; при `trim_after > 0 and overflows > trim_after` → `trim_text`, иначе `summary_too_long`). Хендлеры при обрезке: `log=["Выжимка принята с обрезкой {n}→{m} симв."]`, `report_tag="summary_trimmed"` (Q3). `TurnContext.__init__`: `summary_overflows = {}`, `summary_trim_after = 0`. `run_scene`/`run_chapter` ставят `ctx.summary_trim_after` из `app_cfg.memory`. Конфиг: `MemoryConfig.summary_trim_after: int = Field(default=2, ge=0)`, `[memory] summary_trim_after = 2` (комментарий: ≤ `retry.invalid_retries`). `boundary.summarize_scene`/`close_chapter`: `result.report_tags += ctx.marks`.
3. **Summarizer на Claude** остаётся `claude-haiku-4-5` (Q4).
4. **61 — переименование тега**: `BACKUP_TAG = "summarizer_backup"` в boundary.py; ARCHITECTURE.md:637, TZ.md:606 (+ «до #22 тег назывался `refusal_fallback`»), BACKLOG 61 закрыть; исторические планы не правим; тесты — 7 файлов + имя теста в `test_r2_replay.py:94`.
5. **46 — пропуск world при мягком сбое**: `call_world` — `try/except TurnFailed`; `soft_failure` → тег `world_skipped`, `result.world_error = f"{reason}: {error}"`, return без вердиктов; `fatal`/`rounds` → raise. `sim.world_calls_today` остаётся увеличенным. Игроку строк нет (В14а). TZ.md:606 — `world_skipped`, `summary_trimmed`. `SOFT_REASONS`/`soft_failure` → `master/session.py`, в summarizer.py импорт (Q6).
6. **Не делаем:** запасной world; хранение отложенных `act` (сейв v11); авто-смену модели world; строки игроку; правку `fallback_summary`/`concat_chapter`; изменение `SceneSummary.source`.
7. **Smells**: `fit_text` убирает три одинаковых блока; при 201+ — компенсация в том же файле.

## 2. Затронутые файлы
`protocol/handlers/summary.py`, `protocol/context.py`, `master/summarizer.py`, `master/session.py`, `master/prompts/summarizer_rules.md`, `game/boundary.py`, `config/app.py`, `config/app_defaults.toml`. Без изменений: `game/turn.py`, `game/app.py`, `master/world.py`, `world_sim/*`, `llm/*`, схема сейва. Доки: ARCHITECTURE E3, TZ.md:606, шапки `summarizer_kit.py`/`world_kit.py`, BACKLOG 46/61/64, ROADMAP #22 (v10), handoff, `~/.config/ai-dm/checklists/checklist-ts-live.md` (не коммитить).

## 3. Шаги kaban
1. `session.py`: перенос `SOFT_REASONS`, `soft_failure`; `summarizer.py`: импорт.
2. `context.py`, `config/app.py`, `app_defaults.toml`: `summary_trim_after`, `summary_overflows`.
3. `handlers/summary.py`: `trim_text`, `fit_text`, три хендлера; `run_scene/run_chapter`.
4. `summarizer_rules.md` по Q5.
5. `boundary.py`: `BACKUP_TAG`, сбор `ctx.marks`, `try/except` в `call_world`, `BoundaryResult.world_error`. `make smells`.
6. Офлайн-гейт: `ai-dm --mock` код 0; мок-сценарий в scratchpad — summarizer три шага ~750/680/640 → граница за 3 вызова, ≤ 600, граница предложения, `source == "summarizer"`, тег `summary_trimmed`; world `{"stop": "refusal"}` → граница завершена, `boundary_pending False`, `world_skipped`, следующий ход сразу. `--replay-report` копии t429 — расхождение на 3-м вызове ожидаемо.
7. Доки; `~/.config/ai-dm/checklists/checklist-ts-live.md`.

## 4. kaban-doeba (TDD)
- `trim_text`: ровно по пределу; обрезка по границе предложения с кавычкой/скобкой; < limit//2 → пробел + «…»; без пробелов → срез + «…»; не пустой; `len ≤ limit` на 601, 750, 1568.
- `fit_text`/хендлеры: `trim_after=0` → всегда Invalid; `=2`: 1-е и 2-е → Invalid с «Попытка k из 2» и кратностью, 3-е → обрезка, лог, `summary_trimmed`, `ctx.marks`; счётчики раздельны по инструментам; пустая не считается переполнением; `already_done`; `label` сохраняются.
- `run_scene`/`run_chapter` ставят `summary_trim_after`; `MemoryConfig` дефолт 2, `ge=0`, читается из `[memory]`.
- Граница: три длинных шага → 3 записи под одним `bnd-…`, бэкап не вызван, тег `summary_trimmed`; с 0 — как раньше (бэкап → `summarizer_backup`); `close_chapter` — обрезка обоих, тег один раз.
- 61: `refusal_fallback` → `summarizer_backup` в 7 файлах, имя теста `test_report_of_boundary_with_backup_names_summarizer_backup`.
- 46 (`test_game_world_boundary.py`): refusal → завершена, `world_skipped`, `world_error` с `refusal:`, триггер не сработал, хроника пуста, записи committed; следующая граница снова даёт verdict-кандидат; три invalid → `world_skipped`; network → пропуск; fatal → как раньше (M10 на fatal); `world_calls_today = 1`; act-кандидат (Q7а); `deferred_input is None`; `test_ui_boundary.py` — на fatal.
- `soft_failure` импортируется из session и summarizer.
- mutmut (точно, без глобов): `summary:scene_summary`, `summary:chapter_summary`, `summary:game_summary`, `summary:fit_text`, `summary:trim_text`, `context:TurnContext.__init__`, `summarizer:SummarizerSession.run_scene`, `summarizer:SummarizerSession.run_chapter`, `session:soft_failure`, `boundary:BoundaryResult.__init__`, `boundary:summarize_scene`, `boundary:close_chapter`, `boundary:call_world`, `app:MemoryConfig`.

## 5. Критерии готовности
Тесты зелёные, cov ≥ 97 %, smells ≤ 200, ruff/dead чисто, mutmut по списку без живых (кроме эквивалентных/текста), `ai-dm --mock` код 0, офлайн-гейт, ревью mama-kaban, чек-лист.

## 6. Оценка
papa ~125 тыс. (факт); kaban 60–80; doeba 110–150; mama ~25. ≈ 0,3–0,35 млн (роадмап 0,45).

## 7. Риски
- Обрезка режет хвост — смягчается порядком в промпте и Q1а (потеря 3–30 %; при Q1б до 40 %).
- `summary_trim_after` > `retry.invalid_retries` — обрезка не наступит; только комментарий и тест.
- `summary_trimmed` на haiku почти на каждой границе → авто-репорт (~0,85 МБ; ротация `max_mb`) — Q3.
- Старые `--replay-report` границ t396–t442 расходятся на 3-м вызове.
- Стойкий отказ world: каждая граница — один обречённый вызов + репорт; verdict-кандидаты висят до `/model`.
- `act` при пропуске теряют нарративную отработку (Q7а).
- Записи мягко упавшего world помечаются committed.
- Старые каталоги `…-refusal_fallback` не переименовываются.
- Перенос `soft_failure` — реэкспорт в summarizer.py.

## 8. Вопросы проектировщику (рекомендации papa)
1. **Когда обрезать:** (а) после двух отказов, 3-я попытка обрезается (`= 2`); (б) на 2-м (`= 1`, потеря до 40 %); (в) сразу, если ≤ 1,5×предела. Рек. **(а)**.
2. **Область:** (а) все три инструмента; (б) только `scene_summary`. Рек. **(а)**.
3. **Видимость обрезки:** (а) тег `summary_trimmed` → авто-репорт (на одну партию прогонов); (б) только журнал. Рек. **(а)**.
4. **Summarizer на Claude:** (а) haiku + мягкий предел; (б) sonnet. Рек. **(а)**.
5. **Тексты промпта/ответа:** (а) заготовка papa; (б) правки. Рек. **(а)**.
6. **`soft_failure`:** (а) импорт из summarizer; (б) перенос в session.py. Рек. **(б)**.
7. **`act` при пропуске world:** (а) теряется на этой границе; (б) хранить в `world.sim` (v11) — хвостом в BACKLOG 46; (в) запасной world. Рек. **(а)** + (б) в BACKLOG.
8. **Мягкий сбой world:** (а) refusal/invalid/network; (б) только refusal/invalid. Рек. **(а)**.

## Решения проектировщика
2026-10-16: Q1–Q8 — все по рекомендациям papa: Q1а, Q2а, Q3а, Q4а, Q5а, Q6б, Q7а (+ хвост «хранить отложенные act в world.sim, v11» в BACKLOG 46), Q8а.

## Правки по ревью: ts-review (бывш. docs/decisions/ts-review.md)

**Ревью: партия #22 ТС (T7 обрезка выжимок, BACKLOG 61/46 мягкий пропуск world) — сверка с TS-PLAN §8 (Q1а–Q8а)**

✅ План закрыт: `summary_trim_after=2` (Q1а), все три инструмента через общий `fit_text` (Q2а), тег `summary_trimmed` через `Decision.report_tag` → `ctx.marks` → `result.report_tags` в сцене и главе (Q3а), `soft_failure`/`SOFT_REASONS` перенесены в session.py (Q6б), пропуск world на refusal/invalid/network (Q8а), `refusal_fallback` → `BACKUP_TAG`. Промпт по заготовке (Q5а). Стиль соседний, лишних абстракций нет. `trim_text`: `text[end]` безопасен, потому что `len(text) > limit >= len(head)`.

⚠️ 1 (важно). Записи журнала мягко упавшего world помечаются `committed` — `game/turn.py:take_boundary` (статус берётся только из `done.error`). Ход world не применён, но журнал говорит обратное, и replay/аудит его не отличит. Предлагается: `mark_journal(run_id, "skipped")` (или "aborted"), если `run_id == done.world_run_id and done.world_error`; для этого и нужен `world_error`. Тест — в test_ts_world_skip.

⚠️ 2. `BoundaryResult.world_error` пишется, но никем не читается (его проверяют только тесты). Либо использовать его в п.1 и/или в hint/журнале, либо убрать вместе с тестами. Мёртвое поле с тестом лучше не оставлять.

⚠️ 3. `handlers/summary.py:fit_text` при `summary_trim_after=0` выдаёт «Попытка k из 0; дальше движок обрежет по предложению.» — это неправда: обрезки не будет. Предлагается добавлять хвост «Попытка … обрежет» только при `after > 0`.

⚠️ 4. Род в логе: `accepted("game_summary", …)` даёт «game_summary принята» (было «принят»), а сообщение пустого — «game_summary пустая» (было «пустой»). Предлагается передавать в `accepted`/`fit_text` сразу готовое слово/форму или назвать лейбл «Выжимка игры». Мелочь, но это видно в журнале.

⚠️ 5. Если `summary_trim_after > retry.invalid_retries`, обрезка не наступит никогда — это записано только комментарием в app_defaults.toml. Предлагается проверка в `AppConfig` (model_validator) или хотя бы та же строка в комментарии `MemoryConfig`. Не блокирует.

**Вердикт:** нужны правки (п.1–4; п.5 по желанию).

### Правки оркестратора (2026-10-17)
- п.3 ✅ `fit_text`: хвост «Попытка k из N; дальше движок обрежет» — только при `after > 0`; тест в `test_fit_text_trim_after_zero_never_trims`.
- п.4 ✅ лейбл «Выжимка игры» (принята/пустая); тесты обновлены.
- п.1 — не сделано: summarizer и world пишут журнал под одним run_id границы (`bnd-…`), `mark_journal` размечает по run_id —
  пометить aborted только записи world нельзя без разметки по роли. Оставлено `committed` (риск §7 плана); сбой виден по
  `error`/`stop_reason` записи и тегу `world_skipped`. → вопрос проектировщику / BACKLOG.
- п.2 — `world_error` оставлен: отладочное поле результата границы, покрыт тестами; использовать в п.1, если его сделают.
- п.5 — не делаем (комментарий в toml), как в плане §7.
- п.2 (обновлено): `world_error` убран — vulture поймал неиспользуемый атрибут; причина пропуска видна в записи журнала.
- Доп.: `tests/unit/game/test_turn_capture.py` — `failed_boundary_rig` переведён на `fatal` world (3 invalid теперь пропуск).
- Полный cov: 17120 passed, 1 failed — известный флейк `test_second_ctrl_c_calls_hard_exit_with_130_and_does_not_save`
  (см. ТО); cov 98 %. `make lint` — 193 старых находки qlty (наших файлов среди них нет); smells 200/200; dead чисто.

### Мутанты (57 выживших, список — «Приложение: выжившие мутанты ТС» в конце документа)
Убийство проверено подменой мутации в копии src (`mutmut run` в этом окружении не работает: сбор статистики падает на
`tests/unit/content/test_attribution.py` — в `mutants/` нет README.md; побочно прогон сбросил статусы в `mutmut results`
на «not checked» — для статусов нужен прогон оркестратора). Новые тесты — конец `tests/unit/protocol/test_ts_summary_handlers.py`
(блок «усиление по мутантам») и `tests/unit/game/test_ts_world_skip.py` (`test_call_world_passes_cfg_registry_and_run_id_to_world`).

| Мутант | Итог |
|---|---|
| summary.trim_text 4, 21, 22, 24, 33, 34, 37 | убит (новые тесты trim_text_*) |
| summary.trim_text 5 (`best = -2`), 23 (`best >= 0`) | эквивалентный: best ставится только в >=1, условие `best > 0` отсекает -1/-2 |
| summary.trim_text 25 (`head[:best].lstrip()`) | эквивалентный: срез заканчивается знаком/кавычкой, rstrip — no-op; текст на входе уже strip |
| summary.fit_text 31 (`after > 1`) | убит (`Попытка 1 из 1`) |
| summary.scene_summary 14, 17, 23–27 | убиты (ключ `scene` в summary_overflows, лейбл «Выжимка …» в сообщении) |
| summary.scene_summary 8, 9, 10 | текст `already_done`, старая строка — не трогаем |
| summary.chapter_summary 21 (`title or "XXXX"`) | старая строка, не трогаем |
| boundary.call_world 30 (`cfg=None` в world.run) | убит (тест на аргументы world.run) |
| boundary.call_world 5, 9, 50 | старая строка, не трогаем |
| boundary.BoundaryResult.__init__ 2, 3 | старая строка, не трогаем |
| boundary.close_chapter 7, 8, 58 | старая строка, не трогаем |
| summarizer.run_scene 3, 4, 18, 19, 21, 29, 30, 32, 44, 47, 52, 53 | старые строки (партия добавила только `summary_trim_after`, он в списке не значится), не трогаем |
| summarizer.run_chapter 3, 4, 19, 20, 22, 24, 30, 31, 33, 35, 45, 48, 53, 54 | старые строки, не трогаем |

Итого: убито 16, эквивалентных 3, старых/текст 38.

### Аудит (кабан-свекровь, 2026-10-17)

**Что проверено:** `git diff HEAD` (21 файл: src, доки, тесты), новые `tests/unit/**/test_ts_*.py`, этот файл. Код не правился.

**Источники истины:** docs/plan-ts.md §1–§7 и «Решения проектировщика» 2026-10-16 (Q1а–Q8а); BACKLOG 46/61/64.

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| `trim_text`/`fit_text`/`accepted`, `summary_overflows`/`summary_trim_after`, `[memory] summary_trim_after = 2`, тег `summary_trimmed`, сбор `ctx.marks` | handlers/summary.py, context.py, config, boundary.py | план §1 п.1–2, Q1а–Q3а | оставить |
| `fit_text`: строка «Попытка k из N…» только при `after > 0` (план её давал всегда) | handlers/summary.py | ревью п.3; при дефолте 2 текст как в Q5а | оставить |
| Промпт summarizer_rules.md | prompts | Q5а | оставить |
| `BACKUP_TAG = "summarizer_backup"`, доки ARCHITECTURE/TZ | boundary.py, docs | план п.4 | оставить |
| Пропуск world на мягком сбое, `soft_failure` в session.py | boundary.call_world, session.py | Q6б, Q8а | оставить |
| **`BoundaryResult.world_error` убран**, хотя он есть в плане §1 п.5, §3 шаг 5, §4 (тест `world_error` с `refusal:`) и в списке mutmut | boundary.py, тесты | ревью п.2 + vulture; это отступление от утверждённого плана | к пользователю (по сути разумно: поле никто не читал; причина пропуска есть в записи журнала. Нужно только согласие) |
| Записи мягко упавшего world остаются `committed` | game/turn.py (не тронут) | план §7 — принятый риск | оставить; **но** в правках написано «→ вопрос проектировщику / BACKLOG», а пункта в BACKLOG нет — к пользователю: заводить ли |
| `failed_boundary_rig` переведён на `fatal` world | test_turn_capture.py | следствие Q8а; план §4 так и делает для test_ui_boundary | оставить |
| Лейбл «Выжимка игры» вместо `game_summary`, текст пустой выжимки игры стал «напиши, что произошло» (было «напиши историю игры») | handlers/summary.py | ревью п.4; это журнал и ответ модели, не игроку | оставить (мелочь, решения пользователя тут не нужно) |
| BACKLOG 69, 70 | BACKLOG.md | просьба пользователя (со слов оркестратора; в git этого не проверить) | оставить, если пользователь подтверждает |
| ROADMAP #22 v9→v10, отметки 46/61/T7, хвост act/v11 в 46 | docs | план, Q7а | оставить |
| mutmut по списку **не прогнан**: в правках сказано, что убийство проверяли подменой вручную, статусы mutmut сброшены. 38 выживших списаны как «старая строка» | ts-mutants.txt | критерий §5 выполнен частично | к пользователю: принять ручную проверку или прогнать mutmut у оркестратора |

Сверх плана ничего нет: новых абстракций, фич, зависимостей и правок вне перечисленных файлов не нашла (game/turn.py, world.py, llm/* и схема сейва не тронуты).

**Решения за пользователя:** (1) удалили `world_error` из утверждённого плана; (2) не дали размечать world в журнале как aborted и не завели это в BACKLOG, хотя сами написали «вопрос проектировщику»; (3) критерий mutmut закрыли ручной проверкой.

**Итог:** убирать нечего, нужны решения пользователя по п.1–3.

### Повторное ревью (мама-кабан, 2026-10-17)
- п.3 ✅ хвост «Попытка … обрежет» только при `after > 0`; `test_fit_text_trim_after_zero_never_trims` проверяет отсутствие обоих слов, счётчик при этом растёт.
- п.4 ✅ «Выжимка игры принята/пустая», род согласован во всех трёх инструментах.
- п.2 ✅ `world_error` удалён из src и тестов (grep пуст).
- п.1 — обоснование принято (общий run_id границы, разметка по роли — отдельная задача); нужно занести в BACKLOG, чтобы не потерялось.
- `test_turn_capture.py:failed_boundary_rig` на `fatal` — корректно: сохраняет смысл теста (граница падает), а 3 invalid теперь законно пропуск.
- Тесты мутантов — реальные проверки поведения (граница предложения на limit//2, пробел на индексе 0/1, «Попытка 1 из 1», ключи счётчиков, аргументы world.run), не подгонка. Эквивалентность 5/23/25 подтверждаю.
- Прогон `-k "ts_ or turn_capture or boundary"`: 2445 passed.

**Вердикт:** можно мержить (п.1 — в BACKLOG).

### Решения проектировщика по аудиту (2026-10-17)
1. Удаление `BoundaryResult.world_error` — согласовано.
2. Пометка aborted для записей world — в BACKLOG 71.
3. Мутанты — ручная проверка doeba принята; mutmut-прогон не повторяем (README в mutants/ — известный хвост).

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **#22 ТС ✅ закоммичена 2026-10-17 (сейв v10 без изменений):** план docs/plan-ts.md (papa, fable; Q1–Q8 по рекомендациям). T7: правило предела в summarizer_rules.md, `fit_text`/`trim_text` в handlers/summary.py, `[memory] summary_trim_after = 2` → 3-я переполненная выжимка обрезается по предложению, тег `summary_trimmed` (мерить частоту в ЖП2); 61: тег `summarizer_backup` (старые каталоги — `refusal_fallback`); 46: мягкий сбой world (refusal/invalid/network) → пропуск, тег `world_skipped`, fatal/rounds — меню; act-нарратив теряется (Q7а, хвост в BACKLOG 46). `SOFT_REASONS`/`soft_failure` — в master/session.py. `world_error` из плана убран (согласовано). Ревью, повторное ревью, мутанты, аудит — docs/plan-ts.md. Тесты 17120+ (флейк ctrl_c — тот же), cov 98 %, smells 200/200; mutmut в `mutants/` падает на test_attribution (нет README) — doeba проверял подменой. Агенты (kaban, doeba, mama, svekrov) снова писали без Edit (Write целиком, ex, heredoc) — вопрос Edit открыт. Новые BACKLOG 69 (опыт каждый ход, dusk_academy игрока), 70 (час каждый ход), 71 (журнал по роли). Чек-лист ~/.config/ai-dm/checklists/checklist-ts-live.md (не коммитить). Расход: papa ~125 тыс., kaban ~113 тыс., doeba ~231+58 тыс., mama ~23+18 тыс., svekrov ~35 тыс. **Дальше:** решить про мини-партию 69+70; ЖП по чек-листам ТМ/ТО/ТС (пользователь); Ж0 (#23).

## Приложение: выжившие мутанты ТС (бывш. docs/decisions/ts-mutants.txt)
57 имён `mutmut` до добивки, в виде `<функция>__mutmut_<N>`; вердикты — таблица «Мутанты» выше.
- `ai_dm.protocol.handlers.summary.x_trim_text`: 4, 5, 21, 22, 23, 24, 25, 33, 34, 37
- `ai_dm.protocol.handlers.summary.x_fit_text`: 31
- `ai_dm.protocol.handlers.summary.x_scene_summary`: 8, 9, 10, 14, 17, 23, 24, 25, 26, 27
- `ai_dm.protocol.handlers.summary.x_chapter_summary`: 21
- `ai_dm.game.boundary.xǁBoundaryResultǁ__init__`: 2, 3
- `ai_dm.game.boundary.x_call_world`: 5, 9, 30, 50
- `ai_dm.game.boundary.x_close_chapter`: 7, 8, 58
- `ai_dm.master.summarizer.xǁSummarizerSessionǁrun_scene`: 3, 4, 18, 19, 21, 29, 30, 32, 44, 47, 52, 53
- `ai_dm.master.summarizer.xǁSummarizerSessionǁrun_chapter`: 3, 4, 19, 20, 22, 24, 30, 31, 33, 35, 45, 48, 53, 54
