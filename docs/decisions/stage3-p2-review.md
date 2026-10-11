# Ревью П2 этапа 3 (мама-кабан): спецификация правок
Решения — оркестратор. K — src/**, docs/**; T — tests/**. Параллельно.
(15 failed в первом прогоне ревьюера — моя ошибочная правка tests/unit/game/test_game_scene.py, откачена; не дефект кода.)

B1. `ensure_chapter(bundle)` — в `GameApp.load` сразу после загрузки (до достройки границы) и в начале `close_boundary`;
    в `close_chapter` — страховка. `started_at_s` восстановленной главы = `current_scene.started_at_s`, если сцена есть.
    Тест: старый сейв без главы → load → глава 1; `end_chapter` при этом пишет title/closed_reason; выжимка первой сцены входит
    в ChapterSummary.
D2. `finish_boundary` ловит только ожидаемые сбои (`TurnFailed`, `LlmError` и будущие ошибки роли world) → меню; прочие исключения
    пробрасываются (бандл не тронут — работа на копии; `boundary_pending` уже в автосейве).
D3. Ввод игрока не теряется: `run_turn` при `boundary_pending` сначала достраивает границу; если достройка упала — строка игрока
    сохраняется как отложенная (`runner.deferred_input`), меню ошибки; `retry` достраивает границу и, если есть отложенная
    строка, играет её как обычный ход. Тест: сбой достройки в run_turn → retry → граница достроена и ход сыгран (turn_seq +1,
    выжимка сцены одна).
D4. `scene_count=1` ставится при создании ChapterState в `campaign/build.py`; костыль в starter убрать.
D5. `retry` при pending вызывает `mark_journal(run_id, committed|aborted)`.
D6. Ветка «save_auto бросил OSError после commit» — описать в stage3-p2-notes.md (не чиним сейчас).
M7–M9. Комментарий TurnResult про on_scene_boundary/этап 4 обновить; ранний return в `load` после упавшей достройки.
T. Тесты UI: вывод «Глава N: …» и блока «За кадром» (и отсутствие пустого блока); retry после сбоя границы через GameApp.
