# Стеки разной цены в бою и цены выбитого оружия монстра (CUSTOM-ITEMS-PLAN, разд. 8, партия 0).
#   Опции боя по предмету считаются по id (сумма по стекам): пункт один на id,
#       «Выпить: ... (осталось N)» и «(осталось N)» у особых стрел -- сумма по стекам.
#   Оружие монстра (обезоруживание, сдача) ложится на землю с ценой из реестра, без качества
#       (трофейные цены по ПО -- партия В); герой, подхвативший его, получает запись с этой ценой.
#   Герой из конструктора (build_character) получает вещи с ценой из реестра.
from pathlib import Path

import pytest
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, option_ids

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.rules.inventory import add_item, count_item, equip
from ai_dm.state.hero import InventoryEntry

WIN = [5, 5, 15]
DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


def duel(registry, cfg, rng=None, hero=None):
    return make_engine(
        registry, cfg, heroes=[hero or make_fighter(registry)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def disarm_scimitar(engine):
    option = [
        o for o in engine.available_actions("hero")
        if o.kind == "disarm" and o.params["weapon_id"] == "scimitar"
    ][0]
    engine.perform("hero", option.id)


# опции по предметам

def test_two_potion_stacks_give_one_use_option(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", 2, cost_cp=5000)
    add_item(hero, "potion_of_healing", cost_cp=500)
    ids = option_ids(duel(registry, cfg, hero=hero), "hero")
    assert ids.count("use_item:potion_of_healing") == 1


def test_use_item_takes_the_cheapest_stack(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=5000)
    add_item(hero, "potion_of_healing", cost_cp=500)
    engine = duel(registry, cfg, ScriptedRng(d4=[1, 1]), hero=hero)
    engine.perform("hero", "use_item:potion_of_healing")
    assert [(e.cost_cp, e.qty) for e in hero.inventory if e.item_id == "potion_of_healing"] == [
        (5000, 1)
    ]


def dragon_engine(cfg, tmp_path, extra_cost_items):
    registry = load_registry([pack_content_dir(DRAGON)])
    pack = load_pack(DRAGON, registry)
    bundle = new_world_from_pack(
        registry, cfg, pack, hero="grey", seed=1, world_id="dd", saved_at="2026-01-01T00:00:00",
    )
    hero = bundle.heroes[0]
    equip(hero, "composite_longbow", registry)
    for item_id in extra_cost_items:
        add_item(hero, item_id, cost_cp=1)
    engine = make_engine(
        registry, cfg, heroes=[hero], monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        hero_zone="door",
    )
    return engine, hero


def option_label(engine, prefix):
    return [o.label for o in engine.available_actions("hero") if prefix in o.id][0]


def test_elixir_note_sums_the_stacks(cfg, tmp_path):
    engine, hero = dragon_engine(cfg, tmp_path, ["stoneskin_elixir"])
    total = count_item(hero, "stoneskin_elixir")
    assert total >= 2
    options = engine.available_actions("hero")
    labels_ = [o.label for o in options if o.id == "use_item:stoneskin_elixir"]
    assert len(labels_) == 1
    assert f"осталось {total}" in labels_[0]


def test_special_arrows_option_sums_the_stacks(cfg, tmp_path):
    engine, hero = dragon_engine(cfg, tmp_path, ["arrow_fire"])
    total = count_item(hero, "arrow_fire")
    assert total == 11
    assert f"(осталось {total})" in option_label(engine, "ammo:arrow_fire")


# оружие монстра на земле

def test_monster_weapon_on_the_ground_has_the_trophy_price(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    disarm_scimitar(engine)
    item = engine.state.ground_items[0]
    assert (item.item_id, item.cost_cp, item.quality) == (
        "scimitar", 250, "junk"
    )


def test_hero_picks_the_monster_weapon_with_its_ground_price(registry, cfg):
    engine = duel(registry, cfg, ScriptedRng(d20=WIN))
    disarm_scimitar(engine)
    engine.perform("hero", "pickup:0")
    hero = engine.heroes["hero"]
    assert [(e.cost_cp, e.quality) for e in hero.inventory if e.item_id == "scimitar"] == [
        (250, "junk")
    ]


def test_monster_weapon_price_does_not_touch_other_stacks(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "scimitar", cost_cp=3)
    engine = duel(registry, cfg, ScriptedRng(d20=WIN), hero=hero)
    disarm_scimitar(engine)
    engine.perform("hero", "pickup:0")
    assert sorted(e.cost_cp for e in hero.inventory if e.item_id == "scimitar") == [3, 250]


# герой из конструктора

def test_built_hero_items_have_registry_prices(registry):
    hero = make_fighter(registry)
    for entry in hero.inventory:
        found = [
            registry.get(kind, entry.item_id).cost_cp
            for kind in ("weapon", "armor", "item") if registry.has(kind, entry.item_id)
        ]
        assert entry.cost_cp == found[0]
        assert entry.quality is None


def test_built_hero_still_has_his_gear(registry):
    hero = make_fighter(registry)
    assert count_item(hero, "longsword") == 1
    assert hero.equipped.main_hand == "longsword"


def test_inventory_entry_requires_a_price():
    from pydantic import ValidationError

    with pytest.raises(ValidationError):
        InventoryEntry(item_id="scimitar")
