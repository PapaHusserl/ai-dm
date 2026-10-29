# 137. Упоминание NPC по имени не ловит падежи
status: done
priority: low
updated: 2026-10-30

(папа-кабан, docs/plan-fix-zhp4.md) `npc_reason_set`, причина `said`: ищется `npc.name.lower()` целиком — «у матушки
Греты» не находит «Матушка Грета». При касании relevance — хотя бы по фамилии/последнему слову имени.

## Закрыто

Шаг ФС, 2026-10-30 — docs/plan-fs.md (П3: `rules/knowledge.py` `mentions` с падежами).
