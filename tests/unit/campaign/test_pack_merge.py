# Догрузка новых сущностей пака в идущий мир (этап 3, партия 1; STAGE3-PLAN A2, Т-6).
# merge_new(bundle, pack) -> report (.added, .conflicts): новые = id нет в world.npcs / factions /
# pantheon / locations / events; существующие не меняются; новые проходят уникальность против
# текущего мира (включая origin: ai); добавленные -- запись хроники kind "pack_update",
# world.campaign_version = версия пака; идемпотентно; world.md / truths.md не обновляются.
from campaign_kit import bundle_from_world, default_files, ids, load, world_from_pack, write_pack

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
