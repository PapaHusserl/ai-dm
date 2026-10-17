# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Последний коммит до 22д — 717e7bf (22 ТС ✅, сейв v10). 22д (docs/ по правилам дашборда, BACKLOG 68) закрывается
  своим коммитом: docs/decisions слит в plan-*.md, HANDOFF → handoff.md, BACKLOG в формате дашборда + docs/done/ (24 карточки, 59 закрыт владельцем),
  AGENTS.md/CLAUDE.md/RULES.md, чек-листы вне репо.
- Дальше 22а ТХ (BACKLOG 69, 70: опыт и час каждый ход) — ждёт журнала игрока (dusk_academy); затем Ж0 (v11).
- Бюджет: остаток ≈ 52 млн (с переделками и прогонами ≈ 56–58); факт этапов 1–К0 ≈ 9,5 млн, R5 #8–16 + B59 ≈ 6,2 млн.
  Партии техдолга — без груминга, по правилу фикса. Тесты ≈ 17000, cov 98 %, smells 200/200.

## Следующие 3 шага (из ROADMAP)
1. 22а ТХ Повторы хода: опыт и время (BACKLOG 69 + 70, по образцу ТМ) — после журнала игрока.
2. Ж0 Поля и память NPC (BACKLOG 63, 56, 45, 15, 71, 42 поля, хвост 46; сейв v11) — груминг svinopas + kaban-svekrov.
3. Ж1 → Ж2 → Ж3 → ЖП2 (живой прогон; считать `combat_announced`, `summary_trimmed`, `choices_retry`).

## Открытые вопросы
- Агенты: у kaban/kaban-doeba нет Edit (намеренно, в msa правки через bash/ex), в ai-dm они правят скриптами вопреки правилу
  «вне msa — Edit/Write»; варианты — вернуть Edit с оговоркой или отдельные агенты для ai-dm. Пока мелкие правки после
  ревью вносит оркестратор.- Живой мир игрока на другой машине (сейв v9, dusk_academy): раздать `scripts/migrate_dusk_18plus.py` + docs/migrate-dusk-18plus.md.
- Перед живым прогоном — бэкап saves/: первый же репорт (`trim_issues`, `[reports] max_mb = 200`) может удалить старые
  авто-каталоги issues/.

## Временное и заморожено
- Временные обходы: ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer на gemini-3-flash-preview,
  запасной рассказчик gemini-4-argon, цены/окна argon и 3-flash-preview, пока 3.8-flash перегружена (503); снять после её
  возвращения. IPv6 до googleapis не работает с 14.10 — на Gemini играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30. Отменено 2026-10-15: 53 (docs/done/), 16-P3, хвосты 33.
- Живые прогоны Р1+Ф1+Р2, К1, К7к/х/д, B59, Т60 вошли в ЖП1; непройденное → ЖП2. Чек-листы (zhp1, 19f, tm, to, ts) —
  ~/.config/ai-dm/checklists/.
- Тегов stage-* в репо нет (есть только k0).
- Пункт 72 (бывш. 5а, рисунки 31 локации) — перенумерован в BACKLOG; в старых планах остаётся «5а».

## Ссылки
- Документ текущего шага: docs/plan-22d.md; очередь — docs/ROADMAP.md (R6: docs/plan-roadmap-r6.md); беклог — docs/BACKLOG.md.
- История шагов, расходы и находки — разделы «Итог» в docs/plan-*.md (в т. ч. «Из HANDOFF.md до 22д»).
- Откат 22д: `git checkout docs-legacy-22d -- docs/` + архив ~/.config/ai-dm/backups/docs-legacy-22d-20261017-1327.tgz.
- AGENTS.md, docs/RULES.md, NOTES.md.
