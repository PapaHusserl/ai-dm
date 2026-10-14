# Б0-П2: --preset ID (пресет мира для нового мира). Только с --new (иначе код 2, как --hero);
# неизвестный id -- код 2 и список id каталога; в заметках старта «пресет <id>»; без флага
# тон пака не меняется; --replay берёт тот же --preset, что исходный прогон (подсказка в сообщении).
from pathlib import Path

import pytest
from ui_kit import NUMBERED, SEED, cli, numbered_lines, write_script

from ai_dm.persistence.store import load_slot

BASE = ["--new", "--hero", "arn", "--seed", str(SEED)]
IDS = ["heroic", "grim", "romantic", "fairytale"]


def argv(tmp_path, *extra):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    return [*extra, "--mock", str(script), "--saves", str(tmp_path / "saves")]


def world_dirs(tmp_path):
    saves = tmp_path / "saves"
    return sorted(p.name for p in saves.iterdir()) if saves.exists() else []


def start(tmp_path, *extra, world="w1"):
    code, out = cli(argv(tmp_path, *BASE, "--world", world, *extra), ["/quit"], env={})
    return code, out


def test_new_with_preset_grim_notes_and_romance(tmp_path):
    code, out = start(tmp_path, "--preset", "grim")
    assert code == 0
    assert "пресет grim" in out.text
    assert load_slot(tmp_path / "saves", "w1", "auto").world.tone.romance == "откровенно"


def test_new_with_preset_fairytale_changes_axes(tmp_path):
    start(tmp_path, "--preset", "fairytale")
    tone = load_slot(tmp_path / "saves", "w1", "auto").world.tone
    assert tone.romance == "нет"
    assert tone.horror == "нет"


def test_new_with_preset_writes_one_tone_entry(tmp_path):
    start(tmp_path, "--preset", "grim")
    entries = load_slot(tmp_path / "saves", "w1", "auto").chronicle.entries
    assert len([e for e in entries if e.kind == "tone" and "Пресет мира" in e.text]) == 1


def test_preset_note_is_in_world_line(tmp_path):
    _, out = start(tmp_path, "--preset", "grim")
    line = next(line for line in out.lines if line.startswith("Мир: "))
    assert "w1" in line
    assert f"сид {SEED}" in line
    assert "пресет grim" in line


def test_no_preset_has_no_preset_note(tmp_path):
    _, out = start(tmp_path)
    assert "пресет" not in out.text


def default_pack_manifest():
    from ai_dm.campaign.loader import load_pack
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import DEFAULT_CAMPAIGN

    root = Path(__file__).resolve().parents[3] / "campaigns" / DEFAULT_CAMPAIGN
    return load_pack(root, load_registry()).manifest


def assert_manifest_preset_tone(tmp_path):
    from ai_dm.campaign.presets import apply_preset, load_presets

    manifest = default_pack_manifest()
    bundle = load_slot(tmp_path / "saves", "w1", "auto")
    assert bundle.world.tone == apply_preset(manifest.tone, load_presets()[manifest.preset])
    tones = [e.text for e in bundle.chronicle.entries if e.kind == "tone"]
    assert tones == ["Пресет мира: Героическое приключение"]


def test_no_preset_uses_manifest_preset_tone(tmp_path):
    start(tmp_path)
    assert_manifest_preset_tone(tmp_path)


def test_preset_without_new_is_code_2(tmp_path):
    code, out = cli(argv(tmp_path, "--world", "some", "--preset", "grim"), env={})
    assert code == 2
    assert "--preset" in out.text
    assert world_dirs(tmp_path) == []


def test_unknown_preset_is_code_2_with_catalog_ids(tmp_path):
    code, out = start(tmp_path, "--preset", "nowhere")
    assert code == 2
    assert "nowhere" in out.text
    for preset_id in IDS:
        assert preset_id in out.text
    assert world_dirs(tmp_path) == []


def test_replay_hint_mentions_preset(tmp_path):
    code, out = cli(["--replay", "--world", "w1", "--saves", str(tmp_path)], env={})
    assert code == 2
    code, out = cli(
        ["--replay", "--world", "w1", "--hero", "arn", "--saves", str(tmp_path)], env={}
    )
    assert code == 2
    assert "--preset" in out.text


def played(tmp_path, *extra):
    code, _ = cli(argv(tmp_path, *BASE, "--world", "w1", *extra), ["осматриваюсь", "/quit"], env={})
    assert code == 0


def replay_args(tmp_path, *extra):
    return ["--replay", "--world", "w1", "--hero", "arn", "--seed", str(SEED), *extra,
            "--saves", str(tmp_path / "saves")]


def test_replay_with_same_preset_goes_through(tmp_path):
    played(tmp_path, "--preset", "grim")
    code, _ = cli(replay_args(tmp_path, "--preset", "grim"), ["осматриваюсь", "/quit"], env={})
    assert code == 0


def test_replay_without_the_preset_of_the_original_run_diverges(tmp_path):
    played(tmp_path, "--preset", "grim")
    code, _ = cli(replay_args(tmp_path), ["осматриваюсь", "/quit"], env={})
    assert code == 1


def test_replay_with_unknown_preset_is_code_2(tmp_path):
    code, out = cli(
        ["--replay", "--world", "w1", "--hero", "arn", "--seed", str(SEED), "--preset", "nowhere",
         "--saves", str(tmp_path / "saves")],
        env={},
    )
    assert code == 2
    assert "nowhere" in out.text


def test_manifest_preset_of_pack_is_applied_by_cli(tmp_path):
    import sys

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
    from campaign_kit import default_files, write_pack

    files = default_files()
    files["campaign.yaml"]["preset"] = "grim"
    root = tmp_path / "packs"
    write_pack(root, files)
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    args = ["--new", "--campaign", "mini", "--hero", "arn", "--seed", "3", "--world", "w1",
            "--mock", str(script), "--saves", str(tmp_path / "saves")]
    code, _ = cli(args, ["/quit"], env={}, campaigns_dir=root)
    assert code == 0
    assert load_slot(tmp_path / "saves", "w1", "auto").world.tone.romance == "откровенно"


def test_preset_pack_keeps_pack_tone_and_labels_note(tmp_path):
    code, out = start(tmp_path, "--preset", "pack")
    assert code == 0
    line = next(line for line in out.lines if line.startswith("Мир: "))
    assert "пресет pack (как в паке)" in line
    bundle = load_slot(tmp_path / "saves", "w1", "auto")
    assert bundle.world.tone.romance == ""
    assert [e for e in bundle.chronicle.entries if e.kind == "tone"] == []


def test_unknown_preset_error_lists_pack_option(tmp_path):
    _, out = start(tmp_path, "--preset", "nowhere")
    assert "pack (как в паке)" in out.text


# кодовое имя в меню пресета (интерактивный старт: герой, потом пресет)

CODENAMES = ["Властелин колец", "Ведьмак", "Сумерки", "Хроники Нарнии"]


def interactive(tmp_path, lines, extra=(), **kw):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    args = ["--new", "--world", "w1", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(tmp_path / "saves"), *extra]
    return cli(args, lines, env={}, **kw)


def test_preset_menu_items_show_codename(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    for codename in CODENAMES:
        assert f"(в духе «{codename}»)" in out.text


def test_preset_menu_item_has_name_codename_and_description(tmp_path):
    from ai_dm.campaign.presets import load_presets

    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    heroic = load_presets()["heroic"]
    assert f"{heroic.name} (в духе «Властелин колец») — {heroic.description}" in " ".join(
        out.text.split()
    )


def test_preset_without_codename_has_no_parenthesis(tmp_path, monkeypatch):
    import ai_dm.ui.cli as cli_module
    from ai_dm.campaign.presets import load_presets

    plain = load_presets()["heroic"].model_copy(update={"codename": None, "name": "Безымянный"})
    monkeypatch.setattr(cli_module, "load_presets", lambda: {"heroic": plain})
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    line = next(line for line in out.lines if "Безымянный" in line)
    assert "в духе" not in line
    assert "(" not in line


def test_codename_is_not_in_world_tone(tmp_path):
    interactive(tmp_path, ["1", "2", "/quit"])
    tone = load_slot(tmp_path / "saves", "w1", "auto").world.tone
    assert tone.model_dump_json() != ""
    for codename in CODENAMES:
        assert codename not in tone.model_dump_json()


def test_codename_is_not_in_narrator_requests(tmp_path):
    from ai_dm.llm.mock import ScriptedAdapter, load_script

    made = []

    def factory(path):
        adapter = ScriptedAdapter(load_script(path))
        made.append(adapter)
        return adapter

    interactive(tmp_path, ["1", "2", "1", "Осматриваюсь", "/quit"], mock_factory=factory)
    requests = [r for adapter in made for r in adapter.requests]
    assert requests
    for request in requests:
        dumped = repr(request)
        for codename in CODENAMES:
            assert codename not in dumped


# меню «Пресет мира:» при интерактивном старте (герой -> пресет -> мир)

def test_interactive_start_asks_preset_after_hero(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    text = out.text
    assert text.index("Выберите героя") < text.index("Пресет мира")


def test_interactive_preset_menu_first_item_is_as_in_pack(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    items = [text for number, text in numbered_lines(out.lines) if number == 1]
    assert any("как в паке" in item.lower() for item in items)


def menu_numbers(out):
    # номера пунктов меню пресетов: от заголовка «Пресет мира» подряд с 1
    lines = out.lines
    start = lines.index(next(line for line in lines if "Пресет мира" in line))
    numbers = []
    for number, _ in numbered_lines(lines[start:]):
        if number != len(numbers) + 1:
            break
        numbers.append(number)
    return numbers


def test_interactive_preset_menu_has_pack_item_and_four_presets(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    assert menu_numbers(out) == [1, 2, 3, 4, 5]


def test_interactive_second_item_is_heroic_in_notes_and_tone(tmp_path):
    from ai_dm.campaign.presets import apply_preset, load_presets

    code, out = interactive(tmp_path, ["1", "2", "/quit"])
    assert code == 0
    assert "пресет heroic" in out.text
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    presets = load_presets()
    assert world.tone.notes == presets["heroic"].tone.notes
    assert world.tone != apply_preset(world.tone, presets["grim"])


def test_interactive_preset_as_in_pack_uses_manifest_preset_tone(tmp_path):
    interactive(tmp_path, ["1", "1", "/quit"])
    assert_manifest_preset_tone(tmp_path)


def test_interactive_end_of_input_on_preset_means_as_in_pack(tmp_path):
    code, _ = interactive(tmp_path, ["1"])
    assert code == 0
    assert_manifest_preset_tone(tmp_path)


def test_interactive_wrong_answer_on_preset_asks_again(tmp_path):
    code, out = interactive(tmp_path, ["1", "9", "ерунда", "3", "/quit"])
    assert code == 0
    assert "пресет grim" in out.text


def test_hero_flag_skips_preset_question(tmp_path):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    argv = ["--new", "--hero", "arn", "--seed", str(SEED), "--mock", str(script),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["/quit"], env={})
    assert code == 0
    assert "Пресет мира" not in out.text


def test_preset_flag_skips_preset_question(tmp_path):
    code, out = interactive(tmp_path, ["1", "/quit"], extra=["--preset", "grim"])
    assert code == 0
    assert "Пресет мира" not in out.text
    assert "пресет grim" in out.text


def test_hero_describe_skips_preset_question(tmp_path):
    sheet = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "hero_sheet.yaml"
    argv = ["--new", "--seed", str(SEED), "--hero-describe", "воин", "--mock", str(sheet),
            "--saves", str(tmp_path / "saves")]
    code, out = cli(argv, ["/quit"], env={})
    assert code == 0
    assert "Пресет мира" not in out.text


# П37: подсказка пака к пресету мира (меню и заметки старта)
# временный campaigns_dir: mini (без preset) и rose (preset: romantic, «Розы»)

HINT = "подходит"


def make_packs(tmp_path, rose=True, extra=None):
    import sys

    import yaml

    sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
    from campaign_kit import default_files, write_pack

    root = tmp_path / "packs"
    write_pack(root, default_files())
    if rose:
        files = default_files()
        files["campaign.yaml"].update({"id": "rose", "name": "Розы", "preset": "romantic"})
        write_pack(tmp_path / "rose_tmp", files)
        (tmp_path / "rose_tmp" / "mini").rename(root / "rose")
    for name, text in (extra or {}).items():
        (root / name).mkdir()
        (root / name / "campaign.yaml").write_text(
            text if isinstance(text, str) else yaml.safe_dump(text), encoding="utf-8"
        )
    return root


def packs_cli(tmp_path, root, *extra, lines=("/quit",), campaign="mini"):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    args = ["--new", "--campaign", campaign, "--seed", "3", "--world", "w1", "--mock", str(script),
            "--saves", str(tmp_path / "saves"), *extra]
    return cli(args, list(lines), env={}, campaigns_dir=root)


def line_index(out, part):
    # позиция в тексте вывода без переносов (строки переносятся по 80)
    return flat(out).index(part)


def flat(out):
    return " ".join(out.text.split())


def command(campaign, preset):
    return f"ai-dm --new --campaign {campaign} --preset {preset}"


def romantic_label_text():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import preset_label

    return preset_label(load_presets()["romantic"])


def test_preset_label_without_hint_is_unchanged():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import preset_label

    p = load_presets()["heroic"]
    assert preset_label(p) == f"{p.name} (в духе «Властелин колец») — {p.description}"
    assert preset_label(p, "") == preset_label(p)


def test_preset_label_appends_hint_after_space():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import preset_label

    p = load_presets()["heroic"]
    assert preset_label(p, "X") == preset_label(p) + " X"


def test_hint_suffix_empty_is_empty_string():
    from ai_dm.ui.cli import hint_suffix

    assert hint_suffix([]) == ""
    assert hint_suffix(()) == ""


def test_hint_suffix_names_pack_and_id():
    from ai_dm.ui.cli import hint_suffix

    text = hint_suffix([("rose", "Розы")])
    assert "Розы" in text
    assert "(rose)" in text
    assert text.endswith(".")


def test_hint_suffix_lists_all_packs():
    from ai_dm.ui.cli import hint_suffix

    text = hint_suffix([("aa", "Аа"), ("rose", "Розы")])
    for part in ("Аа", "(aa)", "Розы", "(rose)"):
        assert part in text
    assert text.index("Аа") < text.index("Розы")
    assert "«Аа» (aa), «Розы» (rose)" in text


@pytest.mark.parametrize("preset_id", [None, "", "pack"])
def test_hint_lines_without_real_preset_is_empty(preset_id):
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import hint_lines

    hints = {"romantic": [("rose", "Розы")]}
    assert hint_lines(preset_id, hints, load_presets()) == []


def test_hint_lines_preset_without_packs_is_empty():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import hint_lines

    assert hint_lines("heroic", {"romantic": [("rose", "Розы")]}, load_presets()) == []
    assert hint_lines("heroic", {}, load_presets()) == []


def test_hint_lines_one_pack_gives_one_line_with_command():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import hint_lines

    lines = hint_lines("romantic", {"romantic": [("rose", "Розы")]}, load_presets())
    assert len(lines) == 1
    assert "Чувства и интриги" in lines[0]
    assert "Розы" in lines[0]
    assert command("rose", "romantic") in lines[0]
    assert "новый мир" in lines[0]


def test_hint_lines_two_packs_give_two_lines():
    from ai_dm.campaign.presets import load_presets
    from ai_dm.ui.cli import hint_lines

    hints = {"romantic": [("aa", "Аа"), ("rose", "Розы")]}
    lines = hint_lines("romantic", hints, load_presets())
    assert len(lines) == 2
    assert command("aa", "romantic") in lines[0]
    assert command("rose", "romantic") in lines[1]


def test_pack_hints_drops_current_pack_and_empty_lists(tmp_path):
    from ai_dm.ui.cli import pack_hints

    root = make_packs(tmp_path)
    assert pack_hints(root, "rose") == {}


def test_pack_hints_keeps_other_packs(tmp_path):
    from ai_dm.ui.cli import pack_hints

    root = make_packs(tmp_path)
    assert pack_hints(root, "mini") == {"romantic": [("rose", "Розы")]}


def test_pack_hints_keeps_second_pack_of_same_preset(tmp_path):
    from ai_dm.ui.cli import pack_hints

    root = make_packs(tmp_path, extra={"aa": {"id": "aa", "name": "Аа", "preset": "romantic"}})
    assert pack_hints(root, "rose") == {"romantic": [("aa", "Аа")]}


def test_choose_preset_simple_puts_hint_only_into_its_item():
    from slots_kit import ScriptedInput

    from ai_dm.ui.cli import Setup, choose_preset
    from ai_dm.ui.io import CaptureOutput

    out = CaptureOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "simple")
    result = choose_preset(
        ScriptedInput(["4"]), out, CaptureOutput(), setup, {"romantic": [("rose", "Розы")]}
    )
    assert result == "romantic"
    text = " ".join(" ".join(out.lines).split())
    assert "Розы" in text
    assert text.count("Розы") == 1
    assert text.index("Розы") > text.index("Чувства и интриги")


def test_choose_preset_tui_gets_names_with_hint(monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import PRESET_AS_PACK, Setup, choose_preset
    from ai_dm.ui.io import CaptureOutput

    seen = []

    def fake_pick(title, names, splash=False):
        seen.append(names)
        return 4

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    result = choose_preset(
        None, CaptureOutput(), CaptureOutput(), setup, {"romantic": [("rose", "Розы")]}
    )
    assert result == "romantic"
    names = seen[0]
    assert names[0] == PRESET_AS_PACK
    assert [("Розы" in name) for name in names] == [False, False, False, True, False]
    assert names[3].startswith(romantic_label_text())


def test_choose_preset_without_hints_has_no_hint_text():
    from slots_kit import ScriptedInput

    from ai_dm.ui.cli import Setup, choose_preset
    from ai_dm.ui.io import CaptureOutput

    out = CaptureOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "simple")
    choose_preset(ScriptedInput(["1"]), out, CaptureOutput(), setup, None)
    assert "Лучше подходит" not in " ".join(out.lines)


def test_preset_without_own_pack_prints_hint_after_world_line(tmp_path):
    code, out = packs_cli(tmp_path, make_packs(tmp_path), "--hero", "arn", "--preset", "romantic")
    assert code == 0
    assert line_index(out, "Мир: ") < line_index(out, command("rose", "romantic"))


def test_hint_line_names_pack_and_new_world_command(tmp_path):
    _, out = packs_cli(tmp_path, make_packs(tmp_path), "--hero", "arn", "--preset", "romantic")
    text = flat(out)
    line = text[text.index("Пресету"):]
    assert "Розы" in line
    assert "Чувства и интриги" in line


def test_preset_of_own_pack_prints_no_hint(tmp_path):
    root = make_packs(tmp_path)
    code, out = packs_cli(tmp_path, root, "--hero", "arn", "--preset", "romantic", campaign="rose")
    assert code == 0
    assert HINT not in out.text


def test_preset_without_pack_prints_no_hint(tmp_path):
    _, out = packs_cli(tmp_path, make_packs(tmp_path), "--hero", "arn", "--preset", "heroic")
    assert HINT not in out.text


def test_preset_pack_prints_no_hint(tmp_path):
    _, out = packs_cli(tmp_path, make_packs(tmp_path), "--hero", "arn", "--preset", "pack")
    assert HINT not in out.text


def test_no_preset_with_hero_flag_prints_no_hint(tmp_path):
    _, out = packs_cli(tmp_path, make_packs(tmp_path), "--hero", "arn")
    assert HINT not in out.text


def test_hero_describe_prints_no_hint(tmp_path):
    sheet = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "hero_sheet.yaml"
    root = make_packs(tmp_path)
    args = ["--new", "--campaign", "mini", "--seed", "3", "--hero-describe", "воин",
            "--mock", str(sheet), "--saves", str(tmp_path / "saves")]
    code, out = cli(args, ["/quit"], env={}, campaigns_dir=root)
    assert code == 0
    assert HINT not in out.text


def packs_menu_number(root):
    # номер пункта romantic в меню: «Как в паке» + пресеты каталога по порядку
    from ai_dm.campaign.presets import load_presets

    return list(load_presets()).index("romantic") + 2


def test_interactive_menu_shows_hint_in_romantic_item(tmp_path):
    root = make_packs(tmp_path)
    _, out = packs_cli(tmp_path, root, lines=["1", "1", "/quit"])
    text = " ".join(" ".join(out.lines).split())
    assert "Лучше подходит пак «Розы» (rose)" in text


def test_interactive_romantic_choice_prints_command_after_world_line(tmp_path):
    root = make_packs(tmp_path)
    number = str(packs_menu_number(root))
    code, out = packs_cli(tmp_path, root, lines=["1", number, "/quit"])
    assert code == 0
    assert line_index(out, "Мир: ") < line_index(out, command("rose", "romantic"))


def test_interactive_as_in_pack_prints_no_hint_line(tmp_path):
    root = make_packs(tmp_path)
    _, out = packs_cli(tmp_path, root, lines=["1", "1", "/quit"])
    assert not [line for line in out.lines if "новый мир — ai-dm" in line]


def test_replay_prints_no_hint(tmp_path):
    root = make_packs(tmp_path)
    packs_cli(tmp_path, root, "--hero", "arn", "--preset", "romantic",
              lines=["осматриваюсь", "/quit"])
    args = ["--replay", "--world", "w1", "--campaign", "mini", "--hero", "arn", "--seed", "3",
            "--preset", "romantic", "--saves", str(tmp_path / "saves")]
    code, out = cli(args, ["осматриваюсь", "/quit"], env={}, campaigns_dir=root)
    assert "Повтор идёт" in out.text
    assert HINT not in out.text


def test_broken_neighbour_pack_does_not_break_start(tmp_path):
    root = make_packs(tmp_path, extra={"broken": ": :"})
    code, out = packs_cli(tmp_path, root, "--hero", "arn", "--preset", "romantic")
    assert code == 0
    assert command("rose", "romantic") in flat(out)


def test_import_temp_dir_is_not_offered(tmp_path):
    root = make_packs(
        tmp_path, rose=False,
        extra={".import-x-abc": {"id": "x", "name": "Икс", "preset": "romantic"}},
    )
    _, out = packs_cli(tmp_path, root, "--hero", "arn", "--preset", "romantic")
    assert HINT not in out.text


# на реальных паках каталога

def real_cli(tmp_path, *extra, lines=("/quit",), campaign="vale"):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    args = ["--new", "--campaign", campaign, "--seed", "3", "--world", "w1", "--mock", str(script),
            "--saves", str(tmp_path / "saves"), *extra]
    return cli(args, list(lines), env={})


def test_real_vale_menu_hints_romantic_and_grim_but_not_heroic(tmp_path):
    _, out = real_cli(tmp_path, lines=["1", "1", "/quit"])
    lines = out.lines
    start = lines.index(next(line for line in lines if "Пресет мира" in line))
    items = {}
    current = None
    for line in lines[start:]:
        if line.startswith("Мир:"):
            break
        match = NUMBERED.match(line)
        if match and int(match.group(1)) == len(items) + 1:
            current = int(match.group(1))
            items[current] = ""
        if current:
            items[current] += " " + line
    assert "dusk_academy" in items[4]
    assert "drunk_dragon" in items[3]
    assert "Лучше подходит" not in items[2]
    assert "Лучше подходит" not in items[1]
    assert "Лучше подходит" not in items[5]


def test_real_vale_with_romantic_prints_dusk_academy_command(tmp_path):
    _, out = real_cli(tmp_path, "--hero", "arn", "--preset", "romantic")
    assert command("dusk_academy", "romantic") in flat(out)


def test_real_vale_with_grim_prints_drunk_dragon_command(tmp_path):
    _, out = real_cli(tmp_path, "--hero", "arn", "--preset", "grim")
    assert command("drunk_dragon", "grim") in flat(out)


def test_real_vale_with_heroic_prints_no_hint(tmp_path):
    _, out = real_cli(tmp_path, "--hero", "arn", "--preset", "heroic")
    assert HINT not in out.text


def test_real_dusk_academy_with_romantic_prints_no_hint(tmp_path):
    sheet = Path(__file__).resolve().parents[2] / "fixtures" / "scripts" / "hero_sheet.yaml"
    args = ["--new", "--campaign", "dusk_academy", "--seed", "3", "--hero-describe", "воин",
            "--preset", "romantic", "--mock", str(sheet), "--saves", str(tmp_path / "saves")]
    code, out = cli(args, ["/quit"], env={})
    assert code == 0
    assert HINT not in out.text


def test_choose_preset_tui_pick_gets_no_splash(monkeypatch):
    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import Setup, choose_preset
    from ai_dm.ui.io import CaptureOutput

    seen = []

    def fake_pick(title, names, splash=False):
        seen.append(splash)
        return 1

    monkeypatch.setattr(tui_module, "pick", fake_pick)
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    choose_preset(None, CaptureOutput(), CaptureOutput(), setup)
    assert seen == [False]


def test_choose_preset_tui_failure_notes_it_and_falls_back_to_simple(monkeypatch):
    from slots_kit import ScriptedInput

    import ai_dm.ui.tui as tui_module
    from ai_dm.ui.cli import Setup, choose_preset
    from ai_dm.ui.io import CaptureOutput

    def broken(title, names, splash=False):
        raise tui_module.TuiStartError("нет экрана")

    monkeypatch.setattr(tui_module, "pick", broken)
    notes = CaptureOutput()
    setup = Setup({}, Path("no.env"), None, [], Path("."), "tui")
    result = choose_preset(ScriptedInput(["3"]), CaptureOutput(), notes, setup)
    assert result == "grim"
    assert "Выбор пресета в TUI не запустился: нет экрана" in " ".join(notes.lines)
