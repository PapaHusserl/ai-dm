# Б0-П2: --preset ID (пресет мира для нового мира). Только с --new (иначе код 2, как --hero);
# неизвестный id -- код 2 и список id каталога; в заметках старта «пресет <id>»; без флага
# тон пака не меняется; --replay берёт тот же --preset, что исходный прогон (подсказка в сообщении).
from pathlib import Path

from ui_kit import SEED, cli, numbered_lines, write_script

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


def test_no_preset_keeps_pack_tone(tmp_path):
    from ai_dm.campaign.loader import load_pack
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import DEFAULT_CAMPAIGN

    start(tmp_path)
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    root = Path(__file__).resolve().parents[3] / "campaigns" / DEFAULT_CAMPAIGN
    assert world.tone == load_pack(root, load_registry()).manifest.tone
    entries = load_slot(tmp_path / "saves", "w1", "auto").chronicle.entries
    assert [e for e in entries if e.kind == "tone"] == []


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

    interactive(tmp_path, ["1", "2", "Осматриваюсь", "/quit"], mock_factory=factory)
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


def test_interactive_preset_menu_has_pack_item_and_four_presets(tmp_path):
    _, out = interactive(tmp_path, ["1", "1", "/quit"])
    start = out.lines.index(next(line for line in out.lines if "Пресет мира" in line))
    assert len(numbered_lines(out.lines[start:start + 6])) == 5


def test_interactive_second_item_is_heroic_in_notes_and_tone(tmp_path):
    from ai_dm.campaign.presets import apply_preset, load_presets

    code, out = interactive(tmp_path, ["1", "2", "/quit"])
    assert code == 0
    assert "пресет heroic" in out.text
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    presets = load_presets()
    assert world.tone.notes == presets["heroic"].tone.notes
    assert world.tone != apply_preset(world.tone, presets["grim"])


def test_interactive_preset_as_in_pack_keeps_pack_tone(tmp_path):
    from ai_dm.campaign.loader import load_pack
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import DEFAULT_CAMPAIGN

    interactive(tmp_path, ["1", "1", "/quit"])
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    root = Path(__file__).resolve().parents[3] / "campaigns" / DEFAULT_CAMPAIGN
    assert world.tone == load_pack(root, load_registry()).manifest.tone


def test_interactive_end_of_input_on_preset_means_as_in_pack(tmp_path):
    from ai_dm.campaign.loader import load_pack
    from ai_dm.content.loader import load_registry
    from ai_dm.ui.cli import DEFAULT_CAMPAIGN

    code, _ = interactive(tmp_path, ["1"])
    assert code == 0
    world = load_slot(tmp_path / "saves", "w1", "auto").world
    root = Path(__file__).resolve().parents[3] / "campaigns" / DEFAULT_CAMPAIGN
    assert world.tone == load_pack(root, load_registry()).manifest.tone


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
