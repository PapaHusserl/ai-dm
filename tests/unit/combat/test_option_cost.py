# Ресурс пункта меню (stage3-live-combat-menu, M3): ActionOption.cost --
# action | bonus | move | free | reaction. Тот же признак уходит модели в combat.options.
from combat_kit import make_engine, make_fighter, mon

COSTS = {"action", "bonus", "move", "free", "reaction"}


def duel(registry, cfg):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def options_of(registry, cfg):
    return duel(registry, cfg).available_actions("hero")


def test_every_option_has_a_known_cost(registry, cfg):
    for option in options_of(registry, cfg):
        assert option.cost in COSTS


def test_attack_costs_action(registry, cfg):
    attacks = [o for o in options_of(registry, cfg) if o.kind == "attack"]
    assert attacks
    assert all(o.cost == "action" for o in attacks)


def test_move_costs_move(registry, cfg):
    moves = [o for o in options_of(registry, cfg) if o.kind == "move"]
    assert moves
    assert all(o.cost == "move" for o in moves)


def test_dodge_costs_action(registry, cfg):
    dodge = [o for o in options_of(registry, cfg) if o.kind == "dodge"]
    assert dodge
    assert dodge[0].cost == "action"


def test_end_turn_is_free(registry, cfg):
    end = next(o for o in options_of(registry, cfg) if o.kind == "end_turn")
    assert end.cost == "free"


def test_second_wind_costs_bonus(registry, cfg):
    wind = [o for o in options_of(registry, cfg) if o.kind == "second_wind"]
    assert wind
    assert wind[0].cost == "bonus"
