# Б3 (B3-PLAN A5): ai-dm --import FILE --campaign ID -- пак из текстовой выжимки в campaigns/<id>.
# Мок-сценарий tests/fixtures/scripts/import_pack.yaml: шаг 1 -- валидный вызов pack. Вывод --
# только консольный (без TUI); коды выхода: 0 пак записан, 1 отказ/отмена/сбой, 2 неверные флаги.
import json
import sys
from pathlib import Path

import pytest
import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from import_kit import (  # noqa: E402
    PACK_ID,
    bad_pack_call,
    pack_call,
    summary_text,
)
from ui_kit import SEED, cli  # noqa: E402

from ai_dm.campaign.importer import PACK_FILES, check_pack_dir  # noqa: E402
from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402
from ai_dm.ui.cli import make_parser  # noqa: E402

FIXTURES = Path(__file__).resolve().parents[2] / "fixtures" / "scripts"
IMPORT_SCRIPT = FIXTURES / "import_pack.yaml"
SHEET_SCRIPT = FIXTURES / "hero_sheet.yaml"
DESCRIBE = "воин-сирота ищет сестру"


def write_steps(path, steps):
    path.write_text(yaml.safe_dump({"steps": steps}, allow_unicode=True), encoding="utf-8")
    return path


def summary_file(tmp_path, text=None):
    path = tmp_path / "summary.txt"
    path.write_text(summary_text() if text is None else text, encoding="utf-8")
    return path


def campaigns_of(tmp_path):
    folder = tmp_path / "campaigns"
    folder.mkdir(exist_ok=True)
    return folder


def run(tmp_path, *extra, lines=(), script=IMPORT_SCRIPT, summary=None, campaign=PACK_ID):
    argv = ["--import", str(summary or summary_file(tmp_path))]
    if campaign is not None:
        argv += ["--campaign", campaign]
    argv += ["--mock", str(script), "--saves", str(tmp_path / "saves"), *extra]
    root = campaigns_of(tmp_path)
    code, out = cli(argv, list(lines), env={}, campaigns_dir=root)
    return code, out, root


def names(root):
    return sorted(p.name for p in root.iterdir())


def snapshot(folder):
    return {
        str(p.relative_to(folder)): p.read_bytes()
        for p in sorted(folder.rglob("*")) if p.is_file() and ".import" not in p.parts
    }


# успех

def test_import_writes_pack_files_and_returns_0(tmp_path):
    code, _, root = run(tmp_path)
    assert code == 0
    folder = root / PACK_ID
    for name in PACK_FILES:
        assert (folder / name).is_file(), name


def test_import_leaves_only_the_pack_in_campaigns(tmp_path):
    _, _, root = run(tmp_path)
    assert names(root) == [PACK_ID]


def test_imported_pack_is_valid_for_the_real_loader(tmp_path, registry):
    _, _, root = run(tmp_path)
    assert check_pack_dir(root / PACK_ID, registry) == []


def test_import_writes_journal_with_one_import_record(tmp_path):
    _, _, root = run(tmp_path)
    path = root / PACK_ID / ".import" / "journal" / "calls-001.jsonl"
    records = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]
    assert len(records) == 1
    assert records[0]["role"] == "import"
    assert records[0]["run_id"].startswith("import-")
    assert records[0]["turn_seq"] == 0


def test_import_reports_pack_cost_and_next_step(tmp_path):
    _, out, _ = run(tmp_path)
    assert f"Пак {PACK_ID} записан" in out.text
    assert "Импорт пака: $" in out.text
    assert "(1 вызовов)" in out.text
    assert f"ai-dm --new --campaign {PACK_ID}" in out.text
    assert "правьте файлы руками" in out.text


def test_import_cost_line_comes_before_the_pack_report(tmp_path):
    _, out, _ = run(tmp_path)
    lines = out.lines
    cost = next(i for i, line in enumerate(lines) if line.startswith("Импорт пака: $"))
    report = next(i for i, line in enumerate(lines) if line.startswith(f"Пак {PACK_ID} записан"))
    assert cost < report


def test_import_does_not_touch_saves(tmp_path):
    run(tmp_path)
    assert not (tmp_path / "saves").exists()


def test_successful_import_does_not_wait_for_more_input(tmp_path):
    from ai_dm.ui.cli import main

    class Reads:
        def __init__(self):
            self.prompts = []

        def read(self, prompt=""):
            self.prompts.append(prompt)
            return None

    source = Reads()
    argv = ["--import", str(summary_file(tmp_path)), "--campaign", PACK_ID, "--mock",
            str(IMPORT_SCRIPT), "--saves", str(tmp_path / "saves")]
    code = main(argv, stdin=source, stdout=_Sink(), env={}, campaigns_dir=campaigns_of(tmp_path))
    assert code == 0
    assert source.prompts == []


class _Sink:
    def write(self, line):
        pass


def test_import_with_provider_anthropic_uses_import_role_of_that_profile(tmp_path):
    code, _, root = run(tmp_path, "--provider", "anthropic")
    assert code == 0
    path = root / PACK_ID / ".import" / "journal" / "calls-001.jsonl"
    record = json.loads(path.read_text(encoding="utf-8").splitlines()[0])
    assert record["requested_model"] == "claude-sonnet-5-5"


# повторный import в тот же id

def test_repeat_import_into_same_id_is_refused_with_code_1(tmp_path):
    run(tmp_path)
    code, out, _ = run(tmp_path)
    assert code == 1
    assert "уже есть" in out.text
    assert PACK_ID in out.text


def test_repeat_import_does_not_change_files(tmp_path):
    _, _, root = run(tmp_path)
    before = snapshot(root / PACK_ID)
    run(tmp_path)
    assert snapshot(root / PACK_ID) == before


def test_repeat_import_leaves_no_staging(tmp_path):
    run(tmp_path)
    _, _, root = run(tmp_path)
    assert names(root) == [PACK_ID]


def test_repeat_import_keeps_hand_edits(tmp_path):
    _, _, root = run(tmp_path)
    world = root / PACK_ID / "world.md"
    world.write_text("Правка руками.\n", encoding="utf-8")
    run(tmp_path)
    assert world.read_text(encoding="utf-8") == "Правка руками.\n"


def test_existing_directory_without_pack_is_also_refused(tmp_path):
    (campaigns_of(tmp_path) / PACK_ID).mkdir()
    code, out, root = run(tmp_path)
    assert code == 1
    assert "уже есть" in out.text
    assert list((root / PACK_ID).iterdir()) == []


# флаги

def test_import_without_campaign_is_code_2(tmp_path):
    code, out, root = run(tmp_path, campaign=None)
    assert code == 2
    assert "--campaign" in out.text
    assert names(root) == []


@pytest.mark.parametrize("extra", [
    ["--new"], ["--world", "w1"], ["--replay"], ["--replay-report", "some/dir"],
    ["--hero", "arn"], ["--hero-describe", "воин"], ["--preset", "grim"], ["--seed", "3"],
    ["--mock-world", "x.yaml"], ["--mock-summarizer", "x.yaml"],
])
def test_import_with_game_flag_is_code_2(tmp_path, extra):
    code, out, root = run(tmp_path, *extra)
    assert code == 2
    assert "--import" in out.text
    assert names(root) == []


def test_import_with_game_flag_makes_no_model_call(tmp_path):
    script = write_steps(tmp_path / "steps.yaml", [{"tool_calls": [pack_call()]}])
    code, _, root = run(tmp_path, "--seed", "3", script=script)
    assert code == 2
    assert names(root) == []


def test_parser_has_import_flag():
    assert "--import" in make_parser().format_help()


def test_parser_import_is_stored_as_import_file():
    args = make_parser().parse_args(["--import", "f.txt", "--campaign", "a"])
    assert args.import_file == "f.txt"
    assert make_parser().parse_args([]).import_file is None


# выжимка

def test_missing_summary_file_is_code_1(tmp_path):
    code, out, root = run(tmp_path, summary=tmp_path / "nope.txt")
    assert code == 1
    assert "не прочитана" in out.text
    assert names(root) == []


def test_empty_summary_is_code_1(tmp_path):
    code, out, root = run(tmp_path, summary=summary_file(tmp_path, ""))
    assert code == 1
    assert "Выжимка пуста" in out.text
    assert names(root) == []


def test_whitespace_summary_is_code_1(tmp_path):
    code, out, _ = run(tmp_path, summary=summary_file(tmp_path, "  \n \n"))
    assert code == 1
    assert "Выжимка пуста" in out.text


def test_too_long_summary_is_code_1_with_length(tmp_path):
    long_text = "а" * 60001
    code, out, root = run(tmp_path, summary=summary_file(tmp_path, long_text))
    assert code == 1
    assert "Выжимка длиннее 60000 символов (60001)" in out.text
    assert names(root) == []


def test_summary_of_exactly_max_chars_is_accepted(tmp_path):
    code, _, _ = run(tmp_path, summary=summary_file(tmp_path, "а" * 60000))
    assert code == 0


def test_non_utf8_summary_is_code_1(tmp_path):
    path = tmp_path / "bin.txt"
    path.write_bytes(b"\xff\xfe\x00bad")
    code, out, root = run(tmp_path, summary=path)
    assert code == 1
    assert "не прочитана" in out.text
    assert names(root) == []


def test_summary_that_is_a_directory_is_code_1(tmp_path):
    code, out, _ = run(tmp_path, summary=tmp_path)
    assert code == 1
    assert "не прочитана" in out.text


# сбои модели

def three_bad(tmp_path):
    steps = [{"tool_calls": [bad_pack_call(f"b-{i}")]} for i in range(3)]
    return write_steps(tmp_path / "bad.yaml", steps)


def test_three_invalid_packs_show_menu_and_leave_gives_code_1(tmp_path):
    code, out, _ = run(tmp_path, script=three_bad(tmp_path), lines=["3"])
    assert code == 1
    assert "Повторить" in out.text
    assert "Сменить модель" in out.text
    assert "Выйти" in out.text
    assert "Импорт отменён" in out.text


def test_three_invalid_packs_leave_nothing_on_disk(tmp_path):
    _, _, root = run(tmp_path, script=three_bad(tmp_path), lines=["3"])
    assert names(root) == []


def test_cost_of_failed_import_is_printed_before_staging_is_removed(tmp_path):
    _, out, _ = run(tmp_path, script=three_bad(tmp_path), lines=["3"])
    assert "Импорт пака: $" in out.text
    assert "(3 вызовов)" in out.text


def test_end_of_input_in_error_menu_gives_code_1_and_clean_disk(tmp_path):
    code, _, root = run(tmp_path, script=three_bad(tmp_path), lines=[])
    assert code == 1
    assert names(root) == []


def test_retry_from_menu_can_finish_the_import(tmp_path):
    steps = [{"tool_calls": [bad_pack_call(f"b-{i}")]} for i in range(3)]
    steps.append({"tool_calls": [pack_call("ok-1")]})
    code, out, root = run(tmp_path, script=write_steps(tmp_path / "s.yaml", steps), lines=["1"])
    assert code == 0
    assert "(4 вызовов)" in out.text
    assert names(root) == [PACK_ID]


def test_invalid_digit_in_error_menu_is_refused_and_menu_stays(tmp_path):
    code, out, _ = run(tmp_path, script=three_bad(tmp_path), lines=["9", "3"])
    assert code == 1
    assert "Нет такого варианта" in out.text


def test_refusal_shows_hint_and_menu(tmp_path):
    script = write_steps(tmp_path / "ref.yaml", [{"stop": "refusal"}])
    code, out, root = run(tmp_path, script=script, lines=["3"])
    assert code == 1
    assert REFUSAL_HINT in " ".join(out.text.split())
    assert "Выйти" in out.text
    assert names(root) == []


def test_error_lines_of_the_loader_have_campaign_id_not_staging_path(tmp_path):
    steps = [{"tool_calls": [bad_pack_call()]}, {"tool_calls": [pack_call("ok")]}]
    script = write_steps(tmp_path / "s.yaml", steps)
    code, _, root = run(tmp_path, script=script)
    assert code == 0
    path = root / PACK_ID / ".import" / "journal" / "calls-001.jsonl"
    text = path.read_text(encoding="utf-8")
    assert ".import-" not in text
    assert f"{PACK_ID}/campaign.yaml" in text


def test_exception_in_the_run_removes_staging(tmp_path, monkeypatch):
    def boom(*args, **kwargs):
        raise RuntimeError("сбой")

    monkeypatch.setattr("ai_dm.ui.import_session.run_import", boom)
    code, _, root = run(tmp_path)
    assert code == 1
    assert names(root) == []


def test_unreadable_script_is_code_1_without_staging(tmp_path):
    code, _, root = run(tmp_path, script=tmp_path / "no_script.yaml")
    assert code == 1
    assert names(root) == []


def test_read_only_campaigns_dir_is_code_1_with_text(tmp_path):
    root = campaigns_of(tmp_path)
    root.chmod(0o500)
    try:
        code, out, _ = run(tmp_path)
    finally:
        root.chmod(0o700)
    if code == 0:
        pytest.skip("права на каталог не действуют (root)")
    assert code == 1
    assert "Не удалось подготовить импорт" in out.text


# мир из импортированного пака

def start_world(tmp_path, *extra, lines=("/quit",)):
    argv = ["--new", "--world", "w1", "--campaign", PACK_ID, "--seed", str(SEED), *extra,
            "--mock", str(SHEET_SCRIPT), "--saves", str(tmp_path / "saves")]
    return cli(argv, list(lines), env={}, campaigns_dir=campaigns_of(tmp_path))


def test_world_from_imported_pack_starts_with_hero_on_the_fly(tmp_path):
    run(tmp_path)
    code, _ = start_world(tmp_path, "--hero-describe", DESCRIBE)
    assert code == 0
    bundle = load_slot(tmp_path / "saves", "w1", "auto")
    assert bundle.world.campaign_id == PACK_ID
    assert bundle.heroes[0].name == "Борин"
    assert bundle.heroes[0].location_id == "inn"
    assert sorted(bundle.world.npcs) == ["guard", "mara"]
    assert sorted(bundle.world.locations) == ["inn", "square"]


def test_world_from_imported_pack_has_pack_tone_and_date(tmp_path):
    run(tmp_path)
    start_world(tmp_path, "--hero-describe", DESCRIBE)
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    assert world.tone.violence == "жестоко"
    assert world.clock.to_date() == "0100-03-01"


def test_interactive_start_on_imported_pack_goes_straight_to_describe(tmp_path):
    run(tmp_path)
    code, out = start_world(tmp_path, lines=["1", "1", DESCRIBE, "1", "/quit"])
    assert code == 0, out.text
    assert "Выберите героя" not in out.text
    assert load_slot(tmp_path / "saves", "w1", "auto").heroes[0].name == "Борин"


def test_hero_flag_on_imported_pack_is_code_2(tmp_path):
    run(tmp_path)
    code, out = start_world(tmp_path, "--hero", "arn")
    assert code == 2
    assert "arn" in out.text


def test_hand_edit_of_imported_pack_is_picked_up_by_the_world(tmp_path):
    _, _, root = run(tmp_path)
    npcs = root / PACK_ID / "npcs.yaml"
    npcs.write_text(
        npcs.read_text(encoding="utf-8").replace("Хочет выкупить долг.", "Хочет уехать."),
        encoding="utf-8",
    )
    start_world(tmp_path, "--hero-describe", DESCRIBE)
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    assert world.npcs["mara"].motive == "Хочет уехать."



# id кампании: путь наружу из campaigns/ недопустим

@pytest.mark.parametrize("campaign", ["a/b", "..", "../x", "/abs", "a b"])
def test_campaign_id_that_is_not_a_plain_id_is_code_2(tmp_path, campaign):
    code, out, root = run(tmp_path, campaign=campaign)
    assert code == 2
    assert "--campaign" in out.text
    assert names(root) == []
    assert not (tmp_path / "x").exists()


# роль import: профиль без неё откатывается на roles.import

PROFILE_WITHOUT_IMPORT = "".join(
    f'\n[profiles.other.{name}]\nprovider = "other"\n'
    f'model = "gemini-3.5-flash-lite"\nmax_tokens = 100\n'
    for name in ("narrator", "world", "summarizer")
)


def pick(provider_flag, narrator_provider):
    from types import SimpleNamespace

    from ai_dm.config.app import load_settings
    from ai_dm.ui.cli import pick_import

    settings = load_settings(PROFILE_WITHOUT_IMPORT)
    args = SimpleNamespace(provider=provider_flag)
    narrator = SimpleNamespace(provider=narrator_provider)
    return pick_import(args, settings, narrator), settings


def test_pick_import_with_provider_flag_of_profile_without_import_falls_back():
    role, settings = pick("other", "gemini")
    assert role is settings.app.roles.import_


def test_pick_import_with_narrator_of_profile_without_import_falls_back():
    role, settings = pick(None, "other")
    assert role is settings.app.roles.import_


def test_pick_import_takes_import_role_of_profile_when_it_has_one():
    role, settings = pick("anthropic", "gemini")
    assert role is settings.app.profiles["anthropic"].import_


def test_pick_import_by_narrator_provider_uses_that_profile():
    role, settings = pick(None, "anthropic")
    assert role is settings.app.profiles["anthropic"].import_


def test_pick_import_for_default_narrator_is_roles_import():
    role, settings = pick(None, "gemini")
    assert role is settings.app.roles.import_


def test_pick_import_for_unknown_provider_is_roles_import():
    role, settings = pick(None, "nowhere")
    assert role is settings.app.roles.import_


# добивка по мутантам

def test_summary_text_reaches_the_model_request(tmp_path):
    _, _, root = run(tmp_path)
    path = root / PACK_ID / ".import" / "journal" / "calls-001.jsonl"
    text = path.read_text(encoding="utf-8")
    assert "Мара знает все слухи" in json.loads(text.splitlines()[0])["request"]["messages"][0][
        "content"
    ][0]["text"] or "Мара знает все слухи" in text.replace("\\u041c", "М")


def test_error_menu_prompt_is_greater_than_sign(tmp_path):
    from ai_dm.ui.cli import main

    class Reads:
        def __init__(self):
            self.prompts = []

        def read(self, prompt=""):
            self.prompts.append(prompt)
            return "3"

    source = Reads()
    argv = ["--import", str(summary_file(tmp_path)), "--campaign", PACK_ID, "--mock",
            str(three_bad(tmp_path)), "--saves", str(tmp_path / "saves")]
    main(argv, stdin=source, stdout=_Sink(), env={}, campaigns_dir=campaigns_of(tmp_path))
    assert source.prompts == ["> "]


def test_staging_is_made_in_campaigns_dir_for_the_campaign_id(tmp_path, monkeypatch):
    import ai_dm.ui.cli as cli_module

    seen = []
    real = cli_module.stage_dir
    monkeypatch.setattr(
        cli_module, "stage_dir", lambda root, campaign: seen.append((root, campaign)) or real(
            root, campaign
        )
    )
    run(tmp_path)
    assert seen == [(tmp_path / "campaigns", PACK_ID)]


def test_switch_model_in_menu_uses_keys_from_env(tmp_path):
    summary = summary_file(tmp_path)
    argv = ["--import", str(summary), "--campaign", PACK_ID, "--mock", str(three_bad(tmp_path)),
            "--saves", str(tmp_path / "saves")]
    env = {"ANTHROPIC_API_KEY": "sk-test-a", "GEMINI_API_KEY": "sk-test-g"}
    code, out = cli(argv, ["2", "1", "3"], env=env, campaigns_dir=campaigns_of(tmp_path),
                    dotenv_path=tmp_path / "no.env")
    assert code == 1
    assert "Модель рассказчика: " in out.text
    assert "sk-test" not in out.text


def test_switch_model_without_keys_shows_error_and_menu(tmp_path):
    argv = ["--import", str(summary_file(tmp_path)), "--campaign", PACK_ID, "--mock",
            str(three_bad(tmp_path)), "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["2", "1", "3"], env={}, campaigns_dir=campaigns_of(tmp_path),
                    dotenv_path=tmp_path / "no.env")
    assert code == 1
    assert "нет ключа" in out.text


def test_live_import_without_key_is_code_1_with_key_name(tmp_path):
    argv = ["--import", str(summary_file(tmp_path)), "--campaign", PACK_ID,
            "--saves", str(tmp_path / "saves")]
    root = campaigns_of(tmp_path)
    code, out = cli(argv, [], env={}, campaigns_dir=root, dotenv_path=tmp_path / "no.env")
    assert code == 1
    assert "API_KEY" in out.text
    assert names(root) == []


def test_each_refusal_text_is_specific(tmp_path):
    code, out, _ = run(tmp_path, "--new")
    assert code == 2
    assert out.text.startswith("--import несовместим")
    code, out, _ = run(tmp_path, campaign=None)
    assert out.text.startswith("Для --import нужен --campaign")
    code, out, _ = run(tmp_path, campaign="a/b")
    assert out.text.startswith("--campaign: id пака")
