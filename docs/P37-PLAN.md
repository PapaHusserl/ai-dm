# План партии П37 «Подсказка пака к пресету мира» (papa-kaban, 2026-10-12; на аппрув проектировщика)

Задача: BACKLOG 37 по решениям docs/decisions/p37-grooming.md (раздел «Решения»): В1б `CampaignManifest.preset` (принята смена
тона паков по умолчанию), В2а, В3а (пикер пака — BACKLOG 40), В4а, В5а, В6а, В7 (romantic → dusk_academy, grim → drunk_dragon,
heroic → vale; fairytale без пака), В8а. Размер S (≈0,5–0,6 млн по шкале R5), сейв v9, миграций нет, схема сейва не трогается.
Старт — после К0-фикса (пересечения — раздел «Риски»). Код на 1caa0a7 + рабочее дерево К0-фикс-а (cli.py, campaign/*, presets
им не тронуты).

## Что показал код (сверка перед планом)

- `CampaignManifest.preset: str = ""` (`campaign/models.py:77`); ни один из `campaigns/{vale,drunk_dragon,dusk_academy,test}`
  его не заполняет. `pick_tone(manifest, preset_id)` (`campaign/build.py:127–133`): `preset_id or manifest.preset`; пусто
  или `"pack"` → тон пака как есть и без записи хроники; иначе `apply_preset(manifest.tone, preset)` + запись хроники
  `kind="tone"`, «Пресет мира: <name>». `apply_preset` (`campaign/presets.py:41`): **оси, mood и notes — из пресета**,
  `hard_limits`/`soft_limits` — объединение (пак первым). `check_manifest` (`campaign/loader.py:263`) уже проверяет, что
  `manifest.preset` есть в каталоге (или `pack`) — чужое значение = ошибка загрузки пака.
- `/tone` меняет mood, оси и лимиты, **notes не меняет** (`tests/unit/game/test_game_tone.py` шапка) — голос пака, замещённый
  пресетом, в игре не вернуть.
- CLI (`ui/cli.py`): `preset_label(preset)` (187) — «Имя (в духе «codename») — описание»; `choose_preset(stdin, stdout,
  notes, setup)` (194) — `[PRESET_AS_PACK] + [preset_label(p) …]` через `choose_number` (TUI `pick_tui` / `ask_choice` в
  simple — один код); `None`/пункт 1 → `None` («как в паке» → сработает `manifest.preset`). `prepare` (747): пак грузится
  (845) → `choose_hero` → `choose_preset` только при интерактивном герое и без `--preset` (859–860) → `new_world_from_pack(…,
  preset_id=preset)` (889) → строка «Мир: {id}, сид N, пресет X» (918–923) только в не-replay ветке. `preset_refusal`
  (696) валидирует `--preset`. `Setup.campaigns_dir` (88) — каталог паков (`CAMPAIGNS_DIR` по умолчанию, тесты подменяют через
  `cli(..., campaigns_dir=…)` из `tests/unit/ui/ui_kit.py:169`).
- Реестра/перечисления паков нет; в `campaigns_dir` кроме паков бывают временные каталоги импорта `.import-<id>-XXXX`
  (`game/pack_import.py:21`, с готовым `campaign.yaml` до `rename`) и чужие паки без `preset` (`campaigns/test` — untracked).
- Пункты меню: simple — `format.menu_lines` переносит по `WIDTH = 80` (метки пресетов уже 102–118 символов, переносятся);
  TUI — `Choices.show` пишет `Static(Text("N. метка"))` (`ui/tui/widgets.py:98`), переносится сам. `preset_label(p)` с
  одним аргументом используют тесты `tests/unit/ui/tui/test_tui_entry_points.py:1341 preset_names()`.
- Тесты, которые сейчас фиксируют «тон vale/дракона = тон манифеста» и сломаются от `preset` в манифестах:
  `tests/unit/ui/test_cli_preset.py` — `test_no_preset_keeps_pack_tone` (62), `test_interactive_preset_as_in_pack_keeps_pack_tone`
  (265), `test_interactive_end_of_input_on_preset_means_as_in_pack` (276); `tests/unit/campaign/test_vale_pack.py:134`
  `test_vale_tone_keeps_mood_and_has_typed_scales` (mood == «приключенческое фэнтези»); `tests/unit/campaign/test_dragon_pack.py:154`
  `test_dragon_tone_is_approved` (horror «умеренно», language «сдержанно» — у grim «сильно»/«грубо»). Не ломаются:
  `test_preset_pack_keeps_pack_tone_and_labels_note` (`--preset pack`), `test_no_preset_has_no_preset_note` (`--hero arn`,
  строки нет), сценарии `test_b2_done`/`test_stage6b_done` (явный `preset_id="heroic"`), `test_stage4_memory` (бандл
  `make_bundle`, без пака — WINDOW 22450 не плывёт), golden `tests/golden/*` (из сейва v4_dragon и sim_combat), фикстуры
  `tests/fixtures/saves/*` (тон в сейве).
- `make smells` сейчас **205/206** (замер 2026-10-12 на рабочем дереве с К0-фикс-а).

## Что именно поменяется у паков (pick_tone при «Как в паке» / без `--preset`)

Живые миры не трогаются (тон лежит в `world.json`). Меняются только **новые** миры этих паков без `--preset` или с «Как в
паке»; `--preset pack` по-прежнему даёт тон манифеста без наложения. У всех трёх появится запись хроники «Пресет мира: …».

| Пак → пресет | Было (манифест) | Станет (apply_preset) | Что теряется |
|---|---|---|---|
| **vale → heroic** | mood «приключенческое фэнтези», оси пустые («не задано»), notes пусто, лимитов нет | mood «героическое приключенческое фэнтези», violence реалистично, horror умеренно, romance намёки, language сдержанно, notes = голос heroic | ничего по сути; рассказчик получает явные оси и голос |
| **drunk_dragon → grim** | mood «Тёмное героическое фэнтези: расследование заговора, болота, культ, чума; редкие тёплые моменты с Мило и знамения Селунэ», violence жестоко, horror умеренно, romance откровенно, language сдержанно, лимитов нет, notes = 3 строки стиля игры («маленькими кусками», «статус/снаряжение/расстояния — конкретно», «мета-игрово:») | mood «мрачное фэнтези, моральная серость», violence жестоко (=), **horror сильно**, romance откровенно (=), **language грубо**, notes = голос grim | сюжетный mood и **все три строки стиля игры** (это предпочтения игрока; `/tone` notes не правит) |
| **dusk_academy → romantic** | mood «Романтическое доброе фэнтези: …первая влюблённость, дружба и уютные вечера», violence мягко, **horror нет**, romance намёки, language сдержанно, hard_limits [жестокость к беззащитным, смерть близких героя], soft_limits [кровь мельком], notes = 4 строки (тёплый тон; ночной народ — соседи, не чудовища; романтика медленная, без пошлости; бой — редкость) | mood «романтическая драма и социальные интриги», violence мягко (=), **horror умеренно**, **romance чувственно** (принято), language (=), лимиты пака **сохраняются** (merge_limits), notes = голос romantic | mood пака, horror «нет» → «умеренно», строки «без пошлости», «ночной народ — не чудовища», «старое проклятие» |

Смена romance у dusk_academy принята проектировщиком; horror и потеря notes у dusk_academy и drunk_dragon в груминге не
назывались — вынесены в Q1/Q2.

## Реализация (kaban)

### 1. Данные: `preset` в манифестах трёх паков
1.1. `campaigns/vale/campaign.yaml` — после блока `tone:` строка `preset: heroic`; `campaigns/drunk_dragon/campaign.yaml` —
   `preset: grim` между `tone:` и `flags:`; `campaigns/dusk_academy/campaign.yaml` — `preset: romantic`. `campaigns/test`
   (untracked, пак пользователя) и `tests/fixtures/packs/mini` — без изменений. Значения уже валидируются `check_manifest`.
1.2. (Q1/Q2, если выбрано «смягчить данными») — правки `soft_limits`/`world.md` соответствующих паков, отдельным коммитом данных.

### 2. Обратный индекс «пресет → паки» — `src/ai_dm/campaign/presets.py`
2.1. Новая функция `preset_packs(campaigns_dir) -> dict[str, list[tuple[str, str]]]`: обходит `sorted(Path(campaigns_dir).iterdir())`;
   берёт только каталоги, имя которых не начинается с `.` (временные `.import-*` пропускаются), в которых есть `campaign.yaml`;
   читает его `yaml.safe_load` **без** `CampaignManifest` (дёшево и терпимо к чужим/битым пакам — В8а: ошибка YAML,
   не-mapping, отсутствие ключей → каталог молча пропускается); `preset = data.get("preset")`; пусто или `PACK_TONE` → пропуск;
   иначе `result[preset].append((pack_id, name))`, где `pack_id = data.get("id") or имя каталога`, `name = data.get("name") or
   pack_id`. Несуществующий `campaigns_dir` → `{}`. Списки отсортированы по `pack_id` (порядок обхода). Модуль остаётся без
   новых импортов, кроме `Path`. Проверять существование пака не нужно — индекс строится из того, что реально лежит в
   `campaigns_dir` (В8а само собой: удалённый пак в индекс не попадёт).

### 3. Подсказка в CLI — `src/ai_dm/ui/cli.py`
3.1. `preset_label(preset, hint="")`: как сейчас; при непустом `hint` — `f"{label} {hint}"`. Сигнатура с одним аргументом
   сохраняется (тесты TUI зовут `preset_label(p)`).
3.2. Новая `pack_hints(campaigns_dir, current_id) -> dict[str, list[tuple[str, str]]]`: `preset_packs(campaigns_dir)` без
   записей текущего пака (`pack_id != current_id`), пустые списки выброшены. Так «текущий пак — не он» решается один раз для
   меню и для заметок (В4а/В5а).
3.3. Новая `hint_suffix(packs) -> str` (текст пункта меню, В4а): `"Лучше подходит пак «Академия Сумеречного Мыса»
   (dusk_academy)."`; несколько паков — `«A» (a), «B» (b)`; пусто → `""`.
3.4. Новая `hint_lines(preset_id, hints, presets) -> list[str]` (заметки старта, В2а/В5а): `preset_id` пустой, `PACK_TONE` или
   без паков → `[]`; иначе по строке на пак: `Пресету «Чувства и интриги» лучше подходит пак «Академия Сумеречного Мыса»:
   новый мир — ai-dm --new --campaign dusk_academy --preset romantic`. Текст про **новый** мир — не «сменить сейчас» (риск 2
   груминга).
3.5. `choose_preset(stdin, stdout, notes, setup, hints=None)`: `hints = hints or {}`; `names = [PRESET_AS_PACK] +
   [preset_label(p, hint_suffix(hints.get(p.id, ()))) for p in presets.values()]`. Возврат и нумерация не меняются; TUI и
   `--simple` получают один и тот же текст через `choose_number`.
3.6. `prepare`: рядом с `created = None` — `hints = {}`; в ветке нового мира сразу после `load_pack` — `hints =
   pack_hints(campaigns_dir, pack.manifest.id)`; вызов `choose_preset(…, hints)`; в не-replay ветке сразу после строки
   «Мир: …» — `for line in hint_lines(preset, hints, load_presets()): say(notes, line)`. Ветка `--replay` (914–916) и `--world`
   (hints пустые) строк не дают; `--hero`/`--hero-describe` без `--preset` — `preset is None` → строк нет (В6а). `--preset`
   с паком, у которого этот же пресет (`--campaign dusk_academy --preset romantic`) — строк нет. В `prepare` добавляются
   3 строки, логика — в помощниках (smells 205/206).

### 4. Docs
`docs/BACKLOG.md` п.37 — сделано (ссылка на план и ревью), п.25 — приписка «manifest.preset заполнен у vale/drunk_dragon/
dusk_academy — тон по умолчанию = пресет (решение П37)»; п.40 без изменений. `docs/handoff.md` — строка П37. Чек-лист
`docs/checklist-p37-live.md` (не коммитить): пройти **на `--mock`** (без расходов): TUI на vale — пункты romantic и grim с
подсказкой, heroic без; выбрать romantic — после «Мир:» строка с командой; выполнить команду → dusk_academy, подсказки нет,
`/tone` показывает romance чувственно, horror умеренно, хроника «Пресет мира: Чувства и интриги»; то же в `--simple`;
`--preset grim` на vale → строка про drunk_dragon; новый мир drunk_dragon «Как в паке» → `/tone` language грубо, horror сильно.

## Изменённые функции для mutmut (`make mutate FUNCS=… TESTS=…`)
- `ai_dm.campaign.presets:preset_packs` — TESTS tests/unit/campaign/test_presets.py tests/unit/campaign/test_preset_packs.py
- `ai_dm.ui.cli:preset_label ai_dm.ui.cli:pack_hints ai_dm.ui.cli:hint_suffix ai_dm.ui.cli:hint_lines ai_dm.ui.cli:choose_preset`
  — TESTS tests/unit/ui/test_cli_preset.py tests/unit/ui/test_ui_cli.py
- `prepare` мутациями не гоняем (огромная, узкие TESTS); три новые строки покрываются CLI-тестами ниже.

## Тесты (kaban-doeba, TDD)

Правка существующих (ломаются от п.1):
- `tests/unit/ui/test_cli_preset.py`: `test_no_preset_keeps_pack_tone`, `test_interactive_preset_as_in_pack_keeps_pack_tone`,
  `test_interactive_end_of_input_on_preset_means_as_in_pack` → ожидание `world.tone == apply_preset(pack.manifest.tone,
  load_presets()[pack.manifest.preset])` и ровно одна запись хроники `kind="tone"` «Пресет мира: Героическое приключение»
  (переименовать: «as in pack = manifest preset»). `test_interactive_preset_menu_has_pack_item_and_four_presets` — пункты с
  подсказкой длиннее и переносятся по 80: если окно `start:start+6` перестанет вмещать 5 номеров — считать номера по всему
  блоку меню до строки `> `/первой ненумерованной. `test_no_preset_has_no_preset_note` и
  `test_preset_pack_keeps_pack_tone_and_labels_note` — без правок, должны остаться зелёными (контроль В6а и `pack`).
- `tests/unit/campaign/test_vale_pack.py:134` → `pack.manifest.tone.mood == "приключенческое фэнтези"` (данные) + новый
  `world.tone == apply_preset(manifest.tone, heroic)`. `tests/unit/campaign/test_dragon_pack.py:154–166` → «approved»
  проверять на `dragon_pack().manifest.tone` (данные пака не меняются), отдельно `world.tone == apply_preset(manifest.tone,
  grim)` и `manifest.tone.notes` непуст.

Новые — каталог и данные (`tests/unit/campaign/test_preset_packs.py`, фикстуры через `campaign_kit.default_files/write_pack`
с подменой `id`/`name`/`preset`):
- `preset_packs(dir)`: пак `rose` (`preset: romantic`, name «Розы») и `mini` без поля → `{"romantic": [("rose", "Розы")]}`; два
  пака на один пресет → список по `id` (`aa` раньше `rose`); `preset: pack` → нет; каталог `.import-rose-abc` с валидным
  `campaign.yaml preset: grim` → не учтён; каталог без `campaign.yaml`, файл вместо каталога, битый YAML, YAML-список,
  `name` отсутствует (→ имя = id) — не падает; несуществующий `dir` → `{}`; `campaign.yaml` без `id` → id = имя каталога.
- Данные репозитория (В7/В8а; фильтровать по трём известным id — локально у пользователя лежит untracked `campaigns/test`):
  `{k: v for k, v in preset_packs(CAMPAIGNS_DIR).items()}` для паков `vale`, `drunk_dragon`, `dusk_academy` ==
  `{"heroic": [("vale", "Вейл")], "grim": [("drunk_dragon", "Пьяный Дракон")], "romantic": [("dusk_academy", "Академия
  Сумеречного Мыса")]}`; `fairytale` без пака; у каждого пресета ≤ 1 пака среди трёх; каждый из трёх паков грузится
  (`load_pack`, уже есть в test_vale_pack/test_dragon_pack — для dusk_academy добавить, если нет).
- Тон по умолчанию трёх паков (`new_world_from_pack` без `preset_id`): `world.tone == apply_preset(manifest.tone,
  presets[manifest.preset])`; одна запись «Пресет мира: <name>»; `preset_id="pack"` → `manifest.tone` и записей нет;
  dusk_academy сохраняет `hard_limits` (2) и `soft_limits` (1) пака, romance «чувственно», horror «умеренно»; drunk_dragon
  romance «откровенно», language «грубо»; vale romance «намёки».

Новые — CLI (`tests/unit/ui/test_cli_preset.py`, временный `campaigns_dir` с `mini` (без preset) и `rose` (romantic, «Розы»),
`cli(..., campaigns_dir=root)`, `--campaign mini`):
- `preset_label(p)` без хинта — прежняя строка; `preset_label(p, "X")` → `"… X"`. `hint_suffix([])` → `""`;
  `hint_suffix([("rose","Розы")])` содержит «Розы» и «(rose)»; два пака — оба.
- `hint_lines(None|""|"pack", …)` → `[]`; пресет без паков → `[]`; `("romantic", {"romantic": [("rose","Розы")]})` → одна
  строка с «Чувства и интриги», «Розы», `ai-dm --new --campaign rose --preset romantic`; два пака → две строки.
- `pack_hints(root, "rose")` → без `rose` (пустой список выброшен); `pack_hints(root, "mini")` → `rose` на месте.
- `choose_preset` simple с `hints`: пункт romantic содержит «Розы», пункты heroic/«Как в паке» — нет; нумерация прежняя
  (существующие параметризованные тесты в `test_ui_cli.py` с `hints=None` зелёные); TUI (monkeypatch `tui.pick`) получает
  `names` с подсказкой.
- Сквозные: `--new --campaign mini --hero arn --preset romantic` → в выводе строка с `--campaign rose --preset romantic`
  **после** строки «Мир:»; `--campaign rose --preset romantic` → строки нет; `--campaign mini --preset heroic` (пресет без
  пака) и `--preset pack` → нет; интерактив `["1", "<номер romantic>", "/quit"]` → в меню «Розы», в заметках команда;
  `["1", "1", "/quit"]` («Как в паке») → строки нет; `--hero arn` без `--preset` и `--hero-describe` → нигде нет «подходит»
  (В6а); `--replay … --preset romantic` после сыгранного мира → «Повтор идёт», строки «подходит» нет; битый сосед
  (`campaigns_dir/broken/campaign.yaml` = `: :`) → старт `mini` проходит, код 0.
- На реальных паках: интерактив на vale — пункт romantic содержит «dusk_academy», grim — «drunk_dragon», heroic — без
  «подходит»; `--preset romantic` на vale → строка с `--campaign dusk_academy --preset romantic`;
  `--campaign dusk_academy --preset romantic` → строки нет.
- Общее в конце: `uv run pytest -q`, `make cov` (≥94 %), `make smells` (≤206; сейчас 205), `make dead`, `uv run ruff check
  src tests`; mutmut по списку выше.

## Риски / на что обратить внимание
- **Смена тона по умолчанию трёх паков** (таблица выше) — следствие В1б; у drunk_dragon и dusk_academy теряются notes и часть
  осей, что в груминге не называлось → Q1/Q2. Живые миры (29a049dc, 00000001, ee8aa926) не меняются.
- **`--replay` старых журналов новых миров**: мир, созданный из vale/drunk_dragon/dusk_academy без `--preset` до П37, при
  повторе получит другой `system[1]` (тон) → «Расхождение с журналом». В `tests/fixtures` и `tests/golden` таких журналов нет
  (replay-тесты строят мир в самом тесте). Миры с `--preset X` или `--preset pack` воспроизводятся как раньше.
- **Мок-бюджеты**: тон уходит в `system[1]` целиком (`master/prompt.py:226 world_block`) — у vale блок вырастет на голос
  heroic (~100 токенов). `test_stage4_memory` на `make_bundle` (не пак) — не задет; CLI-мок-тесты без лимита окна. Кэш
  Gemini: схемы инструментов не меняются, только содержимое system[1] новых миров.
- **Пикер**: у `rose`-подобных подсказок пункты меню станут 150+ символов — в simple переносятся (`WIDTH=80`), в TUI `Static`
  переносится сам; проверить глазами в чек-листе (на `--mock`).
- **Несколько паков на пресет** нельзя запретить для чужих/импортных паков (индекс — из манифестов) → Q3; каталожные паки
  держит тест данных.
- **smells 205/206**: три помощника в cli.py и один в presets.py — короткие, без ветвлений сверх `if`; в `prepare` только
  3 строки. При превышении — упрощать, лимит не поднимать без согласия.
- **Пересечения с К0-фикс**: cli.py, `campaign/presets.py`, `campaign/*.yaml` К0-фикс не трогает; К0-фикс-б правит
  `campaigns/*/npcs.yaml` и `heroes/*.yaml` — П37 правит только `campaign.yaml` тех же каталогов (конфликта файлов нет,
  коммитить свои пути). Тесты К0-фикса (`test_game_controllers`, `test_tui_layout`, `test_master_rules`, llm, reports) с
  тестами П37 (`test_cli_preset`, `test_ui_cli`, `test_vale_pack`, `test_dragon_pack`, `test_presets`, новые) не пересекаются.
  Поэтому П37 можно стартовать и сразу после К0-фикс-а, не дожидаясь данных К0-фикс-б.
- `game/starter.py:58` грузит vale для `new_world` старых путей (`preset_choices`) — тон там тоже станет heroic; тесты
  этапов 2–3 на тон vale не завязаны (grep), kaban-doeba сверит полным прогоном.

## Открытые вопросы
- **Q1 dusk_academy: horror «нет» → «умеренно» и потеря notes («без пошлости», «ночной народ — соседи») при romantic.**
  (а) **рекомендация** — принять как есть (решение В1б; лимиты пака сохраняются, romance уже принят); (б) смягчить
  данными без кода: «романтика медленная, без пошлости» → `soft_limits` dusk_academy (переживает `apply_preset`), «ночной
  народ и оборотни — соседи» — проверить/дописать в `world.md`; horror остаётся «умеренно»; (в) расширить `apply_preset`
  (notes = голос пресета + notes пака) — меняет решение Б0-П2 для всех пресетов и `--preset`, тесты
  `test_apply_voice_replaces_pack_notes`/`test_preset_voice_is_inside_system_1`, промпт длиннее — архитектурное, не
  рекомендую в П37.
- **Q2 drunk_dragon: потеря трёх строк стиля игры и сюжетного mood при grim; language «грубо», horror «сильно».**
  (а) **рекомендация** — принять: строки стиля («маленькими кусками», «мета-игрово:») — предпочтения игрока, а не пака;
  живой мир 29a049dc их уже несёт в сейве; новые миры дракона — тестовые; (б) те же строки → `soft_limits` дракона
  (натяжка по смыслу «лимитов», но данные, не код); (в) не ставить `preset` у drunk_dragon — тогда нет подсказки
  grim → drunk_dragon (противоречит В7).
- **Q3 Несколько паков на один пресет** (импорт пользователя может объявить `preset: romantic`): (а) **рекомендация** —
  показывать все, по `id`, через запятую в пункте и по строке на пак в заметках; тест данных держит «≤ 1 на пресет» только для
  каталожных паков; (б) показывать только первый по `id`; (в) при нескольких не показывать ничего.
- **Q4 Строка «Мир:» при пресете из манифеста** (игрок выбрал «Как в паке» на vale — тон heroic применён молча, видно
  только в хронике): (а) **рекомендация** — в П37 ничего (поведение Б0-П2, не предмет BACKLOG 37; `test_no_preset_has_no_preset_note`
  без правок); (б) дописывать «пресет heroic (из пака)» в «Мир:» — ещё ветка в `prepare`, инверсия этого теста.

## Решения проектировщика (2026-10-12)
- Q1 (б): dusk_academy — смягчить данными: «без пошлости» → soft_limits, лор «ночной народ — соседи» → world.md; код
  apply_preset не трогать.
- Q2 (б): drunk_dragon — строки стиля игры (и mood, если ложится) → soft_limits пака; пара grim → drunk_dragon остаётся.
- Q3 (а) показывать все паки по id; Q4 (а) строку «Мир:» в П37 не менять.
