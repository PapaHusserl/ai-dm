# План партии Б1: «Герой на лету, ИИ-путь» — Б1а (модуль, протокол, мок) и Б1б (UI, пресет, живой прогон)

Автор: папа-кабан, 2026-10-08. Статус: **предложение на аппрув** (решения проектировщика В1–В15 из
`docs/plan-b1.md` обязательны и приняты за основу). Основа: `docs/plan-b1.md` (ТЗ свинопаса, аудит свекрови,
решения), `docs/plan-b0.md` (форма, A4–A6), `docs/plan-roadmap-r4.md` (#2 Б1), `docs/plan-roadmap-r2.md` (критерий Б1, стр. 310),
`BACKLOG.md` 16 (хвосты Б0) и 34, `TZ.md` 2.2 / 4.01 / 5 / 5.2 / 5.3 / 6 / 10, HANDOFF («Инструменты качества», «Правила экономии»).
Код: `game/hero_create.py`, `master/hero.py` + `prompts/background_rules.md`, `protocol/{context,requests,schema,apply}.py`,
`protocol/handlers/hero.py`, `master/session.py`, `rules/builder.py`, `rules/uniqueness.py`, `rules/triggers_eval.py`,
`state/hero.py`, `state/triggers.py`, `content/models/classes.py`, `srd/data/classes/*.yaml`, `campaign/{build,presets,models,loader}.py`,
`game/{starter,sheet_text,commands,app}.py`, `master/prompt.py`, `llm/{journal,replay}.py`, `ui/{cli,simple,session,screen}.py`,
`ui/tui/{__init__,modals,app,strings}.py`, тесты `tests/unit/{rules,protocol,master,game,campaign,ui,ui/tui}`, kit-ы
`master_kit`/`protocol_kit`/`game_kit`/`ui_kit`/`campaign_kit`, `tests/scenarios/test_stage6b_background.py`, `memory_script.py` (WINDOW).

**Критерий Б1 (груминг «Готово»):** мок `test_stage6b_done` (ИИ-путь): описание → невалидный лист → отказ инструмента →
валидный → ручная правка с ошибкой (тот же текст, что у модели) → подтверждение → мир → ход → сейв/загрузка (герой,
motive/means/opportunity целы); простой режим и TUI проходят путь (тест на каждый); `make smells` ≤ 202, `make dead` чисто,
mutmut по новым функциям; **живой прогон** (Б1б): новый мир, герой на лету, пресет мира с романтикой 4 (`grim`), 10–15 ходов,
`/cost` (цена создания отдельно), сейв/загрузка, фиксация refusal (В8). Сейв **остаётся v8** (motive/means/opportunity у
`HeroState` есть — `state/hero.py:99–101`; `CharacterChoices` в сейв не пишется).

**Принято из решений:** один режим `hero_sheet` с одним strict-инструментом, предыстория — вложенное поле (В1); любой из трёх
методов характеристик (В2); ручная правка всех полей тем же валидатором (В3); интерактивный выбор пресета мира (В4);
opportunity героя 0–2 триггера, проверка ссылок как у NPC (В5); `--hero-describe` с автоподтверждением (В6); replay берёт
итоговый лист из записи старта (В7); refusal на романтике 4 фиксируется, партия принимается, пресет помечается
провайдер-зависимым (В8); роль narrator (В9); деление Б1а/Б1б (В10); имя даёт ИИ, id — движок, совпадение имени с NPC — ошибка
валидатора (В11); снаряжение/деньги — стандартный набор от движка по классу/предыстории, ИИ выбирает из вариантов (В12);
стартовая локация из манифеста (В13); пак без пресетов героев — сразу ИИ-путь (В14); 2 повтора валидатора, потом меню 2.2 (В15).

**Не входит:** пошаговый режим и выбор метода руками в UI (Б2); `HeroPickerApp`/экран создания внутрь основного App, заставка до
выбора (Б2, BACKLOG 16); продолжение мира/наследник (Н1); import (Б3); поля пресета в сейве (М0); means/opportunity в
`HeroPreset` пака (BACKLOG 34); подбор id по имени (только если живой прогон покажет, B0 риск 5); авто-репорт refusal при
создании (мира ещё нет — только журнал; см. D7); смена предыстории у героя пресета (stage6 В8).

## A0. Поправки фактов (проверено по коду и `qlty smells`, 2026-10-08)
1. **`protocol/context.py:5` «__init__, 9 параметров» — это `TurnContext.__init__`** (старый код, BACKLOG 16 «дефолты
   TurnContext.__init__»), а не `CreationContext` (строка 87, 4 параметра, **smell на нём нет**). Пункт груминга «разгружать
   атрибуты `CreationContext`» целится мимо: атрибуты qlty не считает. В Б1 `CreationContext` **обобщается по задаче** (A2), а не
   «разгружается»; `TurnContext.__init__` не трогаем (не Б1).
2. qlty считает маркер `*` параметром: `propose_background` = 12 именованных + `*` = 13; порог — **≥ 6 с учётом `*`**
   (т.е. не больше 4 именованных + `*`), «много return» — ≥ 6, сложность — флаг от ~18, вложенность — 5. Разгрузка
   `propose_background` в объект даёт ровно **−1** smell; весь новый код обязан дать **+0** (плоские функции, ≤ 4 именованных
   параметра + `*`, ≤ 5 return). Функции, уже помеченные (`build_world` 9 параметров, `prepare` 16 return, `build_character`
   сложность 176), новых smells при правке не добавляют, но править их — минимально.
3. `retry.invalid_retries = 2` уже в `config/app_defaults.toml:76` — В15 выполняется существующим бюджетом `MasterSession.count_invalid`,
   новой ручки нет.
4. id героя всегда `"hero"` (`campaign/build.py:37` `hero_id="hero"`, `Manifest.current_hero_id`) — В11 «id генерирует движок»
   уже так; остаётся только проверка **имени** (`rules/uniqueness.check_hero`, строки 68–80).
5. **В контенте нет стартовых наборов классов** (`CharacterClass` без поля снаряжения, пресеты паков задают `inventory`/`equip`
   руками). В12 требует данных — A5, вопрос Q2.
6. В протоколе **нет схемы триггеров от модели** (`npc_create` без `opportunity`, `requests.py:392–406`); strict-схема не может
   быть рекурсивной (`strictify` инлайнит `$ref`, `Condition` — рекурсивный union). Для opportunity героя нужна **плоская**
   форма (A2, Q3). Проверка ссылок — `rules/triggers_eval.validate_refs` (строка 133; в `src` не используется — Б1 даёт ей
   потребителя).
7. `/sheet` и промпт не показывают `BackgroundSpec.description` (хвост Б0, B0-PLAN A5/Q4 «в промпт и `/sheet` — Б1») — A6.

## A. Архитектура

### A1. Данные: `HeroSheet`, наборы классов, помощники (слой `rules`/`content`, сейв не меняется)
- `rules/builder.py`:
  - `class HeroSheet(BaseModel, extra="forbid")`: `choices: CharacterChoices`, `motive: str = ""`, `means: list[str] = []`,
    `opportunity: list[Trigger] = []`. Итог ИИ-пути и ручной правки; сериализуется в `meta/hero_sheet.json` (A7, В7).
    Пределы (Q5): `MOTIVE_MAX = 200`, `MEANS_MAX = 3` (по ≤ 120 символов, как `NPC.means` 1..3), `OPPORTUNITY_MAX = 2`,
    `then` ≤ 200.
  - `CharacterChoices.class_kit: str | None = None` — id стартового набора класса (A5); `None` — как сейчас (пресеты паков не
    меняются; схема пака, не сейва). `build_character`: одна проверка `class_kit_problem(choices, char_class)` (неизвестный набор →
    код `class_kit_unknown`, текст «неизвестный набор класса: …; доступны: a, b») и один вызов `apply_class_kit(hero, choices,
    registry)` после сборки (предметы `add_catalog_item`, `equip`, `money_cp += gold_cp`) — обе функции плоские, вне
    `build_character`.
  - `sheet_check(sheet, registry, *, known=None, taken_names=()) -> (codes, messages)` — **единый валидатор листа** для пути
    модели и ручной правки (Б-2): (1) `build_character(sheet.choices, registry)` → коды/тексты `ValidationErrors` как есть;
    (2) при `BackgroundSpec` — пары из `background_check(spec, registry, choices.class_skills)`, которых нет в (1)
    (`background_tool_unknown`, `background_gold_negative`, `description_too_long`; дубли по (code, message) не добавляются);
    (3) `sheet_name_problems`: пустое имя → `hero_name_empty`; занятое (без учёта регистра, через новый
    `rules/uniqueness.name_taken(name, taken) -> bool`, его же использует `check_hero`) → `hero_name_taken`, текст тот же, что в
    `check_hero`: «имя … уже занято (NPC, бог, фракция или герой)»; (4) `sheet_hooks_problems(sheet, known, registry)`: пустой
    motive → `motive_empty`; means не 1..3 → `means_count` («от одного до трёх средств», как `npc_create`); opportunity > 2 →
    `opportunity_count`; пустой/повторный `id`, пустой `then` → `opportunity_id`/`opportunity_then`; битые ссылки условий →
    `opportunity_ref` с текстами `validate_refs` («npc_status: неизвестный NPC …»). Три плоские функции, `sheet_check` их
    склеивает.
- `rules/triggers_eval.py`: `KnownIds` (dataclass: `npcs`, `locations`, `pantheon: set[str]`; `from_world(world)`);
  `validate_refs(condition, known, registry=None)` — параметр переименован, семантика «объект с `npcs/locations/pantheon`»
  (`WorldState` подходит как раньше).
- `content/models/classes.py`: `StartingKit(ContentModel)`: `id`, `items: list[str]` (повтор = количество), `equip: list[str] = []`,
  `gold_cp: int = 0`; `CharacterClass.starting_kits: list[StartingKit] = []`. Данные — A5. Проверка целостности (все `items`
  находятся `find_item`, `equip ⊆ items`) — тестом контента (как `test_srd_minimum`), не загрузчиком.

### A2. Протокол: режим `hero_sheet`, контекст по задаче
- `protocol/context.py`: `CreationContext(registry, cfg, task)` (3 параметра). Задачи — маленькие классы там же:
  `BackgroundTask(class_id, class_skills=())` → `mode = "hero_background"`; `SheetTask(known: KnownIds, taken_names: list[str],
  feedback: str = "", previous: dict | None = None)` → `mode = "hero_sheet"` (`feedback`/`previous` — путь «переописать с
  замечанием», В3). Атрибуты контекста: `registry`, `cfg`, `task`, `mode = task.mode`, `background = None`, `sheet = None`,
  `marks = []`, `turn_seq = 0`. Тесты Б0 (`test_hero_background.py:27`, `test_hero_session.py`, `test_hero_prompt.py`,
  `test_hero_create.py`, сценарий 6b) переводятся на `CreationContext(registry, cfg, BackgroundTask(...))`.
- `protocol/schema.py`: `HERO_MODES = ("hero_background", "hero_sheet")`; `MODE_TOOLS["hero_sheet"] = ("hero_sheet",)`;
  `own_models`: `mode in HERO_MODES → HERO_MODELS`; группа кэша `"hero"` для обоих. Инструмент strict (как `background_spec`);
  если на живом прогоне Anthropic ответит «compiled grammar is too large» — `NON_STRICT["hero_sheet"] = ("hero_sheet",)`
  (Pydantic валидирует всё равно; прецедент explore) — D4.
- `protocol/requests.py`: общая база `BackgroundFields(Request)` (поля нынешнего `BackgroundSpecRequest` без `type`;
  `BackgroundSpecRequest(BackgroundFields)` добавляет только `type`) — без дублирования. **`HeroSheetRequest(Request)`**,
  `type: Literal["hero_sheet"]`, docstring = описание инструмента; поля плоские, strict-совместимые (без свободных словарей —
  `dict[str, …]` даёт `additionalProperties`-схему, которую strict не принимает):
  `name`, `species_id`, `class_id`, `ability_method: Literal[standard_array, point_buy, explicit]`,
  `ability_scores: AbilityScores` (вложенная модель `str/dex/con/int_/wis/cha: int`, `int_` с `alias="int"` — прецедент
  `NpcStatus.is_`), `bonus_plus2: AbilityOrNone` («none» = схема +1/+1/+1), `bonus_plus1: list[Ability]` (1 или 3),
  `class_skills: list[Skill]`, `weapon_masteries: list[str]`, `fighting_style: str` («» = нет), `class_kit: str` (id набора класса
  из справочника), `spells: list[str]`, `prepared: list[str]`, `species_skill: SkillOrNone`, `species_feat: str` («» = нет),
  `feat_skills: list[str]` (выборы черты предыстории — «Одарённый»: 3 навыка/инструмента; пусто = черта без выборов),
  `species_feat_skills: list[str]` (то же для черты Универсальности), `background: BackgroundFields` (вложенный объект),
  `background_gear: Literal[equipment, gold]`, `motive: str`, `means: list[str]`, `opportunity: list[HeroTriggerSpec]`.
  `HeroTriggerSpec(Request)`: `id`, `then`, `kind: Literal[narrative, flag, hero_has, hero_at, npc_status, attitude, favor]`,
  `ref: str` (текст условия для narrative / имя флага / id предмета, локации, NPC, бога), `status: str` («» = alive; только
  npc_status), `gte: int` (0 = не задан; только attitude/favor). Одно условие на триггер, без `all/any/not` (Q3); `once = true`.
  `NEUTRAL`: `fighting_style ""`, `species_feat ""`, `species_skill "none"`, `bonus_plus2 "none"`, `status ""`, `gte 0`,
  `description ""`. `HERO_MODELS["hero_sheet"]`, `HERO_ADAPTERS = {mode: TypeAdapter}` по двум режимам; `parse_request`:
  `mode in HERO_MODES → HERO_ADAPTERS[mode]`.
- `protocol/handlers/hero.py`: `hero_sheet(ctx, request)`: повтор после принятого → `Invalid("already_done")`;
  `sheet = sheet_from_request(request)` (плоские поля → `HeroSheet`: `ability_scores` в dict, бонус в `background_bonus`,
  `species_choices` из `species_skill/species_feat`, `feat_choices` по ключам `rules.builder.origin_feat_keys(spec,
  species_choices)` из `feat_skills`/`species_feat_skills`, `BackgroundSpec(..., gold_option_cp=5000)`, триггеры через
  `condition_from_spec(spec)` → короткая запись 4.01 (`{"narrative": ref}`, `{"flag": ref}`, `{"hero_has": ref}`,
  `{"hero_at": ref}`, `{"npc_status": {"id": ref, "is": status or "alive"}}`, `{"attitude": {"npc": ref, "gte": gte}}`,
  `{"favor": {"god": ref, "gte": gte}}`) → `Trigger.model_validate({"id", "if", "then", "once": True})`; ошибка pydantic →
  `Invalid("invalid_request", текст)`); затем `codes, messages = sheet_check(sheet, ctx.registry, known=ctx.task.known,
  taken_names=ctx.task.taken_names)` → `Invalid(code=codes[0], message="; ".join(messages))` (модель видит все тексты, как в Б0);
  успех → `ctx.sheet = sheet`, `Decision(status="accepted", log=["Лист героя принят"])`. Три плоские функции.
- `protocol/apply.py`: `HERO_HANDLERS["hero_sheet"] = hero.hero_sheet`; ветка `ctx.mode in HERO_MODES`.
- `master/session.py`: `REQUIRED_BY_MODE["hero_sheet"] = "hero_sheet"`, `SINGLE_SHOT_MODES += ("hero_sheet",)`,
  `EMPTY_NOTES["hero_sheet"] = "Пустой ответ. Вызови инструмент hero_sheet."`. Больше правок нет (ранний выход, `required_tool`
  без бандла — уже сделано в Б0).

### A3. Промпт: `master/hero.py` → `HeroPromptBuilder` (оба режима), `prompts/hero_sheet_rules.md`
- `BackgroundPromptBuilder` переименовывается в `HeroPromptBuilder(app_cfg, model=None)` (роль narrator, `find_role_cfg` как
  сейчас); `build(ctx, user_input, mode, *, world_text="")` ветвится по `mode`: `hero_background` — как в Б0 (читает
  `ctx.task.class_id/class_skills`); `hero_sheet` — system[0] `prompts/hero_sheet_rules.md` (cache), system[1]
  `sheet_reference_block(ctx)` (cache), messages[0] `dump({"description": user_input, "feedback": task.feedback,
  "previous": task.previous})` (`previous` — `HeroSheetRequest`-совместимый словарь прошлого листа при переописании, иначе
  `None`). Префикс system[0..1] байт-в-байт одинаков для разных описаний/замечаний (кэш).
- `sheet_reference_block(ctx)`: справочник предыстории (`reference_block` Б0 как есть) + `classes`: по каждому классу
  `{id, name, skill_options, skill_count, mastery_count, mastery_weapon_ids (оружие с mastery, которым класс владеет —
  weapon_proficient), fighting_style: bool (умение fighting_style на 1 ур.), fighting_style_ids (черты категории
  fighting_style), kits: [{id, items, equip, gold_cp}], spellcasting: {cantrips, spells, prepared} | None, cantrip_ids,
  spell_ids (класс в spell.classes, уровень 1)}`; `species`: `{id, name, choices: species_choice_keys}`; `origin_feats`:
  `{id, picks: feat_choice_count}`; таблицы: `standard_array` (значения), `point_buy` (стоимость + budget), `explicit` 3..20;
  `world`: `{npc_ids, location_ids, god_ids, taken_names}` из `ctx.task` (стабильно в пределах сессии — кэшируется);
  `limits`: `MOTIVE_MAX`, `MEANS_MAX`, `OPPORTUNITY_MAX`, `BACKGROUND_DESCRIPTION_MAX`, `BACKGROUND_BUDGET_CP`. Размер — заметно больше
  справочника Б0 (D3), но в кэше.
- `hero_sheet_rules.md` (коротко, по образцу `background_rules.md`): задача — один вызов `hero_sheet` по описанию игрока,
  лист 1 уровня; имя героя не из `taken_names`; виды/классы/id только из справочника; метод характеристик — любой из трёх
  (стандартный набор — ровно 15,14,13,12,10,8; покупка — по таблице, не больше бюджета; свободный — 3..20, после бонуса ≤ 20);
  бонус +2/+1 или +1/+1/+1 только по трём характеристикам предыстории; навыки класса — `skill_count` из `skill_options`, не
  совпадают с навыками предыстории; мастерства — ровно `mastery_count` из `mastery_weapon_ids`; боевой стиль — только если у
  класса есть; `class_kit` — один id из `kits` класса (набор и деньги даёт движок — В12); предыстория — правила 5.2 как в
  `background_rules.md` (три характеристики, два навыка, инструмент, черта origin, набор ≤ 50 зм, описание ≤ 300);
  заклинания — число заговоров/заклинаний класса, `prepared ⊆ spells` 1 круга и не больше лимита; выборы вида (человек: навык и
  черта origin; «Одарённый» — три выбора); `motive` одно предложение, `means` 1–3, `opportunity` 0–2 триггера — структурные
  с id из `world`, иначе narrative; при `feedback` — менять только то, о чём просит игрок, остальное из `previous`; при
  отклонении — исправить и вызвать снова; по-русски.

### A4. Слой `game`: `hero_create.py` (зависимости объектом, предпросмотр, ручная правка, лист ↔ meta)
- `HeroCreateDeps` (dataclass): `adapter, app_cfg, registry, cfg, journal=None, ledger=None, now=None, model=None,
  adapter_factory=None`. `run_creation(deps, task, description, run_id) -> CreationContext` — общий прогон (`MasterSession(...,
  role="narrator", builder=HeroPromptBuilder(deps.app_cfg, model=deps.model))`, `session.run(ctx, description, apply, task.mode,
  run_id=run_id)`); `propose_background(deps, task, description, run_id) -> BackgroundSpec` (сохраняется для Б2, 4 параметра,
  smell снят); **`propose_hero_sheet(deps, task, description, run_id) -> HeroSheet`** — сбои `TurnFailed` наверх (меню 2.2 — у
  `HeroSession`, A6). `with_background` — удалить (одна строка, потребителя нет и в Б1; Q6). `run_id` — `hero-<stamp>-<n>`.
- `preview_lines(sheet, registry, width) -> list[str]` — показ листа «как `/sheet`»: герой собирается `build_character`
  (лист уже валиден), строки — те же функции `game/sheet_text` (`title_line`, `armor_class(…, now_s=0)`, `ac_text`,
  `equipment_text`, `sheet_stat_lines`, `spell_names`/`slots_lines`, `inv_lines`) + новый `hooks_lines(hero) -> list[str]`
  («Предыстория: <name> — <description>», «Мотив: …», «Средства: …», «Возможности: <id> — <then>»), который использует и
  `cmd_sheet` (хвост Б0 про description — закрывается здесь).
- `edit_sheet(sheet, line) -> HeroSheet | str` — ручная правка «поле = значение» (В3): таблица `SHEET_FIELDS` (ключ → геттер/
  сеттер, значения-списки через запятую): `name, species, class, method, str, dex, con, int, wis, cha, bonus («str+2, con+1»),
  class_skills, masteries, style, kit, spells, prepared, species_skill, species_feat, feat_skills, species_feat_skills, gear,
  bg_name, bg_abilities, bg_skills, bg_tool, bg_feat, bg_equipment, bg_gold, bg_description, motive, means, opportunity`.
  Неизвестное поле/плохой формат → строка ошибки со списком полей; результат — копия `HeroSheet` через `model_validate`
  (ошибка pydantic → её текст). Валидность содержимого проверяет вызывающий тем же `sheet_check` — тексты совпадают с путём
  модели (критерий). `opportunity` руками: пусто — очистить; `«<id>: <условие словами> -> <намерение>»` — narrative-триггер;
  структурные условия — только через переописание ИИ (Q4). `sheet_fields_lines(sheet) -> list[str]` — «поля» с текущими
  значениями для подсказки.
- `write_hero_sheet(saves_root, world_id, sheet)` / `read_hero_sheet(saves_root, world_id) -> HeroSheet | None` —
  `saves/<world>/meta/hero_sheet.json` (рядом с `models.json`; В7, Q8). `creation_cost_line(journal, run_ids) -> str` —
  «Создание героя: $X (N вызовов)» по `journal.records_for(run_ids)` и `money_text` (критерий «цена создания отдельно»).
- `campaign/build.py`: `build_world(..., hero_id=...)` принимает `str | HeroSheet`: `resolve_hero_preset(pack, hero) -> HeroPreset`
  (строка — поиск как сейчас/`ValueError`; лист — `HeroPreset(id=ON_THE_FLY_ID="custom", choices=sheet.choices,
  motive=sheet.motive)`, остальные поля по умолчанию: уровень 1, `location_id=None` → `manifest.start.hero_location` (В13),
  `money_cp=None` → деньги от `build_character` с набором класса); после `build_hero` при листе — `apply_hooks(hero, sheet)`
  (`means`, `opportunity` копиями). `refusal_lines` → `check_hero` остаётся страховкой (имя занято после слияния пака →
  `StartRefused`). `known_ids(pack) -> KnownIds` и `taken_names(pack) -> list[str]` (именованные NPC, боги, фракции пака) —
  здесь же (campaign знает пак; game составляет `SheetTask`). `new_world_from_pack(hero=...)` — без изменения сигнатуры.
- `master/prompt.py` `state_data`: в `hero_data` добавить `means` (если непусто) и `background_description` (если непусто) —
  крючки для мастера (ТЗ 5); opportunity героя мастеру не показывается — её исполняет `world_sim.triggers.check` (владельцы уже
  включают героев: `candidates.owners`, строка 63). В мок-прогоне памяти оба поля пусты → WINDOW не меняется (C).

### A5. Стартовые наборы классов — предложение данных (Q2)
SRD 5.2, адаптация под имеющиеся предметы (нет: булавы, кистеня, дротиков, кольчужной рубахи, книги заклинаний, наборов
взломщика/жреца/учёного — замены ниже; «c» = только золото, как вариант «B/C» SRD). Пресеты паков (`arn`, `liel`, `grey`) не
меняются. Запись в `docs/rules-adaptation.md`.

| класс | id | items (повтор = количество) | equip | gold_cp |
|---|---|---|---|---|
| fighter | a | chain_mail, greatsword, spear, explorers_pack | chain_mail, greatsword | 400 |
| fighter | b | studded_leather, scimitar, shortsword, longbow, arrows, quiver, explorers_pack | studded_leather, longbow | 1100 |
| fighter | c | — | — | 15500 |
| rogue | a | leather_armor, dagger, dagger, shortsword, shortbow, arrows, quiver, thieves_tools, explorers_pack | leather_armor, shortsword | 800 |
| rogue | b | — | — | 10000 |
| cleric | a | studded_leather, shield, quarterstaff, holy_symbol, explorers_pack | studded_leather, shield, quarterstaff | 700 |
| cleric | b | — | — | 11000 |
| wizard | a | dagger, dagger, quarterstaff, robe, explorers_pack | quarterstaff | 500 |
| wizard | b | — | — | 5500 |
| ranger | a | studded_leather, scimitar, shortsword, longbow, arrows, quiver, druidic_focus, explorers_pack | studded_leather, longbow | 700 |
| ranger | b | — | — | 15000 |

### A6. UI (Б1б): `HeroSession`, простой режим, TUI, выбор пресета, CLI
- `ui/hero_session.py: HeroSession(deps, task, width)` — машина состояний создания, не знающая о терминале (образец
  `PlaySession`): `start() -> Step` («Опишите героя словами…»), `submit(line) -> Step` (блоки `note`/`menu` из `ui/screen`,
  цифра при меню → пункт, как `PlaySession.apply_line`). Состояния: `describe` → вызов `propose_hero_sheet` → `review`
  (предпросмотр `preview_lines` + меню «принять / переописать / править») → `remark` (замечание → `task.feedback/previous`,
  новый вызов) / `edit` («поле = значение» через `edit_sheet` + `sheet_check`; «поля» — список; «готово» — назад в `review`;
  ошибки — теми же текстами) → `accept` → `session.sheet`. `TurnFailed` → `error_menu` «повторить / сменить модель / выйти»
  (2.2; `refusal` — `REFUSAL_HINT` из `game/turn.py`); «сменить модель» → `model_choice` (тот же список, что `GameApp.model_options`
  — вынести в общий помощник), проверка через `deps.adapter_factory` (как `GameApp.check_model`), затем снова `error_menu`;
  «выйти» → `Step(quit=True)`, `sheet is None`. `run_id` считает сессия; `run_ids` — для `creation_cost_line`.
- `ui/simple.py`: `emit_blocks(sink, blocks, width)` (из `show_blocks`); `ui/cli.py: create_hero_simple(stdin, stdout, session)` —
  цикл `read → submit → emit_blocks`.
- TUI: `ui/tui/create.py: HeroCreateApp(App)` — отдельный App до основного (как `HeroPickerApp`, Q10): `#feed` (RichLog),
  `#choices` (`Choices`), `#input` (`Entry`), `#status`; ввод/цифры → `session.submit` в thread-worker (как `AiDmApp.start_turn`,
  `strings.THINKING` в статусе, `#input` disabled на время вызова); `return_value` — `HeroSheet | None`; Esc/Ctrl+C — отмена.
  `ui/tui/__init__.py: create_hero(session)` с `TuiStartError` → cli уходит в простой режим (как `pick_hero`). Все строки — в
  `strings.py` (русские; `test_tui_russian` покроет).
- Выбор героя и пресета: `HeroPickerApp(names)` → общий `PickerApp(title, names)` (`tui.pick(title, names)`); `ask_hero` →
  `ask_choice(stdin, stdout, title, names) -> int | None`. Пикер героев: пресеты пака + последний пункт «Создать героя на лету»
  (`strings.CREATE_HERO`); пак без пресетов (`manifest.start.heroes` пуст) — пикер не показывается, сразу создание (В14).
  Пресет мира (В4): меню «Пресет мира:» — «Как в паке» (= `manifest.preset` или тон пака, `PACK_TONE`) + 4 пресета
  `«<name> — <description>»` из `load_presets()`; показывается только при интерактивном старте (нет `--hero`/`--hero-describe`
  и нет `--preset`); порядок: герой (пикер) → пресет → (создание на лету) → мир; Esc/конец ввода на пресете = «как в паке»
  (не отмена) — Q7. Строка «Мир: …, пресет <id>» — как в Б0.
- `ui/cli.py`: `--hero-describe TEXT` (только с `--new`; вместе с `--hero` — код 2; с `--replay` — код 2) — `hero_flag_refusal`
  по образцу `preset_refusal`. Неинтерактивно: `propose_hero_sheet` один раз, валидный лист принимается сам, `TurnFailed` →
  сообщение и код 1 (меню нет). `choose_hero` возвращает `str | HeroSheet | None`; `prepare`: `hero is None` → «Герой не
  выбран» (код 1, как сейчас); `Journal`/`CostLedger` создаются до мира (`world_id` известен — строка 514); при отмене создания
  каталог `saves/<world_id>` без слотов удаляется (Q9); после `new_world_from_pack(hero=sheet)` — `write_hero_sheet` и заметки
  «Герой на лету: <имя>», `creation_cost_line`. Мир создаётся под `hero=sheet` — `app.save_current("auto")` как сейчас.
- Replay (В7): `--replay` без `--hero` берёт лист из `read_hero_sheet`; нет ни того ни другого → подсказка (строки 464–469
  дополняются «--hero или лист героя на лету из meta»); записи `run_id` с префиксом `hero-` исключаются из `records` для
  narrator (`replay_records(records)` в cli; world/summarizer не затронуты); ИИ-вызова создания при replay нет.

### A7. Документы
ARCHITECTURE (`master.hero` → `HeroPromptBuilder`, режимы `HERO_MODES`; `game.hero_create`: deps, `propose_hero_sheet`,
правка, meta; `campaign`: герой на лету, `known_ids/taken_names`; `content`: наборы классов; `ui`: `HeroSession`,
`HeroCreateApp`, `PickerApp`, `--hero-describe`, replay без ИИ-вызова), README/`--help`, `rules-adaptation.md` (наборы A5),
BACKLOG 16 (снять хвост «description в /sheet/промпт»; добавить: TUI создания внутрь основного App; `TurnContext.__init__`
smell — уже там), HANDOFF (статусы Б1а/Б1б, расходы), `docs/plan-b1.md` (Б1б: живой прогон, refusal по В8).

## B. Партии

### Б1а. Модуль, протокол, мок (M/L)
1. `rules/builder.py` — `HeroSheet`, пределы, `class_kit` + `class_kit_problem`/`apply_class_kit`, `sheet_check` +
   `sheet_name_problems` + `sheet_hooks_problems` (A1). 2. `rules/uniqueness.py` `name_taken` (+ в `check_hero`);
   `rules/triggers_eval.py` `KnownIds`, `validate_refs(known)` (A1). 3. `content/models/classes.py` `StartingKit`; данные в
   5 YAML классов (A5); `rules-adaptation.md`. 4. `protocol/context.py` задачи; `requests.py` `BackgroundFields`,
   `HeroSheetRequest`, `HeroTriggerSpec`, адаптеры; `schema.py` `HERO_MODES`; `handlers/hero.py` `hero_sheet`,
   `sheet_from_request`, `condition_from_spec`; `apply.py`; `master/session.py` (A2). 5. `master/hero.py` `HeroPromptBuilder` +
   `prompts/hero_sheet_rules.md` (A3). 6. `game/hero_create.py` — `HeroCreateDeps`, `run_creation`, `propose_background` (новая
   сигнатура), `propose_hero_sheet`, `preview_lines`, `hooks_lines` (+ `cmd_sheet`), `edit_sheet`, `sheet_fields_lines`,
   `write_/read_hero_sheet`, `creation_cost_line`; удалить `with_background` (A4). 7. `campaign/build.py` —
   `resolve_hero_preset`, `apply_hooks`, `known_ids`, `taken_names` (A4). 8. `master/prompt.py` `state_data` — `means`,
   `background_description` (A4). 9. `vulture_allowlist.py`: снять `with_background`, `background_problems` (если у неё нет
   потребителя — удалить функцию: `sheet_check` и `background_check` покрывают); `propose_background` — оставить с пометкой «Б2»
   (Q6). 10. ARCHITECTURE, BACKLOG 16.

Тесты Б1а (doeba; общий kit `tests/unit/game/hero_kit.py`: `sheet_call(call_id, **changes)` — канонический валидный вызов
`hero_sheet` (человек-воин, `standard_array`, набор `a`, предыстория как в `spec_call` Б0, motive/means, 1 narrative-триггер),
`sheet_task(pack)`, `deps(...)`; переиспользуется protocol/master/game/ui-тестами и сценарием):
- `tests/unit/rules/test_sheet_check.py` (новый): валидный лист → `([], [])`; каждая группа кодов по одному случаю: ошибка
  `build_character` (стандартный набор не тот → `standard_array_invalid`, текст как у `build_character`); `point_buy` > 27;
  `explicit` 21; бонус не по характеристикам предыстории; навык класса = навык предыстории (текст `SKILL_CONFLICT_MESSAGE`,
  **один раз**, не дубль из `background_check`); `background_tool_unknown`/`description_too_long`/`background_gold_negative`
  попадают из `background_check`; пустое имя; имя занято (регистр/пробелы — через `name_taken`); motive пуст; means 0 и 4;
  opportunity 3; повтор id; `npc_status` с неизвестным NPC → текст `validate_refs`; `hero_at` с известной локацией — ок;
  порядок сообщений стабилен; `known=None` — ссылки не проверяются.
- `tests/unit/rules/test_builder.py` (+): `class_kit="a"` у воина → предметы набора в инвентаре, надето `equip`, деньги =
  предыстория + `gold_cp` набора; `class_kit` неизвестен → `class_kit_unknown` с перечнем; `class_kit=None` — регресс
  (пресеты `arn/liel/grey` собираются как раньше, `test_game_starter`). `test_uniqueness.py` (+): `name_taken`;
  `check_hero` прежние тексты. `test_triggers_eval.py` (+): `validate_refs` с `KnownIds` и с `WorldState` — одинаковые тексты.
- `tests/unit/content/test_class_kits.py` (новый): у каждого из 5 классов ≥ 1 набор, id наборов уникальны, все `items`
  находятся `find_item`, `equip ⊆ items`, надеваемое — только armor/weapon/shield; `gold_cp ≥ 0`; герой каждого класса с
  набором `a` собирается `build_character` (минимальные choices по классу).
- `tests/unit/protocol/test_hero_sheet.py` (новый): `tool_set("hero_sheet")` — один strict-инструмент, схема без `$ref`, **ни
  у одного объекта нет `additionalProperties` кроме `false`** (нет свободных словарей), описание из docstring; `parse_request`
  в режиме принимает только `hero_sheet`, `background_spec` в `hero_sheet` и `hero_sheet` в `hero_background`/`explore` не
  разбираются; `apply` в чужом режиме → `not_available_in_mode`; хендлер: валидный → `ctx.sheet` заполнен (`choices.class_kit`,
  `background_bonus`, `species_choices`, `feat_choices` по `origin_feat_keys`, `Trigger` с `once=True`), второй вызов →
  `already_done`; невалидные → `Invalid` с кодом первого и всеми текстами через «; »; триггер `attitude` без `gte` → ошибка
  разбора; `kind=npc_status` без `status` → `is: alive`; `previous`/`feedback` не влияют на хендлер; `CreationContext(registry,
  cfg, BackgroundTask(...))` — регресс `test_hero_background.py`; `test_schema_cache_group` — группа `hero` для обоих режимов.
- `tests/unit/master/test_hero_sheet_prompt.py` (новый): system — ровно 2 блока, оба `cache=True`, system[0] = файл правил
  (упоминает `hero_sheet`), system[1] содержит 5 классов с `kits`, `skill_options`, `mastery_weapon_ids` (у воина есть
  `longsword`, у волшебника нет), `spell_ids` волшебника только 1 круга, 4 вида с `choices` (человек: `skill`, `feat`),
  `origin_feats` с `picks`, таблицы `standard_array`/`point_buy`, `world` из задачи, `limits`; messages[0] — описание, feedback
  и previous; префикс одинаков для двух описаний и для описания с замечанием; `hero_background` — регресс
  `test_hero_prompt.py` через `HeroPromptBuilder`. `test_hero_session.py` (+): `hero_sheet` — один вызов модели при валидном,
  ранний выход, `EMPTY_NOTES` называет `hero_sheet`. `test_master_rules.py` (+): `hero_sheet_rules.md` содержит имена всех трёх
  методов характеристик и слово `class_kit`.
- `tests/unit/game/test_hero_create.py` (+): `propose_hero_sheet(deps, task, …)` → `HeroSheet`; журнал: роль narrator,
  `run_id` `hero-…`, `turn_seq 0`; `TurnFailed` наверх; `preview_lines` — есть имя, вид/класс, КД, предметы набора,
  «Мотив:», «Средства:», «Возможности:» и описание предыстории; `edit_sheet`: `name = Ило`, `str = 16` (method explicit),
  `bonus = dex+2, con+1`, `means = а, б`, `opportunity =` (очистка), `opportunity = o1: герой узнаёт о сестре -> отомстить`
  (narrative), неизвестное поле → список полей, плохое число → текст; после `edit_sheet` `sheet_check` даёт **тот же текст**, что
  путь модели с тем же дефектом; `write/read_hero_sheet` round-trip; `creation_cost_line` считает только `hero-` записи.
  `test_sheet_description.py`/`test_game_commands.py` (+): `/sheet` показывает описание предыстории, мотив, средства.
- `tests/unit/campaign/test_pack_build.py` (+): `build_world(hero_id=sheet)` — герой в `lame_goose` (манифест), id `hero`,
  `means`/`opportunity` перенесены, `motive` из листа, деньги с набором; имя как у именованного NPC пака → `StartRefused`
  (страховка); `known_ids(pack)`/`taken_names(pack)` (`vale`, mini-pack из `campaign_kit`); `hero_id="arn"` — регресс.
- `tests/unit/master/test_master_hero_data.py` (+): `means`/`background_description` в `hero_data` только когда непусты.
- **Сценарий `tests/scenarios/test_stage6b_done.py`** (критерий, без CLI): `ScriptedAdapter`: вызов `hero_sheet` с
  `standard_array` не тем набором и именем NPC пака → `tool_result is_error` с обоими текстами → валидный → `HeroSheet`;
  `edit_sheet(…, "class_skills = perception, acrobatics")` при навыке предыстории `acrobatics` → `sheet_check` → текст
  `SKILL_CONFLICT_MESSAGE` = текст модели для того же дефекта; `edit_sheet(…, "name = Ило")` → `[]`; мир
  `new_world_from_pack(hero=sheet, preset_id="heroic")` → один мок-ход (`GameApp`) → `save_current` → `load_slot` → герой: имя,
  класс, набор, `motive/means/opportunity` целы, `world.tone` = пресет; журнал: 2 записи `hero-…` + записи хода; `/cost` —
  леджер narrator пополнен обоими; `refusal` при создании → `TurnFailed("refusal")`; 3 невалидных подряд →
  `TurnFailed("invalid")` (бюджет 2 повтора). `test_stage6b_background.py` — остаётся (регресс Б0, новые сигнатуры).
- `test_architecture`: `master/hero.py` не импортирует `game` (есть); добавить сторож «`campaign` не импортирует `protocol`/`master`».

### Б1б. UI (TUI + простой), выбор пресета, CLI, живой прогон (M)
1. `ui/hero_session.py` (A6). 2. `ui/simple.py` `emit_blocks`; `ui/cli.py`: `--hero-describe`, `hero_flag_refusal`,
   `choose_hero` (пикер с пунктом «на лету», В14), `choose_preset`, `ask_choice`, `create_hero`/`create_hero_simple`,
   `replay_records`, `write_hero_sheet`, заметки старта, удаление каталога при отмене. 3. `ui/tui/modals.py` `PickerApp`;
   `ui/tui/create.py` `HeroCreateApp`; `ui/tui/__init__.py` `pick`, `create_hero`; `strings.py`. 4. `game/app.py` —
   `model_options` вынести в помощник, общий с `HeroSession`. 5. README/`--help`, ARCHITECTURE (ui), HANDOFF. 6. **Живой прогон**
   (пользователь): `ai-dm --new --campaign vale` (TUI) → пресет `grim` → «Создать героя на лету» → описание → лист → правка
   одного поля → принять → 10–15 ходов → `/cost` (строка создания и ходы) → `/save`, перезапуск `--world` → `/sheet`; то же
   через `--hero-describe` в простом режиме; фиксация refusal (В8) и цены в `docs/plan-b1.md`.

Тесты Б1б (doeba):
- `tests/unit/ui/test_hero_session.py` (новый, `ScriptedAdapter`): `start` — блок с подсказкой; описание → `review` с
  предпросмотром и меню из 3 пунктов; «1» (принять) → `sheet`, `Step.quit`; «2» → ввод замечания → второй вызов модели с
  `feedback`/`previous` в messages[0]; «3» → `edit`: «поля» — список, «name = Ило» → «принято», дефект → тот же текст, что у
  модели, «готово» → `review`; невалидный первый ответ модели → повтор внутри `MasterSession`, в `Step` ничего лишнего;
  `TurnFailed("invalid")` → меню 2.2 (3 пункта), «1» → новый `run_id`; `refusal` → `REFUSAL_HINT`; «2» → список моделей →
  выбор → `adapter_factory` вызван (`FactorySpy`), снова меню 2.2; «3» → `quit`, `sheet is None`; цифра вне меню → «Нет такого
  варианта»; `run_ids` растут.
- `tests/unit/ui/test_cli_hero_describe.py` (новый, `cli(...)` + мок-скрипт `tests/fixtures/scripts/hero_sheet.yaml` — первый
  шаг вызов `hero_sheet`, затем текст): `--new --hero-describe "..." --mock` → код 0, заметки «Герой на лету: …» и «Создание
  героя: $…», `meta/hero_sheet.json` есть, слот `auto` с героем листа; `--hero-describe` без `--new` → 2; с `--hero` → 2; с
  `--replay` → 2; скрипт с `refusal` первым шагом → код 1 и текст без меню; `--replay --world w --seed N` без `--hero` при
  `hero_sheet.json` → повтор без расхождения (`ReplayAdapter` narrator не получает записи `hero-…`); без meta и без `--hero` →
  подсказка; `--preset grim` + `--hero-describe` → тон пресета.
- `tests/unit/ui/test_ui_cli.py` (+): `ask_choice` (регресс `test_ask_hero_*` через новое имя); интерактив: `ScriptedInput(["4",
  "Описание…", "1"])` для `vale` (4 = «Создать героя на лету») в простом режиме с мок-скриптом → мир с героем листа; пак без
  пресетов (mini-pack `campaign_kit` без `heroes`) → без пикера сразу «Опишите героя»; `test_cli_preset.py` (+): интерактивный
  старт без `--preset` и без `--hero`: `ScriptedInput(["1", "2"])` → пресет `heroic` в заметках и `world.tone`; конец ввода на
  пресете → «как в паке» (тон пака); с `--hero arn` вопроса о пресете нет (регресс всех прежних `cli([...])`).
- `tests/unit/ui/tui/test_tui_create.py` (новый, Pilot, `asyncio.run`, без сна, адаптер-барьер как `GateAdapter`): ввод
  описания → статус «Мастер думает…», `#input` disabled → после ответа лист в `#feed` и меню в `#choices`; «1» → `return_value`
  — `HeroSheet`; Esc → `None`; меню 2.2 при сбое; русский (`test_tui_russian` расширить на `HeroCreateApp`/`PickerApp`);
  `test_tui_entry_points.py`: `PickerApp` (регресс `HeroPickerApp`-тестов), пункт «Создать героя на лету» последний, пак без
  пресетов — пикера нет; сбой `tui.create_hero` → одна заметка и простой режим (как `test_hero_screen_failure_falls_back…`).
- `tests/scenarios/test_stage6b_done.py` (+): путь через `main([...--simple-подобный ScriptedInput...])` и через
  `HeroCreateApp` (Pilot) с одним и тем же скриптом дают один `core_dump` героя (образец `test_stage5_tui`).

## C. Качество (каждый шаг)
`make cov` ≥ 94%, `make smells` ≤ 202 (бюджет: −1 за `propose_background`, +0 за новый код — см. A0.2; `TurnContext.__init__`
не трогаем), `make dead` (allowlist — Q6), `make mutate FUNCS="…" TESTS="…"` по изменённым функциям из diff.
- Б1а FUNCS: `ai_dm.rules.builder:sheet_check`, `ai_dm.rules.builder:sheet_name_problems`, `ai_dm.rules.builder:sheet_hooks_problems`,
  `ai_dm.rules.builder:class_kit_problem`, `ai_dm.rules.builder:apply_class_kit`, `ai_dm.rules.builder:build_character` (только
  новые строки), `ai_dm.rules.uniqueness:name_taken`, `ai_dm.rules.uniqueness:check_hero`, `ai_dm.rules.triggers_eval:validate_refs`,
  `ai_dm.protocol.handlers.hero:hero_sheet`, `ai_dm.protocol.handlers.hero:sheet_from_request`,
  `ai_dm.protocol.handlers.hero:condition_from_spec`, `ai_dm.protocol.requests:parse_request`, `ai_dm.protocol.schema:own_models`,
  `ai_dm.protocol.schema:tool_defs`, `ai_dm.protocol.apply:apply`, `ai_dm.master.hero:HeroPromptBuilder.build`,
  `ai_dm.master.hero:HeroPromptBuilder.sheet_reference_block`, `ai_dm.master.session:MasterSession.empty_note`,
  `ai_dm.master.prompt:PromptBuilder.state_data` (новые строки), `ai_dm.game.hero_create:run_creation`,
  `ai_dm.game.hero_create:propose_hero_sheet`, `ai_dm.game.hero_create:preview_lines`, `ai_dm.game.hero_create:hooks_lines`,
  `ai_dm.game.hero_create:edit_sheet`, `ai_dm.game.hero_create:creation_cost_line`, `ai_dm.game.hero_create:read_hero_sheet`,
  `ai_dm.campaign.build:resolve_hero_preset`, `ai_dm.campaign.build:apply_hooks`, `ai_dm.campaign.build:known_ids`,
  `ai_dm.campaign.build:taken_names`, `ai_dm.campaign.build:build_world` (новые строки). TESTS — каталоги `tests/unit/{rules,
  protocol,master,game,campaign}` + сценарий.
- Б1б FUNCS: `ai_dm.ui.hero_session:HeroSession.start`, `…:HeroSession.submit`, `…:HeroSession.choose`, `…:HeroSession.propose`,
  `…:HeroSession.edit`, `ai_dm.ui.cli:choose_hero`, `ai_dm.ui.cli:choose_preset`, `ai_dm.ui.cli:ask_choice`,
  `ai_dm.ui.cli:create_hero`, `ai_dm.ui.cli:create_hero_simple`, `ai_dm.ui.cli:hero_flag_refusal`, `ai_dm.ui.cli:replay_records`,
  `ai_dm.ui.cli:prepare` (новые строки), `ai_dm.ui.simple:emit_blocks`, `ai_dm.game.app:GameApp.model_options` (вынос).
  `ui.tui.*` — mutmut не гонять (segfault, BACKLOG 16), только Pilot-тесты. Выжившие на старых строках — в BACKLOG 16.
- **WINDOW мока (`memory_script.py`, 22070): оценка — без изменений.** `narrator_rules.md` и `world_block` (system[0..1]
  нарратора) Б1 не трогает; новые поля `hero_data` (`means`, `background_description`) добавляются только при непустых значениях,
  а у героя мок-прогона памяти (`make_bundle`) они пусты; справочник `hero_sheet` живёт в другом билдере. Doeba подтверждает
  `test_stage4_memory` зелёным в Б1а (шаг 8) и в Б1б; если сдвиг всё же есть — подобрать и записать причину (как Т2–Б0).
- Ревью мамы-кабана — каждая партия. Расходы и решения — HANDOFF / `docs/plan-b1.md`, `docs/plan-b1.md`.

## D. Риски
1. **Наборов классов нет в контенте** (A0.5) — без A5 решение В12 невыполнимо; данные — в первом шаге Б1а, адаптация замен
   на подтверждение (Q2). Если Q2 «нет» — модель называет `inventory` id из справочника (как в предыстории), риск повторов растёт.
2. **Strict-схема `hero_sheet`** крупнее всех прежних (вложенная предыстория + список триггеров): возможен отказ грамматики
   Anthropic («compiled grammar is too large») — только на живом прогоне (Б1б). Запасной путь готов: `NON_STRICT` для режима
   (A2), Pydantic валидирует.
3. **Справочник system[1] большой** (классы, заклинания, наборы, таблицы, мир) — цена первого вызова выше, далее кэш; на живом
   прогоне записать токены создания (`/cost`, журнал `hero-…`). Если id заклинаний/оружия модель путает — подбор по имени
   (B0 риск 5) остаётся в бэклоге.
4. **Replay** мира с героем на лету: `meta/hero_sheet.json` обязателен, записи `hero-…` фильтруются; мир, созданный до Б1б
   (нет meta), требует `--hero`. Репорты (`--replay-report`) не затронуты (журнал хода, не старта).
5. **Отмена создания** оставляет `saves/<world_id>/journal` (вызовы уже записаны) — удаляем каталог без слотов (Q9); иначе
   `--world id` даст «Нет автосохранения».
6. **Пресет-меню и существующие тесты CLI**: меню показывается только при интерактивном старте без `--hero` — все прежние
   `cli([... "--hero", "arn" ...])` остаются; тесты `ask_hero` получают новое имя `ask_choice` и второй ответ/конец ввода.
7. **Refusal при создании** — авто-репорт не пишется (нет мира и `TurnRunner`), есть только журнал `hero-…` с `stop_reason`;
   фиксация по В8 — руками в `docs/plan-b1.md`. Если на `grim` (романтика 4) Gemini откажет уже на создании — меню 2.2
   «сменить модель» проверяется этим же прогоном.
8. **Имя героя vs слияние пака** — проверка на уровне инструмента по `taken_names` пака; `check_hero` в `refusal_lines` остаётся
   страховкой (например, пак с NPC без `named`, но с совпадающим именем — конфликта нет, как у пресетов).
9. **`build_character` (сложность 176)** — одна проверка и один вызов добавляются; не раздувать: наборы — в `apply_class_kit`.
10. Объём Б1б: TUI-создание — отдельный App с worker-потоком; Pilot-тесты с барьером (`GateAdapter`) уже есть как образец.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1.** `CreationContext`: не «разгружать атрибуты», а **обобщить по задаче** (`BackgroundTask`/`SheetTask`, A2); smell на
  `TurnContext.__init__` не трогать (старый код, BACKLOG 16). Альтернатива — пытаться чистить `TurnContext` (вне Б1).
- **Q2.** Стартовые наборы классов — **добавить в контент по таблице A5** (SRD 5.2, замены: кистень/дротики → копьё, булава →
  посох, кольчужная рубаха → клёпаная кожа, наборы взломщика/жреца/учёного → набор путешественника, книга заклинаний — нет;
  вариант «только золото» как в SRD). Альтернатива — модель называет предметы сама из справочника (риск 1).
- **Q3.** Opportunity героя в инструменте — **плоские триггеры: одно условие на триггер, виды narrative / flag / hero_has /
  hero_at / npc_status / attitude / favor, `once`** (strict-схема не рекурсивна; `all/any/not` — только из паков). Альтернатива —
  только narrative.
- **Q4.** Ручная правка opportunity — **очистка и narrative-триггеры «id: условие -> намерение»**, структурные — переописанием
  через ИИ. Альтернатива — правка только через ИИ.
- **Q5.** Пределы: motive ≤ 200, means 1–3 по ≤ 120, opportunity 0–2, `then` ≤ 200, описание предыстории ≤ 300 (как Б0) — **да**.
- **Q6.** `hero_background`/`propose_background` — **оставить до Б2** (пошаговый режим: класс руками, предыстория словами),
  `propose_background` в allowlist с пометкой «Б2»; `with_background` и `background_problems` удалить (поглощены). Альтернатива —
  удалить режим целиком и вернуть в Б2.
- **Q7.** Порядок интерактивного старта: **пикер героя (с пунктом «на лету») → меню пресета → создание → мир**; меню пресета
  только без `--hero`/`--hero-describe`/`--preset`; Esc/конец ввода на пресете = «как в паке». Альтернатива — пресет строго
  перед пикером героя (тогда прежние тесты `ask_hero` меняются сильнее, смысл тот же).
- **Q8.** «Журнал старта» для replay (В7) — **файл `saves/<world>/meta/hero_sheet.json`** (рядом с `models.json`; журнал
  вызовов хранит только вызовы модели, записи `hero-…` остаются для `/cost`). Альтернатива — запись иной формы в `calls-*.jsonl`
  (ломает потребителей записей: `ReplayAdapter`, `records_for`, `mark_turn`).
- **Q9.** При отмене создания удалять `saves/<world_id>`, если в нём нет слотов — **да**.
- **Q10.** TUI создания — **отдельный `HeroCreateApp` до основного App** (как `HeroPickerApp`; внутрь — Б2 по BACKLOG 16).
- **Q11.** `/sheet` и промпт: описание предыстории, мотив, средства героя показывать (хвост Б0 Q4) — **да** (A4).
- **Q12.** Живой прогон Б1б: пресет **`grim`** (романтика 4) на модели по умолчанию (Gemini) и, при refusal, смена на Claude через
  меню 2.2; итог — `docs/plan-b1.md`, пресет помечается «зависит от провайдера» в `presets.yaml` (`description`).

Технические умолчания на аппрув вместе с планом: id пресета героя на лету — `"custom"` (в текстах `StartRefused`); `run_id`
`hero-<stamp>-<n>`; `taken_names` — именованные NPC, боги, фракции пака; `known_ids` — NPC, локации, боги пака; триггеры героя
`once=True`; `class_kit` — поле `CharacterChoices` (схема пака, не сейва; v8 остаётся); `--hero-describe` при валидном листе не
показывает предпросмотр (только заметка «Герой на лету: <имя>»); при `--mock` без tty интерактив идёт через `ScriptedInput`,
как сейчас.

## Решения проектировщика по плану (2026-10-08)
Q1–Q12 — все по рекомендациям (наборы классов по таблице A5; плоские триггеры; правка opportunity — очистка + narrative;
порядок «герой → пресет → создание»; лист для replay — meta/hero_sheet.json; удалять пустой каталог мира при отмене;
живой прогон — grim на Gemini, refusal → Claude через 2.2). Технические умолчания приняты вместе с планом.

## Решения: Груминг партии Б1 — «Герой на лету, ИИ-путь» (свинопас, 2026-10-08) (бывш. docs/decisions/b1-grooming.md)

Источники: roadmap-r4-unified (#2 Б1, риски), ROADMAP-PLAN (Б-2, риск 9, критерий Б1 стр. 310), stage6-grooming (В6,
правка 6б), b0-grooming, B0-PLAN (разд. D риски 5–8), b0-audit, BACKLOG 16 (хвост Б0), TZ 3/5/5.2/6, код Б0.

### Готовность

**Готова к плану после ответов на В1–В7** (блокируют В1, В2, В3; остальное — с умолчаниями). Б0 принят, механизм
одного strict-инструмента (`hero_background`, `CreationContext`, ранний выход SINGLE_SHOT, `background_check`/
`background_problems` для Б-2) есть и переиспользуется. Версия сейва — v8, новая не нужна (motive/means/opportunity
у `HeroState` уже есть: state/hero.py:99–101), если не будет принято В5б.

### Что есть в коде (факты)

- `game/hero_create.py`: `propose_background` (13 параметров, smells), `with_background` — потребителя нет, в
  vulture_allowlist до Б1.
- `protocol/context.py:85` `CreationContext.__init__` (9 параметров/атрибутов, smells), режим жёстко `hero_background`.
- `rules/builder.py`: `CharacterChoices` (имя, вид, класс, предыстория `str | BackgroundSpec`, метод характеристик,
  навыки, мастерство, стиль, инвентарь, заклинания, prepared, feat_choices, …) и `build_character` → `HeroState |
  ValidationErrors` — готовый валидатор листа 1 ур.
- Старт нового мира: `ui/cli.py:548` `hero = args.hero or choose_hero(...)` — герой только id пресета пака;
  `new_world_from_pack(..., hero=<id>, preset_id=args.preset)`. Выбор героя: TUI `HeroPickerApp` (отдельный App) /
  простой `ask_hero` (меню чисел).
- Пресет мира — только флаг `--preset`, интерактивного выбора нет.
- `HeroPreset` пака задаёт `motive`, но не `means`/`opportunity`; `campaign/build.py` переносит только `motive`
  (поправка к stage6-grooming: «build.py заполняет их из пресета» — заполняется лишь motive).
- make smells 202/202 — запаса нет; Б1 обязан сначала разгрузить `propose_background`/`CreationContext`.

### Короткое ТЗ

**Цель.** Новый мир можно начать героем, описанным словами: ИИ предлагает лист 1 ур. (с предысторией и
motive/means/opportunity), движок валидирует, игрок подтверждает или правит, герой входит в мир. В TUI и простом режиме.

**Входит.**
1. Режим протокола (ВЗ: новый `hero_sheet` или расширение `hero_background`) — один strict-инструмент «лист героя»:
   поля `CharacterChoices` (уровень 1) + `BackgroundSpec` + motive/means/opportunity. Ошибки валидатора (`build_character`,
   `background_problems`) возвращаются модели как отказ инструмента, повтор в пределах лимита сессии; после — меню 2.2.
2. Рефакторинг под smells: параметры `propose_*` в объект (напр. зависимости сессии), `CreationContext` — меньше
   аргументов/обобщение по режиму. smells ≤ 202 после партии.
3. Подтверждение/правка: показ листа (как `/sheet`), действия «принять / переописать (новый вызов ИИ с замечанием) /
   ручная правка полей». Любая ручная правка — тем же валидатором (Б-2), те же тексты ошибок, что у пути модели.
4. Точка входа: при новом мире выбор «герой пака … / создать на лету» (TZ 5.2); в TUI — в существующем пикере,
   в простом — пункт меню. CLI без интерактива — см. В6.
5. Сборка мира из `CharacterChoices` + motive/means/opportunity без `HeroPreset` пака: стартовая локация из манифеста,
   проверки уникальности id/имени героя против NPC (TZ 5.3), `check_hero`.
6. Пресет мира выбирается интерактивно при новом мире (ВЗ — В4).
7. Журнал/`/cost`: вызов создания под ролью narrator, `run_id hero-…` (как Б0); replay мира с героем на лету (В7).
8. Снять `propose_background`/`with_background` из vulture_allowlist (или удалить, если поглощены).

**Не входит.** Пошаговый режим и выбор метода характеристик вручную (Б2); HeroPickerApp внутрь основного App и
заставка (Б2); продолжение мира/наследник (Н1); import (Б3); поля пресета в сейве (М0); подбор id по имени (B0 риск 5 —
только если живой прогон покажет).

**Готово, когда.**
- Сценарий на моке `test_stage6b_done` (ИИ-путь): описание → невалидный лист → отказ → валидный → правка руками с
  ошибкой (тот же текст) → подтверждение → мир → ход → сейв/загрузка (герой и motive/means/opportunity целы).
- Простой режим и TUI проходят путь (тест на каждый).
- make smells ≤ 202, make dead чисто, mutmut по новым функциям по правилам партии.
- **Живой прогон** (ROADMAP-PLAN стр. 310): новый мир, герой на лету, пресет мира с романтикой 4, 10–15 ходов,
  `/cost` (цена создания отдельно), сейв/загрузка, фиксация refusal (риск 9; B0 риск 8 — Gemini).

### Риски

1. Модель не знает id предметов/заклинаний/черт → много повторов и цены (B0 риск 5); на листе полей больше, чем у
   предыстории — справочник id в system[1] растёт.
2. Refusal на «откровенно» (4) — не баг Б1, но критерий требует фиксации и решения (риск 9) — см. В8.
3. smells 202/202: без рефакторинга в первом шаге любая новая функция ломает ворота.
4. Replay: создание героя — ИИ-вызов до мира; без записи в журнал replay расходится (как с `--preset`, B0 риск 7).
5. Объём L: при росте плана резать на Б1а (модуль+протокол+мок) и Б1б (UI+живой прогон).

### Развилки — вопросы проектировщику (рекомендация первой)

- **В1 [блок.] Режим протокола.** **(а) новый режим `hero_sheet`** с одним инструментом, предыстория — вложенное поле
  (один вызов, одна цена); (б) два вызова: лист без предыстории + существующий `hero_background` (переиспользование,
  но две цены и согласование навыков между вызовами).
- **В2 [блок.] Характеристики на ИИ-пути.** **(а) ИИ выбирает метод из трёх (TZ 6: «все три доступны и при создании
  на лету»)**, валидатор проверяет; (б) только стандартный набор, остальное — Б2.
- **В3 [блок.] Ручная правка — какие поля.** **(а) все поля `CharacterChoices` + предыстория + motive/means/opportunity,
  простым редактором «поле = значение» с валидатором**; (б) только имя/motive/means и переописание словами, полный
  редактор — Б2 (пошаговый режим и так даёт поле за полем).
- **В4 Пресет мира интерактивно.** **(а) да, в Б1 — экран/меню выбора перед героем (иначе живой прогон с пресетом
  только через `--preset`)**; (б) оставить `--preset`, интерактив — Б2.
- **В5 opportunity героя.** **(а) ИИ даёт motive + 1–3 means + 0–2 opportunity в формате Trigger 4.01, движок
  валидирует условия как у NPC**; (б) только motive+means, opportunity пусто. Отдельно: добавить ли `means`/
  `opportunity` в `HeroPreset` пака — **нет, не в Б1** (новое поле пака, не сейва; в BACKLOG).
- **В6 CLI без интерактива.** **(а) `--hero-describe "<текст>"` — ИИ-путь с автоподтверждением при валидном листе
  (нужно для живого/скриптового прогона)**; (б) только интерактив.
- **В7 Replay мира с героем на лету.** **(а) герой (итоговый `CharacterChoices`) пишется в журнал старта, replay берёт
  его оттуда без ИИ-вызова**; (б) replay такого мира не поддерживается, документировать.
- **В8 Refusal на живом прогоне.** Если романтика 4 даёт refusal: **(а) зафиксировать в decisions, меню 2.2 работает —
  партия принята, пресет «откровенно» помечается провайдер-зависимым**; (б) refusal блокирует приём Б1 до решения.
- **В9 Модель роли создания.** **(а) narrator (как Б0)**; (б) отдельная роль `creator` в конфиге (дешевле модель, но
  narrator-quality-over-cost — против).

Решения за проектировщика, молча не принятые: деление Б1а/Б1б; формат CLI-флага; поведение при refusal.

### Аудит свекрови (2026-10-08)

**Что проверено:** этот файл против roadmap-r4-unified (стр. 53, Б1), stage6-grooming (п. 9–10, В6, В8), TZ 2.2/5/5.2/5.3/6
(стр. 507–508), b0-audit, BACKLOG 16; код: state/hero.py, campaign/build.py, campaign/models.py `HeroPreset`,
ui/cli.py:548, rules/builder.py, game/hero_create.py, protocol/context.py.

**Источники истины:** строка Б1 роадмапа, ТЗ 5/5.2/5.3/6, b0-audit (UI выбора пресета отнесён к Б1).

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| motive/means/opportunity у `HeroState` есть, v8 хватает | state/hero.py:99–101 | код | верно |
| build.py переносит только motive; `HeroPreset` без means/opportunity | build.py:69, models.py:88 | код | верно |
| `cli.py:548 hero = args.hero or choose_hero(...)` | ui/cli.py | код | верно |
| `build_character → HeroState \| ValidationErrors`, `background_problems` | rules/builder.py:196, 121 | код | верно |
| «`propose_background` 13 параметров» | hero_create.py:7 | код: 12 параметров | неточно, поправить или указать, что 13 насчитал smells |
| «`CreationContext.__init__` 9 параметров/атрибутов» | context.py:87 | код: 4 параметра (registry, cfg, class_id, class_skills), 8 атрибутов | **ошибка**: smells ругается на атрибуты, а не на параметры. Пункт 2 «Входит» («меньше аргументов») целится не туда, переформулировать до плана |
| п. 6: интерактивный выбор пресета мира | Входит | b0-audit («UI выбора — Б1»), вынесен в В4 | оставить как вопрос; учесть, что это расширение строки роадмапа |
| п. 2: рефакторинг под smells | Входит | BACKLOG 16 (решение «разгрузить в Б1») | оставить |
| В6 `--hero-describe` (новый CLI-флаг) | Развилки | ниоткуда в ТЗ/роадмапе; мотив — скриптовый живой прогон | к пользователю (вопрос задан правильно) |
| В7 replay | Развилки | stage6-grooming п. 10, B0 риск 7 | оставить |
| В9 роль narrator | Развилки | stage6 В6 (рекомендация), Б0 так сделал, память narrator-quality | можно не спрашивать повторно, если В6 этапа 6 уже принят; иначе — к пользователю |
| В5 opportunity в формате Trigger | Развилки | ТЗ 5 («герою тоже задаются мотив/средства/возможности»), 4.01 | оставить |

**Лишнего сверх роадмапа/ТЗ:** не найдено; пресет-UI (п. 6) и CLI-флаг (В6) честно вынесены в вопросы.

**Упущенные развилки (добавить вопросами):**
1. **id и имя героя на лету**: кто задаёт id (движок из имени / модель), что при конфликте с NPC (ТЗ 5.3) — отказ модели
   и повтор или переименование игроком. Сейчас п. 5 лишь «проверки», без решения.
2. **Стартовое снаряжение и деньги**: `HeroPreset` даёт `inventory_extra/equipped/money_cp`; на ИИ-пути — от класса/
   предыстории по SRD, или выбирает модель? Прямо связано с риском 1 (id предметов).
3. **Стартовая локация**: «из манифеста» записано как факт, а не вопрос; при пресете героя `location_id` бывает своё —
   проверить, что манифест её всегда задаёт.
4. **Пак без героев-пресетов**: в нём меню выбора или сразу ИИ-путь.
5. **Лимит повторов** «в пределах лимита сессии» — какой; влияет на цену (риск 1).

**Рекомендации В1–В9:** разумны и прослеживаются (В2а прямо из ТЗ 6 стр. 508; В8а не противоречит риску 9, но это
продуктовое решение о приёмке — правильно оставлено пользователю). В3а (полный редактор) заметно раздувает объём L —
при В3а деление Б1а/Б1б почти неизбежно; стоит сказать это в вопросе.

**Решения за пользователя:** молча не принято. Но деление Б1а/Б1б, формат CLI и поведение при refusal перечислены одной
строкой в конце, без рекомендаций — оформить их нумерованными вопросами (В10 деление: рекомендую решать сразу, а не
«при росте плана», т.к. В3а+В4+В5а уже дают рост). Строка «Готовность»: «после ответов на В1–В7 (блокируют В1, В2, В3)»
противоречива — привести к одному списку блокирующих.

**Итог:** продуктовых решений за проектировщика нет, лишнего нет. Перед передачей папе-кабану: исправить факт о
`CreationContext` (атрибуты, не параметры) и счёт параметров `propose_background`; добавить упущенные развилки 1–5 и
В10 (деление). Нужны решения пользователя: В1–В10.

### Решения проектировщика (2026-10-08)
Все по рекомендациям:
- В1 — один режим `hero_sheet` (лист + предыстория). В2 — любой из 3 методов характеристик (ТЗ 6). В3 — ручная правка всех полей через тот же валидатор.
- В4 — интерактивный выбор пресета мира в Б1. В5 — opportunity героя 0–2 триггера, проверка как у NPC; means/opportunity в HeroPreset пака — в BACKLOG.
- В6 — флаг `--hero-describe` с автоподтверждением. В7 — replay берёт итоговый лист из журнала старта. В8 — refusal на романтике 4 фиксируется, партия принимается, пресет помечен как зависящий от провайдера.
- В9 — роль narrator. В10 — делить: Б1а (модуль, протокол, мок), Б1б (UI, выбор пресета, живой прогон).
- В11 — имя даёт ИИ, id генерирует движок; совпадение имени с NPC — ошибка валидатора. В12 — снаряжение и деньги: стандартный набор от движка по классу/предыстории, ИИ выбирает только из предложенных вариантов.
- В13 — стартовая локация из манифеста. В14 — пак без героев-пресетов: сразу ИИ-путь. В15 — 2 повтора валидатора, затем меню 2.2.
- Поправки фактов по аудиту: `CreationContext.__init__` — 4 параметра, 8 атрибутов (разгружать атрибуты); `propose_background` — 12 параметров.

## Правки по ревью: Ревью Б1а (бывш. docs/decisions/b1-a-review.md)

### Решения проектировщика
1. vulture_allowlist до Б1б: временно внесены имена без потребителей в Б1а (группа «Б1а → снять в Б1б»); поля AbilityScores con/int_/wis/cha — постоянно (поля схемы).
2. `build_world` для листа героя: до `collect_conflicts` проверка `name_taken(hero.name, taken_names(pack))`, занято → `StartRefused`.
3. `HERO_HANDLERS` и `HERO_MODELS` разложены по режимам; `apply` берёт обработчики по `ctx.mode` (чужой инструмент → `not_available_in_mode`).
4. Ручная правка `opportunity` заменяет весь список (принято до Б1б); в подсказке поля это сказано; правка по id — BACKLOG (Б1б).
5. Пределы — только в `limits` справочника (`means_item_max`, `opportunity_then_max` и др.); числа из `hero_sheet_rules.md` убраны, правила ссылаются на ключи `limits`.
Прочее: `KnownIds.from_world` удалён; `AbilityScores.str` → `str_` (alias `str`); SRD-предыстория (строка) в `sheet_fields_lines`/`background_field` даёт «—» без TypeError.

## Правки по ревью: Ревью Б1б (бывш. docs/decisions/b1-b-review.md)

### Решения проектировщика
1. Кодовые имена пресетов мира (2026-10-08): поле `codename` в presets.yaml (heroic — «Властелин колец», grim — «Ведьмак»,
   romantic — «Сумерки», fairytale — «Хроники Нарнии»); показывается только в меню пресета
   «<name> (в духе «<codename>») — <description>»; в tone/промпт рассказчика не передаётся.
2. В-5: смена модели в меню 2.2 при создании героя может выбрать другого провайдера; смешение с world/summarizer
   допустимо (нужно для Q12: grim на Gemini → Claude при refusal). Запись в models.json — BACKLOG 16.
3. В-3: строки HeroSession остаются в ui/hero_session.py (без textual); проверка «русские строки» — отдельным тестом.

### Отступления kaban от плана (приняты ревью)
choose_hero → id | NEW_HERO | None (создание в prepare); choose_number с кортежем menu (smells); строки HeroSession
в ui/hero_session.py; расход создания в app.ledger.session_lines; «Как в паке»/Esc → preset=None без заметки;
текст отказа --replay дополнен.

### Замечания мамы-кабана → правки
1. (блокер) pyproject.toml `[tool.mutmut]` выборка тестов сужена — вернуть `["tests/"]`.
2. Пустой `--hero-describe` → отказ в hero_flag_refusal (код 2).
3. discard_world — только в ветке нового мира.
4. Не мутировать args.preset в prepare (локальная переменная).
5. HeroCreateApp: исключения сессии кроме TurnFailed — как в AiDmApp.
6. Мелочи: явное состояние model_choice; «поля» одним блоком raw.

### Итог правок kaban
Правки 2–6 внесены; smells 202/202. П.5: HeroSession ловит только TurnFailed, прочие исключения роняют HeroCreateApp
(в игре их ловит PlaySession) — оставлено как есть; защита в HeroSession.submit — кандидат в BACKLOG 16.

### Тесты и mutmut (kaban-doeba)
mutmut по функциям Б1б: 1058 мутантов, 53 выживших → 16 (все эквивалентны/недостижимы, разбор в отчёте doeba:
model_dump mode, ключи меню при 3 пунктах, remark≈None, partition/rpartition, known= при narrative-правке, регистр SLOTS).
Старые выжившие → BACKLOG 16: cli.make_game_adapter mutmut_15, cli.prepare mutmut_568 (opening только без --mock).
Расхождения с планом: `previous` в SheetTask — вложенная форма model_dump(by_alias), а не плоская HeroSheetRequest (A3);
ветка «пак без пресетов героя» (В14) недостижима через loader (требует ≥1 пресет) — покрыта юнитом на заглушке.

## Итог: Аудит партии Б1 (кабан-свекровь, 2026-10-09) (бывш. docs/decisions/b1-audit.md)

**Что проверено:** `git diff f5f7cbc..c6caa33` (Б1а b128324, Б1б c6caa33; 70 файлов, +6897/−233): код src/, данные
(`srd/data/classes/*.yaml`, `presets.yaml`), промпт `hero_sheet_rules.md`, vulture_allowlist, README, ARCHITECTURE,
BACKLOG, HANDOFF, rules-adaptation, список тестов критерия. Прогнано: `make smells` = 202/202, `make dead` чисто,
pyproject.toml в диффе не меняется (блокер мамы-кабана с `[tool.mutmut]` снят). Ответы пользователя сверены по журналам сессий
(AskUserQuestion и реплики), а не по пересказу оркестратора.

**Источники истины:** `docs/plan-b1.md` (В1–В15, ответы через AskUserQuestion), `docs/plan-b1.md` (Q1–Q12 и технические
умолчания, ответы через AskUserQuestion), `docs/plan-b1.md` (решения 1–5: ответы пользователя есть),
`docs/plan-b1.md` (решение 1 codename: реплика пользователя и «всё правильно»; решения 2–3 (В-5, В-3): ответы через AskUserQuestion).

### Находки по важности

| # | Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|---|
| 1 | `previous` при «переописать» уходит модели как `HeroSheet.model_dump(by_alias)`, то есть во вложенной внутренней форме. План (A3, стр. 136) требует словарь, совместимый с `HeroSheetRequest`. Промпт говорит модели: «previous (прошлый лист в виде аргументов hero_sheet)». Промпт расходится с данными, и расхождение ударит именно по пути «изменить только то, о чём просит игрок» | ui/hero_session.py:67, master/prompts/hero_sheet_rules.md | отступление от плана; «принято» только строкой в отчёте doeba (b1-b-review), пользователь не решал | **к пользователю** (до живого прогона): привести к плану или принять и поправить текст промпта |
| 2 | Ветка В14 («пак без пресетов героя — сразу ИИ-путь») недостижима: loader отказывает паку без героев («нужен хотя бы один пресет героя», loader.py:335). Решение пользователя В14 формально реализовано, но его не может увидеть ни один пользователь, а тест работает на заглушке | campaign/loader.py:335, ui/cli.py choose_hero | В14, но без правки loader; факт записан в b1-b-review, в BACKLOG его нет | **к пользователю**: снять ограничение loader (вне плана Б1) или принять и записать в BACKLOG |
| 3 | «Старые выжившие → BACKLOG 16: cli.make_game_adapter mutmut_15, cli.prepare mutmut_568» — в BACKLOG этого нет (grep пуст) | docs/BACKLOG.md | b1-b-review утверждает, что перенесено | в BACKLOG (дописать) |
| 4 | Защита `HeroSession.submit` от исключений, кроме TurnFailed (TUI-создание падает на прочих ошибках). Замечание мамы-кабана п.5 оставлено «кандидатом» и в BACKLOG не внесено | ui/hero_session.py, ui/tui/create.py | ревью | в BACKLOG |
| 5 | Расход создания героя добавлен в `app.ledger.session_lines`, то есть входит в сессионные лимиты цены. kaban сделал это сам, ревью приняло, пользователю о факте сообщили, но не спросили | game/app.py / ui/cli.py | ниоткуда (отступление kaban). Согласуется с духом плана: «/cost — леджер narrator пополнен обоими» | оставить; довести до сведения (поведенческое, но малое) |
| 6 | `check_model` вынесен из `GameApp` вместе с `model_options`, хотя план (Б1б п.4) называет только `model_options` | game/app.py | нужен для меню 2.2 в HeroSession (В-5) | оставить |
| 7 | Прочие отступления kaban (choose_hero → id/NEW_HERO/None, кортеж menu, Esc на пресете → «как в паке» без заметки, дополненный текст отказа `--replay`) | ui/cli.py | ревью | оставить: техника и UX-мелочи, в рамках Q7 |
| 8 | codename пресетов: поле, 4 значения, показ только в меню | campaign/presets.py, presets.yaml | просьба пользователя. Решение «не в промпт» — допущение оркестратора, которое пользователь подтвердил («всё правильно»). Агентам задачу отдали **до** этого подтверждения | оставить; процессная заметка ниже |
| 9 | Стартовые наборы классов: данные и замены | srd/data/classes/*.yaml, rules-adaptation.md | Q2, таблица A5. Золото сверено с SRD 5.2 (воин 4/11/155 зм, плут 100, жрец 110, волшебник 55, следопыт 150) | оставить |
| 10 | Режим `hero_background`, `propose_background`, `BackgroundTask` оставлены в allowlist с пометкой «Б2»; `with_background`/`background_problems` удалены | vulture_allowlist.py | Q6 | оставить |
| 11 | Поля `AbilityScores` (con/int_/wis/cha/str_) постоянно в allowlist | vulture_allowlist.py | решение 1 Б1а | оставить |
| 12 | `MODE_TOOLS["hero_sheet"]`, `HERO_MODES`, обработчики по режимам | protocol/* | В1 и решение 3 Б1а | оставить, лишнего обобщения нет: 2 режима, 2 потребителя |
| 13 | smells 202/202, запаса нет (после Б1а было 201) | — | бюджет плана ≤202 соблюдён | оставить; риск для Б2, см. ниже |

Лишних абстракций «на будущее», незапрошенного контента и новых зависимостей, CI или плагинов не нашла. Каждая
нетривиальная добавка прослеживается к В/Q, к решениям ревью или к реплике пользователя, кроме находок 1, 2 и 5.

### Решения за пользователя

- **Находка 1 (`previous`)**: оркестратор и doeba записали расхождение с утверждённым планом как факт «Расхождения с
  планом» и закоммитили. Утверждённую форму поменяли без вопроса пользователю.
- **Находка 2 (В14)**: решение пользователя фактически не действует. Об этом записано, но вопрос не задан.
- **Находка 5**: о факте пользователю сказали («стоит знать заранее»), но не спросили. Решение малое, я его принимаю как есть.
- Процесс (codename): реализацию запустили по допущению оркестратора до подтверждения пользователя. На этот раз
  пользователь подтвердил, так что вреда нет. На будущее: сначала подтверждение, потом агентам.
- Ответы на В-5 и В-3, решения 1–5 Б1а, В1–В15, Q1–Q12 подтверждены журналами: это решения пользователя.

### Критерий Б1 (без живого прогона)

- Мок `test_stage6b_done`: описание → невалидный лист (оба текста) → валидный → правка с тем же текстом ошибки → имя
  NPC отклонено как у модели → мир → ход → сейв/загрузка (`core_dump` равен) → журнал `hero-…` → `/cost` → refusal/invalid:
  **есть**.
- Простой режим и TUI проходят путь одним скриптом с одинаковым героем (`test_tui_and_simple_creation_give_the_same_*`): **есть**.
- smells ≤ 202 (202), dead чисто: **есть**. mutmut: по отчёту doeba 16 выживших, все эквивалентны. Не перепроверяла.
- **Не сделано (ожидаемо):** живой прогон, `docs/plan-b1.md`, пометка `grim` «зависит от провайдера» (Q12/В8, после прогона).

### Что вынести проектировщику

1. `previous` (находка 1): **рекомендую до живого прогона привести к плану** (форма `HeroSheetRequest`, как в промпте).
   Альтернатива: оставить вложенную форму и поправить текст промпта.
2. В14 (находка 2): **рекомендую принять как есть и записать в BACKLOG** «loader: пак без пресетов героя → разрешить, когда
   появится такой пак». Альтернатива: ослабить loader сейчас (выходит за план Б1).
3. Проба fable у papa-kaban: решить, продлевать ли (оценка ниже).

### Что в BACKLOG (16)

- выжившие `cli.make_game_adapter mutmut_15`, `cli.prepare mutmut_568` (обещано в b1-b-review, не внесено);
- защита `HeroSession.submit` / HeroCreateApp от исключений, кроме TurnFailed;
- В14 недостижима через loader (если проектировщик примет п.2 как есть);
- smells 202/202 без запаса: Б2 (пошаговый режим, `propose_background`) потребует разгрузки в первом шаге.

### Проба fable у papa-kaban (Б1)

- **План лучше?** Да. План подробный и проверяемый: таблица наборов A5, плоские триггеры, полный список FUNCS для mutmut,
  поимённые тесты, риски с запасными путями (NON_STRICT при большой грамматике, WINDOW мока). Технические умолчания вынесены
  отдельно на аппрув, развилки Q1–Q12 поставлены как вопросы с рекомендацией. Все 12 приняты по рекомендации.
- **Меньше дозадач?** Нет. Б1а: 4 вопроса пользователю из ревью (проверка имени в build_world, обработчики по режимам,
  отступающие от формы A2, замена списка opportunity, пределы в limits). Это пробелы плана. Б1б: 7 отступлений kaban, 2 вопроса
  пользователю (В-5, В-3), блокер mutmut в pyproject, конфликт имён тестовых файлов, расхождение `previous` и мёртвая В14.
  План не учёл, что loader требует пресет героя, хотя `loader.py` был в его списке чтения. Дозадач примерно столько же, сколько в Б0.
- **Цена:** ~257 тыс. (Б0: ~177 тыс.) при партии L против M.
- **Вывод:** тот же, что в Б0: план качественнее, но дозадач не меньше. Продлевать ли пробу, решает проектировщик. Довод
  против: две партии подряд без выигрыша по дозадачам. Довод за: прочие сбои на стыке плана и кода (loader, форма `previous`)
  ловит ревью, а не план.

**Итог:** лишнего контента и абстракций нет, smells/dead в норме. Нужны решения пользователя по п.1 (`previous`) и п.2 (В14)
до живого прогона. В BACKLOG 16 нужно дописать 3–4 пункта, обещанных или найденных.

### Решения проектировщика по аудиту (2026-10-09)
1. `previous` при «переописать» — привести к плану (A3): словарь в форме HeroSheetRequest (аргументы hero_sheet) + тест. До живого прогона.
2. В14 — принять как есть (loader требует ≥1 пресет героя), в BACKLOG.
3. fable у papa-kaban — оставить (качество плана важнее цены).
Выполнено: previous = request_from_sheet (+trigger_spec), тесты круга, mutmut новых функций — 0 выживших (trigger_spec упрощён); хвосты аудита — BACKLOG 16.

## Итог: Б1: живой прогон проектировщика (2026-10-09) (бывш. docs/decisions/b1-live.md)

Чек-лист: checklist-b1-live.md. Мир: vale-1e54eae8, рассказчик claude-sonnet-5-5.

### Итог по чек-листу
- Пройдено всё, кроме `/cost` (цифр нет). Создание героя (оба режима), «Переописать»/«Править», меню отказа,
  сейв и загрузка, `--hero-describe` — ок.
- Отказов на Sonnet нет; Gemini не пробовался.
- Цена по meta/costs.jsonl: создание героя ≈ $0,041 + $0,013 (2 вызова), первый ход ≈ $0,075 (запись кэша 1 ч),
  обычный ход ≈ $0,017–0,027.

### Репорты
#### t5 — текст мастера повторяется дважды (saves/vale-1e54eae8/issues/20261009T083041-t5-manual)
Причина найдена. Ответ 1: рассказ + `offer_choices` (stop_reason tool_use). Ответ 2 после результата инструмента:
модель пишет тот же рассказ заново, перефразируя (правило 3 «Порядок работы» в narrator_rules.md: «только после
результатов напиши повествование»). `MasterSession.finish` склеивает тексты всех раундов → дубль.
Варианты исправления:
- (а, рекомендация) код: если в раунде приняты только «немеханические» инструменты (`offer_choices`) и текст уже
  есть — ход завершается без завершающего вызова (как SINGLE_SHOT_MODES). Убирает дубль и экономит вызов на ходу.
- (б) промпт: «`offer_choices` вызывай в том же ответе, что и рассказ; после его результата рассказ не повторяй».
  Дешевле, но не гарантирует.

#### t6 — после перезагрузки нет текста мастера, только выбор (…/20261009T084251-t6-manual)
Не воспроизведено: `--world vale-1e54eae8` на копии сейва и в простом режиме, и в TUI (headless) показывает рамку
с последним рассказом. Но рассказ хода 6 — всего две фразы («Ты спустился в подвал…»): модель отдала механику
(`advance_time`, `offer_choices`) без текста, а финальный ответ сделала куцым. Вопрос проектировщику — см. ниже.

### Замечено попутно (не в репортах)
- Ход 2: в рассказ протекли рассуждения модели («Игрок торгуется, поэтому проверим убеждение через движок…
  haggle не годится»), нарушение «не раскрывай служебные данные».
- Ход 4–5: Гарт дал флягу настойки только рассказом (без `give_item`), «выпью настойку» прошло без `use_item`.
- Тон мира — пресет «героическое фэнтези», хотя в чек-листе отмечен «Суровый мир».

### Решения проектировщика (2026-10-09)
1. t5 — вариант (а): ход завершается без завершающего вызова, если в раунде только `offer_choices` и текст есть.
2. t6 — загрузка была через `/load` в игре. Подтверждено: `render_step` для `/load` добавляет только меню, без рассказа.
3. Попутные пункты — завести (BACKLOG 35) и чинить в этой же партии. Пресет в прогоне выбран grim → пункт 5 — баг.

### Итоги партии «Б1-фикс» (2026-10-09)
- пп. 1–4 (BACKLOG 35) сделаны: ранний выход после `offer_choices` с текстом (FREE_TOOLS), рассказ после `/load`,
  правки narrator_rules («Порядок работы», «Сюжетные предметы»).
- п. 5 (пресет grim → тон heroic): цепочка проверена, в мир пришёл preset_id heroic, причина вне кода; код не менялся.
  Следы при повторе: строка «Мир: …, пресет …» и chronicle kind=tone. Вопрос пользователю: пресет выбирался цифрой или кликом?
- Риск: репорты/журналы до Б1-фикс не воспроизводятся через --replay на ходах текст+offer_choices.

Ответ пользователя по п.5 (2026-10-09): пресет выбирался цифрой. Гипотеза «хвостового» клика мыши отпадает; тесты PickerApp по цифрам зелёные. Остаётся сверить строку «Мир: …, пресет …» в следующем живом прогоне.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- Б1 расходы: svinopas ~39 тыс.; kaban-svekrov ~24 тыс.; papa-kaban (fable) ~257 тыс. (~18 мин).
- Б1б: kaban ~157+163 тыс. (~25 мин); kaban-doeba ~229 тыс. (~2 ч, mutmut); mama-kaban ~43 тыс.
- Б1а: kaban ~188 тыс. (~27 мин, вкл. правки ревью); kaban-doeba ~381 тыс. (~2,8 ч, mutmut); mama-kaban ~64 тыс. (3 прохода).
