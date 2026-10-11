# Ревью Б0-П1 (свободная предыстория) — мама-кабан, 2026-10-08

Проверено: незакоммиченный diff (rules/builder, protocol/requests|schema|apply|context, handlers/hero, master/session,
master/hero, prompts/background_rules.md, game/hero_create, vulture_allowlist, ARCHITECTURE) против `docs/B0-PLAN.md`
(A4, A5, шаг П1, решения проектировщика). `pytest tests/unit tests/scenarios/test_stage6b_background.py` — зелёный.

## Что сделано хорошо
- Все пункты A4/A5 на месте, по образцу summarizer: свой запрос/модели/адаптер, режим в `MODE_TOOLS`, группа кэша `hero`,
  `HERO_HANDLERS` до общих, `CreationContext` ровно по плану, `TurnContext.turn_seq` — свойство.
- `master/session.py`: регресса нет. `bundle` больше нигде в `session.py` не читается безусловно (единственное чтение —
  под `mode == "combat_narrate"`); `SINGLE_SHOT_MODES` для summarizer эквивалентен прежнему `role == "summarizer"`
  (summarizer работает только в `summarize_*`); `turn_seq=ctx.turn_seq` — для `TurnContext` то же значение.
- `background_skill_conflict` вынесен, `build_character` использует его и общий текст `SKILL_CONFLICT_MESSAGE`.

## Оценка отклонений кабана
- `background_check -> (codes, messages)` + обёртка `background_problems` — **принять**: хендлеру нужен первый код
  (`Invalid(code=codes[0])` по плану), иначе пришлось бы дублировать логику. Минимально и понятно.
- `background_tool_unknown` только при непустом `tool` — **принять**: пустой tool уже даёт `background_tool`, двойной
  текст модели ни к чему.
- `description_too_long` в хендлере — **нужна правка**, см. замечание 1.
- подсказка `empty_note` для `hero_background` — **принять**: без неё narrator получил бы общую подсказку роли
  narrator, не называющую инструмент; одна строка по соседнему паттерну.
- `cache=True` у messages[0] — **принять**: так же у `SummarizerPromptBuilder` и `PromptBuilder` (повторы после
  `Invalid` дописывают сообщения, префикс переиспользуется). Выжившие мутанты на этом флаге — эквиваленты дизайна.
- `background_problems` в `vulture_allowlist.py` — по решению проектировщика, ок (снять в Б1 вместе с
  `propose_background`/`with_background`).

## Замечания

1. **Блокер.** Предел описания 300 символов проверяется только в `protocol/handlers/hero.py:background_spec`, а не в
   `rules/builder.py:background_check`. План (Б-2, тест «г») требует, чтобы ручная правка через
   `BackgroundSpec.model_validate(dict)` + `background_problems` давала **те же** коды/тексты, что путь модели —
   сейчас длинное описание руками пройдёт. Предложение: перенести проверку (`DESCRIPTION_MAX`, код
   `description_too_long`, текст) в `background_check`, хендлер оставить без своей ветки; тест (г) дополнить случаем
   длинного описания.

2. **Желательно.** `master/hero.py:reference_block` — `item_ids` и `tool_ids` строятся только из `registry.all("item")`,
   а SRD-образцы в том же блоке содержат оружие (`spear`, `quarterstaff`, `dagger`), а `find_item` в проверке принимает
   weapon/armor. Модели сказано «используй только id из справочника» — она видит в примерах id, которых нет в
   `item_ids`, и не знает их цену для бюджета. План буквально писал `registry.all("item")`, но это недосмотр плана.
   Предложение: `item_ids` собирать по `("weapon", "armor", "item")` (как `find_item`), с тем же фильтром
   `source != "world"`; `tool_ids` — как есть. Если папа-кабан против — хотя бы убрать противоречие в
   `background_rules.md`.

3. **Желательно.** `gold_cp` не проверяется на отрицательность (`validate_background` суммирует как есть). Для SRD-пути
   неважно (данные из реестра), а модель/ручная правка может прислать `gold_cp=-3000` и обойти бюджет набора.
   Предложение: в `background_check` (не в `validate_background`, его коды план замораживает) добавить
   `gold_cp < 0` → тот же `background_budget_invalid`/свой текст; один тест.

4. **Мелочь.** `protocol/handlers/hero.py`: `description=request.description or ""` — поле обязательно и строковое,
   `or ""` лишнее.

5. **Мелочь.** `protocol/apply.py`, `protocol/schema.py`: импорты переформатированы в многострочные скобки (ruff/isort
   по длине — допустимо, если это вывод `make fmt`; если руками — вернуть однострочный стиль соседей не получится по
   длине, оставить).

6. **Мелочь.** Тесты `tests/unit/game/test_hero_create.py` и `tests/scenarios/test_stage6b_background.py` импортируют
   `fighter_choices` из модуля `test_builder` через `sys.path` — прецедент в репо есть (`tests/unit/ui/*`), работает.
   Но импорт тест-модуля как библиотеки хрупок (при переименовании/коллизии имени `test_builder`). На будущее —
   вынести `fighter_choices` в `tests/unit/rules/rules_kit.py`; сейчас не обязательно.

7. **Мелочь.** `schema.py:tool_defs` — `{"world": "world", "hero_background": "hero"}.get(mode, "summarize")` —
   словарь на каждый вызов; читается нормально, но `if/elif` в стиле соседей был бы проще для джуна. На усмотрение.

## Вердикт
Нужны правки: п. 1 (блокер). П. 2–3 — настоятельно до Б1 (иначе живой прогон Б1 упрётся в id оружия). Остальное —
по желанию.

## Решения
- Проектировщик (2026-10-08): `background_problems` — в vulture_allowlist до Б1 (вариант «а»).
- Оркестратор: п. 1–4 — править до коммита (kaban — src, kaban-doeba — тесты); п. 5–7 — оставить (п. 6 — кандидат в BACKLOG 16: вынести fighter_choices в kit-модуль).
- П. 4 снят: `or ""` нужен — NEUTRAL `{"description": ""}` превращает пустую строку в None при разборе, без `or ""` пустое описание не проходит BackgroundSpec. Сделано: п. 1 (BACKGROUND_DESCRIPTION_MAX в background_check), п. 2 (weapon/armor/item в справочнике), п. 3 (код background_gold_negative).
- Smells: партия дала 204 → apply и empty_note переведены на таблицы (202). Находки propose_background (13 парам.) и CreationContext.__init__ (9) остались; лимит без запаса.
- Мутации: поведенческие на новых строках убиты; эквиваленты/шум — в отчёте doeba. Для BACKLOG 16: выжившие на старых строках при суженном TESTS — ветки world в apply, world_verdict в required_tool, deepcopy в tool_defs; вынос fighter_choices в kit-модуль.
