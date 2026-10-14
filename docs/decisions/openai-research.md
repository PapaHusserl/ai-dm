# OpenAI как третий провайдер — ресёрч (2026-10-15)

Автор: дядя-кабан. Факты помечены ссылками; «догадка» — моя оценка, не проверено.

## 1. Модели и цены (Standard, ≤272K input, $/1M)
Источник: официальная страница цен https://developers.openai.com/api/docs/pricing (прочитана 2026-10-15).

| Модель | Input | Cached | Output | Окно / макс. вывод | Reasoning effort | Статус |
|---|---|---|---|---|---|---|
| gpt-6-astra | 10.00 | 1.00 | 50.00 | 1.05M / н.п. | — | флагман, вышел в сент. 2026 |
| gpt-6.1-sol | 2.00 | 0.10 | 10.00 | 1.05M (922K in) / 128K | low…max, **без none** | новейший Sol; cutoff 2026-04-30 |
| gpt-6-sol | 2.00 | 0.20 | 10.00 | 1.05M / 128K | none…max | вышел 2026-09-22 |
| gpt-6-luna | 0.10 | 0.01 | 0.50 | 1.05M / 128K | none…max | вышел 2026-09-22, «high-volume» |
| gpt-5.6-sol / terra / luna | 4/2/0.20 | 0.40/0.20/0.02 | 20/12/1.20 | 1.05M | — | прошлое поколение, Sol — промо до ≥2026-11-21 |
| gpt-5.4-mini / nano | 0.75 / 0.20 | 0.075 / 0.02 | 4.50 / 1.25 | 400K | — | nano deprecated, удаление 2027-04-01 (mem0) |

- Модельные страницы: https://developers.openai.com/api/docs/models/gpt-6.1-sol , .../gpt-6-sol , .../gpt-6-luna
- Reasoning-токены не видны, но оплачиваются как output (`output_tokens_details.reasoning_tokens`) — https://developers.openai.com/api/docs/guides/reasoning
- >272K input — двойной тариф (нам не грозит).
- Даты релиза Sol/Luna 2026-09-22: https://iphonesoft.fr/2026/09/23/openai-gpt-6-sol-luna , https://computingforgeeks.com/gpt-6-sol-luna-released-features-benchmarks/
- Дата релиза gpt-6.1-sol — не проверено (официальная статья openai.com/index/introducing-gpt-6-1-sol/ отдала 403).

## 2. API
- **Responses API — рекомендован.** Важно: **Chat Completions не поддерживает function calling у gpt-6-astra и gpt-6.1-sol**; у gpt-6-sol и gpt-6-luna — только при `reasoning_effort=none`. (guides/reasoning, models/*). Для нас — Responses обязателен.
- **Function calling** (https://developers.openai.com/api/docs/guides/function-calling): параллельные вызовы по умолчанию, отключаются `parallel_tool_calls=false`. `strict: true` рекомендован: все поля в `required`, опциональные через `null` в типе, `additionalProperties:false` везде; несовместимая схема → отказ запроса. В Responses без `strict` API пытается нормализовать схему. Мягкая рекомендация — <20 функций в начале хода (у нас 30); есть tool search / `defer_loading` (gpt-5.4+).
- **Reasoning items**: настоятельно рекомендуется возвращать все reasoning/function_call/function_call_output после последнего user-сообщения, не меняя их. При `store=false` reasoning items приходят с `encrypted_content` по умолчанию (флаг `include` — legacy). Альтернатива — `previous_response_id` (store=true).
- **Prompt caching** (https://developers.openai.com/api/docs/guides/prompt-caching): автоматический; для GPT-5.6+ порог 1024 токена, чтение 0.1× (0.05× у gpt-6.1-sol), **запись в кэш 1.25×**, TTL `30m` (не менее 30 мин после последнего использования); опционально явные breakpoints и `prompt_cache_key`.
- **Python SDK**: `openai` 3.31.0 от 2026-10-14 — https://pypi.org/project/openai/

## 3. Политика контента
- Model Spec (версия 2026-08-18, помечена как не текущая): эротика — system-level ограничение, «не генерировать эротику… кроме научного, исторического, новостного, художественного контекста»; сексуальный контент с несовершеннолетними — абсолютный запрет; разработчик не может переопределить system-level. https://model-spec.openai.com/2026-08-18.html . Текущую версию спеки и usage policies прочитать не удалось (redirect/403) — не проверено.
- «Adult mode» для верифицированных взрослых: анонсирован окт. 2025, отложен 2026-03-06, по сообщениям приостановлен 2026-03-26; запуска не подтверждено; это про ChatGPT, **API-режима для взрослого контента нет** (по найденному). https://techcrunch.com/2026/03/07/openai-delays-chatgpts-adult-mode-again/ , https://justainews.com/blog/adult-mode-in-chatgpt-explained-nsfw-erotica-porn-policy/ , https://www.fastcompany.com/91504593/openai-delayed-adult-mode-age-gating-ai
- Сравнение с Gemini: контролируемого бенчмарка ложных отказов нет. Анекдотично — жалобы на блок флирта/PG-13 романтики в Gemini API и «с OpenAI таких проблем нет»: https://discuss.ai.google.dev/t/is-the-gemini-api-basically-useless-for-pg-13-romance-stories/37629 , https://discuss.ai.google.dev/t/gemini-2-5-creative-writing-vs-filtering/75171
- Догадка: у OpenAI нет жёсткого постфильтра типа PROHIBITED_CONTENT, отказ формируется самой моделью (текстом), поэтому романтика/намёки/fade-to-black в художественной прозе со взрослыми персонажами, скорее всего, пройдут; откровенная эротика — нет. Слово «студенты академии» может провоцировать осторожность модели (риск ассоциации с несовершеннолетними) — явно указывать возраст в системном промпте мира. Проверять своим набором промптов.

## 4. Качество прозы
- EQ-Bench Creative Writing v3 (данные агрегаторов, официальную таблицу eqbench.com прочитать не удалось): GPT-6 Astra ~2173 (1-е), GPT-6 Sol ~2125 (4-е), Claude Fable 5.1 ~2162, Claude Opus 5 ~2133. https://llmlearner.com/rankings/creative-writing , https://llm-stats.com/benchmarks/creative-writing-v3 . Источники противоречат друг другу — не проверено.
- По GPT-6.1 Sol и Luna независимых оценок творческого письма не найдено; русскоязычных отзывов о прозе/ролевых играх не найдено (поиск на русском дал только описания моделей: https://www.cometapi.com/ru/gpt-6-1-sol-vs-gpt-6-sol/ ).
- Следование длинным правилам: прямых данных нет. Документация предупреждает, что примеры в промпте могут ухудшать reasoning-модели (function-calling guide) — у нас 47 КБ правил с примерами, стоит учесть.

## 5. Надёжность
- Тиры (с 2026-10-06, по одному источнику, не подтверждено официально): Build ($5, лимит $500/мес), Launch ($100, $5k/мес), Grow ($500, $200k/мес). https://fourweekmba.com/ai-openai-cuts-api-tiers-to-3-500-unlocks-200k-a-month/ . Названия Build/Launch/Grow совпадают с модельными страницами OpenAI.
- Лимиты (офиц. страницы моделей): gpt-6.1-sol / gpt-6-sol Build 5k RPM / 1M TPM; gpt-6-luna Build 5k RPM / 2M TPM. Для одного игрока — с огромным запасом.
- Инциденты: короткие деградации 2026-10-02, 10-06 (~36 мин, ChatGPT/API), 10-07 (62 мин, Codex/Work) — https://apistatuscheck.com/blog/openai-outage-2026-10-06 , https://sessionwatcher.com/news/codex-work-mode-dot-degradation-october-7-2026 , https://uptimerobot.com/is-it-down/openai/2026-10-02/ . Систематической перегрузки 503 масштаба Gemini (с 14.10) не найдено. Официальный status.openai.com не проверял.

## 6. Итог и стоимость хода
Допущения (догадка): ход = 3 вызова × 30k input = 90k, из них ~80k читаются из кэша, ~10k новые (пишутся в кэш); output ≈ 4k (2k прозы + reasoning + вызовы). Для OpenAI 5.6+ новые токены считаю по 1.25× (запись в кэш).

| Модель | Новые input | Кэш | Output | Итого/ход | vs Gemini |
|---|---|---|---|---|---|
| gemini-3.8-flash | $0.0075 | $0.0060 | $0.0150 | **~$0.029** | 1× |
| gpt-6.1-sol | $0.025 | $0.008 | $0.040 | **~$0.073** | ~2.5× |
| gpt-6-sol | $0.025 | $0.016 | $0.040 | ~$0.081 | ~2.8× |
| gpt-6-astra | $0.125 | $0.080 | $0.200 | ~$0.405 | ~14× |
| gpt-6-luna | $0.00125 | $0.0008 | $0.002 | ~$0.004 | ~0.14× |

Reasoning effort сильно двигает output: на `high` reasoning может быть кратно больше прозы — держать `low`/`medium`.

**Рекомендация (вердикт: собрать из готового):**
- narrator — **gpt-6.1-sol** через Responses API, effort `low`/`medium`, `store=false` + encrypted reasoning (или `previous_response_id`). Дешевле кэш, новее; ~2.5× цены Gemini за ход. Astra — только если Sol не тянет прозу (14×).
- world / summarizer — **gpt-6-luna** (effort `none`/`low`), дешевле Gemini Flash.
- Перед решением — собственный A/B на русском: 10–20 ходов из реальных сохранений, включая мир с романтикой; считать отказы и качество.

## Открытые вопросы
- Готов ли Влад к ~2.5× цены хода на narrator ради стабильности/романтики?
- Нужна ли откровенная эротика, или достаточно романтики/fade-to-black? От ответа зависит, решит ли OpenAI проблему вообще.

Решение проектировщика 2026-10-15: OpenAI-провайдер пока не делаем — ждём, что Google разгрузит Gemini; ресёрч оставлен на случай возврата к вопросу.
