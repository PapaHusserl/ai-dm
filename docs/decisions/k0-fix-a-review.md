# Ревью К0-фикс-а (шаги 1–6 docs/K0-FIX-PLAN.md), мама-кабан, 2026-10-12

Проверено: `git diff` src/tests/docs, новые tests/unit/protocol/test_improvise_effect.py,
tests/unit/llm/test_llm_gemini_safety.py; `uv run pytest -q` — 13452 passed, 1 xfailed.
`make cov / smells / dead / ruff` в ревью не запускались — kaban прогоняет перед коммитом.

## Что хорошо
- План шагов 1–5 выполнен полностью, решения проектировщика Q1–Q8 (все «а») соблюдены: `ImproviseEffect` в
  `state/combat.py`, `EFFECTS = get_args(...)`, `spec_problem` вынесен без изменения кодов движка, `Invalid` с
  подсказкой в `player_action` после `no_active_combat`, правила (п.1.5, 2, 3) — дословно по плану, ручка
  `gemini_safety` с дефолтом `block_none`, `safety_settings` в обеих ветках `build_config`, `stop_detail` в
  журнале/сессии/репорте, F2 через класс `closed` + сброс при смене режима.
- Стиль соседних мест сохранён (`IMPROVISE_HINTS` как `SETUP_HINTS`, `NEUTRAL` с `"none"` как у `SkillOrNone`).
- Тесты закрывают план, а не подогнаны: проверены сообщения подсказок, неизменность состояния, реальные типы SDK,
  кэш-ветка, старые записи без `stop_detail`.

## Замечания
- [low] Список эффектов захардкожен строкой трижды: `IMPROVISE_HINTS["unknown_effect"]`
  (protocol/handlers/combat.py), `ValueError` в `PlayerAction.cut_improvise` (protocol/requests.py), правила.
  Для кода — `", ".join(EFFECTS)` / `get_args(ImproviseEffect)`, чтобы новый эффект не разошёлся с подсказкой.
  Правила — оставить текстом (их держит test_master_rules).
- [low] `stop_detail` vs `stop_reason` для `BLOCKED_REASON_UNSPECIFIED` (заметка doeba 4): `stop_reason` даёт
  `other`, а `stop_detail` — `"BLOCKED_REASON_UNSPECIFIED"`. Это не баг: для `other` detail идёт только в журнал/репорт
  (TurnFailed пишет detail лишь при refusal) и полезен для диагностики. Но поведение не зафиксировано тестом —
  добавить тест на `block_reason=BLOCKED_REASON_UNSPECIFIED` → `stop_reason="other"`, `stop_detail` = имя (или
  явно None — см. В-1).
- [low] `target_required` для неизвестного ref (`test_unknown_target_ref_is_target_required`) — текст «эффект X
  требует target» модель может понять как «target пуст». Можно добавить `{target!r}` («target 'xx' не найден»), но
  это не в плане — по желанию.
- [info] Заметка doeba 1: `PlayerAction.cut_improvise` под `@model_validator` — mutmut его не мутирует. Ветка
  покрыта прямыми тестами (`test_effect_none_with_skill_and_category_requires_effect`,
  `test_missing_effect_...`); выносить логику в функцию ради mutmut не нужно (в репо так же `cut_parley`).
  Убрать `PlayerAction.cut_improvise` из списка FUNCS плана/отчёта, отметить «покрыто тестами, mutmut не видит».
- [info] Заметка doeba 2: перечисленные тесты с `press("f2")` (test_tui_art.py:194, test_tui_russian.py:48,
  test_tui_live1.py:174, test_tui_turn.py:83, test_tui_entry_points.py:936) запускаются в **(100, 40)**, а не
  140×40 (см. `run(app, steps, size=(100, 40))`); файлы не изменены. Смысл не потерян — они проверяют узкий режим,
  где F2 по-прежнему открывает панель. test_tui_combat_menu.py:572/587 — (80, 24), тоже узкие. Широкий F2 покрыт
  новыми тестами test_tui_layout.py.
- [info] Заметка doeba 3: WINDOW 22450→23000 в tests/scenarios/memory_script.py обоснован комментарием (рост
  narrator_rules.md на ~1 абзац, пик 17986 > 17960). Принять; на будущее это значит, что каждый рост правил
  двигает окно — уже в духе Р1 «Память боя», отдельной правки не требует.
- [info] Заметка doeba 5 (stash/pop): `git stash list` пуст; все пункты шагов 1–6 в рабочем дереве на месте, оба
  новых тест-файла и правки 10 тестовых файлов присутствуют, полный pytest зелёный. Признаков потери нет.
  Неотслеживаемые файлы (`??`) stash по умолчанию не трогает — их потеря исключена.
- [info] docs/BACKLOG.md в том же диффе несёт посторонние записи (38 к, 39, 40) — это не код партии, но попадут в
  коммит К0-фикс-а; нормально, если так задумано (39 — следующая подпартия).

## Вопросы проектировщику
- **В-1. `stop_detail` при `stop_reason=other`** (в т.ч. `BLOCKED_REASON_UNSPECIFIED`, `MALFORMED_FUNCTION_CALL`):
  (а) **рекомендация** — оставить как есть (имя причины пишется всегда, кроме STOP/MAX_TOKENS/tool_use; для Р2 это
  данные), добавить тест; (б) писать detail только при `refusal`.
- **В-2. Список эффектов в подсказках:** (а) **рекомендация** — собирать из `EFFECTS` в коде; (б) оставить
  литералом (проще читать, риск расхождения при новом эффекте).

**Вердикт:** можно мержить после low-правок (или с ними в BACKLOG); блокирующих замечаний нет.

## Решения проектировщика (2026-10-12)
- В-1 (а): stop_detail пишется и при stop_reason=other — закреплено тестами (test_llm_gemini_safety.py).
- В-2 (а): список эффектов в подсказках собирается из EFFECTS / get_args(ImproviseEffect).
- Итог: тесты 13452+ passed (полный прогон до В-1/В-2; после — protocol/llm/combat 3507 passed), smells 205/206, dead чисто.
  mutmut: cut_improvise не виден mutmut (@model_validator) — покрыт прямыми тестами. Выжившие на старых строках
  (player_action, parse_response, stop_reason, markdown "") — BACKLOG 16 по правилу 4.
- Расходы: kaban ~80+82 тыс. (~22 мин); kaban-doeba ~178+179 тыс. (~76 мин, mutmut); mama-kaban ~53 тыс.
