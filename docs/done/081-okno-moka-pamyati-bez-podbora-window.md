# 81. Окно мока памяти без подбора WINDOW
status: done
priority: low
updated: 2026-10-18

`tests/scenarios/memory_script.py:WINDOW` (test_stage4_memory) подбирается под размер статики: в Ж0 подшаге 2 поднят
25400 → 26000, и проходит только это значение — следующая правка `narrator_rules` снова сломает тест. Перевести на
большое окно и фиксированный `context_cap`, как мок памяти NPC (`npc_memory_bundle`). Рекомендация mama-kaban, ревью Ж0
подшага 2.

## Закрыто

ТХ, 2026-10-18. `memory_script.memory_settings` — фиксированные `NPC_MEMORY_WINDOW` и `MEMORY_CONTEXT_CAP`, `WINDOW` убран.
План: docs/plan-tx.md
