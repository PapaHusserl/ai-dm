# 130. Строка ленты «Записано в журнал: npc Лира» — служебный вид записи виден игроку
status: done
priority: low
updated: 2026-10-22

(Проектировщик, ЖП4, 2026-10-21: «что значит "записано в журнал: npc Лира"») Лог `knowledge_note`
(`protocol/handlers/knowledge.py:knowledge_note`) пишет в ленту сырое `request.kind` (`npc`, `location`, `faction`,
`god`, `creature`, `situation` — `state/knowledge.py:KNOWLEDGE_KINDS`). Игроку непонятно, что это и где смотреть.
Нужна русская формулировка с указанием на `/lore` (например «В журнал знаний (/lore): о Лире»); склонение имени и
подписи видов — на груминге. Того же рода строка `npc_update` (`protocol/handlers/world.py:201`, ход 611):
«Лира запомнил: joke» — мужской род для женщины и сырой `memory_kind`.

## Закрыто
Шаг «Фикс ЖП4», П2 (3b4440d), 2026-10-22 — docs/plan-fix-zhp4.md
