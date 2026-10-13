# Импровизированное оружие (docs/COMBAT-EXTRAS-PLAN.md, разд. 2, ответы проектировщика 1 и 4).
# Фиксированные варианты меню, всегда доступные герою (предмета в инвентаре не нужно):
#   improvised        -- melee, бонус = СИЛ (без БМ), урон 1d4 + СИЛ дробящий
#   improvised_thrown -- ranged 20/60 фт, те же бонус и урон; в зоне врага и на соседней зоне --
#       помеха; дальше 60 фт (через зону) недоступен
#   порядок в attacks_of: оружие, безоружный, импровизированное ближнее, бросок
# Это обычные атаки, не improvise() (проверка навыка) -- та работает как раньше.
# Герой -- воин (СИЛ +3, БМ +2): бонус +3, урон 1d4+3. Гоблин: КД 15, 10 HP.
from combat_kit import ScriptedRng, creature, hp, make_engine, make_fighter, mon, option_ids

from ai_dm.combat.actions.attack import attacks_of


def duel(registry, cfg, rng, goblin_zone="hall"):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def info_of(engine, attack_id):
    return [i for i in attacks_of(engine, "hero") if i.id == attack_id][0]


# attacks_of

def test_attack_order_is_weapons_unarmed_improvised_thrown(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    ids = [i.id for i in attacks_of(engine, "hero")]
    assert ids[0] == "longsword"
    assert ids[-3:] == ["unarmed", "improvised", "improvised_thrown"]
    assert "unarmed" not in ids[:-3]


def test_improvised_melee_is_a_melee_attack_without_a_weapon(registry, cfg):
    info = info_of(duel(registry, cfg, ScriptedRng()), "improvised")
    assert info.kind == "melee"
    assert info.weapon_id is None


def test_improvised_bonus_has_no_proficiency(registry, cfg):
    assert info_of(duel(registry, cfg, ScriptedRng()), "improvised").bonus == 3


def test_improvised_damage_is_d4_plus_strength_bludgeoning(registry, cfg):
    info = info_of(duel(registry, cfg, ScriptedRng()), "improvised")
    assert info.dice == "1d4"
    assert info.damage_bonus == 3
    assert info.damage_type == "bludgeoning"


def test_thrown_is_a_ranged_attack_with_range_20_60(registry, cfg):
    info = info_of(duel(registry, cfg, ScriptedRng()), "improvised_thrown")
    assert info.kind == "ranged"
    assert info.range_normal_ft == 20
    assert info.range_long_ft == 60
    assert info.weapon_id is None


def test_thrown_bonus_and_damage_match_the_melee_variant(registry, cfg):
    info = info_of(duel(registry, cfg, ScriptedRng()), "improvised_thrown")
    assert info.bonus == 3
    assert info.dice == "1d4"
    assert info.damage_bonus == 3
    assert info.damage_type == "bludgeoning"


# меню

def test_improvised_options_are_offered_in_the_same_zone(registry, cfg):
    ids = option_ids(duel(registry, cfg, ScriptedRng()), "hero")
    assert "attack:improvised:goblin_1" in ids
    assert "attack:improvised_thrown:goblin_1" in ids


def test_improvised_melee_has_a_nonlethal_variant(registry, cfg):
    ids = option_ids(duel(registry, cfg, ScriptedRng()), "hero")
    assert "attack:improvised:goblin_1:nonlethal" in ids


def test_thrown_has_no_nonlethal_variant(registry, cfg):
    ids = option_ids(duel(registry, cfg, ScriptedRng()), "hero")
    assert "attack:improvised_thrown:goblin_1:nonlethal" not in ids


def test_improvised_melee_is_not_offered_against_a_neighbour_zone(registry, cfg):
    ids = option_ids(duel(registry, cfg, ScriptedRng(), goblin_zone="door"), "hero")
    assert "attack:improvised:goblin_1" not in ids


def test_thrown_is_offered_against_a_neighbour_zone(registry, cfg):
    ids = option_ids(duel(registry, cfg, ScriptedRng(), goblin_zone="door"), "hero")
    assert "attack:improvised_thrown:goblin_1" in ids


def test_thrown_is_offered_across_one_zone(registry, cfg):
    # 2 шага = 60 фт = дальняя дистанция броска 20/60: вариант есть (с помехой)
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")], hero_zone="door",
    )
    assert "attack:improvised_thrown:goblin_1" in option_ids(engine, "hero")


# броски

def test_improvised_hit_deals_d4_plus_strength(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[12], d4=[2]))
    engine.perform("hero", "attack:improvised:goblin_1")
    assert hp(engine, "goblin_1") == 5


def test_improvised_attack_does_not_add_proficiency(registry, cfg):
    # 11 + 3 = 14 < КД 15 (с мастерством было бы 16)
    engine = duel(registry, cfg, ScriptedRng(d20=[11]))
    engine.perform("hero", "attack:improvised:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_improvised_crit_doubles_the_die_only(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[20], d4=[2, 2]))
    engine.perform("hero", "attack:improvised:goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_improvised_attack_keeps_the_weapon_in_hand(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[12], d4=[2]))
    engine.perform("hero", "attack:improvised:goblin_1")
    assert engine.heroes["hero"].equipped.main_hand == "longsword"


def test_improvised_hit_does_not_trigger_weapon_mastery(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["longsword"]
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(d20=[12], d4=[2]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:improvised:goblin_1")
    assert creature(engine, "goblin_1").active_effects == []


def test_thrown_at_a_neighbour_zone_is_made_with_disadvantage(registry, cfg):
    # два d20: берётся меньший (3 + 3 = 6 -- промах)
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 3]), goblin_zone="door")
    engine.perform("hero", "attack:improvised_thrown:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_thrown_disadvantage_takes_the_lower_die(registry, cfg):
    # помеха: 14 и 13 -> 13 + 3 = 16 попадание
    engine = duel(registry, cfg, ScriptedRng(d20=[14, 13], d4=[1]), goblin_zone="door")
    engine.perform("hero", "attack:improvised_thrown:goblin_1")
    assert hp(engine, "goblin_1") == 6


def test_thrown_in_the_enemy_zone_is_made_with_disadvantage(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 3]))
    engine.perform("hero", "attack:improvised_thrown:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_thrown_hit_deals_d4_plus_strength(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[16, 15], d4=[4]), goblin_zone="door")
    engine.perform("hero", "attack:improvised_thrown:goblin_1")
    assert hp(engine, "goblin_1") == 3


# регрессия: improvise() -- проверка навыка, как раньше

def test_improvise_skill_check_still_works(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.improvise(
        "hero", skill="athletics", category="medium", effect="prone", target="goblin_1"
    )
    assert [c.id for c in creature(engine, "goblin_1").conditions] == ["prone"]


# названия и слагаемые для строк броска

def test_improvised_names_and_parts(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    melee = info_of(engine, "improvised")
    thrown = info_of(engine, "improvised_thrown")
    assert melee.name == "импровизированное оружие"
    assert thrown.name == "бросок подручного предмета"
    for info in (melee, thrown):
        assert info.bonus_parts == [("Сил", 3)]
        assert info.damage_parts == [("Сил", 3)]


def test_unarmed_names_and_parts(registry, cfg):
    info = info_of(duel(registry, cfg, ScriptedRng()), "unarmed")
    assert info.name == "безоружный удар"
    assert info.bonus_parts == [("Сил", 3), ("мастерство", 2)]
    assert info.damage_parts == [("", 1), ("Сил", 3)]
