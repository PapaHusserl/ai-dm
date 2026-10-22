# 129. OpenAI: завышенная оценка входа вытесняет прошлые ходы и соседние локации — нельзя уйти
status: done
priority: high
updated: 2026-10-22

(ЖП4, drunk_dragon-00000001, calls-018, ходы 581–600) Оценка входа рассказчика на openai `gpt-6.1-sol` ≈ 37,8k против
факта ≈ 26,4k (×1,43; `chars_per_token` 2,5 по умолчанию, перекрытия для openai нет — как 109 у gemini). Итог: с хода
581 вытеснены все 7 из 8 `recent_turns` (остаётся пол `recent_turns_floor = 1`), с хода 598 — все 8 соседних локаций:
в `locations` только текущая (`sanctuary_of_dawn`), `travel_to` некуда — рассказчик дважды отвечает
`unsupported_action` (ходы 599, 600: «иду в таверну» не выполнить). Две правки: (1) `openai = 3.5` в
`[master.chars_per_token_by_provider]` (`config/app_defaults.toml`; временно стоит в ~/.config/ai-dm/config.toml
проектировщика); (2) соседние локации текущего места (`nearby_locations`) — цели `travel_to`, их вытеснять нельзя
(в фиксированные, как текущая), иначе при любой недооценке бюджета герой застревает.

## Закрыто
Шаг «Фикс ЖП4», П1 (bbc9a96), 2026-10-22 — docs/plan-fix-zhp4.md
