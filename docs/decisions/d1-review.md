# Ревью партии Д1 (черновик)

Статус: черновик kaban, ревью мамы-кабана ещё не проведено. Решения проектировщика: Q1а, Q2а, Q3а, Q4а (docs/D1-PLAN.md, конец).

## Что сделано (kaban, src/docs)
- `master/prompt.py`: `clip(text, limit)`; `inventory_data` режет описание до 120 с «…» (119 + «…»).
- `ui/cli.py`: `play` — `try/except BaseException` вокруг `prepare`: `flush_notes` + `raise`. Новых return/параметров нет.
- `vulture_allowlist.py`: снят `display`; `border_title`, `on_click`, `closing` оставлены с комментариями.
- Makefile: комментарий у `mutate` (уточнить по итогу E1-E3 doeba).
- Доки: ARCHITECTURE (Ctrl+C), README, BACKLOG 16, roadmap-r4 стр. 168.

## Остаётся
- Тесты и исследование segfault (E1-E3) — kaban-doeba.
- HANDOFF — оркестратор.
- Итог ревью и решения — после ревью мамы-кабана.

## Ревью мамы-кабана (2026-10-10)

Проверено: git diff src/ai_dm/{master/prompt.py,ui/cli.py}, vulture_allowlist.py, Makefile, pyproject.toml, README, ARCHITECTURE, BACKLOG 16,
roadmap-r4 стр. 168 — против D1-PLAN (A0–A6, C, «Решения проектировщика по Q») и d1-grooming. Тесты doeba не оценивались (в работе).

Хорошо: `play` — `except BaseException` + `flush_notes` + `raise` ровно по Q1а, без новых return/параметров, в простом режиме
`notes is stdout` — дублей нет; `clip` — 2 параметра, 1 ветка, 119 + «…» = 120 (A3); allowlist по A0.7/A6 (`display` снят, он
читается в widgets.py:104); roadmap стр. 168 без «карты боя»; В4/В5 помечены «не чинить».

1. **[высокий] pyproject.toml** — `pytest_add_cli_args_test_selection = ["tests/unit/ui"]` вместо `["tests/"]`. Это не правка
   плана (Q3а разрешает только строку `process_isolation = "forkserver"` при E3), похоже на след прерванного `make mutate TESTS=…`
   или эксперимента E1–E3. В коммит не брать: вернуть `["tests/"]`; если E3 дал результат — добавить только `process_isolation`.
2. **[средний] Makefile** — комментарий у `mutate` с заглушкой «уточнить по итогу E1-E3 doeba». До коммита заменить итогом
   (починено forkserver'ом / воспроизведение + правило «ui.tui.* не мутировать»), иначе в репо уедет TODO.
3. **[средний] BACKLOG 16** — две строки про segfault (P2 ui.screen, P5) отмечены ссылкой «см. HANDOFF», но ни ✅, ни правила нет;
   после отчёта doeba дописать итог в саму строку (критерий Д1: «итог записан в HANDOFF и BACKLOG 16»).
4. **[низкий] BACKLOG 16** — «✅ (Д1) P3: Ctrl+C во время подготовки мира … — не затронуто P3, остаётся.»: хвост «остаётся»
   противоречит ✅ и дублирует первую ✅-строку про Ctrl+C. Предлагается удалить строку или сократить до «✅ (Д1) P3: … — см. выше».
5. **[низкий] ARCHITECTURE F4** — «при любом исключении» + «затем «Прервано.», код 130» читается так, будто любая ошибка даёт 130.
   Уточнить: «Ctrl+C — «Прервано.», 130; прочая ошибка — «Ошибка: …», 1».

Вердикт: после пп. 1–2 (и 3 по отчёту doeba) — можно мержить; пп. 4–5 по желанию.

## Итог doeba
- Тесты: 12436 passed / 1 xfailed, cov 96,83 %.
- Мутации: `clip` 0 выживших; `simple.run` 0 (было 3); `play` 0 (14 segfault-статусов убиты прогоном с test_cli_import/test_stage6a_done); `inventory_data` 4 старых выживших (quality, BACKLOG 16).
- Segfault mutmut: E1/E2 без segfault, E2b (TESTS=tests/unit/ui) — 4 segfault на status_line, E3 forkserver — ChildProcessError -6 в stats (_scproxy). Правило записано в Makefile и BACKLOG 16.
