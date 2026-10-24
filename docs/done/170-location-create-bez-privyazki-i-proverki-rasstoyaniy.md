# 170. location_create без привязки и проверки расстояний — часы пути внутри Академии
status: done
priority: high
updated: 2026-10-24

(разбор репортов dusk_academy 2026-10-23, жалобы игрока /report t941, t1081) Переход внутри Академии — 7913 с и 6638 с
(≈ 2 ч). `protocol/handlers/world.py:154` `location_create` принимает любые `connections`/`distance_m`, `parent_id=None`,
без привязки к локации пака и без дедупа: все 18 локаций `origin=ai` без родителя, мастер вешает новую цепочкой на
последнюю созданную (rectors_study_chamber—peat_oak_grove 3500 м), `route_path` (`rules/time_ops.py:35`) тянет через весь
граф; дубль `academy_hall` ≈ `academy`. Нужно: привязка к паковому узлу/родителю, лимит расстояния, дедуп. Смежно 136, 151.

## Закрыто

Шаг «Фикс dusk», 2026-10-24, коммит 5cec661 — docs/plan-fix-dusk.md.
