# Ожидаемый API: ai_dm.game.controllers (PlayerController, MasterChoiceController) -- контракт в
# game_kit.py. Герой: план шагов и импровизация через run_controller движка; ключевой NPC:
# intent_reconsider и ход через модель (npc_action), иначе EngineTactics; невалидно x3 ->
# TurnFailed. «Модель спрашивали про ход» живёт между ходами (контроллер пересоздаётся на ходу).
import pytest
from game_kit import (
    ReactiveAdapter,
    combat_of,
    drive,
    end_turn_number,
    make_rig,
    pick_bogus,
    requests_with_tools,
    script_then_react,
    scripted,
    start_combat_call,
    state_of,
    text_step,
    tools_step,
)
from master_kit import make_session
from protocol_kit import combat_request, goblin, make_ctx

from ai_dm.combat.controllers import EngineTactics, ScriptedController
from ai_dm.combat.downed import INTENT_OPTIONS
from ai_dm.combat.engine import CombatEngine
from ai_dm.core.rng import Rng
from ai_dm.master.session import TurnFailed
from ai_dm.protocol.apply import apply
from ai_dm.state.combat import DecisionPoint

NPC_ONLY = {"npc_action"}


def hero_engine(registry, cfg, seed=3, extra_controllers=None, request=None):
    ctx = make_ctx(registry, cfg, rng=Rng(seed), mode="combat_classify")
    apply(ctx, request or combat_request())
    bundle = ctx.bundle
    controllers = {"hero": ScriptedController([])}
    controllers.update(extra_controllers or {})
    engine = CombatEngine(
        bundle.session.active_combat, bundle.world, {"hero": bundle.heroes[0]}, registry, cfg,
        ctx.rng, controllers=controllers,
    )
    engine.start()
    return ctx, engine


def hero_turn_point(engine):
    options = engine.available_actions("hero")
    return options, DecisionPoint(
        kind="turn_action", actor="hero", options=[o.id for o in options]
    )


def hero_zone(engine):
    return engine.part("hero").zone_id


# PlayerController

def test_player_controller_returns_steps_then_end_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    controller = PlayerController(["dodge"])
    controller.attach(engine)
    assert controller.choose(options, point) == "dodge"
    rest = [o for o in options if o.cost != "action"]
    assert controller.choose(rest, point) == "end_turn"


def test_player_controller_without_plan_ends_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    controller = PlayerController()
    controller.attach(engine)
    rest = [o for o in options if o.cost != "action"]
    assert controller.choose(rest, point) == "end_turn"


def test_player_controller_plays_plan_through_engine(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    controller = PlayerController(["move:hall", "attack:longsword:g1"])
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert hero_zone(engine) == "hall"
    assert any(line.startswith("Арн -> ") for line in engine.state.log)
    assert engine.part("hero").turn.action is False


def test_player_controller_improvise_runs_dice_and_spends_action(registry, cfg):
    from ai_dm.game.controllers import PlayerController
    from ai_dm.protocol.requests import ImproviseSpec

    _, engine = hero_engine(registry, cfg)
    spec = ImproviseSpec(
        skill="athletics", category="medium", effect="prone", target="g1", zone=""
    )
    controller = PlayerController([], improvise=spec)
    controller.attach(engine)
    engine.controllers["hero"] = controller
    draws = engine.rng.draws
    engine.run_controller("hero")
    assert engine.rng.draws > draws
    assert any("импровизация (Лежит)" in line for line in engine.state.log)
    assert engine.part("hero").turn.action is False


def test_player_controller_improvise_then_steps(registry, cfg):
    from ai_dm.game.controllers import PlayerController
    from ai_dm.protocol.requests import ImproviseSpec

    _, engine = hero_engine(registry, cfg)
    spec = ImproviseSpec(
        skill="athletics", category="medium", effect="prone", target="g1", zone=""
    )
    controller = PlayerController(["move:hall"], improvise=spec)
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    log = engine.state.log
    assert any("импровизация (Лежит)" in line for line in log)
    assert hero_zone(engine) == "hall"
    first_improvise = [i for i, line in enumerate(log) if "импровизация" in line][0]
    first_move = [i for i, line in enumerate(log) if line.startswith("Арн идёт:")][0]
    assert first_improvise < first_move


def test_player_controller_improvise_is_done_once(registry, cfg):
    from ai_dm.game.controllers import PlayerController
    from ai_dm.protocol.requests import ImproviseSpec

    _, engine = hero_engine(registry, cfg)
    spec = ImproviseSpec(
        skill="athletics", category="medium", effect="prone", target="g1", zone=""
    )
    controller = PlayerController([], improvise=spec)
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    lines = [line for line in engine.state.log if "импровизация" in line]
    assert len(lines) == 1


# MasterChoiceController

def grakh_request(intent="capture"):
    return combat_request(
        enemies=[
            goblin("g1"),
            {"ref": "grakh", "monster_id": "goblin_boss", "zone": "hall", "group": "goblins"},
        ],
        groups=[{
            "id": "goblins", "leader": "grakh", "intent": intent,
            "lair_location_id": "goblin_den",
        }],
    )


def npc_call(choice, call_id="na-1"):
    return {
        "id": call_id, "name": "npc_action", "input": {"type": "npc_action", "choice": choice},
    }


def controller_rig(registry, cfg, tmp_path, steps, **kw):
    from ai_dm.game.controllers import MasterChoiceController

    adapter = scripted(steps)
    session, journal, ledger, sleeps = make_session(adapter, tmp_path)
    ctx = make_ctx(registry, cfg, rng=Rng(3), mode="combat_classify")
    apply(ctx, grakh_request(**kw))
    bundle = ctx.bundle
    controller = MasterChoiceController(ctx, session, run_id="run-7", world_text="Мир.")
    engine = CombatEngine(
        bundle.session.active_combat, bundle.world, {"hero": bundle.heroes[0]}, registry, cfg,
        ctx.rng, controllers={"hero": ScriptedController([]), "grakh": controller},
    )
    engine.start()
    controller.attach(engine)
    return controller, engine, adapter, journal


def grakh_turn(engine):
    options = engine.available_actions("grakh")
    return options, DecisionPoint(
        kind="turn_action", actor="grakh", options=[o.id for o in options]
    )


def reconsider_point():
    return DecisionPoint(
        kind="intent_reconsider", actor="grakh", options=list(INTENT_OPTIONS),
        subject="hero", attacker="g1",
    )


def test_intent_reconsider_asks_model_through_npc_action(registry, cfg, tmp_path):
    controller, _, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("intent:kill")), text_step("Решил.")]
    )
    assert controller.choose([], reconsider_point()) == "intent:kill"
    request = adapter.requests[0]
    assert {t.name for t in request.tools} == NPC_ONLY


def test_intent_reconsider_keep(registry, cfg, tmp_path):
    controller, _, _, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("keep")), text_step()]
    )
    assert controller.choose([], reconsider_point()) == "keep"


def test_npc_request_lists_every_option_on_its_own_line(registry, cfg, tmp_path):
    controller, _, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("keep")), text_step()]
    )
    controller.choose([], reconsider_point())
    lines = state_of(adapter.requests[0])["player_input"].splitlines()
    for option in INTENT_OPTIONS:
        assert f"- {option}" in lines


def test_npc_call_uses_given_run_id_and_world_text(registry, cfg, tmp_path):
    controller, _, adapter, journal = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("keep")), text_step()]
    )
    controller.choose([], reconsider_point())
    assert {r["run_id"] for r in journal.read_records()} == {"run-7"}
    assert "Мир." in adapter.requests[0].system[1].text


def test_npc_choice_is_not_state_change(registry, cfg, tmp_path):
    controller, engine, _, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("keep")), text_step()]
    )
    before = engine.world.model_dump_json()
    controller.choose([], reconsider_point())
    assert engine.world.model_dump_json() == before


def test_full_hp_turn_uses_engine_tactics_without_model(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(registry, cfg, tmp_path, [])
    options, point = grakh_turn(engine)
    expected = EngineTactics(engine).choose(options, point)
    assert controller.choose(options, point) == expected
    assert adapter.requests == []


def test_first_low_hp_turn_asks_model_with_turn_options(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("end_turn")), text_step("Отступает.")]
    )
    engine.creature("grakh").hp_current = 10
    options, point = grakh_turn(engine)
    assert controller.choose(options, point) == "end_turn"
    assert len(adapter.requests) == 2
    lines = state_of(adapter.requests[0])["player_input"].splitlines()
    for option in point.options:
        assert f"- {option}" in lines


def test_low_hp_model_is_asked_only_once(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("end_turn")), text_step("Отступает.")]
    )
    engine.creature("grakh").hp_current = 10
    options, point = grakh_turn(engine)
    controller.choose(options, point)
    asked = len(adapter.requests)
    expected = EngineTactics(engine).choose(options, point)
    # сценарий кончился: второй вызов модели упал бы ScriptExhausted
    assert controller.choose(options, point) == expected
    assert len(adapter.requests) == asked


def test_hp_just_above_threshold_does_not_ask_model(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(registry, cfg, tmp_path, [])
    # hp_max 21: 11 -- чуть больше 50%
    engine.creature("grakh").hp_current = 11
    options, point = grakh_turn(engine)
    controller.choose(options, point)
    assert adapter.requests == []


def test_hp_at_threshold_asks_model(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("end_turn")), text_step()]
    )
    engine.creature("grakh").hp_current = 10
    controller.choose(*grakh_turn(engine))
    assert adapter.requests


def test_threshold_comes_from_config_and_is_inclusive(registry, cfg, tmp_path):
    controller, engine, adapter, _ = controller_rig(
        registry, cfg, tmp_path, [tools_step(npc_call("end_turn")), text_step()]
    )
    # 100%: полное здоровье (hp == hp_max) уже «не больше порога»
    controller.session.app_cfg.master.key_npc_consult_hp_percent = 100
    controller.choose(*grakh_turn(engine))
    assert adapter.requests


def test_reconsider_does_not_use_up_the_turn_consultation(registry, cfg, tmp_path):
    steps = [
        tools_step(npc_call("keep", "a")), text_step(),
        tools_step(npc_call("end_turn", "b")), text_step(),
    ]
    controller, engine, adapter, _ = controller_rig(registry, cfg, tmp_path, steps)
    controller.choose([], reconsider_point())
    engine.creature("grakh").hp_current = 5
    options, point = grakh_turn(engine)
    assert controller.choose(options, point) == "end_turn"
    assert len(requests_with_tools(adapter, NPC_ONLY)) == 4


def test_three_invalid_answers_fail_the_turn(registry, cfg, tmp_path):
    steps = [tools_step(npc_call("bogus", f"x{i}")) for i in range(3)]
    controller, _, _, _ = controller_rig(registry, cfg, tmp_path, steps)
    with pytest.raises(TurnFailed) as info:
        controller.choose([], reconsider_point())
    assert info.value.reason == "invalid"


def test_two_invalid_answers_then_valid_one_is_accepted(registry, cfg, tmp_path):
    steps = [
        tools_step(npc_call("bogus", "x1")), tools_step(npc_call("bogus", "x2")),
        tools_step(npc_call("keep", "x3")), text_step(),
    ]
    controller, _, _, _ = controller_rig(registry, cfg, tmp_path, steps)
    assert controller.choose([], reconsider_point()) == "keep"


# ключевой NPC в ходе боя (TurnRunner)

def fight_with_grakh(registry, cfg, tmp_path, *, intent="capture", **reactive):
    steps = [
        tools_step(start_combat_call(grakh=True, intent=intent)), text_step("Бой начался."),
    ]
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps, **reactive))
    assert rig.runner.play("Нападаю").committed is True
    return rig


def test_grakh_is_external_and_alive_in_combat(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path)
    boss = [p for p in combat_of(rig.runner).participants if p.ref == "grakh"][0]
    assert boss.controller == "external"
    assert rig.runner.bundle.world.npcs["grakh"].creature.hp_max == 21


def test_healthy_key_npc_never_asks_model_for_turns(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path)
    for _ in range(3):
        rig.runner.play(str(end_turn_number(rig.runner)))
    assert requests_with_tools(rig.adapter, NPC_ONLY) == []


def test_wounded_key_npc_asks_model_once_per_fight(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path)
    rig.runner.bundle.world.npcs["grakh"].creature.hp_current = 10
    first = rig.runner.play(str(end_turn_number(rig.runner)))
    asked = requests_with_tools(rig.adapter, NPC_ONLY)
    assert len(asked) == 2
    assert "- end_turn" in state_of(asked[0])["player_input"].splitlines()
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert len(requests_with_tools(rig.adapter, NPC_ONLY)) == 2
    assert first.committed is True


def test_npc_call_shares_run_id_with_narration(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path)
    rig.runner.bundle.world.npcs["grakh"].creature.hp_current = 10
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    records = [r for r in rig.journal.read_records() if r["run_id"] == result.run_id]
    # npc_action + его завершающий ответ + повествование
    assert len(records) == 3
    assert {r["turn_status"] for r in records} == {"committed"}


def test_three_invalid_npc_answers_roll_back_whole_turn(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path, npc_pick=pick_bogus)
    rig.runner.bundle.world.npcs["grakh"].creature.hp_current = 10
    number = [o.id for o in rig.runner.preview_turn()].index("move:hall") + 1
    assert rig.runner.play(str(number)).committed is True
    before = rig.runner.bundle.model_dump_json()
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.committed is False
    assert result.failure.reason == "invalid"
    assert rig.runner.bundle.model_dump_json() == before
    hero = [p for p in combat_of(rig.runner).participants if p.ref == "hero"][0]
    assert hero.zone_id == "hall"
    assert result.menu == ["retry", "switch_model", "save_and_quit"]
    assert {r["turn_status"] for r in rig.journal.read_records()
            if r["run_id"] == result.run_id} == {"aborted"}


def test_key_npc_is_asked_when_hero_falls_and_may_keep_intent(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path, intent="capture", defeat="call")
    rig.runner.bundle.heroes[0].creature.hp_current = 1
    results = drive(rig.runner, end_turn_number)
    asked = requests_with_tools(rig.adapter, NPC_ONLY)
    reconsider = [
        r for r in asked
        if "- intent:kill" in state_of(r)["player_input"].splitlines()
    ]
    assert reconsider
    assert "- keep" in state_of(reconsider[0])["player_input"].splitlines()
    assert results[-1].combat_outcome == "defeat_pending"


def test_key_npc_can_change_intent_to_kill(registry, cfg, tmp_path):
    def pick_kill(options):
        return "intent:kill" if "intent:kill" in options else options[-1]

    rig = fight_with_grakh(registry, cfg, tmp_path, intent="capture", npc_pick=pick_kill)
    rig.runner.bundle.heroes[0].creature.hp_current = 1
    results = drive(rig.runner, end_turn_number)
    lines = [line for r in results for line in r.log]
    assert any("меняет намерение: убить" in line for line in lines)
    assert results[-1].combat_outcome == "hero_dead"
    assert results[-1].hero_dead is True


def test_reactive_default_pick_keeps_intent(registry, cfg, tmp_path):
    rig = fight_with_grakh(registry, cfg, tmp_path, intent="capture")
    rig.runner.bundle.heroes[0].creature.hp_current = 1
    results = drive(rig.runner, end_turn_number)
    lines = [line for r in results for line in r.log]
    assert not any("меняет намерение" in line for line in lines)
    assert ReactiveAdapter().npc_pick(["keep", "intent:kill"]) == "keep"


# M5: свободный текст держит ход открытым, пока основное действие не потрачено

def spent_action_point(engine):
    engine.perform("hero", "dodge")
    return hero_turn_point(engine)


def test_text_plan_without_action_holds_turn_after_steps(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    controller = PlayerController(["move:hall"])
    controller.attach(engine)
    assert controller.choose(options, point) == "move:hall"
    engine.perform("hero", "move:hall")
    options, point = hero_turn_point(engine)
    assert controller.choose(options, point) == "hold"


def test_text_bonus_step_holds_turn_while_action_is_left(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    controller = PlayerController(["second_wind"])
    controller.attach(engine)
    assert controller.choose(options, point) == "second_wind"
    engine.perform("hero", "second_wind")
    options, point = hero_turn_point(engine)
    assert controller.choose(options, point) == "hold"


def test_text_plan_with_spent_action_ends_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = spent_action_point(engine)
    assert any(o.cost in ("bonus", "move") for o in options)
    controller = PlayerController(["move:hall"])
    controller.attach(engine)
    assert controller.choose(options, point) == "move:hall"
    assert controller.choose(options, point) == "end_turn"


def test_text_plan_ends_turn_when_action_step_was_the_last(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    controller = PlayerController(["move:hall", "attack:longsword:g1"])
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert engine.part("hero").turn.action is False
    assert engine.held is False


def test_text_plan_without_action_step_sets_held_in_engine(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    controller = PlayerController(["move:hall"])
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert hero_zone(engine) == "hall"
    assert engine.part("hero").turn.action is True
    assert engine.held is True


def test_text_improvise_spends_action_and_ends_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController
    from ai_dm.protocol.requests import ImproviseSpec

    _, engine = hero_engine(registry, cfg)
    spec = ImproviseSpec(
        skill="athletics", category="medium", effect="prone", target="g1", zone=""
    )
    controller = PlayerController([], improvise=spec)
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert engine.part("hero").turn.action is False
    assert engine.held is False


def test_text_skipped_unavailable_step_still_holds_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    controller = PlayerController(["no_such_step"])
    controller.attach(engine)
    assert controller.choose(options, point) == "hold"
    assert any("no_such_step" in line for line in engine.state.log)


def test_number_hold_unchanged_with_spent_action_and_bonus_left(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = spent_action_point(engine)
    controller = PlayerController(["second_wind"], hold=True)
    controller.attach(engine)
    assert controller.choose(options, point) == "second_wind"
    assert controller.choose(options, point) == "hold"


def test_number_hold_ends_turn_when_only_end_turn_is_left(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    _, engine = hero_engine(registry, cfg)
    options, point = hero_turn_point(engine)
    only_end = [o for o in options if o.id == "end_turn"]
    controller = PlayerController([], hold=True)
    controller.attach(engine)
    assert controller.choose(only_end, point) == "end_turn"


def test_text_rejected_improvise_keeps_turn_open(registry, cfg):
    from ai_dm.game.controllers import PlayerController
    from ai_dm.protocol.requests import ImproviseSpec

    _, engine = hero_engine(registry, cfg)
    own_zone = engine.part("g1").zone_id
    spec = ImproviseSpec(
        skill="athletics", category="medium", effect="push", target="g1", zone=own_zone
    )
    controller = PlayerController([], improvise=spec)
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert engine.part("hero").turn.action is True
    assert engine.held is True
    assert any("импровизация невозможна" in line for line in engine.state.log)


# M5 и Extra Attack: после первой атаки ход открыт, после второй закрыт

def ranger_extra_attack_engine(registry, cfg):
    from combat_kit import ScriptedRng, make_engine, mon

    from ai_dm.game.starter import ranger_choices
    from ai_dm.rules.builder import build_character
    from ai_dm.rules.progression import sync_resources

    hero = build_character(ranger_choices("hero"), registry)
    hero.sheet.feats = [f for f in hero.sheet.feats if f != "savage_attacker"]
    hero.sheet.primary.level = 5
    sync_resources(hero, registry)
    rng = ScriptedRng(d20=[15, 15], d8=[5, 5])
    monsters = [mon("goblin_1", "goblin_warrior", "hall")]
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng, monsters=monsters, hero_zone="door"
    )
    engine.creature("goblin_1").hp_max = 40
    engine.creature("goblin_1").hp_current = 30
    return engine


def test_text_attack_with_extra_attack_left_keeps_turn_open(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    engine = ranger_extra_attack_engine(registry, cfg)
    shoot = "attack:longbow:goblin_1"
    controller = PlayerController([shoot])
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert engine.part("hero").turn.action is False
    assert engine.part("hero").turn.attacks_left == 1
    assert engine.held is True


def test_text_second_attack_closes_turn(registry, cfg):
    from ai_dm.game.controllers import PlayerController

    engine = ranger_extra_attack_engine(registry, cfg)
    shoot = "attack:longbow:goblin_1"
    controller = PlayerController([shoot, shoot])
    controller.attach(engine)
    engine.controllers["hero"] = controller
    engine.run_controller("hero")
    assert engine.part("hero").turn.attacks_left == 0
    assert engine.held is False
