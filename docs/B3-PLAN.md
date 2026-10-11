# План партии Б3: «import пака» — команда `--import`, пак без героя, хвосты п. 30, `test_stage6b_done` полностью

Автор: папа-кабан, 2026-10-09. Статус: **предложение на аппрув** (решения проектировщика В1–В11 и Г1–Г2 из
`decisions/b3-grooming.md`, разделы «Решения проектировщика», обязательны и приняты за основу). Основа: `decisions/b3-grooming.md`
(ТЗ свинопаса, аудит свекрови, догруминг), `B2-PLAN.md`/`B1-PLAN.md` (форма, A0, Q-умолчания), `decisions/roadmap-r4-unified.md`
(#4 Б3), `ROADMAP-PLAN.md` (стр. 167–173, 311, 337), `BACKLOG.md` 16 (в), 30, `TZ.md` 3 / 4 / 5.3 / 13, HANDOFF («Инструменты
качества», «Правила экономии»). Код на main 438d517: `campaign/{loader,uniqueness,build,merge,models,presets}.py`, `ui/cli.py`,
`ui/hero_session.py` (`RetryMenu`, `menu_number`), `game/hero_create.py` (`HeroCreateDeps`, `run_creation`, `creation_cost_line`),
`master/{hero,session,prompt}.py`, `protocol/{context,schema,apply,requests}.py`, `protocol/handlers/hero.py`
(`HeroTriggerSpec`, `condition_from_spec`), `config/app.py` + `app_defaults.toml`, `llm/journal.py`, `core/clock.py`,
`persistence/{store,migrations/m0003}.py`, тесты `tests/unit/{campaign,protocol,master,game,ui,config}`, kit-ы `campaign_kit`/
`hero_kit`/`master_kit`/`ui_kit`, `tests/scenarios/test_stage6b_done.py`, `test_stage6b_background.py` (`spec_call`),
`tests/unit/master/test_master_prompt.py` (тесты префикса).

**Критерий Б3 (груминг «Готово», п. 7 + догруминг):** мок `test_stage6b_done`: (1) import — мок-выжимка → невалидный `pack`
(битая ссылка + конфликт 5.3) → отказ инструмента строками «файл: поле: что не так» → валидный → файлы в `campaigns/<id>/` →
`load_pack` без ошибок, `collect_conflicts` пуст → новый мир из этого пака с героем на лету → ход → сейв/загрузка; повторный import в тот
же id — отказ, файлы целы; 3 невалидных подряд → меню 2.2, на диске ничего; refusal → подсказка и меню; (2) три невалидные предыстории
подряд с разными нарушениями → `invalid`, две + валидная → проходит; (3) пресет `grim` → абзац пресета в кэшируемом блоке system → два
хода → префикс байт-в-байт; (4) п. 30: тестовый мир с другим `campaign_id` → мутанты `campaign_registry`/`pack_npc_trade` (ветка `None`);
`make smells` ≤ 205, `make dead` чисто, mutmut по новым функциям; живой прогон по В10а + Г1а/Г2а (`decisions/b3-live.md`). Сейв
**остаётся v8**: import пишет файлы пака, схема сейва не меняется; новой версии пака нет (состав файлов — подмножество нынешнего).

**Принято из решений:** пак без пресета героя допустим, старт — только героем на лету/пошагово (В1а; отменяет Б2 В11а и закрывает
BACKLOG 16 (в)); состав — campaign, world, truths, npcs, factions, pantheon, locations; `events.yaml`, `start/`, `heroes/` не пишутся
(В2а); форма — флаг `ai-dm --import <файл> --campaign <id>`, несовместим с игровыми флагами (В3а); ошибки `load_pack`/ссылок/5.3 →
назад модели, бюджет повторов как у Б1 (`retry.invalid_retries` = 2, т.е. до 3 попыток), после — меню 2.2; на диск только валидный пак
(В4а); один strict-инструмент `pack` со всеми файлами (В5а); роль модели — см. Q1 (В6а: текст и буква расходятся); журнал import в
`campaigns/<id>/.import/`, цена — строкой в выводе (В7а); id занят → отказ с подсказкой, `--force` нет (В8а); `[import] max_chars`,
превышение — отказ до вызова (В9а); живой прогон — import реальной выжимки → правка руками → мир → 3–5 ходов → `/report` →
`--replay-report` + проверка refusal на `grim` (В10а, Г1а не блокирует, Г2а); одной партией M (В11а).

**Не входит:** существа/монстры в паке (`combat`, `monsters` — BACKLOG 2 → Ж4); `events.yaml`, `heroes/`, `start/`, `content/`;
import внутрь идущего мира; правка существующего пака; `--force`; subparsers `ai-dm import`; TUI для import (команда вне игры —
только консольный вывод, Q11); календарь, `mortality`, `natural_events`, `nudge`, `flags`, `preset` в манифесте (движок по умолчанию,
пользователь правит руками — ТЗ 3); условия `all/any/not`, `npc_at`, `time_after`, `event_active`, `hero_dead` в триггерах из import
(только плоские, как Б1 Q3 — Q10); генерация пресета героя из выжимки (В1б отвергнут); обобщение `pick_world`/`pick_summarizer`.

## A0. Поправки фактов (проверено по коду и `qlty smells`, 2026-10-09)
1. **`make smells` = 204 при лимите 205** (перепроверено, запас 1). `campaign/loader.py` **уже помечен** файловым флагом «High total
   complexity (137)» плюс `entity_refs` (23) и `check_pack_refs` (22) — правки loader не добавляют файлового smell, но функции не
   раздувать. `ui/cli.py` — 3 smells (`main` 8 параметров, `make_summarizer_adapter` и `hero_flag_refusal` по 6 return), файлового
   флага нет. `game/hero_create.py`, `master/hero.py`, `protocol/handlers/hero.py`, `protocol/requests.py` — 0. Правило Б1/Б2:
   новый код +0 (≤ 4 именованных параметра + `*`, ≤ 5 return, диспетчеры таблицей, без вложенности 5, без замыканий).
2. **В6 в решении: «В6а (новая роль `import`)»**, но в груминге буква (а) = роль `world`, а новая роль — (в). Буква и текст расходятся —
   Q1. План ниже исходит из текста (новая роль), потому что роль `world` (`gemini-3.5-flash-lite`, `max_tokens` 4000) физически не
   выдаст пак размером с `drunk_dragon` (npcs.yaml 33 КБ ≈ 13 тыс. токенов).
3. **`MasterSession.run(ctx, text, executor, mode, run_id=)` принимает исполнитель** — Б1 передаёт `protocol.apply.apply`, `WorldSession`
   — свой. Значит проверка пака (диск + `load_pack` + 5.3) может жить в слое `game` как обёртка над `apply`, а `protocol` остаётся без
   импорта `campaign` (сторожа `test_protocol_hero_handler_does_not_import_upper_layers_or_campaign`, `test_campaign_does_not_import_
   upper_layers` сохраняются). `CreationContext(registry, cfg, task)` уже «контекст без бандла» — хватает одного нового поля.
4. **`load_pack` работает только с каталогом на диске** (читает файлы, `check_manifest` + `check_pack_refs` + `check_hero`); **5.3 в нём
   нет** — `collect_conflicts(world, heroes, pack)` вызывается из `build.py:169` и `merge.py:41`. «Пак грузится без ошибок 5.3» =
   `load_pack(dir)` + `collect_conflicts(WorldState(пустой), [], pack)` с пустым списком конфликтов. Поэтому кандидат пишется в
   **staging-каталог** и проверяется настоящим загрузчиком; на успехе каталог переименовывается в `campaigns/<id>` (атомарно, одна ФС).
5. **Плоские условия Б1 переиспользуемы:** `HeroTriggerSpec` (`id, then, kind, ref, status, gte`) и `condition_from_spec(spec)` →
   короткая запись 4.01 (`{"flag": name}`, `{"npc_status": {...}}` …), которую `Trigger`/`Secret.reveal_if` принимают (так пишут паки:
   `campaign_kit.default_files`). `Condition` рекурсивен (`all/any/not`) — в strict-схему не влезает (Б1 A0.6); import даёт только плоские.
6. **`RetryMenu(deps, leave_label)`** нужны лишь `deps.app_cfg/adapter/model/adapter_factory` — ровно поля `HeroCreateDeps`; список
   моделей в меню — `model_options(app_cfg)` (модели рассказчика) — для import тот же список годится (Q6).
7. **`Journal(saves_root, world_id, cfg)`** пишет в `<root>/<world_id>/journal/calls-NNN.jsonl` + `blobs/`; `Journal(staging, ".import",
   cfg)` даёт `campaigns/<id>/.import/journal/…` без нового формата (В7а дословно «calls.jsonl + блобы» — фактическая раскладка
   `journal/calls-001.jsonl` + `journal/blobs/`, техническое умолчание). `records_for(run_ids)` читает по пути `Journal.dir` — строку цены
   считать **до** переименования staging.
8. **Сценарий п. 30 достижим без нового кода:** `m0003` ставит `campaign_id = "vale"` миру с `world_id` вида `vale-*` и `campaign_id: null`
   (`migrations/m0003_v2_to_v3.py:95–97`); фикстуры `tests/fixtures/saves/v2…v7` имеют `campaign_id: null`, `world_id: old_world`.
   Копия фикстуры с `world_id` → `vale-old` даёт `peek_campaign_id == None`, а `bundle.world.campaign_id == "vale"` → ветка `cli.py:646–649`.
   Пак с `campaign_id` без каталога (`ghost`) → `pack_npc_trade` → `None` → предупреждение миграции (Т0) и «Пака ghost нет … без догрузки».
9. **`pick_narrator(args, …)`** при `not args.new` зовёт `stored_narrator(saves_root, args.world)` — с `args.world is None` упадёт
   (`Path / None`). Прецедент: `--replay` ставит `args.new = True` (`cli.py:611–612`) — import делает так же.
10. **Дата без календаря:** `default_calendar()` = 12 месяцев по 30 дней (`core/clock.py`); `check_manifest` проверяет `start.date`
    через `GameClock.from_date` — модели даётся формат и пределы в справочнике.
11. **Тон пресета в промпте:** `PromptBuilder.world_block` (system[1], `cache=True`) кладёт `world.tone.model_dump()` — абзац пресета
    (`notes` + оси) живёт в кэшируемом блоке; тесты префикса `test_master_prompt.py:311–335` (`build`, `make_ctx`, `second_turn_ctx`) —
    образец для теста (3) критерия. `test_master_prompt.py` пресет не применяет ни разу (grep `preset` пуст — догруминг прав).
12. **`--import` и `import` — ключевые слова:** `argparse` → `dest="import_file"`; поля pydantic → `import_` с `alias="import"`
    (прецедент `NpcStatus.is_` / `alias="is"`). Тестов на main — 11 632.

## A. Архитектура

### A1. Протокол: режим `pack_import`, инструмент `pack`, конвертер в файлы
- `protocol/requests.py`: `IMPORT_MODE = "pack_import"`. Модели (все `Request`, strict-совместимые: без свободных словарей, без `$ref`
  на рекурсию; `NEUTRAL` для «пусто = нет»):
  - `SecretSpec(Request)`: `id`, `text`, `kind: Literal[narrative, flag, hero_has, hero_at, npc_status, attitude, favor]`, `ref`,
    `status ""`, `gte 0` — те же поля условия, что у `HeroTriggerSpec` (отдельная модель, чтобы не менять схему `hero_sheet` Б1).
  - `PackLocation(Request)`: `id`, `name`, `parent_id ""`, `description ""`, `connections: list[ConnectionSpec]` (есть, стр. 105).
  - `PackNpc(Request)`: поля `npc_create` (`id, name, means, named, key, motive "", location_id "", trade_kind "none"`) +
    `species_id ""` + `opportunity: list[HeroTriggerSpec]` + `secrets: list[SecretSpec]`.
  - `PackFaction(Request)`: `id, name, motive "", means, members (id NPC), regions (id локаций), opportunity`.
  - `PackGod(Request)`: `id, name, domains, role "", motive "", pleased_by, angered_by, rivals (id богов), means, realm "",
    servants (id NPC), opportunity`.
  - `PackStart(Request)`: `date` («YYYY-MM-DD»), `time "08:00"`, `hero_location` (id своей локации), `chapter_number 1`,
    `chapter_title ""`, `scene_summary ""`.
  - `PackRequest(Request)`: `type: Literal["pack"]`, docstring = описание инструмента; `name`, `start: PackStart`, `tone: Tone`
    (вложить `state.world.Tone` как есть — один источник осей; strict сделает все поля required, пустые списки/строки = «не задано»),
    `world_text`, `truths ""`, `locations: list[PackLocation]`, `npcs: list[PackNpc]`, `factions: list[PackFaction]`,
    `pantheon: list[PackGod]`. `id`/`version` манифеста модель **не** выдаёт — их ставит движок (`--campaign`, `"1"`).
  - `IMPORT_MODELS = {"pack": PackRequest}`, `IMPORT_ADAPTER = TypeAdapter(PackRequest)`; `parse_request`: `if mode == IMPORT_MODE`.
- `protocol/schema.py`: `MODE_TOOLS[IMPORT_MODE] = ("pack",)`; `own_models`: `mode == IMPORT_MODE → IMPORT_MODELS`; группа кэша
  `tool_defs`: `{"world": "world", IMPORT_MODE: "import"}.get(mode, "summarize")`. Strict — да (В5а); запасной путь
  `NON_STRICT[IMPORT_MODE] = ("pack",)` готов на случай «compiled grammar is too large» на живом прогоне (Б1 D4; Q7).
- `protocol/handlers/pack.py` (новый): плоские функции **без диска и без `campaign`**: `trigger_data(spec)` →
  `{"id", "if": condition_from_spec(spec), "then", "once": True}`; `secret_data(spec)` → `{"id", "text", "reveal_if": condition_from_spec(spec)}`;
  `location_data`, `npc_data`, `faction_data`, `god_data` — словари **только с заданными полями** (None/пустое выбрасывается, чтобы
  YAML был чистым, как у `vale`); `tone_data(tone)`; `manifest_data(request, campaign_id)` → `{"id", "name", "version": "1", "start":
  {...}, "tone": {...}}`; `files_from_request(request, campaign_id) -> dict[str, object]` с ключами `campaign.yaml, world.md, truths.md,
  locations.yaml, npcs.yaml, factions.yaml, pantheon.yaml` (значения: dict / str / list). Хендлер `pack_spec(ctx, request)`: повтор после
  принятого → `Invalid("already_done")`; `ValueError` конвертера (например, `attitude` без `gte`) → `Invalid("invalid_request", текст)`;
  иначе `ctx.files = files`, `Decision(status="accepted", log=["Пак принят"])`.
- `protocol/apply.py`: `IMPORT_HANDLERS = {"pack": pack.pack_spec}`; в `apply` ветка `elif ctx.mode == IMPORT_MODE: service =
  (IMPORT_HANDLERS, "import")` (чужой инструмент → `not_available_in_mode`, как у героя).
- `protocol/context.py`: `ImportTask(campaign_id: str)`, `mode = IMPORT_MODE`; `CreationContext` — комментарий «контекст без бандла:
  создание героя и import», поле `self.files = None`.
- `master/session.py`: `REQUIRED_BY_MODE[IMPORT_MODE] = "pack"`, `SINGLE_SHOT_MODES += (IMPORT_MODE,)`,
  `EMPTY_NOTES[IMPORT_MODE] = "Пустой ответ. Вызови инструмент pack."`. Бюджет повторов — существующий `count_invalid`
  (`retry.invalid_retries = 2` → до 3 попыток, В4а), новой ручки нет.

### A2. Промпт: `master/importer.py` → `ImportPromptBuilder`, `prompts/import_rules.md`
- `ImportPromptBuilder(app_cfg, *, model=None)` по образцу `HeroPromptBuilder`: `role = "import"`, `find_role_cfg(model)` ищет среди
  `roles.import_`, `profiles[*].import_`; `build(ctx, user_input, mode, *, world_text="")`: system[0] = `prompts/import_rules.md`
  (cache), system[1] = `reference_block(ctx)` (cache), messages[0] = `dump({"campaign_id": task.campaign_id, "summary": user_input})`;
  `tools = tool_set(IMPORT_MODE)`. Префикс system[0..1] байт-в-байт одинаков для разных выжимок (кэш).
- `reference_block(ctx)`: `species_ids` (реестр), `item_ids` (для `hero_has`; `source != "world"`), `trade_kinds` (`ctx.cfg.trade.presets`),
  `condition_kinds` (7 видов с подписью, как в `HeroTriggerSpec.ref`), `tone_axes` (допустимые значения осей из `Tone` через
  `typing.get_args(Tone.model_fields[...].annotation)` — один источник), `calendar` (`{"months": 12, "days_per_month": 30, "date":
  "YYYY-MM-DD", "time": "HH:MM"}` по `default_calendar`), `limits` (`means` 1–3, `name`/`id` правила), `required` (≥ 1 локация,
  `hero_location` из своих локаций).
- `import_rules.md` (коротко, по образцу `hero_sheet_rules.md`): задача — один вызов `pack` по выжимке; `id` — латиница snake_case,
  уникальны в едином пространстве (NPC, фракции, боги, локации); имена именованных NPC, богов и фракций не повторяются, имена локаций
  уникальны в пределах родителя (5.3); сущности и факты — только из выжимки, не выдумывать; существ/монстров и `combat` не описывать
  (BACKLOG 2); героев не описывать (у пака нет пресетов, герой создаётся при старте); `means` NPC 1–3; условия триггеров и секретов —
  структурные с id из своего же вывода, иначе `narrative`; `hero_location` — id своей локации; `start.date` — в календаре 12×30;
  `scene_summary` — положение дел на момент выжимки (стартовая сцена); `world_text` — мир/история/атмосфера, `truths` — неизменные
  факты (может быть пусто); оси тона — только из списка; при отклонении — исправить по тексту ошибки и вызвать снова; по-русски.

### A3. Слой `campaign`: `campaign/importer.py` (новый) и снятие запрета на пак без героя
- `PACK_FILES = ("campaign.yaml", "world.md", "truths.md", "locations.yaml", "npcs.yaml", "factions.yaml", "pantheon.yaml")`.
- `write_pack_files(folder, files) -> list[str]` — пишет файлы из `files_from_request`: YAML — `yaml.safe_dump(allow_unicode=True,
  sort_keys=False)`, `.md` — текст; **списковые файлы и `truths.md` пишутся только если непусты** (как у `vale` — нет `factions/pantheon/
  truths`; Q9); возвращает имена записанных файлов. `clear_pack_files(folder)` — удаляет `PACK_FILES` (между попытками).
- `check_pack_dir(folder, registry) -> list[str]`: `load_pack(folder, registry)` (`PackError.lines`) + `collect_conflicts(
  WorldState(world_id="import", rng=Rng(0).state), [], pack)` → `conflict.line()`; пусто = «пак грузится без ошибок 5.3».
  `relabel(lines, folder, campaign_id)` — префикс `str(folder)` в строках → `campaign_id` (модель и пользователь видят
  `my_pack/npcs.yaml: запись 1 (x), поле means: …`, а не временный путь). Сторож `test_campaign_does_not_use_random_or_wall_clock` —
  `Rng` из `core`, `tempfile` здесь не нужен (staging делает `game`).
- `campaign/loader.py:335–336` — **убрать** `if not heroes and not errors: errors.append("нужен хотя бы один пресет героя")` (В1а).
  `check_manifest` (`start.heroes` ⊆ пресетов) и `load_pack:369–370` (`start.heroes = []`) работают как есть; `hero_presets(pack)` → `[]`;
  `choose_hero` → `NEW_HERO` (Б2 Q12а, ветка уже есть); `--hero X` на таком паке → «В паке нет героя» (код 2, как сейчас).

### A4. Слой `game`: `game/pack_import.py` (новый) — прогон, исполнитель, staging, цена
- Зависимости — **`HeroCreateDeps` как есть** (поля ровно те, что нужны `MasterSession` и `RetryMenu`; Q6); в ARCHITECTURE —
  «зависимости вызова ИИ вне мира (создание героя, import)».
- `stage_dir(campaigns_dir, campaign_id) -> Path` — `tempfile.mkdtemp(prefix=f".import-{campaign_id}-", dir=campaigns_dir)` (та же
  ФС → атомарный `rename`); `finish_import(folder, campaigns_dir, campaign_id)` — `folder.rename(campaigns_dir / campaign_id)`;
  `discard_import(folder)` — `shutil.rmtree(folder, ignore_errors=True)`.
- `ImportExecutor(folder, registry, campaign_id)` — маленький класс с `__call__(ctx, request)` (не замыкание — mutmut, BACKLOG 16):
  `outcome = apply(ctx, request)`; `Invalid` → вернуть; `write_pack_files(folder, ctx.files)`; `errors = check_pack_dir(folder, registry)`;
  ошибки → `clear_pack_files(folder); ctx.files = None; return Invalid(code="pack_invalid", message="\n".join(relabel(errors, folder,
  campaign_id)))` (модель видит все строки «файл: поле: что не так», как Б1 видит все тексты валидатора); иначе `outcome` (принято,
  файлы уже на диске staging — они и есть проверенный пак).
- `run_import(deps, task, text, run_id, folder) -> CreationContext`: `MasterSession(deps.adapter, deps.app_cfg, journal=deps.journal,
  ledger=None, run_id=run_id, now=deps.now, role="import", builder=ImportPromptBuilder(deps.app_cfg, model=deps.model))`;
  `session.run(ctx, text, ImportExecutor(folder, deps.registry, task.campaign_id), IMPORT_MODE, run_id=run_id)`; `TurnFailed` наверх.
- `check_summary(text, max_chars) -> str | None` (В9а): пусто → «Выжимка пуста.»; длиннее → «Выжимка длиннее {max} символов ({len}).»
- `calls_cost_line(journal, run_ids, label) -> str` — общий вид «{label}: $X (N вызовов)»; `creation_cost_line` в `hero_create.py`
  становится `return calls_cost_line(journal, run_ids, "Создание героя")` (байт-в-байт та же строка; тесты Б1 зелёные).
  Для import — `calls_cost_line(journal, run_ids, "Импорт пака")`.
- `pack_report_lines(folder, files)` → «Пак {id} записан: campaigns/{id}/ — campaign.yaml, world.md, …; локаций N, NPC N, фракций N,
  богов N. Дальше: правьте файлы руками и запускайте `ai-dm --new --campaign {id}`.» (ТЗ 3 «пользователь правит руками»).

### A5. UI: `ui/import_session.py` (новый) и `ui/cli.py`
- `ImportSession(deps, task, text, folder)` (dataclass, как `HeroSession`, без терминала): `state` (`run | error_menu | model_choice`),
  `run_ids`, `stamp`, `retry = RetryMenu(deps)` (`leave_label` = «Выйти»), `ctx = None`. `start() -> Step` = `attempt()`:
  `run_id = f"import-{stamp}-{n}"` → `run_import(...)` → успех: `self.ctx = ctx`, `Step([note_block("Пак собран.")], quit=True)`;
  `TurnFailed` → `state = "error_menu"`, `retry.fail(failure)` (при `refusal` — `REFUSAL_HINT`, как Б1). `submit(line)`: `None` →
  `Step(quit=True)`; `number = menu_number(line, retry.menu)` → `None` → `NO_SUCH`; `retry.choose(number)`: `RETRY` → `attempt()`,
  `LEAVE` → `Step(quit=True)`, `Step` → `state = retry.state`, вернуть. ≤ 5 return. Смена модели → `deps.adapter/model` обновляются
  (`RetryMenu.choose_model`), следующий `attempt()` идёт новой моделью (билдер создаётся в `run_import` заново).
- `ui/cli.py`:
  - парсер: `--import FILE` (`dest="import_file"`, `metavar="FILE"`, help «импорт пака из текстовой выжимки в campaigns/<id> (нужен
    --campaign <id>; с --mock — сценарий вместо модели)»).
  - `play()`: `if args.import_file: return import_pack(args, stdin, stdout, setup)` — до `--replay-report` (обе команды вне игры;
    вывод — в `stdout` напрямую, без `CaptureOutput`/TUI, Q11).
  - `import_refusal(args, stdout) -> int | None` (≤ 5 return): несовместимые флаги (`new, world, replay, replay_report, hero,
    hero_describe, preset, seed, mock_world, mock_summarizer` — одним `any`) → 2; нет `--campaign` → 2; `campaigns_dir/<id>` существует →
    1 «Пак {id} уже есть: выберите другой id (--campaign)»; файл не читается / `check_summary` → 1; иначе `None`.
  - `pick_import(args, settings, narrator)` — той же формы, что `pick_world` (профиль провайдера рассказчика → `profile.import_`, иначе
    `roles.import_`).
  - `import_pack(args, stdin, stdout, setup) -> int`: `import_refusal`; `settings = load_settings()`; `args.new = True` (A0.9, прецедент
    replay); `narrator = pick_narrator(...)`; `role = pick_import(...)`; `adapter = make_game_adapter(args, role, settings, setup, None)`
    (`--mock` → `ScriptedAdapter`, живой → `make_adapter`; `MissingKey`/`OSError`/`ValueError` → код 1, как в `prepare`);
    `adapter_factory = functools.partial(make_adapter, app=settings.app, env=setup.env, dotenv_path=setup.dotenv_path)` (закрытие
    `prepare` не трогаем); `registry = load_registry([])`; `folder = stage_dir(setup.campaigns_dir, id)`; `deps = HeroCreateDeps(adapter,
    settings.app, registry, settings.rules, journal=Journal(folder, ".import", settings.app.journal), model=role.model,
    adapter_factory=adapter_factory)`; `session = ImportSession(deps, ImportTask(id), text, folder)`; цикл как `create_hero_simple`:
    `step = session.start(); emit_blocks(...)`; `while not step.quit: step = session.submit(stdin.read("> ")); emit_blocks(...)`;
    затем `say(calls_cost_line(deps.journal, session.run_ids, "Импорт пака"))` **до** переименования; `session.ctx is None` →
    `discard_import(folder)`, «Импорт отменён, пак не записан.», код 1; иначе `finish_import(...)`, `pack_report_lines`, код 0.
    `try/finally`: при исключении staging удаляется (мусор `.import-*` не остаётся). Коды: 0 — пак записан; 1 — отказ/отмена/сбой;
    2 — неверные флаги (как у `--replay-report`).
  - `make_parser` help/README: раздел «Импорт пака из выжимки»; описание `.import/` (журнал вызовов) и «правьте руками».
- `.gitignore`: `campaigns/*/.import/` (журнал локальный: выжимка и ответы модели) — Q5.

### A6. Конфиг: роль `import`, `[import] max_chars`
- `config/app.py`: `RolesConfig.import_: ModelRole = Field(alias="import")`; `AppConfig.check_models_known` — добавить `roles.import_`
  и `profile.import_`; `ImportConfig(BaseModel, extra="forbid")`: `max_chars: int = Field(default=60000, ge=1)`;
  `AppConfig.import_: ImportConfig = Field(default_factory=ImportConfig, alias="import")`.
- `app_defaults.toml`: `[roles.import]` = провайдер/модель рассказчика профиля по умолчанию (`gemini`, `gemini-3.8-flash`,
  `max_tokens = 32000`); `[profiles.gemini.import]` то же; `[profiles.anthropic.import]` — `claude-sonnet-5-5`, `effort = "low"`,
  `max_tokens = 32000` (Q2); `[import] max_chars = 60000` (≈ 24 тыс. токенов при 2,5 символа/токен; Q3).
- `llm_kit.app_cfg()` (`app.roles = app.profiles["anthropic"]`) работает без правок — профиль получает поле `import_` из defaults.

### A7. Тесты критерия и п. 30 — только `tests/**` (doeba), кода продукта нет
- `test_stage6b_done` (2) предыстории: `spec_call` из `test_stage6b_background` + `BackgroundTask(class_id, class_skills=("acrobatics",))`
  → три разных нарушения подряд (навык класса = навык предыстории; бюджет > 50 зм; неизвестный инструмент / описание > 300) →
  `TurnFailed("invalid")`, 3 запроса; две невалидные + валидная → `BackgroundSpec`.
- `test_stage6b_done` (3) пресет: мир `new_world_from_pack(..., preset_id="grim")` → `PromptBuilder.build` → system[1] (`cache=True`)
  содержит `notes` пресета `grim` и оси (`violence: жестоко`, `romance: откровенно`) → два мок-хода → `[b.model_dump_json() for b in
  system]` и `tools` равны между ходами (образец `test_system_bytes_equal_between_turns`). **Если упадёт — стоп и вопрос проектировщику**
  (дефект Б0, не объём Б3; догруминг).
- п. 30: `tests/unit/ui/test_cli_migration.py` (+): копия `tests/fixtures/saves/v5` с `world_id` → `vale-old` (`manifest.json`,
  `world/world.json`) → `--world vale-old --mock` → код 0, в слоте после хода `world.campaign_id == "vale"`, в выводе строки догрузки
  `vale` («Из пака добавлено: …» или «Не загружено из пака») — ветка `cli.py:646–649`; копия с `campaign_id: "ghost"` в обоих файлах →
  `pack_npc_trade` → `None` → предупреждение миграции (текст Т0) и «Пака ghost нет в … без догрузки»; `old_world` без `campaign_id`
  (фикстура как есть) → `campaign_registry(None)` → `(None, registry)`. Затем `make mutate FUNCS="ai_dm.ui.cli:campaign_registry
  ai_dm.campaign.loader:pack_npc_trade" TESTS="tests/unit/ui/test_cli_migration.py tests/unit/campaign/test_pack_trade.py"` —
  выжившие на старых строках разобрать (это и есть п. 30), остаток → BACKLOG 16 с пометкой.

### A8. Документы
ARCHITECTURE (`protocol`: режим `pack_import`, `handlers/pack.py`; `master.importer`; `campaign.importer` + «пак без пресетов героя
допустим»; `game.pack_import` (staging, исполнитель, цена); `ui.import_session`, `cli --import`, коды выхода; конфиг: роль `import`,
`[import]`; журнал `campaigns/<id>/.import/`), README/`--help` (раздел import, «правьте руками», `.import/`), BACKLOG 16 (закрыть (в)
«пак без героя»; записать, что Б2 В11а отменено решением Б3 В1а), BACKLOG 30 (закрыть «мутанты campaign_registry/pack_npc_trade»;
«живой replay» — после прогона), BACKLOG риск 9 (если refusal на `grim` — запись по Г1а), HANDOFF (статусы, расходы),
`decisions/b3-review.md` (ревью и решения), `decisions/b3-live.md` (живой прогон).

## B. Партия (одна, M — В11а)

### Шаги kaban (src/docs), в порядке зависимостей
1. `config/app.py` + `app_defaults.toml` — роль `import_`, `ImportConfig`, `check_models_known` (A6).
2. `protocol/requests.py` — `IMPORT_MODE`, `SecretSpec`, `PackLocation/PackNpc/PackFaction/PackGod/PackStart/PackRequest`,
   `IMPORT_MODELS`, `IMPORT_ADAPTER`, `parse_request`; `protocol/schema.py` — `MODE_TOOLS`, `own_models`, группа кэша; `protocol/
   context.py` — `ImportTask`, `CreationContext.files`; `protocol/handlers/pack.py` — конвертер и `pack_spec`; `protocol/apply.py` —
   `IMPORT_HANDLERS` (A1). 3. `master/session.py` — три константы (A1). 4. `master/importer.py` + `prompts/import_rules.md` (A2).
5. `campaign/importer.py`; `campaign/loader.py` — снять запрет 335–336 (A3). 6. `game/pack_import.py`; `game/hero_create.py` —
   `calls_cost_line` (A4). 7. `ui/import_session.py`; `ui/cli.py` — `--import`, `import_refusal`, `pick_import`, `import_pack`, ветка в
   `play` (A5). 8. `.gitignore` (Q5), README, ARCHITECTURE, BACKLOG 16/30, HANDOFF (A8). 9. `vulture_allowlist.py` — без изменений
   (новых мёртвых имён нет; `import_` читается `find_role_cfg`/`pick_import`/`check_models_known`, `max_chars` — `import_refusal`).

### Тесты kaban-doeba (tests/**; kit `tests/unit/game/import_kit.py`: `pack_input(**changes)` — канонический валидный вызов `pack`
(2 локации `square`/`inn` со связями, NPC именованный `mara` с триггером `flag` и секретом `narrative` и безымянный `guard`, фракция
`watch` с `members/regions`, бог `selune` с `servants`, тон `grim`-подобный, `start` с `hero_location="inn"`, `scene_summary`);
`pack_call(call_id, **changes)`; `import_task(id="mini_import")`; `import_deps(adapter, registry, cfg, folder)` → `HeroCreateDeps` с
`Journal(folder, ".import", …)`; `staged(tmp_path)` — каталог `campaigns` + staging; скрипт `tests/fixtures/scripts/import_pack.yaml`
(шаг с вызовом `pack` для `cli --mock`); `summary_text()` — выжимка из нескольких абзацев):
- `tests/unit/config/test_app.py` (+): `roles.import_` и у обоих профилей есть; `[roles.import] model = "claude-new-9"` без цены →
  `ValueError` «нет цены» (как для других ролей, тесты :276–311 параметризовать и на `import`); `import_.max_chars` по умолчанию 60000,
  `[import]\nmax_chars = 10` переопределяет, `max_chars = 0` → ошибка; alias: `load_settings('[import]\nbogus = 1')` → ошибка.
- `tests/unit/protocol/test_pack_request.py` (новый): `tool_set("pack_import")` — ровно один strict-инструмент `pack`, схема без `$ref`,
  `additionalProperties` только `False`, описание из docstring, в `properties` есть `tone` с осями из `Tone`; `parse_request(…, mode)` в
  `pack_import` принимает только `pack`; `pack` в `explore`/`hero_sheet` и `hero_sheet` в `pack_import` не разбираются; `apply` с
  `npc_create` в `pack_import` → `not_available_in_mode`; хендлер: валидный → `ctx.files` с 7 ключами, `campaign.yaml["id"]` = id задачи,
  `version == "1"`, `tone` без пустых осей, `connections` сохранены, триггер → `{"if": {"flag": …}, "once": True}`, секрет →
  `reveal_if` короткой записью, `means` списком, `named/key` булевы, пустые `motive/location_id/species_id/trade_kind` **отсутствуют** в
  словаре; второй вызов → `already_done`; `attitude` без `gte` → `invalid_request` с текстом `condition_from_spec`; `test_schema_cache_
  group`-регресс: группа `import`.
- `tests/unit/master/test_import_prompt.py` (новый): system — 2 блока, оба `cache=True`; system[0] = файл правил (упоминает `pack`,
  `hero_location`, «не выдумывать»); system[1] содержит `species_ids` (human, elf…), `trade_kinds` из `cfg.trade.presets`, `condition_
  kinds` (7), `tone_axes` (`violence` → `мягко/реалистично/жестоко`), `calendar.months == 12`; messages[0] — `campaign_id` и выжимка;
  префикс (`tools` + `system`) байт-в-байт равен для двух разных выжимок; `role == "import"`, `model` из `roles.import_`, `max_tokens`
  роли; `find_role_cfg` по модели профиля anthropic. `test_master_rules.py` (+): `import_rules.md` существует, по-русски, содержит `pack`.
  `test_hero_session.py`/`test_master_session.py` (+): `pack_import` — один вызов при валидном (single-shot), `EMPTY_NOTES` называет
  `pack`, пустой ответ → подсказка, 3 невалидных → `TurnFailed("invalid")`.
- `tests/unit/campaign/test_pack_importer.py` (новый): `write_pack_files` пишет 7 файлов при полных данных, **не пишет** пустые
  `factions.yaml/pantheon.yaml/truths.md`; YAML читается обратно `yaml.safe_load` в те же словари, порядок ключей как в словаре
  (`sort_keys=False`), кириллица без `\u`; `clear_pack_files` убирает только `PACK_FILES` (каталог `.import/` цел); `check_pack_dir` на
  записанном `pack_input` → `[]`; битая `hero_location` → строка `campaign.yaml: поле start.hero_location`; два NPC с одним именем
  (`named`) → строка `collect_conflicts` («npcs.yaml: npc …: имя … уже занято»); `relabel` меняет префикс staging на id.
  `test_pack_loader.py`: `test_pack_without_heroes_is_error` → **`test_pack_without_heroes_loads`** (`heroes == []`,
  `start.heroes == []`); `start.heroes: [ghost]` без пресета — по-прежнему ошибка (:271). `test_pack_build.py` (+): `build_world(hero_id=
  sheet)` на паке без `heroes/` — мир стартует (`taken_names`/`known_ids` работают). `test_ui_cli_pack.py`/`test_ui_cli.py` (+):
  мини-пак без `heroes/` → интерактивный старт без пикера сразу «Опишите героя» (`NEW_HERO`), `--hero arn` → код 2.
- `tests/unit/game/test_pack_import.py` (новый): `run_import` → `ctx.files` заполнен, в staging лежит проверенный пак, `load_pack`
  проходит; журнал — роль `import`, `run_id` `import-…`, `turn_seq 0`, каталог `<staging>/.import/journal/`; невалидный первый
  `pack` (битая ссылка + конфликт имён) → `tool_result is_error` с **обеими** строками через `\n`, после него staging без файлов пака,
  второй валидный → принят; `ImportExecutor` на `Invalid` от `apply` (чужой инструмент) не пишет файлы; `TurnFailed` наверх; `finish_
  import` переименовывает в `campaigns/<id>` (staging исчез, `.import/journal` переехал); `discard_import`; `check_summary` (пусто,
  ровно `max`, `max+1`); `calls_cost_line` считает только записи `run_ids`; `creation_cost_line` даёт прежнюю строку (регресс).
- `tests/unit/ui/test_import_session.py` (новый, `ScriptedAdapter`): `start` при валидном → `quit`, `ctx` не `None`, `run_ids == ["import-…-1"]`;
  `TurnFailed("invalid")` → меню 3 пункта («Повторить», «Сменить модель», «Выйти»); «1» → новый `run_id`, второй прогон; «2» → список
  моделей → выбор → `FactorySpy` вызван, `deps.adapter/model` обновлены, снова меню; негодная модель → текст `check_model`; «3» →
  `quit`, `ctx is None`; `refusal` → `REFUSAL_HINT`; цифра вне меню → `NO_SUCH`; `None` → `quit`.
- `tests/unit/ui/test_cli_import.py` (новый, `cli(...)` + `campaigns_dir=tmp`): `--import f.txt --campaign mini_import --mock
  import_pack.yaml` → код 0, `campaigns_dir/mini_import/{campaign.yaml, world.md, …}`, `.import/journal/calls-001.jsonl` с 1 записью
  роли `import`, в выводе «Пак mini_import записан», «Импорт пака: $…», «ai-dm --new --campaign mini_import», staging `.import-*` не
  остался; повтор той же команды → код 1 «уже есть», байты файлов не изменились; без `--campaign` → 2; с `--new`/`--world`/`--replay`/
  `--replay-report`/`--hero`/`--preset`/`--seed` → 2; файла нет → 1; пустой файл → 1 «Выжимка пуста»; `[import] max_chars` (через
  `load_settings`-monkeypatch или длинный файл > 60000) → 1 с длиной; скрипт с 3 невалидными → меню, ввод «3» → код 1, в `campaigns_dir`
  нет каталога `mini_import` и нет `.import-*`; скрипт с `refusal` → `REFUSAL_HINT` и меню; `--provider anthropic` → роль import из
  профиля anthropic (`requested_model` в журнале); затем `--new --campaign mini_import --hero-describe … --mock hero_sheet.yaml` →
  мир из импортированного пака стартует (`world.campaign_id == "mini_import"`, герой в `hero_location`); `make_parser().format_help()`
  содержит `--import`. `test_ui_cli_mode.py`/`test_tui_russian.py` — без правок (import не трогает TUI).
- **`tests/scenarios/test_stage6b_done.py` (+)**: (1) import — сценарий критерия через `run_import` + `cli` (см. выше: невалидный →
  валидный → `load_pack` + `collect_conflicts == []` → `new_world_from_pack(hero=base_sheet(), preset_id="heroic")` → мок-ход →
  `save_current` → `load_slot` → `core_dump` равен; повторный import — отказ, файлы целы; 3 невалидных → меню, на диске ничего;
  refusal); (2) предыстории; (3) пресет `grim` (A7). `test_stage6b_background.py` — регресс.
- п. 30 — `test_cli_migration.py` (+) и mutmut (A7).
- `test_architecture.py` (+): сторожа-близнецы для новых модулей: `master/importer.py` не импортирует `game/ui/campaign`;
  `protocol/handlers/pack.py` — не `llm/master/game/ui/campaign`; `campaign/importer.py` — под существующий
  `test_campaign_does_not_import_upper_layers` (ничего нового); `game/pack_import.py` — под `test_game_does_not_import_ui_or_sdks`.

### Живой прогон (пользователь, В10а + Г1а/Г2а) → `decisions/b3-live.md`
1. `ai-dm --import <выжимка> --campaign <id>` на модели по умолчанию (реальная выжимка: сессия Дракона / Антигравити; размер в
   пределах `max_chars`) → число попыток, цена, тексты отказов (если были), refusal → меню 2.2 (смена модели).
2. Правка файлов руками (хотя бы одно поле) → `ai-dm --new --campaign <id> --preset grim` → герой на лету → 3–5 ходов, среди них
   сцена близости (Г2а `grim`: `romance: откровенно`) → refusal есть → `/report`, запись в BACKLOG (риск 9), Б3 **не блокирует** (Г1а).
3. `/report <текст>` на любом ходу → `ai-dm --replay-report saves/<мир>/issues/<имя>` на реальном журнале → код 0 («Состояние совпало»)
   — закрывает живой replay п. 30; код 1 — зафиксировать расхождение (AD1 Q4 — только старые репорты с summarizer).
4. Пример живого пака (без `.import/`) можно положить в `campaigns/` как образец — решение после прогона (не в объёме Б3).

## C. Качество (каждый шаг)
- **`SMELLS_MAX = 205` не меняется, запас 1 — новый код +0** (A0.1). Риск файлового флага: `protocol/requests.py` (+~9 моделей-данных,
  сложность не растёт), `ui/cli.py` (+4 плоские функции; если флаг появится — `import_pack`/`import_refusal`/`pick_import`/
  `ImportSession`-цикл переезжают в `ui/import_cli.py` целиком, лимит не трогаем). `apply()` +1 ветка — ниже порога. `loader.py` —
  минус 2 строки. Если запас всё же съеден — перепланировка на ревью, не поднятие лимита (Б2 Q1: цель вернуть ≤ 203).
- `make cov` ≥ 94% (новые модули — 100% строк тестами выше; `ui.tui` не трогается); `make dead` — allowlist без изменений;
  `make mutate FUNCS="…" TESTS="…"` по изменённым функциям из diff.
- FUNCS Б3: `ai_dm.protocol.handlers.pack:trigger_data`, `…:secret_data`, `…:location_data`, `…:npc_data`, `…:faction_data`,
  `…:god_data`, `…:tone_data`, `…:manifest_data`, `…:files_from_request`, `…:pack_spec`, `ai_dm.protocol.requests:parse_request`,
  `ai_dm.protocol.schema:own_models`, `…:tool_defs` (новые строки), `ai_dm.protocol.apply:apply` (новые строки),
  `ai_dm.master.session:MasterSession.empty_note` (регресс), `ai_dm.master.importer:ImportPromptBuilder.build`,
  `…:ImportPromptBuilder.reference_block`, `…:ImportPromptBuilder.find_role_cfg`, `ai_dm.campaign.importer:write_pack_files`,
  `…:clear_pack_files`, `…:check_pack_dir`, `…:relabel`, `ai_dm.campaign.loader:load_pack` (изменённые строки),
  `ai_dm.game.pack_import:ImportExecutor.__call__`, `…:run_import`, `…:stage_dir`, `…:finish_import`, `…:discard_import`,
  `…:check_summary`, `…:calls_cost_line`, `…:pack_report_lines`, `ai_dm.game.hero_create:creation_cost_line`,
  `ai_dm.ui.import_session:ImportSession.start`, `…:ImportSession.attempt`, `…:ImportSession.submit`, `ai_dm.ui.cli:import_refusal`,
  `…:pick_import`, `…:import_pack`, `…:play` (новые строки), `ai_dm.config.app:AppConfig.check_models_known`; п. 30 —
  `ai_dm.ui.cli:campaign_registry`, `ai_dm.campaign.loader:pack_npc_trade`. TESTS — `tests/unit/{protocol,master,campaign,game,ui,config}`
  + сценарий; `ui.tui.*` не трогается.
- **WINDOW мока (`memory_script.py`, 22070) — без изменений:** промпт нарратора, `narrator_rules.md`, `world_block` не трогаются
  (`Tone` остаётся как есть; вложение в `PackRequest` его схему для нарратора не меняет). Doeba подтверждает `test_stage4_memory`.
- Ревью мамы-кабана — одна партия; решения и расходы — HANDOFF / `decisions/b3-review.md`.

## D. Риски
1. **Strict-схема `pack` — самая крупная в проекте** (4 списка сущностей × вложенные триггеры/секреты + `Tone` + `start`): отказ грамматики
   Anthropic возможен только на живом прогоне; запасной путь `NON_STRICT[IMPORT_MODE]` (одна строка), Pydantic валидирует (Q7). На Gemini
   strict-ограничений такого рода не наблюдалось.
2. **Длина ответа:** пак уровня `drunk_dragon` ≈ 20 тыс. токенов вывода; `max_tokens` роли 32000 (Q2); обрыв → «повтори короче» →
   `count_invalid` → меню 2.2. Смена модели в меню — на модели рассказчика (список `model_options`), это ожидаемо.
3. **Модель ошибается в ссылках/датах/уникальности** (риск 3 груминга) — закрыто по построению: все строки загрузчика и 5.3 уходят модели
   в `tool_result` до 3 попыток; цена повторов видна в строке «Импорт пака: $…».
4. **Staging внутри `campaigns/`** (репозиторий): при крахе остаётся `.import-<id>-*` — `try/finally` удаляет; `.gitignore` (Q5) закрывает
   журнал. `campaigns_dir` только для чтения — `mkdtemp` упадёт `OSError` → код 1 с текстом (тест).
5. **Журнал в staging при неудаче исчезает** (В4а «на диск только валидный пак») — цена печатается до удаления; для отладки живого
   прогона можно сохранить путь (Q4).
6. **`Journal.world_id = ".import"`** попадает в записи как `world_id` — косметика; потребителей (`records_for`, `/cost`) у import-журнала
   нет, `ReplayAdapter` его не читает.
7. **Пак без героя и старые тесты:** `test_pack_without_heroes_is_error` инвертируется; `check_manifest` для `start.heroes` остаётся;
   README уже обещает «у пака без пресетов — сразу создание». `--replay` на таком мире требует `meta/hero_sheet.json` (есть с Б1).
8. **Роль `import` — обязательное поле `RolesConfig`:** пользовательский `config.toml` с полным `[roles]`/`[profiles.x]` без `import`
   получит поле из defaults (`deep_merge`), ломаться нечему; `extra="forbid"` на `[import]` ловит опечатки.
9. **Тест (3) пресета может вскрыть дефект Б0** (абзац не в кэшируемом блоке или префикс плавает) — по догрумингу: стоп и вопрос
   проектировщику, в Б3 не чинить.
10. **Объём M** держится за счёт переиспользования (Б1: `RetryMenu`, `HeroCreateDeps`, `HeroTriggerSpec`, `condition_from_spec`,
    `MasterSession` single-shot, `make_game_adapter`, `Journal`); если ревью потребует делить — естественная линия: код+мок (A1–A6) /
    тесты A7 + живой прогон, без перепланирования.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1. Роль модели (В6: текст «новая роль `import`» vs буква (а) = `world`).** **(а) новая роль `import` в конфиге** (`[roles.import]`,
  `[profiles.*.import]`), по умолчанию модель рассказчика профиля; (б) роль `world` — `flash-lite`, `max_tokens` 4000: пак не выдаст,
  пришлось бы менять её лимиты для игры; (в) роль `narrator` без новой ручки (цена/модель как у рассказчика, в `/cost`-подобной строке
  роль «narrator»).
- **Q2. Модель и `max_tokens` роли `import`.** **(а) `gemini-3.8-flash` / `claude-sonnet-5-5` (effort low), `max_tokens = 32000`**;
  (б) как у narrator (16000) — обрыв на крупных паках; (в) `claude-opus-5-5` в профиле anthropic (дороже, точнее).
- **Q3. `[import] max_chars`.** **(а) 60000** (≈ 24 тыс. токенов; выжимка Дракона ≈ 5 КБ); (б) 30000; (в) 120000.
- **Q4. Журнал неудачного импорта.** **(а) staging удаляется целиком, цена печатается до удаления** (В4а буквально); (б) журнал
  остаётся во временном каталоге, путь печатается (отладка живого прогона).
- **Q5. `.gitignore`.** **(а) добавить `campaigns/*/.import/`** (журнал содержит выжимку и ответы модели, локальный); (б) не трогать.
- **Q6. Зависимости import.** **(а) `HeroCreateDeps` как есть** (поля совпадают, `RetryMenu` на нём работает); (б) переименовать в
  `AiDeps` (правки Б1/Б2 тестов и ARCHITECTURE ради имени); (в) новый `ImportDeps` (дубль).
- **Q7. Strict.** **(а) strict, запасной `NON_STRICT[IMPORT_MODE]` включается только по факту отказа грамматики на живом прогоне**
  (Б1 D4); (б) сразу non-strict.
- **Q8. Состав полей сущностей в `pack`.** **(а) минимальный: NPC как `npc_create` + `species_id` + `opportunity` + `secrets`; локации как
  `location_create`; фракции/боги — поля ТЗ 4.2 (без `season_power`, `check_every_days`, `attitude`, `tags`, `groups`)**; (б) полные
  схемы `state.world` (раздувает strict и путает модель).
- **Q9. Пустые файлы.** **(а) списковые файлы и `truths.md` пишутся только если непусты** (как `vale`); (б) все 7 всегда.
- **Q10. Условия триггеров/секретов из import.** **(а) плоские, один `kind` на условие (как Б1 Q3)**; (б) только `narrative`.
- **Q11. Вывод import.** **(а) только консольный, без TUI, даже в терминале** (команда вне игры, как `--replay-report`); (б) меню 2.2
  через `PickerApp` в режиме TUI.
- **Q12. Живой прогон.** **(а) один сквозной: import реальной выжимки → правка → мир на `grim` с героем на лету → 3–5 ходов со сценой
  близости → `/report` → `--replay-report`**; (б) два прогона: import + replay на любом пресете, `grim`/refusal отдельно.

Технические умолчания на аппрув вместе с планом: режим `pack_import`, инструмент `pack`, код отказа `pack_invalid`; `run_id`
`import-<stamp>-<n>`; staging `campaigns/.import-<id>-<rand>/` → `rename` в `campaigns/<id>/`; журнал `Journal(staging, ".import", …)`
→ `campaigns/<id>/.import/journal/calls-001.jsonl` + `blobs/`, леджера нет; `version: "1"`, `chapter` 1 по умолчанию; `id`/`version`
манифеста ставит движок, модель их не выдаёт; `Tone` вложен в запрос как есть; пустые оси/списки в YAML не пишутся; строки ошибок
модели — с префиксом `<id>/` вместо пути staging; строка «Импорт пака: $X (N вызовов)»; коды выхода 0/1/2; `args.new = True` внутри
`import_pack` (прецедент `--replay`); `registry = load_registry([])`; `adapter_factory` через `functools.partial(make_adapter, …)`;
`leave_label` меню — «Выйти»; `choose_hero` на паке без пресетов — сразу «на лету» (Б2 Q12а); сейв v8.

## Решения проектировщика (2026-10-09)
Q1–Q12 — все по рекомендациям (вариант «а»): роль `import` (по умолчанию модель рассказчика профиля); flash / sonnet-5-5 low, max_tokens 32000; `max_chars` 60000; неудачный staging удаляется, цена печатается до удаления; `.gitignore` += `campaigns/*/.import/`; `HeroCreateDeps` как есть; strict + запасной NON_STRICT только по факту; минимальные поля сущностей; пишутся только непустые файлы; плоские условия; вывод только в консоль; один сквозной живой прогон. Технические умолчания из конца плана приняты вместе с планом.
