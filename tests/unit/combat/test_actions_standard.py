# Стандартные действия (шаг 17): Disengage, Dodge, Help, Second Wind, зелье, стабилизация.
#   disengage -- действие; turn.disengaged = True: выход из зон этим ходом не провоцирует атаки
#     (см. test_opportunity.py)
#   dodge -- действие; на себя ActiveEffect(id="dodge", kind="modifier",
#     params={"target": "attack_roll", "mode": "disadvantage", "side": "target"},
#     expires=Expiry(kind="start_of_turn", owner=<ref>)) -- атаки по уклоняющемуся с помехой (D1,
#     эффект со стороны цели); второй ActiveEffect(id="dodge") с params={"target":
#     "saving_throw", "mode": "advantage", "ability": "dex"} (тот же expires) -- преимущество на
#     его спасброски ЛОВ (см. test_area_saves.py); оба снимаются в начале следующего хода участника
#   help:<союзник>:<враг> -- действие; помощник в зоне врага; на союзника ActiveEffect(id="help",
#     params={"target": "attack_roll", "mode": "advantage", "against": <враг>, "consume": True},
#     expires=Expiry(kind="start_of_turn", owner=<помощник>)) -- следующая атака союзника по этому
#     врагу с преимуществом, эффект снимается после броска
#   second_wind -- бонусное; 1d10 + уровень воина, пул second_wind -1; пул 0 -- нет варианта
#   use_item:<предмет> -- бонусное; зелье лечения (2d4+2), предмет уходит из инвентаря
#   stabilize:<цель> -- действие; цель -- умирающий (0 HP, не стабилен, status "down") в той же
#     зоне; проверка Медицины СЛ 10: успех -> death_saves.stable (hp остаётся 0); провал -- действие
#     потрачено; цель вне зоны / в сознании / уже стабильна / мертва -- варианта нет
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    hp,
    make_engine,
    make_fighter,
    mon,
    move_to,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.rules.death_saves import is_stable
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.rules.results import Rejected


def duel(registry, cfg, rng=None, hero=None, goblin_zone="hall", **kwargs):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)], **kwargs,
    )


def effect_ids(engine, ref):
    return [e.id for e in creature(engine, ref).active_effects]


# Disengage

def test_disengage_marks_the_turn(registry, cfg):
    engine = duel(registry, cfg)
    engine.perform("hero", "disengage")
    assert turn(engine, "hero").disengaged is True
    assert turn(engine, "hero").action is False


# Dodge

def test_dodge_puts_an_effect_on_the_dodger(registry, cfg):
    engine = duel(registry, cfg)
    engine.perform("hero", "dodge")
    assert effect_ids(engine, "hero") == ["dodge", "dodge"]
    assert turn(engine, "hero").action is False


def test_dodge_effect_is_target_side_until_next_turn(registry, cfg):
    engine = duel(registry, cfg)
    engine.perform("hero", "dodge")
    dodge = creature(engine, "hero").active_effects[0]
    assert dodge.params["target"] == "attack_roll"
    assert dodge.params["side"] == "target"
    assert dodge.params["mode"] == "disadvantage"
    assert dodge.expires.kind == "start_of_turn"
    assert dodge.expires.owner == "hero"


def test_dodge_second_effect_is_advantage_on_dex_saves(registry, cfg):
    engine = duel(registry, cfg)
    engine.perform("hero", "dodge")
    saves = [e for e in creature(engine, "hero").active_effects
             if e.params["target"] == "saving_throw"]
    assert len(saves) == 1
    assert saves[0].params["mode"] == "advantage"
    assert saves[0].params["ability"] == "dex"
    assert saves[0].expires.kind == "start_of_turn"
    assert saves[0].expires.owner == "hero"


def test_dodge_advantage_does_not_apply_to_other_saves(registry, cfg):
    # ТЕЛ-спасбросок уклоняющегося: один d20
    rng = ScriptedRng(d20=[10])
    engine = duel(registry, cfg, rng)
    engine.perform("hero", "dodge")
    engine.save("hero", "con", 10)
    assert rng.left("d20") == 0


def test_attack_on_dodging_target_has_disadvantage(registry, cfg):
    # d20 18 и 2: с помехой берётся 2 -> 6 против КД 19 -- промах
    engine = duel(registry, cfg, ScriptedRng(d20=[18, 2]))
    engine.perform("hero", "dodge")
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert hp(engine, "hero") == 12


def test_attack_on_non_dodging_target_rolls_one_die(registry, cfg):
    rng = ScriptedRng(d20=[18], d6=[3])
    engine = duel(registry, cfg, rng)
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert rng.left("d20") == 0
    assert hp(engine, "hero") == 7


def test_dodge_ends_at_the_start_of_the_next_own_turn(registry, cfg):
    controllers = {"hero": ScriptedController(["dodge"]), "goblin_1": ScriptedController([])}
    engine = duel(registry, cfg, controllers=controllers)
    engine.step()
    engine.step()
    assert effect_ids(engine, "hero") == ["dodge", "dodge"]
    engine.step()
    assert effect_ids(engine, "hero") == []


# Help

def help_engine(registry, cfg, rng):
    helper = make_fighter(registry, "helper")
    attacker = make_fighter(registry, "hero")
    return make_engine(
        registry, cfg, heroes=[helper, attacker], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )


def test_help_puts_an_effect_on_the_ally(registry, cfg):
    engine = help_engine(registry, cfg, ScriptedRng())
    engine.perform("helper", "help:hero:goblin_1")
    assert effect_ids(engine, "hero") == ["help"]
    assert turn(engine, "helper").action is False


def test_help_gives_advantage_on_the_next_attack_on_that_enemy(registry, cfg):
    # два d20: берётся больший (17 + 5 >= 15); без помощи 3 + 5 = 8 было бы промахом
    engine = help_engine(registry, cfg, ScriptedRng(d20=[3, 17], d8=[4]))
    engine.perform("helper", "help:hero:goblin_1")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_help_is_spent_by_the_attack(registry, cfg):
    engine = help_engine(registry, cfg, ScriptedRng(d20=[3, 17, 3], d8=[4]))
    engine.perform("helper", "help:hero:goblin_1")
    engine.perform("hero", "attack:longsword:goblin_1")
    assert effect_ids(engine, "hero") == []


def test_help_does_not_work_against_another_enemy(registry, cfg):
    rng = ScriptedRng(d20=[3])
    engine = help_engine(registry, cfg, rng)
    engine.perform("helper", "help:hero:goblin_1")
    engine.perform("hero", "attack:longsword:goblin_2")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_2") == 10


def test_help_needs_the_helper_next_to_the_enemy(registry, cfg):
    engine = help_engine(registry, cfg, ScriptedRng())
    move_to(engine, "helper", "door")
    assert "help:hero:goblin_1" not in option_ids(engine, "helper")


# Second Wind

def test_second_wind_heals_1d10_plus_level(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d10=[6]))
    set_hp(engine, "hero", 3)
    engine.perform("hero", "second_wind")
    assert hp(engine, "hero") == 10


def test_second_wind_does_not_exceed_max_hp(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d10=[10]))
    set_hp(engine, "hero", 8)
    engine.perform("hero", "second_wind")
    assert hp(engine, "hero") == 12


def test_second_wind_spends_one_use(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d10=[1]))
    set_hp(engine, "hero", 3)
    engine.perform("hero", "second_wind")
    assert creature(engine, "hero").resources["second_wind"].current == 1


def test_second_wind_is_gone_when_the_pool_is_empty(registry, cfg):
    engine = duel(registry, cfg)
    creature(engine, "hero").resources["second_wind"].current = 0
    assert "second_wind" not in option_ids(engine, "hero")
    assert isinstance(engine.perform("hero", "second_wind"), Rejected)


def test_monster_has_no_second_wind(registry, cfg):
    assert "second_wind" not in option_ids(duel(registry, cfg), "goblin_1")


# зелье

def test_potion_heals_2d4_plus_2(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    engine = duel(registry, cfg, ScriptedRng(d4=[2, 3]), hero=hero)
    set_hp(engine, "hero", 3)
    engine.perform("hero", "use_item:potion_of_healing")
    assert hp(engine, "hero") == 10


def test_potion_leaves_the_inventory(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    engine = duel(registry, cfg, ScriptedRng(d4=[1, 1]), hero=hero)
    engine.perform("hero", "use_item:potion_of_healing")
    assert count_item(hero, "potion_of_healing") == 0


def test_no_potion_no_option(registry, cfg):
    assert "use_item:potion_of_healing" not in option_ids(duel(registry, cfg), "hero")


# стабилизация

def stabilize_engine(registry, cfg, rng, ally_zone="hall"):
    healer = make_fighter(registry, "hero")
    ally = make_fighter(registry, "ally")
    engine = make_engine(
        registry, cfg, heroes=[healer, ally], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    move_to(engine, "ally", ally_zone)
    down_hero(engine, "ally")
    return engine


def test_stabilize_succeeds_on_dc_10(registry, cfg):
    # d20 8 + Медицина 2 = 10
    engine = stabilize_engine(registry, cfg, ScriptedRng(d20=[8]))
    engine.perform("hero", "stabilize:ally")
    assert is_stable(engine.heroes["ally"].creature)
    assert hp(engine, "ally") == 0


def test_stabilize_fails_below_dc_10(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng(d20=[7]))
    engine.perform("hero", "stabilize:ally")
    assert not is_stable(engine.heroes["ally"].creature)


def test_failed_stabilize_still_spends_the_action(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng(d20=[7]))
    engine.perform("hero", "stabilize:ally")
    assert turn(engine, "hero").action is False


def test_stabilize_needs_the_same_zone(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng(), ally_zone="door")
    assert "stabilize:ally" not in option_ids(engine, "hero")


def test_conscious_ally_cannot_be_stabilized(registry, cfg):
    engine = duel(registry, cfg)
    assert not [i for i in option_ids(engine, "hero") if i.startswith("stabilize:")]


def test_already_stable_ally_cannot_be_stabilized(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng())
    engine.heroes["ally"].creature.death_saves.stable = True
    assert "stabilize:ally" not in option_ids(engine, "hero")


def test_dead_ally_cannot_be_stabilized(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng())
    part(engine, "ally").status = "dead"
    assert "stabilize:ally" not in option_ids(engine, "hero")


def test_stabilize_is_a_check_with_the_hero_medicine_bonus(registry, cfg):
    engine = stabilize_engine(registry, cfg, ScriptedRng(d20=[8]))
    engine.perform("hero", "stabilize:ally")
    assert any("= 10" in line for line in engine.state.log)


def test_potion_writes_log_line_with_name_and_healed(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    engine = duel(registry, cfg, ScriptedRng(d4=[2, 3]), hero=hero)
    set_hp(engine, "hero", 3)
    engine.perform("hero", "use_item:potion_of_healing")
    name = registry.get("item", "potion_of_healing").name
    assert [x for x in engine.state.log if f"{name} +7," in x] == [engine.state.log[-1]]
