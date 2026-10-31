# Шаг К2, П2: бросок метательного оружия (docs/plan-k2.md, решения 2, 16, 17; combat/thrown.py).
#   * оружие со свойством thrown (кинжал, копьё, метательное копьё...) даёт у героя второй вариант
#     атаки attack:<оружие>_thrown:<цель> (mode "ranged", подпись «Бросок: ...»); в зоне цели
#     (дальность 10 фт) вариант в соседней зоне -- нормальный/с помехой по дальности оружия;
#     ближний вариант attack:<оружие>:<цель> при цели в другой зоне недоступен;
#   * бросок тратит один экземпляр: count_item -1, брошенное падает в зону цели (ground_items,
#     owner_ref -- бросивший); стек кончился -- рука пуста;
#   * в своей зоне бросок идёт с помехой («враг рядом»);
#   * мастерство оружия (Sap и др.) срабатывает и при броске;
#   * победа: своё брошенное -- «<герой>: подобрал <оружие>», чужое -- «достаётся»; бегство --
#     «остался на поле боя»; в бою брошенное поднимается как выбитое (pickup).
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    make_engine,
    make_fighter,
    make_line,
    mon,
    move_to,
    option_ids,
    set_hp,
    turn,
)

from ai_dm.combat.actions.attack import attacks_of, base_advantage
from ai_dm.combat.end import settle_ground
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.state.combat import GroundItem

THROW = "attack:dagger_thrown:goblin_1"


def thrower(
    registry, cfg, rng=None, count=2, weapon="dagger", hero_zone="door", goblin_zone="hall"
):
    hero = make_fighter(registry)
    give_weapon(hero, registry, weapon)
    if count > 1:
        add_item(hero, weapon, count - 1, cost_cp=0)
    engine = make_engine(
        registry, cfg, heroes=[(hero, hero_zone)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )
    return engine, hero


def throw_info(engine, weapon):
    return [i for i in attacks_of(engine, "hero") if i.id == f"{weapon}_thrown"][0]


def throw_mode(engine, weapon):
    return base_advantage(engine, "hero", "goblin_1", throw_info(engine, weapon))


# --- варианты ---

def test_thrown_weapon_in_the_next_zone_is_offered_as_a_throw(registry, cfg):
    engine, _ = thrower(registry, cfg)
    assert THROW in option_ids(engine, "hero")


def test_the_throw_is_a_ranged_attack(registry, cfg):
    engine, _ = thrower(registry, cfg)
    option = [o for o in engine.available_actions("hero") if o.id == THROW][0]
    assert option.params["mode"] == "ranged"


def test_the_throw_label_says_throw(registry, cfg):
    engine, _ = thrower(registry, cfg)
    option = [o for o in engine.available_actions("hero") if o.id == THROW][0]
    assert option.label.startswith("Бросок: кинжал")


def test_melee_variant_of_the_same_weapon_is_not_offered_at_range(registry, cfg):
    engine, _ = thrower(registry, cfg)
    assert "attack:dagger:goblin_1" not in option_ids(engine, "hero")


def test_in_the_target_zone_both_the_blow_and_the_throw_are_offered(registry, cfg):
    engine, _ = thrower(registry, cfg, hero_zone="hall")
    assert {"attack:dagger:goblin_1", THROW} <= set(option_ids(engine, "hero"))


def test_weapon_without_the_thrown_property_has_no_throw(registry, cfg):
    engine, _ = thrower(registry, cfg, count=1, weapon="shortsword", hero_zone="hall")
    assert "attack:shortsword_thrown:goblin_1" not in option_ids(engine, "hero")


# --- дальность ---

def test_throw_in_the_own_zone_is_at_disadvantage(registry, cfg):
    engine, _ = thrower(registry, cfg, hero_zone="hall")
    assert throw_mode(engine, "dagger") == "disadvantage"


def test_javelin_from_the_next_zone_is_a_normal_throw(registry, cfg):
    engine, _ = thrower(registry, cfg, count=1, weapon="javelin")
    assert throw_mode(engine, "javelin") == "normal"


def test_javelin_from_two_zones_away_is_at_disadvantage(registry, cfg):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "javelin")
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert throw_mode(engine, "javelin") == "disadvantage"


def test_dagger_from_beyond_the_long_range_is_not_offered(registry, cfg):
    # кинжал 20/60: три зоны -- 120 фт
    hero = make_fighter(registry)
    give_weapon(hero, registry, "dagger")
    engine = make_engine(
        registry, cfg, heroes=[(hero, "z0")], rng=ScriptedRng(), zones=make_line(4),
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert "attack:dagger_thrown:goblin_1" not in option_ids(engine, "hero")


# --- расход и падение ---

def test_throw_spends_one_copy(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    assert count_item(hero, "dagger") == 1


def test_the_remaining_copy_stays_in_hand(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    assert hero.equipped.main_hand == "dagger"


def test_thrown_weapon_lies_in_the_target_zone(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    ground = [(g.item_id, g.zone_id, g.owner_ref) for g in engine.state.ground_items]
    assert ground == [("dagger", "hall", "hero")]


def test_a_miss_drops_the_weapon_too(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[1, 1]))
    engine.perform("hero", THROW)
    assert (count_item(hero, "dagger"), len(engine.state.ground_items)) == (1, 1)


def test_the_last_copy_empties_the_hand(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[15] * 4, d4=[1, 1]))
    engine.perform("hero", THROW)
    turn(engine, "hero").action = True
    engine.perform("hero", THROW)
    assert (hero.equipped.main_hand, count_item(hero, "dagger")) == (None, 0)


def test_throw_deals_weapon_damage(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    # кинжал 1d4 + Сил 3 = 5 из 10
    assert creature(engine, "goblin_1").hp_current == 5


def test_throw_spends_the_action(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    assert turn(engine, "hero").action is False


# --- мастерство ---

def test_sap_works_on_a_thrown_spear(registry, cfg):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "spear")
    hero.sheet.weapon_masteries = ["spear"]
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], rng=ScriptedRng(d20=[18, 18], d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:spear_thrown:goblin_1")
    assert [e.id for e in creature(engine, "goblin_1").active_effects] == ["sap"]


def test_mastery_not_chosen_does_not_work_on_a_throw(registry, cfg):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "spear")
    hero.sheet.weapon_masteries = []
    engine = make_engine(
        registry, cfg, heroes=[(hero, "door")], rng=ScriptedRng(d20=[18, 18], d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "attack:spear_thrown:goblin_1")
    assert creature(engine, "goblin_1").active_effects == []


# --- подбор ---

def test_victory_returns_the_thrown_weapon_with_a_line(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[4]))
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", THROW)
    assert engine.state.outcome == "victory"
    assert count_item(hero, "dagger") == 2
    assert "Арн: подобрал кинжал" in engine.state.log


def test_victory_keeps_the_line_for_a_foreign_weapon_as_before(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[4]))
    set_hp(engine, "goblin_1", 1)
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=0)
    )
    engine.perform("hero", THROW)
    assert any("скимитар: достаётся Арн" in line for line in engine.state.log)


def test_flight_leaves_the_thrown_weapon_on_the_field(registry, cfg):
    engine, hero = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    engine.state.outcome = "fled"
    settle_ground(engine)
    assert count_item(hero, "dagger") == 1
    assert any("остался на поле боя" in line for line in engine.state.log)
    assert engine.state.ground_items == []


def pickups(engine):
    return [o for o in engine.available_actions("hero") if o.kind == "pickup"]


def test_pickup_in_the_target_zone_is_a_free_interaction(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    move_to(engine, "hero", "hall")
    option = pickups(engine)[0]
    assert (option.id, option.cost) == ("pickup:0", "free")


def test_pickup_costs_the_action_when_the_interaction_is_spent(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    move_to(engine, "hero", "hall")
    turn(engine, "hero").action = True
    turn(engine, "hero").free_interaction = False
    assert pickups(engine)[0].cost == "action"


def test_pickup_in_another_zone_is_not_offered(registry, cfg):
    engine, _ = thrower(registry, cfg, ScriptedRng(d20=[15, 15], d4=[2]))
    engine.perform("hero", THROW)
    assert pickups(engine) == []
