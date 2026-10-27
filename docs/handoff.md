# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 209 ✅ — docs/plan-209.md («Итог» тестя: 5,33 $ при смете 5,8–8,2 $). Закрытие aa695d2.
- Причина падения тестов окна `/model` — 809b059 убрал Claude из меню; тесты теперь берут модель из
  `settings().app.roles.narrator`. src не менялся, cov не снимался.
- ruff красный на HEAD (16 ошибок, не от 209) — BACKLOG 211, следующий шаг.
- Отклик: ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-27-209.md.

## Следующие 3 шага (из ROADMAP)
1. 211 — ruff красный на HEAD: 16 ошибок (мини, перед 188).
2. 188 — по ROADMAP.
3. 190 — по ROADMAP.
210 (тест порядка меню /model) — при касании `game/models.py`; 208 — в резерве «Фикс ЖП5».

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
- docs/plan-209.md; последний коммит — aa695d2 и handoff после него.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md. AGENTS.md, docs/RULES.md.
