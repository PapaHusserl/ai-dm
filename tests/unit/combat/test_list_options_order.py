# Партия К7д, шаг 0.3: снимок порядка пунктов available.list_options до разгрузки (кабан выносит
# standard_actions / bonus_actions). Ожидания сняты с кода на 187d319: порядок пунктов не меняется.
from combat_kit import make_engine, make_fighter, make_wizard, make_zones, mon, option_ids, turn

HERO_FIGHTER = [
    "attack:longsword:goblin_1", "attack:longsword:goblin_1:nonlethal", "attack:spear:goblin_1",
    "attack:spear:goblin_1:nonlethal", "attack:unarmed:goblin_1",
    "attack:unarmed:goblin_1:nonlethal", "attack:improvised:goblin_1",
    "attack:improvised:goblin_1:nonlethal", "attack:improvised_thrown:goblin_1",
    "attack:improvised_thrown:goblin_2", "disarm:goblin_1:scimitar", "disarm:goblin_1:shortbow",
    "dash", "disengage", "dodge", "parley:goblin_1:intimidation:surrender",
    "parley:goblin_1:persuasion:defect", "parley:goblin_1:deception:flee",
    "parley:goblin_2:intimidation:surrender", "parley:goblin_2:persuasion:defect",
    "parley:goblin_2:deception:flee", "second_wind", "move:door", "move:balcony", "end_turn",
]

GOBLIN_1 = [
    "attack:скимитар:hero", "attack:короткий_лук:hero", "shove:hero:door", "shove:hero:balcony",
    "dash", "disengage", "dodge", "help:goblin_2:hero", "disengage_bonus", "move:door",
    "move:balcony", "end_turn",
]

WIZARD = [
    "attack:quarterstaff:goblin_1", "attack:quarterstaff:goblin_1:nonlethal",
    "attack:unarmed:goblin_1", "attack:unarmed:goblin_1:nonlethal", "attack:improvised:goblin_1",
    "attack:improvised:goblin_1:nonlethal", "attack:improvised_thrown:goblin_1",
    "attack:improvised_thrown:goblin_2", "disarm:goblin_1:scimitar", "disarm:goblin_1:shortbow",
    "cast:fire_bolt:0:goblin_1", "cast:fire_bolt:0:goblin_2", "cast:magic_missile:1:goblin_1",
    "cast:magic_missile:1:goblin_2", "cast:burning_hands:1:door", "cast:burning_hands:1:hall",
    "cast:burning_hands:1:balcony", "dash", "disengage", "dodge",
    "parley:goblin_1:intimidation:surrender", "parley:goblin_1:persuasion:defect",
    "parley:goblin_1:deception:flee", "parley:goblin_2:intimidation:surrender",
    "parley:goblin_2:persuasion:defect", "parley:goblin_2:deception:flee", "move:door",
    "move:balcony", "end_turn",
]

EXIT_HERO = [
    "attack:improvised_thrown:boss", "dash", "disengage", "dodge",
    "parley:boss:intimidation:surrender", "parley:boss:persuasion:defect",
    "parley:boss:deception:flee", "flee", "second_wind", "move:hall", "end_turn",
]

BOSS = [
    "attack:короткий_лук:hero", "dash", "disengage", "dodge", "disengage_bonus", "move:door",
    "move:balcony", "end_turn",
]

HERO_ACTION_SPENT = [
    "second_wind", "move:door", "move:balcony", "end_turn",
]

HERO_BONUS_SPENT = [
    "attack:longsword:goblin_1", "attack:longsword:goblin_1:nonlethal", "attack:spear:goblin_1",
    "attack:spear:goblin_1:nonlethal", "attack:unarmed:goblin_1",
    "attack:unarmed:goblin_1:nonlethal", "attack:improvised:goblin_1",
    "attack:improvised:goblin_1:nonlethal", "attack:improvised_thrown:goblin_1",
    "disarm:goblin_1:scimitar", "disarm:goblin_1:shortbow", "dash", "disengage", "dodge",
    "parley:goblin_1:intimidation:surrender", "parley:goblin_1:persuasion:defect",
    "parley:goblin_1:deception:flee", "move:door", "move:balcony", "end_turn",
]


def two_goblins(registry, cfg, hero):
    return make_engine(
        registry, cfg, heroes=[hero],
        monsters=[
            mon("goblin_1", "goblin_warrior", "hall"), mon("goblin_2", "goblin_warrior", "balcony"),
        ],
    )


def visible_ids(engine, ref):
    # видимые пункты: до end_turn включительно; после него идут скрытые equip/unequip
    ids = option_ids(engine, ref)
    return ids[: ids.index("end_turn") + 1]


def test_hidden_swap_options_come_after_end_turn(registry, cfg):
    ids = option_ids(two_goblins(registry, cfg, make_fighter(registry)), "hero")
    tail = ids[ids.index("end_turn") + 1:]
    assert tail
    assert all(i.startswith(("equip:", "unequip:")) for i in tail)


def test_fighter_order(registry, cfg):
    engine = two_goblins(registry, cfg, make_fighter(registry))
    assert visible_ids(engine, "hero") == HERO_FIGHTER


def test_goblin_order(registry, cfg):
    assert option_ids(two_goblins(registry, cfg, make_fighter(registry)), "goblin_1") == GOBLIN_1


def test_wizard_order(registry, cfg):
    assert visible_ids(two_goblins(registry, cfg, make_wizard(registry)), "wiz") == WIZARD


def test_hero_in_an_exit_zone_order(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=make_zones(door_exit=True),
        hero_zone="door", monsters=[mon("boss", "goblin_boss", "hall")],
    )
    assert visible_ids(engine, "hero") == EXIT_HERO
    assert option_ids(engine, "boss") == BOSS


def solo(registry, cfg):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_order_after_the_action_is_spent(registry, cfg):
    engine = solo(registry, cfg)
    turn(engine, "hero").action = False
    assert visible_ids(engine, "hero") == HERO_ACTION_SPENT


def test_order_after_the_bonus_action_is_spent(registry, cfg):
    engine = solo(registry, cfg)
    turn(engine, "hero").bonus = False
    assert visible_ids(engine, "hero") == HERO_BONUS_SPENT
