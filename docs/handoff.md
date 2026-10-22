# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- У1 Атмосферные услуги ▶ — docs/plan-u1.md (решения 1–32). П1 ✅ a8ce084, П2 (память/порог романа 90) ✅ be0026a.
- Дальше П3 (болезнь, кража, ревность, гигиена/«вонь» + Р9(б)), затем живой прогон `inn_test --preset grim`,
  затем П4 (живые миры по списку проектировщика).
- Порядок партии: новый kaban → новый doeba → мама ‖ свекровь → правки тому же id → cov+mutmut фоном → архитектор → коммит.
- У0 ✅ — docs/plan-u0.md. dusk_academy ещё не мигрирован (docs/migrate-dusk-ferry.md, запускает проектировщик).

## Следующие 3 шага (из ROADMAP)
1. У1 П3 — состояния и последствия, гигиена (кража: решение 29).
2. Живой прогон У1, П4.
3. ДН (BACKLOG 36).

## Открытые вопросы
- В П3 снять из vulture_allowlist оставшиеся поля У1 (`disease_dc`, `theft_dc`, `risks`, `hygiene_days`, `washed_at`).
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261021).
- Проектировщику: дописать t513 в BACKLOG 11 и заметку про north_wind_blade без Light в 66?
- mutmut без сети: `UV_OFFLINE=1`; гонять только после последнего круга ревью.

## Ссылки
- docs/plan-u1.md; последний коммит — У1 П2 be0026a (+ handoff).
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
