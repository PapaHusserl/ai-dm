import argparse
import functools
import json
import os
import re
import shutil
import sys
import tempfile
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from ai_dm.audio import SilentSound, load_audio, make_sound
from ai_dm.campaign.build import StartRefused, known_ids, taken_names
from ai_dm.campaign.loader import (
    PackError,
    load_pack,
    pack_content_dir,
    pack_dir,
    pack_monster_scope,
    pack_npc_trade,
)
from ai_dm.campaign.presets import PACK_TONE, all_preset_packs, load_presets
from ai_dm.config.app import ModelRole, profile_for
from ai_dm.config.user import (
    AUDIO_FILE,
    AudioPrefs,
    config_dir,
    data_dir,
    load_user_settings,
    local_or_user,
)
from ai_dm.content.loader import load_registry
from ai_dm.game import difficulty
from ai_dm.game.app import SIMPLE_REASON, GameApp, merge_pack
from ai_dm.game.commands import calls_cost_line
from ai_dm.game.difficulty import DIFFICULTIES
from ai_dm.game.hero_create import (
    HeroCreateDeps,
    creation_cost_line,
    read_hero_sheet,
    write_hero_sheet,
)
from ai_dm.game.pack_import import (
    check_summary,
    discard_import,
    finish_import,
    pack_report_lines,
    stage_dir,
)
from ai_dm.game.scene import start_scene
from ai_dm.game.starter import new_world_from_pack
from ai_dm.llm.cost import CostLedger
from ai_dm.llm.errors import MissingKey
from ai_dm.llm.factory import make_adapter, verify_key
from ai_dm.llm.journal import Journal
from ai_dm.llm.keys import KEY_VARS, load_key, read_var, redact
from ai_dm.llm.mock import ScriptedAdapter, load_script
from ai_dm.llm.replay import ReplayAdapter, ReplayDivergence
from ai_dm.persistence.durable import set_durable
from ai_dm.persistence.migrations import MigrationContext
from ai_dm.persistence.store import load_slot, peek_campaign_id
from ai_dm.protocol.context import ImportTask, SheetTask
from ai_dm.reports.replay import compare, load_report
from ai_dm.rules.encounter import TIER_WORDS
from ai_dm.ui.format import menu_lines, note_lines
from ai_dm.ui.hero_session import CREATE_HERO, HeroSession
from ai_dm.ui.hero_wizard import CREATE_HERO_STEPS, HeroWizard
from ai_dm.ui.import_session import ImportSession
from ai_dm.ui.io import CaptureOutput, InputSource, OutputSink, StdinInput, StdoutOutput
from ai_dm.ui.key_session import PROVIDER_VAR, KeyDeps, KeySession
from ai_dm.ui.simple import emit_blocks, enter_key_simple, run

# первый ход нового мира — мастер открывает сцену сам
OPENING = (
    "(Начало игры. Открой сцену: где находится герой, что вокруг, кто рядом и что происходит. "
    "Заверши вопросом, что он делает.)"
)

DEFAULT_CAMPAIGN = "vale"
CAMPAIGN_ID_RE = re.compile(r"[a-z0-9_-]+")

HERO_TITLE = "Выберите героя:"
PRESET_TITLE = "Пресет мира:"
PRESET_AS_PACK = "Как в паке"
DIFFICULTY_TITLE = "Сложность боёв:"
# выбор «создать героя на лету» (не id пресета пака)
NEW_HERO = object()
# выбор «создать героя пошагово»
STEP_HERO = object()


@dataclass
class Setup:
    # всё окружение запуска, кроме args и ввода/вывода
    env: object
    dotenv_path: Path
    mock_factory: object
    secrets: list
    campaigns_dir: Path
    mode: str
    # настройки, загруженные в main; нет -- грузятся из env (вызовы без main)
    settings: object = None


def settings_of(setup):
    return getattr(setup, "settings", None) or load_user_settings(setup.env)


def make_parser():
    parser = argparse.ArgumentParser(prog="ai-dm")
    parser.add_argument("--new", action="store_true", help="новый мир")
    parser.add_argument("--world", help="id мира: продолжить (или id нового мира с --new)")
    parser.add_argument("--campaign", help="id пака кампании для нового мира (по умолчанию vale)")
    parser.add_argument("--hero", help="id пресета героя из пака")
    parser.add_argument(
        "--hero-describe", metavar="TEXT",
        help="описание героя словами: ИИ соберёт лист героя на лету (только с --new)",
    )
    parser.add_argument("--preset", help="id пресета мира (по умолчанию как в паке)")
    parser.add_argument(
        "--difficulty", choices=DIFFICULTIES, help="сложность боёв для нового мира (только с --new)"
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument(
        "--provider", metavar="PROFILE",
        help="имя профиля из config (profiles)",
    )
    parser.add_argument("--mock", metavar="PATH", help="YAML-сценарий вместо модели")
    parser.add_argument(
        "--mock-world", metavar="PATH", help="YAML-сценарий вместо модели роли world"
    )
    parser.add_argument(
        "--mock-summarizer", metavar="PATH", help="YAML-сценарий вместо модели роли summarizer"
    )
    parser.add_argument("--replay", action="store_true", help="повтор по журналу мира")
    parser.add_argument(
        "--replay-report", metavar="PATH", help="воспроизвести ход из каталога репорта"
    )
    parser.add_argument(
        "--import", dest="import_file", metavar="FILE",
        help="импорт пака из текстовой выжимки в папку паков (./campaigns, если есть, иначе "
        "~/.local/share/ai-dm/campaigns) под <id> (нужен --campaign <id>; "
        "с --mock -- сценарий вместо модели)",
    )
    parser.add_argument(
        "--saves", default=None,
        help="папка сейвов (по умолчанию ./saves, если есть, иначе ~/.local/share/ai-dm/saves)",
    )
    parser.add_argument("--mute", action="store_true", help="без музыки в этом запуске")
    parser.add_argument("--simple", action="store_true", help="простой построчный режим без TUI")
    return parser


def say(stdout, text):
    for line in note_lines(text):
        stdout.write(line)


def hero_presets(pack):
    by_id = {p.id: p for p in pack.heroes}
    return [by_id[hero_id] for hero_id in pack.manifest.start.heroes]


def pick_tui(title, names, splash=False):
    # выбор пункта экраном TUI до игры: (номер | None, причина отказа запуска)
    try:
        from ai_dm.ui import tui
    except ImportError as error:
        return None, error
    try:
        return tui.pick(title, names, splash), None
    except tui.TuiStartError as error:
        return None, error


def choose_number(stdin, stdout, notes, setup, menu):
    # menu -- (что выбираем, заголовок, пункты, заставка); TUI -- экран, иначе -- ask_choice
    what, title, names, splash = menu
    if setup.mode == "tui":
        number, reason = pick_tui(title, names, splash)
        if reason is None:
            return number
        text = f"Выбор {what} в TUI не запустился: {reason}, простой режим."
        say(notes, redact(text, setup.secrets))
    return ask_choice(stdin, stdout, title, names)


def choose_hero(stdin, stdout, notes, pack, setup):
    # HeroPicker: id пресета пака, NEW_HERO (на лету), STEP_HERO (пошагово) или None (отмена);
    # у пака без пресетов героя выбирать не из чего -- сразу создание
    presets = hero_presets(pack)
    if not presets:
        return NEW_HERO
    names = [p.choices.name for p in presets] + [CREATE_HERO, CREATE_HERO_STEPS]
    number = choose_number(stdin, stdout, notes, setup, ("героя", HERO_TITLE, names, True))
    if number is None:
        return None
    if number == len(presets) + 2:
        return STEP_HERO
    if number > len(presets):
        return NEW_HERO
    return presets[number - 1].id


def make_hero_session(kind, deps, task, width):
    # сессия создания героя: пошаговая для STEP_HERO, иначе на лету
    if kind is STEP_HERO:
        return HeroWizard(deps, task, width)
    return HeroSession(deps, task, width)


def preset_label(preset, hint=""):
    name = preset.name
    if preset.codename:
        name += f" (в духе «{preset.codename}»)"
    label = f"{name} — {preset.description}"
    if hint:
        label += f" {hint}"
    return label


def pack_hints(campaigns_dir, current_id):
    # пресет -> паки, которым он подходит, кроме текущего
    hints = {}
    for preset_id, packs in all_preset_packs(campaigns_dir).items():
        others = [pack for pack in packs if pack[0] != current_id]
        if others:
            hints[preset_id] = others
    return hints


def hint_suffix(packs):
    if not packs:
        return ""
    names = ", ".join(f"«{name}» ({pack_id})" for pack_id, name in packs)
    return f"Лучше подходит пак {names}."


def hint_lines(preset_id, hints, presets):
    # заметки старта: готовая команда нового мира с подходящим паком
    if not preset_id or preset_id == PACK_TONE:
        return []
    return [
        f"Пресету «{presets[preset_id].name}» лучше подходит пак «{name}»: "
        f"новый мир — ai-dm --new --campaign {pack_id} --preset {preset_id}"
        for pack_id, name in hints.get(preset_id, ())
    ]


def choose_preset(stdin, stdout, notes, setup, hints=None):
    # пресет мира меню: id или None (как в паке; Esc и конец ввода -- тоже как в паке)
    presets = load_presets()
    hints = hints or {}
    names = [PRESET_AS_PACK] + [
        preset_label(p, hint_suffix(hints.get(p.id, ()))) for p in presets.values()
    ]
    number = choose_number(stdin, stdout, notes, setup, ("пресета", PRESET_TITLE, names, False))
    if number is None or number == 1:
        return None
    return list(presets)[number - 2]


def choose_difficulty(stdin, stdout, notes, setup, tier="moderate"):
    # сложность боёв меню: easy/normal/hard или None (как в конфиге; Esc и конец ввода -- тоже)
    names = [f"Как в конфиге ({TIER_WORDS[tier]})"]
    names += [difficulty.WORDS[v].capitalize() for v in DIFFICULTIES]
    menu = ("сложности", DIFFICULTY_TITLE, names, False)
    number = choose_number(stdin, stdout, notes, setup, menu)
    if number is None or number == 1:
        return None
    return DIFFICULTIES[number - 2]


def ask_choice(stdin: InputSource, stdout: OutputSink, title, names):
    # номер пункта с 1 или None, когда ввод кончился
    for line in menu_lines(title, names):
        stdout.write(line)
    while True:
        answer = stdin.read("> ")
        if answer is None:
            return None
        if answer.strip().isdigit() and 1 <= int(answer.strip()) <= len(names):
            return int(answer.strip())
        say(stdout, f"Введите число от 1 до {len(names)}.")


def create_hero_tui(session):
    # создание героя экраном TUI: (лист | None, причина отказа запуска)
    try:
        from ai_dm.ui import tui
    except ImportError as error:
        return None, error
    try:
        steps = isinstance(session, HeroWizard)
        placeholder = tui.strings.STEPS_PLACEHOLDER if steps else tui.strings.CREATE_PLACEHOLDER
        return tui.create_hero(session, placeholder), None
    except tui.TuiStartError as error:
        return None, error


def create_hero_simple(stdin, stdout, session):
    emit_blocks(stdout, session.start().blocks, session.width)
    while True:
        step = session.submit(stdin.read("> "))
        emit_blocks(stdout, step.blocks, session.width)
        if step.quit:
            return session.sheet


def create_hero(stdin, stdout, notes, setup, session):
    # лист героя на лету или None (отмена); в TUI -- экран, при сбое экрана -- простой режим
    if setup.mode == "tui":
        sheet, reason = create_hero_tui(session)
        if reason is None:
            return sheet
        text = f"Создание героя в TUI не запустилось: {reason}, простой режим."
        say(notes, redact(text, setup.secrets))
    return create_hero_simple(stdin, stdout, session)


def enter_key(stdin, stdout, notes, setup, session):
    # ввод ключа API; сессия (saved=True, если ключ записан); экран TUI -- партия 2, пока простой
    return enter_key_simple(stdin, stdout, session)


def key_session_of(setup, remember=False):
    deps = KeyDeps(
        settings_of(setup).app, setup.env, setup.dotenv_path, setup.secrets, verify=verify_key
    )
    return KeySession(deps, remember=remember)


def profile_narrator(settings, provider):
    profiles = settings.app.profiles
    if provider not in profiles:
        raise ValueError(f"нет профиля {provider}; есть: {', '.join(profiles)}")
    return profiles[provider].narrator


def stored_narrator(saves_root, world_id):
    path = Path(saves_root) / world_id / "meta" / "models.json"
    if not path.is_file():
        return None
    try:
        stored = json.loads(path.read_text(encoding="utf-8")).get("narrator")
        return ModelRole(provider=stored["provider"], model=stored["model"], max_tokens=1)
    except (ValueError, KeyError, TypeError):
        return None


def chosen_narrator(args, settings, setup, saves_root):
    # явный выбор: --provider, сохранённая модель мира, провайдер мастера ключа (AI_DM_PROVIDER)
    if args.provider:
        return profile_narrator(settings, args.provider)
    if not args.new:
        stored = stored_narrator(saves_root, args.world)
        if stored is not None:
            return stored
    remembered = read_var(PROVIDER_VAR, env=setup.env, dotenv_path=setup.dotenv_path)
    if remembered:
        return profile_narrator(settings, remembered)
    return None


def pick_narrator(args, settings, setup, saves_root, stdout):
    # роль рассказчика: явный выбор (chosen_narrator), roles.narrator, иначе профиль провайдера,
    # для которого есть ключ
    chosen = chosen_narrator(args, settings, setup, saves_root)
    if chosen is not None:
        return chosen
    env, dotenv_path = setup.env, setup.dotenv_path
    narrator = settings.app.roles.narrator
    # имя переменной ключа: у встроенного из KEY_VARS, у хостера из providers (как у make_adapter)
    host = settings.app.providers.get(narrator.provider)
    var = KEY_VARS[narrator.provider] if host is None else host.key_env
    if load_key(narrator.provider, env=env, dotenv_path=dotenv_path, var=var) is not None:
        return narrator
    for provider in settings.app.profiles:
        # профили хостеров (deepseek, qwen) сами не выбираются: только явно (--provider, /model)
        if provider not in KEY_VARS:
            continue
        if load_key(provider, env=env, dotenv_path=dotenv_path) is not None:
            say(stdout, f"Нет ключа {var}: беру профиль {provider}.")
            return profile_narrator(settings, provider)
    return narrator


def make_game_adapter(args, narrator, settings, setup, records):
    # возвращает адаптер; нет ключа -- MissingKey (сообщение уйдёт игроку)
    env, dotenv_path, mock_factory = setup.env, setup.dotenv_path, setup.mock_factory
    if args.mock:
        if mock_factory is not None:
            return mock_factory(args.mock)
        return ScriptedAdapter(load_script(args.mock))
    if args.replay:
        return ReplayAdapter(replay_records(records), role="narrator")
    return make_adapter(narrator.provider, narrator.model, settings.app, env=env,
                        dotenv_path=dotenv_path)


def replay_records(records):
    # создание героя на лету (run_id hero-…) при повторе не вызывается, записей рассказчик не ждёт
    return [r for r in records if not r["run_id"].startswith("hero-")]


def pick_world(args, settings, narrator):
    # роль world: профиль того же провайдера, что у рассказчика; по умолчанию roles.world
    roles = settings.app.roles
    if args.provider:
        return settings.app.profiles[args.provider].world
    if narrator.provider == roles.world.provider:
        return roles.world
    profile = profile_for(settings.app, narrator.provider, narrator.model)
    if profile is not None:
        return profile.world
    return roles.world


def pick_summarizer(args, settings, narrator):
    # роль summarizer: профиль того же провайдера, что у рассказчика; по умолчанию roles.summarizer
    roles = settings.app.roles
    if args.provider:
        return settings.app.profiles[args.provider].summarizer
    if narrator.provider == roles.summarizer.provider:
        return roles.summarizer
    profile = profile_for(settings.app, narrator.provider, narrator.model)
    if profile is not None:
        return profile.summarizer
    return roles.summarizer


def pick_import(args, settings, narrator):
    # роль import: профиль того же провайдера, что у рассказчика; по умолчанию roles.import
    # профиль без своей роли import откатывается на roles.import
    roles = settings.app.roles
    if args.provider:
        return settings.app.profiles[args.provider].import_ or roles.import_
    if narrator.provider == roles.import_.provider:
        return roles.import_
    profile = profile_for(settings.app, narrator.provider, narrator.model)
    if profile is not None:
        return profile.import_ or roles.import_
    return roles.import_


def journal_role_model(records, role, default):
    # replay: модель запроса роли -- из первой записи этой роли в журнале, иначе из конфига
    for record in records or []:
        if record["role"] == role:
            return record.get("requested_model") or default
    return default


def journal_world_model(records, default):
    return journal_role_model(records, "world", default)


def make_world_adapter(args, world, settings, setup, records):
    # адаптер роли world; None -- вызовы world идут через адаптер рассказчика (мок без --mock-world)
    env, dotenv_path, mock_factory = setup.env, setup.dotenv_path, setup.mock_factory
    if args.mock_world:
        if mock_factory is not None:
            return mock_factory(args.mock_world)
        return ScriptedAdapter(load_script(args.mock_world))
    if args.mock:
        return None
    if args.replay:
        return ReplayAdapter(records, role="world")
    return make_adapter(world.provider, world.model, settings.app, env=env,
                        dotenv_path=dotenv_path)


def make_summarizer_adapter(args, summarizer, settings, setup, records):
    # адаптер роли summarizer; None -- запасная выжимка без модели (мок без --mock-summarizer)
    env, dotenv_path, mock_factory = setup.env, setup.dotenv_path, setup.mock_factory
    if args.mock_summarizer:
        if mock_factory is not None:
            return mock_factory(args.mock_summarizer)
        return ScriptedAdapter(load_script(args.mock_summarizer))
    if args.mock:
        return None
    if args.replay:
        # в журнале нет записей summarizer (повтор прогона без роли): запасная выжимка
        if not any(r["role"] == "summarizer" for r in records):
            return None
        return ReplayAdapter(records, role="summarizer")
    return make_adapter(summarizer.provider, summarizer.model, settings.app, env=env,
                        dotenv_path=dotenv_path)


def choose_mode(args, injected, env, stdin_tty, stdout_tty):
    # TUI только в настоящем терминале; --simple, подмена ввода/вывода и TERM=dumb -- простой
    if args.simple or injected or not (stdin_tty and stdout_tty):
        return "simple"
    if env.get("TERM", "") == "dumb":
        return "simple"
    return "tui"


def main(argv=None, *, stdin=None, stdout=None, env=None, dotenv_path=None, mock_factory=None,
         campaigns_dir=None):
    args = make_parser().parse_args(argv)
    injected = stdin is not None or stdout is not None
    stdin = stdin or StdinInput()
    stdout = stdout or StdoutOutput()
    if env is None:
        env = os.environ
    mode = choose_mode(args, injected, env, sys.stdin.isatty(), sys.stdout.isatty())
    # рядом есть -- берём (режим разработчика), нет -- пользовательские папки
    if args.saves is None:
        args.saves = local_or_user(Path("saves"), data_dir(env) / "saves")
    if campaigns_dir is None:
        campaigns_dir = local_or_user(Path("campaigns"), data_dir(env) / "campaigns")
    if dotenv_path is None:
        dotenv_path = local_or_user(Path(".env"), config_dir(env) / ".env")
    secrets = []
    try:
        secrets = [load_key(provider, env=env, dotenv_path=dotenv_path) for provider in KEY_VARS]
        # ключи хостеров тоже маскируются; ошибка конфига -- «Ошибка: …», игра не стартует
        settings = load_user_settings(env)
        hosts = settings.app.providers.values()
        secrets += [read_var(h.key_env, env=env, dotenv_path=dotenv_path) for h in hosts]
        setup = Setup(env, dotenv_path, mock_factory, secrets, campaigns_dir, mode, settings)
        return play(args, stdin, stdout, setup)
    except KeyboardInterrupt:
        say(stdout, "Прервано.")
        return 130
    except Exception as error:
        say(stdout, redact(f"Ошибка: {error}", secrets))
        return 1


def import_refusal(args, stdout, campaigns_dir):
    # код выхода при неверных флагах --import или None
    others = (
        args.new, args.world, args.replay, args.replay_report, args.hero, args.hero_describe,
        args.preset, args.seed is not None, args.mock_world, args.mock_summarizer,
    )
    if any(others):
        say(stdout, "--import несовместим с игровыми флагами (--new, --world, --hero и другими).")
        return 2
    if not args.campaign:
        say(stdout, f"Для --import нужен --campaign <id> (под ним пак ляжет в {campaigns_dir}).")
        return 2
    if CAMPAIGN_ID_RE.fullmatch(args.campaign) is None:
        say(stdout, "--campaign: id пака — латиница, цифры, «_» и «-».")
        return 2
    return None


def import_text(args, stdout, setup, max_chars):
    # текст выжимки или код выхода: пак с этим id уже есть, файл не читается, выжимка не годится
    if pack_dir(setup.campaigns_dir, args.campaign).exists():
        say(stdout, f"Пак {args.campaign} уже есть: выберите другой id (--campaign).")
        return 1
    try:
        text = Path(args.import_file).read_text(encoding="utf-8")
    except (OSError, ValueError) as error:
        say(stdout, f"Выжимка не прочитана: {error}")
        return 1
    problem = check_summary(text, max_chars)
    if problem is not None:
        say(stdout, problem)
        return 1
    return text


def import_dialog(deps, session, stdin, stdout, width):
    # цикл простого режима: прогон, при сбое меню 2.2; цена печатается до переименования staging
    step = session.start()
    emit_blocks(stdout, step.blocks, width)
    while not step.quit:
        step = session.submit(stdin.read("> "))
        emit_blocks(stdout, step.blocks, width)
    say(stdout, calls_cost_line(deps.journal, session.run_ids, "Импорт пака"))


def import_pack(args, stdin, stdout, setup):
    # ai-dm --import FILE --campaign ID: пак из выжимки в campaigns/<id>; вывод без TUI
    refusal = import_refusal(args, stdout, setup.campaigns_dir)
    if refusal is not None:
        return refusal
    settings = settings_of(setup)
    text = import_text(args, stdout, setup, settings.app.import_.max_chars)
    if isinstance(text, int):
        return text
    # как у --replay: сохранённой модели мира нет, рассказчик выбирается как для нового мира
    args.new = True
    narrator = pick_narrator(args, settings, setup, Path(args.saves), stdout)
    role = pick_import(args, settings, narrator)
    try:
        adapter = make_game_adapter(args, role, settings, setup, None)
        Path(setup.campaigns_dir).mkdir(parents=True, exist_ok=True)
        folder = stage_dir(setup.campaigns_dir, args.campaign)
    except MissingKey as error:
        say(stdout, redact(str(error), setup.secrets))
        return 1
    except (OSError, ValueError) as error:
        say(stdout, redact(f"Не удалось подготовить импорт: {error}", setup.secrets))
        return 1
    try:
        return import_run(args, text, (adapter, role, folder), (stdin, stdout, setup), settings)
    finally:
        discard_import(folder)


def import_run(args, text, prepared, io, settings):
    adapter, role, folder = prepared
    stdin, stdout, setup = io
    registry = load_registry([])
    factory = functools.partial(
        make_adapter, app_cfg=settings.app, env=setup.env, dotenv_path=setup.dotenv_path
    )
    deps = HeroCreateDeps(
        adapter=adapter, app_cfg=settings.app, registry=registry, cfg=settings.rules,
        journal=Journal(folder, ".import", settings.app.journal), model=role.model,
        adapter_factory=factory,
    )
    session = ImportSession(deps, ImportTask(args.campaign), text, folder)
    import_dialog(deps, session, stdin, stdout, settings.app.ui.width)
    if session.ctx is None:
        say(stdout, "Импорт отменён, пак не записан.")
        return 1
    finish_import(folder, setup.campaigns_dir, args.campaign)
    for line in pack_report_lines(session.ctx.files):
        say(stdout, line)
    return 0


def flush_notes(notes, stdout):
    if notes is not stdout:
        for line in notes.lines:
            stdout.write(line)


def play(args, stdin, stdout, setup):
    # в режиме TUI строки старта копятся и попадают в ленту; при раннем выходе печатаются как есть
    notes = stdout
    if setup.mode == "tui":
        notes = CaptureOutput()
    secrets = setup.secrets
    if args.import_file:
        return import_pack(args, stdin, stdout, setup)
    if args.replay_report:
        return replay_report(args, stdout, setup)
    try:
        prepared = prepare(args, stdin, stdout, notes, setup)
    except BaseException:
        flush_notes(notes, stdout)
        raise
    if isinstance(prepared, int):
        flush_notes(notes, stdout)
        return prepared
    app, opening = prepared
    if setup.mode == "tui":
        code, reason = run_tui(args, app, opening, notes, setup)
        if reason is None:
            return code
        say(stdout, redact(f"TUI не запустился: {reason}, простой режим.", secrets))
        flush_notes(notes, stdout)
    return run(
        app, stdin, stdout, replay=args.replay, secrets=secrets, opening=opening,
        key_factory=functools.partial(key_session_of, setup),
    )


def attach_sound(args, app, setup):
    # звук только в TUI; replay и mock -- без звука и без строки
    # возвращает строку для ленты или None
    silent = "режим --replay" if args.replay else "режим --mock" if args.mock else None
    if silent is not None:
        app.audio = SilentSound(silent)
        return None
    prefs = AudioPrefs(config_dir(setup.env) / AUDIO_FILE)
    app.audio, line = make_sound(app.settings.app.audio, prefs, load_audio(), mute=args.mute)
    return line


def run_tui(args, app, opening, notes, setup):
    # textual импортируется только здесь, лениво; возвращает (код, причина отказа запуска)
    secrets = setup.secrets
    try:
        from ai_dm.ui import tui
    except ImportError as error:
        return None, error
    line = attach_sound(args, app, setup)
    if line is not None:
        notes.lines.append(line)
    try:
        code = tui.run_tui(
            app, notes=notes.lines, replay=args.replay, secrets=secrets, opening=opening
        )
    except tui.TuiStartError as error:
        # дальше простой режим: звука в нём нет, строки про звук тоже
        app.audio = SilentSound(SIMPLE_REASON)
        if line is not None:
            notes.lines.remove(line)
        return None, error
    return code, None


def campaign_registry(campaign_id, campaigns_dir):
    # возвращает (каталог пака или None, реестр с контентом пака)
    folder = None
    if campaign_id is not None:
        folder = pack_dir(campaigns_dir, campaign_id)
    content_dirs = []
    if folder is not None:
        content_dir = pack_content_dir(folder)
        if content_dir is not None:
            content_dirs.append(content_dir)
    registry = load_registry(content_dirs)
    if folder is not None:
        registry.monster_scope = pack_monster_scope(folder)
    return folder, registry


def role_replay(records, role):
    # адаптер повтора роли; нет записей роли -- None (запасной путь без модели)
    if not any(r["role"] == role for r in records):
        return None
    return ReplayAdapter(records, role=role)


def report_verdict(report, app, reply) -> list[str]:
    # расхождения хода из репорта с повтором; пустой список -- совпало
    turn = reply.turn
    if report.expected is None:
        if turn.committed:
            return ["Ход прошёл, а в репорте он откатан."]
        if turn.failure.reason != report.failure_reason:
            return [f"Сбой {turn.failure.reason!r}, в репорте {report.failure_reason!r}."]
        return compare(report.before, app.bundle)
    if not turn.committed:
        return [f"Ход не прошёл: {turn.failure.reason}."]
    return compare(report.expected, app.bundle)


def replay_report(args, stdout, setup):
    # ход из каталога репорта заново по журналу репорта; живые сейвы не трогаются
    others = (args.new, args.world, args.replay, args.mock, args.mock_world, args.mock_summarizer)
    if any(others):
        say(stdout, "--replay-report несовместим с --new, --world, --replay и --mock*.")
        return 2
    registries = []

    def context_for(campaign_id):
        pack_dir, registry = campaign_registry(campaign_id, setup.campaigns_dir)
        registries.append(registry)
        context = MigrationContext.from_registry(registry)
        context.npc_trade = pack_npc_trade(pack_dir, registry)
        return context

    try:
        report = load_report(args.replay_report, context_for)
    except (FileNotFoundError, KeyError, ValueError) as error:
        say(stdout, redact(f"Репорт не прочитан: {error!r}", setup.secrets))
        return 2
    meta = report.meta
    if not meta["replayable"] or meta["status"] == "none":
        say(stdout, "Репорт не воспроизводится: нет журнала хода (или в репорте нет хода).")
        return 2
    saves_root = Path(tempfile.mkdtemp(prefix="ai-dm-replay-"))
    try:
        return play_report(report, registries[0], saves_root, stdout, setup)
    finally:
        shutil.rmtree(saves_root, ignore_errors=True)


def play_report(report, registry, saves_root, stdout, setup):
    records = report.records
    settings = settings_of(setup)
    now = datetime.fromisoformat(report.now_iso)
    world = journal_role_model(records, "world", None)
    summarizer = journal_role_model(records, "summarizer", None)
    world_adapter = role_replay(records, "world")
    summarizer_adapter = role_replay(records, "summarizer")
    app = GameApp(
        settings, registry, report.before, ReplayAdapter(records, role="narrator"),
        saves_root=saves_root, world_text=report.before.world.lore.world_text,
        model=journal_role_model(records, "narrator", report.meta["model"]),
        use_stored_model=False, campaigns_dir=setup.campaigns_dir, auto_reports=False,
        secrets=setup.secrets, world_adapter=world_adapter, world_model=world,
        summarizer_adapter=summarizer_adapter, summarizer_model=summarizer,
        summarizer_backup=summarizer_adapter,
        adapter_factory=functools.partial(
            make_adapter, app_cfg=settings.app, env=setup.env, dotenv_path=setup.dotenv_path
        ),
        # отпечаток запроса от времени не зависит; now фиксируется ради stamp и saved_at
        now=lambda: now, sleeper=lambda seconds: None,
    )
    try:
        if report.player_input is None:
            # достройка границы: другого публичного пути нет, "retry" меню ошибки зовёт runner.retry
            app.pending = "error_menu"
            reply = app.choose("retry")
        else:
            reply = app.handle(report.player_input)
    except ReplayDivergence as error:
        # журнал записан под старые промпты/схему -- расхождение ожидаемо (STAGE6A-PLAN D.5)
        meta = report.meta
        version = f"формат репорта {meta['report_format']}, схема снимка {report.schema_version}"
        say(stdout, f"Расхождение с журналом: {error} ({version})")
        return 1
    say(stdout, reply.narration or reply.hint or "")
    lines = report_verdict(report, app, reply)
    if lines:
        say(stdout, "Состояние не совпало:")
        for line in lines:
            say(stdout, line)
        return 1
    say(stdout, "Состояние совпало.")
    return 0


def preset_refusal(args, notes):
    # код выхода при неверном --preset или None
    if args.preset is None:
        return None
    if not args.new:
        say(notes, "--preset нужен только для нового мира (--new).")
        return 2
    ids = list(load_presets())
    if args.preset not in [*ids, PACK_TONE]:
        say(notes, f"Нет пресета {args.preset!r}: {', '.join(ids)}, {PACK_TONE} (как в паке)")
        return 2
    return None


def difficulty_refusal(args, notes):
    # код выхода при --difficulty без нового мира или None
    if args.difficulty is not None and not args.new:
        say(notes, "--difficulty нужен только для нового мира (--new).")
        return 2
    return None


def hero_flag_refusal(args, notes):
    # код выхода при неверном --hero-describe или None
    if args.hero_describe is None:
        return None
    refusals = [
        (not args.hero_describe.strip(), "--hero-describe: пустое описание."),
        (
            bool(args.replay),
            "--hero-describe несовместим с --replay: лист героя берётся из meta мира.",
        ),
        (not args.new, "--hero-describe нужен только для нового мира (--new)."),
        (bool(args.hero), "--hero-describe несовместим с --hero."),
    ]
    for hit, text in refusals:
        if hit:
            say(notes, text)
            return 2
    return None


def describe_hero(text, notes, session):
    # создание по --hero-describe: меню нет, один вызов, годный лист принимается; иначе None
    step = session.submit(text)
    if session.state != "review":
        for block in step.blocks:
            if block.kind == "note":
                say(notes, block.text)
        return None
    return session.proposal


def discard_world(saves_root, world_id):
    # отмена создания героя: каталог мира без слотов (там лишь журнал вызовов создания) не нужен
    root = saves_root / world_id
    if root.is_dir() and not any((root / "slots").glob("*")):
        shutil.rmtree(root)


def prepare(args, stdin, stdout, notes, setup):
    # возвращает код выхода (ранний отказ) или (GameApp, opening)
    env, dotenv_path = setup.env, setup.dotenv_path
    secrets, campaigns_dir = setup.secrets, setup.campaigns_dir
    saves_root = Path(args.saves)
    if args.replay and not args.world:
        say(notes, "Для --replay нужен --world <id>.")
        return 2
    refusal = hero_flag_refusal(args, notes)
    if refusal is not None:
        return refusal
    if args.replay and (
        args.seed is None or not (args.hero or read_hero_sheet(saves_root, args.world))
    ):
        say(
            notes,
            "Для --replay нужны --seed и --hero (или лист героя на лету из meta мира; "
            "и --preset с --difficulty, если они были) как в исходном прогоне.",
        )
        return 2
    if args.replay:
        args.new = True
    refusal = preset_refusal(args, notes)
    if refusal is not None:
        return refusal
    refusal = difficulty_refusal(args, notes)
    if refusal is not None:
        return refusal
    if not args.new and not args.world:
        say(notes, "Укажите --new (новый мир) или --world <id> (продолжить).")
        return 2
    if not args.new and (args.hero or args.seed is not None or args.campaign):
        say(notes, "--campaign, --hero и --seed нужны только для нового мира (--new).")
        return 2
    settings = settings_of(setup)
    set_durable(settings.app.persistence.durable)
    if not any(secrets) and not (args.mock or args.replay):
        # ключа нет нигде: мастер; отмена -- дальше прежний MissingKey
        enter_key(stdin, stdout, notes, setup, key_session_of(setup, remember=True))
    narrator = pick_narrator(args, settings, setup, saves_root, notes)
    records = None
    if args.replay:
        records = Journal(saves_root, args.world, settings.app.journal).read_records()
        if not records:
            say(notes, f"Журнал мира {args.world} пуст.")
            return 1
    if not args.new:
        try:
            # реестр грузится до сейва: миграции нужны цены предметов
            peeked = peek_campaign_id(saves_root, args.world, "auto")
            pack_dir, registry = campaign_registry(peeked, campaigns_dir)
            context = MigrationContext.from_registry(registry)
            context.npc_trade = pack_npc_trade(pack_dir, registry)
            bundle = load_slot(saves_root, args.world, "auto", context=context)
        except FileNotFoundError:
            say(notes, f"Нет автосохранения мира {args.world} в {saves_root}.")
            return 1
        scene = bundle.session.current_scene
        if scene is None or scene.closed_reason is not None:
            start_scene(bundle)
        world_id = args.world
        campaign_id = bundle.world.campaign_id
        if campaign_id != peeked:
            # у старых сейвов campaign_id появляется при миграции: пак и реестр по нему
            pack_dir, registry = campaign_registry(campaign_id, campaigns_dir)
        if context.report:
            say(notes, context.warning())
    else:
        campaign_id = args.campaign or DEFAULT_CAMPAIGN
        pack_dir, registry = campaign_registry(campaign_id, campaigns_dir)
        world_id = args.world or f"{campaign_id}-{uuid.uuid4().hex[:8]}"
        if args.world and not args.replay and (saves_root / world_id).exists():
            say(notes, f"Мир {world_id} уже есть: продолжить — ai-dm --world {world_id}")
            return 1
        bundle = None
    seed = None
    world_role = pick_world(args, settings, narrator)
    summarizer_role = pick_summarizer(args, settings, narrator)
    try:
        adapter = make_game_adapter(args, narrator, settings, setup, records)
        world_adapter = make_world_adapter(args, world_role, settings, setup, records)
        summarizer_adapter = make_summarizer_adapter(
            args, summarizer_role, settings, setup, records
        )
    except MissingKey as error:
        say(notes, redact(str(error), secrets))
        return 1
    except (OSError, ValueError) as error:
        say(notes, redact(f"Не удалось подготовить модель: {error}", secrets))
        return 1
    def adapter_factory(provider, model):
        return make_adapter(provider, model, settings.app, env=env, dotenv_path=dotenv_path)

    model = narrator.model
    preset = args.preset
    difficulty_value = args.difficulty
    created = None
    hints = {}
    world_model = world_role.model
    if args.replay:
        world_model = journal_world_model(records, world_model)
    summarizer_model = summarizer_role.model
    if args.replay:
        summarizer_model = journal_role_model(records, "summarizer", summarizer_model)
    if bundle is None:
        try:
            pack = load_pack(pack_dir, registry)
        except PackError as error:
            say(notes, f"Пак {campaign_id} не загружен:")
            for line in error.lines:
                say(notes, line)
            return 1
        hints = pack_hints(campaigns_dir, pack.manifest.id)
        if args.hero_describe is not None:
            hero = NEW_HERO
        elif args.hero:
            hero = args.hero
        elif args.replay:
            hero = read_hero_sheet(saves_root, args.world)
        else:
            hero = choose_hero(stdin, stdout, notes, pack, setup)
            if hero is not None and preset is None:
                preset = choose_preset(stdin, stdout, notes, setup, hints)
            if hero is not None and difficulty_value is None:
                difficulty_value = choose_difficulty(
                    stdin, stdout, notes, setup, settings.rules.encounter.tier
                )
        if hero is NEW_HERO or hero is STEP_HERO:
            created = HeroCreateDeps(
                adapter=adapter, app_cfg=settings.app, registry=registry, cfg=settings.rules,
                journal=Journal(saves_root, world_id, settings.app.journal),
                ledger=CostLedger(saves_root, world_id), model=model,
                adapter_factory=adapter_factory,
            )
            task = SheetTask(known=known_ids(pack), taken_names=taken_names(pack))
            session = make_hero_session(hero, created, task, settings.app.ui.width)
            if args.hero_describe is None:
                hero = create_hero(stdin, stdout, notes, setup, session)
            else:
                hero = describe_hero(args.hero_describe, notes, session)
            adapter = created.adapter
            model = created.model
        if hero is None:
            if args.hero_describe is None:
                say(notes, "Герой не выбран.")
            if created is not None:
                discard_world(saves_root, world_id)
            return 1
        if isinstance(hero, str) and hero not in pack.manifest.start.heroes:
            names = ", ".join(pack.manifest.start.heroes)
            say(notes, f"В паке {campaign_id} нет героя {hero!r}: {names}")
            return 2
        seed = args.seed if args.seed is not None else uuid.uuid4().int % 2**32
        conflicts = []
        try:
            bundle = new_world_from_pack(
                registry, settings.rules, pack, hero=hero, seed=seed, world_id=world_id,
                saved_at=datetime.now(UTC).isoformat(), conflicts=conflicts,
                preset_id=preset, difficulty=difficulty_value,
            )
        except StartRefused as error:
            say(notes, "Старт отказан:")
            for line in error.lines:
                say(notes, line)
            if created is not None:
                discard_world(saves_root, world_id)
            return 1
        if created is not None:
            write_hero_sheet(saves_root, world_id, hero)
            kind = "пошагово" if isinstance(session, HeroWizard) else "на лету"
            say(notes, f"Герой {kind}: {hero.choices.name}")
            if session.run_ids:
                say(notes, creation_cost_line(created.journal, session.run_ids))
        if conflicts:
            say(notes, "Не загружено из пака (конфликты):")
            for conflict in conflicts:
                say(notes, conflict.line())
    else:
        for line in merge_pack(bundle, registry, campaigns_dir):
            say(notes, line)
    if args.replay:
        saves_root = Path(tempfile.mkdtemp(prefix="ai-dm-replay-"))
        say(notes, f"Повтор идёт во временной папке {saves_root}, живой мир не меняется.")
    else:
        seed_text = "" if seed is None else f", сид {seed}"
        if preset:
            seed_text += f", пресет {preset}"
            if preset == PACK_TONE:
                seed_text += " (как в паке)"
        if difficulty_value:
            seed_text += f", сложность {difficulty.WORDS[difficulty_value]}"
        say(notes, f"Мир: {world_id}{seed_text} (продолжить: ai-dm --world {world_id})")
        for line in hint_lines(preset, hints, load_presets()):
            say(notes, line)

    app = GameApp(
        settings, registry, bundle, adapter, saves_root=saves_root,
        adapter_factory=adapter_factory, world_text=bundle.world.lore.world_text,
        model=model,
        use_stored_model=not (args.mock or args.replay), campaigns_dir=campaigns_dir,
        auto_reports=not (args.mock or args.replay), secrets=setup.secrets,
        refusal_chain=not (args.mock or args.replay), world_adapter=world_adapter,
        world_model=None if world_adapter is None else world_model,
        summarizer_adapter=summarizer_adapter,
        summarizer_model=None if summarizer_adapter is None else summarizer_model,
        summarizer_backup=summarizer_adapter if args.replay else None,
    )
    if created is not None:
        # траты создания входят в сессию (лимиты, /cost)
        app.ledger.session_lines.extend(created.ledger.session_lines)
    if args.new and not args.replay:
        app.save_current("auto")
    opening = None
    if args.new and not (args.mock or args.replay):
        opening = OPENING
    return app, opening


if __name__ == "__main__":
    sys.exit(main())
