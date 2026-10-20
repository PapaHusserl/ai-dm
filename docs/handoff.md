# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Ж8 ✅ (2026-10-20): тёплые виды памяти NPC (`friendship`, `joke`, `shared_deed`, `battle`). Вес тёплой сцены при
  вытеснении не меньше 10. Общий бой спутникам пишет движок, нейтральным текстом. Правило рассказчика: тёплое
  записывать, рутину нет. П1 — d15479f, П2 — доки и BACKLOG 116/117. Закрыт BACKLOG 91, $8,49 —
  docs/plan-zh8.md.
- Мир drunk_dragon: Лире дописаны 8 событий памяти (слот `auto`, 14 сцен). Бэкап —
  ~/ai-dm-backups/drunk_dragon-00000001.bak-20261020-1450.

## Следующие 3 шага (из ROADMAP)
1. 19 (живая проверка «ссорится» и морали).
2. 96а Экипировка и зелья из `inv`.
3. ЖП4 Живой прогон (+ резерв Фикс ЖП4): проверить Ж8 — записи новых видов у спутников, частота `duplicate-kind`,
   вход рассказчика против ≈ 28k.

## Открытые вопросы
- BACKLOG 67, 75 — ждут ЖП4 (без находок → dropped).
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806 — хрупкий, сломается от нового поля героя.
- BACKLOG 10 и 20: строки «Остаток … → Ж2» устарели — поправить при касании.
- `master.context_cap`: `ge=8000` в коде или только рекомендация в TZ 11 — решение проектировщика.
- mutmut без сети не собирается (PyPI timeout): запускать с `UV_OFFLINE=1`.
- Живой мир на другой машине (dusk_academy): раздать `scripts/migrate_dusk_18plus.py`; откат — `scripts/rollback_world.py`.
- Перед живым прогоном — бэкап saves/.

## Временное и заморожено
- ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer gemini-3-flash-preview, запасной
  рассказчик gemini-4-argon; IPv6 до googleapis — играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for), 65. Тегов stage-* нет (есть только k0).
- Музыка: OGG кодировать через libsndfile (`uv run --no-project --with soundfile`).

## Ссылки
- Последний шаг — docs/plan-zh8.md; отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-20-zh8.md.
- `ruff check src tests` — 16 замечаний на main, не разобраны.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
