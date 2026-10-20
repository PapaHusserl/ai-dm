# Экономия хода (шаг 16/17): действие, бонусное действие, перемещение, реакция.
#   Participant.turn (TurnState): action / bonus / reaction -- True, пока не потрачены;
#   move -- сколько зон ещё можно пройти (1 за ход, рывок даёт +1, вход в difficult обнуляет).
#   Потраченное исчезает из available_actions; perform вне списка ->
#   Rejected(reason="not_available").
#   Действие: attack, cast, dash, disengage, dodge, help, stabilize, flee, improvise.
#   Бонусное: second_wind, use_item (зелье), disengage_bonus (Nimble Escape).
#   Перемещение (move:<зона>) не тратит действие; рывок (dash) -- действие, добавляет 1 зону.
#   Реакция тратится на провоцированную атаку.
#   Всё восстанавливается в начале собственного хода участника (см. test_engine.py).
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, option_ids, part, set_hp, turn

from ai_dm.rules.inventory import add_item
from ai_dm.rules.results import Rejected


def duel(registry, cfg, rng=None, hero=None, hero_zone="hall", goblin_zone="hall"):
    hero = hero or make_fighter(registry)
    return make_engine(
        registry, cfg, heroes=[(hero, hero_zone)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)],
    )


def only_kinds(engine, ref, prefix):
    return [i for i in option_ids(engine, ref) if i.startswith(prefix)]


def test_attack_spends_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert turn(engine, "hero").action is False


def test_after_attack_no_more_actions(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    ids = option_ids(engine, "hero")
    assert only_kinds(engine, "hero", "attack:") == []
    for gone in ("dash", "disengage", "dodge"):
        assert gone not in ids


def test_second_action_is_rejected(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    result = engine.perform("hero", "dodge")
    assert isinstance(result, Rejected)
    assert result.reason == "not_available"


def test_end_turn_stays_after_the_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    ids = [i for i in option_ids(engine, "hero") if not i.startswith(("equip:", "unequip:"))]
    assert ids[-1] == "end_turn"


def test_potion_spends_the_bonus_action_only(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", 2, cost_cp=0)
    engine = duel(registry, cfg, ScriptedRng(d4=[1, 1]), hero=hero)
    engine.perform("hero", "use_item:potion_of_healing")
    assert turn(engine, "hero").bonus is False
    assert turn(engine, "hero").action is True
    assert "use_item:potion_of_healing" not in option_ids(engine, "hero")


def test_action_and_bonus_action_both_fit_in_one_turn(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    engine = duel(registry, cfg, ScriptedRng(d20=[2], d4=[1, 1]), hero=hero)
    assert not isinstance(engine.perform("hero", "attack:longsword:goblin_1"), Rejected)
    assert not isinstance(engine.perform("hero", "use_item:potion_of_healing"), Rejected)


def test_second_wind_spends_the_bonus_action(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d10=[5]))
    set_hp(engine, "hero", 3)
    engine.perform("hero", "second_wind")
    assert turn(engine, "hero").bonus is False
    assert "second_wind" not in option_ids(engine, "hero")


def test_one_move_per_turn(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    engine.perform("hero", "move:hall")
    assert only_kinds(engine, "hero", "move:") == []
    assert isinstance(engine.perform("hero", "move:balcony"), Rejected)


def test_move_does_not_spend_the_action(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    engine.perform("hero", "move:hall")
    assert turn(engine, "hero").action is True
    assert "dodge" in option_ids(engine, "hero")


def test_move_only_to_adjacent_zones(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    assert only_kinds(engine, "hero", "move:") == ["move:hall"]


def test_dash_spends_the_action_and_gives_a_second_move(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    engine.perform("hero", "dash")
    assert turn(engine, "hero").action is False
    assert turn(engine, "hero").move == 2


def test_dash_gives_exactly_two_zones(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    engine.perform("hero", "dash")
    engine.perform("hero", "move:hall")
    engine.perform("hero", "move:balcony")
    assert only_kinds(engine, "hero", "move:") == []


def test_moving_back_and_forth_still_costs_moves(registry, cfg):
    engine = duel(registry, cfg, hero_zone="door", goblin_zone="balcony")
    engine.perform("hero", "dash")
    engine.perform("hero", "move:hall")
    engine.perform("hero", "move:door")
    assert only_kinds(engine, "hero", "move:") == []


def test_reaction_is_spent_by_an_opportunity_attack(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "move:door")
    assert turn(engine, "goblin_1").reaction is False


def test_reaction_is_spent_only_once_per_round(registry, cfg):
    second = make_fighter(registry, "hero_2")
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), second],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], rng=ScriptedRng(d20=[2]),
    )
    engine.perform("hero", "move:door")
    engine.perform("hero_2", "move:door")
    assert turn(engine, "goblin_1").reaction is False


def test_unused_reaction_stays_available(registry, cfg):
    engine = duel(registry, cfg)
    assert turn(engine, "goblin_1").reaction is True
    assert part(engine, "goblin_1").turn.action is True
