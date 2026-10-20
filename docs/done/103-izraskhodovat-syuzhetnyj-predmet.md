# 103. Израсходовать сюжетный предмет
status: done
priority: medium
updated: 2026-10-20

(авто-репорт t421, ЖП3) Герой влил флакон нейтрализатора Греты (`custom_19`) в воду. `take_item why=spent` по сюжетному
предмету отклонён `holder_required` (`protocol/handlers/resources.py:take_holder` — сюжетный предмет только отдают NPC),
рассказчик ушёл в `unsupported_action`; флакон остался в инвентаре, хотя по рассказу потрачен. Нужен путь «потрачен» без
держателя. Близко к BACKLOG 92, 94.

## Закрыто
Шаг «Фикс ЖП3», партия П3, 2026-10-20 — docs/plan-fix-zhp3.md
