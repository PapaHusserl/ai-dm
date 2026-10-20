# 107. advance_time с travel_to «none» — Invalid
status: done
priority: medium
updated: 2026-10-20

(репорты t456, t458 и 3 случая в ЖП3) Рассказчик пишет `travel_to: "none"`, нейтральное значение — только `""`
(`protocol/requests.py:389–401`). В Фикс ЖП3 — решение проектировщика 2026-10-20.

## Закрыто
Шаг «Фикс ЖП3», партия П2, 2026-10-20 — docs/plan-fix-zhp3.md
