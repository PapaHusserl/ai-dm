# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Ж0 ✅ 2417df9 (подшаги 0–3) — docs/plan-zh0.md: память NPC, сейв v11, доки; закрыты 77, 15, 63, 79, 78 снят.
- Тесты 17701, cov 97,67 %, smells 200/200 (на пределе), `make dead` чист; ruff — 18 старых E501.
- Ж0 факт/смета 1,39 (половина — mutmut/разбор у doeba). Пересчёт бюджета — docs/plan-roadmap-r8.md §4а:
  линия ≈ 75 млн факта при остатке ≈ 49,5 (разрыв ≈ 25). Вопрос 10 R8 открыт (варианты а–г, коэффициент ×1,4?).

## Следующие 3 шага (из ROADMAP)
1. Ответ проектировщика на вопрос 10 R8 → архитектор проводит линию.
2. ТХ (крайняя точка «перед ЖП2» наступила).
3. ЖП2 (живой прогон; чек-лист заранее в ~/.config/ai-dm/checklists/).

## Открытые вопросы
- `master.context_cap`: жёсткий `ge=8000` в коде или только рекомендация в TZ 11 — решение проектировщика.
- Агенты: у kaban/kaban-doeba/kaban-arhitektor нет Edit; kaban в ТБ делал `git stash` поверх файлов doeba — запретить
  в описании агента (через skill-intake) или оставить.
- `mutmut run <один мутант>` гоняет stats по всему tests/ (>10 мин) — точечная проверка мутантов недоступна.
- `GOAL_KINDS` в vulture_allowlist до появления кода целей.
- Живой мир игрока на другой машине (сейв v9, dusk_academy): раздать `scripts/migrate_dusk_18plus.py` (v9–v11)
  + docs/migrate-dusk-18plus.md. После обновления кода сейв станет v11 и на старом коде не откроется.
- Перед живым прогоном — бэкап saves/: первый же репорт (`trim_issues`, `[reports] max_mb = 200`) может удалить старые
  авто-каталоги issues/.

## Временное и заморожено
- Временные обходы: ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer на gemini-3-flash-preview,
  запасной рассказчик gemini-4-argon, цены/окна argon и 3-flash-preview, пока 3.8-flash перегружена (503); снять после её
  возвращения. IPv6 до googleapis не работает с 14.10 — на Gemini играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for → ТБ), 65. Отменено 2026-10-15: 53, 16-P3, хвосты 33.
- Чек-листы (zhp1, 19f, tm, to, ts) — ~/.config/ai-dm/checklists/. Тегов stage-* нет (есть только k0).

## Ссылки
- Текущий шаг — docs/plan-zh0.md; последний коммит 2417df9.
- Очередь — docs/ROADMAP.md (R8: docs/plan-roadmap-r8.md; R9 закрыт); беклог — docs/BACKLOG.md.
- AGENTS.md, docs/RULES.md, NOTES.md.
