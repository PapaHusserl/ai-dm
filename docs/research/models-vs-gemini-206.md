# Модели против gemini — ресёрч BACKLOG 206 (2026-10-26)

Дядя-кабан; сохранил оркестратор из хэнд-бэка.

**Идея:** найти 2–3 дешёвые модели для роли рассказчика на OpenAI-совместимом хостере (приоритет — DeepInfra), чтобы конкурировать с gemini-3.8-flash.

**Эталон** (src/ai_dm/config/app_defaults.toml, `profiles.gemini.narrator` → `gemini-3.8-flash`): $0,75 вход / $3,75 выход / $0,075 чтение кэша за 1M токенов; хранение кэша $0,50 за 1M токенов в час. С 2027-01-01 по комментарию в конфиге цены станут 1,50 / 7,50 / 0,15.

**Как считал цену хода:** вход 30k, из них 28k из кэша и 2k новых; выход 1,5k. Токены мышления сверх этого не учтены, а у мыслящих моделей они увеличат выход.

Цены взяты с живой страницы https://deepinfra.com/pricing на 2026-10-26. Скорость и время до первого токена — по независимым замерам Artificial Analysis (страница DeepInfra): https://artificialanalysis.ai/providers/deepinfra

## Ближайшие аналоги

| Модель (DeepInfra) | Вход / выход / кэш, $ за 1M | $ за ход | Скорость, ток/с | До первого токена | Кэш префикса | Окно | Tool calls | Художественный русский |
|---|---|---|---|---|---|---|---|---|
| **gemini-3.8-flash (эталон, Google)** | 0,75 / 3,75 / 0,075 + хранение | **≈ 0,0092** + хранение | 129–141 | ≈ 25 с (High, вместе с мышлением) [AA](https://artificialanalysis.ai/models/gemini-3-8-flash/providers) | явный | см. конфиг | работает в проекте | эталон проектировщика |
| **DeepSeek-V4-Pro** | 1,30 / 2,60 / 0,10 | **≈ 0,0093** | 83 (FP4) | 0,94 с | есть, по цене кэша на прайсе DeepInfra; приходит ли `cached_tokens`, не проверено | 1024k | не проверено; у V4-Flash на DeepInfra в П3 ошибок API не было (plan-184, «Итог») | EQ-Bench Creative v3, rubric 16,45 — по стороннему посту [featherless](https://featherless.ai/blog/best-ai-for-creative-writing-2026); по русскому не проверено |
| **Kimi-K2.6** | 0,75 / 3,50 / 0,15 | **≈ 0,011** | 89 (reasoning, FP4); 67 (non-reasoning) | 0,8 с | есть по прайсу; `cached_tokens` не проверены | 256k | для сборки NVIDIA NVFP4 по K2 Vendor Verifier: 10,4 % вызовов с ошибкой схемы. Для DeepInfra данных нет, не проверено. [Kimi blog](https://www.kimi.com/en/blog/kimi-vendor-verifier) | По сторонним постам — лучший открытый результат в EQ-Bench Creative v3 (rubric 16,67) [featherless](https://featherless.ai/blog/best-ai-for-creative-writing-2026), [promptquorum](https://www.promptquorum.com/power-local-llm/best-local-llm-creative-writing); на самом лидерборде не проверено. **Риск:** AA пометил K2.6 как устаревшую, преемник — Kimi-K3 ($2,85 / $14,25, дорого) [AA](https://artificialanalysis.ai/de/models/kimi-k2-6-non-reasoning/providers) |
| gemma-4-31B-it-turbo | 0,09 / 0,34 / 0,05 | **≈ 0,0021** | 22–25 (замер AA для gemma-4-31B; для turbo отдельного замера нет, не проверено) | 1,4–1,7 с | есть по прайсу | 256k | не проверено | EQ-Bench Creative v3: rubric 16,01, Elo 1408 — по стороннему посту; по русскому не проверено |
| Qwen3.5-397B-A17B | 0,45 / 3,00 / 0,22 | ≈ 0,0116 | 44–48 | 1,1–1,2 с | есть | 256k | не проверено | rubric 16,00, Elo 1486 — по стороннему посту. Семейство Qwen проектировщику не понравилось |
| Nemotron-3-Ultra-550B | 0,50 / 2,20 / 0,10 | ≈ 0,0071 | 70–99 | 1,4 с | есть | 256k | не проверено | данных о прозе нет |

Почему не беру остальные с прайса DeepInfra:
- gemini-3.1-flash-lite на DeepInfra ($0,25 / $1,50) — без кэша и старее нашего flash.
- DeepSeek-V4-Flash-0731 — то же семейство, что и отвергнутый deepseek-v4-flash.
- DeepSeek V4.1 Flash есть в замерах AA, но в прайсе DeepInfra её нет — не проверено.

## Другие хостеры

Kimi-K2.6 у Together AI быстрее: ~472 ток/с ([AA](https://artificialanalysis.ai/de/models/kimi-k2-6-non-reasoning/providers)). Оплата из Узбекистана там не проверена. Fireworks и CoreWeave — то же самое, оплата из Узбекистана не проверена.

## Строительные блоки

Уже готовый адаптер Chat Completions и профиль `[providers]` из шага 184. Новые модели подключаются профилем в config.toml без кода, по образцу DeepInfra из П3.

## Свободная ниша / уникальность

Ни один найденный бенчмарк не измеряет художественный текст **на русском**. Решить может только собственная проба 185.

## Вердикт

**Собери из готового.** Механизм уже есть, нужна проба моделей:
1. **DeepSeek-V4-Pro** — по цене хода как gemini, высокий рейтинг прозы, быстрый.
2. **Kimi-K2.6** — сильнейшая проза среди открытых моделей по сторонним данным, на ~20 % дороже gemini. Модель устаревает, а преемник K3 дорог.
3. По желанию **gemma-4-31B-it-turbo** — в 4 раза дешевле gemini, но медленная (~22–25 ток/с), риск повторить жалобу на qwen.

Сэкономить при той же прозе, скорее всего, не выйдет: реальная альтернатива — «та же цена, другой хостер». Gemini в 2027 году подорожает вдвое, и тогда V4-Pro и K2.6 станут дешевле его примерно в 2 раза.

## Открытые вопросы к проектировщику

- Цель — снизить цену или найти замену gemini по прозе при той же цене? Если снизить, из найденного проходит только gemma, и то с риском по скорости.
- Мышление у V4-Pro и K2.6 включать или нет? С ним вырастут выход и время хода.

## Источники

- https://deepinfra.com/pricing
- https://artificialanalysis.ai/providers/deepinfra
- https://artificialanalysis.ai/models/gemini-3-8-flash/providers
- https://artificialanalysis.ai/de/models/kimi-k2-6-non-reasoning/providers
- https://featherless.ai/blog/best-ai-for-creative-writing-2026
- https://www.promptquorum.com/power-local-llm/best-local-llm-creative-writing
- https://www.kimi.com/en/blog/kimi-vendor-verifier
- docs/plan-184.md (Итог, П3)
