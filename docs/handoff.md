# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 207 ✅ — docs/plan-207.md («Итог» тестя: $11,79 при смете $10–19). П1 933888e, закрытие 315ef73.
- В журнале вызовов теперь `duration_s` и `tokens_per_s`. Живой замер (медиана хода до текста): V4-Flash 43 с, gemini 28 с,
  qwen 57 с. Ориентир в business-plan.md — ≤ 45 с по медиане ходов.
- Рассказчик по умолчанию — DeepSeek-V4-Flash; в ~/.config/ai-dm/config.toml возвращён профиль deepinfra-qwen
  (бэкап config.toml.bak-20261027-1121).
- `make cov` красный: 3 теста окна модели в TUI падают и на HEAD — BACKLOG 209, следующий шаг.

## Следующие 3 шага (из ROADMAP)
1. 209 — тесты окна выбора модели в TUI падают на HEAD (мини; решение Влада 2026-10-27 — до 188).
2. 188 — по ROADMAP.
3. 190 — по ROADMAP.
208 (старые мутанты журнала и MasterSession.call) — в резерве «Фикс ЖП5», при касании (решение Влада 2026-10-27).

## Открытые вопросы
- Копии мира saves/drunk_dragon-207-{flash,gemini,qwen} — удалить? Только по «да» Влада.
- В журналах V4-Flash и qwen по 6 ходов при 5 сыгранных; граница сцены только у gemini — не проверено.
- Проектировщику: решение 2026-10-26 о порядке этапов не записано в NOTES.md — записать?
- Проектировщику: живая загрузка `drunk_dragon-00000001` — «Из пака добавлено», `/shop`, баня, мытьё в реке, платный
  `rest long` у Грока, трата вдохновения. Находки → резерв Фикс У1.
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261021).
- Проектировщику: дописать t513 в BACKLOG 11 и заметку про north_wind_blade без Light в 66?
- Мир drunk_dragon-00000001 помнит gemini (meta/models.json) — первый запуск с `--provider deepinfra-deepseek`.
- mutmut без сети: `UV_OFFLINE=1`, перед прогоном `rm -rf mutants`; полный `make cov` — 15–18 мин.

## Ссылки
- docs/plan-207.md; последний коммит — 315ef73 и handoff после него.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md. AGENTS.md, docs/RULES.md.
