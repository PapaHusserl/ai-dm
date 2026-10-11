# Мультиатака монстра (ревью партии 5, п. 9): Monster.multiattack = [{action, count}].
#   У монстра с multiattack (goblin_boss: Скимитар x2) в available_actions есть отдельный вариант
#   "multiattack" (тратит действие); выполнение -- шаги multiattack по порядку, каждая атака со
#   своим броском; цель каждой атаки выбирает тактика (EngineTactics), без дополнительных бросков.
#   Событий attack -- по числу атак; без бросков кроме самих атак и урона -- детерминизм: один сид
#   даёт один и тот же ход.
#   У монстров без multiattack (goblin_warrior) варианта "multiattack" нет.
# Босс: КД 17, +4 к атаке, скимитар 1d6+2; КД героя-воина 19 -> d20 15 попадает.
from combat_kit import ScriptedRng, hp, make_engine, make_fighter, mon, option_ids, turn

from ai_dm.combat.controllers import ScriptedController


def boss_fight(registry, cfg, rng, controllers=None, **kwargs):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, controllers=controllers,
        monsters=[mon("boss", "goblin_boss", "hall")], **kwargs,
    )


def attacks(events):
    return [e.data for e in events if e.type == "attack"]


def test_boss_has_a_multiattack_option(registry, cfg):
    engine = boss_fight(registry, cfg, ScriptedRng())
    assert "multiattack" in option_ids(engine, "boss")


def test_goblin_warrior_has_no_multiattack_option(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert "multiattack" not in option_ids(engine, "goblin_1")


def test_multiattack_makes_two_attacks(registry, cfg):
    engine = boss_fight(registry, cfg, ScriptedRng(d20=[15, 15], d6=[1, 1]))
    events = engine.perform("boss", "multiattack")
    assert [(a["attacker"], a["target"], a["outcome"]) for a in attacks(events)] == [
        ("boss", "hero", "hit"), ("boss", "hero", "hit"),
    ]


def test_multiattack_rolls_each_attack_and_damage_separately(registry, cfg):
    # 1d6 + 2: (3 + 2) + (4 + 2) = 11
    engine = boss_fight(registry, cfg, ScriptedRng(d20=[15, 15], d6=[3, 4]))
    engine.perform("boss", "multiattack")
    assert hp(engine, "hero") == 12 - 11


def test_multiattack_uses_the_action(registry, cfg):
    engine = boss_fight(registry, cfg, ScriptedRng(d20=[2, 2]))
    engine.perform("boss", "multiattack")
    assert turn(engine, "boss").action is False
    assert "multiattack" not in option_ids(engine, "boss")


def test_multiattack_misses_are_reported_too(registry, cfg):
    engine = boss_fight(registry, cfg, ScriptedRng(d20=[2, 15], d6=[1]))
    events = engine.perform("boss", "multiattack")
    assert [a["outcome"] for a in attacks(events)] == ["miss", "hit"]


def test_boss_turn_under_engine_tactics_makes_two_attacks(registry, cfg):
    controllers = {"hero": ScriptedController([])}
    engine = boss_fight(registry, cfg, ScriptedRng(d20=[15, 15], d6=[1, 1]), controllers)
    engine.step()
    events = engine.step()
    assert [a["attacker"] for a in attacks(events)] == ["boss", "boss"]


def test_multiattack_is_deterministic(registry, cfg):
    def play():
        controllers = {"hero": ScriptedController([])}
        engine = boss_fight(registry, cfg, ScriptedRng(d20=[15, 3], d6=[5]), controllers)
        engine.step()
        engine.step()
        return engine.state.model_dump_json(), engine.heroes["hero"].model_dump_json()

    assert play() == play()

