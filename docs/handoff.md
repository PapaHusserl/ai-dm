# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- ТБ ✅ (docs/plan-tb.md): фильтр `monster_ids` по паку (поле `monsters` манифеста), порог статики `STATIC_MAX` 28900 +
  `make prompt-budget`, механизм `chars_per_token_by_provider` (дефолт пуст) и `api_tokens` без двойного кэша Gemini,
  разметка журнала границы по роли, mutmut `also_copy`. BACKLOG 45/56/71/76 → done/, заведены 77 (high), 78 (low).
- Сейв v10. Тесты ≈ 17300, cov 97 %, smells 200/200. Расход ТБ ≈ 0,65 млн против сметы 0,45.
- Бюджет: остаток ≈ 51 млн, пересчёт после Ж0.

## Следующие 3 шага (из ROADMAP)
1. ТХ (69, 70 + хвосты 73/74) — плавающая: как только будет журнал игрока; крайняя точка перед ЖП2.
2. Ж0 (v11) — первым подшагом BACKLOG 77: anthropic cpt 2.2, `context_cap` по провайдеру / без кэшируемой статики,
   пересчёт WINDOW, запас под динамику (статика explore ≈ 28k при cap 30k). Груминг svinopas + svekrov по блоку Ж0–Ж3.
3. ЖП2 (живой прогон + чек-листы tm/to/ts/19f, хвост 62).

## Открытые вопросы
- Агенты: у kaban/kaban-doeba/kaban-arhitektor нет Edit; kaban в ТБ делал `git stash` поверх файлов doeba — запретить
  в описании агента (через skill-intake) или оставить.
- `mutmut run <один мутант>` гоняет stats по всему tests/ (>10 мин) — точечная проверка мутантов недоступна.
- Живой мир игрока на другой машине (сейв v9, dusk_academy): раздать `scripts/migrate_dusk_18plus.py` + docs/migrate-dusk-18plus.md.
- Перед живым прогоном — бэкап saves/: первый же репорт (`trim_issues`, `[reports] max_mb = 200`) может удалить старые
  авто-каталоги issues/.

## Временное и заморожено
- Временные обходы: ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer на gemini-3-flash-preview,
  запасной рассказчик gemini-4-argon, цены/окна argon и 3-flash-preview, пока 3.8-flash перегружена (503); снять после её
  возвращения. IPv6 до googleapis не работает с 14.10 — на Gemini играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for → ТБ), 65. Отменено 2026-10-15: 53, 16-P3, хвосты 33.
- Чек-листы (zhp1, 19f, tm, to, ts) — ~/.config/ai-dm/checklists/. Тегов stage-* нет (есть только k0).

## Ссылки
- Очередь — docs/ROADMAP.md (R7: docs/plan-roadmap-r7.md); беклог — docs/BACKLOG.md.
- История шагов, расходы и находки — разделы «Итог» в docs/plan-*.md.
- AGENTS.md, docs/RULES.md, NOTES.md.
