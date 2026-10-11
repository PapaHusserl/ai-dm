# План партии Б2: «Пошаговое создание героя» — Б2а (шаги, автомат, простой режим, мок) и Б2б (TUI, заставка, живой прогон)

Автор: папа-кабан, 2026-10-09. Статус: **предложение на аппрув** (решения проектировщика В1–В12 из
`decisions/b2-grooming.md`, раздел «Решения проектировщика», обязательны и приняты за основу). Основа: `decisions/b2-grooming.md`
(ТЗ свинопаса, аудит свекрови, решения), `B1-PLAN.md` (форма, A6, Q6/Q10), `decisions/roadmap-r4-unified.md` (#3 Б2, #6 Д1),
`ROADMAP-PLAN.md` (стр. 165–166, 332), `BACKLOG.md` 16 (хвосты Б1а/Б1б, HeroPicker, заставка), 34, `TZ.md` 5 / 6,
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
`decisions/b2-a-review.md`, `b2-b-review.md`, `b2-live.md`.

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
при refusal — меню); итог — `decisions/b2-live.md`.

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
- Ревью мамы-кабана — каждая партия; решения и расходы — HANDOFF / `decisions/b2-a-review.md`, `b2-b-review.md`.

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
  `decisions/b2-live.md`); (б) три метода без ИИ-шага.
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
