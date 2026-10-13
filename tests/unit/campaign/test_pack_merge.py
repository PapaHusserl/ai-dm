# Догрузка новых сущностей пака в идущий мир (этап 3, партия 1; STAGE3-PLAN A2, Т-6).
# merge_new(bundle, pack) -> report (.added, .conflicts): новые = id нет в world.npcs / factions /
# pantheon / locations / events; существующие не меняются; новые проходят уникальность против
# текущего мира (включая origin: ai); добавленные -- запись хроники kind "pack_update",
# world.campaign_version = версия пака; идемпотентно; world.md / truths.md не обновляются.
from campaign_kit import (
    arn_choices,
    bundle_from_world,
    default_files,
    ids,
    load,
    world_from_pack,
    write_pack,
)

NEW_NPC = {"id": "brana", "name": "Бранка", "named": True, "means": ["топор"],
           "location_id": "tavern"}


def v1_bundle(tmp_path, registry):
    pack = load(write_pack(tmp_path / "v1"), registry)
    return bundle_from_world(world_from_pack(pack))


def v2_pack(tmp_path, registry, edit):
    files = default_files()
    files["campaign.yaml"]["version"] = "2.0"
    edit(files)
    return load(write_pack(tmp_path / "v2", files), registry)


def merge(bundle, pack):
    from ai_dm.campaign.merge import merge_new

    return merge_new(bundle, pack)


def test_same_pack_gives_empty_report(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    before = bundle.model_dump()
    report = merge(bundle, load(write_pack(tmp_path / "again"), registry))
    assert report.added == []
    assert report.conflicts == []
    assert bundle.model_dump() == before


def test_new_npc_appears_in_world(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    report = merge(bundle, pack)
    assert "brana" in bundle.world.npcs
    assert bundle.world.npcs["brana"].name == "Бранка"
    assert report.added != []
    assert report.conflicts == []


def test_merge_writes_pack_update_to_chronicle(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    merge(bundle, pack)
    kinds = [entry.kind for entry in bundle.chronicle.entries]
    assert kinds != []
    assert set(kinds) == {"pack_update"}
    texts = " ".join(entry.text + " ".join(entry.refs) for entry in bundle.chronicle.entries)
    assert "Бранка" in texts or "brana" in texts


def test_merge_sets_campaign_version(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    assert bundle.world.campaign_version == "1.0"
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    merge(bundle, pack)
    assert bundle.world.campaign_version == "2.0"


def test_new_location_faction_and_god_are_added(tmp_path, registry):
    def edit(files):
        files["locations.yaml"].append({"id": "port", "name": "Порт"})
        files["factions.yaml"].append({"id": "navy", "name": "Флот"})
        files["pantheon.yaml"].append({"id": "umberlee", "name": "Амберли"})

    bundle = v1_bundle(tmp_path, registry)
    merge(bundle, v2_pack(tmp_path, registry, edit))
    assert "port" in bundle.world.locations
    assert "navy" in bundle.world.factions
    assert "umberlee" in bundle.world.pantheon


def test_new_event_is_added(tmp_path, registry):
    def edit(files):
        files["events.yaml"] = [{"id": "war", "type": "war", "regions": ["town"],
                                 "cause": "trigger:aldric:steal"}]

    bundle = v1_bundle(tmp_path, registry)
    merge(bundle, v2_pack(tmp_path, registry, edit))
    assert ids(bundle.world.events) == ["war"]


def test_existing_npc_changed_in_pack_stays_as_in_world(tmp_path, registry):
    def edit(files):
        files["npcs.yaml"][0]["motive"] = "новый мотив из пака"
        files["npcs.yaml"][0]["means"] = ["совсем другое"]

    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].attitude = 40
    merge(bundle, v2_pack(tmp_path, registry, edit))
    aldric = bundle.world.npcs["aldric"]
    assert aldric.motive == ""
    assert aldric.means == ["связи"]
    assert aldric.attitude == 40


def test_npc_removed_from_pack_stays_in_world(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].pop(1))
    merge(bundle, pack)
    assert "guard" in bundle.world.npcs


def test_npc_with_id_of_ai_npc_is_not_new_and_report_is_empty(tmp_path, registry):
    from ai_dm.state.world import NPC

    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["brana"] = NPC(
        id="brana", name="Придуманная ИИ", named=True, means=["лук"], origin="ai"
    )
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    report = merge(bundle, pack)
    assert report.added == []
    assert report.conflicts == []
    assert bundle.world.npcs["brana"].name == "Придуманная ИИ"
    assert bundle.world.npcs["brana"].origin == "ai"


def test_new_npc_with_name_of_ai_npc_is_conflict(tmp_path, registry):
    from ai_dm.state.world import NPC

    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["ai_branka"] = NPC(
        id="ai_branka", name="Бранка", named=True, means=["лук"], origin="ai"
    )
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    report = merge(bundle, pack)
    assert [c.id for c in report.conflicts] == ["brana"]
    assert "brana" not in bundle.world.npcs


def test_conflicting_new_entity_is_not_added_but_others_are(tmp_path, registry):
    def edit(files):
        files["npcs.yaml"] += [
            {"id": "clash", "name": "Олдрик", "named": True, "means": ["меч"]},
            NEW_NPC,
        ]

    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, v2_pack(tmp_path, registry, edit))
    assert "clash" not in bundle.world.npcs
    assert "brana" in bundle.world.npcs
    assert [c.id for c in report.conflicts] == ["clash"]


def test_new_entity_referring_to_conflicting_one_is_dropped(tmp_path, registry):
    def edit(files):
        files["npcs.yaml"] += [
            {"id": "clash", "name": "Олдрик", "named": True, "means": ["меч"]},
            {"id": "fan", "name": "Фанат", "named": True, "means": ["нож"],
             "opportunity": [{"id": "t", "if": {"npc_status": {"id": "clash", "is": "dead"}},
                              "then": "плачет"}]},
        ]

    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, v2_pack(tmp_path, registry, edit))
    assert "fan" not in bundle.world.npcs
    assert {c.id for c in report.conflicts} == {"clash", "fan"}


def test_new_trigger_may_refer_to_existing_world_entities(tmp_path, registry):
    def edit(files):
        files["npcs.yaml"].append(dict(NEW_NPC, opportunity=[
            {"id": "t", "if": {"npc_status": {"id": "aldric", "is": "dead"}}, "then": "скорбит"}
        ]))

    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, v2_pack(tmp_path, registry, edit))
    assert report.conflicts == []
    assert bundle.world.npcs["brana"].opportunity[0].id == "t"


def test_second_merge_is_empty_and_changes_nothing(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    pack = v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC))
    merge(bundle, pack)
    after_first = bundle.model_dump()
    report = merge(bundle, pack)
    assert report.added == []
    assert report.conflicts == []
    assert bundle.model_dump() == after_first


def test_lore_text_is_not_updated_by_merge(tmp_path, registry):
    def edit(files):
        files["world.md"] = "Совсем новый текст мира.\n"
        files["npcs.yaml"].append(NEW_NPC)

    bundle = v1_bundle(tmp_path, registry)
    bundle.world.lore.world_text = "Старый текст мира"
    merge(bundle, v2_pack(tmp_path, registry, edit))
    assert bundle.world.lore.world_text == "Старый текст мира"


def test_empty_lore_is_filled_from_pack_on_merge(tmp_path, registry):
    # R1: мир после миграции без текста мира -- догрузка заполняет его, только если пуст
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.lore.world_text = ""
    merge(bundle, load(write_pack(tmp_path / "again"), registry))
    assert "город с таверной" in bundle.world.lore.world_text


def test_merge_fills_empty_tags_of_existing_pack_npc(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    npc_id = next(iter(bundle.world.npcs))
    assert bundle.world.npcs[npc_id].tags == []

    def edit(files):
        for npc in files["npcs.yaml"]:
            if npc["id"] == npc_id:
                npc["tags"] = ["mor"]

    report = merge(bundle, v2_pack(tmp_path, registry, edit))
    assert bundle.world.npcs[npc_id].tags == ["mor"]
    assert f"tags:{npc_id}" in report.added


def test_merge_does_not_overwrite_existing_tags(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    npc_id = next(iter(bundle.world.npcs))
    bundle.world.npcs[npc_id].tags = ["undead"]

    def edit(files):
        for npc in files["npcs.yaml"]:
            if npc["id"] == npc_id:
                npc["tags"] = ["mor"]

    merge(bundle, v2_pack(tmp_path, registry, edit))
    assert bundle.world.npcs[npc_id].tags == ["undead"]


# пол из пака у миров до К0-фикс-б (Ф1, BACKLOG 43): fill_identity в merge_new

def gender_pack(tmp_path, registry, gender="female", pronouns="она, госпожа", hero_gender=None,
                hero_name=None):
    files = default_files()
    files["npcs.yaml"][0]["gender"] = gender
    files["npcs.yaml"][0]["pronouns"] = pronouns
    if hero_gender is not None:
        choices = files["heroes/arn.yaml"]["choices"]
        choices["gender"] = hero_gender
        choices["pronouns"] = "он"
        if hero_name is not None:
            choices["name"] = hero_name
    return load(write_pack(tmp_path / "gender", files), registry)


def world_hero(registry):
    from ai_dm.rules.builder import CharacterChoices, build_character

    return build_character(CharacterChoices(**arn_choices()), registry)


def test_old_world_npc_gets_gender_and_pronouns_from_pack(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, gender_pack(tmp_path, registry))
    aldric = bundle.world.npcs["aldric"]
    assert (aldric.gender, aldric.pronouns) == ("female", "она, госпожа")
    assert "gender:aldric" in report.added


def test_npc_gender_fill_touches_nothing_else(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].attitude = 40
    before = bundle.world.npcs["aldric"].model_dump()
    merge(bundle, gender_pack(tmp_path, registry))
    after = bundle.world.npcs["aldric"].model_dump()
    for key in ("gender", "pronouns"):
        before.pop(key)
        after.pop(key)
    assert after == before


def test_npc_gender_set_by_narrator_is_not_overwritten(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].gender = "male"
    report = merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.world.npcs["aldric"].gender == "male"
    assert bundle.world.npcs["aldric"].pronouns == ""
    assert "gender:aldric" not in report.added


def test_npc_gender_fill_keeps_existing_pronouns(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].pronouns = "она"
    merge(bundle, gender_pack(tmp_path, registry, pronouns="госпожа"))
    aldric = bundle.world.npcs["aldric"]
    assert aldric.gender == "female"
    assert aldric.pronouns == "она"


def test_pack_without_gender_changes_nothing(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, load(write_pack(tmp_path / "plain"), registry))
    assert report.added == []
    assert bundle.world.npcs["aldric"].gender is None


def test_npc_without_gender_in_pack_stays_unset(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.world.npcs["guard"].gender is None
    assert bundle.world.npcs["guard"].pronouns == ""


def test_ai_npc_with_pack_id_gets_no_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].origin = "ai"
    report = merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.world.npcs["aldric"].gender is None
    assert "gender:aldric" not in report.added


def test_dead_npc_still_gets_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].status = "dead"
    merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.world.npcs["aldric"].gender == "female"


def test_npc_missing_in_world_is_added_whole_with_pack_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    del bundle.world.npcs["aldric"]
    merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.world.npcs["aldric"].gender == "female"


def test_gender_fill_is_idempotent(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    pack = gender_pack(tmp_path, registry, hero_gender="male")
    bundle.heroes.append(world_hero(registry))
    merge(bundle, pack)
    after_first = bundle.model_dump()
    report = merge(bundle, pack)
    assert report.added == []
    assert bundle.model_dump() == after_first


def test_old_world_hero_gets_gender_from_preset_with_same_name_and_class(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.heroes.append(world_hero(registry))
    report = merge(bundle, gender_pack(tmp_path, registry, hero_gender="male"))
    hero = bundle.heroes[0]
    assert (hero.gender, hero.pronouns) == ("male", "он")
    assert f"gender:{hero.id}" in report.added


def test_hero_with_other_class_gets_no_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    hero = world_hero(registry)
    hero.sheet.primary.class_id = "rogue"
    bundle.heroes.append(hero)
    pack = gender_pack(tmp_path, registry, hero_gender="male")
    report = merge(bundle, pack)
    assert bundle.heroes[0].gender is None
    assert all(not item.startswith("gender:hero") for item in report.added)


def test_hero_with_other_name_gets_no_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.heroes.append(world_hero(registry))
    pack = gender_pack(tmp_path, registry, hero_gender="male", hero_name="Борин")
    merge(bundle, pack)
    assert bundle.heroes[0].gender is None


def test_hero_with_gender_is_not_touched(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    hero = world_hero(registry)
    hero.gender = "female"
    hero.pronouns = "она"
    bundle.heroes.append(hero)
    report = merge(bundle, gender_pack(tmp_path, registry, hero_gender="male"))
    assert (bundle.heroes[0].gender, bundle.heroes[0].pronouns) == ("female", "она")
    assert f"gender:{hero.id}" not in report.added


def test_hero_gender_fill_keeps_existing_pronouns(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    hero = world_hero(registry)
    hero.pronouns = "он сам"
    bundle.heroes.append(hero)
    merge(bundle, gender_pack(tmp_path, registry, hero_gender="male"))
    assert (bundle.heroes[0].gender, bundle.heroes[0].pronouns) == ("male", "он сам")


def test_hero_preset_without_gender_gives_nothing(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.heroes.append(world_hero(registry))
    merge(bundle, gender_pack(tmp_path, registry))
    assert bundle.heroes[0].gender is None


def test_gender_fill_goes_on_after_npc_with_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    bundle.world.npcs["aldric"].gender = "male"
    files = default_files()
    for npc in files["npcs.yaml"]:
        npc["gender"] = "female"
        npc["pronouns"] = "она"
    files["campaign.yaml"]["version"] = "2.0"
    merge(bundle, load(write_pack(tmp_path / "all", files), registry))
    assert bundle.world.npcs["aldric"].gender == "male"
    assert bundle.world.npcs["guard"].gender == "female"


def second_hero(registry):
    hero = world_hero(registry)
    hero.id = "hero2"
    return hero


def test_gender_fill_goes_on_after_hero_with_gender(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    first = world_hero(registry)
    first.gender = "female"
    bundle.heroes += [first, second_hero(registry)]
    merge(bundle, gender_pack(tmp_path, registry, hero_gender="male"))
    assert bundle.heroes[0].gender == "female"
    assert bundle.heroes[1].gender == "male"


def test_gender_fill_looks_past_preset_with_other_name(tmp_path, registry):
    files = default_files()
    other = {"id": "aaa", "choices": dict(arn_choices(), name="Борин", gender="female",
                                          pronouns="она"), "location_id": "tavern"}
    files["heroes/aaa.yaml"] = other
    files["heroes/arn.yaml"]["choices"]["gender"] = "male"
    files["heroes/arn.yaml"]["choices"]["pronouns"] = "он"
    pack = load(write_pack(tmp_path / "two", files), registry)
    assert [p.id for p in pack.heroes][0] == "aaa"
    bundle = v1_bundle(tmp_path, registry)
    bundle.heroes.append(world_hero(registry))
    merge(bundle, pack)
    assert bundle.heroes[0].gender == "male"


def test_new_event_is_reported_and_written_to_chronicle(tmp_path, registry):
    def edit(files):
        files["events.yaml"] = [{"id": "war", "type": "war", "regions": ["town"],
                                 "cause": "trigger:aldric:steal"}]

    bundle = v1_bundle(tmp_path, registry)
    report = merge(bundle, v2_pack(tmp_path, registry, edit))
    assert "event:war" in report.added
    assert [e.refs for e in bundle.chronicle.entries] == [["war"]]


def test_new_npc_chronicle_entry_refers_to_its_id(tmp_path, registry):
    bundle = v1_bundle(tmp_path, registry)
    merge(bundle, v2_pack(tmp_path, registry, lambda files: files["npcs.yaml"].append(NEW_NPC)))
    assert [e.refs for e in bundle.chronicle.entries] == [["brana"]]


def test_merged_entities_are_copies_of_pack_ones(tmp_path, registry):
    def edit(files):
        files["npcs.yaml"].append(NEW_NPC)
        files["events.yaml"] = [{"id": "war", "type": "war", "regions": ["town"],
                                 "cause": "trigger:aldric:steal"}]

    bundle = v1_bundle(tmp_path, registry)
    pack = v2_pack(tmp_path, registry, edit)
    merge(bundle, pack)
    bundle.world.npcs["brana"].means.append("лук")
    bundle.world.events[0].regions.append("port")
    assert next(n for n in pack.npcs if n.id == "brana").means == ["топор"]
    assert pack.events[0].regions == ["town"]
