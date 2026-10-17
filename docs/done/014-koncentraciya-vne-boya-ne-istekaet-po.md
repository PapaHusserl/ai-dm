# 14. Концентрация вне боя не истекает по времени
status: done
priority: low
updated: 2026-10-13

(бывш. второй раздел 11) ✅ К1
Заклинание с К вне боя (cast_spell) ставит creature.concentration и эффект длительности kind=spell; эффект истекает по часам,
а concentration остаётся до следующего заклинания. Снимать концентрацию по истечении длительности.
К0а: поле `Concentration.until_s` есть с v9, логика — К1.
✅ К1: `until_s` = часы мира + длительность (вне боя и в бою); `expire_concentration` после `rest`, `advance_time`, `travel`, в `end.conclude`, в конце хода (`TurnRunner.attempt`) и на границе сцены; Метка вне боя — 1 ч; старые сейвы с `until_s=None` — бессрочно до следующего заклинания. План docs/plan-k1.md.

## Закрыто

Шаг К1, 2026-10-13. План: docs/plan-k1.md
