# Партия К7д, шаг 0.3: тип, подпись, цена и параметры пунктов меню (снято с кода на 187d319) --
# разгрузка list_options (standard_actions / bonus_actions) их не меняет.
from combat_kit import (
    creature,
    down_hero,
    feature,
    make_engine,
    make_fighter,
    make_zones,
    mon,
)

from ai_dm.rules.inventory import add_item
from ai_dm.state.creature import AppliedCondition


def row(engine, ref, option_id):
    option = [o for o in engine.available_actions(ref) if o.id == option_id][0]
    return (option.kind, option.label, option.cost, option.params)


def hero_engine(registry, cfg):
    hero = make_fighter(registry)
    add_item(hero, "potion_of_healing", cost_cp=0)
    return make_engine(
        registry, cfg, heroes=[hero], monsters=[mon("g", "goblin_warrior", "balcony")],
        zones=make_zones(hall=[feature("cover_half")]),
    )


def exit_engine(registry, cfg):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=make_zones(door_exit=True),
        hero_zone="door", monsters=[mon("boss", "goblin_boss", "hall")],
    )


def test_standard_rows(registry, cfg):
    engine = hero_engine(registry, cfg)
    assert row(engine, "hero", "dash") == ("dash", "Рывок", "action", {})
    assert row(engine, "hero", "disengage") == ("disengage", "Отход", "action", {})
    assert row(engine, "hero", "dodge") == ("dodge", "Уклонение", "action", {})
    assert row(engine, "hero", "hide") == (
        "hide", "Спрятаться (Скрытность СЛ 15)", "action", {},
    )


def test_bonus_and_end_rows(registry, cfg):
    engine = hero_engine(registry, cfg)
    assert row(engine, "hero", "second_wind") == ("second_wind", "Второе дыхание", "bonus", {})
    assert row(engine, "hero", "use_item:potion_of_healing") == (
        "use_item", "Использовать Зелье лечения", "bonus", {"item": "potion_of_healing"},
    )
    assert row(engine, "hero", "end_turn") == ("end_turn", "Закончить ход", "free", {})


def test_stabilize_row_for_a_downed_ally(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry), make_fighter(registry, "b")],
        monsters=[mon("g", "goblin_warrior", "balcony")],
    )
    down_hero(engine, "b")
    assert row(engine, "hero", "stabilize:b") == (
        "stabilize", "Стабилизировать Арн", "action", {"target": "b"},
    )


def test_flee_row_in_an_exit_zone(registry, cfg):
    assert row(exit_engine(registry, cfg), "hero", "flee") == ("flee", "Бежать", "action", {})


def test_restrained_hero_cannot_flee(registry, cfg):
    engine = exit_engine(registry, cfg)
    creature(engine, "hero").conditions.append(AppliedCondition(id="restrained", source="x"))
    assert "flee" not in [o.id for o in engine.available_actions("hero")]


def test_nimble_escape_row(registry, cfg):
    assert row(exit_engine(registry, cfg), "boss", "disengage_bonus") == (
        "disengage", "Проворное бегство", "bonus", {"bonus": True},
    )
