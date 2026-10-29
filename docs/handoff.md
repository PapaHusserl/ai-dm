# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 217 ✅ — docs/plan-217.md, коммит 697cb07: сон перемоткой ≥ long_rest_s при доступном отдыхе отклоняется
  с подсказкой rest long и авто-репортом sleep_not_rest; cov 98,15 %, smells 200; итог тестя: 10,08 $ при смете 11–16 $.
- Заведены BACKLOG 219 (time_repeat теряет час) и 220 (старые мутанты 217 — при касании в 219).
- Следующее — ФС.

## Следующие 3 шага (из ROADMAP)
1. ФС — фикс сцены: 134 (cap 32000 + конспект выпавших ходов сцены), 214, 145 (причина только у смерти).
2. 219 — time_repeat теряет час (с ним 220).
3. 212 — устаревшая сводка игры (диагностика).

## Открытые вопросы
- `[master] context_cap = 32000` в ~/.config/ai-dm/config.toml — снять при закрытии ФС.
- BACKLOG 216 — Pilot DeadlockError под нагрузкой, причина не установлена (в 217 флакнул снова: 2 теста TUI в cov r2).
- mutmut r2 шага 217 — 3 timeout в `time_by_category`, в первом прогоне не было; причина не установлена.
- Бэкап сейва saves/drunk_dragon-00000001.bak-20261028-t1279 и копии -207-{flash,gemini,qwen},
  .bak-rollback-20261028-* — удалить? Только по «да» Влада.
- Проектировщику: снять `openai = 3.5` в config.toml; t513 в BACKLOG 11 и north_wind_blade в 66.
- Тест «стрелы подходят к луку composite_longbow_bound» не написан — по желанию.
- Отклик шага 217 — semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-29-217.md.

## Ссылки
- docs/plan-217.md («Итог»); последний коммит — 697cb07.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md 2026-10-29. AGENTS.md, docs/RULES.md.
