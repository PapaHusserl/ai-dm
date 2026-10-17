# 71. Разметка журнала границы по роли
status: done
priority: high
updated: 2026-10-17

(из ревью #22 ТС, 2026-10-17, без приоритета)
Summarizer и world пишут журнал под одним run_id границы (`bnd-…`), `TurnRunner.take_boundary`/`mark_journal`
размечает committed/aborted по run_id. После #22 мягко упавший world пропускается, а его записи остаются `committed`
(сбой виден по `error`/`stop_reason` записи и тегу `world_skipped`). Чтобы помечать aborted только записи world —
разметка по роли (или отдельный run_id у world).

## Закрыто

Шаг ТБ «Бюджет контекста», 2026-10-17. План: docs/plan-tb.md
