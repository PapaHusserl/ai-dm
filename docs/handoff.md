# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- 96а ▶: П1 «движок + простая UI» закоммичена (6dca2ea, push): `/inv надеть|снять|выпить`, смена оружия/щита в бою
  по SRD, заметки рассказчику. cov 97,97 %, smells 200/200, dead чист. Итог П1 и решения 1–17 — docs/plan-96a.md.
  П2 (окно `InvModal` в TUI) — после Э10а.
- Э10а (OpenAI, BACKLOG 65): блок снят (NOTES.md 2026-10-20 «gemini очень плохо»), план — docs/plan-e10a.md
  (не закоммичен — войдёт в коммит Э10а); решения 1–7 приняты (зависимость `openai>=3.35` — да; по умолчанию Gemini,
  OpenAI запасной в `narrator_chain`; effort medium; import — sol low; без reasoning.summary; сметы тестя не делать).
  Ждёт «окей, кабаним».

## Следующие 3 шага (из ROADMAP)
1. Э10а OpenAI-адаптер — docs/plan-e10a.md (одна партия M; груминг пропущен по просьбе проектировщика).
2. 96а П2 — окно TUI по плану в docs/plan-96a.md; затем итог шага у тестя, 96 → done/ решает архитектор (96б впереди).
3. ЖП4 (+ резерв Фикс ЖП4) — проверить 96а целиком, Ж8, 19; первый прогон на OpenAI-адаптере. Затем У0.

## Открытые вопросы
- BACKLOG 67, 75 — ждут ЖП4. Новые: 120 (сдвиг часов `/inv` через полночь), 121 (старые мутанты после 96а П1).
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806 — хрупкий.
- mutmut без сети: `UV_OFFLINE=1`. Папа-кабан — на fable; на opus не переключать без спроса Влада (2026-10-20).
- Хук запрещает правку docs/ через bash — только Edit/Write.
- Перед живым прогоном — бэкап saves/. `ruff check src tests` — 16 старых замечаний на main.

## Ссылки
- docs/plan-e10a.md (текущий), docs/plan-96a.md; последний коммит 6dca2ea.
- Отклик планирования 96а — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-20-96a.md.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
