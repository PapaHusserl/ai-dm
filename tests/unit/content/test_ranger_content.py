# Контент следопыта 2-5 ур. (docs/plan-ranger-2-5.md, разд. 2-5).
# Ожидаемые данные:
#   class ranger: features -- favored_enemy (1), deft_explorer (2), fighting_style (2),
#       ability_score_improvement (4), extra_attack (5);
#       spellcasting.prepared_by_level == {1: 2 ... 5: 6}
#   subclass hunter (srd-5.2) и beast_master (custom), class_id == "ranger"
#   feat archery и ability_score_improvement; spells следопыта 1-2 круга, hunters_mark --
#   бонусное действие, концентрация, 90 фт, эффект extra_damage
import pytest

NEW_SPELLS = {
    "hunters_mark": 1, "ensnaring_strike": 1, "entangle": 1, "fog_cloud": 1, "goodberry": 1,
    "speak_with_animals": 1, "longstrider": 1, "alarm": 1, "pass_without_trace": 2,
    "spike_growth": 2, "lesser_restoration": 2, "barkskin": 2,
}
RANGER_FEATURES = [
    "favored_enemy", "deft_explorer", "extra_attack", "ability_score_improvement",
    "hunters_lore", "hunters_prey", "colossus_slayer", "horde_breaker",
    "beast_companion", "pack_sense",
]


@pytest.mark.parametrize("feature_id", RANGER_FEATURES)
def test_ranger_feature_is_loaded(registry, feature_id):
    assert registry.has("feature", feature_id)


@pytest.mark.parametrize("subclass_id", ["hunter", "beast_master"])
def test_subclass_belongs_to_ranger(registry, subclass_id):
    assert registry.get("subclass", subclass_id).class_id == "ranger"


def test_hunter_is_srd(registry):
    assert registry.get("subclass", "hunter").source == "srd-5.2"


def test_beast_master_is_custom(registry):
    assert registry.get("subclass", "beast_master").source == "custom"


def test_beast_master_has_companion_and_pack_sense_at_level_3(registry):
    rows = {(r.level, r.feature) for r in registry.get("subclass", "beast_master").features}
    assert (3, "beast_companion") in rows
    assert (3, "pack_sense") in rows


def test_hunter_has_lore_and_prey_at_level_3(registry):
    rows = {(r.level, r.feature) for r in registry.get("subclass", "hunter").features}
    assert (3, "hunters_lore") in rows
    assert (3, "hunters_prey") in rows


@pytest.mark.parametrize(
    "level, feature",
    [(1, "favored_enemy"), (2, "deft_explorer"), (2, "fighting_style"),
     (4, "ability_score_improvement"), (5, "extra_attack")],
)
def test_ranger_class_has_feature_at_level(registry, level, feature):
    rows = {(r.level, r.feature) for r in registry.get("class", "ranger").features}
    assert (level, feature) in rows


def test_ranger_prepared_by_level(registry):
    spellcasting = registry.get("class", "ranger").spellcasting
    levels_1_5 = {k: v for k, v in spellcasting.prepared_by_level.items() if k <= 5}
    assert levels_1_5 == {1: 2, 2: 3, 3: 4, 4: 5, 5: 6}


def test_favored_enemy_pool_by_level(registry):
    effects = registry.get("feature", "favored_enemy").effects
    pool = [e for e in effects if e.type == "resource" and e.pool == "favored_enemy"][0]
    assert pool.max_by_level == {1: 2, 2: 2, 3: 2, 4: 2, 5: 3}


def test_archery_is_a_fighting_style_with_ranged_attack_bonus(registry):
    feat = registry.get("feat", "archery")
    assert feat.category == "fighting_style"
    effect = feat.effects[0]
    assert (effect.type, effect.target, effect.value, effect.when) == (
        "modifier", "attack_roll", 2, "ranged_weapon"
    )


def test_ability_score_improvement_feat_is_loaded(registry):
    assert registry.has("feat", "ability_score_improvement")


@pytest.mark.parametrize("feat_id", ["great_weapon_fighting", "two_weapon_fighting"])
def test_other_fighting_styles_are_listed(registry, feat_id):
    assert registry.get("feat", feat_id).category == "fighting_style"


@pytest.mark.parametrize("spell_id, level", sorted(NEW_SPELLS.items()))
def test_spell_is_loaded_with_circle(registry, spell_id, level):
    assert registry.get("spell", spell_id).level == level


@pytest.mark.parametrize("spell_id", sorted(NEW_SPELLS))
def test_spell_is_in_ranger_list(registry, spell_id):
    assert "ranger" in registry.get("spell", spell_id).classes


def test_cure_wounds_is_still_in_ranger_list(registry):
    assert "ranger" in registry.get("spell", "cure_wounds").classes


def test_hunters_mark_data(registry):
    spell = registry.get("spell", "hunters_mark")
    assert spell.casting_time == "bonus_action"
    assert spell.concentration is True
    assert spell.range_ft == 90
    assert "extra_damage" in [e.type for e in spell.effects]


def test_barkskin_has_no_concentration(registry):
    # SRD 5.2.1: Дубовая кора -- без концентрации
    assert registry.get("spell", "barkskin").concentration is False
