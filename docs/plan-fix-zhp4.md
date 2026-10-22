# Фикс ЖП4 (BACKLOG 129, 130, 131, 128 + хвост 127 `inv_rows_66`)

Контур: вне msa; режим: встроить. План папы-кабана 2026-10-21 по грумингу свинопаса и аудиту свекрови (scratchpad
сессии) и решениям проектировщика на окнах груминга. ROADMAP блок Ф, строка «Фикс ЖП4 ▶».

## Суть

Четыре находки живого прогона ЖП4 (docs/plan-zhp4.md «Итог») и хвост 127:

- **129 (high)** — на OpenAI оценка входа ×1,43 к факту вытесняла прошлые ходы и все соседние локации: герой не мог
  уйти (`unsupported_action` на «иду в таверну», ходы 599–600). Правки: `openai = 3.5` в умолчаниях и соседние локации
  текущего места — в неустранимое.
- **130 (low)** — строки ленты «Записано в журнал: npc Лира» и «Лира запомнил: joke»: сырой код вида и мужской род.
- **131 (low)** — «засыпаем до утра» при отклонённом длинном отдыхе: категорий `advance_time` только minute…month,
  рассказчик копит `advance_time hour` (репорт t623). Нужен сдвиг до цели: утро / час N / момент, когда снова можно
  длинный отдых.
- **128 (medium)** — окно `/inv` одним списком ≈ 50 строк; нужны разделы вкладками (NOTES.md 2026-10-21).
- **127, хвост** — тест на мутант `inv_rows__mutmut_66` (неизвестный id перед известным).
- **132 (high, решение 13)** — рассказчик сыграл визит к Грете (`apothecary_shop`) без `travel_to`: герой по сейву
  в `tavern_drunken_dragon`, `/shop` пуст. Разбор причины — раздел «132: причина».

Без полей сейва. Новое в конфиге: `openai = 3.5` (app_defaults) и час утра (defaults.toml `[time]`).

## 132: причина (calls-019, run c81c9c, ходы 624–631; сейв auto-1 — только чтение)

- Ход 627, ввод «Сделать крюк через лавку матушки Греты»: рассказчик вызвал `advance_time category=minute` и
  `offer_choices`, текстом провёл героя по городу до двери лавки; ход 628 — «толкнуть дверь» — то же; 629–631 —
  разговор с Гретой. Ни `travel_to`, ни `unsupported_action`, тегов репортов нет. Все 8 ходов — `committed`.
- Что рассказчик видел: `locations` = `tavern_drunken_dragon` (0 м), `sanctuary_of_dawn` (1000 м), `chernolesye`
  (15 000 м), `old_tower` (48 270 м). Лавки среди них нет. `known_npcs` (20 NPC) — без Греты: она не ключевая,
  не в локации героя, без активного триггера и по имени в `recent_turns`/вариантах не названа («у матушки» —
  `npc_reason_set` ищет `npc.name.lower()` в тексте). Торвальд (`torvald_merchant`) там есть — с `location_id:
  upper_city_square`, но и площадь не соседняя. Блок `knowledge` о Грете пуст. Лавку рассказчик помнит из выжимок.
- Карта: `apothecary_shop` связана только с `upper_city_square` (80 м), площадь — с `sanctuary_of_dawn` (150 м) и
  `dawn_cell_alley`; путь из таверны — три перехода: таверна → Святилище (1000) → площадь (150) → лавка (80),
  ≈ 1230 м ≈ 15 мин при `normal`. Протокол и обработчик `travel` (`resources.py:854`) знают только соседей
  (`reachable_ids` — связи в обе стороны): любой `travel_to` не-соседа → Invalid `no_route`. На OpenAI (ходы
  599–600, 129) рассказчик в той же ситуации отвечал `unsupported_action`; gemini — играет молча.
- По сейву у `apothecary_shop` и `upper_city_square` поле `visited: false`, но флаги `world.flags["visited:…"]`
  стоят — когда-то (ЖП3) герой туда доходил движком; в calls-018/019 `travel_to` в лавку нет — визит 627–631 сыгран
  текстом (уточнение 2026-10-21 по находке кабана: поле `visited` ставит только пак, движок — флаг). Это не разовый сбой,
  а дыра: цель не в `locations` → правил на этот случай нет (narrator_rules:44 говорит лишь «id бери только
  отсюда»), многошагового пути нет, детектора «уехал текстом» нет и быть не может.
- Данные мира: две локации «Таверна „Пьяный Дракон“» — `tavern_drunken_dragon` (пак, теги таверна/безопасная зона,
  соседи 1–48 км) и `drunken_dragon_inn` (`origin: ai`, соседи — склад 400 м, Святилище 600 м). Городские места
  от роли world цепляются к Святилищу/второй таверне, а герой живёт в паковой — отсюда 2–3 перехода до любой лавки.
  Дубль — в беклог (не шаг); 42 связи из 53 локаций односторонние (`nearby_locations`/`reachable_ids` и так считают
  обе стороны — для пути не помеха).

Итог: три причины — (а) протокол умеет только соседний переход, (б) рассказчик не видит id дальних известных мест
(лавка не в `locations`, Грета не в `known_npcs`), (в) правил на «цель не рядом» нет. Чинить все три; (в) одна
не держит (101: правило без механики gemini обходит).

## Решения

Проектировщик, 2026-10-21 (окна груминга, вопросы свинопаса В1–В6):

1. 131, В1: «спим до утра», когда длинный отдых ещё нельзя → время доматывается до момента, когда отдых снова
   можно, и сразу `rest long` — одним ходом, с восстановлением HP и ресурсов.
2. 131, В2: «утро» — фиксированный час в конфиге (например 06:00).
3. 131, В3: «до часа N», если час уже прошёл сегодня → до этого часа завтра.
4. 130, В4: строка журнала знаний — без вида записи: «В журнал знаний (/lore): Лира».
5. 130, В4: память NPC — «Лира запомнит это: шутка» (форма без рода; русские подписи 18 видов `MEMORY_KINDS`).
6. 130, В5: объём — две строки из 130 плюс «уже помнит {вид}»; остальные строки ленты с сырыми кодами/родом в шаге
   не трогаем.
7. 128, В6: приняты рекомендации 6.1–6.5: надетое — только во вкладке «Надето»; пустые вкладки скрыты; первой
   открывается первая непустая; ненадетая `clothing` и `""` — в «Снаряжение»; неизвестный id — в «Снаряжение».
8. 129: соседние локации текущего места никогда не вытеснять (не «пол N», как `recent_turns_floor`).
9. 129: `openai = 3.5` — в умолчания (`src/ai_dm/config/app_defaults.toml`).
10. Живых проверок-заданий проектировщику нет: он просто играет (решение 2026-10-19 подтверждено).
11. Ходы 624–627 на gemini — провайдер переключён намеренно.
12. BACKLOG 125: пометка ROADMAP «до Э10б — решение итога ЖП4» решением проектировщика не была; место 125 —
    архитектор (см. «Предложения архитектора»).
15. 2026-10-21, проектировщик: kaban-doeba — opus; партии — три (П1 + П2 не сливать).
14. 2026-10-21, проектировщик: развилки Р1–Р8 — принять рекомендации папы (Р1 (1), Р2 (1), Р3 06:00, Р4 (1),
  Р5 подписи как в плане, Р6 (1), Р7 (1), Р8 (1)).
13. 2026-10-21, проектировщик: BACKLOG 132 (рассказчик играет визит к Грете без `travel_to`, `/shop` пуст) —
    включить в Фикс ЖП4.
16. 2026-10-21, проектировщик (окно по аудиту свекрови П1): «известное» место для `known_locations` — паковое
    `Location.visited` **или** флаг `visited:<id>` (рекомендация папы); принят рост блока ≈ 510 → ≈ 900 токенов и
    18 паковых мест, где герой движком не был.
17. 2026-10-22, проектировщик (окно по аудиту свекрови П2): `until` ровно в H:00 → до H:00 завтра (умолчание папы).
18. 2026-10-22, проектировщик (окно по аудиту свекрови П2): при 0 HP `until` сдвигает время по формуле (умолчание
    папы).
19. 2026-10-22, проектировщик (П3, окно по хэнд-бэку кабана): в `vulture_allowlist` — две строки для обработчиков
    Textual `InvModal.on_tabs_tab_activated` и `InvModal.action_tab`.
20. 2026-10-22, проектировщик (П3, окно по аудиту свекрови, «Принять модуль»): `inv_section` и `inv_tabs` — в новом
    модуле `src/ai_dm/ui/tui/inv_sections.py`, не в `blocks.py` (smells 201 > 200); mutmut П3 —
    по `ai_dm.ui.tui.inv_sections`.

Развилки плана (Р1–Р8, раздел «Развилки») — решения проектировщика дописать сюда при аппруве.

## Правила (было → станет)

- 129: `master/prompt.py:312` было `fixed_locations = [place.id]`, `locations = [x["id"] for x in far_first]` →
  станет `fixed_locations = [place.id, *(x["id"] for x in nearby)]`, `locations = []` (сортировка `far_first` уходит).
  Ступень `locations` в `STAGES` у рассказчика больше не срабатывает (при Р2 = (1) ступень остаётся в планировщике).
- 129: `app_defaults.toml` `[master.chars_per_token_by_provider]` было `anthropic = 2.2`, `gemini = 3.0` → станет
  плюс `openai = 3.5` (калибровка calls-018: оценка ×1,43 к факту; после 3,5 оценка = факт 31,5k, ходы 612–622).
- 130: `knowledge.py:94` было `f"Записано в журнал: {request.kind} {ref_name(ctx, request)}"` → станет
  `f"В журнал знаний (/lore): {ref_name(ctx, request)}"`.
- 130: `world.py` `change_memory` было `f"{npc_label(npc)} запомнил: {request.memory_kind}"` → станет
  `f"{npc_label(npc)} запомнит это: {MEMORY_KIND_TITLES[request.memory_kind]}"`; было
  `f"{npc_label(npc)} уже помнит {request.memory_kind} в этой сцене"` (log) → станет
  `f"{npc_label(npc)} уже помнит это в этой сцене: {MEMORY_KIND_TITLES[...]}"`. `signal_to_master` и `reason`
  (для рассказчика и репорта) — с кодом вида, не трогаем (решение 6).
- 131: `resources.py:845` было `(request.category is None) == (request.travel_to is None)` → Invalid → станет
  «ровно одно из `category`, `travel_to`, `until`» (при Р1 = (1); при (3) правило не меняется).
- 128: `InvModal(title, rows)` одним списком → `InvModal(title, tabs)` вкладками; строки `inv_rows` получают раздел.
- 132 (при Р7 = (1)): `resources.py:863–878` было «`route` — одна связь `here → travel_to` или обратная, иначе
  Invalid `no_route`» → станет «кратчайший путь по карте (связи в обе стороны, сумма `distance_m`); нет пути —
  `no_route`»; время — сумма `travel_seconds` по переходам. `master/prompt.py:496` `state_data`: было `locations` =
  текущая + соседи → станет плюс `known_locations` = известные (`Location.visited` или флаг `visited:<id>`, решение 16) не-соседние `{id, name}`.
  `relevance.py:29` `npc_reason_set`: было причины `with_hero/here/active/key/said/nearby` → станет плюс `merchant`
  (`npc.trade is not None`, вытесняемая, после `nearby`). `narrator_rules.md:44` было «для `advance_time.travel_to`
  бери id только отсюда» → станет «из `locations` или `known_locations`; движок проведёт по карте; в другое место
  без `travel_to` герой не попадает — нет id → `unsupported_action`».

## Поведение

- 129: меняется состав промпта — соседние локации всегда в `locations` состояния хода; `recent_turns` по-прежнему
  вытесняются до 3–5 из 8 (ограничитель `context_cap = 16000`, не калибровка — находка в беклог, ниже).
- 130: три строки ленты.
- 131: новый запрос рассказчика `advance_time` с целью; текст отказа 100 (`rest_redundant`, сигнал рассказчику)
  дополняется подсказкой `until: long_rest`.
- 128: окно `/inv` — вкладки; текстовый `/inv <аргументы>` и справка в ленте — без изменений.
- 132: что увидит игрок — «иду к Грете» из таверны: герой реально оказывается в лавке (один `travel_to`, часы +≈ 15
  мин, `/shop` показывает Грету), в ленте строка пути (Р8); место, которого рассказчик не знает (нет в состоянии) —
  `unsupported_action`, рассказчик говорит, что дороги не знает / уточняет; промежуточные места по пути получают
  `visited` (умолчание). Что сделает игрок — ничего нового.

## Вне репо

Нет. Проектировщику после коммита П1 — снять временный `openai = 3.5` из ~/.config/ai-dm/config.toml (бэкап
config.toml.bak-20261021): иначе переопределение скроет будущие калибровки.

## Модули / функции (grep 2026-10-21)

- `src/ai_dm/config/app_defaults.toml:156` `[master.chars_per_token_by_provider]` — `openai = 3.5`.
- `src/ai_dm/master/prompt.py:299` `PromptBuilder.candidates` — соседние в `fixed_locations`.
- `docs/ARCHITECTURE.md` E4 (стр. 677): «→ соседние локации →» — пометить, что у рассказчика соседние фиксированы (129).
- `src/ai_dm/protocol/handlers/knowledge.py:81` `knowledge_note` — строка лога.
- `src/ai_dm/protocol/handlers/world.py:182` `change_memory` — две строки лога; `MEMORY_KIND_TITLES` — **новая**
  (словарь 18 подписей; место — `src/ai_dm/state/relations.py` рядом с `MEMORY_KINDS`, как `KIND_TITLES` журнала
  в `game/lore_text.py`).
- `src/ai_dm/protocol/requests.py:394` `AdvanceTime` — поле(я) цели, `NEUTRAL`, docstring.
- `src/ai_dm/protocol/handlers/resources.py:754` `rest_redundant` — формула порога выносится в `next_long_rest_s`
  (**новая**, там же), сигнал дополняется; `:826` `time_by_category`; `:844` `advance_time` — ветка `until` →
  `time_until` (**новая**); `time_repeated` (:813) — не трогаем.
- `src/ai_dm/config/defaults.toml:1` `[time]` + `src/ai_dm/config/settings.py:17` `TimeConfig` — `morning_hour`
  (**новое поле**).
- `src/ai_dm/master/prompts/narrator_rules.md:130` (абзац «Время двигай…») — строка про `until`.
- `src/ai_dm/ui/tui/blocks.py:80` `inv_rows` — раздел в строке; `inv_section` (**новая**), `inv_tabs` (**новая**).
- `src/ai_dm/rules/trade.py:9` `item_category` — переиспользуется для раздела (weapon/armor/ammo/gear/consumable/
  clothing/valuable/None=quest); `ammo_for` второй раз не изобретаем.
- `src/ai_dm/ui/tui/modals.py:147` `InvModal` — вкладки (`textual.widgets.Tabs`, Textual 8.2.8 в lock; `Tabs`
  есть, бинды ←/→ только при фокусе на самих вкладках — в модалке фокус у списка, значит бинды свои).
- `src/ai_dm/ui/tui/app.py:469` `push_screen(InvModal(title, inv_rows(self.game)))`, `:507` `can_pick_item`,
  `:513` `inv_chosen` — вызов с вкладками; `app.tcss:192` `#inv-list` — стиль вкладок.
- `src/ai_dm/ui/tui/strings.py:52` `INV_PICK` — подсказка; `INV_TABS` (**новое**) — названия вкладок.
- 132: `src/ai_dm/protocol/handlers/resources.py:854` `travel` — путь по карте через `route_path` (**новая**;
  место — `src/ai_dm/rules/time_ops.py` рядом с `travel_seconds` или `master/relevance.py` рядом с
  `nearby_locations`: обе читают `world.locations`); `src/ai_dm/protocol/hints.py:23` `reachable_ids` — подсказка
  `allowed` (LIMIT 20): оставить соседей (умолчание); `src/ai_dm/master/prompt.py:496` `state_data` —
  `known_locations`; `src/ai_dm/master/relevance.py:29` `npc_reason_set`, `:72` `rank_npcs` — причина `merchant`;
  `src/ai_dm/protocol/requests.py:404` `AdvanceTime.travel_to` — описание; `narrator_rules.md:44` и `:130` — правило;
  `docs/ARCHITECTURE.md:279–281` (путешествие) — фраза о пути по карте.
- Тесты (доеба): `tests/unit/protocol/test_apply_resources.py:583–640` (`travel`: `goblin_den` без связей — `no_route`
  остаётся), `tests/unit/master/test_master_relevance.py` (`npc_reasons`), `test_master_prompt.py:502–560`
  (`locations` состояния); `tests/unit/master/test_static_budget.py:38` `STATIC_MAX`; `tests/scenarios/memory_script.py:28`
  `MEMORY_CONTEXT_CAP`; `tests/scenarios/test_stage4_memory.py:159` `test_every_stage_fires_somewhere`;
  `tests/unit/master/test_master_context_build.py:22` `FULL_ORDER` (6 `locations` уходят); `tests/unit/protocol/
  test_npc_update_memory.py:311, 539–555`, `test_npc_update_name.py:118, 392` (строки «запомнил»);
  `test_apply_knowledge.py`, `tests/scenarios/test_zh3_knowledge.py` (grep «Записано» — проверить);
  `tests/unit/protocol/test_xp_time_repeat.py:336–351` (`category`/`travel_to`), `test_rest_repeat.py`;
  `tests/unit/ui/tui/test_tui_inv.py` (41 тестов: `app.screen.rows`, `#inv-list`, `labels()`).

## Цифры

- Статика: замер сейчас `explore.total 21307` (rules 10530, tools 10777), порог `STATIC_MAX 21620`, запас 313.
  131 добавляет в схему `AdvanceTime` поле(я) с описанием (≈ 250 знаков в JSON схем) и строку правил (≈ 300 знаков)
  → ≈ +220 токенов → ≈ 21530: впритык; при превышении доеба поднимает порог «замер + 3 %» с причиной в шапке теста
  (как Фикс ЖП3 П3).
- Соседи «никогда не вытеснять» (живой мир drunk_dragon-00000001, auto-1, 53 локации): максимум связей — 8 у
  `sanctuary_of_dawn`, JSON `locations` ≈ 736 знаков ≈ 295 токенов при 2,5 (≈ 210 при 3,5) — ≤ 2 % от
  `context_cap 16000`. Фиксированная часть растёт на эти ≈ 300, не больше.
- `MEMORY_CONTEXT_CAP 2806` (`memory_script.py`): в сценарии 6 соседних локаций, 5 с `LONG_NAME` (812 знаков) ≈ 340
  токенов каждая ≈ 1,7k; они давили именно на ступень `locations`. После 129 ступень у рассказчика не срабатывает →
  `test_every_stage_fires_somewhere` ждёт `set(STAGES) - {"locations"}`, а 1,7k становятся неустранимыми.
  Два пути (умолчание доебы, Р2): укоротить имена локаций сценария (давление на `locations` больше не нужно) и
  подобрать `MEMORY_CONTEXT_CAP` заново (ожидание ≈ 2850–2950) — рекомендую; или оставить имена и поднять CAP на
  ≈ 1,7k (≈ 4500) с подбором. Условия подбора прежние: без `overflow`, ступени turns/scenes/npcs/chapters срабатывают,
  главы 1–4 на сцене 50 на месте.
- `context_cap 16000`: на openai после 3,5 (оценка = факт 31,5k) и на gemini (34,1k / 32,3k) вытесняются 4–5 из 8
  `recent_turns` — потолок динамики, не калибровка. В шаг не входит → «Находки для беклога».
- 132, статика: правило (≈ 400 знаков) + описание `travel_to` (≈ 60) ≈ +180 токенов; вместе со 131 (+220) замер
  ≈ 21 700 > порога 21620 → порог поднимается до «замер + 3 %» (≈ 22 350), причина в шапке; сторож
  `STATIC_MAX + context_cap ≤ window80` при окнах ≥ 128k не мешает.
- 132, динамика: `known_locations` в живом мире сейчас 22 посещённых из 53 → 1276 знаков ≈ 510 токенов при 2,5
  (≈ 365 при 3,5); все 53 — 3369 знаков ≈ 1350 (потолок). Торговцев 2 (Торвальд, Грета) ≈ +100 токенов в
  `known_npcs`. Блок фиксированный (не вытесняется, как `locations` после 129) — иначе при недооценке бюджета
  дальние цели исчезают первыми, и 132 возвращается; суммарно ≤ 10 % cap.
- 132, путь: 53 локации, Дейкстра по сумме `distance_m` — мгновенно; подсказка `allowed` при `no_route` — соседи
  (как сейчас), не все 38 достижимых.

## Партии

Порядок ROADMAP «129 → 128 → 130 → 131» — по приоритету; исполнение — по областям кода. Со 132 (high, решение 13)
партий три (решение архитектора, не развилка):
**П1 = 129 + 132** — движение героя (конфиг, `candidates`/`state_data`, `travel`, relevance, правило) — оба high,
одна область; **П2 = 130 + 131** — лента и время (лог, протокол `until`, правило; свой замер статики);
**П3 = 128 + хвост 127** — только TUI. Было П1 = 129 + 130 + 131, П2 = 128 + 127 (ROADMAP); 132 в старый П1 делает
его M и смешивает high с low. Хочет проектировщик меньше кругов ревью — П1 + П2 сливаются обратно (один замер
статики), цена — большое ревью. Смету тесть пересчитывает под три партии.

### П1 (129, 132) — модель кабана и доебы sonnet (ROADMAP)

Шаги 129 — пп. 1–3; 132 — пп. 12–17 (нумерация сквозная по шагу, чтобы ссылки ревью не плыли).

1. 129 — `app_defaults.toml` — `openai = 3.5` с комментарием «ЖП4: оценка/факт 1,43 по calls-018». Проверка:
   `MasterConfig.cpt_for("openai") == 3.5` (тест рядом с `gemini = 3.0`).
2. 129 — `PromptBuilder.candidates` — `fixed_locations = [place.id] + соседние`, `locations = []`; `far_first`
   убрать (иначе `make dead`). Проверка: план хода при `cap=1` не содержит `("locations", …)` в `dropped`,
   `locations` состояния — все соседи; `FULL_ORDER` без 6 локаций. Комментарий в `candidates`: «соседние — цели
   travel_to, вытеснять нельзя (129)». ARCHITECTURE E4 — одна фраза.
3. 129 — `memory_script.py` / `test_stage4_memory.py` — по разделу «Цифры» (доеба; при Р2 = (1)).
12. 132 — `route_path(world, from_id, to_id) -> list[tuple[str, int]] | None` (**новая**): Дейкстра по сумме
    `distance_m`, связи в обе стороны (как `reachable_ids`), ответ — переходы `(id, distance_m)` без старта; нет
    пути — None. Проверка: три перехода таверна → лавка, кратчайший из двух маршрутов, изолированная — None.
13. 132 — `travel`: `route_path` вместо поиска одной связи; `no_route` только при None (подсказка `allowed` —
    соседи, как сейчас); секунды = Σ `travel_seconds(d, pace)`; `hero.location_id` и спутники — в цель;
    `location_visited` и `apply_events` — на каждый переход по порядку (умолчание); лог по Р8; `result` +
    `"path": [id…]`. Проверка: часы, флаги `visited:*` промежуточных, события, спутники, лог.
14. 132 — `state_data`: `known_locations` — `[{id, name}]` известных локаций, кроме текущей и соседей, по id;
    пусто → ключа нет (как `knowledge_data`). «Известна» = `Location.visited` **или** `world.flags["visited:<id>"]`
    (решение архитектора 2026-10-21 по находке кабана: движок поле `visited` нигде не ставит — оно приходит из
    пака как «известно с начала» (в auto-1 — 18 паковых мест: город, Старая башня, Чернолесье…), а путь `travel`
    пишет только флаг `visited:<id>` (25 мест, в т. ч. `apothecary_shop`); читатели поля — `summarizer.py:114`,
    `rules/knowledge.py:177`. Оба источника — «герой знает дорогу», вместе 39 из 53 ≈ 2,3k знаков ≈ 900 токенов
    при 2,5; игроку разницы нет — не развилка). Проверка: место с полем, место с флагом, оба, ни того ни другого;
    соседи не дублируются.
15. 132 — `npc_reason_set`/`rank_npcs`: причина `merchant` (`npc.trade is not None`), вытесняемая, ранг после
    `nearby`; `relevant_npcs` (вход роли world) унаследует причину из `npc_reason_set`; если тесты роли world
    ломаются — исключить `merchant` там (умолчание).
16. 132 — `AdvanceTime.travel_to` описание: «Id локации из locations или known_locations; путь по карте считает
    движок; пусто = нет». `narrator_rules.md:44`: «…бери id из `locations` или `known_locations` (посещённые места);
    движок сам проведёт через промежуточные локации и посчитает время. Герой не оказывается в другом месте без
    `travel_to`: нет id — `unsupported_action`, не описывай приход»; `:130` — «Путь в другую локацию — всегда
    `travel_to`, даже если она не соседняя».
17. 132 — ARCHITECTURE «Путешествие» (стр. 279): фраза о пути по карте и `known_locations`. Порог статики в П1 не
    трогать, если влезает, иначе поднять с причиной; основной замер — П2.

### П2 (130, 131) — sonnet

4. 130 — `state/relations.py` `MEMORY_KIND_TITLES` (18 подписей, Р5) + `change_memory`: «{имя} запомнит это:
   {подпись}», «{имя} уже помнит это в этой сцене: {подпись}». Проверка: `decision.log`; `signal_to_master` прежний.
5. 130 — `knowledge_note`: «В журнал знаний (/lore): {ref_name}». Проверка: лог для npc и location.
6. 131 — `defaults.toml` `[time] morning_hour = 6` (Р3) + `TimeConfig.morning_hour: int` (`ge=0, le=23`).
7. 131 — `AdvanceTime`: форма по Р1 (рекомендация — `until: Literal["none","morning","long_rest","hour"]` и
   `until_hour: int = -1`, описания коротко; `NEUTRAL` += `until: "none"`, `until_hour: -1`; docstring «ровно одно из
   category, travel_to и until»).
8. 131 — `resources.py`: `next_long_rest_s(hero, cfg) -> int | None` (вынос из `rest_redundant`: `end_s +
   Duration.parse(cfg.limits.long_rest_cooldown).seconds`); `advance_time` — проверка «ровно одно» на три поля,
   ветка `until` → `time_until(ctx, request)`:
   - `morning` → цель `morning_hour`; `hour` → `until_hour` (без `until_hour` при `until=hour` → Invalid
     `until_hour_required`; `until_hour` без `hour` → Invalid `until_hour_only_with_hour`);
     цель в секундах: `target = now - now % DAY + H*3600`; `target <= now` → `+ DAY` (решение 3; ровно H:00 сейчас
     → завтра, умолчание);
   - `long_rest` → `next = next_long_rest_s(hero, cfg)`; `next is None or now >= next` → `rejected("отдых уже
     можно", "Длинный отдых уже возможен: вызови rest long, время не двигай.")` без report_tag;
   - сдвиг `world.clock.advance(target - now)`, лог `TIME_LOG` (как у категорий), `concentration_note`, result
     `{"seconds", "now_s"}`. `time_repeated` для `until` не применяется (секунды каждый раз свои; риск Р-риски 3).
9. 131 — `rest_redundant` сигнал: после «время двигай advance_time» добавить «(`until: long_rest` — до момента,
   когда отдых снова можно, затем `rest long` в том же ходу)». Текст 100 игроку не виден (сигнал рассказчику).
10. 131 — `narrator_rules.md` абзац «Время двигай…»: одна фраза про `until` (морнинг/час/отдых) и правило решения 1:
    «„спим до утра“ при отклонённом длинном отдыхе — `advance_time` `until: long_rest`, затем `rest long` в том же
    ходу». Проверка: `test_static_budget` (порог), тест правил — фраза есть.
11. Замер статики в конце П2 (правила трогают П1 и П2 — ratchet штатный); `STATIC_MAX` — только при превышении,
    с причиной.

### П3 (128 + хвост 127)

1. `strings.py` — `INV_TABS` в порядке NOTES: Надето / Оружие / Боеприпасы / Доспехи / Расходники / Снаряжение /
   Ценности / Сюжетное; `INV_PICK` — добавить клавиши вкладок (Р6).
2. `blocks.py` — `inv_section(found, worn) -> str`: `worn` → Надето; `found is None` → Снаряжение (решение 7);
   иначе `item_category(kind, model)`: weapon → Оружие, armor → Доспехи, ammo → Боеприпасы, consumable → Расходники,
   gear/clothing → Снаряжение, valuable → Ценности, None (quest) → Сюжетное. `inv_rows` — четвёртый элемент строки
   (раздел); `inv_tabs(rows) -> list[tuple[str, list]]` — группировка по порядку `INV_TABS`, пустые вкладки
   опущены. Порядок строк внутри вкладки — порядок инвентаря (как сейчас).
3. `InvModal(title, tabs)` — `Tabs` над `OptionList` (id `inv-tabs`); `self.rows` = строки активной вкладки
   (остальной код окна — `show_description`, `on_option_list_option_selected`, `action_act` — без изменений);
   `on_tabs_tab_activated` → перезаполнить список, подсветить 0, описание; бинды переключения (Р6) зовут
   `tabs.action_previous_tab()/action_next_tab()`; первой активна первая вкладка списка (она же первая непустая).
   `app.tcss` — `#inv-tabs` (высота по умолчанию у Tabs 2). `app.py:469` — `InvModal(title, inv_tabs(inv_rows(game)))`.
4. Хвост 127 — тест в `test_tui_inv.py`: неизвестный id первым в инвентаре, известные после → все строки на месте
   (убивает `inv_rows__mutmut_66` `continue → break`).
5. Текстовый `/inv` (аргументы, справка `sheet_text`) и `can_pick_item` — не трогаем.

## Тестовые сценарии (доеба, TDD)

П1 (129) и П2 (130, 131):
- `cpt_for("openai") == 3.5`; `cpt_for("mistral")` — общий 2,5 (перекрытия нет).
- `candidates`: герой в `vale` с 6 соседями → `fixed_locations` = `[vale, …6]`, `locations == []`; `cap=1` →
  `dropped` без `locations`, `state_data["locations"]` содержит всех соседей; герой без `location_id` →
  `fixed_locations == []`.
- `memory_script`: все записи narrator `estimate <= budget`, `overflow False`; ступени turns/scenes/npcs/chapters
  срабатывают; `locations` — нет.
- `change_memory`: `joke` → лог «Олдрик запомнит это: шутка»; повтор тёплого вида в сцене → лог «Олдрик уже помнит
  это в этой сцене: шутка», `signal_to_master` по-прежнему с кодом `joke`; каждый из 18 кодов имеет подпись
  (`set(MEMORY_KIND_TITLES) == set(MEMORY_KINDS)`), подписи русские, без «запомнил».
- `knowledge_note`: npc → «В журнал знаний (/lore): Лира»; location → имя локации; situation → слаг как есть
  (умолчание); в логе нет кода вида.
- `AdvanceTime`: `category` + `until` → Invalid `category_or_travel_to`-подобный код с тремя полями; ни одного →
  Invalid; `until="none"` → None (NEUTRAL); `until_hour=-1` → None.
- `time_until`: 20:06, `morning` (6) → +35 640 с, 06:00 следующего дня; 05:00, `morning` → 06:00 того же дня;
  07:00, `hour`, `until_hour=6` → завтра 06:00; ровно 06:00, `morning` → завтра (умолчание); `hour` без
  `until_hour` → Invalid; `until_hour=25` → ошибка схемы.
- `long_rest`: `long_rest_end_s = 09:50`, кулдаун 12h, сейчас 20:06 → сдвиг до 21:50, затем `rest long` в том же
  ходу принят, HP полные, подъём 05:50; `long_rest_end_s is None` или сейчас ≥ порог → rejected «отдых уже можно»,
  часы не тронуты; при 0 HP — сдвиг считается по формуле.
- `next_long_rest_s`: `rest_redundant` даёт тот же порог (тесты `test_rest_repeat` зелёные без правок текста
  времени); сигнал содержит `until: long_rest`.
- `narrator_rules.md`: фраза про `until` и «затем `rest long`»; `test_static_budget` — порог.
- Проверка руками (проектировщик просто играет, решение 10): вечером после отказа 100 рассказчик делает один
  `advance_time` с `until` и `rest long` в том же ходу — видно в calls-журнале.

П1, 132 (фикстура protocol_kit: `vale → forest` 4800 м; `goblin_den` без связей; тесты добавляют связи сами):
- `route_path`: `forest → hill` 2400 добавлена → из `vale` в `hill` = `[(forest, 4800), (hill, 2400)]`; два
  маршрута (`vale → hill` 9000 напрямую и через `forest` 7200) → через `forest`; связь только у цели
  (`hill → forest`) считается; `goblin_den` → None; `vale → vale` → `[]`.
- `travel` многошаговый: `travel_to=hill` из `vale` → accepted, `location_id == hill`, часы 3600 + 1800 = 5400,
  `flags["visited:forest"]` и `visited:hill` True, два события `location_visited` по порядку, спутник
  (`follows == hero`) в `hill`, `result["path"] == ["forest", "hill"]`, лог по Р8; `pace=fast` — сумма по темпу.
- `travel` соседний — прежние тесты зелёные без правок (`test_travel_takes_time_by_distance` …); `goblin_den` →
  `no_route`, bundle не тронут; `atlantis` → `unknown_location`.
- `state_data["known_locations"]`: `goblin_den.visited=True` и не сосед → `[{"id": "goblin_den", "name": "Логово"}]`;
  `forest.visited=True` (сосед) → не дублируется; ни одной → ключа нет; порядок по id.
- `npc_reasons`: NPC с `trade` в дальней локации → причина `merchant`, в `known_npcs` с `location_id`; `rank_npcs`:
  `merchant` вытесняется раньше `nearby`? — нет: после `nearby` (ранг 3), проверить порядок `[said, key, nearby,
  merchant]`; торговец в локации героя — `here` (неустранимый), как раньше.
- Правила: `narrator_rules.md` содержит `known_locations` и «не описывай приход»; описание `travel_to` в схеме —
  `known_locations`.
- Проверка руками: из таверны «идём к Грете за зельями» → в calls один `advance_time travel_to=apothecary_shop`,
  в ленте строка пути, часы +≈ 15 мин, `/shop` — Грета; «идём в Железный хребет» (не посещён, NPC известен) —
  `travel_to` по `location_id` из `known_npcs`.

П3:
- `inv_section`: надетая кольчуга → Надето (и не в Доспехи); копьё → Оружие; стрелы (`ammo_for`) → Боеприпасы;
  зелье → Расходники; `category=""` и ненадетая `clothing` → Снаряжение; `valuable` → Ценности; `quest` → Сюжетное;
  неизвестный id → Снаряжение.
- `inv_tabs`: пустые вкладки отсутствуют; порядок вкладок по `INV_TABS`; герой protocol_kit (кольчуга, щит, меч надеты;
  копьё, лук в рюкзаке) → первая вкладка «Надето».
- Окно: открыть `/inv` → активна первая вкладка, список — её строки с нумерацией с 1; клавиша вкладки → список
  перезаполнен, подсветка 0, описание первой строки; Enter/e/l/u/d — действия как раньше во второй вкладке; Esc.
- Хвост 127: `ghost_item` первым → `("Копьё", …)` всё равно в строках.
- Проверка руками: `/inv` у героя drunk_dragon — 8 вкладок без пустых, стрелы в «Боеприпасы», ★ только в «Надето».

## Развилки

- **Р1 (131, форма протокола).** (1) поле `until: Literal["none","morning","long_rest","hour"]` + `until_hour: int`
  (-1 = нет; 0–23); «ровно одно из category/travel_to/until». (2) одно поле `until: str` — `morning` | `long_rest`
  | `HH:MM`, разбор в обработчике, ошибка → Invalid `bad_until`. (3) расширить `category` значениями `morning`,
  `long_rest`, `hour_of_day` + поле `hour`; правило «ровно одно из category/travel_to» не меняется.
  Рекомендую (1): перечисления надёжнее при `strict_tools` и у Gemini, «на сколько» и «до когда» не смешаны в одном
  перечне, цена — ≈ +150 токенов статики. Решает проектировщик.
- **Р2 (129, ступень `locations`).** (1) ступень остаётся в `STAGES`/`Candidates` (планировщик общий, тесты
  `test_master_context.py` не трогаем), у рассказчика `locations = []`; ARCHITECTURE E4 — пометка; ТЗ 11 «неактивные
  NPC и локации» — фраза проектировщика, править ли ТЗ — его слово. (2) убрать ступень из `STAGES`, `Candidates`,
  `ContextPlan` и ТЗ 11. Рекомендую (1): минимум под задачу, без правки ТЗ и ≈ 20 тестов планировщика.
- **Р3 (131, час утра).** 06:00 (t623: подъём 06:06; рекомендую) или 07:00. Значение видно игроку.
- **Р4 (131, кто доматывает).** (1) рассказчик двумя вызовами в одном ходу: `advance_time until=long_rest` →
  `rest long` (правило 100 и отказ `rest_repeat` остаются; рекомендую — одно правило промпта, движок без новой
  ветки в `rest`). (2) `rest long` с полем `wait: true` — движок сам доматывает и отдыхает (отменяет часть
  решения 2 plan-fix-zhp3 по 100).
- **Р5 (130, подписи 18 видов — видимый текст).** Предложение: spared — пощада, saved — спасение, helped — помощь,
  gift — подарок, promise — обещание, betrayal — предательство, insult — оскорбление, threat — угроза, theft — кража,
  harm — вред, kin_killed — убийство близкого, romance — роман, deal — сделка, other — другое, friendship — дружба,
  joke — шутка, shared_deed — общее дело, battle — бой плечом к плечу. Проектировщик правит слова.
- **Р6 (128, клавиши вкладок и подсказка).** (1) ←/→ (как у `Tabs` Textual при фокусе; список занят ↑/↓/Enter;
  рекомендую), подсказка `INV_PICK`: «Предмет (←/→ — раздел, Enter — действие по умолчанию, e/l/u/r/d — действие,
  Esc — закрыть):». (2) Tab/Shift+Tab. (3) цифры 1–8 (конфликт с нумерацией строк).
- **Р7 (132, объём фикса).** Что увидит игрок:
  (1) движок + состояние + правило — «иду к Грете» → герой реально в лавке за один ход (путь по карте, часы
  +≈ 15 мин), `/shop` работает; место, которого рассказчик не знает, — отказ «дороги не знаю» (`unsupported_action`).
  Рекомендую: единственный вариант, где визит нельзя сыграть молча и при этом не надо вести героя за руку
  по три хода.
  (2) только правило («цель не рядом — иди по соседям или `unsupported_action`») — игрок увидит либо три хода
  «вышли к Святилищу» / «на площади» / «в лавке», либо отказы; без механики gemini правило обойдёт (как 101).
  (3) правило + `known_locations` без многошагового пути — рассказчик знает id, но движок откажет `no_route`
  на не-соседа → отказы «не дойти» (как 599–600). Не рекомендую.
- **Р8 (132, строка ленты при пути через промежуточные места).** (1) «Путь в «Алхимическая лавка „Медная реторта“»:
  924 с (через Святилище Рассвета, Площадь Верхнего города)» — текущий формат плюс скобка при ≥ 2 переходах;
  рекомендую: игрок видит, что герой прошёл, а не телепортировался. (2) Как сейчас, только цель: «Путь в «…»: 924 с».
  (3) Строка на каждый переход. Единицы времени («с») — как сейчас, не в этом шаге.

## Умолчания (внутреннее)

- Имена: `next_long_rest_s`, `time_until`, `inv_section`, `inv_tabs`, `MEMORY_KIND_TITLES`, `INV_TABS`,
  `TimeConfig.morning_hour`, id `#inv-tabs`; строка `inv_rows` — 4-кортеж `(label, description, actions, section)`.
- `TIME_LOG` для `until` прежний («Время идёт: N с»); `rejected` «отдых уже можно» без report_tag.
- При Р1 = (1): `until_hour` валидируется `ge=-1, le=23`; при Р1 = (2) — разбор `HH:MM` регуляркой, минуты
  допускаются.
- `ref_name` для `creature`/`situation` — как сейчас (id монстра / слаг): вне решения 4; если мешает — беклог.
- `memory_script.py`: при Р2 = (1) — укоротить имена локаций и подобрать `MEMORY_CONTEXT_CAP`.
- 132 (при Р7 = (1)): `route_path` — Дейкстра по `distance_m`, при равной длине — по id; `location_visited` на
  каждый переход (флаги `visited:*`, триггеры прибытия срабатывают и на проходе); `known_locations` — фиксированный
  блок, `{id, name}` без расстояния; причина `merchant` — ранг 3 (после `nearby`); `allowed` при `no_route` — соседи;
  `result["path"]`; `known_locations` в режимах боя не добавляется (как `locations` — только `state_data`
  explore).
- `make mutate` П1: `ai_dm.master.prompt:PromptBuilder.candidates ai_dm.master.prompt:PromptBuilder.state_data
  ai_dm.protocol.handlers.resources:travel ai_dm.rules.time_ops:route_path (или master.relevance:route_path)
  ai_dm.master.relevance:npc_reason_set ai_dm.master.relevance:rank_npcs` — TESTS `tests/unit/master
  tests/unit/protocol`;
  П2: `ai_dm.protocol.handlers.world:change_memory ai_dm.protocol.handlers.knowledge:knowledge_note
  ai_dm.protocol.handlers.resources:rest_redundant ai_dm.protocol.handlers.resources:next_long_rest_s
  ai_dm.protocol.handlers.resources:time_until ai_dm.protocol.handlers.resources:advance_time` — TESTS
  `tests/unit/protocol tests/unit/master`;
  П3: `ai_dm.ui.tui.blocks:inv_rows ai_dm.ui.tui.blocks:inv_section ai_dm.ui.tui.blocks:inv_tabs
  ai_dm.ui.tui.modals:InvModal.on_mount ai_dm.ui.tui.modals:InvModal.on_tabs_tab_activated` — TESTS
  `tests/unit/ui/tui/test_tui_inv.py tests/unit/game/test_inv_actions.py`.

## Риски

1. Статика впритык (запас 313): порог может подняться — штатно, с причиной в шапке.
2. `MEMORY_CONTEXT_CAP` — подбор заново (окно узкое ≈ 50 токенов); сценарий 52 сцены ≈ минуты на прогон.
3. Повтор `until morning` в соседних праздных ходах даст +24 ч: `time_repeated` ловит только `hour`; защита —
   правило «„Время идёт“ в outcomes — сделано» (narrator_rules:130). Если встретится живьём — беклог, не этот шаг.
4. `test_tui_inv.py` — 41 тест на `app.screen.rows`/`#inv-list`; с вкладками `rows` = активная вкладка, хелпер
   `highlight` ходит только внутри вкладки — доеба правит хелперы и тесты, где нужная строка в другой вкладке.
5. Статику трогают П1 (132) и П2 (131) — два замера, ratchet штатный; порог поднимется один раз или дважды, с
   причиной в шапке.
6. 132: проход через промежуточные локации ставит им `visited` и пускает триггеры прибытия (`location_visited`) —
   NPC с триггером «когда герой придёт в X» сработает на проходе; в живом мире таких триггеров на городских
   узлах не видно, но доебе — тест, что события идут по порядку, и риск записать в «Итог», если живьём стрельнёт.
7. 132: рассказчик может по-прежнему сыграть визит текстом (детектора нет) — правило + механика снижают, не
   исключают; повтор живьём — репорт и новый пункт, не переоткрытие 132.
8. 132: `known_locations` растёт с миром (потолок ≈ 1350 токенов на 53 локации) — при мирах > 100 локаций
   пересмотреть (беклог при необходимости).
9. 131 (ревью П2): лог `until` совпадает с `TIME_LOG`; если `until` дал ровно 3600 с, следующий `hour` в ближайшие
   ходы отклонит `time_repeated` — допустимо, час прошёл.

## Находки для беклога (не в шаг)

- `context_cap = 16000` вытесняет 3–5 из 8 `recent_turns` при верной оценке (openai 3,5: 31,5k факт, ходы 612–622;
  gemini: 34,1k/32,3k, t624–t626). Потолок динамики, не калибровка: 129 (1) возвращает точность, не ходы. Последствия
  как в 109 (ложный `xp_repeat`). Варианты: поднять `context_cap` (сторож `STATIC_MAX + cap ≤ window80` — у моделей
  рассказчика окна ≥ 128k, запас есть) или сократить состояние хода. Новый пункт беклога — оркестратор.
- Ступень `locations` планировщика после 129 у рассказчика мертва (при Р2 = (1)) — чистка вместе с ближайшим
  касанием `master/context.py`.
- Дубль локации в живом мире: «Таверна „Пьяный Дракон“» дважды — `tavern_drunken_dragon` (пак) и
  `drunken_dragon_inn` (`origin: ai`, роль world); городские места от роли world привязаны ко второй. Роль world
  не сверяет имя новой локации с существующими — пункт беклога (дедуп по имени при создании); правка живого
  сейва — только с согласия проектировщика и с бэкапом, не в шаге.
- Упоминание NPC по имени (`npc_reason_set`, причина `said`): ищется `npc.name.lower()` целиком — «у матушки Греты»
  не находит «Матушка Грета» (падежи). Низкий приоритет; при касании relevance — хотя бы по фамилии/последнему
  слову имени.

## Предложения архитектора

- BACKLOG 125 (промах кэша OpenAI при смене блока памяти): ЖП4 — 1–2 хода из 21 (601 после перезапуска, 602 смена
  сцены), ≈ +$0,05 на ход. Решение архитектора (не проектировщика): остаётся в беклоге medium, место — при касании
  адаптера OpenAI (сборка `instructions`), не позже Э10б; формулировку ROADMAP «решение итога ЖП4» заменить на
  «решение архитектора 2026-10-21». Переставлять раньше незачем: редкий промах, резерв Фикс ЖП4 и так S+.
- Путь в ROADMAP `config/app_defaults.toml` → `src/ai_dm/config/app_defaults.toml` (свинопас).
- handoff «новых репортов после t612 нет» → устарело (t623) — оркестратор.

## Смета (кабан-тесть, режим 1)

Пересчёт под три партии (план с BACKLOG 132, Р7–Р8). Источник токенов и времени — последний «Итог» цепочки с
расходом: docs/plan-96a.md (П1 172 мин / 42,17 M, П2 114 мин / 11,28 M). Допущения по объёму: П1 (129 + 132, M —
движок пути, состояние, relevance, правило) ≈ 96a П1; П2 (130 + 131) ≈ 0,7 × 96a П1; П3 (128 + 127, TUI) ≈ 96a П2.
Груминг и план (papa-kaban, svinopas) — один раз, в П1. Модели — `model:` из `~/.claude/agents/<роль>.md` на 2026-10-21.
$ — тариф metrics.py от 2026-10-17 (fable — по Opus); у ролей, сменивших модель против 96a (kaban-doeba sonnet → opus,
kaban-svekrov opus → sonnet), $ за M токенов пересчитан ×2 / ×0,5. Живые вызовы API игры — у проектировщика, в смету
не входят (ЖП4: ≈ $0,91 за прогон).

| Партия | Время |
|---|---|
| П1 (129, 132) | ≈ 170 мин (96a П1 — 172 мин) |
| П2 (130, 131) | ≈ 120 мин (0,7 × 96a П1) |
| П3 (128 + 127) | ≈ 115 мин (96a П2 — 114 мин) |

| Роль | Модель | Токены П1 / П2 / П3 | $ П1 / П2 / П3 (тариф metrics.py 2026-10-17) |
|---|---|---|---|
| оркестратор | opus | 16,5 M / 11,5 M / 4,5 M | 5,30 / 3,70 / 2,20 |
| kaban | sonnet | 8,7 M / 6,1 M / 2,7 M | 2,24 / 1,57 / 1,21 |
| kaban-doeba (с мутантами) | opus | 12,4 M / 8,7 M / 3,1 M | 7,40 / 5,18 / 2,10 |
| mama-kaban | opus | 0,7 M / 0,5 M / 0,44 M | 0,65 / 0,46 / 0,51 |
| kaban-svekrov | sonnet | 0,54 M / 0,38 M / 0,41 M | 0,35 / 0,25 / 0,24 |
| papa-kaban | opus | 3,0 M / — / — | 2,40 / — / — |
| svinopas | fable (цены Opus) | 0,32 M / — / — | 0,28 / — / — |
| kaban-test | opus | 0,05 M / 0,04 M / 0,08 M | 0,12 / 0,08 / 0,14 |

Итого: ≈ 405 мин, ≈ 80,6 M токенов, ≈ $36,4 (П1 ≈ $18,7, П2 ≈ $11,2, П3 ≈ $6,4). Расхождение: в плане «модель
кабана и доебы sonnet (ROADMAP)», а `kaban-doeba.md` — `model: opus`; при sonnet у доебы — ≈ $29,1. Слияние П1 + П2
(вариант плана) — минус один круг ревью/cov/полного pytest: ≈ −$3 и ≈ −45 мин, цена — большое ревью.

## Правки по ревью

### П1, круг 1 (mama-kaban ‖ kaban-svekrov, 2026-10-21)

Мама: можно мержить после правки пробела. Свекровь: лишнего нет; к пользователю — семантика «известного» места
(закрыто решением 16), строка «Правила» расходилась с п. 14 (поправлена оркестратором в документе).

Передано кабану (решение оркестратора по замечаниям мамы):
- `prompt.py` `state_data`: `location ={` → `location = {`;
- `route_path`: комментарий «при равенстве по id» не совпадает с кодом — привести комментарий к поведению;
- `route_path`: в комментарии пояснить разницу `[]` (старт = цель) и `None` (нет пути).

Не в П1 (мама): `known_locations` без потолка — оценка ≈ 800–900 токенов принята решением 16; потолок — пункт
беклога после П1 (BACKLOG 138). `MEMORY_CONTEXT_CAP` 2950 — в шапке теста записать проходящий диапазон (доеба).

### П1, круг 2 и проверки (2026-10-22)

Мама: можно мержить; свекровь: чисто. `make cov` — 20257 passed, 1 xfailed, 97,98 %. mutmut по 6 функциям —
31 выживший: на новых строках 5 убиты тестами (доеба sonnet), 6 эквивалентных; 20 на старых строках — BACKLOG 139.

### П2, круг 1 (mama-kaban ‖ kaban-svekrov, 2026-10-22)

Мама: можно мержить, правки необязательные. Свекровь (второй заход, построчно): лишнего нет; к пользователю — два
умолчания папы (закрыты решениями 17, 18). Кабан сам добавил `field_validator` для `until_hour` (ge/le ломали
strict-схему) и переименовал код Invalid в `category_travel_to_or_until` (план, стр. 305, допускает).

Передано кабану (решение оркестратора по замечаниям мамы):
- `requests.py` `AdvanceTime.NEUTRAL` — одной строкой, как у соседних классов;
- `world.py` `change_memory` — `title = MEMORY_KIND_TITLES[...]` один раз до ветвления, в обеих ветках одинаково.

Итог правок (кабан): `title` вынесен; `NEUTRAL` оставлен многострочным — одной строкой 101 знак (E501), оценка мамы
«99» неверна. Затронутые тесты 621 passed, ruff 16 старых, smells 200, dead чисто.

### П2, круг 2 и проверки (2026-10-22)

Мама: можно мержить; свекровь: чисто. `make cov` — 20371 passed, 1 xfailed, 97,99 %. mutmut по 8 функциям — 7 выживших
(новые строки, только текст `message`/`rejected`; коды и причины проверены тестами — эквивалентные по поведению,
доеба sonnet), 12 timeout `rest_redundant`; старых нет. Попутно в BACKLOG 140–145 — разбор репортов 2026-10-22.

В «Риски» (оркестратор, по маме): лог `until` совпадает с `TIME_LOG`, и ровно 3600 с из `until` даёт `time_repeated`
на следующий `hour` — допустимо, час прошёл. Статика: план ждал +220 токенов, вышло +356 вместе с known_locations П1
(свекровь) — в «Итог».

### П3, круг 1 (mama-kaban ‖ kaban-svekrov, 2026-10-22)

- Отступление кабана: `inv_section`/`inv_tabs` вынесены в `inv_sections.py` — принято решением 20 (проектировщик).
- Кабану (мама): названия вкладок в `inv_section` и `SECTIONS` — только из `strings.INV_TABS`, без литералов
  «Снаряжение»/«Надето»; доебе (мама) — тест-инвариант: разделы `SECTIONS` + «Надето» + «Снаряжение» = `INV_TABS`.
- Не правим (мама, мелочь): двойной `fill(0)` при монтировании.
- Свекровь: решение 19 и запись NOTES.md 2026-10-22 — ответы проектировщика в чате («Добавить две строки», «да»);
  BACKLOG 127 закрыт частично (`inv_rows_66`), 26 мутантов `finish_turn` остаются — 127 в done/ не переносить.

### П3, круг 2 и проверки (2026-10-22)

Мама: можно мержить; свекровь: чисто. `make cov` — 20390 passed, 1 failed, 1 xfailed, 97,99 %: упал
`test_commands_both_modes::test_command_answers_in_tui[/inv]` (ждал «Предмет (Enter») — доеба поправил ожидание на
«Предмет (←/→ — раздел», файл 40/40. mutmut по 7 функциям (`inv_sections`, `inv_rows`, `InvModal.*`) — 18 выживших, все
на новых строках: 8 убиты тестами доебы sonnet (`inv_rows_46/49`, `compose_5/7/9/10/25/26/27`, `fill_3`; test_tui_inv.py
68/68), эквивалентные — `inv_rows_17` (None ≡ []), `fill_8/9/10`, `action_tab_3/4/5` (тот же виджет), `action_tab_8`
(шаг только ±1). `inv_sections` — выживших нет.

## Итог

- Закрыты: BACKLOG 128, 129, 130, 131, 132 (П1 bbc9a96, П2 3b4440d, П3 4169140). 127 — частично: хвост `inv_rows_66`
  сделан, 26 мутантов `finish_turn` остаются, пункт в BACKLOG.
- Тесты П3: cov 97,99 %, 20390 passed (1 упавший `/inv` в test_commands_both_modes исправлен); мутанты П3 — 8 убиты,
  остальные эквивалентны.
- Отступление от плана: модуль `ui/tui/inv_sections.py` (решение 20) — smells 201 в blocks.py, нулевой баланс.
- Находки: статика +356 против ожидаемых +220; тест вне модулей партии ловится только `make cov`.
- Отклик оркестратора — ~/projects/semia-kabanov/otkliki/orkestrator/ai-dm/2026-10-22-fix-zhp4.md.

### Расход (кабан-тесть, режим 3, 2026-10-22)

**Источник токенов:** `metrics.py` по
`/Users/vladislavahtamov/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/fe8ac84d-df75-4f7a-bab5-36b58f3f72e7.jsonl`
(с subagents/); **цены:** тариф metrics.py от 2026-10-17, https://platform.claude.com/docs/en/about-claude/pricing — страницу
pricing на 2026-10-22 не сверял (не проверено); fable — по ценам Opus. Время партий — по стартам агентов из metrics.py
и времени коммитов (UTC+5), ночная пауза 01:56–09:29 не считается. По партиям токены скрипт не делит — факт по
ролям за шаг целиком.

| Партия | Смета | Факт |
|---|---|---|
| груминг + план | в П1 | ≈ 81 мин (21:44 → старт кабана П1 23:05) |
| П1 (129, 132) | ≈ 170 мин | ≈ 99 мин (23:05 → bbc9a96 00:44) — смета по 96a П1 завышена: 132 оказался меньше «M» |
| П2 (130, 131) | ≈ 120 мин | ≈ 71 мин (00:44 → 3b4440d 01:55) — меньше кода, чем 0,7 × 96a П1 |
| П3 (128 + 127) | ≈ 115 мин | ≈ 68 мин (09:29 → 4169140 10:37) — плюс круг на упавший тест `/inv` и мутанты |
| итого | ≈ 405 мин, 80,6 M, ≈ $36,4 | ≈ 319 мин активных (шаг 746 мин с паузой), 58,5 M, $31,74 |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| оркестратор | opus | 23,40 M | 9,77 (на момент подсчёта 10:47) |
| papa-kaban (план + ROADMAP, запуск возобновлялся до 10:43) | fable (цены Opus) | 8,97 M | 10,47 |
| kaban-doeba (6 запусков, мутанты на sonnet) | opus + sonnet | 6,98 M | 4,00 |
| kaban (3 запуска) | sonnet | 5,97 M | 1,91 |
| general-purpose (разбор репортов, вопросы — вне сметы) | sonnet | 9,73 M | 1,67 |
| kaban-svekrov (4 запуска) | opus (по журналу; в смете sonnet по файлу агента) | 1,28 M | 1,42 |
| mama-kaban (3 запуска) | opus | 0,90 M | 1,04 |
| svinopas | opus (по журналу; в смете fable) | 0,90 M | 0,56 |
| kaban-test | opus | 0,36 M | 0,91 (на момент подсчёта 10:47) |

**Итого:** смета ≈ 405 мин / 80,6 M / ≈ $36,4 → факт ≈ 319 мин / 58,5 M / $31,74. Отклонения от сметы: доеба 7,0 M
вместо 24,2 M (база 96a завышена); папа 9,0 M и $10,47 вместо 3,0 M и $2,40 — самая дорогая роль, контекст до 326k
(ROADMAP линией в том же запуске); general-purpose $1,67 сметой не учтён; свекровь и свинопас шли на opus, а не на
моделях из файлов агентов. Орк и тесть — неполные, сессия ещё идёт; с итоговыми цифрами не сверять.

Разбор — кабан Декарта.
