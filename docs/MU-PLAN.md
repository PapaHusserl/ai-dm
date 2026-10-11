# План партии Му: «тематическая музыка и эмбиент» — Му-а (выбор темы, no-op, мок-плеер, пользовательский конфиг) / Му-б (плеер, эмбиент, треки, живой прогон)

Автор: папа-кабан, 2026-10-10. Статус: **предложение на аппрув** (решения проектировщика В1–В12 + «эмбиент», «smells», «платформы»
из `decisions/mu-grooming.md`, раздел «Решения проектировщика (2026-10-10)», обязательны и приняты за основу). Основа:
`decisions/mu-grooming.md` (ТЗ свинопаса, аудит свекрови, решения), `decisions/music-research.md`, BACKLOG 33, `roadmap-r4-unified.md` #5,
`B3-PLAN.md` (форма), HANDOFF («Инструменты качества», «Правила экономии»). Код на main 9b6f56b: `art/{pick,catalog}.py` + `art/data/index.yaml`
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
     размер, дата проверки страницы. Результат — таблица в `decisions/mu-tracks.md` (кандидаты + статус «утверждён/отклонён»).
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
багами, записанными в `decisions/mu-live.md` и BACKLOG.

**FUNCS Му-б (`TESTS="tests/unit/audio"`; все тесты с fake-модулем, настоящего miniaudio в процессе нет):** `ai_dm.audio.miniaudio_player:mix_chunk`,
`…:gain_ramp`, `…:Layer.set`, `…:Layer.chunk`, `…:Layer.open`, `…:MiniaudioPlayer.start`, `…:MiniaudioPlayer.set_layer`,
`…:MiniaudioPlayer.set_volume`, `…:MiniaudioPlayer.generator`, `…:MiniaudioPlayer.stop`, `ai_dm.audio.control:make_sound` (ветка реального
плеера). Перед mutmut убедиться, что автофикстура `sys.modules["miniaudio"] = None` действует и в `mutants/` (mutmut гоняет те же тесты).

**Живой прогон (пользователь, В11) → `decisions/mu-live.md`:** 0. `uv sync --extra audio`; чек-лист `docs/checklist-mu-live.md` (не коммитить).
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
- Ревью мамы-кабана — по одной на подпартию; решения и расходы — HANDOFF / `decisions/mu-a-review.md`, `decisions/mu-b-review.md`.

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
