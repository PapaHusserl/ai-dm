# Атака (шаг 17, ТЗ 7): ближняя и дальняя, дальности, помеха, крит, монстры.
#   Вариант атаки героя: attack:<оружие в main_hand>:<цель>[:nonlethal]; монстра:
#   attack:<имя действия нижним регистром, пробелы -> "_">:<цель>.
#   Цели -- участники другой стороны со status "active" или "down" (лежачего можно добить),
#   но не "dead" и не "fled".
#   Ближнее оружие (melee): цель только в своей зоне. Дальнее (ranged, range_normal/long_ft):
#     полоса до цели по таблице ТЗ 7 (та же зона 10 фт, соседняя 30, через одну 60, дальше 120):
#     полоса <= range_normal -- без штрафа; <= range_long -- помеха ("дальняя дистанция");
#     дальше -- варианта нет. Помеха и при боеспособном враге в зоне стреляющего (в т.ч. не цели).
#   Бонус атаки героя: derived.attack_bonus; урон: кубики оружия + derived.damage_bonus;
#   у монстра -- attack_bonus и damage_dice действия (с бонусом "1d6+2");
#   advantage_damage_dice монстра добавляется, если бросок атаки был с преимуществом.
#   Крит (натуральная 20 или автокрит) удваивает кубики. Движок ставит запросу tags["melee"]
#   (лежащая цель: преимущество вблизи, помеха издали).
#   Событие attack {attacker, target, weapon, mode, outcome, damage}; в state.log -- строка броска.
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_line,
    mon,
    move_to,
    option_ids,
    part,
    set_hp,
)

from ai_dm.combat.actions.attack import attack_targets
from ai_dm.rules.results import Rejected
from ai_dm.state.creature import ActiveEffect, AppliedCondition


def duel(registry, cfg, rng=None, hero=None, hero_zone="hall", goblin_zone="hall"):
    return make_engine(
        registry, cfg, heroes=[(hero or make_fighter(registry), hero_zone)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def attack_events(events):
    return [e for e in events if e.type == "attack"]


# ближний бой героя

def test_melee_hit_deals_weapon_damage_plus_modifier(registry, cfg):
    # 10 + 5 = 15 против КД 15; урон 5 + 3
    engine = duel(registry, cfg, ScriptedRng(d20=[10], d8=[5]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 2


def test_melee_miss_deals_nothing_and_rolls_no_damage(registry, cfg):
    rng = ScriptedRng(d20=[9], d8=[5])
    engine = duel(registry, cfg, rng)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert rng.left("d8") == 1


def test_attack_event_describes_the_blow(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10], d8=[5]))
    events = attack_events(engine.perform("hero", "attack:longsword:goblin_1"))
    assert [e.data for e in events] == [
        {"attacker": "hero", "target": "goblin_1", "weapon": "longsword", "mode": "melee",
         "outcome": "hit", "damage": 8}
    ]


def test_miss_event_has_zero_damage(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[3]))
    events = attack_events(engine.perform("hero", "attack:longsword:goblin_1"))
    assert events[0].data["outcome"] == "miss"
    assert events[0].data["damage"] == 0


def test_natural_20_doubles_the_dice(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[20], d8=[4, 6]))
    set_hp(engine, "goblin_1", 30)
    events = attack_events(engine.perform("hero", "attack:longsword:goblin_1"))
    assert events[0].data["outcome"] == "crit"
    assert hp(engine, "goblin_1") == 17


def test_natural_1_always_misses(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[1]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_attack_roll_is_written_to_the_combat_log(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[10], d8=[5]))
    engine.perform("hero", "attack:longsword:goblin_1")
    expected = "Атака (длинный меч): d20 (10) + 3 Сил + 2 мастерство = 15 против КД 15"
    assert any(expected in line for line in engine.state.log)


def test_melee_targets_only_the_own_zone(registry, cfg):
    engine = duel(registry, cfg, goblin_zone="balcony")
    options = engine.available_actions("hero")
    assert not [o for o in options if o.kind == "attack" and o.params["mode"] == "melee"]


def test_melee_option_exists_for_enemy_in_the_zone(registry, cfg):
    engine = duel(registry, cfg)
    assert "attack:longsword:goblin_1" in option_ids(engine, "hero")


def test_melee_attack_on_far_enemy_is_rejected(registry, cfg):
    engine = duel(registry, cfg, goblin_zone="balcony")
    assert isinstance(engine.perform("hero", "attack:longsword:goblin_1"), Rejected)


def test_dead_enemy_is_not_a_target(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = "dead"
    assert "attack:longsword:goblin_1" not in option_ids(engine, "hero")


def test_downed_enemy_can_still_be_attacked(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = "down"
    set_hp(engine, "goblin_1", 0)
    assert "attack:longsword:goblin_1" in option_ids(engine, "hero")


def test_allies_are_not_targets(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert "attack:longsword:ally" not in option_ids(engine, "hero")


def test_melee_attack_on_prone_target_has_advantage(registry, cfg):
    # 3 и 18: берётся 18; без преимущества 3 + 5 = 8 -- промах
    engine = duel(registry, cfg, ScriptedRng(d20=[3, 18], d8=[4]))
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="prone"))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3


# дальний бой героя

def archer(registry):
    hero = make_fighter(registry)
    give_weapon(hero, registry, "shortbow")
    return hero


def test_ranged_attack_on_neighbour_zone_has_no_penalty(registry, cfg):
    # шортбоу: +3 (ЛОВ 1 + мастерство 2); 30 фт < 80 фт -- обычная дистанция
    rng = ScriptedRng(d20=[12], d6=[4])
    engine = duel(registry, cfg, rng, hero=archer(registry), goblin_zone="balcony")
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 10 - (4 + 1)


def test_ranged_attack_beyond_normal_range_has_disadvantage(registry, cfg):
    # через две зоны (3 шага): 120 фт > 80 фт, но < 320 фт -- дальняя дистанция, помеха: берётся 2
    engine = make_engine(
        registry, cfg, heroes=[(archer(registry), "z0")], rng=ScriptedRng(d20=[18, 2]),
        monsters=[mon("goblin_1", "goblin_warrior", "z3")], zones=make_line(4),
    )
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_ranged_attack_across_one_zone_has_no_disadvantage(registry, cfg):
    # через одну зону (2 шага): 60 фт < 80 фт -- обычная дистанция, второй d20 не бросается
    rng = ScriptedRng(d20=[18], d6=[4])
    engine = duel(
        registry, cfg, rng, hero=archer(registry), hero_zone="door", goblin_zone="balcony",
    )
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 10 - (4 + 1)


def test_ranged_attack_in_range_hits_with_the_same_roll_that_missed_at_long_range(registry, cfg):
    engine = duel(
        registry, cfg, ScriptedRng(d20=[18], d6=[4]), hero=archer(registry),
        hero_zone="hall", goblin_zone="balcony",
    )
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") < 10


def test_ranged_attack_with_enemy_in_own_zone_has_disadvantage(registry, cfg):
    hero = archer(registry)
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=ScriptedRng(d20=[18, 2]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "attack:shortbow:goblin_2")
    assert hp(engine, "goblin_2") == 10


def test_downed_enemy_in_own_zone_does_not_give_disadvantage(registry, cfg):
    hero = archer(registry)
    rng = ScriptedRng(d20=[18], d6=[4])
    engine = make_engine(
        registry, cfg, heroes=[(hero, "hall")], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "balcony")],
    )
    part(engine, "goblin_1").status = "down"
    set_hp(engine, "goblin_1", 0)
    engine.perform("hero", "attack:shortbow:goblin_2")
    assert rng.left("d20") == 0


def test_ranged_attack_on_enemy_in_own_zone_is_allowed(registry, cfg):
    engine = duel(registry, cfg, hero=archer(registry))
    assert "attack:shortbow:goblin_1" in option_ids(engine, "hero")


def test_ranged_attack_on_prone_target_has_disadvantage(registry, cfg):
    engine = duel(
        registry, cfg, ScriptedRng(d20=[18, 2]), hero=archer(registry), goblin_zone="balcony"
    )
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="prone"))
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_hero_without_weapon_has_only_unarmed_and_improvised_attacks(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    hero.inventory = [e for e in hero.inventory if not registry.has("weapon", e.item_id)]
    engine = duel(registry, cfg, hero=hero)
    weapons = {"unarmed", "improvised", "improvised_thrown"}
    attacks = [i for i in option_ids(engine, "hero") if i.startswith("attack:")]
    assert attacks
    assert {i.split(":")[1] for i in attacks} <= weapons


def test_hero_attacks_with_inventory_weapon_and_it_becomes_main_hand(registry, cfg):
    hero = make_fighter(registry)
    hero.equipped.main_hand = None
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[3]), hero=hero)
    weapon = "longsword"
    assert any(i.startswith("attack:") for i in option_ids(engine, "hero"))
    engine.perform("hero", f"attack:{weapon}:goblin_1")
    assert hero.equipped.main_hand == weapon


# монстры

def test_monster_melee_hit(registry, cfg):
    # +4 против КД 19: 15 + 4 = 19; урон 1d6 + 2
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert hp(engine, "hero") == 7


def test_monster_melee_miss(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[14]))
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert hp(engine, "hero") == 12


def test_monster_ranged_attack_uses_its_own_ranges(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3]), goblin_zone="balcony")
    engine.perform("goblin_1", "attack:короткий_лук:hero")
    assert hp(engine, "hero") == 7


def test_monster_melee_action_needs_the_same_zone(registry, cfg):
    engine = duel(registry, cfg, goblin_zone="balcony")
    ids = option_ids(engine, "goblin_1")
    assert "attack:скимитар:hero" not in ids
    assert "attack:короткий_лук:hero" in ids


def test_advantage_damage_dice_are_added_with_advantage(registry, cfg):
    # лежащий герой: у гоблина вблизи преимущество; 1d6 + 2 и ещё 1d4
    engine = duel(registry, cfg, ScriptedRng(d20=[3, 16], d6=[2], d4=[3]))
    engine.heroes["hero"].creature.conditions.append(AppliedCondition(id="prone"))
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert hp(engine, "hero") == 12 - (2 + 2 + 3)


def test_advantage_damage_dice_are_not_added_without_advantage(registry, cfg):
    rng = ScriptedRng(d20=[16], d6=[2], d4=[3])
    engine = duel(registry, cfg, rng)
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert rng.left("d4") == 1
    assert hp(engine, "hero") == 12 - 4


def test_guard_has_only_melee_options(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("guard_1", "guard", "hall")],
    )
    ids = [i for i in option_ids(engine, "guard_1") if i.startswith("attack:")]
    assert ids == ["attack:копьё:hero"]


def test_moved_enemy_is_targetable_in_its_new_zone(registry, cfg):
    engine = duel(registry, cfg, goblin_zone="balcony")
    move_to(engine, "goblin_1", "hall")
    assert "attack:longsword:goblin_1" in option_ids(engine, "hero")


# --- шаг 19: поссорившийся бьёт союзников (метка quarreling) ---

def pair(registry, cfg, other_group="goblins"):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall", group=other_group)],
    )


def quarrel_flag(engine, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="quarreling", source="hero", kind="flag")
    )


def test_attack_targets_of_a_monster_are_the_heroes(registry, cfg):
    assert attack_targets(pair(registry, cfg), "goblin_1") == ["hero"]


def test_attack_targets_of_a_quarreling_monster_are_its_mates(registry, cfg):
    engine = pair(registry, cfg)
    quarrel_flag(engine)
    assert attack_targets(engine, "goblin_1") == ["goblin_2"]


def test_attack_targets_of_a_quarreling_monster_take_another_group_without_mates(registry, cfg):
    engine = pair(registry, cfg, other_group="raiders")
    quarrel_flag(engine)
    assert attack_targets(engine, "goblin_1") == ["goblin_2"]


def test_attack_targets_of_a_quarreling_monster_skip_a_downed_hero(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    down_hero(engine, "hero")
    quarrel_flag(engine)
    assert attack_targets(engine, "goblin_1") == []


def test_attack_targets_of_a_calm_monster_still_include_a_downed_hero(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    down_hero(engine, "hero")
    assert attack_targets(engine, "goblin_1") == ["hero"]


def test_the_flag_changes_only_the_targets_of_its_owner(registry, cfg):
    engine = pair(registry, cfg)
    quarrel_flag(engine)
    assert attack_targets(engine, "goblin_2") == ["hero"]


def test_the_flag_does_not_change_the_hero_targets(registry, cfg):
    engine = pair(registry, cfg)
    quarrel_flag(engine)
    assert attack_targets(engine, "hero") == ["goblin_1", "goblin_2"]


def test_quarreling_monster_gets_attack_options_against_mates_only(registry, cfg):
    engine = pair(registry, cfg)
    quarrel_flag(engine)
    ids = [i for i in option_ids(engine, "goblin_1") if i.startswith("attack:")]
    assert ids and all(i.endswith(":goblin_2") for i in ids)
