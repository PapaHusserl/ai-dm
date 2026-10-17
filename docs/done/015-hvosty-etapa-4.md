# 15. Хвосты этапа 4
status: done
priority: high
updated: 2026-10-18

(аудит кабана-свекрови, 2026-10-05)
- Калибровка (живой прогон, saves/drunk_dragon-d2aabbcf, 50 запросов нарратора): Gemini Flash — api/estimate 0.76–0.90
  (оценка завышена на 10–24%, безопасно); Anthropic Sonnet — 1.09–1.14 (оценка ЗАНИЖЕНА до 14%, в пределах 20%, но не в
  безопасную сторону). Решить: chars_per_token по провайдеру (Anthropic ~2.2) или общий запас. ✅ ТБ: механизм `chars_per_token_by_provider`; значение anthropic = 2.2 — в Ж0 (BACKLOG 77).
- `meta.context.api_tokens` (src/ai_dm/master/session.py:113) у Gemini на запросе, создающем явный кэш, считает кэш дважды
  (cache_write == cache_read) → ложные 1.09–1.41. Для калибровки считать без cache_write у Gemini. ✅ ТБ: `api_tokens(usage, provider)`.
- Окно мока 20 000 в tests/scenarios/memory_script.py подбирать заново при росте правил/tools нарратора.
- Пятая ступень вытеснения: выкидывать выжимки глав, уже свёрнутые в game_summary (G1, вариант «б»).
- Риск 6 плана (кэш памяти Gemini на Pro) закрыт решением E1 (память внутри явного кэша).

✅ Все подпункты закрыты: cpt anthropic 2.2 и пятая ступень вытеснения — Ж0 подшаг 0 (f16e8fa); `api_tokens` без двойного
cache_write — ТБ; окно мока — `WINDOW` 25400 (Ж0 подшаг 0); риск 6 — решение E1. Закрывается в done/ при коммите Ж0 подшага 3.

## Закрыто

Ж0, 2026-10-18, подшаг 0 (f16e8fa). План: docs/plan-zh0.md
