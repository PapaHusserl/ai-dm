# Ревью партии P0 этапа 6а (мама-кабан)

Проверено: незакоммиченный diff (game/app.py, boundary.py, commands.py, turn.py, master/session.py,
protocol/decision.py, handlers/combat.py, ui/cli.py), новые src/ai_dm/reports/, тесты P0.
Прогон: tests/unit — 9858 passed; полный `pytest` — **2 failed** (tests/scenarios/test_stage4_memory.py).

## Хорошо
- Пункты плана P0 закрыты: TurnCapture, run_ids/before в TurnResult, метки границы из ctx.marks, last_capture,
  render/write_report, auto_reports, cmd_report, cli (auto_reports выкл. в mock/replay), тесты по всем меткам,
  сторож ключей, архитектурный тест.
- Отклонения обоснованы:
  - `before` как ссылка без deep-copy и при boundary_pending корректно: `finish_boundary` работает на
    `bundle.model_copy(deep=True)`, `close_boundary` в `boundary.run` мутирует уже `work` (новый self.bundle после
    commit), а не `before`; ход идёт на копии `work`. Значит план с deep-copy был перестраховкой.
  - `Invalid.report_tag` с `exclude=True` — метка не уходит модели; добавление в run_call — одна точка на все
    обработчики.
  - `failed(started, failure)` сохраняет run_ids/before — проще, чем протаскивать два параметра.
  - `secrets` в GameApp — нужно для redact строки об ошибке; cli передаёт `setup.secrets`.
- Writer атомарен: tmp-каталог → `os.replace`, при OSError tmp удаляется; коллизии — `-2`, `-3`.

## Замечания

- БЛОКЕР: полный прогон падает — `tests/scenarios/test_stage4_memory.py::test_estimate_within_budget_...` и
  `::test_json_length_over_2_5_within_budget_on_every_turn` (17526 > 17520, «подобрать WINDOW в memory_script.py»).
  Рост контекста на ~6 знаков, вероятно из-за новой строки HELP `report` («<что не так> записать репорт об ошибке»)
  или иного текста, попадающего в контекст мастера. Подобрать WINDOW в tests/scenarios/memory_script.py
  (как делалось в Т3/Т5) и прогнать весь `pytest`, не только tests/unit.

- `before` у откатанного хода — game/turn.py `failed()`/`capture_of`: при `committed=False` `before` — это текущий
  `self.bundle`, тот же объект, что живёт дальше. Авто-репорт пишется сразу — безопасно. Но ручной `/report` после
  отката, сделанный позже, увидит мутации на месте (`tone.apply` в app.py:358 и т.п.). На RNG/ход это сейчас не
  влияет (level_up после отката недоступен), так что не блокер; достаточно комментария в TurnCapture, что `before`
  у aborted/none — живой бандл, и «снимать» его надо до записи. В P1 (снимки) учесть.

- game/app.py `write_report_lines`: ловится только OSError. Любое другое исключение из `render` (например KeyError
  в `STATUS_NAMES`, отсутствующий `world.rng`) уронит ход уже после commit, причём `auto_report` вызывается в
  `after_turn` до установки pending. Сейчас статусы закрыты (committed/aborted/none), так что это рекомендация:
  оставить как есть по ТЗ (только OSError), но держать STATUS_NAMES синхронным с capture.

- game/turn.py `take_boundary`: run_ids границы добавляются и при `done.error`, а метки границы — только при
  успехе (цикл по report_tags после `return` при ошибке). Если world выдал limit-exceeded, а потом граница упала
  (summarizer), метка теряется. Предложение: перенести добавление `done.report_tags` выше проверки `done.error`
  (рядом с run_ids). Мелочь, но это ровно случай «баг на границе», для которого репорт и нужен.

- reports/writer.py `write_report`: `"+".join(capture.tags)` в имени каталога — при пустых tags и пустом text
  (теоретически невозможно по вызовам) имя кончится на `-t5-`. Не трогать, просто отметка.

- Утечка секретов: в report.md/meta.json пишутся только player_input, текст /report, метки, причина сбоя, модель,
  RNG — ключей там нет, сторож-тест есть. `failure_reason` — код (`refusal`, `round_limit`), не текст исключения;
  ок. Текст в «Репорт не записан» маскируется через redact. Утечек не нашла.

- Стиль: соответствует соседнему коду (простые функции, комментарии по-русски, без абстракций). `sorted(...)` в
  take_boundary — изменение порядка mark_journal ради детерминированных run_ids; приемлемо.

## Вердикт
Нужны правки: блокер — упавшие сценарные тесты бюджета контекста (WINDOW). Рекомендация — сохранять метки границы
и при её сбое. Остальное — можно мержить после этого.

## Итог оркестратора (2026-10-07)
- Блокер stage4_memory: падает и на чистом 39a9b80 (проверено), оценка детерминирована (не дата/TZ/HOME/хеш-сид);
  WINDOW мока 21900 → 21910, причина 6 ток. не найдена (вероятно окружение) — при расхождении на другой машине выяснять.
- Рекомендация 1 (метки границы до проверки done.error) — внесена (take_tags). Рекомендация 2 — комментарий в TurnCapture.
- Мутанты: на новых строках — только шум/эквиваленты; старые выжившие (retry, take_boundary, call_world, failed) — BACKLOG 16.
- make mutate: шаблон "$(m).*" не ловит методы xǁClassǁmethod — doeba гонял вручную (BACKLOG 16).
