# Разбор 503 и зависаний Gemini (2026-10-14) — papa-kaban + dyadya-kaban

## Вывод
- 503 не вызваны нашим запросом: тот же запрос (кэш, ~30k ток., те же параметры) успешно отвечал в 14:12:46 и 14:15:17; с 14:15:20 до 18:16 все ~40 вызовов `gemini-3.8-flash` в двух мирах и двух ролях (включая summarizer с телом 561 байт) — 503 за 2–4 с. Отказ по ёмкости модели/аккаунта на стороне Google. Вероятная причина «high demand» — депрекация 3.7/3.5 Flash с автомаршрутизацией на 3.8 Flash (08.10, сторонний пересказ, первоисточник не сверен). Ключ на предоплате (13.10 был 402 «prepayment credits are depleted»); на форуме 503 бывает ключе-/тарифо-зависимым.
- Зависания — наша проблема: `HttpOptions(timeout=180000)` даёт httpx-таймаут 180 с на каждую фазу (connect/handshake/read) и на каждый адрес getaddrinfo, без Happy Eyeballs, IPv6 первым → одна попытка до ~12 мин. 504 через 182 с — серверный дедлайн по заголовку `X-Server-Timeout: 180`. Висящая попытка в журнал не пишется (запись по завершении).
- SDK google-genai 2.28.0 сам не ретраит (`retry_options` не задан → `stop_after_attempt(1)`); 4 попытки — наши `[retry] delays=[1,3,10]`.
- Запрос: v1beta, без `thinking_config`, `temperature`, `service_tier`, `retry_options`; неподдерживаемое поле дало бы 400, не 503. Побочно: `create_cache` при 5xx повторяет create на каждой попытке (два запроса и 75 КБ без кэша).
- AI Studio (чат) — другой путь со своим пулом; честное сравнение — curl тем же ключом.

## Живая проверка (пользователь)
1. `curl -4 -s -o /dev/null -w '%{http_code} %{time_total}\n' -H "x-goog-api-key: $GEMINI_API_KEY" -H 'Content-Type: application/json' -d '{"contents":[{"parts":[{"text":"ping"}]}]}' https://generativelanguage.googleapis.com/v1beta/models/gemini-3.8-flash:generateContent`
2. То же для `gemini-3.6-flash` и `gemini-3.5-flash-lite`.
3. То же с `-6`.

## Предложение (мини-партия BACKLOG 60)
1. Принудительный IPv4 для Gemini: `GeminiAdapter.get_client` — `client_args={"transport": httpx.HTTPTransport(local_address="0.0.0.0")}`, флаг `[llm] gemini_ipv4 = true`; по желанию то же для Anthropic.
2. Таймаут по провайдеру/роли (Gemini 60–90 с); раздельный connect — только подклассом httpx-клиента SDK (архитектурный вопрос).
3. Сетевой сбой → запасная модель: `"network"` в `SOFT_REASONS` summarizer; при 503 high demand не ждать все 4 попытки.
4. Цепочка моделей 3.8-flash → 3.6-flash → 3.5-flash-lite в `[alternatives]` (решение проектировщика).
5. Меню ошибки: при сетевом сбое менять обе роли.
6. Наблюдаемость: лог старта попытки; `create_cache` не повторять create при 5xx.

## Открытые вопросы
- Модели по умолчанию менять или только добавить запасные.
- Подкласс httpx ради connect-таймаута или IPv4 + меньший `timeout_s`.
- Тариф ключа (предоплата/flex?), `service_tier`; VPN.

## Живая проверка пользователя (2026-10-14, вечер, curl -4, «ping»)
Только `gemini-3.5-flash-lite` вернула 200; `gemini-3.8-flash` и `gemini-3.6-flash` — не 200. Крошечный запрос тоже отвергается → 503 не из-за нашего запроса. Запасная модель, которая сейчас отвечает, — 3.5-flash-lite.
Биллинг (пользователь, 2026-10-14): тариф paid, кредиты $109.54, service tier и прочие настройки — по умолчанию. Гипотеза «кончились кредиты» снята.
Ping моделей (пользователь, вечер 2026-10-14, curl -4): 200 — gemini-4-argon (12,5 с), gemini-3-flash-preview (6,5 с), ранее gemini-3.5-flash-lite; 503 — gemini-pro-latest, gemini-3.1-pro-preview, gemini-flash-latest, gemini-3.7-flash, gemini-3.5-flash (+3.6-flash ранее); 000 (таймаут 30 с) — gemini-3.8-flash; 404 — gemini-2.5-pro, gemini-2.5-flash. Вывод: перегрузка широкая (Flash и Pro), не только 3.8; отвечают argon и 3-flash-preview.
