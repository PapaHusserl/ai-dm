# План партии «К0-фикс» (papa-kaban, 2026-10-11; на аппрув проектировщика)

Задача: BACKLOG 38 а–г + `safety_settings` Gemini (R5, решение 4) + BACKLOG 39 (пол и местоимения; добавлен проектировщиком 2026-10-12, шаг 7). Размер: «фикс» → S (см. оценку в шаге 7), сейв v9, миграций нет.
Контекст: docs/plan-k0.md, docs/plan-roadmap-r5.md («К0-фикс — #8»), репорты
`saves/drunk_dragon-00000001/issues/*-t50-refusal, -t53, -t76, -t94`. Груминга нет — решения записаны.

Что показал код (сверка перед планом):
- t94: модель прислала `player_action.improvise = {effect: "столкнуть дозорного с крыши во двор", target: cultist_guard_2,
  zone: "roof", skill: athletics, category: medium}` — свободная строка в `effect` (`protocol/requests.py:87`) и zone =
  зона самой цели. Классификация (`combat_classify`) принимает всё без проверки (`protocol/handlers/combat.py
  player_action`), а отказ приходит только позже из движка (`combat/actions/improvise.py check_request` →
  `Rejected("unknown_effect"|"zone_not_adjacent")`), когда модель уже не отвечает — в лог боя строкой
  «импровизация невозможна (…)» (`game/controllers.py PlayerController.act`). Схема инструмента — Pydantic
  `Literal` → `enum` (`protocol/schema.py strictify`), как у `SkillOrNone`; `player_action` в `combat_classify` strict.
- t76: в правилах «Выбор игроку» (`narrator_rules.md:100–102`) — «когда уместно»; в репорте один `offer_choices`
  (в списке инструментов), вызова нет.
- t53: в `scene_npcs` репорта Эдрин **без** `follows` (спутники — Бран, Йорген, Лира с `follows: hero`); он просто
  живой NPC в локации героя. Значит `follows: "none"` ему нечего снимать, а `location_id` у нарраторского
  `NpcUpdate` нет (есть только у `WorldNpcUpdate`, `requests.py:563`, обработчик `handlers/offscreen.py npc_update`).
  Отдельной локации «коридор» в мире нет. Вывод: существующего `npc_update` для t53 **не хватает**, но и новое поле
  не помогло бы — нужен хинт о смысле `scene_npcs` (см. шаг 3 и Q4).
- F2: `app.tcss:41` `.wide #side { display: block }` всегда, `action_toggle_side` (`ui/tui/app.py:131`) переключает
  только `open` — в широком окне эффекта нет. Все существующие тесты с `press("f2")` — узкие (100×40 / 80×24).
- Gemini: `gemini_adapter.py build_config` не передаёт `safety_settings`. SDK google-genai 2.28.0:
  `GenerateContentConfig.safety_settings` есть, у `CreateCachedContentConfig` — нет (в кэш не входит);
  `HarmBlockThreshold`: BLOCK_NONE («не блокировать ни при какой вероятности») и OFF («выключить фильтр»);
  текстовые категории: HARASSMENT, HATE_SPEECH, SEXUALLY_EXPLICIT, DANGEROUS_CONTENT (CIVIC_INTEGRITY — deprecated,
  JAILBREAK и IMAGE_* не трогаем). Поддержку именно моделью gemini-3.8-flash офлайн не проверить (риск Р4).
- Был ли t50 `PROHIBITED_CONTENT` — **установить нельзя**: журнал (`llm/journal.py`) пишет только нормализованный
  `stop_reason: refusal`; в записи `content: []`, output 127 токенов (мышление), сырого `finish_reason`/`block_reason`
  нет. Пункт д остаётся в К0-фикс (решение 4), а чтобы в Р2 решать по данным — шаг 5б (Q7).
- `[llm] refusal_fallback` в конфиге — только Anthropic (серверный фолбэк), к Gemini отношения не имеет.

## Реализация (kaban)

### 1. ImproviseSpec.effect — перечисление + Invalid на классификации (38 а)
1.1. `src/ai_dm/state/combat.py`: рядом с `Intent` — `ImproviseEffect = Literal["advantage", "prone", "extra_damage",
   "push", "disarm"]`. `src/ai_dm/combat/actions/improvise.py`: `EFFECTS = get_args(ImproviseEffect)` (значение и порядок
   те же; `NEEDS_TARGET`, `EFFECT_WORDS`, `APPLY` не меняются). (Q1)
1.2. `src/ai_dm/protocol/requests.py`: `ImproviseEffectOrNone = Literal[(*get_args(ImproviseEffect), "none")]` рядом с
   `SkillOrNone`; `ImproviseSpec.effect: ImproviseEffectOrNone = Field("none", description=…)` — описание
   перечисляет эффекты: advantage — преимущество на следующую атаку героя; prone — цель сбита с ног (нужен target);
   extra_damage — доп. урон цели (target); push — цель отброшена в соседнюю зону (target и zone — зона, соседняя с
   зоной цели, не её собственная); disarm — выбить оружие (target); none — импровизации нет. В `NEUTRAL` добавить
   `"effect": "none"`. В `PlayerAction.cut_improvise`: если skill и category заданы, а `spec.effect is None` →
   `ValueError("improvise: effect обязателен (advantage, prone, extra_damage, push, disarm)")`. Pydantic-ошибка на
   чужое значение уходит модели как `Invalid(invalid_request)` через `MasterSession.run_call` — набор она видит и в
   схеме (enum), и в тексте ошибки.
1.3. `src/ai_dm/combat/actions/improvise.py`: вынести из `check_request` чистую проверку по состоянию боя —
   `spec_problem(state, effect, target, zone) -> str | None` (коды `unknown_effect`, `target_required`,
   `zone_required`, `zone_not_adjacent` по `state.participants`/`state.zones`); `check_request` = `not_a_hero`,
   `not_available` + `spec_problem(engine.state, …)`. Поведение движка и коды не меняются (тест
   `test_unknown_effect_is_rejected_without_a_roll` остаётся: движок получает строку напрямую).
1.4. `src/ai_dm/protocol/handlers/combat.py player_action`: после проверок `no_active_combat`/`unknown_step`, если
   `request.improvise is not None` — `problem = improvise_problem(state, request.improvise)`; `Invalid` вернуть до
   `result`. Новый маленький помощник `improvise_problem(state, spec)` + словарь подсказок `IMPROVISE_HINTS` в стиле
   `SETUP_HINTS`: код = код движка; сообщения:
   - `target_required`: «эффект {effect} требует target — ref врага: {refs врагов из state.participants}»;
   - `zone_required`: «push требует zone — зона, соседняя с зоной цели {target} ({zone цели}): {adjacent}»;
   - `zone_not_adjacent`: «зона {zone!r} не подходит для push: цель {target} стоит в зоне {zone цели}{, это её
     собственная зона — если zone == зона цели}; нужна соседняя зона: {adjacent}»;
   - `unknown_effect`: «нет эффекта {effect!r}; допустимые: advantage, prone, extra_damage, push, disarm» (защита: со
     схемой-enum практически недостижимо).
   Лог «импровизация невозможна (…)» в `PlayerController.act` остаётся второй линией. (Q2)
1.5. `src/ai_dm/master/prompts/narrator_rules.md:36` (режим combat_classify), после «импровизация — проверка навыка
   ради эффекта вроде толчка или подножки»: «Поле effect — только одно из: advantage, prone, extra_damage, push,
   disarm; описание эффекта своими словами движок не принимает. Сбросить, столкнуть, отбросить — push: zone — зона,
   куда цель отлетает, соседняя с её нынешней (не её собственная). Чего в наборе нет — в unsupported». Имена эффектов
   писать без обратных кавычек (иначе `test_rules_mention_only_known_tools` сочтёт `extra_damage` инструментом) либо
   добавить их в `fields` этого теста — на выбор kaban-doeba.
1.6. `tests/unit/game/test_game_controllers.py:566` (`effect="bogus"`) теперь не проходит схему: заменить на спец,
   который проходит схему, но отклоняется движком (например `effect="push"`, `target="g1"`, `zone` = зона самого g1 →
   `zone_not_adjacent`) — смысл теста (ход остаётся открытым после отказа) сохраняется.

### 2. Обязательный offer_choices после вопроса/развилки (38 б)
2.1. `narrator_rules.md`, раздел «## Выбор игроку» (строки 100–102) целиком заменить: «Если ход кончается вопросом к
   игроку, развилкой или ожиданием его решения (куда идти, что ответить, кого выбрать), `offer_choices` обязателен:
   2–4 коротких варианта, различных по смыслу. Вопрос в тексте без вызова `offer_choices` — ошибка: игрок не увидит
   вариантов. Варианты не нужны, только когда сцена идёт дальше сама и выбора у игрока нет; в бою список действий даёт
   движок.» Слова «когда уместно» убрать. Код не трогать (Q3).

### 3. Спутник остался / NPC не в сцене (38 в)
3.1. `narrator_rules.md:44`, после «…одного текста мало.» добавить: «`scene_npcs` — живые NPC в локации героя; с
   `follows` — спутники, они всегда рядом с героем. Остальные находятся в локации, но не обязательно рядом: если по
   твоему рассказу NPC остался в другом месте (коридор, соседняя комната, лагерь), он там и остаётся — не вводи его в
   сцену, пока герой к нему не вернётся или он не придёт сам по сюжету. Спутник, который остался или ушёл, — в том же
   ходу `npc_update` с `follows: "none"`; присоединился снова — `follows: "hero"`.» Код не трогать (Q4; вариант с
   `location_id` у нарраторского `npc_update` — описан в Q4б, по умолчанию не делаем).

### 4. F2 в широком окне (38 г)
4.1. `src/ai_dm/ui/tui/app.tcss`: после `.wide #side { … }` добавить `.wide #side.closed { display: none; }`
   (специфичность выше `.wide #side`, `#left` — `1fr`, займёт ширину сам).
4.2. `src/ai_dm/ui/tui/app.py AiDmApp.action_toggle_side`: `side = self.query_one("#side")`; в широком режиме
   (`self.has_class("wide")`) — `side.toggle_class("closed")`, иначе — `side.toggle_class("open")` (как сейчас).
4.3. `AiDmApp.apply_width`: при смене режима (значение `wide` до/после `set_class` различается) —
   `side.remove_class("open", "closed")`: после ресайза панель снова «по ширине», как ждут
   `test_resize_from_*` (Q8). `strings.KEY_SIDE` («Панель героя») не меняется.

### 5. safety_settings Gemini (38 ж, минимум; решение 4)
5.1. `src/ai_dm/config/app.py LlmConfig`: `gemini_safety: Literal["default", "block_none", "off"] = "block_none"`;
   `src/ai_dm/config/app_defaults.toml [llm]`: `gemini_safety = "block_none"` с комментарием (только Gemini; `default`
   — не передавать `safety_settings`, если API модели их отвергнет). (Q5, Q6)
5.2. `src/ai_dm/llm/gemini_adapter.py`: константа `SAFETY_CATEGORIES = ("HARM_CATEGORY_HARASSMENT",
   "HARM_CATEGORY_HATE_SPEECH", "HARM_CATEGORY_SEXUALLY_EXPLICIT", "HARM_CATEGORY_DANGEROUS_CONTENT")`; метод
   `GeminiAdapter.safety_settings()` → `None` при `default`, иначе
   `[sdk.SafetySetting(category=name, threshold="BLOCK_NONE"|"OFF") for name in SAFETY_CATEGORIES]` (строки: enum
   SDK регистронезависимый, фейковому SDK тестов проще). В `build_config` — в базовые `fields` (обе ветки: с кэшем и
   без; в `CreateCachedContentConfig` поля нет, `cache_key` не трогать). Anthropic/мок не меняются.
5.3. (Q7) Сырой повод отказа в журнал и в сообщение игроку: `src/ai_dm/llm/types.py ChatResponse.stop_detail: str |
   None = None`; `gemini_adapter.py stop_reason` при refusal/other отдаёт ещё имя `finish_reason`/`block_reason`
   (например «SAFETY», «PROHIBITED_CONTENT»), `parse_response` кладёт в `stop_detail`; `master/session.py:261`
   `TurnFailed("refusal", f"Модель отказалась отвечать ({detail}).")` при наличии detail;
   `reports/markdown.py:70` — «stop_reason: refusal (PROHIBITED_CONTENT)». В `calls.jsonl` попадает само через
   `response.model_dump`. Anthropic — `None`.

### 6. Docs
`docs/BACKLOG.md` п.38: а–г сделаны, ж — «safety_settings в К0-фикс, повтор/фолбэк — Р2»; `docs/plan-k0.md`
— ссылка на партию; в чек-лист живого прогона фикса (checklist-k0-fix-live.md, не коммитить): сцена с толчком
(push в зону цели и в соседнюю), ход с вопросом без вариантов, «оставить NPC в коридоре» и перейти в другую комнату,
F2 в окне ≥120 колонок, первый ход на Gemini (ошибок 400 от `safety_settings` нет), по возможности сцена убийства на
grim — отказ или нет, и что в репорте в `stop_detail`.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.protocol.requests:PlayerAction.cut_improvise` — TESTS tests/unit/protocol
- `ai_dm.combat.actions.improvise:spec_problem ai_dm.combat.actions.improvise:check_request` — TESTS
  tests/unit/combat/test_improvise.py tests/unit/game/test_game_controllers.py
- `ai_dm.protocol.handlers.combat:improvise_problem ai_dm.protocol.handlers.combat:player_action` — TESTS
  tests/unit/protocol
- `ai_dm.ui.tui.app:AiDmApp.action_toggle_side ai_dm.ui.tui.app:AiDmApp.apply_width` — TESTS tests/unit/ui/tui/test_tui_layout.py
- `ai_dm.llm.gemini_adapter:GeminiAdapter.safety_settings ai_dm.llm.gemini_adapter:GeminiAdapter.build_config
  ai_dm.llm.gemini_adapter:GeminiAdapter.stop_reason ai_dm.llm.gemini_adapter:GeminiAdapter.parse_response` — TESTS
  tests/unit/llm
- `ai_dm.master.session:MasterSession.run` (одна строка refusal) — TESTS tests/unit/master/test_master_session_loop.py
Правила narrator_rules.md мутациями не покрываются — тесты фраз.

## Тесты (kaban-doeba, TDD)
п.1 — tests/unit/protocol/test_requests.py, test_parley_request.py, test_schema.py, test_apply_combat.py
(`protocol_kit`: зоны door–hall–balcony, g1/g2 в hall, герой в door):
- `ImproviseSpec(effect="столкнуть…")` → ValidationError; `effect` отсутствует/`"none"` при заданных skill+category →
  ValidationError с «effect обязателен»; все пять эффектов проходят; `skill=category=effect="none"` → `improvise is None`.
- схема `player_action` в `combat_classify`: `properties.improvise.properties.effect.enum` == 5 эффектов + "none";
  `test_no_empty_string_in_any_enum` зелёный; strict не сломан (`test_real_build_config_for_every_tool_set`).
- `player_action` в бою: `improvise push target=g1 zone=hall` (зона самой цели) → `Invalid(code="zone_not_adjacent")`,
  в message есть «собственная» и «balcony»/«door» (соседи hall) — и состояние не изменилось (`dump(ctx)` до/после);
  `push zone=""` → `zone_required` с перечнем соседей; `prone` без target → `target_required` с «g1, g2»; `push
  target=g1 zone=door` → accepted, `result["improvise"]["effect"] == "push"`; `advantage` без target → accepted;
  `player_action` без improvise — как раньше (steps, unsupported, missing-mechanic).
- tests/unit/combat/test_improvise.py: `spec_problem(state, …)` напрямую — те же четыре кода и `None`; `check_request`
  по-прежнему `not_a_hero`/`not_available`; существующие тесты движка зелёные без правок.
- tests/unit/game/test_game_controllers.py: `test_text_rejected_improvise_keeps_turn_open` на валидном по схеме, но
  отклонённом движком спеке (п.1.6).
- tests/unit/master/test_master_rules.py: в правилах есть «advantage, prone, extra_damage, push, disarm» и «соседняя»
  рядом с «push»; `test_rules_mention_only_known_tools` зелёный.
п.2 — test_master_rules.py: секция «## Выбор игроку» (по образцу `tone_section`) содержит «обязателен» и «вопрос»
и не содержит «когда уместно»; `offer_choices` упомянут в секции.
п.3 — test_master_rules.py: в тексте есть «scene_npcs» рядом с «не вводи» (или «остался») и `follows: "none"`;
`test_rules_say_to_mark_followers_by_npc_update` зелёный. Prompt-тесты (`test_master_prompt.py` scene_npcs) не меняются.
п.4 — tests/unit/ui/tui/test_tui_layout.py: при (140, 40) `#side` виден → `press("f2")` → скрыт (`tui.shown` False),
`#feed.region.width` вырос → `f2` снова → виден; при (100, 40) существующий `test_f2_shows_side_panel_in_narrow_terminal`
без изменений; скрыть F2 в широком → ресайз до (100, 40) → панель скрыта (узкий авто) и класс `closed` снят → ресайз
обратно в (140, 40) → панель видна; `test_resize_from_*` зелёные. Проверить, что тесты с `press("f2")` в
test_tui_combat_menu.py (строки ~561/583) узкие — иначе поправить размер.
п.5 — tests/unit/llm/test_llm_gemini_adapter.py (в `FAKE_SDK` добавить `SafetySetting(Rec)`): `sent()["config"].
safety_settings` — 4 записи, категории ровно `SAFETY_CATEGORIES`, threshold `BLOCK_NONE`; при `gemini_safety="off"` —
`OFF`; при `"default"` — атрибута нет/None; с кэшем (test_llm_gemini_cache.py: ветка `cached_content`) safety_settings
тоже переданы, а в `CreateCachedContentConfig` их нет; реальные типы: `build_config` для каждого `MODE_TOOLS` даёт
`types.GenerateContentConfig` с `safety_settings[0].threshold == types.HarmBlockThreshold.BLOCK_NONE`; конфиг:
дефолт `block_none`, чужое значение → ValidationError. п.5.3: `finish_reason=SAFETY` → `stop_reason="refusal"`,
`stop_detail="SAFETY"`; `PROHIBITED_CONTENT` → `stop_detail="PROHIBITED_CONTENT"`; блок промпта (`prompt_feedback.
block_reason`) → detail = имя причины; STOP/tool_use → `stop_detail is None`; Anthropic-адаптер — `None`; журнал
(`test_llm_journal.py`) пишет `stop_detail` в `response`; replay старых записей без поля (`test_llm_replay.py`,
tests/fixtures) — зелёный; session: refusal с detail → `TurnFailed.args[0]` содержит «(SAFETY)»; `reports/markdown`
печатает «refusal (SAFETY)».
Общее — в конце партии: `uv run pytest -q`, `make cov` (≥94 %), `make smells` (≤206 — сейчас 206/206, запаса нет),
`make dead`, `uv run ruff check src tests`.

## Риски / на что обратить внимание
- Схема `player_action` меняется → sha `tools` режима `combat_classify` другой → кэш Gemini пересоздастся один раз
  (копейки). Журналы с прозой в `effect` (t94) через `--replay` не воспроизведутся — такие есть только в `issues`,
  в tests/fixtures и tests/golden вызовов `improvise` нет (проверено grep).
- `make smells` 206/206: новые помощники (`spec_problem`, `improvise_problem`, `safety_settings`) держать короткими,
  подсказки — словарём; при превышении лимита — сначала упростить, поднимать лимит только с согласия пользователя.
- `safety_settings`: если API gemini-3.8-flash отвергнет категорию/порог (400) — `translate_error` → `LlmFatal` на
  каждом вызове. Поэтому ручка `gemini_safety` (п.5.1) и первый ход живого прогона — проверка. `OFF` на новых моделях
  поддерживается не всегда — по умолчанию `BLOCK_NONE` (решение 4). `PROHIBITED_CONTENT` ничем не снимается — это
  известно (решение 4), Р2 добавляет повтор/фолбэк.
- Пп.2–3 — только правила: проверяются живым прогоном, тесты фраз лишь фиксируют текст. Если в прогоне вопрос без
  вариантов повторится — вариант Q3б (код) в BACKLOG.
- t53 был отчасти следствием памяти: в `meta.context` репорта t50 `dropped: turns 42, 43` — окно `recent_turns`
  резалось по лимиту контекста (Р1 «Память боя»), правило п.3 это не лечит, только снижает частоту.
- `ChatResponse` — `extra="forbid"`: поле `stop_detail` добавляется с дефолтом `None`, старые журналы читаются;
  дампы в golden-тестах (если сравнивают `model_dump`) получат новый ключ — kaban-doeba сверит.

## Открытые вопросы
- **Q1 (а) Где объявить набор эффектов:** (а) **рекомендация** — `Literal ImproviseEffect` в `state/combat.py` рядом с
  `Intent`, `EFFECTS = get_args(…)` в improvise.py (protocol уже импортирует `state.combat`); (б) импортировать `EFFECTS`
  из `combat.actions.improvise` в `requests.py` (цикла нет, но protocol начинает зависеть от действий боя).
- **Q2 (а) Проверка target/zone на классификации:** (а) **рекомендация** — `Invalid` с подсказкой в `player_action`
  (модель исправляет в том же ходу; лог движка остаётся второй линией); (б) только enum в схеме, target/zone — как
  сейчас (лог боя, модель не узнаёт).
- **Q3 (б) Контроль `offer_choices` кодом** (рассказ кончается «?» без `offer_choices` → подсказка модели, ещё один
  вызов ≈ $0,01): (а) **рекомендация** — только правило (R5: «38 б/в — промпт-правила»), код — если прогон покажет
  повтор; (б) правило + код сразу.
- **Q4 (в) Как чинить t53:** (а) **рекомендация** — правило о смысле `scene_npcs` + `follows: "none"` (п.3), кода нет;
  (б) дополнительно `location_id` в нарраторском `npc_update` (поле в `NpcUpdateBase`, общая проверка с
  `offscreen.npc_update`, обработчик в `handlers/world.py`: `unknown_location`/`npc_not_alive`, снятие `follows` при
  переносе) — даёт рычаг «NPC ушёл в другую локацию», но t53 (коридор без своей локации) не решает; (в) оба.
- **Q5 (д) Порог:** (а) **рекомендация** — `BLOCK_NONE` (решение 4; принимается всеми моделями); (б) `OFF` («выключить
  фильтр», новее, но поддержка моделью не гарантирована); (в) `BLOCK_ONLY_HIGH`.
- **Q6 (д) Ручка `[llm] gemini_safety`:** (а) **рекомендация** — да, дефолт `block_none`, `default` = не передавать
  (откат без кода, если API откажет); (б) захардкодить в адаптере.
- **Q7 (д) `stop_detail` — сырой повод отказа в журнал/репорт/сообщение игроку (п.5.3):** (а) **рекомендация** — да, в
  К0-фикс (иначе Р2 решает вслепую, как сейчас с t50); (б) отложить в Р2; (в) не делать.
- **Q8 (г) Ресайз сбрасывает ручное F2:** (а) **рекомендация** — да (панель снова «по ширине», тесты `test_resize_*`
  без правок); (б) помнить выбор пользователя до следующего F2.

## 7. Пол и местоимения NPC и героя (BACKLOG 39; добавлено 2026-10-12)

Что показал код:
- Пола нет ни в `state/world.py NPC`, ни в `HeroState`/`CharacterChoices` (`rules/builder.py:46`), ни в запросах
  `NpcCreate`/`NpcUpdateBase`/`HeroSheetRequest`/`PackNpc` (`protocol/requests.py`), ни в промпте: `scene_npcs` —
  `id, name, attitude, follows, merchant`; `known_npcs` — `id, name, location_id, key`; герой — `name, hp, …`
  (`master/prompt.py:347–390`); роль world — `id, name, location_id, key, attitude` (`master/world.py:91`).
- `npcs.yaml` пака грузится **прямо в модель `NPC`** (`campaign/loader.py:36`), готовые герои `heroes/*.yaml` — в
  `CharacterChoices` (`campaign/models.py`, `loader.py:286`): новое поле с дефолтом даёт пак и сейв без миграции
  (`extra="forbid"` запрещает лишние ключи, отсутствующие — берут дефолт). Схема сейва остаётся 9.
- Все три пути создания героя сходятся в `CharacterChoices` → `HeroState` (`rules/builder.py:503`): на лету —
  `protocol/handlers/hero.py:63`; пошагово — `game/hero_steps.py:567` (шаги `STEPS`, `Draft`); пресеты — yaml.
- NPC в паках: drunk_dragon 47 (31 именованных), dusk_academy 6 (все именованные, романтический пак), vale 2,
  campaigns/test 11 (3), tests/fixtures/packs/mini; готовые герои: vale arn/grey/liel, drunk_dragon grey.
- `/sheet` (`game/sheet_text.py:212`): «Грей — человек, следопыт 3 ур.»; golden `tests/golden/k0_sheet_v4_dragon.txt`
  и `k0_sheet_data_v4_dragon.json` сняты с мира v4 без пола — не меняются, если пол выводится только когда задан.

### Реализация (kaban)
7.1. Тип: `src/ai_dm/state/gender.py` — `Gender = Literal["male", "female", "other"]`, `GENDER_WORDS = {"male":
   "мужской", "female": "женский", "other": "другой"}` (Q9). `requests.py`: `GenderOrNone = Literal[(*get_args(Gender),
   "none")]` рядом с `SkillOrNone`.
7.2. Состояние: `NPC.gender: Gender | None = None`, `NPC.pronouns: str = ""` (`state/world.py`, после `species_id`);
   `CharacterChoices.gender: Gender | None = None`, `pronouns: str = ""` (`rules/builder.py`); `HeroState.gender`,
   `pronouns` — те же дефолты; `build_character` (`builder.py:503`) копирует их из `choices`, как `name`.
7.3. Протокол: `NpcCreate` и `PackNpc` — `gender: GenderOrNone = "none"`, `pronouns: str = ""` (описание: «пол NPC:
   male, female, other; none — не известен»; «местоимения/обращение, если отличаются от пола или важны: пусто = нет»),
   в `NEUTRAL`. `NpcUpdateBase` — те же два поля («none/пусто = не менять»); `update_problem` (world.py:204) и
   `offscreen.npc_update:110` — `empty_update` учитывает `gender`/`pronouns`; новый маленький `change_identity(npc,
   request, decision)` в `handlers/world.py` (ставит поля, лог «{name}: пол {слово}»), вызывается из обоих
   `npc_update`. `npc_create` (world.py:63) и `HeroSheetRequest` (+ `handlers/hero.py:63` → `choices`) — поля
   прокидываются. Импорт пака: `PackNpc` → `npcs.yaml` через `importer.py` (model_dump → yaml) — автоматически.
7.4. Пошаговое создание (`game/hero_steps.py`): `Draft.gender: str = ""`, `Draft.pronouns: str = ""`; после шага `name` —
   `StepDef("gender", "gender", "pick", "Пол героя", options=options_gender)` с вариантами male/female/other +
   «не указывать» (значение "" → None), и `StepDef("pronouns", "pronouns", "text", "Местоимения/обращение (пусто —
   по полу)", put=put_pronouns)` — пустой ввод допустим (Q11; проверить, что `HeroWizard`/`hero_session` пропускают
   пустую строку в `put`). Сборка `HeroSheet` (hero_steps.py:567) — поля в `CharacterChoices`.
7.5. Промпт (`master/prompt.py`): в `scene_npcs` и `known_npcs` — `"gender"` и `"pronouns"` только если заданы (как
   `follows`); в `hero_data` — `"gender"`, `"pronouns"` (None/"" — ключ не класть, чтобы golden и тесты ключей не
   поплыли); `master/world.py:91` — `gender` у NPC. Summarizer не трогать.
7.6. Правила: `narrator_rules.md:44` — «У NPC и героя может быть `gender` (male/female/other) и `pronouns`: пол, род
   глаголов, обращения и романтика — по ним, не по имени. Если у NPC в сцене пола нет (старый мир, NPC без пола) —
   определи его по роли и описанию при первом появлении и в том же ходу зафиксируй `npc_update` с `gender`; новых NPC
   создавай сразу с полом.» `hero_sheet_rules.md:6` после `name`: «gender — по описанию игрока; не ясно — по имени;
   pronouns — только если игрок их назвал». `import_rules.md:14` — «gender — из выжимки, none, если не ясно».
   `world_rules.md:7` — `npc_create` с полом. Раздел «Тон»: романтика опирается на `gender`/`pronouns` героя и NPC.
7.7. `/sheet` (`game/sheet_text.py:212`): при заданном поле — «Грей — человек (муж.), следопыт 3 ур.», с `pronouns` —
   «…, местоимения: они»; не задано — строка прежняя (golden без правок). (Q12)
7.8. Данные: проставить `gender` именованным NPC в `campaigns/drunk_dragon/npcs.yaml` (31), `dusk_academy` (6, обязательно —
   романтический пак), `vale` (2), `campaigns/test` (3) и готовым героям (4 yaml); безымянным — не ставить (мастер
   определит по сцене). По именам/мотивам — отдельный шаг данных (dyadya-kaban или kaban), сверка пользователем на
   прогоне. (Q10)
7.9. Docs: BACKLOG 39 → сделано; чек-лист прогона: старый мир (29a049dc) — у NPC без пола мастер вызывает
   `npc_update gender` при появлении; новый мир dusk_academy — пол из пака в контексте; создание героя всеми тремя
   путями — пол в `/sheet`; `meta/hero_sheet.json` старого героя грузится.

### Функции для mutmut (шаг 7)
`ai_dm.protocol.handlers.world:npc_create ai_dm.protocol.handlers.world:npc_update
ai_dm.protocol.handlers.world:update_problem ai_dm.protocol.handlers.world:change_identity` — TESTS tests/unit/protocol;
`ai_dm.protocol.handlers.offscreen:npc_update` — TESTS tests/unit/protocol; функция `handlers/hero.py:63`
(сборка `CharacterChoices` из `HeroSheetRequest`) — TESTS tests/unit/protocol tests/unit/game;
`ai_dm.rules.builder:build_character` (функция у стр. 503) — TESTS tests/unit/rules; `ai_dm.game.hero_steps:options_gender
ai_dm.game.hero_steps:put_pronouns` + функция сборки `HeroSheet` (стр. 567) — TESTS tests/unit/game tests/unit/ui;
`ai_dm.master.prompt:PromptBuilder.state_data` + метод с `hero_data` (стр. 385) — TESTS tests/unit/master;
`ai_dm.master.world:*` метод со списком npcs (стр. 85) — TESTS tests/unit/master; `ai_dm.game.sheet_text:*` функция
строки 212 — TESTS tests/unit/game. Точные имена методов kaban уточнит по `git diff` (правило 7 handoff).

### Тесты (kaban-doeba)
- Модели: `NPC()`/`HeroState()`/`CharacterChoices()` без полей → `gender is None`, `pronouns == ""`; `gender="x"` →
  ValidationError; старый `world.json`/`hero.json` v9 (tests/fixtures/saves) грузится без миграции и без предупреждения;
  `meta/hero_sheet.json` без полей грузится.
- Паки: `load_pack` на mini с `gender: female` у NPC → в `NPC`; без поля → None; у готового героя `choices.gender` →
  `HeroState.gender` через `build_world`; все три пака грузятся после правки данных (существующий тест загрузки паков);
  import пака: `PackNpc(gender="male")` → в записанном `npcs.yaml` ключ `gender`.
- Протокол/схемы: `npc_create` с `gender`/`pronouns` → поля у NPC и в логе; `npc_update` только с `gender` →
  accepted (не `empty_update`), поле обновлено; `pronouns=""` — не меняет; world-роль `npc_update` с `gender` и
  `then_ref` → accepted; `hero_sheet` с `gender` → `HeroSheet.choices.gender`; схемы `npc_create`/`npc_update`/
  `hero_sheet`/`pack` содержат enum `male, female, other, none` (`test_no_empty_string_in_any_enum`,
  `test_real_build_config_for_every_tool_set` зелёные).
- Пошагово: шаг `gender` после `name`, 4 варианта, «не указывать» → None; `pronouns` пустой → ""; итоговый лист несёт
  поля; `HeroWizard` и `--simple` проходят новые шаги (существующие сценарии создания — с добавленными ответами).
- Промпт: NPC с полом → в `scene_npcs`/`known_npcs` ключ `gender` (и `pronouns`, если есть); без пола — ключа нет
  (существующие тесты равенства словарей зелёные); `hero_data["gender"]` при заданном; world-промпт — `gender`.
- Правила: фразы «gender», «pronouns», «по роли» в narrator_rules.md; «gender» в hero_sheet_rules.md и import_rules.md;
  `test_rules_mention_only_known_tools` зелёный.
- `/sheet`: герой с `gender="male"` → «(муж.)» в первой строке; без пола — строка прежняя; golden К0 без правок.

### Риски (шаг 7)
- Меняются схемы `npc_create`, `npc_update` (explore и world), `hero_sheet`, `pack` → sha `tools` четырёх режимов →
  кэши Gemini пересоздаются один раз; strict-грамматика Anthropic: `npc_create`/`npc_update` в explore и так NON_STRICT,
  `hero_sheet` strict — поле маленькое, но проверить `test_real_build_config_for_every_tool_set`.
- Replay старых журналов: Pydantic-разбор вызовов без новых полей берёт дефолты — `--replay` не ломается; репорты
  тоже. Golden К0 не меняются при условии «выводить только когда задано».
- `make smells` 206/206: `npc_update`/`update_problem` и так ветвистые — новое только через `change_identity` и
  расширение условия `empty_update`; при превышении — упрощать, не поднимать лимит без согласия.
- Данные паков (7.8) — ручная работа по 42 именованным NPC; ошибки пола у NPC заметны игроку сразу — сверка
  пользователем на прогоне; dusk_academy — приоритет.
- Контекст: +1–2 ключа на NPC в `scene_npcs`/`known_npcs` — десятки токенов, на цену хода не влияет.
- Пошаговый визард: если `text`-шаги не принимают пустую строку (проверить `HeroWizard`), для `pronouns` нужен обход
  («-» = нет) или шаг убрать (Q11).

### Оценка размера
Шаг 7 трогает ~12 модулей src (state, rules/builder, requests, 3 обработчика, hero_steps, prompt, world, sheet_text,
importer — последний без правок), 4 файла правил, 7 yaml данных и тесты в 7 каталогах — это отдельная S, сопоставимая с
Б0-П1/П2. Партия «К0-фикс» вырастает с «фикс» (≈0,4 млн R5) до **S ≈ 0,9–1,1 млн** (×2–2,5), по времени — два цикла
kaban/kaban-doeba вместо одного. Рекомендация: одна партия, **два коммита и два ревью** — «К0-фикс-а» (шаги 1–6, баги
прогона, живой прогон не ждёт данных) и «К0-фикс-б» (шаг 7 + данные паков); решение R5-1 «одна подпартия на S» не
нарушается — подпартия одна, коммитов два. (Q13)

### Открытые вопросы (шаг 7)
- **Q9 Где тип `Gender`:** (а) **рекомендация** — `state/gender.py` (`Gender`, `GENDER_WORDS`), импорт в state/world,
  rules/builder, requests, sheet_text; (б) в `state/world.py` рядом с `Tone`; (в) в `content/models/common.py` к Ability.
- **Q10 Данные паков:** (а) **рекомендация** — пол всем именованным NPC трёх паков + test + mini + 4 готовым героям,
  безымянным не ставить; (б) только dusk_academy и готовые герои, остальным — мастер по правилу; (в) данные не трогать.
- **Q11 Пошаговый визард:** (а) **рекомендация** — шаг «Пол» (pick, 4 варианта) + шаг «Местоимения» (text, пусто =
  нет), если пустой ввод проходит; (б) только шаг «Пол», местоимения — лишь через создание на лету/пак; (в) оба шага
  необязательными через «-».
- **Q12 `/sheet`:** (а) **рекомендация** — «(муж./жен./др.)» после вида, местоимения отдельно, только когда задано;
  (б) отдельная строка «Пол: …»; (в) в `/sheet` не показывать (только промпт).
- **Q13 Деление:** (а) **рекомендация** — одна партия, два коммита/ревью (а: шаги 1–6; б: шаг 7 + данные), один живой
  прогон после б (или а — сразу, б — по готовности данных); (б) один коммит целиком; (в) вынести п.39 в отдельную
  партию S после П37.
- **Q14 Кто ставит пол старым NPC:** (а) **рекомендация** — рассказчик `npc_update gender` при первом появлении
  (правило 7.6), без кода; (б) дополнительно world-роль при закадровых ходах; (в) эвристика по имени в коде — нет
  (рассказчик делает это лучше).

## Решения проектировщика (2026-10-12)
- Q1–Q8 — (а): Literal в `state/combat.py`; Invalid с подсказкой в `player_action`; offer_choices — только правило;
  t53 — правило о `scene_npcs` + `follows: none`; BLOCK_NONE; ручка `[llm] gemini_safety` (дефолт block_none);
  `stop_detail` — в К0-фикс; ресайз сбрасывает ручное F2.
- Q9 (а) `state/gender.py`; Q10 (а) пол всем именованным NPC трёх паков + test/mini + 4 героям; Q11 (а) шаги «Пол» +
  «Местоимения»; **Q12 (в) в `/sheet` пол не показывать**; Q13 (а) К0-фикс-а (шаги 1–6) и К0-фикс-б (шаг 7 + данные),
  два коммита и два ревью; Q14 (а) рассказчик `npc_update gender` при первом появлении.

## Правки по ревью: Ревью К0-фикс-а (шаги 1–6 docs/K0-FIX-PLAN.md), мама-кабан, 2026-10-12 (бывш. docs/decisions/k0-fix-a-review.md)

Проверено: `git diff` src/tests/docs, новые tests/unit/protocol/test_improvise_effect.py,
tests/unit/llm/test_llm_gemini_safety.py; `uv run pytest -q` — 13452 passed, 1 xfailed.
`make cov / smells / dead / ruff` в ревью не запускались — kaban прогоняет перед коммитом.

### Что хорошо
- План шагов 1–5 выполнен полностью, решения проектировщика Q1–Q8 (все «а») соблюдены: `ImproviseEffect` в
  `state/combat.py`, `EFFECTS = get_args(...)`, `spec_problem` вынесен без изменения кодов движка, `Invalid` с
  подсказкой в `player_action` после `no_active_combat`, правила (п.1.5, 2, 3) — дословно по плану, ручка
  `gemini_safety` с дефолтом `block_none`, `safety_settings` в обеих ветках `build_config`, `stop_detail` в
  журнале/сессии/репорте, F2 через класс `closed` + сброс при смене режима.
- Стиль соседних мест сохранён (`IMPROVISE_HINTS` как `SETUP_HINTS`, `NEUTRAL` с `"none"` как у `SkillOrNone`).
- Тесты закрывают план, а не подогнаны: проверены сообщения подсказок, неизменность состояния, реальные типы SDK,
  кэш-ветка, старые записи без `stop_detail`.

### Замечания
- [low] Список эффектов захардкожен строкой трижды: `IMPROVISE_HINTS["unknown_effect"]`
  (protocol/handlers/combat.py), `ValueError` в `PlayerAction.cut_improvise` (protocol/requests.py), правила.
  Для кода — `", ".join(EFFECTS)` / `get_args(ImproviseEffect)`, чтобы новый эффект не разошёлся с подсказкой.
  Правила — оставить текстом (их держит test_master_rules).
- [low] `stop_detail` vs `stop_reason` для `BLOCKED_REASON_UNSPECIFIED` (заметка doeba 4): `stop_reason` даёт
  `other`, а `stop_detail` — `"BLOCKED_REASON_UNSPECIFIED"`. Это не баг: для `other` detail идёт только в журнал/репорт
  (TurnFailed пишет detail лишь при refusal) и полезен для диагностики. Но поведение не зафиксировано тестом —
  добавить тест на `block_reason=BLOCKED_REASON_UNSPECIFIED` → `stop_reason="other"`, `stop_detail` = имя (или
  явно None — см. В-1).
- [low] `target_required` для неизвестного ref (`test_unknown_target_ref_is_target_required`) — текст «эффект X
  требует target» модель может понять как «target пуст». Можно добавить `{target!r}` («target 'xx' не найден»), но
  это не в плане — по желанию.
- [info] Заметка doeba 1: `PlayerAction.cut_improvise` под `@model_validator` — mutmut его не мутирует. Ветка
  покрыта прямыми тестами (`test_effect_none_with_skill_and_category_requires_effect`,
  `test_missing_effect_...`); выносить логику в функцию ради mutmut не нужно (в репо так же `cut_parley`).
  Убрать `PlayerAction.cut_improvise` из списка FUNCS плана/отчёта, отметить «покрыто тестами, mutmut не видит».
- [info] Заметка doeba 2: перечисленные тесты с `press("f2")` (test_tui_art.py:194, test_tui_russian.py:48,
  test_tui_live1.py:174, test_tui_turn.py:83, test_tui_entry_points.py:936) запускаются в **(100, 40)**, а не
  140×40 (см. `run(app, steps, size=(100, 40))`); файлы не изменены. Смысл не потерян — они проверяют узкий режим,
  где F2 по-прежнему открывает панель. test_tui_combat_menu.py:572/587 — (80, 24), тоже узкие. Широкий F2 покрыт
  новыми тестами test_tui_layout.py.
- [info] Заметка doeba 3: WINDOW 22450→23000 в tests/scenarios/memory_script.py обоснован комментарием (рост
  narrator_rules.md на ~1 абзац, пик 17986 > 17960). Принять; на будущее это значит, что каждый рост правил
  двигает окно — уже в духе Р1 «Память боя», отдельной правки не требует.
- [info] Заметка doeba 5 (stash/pop): `git stash list` пуст; все пункты шагов 1–6 в рабочем дереве на месте, оба
  новых тест-файла и правки 10 тестовых файлов присутствуют, полный pytest зелёный. Признаков потери нет.
  Неотслеживаемые файлы (`??`) stash по умолчанию не трогает — их потеря исключена.
- [info] docs/BACKLOG.md в том же диффе несёт посторонние записи (38 к, 39, 40) — это не код партии, но попадут в
  коммит К0-фикс-а; нормально, если так задумано (39 — следующая подпартия).

### Вопросы проектировщику
- **В-1. `stop_detail` при `stop_reason=other`** (в т.ч. `BLOCKED_REASON_UNSPECIFIED`, `MALFORMED_FUNCTION_CALL`):
  (а) **рекомендация** — оставить как есть (имя причины пишется всегда, кроме STOP/MAX_TOKENS/tool_use; для Р2 это
  данные), добавить тест; (б) писать detail только при `refusal`.
- **В-2. Список эффектов в подсказках:** (а) **рекомендация** — собирать из `EFFECTS` в коде; (б) оставить
  литералом (проще читать, риск расхождения при новом эффекте).

**Вердикт:** можно мержить после low-правок (или с ними в BACKLOG); блокирующих замечаний нет.

### Решения проектировщика (2026-10-12)
- В-1 (а): stop_detail пишется и при stop_reason=other — закреплено тестами (test_llm_gemini_safety.py).
- В-2 (а): список эффектов в подсказках собирается из EFFECTS / get_args(ImproviseEffect).
- Итог: тесты 13452+ passed (полный прогон до В-1/В-2; после — protocol/llm/combat 3507 passed), smells 205/206, dead чисто.
  mutmut: cut_improvise не виден mutmut (@model_validator) — покрыт прямыми тестами. Выжившие на старых строках
  (player_action, parse_response, stop_reason, markdown "") — BACKLOG 16 по правилу 4.
- Расходы: kaban ~80+82 тыс. (~22 мин); kaban-doeba ~178+179 тыс. (~76 мин, mutmut); mama-kaban ~53 тыс.

## Правки по ревью: Ревью К0-фикс-б (шаг 7 плана K0-FIX-PLAN: пол и местоимения, BACKLOG 39) (бывш. docs/decisions/k0-fix-b-review.md)

Мама-кабан, 2026-10-12. Предмет: незакоммиченный дифф поверх 6a51984 + новые файлы.

### Что сделано хорошо
- Сделано по плану и решениям Q9а/Q10а/Q11а/Q12в/Q13а/Q14а: `state/gender.py`, поля с дефолтами у `NPC`,
  `HeroState`, `CharacterChoices`; `GenderOrNone` + `NEUTRAL` у `NpcCreate`/`NpcUpdateBase`/`HeroSheetRequest`/`PackNpc`.
- Обратная совместимость: старые сейвы v9 и `meta/hero_sheet.json` без полей грузятся (дефолты None/""), схема остаётся 9.
  Replay старых журналов: запросы без полей -> "none"/"" -> None, `change_identity` ничего не пишет, лог прежний.
- Промпт: `identity_data` кладёт ключи только когда заданы (scene_npcs, known_npcs, hero, world) — golden не плывёт.
- `nothing_to_change` в обоих `npc_update` учитывает gender/pronouns: запрос только с полом не отклоняется.
- Импорт пака: `npc_data` через `filled` — None/"" в yaml не попадают.
- `/sheet` не тронут (Q12в). Визард: «Не указывать» = "" -> None, «-» = по полу.
- DefeatOutcome: полей нет и не нужно — он не создаёт NPC (последствия поражения героя). Заметка doeba закрывается «не нужно».
- Кэш схем Gemini: схемы инструментов изменились один раз — разовая инвалидация кэша, не баг.

### Замечания
- [low] `handlers/world.py npc_create` — пол/местоимения ставятся дважды: в `NPC(..., gender=..., pronouns=request.pronouns or "")`
  и затем `change_identity`. Предлагается оставить одно: убрать поля из конструктора `NPC(...)` (лог «пол …» даёт
  `change_identity`), либо не вызывать `change_identity` и лог дописать руками. Сейчас работает, но дублирование.
- [low] `npc_update` не умеет сбросить pronouns/пол («пусто/none = не менять»). По плану так и задумано; фиксирую как
  известное ограничение (исправить ошибочный пол можно только сменой на другой).
- [medium] Чек-лист живого прогона `checklist-k0-fix-live.md` не содержит пунктов 7.9 (старый мир — рассказчик
  ставит `npc_update gender`; dusk_academy — пол в контексте; создание героя тремя путями; старый hero_sheet.json грузится).
  Пункт 7.9 «пол в /sheet» после Q12в заменить на «пол в hero_data промпта / сейве». Дописать до прогона.
- [low] Данные: drunk_dragon — 31 именованный NPC, female только Лира; остальные male (14 неоднозначных — по роду титула,
  как решено). Выборочно сверено: dusk_academy (Майя, Селена, Эдит, Матушка Рут — female; Люциан, Кай — male), vale
  (Гарт, Гракх — male), test (Ильва, Мейра — female; Бертрам — male; безымянные стражники без пола), герои Грей/Арн — male,
  Лиэль — female. Противоречий с описаниями не нашёл.

### Вопросы проектировщику
- В-1. Сброс пола/местоимений через `npc_update`. (а) **рекомендация** — не делать, ограничение принять (редкий случай);
  (б) ввести значение "clear" для pronouns.
- В-2. Женские роли drunk_dragon, обозначенные титулом мужского рода («Капитан…», «Иерарх…»): (а) **рекомендация** —
  оставить male по решению, сверить на прогоне; (б) снять пол с неоднозначных и отдать рассказчику (Q14а).

**Вердикт:** можно мержить после дописания чек-листа (medium); low — по желанию.

### Решения проектировщика (2026-10-12)
- В-1 **(б) сделать сброс**: `GenderUpdate` = пол + `"unset"` только в `NpcUpdateBase` (оба npc_update); `pronouns: "-"` —
  сброс; лог «пол не задан» / «местоимения не заданы»; фраза в narrator_rules.md и world_rules.md.
- В-2: 14 NPC drunk_dragon — male по роду титула (решено ранее), сверить на живом прогоне.
- [low] двойная установка пола в npc_create убрана (только change_identity). [medium] чек-лист дополнен.
- Итог: полный pytest 13629 passed, 1 xfailed; smells 205/206; mutmut change_identity 26/26 убиты.
- Расходы: kaban ~134+138+141 тыс. (~18 мин); kaban-doeba ~203 тыс.+дозадача (~70 мин, mutmut); mama-kaban ~43 тыс.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- **К0-фикс (2026-10-12):** план docs/plan-k0-fix.md (papa-kaban ~149+41 тыс.), + BACKLOG 39 (пол и местоимения NPC/героя, решение проектировщика — в К0-фикс). Решения Q1–Q14 — в конце плана (все (а), кроме Q12 — пол в /sheet не показывать). Деление: К0-фикс-а (шаги 1–6), К0-фикс-б (шаг 7 + данные паков), два коммита/ревью. Размер S ≈ 0,9–1,1 млн. Ждёт «окей, кабаним».
- К0-фикс-а ✅ (код+тесты+ревью docs/plan-k0-fix.md, В-1а, В-2а; расходы там же). К0-фикс-б ✅ (пол и местоимения, сброс unset/«-»; ревью docs/plan-k0-fix.md). Дальше — живой прогон пользователя по checklist-k0-fix-live.md → docs/plan-k0-fix.md, затем П37 («окей, кабаним»). Обход summarizer (38 к) — в Р2.
- ⚠ 2026-10-12: обход BACKLOG 38 к) — ~/.config/ai-dm/config.toml переводит summarizer на gemini-3.8-flash (flash-lite отказывал в выжимке, мир dusk_academy-d3de6c57 стоял). Снять после фикса отказа summarizer.
- **2026-10-12:** живой прогон К0-фикс отменён проектировщиком; К0-фикс закрыта без прогона (чек-лист остаётся для будущих прогонов). Дальше — П37 (код kaban + тесты kaban-doeba по docs/plan-p37.md).
