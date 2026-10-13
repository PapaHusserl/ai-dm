# Приёмка этапа 2 через ui (ТЗ 13, STAGE2-PLAN «Критерий готово», партия 6): сцена «разговор ->
# проверка -> бой» на моке проходит через простой построчный интерфейс. Живых вызовов нет:
# ScriptedAdapter (tests/fixtures/scripts/talk_check_fight.yaml), ReactiveAdapter из game_kit
# (бой реактивный: число ходов зависит от бросков), ReplayAdapter по журналу.
#
# Критерий ТЗ 13 этапа 2 -> тест
#   «мок-адаптер со скриптованными ответами проходит сцену “разговор → проверка → бой”»
#     повествование трёх ходов в выводе ......... test_cli_prints_narration_of_all_three_turns
#     нумерованные варианты ..................... test_cli_prints_numbered_choices
#     строка `[бросок] ... против СЛ 15 ...` ........ test_cli_prints_roll_line_with_dc_15
#     переход в бой, список действий ............ test_cli_enters_combat_and_lists_actions
#     порядок: рассказ, бросок, бой, действия ... test_cli_output_goes_in_scene_order
#   честная победа через main(): Арн с родными 12 HP, сид HONEST_SEED (подобран, ниже)
#     «разговор -> проверка -> бой -> победа -> автосейв -> меню уровня» по порядку
#                                                 test_cli_honest_win_goes_through_the_whole_scene,
#                                                 test_cli_honest_win_prints_victory_and_xp,
#                                                 test_cli_honest_win_opens_level_up_menu,
#                                                 test_cli_honest_win_makes_auto_save
#     победа, опыт, повышение уровня (герой на 200 HP через run(), дополнительно)
#                                                 test_ui_fight_ends_with_victory_and_xp,
#                                                 test_ui_level_up_menu_after_victory
#   «лог бросков, варианты ответа» (ТЗ 13, 6, 10)  test_ui_fight_log_has_rolls_in_tz6_format
#   вывод без дублей, [бросок] только у бросков ... test_cli_start_of_combat_prints_each_line_once,
#                                                    test_cli_roll_prefix_is_only_on_rolls
#   «учёт стоимости (2.0)», строка состояния ...... test_cli_status_line_shows_session_cost
#   «журнал вызовов модели (11)» ................... test_cli_writes_journal_and_costs
#   id мира при старте ............................. test_cli_prints_world_id_at_start
#   автосейв на границе сцены ...................... test_cli_honest_win_makes_auto_save,
#                                                    test_ui_victory_creates_auto_save
#   повторный запуск `--world <id>` с того же места  test_cli_world_resumes_from_auto_save,
#     (на честном CLI-прогоне)                       test_cli_world_resume_continues_the_story
#   `--replay` воспроизводит бандл (ТЗ 11) ......... test_cli_replay_reproduces_narration_and_rolls,
#                                                    test_cli_replay_of_honest_win_gives_victory
#   replay не меняет живой мир ..................... test_cli_replay_leaves_live_world_untouched
#   детерминизм по сиду (ТЗ 13, тестирование ИИ) ... test_cli_same_seed_same_output,
#                                                    test_ui_same_seed_same_fight_output
#   ключи (ТЗ 11) .................................. test_cli_without_key_explains_and_fails
# Не покрыто: «живая сцена с Claude и Gemini играется вручную» -- чек-лист, не автотест.
#
# Честная победа: HONEST_SEED подобран скриптом tests/scenarios/find_honest_seed.py. Бой реактивный
# (число ходов зависит от бросков), Арн на 12 HP может проиграть, поэтому нужен сид с победой.
# Тесты на run() с героем на 200 HP (victory()) остаются как дополнительные.
#
# Параметры main() (stdin / stdout / env / mock_factory) и контракт ui -- tests/unit/ui/ui_kit.py.
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "unit" / "ui"))

from slots_kit import list_slots  # noqa: E402
from ui_kit import (  # noqa: E402
    DESCEND,
    SEED,
    TALK,
    WORLD,
    FightInput,
    PlainOutput,
    ReactiveAdapter,
    ScriptThenReactive,
    build_app,
    cli,
    numbered_lines,
    player_action_input,
    scripted_from_yaml,
)

from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.ui.cli import main  # noqa: E402

SCRIPT = Path(__file__).resolve().parents[1] / "fixtures" / "scripts" / "talk_check_fight.yaml"
KICK = "Опрокидываю бочку на ближнего гоблина"
IMPROVISE = {
    "skill": "athletics", "category": "medium", "effect": "prone", "target": "goblin_1",
    "zone": "",
}
INPUTS = [TALK, "1", DESCEND, "/quit"]
# подобран; при изменении правил подобрать заново:
#   uv run python tests/scenarios/find_honest_seed.py 1 200
HONEST_SEED = 156  # К1: 57 больше не победа (лук гоблина без помехи «дальность»)
NARRATION = [
    "в подвале «Хромого гуся» что-то возится",
    "Трактирщик вздыхает и кивает на дверь в подвал.",
    "Из темноты выскакивают гоблины, а за бочками ухмыляется Гракх.",
]


def scene_argv(root, seed=SEED):
    return [
        "--new", "--hero", "arn", "--seed", str(seed), "--mock", str(SCRIPT), "--saves", str(root),
    ]


def play_scene(root, seed=SEED):
    return cli(scene_argv(root, seed), INPUTS, env={})


def world_id_of(root):
    ids = [p.name for p in Path(root).iterdir() if p.is_dir()]
    assert len(ids) == 1
    return ids[0]


def index_of(out, part):
    for i, line in enumerate(out.lines):
        if part in line:
            return i
    raise AssertionError(f"нет строки с {part!r}")


def victory(registry, root, seed=SEED):
    from ai_dm.ui.simple import run

    adapter = ScriptThenReactive(
        scripted_from_yaml("talk_check_fight.yaml"),
        ReactiveAdapter(classify=[player_action_input([], improvise=IMPROVISE)]),
    )
    app = build_app(registry, root, adapter, seed=seed, hp=200)
    out = PlainOutput()
    run(app, FightInput(out, [TALK, "1", DESCEND, KICK]), out)
    return app, out


class HonestInput(FightInput):
    # как FightInput, но после выбора «среднее значение HP» в меню уровня -- /quit
    def __init__(self, out, first, limit=100):
        super().__init__(out, first, limit)
        self.leveled = False

    def read(self, prompt=""):
        if self.leveled:
            return "/quit"
        options = numbered_lines(self.out.lines[self.seen:])
        answer = super().read(prompt)
        for number, text in options:
            if answer == str(number) and "средн" in text.lower():
                self.leveled = True
        return answer


def honest_run(root, seed=HONEST_SEED):
    out = PlainOutput()

    def factory(path):
        return ScriptThenReactive(scripted_from_yaml("talk_check_fight.yaml"), ReactiveAdapter())

    stdin = HonestInput(out, [TALK, "1", DESCEND])
    code = main(scene_argv(root, seed), stdin=stdin, stdout=out, env={}, mock_factory=factory)
    return code, out


# разговор -> проверка -> бой через main()

def test_cli_scene_exits_with_zero(tmp_path):
    code, _ = play_scene(tmp_path / "saves")
    assert code == 0


def test_cli_prints_narration_of_all_three_turns(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    for part in NARRATION:
        assert part in out.text


def test_cli_prints_numbered_choices(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    assert "1. Спросить про подвал" in out.lines
    assert "2. Заказать эль" in out.lines


def test_cli_prints_roll_line_with_dc_15(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    rolls = [line for line in out.lines if line.startswith("[бросок] ")]
    assert any(re.search(r"d20 \(\d+\).* = \d+ против СЛ 15 → ", line) for line in rolls)


def test_cli_enters_combat_and_lists_actions(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    assert "Бой начался" in out.text
    last = out.lines.index("Бой начался")
    actions = numbered_lines(out.lines[last:])
    block = []
    for number, text in actions:
        if number != len(block) + 1:
            break
        block.append(text)
    assert actions[0][0] == 1
    texts = block
    assert any(text.startswith("Атака:") for text in texts)
    assert texts[-1] == "Закончить ход"


def test_cli_output_goes_in_scene_order(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    order = [
        index_of(out, NARRATION[0]),
        index_of(out, "против СЛ 15"),
        index_of(out, NARRATION[1]),
        index_of(out, "Бой начался"),
        index_of(out, NARRATION[2]),
    ]
    assert order == sorted(order)


def test_cli_status_line_shows_session_cost(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    costs = [
        float(m.group(1)) for m in (re.search(r"сессия \$(\d+\.\d+)$", line) for line in out.lines)
        if m
    ]
    assert costs[0] == 0
    assert costs[-1] > 0
    assert costs == sorted(costs)


def test_cli_writes_journal_and_costs(tmp_path):
    root = tmp_path / "saves"
    play_scene(root)
    folder = root / world_id_of(root)
    assert list((folder / "journal").iterdir())
    assert (folder / "meta" / "costs.jsonl").is_file()


def test_cli_same_seed_same_output(tmp_path):
    _, one = play_scene(tmp_path / "one")
    _, two = play_scene(tmp_path / "two")
    one_text = one.text.replace(world_id_of(tmp_path / "one"), "<world>")
    two_text = two.text.replace(world_id_of(tmp_path / "two"), "<world>")
    assert one_text == two_text


def test_cli_without_key_explains_and_fails(tmp_path):
    argv = ["--new", "--hero", "arn", "--saves", str(tmp_path)]
    code, out = cli(argv, [TALK], env={}, dotenv_path=tmp_path / "no.env")
    assert code != 0
    assert "GEMINI_API_KEY" in out.text


# replay

def replay_argv(root, world, seed=SEED):
    return ["--replay", "--world", world, "--hero", "arn", "--seed", str(seed),
            "--saves", str(root)]


def snapshot(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(Path(folder).rglob("*")) if p.is_file()
    }


def test_cli_replay_reproduces_narration_and_rolls(tmp_path):
    live = tmp_path / "live"
    _, one = play_scene(live)
    world = world_id_of(live)
    code, two = cli(replay_argv(live, world), INPUTS, env={})
    assert code == 0
    rolls_one = [line for line in one.lines if line.startswith("[бросок] ")]
    rolls_two = [line for line in two.lines if line.startswith("[бросок] ")]
    assert rolls_one
    assert rolls_one == rolls_two
    for part in NARRATION:
        assert part in two.text
    assert "Бой начался" in two.text


def test_cli_replay_leaves_live_world_untouched(tmp_path):
    live = tmp_path / "live"
    play_scene(live)
    world = world_id_of(live)
    before = snapshot(live / world)
    for _ in range(2):
        code, _ = cli(replay_argv(live, world), INPUTS, env={})
        assert code == 0
        assert snapshot(live / world) == before


def test_cli_replay_of_honest_win_gives_victory(tmp_path):
    root = tmp_path / "saves"
    _, one = honest_run(root)
    world = world_id_of(root)
    before = snapshot(root / world)
    two = PlainOutput()
    code = main(replay_argv(root, world, HONEST_SEED), stdin=HonestInput(two, [TALK, "1", DESCEND]),
                stdout=two, env={})
    assert code == 0
    assert any("победа" in line.lower() for line in two.lines)
    rolls_one = [line for line in one.lines if line.startswith("[бросок] ")]
    assert rolls_one == [line for line in two.lines if line.startswith("[бросок] ")]
    assert snapshot(root / world) == before


# id мира при старте и дубли в выводе

def test_cli_prints_world_id_at_start(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    world = world_id_of(tmp_path / "saves")
    assert f"Мир: {world}, сид 3 (продолжить: ai-dm --world {world})" in out.lines


def test_cli_start_of_combat_prints_each_line_once(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    initiative = [line for line in out.lines if "инициатива" in line]
    assert initiative
    assert len(initiative) == len(set(initiative))
    assert out.lines.count("Бой начался") == 1


def test_cli_roll_prefix_is_only_on_rolls(tmp_path):
    _, out = play_scene(tmp_path / "saves")
    assert "[бросок] Бой начался" not in out.lines
    assert not [line for line in out.lines if line.startswith("[бросок] Мир")]
    assert "Действие игрока" not in out.text
    assert "Варианты ответа предложены" not in out.text


# честная победа через main()

def test_cli_honest_win_goes_through_the_whole_scene(tmp_path):
    code, out = honest_run(tmp_path / "saves")
    assert code == 0
    order = [
        index_of(out, NARRATION[0]),
        index_of(out, "против СЛ 15"),
        index_of(out, NARRATION[1]),
        index_of(out, "Бой начался"),
        index_of(out, NARRATION[2]),
        index_of(out, "победа"),
    ]
    assert order == sorted(order)
    menu = [i for i, line in enumerate(out.lines) if "средн" in line.lower()]
    assert menu
    assert menu[0] > order[-1]


def test_cli_honest_win_prints_victory_and_xp(tmp_path):
    _, out = honest_run(tmp_path / "saves")
    assert any("победа" in line.lower() for line in out.lines)
    assert any("опыт" in line.lower() and "300" in line for line in out.lines)


def test_cli_honest_win_opens_level_up_menu(tmp_path):
    _, out = honest_run(tmp_path / "saves")
    texts = [text.lower() for _, text in numbered_lines(out.lines)]
    assert any("средн" in text for text in texts)
    assert any("бросок" in text for text in texts)


def test_cli_honest_win_makes_auto_save(tmp_path):
    root = tmp_path / "saves"
    honest_run(root)
    world = world_id_of(root)
    assert "auto" in list_slots(root, world)
    saved = load_slot(root, world, "auto")
    assert saved.session.active_combat is None
    assert saved.heroes[0].sheet.xp == 300


# бой до победы через run()

def test_ui_fight_ends_with_victory_and_xp(registry, tmp_path):
    app, out = victory(registry, tmp_path)
    assert app.bundle.session.active_combat is None
    assert any("победа" in line.lower() for line in out.lines)
    assert any("опыт" in line.lower() and "300" in line for line in out.lines)
    assert app.bundle.heroes[0].sheet.xp == 300


def test_ui_fight_log_has_rolls_in_tz6_format(registry, tmp_path):
    _, out = victory(registry, tmp_path)
    assert re.search(r"d20 \(\d+.*\) \+ \d+ .*= \d+ против КД \d+ → ", " ".join(out.lines))
    assert any("импровизация (Лежит)" in line for line in out.lines)


def test_ui_fight_actions_are_listed_every_turn_until_the_end(registry, tmp_path):
    _, out = victory(registry, tmp_path)
    ends = [n for n, text in numbered_lines(out.lines) if text == "Закончить ход"]
    assert len(ends) >= 3


def test_ui_level_up_menu_after_victory(registry, tmp_path):
    app, out = victory(registry, tmp_path)
    texts = [text.lower() for _, text in numbered_lines(out.lines)]
    assert any("средн" in text for text in texts)
    assert any("бросок" in text for text in texts)
    assert app.bundle.heroes[0].sheet.level == 2
    assert app.pending is None


def test_ui_victory_creates_auto_save(registry, tmp_path):
    app, _ = victory(registry, tmp_path)
    assert "auto" in list_slots(tmp_path, WORLD)
    saved = load_slot(tmp_path, WORLD, "auto")
    assert saved.session.active_combat is None
    assert saved.heroes[0].sheet.xp == 300


def test_ui_same_seed_same_fight_output(registry, tmp_path):
    _, one = victory(registry, tmp_path / "one")
    _, two = victory(registry, tmp_path / "two")
    assert one.lines == two.lines


# повторный запуск на честном CLI-прогоне

def resume_argv(root, world):
    return ["--world", world, "--mock", str(SCRIPT), "--saves", str(root)]


def test_cli_world_resumes_from_auto_save(tmp_path):
    root = tmp_path / "saves"
    honest_run(root)
    world = world_id_of(root)
    saved = load_slot(root, world, "auto")
    hero = saved.heroes[0]
    code, out = cli(
        resume_argv(root, world), [], env={}, mock_factory=lambda path: ReactiveAdapter()
    )
    assert code == 0
    first = next(line for line in out.lines if line.startswith("HP "))
    assert first.startswith(f"HP {hero.creature.hp_current}/{hero.creature.hp_max} · ")
    assert saved.world.clock.to_date() in first


def test_cli_world_resume_continues_the_story(tmp_path):
    root = tmp_path / "saves"
    honest_run(root)
    world = world_id_of(root)
    code, out = cli(
        resume_argv(root, world), ["Осматриваюсь"], env={},
        mock_factory=lambda path: ReactiveAdapter(),
    )
    assert code == 0
    assert "Рассказ." in out.text
    assert "Спрашиваю" not in out.text


def test_cli_world_resume_shows_last_narration_before_menu(tmp_path):
    root = tmp_path / "saves"
    honest_run(root)
    world = world_id_of(root)
    last = load_slot(root, world, "auto").memory.recent_turns[-1].narration
    code, out = cli(
        resume_argv(root, world), [], env={}, mock_factory=lambda path: ReactiveAdapter()
    )
    assert code == 0
    assert last
    first_words = " ".join(last.split()[:4])
    assert first_words in out.text
    assert out.text.index(first_words) < out.text.index("HP ")
