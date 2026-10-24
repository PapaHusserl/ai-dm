# Уникальность сущностей пака (этап 3, партия 1; STAGE3-PLAN A2, ТЗ 5.3, Т-5).
# collect_conflicts(world, heroes, pack) -> (accepted, conflicts): сущности добавляются по одной
# в порядке локации -> боги -> фракции -> NPC (внутри -- порядок файла); конфликтная не
# загружается и попадает в список Conflict{file, kind, id, name, reason}; ссылающиеся на
# отброшенную тоже отбрасываются со строкой «ссылается на отброшенную X» (транзитивно).
from types import SimpleNamespace

from campaign_kit import default_files, empty_world, ids, load, write_pack

HEROES = [SimpleNamespace(id="hero", name="Герой")]


def collect(tmp_path, registry, files=None, heroes=HEROES):
    from ai_dm.campaign.uniqueness import collect_conflicts

    pack = load(write_pack(tmp_path, files), registry)
    return collect_conflicts(empty_world(), heroes, pack)


def conflict_of(conflicts, entity_id):
    found = [c for c in conflicts if c.id == entity_id]
    assert len(found) == 1, conflicts
    return found[0]


def test_clean_pack_has_no_conflicts(tmp_path, registry):
    accepted, conflicts = collect(tmp_path, registry)
    assert conflicts == []
    assert ids(accepted.locations) == ["town", "tavern", "cellar"]
    assert ids(accepted.pantheon) == ["selune"]
    assert ids(accepted.factions) == ["guild"]
    assert ids(accepted.npcs) == ["aldric", "guard"]


def test_npc_id_equal_to_location_id_is_dropped(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"].append({"id": "tavern", "name": "Хозяин", "named": True, "means": ["ключ"]})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "tavern" not in ids(accepted.npcs)
    assert "tavern" in ids(accepted.locations)
    conflict = conflict_of(conflicts, "tavern")
    assert conflict.kind == "npc"
    assert conflict.file == "npcs.yaml"
    assert conflict.name == "Хозяин"
    assert "tavern" in conflict.reason


def test_two_npcs_with_one_name_second_is_dropped(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"].append({"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert ids(accepted.npcs) == ["aldric", "guard"]
    assert "Олдрик" in conflict_of(conflicts, "twin").reason


def test_unnamed_npcs_may_share_a_name(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"].append({"id": "guard_2", "name": "Стражник", "means": ["меч"]})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert conflicts == []
    assert "guard_2" in ids(accepted.npcs)


def test_npc_with_hero_name_is_dropped(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"].append({"id": "double", "name": "Герой", "named": True, "means": ["меч"]})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "double" not in ids(accepted.npcs)
    assert "Герой" in conflict_of(conflicts, "double").reason


def test_same_location_name_under_different_parents_is_dropped(tmp_path, registry):
    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "cellar"})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "tavern_2" not in ids(accepted.locations)
    assert conflict_of(conflicts, "tavern_2").kind == "location"


def test_same_location_name_under_one_parent_is_dropped(tmp_path, registry):
    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "town"})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "tavern_2" not in ids(accepted.locations)
    conflict = conflict_of(conflicts, "tavern_2")
    assert conflict.kind == "location"
    assert conflict.file == "locations.yaml"


def test_faction_with_god_name_is_dropped(tmp_path, registry):
    files = default_files()
    files["factions.yaml"].append({"id": "church", "name": "Селунэ"})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert ids(accepted.pantheon) == ["selune"]
    assert "church" not in ids(accepted.factions)
    assert conflict_of(conflicts, "church").kind == "faction"


def test_god_with_faction_name_is_dropped_first_wins_by_order(tmp_path, registry):
    # порядок: боги раньше фракций, значит фракция проигрывает, а бог остаётся
    files = default_files()
    files["pantheon.yaml"].append({"id": "thief_god", "name": "Гильдия воров"})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "thief_god" in ids(accepted.pantheon)
    assert ids(accepted.factions) == []
    assert conflict_of(conflicts, "guild").kind == "faction"


def test_god_id_equal_to_npc_id_drops_the_npc(tmp_path, registry):
    files = default_files()
    files["pantheon.yaml"].append({"id": "guard", "name": "Страж богов"})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "guard" in ids(accepted.pantheon)
    assert "guard" not in ids(accepted.npcs)
    assert conflict_of(conflicts, "guard").kind == "npc"


def test_entity_referring_to_dropped_one_is_dropped_too(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"] += [
        {"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]},
        {"id": "bob", "name": "Боб", "named": True, "means": ["меч"],
         "opportunity": [{"id": "t", "if": {"npc_status": {"id": "twin", "is": "dead"}},
                          "then": "мстит"}]},
    ]
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "bob" not in ids(accepted.npcs)
    reason = conflict_of(conflicts, "bob").reason
    assert "ссылается на отброшенную" in reason
    assert "twin" in reason


def test_dropping_is_transitive(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"] += [
        {"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]},
        {"id": "bob", "name": "Боб", "named": True, "means": ["меч"],
         "opportunity": [{"id": "t", "if": {"npc_status": {"id": "twin", "is": "dead"}},
                          "then": "мстит"}]},
        {"id": "carol", "name": "Кэрол", "named": True, "means": ["меч"],
         "opportunity": [{"id": "t", "if": {"npc_status": {"id": "bob", "is": "dead"}},
                          "then": "плачет"}]},
    ]
    accepted, conflicts = collect(tmp_path, registry, files)
    assert ids(accepted.npcs) == ["aldric", "guard"]
    assert "bob" in conflict_of(conflicts, "carol").reason


def test_faction_with_dropped_member_is_dropped(tmp_path, registry):
    files = default_files()
    files["npcs.yaml"].append({"id": "twin", "name": "Олдрик", "named": True, "means": ["меч"]})
    files["factions.yaml"].append({"id": "gang", "name": "Банда", "members": ["twin"]})
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "gang" not in ids(accepted.factions)
    assert "twin" in conflict_of(conflicts, "gang").reason


def test_dropped_start_location_is_in_conflicts(tmp_path, registry):
    files = default_files()
    files["locations.yaml"].append({"id": "tavern_2", "name": "Таверна", "parent_id": "town"})
    files["campaign.yaml"]["start"]["hero_location"] = "tavern_2"
    accepted, conflicts = collect(tmp_path, registry, files)
    assert "tavern_2" not in ids(accepted.locations)
    assert conflict_of(conflicts, "tavern_2").kind == "location"


def test_conflicts_against_existing_world(tmp_path, registry):
    from ai_dm.campaign.uniqueness import collect_conflicts
    from ai_dm.state.world import NPC

    pack = load(write_pack(tmp_path), registry)
    world = empty_world()
    world.npcs["aldric"] = NPC(id="aldric", name="Уже тут", named=True, means=["меч"])
    accepted, conflicts = collect_conflicts(world, HEROES, pack)
    assert "aldric" not in ids(accepted.npcs)
    assert conflict_of(conflicts, "aldric").kind == "npc"


def test_dropping_does_not_touch_entities_already_in_world(tmp_path, registry):
    # R3: id есть в мире -- ссылка на него допустима, даже если одноимённая сущность пака отброшена
    from ai_dm.campaign.uniqueness import collect_conflicts
    from ai_dm.state.world import NPC

    files = default_files()
    files["npcs.yaml"] += [
        {"id": "old", "name": "Старый", "named": True, "means": ["меч"]},
        {"id": "bob", "name": "Боб", "named": True, "means": ["меч"],
         "opportunity": [{"id": "t", "if": {"npc_status": {"id": "old", "is": "dead"}},
                          "then": "мстит"}]},
    ]
    pack = load(write_pack(tmp_path, files), registry)
    world = empty_world()
    world.npcs["old"] = NPC(id="old", name="Уже в мире", named=True, means=["меч"])
    accepted, conflicts = collect_conflicts(world, HEROES, pack)
    assert "bob" in ids(accepted.npcs)
    assert [c.id for c in conflicts if c.id in ("old", "bob")] == ["old"]
