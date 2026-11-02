# К3 П1: заклинания жреца и волшебника кругов 0–3 (SRD 5.2) — данные грузятся, счёт по кругам,
# ритуалы, строка эффекта у utility.
from collections import Counter

import pytest

RITUALS = {
    "alarm", "augury", "comprehend_languages", "detect_magic", "detect_poison_and_disease",
    "find_familiar", "floating_disk", "speak_with_animals", "gentle_repose", "identify",
    "illusory_script", "magic_mouth", "meld_into_stone", "phantom_steed", "purify_food_and_drink",
    "silence", "tiny_hut", "unseen_servant", "water_breathing", "water_walk",
}
SHARED = {
    "light", "mending", "detect_magic", "protection_from_evil_and_good", "augury",
    "blindness_deafness", "continual_flame", "enhance_ability", "gentle_repose", "hold_person",
    "locate_object", "animate_dead", "bestow_curse", "clairvoyance", "dispel_magic",
    "glyph_of_warding", "magic_circle", "protection_from_energy", "remove_curse", "sending",
    "speak_with_dead", "tongues",
}


def spells(registry):
    return list(registry.all("spell"))


def by_class(registry, class_id):
    return [s for s in spells(registry) if class_id in s.classes]


def test_there_are_154_spells(registry):
    assert len(spells(registry)) == 154


@pytest.mark.parametrize("class_id, expected", [
    ("cleric", {0: 7, 1: 15, 2: 17, 3: 19}),
    ("wizard", {0: 15, 1: 30, 2: 36, 3: 29}),
])
def test_spell_counts_by_circle(registry, class_id, expected):
    assert dict(Counter(s.level for s in by_class(registry, class_id))) == expected


def test_shared_spells_belong_to_both_classes(registry):
    shared = {s.id for s in spells(registry) if {"cleric", "wizard"} <= set(s.classes)}
    assert shared == SHARED


def test_every_spell_has_school_and_known_classes(registry):
    for spell in spells(registry):
        assert spell.school, spell.id
        assert set(spell.classes) <= {"cleric", "wizard", "ranger"}, spell.id
        assert 0 <= spell.level <= 3, spell.id


def test_rituals(registry):
    assert {s.id for s in spells(registry) if s.ritual} == RITUALS


def test_utility_spells_have_a_short_effect_text(registry):
    utility = [s for s in spells(registry) if any(e.type == "utility" for e in s.effects)]
    assert len(utility) == 49
    for spell in utility:
        assert 0 < len(spell.effect_text) <= 120, spell.id


def test_effect_text_only_where_utility(registry):
    for spell in spells(registry):
        if spell.effect_text:
            assert any(e.type == "utility" for e in spell.effects), spell.id


def test_ready_spells_keep_a_combat_kind(registry):
    from ai_dm.rules.spellcasting import spell_kind

    ready = {
        "guidance": "buff", "resistance": "buff", "prayer_of_healing": "heal",
        "chill_touch": "attack", "chromatic_orb": "attack", "shatter": "area",
        "fireball": "area", "lightning_bolt": "area",
    }
    assert {i: spell_kind(registry.get("spell", i)) for i in ready} == ready


# К3 П3а: вид заклинания по эффектам (spell_kind) -- что понимает бой
P3A_KINDS = {
    "sacred_flame": "save", "scorching_ray": "rays", "magic_missile": "darts",
    "hold_person": "condition", "sleep": "condition", "entangle": "condition",
    "grease": "condition", "fear": "condition", "color_spray": "condition",
    "ray_of_enfeeblement": "condition", "bestow_curse": "mark",
    "inflict_wounds": "save", "shocking_grasp": "attack", "vampiric_touch": "attack",
    "guiding_bolt": "attack", "ray_of_frost": "attack", "acid_arrow": "attack",
    "ray_of_sickness": "attack", "ice_knife": "attack", "fire_bolt": "attack",
    "thunderwave": "area", "gust_of_wind": "area", "acid_splash": "area",
    "burning_hands": "area", "fog_cloud": "fog", "spike_growth": "hazard",
    "goodberry": "create_item", "create_food_and_water": "create_item", "false_life": "temp_hp",
    "mage_armor": "defense", "shield_of_faith": "defense", "barkskin": "defense",
    "blur": "defense", "invisibility": "defense", "protection_from_energy": "defense",
    "protection_from_evil_and_good": "ward", "lesser_restoration": "cure",
    "remove_curse": "cure", "healing_word": "heal", "mass_healing_word": "heal",
    "cure_wounds": "heal", "misty_step": "teleport", "expeditious_retreat": "retreat",
    "prestidigitation": "utility", "longstrider": "utility", "magic_weapon": "buff",
    "enhance_ability": "buff", "beacon_of_hope": "buff", "bless": "buff",
    "pass_without_trace": "buff", "spare_the_dying": "stabilize",
}


@pytest.mark.parametrize("spell_id, kind", sorted(P3A_KINDS.items()))
def test_spell_kind_of_p3a_spells(registry, spell_id, kind):
    from ai_dm.rules.spellcasting import spell_kind

    assert spell_kind(registry.get("spell", spell_id)) == kind


def test_spell_without_effects_has_no_kind(registry):
    from ai_dm.rules.spellcasting import spell_kind

    assert spell_kind(registry.get("spell", "speak_with_animals")) is None


def test_has_effect_matches_any_of_the_given_types(registry):
    from ai_dm.rules.spellcasting import has_effect

    spell = registry.get("spell", "hold_person")
    assert has_effect(spell, "save_effect") is True
    assert has_effect(spell, "damage", "apply_condition") is True
    assert has_effect(spell, "damage", "heal") is False


@pytest.mark.parametrize("spell_id, feet", [
    ("sacred_flame", 60), ("fog_cloud", 120), ("vampiric_touch", 10), ("mage_armor", 10),
])
def test_reach_ft_uses_range_or_touch_default(registry, spell_id, feet):
    from ai_dm.rules.spellcasting import reach_ft

    assert reach_ft(registry.get("spell", spell_id)) == feet


def test_modifier_params_skip_empty_fields(registry):
    from ai_dm.rules.spellcasting import modifier_params

    trace = registry.get("spell", "pass_without_trace").effects[0]
    assert modifier_params(trace) == {"target": "skill", "skill": "stealth", "amount": 10}
    bless = registry.get("spell", "bless").effects[0]
    assert modifier_params(bless) == {"target": "attack_roll", "dice": "1d4"}


def test_modifier_params_carry_mode_and_ability(registry):
    from ai_dm.rules.spellcasting import modifier_params

    beacon = registry.get("spell", "beacon_of_hope").effects[0]
    assert modifier_params(beacon) == {
        "target": "saving_throw", "mode": "advantage", "ability": "wis",
    }


def test_modifier_params_never_hold_none(registry):
    from ai_dm.rules.spellcasting import modifier_params

    for spell in spells(registry):
        for effect in spell.effects:
            if effect.type == "modifier":
                assert None not in modifier_params(effect).values(), spell.id


def test_ray_of_enfeeblement_cuts_weapon_damage_and_gives_disadvantage(registry):
    effects = registry.get("spell", "ray_of_enfeeblement").effects
    assert not [e for e in effects if e.type == "damage"]
    save = [e for e in effects if e.type == "save_effect"]
    assert [(e.ability, e.repeat) for e in save] == [("con", True)]
    mods = {e.target: (e.dice, e.mode) for e in effects if e.type == "modifier"}
    assert mods == {"weapon_damage": ("1d8", "penalty"), "attack_roll": (None, "disadvantage")}


def test_chill_touch_is_a_melee_spell_attack(registry):
    spell = registry.get("spell", "chill_touch")
    assert (spell.range_kind, spell.range_ft) == ("touch", None)


def test_chill_touch_damage_and_scaling(registry):
    spell = registry.get("spell", "chill_touch")
    assert (spell.effects[0].dice, spell.effects[0].damage_type) == ("1d10", "necrotic")
    assert spell.cantrip_scaling == {5: "2d10", 11: "3d10", 17: "4d10"}


@pytest.mark.parametrize("spell_id, field, expected", [
    ("magic_weapon", "concentration", False),
    ("spiritual_weapon", "concentration", True),
    ("sleep", "range_ft", 60),
    ("magic_circle", "range_ft", 10),
    ("find_traps", "range_ft", 120),
    ("spare_the_dying", "range_ft", 15),
    ("jump", "casting_time", "bonus_action"),
    ("sanctuary", "casting_time", "bonus_action"),
    ("dragons_breath", "casting_time", "bonus_action"),
])
def test_fields_corrected_after_srd_check(registry, spell_id, field, expected):
    assert getattr(registry.get("spell", spell_id), field) == expected


def test_spiritual_weapon_gains_1d8_per_slot_level(registry):
    assert registry.get("spell", "spiritual_weapon").upcast.per_slot_level.dice == "1d8"


@pytest.mark.parametrize("spell_id", ["aid", "false_life"])
def test_max_hp_and_temp_hp_spells_gain_5_per_slot_level(registry, spell_id):
    assert registry.get("spell", spell_id).upcast.per_slot_level.value == 5


def test_aid_is_a_max_hp_spell_for_three_targets(registry):
    effect = registry.get("spell", "aid").effects[0]
    assert (effect.type, effect.value, effect.targets) == ("max_hp", 5, 3)


def test_color_spray_saves_with_constitution(registry):
    # SRD 5.2: Цветная пыль — Телосложение (в плане было Ловкость)
    effects = registry.get("spell", "color_spray").effects
    assert [e.ability for e in effects if e.type == "save_effect"] == ["con"]


def test_create_food_and_water_names_rations(registry):
    effects = registry.get("spell", "create_food_and_water").effects
    assert any(getattr(e, "item", None) == "rations" for e in effects)


def test_concentration_spells_have_a_duration(registry):
    for spell in spells(registry):
        if spell.concentration:
            assert spell.duration_s, spell.id


def test_cantrips_have_no_upcast(registry):
    for spell in spells(registry):
        if spell.level == 0:
            assert spell.upcast is None, spell.id


def test_variant_spells(registry):
    orb = registry.get("spell", "chromatic_orb").effects[0]
    energy = registry.get("spell", "protection_from_energy").effects[0]
    ability = registry.get("spell", "enhance_ability").effects[0]
    assert (orb.type, len(orb.variants)) == ("damage", 6)
    assert (energy.type, len(energy.variants)) == ("resist", 5)
    assert (ability.type, len(ability.variants)) == ("modifier", 6)
