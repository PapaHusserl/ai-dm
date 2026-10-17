# 63. Отношения с NPC не переживают сессию
status: done
priority: high
updated: 2026-10-18

(техдолг T8, 2026-10-14; высокая для романтических пресетов)
`npc.relations_text` объявлен (state/world.py:94), но нигде не пишется; `favor {}`, `attitude` — только число. Отношения держатся лишь в выжимках сцен (600 симв.) и game_summary. Репорт dusk_academy t411 (Люциан: attitude 10, relations_text ""). Связано с BACKLOG 20 и Ж0–Ж3 — в груминг блока Ж. Детали — docs/plan-techdebt.md (T8).

## Закрыто

Ж0, 2026-10-18, подшаги 1–2 (9de1f9a, 8665cb0). План: docs/plan-zh0.md
