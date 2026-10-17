# Карта боя: строка «На земле: скимитар (Центр зала)» -- выбитое оружие (docs/plan-combat-disarm.md,
# п. 4). ground_line(state, registry, width) -> list[str]; battle_map_lines(..., registry=None)
# добавляет её в конец; без registry или без предметов строки нет.
from combat_kit import make_engine, make_fighter, mon

from ai_dm.game.battle_map import battle_map_lines, ground_line
from ai_dm.state.combat import GroundItem


def engine_with(registry, cfg, items):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    engine.state.ground_items = items
    return engine


def test_ground_line_names_the_weapon_and_the_zone(registry, cfg):
    engine = engine_with(registry, cfg, [GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0)])
    assert ground_line(engine.state, registry, 80) == ["  На земле: скимитар (Центр зала)"]


def test_ground_line_lists_every_item(registry, cfg):
    items = [
        GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0),
        GroundItem(item_id="shortbow", zone_id="door", cost_cp=0),
    ]
    engine = engine_with(registry, cfg, items)
    text = " ".join(ground_line(engine.state, registry, 80))
    assert "скимитар (Центр зала); короткий лук (У двери)" in text


def test_ground_line_is_empty_without_items(registry, cfg):
    engine = engine_with(registry, cfg, [])
    assert ground_line(engine.state, registry, 80) == []


def test_ground_line_is_empty_without_a_registry(registry, cfg):
    engine = engine_with(registry, cfg, [GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0)])
    assert ground_line(engine.state, None, 80) == []


def test_ground_line_wraps_to_the_width(registry, cfg):
    items = [GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0),
             GroundItem(item_id="shortbow", zone_id="door", cost_cp=0)]
    engine = engine_with(registry, cfg, items)
    lines = ground_line(engine.state, registry, 30)
    assert len(lines) > 1
    assert all(len(line) <= 30 for line in lines)


def test_battle_map_ends_with_the_ground_line(registry, cfg):
    engine = engine_with(registry, cfg, [GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0)])
    hero = engine.heroes["hero"]
    lines = battle_map_lines(engine.state, engine.world, hero, 80, registry)
    assert lines[-1] == "  На земле: скимитар (Центр зала)"


def test_battle_map_without_a_registry_has_no_ground_line(registry, cfg):
    engine = engine_with(registry, cfg, [GroundItem(item_id="scimitar", zone_id="hall", cost_cp=0)])
    hero = engine.heroes["hero"]
    lines = battle_map_lines(engine.state, engine.world, hero, 80)
    assert not [line for line in lines if "На земле" in line]
