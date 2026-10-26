# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 184 ✅ — docs/plan-184.md («Итог» тестя: $30,71 при смете $15–26). П1 5cf32c7, П2 7e2a4b3, закрытие 848edbe.
- Проба моделей 2026-10-26/27 на копиях drunk_dragon (итоги — NOTES.md, «эксперимент 18+»; ресёрч 206 с разделом 18+ —
  docs/research/models-vs-gemini-206.md, 9b7213f). gemini режет 18+ (PROHIBITED_CONTENT), Kimi — таймаут, gemma и
  Nemotron — слабый русский, V4-Pro ≈ $0,047/ход. Выбрана DeepSeek-V4-Flash (≈ $0,004/ход) — Влад живёт с ней.
- ~/.config/ai-dm/config.toml (бэкап .bak-20261027): roles.narrator — deepinfra V4-Flash; narrator_chain:
  V4-Flash → V4-Pro → gemini…; профили deepinfra-deepseek, deepinfra-v4pro; qwen/kimi/gemma/nemotron убраны.
- 809b059: быстрый выбор рассказчика — только roles, alternatives (теперь gpt-6.1-sol вместо Claude) и narrator_chain;
  сценарные тесты изолированы от пользовательского конфига. 6eaa3a4: тон «откровенно» — сцена целиком, без склейки.
- Копии drunk_dragon-cmp-* удалены. Вживую не проверены: Фикс dusk, Договор, 165, 182, ДН П1 и П2.

## Следующие 3 шага (из ROADMAP)
1. 206 — ресёрч и проба по сути сделаны (NOTES.md); архитектору — отметить 206 и переставить 185 (V4-Flash выбрана).
2. 207 — время до первого токена и ток/с в журнале вызовов.
3. 185/186 — по итогам жизни с V4-Flash; ROADMAP-строке 184 вписать хэш 848edbe (архитектор).

## Открытые вопросы
- Архитектору: итог пробы моделей (NOTES.md 2026-10-26/27) — встроить в ROADMAP (206 ✅?, 185 по факту, 186).
- Проектировщику: решение 2026-10-26 о порядке этапов не записано в NOTES.md — записать?
- Проектировщику: живая загрузка `drunk_dragon-00000001` — «Из пака добавлено», `/shop`, баня, мытьё в реке, платный
  `rest long` у Грока, трата вдохновения. Находки → резерв Фикс У1.
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261021).
- Проектировщику: дописать t513 в BACKLOG 11 и заметку про north_wind_blade без Light в 66?
- Мир drunk_dragon-00000001 помнит gemini (meta/models.json) — первый запуск с `--provider deepinfra-deepseek`.
- V4-Pro: первые вызовы хода без кэша (cache_read 0) — дороже ресёрча; V4-Flash кэш даёт.
- Старые выжившие мутанты П2 — BACKLOG 205. mutmut: `prepare`/`make_parser` не брать в FUNCS (> 1 ч).
- mutmut без сети: `UV_OFFLINE=1`, перед прогоном `rm -rf mutants`; полный `make cov` — 13–15 мин.

## Ссылки
- docs/plan-184.md; NOTES.md; последний коммит — 6eaa3a4 и handoff после него.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md. AGENTS.md, docs/RULES.md.
