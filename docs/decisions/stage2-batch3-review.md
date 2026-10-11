# Ревью партии 3 этапа 2 (слой llm): спецификация правок

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `devtools/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

## Блокирующие
B1. Gemini `FINISH_REASONS`: `PROHIBITED_CONTENT`, `BLOCKLIST`, `SPII`, `RECITATION` → `refusal` (как SAFETY); строка в gemini-facts.
B2. Конфиг Gemini (`app_defaults.toml`, `config/app.py`):
    - `[prices.gemini-3.8-flash]` input 750000, output 3750000, cache_read 75000, cache_write = input (комментарий: неявный кэш
      Gemini, адаптер cache_write не заполняет; «пересмотреть с 2027-01-01: 1.50/7.50/0.15»);
      `[prices.gemini-3.5-flash-lite]` 300000 / 2500000 / 30000, cache_write = input;
    - `[context_windows]` обеим 1000000 (комментарий «консервативно, сверить»);
    - `AppConfig.profiles: dict[str, RolesConfig] = {}`; `[profiles.gemini.narrator|world|summarizer]` (narrator —
      gemini-3.8-flash, world/summarizer — gemini-3.5-flash-lite; effort для Gemini не используется — допустимо поле, игнорируется);
      `check_models_known` проверяет и роли профилей.
B3. `devtools/live_smoke.py`: для `gemini` роль из `cfg.profiles["gemini"].narrator`; effort передаётся, только если модель =
    модели роли (иначе — без effort).
B4. Gemini-клиент с таймаутом: `genai.Client(api_key=..., http_options=types.HttpOptions(timeout=cfg.retry.timeout_s * 1000))` (мс).

## Желательные (делаются сейчас)
D5. Gemini `FunctionResponse` с `id`, если `call_id` пришёл от API (не синтезированный `gemini-…`):
    `Part(function_response=FunctionResponse(id=..., name=..., response=...))`; иначе — как сейчас. Риск в gemini-facts.
D6. Gemini: сборка `contents`/`config` до `try` (как у Anthropic); неизвестный `call_id` → понятный `ValueError`.
D7. `errors.NETWORK_NAMES` + `"TransportError"` (общий предок транспортных ошибок httpx), `RemoteProtocolError`, `ReadError`, `WriteError`.
D8. Журнал устойчив к обрыву: нечитаемая последняя строка сегмента пропускается при чтении; перезапись сегмента в `mark_turn` —
    через временный файл и `os.replace`.
D9. **Формат журнала (до этапа 6):** поле `run_id` (передаёт вызывающий, один на прогон хода; повтор того же хода — новый
    `run_id`) и `ts` (передаётся параметром — без `time.time()` в llm; если нужно, вызывающий передаёт строку); `mark_turn(run_id, status)`
    помечает записи этого прогона; Replay группирует по `run_id` в порядке записей. В ledger — поле `call_id`.
D10. Чистка `blobs/`, на которые не ссылается ни один оставшийся сегмент, при удалении сегментов по `max_mb`.
D11. (T) сквозной сторож ключей: фейковый клиент Anthropic и Gemini бросает ошибку с ключом в тексте → `call_with_retries` →
     `journal` → ключа нет ни в одном файле. Комментарий-напоминание для этапа 6 в errors.py: исходное исключение в `__cause__`,
     трейсбек в репорт не выводить.
D12. (T) 2–3 теста Gemini на настоящих `google.genai.types`: `build_config` для всех `tool_set`; `parse_response` → JSON →
     `build_contents` с `thought_signature` (bytes). Убрать устаревший комментарий «SDK не установлен».
D13. `retry_after_of`: `float`, учитывать `retry-after-ms`; **408 → transient** в обоих адаптерах.
D14. `ChatResponse.model` из ответа провайдера (Anthropic `response.model`, Gemini `model_version` или запрошенная); учёт стоимости
     и журнал — по фактической модели (если нет цены — по запрошенной + метка).
D15. Gemini `count_tokens`: + оценка system+tools (`len(json) // 4`); ограничение — в gemini-facts.
D16. Модель — из `req.model`; `self.model` только для `info()`; тест фабрики — равенство.
D17. Лимиты стоимости в микро-долларах, как цены: `session_limit_micro`, `day_limit_micro` (0 = нет); перевод в нано внутри `check_limit`.
