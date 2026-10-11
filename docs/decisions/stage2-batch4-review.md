# Ревью партии 4 этапа 2 (master): спецификация правок

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

## Блокирующие
B1. `max_tokens` + `tool_use`: вызовы не исполняются; в следующее user-сообщение — `ToolResult(call_id, content=<пояснение
    «ответ оборван по длине, повтори короче»>, is_error=True)` на каждый вызов, Text-пояснение — последним блоком;
    `invalid_count += 1`.
B2. `run_call`: `call.input.get("type") != call.name` → `Invalid(code="invalid_request", message=...)` до `parse_request`.

## Желательные (делаются сейчас)
D1. `MasterSession.run(..., *, world_text="")` → `build(..., world_text=world_text)`.
D2. **Контракт для партии 5 (записать в docstring и в STAGE2-PLAN A4):** game создаёт `PromptBuilder(app_cfg, model=<модель выбранного
    адаптера>, count_tokens=<адаптер.count_tokens>)` и передаёт в сессию. Оценка бюджета: `count_tokens` адаптера вызывается
    **один раз** на запрос (полный), дальше выкидывание ходов — по эвристике; эвристика для кириллицы `len // 3` (вместо `// 4`).
    Ошибка `count_tokens` → эвристика (не падать).
D3. `run_id` передаётся в `run(..., run_id=...)` (по умолчанию — из конструктора); счётчик `call_id` — по run_id
    (`{run_id}-{n}` уникален в пределах run_id даже при нескольких вызовах `run`). Правило: все вызовы мастера одного прогона хода
    (classify / npc_choice / narrate) используют один `run_id`.
D4. `MasterResult.texts` — только из принятых ответов; добавить `MasterResult.narration` = текст финального принятого ответа
    (то, что показывает игра).
D5. Пустой ответ при `required is not None and required_done` → успех (не тратит бюджет).
D6. Риски для живого smoke (партия 6, в STAGE2-PLAN): два user подряд у Gemini; ответ только из thinking (Opaque) у Anthropic;
    `cache_read > 0` на втором ходу explore.
D7. Кэш внутри цикла инструментов — третья точка `cache_control` на последнем сообщении истории раунда (лимит 4 точки).
D8. `narrator_rules.md`:
    - раздел о режимах: «в бою фразу игрока передай через `player_action`; при поражении героя обязателен `defeat_outcome`; ход NPC —
      `npc_action`; набор инструментов в запросе — всё, что доступно сейчас»;
    - формат входа: сообщение — JSON, `player_input` — ввод игрока, остальное — состояние; system[1] — данные мира;
    - «в инструментах используй только id из `monster_ids`/`item_ids`» (вместо «нельзя называть id»);
    - «лечение — только `rest`; иное лечение — `unsupported_action`»;
    - «смерть NPC через `npc_update` — только с `cause` goal/hazard и ссылкой на бросок этого хода».
D9. Мелочи: «Инструмент X: в этом режиме недоступно.»; убрать дубль `role_cfg`.

## Тесты (T)
B1 (`max_tokens` с tool_calls → у каждого ToolCall есть ToolResult is_error, executor не вызывался, invalid_count 1); B2 (рассогласование
name/type у нестрогого инструмента и при strict_tools=false — Invalid, ничего не исполнено); D1 (`world_text` в system[1], стабилен между
ходами); D2 (count_tokens зовётся один раз; ошибка count_tokens → эвристика); D3 (два `run()` на одной сессии — разные call_id; явный
run_id); D4 (texts/narration без отбракованных ответов); D5 (пустой ответ после accepted player_action — успех); два Invalid в одном ответе —
одна единица бюджета; D7 (cache-точка на последнем сообщении раунда, ≤ 4 точек); D8 (правила упоминают `player_action`, `defeat_outcome`,
`npc_action`, `rest`, `monster_ids`).
