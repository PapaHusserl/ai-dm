# Ожидаемый API: ai_dm.rules.derived (hero: HeroState; registry: ContentRegistry)
#   ability_modifier(score: int) -> int                  -- (score - 10) // 2  (8 -> -1, 15 -> +2)
#   ability_mod(hero, ability: str) -> int               -- по sheet.abilities (итоговые значения)
#   proficiency(hero, registry) -> int                   -- бонус мастерства по sheet.level
#                                                           (таблица proficiency из реестра)
#   saving_throw_bonus(hero, registry, ability) -> int
#       мод. + бонус мастерства, если ability в class.saving_throws
#   skill_bonus(hero, registry, skill: str) -> int
#       мод. характеристики навыка + мастерство, если навык в sheet.skill_proficiencies
#   passive_perception(hero, registry) -> int   -- 10 + skill_bonus(hero, registry, "perception")
#   initiative_bonus(hero, registry) -> int
#       мод. ЛОВ; черта "alert" в sheet.feats добавляет бонус мастерства
#   armor_class(hero, registry) -> int
#       без доспеха 10 + мод. ЛОВ; доспех из hero.equipped.armor: ac + мод. ЛОВ, ограниченный
#       dex_cap (None -- без предела, 0 -- ЛОВ не прибавляется); щит hero.equipped.shield +ac;
#       черта "defense" в sheet.feats: +1, только если надет доспех
#   armor_dex(armor, dex) -> int                        (К7х) Лов в КД с учётом dex_cap: 0 -- Лов не
#       прибавляется (даже отрицательный), None -- без предела, число -- не больше предела
#   gear_ac(registry, armor_id, shield_id, dex) -> int  (К7х) без доспеха 10 + Лов, иначе ac +
#     armor_dex;
#       плюс ac щита; armor_class_parts героя считает Лов тем же armor_dex (сумма КД не изменилась)
#   effect_amount(effect, hero, registry) -> int
#       единая функция числа эффекта (КД, инициатива, лечение): effect.value (или 0) + добавка
#       effect.add: proficiency_bonus -> бонус мастерства; spellcasting_modifier -> мод.
#       заклинательной характеристики; class_level -> уровень героя, если его класс ==
#       effect.class_id, иначе 0
#   attack_bonus(hero, registry, weapon_id) -> int
#       характеристика: СИЛ для ближнего, ЛОВ для дальнего, для finesse -- большая из двух;
#       + бонус мастерства, если категория оружия (simple|martial) в class.weapon_training
#       или оружие воинское и имеет любое свойство из class.weapon_training_properties (плут)
#   damage_bonus(hero, registry, weapon_id) -> int       -- та же характеристика, что и в атаке
#   spell_save_dc(hero, registry) -> int
#       8 + мастерство + мод. заклинательной характеристики; не заклинатель -> ValueError
#   spell_attack_bonus(hero, registry) -> int
#       мастерство + мод. заклинательной характеристики; не заклинатель -> ValueError
#   spell_slots_for(registry, progression, level) -> dict[int, int]
#       ячейки из таблиц реестра spell_slots_full / spell_slots_half (ключ "уровень:круг", п. 2.10)
#   spell_slots(hero, registry) -> dict[int, int]   -- {круг: ячейки} по class.spellcasting.
#       progression (full | half), без списка классов в коде; не заклинатель -> {}
# Данные героев собираются прямо в тесте (без build_character).
import pytest

from ai_dm.rules.derived import (
    ability_mod,
    ability_modifier,
    armor_class,
    armor_class_parts,
    armor_dex,
    attack_bonus,
    damage_bonus,
    effect_amount,
    gear_ac,
    initiative_bonus,
    passive_perception,
    proficiency,
    saving_throw_bonus,
    skill_bonus,
    spell_attack_bonus,
    spell_save_dc,
    spell_slots,
    spell_slots_for,
)
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, Equipped, HeroState


def make_fighter(**equipped):
    # человек-воин-солдат: СИЛ 17, ЛОВ 13, ТЕЛ 15, ИНТ 8, МУД 10, ХАР 12
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
        skill_proficiencies=["athletics", "intimidation", "perception", "survival"],
        feats=["savage_attacker"],
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
        equipped=Equipped(**equipped),
    )


def make_wizard():
    # эльф-волшебник-мудрец: СИЛ 8, ЛОВ 13, ТЕЛ 15, ИНТ 17, МУД 12, ХАР 10
    sheet = CharacterSheet(
        species_id="elf",
        classes=[ClassLevel(class_id="wizard")], level_history=["wizard"] * 1,
        background=BackgroundSpec(
            name="Мудрец",
            abilities=["con", "int", "wis"],
            skills=["arcana", "history"],
            tool="calligraphers_supplies",
            feat="magic_initiate",
        ),
        abilities={"str": 8, "dex": 13, "con": 15, "int": 17, "wis": 12, "cha": 10},
        skill_proficiencies=["arcana", "history", "investigation", "medicine"],
        feats=["magic_initiate"],
    )
    return HeroState(
        id="h2", ordinal=1, name="Лиэль", sheet=sheet,
        creature=CreatureState(hp_current=8, hp_max=8),
    )


# модификаторы

@pytest.mark.parametrize(
    "score, mod",
    [(1, -5), (8, -1), (9, -1), (10, 0), (11, 0), (12, 1), (15, 2), (17, 3), (20, 5)],
)
def test_ability_modifier_by_score(score, mod):
    assert ability_modifier(score) == mod


@pytest.mark.parametrize(
    "ability, mod",
    [("str", 3), ("dex", 1), ("con", 2), ("int", -1), ("wis", 0), ("cha", 1)],
)
def test_ability_mod_of_hero(ability, mod):
    assert ability_mod(make_fighter(), ability) == mod


def test_proficiency_at_level_1_is_2(registry):
    assert proficiency(make_fighter(), registry) == 2


def test_proficiency_at_level_5_is_3(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    assert proficiency(hero, registry) == 3


# спасброски

@pytest.mark.parametrize(
    "ability, bonus",
    [("str", 5), ("dex", 1), ("con", 4), ("int", -1), ("wis", 0), ("cha", 1)],
)
def test_fighter_saving_throws(registry, ability, bonus):
    assert saving_throw_bonus(make_fighter(), registry, ability) == bonus


@pytest.mark.parametrize(
    "ability, bonus",
    [("str", -1), ("dex", 1), ("con", 2), ("int", 5), ("wis", 3), ("cha", 0)],
)
def test_wizard_saving_throws(registry, ability, bonus):
    assert saving_throw_bonus(make_wizard(), registry, ability) == bonus


# навыки

def test_skill_with_proficiency_adds_proficiency(registry):
    assert skill_bonus(make_fighter(), registry, "athletics") == 3 + 2


def test_skill_without_proficiency_is_plain_modifier(registry):
    assert skill_bonus(make_fighter(), registry, "acrobatics") == 1


def test_skill_without_proficiency_with_negative_modifier(registry):
    assert skill_bonus(make_fighter(), registry, "arcana") == -1


def test_perception_uses_wisdom(registry):
    assert skill_bonus(make_fighter(), registry, "perception") == 0 + 2


def test_stealth_uses_dexterity(registry):
    assert skill_bonus(make_fighter(), registry, "stealth") == 1


def test_wizard_arcana_uses_intelligence_with_proficiency(registry):
    assert skill_bonus(make_wizard(), registry, "arcana") == 3 + 2


def test_skill_bonus_grows_with_level(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    assert skill_bonus(hero, registry, "athletics") == 3 + 3


def test_unknown_skill_raises_value_error(registry):
    with pytest.raises(ValueError):
        skill_bonus(make_fighter(), registry, "juggling")


def test_passive_perception_is_10_plus_perception_bonus(registry):
    assert passive_perception(make_fighter(), registry) == 12


# инициатива

def test_initiative_is_dexterity_modifier(registry):
    assert initiative_bonus(make_fighter(), registry) == 1


def test_alert_adds_proficiency_to_initiative(registry):
    hero = make_fighter()
    hero.sheet.feats.append("alert")
    assert initiative_bonus(hero, registry) == 1 + 2


def test_alert_bonus_grows_with_level(registry):
    hero = make_fighter()
    hero.sheet.feats.append("alert")
    hero.sheet.primary.level = 5
    assert initiative_bonus(hero, registry) == 1 + 3


# КД

def test_unarmored_ac_is_10_plus_dex(registry):
    assert armor_class(make_fighter(), registry) == 11


def test_leather_armor_adds_full_dex(registry):
    assert armor_class(make_fighter(armor="leather_armor"), registry) == 11 + 1


def test_chain_mail_ignores_dex(registry):
    assert armor_class(make_fighter(armor="chain_mail"), registry) == 16


def test_shield_alone_adds_2_to_unarmored(registry):
    assert armor_class(make_fighter(shield="shield"), registry) == 10 + 1 + 2


def test_chain_mail_and_shield_give_18(registry):
    assert armor_class(make_fighter(armor="chain_mail", shield="shield"), registry) == 18


def test_defense_style_adds_1_with_armor(registry):
    # ВНИМАНИЕ: по SRD 5.2 кольчуга 16 + щит 2 + Defense 1 = 19, а не 18 (см. отчёт)
    hero = make_fighter(armor="chain_mail", shield="shield")
    hero.sheet.feats.append("defense")
    assert armor_class(hero, registry) == 19


def test_defense_style_does_nothing_without_armor(registry):
    hero = make_fighter(shield="shield")
    hero.sheet.feats.append("defense")
    assert armor_class(hero, registry) == 10 + 1 + 2


# атака оружием

def test_longsword_attack_uses_strength_and_proficiency(registry):
    assert attack_bonus(make_fighter(), registry, "longsword") == 3 + 2


def test_longsword_damage_bonus_is_strength_modifier(registry):
    assert damage_bonus(make_fighter(), registry, "longsword") == 3


def test_shortbow_attack_uses_dexterity(registry):
    assert attack_bonus(make_fighter(), registry, "shortbow") == 1 + 2


def test_shortbow_damage_bonus_is_dexterity_modifier(registry):
    assert damage_bonus(make_fighter(), registry, "shortbow") == 1


def test_finesse_dagger_takes_better_of_strength_and_dexterity(registry):
    assert attack_bonus(make_fighter(), registry, "dagger") == 3 + 2


def test_finesse_dagger_uses_dexterity_when_it_is_higher(registry):
    hero = make_fighter()
    hero.sheet.abilities["dex"] = 18
    hero.sheet.abilities["str"] = 10
    assert attack_bonus(hero, registry, "dagger") == 4 + 2


def test_attack_bonus_grows_with_proficiency(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    assert attack_bonus(hero, registry, "longsword") == 3 + 3


def test_wizard_has_no_proficiency_with_martial_weapon(registry):
    assert attack_bonus(make_wizard(), registry, "longsword") == -1


def test_wizard_has_proficiency_with_simple_finesse_weapon(registry):
    assert attack_bonus(make_wizard(), registry, "dagger") == 1 + 2


def test_unknown_weapon_raises_key_error(registry):
    with pytest.raises(KeyError):
        attack_bonus(make_fighter(), registry, "no_such_weapon")


# заклинания

def test_wizard_spell_save_dc(registry):
    assert spell_save_dc(make_wizard(), registry) == 8 + 2 + 3


def test_wizard_spell_attack_bonus(registry):
    assert spell_attack_bonus(make_wizard(), registry) == 2 + 3


def test_wizard_dc_grows_with_level(registry):
    hero = make_wizard()
    hero.sheet.primary.level = 5
    assert spell_save_dc(hero, registry) == 8 + 3 + 3


def test_wizard_level_1_has_two_first_level_slots(registry):
    assert spell_slots(make_wizard(), registry) == {1: 2}


def test_fighter_has_no_spell_slots(registry):
    assert spell_slots(make_fighter(), registry) == {}


def test_fighter_spell_save_dc_raises_value_error(registry):
    with pytest.raises(ValueError):
        spell_save_dc(make_fighter(), registry)


def test_fighter_spell_attack_bonus_raises_value_error(registry):
    with pytest.raises(ValueError):
        spell_attack_bonus(make_fighter(), registry)


# единая функция числа эффекта

def test_effect_amount_alert_is_proficiency_bonus(registry):
    effect = registry.get("feat", "alert").effects[0]
    assert effect_amount(effect, make_fighter(), registry) == 2


def test_effect_amount_alert_grows_with_level(registry):
    effect = registry.get("feat", "alert").effects[0]
    hero = make_fighter()
    hero.sheet.primary.level = 5
    assert effect_amount(effect, hero, registry) == 3


def test_effect_amount_defense_is_plain_value(registry):
    effect = registry.get("feat", "defense").effects[0]
    assert effect_amount(effect, make_fighter(), registry) == 1


def test_effect_amount_cure_wounds_adds_spellcasting_modifier(registry):
    effect = registry.get("spell", "cure_wounds").effects[0]
    assert effect_amount(effect, make_wizard(), registry) == 3


def test_effect_amount_second_wind_adds_level_for_fighter(registry):
    heal = [e for e in registry.get("feature", "second_wind").effects if e.type == "heal"][0]
    hero = make_fighter()
    hero.sheet.primary.level = 3
    assert effect_amount(heal, hero, registry) == 3


def test_effect_amount_second_wind_is_zero_for_other_class(registry):
    heal = [e for e in registry.get("feature", "second_wind").effects if e.type == "heal"][0]
    assert effect_amount(heal, make_wizard(), registry) == 0


def test_effect_amount_spellcasting_modifier_for_non_caster_raises_value_error(registry):
    effect = registry.get("spell", "cure_wounds").effects[0]
    with pytest.raises(ValueError):
        effect_amount(effect, make_fighter(), registry)


# плут: воинское оружие со свойствами finesse/light

def make_rogue():
    # СИЛ 8, ЛОВ 17 (мод. +3), остальные средние
    hero = make_fighter()
    hero.sheet.primary.class_id = "rogue"
    hero.sheet.abilities = {"str": 8, "dex": 17, "con": 14, "int": 12, "wis": 10, "cha": 10}
    return hero


def test_rogue_shortsword_attack_adds_proficiency(registry):
    assert attack_bonus(make_rogue(), registry, "shortsword") == 3 + 2


def test_rogue_scimitar_attack_adds_proficiency(registry):
    assert attack_bonus(make_rogue(), registry, "scimitar") == 3 + 2


def test_rogue_longsword_attack_has_no_proficiency(registry):
    assert attack_bonus(make_rogue(), registry, "longsword") == -1


def test_rogue_greatsword_attack_has_no_proficiency(registry):
    assert attack_bonus(make_rogue(), registry, "greatsword") == -1


def test_rogue_simple_weapon_is_proficient(registry):
    assert attack_bonus(make_rogue(), registry, "dagger") == 3 + 2


def test_rogue_shortsword_proficiency_grows_with_level(registry):
    hero = make_rogue()
    hero.sheet.primary.level = 5
    assert attack_bonus(hero, registry, "shortsword") == 3 + 3


def test_fighter_is_not_affected_by_weapon_training_properties(registry):
    assert attack_bonus(make_fighter(), registry, "shortsword") == 3 + 2


def test_wizard_has_no_proficiency_with_martial_finesse_weapon(registry):
    assert attack_bonus(make_wizard(), registry, "shortsword") == 1


# ячейки заклинаний по уровню героя (SRD 5.2)

def caster_slots(registry, class_id, level):
    hero = make_wizard()
    hero.sheet.primary.class_id = class_id
    hero.sheet.primary.level = level
    return spell_slots(hero, registry)


@pytest.mark.parametrize(
    "level, slots",
    [
        (1, {1: 2}),
        (2, {1: 3}),
        (3, {1: 4, 2: 2}),
        (4, {1: 4, 2: 3}),
        (5, {1: 4, 2: 3, 3: 2}),
    ],
)
def test_wizard_slots_by_level(registry, level, slots):
    assert caster_slots(registry, "wizard", level) == slots


@pytest.mark.parametrize(
    "level, slots",
    [
        (1, {1: 2}),
        (2, {1: 3}),
        (3, {1: 4, 2: 2}),
        (4, {1: 4, 2: 3}),
        (5, {1: 4, 2: 3, 3: 2}),
    ],
)
def test_cleric_slots_by_level_are_full_caster(registry, level, slots):
    assert caster_slots(registry, "cleric", level) == slots


@pytest.mark.parametrize(
    "level, slots",
    [
        (1, {1: 2}),
        (2, {1: 2}),
        (3, {1: 3}),
        (4, {1: 3}),
        (5, {1: 4, 2: 2}),
    ],
)
def test_ranger_slots_by_level_are_half_caster(registry, level, slots):
    assert caster_slots(registry, "ranger", level) == slots


def test_rogue_has_no_spell_slots(registry):
    assert caster_slots(registry, "rogue", 3) == {}


def test_slots_follow_progression_from_data_not_class_name(registry, tmp_path):
    from ai_dm.content.loader import load_registry

    (tmp_path / "classes").mkdir()
    (tmp_path / "classes" / "half_mage.yaml").write_text(
        "id: half_mage\nname: Полумаг\nhit_die: 8\nsaving_throws: [int]\n"
        "spellcasting:\n  ability: int\n  progression: half\n",
        encoding="utf-8",
    )
    custom = load_registry([tmp_path])
    hero = make_wizard()
    hero.sheet.primary.class_id = "half_mage"
    hero.sheet.primary.level = 5
    assert spell_slots(hero, custom) == {1: 4, 2: 2}


# ячейки из таблиц реестра (аудит 1 п. 2.10)

def test_spell_slots_for_full_level_5(registry):
    assert spell_slots_for(registry, "full", 5) == {1: 4, 2: 3, 3: 2}


def test_spell_slots_for_half_level_5(registry):
    assert spell_slots_for(registry, "half", 5) == {1: 4, 2: 2}


def test_spell_slots_for_reads_registry_table_not_code_constants(tmp_path):
    from ai_dm.content.loader import load_registry

    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "spell_slots_third.yaml").write_text(
        "id: spell_slots_third\nname: Свои ячейки\nrows:\n  '1:1': 9\n  '2:1': 7\n",
        encoding="utf-8",
    )
    custom = load_registry([tmp_path])
    assert spell_slots_for(custom, "third", 2) == {1: 7}


# К7х: armor_dex и gear_ac

def test_armor_dex_without_a_cap_is_the_dexterity(registry):
    assert armor_dex(registry.get("armor", "leather_armor"), 3) == 3


def test_armor_dex_without_a_cap_keeps_a_negative_dexterity(registry):
    assert armor_dex(registry.get("armor", "leather_armor"), -1) == -1


def test_armor_dex_cap_zero_gives_zero(registry):
    assert armor_dex(registry.get("armor", "chain_mail"), 3) == 0


def test_armor_dex_cap_zero_cancels_a_negative_dexterity_too(registry):
    assert armor_dex(registry.get("armor", "chain_mail"), -1) == 0


def test_armor_dex_cap_cuts_the_dexterity(registry):
    assert armor_dex(registry.get("armor", "chain_shirt"), 4) == 2


def test_armor_dex_under_the_cap_is_unchanged(registry):
    assert armor_dex(registry.get("armor", "chain_shirt"), 1) == 1


def test_armor_dex_equal_to_the_cap_is_unchanged(registry):
    assert armor_dex(registry.get("armor", "chain_shirt"), 2) == 2


def test_gear_ac_without_anything_is_ten_plus_dex(registry):
    assert gear_ac(registry, None, None, 2) == 12


def test_gear_ac_with_leather_armor(registry):
    assert gear_ac(registry, "leather_armor", None, 2) == 13


def test_gear_ac_with_a_shield_only(registry):
    assert gear_ac(registry, None, "shield", 2) == 14


def test_gear_ac_with_leather_and_a_shield(registry):
    assert gear_ac(registry, "leather_armor", "shield", 2) == 15


def test_gear_ac_chain_mail_ignores_dexterity(registry):
    assert gear_ac(registry, "chain_mail", None, 3) == 16


def test_gear_ac_chain_shirt_is_capped(registry):
    assert gear_ac(registry, "chain_shirt", "shield", 4) == 13 + 2 + 2


def test_gear_ac_with_negative_dexterity(registry):
    assert gear_ac(registry, None, None, -1) == 9


def test_gear_ac_equals_the_hero_ac_without_extras(registry):
    for armor in (None, "leather_armor", "chain_shirt", "chain_mail"):
        for shield in (None, "shield"):
            hero = make_fighter(armor=armor, shield=shield)
            assert gear_ac(registry, armor, shield, 1) == armor_class(hero, registry)


def test_hero_ac_parts_keep_their_sum_for_a_capped_armor(registry):
    hero = make_fighter(armor="chain_mail", shield="shield")
    parts = armor_class_parts(hero, registry)
    assert [(name, value) for name, value, _ in parts] == [
        ("Кольчуга", 16), ("Лов", 0), ("Щит", 2),
    ]


def test_hero_ac_parts_note_a_zero_cap_only_when_dexterity_is_lost(registry):
    hero = make_fighter(armor="chain_mail")
    parts = armor_class_parts(hero, registry)
    assert parts[1][1] == 0
    assert parts[1][2] != ""


def test_hero_ac_parts_have_no_note_for_free_dexterity(registry):
    parts = armor_class_parts(make_fighter(armor="leather_armor"), registry)
    assert parts[1] == ("Лов", 1, "")
