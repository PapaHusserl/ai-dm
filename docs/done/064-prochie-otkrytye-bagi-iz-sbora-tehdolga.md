# 64. Прочие открытые баги из сбора техдолга 2026-10-14
status: done
priority: low
updated: 2026-10-17

(docs/plan-techdebt.md)
- T3 ✅ (партия #18 ТВ: текст раунда с отклонённым вызовом сохраняется) — было: отклонённый вызов инструмента в ответе выбрасывает весь текст рассказа (`master/session.py`, `if not has_invalid: result.texts += texts`); ход 436 dusk.
- T5 ✅ (партия #18 ТВ: приписка `CHOICES_ASK`, тег `choices_retry`) — было: слабые модели (flash-lite) дают варианты списком «- …» в тексте вместо `offer_choices` (drunk_dragon 130–133).
- T6 ✅ (партия #20 ТМ, 2026-10-16: защиты `gold_repeat`/`rest_repeat`, итоги вызовов в `recent_turns`; там же Ф3 ЖП1 — повтор `rest long` в vale t21; docs/plan-tm.md) — было: повторный `gold` +2000 cp на ходах 130–132 drunk_dragon (копирование из recent_turns), лишние 6000 cp в сейве — оставить (решение проектировщика 2026-10-15: «пусть герой побогаче будет»); мазь дважды rejected, а рассказ описывает лечение.
- T7 ✅ (партия #22 ТС, 2026-10-16: промпт с ориентиром, обрезка движком после `summary_trim_after` переполнений, тег `summary_trimmed`; docs/plan-ts.md) — summarizer haiku-4-5 не укладывается в 600 симв. → 5–6 вызовов на границу.
- T9 ✅ (партия #21 ТО, 2026-10-16: `already_reported`, один репорт на попытку хода и модель; docs/plan-to.md, docs/plan-to.md) — было: одинаковые авто-репорты при каждом повторе упавшего хода.

## Закрыто

Шаг T3/T5 — ТВ, T6 — ТМ, T7 — ТС, T9 — ТО, 2026-10-17. План: docs/plan-tv.md, docs/plan-tm.md, docs/plan-ts.md, docs/plan-to.md
