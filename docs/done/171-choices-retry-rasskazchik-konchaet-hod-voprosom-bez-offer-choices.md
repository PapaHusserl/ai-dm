# 171. choices_retry — рассказчик кончает ход вопросом без offer_choices
status: done
priority: high
updated: 2026-10-24

(разбор репортов dusk_academy 2026-10-23) 13 ходов (+5 в группе overflow; t837, t841, t903, t958, t978…; gemini-4-argon,
gemini-3.8-flash): текст кончается вопросом, `offer_choices` нет → третий вызов `CHOICES_ASK` (`master/session.py:341,
368, 484`) с полным контекстом — задержка и цена (~4 % ходов). Игрок видит варианты. Вариант: усилить правило рассказчика.

## Закрыто

Шаг «Фикс dusk», 2026-10-24, коммит 95856f6 — docs/plan-fix-dusk.md.
