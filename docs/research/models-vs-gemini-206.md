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

По 18+ данных мало. В пробу 185 добавить на каждой модели 1–2 хода с откровенной сценой в мире Влада и смотреть отказы, обрывы и смягчения. На DeepInfra ограничения правилами хостера не видно; у gemini 18+ упирается в политику Google, а не только в настройки safety settings.

## Откровенные сцены (18+) — дополнение от 2026-10-26

Влад уточнил: речь об откровенных сценах 18+. Про жёсткое насилие отдельно не искал. Мимоходом нашёл только запрет Google на контент, который «facilitates violence», в Prohibited Use Policy (17.12.2024). Как это применяется к художественному тексту — не проверено.

**Правила хостеров**

| Хостер | Запрет 18+ в правилах | Фильтр и его настройка | Источник |
|---|---|---|---|
| DeepInfra | Явного запрета нет. Под запретом только «illegal, fraudulent, deceptive purpose» (п. 11a). | Фильтрация не описана. Данные могут храниться для расследования «abuse». Отдельной AUP на странице нет; есть ли она где-то ещё — не проверено. | [DeepInfra ToS, ред. 15.10.2026](https://deepinfra.com/terms) |
| Google (Gemini API) | Запрещён «sexually explicit content… for the purpose of pornography or sexual gratification». Исключение — «artistic considerations», на усмотрение Google. | Категорию `HARM_CATEGORY_SEXUALLY_EXPLICIT` можно поставить на `BLOCK_NONE`. По официальной странице, у новых стабильных моделей «Block none» стоит по умолчанию (отдельно для 3.8-flash не проверено). По отзывам, модель всё равно решает сама. | [Generative AI Prohibited Use Policy, 17.12.2024](https://policies.google.com/terms/generative-ai/use-policy); [safety settings](https://ai.google.dev/docs/safety_setting_gemini); [форум, PG-13 romance](https://discuss.ai.google.dev/t/is-the-gemini-api-basically-useless-for-pg-13-romance-stories/37629) (дата не проверена) |

**Поведение моделей**

| Модель | Пропускает, смягчает или отказывает | Русский | Источник |
|---|---|---|---|
| gemini-3.8-flash | Модель не uncensored. Даже при `BLOCK_NONE` возможны обрывы и смягчения, по отзывам на старших версиях. Для 3.8 не проверено. | не проверено | см. выше |
| DeepSeek-V4-Pro | Отзывы противоречат друг другу. По одному, модель «не uncensored» и при аккуратной подаче долго держит роль до дисклеймеров. По другому, явное отсекает классификатор, причём стабильно. Это сайт, продающий NSFW-инструменты. | не проверено | [Picasso IA, обзор ролевой игры](https://blog.picassoia.com/deepseek-v4-pro-roleplay-nsfw-review), [Picasso IA, adult content](https://blog.picassoia.com/deepseek-v4-pro-adult-content-what-it-allows) (даты не проверены) |
| Kimi-K2.6 | Якобы спокойно пишет взрослый контент в художественном контексте. Это рекламный листикл без тестов. | не проверено | [Picasso IA](https://blog.picassoia.com/best-free-ai-chatbots-for-nsfw-conversations) (дата не проверена) |
| gemma-4-31B-it-turbo | Данных о стоковой модели нет. Существуют «decensored»-форки (Heretic, «−97 % отказов» по замеру автора), значит у стока отказы есть. Политика Gemma Prohibited Use — не проверено. | не проверено | [featherless, gemma-4 heretic](https://featherless.ai/models/llmfan46/gemma-4-26B-A4B-it-ultra-uncensored-heretic) |

Независимых бенчмарков доли отказов на NSFW ни для одной модели не нашёл, на русском тем более.

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
