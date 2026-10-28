# Пак campaigns/vale (этап 3, партия 1; STAGE3-PLAN A2 «Вейл -> пак», BACKLOG 7).
# Критерий партии: новый мир Вейла из пака равен миру этапа 2 по сущностям (кроме новых полей).
# Эталон мира этапа 2 -- tests/fixtures/packs/vale_stage2_world.json (снят с starter.new_world
# до переезда на пак: seed 1, world_id "w"; локации, NPC, герой, стартовая сцена, rng, часы).
# Сравнение «по подмножеству»: каждое поле эталона должно совпасть, новые поля v3 игнорируются.
import copy
import json

from campaign_kit import ROOT, SAVED_AT, VALE_DIR, ids

from ai_dm.config.settings import load_rules_config
from ai_dm.core.rng import Rng

SNAPSHOT = json.loads(
    (ROOT / "tests" / "fixtures" / "packs" / "vale_stage2_world.json")
    .read_text(encoding="utf-8")
)


def vale(registry):
    from ai_dm.campaign.loader import load_pack

    return load_pack(VALE_DIR, registry)


def new_world(registry, hero):
    from ai_dm.game.starter import new_world_from_pack

    return new_world_from_pack(
        registry, load_rules_config(), vale(registry), hero=hero, seed=1, world_id="w",
        saved_at=SAVED_AT,
    )


def contains(expected, actual, path="$"):
    # возвращает список расхождений: все ключи expected есть в actual и равны
    if isinstance(expected, dict):
        if not isinstance(actual, dict):
            return [f"{path}: ожидался dict"]
        diffs = []
        for key, value in expected.items():
            if key not in actual:
                diffs.append(f"{path}.{key}: нет поля")
            else:
                diffs += contains(value, actual[key], f"{path}.{key}")
        return diffs
    if isinstance(expected, list):
        if not isinstance(actual, list) or len(actual) != len(expected):
            return [f"{path}: списки разной длины или не список"]
        diffs = []
        for i, (e, a) in enumerate(zip(expected, actual, strict=True)):
            diffs += contains(e, a, f"{path}[{i}]")
        return diffs
    return [] if expected == actual else [f"{path}: {expected!r} != {actual!r}"]


def stage2_locations():
    # К7д: подвал получил описание про арку и выход в старую крипту (новая локация old_crypt)
    locations = copy.deepcopy(SNAPSHOT["arn"]["locations"])
    del locations["cellar"]["description"]
    locations["cellar"]["connections"].append({"distance_m": 15, "to": "old_crypt"})
    return locations


def stage2_hero(key):
    # шаг 34: пресеты Вейла получили motive/means/opportunity; эталон этапа 2 их держит пустыми
    hero = copy.deepcopy(SNAPSHOT[key]["hero"])
    for hook in ("motive", "means", "opportunity"):
        del hero[hook]
    return hero


# пак как данные

def test_vale_pack_loads(registry):
    pack = vale(registry)
    assert pack.manifest.id == "vale"
    assert pack.manifest.version


def test_vale_has_three_hero_presets(registry):
    assert sorted(ids(vale(registry).heroes)) == ["arn", "grey", "liel"]


def test_vale_world_text_is_in_pack(registry):
    assert "Вейл" in vale(registry).world_text


def test_vale_locations_and_npcs(registry):
    pack = vale(registry)
    assert ids(pack.locations) == ["vale", "lame_goose", "cellar", "old_crypt"]
    assert ids(pack.npcs) == ["innkeeper", "grakh"]


def test_vale_has_no_uniqueness_conflicts(registry, cfg):
    from ai_dm.game.starter import new_world_from_pack

    conflicts = []
    new_world_from_pack(
        registry, cfg, vale(registry), hero="arn", seed=1, world_id="w", saved_at=SAVED_AT,
        conflicts=conflicts,
    )
    assert conflicts == []


# мир Вейла = мир этапа 2

def test_arn_world_equals_stage2_locations_and_npcs(registry):
    world = new_world(registry, "arn").world
    expected = SNAPSHOT["arn"]
    assert contains(stage2_locations(), {k: v.model_dump(mode="json")
                                         for k, v in world.locations.items()}) == []
    assert contains(expected["npcs"], {k: v.model_dump(mode="json")
                                       for k, v in world.npcs.items()}) == []


def test_world_has_no_extra_entities_compared_to_stage2(registry):
    world = new_world(registry, "arn").world
    assert sorted(world.locations) == sorted([*SNAPSHOT["arn"]["locations"], "old_crypt"])
    assert sorted(world.npcs) == sorted(SNAPSHOT["arn"]["npcs"])
    assert world.factions == {}
    assert world.pantheon == {}


def test_arn_hero_equals_stage2(registry):
    hero = new_world(registry, "arn").heroes[0]
    assert contains(stage2_hero("arn"), hero.model_dump(mode="json")) == []


def test_liel_hero_equals_stage2(registry):
    hero = new_world(registry, "liel").heroes[0]
    assert contains(stage2_hero("liel"), hero.model_dump(mode="json")) == []


def test_vale_presets_have_motive_and_means(registry):
    for preset in vale(registry).heroes:
        assert preset.motive, preset.id
        assert 1 <= len(preset.means) <= 3, preset.id


def test_vale_world_heroes_get_preset_hooks(registry):
    presets = {p.id: p for p in vale(registry).heroes}
    for hero_id in ("arn", "grey", "liel"):
        hero = new_world(registry, hero_id).heroes[0]
        assert hero.motive == presets[hero_id].motive
        assert hero.means == presets[hero_id].means


def test_start_scene_rng_and_clock_equal_stage2(registry):
    bundle = new_world(registry, "arn")
    expected = SNAPSHOT["arn"]
    assert contains(expected["scene"], bundle.session.current_scene.model_dump(mode="json")) == []
    assert bundle.world.rng == Rng(1).state
    assert bundle.world.clock.now_s == expected["clock_now_s"]


def test_vale_world_has_chapter_one_and_campaign_id(registry):
    bundle = new_world(registry, "arn")
    assert bundle.world.campaign_id == "vale"
    assert bundle.manifest.campaign_id == "vale"
    assert bundle.session.current_chapter.number == 1
    assert "Вейл" in bundle.world.lore.world_text


def test_vale_pack_tone_keeps_mood_and_has_typed_scales(registry):
    tone = vale(registry).manifest.tone
    assert tone.mood == "приключенческое фэнтези"
    assert tone.language in ("", "сдержанно", "грубо")


def test_vale_world_tone_is_manifest_preset_heroic(registry):
    from ai_dm.campaign.presets import apply_preset, load_presets

    manifest = vale(registry).manifest
    assert manifest.preset == "heroic"
    world = new_world(registry, "arn").world
    assert world.tone == apply_preset(manifest.tone, load_presets()["heroic"])


def test_vale_world_writes_one_tone_chronicle_entry(registry):
    entries = new_world(registry, "arn").chronicle.entries
    assert [e.text for e in entries if e.kind == "tone"] == ["Пресет мира: Героическое приключение"]


# Грей: набор следопыта (BACKLOG 7)

def test_grey_has_standard_ranger_kit(registry):
    hero = new_world(registry, "grey").heroes[0]
    items = {e.item_id for e in hero.inventory}
    assert {"longbow", "studded_leather", "explorers_pack", "druidic_focus"} <= items


def test_grey_wears_studded_leather_and_holds_longbow(registry):
    hero = new_world(registry, "grey").heroes[0]
    assert hero.equipped.armor == "studded_leather"
    assert hero.equipped.main_hand == "longbow"


def test_grey_armor_class_is_12_plus_dex(registry):
    from ai_dm.rules.derived import ability_mod, armor_class

    hero = new_world(registry, "grey").heroes[0]
    assert armor_class(hero, registry) == 12 + ability_mod(hero, "dex")


def test_grey_has_seven_gold_of_standard_kit_money(registry):
    assert new_world(registry, "grey").heroes[0].money_cp == 700


def test_grey_masteries_are_longbow_and_scimitar(registry):
    hero = new_world(registry, "grey").heroes[0]
    assert sorted(hero.sheet.weapon_masteries) == ["longbow", "scimitar"]


# новые предметы SRD

def test_longbow_is_srd_martial_ranged_weapon(registry):
    weapon = registry.get("weapon", "longbow")
    assert weapon.source.startswith("srd")
    assert (weapon.category, weapon.kind) == ("martial", "ranged")
    assert weapon.damage_dice == "1d8"
    assert (weapon.range_normal_ft, weapon.range_long_ft) == (150, 600)
    assert "ammunition" in weapon.properties


def test_studded_leather_is_light_armor_ac_12(registry):
    armor = registry.get("armor", "studded_leather")
    assert armor.source.startswith("srd")
    assert (armor.category, armor.ac, armor.dex_cap) == ("light", 12, None)


def test_explorers_pack_and_druidic_focus_are_srd_items(registry):
    for item_id in ("explorers_pack", "druidic_focus"):
        assert registry.get("item", item_id).source.startswith("srd")


# К7д (Q7а): старая крипта под подвалом

def location(registry, location_id):
    return {loc.id: loc for loc in vale(registry).locations}[location_id]


def test_old_crypt_hangs_under_the_cellar(registry):
    crypt = location(registry, "old_crypt")
    assert (crypt.name, crypt.parent_id) == ("Старая крипта", "cellar")
    assert crypt.tags == ["гробница", "подвал"]


def test_cellar_and_crypt_are_connected_both_ways(registry):
    assert "old_crypt" in [c.to for c in location(registry, "cellar").connections]
    assert "cellar" in [c.to for c in location(registry, "old_crypt").connections]


def test_cellar_description_points_to_the_crypt(registry):
    assert "крипт" in location(registry, "cellar").description


def test_old_crypt_gets_the_tomb_picture(registry):
    from ai_dm.art.catalog import art_for_location, load_art

    assert art_for_location(location(registry, "old_crypt")) == load_art().pictures["tomb"]


def test_world_text_mentions_the_crypt():
    assert "крипт" in (VALE_DIR / "world.md").read_text(encoding="utf-8")


def test_grakh_is_still_a_goblin_boss_taking_the_prisoners(registry):
    grakh = {n.id: n for n in vale(registry).npcs}["grakh"]
    assert (grakh.combat["monster_id"], grakh.combat["intent"]) == ("goblin_boss", "capture")
    assert "disarmer" in registry.get("monster", "goblin_boss").tags


# ТБ #56 (docs/plan-tb.md Q1а): vale и test -- без списка monsters, рассказчик видит всех монстров

def test_vale_and_test_packs_have_no_monsters_list():
    from ai_dm.campaign.loader import pack_monster_scope

    assert pack_monster_scope(VALE_DIR) is None
    assert pack_monster_scope(ROOT / "campaigns" / "test") is None


def test_vale_narrator_sees_all_monsters():
    from ai_dm.ui.cli import campaign_registry

    _, reg = campaign_registry("vale", VALE_DIR.parent)
    assert reg.narrator_monster_ids() == reg.ids("monster")


def test_test_pack_narrator_sees_all_monsters():
    from ai_dm.ui.cli import campaign_registry

    _, reg = campaign_registry("test", ROOT / "campaigns")
    assert reg.narrator_monster_ids() == reg.ids("monster")
