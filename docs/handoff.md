# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Фикс ЖП4 ✅ — docs/plan-fix-zhp4.md (П1 bbc9a96, П2 3b4440d, П3 4169140; BACKLOG 128–132 в done/).
- ROADMAP — строгая линия (NOTES.md 2026-10-22); ▶ — У0 Реестр услуг.
- 127 открыт: 26 мутантов `finish_turn` — при касании в Ж6.
- Бэкап сейвов: ~/ai-dm-backups/saves.bak-20261021-zhp4.

## Следующие 3 шага (из ROADMAP)
1. У0 Реестр услуг (BACKLOG 32) — груминг.
2. У1 Атмосферные услуги.
3. ДН Минимум день и ночь (BACKLOG 36).

## Открытые вопросы
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (теперь в умолчаниях; бэкап config.toml.bak-20261021).
- Проектировщику: дописать t513 в BACKLOG 11 и заметку про north_wind_blade без Light в 66?
- Свекровь и свинопас по журналу шли на opus, не на моделях из файлов агентов — проверить (итог тестя).
- mutmut без сети: `UV_OFFLINE=1`; гонять только после последнего круга ревью.
- Кабану — мерить `make smells` и `make dead` до хэнд-бэка (smells 200 = max). ruff — 16 старых.

## Ссылки
- docs/plan-fix-zhp4.md; отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-22-fix-zhp4.md.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
