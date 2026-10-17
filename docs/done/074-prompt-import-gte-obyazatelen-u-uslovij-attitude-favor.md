# 74. Промпт import: `gte` обязателен у условий attitude/favor
status: dropped
priority: low
updated: 2026-10-18

(хвост Б3, docs/plan-b3.md)
Первый вызов `pack` при импорте отклоняется `invalid_request` («для attitude нужен порог gte»), модель исправляется со второго
раза — лишний вызов ≈ $0,014. Явно сказать в `prompts/import_rules.md`, что у условий attitude/favor обязателен `gte`.
Хвост ТХ (R7 #2).

## Закрыто

Снят в ТХ, 2026-10-18 (решение В3): единственный журнал импорта (`campaigns/test/.import/journal/calls-001.jsonl`,
2026-10-10) — один `invalid_request` про `gte`, второй вызов принят, повторов нет; не подтвердился. План: docs/plan-tx.md §0
