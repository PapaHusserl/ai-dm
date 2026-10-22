# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 146 Паром ✅ — docs/plan-ferry-npcs.md (коммит 2540be5): Франциск и Нокс в паке, scripts/migrate_dusk_ferry.py.
- Живой мир dusk_academy-d3de6c57 ещё не мигрирован: проектировщик загружает мир, затем запускает скрипт
  (docs/migrate-dusk-ferry.md). Слух при N = 1 приходит сразу, паром — через сутки.
- ROADMAP — строгая линия; ▶ — У0 Реестр услуг.
- 127 открыт: 26 мутантов `finish_turn` — при касании в Ж6.

## Следующие 3 шага (из ROADMAP)
1. У0 Реестр услуг (BACKLOG 32) — груминг.
2. У1 Атмосферные услуги.
3. ДН Минимум день и ночь (BACKLOG 36).

## Открытые вопросы
- Проектировщику: снять `openai = 3.5` в ~/.config/ai-dm/config.toml (теперь в умолчаниях; бэкап config.toml.bak-20261021).
- Проектировщику: дописать t513 в BACKLOG 11 и заметку про north_wind_blade без Light в 66?
- Свекровь и свинопас по журналу шли на opus, не на моделях из файлов агентов — проверить.
- Паром — прецедент для Р3 «Сюжетные арки» (NOTES.md 2026-10-22): тексты для игрока выносить окном в плане.
- mutmut без сети: `UV_OFFLINE=1`; гонять только после последнего круга ревью.

## Ссылки
- docs/plan-ferry-npcs.md; отклик — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-22-ferry-npcs.md.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
