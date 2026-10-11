# План партии Б1: «Герой на лету, ИИ-путь» — Б1а (модуль, протокол, мок) и Б1б (UI, пресет, живой прогон)

Автор: папа-кабан, 2026-10-08. Статус: **предложение на аппрув** (решения проектировщика В1–В15 из
`decisions/b1-grooming.md` обязательны и приняты за основу). Основа: `decisions/b1-grooming.md` (ТЗ свинопаса, аудит свекрови,
решения), `B0-PLAN.md` (форма, A4–A6), `decisions/roadmap-r4-unified.md` (#2 Б1), `ROADMAP-PLAN.md` (критерий Б1, стр. 310),
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
smell — уже там), HANDOFF (статусы Б1а/Б1б, расходы), `decisions/b1-live.md` (Б1б: живой прогон, refusal по В8).

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
   через `--hero-describe` в простом режиме; фиксация refusal (В8) и цены в `decisions/b1-live.md`.

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
- Ревью мамы-кабана — каждая партия. Расходы и решения — HANDOFF / `decisions/b1-a-review.md`, `b1-b-review.md`.

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
   фиксация по В8 — руками в `decisions/b1-live.md`. Если на `grim` (романтика 4) Gemini откажет уже на создании — меню 2.2
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
  меню 2.2; итог — `decisions/b1-live.md`, пресет помечается «зависит от провайдера» в `presets.yaml` (`description`).

Технические умолчания на аппрув вместе с планом: id пресета героя на лету — `"custom"` (в текстах `StartRefused`); `run_id`
`hero-<stamp>-<n>`; `taken_names` — именованные NPC, боги, фракции пака; `known_ids` — NPC, локации, боги пака; триггеры героя
`once=True`; `class_kit` — поле `CharacterChoices` (схема пака, не сейва; v8 остаётся); `--hero-describe` при валидном листе не
показывает предпросмотр (только заметка «Герой на лету: <имя>»); при `--mock` без tty интерактив идёт через `ScriptedInput`,
как сейчас.

## Решения проектировщика по плану (2026-10-08)
Q1–Q12 — все по рекомендациям (наборы классов по таблице A5; плоские триггеры; правка opportunity — очистка + narrative;
порядок «герой → пресет → создание»; лист для replay — meta/hero_sheet.json; удалять пустой каталог мира при отмене;
живой прогон — grim на Gemini, refusal → Claude через 2.2). Технические умолчания приняты вместе с планом.
