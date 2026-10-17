# План мини-партии #22 «ТС Summarizer и границы» (T7 + BACKLOG 61 + BACKLOG 46)

Автор: papa-kaban (fable), 2026-10-16. Статус: **на аппрув** (Q1–Q8 в §8). Груминга нет (техдолг по правилу фикса, прецеденты TV/TM/TO-PLAN). Smells 200/200 — нулевой баланс. Сейв: **v10 без изменений** (строка ROADMAP #22 «v9» устарела — поправить).
Источники: ROADMAP #22; roadmap-r6-proposal.md §2 «ТС»; BACKLOG 46, 61, 64 (T7); tech-debt-2026-10-14.md T7, §4 п.5; R2-PLAN (В13а, В14а, Q3), T60-PLAN, B59-PLAN п.7; ARCHITECTURE E3 (стр. 637), TZ.md:606.

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
`protocol/handlers/summary.py`, `protocol/context.py`, `master/summarizer.py`, `master/session.py`, `master/prompts/summarizer_rules.md`, `game/boundary.py`, `config/app.py`, `config/app_defaults.toml`. Без изменений: `game/turn.py`, `game/app.py`, `master/world.py`, `world_sim/*`, `llm/*`, схема сейва. Доки: ARCHITECTURE E3, TZ.md:606, шапки `summarizer_kit.py`/`world_kit.py`, BACKLOG 46/61/64, ROADMAP #22 (v10), handoff, `docs/checklist-ts-live.md` (не коммитить).

## 3. Шаги kaban
1. `session.py`: перенос `SOFT_REASONS`, `soft_failure`; `summarizer.py`: импорт.
2. `context.py`, `config/app.py`, `app_defaults.toml`: `summary_trim_after`, `summary_overflows`.
3. `handlers/summary.py`: `trim_text`, `fit_text`, три хендлера; `run_scene/run_chapter`.
4. `summarizer_rules.md` по Q5.
5. `boundary.py`: `BACKUP_TAG`, сбор `ctx.marks`, `try/except` в `call_world`, `BoundaryResult.world_error`. `make smells`.
6. Офлайн-гейт: `ai-dm --mock` код 0; мок-сценарий в scratchpad — summarizer три шага ~750/680/640 → граница за 3 вызова, ≤ 600, граница предложения, `source == "summarizer"`, тег `summary_trimmed`; world `{"stop": "refusal"}` → граница завершена, `boundary_pending False`, `world_skipped`, следующий ход сразу. `--replay-report` копии t429 — расхождение на 3-м вызове ожидаемо.
7. Доки; `docs/checklist-ts-live.md`.

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
