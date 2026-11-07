# К3 П4 (docs/plan-k3.md, «Тесты» П4; решения 29, 68, 69): призывы и аура жреца в бою
#   (combat/summons.py, combat/aura.py).
#   Призыв (Духовное оружие жреца, Пылающий шар волшебника): каст -- ActiveEffect(kind="summon",
#     params zone/spell/dice) на заклинателе, срок -- концентрация; цель каста -- своя или
#     соседняя зона. Ход сотворения: бонусное потрачено, пунктов призыва нет. Следующий ход,
#     бонусным действием:
#       summon_attack:<заклинание>:<цель> -- «<Призыв>: удар → <цель>», враг в зоне призыва или
#         соседней;
#         Духовное оружие -- бросок атаки заклинанием, 1d8 + Мдр силовым; Пылающий шар -- спасбросок
#         Лов, 2d6 огнём, половина при успехе;
#       summon_move:<заклинание>:<зона> -- «<Призыв>: переместить → <зона>», соседняя зона призыва.
#     Концентрация кончилась -- пунктов нет.
#   Аура (Духовные стражи): ActiveEffect(kind="aura") на заклинателе; враг, заканчивающий ход в зоне
#     заклинателя (SRD 5.2.1, решение 71), -- спасбросок Мдр, 3d8 излучением, половина при успехе;
#     союзник и враг в другой зоне -- нет; жрец ушёл из зоны -- стражи с ним; концентрация
#     кончилась -- урона нет.
#   Жрец 3 ур.: Мдр +2, СЛ 12, бонус атаки заклинанием +4; волшебник 1 ур.: СЛ 13.
from combat_kit import (
    ScriptedRng,
    creature,
    hp,
    make_cleric,
    make_engine,
    make_fighter,
    make_line,
    make_wizard,
    mon,
    move_to,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.creatures import end_concentration
from ai_dm.state.creature import ActiveEffect, ResourcePool

GOBLIN = [mon("goblin_1", "goblin_warrior", "hall")]
WEAPON = "spiritual_weapon"
SPHERE = "flaming_sphere"
GUARDIANS = "spirit_guardians"


def priest(registry, *spells):
    hero = make_cleric(registry, level=3)
    hero.sheet.prepared_of().extend(spells)
    return hero


# гоблин на балконе: в зале (зона жреца) пусто, поэтому «Духовное оружие → зал» остаётся целью-зоной
# (решение 72: зона с врагом — не цель-зона), а враг в соседней зоне виден удару призыва
NEAR_GOBLIN = [mon("goblin_1", "goblin_warrior", "balcony")]


def engine_of(registry, cfg, hero, monsters=NEAR_GOBLIN, rng=None, extra=(), **kwargs):
    engine = make_engine(
        registry, cfg, heroes=[hero, *extra], monsters=monsters, rng=rng or ScriptedRng(), **kwargs
    )
    for spec in monsters:
        set_hp(engine, spec["ref"], 30)
    return engine


def summons_of(engine, ref="cler"):
    return [e for e in creature(engine, ref).active_effects if e.kind == "summon"]


def summon_ids(engine, ref="cler"):
    return [i for i in option_ids(engine, ref) if i.startswith("summon_")]


def cast_weapon(registry, cfg, zone="hall", **kwargs):
    # жрец с Духовным оружием, оружие уже стоит в зоне zone; бонусное действие нового хода
    engine = engine_of(registry, cfg, priest(registry, WEAPON), **kwargs)
    engine.perform("cler", f"cast:{WEAPON}:2:{zone}")
    engine.start_turn("cler")
    return engine


# каст призыва

def test_spiritual_weapon_is_cast_into_every_zone_in_reach(registry, cfg):
    # зона с врагом -- не цель-зона: у врага своя строка (решение 72); пустые зоны остаются
    engine = engine_of(registry, cfg, priest(registry, WEAPON), monsters=GOBLIN)
    ids = [i for i in option_ids(engine, "cler") if i.startswith(f"cast:{WEAPON}:2:")]
    assert ids == [f"cast:{WEAPON}:2:{z}" for z in ("door", "balcony", "goblin_1")]


def test_summon_zone_is_limited_to_own_and_adjacent_zones(registry, cfg):
    engine = engine_of(
        registry, cfg, priest(registry, WEAPON), zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    ids = [i for i in option_ids(engine, "cler") if i.startswith(f"cast:{WEAPON}:2:")]
    assert ids == [f"cast:{WEAPON}:2:z0", f"cast:{WEAPON}:2:z1"]


def test_casting_the_weapon_puts_a_summon_effect_in_the_zone(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:2:door")
    (effect,) = summons_of(engine)
    assert (effect.id, effect.params["zone"], effect.params["spell"]) == (WEAPON, "door", WEAPON)


def test_summon_effect_lasts_while_concentration_lasts(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    (effect,) = summons_of(engine)
    assert (effect.expires.kind, effect.expires.owner) == ("concentration", "cler")


def test_casting_the_weapon_holds_concentration_and_spends_a_slot(registry, cfg):
    hero = priest(registry, WEAPON)
    engine = engine_of(registry, cfg, hero)
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    assert engine.creature("cler").concentration.spell_id == WEAPON
    assert hero.creature.resources["spell_slot:2"].current == 2


def test_casting_the_weapon_costs_the_bonus_action_not_the_action(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    assert (turn(engine, "cler").bonus, turn(engine, "cler").action) == (False, True)


def test_casting_the_weapon_writes_the_log_line(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    assert "Отец Марк: Духовное оружие — Центр зала" in engine.state.log


def test_upcast_weapon_gets_an_extra_d8(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:3:hall")
    assert summons_of(engine)[0].params["dice"] == "2d8"


def test_no_summon_options_on_the_turn_of_casting(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    assert summon_ids(engine) == []


def test_no_summon_options_without_a_summon(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    assert summon_ids(engine) == []


# пункты призыва

def test_weapon_strike_is_offered_against_an_enemy_in_the_next_zone(registry, cfg):
    # оружие в зале, гоблин на балконе (соседняя зона)
    engine = cast_weapon(registry, cfg)
    assert f"summon_attack:{WEAPON}:goblin_1" in summon_ids(engine)


def test_weapon_strike_label_names_the_summon_and_the_target(registry, cfg):
    engine = cast_weapon(registry, cfg)
    option = [o for o in engine.available_actions("cler") if o.kind == "summon_attack"][0]
    assert option.label == f"Духовное оружие: удар → {engine.name('goblin_1')}"


def test_weapon_strike_costs_the_bonus_action(registry, cfg):
    engine = cast_weapon(registry, cfg)
    option = [o for o in engine.available_actions("cler") if o.kind == "summon_attack"][0]
    assert option.cost == "bonus"


def test_weapon_strike_reaches_an_enemy_next_to_the_summon_zone(registry, cfg):
    # жрец в z0, оружие в z1, враг в z2: соседняя с оружием зона
    engine = cast_weapon(
        registry, cfg, zone="z1", zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z2")],
    )
    assert f"summon_attack:{WEAPON}:goblin_1" in summon_ids(engine)


def test_weapon_strike_does_not_reach_an_enemy_two_zones_from_the_summon(registry, cfg):
    # враг рядом с жрецом (z1), но оружие улетело в z3
    engine = cast_weapon(
        registry, cfg, zone="z1", zones=make_line(5), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert f"summon_attack:{WEAPON}:goblin_1" not in summon_ids(engine)


def test_weapon_strike_is_not_offered_against_a_dead_enemy(registry, cfg):
    engine = cast_weapon(registry, cfg)
    part(engine, "goblin_1").status = "dead"
    assert [i for i in summon_ids(engine) if i.startswith("summon_attack")] == []


def test_weapon_strike_is_not_offered_without_the_bonus_action(registry, cfg):
    engine = cast_weapon(registry, cfg)
    turn(engine, "cler").bonus = False
    assert summon_ids(engine) == []


def test_summon_move_is_offered_to_adjacent_zones_of_the_summon(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    moves = [i for i in summon_ids(engine) if i.startswith("summon_move")]
    assert moves == [f"summon_move:{WEAPON}:door", f"summon_move:{WEAPON}:balcony"]


def test_summon_move_label_names_the_summon_and_the_zone(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    labels = [o.label for o in engine.available_actions("cler") if o.kind == "summon_move"]
    assert labels == [
        "Духовное оружие: переместить → У двери", "Духовное оружие: переместить → Балкон",
    ]


def test_no_summon_options_after_concentration_ends(registry, cfg):
    engine = cast_weapon(registry, cfg)
    end_concentration(engine.creature("cler"))
    engine.drop_concentration_effects("cler")
    assert summon_ids(engine) == []


def test_new_concentration_spell_removes_the_summon(registry, cfg):
    hero = priest(registry, WEAPON, "bless")
    engine = engine_of(registry, cfg, hero)
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    engine.start_turn("cler")
    engine.perform("cler", "cast:bless:1:cler")
    assert summons_of(engine) == []


# удар Духовного оружия

def test_weapon_hit_deals_d8_plus_wisdom_force_damage(registry, cfg):
    # бросок 15 + 4 = 19 против КД 15; 1d8 = 5, +2 Мдр
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[15], d8=[5]))
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 7


def test_weapon_miss_deals_no_damage(registry, cfg):
    # 5 + 4 = 9 < 15
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[5]))
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_weapon_miss_returns_a_miss_event(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[5]))
    events = engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert events[0].data["outcome"] == "miss"


def test_weapon_hit_returns_a_hit_event_with_the_damage(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[15], d8=[5]))
    events = engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert events[0].data == {
        "attacker": "cler", "target": "goblin_1", "weapon": WEAPON, "mode": "spell",
        "outcome": "hit", "damage": 7,
    }


def test_weapon_critical_hit_doubles_the_dice_but_not_the_modifier(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[20], d8=[5, 3]))
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - (5 + 3 + 2)


def test_upcast_weapon_hits_with_two_dice(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[5, 6])
    engine = engine_of(registry, cfg, priest(registry, WEAPON), rng=rng)
    engine.perform("cler", f"cast:{WEAPON}:3:hall")
    engine.start_turn("cler")
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - (5 + 6 + 2)


def test_weapon_strike_spends_the_bonus_action_only(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[5]))
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert (turn(engine, "cler").bonus, turn(engine, "cler").action) == (False, True)


def test_weapon_strike_keeps_the_summon_and_the_slot(registry, cfg):
    hero = priest(registry, WEAPON)
    engine = engine_of(registry, cfg, hero, rng=ScriptedRng(d20=[5]))
    engine.perform("cler", f"cast:{WEAPON}:2:hall")
    engine.start_turn("cler")
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert (len(summons_of(engine)), hero.creature.resources["spell_slot:2"].current) == (1, 2)


# перемещение

def test_summon_move_changes_the_summon_zone(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    engine.perform("cler", f"summon_move:{WEAPON}:balcony")
    assert summons_of(engine)[0].params["zone"] == "balcony"


def test_summon_move_spends_the_bonus_action(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    engine.perform("cler", f"summon_move:{WEAPON}:balcony")
    assert turn(engine, "cler").bonus is False


def test_summon_move_does_not_move_the_cleric(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    engine.perform("cler", f"summon_move:{WEAPON}:balcony")
    assert part(engine, "cler").zone_id == "hall"


def test_summon_move_writes_the_log_line(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    engine.perform("cler", f"summon_move:{WEAPON}:balcony")
    assert "Отец Марк: Духовное оружие — Балкон" in engine.state.log


def test_after_the_move_strikes_reach_targets_near_the_new_zone(registry, cfg):
    engine = cast_weapon(
        registry, cfg, zone="z0", zones=make_line(5), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z2")],
    )
    engine.perform("cler", f"summon_move:{WEAPON}:z1")
    engine.start_turn("cler")
    assert f"summon_attack:{WEAPON}:goblin_1" in summon_ids(engine)


# Пылающий шар

def sphere_engine(registry, cfg, rng):
    hero = make_wizard(registry)
    hero.sheet.prepared_of().append(SPHERE)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=3, max=3)
    engine = engine_of(registry, cfg, hero, rng=rng)
    engine.perform("wiz", f"cast:{SPHERE}:2:hall")
    engine.start_turn("wiz")
    return engine


def test_flaming_sphere_failed_save_deals_full_fire_damage(registry, cfg):
    # Лов гоблина 15 (+2): 5 + 2 = 7 < СЛ 13; 2d6 = 3 + 4
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[3, 4]))
    engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 7


def test_flaming_sphere_passed_save_halves_the_damage(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[18], d6=[3, 4]))
    engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 3


def test_flaming_sphere_has_no_attack_roll_and_no_modifier(registry, cfg):
    # в очереди d20 одна грань -- на спасбросок цели; второй бросок (атака) дал бы AssertionError
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[1, 1]))
    events = engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert (events[0].data["outcome"], events[0].data["damage"]) == ("auto", 2)


def test_flaming_sphere_strike_label_uses_the_spell_name(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng())
    option = [o for o in engine.available_actions("wiz") if o.kind == "summon_attack"][0]
    assert option.label == f"Пылающий шар: удар → {engine.name('goblin_1')}"


# Духовные стражи

def guardians(registry, cfg, monsters=GOBLIN, rng=None, extra=()):
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=monsters, rng=rng, extra=extra
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    return engine


def end_turn(engine, ref):
    # ход участника целиком: начало, «закончить ход» (контроллер без сценария), конец хода --
    # стражи бьют в конце хода врага в зоне (SRD 5.2.1)
    engine.state.turn_index = engine.state.initiative_order.index(ref)
    engine.controllers[ref] = ScriptedController([])
    return engine.step()


def test_spirit_guardians_puts_an_aura_effect_on_the_caster(registry, cfg):
    engine = guardians(registry, cfg)
    (effect,) = [e for e in creature(engine, "cler").active_effects if e.kind == "aura"]
    assert (effect.params["dice"], effect.params["ability"], effect.params["damage_type"]) == (
        "3d8", "wis", "radiant",
    )


def test_spirit_guardians_hold_concentration_and_use_a_slot(registry, cfg):
    engine = guardians(registry, cfg)
    assert engine.creature("cler").concentration.spell_id == GUARDIANS
    assert engine.heroes["cler"].creature.resources["spell_slot:3"].current == 1


def test_spirit_guardians_write_the_log_line(registry, cfg):
    engine = guardians(registry, cfg)
    assert "Отец Марк: Духовные стражи" in engine.state.log


def test_enemy_ending_its_turn_in_the_zone_takes_the_aura_damage(registry, cfg):
    # Мдр гоблина 8 (-1): 5 - 1 < СЛ 12; 3d8 = 4 + 5 + 6
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[4, 5, 6]))
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 15


def test_aura_passed_save_halves_the_damage(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[18], d8=[4, 5, 6]))
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 7


def test_aura_writes_the_log_lines(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[4, 5, 6]))
    end_turn(engine, "goblin_1")
    assert f"{engine.name('goblin_1')} в зоне: Духовные стражи" in engine.state.log


def test_aura_returns_an_attack_event_for_the_caster(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[4, 5, 6]))
    events = end_turn(engine, "goblin_1")
    assert [e.data for e in events if e.type == "attack"] == [{
        "attacker": "cler", "target": "goblin_1", "weapon": GUARDIANS, "mode": "spell",
        "outcome": "auto", "damage": 15,
    }]


def test_ally_ending_its_turn_in_the_zone_takes_nothing(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = guardians(registry, cfg, extra=[ally])
    end_turn(engine, "ally")
    assert hp(engine, "ally") == 12


def test_enemy_in_another_zone_takes_nothing(registry, cfg):
    engine = guardians(registry, cfg)
    move_to(engine, "goblin_1", "balcony")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_aura_travels_with_the_cleric(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[4, 5, 6]))
    move_to(engine, "cler", "balcony")
    move_to(engine, "goblin_1", "balcony")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 15


def test_aura_does_not_stay_in_the_zone_the_cleric_left(registry, cfg):
    engine = guardians(registry, cfg)
    move_to(engine, "cler", "balcony")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_no_aura_damage_after_concentration_ends(registry, cfg):
    engine = guardians(registry, cfg)
    end_concentration(engine.creature("cler"))
    engine.drop_concentration_effects("cler")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30


def test_aura_does_not_hit_an_enemy_that_is_down(registry, cfg):
    engine = guardians(registry, cfg)
    set_hp(engine, "goblin_1", 0)
    part(engine, "goblin_1").status = "down"
    events = end_turn(engine, "goblin_1")
    assert [e for e in events if e.type == "attack"] == []


def test_aura_damage_can_drop_the_enemy(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[8, 8, 8]))
    set_hp(engine, "goblin_1", 10)
    end_turn(engine, "goblin_1")
    assert part(engine, "goblin_1").status != "active"


def test_two_enemies_each_roll_their_own_save(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    engine = guardians(registry, cfg, monsters=monsters,
                       rng=ScriptedRng(d20=[5, 18], d8=[4, 5, 6, 1, 1, 1]))
    end_turn(engine, "goblin_1")
    end_turn(engine, "goblin_2")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (15, 29)


# Духовные стражи по SRD 5.2.1 (решение 71): вход, конец хода, раз в ход

def scripted_turn(engine, ref, *script):
    # ход участника целиком со сценарием контроллера (затем «закончить ход»)
    engine.state.turn_index = engine.state.initiative_order.index(ref)
    engine.controllers[ref] = ScriptedController(list(script))
    return engine.step()


FAIL_15 = {"d20": [5], "d8": [4, 5, 6]}


def test_casting_the_guardians_does_not_hit_an_enemy_in_the_zone(registry, cfg):
    # очередь пуста: любой бросок при касте дал бы AssertionError
    engine = guardians(registry, cfg)
    assert hp(engine, "goblin_1") == 30


def test_enemy_that_leaves_the_zone_on_its_own_turn_takes_nothing(registry, cfg):
    # жрец бьёт по возможности (d20 = 1: промах), аура при этом не срабатывает
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[1]))
    scripted_turn(engine, "goblin_1", "move:door")
    assert (part(engine, "goblin_1").zone_id, hp(engine, "goblin_1")) == ("door", 30)


def test_enemy_entering_the_zone_saves_at_once(registry, cfg):
    monsters = [mon("goblin_1", "goblin_warrior", "balcony")]
    engine = guardians(registry, cfg, monsters=monsters, rng=ScriptedRng(**FAIL_15))
    engine.state.turn_index = 1
    engine.controllers["goblin_1"] = ScriptedController(["move:hall"])
    engine.perform("goblin_1", "move:hall")
    assert hp(engine, "goblin_1") == 30 - 15


def test_enemy_entering_and_ending_its_turn_in_the_zone_saves_once(registry, cfg):
    # в очереди одна грань d20: второй спасбросок в конце хода дал бы AssertionError
    monsters = [mon("goblin_1", "goblin_warrior", "balcony")]
    engine = guardians(registry, cfg, monsters=monsters, rng=ScriptedRng(**FAIL_15))
    scripted_turn(engine, "goblin_1", "move:hall")
    assert hp(engine, "goblin_1") == 30 - 15


def test_enemy_is_hit_again_at_the_end_of_its_next_turn_in_the_zone(registry, cfg):
    monsters = [mon("goblin_1", "goblin_warrior", "balcony")]
    rng = ScriptedRng(d20=[5, 5], d8=[4, 5, 6, 1, 1, 1])
    engine = guardians(registry, cfg, monsters=monsters, rng=rng)
    scripted_turn(engine, "goblin_1", "move:hall")
    scripted_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 15 - 3


def test_aura_hit_flag_is_gone_at_the_start_of_the_enemy_turn(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(**FAIL_15))
    scripted_turn(engine, "goblin_1")
    engine.start_turn("goblin_1")
    flags = [e.id for e in creature(engine, "goblin_1").active_effects if e.kind == "flag"]
    assert flags == []


def test_cleric_entering_the_zone_hits_every_enemy_in_it(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    rng = ScriptedRng(d20=[5, 18], d8=[4, 5, 6, 1, 1, 1])
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=monsters, rng=rng, hero_zone="door"
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (15, 29)


def test_enemies_hit_by_the_cleric_entry_are_hit_again_at_the_end_of_their_turns(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    rng = ScriptedRng(d20=[5, 18, 5, 18], d8=[4, 5, 6, 1, 1, 1, 2, 2, 2, 2, 2, 2])
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=monsters, rng=rng, hero_zone="door"
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    # метка «раз в ход» снимается в конце любого хода (решение 74): сначала кончается ход жреца
    scripted_turn(engine, "cler")
    scripted_turn(engine, "goblin_1")
    scripted_turn(engine, "goblin_2")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (15 - 6, 29 - 3)


def test_dash_out_and_back_after_the_enemy_turn_hits_it_again(registry, cfg):
    # решение 74: урон в конце хода гоблина; в ход жреца Рывок туда-обратно -- второй бросок
    # (d20: спасбросок, промах по возможности при выходе, спасбросок при возвращении)
    rng = ScriptedRng(d20=[5, 1, 5], d8=[4, 5, 6, 1, 1, 1])
    engine = guardians(registry, cfg, rng=rng)
    scripted_turn(engine, "goblin_1")
    scripted_turn(engine, "cler", "dash", "move:door", "move:hall")
    assert hp(engine, "goblin_1") == 30 - 15 - 3


def test_marks_are_cleared_at_the_end_of_any_turn(registry, cfg):
    rng = ScriptedRng(**FAIL_15)
    engine = guardians(registry, cfg, rng=rng)
    scripted_turn(engine, "goblin_1")
    flags = [e.id for e in creature(engine, "goblin_1").active_effects if e.kind == "flag"]
    assert flags == []


def test_marks_of_another_creature_are_cleared_at_the_end_of_the_cleric_turn(registry, cfg):
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=GOBLIN,
        rng=ScriptedRng(**FAIL_15), hero_zone="door",
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    assert [e.kind for e in creature(engine, "goblin_1").active_effects] == ["flag"]
    scripted_turn(engine, "cler")
    assert creature(engine, "goblin_1").active_effects == []


def misty_cleric(registry):
    hero = priest(registry, GUARDIANS, "misty_step")
    return hero


def test_teleport_into_the_guardians_zone_is_an_entry(registry, cfg):
    # Туманный шаг (дописан жрецу в prepared): прыжок к гоблину под стражами -- спасбросок сразу
    engine = engine_of(
        registry, cfg, misty_cleric(registry), monsters=GOBLIN,
        rng=ScriptedRng(**FAIL_15), hero_zone="door",
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "cast:misty_step:2:hall")
    assert (part(engine, "cler").zone_id, hp(engine, "goblin_1")) == ("hall", 30 - 15)


def test_teleport_into_a_zone_without_enemies_hits_nobody(registry, cfg):
    monsters = [mon("goblin_1", "goblin_warrior", "balcony")]
    engine = engine_of(registry, cfg, misty_cleric(registry), monsters=monsters, hero_zone="door")
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "cast:misty_step:2:hall")
    assert hp(engine, "goblin_1") == 30


def test_cleric_entering_a_zone_without_enemies_hits_nobody(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, GUARDIANS), hero_zone="door")
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    assert hp(engine, "goblin_1") == 30


def test_ally_entering_the_zone_takes_nothing(registry, cfg):
    ally = (make_fighter(registry, "ally"), "balcony")
    engine = guardians(registry, cfg, extra=[ally])
    engine.perform("ally", "move:hall")
    assert hp(engine, "ally") == 12


def test_enemy_shoved_into_the_zone_saves_on_arrival(registry, cfg):
    # гоблин из зала толкает жреца на балкон, где стоит второй гоблин: тот бросает спасбросок
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "balcony"),
    ]
    rng = ScriptedRng(d20=[2, 5], d8=[4, 5, 6])
    engine = guardians(registry, cfg, monsters=monsters, rng=rng)
    engine.perform("goblin_1", "shove:cler:balcony")
    assert (part(engine, "cler").zone_id, hp(engine, "goblin_2")) == ("balcony", 30 - 15)


def test_enemy_left_behind_by_a_shoved_cleric_takes_nothing(registry, cfg):
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "balcony"),
    ]
    rng = ScriptedRng(d20=[2, 5], d8=[4, 5, 6])
    engine = guardians(registry, cfg, monsters=monsters, rng=rng)
    engine.perform("goblin_1", "shove:cler:balcony")
    assert hp(engine, "goblin_1") == 30


def test_enemy_pushed_out_of_the_zone_takes_no_aura_damage(registry, cfg):
    # Громовая волна (в списке жреца её нет -- добавлена в подготовленные): гоблин вылетает из
    # зоны жреца -- вышел, не вошёл; урон только от волны
    hero = priest(registry, GUARDIANS, "thunderwave")
    hero.creature.resources["spell_slot:1"] = ResourcePool(current=4, max=4)
    engine = engine_of(
        registry, cfg, hero, monsters=GOBLIN, rng=ScriptedRng(d20=[2], d8=[1, 1]),
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.state.turn_index = 0
    turn(engine, "cler").action = True
    engine.perform("cler", "cast:thunderwave:1:hall")
    assert (part(engine, "goblin_1").zone_id != "hall", hp(engine, "goblin_1")) == (True, 28)


def test_guardians_finishing_the_last_enemy_end_the_combat_without_extra_saves(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[8, 8, 8]))
    set_hp(engine, "goblin_1", 5)
    scripted_turn(engine, "goblin_1")
    log = engine.state.log
    after = log[[i for i, line in enumerate(log) if line.startswith("Бой окончен")][0] + 1:]
    assert engine.is_over and after == []


# Духовное оружие, каст по цели (решение 72)

def test_weapon_cast_menu_offers_the_enemy_as_a_target(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    assert f"cast:{WEAPON}:2:goblin_1" in option_ids(engine, "cler")


def test_weapon_cast_menu_has_no_zone_target_for_the_enemy_zone(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    assert f"cast:{WEAPON}:2:balcony" not in option_ids(engine, "cler")


def test_weapon_cast_menu_keeps_empty_zones(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    assert {f"cast:{WEAPON}:2:door", f"cast:{WEAPON}:2:hall"} <= set(option_ids(engine, "cler"))


def test_weapon_cast_menu_offers_an_enemy_two_zones_away_only_through_the_zone(registry, cfg):
    engine = engine_of(
        registry, cfg, priest(registry, WEAPON), zones=make_line(4), hero_zone="z0",
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )
    assert f"cast:{WEAPON}:2:goblin_1" not in option_ids(engine, "cler")


def cast_at_goblin(registry, cfg, rng, circle=2):
    engine = engine_of(registry, cfg, priest(registry, WEAPON), rng=rng)
    engine.perform("cler", f"cast:{WEAPON}:{circle}:goblin_1")
    return engine


def test_weapon_cast_at_a_target_puts_the_summon_in_its_zone(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[15], d8=[5]))
    assert summons_of(engine)[0].params["zone"] == "balcony"


def test_weapon_cast_at_a_target_hits_at_once(registry, cfg):
    # 15 + 4 = 19 против КД 15; 1d8 = 5, +2 Мдр
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[15], d8=[5]))
    assert hp(engine, "goblin_1") == 30 - 7


def test_weapon_cast_at_a_target_can_miss(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[5]))
    assert hp(engine, "goblin_1") == 30


def test_weapon_cast_at_a_target_reports_a_miss_event(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON), rng=ScriptedRng(d20=[5]))
    events = engine.perform("cler", f"cast:{WEAPON}:2:goblin_1")
    assert [e.data["outcome"] for e in events if e.type == "attack"] == ["miss"]


def test_weapon_cast_at_a_target_critical_doubles_the_dice(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[20], d8=[5, 3]))
    assert hp(engine, "goblin_1") == 30 - (5 + 3 + 2)


def test_weapon_cast_at_a_target_at_circle_three_hits_with_two_dice(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[15], d8=[5, 6]), circle=3)
    assert hp(engine, "goblin_1") == 30 - (5 + 6 + 2)


def test_weapon_cast_at_a_target_costs_the_bonus_action_and_leaves_the_action(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[5]))
    assert (turn(engine, "cler").bonus, turn(engine, "cler").action) == (False, True)


def test_weapon_cast_at_a_target_spends_one_slot_and_holds_concentration(registry, cfg):
    hero = priest(registry, WEAPON)
    engine = engine_of(registry, cfg, hero, rng=ScriptedRng(d20=[5]))
    engine.perform("cler", f"cast:{WEAPON}:2:goblin_1")
    assert hero.creature.resources["spell_slot:2"].current == 2
    assert engine.creature("cler").concentration.spell_id == WEAPON


def test_weapon_cast_at_a_target_logs_the_zone_once(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[5]))
    assert engine.state.log.count("Отец Марк: Духовное оружие — Балкон") == 1


def test_after_a_cast_at_a_target_the_next_turn_strikes_as_before(registry, cfg):
    engine = cast_at_goblin(registry, cfg, ScriptedRng(d20=[5, 15], d8=[5]))
    engine.start_turn("cler")
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert hp(engine, "goblin_1") == 30 - 7


def test_weapon_cast_into_an_empty_zone_does_not_strike(registry, cfg):
    # очередь пуста: бросок атаки дал бы AssertionError
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    events = engine.perform("cler", f"cast:{WEAPON}:2:door")
    assert [e for e in events if e.type == "attack"] == []
    assert hp(engine, "goblin_1") == 30


def test_flaming_sphere_cast_has_only_zone_targets(registry, cfg):
    hero = make_wizard(registry)
    hero.sheet.prepared_of().append(SPHERE)
    hero.creature.resources["spell_slot:2"] = ResourcePool(current=3, max=3)
    engine = engine_of(registry, cfg, hero)
    ids = [i for i in option_ids(engine, "wiz") if i.startswith(f"cast:{SPHERE}:2:")]
    assert ids == [f"cast:{SPHERE}:2:{z}" for z in ("door", "hall", "balcony")]


def lay_down(engine, ref):
    set_hp(engine, ref, 0)
    part(engine, ref).status = "down"


def test_weapon_cast_menu_has_no_row_for_a_downed_enemy(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    lay_down(engine, "goblin_1")
    assert f"cast:{WEAPON}:2:goblin_1" not in option_ids(engine, "cler")


def test_weapon_cast_menu_keeps_the_zone_of_a_downed_enemy(registry, cfg):
    engine = engine_of(registry, cfg, priest(registry, WEAPON))
    lay_down(engine, "goblin_1")
    assert f"cast:{WEAPON}:2:balcony" in option_ids(engine, "cler")


def test_weapon_strike_is_not_offered_against_a_downed_enemy(registry, cfg):
    # решение 75: лежачего врага нет в меню героя
    engine = cast_weapon(registry, cfg)
    lay_down(engine, "goblin_1")
    assert f"summon_attack:{WEAPON}:goblin_1" not in summon_ids(engine)


def test_weapon_strike_is_offered_against_a_surrendered_enemy(registry, cfg):
    engine = cast_weapon(registry, cfg)
    part(engine, "goblin_1").status = "surrendered"
    assert f"summon_attack:{WEAPON}:goblin_1" in summon_ids(engine)


def test_weapon_strike_is_offered_against_an_enemy_in_the_summon_zone(registry, cfg):
    # враг в зоне призыва (оружие переставили к нему), а не рядом
    engine = cast_weapon(registry, cfg, monsters=[mon("goblin_1", "goblin_warrior", "door")])
    engine.perform("cler", f"summon_move:{WEAPON}:door")
    engine.start_turn("cler")
    assert f"summon_attack:{WEAPON}:goblin_1" in summon_ids(engine)


# добор по выжившим мутантам П4: призыв

def test_summon_move_costs_the_bonus_action(registry, cfg):
    engine = cast_weapon(registry, cfg, zone="hall")
    option = [o for o in engine.available_actions("cler") if o.kind == "summon_move"][0]
    assert option.cost == "bonus"


def test_every_summon_of_the_caster_gets_its_own_options(registry, cfg):
    # два призыва на одном заклинателе (в игре концентрация держит один): пункты обоих
    engine = cast_weapon(registry, cfg)
    creature(engine, "cler").active_effects.append(ActiveEffect(
        id=SPHERE, source="cler", kind="summon",
        params={"zone": "hall", "spell": SPHERE, "dice": "2d6"},
    ))
    ids = summon_ids(engine)
    assert {f"summon_attack:{WEAPON}:goblin_1", f"summon_attack:{SPHERE}:goblin_1"} <= set(ids)


def test_weapon_miss_event_names_attacker_target_spell_and_mode(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[5]))
    events = engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert events[0].data == {
        "attacker": "cler", "target": "goblin_1", "weapon": WEAPON, "mode": "spell",
        "outcome": "miss", "damage": 0,
    }


def test_weapon_attack_roll_line_shows_the_spell_attack_parts(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[15], d8=[5]))
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert any("d20 (15) + 2 Мдр + 2 мастерство = 19" in line for line in engine.state.log)


def test_weapon_kill_is_credited_to_the_cleric(registry, cfg):
    engine = cast_weapon(registry, cfg, rng=ScriptedRng(d20=[15], d8=[5]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("cler", f"summon_attack:{WEAPON}:goblin_1")
    assert (part(engine, "goblin_1").status, part(engine, "goblin_1").last_hit_by) == (
        "dead", "cler",
    )


def test_weapon_critical_hit_drops_a_zombie_despite_undead_fortitude(registry, cfg):
    # крит отключает Стойкость нежити; в очереди нет d20 на её спасбросок
    engine = cast_weapon(
        registry, cfg, rng=ScriptedRng(d20=[20], d8=[5, 3]),
        monsters=[mon("zom", "zombie", "balcony")],
    )
    set_hp(engine, "zom", 1)
    engine.perform("cler", f"summon_attack:{WEAPON}:zom")
    assert part(engine, "zom").status == "dead"


def test_flaming_sphere_damage_roll_line(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[3, 4]))
    engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert "  Урон (Пылающий шар): 2d6 (3, 4) = 7 огненный" in engine.state.log


def test_flaming_sphere_writes_the_hit_points_line(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[3, 4]))
    engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert f"  {engine.name('goblin_1')}: {engine.hp_text('goblin_1')}" in engine.state.log


def test_flaming_sphere_returns_an_auto_attack_event(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[3, 4]))
    events = engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert events[0].data == {
        "attacker": "wiz", "target": "goblin_1", "weapon": SPHERE, "mode": "spell",
        "outcome": "auto", "damage": 7,
    }


def test_flaming_sphere_kill_is_credited_to_the_caster(registry, cfg):
    engine = sphere_engine(registry, cfg, ScriptedRng(d20=[5], d6=[3, 4]))
    set_hp(engine, "goblin_1", 3)
    engine.perform("wiz", f"summon_attack:{SPHERE}:goblin_1")
    assert (part(engine, "goblin_1").status, part(engine, "goblin_1").last_hit_by) == (
        "dead", "wiz",
    )


# добор по выжившим мутантам П4: аура

def test_spirit_guardians_last_while_concentration_lasts(registry, cfg):
    engine = guardians(registry, cfg)
    (effect,) = [e for e in creature(engine, "cler").active_effects if e.kind == "aura"]
    assert (effect.expires.kind, effect.expires.owner) == ("concentration", "cler")


def test_spirit_guardians_vanish_when_the_cleric_loses_concentration(registry, cfg):
    engine = guardians(registry, cfg)
    engine.drop_concentration_effects("cler")
    assert [e for e in creature(engine, "cler").active_effects if e.kind == "aura"] == []


def test_spirit_guardians_cast_at_the_fourth_circle_gain_a_die(registry, cfg):
    hero = priest(registry, GUARDIANS)
    hero.creature.resources["spell_slot:4"] = ResourcePool(current=1, max=1)
    engine = engine_of(registry, cfg, hero, monsters=GOBLIN)
    engine.perform("cler", f"cast:{GUARDIANS}:4:")
    (effect,) = [e for e in creature(engine, "cler").active_effects if e.kind == "aura"]
    assert effect.params["dice"] == "4d8"


def test_aura_damage_roll_line(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(**FAIL_15))
    end_turn(engine, "goblin_1")
    assert "  Урон (Духовные стражи): 3d8 (4, 5, 6) = 15 излучением" in engine.state.log


def test_aura_writes_the_hit_points_line(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(**FAIL_15))
    end_turn(engine, "goblin_1")
    assert f"  {engine.name('goblin_1')}: {engine.hp_text('goblin_1')}" in engine.state.log


def test_aura_kill_is_credited_to_the_cleric(registry, cfg):
    engine = guardians(registry, cfg, rng=ScriptedRng(d20=[5], d8=[8, 8, 8]))
    set_hp(engine, "goblin_1", 10)
    end_turn(engine, "goblin_1")
    assert (part(engine, "goblin_1").status, part(engine, "goblin_1").last_hit_by) == (
        "dead", "cler",
    )


def test_aura_finds_the_caster_behind_a_hero_of_another_zone(registry, cfg):
    # разведчик в другой зоне стоит в списке раньше жреца: аура всё равно бьёт
    scout = make_fighter(registry, "scout")
    engine = make_engine(
        registry, cfg, heroes=[(scout, "balcony"), priest(registry, GUARDIANS)],
        monsters=GOBLIN, rng=ScriptedRng(**FAIL_15),
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 15


def second_priest(registry):
    hero = make_cleric(registry, level=3, hero_id="cler2")
    hero.sheet.prepared_of().append(GUARDIANS)
    hero.creature.resources["spell_slot:4"] = ResourcePool(current=1, max=1)
    return hero


def two_priests(registry, cfg, rng, monsters=GOBLIN, **kwargs):
    return engine_of(
        registry, cfg, priest(registry, GUARDIANS), rng=rng, monsters=monsters,
        extra=[second_priest(registry)], **kwargs,
    )


def attack_events(events):
    return [e.data for e in events if e.type == "attack"]


def test_two_clerics_auras_hit_an_enemy_once(registry, cfg):
    # SRD 5.2.1, Combining Spell Effects: то же заклинание от двух жрецов не складывается;
    # в очереди одна грань d20 -- второй спасбросок дал бы AssertionError
    engine = two_priests(registry, cfg, ScriptedRng(d20=[5], d8=[4, 5, 6]))
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    events = end_turn(engine, "goblin_1")
    assert [(e["attacker"], e["damage"]) for e in attack_events(events)] == [("cler", 15)]


def test_equal_auras_of_two_clerics_are_hit_by_the_first_in_turn_order(registry, cfg):
    engine = two_priests(registry, cfg, ScriptedRng(d20=[5], d8=[4, 5, 6]))
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    events = end_turn(engine, "goblin_1")
    assert [e["attacker"] for e in attack_events(events)] == ["cler"]


def test_stronger_aura_of_the_second_cleric_hits_instead_of_the_first(registry, cfg):
    # 4 круг: 4d8 против 3d8
    engine = two_priests(registry, cfg, ScriptedRng(d20=[5], d8=[1, 2, 3, 4]))
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:4:")
    events = end_turn(engine, "goblin_1")
    assert [(e["attacker"], e["damage"]) for e in attack_events(events)] == [("cler2", 10)]


def test_stronger_aura_hits_when_it_was_cast_first(registry, cfg):
    engine = two_priests(registry, cfg, ScriptedRng(d20=[5], d8=[1, 2, 3, 4]))
    engine.perform("cler2", f"cast:{GUARDIANS}:4:")
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    events = end_turn(engine, "goblin_1")
    assert [(e["attacker"], e["damage"]) for e in attack_events(events)] == [("cler2", 10)]


def test_stronger_aura_leaves_the_enemy_with_the_four_dice_damage(registry, cfg):
    engine = two_priests(registry, cfg, ScriptedRng(d20=[5], d8=[1, 2, 3, 4]))
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:4:")
    end_turn(engine, "goblin_1")
    assert hp(engine, "goblin_1") == 30 - 10


def test_second_cleric_entering_after_the_first_aura_hit_does_not_roll(registry, cfg):
    # оба жреца в двери, гоблин в зале; жрец 1 входит -- бросок, жрец 2 входит в тот же ход -- нет
    rng = ScriptedRng(d20=[5], d8=[4, 5, 6])
    engine = two_priests(registry, cfg, rng, hero_zone="door")
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    events = engine.perform("cler2", "move:hall")
    assert attack_events(events) == []
    assert hp(engine, "goblin_1") == 30 - 15


def test_cleric_entering_with_a_weaker_aura_lets_the_stronger_one_hit(registry, cfg):
    # жрец 1 уже в зале со стражами 4 круга; жрец 2 со стражами 3 круга входит -- гоблин ещё не бит:
    # бьёт сильнейшая аура (cler, 4d8), а не аура входящего
    hero = priest(registry, GUARDIANS)
    hero.creature.resources["spell_slot:4"] = ResourcePool(current=1, max=1)
    engine = engine_of(
        registry, cfg, hero, rng=ScriptedRng(d20=[5], d8=[1, 2, 3, 4]), monsters=GOBLIN,
        extra=[second_priest(registry)], hero_zone="door",
    )
    move_to(engine, "cler", "hall")
    engine.perform("cler", f"cast:{GUARDIANS}:4:")
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    events = engine.perform("cler2", "move:hall")
    assert [(e["attacker"], e["damage"]) for e in attack_events(events)] == [("cler", 10)]


def test_cleric_entering_his_zone_does_not_hit_an_enemy_under_another_aura_elsewhere(registry, cfg):
    # жрец 2 со стражами стоит на балконе рядом со своим гоблином (тот ещё не бит); жрец 1 входит
    # в зал: бьётся только гоблин зала (очередь на один спасбросок)
    monsters = [
        mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "balcony"),
    ]
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=monsters,
        rng=ScriptedRng(d20=[5], d8=[4, 5, 6]), extra=[(second_priest(registry), "balcony")],
        hero_zone="door",
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    engine.perform("cler", "move:hall")
    assert (hp(engine, "goblin_1"), hp(engine, "goblin_2")) == (30 - 15, 30)


def test_different_enemies_are_each_hit_once_by_two_auras(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    rng = ScriptedRng(d20=[5, 5], d8=[4, 5, 6, 1, 1, 1])
    engine = two_priests(registry, cfg, rng, monsters=monsters)
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    engine.perform("cler2", f"cast:{GUARDIANS}:3:")
    first = end_turn(engine, "goblin_1")
    second = end_turn(engine, "goblin_2")
    assert (len(attack_events(first)), len(attack_events(second))) == (1, 1)


def test_cleric_entering_a_zone_reports_every_enemy_it_hit(registry, cfg):
    monsters = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    rng = ScriptedRng(d20=[5, 18], d8=[4, 5, 6, 1, 1, 1])
    engine = engine_of(
        registry, cfg, priest(registry, GUARDIANS), monsters=monsters, rng=rng, hero_zone="door"
    )
    engine.perform("cler", f"cast:{GUARDIANS}:3:")
    events = engine.perform("cler", "move:hall")
    assert [e.data["target"] for e in events if e.type == "attack"] == ["goblin_1", "goblin_2"]
