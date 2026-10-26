# Хостеры open-weight моделей и адаптер ai-dm: совместимость API (шаг 184)

Дата проверки: 2026-10-26. Дополняет docs/research/business-hosting-research.md и не повторяет его.
Адаптер игры использует OpenAI Responses API: `responses.create`, `include=["reasoning.encrypted_content"]`, `reasoning.effort`, `usage.input_tokens_details.cached_tokens`.

## 1. Поддерживаемые API

| Хостер | Responses API | encrypted_content / reasoning.effort | Chat Completions |
|---|---|---|---|
| OpenRouter | Есть, `/api/v1/responses`. Работает без хранения состояния: запросы с `store: true` и с `previous_response_id` получают 400 [1] | `include: reasoning.encrypted_content` есть в схеме [2]. В примере ответа поле приходит, но пример многоходового диалога не передаёт его обратно; для моделей не от OpenAI это не описано [3]. `effort` есть, список моделей не приведён [3]. Обратную передачу для DeepSeek/Qwen не проверял | Да, это основной путь |
| DeepInfra | В документации нет: описаны только `/v1/openai/chat/completions`, embeddings и изображения [4]. Проба: POST `/v1/openai/responses` без ключа отвечает 401, как и chat/completions; несуществующий путь отвечает 404. Похоже, маршрут есть, но не документирован; поведение не проверено | `reasoning_effort` — параметр Chat Completions [4] | Да |
| Cloud.ru FM | Нет. В `/v1/models` у моделей перечислены `/v1/chat/completions`, `/v1/completions`, `/tokenize`, у gpt-oss-120b ещё `/v1/messages`. POST `/v1/responses` отвечает 404 [5][6] | В документации нет [6] | Да, base URL `https://foundation-models.api.cloud.ru/v1/` [6] |

## 2. Кэш и cached_tokens
- OpenRouter: DeepSeek кэширует автоматически, Qwen (Alibaba) — только по явным `cache_control`. Счётчик в usage — `prompt_tokens_details.cached_tokens` в Chat Completions и `usage.input_tokens_details` в Responses [7]. У Qwen3-235B цены за чтение кэша нет [8].
- DeepInfra: у DeepSeek V4/V4.1 есть тег `prompt_cache` и цена `cache_read_tokens`, у Qwen3-235B-Instruct-2507 их нет [9]. Поле `cached_tokens` в usage документация не описывает [4]; не проверено.
- Cloud.ru: цена чтения кэша есть только у DeepSeek-V4.1-Flash и у внешних моделей OpenAI; у V4-Pro и V4-Flash её нет [5]. Поле cached_tokens документация не описывает; не проверено.

## 3. Цены за 1M токенов (вход / кэш / выход) и окно контекста

| Хостер | Модель | Вход | Кэш | Выход | Контекст |
|---|---|---|---|---|---|
| OpenRouter [8] | deepseek-v4-pro | $0.955 | $0.080 | $1.911 | 1 048 576 |
| OpenRouter [8] | deepseek-v4-pro-0813 | $0.66 | $0.022 | $1.98 | 1 048 576 |
| OpenRouter [8] | deepseek-v4-flash | $0.091 | $0.018 | $0.182 | 1 048 576 |
| OpenRouter [8] | deepseek-v4.1-flash | $0.02 | $0.015 | $1.00 | 1 048 576 |
| OpenRouter [8] | qwen3-235b-a22b-2507 | $0.09 | — | $0.55 | 262 144 |
| OpenRouter [8] | qwen3-235b-a22b-thinking-2507 | $0.45 | — | $3.50 | 128 000 |
| DeepInfra [9] | DeepSeek-V4-Pro (и -0813) | $1.30 | $0.10 | $2.60 | 1 048 576 |
| DeepInfra [9] | DeepSeek-V4-Flash | $0.09 | $0.018 | $0.18 | 1 048 576 |
| DeepInfra [9] | DeepSeek-V4-Flash-0731 | $0.06 | $0.015 | $0.18 | 1 048 576 |
| DeepInfra [9] | DeepSeek-V4.1-Flash | $0.20 | $0.006 | $0.60 | 1 048 576 |
| DeepInfra [9] | Qwen3-235B-A22B-Instruct-2507 | $0.09 | — | $0.55 | 262 144 |
| Cloud.ru [5] | DeepSeek-V4-Pro | 183 ₽ | — | 732 ₽ | 1 048 576 |
| Cloud.ru [5] | DeepSeek-V4-Flash | 43.30 ₽ | — | 86.58 ₽ | не проверено |
| Cloud.ru [5] | DeepSeek-V4.1-Flash | 64.94 ₽ | 6.5 ₽ | 194.81 ₽ | не проверено |
| Cloud.ru | Qwen3-235B | на 2026-10-26 в каталоге нет [5]; в 2025 была, 17/50 ₽ [10] | | | |

Для OpenRouter указаны цены провайдера по умолчанию. Входит ли НДС в цены Cloud.ru — не проверено. Цены меняются часто, перед расчётом их нужно брать из живых `/models`.

## 4. Доступ из РФ и Узбекистана, способы оплаты
- OpenRouter: российские карты не проходят. Баланс пополняют криптовалютой (стейблкоины), через посредников (рубли или СБП, с комиссией) или зарубежной картой [11][12]. Источники — рекламные статьи. Узбекистан — не проверено.
- DeepInfra: способ оплаты и доступ из РФ и Узбекистана не проверены.
- Cloud.ru: российский провайдер, оплата в рублях [10]. Доступ физлицу и нерезиденту (Узбекистан) — не проверено.

## Вывод
Responses API подходит только для OpenRouter, и там это бета без хранения состояния; передача encrypted_content для DeepSeek и Qwen не документирована. DeepInfra и Cloud.ru работают через Chat Completions. Для нескольких хостеров нужен адаптер Chat Completions: `reasoning_effort`, `prompt_tokens_details.cached_tokens`, без зашифрованных рассуждений.

## Источники (проверено 2026-10-26)
1. https://openrouter.ai/docs/api/reference/responses/overview.md
2. https://openrouter.ai/docs/api/api-reference/responses/create-responses.md
3. https://openrouter.ai/docs/api/reference/responses/reasoning.md
4. https://docs.deepinfra.com/chat/overview
5. https://foundation-models.api.cloud.ru/v1/models — живой JSON (эндпоинты и поля `*_cost`), плюс пробы POST `/v1/responses`
6. https://cloud.ru/docs/foundation-models/ug/topics/api-ref
7. https://openrouter.ai/docs/guides/best-practices/prompt-caching
8. https://openrouter.ai/api/v1/models — живой JSON
9. https://api.deepinfra.com/v1/openai/models — живой JSON (metadata.pricing и tags), плюс пробы POST `/v1/openai/responses`
10. https://www.comnews.ru/content/241030/2025-09-03/2025-w36/1018/cloudru-delaet-otkrytye-llm-dostupnee
11. https://vc.ru/services/3008513-kak-popolnit-openrouter-iz-rossii
12. https://dtf.ru/howto/5051854-kak-oplatit-openrouter-iz-rossii
