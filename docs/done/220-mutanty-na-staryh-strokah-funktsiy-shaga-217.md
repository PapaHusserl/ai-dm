# 220. Мутанты на старых строках функций шага 217
status: done
priority: low
updated: 2026-10-30

mutmut шага 217 (docs/plan-217.md), resources.py, строки вне диффа: `x_time_by_category__mutmut_33/40/41/60/61`
(survived), `_79/80` (timeout), `x_time_until__mutmut_21/22` (survived).

## Закрыто

Шаг 219, 2026-10-30 — docs/plan-219.md. Номера `time_by_category` сдвинулись на +21 (33/40/41/60/61/79/80 →
54/61/62/81/82/100/101; сдвиг по номерам, поштучно не сверялся): убиты тестами все, кроме 61/62
(`model_copy(deep=…)`, эквивалентны); `time_until` 21/22 убиты.
