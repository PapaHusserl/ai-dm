# План партии Му: «тематическая музыка и эмбиент» — Му-а (выбор темы, no-op, мок-плеер, пользовательский конфиг) / Му-б (плеер, эмбиент, треки, живой прогон)

Автор: папа-кабан, 2026-10-10. Статус: **предложение на аппрув** (решения проектировщика В1–В12 + «эмбиент», «smells», «платформы»
из `docs/plan-mu.md`, раздел «Решения проектировщика (2026-10-10)», обязательны и приняты за основу). Основа:
`docs/plan-mu.md` (ТЗ свинопаса, аудит свекрови, решения), `docs/research/music-research.md`, BACKLOG 33, `docs/plan-roadmap-r4.md` #5,
`docs/plan-b3.md` (форма), HANDOFF («Инструменты качества», «Правила экономии»). Код на main 9b6f56b: `art/{pick,catalog}.py` + `art/data/index.yaml`
(образец «выбор по ситуации» и таблица в данных), `ui/screen.py` (`picture_state`), `ui/session.py` (`Step`, `turn_events`), `ui/tui/app.py`
(`show_step`, `show_picture`, `finish_turn`), `ui/tui/__init__.py` (`run_tui`), `ui/simple.py`, `ui/cli.py` (`make_parser`, `main`, `play`,
`run_tui`, `prepare`, `import_pack`, `play_report` — три вызова `load_settings()` без пути), `config/app.py` (`load_settings(toml_text, path)`,
модели `extra="forbid"`), `config/settings.py` (`deep_merge`), `app_defaults.toml`, `game/app.py` (`GameApp`, `handle`, `models.json`),
`game/commands.py` (`HELP`, `COMMANDS`), `state/world.py` (`Tone`, `Location.tags/parent_id`), `pyproject.toml` (нет `optional-dependencies`),
`Makefile` (`SMELLS_MAX = 205`, `install-check`, `linux-check` с `uv sync --locked`), `devtools/check_install.py`, `tests/unit/test_architecture.py`
(сторожа слоёв: `ENGINE_PACKAGES` = core, config, content, srd, state, rules, combat; textual — только из `ui/tui`), `tests/unit/art/*`,
`tests/unit/ui/{ui_kit.py,test_ui_picture_state.py,test_commands_both_modes.py}`, `tests/unit/ui/tui/conftest.py` (Pilot, `tui.submit`).

**Критерий Му (груминг «Готово» + решения):** Му-а — тесты маппинга/приоритетов/гистерезиса/возврата после боя/no-op/мок-плеера/режимов тишины/
пользовательского конфига зелёные; `/music` отвечает в обоих режимах; TUI без extra пишет одну строку «Звук выключен: …» и молчит. Му-б — реальный
плеер на miniaudio за тем же интерфейсом, два слоя (музыка + эмбиент) с кроссфейдом; 8 тем + эмбиенты CC0/CC-BY в пакете ≤ 40 МБ с ATTRIBUTION,
утверждённые пользователем на слух; `make install-check` с extra и без; живой прогон В11. Общее: `make smells` ≤ лимита (лимит поднимается на факт
партии — решение), `make dead` чисто, mutmut по новым функциям (**без `ui.tui.*` и без реального плеера** — риск segfault Д1). **Сейв v8 без
миграции**, протокол/промпт/`WINDOW` мока не трогаются (В1в, В2а): цена хода не меняется.

**Принято из решений:** уровня «сцена» нет, приоритет бой > локация > тон мира > тишина (В1в); локация: id → свои теги → теги родителей вверх по
`parent_id`; теги дописать в паки данными (В2а); пользовательский конфиг через `load_settings(path)`, `/music` сохраняет громкость/вкл/эмбиент
туда, переживает перезапуск (В3б); тон: `horror == "сильно"` → мрачная, иначе «исследование» (В4а); 8 тем — бой, таверна, город/деревня,
природа, подземелье, мрачная, исследование, романтика, по 1 треку (В5); эмбиент — второй слой (решение); агент ищет кандидатов только CC0/CC-BY,
пользователь слушает и утверждает; OGG, внутри пакета, всего ≤ 40 МБ (В6); звук **только в TUI** — простой режим, создание героя, пикер, replay,
import, mock, тесты — тишина (В7); одна команда `/music`: состояние, on/off, 0–100, эмбиент вкл/выкл, в HELP (В8); смена темы не чаще раза в 20 с,
бой — сразу (вход и выход), после боя — тема текущей локации, кроссфейд 2 с, позицию не помнить (В9); одна строка «Звук выключен: причина»,
дальше тишина, без репорта (В10); живой прогон полный (В11); деление Му-а / Му-б (В12б); платформы macOS + Linux, extra `audio`, нет
библиотеки/устройства → тишина; smells — поднять лимит на факт.

**Не входит:** поле `mood` в ответе мастера, `tags` в `location_create`, любые правки `protocol/`, `master/`, промптов (В1в, В2а); звук в простом
режиме, на экране создания героя и в пикере (В7); звуковые эффекты (удар, монета); своя папка музыки пользователя (ресёрч разд. 2); запоминание
позиции трека (В9б); генерация треков; Windows; изменение сейва; тема заставки.

## A0. Поправки фактов (проверено по коду, PyPI и `make smells`, 2026-10-10)
1. **`make smells` = 204 при лимите 205** (запас 1). Новый пакет `audio/` добавит 0–3 smells даже при дисциплине Б1/Б2 (≤ 4 именованных
   параметра + `*`, ≤ 5 return, диспетчер таблицей) — по решению проектировщика лимит поднимается **на факт партии при ревью** (Q9).
2. **miniaudio 1.71 (MIT) на PyPI имеет колёса `cp312` для `macosx_11_0_arm64`, `macosx_10_13_x86_64`, `manylinux_2_24/2_28_x86_64`,
   `musllinux_1_2`** — риск 6 груминга («сборка из исходников») на целевых платформах снят. API (проверено по sdist): `PlaybackDevice(output_format,
   nchannels, sample_rate, buffersize_msec=200).start(generator)` — генератор получает `send(framecount)` и отдаёт `array.array`/bytes;
   `stream_file(filename, output_format, nchannels, sample_rate, frames_to_read, seek_frame)` — стриминг чанками (память малая);
   `decode_file(...)` — весь файл в память (3-минутный трек ≈ 32 МБ int16-стерео); `DecodeError`/`MiniaudioError`. Микширования и громкости в
   библиотеке нет — делаются своим генератором (ресёрч разд. 3).
3. **В stdlib нет TOML-писателя** (`tomllib` только читает). «`/music` сохраняет в пользовательский конфиг» нельзя сделать перезаписью
   редактируемого руками `config.toml` без потери комментариев и порядка — отсюда Q2 (отдельный файл `audio.toml`, который пишет только игра).
4. **`load_settings(toml_text, path)`** уже мерджит два слоя поверх дефолтов (строка, затем файл — файл сильнее; тест `test_path_overrides_text`).
   Для двух пользовательских файлов хватает вызова `load_settings(toml_text=<config.toml>, path=<audio.toml>)` без правки сигнатуры.
5. **`GameApp.handle` обрабатывает все `/команды` одинаково в обоих режимах** (`COMMANDS`), а `test_commands_both_modes` требует: каждая команда
   `HELP` отвечает и в простом режиме, и в TUI. Значит `/music` живёт в `game/commands.py`, а контроллер звука — атрибут `GameApp` (`app.audio`),
   который cli подменяет на настоящий только в TUI; по умолчанию — `SilentSound` с причиной (Q4).
6. **Точка применения состояния в TUI — `AiDmApp.show_step`** (вызывается на старте из `on_mount` и после каждого хода/команды из `finish_turn`):
   там уже `show_picture(step.events, refresh)` по `picture_state(self.game)`. Звук встаёт рядом тем же приёмом: `sound_state(self.game)` →
   `self.game.audio.update(state)`. Ход идёт в thread-worker, команды тоже (`session.submit` в потоке), `show_step` — в главном потоке, колбэк
   miniaudio — в его потоке: контроллеру и плееру нужен `threading.Lock` (риск 5).
7. **Нет тегов у локаций:** `vale` (3 локации) и `campaigns/test` (4) — без тегов вовсе; `drunk_dragon` — 9 без тегов (`dead_pine_gorge`,
   `deep_shaft`, `olbrecht_manor`, `varen_manor`, `watch_tower_outpost`, `white_winds_ledge`, `wolf_teeth_pass`, + 2 служебных), но все с
   `parent_id`, и обход родителей (В2а) даёт `city`/`iron_ridge`/`heather_wastes`. Правка данными нужна только там, где родитель даёт неверную
   тему (`deep_shaft` → `шахта`, иначе «горы» → природа), и в `vale`/`test`. `campaigns/test/` в git **не отслеживается** (`??` в статусе) — его
   не трогаем (Q13).
8. **`Tone.horror` — Literal `"", "нет", "умеренно", "сильно"`**, `Tone.romance` — `"", "нет", "намёки", "чувственно", "откровенно"`; id пресета
   в мир не пишется. Для В4а достаточно `horror`. Для темы «романтика» (В5) сигнала **нет** ни в тоне (не решено), ни в сцене (В1в) — Q1.
9. **`run_tui` (`ui/tui/__init__.py`) — единственное место, где создаётся `AiDmApp`** для игры; `cli.run_tui(args, app, opening, notes, secrets)`
   знает `args` (флаг `--mute`, `--replay`, `--mock`) и `notes.lines` (строки старта → лента). Реальный плеер создаётся **только здесь**;
   `PickerApp`/`HeroCreateApp` его не получают (В7).
10. **`uv.lock` + `linux-check` с `uv sync --locked`:** добавление `[project.optional-dependencies] audio` требует `uv lock` и коммита lock-файла;
    Docker Linux без устройства — тесты только с подменённым модулем `miniaudio`.
11. **mutmut копирует `src/` в `mutants/`** (`source_paths = ["src/"]`) — после Му-б каждая копия тащит ~30–40 МБ аудио; терпимо, но FUNCS/TESTS
    задавать узко (правило 1 экономии).
12. HANDOFF «Порядок R4: Му … v7» — цифра устарела (код v8), поправить вместе с партией (документ, не решение). Тестов на main — 11 963.

## A. Архитектура

### A1. Пакет `ai_dm/audio/` (новый, уровень `art`: ниже `game`/`ui`, не импортирует `game`, `ui`, `llm`, `master`, `protocol`)
- `audio/catalog.py` — по образцу `art/catalog.py`: `AUDIO_DIR = Path(__file__).parent / "data"`; `AudioIndex(BaseModel, extra="forbid")`:
  `themes: dict[str, Theme]` (`Theme(music: str, ambient: str = "")` — имена файлов в `data/`), `location_tags: dict[str, str]` (тег → id темы,
  порядок тегов локации — приоритет, как у рисунков), `locations: dict[str, str]` (точный id локации → тема), `tone: ToneThemes(horror_strong:
  str = "dark", default: str = "explore")`, `combat: str = "combat"`. `load_audio(folder=AUDIO_DIR)` (`lru_cache`; `folder` — для тестов на
  временных каталогах, как `ART_DIR`), `theme_for_tags(index, tags) -> str | None` (первый тег с темой), `theme_files(index, folder, theme) ->
  (Path | None, Path | None)` (музыка, эмбиент; отсутствующий файл → `None`, без исключений — В10).
- `audio/select.py` — чистая функция по образцу `pick_picture`: `SoundState(frozen dataclass)`: `location_id: str | None`, `tags: tuple[str, ...]`
  (**уже с тегами родителей**, свои первыми), `in_combat: bool`, `horror: str`, `romance: str`; `pick_theme(index, state) -> str | None`:
  `in_combat` → `index.combat`; `locations[location_id]` → тема; `theme_for_tags(tags)` → тема; `horror == "сильно"` → `tone.horror_strong`;
  иначе `tone.default` (В4а: «исследование» — тема по умолчанию, тишина только если тема без файла). Романтика — Q1.
- `audio/control.py`:
  - `next_switch(current, wanted, last_switch_s, now_s, min_s) -> bool` — чистая: `wanted != current` и (вход/выход боя — `wanted == COMBAT or
    current == COMBAT` — сразу, иначе `now_s - last_switch_s >= min_s`). Гистерезис считается от последней смены; подавленная смена
    применяется на следующем шаге (Q7).
  - `SoundController(player, index, cfg, prefs, *, now=time.monotonic)`: состояние `enabled`, `volume` (0–100), `ambient` (bool), `theme`,
    `last_switch_s`, `reason` (строка причины тишины или `None`), `lock`. `update(state)`: `theme = pick_theme(...)`; `next_switch(...)` →
    `apply(theme)`: `music, ambient = theme_files(...)`; `player.set_layer("music", music, cfg.crossfade_s)`; `player.set_layer("ambient", ambient
    if self.ambient else None, cfg.crossfade_s)`; `last_switch_s = now()`. `command(arg) -> list[str]` — диспетчер таблицей: `""` → строки
    состояния («Звук: вкл, громкость 60, эмбиент: вкл», «Тема: таверна (tavern.ogg) + crowd.ogg» / «Звук выключен: причина»); `on|off` →
    `enabled`, `off` → `player.set_layer(.., None)` обоих слоёв, `on` → `apply(theme)` немедленно; `0–100` → `volume`, `player.set_volume(gain)`;
    `ambient on|off` → слой эмбиента; иначе — строка «Использование: /music [on|off|0–100|ambient on|off]». Каждое изменение → `prefs.save(enabled,
    volume, ambient)`. `stop()` → `player.stop()`. Громкость: `gain = (volume / 100) ** 2` (перцептивная шкала; техническое умолчание).
  - `SilentSound(reason)`: `update` — no-op; `command("")` → `[f"Звук выключен: {reason}"]`; любой другой аргумент → та же строка (Q4 — в простом
    режиме причина «звук только в TUI»); `stop()` — no-op. Один класс для простого режима, replay/mock и «нет библиотеки» (различается причиной).
  - `make_sound(cfg, prefs, index, *, mute, silent_reason=None) -> (controller, line | None)`: `silent_reason` → `SilentSound`, строка — по Q8;
    `not cfg.enabled and not prefs.enabled` → контроллер на `NullPlayer` без строки (выключено пользователем — не ошибка); иначе лениво
    `from ai_dm.audio.miniaudio_player import MiniaudioPlayer` (`ImportError` → `NullPlayer`, причина «библиотека miniaudio не установлена
    (uv sync --extra audio)»), `player.start()` → строка ошибки (`MiniaudioError`/`OSError` — нет устройства, SSH) → `NullPlayer`, причина.
    Строка в ленту ровно одна: «Звук выключен: {причина}» (В10). `mute=True` (флаг `--mute`) → `enabled=False` на сессию без записи в prefs (Q5).
- `audio/player.py` — `Player(Protocol)`: `start() -> str | None` (причина отказа), `set_layer(layer: str, path: Path | None, fade_s: float)`,
  `set_volume(gain: float)`, `stop()`. `NullPlayer` — всё no-op, `start()` → `None`. Тестовый `FakePlayer` (пишет список команд) — в kit тестов,
  не в продукте.
- `audio/miniaudio_player.py` (**Му-б**, единственный модуль с `import miniaudio`, импорт — внутри `start()`/методов, по образцу
  `test_cli_imports_tui_only_lazily`): `Layer` (текущий поток + уходящий поток с рампой гейна; `stream_file(path, SIGNED16, 2, 44100,
  frames_to_read=n)` c `send(n)`; `StopIteration` → новый генератор с начала = луп; позиция не хранится — В9); чистые функции
  `gain_ramp(start, end, steps)`, `mix_chunk(chunks_with_gains, n) -> array("h")` (сумма с клиппингом ±32767); `MiniaudioPlayer(cfg)`: `start()` —
  `PlaybackDevice(buffersize_msec=cfg.buffer_ms)` + `device.start(self.generator())`; `generator()` — бесконечный, под `lock` читает слои и
  микширует `music×gain + ambient×gain×ambient_gain`; `set_layer` — под `lock` переводит текущий поток в «уходящий» (fade-out за `fade_s`), новый —
  fade-in; `stop()` — `device.stop(); device.close()`. Все ошибки декодирования/устройства → строка в `start()`/тихий пропуск слоя (без
  исключений в колбэке — колбэк miniaudio исключения не переживает). Чистый Python на `array`: ~2048 сэмплов × ≤ 4 потока на колбэк ≈ 3–5 %
  ядра — приемлемо (риск 7); `numpy`/`audioop` не добавляем (`audioop` удалён в 3.13).
- `audio/data/index.yaml` — таблица тем (техническое умолчание на аппрув, Q13): `themes`: `combat` (без эмбиента), `tavern` (+`crowd`), `town`
  (+`street`), `nature` (+`wind_birds`), `dungeon` (+`drips`), `dark` (+`night`), `explore` (без эмбиента или `wind_birds`), `romance` (без
  эмбиента); `location_tags`: таверна, трактир → tavern; город, деревня, квартал, магазин, власть, гильдия, храм, порт → town; равнина, горы,
  предгорья, болото, лес, долина, дорога, ущелье → nature; руины, гробница, подвал, логово, логово врага, крепость, шахта, пещера, вход → dungeon;
  святилище, кладбище, заброшено → dark; `locations`: пусто; `tone`: `horror_strong: dark`, `default: explore`. `audio/data/ATTRIBUTION.md`
  (Му-б): таблица «файл · тема · автор · название · лицензия (ссылка) · страница источника · дата проверки · правки (обрезка, конвертация в OGG)».
- Сторожа (`test_architecture.py`, +): `audio` не импортирует `game/ui/llm/master/protocol`; `miniaudio` импортируется только в
  `audio/miniaudio_player.py` и только внутри функций (как textual).

### A2. Конфиг: `[audio]`, пользовательский конфиг (В3б)
- `config/app.py`: `AudioConfig(BaseModel, extra="forbid")`: `enabled: bool = True`, `volume: int = Field(60, ge=0, le=100)`, `ambient: bool = True`,
  `ambient_percent: int = Field(50, ge=0, le=100)`, `crossfade_s: float = Field(2.0, ge=0)`, `min_switch_s: float = Field(20.0, ge=0)`,
  `buffer_ms: int = Field(200, ge=20)`; `AppConfig.audio: AudioConfig = AudioConfig()`. `app_defaults.toml`: секция `[audio]` с комментариями.
- `config/user.py` (новый, слой `config` — без `time`/`random`): `config_dir(env) -> Path`: `env["AI_DM_CONFIG_DIR"]` (тесты, явный выбор) →
  `env["XDG_CONFIG_HOME"]/ai-dm` → `~/.config/ai-dm`; `CONFIG_FILE = "config.toml"` (правит пользователь руками: любые секции, включая `[audio]`
  как дефолты), `AUDIO_FILE = "audio.toml"` (пишет **только игра**: ровно `[audio]` с `enabled/volume/ambient`; поверх `config.toml`);
  `load_user_settings(env) -> Settings`: `load_settings(toml_text=<config.toml, если есть>, path=<audio.toml, если есть>)`; битый TOML/валидация →
  `ValueError` с именем файла (cli печатает «Ошибка: …», код 1 — как сейчас при любой ошибке в `main`); `audio_prefs_text(enabled, volume,
  ambient) -> str` (3 строки TOML, детерминированно); `write_audio_prefs(path, ...)` — `mkdir(parents=True)`, запись во временный файл + `replace`
  (атомарно, как сейвы). `AudioPrefs(path)` с `save(...)` — объект для контроллера (в тестах подменяется записью в `tmp_path`). Q2/Q3.
- `ui/cli.py`: три `load_settings()` (`prepare`, `import_pack`, `play_report`) → `load_user_settings(setup.env)` (Q3). `config_dir(env)` без
  `AI_DM_CONFIG_DIR`/`XDG_CONFIG_HOME` падает на `Path.home()` — а он читает настоящий `os.environ`, не переданный `env`. Поэтому kit-хелпер `cli()`
  в тестах **по умолчанию** добавляет в `env` ключ `AI_DM_CONFIG_DIR = <tmp_path>` (явно переданный `env` дополняется, не заменяется), и ни один
  cli-тест не читает домашний каталог разработчика. Сторож: `load_user_settings({"AI_DM_CONFIG_DIR": <пустой tmp>})` даёт дефолты и ничего не
  создаёт на диске.

### A3. Слой `game`: атрибут `GameApp.audio`, команда `/music`
- `game/app.py`: `self.audio = SilentSound(SIMPLE_REASON)` в `__init__` (без нового параметра — у `__init__` уже 17 параметров; cli присваивает
  `app.audio = controller` после создания, как `app.ledger.session_lines.extend(...)`). `SIMPLE_REASON = "звук только в TUI"` (Q4).
- `game/commands.py`: `HELP["music"] = "[on|off|0–100|ambient on|off] музыка и эмбиент (только в TUI)"`; `cmd_music(app, arg) = app.reply(
  app.audio.command(arg))`; `COMMANDS["music"]`. Команда вне хода (начинается с `/` → `is_game_line` ложь → без refresh), `MODAL_TITLES` не
  трогаем (ответ — строками в ленту, как `/model narrator x`).

### A4. Слой `ui`: состояние, TUI, cli
- `ui/screen.py`: `location_tag_chain(world, location) -> tuple[str, ...]` — теги локации, затем родителя и дальше вверх по `parent_id`
  (`world.locations.get`), защита от цикла множеством пройденных id; `sound_state(app) -> SoundState` рядом с `picture_state`: локация героя
  (`hero_of(app.bundle).location_id`), `in_combat = app.bundle.session.active_combat is not None`, `tone.horror`, `tone.romance`.
- `ui/tui/app.py`: в `show_step` после `show_picture`: `self.game.audio.update(sound_state(self.game))` (каждый шаг: и после команд — `/music on`
  должен зазвучать сразу; `/load` меняет локацию). Больше в TUI ничего: ни виджета, ни строк (строка «Звук выключен…» приходит через `startup`
  → лента). Остановка — в `ui/tui/__init__.run_tui`: `try: app.run() … finally: game.audio.stop()` (покрывает исключения после первого кадра;
  при `abandon`/`os._exit` поток плеера умирает с процессом).
- `ui/cli.py`: `--mute` (`action="store_true"`, help «без музыки в этом запуске»); в `cli.run_tui(args, app, opening, notes, secrets)` перед
  `tui.run_tui`: `silent = "режим --replay" if args.replay else "режим --mock" if args.mock else None`; `controller, line = make_sound(
  app.settings.app.audio, AudioPrefs(config_dir(setup.env) / AUDIO_FILE), load_audio(), mute=args.mute, silent_reason=silent)`; `app.audio =
  controller`; `line` → `notes.lines.append(line)` (В10, одна строка). В простом режиме `--mute` принимается и игнорируется (звука нет). `setup`
  нужен в `run_tui` — добавить параметром или брать `env` из `app`… — проще: `run_tui(args, app, opening, notes, setup)` (secrets = `setup.secrets`).
- README: раздел «Музыка и эмбиент» (`uv sync --extra audio` / `pip install ai-dm[audio]`, `/music`, `--mute`, где лежит конфиг, что без библиотеки
  или по SSH — тишина с одной строкой; ATTRIBUTION); ARCHITECTURE: раздел «F8. Музыка и эмбиент» (пакет `audio`, интерфейс `Player`, где создаётся,
  потоки, конфиг, файлы пользователя); BACKLOG 33 — статус; HANDOFF — статусы, расходы, «v7» → «v8».

### A5. Данные: теги паков (Му-а) и треки (Му-б, шаг «данные»)
- Му-а, теги (В2а): `campaigns/vale/locations.yaml`: `vale` → `[долина]`, `lame_goose` → `[таверна]`, `cellar` → `[подвал]`;
  `campaigns/drunk_dragon/locations.yaml`: `deep_shaft` → `[шахта]` (иначе родитель «горы» → природа); остальные без тегов получают тему родителя
  (`city` → town, `iron_ridge` → nature, `heather_wastes` → nature). Теги — свободные русские слова, `Location.tags` без схемы — миграция не нужна;
  `art/data/index.yaml` новые теги не затрагивают (у рисунков своя таблица). `campaigns/test/` не трогаем (не в git).
- Му-б, шаг «данные» (В6, до живого прогона; код ждёт треки только на прогоне):
  1. Агент (кабан или дядя-кабан, отдельная задача) собирает **кандидатов**: на каждую из 8 тем 2–3 трека, на 5 эмбиентов (толпа таверны, улица
     города, ветер/птицы, капель подземелья, ночь) 1–2 звука. Источники: OpenGameArt (фильтр CC0 / CC-BY 3.0/4.0), Incompetech (Kevin MacLeod,
     CC BY 4.0), freesound (CC0 для эмбиентов), Alexander Nakarada (CC BY 4.0) и подобные; **никаких** NC/ND/SA, Pixabay-лицензии, «royalty-free
     без указания CC». Для каждого — ссылка на страницу трека, точная лицензия со ссылкой на текст, автор, название, длительность, формат,
     размер, дата проверки страницы. Результат — таблица в `docs/plan-mu.md` (кандидаты + статус «утверждён/отклонён»).
  2. **Пользователь слушает и утверждает** по одному на тему/эмбиент (агент не слышит шов лупа и качество — риск 3 груминга). Отклонено →
     следующий кандидат.
  3. Утверждённые: скачивание оригинала; конвертация в OGG Vorbis (`ffmpeg -c:a libvorbis -q:a 3` ≈ 100–110 кбит/с; музыка 44,1 кГц стерео ≤
     3,5 МБ ≈ 4 мин; эмбиент — моно 44,1 кГц ≤ 1,5 МБ ≈ 2 мин, луп); обрезка хвостов до чистого шва (правка допустима для CC0/CC-BY, фиксируется в
     ATTRIBUTION); имена файлов = id темы/эмбиента (`tavern.ogg`, `crowd.ogg`); сумма `audio/data/*.ogg` ≤ 40 МБ (цель ≤ 32).
  4. `audio/data/ATTRIBUTION.md` + ссылка из README «Лицензия» (код — лицензия проекта, музыка — по ATTRIBUTION); проверка тестом: каждый `.ogg`
     упомянут, у каждого есть лицензия из {CC0, CC-BY} и ссылка.
  5. Один коммит «Му-б: треки» после утверждения (в историю git навсегда — до коммита пересобрать не поздно).

## B. Партии

### B1. Му-а — выбор темы, no-op и мок-плеер, `/music`, пользовательский конфиг, теги паков (без звука)

**Шаги kaban (src/docs), в порядке зависимостей:** 1. `config/app.py` `AudioConfig` + `app_defaults.toml` `[audio]`; `config/user.py` (A2).
2. `audio/{__init__,catalog,select,control,player}.py` + `audio/data/index.yaml` (A1; без `.ogg`). 3. `game/app.py` `self.audio`; `game/commands.py`
`/music` (A3). 4. `ui/screen.py` `location_tag_chain`, `sound_state`; `ui/tui/app.py` вызов `update`; `ui/tui/__init__.py` `finally: stop()`;
`ui/cli.py` `--mute`, `load_user_settings` ×3, подключение в `run_tui` (A4). 5. Теги `vale`/`drunk_dragon` (A5). 6. README, ARCHITECTURE F8,
BACKLOG 33, HANDOFF (вкл. «v7» → «v8»). `vulture_allowlist.py` — без изменений (поля `AudioConfig` читаются контроллером; если `buffer_ms` до Му-б
не читается — завести его в Му-б, а не в allowlist).

**Интерфейсы (контракт для doeba):** `ai_dm.audio.SoundState(location_id, tags, in_combat, horror, romance)`; `pick_theme(index, state) -> str | None`;
`load_audio(folder=AUDIO_DIR) -> Audio(index, folder)`; `theme_for_tags(index, tags)`; `theme_files(index, folder, theme) -> (Path|None, Path|None)`;
`next_switch(current, wanted, last_switch_s, now_s, min_s) -> bool`; `SoundController(player, index, cfg, prefs, *, now)`: `.update(state)`,
`.command(arg) -> list[str]`, `.stop()`, поля `enabled/volume/ambient/theme/reason`; `SilentSound(reason)`; `make_sound(cfg, prefs, index, *, mute,
silent_reason=None) -> (sound, line|None)`; `Player` protocol (`start/set_layer/set_volume/stop`), `NullPlayer`; `config.user`: `config_dir(env)`,
`CONFIG_FILE`, `AUDIO_FILE`, `load_user_settings(env)`, `audio_prefs_text(...)`, `write_audio_prefs(path, ...)`, `AudioPrefs(path).save(...)`;
`ui.screen.sound_state(app)`, `location_tag_chain(world, loc)`; `GameApp.audio`; `HELP["music"]`; флаг `--mute`.

**Тесты kaban-doeba (tests/**; kit `tests/unit/audio/audio_kit.py`: `FakePlayer` (список `calls`: `("layer", name, path, fade)`, `("volume", gain)`,
`("stop",)`; `start()` возвращает заданную причину или `None`), `FakeClock` (`now()` из списка/счётчика), `index(**overrides)` — `AudioIndex`
из словаря, `audio_dir(tmp_path, files)` — каталог с `index.yaml` и пустыми `*.ogg`, `state(**kw)` — `SoundState` с дефолтами, `prefs(tmp_path)`):
- `tests/unit/audio/test_audio_select.py`: бой > точный id локации > первый тег > тон; `tags=()` + `horror="сильно"` → `dark`; `horror` иное → `explore`;
  в бою с любыми тегами → `combat`; тег родителя (второй в `tags`) срабатывает, когда своих нет; порядок тегов — приоритет (`("руины", "город")` →
  dungeon); неизвестные теги пропускаются; `location_id` без записи в `locations` → теги; `romance` на выбор не влияет (при Q1а).
- `test_audio_catalog.py`: `load_audio` читает `index.yaml` пакета — у каждой из 8 тем есть `music`, все теги таблицы ссылаются на существующие темы
  (сторож данных); `theme_files` на временном каталоге: оба файла есть → пути; нет эмбиента → `(music, None)`; нет файла музыки → `(None, …)`;
  неизвестная тема → `(None, None)`; `extra="forbid"`: лишний ключ в `index.yaml` → `ValidationError`.
- `test_audio_control.py`: `next_switch` — та же тема → False; вход в бой при 0 с с последней смены → True; выход из боя → True; смена локации через
  5 с → False, через 20 с → True (граница включительно), `min_s=0` → всегда True. `SoundController` на `FakePlayer`/`FakeClock`: первый `update` →
  `set_layer("music", tavern.ogg, 2.0)` и `set_layer("ambient", crowd.ogg, 2.0)`; повтор того же состояния → без команд; локация → бой → `combat`
  сразу, эмбиент → `None`; после боя — тема **текущей** локации (сменилась в бою → новая), не прежней; подавленная смена (5 с) применяется на
  следующем `update` после 20 с; `ambient=False` → слой эмбиента всегда `None`; `enabled=False` → `update` не трогает плеер; `command("")` → строки
  с «вкл», «60», темой и файлами; `command("off")` → оба слоя `None`, `prefs.save(False, 60, True)` записан, файл `audio.toml` содержит ровно
  `[audio]` + 3 ключа; `command("on")` → `apply` сразу (без ожидания 20 с); `command("35")` → `set_volume((0.35)**2)` и save; `command("101")`/`"abc"`/
  `"ambient maybe"` → строка «Использование…», prefs не трогаются; `command("ambient off")` → слой `None`, save; `stop()` → `("stop",)`.
  `SilentSound("звук только в TUI")`: `command("")`/`command("on")`/`command("50")` → `["Звук выключен: звук только в TUI"]`, `update`/`stop` — no-op.
  `make_sound`: `silent_reason="режим --replay"` → `SilentSound`, строка по Q8; `cfg.enabled=False` → `NullPlayer`, строка `None`; `ImportError` при
  импорте `ai_dm.audio.miniaudio_player` (monkeypatch `builtins.__import__`/`sys.modules[...] = None`) → `NullPlayer` и строка «Звук выключен:
  библиотека miniaudio не установлена…»; `start()` вернул причину → строка с ней; `mute=True` → `enabled=False`, `prefs.save` не вызван.
- `tests/unit/config/test_app.py` (+): `audio` в дефолтах (`enabled True`, `volume 60`, `ambient True`, `ambient_percent 50`, `crossfade_s 2.0`,
  `min_switch_s 20`), `[audio] volume = 101` → ошибка, `bogus = 1` → ошибка. `tests/unit/config/test_user_config.py` (новый): `config_dir`:
  `AI_DM_CONFIG_DIR` > `XDG_CONFIG_HOME/ai-dm` > `~/.config/ai-dm`; `load_user_settings` без файлов → дефолты и **ничего не создано**; `config.toml`
  с `[master] recent_turns = 12` применяется; `[audio] volume = 30` в `config.toml` и `volume = 70` в `audio.toml` → 70 (audio.toml сильнее);
  битый TOML → `ValueError` с именем файла; `audio_prefs_text` детерминирован, `write_audio_prefs` создаёт каталог, атомарно перезаписывает,
  читается обратно `tomllib`.
- `tests/unit/ui/test_ui_sound_state.py` (по образцу `test_ui_picture_state.py`, `SimpleNamespace`): без боя → `in_combat False`, теги свои + родителя
  + деда в порядке «от себя вверх»; цикл `parent_id` → без зацикливания; неизвестная локация → `location_id None`, `tags ()`; бой → `in_combat True`;
  `horror`/`romance` из `world.tone`.
- `tests/unit/ui/test_commands_both_modes.py` — `/music` подхватывается из `HELP` автоматически (простой режим: «Звук выключен: звук только в TUI»;
  TUI на `AiDmApp(PlaySession(game))` без cli — та же `SilentSound`, строка в ленте). `tests/unit/game/test_commands_music.py` (новый): `cmd_music`
  зовёт `app.audio.command(arg)` c `arg.strip()`; `HELP` содержит `music`, `COMMANDS` тоже.
- `tests/unit/ui/tui/test_tui_sound.py` (новый, Pilot как `test_tui_art.py`): `game.audio = SoundController(FakePlayer(), …)` → после `on_mount`
  команды `set_layer` по локации героя (`lame_goose` → tavern по тегу из `vale`); ход в бой (`scene_app`, `start_fight`) → `combat` сразу; после
  боя → тема локации; команда `/music off` в поле ввода → слои `None`, ответ в ленте; выход из TUI (`run_tui` через `cli` с `ran_tui`-подменой или
  прямой вызов `tui.run_tui` с подменённым `App.run`) → `("stop",)` ровно один раз. **Без mutmut** (ui.tui — Д1).
- `tests/unit/ui/test_ui_cli_mode.py`/`test_ui_cli.py` (+): `--mute` в `format_help()`; `--mute --simple --mock` → код 0 (флаг принят и
  проигнорирован); `run_tui` в режиме TUI (подмена `ai_dm.ui.tui.run_tui` как в `ran_tui`) при `--replay`/`--mock` → `app.audio` — `SilentSound`
  с причиной режима; без библиотеки (monkeypatch импорт) → `notes.lines` содержит ровно одну строку «Звук выключен: …» и игра идёт; `cli(...)` с
  `env={"AI_DM_CONFIG_DIR": tmp}` и `config.toml` `[journal] max_mb = 7` → `app.settings.app.journal.max_mb == 7` (прочитан в `prepare`); то же для
  `--import` и `--replay-report` путей (`load_user_settings` во всех трёх). `ui_kit.cli()` подставляет `AI_DM_CONFIG_DIR` (A2) — проверить, что
  существующие cli-тесты с `env={}` проходят без чтения `~/.config`.
- `tests/unit/campaign/test_pack_tags.py` (новый): для `vale` и `drunk_dragon` каждая локация пака через `location_tag_chain` + `pick_theme` даёт
  тему, отличную от `None`; `lame_goose` → tavern, `cellar` → dungeon, `deep_shaft` → dungeon, `tavern_drunken_dragon` → tavern,
  `iron_ridge_foothills_villages` → town, `wolf_teeth_pass` → nature (через родителя), `sanctuary_of_dawn` → town (храм; Q13).
- `tests/unit/test_architecture.py` (+): `audio` не импортирует `game/ui/llm/master/protocol`; `miniaudio` импортируется только в
  `audio/miniaudio_player.py` и не на верхнем уровне модуля; `ai_dm.audio` импортируется без `miniaudio` в `sys.modules` (запуск в подпроцессе
  `python -c "import ai_dm.audio, sys; assert 'miniaudio' not in sys.modules"`).

**Критерии приёмки Му-а:** все тесты выше зелёные; `uv run ai-dm --new --mock … ` в TUI (реальный терминал пользователя или `ran_tui`-тест) показывает
одну строку «Звук выключен: библиотека miniaudio не установлена (uv sync --extra audio)» и играет как раньше; `/music` отвечает в обоих режимах;
`/music 40` в TUI создаёт `~/.config/ai-dm/audio.toml` (или `AI_DM_CONFIG_DIR`) и после перезапуска `/music` показывает 40; `make dead` чисто без
правок allowlist; `make smells` — факт зафиксирован в ревью (лимит по Q9); mutmut по FUNCS Му-а разобран.

**FUNCS Му-а (mutmut, `TESTS="tests/unit/audio tests/unit/config tests/unit/game/test_commands_music.py tests/unit/ui/test_ui_sound_state.py
tests/unit/campaign/test_pack_tags.py tests/unit/ui/test_ui_cli_mode.py tests/unit/ui/test_ui_cli.py"`):** `ai_dm.audio.select:pick_theme`,
`ai_dm.audio.catalog:theme_for_tags`, `…:theme_files`, `…:load_audio`, `ai_dm.audio.control:next_switch`, `…:SoundController.update`,
`…:SoundController.apply`, `…:SoundController.command`, `…:SoundController.set_enabled` (и прочие обработчики таблицы), `…:SilentSound.command`,
`…:make_sound`, `ai_dm.config.user:config_dir`, `…:load_user_settings`, `…:audio_prefs_text`, `…:write_audio_prefs`, `…:AudioPrefs.save`,
`ai_dm.game.commands:cmd_music`, `ai_dm.ui.screen:location_tag_chain`, `…:sound_state`, `ai_dm.ui.cli:run_tui` (новые строки), `…:make_parser`
(новые строки). Не мутировать: `ui.tui.*` (Д1), `GameApp.__init__` (одна строка).

**Оценка Му-а:** M− (код ≈ 350–450 строк + данные + доки). По факту HANDOFF: kaban ~250–300 тыс. (~25 мин), kaban-doeba ~300–350 тыс. (~1 ч с mutmut),
mama-kaban ~40–50 тыс.

### B2. Му-б — плеер miniaudio, эмбиент в звуке, extra `audio`, треки, живой прогон

**Шаги kaban:** 1. `pyproject.toml`: `[project.optional-dependencies] audio = ["miniaudio>=1.60"]`; `uv lock` (коммит `uv.lock`); README установка
`uv sync --extra audio` / `pip install "ai-dm[audio]"`. 2. `audio/miniaudio_player.py` (A1): `Layer`, `gain_ramp`, `mix_chunk`, `MiniaudioPlayer`.
3. `devtools/check_install.py`: установка `--from <wheel> "ai-dm[audio]"` и проверка `import miniaudio` рядом с `import textual` (Q10); `make
linux-check` — без изменений (fake-модуль в тестах). 4. Шаг «данные» (A5, п. 1–5) — **отдельная задача до прогона**, не блокирует код п. 1–3.
5. Тесты данных (ниже) после укладки треков. 6. ARCHITECTURE F8 (микшер, потоки), README «Музыка» (как заменить трек — файл с тем же именем в
`audio/data/`), BACKLOG 33 закрыть, HANDOFF.

**Интерфейсы:** `MiniaudioPlayer(cfg: AudioConfig)` реализует `Player`; `Layer(name)`: `.set(path, fade_s, now_frames)`, `.chunk(n) -> array|None`;
`gain_ramp(start, end, n) -> list[float]`; `mix_chunk(parts: list[tuple[array, float]], n) -> array("h")`; внутренние зависимости (`stream_file`,
`PlaybackDevice`) берутся из модуля `miniaudio` **по имени во время вызова** (`import miniaudio` внутри `start()`/`Layer.open`) — тесты подменяют
`sys.modules["miniaudio"]` на fake без нативного кода.

**Тесты kaban-doeba (kit `tests/unit/audio/fake_miniaudio.py`: модуль-подделка `SampleFormat`, `PlaybackDevice` (запоминает генератор, `pull(n)`
дёргает `send(n)`, `start/stop/close` считаются), `stream_file(path, …)` — генератор по синтетическим данным из словаря `path → (значение сэмпла,
число кадров)`, `MiniaudioError`, `DecodeError`; фикстура `fake_miniaudio(monkeypatch)` ставит его в `sys.modules`; автофикстура в
`tests/unit/audio/conftest.py` **запрещает** настоящий `miniaudio` (`sys.modules["miniaudio"] = None` по умолчанию, пока fake не включён) — чтобы
никто случайно не открыл устройство в pytest/mutmut (Д1)):
- `test_mix.py`: `mix_chunk` двух константных потоков (1000, 2000) с гейнами (1.0, 0.5) → 2000 во всех сэмплах; клиппинг: 30000 + 30000 → 32767,
  −30000 − 30000 → −32768; пустой список → нули длины `n`; короткий чанк (конец файла) дополняется нулями; `gain_ramp(0, 1, 4)` → монотонно,
  последний = 1.0, `n=0` → `[]`.
- `test_player.py` (на fake): `start()` → `None`, устройство открыто с `buffer_ms` из cfg; `set_layer("music", a.ogg, 2.0)` → первый `pull`
  даёт нарастающие значения (fade-in за 2 с при 44100 → ~88200 кадров), после рампы — ровно значение потока × gain; `set_layer("music", b.ogg, 2.0)`
  в середине → смесь уходящего (убывает) и нового (растёт), через 2 с — только новый; `set_layer("music", None, 2.0)` → затухание до нуля, поток
  закрыт; луп: поток из 100 кадров при `pull(250)` → значения повторяются без паузы; `set_volume(0.25)` → масштаб; эмбиент × `ambient_percent`;
  `DecodeError` при открытии файла → слой пустой, исключения нет, `pull` даёт нули; `MiniaudioError` в `PlaybackDevice()` → `start()` возвращает
  строку с текстом ошибки; `stop()` → `device.stop()` + `close()` один раз; `set_layer` после `stop()` — no-op. Потокобезопасность: `set_layer`
  из другого потока во время `pull` в цикле — без исключений (простой стресс на 200 итераций).
- `test_make_sound_real.py`: `make_sound` с fake-модулем создаёт `MiniaudioPlayer`, строка `None`; fake, у которого `PlaybackDevice` бросает
  («No backend») → `NullPlayer`, строка «Звук выключен: No backend».
- `tests/unit/audio/test_audio_data.py` (после шага «данные»): у каждой темы файл `music` существует, у эмбиентов — тоже; сумма размеров `*.ogg` ≤
  40 МБ; каждый `.ogg` — OGG (сигнатура `OggS`); `ATTRIBUTION.md` упоминает каждый файл, у каждой строки лицензия из {CC0, CC-BY} и `http`-ссылка;
  лишних файлов без атрибуции нет.
- `tests/unit/devtools/test_check_install.py` (есть ли? если да — +): команда установки содержит `ai-dm[audio]` и проверку `import miniaudio`.
- `tests/unit/test_architecture.py`: сторож «miniaudio только в `audio/miniaudio_player.py`, лениво» уже в Му-а; `uv.lock` содержит `miniaudio` как
  optional (простой grep-тест по `pyproject` — `audio` в `optional-dependencies`).

**Критерии приёмки Му-б:** тесты выше зелёные; `make install-check` проходит с extra (и `import miniaudio` в установленном окружении); `make
linux-check` зелёный (без устройства); данные ≤ 40 МБ, ATTRIBUTION полон, пользователь утвердил каждый трек; живой прогон (ниже) без багов или с
багами, записанными в `docs/plan-mu.md` и BACKLOG.

**FUNCS Му-б (`TESTS="tests/unit/audio"`; все тесты с fake-модулем, настоящего miniaudio в процессе нет):** `ai_dm.audio.miniaudio_player:mix_chunk`,
`…:gain_ramp`, `…:Layer.set`, `…:Layer.chunk`, `…:Layer.open`, `…:MiniaudioPlayer.start`, `…:MiniaudioPlayer.set_layer`,
`…:MiniaudioPlayer.set_volume`, `…:MiniaudioPlayer.generator`, `…:MiniaudioPlayer.stop`, `ai_dm.audio.control:make_sound` (ветка реального
плеера). Перед mutmut убедиться, что автофикстура `sys.modules["miniaudio"] = None` действует и в `mutants/` (mutmut гоняет те же тесты).

**Живой прогон (пользователь, В11) → `docs/plan-mu.md`:** 0. `uv sync --extra audio`; чек-лист `checklist-mu-live.md` (не коммитить).
1. `ai-dm --world <живой мир drunk_dragon>` в TUI: при старте — тема локации (таверна → `tavern` + толпа); ленты без строки «Звук выключен». 2. Бой
→ `combat` сразу, эмбиент ушёл; после боя → тема локации (если локация сменилась в бою — новая). 3. Смена локации → смена темы не раньше 20 с от
прошлой смены, кроссфейд слышен (~2 с), без щелчков. 4. `/music` → состояние; `/music 30`, `/music off`, `/music on`, `/music ambient off` →
звук реагирует, ответ в ленте; выход (`/quit`) и повторный запуск → громкость/эмбиент сохранились (`~/.config/ai-dm/audio.toml`). 5. `ai-dm --mute
--world …` → тишина, строки ошибки нет. 6. Окружение без extra (`uv sync` без `--extra audio` или `uv tool install ai-dm` без extra) → одна строка
«Звук выключен: библиотека miniaudio не установлена…», игра идёт. 7. (по возможности) запуск по SSH на Linux → одна строка про устройство, игра идёт.
8. ATTRIBUTION просмотрен. CPU плеера (Activity Monitor) — записать в mu-live.

**Оценка Му-б:** M (код ≈ 250–300 строк + install-check + данные). kaban ~200–250 тыс. (~20 мин); kaban-doeba ~250–300 тыс. (~50 мин); mama-kaban
~40 тыс.; шаг «данные» — агент ~100–150 тыс. (поиск, проверка страниц лицензий, таблица) + пользователь ~40–60 мин прослушивания (8 музыки × 2–3
кандидата + 5 эмбиентов) + конвертация/проверка ~30 тыс.

## C. Качество (обе подпартии)
- `make cov` ≥ 94 %: `audio/*` — 100 % строк (чистые функции и fake); `ui/tui/app.py` +1 строка под Pilot-тестом; `cli.run_tui` новые строки — под
  `ran_tui`-тестами. `make dead` — allowlist без изменений (поля `AudioConfig` читаются; `Player` — Protocol, как `Controller`/`ModelAdapter` уже в
  allowlist — если vulture пожалуется на `Player`, это кандидат **с согласия пользователя**; альтернатива — не объявлять Protocol, а описать в
  докстринге `NullPlayer`).
- `make smells`: факт после Му-а и после Му-б фиксируется в ревью; `SMELLS_MAX` поднимается до факта (решение проектировщика), цель — не более +3
  к 204 (Q9). Дисциплина: `command` — таблица `{"on": …, "off": …}` + разбор числа отдельной функцией; `make_sound` ≤ 5 return.
- mutmut — только FUNCS выше, фоном, разбор выживших doeba; **`ui.tui.*` и `AiDmApp` не мутируются** (Д1: fork + потоки → segfault); реальный
  `miniaudio` в pytest/mutmut запрещён автофикстурой.
- `WINDOW` мока 22070 — без изменений (промпт/протокол не тронуты); doeba подтверждает `test_stage4_memory` в полном прогоне.
- Ревью мамы-кабана — по одной на подпартию; решения и расходы — HANDOFF / `docs/plan-mu.md`, `docs/plan-mu.md`.

## D. Риски
1. **Романтика без сигнала** (A0.8): при Q1а трек лежит, но не звучит до появления `mood` — честно записать в BACKLOG; при Q1б тема тона
   «романтика» будет звучать во всём мире с `romance ≥ чувственно` вне тегированных локаций — спорно на слух.
2. **Два файла конфига** (Q2): пользователь правит `[audio]` в `config.toml`, а игра пишет `audio.toml` поверх — надо сказать в README, что
   `/music` сильнее ручной правки; `/music` показывает путь к файлу в строке состояния, чтобы было понятно, откуда значение.
3. **Пользовательский конфиг во всех трёх точках** (Q3): если у пользователя уже лежит `~/.config/ai-dm/config.toml` от чего-то ещё — нет (каталог
   новый). Replay детерминирован по журналу, настройки `[master]` из пользовательского файла могут отличаться от исходного прогона — то же, что
   правка `app_defaults.toml`; в `mu-live` отметить.
4. **Лицензии и качество треков** — главный риск (ресёрч): закрывается процедурой A5 (кандидаты → прослушивание пользователем → ATTRIBUTION →
   тест полноты). Агент **не** скачивает и **не** коммитит ничего до утверждения. Конвертация/обрезка — производная работа; для CC-BY/CC0 допустимо,
   фиксируется.
5. **Потоки:** колбэк miniaudio (поток HIGHEST), worker хода Textual, главный поток. Контроллер и плеер — под `Lock`, колбэк не бросает исключений
   (всё ловится внутрь, слой обнуляется), `stop()` идемпотентен; при втором Ctrl+C `os._exit` убивает поток устройства (возможен короткий щелчок —
   допустимо). В тестах — только fake.
6. **Вес репозитория/колеса +30–40 МБ навсегда** (решение В6 принято): один коммит данных после утверждения; `mutants/` копирует данные при каждом
   запуске mutmut (A0.11) — терпимо.
7. **CPU микшера на чистом Python** (A0.2): ≈ 3–5 % ядра; если на живом прогоне больше или слышны провалы — поднять `buffer_ms` (200 → 400) и/или
   уменьшить частоту эмбиента; запас — предрасчёт рамп. `numpy` не вводим.
8. **Headless/SSH:** `PlaybackDevice()` без устройства → `MiniaudioError` на `start()` — ловится один раз (`make_sound`), строка в ленту, дальше
   `NullPlayer`. На macOS без прав на звук — то же.
9. **`extra="forbid"` на `[audio]` и старые пользовательские файлы** — файлов пока нет; опечатка в `config.toml` даст `ValueError` с именем файла при
   старте (как любая ошибка конфига) — это желаемое поведение, но строка должна называть файл (тест).
10. **smells 204/205** — лимит поднимается на факт (решение); если ревью увидит > +3, перепланировка (вынос `command`-таблицы в `audio/commands.py`),
    не рост лимита.
11. **Му-а в TUI всегда печатает «Звук выключен: библиотека не установлена»** до Му-б (Q11) — ожидаемо, строка одна; если мешает — Q11б.

## E. Вопросы проектировщику (рекомендация — первой)
- **Q1. Тема «романтика» — чем запускается** (В5 требует тему, В1в/В4а сигнала не дают). **(а) трек и тема в данных и таблице, автоматического
  триггера в Му нет; запись в BACKLOG «триггер романтики — с полем `mood` (В1б) или тегом сцены»**; (б) по тону: `horror != сильно` и `romance ∈
  {чувственно, откровенно}` → `romance` вместо `explore` (звучит во всех нетегированных локациях такого мира); (в) трек в Му не класть (7 тем).
- **Q2. Как `/music` сохраняет настройки** (В3б + A0.3). **(а) два файла в `~/.config/ai-dm/` (`XDG_CONFIG_HOME`, для тестов `AI_DM_CONFIG_DIR`):
  `config.toml` — пользователь правит руками (любые секции), `audio.toml` — пишет только игра, ровно `[audio] enabled/volume/ambient`, применяется
  поверх `config.toml`**; (б) один `config.toml`, игра перезаписывает его целиком своим TOML-писателем (комментарии и порядок теряются); (в) `/music`
  пишет JSON `audio.json` (как `models.json`) — расходится с буквой В3б «через load_settings».
- **Q3. Пользовательский `config.toml` применяется ко всем настройкам и во всех трёх точках (`prepare`, `--import`, `--replay-report`)?** **(а) да —
  это и есть «пользовательский конфиг», одна функция `load_user_settings(env)`**; (б) только `[audio]`, остальные секции игнорировать (искусственно:
  `load_settings` уже умеет всё).
- **Q4. `/music` в простом режиме** (деталь пользователя, не решение). **(а) отвечает одной строкой «Звук выключен: звук только в TUI»; аргументы не
  принимаются и настройки не меняются**; (б) `/music 40|on|off|ambient …` в простом режиме меняет и сохраняет настройки (без звука) — удобно для SSH,
  +код; (в) `/music` не показывать в HELP простого режима — ломает «HELP общий для обоих режимов» и `test_commands_both_modes`.
- **Q5. `--mute`.** **(а) тишина только на этот запуск, в `audio.toml` не пишется**; (б) `--mute` = `/music off` с записью.
- **Q6. Эмбиент привязан к теме** (таблица `theme → ambient`; у `combat` эмбиента нет → в бою тишина второго слоя). **(а) да**; (б) эмбиент по
  локации независимо от боя (в бою толпа таверны продолжает шуметь) — второй селектор и второй гистерезис.
- **Q7. Подавленная гистерезисом смена.** **(а) применяется на следующем шаге (ход/команда), таймера нет**; (б) Textual `set_timer` на остаток до
  20 с — смена без действия игрока (+код в TUI, +тест Pilot без mutmut).
- **Q8. `--replay`/`--mock` в TUI.** **(а) тишина без строки (не ошибка, а режим)**; (б) строка «Звук выключен: режим --replay».
- **Q9. Лимит smells.** **(а) поднять до факта партии при ревью, цель ≤ 207**; (б) держать 205 переносом `command` в отдельный модуль сразу.
- **Q10. `make install-check`.** **(а) одна установка `ai-dm[audio]`, проверки `import textual` и `import miniaudio`** (без extra проверяется
  тестом с подменённым импортом); (б) две установки — с extra и без (~2× время, сеть); (в) не трогать.
- **Q11. Му-а в TUI** (плеера ещё нет). **(а) уже печатает «Звук выключен: библиотека miniaudio не установлена (uv sync --extra audio)» — поведение
  В10 проверяется сразу**; (б) до Му-б `make_sound` молчит.
- **Q12. Громкость.** **(а) `gain = (volume/100)²` (перцептивно ровнее), эмбиент × `ambient_percent` (50)**; (б) линейно.
- **Q13. Таблица «тег → тема» и теги паков** (A1 `index.yaml`, A5): **(а) как в A1: храм/святилище → town/dark, предгорья → nature (но
  `iron_ridge_foothills_villages` даёт town по первому тегу «деревня»), `vale` → долина/таверна/подвал, `deep_shaft` → шахта; `campaigns/test` не
  трогать**; (б) свой список от проектировщика.
- **Q14. Состав данных Му-б.** **(а) 8 музыкальных тем по 1 треку (≤ 3,5 МБ, OGG q3, стерео) + 5 эмбиентов (толпа, улица, ветер/птицы, капель,
  ночь; ≤ 1,5 МБ, моно); цель ≤ 32 МБ, потолок 40**; (б) эмбиентов 3 (толпа, природа, подземелье); (в) без эмбиента `night`, `dark` без второго слоя.
- **Q15. Где ATTRIBUTION.** **(а) `src/ai_dm/audio/data/ATTRIBUTION.md` (едет в wheel вместе с треками) + абзац в README «Лицензия»**; (б) только в
  корне репозитория (в wheel не попадёт).

Технические умолчания на аппрув вместе с планом: пакет `ai_dm.audio` (`catalog/select/control/player/miniaudio_player`); id тем `combat, tavern,
town, nature, dungeon, dark, explore, romance`; имена файлов = id (`tavern.ogg`), эмбиенты `crowd, street, wind_birds, drips, night`; слои `music`/
`ambient`; `SoundState(location_id, tags, in_combat, horror, romance)`; `[audio]`: `enabled=true, volume=60, ambient=true, ambient_percent=50,
crossfade_s=2.0, min_switch_s=20.0, buffer_ms=200`; гистерезис от момента последней смены, граница включительно; старт — тема сразу; `audio.toml` —
`[audio]` + `enabled/volume/ambient`; строки: «Звук выключен: {причина}», «Звук: вкл, громкость 60, эмбиент: вкл», «Тема: {id} ({music}[ + {ambient}])»,
«Использование: /music [on|off|0–100|ambient on|off]»; `HELP["music"]`; `--mute`; `GameApp.audio` по умолчанию `SilentSound("звук только в TUI")`;
`run_tui(args, app, opening, notes, setup)`; стриминг `stream_file` (не `decode_file`), 44,1 кГц, int16, стерео; луп — перезапуск генератора;
`stop()` в `finally` у `tui.run_tui`; mutmut без `ui.tui.*` и без реального `miniaudio`; сейв v8; HANDOFF «v7» → «v8».

## Решения проектировщика (2026-10-10)
Q1–Q15 — все по рекомендациям (вариант «а»): романтика — трек и тема в данных, автотриггер позже (пункт в BACKLOG «триггер романтики с mood»); два файла config.toml + audio.toml; /music в простом режиме — одна строка «Звук выключен: звук только в TUI»; эмбиент по теме, в бою нет. Технические умолчания из конца плана приняты. План утверждён: «Окей, кабаним» — Му-а.

## Решения: Груминг партии Му — «тематическая музыка и эмбиент» (свинопас, 2026-10-10) (бывш. docs/decisions/mu-grooming.md)

Источники: roadmap-r4-unified #5 Му и раздел 3; BACKLOG 33 (ответы проектировщика 1–3); docs/research/music-research.md; HANDOFF
(порядок R4, инструменты качества); ARCHITECTURE; код на 9b6f56b.

### Груминг

#### Готовность

**Не готова к плану до ответов на В1–В4** (блокирующие). В5–В12 можно закрыть по рекомендации.
Решено раньше (BACKLOG 33, 2026-10-08): только CC0/CC-BY; аудио в репозитории; режим без звука обязателен (SSH/headless,
нет `[audio]`, флаг/команда mute); выбор темы без вызовов LLM; приоритет бой > сцена > локация > тон > тишина.
Не решено: откуда брать уровень «сцена» (в коде у сцены нет ни тона, ни тегов), что делать с локациями без тегов, где
живут громкость и mute между запусками (пользовательского конфига нет), как тон мира превращается в тему.

**Версия сейва.** В коде `CURRENT_SCHEMA_VERSION = 8` (`persistence/migrations/__init__.py:13`). Роадмап (#5) пишет
«v8», HANDOFF (строка «Порядок R4») и задание пишут «v7». Это одна и та же мысль — «новой версии нет», цифра v7
устарела (v8 появилась в Б0). Груминг исходит из v8 без миграции; HANDOFF стоит поправить оркестратору.

**Двусмысленность «`[audio]`».** В роадмапе `[audio]` — необязательная зависимость (`pip install ai-dm[audio]`). В
задании — «секция `[audio]` необязательна». Это разные вещи: extra в pyproject и секция конфига. Груминг считает
обязательными обе необязательности: без extra игра работает молча, без секции конфига — дефолты. Если имелось в виду
одно — поправить в ответе на В3.

`make smells` на 9b6f56b — по HANDOFF 204 (лимит 205, запас 1). Новый модуль audio почти наверняка его съест.

#### Что есть в коде (факты)

- **Готовый образец выбора «по ситуации»** — рисунки: `art/pick.py:45` `pick_picture(prev_state, state, events)` —
  событие (death/victory/level_up) > начало боя > смена локации > ничего. `art/catalog.py:47` `art_for_location`:
  точный id локации → первый совпавший тег (`art/data/index.yaml`, `location_tags`: таверна, город, деревня, болото,
  руины, храм, святилище, магазин, горы, предгорья, гробница, равнина) → None. Родителей не обходит.
- Состояние для выбора уже собирается: `ui/screen.py:90` `picture_state(app)` (локация героя, первый живой враг, id боя).
  События хода — `ui/session.py:29` `turn_events` (death, victory, level_up). Вызов — только в TUI
  (`ui/tui/app.py:283` `show_picture`). Простой режим рисунков не показывает, кроме заставки (`ui/simple.py:73`).
- Бой: `SessionState.active_combat` (`state/session.py:39`); исход боя — `turn.combat_outcome`.
- **Сцена:** `state/scene.py:6` `SceneState` — id, время, счётчики, `location_id`. **Ни тона, ни тегов, ни настроения
  у сцены нет.** Инструмент `end_scene` только закрывает сцену. Ресёрч (разд. 4) предполагал «если у сцены уже есть
  тон/теги от мастера» — их нет.
- **Тон мира:** `state/world.py:15` `Tone` — оси `horror`, `romance`, `violence`, `language` (Literal) и `mood` —
  свободный текст («мрачное фэнтези, моральная серость»). Id пресета в мир не пишется: пресет раскладывается в `Tone`
  (`campaign/presets.py:41`), `preset` есть только в манифесте пака (`campaign/models.py:78`).
- **Теги локаций:** `Location.tags` (`state/world.py:152`) — свободные русские слова. В паках 40 локаций, тегов
  ~26 строк (drunk_dragon 26 из 33, vale/test — почти нет); много служебных (`зачищено`, `власть`, `Ложа`).
  **`location_create` поля `tags` не имеет** (`protocol/requests.py:410`) — локации, созданные мастером на лету, всегда
  без тегов.
- Глобальные события: `event_start`/`event_end` (`protocol/requests.py`) — единственный «сценический» сигнал, который
  уже есть.
- **Конфиг:** `config/app.py:193` `load_settings()` читает только встроенные `defaults.toml` + `app_defaults.toml`;
  CLI зовёт его без пути (`ui/cli.py:471, 629, 751`). **Пользовательского файла настроек нет.** Все модели
  `extra="forbid"`; новая секция `[audio]` = новая модель `AudioConfig`.
- Зависимостей аудио нет; `[project.optional-dependencies]` в `pyproject.toml` нет. Сборка — hatch, в wheel едет
  `src/ai_dm` целиком (файлы данных внутри пакета попадут в дистрибутив). Есть `make install-check`
  (`devtools/check_install.py`) и `make linux-check`.
- Команды: `game/commands.py:31` `HELP` — общий список для обоих режимов; команды музыки нет.
- Режимы, где звука быть не должно: `--replay`, `--replay-report`, `--import`, `--mock`, pytest. Флага `--mute` нет.

#### Суть

Модуль, который после каждого шага игры смотрит на состояние (бой, событие, локация, тон) и говорит плееру «играй тему
X». Плеер — необязательный, на pyminiaudio, в своём потоке, с кроссфейдом, громкостью и mute. Нет библиотеки, нет
устройства, SSH, replay, тесты — тишина без ошибок. Плюс набор треков CC0/CC-BY в репозитории с атрибуцией.
Протокол мастера, промпт и сейв не трогаются (при рекомендованных ответах) — цена хода не меняется.

#### Короткое ТЗ (при рекомендованных ответах)

**Входит.**
1. Выбор темы — чистая функция по образцу `pick_picture`: бой > событие (В1) > локация (id → теги → теги родителя,
   В2) > тон (В4) > тишина. Таблица «тег → тема» и «тема → файлы» — в данных (TOML/YAML, как `art/data/index.yaml`).
2. Гистерезис и возврат после боя (В9).
3. Плеер за интерфейсом «тема / громкость / mute / стоп»: реальный (miniaudio, extra `audio`) и пустой (no-op).
   Выбор реализации при старте; отказ устройства — по В10.
4. Настройки `[audio]` (вкл/выкл, громкость, кроссфейд, гистерезис) — по В3; флаг `--mute`; команда — по В8.
5. Точки входа — по В7; replay/import/report/mock/тесты — всегда no-op.
6. Треки: 6–8 тем (В5), формат и место — В6, файл ATTRIBUTION (автор, название, лицензия, ссылка, дата проверки).
7. Тесты: маппинг тем, приоритеты, гистерезис, возврат после боя, no-op без extra, мок-плеер (запись команд), режимы
   тишины. `make install-check` — с extra и без.

**Не входит.** Поле `mood` в ответе мастера и любые правки протокола/промпта (если В1а/В2а); генерация треков; звуковые
эффекты (удар, монета); своя папка музыки пользователя (ресёрч, разд. 2 — если не В6в); тема на экране создания героя
(если В7а).

**Готово, когда.** Тесты п. 7 зелёные; smells ≤ лимита, dead чисто, mutmut по новым функциям; живой прогон
пользователя (В11).

#### Объём

**M при В1а, В2а, В3а.** Новое: модуль выбора (маленький, есть образец), плеер с микшированием (~100–150 строк,
ресёрч), конфиг, команда, флаг, extra. Плюс работа «данные»: подбор и проверка лицензий треков. Если В1б или В2б —
появляется правка протокола и промпта, тест стабильности префикса, замер кэша: M–L.

#### Риски

1. **Уровень «сцена» пустой.** Сигнала нет; без решения В1 приоритет из роадмапа реализуется не целиком.
2. **Локации без тегов.** Всё, что мастер создаёт на лету, и почти весь `vale` — без тегов. Без В2 большую часть игры
   будет играть тема тона или тишина. Это видно только на живом прогоне.
3. **Лицензии — главный риск (ресёрч, вердикт).** Агент не может послушать трек; лицензию на странице проверить может,
   качество и шов лупа — нет. Неверная атрибуция CC-BY = нарушение лицензии в публичном репозитории.
4. **Вес репозитория.** 6–8 тем по 2–5 МБ = 20–40 МБ в git навсегда (история не чистится). В wheel — тоже, если внутри
   пакета.
5. **Потоки.** Аудио-поток рядом с Textual. В Д1 уже висит «mutmut segfault на `ui.screen` (fork + потоки)» — реальный
   плеер в тестах/mutmut недопустим, только мок.
6. **Колёса miniaudio** под py3.12 macOS arm64/Linux — по ресёрчу есть, в этой сессии не проверено. Если колеса нет —
   сборка из исходников на машине пользователя.
7. **Headless/SSH.** Нет устройства → исключение при открытии. Должно ловиться один раз на старте.
8. **smells 204/205** — запас 1.
9. **Нет пользовательского конфига** — громкость/mute, выставленные командой, не переживут перезапуск (В3).

#### Вопросы проектировщику (рекомендация первой)

- **В1 [блок.] Что такое «сцена» в приоритете.** У сцены нет тона и тегов. **(а) уровень «сцена» = идущее глобальное
  событие (`event_start` … `event_end`), тема по типу события в таблице; поле `mood` от мастера — не делать в Му** (0
  правок протокола); (б) добавить необязательное `mood` в протокол мастера (новый инструмент или поле) — правка
  промпта и схемы инструментов, меняет кэшируемый префикс, нужен замер цены хода; (в) уровня «сцена» в Му нет вовсе:
  бой > локация > тон > тишина.
- **В2 [блок.] Локации без тегов.** **(а) id → теги → теги родителя (вверх по `parent_id`) → дальше по приоритету;
  протокол не трогать; теги в паках дописать данными (drunk_dragon, vale)**; (б) + поле `tags` в `location_create`
  (мастер ставит теги новым локациям) — правка протокола и промпта, как В1б; (в) только как у рисунков (id → теги), без
  родителей.
- **В3 [блок.] Где живут настройки звука.** Пользовательского конфига нет. **(а) секция `[audio]` в
  `app_defaults.toml` (дефолты: включено, громкость 60), флаг `--mute`, команда меняет только текущий запуск**;
  (б) завести пользовательский файл настроек (напр. `~/.config/ai-dm/config.toml`) — новая инфраструктура, задевает
  все настройки, не только звук; (в) хранить в сейве — нельзя (правило 3 роадмапа: Му без полей).
- **В4 [блок.] Как тон мира даёт тему.** Id пресета в мир не пишется, есть только оси и свободный `mood`. **(а) по
  осям: `horror` = «сильно» → мрачная тема; иначе — нейтральная тема «путь/исследование»**; (б) ключевые слова в
  свободном `Tone.mood` («мрачн», «сказоч», «романт») — хрупко, тексты пишет модель; (в) уровня «тон» нет: после
  локации сразу тишина.
- **В5 Набор тем.** **(а) 7 тем: бой, таверна, город/деревня, дикая природа (лес, равнина, горы, болото), подземелье
  (руины, гробница, подвал, логово), мрачная, исследование (тема тона по умолчанию); по 1 треку**; (б) 10–12 тем с
  романтикой, ужасом, храмом; (в) 5 тем, без мрачной и природы.
- **В6 Треки: кто подбирает и где лежат.** **(а) агент ищет кандидатов (OpenGameArt, Incompetech, freesound) только
  CC0/CC-BY, пишет ATTRIBUTION с ссылкой на страницу лицензии; пользователь слушает и утверждает; OGG, ≤ 5 МБ на трек,
  ≤ 35 МБ всего, обычный git, внутри пакета (едет в wheel)**; (б) то же, но вне пакета (`assets/audio/`), в wheel не
  едет; (в) + своя папка пользователя (`[audio] dir`) поверх встроенных.
- **В7 Где играет музыка.** **(а) игра в TUI и в простом режиме; экран создания героя и пикер — тишина;
  replay/`--replay-report`/`--import`/`--mock`/тесты — всегда тишина**; (б) только TUI; (в) (а) + тема заставки на
  экране создания героя.
- **В8 Команда.** **(а) `/music` — показать состояние; `/music off|on`; `/music 0–100` — громкость; в `HELP` обоих
  режимов, вне хода**; (б) только флаг и конфиг, без команды (противоречит BACKLOG 33 п. 3 «флаг/команда»).
- **В9 Гистерезис и бой.** **(а) смена темы не чаще раза в 20 с, кроме входа в бой и выхода из него (сразу); после боя
  — тема по текущей локации (не «прежняя», если локация сменилась); кроссфейд 2 с; позицию трека не запоминать**;
  (б) запоминать позицию прерванного трека и продолжать с неё (как Combat Plus).
- **В10 Ошибка звука.** **(а) нет extra/устройства/файла → одна строка в ленту при старте «Звук выключен: причина»,
  дальше no-op, без репорта**; (б) полностью молча.
- **В11 Живой прогон.** **(а) TUI: таверна → бой → после боя → смена локации; `/music off/on/громкость`; запуск по
  SSH или без extra — тишина без ошибок; ATTRIBUTION просмотрен**; (б) только «звук есть / нет» без SSH.
- **В12 Деление.** **(а) одной партией M; подбор треков — шагом «данные» до живого прогона (код ждёт треки только на
  прогоне, тесты — на мок-плеере и коротких тестовых файлах)**; (б) Му-а: выбор темы + no-op + мок, без звука;
  Му-б: плеер, треки, живой прогон.

Решения за проектировщика, молча не принятые: источник «сцены» (В1), теги локаций и правка протокола (В2), место
настроек (В3), тон → тема (В4). Предложения разработки (к архитектору, не принятые): выбор темы чистой функцией по
образцу `pick_picture`; плеер за интерфейсом с no-op реализацией; таблица тем в данных рядом с `art/data/index.yaml`.

### Аудит свекрови (кабан-свекровь, 2026-10-10)

**Что проверено:** раздел «Груминг» этого файла; код на 9b6f56b (`persistence/migrations/__init__.py`, `state/scene.py`,
`state/world.py`, `protocol/requests.py`, `config/app.py`, `ui/cli.py`, `art/catalog.py`, `art/pick.py`, `ui/screen.py`,
`ui/session.py`, `game/commands.py`, `pyproject.toml`); HANDOFF (строка «Порядок R4», smells).

**Источники истины:** BACKLOG 33 (идея и ответы проектировщика 1–3, 2026-10-08); roadmap-r4-unified #5 (утверждён
2026-10-08); docs/research/music-research.md (рекомендации ресёрча, не решения).

**Факты о коде — верны.** `CURRENT_SCHEMA_VERSION = 8` (`migrations/__init__.py:13`); `SceneState` без тона/тегов/настроения;
`LocationCreate` без `tags` (`requests.py:410`); `load_settings()` вызывается без пути (`cli.py:471, 629, 751`),
пользовательского файла нет; `Tone` — оси + свободный `mood`; `art_for_location` — id → теги, родителей не обходит;
`optional-dependencies` в pyproject нет; HANDOFF: «Му … v7» и smells 204/205 — так и есть. Уточнения:
- `load_settings(toml_text, path)` уже умеет мерджить внешний файл (`config/app.py:193`) — инфраструктура В3б дешевле,
  чем «новая инфраструктура, задевает все настройки». Оценку варианта (б) стоит смягчить, иначе выбор подталкивается к (а).
- `event_start.event_type` — свободная строка («war, plague и т.п.», `requests.py:495`), и это событие **мира**, а не
  сцены. В1а маппит свободный текст модели на тему (та же хрупкость, за которую отвергнут В4б) и подменяет «сцену»
  глобальным событием. В груминге это не сказано.

| Находка | Где | Откуда взялось | Вердикт |
|---|---|---|---|
| В5а: 7 тем **без романтики**, по 1 треку | В5 | ресёрч — «5–6 тем»; BACKLOG 33 явно называет «романтика → романтическая» | к пользователю: рекомендация расходится с примером проектировщика, сказать прямо |
| «Шум толпы» в таверне (эмбиент, не музыка) | — | BACKLOG 33 («таверна → шум толпы», «эмбиент» в названии) | к пользователю: в вариантах не отражено — музыка или эмбиент-лупы |
| Гистерезис 20 с, кроссфейд 2 с | В9а | ресёрч: «N секунд», «1.5–3 с» — числа выбраны свинопасом | оставить как рекомендацию (вынесено в вопрос) |
| OGG, ≤ 5 МБ/трек, ≤ 35 МБ всего | В6а | ниоткуда (ресёрч: 20–80 МБ, формат не выбран) | к пользователю: в В6 склеены 4 решения (кто ищет, формат, бюджет веса, внутри/вне пакета) — разделить или явно перечислить при ответе |
| Громкость по умолчанию 60, «включено» | В3а | ниоткуда | оставить (мелочь, но в ответе видна) |
| «Позицию трека не запоминать», «после боя — по текущей локации» | В9а | BACKLOG: «возврат темы после боя»; уточнение — свинопаса | оставить: вынесено в вопрос, (б) есть |
| «Поле `mood` в Му не делать» | В1а | BACKLOG/роадмап: `mood` — «опционально» | оставить: вариант В1б есть |
| В3в «в сейве — нельзя» | В3 | правило 3 роадмапы | оставить, но это не вариант, а ограничение |
| HANDOFF «v7» → поправить оркестратору | Готовность | роадмап #5 «v8», код | оставить (правка документа, не решение) |
| Предложения разработки (pick по образцу, no-op плеер, таблица в данных) | конец | помечены «к архитектору, не принятые» | оставить |

**Полнота В1–В12.** Не хватает вопросов:
1. Романтика/ужас как темы — BACKLOG 33 их называет, В5а их выкидывает (см. таблицу); нужен явный выбор.
2. Эмбиент («шум толпы») против музыки — не спрошено.
3. Лимит smells 204/205 — назван риском 8, но решения (поднять лимит / расчистить до партии) не предложено; в Б2 это
   решал проектировщик.
4. Платформы (macOS arm64 / Linux; Windows?) и что делать, если колеса miniaudio нет (риск 6) — без варианта.
5. В1а: что делать с неизвестным `event_type` (нет в таблице → пропуск уровня?) — без ответа.

**Решения за пользователя:** молча не принято ничего блокирующего — В1–В4 вынесены. Но рекомендации В5а (без романтики)
и В6а (числа веса, формат, место) содержат решения, которые проектировщик мог не заметить при ответе «по
рекомендациям»; их стоит назвать отдельно.

**Итог:** факты верны; сверх BACKLOG и роадмапы контента нет — все числа (7 тем, 20 с, 2 с, ≤35 МБ, OGG, 60) оформлены
как рекомендации внутри вопросов, не навязаны. **Нужны решения пользователя:** В1–В4 плюс пять пропущенных вопросов
выше; В5а противоречит примеру из BACKLOG 33 — не принимать «по рекомендациям» без явного согласия.

### Решения проектировщика (2026-10-10)
- В1 — **в)** уровня «сцена» нет: приоритет бой > локация > тон мира; event_start/mood не используются.
- В2 — **а)** id → теги → теги родителя; теги дописать в паки данными, протокол не трогать.
- В3 — **б)** пользовательский конфиг (через `load_settings(path)`); `/music` сохраняет громкость/вкл туда, переживает перезапуск.
- В4 — **а)** horror = «сильно» → мрачная тема, иначе «исследование».
- В5 — **8 тем**: бой, таверна, город/деревня, природа, подземелье, мрачная, исследование, **романтика**; по 1 треку.
- В6 — агент ищет кандидатов (только CC0/CC-BY, ATTRIBUTION), пользователь слушает и утверждает; OGG, внутри пакета, всего ≤ 40 МБ.
- Эмбиент — **нужен**: музыка + эмбиент (второй слой).
- Smells — поднять лимит на факт партии.
- Платформы — macOS + Linux; зависимость необязательная (extra), нет сборки/нет библиотеки → тишина.
- В7 — звук **только в TUI**; простой режим, создание героя, replay, import, мок, тесты — тишина.
- В8 — одна команда `/music`: состояние, on/off, громкость 0–100, вкл/выкл эмбиента; в HELP (в простом режиме — сообщение «звук только в TUI»).
- В9 — смена темы не чаще раза в 20 с, бой — сразу, после боя — тема локации, кроссфейд 2 с, позицию не помнить.
- В10 — одна строка «Звук выключен: причина», дальше тишина.
- В11 — полный живой прогон: таверна → бой → после боя → смена локации, `/music`, запуск без extra.
- В12 — деление **Му-а** (выбор темы, no-op, мок-плеер, пользовательский конфиг) / **Му-б** (плеер, эмбиент, треки, живой прогон).
- Сейв — без миграции (текущая v8).

## Правки по ревью: Му-а: ревью и решения (бывш. docs/decisions/mu-a-review.md)

### Решения проектировщика (2026-10-10)
1. `ambient_percent` — в vulture_allowlist до Му-б (снять в Му-б, когда плеер начнёт читать).
2. `/music on` при enabled=false или `--mute` включает звук сразу (создаёт плеер, если библиотека есть), а не после перезапуска.

### Ревью Му-а (mama-kaban, 2026-10-10)

Проверено: незакоммиченный дифф main против MU-PLAN A1–A5/B1 и решений выше. Тесты подпартии: 534 passed. smells 206/205
(новые: `control.py` `SoundController.__init__` count=6, `make_sound` count=6).

Хорошо: пакет `audio` по образцу `art`, сторожа слоёв, `SilentSound` одним классом, `location_tag_chain` с защитой от
цикла, `load_user_settings` во всех трёх точках cli, атомарная запись `audio.toml`, теги паков по A5.

#### Замечания
1. **[высокий] `--mute` протекает в `audio.toml`.** `make_sound(mute=True)` ставит `enabled=False`, а любая `/music 40`
   или `/music ambient off` в этом запуске зовёт `prefs.save(self.enabled=False, ...)` — следующий запуск без `--mute`
   молчит. Нарушает Q5 («--mute — без записи в prefs», README: «в настройки не пишется»). Предложение: поле
   `saved_enabled = cfg.enabled` в контроллере; `turn_on`/`turn_off` меняют и его; `command` сохраняет его вместо
   `enabled`. Тест doeba: `make_sound(mute=True)` → `command("40")` → в `audio.toml` `enabled = true`.
2. **[средний] Начальная громкость не отдаётся плееру (отступление kaban).** Отложенный путь (`turn_on` при deferred)
   зовёт `set_volume`, обычный (`make_sound` → `open_player`) — нет; в Му-б MiniaudioPlayer стартует с gain 1.0
   вместо 0.36, если сам не прочтёт `cfg.volume`. Предложение: один путь — в `make_sound` после `open_player`
   `sound.player.set_volume((cfg.volume / 100) ** 2)` (или вынести открытие+громкость в метод контроллера и звать
   из обоих мест). Принимать отступление как есть не стоит.
3. **[средний] Лимит smells можно не поднимать.** Оба новых запаха убираются дёшево: `SoundController.__init__(self,
   player, audio, cfg, prefs, now=time.monotonic)` — без `*` (qlty считает `*`); `make_sound` — ветку
   `silent_reason` перенести в `cli.attach_sound` (`app.audio = SilentSound(silent)` и return), параметр уйдёт.
   Ожидаемо 204/205 — проверить `make smells`; тогда Q9 для Му-а не нужен.
4. **[низкий] `status()`: пустые скобки и эмбиент при выключенном слое.** В Му-а файлов нет → «Тема: explore ()»;
   при `ambient off` в скобках всё равно `crowd.ogg`. Предложение: имя эмбиента только при `self.ambient`; скобки
   только если `names` не пуст.
5. **[низкий] `/music on` при уже включённом звуке перезапускает тему** (`apply(wanted)` без проверки) — в Му-б
   лишний кроссфейд того же трека и сброс гистерезиса. Предложение: `if self.theme != self.wanted: self.apply(...)`.
6. **[низкий] Имя параметра.** `SoundController(player, index, ...)` получает `Audio`, хранит в `self.audio`;
   ARCHITECTURE пишет `audio`. Переименовать параметр в `audio`.
7. **[низкий] Падение TUI → простой режим печатает «Звук выключен: библиотека…»** из `notes` (`flush_notes`), хотя
   в простом режиме звука нет по определению. Предложение: в `except tui.TuiStartError` убрать строку звука из
   `notes.lines` (или добавлять её в `run_tui` после успешного старта нельзя — строка нужна в ленте; проще удалить).
8. **[инфо] Критерий приёмки B1 противоречит A4:** «`--new --mock` в TUI показывает строку про miniaudio», а A4 —
   mock молчит (`SilentSound("режим --mock")`). Код следует A4, это верно; ручную проверку делать без `--mock`
   или считать критерий опечаткой плана.

#### Оценка отступлений kaban
- F8 вместо F7 — верно: F7 занят «Репорты».
- `buffer_ms` убран до Му-б — по плану (B1 шаг: «завести в Му-б, а не в allowlist»). Принять.
- `SoundController` берёт `Audio` (индекс+папка) — нужно для `theme_files(folder)`, проще, чем два параметра. Принять
  (с переименованием, п. 6).
- Начальная громкость — не принимать, см. п. 2.
- Флаг `deferred` для `/music on` — реализует решение 2, просто. Принять, но см. п. 1 (сохранение `enabled`).
- `app.audio = SilentSound(SIMPLE_REASON)` при падении TUI — верно: контроллер уже остановлен `finally` в
  `tui.run_tui`, а в простом режиме `/music` должна отвечать «звук только в TUI». Принять.

**Вердикт:** нужны правки — п. 1 обязательно, п. 2–3 желательно в Му-а (дёшево), 4–7 по желанию.

## Правки по ревью: Му-б: ревью и решения (бывш. docs/decisions/mu-b-review.md)

### Решения проектировщика (2026-10-10)
1. Править все замечания, кроме CPU колбэка — он в чек-лист живого прогона. Шов лупа — в ARCHITECTURE как известное ограничение + проверка на прогоне.
2. `ambient_percent` снять из vulture_allowlist.
3. Ротация треков в теме не нужна — один трек на тему.
5. Выбор треков (прослушивание): combat №1, tavern №3, town №1, nature №1, dungeon №2, dark №2, explore №3, romance №1;
   crowd №3, street №2, wind_birds №2, drips №1, night №1 (номера — docs/plan-mu.md).
6. Новая тема `wilds` — опасная дикость (страшный лес): свой трек + эмбиент night; теги «чаща», «тёмный лес», «топь» → wilds;
   при тоне horror=«сильно» природные теги (→ nature) дают wilds. Добор кандидатов.
7. Вариант романтики для grim: тема `romance_sensual` (чувственная, тёмная) для тона romance=«откровенно»; трек подбираем
   сейчас, автотриггер романтики — по-прежнему BACKLOG, он выберет вариант по тону.
8. Добор: wilds — №2 Dark Forest Theme (cynicmusic, CC0); romance_sensual — все 3 кандидата отклонены, повторный поиск.
10. romance_sensual — добор 2, №2 Sardana (Kevin MacLeod, CC BY 4.0). Все треки выбраны.
9. smells 206 > 205 — лимит поднят до 206 (Makefile SMELLS_MAX).
Итог кода+тестов: pytest 12371 passed / 1 xfail; cov 96,83 %; dead чисто; smells 206/206; mutmut — выжившие только
эквивалентные (разбор kaban-doeba); ruff — 5 E501 в tests/unit/ui (не файлы партии, были на main).
4. Баг после узкого except (нашёл kaban-doeba): поток с непредвиденной ошибкой оставался в слое и глушил звук навсегда. Чинить сейчас: такой поток закрывается и выкидывается из слоя, как при DecodeError.

### Ревью Му-б (mama-kaban, 2026-10-10)

Проверено: незакоммиченный дифф main (код kaban + тесты kaban-doeba) против MU-PLAN B2/A1 и Q1–Q15. Тесты
`tests/unit/audio`, `devtools`, `test_architecture`: 340 passed. Треки и ATTRIBUTION не выбраны — не замечание.

Хорошо: miniaudio только в одном модуле и импортируется лениво; fake-модуль и запрет настоящего miniaudio в conftest;
округление один раз в `mix_chunk` (рампа не дребезжит); новый трек стартует с текущего гейна уходящего — рампы
непрерывны, перебивка кроссфейда без скачка; `set_layer` после `stop()` — no-op; тесты подробные (кроссфейд, луп,
DecodeError, стресс из потока).

Отступления kaban принять: `Layer.set(path, fade_s)` без `now_frames` (рампа считается в кадрах колбэка — проще);
`mix_total` + `Stream`; `n` в `mix_chunk` — сэмплы (в ARCHITECTURE и докстринге сказать «сэмплов», не «кадров»);
ImportError в `start()` → `MISSING`; `stop()` вне lock (верно: `device.stop()` ждёт колбэк, тот ждёт lock — дедлок
иначе); `buffer_ms` в AudioConfig (с `ge=20`, дефолт 200).

#### Замечания
1. **[высокий] Открытие файла под lock колбэка.** `MiniaudioPlayer.set_layer` держит `self.lock`, а `Layer.set` внутри
   зовёт `open_stream` → `miniaudio.stream_file` (открытие файла, разбор заголовка OGG, первый декод). Всё это время
   `render` в аудиопотоке ждёт lock → недобор буфера → щелчок ровно в момент кроссфейда. Предложение: в `set_layer`
   открыть поток до lock (`stream = Stream(path, ...)`, `stream.gen = open_stream(...)`), а под lock только
   переставить ссылки (`Layer.set(stream, fade_s)` или `Layer.set` принимает готовый поток). То же для `close()` уходящих
   потоков — дёшево, можно оставить.
2. **[средний] Переоткрытие файла на лупе — в аудиопотоке.** `Stream.read` при конце файла зовёт `open_stream` прямо
   в колбэке: каждый круг трека — открытие и первый декод в реальном времени, при 200 мс буфера на медленном диске
   возможен щелчок на шве лупа. Для Му-б допустимо (треки длинные, шов раз в минуты), но записать в ARCHITECTURE F8 как
   известное ограничение; если на живом прогоне шов щёлкает — держать следующий генератор открытым заранее.
3. **[средний] `except Exception` в `Stream.read` глушит любые ошибки.** Опечатка/TypeError в `send` молча даст
   тишину слоя навсегда. Предложение: ловить `(miniaudio.DecodeError, miniaudio.MiniaudioError)` как в `open_stream`
   (импорт внутри функции уже принят). Колбэк при этом не должен падать — значит, оставить широкий перехват только в
   `MiniaudioPlayer.generator()`/`render` с отдачей тишины, а не в каждом потоке.
4. **[средний] Утечка устройства при сбое `start()`.** Если `PlaybackDevice(...)` создан, а `device.start(generator)`
   бросил `MiniaudioError`, устройство не закрыто (поток/хэндл ОС висит до сборки мусора). Предложение: создать
   устройство, затем `try: device.start(...) except (...): device.close(); return причина`. Тест doeba: fake со
   сбоем `start` → `close` вызван один раз.
5. **[средний] `vulture_allowlist.py:97` `ambient_percent` не снят.** Решение 1 Му-а: снять в Му-б, когда плеер начнёт
   читать — теперь читает (`render`). Убрать строку, проверить `make vulture`.
6. **[низкий] Нулевой fade обрывает старый поток.** `crossfade_s = 0` (конфиг допускает `ge=0`) → `Stream.fade(0, 0)`
   гасит гейн мгновенно — щелчок. Предложение: в `Layer.set` минимальная рампа на уходящий поток, напр.
   `max(fade_frames, RATE // 100)` (10 мс) только для затухания. Тест: fade 0 → первый чанк старого убывает, не 0.
7. **[низкий] Нагрузка колбэка в чистом Python.** На каждый чанк 2–3 списка поэлементно на поток (`chunk`, `mix_total`,
   `mix_chunk`) — 88200 сэмплов/с × до 4 потоков во время кроссфейда, под GIL вместе с Textual. Не правка, а пункт
   чек-листа живого прогона: `top` во время кроссфейда музыки + эмбиента, щелчки при прокрутке ленты. Дешёвое
   улучшение при необходимости — `array("h")` на выходе `Stream.chunk` при `left == 0 and gain == 1.0` уже есть;
   то же можно для постоянного гейна.
8. **[низкий] `Layer.chunk` сбрасывает `current` только после чанка.** Если файл перестал читаться (`gen is None`),
   поток уходит из `current`, но не в `old` и не закрывается явно — `gen` уже None, утечки нет; ок, только
   комментарий «поток сломан — слой молчит до следующего set».
9. **[низкий] Док-расхождение.** План B2 п. 6 — раздел F7, kaban писал F8: сверить номер в ARCHITECTURE и HANDOFF,
   чтобы ссылки из плана не вели в другой раздел; в описании `mix_chunk(parts, n)` — n сэмплов.

Тесты doeba: реализация закрывает их без подгонки (рампа по кадрам, луп через переоткрытие, стресс из потока). Не
хватает: сбой `device.start` (п. 4), нулевой fade у уходящего (п. 6), `set_layer` не блокирует `render` на время
открытия файла (п. 1 — fake `stream_file` с `Event`, проверить, что `pull` из другого потока проходит, пока открытие висит).

**Вердикт:** нужны правки (п. 1, 4, 5 обязательно; 2–3 — желательно до живого прогона).

## Итог: Му: живой прогон (2026-10-10) (бывш. docs/decisions/mu-live.md)

Прогон пользователя по чек-листу Му (TUI, мир `saves/drunk_dragon-29a049dc`, `uv sync --extra audio`). Багов нет.

### Проверено ✅
- Старт: строки «Звук выключен» нет; тема локации с эмбиентом; fade-in без щелчка.
- Бой: `combat` сразу, эмбиент уходит; после боя — тема локации.
- Смена локации: кроссфейд слышен, без щелчков; гистерезис ~20 с соблюдается.
- Луп музыки: повтор без паузы, щелчка на шве не слышно. Шов эмбиента — замечаний нет.
- `/music`: состояние, громкость, off/on, `ambient off`; настройки сохраняются между запусками.
- `--mute` — тишина без строки ошибки; без extra — одна строка «Звук выключен: библиотека miniaudio не установлена…»;
  простой режим — «звук только в TUI».
- Нагрузка: CPU процесса ~9 % при игре музыки и ~9 % во время кроссфейда.
- Новые темы: grim (horror «сильно») — лес → wilds (Dark Forest Theme + ночь); romance_sensual сам не включается (ожидаемо).
- ATTRIBUTION просмотрен.

### Не проверено (на будущее)
- На слух — нет ли в street/crowd современных звуков и разборчивой речи.
- Запуск по SSH на Linux (нет возможности).
- Подлагивает ли ввод/лента во время кроссфейда — вопрос в чек-листе остался без ответа (CPU записан).

Итог: Му закрыта.

## Итог: Из HANDOFF.md до 22д (бывш. docs/HANDOFF.md)

- Му: svinopas ~100 тыс.; kaban-svekrov ~41 тыс.; papa-kaban (план, fable) ~208 тыс. (~15 мин).
- Му-б: kaban ~71 тыс. (~6 мин); dyadya-kaban (кандидаты треков) ~66 тыс. (~3 мин); kaban-doeba ~95+111+128 тыс. (~68 мин, mutmut); kaban правки ~83+84+90 тыс.; mama-kaban ~37 тыс.; dyadya-kaban добор ~45+30 тыс. Статус: код ✅ 1ab741a, треки ✅ 5df0aaf (15 OGG ≈32 МБ, ATTRIBUTION, test_audio_data; решения 1–10 — docs/plan-mu.md; OGG кодирован через libsndfile — в brew-ffmpeg нет libvorbis). Живой прогон ✅ docs/plan-mu.md (багов нет, CPU ~9 %). Му закрыта. Дальше по R4 — Д1. kaban (треки) ~60 тыс. (~9 мин). Ротация треков в теме — не нужна (решение 2026-10-10, один трек на тему).
- Му-а: kaban ~139+146+155 тыс. (~25 мин); kaban-doeba ~162+167+200 тыс. (~54 мин, mutmut); mama-kaban ~73 тыс.

## Приложение: Му-б: кандидаты треков и эмбиентов (шаг «данные», п. 1) (бывш. docs/decisions/mu-tracks.md)

Дата проверки всех страниц: **2026-10-10**. Статус всех строк — **кандидат** (утверждает пользователь на слух, п. 2 A5 `docs/plan-mu.md`).
Ничего не скачано в репозиторий.

### Лицензии

- **Incompetech (Kevin MacLeod)** — CC BY 4.0, <https://creativecommons.org/licenses/by/4.0/>. Проверено на странице трека
  (`incompetech.com/music/royalty-free/index.html?isrc=…`, блок «Attribution Code»: «Licensed under Creative Commons: By Attribution 4.0
  License») и на <https://incompetech.com/music/royalty-free/licenses/>. Атрибуция: «"<Название>" Kevin MacLeod (incompetech.com),
  Licensed under Creative Commons: By Attribution 4.0 License, http://creativecommons.org/licenses/by/4.0/».
  Метаданные (длительность, ISRC) — из каталога `incompetech.com/music/royalty-free/pieces.json`; размер — `Content-Length` прямой ссылки.
- **freesound.org** — CC0 1.0, <https://creativecommons.org/publicdomain/zero/1.0/>. Проверено на странице каждого звука (блок лицензии
  «Creative Commons 0»). Оригинал качается только после входа на freesound; прослушивание — HQ-превью mp3 (ссылка в таблице).

Формат музыки — MP3 (оригинал Incompetech), эмбиентов — как указано (WAV/M4A/AIFF). Конвертация в OGG — п. 3 A5.

### Музыка (8 тем)

| Тема | # | Название | Автор | Лицензия | Длит. | Формат | Размер | Страница | Прослушать/скачать | Статус |
|---|---|---|---|---|---|---|---|---|---|---|
| combat | 1 | Clash Defiant | Kevin MacLeod | CC BY 4.0 | 6:16 | MP3 | 12.0 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1600003) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Clash%20Defiant.mp3) | кандидат |
| combat | 2 | Death and Axes | Kevin MacLeod | CC BY 4.0 | 2:48 | MP3 | 5.4 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1700049) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Death%20and%20Axes.mp3) | кандидат |
| combat | 3 | Curse of the Scarab | Kevin MacLeod | CC BY 4.0 | 5:27 | MP3 | 10.5 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1600014) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Curse%20of%20the%20Scarab.mp3) | кандидат |
| tavern | 1 | The Britons | Kevin MacLeod | CC BY 4.0 | 5:07 | MP3 | 12.3 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN2600004) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Britons.mp3) | кандидат |
| tavern | 2 | Minstrel Guild | Kevin MacLeod | CC BY 4.0 | 3:06 | MP3 | 7.4 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200098) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Minstrel%20Guild.mp3) | кандидат |
| tavern | 3 | Midnight Tale | Kevin MacLeod | CC BY 4.0 | 2:42 | MP3 | 6.5 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1900004) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Midnight%20Tale.mp3) | кандидат |
| town | 1 | Village Consort | Kevin MacLeod | CC BY 4.0 | 3:35 | MP3 | 6.9 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1700007) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Village%20Consort.mp3) | кандидат |
| town | 2 | Townie Loop | Kevin MacLeod | CC BY 4.0 | 2:35 | MP3 | 5.0 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1800003) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Townie%20Loop.mp3) | кандидат |
| nature | 1 | Ascending the Vale | Kevin MacLeod | CC BY 4.0 | 4:08 | MP3 | 7.9 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1600064) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ascending%20the%20Vale.mp3) | кандидат |
| nature | 2 | The Forest and the Trees | Kevin MacLeod | CC BY 4.0 | 1:34 | MP3 | 3.8 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100766) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/The%20Forest%20and%20the%20Trees.mp3) | кандидат |
| nature | 3 | Windswept | Kevin MacLeod | CC BY 4.0 | 3:28 | MP3 | 8.3 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100757) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Windswept.mp3) | кандидат |
| dungeon | 1 | Ossuary 2 - Turn | Kevin MacLeod | CC BY 4.0 | 4:48 | MP3 | 9.2 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1500044) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ossuary%202%20-%20Turn.mp3) | кандидат |
| dungeon | 2 | Rites | Kevin MacLeod | CC BY 4.0 | 2:07 | MP3 | 5.1 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100722) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Rites.mp3) | кандидат |
| dark | 1 | Darkest Child | Kevin MacLeod | CC BY 4.0 | 3:59 | MP3 | 9.6 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100783) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Darkest%20Child.mp3) | кандидат |
| dark | 2 | Unseen Horrors | Kevin MacLeod | CC BY 4.0 | 4:11 | MP3 | 8.0 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400043) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Unseen%20Horrors.mp3) | кандидат |
| dark | 3 | Ice Demon | Kevin MacLeod | CC BY 4.0 | 4:25 | MP3 | 10.6 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1200061) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Ice%20Demon.mp3) | кандидат |
| explore | 1 | Lord of the Land | Kevin MacLeod | CC BY 4.0 | 3:06 | MP3 | 6.0 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400022) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Lord%20of%20the%20Land.mp3) | кандидат |
| explore | 2 | Long Road Ahead | Kevin MacLeod | CC BY 4.0 | 2:26 | MP3 | 5.8 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100588) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Long%20Road%20Ahead.mp3) | кандидат |
| explore | 3 | Skye Cuillin | Kevin MacLeod | CC BY 4.0 | 3:13 | MP3 | 7.9 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100346) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Skye%20Cuillin.mp3) | кандидат |
| romance | 1 | There is Romance | Kevin MacLeod | CC BY 4.0 | 3:18 | MP3 | 8.1 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100044) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/There%20is%20Romance.mp3) | кандидат |
| romance | 2 | Reawakening | Kevin MacLeod | CC BY 4.0 | 3:34 | MP3 | 8.6 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400017) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Reawakening.mp3) | кандидат |
| romance | 3 | Inner Light | Kevin MacLeod | CC BY 4.0 | 9:36 | MP3 | 23.1 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300021) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Inner%20Light.mp3) | кандидат |

Заметки по подбору (по описаниям автора, не на слух): The Britons — «Tavern music like from the olden days»; Midnight Tale — «Gather 'round the
tavern's fire»; Village Consort — «pixellated medieval village»; Townie Loop — «Welcome to the town!»; Lord of the Land — средневековое, «good when
not travelling/travelling»; Reawakening — «Easy love theme; Useful for quiet talks»; Inner Light — 9:36, длиннее лимита 4 мин (потребует обрезки).
Clash Defiant (6:16), Curse of the Scarab (5:27), The Britons (5:07), Ossuary 2 (4:48) — длиннее 4 мин: под лимит 3,5 МБ нужна обрезка.

### Эмбиенты (5)

| Эмбиент (файл) | # | Название | Автор | Лицензия | Длит. | Формат | Размер | Страница | Прослушать (HQ-превью) | Статус |
|---|---|---|---|---|---|---|---|---|---|---|
| crowd.ogg (таверна) | 1 | background_chatter_tavern.wav | dazzamoo | CC0 1.0 | 1:06 | WAV стерео | 11.1 МБ | [стр.](https://freesound.org/people/dazzamoo/sounds/651364/) | [mp3](https://cdn.freesound.org/previews/651/651364_4219647-hq.mp3) | кандидат |
| crowd.ogg | 2 | English pub ambiance.m4a | Talitha5 | CC0 1.0 | 2:20 | M4A моно | 1.1 МБ | [стр.](https://freesound.org/people/Talitha5/sounds/690597/) | [mp3](https://cdn.freesound.org/previews/690/690597_4458028-hq.mp3) | кандидат |
| crowd.ogg | 3 | Small_Town_Bar_007.wav | conleec | CC0 1.0 | 6:11 | WAV моно | 51.3 МБ | [стр.](https://freesound.org/people/conleec/sounds/212094/) | [mp3](https://cdn.freesound.org/previews/212/212094_221578-hq.mp3) | кандидат |
| street.ogg (город) | 1 | Village square voices birds | Martin.Sadoux | CC0 1.0 | 6:29 | WAV стерео | 106.8 МБ | [стр.](https://freesound.org/people/Martin.Sadoux/sounds/422585/) | [mp3](https://cdn.freesound.org/previews/422/422585_8177280-hq.mp3) | кандидат |
| street.ogg | 2 | CROWD village square.wav | nicoproson | CC0 1.0 | 4:08 | WAV стерео | 182.4 МБ | [стр.](https://freesound.org/people/nicoproson/sounds/648483/) | [mp3](https://cdn.freesound.org/previews/648/648483_457982-hq.mp3) | кандидат |
| street.ogg | 3 | Street-Market-Gap-France.wav | Astounded | CC0 1.0 | 14:54 | WAV стерео | 491.1 МБ | [стр.](https://freesound.org/people/Astounded/sounds/483561/) | [mp3](https://cdn.freesound.org/previews/483/483561_10201334-hq.mp3) | кандидат |
| wind_birds.ogg | 1 | Wind in the Trees with Birds.m4a | HighPeakEmma | CC0 1.0 | 0:32 | M4A стерео | 261.7 КБ | [стр.](https://freesound.org/people/HighPeakEmma/sounds/538197/) | [mp3](https://cdn.freesound.org/previews/538/538197_11335579-hq.mp3) | кандидат |
| wind_birds.ogg | 2 | Countryside | brunoboselli | CC0 1.0 | 0:58 | WAV стерео | 15.9 МБ | [стр.](https://freesound.org/people/brunoboselli/sounds/458113/) | [mp3](https://cdn.freesound.org/previews/458/458113_300738-hq.mp3) | кандидат |
| wind_birds.ogg | 3 | Backyard nature | danieldouch | CC0 1.0 | 1:14 | WAV стерео | 13.5 МБ | [стр.](https://freesound.org/people/danieldouch/sounds/163997/) | [mp3](https://cdn.freesound.org/previews/163/163997_1622836-hq.mp3) | кандидат |
| drips.ogg (подземелье) | 1 | Dark Dungeon Ambience | Kinoton | CC0 1.0 | 3:00 | WAV стерео | 49.5 МБ | [стр.](https://freesound.org/people/Kinoton/sounds/516566/) | [mp3](https://cdn.freesound.org/previews/516/516566_2247456-hq.mp3) | кандидат |
| drips.ogg | 2 | Droplets in a cave | iampagan | CC0 1.0 | 0:54 | WAV стерео | 13.6 МБ | [стр.](https://freesound.org/people/iampagan/sounds/177031/) | [mp3](https://cdn.freesound.org/previews/177/177031_2484711-hq.mp3) | кандидат |
| drips.ogg | 3 | Water Dripping (Large Echo) | editor_adp | CC0 1.0 | 1:04 | WAV стерео | 23.5 МБ | [стр.](https://freesound.org/people/editor_adp/sounds/162116/) | [mp3](https://cdn.freesound.org/previews/162/162116_2155835-hq.mp3) | кандидат |
| night.ogg | 1 | Crickets At Night - Raw sound | Defelozedd94 | CC0 1.0 | 3:43 | WAV стерео | 40.8 МБ | [стр.](https://freesound.org/people/Defelozedd94/sounds/522299/) | [mp3](https://cdn.freesound.org/previews/522/522299_9084007-hq.mp3) | кандидат |
| night.ogg | 2 | Wind singing in the mountain, some night cricket in background | felix.blume | CC0 1.0 | 3:50 | WAV стерео | 126.4 МБ | [стр.](https://freesound.org/people/felix.blume/sounds/165526/) | [mp3](https://cdn.freesound.org/previews/165/165526_1661766-hq.mp3) | кандидат |
| night.ogg | 3 | Night Crickets Back Porch.aiff | hdfreema | CC0 1.0 | 3:40 | AIFF стерео | 40.3 МБ | [стр.](https://freesound.org/people/hdfreema/sounds/333221/) | [mp3](https://cdn.freesound.org/previews/333/333221_2098408-hq.mp3) | кандидат |

Риски для прослушивания (не проверено на слух): реальные записи улиц/баров могут содержать современные звуки (машины, музыка из колонок,
разборчивая речь на современном языке) — для фэнтези это повод отклонить; `wind_birds` 1 короткий (0:32) — шов лупа заметнее;
Street-Market-Gap-France — 14:54, нужна вырезка 2 мин.

### Источники

- Каталог и лицензия Incompetech: <https://incompetech.com/music/royalty-free/pieces.json>, <https://incompetech.com/music/royalty-free/licenses/>
- CC BY 4.0: <https://creativecommons.org/licenses/by/4.0/>; CC0 1.0: <https://creativecommons.org/publicdomain/zero/1.0/>
- Поиск freesound с фильтром `license:"Creative Commons 0"`: <https://freesound.org/search/>

### Добор: wilds, romance_sensual (решения 6–7 `docs/plan-mu.md`)

Дата проверки страниц: **2026-10-10**. Статус — **кандидат** (утверждение на слух). Ничего не скачано в репозиторий. Лицензия сверена
на странице каждого трека (OpenGameArt — поле «License(s)»; Incompetech — как выше). Размер — `Content-Length` прямой ссылки;
длительность OGA с сайта не берётся — «н/п» (не проверено), WAV оценён по размеру (44.1 кГц/16 бит/стерео).

| Тема | # | Название | Автор | Лицензия | Длит. | Формат | Размер | Страница | Прослушать/скачать | Статус |
|---|---|---|---|---|---|---|---|---|---|---|
| wilds | 1 | Magic Forest | Kevin MacLeod | CC BY 4.0 | 4:20 | MP3 | 8.3 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1600044) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Magic%20Forest.mp3) | кандидат |
| wilds | 2 | Dark Forest Theme | cynicmusic | CC0 1.0 | н/п | MP3 | 1.9 МБ | [стр.](https://opengameart.org/content/dark-forest-theme) | [mp3](https://opengameart.org/sites/default/files/GameMusic_ForestTheme_24_0.mp3) | кандидат |
| wilds | 3 | dark forest 1 | Alexandr Zhelanov | CC BY 4.0 | ~4:34 | WAV | 48.4 МБ | [стр.](https://opengameart.org/content/dark-forest-1) | [wav](https://opengameart.org/sites/default/files/dark_forest.wav) | кандидат |
| wilds | запас | Creepy Forest (F) | Augmentality (Brandon Morris) | CC0 1.0 (или OGA-BY 3.0) | н/п | OGG | 10.8 МБ | [стр.](https://opengameart.org/content/creepy-forest-f) | [ogg](https://opengameart.org/sites/default/files/forest.ogg) | кандидат |
| romance_sensual | 1 | Tenebrous Brothers Carnival - Snake Lady | Kevin MacLeod | CC BY 4.0 | 3:22 | MP3 | 8.1 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100670) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Tenebrous%20Brothers%20Carnival%20-%20Snake%20Lady.mp3) | кандидат |
| romance_sensual | 2 | Siren Queen's Desire | Jan125 | CC BY 4.0 | н/п | OGG | 1.1 МБ (луп 0.7 МБ) | [стр.](https://opengameart.org/content/siren-queens-desire) | [ogg](https://opengameart.org/sites/default/files/sirenqueensdesire_0.ogg), [луп](https://opengameart.org/sites/default/files/sirenqueensdesire_loop.ogg) | кандидат |
| romance_sensual | 3 | Sad desire | Flixberry Entertainment | CC BY 4.0 | н/п | MP3 | 0.9 МБ | [стр.](https://opengameart.org/content/sad-desire) | [mp3](https://opengameart.org/sites/default/files/Sad%20desire%20music_0.mp3) | кандидат |

Заметки (по описаниям/тегам, не на слух): Magic Forest — feel «Mystical, Dark, Mysterious», лес с кентаврами; Dark Forest Theme — теги dark,
spooky, forest, «dark brooding acoustic guitar and strings»; Creepy Forest — теги eerie, scary — риск уйти в чистый хоррор, поэтому запас;
dark forest 1 — WAV, нужна конвертация и, вероятно, обрезка под лимит. Snake Lady — автор: «one of the more sultry sideshow acts», feel
«Eerie, Mysterious, Unnerving» — чувственно-тёмная, но с карнавальным оттенком; Siren Queen's Desire — по названию и коллаборации, описание
скупое, есть готовый луп; Sad desire — описания нет, может оказаться скорее грустной, чем чувственной. Атрибуция OGA CC BY 4.0:
«"<Название>" by <автор> (opengameart.org/content/<slug>), CC BY 4.0». Явно «sensual/seductive» CC0/CC-BY-треков почти нет: найденные по тегам
`sexy` — Deliciously Sour (Matthew Pablo, CC-BY 3.0, лёгкий шпионский) и Dirty sexy sax (CC-BY-SA — не подходит по лицензии).
Nakarada (serpentsoundstudios.com) по этим темам не проверен: подходящий трек с лицензией на странице найти не удалось.

### Добор 2: romance_sensual

Дата проверки: **2026-10-10**. Статус — **кандидат** (утверждение на слух). Ничего не скачано. Кандидаты прошлого добора (Snake Lady,
Siren Queen's Desire, Sad desire) отклонены и не повторяются. Все пять — Kevin MacLeod, лицензия CC BY 4.0 (как в разделах выше);
длительность, feel и описание — из каталога incompetech `pieces.json`, размер — `Content-Length` прямой ссылки (HTTP 200).

| Тема | # | Название | Автор | Лицензия | Длит. | Формат | Размер | Страница | Прослушать/скачать | Статус |
|---|---|---|---|---|---|---|---|---|---|---|
| romance_sensual | 1 | Night on the Docks - Sax | Kevin MacLeod | CC BY 4.0 | 2:54 | MP3 | 5.9 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100137) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Night%20on%20the%20Docks%20-%20Sax.mp3) | кандидат |
| romance_sensual | 2 | Sardana | Kevin MacLeod | CC BY 4.0 | 3:12 | MP3 | 6.1 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400055) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Sardana.mp3) | кандидат |
| romance_sensual | 3 | Desert City | Kevin MacLeod | CC BY 4.0 | 1:29 | MP3 | 3.7 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1100564) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Desert%20City.mp3) | кандидат |
| romance_sensual | 4 | Dark Fog | Kevin MacLeod | CC BY 4.0 | 3:59 | MP3 | 9.6 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1300031) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Dark%20Fog.mp3) | кандидат |
| romance_sensual | запас | Heart of Nowhere | Kevin MacLeod | CC BY 4.0 | 2:52 | MP3 | 5.5 МБ | [стр.](https://incompetech.com/music/royalty-free/index.html?isrc=USUAN1400045) | [mp3](https://incompetech.com/music/royalty-free/mp3-royaltyfree/Heart%20of%20Nowhere.mp3) | кандидат |

Заметки (по описаниям каталога, не на слух): Night on the Docks - Sax — feel «Dark, Somber, Relaxed», «sad and smooth», нуарный сакс;
Sardana — «Intimate guitar dance piece», feel «Mysterious, Intense», 75 BPM, испанская гитара рубато; Desert City — «Middle Eastern
atmospheric, sort of chill», feel «Grooving, Mysterious, Relaxed», легко лупится, но короткий; Dark Fog — feel «Dark, Grooving, Intense,
Somber» — тёмный пульс; Heart of Nowhere — «Lush vocals and calming chords», риск уйти в печаль — поэтому запас. Не найдено: в OpenGameArt
по `seductive`/`sensual`/`harem` — только Deliciously Sour (уже отмечен выше); FMA, ccMixter, freesound, Nakarada, Scott Buckley,
Purple Planet в этот раз не проверены.
