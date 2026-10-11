# Провоцированная атака и Nimble Escape (шаг 17, ТЗ 7).
#   Выход из зоны (perform move:<зона>), где есть боеспособный враг с нетронутой реакцией, без
#   Disengage в этом ходу (turn.disengaged) -- каждый такой враг одной реакцией делает ближнюю
#   атаку по уходящему (событие attack, outcome hit/miss/crit; turn.reaction врага -> False).
#   Враг без ближней атаки, без реакции, лежащий (status down/dead, hp 0) -- не атакует.
#   Если атака уронила уходящего на 0 HP -- он остаётся в прежней зоне.
#   Nimble Escape (черта nimble_escape у гоблинов): вариант disengage_bonus (бонусное действие)
#   = Disengage бонусным действием; у героя и стражника его нет.
from combat_kit import (
    ScriptedRng,
    hp,
    make_engine,
    make_fighter,
    mon,
    option_ids,
    part,
    set_hp,
    turn,
)

from ai_dm.rules.results import Rejected


def engine_with(registry, cfg, rng, goblins=("goblin_1",), hero_hp=None):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng,
        monsters=[mon(ref, "goblin_warrior", "hall") for ref in goblins],
    )
    if hero_hp is not None:
        set_hp(engine, "hero", hero_hp)
    return engine


def attacks(events):
    return [e.data for e in events if e.type == "attack"]


def test_leaving_a_zone_with_an_enemy_provokes_an_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2]))
    events = engine.perform("hero", "move:door")
    assert [(a["attacker"], a["target"]) for a in attacks(events)] == [("goblin_1", "hero")]


def test_opportunity_attack_hits_like_any_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[15], d6=[3]))
    engine.perform("hero", "move:door")
    assert hp(engine, "hero") == 7


def test_opportunity_attack_can_miss(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "move:door")
    assert hp(engine, "hero") == 12


def test_the_mover_still_leaves_after_a_miss(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "move:door")
    assert part(engine, "hero").zone_id == "door"


def test_opportunity_attack_spends_the_reaction(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("hero", "move:door")
    assert turn(engine, "goblin_1").reaction is False


def test_disengage_prevents_the_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    engine.perform("hero", "disengage")
    events = engine.perform("hero", "move:door")
    assert attacks(events) == []
    assert turn(engine, "goblin_1").reaction is True


def test_leaving_an_empty_zone_provokes_nothing(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert attacks(engine.perform("hero", "move:hall")) == []


def test_every_enemy_in_the_zone_gets_its_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2, 2]), goblins=("goblin_1", "goblin_2"))
    events = engine.perform("hero", "move:door")
    assert [a["attacker"] for a in attacks(events)] == ["goblin_1", "goblin_2"]


def test_enemy_without_reaction_does_not_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    turn(engine, "goblin_1").reaction = False
    assert attacks(engine.perform("hero", "move:door")) == []


def test_downed_enemy_does_not_attack(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(), goblins=("goblin_1", "goblin_2"))
    part(engine, "goblin_1").status = "down"
    set_hp(engine, "goblin_1", 0)
    part(engine, "goblin_2").status = "dead"
    assert attacks(engine.perform("hero", "move:door")) == []


def test_entering_a_zone_with_an_enemy_provokes_nothing(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], rng=ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert attacks(engine.perform("hero", "move:hall")) == []


def test_opportunity_attack_uses_the_melee_action(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[2]),
        monsters=[mon("guard_1", "guard", "hall")],
    )
    events = engine.perform("hero", "move:door")
    assert attacks(events)[0]["weapon"] == "копьё"
    assert attacks(events)[0]["mode"] == "melee"


def test_mover_dropped_by_the_attack_stays_in_place(registry, cfg):
    # 15 + 4 = 19 попадает; 1d6 + 2 = 8 против 3 HP
    engine = engine_with(registry, cfg, ScriptedRng(d20=[15], d6=[6]), hero_hp=3)
    engine.perform("hero", "move:door")
    assert part(engine, "hero").zone_id == "hall"
    assert hp(engine, "hero") == 0


# Nimble Escape

def test_goblin_can_disengage_with_a_bonus_action(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    assert "disengage_bonus" in option_ids(engine, "goblin_1")


def test_nimble_escape_spends_the_bonus_action_not_the_action(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    engine.perform("goblin_1", "disengage_bonus")
    assert turn(engine, "goblin_1").bonus is False
    assert turn(engine, "goblin_1").action is True
    assert turn(engine, "goblin_1").disengaged is True


def test_goblin_leaves_after_nimble_escape_without_provoking(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    engine.perform("goblin_1", "disengage_bonus")
    events = engine.perform("goblin_1", "move:balcony")
    assert attacks(events) == []
    assert turn(engine, "hero").reaction is True


def test_goblin_without_nimble_escape_provokes(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng(d20=[2]))
    events = engine.perform("goblin_1", "move:balcony")
    assert [a["attacker"] for a in attacks(events)] == ["hero"]


def test_nimble_escape_is_used_once_per_turn(registry, cfg):
    engine = engine_with(registry, cfg, ScriptedRng())
    engine.perform("goblin_1", "disengage_bonus")
    assert isinstance(engine.perform("goblin_1", "disengage_bonus"), Rejected)


def test_goblin_boss_has_nimble_escape_too(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("boss", "goblin_boss", "hall")],
    )
    assert "disengage_bonus" in option_ids(engine, "boss")


def test_guard_and_hero_have_no_nimble_escape(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("guard_1", "guard", "hall")],
    )
    assert "disengage_bonus" not in option_ids(engine, "guard_1")
    assert "disengage_bonus" not in option_ids(engine, "hero")


def test_hero_opportunity_attack_uses_only_the_weapon_in_hand(registry, cfg):
    # решение проектировщика 3б: сменить оружие можно лишь в действии Атака
    from combat_kit import give_weapon

    from ai_dm.combat.opportunity import melee_attack_of
    hero = make_fighter(registry)
    give_weapon(hero, registry, "shortbow")
    engine = make_engine(registry, cfg, heroes=[hero], rng=ScriptedRng(),
                         monsters=[mon("goblin_1", "goblin_warrior", "hall")])
    assert melee_attack_of(engine, "hero") is None
    give_weapon(engine.heroes["hero"], registry, "longsword")
    assert melee_attack_of(engine, "hero").id == "longsword"
