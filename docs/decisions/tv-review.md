# Ревью #18 «ТВ Текст и выбор» (мама-кабан, 2026-10-15)

Проверено: `git diff` по src/, tests/, docs/ARCHITECTURE.md, BACKLOG.md; новые test_master_choices_ask.py,
test_narrator_choices_rules.py, test_game_choices_ask.py, tests/scenarios/test_tv_replay.py. Сверено с docs/TV-PLAN.md
(Q1–Q3 = а, а, а). cov/smells/mutmut не запускались (их гоняет оркестратор).

## Хорошо
- T3: в `run`, ветка `elif calls:`, `result.texts += texts` теперь без условия; в ветке `max_tokens` текст по-прежнему
  отбрасывается. `choices_unseen(done, told, accepted)`, ворота `has_invalid` убраны, как в п.1.2 плана.
- T5: `MasterResult.accepted`, `ends_with_choice`, `choices_missing`, `ask_choices`, `CHOICES_ASK` сделаны по п.1.3.
  `ask_choices` исполняет только первый `offer_choices`, тексты не добавляет, `rounds` и `invalid_count` не трогает,
  `TurnFailed` и `refusal` глотает. Вызов стоит только в ветке `note is None`, ранний выход и SINGLE_SHOT не задеты.
- Компенсация smells: из `run_call` убран `allowed` (п.1.6).
- `narrator_rules.md`: «2–3» и фраза про список текстом (Q1а).
- Q2а: текст после приписки не трогается. Q3а: авто-репорт на `choices_retry` есть (test_game_choices_ask).
- Сомнительного места с `offer_choices` из 4 пунктов в ответе на приписку нет: `TurnResult.requests` копит только
  accepted/clamped (`turn.py` `recording`), поэтому `offer_is_stale` не оживит варианты прошлого хода.
- Замена `test_narration_with_rejected_round_does_not_excuse_empty_final` смысл не теряет. Старый тест проверял
  «текст invalid-раунда не считается рассказом, пустой финал повторяется». По T3 это утверждение перевёрнуто
  (`..._invalid_round_excuses_empty_final`: 2 вызова, narration = текст раунда). Ветка «invalid без текста, потом пустой
  финал → повтор, invalid_count 2, narration "Рассказ."» сохранена во втором тесте. Покрыты обе стороны.
- Тесты по §4 плана закрыты: ends_with_choice (включая 4 хвоста дракона и границу 120/121), запрос приписки, сбои,
  случаи «приписки нет», журнал, game-уровень, реплей. Реализацию под тесты не подгоняли.

## Замечания (необязательные, мержу не мешают)
1. `ends_with_choice`: маркер «—» совпадает с репликами диалога. Если последний абзац — две реплики «— …», функция
   вернёт True, даже если они кончаются точкой. В плане «—» назван явно, а корпус §0 проверял ложные срабатывания на
   ходах с `offer_choices`. Ходы без него, которые кончаются диалогом, там почти не встречаются. Цена ошибки — один вызов
   (Risk §7). Предложение: на ЖП1 отдельно смотреть репорты `choices_retry` с хвостом-диалогом. Если такие будут —
   в BACKLOG: для «—» требовать отсутствия конечной пунктуации, как для голых строк.
2. `ends_with_choice` разбирает текст двумя проходами: `lines`, потом `reversed(narration.split("\n"))`. Можно один:
   набрать `block` и взять `block[0]` как последнюю строку для проверок «?» и «|». Простота, не баг.
3. `ask_choices`: если ответ на приписку пришёл с `stop_reason == "max_tokens"`, его `offer_choices` всё равно
   исполняется. В основном цикле вызовы из `max_tokens` считаются невалидными. Обрезанный JSON отсеет `parse_request`,
   так что вред маловероятен; есть тест `test_ask_stop_reason_is_from_ask_answer`, значит поведение закреплено
   сознательно. Оставить, но упомянуть одной фразой в ARCHITECTURE (абзац `CHOICES_ASK`) или в комментарии.
4. `run_round` по-прежнему считает `allowed` (нужен только для `summarize_chapter`), и `run_call` считает его ещё раз
   на каждый вызов. Это цена компенсации smells по плану, приемлемо.
5. Офлайн-реплей t436 (§3 п.6) прошёл не через `--replay-report`, а скриптом с отключённым fingerprint: 3 вызова,
   без `short_retry`, сцена сохранена. Отклонение оправдано, потому что запрос вызова 1 менялся в B59/Т60. Предложение:
   записать в HANDOFF способ проверки и где лежит скрипт/вывод (вне проекта), чтобы аудит мог повторить.

## Вердикт
Можно мержить. Обязательных правок нет; п.1 — наблюдение на ЖП1, п.5 — одна строка в HANDOFF.

## Мутанты

Выжившие мутанты mutmut по `src/ai_dm/master/session.py` (41 шт.). Тесты: `tests/unit/master/test_master_session_loop.py` (SL), `test_master_empty_note.py` (EN), `test_master_choices_ask.py` (CA).

| Мутант (run_call / run_round / ask_choices / run) | Исход |
|---|---|
| run_call 1, 2 (дефолт mode) | убит: SL `test_run_call_default_mode_is_explore` |
| run_call 15 (разделитель в «Доступны») | убит: SL `test_run_call_not_in_mode_lists_allowed_with_comma` |
| run_call 17, 18 (ключ "type" в input) | убит: SL `test_run_call_type_mismatch_is_invalid_with_both_names` (при мутации тип перезаписывался бы и расхождение не ловилось); SL `test_run_call_missing_type_is_filled_from_name` |
| run_call 33, 34, 35 (get('type') в тексте) | убит: SL `test_run_call_type_mismatch_is_invalid_with_both_names` (в message есть 'skill_check') |
| run_call 45, 46, 47 (код/текст invalid_request) | убит: SL `test_run_call_bad_fields_is_invalid_request_with_validation_text` |
| run_call 56 (report_tag Invalid -> result) | убит: SL `test_run_call_report_tag_of_invalid_from_executor_goes_to_result` |
| run_round 6 (has_invalid = None) | убит: SL `test_run_round_without_invalid_returns_false_flag` (`is False`); по сути почти эквивалентен: везде используется как truthy |
| run_round 53 (текст ноты «Нужны оба вызова») | текстовый: подсказка модели; подстрока при этом проверяется в `test_chapter_incomplete_round_tells_model_to_send_both`, поведение не меняет |
| run_round 58, 59 (has_invalid = True в неполной свёртке) | убит: EN `test_chapter_incomplete_round_counts_as_invalid` |
| ask_choices 29, 33 (plan не передаётся в call) | убит: CA `test_ask_call_in_journal_has_context_meta_like_main_call` |
| ask_choices 36, 37 (сравнение с "refusal") | убит: CA `test_ask_refusal_answer_with_offer_choices_is_not_executed` |
| run 1 (дефолт world_text "XXXX") | убит: SL `test_run_without_world_text_has_empty_world_text_in_system` |
| run 45 (required_done = None) | эквивалентный: значение используется только как булево (`not required_done`, `done`, `empty_ok`) |
| run 152 (required_done = None в свёртке) | эквивалентный: то же, только булево |
| run 111, 114, 115, 116 (текст TurnFailed «корректный вызов», max_tokens) | текстовый: пояснение исключения, поведение (reason="invalid") то же |
| run 212, 215, 216, 217 (тот же текст, ветка has_invalid) | текстовый: пояснение исключения |
| run 266, 269, 270, 271 (текст «корректный ответ») | текстовый: пояснение исключения |
| run 128, 133, 134, 135 (текст TurnFailed rounds) | текстовый: пояснение исключения, reason="rounds" проверен |
| run 161 (`texts +=` -> `=` в одноразовом выходе) | убит: EN `test_single_shot_texts_of_earlier_rounds_are_kept` |
| run 253 (plan=None в ask_choices) | убит: CA `test_ask_call_in_journal_has_context_meta_like_main_call` |

Примечание: mutmut заново не гонялся, убийство подтверждено разбором диффов и прогоном своих файлов (174 passed).
