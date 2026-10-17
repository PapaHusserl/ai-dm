# Партия К7х, п. 6: Истребитель орд (docs/plan-k7x.md, В7).
#   Охотник (следопыт 3 ур., feature_choices {"hunters_prey": ["horde_breaker"]}):
#   * features.horde_mark (из attack.perform): первая атака оружием за ход (попал или промахнулся)
#     ставит
#     ActiveEffect(id="horde_breaker", kind="flag", expires=end_of_turn, owner=герой) с params
#     {"weapon", "target", "zone", "used"}; безоружный удар, атака монстра, провоцированная атака
#       флаг не
#     ставят; вторая атака хода (Доп. атака) флаг не дублирует;
#   * available.horde_options: пока флаг не used -- пункт horde_breaker:<цель> (kind
#     "horde_breaker",
#     cost "free", params {"weapon", "target"}) по каждой другой цели в зоне первой цели, которую
#       это
#     оружие достаёт (base_advantage не None); по первой цели пункта нет;
#   * features.horde_breaker: used = True, атака тем же оружием без траты действия и attacks_left;
#   * AutoHeroController берёт пункт первым; флаг снимается engine.expire("end_of_turn") в конце
#     хода;
#     с colossus_slayer ни флага, ни пункта.
#   Следопыт Грей: скимитар +5 (d20 15 попадает по КД 15), 1d6+3; длинный лук. Гоблины здесь по 40
#     HP.
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
)
from test_ranger_combat import make_ranger

from ai_dm.combat.controllers import AutoHeroController
from ai_dm.rules.inventory import remove_item
from ai_dm.state.combat import CombatState
from ai_dm.state.creature import ActiveEffect

HIT = "attack:scimitar:goblin_1"


def horde_ranger(registry, level=3, prey="horde_breaker", sword=True):
    hero = make_ranger(registry, level=level, subclass="hunter", options={"hunters_prey": prey})
    if sword:
        give_weapon(hero, registry, "scimitar")
    return hero


def horde(registry, cfg, rng=None, hero=None, zones=("hall", "hall"), hero_zone="hall"):
    monsters = [mon(f"goblin_{i + 1}", "goblin_warrior", zone) for i, zone in enumerate(zones)]
    engine = make_engine(
        registry, cfg, heroes=[hero or horde_ranger(registry)], rng=rng, monsters=monsters,
        hero_zone=hero_zone,
    )
    for i in range(len(zones)):
        creature(engine, f"goblin_{i + 1}").hp_max = 40
        set_hp(engine, f"goblin_{i + 1}", 40)
    return engine


def horde_ids(engine):
    return [o.id for o in engine.available_actions("hero") if o.kind == "horde_breaker"]


def flags(engine):
    return [e for e in creature(engine, "hero").active_effects if e.id == "horde_breaker"]


# --- пункт после атаки ---

def test_no_horde_option_before_the_first_attack(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng())
    assert horde_ids(engine) == []
    assert flags(engine) == []


def test_hit_opens_the_horde_option_on_the_other_goblin(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    assert horde_ids(engine) == ["horde_breaker:goblin_2"]


def test_miss_opens_the_horde_option_too(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", HIT)
    assert horde_ids(engine) == ["horde_breaker:goblin_2"]


def test_no_horde_option_on_the_first_target(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    assert "horde_breaker:goblin_1" not in option_ids(engine, "hero")


def test_horde_option_kind_cost_and_params(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    option = [o for o in engine.available_actions("hero") if o.kind == "horde_breaker"][0]
    assert option.cost == "free"
    assert option.params == {"weapon": "scimitar", "target": "goblin_2"}


def test_horde_option_label_names_the_weapon_and_the_target(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    option = [o for o in engine.available_actions("hero") if o.kind == "horde_breaker"][0]
    assert option.label.startswith("Истребитель орд: ")
    assert option.label == "Истребитель орд: скимитар → Воин-гоблин 2"


def test_horde_option_for_each_other_goblin_in_the_zone(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]), zones=("hall", "hall", "hall"))
    engine.perform("hero", HIT)
    assert sorted(horde_ids(engine)) == ["horde_breaker:goblin_2", "horde_breaker:goblin_3"]


def test_goblin_in_another_zone_is_not_offered(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]), zones=("hall", "balcony"))
    engine.perform("hero", HIT)
    assert horde_ids(engine) == []


def test_only_goblins_of_the_first_target_zone_are_offered(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]),
                   zones=("hall", "balcony", "hall"))
    engine.perform("hero", HIT)
    assert horde_ids(engine) == ["horde_breaker:goblin_3"]


def test_dead_goblin_is_not_offered(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    part(engine, "goblin_2").status = "dead"
    assert horde_ids(engine) == []


def test_no_horde_option_without_the_feature_choice(registry, cfg):
    hero = make_fighter(registry)
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d8=[4]), hero=hero)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert horde_ids(engine) == []
    assert flags(engine) == []


def test_colossus_slayer_hero_has_no_horde_option(registry, cfg):
    hero = horde_ranger(registry, prey="colossus_slayer")
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3], d8=[2]), hero=hero)
    engine.perform("hero", HIT)
    assert horde_ids(engine) == []
    assert flags(engine) == []


def test_horde_hero_gets_no_colossus_damage_on_a_wounded_target(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    set_hp(engine, "goblin_1", 30)
    engine.perform("hero", HIT)
    assert hp(engine, "goblin_1") == 24


# --- флаг ---

def test_flag_is_set_by_the_first_attack(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    assert len(flags(engine)) == 1
    flag = flags(engine)[0]
    assert flag.kind == "flag"
    assert flag.source == "hero"
    assert flag.params == {
        "weapon": "scimitar", "target": "goblin_1", "zone": "hall", "used": False,
    }


def test_flag_expires_at_the_end_of_the_hero_turn(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    expiry = flags(engine)[0].expires
    assert (expiry.kind, expiry.value, expiry.owner) == ("end_of_turn", 0, "hero")


def test_flag_is_removed_by_the_end_of_turn_expiry(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    engine.expire("end_of_turn", "hero")
    assert flags(engine) == []
    assert horde_ids(engine) == []


def test_flag_survives_the_end_of_another_turn(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    engine.expire("end_of_turn", "goblin_1")
    assert len(flags(engine)) == 1


def test_flag_is_set_by_a_miss(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", HIT)
    assert len(flags(engine)) == 1


def test_unarmed_strike_sets_no_flag(registry, cfg):
    hero = horde_ranger(registry, sword=False)
    hero.equipped.main_hand = None
    engine = horde(registry, cfg, ScriptedRng(d20=[15]), hero=hero)
    engine.perform("hero", "attack:unarmed:goblin_1")
    assert flags(engine) == []
    assert horde_ids(engine) == []


def test_opportunity_attack_sets_no_flag(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]), zones=("hall",))
    engine.start_turn("goblin_1")
    engine.perform("goblin_1", "move:door")
    assert hp(engine, "goblin_1") < 40
    assert flags(engine) == []


def test_monster_attack_sets_no_flag(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert flags(engine) == []
    assert [e.id for e in creature(engine, "goblin_1").active_effects] == []


def test_second_attack_of_extra_attack_does_not_duplicate_the_flag(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]), hero=horde_ranger(
        registry, level=5), zones=("hall", "hall"))
    engine.perform("hero", HIT)
    engine.perform("hero", "attack:scimitar:goblin_2")
    assert len(flags(engine)) == 1
    assert flags(engine)[0].params["target"] == "goblin_1"


def test_the_flag_is_not_moved_by_a_later_attack_on_another_goblin(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]), hero=horde_ranger(
        registry, level=5))
    engine.perform("hero", HIT)
    engine.perform("hero", "attack:scimitar:goblin_2")
    # пункт по-прежнему «по другой цели, чем первая»: goblin_2
    assert horde_ids(engine) == ["horde_breaker:goblin_2"]


# --- выполнение ---

def test_perform_attacks_the_second_goblin(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 4]))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert hp(engine, "goblin_1") == 34
    assert hp(engine, "goblin_2") == 33


def test_perform_costs_neither_action_nor_attacks(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    turn = part(engine, "hero").turn
    before = (turn.action, turn.attacks_left, turn.bonus)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert (turn.action, turn.attacks_left, turn.bonus) == before


def test_perform_works_at_extra_attack_without_spending_it(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]),
                   hero=horde_ranger(registry, level=5))
    engine.perform("hero", HIT)
    left = part(engine, "hero").turn.attacks_left
    engine.perform("hero", "horde_breaker:goblin_2")
    assert part(engine, "hero").turn.attacks_left == left


def test_perform_marks_the_flag_as_used(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert flags(engine)[0].params["used"] is True


def test_option_disappears_after_use(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]),
                   zones=("hall", "hall", "hall"))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert horde_ids(engine) == []


def test_second_use_in_the_same_turn_is_rejected(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    result = engine.perform("hero", "horde_breaker:goblin_2")
    assert result.reason == "not_available"


def test_perform_logs_an_attack_on_the_second_goblin(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    before = len(engine.state.log)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert any("Атака" in line for line in engine.state.log[before:])


def test_perform_returns_events_of_the_attack(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    events = engine.perform("hero", "horde_breaker:goblin_2")
    assert [e.type for e in events] == ["attack"]
    assert events[0].data["target"] == "goblin_2"


def test_perform_can_kill_the_second_goblin(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 6]))
    set_hp(engine, "goblin_2", 5)
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert part(engine, "goblin_2").status == "dead"


def test_horde_attack_does_not_set_a_new_flag(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    assert len(flags(engine)) == 1


def test_flag_is_new_in_the_next_turn(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15, 15], d6=[3, 3, 3]))
    engine.perform("hero", HIT)
    engine.perform("hero", "horde_breaker:goblin_2")
    engine.expire("end_of_turn", "hero")
    engine.start_turn("hero")
    engine.perform("hero", HIT)
    assert horde_ids(engine) == ["horde_breaker:goblin_2"]
    assert flags(engine)[0].params["used"] is False


# --- дальний бой ---

def test_longbow_gives_the_option_for_the_other_goblin_in_range(registry, cfg):
    hero = horde_ranger(registry, sword=False)
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d8=[4]), hero=hero, hero_zone="door")
    engine.perform("hero", "attack:longbow:goblin_1")
    assert horde_ids(engine) == ["horde_breaker:goblin_2"]
    option = [o for o in engine.available_actions("hero") if o.kind == "horde_breaker"][0]
    assert option.params["weapon"] == "longbow"


def test_longbow_horde_attack_uses_the_bow(registry, cfg):
    hero = horde_ranger(registry, sword=False)
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d8=[4, 5]), hero=hero,
                   hero_zone="door")
    engine.perform("hero", "attack:longbow:goblin_1")
    engine.perform("hero", "horde_breaker:goblin_2")
    assert hp(engine, "goblin_2") == 32


# --- оружие первой атаки пропало ---

def test_menu_is_built_without_error_when_the_weapon_was_removed(registry, cfg):
    hero = horde_ranger(registry)
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]), hero=hero)
    engine.perform("hero", HIT)
    hero.equipped.main_hand = None
    remove_item(hero, "scimitar")
    assert horde_ids(engine) == []


def test_flag_stays_but_no_option_when_the_weapon_was_removed(registry, cfg):
    hero = horde_ranger(registry)
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]), hero=hero)
    engine.perform("hero", HIT)
    hero.equipped.main_hand = None
    remove_item(hero, "scimitar")
    engine.available_actions("hero")
    assert len(flags(engine)) == 1


# --- AutoHeroController и сохранение ---

def test_auto_hero_takes_the_horde_option_first(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    options = engine.available_actions("hero")
    assert AutoHeroController(engine).choose_turn(options, "hero") == "horde_breaker:goblin_2"


def test_auto_hero_attacks_when_there_is_no_horde_option(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng())
    options = engine.available_actions("hero")
    assert AutoHeroController(engine).choose_turn(options, "hero").startswith("attack:")


def test_auto_hero_turn_makes_two_attacks_and_clears_the_flag(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 3]))
    engine.step()
    assert hp(engine, "goblin_1") < 40
    assert hp(engine, "goblin_2") < 40
    assert flags(engine) == []


def test_flag_round_trips_through_the_combat_save(registry, cfg):
    engine = horde(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", HIT)
    hero_json = engine.heroes["hero"].model_dump_json()
    flag = flags(engine)[0]
    assert ActiveEffect.model_validate_json(flag.model_dump_json()) == flag
    assert '"horde_breaker"' in hero_json
    assert CombatState.model_validate_json(engine.state.model_dump_json()) == engine.state
