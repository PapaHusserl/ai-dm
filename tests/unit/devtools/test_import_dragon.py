# devtools/import_dragon.py (этап 3, П7): одноразовый конвертер сырого слота Дракона в пак.
# Тесты на урезанной обезличенной копии слота
# tests/fixtures/import/drunk_dragon/ (saves/ в git нет).
# Ожидаемый API: convert(slot_dir, out_dir) -> отчёт (строка или список строк) о нераспознанном.
# Раскладка пака: campaign.yaml, npcs/factions/pantheon/locations/events.yaml, heroes/grey.yaml,
# start/memory.yaml, start/chronicle.yaml, content/.
import importlib.util
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[3]
CONVERTER = ROOT / "devtools" / "import_dragon.py"
FIXTURE = ROOT / "tests" / "fixtures" / "import" / "drunk_dragon"
SLOT = FIXTURE / "slots" / "manual-import"


def load_converter():
    spec = importlib.util.spec_from_file_location("import_dragon", CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def convert(out):
    report = load_converter().convert(SLOT, out)
    if isinstance(report, str):
        return report
    if isinstance(report, (list, tuple)):
        return "\n".join(str(line) for line in report)
    return str(report)


def read_yaml(path):
    return yaml.safe_load(path.read_text(encoding="utf-8"))


def files_of(root):
    paths = sorted(p for p in root.rglob("*") if p.is_file())
    return {p.relative_to(root).as_posix(): p.read_bytes() for p in paths}


def test_converter_writes_pack_files(tmp_path):
    convert(tmp_path)
    for name in ("campaign.yaml", "npcs.yaml", "factions.yaml", "pantheon.yaml", "locations.yaml",
                 "events.yaml", "heroes/grey.yaml", "start/memory.yaml", "start/chronicle.yaml"):
        assert (tmp_path / name).is_file(), name


def test_converter_is_byte_deterministic(tmp_path):
    convert(tmp_path / "a")
    convert(tmp_path / "b")
    assert files_of(tmp_path / "a") == files_of(tmp_path / "b")


def test_converter_lists_are_sorted_by_id(tmp_path):
    convert(tmp_path)
    for name in ("npcs.yaml", "locations.yaml"):
        ids = [e["id"] for e in read_yaml(tmp_path / name)]
        assert ids == sorted(ids), name


def test_converter_start_is_oct_5_2350_chapter_two(tmp_path):
    convert(tmp_path)
    start = read_yaml(tmp_path / "campaign.yaml")["start"]
    assert str(start["date"]) == "0001-10-05"
    assert start["time"] == "23:50"
    assert start["chapter"]["number"] == 2
    assert start["chapter"]["title"] == "Глава II: Отголоски Мора"
    assert start["hero_location"] == "iron_ridge_foothills"


def test_converter_flags_go_to_campaign(tmp_path):
    convert(tmp_path)
    assert read_yaml(tmp_path / "campaign.yaml")["flags"]["milo_rescued"] is True


def test_converter_tone_notes_have_no_output_layout_demands(tmp_path):
    # оформление вывода рисует игра: требования старой сессии к рамкам и колонкам не переносятся
    convert(tmp_path)
    notes = read_yaml(tmp_path / "campaign.yaml")["tone"]["notes"]
    assert notes
    for word in ("ASCII", "колонк", "tmux", "```"):
        assert word not in notes


def test_scene_summary_has_no_session_meta(tmp_path):
    convert(tmp_path)
    summary = read_yaml(tmp_path / "campaign.yaml")["start"]["scene_summary"]
    for junk in ("dm_hint", "мета-вопрос", "по шагу"):
        assert junk not in summary


def test_scene_summary_has_all_four_options(tmp_path):
    convert(tmp_path)
    summary = read_yaml(tmp_path / "campaign.yaml")["start"]["scene_summary"]
    for n in ("[1]", "[2]", "[3]", "[4]"):
        assert n in summary


def test_scene_summary_has_choice_and_unanswered_question(tmp_path):
    convert(tmp_path)
    summary = read_yaml(tmp_path / "campaign.yaml")["start"]["scene_summary"]
    assert "2 и 3" in summary
    assert "статус?" in summary


def test_scene_summary_has_eight_turn_lines(tmp_path):
    convert(tmp_path)
    summary = read_yaml(tmp_path / "campaign.yaml")["start"]["scene_summary"]
    assert summary.count("→") == 8


def test_scene_summary_has_situation_and_deadlines(tmp_path):
    convert(tmp_path)
    summary = read_yaml(tmp_path / "campaign.yaml")["start"]["scene_summary"]
    assert "Перед подъёмом к Восточной шахте" in summary or "Эдрин" in summary
    assert "Начало ритуала Назира" in summary


def test_recent_turns_are_not_carried(tmp_path):
    convert(tmp_path)
    memory = read_yaml(tmp_path / "start" / "memory.yaml")
    assert not memory.get("recent_turns")


def test_memory_keeps_scenes_and_game_summary(tmp_path):
    convert(tmp_path)
    memory = read_yaml(tmp_path / "start" / "memory.yaml")
    assert len(memory["scenes"]) == 3
    assert memory["game_summary"]


def test_chronicle_day_becomes_at_s(tmp_path):
    convert(tmp_path)
    entries = read_yaml(tmp_path / "start" / "chronicle.yaml")["entries"]
    assert len(entries) == 2
    assert all("at_s" in e and "day" not in e for e in entries)


def test_event_region_names_become_location_ids(tmp_path):
    convert(tmp_path)
    events = {e["id"]: e for e in read_yaml(tmp_path / "events.yaml")}
    assert events["harvest_raids"]["regions"] == ["tavern_drunken_dragon"]


def test_event_region_matches_exactly_and_normalized(tmp_path):
    convert(tmp_path)
    events = {e["id"]: e for e in read_yaml(tmp_path / "events.yaml")}
    assert events["nazir_ritual"]["regions"] == ["iron_ridge_foothills", "city"]


def test_unknown_event_region_goes_to_report_and_is_dropped(tmp_path):
    report = convert(tmp_path)
    events = read_yaml(tmp_path / "events.yaml")
    assert "Нигдеград" in report
    assert all("Нигдеград" not in e["regions"] for e in events)


def test_events_are_caused_and_keep_cause_text(tmp_path):
    convert(tmp_path)
    for event in read_yaml(tmp_path / "events.yaml"):
        assert event["kind"] == "caused"
        assert event["cause"]


def test_origin_of_entities_is_pack(tmp_path):
    convert(tmp_path)
    for name in ("npcs.yaml", "pantheon.yaml", "locations.yaml"):
        assert all(e.get("origin") == "pack" for e in read_yaml(tmp_path / name)), name


def test_hero_grey_has_inventory_and_money(tmp_path):
    convert(tmp_path)
    hero = read_yaml(tmp_path / "heroes" / "grey.yaml")
    items = set(hero["choices"]["inventory"]) | {e["item_id"] for e in hero["inventory_extra"]}
    assert items == {"north_wind_blade", "travel_flask", "mithral_shirt"}
    assert hero["money_cp"] == 5400
    assert hero["equipped"]["armor"] == "mithral_shirt"


def test_hero_has_no_birth_s_value(tmp_path):
    convert(tmp_path)
    npcs = read_yaml(tmp_path / "npcs.yaml")
    assert all(n.get("birth_s") is None for n in npcs)


def test_items_are_copied_to_pack_content(tmp_path):
    convert(tmp_path)
    assert (tmp_path / "content" / "items" / "travel_flask.yaml").is_file()
    assert (tmp_path / "content" / "weapons" / "north_wind_blade.yaml").is_file()


def test_converter_does_not_touch_fixture(tmp_path):
    before = files_of(FIXTURE)
    convert(tmp_path)
    assert files_of(FIXTURE) == before


# Грей 3 ур. из черновиков (docs/decisions/ranger-2-5-plan.md, п. 12, решения 1-4)

def test_hero_grey_is_level_3_from_drafts(tmp_path):
    convert(tmp_path)
    hero = read_yaml(tmp_path / "heroes" / "grey.yaml")
    assert hero["level"] == 3
    assert hero["xp"] == 900


def test_hero_grey_has_level_choices_and_companion(tmp_path):
    convert(tmp_path)
    hero = read_yaml(tmp_path / "heroes" / "grey.yaml")
    by_level = {c["level"]: c for c in hero["level_choices"]}
    assert by_level[2]["fighting_style"] == "archery"
    assert by_level[2]["expertise"] == ["survival"]
    assert by_level[3]["subclass_id"] == "beast_master"
    assert set(by_level[3]["spells_add"]) == {
        "cure_wounds", "ensnaring_strike", "speak_with_animals", "fog_cloud",
    }
    assert hero["companion"]["name"] == "Акела"
