# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Ж0 ▶ в работе («окей, кабаним» уже дано) — docs/plan-zh0.md. Подшаги 0 ✅ f16e8fa, 1 ✅ 9de1f9a, 2 ✅ 8665cb0:
  память NPC (`rules/npc_memory.py`, поля памяти `npc_update`, память/цели/`notes` рассказчику, мок 50 сцен).
- Тесты 17701, cov 97,67 %, smells 200/200, `make dead` чист; ruff — 18 старых E501 (не из Ж0).
- R9 (перебор по заметке проектировщика) закрыт ee09038: очередь R8 сохранена, в ROADMAP добавлены пояснения переносов
  (↷, резервы, ⛔) — docs/plan-roadmap-r9.md.
- Бюджет: остаток ≈ 49,5 млн против ≈ 54 млн сметы линии; решение R8 1в — пересчёт после Ж0 (×1,3 — ориентир).

## Следующие 3 шага (из ROADMAP)
1. Ж0 подшаг 3 — доки (п. 20): ARCHITECTURE (E1, E4, новый E11 «Сейв v11»), TZ 4.1/11, BACKLOG-пометки;
   docs/migrate-dusk-18plus.md — «версии 9–11»; в done/: 77, 15, 63, 79 и 78 (dropped, хвост `start_combat` — в Ж1);
   «Итог» плана с расходом (кабан-тесть) и пересчёт бюджета (R8 1в) — архитектор; ✅ Ж0 в ROADMAP — архитектор.
2. ТХ (крайняя точка «перед ЖП2» наступила).
3. ЖП2 (живой прогон; чек-лист заранее в ~/.config/ai-dm/checklists/).

## Открытые вопросы
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
- Текущий шаг — docs/plan-zh0.md; последний коммит 8665cb0.
- Очередь — docs/ROADMAP.md (R8: docs/plan-roadmap-r8.md; R9 закрыт); беклог — docs/BACKLOG.md.
- AGENTS.md, docs/RULES.md, NOTES.md.
