# Пак campaigns/vale (этап 3, партия 1; STAGE3-PLAN A2 «Вейл -> пак», BACKLOG 7).
# Критерий партии: новый мир Вейла из пака равен миру этапа 2 по сущностям (кроме новых полей).
# Эталон мира этапа 2 -- tests/fixtures/packs/vale_stage2_world.json (снят с starter.new_world
# до переезда на пак: seed 1, world_id "w"; локации, NPC, герой, стартовая сцена, rng, часы).
# Сравнение «по подмножеству»: каждое поле эталона должно совпасть, новые поля v3 игнорируются.
import json

from campaign_kit import SAVED_AT, VALE_DIR, ids

from ai_dm.config.settings import load_rules_config
from ai_dm.core.rng import Rng

SNAPSHOT = json.loads(
    (VALE_DIR.parents[1] / "tests" / "fixtures" / "packs" / "vale_stage2_world.json")
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
    assert ids(pack.locations) == ["vale", "lame_goose", "cellar"]
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
    assert contains(expected["locations"], {k: v.model_dump(mode="json")
                                            for k, v in world.locations.items()}) == []
    assert contains(expected["npcs"], {k: v.model_dump(mode="json")
                                       for k, v in world.npcs.items()}) == []


def test_world_has_no_extra_entities_compared_to_stage2(registry):
    world = new_world(registry, "arn").world
    assert sorted(world.locations) == sorted(SNAPSHOT["arn"]["locations"])
    assert sorted(world.npcs) == sorted(SNAPSHOT["arn"]["npcs"])
    assert world.factions == {}
    assert world.pantheon == {}


def test_arn_hero_equals_stage2(registry):
    hero = new_world(registry, "arn").heroes[0]
    assert contains(SNAPSHOT["arn"]["hero"], hero.model_dump(mode="json")) == []


def test_liel_hero_equals_stage2(registry):
    hero = new_world(registry, "liel").heroes[0]
    assert contains(SNAPSHOT["liel"]["hero"], hero.model_dump(mode="json")) == []


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


def test_vale_tone_keeps_mood_and_has_typed_scales(registry):
    tone = new_world(registry, "arn").world.tone
    assert tone.mood == "приключенческое фэнтези"
    assert tone.language in ("", "сдержанно", "грубо")


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
