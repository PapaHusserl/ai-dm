# 106. Рассказчик боя видит варианты действий и сам кончает бой
status: done
priority: high
updated: 2026-10-20

(авто-репорт t446, drunk_dragon) В `combat_narrate` рассказчику отдаются `combat.options` (140 вариантов, ≈ 6,5k токенов,
`master/prompt.py:452–453`); он зовёт `player_action` ×2 (`not_available_in_mode`), затем `end_combat` на раунде 1 при
5 живых врагах. Не отдавать options в `combat_narrate`; `end_combat` — только сдача/бегство (narrator_rules.md:38,
описание `EndCombat`). В Фикс ЖП3 — решение проектировщика 2026-10-20 (docs/plan-fix-zhp3.md).

## Закрыто
Шаг «Фикс ЖП3», партия П2, 2026-10-20 — docs/plan-fix-zhp3.md
