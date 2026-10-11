# План партии Д1: «хвосты TUI и простого режима» — Ctrl+C при подготовке, тест второго Ctrl+C, `simple.run` с `opening`, многоточие, segfault mutmut, allowlist

Автор: папа-кабан, 2026-10-10. Статус: **предложение на аппрув** (решения проектировщика из `decisions/d1-grooming.md`, раздел
«Решения проектировщика (2026-10-10)», приняты за основу: В1а, В2а, В3а, В6а, В7а, В8а, В9а; В4/В5 — не чинить). Основа: `decisions/d1-grooming.md`
(ТЗ свинопаса + аудит свекрови), `B3-PLAN.md` (форма), `decisions/roadmap-r4-unified.md` (#6 Д1, стр. 168), `BACKLOG.md` 16, HANDOFF
(«Инструменты качества», «Правила экономии»). Код на main f23c9d7 (+ незакоммиченная правка `docs/BACKLOG.md` — снятые пп. 3 и 10, см. A0.10).

**Критерий Д1 (груминг «Готово, когда»):** тесты пп. 1, 2, 5, 8 зелёные (Ctrl+C при подготовке в TUI-режиме печатает строки старта и «Прервано.»,
код 130; тест второго Ctrl+C проверяет состояние в момент жёсткого выхода и после конца потока; `simple.run(opening=…)` делает первый ход из
`opening` без чтения ввода; описание > 120 в `inventory_data` заканчивается «…» и не длиннее 120); `make dead` чисто, в `vulture_allowlist.py`
из четырёх имён остались только нужные с комментарием; `make smells` ≤ 206 (лимит не поднимать, В9а); mutmut по изменённым функциям
(`cli.play`, `master.prompt.inventory_data`/хелпер, `simple.run`), **без `ui.tui.*`**; итог по segfault записан в HANDOFF «Инструменты
качества» и BACKLOG 16 (починено или воспроизведение + правило). Сейв **v8 без изменений**, миграций нет. Живой прогон **не нужен** (R4 стр. 168:
мок — ui/simple тесты). Партия **S**, одна, без деления.

**Не входит:** перенос `PickerApp`/`HeroCreateApp` внутрь `AiDmApp` (В1а — отдельный пункт BACKLOG, при пересмотре Т-4); прерывание потока хода
(В3а); «предмет виден дважды» и «Получено: Опыт» в простом режиме (В4/В5 — не чинить, остаются в BACKLOG 16 как «не горит»); карта боя в панели и
порядок вывода при `ask_hero` (закрыты P3, в BACKLOG уже ✅); переименование кода ради vulture; поднятие `SMELLS_MAX`.

## A0. Поправки фактов (проверено по коду и прогонами, 2026-10-10)
1. **`make smells` = 206/206, запас 0.** `ui/cli.py` уже несёт файловый флаг «High total complexity (252)» и 4 функциональных smell (`main` 8
   параметров; `make_summarizer_adapter`, `hero_flag_refusal` 6 return; `prepare` 17 return / сложность 106). `master/prompt.py` — файловый флаг
   «High total complexity (80)» + `state_data` (22). `ui/simple.py` — `run` 6 параметров, `render` 8 return. Значит: новая ветка в `cli.play`
   (4 параметра, 5 return — на пороге по return, **новых return не добавлять**) и маленький хелпер в `prompt.py` **не дают нового smell** (файловые
   флаги уже посчитаны). Правило: новый код +0.
2. **Ctrl+C при подготовке (п. 1).** `cli.main:416` ловит `KeyboardInterrupt` → «Прервано.», 130. `play:526–547` создаёт `notes = CaptureOutput()`
   в режиме TUI и зовёт `flush_notes` только на раннем `int`-выходе `prepare` и при фолбэке в простой режим. Исключение из `prepare` (вкл.
   `KeyboardInterrupt`) минует оба `flush_notes` — строки в `notes.lines` теряются. **Тот же дефект у любого исключения** из `prepare` в TUI-режиме
   (ветка `except Exception` в `main` печатает только «Ошибка: …») — Q1.
3. **Второй Ctrl+C (п. 2) — проба на коде** (скрипт по образцу `test_tui_turn.py:332`, `hard_exit` подменён, гейт `GateAdapter` открыт до
   `await task`): `hard_exit` вызван с `130`, слотов нет, но **`turn_seq` уже 1** — поток хода успевает применить ход в памяти, потому что гейт
   открывается раньше жёсткого выхода. Автосейва **нет ни сразу, ни через 3 с**: сохранение хода делает не поток (`PlaySession.play` не зовёт
   `save_current`), а выход (`after_exit` → `session.finish()` → `save_current("auto")`, `session.py:85–93`) или граница/меню (`game/app.py:359,
   381`). `asyncio.run` в 3.13 перед возвратом **дожидается** потоков default-executor (`Runner.close` → `shutdown_default_executor`): после
   `run(app, steps)`/`asyncio.run(...)` поток хода уже завершён — ждать его отдельно не нужно, достаточно зафиксировать это комментарием.
   Вывод: буквальная формула В3а («после конца потока `turn_seq` не вырос») в тестовой схеме **ложна** — в тесте поток доживает до конца и
   применяет ход; в процессе его убивает `os._exit`. Что вправе утверждать тест — Q2.
4. **Textual 8.2.8:** при выходе App `workers.cancel_all()` (app.py:3465) — thread-worker **не ждут** (`_run_threaded` → `run_in_executor`,
   worker.py:326); `run_async` возвращается при закрытом гейте — значит `hard_exit` можно вызвать **до** открытия гейта (детерминированный снимок
   «в момент смерти процесса»). `App.run_test` не проходит через `run_async` → в тесте :313 `hard_exit` не вызывается (там `after_exit() == 130`).
5. **`simple.run` с `opening` (п. 5):** `simple.run:71–83` → `PlaySession(opening=)`, в цикле `take_opening()` → при `None` — `source.read`. Тестов
   простого режима с непустым `opening` нет (`test_ui_session.py:80–95` — только `PlaySession`; `test_tui_entry_points.py:910` — `opening is None`).
   `ScriptedAdapter.requests` (llm/mock.py:73–84) хранит запросы — первый запрос должен нести текст `opening`. `slots_kit.ScriptedInput.remaining`
   показывает, сколько строк прочитано.
6. **Многоточие (п. 8):** `master/prompt.py:45` `description[:DESCRIPTION_MAX]` (120) без «…». Прецедент в проекте — `game/battle_map.py:160`
   `text[: width - 1] + "…"` (один символ U+2026). Тест `test_prompt_custom_items.py:99` (`LONG` = 228 знаков) сейчас допускает `len ≤ 121` — его
   ужесточить. Описание — в динамической части (`inventory_data` → `state_data`), кэшируемый префикс не задет.
   **Байты промпта:** в `tests/scenarios/memory_script.py` (WINDOW 22450) и `test_stage4_memory` кастомных предметов с описанием нет; в
   `tests/fixtures/**/*.json` описаний > 100 знаков у **предметов** нет (только у локаций `v4_dragon`/`import/drunk_dragon` — локации не
   обрезаются); журналов `*.jsonl` и replay-эталонов в `tests/fixtures`/`tests/golden` нет (репорты генерируются в тестах). Ожидание: WINDOW и
   replay-тесты не меняются — doeba подтверждает прогоном.
7. **Allowlist (п. 9) — vulture прогнан без четырёх имён** (копия allowlist во временном каталоге): `display` **не нужен** (читается кодом:
   `app.py:156, 158, 173, 386`, `create.py:52`); `border_title` (7 присваиваний: `modals.py:32,78,117,165`, `widgets.py:45,180,274,281`),
   `on_click` (`widgets.py:68,120,158`), `closing` (`app.py:63,135`; читается только тестами `test_commands_both_modes.py:55`,
   `test_tui_entry_points.py:82` — публичный признак для тестов) **нужны** — без них 13 находок. Итог В8а предопределён: снять `display`, три
   оставить с комментарием.
8. **mutmut 3.8.0, Python 3.13.7, macOS.** Режим по умолчанию `process_isolation = "fork"`: главный процесс **сам** импортирует pytest и гоняет
   выбранные тесты в фазе stats (`runners/harness.py:132 pytest.main`), затем `os.fork()` на каждого мутанта (`workers/isolation.py:142`) —
   «every worker inherits whatever the test setup left in that process» (configuration.py:24–33). Есть штатная ручка **`process_isolation =
   "forkserver"`** (`[tool.mutmut]`): родитель чист от pytest, форк-сервер делает `pytest --collect-only` и форкает внуков — «for test setups
   that are not fork-safe». В P2/P5 segfault'ы шли при `TESTS` = весь `tests/` (включая `tests/unit/ui/tui` с Textual/asyncio/thread-worker'ами);
   с AD1 `TESTS` сужают (Му-б: `tests/unit/audio`; Б3: `tests/unit/{…,ui,…}` — **включая `ui/tui`**, segfault в ревью Б3 не отмечен).
   Гипотеза для В7: segfault = fork после прогона Textual-тестов в родителе; проверка и кандидат-фикс — одна конфиг-строка (A4, Q3). Segfault в
   `mutmut results` — код −11/−9 (`stats.py:33–34`). `make mutate` правит sed'ом только строку `pytest_add_cli_args_test_selection` — строка
   `process_isolation` в `[tool.mutmut]` Makefile не задевается.
9. **Автофикстура `tests/unit/audio/conftest.py`** (`sys.modules["miniaudio"] = None`) действует только внутри `tests/unit/audio` — в прогонах
   Д1 (`tests/unit/ui`, `tests/unit/master`) настоящего `miniaudio` нет и так: `attach_sound` не вызывается (`run_tui` подменяется), `audio`
   Му-б не трогаем.
10. **BACKLOG 16 уже правлен в рабочем дереве** (не закоммичено): пп. «карта боя 46 кол.» и «порядок вывода при `ask_hero`» помечены ✅ «(P3,
    снято в груминге Д1)», строка про перенос пикера переписана под В1а. Коммитится **вместе с Д1**, kaban эти строки не переписывает.
11. **Тестов на main — 11 963** (`cov` 96,78 %). Harness TUI-режима для `cli.main`: `test_ui_cli_mode.py` (`fake_terminal`, `real_main`,
    `ran_tui`); harness `prepare` в TUI-режиме: `test_tui_entry_points.prepared()` (`Setup(..., "tui")`, `CaptureOutput` как `notes`);
    фикстура старого мира с предупреждением миграции — `test_cli_migration.py` (`FIXTURE_V5`, `make_world`).

## A. Архитектура (всё — правки в существующем, новых модулей нет)

### A1. Ctrl+C при подготовке мира в TUI-режиме (п. 1, В2а) — `ui/cli.py`
- `play()`: вызов `prepare(...)` обернуть в `try/except`: при исключении — `flush_notes(notes, stdout)` и `raise` (без нового `return`; `main`
  как прежде печатает «Прервано.» и возвращает 130 — порядок «строки старта → Прервано.» получается сам). Ширина `except` — Q1: только
  `KeyboardInterrupt` (буквально В2а) или `BaseException` (та же строка закрывает и «Ошибка: …», A0.2). В простом режиме `notes is stdout` —
  `flush_notes` no-op, поведение не меняется (`test_ctrl_c_ends_with_code_130` зелёный).
- Больше ничего: `prepare` (уже 17 return/сложность 106) не трогаем; `run_tui` не трогаем (внутри Textual Ctrl+C — binding, не исключение).
- Доки: ARCHITECTURE стр. 660–661 (абзац Ctrl+C) — добавить «при подготовке мира в TUI-режиме накопленные строки старта печатаются, затем
  „Прервано.“, код 130»; README стр. 60 — полфразы о том же (техническое умолчание, см. конец).

### A2. Тест второго Ctrl+C (п. 2, В3а) — только `tests/unit/ui/tui/test_tui_turn.py`, кода продукта нет
- Дефект тестов `:313` и `:332`: «сейва нет» проверяется сразу после `release` — пока поток ещё может работать; при этом по A0.3 автосейв потоком
  невозможен в принципе, так что проверка вакуумная, а `turn_seq` не проверяется вовсе.
- Переделка (вариант Q2а, рекомендуемый): **снимок состояния в момент жёсткого выхода при закрытом гейте** + проверка после конца потока.
  - `:332` (`hard_exit` подменён): стаб `hard_exit` записывает `(code, list_slots(...), turn_seq)` **и только затем** открывает гейт
    (`gate_adapter.release.set()`); в `finally` сценария `release.set()` остаётся как страховка от зависания. После `asyncio.run` (поток уже
    дожат, A0.3) — `exits == [(130, [], 0)]`, слотов по-прежнему нет; комментарий: «после выхода поток доживает только в тесте — в процессе его
    убивает `os._exit`; `turn_seq` после конца потока поэтому не утверждается».
  - `:313` (Pilot, `hard_exit` не вызывается): после второго `ctrl+c` и **до** `release` — снимок `(app.return_code/closing, slots, turn_seq)` =
    `(130, [], 0)`; затем `release`, `run` возвращается после конца потока; `after_exit() == 130`, слотов нет.
  - Вариант Q2б (буквально В3а): `GateAdapter` после `hard_exit` **бросает** исключение (имитация смерти процесса) → `PlaySession.play` ловит →
    ход не применён, `turn_seq == 0` и после конца потока. Честно, но тестирует имитацию; не рекомендую.
- BACKLOG 16 строка «P2: второй Ctrl+C … проверяется только отсутствием сейва» → ✅ со ссылкой на тест.

### A3. `simple.run` с `opening` (п. 5) — только `tests/unit/ui/test_ui_simple.py`
- Тесты на `run(app, source, out, opening="Начало.")` (см. B), убивающие трёх выживших P6 (`opening` не передан в `PlaySession`; `take_opening()`
  пропущен; `line = None`). FUNCS: `ai_dm.ui.simple:run`, TESTS `tests/unit/ui/test_ui_simple.py`. BACKLOG 16 «P6: mutmut `ui.simple.run` — 3
  выживших» → ✅.

### A4. Многоточие при обрезке описания (п. 8, В6а) — `master/prompt.py`
- Хелпер `clip(text, limit)` рядом с `DESCRIPTION_MAX`: `text` короче или ровно `limit` → как есть; длиннее → `text[: limit - 1] + "…"` (итог ровно
  `limit`; прецедент `battle_map.py:160`). `inventory_data:45` → `clip(found[1].description, DESCRIPTION_MAX)`. Отдельная функция, не замыкание
  (mutmut, BACKLOG 16). Файл уже под файловым флагом — smells +0.
- Комментарий-контракт в `test_prompt_custom_items.py:3` («не длиннее 120 знаков») уточнить: «обрезка до 119 + „…“».
- BACKLOG 16 (строка партии Б) «Описание кастомного … без многоточия» → ✅.

### A5. segfault mutmut (п. 4, В7а) — исследование с потолком, `pyproject.toml [tool.mutmut]`
- Исполнитель — **kaban-doeba** (mutmut — его зона); kaban `pyproject.toml` в Д1 не трогает (нет гонки за файл).
- **Потолок (одна попытка): ≤ 3 запуска mutmut, ≤ 60 мин wall-clock, FUNCS 1–2 функции.** Протокол:
  - **E1 (контроль):** `make mutate FUNCS="ai_dm.ui.screen:limit_percent ai_dm.ui.screen:status_line" TESTS="tests/unit/ui/test_ui_screen.py"` →
    ожидание: 0 segfault (тесты без Textual).
  - **E2 (воспроизведение):** те же FUNCS, `TESTS="tests/unit/ui/test_ui_screen.py tests/unit/ui/tui/test_tui_turn.py"` → ожидание по гипотезе
    A0.8: в `mutmut results` появляются 💥 segfault (−11) — родитель прогнал Textual-тесты и форкнулся.
  - **E3 (кандидат-фикс, только если E2 воспроизвёл):** в `pyproject.toml` `[tool.mutmut]` добавить `process_isolation = "forkserver"` → повтор
    E2 → ожидание: 0 segfault. Зафиксировать и разницу во времени прогона.
  - Выход за потолок или E2 не воспроизвёл — **стоп**; записать: версии (mutmut 3.8.0, Python 3.13.7, macOS 25.2), команды, результат, и
    закрепить правило обхода.
- Запись результата (doeba в отчёте, kaban переносит в доки): HANDOFF «Инструменты качества» — либо «`process_isolation = "forkserver"`
  включён; segfault при `TESTS` с `tests/unit/ui/tui` не воспроизводится; `ui.tui.*` всё равно не мутируем (дорого)», либо «segfault: fork после
  Textual-тестов; правило — `TESTS` никогда не включает `tests/unit/ui/tui`, `ui.tui.*`/`ui.screen` под Textual не мутировать; воспроизведение —
  E2». BACKLOG 16 строки «P2: … segfault на 21 мутанте» и «P5: segfault (36) и timeout (2)» → ✅ или уточнение с воспроизведением.
  Комментарий в Makefile у `mutate` (kaban) — ссылка на правило/ручку.

### A6. Allowlist vulture (п. 9, В8а) — `vulture_allowlist.py`
- По A0.7: **убрать `display`** (строка 57 блока P2); `border_title` (P2), `on_click`, `closing` (P3) оставить, у каждого — комментарий причины:
  «`border_title` — атрибут Textual, только присваивается»; «`on_click` — обработчик, зовёт фреймворк»; «`closing` — публичный флаг для тестов
  (`test_commands_both_modes`, `test_tui_entry_points`)»; общая пометка блока: «имена глобальные, по файлу vulture не сужает». Остальной allowlist
  не трогать (согласие В8а — только на эти четыре).
- `make dead` чисто. BACKLOG 16 строки «P2: сузить … `display`, `border_title`» и «P3: … `on_click`, `closing`» → ✅ с формулой «сужение по файлу
  невозможно, снято лишнее».

### A7. Документы
ARCHITECTURE (абзац Ctrl+C, A1), README (полфразы, A1), BACKLOG 16 (✅ по A2–A6; строки В4/В5 остаются с пометкой «не чинить, решение
2026-10-10»), `decisions/roadmap-r4-unified.md` стр. 168 — из «Что проверить» Д1 убрать «карта боя в панели» (груминг), HANDOFF («Где мы»: Д1;
«Инструменты качества»: итог В7, `SMELLS_MAX` 206; расходы), `decisions/d1-review.md` (ревью мамы-кабана и решения). Makefile — только комментарий
(A5), `SMELLS_MAX` не меняется.

## B. Партия (одна, S)

### Шаги kaban (src/docs), в порядке зависимостей
1. `master/prompt.py` — `clip`, `inventory_data` (A4). 2. `ui/cli.py` — `play`: try/except вокруг `prepare` с `flush_notes` + `raise` (A1, ширина
по Q1). 3. `vulture_allowlist.py` — снять `display`, комментарии к трём (A6); `make dead`. 4. Makefile — комментарий у `mutate` (A5, после отчёта
doeba). 5. Доки (A7): ARCHITECTURE, README, BACKLOG 16, roadmap-r4 стр. 168, HANDOFF. `make smells` = 206 на каждом шаге.

### Тесты kaban-doeba (tests/**, TDD; плюс исследование A5)
- `tests/unit/ui/test_ui_cli_mode.py` (+), harness `fake_terminal` + `real_main` (A0.11):
  - старый мир `FIXTURE_V5` (копия как в `test_cli_migration.make_world`) + `monkeypatch.setattr(cli, "make_game_adapter", <raise
    KeyboardInterrupt>)` → код 130; в `out.getvalue()` есть текст предупреждения миграции (`context.warning()`) **и** «Прервано.», причём
    предупреждение раньше; «Traceback» нет.
  - вариант без фикстуры: стаб `pick_narrator(args, settings, setup, saves_root, notes)` пишет `say(notes, "строка старта")` и бросает
    `KeyboardInterrupt` → те же проверки.
  - простой режим (`cli(...)` с инжектом) при том же стабе → «строка старта» и «Прервано.» ровно по одному разу (дублей от `flush_notes` нет).
  - при Q1б: стаб бросает `RuntimeError("сломалось")` в TUI-режиме → строки старта, затем «Ошибка: сломалось», код 1.
  - регресс: `test_terminal_starts_tui_with_start_notes`, `test_tui_import_failure_keeps_start_notes` зелёные (строки не печатаются дважды).
- `tests/unit/ui/test_ui_cli_mode.py` или `test_ui_cli.py` (+), уровень `play`: `play(args, ScriptedInput([]), out, Setup(..., mode="tui"))` с
  подменённым `prepare` (пишет в `notes`, бросает `KeyboardInterrupt`) → `pytest.raises(KeyboardInterrupt)`, в `out` строка из `notes`.
- `tests/unit/ui/tui/test_tui_turn.py` — переделка `:313` и `:332` по A2 (Q2): снимок при закрытом гейте `(130, [], 0)`; после конца потока —
  слотов нет; `exits == [130]` ровно один раз; комментарий про `asyncio.run`/`os._exit` (A0.3). Тест `:287` (первый Ctrl+C) не трогать.
- `tests/unit/ui/test_ui_simple.py` (+): `run(app, ScriptedInput([]), out, opening="Начало.")` → `turn_seq == 1`, рассказ хода в `out`, первый
  `adapter.requests[0]` несёт «Начало.» (через `requests_with_tools`/`app.adapter.requests`), «Сохранено: auto.» в конце (ввод кончился);
  `run(app, ScriptedInput(["Иду"]), out, opening="Начало.")` → `turn_seq == 2`, `source.remaining == []`, порядок запросов: «Начало.» раньше «Иду»;
  `opening=None` с `ScriptedInput([])` → `turn_seq == 0`; при `opening` `start()` не показывает последний рассказ (регресс `test_ui_session:92`
  на уровне `run`, если мир с рассказом есть — иначе пропустить).
- `tests/unit/master/test_prompt_custom_items.py` (±): `test_long_description_is_cut_to_120` → `len == 120`, `endswith("…")`, начало совпадает с
  `LONG[:119]`; ровно 120 знаков → без изменений и без «…»; 121 → `LONG[:119] + "…"`; короткое («Ключ от ворот») → как есть; `clip("", n) == ""`.
  Регресс байтов: `tests/scenarios/test_stage4_memory.py` (WINDOW 22450) и `tests/unit/ui/test_cli_reports.py`, `tests/unit/reports/*` зелёные
  без правок (A0.6) — если нет, стоп и сообщить.
- `make dead` после A6 — чисто (doeba подтверждает в отчёте; при желании — проверка «убрать любое из трёх → находки есть», как в A0.7, без
  правки файла).
- **A5 (segfault):** E1–E3 по протоколу, отчёт с командами/кодами/временем; при E3 — строка `process_isolation = "forkserver"` в `pyproject.toml`
  остаётся в партии (Q3).
- mutmut Д1: `make mutate FUNCS="ai_dm.ui.cli:play" TESTS="tests/unit/ui/test_ui_cli_mode.py tests/unit/ui/test_ui_cli.py"`;
  `FUNCS="ai_dm.master.prompt:clip ai_dm.master.prompt:inventory_data" TESTS="tests/unit/master/test_prompt_custom_items.py"`;
  `FUNCS="ai_dm.ui.simple:run" TESTS="tests/unit/ui/test_ui_simple.py"`. Выжившие на старых строках `inventory_data` — в BACKLOG 16, не чинить.
  `ui.tui.*` не мутировать (поведение теста A2 — Pilot, не mutmut).

## C. Качество
- `SMELLS_MAX = 206` не меняется; новый код +0 (A0.1): в `play` без новых `return`/параметров; `clip` — 2 параметра, 1 ветка. Превысили — стоп и
  вопрос (В9а), не поднимать.
- `make cov` ≥ 94 % (новых строк ~10, все под тестами B); `make dead` чисто с allowlist по A6; mutmut по FUNCS выше.
- Полный `pytest` и `make cov` — один раз в конце партии; `make smells` — после каждого шага kaban.
- Коммит — только пути партии: `src/ai_dm/ui/cli.py`, `src/ai_dm/master/prompt.py`, `vulture_allowlist.py`, `Makefile` (комментарий),
  `pyproject.toml` (если E3), `tests/unit/ui/test_ui_cli_mode.py`, `tests/unit/ui/test_ui_cli.py`, `tests/unit/ui/tui/test_tui_turn.py`,
  `tests/unit/ui/test_ui_simple.py`, `tests/unit/master/test_prompt_custom_items.py`, `README.md` (корень), `docs/{ARCHITECTURE,BACKLOG,handoff,D1-PLAN}.md`,
  `docs/decisions/{roadmap-r4-unified,d1-review}.md`. Без `checklist-*.md`, без `saves/`.

## D. Риски
1. **В3а против факта (A0.3):** «turn_seq не вырос после конца потока» в тесте недостижимо без имитации смерти процесса. План предлагает снимок
   в момент `hard_exit` при закрытом гейте — это и есть «что видит процесс перед `os._exit`». Если проектировщик хочет буквально — Q2б.
2. **Зависание теста:** если `hard_exit` не вызовется, гейт останется закрытым — `GateAdapter.release.wait(10)` с `assert` обрывает поток через
   10 с, `finally: release.set()` страхует; `asyncio.run` ждёт executor до `THREAD_JOIN_TIMEOUT` (300 с) — поэтому страховка обязательна.
3. **segfault без потолка** — потолок задан (3 запуска / 60 мин). Гипотеза A0.8 может не подтвердиться (например, segfault от `rich`/`ctypes` в
   форке) — тогда только правило. `forkserver` меняет тайминги mutmut (warmup `--collect-only` на `tests/`) — doeba записывает разницу; если
   прогон заметно медленнее при узких `TESTS`, решение «включать всегда или только при `ui`» — в ревью.
4. **Байты промпта (п. 8):** фикстур/эталонов с описанием предмета > 120 нет (A0.6); если doeba всё же найдёт падение `WINDOW`/replay — стоп,
   не подбирать окно молча.
5. **Двойная печать строк старта:** `flush_notes` при фолбэке (`play:546`) и при исключении — разные ветки, оба не срабатывают вместе; тест на
   «ровно один раз» в B.
6. **`BaseException` (Q1б) ловит и `SystemExit`** — `argparse` вызывает `SystemExit` в `make_parser().parse_args` **до** `play`, внутри `prepare`
   `sys.exit` нет; `raise` без изменений — семантика кодов выхода сохраняется.
7. **Allowlist:** `closing` живёт только ради тестов — альтернатива «сделать свойством/читать в коде» не предлагается (В8: переименования ради
   vulture нет).
8. **`pyproject.toml` правит doeba** (A5) — kaban его не трогает; mama-kaban проверяет, что изменена только секция `[tool.mutmut]`.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1. Ширина `except` в `play` (п. 1).** **(а) `BaseException`: строки старта печатаются и при Ctrl+C («Прервано.», 130), и при любой ошибке
  подготовки («Ошибка: …», 1) — одна строка кода, тот же дефект закрыт целиком (A0.2)**; (б) только `KeyboardInterrupt` — буквально В2а, ошибки
  подготовки в TUI-режиме по-прежнему теряют строки старта.
- **Q2. Что утверждает тест второго Ctrl+C (п. 2, В3а).** **(а) снимок в момент `hard_exit` при закрытом гейте: код 130, сейва нет, `turn_seq == 0`;
  после конца потока — сейва по-прежнему нет; `turn_seq` после конца потока не утверждается (в тесте поток доживает, в процессе его убивает
  `os._exit` — A0.3)**; (б) буквально В3а: `GateAdapter` после `hard_exit` бросает исключение (имитация смерти процесса) → `turn_seq == 0` и после
  конца потока — тестируется имитация, kit усложняется.
- **Q3. Исследование segfault (п. 4, В7а).** **(а) протокол E1–E3 (A5), потолок 3 запуска / 60 мин; кандидат-фикс — `process_isolation =
  "forkserver"` в `[tool.mutmut]`, строку ставит doeba, остаётся в партии, если E3 убрал segfault; правило «`ui.tui.*` не мутировать» сохраняется
  (дорого), снимается только запрет на `TESTS` с `ui/tui`**; (б) только E1–E2 (воспроизведение) и правило в HANDOFF, конфиг не трогать;
  (в) без исследования — сразу правило (В7 закрывается записью).
- **Q4. Перенос пикера (В1а) — место в BACKLOG.** **(а) оставить строку в BACKLOG 16 как сейчас в рабочем дереве («не Д1 … при пересмотре Т-4»),
  в R4 не добавлять** (аудит просил «назвать место»: место — пересмотр Т-4, партии нет); (б) завести отдельный номер BACKLOG и строку-кандидат в
  R4 «после Ж3» (решение по очереди — проектировщика).

**Технические умолчания на аппрув вместе с планом:** `clip(text, limit)` в `master/prompt.py` рядом с `DESCRIPTION_MAX`; символ «…» U+2026, итог
ровно 120 при обрезке, ровно 120 знаков — без «…»; `flush_notes` + `raise` в `play` (не в `main`), порядок вывода «строки старта → Прервано.»;
тесты второго Ctrl+C — снимок через стаб `hard_exit`/до `release`, страховочный `release.set()` в `finally`; `display` снят из allowlist, три
имени с комментариями; BACKLOG 16 — пометки ✅ (строки не удаляются), В4/В5 — пометка «не чинить (2026-10-10)»; README — полфразы про Ctrl+C
при подготовке; R4 стр. 168 — «карта боя в панели» убрана из «Что проверить» Д1; mutmut Д1 по трём FUNCS выше; `SMELLS_MAX` 206; сейв v8;
живого прогона нет.

## Решения проектировщика по Q (2026-10-10)

Q1а (`BaseException`), Q2а (снимок в момент `hard_exit`), Q3а (E1–E3, потолок 3 запуска / 60 мин, `forkserver` остаётся при
успехе, правило «`ui.tui.*` не мутировать» сохраняется), Q4а (строка в BACKLOG 16, в R4 не добавлять) — все по рекомендациям.
