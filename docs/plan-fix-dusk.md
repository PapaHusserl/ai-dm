# Фикс dusk — репорты игроков

BACKLOG 170 (+136), 171 (+140), 172 (+144), 173, 141, 142. ROADMAP R11, первый открытый шаг.

## Суть

Разбор репортов dusk_academy (t837–t1081) и новых репортов drunk_dragon (t882, t887, t906, t907): дубли и дикие
расстояния у `location_create`, повтор `rest long` после отказа, ход без кнопок, шум авто-репортов `duplicate-kind` и
`limit-exceeded`, план сцены в рассказе после победы, слёт `scene_mood` на границе сцены.

Груминг: отчёт свинопаса и аудит свекрови — scratchpad сессии 2026-10-24 (не в репо).

## Решения

Проектировщик, 2026-10-24 (окна груминга):

1. 142 — вариант (а): движок переносит `scene_mood` в новую сцену при тех же NPC и локации. Подтверждение решения
   2026-10-23 («музыка важна», транскрипт 5e6f923c, строка 242).
2. 141 — в шаге (детектор плана сцены + перезапрос). Подтверждение решения 2026-10-23 («да, всё по советам
   архитектора», транскрипт 5e6f923c, строка 290).
3. 170+136 дубли — (а): локацию с тем же именем нельзя создать нигде в мире, мастер получает отказ и берёт существующую.
4. 170 расстояния — (а): локация «внутри» паковой обязана иметь родителя; связи внутри родителя не длиннее 500 м,
   наружу без ограничения.
5. 171 — (в) оба: правило рассказчику «кончил вопросом — дай `offer_choices`» и дешёвый повторный запрос в коде;
   вместе со 140.
6. 172 — (б): убрать тег `duplicate-kind` (авто-репорт), правило рассказчику не трогать; касается всех тёплых видов.
7. 144 — ответ вне вариантов: «давай поднимем лимиты на сцену, репорты уберем». Авто-репорта при урезании отношения
   нет; лимит на сцену (`per_scene = 20`) поднять — величину и затрагивает ли это `step = 10` даёт папа развилкой.

Проектировщик, 2026-10-24 (развилки плана, «принять рекомендации Р1–Р5»):

8. Р1 (144) — (а): `per_scene = 30`, `step = 10`.
9. Р2 (173) — (а): движок сам ждёт до конца кулдауна (≤ 8 ч) и проводит отдых; тег `rest_repeat` снят.
10. Р3 (171) — (а): дешёвый повтор — только текст хода и `player_input`.
11. Р4 (170) — (а): `parent_id` обязателен всегда.
12. Р5 (142) — (б): метка переносится, если все NPC сцены на месте (новые не мешают).
13. Видимые умолчания плана приняты как есть: строки ленты «Герой ждал до …», «Новая локация: …»; убитый NPC —
    ушедший; «внутри родителя» — родитель, потомки, предки.

## План (папа-кабан, 2026-10-24)

Контур вне msa; режим «встроить». Три партии по файлам: П1 `handlers/world.py` + `rules/uniqueness.py` (170+136, 172,
144), П2 `game/scene.py` + `game/boundary.py` + `handlers/resources.py` (173, 142), П3 `master/session.py` +
`master/leaks.py` (171+140, 141). Порядок — как рекомендация R11 (видимое игроку первым); каждая партия — ревью, аудит,
коммит. Полей сейва нет (новые ключи только в `config/defaults.toml`).

### Проверено по коду (ответы на открытое груминга)

- **136 и решение 3.** В `saves/drunk_dragon-00000001/slots/auto/world/world.json` у `tavern_drunken_dragon` (пак,
  родитель `city`) и `drunken_dragon_inn` (ai, без родителя) имя одно и то же: «Таверна «Пьяный Дракон»». Точное имя по
  всему миру (решение 3) ловит. Там же второй такой дубль: «Болотная застава у Старого канала» (`black_marshes_gate`
  / `old_canal_bog_outpost`). В паках (`campaigns/*/locations.yaml`) дублей имён между родителями нет — правило паки
  не ломает. Существующие дубли в живых сейвах план не трогает (136: только с согласия и с бэкапом).
- **173, что звала модель между отказами.** t864 (и t676 drunk_dragon): `rest long` → отказ → `advance_time
  category=hour` (+ `scene_mood none`) → `rest long` → отказ снова (час меньше остатка кулдауна). Подсказка тогда ещё
  не содержала «until: long_rest» (старый текст, см. результат в репорте). t860 — не цикл: раунд один, второй вызов
  оборвался `refusal`, ход перезапущен целиком (run -28 → -29). t1002 — новая подсказка с «until: long_rest»: отказ
  один, модель не стала ждать и вызвала `offer_choices`; герой «лёг спать» в рассказе без отдыха. Итог: подсказка
  «advance_time until long_rest, затем rest long» (`resources.py:816`) и правило `narrator_rules.md:134` — верный путь,
  не источник повтора; источник был `hour`. Остаток проблемы — модель двухшаговку не исполняет → Р2.
- **142, где NPC сцены.** В `SceneState` (`state/scene.py`) списка NPC нет; `scene_npcs` считается на каждом запросе
  в `master/prompt.py:548`: живые NPC с `location_id == hero.location_id`. Поля сейва не добавляем: множество
  снимается в памяти на границе (см. П2).
- **171, размер контекста `CHOICES_ASK`.** `ask_choices` (`session.py:368`) копирует `req` целиком: system (правила +
  блок мира + память, ≈ 23 k статики с кэшем — `STATIC_MAX = 23380`) + JSON состояния (до `context_cap = 16000`) +
  история раундов + ответ модели + `CHOICES_ASK`. Третий вызов стоит как полный ход (минус кэш system). Правило
  «кончил вопросом — дай `offer_choices`» уже есть: `narrator_rules.md:128`, дословно с «вопрос без вызова — ошибка»;
  добавлять нечего, усиление текстом не рекомендую (токены статики).

**Правило:**
- 170: было `other.parent_id == location.parent_id and norm(other.name) == name` (`rules/uniqueness.py:42`) → станет
  `norm(other.name) == name` (имя уникально во всём мире); `location_create` (`world.py:154`): было «родитель
  необязателен, расстояние ≥ 0» → станет «`parent_id` обязателен (Р4); связь с локацией внутри того же родителя
  (родитель, его потомки, предки — см. умолчания) не длиннее `locations.inside_max_m = 500`; наружу без лимита».
- 172: было `decision.report_tag = "duplicate-kind"` (`world.py:250`) → станет без тега (статус `clamped`, лог и
  `signal_to_master` остаются).
- 144: было `decision.report_tag = "limit-exceeded"` (`world.py:209`) → станет без тега; `per_scene = 20` → Р1.
- 173: было `rest_redundant` → `rejected` при `now_s < next_s` → при Р2 = а станет: `next_s - now_s ≤
  limits.long_rest_wait_max` → часы двигаются до `next_s`, отдых проходит (`clamped`, без тега); иначе отказ как
  сейчас, без тега.
- 142: было `start_scene` → `scene_mood = ""` всегда → станет перенос `old.scene_mood`, если локация та же и NPC сцены
  на месте (Р5).
- 171+140: было `ends_with_choice` по «?», «|», списку → станет плюс строка-заголовок «…варианты…:»/«…выбор…:»;
  повторный запрос — короткий (Р3) вместо копии полного.
- 141: новое — текст рассказчика, похожий на план («Опиши:» + нумерованные задания / «инструмент … отклонён»),
  не принимается: подсказка и повтор, как невалидный ответ.

**Поведение:** меняется — у игрока: нет дублей локаций и часовых переходов внутри зданий (170), музыка romance не
обрывается на границе сцены (142), при Р2 = а сон восстанавливает HP (173), ход с вопросом без кнопок — быстрее и
дешевле (171), после победы нет сырого плана в рассказе (141); невидимое: меньше `issues/` (172, 144, 173).
**Вне ai-dm:** нет.

**Модули/файлы/функции** (все найдены grep, кроме помеченных «новая»):
- П1: `rules/uniqueness.py:check_location`; `protocol/handlers/world.py:location_create`, `change_attitude`,
  `change_memory`; `world.py:connection_problem` (новая — проверка родителя и расстояний); `rules/uniqueness.py:
  inside_of` (новая — предки/потомки по `parent_id`); `config/settings.py:LocationsConfig` (новая) + поле
  `locations` в `RulesConfig`, `AttitudeConfig` (без правок кода, число в `defaults.toml:87`); `config/defaults.toml`
  — `[locations] inside_max_m = 500`, `[attitude] per_scene`; `protocol/requests.py:LocationCreate` (описание `name`,
  `parent_id`); `master/prompts/narrator_rules.md` (строка про `location_create`), `import_rules.md:8`;
  `tests/unit/master/test_static_budget.py:STATIC_MAX` (поднять с причиной).
- П2: `game/scene.py:start_scene`, `scene_npc_ids` (новая); `game/boundary.py:finish_boundary`;
  `protocol/handlers/resources.py:rest_redundant`, `rest`, `wait_for_long_rest` (новая, при Р2 = а);
  `config/settings.py:LimitsConfig` + `defaults.toml` `[limits] long_rest_wait_max` (при Р2 = а);
  `narrator_rules.md:124` («с новой сценой метка слетает сама» → остаётся при тех же месте и NPC).
- П3: `master/leaks.py:cut_leaks`, `cut_choice_head` (новая), `looks_like_plan` (новая); `master/session.py:
  ends_with_choice`, `MasterSession.finish`, `choices_missing`, `ask_choices`, `run`, `MasterResult`
  (поле `choices_announced`).

### Партии

**П1 — локации и шум отношения (170+136, 172, 144).**
1. `uniqueness.check_location` — убрать условие по родителю; текст конфликта с id существующей: «имя 'X' уже у
   локации 'id'». `location_create` — сигнал мастеру при конфликте имени: «место то же — используй id …, иначе другое
   имя». Проверка: `location_create` с именем паковой локации при другом `parent_id` → `rejected`, в сигнале id.
2. `world.connection_problem(ctx, request)` — вызывается из `location_create` до создания: `parent_id` пуст (Р4 = а)
   → `rejected` «укажи parent_id: здание, двор, город или область из locations/known_locations»; `parent_id` есть →
   для каждой связи с локацией внутри того же родителя (`uniqueness.inside_of`) `distance_m > cfg.locations.
   inside_max_m` → `rejected` «внутри {родитель} связи не длиннее 500 м: {id} — {d} м; место дальше — выбери другого
   родителя». Связь наружу — без лимита. Проверка: `parent_id="academy"`, связь `candle_library` 3500 → отказ;
   связь `misty_haven` 3500 → принято; «Хутор» с `parent_id="iron_ridge"` и 4000 м до `north_gates_grey_boar` →
   принято.
3. `change_memory` (`world.py:250`) и `change_attitude` (`world.py:209`) — снять `report_tag`; `defaults.toml`
   `per_scene` → Р1. Проверка: повтор `romance` в сцене → `clamped`, `report_tag is None`, память не записана,
   отношение применено; отношение 100 и `attitude_delta +1` → `clamped` без тега.
4. Подсказка рассказчику — одна фраза в `narrator_rules.md` (рядом со строкой 46 о `locations`): «Новое место —
   `location_create`: имя сверь с `locations`/`known_locations` (занято → существующий id); `parent_id` обязателен;
   внутри родителя связи ≤ 500 м, наружу — реальные». `import_rules.md:8` → «имена локаций уникальны».
   `LocationCreate.name` → «уникально во всём мире», `parent_id` → «обязателен». `STATIC_MAX` 23380 → по замеру
   (+≈80 токенов), причина в комментарии теста.
   Выход П1: `uv run pytest tests/unit/rules tests/unit/protocol tests/unit/master/test_static_budget.py -q`.

**П2 — сон и музыка (173, 142).**
1. При Р2 = а: `resources.wait_for_long_rest(ctx, request)` — до `rests.long_rest` в `rest`: если `kind == "long"`,
   `next_s` впереди и `next_s - now_s ≤ long_rest_wait_max` → `world.clock.advance(next_s - now_s)`, строка лога
   «Герой ждал до HH:MM» (`clock_text`), результат `clamped` с `signal_to_master` «отдых начался в HH:MM: опиши по
   факту», `report_tag=None`. `rest_redundant` — отказ только при ожидании больше лимита, без тега. При Р2 = б/в —
   только тег. Проверка: кулдаун до 02:00, сейчас 22:00 → после `rest long` часы 02:00 + `long_rest_s`, HP полные;
   сейчас 13:00 (ждать 13 ч) → `rejected`.
2. `scene.scene_npc_ids(bundle)` — `{npc.id: alive, location_id == hero.location_id}` (тот же фильтр, что
   `prompt.py:548`). `boundary.finish_boundary` — первой строкой `present = scene_npc_ids(work)`,
   `start_scene(work, npcs_before=present)`. `start_scene(bundle, npcs_before=None)` — если `old.scene_mood`,
   `old.location_id == location_id` и Р5 выполнено → `scene.scene_mood = old.scene_mood`. Прочие вызовы
   `start_scene` (`starter.py:49`, `app.py:477`, `cli.py:870`) без параметра — без переноса. Проверка: `end_scene`
   при `scene_mood="romance"`, герой и NPC на месте → у новой сцены `romance`; `location_changed` → `""`; NPC сцены
   ушёл (`location_id` другой) → `""`.
   Выход П2: `uv run pytest tests/unit/protocol/test_rest_repeat.py tests/unit/protocol/test_apply_resources.py
   tests/unit/game -q`.

**П3 — кнопки и план (171+140, 141).**
1. `leaks.cut_choice_head(text)` → `(text, found)`: последняя непустая строка по regex
   `^[^\w]*(?:игрок\s+)?(?:получает\s+)?(?:варианты|выбор)[^:\n]{0,40}:\s*$` (без регистра) срезается.
   `MasterSession.finish` — после `cut_leaks`: `narration, result.choices_announced = cut_choice_head(narration)`,
   тег `leak_cleaned`. `choices_missing` — `ends_with_choice(...) or result.choices_announced`. Проверка: текст с
   хвостом «Игрок получает варианты действий:» → строка срезана, `ask_choices` вызван, тег `choices_retry`.
2. `ask_choices` — вместо копии `req`: `ChatRequest(role, model=req.model, system=[SystemBlock(короткая инструкция
   без кэша)], tools=[спека offer_choices], messages=[user: «Фраза игрока: …\n\nТекст хода:\n<narration>\n\n» +
   CHOICES_ASK], max_tokens=req.max_tokens)` (Р3 = а). Остальное (`choices_retry`, `run_round`, refusal) как есть.
   Проверка: в запросе повторного вызова нет JSON состояния и один инструмент; `offer_choices` из ответа исполнен.
3. `leaks.looks_like_plan(text)` — истина, если есть строка, начинающаяся с «Опиши» и заканчивающаяся «:», и дальше
   ≥ 2 строк `MARKED_LINE`, или в тексте «инструмент» рядом с «отклон»/«недоступ»/«Сделай `…`» (имя инструмента в
   бэктиках). `MasterSession.run` — в ветке текстового ответа нарратора: `elif self.role == "narrator" and
   looks_like_plan(...)`: `note = PLAN_NOTE` («Это план, а не рассказ … напиши сцену повествованием, без заданий себе
   и названий инструментов»), тег `plan_leak`; дальше общий путь `count_invalid` (лимит `invalid_retries = 2`).
   Проверка: ответ-план после `not_available_in_mode` → не коммитится, второй вызов с подсказкой; обычный рассказ с
   нумерованным списком без «Опиши:» → не срабатывает.
   Выход П3: `uv run pytest tests/unit/master tests/unit/game/test_game_choices_ask.py
   tests/unit/game/test_f2_choices_after_fight.py -q`.

Перед коммитом каждой партии: `make cov` (≥ 94 %), `make smells` (≤ 200; П1 добавляет функции в `world.py` — при
росте smells вынести `connection_problem` в `rules/locations.py`), `make dead`, mutmut по списку ниже.

### Тестовые сценарии (кабан-доеба, TDD)

Тесты, которые перевернутся (править ожидание, не удалять): `tests/unit/rules/test_uniqueness.py:121`
`test_same_name_in_other_parent_is_allowed`, `tests/unit/protocol/test_apply_world.py:182`
`test_location_create_same_name_other_parent_is_accepted`; тесты на тег `duplicate-kind`
(`tests/unit/protocol/test_npc_update_memory.py`) и `limit-exceeded` у отношения; при Р2 = а —
`tests/unit/protocol/test_rest_repeat.py` (отказ только при долгом ожидании) и `tests/unit/game/test_tm_auto_reports.py:99–112`
(репорт `rest_repeat` → заменить на другой тег, например `gold_repeat`); при Р3 = а —
`tests/unit/master/test_master_choices_ask.py:142–162` (состав повторного запроса); `test_static_budget.py`.

П1:
- `check_location`: имя занято в другом родителе → конфликт с id; тот же родитель → конфликт; другое имя → пусто;
  регистр и пробелы (`norm`) игнорируются.
- `location_create`: без `parent_id` → `rejected` (Р4 = а); `parent_id` неизвестный → `Invalid unknown_location`;
  связь внутри родителя 500 → принято, 501 → `rejected` с id и метрами; связь наружу 4000 → принято; связь с самим
  родителем 3000 → `rejected`; связь с потомком родителя (внук) 3000 → `rejected`.
- `inside_of(world, parent_id, other_id)`: сам родитель, ребёнок, внук, предок → True; соседняя ветка → False;
  цикл `parent_id` не зацикливает.
- `change_memory`: второй `romance` в сцене → `clamped`, тег None, `has_kind` не добавил событие; `deal` после
  платной близости — поведение прежнее (тег `paid_not_romance` остаётся).
- `change_attitude`: на 100 с `+1` → `clamped`, тег None, `signal_to_master` есть; `per_scene` новый: три шага по
  10 проходят, четвёртый → `clamped` (при Р1 = 30).
- `merge_new` (`campaign/merge.py`): пак добавляет локацию с именем, уже занятым ai-локацией → `Conflict` в отчёте,
  слияние не падает.
- Проверка руками: `uv run ai-dm` (мок), ввод с `location_create` без родителя → в ленте «Локация не создана…».

П2:
- `wait_for_long_rest`: ожидание ≤ лимита → часы на `next_s`, отдых прошёл, лог «ждал до», `clamped`, тег None;
  ожидание > лимита → `rejected` без тега; короткий отдых и 0 HP — как было; `lodging_unpaid` по-прежнему раньше
  ожидания (комната не оплачена → отказ без сдвига часов).
- `start_scene`: перенос при тех же месте и NPC; нет переноса при смене локации, при ушедшем NPC сцены, при
  `npcs_before=None`; пустая метка не переносится; `finish_boundary` снимает множество до `tick_days`/`call_world`
  (NPC, которого убил тик, не ломает сравнение — см. Р5).
- Проверка руками: `uv run ai-dm`, `scene_mood romance`, `end_scene` в той же комнате → строка статуса/музыка та же.

П3:
- `cut_choice_head`: «Игрок получает варианты действий:», «Варианты:», «Выбор за тобой:» → срез и True; «Он ждал
  ответа.» → без изменений и False; строка не последняя → без изменений.
- `ask_choices`: запрос без JSON состояния, один инструмент `offer_choices`, в тексте рассказ и `player_input`;
  `choices_retry` в тегах; refusal и текст без инструмента — ход принят как есть (как сейчас).
- `looks_like_plan`: образец из t492 («Опиши: 1… 5… Инструменты gold и advance_time были отклонены… Сделай
  end_combat») → True; рассказ с «- » списком в конце → False; «Опиши» внутри реплики NPC без списка → False.
- `run`: ответ-план → повтор с `PLAN_NOTE`, тег `plan_leak`, `invalid_count` +1; три плана подряд → `TurnFailed`.

mutmut: П1 `FUNCS="ai_dm.rules.uniqueness:check_location ai_dm.rules.uniqueness:inside_of
ai_dm.protocol.handlers.world:location_create ai_dm.protocol.handlers.world:connection_problem
ai_dm.protocol.handlers.world:change_attitude ai_dm.protocol.handlers.world:change_memory"
TESTS="tests/unit/rules tests/unit/protocol"`; П2 `FUNCS="ai_dm.game.scene:start_scene ai_dm.game.scene:scene_npc_ids
ai_dm.game.boundary:finish_boundary ai_dm.protocol.handlers.resources:rest_redundant
ai_dm.protocol.handlers.resources:rest ai_dm.protocol.handlers.resources:wait_for_long_rest"
TESTS="tests/unit/game tests/unit/protocol"`; П3 `FUNCS="ai_dm.master.leaks:cut_choice_head
ai_dm.master.leaks:looks_like_plan ai_dm.master.leaks:cut_leaks ai_dm.master.session:ends_with_choice
ai_dm.master.session:MasterSession.finish ai_dm.master.session:MasterSession.choices_missing
ai_dm.master.session:MasterSession.ask_choices ai_dm.master.session:MasterSession.run"
TESTS="tests/unit/master tests/unit/game"`. Старые выжившие `change_attitude` (158) и `change_memory` — по
правилу 4 экономии: только новые строки.

### Развилки и риски

- **Р1 (144) — величина `per_scene` и `step`.** Сейчас `step = 10`, `per_scene = 20` (`defaults.toml:85–87`):
  два полных шага на сцену, третий тёплый ход уже режется (t906: +15 → +5, затем +2 → 0). Варианты: (а) `per_scene
  = 30`, `step = 10`; (б) `per_scene = 40`, `step = 10`; (в) `per_scene = 30`, `step = 15`. Рекомендую (а): три
  полных шага покрывают романтическую сцену из t846–t1015 без клэмпа, а порог романа 90 (`services.romance_from`)
  не берётся за две сцены с нуля; `step` не трогать — он режет один вызов (+15 за реплику — много и при 40).
  Тот же `per_scene` читает `combat_flow.py:192` (отношение после боя) — поднимется и там, это приемлемо.
- **Р2 (173) — что делать с `rest long` в кулдауне.** (а) Движок сам ждёт до конца кулдауна и проводит отдых, если
  ждать ≤ `limits.long_rest_wait_max` (рекомендую `"8h"` — ночь); дольше — отказ как сейчас; тег `rest_repeat`
  снять в обоих случаях. (б) Только снять тег, поведение прежнее (герой «спит» без восстановления, модель
  двухшаговку не делает — t1002). (в) Как есть. Рекомендую (а): игрок сказал «лечь спать», он получает сон и
  восстановление, лишний вызов модели не нужен; видимое — часы уходят дальше (как при `until: long_rest`), сцена
  закроется по `time_jump`. Подварианты порога: 8 ч / без порога — выбор проектировщика.
- **Р3 (171) — контекст дешёвого повторного запроса.** (а) Только текст хода и `player_input`, один инструмент
  `offer_choices`, модель рассказчика (≈ 1,5 k токенов вместо ≈ 40 k). (б) Плюс имена `scene_npcs` и соседних
  `locations` (ещё ≈ 0,3 k). Рекомендую (а): вопрос и действующие лица уже в тексте хода; варианты — строки, id не
  нужны. Риск: варианты без памяти о прошлых ходах чуть площе — видит игрок, цена одного вызова ≈ в 20 раз ниже.
- **Р4 (170) — когда `parent_id` обязателен.** Решение 4 говорит «локация внутри паковой», но движок «внутри» по
  смыслу не видит. (а) Обязателен всегда: любое место лежит в здании, городе или области; загородное — в области
  пака (в drunk_dragon 9 верхних узлов, в dusk — `dusk_cape`). (б) Обязателен, только если есть связь ≤ 500 м с
  локацией, у которой есть родитель; иначе место «загородное». Рекомендую (а): в dusk цепочка шла от ai-локаций без
  родителя (`rectors_study_chamber`—`peat_oak_grove`), (б) её не поймает; роль world (`world_rules.md:7`) тоже
  создаёт локации — для неё правило то же.
- **Р5 (142) — что значит «те же NPC».** (а) Равенство множеств живых NPC в локации героя до и после границы.
  (б) Все NPC сцены на месте (новые не мешают). Рекомендую (б): случайный вошедший не глушит музыку; ушедший —
  глушит. Риск обоих (свинопас): NPC «ушёл» в рассказе, но мастер его не переместил — метка залипает; рассказчик
  снимает её `scene_mood none`.
- Риск П1 для живых сейвов: `merge_new` идёт через `check_location` (`campaign/merge.py:3` →
  `campaign/uniqueness.py:54`): при догрузке пака в сейв, где ai уже создал локацию с таким же именем, паковая
  локация отбросится как `Conflict`. Игрок dusk ещё не обновлялся (ROADMAP:109): проверить отчёт слияния при
  загрузке. Старые дубли (`drunken_dragon_inn`, `academy_hall`) остаются — слияние только с согласия и бэкапом (136).
- Риск П1: после правила родителя мастер может чаще получать отказ `location_create` и описывать место без него —
  это уже сейчас штатно («опиши иначе»); следить по `issues/` первого прогона.
- Риск П3: `looks_like_plan` ложно сработает на рассказе с инструкцией NPC («Опиши мне, что ты видел: 1… 2…») —
  поэтому второй признак (имя инструмента/«отклонён») и консервативный порог; ложное срабатывание стоит один повтор.
- Регресс в области: тесты на флип выше; `vulture_allowlist` не трогаем; smells ≤ 200 — при росте вынос в
  `rules/locations.py`.

### Умолчания (внутреннее)

- Имена: `connection_problem`, `inside_of`, `LocationsConfig.inside_max_m`, `scene_npc_ids`, `wait_for_long_rest`,
  `LimitsConfig.long_rest_wait_max` (строка длительности, как `long_rest_cooldown`), `cut_choice_head`,
  `looks_like_plan`, `PLAN_NOTE`, тег `plan_leak`, поле `MasterResult.choices_announced`.
- «Внутри родителя» (`inside_of`): другая локация — сам родитель, его потомок любой глубины или его предок; предки
  считаются по цепочке `parent_id` с защитой от цикла.
- При Р2 = а: ожидание считается от `next_long_rest_s`; `lodging_unpaid`, `swap_invalid`, `prey_invalid` проверяются
  до ожидания; тег `rest_repeat` снят и у отказа.
- При Р3 = а: короткий system — одна фраза «Ты предлагаешь игроку 2–3 варианта действия по тексту хода», без кэша
  (`cache=False`); повторный запрос по-прежнему один, без `rounds`/`invalid_count`.
- При Р5 = б: сравнение `npcs_before <= scene_npc_ids(work)` после `call_world`; NPC, убитый тиком, считается
  ушедшим (метка не переносится).
- Тексты сигналов мастеру и строки лога — как в партиях выше; игроку в ленту идут только строки лога
  («Герой ждал до …», «Новая локация: …»).
- Тесты — рядом с существующими файлами модулей (`test_uniqueness.py`, `test_apply_world.py`, `test_rest_repeat.py`,
  `test_game_boundary.py`, `test_leaks.py`, `test_master_choices_ask.py`), новый файл только для `connection_problem`
  (`tests/unit/protocol/test_location_parent.py`).

### Открытые вопросы

1. Р4 — `parent_id` обязателен всегда или только при короткой связи внутрь (`world.py:154`
   `location_create`)? Рекомендую (а) всегда; разблокирует П1; решает проектировщик. Блокирующий.
2. Р1 — `per_scene` 30/40 и `step` 10/15 (`defaults.toml:85–87`, `world.py:188` `wanted_attitude`)? Рекомендую
   30/10; разблокирует П1 шаг 3; решает проектировщик.
3. Р2 — `rest long` в кулдауне: движок ждёт сам (≤ 8 ч) / только снять тег / как есть (`resources.py:802`
   `rest_redundant`, `:855` `rest`)? Рекомендую (а) с порогом 8 ч; разблокирует П2; решает проектировщик.
4. Р5 — «те же NPC»: равенство / все старые на месте (`game/scene.py:14` `start_scene`)? Рекомендую (б);
   разблокирует П2 шаг 2; решает проектировщик.
5. Р3 — контекст дешёвого повтора: только текст хода / плюс имена NPC и мест (`session.py:368` `ask_choices`)?
   Рекомендую (а); разблокирует П3 шаг 2; решает проектировщик.

## Смета (кабан-тесть, режим 1)

Кабан-тесть, 2026-10-24. Новых платных позиций (подписки, хостинг, зависимости) план не вводит. Игровой API: Р3 = (а)
удешевляет повтор `ask_choices` (≈ 40 k → ≈ 1,5 k входа на вызов, оценка папы); 141 добавляет до 2 повторов хода
только при ложном/настоящем плане (редко). Токены по ролям — по последнему «Итогу» (`docs/plan-u1.md`, 4 партии,
131,6 M / $61,43 вместе с 164), масштаб на 3 партии средней величины; $/M каждой роли — из того же итога
(смесь кэш-чтения). Модели — `model:` из `~/.claude/agents/`. Цены — тариф metrics.py от 2026-10-17
(https://platform.claude.com/docs/en/about-claude/pricing), страницу не сверял; fable — по ценам Opus.

| Партия | Время |
|---|---|
| груминг + план (уже прошли) | ≈ 90 мин |
| П1 (локации, отношение; 6 функций в mutmut, флип 4 тестов) | ≈ 180 мин, из них cov ≈ 40 |
| П2 (сон, музыка) | ≈ 150 мин |
| П3 (кнопки, план; `session.py` — риск 2–3 кругов ревью, как П3 У1) | ≈ 200 мин |
| итого | ≈ 620 мин без ожидания решений |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | ≈ 40 M | ≈ 14,8 |
| papa-kaban | fable (цены Opus) | ≈ 2,5 M | ≈ 2,6 |
| svinopas | opus | ≈ 1,3 M | ≈ 0,8 |
| kaban | sonnet | ≈ 12 M | ≈ 4,8 |
| kaban-doeba | sonnet | ≈ 18 M | ≈ 6,5 |
| mama-kaban | opus | ≈ 3,5 M | ≈ 3,9 |
| kaban-svekrov | opus | ≈ 3,5 M | ≈ 4,2 |
| kaban-test | opus | ≈ 1,5 M | ≈ 2,5 |
| итого | | ≈ 82 M | ≈ 40 |

Дешевле (выбор пользователя): оркестратор — /compact между партиями (≈ −10 M, ≈ −$4; теряем — ничего, правило уже
есть); mutmut-разбор выживших — haiku вместо sonnet (≈ −$0,5; теряем точность разбора). Ревью, аудит и модели
мамы/свекрови/оркестратора не трогаем.

## Правки по ревью

### П1

Аудит свекрови: чисто (всё прослеживается к решениям 3, 4, 6–8, 11, 13). Ревью мамы — три пункта, все приняты
(решение мамы, по решению 3 и 13):
1. `location_create`: `connection_problem` перенесён после проверки конфликтов имени и id — мастер без `parent_id`
   с занятым именем сразу получает существующий id (кабан).
2. Тест на соседа родителя (связь с другим ребёнком родителя родителя на 3000 м принимается) и тест «без родителя,
   имя занято → в сигнале существующий id» (доеба).
3. `test_location_create_without_parent_is_rejected_with_connections` проверяет «parent_id» в сигнале (доеба).

По полному прогону (`make cov`, 3 падения из 21 496):
4. `narrator_rules.md`: `parent_id` без бэктиков — `test_rules_mention_only_known_tools` считает имя в бэктиках
   инструментом (кабан).
5. `test_auto_reports.py`: механизм авто-репорта проверяется через `give_item` qty 50 (тег `limit-exceeded`
   остаётся у предметов); новый `test_clamped_attitude_writes_no_report` — клэмп отношения без репорта, решение 7
   (доеба, по указанию оркестратора).
6. Хелпер `too_friendly_call` → `over_limit_item_call` в `test_auto_reports.py` (ревью мамы, доеба).
7. mutmut по 7 функциям: 306 убито, 31 выжил, 1 таймаут (`climbs_to_10` — зависание на цикле, по сути убит).
   На новых строках доеба (sonnet) добавил 4 теста в `test_location_parent.py` (reason/сигнал без родителя, конфликт
   id+имя, рамка сигнала конфликта). Старые строки — BACKLOG 175.
8. Ревью мамы к тестам п. 7: тест конфликта id+имя проверяет ровно один «; » и оба текста конфликта (принято, доеба);
   замена точного сигнала «без родителя» на `startswith` — условное предложение, отклонено доебой: оставила бы живыми
   мутантов `connection_problem` 12 и 13.

### П2

Ревью мамы: можно мержить, без правок (двойной вызов `rest_wait_s` в `rest` оставлен). Аудит свекрови: чисто
(решения 1, 9, 12, 13; `rest_wait_s` — в FUNCS mutmut):
1. Комментарий к `STATIC_MAX` в `test_static_budget.py`: номер пункта 173 → 142 (аудит свекрови, доеба).
2. mutmut по 7 функциям: ≈ 310, выжили 27. На новых строках (`rest` 122, 128, 129, 131, 132 — reason и сигнал
   «герой ждал») доеба (sonnet) добавил 2 теста в `test_rest_repeat.py`. Старые строки — BACKLOG 176.
3. `make smells` 201 > 200: условие переноса `scene_mood` вынесено в хелпер `mood_carries` в `scene.py`, поведение
   то же (кабан).
4. По полному прогону (2 падения из 21 565, оба — старое правило «новая сцена сбрасывает метку», Р5): в
   `test_zh3_knowledge.py` место и NPC те же — тест ждёт `romance`; `test_narrator_knowledge_rules.py` — проверка
   новой формулировки двумя тестами (доеба).
   Для живого прогона (мама): если мастер «разводит» NPC только текстом, без `npc_update`/перемещения, метка
   переживёт сцену — следствие Р5, смотреть в логах.
5. После правок 3–4: smells 200; mutmut `mood_carries` + `start_scene` — 39/39 убиты; затронутые тесты 7722 passed.
