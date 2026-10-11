# Список доступных действий (шаг 18, A1): CombatEngine.available_actions(ref) -> list[ActionOption]
#   ai_dm.combat.available.ActionOption(id: str, kind: str, label: str, params: dict) -- Pydantic;
#   kind: attack | cast | move | dash | disengage | dodge | help | second_wind | use_item |
#   stabilize | flee | end_turn. Формат id -- в шапке combat_kit.py.
#   Стабильность: id детерминированы (тот же вызов -- тот же список в том же порядке, у
#   одинаково построенного боя -- то же самое), уникальны, end_turn всегда последний.
#   Участник без хода (status down / dead / fled) -- пустой список; недееспособный
#   (incapacitated, в т.ч. вложенное: stunned, paralyzed, unconscious) -- только end_turn.
#   nonlethal -- только ближний бой. flee -- только в зоне с exit=True.
import pytest
from combat_kit import (
    creature,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
)

from ai_dm.combat.available import ActionOption
from ai_dm.state.creature import AppliedCondition


def duel(registry, cfg, **kwargs):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "balcony")],
        **kwargs,
    )


def test_options_are_action_options(registry, cfg):
    options = duel(registry, cfg).available_actions("hero")
    assert options
    assert all(isinstance(o, ActionOption) for o in options)


def test_option_has_id_kind_label_and_params(registry, cfg):
    option = duel(registry, cfg).available_actions("hero")[0]
    assert isinstance(option.id, str) and option.id
    assert isinstance(option.kind, str) and option.kind
    assert isinstance(option.label, str) and option.label
    assert isinstance(option.params, dict)


def test_ids_are_unique(registry, cfg):
    ids = option_ids(duel(registry, cfg), "hero")
    assert len(ids) == len(set(ids))


def test_same_call_gives_the_same_list(registry, cfg):
    engine = duel(registry, cfg)
    assert option_ids(engine, "hero") == option_ids(engine, "hero")


def test_equal_fights_give_equal_lists(registry, cfg):
    first = option_ids(duel(registry, cfg), "goblin_1")
    assert first == option_ids(duel(registry, cfg), "goblin_1")


def test_end_turn_is_always_last(registry, cfg):
    engine = duel(registry, cfg)
    for ref in ("hero", "goblin_1", "goblin_2"):
        assert option_ids(engine, ref)[-1] == "end_turn"


def test_attack_option_kind_and_params(registry, cfg):
    engine = duel(registry, cfg)
    options = engine.available_actions("hero")
    option = next(o for o in options if o.id == "attack:longsword:goblin_1")
    assert option.kind == "attack"
    assert option.params["target"] == "goblin_1"
    assert option.params["weapon"] == "longsword"


def test_hero_gets_standard_actions(registry, cfg):
    ids = option_ids(duel(registry, cfg), "hero")
    for expected in ("dash", "disengage", "dodge", "second_wind", "move:door", "move:balcony"):
        assert expected in ids


def test_far_enemy_is_not_a_melee_target(registry, cfg):
    ids = option_ids(duel(registry, cfg), "hero")
    assert "attack:longsword:goblin_2" not in ids


def test_nonlethal_variant_exists_for_melee(registry, cfg):
    assert "attack:longsword:goblin_1:nonlethal" in option_ids(duel(registry, cfg), "hero")


def test_nonlethal_variant_is_not_offered_for_ranged_attacks(registry, cfg):
    ids = option_ids(duel(registry, cfg), "goblin_2")
    assert not [i for i in ids if i.startswith("attack:короткий_лук") and i.endswith(":nonlethal")]


def test_help_is_offered_against_enemy_in_the_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "ally")],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert "help:ally:goblin_1" in option_ids(engine, "hero")


def test_flee_only_in_an_exit_zone(registry, cfg):
    plain = duel(registry, cfg)
    assert "flee" not in option_ids(plain, "hero")
    exit_engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=make_zones(door_exit=True),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert "flee" in option_ids(exit_engine, "hero")


@pytest.mark.parametrize("status", ["down", "dead", "fled"])
def test_participant_out_of_the_fight_has_no_options(registry, cfg, status):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").status = status
    assert engine.available_actions("goblin_1") == []


@pytest.mark.parametrize("condition", ["incapacitated", "stunned", "paralyzed", "unconscious"])
def test_incapacitated_participant_can_only_end_the_turn(registry, cfg, condition):
    engine = duel(registry, cfg)
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id=condition))
    assert option_ids(engine, "goblin_1") == ["end_turn"]
