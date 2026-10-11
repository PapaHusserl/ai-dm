# Б1б (B1-PLAN, A6, «Тесты Б1б»): --hero-describe TEXT -- герой на лету без меню (неинтерактивно).
# Мок-скрипт tests/fixtures/scripts/hero_sheet.yaml: шаг 1 -- hero_sheet (валидный лист для vale,
# воин Борин), шаг 2 -- рассказ. Валидный лист принимается сам; сбой -- сообщение и код 1.
# Лист пишется в saves/<мир>/meta/hero_sheet.json; --replay без --hero берёт его оттуда.
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from hero_kit import sheet_input  # noqa: E402
from slots_kit import list_slots  # noqa: E402
from ui_kit import SEED, cli, numbered_lines  # noqa: E402

from ai_dm.game.hero_create import read_hero_sheet  # noqa: E402
from ai_dm.game.turn import REFUSAL_HINT  # noqa: E402
from ai_dm.persistence.store import load_slot  # noqa: E402

SHEET = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "hero_sheet.yaml"
DESCRIBE = "воин-сирота ищет сестру"


def argv(root, *extra, script=SHEET):
    return ["--new", "--world", "w1", "--seed", str(SEED), "--hero-describe", DESCRIBE,
            "--mock", str(script), "--saves", str(root), *extra]


def run(tmp_path, *extra, lines=("/quit",), script=SHEET):
    root = tmp_path / "saves"
    code, out = cli(argv(root, *extra, script=script), list(lines), env={})
    return code, out, root


def write_steps(path, steps):
    path.write_text(yaml.safe_dump({"steps": steps}, allow_unicode=True), encoding="utf-8")
    return path


# успех

def test_describe_starts_the_world_with_code_0(tmp_path):
    code, _, _ = run(tmp_path)
    assert code == 0


def test_describe_notes_the_hero_name(tmp_path):
    _, out, _ = run(tmp_path)
    assert "Герой на лету: Борин" in out.text


def test_describe_notes_creation_cost(tmp_path):
    _, out, _ = run(tmp_path)
    assert "Создание героя: $" in out.text
    assert "(1 вызовов)" in out.text


def test_describe_writes_hero_sheet_to_meta(tmp_path):
    _, _, root = run(tmp_path)
    assert (root / "w1" / "meta" / "hero_sheet.json").is_file()
    assert read_hero_sheet(root, "w1").choices.name == "Борин"


def test_describe_saves_auto_slot_with_the_sheet_hero(tmp_path):
    _, _, root = run(tmp_path)
    assert "auto" in list_slots(root, "w1")
    hero = load_slot(root, "w1", "auto").heroes[0]
    assert hero.name == "Борин"
    assert hero.sheet.class_id == "fighter"


def test_describe_hero_has_motive_means_and_opportunity(tmp_path):
    _, _, root = run(tmp_path)
    hero = load_slot(root, "w1", "auto").heroes[0]
    assert hero.motive == "Найти сестру."
    assert hero.means == ["острый ум"]
    assert [t.id for t in hero.opportunity] == ["o1"]


def test_describe_hero_has_class_kit_items(tmp_path):
    _, _, root = run(tmp_path)
    hero = load_slot(root, "w1", "auto").heroes[0]
    assert {e.item_id for e in hero.inventory} >= {"chain_mail", "greatsword"}


def test_describe_does_not_show_preview(tmp_path):
    _, out, _ = run(tmp_path)
    assert "Мотив:" not in out.text


def test_describe_has_no_menu_and_no_hero_question(tmp_path):
    _, out, _ = run(tmp_path)
    assert "Выберите героя" not in out.text
    assert "Пресет мира" not in out.text


def test_describe_world_runs_a_turn_after_creation(tmp_path):
    code, out, _ = run(tmp_path, lines=("Осматриваюсь", "/quit"))
    assert code == 0
    assert "Огонь в очаге трещит." in out.text


def test_describe_with_preset_grim_sets_preset_tone(tmp_path):
    code, out, root = run(tmp_path, "--preset", "grim")
    assert code == 0
    assert "пресет grim" in out.text
    assert load_slot(root, "w1", "auto").world.tone.romance == "откровенно"


def test_describe_writes_creation_calls_to_journal(tmp_path):
    from ai_dm.config.app import load_settings
    from ai_dm.llm.journal import Journal

    _, _, root = run(tmp_path, lines=("Осматриваюсь", "/quit"))
    records = Journal(root, "w1", load_settings().app.journal).read_records()
    hero = [r for r in records if r["run_id"].startswith("hero-")]
    assert len(hero) == 1


# несовместимые флаги

def test_describe_without_new_is_code_2(tmp_path):
    code, out = cli(
        ["--world", "w1", "--hero-describe", DESCRIBE, "--saves", str(tmp_path / "saves")],
        env={},
    )
    assert code == 2
    assert "--hero-describe" in out.text


def test_describe_with_hero_is_code_2(tmp_path):
    code, out, root = run(tmp_path, "--hero", "arn")
    assert code == 2
    assert "--hero-describe" in out.text
    assert not (root / "w1").exists()


def test_describe_with_replay_is_code_2(tmp_path):
    code, out, root = run(tmp_path, "--replay")
    assert code == 2
    assert "--hero-describe" in out.text
    assert not (root / "w1").exists()


# сбои без меню

def test_describe_refusal_is_code_1_with_hint_and_no_menu(tmp_path):
    script = write_steps(tmp_path / "refusal.yaml", [{"stop": "refusal"}])
    code, out, _ = run(tmp_path, script=script)
    assert code == 1
    assert REFUSAL_HINT in " ".join(out.text.split())
    assert numbered_lines(out.lines) == []


def test_describe_refusal_leaves_no_slot(tmp_path):
    script = write_steps(tmp_path / "refusal.yaml", [{"stop": "refusal"}])
    _, _, root = run(tmp_path, script=script)
    assert list_slots(root, "w1") == []


def test_describe_invalid_sheets_are_code_1_without_menu(tmp_path):
    call = {"id": "s-1", "name": "hero_sheet", "input": sheet_input(motive="")}
    script = write_steps(tmp_path / "bad.yaml", [{"tool_calls": [call]}] * 4)
    code, out, root = run(tmp_path, script=script)
    assert code == 1
    assert numbered_lines(out.lines) == []
    assert not (root / "w1" / "meta" / "hero_sheet.json").exists()


# replay

def live(tmp_path):
    code, _, root = run(tmp_path, lines=("Осматриваюсь", "/quit"))
    assert code == 0
    return root


def replay_argv(root, *extra):
    return ["--replay", "--world", "w1", "--seed", str(SEED), "--saves", str(root), *extra]


def test_replay_without_hero_takes_the_sheet_from_meta(tmp_path):
    root = live(tmp_path)
    code, out = cli(replay_argv(root), ["Осматриваюсь", "/quit"], env={})
    assert code == 0
    assert "Расхождение" not in out.text


def test_replay_does_not_change_the_live_world(tmp_path):
    root = live(tmp_path)
    before = {p: p.read_bytes() for p in sorted((root / "w1").rglob("*")) if p.is_file()}
    cli(replay_argv(root), ["Осматриваюсь", "/quit"], env={})
    after = {p: p.read_bytes() for p in sorted((root / "w1").rglob("*")) if p.is_file()}
    assert after == before


def test_replay_without_meta_and_without_hero_gives_hint(tmp_path):
    root = live(tmp_path)
    (root / "w1" / "meta" / "hero_sheet.json").unlink()
    code, out = cli(replay_argv(root), ["/quit"], env={})
    assert code == 2
    assert "--hero" in out.text
    assert "лист героя" in out.text


def test_replay_with_hero_still_works_as_before(tmp_path):
    root = tmp_path / "saves"
    code, _ = cli(
        ["--new", "--hero", "arn", "--world", "w1", "--seed", str(SEED), "--mock", str(SHEET),
         "--saves", str(root)],
        ["/quit"], env={},
    )
    assert code == 0
    assert not (root / "w1" / "meta" / "hero_sheet.json").exists()


# hero_flag_refusal, replay_records, emit_blocks напрямую

def refusal_of(*flags):
    from ai_dm.ui.cli import hero_flag_refusal, make_parser
    from ai_dm.ui.io import CaptureOutput

    notes = CaptureOutput()
    args = make_parser().parse_args(list(flags))
    return hero_flag_refusal(args, notes), notes


def test_refusal_none_without_the_flag():
    code, notes = refusal_of("--new", "--hero", "arn")
    assert code is None
    assert notes.lines == []


def test_refusal_none_for_new_with_describe_only():
    code, notes = refusal_of("--new", "--hero-describe", "воин")
    assert code is None
    assert notes.lines == []


def test_refusal_without_new_names_the_flag():
    code, notes = refusal_of("--world", "w1", "--hero-describe", "воин")
    assert code == 2
    assert "--hero-describe" in "\n".join(notes.lines)
    assert "--new" in "\n".join(notes.lines)


def test_refusal_with_hero_names_both_flags():
    code, notes = refusal_of("--new", "--hero", "arn", "--hero-describe", "воин")
    assert code == 2
    text = "\n".join(notes.lines)
    assert "--hero-describe" in text
    assert "--hero" in text


def test_refusal_with_replay_is_code_2():
    code, notes = refusal_of("--new", "--replay", "--hero-describe", "воин")
    assert code == 2
    assert "--replay" in "\n".join(notes.lines)


def test_replay_records_drops_hero_creation_records():
    from ai_dm.ui.cli import replay_records

    records = [
        {"run_id": "hero-20261008T1200-1", "role": "narrator"},
        {"run_id": "t-1", "role": "narrator"},
        {"run_id": "hero-20261008T1200-2", "role": "narrator"},
        {"run_id": "t-2", "role": "world"},
    ]
    assert [r["run_id"] for r in replay_records(records)] == ["t-1", "t-2"]


def test_replay_records_keeps_all_without_hero_prefix():
    from ai_dm.ui.cli import replay_records

    records = [{"run_id": "t-1", "role": "narrator"}, {"run_id": "heroic-1", "role": "world"}]
    assert replay_records(records) == records


def test_emit_blocks_writes_note_and_menu_lines():
    from ui_kit import PlainOutput

    from ai_dm.ui.screen import menu_block, note_block
    from ai_dm.ui.simple import emit_blocks

    out = PlainOutput()
    emit_blocks(out, [note_block("Привет"), menu_block(["а", "б"], "Выбери:")], 80)
    assert out.lines[0] == "Привет"
    assert out.lines[1:] == ["Выбери:", "1. а", "2. б"]


def test_emit_blocks_wraps_by_width():
    from ui_kit import PlainOutput

    from ai_dm.ui.screen import note_block
    from ai_dm.ui.simple import emit_blocks

    out = PlainOutput()
    emit_blocks(out, [note_block("слово " * 20)], 30)
    assert len(out.raw) > 1
    assert all(len(line) <= 30 for line in out.raw)


# пустое описание, чужой мир, preset не мутируется

def test_empty_describe_is_code_2(tmp_path):
    root = tmp_path / "saves"
    base = ["--new", "--world", "w1", "--mock", str(SHEET), "--saves", str(root)]
    code, out = cli([*base, "--hero-describe", ""], env={})
    assert code == 2
    assert "--hero-describe" in out.text
    assert not (root / "w1").exists()


def test_blank_describe_is_code_2(tmp_path):
    root = tmp_path / "saves"
    base = ["--new", "--world", "w1", "--mock", str(SHEET), "--saves", str(root)]
    code, _ = cli([*base, "--hero-describe", "   "], env={})
    assert code == 2


def test_failed_describe_on_existing_world_does_not_delete_it(tmp_path):
    root = live(tmp_path)
    before = {p: p.read_bytes() for p in sorted((root / "w1").rglob("*")) if p.is_file()}
    code, _ = cli(argv(root), ["/quit"], env={})
    assert code == 1
    after = {p: p.read_bytes() for p in sorted((root / "w1").rglob("*")) if p.is_file()}
    assert after == before


def test_interactive_cancel_on_existing_world_does_not_delete_it(tmp_path):
    root = live(tmp_path)
    argv_ = ["--new", "--world", "w1", "--seed", str(SEED), "--mock", str(SHEET),
             "--saves", str(root)]
    code, _ = cli(argv_, ["4", "1"], env={})
    assert code == 1
    assert "auto" in list_slots(root, "w1")


def test_prepare_does_not_mutate_args_preset(tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup, make_parser, prepare
    from ai_dm.ui.io import CaptureOutput

    args = make_parser().parse_args(
        ["--new", "--seed", str(SEED), "--saves", str(tmp_path / "saves"), "--mock", str(SHEET)]
    )
    setup = Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "simple")
    out = CaptureOutput()
    prepare(args, ScriptedInput(["4", "2", DESCRIBE, "1"]), out, out, setup)
    assert args.preset is None


# добивка по выжившим мутантам mutmut (Б1б): prompt ввода, заголовки экрана TUI, discard_world

class RecordingInput:
    def __init__(self, lines):
        self.lines = list(lines)
        self.prompts = []

    def read(self, prompt=""):
        self.prompts.append(prompt)
        return self.lines.pop(0) if self.lines else None


def test_ask_choice_reads_with_prompt_mark():
    from ui_kit import PlainOutput

    from ai_dm.ui.cli import ask_choice

    source = RecordingInput(["x", "1"])
    ask_choice(source, PlainOutput(), "Т:", ["а"])
    assert source.prompts == ["> ", "> "]


def test_create_hero_simple_reads_with_prompt_mark():
    from types import SimpleNamespace

    from ui_kit import PlainOutput

    from ai_dm.ui.cli import create_hero_simple

    steps = iter([SimpleNamespace(blocks=[], quit=True)])
    session = SimpleNamespace(
        start=lambda: SimpleNamespace(blocks=[]), submit=lambda line: next(steps), width=80,
        sheet=None,
    )
    source = RecordingInput(["описание"])
    create_hero_simple(source, PlainOutput(), session)
    assert source.prompts == ["> "]


def tui_setup(tmp_path):
    from ai_dm.campaign.loader import CAMPAIGNS_DIR
    from ai_dm.ui.cli import Setup

    return Setup({}, tmp_path / "no.env", None, [], CAMPAIGNS_DIR, "tui")


def test_choose_number_passes_title_and_names_to_tui_pick(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_number
    from ai_dm.ui.io import CaptureOutput

    seen = []
    monkeypatch.setattr(tui_module, "pick", lambda title, names, splash: seen.append((title,
        names, splash)) or 2)
    out = CaptureOutput()
    number = choose_number(
        None, out, out, tui_setup(tmp_path), ("героя", "Заголовок:", ["а", "б"], True)
    )
    assert number == 2
    assert seen == [("Заголовок:", ["а", "б"], True)]


def test_preset_screen_failure_note_names_the_preset(tmp_path, monkeypatch):
    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_preset
    from ai_dm.ui.io import CaptureOutput

    def broken(title, names, splash=False):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "pick", broken)
    notes = CaptureOutput()
    result = choose_preset(ScriptedInput(["2"]), CaptureOutput(), notes, tui_setup(tmp_path))
    assert result == "heroic"
    assert any("Выбор пресета в TUI не запустился" in line for line in notes.lines)


def test_discard_world_removes_dir_without_slots(tmp_path):
    from ai_dm.ui.cli import discard_world

    (tmp_path / "w1" / "journal").mkdir(parents=True)
    discard_world(tmp_path, "w1")
    assert not (tmp_path / "w1").exists()


def test_discard_world_keeps_dir_with_slots(tmp_path):
    from ai_dm.ui.cli import discard_world

    (tmp_path / "w1" / "slots" / "auto").mkdir(parents=True)
    discard_world(tmp_path, "w1")
    assert (tmp_path / "w1" / "slots" / "auto").is_dir()


def test_discard_world_ignores_missing_dir(tmp_path):
    from ai_dm.ui.cli import discard_world

    discard_world(tmp_path, "nope")
    assert not (tmp_path / "nope").exists()


def test_choose_number_passes_splash_flag_from_menu_not_from_label(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_number
    from ai_dm.ui.io import CaptureOutput

    seen = []
    monkeypatch.setattr(tui_module, "pick", lambda title, names, splash: seen.append(splash) or 1)
    out = CaptureOutput()
    choose_number(None, out, out, tui_setup(tmp_path), ("героя", "Заголовок:", ["а", "б"], False))
    assert seen == [False]


def test_choose_preset_asks_tui_without_splash(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_preset
    from ai_dm.ui.io import CaptureOutput

    seen = []
    monkeypatch.setattr(tui_module, "pick", lambda title, names, splash: seen.append(splash) or 1)
    out = CaptureOutput()
    choose_preset(None, out, out, tui_setup(tmp_path))
    assert seen == [False]


def test_choose_hero_asks_tui_with_splash(tmp_path, monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import choose_hero
    from ai_dm.ui.io import CaptureOutput

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))
    from hero_kit import vale_pack

    from ai_dm.content.loader import load_registry

    seen = []
    monkeypatch.setattr(tui_module, "pick", lambda title, names, splash: seen.append(splash) or 1)
    out = CaptureOutput()
    choose_hero(None, out, out, vale_pack(load_registry()), tui_setup(tmp_path))
    assert seen == [True]
