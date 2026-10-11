# CLI и паки кампаний (этап 3, партия 1, ревью R4): main(..., campaigns_dir=<каталог паков>).
# --campaign <id> (по умолчанию vale), --hero -- id пресета пака (нет -- код 2), PackError и
# «Старт отказан» -- код 1, конфликты печатаются, догрузка при --world,
# --campaign без --new -- код 2.
import sys
from pathlib import Path

from ui_kit import cli, write_script

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "campaign"))
from campaign_kit import default_files, write_pack  # noqa: E402

from ai_dm.persistence.store import load_slot  # noqa: E402


def packs(tmp_path, files=None):
    root = tmp_path / "packs"
    write_pack(root, files)
    return root


def argv_for(tmp_path, *extra):
    script = write_script(tmp_path / "one.yaml", "Мир оживает.")
    return [*extra, "--mock", str(script), "--saves", str(tmp_path / "saves")]


def run(tmp_path, root, *extra, lines=()):
    return cli(argv_for(tmp_path, *extra), list(lines), env={}, campaigns_dir=root)


def world_dirs(tmp_path):
    saves = tmp_path / "saves"
    return sorted(p.name for p in saves.iterdir()) if saves.exists() else []


def test_campaign_flag_starts_world_from_that_pack(tmp_path):
    root = packs(tmp_path)
    code, _ = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3",
                  "--world", "mini-w1")
    assert code == 0
    bundle = load_slot(tmp_path / "saves", "mini-w1", "auto")
    assert bundle.world.campaign_id == "mini"
    assert "tavern" in bundle.world.locations
    assert bundle.heroes[0].location_id == "tavern"


def test_world_id_gets_campaign_prefix(tmp_path):
    root = packs(tmp_path)
    run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3")
    assert [name.startswith("mini-") for name in world_dirs(tmp_path)] == [True]


def test_hero_menu_comes_from_pack_presets(tmp_path):
    root = packs(tmp_path)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--seed", "3", lines=["1"])
    assert code == 0
    assert "Арн" in out.text


def test_hero_not_in_pack_presets_is_code_2(tmp_path):
    root = packs(tmp_path)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "ghost", "--seed", "3")
    assert code == 2
    assert "ghost" in out.text
    assert world_dirs(tmp_path) == []


def test_unknown_campaign_is_code_1_with_message(tmp_path):
    root = packs(tmp_path)
    code, out = run(tmp_path, root, "--new", "--campaign", "nowhere", "--hero", "arn")
    assert code == 1
    assert "nowhere" in out.text
    assert world_dirs(tmp_path) == []


def test_broken_pack_is_code_1_and_prints_error_lines(tmp_path):
    files = default_files()
    files["locations.yaml"][2]["parent_id"] = "nowhere"
    root = packs(tmp_path, files)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3")
    assert code == 1
    assert "locations.yaml" in out.text
    assert "nowhere" in out.text
    assert world_dirs(tmp_path) == []


def test_start_refused_is_code_1(tmp_path):
    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "town"})
    files["campaign.yaml"]["start"]["hero_location"] = "tavern_2"
    files["heroes/arn.yaml"].pop("location_id")
    root = packs(tmp_path, files)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3")
    assert code == 1
    assert "Старт отказан" in out.text
    assert "tavern_2" in out.text
    assert world_dirs(tmp_path) == []


def test_conflicts_are_printed_and_world_starts_without_them(tmp_path):
    files = default_files()
    files["npcs.yaml"].append({"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]})
    root = packs(tmp_path, files)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3",
                    "--world", "mini-w1")
    assert code == 0
    assert "конфликты" in out.text
    assert "twin" in out.text
    assert "twin" not in load_slot(tmp_path / "saves", "mini-w1", "auto").world.npcs


def test_clean_pack_prints_no_conflicts(tmp_path):
    root = packs(tmp_path)
    _, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3")
    assert "конфликты" not in out.text


def test_campaign_without_new_is_code_2(tmp_path):
    root = packs(tmp_path)
    code, out = run(tmp_path, root, "--world", "some", "--campaign", "mini")
    assert code == 2
    assert out.lines


def test_world_flag_merges_new_pack_entities(tmp_path):
    root = packs(tmp_path)
    run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3",
        "--world", "mini-w1")
    files = default_files()
    files["campaign.yaml"]["version"] = "2.0"
    files["npcs.yaml"].append({"id": "brana", "name": "Бранка", "named": True, "means": ["топор"]})
    write_pack(root, files)
    code, out = run(tmp_path, root, "--world", "mini-w1", lines=[])
    assert code == 0
    assert "Из пака добавлено" in out.text
    assert "brana" in out.text


def test_world_flag_with_missing_pack_dir_warns_and_continues(tmp_path):
    root = packs(tmp_path)
    run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3",
        "--world", "mini-w1")
    code, out = run(tmp_path, tmp_path / "no_packs", "--world", "mini-w1")
    assert code == 0
    assert "mini" in out.text


# Б3: пак без пресетов героя -- старт только героем на лету (BACKLOG 16 (в), Б3 В1а)

def packs_without_heroes(tmp_path):
    files = default_files()
    files["heroes/arn.yaml"] = None
    files["campaign.yaml"]["start"]["heroes"] = []
    return packs(tmp_path, files)


def test_pack_without_heroes_loads_in_cli_and_asks_to_describe_hero(tmp_path):
    root = packs_without_heroes(tmp_path)
    _, out = run(tmp_path, root, "--new", "--campaign", "mini", "--seed", "3", lines=["1"])
    assert "Опишите героя" in out.text
    assert "Выберите героя" not in out.text
    assert "нужен хотя бы один пресет героя" not in out.text


def test_hero_flag_on_pack_without_heroes_is_code_2(tmp_path):
    root = packs_without_heroes(tmp_path)
    code, out = run(tmp_path, root, "--new", "--campaign", "mini", "--hero", "arn", "--seed", "3")
    assert code == 2
    assert "arn" in out.text
    assert world_dirs(tmp_path) == []
