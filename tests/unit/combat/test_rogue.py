# Шаг К2, П3: бой плута (docs/plan-k2.md, решения 46-59; combat/sneak.py, actions/rogue.py).
#   * Скрытая атака: плут, фехтовальное или дальнобойное оружие, раз в ход; есть преимущество, либо
#     боеспособный союзник у цели и нет помехи; кости по таблице (1/2/3 ур. -> 1d6/2d6/3d6),
#     крит удваивает; бросок метательного, не фехтовального (метательное копьё) -- не даёт (Р43);
#   * Хитрое действие (2 ур.): dash_bonus / disengage_bonus / hide_bonus тратят бонусное действие;
#   * Верный прицел (3 ур.): без перемещения в этот ход, следующая атака с преимуществом,
#     скорость 0;
#   * Хитрый удар (5 ур.): выбор эффекта следующей Скрытой атаки (кость меньше), эффект -- после
#     урона (Р44), цель крупнее Large при «Сбить с ног» -- строка в логе, кость цела (Р45);
#   * Невероятное уклонение (5 ур.): реакцией урон попавшей атаки вдвое (округление вниз);
#   * авто-герой: Верный прицел при враге в своей зоне, Всплеск действий после end_turn тактики.
from combat_kit import (
    ScriptedRng,
    creature,
    custom_registry,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.combat import sneak
from ai_dm.combat.actions import rogue
from ai_dm.combat.controllers import AutoHeroController
from ai_dm.devtools.grid_heroes import build_hero
from ai_dm.rules.inventory import add_item
from ai_dm.rules.progression import sync_resources
from ai_dm.state.combat import ZoneFeature
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

HIT = 15
GOBLIN = "goblin_1"
ATTACK = f"attack:shortsword:{GOBLIN}"


def rogue_hero(registry, level=1, weapon="shortsword"):
    # Лов 17 (+3), Сил 8: атака +5 (+6 с 5 ур.), КД гоблина 15 -- d20 15 попадает
    hero = build_hero("rogue", level, registry)
    hero.sheet.abilities["dex"] = 17
    hero.sheet.abilities["str"] = 8
    # Savage Attacker бросает урон дважды, а тесты задают грани один раз (как make_fighter)
    hero.sheet.feats = [f for f in hero.sheet.feats if f != "savage_attacker"]
    # мастерства (Vex: преимущество следующей атаки) сбили бы счёт d20
    hero.sheet.weapon_masteries = []
    give_weapon(hero, registry, weapon)
    return hero


def duel(
    registry, cfg, hero, rng=None, ally=False, goblin_zone="hall", hero_zone="hall", zones=None,
    reg=None, monster="goblin_warrior",
):
    # ally -- союзник героя в зоне гоблина; у гоблина 40 HP
    monsters = [mon(GOBLIN, monster, goblin_zone)]
    if ally:
        monsters.append(mon("ally", "goblin_warrior", goblin_zone, side="heroes", group="allies"))
    engine = make_engine(
        reg or registry, cfg, heroes=[(hero, hero_zone)], rng=rng, monsters=monsters, zones=zones,
    )
    creature(engine, GOBLIN).hp_max = 40
    set_hp(engine, GOBLIN, 40)
    return engine


def log_text(engine):
    return "\n".join(engine.state.log)


def effect_ids(engine, ref="hero"):
    return [e.id for e in creature(engine, ref).active_effects]


def line_index(engine, part_of_line):
    lines = engine.state.log
    return [i for i, line in enumerate(lines) if part_of_line in line][0]


def modifier(effect_id, mode):
    return ActiveEffect(
        id=effect_id, source="hero", kind="modifier",
        params={"target": "attack_roll", "mode": mode, "consume": True},
        expires=Expiry(kind="end_of_turn", value=0, owner="hero"),
    )


# --- Скрытая атака ---

def test_sneak_attack_with_an_ally_at_the_target_adds_the_dice(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4])
    engine = duel(registry, cfg, rogue_hero(registry), rng, ally=True)
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (2 + 3) - 4


def test_sneak_attack_is_in_the_log(registry, cfg):
    engine = duel(
        registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT], d6=[2, 4]), ally=True,
    )
    engine.perform("hero", ATTACK)
    assert "Скрытая атака +1d6" in log_text(engine)


def test_no_sneak_attack_without_an_ally_or_advantage(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT], d6=[2]))
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (2 + 3)
    assert "Скрытая атака" not in log_text(engine)


def test_no_sneak_attack_when_the_ally_is_down(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT], d6=[2]), ally=True)
    set_hp(engine, "ally", 0)
    engine.perform("hero", ATTACK)
    assert "Скрытая атака" not in log_text(engine)


def test_ally_in_another_zone_does_not_give_a_sneak_attack(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT], d6=[2]), ally=True)
    part(engine, "ally").zone_id = "door"
    engine.perform("hero", ATTACK)
    assert "Скрытая атака" not in log_text(engine)


def test_sneak_attack_with_advantage_and_no_ally(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 2], d6=[2, 4])
    engine = duel(registry, cfg, rogue_hero(registry), rng)
    creature(engine, "hero").active_effects.append(modifier("help", "advantage"))
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (2 + 3) - 4


def test_no_sneak_attack_with_disadvantage_even_with_an_ally(registry, cfg):
    rng = ScriptedRng(d20=[HIT, HIT], d6=[2])
    engine = duel(registry, cfg, rogue_hero(registry), rng, ally=True)
    creature(engine, "hero").active_effects.append(modifier("help", "disadvantage"))
    engine.perform("hero", ATTACK)
    assert "Скрытая атака" not in log_text(engine)


def test_sneak_attack_once_per_turn(registry, cfg):
    rng = ScriptedRng(d20=[HIT, HIT], d6=[2, 4, 3])
    engine = duel(registry, cfg, rogue_hero(registry), rng, ally=True)
    engine.perform("hero", ATTACK)
    turn(engine, "hero").action = True
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (2 + 3 + 4) - (3 + 3)


def test_sneak_attack_is_available_again_in_the_next_turn(registry, cfg):
    rng = ScriptedRng(d20=[HIT, HIT], d6=[2, 4, 3, 5])
    engine = duel(registry, cfg, rogue_hero(registry), rng, ally=True)
    engine.perform("hero", ATTACK)
    engine.start_turn(GOBLIN)
    turn(engine, "hero").action = True
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (2 + 3 + 4) - (3 + 3 + 5)


def test_sneak_flag_is_cleared_by_any_start_of_turn(registry, cfg):
    engine = duel(
        registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT], d6=[2, 4]), ally=True,
    )
    engine.perform("hero", ATTACK)
    assert sneak.USED in effect_ids(engine)
    engine.start_turn(GOBLIN)
    assert sneak.USED not in effect_ids(engine)


def test_critical_hit_doubles_the_sneak_dice(registry, cfg):
    rng = ScriptedRng(d20=[20], d6=[1, 1, 3, 3])
    engine = duel(registry, cfg, rogue_hero(registry), rng, ally=True)
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40 - (1 + 1 + 3) - (3 + 3)


def test_level_3_sneak_attack_is_two_dice(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = duel(registry, cfg, rogue_hero(registry, 3), rng, ally=True)
    engine.perform("hero", ATTACK)
    assert "Скрытая атака +2d6" in log_text(engine)
    assert hp(engine, GOBLIN) == 40 - (2 + 3) - (4 + 5)


def test_level_5_sneak_attack_is_three_dice(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5, 6])
    engine = duel(registry, cfg, rogue_hero(registry, 5), rng, ally=True)
    engine.perform("hero", ATTACK)
    assert "Скрытая атака +3d6" in log_text(engine)
    assert hp(engine, GOBLIN) == 40 - (2 + 3) - (4 + 5 + 6)


def test_no_sneak_attack_for_a_non_rogue(registry, cfg):
    engine = duel(registry, cfg, make_fighter(registry), ScriptedRng(d20=[HIT], d8=[2]), ally=True)
    engine.perform("hero", f"attack:longsword:{GOBLIN}")
    assert "Скрытая атака" not in log_text(engine)


def test_no_sneak_attack_for_unarmed(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry), ScriptedRng(d20=[HIT]), ally=True)
    engine.perform("hero", f"attack:unarmed:{GOBLIN}")
    assert "Скрытая атака" not in log_text(engine)


def test_no_sneak_attack_with_a_non_finesse_melee_weapon(registry, cfg):
    hero = rogue_hero(registry, weapon="longsword")
    engine = duel(registry, cfg, hero, ScriptedRng(d20=[HIT], d8=[4]), ally=True)
    engine.perform("hero", f"attack:longsword:{GOBLIN}")
    assert "Скрытая атака" not in log_text(engine)


def test_sneak_attack_with_a_finesse_dagger(registry, cfg):
    hero = rogue_hero(registry, weapon="dagger")
    engine = duel(registry, cfg, hero, ScriptedRng(d20=[HIT], d4=[2], d6=[4]), ally=True)
    engine.perform("hero", f"attack:dagger:{GOBLIN}")
    assert "Скрытая атака +1d6" in log_text(engine)


def ranged_duel(registry, cfg, weapon, rng):
    # гоблин и его союзник в соседней зоне: дальнобойная атака без помехи
    hero = rogue_hero(registry, weapon=weapon)
    return duel(registry, cfg, hero, rng, ally=True, goblin_zone="door")


def test_sneak_attack_with_a_bow(registry, cfg):
    engine = ranged_duel(registry, cfg, "shortbow", ScriptedRng(d20=[HIT], d6=[2, 4]))
    engine.perform("hero", f"attack:shortbow:{GOBLIN}")
    assert "Скрытая атака +1d6" in log_text(engine)


def test_sneak_attack_with_a_pistol(registry, cfg):
    engine = ranged_duel(registry, cfg, "pistol", ScriptedRng(d20=[HIT], d10=[5], d6=[4]))
    engine.perform("hero", f"attack:pistol:{GOBLIN}")
    assert "Скрытая атака +1d6" in log_text(engine)


def test_thrown_dagger_gives_a_sneak_attack(registry, cfg):
    # бросок кинжала в соседнюю зону идёт с помехой по дальности; преимущество гасит её, и союзник
    # у цели даёт Скрытую атаку (кинжал фехтовальный)
    engine = ranged_duel(registry, cfg, "dagger", ScriptedRng(d20=[HIT, HIT], d4=[2], d6=[4]))
    creature(engine, "hero").active_effects.append(modifier("help", "advantage"))
    engine.perform("hero", f"attack:dagger_thrown:{GOBLIN}")
    assert "Скрытая атака +1d6" in log_text(engine)


def test_thrown_javelin_gives_no_sneak_attack(registry, cfg):
    engine = ranged_duel(registry, cfg, "javelin", ScriptedRng(d20=[HIT], d6=[2]))
    engine.perform("hero", f"attack:javelin_thrown:{GOBLIN}")
    assert "Скрытая атака" not in log_text(engine)
    assert hp(engine, GOBLIN) < 40


# --- Хитрое действие ---

def test_cunning_action_options_for_a_level_2_rogue(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    assert {"dash_bonus", "disengage_bonus"} <= set(option_ids(engine, "hero"))


def test_cunning_action_labels(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    labels = {o.id: o.label for o in engine.available_actions("hero")}
    assert labels["dash_bonus"] == "Хитрое действие: Рывок"
    assert labels["disengage_bonus"] == "Хитрое действие: Отход"


def test_level_1_rogue_has_no_cunning_action(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 1))
    assert not {"dash_bonus", "disengage_bonus", "hide_bonus"} & set(option_ids(engine, "hero"))


def test_no_cunning_action_when_the_bonus_is_spent(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    turn(engine, "hero").bonus = False
    assert "dash_bonus" not in option_ids(engine, "hero")


def test_non_rogue_has_no_cunning_action(registry, cfg):
    engine = duel(registry, cfg, make_fighter(registry))
    assert "dash_bonus" not in option_ids(engine, "hero")


def test_bonus_dash_spends_the_bonus_action_and_keeps_the_action(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    engine.perform("hero", "dash_bonus")
    state = turn(engine, "hero")
    assert (state.bonus, state.action, state.move) == (False, True, 2)


def test_bonus_disengage_spends_the_bonus_action_and_keeps_the_action(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    engine.perform("hero", "disengage_bonus")
    state = turn(engine, "hero")
    assert (state.bonus, state.action, state.disengaged) == (False, True, True)


def hiding_duel(registry, cfg, rng=None):
    # герой у двери с укрытием, гоблин на балконе
    zones = make_zones(door=[ZoneFeature(kind="cover_half")])
    return duel(
        registry, cfg, rogue_hero(registry, 2), rng, goblin_zone="balcony", hero_zone="door",
        zones=zones,
    )


def test_hide_bonus_is_offered_with_cover_and_labelled(registry, cfg):
    engine = hiding_duel(registry, cfg)
    option = [o for o in engine.available_actions("hero") if o.id == "hide_bonus"][0]
    assert (option.label, option.cost) == ("Хитрое действие: Спрятаться", "bonus")


def test_hide_bonus_is_absent_without_cover(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2), goblin_zone="balcony")
    assert "hide_bonus" not in option_ids(engine, "hero")


def test_hide_bonus_spends_the_bonus_and_keeps_the_action(registry, cfg):
    engine = hiding_duel(registry, cfg, ScriptedRng(d20=[15]))
    engine.perform("hero", "hide_bonus")
    state = turn(engine, "hero")
    assert (state.bonus, state.action) == (False, True)


def test_plain_hide_stays_a_separate_action_option(registry, cfg):
    engine = hiding_duel(registry, cfg)
    assert {"hide", "hide_bonus"} <= set(option_ids(engine, "hero"))


def test_plain_hide_still_spends_the_action(registry, cfg):
    engine = hiding_duel(registry, cfg, ScriptedRng(d20=[15]))
    engine.perform("hero", "hide")
    state = turn(engine, "hero")
    assert (state.action, state.bonus) == (False, True)


# --- Верный прицел ---

def test_steady_aim_is_offered_to_a_level_3_rogue_who_stood_still(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3))
    option = [o for o in engine.available_actions("hero") if o.id == "steady_aim"][0]
    assert (option.label, option.cost) == ("Верный прицел", "bonus")


def test_level_2_rogue_has_no_steady_aim(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    assert "steady_aim" not in option_ids(engine, "hero")


def test_steady_aim_zeroes_the_move_and_spends_the_bonus(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), hero_zone="door", goblin_zone="hall")
    engine.perform("hero", "steady_aim")
    state = turn(engine, "hero")
    assert (state.move, state.bonus) == (0, False)
    assert not [i for i in option_ids(engine, "hero") if i.startswith("move:")]


def test_steady_aim_is_gone_after_use(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3))
    engine.perform("hero", "steady_aim")
    turn(engine, "hero").bonus = True
    assert "steady_aim" not in option_ids(engine, "hero")


def test_steady_aim_gives_advantage_and_a_sneak_attack_without_an_ally(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 2], d6=[2, 3, 4])
    engine = duel(registry, cfg, rogue_hero(registry, 3), rng)
    engine.perform("hero", "steady_aim")
    engine.perform("hero", ATTACK)
    assert "Скрытая атака +2d6" in log_text(engine)
    assert hp(engine, GOBLIN) == 40 - (2 + 3) - (3 + 4)


def test_steady_aim_is_named_in_the_attack_log(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), ScriptedRng(d20=[HIT, 2], d6=[2, 3, 4]))
    engine.perform("hero", "steady_aim")
    engine.perform("hero", ATTACK)
    assert "верный прицел" in log_text(engine)


def test_steady_aim_advantage_is_spent_by_the_attack(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 2, HIT], d6=[2, 3, 4, 5])
    engine = duel(registry, cfg, rogue_hero(registry, 3), rng)
    engine.perform("hero", "steady_aim")
    engine.perform("hero", ATTACK)
    turn(engine, "hero").action = True
    engine.perform("hero", ATTACK)
    assert rng.left("d20") == 0


def test_no_steady_aim_after_a_move(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), hero_zone="door", goblin_zone="hall")
    engine.perform("hero", "move:hall")
    assert "steady_aim" not in option_ids(engine, "hero")


def test_no_steady_aim_after_a_dash(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3))
    engine.perform("hero", "dash")
    assert "steady_aim" not in option_ids(engine, "hero")


def test_only_steady_aim_heroes_remember_moves(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2), hero_zone="door", goblin_zone="hall")
    engine.perform("hero", "move:hall")
    assert rogue.MOVED not in effect_ids(engine)


def test_move_is_remembered_for_steady_aim_heroes(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), hero_zone="door", goblin_zone="hall")
    engine.perform("hero", "move:hall")
    assert rogue.MOVED in effect_ids(engine)


# --- Хитрый удар ---

def strike_duel(registry, cfg, rng, ally=True, level=5, **kwargs):
    return duel(registry, cfg, rogue_hero(registry, level), rng, ally=ally, **kwargs)


def strike_ids(engine):
    return [i for i in option_ids(engine, "hero") if i.startswith("cunning_strike:")]


def test_cunning_strike_options_without_a_poisoners_kit(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng())
    assert strike_ids(engine) == ["cunning_strike:trip", "cunning_strike:withdraw"]


def test_cunning_strike_labels(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng())
    labels = [o.label for o in engine.available_actions("hero") if o.kind == "cunning_strike"]
    assert labels == ["Сбить с ног", "Отступить"]


def test_poison_effect_needs_a_poisoners_kit(registry, cfg):
    hero = rogue_hero(registry, 5)
    add_item(hero, "poisoners_kit", cost_cp=0)
    engine = duel(registry, cfg, hero)
    assert "cunning_strike:poison" in strike_ids(engine)


def test_level_4_rogue_has_no_cunning_strike(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng(), level=4)
    assert strike_ids(engine) == []


def test_cunning_strike_choice_is_free_and_leaves_the_actions(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng())
    engine.perform("hero", "cunning_strike:trip")
    state = turn(engine, "hero")
    assert (state.action, state.bonus) == (True, True)


def test_cunning_strike_choice_is_replaced_by_the_next_one(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng())
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", "cunning_strike:withdraw")
    flags = [e for e in creature(engine, "hero").active_effects if e.id == rogue.STRIKE]
    assert [f.params["effect"] for f in flags] == ["withdraw"]


def test_cunning_strike_flag_is_cleared_at_the_end_of_the_turn(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng())
    engine.perform("hero", "cunning_strike:trip")
    engine.expire("end_of_turn", "hero")
    assert rogue.STRIKE not in effect_ids(engine)


def test_cunning_strike_flag_survives_an_attack_without_a_sneak_attack(registry, cfg):
    engine = strike_duel(registry, cfg, ScriptedRng(d20=[HIT], d6=[2]), ally=False)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert rogue.STRIKE in effect_ids(engine)
    assert "СЛ" not in log_text(engine)


def test_trip_costs_one_die_and_the_target_falls_on_a_failed_save(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 3], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert "Скрытая атака +2d6" in log_text(engine)
    assert "prone" in [c.id for c in creature(engine, GOBLIN).conditions]


def test_trip_log_has_the_dc_8_plus_dex_plus_proficiency(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 3], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert "Хитрый удар (Сбить с ног): СЛ 14" in log_text(engine)


def test_trip_with_a_passed_save_leaves_the_target_standing(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 19], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert "prone" not in [c.id for c in creature(engine, GOBLIN).conditions]


def test_cunning_strike_effect_comes_after_the_damage_lines_not_before_the_sneak_line(
    registry, cfg
):
    rng = ScriptedRng(d20=[HIT, 3], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert line_index(engine, "Скрытая атака") < line_index(engine, "Хитрый удар (Сбить с ног)")
    assert line_index(engine, "Урон") < line_index(engine, "Хитрый удар (Сбить с ног)")


def test_cunning_strike_flag_is_spent_with_the_sneak_attack(registry, cfg):
    rng = ScriptedRng(d20=[HIT, 19], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert rogue.STRIKE not in effect_ids(engine)
    assert rogue.PENDING not in effect_ids(engine)


def test_no_cunning_strike_options_after_the_sneak_attack(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5, 6])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", ATTACK)
    assert strike_ids(engine) == []


def test_trip_on_a_killed_target_has_no_effect_and_no_save(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    set_hp(engine, GOBLIN, 1)
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert "Хитрый удар (Сбить с ног)" not in log_text(engine)
    assert "prone" not in [c.id for c in creature(engine, GOBLIN).conditions]


def test_trip_on_a_target_immune_to_the_damage_has_no_effect(registry, cfg):
    reg = custom_registry(registry, immune_gob={"damage_immunities": ["piercing"]})
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng, reg=reg, monster="immune_gob")
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) == 40
    assert "Хитрый удар (Сбить с ног)" not in log_text(engine)


def test_trip_on_a_huge_target_explains_and_spends_no_die(registry, cfg):
    reg = custom_registry(registry, huge_gob={"size": "huge"})
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5, 6])
    engine = strike_duel(registry, cfg, rng, reg=reg, monster="huge_gob")
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    text = log_text(engine)
    assert "Хитрый удар (Сбить с ног): цель слишком велика, кость не потрачена" in text
    assert "Скрытая атака +3d6" in text
    assert "СЛ" not in text


def test_trip_on_a_large_target_still_works(registry, cfg):
    reg = custom_registry(registry, large_gob={"size": "large"})
    rng = ScriptedRng(d20=[HIT, 3], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng, reg=reg, monster="large_gob")
    engine.perform("hero", "cunning_strike:trip")
    engine.perform("hero", ATTACK)
    assert "prone" in [c.id for c in creature(engine, GOBLIN).conditions]


def test_withdraw_lets_the_rogue_move_without_provoking(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    engine.perform("hero", "cunning_strike:withdraw")
    assert turn(engine, "hero").disengaged is False
    engine.perform("hero", ATTACK)
    assert turn(engine, "hero").disengaged is True


def test_withdraw_works_on_a_finished_target(registry, cfg):
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng)
    set_hp(engine, GOBLIN, 1)
    engine.perform("hero", "cunning_strike:withdraw")
    engine.perform("hero", ATTACK)
    assert hp(engine, GOBLIN) <= 0
    assert turn(engine, "hero").disengaged is True


def test_withdraw_does_nothing_when_the_damage_is_zero(registry, cfg):
    reg = custom_registry(registry, immune_gob={"damage_immunities": ["piercing"]})
    rng = ScriptedRng(d20=[HIT], d6=[2, 4, 5])
    engine = strike_duel(registry, cfg, rng, reg=reg, monster="immune_gob")
    engine.perform("hero", "cunning_strike:withdraw")
    engine.perform("hero", ATTACK)
    assert turn(engine, "hero").disengaged is False


def test_poison_makes_the_target_poisoned_on_a_failed_save(registry, cfg):
    hero = rogue_hero(registry, 5)
    add_item(hero, "poisoners_kit", cost_cp=0)
    rng = ScriptedRng(d20=[HIT, 1], d6=[2, 4, 5])
    engine = duel(registry, cfg, hero, rng, ally=True)
    engine.perform("hero", "cunning_strike:poison")
    engine.perform("hero", ATTACK)
    assert "poisoned" in [c.id for c in creature(engine, GOBLIN).conditions]


# --- Невероятное уклонение ---

def attacked_rogue(registry, cfg, rng, level=5):
    # гоблин бьёт плута; d6 = 5 -> урон скимитара 5 + 2 = 7
    engine = duel(registry, cfg, rogue_hero(registry, level), rng)
    set_hp(engine, "hero", 30)
    return engine


def goblin_attack(engine):
    turn(engine, GOBLIN).action = True
    return engine.perform(GOBLIN, "attack:скимитар:hero")


def test_uncanny_dodge_halves_an_odd_damage_rounding_down(registry, cfg):
    engine = attacked_rogue(registry, cfg, ScriptedRng(d20=[HIT], d6=[5]))
    goblin_attack(engine)
    assert hp(engine, "hero") == 30 - 3


def test_uncanny_dodge_spends_the_reaction_and_is_logged(registry, cfg):
    engine = attacked_rogue(registry, cfg, ScriptedRng(d20=[HIT], d6=[5]))
    goblin_attack(engine)
    assert turn(engine, "hero").reaction is False
    assert "Невероятное уклонение: 7 → 3" in log_text(engine)


def test_second_hit_in_the_round_is_not_halved(registry, cfg):
    engine = attacked_rogue(registry, cfg, ScriptedRng(d20=[HIT, HIT], d6=[5, 5]))
    goblin_attack(engine)
    goblin_attack(engine)
    assert hp(engine, "hero") == 30 - 3 - 7


def test_level_4_rogue_takes_full_damage(registry, cfg):
    engine = attacked_rogue(registry, cfg, ScriptedRng(d20=[HIT], d6=[5]), level=4)
    goblin_attack(engine)
    assert hp(engine, "hero") == 30 - 7


def test_uncanny_dodge_halves_the_total_damage_value(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5))
    assert rogue.uncanny_dodge(engine, "hero", 10) == 5


def test_uncanny_dodge_ignores_zero_damage(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5))
    assert rogue.uncanny_dodge(engine, "hero", 0) == 0
    assert turn(engine, "hero").reaction is True


def test_uncanny_dodge_does_not_work_blinded(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5))
    creature(engine, "hero").conditions.append(AppliedCondition(id="blinded", source="x"))
    assert rogue.uncanny_dodge(engine, "hero", 10) == 10


def test_uncanny_dodge_does_not_work_incapacitated(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5))
    creature(engine, "hero").conditions.append(AppliedCondition(id="incapacitated", source="x"))
    assert rogue.uncanny_dodge(engine, "hero", 10) == 10


def test_uncanny_dodge_needs_the_reaction(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5))
    turn(engine, "hero").reaction = False
    assert rogue.uncanny_dodge(engine, "hero", 10) == 10


def test_uncanny_dodge_is_for_heroes_with_the_feature_only(registry, cfg):
    engine = duel(registry, cfg, make_fighter(registry))
    assert rogue.uncanny_dodge(engine, "hero", 10) == 10
    assert rogue.uncanny_dodge(engine, GOBLIN, 10) == 10


# --- авто-герой ---

def auto_choice(engine):
    return AutoHeroController(engine).choose_turn(engine.available_actions("hero"), "hero")


def fighter_level_2(registry):
    hero = make_fighter(registry)
    hero.sheet.primary.level = 2
    sync_resources(hero, registry)
    return hero


def test_auto_rogue_uses_steady_aim_with_an_enemy_in_its_zone(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3))
    assert auto_choice(engine) == "steady_aim"


def test_auto_rogue_does_not_aim_when_the_enemy_is_in_another_zone(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), goblin_zone="door")
    assert auto_choice(engine) != "steady_aim"


def test_auto_rogue_aims_only_once(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 3), ScriptedRng(d20=[HIT, 2], d6=[2, 3, 4]))
    engine.perform("hero", "steady_aim")
    assert auto_choice(engine) == ATTACK


def test_auto_rogue_without_steady_aim_attacks(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 2))
    assert auto_choice(engine) == ATTACK


def test_auto_rogue_does_not_pick_cunning_strike(registry, cfg):
    engine = duel(registry, cfg, rogue_hero(registry, 5), ally=True)
    assert not auto_choice(engine).startswith("cunning_strike")


def test_auto_fighter_uses_the_surge_when_nothing_else_is_left(registry, cfg):
    engine = duel(registry, cfg, fighter_level_2(registry))
    turn(engine, "hero").action = False
    assert auto_choice(engine) == "action_surge"


def test_auto_fighter_attacks_before_the_surge(registry, cfg):
    engine = duel(registry, cfg, fighter_level_2(registry))
    assert auto_choice(engine).startswith("attack:")


def test_auto_fighter_does_not_surge_without_enemies(registry, cfg):
    engine = duel(registry, cfg, fighter_level_2(registry))
    turn(engine, "hero").action = False
    part(engine, GOBLIN).status = "dead"
    assert auto_choice(engine) != "action_surge"
