# 209. Тесты окна выбора модели в TUI падают на HEAD
status: done
priority: medium
updated: 2026-10-27

`make cov` шага 207 П1 (docs/plan-207.md): падают test_tui_live1.py::test_model_window_enter_picks_highlighted_current_model,
::test_model_window_down_enter_picks_next_model и test_tui_live1_edges.py::test_model_window_marks_only_current_and_has_title
(список моделей пуст, `assert 0 == 1`); на HEAD a288984 в worktree — тоже. Причина не установлена.
`test_digit_key…` при повторе прошёл. Гипотеза оркестратора — зависят от пользовательского `config.toml`,
не проверена. Найти причину и починить или изолировать. Источник — отклик Декарта семьи кабанов
`~/projects/semia-kabanov/otkliki/dekart/2026-10-27-ai-dm-207-p1-sh20-dolg.md` (Н5), решение Влада 2026-10-27.

## Закрыто
Шаг 209, 2026-10-27 — docs/plan-209.md.
