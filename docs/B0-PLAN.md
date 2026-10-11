# План партии Б0 (этап 6б): свободная предыстория + лёгкий пресет мира

Автор: папа-кабан, 2026-10-08. Статус: **предложение на аппрув** (решения проектировщика в `decisions/b0-grooming.md`
обязательны: П-1 → б, П-2 → а, П-5/П-6, П-3/П-4). Основа: `decisions/b0-grooming.md` (ТЗ свинопаса, аудит свекрови,
решения), `decisions/roadmap-r4-unified.md` (#1 Б0, правила 1–3, разд. 3 версии), `ROADMAP-PLAN.md` (Б0, Б-1/Б-2, М0),
`BACKLOG.md` п. 25 (градиент 1–4), `TZ.md` 3 (tone) и 5.2 (предыстория), `STAGE6A-PLAN.md` (формат), HANDOFF.
Код: `rules/builder.py`, `state/world.py` (Tone), `state/hero.py` (BackgroundSpec), `campaign/models.py`, `campaign/build.py`,
`campaign/loader.py`, `game/tone.py`, `game/starter.py`, `master/prompt.py`, `master/summarizer.py` (образец роли),
`master/session.py`, `protocol/schema.py`, `protocol/requests.py`, `protocol/apply.py`, `protocol/handlers/summary.py`
(образец хендлера), `protocol/context.py`, `persistence/migrations/` (`m0003` — образец миграции тона, `m0007` — последняя),
`ui/cli.py`, `campaigns/drunk_dragon/campaign.yaml`, `tests/unit/persistence/test_migration_v7.py`, `test_schema_fingerprint.py`,
`tests/scenarios/memory_script.py` (WINDOW).

**Критерий Б0 (из груминга, «Готово»):** мок — валидная предыстория от модели → `BackgroundSpec` → герой собирается
`build_character`; три невалидные (бюджет > 50 зм, навык класса, черта не origin) → ошибка модели и повтор; ответ не
разбирается → сбой `TurnFailed("invalid")` (меню 2.2 рисует UI в Б1); пресет: абзац голоса в кэшируемой части, префикс
system[0..1] байт-в-байт одинаков между ходами; **сейв v7 грузится через миграцию v8** (решение П-1 б — пункт «версия
остаётся 7» из черновика снят проектировщиком).

**Принято из решений:** романтика 1–4 → расширение `Tone.romance` в сейве, **v8 в Б0**; пресет разворачивается в
`world.tone` при создании мира, в сейве `preset_id` нет (М0); в паке — только пресет по умолчанию; пресет главнее тона пака;
голос пресета **заменяет** `tone.notes`; UI выбора (предыстория и пресет) — Б1, в Б0 модуль + мок + CLI-флаг; проверки
черты origin (`builder.py:74`) и конфликта навыка класса (`builder.py:224`) **переиспользуются**, не пишутся заново.

**Не входит:** герой на лету и экраны выбора (Б1), пошаговый режим (Б2), import (Б3), поля пресета в сейве / ритм мира /
свои пресеты / история смены (М0, П1–П2), внутриигровая смена пресета, уровень 5, живой прогон refusal (после Б1).

## A. Архитектура

### A1. Сейв v8: только `Tone.romance`
- `state/world.py`: `romance: Literal["", "нет", "намёки", "чувственно", "откровенно"]` (1 нет · 2 намёки · 3 «фильм 18+
  мягко» · 4 «фильм 18+ максимум»; имена — вопрос Q2). Значение `"есть"` **уходит** из Literal.
- `persistence/migrations/m0008_v7_to_v8.py`: `migrate_v7_to_v8(data, context=None)` — чистая `dict → dict`, вход не
  мутирует, литералы заморожены (как `m0003`), контекст не нужен (в кортеж `MigrationContextRequired` в `migrate()` не
  добавлять). Правило одно: `world.tone.romance == "есть"` → `"откровенно"` (Q1); прочие значения не трогаются; значение
  вне списка → `""` (как в `m0003.convert_tone`). Ничего другого v8 не добавляет (правило 3 R4 — только нужное).
- `CURRENT_SCHEMA_VERSION = 8`, `MIGRATIONS[7]`, отпечаток `tests/schema/save_v8.schema.json` (команда — в
  `test_schema_fingerprint.py`), `save_v7.schema.json` остаётся историей.
- Нейтральность (правило 2 R4): миграция меняет только одно значение шкалы; поведение хода до/после на моке совпадает
  (ответы модели скриптованы), промпт меняется в одном слове `world_block`.
- **Сдвиг версий в роадмапе (предложение):** v8 Б0 · **v9 К0** · **v10 Ж0** · **v11 М0** · **v12 С0**. Правки документов:
  `roadmap-r4-unified.md` (строка #1 → v8, строки #7–#56 и таблица разд. 3), `ROADMAP-PLAN.md` (разд. 3 «Точки миграции»,
  сводка), HANDOFF («Сейв: …»). Правило 3 R4 остаётся: кроме К0/Ж0/М0/С0 схему не трогают.
- Побочка v8 (ожидаемо, как риск 5 STAGE6A-PLAN): старые репорты 6а в `saves/*/issues` после v8 дадут `ReplayDivergence`
  (снимок `before` мигрирует, журнал записан под `romance: есть`); сообщение уже содержит версии. Новые репорты — норма.

### A2. Паки и тесты, где живёт `"есть"`
- `campaigns/drunk_dragon/campaign.yaml:58` `romance: есть` → новое значение (то же, что в миграции). Пак валидируется
  моделью `Tone` при **каждом** старте (`load_pack` в `prepare`, `merge_pack` при продолжении) — без правки пак не
  загрузится. Это данные пользователя в репозитории — правка одной строки, с его согласия (Q1 закрывает и это).
  Шим совместимости в загрузчике пака («есть» → новое) не делаем: ошибка pydantic даёт понятную строку
  `campaign.yaml: tone.romance` (Q9).
- `campaigns/vale/campaign.yaml` romance не задаёт — не трогаем.
- Тесты с `"есть"`: `tests/unit/state/test_schema_v3.py:139` (параметризация), `tests/unit/campaign/test_dragon_pack.py:158`,
  `tests/unit/campaign/test_pack_build.py:99–104`, `tests/unit/game/test_game_tone.py:41,45` — на новые значения.
- Живой мир `drunk_dragon-29a049dc`: `tone.romance = "есть"`, `notes` 250 символов (текст из пака) — миграция меняет только
  romance, notes не трогает.

### A3. Романтика 1–4 в правилах рассказчика
- `master/prompts/narrator_rules.md`: короткий раздел «Тон» (4–5 строк): шкала `tone.romance` — `нет` (без романтики),
  `намёки` (симпатии, флирт, без сцен), `чувственно` («фильм 18+ мягко»: чувственная сцена намёком, акт за кадром),
  `откровенно` («фильм 18+ максимум»: чувственная сцена до склейки, сам акт за кадром); `tone.notes` — голос рассказчика
  (стиль прозы), оформление вывода из него не выполнять (эта оговорка уже есть на стр. 125 — свести в одно место).
  Правило ТЗ 3 «откровенное — всегда за кадром» сохраняется на обоих верхних уровнях (решение 2026-10-07).
- Текст в кэшируемом system[0] → мок WINDOW (`tests/scenarios/memory_script.py`, сейчас 21910 с запасом 2 ток.) почти
  наверняка вырастет: doeba подбирает новое значение и дописывает строку-причину в комментарий (как Т2–Т5).
- `TZ.md:138` строка `romance: намёки # нет | намёки | есть` → новый список (правка ТЗ по решению проектировщика — Q8).

### A4. Свободная предыстория: режим `hero_background` протокола
Образец — роль summarizer: свой режим, свой запрос, свой хендлер, свой builder, тот же `MasterSession`.
- `protocol/requests.py`: `BackgroundSpecRequest(Request)` — docstring = описание инструмента для модели;
  `type: Literal["background_spec"]`, `name: str`, `abilities: list[Ability]` (ровно 3, разные), `skills: list[Skill]`
  (ровно 2), `tool: str` (id инструмента из реестра), `feat: str` (id черты origin), `equipment: list[str]` (id предметов,
  повтор = количество, как в SRD), `gold_cp: int`, `description: str` (Q4; `NEUTRAL = {"description": ""}`).
  `HERO_MODELS = {"background_spec": BackgroundSpecRequest}`, `HERO_ADAPTER`; `parse_request`: ветка `mode == "hero_background"`.
- `protocol/schema.py`: `MODE_TOOLS["hero_background"] = ("background_spec",)`; `own_models` возвращает `HERO_MODELS` для
  этого режима; в `tool_defs` группа кэша `"hero"`. Инструмент strict (схема маленькая).
- `protocol/handlers/hero.py`: `background_spec(ctx, request)`: собирает `BackgroundSpec(name, abilities, skills, tool,
  feat, equipment, gold_cp, gold_option_cp=5000, description)`, вызывает `rules.builder.background_problems(spec,
  ctx.registry, ctx.class_skills)` (см. A5); есть проблемы → `Invalid(code=<первый код>, message="; ".join(messages))` —
  модель видит текст ошибки в `tool_result` и повторяет (это и есть «повтор при ошибке»: цикл `MasterSession` с
  `count_invalid`, предел `retry.invalid_retries` → `TurnFailed("invalid")`). Повторный вызов после принятого —
  `Invalid("already_done")` (как `scene_summary`). Успех → `ctx.background = spec`, `Decision(status="accepted",
  log=["Предыстория принята"])`.
- `protocol/apply.py`: `HERO_HANDLERS = {"background_spec": hero.background_spec}`; ветка `ctx.mode == "hero_background"`
  до общего `HANDLERS` (как `summarize_*` и `world`).
- `protocol/context.py`: `CreationContext` — контекст без бандла: `registry`, `cfg`, `mode="hero_background"`, `class_id`,
  `class_skills: list[str]`, `background: BackgroundSpec | None = None`, `marks=[]`, `turn_seq = 0`. У `TurnContext` —
  свойство `turn_seq` → `bundle.session.turn_seq`.
- `master/session.py` (три точечные правки, поведение остальных ролей не меняется):
  1) `call()`: `turn_seq=ctx.turn_seq` вместо `ctx.bundle.session.turn_seq`;
  2) `required_tool()`: `ctx.bundle.session.active_combat` читать только при `mode == "combat_narrate"` (сейчас читается
     безусловно — упадёт на `CreationContext`); `REQUIRED_BY_MODE["hero_background"] = "background_spec"`;
  3) ранний выход после принятого обязательного инструмента: вместо `self.role == "summarizer"` — `mode in
     SINGLE_SHOT_MODES` (`summarize_scene`, `summarize_chapter`, `hero_background`); для summarizer эквивалентно.
  Роль остаётся `narrator` (ТЗ груминга): модель и цена роли narrator, журнал/`/cost` — под narrator.
- `master/hero.py`: `BackgroundPromptBuilder(app_cfg, model=None)` по образцу `SummarizerPromptBuilder`: `role="narrator"`,
  `find_role_cfg` — как у `PromptBuilder` (narrator + alternatives + profiles). `build(ctx, user_input, mode, world_text="")`:
  system[0] — `master/prompts/background_rules.md` (cache=True): задача, правило 5.2 (+2/+1 или +1/+1/+1 — бонус задаёт
  игрок позже, предыстория даёт три характеристики; 2 навыка; инструмент; черта origin; набор ≤ 50 зм; навыки не из уже
  выбранных навыков класса; только id из справочника; описание ≤ 300 символов), требование вызвать `background_spec`;
  system[1] — справочник (cache=True): 4 SRD-предыстории `registry.all("background")` как примеры, id черт origin,
  id инструментов (`registry.all("item")` с `.tool`), id предметов с ценами `cost_cp` (как `item_ids` в `world_block`),
  списки `ABILITIES`/`SKILLS`, `BACKGROUND_BUDGET_CP`; messages[0] — `dump({"class": class_id, "class_skills": [...],
  "description": <текст игрока>})`. Без плана контекста (`last_plan` нет — `getattr` в `run()` уже это переживает).
- `game/hero_create.py` (новый, слой game): `propose_background(adapter, app_cfg, registry, cfg, *, class_id,
  class_skills=(), description, run_id, journal=None, ledger=None, now=None, model=None) -> BackgroundSpec` — создаёт
  `CreationContext`, `MasterSession(adapter, app_cfg, journal=…, ledger=…, run_id=run_id, now=now, role="narrator",
  builder=BackgroundPromptBuilder(app_cfg, model=model))`, `session.run(ctx, description, apply, "hero_background",
  run_id=run_id)`; возвращает `ctx.background`; сбои — `TurnFailed` (`network`/`fatal`/`invalid`/`refusal`) наверх: меню
  2.2 — у вызывающего (Б1). Префикс `run_id` — `"hero-…"` (как `bnd-…` у границы). `with_background(choices, spec) ->
  CharacterChoices` — `model_copy(update={"background": spec})`; герой собирается штатным `build_character`.
  До Б1 у функций нет вызывающего в `src` → `make dead` их подсветит: внести в `vulture_allowlist.py` до Б1 (прецедент
  `haggle_*` до Т5) — Q6.
- Ручная правка (Б-2): та же `background_problems` на `BackgroundSpec.model_validate(dict)` — функция в `rules/builder.py`,
  UI — Б1. В Б0 — только тест, что путь «руками» и путь «от модели» дают одни коды/тексты.

### A5. `rules/builder.py`: вынести общую проверку, не дублируя
- `background_skill_conflict(spec, class_skills) -> bool` — вынести из `build_character` (строка 224), там же использовать.
- `background_problems(spec, registry, class_skills=()) -> list[str]` — тексты: `validate_background` →
  `BACKGROUND_MESSAGES`, + конфликт навыка класса (текст со строки 225), + `item_unknown` для `equipment`
  (`find_item is None`, текст как на 356), + инструмент: `registry.has("item", tool) and registry.get("item", tool).tool`
  (новый код `background_tool_unknown`, текст «предыстория: нет такого инструмента: …»). Сам `validate_background` и его
  коды не меняются (его проверки — те же, что у SRD-пути).
- `state/hero.py`: `BackgroundSpec.description: str = ""` (Q4) — попадает в v8 сейчас; у 4 SRD-предысторий остаётся пустым
  (`background_from_registry` не трогаем). В промпт/`/sheet` — Б1.

### A6. Лёгкий пресет мира
- `campaign/presets.py` + данные `campaign/presets.yaml` (читать через `importlib.resources`, как `prompts/*.md` и
  `art/index.yaml`): `WorldPreset(BaseModel, extra="forbid")`: `id`, `name`, `description` (одна строка для будущего
  экрана), `tone: Tone` (mood, 4 оси, `notes` = абзац голоса; `hard_limits`/`soft_limits` у пресетов пусты).
  `load_presets() -> dict[str, WorldPreset]` (с проверкой уникальности id и непустого голоса), `PACK_TONE = "pack"` —
  служебное значение «как в паке» (не пресет каталога).
  `apply_preset(pack_tone: Tone, preset: WorldPreset) -> Tone`: mood/violence/horror/romance/language/notes — из пресета
  (П-5, П-6: голос **заменяет** notes); `hard_limits`/`soft_limits` — объединение пака и пресета без дублей, порядок пака
  первым (Q5: ограничения — не «оси тона», пресет их не снимает).
- `campaign/models.py`: `CampaignManifest.preset: str = ""` — пресет по умолчанию пака («» = как в паке). Схема пака,
  не сейва. `campaign/loader.py check_manifest`: непустой `preset` должен быть в каталоге — иначе строка ошибки пака.
  Манифесты `vale` и `drunk_dragon` не трогаем (их тон авторский, см. Q3).
- `campaign/build.py build_world(..., preset_id=None)`: `preset_id` → `manifest.preset` → `""`; при непустом —
  `tone=apply_preset(manifest.tone, presets[preset_id])`, иначе `manifest.tone.model_copy(deep=True)` как сейчас.
  Запись хроники при применении: `ChronicleEntry(kind="tone", text="Пресет мира: <name>")` (как `/tone`; история
  смен — задел для М0, схема не меняется). `game/starter.py new_world_from_pack(..., preset_id=None)` — пробросить.
- `ui/cli.py`: `--preset ID` (только с `--new`, иначе код 2, как `--hero`); неизвестный id → код 2 и список id каталога;
  `--replay` с `--preset` — как `--seed/--hero`: тот же, что в исходном прогоне (иначе `world_block` другой →
  `ReplayDivergence`; добавить в подсказку строки 448–450). Строка «Мир: … , пресет <id>» в заметках старта.
- Промпт: ничего менять не нужно — `tone` уже в `world_block` (`prompt.py:220`, блок `cache=True`), голос лежит в
  `tone.notes`. Тест стабильности — обязателен (см. B3).
- `/tone` после старта правит оси и `notes` как раньше (голос можно затереть `/tone notes …` — допустимо до М0, П-6).

### A7. Каталог пресетов — предложение на подтверждение (Q7)
Названия нейтральные (франшизы — только ориентир здесь). Оси — значения `Tone`; голос — 3–4 предложения о стиле прозы,
без указаний про оформление вывода.

| id | Название | mood | violence | horror | romance | language | Голос (суть) | Ориентир |
|---|---|---|---|---|---|---|---|---|
| `heroic` | Героическое приключение | героическое приключенческое фэнтези | реалистично | умеренно | намёки (2) | сдержанно | эпичный размах, дорога и товарищество; опасность реальна, надежда сильнее; уместный юмор | ВК |
| `grim` | Суровый мир | мрачное фэнтези, моральная серость | жестоко | сильно | откровенно (4) | грубо | грязь и цена выбора, никто не чист; натуралистичные детали ран и боя; циничные диалоги | Ведьмак |
| `romantic` | Чувства и интриги | романтическая драма и социальные интриги | мягко | умеренно | чувственно (3) | сдержанно | напряжение между людьми, взгляды и недосказанность; бой редок и быстр; акцент на отношениях и выборе сердца | Сумерки |
| `fairytale` | Светлая сказка | светлая сказочная история | мягко | нет | нет (1) | сдержанно | чудо и ясность, добро и зло различимы; жестокость без смакования; тёплый, образный тон | Нарния |

**Пресет по умолчанию** (старт без интерактива: CLI без `--preset`, replay): `manifest.preset` пака, а если он пуст —
**«как в паке»** (тон манифеста без наложения). Основание: нейтральность — ни один существующий тест/пак/мир не меняет тон;
авторские `mood`/`notes` паков (`drunk_dragon` — 250 символов заметок) не затираются молча; явный выбор пресета (флаг,
в Б1 — экран) побеждает пак, как решено в П-5. Альтернатива — `heroic` по умолчанию для всех (Q3).

## B. Партии (одна очередь, три шага; версия сейва меняется только в Б0-П0)

### Б0-П0. Сейв v8, романтика 1–4, пак, правила (S)
1. `state/world.py` — Literal `romance` (A1). 2. `m0008_v7_to_v8.py`, `migrations/__init__.py` (A1). 3. Отпечаток
`save_v8.schema.json`; `BackgroundSpec.description` (A5, Q4) — в этом же шаге, чтобы v8 была одна. 4. `campaigns/drunk_dragon/
campaign.yaml` (A2). 5. `narrator_rules.md` раздел «Тон» (A3). 6. `game/tone.py` — без правок (значения берутся из Literal:
`/tone romance чувственно` заработает само; `show_lines` без изменений). 7. Документы: TZ 3 (Q8), ARCHITECTURE (версия,
шкала), roadmap-r4/ROADMAP-PLAN/HANDOFF — сдвиг версий (A1). После коммита П0 живые миры играть **можно** (v8, нейтрально).

Тесты П0 (doeba):
- `tests/unit/persistence/test_migration_v8.py` (по образцу `test_migration_v7.py`): `MIGRATIONS[7] is migrate_v7_to_v8`,
  `CURRENT_SCHEMA_VERSION == 8`; `"есть"` → решённое значение; `"нет"/"намёки"/""` не меняются; мусор → `""`; `notes`,
  остальные шкалы, лимиты не тронуты; вход не мутирует; без `MigrationContext` цепочка 7→8 проходит (контекст не нужен);
  миграция не импортирует `ai_dm.state`/`content` (ast-проверка как в v3/v7).
- Фикстура `tests/fixtures/saves/v7/` — слот движка v7 (сгенерировать из `v6` через `load_slot`+`save_slot`, выставить
  `tone.romance: есть`); загрузка `load_slot` → валидный `SaveBundle` v8, `romance` новое; бэкап слота создан.
- Нейтральность: фикстура v7 → один мок-ход (`ScriptedAdapter`) на бандле, загруженном до правки (подменить
  `current_version=7` в `migrate`) и после → `core_dump` совпадает везде, кроме `world.tone.romance`.
- `test_schema_fingerprint`: v8 есть, совпадает; `test_schema_v3` параметризация и «отказ свободного текста» (`"есть"`
  теперь отвергается — отдельный тест); `test_game_tone`: `/tone romance чувственно|откровенно` принимается, `есть` —
  текст ошибки со списком значений; показ `/tone` содержит новое значение.
- Пак `drunk_dragon` грузится (`test_dragon_pack`), тон новый; `test_pack_build` с новым значением.
- `test_master_rules`: раздел «Тон» в правилах содержит все четыре значения шкалы (строки берутся из `Tone` Literal, чтобы
  текст и модель не разошлись); WINDOW мока пересчитан, `test_stage4_memory` зелёный.

### Б0-П1. Свободная предыстория (M)
1. `rules/builder.py` — A5. 2. `protocol/requests.py`, `schema.py`, `apply.py`, `handlers/hero.py`, `context.py` — A4.
3. `master/session.py` — три правки A4. 4. `master/hero.py` + `prompts/background_rules.md`. 5. `game/hero_create.py`.
6. `vulture_allowlist.py` (Q6). 7. ARCHITECTURE: роль/режим `hero_background`, модуль `game/hero_create`, `protocol` (режим).

Тесты П1 (doeba):
- `tests/unit/rules/test_builder.py` (+): `background_problems` — валидный spec → `[]`; бюджет 50 зм + 1 мм → текст бюджета;
  черта не origin (например, боевой стиль) → `background_feat`; навык из `class_skills` → текст «навык класса уже даёт
  предыстория»; неизвестный предмет → `item_unknown`; инструмент не из реестра / не инструмент → новый код;
  `background_skill_conflict` — вынесен, `build_character` даёт прежний результат (регресс по существующим тестам
  строк 1116–1144, 452–464). Подтверждение аудита: проверки origin и конфликта **существуют** и покрыты.
- `tests/unit/protocol/`: `tool_set("hero_background")` — один strict-инструмент `background_spec`, схема без `$ref`,
  `description` из docstring; `parse_request` в этом режиме принимает только `background_spec`; `apply` в чужом режиме →
  `not_available_in_mode`; хендлер: невалидный → `Invalid` с текстами всех проблем через «; », валидный → `ctx.background`
  заполнен, второй вызов → `already_done`; `CreationContext.turn_seq == 0`, `TurnContext.turn_seq` = `session.turn_seq`.
- `tests/unit/master/test_hero_prompt.py`: system[0] = правила файла, system[1] — 4 SRD-предыстории (имена из реестра),
  id черт только origin, инструменты только `.tool`, оба блока `cache=True`; messages[0] содержит class/class_skills/описание;
  `find_role_cfg` берёт конфиг narrator (`max_tokens`/`effort`), профиль по модели; префикс system[0..1] одинаков для
  двух разных описаний (кэш).
- `tests/unit/master/test_master_session_*` (+): ранний выход в `hero_background` после принятого инструмента (второго
  вызова модели нет — `CountingAdapter`); summarizer — поведение прежнее (регресс существующих тестов); `required_tool`
  в режиме `hero_background` не трогает `bundle`.
- `tests/unit/game/test_hero_create.py` (+ сценарий `tests/scenarios/test_stage6b_background.py`, критерий Б0):
  (а) `ScriptedAdapter`: вызов `background_spec` валидный → `BackgroundSpec`; `with_background(fighter_choices(), spec)` с
  `class_skills` без конфликта → `build_character` возвращает `HeroState`, навыки/инструмент/черта/набор/деньги по spec;
  (б) три невалидных первым шагом (бюджет 60 зм; навык `perception` при `class_skills=[perception, survival]`; черта
  `defense`) → `tool_result is_error` с нужным текстом, второй шаг валидный → принято; журнал: 2 вызова, `role=narrator`,
  `run_id` с префиксом `hero-`, `turn_seq=0`; `/cost`-леджер пополнен под narrator;
  (в) ответы без инструмента `invalid_retries + 1` раз → `TurnFailed("invalid")`; `stop_reason=refusal` →
  `TurnFailed("refusal")` с меткой; `max_tokens` → повтор с подсказкой;
  (г) ручная правка: `BackgroundSpec.model_validate(dict)` с теми же дефектами даёт те же тексты, что путь модели (Б-2);
  (д) `description` длиннее 300 символов → `Invalid` (если предел принят в Q4).
- `test_architecture`: `rules` не импортирует `protocol/master` (сторож уже есть); `master/hero.py` не импортирует `game`.

### Б0-П2. Лёгкий пресет (S/M)
1. `campaign/presets.py`, `campaign/presets.yaml` (A6, каталог A7). 2. `campaign/models.py` `preset`, `loader.py` проверка.
3. `campaign/build.py`, `game/starter.py` — `preset_id`, хроника. 4. `ui/cli.py` `--preset`. 5. README/`--help`,
ARCHITECTURE (`campaign`: пресеты), BACKLOG 25 (сделано в Б0: тон/голос/романтика; остальное М0/П).

Тесты П2 (doeba):
- `tests/unit/campaign/test_presets.py`: каталог грузится, 4 пресета, id уникальны, у каждого непустые `name`/`notes`,
  все оси — допустимые значения `Tone` (`model_validate`), romance ≤ «откровенно» (уровня 5 нет); `apply_preset`: оси и
  `mood`/`notes` из пресета, лимиты = объединение (пак первым, без дублей); тон пака не мутирует.
- `test_pack_build` (+): `build_world(preset_id="grim")` — `world.tone` = пресет поверх `vale`; без `preset_id` и с пустым
  `manifest.preset` — тон пака как сейчас (регресс); `manifest.preset: "heroic"` в тестовом паке → применяется; неизвестный
  `preset` в манифесте → строка ошибки `PackError`; запись хроники `kind="tone"` с названием пресета ровно одна.
- `tests/unit/ui/test_cli_*` (+): `--new --preset grim` → в заметках «пресет grim», `world.tone.romance == "откровенно"`;
  `--preset` без `--new` → код 2; неизвестный id → код 2 и список id; `--replay` без `--preset`, когда мир создавался с
  ним, — подсказка в сообщении (строки 448–450).
- Стабильность префикса (критерий): мир с пресетом → два мок-хода → `system[0].text` и `system[1].text` запросов narrator
  побайтно равны, `tone.notes` пресета внутри system[1]; после `/tone romance намёки` — system[1] меняется (ожидаемо, как
  сейчас), system[0] — нет.
- Сценарий `test_stage6b_background.py` расширить шагом: новый мир `--preset heroic` через `main([...--mock])` — старт
  проходит, `/tone` показывает оси пресета.

## C. Качество (каждый шаг)
`make cov` ≥ 94%, `make smells` ≤ 202 (новый код плоско: хендлер и `apply_preset` — без вложенности), `make dead`
(allowlist — Q6), `make mutate FUNCS="…" TESTS="…"` по изменённым функциям из diff (П0: `m0008:migrate_v7_to_v8`,
`game.tone` не меняется; П1: `rules.builder:background_problems`, `rules.builder:background_skill_conflict`,
`protocol.handlers.hero:background_spec`, `master.session:MasterSession.required_tool`, `master.session:MasterSession.run`,
`master.hero:BackgroundPromptBuilder.build`, `game.hero_create:propose_background`; П2: `campaign.presets:apply_preset`,
`campaign.presets:load_presets`, `campaign.build:build_world`, `ui.cli:prepare`). Выжившие на старых строках `build_world`/
`prepare`/`run` — в BACKLOG 16, не разбирать. Ревью мамы-кабана — каждый шаг. Расходы — в HANDOFF.

## D. Риски
1. **Пак не грузится** после смены Literal, если `drunk_dragon/campaign.yaml` не поправлен в том же коммите П0 — живой мир
   нельзя продолжить. Шаги 1 и 4 П0 — атомарно.
2. **WINDOW мока** без запаса (2 ток.) — раздел «Тон» в правилах его сдвинет; doeba пересчитывает, причину записывает.
3. **Старые репорты 6а** станут невоспроизводимыми (A1) — ожидаемо, сообщить проектировщику явно.
4. `MasterSession.required_tool` читает `bundle` безусловно — без правки 2) из A4 `CreationContext` упадёт; тест на это
   обязателен до остального (как детерминизм в 6а).
5. Модель может не знать id предметов/инструментов — поэтому справочник id в system[1]; при больших реестрах блок растёт
   (оценка ~ как `item_ids` в `world_block`, приемлемо). Если на живом прогоне Б1 модель упорно ошибается в id — добавить
   подбор по имени (сейчас не делаем).
6. `make dead` на `propose_background`/`with_background` до Б1 (Q6).
7. Replay (`--replay`) мира, созданного с `--preset`, без того же флага — расхождение по отпечатку; документируем.
8. Романтика 4 на Gemini — refusal: проверяется живым прогоном после Б1 (риск 9 роадмапа), в Б0 — только мок.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1.** Миграция `"есть"` → **`откровенно` (4)**: «есть» было верхом старой шкалы, пользователь поставил верх в своём паке и
  мире — сохраняем относительное положение; пак и мир получают одно значение. Альтернатива — `чувственно` (3), осторожнее
  по поведению.
- **Q2.** Имена новых значений шкалы: **`чувственно` (3) и `откровенно` (4)** (одно слово, в духе остальных шкал).
  Альтернатива — `18+ мягко` / `18+ максимум`.
- **Q3.** Пресет по умолчанию без интерактива: **«как в паке»** (нейтрально, авторский тон паков цел); манифесты `vale`/
  `drunk_dragon` не трогать. Альтернатива — `heroic` для всех.
- **Q4.** `BackgroundSpec.description: str = ""` (текст предыстории от модели, ≤ 300 символов) — **добавить сейчас в v8**
  (бесплатно, потом — отдельная версия); использование в промпте/`/sheet` — Б1.
- **Q5.** `hard_limits`/`soft_limits` при наложении пресета — **объединение пака и пресета** (пресет лимиты не снимает);
  альтернатива — пресет заменяет тон целиком, включая лимиты.
- **Q6.** `vulture_allowlist.py`: `propose_background`, `with_background` (и, если подсветит, `CreationContext.background`)
  до Б1 — **да** (прецедент `haggle_*` до Т5).
- **Q7.** Каталог A7 (4 пресета, нейтральные имена, оси и голос) — подтвердить или поправить оси/тексты.
- **Q8.** Правка `TZ.md` 3 (строка `romance`) под четыре значения — **да**, с пометкой «решение 2026-10-08».
- **Q9.** Шим «есть» → новое значение в загрузчике пака — **нет** (ошибка pydantic понятна, паки правятся руками).

Технические умолчания на аппрув вместе с планом: проверка существования инструмента в реестре только на пути модели
(`background_problems`), `validate_background` не меняется; запись хроники при применении пресета; служебное значение
«как в паке» не входит в каталог; роль вызова предыстории — `narrator` (журнал/`/cost` под narrator); `run_id` `hero-…`.

## Решения проектировщика (2026-10-08)
Q1–Q4, Q6–Q9 — по рекомендациям; технические умолчания — приняты. Q5 — объединение лимитов пака и пресета (пресет
hard/soft_limits не снимает; уточняет П-5 «пресет главнее» — главнее по осям, mood и notes). «Окей, кабаним».
