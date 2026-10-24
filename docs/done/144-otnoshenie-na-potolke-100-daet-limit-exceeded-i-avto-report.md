# 144. Отношение на потолке 100 даёт limit-exceeded и авто-репорт
status: done
priority: low
updated: 2026-10-24

(разбор репортов 2026-10-22, t145, t395, t460, t462, t496) `attitude_delta` при отношении 100 — clamp +0 с
`report_tag=limit-exceeded`: на каждый тёплый ход авто-репорт, в t496 ещё три раунда тех же вызовов. Игрок ничего не
видит — шум `issues/` и токены. Предложение: на потолке без тега и `signal_to_master` и/или правило рассказчику «при
attitude 100 attitude_delta не присылай».

## Закрыто

Шаг «Фикс dusk», 2026-10-24, коммит 5cec661 — docs/plan-fix-dusk.md.
