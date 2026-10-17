# План партии Б2: «Пошаговое создание героя» — Б2а (шаги, автомат, простой режим, мок) и Б2б (TUI, заставка, живой прогон)

Автор: папа-кабан, 2026-10-09. Статус: **предложение на аппрув** (решения проектировщика В1–В12 из
`docs/plan-b2.md`, раздел «Решения проектировщика», обязательны и приняты за основу). Основа: `docs/plan-b2.md`
(ТЗ свинопаса, аудит свекрови, решения), `docs/plan-b1.md` (форма, A6, Q6/Q10), `docs/plan-roadmap-r4.md` (#3 Б2, #6 Д1),
`docs/plan-roadmap-r2.md` (стр. 165–166, 332), `BACKLOG.md` 16 (хвосты Б1а/Б1б, HeroPicker, заставка), 34, `TZ.md` 5 / 6,
HANDOFF («Инструменты качества», «Правила экономии»). Код на main 99d29cb: `ui/hero_session.py`, `ui/tui/{create,modals,__init__,
strings}.py`, `ui/cli.py` (`choose_hero`, `create_hero*`, `prepare`), `ui/simple.py`, `game/hero_create.py`, `game/sheet_text.py`,
`master/hero.py` (`class_data`), `rules/builder.py` (`CharacterChoices`, `check_ability_scores`, `build_character`, `sheet_check`,
`sheet_name_problems`, `sheet_hooks_problems`), `rules/names.py` (`ABILITY_NAMES`, `SKILL_NAMES`), `protocol/context.py`
(`BackgroundTask`, `SheetTask`), `protocol/handlers/hero.py` (`background_spec`), `art/catalog.py` (`art_for_event`),
`vulture_allowlist.py`, тесты `tests/unit/{rules,game,ui,ui/tui}`, kit-ы `hero_kit`/`master_kit`/`ui_kit`/`game_kit`,
`tests/scenarios/test_stage6b_done.py` (образец «TUI = простой»), `tests/fixtures/scripts/hero_sheet.yaml`.

**Критерий Б2 (груминг «Готово» + решения):** мок-сценарий — пошаговый герой каждым из трёх методов → ошибка (покупка очков
> 27, бонус выше 20, свободный ввод 21, занятое имя) **тем же текстом, что у `sheet_check`** → исправление → подтверждение → мир →
ход → сейв/загрузка (лист, motive/means/opportunity целы) → replay мира с пошаговым героем без расхождения; TUI и простой режим
дают одного героя одним скриптом; заклинатель (волшебник и жрец) собирается пошагово — заговоры и подготовленные в лимите;
`make smells` ≤ новому лимиту (C, Q1), `make dead` чисто (allowlist Б2 снят), mutmut по новым функциям; живой прогон короткий
(В10а; пошаговый герой каждым методом, 3–5 ходов, сейв/загрузка). Сейв **остаётся v8**: итог пошагового пути — тот же `HeroSheet`,
тот же `meta/hero_sheet.json`, схема сейва не меняется.

**Принято из решений:** порядок шагов как SRD 2024 (В1а); предыстория — 4 SRD или «описать словами» через `propose_background`,
при сбое ИИ — назад к списку SRD (В2а); motive и 1–3 means вводит игрок, opportunity пустой (В3а); третий пункт `choose_hero`
«Создать пошагово» (В4а); заставка до выбора героя — в Б2, «HeroPickerApp внутрь основного App» — Д1 (В5а); шаг назад со сбросом
зависимых, отмена (В6а); на шаге только допустимые варианты, тексты ошибок из валидатора (В7а); стандартный набор / покупка / свободный
ввод — по одной характеристике (В8а); без неинтерактивного флага (В9а); живой прогон короткий (В10а); запрет пака без героев не трогать
(В11а); деление Б2а/Б2б, объём L (В12а); лимит smells поднять (новое значение — C/Q1); «автомат отдельным классом» — решение
архитектора (A1, Q2); уникальность имени — `taken_names` как в `sheet_check`.

**Не входит:** уровни > 1 (К0+), новые классы/виды, import (Б3), пак без пресетов героя (loader `campaign/loader.py:335`, BACKLOG 16(в)),
means/opportunity в `HeroPreset` пака (BACKLOG 34), `HeroPickerApp`/создание внутрь основного App (Д1), ввод opportunity руками в
мастере (только `edit_sheet`, как Б1 Q4), новый CLI-флаг, правка `TurnContext.__init__` (BACKLOG 16).

## A0. Поправки фактов (проверено по коду и `qlty smells`, 2026-10-09)
1. **`make smells` = 203 при лимите 202** (подтверждено; `~/.qlty/bin/qlty smells --all`). Разбивка: 86 «many parameters», 52 «high
   complexity», 30 «high total complexity» (файловый флаг), 28 «many returns», 5 «deeply nested», 2 «complex binary». В файлах темы:
   `ui/cli.py` — `prepare` (98 / 17 return), `hero_flag_refusal` (6 return), `main` (8 параметров), файл 217; `rules/builder.py` —
   `build_character` 177, файл 242; `game/app.py` файл 106; `ui/tui/app.py` файл 98. **`ui/hero_session.py`, `game/hero_create.py`,
   `ui/tui/create.py`, `master/hero.py` — 0 smells.** Пороги по наблюдению: функция — сложность от ~18, параметры ≥ 6 (с учётом `*`),
   return ≥ 6, вложенность 5; **файл — «High total complexity» уже при 98** (`tui/app.py`). Значит риск Б2 — не функции (их делаем
   плоскими), а **файловый флаг на новом плотном модуле**: это и есть бюджет C.
2. **`HeroCreateApp` и `create_hero_simple` не знают о `HeroSession`**: им нужны только `start()`, `submit(line) -> Step`, `.sheet`,
   `.width` (`ui/tui/create.py:89–104`, `ui/cli.py:197–203`). Пошаговый автомат с тем же интерфейсом **получает TUI и простой режим без
   нового App** — Б2б по TUI сводится к placeholder, заставке и Pilot-тестам.
3. **Допустимые множества уже вычисляются в `master/hero.py:class_data`** (оружие с мастерством и владением, стили, заговоры/заклинания
   1 круга класса, наборы) и `sheet_reference_block` (виды с `species_choice_keys`, черты origin с `feat_choice_count`, таблицы).
   Для меню шагов их надо переиспользовать, а не переписывать: иначе два источника «что разрешено» (риск 4 груминга). `master` не
   может импортировать `game`/`ui`, поэтому общий дом — слой `rules` (A2).
4. **Тексты арифметических ошибок живут только внутри `build_character`** (строки 284–297: «покупка очков: …», «стандартный набор: …»,
   «нужны все шесть характеристик …», «характеристика выше 20 после бонуса: …»); `check_ability_scores` возвращает `bool`. Чтобы шаг
   показывал **тот же текст**, их надо вынести в константы/функцию модуля и использовать из обеих точек (A3) — поведение Б1 не меняется.
   То же с именем (`sheet_name_problems(sheet, …)` требует целый лист) и мотивом/средствами (`sheet_hooks_problems`): нужны
   варианты по значениям, через которые делегируют нынешние функции.
5. **Выборы вида есть только у человека** (`skillful` → навык, `versatile` → черта origin; `species_choice_keys`); эльф, дварф,
   полурослик — без шагов. Черты с выбором — только `skilled` (3 навыка/инструмента). Стиль боя на 1 ур. — воин и следопыт;
   мастерства — воин 3, плут 2, следопыт 2, жрец/волшебник 0. Заклинатели: волшебник 3/6/4, жрец 3/4/4, следопыт 0/2/2 (заговоров 0 —
   шаг пропускается). Все условные шаги вычисляются из реестра, не из id классов.
6. **`creation_cost_line`** без вызовов даст «Создание героя: $0.0000 (0 вызовов)» — для пошагового пути без ИИ строку лучше не печатать
   (Q6). `discard_world` при отмене работает как есть (каталог без слотов).
7. Порядок В1а не покрывает выборы вида, черт и мотив/средства — технически они ставятся после навыков класса (A1, Q9), чтобы меню
   фильтровало уже занятые навыки (В7а). `BackgroundTask.class_skills=()` при предыстории словами — конфликт навыков не возникает,
   потому что меню навыков класса потом исключит навыки предыстории.
8. Тестов на main — 11 232 (collect-only).

## A. Архитектура

### A1. Решение по автомату (вместо «отдельный класс рядом с HeroSession»)
**Отдельный автомат шагов `HeroWizard` + общий хвост через композицию `HeroSession`** — не новые состояния в `HeroSession` и не копия.
- Почему не новые состояния: `HeroSession.submit/choose/choose_review` — диспетчеры по строке `state`; ~20 состояний шагов дадут
  «many returns» на `submit`/`choose` и перемешают два пути; тесты Б1 (`test_ui_hero_session.py`, 1 файл, ~40 тестов) станут хрупкими.
- Почему не копия: ревью (предпросмотр + меню), ручная правка (`edit` → `edit_sheet` + `sheet_check`), меню 2.2 и смена модели —
  это ~60 строк с текстами, которые по Б-2 должны быть одни; Qlty ловит дубли (BACKLOG 16: «плавание из-за дублей»).
- Композиция: `HeroWizard` ведёт шаги и при финише **передаёт готовый `HeroSheet` в `HeroSession` на стадии review** (`proposal`
  задан, `state = "review"`), дальше делегирует ему `submit`. `HeroSession` получает две маленькие точки расширения (A4): поле
  `review_menu` (пункт 2 у пошагового — «Вернуться к шагам», Q3) и вынесенный помощник меню 2.2 `RetryMenu` (нужен шагу
  «описать словами», В2а). Интерфейс наружу тот же, что у `HeroSession` (A0.2): `start()`, `submit()`, `.sheet`, `.run_ids`, `.width`.
- Слои: `rules/hero_options.py` (чистые запросы к реестру — допустимые множества), `game/hero_steps.py` (таблица шагов, черновик,
  сборка листа — без UI), `ui/hero_wizard.py` (автомат без терминала, блоки `note`/`menu`/`raw` из `ui/screen`, как `HeroSession`).
  Все функции плоские, без замыканий (урок `SHEET_FIELDS`, BACKLOG 16: mutmut не мутирует замыкания): шаги — `StepDef`-записи с
  именами функций модуля, не фабрики.

### A2. `rules/hero_options.py` — допустимые множества (новый, чистый, только registry)
- `species_options(registry) -> list[Species]`, `class_options(registry)`, `background_options(registry)` (4 SRD по `registry.all`).
- `class_skill_options(char_class, taken: set[str]) -> list[str]` — `skill_choices.options` минус занятые (навыки предыстории).
- `mastery_weapons(registry, char_class) -> list[Weapon]` — оружие с `mastery` и `weapon_proficient`, `source != "world"`
  (сейчас — тело `class_data`); `has_fighting_style(char_class) -> bool`; `fighting_styles(registry) -> list[Feat]`.
- `class_spells(registry, class_id, level) -> list[Spell]` (заговоры `level=0`, 1 круг `level=1`; сейчас — `class_data`);
  `spell_counts(char_class) -> (cantrips, spells, prepared)` (None → 0, т.е. шаг пропускается — в контенте все заданы, A0.5).
- `origin_feats(registry, exclude_feat: str | None)` — черты origin минус черта предыстории, если она не `repeatable`
  (правило `build_character:428–434`); `feat_pick_options(registry, taken_skills, taken_tools) -> list[(id, label)]` — навыки из
  `SKILLS` минус занятые + инструменты (`item.tool`) минус занятые (правило строк 393–407).
- `species_skill_options(taken_skills)`; `standard_array(registry) -> list[int]`; `point_buy_table(registry) -> (cost: dict[int,int],
  budget: int)`; `kit_options(char_class)`; `kit_label(registry, kit) -> str` («кольчуга, двуручный меч, копьё, набор путешественника;
  +4 зм», имена через `find_item`, деньги `format_cp`).
- `master/hero.py:class_data` переводится на эти функции (минус ~10 строк; вывод `sheet_reference_block` байт-в-байт тот же —
  регресс `test_hero_sheet_prompt.py`). Это и есть «один источник разрешённого» для модели и мастера шагов (A0.3). `test_architecture`:
  `rules` не импортирует `master`/`game` — соблюдается (модуль только `content`/`rules`).

### A3. `rules/builder.py` — тексты валидатора доступны по частям (поведение Б1 не меняется)
- `ABILITY_MESSAGES = {"point_buy_invalid": "покупка очков: неверные значения или больше 27 очков", "standard_array_invalid":
  "стандартный набор: нужны 15,14,13,12,10,8 по разу", "abilities_invalid": "нужны все шесть характеристик со значениями от 3 до 20"}`,
  `BONUS_MESSAGE = "бонус предыстории: +2/+1 или +1/+1/+1"`, `over_twenty_message(ability) -> str` («характеристика выше 20 после
  бонуса: …»); `build_character` берёт тексты отсюда (строки 284–297) — те же байты.
- `name_problems(name, taken_names) -> list[(code, text)]` — тело нынешней `sheet_name_problems`, которая становится
  `return name_problems(sheet.choices.name, taken_names)`; `hooks_problems(motive, means) -> list[(code, text)]` — мотив/средства без
  opportunity, `sheet_hooks_problems` = `hooks_problems(...) + opportunity_problems(...)`. Сигнатуры `sheet_check`,
  `sheet_name_problems`, `sheet_hooks_problems` не меняются (тесты Б1а зелёные).
- `point_buy_cost(scores: dict[str,int], registry) -> int | None` (None — значение вне таблицы) — используется `check_ability_scores`
  (строки 163–168) и шагом покупки для остатка бюджета.
- `build_character` не трогаем сверх подстановки констант (сложность 177 — не раздувать).

### A4. `ui/hero_session.py` — две точки расширения
- `HeroSession.review_menu: tuple[str, ...] = REVIEW_MENU` (поле dataclass); `review()` и `choose()` берут меню из поля; поведение
  Б1 по умолчанию то же. Для пошагового: `WIZARD_REVIEW_MENU = ("Принять героя", "Вернуться к шагам", "Править поля вручную")` (Q3);
  пункт 2 перехватывает `HeroWizard` до делегирования (A6), `HeroSession.choose_review(2)` в этом режиме не вызывается.
- `RetryMenu(deps, leave_label=ERROR_MENU[2])` — вынос `choose_error`/`choose_model`: `fail(failure) -> Step` (подсказка `REFUSAL_HINT`
  при `refusal`, иначе `str(failure)`; меню «Повторить / Сменить модель / <leave_label>»), `menu` (текущее: ошибка или список
  моделей), `choose(number) -> RETRY | LEAVE | Step` (смена модели через `check_model`, затем снова меню ошибки; `deps.adapter/model`
  обновляются как сейчас), `state` (`"error_menu"` / `"model_choice"`). `HeroSession` хранит `retry = RetryMenu(deps)` и
  **зеркалит `self.state`** теми же строками (`describe_hero` в cli и тесты смотрят `session.state`): `propose()` при `TurnFailed` →
  `self.state = "error_menu"; return self.retry.fail(failure)`; `choose()` в `error_menu`/`model_choice` → `retry.choose(number)`:
  `RETRY` → `self.propose()`, `LEAVE` → `Step(quit=True)`, `Step` → вернуть и выставить `self.state = retry.state`. Тексты/меню —
  те же константы, `test_ui_hero_session.py` остаётся зелёным без правок (критерий рефакторинга).
- Константы меню/подсказок пошагового — в `ui/hero_wizard.py`, строки TUI — в `ui/tui/strings.py` (только placeholder).

### A5. `game/hero_steps.py` — черновик, таблица шагов, сборка листа (без UI)
- `Draft` (dataclass, поля `CharacterChoices` + `motive`, `means`, служебные): `species_id=""`, `class_id=""`, `background: str |
  BackgroundSpec | None`, `ability_method=""`, `scores: dict[str,int]` (заполняется по одной), `bonus_scheme: "2+1" | "1+1+1" | ""`,
  `bonus: dict[str,int]`, `class_skills: list`, `masteries: list`, `style: str | None`, `cantrips: list`, `spells: list`,
  `prepared: list`, `species_choices: dict`, `feat_picks: dict[str, list]`, `kit: str | None`, `gear: "equipment" | "gold"`, `name`,
  `motive`, `means`. `clear_from(draft, key)` — сбрасывает поля шага `key` и всех последующих (В6а «зависимые сбрасываются» —
  сброс «всё после» проще и всегда корректен, т.к. шаги упорядочены по зависимости).
- `StepDef` (frozen dataclass): `key`, `kind` (`pick` — один из вариантов; `multi` — N вариантов по одному; `text`; `number`),
  `title`, `needs` (функция `(draft, registry) -> bool`; `None` = всегда), `options` (`(draft, registry) -> list[Option(value, label)]`;
  для `multi` — уже без выбранных), `count` (`(draft, registry) -> int` для `multi`/повтора по характеристикам), `put`
  (`(draft, value, registry) -> str | None` — записать или вернуть **текст ошибки валидатора**), `hint` (для `text`/`number`).
  Все — функции модуля по имени (`put_species`, `options_class_skills`, …), не замыкания.
- `STEPS: tuple[StepDef, ...]` в порядке В1а с техническими вставками (Q9):
  1 `species` (pick, `species_options`, подпись `name`) → 2 `class` (pick) → 3 `background` (pick: 4 SRD по `name` + «Описать словами»;
  значение `words` обрабатывает автомат, A6) → 4 `method` (pick: «Стандартный набор (15,14,13,12,10,8)», «Покупка очков (27)»,
  «Свободный ввод (3..20)») → 5 `scores` (повтор ×6 по `ABILITIES` с подписью `ABILITY_NAMES`: standard — pick из оставшихся значений
  набора; point_buy — pick 8..15 с подписью «13 (5 очков)» и заголовком «осталось N очков»; explicit — number) → 6 `bonus_scheme`
  (pick «+2 и +1» / «+1, +1, +1») → 7 `bonus` (pick по характеристикам предыстории: для «2+1» две подряд (+2, затем +1 из оставшихся),
  для «1+1+1» — без вопроса, все три) → 8 `class_skills` (multi, `count = skill_choices.count`, `class_skill_options` минус навыки
  предыстории) → 9 `masteries` (multi, `needs = weapon_mastery_count > 0`, `mastery_weapons`) → 10 `style` (pick, `needs =
  has_fighting_style`) → 11 `cantrips` (multi, `needs = cantrips > 0`) → 12 `spells` (multi, `needs = spells > 0`, 1 круг) →
  13 `prepared` (multi из `draft.spells`, `count = min(prepared, len(spells))`, `needs = spells > 0`) → 14 `species_skill` (pick,
  `needs = "skill" in species_choice_keys`, навыки минус предыстория/класс) → 15 `species_feat` (pick, `needs = "feat" in keys`,
  `origin_feats(exclude=spec.feat)`) → 16 `feat_picks_bg` (multi, `needs = feat_choice_count(spec.feat) > 0`, `feat_pick_options`) →
  17 `feat_picks_species` (то же для черты вида; ключи через `origin_feat_keys`) → 18 `kit` (pick, `kit_label`) → 19 `gear` (pick:
  «Снаряжение предыстории» / «50 зм вместо снаряжения») → 20 `name` (text) → 21 `motive` (text) → 22 `means` (text, через запятую
  как `split_list` в `edit_sheet`, 1–3).
- Проверки на шаге (принцип, Q8): **множества из реестра фильтруются** (навыки, оружие, заклинания, черты, наборы — ошибка невозможна);
  **арифметика проверяется текстом валидатора**: `put_score` explicit вне 3..20 → `ABILITY_MESSAGES["abilities_invalid"]`; point_buy
  сверх остатка → `ABILITY_MESSAGES["point_buy_invalid"]` (меню показывает все 8..15 с ценой и остатком — так ошибка «покупка > 27»
  из критерия воспроизводима, как и в ИИ-пути); `put_bonus` при `score + bonus > 20` → `over_twenty_message(ability)` и возврат к шагу
  6; `put_name` → `name_problems(name, task.taken_names)` (пусто/занято — тексты `hero_name_empty`/`hero_name_taken`); `put_motive`/
  `put_means` → `hooks_problems` (пусто, > 200, не 1–3, > 120). Тексты — только импортом из `rules.builder`, не копией.
- `to_sheet(draft) -> HeroSheet`: `CharacterChoices(name, species_id, class_id, background (id или `BackgroundSpec`), ability_method,
  ability_scores, background_bonus, class_skills, weapon_masteries, fighting_style, spells = cantrips + spells, prepared,
  species_choices, feat_choices по `origin_feat_keys`, background_gear, class_kit)`, `motive`, `means`, `opportunity=[]`
  (В3а); `inventory`/`equip` пустые (снаряжение — набор класса и предыстория, как В12 Б1).
- `step_for_code(code) -> key` — куда вернуться, если финальный `sheet_check` всё же нашёл дефект (страховка: `class_skills_invalid` →
  8, `spells_invalid` → 11, `species_choices_invalid` → 14, `feat_choices_invalid` → 16, `*_bonus*`/`abilities_invalid` → 6,
  `point_buy_invalid`/`standard_array_invalid` → 4, `hero_name_*` → 20, `motive_*` → 21, `means_*` → 22, иначе → 1).
- `background_summary_lines(spec, registry) -> list[str]` — показать предысторию из ИИ перед следующим шагом (имя, характеристики,
  навыки, инструмент, черта, снаряжение/золото, описание) — подписи `ABILITY_NAMES`/`SKILL_NAMES`.

### A6. `ui/hero_wizard.py` — автомат шагов без терминала
- `HeroWizard(deps, task, width)` (dataclass, как `HeroSession`): `draft = Draft()`, `pos = 0` (индекс в `STEPS`), `partial: list`
  (набранное на `multi`/повторе), `history: list[(pos, draft_copy, partial)]` для «назад», `review = HeroSession(deps, task, width,
  review_menu=WIZARD_REVIEW_MENU)`, `retry = RetryMenu(deps, leave_label=BACK_TO_LIST)`, `state: "step" | "words" | "error_menu" |
  "model_choice" | "review"`, `run_ids: list` (только вызовы ИИ-предыстории), `stamp`. Свойства: `sheet` → `review.sheet`.
- `start() -> Step`: подсказка `WIZARD_HINT` («Собираем героя по шагам. Цифра — выбор, «назад» — шаг назад, «отмена» — выйти.») +
  текущий шаг. `show() -> Step`: для `pick`/`multi` — `menu_block(labels, title)` (title с прогрессом: «Навыки класса (1 из 2):»;
  «Характеристика Сила — осталось 20 очков:»); для `text`/`number` — `note_block(hint)`.
- `submit(line)`: `None` → `Step(quit=True)`; `state == "review"` → перехват «2» при `review.state == "review"` → `resume()`
  (возврат к последнему шагу, `draft` цел; Q3), иначе `review.submit(line)`; `state in (error_menu, model_choice)` → `retry.choose`
  (`RETRY` → повторить ИИ-вызов с тем же текстом, `LEAVE` → шаг 3 заново (список SRD, В2а), `Step` → показать); `"отмена"` →
  `Step(quit=True)` (`sheet is None`, как Esc в Б1); `"назад"` → `back()`; `state == "words"` → `background_call(line)`; иначе
  `pick(line)`. Диспетчер — таблица `state → метод`, ≤ 5 return (A0.1).
- `pick(line)`: `pick`/`multi` — цифра в диапазоне → значение (иначе `NO_SUCH`, как `HeroSession.choose`); `text`/`number` — строка
  как есть (пустая → повтор подсказки). `step.put(...)` вернул текст → `Step([note_block(text)])` + показать шаг снова; иначе
  `advance()`: для `multi`/повтора — пока `len(partial) < count`; потом `history.append`, `pos` → следующий шаг с `needs`; после
  последнего — `finish()`.
- `back()`: `history.pop()` → восстановить `draft`/`partial`/`pos`; пусто → `note_block(AT_START)`. На `multi` посреди набора «назад»
  снимает последний выбранный пункт (не весь шаг) — предсказуемо и дёшево.
- Шаг 3, значение `words`: `state = "words"`, `note_block(WORDS_HINT)` («Опишите предысторию словами…»); `background_call(text)`:
  `run_id = f"hero-{stamp}-{n}"` → `run_ids`; `propose_background(deps, BackgroundTask(draft.class_id), text, run_id)` (журнал/леджер
  — роль narrator, как Б1; меню 2.2 — ТЗ п. 6); успех → `draft.background = spec`, `Block("raw", background_summary_lines)` +
  следующий шаг; `TurnFailed` → `state = "error_menu"`, `retry.fail(failure)` (меню «Повторить / Сменить модель / Выбрать из списка»,
  Q4).
- `finish()`: `sheet = to_sheet(draft)`; `codes, messages = sheet_check(sheet, deps.registry, known=task.known,
  taken_names=task.taken_names)`; коды → `note_block("; ".join(messages))` и `pos = index(step_for_code(codes[0]))` (страховка, в
  тестах недостижима на пути меню); иначе `review.proposal = sheet; state = "review"; return review.review()` — дальше предпросмотр
  `preview_lines`, «принять» (`review.sheet`, `quit`), «править поля» (`edit_sheet` + `sheet_check`, те же тексты, что и в Б1).
- `run_ids` → `creation_cost_line` в cli, только если не пусто (Q6).

### A7. CLI (`ui/cli.py`), простой режим, TUI, заставка
- `choose_hero`: `names = [пресеты] + [CREATE_HERO, CREATE_HERO_STEPS]`; возвращает `NEW_HERO` или новый сентинел `STEP_HERO`
  (`number == len(presets) + 2`). Пак без пресетов (недостижимо, loader) — как сейчас `NEW_HERO` (В11, Q12).
- `make_hero_session(kind, deps, task, width)` (новая плоская функция вне `prepare`): `STEP_HERO` → `HeroWizard`, иначе `HeroSession`.
  В `prepare`: условие `if hero is NEW_HERO or hero is STEP_HERO:` → `created = HeroCreateDeps(...)` как сейчас; `session =
  make_hero_session(hero, created, task, width)`; строка цены — `if session.run_ids:`. `prepare` уже помечен (98/17) — новых smells
  не добавляет; правки — 4 строки. `--hero-describe` — только `HeroSession` (без изменений). Отмена → `discard_world` как сейчас.
- Простой режим: `create_hero_simple` — без изменений (A0.2); `emit_blocks` печатает `menu`/`note`/`raw`.
- TUI: `HeroCreateApp(session, placeholder=strings.CREATE_PLACEHOLDER)` — параметр placeholder; `tui.create_hero(session,
  placeholder=...)`; `strings.STEPS_PLACEHOLDER = "Номер пункта или значение («назад» — шаг назад, Esc — отмена)"`; `cli.create_hero_tui`
  передаёт placeholder по типу сессии (`isinstance(session, HeroWizard)`). Остальное в `HeroCreateApp` — без изменений (worker-поток
  нужен шагу «описать словами»).
- Заставка (В5а, Q5): `art_for_event("title")` — в `PickerApp` (новый `RichLog(id="feed", wrap=False)`/`Static` над `#choices`,
  строки в `on_mount` до `show`) и в `HeroCreateApp.on_mount` (в `#feed` до `start()`), тем же `title.split("\n")`, что `AiDmApp`
  (16 строк, `art/data/title.txt`). Основной `AiDmApp` — как сейчас. Простой режим — без изменений (заставка там уже при старте
  `simple.run`).
- `vulture_allowlist.py`: снять `propose_background` и `BackgroundTask` (появились потребители). README/`--help` — новых флагов нет;
  описание пункта меню — в README.

### A8. Документы
ARCHITECTURE (`rules.hero_options`; `rules.builder` — тексты по частям; `game.hero_steps`; `ui.hero_wizard` + композиция с
`HeroSession`, `RetryMenu`; `ui/cli` `STEP_HERO`/`make_hero_session`; TUI placeholder и заставка), README (пункт «Создать пошагово»,
навигация «назад»/«отмена»), BACKLOG 16 (снять «заставка до выбора героя»; «HeroPickerApp внутрь App» → явно Д1; записать исключение
по лимиту smells с причиной и целью вернуть; хвост (б) «защита `HeroSession.submit` от исключений» — не Б2), HANDOFF (статусы, расходы),
`docs/plan-b2.md`, `docs/plan-b2.md`, `docs/plan-b2.md`.

## B. Партии

### Б2а. Шаги, автомат, простой режим, мок (L)
1. `rules/hero_options.py` (A2); `master/hero.py:class_data` на него (регресс промпта). 2. `rules/builder.py` — `ABILITY_MESSAGES`,
`BONUS_MESSAGE`, `over_twenty_message`, `point_buy_cost`, `name_problems`, `hooks_problems` (A3). 3. `game/hero_steps.py` — `Draft`,
`StepDef`, `STEPS`, функции шагов, `to_sheet`, `step_for_code`, `background_summary_lines` (A5). 4. `ui/hero_session.py` — `review_menu`,
`RetryMenu` (A4). 5. `ui/hero_wizard.py` — `HeroWizard` (A6). 6. `ui/cli.py` — `CREATE_HERO_STEPS`, `STEP_HERO`, `choose_hero`,
`make_hero_session`, `prepare` (4 строки), цена только при `run_ids` (A7). 7. `vulture_allowlist.py` — снять две записи. 8. ARCHITECTURE,
README, BACKLOG 16, Makefile `SMELLS_MAX` (C/Q1).

Тесты Б2а (doeba; в `tests/unit/game/hero_kit.py` добавить `wizard_picks(**kw) -> list[str]` — канонический сценарий ответов для
человека-воина/солдата/стандартного набора, воспроизводящий `base_sheet()` Б1 с `background="soldier"`; `walk(wizard, lines)`;
`first_option_walk(wizard)` — политика «всегда 1», для `text` — заготовки имени/мотива/средств):
- `tests/unit/rules/test_hero_options.py` (новый): воин — `mastery_weapons` содержит `longsword`, волшебник — пусто;
  `has_fighting_style` воин/следопыт да, плут/жрец/волшебник нет; `class_spells(wizard, 0)` — только заговоры из списка волшебника,
  `(…, 1)` — 1 круг; `origin_feats(exclude="skilled")` оставляет `skilled` (repeatable), `exclude="alert"` убирает `alert`;
  `feat_pick_options` без занятых навыков/инструмента предыстории; `class_skill_options` без навыков предыстории; `point_buy_table`
  (8..15, 27); `kit_label` — русские имена предметов и «зм». `test_hero_sheet_prompt.py` (+): `sheet_reference_block` до/после —
  одинаковый текст (снимок на `vale`).
- `tests/unit/rules/test_builder.py` (+): `build_character` тексты арифметических ошибок равны `ABILITY_MESSAGES[...]`/
  `over_twenty_message` (прямое сравнение); `point_buy_cost` на {все 8} = 0, {15×6} = 54, значение 16 → None; `name_problems`/
  `hooks_problems` дают те же пары, что `sheet_name_problems`/`sheet_hooks_problems` на листе с теми же значениями.
- `tests/unit/game/test_hero_steps.py` (новый): последовательность ключей шагов для воина/человека/солдата (есть 9, 10, 14–16, нет 11–13,
  17), для волшебника/эльфа/мудреца (есть 11–13, нет 9, 10, 14–17), для следопыта (нет 11, есть 12–13, 10); `options`: навыки класса
  исключают навыки предыстории; `species_skill` исключает класс+предыстория+черты; `masteries` на втором выборе без первого; standard
  — оставшиеся значения; point_buy — заголовок с остатком и подпись «(N очков)»; `put_score` explicit 21 → текст
  `ABILITY_MESSAGES["abilities_invalid"]`, 2 → тот же; point_buy сверх остатка → `point_buy_invalid`; `put_bonus` 19+2 →
  `over_twenty_message("str")`; `put_name` пустое/занятое (`taken_names` пака: имя NPC vale, регистр) → тексты `hero_name_*`;
  `put_motive` пусто/201 символ; `put_means` 0 и 4; `clear_from("class")` обнуляет всё после; **`to_sheet(draft по wizard_picks) ==
  base_sheet(background="soldier", opportunity=[])`** (канон Б1); `step_for_code` таблица; **свойство валидности**: для всех видов ×
  классов × 4 предысторий × 3 методов `first_option_walk` → `sheet_check == ([], [])` (240 комбинаций, без ИИ).
- `tests/unit/ui/test_ui_hero_session.py` (без правок — критерий рефакторинга A4) + `test_ui_retry_menu.py` (новый): `fail` с
  `refusal` → `REFUSAL_HINT`; меню 3 пункта с `leave_label`; `choose` → `RETRY`/`LEAVE`; «2» → список `model_options`; выбор модели →
  `FactorySpy` вызван, `deps.adapter/model` обновлены, снова меню ошибки; негодная модель → текст `check_model` и меню ошибки.
- `tests/unit/ui/test_ui_hero_wizard.py` (новый, `ScriptedAdapter` только для шага словами): `start` — подсказка + меню видов (4, русские
  имена); «9» → `NO_SUCH`; текст на меню → `NO_SUCH`; полный `wizard_picks` → `review` с предпросмотром и меню
  `WIZARD_REVIEW_MENU`; «1» → `sheet == base_sheet(...)`, `quit`; «2» → снова шаг 22 с подсказкой, затем «назад» ×2 возвращает к
  имени с прежним значением; «3» → `edit` (та же логика `edit_sheet`: `class_skills = acrobatics, …` при навыке предыстории →
  `SKILL_CONFLICT_MESSAGE`, «готово» → ревью); «назад» на первом шаге → `AT_START`; «назад» после класса на шаге предыстории → меню
  классов, `draft.class_id == ""`; «назад» посреди `multi` снимает один пункт; «отмена» → `quit`, `sheet is None`; point_buy: шесть
  «15» → на шестой шаг текст `point_buy_invalid`, затем «8» проходит; explicit «21» → текст и повтор; бонус 19+2 → текст и шаг 6;
  предыстория словами: `spec_call` → `draft.background` BackgroundSpec, `raw`-блок с «Бывший цирковой акробат», `run_ids == ["hero-…-1"]`,
  журнал `role=narrator`, `turn_seq 0`; `TurnFailed("invalid")` → меню с «Выбрать из списка», «3» → меню предысторий (5 пунктов),
  «1» (Повторить) → новый `run_id`; `refusal` → `REFUSAL_HINT`; смена модели → `FactorySpy`; без ИИ `run_ids == []`; заклинатель
  (волшебник): 3 заговора, 6 заклинаний, 4 подготовленных из выбранных — предпросмотр содержит «Заклинания (ячейки …)».
- `tests/unit/ui/test_ui_cli.py` / `test_cli_hero_describe.py` (+): `choose_hero` для `vale` — 5 пунктов, последний
  `CREATE_HERO_STEPS`, «5» → `STEP_HERO`; интерактив простого режима: `cli([--new --world w1 --seed 7 --mock <script без hero_sheet>
  --saves], ["5", "1", *wizard_picks(), "1", "/quit"])` → код 0, слот `auto` с героем листа, `meta/hero_sheet.json`, заметка «Герой на
  лету: …», **нет** строки «Создание героя:»; тот же путь с «описать словами» (скрипт `background_spec` + текст) → строка цены есть;
  `--replay --world w1 --seed 7` без `--hero` → без расхождения; «отмена» на шаге → «Герой не выбран», код 1, каталога нет;
  `make_hero_session` по типу.
- **Сценарий `tests/scenarios/test_b2_done.py`** (критерий): три героя тремя методами через `HeroWizard` → ошибки (point_buy, 21,
  бонус > 20, занятое имя) **текст == `sheet_check` на листе с тем же дефектом** (через `edit_sheet` канона Б1) → исправление → ревью →
  принять → `new_world_from_pack(hero=sheet, preset_id="heroic")` → мок-ход → `save_current` → `load_slot` → имя, класс, набор,
  `motive/means` целы, `opportunity == []`; replay (`cli --replay`) без расхождения; волшебник и жрец пошагово — `spells_known`/
  `spells_prepared` в лимите (`sync_resources` ячейки). `test_stage6b_done.py` — регресс (без правок).
- `test_architecture`: `rules/hero_options.py` попадает под сторож «engine не импортирует верхние слои» (импортирует только
  `content`/`rules`); `ui/hero_wizard.py` берёт `BackgroundTask` из `protocol.context` так же, как `cli` берёт `SheetTask` — существующие
  сторожа (`master` не импортирует `game`/`ui`, `game` не импортирует `ui`) не нарушаются; новых сторожей не нужно.

### Б2б. TUI, заставка, живой прогон (S/M)
1. `ui/tui/create.py` — `placeholder` параметр; `ui/tui/__init__.py` `create_hero(session, placeholder)`; `strings.STEPS_PLACEHOLDER`;
`cli.create_hero_tui` передаёт по типу. 2. Заставка: `PickerApp` (виджет над `#choices`), `HeroCreateApp.on_mount` (A7). 3. README,
ARCHITECTURE (ui), HANDOFF. 4. **Живой прогон** (пользователь, В10а, Q10): `ai-dm --new --campaign vale` (TUI) → «Создать пошагово» →
пресет «Как в паке» → герой стандартным набором (воин) → 3–5 ходов → `/save`, перезапуск `--world` → `/sheet`; то же покупкой очков
(жрец, заклинания) и свободным вводом (волшебник) в простом режиме `--simple`; один прогон с «описать словами» (цена в `/cost`,
при refusal — меню); итог — `docs/plan-b2.md`.

Тесты Б2б (doeba):
- `tests/unit/ui/tui/test_tui_create.py` (+, Pilot без сна): `HeroCreateApp(HeroWizard(...), placeholder=STEPS_PLACEHOLDER)` — после
  монтирования в `#feed` 16 строк заставки, затем подсказка, в `#choices` меню видов; цифра «1» с пустым вводом → следующий шаг;
  ввод «назад» → предыдущее меню; ввод имени текстом; Esc → `return_value is None`; полный `wizard_picks` → «1» → `return_value`
  `HeroSheet`; шаг словами с `GateAdapter` — статус «Мастер думает…», `#input` disabled, после ответа `raw`-блок предыстории; placeholder
  русский.
- `tests/unit/ui/tui/test_tui_entry_points.py` (+): `PickerApp` показывает заставку над пунктами (строки `title.txt` в виджете), пункт
  «Создать пошагово» последний; `test_tui_russian.py` (+): `PickerApp` с заставкой и `HeroCreateApp` с `STEPS_PLACEHOLDER` без латиницы
  (заставка — ASCII-рисунок: проверить, что сторож латиницы его не ловит, иначе исключить `#feed`-строки рисунка как в `test_tui_art`).
- `tests/scenarios/test_b2_done.py` (+): `test_tui_and_simple_stepwise_give_the_same_hero` — один список ответов через
  `cli([...], ["5", "1", *picks, "1", "/quit"])` и через `HeroCreateApp(HeroWizard)` (Pilot) → равные `hero_dump` (образец
  `test_stage6b_done.py:229–278`).

## C. Качество (каждый шаг)
- **Лимит smells (Q1): `SMELLS_MAX = 205`.** Обоснование: 203 — фактическая база main (дрейф после Б1-фикс, не разгружаем чужие модули —
  решение проектировщика); +2 — бюджет ровно на файловые флаги «High total complexity» для двух новых плотных модулей
  (`game/hero_steps.py`, `ui/hero_wizard.py`), если они перевалят ~98 (A0.1); всё остальное — +0 по правилам Б1 (≤ 4 именованных
  параметра + `*`, ≤ 5 return, диспетчеры таблицей, без вложенности 5). Ratchet в Makefile «только вниз» — исключение записывается в
  BACKLOG 16 с целью: если Б2 закроется на ≤ 203, лимит опускается обратно в том же коммите. Альтернативы — в Q1.
- `make cov` ≥ 94%, `make dead` (allowlist: −2 записи, новых нет), `make mutate FUNCS="…" TESTS="…"`.
- Б2а FUNCS: `ai_dm.rules.hero_options:*` (все публичные), `ai_dm.rules.builder:point_buy_cost`, `…:name_problems`, `…:hooks_problems`,
  `…:over_twenty_message`, `…:check_ability_scores` (новые строки), `ai_dm.game.hero_steps:*` (все `needs_*/options_*/count_*/put_*`,
  `to_sheet`, `clear_from`, `step_for_code`, `background_summary_lines`), `ai_dm.ui.hero_session:RetryMenu.fail`, `…:RetryMenu.choose`,
  `…:HeroSession.propose`, `…:HeroSession.choose` (новые строки), `ai_dm.ui.hero_wizard:HeroWizard.start`, `…:submit`, `…:pick`,
  `…:advance`, `…:back`, `…:background_call`, `…:finish`, `…:show`, `ai_dm.ui.cli:choose_hero`, `…:make_hero_session`, `…:prepare` (новые
  строки), `ai_dm.master.hero:class_data`. TESTS — `tests/unit/{rules,game,ui,master}` + сценарий. Б2б: `ui.tui.*` — mutmut не гонять
  (segfault, BACKLOG 16), только Pilot; `ai_dm.ui.cli:create_hero_tui`.
- WINDOW мока (`memory_script.py`, 22070) — без изменений: промпт нарратора не трогается; `sheet_reference_block` — байт-в-байт
  (тест A2). Doeba подтверждает `test_stage4_memory` зелёным.
- Ревью мамы-кабана — каждая партия; решения и расходы — HANDOFF / `docs/plan-b2.md`, `docs/plan-b2.md`.

## D. Риски
1. **Файловые smells на новых модулях** — бюджет +2 (C). Если `hero_steps.py` разрастается (22 шага × 3–4 функции) — делить на
   `hero_steps.py` (таблица, Draft, to_sheet) и `hero_step_rules.py` (options/put), не дробить функции искусственно.
2. **Расхождение «меню разрешило — валидатор отверг»** — закрыто по построению: множества — одни функции для промпта и шагов (A2);
   арифметика — одни константы (A3); страховка `finish()` + свойство валидности на 240 комбинациях. Если свойство падает — дефект в
   `hero_options`, а не в валидаторе.
3. **ИИ посреди ручного мастера** (риск 5 груминга): один вызов, журнал `hero-…`, меню 2.2 через `RetryMenu`; при `LEAVE` — список SRD
   (В2а). Replay: записи `hero-…` уже фильтруются `replay_records`. Отмена после вызова — `discard_world` (слотов нет).
4. **Рефакторинг `HeroSession` (A4)** — критерий «тесты Б1б без правок зелёные»; `describe_hero` смотрит `session.state` — имена
   состояний сохраняются.
5. **Зарезервированные слова «назад»/«отмена»** на текстовых шагах (имя героя «Назад» невозможно) — допустимо; в TUI есть Esc.
6. **Point buy и «только допустимые»** — меню показывает все 8..15 (чтобы ошибка критерия воспроизводилась тем же текстом); остаток в
   заголовке. Если проектировщик предпочтёт фильтр — Q8(б), критерий по point_buy тогда проверяется только через `edit_sheet`.
7. **Заставка в нескольких App подряд** (пикер героя → пикер пресета → экран создания → основной) — Q5; высота 16 строк + меню до 24
   пунктов в `PickerApp` на малом терминале (40 строк хватает; `Choices` без прокрутки — проверить Pilot на 140×30).
8. **Объём Б2а — L** (22 шага, условные ветви, три метода, ИИ-шаг); Б2б — S/M за счёт A0.2. Делить Б2а дальше не стоит: автомат без
   таблицы шагов не тестируется.
9. **Латиница в тесте русского TUI** — ASCII-заставка в `#feed` `PickerApp`: сторож `test_tui_russian` может поймать; прецедент —
   `test_tui_art` (рисунки исключены).
10. **`BackgroundTask.class_skills=()`** при словами — `background_check` не проверяет конфликт; меню навыков класса потом исключает
    навыки предыстории — конфликт невозможен (A0.7). Если игрок вернётся «назад» и сменит предысторию на SRD после выбора навыков —
    `clear_from` сбрасывает навыки (всё после шага 3), конфликт невозможен.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1. Лимит smells.** **(а) 205** — факт 203 + 2 на файловые флаги новых модулей, с записью исключения в BACKLOG 16 и возвратом вниз,
  если не понадобилось; (б) 203 — без бюджета: любой новый smell = перепланировка посреди партии; (в) 210 — прежний уровень этапа 5,
  скрывает регрессии.
- **Q2. Автомат.** **(а) `HeroWizard` отдельно + хвост (ревью/правка/2.2) композицией `HeroSession`** (A1, A4); (б) новые состояния в
  `HeroSession` (рост `submit/choose`, smells, хрупкость тестов Б1); (в) полная копия хвоста в новом классе (дубли, два источника текстов).
- **Q3. Меню ревью пошагового пути.** **(а) «Принять героя / Вернуться к шагам / Править поля вручную»** — возврат на последний шаг с
  целым черновиком, дальше «назад»; (б) как в Б1 («Переописать с замечанием» → ИИ-вызов по готовому листу через `feedback/previous` —
  второй ИИ-путь, цена); (в) только «Принять / Править».
- **Q4. Сбой ИИ на «описать словами».** **(а) меню «Повторить / Сменить модель / Выбрать из списка»** (третий пункт = В2а «назад к
  SRD»); (б) без меню — сразу список SRD с подсказкой; (в) как в Б1 — «Выйти» третьим, список SRD через «назад».
- **Q5. Заставка (В5а).** **(а) в пикере героя и на экране создания**, пикер пресета — без; основной экран как сейчас; (б) во всех трёх
  App до игры; (в) только в пикере героя.
- **Q6. Строка «Создание героя: $…»** при пошаговом без ИИ — **(а) не печатать** (`run_ids` пуст); (б) печатать «$0 (0 вызовов)».
- **Q7. Навигация.** **(а) слова «назад» / «отмена» в любом месте, в TUI плюс Esc = отмена**; (б) цифра «0» = назад (конфликт с
  меню из 10 пунктов — заклинания); (в) оба.
- **Q8. Проверки на шаге.** **(а) множества из реестра фильтруются, арифметика (бюджет, 3..20, ≤ 20 после бонуса, имя, мотив/средства)
  проверяется текстами валидатора; point buy показывает все 8..15 с ценой и остатком**; (б) фильтровать и бюджет (ошибка критерия по
  point buy — только через `edit_sheet`); (в) всё проверять в конце (В7б — отвергнуто).
- **Q9. Технические вставки в порядок В1а.** **(а) выборы вида (навык/черта), выборы черт и мотив/средства — после навыков класса,
  перед набором/именем** (фильтрация занятого); (б) строго при виде/предыстории, конфликты — в конце страховкой.
- **Q10. Живой прогон (В10а).** **(а) три метода (по одному на TUI/простой) + один с «описать словами»** (цена/refusal в `/cost`,
  `docs/plan-b2.md`); (б) три метода без ИИ-шага.
- **Q11. Источник вариантов.** **(а) вынести запросы `class_data` в `rules/hero_options.py`, промпт и мастер шагов — на них**
  (один источник, снимок промпта байт-в-байт); (б) мастер шагов считает сам (два источника, риск 2).
- **Q12. Пак без пресетов героя** (В11а, недостижимо на loader) — **(а) `choose_hero` как сейчас → сразу «на лету»**; (б) меню из двух
  пунктов «на лету / пошагово».

Технические умолчания на аппрув вместе с планом: сентинел `STEP_HERO`, подпись пункта «Создать пошагово»; `multi`-шаги — по одному
выбору с прогрессом в заголовке; «назад» посреди `multi` снимает один пункт; `clear_from` сбрасывает всё после шага; средства — через
запятую (как `edit_sheet`); `opportunity = []`; `inventory/equip` пусты (снаряжение — набор класса + предыстория); `run_id`
`hero-<stamp>-<n>` только у ИИ-шага; `BackgroundTask(class_id, class_skills=())`; при `TurnFailed` на шаге словами описание игрока
сохраняется для «Повторить»; `HeroCreateApp` без изменений кроме placeholder; `--hero-describe` не меняется; сейв v8.

## Решения проектировщика (2026-10-09)
Q1 (а) лимит smells 205 с возвратом вниз при итоге ≤ 203; Q2 (а) HeroWizard + композиция HeroSession; Q3 (а) «Принять / Вернуться к шагам / Править поля вручную»; Q4–Q12 — по рекомендациям (вариант а).

## Решения: Груминг партии Б2 — «Пошаговый режим создания героя» (свинопас, 2026-10-09) (бывш. docs/decisions/b2-grooming.md)

Источники: roadmap-r4-unified (#3 Б2, риски), ROADMAP-PLAN (блок Б стр. 165–166, п. 16 стр. 332), BACKLOG 16 (хвосты Б1а/Б1б,
HeroPicker, заставка), 34, 35; stage6-grooming (п. 12, В6, аудит стр. 169, решения стр. 188), b1-grooming, B1-PLAN (Q6, Q10),
b1-a/b1-b-review, b1-live, b1-fix-review, b1-audit; TZ 5, 6 (стр. 353–358, 501–508); код на 99d29cb.

### Готовность

**Не готова к плану до ответов на В1–В5** (блокирующие). Остальные В6–В12 можно закрыть по рекомендации.
Механика есть почти вся: валидатор листа, сессия создания, сейв листа, replay листа. Не решено, *что* игрок вводит руками
и *чем* закрываются мотив/средства/возможности и предыстория в пошаговом пути. Версия сейва — v8, новая не нужна:
итог пошагового пути — тот же `HeroSheet` в `meta/hero_sheet.json`.

**Стоп-сигнал до начала:** `make smells` на main (99d29cb) = **203 при лимите 202** (замер свинопаса 2026-10-09;
в BACKLOG 16 записано 202/202 — либо дрейф после Б1-фикс, либо «плавание» Qlty, как раньше 208–212). Первый шаг Б2 —
вернуть ≤ 202 и иметь запас, иначе любая новая функция ломает ворота.

### Что есть в коде (факты)

- `rules/builder.py:38` `CharacterChoices` — все поля листа 1 ур.; `ability_method` уже `standard_array | point_buy | explicit`
  (стр. 44). `check_ability_scores` (стр. 156) проверяет все три метода; таблицы `srd/data/tables/point_buy.yaml`
  (8..15, budget 27) и `standard_array.yaml`. Значит «три метода» в движке есть — нет только UI ввода.
- `rules/builder.py:236` `build_character` — сложность 177 (smells); `sheet_check` (стр. 555) — единый валидатор: лист +
  предыстория + имя + motive/means/opportunity. Требует непустой `motive` и 1–3 `means` (стр. 541–552) — пошаговый путь
  без ответа на В3 провалит валидацию.
- `rules/builder.py:213` `class_kit_problem`, `apply_class_kit` — стартовые наборы класса (`starting_kits` в
  `srd/data/classes/*.yaml`, у каждого класса a/b). `background_gear` `equipment | gold`.
- Выборы, которые нужно задать по шагам (из `CharacterChoices`): вид → `species_choices` (skill/feat Универсальности,
  `species_choice_keys` стр. 172) → класс → навыки класса (`skill_choices.count/options`) → мастерства → стиль боя →
  заклинания и подготовленные (волшебник: 3 заговора, 4 подготовленных) → `feat_choices` (Одарённый: 3) → предыстория
  (SRD id или `BackgroundSpec`) → бонус +2/+1 / +1/+1/+1 → метод и значения → набор класса/вариант предыстории → надеть.
  Строка роадмапа «класс → навыки → снаряжение» — сокращение; шагов ~12.
- `game/hero_create.py:235` `SHEET_FIELDS` — 32 поля ручной правки «поле = значение» (Б1, В3); `edit_sheet` (стр. 267).
  Это уже «свободный ввод полей», но не пошаговый мастер.
- `game/hero_create.py:53` `propose_background` и `protocol/context.py:88` `BackgroundTask` (режим `hero_background`) —
  оставлены под Б2 (B1-PLAN Q6: «класс руками, предыстория словами»), в `vulture_allowlist.py:91–92` с пометкой «Б2».
- `ui/hero_session.py:37` `HeroSession` — автомат состояний describe/review/remark/edit/error_menu/model_choice без
  терминала; один и тот же для TUI (`ui/tui/create.py:10` `HeroCreateApp`) и простого режима (`ui/cli.py:197`).
  Итог — `HeroSheet`, дальше путь общий (`ui/cli.py:704–728`: `new_world_from_pack`, `write_hero_sheet`, цена создания).
- Точка входа: `ui/cli.py:140` `choose_hero` — пункты «пресеты пака + Создать героя на лету»; пак без пресетов — сразу
  NEW_HERO, но loader требует ≥1 пресет (`campaign/loader.py:258`, BACKLOG 16 (в)). `--hero-describe` (`ui/cli.py:681`) —
  неинтерактивный ИИ-путь. Пошагового флага нет.
- `ui/cli.py:577` `prepare` — сложность 98, 17 return (smells): любая новая ветка старта пойдёт сюда.
- Replay: `ui/cli.py:686` при `--replay` герой берётся из `read_hero_sheet` — пошаговый `HeroSheet` воспроизведётся без
  изменений, если итог пишется тем же `write_hero_sheet`.
- TUI: `AiDmApp.__init__(session, startup)` (`ui/tui/app.py:56`) требует готовый `GameApp` (`session.app`), т.е. мир уже
  построен. Пикеры (`ui/tui/__init__.py:26` `pick`→`PickerApp`, стр. 35 `create_hero`→`HeroCreateApp`) — отдельные App до
  основного. Заставка `art_for_event("title")` пишется только в `AiDmApp.on_mount` (`ui/tui/app.py:111–114`) — до выбора
  героя её нет (BACKLOG 16, P6).
- «HeroPickerApp внутрь основного App» = основной App стартует без мира, мир строится внутри него. Это перестройка
  `prepare` (сложность 98) и `AiDmApp`, а не косметика.

### Короткое ТЗ

**Цель.** Новый мир можно начать героем, собранным по шагам руками (ТЗ 5 «альтернативно — пошаговый классический
режим»; ТЗ 6: три метода характеристик). Равноправно ИИ-пути (stage6, решение стр. 188), не fallback.

**Входит.**
1. Разгрузка smells до ≤ 202 с запасом — первым шагом.
2. Пошаговая сессия создания (по образцу `HeroSession`, без терминала): шаги из «Факты» в порядке В1; на каждом шаге —
   меню вариантов из реестра (только допустимые для уже выбранного), ввод значений для метода характеристик; назад/
   отмена (В6). Итог — `HeroSheet`, проверка `sheet_check`, тот же лист на подтверждение, что в Б1 (принять / править
   поля — существующий `edit_sheet`).
3. Три метода характеристик: стандартный набор (распределить 15,14,13,12,10,8), покупка очков (остаток бюджета 27 виден),
   свободный ввод 3..20; бонус предыстории с проверкой ≤ 20.
4. Предыстория — по В2. Мотив/средства/возможности — по В3.
5. Точка входа — пункт в `choose_hero` (В4); TUI и простой режим одним автоматом.
6. Журнал/`/cost`: если в шаге есть ИИ-вызов — `run_id hero-…`, роль narrator, меню 2.2 (как Б1).
7. Снять `propose_background`/`BackgroundTask` из vulture_allowlist (использовать или удалить — по В2).
8. Хвосты п. 16 — по В5 (App и заставка).

**Не входит.** Уровни выше 1 (К0+); новые классы/виды; import (Б3); пак без пресетов героя (loader, BACKLOG 16 (в)) —
если не решено иначе в В11; means/opportunity в `HeroPreset` пака (BACKLOG 34).

**Готово, когда.**
- Мок-сценарий: пошагово герой каждым из трёх методов → ошибка (напр. покупка очков > 27, бонус выше 20) с тем же текстом,
  что у валидатора → исправление → подтверждение → мир → ход → сейв/загрузка (лист и motive/means/opportunity целы) →
  replay мира с пошаговым героем.
- TUI и простой режим дают одинакового героя одним скриптом (как `test_tui_and_simple_creation_give_the_same_*`).
- Заклинатель (волшебник или жрец) собирается пошагово: заговоры и подготовленные в лимите.
- make smells ≤ 202, make dead чисто, mutmut по новым функциям.
- Живой прогон — по В10.

### Риски

1. **smells 203/202 уже сейчас.** Новый автомат + ветка в `prepare` (98) почти наверняка добавят smells.
2. **Объём занижен.** Роадмап даёт M, но шагов ~12, условные (стиль боя только у воина, заклинания только у заклинателей,
   выборы вида/черт), плюс три метода с интерактивным распределением. С хвостами п. 16 — L.
3. **Хвост «App внутрь» — перестройка старта.** `AiDmApp` требует готовый мир; перенос ломает текущий порядок `prepare`
   и тесты точек входа TUI. Оговорка роадмапа «если не раздувают объём» — по фактам раздувают.
4. **Валидатор в конце, а не на шаге.** `sheet_check` валидирует лист целиком; если шаги не фильтруют варианты сами,
   игрок узнает об ошибке через 10 шагов. Фильтрация вариантов по шагу — новая логика рядом с валидатором, риск расхождения
   «меню разрешило — валидатор отверг» (Б-2: тексты ошибок должны быть одни).
5. **Предыстория словами в пошаговом пути** — ИИ-вызов посреди ручного мастера: цена, refusal, меню 2.2 в середине шагов.
6. **Мутанты замыканий** (`SHEET_FIELDS`, BACKLOG 16 Б1а) — если шаги построены так же, mutmut будет плохо их мутировать.

### Развилки — вопросы проектировщику (рекомендация первой)

- **В1 [блок.] Порядок шагов.** **(а) вид → класс → предыстория → характеристики (метод, значения, бонус) → навыки класса →
  мастерства/стиль → заклинания → снаряжение → имя** (как в SRD 2024: предыстория до характеристик, т.к. бонус зависит от
  неё); (б) класс → навыки → снаряжение первым (дословно строка роадмапа), вид и предыстория после; (в) свободный порядок —
  меню «что заполнить», готово когда всё заполнено.
- **В2 [блок.] Предыстория в пошаговом пути.** **(а) выбор: одна из 4 SRD или «описать словами» → `propose_background`
  (режим `hero_background`, ИИ-вызов, меню 2.2)** — использует оставленный под Б2 код; (б) только 4 SRD, режим
  `hero_background` удалить; (в) ручной ввод полей `BackgroundSpec` (характеристики, навыки, инструмент, черта, снаряжение
  ≤ 50 зм).
- **В3 [блок.] Мотив/средства/возможности.** Валидатор требует motive и 1–3 means. **(а) ручной ввод motive и means текстом,
  opportunity — пусто (0 разрешено)**; (б) ИИ дописывает их по готовому листу (ещё один вызов); (в) ослабить валидатор для
  пошагового пути (motive/means необязательны) — меняет решение Б1.
- **В4 [блок.] Точка входа.** **(а) третий пункт в `choose_hero`: «Создать пошагово»** рядом с «Создать на лету»;
  (б) внутри ИИ-пути: «Создать героя» → меню «словами / пошагово»; (в) пошаговый — только из меню 2.2 при сбое ИИ
  (fallback — stage6 аудит отметил, что ТЗ говорит «альтернативно», не fallback).
- **В5 [блок.] Хвосты п. 16 (App внутрь, заставка).** **(а) в Б2 только заставка в пикере/экране создания (дёшево);
  «внутрь основного App» — отдельной партией или в BACKLOG**, т.к. это перестройка `prepare` и `AiDmApp`;
  (б) оба хвоста в Б2 (тогда делить, см. В12); (в) оба — в BACKLOG.
- **В6 Навигация.** **(а) «назад» на шаг и отмена; после шага, от которого зависят следующие (класс, вид, предыстория),
  зависимые шаги сбрасываются**; (б) только вперёд, правка — в конце через `edit_sheet`.
- **В7 Варианты на шаге.** **(а) меню показывает только допустимые для уже выбранного (навыки класса без навыков
  предыстории и т.п.), тексты ошибок — из валидатора**; (б) показывать всё, проверять в конце `sheet_check`.
- **В8 Стандартный набор — ввод.** **(а) по характеристике выбрать значение из оставшихся**; (б) одной строкой
  «15 14 13 12 10 8» в порядке СИЛ..ХАР. Покупка очков — так же, с остатком бюджета.
- **В9 Неинтерактивный путь.** **(а) не нужен: мок-тесты гонят автомат напрямую**; (б) флаг вроде `--hero-steps <файл>`
  для скриптового прогона.
- **В10 Живой прогон.** **(а) короткий: пошаговый герой каждым методом, мир, 3–5 ходов, сейв/загрузка; без цены, если
  предыстория не словами**; (б) не нужен, хватит мока; (в) полный как у Б1 (10–15 ходов, `/cost`).
- **В11 Пак без пресетов героя** (BACKLOG 16 (в), loader требует ≥1). **(а) не трогать в Б2**; (б) снять запрет сейчас —
  с пошаговым и ИИ-путём такой пак становится осмысленным.
- **В12 Деление.** **(а) Б2а — разгрузка smells + пошаговый автомат + простой режим + мок; Б2б — TUI, заставка, (хвост App,
  если В5б), живой прогон**; (б) одной партией M, если В5а.

Решения за проектировщика, молча не принятые: порядок шагов, предыстория/мотив в пошаговом пути, точка входа, объём хвостов
п. 16, деление. Технически без вопроса (решение разработки): автомат — отдельный класс рядом с `HeroSession`, а не новые
состояния в нём (иначе `choose` растёт и бьёт smells).

### Аудит кабана-свекрови (2026-10-09)

**Что проверено:** docs/plan-b2.md (неотслеживаемый файл, main 99d29cb); выборочно пути:строки в коде;
`make smells`.

**Источники истины:** roadmap-r4-unified #3 Б2 (+ #6 Д1); ROADMAP-PLAN блок Б (стр. 165–166), п. 16 (стр. 332);
BACKLOG 16, 34, 35; stage6-grooming (аудит, решения 2026-10-07); TZ 5, 6.

Факты о коде проверены выборочно и совпадают: `builder.py:38/236/555`, `hero_create.py:53/235`, `hero_session.py:37`,
`cli.py:140/577`, `tui/app.py:56`, `loader.py:258`, `context.py:88`, `vulture_allowlist.py:91–92`.
`make smells` = **203 (max 202)** — подтверждено, стоп-сигнал верный.

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| «Технически без вопроса: автомат — отдельный класс рядом с `HeroSession`» | конец документа | ниоткуда (решение свинопаса) | к архитектору (папа-кабан) как предложение, не как принятое; пользователю — только уведомить. Не «решение разработки» груминга |
| В2(б) «только 4 SRD, `hero_background` удалить» | В2 | противоречит ТЗ 6 («предыстории — свободные, нарративные», «4 SRD — примеры») | вариант допустим только с пометкой «отступление от ТЗ»; пометки нет — дописать |
| В3(в) «ослабить валидатор, motive/means необязательны» | В3 | противоречит ТЗ 5 («герою тоже задаются мотив/средства/возможности») и Б1 | то же: пометить как отступление от ТЗ |
| В4(в) «пошаговый — только fallback» | В4 | уже отвергнуто проектировщиком 2026-10-07 (равноправен) | убрать вариант или пометить «закрыто решением 2026-10-07» |
| В1(а) порядок «как SRD 2024», а не «класс → навыки → снаряжение» роадмапа | В1 | роадмап vs SRD; рекомендация расходится с буквой роадмапа | к пользователю — вынесено корректно |
| Пересмотр размера M → L, деление Б2а/Б2б | Риски 2, В12 | ниоткуда (оценка свинопаса) | к пользователю — вынесено корректно |
| Хвост «App внутрь»: варианты «отдельной партией или в BACKLOG» | В5 | роадмап: «если не раздувают объём» | к пользователю; не предложен очевидный дом — партия **Д1** (хвосты TUI п. 16, после Б2–Б3) |
| Разгрузка smells первым шагом Б2 | Входит 1 | ворота make smells (факт 203/202) | оставить, но это работа вне темы Б2: пользователь должен знать, что в Б2 войдёт рефакторинг чужих модулей (что именно разгружать — не сказано) |
| В11 «снять запрет пака без пресетов» | В11 | BACKLOG 16 (в), не в Б2 роадмапа | к пользователю, рекомендация (а) «не трогать» — ок |
| В9(б) новый флаг `--hero-steps` | В9 | ниоткуда | рекомендация (а) «не нужен» — ок; новый CLI-флаг только с согласия |
| Критерий «Готово»: три метода, заклинатель, replay | Готово | ТЗ 6 + вывод грумера | расширение критерия — утвердить пользователем вместе с В1–В5 |
| BACKLOG 35 в источниках | шапка | к Б2 не относится (баги Б1-фикс) | мелко, оставить |

Пропущенные вопросы:
- Имя героя, мотив и пр. — **проверка уникальности имени** (`taken_names` в `sheet_check`) в пошаговом пути — не упомянута; мелко.
- Свободный ввод 3..20 — до бонуса или итог? ТЗ 6 говорит «3..20, после бонуса ≤ 20»; в В8 про свободный ввод не спрошено, как вводить (по характеристике / строкой). Мелко, можно закрыть вместе с В8.
- Если В2(а) — где в порядке В1 стоит ИИ-вызов предыстории и что при сбое ИИ (меню 2.2 откатывает на шаг или к выбору SRD). Риск 5 назван, вопроса нет.
- Взаимодействие с Д1: Ctrl+C при подготовке мира (Д1) и новая ветка `prepare` — не отмечено.

Варианты без рекомендации: нет — у всех В1–В12 рекомендация первой.

**Решения за пользователя:** молча принятых продуктовых решений нет. Одно архитектурное решение записано как принятое
(«отдельный класс рядом с `HeroSession`») — перевести в предложение архитектору. Пересмотр размера партии (M → L) и
деление — решение пользователя, вынесено (В12).

**Итог:** факты верны, стоп-сигнал smells подтверждён. Нужны решения пользователя: В1–В5, В12, критерий «Готово»;
до передачи папе-кабану — пометить В2(б), В3(в) как отступления от ТЗ, снять/пометить В4(в) как закрытый, переписать
строку «технически без вопроса» в предложение архитектору, добавить Д1 как вариант в В5.

### Решения проектировщика (2026-10-09)
- В1 (а): порядок как в SRD 2024 — вид → класс → предыстория → характеристики → навыки → мастерства/стиль → заклинания → снаряжение → имя.
- В2 (а): одна из 4 SRD или «описать словами» через propose_background; при сбое ИИ — назад к выбору из 4 SRD. Вариант «только SRD» снят (противоречит ТЗ 6).
- В3 (а): motive и 1–3 means игрок вводит сам, opportunity пустой. Вариант «ослабить валидатор» снят (ТЗ 5, решение Б1).
- В4 (а): третий пункт в choose_hero «Создать пошагово». Вариант «только запасной путь» снят (решение 2026-10-07).
- В5 (а): заставка до выбора героя — в Б2; HeroPickerApp внутрь основного App — в Д1.
- В6–В11 по рекомендациям (а): шаг назад со сбросом зависимых шагов; только допустимые варианты, тексты ошибок из валидатора; стандартный набор / покупка очков / свободный ввод 3..20 — по одной характеристике; без неинтерактивного флага; короткий живой прогон (каждый метод, 3–5 ходов, сейв/загрузка); запрет пака без героев не трогать. Уникальность имени — как в sheet_check (taken_names).
- В12 (а) и объём: L, деление Б2а (автомат, простой режим, мок) + Б2б (TUI, заставка, живой прогон). Критерий «Готово»: три метода характеристик, пошаговый заклинатель, replay мира с пошаговым героем.
- smells: **поднять лимит** под Б2 вместо разгрузки чужих модулей (новое значение предлагает папа-кабан в плане, утверждает проектировщик).
- «Автомат — отдельный класс рядом с HeroSession» — не решение, а предложение архитектору (по аудиту).

## Правки по ревью: Ревью партии Б2а (мама-кабан, 2026-10-09) (бывш. docs/decisions/b2-a-review.md)

Проверено: незакоммиченный diff поверх f772440 — `rules/hero_options.py`, `game/hero_steps.py`, `ui/hero_wizard.py`,
правки `rules/builder.py`, `master/hero.py`, `ui/hero_session.py`, `ui/cli.py`, `Makefile`, `vulture_allowlist.py`, тесты.
Сверка с `docs/plan-b2.md` (A0–A8) и `docs/plan-b2.md`.

### Что хорошо
- Слои A1 соблюдены: `rules/hero_options.py` чистый (только `content`/`rules`); `class_data` переведён на него без смены вывода.
- A3: тексты ошибок вынесены (`ABILITY_MESSAGES`, `over_twenty_message`, `point_buy_cost`, `name_problems`,
  `motive_problems`/`means_problems`), `build_character` изменён только подстановкой констант; сигнатуры `sheet_*` целы.
- A4: `RetryMenu` вынесен, `HeroSession.state` зеркалится, тесты Б1 без правок.
- Шаги — функции модуля, без замыканий (урок mutmut). `to_sheet` по `origin_feat_keys` корректен (черта предыстории всегда первая).
- Тесты: `test_b2_done.py` закрывает критерий (три метода, тексты ошибок сверяются с `sheet_check`, мир → ход → сейв/загрузка →
  replay, волшебник и жрец); `test_ui_hero_wizard.py` — назад/отмена/words/меню 2.2/страховка `finish`.

### Блокеры
Нет.

### Желательно
1. `src/ai_dm/ui/hero_wizard.py:131`, `src/ai_dm/game/hero_steps.py:525` — признак «ввод строкой» сейчас «список вариантов пуст».
   Если у `multi`/`pick` шага варианты кончились (все навыки заняты и т.п.), любая строка уйдёт в `apply_put` и запишется
   в черновик без фильтра; финальный `sheet_check` поймает, но шаг уже «принят». Предложение: решать по `step.kind`
   (`text` — строка; для свободного ввода характеристик — `kind="number"`, как в плане A5), а пустое меню у `pick`/`multi`
   считать `NO_SUCH`/пропуском шага.
2. `src/ai_dm/ui/hero_wizard.py:95` — «отмена» перехватывается до делегирования в ревью, в т.ч. в режиме ручной правки
   (`review.state == "edit"`): игрок, набравший «отмена» при правке поля, теряет весь собранный лист без подтверждения.
   В Б1 Esc при правке — та же отмена, так что это согласовано с В6а; но стоит хотя бы тестом зафиксировать намеренность
   (сейчас `test_cancel_works_on_text_step_and_in_review` — только меню ревью).
3. `src/ai_dm/ui/cli.py:745` — для пошагового героя печатается «Герой на лету: …». Строка цены уже условна (Q6);
   подпись стоит развести (или нейтральное «Герой: …»), иначе в живом прогоне Б2б это будет вводить в заблуждение.

### Мелочи
4. `src/ai_dm/game/hero_steps.py:79-80` — `taken_names` живёт в `Draft` (служебное поле) и копируется в каждый снимок истории;
   в плане — `task.taken_names`. Работает, но черновик смешивает выбор игрока и контекст мира. Можно передать через
   `registry`-подобный аргумент `put` или оставить с комментарием «не сбрасывается `clear_from`» (сейчас неочевидно).
5. `src/ai_dm/game/hero_steps.py:186` — `point_buy_cost({**draft.scores, "next": number}, ...)`: фиктивный ключ `"next"`.
   Яснее `point_buy_cost(...) + cost_of(number)` или ключ следующей характеристики `ABILITIES[len(draft.scores)]`.
6. `src/ai_dm/game/hero_steps.py:573` `item_name` и `src/ai_dm/rules/hero_options.py:91-92` — одна и та же логика
   «имя через `find_item` или id»; вынести в `hero_options` и переиспользовать (Qlty дубли, BACKLOG 16).
7. `src/ai_dm/ui/hero_wizard.py:109-112` — «назад» в меню ошибки (2.2) отвечает «Нет такого варианта.»; по WIZARD_HINT
   игрок ждёт, что «назад» работает везде. Либо обработать как «Выбрать из списка», либо оставить и зафиксировать тестом.
8. `src/ai_dm/rules/builder.py` — `hooks_problems` используется только `sheet_hooks_problems`; шаги зовут
   `motive_problems`/`means_problems` напрямую. Отклонение от A3 безвредно, но промежуточная функция лишняя — можно склеить.
9. `tests/scenarios/test_b2_done.py:258` — `["5", "1", ...]`: номер «Создать пошагово» захардкожен (зависит от числа
   пресетов пака). Взять из `len(hero_presets(pack)) + 2` или найти пункт по тексту `CREATE_HERO_STEPS`.

### Известные расхождения (оценка)
- Заклинания `count = min(лимит, контент)` (`hero_steps.py:279-287`): приемлемо как временная мера, но тест
  `test_cleric_has_no_cantrips_in_content...` закрепляет дыру контента — при пополнении (BACKLOG) его надо будет перевернуть;
  стоит пометить тест ссылкой на пункт BACKLOG.
- Draft/StepDef с `attr/label/on_error`, `to_sheet(draft, registry)`: проще плана в реализации диспетчера, план не нарушает.
- «Вернуться к шагам» через `back()` откатывает последний шаг (средства) — ожидаемо по снимкам; тексты подсказки это не
  объясняют, игроку придётся ввести средства заново — для Б2б достаточно строки в подсказке ревью.
- Боевой стиль следопыта с 2 ур. и `make smells` 205/205 — по решению, замечаний нет.

**Вердикт:** можно мержить после пунктов 1 и 3 (остальное — по желанию).

### Решения проектировщика


- Р1 (2026-10-09): заметка мира для пошагового героя — «Герой пошагово: …» (путь ИИ остаётся «Герой на лету: …»).
- Р2: «отмена» в режиме ручной правки (edit) возвращает к ревью; выход без героя — «отмена»/Esc из ревью и шагов.
- Р3: править все замечания 1, 4–9 и пометить тест «у жреца нет заговоров» ссылкой на BACKLOG 16 (пополнение заклинаний — отдельная партия).

- mutmut после правок: новые строки — 0 выживших (кроме эквивалентного «готово»→«ГОТОВО» в cancel); cli:prepare — 278 выживших на старых строках → BACKLOG 16.

## Правки по ревью: Ревью партии Б2б (мама-кабан, 2026-10-09) (бывш. docs/decisions/b2-b-review.md)

Проверено: незакоммиченный diff поверх 6ae8ca7 — `ui/cli.py` (`pick_tui`, `choose_number`, `create_hero_tui`),
`ui/tui/{__init__,create,modals,strings}.py`, `ui/hero_wizard.py` (`REVIEW_HINT`), README, ARCHITECTURE, BACKLOG, тесты
`test_tui_create.py`, `test_tui_entry_points.py`, `test_tui_russian.py`, `test_b2_done.py`, `test_cli_hero_describe.py`.
Сверка с `docs/plan-b2.md` (Б2б, A7, A8, D7, Q5) и решениями Б2а (`docs/plan-b2.md`, Р1–Р3).

### Что хорошо
- A7 сделан как в плане: `placeholder` у `HeroCreateApp`/`tui.create_hero`, `STEPS_PLACEHOLDER` дословно, выбор по
  `isinstance(session, HeroWizard)` в `cli.create_hero_tui`.
- Q5а соблюдён: заставка только в пикере героя (флаг `splash`, по умолчанию `False`) и на экране создания; пикер пресета без неё.
  Флаг пробрасывается `choose_number -> pick_tui -> tui.pick -> PickerApp`, дефолт закрыт тестом.
- Заставка рисуется так же, как в `AiDmApp` (`art_for_event("title")`, `split("\n")`, проверка на `None`).
- Подсказка ревью `REVIEW_HINT` закрывает замечание Б2а про откат средств.
- Тесты: Pilot на заставку над меню, цифра с заставкой, отсутствие заставки без флага, TUI = простой режим в `test_b2_done.py`.
- BACKLOG: P6 закрыт, «внутрь основного App» явно отнесено к Д1.

### Блокеры
Нет.

### Желательно
1. `src/ai_dm/ui/tui/modals.py` `PickerApp.compose` — `RichLog(id="feed")` создаётся всегда, а `#feed` в `app.tcss` имеет
   `height: 1fr` и рамку. Значит пикер пресета мира (splash=False) теперь показывает пустую рамку на весь экран над меню, раньше
   её не было. Предложение: `if self.splash: yield RichLog(...)` (и в `on_mount` писать только при splash), либо класс-модификатор
   с `display: none`. Добавить Pilot-проверку: без заставки `#feed` нет (или не отображается).
2. Риск 80x24 (вопрос тестера). По CSS: `#choices` — `height: auto; max-height: 12; overflow-y: auto`, `#feed` — `1fr`.
   Меню не пропадёт: оно ограничено 12 строками и прокручивается, лента получает остаток. Следствие — в 80x24 у пикера героя
   ~10 строк ленты на 16 строк заставки: `RichLog` прокрутит к концу, верх рисунка срежется. Это косметика, не потеря управления.
   Достаточно одного Pilot-теста `size=(80, 24)`: пункты героя видны (`choice-N` в регионе экрана) и цифра выбирает —
   рядом с уже существующими тестами 80x24 в `test_tui_entry_points.py`. План D7 (140x30) этот случай не покрывает.
   На экране создания то же самое; там лента и так прокручиваемая, риска нет.
3. `src/ai_dm/ui/cli.py:135` — `what == "героя"`: признак заставки выводится из русского слова-подписи. Работает, но связь
   хрупкая (правка текста выключит заставку молча). Проще передавать флаг четвёртым элементом `menu` или аргументом
   `choose_number(..., splash=True)` из `choose_hero`.

### Мелочи
4. `src/ai_dm/ui/hero_wizard.py` `REVIEW_HINT` — «средства придётся ввести заново» верно, пока `means` последний шаг `STEPS`.
   Тест на подсказку стоит связать с `STEPS[-1].key == "means"`, чтобы перестановка шагов его уронила.
5. ARCHITECTURE: «пикер пресета мира — тот же `PickerApp`» читается как «тоже с заставкой»; дописать «без заставки (`splash=False`)».

**Вердикт:** можно мержить после пункта 1 (и желательно теста 80x24 из пункта 2); остальное — по желанию.

### Решения проектировщика


- Р1 (2026-10-09): править все замечания 1–5 до коммита.

## Итог: Живой прогон Б2 (пошаговое создание героя), 2026-10-09 (бывш. docs/decisions/b2-live.md)

Прогон — пользователь, по чек-листу (B2-PLAN Б2б шаг 4, Q10а). Все пункты пройдены.

- TUI, воин стандартным набором: заставка в пикере героя и на экране создания, пикер пресета без заставки и рамки; шаги, «назад», ошибки, ревью (принять / вернуться к шагам / править), отмена в правке → ревью; «Герой пошагово: …», строки цены нет.
- Игра 3–5 ходов, тон по пресету; хвост Б1 п.5 (grim→heroic, выбор цифрой) — не воспроизвёлся, закрыт. `/save` → `--world` → `/sheet` — герой тот же.
- Простой режим: жрец покупкой очков (остаток, ошибка бюджета, заклинания; заговоров нет — BACKLOG 16), волшебник свободным вводом (ошибка на 21).
- «Описать словами»: «Мастер думает…», блок предыстории, цена в ленте и `/cost` — ≈ $0,01. Отказов модели не было; меню 2.2 проверено.
- Отмена (Esc / «отмена») — выход без героя.

Багов и замечаний нет. Б2 закрыта; дальше — Б3.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- Б2б: kaban ~53+58+65 тыс.; kaban-doeba ~91+100 тыс. (~46 мин); mama-kaban ~46 тыс.; артефакт роадмапы ~99 тыс.
- Б2а: kaban ~200+10 тыс. (~18 мин); kaban-doeba ~279+17 тыс. (~1,9 ч, mutmut); mama-kaban ~75 тыс.
- Б2 груминг: svinopas ~93 тыс. (~4 мин); kaban-svekrov ~37 тыс.; papa-kaban (план) ~186 тыс. (~13 мин).
