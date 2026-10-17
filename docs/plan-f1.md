# План фикс-партии Ф1 (papa-kaban, 2026-10-13; на аппрув проектировщика)

Задача: BACKLOG 43 (пол NPC старых миров — из пака при загрузке) + BACKLOG 44 (зверь Повелителя зверей при получении
подкласса) + разгрузка smells (206/206, лимит не поднимать, запас ≥ 2 после Ф1 с учётом нового кода). По правилу R5
фикс без груминга. Сейв v9, миграций нет, новых полей нет. Код на 227200b (после Р1), рабочее дерево по src чистое.
Размер S ≈ 0,6–0,8 млн по шкале R5. Бой со зверем — не Ф1 (К7).

## Что показал код (сверка перед планом)

- **Загрузка мира и пак.** `load_slot` (`persistence/store.py:190`) пак не знает: миграции получают только
  `MigrationContext` (`persistence/migrations/__init__.py:30` — цены, `npc_trade`, кости хитов). Зато **после** каждой
  загрузки зовётся `merge_pack(bundle, registry, campaigns_dir)` (`game/app.py:47`): при старте (`ui/cli.py:948`) и в
  `GameApp.load` (`app.py:432`). Он грузит пак и зовёт `merge_new(bundle, pack)` (`campaign/merge.py:38`), которая
  добавляет новые сущности и **дополняет пустое поле у существующих NPC пака** — блок «теги существ пака» (`merge.py:67–71`:
  `old.origin == "pack" and not old.tags and npc.tags` → `old.tags = …`, `report.added.append(f"tags:{id}")`).
  Это ровно нужный аналог для BACKLOG 43. Строка игроку: «Из пака добавлено: …» (`app.py:62`).
- **Пол в данных.** `NPC.gender: Gender | None = None`, `pronouns: str = ""` (`state/world.py:87–88`); NPC пака —
  та же модель (`build.py:166`: `world.npcs[id] = npc.model_copy`). Пол у именованных NPC трёх паков проставлен в
  К0-фикс-б; `HeroPreset.choices.gender` у готовых героев тоже (`campaigns/*/heroes/*.yaml`). `HeroState` id пресета
  не хранит (`state/hero.py:176–206`), но имя героя на лету не может совпасть с именем героя пака
  (`build.py:150–153`, `name_taken`).
- **Спутник.** `HeroState.companions: list[Companion]` (`hero.py:135–139, 204`: name, kind, notes), заполняется только
  в `build_hero` из `preset.companion` (`build.py:98–99`). Читают: промпт (`master/prompt.py:316–317` —
  `data["companion"]` только если есть), `/sheet` (`sheet_text.py:276`), `companions_nearby` в бою — это NPC с
  `follows`, не зверь (`prompt.py:342`). Умение `beast_companion` (`srd/data/features/beast_companion.yaml`, без
  механики → попадает в `hero.features` промпта с описанием; там же текст «новый зверь после одной ночи обряда у
  костра») даёт подкласс `beast_master` на 3-м уровне (`subclasses/ranger/beast_master.yaml`).
  `hero_feature_ids(hero, registry)` (`rules/derived.py:285`) — готовая проверка «есть ли умение».
- **Меню уровня.** `pending="level_up"` → `menu_for` → `step_options` (`app.py:170–174`), шаги — `progression.next_choice`
  (стиль, экспертиза, подкласс, варианты умений, ASI, заклинания; `progression.py:166–183`), выбор — `choose_level_up`
  → `record_choice` → `commit_level_up` → `finish_level_up` (`app.py:282–343`). Меню — только выбор id из списка:
  `ui/session.py:136–142` цифру шлёт в `choose`, текст — в `handle`, а `handle` при `pending` отвечает «Сначала нужно
  сделать выбор в меню» (`app.py:203`). Ввод имени текстом в меню уровня не поддержан. Списка зверей в данных нет
  (`srd/data/monsters` — 3 монстра: гоблины и стражник).
- **Герой на лету/пошагово.** Всегда 1 уровень: `resolve_hero_preset` строит `HeroPreset(id="custom", choices, motive)`
  с `level=1` по умолчанию (`build.py:40–42`, `models.py:95`); аргумента уровня в cli/starter нет. Случай «на 3+» сегодня
  не существует; путь через рассказчика покрывает его автоматически, когда появится.
- **Протокол.** Запрос = модель в `requests.py` (`REQUEST_MODELS`, union `MasterRequest`, `NEUTRAL`), обработчик в
  `protocol/apply.py: HANDLERS`, имя в `MODE_TOOLS["explore"]` (`schema.py:18–25`; новые инструменты автоматически
  не-strict, `STRICT_IN_EXPLORE` фиксирован). Обработчик — `def x(ctx, request) -> Decision | Invalid`
  (`handlers/world.py`, образец `change_follows`/`change_identity`). `ctx.hero` — герой. Тест
  `test_visible_set_has_28_tools_from_plan` закрепляет `len == 32` (`tests/unit/protocol/test_schema.py:281–283`).
- **Smells.** `make smells` = **206/206** на HEAD. Состав: 88 «много параметров», 52 «высокая сложность», 32 «общая
  сложность файла», 27 «много return», 5 «вложенность», 2 «сложное булево». Считаются и `tests/**` (ui_kit, game_kit,
  combat_kit). Порог параметров — > 5. **Проверено пробой (временный файл, удалён): qlty считает голую `*`
  (разделитель keyword-only) параметром, `self` — нет.** Поэтому 7 функций с ровно 5 параметрами числятся smell'ами
  только из-за `*`: `inventory.add_item/remove_item`, `exhaustion.add_exhaustion`, `llm/factory.make_adapter`,
  `GeminiAdapter.__init__`, `master/context.plan`, `store.save_auto` → Q4. Кандидаты на честное упрощение (count = 6,
  одна правка = −1): `combat_fold.fold_text` (6 параметров), `scene.check_close` (6 return, `scene.py:26–40`),
  `master/session.py:295` (булево из 6 операндов), `cli.hero_flag_refusal` (6 return, `cli.py:744–760`),
  `boundary.summarize_scene/close_chapter/finish_boundary` (6 параметров каждая — протаскивание
  `world, summarizer, run_id`), в тестах — `ui_kit.py:285` (булево из 5 операндов) и `ui_kit.read` (6 return).

## Решение по BACKLOG 43: загрузка, не миграция (обоснование)

Делать в `merge_new` при загрузке, по образцу тегов. Почему не миграция v10: (1) миграции не видят пак — пришлось бы
расширять `MigrationContext` картой «id NPC → пол» и прокидывать её из трёх мест (cli, app.load, replay), как
`npc_trade`; (2) миграция одноразовая на слот, а у мира много слотов (`auto-N`, manual) — `merge_pack` отрабатывает
при каждой загрузке любого слота; (3) идемпотентно и «живое»: если автор пака позже проставит пол ещё кому-то, старые
миры подхватят без новой версии; (4) нет смены схемы — v9 остаётся, `tests/schema/save_v9.schema.json` не трогаем.
Условие заполнения — только `old.gender is None` (маркер «старый мир / не задан»): если рассказчик уже поставил пол через
`npc_update`, пак его не перебивает; после заполнения поле не None → повторно не трогается (сброс рассказчиком
`gender: unset` → при следующей загрузке снова возьмётся из пака — принимаем, пак для NPC пака источник истины).

## Решение по BACKLOG 44: путь через рассказчика + подсказка движка (рекомендация, развилка — Q2)

Зверя вводит рассказчик запросом `companion_update` (по сюжету, в ближайшей сцене), движок **сам** сообщает ему, что
зверь положен и его нет (`hero.companion_due: true` в состоянии), а игроку в меню уровня даёт строку-подсказку.
Один механизм закрывает все три пути из BACKLOG 44: подкласс в меню уровня, герой пака/на лету с умением без зверя,
новый зверь после гибели (та же `companion_due` после `dead`). Шаг меню уровня (вид + имя) требует ввода текста в
меню (не поддержан: `handle` при `pending` отказывает), списка видов (в данных нет) и всё равно не покрывает гибель и
героя, созданного с умением. Обряд 8 часов — текстом в правилах (BACKLOG 11 «(текст)»), без поля времени → Q6.

## Реализация (kaban; src и docs)

### 1. BACKLOG 43 — `src/ai_dm/campaign/merge.py`
1.1. Новая функция `fill_identity(bundle, pack, report) -> None` рядом с блоком тегов (стиль тот же): для `npc in
   pack.npcs`: `old = world.npcs.get(npc.id)`; если `old is None`, `old.origin != "pack"` или `old.gender is not None`
   — пропуск; если `npc.gender is None` — пропуск; иначе `old.gender = npc.gender`; если `not old.pronouns` —
   `old.pronouns = npc.pronouns`; `report.added.append(f"gender:{npc.id}")`.
1.2. Герой (Q1а): для `hero in bundle.heroes` с `hero.gender is None` — пресет `p` из `pack.heroes` с
   `p.choices.name == hero.name and p.choices.class_id == hero.sheet.class_id` и `p.choices.gender is not None` →
   `hero.gender`, `hero.pronouns` (если пусты) из `p.choices`; `report.added.append(f"gender:{hero.id}")`.
1.3. Вызов `fill_identity(bundle, pack, report)` из `merge_new` после блока тегов (до `campaign_version`). Строка игроку
   «Из пака добавлено: gender:edith, …» появится один раз (Q5а). Ничего в `load_slot`, миграциях, cli, app не меняется.
   Хроника не пишется (как у тегов).

### 2. BACKLOG 44 — протокол, промпт, меню уровня, правила
2.1. `src/ai_dm/protocol/requests.py` — `class CompanionUpdate(Request)` (докстрока = описание инструмента: «Зверь-спутник
   героя (Повелитель зверей): появление зверя, его гибель или уход»): `type: Literal["companion_update"]`;
   `action: Literal["join", "dead", "gone"]`; `name: str = ""` («имя зверя; обязательно при join»); `kind: str = ""`
   («вид словами: волк, капибара; обязательно при join»); `notes: str = ""` («откуда, повадки; пусто = нет»);
   `NEUTRAL = {"name": "", "kind": "", "notes": ""}`. Добавить в `REQUEST_MODELS` и в union `MasterRequest`
   (`requests.py:958`). В `WORLD_MODELS`/world-режим — не добавлять. Q3 — одна модель с `action`, не две.
2.2. `src/ai_dm/protocol/handlers/world.py` (или `hero.py` — на выбор kaban, рядом с `change_identity`):
   `companion_problem(hero, registry, request) -> Invalid | None` (≤ 5 return): нет `beast_companion` в
   `hero_feature_ids` → `Invalid("no_beast_feature", "у героя нет умения Зверь-спутник")`; `join` и
   `hero.companions` не пуст → `Invalid("companion_exists", "зверь уже есть: сначала dead или gone")`; `join` без
   `name` или `kind` → `Invalid("companion_fields", …)`; `dead`/`gone` при пустом списке → `Invalid("no_companion", …)`.
   `companion_update(ctx, request)`: `problem = companion_problem(...)` → вернуть; `join` →
   `hero.companions = [Companion(name, kind, notes)]`, лог «Зверь-спутник: {name} ({kind}) с героем»; `dead`/`gone` →
   имя из `companions[0]`, `hero.companions = []`, лог «Зверь-спутник {name} погиб» / «… ушёл». `Decision(status=
   "accepted", result={"companions": [c.model_dump() for c in hero.companions]}, log=[…])`. Хроника не пишется (kind —
   закрытый Literal, `memory.py:11`; менять схему не будем).
2.3. `src/ai_dm/protocol/apply.py: HANDLERS["companion_update"]`; `src/ai_dm/protocol/schema.py: MODE_TOOLS["explore"]`
   + `"companion_update"` (не-strict автоматически; в `combat_*`, `world`, hero-режимах — нет).
2.4. `src/ai_dm/master/prompt.py` (`hero_data`, ~316): `if "beast_companion" in feature_ids and not hero.companions:
   data["companion_due"] = True` (ключ только когда положен и нет; `companion` — как раньше, только если есть).
   Вынести проверку в `rules/derived.py: companion_due(hero, registry) -> bool` (одна функция для промпта и меню).
2.5. `src/ai_dm/game/app.py: finish_level_up` — если `companion_due(hero, registry)`: добавить строку «Повелитель зверей:
   зверь-спутник появится по сюжету — скажи рассказчику, кого и как зовут». Та же строка в `GameApp.load`/старте не нужна
   (рассказчик получает `companion_due` в каждом ходу).
2.6. `src/ai_dm/master/prompts/narrator_rules.md` (абзац про спутника, строка 96): «`companion_due: true` — герой
   Повелитель зверей без зверя: в ближайшей сцене вне боя обыграй появление зверя и в том же ходу зафиксируй
   `companion_update` с `action: join`, `name`, `kind`, `notes`; имя и вид игрока — бери его, иначе предложи и спроси;
   без запроса зверя у героя нет. Гибель или уход зверя — `companion_update` `dead`/`gone` в том же ходу; новый зверь —
   только после ночи обряда у костра в диком месте (не раньше следующего дня), снова `join`. В бою зверь не участвует».
2.7. Docs: `docs/BACKLOG.md` 43/44 — сделано (ссылка на план); `docs/glossary.md:168` — `HeroState.companions`,
   `companion_update`; `docs/HANDOFF.md` — строка Ф1; `docs/ROADMAP.md` перед коммитом; чек-лист
   `checklist-f1-live.md` (не коммитить): загрузка мира до К0-фикс-б (копия) → «Из пака добавлено: gender:…», в
   промпте пол NPC; следопыт 3 ур. с `beast_master` → строка в меню, рассказчик вводит зверя, `/sheet` показывает его;
   старый мир с Булочкой — без изменений.

### 3. Разгрузка smells (без смены поведения; цель ≤ 202 до нового кода, новый код — 0 smells)
Ярус 1 (обязательно, −4):
3.1. `game/combat_fold.py: fold_text(bundle, state, registry, folded) -> str` — 4 параметра: `hero = hero_of(bundle)`,
   `last_combat = bundle.session.last_combat`, диапазон `folded[0].turn_seq`–`folded[-1].turn_seq`; `fold_fight` передаёт
   `folded`. Текст байт-в-байт прежний (replay-детерминизм). Тесты `test_combat_fold.py:66, 380, 476` — подпись.
3.2. `game/scene.py: check_close` — после ранней проверки `closed_reason` таблица в порядке приоритета:
   `[("location_changed", hero_location != scene.location_id), ("time_jump", …), ("combat_ended", combat_ended),
   ("turn_limit", …)]` → `next((reason for reason, hit in checks if hit), None)`. 6 return → 2.
3.3. `master/session.py:293–300` — именованные булевы: `clean = not has_invalid and all_free and bool(accepted)`;
   `done = required is None or required_done`; условие `self.role == "narrator" and clean and done and told`. Если
   qlty всё ещё считает сложным — вынести в метод `narrator_done(self, …)` (≤ 5 параметров). Проверить `make smells`.
3.4. `ui/cli.py: hero_flag_refusal` — список `(условие, текст)` + цикл → 2 return.
Ярус 2 (kaban-doeba, тесты, −2): 3.5. `tests/unit/ui/ui_kit.py:285` — условие в helper `continues_item(prev_item,
   prev_indent, indent, body, line)`; 3.6. `ui_kit.read` — цикл по предикатам вместо трёх `for … return`.
Ярус 3 (резерв, только если запас < 2 после всего): 3.7. `game/boundary.py` — dataclass `Roles(world, summarizer,
   run_id)`: `finish_boundary(bundle, cfg, registry, roles)`, `summarize_scene(work, cfg, registry, roles, result)`,
   `close_chapter(…, roles, result)`; `run(...)` оставляет kwargs и строит `Roles` (−3; тесты `test_game_boundary*.py`,
   `world_sim/test_nudge.py` зовут `finish_boundary` напрямую — 3 места). 3.8. — Q4 (снятие `*`).
Контроль: новый код Ф1 — функции ≤ 5 параметров и ≤ 5 return (п. 2.2 разбит на `companion_problem` + обработчик);
`make smells` после п. 1–3 — ожидание 202 (ярус 1) → запас 4.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.campaign.merge:fill_identity ai_dm.campaign.merge:merge_new` — TESTS tests/unit/campaign/test_pack_merge.py
  tests/unit/game/test_game_merge_pack.py
- `ai_dm.protocol.handlers.world:companion_update ai_dm.protocol.handlers.world:companion_problem` (или hero) —
  TESTS tests/unit/protocol/test_companion.py
- `ai_dm.rules.derived:companion_due` — TESTS tests/unit/master/test_master_hero_data.py tests/unit/rules/test_companion_due.py
- `ai_dm.game.combat_fold:fold_text ai_dm.game.combat_fold:fold_fight` — TESTS tests/unit/game/test_combat_fold.py
- `ai_dm.game.scene:check_close` — TESTS tests/unit/game/test_game_scene.py
- `ai_dm.ui.cli:hero_flag_refusal` — TESTS tests/unit/ui/test_ui_cli_hero.py (или где он тестируется)

## Тесты (kaban-doeba, TDD; параллельно с kaban)

Правка существующих: `test_combat_fold.py` (подпись `fold_text`, 3 места); `test_schema.py:281–283` — 33 инструмента
(переименовать/пересчитать); тесты `NEUTRAL`/ALL_TYPES в `test_requests.py` — проверить, что новая модель проходит общие
проверки. Остальное ломаться не должно (`check_close`, `hero_flag_refusal`, session — поведение прежнее).

BACKLOG 43 — `tests/unit/campaign/test_pack_merge.py` (через `campaign_kit.default_files`, `write_pack`, `load`,
`bundle_from_world`; пол в yaml — как в `test_pack_gender.files_with_gender`):
- NPC мира `gender None`, пак `female` + `pronouns` → `gender == "female"`, `pronouns` взяты, `report.added` содержит
  `gender:aldric`; остальные поля NPC не тронуты (`model_dump` без этих двух полей равен прежнему).
- NPC мира `gender == "male"` (рассказчик поставил), пак `female` → не меняется, в `added` нет.
- NPC мира `gender None`, `pronouns == "она"`, пак `female`/«госпожа» → пол взят, pronouns остаются «она».
- Пак без пола → ничего, `added == []` (`test_same_pack_gives_empty_report` остаётся зелёным).
- NPC с `origin == "ai"` и тем же id → не тронут. NPC `status == "dead"` → пол заполняется (вреда нет).
- Идемпотентность: второй `merge_new` → `added == []`, бандл равен.
- Герой (Q1а): `bundle.heroes[0].gender None`, имя и класс совпадают с пресетом пака с полом → заполнен, `gender:hero`
  в `added`; имя совпадает, класс нет → нет; герой с полом → не тронут.
- `tests/unit/game/test_game_merge_pack.py`: строка «Из пака добавлено» содержит `gender:` при заполнении; без изменений
  — `[]`. `GameApp.load` (стиль `test_game_app.py`): сохранённый мир с `gender None` у NPC пака → после `load` пол есть.

BACKLOG 44 — `tests/unit/protocol/test_companion.py` (`protocol_kit.make_ctx`, `req`, `apply`; герой-следопыт 3 ур. с
`beast_master` — как `grey_ctx` в `test_master_hero_data.py`):
- `join` у Повелителя без зверя → accepted, `hero.companions == [Companion(name, kind, notes)]`, лог с именем и видом,
  `result["companions"]` — список из одного.
- `join` при существующем звере → `Invalid companion_exists`, список не тронут. `join` без `name` / без `kind` →
  `Invalid companion_fields`.
- Герой без умения (следопыт `hunter`, воин) → `Invalid no_beast_feature`, даже при `dead`.
- `dead` / `gone` при звере → список пуст, лог «погиб»/«ушёл»; при пустом → `Invalid no_companion`.
- После `dead` → `join` снова принимается (новый зверь).
- `companion_update` есть в `tool_set("explore")`, нет в `combat_classify`, `combat_narrate`, `world`;
  не strict; `parse_request` принимает запрос без `notes` (NEUTRAL).
- Журнал/replay: запрос попадает в `requests` записи хода (`TurnRecord.requests` содержит `"companion_update"`) — на
  риге `game_kit` с `ReactiveAdapter`/скриптом; `/sheet` после хода показывает «Зверь-спутник: …».
- `tests/unit/master/test_master_hero_data.py`: `grey_ctx(companion=False)` → `hero["companion_due"] is True` и
  ключа `companion` нет; `companion=True` → `companion` есть, `companion_due` нет; `subclass="hunter"` → ни того, ни
  другого. `tests/unit/rules/test_companion_due.py`: уровень 2 (умения ещё нет) → False; 3 + beast_master → True;
  со зверем → False.
- `tests/unit/game/test_game_level_choices.py`: следопыт 2→3, выбор `beast_master`, завершение → в `reply.lines` есть
  строка про зверя-спутника; выбор `hunter` → нет; `pending` как раньше.
- Правила: `tests/unit/master/test_gender_rules.py`-стиль — `narrator_rules.md` содержит `companion_due`,
  `companion_update`, «обряд»/«костр».
- Сохранение/загрузка: после `join` сейв v9 валиден по `tests/schema/save_v9.schema.json` (поле `companions` уже в
  схеме), после загрузки зверь на месте.

Smells — поведение прежнее, проверка существующими тестами: `test_game_scene.py` (check_close все причины и приоритет —
добавить тест «две причины сразу: location_changed важнее time_jump», если такого нет), cli `hero_flag_refusal` (4 отказа и
None), session (ранний выход рассказчика — `test_master_session_loop.py`), `test_combat_fold*` (текст свёртки
байт-в-байт как раньше: golden-строка в `test_fold_fight_record_text_is_fold_text_with_range`). Ярус 2 — правки
`ui_kit.py` + прогон `tests/unit/ui`.

Общее в конце: `uv run pytest -q`, `make cov` (≥ 94 %), `make smells` (ожидание ≤ 202, обязательное ≤ 204), `make dead`,
`uv run ruff check src tests`; mutmut по списку выше.

## Критерии приёмки
1. Мир до К0-фикс-б (NPC `gender: null`): после загрузки у NPC пака с полом в паке — пол и местоимения из пака, у
   остальных — как было; повторная загрузка ничего не меняет; пол, поставленный рассказчиком, пак не перебивает.
   Сейв v9, схема без правок, миграций нет.
2. Следопыт, взявший `beast_master` в меню уровня, видит подсказку; рассказчик получает `companion_due: true` и
   может ввести зверя `companion_update join` — зверь появляется в `companions`, `/sheet` и в промпте (`companion`);
   `dead`/`gone` убирают зверя, после них снова `companion_due`. Герой без умения запрос получить не может (Invalid).
3. Инструмент только в explore; strict-набор не изменился; старые журналы и репорты воспроизводятся.
4. `make smells` ≤ 204 с учётом нового кода (ожидание 202), лимит 206 не тронут; поведение упрощённых функций прежнее
   (тесты зелёные без смены ожиданий, кроме подписи `fold_text` и счётчика инструментов).
5. Тесты зелёные, cov ≥ 94 %, `make dead` зелёный.

## Оценка
S ≈ 0,6–0,8 млн: kaban ~90–120 тыс. (~15 мин: merge ~25 строк, запрос+обработчик ~60, промпт/меню/правила ~20,
smells ~40 строк правок); kaban-doeba ~200–260 тыс. (~1–1,5 ч с mutmut: ~40 тестов); mama-kaban ~35 тыс.

## Риски / на что обратить внимание
- **`fold_text` — детерминизм.** Текст свёртки входит в replay-сравнение; менять только подпись, не формат строки.
- **Гонка «пак перебивает рассказчика».** Заполняем только при `gender is None`; сброс `unset` рассказчиком у NPC пака при
  следующей загрузке вернётся к полу пака — осознанно (пак — источник для своих NPC). Если прогон покажет проблему —
  условие сузить на `origin == "pack" and not world.flags.get(...)` не стоит; лучше править пак.
- **Гендер героя по имени (Q1а)** — эвристика name+class; ложное срабатывание исключено `name_taken` на старте мира,
  но мир, импортированный из выжимки (`pack_import`), может иметь героя с тем же именем — класс тоже должен совпасть.
- **Рассказчик может «забыть» ввести зверя** (как было с полом). Подсказка `companion_due` в каждом ходу + строка
  игроку в меню уровня снижают риск; при живом прогоне — проверить на 1–2 сценах; если не вводит — усилить правило
  («в первом же ходу сцены»). Движок зверя сам не создаёт — это сознательно (имя и вид — сюжет).
- **Один зверь.** Список `companions` допускает несколько; обработчик держит ровно одного (`companion_exists`) — по
  редакции умения. Уникальность имени зверя против NPC не проверяем (риск совпадения мал; при желании — `name_taken`).
- **Счётчик инструментов explore — 30.** Strict-грамматика не меняется (новый — не-strict); размер промпта +1 схема
  (~200 токенов на ход). Gemini: enum без пустых строк — соблюдено (`action` без «none», NEUTRAL строки пустые — как у
  `npc_update.text`).
- **Smells — порог «сложного булева» неизвестен точно** (ui_kit — 5 операндов уже флаг): в 3.3 целиться в ≤ 3
  операнда на выражение или вынос в метод; проверять `make smells` после каждого шага яруса 1.
- **Mutmut на macOS** — segfault (BACKLOG 16): узкие TESTS, выживших перепроверять другим файлом.
- Хроника не пишется ни про пол, ни про зверя (kind — закрытый Literal, менять схему не будем); память — через рассказ и
  summarizer.

## Открытые вопросы
- **Q1 Пол героя из пресета пака.** (а) **рекомендация** — заполнять в той же `fill_identity` по совпадению имени и
  класса с пресетом (`HeroPreset.choices.gender`): романтика без пола героя не работает, 10 строк; (б) только NPC, пол
  героя старых миров остаётся пустым (игроку поставить негде, рассказчик героя через `npc_update` не правит).
- **Q2 Путь появления зверя.** (а) **рекомендация** — запрос рассказчика `companion_update` + `companion_due` в
  состоянии + строка-подсказка в меню уровня (один механизм на подкласс, героя с умением без зверя и замену после гибели;
  имя и вид — из разговора игрока с рассказчиком); (б) шаг меню уровня «твой зверь» — нужен ввод текста в меню
  (новый `pending` и ветка в `handle`/TUI), список видов в данных (нет) и отдельно всё равно путь для гибели/замены;
  (в) оба — (а) плюс шаг меню как «быстрый» ввод — дороже, два источника истины.
- **Q3 Форма инструмента.** (а) **рекомендация** — одна модель `companion_update` с `action: join|dead|gone`
  (один обработчик, одна схема в промпте); (б) две: `companion_add` и `companion_remove` — яснее для модели, но +1
  инструмент и +1 обработчик.
- **Q4 Артефакт подсчёта `*` в qlty.** 7 функций с 5 параметрами считаются smell'ами из-за голой `*`. (а)
  **рекомендация** — не трогать: keyword-only — осознанный контракт, снятие `*` не упрощение, а подгонка под метрику;
  честных упрощений яруса 1–2 хватает (−6); (б) разрешить как резерв снять `*` у 1–2 функций, где keyword-only ничего не
  защищает (`context.plan`, `save_auto`), только если запас < 2 после яруса 3.
- **Q5 Показывать заполнение пола в строке «Из пака добавлено».** (а) **рекомендация** — да, `gender:<id>`, как
  `tags:<id>` (одноразово, видно, что мир подхватил пак); (б) молча (в `report.added` не писать).
- **Q6 Обряд 8 часов перед новым зверем.** (а) **рекомендация** — только текст в правилах (BACKLOG 11 так и
  задумывал; полей времени нет, v9); (б) проверка движком «не раньше N часов после `dead`» — нужна метка времени гибели
  → новое поле → v10, не Ф1.

## Решения проектировщика (2026-10-13)
Все по рекомендациям: Q1а (пол героя старых миров из пресета пака, в той же функции), Q2а (зверь — рассказчик
`companion_update` + `companion_due` в hero_data + строка в меню уровня), Q3а (одна модель с `action`), Q4а (артефакт
`*` у qlty не использовать), Q5а (`gender:<id>` в «Из пака добавлено»), Q6а (обряд 8 ч — только текст правил).

## Правки по ревью: Ревью фикс-партии Ф1 (mama-kaban, 2026-10-13) (бывш. docs/decisions/f1-review.md)

Проверено: незакоммиченный дифф src/ и tests/ против docs/plan-f1.md (вкл. «Решения проектировщика»: Q1а–Q6а).
smells 200/206 (план: ≤ 202, обязательно ≤ 204) — выполнено с запасом 6.

### Что сделано хорошо
- BACKLOG 43: заполнение только при `gender is None` и `origin == "pack"`, pronouns только если пусты; NPC, добавленный
  целиком, не дублирует `gender:` (у него пол уже не None). Идемпотентность и случаи из плана покрыты тестами.
- Q1а: пол героя по паре (имя, класс), герой с полом не трогается.
- BACKLOG 44: `companion_update` только в explore, не-strict, одна модель с `action` (Q3а); `companion_problem` ≤ 5 return;
  `companion_due` — одна функция для промпта и меню уровня (п. 2.4–2.5). `request.notes or ""` оправдано: NEUTRAL-поля
  приходят как None (тест `test_request_without_optional_fields_parses`).
- Smells-рефакторинг (`check_close`, `hero_flag_refusal`, булево в session, `fold_text`) поведение не меняет: порядок
  приоритета сохранён, все условия без побочных эффектов, ранний вычисление безопасно (`hero_describe` уже не None).

### Замечания

1. [низкая] Отклонение: четыре функции вместо одной `fill_identity` — `campaign/merge.py`. Принимаю: одна функция с
   условием из 4 операндов + цикл по героям дала бы smell «сложное булево»/«сложность», а `fill_identity` осталась точкой
   входа, как в плане. Мелочь: в `fill_npc_gender` условие из 4 `or` — то самое, что qlty считает сложным с 5; сейчас
   проходит, не наращивать. Переделывать не нужно. Список mutmut в плане (`merge:fill_identity`) стоит дополнить
   `fill_npc_gender`, `fill_hero_gender`, `preset_choices` — проверить, что kaban-doeba гонял их, а не только обёртку.
2. [средняя] Текст правила — `narrator_rules.md`: «имя и вид игрока бери его» — потеряно тире из плана, фраза
   читается как опечатка. Предлагается: «если игрок назвал имя и вид — бери их, иначе предложи и спроси».
3. [низкая] Там же: «В бою зверь не участвует.» в конце дублирует предыдущее предложение абзаца («в бою спутник не
   участвует, пока движок…»). Убрать финальную фразу — минус ~8 токенов кэшируемой части, смысл не теряется.
4. [низкая] Вне плана: `combat_fold.enemy_names`/`defeated_text` переписаны (видимо, ради smells/длины строки). Поведение
   то же, текст свёртки байт-в-байт (golden-тест зелёный), но в отчёте kaban стоит явно назвать эти две правки.
5. [инфо] WINDOW 23500→24000 в `tests/scenarios/memory_script.py` — обоснованно: прирост пика 18565→18880 (+315)
   соответствует +1 схема инструмента (~200) + правило (~100) + `companion_due`; комментарий в истории окна оформлен
   как прежние. Маскировкой не считаю. Но это 4-й подъём подряд (22450→24000 за К0, К0-б, Ф1) — рекомендую завести в
   BACKLOG пункт «бюджет промпта рассказчика»: следить за суммарным ростом статической части, а не только двигать окно.
6. [инфо] Правило про зверя (~110 токенов) в кэшируемой части — приемлемо; разбивать на отдельный условный блок
   (только при `companion_due`) не нужно — это потеряло бы кэш и усложнило сборку промпта.
7. [инфо] «GameApp.load заполняет пол героя» — отдельный тест не нужен: путь `app.load → merge_pack → merge_new →
   fill_identity` уже закреплён тестом `test_load_slot_fills_gender_of_pack_npc` (NPC), а логика героя покрыта на уровне
   `merge_new` в `test_pack_merge.py`. Новый тест дублировал бы проводку.
8. [инфо] 9 выживших мутантов на тексте `message` в `companion_problem` — ок: коды (`code`) закреплены тестами, message —
   свободный текст для модели, фиксировать его — хрупкие тесты. По желанию один тест на `companion_exists` с проверкой
   «dead или gone» в message (это подсказка модели, что делать), остальное не нужно.

### Вопросы проектировщику
- В1. Завести ли в BACKLOG «бюджет статической части промпта рассказчика» (п. 5)? Рекомендация: да, без срочности —
  к следующему подъёму WINDOW измерить вклад правил/схем и решить, что сжимать.

### Вердикт
Нужны мелкие правки: п. 2 (обязательно, текст для модели), п. 3 (желательно). Остальное — можно мержить после них;
перезапуск полного прогона не требуется, кроме `test_gender_rules.py` и memory-сценария (размер правила чуть изменится).

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **2026-10-13:** сейв dusk_academy-d3de6c57 поправлен вручную (пол 6 NPC из пака, Мире — зверь «Булочка», капибара; бэкапы *.bak-20261012-2122, *.bak-20261013-091929; Брандоку пол не задаём). BACKLOG 41–44. Решения проектировщика: фикс-партия **Ф1** = BACKLOG 43 (пол NPC старых миров из пака) + 44 (зверь Повелителя зверей) + разгрузка smells (упрощать, лимит 206 не поднимать); по правилу R5 фикс без груминга — план papa-kaban docs/plan-f1.md ✅, Q1–Q6 по рекомендациям; ждём «окей, кабаним». Живой прогон Р1 перенесён на следующий раз (совместить с прогоном Ф1/Р2).
- **Ф1:** код kaban ✅ 2026-10-13 (merge.fill_identity — пол NPC/героя пака при загрузке; companion_update + companion_due; разгрузка smells ярус 1: fold_text, check_close, session.py, hero_flag_refusal). Тесты kaban-doeba (вкл. ярус 2 smells) и ревью — дальше.
- **Ф1 ✅ закоммичена 2026-10-13:** тесты 13919 passed (флак TUI в этот раз прошёл), cov 97 %, smells 200/206, mutmut — выжившие только на тексте message и дефолтах. Ревью docs/plan-f1.md; правка текста правила companion_due (тире, дубль) — оркестратором. WINDOW мока 23500→24000 (4-й подъём подряд) — вопрос проектировщику про BACKLOG «бюджет статической части промпта». Дальше — живой прогон Р1+Ф1 (checklist-r1-live.md, checklist-f1-live.md; мир dusk_academy — Булочка уже в сейве, проверять companion_due на другом beast_master), затем груминг Р2.
- **2026-10-13 решения:** BACKLOG 45 (бюджет статической части промпта) — без приоритета. Живой прогон Р1+Ф1 — после Р2, одним прогоном на три партии. Дальше — груминг Р2 (svinopas + kaban-svekrov).
