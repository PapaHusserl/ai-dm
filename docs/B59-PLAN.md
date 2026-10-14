# План мини-партии BACKLOG 59 — пустая сцена на запасной модели рассказчика

Автор: papa-kaban, 2026-10-14. Статус: ждёт аппрува проектировщика (вопросы в конце).

## 0. Разбор хода 396 (офлайн)
- Воспроизведено `--replay-report` без ключей (синтетический репорт из `issues/20261014T141830-t396-refusal_fallback/after` + вызовы 41–44 `calls-011.jsonl`): отпечатки совпали, рассказ — «Выбор за тобой.».
- Механизм: вызов 42 — только `offer_choices`, текста нет → `MasterSession.run` (master/session.py:304–319, `told=False`) делает ещё вызов; вызов 43 — «Выбор за тобой.», непусто → `empty_note` пропускает. Защиты «текст слишком короткий» нет.
- Пустое мышление — скрытое (`display: "omitted"`-подобное), а не потеря: ~480 ток. ушли в блок `thinking:""` + подпись (в подписи метка `narration`). Гипотеза: сцену модель написала в мышлении. Адаптер `thinking` не передаёт (anthropic_adapter.py:117–129). Справка SDK говорит, что по умолчанию `summarized`, — расходится с журналом; подтвердит только живой ход.
- Запасная модель ни при чём: `[llm] refusal_fallback = false`. Цепочка: summarizer на gemini — 503 ×8 (сетевой сбой в запасную не уходит) → граница упала → игрок сам сменил рассказчика на sonnet-5-5 → summarizer стал haiku-4-5 → трижды `invalid` (длинная выжимка) → запасной summarizer на модели рассказчика; тег `refusal_fallback` — это его тег (`boundary.py:78/161`), не флаг `[llm]`.

## Затронутые файлы
`game/turn.py` (`play_turn`, `retry_result`, `explore_turn`, новые `check_told`, `TEXT_NOTE`, `RETRY_NOTES`); `config/app.py` (`MasterConfig.min_narration_chars`, `LlmConfig.thinking`, `thinking_display`); `config/app_defaults.toml`; `llm/anthropic_adapter.py` (`complete`, новый `thinking_of`); `tests/conftest.py`; docs: ARCHITECTURE.md:472, :625, llm-notes/claude-api-facts.md, BACKLOG 59, handoff, checklist-b59-live.md (не коммитить).

## Шаги kaban
1. `[master] min_narration_chars = 80` (0 = выкл.), `Field(ge=0)`.
2. `TEXT_NOTE = "Системная приписка: напиши сцену текстом ответа — игрок видит только текст, размышления ему не показываются."`; `RETRY_NOTES = {"refusal": SOFTEN_NOTE, "short": TEXT_NOTE}`.
3. `play_turn`: `note = RETRY_NOTES.get(failure.reason)`; None → `failed`, иначе `retry_result(result, failure.reason)`, `self.note = note`.
4. `retry_result(started, reason)`: тег `f"{reason}_retry"` (`refusal_retry` прежний, новый `short_retry`; тег запускает авто-репорт).
5. `check_told(master)`: `TurnFailed("short", …)` если `self.note is None` и `master.rounds > 0` и `len(master.narration) < порога`. Вызов в `explore_turn` только в ветке `state is None` (вне боя).
6. `[llm] thinking = { narrator = "adaptive" }` (ключи-роли Literal, значения `adaptive|disabled`), `thinking_display = "summarized"|"omitted"`. Не через `ChatRequest` — иначе ломается `request_fingerprint` старых журналов.
7. `AnthropicAdapter.thinking_of(req)` словарём → `kwargs["thinking"]` (и для beta). Gemini не трогаем.
8. Документы (см. выше); чек-лист: thinking в журнале непустой, нет 400 на `display`, нет коротких ответов с одними вариантами.
9. Офлайн-проверка на репорте из п.0: после шага 5 ожидается код 1 «лишний вызов 4» (защита запросила повтор).

## kaban-doeba
- conftest: autouse-фикстура, подменяет `APP_DEFAULTS_PATH` на копию с `min_narration_chars = 0` (как `durable_off`), иначе ~94 файла со сценариями `text_step("Рассказ.")` сломаются. Тесты защиты включают порог явно; отдельный тест — реальный toml = 80.
- Сценарии: повтор и успех (2 прохода, `TEXT_NOTE` только во втором); повтор тоже короткий → принят, `short_retry`; без инструментов — без повтора; граница 79/80; порог 0; бой (`combat_narrate`, `start_combat`) — без повтора; отказ→короткий — принят; короткий→отказ — `failed`, теги `short_retry`+`refusal`; состояние после повтора = как без короткой попытки, `self.note is None`; авто-репорт и `--replay-report` код 0; адаптер narrator adaptive/omitted/disabled, другие роли без ключа — без `thinking`, beta-путь; блок thinking с подписью уходит в следующий раунд неизменным; ошибки конфига.
- mutmut: `ai_dm.game.turn:TurnRunner.play_turn, retry_result, explore_turn, check_told` (тесты `test_game_short_retry`, `test_game_refusal_retry`); `ai_dm.llm.anthropic_adapter:AnthropicAdapter.complete, thinking_of` (`test_llm_anthropic_adapter`). `make cov` один раз в конце.

## Smells (200/200, нулевой баланс)
Новые функции простые, `thinking_of` словарём. Риск — `anthropic_adapter.py` может перейти порог файла; компенсация — вынести разбор `usage` в `usage_of`.

## Оценка
papa ~130 тыс.; kaban 60–80; doeba 150–200; mama ~25. Итого ≈ 0,37–0,44 млн.

## Риски
Старые репорты с коротким рассказом после инструментов дадут код 1 при реплее (прецедент AD1 Q4, Р1). API может отвергнуть `display`/`adaptive` → 400 → меню ошибки (поэтому только narrator). `summarized` увеличивает журнал.

## Вопросы проектировщику (рекомендации papa)
1. Порог `min_narration_chars = 80` (минимальные нормальные рассказы в сейвах 99+, в 396 — 15). Рек.: 80.
2. Повтор тоже короткий: (а) принять ход + `short_retry` + авто-репорт; (б) откат и меню ошибки. Рек.: (а).
3. Где проверять: (а) только вне боя; (б) и `combat_narrate`. Рек.: (а).
4. thinking рассказчика: (а) `adaptive` + `summarized`; (б) `disabled`; (в) не трогать. Рек.: (а).
5. Роли с thinking: только narrator (вкл. создание героя). Рек.: да.
6. Сетевой сбой summarizer (503) не уходит в запасную модель — в BACKLOG, не в этой партии. Рек.: да.
7. Переименовать тег `refusal_fallback` summarizer (`summarizer_backup`) — в BACKLOG. Рек.: да.
8. Поправить текст BACKLOG 59 по разбору п.0 (делает оркестратор). Рек.: да.

## Дополнение 2026-10-14: живой ход 399 и разбор причины (papa-kaban)
Ход 399 (sonnet-5-5): `short_retry` сработал, повтор тоже короткий («Вы спустились ко второму порогу.»); мышление (`summarized`) содержит готовую сцену. Параметр thinking принят API (400 нет).
Причина (схема старая — журналы 5 и 9 октября, без параметра thinking): раунд 1 — механика; раунд 2 — мышление со сценой + `offer_choices` без текста; раунд 3 — модель видит своё мышление (сцена «уже написана») и ответ движка «Варианты ответа предложены» → одна закрывающая строка (`effort=low`). Правила (narrator_rules.md: «Порядок работы» п.1–3, стр.18 «думай молча», стр.108) читаются как «offer_choices — конец хода». `TEXT_NOTE` повтора стоит в первом user-сообщении — далеко от точки решения. Gemini делает те же раунды, но в раунде 3 пишет полную сцену.
Варианты:
- В2 (рек., обязательно): `MasterSession.run`, ветка `elif calls:` — если роль narrator, `offer_choices` accepted, нет invalid и `told` ложно, добавить к ответам инструментов `Text` (константа `CHOICES_NOTE`): «Рассказа этого хода игрок ещё не видел — размышления ему не показываются. Напиши сцену полностью текстом ответа; варианты уже предложены, не повторяй их.» Механизм как у ветки max_tokens. Реплеи расходятся только у ходов с таким раундом.
- В1 (рек. в той же партии): правила и docstring `OfferChoices` — offer_choices вызывается в одном ответе со сценой, после текста; сцена — текстом ответа. Расходятся все старые реплеи (меняется system/tools_sha).
- В3 (решение проектировщика): `effort` рассказчика Claude low → medium — длина/качество прозы (Sonnet на low 550–1500 симв. против 1800–2800 у Gemini), причину не устраняет.
Тесты: приписка при offer_choices без текста (в т.ч. с механикой); нет приписки при тексте, invalid, ролях summarizer/world, max_tokens; check_told/short_retry целы; реплей t399 расходится на вызове 3. mutmut: `ai_dm.master.session:MasterSession.run`.
Решения проектировщика 2026-10-14: В1+В2 в этой партии; В3 — да (effort рассказчика Claude → medium); приписка для всех провайдеров; текст приписки — черновик выше.
