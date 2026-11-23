# 344. Правила рассказчика для openai упёрлись в предел 300 токенов
status: done
priority: low
updated: 2026-11-23

(М0 П3б, docs/plan-m0.md, «Файлы» — «Сверка кода П3б») `narrator_rules_openai.md` после пункта о пути — 299
токенов при пределе 300 (`test_prompt_openai_extra.py::test_rules_extra_is_within_300_tokens`). Следующий пункт
не войдёт без сжатия старых или пересмотра предела.

## Закрыто
Шаг М0, партия П4, 2026-11-23 — docs/plan-m0.md (решение 129: предел 300 → 380).
