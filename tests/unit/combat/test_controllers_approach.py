# Партия К7д, шаг 0.5: EngineTactics.approach(options, ref) -- хвост сближения из choose_turn.
#   Нет целей -> "end_turn"; цель через >= 2 зоны и dash доступен -> "dash"; цель в соседней зоне
#   (или дальше, но без dash) -> шаг move:<зона> к ней;
#   цель в своей зоне или шагать некуда -> "end_turn".
from combat_kit import make_engine, make_fighter, mon, part, set_hp, turn

from ai_dm.combat.controllers import EngineTactics


def guard_vs_hero(registry, cfg, hero_zone, guard_zone="door"):
    return make_engine(
        registry, cfg, heroes=[(make_fighter(registry), hero_zone)],
        monsters=[mon("guard_1", "guard", guard_zone)],
    )


def approach(engine, ref="guard_1"):
    return EngineTactics(engine).approach(engine.available_actions(ref), ref)


def test_far_target_gives_dash(registry, cfg):
    assert approach(guard_vs_hero(registry, cfg, "balcony")) == "dash"


def test_far_target_without_the_action_gives_a_step(registry, cfg):
    engine = guard_vs_hero(registry, cfg, "balcony")
    turn(engine, "guard_1").action = False
    assert approach(engine) == "move:hall"


def test_neighbour_target_gives_a_step(registry, cfg):
    assert approach(guard_vs_hero(registry, cfg, "balcony", "hall")) == "move:balcony"


def test_target_in_the_own_zone_ends_the_turn(registry, cfg):
    assert approach(guard_vs_hero(registry, cfg, "hall", "hall")) == "end_turn"


def test_no_enemies_ends_the_turn(registry, cfg):
    engine = guard_vs_hero(registry, cfg, "balcony")
    part(engine, "hero").status = "dead"
    set_hp(engine, "hero", 0)
    assert approach(engine) == "end_turn"


def test_no_move_option_ends_the_turn(registry, cfg):
    engine = guard_vs_hero(registry, cfg, "balcony", "hall")
    turn(engine, "guard_1").move = 0
    assert approach(engine) == "end_turn"
