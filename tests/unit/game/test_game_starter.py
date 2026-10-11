# Ожидаемый API: ai_dm.game.starter -- контракт в game_kit.py.
# Стартовый мир «Вейл»: выбор героя Арн / Лиэль, локации, трактирщик, Гракх, world_text, сид.
import pytest
from game_kit import SAVED_AT

from ai_dm.persistence.layout import check_world_id
from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION


def make(registry, cfg, hero="arn", seed=11, **kw):
    from ai_dm.game.starter import new_world

    return new_world(registry, cfg, hero=hero, seed=seed, saved_at=SAVED_AT, **kw)


# выбор героя

def test_heroes_are_arn_liel_and_grey():
    from ai_dm.game.starter import HEROES

    assert tuple(HEROES) == ("arn", "liel", "grey")


def test_arn_is_human_fighter_soldier(registry, cfg):
    hero = make(registry, cfg, hero="arn").heroes[0]
    assert hero.id == "hero"
    assert hero.name == "Арн"
    assert hero.sheet.species_id == "human"
    assert hero.sheet.class_id == "fighter"
    assert hero.sheet.background.name == registry.get("background", "soldier").name


def test_liel_is_wizard(registry, cfg):
    hero = make(registry, cfg, hero="liel").heroes[0]
    assert hero.id == "hero"
    assert hero.name == "Лиэль"
    assert hero.sheet.class_id == "wizard"
    assert hero.sheet.species_id == "elf"


# Грей (G1): следопыт 1 ур., снаряжение -- SRD-набор класса, предметов кампании нет

CAMPAIGN_ITEMS = {
    "north_wind_blade", "composite_longbow", "hunting_dirk", "harpoon_dart", "mithral_shirt",
    "hunter_jacket", "snow_ghost_cloak", "spiked_bogshoes", "gnome_climbing_kit",
    "stoneskin_elixir", "breath_cleansing_potion", "mor_antidote", "bran_mountain_salve",
    "spare_bowstring", "arrow_armor_piercing", "arrow_frost", "arrow_fire", "arrow_silver",
}


def grey(registry, cfg):
    return make(registry, cfg, hero="grey").heroes[0]


def test_grey_is_human_ranger_level_1(registry, cfg):
    hero = grey(registry, cfg)
    assert hero.id == "hero"
    assert hero.name == "Грей"
    assert hero.sheet.species_id == "human"
    assert hero.sheet.class_id == "ranger"
    assert hero.sheet.level == 1
    assert hero.sheet.xp == 0


def test_grey_abilities(registry, cfg):
    abilities = grey(registry, cfg).sheet.abilities
    assert abilities == {"str": 12, "dex": 17, "con": 13, "int": 10, "wis": 15, "cha": 8}


def test_grey_hp_is_11(registry, cfg):
    hero = grey(registry, cfg)
    assert hero.creature.hp_max == 11
    assert hero.creature.hp_current == 11


def test_grey_skills(registry, cfg):
    skills = grey(registry, cfg).sheet.skill_proficiencies
    assert sorted(skills) == sorted(
        ["stealth", "survival", "perception", "insight", "nature", "intimidation"]
    )


def test_grey_feats(registry, cfg):
    assert sorted(grey(registry, cfg).sheet.feats) == ["alert", "savage_attacker"]


def test_grey_background_is_lone_woodsman(registry, cfg):
    background = grey(registry, cfg).sheet.background
    assert background.name == "Егерь-одиночка"
    assert background.feat == "alert"
    assert background.tool == "herbalism_kit"


def test_grey_has_no_prepared_spells(registry, cfg):
    sheet = grey(registry, cfg).sheet
    assert sheet.known_of() == []
    assert sheet.prepared_of() == []


def test_grey_inventory_is_srd_items_only(registry, cfg):
    ids = [e.item_id for e in grey(registry, cfg).inventory]
    assert ids != []
    for item_id in ids:
        assert any(registry.has(kind, item_id) for kind in ("item", "weapon", "armor")), item_id


def test_grey_has_no_campaign_items(registry, cfg):
    ids = {e.item_id for e in grey(registry, cfg).inventory}
    assert ids & CAMPAIGN_ITEMS == set()


def test_grey_has_armor_bow_arrows_and_melee_weapon(registry, cfg):
    ids = {e.item_id for e in grey(registry, cfg).inventory}
    assert ids & {"studded_leather"}
    assert any(item_id.endswith("bow") for item_id in ids)
    assert "arrows" in ids
    assert ids & {"scimitar", "shortsword"}


def test_grey_masteries_are_for_his_own_weapons(registry, cfg):
    hero = grey(registry, cfg)
    ids = {e.item_id for e in hero.inventory}
    masteries = hero.sheet.weapon_masteries
    assert len(masteries) == 2
    assert set(masteries) <= ids
    assert any(item_id.endswith("bow") for item_id in masteries)


def test_grey_choices_function_takes_hero_id():
    from ai_dm.game.starter import ranger_choices

    assert ranger_choices("h2").hero_id == "h2"
    assert ranger_choices().hero_id == "hero"


def test_unknown_hero_is_value_error(registry, cfg):
    with pytest.raises(ValueError):
        make(registry, cfg, hero="bob")


def test_choices_functions_take_hero_id():
    from ai_dm.game.starter import fighter_choices, wizard_choices

    assert fighter_choices("h2").hero_id == "h2"
    assert wizard_choices("h2").hero_id == "h2"
    assert fighter_choices().hero_id == "hero"
    assert wizard_choices().hero_id == "hero"


def test_devtools_imports_choices_from_starter():
    from ai_dm.devtools import sim_combat
    from ai_dm.game import starter

    assert sim_combat.fighter_choices is starter.fighter_choices
    assert sim_combat.wizard_choices is starter.wizard_choices


def test_starting_hero_is_fresh(registry, cfg):
    hero = make(registry, cfg).heroes[0]
    assert hero.sheet.level == 1
    assert hero.sheet.xp == 0
    assert hero.status == "active"
    assert hero.creature.hp_current == hero.creature.hp_max


def test_hero_starts_in_tavern(registry, cfg):
    assert make(registry, cfg).heroes[0].location_id == "lame_goose"


# мир

def test_manifest_matches_world_and_hero(registry, cfg):
    bundle = make(registry, cfg)
    assert bundle.manifest.world_id == bundle.world.world_id
    assert bundle.manifest.current_hero_id == "hero"
    assert bundle.manifest.heroes == ["hero"]
    assert bundle.manifest.schema_version == CURRENT_SCHEMA_VERSION
    assert bundle.manifest.saved_at == SAVED_AT


def test_locations_vale_tavern_cellar(registry, cfg):
    world = make(registry, cfg).world
    assert world.locations["vale"].name == "Вейл"
    assert "Хромой гусь" in world.locations["lame_goose"].name
    assert world.locations["lame_goose"].parent_id == "vale"
    assert world.locations["cellar"].parent_id == "lame_goose"


def test_locations_are_connected_in_a_chain(registry, cfg):
    world = make(registry, cfg).world

    def linked(a, b):
        ab = [c for c in world.locations[a].connections if c.to == b]
        ba = [c for c in world.locations[b].connections if c.to == a]
        return any(c.distance_m > 0 for c in ab + ba)

    assert linked("vale", "lame_goose")
    assert linked("lame_goose", "cellar")


def test_cellar_is_where_goblins_live(registry, cfg):
    assert "гоблин" in make(registry, cfg).world.locations["cellar"].description


def test_innkeeper_is_named_non_key_npc_in_tavern(registry, cfg):
    npc = make(registry, cfg).world.npcs["innkeeper"]
    assert npc.named is True
    assert npc.key is False
    assert npc.location_id == "lame_goose"
    assert 1 <= len(npc.means) <= 3


def test_grakh_is_key_goblin_boss_with_capture_intent_in_data(registry, cfg):
    npc = make(registry, cfg).world.npcs["grakh"]
    assert npc.named is True
    assert npc.key is True
    assert npc.location_id == "cellar"
    assert npc.combat == {"monster_id": "goblin_boss", "intent": "capture"}
    assert registry.has("monster", "goblin_boss")


def test_grakh_name_differs_from_hero_names(registry, cfg):
    bundle = make(registry, cfg)
    names = {h.name for h in bundle.heroes}
    assert bundle.world.npcs["grakh"].name not in names
    assert bundle.world.npcs["innkeeper"].name not in names


def test_start_scene_is_open_in_tavern(registry, cfg):
    bundle = make(registry, cfg)
    scene = bundle.session.current_scene
    assert scene.id == "scene_1"
    assert scene.started_at_s == bundle.world.clock.now_s == 0
    assert scene.location_id == "lame_goose"
    assert scene.closed_reason is None
    assert bundle.session.active_combat is None
    assert bundle.session.turn_seq == 0


# сид и id мира

def test_seed_goes_to_rng(registry, cfg):
    from ai_dm.core.rng import Rng

    assert make(registry, cfg, seed=42).world.rng == Rng(42).state
    assert make(registry, cfg, seed=43).world.rng == Rng(43).state


def test_same_arguments_give_equal_bundles(registry, cfg):
    a = make(registry, cfg, world_id="vale-1")
    b = make(registry, cfg, world_id="vale-1")
    assert a.model_dump_json() == b.model_dump_json()


def test_world_ids_are_unique_and_valid(registry, cfg):
    first = make(registry, cfg).world.world_id
    second = make(registry, cfg).world.world_id
    assert first != second
    check_world_id(first)
    check_world_id(second)


def test_explicit_world_id_is_used(registry, cfg):
    bundle = make(registry, cfg, world_id="my-world")
    assert bundle.world.world_id == "my-world"
    assert bundle.manifest.world_id == "my-world"


def test_new_world_roundtrips_through_save_slot(registry, cfg, tmp_path):
    from ai_dm.persistence.store import load_slot, save_slot

    bundle = make(registry, cfg, world_id="w-rt")
    save_slot(tmp_path, bundle, "manual-start", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "w-rt", "manual-start")
    assert loaded.world.model_dump_json() == bundle.world.model_dump_json()
    assert loaded.heroes[0].model_dump_json() == bundle.heroes[0].model_dump_json()


def test_travel_chain_works_with_protocol(registry, cfg):
    # путь таверна -> подвал и обратно -> деревня разрешён протоколом (связи с расстоянием)
    from protocol_kit import make_ctx, req

    from ai_dm.protocol.apply import apply

    bundle = make(registry, cfg)
    ctx = make_ctx(registry, cfg, bundle=bundle)
    done = apply(ctx, req("advance_time", category="none", travel_to="cellar", pace="normal"))
    assert done.status == "accepted"
    assert bundle.heroes[0].location_id == "cellar"
    back = apply(ctx, req("advance_time", category="none", travel_to="lame_goose"))
    assert back.status == "accepted"
    village = apply(ctx, req("advance_time", category="none", travel_to="vale"))
    assert village.status == "accepted"


def test_new_world_starts_the_scene_through_start_scene(registry, cfg, monkeypatch):
    from ai_dm.game import starter
    from ai_dm.game.scene import start_scene

    calls = []

    def spy(bundle):
        calls.append(bundle)
        return start_scene(bundle)

    monkeypatch.setattr(starter, "start_scene", spy)
    bundle = make(registry, cfg)
    assert len(calls) == 1
    assert calls[0] is bundle
    assert bundle.session.current_scene.id == "scene_1"
    assert bundle.session.current_scene.location_id == "lame_goose"
