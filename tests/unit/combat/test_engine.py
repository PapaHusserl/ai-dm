# Цикл боя (шаг 16): CombatEngine.step(), run_to_end(max_rounds), истечение Expiry в цикле.
#   step() -- ход одного участника с индексом turn_index в initiative_order:
#     * мёртвый и ушедший (status dead/fled) пропускаются: событий нет, turn_index сдвигается;
#     * остальным -- событие turn_started {round, id}, начало хода (состояния Expiry
#       start_of_turn, урон зоны hazard, восстановление turn: action/bonus/reaction/move=1,
#       disengaged=False), затем контроллер (DecisionPoint(kind="turn_action", actor=ref,
#       options=[id...])) выбирает, пока не вернёт end_turn; id вне options -> ValueError;
#       конец хода (Expiry end_of_turn), turn_index + 1; после последнего -- round + 1, turn_index 0
#       и тик Expiry(kind="rounds").
#   Истечение (Expiry) у ActiveEffect и AppliedCondition любого участника:
#     start_of_turn, owner -- снимается в начале хода owner (owner=None -- хозяина эффекта);
#     end_of_turn, owner -- в конце хода owner;
#     rounds, value=N -- value уменьшается в конце каждого раунда (после хода последнего),
#       при 0 эффект снимается: value=1 живёт до конца текущего раунда, value=2 -- ещё и следующего;
#     concentration / seconds цикл боя не трогает; эффект без expires живёт вечно.
#   run_to_end(max_rounds=None) -> list[DomainEvent]: step() до конца боя; max_rounds по умолчанию
#     cfg.combat.max_rounds; бой не кончился за лимит -> CombatRoundLimit (RuntimeError),
#     state.outcome остаётся None, combat_ended не порождается.
import pytest
from combat_kit import ScriptedRng, creature, hp, make_engine, make_fighter, mon, part, set_hp

from ai_dm.combat.controllers import ScriptedController
from ai_dm.combat.engine import CombatRoundLimit
from ai_dm.config.settings import load_rules_config
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry


def two_sides(registry, cfg, controllers=None, rng=None, **kwargs):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        controllers=controllers, rng=rng, **kwargs,
    )


def idle():
    return {"hero": ScriptedController([]), "goblin_1": ScriptedController([])}


def effect(effect_id, expires):
    return ActiveEffect(
        id=effect_id, source="test", kind="modifier",
        params={"target": "attack_roll", "mode": "advantage"}, expires=expires,
    )


def effect_ids(engine, ref):
    return [e.id for e in creature(engine, ref).active_effects]


# step

def test_step_advances_turn_index(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.step()
    assert engine.state.turn_index == 1


def test_step_reports_whose_turn_started(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    events = engine.step()
    started = [e for e in events if e.type == "turn_started"]
    assert [e.data for e in started] == [{"round": 1, "id": "hero"}]


def test_second_step_is_the_next_participant(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.step()
    events = engine.step()
    assert [e.data["id"] for e in events if e.type == "turn_started"] == ["goblin_1"]


def test_round_ends_after_the_last_participant(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.step()
    engine.step()
    assert engine.state.round == 2
    assert engine.state.turn_index == 0


def three_sides(registry, cfg):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
        controllers={"hero": ScriptedController([]), "goblin_2": ScriptedController([])},
    )


def test_dead_participant_is_skipped(registry, cfg):
    engine = three_sides(registry, cfg)
    part(engine, "goblin_1").status = "dead"
    engine.step()
    events = engine.step()
    assert [e for e in events if e.type == "turn_started"] == []
    assert engine.state.turn_index == 2


def test_fled_participant_is_skipped(registry, cfg):
    engine = three_sides(registry, cfg)
    part(engine, "goblin_1").status = "fled"
    engine.step()
    assert [e for e in engine.step() if e.type == "turn_started"] == []


def test_controller_gets_a_turn_action_decision_point(registry, cfg):
    controller = ScriptedController([])
    engine = two_sides(registry, cfg, {"hero": controller, "goblin_1": ScriptedController([])})
    engine.step()
    point = controller.seen[0]
    assert point.kind == "turn_action"
    assert point.actor == "hero"
    assert "end_turn" in point.options


def test_controller_is_asked_until_end_turn(registry, cfg):
    controller = ScriptedController(["dodge", "end_turn"])
    engine = two_sides(registry, cfg, {"hero": controller, "goblin_1": ScriptedController([])})
    engine.step()
    assert len(controller.seen) == 2
    assert engine.state.turn_index == 1


def test_unavailable_choice_is_an_error(registry, cfg):
    class Liar:
        def choose(self, options, ctx):
            return "attack:longsword:nobody"

    engine = two_sides(registry, cfg, {"hero": Liar(), "goblin_1": ScriptedController([])})
    with pytest.raises(ValueError):
        engine.step()


def test_turn_economy_is_restored_at_own_turn_start(registry, cfg):
    controllers = {"hero": ScriptedController(["dodge"]), "goblin_1": ScriptedController([])}
    engine = two_sides(registry, cfg, controllers)
    engine.step()
    assert part(engine, "hero").turn.action is False
    engine.step()
    engine.step()
    assert part(engine, "hero").turn.action is True


def test_step_after_the_end_is_an_error(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.end_combat()
    with pytest.raises(ValueError):
        engine.step()


# run_to_end

def test_run_to_end_finishes_the_fight(registry, cfg):
    # у гоблина 1 HP: первая же атака героя добивает
    controllers = {
        "hero": ScriptedController(["attack:longsword:goblin_1"]),
        "goblin_1": ScriptedController([]),
    }
    engine = two_sides(registry, cfg, controllers, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 1)
    events = engine.run_to_end()
    assert engine.state.outcome == "victory"
    assert engine.is_over
    assert events[-1].type == "combat_ended"


def test_run_to_end_raises_on_round_limit(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    with pytest.raises(CombatRoundLimit):
        engine.run_to_end(max_rounds=3)


def test_round_limit_leaves_the_fight_open(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    with pytest.raises(CombatRoundLimit):
        engine.run_to_end(max_rounds=3)
    assert engine.state.outcome is None
    assert "combat_ended:fight_1" not in engine.world.flags


def test_default_round_limit_comes_from_config(registry):
    small = load_rules_config(toml_text="[combat]\nmax_rounds = 2\n")
    engine = two_sides(registry, small, idle())
    with pytest.raises(CombatRoundLimit):
        engine.run_to_end()


def test_run_to_end_within_limit_does_not_raise(registry, cfg):
    controllers = {
        "hero": ScriptedController(["end_turn", "attack:longsword:goblin_1"]),
        "goblin_1": ScriptedController([]),
    }
    engine = two_sides(registry, cfg, controllers, ScriptedRng(d20=[15], d8=[4]))
    set_hp(engine, "goblin_1", 1)
    engine.run_to_end(max_rounds=2)
    assert engine.state.outcome == "victory"
    assert hp(engine, "goblin_1") == 0


# истечение Expiry

def test_start_of_turn_effect_is_removed_when_owner_turn_starts(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="start_of_turn", owner="goblin_1"))
    )
    engine.step()
    assert effect_ids(engine, "hero") == ["e1"]
    engine.step()
    assert effect_ids(engine, "hero") == []


def test_start_of_turn_without_owner_uses_the_holder(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="start_of_turn"))
    )
    engine.step()
    assert effect_ids(engine, "hero") == []


def test_start_of_turn_effect_is_gone_before_the_owner_acts(registry, cfg):
    seen = []

    class Spy:
        def choose(self, options, ctx):
            seen.append(effect_ids(engine, "hero"))
            return "end_turn"

    engine = two_sides(registry, cfg, {"hero": Spy(), "goblin_1": ScriptedController([])})
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="start_of_turn", owner="hero"))
    )
    engine.step()
    assert seen == [[]]


def test_end_of_turn_effect_lives_through_the_turn(registry, cfg):
    seen = []

    class Spy:
        def choose(self, options, ctx):
            seen.append(effect_ids(engine, "hero"))
            return "end_turn"

    engine = two_sides(registry, cfg, {"hero": Spy(), "goblin_1": ScriptedController([])})
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="end_of_turn", owner="hero"))
    )
    engine.step()
    assert seen == [["e1"]]
    assert effect_ids(engine, "hero") == []


def test_end_of_turn_effect_stays_during_other_turns(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    creature(engine, "goblin_1").active_effects.append(
        effect("e1", Expiry(kind="end_of_turn", owner="goblin_1"))
    )
    engine.step()
    assert effect_ids(engine, "goblin_1") == ["e1"]
    engine.step()
    assert effect_ids(engine, "goblin_1") == []


def test_one_round_effect_ends_with_the_round(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="rounds", value=1))
    )
    engine.step()
    assert effect_ids(engine, "hero") == ["e1"]
    engine.step()
    assert effect_ids(engine, "hero") == []


def test_two_round_effect_survives_the_first_round(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="rounds", value=2))
    )
    engine.step()
    engine.step()
    assert effect_ids(engine, "hero") == ["e1"]
    engine.step()
    engine.step()
    assert effect_ids(engine, "hero") == []


def test_rounds_expiry_works_for_conditions(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="poisoned", source="hero", expires=Expiry(kind="rounds", value=1))
    )
    engine.step()
    engine.step()
    assert creature(engine, "goblin_1").conditions == []


def test_start_of_turn_expiry_works_for_conditions(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    creature(engine, "goblin_1").conditions.append(
        AppliedCondition(id="prone", expires=Expiry(kind="start_of_turn", owner="hero"))
    )
    engine.step()
    assert creature(engine, "goblin_1").conditions == []


def test_effect_without_expiry_lives_forever(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(effect("e1", None))
    for _ in range(6):
        engine.step()
    assert effect_ids(engine, "hero") == ["e1"]


def test_concentration_effect_is_not_touched_by_ticks(registry, cfg):
    engine = two_sides(registry, cfg, idle())
    engine.heroes["hero"].creature.active_effects.append(
        effect("e1", Expiry(kind="concentration", owner="hero"))
    )
    for _ in range(4):
        engine.step()
    assert effect_ids(engine, "hero") == ["e1"]
