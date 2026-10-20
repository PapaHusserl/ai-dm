# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Фикс ЖП3 ✅ (2026-10-20): три партии на sonnet — 5377be4 (чистка утечки служебного текста), 014f435 (бой без options,
  end_combat, travel_to "none", gemini), 308d09a (take_item spent, hit_dice, отказ в отдыхе, вещи от NPC). Закрыты
  BACKLOG 99, 100, 101, 103, 104, 106, 107, 109; 108 открыт до Ж5. Итог и стоимость — docs/plan-fix-zhp3.md.
- Новые в беклоге: 112 (П2), 113 (мутанты старых строк П3).

## Следующие 3 шага (из ROADMAP)
1. Ж8 Человеческие отношения и общая память NPC (BACKLOG 91) — нужен груминг.
2. 19, затем 96а (экипировка и зелья из `inv`).
3. Му-с Тема смерти героя (BACKLOG 102) — наполнитель в окно ожидания.

## Открытые вопросы
- BACKLOG 67, 75 в ЖП3 не встретились — ждут следующего живого прогона.
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806, окно ≈ 2780–2830 — хрупкий, сломается от нового поля героя.
- Полный pytest после правок по ревью П3 не повторялся (затронутые файлы — 4213 passed).
- BACKLOG 10 и 20: строки «Остаток … → Ж2» устарели — поправить при касании.
- `master.context_cap`: `ge=8000` в коде или только рекомендация в TZ 11 — решение проектировщика.
- `mutmut run <один мутант>` гоняет stats по всему tests/ (>10 мин).
- Живой мир на другой машине (dusk_academy): раздать `scripts/migrate_dusk_18plus.py`; откат — `scripts/rollback_world.py`.
- Перед живым прогоном — бэкап saves/.

## Временное и заморожено
- ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer gemini-3-flash-preview, запасной
  рассказчик gemini-4-argon; IPv6 до googleapis — играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for), 65. Тегов stage-* нет (есть только k0).
- Музыка: OGG кодировать через libsndfile (`uv run --no-project --with soundfile`).

## Ссылки
- Последний шаг — docs/plan-fix-zhp3.md; отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-20-fix-zhp3.md.
- `ruff check src tests` — 18 замечаний на main, не разобраны.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
