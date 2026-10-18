# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Ж1 ✅ (3c4c079, 7e1d3c8, 1e5c964, итог 8e80eb4): выжившие боя становятся NPC со скрытым именем, схема v11 — docs/plan-zh1.md.
  BACKLOG 20 закрыт частично (planned): цели и мстители — Ж2, напарники — Ж5.
- Тесты 18512, cov 97,75 %, smells 200/200 (на пределе), `make dead` чист; STATIC_MAX 20050 (замер 19736).
- Расход Ж1 ≈ $19. Находка тестя: долгие сессии кабана и доебы (210–220k) — запускать заново на каждый коммит.
- Бэкап saves/ — ~/ai-dm-backups/saves.bak-20261018-1107 (вне репо).

## Следующие 3 шага (из ROADMAP)
1. Ж2 Мстители и должники — груминг → план.
2. ЖП3 Живой прогон (свой мир) — чек-лист ещё не написан.
3. Далее — по ROADMAP; новые пункты BACKLOG 83–87.

## Открытые вопросы
- `master.context_cap`: жёсткий `ge=8000` в коде или только рекомендация в TZ 11 — решение проектировщика.
- Агенты: у kaban/kaban-doeba/kaban-arhitektor нет Edit; kaban в ТБ делал `git stash` поверх файлов doeba — запретить
  в описании агента (через skill-intake) или оставить.
- `mutmut run <один мутант>` гоняет stats по всему tests/ (>10 мин) — точечная проверка мутантов недоступна.
- `GOAL_KINDS` в vulture_allowlist до появления кода целей.
- Живой мир игрока на другой машине (dusk_academy): раздать `scripts/migrate_dusk_18plus.py` + docs/migrate-dusk-18plus.md;
  после обновления кода сейв станет v11 и на старом коде не откроется.
- Перед живым прогоном — бэкап saves/: первый репорт (`trim_issues`) может удалить старые авто-каталоги issues/.

## Временное и заморожено
- Временные обходы: ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer на gemini-3-flash-preview,
  запасной рассказчик gemini-4-argon, пока 3.8-flash перегружена (503); снять после её возвращения.
  IPv6 до googleapis не работает с 14.10 — на Gemini играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for → ТБ), 65. Отменено 2026-10-15: 53, 16-P3, хвосты 33.
- Чек-листы — ~/.config/ai-dm/checklists/. Тегов stage-* нет (есть только k0).

## Ссылки
- Последний шаг — docs/plan-zh1.md (итог 8e80eb4; до него docs/plan-zh3.md).
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md.
- AGENTS.md, docs/RULES.md, NOTES.md.
