# Цена экземпляра в бою (docs/plan-custom-items.md, разд. 8, партия 0).
#   GroundItem(item_id, zone_id, owner_ref=None, qty=1, cost_cp: int, quality=None) -- выбитое
#       оружие несёт цену экземпляра (у героя -- со снятого стека, у монстра -- цена трофея).
#   settle_ground (победа): оружие -> герою с cost_cp и quality записи на земле;
#       своё вернувшееся -- с прежней ценой (отдельная строка, если у героя стек другой цены).
#   Подбор героем (pickup) -- тоже с ценой записи на земле.
#   Обезоруженный герой: на землю падает цена надетого экземпляра (самого дорогого стека id).
#   rob (apply_defeat_outcome): самые дорогие ПО ЦЕНЕ ЗАПИСИ, надетый экземпляр не берётся,
#       у стека снимается именно взятая запись.
from combat_kit import ScriptedRng, down_hero, make_engine, make_fighter, mon, part

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.combat.end import settle_ground
from ai_dm.rules.inventory import add_item, count_item, equip, remove_item
from ai_dm.state.combat import GroundItem
from ai_dm.state.hero import InventoryEntry


def duel(registry, cfg, hero=None, rng=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def stacks(hero, item_id):
    return sorted((e.cost_cp, e.quality, e.qty) for e in hero.inventory if e.item_id == item_id)


def drop(engine, item_id="scimitar", cost_cp=250, owner="goblin_1", quality=None):
    engine.state.ground_items.append(
        GroundItem(item_id=item_id, zone_id="hall", owner_ref=owner, cost_cp=cost_cp,
                   quality=quality)
    )


def won(engine):
    engine.state.outcome = "victory"


# GroundItem

def test_ground_item_keeps_the_price_and_quality():
    item = GroundItem(item_id="scimitar", zone_id="hall", cost_cp=250, quality="worn")
    assert (item.cost_cp, item.quality) == (250, "worn")


def test_ground_item_quality_defaults_to_none():
    assert GroundItem(item_id="scimitar", zone_id="hall", cost_cp=250).quality is None


# settle_ground

def test_settle_ground_gives_the_enemy_weapon_with_the_ground_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, cost_cp=250)
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(250, None, 1)]


def test_settle_ground_keeps_the_quality_of_the_ground_item(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, cost_cp=250, quality="worn")
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(250, "worn", 1)]


def test_settle_ground_own_weapon_returns_with_the_old_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, "scimitar", cost_cp=2500, owner="hero")
    add_item(hero, "scimitar", cost_cp=150)
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(150, None, 1), (2500, None, 1)]


def test_settle_ground_returned_weapon_joins_the_stack_of_the_same_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, "scimitar", cost_cp=2500, owner="hero")
    add_item(hero, "scimitar", cost_cp=2500)
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(2500, None, 2)]


def test_settle_ground_two_items_of_one_id_keep_their_own_prices(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, cost_cp=250)
    drop(engine, cost_cp=2500)
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(250, None, 1), (2500, None, 1)]


def test_settle_ground_qty_goes_with_the_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    engine.state.ground_items.append(
        GroundItem(item_id="scimitar", zone_id="hall", owner_ref="goblin_1", qty=3, cost_cp=250)
    )
    won(engine)
    settle_ground(engine)
    assert stacks(hero, "scimitar") == [(250, None, 3)]


def test_settle_ground_without_a_win_gives_nothing(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine)
    engine.state.outcome = "defeat"
    settle_ground(engine)
    assert count_item(hero, "scimitar") == 0


# подбор

def test_pickup_takes_the_ground_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, cost_cp=250, quality="junk")
    engine.perform("hero", "pickup:0")
    assert stacks(hero, "scimitar") == [(250, "junk", 1)]


def test_pickup_of_own_weapon_returns_the_old_price(registry, cfg):
    hero = make_fighter(registry)
    engine = duel(registry, cfg, hero)
    drop(engine, "scimitar", cost_cp=2500, owner="hero")
    add_item(hero, "scimitar", cost_cp=150)
    engine.perform("hero", "pickup:0")
    assert stacks(hero, "scimitar") == [(150, None, 1), (2500, None, 1)]


# обезоруженный герой

def rival_duel(registry, cfg, rival):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), rival], rng=ScriptedRng(d20=[10]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    part(engine, "rival").side = "enemies"
    part(engine, "rival").group_id = "goblins"
    return engine


def test_disarmed_hero_weapon_lies_on_the_ground_with_its_price(registry, cfg):
    rival = make_fighter(registry, "rival")
    engine = rival_duel(registry, cfg, rival)
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm", target="rival")
    price = registry.get("weapon", "longsword").cost_cp
    assert [(i.item_id, i.cost_cp) for i in engine.state.ground_items] == [("longsword", price)]


def test_disarmed_hero_drops_the_worn_expensive_copy(registry, cfg):
    rival = make_fighter(registry, "rival")
    price = registry.get("weapon", "longsword").cost_cp
    add_item(rival, "longsword", cost_cp=price // 10)
    engine = rival_duel(registry, cfg, rival)
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm", target="rival")
    assert [i.cost_cp for i in engine.state.ground_items] == [price]
    assert stacks(rival, "longsword") == [(price // 10, None, 1)]


# rob

def defeated(registry, cfg, inventory):
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[hero], intent="capture",
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True)],
    )
    hero.money_cp = 0
    hero.inventory = inventory
    engine.state.defeat_group_id = "goblins"
    engine.state.outcome = "defeat_pending"
    down_hero(engine, "hero", by="goblin_1")
    return engine, hero


def rob(engine, hero, registry, cfg, count):
    return apply_defeat_outcome(
        engine.state, ["rob"], DefeatParams(rob_items=count), world=engine.world, hero=hero,
        registry=registry, cfg=cfg, rng=ScriptedRng(),
    )


def test_rob_takes_the_expensive_stack_and_leaves_the_cheap_one(registry, cfg):
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="scimitar", cost_cp=150),
        InventoryEntry(item_id="scimitar", cost_cp=2500),
    ])
    rob(engine, hero, registry, cfg, 1)
    assert stacks(hero, "scimitar") == [(150, None, 1)]


def test_rob_goes_by_the_entry_price_not_the_registry_price(registry, cfg):
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="scimitar", cost_cp=10, quality="junk"),
        InventoryEntry(item_id="spear", cost_cp=100),
    ])
    rob(engine, hero, registry, cfg, 1)
    assert count_item(hero, "spear") == 0
    assert count_item(hero, "scimitar") == 1


def test_rob_takes_both_stacks_of_one_id_when_asked(registry, cfg):
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="scimitar", cost_cp=150),
        InventoryEntry(item_id="scimitar", cost_cp=2500),
    ])
    rob(engine, hero, registry, cfg, 2)
    assert count_item(hero, "scimitar") == 0


def test_rob_does_not_take_the_last_worn_copy_of_two_stacks(registry, cfg):
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="longsword", cost_cp=1500),
        InventoryEntry(item_id="longsword", cost_cp=150),
    ])
    hero.equipped.main_hand = "longsword"
    rob(engine, hero, registry, cfg, 2)
    assert stacks(hero, "longsword") == [(1500, None, 1)]
    assert hero.equipped.main_hand == "longsword"


def test_rob_removes_the_quality_stack_it_picked(registry, cfg):
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="scimitar", cost_cp=150),
        InventoryEntry(item_id="scimitar", cost_cp=150, quality="worn"),
        InventoryEntry(item_id="shortbow", cost_cp=2500),
    ])
    rob(engine, hero, registry, cfg, 1)
    assert [e.item_id for e in hero.inventory] == ["scimitar", "scimitar"]


def test_disarmed_hero_weapon_keeps_its_quality_on_the_ground(registry, cfg):
    rival = make_fighter(registry, "rival")
    remove_item(rival, "longsword")
    add_item(rival, "longsword", cost_cp=150, quality="worn")
    equip(rival, "longsword", registry)
    engine = rival_duel(registry, cfg, rival)
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm", target="rival")
    assert [(i.cost_cp, i.quality) for i in engine.state.ground_items] == [(150, "worn")]


def test_disarmed_hero_with_two_stacks_has_an_empty_hand(registry, cfg):
    rival = make_fighter(registry, "rival")
    add_item(rival, "longsword", cost_cp=15)
    engine = rival_duel(registry, cfg, rival)
    engine.improvise("hero", skill="athletics", category="medium", effect="disarm", target="rival")
    assert rival.equipped.main_hand is None


def test_rob_removes_the_stack_it_picked_when_prices_are_equal(registry, cfg):
    # надет экземпляр первого стека; взять можно только «поношенный» -- он и должен уйти
    engine, hero = defeated(registry, cfg, [
        InventoryEntry(item_id="scimitar", cost_cp=150),
        InventoryEntry(item_id="scimitar", cost_cp=150, quality="worn"),
    ])
    hero.equipped.main_hand = "scimitar"
    rob(engine, hero, registry, cfg, 1)
    assert [(e.cost_cp, e.quality, e.qty) for e in hero.inventory] == [(150, None, 1)]
    assert hero.equipped.main_hand == "scimitar"
