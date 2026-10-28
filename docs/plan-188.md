# Шаг 188. Установка одной командой

BACKLOG 188. План пишет папа-кабан; ниже — решения проектировщика из груминга.

## Решения

Груминг 2026-10-28 (окна оркестратора, варианты и рекомендации свинопаса):

1. Режим разработчика: если в текущей папке есть `./saves`, игра берёт его; иначе — пользовательская папка.
2. Пользовательская папка миров — `~/.local/share/ai-dm` (XDG_DATA_HOME, порядок переменных как у конфига
   в `config/user.py`); папки по правилам Mac и Windows — в 189.
3. `journal/` и `issues/` игрока остаются внутри мира, как у разработчика.
4. Паки поставляются в установке, читаются оттуда, без копирования в пользовательскую папку; переносить ли
   `campaigns/` — решает папа. Готовый мир «с первой минуты» — 191.
5. Состав: `vale`; «+ ещё пара миров, о которых подумаем позже» (ответ вне вариантов — механизм поставки
   должен позволять добавить паки).
6. `--import` — игроку сразу: импорт пишет в пользовательскую папку, игра читает их вместе с поставленными.
7. `.env` ищется и в папке конфига (`~/.config/ai-dm`).
8. Звук — команда установки с extra: `uv tool install "ai-dm[audio] @ git+https://github.com/PapaHusserl/ai-dm"`.
9. Приёмка: локальный тест без CI (сборка wheel во временном каталоге, чистая установка, `--new` на mock без ключа)
   + проектировщик один раз ставит с GitHub на своём Mac после push.
10. README — одна строка про установку в 188; README для игрока — 193.

11. Аппрув плана 2026-10-28: развилки Р1–Р3 — по рекомендациям папы (три независимые проверки; подпапки
    `saves/` и `campaigns/`; полные пути в текстах игроку). Р4 — архитектор (принято в плане).

Ранее (2026-10-26, из ROADMAP R12, пересказ через оркестратора): `saves/` в репо остаётся режимом
разработчика, живые миры не мигрируют.

## План (папа-кабан, 2026-10-28)

Контур: вне msa; режим: встроить. Входы: решения 1–10 выше, отчёт свинопаса и аудит свекрови (scratchpad сессии).

**Задача:** установленная `uv tool install` игра запускается и играет: паки едут в пакете, сейвы/импорт/`.env`
игрока — в пользовательских папках, разработчик в репо ничего не замечает.

**Правило:** было `parser.add_argument("--saves", default="saves")` (`ui/cli.py:138`) и
`dotenv_path = Path(".env")` (`ui/cli.py:479`), `campaigns_dir = CAMPAIGNS_DIR` (`ui/cli.py:471`) →
станет: «рядом есть — берём, нет — пользовательская папка»: `saves = Path("saves") if Path("saves").is_dir()
else data_dir(env) / "saves"`; `campaigns = Path("campaigns") if Path("campaigns").is_dir() else data_dir(env) /
"campaigns"`; `dotenv = Path(".env") if Path(".env").is_file() else config_dir(env) / ".env"`.
Было `CAMPAIGNS_DIR = Path(__file__).resolve().parents[3] / "campaigns"` — единственный корень паков
(`campaign/loader.py:38`) → станет два корня: `SHIPPED_DIR = Path(__file__).resolve().parents[1] / "campaigns"`
(поставка, внутри пакета) + локальный корень (`campaigns_dir` в `Setup`); чтение — `pack_dir(campaigns_dir, id)`:
локальный, иначе поставленный; запись (`--import`) — только локальный.

**Поведение:** меняется — (1) без `./saves` в текущей папке миры идут в `~/.local/share/ai-dm/saves`;
(2) без `./.env` ключ ищется в `~/.config/ai-dm/.env`; (3) без `./campaigns` `--import` кладёт пак в
`~/.local/share/ai-dm/campaigns/<id>`; (4) пак `vale` всегда виден — из поставки; (5) `make install-check`
дополнительно прогоняет `--new` на mock без ключа в установленном колесе. В репо (есть `./saves`, `./campaigns`,
`./.env`) — как раньше.

**Вне репо:** GitHub PapaHusserl/ai-dm — после push проектировщик один раз ставит с GitHub на своём Mac
(решение 9); CI нет и не добавляется.

### Модули, файлы, функции

Проверено grep-ом; «новая» — нет в коде.

- `src/ai_dm/campaign/loader.py` — `CAMPAIGNS_DIR` (остаётся: корень паков репо, только разработка и тесты —
  `prompt_budget`, `GameApp` по умолчанию, киты тестов), `SHIPPED_DIR` (новая константа, `parents[1] / "campaigns"`),
  `pack_dir(campaigns_dir, campaign_id)` (новая, ~5 строк).
- `src/ai_dm/campaigns/vale/` (новая папка в пакете) — `git mv campaigns/vale src/ai_dm/campaigns/vale` (7 файлов, 28K,
  `du -sh`). Проверено пробой в scratchpad: копия репо с vale в `src/ai_dm/campaigns/`, `uv build --wheel` без правок
  `pyproject.toml` — в wheel 7 файлов `ai_dm/campaigns/vale/*` (`unzip -l | grep -c`). Так уже лежат `art/data`,
  `audio/data`, `srd/data` (`ART_DIR = Path(__file__).parent / "data"` — `art/catalog.py:7`). Механизм для «ещё пары
  миров» (решение 5): один `git mv` пака в `src/ai_dm/campaigns/` — он попадает в wheel и в подсказки пресетов.
- `src/ai_dm/game/starter.py:10` — `VALE_DIR = CAMPAIGNS_DIR / "vale"` → `SHIPPED_DIR / "vale"`.
- `src/ai_dm/campaign/presets.py` — `preset_packs` (без изменений), `all_preset_packs(campaigns_dir)` (новая):
  объединение `preset_packs(SHIPPED_DIR)` и `preset_packs(campaigns_dir)`, локальный пак с тем же id перекрывает.
- `src/ai_dm/config/user.py` — `config_dir` (образец), `data_dir(env)` (новая: `AI_DM_DATA_DIR` → `XDG_DATA_HOME/ai-dm`
  → `~/.local/share/ai-dm`, тот же порядок), `local_or_user(local, user)` (новая, 1 строка: `local if local.exists()
  else user`).
- `src/ai_dm/ui/cli.py` — `make_parser` (`--saves default=None`, текст help — Р3), `main` (три умолчания через
  `local_or_user`; `args.saves = …` в стиле `args.new = True` из `import_pack`), `import_text` (проверка «уже есть» —
  `pack_dir`, чтобы нельзя было импортировать под id поставленного пака), `import_refusal` (текст «ляжет в campaigns/» —
  Р3), `campaign_registry` (`pack_dir` вместо `Path(campaigns_dir) / campaign_id`), `pack_hints` (`all_preset_packs`).
- `src/ai_dm/game/app.py` — `merge_pack` (`pack_dir`; текст «Пака X нет в …» — Р3), `GameApp.load` (`pack_dir`).
- `src/ai_dm/llm/factory.py` — `make_adapter`: текст `MissingKey` «(переменная окружения или .env)» — Р3.
- `devtools/check_install.py` — `run` (параметр `input`), `main`: после `--help` — `--new --hero arn --simple --mock
  <tmp>/one.yaml` с `stdin="Здравствуйте\n"`, чистым `env` (`PATH`, `HOME=<tmp>/home`), cwd `<tmp>/home` (без `./saves`);
  затем проверка, что в `<tmp>/home/.local/share/ai-dm/saves` ровно один мир. Mock-сценарий пишет сам (`steps: - text:`,
  как `ui_kit.write_script`), от `tests/fixtures` не зависит. Mock без ключа — факт: `test_ui_cli.py` гоняет `env={}`.
- `pyproject.toml` — не меняется (проба выше); `[tool.mutmut] also_copy` с `campaigns/` остаётся (dev-паки).
- `README.md` — «Установка»: строка `uv tool install "ai-dm[audio] @ git+https://github.com/PapaHusserl/ai-dm"` (решения 8,
  10); три строки, которые становятся ложными, поправить: «`.env` в папке, откуда запускаете» (+ `~/.config/ai-dm/.env`),
  «`--saves DIR` (по умолчанию `./saves`)» (+ пользовательская папка), «пак из `campaigns/<id>`» (+ поставка).
  Полный README игрока — 193.
- `docs/ARCHITECTURE.md:234` (дерево: `campaigns/` → плюс `src/ai_dm/campaigns/` — поставка) и `:645` (`game.pack_import`:
  корень — локальный `campaigns_dir`).
- Тесты, которые строят путь к `vale` от корня репо (ломаются переносом, правятся на `SHIPPED_DIR`/`VALE_DIR` из
  `starter`): `tests/unit/campaign/campaign_kit.py:24`, `tests/unit/ui/test_ui_cli.py:1258`,
  `tests/unit/ui/test_cli_preset.py:68`, `tests/unit/art/test_art_catalog.py:139`, `tests/unit/campaign/test_pack_tags.py:19`,
  `tests/unit/campaign/test_preset_packs.py:128` (`catalog_index` ждёт vale в `ROOT / "campaigns"` → брать из
  `all_preset_packs(CATALOG)`). Пути к `drunk_dragon`/`dusk_academy`/`inn_test` (39/11/1 файлов) не трогаются.
- `tests/unit/ui/test_ui_cli.py:106` `test_default_saves_dir_is_saves_in_current_dir` — по новому правилу без `./saves`
  мир уйдёт в папку данных: тест создаёт `tmp_path / "saves"` заранее (режим разработчика) + новый тест без неё.
- `tests/unit/devtools/test_check_install.py:17` — подмена `run` должна принимать `input` (`lambda cmd, env=None, **kw`).

### Партия — одна

Объём: src ≈ 40–60 строк (ожидание, не проверено), `git mv` 7 файлов, тесты ≈ 8 файлов правок путей + ≈ 12 новых
тестов, README 4 строки, ARCHITECTURE 2 строки. Делить незачем: половина без второй не даёт играбельной установки.
Если ревью захочет меньше — граница: П1 «паки в поставке» (шаги 1–3, 7; после неё установленная игра запускается,
но пишет в `./saves`), П2 «пользовательские папки» (4–6, 8).

1. `git mv campaigns/vale src/ai_dm/campaigns/vale`; `loader.py`: `SHIPPED_DIR`, `pack_dir`; `starter.py`: `VALE_DIR`.
   Выход: `uv run pytest tests/unit/campaign tests/unit/game -q` зелёный после правки путей в тестах из списка.
2. `cli.py`: `campaign_registry`, `import_text` → `pack_dir`; `app.py`: `merge_pack`, `GameApp.load` → `pack_dir`.
   Выход: тесты `tests/unit/ui/test_cli_import.py`, `test_cli_migration.py`, `tests/unit/game/test_game_merge_pack.py`
   зелёные; новый тест: `--import --campaign vale` в пустой локальный корень → «Пак vale уже есть», код 1.
3. `presets.py`: `all_preset_packs`; `cli.py:pack_hints` → она. Выход: `test_preset_packs.py` (catalog + новый тест:
   локальный пак с id поставленного перекрывает, пустой локальный корень даёт паки поставки).
4. `config/user.py`: `data_dir`, `local_or_user` + тесты по образцу `test_config_dir_*`
   (`tests/unit/config/test_user_config.py:37-51`).
5. `cli.py:make_parser` (`--saves default=None`, help), `cli.py:main` — три умолчания. Тесты в `test_ui_cli.py`:
   chdir в tmp без `./saves`, `env={"XDG_DATA_HOME": …}` → мир в `<xdg>/ai-dm/saves`; с `./saves` — как раньше;
   `dotenv_path=None` + `.env` в `<XDG_CONFIG_HOME>/ai-dm/.env` → ключа хватает (образец `test_key_from_dotenv_is_enough:70`);
   `--import` без `./campaigns` → пак в `<xdg>/ai-dm/campaigns/<id>` (образец `test_cli_import.py:run`, `campaigns_dir=None`).
6. Тексты по Р3: `factory.py:make_adapter`, `cli.py:import_refusal`, `app.py:merge_pack`, help `--saves`.
7. `devtools/check_install.py` + `test_check_install.py` (2 новых теста: команда `--new … --mock` есть; `HOME` указывает
   в tmp). Выход: `make install-check` проходит (сеть нужна для зависимостей) — прогон кабаном-доебой.
8. README (4 строки), ARCHITECTURE (2 строки). Перед коммитом: `make cov` ≥ 94 %, `make smells` ≤ 200 (сейчас ровно
   200 — `make smells` 2026-10-28; новые функции по 1–5 строк, `main` +3 строки — риск, см. ниже), `make dead`,
   `make mutate FUNCS="ai_dm.campaign.loader:pack_dir ai_dm.campaign.presets:all_preset_packs ai_dm.config.user:data_dir
   ai_dm.config.user:local_or_user ai_dm.ui.cli:main ai_dm.ui.cli:make_parser ai_dm.ui.cli:import_text
   ai_dm.ui.cli:import_refusal ai_dm.ui.cli:campaign_registry ai_dm.ui.cli:pack_hints ai_dm.game.app:merge_pack
   ai_dm.game.app:GameApp.load ai_dm.llm.factory:make_adapter" TESTS="tests/unit/ui tests/unit/campaign tests/unit/game
   tests/unit/config tests/unit/llm"` (функции `pack_dir`, `all_preset_packs`, `data_dir`, `local_or_user` — новые,
   остальные найдены grep-ом: `cli.py:103, 212, 467, 497, 515, 662`; `app.py:57, 458`; `factory.py:9`).

### Тестовые сценарии (кабану-доебе)

- Wheel из чистой копии, `uv tool install` во временный `UV_TOOL_DIR`, `ai-dm --new --hero arn --simple --mock one.yaml`,
  `HOME=<tmp>`, cwd без `./saves`, без ключей → код 0, в выводе «Мир: vale-…», в `<tmp>/.local/share/ai-dm/saves` один
  мир с `journal/`. Это и есть `make install-check` — «ожидание, не проверено» до реализации; сам запуск с mock без ключа
  проверен тестами `test_ui_cli.py` (env={}).
- Та же команда из папки с `./saves` → мир в `./saves`, папка данных не создаётся (проверено сегодня:
  `test_default_saves_dir_is_saves_in_current_dir` — после правки теста).
- `--saves DIR` явно → DIR, независимо от `./saves` (есть: `test_new_world_goes_to_the_saves_dir:99`).
- Ключ только в `<XDG_CONFIG_HOME>/ai-dm/.env`, `./.env` нет → игра стартует (новый тест, шаг 5); `./.env` есть — он
  главнее (ожидание).
- `--import FILE --campaign x` без `./campaigns` → `<data>/campaigns/x`; `--campaign vale` → отказ «уже есть» (новые).
- Мир `drunk_dragon` в репо: `--world <id>` из корня репо — догрузка пака из `./campaigns` как раньше
  (`test_game_merge_pack.py`, `test_cli_migration.py:142` — `pack_dir == CAMPAIGNS / "drunk_dragon"`).
- Подсказки пресетов при `--new`: vale из поставки + dev-паки из `./campaigns` (`test_preset_packs.py` catalog).
- `uv run pytest -q` из корня репо — зелёный; из другой cwd тесты не обязаны проходить (и сейчас читают `README.md`,
  `Makefile` от корня — `test_prompt_budget.py`).
- Руками (проектировщик, решение 9): после push `uv tool install "ai-dm[audio] @ git+https://github.com/PapaHusserl/ai-dm"`,
  `ai-dm --new` из домашней папки с ключом в `~/.config/ai-dm/.env` — мир в `~/.local/share/ai-dm/saves`.

### Развилки и риски

- **Р1. Правило «рядом есть — берём» на три пути или только на `saves`.** Решение 1 названо для `./saves`; для
  `./campaigns` и `./.env` правило то же (каждый путь проверяется сам по себе) — (1) три независимые проверки,
  (2) один триггер `./saves` на всё, (3) только `saves`, остальное всегда в пользовательских папках. Рекомендую (1): свежий
  клон без `saves/` (в git его нет — `git ls-files saves` пусто, `/saves/` в `.gitignore`) при (2) не увидит dev-паков
  из `./campaigns`; при (3) `--import` у разработчика ляжет в `~/.local/share`, а тесты и `prompt_budget` ждут
  `./campaigns`. Видимо игроку: где лежит файл после `--import`.
- **Р2. Структура папки данных.** Решение 2 говорит «папка миров — `~/.local/share/ai-dm`»; `--import` туда же (решение 6)
  — нужны подпапки: (1) `~/.local/share/ai-dm/saves/<мир>` и `…/campaigns/<id>` (зеркало репо), (2) миры прямо в
  `~/.local/share/ai-dm/<мир>`, паки в `…/campaigns/`. Рекомендую (1): одна форма у разработчика и игрока, `--saves`
  показывает ту же структуру, id мира не спутается с `campaigns`.
- **Р3. Тексты, которые видит игрок** (пять строк): help `--saves` — «папка сейвов (по умолчанию ./saves, если есть,
  иначе ~/.local/share/ai-dm/saves)»; `MissingKey` (`factory.py:16`) — «нет ключа X (переменная окружения или
  <полный путь .env, который смотрели>)»; `import_refusal` (`cli.py:507`) — «под этим id пак ляжет в <campaigns_dir>»
  (нужен параметр или текст без пути); `merge_pack` (`app.py:64`) — «Пака X нет ни в <campaigns_dir>, ни в поставке:
  игра идёт без догрузки». Альтернатива — оставить тексты как есть (тогда «.env» без пути вводит в заблуждение: игрок
  не узнает про `~/.config/ai-dm/.env`). Рекомендую назвать пути.
- **Р4. `CAMPAIGNS_DIR` (`parents[3]`) остаётся как корень паков репо** — у установленной игры это несуществующий путь,
  но им пользуются только `GameApp` по умолчанию (15 конструкторов в тестах без `campaigns_dir`), `prompt_budget`
  (dev) и 6 тестов. Альтернатива — убрать и заменить на `Path("campaigns")` относительно cwd (плюс 6 правок тестов,
  относительный путь зависит от cwd). Рекомендую оставить с комментарием «только разработка».
- Риск smells: сейчас ровно 200 = порог. Правки — короткие функции; `main` +3 строки не меняет его сложность
  (присваивания). Если `make smells` даст 201 — вынести три умолчания из `main` в `default_paths(args, env)` (новая), не
  трогать allowlist.
- Риск: `uv tool install` из GitHub собирает wheel из checkout через hatchling; проба подтвердила только локальный
  `uv build`. Ручная установка проектировщиком (решение 9) закрывает.
- Риск принятый (свинопас): у игрока случайно есть `./saves` → игра возьмёт его. Help `--saves` (Р3) это называет.
- hatchling: последний релиз 1.31.0 (2026-07-08, piwheels/Debian tracker; pepy показывал 1.29.0 от 2026-02-23 —
  устаревший снимок); живой. Новых зависимостей нет (`platformdirs` не нужен — решение 2).

### Умолчания (внутреннее)

- Имена: `SHIPPED_DIR`, `pack_dir`, `all_preset_packs`, `data_dir`, `local_or_user`, `AI_DM_DATA_DIR`. При Р4 = оставить —
  `CAMPAIGNS_DIR` не переименовывается.
- `Setup` не меняется: `campaigns_dir` там — локальный (записываемый) корень; поставка — константа loader.
- `pack_dir` возвращает путь, не проверяя существование поставленного (ошибку «нет каталога пака» даёт `load_pack`, как
  сейчас).
- При Р1 = (1): проверки `is_dir()`/`is_file()` относительно cwd на момент `main`, как сейчас `Path(".env")`.
- При Р2 = (1): `data_dir(env) / "saves"`, `data_dir(env) / "campaigns"`; папки создаются теми же местами, что и сейчас
  (`save_slot`, `stage_dir` — `mkdtemp` требует существующего `dir`: перед `stage_dir` — `mkdir(parents=True,
  exist_ok=True)` локального корня в `import_pack`, 1 строка).
- `check_install.py` пишет mock-сценарий сам; `test_check_install.py` остаётся без сети (подмена `run`).
- `.gitignore` не меняется (`campaigns/*/.import/`, `campaigns/test/` — про корень репо).

### Открытые вопросы

1. Р1 — правило «рядом есть — берём» на три пути? (`ui/cli.py:471, 479`, `make_parser:138`) варианты: (1) три независимые
   проверки (2) один триггер `./saves` (3) только `saves`; рекомендую (1) — свежий клон и `--import` разработчика;
   разблокирует: шаги 5, 7, тексты Р3; решает: проектировщик. Блокирующий.
2. Р2 — подпапки `saves/` и `campaigns/` внутри `~/.local/share/ai-dm`? варианты: (1) да (2) миры прямо в корне;
   рекомендую (1); разблокирует: `data_dir`-умолчания, `check_install`; решает: проектировщик.
3. Р3 — назвать пути в четырёх текстах игроку? варианты: (1) да (2) оставить; рекомендую (1); разблокирует: шаг 6;
   решает: проектировщик.
4. Р4 — `CAMPAIGNS_DIR` остаётся корнем паков репо для разработки? рекомендую да; решает: архитектор (принято в плане,
   если нет возражений).

## Правки по ревью

- Отклонения кабана от плана (приняты мамой): `SHIPPED_DIR` объявлена в `presets.py` (цикл импорта `loader` ↔
  `presets`), реэкспорт из `loader`; `import_refusal` получил параметр `campaigns_dir`; проверка «один мир» в
  `check_install` — через `python -c`; локальные `pack_dir` → `folder`. Старые миры vale догружают пак из поставки
  (замечено свекровью).
- Мама, круг 1: `devtools/prompt_budget.py` → `pack_dir(CAMPAIGNS_DIR, pack)` (иначе `prompt_budget vale` ломался);
  `check_install.run` — `text=True` явно; `merge_pack` — без переменной `where`; пустые строки в `loader.py`. Исправил
  кабан.
- Свекровь: `pyproject.toml` — временная правка `make mutate`, восстановлена им самим; решений за проектировщика нет.
- Мутанты: в диффе выживших нет, 19 segfault; старые строки — BACKLOG 213. Доеба по `mutmut show`: 12 в `make_parser`
  (тексты help) — шум; `main_32`, `main_45` — эквивалентны на macOS (регистр ФС); `main_57` — убит существующим тестом;
  `main_36`, `main_49`, `make_adapter_25`, `make_adapter_26` — дописаны 3 теста. Повтор mutmut — нет (решение Влада
  2026-10-28: «только cov»): мутанты не подтверждены.
- Мама, круг 2: замечания закрыты; пробел `text=True, cwd=cwd` в `check_install.run` — исправил кабан.
- Свекровь, круг 2: по шагу чисто. Абзац t1279 в теле BACKLOG 212 (вне шага) — Влад 2026-10-28: «оставить в 212»,
  коммит отдельно от 188.

## Смета (кабан-тесть, режим 1)

**Что проверено:** план шага 188 (одна партия), прогон цепочки. Новых платных сервисов нет: `uv tool install`, GitHub
(публичный), hatchling — бесплатно; зависимостей не добавляется. Постоянных $/мес шаг не создаёт.
Основа сметы — «Итог» шага 209 (`docs/plan-209.md:115`), масштаб ×2–2,5 для kaban/doeba: в 209 src не менялся и
`make cov`/`make mutate` не гонялись, здесь src ≈ 50 строк, 13 функций в mutmut, `make install-check` с сетью.

| Статья | Сейчас ($/мес) | Допущения | Дешевле | Экономия | Что теряем |
|---|---|---|---|---|---|
| платные сервисы | 0 | нет новых | — | — | — |
| прогон цепочки (разово) | ≈ 9–13 $ за шаг | ×2–2,5 к 209 у исполнителя | оркестратору давать ссылки, а не пересказ; `make mutate` фоном | ≈ 1–1,5 $ | ничего |
| папа-кабан на fable | по ценам Opus | проба с 2026-10-08 | — (решение пользователя, проба) | — | — |

| Партия | Время |
|---|---|
| груминг + план + смета (прошло) | ≈ 30–40 мин, интервал |
| П1 (шаги 1–8) кабан | 50–80 мин |
| doeba: `make cov` ≈ 15 мин + `make mutate` 13 функций, 5 каталогов + install-check | 40–60 мин |
| ревью мамы ‖ аудит свекрови + коммит | 15–25 мин |
| итого | ≈ 2,5–3,5 ч |

| Роль | Модель | Токены | $ (тариф metrics.py 2026-10-25) |
|---|---|---|---|
| papa-kaban (прошло) | fable → по Opus | 0,3–0,5 M (id в agents.md не сверял — интервал по 209) | 0,4–0,7 |
| svinopas (прошло) | opus | 0,5–0,8 M (интервал по 209) | 0,4–0,7 |
| kaban | sonnet | 1,4–1,8 M | 0,7–1,0 |
| kaban-doeba (+ разбор выживших) | sonnet | 0,3–0,6 M | 0,25–0,5 |
| mama-kaban | opus | 0,2–0,4 M | 0,4–0,8 |
| kaban-svekrov | opus | 0,25–0,45 M | 0,6–1,1 |
| оркестратор | opus | 7–10 M | 2,8–4,0 |
| kaban-test (итог) | opus | 0,1 M | 0,2 |
| Декарт | opus | 2 вызова (1 партия + сводный), ≤ 400 KB выжимок ≈ 0,1–0,2 M | 0,3–0,5 |
| **итого** | | ≈ 10–14 M | ≈ 6–9,5 $ |

Модели (`grep -H '^model:' ~/.claude/agents/<роль>.md`): kaban, kaban-doeba — sonnet; mama-kaban, kaban-svekrov,
kaban-test, svinopas — opus; papa-kaban — fable. Свой запуск (режим 1) не включён.
Дорогая статья — оркестратор (≈ 45 %); ревью и аудит не трогаем, модель оркестратору не понижаем.
**Вердикт:** ок по бабкам.

## Итог

Закрыт BACKLOG 188; заведён BACKLOG 213 (выжившие мутанты на старых строках). Результаты: cov 98,14 %, 22300 passed
(1 флак `test_tui_create`, отдельно зелёный); smells 200; ruff и dead — чисто; мутанты не подтверждены (в диффе 19 segfault,
доеба дописала 3 теста, повтор mutmut Влад снял).

**Источник токенов:** metrics.py по `~/.claude/projects/-Users-vladislavahtamov-projects-ai-dm/fdb613e0-572f-44eb-89c0-c386d344021c.jsonl`;
**цены:** тариф metrics.py от 2026-10-25 (https://platform.claude.com/docs/en/about-claude/pricing), с сайтом не сверял (не проверено);
fable — по тарифу metrics.py.

| Партия | Смета | Факт |
|---|---|---|
| груминг + план + смета | ≈ 30–40 мин | ≈ 15 мин работы (свинопас 2,8, свекровь 0,8, папа и тесть по сегментам); интервал 20:58–07:12, в т. ч. ночной простой |
| П1 кабан | 50–80 мин | 19,8 мин работы (основной сегмент 18,3); быстрее сметы — правки короткие |
| доеба: cov + mutate + install-check | 40–60 мин | 23,8 + 11,4 (segfault) мин доебы, cov 11,5 мин; mutmut фоном |
| ревью мамы ‖ аудит свекрови + коммит | 15–25 мин | 3 круга по 0,1–1,3 мин; интервал 08:22–10:38, в т. ч. простой (ожидание Влада, вне шага) |
| итого | ≈ 2,5–3,5 ч | ≈ 75 мин работы субагентов; сессия 825 мин, в т. ч. ночь |

| Роль | Модель | Токены | $ |
|---|---|---|---|
| papa-kaban (план + архитектор) | fable 5.1 | 1 459 001 | 2,11 |
| svinopas (груминг) | opus 5.5 | ≈ 1,97 M на роль, из них запуск шага a8949… | 0,63 |
| kaban | sonnet 5.5 | ≈ 5,78 M на роль, из них запуск шага a7475… | 1,84 |
| kaban-doeba (2 запуска) | sonnet 5.5 | 1 472 683 | 0,82 |
| mama-kaban | opus 5.5 | ≈ 0,49 M на роль, из них запуск шага a03ab… | 0,80 |
| kaban-svekrov (2 запуска) | opus 5.5 | 825 379 | 1,24 |
| оркестратор | opus 5.5 | 15 629 332 | 6,65 — на момент подсчёта 10:44 UTC |
| kaban-test (смета + итог) | opus 5.5 | 169 573 | 0,37 — на момент подсчёта 10:44 UTC |
| Декарт | — | не звали | 0 |
| **вне шага:** t1279 — svinopas a6edb…, kaban-мини ab1d8…, mama a080c… | opus / sonnet / opus | в итогах ролей выше | 0,82 + 0,17 + 0,16 = 1,15 |

**Итого:** смета ≈ 10–14 M, 6–9,5 $, 2,5–3,5 ч → факт 27,8 M, 15,61 $ за сессию (шаг ≈ 14,46 $, вне шага 1,15 $),
≈ 75 мин работы. Выше сметы: оркестратор 15,6 M против 7–10 M (длинная сессия через ночь, контекст до 209 K) и папа на
fable 2,11 $ против 0,4–0,7 $; время — ниже сметы.
Разбор — кабан Декарта.
