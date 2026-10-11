# Конец боя (шаг 21, ТЗ 7): ai_dm.combat.end (вызывается движком после каждого действия и хода).
#   Условия:
#     * у врагов нет боеспособных (мертвы, без сознания, ушли) -- outcome "victory";
#     * у героев нет боеспособных: ушли через exit-зону (вариант flee, действие; в зоне с
#       exit=True), никто не упал -- "fled"; упали -- "defeat_pending" / "hero_dying" /
#       "hero_dead" (test_downed.py);
#       смерть героя бой НЕ обрывает: пока на стороне heroes стоит боеспособный союзник, бой идёт;
#       он кончается по обычным условиям сторон, итог -- "hero_dead", если хоть один герой из
#       engine.heroes мёртв (приоритет над "victory" и "fled"); если мёртвый герой -- единственный
#       участник своей стороны, бой кончается сразу; мёртвый герой не ходит;
#       "hero_dead" -- только при мёртвом ГЕРОЕ (engine.heroes); гибель NPC-союзника (участник
#       стороны heroes без листа героя) исхода не меняет: сбежавший герой + убитый союзник ->
#       "fled";
#       все ГЕРОИ ушли -- "fled", даже если боеспособные союзные NPC остались на поле (их судьба --
#       нарратив мастера, этап 2);
#     * у врагов нет боеспособных -- "victory", если стоит хоть один герой или союзник; иначе
#       (все герои лежат, умирают) спасброски от смерти продолжаются, "hero_dying";
#     * CombatEngine.end_combat() -- "ended_by_master";
#     * лимит раундов -- ошибка CombatRoundLimit (test_engine.py).
#   При завершении (один раз): события в конце списка -- combat_ended {id: state.id}; флаг
#   combat_ended:<id> (auto_flags); часы мира += state.round * cfg.time.round_s через
#   time_ops.rounds_to_seconds (раунд, в котором бой закончился, считается целиком); пока бой идёт,
#   часы не двигаются; state.outcome -- терминальный; step() -> ValueError.
import pytest
from combat_kit import (
    ScriptedRng,
    down_hero,
    make_engine,
    make_fighter,
    make_zones,
    mon,
    option_ids,
    part,
    set_hp,
)

from ai_dm.combat.controllers import ScriptedController
from ai_dm.combat.engine import CombatRoundLimit
from ai_dm.config.settings import load_rules_config


def duel(registry, cfg, rng=None, controllers=None, **kwargs):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=rng, controllers=controllers,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], **kwargs,
    )


def types(events):
    return [e.type for e in events]


def finishing_blow(registry, cfg, **kwargs):
    # у гоблина 1 HP, первая атака героя убивает
    engine = duel(registry, cfg, ScriptedRng(d20=[15], d8=[4]), **kwargs)
    set_hp(engine, "goblin_1", 1)
    return engine


# победа

def test_victory_when_the_last_enemy_dies(registry, cfg):
    engine = finishing_blow(registry, cfg)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.outcome == "victory"
    assert engine.is_over


def test_victory_when_every_enemy_is_down_or_dead(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 1)
    set_hp(engine, "goblin_2", 0)
    part(engine, "goblin_2").status = "down"
    engine.perform("hero", "attack:longsword:goblin_1:nonlethal")
    assert engine.state.outcome == "victory"


def test_no_victory_while_an_enemy_is_fit(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d8=[4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 1)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.state.outcome is None


def test_victory_when_the_enemies_flee(registry, cfg):
    zones = make_zones()
    zones[2].exit = True
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=zones,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("goblin_1", "flee")
    assert part(engine, "goblin_1").status == "fled"
    assert engine.state.outcome == "victory"


# бегство героев

def test_hero_flees_through_the_exit_zone(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=make_zones(door_exit=True),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "flee")
    assert part(engine, "hero").status == "fled"
    assert engine.state.outcome == "fled"
    assert engine.is_over


def test_flee_costs_the_action(registry, cfg):
    engine = make_engine(
        registry, cfg,
        heroes=[(make_fighter(registry), "door"), (make_fighter(registry, "ally"), "hall")],
        zones=make_zones(door_exit=True),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "flee")
    assert part(engine, "hero").turn.action is False


def test_fight_goes_on_until_every_hero_has_left(registry, cfg):
    engine = make_engine(
        registry, cfg,
        heroes=[(make_fighter(registry), "door"), (make_fighter(registry, "ally"), "door")],
        zones=make_zones(door_exit=True),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "flee")
    assert engine.state.outcome is None
    engine.perform("ally", "flee")
    assert engine.state.outcome == "fled"


def guard(ref="guard_1", zone="hall"):
    return mon(ref, "guard", zone, side="heroes", group="allies")


def test_hero_fled_and_the_ally_died_is_fled_not_hero_dead(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=make_zones(door_exit=True),
        monsters=[guard(), mon("goblin_1", "goblin_warrior", "balcony")],
    )
    part(engine, "guard_1").status = "dead"
    set_hp(engine, "guard_1", 0)
    engine.perform("hero", "flee")
    assert engine.state.outcome == "fled"


def test_every_hero_fled_with_a_living_ally_is_fled(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_fighter(registry), "door")], zones=make_zones(door_exit=True),
        monsters=[guard(), mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("hero", "flee")
    assert engine.state.outcome == "fled"
    assert engine.is_over


def test_fight_goes_on_while_a_hero_is_still_there_even_if_the_ally_died(registry, cfg):
    engine = make_engine(
        registry, cfg,
        heroes=[(make_fighter(registry), "door"), (make_fighter(registry, "ally"), "door")],
        zones=make_zones(door_exit=True),
        monsters=[guard(), mon("goblin_1", "goblin_warrior", "balcony")],
    )
    part(engine, "guard_1").status = "dead"
    set_hp(engine, "guard_1", 0)
    engine.perform("hero", "flee")
    assert engine.state.outcome is None


def test_victory_when_only_the_ally_stands(registry, cfg):
    # враги побеждены союзником-стражником, герой лежит и стабилизируется
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15], d6=[6]),
        monsters=[guard(zone="balcony"), mon("goblin_1", "goblin_warrior", "balcony")],
    )
    down_hero(engine, "hero")
    set_hp(engine, "goblin_1", 1)
    engine.perform("guard_1", "attack:копьё:goblin_1")
    assert engine.state.outcome == "victory"


# смерть героя при живом союзнике

def kill_hero(engine, ref="hero"):
    set_hp(engine, ref, 0)
    part(engine, ref).status = "dead"
    engine.heroes[ref].status = "dead"


def hero_and_guard(registry, cfg, **kwargs):
    return make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=make_zones(),
        monsters=[guard(), mon("goblin_1", "goblin_warrior", "hall")], **kwargs,
    )


def test_fight_goes_on_after_the_hero_died_while_the_ally_stands(registry, cfg):
    engine = hero_and_guard(registry, cfg)
    kill_hero(engine)
    engine.perform("guard_1", "end_turn")
    assert engine.state.outcome is None
    assert not engine.is_over


def test_ally_wins_after_the_hero_died_outcome_is_hero_dead(registry, cfg):
    engine = hero_and_guard(registry, cfg, rng=ScriptedRng(d20=[15], d6=[6]))
    set_hp(engine, "goblin_1", 1)
    kill_hero(engine)
    engine.perform("guard_1", "attack:копьё:goblin_1")
    assert part(engine, "goblin_1").status == "dead"
    assert engine.state.outcome == "hero_dead"
    assert engine.is_over


def test_hero_dead_outcome_beats_victory_in_the_end_events(registry, cfg):
    engine = hero_and_guard(registry, cfg, rng=ScriptedRng(d20=[15], d6=[6]))
    set_hp(engine, "goblin_1", 1)
    kill_hero(engine)
    events = engine.perform("guard_1", "attack:копьё:goblin_1")
    assert types(events)[-1] == "combat_ended"


def test_hero_dead_and_the_ally_fell_too_is_hero_dead(registry, cfg):
    engine = hero_and_guard(registry, cfg)
    kill_hero(engine)
    part(engine, "guard_1").status = "dead"
    set_hp(engine, "guard_1", 0)
    engine.perform("goblin_1", "end_turn")
    assert engine.state.outcome == "hero_dead"
    assert engine.is_over


def test_lone_hero_dead_ends_the_fight_at_once(registry, cfg):
    engine = duel(registry, cfg)
    kill_hero(engine)
    engine.perform("goblin_1", "end_turn")
    assert engine.state.outcome == "hero_dead"
    assert engine.is_over


def test_dead_hero_does_not_act_while_the_ally_fights_on(registry, cfg):
    controllers = {
        "hero": ScriptedController(["dodge"]),
        "guard_1": ScriptedController([]),
        "goblin_1": ScriptedController([]),
    }
    engine = hero_and_guard(registry, cfg, controllers=controllers)
    kill_hero(engine)
    engine.step()
    engine.step()
    engine.step()
    assert controllers["hero"].seen == []
    assert engine.state.outcome is None


def test_death_saves_kill_the_hero_and_the_ally_keeps_fighting(registry, cfg):
    controllers = {
        "hero": ScriptedController([]),
        "guard_1": ScriptedController([]),
        "goblin_1": ScriptedController([]),
    }
    engine = hero_and_guard(
        registry, cfg, rng=ScriptedRng(d20=[5, 5, 5]), controllers=controllers,
    )
    down_hero(engine, "hero", by="goblin_1")
    for _ in range(9):
        engine.step()
    assert engine.heroes["hero"].status == "dead"
    assert engine.state.outcome is None
    assert not engine.is_over


def test_no_flee_outside_the_exit_zone(registry, cfg):
    engine = duel(registry, cfg)
    assert "flee" not in option_ids(engine, "hero")


# end_combat

def test_end_combat_sets_ended_by_master(registry, cfg):
    engine = duel(registry, cfg)
    events = engine.end_combat()
    assert engine.state.outcome == "ended_by_master"
    assert engine.is_over
    assert types(events)[-1] == "combat_ended"


def test_end_combat_twice_is_an_error(registry, cfg):
    engine = duel(registry, cfg)
    engine.end_combat()
    with pytest.raises(ValueError):
        engine.end_combat()


# события, флаг, время

def test_combat_ended_event_has_exactly_the_id_key(registry, cfg):
    engine = finishing_blow(registry, cfg)
    events = engine.perform("hero", "attack:longsword:goblin_1")
    ended = [e for e in events if e.type == "combat_ended"]
    assert [e.data for e in ended] == [{"id": "fight_1"}]


def test_combat_ended_flag_is_set(registry, cfg):
    engine = finishing_blow(registry, cfg)
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.world.flags["combat_ended:fight_1"] is True


def test_no_flag_while_the_fight_goes_on(registry, cfg):
    engine = duel(registry, cfg)
    assert "combat_ended:fight_1" not in engine.world.flags


def test_combat_ended_is_the_last_event(registry, cfg):
    engine = finishing_blow(registry, cfg)
    events = engine.perform("hero", "attack:longsword:goblin_1")
    assert types(events)[-1] == "combat_ended"
    assert types(events).count("combat_ended") == 1


def test_time_advances_by_rounds_times_six_seconds(registry, cfg):
    controllers = {
        "hero": ScriptedController(["end_turn", "end_turn", "attack:longsword:goblin_1"]),
        "goblin_1": ScriptedController([]),
    }
    engine = finishing_blow(registry, cfg, controllers=controllers)
    start = engine.world.clock.now_s
    engine.run_to_end()
    assert engine.state.round == 3
    assert engine.world.clock.now_s == start + 3 * 6


def test_fight_ending_in_the_first_round_takes_one_round(registry, cfg):
    engine = finishing_blow(registry, cfg)
    start = engine.world.clock.now_s
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.world.clock.now_s == start + 6


def test_round_length_comes_from_the_config(registry):
    custom = load_rules_config(toml_text="[time]\nround_s = 10\n")
    engine = finishing_blow(registry, custom)
    start = engine.world.clock.now_s
    engine.perform("hero", "attack:longsword:goblin_1")
    assert engine.world.clock.now_s == start + 10


def test_clock_does_not_move_while_the_fight_goes_on(registry, cfg):
    controllers = {"hero": ScriptedController([]), "goblin_1": ScriptedController([])}
    engine = duel(registry, cfg, controllers=controllers)
    start = engine.world.clock.now_s
    for _ in range(4):
        engine.step()
    assert engine.world.clock.now_s == start


def test_end_combat_also_advances_the_clock(registry, cfg):
    engine = duel(registry, cfg)
    start = engine.world.clock.now_s
    engine.end_combat()
    assert engine.world.clock.now_s == start + 6


def test_run_to_end_does_not_advance_the_clock_on_round_limit(registry, cfg):
    controllers = {"hero": ScriptedController([]), "goblin_1": ScriptedController([])}
    engine = duel(registry, cfg, controllers=controllers)
    start = engine.world.clock.now_s
    with pytest.raises(CombatRoundLimit):
        engine.run_to_end(max_rounds=2)
    assert engine.world.clock.now_s == start
