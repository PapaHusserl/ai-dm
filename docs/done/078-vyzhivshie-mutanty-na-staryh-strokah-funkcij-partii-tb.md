# 78. Выжившие мутанты на старых строках функций партии ТБ
status: dropped
priority: low
updated: 2026-10-18

mutmut партии ТБ (docs/plan-tb.md): выжившие на строках до партии — `protocol.handlers.combat.start_combat` ≈ 175
(tests/unit/protocol не входил в TESTS), `TurnRunner.take_boundary` 10, `TurnRunner.mark_journal` 1, `Journal.mark_turn` 9,
`PromptBuilder.world_block` 7, `PromptBuilder.build` 2, `ui.cli.campaign_registry` 3, `ContentRegistry.with_items` 2.
Добить при касании функций.

## Закрыто

Снят, Ж0, 2026-10-18 (docs/plan-zh0.md). `world_block`, `build`, `take_boundary`, `mark_journal`, `mark_turn` затронуты в
Ж0 подшаге 0 (f16e8fa): выжившие разобраны ревью, признаны эквивалентными или шумовыми и приняты. Хвост
`protocol.handlers.combat.start_combat` (≈ 175) — в Ж1, когда шаг коснётся функции.
`ui.cli.campaign_registry` (3) и `ContentRegistry.with_items` (2) сняты решением проектировщика 2026-10-18.
