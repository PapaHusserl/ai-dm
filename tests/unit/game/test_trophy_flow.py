# Квестовый предмет по цепочке «грабёж -> след -> победа над держателем -> добыча»
# (docs/CUSTOM-ITEMS-PLAN.md, разд. 5 и 7, сценарий партии В).
#   1. rob: банда с именованным лидером забирает квестовый ключ, держатель -- NPC-лидер;
#      контекст мастера (lost_items_data) показывает ключ с держателем;
#   2. победа над этим лидером: settle_ground кладёт ключ в gear (как есть, без качества);
#   3. finish_combat переносит gear в last_combat (gear_looted False), контекст мастера видит
#      снаряжение на телах;
#   4. gold loot_individual возвращает ключ герою с той же ценой, держатель снят, lost_items пуст.
import game_kit  # noqa: F401  (путь к master_kit и protocol_kit)
from combat_kit import ScriptedRng, down_hero, make_engine, make_fighter, mon, part
from master_kit import combat_ctx
from protocol_kit import make_bundle, make_ctx, req

from ai_dm.combat.defeat import DefeatParams, apply_defeat_outcome
from ai_dm.combat.end import settle_ground
from ai_dm.game.combat_flow import finish_combat
from ai_dm.master.prompt import items_trail_data, lost_items_data
from ai_dm.protocol.apply import apply
from ai_dm.rules.custom_items import world_registry
from ai_dm.rules.inventory import add_item, count_item
from ai_dm.state.combat import CombatState
from ai_dm.state.hero import Equipped
from ai_dm.state.session import LastCombat
from ai_dm.state.world import CustomItem


def robbed(registry, cfg):
    hero = make_fighter(registry)
    engine = make_engine(
        registry, cfg, heroes=[hero], intent="rob",
        monsters=[mon("goblin_1", "goblin_warrior", "hall", named=True),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    engine.world.npcs["goblin_1"].named = True
    hero.location_id = "vale"
    hero.inventory = []
    hero.equipped = Equipped()
    engine.state.groups["goblins"].lair_location_id = "goblin_den"
    engine.state.defeat_group_id = "goblins"
    engine.state.outcome = "defeat_pending"
    engine.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", quest=True, created_s=0
    )
    add_item(hero, "custom_1", cost_cp=900)
    down_hero(engine, "hero", by="goblin_1")
    apply_defeat_outcome(
        engine.state, ["rob"], DefeatParams(rob_items=1), world=engine.world, hero=hero,
        registry=world_registry(registry, engine.world), cfg=cfg, rng=ScriptedRng(),
    )
    return engine, hero


def victory_over_band(engine, hero):
    hero.creature.hp_current = 5
    part(engine, "hero").status = "active"
    for p in engine.state.participants:
        if p.side == "enemies":
            p.status = "dead"
    engine.state.outcome = "victory"
    settle_ground(engine)


def test_robbed_key_shows_up_in_lost_items(registry, cfg):
    engine, hero = robbed(registry, cfg)
    lost = lost_items_data(engine.world)
    assert [item["item_id"] for item in lost] == ["custom_1"]
    assert lost[0]["holder"]["location_id"] == "goblin_den"


def test_victory_over_the_holder_puts_the_key_into_gear(registry, cfg):
    engine, hero = robbed(registry, cfg)
    victory_over_band(engine, hero)
    keys = [e for e in engine.state.gear if e.item_id == "custom_1"]
    assert [(e.qty, e.cost_cp, e.quality) for e in keys] == [(1, 900, None)]


def test_victory_over_other_goblin_only_does_not_return_the_key(registry, cfg):
    engine, hero = robbed(registry, cfg)
    victory_over_band(engine, hero)
    part(engine, "goblin_1").status = "fled"
    engine.state.gear = []
    settle_ground(engine)
    assert all(e.item_id != "custom_1" for e in engine.state.gear)


def test_loot_returns_the_key_and_clears_the_trail(registry, cfg):
    engine, hero = robbed(registry, cfg)
    victory_over_band(engine, hero)
    bundle = make_bundle(registry)
    bundle.world = engine.world
    bundle.heroes[0].inventory = []
    bundle.session.last_combat = LastCombat(defeated=[], gear=engine.state.gear)
    ctx = make_ctx(registry, cfg, ScriptedRng(), bundle=bundle)
    ctx.registry = world_registry(registry, engine.world)
    d = apply(ctx, req("gold", direction="gain", kind="loot_individual"))
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 1
    assert [(e.cost_cp, e.quality) for e in ctx.hero.inventory if e.item_id == "custom_1"] == [
        (900, None)
    ]
    assert lost_items_data(engine.world) == []
    names = {i["item_id"]: i["name"] for i in d.result["items"]}
    assert names["custom_1"] == "Ржавый ключ"


# finish_combat переносит gear

def combat_over(registry, cfg, outcome, gear):
    ctx = combat_ctx(registry, cfg)
    bundle = ctx.bundle
    state = bundle.session.active_combat
    state.outcome = outcome
    state.gear = gear
    return bundle


def trophies():
    from ai_dm.state.hero import InventoryEntry

    return [InventoryEntry(item_id="scimitar", qty=2, cost_cp=250, quality="junk")]


def test_finish_combat_moves_gear_to_last_combat_unlooted(registry, cfg):
    bundle = combat_over(registry, cfg, "victory", trophies())
    finish_combat(bundle, registry)
    last = bundle.session.last_combat
    assert [(e.item_id, e.qty, e.cost_cp, e.quality) for e in last.gear] == [
        ("scimitar", 2, 250, "junk")
    ]
    assert last.gear_looted is False


def test_finish_combat_keeps_gear_for_ended_by_master(registry, cfg):
    bundle = combat_over(registry, cfg, "ended_by_master", trophies())
    finish_combat(bundle, registry)
    assert len(bundle.session.last_combat.gear) == 1


def test_finish_combat_after_defeat_has_no_last_combat(registry, cfg):
    bundle = combat_over(registry, cfg, "defeat_pending", trophies())
    finish_combat(bundle, registry)
    assert bundle.session.last_combat is None


def test_master_context_shows_gear_on_the_bodies(registry, cfg):
    bundle = combat_over(registry, cfg, "victory", trophies())
    finish_combat(bundle, registry)
    data = items_trail_data(bundle.world, bundle.session, registry)
    assert data["last_combat"] == {"gear": ["Ржавый скимитар ×2"]}


def test_state_gear_defaults_to_empty():
    assert CombatState(id="c", zones=[], participants=[], groups={}).gear == []


def test_finish_combat_after_hero_fled_keeps_last_combat_with_empty_gear(registry, cfg):
    bundle = combat_over(registry, cfg, "fled", [])
    finish_combat(bundle, registry)
    assert bundle.session.last_combat is not None
    assert bundle.session.last_combat.gear == []


def test_finish_combat_with_dead_hero_has_no_last_combat(registry, cfg):
    bundle = combat_over(registry, cfg, "victory", trophies())
    bundle.heroes[0].status = "dead"
    finish_combat(bundle, registry)
    assert bundle.session.last_combat is None


def test_finish_combat_keeps_the_lair_next_to_gear(registry, cfg):
    bundle = combat_over(registry, cfg, "victory", trophies())
    bundle.session.active_combat.groups["goblins"].lair_location_id = "goblin_den"
    finish_combat(bundle, registry)
    assert bundle.session.last_combat.lair_location_id == "goblin_den"


def test_finish_combat_clears_the_active_combat(registry, cfg):
    bundle = combat_over(registry, cfg, "victory", trophies())
    finish_combat(bundle, registry)
    assert bundle.session.active_combat is None
