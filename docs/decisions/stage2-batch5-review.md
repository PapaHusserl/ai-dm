# Ревью партии 5 этапа 2 (game): спецификация правок

Источник: ревью мамы-кабана. Решения — оркестратор. K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

## Блокирующие
B1. **Смерть в бою и временное правило:** `TurnRunner.close_scene_if_needed` при `result.hero_dead` — не закрывать сцену и не
    делать автосейв; `GameApp.load`: если у загруженного героя `status == "dead"` — `pending = "hero_dead"`.
B2. **Битый `models.json`:** общая `check_model(provider, model) -> str | None` (цена, окно, фабрика, MissingKey/ValueError) —
    используется в `set_narrator` и при старте; `read_models` и доступ к ключам — в `try (ValueError, KeyError, OSError)`;
    ошибка → `startup_lines` «Сохранённая модель не подключена: …», остаётся переданный адаптер. Запись `models.json` —
    атомарно (tmp + `os.replace`).
B3. **run_id уникален между перезапусками:** `TurnRunner(..., run_tag=None)`; метка `f"{now:%Y%m%dT%H%M%S}-{tag}"`,
    `tag = run_tag or uuid4().hex[:6]`; тесты передают фиксированный `run_tag`.
B4. **Варианты боя в промпте:** `TurnContext(..., combat_options=None)` — game заполняет из `combat_flow.preview_options`
    (`[{id, label}]`); `PromptBuilder` кладёт `combat.options` в state-JSON при `combat_classify` (варианты на границе хода) и
    `combat_narrate` (варианты следующего хода героя после `advance_until_player`; бой кончился → `[]`); в system вариантов нет.
    `narrator_rules.md`: «в `player_action.steps` используй только id из `combat.options`».
B5. **История в сейве:** `MasterConfig.recent_turns_keep: int = 50`; `TurnRunner.commit` оставляет последние N записей.

## Желательные (делаются сейчас)
D1. `CombatRoundLimit` в ходе → `TurnFailed("round_limit", ...)` → обычное меню ошибки.
D2. **Нат-20 во время фазы NPC:** если герой пришёл в сознание в своём шаге (спасбросок от смерти), `advance_until_player`
    останавливается и ход переходит к игроку (герой действует в этот же ход, по SRD и batch5-review этапа 1 п.12).
D3. `protocol/handlers/combat.player_action`: при наличии `ctx.combat_options` первый шаг обязан быть из них, иначе
    `Invalid(code="unknown_step")` (модель переспросят); последующие шаги (могут появиться после первого) — как сейчас
    (пропуск с пометкой).
D4. `GameApp(..., use_stored_model=True)`; CLI (партия 6) выключает для `--mock`/`--replay`.
D5. `hero_of` — одна функция в `game/scene.py`, используется везде (без фолбэка на `heroes[0]`).
D6. `starter.new_world` вызывает `start_scene(bundle)` вместо ручной сборки `SceneState`.
D7. `TurnResult.scene_summary` / `chapter_title` (из `TurnContext`) — пробрасываются; комментарий в `on_scene_boundary` (этап 4).
D8. **Опыт за бой:** при завершении боя с живым героем (`victory` или `ended_by_master`) — за врагов `dead`/`down`;
    за `fled` и оставшихся на ногах при `ended_by_master` — нет. Комментарий в `finish_combat`.
D9. Комментарий в `MasterChoiceController`: модель выбирает первое действие раненого хода, остальное — `EngineTactics`.
D10. (T) сторож `test_lower_layers_do_not_import_game` — учитывать относительные импорты.
D11. `/save` при `pending == "hero_dead"` — запрещён с сообщением.

## Тесты (T)
B1 (смерть в бою → `load_last_save` → герой active, в `auto` — сейв до боя; загрузка слота с мёртвым героем → pending hero_dead);
B2 (битый JSON / без ключей / модель без цены → старт с переданным адаптером + строка в startup_lines; атомарная запись);
B3 (два раннера с одинаковым `now` на одном журнале → разные run_id; фиксированный run_tag → детерминизм);
B4 (`combat.options` в classify совпадает с `preview_turn()`, в narrate — следующий ход; system без вариантов — префикс стабилен);
B5 (51-й ход вытесняет первый, turn_seq растёт, окно промпта 8); D1 (CombatRoundLimit → меню ошибки); D2 (нат-20 в фазе NPC →
ход у игрока); D3 (первый шаг не из options → Invalid unknown_step); D4; D8 (опыт при ended_by_master за dead/down, не за fled);
D10; D11. Обновить существующие тесты под изменения.
