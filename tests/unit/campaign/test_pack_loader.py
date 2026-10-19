# Загрузчик пака (этап 3, партия 1; STAGE3-PLAN A2). API и допущения -- в campaign_kit.py.
# Ошибки пака -- построчно, с путём файла и полем; битая сущность не даёт загрузить пак.
from campaign_kit import default_files, ids, load, pack_errors, text_of, write_pack


def files_with(**changes):
    files = default_files()
    files.update(changes)
    return files


def check_error(tmp_path, registry, files, *needles):
    errors = pack_errors(write_pack(tmp_path, files), registry)
    assert errors is not None
    text = text_of(errors)
    for needle in needles:
        assert needle in text, text


# валидный пак

def test_minimal_pack_loads(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert pack.manifest.id == "mini"
    assert pack.manifest.name == "Мини"
    assert pack.manifest.version == "1.0"


def test_pack_entities_are_lists_in_file_order(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert ids(pack.locations) == ["town", "tavern", "cellar"]
    assert ids(pack.pantheon) == ["selune"]
    assert ids(pack.factions) == ["guild"]
    assert ids(pack.npcs) == ["aldric", "guard"]
    assert ids(pack.heroes) == ["arn"]


def test_pack_texts_are_read(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert "город с таверной" in pack.world_text
    assert "сырой" in pack.truths


def test_pack_without_optional_files_loads(tmp_path, registry):
    files = files_with(**{"truths.md": None, "npcs.yaml": None, "factions.yaml": None,
                          "pantheon.yaml": None})
    pack = load(write_pack(tmp_path, files), registry)
    assert pack.truths == ""
    assert pack.npcs == []
    assert pack.factions == []
    assert pack.pantheon == []


def test_trigger_and_secret_are_loaded_into_npc(tmp_path, registry):
    aldric = load(write_pack(tmp_path), registry).npcs[0]
    assert aldric.opportunity[0].id == "steal"
    assert aldric.opportunity[0].once is True
    assert aldric.secrets[0].id == "sister"


def test_manifest_defaults(tmp_path, registry):
    manifest = load(write_pack(tmp_path), registry).manifest
    assert manifest.start.time == "08:00"
    assert manifest.start.chapter.number == 1
    assert manifest.mortality.preset == "normal"
    assert manifest.natural_events.chance_percent_per_season == 5
    assert manifest.nudge.scenes == 8
    assert manifest.calendar is None


def test_start_section_is_parsed(tmp_path, registry):
    start = load(write_pack(tmp_path), registry).manifest.start
    assert start.date == "0100-03-01"
    assert start.hero_location == "tavern"
    assert start.heroes == ["arn"]


def test_hero_preset_is_built_from_yaml(tmp_path, registry):
    preset = load(write_pack(tmp_path), registry).heroes[0]
    assert preset.id == "arn"
    assert preset.choices.name == "Арн"
    assert preset.location_id == "tavern"


def test_start_memory_and_chronicle_are_read(tmp_path, registry):
    files = files_with(**{
        "start/memory.yaml": {"game_summary": "Герой пришёл в город."},
        "start/chronicle.yaml": {"entries": [{"at_s": 0, "kind": "event", "text": "Начало"}]},
    })
    pack = load(write_pack(tmp_path, files), registry)
    assert pack.start_memory.game_summary == "Герой пришёл в город."
    assert pack.start_chronicle.entries[0].text == "Начало"


def test_calendar_10x36_from_campaign_yaml(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": f"М{i}", "days": 36} for i in range(1, 11)],
        "seasons": [{"name": "холод", "months": [1, 2, 3, 4, 5]},
                    {"name": "тепло", "months": [6, 7, 8, 9, 10]}],
        "holidays": [{"month": 2, "day": 36, "name": "Свеча"}],
    }
    calendar = load(write_pack(tmp_path, files), registry).manifest.calendar
    assert calendar.days_in_year == 360
    assert calendar.holidays[0].name == "Свеча"


# обязательные файлы

def test_missing_campaign_yaml_is_error(tmp_path, registry):
    check_error(tmp_path, registry, files_with(**{"campaign.yaml": None}), "campaign.yaml")


def test_missing_world_md_is_error(tmp_path, registry):
    check_error(tmp_path, registry, files_with(**{"world.md": None}), "world.md")


def pack_without_heroes(**changes):
    files = files_with(**{"heroes/arn.yaml": None}, **changes)
    files["campaign.yaml"]["start"]["heroes"] = []
    return files


def test_pack_without_heroes_loads(tmp_path, registry):
    pack = load(write_pack(tmp_path, pack_without_heroes()), registry)
    assert pack.heroes == []
    assert pack.manifest.start.heroes == []


def test_pack_without_heroes_directory_loads(tmp_path, registry):
    files = pack_without_heroes()
    pack_dir = write_pack(tmp_path, files)
    assert not (pack_dir / "heroes").exists()
    assert pack_errors(pack_dir, registry) is None


def test_pack_without_heroes_keeps_other_entities(tmp_path, registry):
    pack = load(write_pack(tmp_path, pack_without_heroes()), registry)
    assert ids(pack.npcs) == ["aldric", "guard"]
    assert ids(pack.locations) == ["town", "tavern", "cellar"]


def test_pack_without_heroes_still_checks_manifest_start_location(tmp_path, registry):
    files = pack_without_heroes()
    files["campaign.yaml"]["start"]["hero_location"] = "nowhere"
    check_error(tmp_path, registry, files, "hero_location", "nowhere")


def test_broken_yaml_is_error_with_file(tmp_path, registry):
    files = files_with(**{"npcs.yaml": "- id: [незакрытый\n"})
    check_error(tmp_path, registry, files, "npcs.yaml")


# extra="forbid"

def test_unknown_key_in_campaign_yaml_is_error(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["bogus"] = 1
    check_error(tmp_path, registry, files, "campaign.yaml", "bogus")


def test_unknown_key_in_npc_is_error(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][1]["bogus"] = 1
    check_error(tmp_path, registry, files, "npcs.yaml", "bogus")


def test_unknown_key_in_location_is_error(tmp_path, registry):
    files = default_files()
    files["locations.yaml"][0]["bogus"] = 1
    check_error(tmp_path, registry, files, "locations.yaml", "bogus")


def test_unknown_condition_kind_in_trigger_is_error_with_path(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["opportunity"][0]["if"] = {"phase_of_moon": "full"}
    check_error(tmp_path, registry, files, "npcs.yaml", "phase_of_moon")


def test_bad_start_time_is_error(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["time"] = "25:99"
    check_error(tmp_path, registry, files, "campaign.yaml")


def test_unknown_mortality_preset_is_error(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["mortality"] = {"preset": "ужас"}
    check_error(tmp_path, registry, files, "campaign.yaml", "mortality")


def test_bad_hero_choices_are_error_with_file(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["choices"]["class_id"] = "no_such_class"
    check_error(tmp_path, registry, files, "arn.yaml")


# битые ссылки: строка с файлом и полем

def test_trigger_refers_to_unknown_npc(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["opportunity"][0]["if"] = {"npc_status": {"id": "ghost", "is": "alive"}}
    check_error(tmp_path, registry, files, "npcs.yaml", "ghost")


def test_trigger_with_nested_unknown_location(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["opportunity"][0]["if"] = {
        "all": [{"flag": "x"}, {"not": {"hero_at": "nowhere"}}]
    }
    check_error(tmp_path, registry, files, "npcs.yaml", "nowhere")


def test_trigger_with_unknown_item(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["opportunity"][0]["if"] = {"hero_has": "no_such_item"}
    check_error(tmp_path, registry, files, "npcs.yaml", "no_such_item")


def test_god_trigger_refers_to_unknown_god(tmp_path, registry):
    files = default_files()
    files["pantheon.yaml"][0]["opportunity"] = [
        {"id": "t", "if": {"favor": {"god": "nobody", "gte": 3}}, "then": "знамение"}
    ]
    check_error(tmp_path, registry, files, "pantheon.yaml", "nobody")


def test_secret_refers_to_unknown_npc(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["secrets"][0]["reveal_if"] = {"npc_status": {"id": "ghost", "is": "dead"}}
    check_error(tmp_path, registry, files, "npcs.yaml", "ghost")


def test_location_parent_is_unknown(tmp_path, registry):
    files = default_files()
    files["locations.yaml"][2]["parent_id"] = "nowhere"
    check_error(tmp_path, registry, files, "locations.yaml", "parent_id", "nowhere")


def test_location_connection_is_unknown(tmp_path, registry):
    files = default_files()
    files["locations.yaml"][0]["connections"] = [{"to": "nowhere", "distance_m": 5}]
    check_error(tmp_path, registry, files, "locations.yaml", "nowhere")


def test_npc_location_is_unknown(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["location_id"] = "nowhere"
    check_error(tmp_path, registry, files, "npcs.yaml", "location_id", "nowhere")


def test_npc_species_is_unknown(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["species_id"] = "no_such_species"
    check_error(tmp_path, registry, files, "npcs.yaml", "species_id")


def test_faction_member_is_unknown(tmp_path, registry):
    files = default_files()
    files["factions.yaml"][0]["members"] = ["ghost"]
    check_error(tmp_path, registry, files, "factions.yaml", "members", "ghost")


def test_faction_region_is_unknown(tmp_path, registry):
    files = default_files()
    files["factions.yaml"][0]["regions"] = ["nowhere"]
    check_error(tmp_path, registry, files, "factions.yaml", "regions", "nowhere")


def test_god_rival_is_unknown(tmp_path, registry):
    files = default_files()
    files["pantheon.yaml"][0]["rivals"] = ["nobody"]
    check_error(tmp_path, registry, files, "pantheon.yaml", "rivals", "nobody")


def test_event_region_is_unknown(tmp_path, registry):
    files = default_files()
    files["events.yaml"] = [{"id": "plague", "type": "plague", "regions": ["nowhere"],
                             "cause": "season:winter"}]
    check_error(tmp_path, registry, files, "events.yaml", "regions", "nowhere")


def test_event_region_is_location_id(tmp_path, registry):
    files = default_files()
    files["events.yaml"] = [{"id": "plague", "type": "plague", "regions": ["town"],
                             "cause": "season:winter"}]
    assert ids(load(write_pack(tmp_path, files), registry).events) == ["plague"]


def test_start_location_is_unknown(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["hero_location"] = "nowhere"
    check_error(tmp_path, registry, files, "campaign.yaml", "hero_location", "nowhere")


def test_start_hero_preset_is_unknown(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["heroes"] = ["ghost"]
    check_error(tmp_path, registry, files, "campaign.yaml", "ghost")


def test_hero_preset_location_is_unknown(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["location_id"] = "nowhere"
    check_error(tmp_path, registry, files, "arn.yaml", "nowhere")


# средства и возможности пресета героя (шаг 34): правила листа героя

def preset_opportunity(**changes):
    trigger = {"id": "o1", "if": {"hero_at": "tavern"}, "then": "делает дело", "once": True}
    trigger.update(changes)
    return trigger


def test_hero_preset_means_four_items_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["means"] = ["а", "б", "в", "г"]
    check_error(tmp_path, registry, files, "arn.yaml", "means", "от одного до трёх")


def test_hero_preset_means_item_too_long_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["means"] = ["я" * 121]
    check_error(tmp_path, registry, files, "arn.yaml", "means", "длиннее 120")


def test_hero_preset_empty_means_is_valid(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["means"] = []
    assert ids(load(write_pack(tmp_path, files), registry).heroes) == ["arn"]


def test_hero_preset_valid_means_and_opportunity_load(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["means"] = ["а", "б", "в"]
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity()]
    preset = load(write_pack(tmp_path, files), registry).heroes[0]
    assert preset.means == ["а", "б", "в"]
    assert [t.id for t in preset.opportunity] == ["o1"]


def test_hero_preset_three_opportunities_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [
        preset_opportunity(id="o1"), preset_opportunity(id="o2"), preset_opportunity(id="o3"),
    ]
    check_error(tmp_path, registry, files, "arn.yaml", "opportunity", "не больше 2")


def test_hero_preset_repeated_opportunity_id_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(), preset_opportunity()]
    check_error(tmp_path, registry, files, "arn.yaml", "opportunity", "повторный id")


def test_hero_preset_empty_then_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(then="")]
    check_error(tmp_path, registry, files, "arn.yaml", "opportunity", "намерение")


def test_hero_preset_opportunity_unknown_location_is_error(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(**{"if": {"hero_at": "nowhere"}})]
    check_error(tmp_path, registry, files, "arn.yaml", "неизвестная локация 'nowhere'")


def test_hero_preset_opportunity_unknown_npc_is_error(tmp_path, registry):
    files = default_files()
    cond = {"npc_status": {"id": "ghost", "is": "alive"}}
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(**{"if": cond})]
    check_error(tmp_path, registry, files, "arn.yaml", "неизвестный NPC 'ghost'")


def test_hero_preset_opportunity_unknown_god_is_error(tmp_path, registry):
    files = default_files()
    cond = {"favor": {"god": "nobody", "gte": 1}}
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(**{"if": cond})]
    check_error(tmp_path, registry, files, "arn.yaml", "неизвестный бог 'nobody'")


def test_hero_preset_opportunity_unknown_item_is_error(tmp_path, registry):
    files = default_files()
    cond = {"hero_has": "no_such"}
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(**{"if": cond})]
    check_error(tmp_path, registry, files, "arn.yaml", "неизвестный предмет 'no_such'")


def test_hero_preset_opportunity_known_refs_are_valid(tmp_path, registry):
    files = default_files()
    cond = {"all": [{"hero_at": "cellar"}, {"npc_status": {"id": "aldric", "is": "alive"}},
                    {"favor": {"god": "selune", "gte": 1}}]}
    files["heroes/arn.yaml"]["opportunity"] = [preset_opportunity(**{"if": cond})]
    assert ids(load(write_pack(tmp_path, files), registry).heroes) == ["arn"]


def test_hero_preset_opportunity_flag_and_narrative_have_no_refs(tmp_path, registry):
    files = default_files()
    files["heroes/arn.yaml"]["opportunity"] = [
        preset_opportunity(id="o1", **{"if": {"flag": "anything"}}),
        preset_opportunity(id="o2", **{"if": {"narrative": "случилось нечто"}}),
    ]
    assert ids(load(write_pack(tmp_path, files), registry).heroes) == ["arn"]


# календарь пака

def test_holiday_31st_in_30_day_month_is_error(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["date"] = "0100-01-01"
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": "А", "days": 30}, {"name": "Б", "days": 30}],
        "seasons": [{"name": "х", "months": [1, 2]}],
        "holidays": [{"month": 1, "day": 31, "name": "Не бывает"}],
    }
    check_error(tmp_path, registry, files, "campaign.yaml")


def test_holiday_god_must_exist_in_pantheon(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["date"] = "0100-01-01"
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": "А", "days": 30}],
        "seasons": [{"name": "х", "months": [1]}],
        "holidays": [{"month": 1, "day": 5, "name": "Свеча", "god_id": "nobody"}],
    }
    check_error(tmp_path, registry, files, "campaign.yaml", "nobody")


def test_holiday_of_existing_god_is_ok(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["start"]["date"] = "0100-01-01"
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": "А", "days": 30}],
        "seasons": [{"name": "х", "months": [1]}],
        "holidays": [{"month": 1, "day": 5, "name": "Свеча", "god_id": "selune"}],
    }
    pack = load(write_pack(tmp_path, files), registry)
    assert pack.manifest.calendar.holidays[0].god_id == "selune"


def test_start_date_must_exist_in_pack_calendar(tmp_path, registry):
    files = default_files()
    files["campaign.yaml"]["calendar"] = {
        "months": [{"name": "А", "days": 30}],
        "seasons": [{"name": "х", "months": [1]}],
    }
    files["campaign.yaml"]["start"]["date"] = "0100-02-01"
    check_error(tmp_path, registry, files, "campaign.yaml")


# все ошибки сразу

def test_several_errors_are_reported_together(tmp_path, registry):
    files = default_files()
    files["locations.yaml"][2]["parent_id"] = "nowhere"
    files["factions.yaml"][0]["members"] = ["ghost"]
    errors = pack_errors(write_pack(tmp_path, files), registry)
    text = text_of(errors)
    assert "nowhere" in text
    assert "ghost" in text


# К0а (BACKLOG 16, старые мутанты check_pack_refs): файл в строке ошибки и причина события

TRIGGER = {"id": "t1", "if": {"flag": "x"}, "then": "что-то"}


def event_files(cause, owner_file=None, owner_index=0):
    files = default_files()
    if owner_file is not None:
        files[owner_file][owner_index]["opportunity"] = [TRIGGER]
    files["events.yaml"] = [{"id": "war", "type": "war", "regions": ["town"], "cause": cause}]
    return files


def test_unknown_location_ref_names_locations_file(tmp_path, registry):
    files = default_files()
    files["locations.yaml"][1]["parent_id"] = "nowhere"
    check_error(tmp_path, registry, files, "locations.yaml: location 'tavern'", "parent_id")


def test_unknown_god_ref_names_pantheon_file(tmp_path, registry):
    files = default_files()
    files["pantheon.yaml"][0]["rivals"] = ["nobody"]
    check_error(tmp_path, registry, files, "pantheon.yaml: god 'selune'")


def test_unknown_faction_ref_names_factions_file(tmp_path, registry):
    files = default_files()
    files["factions.yaml"][0]["members"] = ["ghost"]
    check_error(tmp_path, registry, files, "factions.yaml: faction 'guild'")


def test_unknown_npc_ref_names_npcs_file(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"][0]["location_id"] = "nowhere"
    check_error(tmp_path, registry, files, "npcs.yaml: npc 'aldric'")


def test_unknown_event_ref_names_events_file(tmp_path, registry):
    files = default_files()
    files["events.yaml"] = [{"id": "plague", "type": "plague", "regions": ["nowhere"],
                             "cause": "season:winter"}]
    check_error(tmp_path, registry, files, "events.yaml: event 'plague'")


def test_event_cause_with_existing_npc_trigger_is_fine(tmp_path, registry):
    pack = load(write_pack(tmp_path, event_files("trigger:aldric:steal")), registry)
    assert ids(pack.events) == ["war"]


def test_event_cause_with_existing_faction_trigger_is_fine(tmp_path, registry):
    files = event_files("trigger:guild:t1", "factions.yaml")
    assert ids(load(write_pack(tmp_path, files), registry).events) == ["war"]


def test_event_cause_with_existing_god_trigger_is_fine(tmp_path, registry):
    files = event_files("trigger:selune:t1", "pantheon.yaml")
    assert ids(load(write_pack(tmp_path, files), registry).events) == ["war"]


def test_event_cause_with_unknown_trigger_of_known_owner_is_an_error(tmp_path, registry):
    check_error(
        tmp_path, registry, event_files("trigger:aldric:nope"),
        "events.yaml: event 'war', поле cause: нет триггера 'trigger:aldric:nope'",
    )


def test_event_cause_with_unknown_owner_is_an_error(tmp_path, registry):
    check_error(tmp_path, registry, event_files("trigger:ghost:steal"), "нет триггера", "ghost")


def test_event_cause_trigger_of_another_owner_is_an_error(tmp_path, registry):
    files = event_files("trigger:guild:steal")
    check_error(tmp_path, registry, files, "нет триггера 'trigger:guild:steal'")


def test_event_cause_of_another_form_is_not_checked(tmp_path, registry):
    files = event_files("season:winter")
    assert ids(load(write_pack(tmp_path, files), registry).events) == ["war"]


def test_event_without_cause_is_fine(tmp_path, registry):
    files = default_files()
    files["events.yaml"] = [{"id": "war", "type": "war", "regions": ["town"]}]
    assert ids(load(write_pack(tmp_path, files), registry).events) == ["war"]


# ТБ #56 (docs/plan-tb.md п.2): поле manifest.monsters -- монстры пака для рассказчика

def with_monsters(monsters, npc_monster=None):
    files = default_files()
    if monsters is not None:
        files["campaign.yaml"]["monsters"] = monsters
    if npc_monster is not None:
        files["npcs.yaml"][1]["combat"] = {"monster_id": npc_monster, "intent": "kill"}
    return files


def test_manifest_monsters_default_is_empty_list(tmp_path, registry):
    assert load(write_pack(tmp_path), registry).manifest.monsters == []


def test_manifest_monsters_list_is_read(tmp_path, registry):
    pack = load(write_pack(tmp_path, with_monsters(["wolf", "boar"])), registry)
    assert pack.manifest.monsters == ["wolf", "boar"]


def test_pack_with_valid_monsters_loads(tmp_path, registry):
    assert pack_errors(write_pack(tmp_path, with_monsters(["wolf", "guard"])), registry) is None


def test_unknown_monster_in_manifest_is_error_with_file_field_and_id(tmp_path, registry):
    files = with_monsters(["wolf", "no_such_monster"])
    check_error(tmp_path, registry, files, "campaign.yaml", "monsters", "no_such_monster")


def test_each_unknown_monster_gets_own_error_line(tmp_path, registry):
    errors = pack_errors(write_pack(tmp_path, with_monsters(["zz_a", "zz_b"])), registry)
    assert [e for e in errors if "zz_a" in e] and [e for e in errors if "zz_b" in e]


def test_npc_monster_outside_nonempty_list_is_error(tmp_path, registry):
    files = with_monsters(["wolf"], npc_monster="goblin_boss")
    check_error(tmp_path, registry, files, "guard", "goblin_boss")


def test_npc_monster_inside_list_is_ok(tmp_path, registry):
    files = with_monsters(["wolf", "goblin_boss"], npc_monster="goblin_boss")
    assert pack_errors(write_pack(tmp_path, files), registry) is None


def test_npc_monster_with_empty_list_is_ok(tmp_path, registry):
    files = with_monsters(None, npc_monster="goblin_boss")
    assert pack_errors(write_pack(tmp_path, files), registry) is None


def test_check_manifest_monsters_clean_pack_gives_no_lines(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest_monsters

    pack = load(write_pack(tmp_path, with_monsters(["wolf"])), registry)
    assert check_manifest_monsters(pack, registry) == []


def test_check_manifest_monsters_reports_unknown_id(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest_monsters

    pack = load(write_pack(tmp_path, with_monsters(["wolf"])), registry)
    pack.manifest.monsters = ["wolf", "ghost_x"]
    lines = check_manifest_monsters(pack, registry)
    assert len(lines) == 1
    assert "campaign.yaml" in lines[0]
    assert "monsters" in lines[0]
    assert "'ghost_x'" in lines[0]


def test_check_manifest_monsters_unknown_id_line_starts_with_manifest_path(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest_monsters

    pack = load(write_pack(tmp_path, with_monsters(["wolf"])), registry)
    pack.manifest.monsters = ["ghost_x"]
    lines = check_manifest_monsters(pack, registry)
    assert lines[0].startswith(f"{pack.path}/campaign.yaml:")


def test_check_manifest_monsters_npc_outside_list_line_starts_with_npcs_path(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest_monsters

    files = with_monsters(["wolf", "goblin_boss"], npc_monster="goblin_boss")
    pack = load(write_pack(tmp_path, files), registry)
    pack.manifest.monsters = ["wolf"]
    lines = check_manifest_monsters(pack, registry)
    assert len(lines) == 1
    assert lines[0].startswith(f"{pack.path}/npcs.yaml:")
    assert "'goblin_boss'" in lines[0]


def test_check_manifest_monsters_empty_list_skips_npc_check(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest_monsters

    pack = load(write_pack(tmp_path, with_monsters(None, npc_monster="goblin_boss")), registry)
    assert check_manifest_monsters(pack, registry) == []


def test_check_manifest_includes_monsters_check(tmp_path, registry):
    from ai_dm.campaign.loader import check_manifest

    pack = load(write_pack(tmp_path), registry)
    pack.manifest.monsters = ["ghost_x"]
    assert any("ghost_x" in line for line in check_manifest(pack, registry))


# pack_monster_scope: читает только campaign.yaml, None -- «без фильтра»

def scope_of(pack_dir):
    from ai_dm.campaign.loader import pack_monster_scope

    return pack_monster_scope(pack_dir)


def test_pack_monster_scope_returns_list(tmp_path, registry):
    assert scope_of(write_pack(tmp_path, with_monsters(["wolf", "boar"]))) == ["wolf", "boar"]


def test_pack_monster_scope_without_field_is_none(tmp_path, registry):
    assert scope_of(write_pack(tmp_path)) is None


def test_pack_monster_scope_empty_list_is_none(tmp_path, registry):
    assert scope_of(write_pack(tmp_path, with_monsters([]))) is None


def test_pack_monster_scope_missing_dir_is_none(tmp_path):
    assert scope_of(tmp_path / "nowhere") is None


def test_pack_monster_scope_without_campaign_yaml_is_none(tmp_path):
    (tmp_path / "bare").mkdir()
    assert scope_of(tmp_path / "bare") is None


def test_pack_monster_scope_broken_yaml_is_none(tmp_path):
    pack_dir = write_pack(tmp_path, files_with(**{"campaign.yaml": "id: [незакрытый\n"}))
    assert scope_of(pack_dir) is None


def test_pack_monster_scope_non_mapping_yaml_is_none(tmp_path):
    pack_dir = write_pack(tmp_path, files_with(**{"campaign.yaml": "- a\n- b\n"}))
    assert scope_of(pack_dir) is None


def test_pack_monster_scope_invalid_manifest_is_none(tmp_path):
    files = with_monsters(["wolf"])
    files["campaign.yaml"]["bogus"] = 1
    assert scope_of(write_pack(tmp_path, files)) is None


def test_pack_monster_scope_reads_only_campaign_yaml(tmp_path):
    files = with_monsters(["wolf"])
    files["locations.yaml"] = "- id: [незакрытый\n"
    files["world.md"] = None
    assert scope_of(write_pack(tmp_path, files)) == ["wolf"]


def test_pack_monster_scope_keeps_manifest_order(tmp_path):
    assert scope_of(write_pack(tmp_path, with_monsters(["wolf", "boar", "guard"]))) == [
        "wolf", "boar", "guard",
    ]
