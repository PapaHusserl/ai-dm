# Безоружный удар (docs/plan-combat-extras.md, разд. 1; BACKLOG 7). Ожидаемый API:
#   attacks_of(engine, герой) -- в конце всегда AttackInfo(id="unarmed", kind="melee",
#       weapon_id=None, bonus = СИЛ + БМ, урон фиксированный 1 + СИЛ дробящий, без кубиков);
#       у героя без оружия -- единственная атака
#   опция attack:unarmed:<цель> (+ :nonlethal) -- как у любого ближнего оружия
#   урон не ниже 0; крит кость не удваивает (костей нет); equip и мастерство не трогаются
# Герой -- воин (СИЛ +3, БМ +2): бонус +5, урон 1+3 = 4. Гоблин: КД 15, 10 HP.
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
)

from ai_dm.combat.actions.attack import attacks_of


def duel(registry, cfg, rng, hero=None, goblin_zone="hall"):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def bare_hero(registry):
    hero = make_fighter(registry)
    hero.inventory = []
    hero.equipped.main_hand = None
    return hero


def unarmed(engine):
    return [i for i in attacks_of(engine, "hero") if i.id == "unarmed"][0]


# attacks_of

def test_unarmed_follows_the_weapons_of_an_armed_hero(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    ids = [i.id for i in attacks_of(engine, "hero")]
    assert ids[0] == "longsword"
    assert ids[-3:] == ["unarmed", "improvised", "improvised_thrown"]


def test_hero_without_weapons_starts_with_the_unarmed_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), hero=bare_hero(registry))
    assert [i.id for i in attacks_of(engine, "hero")][0] == "unarmed"


def test_unarmed_attack_is_melee_without_a_weapon(registry, cfg):
    info = unarmed(duel(registry, cfg, ScriptedRng()))
    assert info.kind == "melee"
    assert info.weapon_id is None


def test_unarmed_bonus_is_strength_plus_proficiency(registry, cfg):
    assert unarmed(duel(registry, cfg, ScriptedRng())).bonus == 5


def test_unarmed_damage_is_one_plus_strength_bludgeoning(registry, cfg):
    info = unarmed(duel(registry, cfg, ScriptedRng()))
    assert info.damage_bonus == 4
    assert info.damage_type == "bludgeoning"


def test_monsters_get_no_unarmed_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert "unarmed" not in [i.id for i in attacks_of(engine, "goblin_1")]


# меню

def test_unarmed_option_is_offered_against_a_near_enemy(registry, cfg):
    assert "attack:unarmed:goblin_1" in option_ids(duel(registry, cfg, ScriptedRng()), "hero")


def test_unarmed_option_is_not_offered_against_a_far_enemy(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(), goblin_zone="balcony")
    assert "attack:unarmed:goblin_1" not in option_ids(engine, "hero")


def test_unarmed_nonlethal_variant_is_offered(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    assert "attack:unarmed:goblin_1:nonlethal" in option_ids(engine, "hero")


def test_unarmed_option_label_names_the_blow(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng())
    option = next(o for o in engine.available_actions("hero") if o.id == "attack:unarmed:goblin_1")
    assert "безоружный удар" in option.label


# бросок

def test_unarmed_hit_deals_fixed_damage_without_dice(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 6


def test_unarmed_attack_hits_exactly_at_armor_class(registry, cfg):
    # 10 + 5 = 15 = КД; 9 + 5 = 14 -- промах
    engine = duel(registry, cfg, ScriptedRng(d20=[9]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_unarmed_crit_does_not_double_the_fixed_damage(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[20]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 6


def test_unarmed_damage_is_not_negative_with_weak_strength(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.abilities["str"] = 8
    engine = duel(registry, cfg, ScriptedRng(d20=[14]), hero=hero)
    assert unarmed(engine).damage_bonus == 0
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_unarmed_damage_with_weak_strength_never_heals(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.abilities["str"] = 1
    engine = duel(registry, cfg, ScriptedRng(d20=[20]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_unarmed_attack_spends_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert part(engine, "hero").turn.action is False


# оружие в руке и мастерство

def test_unarmed_attack_keeps_the_weapon_in_hand(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert engine.heroes["hero"].equipped.main_hand == "longsword"


def test_unarmed_attack_of_a_bare_hero_equips_nothing(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]), hero=bare_hero(registry))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert engine.heroes["hero"].equipped.main_hand is None


def test_unarmed_hit_does_not_trigger_the_mastery_of_the_weapon_in_hand(registry, cfg):
    # меч в руке с мастерством (Sap); безоружный удар его не включает
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["longsword"]
    engine = duel(registry, cfg, ScriptedRng(d20=[10]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert creature(engine, "goblin_1").active_effects == []


def test_unarmed_miss_does_not_graze(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.weapon_masteries = ["longsword"]
    engine = duel(registry, cfg, ScriptedRng(d20=[2]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert hp(engine, "goblin_1") == 10


# оглушающая

def test_nonlethal_unarmed_blow_knocks_the_monster_out(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    creature(engine, "goblin_1").hp_current = 3
    events = engine.perform("hero", "attack:unarmed:goblin_1:nonlethal")
    assert hp(engine, "goblin_1") == 0
    assert part(engine, "goblin_1").status == "down"
    assert "monster_died" not in [e.type for e in events]


def test_lethal_unarmed_blow_kills_the_monster(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    creature(engine, "goblin_1").hp_current = 3
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert part(engine, "goblin_1").status == "dead"


# боевые стили и черты оружия не добавляются

def test_unarmed_damage_ignores_the_weapon_bonuses_of_the_hero(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.feats = hero.sheet.feats + ["archery"]
    engine = duel(registry, cfg, ScriptedRng(), hero=hero)
    assert unarmed(engine).bonus == 5
    assert unarmed(engine).damage_bonus == 4


# строка лога урона без костей

def test_unarmed_damage_line_shows_the_sum(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert "  Урон (безоружный удар): 1 + 3 Сил = 4 дробящий" in engine.state.log


def test_unarmed_damage_line_shows_a_negative_modifier_and_zero(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.abilities["str"] = 8
    engine = duel(registry, cfg, ScriptedRng(d20=[14]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert "  Урон (безоружный удар): 1 - 1 Сил = 0 дробящий" in engine.state.log


def test_unarmed_damage_line_shows_a_zero_modifier_with_plus(registry, cfg):
    hero = make_fighter(registry)
    hero.sheet.abilities["str"] = 10
    engine = duel(registry, cfg, ScriptedRng(d20=[13]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert "  Урон (безоружный удар): 1 + 0 Сил = 1 дробящий" in engine.state.log


def test_unarmed_attack_line_names_the_proficiency(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10]))
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert any("+ 2 мастерство" in line for line in engine.state.log)
