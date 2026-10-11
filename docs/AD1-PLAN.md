# План партии AD1 «Надёжность + долг конвейера» (papa-kaban, 2026-10-08)

Основание: docs/ROADMAP-PLAN.md (решения 2026-10-08, блок AD, разд. 5, вопросы AD-1/AD-2 — отвечены),
docs/BACKLOG.md п. 3, 12, 16, 30; docs/decisions/roadmap-cost-review.md (предложение 4); код сверен 2026-10-08.
Размер M (~0,3–0,4 млн ток.). **Сейв v7, миграции нет.** Живой прогон не нужен; живые миры играть можно.
Решения проектировщика: AD-1 — флаг `[persistence] durable`, по умолчанию включён; AD-2 — убрать 5–10 находок smells, лимит 210 оставить.

**Задача:** fsync сейва, устойчивый `PlaySession.submit`, досрочный выход summarizer, экранирование ``` в report.md,
разбор `make dead`, `make mutate` по функциям/методам, запас по smells, правило конвейера «doeba = diff + функции».

## 1. Состав работ (kaban)

### W1. Durability сейва (п. 3) — `src/ai_dm/persistence/`
1. Новый модуль `persistence/durable.py` (чистые помощники, по образцу `backup.py`):
   - `sync_file(fd)`: на macOS `fcntl.fcntl(fd, fcntl.F_FULLFSYNC)`; нет атрибута / `OSError` → `os.fsync(fd)`.
   - `sync_dir(path)`: `os.open(path, os.O_RDONLY)` → `sync_file` → `os.close` (в `finally`).
   - флаг модуля `DURABLE = True` + `set_durable(flag)` (см. вопрос Q1).
2. `store.write_text`: при `DURABLE` — писать через `open(..., "w")`, `flush`, `sync_file(f.fileno())`; без флага — как сейчас.
3. `store.write_slot`: порядок — все файлы (fsync каждого) → `sync_dir` подкаталогов `tmp/world`, `tmp/heroes/<h>`, `tmp`
   → `os.replace(final, old)` / `os.replace(tmp, final)` → `sync_dir(slots)` (каталог слотов) → `sync_dir(slots.parent)`
   (каталог мира) → `rmtree(old)`. Ошибка fsync до replace = ошибка записи (старый слот цел, tmp удаляется существующим `except`).
4. `store.move_slot`: fsync `manifest.json.tmp` + `sync_dir(dst_dir)` + `sync_dir(slots)` после replace.
   `save_auto` (ротация auto-N) — `sync_dir(slots)` один раз в конце ротации, до `save_slot`.
5. Конфиг: `config/app_defaults.toml` — секция `[persistence]` `durable = true`; `config/app.py` — `PersistenceConfig`
   (`extra="forbid"`, `durable: bool = True`) в модели приложения. `ui/cli.py::prepare` (единая точка старта) — `set_durable(cfg.persistence.durable)`.
6. Тесты: корневой `tests/conftest.py` (новый, autouse) — `set_durable(False)` (ускорение; см. Q1). `reports/writer.py`
   (`write_slot` снимков before/after) — durable тоже действует, отдельно не трогать.

### W2. `PlaySession.submit` (п. 16) — `src/ai_dm/ui/session.py`
Сейчас `try` охватывает только `app.choose/app.handle`; `loot_snapshot`, `hero_of`, `reply_blocks`, `turn_events`,
`screen_blocks`, `status_block`, `limit_state` — вне его, исключение роняет worker TUI. Автосейв делается внутри `handle`.
1. Разбить `submit` на `submit` (разбор строки, limit_menu) → `apply_line(line)` (выбор/ход, текущий `try`) → `render_step(app, reply, ...)`.
2. Исключение **до** хода (snapshot/hero_of) → `Step([note "Ошибка хода: …"])`, ход не применён, сейв не тронут.
3. Исключение **после** хода (рендер) → `Step([note "Ход сделан и сохранён, но экран не обновился: …"]) + status_block`
   (если и он падает — только заметка). Текст через `redact(..., self.secrets)`. В replay — `quit=True, exit_code=1`, как сейчас.
4. Строки — в `ui/tui/strings.py`? Нет: заметки `session.py` живут в нём самом — оставить там (стиль файла).
Касается обоих режимов (simple и TUI) — у обоих один `PlaySession`.

### W3. offered_choices: цифра при скрытых вариантах (п. 16, P3)
Без изменения game/промпта/relevance (влияние на рассказчика не трогаем): в `PlaySession` вынести из
`ui/tui/app.py::stale_offer` логику «варианты устарели» в `ui/session.py` (`offer_is_stale(app)`), `submit` подставляет
вариант по цифре только если `not offer_is_stale`; TUI `stale_offer` вызывает её же. В простом режиме варианты
показываются всегда — см. Q3 (рекомендация: одинаково в обоих режимах — номер устаревшего варианта не подставлять).

### W4. Досрочный выход summarizer (п. 12) — `src/ai_dm/master/session.py::MasterSession.run`
1. В ветке `elif calls:` после разбора раунда: если `self.role == "summarizer"` и `required_done` и `not has_invalid`
   (для `summarize_chapter` — уже гарантировано проверкой обоих инструментов) → `result.texts += texts`, собрать
   `narration` и `return result` без следующего вызова модели. Нарратор/world — без изменений.
2. Попутно (smells, W7): вынести тело разбора раунда в `run_round(ctx, calls, executor, allowed, result, mode, required)`
   → `(blocks, has_invalid, required_done)`; `required_tool` — таблица `REQUIRED_BY_MODE` + два особых случая.
3. Фикстуры: убрать завершающий шаг `text: "Готово."` после вызова инструмента summarizer —
   `tests/fixtures/scripts/summarizer_scene.yaml`, `tests/unit/game/summarizer_kit.py`, `chapter_kit.py`,
   `tests/scenarios/memory_script.py`, тесты `test_game_chapter_summary.py`, `test_game_summarizer_boundary.py`,
   `test_master_session_loop.py` (только шаги роли summarizer; у world «Готово.» остаётся). WINDOW мока не меняется
   (summarizer в окно нарратора не входит) — проверить. Старые репорты 6а с лишним вызовом replay может не пройти — Q4.

### W5. report.md: ``` внутри текста (п. 30) — `src/ai_dm/reports/markdown.py`
`fence(text)`: длина ограды = max(3, самая длинная серия ` в тексте + 1); `message_lines`/`call_lines` используют её
вместо литерала "```". Источник истины — calls.jsonl, replay не задет. «WINDOW +6» — закрыть в BACKLOG 30 без исследования.

### W6. `make dead` (30 находок) — решение по каждой (список ниже, согласие — Q2)
- Удалить (мёртвые, тестами не держатся — kaban проверяет grep по tests/): `game/starter.py::__getattr__`, `ranger_choices`,
  `new_world` (если шим совместимости — проверить); `game/tone.FREE_SCALES`; `game/turn.preview_turn_state`;
  `protocol/requests.VISIBLE_TYPES`; `config/settings.spread_morale` (только если нет в defaults.toml — иначе поле конфига, в allowlist).
- Записываемые, но не читаемые атрибуты (`scene_closed`, `chapter_ended`, `verdict_reasons`): удалить запись, если нет читателей в tests/.
- Используются только тестами/будущим (в allowlist с комментарием «тесты»/«К0/Ж2»): `combat/controllers.Controller/ScriptedController`,
  `llm/adapter.ModelAdapter` (протокол), `llm/replay.group_runs`, `store.list_slots`, `ui/io.ScriptedInput`,
  `rules/checks.passive_check`, `rules/divine.change_deity` (Ж2), `rules/inventory.unequip`, `rules/money.to_cp`,
  `rules/progression.level_for_xp/proficiency_bonus` (К0).
- API Textual: `highlighted`, `on_option_list_option_highlighted`, `action_complete` — в allowlist точечно `ui/tui/*`.
Итог: `make dead` зелёный. vulture_allowlist правится только после согласия (Q2).

### W7. `make smells` ≤ 200 (AD-2: −5…−10)
Цели (те файлы, что партия и так трогает, + дубль тестов):
- `master/session.py`: 3× «deeply nested» (214–218) и сложность `run` (88) — через `run_round` (W4); `required_tool` many returns — таблица. (−4…−5)
- `ui/session.py::submit` many returns + complexity — через разбиение (W2). (−2)
- `tests/unit/combat/combat_kit.py:138` ↔ `tests/unit/protocol/protocol_kit.py:143` — 18 одинаковых строк, вынести в общий kit (kaban-doeba). (−2)
Итого −8…−9; `SMELLS_MAX` в Makefile опустить до фактического значения (ratchet).

### W8. `make mutate` по функциям и методам — `Makefile`
Новая переменная `FUNCS` (пробел-разделённо, `модуль:функция` или `модуль:Класс.метод`), разворачивается в шаблоны mutmut
`ai_dm.mod.x_func__mutmut_*` и `ai_dm.mod.xǁClassǁmethod__mutmut_*`; без `FUNCS` — старое поведение `MOD`. Комментарий
с примером в Makefile; строка в HANDOFF «Инструменты качества». Проверить на `ui.session:PlaySession.submit`.

### W9. Конвейер (решение 4) — правило, не код игры
Агенты лежат в `~/.claude/agents/` (глобально, общие с другими проектами) — см. Q5. Рекомендация: не трогать глобальные
файлы; правило записать в docs/HANDOFF.md «Правила экономии» п. 7: «kaban-doeba получает diff партии и список
изменённых функций (`модуль:функция`), mutmut — `make mutate FUNCS=…`; разбор выживших — отдельным вызовом меньшей модели
(sonnet/haiku) по выводу `mutmut results`». Оркестратор подставляет это в задание.

### W10. Документы
BACKLOG: п. 3, 12 закрыть; п. 16 — вычеркнуть submit, make dead, шаблон mutate, offered_choices; «архив мутантов» —
отдельной строкой «не делать, пока модуль не трогают»; п. 30 — ``` и WINDOW+6 закрыть. HANDOFF — строка AD1, расходы.
Ревью — docs/decisions/ad1-review.md.

## 2. Тесты (kaban-doeba, TDD; вход — этот план, затем diff + список функций)
Durability (`tests/unit/persistence/test_store_durable.py`):
- `DURABLE=True`, подмена `os.fsync`/`fcntl.fcntl`/`os.replace` записывающими шпионами → порядок: fsync всех 5+N файлов
  → fsync каталогов tmp → replace → fsync `slots` → fsync каталога мира.
- macOS-ветка: `fcntl` с `F_FULLFSYNC` бросает `OSError` → вызван `os.fsync`; нет атрибута `F_FULLFSYNC` → `os.fsync`.
- fsync файла бросает `OSError` → исключение наружу, старый слот на месте и читается, `.tmp-*` удалён.
- `DURABLE=False` → ни одного fsync. `move_slot`/`save_auto` при durable — fsync каталога слотов.
- `sync_dir` закрывает дескриптор и при ошибке fsync.
- Конфиг: `[persistence] durable` по умолчанию true; неизвестный ключ → ошибка валидации; `prepare` вызывает `set_durable`.
submit (`tests/unit/ui/test_session_submit_errors.py`):
- `loot_snapshot` бросает → заметка «Ошибка хода», сейв auto не изменился (mtime/содержимое), сессия живёт, следующий ввод работает.
- `reply_blocks`/`screen_blocks` бросает после хода → заметка «Ход сделан и сохранён…», auto содержит ход.
- секрет в тексте исключения редактируется; replay-режим → `quit, exit_code=1`.
- TUI (pilot): исключение в рендере → App не падает, заметка в ленте.
offered_choices:
- устаревшие варианты (последний ход без offer_choices) + «1» → строка «1» уходит как ввод, не вариант; свежие → вариант. Оба режима.
summarizer (`tests/unit/master/test_master_session_loop.py`, game-тесты границы):
- summarize_scene: ответ с `scene_summary` accepted → ровно 1 вызов модели (журнал/requests), выжимка записана.
- summarize_chapter: оба инструмента в одном ответе → 1 вызов; только один → повтор (как сейчас).
- `scene_summary` invalid → повтор; clamped → считается принятым.
- нарратор/world после раунда инструментов по-прежнему делают финальный вызов (регресс).
- мок-сценарии tests/scenarios (stage4_memory и др.) зелёные; число summarizer-записей в журнале уменьшилось.
markdown: текст с ``` и ```` → ограда длиннее, md корректен (нет преждевременного закрытия); без ``` — как раньше (golden).
make dead/smells: дубль kit-ов вынесен, тесты зелёные.
Мутации: только изменённые функции — `durable.*`, `store.write_text/write_slot/move_slot/save_auto`,
`PlaySession.submit/apply_line/render_step/offer_is_stale`, `MasterSession.run/run_round/required_tool`, `markdown.fence/message_lines/call_lines`.

## 3. Критерии приёмки
- `uv run pytest -q` зелёный (один раз в конце), `uv run ruff check src tests` чист.
- `make cov` ≥ 94%; `make smells` ≤ 202 и `SMELLS_MAX` опущен до факта; `make dead` зелёный.
- `make mutate FUNCS="…" TESTS="…"` по функциям из п. 2 — 0 выживших на новых строках (кроме эквивалентных/текстовых,
  перечислить в ревью); старые выжившие — в BACKLOG 16.
- `make linux-check` зелёный (fsync каталога и отсутствие F_FULLFSYNC на Linux).
- Ручной: сейв/загрузка живой копии мира во временном каталоге (не saves/) — без регресса.

## 4. Открытые вопросы проектировщику (с рекомендацией)
- **Q1.** Как прокидывать `durable`: флаг модуля `persistence.durable` (выставляется в `prepare`, в тестах выключен
  корневым conftest) или параметр через `write_slot/save_slot/save_auto/GameApp/reports.writer`? **Рекомендация:** флаг модуля —
  одна точка, не трогает ~10 сигнатур и тесты; durable-путь покрыт отдельными тестами.
- **Q2.** Согласие на vulture_allowlist для ~14 имён (тестовые помощники, протоколы, будущие К0/Ж2, API Textual) и удаление
  ~9 мёртвых. **Рекомендация:** да, по списку W6; спорные (`change_deity`, `level_for_xp`) — allowlist с пометкой блока.
- **Q3.** offered_choices в простом режиме: не подставлять устаревший вариант по цифре и там? **Рекомендация:** да, одно поведение.
- **Q4.** Старые репорты 6а (с лишним вызовом summarizer) после п. 12 могут не воспроизводиться `--replay-report`
  (код 1 «расхождение»). **Рекомендация:** принять; в сообщении — версия формата уже есть; живых репортов с границей сцены единицы.
- **Q5.** Правило doeba/мутантов (решение 4): в HANDOFF (проектное) или править глобальные `~/.claude/agents/kaban-doeba.md`
  (действует и в msa)? **Рекомендация:** HANDOFF + шаблон задания оркестратора; глобальные агенты не трогать.
