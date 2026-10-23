# 16. Хвосты P1 этапа 5
status: dropped
priority: low
updated: 2026-10-23

(ревью мамы-кабана, docs/plan-stage5.md)
- AD1, выжившие мутанты в старых строках: indent=/ensure_ascii= в model_dump_json/move_slot, rmtree(ignore_errors), пустые строки call_lines, uuid-суффикс write_slot, combat_ended в close_scene_if_needed, run_round _65, дефолты TurnResult.__init__/TurnContext.__init__, end_chapter _1,_2,_4–_7, world_verdict _8; mutmut по PlaySession.play/render_step после последних правок не перегонялся.
- ✅ (Д1) Ctrl+C и любая ошибка при подготовке мира в режиме TUI: строки старта печатаются (flush_notes + raise в cli.play).
- ✅ (P3, снято в груминге Д1) Порядок вывода при ask_hero в режиме TUI: подсказка выбора героя идёт в терминал раньше накопленных строк (уйдёт с HeroPicker, P3).
- ✅ (Д1, тест снимает состояние в момент жёсткого выхода при закрытом гейте: tests/unit/ui/tui/test_tui_turn.py) P2: второй Ctrl+C во время хода — поток хода не прерывается, «ход не применён» проверяется только отсутствием сейва.
- ✅ (P3, снято в груминге Д1) P2: карта боя (~80 кол.) в правой панели 46 кол. прокручивается по горизонтали.
- ✅ (Д1: сужение по файлу невозможно, снят лишний display) P2: сузить общие имена `display`, `border_title` в vulture_allowlist.
- (итог Д1 (протокол E1–E3): E1/E2 без segfault; E2b TESTS=tests/unit/ui — 4 segfault на status_line; E3 forkserver — ChildProcessError -6 в stats (_scproxy macOS под подозрением); гипотеза Textual не подтвердилась; потрачено ~85 мин сверх потолка 60. Правило: TESTS по узким файлам функции, segfault-мутантов перепроверять прогоном с тестами других файлов) P2: mutmut на ui.screen даёт segfault на 21 мутанте (status_line, gains_lines, reply_blocks) — разобраться (fork + потоки Textual?).
- P3: выбор героя (HeroPickerApp) и создание героя (HeroCreateApp) — отдельные App до основного; перенести внутрь основного — не Д1 (решение В1а груминга Д1, 2026-10-10): отдельный пункт, место в очереди — при пересмотре Т-4. **Отменено 2026-10-15 (решение проектировщика):** отдельные App выбора/создания героя остаются, переносить не будем.
- P6 ✅ (Б2б): заставка-титул показана и в `PickerApp`, и на экране создания героя (`HeroCreateApp`).
- ✅ (Д1: сужение по файлу невозможно, три имени оставлены с комментариями) P3: vulture_allowlist — глобальные имена on_click, closing и др. (способ P1); сузить вместе с display/border_title.
- P5: `mutate` game.commands — 84 выживших мутанта в старом коде (cmd_sheet 26, equipment_text 15, cmd_quit 10, cmd_model 9, ac_text 8, прочее): тексты и форматирование, добить тестами.
- (итог Д1 (протокол E1–E3): E1/E2 без segfault; E2b TESTS=tests/unit/ui — 4 segfault на status_line; E3 forkserver — ChildProcessError -6 в stats (_scproxy macOS под подозрением); гипотеза Textual не подтвердилась; потрачено ~85 мин сверх потолка 60. Правило: TESTS по узким файлам функции, segfault-мутантов перепроверять прогоном с тестами других файлов) P5: segfault (36) и timeout (2) mutmut в ui.screen/ui.session — сбои прогона, не выжившие мутанты.
- ✅ (Д1, тесты simple.run с opening) P6: mutmut `ui.simple.run` — 3 выживших на старых строках (передача `opening` в PlaySession, пропуск `take_opening()`); нужен тест на режим с `opening` в простом режиме.

- Партия 0 кастомных предметов (старые выжившие мутанты): pick_valuables — ничья по цене между разными id; settle_ground —
  тексты логов, owner_ref in heroes, очистка disarmed/disarm_used; disarm take(..., quality) у героя; load_slot — FileNotFoundError/ValueError.
- Кастом. предметы, партия А: старые выжившие мутанты — do_rob (rng=None, аргументы remove_item, статус «applied»), do_capture (статус), give_item (старые ветки ~49), цены m0006 (~32; test_migration_v6 не входит в выборку из-за game_kit); make smells плавает 208–212 из-за нестабильных дублей Qlty (common/names, commands/roll_pipeline).
- Кастом. предметы, партия Б (docs/plan-custom-items.md): простой режим — предмет виден дважды (строка лога
  «Получен предмет: …» и заметка «Получено: …»); вне победы «Получено: Опыт: +N, …» — неуклюже (проектировщик: не горит; не чинить, решение 2026-10-10).
  Старые выжившие мутанты master.prompt (state_data: секреты/nudge/recent_turns; divine_data, sheet_data, combat_data,
  memory_block, candidates, find_role_cfg, draft_plan, dump). ✅ (Д1) Описание кастомного режется до 120 с «…» (master.prompt.clip).
- Торговля Т0 (docs/plan-trade.md): старые выжившие мутанты — migrate (тексты исключений, copy vs deepcopy,
  `version = 1`), check_pack_refs (26, ветка event.cause/owners); нет теста ui/cli.py::prepare (npc_trade); тест
  test_game_app_load_shows_the_migration_warning падает при изолированном запуске tests/unit/persistence (game_kit в sys.path).
- Кастом. предметы, партия В (docs/plan-custom-items.md): старые выжившие мутанты — gold_loot (тексты
  message/reason/signal_to_master), finish_combat (слова статусов down/fled в defeated, ended_by_master, `xp +=`),
  strip_weapon (kind="flag"), settle_ground (disarm_used). Нет тестов на монстра без weapon_id в реальном контенте (волка
  в реестре нет) и сценария «rob → возврат ключа» на моке рассказчика. Ревью п.7 (add_stack дублирует стек inventory)
  и п.8 (gear по ссылке в LastCombat) — не правились.

- Торговля Т3 (мутанты, старые строки — тексты сообщений): handlers/trade.py x_trade_mutmut_29–31 («больше нельзя торговать»),
  trade_pick.py x_merchant_problem_mutmut_8–9 («во время боя»), 30–31 («не меньше 1»); state_data — выжившие на старых строках
  (тесты state_data вне набора TESTS).

- Этап 6а P0 (2026-10-07): старые выжившие мутанты game/turn.py retry/take_boundary/failed, game/boundary.py call_world
  (ветки журнала, лимит дня, hero_dead, hint); make mutate MOD не ловит методы классов — ✅ AD1: `make mutate FUNCS=модуль:Класс.метод`;
  ✅ (2026-10-08) дубль common.py↔rules/names.py убран — make smells стабильно 210 (запаса нет).
- Архив мутантов (хранить результаты mutmut между партиями): не делать, пока модуль не трогают (решение AD1).
- Б0 (аудит docs/plan-b0.md, 2026-10-08): вынести `fighter_choices` в kit-модуль; старые выжившие мутанты —
  ветки world в apply, `world_verdict` в required_tool, deepcopy в tool_defs, `ui.cli x_prepare__mutmut_432`;
  make smells 202/202 из-за `propose_background` (13 параметров) и `CreationContext.__init__` (9) — разгрузить в Б1, он их трогает;
  пробел v6/v7 в части E ARCHITECTURE.
  Закрыто в Б1а (2026-10-08): `propose_background` разгружена (`HeroCreateDeps`, smells 201); `CreationContext` обобщён по задаче
  (`BackgroundTask`/`SheetTask`); описание предыстории показывается в `/sheet` и в промпте мастера (`hooks_lines`, `state_data`).
  Не закрыто: smell на `TurnContext.__init__` (старый код, не Б1) — дефолты `TurnContext.__init__` остаются в хвосте выше.
- Б1а: TUI создания героя (`HeroCreateApp`) — отдельным App до основного, внутрь основного App и заставка до выбора — Б2
  (вместе с `HeroPickerApp`, п. выше); режим `hero_background` и `propose_background` оставлены под пошаговый режим Б2
  (в vulture_allowlist с пометкой «Б2»; режим `hero_background` теперь защищён тестами и обработчиками по режимам);
  means/opportunity в `HeroPreset` пака — п. 34.
- Б1а: фабрики `SHEET_FIELDS` (`scalar_field`, `list_field`, `number_field`, `background_field`, `species_field`,
  `feat_skills_field`) возвращают замыкания — mutmut их плохо мутирует: добивать тестами на поведение `edit_sheet`, не по
  замыканиям. Ручная правка `opportunity` заменяет весь список; правка по id — Б1б.
- Б1б ✅: блок «Б1а → снять в Б1б» в vulture_allowlist снят (остался `propose_background`/`BackgroundTask` — «Б2»).
  Хвост «description в /sheet/промпт» закрыт Б1а. Добавить: создание героя внутрь основного App (сейчас отдельный `HeroCreateApp`,
  Б2); модель, сменённая в меню 2.2 при создании, не пишется в `meta/models.json` до первой смены в игре (при смене на другого провайдера world/summarizer остаются на исходном — решение В-5, допустимо); живой прогон Б1б —
  `docs/plan-b1.md` (пользователь).
  Хвосты Б1б после аудита: (а) выжившие мутанты `cli.make_game_adapter` mutmut_15, `cli.prepare` mutmut_568 (opening только без
  `--mock`); (б) защита `HeroSession.submit` от исключений кроме `TurnFailed` (сейчас падает `HeroCreateApp`); (в) ✅ закрыто в Б3 (В1а): запрет `campaign/loader.py` на пак
  без пресетов героя снят, ветка `choose_hero` для пака без героев достижима (Б2 В11а отменено решением Б3 В1а: пак без
  пресета допустим, старт — только героем на лету/пошагово); (г) smells 202/202, запаса для Б2 нет.
- Б2а (2026-10-09): `SMELLS_MAX` поднят 202 → 205 (решение проектировщика, Q1): база main 203 + файловый флаг «High total
  complexity» на новом `game/hero_steps.py` + запас. Цель — вернуть лимит вниз (≤ 203), если Б2 закроется без запаса.
  «HeroPickerApp/создание внутрь основного App» — явно Д1, не Б2. Хвост (б) «защита `HeroSession.submit` от исключений» — не Б2.
  Спеллы в контенте скудные (волшебник: 1 заговор и 5 заклинаний 1 круга; жрец: 0 и 2), поэтому шаги заговоров и заклинаний
  берут `min(лимит класса, доступно в контенте)`; при пополнении списка заклинаний шаги потребуют лимит класса сами.
  **Решение проектировщика (2026-10-09): пополнение заклинаний волшебника/жреца/следопыта до лимитов классов 1 ур. —
  отдельная партия** (после Б2, место в очереди R4 определить при груминге). Б2а остаётся с `min(...)`.

- К0а (2026-10-11), старые выжившие мутанты: spell_candidates/spell_errors (default= у max), resource_maxes/add_amount (max_add), choice_errors/short_rest/rest (тексты), castable_spells (has_slot, forbidden), cast_mark (лог), conclude (invisible/hidden, OUTCOME_WORDS), transfer_mark_options (continue→break), GameApp.__init__/load (boundary), build_hero (motive/deity/birth_s), feature_groups/sheet_data, concentration_line. Не мутированы: sheet_text.spell_ids, GameApp.save_current (ветка pending_level). Commit с чертой (feat) не покрыт — общих черт в SRD-данных нет. pending_level проверяется только у первого героя — пересмотреть в Ж0.
- К0б (2026-10-11): выжившие мутанты — 22 текст исключений (норма), 3 эквивалентных в `level_for_xp`, 3 старых в `roll_hazard` (аргументы `damage_log_text`: крит/бонус лога урона опасности не проверяются). `sys.path.insert` — +1 файл `tests/unit/rules/test_classes_1_20.py` (долг 70 файлов, решение В-2а).

## Закрыто

Снят решением проектировщика 2026-10-23 (перебор R11, docs/ROADMAP.md «Переборы роадмапа»): всё живое закрыто Д1/Б1–Б3/AD1
или отменено (отдельные App выбора/создания героя остаются — 2026-10-15); остаток — старые выжившие мутанты (дубли
BACKLOG 149/157 по `cmd_sheet`, `state_data`; правило «при касании функции») и хвост (б) `HeroSession.submit`, шага не
получил. Пополнение заклинаний до лимитов классов — К3 (ROADMAP, хвост-«д»).
