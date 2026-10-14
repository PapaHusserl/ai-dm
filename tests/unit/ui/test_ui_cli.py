# Ожидаемый API: ai_dm.ui.cli.main -- контракт в ui_kit.py (параметры stdin / stdout / env /
# dotenv_path / mock_factory вместо настоящих stdin, окружения и сети).
# Живых вызовов нет: --mock (YAML-сценарий), ключи -- словари env.
import tomllib
from pathlib import Path

import pytest
from slots_kit import list_slots
from ui_kit import (
    DESCEND,
    NUMBERED,
    OPUS,
    SEED,
    TALK,
    WORLD,
    ReactiveAdapter,
    cli,
    numbered_lines,
    text_app,
    text_step,
    write_script,
)

from ai_dm.llm.mock import ScriptedAdapter
from ai_dm.persistence.store import load_slot

SCRIPTS = Path(__file__).resolve().parents[2] / "fixtures" / "scripts"
PYPROJECT = Path(__file__).resolve().parents[3] / "pyproject.toml"
BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]


def mock_args(tmp_path, text="Трактирщик кивает."):
    script = write_script(tmp_path / "one.yaml", text)
    return ["--mock", str(script), "--saves", str(tmp_path / "saves")]


def world_dirs(root):
    return sorted(p.name for p in Path(root).iterdir() if p.is_dir())


# точка входа

def test_pyproject_declares_ai_dm_script():
    data = tomllib.loads(PYPROJECT.read_text(encoding="utf-8"))
    assert data["project"]["scripts"]["ai-dm"] == "ai_dm.ui.cli:main"


# ключи

def test_without_key_and_mock_explains_and_exits_with_error(tmp_path):
    code, out = cli(BASE + ["--saves", str(tmp_path)], env={}, dotenv_path=tmp_path / "no.env")
    assert code != 0
    assert "GEMINI_API_KEY" in out.text
    assert ".env" in out.text


def test_without_key_nothing_is_created(tmp_path):
    cli(BASE + ["--saves", str(tmp_path / "saves")], env={}, dotenv_path=tmp_path / "no.env")
    assert not (tmp_path / "saves").exists() or world_dirs(tmp_path / "saves") == []


def test_key_from_env_is_enough_and_is_not_printed(tmp_path):
    env = {"ANTHROPIC_API_KEY": "sk-test-secret"}
    code, out = cli(BASE + ["--saves", str(tmp_path)], env=env, dotenv_path=tmp_path / "no.env")
    assert code == 0
    assert "sk-test-secret" not in out.text


def test_key_from_dotenv_is_enough(tmp_path):
    dotenv = tmp_path / ".env"
    dotenv.write_text("ANTHROPIC_API_KEY=sk-from-file\n", encoding="utf-8")
    code, out = cli(BASE + ["--saves", str(tmp_path / "saves")], env={}, dotenv_path=dotenv)
    assert code == 0
    assert "sk-from-file" not in out.text


def test_mock_needs_no_key(tmp_path):
    code, out = cli(BASE + mock_args(tmp_path), ["/quit"], env={})
    assert code == 0
    assert "ANTHROPIC_API_KEY" not in out.text


def test_missing_mock_script_is_a_message_not_a_traceback(tmp_path):
    argv = BASE + ["--mock", str(tmp_path / "nope.yaml"), "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, env={})
    assert code != 0
    assert out.lines


# новый мир, герой, сид, сейвы

def test_new_world_plays_a_turn_through_the_mock(tmp_path):
    code, out = cli(BASE + mock_args(tmp_path), ["Здравствуйте", "/quit"], env={})
    assert code == 0
    assert "Трактирщик кивает." in out.text


def test_new_world_goes_to_the_saves_dir(tmp_path):
    cli(BASE + mock_args(tmp_path), ["Здравствуйте"], env={})
    dirs = world_dirs(tmp_path / "saves")
    assert len(dirs) == 1
    assert (tmp_path / "saves" / dirs[0] / "journal").is_dir()


def test_default_saves_dir_is_saves_in_current_dir(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    script = write_script(tmp_path / "one.yaml")
    code, _ = cli(BASE + ["--mock", str(script)], ["Здравствуйте"], env={})
    assert code == 0
    assert len(world_dirs(tmp_path / "saves")) == 1


def test_two_new_worlds_get_different_ids(tmp_path):
    cli(BASE + mock_args(tmp_path), ["Здравствуйте"], env={})
    cli(BASE + mock_args(tmp_path), ["Здравствуйте"], env={})
    assert len(world_dirs(tmp_path / "saves")) == 2


def test_hero_arn_is_the_fighter(tmp_path):
    _, out = cli(BASE + mock_args(tmp_path), ["/sheet"], env={})
    assert "Арн" in out.text


def test_hero_liel_is_the_wizard(tmp_path):
    argv = ["--new", "--hero", "liel", "--seed", "3"] + mock_args(tmp_path)
    _, out = cli(argv, ["/sheet"], env={})
    assert "Лиэль" in out.text
    assert "Арн" not in out.text


def test_hero_grey_is_the_ranger(tmp_path):
    argv = ["--new", "--hero", "grey", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["/sheet"], env={})
    assert code == 0
    assert "Грей" in out.text
    assert "Арн" not in out.text


def test_unknown_hero_is_rejected(tmp_path):
    argv = ["--new", "--hero", "zzz"] + mock_args(tmp_path)
    code, _ = cli(argv, env={})
    assert code != 0


def test_without_hero_flag_asks_at_start(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["2", "1", "1", "/sheet"], env={})
    assert code == 0
    texts = [text for _, text in numbered_lines(out.lines)]
    assert any("Арн" in text for text in texts)
    assert any("Лиэль" in text for text in texts)
    last_menu_line = max(i for i, line in enumerate(out.lines) if NUMBERED.match(line))
    assert "Лиэль" in "\n".join(out.lines[last_menu_line + 1:])
    assert "Арн" not in "\n".join(out.lines[last_menu_line + 1:])


def test_seed_sets_the_rolls(tmp_path):
    steps = (SCRIPTS / "talk_check_fight.yaml")
    argv = ["--new", "--hero", "arn", "--seed", "3", "--mock", str(steps),
            "--saves", str(tmp_path / "saves")]
    _, out = cli(argv, [TALK, "1", "Спускаюсь"], env={})
    assert "Арн: инициатива d20 (9) + 1 = 10" in out.text


def test_other_seed_gives_other_rolls(tmp_path):
    steps = (SCRIPTS / "talk_check_fight.yaml")
    argv = ["--new", "--hero", "arn", "--seed", "2", "--mock", str(steps),
            "--saves", str(tmp_path / "saves")]
    _, out = cli(argv, [TALK, "1", "Спускаюсь"], env={})
    assert "Арн: инициатива d20 (14) + 1 = 15" in out.text


def test_mock_factory_replaces_the_scripted_adapter(tmp_path):
    seen = []

    def factory(path):
        seen.append(path)
        return ScriptedAdapter([text_step("Из фабрики.")], provider="anthropic", model=OPUS)

    _, out = cli(BASE + mock_args(tmp_path), ["Привет"], env={}, mock_factory=factory)
    assert len(seen) == 1
    assert str(seen[0]).endswith("one.yaml")
    assert "Из фабрики." in out.text


# продолжить мир

def saved_world(registry, root):
    app = text_app(registry, root, [text_step()])
    app.bundle.heroes[0].creature.hp_current = 7
    app.save_current("auto")
    return app


def test_world_flag_continues_from_auto_slot(registry, tmp_path):
    root = tmp_path / "saves"
    saved_world(registry, root)
    argv = ["--world", WORLD, "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(root)]
    code, out = cli(argv, ["/sheet"], env={})
    assert code == 0
    assert any(line.startswith("HP 7/12") for line in out.lines)


def test_world_flag_continues_the_story(registry, tmp_path):
    root = tmp_path / "saves"
    saved_world(registry, root)
    script = write_script(tmp_path / "s.yaml", "Продолжение.")
    argv = ["--world", WORLD, "--mock", str(script), "--saves", str(root)]
    _, out = cli(argv, ["Иду дальше"], env={})
    assert "Продолжение." in out.text
    assert load_slot(root, WORLD, "auto").heroes[0].creature.hp_current == 7


def test_unknown_world_is_a_message_and_error_code(tmp_path):
    argv = ["--world", "no-such-world", "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, env={})
    assert code != 0
    assert "no-such-world" in out.text


def test_replay_without_world_is_an_error(tmp_path):
    code, out = cli(["--replay", "--saves", str(tmp_path)], env={})
    assert code != 0
    assert out.lines


# --mock / --replay не берут сохранённую модель (D4 stage2-batch5-review)

def test_mock_ignores_stored_model(registry, tmp_path):
    root = tmp_path / "saves"
    saved_world(registry, root)
    meta = root / WORLD / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "models.json").write_text(
        '{"narrator": {"provider": "anthropic", "model": "claude-sonnet-5-5"}}', encoding="utf-8"
    )
    made = []

    def factory(path):
        made.append(path)
        return ReactiveAdapter()

    argv = ["--world", WORLD, "--mock", "any.yaml", "--saves", str(root)]
    code, out = cli(argv, ["/quit"], env={}, mock_factory=factory)
    assert code == 0
    assert "Сохранённая модель не подключена" not in out.text
    assert len(made) == 1


# общие помощники партии 6: живой прогон сцены и снимок папки мира

SCENE = SCRIPTS / "talk_check_fight.yaml"
SCENE_INPUTS = [TALK, "1", DESCEND, "/quit"]


def scene_argv(root, extra=()):
    return ["--new", "--hero", "arn", "--seed", str(SEED), "--mock", str(SCENE),
            "--saves", str(root), *extra]


def live_scene(root):
    code, out = cli(scene_argv(root), SCENE_INPUTS, env={})
    assert code == 0
    return world_dirs(root)[0], out


def replay_argv(root, world, extra=()):
    return ["--replay", "--world", world, "--hero", "arn", "--seed", str(SEED),
            "--saves", str(root), *extra]


def snapshot(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(Path(folder).rglob("*")) if p.is_file()
    }


# B1: replay не меняет живой мир

def test_replay_twice_leaves_the_live_world_untouched(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    before = snapshot(root / world)
    for _ in range(2):
        code, _ = cli(replay_argv(root, world), SCENE_INPUTS, env={})
        assert code == 0
        assert snapshot(root / world) == before


def test_replay_keeps_journal_costs_and_slots_of_the_live_world(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    before = snapshot(root / world)
    cli(replay_argv(root, world), SCENE_INPUTS, env={})
    after = snapshot(root / world)
    for part in ("journal", "meta", "slots"):
        kept = {k: v for k, v in before.items() if k.startswith(part)}
        assert kept
        assert {k: v for k, v in after.items() if k.startswith(part)} == kept


def test_replay_prints_the_temp_dir_in_one_line(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    _, out = cli(replay_argv(root, world), SCENE_INPUTS, env={})
    lines = [line for line in out.lines if "ai-dm-replay-" in line]
    assert len(lines) == 1


def test_replay_does_not_create_new_worlds_in_saves(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    cli(replay_argv(root, world), SCENE_INPUTS, env={})
    assert world_dirs(root) == [world]


# B2: replay требует --seed и --hero; пустой журнал

def test_replay_without_seed_is_an_error_with_code_2(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    argv = ["--replay", "--world", world, "--hero", "arn", "--saves", str(root)]
    code, out = cli(argv, env={})
    assert code == 2
    assert "--seed" in out.text


def test_replay_without_hero_is_an_error_with_code_2(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    argv = ["--replay", "--world", world, "--seed", str(SEED), "--saves", str(root)]
    code, out = cli(argv, env={})
    assert code == 2
    assert "--hero" in out.text


def test_replay_of_empty_journal_says_so_and_exits_with_1(tmp_path):
    root = tmp_path / "saves"
    (root / "empty-w" / "journal").mkdir(parents=True)
    code, out = cli(replay_argv(root, "empty-w"), env={})
    assert code == 1
    assert "Журнал мира empty-w пуст" in out.text


def test_replay_of_empty_journal_creates_no_world(tmp_path):
    root = tmp_path / "saves"
    (root / "empty-w" / "journal").mkdir(parents=True)
    cli(replay_argv(root, "empty-w"), env={})
    assert not (root / "empty-w" / "slots").exists()
    assert world_dirs(root) == ["empty-w"]


# B3: --new с существующим id

def test_new_with_existing_world_id_is_refused(tmp_path):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    before = snapshot(root / world)
    argv = ["--new", "--world", world, "--hero", "arn", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["Здравствуйте"], env={})
    assert code == 1
    assert f"Мир {world} уже есть" in out.text
    assert f"ai-dm --world {world}" in out.text
    assert snapshot(root / world) == before


def test_new_with_free_world_id_is_created(tmp_path):
    argv = ["--new", "--world", "free-id", "--hero", "arn", "--seed", "3"] + mock_args(tmp_path)
    code, _ = cli(argv, ["/quit"], env={})
    assert code == 0
    assert world_dirs(tmp_path / "saves") == ["free-id"]


# B6: id мира при старте

def test_new_world_id_is_printed_at_start(tmp_path):
    cli(BASE + mock_args(tmp_path), ["/quit"], env={})
    world = world_dirs(tmp_path / "saves")[0]
    _, out = cli(["--world", world, "--mock", str(tmp_path / "one.yaml"),
                  "--saves", str(tmp_path / "saves")], ["/quit"], env={})
    assert f"Мир: {world} (продолжить: ai-dm --world {world})" in out.lines


def test_new_world_with_own_id_prints_it(tmp_path):
    argv = ["--new", "--world", "my-id", "--hero", "arn", "--seed", "3"] + mock_args(tmp_path)
    _, out = cli(argv, ["/quit"], env={})
    assert world_line(out, "my-id")


def world_line(out, world):
    lines = [line for line in out.lines if line.startswith(f"Мир: {world}")]
    return lines[0] if lines else None


def test_world_id_line_is_before_the_status_line(tmp_path):
    argv = ["--new", "--world", "my-id", "--hero", "arn", "--seed", "3"] + mock_args(tmp_path)
    _, out = cli(argv, ["/quit"], env={})
    first_status = next(i for i, line in enumerate(out.lines) if line.startswith("HP "))
    assert out.lines.index(world_line(out, "my-id")) < first_status


# T4: сид нового мира печатается рядом с id мира

def test_new_world_prints_seed_next_to_id(tmp_path):
    argv = ["--new", "--world", "my-id", "--hero", "arn", "--seed", "3"] + mock_args(tmp_path)
    _, out = cli(argv, ["/quit"], env={})
    line = world_line(out, "my-id")
    assert "сид 3" in line
    assert "ai-dm --world my-id" in line


def test_new_world_without_seed_prints_the_random_seed_it_used(tmp_path):
    argv = ["--new", "--world", "my-id", "--hero", "arn"] + mock_args(tmp_path)
    _, out = cli(argv, ["/quit"], env={})
    seed = load_slot(tmp_path / "saves", "my-id", "auto").world.rng.seed
    assert f"сид {seed}" in world_line(out, "my-id")


# D1: начальный автосейв

def test_new_world_makes_initial_auto_save(tmp_path):
    cli(BASE + mock_args(tmp_path), ["/quit"], env={})
    world = world_dirs(tmp_path / "saves")[0]
    assert "auto" in list_slots(tmp_path / "saves", world)


def test_world_flag_continues_after_new_and_quit(tmp_path):
    cli(BASE + mock_args(tmp_path), ["/quit"], env={})
    world = world_dirs(tmp_path / "saves")[0]
    code, out = cli(["--world", world, "--mock", str(tmp_path / "one.yaml"),
                     "--saves", str(tmp_path / "saves")], ["/quit"], env={})
    assert code == 0
    assert "HP 12/12" in out.text


def test_world_without_auto_save_says_so(tmp_path):
    (tmp_path / "saves" / "bare" / "journal").mkdir(parents=True)
    argv = ["--world", "bare", "--mock", str(write_script(tmp_path / "s.yaml")),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, env={})
    assert code == 1
    assert "нет автосохранения мира bare" in out.text.lower()


# D2: исключение посреди хода

def break_first_handle(monkeypatch):
    from ai_dm.game.app import GameApp

    original = GameApp.handle
    calls = []

    def broken(self, line):
        calls.append(line)
        if len(calls) == 1:
            raise RuntimeError("сломалось")
        return original(self, line)

    monkeypatch.setattr(GameApp, "handle", broken)


def test_live_error_in_turn_is_printed_and_loop_goes_on(tmp_path, monkeypatch):
    break_first_handle(monkeypatch)
    argv = BASE + mock_args(tmp_path, "После ошибки.")
    code, out = cli(argv, ["Первое", "Второе"], env={})
    assert code == 0
    assert "Ошибка хода: сломалось" in out.text
    assert "После ошибки." in out.text


def test_live_error_in_turn_hides_the_key(tmp_path, monkeypatch):
    from ai_dm.game.app import GameApp

    def broken(self, line):
        raise RuntimeError("плохой ключ sk-secret-1")

    monkeypatch.setattr(GameApp, "handle", broken)
    env = {"ANTHROPIC_API_KEY": "sk-secret-1"}
    code, out = cli(BASE + mock_args(tmp_path), ["Первое"], env=env)
    assert code == 0
    assert "Ошибка хода" in out.text
    assert "sk-secret-1" not in out.text


def test_error_in_turn_of_replay_ends_with_code_1(tmp_path, monkeypatch):
    root = tmp_path / "saves"
    world, _ = live_scene(root)
    break_first_handle(monkeypatch)
    code, out = cli(replay_argv(root, world), SCENE_INPUTS, env={})
    assert code == 1
    assert "сломалось" in out.text


# D6: ключи не попадают в вывод, Ctrl-C

def test_error_message_from_factory_hides_the_key(tmp_path):
    def factory(path):
        raise RuntimeError(f"bad {'sk-secret-2'}")

    env = {"ANTHROPIC_API_KEY": "sk-secret-2"}
    code, out = cli(BASE + mock_args(tmp_path), env=env, mock_factory=factory)
    assert code != 0
    assert "***" in out.text
    assert "sk-secret-2" not in out.text


def test_error_message_from_factory_hides_the_gemini_key(tmp_path):
    def factory(path):
        raise RuntimeError("bad sk-gemini-3")

    env = {"GEMINI_API_KEY": "sk-gemini-3"}
    code, out = cli(BASE + mock_args(tmp_path), env=env, mock_factory=factory)
    assert code != 0
    assert "sk-gemini-3" not in out.text


def test_ctrl_c_ends_with_code_130(tmp_path):
    def factory(path):
        raise KeyboardInterrupt

    code, out = cli(BASE + mock_args(tmp_path), env={}, mock_factory=factory)
    assert code == 130
    assert out.lines


def test_unreadable_dotenv_is_a_message_not_a_traceback(tmp_path):
    code, out = cli(BASE + ["--saves", str(tmp_path / "saves")], env={}, dotenv_path=tmp_path)
    assert code != 0
    assert out.lines


# D7: --hero / --seed только с --new

@pytest.mark.parametrize("flags", [["--hero", "arn"], ["--seed", "3"]])
def test_hero_or_seed_with_world_without_new_is_an_error(tmp_path, flags):
    argv = ["--world", "some", *flags] + mock_args(tmp_path)
    code, out = cli(argv, env={})
    assert code == 2
    assert out.lines


# D8: ask_hero переспрашивает

def test_hero_menu_has_three_items_with_grey_last(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    _, out = cli(argv, ["3", "1", "1", "/sheet"], env={})
    texts = [text for _, text in numbered_lines(out.lines)]
    assert any("Грей" in text for text in texts)


def test_menu_item_3_is_grey(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["3", "1", "1", "/sheet"], env={})
    assert code == 0
    last_menu_line = max(i for i, line in enumerate(out.lines) if NUMBERED.match(line))
    after = "\n".join(out.lines[last_menu_line + 1:])
    assert "Грей" in after
    assert "Арн" not in after
    assert "Лиэль" not in after


def test_menu_item_6_is_asked_again(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["6", "3", "1", "1", "/sheet"], env={})
    assert code == 0
    assert "Герой не выбран" not in out.text
    assert "Грей" in out.text.split("/sheet")[-1]


def test_ask_hero_asks_again_on_wrong_answer(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["9", "ерунда", "2", "1", "/sheet"], env={})
    assert code == 0
    assert "Герой не выбран" not in out.text
    assert "Лиэль" in out.text.split("/sheet")[-1]


def test_ask_hero_ends_when_input_ends(tmp_path):
    argv = ["--new", "--seed", "3"] + mock_args(tmp_path)
    code, out = cli(argv, ["9"], env={})
    assert code == 1
    assert "Герой не выбран" in out.text


# E1: старт только с ключом Gemini, --provider, мир под Gemini без ключа Anthropic

GEMINI = ("gemini", "gemini-3.8-flash")
ANTHROPIC = ("anthropic", OPUS)
BOTH = {"ANTHROPIC_API_KEY": "sk-a", "GEMINI_API_KEY": "sk-g"}
NO_ENV = {"dotenv_path": Path("/nonexistent/.env")}


class FactorySpyCli:
    def __init__(self):
        self.calls = []

    def __call__(self, provider, model, app_cfg, **kwargs):
        self.calls.append((provider, model))
        return ReactiveAdapter(provider=provider, model=model)


def spy_adapters(monkeypatch):
    spy = FactorySpyCli()
    monkeypatch.setattr("ai_dm.ui.cli.make_adapter", spy)
    return spy


def test_only_gemini_key_starts_with_gemini_profile(tmp_path, monkeypatch):
    spy = spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["/quit"], env={"GEMINI_API_KEY": "sk-g"}, **NO_ENV)
    assert code == 0
    assert spy.calls[0] == GEMINI
    assert "Ошибка" not in out.text


def test_only_gemini_key_needs_no_profile_message(tmp_path, monkeypatch):
    spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    _, out = cli(argv, ["/quit"], env={"GEMINI_API_KEY": "sk-g"}, **NO_ENV)
    assert "беру профиль" not in out.text


def test_only_anthropic_key_starts_with_anthropic_profile(tmp_path, monkeypatch):
    spy = spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["/quit"], env={"ANTHROPIC_API_KEY": "sk-a"}, **NO_ENV)
    assert code == 0
    assert spy.calls[0] == ANTHROPIC
    assert "Ошибка" not in out.text


def test_only_anthropic_key_says_which_profile_is_used(tmp_path, monkeypatch):
    spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    _, out = cli(argv, ["/quit"], env={"ANTHROPIC_API_KEY": "sk-a"}, **NO_ENV)
    assert any("anthropic" in line.lower() for line in out.lines)


def test_only_anthropic_key_does_not_leak_the_key(tmp_path, monkeypatch):
    spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    _, out = cli(argv, ["/quit"], env={"ANTHROPIC_API_KEY": "sk-a-secret"}, **NO_ENV)
    assert "sk-a-secret" not in out.text


def test_only_gemini_key_does_not_leak_the_key(tmp_path, monkeypatch):
    spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    _, out = cli(argv, ["/quit"], env={"GEMINI_API_KEY": "sk-g-secret"}, **NO_ENV)
    assert "sk-g-secret" not in out.text


def test_both_keys_without_flag_use_gemini(tmp_path, monkeypatch):
    spy = spy_adapters(monkeypatch)
    argv = BASE + ["--saves", str(tmp_path / "saves")]
    cli(argv, ["/quit"], env=BOTH, **NO_ENV)
    assert spy.calls[0] == GEMINI


def test_provider_gemini_with_both_keys_uses_gemini(tmp_path, monkeypatch):
    spy = spy_adapters(monkeypatch)
    argv = BASE + ["--provider", "gemini", "--saves", str(tmp_path / "saves")]
    code, _ = cli(argv, ["/quit"], env=BOTH, **NO_ENV)
    assert code == 0
    assert spy.calls[0] == GEMINI


def test_provider_anthropic_with_both_keys_uses_anthropic(tmp_path, monkeypatch):
    spy = spy_adapters(monkeypatch)
    argv = BASE + ["--provider", "anthropic", "--saves", str(tmp_path / "saves")]
    cli(argv, ["/quit"], env=BOTH, **NO_ENV)
    assert spy.calls[0] == ANTHROPIC


def test_provider_gemini_without_its_key_names_the_variable(tmp_path):
    argv = BASE + ["--provider", "gemini", "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, env={"ANTHROPIC_API_KEY": "sk-a"}, **NO_ENV)
    assert code != 0
    assert "GEMINI_API_KEY" in out.text


def test_unknown_provider_is_rejected(tmp_path):
    argv = BASE + ["--provider", "openai", "--saves", str(tmp_path / "saves")]
    code, _ = cli(argv, env=BOTH, **NO_ENV)
    assert code != 0


def test_without_any_key_still_explains(tmp_path):
    code, out = cli(BASE + ["--saves", str(tmp_path / "saves")], env={}, **NO_ENV)
    assert code != 0
    assert "API_KEY" in out.text


def gemini_world(registry, root):
    saved_world(registry, root)
    meta = root / WORLD / "meta"
    meta.mkdir(parents=True, exist_ok=True)
    (meta / "models.json").write_text(
        '{"narrator": {"provider": "gemini", "model": "gemini-3.8-flash"}}', encoding="utf-8"
    )


def test_gemini_world_opens_without_anthropic_key(registry, tmp_path, monkeypatch):
    root = tmp_path / "saves"
    gemini_world(registry, root)
    spy = spy_adapters(monkeypatch)
    argv = ["--world", WORLD, "--saves", str(root)]
    code, out = cli(argv, ["/quit"], env={"GEMINI_API_KEY": "sk-g"}, **NO_ENV)
    assert code == 0
    assert "Сохранённая модель не подключена" not in out.text
    assert GEMINI in spy.calls
    assert not [call for call in spy.calls if call[0] == "anthropic"]


def test_gemini_world_with_both_keys_still_uses_gemini(registry, tmp_path, monkeypatch):
    root = tmp_path / "saves"
    gemini_world(registry, root)
    spy = spy_adapters(monkeypatch)
    cli(["--world", WORLD, "--saves", str(root)], ["/quit"], env=BOTH, **NO_ENV)
    assert spy.calls[0] == GEMINI


def test_gemini_world_without_gemini_key_is_a_message(registry, tmp_path):
    root = tmp_path / "saves"
    gemini_world(registry, root)
    argv = ["--world", WORLD, "--saves", str(root)]
    code, out = cli(argv, ["/quit"], env={"ANTHROPIC_API_KEY": "sk-a"}, **NO_ENV)
    assert code == 1
    assert "GEMINI_API_KEY" in out.text


# Б1б: ask_choice, пункт «Создать героя на лету», создание в простом режиме

SHEET_SCRIPT = SCRIPTS / "hero_sheet.yaml"
DESCRIBE_LINE = "воин-сирота ищет сестру"


def create_argv(tmp_path, script=SHEET_SCRIPT, *extra):
    return ["--new", "--world", "w1", "--seed", "3", "--mock", str(script),
            "--saves", str(tmp_path / "saves"), *extra]


def test_ask_choice_returns_the_chosen_number():
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.cli import ask_choice

    out = PlainOutput()
    assert ask_choice(ScriptedInput(["2"]), out, "Заголовок:", ["а", "б"]) == 2
    assert "Заголовок:" in out.text
    assert (1, "а") in numbered_lines(out.lines)
    assert (2, "б") in numbered_lines(out.lines)


def test_ask_choice_asks_again_on_wrong_answer():
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.cli import ask_choice

    out = PlainOutput()
    assert ask_choice(ScriptedInput(["0", "3", "ерунда", "1"]), out, "Т:", ["а", "б"]) == 1
    assert out.text.count("Введите число от 1 до 2") == 3


def test_ask_choice_returns_none_when_input_ends():
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.cli import ask_choice

    assert ask_choice(ScriptedInput(["9"]), PlainOutput(), "Т:", ["а", "б"]) is None


def test_hero_menu_last_item_is_create_on_the_fly(tmp_path):
    _, out = cli(create_argv(tmp_path), ["4", "1"], env={})
    items = dict(numbered_lines(out.lines)[:4])
    assert items[4] == "Создать героя на лету"
    assert "Грей" in items[3]


def test_create_on_the_fly_in_simple_mode_starts_world_with_sheet_hero(tmp_path):
    lines = ["4", "1", "1", DESCRIBE_LINE, "1", "/quit"]
    code, out = cli(create_argv(tmp_path), lines, env={})
    assert code == 0
    assert "Герой на лету: Борин" in out.text
    assert "Создание героя: $" in out.text
    hero = load_slot(tmp_path / "saves", "w1", "auto").heroes[0]
    assert hero.name == "Борин"
    assert hero.motive == "Найти сестру."


def test_create_on_the_fly_writes_hero_sheet_meta(tmp_path):
    cli(create_argv(tmp_path), ["4", "1", "1", DESCRIBE_LINE, "1", "/quit"], env={})
    assert (tmp_path / "saves" / "w1" / "meta" / "hero_sheet.json").is_file()


def test_create_shows_preview_and_review_menu(tmp_path):
    _, out = cli(create_argv(tmp_path), ["4", "1", "1", DESCRIBE_LINE, "1", "/quit"], env={})
    assert "Мотив: Найти сестру." in out.text
    assert "Принять" in out.text


def test_create_with_manual_edit_gives_edited_hero(tmp_path):
    lines = ["4", "1", "1", DESCRIBE_LINE, "3", "name = Ило", "готово", "1", "/quit"]
    code, _ = cli(create_argv(tmp_path), lines, env={})
    assert code == 0
    assert load_slot(tmp_path / "saves", "w1", "auto").heroes[0].name == "Ило"


def test_create_runs_the_first_turn_with_the_world_after_it(tmp_path):
    lines = ["4", "1", "1", DESCRIBE_LINE, "1", "Осматриваюсь", "/quit"]
    _, out = cli(create_argv(tmp_path), lines, env={})
    assert "Огонь в очаге трещит." in out.text


def test_create_with_preset_uses_chosen_preset_tone(tmp_path):
    lines = ["4", "3", "1", DESCRIBE_LINE, "1", "/quit"]
    code, out = cli(create_argv(tmp_path), lines, env={})
    assert code == 0
    assert "пресет grim" in out.text
    assert load_slot(tmp_path / "saves", "w1", "auto").world.tone.romance == "откровенно"


def test_create_cancelled_by_end_of_input_is_code_1_and_removes_world_dir(tmp_path):
    code, out = cli(create_argv(tmp_path), ["4", "1"], env={})
    assert code == 1
    assert "Герой не выбран" in out.text
    assert not (tmp_path / "saves" / "w1").exists()


def test_create_cancelled_from_error_menu_removes_world_dir(tmp_path):
    from pathlib import Path as P

    refusal = P(tmp_path) / "refusal.yaml"
    refusal.write_text('steps:\n  - stop: refusal\n', encoding="utf-8")
    code, _ = cli(create_argv(tmp_path, refusal), ["4", "1", "1", DESCRIBE_LINE, "3"], env={})
    assert code == 1
    assert not (tmp_path / "saves" / "w1").exists()


def test_create_cancelled_keeps_other_worlds(tmp_path):
    cli(create_argv(tmp_path), ["4", "1", "1", DESCRIBE_LINE, "1", "/quit"], env={})
    argv = ["--new", "--world", "w2", "--seed", "3", "--mock", str(SHEET_SCRIPT),
            "--saves", str(tmp_path / "saves")]
    cli(argv, ["4", "1"], env={})
    assert (tmp_path / "saves" / "w1").is_dir()
    assert not (tmp_path / "saves" / "w2").exists()


def test_pack_without_hero_presets_skips_the_picker():
    from types import SimpleNamespace

    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.ui.cli import NEW_HERO, Setup, choose_hero

    pack = SimpleNamespace(heroes=[], manifest=SimpleNamespace(start=SimpleNamespace(heroes=[])))
    out = PlainOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "simple")
    assert choose_hero(ScriptedInput([]), out, out, pack, setup) is NEW_HERO
    assert out.raw == []


def test_choose_hero_returns_preset_id_for_preset_item():
    from slots_kit import ScriptedInput
    from ui_kit import PlainOutput

    from ai_dm.campaign.loader import load_pack
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import Setup, choose_hero

    root = Path(__file__).resolve().parents[3] / "campaigns" / "vale"
    pack = load_pack(root, load_registry())
    out = PlainOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "simple")
    assert choose_hero(ScriptedInput(["2"]), out, out, pack, setup) == "liel"


# Б1-фикс п.5: выбор пресета мира цифрой, номер -> id

def preset_setup(mode):
    from ai_dm.ui.cli import Setup

    return Setup({}, Path("no.env"), None, [], Path("."), mode)


@pytest.mark.parametrize("answer, expected", [("1", None), ("2", "heroic"), ("3", "grim")])
def test_choose_preset_simple_mode_maps_number_to_preset(answer, expected):
    from slots_kit import ScriptedInput

    from ai_dm.ui.cli import choose_preset
    from ai_dm.ui.io import CaptureOutput

    result = choose_preset(
        ScriptedInput([answer]), CaptureOutput(), CaptureOutput(), preset_setup("simple")
    )
    assert result == expected


@pytest.mark.parametrize("number, expected", [(1, None), (2, "heroic"), (3, "grim")])
def test_choose_preset_tui_mode_maps_picked_number_to_preset(number, expected, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_preset
    from ai_dm.ui.io import CaptureOutput

    monkeypatch.setattr(tui_module, "pick", lambda title, names, splash=False: number)
    result = choose_preset(None, CaptureOutput(), CaptureOutput(), preset_setup("tui"))
    assert result == expected
