# 211. ruff красный на HEAD: 16 ошибок
status: done
priority: medium
updated: 2026-10-28

`uv run ruff check src tests` на HEAD a870c1e (worktree, шаг 209) — 16 ошибок: src/ai_dm/config/app.py, 4 в
tests/unit/ui/tui/test_tui_entry_points.py (E501), по одной в 11 файлах tests/unit (config, game_kit, llm, master,
protocol, reports_kit, rules). Не от шага 209; причина не установлена.

## Закрыто
Шаг 211, 2026-10-28 — docs/plan-211.md.
