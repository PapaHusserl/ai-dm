# К8с П1: Неутомимость в бою (docs/plan-k8s.md, «Тесты», П1; решение 10 -- только в бою).
# Ожидание: пункт меню id "tireless", label «Неутомимость», cost "action"; есть, пока действие
# не потрачено и заряд пула tireless > 0; действие и заряд тратятся; hp_temp = max(прежние,
# 1d8 + мод. Мдр), но не меньше 1 на броске; лог «<Имя>: Неутомимость, временные HP N».
from combat_kit import ScriptedRng, make_engine, make_fighter, mon, option_ids, turn
from ranger_kit import ranger_at

from ai_dm.rules.progression import sync_resources

TIRELESS = "tireless"


def tireless_engine(registry, cfg, wis=16, level=10, rolls=(5,)):
    # Мдр 16 -> мод. +3
    hero = ranger_at(registry, level)
    hero.sheet.abilities["wis"] = wis
    sync_resources(hero, registry)
    return make_engine(
        registry, cfg, heroes=[hero], rng=ScriptedRng(d8=list(rolls)),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def hero_of(engine):
    return engine.heroes["hero"]


def test_tireless_option_is_offered_with_action_and_charge(registry, cfg):
    assert TIRELESS in option_ids(tireless_engine(registry, cfg), "hero")


def test_tireless_option_is_action_labelled(registry, cfg):
    engine = tireless_engine(registry, cfg)
    option = next(o for o in engine.available_actions("hero") if o.id == TIRELESS)
    assert (option.cost, option.label) == ("action", "Неутомимость")


def test_no_tireless_option_without_action(registry, cfg):
    engine = tireless_engine(registry, cfg)
    turn(engine, "hero").action = False
    assert TIRELESS not in option_ids(engine, "hero")


def test_no_tireless_option_with_empty_pool(registry, cfg):
    engine = tireless_engine(registry, cfg)
    hero_of(engine).creature.resources["tireless"].current = 0
    assert TIRELESS not in option_ids(engine, "hero")


def test_no_tireless_option_for_ranger_below_level_10(registry, cfg):
    assert TIRELESS not in option_ids(tireless_engine(registry, cfg, level=9), "hero")


def test_no_tireless_option_for_fighter(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert TIRELESS not in option_ids(engine, "hero")


def test_tireless_spends_the_action(registry, cfg):
    engine = tireless_engine(registry, cfg)
    engine.perform("hero", TIRELESS)
    assert turn(engine, "hero").action is False


def test_tireless_spends_one_charge(registry, cfg):
    engine = tireless_engine(registry, cfg)
    engine.perform("hero", TIRELESS)
    assert hero_of(engine).creature.resources["tireless"].current == 2


def test_tireless_gives_roll_plus_wisdom_temp_hp(registry, cfg):
    engine = tireless_engine(registry, cfg, rolls=(5,))
    engine.perform("hero", TIRELESS)
    assert hero_of(engine).creature.hp_temp == 8


def test_tireless_keeps_bigger_existing_temp_hp(registry, cfg):
    engine = tireless_engine(registry, cfg, rolls=(5,))
    hero_of(engine).creature.hp_temp = 12
    engine.perform("hero", TIRELESS)
    assert hero_of(engine).creature.hp_temp == 12


def test_tireless_replaces_smaller_temp_hp(registry, cfg):
    engine = tireless_engine(registry, cfg, rolls=(5,))
    hero_of(engine).creature.hp_temp = 3
    engine.perform("hero", TIRELESS)
    assert hero_of(engine).creature.hp_temp == 8


def test_tireless_gives_at_least_one_temp_hp(registry, cfg):
    # Мдр 8 -> мод. -1; бросок 1 -> итог 0 -> 1
    engine = tireless_engine(registry, cfg, wis=8, rolls=(1,))
    engine.perform("hero", TIRELESS)
    assert hero_of(engine).creature.hp_temp == 1


def test_tireless_logs_temp_hp(registry, cfg):
    engine = tireless_engine(registry, cfg, rolls=(5,))
    engine.perform("hero", TIRELESS)
    assert any("Неутомимость, временные HP 8" in line for line in engine.state.log)
