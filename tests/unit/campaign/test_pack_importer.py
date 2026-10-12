# Б3 (B3-PLAN A3): campaign/importer.py -- запись файлов пака из вывода модели, проверка каталога
# настоящим загрузчиком + 5.3, подмена временного пути в строках ошибок.
import sys
from pathlib import Path

import yaml

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "game"))

from import_kit import (  # noqa: E402
    PACK_ID,
    STAGE_NAME,
    faction_input,
    guard_input,
    npc_input,
    pack_files,
    staged,
    start_input,
    written_pack,
)

from ai_dm.campaign.importer import (  # noqa: E402
    ALWAYS_FILES,
    PACK_FILES,
    check_pack_dir,
    clear_pack_files,
    relabel,
    write_pack_files,
)
from ai_dm.campaign.loader import load_pack  # noqa: E402


def names_in(folder):
    return sorted(p.name for p in Path(folder).iterdir())


def read_yaml(folder, name):
    return yaml.safe_load((Path(folder) / name).read_text(encoding="utf-8"))


# PACK_FILES и write_pack_files

def test_pack_files_are_the_seven_files():
    assert PACK_FILES == (
        "campaign.yaml", "world.md", "truths.md", "locations.yaml", "npcs.yaml",
        "factions.yaml", "pantheon.yaml",
    )


def test_always_files_are_manifest_and_world_text():
    assert ALWAYS_FILES == ("campaign.yaml", "world.md")


def test_full_pack_writes_seven_files_and_returns_their_names(tmp_path):
    _, folder = staged(tmp_path)
    written = write_pack_files(folder, pack_files())
    assert written == list(PACK_FILES)
    assert names_in(folder) == sorted(PACK_FILES)


def test_empty_factions_pantheon_and_truths_are_not_written(tmp_path):
    _, folder = staged(tmp_path)
    written = write_pack_files(folder, pack_files(factions=[], pantheon=[], truths=""))
    assert written == ["campaign.yaml", "world.md", "locations.yaml", "npcs.yaml"]
    assert names_in(folder) == ["campaign.yaml", "locations.yaml", "npcs.yaml", "world.md"]


def test_empty_npcs_file_is_not_written(tmp_path):
    _, folder = staged(tmp_path)
    write_pack_files(folder, pack_files(npcs=[], factions=[], pantheon=[]))
    assert "npcs.yaml" not in names_in(folder)


def test_no_events_start_or_heroes_are_written(tmp_path):
    folder = written_pack(tmp_path)
    assert not (folder / "events.yaml").exists()
    assert not (folder / "start").exists()
    assert not (folder / "heroes").exists()


def test_yaml_files_read_back_as_the_same_data(tmp_path):
    files = pack_files()
    _, folder = staged(tmp_path)
    write_pack_files(folder, files)
    for name in ("campaign.yaml", "locations.yaml", "npcs.yaml", "factions.yaml", "pantheon.yaml"):
        assert read_yaml(folder, name) == files[name]


def test_yaml_keeps_key_order_of_the_dictionary(tmp_path):
    files = pack_files()
    folder = written_pack(tmp_path)
    first = read_yaml(folder, "npcs.yaml")[0]
    assert list(first) == list(files["npcs.yaml"][0])
    assert list(read_yaml(folder, "campaign.yaml")) == list(files["campaign.yaml"])


def test_yaml_has_cyrillic_without_escapes(tmp_path):
    folder = written_pack(tmp_path)
    text = (folder / "npcs.yaml").read_text(encoding="utf-8")
    assert "Мара" in text
    assert "\\u" not in text


def test_markdown_files_are_plain_text(tmp_path):
    folder = written_pack(tmp_path)
    assert (folder / "world.md").read_text(encoding="utf-8").strip() == (
        "Город у реки: площадь и трактир."
    )
    assert (folder / "truths.md").read_text(encoding="utf-8").strip() == "Река не замерзает."


def test_write_overwrites_files_of_a_previous_attempt(tmp_path):
    _, folder = staged(tmp_path)
    write_pack_files(folder, pack_files(world_text="Первый вариант."))
    write_pack_files(folder, pack_files(world_text="Второй вариант."))
    assert (folder / "world.md").read_text(encoding="utf-8").strip() == "Второй вариант."


# clear_pack_files

def test_clear_pack_files_removes_all_pack_files(tmp_path):
    folder = written_pack(tmp_path)
    clear_pack_files(folder)
    assert names_in(folder) == []


def test_clear_pack_files_keeps_other_files_and_import_dir(tmp_path):
    folder = written_pack(tmp_path)
    (folder / ".import" / "journal").mkdir(parents=True)
    (folder / ".import" / "journal" / "calls-001.jsonl").write_text("{}\n", encoding="utf-8")
    (folder / "notes.txt").write_text("мои заметки", encoding="utf-8")
    clear_pack_files(folder)
    assert names_in(folder) == [".import", "notes.txt"]
    assert (folder / ".import" / "journal" / "calls-001.jsonl").is_file()


def test_clear_pack_files_on_empty_folder_is_fine(tmp_path):
    _, folder = staged(tmp_path)
    clear_pack_files(folder)
    assert names_in(folder) == []


# check_pack_dir

def test_valid_pack_has_no_errors(tmp_path, registry):
    assert check_pack_dir(written_pack(tmp_path), registry) == []


def test_written_pack_is_loaded_by_the_real_loader(tmp_path, registry):
    pack = load_pack(written_pack(tmp_path), registry)
    assert pack.manifest.id == PACK_ID
    assert pack.manifest.version == "1"
    assert [loc.id for loc in pack.locations] == ["square", "inn"]
    assert [npc.id for npc in pack.npcs] == ["mara", "guard"]
    assert [f.id for f in pack.factions] == ["watch"]
    assert [g.id for g in pack.pantheon] == ["selune"]
    assert pack.heroes == []
    assert pack.manifest.start.heroes == []


def test_pack_triggers_and_secrets_survive_the_round_trip(tmp_path, registry):
    pack = load_pack(written_pack(tmp_path), registry)
    mara = next(npc for npc in pack.npcs if npc.id == "mara")
    assert [t.id for t in mara.opportunity] == ["leave"]
    assert mara.opportunity[0].once is True
    assert [s.id for s in mara.secrets] == ["debt"]


def test_pack_trade_kind_survives_the_round_trip(tmp_path, registry):
    folder = written_pack(tmp_path, npcs=[npc_input(trade_kind="smith"), guard_input()])
    pack = load_pack(folder, registry)
    assert next(npc for npc in pack.npcs if npc.id == "mara").trade.kind == "smith"


def test_pack_gender_survives_the_round_trip(tmp_path, registry):
    folder = written_pack(
        tmp_path, npcs=[npc_input(gender="female", pronouns="она"), guard_input()]
    )
    pack = load_pack(folder, registry)
    mara = next(npc for npc in pack.npcs if npc.id == "mara")
    assert (mara.gender, mara.pronouns) == ("female", "она")
    assert next(npc for npc in pack.npcs if npc.id == "guard").gender is None


def test_bad_hero_location_is_reported_with_file_and_field(tmp_path, registry):
    folder = written_pack(tmp_path, start=start_input(hero_location="nowhere"))
    lines = check_pack_dir(folder, registry)
    assert len(lines) == 1
    assert "campaign.yaml" in lines[0]
    assert "start.hero_location" in lines[0]
    assert "nowhere" in lines[0]


def test_bad_date_is_reported(tmp_path, registry):
    folder = written_pack(tmp_path, start=start_input(date="0100-13-45"))
    lines = check_pack_dir(folder, registry)
    assert any("start.date" in line for line in lines)


def test_unknown_member_of_faction_is_reported(tmp_path, registry):
    folder = written_pack(tmp_path, factions=[faction_input(members=["ghost"])])
    lines = check_pack_dir(folder, registry)
    assert any("factions.yaml" in line and "ghost" in line for line in lines)


def test_all_loader_errors_are_returned_at_once(tmp_path, registry):
    folder = written_pack(
        tmp_path, start=start_input(hero_location="nowhere"),
        factions=[faction_input(members=["ghost"])],
    )
    assert len(check_pack_dir(folder, registry)) >= 2


def test_same_name_of_two_named_npcs_is_a_conflict_line(tmp_path, registry):
    twin = npc_input(id="mara2", opportunity=[], secrets=[])
    folder = written_pack(tmp_path, npcs=[npc_input(), twin, guard_input()])
    lines = check_pack_dir(folder, registry)
    assert len(lines) == 1
    assert lines[0].startswith("npcs.yaml: npc ")
    assert "Мара" in lines[0]


def test_unnamed_npcs_may_share_a_name(tmp_path, registry):
    first = guard_input()
    second = guard_input(id="guard2")
    folder = written_pack(tmp_path, npcs=[first, second], factions=[], pantheon=[])
    assert check_pack_dir(folder, registry) == []


def test_pack_without_heroes_is_not_an_error(tmp_path, registry):
    lines = check_pack_dir(written_pack(tmp_path), registry)
    assert not any("heroes" in line for line in lines)


# relabel

def test_relabel_replaces_staging_path_with_campaign_id():
    folder = Path("/x/campaigns") / STAGE_NAME
    lines = [f"{folder}/npcs.yaml: запись 1 (x), поле means: слишком много"]
    assert relabel(lines, folder, PACK_ID) == [
        f"{PACK_ID}/npcs.yaml: запись 1 (x), поле means: слишком много"
    ]


def test_relabel_keeps_lines_without_the_path():
    assert relabel(["npcs.yaml: npc 'a'"], Path("/x/y"), "z") == ["npcs.yaml: npc 'a'"]


def test_relabel_handles_every_line_and_keeps_order():
    folder = Path("/x/stage")
    lines = ["/x/stage/a: 1", "/x/stage/b: 2"]
    assert relabel(lines, folder, "id") == ["id/a: 1", "id/b: 2"]


def test_error_lines_of_real_check_contain_the_folder_before_relabel(tmp_path, registry):
    folder = written_pack(tmp_path, start=start_input(hero_location="nowhere"))
    lines = check_pack_dir(folder, registry)
    assert str(folder) in lines[0]
    relabeled = relabel(lines, folder, PACK_ID)
    assert str(folder) not in relabeled[0]
    assert relabeled[0].startswith(f"{PACK_ID}/campaign.yaml")
