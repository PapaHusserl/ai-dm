# 172. duplicate-kind — повтор romance/joke в сцене
status: done
priority: high
updated: 2026-10-24

(разбор репортов dusk_academy 2026-10-23) 12 ходов (t846, t855, t869…, t1015), почти все — романтические сцены Люциана:
`npc_update memory_kind=romance/joke, attitude_delta=1` второй раз в сцене → `clamped`, память не пишется, отношение
применено (`protocol/handlers/world.py:247–258`). Игрок не видит; тег мониторинга из plan-zh8. Решить: правило
рассказчику «romance раз в сцену» или оставить.

## Закрыто

Шаг «Фикс dusk», 2026-10-24, коммит 5cec661 — docs/plan-fix-dusk.md.
