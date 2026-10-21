# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 96а П2 ✅ (f285030): окно `InvModal` в TUI; шаг 96а закрыт целиком (П1 6dca2ea + П2). BACKLOG 96 открыт — 96б в М0/М0п.
  Решения 18–21 — docs/plan-96a.md. Стоимость шага ≈ $21,27 (тесть, «Итог»).
- Новый BACKLOG 127 (старые мутанты `finish_turn`, неубитый `inv_rows_66`), low.
- Бэкап сейва: saves/drunk_dragon-00000001.bak-20261021-1231.

## Следующие 3 шага (из ROADMAP)
1. ЖП4 — живая игра проектировщика (мир drunk_dragon, первый прогон на OpenAI); перед игрой — свежий бэкап saves/;
   шпаргалка — ~/.config/ai-dm/checklists/ (составить checklist-zhp4-live.md по строке ЖП4 в ROADMAP).
2. Резерв Фикс ЖП4 (кандидаты 110, 120, 125, 126, 127 — по находкам), затем У0.
3. У1.

## Открытые вопросы
- Наблюдение для ЖП4: окно `inv` не переоткрывается после действия (как `/spells`) — мешает ли.
- BACKLOG 67, 75 — ждут ЖП4; 120–122, 126, 127 low.
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806 — хрупкий.
- mutmut без сети: `UV_OFFLINE=1`; гонять только после последнего круга ревью (след в pyproject.toml после прогона
  откатывать). Архитектор — агент `papa-kaban` (типа `kaban-arhitektor` нет), на fable.
- Кабану — мерить `make smells` и `make dead` до хэнд-бэка (smells 200 = max). Хук запрещает правку docs/ через bash.
  ruff — 16 старых.

## Ссылки
- docs/plan-96a.md (закрыт); последний коммит f285030.
- Отклик: ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-21-96a-p2.md
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
