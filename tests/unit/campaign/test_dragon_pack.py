# Пак campaigns/drunk_dragon (этап 3, П7; STAGE3-PLAN B/П7, решения 1в 2б 3а 4а 7, G5а, G6).
# Тесты на реальный пак из репо (saves/ в git нет). Старт с главы II, 23:50 дня 5 Листопада.
from campaign_kit import ROOT, SAVED_AT

DRAGON_DIR = ROOT / "campaigns" / "drunk_dragon"
EVENT_KINDS = ("natural", "caused")


def dragon_registry():
    from ai_dm.campaign.loader import pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DRAGON_DIR)
    return load_registry([content] if content is not None else [])


def dragon_pack():
    from ai_dm.campaign.loader import load_pack

    return load_pack(DRAGON_DIR, dragon_registry())


def dragon_world(cfg, conflicts=None, seed=1):
    from ai_dm.game.starter import new_world_from_pack

    return new_world_from_pack(
        dragon_registry(), cfg, dragon_pack(), hero="grey", seed=seed, world_id="dd",
        saved_at=SAVED_AT, conflicts=conflicts,
    )


def test_dragon_pack_loads():
    pack = dragon_pack()
    assert pack.manifest.id == "drunk_dragon"
    assert pack.manifest.version


def test_dragon_pack_has_grey_preset():
    assert "grey" in [p.id for p in dragon_pack().heroes]


def test_dragon_world_builds_without_conflicts(cfg):
    conflicts = []
    dragon_world(cfg, conflicts)
    assert conflicts == []


def test_dragon_world_has_campaign_id(cfg):
    bundle = dragon_world(cfg)
    assert bundle.world.campaign_id == "drunk_dragon"
    assert bundle.manifest.campaign_id == "drunk_dragon"


def test_dragon_starts_in_chapter_two_with_title(cfg):
    chapter = dragon_world(cfg).session.current_chapter
    assert chapter.number == 2
    assert chapter.title


def test_dragon_start_date_is_oct_5_2350(cfg):
    clock = dragon_world(cfg).world.clock
    # 0001-10-05 23:50: 9 месяцев по 30 дней + 4 дня + 23:50
    assert clock.now_s == (9 * 30 + 4) * 86400 + 23 * 3600 + 50 * 60


def test_dragon_calendar_is_standard_month_ten_is_listopad(cfg):
    calendar = dragon_world(cfg).world.clock.calendar
    assert calendar.months[9].name == "Листопад"


def test_dragon_start_scene_has_summary(cfg):
    scene = dragon_world(cfg).session.current_scene
    assert scene.summary


def test_dragon_scene_summary_has_all_four_options(cfg):
    summary = dragon_world(cfg).session.current_scene.summary
    for n in ("[1]", "[2]", "[3]", "[4]"):
        assert n in summary


def test_dragon_scene_summary_has_player_choice_and_unanswered_status(cfg):
    summary = dragon_world(cfg).session.current_scene.summary
    assert "2 и 3" in summary
    assert "статус?" in summary


def test_dragon_scene_summary_has_eight_recent_turns(cfg):
    summary = dragon_world(cfg).session.current_scene.summary
    assert summary.count("→") >= 8


def test_dragon_scene_is_in_iron_ridge_foothills(cfg):
    bundle = dragon_world(cfg)
    assert bundle.session.current_scene.location_id == "iron_ridge_foothills"


def test_dragon_recent_turns_and_offered_choices_are_empty(cfg):
    bundle = dragon_world(cfg)
    assert bundle.memory.recent_turns == []
    assert bundle.session.offered_choices == []


def test_dragon_combat_is_empty(cfg):
    assert dragon_world(cfg).session.active_combat is None


def test_dragon_memory_has_two_chapters_and_game_summary(cfg):
    memory = dragon_world(cfg).memory
    assert len(memory.chapters) == 2
    assert memory.game_summary
    assert memory.scenes


def test_dragon_chronicle_has_days_one_to_five(cfg):
    assert len(dragon_world(cfg).chronicle.entries) >= 5


def test_dragon_chronicle_times_are_before_start(cfg):
    bundle = dragon_world(cfg)
    assert all(e.at_s <= bundle.world.clock.now_s for e in bundle.chronicle.entries)


def test_dragon_olbrecht_is_dead_and_varen_alive(cfg):
    npcs = dragon_world(cfg).world.npcs
    assert npcs["olbrecht"].status == "dead"
    assert npcs["varen"].status == "alive"


def test_dragon_nazir_ritual_is_active(cfg):
    events = {e.id: e for e in dragon_world(cfg).world.events}
    assert "nazir_ritual" in events
    assert events["nazir_ritual"].ends_at_s is None or events["nazir_ritual"].ends_at_s > (
        dragon_world(cfg).world.clock.now_s
    )


def test_dragon_events_have_kind_from_list(cfg):
    assert all(e.kind in EVENT_KINDS for e in dragon_world(cfg).world.events)


def test_dragon_event_regions_are_location_ids(cfg):
    world = dragon_world(cfg).world
    for event in world.events:
        assert set(event.regions) <= set(world.locations), event.id


def test_dragon_entities_have_origin_pack(cfg):
    world = dragon_world(cfg).world
    for group in (world.npcs, world.pantheon, world.locations):
        assert all(e.origin == "pack" for e in group.values())


def test_dragon_pack_tone_is_approved():
    tone = dragon_pack().manifest.tone
    assert tone.violence == "жестоко"
    assert tone.horror == "умеренно"
    assert tone.romance == "откровенно"
    assert tone.language == "сдержанно"
    assert tone.mood
    assert tone.hard_limits == []


def test_dragon_world_tone_is_manifest_preset_grim(cfg):
    from ai_dm.campaign.presets import apply_preset, load_presets

    manifest = dragon_pack().manifest
    assert manifest.preset == "grim"
    assert dragon_world(cfg).world.tone == apply_preset(manifest.tone, load_presets()["grim"])


def test_dragon_world_tone_is_grimmer_than_pack(cfg):
    tone = dragon_world(cfg).world.tone
    assert tone.horror == "сильно"
    assert tone.language == "грубо"
    assert tone.romance == "откровенно"


def test_dragon_pack_style_lines_survive_in_world_soft_limits(cfg):
    manifest = dragon_pack().manifest
    assert manifest.tone.soft_limits
    assert set(manifest.tone.soft_limits) <= set(dragon_world(cfg).world.tone.soft_limits)


def test_dragon_narration_style_is_in_tone_notes():
    assert dragon_pack().manifest.tone.notes


def test_dragon_grey_has_54_crowns(cfg):
    assert dragon_world(cfg).heroes[0].money_cp == 5400


def test_dragon_grey_has_campaign_inventory(cfg):
    hero = dragon_world(cfg).heroes[0]
    items = {e.item_id for e in hero.inventory}
    assert {"north_wind_blade", "composite_longbow", "mithral_shirt"} <= items
    assert hero.equipped.armor == "mithral_shirt"
    assert hero.equipped.main_hand == "north_wind_blade"


def test_dragon_grey_is_in_foothills_and_not_priest(cfg):
    hero = dragon_world(cfg).heroes[0]
    assert hero.location_id == "iron_ridge_foothills"
    assert hero.deity_id is None


def test_dragon_chapter_one_lost_items_are_not_carried(cfg):
    items = {e.item_id for e in dragon_world(cfg).heroes[0].inventory}
    assert not any("unaccounted" in i for i in items)


def test_dragon_campaign_items_are_in_registry():
    registry = dragon_registry()
    assert registry.has("weapon", "north_wind_blade")


def test_dragon_birth_s_is_empty_for_all_npcs(cfg):
    assert all(n.birth_s is None for n in dragon_world(cfg).world.npcs.values())


def test_dragon_key_npcs_and_factions_have_opportunity(cfg):
    world = dragon_world(cfg).world
    keys = [n for n in world.npcs.values() if n.key and n.status == "alive"]
    assert keys
    assert all(n.opportunity for n in keys)
    assert all(f.opportunity for f in world.factions.values())


def test_dragon_every_npc_has_motive(cfg):
    npcs = dragon_world(cfg).world.npcs.values()
    assert all(n.motive for n in npcs if n.status == "alive")


def test_dragon_gods_have_opportunity_and_relations(cfg):
    gods = dragon_world(cfg).world.pantheon
    assert len(gods) == 6
    assert all(g.opportunity and g.pleased_by and g.angered_by for g in gods.values())


def test_dragon_and_vale_coexist_with_different_campaign_ids(registry, cfg):
    from campaign_kit import VALE_DIR

    from ai_dm.campaign.loader import load_pack
    from ai_dm.game.starter import new_world_from_pack

    vale = new_world_from_pack(
        registry, cfg, load_pack(VALE_DIR, registry), hero="arn", seed=1, world_id="v",
        saved_at=SAVED_AT,
    )
    assert vale.world.campaign_id != dragon_world(cfg).world.campaign_id


def test_dragon_world_is_deterministic_by_seed(cfg):
    first = dragon_world(cfg, seed=3).model_dump_json()
    assert first == dragon_world(cfg, seed=3).model_dump_json()


def test_dragon_selune_has_season_power_profile(cfg):
    power = dragon_world(cfg).world.pantheon["selune"].season_power
    assert power
    assert power["весна"] > 0
    assert power["осень"] < 0
    assert power["весна"] > power["осень"]


# решения проектировщика (stage3-p7-review, Q1-Q3, Селунэ)
def test_dragon_olbrecht_and_supreme_hierarch_stay_key_though_dead(cfg):
    npcs = dragon_world(cfg).world.npcs
    for npc_id in ("olbrecht", "supreme_hierarch"):
        assert npcs[npc_id].status == "dead"
        assert npcs[npc_id].key is True


def test_dragon_grey_has_motive_in_pack_and_in_hero_state(cfg):
    preset = next(p for p in dragon_pack().heroes if p.id == "grey")
    assert preset.motive
    assert dragon_world(cfg).heroes[0].motive == preset.motive


def test_dragon_has_foothills_villages_and_grey_quarter(cfg):
    names = [loc.name for loc in dragon_world(cfg).world.locations.values()]
    assert any("Предгорья Кряжа" in n for n in names)
    assert any("Серый Квартал" in n for n in names)


def test_dragon_grey_quarter_is_inside_the_city(cfg):
    locations = dragon_world(cfg).world.locations
    quarter = next(loc for loc in locations.values() if "Серый Квартал" in loc.name)
    assert quarter.parent_id == "city"


def test_dragon_raids_event_and_conspiracy_faction_have_existing_regions(cfg):
    world = dragon_world(cfg).world
    events = {e.id: e for e in world.events}
    groups = {"harvest_raids": events["harvest_raids"],
              "city_council_conspiracy": world.factions["city_council_conspiracy"]}
    for owner_id, owner in groups.items():
        assert owner.regions, owner_id
        assert set(owner.regions) <= set(world.locations), owner_id


def test_dragon_selune_is_stronger_in_summer_than_usual(cfg):
    assert dragon_world(cfg).world.pantheon["selune"].season_power["лето"] > 0


def omen_ready_bundle(cfg, flag_seen):
    bundle = dragon_world(cfg)
    bundle.world.flags["selune_owl_omen_seen"] = flag_seen
    bundle.world.npcs["edrin"].status = "alive"
    bundle.heroes[0].location_id = "east_shaft"
    return bundle


def omen_fired(bundle):
    from ai_dm.world_sim.triggers import check

    return any("omen_for_the_living" in ref for ref in check(bundle).fired)


def test_dragon_selune_omen_does_not_fire_after_flag(cfg):
    assert not omen_fired(omen_ready_bundle(cfg, True))


def test_dragon_selune_omen_fires_before_flag(cfg):
    assert omen_fired(omen_ready_bundle(cfg, False))


def test_dragon_captain_guards_the_villages_not_the_party():
    # решение проектировщика: Капитан с заслоном у предгорных деревень, в сцене отряда его нет
    from pathlib import Path

    import yaml
    npcs = yaml.safe_load((Path("campaigns/drunk_dragon/npcs.yaml")).read_text(encoding="utf-8"))
    npcs = npcs if isinstance(npcs, list) else next(iter(npcs.values()))
    captain = next(n for n in npcs if n["id"] == "captain_of_guard")
    assert captain["location_id"] == "iron_ridge_foothills_villages"


# спутники героя (stage3-live-followers, F4): отряд у подъёма к шахте идёт за Греем

def test_dragon_squad_follows_the_hero(cfg):
    bundle = dragon_world(cfg)
    hero_ids = (bundle.heroes[0].id, "grey")
    for npc_id in ("bran_sedogriv", "jorgen", "lira", "edrin"):
        assert bundle.world.npcs[npc_id].follows in hero_ids


def test_dragon_other_npcs_do_not_follow(cfg):
    bundle = dragon_world(cfg)
    squad = {"bran_sedogriv", "jorgen", "lira", "edrin"}
    for npc in bundle.world.npcs.values():
        if npc.id not in squad:
            assert npc.follows is None


def test_dragon_squad_starts_in_the_heros_place(cfg):
    bundle = dragon_world(cfg)
    here = bundle.heroes[0].location_id
    for npc_id in ("bran_sedogriv", "jorgen", "lira", "edrin"):
        assert bundle.world.npcs[npc_id].location_id == here


# ТБ #56 (docs/plan-tb.md Q1а): список monsters в campaign.yaml пака

DRAGON_MONSTERS = [
    "guard", "goblin_warrior", "goblin_boss", "wolf", "dire_wolf", "giant_rat", "swarm_of_rats",
    "giant_spider", "black_bear", "boar", "ghoul", "ghast", "zombie", "ogre_zombie", "skeleton",
    "wight", "shadow", "specter", "gargoyle", "magmin", "fire_elemental", "earth_elemental",
    "dust_mephit", "steam_mephit", "homunculus",
]


def test_dragon_monsters_list_is_as_agreed():
    from ai_dm.campaign.loader import pack_monster_scope

    assert sorted(pack_monster_scope(DRAGON_DIR)) == sorted(DRAGON_MONSTERS)


def test_dragon_monsters_are_known_to_registry():
    registry = dragon_registry()
    assert [m for m in DRAGON_MONSTERS if not registry.has("monster", m)] == []


def test_dragon_narrator_sees_only_the_list():
    from ai_dm.ui.cli import campaign_registry

    _, registry = campaign_registry("drunk_dragon", ROOT / "campaigns")
    assert registry.narrator_monster_ids() == sorted(DRAGON_MONSTERS)
    assert len(registry.ids("monster")) > len(DRAGON_MONSTERS)
