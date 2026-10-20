# Список доступных действий (шаг 18, A1): CombatEngine.available_actions(ref) -> list[ActionOption]
#   ai_dm.combat.available.ActionOption(id: str, kind: str, label: str, params: dict) -- Pydantic;
#   kind: attack | cast | move | dash | disengage | dodge | help | second_wind | use_item |
#   stabilize | flee | end_turn. Формат id -- в шапке combat_kit.py.
#   Стабильность: id детерминированы (тот же вызов -- тот же список в том же порядке, у
#   одинаково построенного боя -- то же самое), уникальны, end_turn всегда последний.
#   Участник без хода (status down / dead / fled) -- пустой список; недееспособный
#   (incapacitated, в т.ч. вложенное: stunned, paralyzed, unconscious) -- только end_turn.
#   nonlethal -- только ближний бой. flee -- только в зоне с exit=True.
#   Шаг 96а: после end_turn идут скрытые варианты смены экипировки героя (kind equip / unequip,
#   id "equip:<предмет>[:off_hand]" / "unequip:<слот>"): оружие -- free (свободное взаимодействие)
#   или action, щит -- action, доспех -- нет вовсе; perform тратит ресурс по cost варианта.
import pytest
from combat_kit import (
    ScriptedRng,
    creature,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    turn,
)

from ai_dm.combat.available import ActionOption
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.rules.results import Rejected
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
    # видимые варианты; скрытые equip/unequip идут после end_turn
    for ref in ("hero", "goblin_1", "goblin_2"):
        ids = [i for i in option_ids(engine, ref) if not i.startswith(("equip:", "unequip:"))]
        assert ids[-1] == "end_turn"


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


# смена экипировки (шаг 96а): скрытые варианты equip / unequip

def swap_duel(registry, cfg, hero=None, rng=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def swaps(engine, ref="hero"):
    return {o.id: o for o in engine.available_actions(ref) if o.kind in ("equip", "unequip")}


def bare_hero(registry, *items):
    # воин без щита и оружия в руках; items -- в инвентаре
    hero = make_fighter(registry)
    hero.equipped.shield = None
    hero.equipped.main_hand = None
    for item in items:
        add_item(hero, item, cost_cp=0)
    return hero


def test_fighter_swap_options_follow_end_turn_in_fixed_order(registry, cfg):
    ids = option_ids(swap_duel(registry, cfg), "hero")
    assert ids[ids.index("end_turn") + 1:] == ["equip:spear", "unequip:main_hand", "unequip:shield"]


def test_swap_weapon_costs_the_free_interaction(registry, cfg):
    options = swaps(swap_duel(registry, cfg))
    assert options["equip:spear"].cost == "free"
    assert options["unequip:main_hand"].cost == "free"


def test_swap_shield_costs_the_action(registry, cfg):
    assert swaps(swap_duel(registry, cfg))["unequip:shield"].cost == "action"


def test_swap_params_carry_item_and_slot(registry, cfg):
    options = swaps(swap_duel(registry, cfg))
    assert options["equip:spear"].params == {"item": "spear", "slot": "main_hand"}
    assert options["unequip:shield"].params == {"slot": "shield"}


def test_swap_weapon_costs_the_action_after_the_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg)
    turn(engine, "hero").free_interaction = False
    options = swaps(engine)
    assert options["equip:spear"].cost == "action"
    assert options["unequip:main_hand"].cost == "action"


def test_no_swap_without_action_and_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg)
    turn(engine, "hero").free_interaction = False
    turn(engine, "hero").action = False
    assert swaps(engine) == {}


def test_weapon_swap_stays_free_without_the_action_but_shield_is_gone(registry, cfg):
    engine = swap_duel(registry, cfg)
    turn(engine, "hero").action = False
    options = swaps(engine)
    assert options["equip:spear"].cost == "free"
    assert "unequip:shield" not in options


def test_shield_swap_needs_the_action_even_with_the_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg, hero=bare_hero(registry, "shield"))
    assert swaps(engine)["equip:shield"].cost == "action"
    turn(engine, "hero").action = False
    assert "equip:shield" not in swaps(engine)


def test_equip_shield_option_label_and_params(registry, cfg):
    option = swaps(swap_duel(registry, cfg, hero=bare_hero(registry, "shield")))["equip:shield"]
    assert option.params == {"item": "shield", "slot": "shield"}
    assert registry.get("armor", "shield").name in option.label


def test_no_equip_shield_option_when_it_is_already_worn(registry, cfg):
    assert "equip:shield" not in swaps(swap_duel(registry, cfg))


def test_armor_is_never_offered_in_combat(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "leather_armor", cost_cp=0)
    options = swaps(swap_duel(registry, cfg, hero=hero))
    assert "unequip:armor" not in options
    assert "equip:leather_armor" not in options
    assert "equip:chain_mail" not in options


def test_equipped_weapon_is_not_offered_for_the_same_slot(registry, cfg):
    assert "equip:longsword" not in swaps(swap_duel(registry, cfg))


def test_light_weapon_gets_main_and_off_hand_variants_without_shield(registry, cfg):
    hero = bare_hero(registry, "dagger")
    options = swaps(swap_duel(registry, cfg, hero=hero))
    assert options["equip:dagger"].params == {"item": "dagger", "slot": "main_hand"}
    assert options["equip:dagger:off_hand"].params == {"item": "dagger", "slot": "off_hand"}
    assert options["equip:dagger:off_hand"].cost == "free"


def test_off_hand_variant_is_absent_with_a_shield(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "dagger", cost_cp=0)
    options = swaps(swap_duel(registry, cfg, hero=hero))
    assert "equip:dagger" in options
    assert "equip:dagger:off_hand" not in options


def test_single_item_in_main_hand_is_not_offered_for_the_off_hand(registry, cfg):
    hero = bare_hero(registry, "dagger")
    hero.equipped.main_hand = "dagger"
    assert "equip:dagger:off_hand" not in swaps(swap_duel(registry, cfg, hero=hero))


def test_second_copy_is_offered_for_the_off_hand(registry, cfg):
    hero = bare_hero(registry, "dagger", "dagger")
    hero.equipped.main_hand = "dagger"
    assert "equip:dagger:off_hand" in swaps(swap_duel(registry, cfg, hero=hero))


def test_off_hand_weapon_gets_an_unequip_variant(registry, cfg):
    hero = bare_hero(registry, "dagger")
    hero.equipped.off_hand = "dagger"
    option = swaps(swap_duel(registry, cfg, hero=hero))["unequip:off_hand"]
    assert option.params == {"slot": "off_hand"}
    assert option.cost == "free"


def test_two_handed_weapon_is_not_offered_while_the_shield_is_worn(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "greatsword", cost_cp=0)
    assert "equip:greatsword" not in swaps(swap_duel(registry, cfg, hero=hero))


def test_two_handed_weapon_is_offered_with_free_hands(registry, cfg):
    hero = bare_hero(registry, "greatsword")
    assert "equip:greatsword" in swaps(swap_duel(registry, cfg, hero=hero))


def test_consumables_get_no_swap_options(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    assert not any("potion" in i for i in swaps(swap_duel(registry, cfg, hero=hero)))


def test_monsters_get_no_swap_options(registry, cfg):
    assert swaps(swap_duel(registry, cfg), "goblin_1") == {}


def test_incapacitated_hero_gets_no_swap_options(registry, cfg):
    engine = swap_duel(registry, cfg)
    creature(engine, "hero").conditions.append(AppliedCondition(id="incapacitated"))
    assert option_ids(engine, "hero") == ["end_turn"]


def test_swap_does_not_shift_the_visible_options(registry, cfg):
    ids = option_ids(swap_duel(registry, cfg), "hero")
    visible = ids[: ids.index("end_turn") + 1]
    assert not any(i.startswith(("equip:", "unequip:")) for i in visible)


def test_equip_free_swap_takes_the_weapon_and_keeps_the_action(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "equip:spear")
    assert engine.heroes["hero"].equipped.main_hand == "spear"
    assert turn(engine, "hero").free_interaction is False
    assert turn(engine, "hero").action is True


def test_equip_keeps_the_old_weapon_in_the_inventory(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "equip:spear")
    assert count_item(engine.heroes["hero"], "longsword") == 1


def test_second_swap_in_the_turn_spends_the_action(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "equip:spear")
    assert swaps(engine)["equip:longsword"].cost == "action"
    engine.perform("hero", "equip:longsword")
    assert engine.heroes["hero"].equipped.main_hand == "longsword"
    assert turn(engine, "hero").action is False


def test_swap_after_the_action_is_gone_is_rejected(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "equip:spear")
    turn(engine, "hero").action = False
    result = engine.perform("hero", "equip:longsword")
    assert isinstance(result, Rejected)
    assert result.reason == "not_available"
    assert engine.heroes["hero"].equipped.main_hand == "spear"


def test_unequip_shield_spends_the_action_not_the_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "unequip:shield")
    assert engine.heroes["hero"].equipped.shield is None
    assert turn(engine, "hero").action is False
    assert turn(engine, "hero").free_interaction is True


def test_equip_shield_in_combat_puts_it_on_and_spends_the_action(registry, cfg):
    hero = bare_hero(registry, "shield")
    engine = swap_duel(registry, cfg, hero=hero)
    engine.perform("hero", "equip:shield")
    assert hero.equipped.shield == "shield"
    assert turn(engine, "hero").action is False


def test_unequip_weapon_is_free_and_leaves_hand_empty(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "unequip:main_hand")
    assert engine.heroes["hero"].equipped.main_hand is None
    assert turn(engine, "hero").free_interaction is False
    assert turn(engine, "hero").action is True
    assert count_item(engine.heroes["hero"], "longsword") == 1


def test_equip_off_hand_variant_fills_the_left_hand(registry, cfg):
    hero = bare_hero(registry, "dagger")
    engine = swap_duel(registry, cfg, hero=hero)
    engine.perform("hero", "equip:dagger:off_hand")
    assert hero.equipped.off_hand == "dagger"
    assert hero.equipped.main_hand is None


def test_swap_writes_a_log_line_with_the_item_name(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "equip:spear")
    assert any(registry.get("weapon", "spear").name in line for line in engine.state.log)


def test_unequip_shield_log_names_the_shield(registry, cfg):
    engine = swap_duel(registry, cfg)
    engine.perform("hero", "unequip:shield")
    assert any(registry.get("armor", "shield").name in line for line in engine.state.log)


def test_equip_problem_is_none_when_equip_would_pass(registry):
    from ai_dm.combat.available import equip_ok, equip_problem

    hero = make_fighter(registry)
    assert equip_problem(hero, "spear", registry, "main_hand") is None
    assert equip_ok(hero, "spear", registry, "main_hand") is True


def test_equip_problem_returns_the_error_and_keeps_the_slots(registry):
    from ai_dm.combat.available import equip_ok, equip_problem
    from ai_dm.rules.inventory import InventoryError

    hero = bare_hero(registry, "dagger")
    hero.equipped.main_hand = "dagger"
    before = hero.equipped.model_copy()
    problem = equip_problem(hero, "dagger", registry, "off_hand")
    assert isinstance(problem, InventoryError)
    assert "dagger" in str(problem)
    assert equip_ok(hero, "dagger", registry, "off_hand") is False
    assert hero.equipped == before


def test_equip_problem_does_not_apply_a_passing_equip(registry):
    from ai_dm.combat.available import equip_problem

    hero = make_fighter(registry)
    equip_problem(hero, "spear", registry, "main_hand")
    assert hero.equipped.main_hand == "longsword"


def test_equip_slots_for_a_weapon_are_both_hands():
    from types import SimpleNamespace

    from ai_dm.combat.available import equip_slots

    found = ("weapon", SimpleNamespace(category="martial"))
    assert [s for s, _ in equip_slots(found)] == ["main_hand", "off_hand"]


def test_equip_slots_for_a_shield_is_the_shield_slot():
    from types import SimpleNamespace

    from ai_dm.combat.available import equip_slots

    found = ("armor", SimpleNamespace(category="shield"))
    assert [s for s, _ in equip_slots(found)] == ["shield"]


def test_equip_slots_for_body_armor_is_empty():
    from types import SimpleNamespace

    from ai_dm.combat.available import equip_slots

    assert equip_slots(("armor", SimpleNamespace(category="heavy"))) == ()


def test_equip_candidates_respect_the_slot_costs(registry, cfg):
    from ai_dm.combat.available import equip_candidates

    engine = swap_duel(registry, cfg)
    hero = engine.heroes["hero"]
    costs = {"main_hand": "free", "off_hand": None, "shield": "action"}
    found = list(equip_candidates(engine, hero, costs))
    assert [(i, s) for i, s, _ in found] == [("spear", "main_hand")]
    assert found[0][2] == f"Взять в руку: {registry.get('weapon', 'spear').name}"


def test_equip_candidates_without_any_cost_are_empty(registry, cfg):
    from ai_dm.combat.available import equip_candidates

    engine = swap_duel(registry, cfg)
    costs = {"main_hand": None, "off_hand": None, "shield": None}
    assert list(equip_candidates(engine, engine.heroes["hero"], costs)) == []


def test_equip_candidates_skip_what_is_already_in_the_slot(registry, cfg):
    from ai_dm.combat.available import equip_candidates

    engine = swap_duel(registry, cfg)
    costs = {"main_hand": "free", "off_hand": "free", "shield": "action"}
    items = [i for i, _, _ in equip_candidates(engine, engine.heroes["hero"], costs)]
    assert "longsword" not in items
    assert "shield" not in items


def test_swap_returns_no_events(registry, cfg):
    assert swap_duel(registry, cfg).perform("hero", "equip:spear") == []


# регресс: достать оружие при атаке и обезоруживании -- часть действия, взаимодействие цело

def test_attack_with_another_weapon_keeps_the_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg, rng=ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:spear:goblin_1")
    assert engine.heroes["hero"].equipped.main_hand == "spear"
    assert turn(engine, "hero").action is False
    assert turn(engine, "hero").free_interaction is True


def test_disarm_keeps_the_free_interaction(registry, cfg):
    engine = swap_duel(registry, cfg, rng=ScriptedRng(d20=[15, 15, 2]))
    engine.perform("hero", "disarm:goblin_1:scimitar")
    assert turn(engine, "hero").action is False
    assert turn(engine, "hero").free_interaction is True


def test_swap_after_an_attack_is_still_free(registry, cfg):
    engine = swap_duel(registry, cfg, rng=ScriptedRng(d20=[2]))
    engine.perform("hero", "attack:longsword:goblin_1")
    assert swaps(engine)["equip:spear"].cost == "free"


# подписи и журнал смены экипировки (добивка мутантов шага 96а)

def test_unequip_shield_label(registry, cfg):
    option = swaps(swap_duel(registry, cfg))["unequip:shield"]
    assert option.label == f"Снять щит: {registry.get('armor', 'shield').name}"


def test_unequip_weapon_label(registry, cfg):
    option = swaps(swap_duel(registry, cfg))["unequip:main_hand"]
    assert option.label == f"Убрать оружие: {registry.get('weapon', 'longsword').name}"


def test_equip_main_hand_label(registry, cfg):
    option = swaps(swap_duel(registry, cfg))["equip:spear"]
    assert option.label == f"Взять в руку: {registry.get('weapon', 'spear').name}"


def test_equip_off_hand_label(registry, cfg):
    option = swaps(swap_duel(registry, cfg, hero=bare_hero(registry, "dagger")))
    assert option["equip:dagger:off_hand"].label == (
        f"В левую руку: {registry.get('weapon', 'dagger').name}"
    )


def test_equip_shield_label_text(registry, cfg):
    option = swaps(swap_duel(registry, cfg, hero=bare_hero(registry, "shield")))["equip:shield"]
    assert option.label == f"Надеть щит: {registry.get('armor', 'shield').name}"


def test_equip_slots_labels():
    from types import SimpleNamespace

    from ai_dm.combat.available import equip_slots

    weapon = equip_slots(("weapon", SimpleNamespace(category="martial")))
    assert weapon == (("main_hand", "Взять в руку"), ("off_hand", "В левую руку"))
    assert equip_slots(("armor", SimpleNamespace(category="shield"))) == (
        ("shield", "Надеть щит"),
    )


def test_inventory_entry_unknown_to_the_registry_is_skipped(registry, cfg):
    hero = make_fighter(registry)
    hero.inventory.append(hero.inventory[0].model_copy(update={"item_id": "no_such_thing"}))
    assert "equip:no_such_thing" not in swaps(swap_duel(registry, cfg, hero=hero))


def swap_log(registry, cfg, option_id, hero=None):
    engine = swap_duel(registry, cfg, hero=hero)
    engine.perform("hero", option_id)
    return engine.name("hero"), engine.state.log[-1]


def test_swap_log_unequip_shield_verb(registry, cfg):
    name, line = swap_log(registry, cfg, "unequip:shield")
    assert line == f"{name} снимает: {registry.get('armor', 'shield').name}"


def test_swap_log_equip_shield_verb(registry, cfg):
    name, line = swap_log(registry, cfg, "equip:shield", bare_hero(registry, "shield"))
    assert line == f"{name} надевает: {registry.get('armor', 'shield').name}"


def test_swap_log_unequip_weapon_verb(registry, cfg):
    name, line = swap_log(registry, cfg, "unequip:main_hand")
    assert line == f"{name} убирает: {registry.get('weapon', 'longsword').name}"


def test_swap_log_equip_weapon_verb(registry, cfg):
    name, line = swap_log(registry, cfg, "equip:spear")
    assert line == f"{name} берёт: {registry.get('weapon', 'spear').name}"
