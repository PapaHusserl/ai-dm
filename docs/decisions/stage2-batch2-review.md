# Ревью партии 2 этапа 2 (протокол): спецификация правок

Источник: ревью мамы-кабана + официальные лимиты strict (docs/llm-notes/claude-api-facts.md). Решения — оркестратор.
Исполнители: K — `src/**`, `docs/**` кроме TZ; T — `tests/**`. Параллельно.

## S. Лимиты strict-схем (блокирующее для партии 3)
Сейчас: 21 strict-инструмент в видимом наборе и 45 union-параметров → 400 «Schema is too complex».
S1. **Без union вообще.** Необязательные поля в схеме для модели — обязательные НЕ-nullable с нейтральным значением:
    bool → `false`; списки → `[]`; enum → значение-«ничего» в enum (`stakes: "normal"`, `pace: "normal"`, и т.п.);
    строковые ссылки (`failed_roll_ref`, `evidence_ref`, `npc_id`, `travel_to`, `debt_to`, `lair_location_id`, …) → `""`
    означает «нет»; числа → `0` означает «нет», где это однозначно. `set_flag.value` — один тип: строка (`"true"`/`"false"`
    или текст) либо два отдельных поля `value_bool` / `value_text` — выбери простое, чтобы не было union.
    Pydantic-модели запросов при разборе нормализуют нейтральные значения в `None` (внутренний API протокола не меняется).
    Схема выводится так, чтобы `anyOf`/массивов типов не было нигде.
S2. **Наборы инструментов по режиму** (`protocol.schema.tool_set(mode)`), каждый ≤ 16 strict-инструментов:
    - `explore`: skill_check, saving_throw, start_combat, damage, give_item, take_item, gold, award_xp, advance_time, rest,
      set_flag, npc_create, location_create, npc_update, offer_choices, end_scene, end_chapter, unsupported_action
      — если больше 16, вынести редкие (end_chapter, location_create, set_flag) без strict (`strict: false`, Pydantic
      проверяет всё равно) и зафиксировать в отчёте, какие;
    - `combat_classify`: player_action, unsupported_action;
    - `combat_narrate`: offer_choices, unsupported_action, end_combat, defeat_outcome;
    - `npc_choice`: npc_action.
    `tool_defs(exposed)` остаётся; `apply` по-прежнему принимает любой видимый запрос (контроль режима — MasterSession, партия 4).
S3. **Тест-сторож**: для каждого режима — strict-инструментов ≤ 20, union-параметров = 0, необязательных = 0, нет
    неподдерживаемых ключевых слов (список из справки). План A2 («`["T","null"]`») — поправить в STAGE2-PLAN.md.

## Блокирующие (по ревью)
B1. `start_combat`: после среза до `max_enemies` убрать группы без участников; выпал лидер → лидер = первый оставшийся член
    группы; результат clamped + `limit-exceeded`, бой создан. Пустой `enemies` → Invalid `no_enemies`.
B2. `start_combat`: NPC мира со статусом ≠ `alive` → Invalid `npc_unavailable`.
B3. `npc_update`: сначала проверка условий смерти (причина, ссылка); не выполнены → rejected `invalid-death` **до любых
    мутаций** (отношение не меняется). Метки урезания и отказа не затирают друг друга: в `ctx.marks` попадают обе.
    Пустой запрос (нет ни `attitude_delta`, ни `status`, ни `location_id`) → Invalid `empty_update`.
B4. `defeat_outcome`: `lair_location_id` ∉ `world.locations` → Invalid `unknown_location`; `debt_to` ∉ `world.npcs` → Invalid
    `unknown_npc`; `rob_items` урезается до 1..2 → clamped + `limit-exceeded`.
B5. `defeat_outcome`: `Rejected` из `apply_defeat_outcome` (ошибки формы) → `Invalid(code="invalid_defeat", message=reason)`.
B6. `damage`: если `after_damage` вернул `"down"` **или** `"failure"` (герой уже лежал) → `resolve_out_of_combat`.
    Урон по мёртвому герою → Invalid `hero_dead` (без второго `hero_died`). `result` содержит `hero_status` и исход
    спасбросков; `resolve_out_of_combat` возвращает строки бросков (каждый спасбросок — строка в формате ТЗ 6) —
    сигнатура: возвращает `(outcome, logs)` или объект; обнови вызовы. `failed_save=(severity == "deadly")`.

## Желательные (делаются сейчас)
D1. `rest(short, hit_dice > доступных)` → clamped до доступного + `limit-exceeded` (как take_item).
D2. `roll_ref` «тратится»: один проваленный бросок — одно смертельное последствие (`damage(deadly)` или смерть NPC);
    повторное использование → clamped (урон) / rejected `invalid-death` (смерть). Множество использованных в `TurnContext`.
D3. Отношение у предела ±100: лог и списание из лимита сцены — по фактическому изменению.
D4. id боя: первое `n ≥ 1`, для которого нет флага `combat_ended:combat_{n}` и нет активного боя с таким id.
D5. Invalid от `validate_start` — все коды с русскими подсказками и id сущностей (словарь «код → подсказка»).
D6. `npc_action` — в `HANDLERS` (контроль режима остаётся в обработчике).
D7. Синхронизировать STAGE2-PLAN.md: лимиты в обработчиках (нет `limits.py`), union → нейтральные значения, наборы по режимам.
Вне партии (записано для этапа 3): уникальность при загрузке пака; пробуждение стабильного героя вне боя (SRD: 1 HP через
1d4 часа) — этап 2 партия 5 (game) или этап 3 — решит план партии 5.

## Тесты (T)
S3-сторож; обновить тесты под S1 (нейтральные значения в схемах; Pydantic нормализует в None) и S2 (наборы по режимам);
B1–B6, D1–D6 — по тесту на каждый пункт (7 врагов с лидером второй группы седьмым → clamped, бой создан; мёртвый NPC в бою;
комбинированный npc_update `attitude_delta=50, status=dead, cause=chance` → rejected, отношение прежнее; defeat_outcome со
ссылками и rob_items=50; damage: down→stable/revived/dead, уже лежащий, мгновенная смерть от массивного урона, урон по мёртвому;
повторное использование roll_ref; rest clamp; id боя с заранее существующим флагом; подсказки validate_start).
