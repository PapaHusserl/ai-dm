# 41. Флак test_second_ctrl_c_calls_hard_exit_with_130_and_does_not_save
status: done
priority: medium
updated: 2026-10-18

(из ревью Р1, 2026-10-12)
`tests/unit/ui/tui/test_tui_turn.py::test_second_ctrl_c_calls_hard_exit_with_130_and_does_not_save` падает на чистом HEAD
(3ae371f): `[(130, [], 1)] == [(130, [], 0)]` — поток хода успевает применить ход до `hard_exit` (гонка гейта в тесте/TUI).
С Р1 не связан. Починить гейт/синхронизацию в тесте или TUI.

## Закрыто

Ж3, 2026-10-18. План: docs/plan-zh3.md
