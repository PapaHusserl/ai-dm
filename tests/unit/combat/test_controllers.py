# Контроллеры и тактика (шаг 18, A1): ai_dm.combat.controllers
#   Controller (Protocol):
#     choose(options: list[ActionOption], ctx: DecisionPoint) -> str (id варианта)
#   ScriptedController(script: list[str]):
#     отдаёт id по порядку; id вне options -> ValueError; скрипт кончился -> "end_turn"
#     (kind="turn_action") или "keep" (kind="intent_reconsider"); .seen -- список полученных ctx
#   EngineTactics(engine): детерминированная, броски не использует:
#     * цель -- враг в СВОЕЙ зоне с наименьшим hp_current среди боеспособных, ничья -- меньший id;
#       ближняя атака; при намерении группы kill, когда боеспособных врагов рядом нет, добивает
#       лежащего (status down) героя в своей зоне; без kill лежащих не трогает;
#     * нет врага в своей зоне, но есть дальняя атака -- стреляет (цель с наименьшим hp,
#       ничья -- id);
#     * иначе сближение: move:<зона> по кратчайшему пути к ближайшему врагу; если врагов в зонах
#       >= 2 шагов и действие свободно -- сначала dash;
#     * после атаки / нечего делать -- end_turn; на intent_reconsider -- "keep"
#   AutoHeroController(engine): EngineTactics + (1) hp_current <= hp_max // 2 и есть second_wind --
#     second_wind; (2) умирающий союзник в своей зоне -- stabilize:<он>; (3) заклинатель с доступным
#     заклинанием: magic_missile, иначе fire_bolt по врагу с наименьшим hp.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    move_to,
    part,
    set_hp,
    turn,
)

from ai_dm.combat.controllers import (
    AutoHeroController,
    EngineTactics,
    ScriptedController,
    is_quarreling,
    quarrel_targets,
)
from ai_dm.core.rng import Rng
from ai_dm.state.combat import DecisionPoint
from ai_dm.state.creature import ActiveEffect


def decide(controller, engine, ref, kind="turn_action"):
    options = engine.available_actions(ref)
    point = DecisionPoint(kind=kind, actor=ref, options=[o.id for o in options])
    return controller.choose(options, point)


def heroes_vs_goblin(registry, cfg, goblin_zone="hall", intent="kill", rng=None):
    return make_engine(
        registry, cfg,
        heroes=[make_fighter(registry, "hero_a"), make_fighter(registry, "hero_b")],
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)], intent=intent, rng=rng,
    )


# ScriptedController

def test_scripted_controller_returns_ids_in_order(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    controller = ScriptedController(["dodge", "dash"])
    assert decide(controller, engine, "hero_a") == "dodge"
    assert decide(controller, engine, "hero_a") == "dash"


def test_scripted_controller_rejects_an_unavailable_id(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    with pytest.raises(ValueError):
        decide(ScriptedController(["attack:longsword:nobody"]), engine, "hero_a")


def test_exhausted_script_ends_the_turn(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    assert decide(ScriptedController([]), engine, "hero_a") == "end_turn"


def test_exhausted_script_keeps_the_intent(registry, cfg):
    point = DecisionPoint(kind="intent_reconsider", actor="goblin_1", options=["keep"])
    assert ScriptedController([]).choose([], point) == "keep"


def test_scripted_controller_remembers_what_it_saw(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    controller = ScriptedController(["dodge"])
    decide(controller, engine, "hero_a")
    assert [p.actor for p in controller.seen] == ["hero_a"]
    assert controller.seen[0].kind == "turn_action"


# EngineTactics

def test_tactics_attack_the_weakest_enemy_in_the_zone(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    set_hp(engine, "hero_b", 5)
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:скимитар:hero_b"


def test_tactics_break_ties_by_smaller_id(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:скимитар:hero_a"


def test_tactics_prefer_melee_when_an_enemy_is_near(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    assert decide(EngineTactics(engine), engine, "goblin_1").startswith("attack:скимитар:")


def test_archer_without_enemy_nearby_shoots(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, goblin_zone="balcony")
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:короткий_лук:hero_a"


def test_archer_shoots_the_weakest_target(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, goblin_zone="balcony")
    set_hp(engine, "hero_b", 5)
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:короткий_лук:hero_b"


def test_melee_only_fighter_closes_the_distance(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")],
        monsters=[mon("guard_1", "guard", "hall")],
    )
    assert decide(EngineTactics(engine), engine, "guard_1") == "move:balcony"


def test_melee_only_fighter_dashes_when_far(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")],
        monsters=[mon("guard_1", "guard", "door")],
    )
    assert decide(EngineTactics(engine), engine, "guard_1") == "dash"


def test_far_guard_reaches_the_hero_in_one_turn(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")],
        monsters=[mon("guard_1", "guard", "door")], rng=Rng(3),
    )
    engine.state.initiative_order = ["guard_1", "hero"]
    engine.step()
    assert part(engine, "guard_1").zone_id == "balcony"


def test_guard_next_door_moves_and_attacks_in_one_turn(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "balcony")],
        monsters=[mon("guard_1", "guard", "hall")], rng=Rng(3),
    )
    engine.state.initiative_order = ["guard_1", "hero"]
    engine.step()
    assert part(engine, "guard_1").zone_id == "balcony"
    assert turn(engine, "guard_1").action is False


def test_tactics_finish_a_downed_hero_when_intent_is_kill(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, intent="kill")
    down_hero(engine, "hero_a")
    move_to(engine, "hero_b", "door")
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:скимитар:hero_a"


def test_tactics_prefer_a_standing_hero_over_a_downed_one(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, intent="kill")
    down_hero(engine, "hero_a")
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:скимитар:hero_b"


def test_tactics_do_not_target_a_dead_hero(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, intent="kill")
    set_hp(engine, "hero_a", 0)
    part(engine, "hero_a").status = "dead"
    engine.heroes["hero_a"].status = "dead"
    assert decide(EngineTactics(engine), engine, "goblin_1") == "attack:скимитар:hero_b"


def test_tactics_do_not_touch_a_downed_hero_without_kill(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg, intent="capture")
    down_hero(engine, "hero_a")
    move_to(engine, "hero_b", "door")
    assert decide(EngineTactics(engine), engine, "goblin_1") != "attack:скимитар:hero_a"


def test_tactics_end_the_turn_after_the_attack(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    turn(engine, "goblin_1").action = False
    assert decide(EngineTactics(engine), engine, "goblin_1") == "end_turn"


def test_tactics_end_the_turn_when_nobody_is_left(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    part(engine, "hero_a").status = "dead"
    part(engine, "hero_b").status = "dead"
    assert decide(EngineTactics(engine), engine, "goblin_1") == "end_turn"


def test_tactics_answer_keep_to_an_intent_question(registry, cfg):
    engine = heroes_vs_goblin(registry, cfg)
    point = DecisionPoint(kind="intent_reconsider", actor="goblin_1", options=["keep"])
    assert EngineTactics(engine).choose([], point) == "keep"


def test_tactics_are_deterministic_and_do_not_roll(registry, cfg):
    rng = ScriptedRng()
    engine = heroes_vs_goblin(registry, cfg, rng=rng)
    tactics = EngineTactics(engine)
    first = decide(tactics, engine, "goblin_1")
    assert decide(tactics, engine, "goblin_1") == first
    assert rng.calls == []


# AutoHeroController

def test_auto_hero_attacks_the_weakest_enemy(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_2", 4)
    assert decide(AutoHeroController(engine), engine, "hero") == "attack:longsword:goblin_2"


def test_auto_hero_breaks_ties_by_smaller_id(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_2", "goblin_warrior", "hall"),
                  mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert decide(AutoHeroController(engine), engine, "hero") == "attack:longsword:goblin_1"


def test_auto_hero_uses_second_wind_when_hurt(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "hero", 6)
    assert decide(AutoHeroController(engine), engine, "hero") == "second_wind"


def test_auto_hero_keeps_second_wind_while_healthy(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "hero", 7)
    assert decide(AutoHeroController(engine), engine, "hero") == "attack:longsword:goblin_1"


def test_auto_hero_attacks_after_second_wind_is_spent(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "hero", 6)
    turn(engine, "hero").bonus = False
    assert decide(AutoHeroController(engine), engine, "hero") == "attack:longsword:goblin_1"


def test_auto_hero_stabilizes_a_dying_ally_in_the_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    down_hero(engine, "ally")
    assert decide(AutoHeroController(engine), engine, "hero") == "stabilize:ally"


def test_auto_hero_caster_prefers_magic_missile(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_2", 3)
    assert decide(AutoHeroController(engine), engine, "wiz") == "cast:magic_missile:1:goblin_2"


def test_auto_hero_caster_falls_back_to_fire_bolt_without_slots(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.heroes["wiz"].creature.resources["spell_slot:1"].current = 0
    assert decide(AutoHeroController(engine), engine, "wiz") == "cast:fire_bolt:0:goblin_1"


def test_auto_hero_walks_to_a_distant_enemy(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert decide(AutoHeroController(engine), engine, "hero") == "move:hall"


def test_auto_hero_ends_the_turn_when_nobody_is_left(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "goblin_1").status = "dead"
    assert decide(AutoHeroController(engine), engine, "hero") == "end_turn"


def test_engine_builds_default_controllers_from_participant_kind(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert isinstance(engine.controllers["hero"], AutoHeroController)
    assert isinstance(engine.controllers["goblin_1"], EngineTactics)


# --- шаг 19: поссорившийся (метка quarreling) бьёт своих ---

def band(registry, cfg, specs):
    # specs: (ref, group) -- безымянные воины-гоблины в зале против героя
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon(ref, "goblin_warrior", "hall", group=group) for ref, group in specs],
    )


def mark_quarrel(engine, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="quarreling", source="hero", kind="flag")
    )


def test_is_quarreling_needs_the_quarreling_flag(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    creature(engine, "goblin_1").active_effects.append(
        ActiveEffect(id="wavering", source="hero", kind="flag")
    )
    assert is_quarreling(engine, "goblin_1") is False


def test_is_quarreling_sees_the_flag(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    mark_quarrel(engine)
    assert (is_quarreling(engine, "goblin_1"), is_quarreling(engine, "goblin_2")) == (True, False)


def test_quarrel_targets_are_the_group_mates(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a"), ("raider_1", "b")])
    assert quarrel_targets(engine, "goblin_1") == ["goblin_2"]


def test_quarrel_targets_exclude_the_quarreler_and_the_heroes(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a"), ("goblin_3", "a")])
    assert quarrel_targets(engine, "goblin_1") == ["goblin_2", "goblin_3"]


def test_quarrel_targets_fall_back_to_the_whole_side(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("raider_1", "b"), ("raider_2", "b")])
    assert quarrel_targets(engine, "goblin_1") == ["raider_1", "raider_2"]


def test_quarrel_targets_skip_the_incapable(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a"), ("raider_1", "b")])
    part(engine, "goblin_2").status = "dead"
    assert quarrel_targets(engine, "goblin_1") == ["raider_1"]


def test_quarrel_targets_skip_a_mate_without_hp(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    set_hp(engine, "goblin_2", 0)
    assert quarrel_targets(engine, "goblin_1") == []


def test_quarrel_targets_are_empty_for_a_lone_monster(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a")])
    assert quarrel_targets(engine, "goblin_1") == []


def test_quarrel_targets_skip_a_creature_of_another_side(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    part(engine, "goblin_2").side = "heroes"
    assert quarrel_targets(engine, "goblin_1") == []


def test_enemies_of_a_quarreling_monster_are_its_targets(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    mark_quarrel(engine)
    assert EngineTactics(engine).enemies("goblin_1", "active") == ["goblin_2"]


def test_a_quarreling_monster_has_no_downed_enemies(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    down_hero(engine, "hero")
    mark_quarrel(engine)
    assert EngineTactics(engine).enemies("goblin_1", "down") == []


def test_enemies_of_a_calm_monster_stay_the_heroes(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    mark_quarrel(engine, "goblin_2")
    tactics = EngineTactics(engine)
    assert (tactics.enemies("goblin_1", "active"), tactics.enemies("goblin_1", "down")) == (
        ["hero"], [],
    )


def test_a_calm_monster_still_finishes_a_downed_hero(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a")])
    down_hero(engine, "hero")
    assert EngineTactics(engine).enemies("goblin_1", "down") == ["hero"]


def test_a_lone_quarreling_monster_ends_the_turn_and_leaves_a_downed_hero(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a")])
    down_hero(engine, "hero")
    mark_quarrel(engine)
    options = engine.available_actions("goblin_1")
    assert EngineTactics(engine).choose_turn(options, "goblin_1") == "end_turn"


def test_a_quarreling_monster_attacks_a_mate(registry, cfg):
    engine = band(registry, cfg, [("goblin_1", "a"), ("goblin_2", "a")])
    mark_quarrel(engine)
    options = engine.available_actions("goblin_1")
    assert EngineTactics(engine).choose_turn(options, "goblin_1") == "attack:скимитар:goblin_2"
