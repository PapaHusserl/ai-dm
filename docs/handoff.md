# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Фикс ЖП4 ▶ — docs/plan-fix-zhp4.md. П1 (129 + 132) ✅ bbc9a96; П2 (130 + 131) ✅ — коммит после bbc9a96.
- Следующее — П3 (128 + хвост 127 `inv_rows_66`): кабан (sonnet) → доеба (opus) → мама ‖ свекровь; затем итог тестя.
- BACKLOG 140–145 — из разбора репортов 2026-10-22 (места — ROADMAP).
- Бэкап сейвов: ~/ai-dm-backups/saves.bak-20261021-zhp4.

## Следующие 3 шага (из ROADMAP)
1. Фикс ЖП4 П3, итог шага.
2. У0.
3. У1.

## Открытые вопросы
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (теперь в умолчаниях; бэкап config.toml.bak-20261021).
- mutmut без сети: `UV_OFFLINE=1`; гонять только после последнего круга ревью.
- Кабану — мерить `make smells` и `make dead` до хэнд-бэка (smells 200 = max). Хук запрещает правку docs/ через bash.
  ruff — 16 старых. `STATIC_MAX` 22310 (П2).
- Агенты шага — scratchpad agents.md сессии fe8ac84d (papa a5dc8c3b7e6cde2e5, тесть a5d9eaf250c633249).

## Ссылки
- docs/plan-fix-zhp4.md; последний коммит — bbc9a96 (Фикс ЖП4 П1).
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
