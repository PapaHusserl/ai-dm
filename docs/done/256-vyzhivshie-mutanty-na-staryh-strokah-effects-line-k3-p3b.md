# 256. Выжившие мутанты на старых строках effects_line (К3 П3б)
status: done
priority: low
updated: 2026-11-15

(разбор мутантов К3 П3б, правило 4 AGENTS — docs/plan-k3.md, «Старые мутанты П3б»)
Выжили на строках до партии: `ai_dm.rules.inventory.effects_line` — 3, 5, 39, 41, 58, 59, 60, 66, 71, 78, 86.
Те же строки раньше — BACKLOG 157 (61 выживший У1 П1). Возможно, часть убивают `tests/unit/ui/test_ui_effects_visible.py`
и `tests/unit/game/test_sheet_effects.py` вне прогона П3б (TESTS) — ожидание, не проверено.

## Закрыто

Шаг К3б, 2026-11-15 — docs/plan-k3b.md, решение Влада 44: поглощён BACKLOG 307 (К3б П2 тронул `effects_line`, номера
мутантов сменились; выжившие на старых строках той же функции записаны в 307).
