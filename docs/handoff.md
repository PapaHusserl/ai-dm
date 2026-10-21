# Handoff: ai-dm

Закладка для новой сессии. Перезаписывается, не дописывается. Правила — docs/RULES.md, как работаем — AGENTS.md.

## Где мы
- Э10а ✅ (7a9db1d, push): OpenAI (Responses API) третьим провайдером — `llm/openai_adapter.py`, профиль `openai`
  (narrator gpt-6.1-sol medium, world/summarizer gpt-6-luna low, import sol low), `--provider openai`,
  `openai:gpt-6.1-sol` вторым в `narrator_chain`; по умолчанию Gemini. 65 → done/. Итог и стоимость (≈ $6,5) —
  docs/plan-e10a.md. pytest 20128, cov 97,98 %, smells 200/200.
- Живой smoke OpenAI — за проектировщиком: ключ `OPENAI_API_KEY`, `uv run python devtools/live_smoke.py openai`, затем
  в игре `/model narrator openai:gpt-6.1-sol`. Находки smoke — новым пунктом беклога и фиксом перед 96а П2 (решение
  архитектора).

## Следующие 3 шага (из ROADMAP)
1. 96а П2 — окно `InvModal` в TUI по docs/plan-96a.md; затем итог шага у тестя, 96 → done/ решает архитектор.
2. ЖП4 (+ резерв Фикс ЖП4, кандидат 120) — проверить 96а, Ж8, 19; первый прогон на OpenAI.
3. У0.

## Открытые вопросы
- Риск smoke: при `store=False` API может отвергнуть `id` у message/function_call → убирать `id` в `item_from_api`
  (docs/llm-notes/openai-facts.md). `live_smoke.py` max_tokens 1000 при effort medium может дать `max_tokens`.
- BACKLOG 67, 75 — ждут ЖП4; 120–122 low (хвосты 96а П1 и Э10а).
- tests/scenarios/memory_script.py: MEMORY_CONTEXT_CAP 2806 — хрупкий.
- mutmut без сети: `UV_OFFLINE=1`; несколько имён в `mutmut run` в zsh — `${=N}`. Папа-кабан — на fable.
- Хук запрещает правку docs/ через bash — только Edit/Write. Перед живым прогоном — бэкап saves/. ruff — 16 старых.

## Ссылки
- docs/plan-e10a.md, docs/plan-96a.md (следующий); последний коммит 7a9db1d.
- Отклик планирования Э10а — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-20-e10a.md.
- Очередь — docs/ROADMAP.md; беклог — docs/BACKLOG.md; NOTES.md. AGENTS.md, docs/RULES.md.
