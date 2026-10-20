# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 19 ✅ (2026-10-20, 6a502ec): Обман «ссорится» — цель один свой ход бьёт союзника по `group_id` (иначе по стороне),
  СЛ +2, только фразой; мораль группы при сильном успехе (СЛ+10 / нат. 20) — раненые ≤ 50 % HP «тоже сдаются/уходят»,
  `spread_morale = true`. Исходы переговоров вынесены в `combat/actions/parley_effects.py`. ≈ $8 — docs/plan-19.md.
- Новые BACKLOG 118 (подменю TUI «навык × исход»), 119 (старые мутанты `parley_dc`).

## Следующие 3 шага (из ROADMAP)
1. 96а Экипировка и зелья из `inv`.
2. ЖП4 Живой прогон (+ резерв Фикс ЖП4): проверить Ж8 (записи новых видов у спутников, `duplicate-kind`, вход
   рассказчика против ≈ 28k) и 19 (Обман «он вас предаст» → враг бьёт своего; «сдавайтесь» с большим броском по
   раненой группе → несколько сдались).
3. У0.

## Открытые вопросы
- BACKLOG 67, 75 — ждут ЖП4 (без находок → dropped).
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806 — хрупкий, сломается от нового поля героя.
- BACKLOG 10 и 20: строки «Остаток … → Ж2» устарели — поправить при касании.
- `master.context_cap`: `ge=8000` в коде или только рекомендация в TZ 11 — решение проектировщика.
- mutmut без сети не собирается (PyPI timeout): запускать с `UV_OFFLINE=1`.
- Папа-кабан на fable упирается в лимит Fable — в шаге 19 перезапущен на opus разово.
- Живой мир на другой машине (dusk_academy): раздать `scripts/migrate_dusk_18plus.py`; откат — `scripts/rollback_world.py`.
- Перед живым прогоном — бэкап saves/.

## Временное и заморожено
- ~/.config/ai-dm/config.toml (бэкап config.toml.bak-20261014): summarizer gemini-3-flash-preview, запасной
  рассказчик gemini-4-argon; IPv6 до googleapis — играть с `networksetup -setv6off Wi-Fi`.
- Заморожено: BACKLOG 16, 30 (кроме records_for), 65. Тегов stage-* нет (есть только k0).
- Музыка: OGG кодировать через libsndfile (`uv run --no-project --with soundfile`).

## Ссылки
- Последний шаг — docs/plan-19.md; отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-20-19.md.
- `ruff check src tests` — 16 замечаний на main (старые), не разобраны.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
