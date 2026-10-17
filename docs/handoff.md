# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Ж0 ▶ в работе (снят с холда 2026-10-17, «окей, кабаним» уже дано) — docs/plan-zh0.md.
  Подшаг 0 ✅ f16e8fa: статика explore 17666 / `STATIC_MAX` 18200, `context_cap` 16000 = потолок динамики сверх статики,
  anthropic cpt 2.2 (общий `chars_per_token` слоя перекрывает), пятая ступень (главы), фикстура v10 + золотой ход
  `tests/unit/persistence/test_zh0_golden_turn.py` (после v11 должен пройти без правок снимка).
- Сейв v10. Тесты 17386, cov 97,45 %, smells 200/200. Расход подшага 0 ≈ 0,45 млн агентов (в документе шага).
- Бюджет: остаток ≈ 51 млн, пересчёт после Ж0.

## Следующие 3 шага (из ROADMAP)
1. Ж0 подшаг 1 — поля v11 одной миграцией (план пп. 7–12): kaban (код), затем doeba (тесты), ревью, аудит, коммит.
   В подшаге 2 — мок памяти на большое окно + фиксированный `context_cap` вместо подбора `WINDOW` (ревью п. 0).
2. Ж0 подшаги 2+3 — память NPC (79, 63), доки; закрыть 77/15/78/… в done/.
3. ТХ (плавающая, ждёт журнал игрока), затем ЖП2.

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
