# Минимальный SRD-контент этапа 1 (ARCHITECTURE B, таблица). Контракт id (латиница snake_case)
# и ключевых полей; загрузка -- ai_dm.content.loader.load_registry(), см. test_content_loader.py.
#
# Id контента:
#   class:      fighter, wizard, cleric, rogue, ranger
#   species:    human, elf, dwarf, halfling
#   background: acolyte, criminal, sage, soldier
#   feat:       alert, savage_attacker, skilled, magic_initiate   (category: origin)
#               defense                                            (category: fighting_style)
#   weapon:     longsword, greatsword, scimitar, shortsword, dagger, shortbow, light_crossbow, spear
#   armor:      leather_armor, chain_mail, shield
#   item:       potion_of_healing
#   spell:      fire_bolt, magic_missile, burning_hands, cure_wounds, bless
#   condition:  blinded, charmed, deafened, exhaustion, frightened, grappled, incapacitated,
#               invisible, paralyzed, petrified, poisoned, prone, restrained, stunned, unconscious
#   monster:    goblin_warrior, goblin_boss, guard
#   mastery:    graze, sap, vex, topple
#   feature:    second_wind, fighting_style, weapon_mastery, spellcasting,
#               resourceful, skillful, versatile, fey_ancestry, dwarven_resilience, luck, brave
#   table:      xp, proficiency, dc, cr_xp, standard_array, point_buy, spell_slots_full,
#               spell_slots_half, individual_treasure, lifespan, encounter_budget, hoard,
#               pact_slots, damage_severity (К0б: таблицы 1-20, см. test_tables_1_20.py)
#               (вид "table", srd/data/tables/*.yaml; аудит 1 п. 2.10:
#               константы SRD живут в данных; point_buy: rows["8".."15"] -- стоимость,
#               rows["budget"] -- 27; spell_slots_*: ключ "уровень:круг" -> ячейки)
#
# Характеристики -- ключи "str", "dex", "con", "int", "wis", "cha".
# Навыки -- acrobatics, animal_handling, arcana, athletics, deception, history, insight,
#   intimidation, investigation, medicine, nature, perception, performance, persuasion,
#   religion, sleight_of_hand, stealth, survival.
#
# Поля моделей (то, что проверяют тесты):
#   class:      hit_die: int, saving_throws: list[str], skill_choices {count, options},
#               armor_training: list[str] (light|medium|heavy|shield),
#               weapon_training: list[str] (simple|martial), weapon_mastery_count: int = 0,
#               spellcasting: {ability, progression: full|half} | None,
#               features: [{level, feature}],
#               weapon_training_properties: list[str] (finesse|light -- воинское оружие с любым
#               из свойств; плут)
#   species:    speed_ft: int, traits: list[str]  (id умений вида)
#   background: abilities: list[str] (3), skills: list[str] (2), tool: str, feat: str,
#               equipment: list[str] (id существующих предметов), gold_cp: int
#   feat:       category: str (origin | fighting_style)
#   weapon:     category (simple|martial), kind (melee|ranged), damage_dice, damage_type,
#               properties: list[str] (finesse, light, heavy, two_handed, versatile, thrown,
#               ammunition, loading), versatile_dice: str | None, mastery: str | None,
#               range_normal_ft / range_long_ft: int | None, cost_cp: int
#   armor:      category (light|medium|heavy|shield), ac: int (у щита -- бонус),
#               dex_cap: int | None (None -- без предела, 0 -- тяжёлый), strength_min: int, cost_cp
#   item:       cost_cp: int, effects: [{type: "heal", dice: "2d4+2"}]
#   spell:      level: int (0 -- заговор), school: str,
#               range_kind: self|touch|ranged, range_ft: int | None (только для ranged),
#               duration_s: int | None (None -- мгновенное; "1m" -> 60),
#               concentration: bool, classes: list[str],
#               upcast: {per_slot_level: {dice?, count?, targets?}} | None (Bless: targets,
#               п. 2.14), cantrip_scaling: {уровень: кости}
#   effect:     targets (число целей, Bless) отдельно от count (дротики)
#   feature second_wind: resource-эффект pool=second_wind, max=2,
#               recover [{on: short_rest, amount: 1}, {on: long_rest, amount: "all"}]
#   monster:    actions[].advantage_damage_dice (доп. урон при преимуществе, "1d4" у гоблинов),
#               multiattack: [{action: <имя действия из actions>, count: int}]
#   condition:  id, name
#   monster:    ac: int, hp: int, cr: str ("1/8", "1/4", "1"), abilities: dict[str, int];
#               поля xp нет -- опыт из table cr_xp по cr (аудит 1 п. 2.11)
#   mastery:    id, name
#
# Числа, которые автор теста не зафиксировал (проверяется только тип/структура): HP goblin_warrior,
# цены всего, кроме longsword/chain_mail/shield, школа cure_wounds, размер видов.
import pytest

CLASSES = ["fighter", "wizard", "cleric", "rogue", "ranger"]
SPECIES = ["human", "elf", "dwarf", "halfling"]
BACKGROUNDS = ["acolyte", "criminal", "sage", "soldier"]
ORIGIN_FEATS = ["alert", "savage_attacker", "skilled", "magic_initiate"]
WEAPONS = [
    "longsword", "greatsword", "scimitar", "shortsword", "dagger", "shortbow", "light_crossbow",
    "spear",
]
ARMOR = ["leather_armor", "chain_mail", "shield"]
SPELLS = ["fire_bolt", "magic_missile", "burning_hands", "cure_wounds", "bless"]
CONDITIONS = [
    "blinded", "charmed", "deafened", "exhaustion", "frightened", "grappled", "incapacitated",
    "invisible", "paralyzed", "petrified", "poisoned", "prone", "restrained", "stunned",
    "unconscious",
]
MONSTERS = ["goblin_warrior", "goblin_boss", "guard"]
MASTERIES = ["graze", "sap", "vex", "topple"]
ABILITIES = {"str", "dex", "con", "int", "wis", "cha"}


@pytest.mark.parametrize("class_id", CLASSES)
def test_class_exists(registry, class_id):
    assert registry.has("class", class_id)


@pytest.mark.parametrize("species_id", SPECIES)
def test_species_exists(registry, species_id):
    assert registry.has("species", species_id)


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_exists(registry, background_id):
    assert registry.has("background", background_id)


@pytest.mark.parametrize("feat_id", ORIGIN_FEATS)
def test_origin_feat_exists(registry, feat_id):
    assert registry.has("feat", feat_id)


@pytest.mark.parametrize("feat_id", ORIGIN_FEATS)
def test_origin_feat_has_origin_category(registry, feat_id):
    assert registry.get("feat", feat_id).category == "origin"


def test_defense_is_fighting_style_feat(registry):
    assert registry.get("feat", "defense").category == "fighting_style"


@pytest.mark.parametrize("weapon_id", WEAPONS)
def test_weapon_exists(registry, weapon_id):
    assert registry.has("weapon", weapon_id)


@pytest.mark.parametrize("armor_id", ARMOR)
def test_armor_exists(registry, armor_id):
    assert registry.has("armor", armor_id)


def test_potion_of_healing_exists(registry):
    assert registry.has("item", "potion_of_healing")


@pytest.mark.parametrize("spell_id", SPELLS)
def test_spell_exists(registry, spell_id):
    assert registry.has("spell", spell_id)


@pytest.mark.parametrize("condition_id", CONDITIONS)
def test_condition_exists(registry, condition_id):
    assert registry.has("condition", condition_id)


def test_there_are_exactly_15_conditions(registry):
    assert len(registry.ids("condition")) == 15


@pytest.mark.parametrize("monster_id", MONSTERS)
def test_monster_exists(registry, monster_id):
    assert registry.has("monster", monster_id)


@pytest.mark.parametrize("mastery_id", MASTERIES)
def test_mastery_exists(registry, mastery_id):
    assert registry.has("mastery", mastery_id)


# классы

@pytest.mark.parametrize(
    "class_id, hit_die, saves",
    [
        ("fighter", 10, {"str", "con"}),
        ("wizard", 6, {"int", "wis"}),
        ("cleric", 8, {"wis", "cha"}),
        ("rogue", 8, {"dex", "int"}),
        ("ranger", 10, {"str", "dex"}),
    ],
)
def test_class_hit_die_and_saving_throws(registry, class_id, hit_die, saves):
    cls = registry.get("class", class_id)
    assert cls.hit_die == hit_die
    assert set(cls.saving_throws) == saves


def test_fighter_trains_all_armor_and_shields(registry):
    assert set(registry.get("class", "fighter").armor_training) == {
        "light", "medium", "heavy", "shield",
    }


def test_fighter_trains_simple_and_martial_weapons(registry):
    assert set(registry.get("class", "fighter").weapon_training) == {"simple", "martial"}


def test_wizard_trains_only_simple_weapons(registry):
    assert set(registry.get("class", "wizard").weapon_training) == {"simple"}


def test_wizard_wears_no_armor(registry):
    assert registry.get("class", "wizard").armor_training == []


def test_fighter_picks_two_skills(registry):
    assert registry.get("class", "fighter").skill_choices.count == 2


def test_fighter_skill_options_include_athletics_and_perception(registry):
    options = registry.get("class", "fighter").skill_choices.options
    assert "athletics" in options
    assert "perception" in options


def test_fighter_skill_options_exclude_arcana(registry):
    assert "arcana" not in registry.get("class", "fighter").skill_choices.options


def test_fighter_has_three_weapon_masteries(registry):
    assert registry.get("class", "fighter").weapon_mastery_count == 3


def test_wizard_has_no_weapon_masteries(registry):
    assert registry.get("class", "wizard").weapon_mastery_count == 0


@pytest.mark.parametrize("feature_id", ["second_wind", "fighting_style", "weapon_mastery"])
def test_fighter_level_1_features(registry, feature_id):
    features = registry.get("class", "fighter").features
    assert (1, feature_id) in [(f.level, f.feature) for f in features]


def test_fighter_is_not_a_caster(registry):
    assert registry.get("class", "fighter").spellcasting is None


def test_wizard_casts_with_intelligence(registry):
    assert registry.get("class", "wizard").spellcasting.ability == "int"


def test_wizard_level_1_has_spellcasting_feature(registry):
    features = registry.get("class", "wizard").features
    assert (1, "spellcasting") in [(f.level, f.feature) for f in features]


def test_cleric_casts_with_wisdom(registry):
    assert registry.get("class", "cleric").spellcasting.ability == "wis"


# виды

@pytest.mark.parametrize("species_id", SPECIES)
def test_species_speed_is_30_feet(registry, species_id):
    assert registry.get("species", species_id).speed_ft == 30


@pytest.mark.parametrize(
    "species_id, traits",
    [
        ("human", {"resourceful", "skillful", "versatile"}),
        ("elf", {"fey_ancestry"}),
        ("dwarf", {"dwarven_resilience"}),
        ("halfling", {"luck", "brave"}),
    ],
)
def test_species_traits_include_required_ones(registry, species_id, traits):
    assert traits <= set(registry.get("species", species_id).traits)


# предыстории

@pytest.mark.parametrize(
    "background_id, abilities, skills, feat",
    [
        ("acolyte", {"int", "wis", "cha"}, {"insight", "religion"}, "magic_initiate"),
        ("criminal", {"dex", "con", "int"}, {"sleight_of_hand", "stealth"}, "alert"),
        ("sage", {"con", "int", "wis"}, {"arcana", "history"}, "magic_initiate"),
        ("soldier", {"str", "dex", "con"}, {"athletics", "intimidation"}, "savage_attacker"),
    ],
)
def test_background_structure_by_srd_5_2(registry, background_id, abilities, skills, feat):
    background = registry.get("background", background_id)
    assert set(background.abilities) == abilities
    assert set(background.skills) == skills
    assert background.feat == feat
    assert isinstance(background.tool, str)
    assert background.tool != ""


# оружие

@pytest.mark.parametrize(
    "weapon_id, category, kind, dice, damage_type",
    [
        ("longsword", "martial", "melee", "1d8", "slashing"),
        ("greatsword", "martial", "melee", "2d6", "slashing"),
        ("scimitar", "martial", "melee", "1d6", "slashing"),
        ("shortsword", "martial", "melee", "1d6", "piercing"),
        ("dagger", "simple", "melee", "1d4", "piercing"),
        ("shortbow", "simple", "ranged", "1d6", "piercing"),
        ("light_crossbow", "simple", "ranged", "1d8", "piercing"),
        ("spear", "simple", "melee", "1d6", "piercing"),
    ],
)
def test_weapon_damage_and_category(registry, weapon_id, category, kind, dice, damage_type):
    weapon = registry.get("weapon", weapon_id)
    assert weapon.category == category
    assert weapon.kind == kind
    assert weapon.damage_dice == dice
    assert weapon.damage_type == damage_type


@pytest.mark.parametrize(
    "weapon_id, properties",
    [
        ("longsword", {"versatile"}),
        ("greatsword", {"heavy", "two_handed"}),
        ("scimitar", {"finesse", "light"}),
        ("shortsword", {"finesse", "light"}),
        ("dagger", {"finesse", "light", "thrown"}),
        ("shortbow", {"ammunition", "two_handed"}),
        ("light_crossbow", {"ammunition", "loading", "two_handed"}),
        ("spear", {"thrown", "versatile"}),
    ],
)
def test_weapon_properties(registry, weapon_id, properties):
    assert properties <= set(registry.get("weapon", weapon_id).properties)


def test_longsword_versatile_damage_is_1d10(registry):
    assert registry.get("weapon", "longsword").versatile_dice == "1d10"


def test_spear_versatile_damage_is_1d8(registry):
    assert registry.get("weapon", "spear").versatile_dice == "1d8"


@pytest.mark.parametrize(
    "weapon_id, mastery",
    [
        ("longsword", "sap"),
        ("greatsword", "graze"),
        ("shortsword", "vex"),
        ("shortbow", "vex"),
        ("spear", "sap"),
    ],
)
def test_weapon_mastery_by_srd_5_2(registry, weapon_id, mastery):
    assert registry.get("weapon", weapon_id).mastery == mastery


@pytest.mark.parametrize("weapon_id", WEAPONS)
def test_weapon_mastery_is_none_or_existing_mastery(registry, weapon_id):
    # dagger/scimitar (Nick) и light_crossbow (Slow) -- мастерства вне минимума этапа 1:
    # либо их данные добавлены, либо mastery = None
    mastery = registry.get("weapon", weapon_id).mastery
    assert mastery is None or registry.has("mastery", mastery)


@pytest.mark.parametrize("weapon_id", ["shortbow", "light_crossbow"])
def test_bow_range_in_feet(registry, weapon_id):
    weapon = registry.get("weapon", weapon_id)
    assert weapon.range_normal_ft == 80
    assert weapon.range_long_ft == 320


def test_melee_weapon_without_thrown_has_no_range(registry):
    weapon = registry.get("weapon", "longsword")
    assert weapon.range_normal_ft is None
    assert weapon.range_long_ft is None


@pytest.mark.parametrize("weapon_id", ["dagger", "spear"])
def test_thrown_weapon_range_is_20_60(registry, weapon_id):
    weapon = registry.get("weapon", weapon_id)
    assert (weapon.range_normal_ft, weapon.range_long_ft) == (20, 60)


@pytest.mark.parametrize("weapon_id", WEAPONS)
def test_weapon_cost_is_positive_int(registry, weapon_id):
    cost = registry.get("weapon", weapon_id).cost_cp
    assert isinstance(cost, int)
    assert cost > 0


def test_longsword_costs_15_gold(registry):
    assert registry.get("weapon", "longsword").cost_cp == 1500


# доспехи

def test_leather_armor(registry):
    armor = registry.get("armor", "leather_armor")
    assert armor.category == "light"
    assert armor.ac == 11
    assert armor.dex_cap is None


def test_chain_mail(registry):
    armor = registry.get("armor", "chain_mail")
    assert armor.category == "heavy"
    assert armor.ac == 16
    assert armor.dex_cap == 0
    assert armor.strength_min == 13


def test_shield_gives_plus_2(registry):
    armor = registry.get("armor", "shield")
    assert armor.category == "shield"
    assert armor.ac == 2


def test_chain_mail_costs_75_gold(registry):
    assert registry.get("armor", "chain_mail").cost_cp == 7500


def test_shield_costs_10_gold(registry):
    assert registry.get("armor", "shield").cost_cp == 1000


# расходники

def test_potion_of_healing_heals_2d4_plus_2(registry):
    effect = registry.get("item", "potion_of_healing").effects[0]
    assert effect.type == "heal"
    assert effect.dice == "2d4+2"


def test_potion_of_healing_cost_is_int(registry):
    assert isinstance(registry.get("item", "potion_of_healing").cost_cp, int)


# заклинания

@pytest.mark.parametrize(
    "spell_id, level",
    [
        ("fire_bolt", 0),
        ("magic_missile", 1),
        ("burning_hands", 1),
        ("cure_wounds", 1),
        ("bless", 1),
    ],
)
def test_spell_level(registry, spell_id, level):
    assert registry.get("spell", spell_id).level == level


@pytest.mark.parametrize("spell_id", ["fire_bolt", "magic_missile", "burning_hands"])
def test_attack_spells_are_evocation(registry, spell_id):
    assert registry.get("spell", spell_id).school == "evocation"


def test_bless_is_enchantment(registry):
    assert registry.get("spell", "bless").school == "enchantment"


def test_cure_wounds_school_is_a_string(registry):
    assert isinstance(registry.get("spell", "cure_wounds").school, str)


@pytest.mark.parametrize(
    "spell_id, range_ft", [("fire_bolt", 120), ("magic_missile", 120), ("bless", 30)]
)
def test_spell_range_in_feet(registry, spell_id, range_ft):
    assert registry.get("spell", spell_id).range_ft == range_ft


def test_bless_requires_concentration(registry):
    assert registry.get("spell", "bless").concentration is True


@pytest.mark.parametrize(
    "spell_id", ["fire_bolt", "magic_missile", "burning_hands", "cure_wounds"]
)
def test_other_spells_do_not_require_concentration(registry, spell_id):
    assert registry.get("spell", spell_id).concentration is False


@pytest.mark.parametrize(
    "spell_id, class_id",
    [
        ("fire_bolt", "wizard"),
        ("magic_missile", "wizard"),
        ("burning_hands", "wizard"),
        ("cure_wounds", "cleric"),
        ("bless", "cleric"),
    ],
)
def test_spell_is_on_class_list(registry, spell_id, class_id):
    assert class_id in registry.get("spell", spell_id).classes


# монстры

@pytest.mark.parametrize(
    "monster_id, ac, cr, xp",
    [
        ("goblin_warrior", 15, "1/4", 50),
        ("goblin_boss", 17, "1", 200),
        ("guard", 16, "1/8", 25),
    ],
)
def test_monster_ac_cr_and_xp_by_cr(registry, monster_id, ac, cr, xp):
    # аудит 1 п. 2.11: у монстра нет поля xp, опыт -- из tables/cr_xp по cr
    monster = registry.get("monster", monster_id)
    assert monster.ac == ac
    assert monster.cr == cr
    assert registry.get("table", "cr_xp").rows[monster.cr] == xp


@pytest.mark.parametrize("monster_id", MONSTERS)
def test_monster_has_no_xp_field(registry, monster_id):
    assert "xp" not in type(registry.get("monster", monster_id)).model_fields
    assert "xp" not in registry.get("monster", monster_id).model_dump()


@pytest.mark.parametrize("monster_id", MONSTERS)
def test_monster_cr_is_in_cr_xp_table(registry, monster_id):
    assert registry.get("monster", monster_id).cr in registry.get("table", "cr_xp").rows


def test_guard_hp_is_11(registry):
    assert registry.get("monster", "guard").hp == 11


def test_goblin_boss_hp_is_21(registry):
    assert registry.get("monster", "goblin_boss").hp == 21


@pytest.mark.parametrize("monster_id", MONSTERS)
def test_monster_hp_is_positive_int(registry, monster_id):
    hp = registry.get("monster", monster_id).hp
    assert isinstance(hp, int)
    assert hp > 0


@pytest.mark.parametrize("monster_id", MONSTERS)
def test_monster_has_all_six_abilities(registry, monster_id):
    assert set(registry.get("monster", monster_id).abilities) == ABILITIES


# закрытый список навыков

SKILL_IDS = {
    "acrobatics", "animal_handling", "arcana", "athletics", "deception", "history", "insight",
    "intimidation", "investigation", "medicine", "nature", "perception", "performance",
    "persuasion", "religion", "sleight_of_hand", "stealth", "survival",
}


def test_skill_literal_has_18_skills():
    from typing import get_args

    from ai_dm.content.models.common import Skill

    assert set(get_args(Skill)) == SKILL_IDS


def test_skills_mapping_lives_in_content_common():
    from ai_dm.content.models.common import SKILLS

    assert set(SKILLS) == SKILL_IDS
    assert SKILLS["athletics"] == "str"
    assert SKILLS["stealth"] == "dex"


@pytest.mark.parametrize("class_id", CLASSES)
def test_class_skill_options_are_known_skills(registry, class_id):
    options = registry.get("class", class_id).skill_choices.options
    assert set(options) <= SKILL_IDS


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_skills_are_known_skills(registry, background_id):
    assert set(registry.get("background", background_id).skills) <= SKILL_IDS


# заклинательная прогрессия

@pytest.mark.parametrize(
    "class_id, progression", [("wizard", "full"), ("cleric", "full"), ("ranger", "half")]
)
def test_spellcasting_progression(registry, class_id, progression):
    assert registry.get("class", class_id).spellcasting.progression == progression


def test_ranger_casts_with_wisdom(registry):
    assert registry.get("class", "ranger").spellcasting.ability == "wis"


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
def test_non_casters_have_no_spellcasting(registry, class_id):
    assert registry.get("class", class_id).spellcasting is None


# плут: воинское оружие со свойствами

def test_rogue_trains_finesse_and_light_martial_weapons(registry):
    rogue = registry.get("class", "rogue")
    assert set(rogue.weapon_training_properties) == {"finesse", "light"}
    assert rogue.weapon_training == ["simple"]


@pytest.mark.parametrize("class_id", ["fighter", "wizard", "cleric", "ranger"])
def test_other_classes_have_no_weapon_training_properties(registry, class_id):
    assert registry.get("class", class_id).weapon_training_properties == []


@pytest.mark.parametrize("weapon_id", ["shortsword", "scimitar"])
def test_rogue_martial_weapons_have_finesse_or_light(registry, weapon_id):
    weapon = registry.get("weapon", weapon_id)
    assert weapon.category == "martial"
    assert {"finesse", "light"} & set(weapon.properties)


# Second Wind: пул данными

def second_wind_resource(registry):
    effects = registry.get("feature", "second_wind").model_dump()["effects"]
    return [e for e in effects if e["type"] == "resource"][0]


def test_second_wind_resource_pool_key(registry):
    assert second_wind_resource(registry)["pool"] == "second_wind"


def test_second_wind_pool_max_is_2(registry):
    assert second_wind_resource(registry)["max"] == 2


def test_second_wind_short_rest_restores_one(registry):
    recover = second_wind_resource(registry)["recover"]
    short = [r for r in recover if r["on"] == "short_rest"]
    assert [r["amount"] for r in short] == [1]


def test_second_wind_long_rest_restores_all(registry):
    recover = second_wind_resource(registry)["recover"]
    long_ = [r for r in recover if r["on"] == "long_rest"]
    assert [r["amount"] for r in long_] == ["all"]


def test_second_wind_heal_adds_fighter_level(registry):
    effects = registry.get("feature", "second_wind").effects
    heal = [e for e in effects if e.type == "heal"][0]
    assert heal.dice == "1d10"
    assert heal.add == "class_level"
    assert heal.class_id == "fighter"


# таблицы SRD

TABLES = [
    "xp", "proficiency", "dc", "cr_xp",
    "standard_array", "point_buy", "spell_slots_full", "spell_slots_half",
    "individual_treasure", "lifespan", "encounter_budget", "hoard",
    "pact_slots", "damage_severity",
]


@pytest.mark.parametrize("table_id", TABLES)
def test_table_exists(registry, table_id):
    assert registry.has("table", table_id)


def test_there_are_fourteen_srd_tables(registry):
    assert len(TABLES) == 14
    assert registry.ids("table") == sorted(TABLES)


def test_standard_array_table_has_srd_values(registry):
    rows = registry.get("table", "standard_array").rows
    assert sorted(rows.values(), reverse=True) == [15, 14, 13, 12, 10, 8]


def test_point_buy_table_has_srd_costs(registry):
    rows = registry.get("table", "point_buy").rows
    costs = {int(k): v for k, v in rows.items() if k != "budget"}
    assert costs == {8: 0, 9: 1, 10: 2, 11: 3, 12: 4, 13: 5, 14: 7, 15: 9}


def test_point_buy_table_budget_is_27(registry):
    assert registry.get("table", "point_buy").rows["budget"] == 27


def only_levels_up_to(rows, top):
    # уровни 6-20 проверяет test_tables_1_20.py
    return {key: count for key, count in rows.items() if int(key.split(":")[0]) <= top}


def test_spell_slots_full_table_by_level_and_circle(registry):
    rows = only_levels_up_to(registry.get("table", "spell_slots_full").rows, 5)
    assert rows == {
        "1:1": 2, "2:1": 3, "3:1": 4, "3:2": 2, "4:1": 4, "4:2": 3,
        "5:1": 4, "5:2": 3, "5:3": 2,
    }


def test_spell_slots_half_table_by_level_and_circle(registry):
    rows = only_levels_up_to(registry.get("table", "spell_slots_half").rows, 5)
    assert rows == {"1:1": 2, "2:1": 2, "3:1": 3, "4:1": 3, "5:1": 4, "5:2": 2}


@pytest.mark.parametrize("table_id", TABLES)
def test_table_is_not_empty(registry, table_id):
    assert registry.get("table", table_id).model_dump() != {}


# предыстории: снаряжение и золото

@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_has_starting_equipment(registry, background_id):
    assert len(registry.get("background", background_id).equipment) > 0


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_equipment_items_exist(registry, background_id):
    for item_id in registry.get("background", background_id).equipment:
        assert any(registry.has(kind, item_id) for kind in ("weapon", "armor", "item"))


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_gold_option_is_50_gp(registry, background_id):
    # аудит 1 п. 2.10: BACKGROUND_GOLD_B_CP стал полем предыстории gold_option_cp
    assert registry.get("background", background_id).gold_option_cp == 5000


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_equipment_and_gold_fit_50_gp_budget(registry, background_id):
    # P3: сумма цен предметов + gold_cp не больше 5000 мм
    b = registry.get("background", background_id)
    total = b.gold_cp
    for item_id in b.equipment:
        kind = [k for k in ("weapon", "armor", "item") if registry.has(k, item_id)][0]
        total += registry.get(kind, item_id).cost_cp
    assert total <= 5000


@pytest.mark.parametrize("feat_id, repeatable", [
    ("skilled", True), ("magic_initiate", True), ("alert", False),
    ("savage_attacker", False), ("defense", False),
])
def test_feat_repeatable_flag(registry, feat_id, repeatable):
    # P5 / аудит 1 п. 2.2: Repeatable по SRD -- Одарённый и Посвящённый в магию
    assert registry.get("feat", feat_id).repeatable is repeatable


def test_skilled_asks_for_three_skills_or_tools(registry):
    effects = registry.get("feat", "skilled").effects
    assert [(e.type, e.target, e.count) for e in effects] == [
        ("proficiency", "skill_or_tool", 3)
    ]


@pytest.mark.parametrize("background_id", BACKGROUNDS)
def test_background_gold_is_positive_int(registry, background_id):
    gold = registry.get("background", background_id).gold_cp
    assert isinstance(gold, int)
    assert gold > 0


# вид человека

def test_human_skillful_grants_one_skill_of_choice(registry):
    effect = registry.get("feature", "skillful").effects[0]
    assert effect.type == "proficiency"
    assert effect.target == "skill"
    assert effect.count == 1


def test_human_versatile_gives_an_origin_feat_of_choice(registry):
    feature = registry.get("feature", "versatile")
    assert feature.effects != [] or feature.handler is not None


# заклинания: дальность и длительность

@pytest.mark.parametrize(
    "spell_id, kind",
    [
        ("fire_bolt", "ranged"),
        ("magic_missile", "ranged"),
        ("bless", "ranged"),
        ("cure_wounds", "touch"),
        ("burning_hands", "self"),
    ],
)
def test_spell_range_kind(registry, spell_id, kind):
    assert registry.get("spell", spell_id).range_kind == kind


@pytest.mark.parametrize("spell_id", ["cure_wounds", "burning_hands"])
def test_touch_and_self_spells_have_no_range_ft(registry, spell_id):
    assert registry.get("spell", spell_id).range_ft is None


def test_fire_bolt_range_is_120_feet(registry):
    spell = registry.get("spell", "fire_bolt")
    assert (spell.range_kind, spell.range_ft) == ("ranged", 120)


def test_bless_is_concentration_for_one_minute(registry):
    spell = registry.get("spell", "bless")
    assert spell.concentration is True
    assert spell.duration_s == 60


@pytest.mark.parametrize(
    "spell_id", ["fire_bolt", "magic_missile", "burning_hands", "cure_wounds"]
)
def test_instant_spells_have_no_duration_seconds(registry, spell_id):
    assert registry.get("spell", spell_id).duration_s is None


def test_bless_targets_three_creatures_not_count(registry):
    effects = registry.get("spell", "bless").effects
    assert [e.targets for e in effects] == [3, 3]
    assert [e.count for e in effects] == [None, None]


def test_magic_missile_has_three_darts_in_count_not_targets(registry):
    damage = registry.get("spell", "magic_missile").effects[0]
    assert damage.count == 3
    assert damage.targets is None


def test_burning_hands_upcast_adds_1d6_per_slot_level(registry):
    upcast = registry.get("spell", "burning_hands").model_dump()["upcast"]
    assert upcast["per_slot_level"]["dice"] == "1d6"


def test_cure_wounds_upcast_adds_2d8_per_slot_level(registry):
    upcast = registry.get("spell", "cure_wounds").model_dump()["upcast"]
    assert upcast["per_slot_level"]["dice"] == "2d8"


def test_magic_missile_upcast_adds_one_dart_per_slot_level(registry):
    upcast = registry.get("spell", "magic_missile").model_dump()["upcast"]
    assert upcast["per_slot_level"]["count"] == 1


def test_bless_upcast_adds_one_target_per_slot_level(registry):
    upcast = registry.get("spell", "bless").model_dump()["upcast"]
    assert upcast["per_slot_level"]["targets"] == 1


def test_bless_upcast_has_no_count(registry):
    upcast = registry.get("spell", "bless").model_dump()["upcast"]
    assert upcast["per_slot_level"].get("count") is None


def test_fire_bolt_grows_at_levels_5_11_17(registry):
    scaling = registry.get("spell", "fire_bolt").model_dump()["cantrip_scaling"]
    assert set(scaling) == {5, 11, 17}


# монстры: действия

def action_by_name(monster, name):
    return [a for a in monster.actions if a.name == name][0]


@pytest.mark.parametrize("monster_id", ["goblin_warrior", "goblin_boss", "guard"])
def test_monster_actions_are_not_empty(registry, monster_id):
    assert len(registry.get("monster", monster_id).actions) > 0


def test_goblin_warrior_has_melee_and_ranged_attack(registry):
    kinds = {a.kind for a in registry.get("monster", "goblin_warrior").actions}
    assert kinds == {"melee", "ranged"}


def test_goblin_warrior_attacks_have_bonus_and_damage(registry):
    for action in registry.get("monster", "goblin_warrior").actions:
        assert action.attack_bonus == 4
        assert action.damage_dice == "1d6+2"


def test_goblin_warrior_ranged_attack_is_a_shortbow_80_320(registry):
    ranged = [a for a in registry.get("monster", "goblin_warrior").actions if a.kind == "ranged"]
    assert (ranged[0].range_normal_ft, ranged[0].range_long_ft) == (80, 320)
    assert ranged[0].damage_type == "piercing"


def test_goblin_warrior_deals_extra_1d4_with_advantage_on_every_attack(registry):
    for action in registry.get("monster", "goblin_warrior").actions:
        assert action.advantage_damage_dice == "1d4"


def test_guard_has_no_advantage_damage(registry):
    for action in registry.get("monster", "guard").actions:
        assert action.advantage_damage_dice is None


def test_goblin_boss_has_multiattack_of_two_or_more_attacks(registry):
    boss = registry.get("monster", "goblin_boss")
    assert len(boss.multiattack) >= 1
    assert sum(step.count for step in boss.multiattack) >= 2


def test_goblin_boss_multiattack_refers_to_its_own_actions(registry):
    boss = registry.get("monster", "goblin_boss")
    names = [a.name for a in boss.actions]
    for step in boss.multiattack:
        assert step.action in names


def test_goblin_boss_multiattack_uses_melee_action(registry):
    boss = registry.get("monster", "goblin_boss")
    first = action_by_name(boss, boss.multiattack[0].action)
    assert first.kind == "melee"


@pytest.mark.parametrize("monster_id", ["goblin_warrior", "guard"])
def test_monsters_without_multiattack_have_empty_list(registry, monster_id):
    assert registry.get("monster", monster_id).multiattack == []


# Item.tool — признак инструмента

@pytest.mark.parametrize("item_id", ["thieves_tools", "calligraphers_supplies", "gaming_set"])
def test_srd_tools_are_marked_as_tools(registry, item_id):
    assert registry.get("item", item_id).tool is True


@pytest.mark.parametrize("item_id", ["crowbar", "potion_of_healing", "parchment"])
def test_srd_non_tools_are_not_tools(registry, item_id):
    assert registry.get("item", item_id).tool is False


def test_srd_background_tools_are_tools(registry):
    for background_id in registry.ids("background"):
        tool = registry.get("background", background_id).tool
        assert registry.get("item", tool).tool is True
