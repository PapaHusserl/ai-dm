# Подбор оружия с земли (docs/plan-combat-disarm.md, п. 4; В5).
#   state.ground_items: list[GroundItem(item_id, zone_id, owner_ref=None, qty=1)];
#   TurnState.free_interaction: bool = True -- одно бесплатное взаимодействие с предметом за ход.
#   Опция: kind "pickup" (id "pickup:<индекс в ground_items>"), предмет в зоне участника.
#     Цена: свободное взаимодействие, если не потрачено (cost "free", действие остаётся);
#     иначе действие. Нет ни того ни другого -- опции нет.
#   Герой: add_item + equip в main_hand, если рука свободна; иначе только в инвентарь.
#     GroundItem удаляется.
#   Монстр: поднимает только своё оружие (weapon_id == флаг disarmed) -- флаг снимается и атака
#     возвращается; чужое оружие не берёт.
#   К7х: оружие, которого нет в заданном equipment участника (В10), монстр тоже считает потерянным:
#     берёт
#     его с земли (can_pick), и оно возвращается в equipment.weapons; флага disarmed в этом случае
#       нет.
#   ИИ: обезоруженный монстр рядом со своим оружием подбирает его (EngineTactics); авто-герой
#     с пустой рукой подбирает своё (AutoHeroController).
from combat_kit import ScriptedRng, creature, make_engine, make_fighter, mon, part, turn

from ai_dm.rules.inventory import count_item, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.creature import ActiveEffect, Equipment


def duel(registry, cfg, rng=None, hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def drop(engine, item_id, zone="hall", owner=None):
    engine.state.ground_items.append(
        GroundItem(item_id=item_id, zone_id=zone, owner_ref=owner, cost_cp=0)
    )


def pickups(engine, ref="hero"):
    return [o for o in engine.available_actions(ref) if o.kind == "pickup"]


def take_flag(engine, weapon_id, ref="goblin_1"):
    creature(engine, ref).active_effects.append(
        ActiveEffect(id="disarmed", source="hero", kind="flag", params={"weapon_id": weapon_id})
    )


def flags(engine, ref="goblin_1"):
    return [e.params for e in creature(engine, ref).active_effects if e.id == "disarmed"]


def attack_ids(engine, ref):
    return [o.id for o in engine.available_actions(ref) if o.kind == "attack"]


# --- опции героя ---

def test_ground_item_in_the_hero_zone_can_be_picked_up(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    assert len(pickups(engine)) == 1


def test_ground_item_in_another_zone_cannot_be_picked_up(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar", zone="door")
    assert pickups(engine) == []


def test_no_pickup_option_without_ground_items(registry, cfg):
    assert pickups(duel(registry, cfg)) == []


def test_each_ground_item_has_its_own_option(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    drop(engine, "shortbow")
    assert len({o.id for o in pickups(engine)}) == 2


def test_pickup_option_id_carries_the_index(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar", zone="door")
    drop(engine, "shortbow")
    assert [o.id for o in pickups(engine)] == ["pickup:1"]


def test_first_pickup_is_a_free_interaction(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    assert pickups(engine)[0].cost == "free"


def test_turn_starts_with_a_free_interaction(registry, cfg):
    engine = duel(registry, cfg)
    assert turn(engine, "hero").free_interaction is True


def test_first_pickup_keeps_the_action(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    engine.perform("hero", pickups(engine)[0].id)
    assert turn(engine, "hero").action is True
    assert turn(engine, "hero").free_interaction is False


def test_second_pickup_costs_the_action(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    drop(engine, "shortbow")
    engine.perform("hero", pickups(engine)[0].id)
    option = pickups(engine)[0]
    assert option.cost == "action"
    engine.perform("hero", option.id)
    assert turn(engine, "hero").action is False


def test_no_pickup_without_the_action_and_the_free_interaction(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    turn(engine, "hero").action = False
    turn(engine, "hero").free_interaction = False
    assert pickups(engine) == []


def test_free_interaction_works_without_the_action(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    turn(engine, "hero").action = False
    assert [o.cost for o in pickups(engine)] == ["free"]


def test_free_interaction_comes_back_next_turn(registry, cfg):
    engine = duel(registry, cfg)
    turn(engine, "hero").free_interaction = False
    engine.start_turn("hero")
    assert turn(engine, "hero").free_interaction is True


def test_new_turn_state_defaults_to_a_free_interaction():
    from ai_dm.state.combat import TurnState

    assert TurnState().free_interaction is True


# --- результат подбора героем ---

def test_hero_picks_the_weapon_into_the_inventory(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero=hero)
    drop(engine, "scimitar")
    engine.perform("hero", "pickup:0")
    assert count_item(hero, "scimitar") == 1


def test_picked_up_item_leaves_the_ground(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    engine.perform("hero", "pickup:0")
    assert engine.state.ground_items == []


def test_hero_with_an_empty_hand_takes_the_weapon_in_hand(registry, cfg):
    hero = make_fighter(registry)
    remove_item(hero, "longsword")
    engine = duel(registry, cfg, hero=hero)
    drop(engine, "longsword", owner="hero")
    engine.perform("hero", "pickup:0")
    assert hero.equipped.main_hand == "longsword"


def test_hero_with_a_weapon_in_hand_keeps_it(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero=hero)
    drop(engine, "scimitar")
    engine.perform("hero", "pickup:0")
    assert hero.equipped.main_hand == "longsword"


def test_pickup_is_logged(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar")
    engine.perform("hero", "pickup:0")
    assert any("подбирает" in line for line in engine.state.log)


# --- монстр ---

def test_monster_can_pick_up_its_own_weapon(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    assert len(pickups(engine, "goblin_1")) == 1


def test_monster_picking_up_its_weapon_removes_the_flag(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert flags(engine) == []
    assert engine.state.ground_items == []


def test_monster_gets_its_attack_back(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    assert "attack:скимитар:hero" not in attack_ids(engine, "goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert "attack:скимитар:hero" in attack_ids(engine, "goblin_1")


def test_monster_keeps_the_other_flag_when_picking_up_one_weapon(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    take_flag(engine, "shortbow")
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert flags(engine) == [{"weapon_id": "shortbow"}]


def test_monster_takes_the_weapon_of_its_kind_even_if_it_was_not_the_owner(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="hero")
    assert len(pickups(engine, "goblin_1")) == 1


def test_monster_does_not_pick_up_a_foreign_weapon(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "longsword", owner="hero")
    assert pickups(engine, "goblin_1") == []


def test_armed_monster_does_not_pick_up_anything(registry, cfg):
    engine = duel(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    assert pickups(engine, "goblin_1") == []


def test_monster_does_not_pick_up_from_another_zone(registry, cfg):
    engine = duel(registry, cfg)
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", zone="door", owner="goblin_1")
    assert pickups(engine, "goblin_1") == []


# --- ИИ ---

def test_disarmed_monster_picks_up_its_weapon_on_its_turn(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2, 2], d6=[1]))
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.state.turn_index = 1
    engine.step()
    assert flags(engine) == []
    assert engine.state.ground_items == []


def test_disarmed_monster_attacks_with_the_picked_up_weapon(registry, cfg):
    # 15 + 4 = 19 попадает в КД 19; 1d6 + 2 = 5
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    take_flag(engine, "scimitar")
    drop(engine, "scimitar", owner="goblin_1")
    engine.state.turn_index = 1
    engine.step()
    assert engine.heroes["hero"].creature.hp_current == 12 - 5


def test_monster_without_its_weapon_nearby_does_not_pick_up(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=[2, 2], d6=[1]))
    take_flag(engine, "scimitar")
    drop(engine, "longsword", owner="hero")
    engine.state.turn_index = 1
    engine.step()
    assert len(engine.state.ground_items) == 1
    assert part(engine, "goblin_1").zone_id == "hall"


def test_auto_hero_with_an_empty_hand_picks_up_its_weapon(registry, cfg):
    hero = make_fighter(registry)
    remove_item(hero, "longsword")
    engine = duel(registry, cfg, ScriptedRng(d20=[2], d8=[1]), hero=hero)
    drop(engine, "longsword", owner="hero")
    engine.step()
    assert hero.equipped.main_hand == "longsword"
    assert engine.state.ground_items == []


# --- К7х: потеряно по equipment ---

def test_goblin_picks_up_the_weapon_lost_by_equipment(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["shortbow"])
    drop(engine, "scimitar", owner="goblin_1")
    assert len(pickups(engine, "goblin_1")) == 1
    engine.perform("goblin_1", "pickup:0")
    assert part(engine, "goblin_1").equipment.weapons == ["shortbow", "scimitar"]
    assert flags(engine) == []


def test_goblin_does_not_pick_up_a_weapon_still_in_its_equipment(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["scimitar"])
    drop(engine, "scimitar", owner="goblin_1")
    assert pickups(engine, "goblin_1") == []


def test_goblin_with_equipment_still_does_not_take_a_foreign_weapon(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["scimitar"])
    drop(engine, "longsword")
    assert pickups(engine, "goblin_1") == []


def test_pickup_by_equipment_returns_the_attack(registry, cfg):
    engine = duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["shortbow"])
    drop(engine, "scimitar", owner="goblin_1")
    assert "attack:скимитар:hero" not in attack_ids(engine, "goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert "attack:скимитар:hero" in attack_ids(engine, "goblin_1")


def test_hero_pickup_keeps_the_quality_and_the_price_of_the_item(registry, cfg):
    hero = make_fighter(registry)
    remove_item(hero, "longsword")
    engine = duel(registry, cfg, hero=hero)
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="goblin_1", cost_cp=250,
                   quality="junk")
    )
    engine.perform("hero", "pickup:0")
    entry = [e for e in hero.inventory if e.item_id == "scimitar"][0]
    assert (entry.cost_cp, entry.quality) == (250, "junk")


# --- К7х ревью: участник без equipment, у NPC он задан ---

def npc_duel(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True)],
    )
    part(engine, "goblin_1").equipment = None
    engine.world.npcs["goblin_1"].equipment = Equipment(weapons=["shortbow"])
    return engine


def test_pickup_writes_into_a_copy_for_the_participant_without_equipment(registry, cfg):
    engine = npc_duel(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert engine.equipment("goblin_1").weapons == ["shortbow", "scimitar"]


def test_pickup_does_not_change_the_npc_equipment(registry, cfg):
    engine = npc_duel(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert engine.world.npcs["goblin_1"].equipment.weapons == ["shortbow"]


def test_pickup_gives_the_participant_its_own_equipment(registry, cfg):
    engine = npc_duel(registry, cfg)
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert part(engine, "goblin_1").equipment is not engine.world.npcs["goblin_1"].equipment
    assert part(engine, "goblin_1").equipment.weapons == ["shortbow", "scimitar"]


def test_pickup_keeps_the_own_equipment_of_the_participant(registry, cfg):
    engine = npc_duel(registry, cfg)
    part(engine, "goblin_1").equipment = Equipment(weapons=["dagger"])
    drop(engine, "scimitar", owner="goblin_1")
    engine.perform("goblin_1", "pickup:0")
    assert part(engine, "goblin_1").equipment.weapons == ["dagger", "scimitar"]
    assert engine.world.npcs["goblin_1"].equipment.weapons == ["shortbow"]
