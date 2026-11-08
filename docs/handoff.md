# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- К3 ✅ Жрец и волшебник 1–5 — docs/plan-k3.md. Коммиты П1 21434d2, П2 fd891ae, П3а 9959f76, П3б b3f5376, П4 f58f2f1,
  П5 и закрытие 1dbdd1a. Факт по тестю: 222,93 $ (смета 123–160 $).
- П5: мутанты 236 добиты тестами (решения 76, 77); закрыты BACKLOG 47, 50, 235, 236.
- Новая сессия: Read ~/.claude/kaban-kb/ family.md, okna.md, testy.md, sessiya.md; агенты — новыми Agent.
  Пороги: smells ≤ 200, STATIC_MAX = 24500, `uv run ruff check src tests`.
- Замеры: полный pytest 12 мин 44 с (xdist 4), cov 42 мин (98,28 %), mutmut 42 функций 7 ч 36 мин.

## Следующие 3 шага (из ROADMAP)
1. Л1 Перемещение (BACKLOG 251, 252) — docs/plan-l1.md.
2. ФД2 Фикс dusk 2 (BACKLOG 274, 275; кандидат 224).
3. 254 Окно торговли → К3б.

## Открытые вопросы
- Новые в BACKLOG: 277 ваншоты (публикация, до 191 — груминг), 278 флак TUI-теста, 279 меню боя, 280 авто-жрец сетки.
- Живой прогон К2 и К3 — за Владом; шпаргалка ~/.config/ai-dm/checklists/checklist-k2-live.md.
- Миграция dusk_academy — за Владом; после неё мини-задача: удалить migrate_dusk_vibe.py, тест и howto.
- Стейджинг `saves/drunk_dragon/` (импорт 2026-10-02): удалять ли — вопрос Владу.
- Хук commit-close.sh режет ✅-строки ROADMAP с кодами шагов — кандидат в BACKLOG семьи.
- Живой прогон 219, ФС, 212 и БП — за Владом. BACKLOG 239 (долг cov/mutmut К2).
- Р2/Р8 (рынок, монетизация) — до 198г; Р9 — в 198в (docs/plan-197.md).
- Pilot-тесты флакают под нагрузкой: BACKLOG 216, 226, 278 — причина не установлена.

## Ссылки
- docs/plan-k3.md («Итог», «Правки по ревью» П5); последний коммит 1dbdd1a.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
- Отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-11-08-k3.md.
