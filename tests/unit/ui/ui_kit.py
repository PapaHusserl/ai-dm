# Общие помощники тестов слоя ui (этап 2, партия 6). Не фикстуры pytest, а обычные функции.
# Живых вызовов и сети нет: ScriptedAdapter / YAML-сценарии / ReactiveAdapter из game_kit.
# Импорты ai_dm.ui.* -- ВНУТРИ функций: пока слоя нет, тесты падают по одному (red).
#
# КОНТРАКТ СЛОЯ ui (STAGE2-PLAN A6, ТЗ 10, 11, 6). Где план не даёт точных имён, они выбраны
# здесь -- это ТРЕБОВАНИЕ к реализации. ui -- верхний слой: его импортирует только он сам
# (сторож в test_architecture.py). ui синхронный, ввод-вывод только через io.
#
#   ai_dm.ui.io
#     InputSource (Protocol): read(prompt: str = "") -> str | None  (None -- ввод кончился)
#     OutputSink (Protocol): write(line: str) -> None  (одна строка вывода за вызов)
#     ScriptedInput(lines): read() отдаёт строки по очереди, потом None; .remaining -- список
#       ещё не прочитанных строк; переданный список не меняется.
#     CaptureOutput(): write() накапливает; .lines -- list[str] в порядке записи; .text --
#       "\n".join(lines).
#
#   ai_dm.ui.simple
#     status_line(app) -> str: "HP <cur>/<max> · <дата календаря> <ЧЧ:ММ> · сессия $<сумма>"
#       (HP героя; дата -- world.clock.to_date(), время -- now_s внутри суток; сумма --
#       ledger.report(today).session.total_nano / 1e9 с 3 или 4 знаками: "$0.000" / "$0.0000").
#     run(app, source, sink) -> None: цикл. Старт: app.startup_lines -> строка состояния -> текущий
#       экран (pending-меню, иначе в бою список действий). Дальше: read -> app.handle / choose ->
#       вывод ответа -> строка состояния. Конец: ввод кончился (None) или reply.quit.
#     Вывод ответа (всё -- отдельными строками sink):
#       - reply.lines как есть; narration как есть; строки turn.lines с префиксом "[бросок] ";
#         строки turn.log как есть (в них бой: "... против КД 19 → промах"); hint как есть;
#       - итог боя: при turn.combat_outcome == "victory" строка со словом «победа» (регистр не
#         важен) и строка со словами «опыт» и числом полученного опыта (рост hero.sheet.xp);
#       - вне боя при непустых bundle.session.offered_choices -- "1. <вариант>" ... ;
#       - в бою (active_combat, pending None) -- список runner.preview_turn(): "<n>. <label>";
#       - pending -> меню: нумерованные строки "<n>. <метка>", метка -- по ключу:
#           retry «повтор», switch_model «модел», save_and_quit «сохран»; average «средн»,
#           roll «бросок»; load_last_save «загруз», quit «выйти»; model_choice -- сам id
#           "provider:model".
#     Ввод: цифры при pending -> app.choose(menu[n-1]); вне диапазона -- строка «Нет такого
#       варианта» и ничего больше. Цифры вне боя при offered_choices -> текст варианта в
#       app.handle; в бою цифры уходят в app.handle как есть (номер действия, без модели).
#       Остальное (текст, /команды) -> app.handle. /quit -> цикл кончается.
#     Мягкий лимит (cfg.app.cost_limits включён, llm.cost.check_limit по трате сессии и
#       session_limit_micro): после хода "warn" -> строка со словом «лимит» и «80%» (warn_percent);
#       "pause" -> строка со словом «лимит» + меню "1. продолжить" / "2. сохранить и выйти";
#       "1" -- игра идёт дальше, "2" -- автосейв и конец цикла.
#
#   ai_dm.ui.cli
#     main(argv=None, *, stdin=None, stdout=None, env=None, dotenv_path=None, mock_factory=None)
#       -> int (код выхода; исключения наружу не летят, трейсбека нет).
#       stdin: InputSource, stdout: OutputSink (по умолчанию -- настоящие stdin/stdout);
#       env: словарь вместо os.environ; dotenv_path: путь к .env (по умолчанию ./.env);
#       mock_factory(script_path) -> адаптер: подмена ScriptedAdapter для --mock (тесты боя,
#       где нужен ReactiveAdapter); по умолчанию ScriptedAdapter(load_script(path)).
#       Ошибки (нет ключа, нет мира, нет файла сценария) -- сообщение в stdout и код != 0.
#       Разбор аргументов argparse-ом: плохие аргументы -- SystemExit с кодом != 0 (допустимо).
#     Параметры:
#       --new             новый мир (game.starter.new_world), id по умолчанию уникальный;
#       --world <id>      без --new: продолжить мир -- слот "auto" из <saves>/<id>; с --new: id
#                         нового мира (нужно для --replay);
#       --hero arn|liel   герой; без флага при --new -- вопрос на старте через stdin
#                         («1. Арн» / «2. Лиэль», ответ -- номер);
#       --seed N          сид RNG нового мира (int);
#       --mock PATH       ScriptedAdapter по YAML; ключ не нужен; use_stored_model=False;
#       --replay          ReplayAdapter по журналу <saves>/<id>/journal (id из --world, вместе с
#                         --new: новый мир с тем же id и сидом, повтор ходов); ключ не нужен;
#                         use_stored_model=False;
#       --saves DIR       корень сейвов, по умолчанию ./saves.
#     Модель для GameApp(model=...) и цены -- рассказчик из конфига (roles.narrator.model).
#     Без ключа, --mock и --replay: сообщение с «ANTHROPIC_API_KEY» и «.env», код != 0.
#     pyproject: [project.scripts] ai-dm = "ai_dm.ui.cli:main".
#
# ДОПОЛНЕНИЯ по ревью партии 6 (docs/decisions/stage2-batch6-review.md, B1-B6, D1-D8):
#   run(app, source, sink, replay=False, secrets=()) -> int: 0 или 1 (ошибка хода в replay).
#     Строки turn.lines, уже есть в turn.log, не дублируются; «[бросок] » -- только у строк из
#     turn.rolls; служебные строки («Действие игрока: ...», «Варианты ответа предложены») не
#     печатаются. Мягкий лимит -- худшее из сессионного и дневного; только при app.pending is None;
#     «Сохранить и выйти» при pending == "hero_dead" запрещено,
#     ValueError от save_current -- сообщение.
#     Исключение в handle/choose -- «Ошибка хода: ...» (ключи -> ***), цикл жив; в replay -- код 1.
#   main: при старте строка «Мир: <id> (продолжить: ai-dm --world <id>)»; после --new (не replay)
#     автосейв «auto»; --new --world <есть> -> код 1; --replay требует --world, --hero,
#     --seed (код 2),
#     пустой журнал -> код 1; replay идёт во временном каталоге «ai-dm-replay-*» (путь выведен),
#     живой мир не меняется; --hero/--seed с --world без --new -> код 2; ask_hero переспрашивает;
#     ошибки (в т. ч. из mock_factory) идут через redact (***), Ctrl-C -> код 130.
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from game_kit import (  # noqa: E402, F401
    OPUS,
    SAVED_AT,
    FactorySpy,
    ReactiveAdapter,
    ScriptThenReactive,
    make_app,
    player_action_input,
    requests_with_tools,
    scripted_from_yaml,
    settings,
    state_of,
    text_step,
)

from ai_dm.llm.mock import ScriptedAdapter  # noqa: E402

SEED = 3
WORLD = "vale-ui"
NUMBERED = re.compile(r"^(\d+)\. (.+)$")
# U7: «снять оформление». Оформление (stage2-live-1, U1-U6): рамка ╭─╮ │ … │ ╰─╯ вокруг
# повествования, отступы, маркер броска, перенос длинных строк, строка состояния «── … ──».
# Маркер броска -- один из ROLL_MARKERS (какой именно, решает реализация); в чистом тексте
# он заменяется на "[бросок] ".
ROLL_MARKERS = ("🎲", "⚄", "[d20]")
ROLL_PREFIX = "[бросок] "
FRAME_TOP = "╭"
FRAME_BOTTOM = "╰"
FRAME_SIDE = "│"
RULE = "─"
TALK = "Спрашиваю трактирщика, что слышно в округе"
DESCEND = "Спускаюсь в подвал"


def build_app(registry, root, adapter, *, seed=SEED, hero="arn", hp=None, adapter_factory=None):
    from slots_kit import WORLD_TEXT

    from ai_dm.game.starter import new_world

    bundle = new_world(
        registry, settings().rules, hero=hero, seed=seed, world_id=WORLD, saved_at=SAVED_AT
    )
    if hp is not None:
        bundle.heroes[0].creature.hp_max = bundle.heroes[0].creature.hp_current = hp
    return make_app(
        registry, root, adapter, bundle=bundle, world_text=WORLD_TEXT, model=OPUS,
        adapter_factory=adapter_factory,
    )


def text_app(registry, root, steps, **kw):
    adapter = ScriptedAdapter(steps, provider="anthropic", model=OPUS)
    return build_app(registry, root, adapter, **kw)


def scene_app(registry, root, **kw):
    # три хода talk_check_fight.yaml, дальше -- ReactiveAdapter
    adapter = ScriptThenReactive(scripted_from_yaml("talk_check_fight.yaml"), ReactiveAdapter())
    return build_app(registry, root, adapter, **kw), adapter


def play(app, lines):
    from slots_kit import ScriptedInput

    from ai_dm.ui.simple import run

    out = PlainOutput()
    run(app, ScriptedInput(lines), out)
    return out


def numbered_lines(lines):
    result = []
    for line in lines:
        match = NUMBERED.match(line)
        if match:
            result.append((int(match.group(1)), match.group(2)))
    return result


def cli(argv, lines=(), **kw):
    # main() с ScriptedInput / CaptureOutput; возвращает (код, вывод)
    from slots_kit import ScriptedInput

    from ai_dm.ui.cli import main

    out = PlainOutput()
    try:
        code = main(argv, stdin=ScriptedInput(lines), stdout=out, **kw)
    except SystemExit as error:
        code = error.code
    return code, out


def write_script(path, text="Рассказ."):
    path.write_text(f'steps:\n  - text: "{text}"\n', encoding="utf-8")
    return path


class FightInput:
    # ввод, который смотрит на вывод: сначала фиксированные строки, потом по номерам: меню
    # повышения уровня -> «средн», иначе атака мечом, иначе шаг к врагам, иначе последний пункт.
    # Нет нумерованных строк в новом выводе -- ввод кончился
    MOVES = ("Идти: Земляной пол", "Идти: Бочки")

    def __init__(self, out, first, limit=100):
        self.out = out
        self.first = list(first)
        self.seen = 0
        self.reads = 0
        self.limit = limit

    def read(self, prompt=""):
        new = self.out.lines[self.seen:]
        self.seen = len(self.out.lines)
        if self.first:
            return self.first.pop(0)
        self.reads += 1
        options = numbered_lines(new)
        if self.reads > self.limit or not options:
            return None
        preferred = (
            lambda text: "средн" in text.lower(),
            lambda text: text.startswith("Атака:"),
            lambda text: text in self.MOVES,
        )
        for matches in preferred:
            for number, text in options:
                if matches(text):
                    return str(number)
        return str(options[-1][0])


class EndTurnInput:
    # один ввод: номер пункта «Закончить ход» из уже выведенного списка; потом конец ввода
    def __init__(self, out):
        self.out = out
        self.done = False

    def read(self, prompt=""):
        if self.done:
            return None
        self.done = True
        for number, text in reversed(numbered_lines(self.out.lines)):
            if text == "Закончить ход":
                return str(number)
        return None


def roll_text(line):
    # «  🎲 d20 (14) ...» -> "d20 (14) ..."; None, если это не строка броска
    body = line.strip()
    for marker in ROLL_MARKERS:
        if body.startswith(marker + " "):
            return body[len(marker) + 1:]
    return None


def indent_of(line):
    return len(line) - len(line.lstrip(" "))


def continues_item(prev_item, prev_indent, indent, body, line):
    # перенос пункта списка / броска: строка глубже предыдущего пункта и сама не пункт
    if not prev_item or prev_indent is None or indent <= prev_indent:
        return False
    return not NUMBERED.match(body) and roll_text(line) is None


def plain_lines(raw):
    # сырой вывод -> логические строки: без рамки, отступов, переносов, разделителя; пустые
    # строки выброшены. Абзац рамки -- одна строка. Перенос пункта списка / броска (строка с
    # бОльшим отступом, не «N. ...») склеивается с предыдущей строкой пробелом.
    result = []
    paragraph = []
    prev_indent = None
    prev_item = False
    for line in raw:
        if line.startswith((FRAME_TOP, FRAME_BOTTOM)):
            continue
        if line.startswith(FRAME_SIDE):
            inner = line[1:-1].strip() if line.endswith(FRAME_SIDE) else line[1:].strip()
            if inner:
                paragraph.append(inner)
            elif paragraph:
                result.append(" ".join(paragraph))
                paragraph = []
            prev_item = False
            continue
        if paragraph:
            result.append(" ".join(paragraph))
            paragraph = []
        body = line.strip()
        if not body:
            continue
        if body.startswith(RULE * 2) and body.endswith(RULE * 2):
            body = body.strip(RULE).strip()
            if body:
                result.append(body)
            prev_item = False
            continue
        indent = indent_of(line)
        if continues_item(prev_item, prev_indent, indent, body, line):
            result[-1] += " " + body
            continue
        rolled = roll_text(line)
        if rolled is not None:
            result.append(ROLL_PREFIX + rolled)
            prev_item = True
        else:
            result.append(body)
            prev_item = bool(NUMBERED.match(body))
        prev_indent = indent
    if paragraph:
        result.append(" ".join(paragraph))
    return result


class PlainOutput:
    # вместо CaptureOutput в тестах содержимого: .lines / .text -- уже без оформления, .raw --
    # то, что реально записано в sink (для тестов оформления)
    def __init__(self):
        self.raw = []

    def write(self, line):
        self.raw.append(line)

    @property
    def lines(self):
        return plain_lines(self.raw)

    @property
    def text(self):
        return "\n".join(self.lines)
