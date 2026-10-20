# Ожидаемый API: ai_dm.game.combat_flow и бой в TurnRunner -- контракт в game_kit.py.
# Бой с мастером: start_combat -> ходы NPC до героя; preview_turn; ход героя номером (без модели) и
# текстом (combat_classify); NPC до следующего хода героя; combat_narrate после каждого хода;
# конец боя (опыт, флаг, сброс active_combat, закрытие сцены); defeat_outcome; hero_dead; сейв
# посреди боя.
import json

from game_kit import (
    SAVED_AT,
    ReactiveAdapter,
    attack_or_move_number,
    combat_of,
    core_dump,
    drive,
    end_turn_number,
    enemies_surrender,
    make_rig,
    number_of,
    option_ids,
    player_action_input,
    run_records,
    script_then_react,
    start_combat_call,
    state_of,
    text_step,
    tool_names,
    tools_step,
)
from master_kit import combat_ctx
from slots_kit import list_slots, saved_close_reason

from ai_dm.core.rng import Rng
from ai_dm.persistence.store import load_slot
from ai_dm.protocol.schema import tool_set

CLASSIFY = {"player_action", "unsupported_action"}
NARRATE = {d["name"] for d in tool_set("combat_narrate")}


def start_fight(registry, cfg, tmp_path, *, grakh=False, intent="kill", hazard=False, **reactive):
    steps = [
        tools_step(start_combat_call(grakh=grakh, intent=intent, hazard=hazard)),
        text_step("Гоблины бросаются на вас."),
    ]
    adapter = script_then_react(steps, **reactive)
    rig = make_rig(registry, cfg, tmp_path, adapter)
    result = rig.runner.play("Бью ногой дверь")
    assert result.committed is True
    return rig, result


def narrate_requests(adapter):
    return [r for r in adapter.requests if tool_names(r) == NARRATE]


def classify_requests(adapter):
    return [r for r in adapter.requests if tool_names(r) == CLASSIFY]


# advance_until_player

def engine_after_start(registry, cfg, seed):
    from ai_dm.combat.controllers import ScriptedController
    from ai_dm.combat.engine import CombatEngine

    ctx = combat_ctx(registry, cfg, rng=Rng(seed))
    bundle = ctx.bundle
    state = bundle.session.active_combat
    engine = CombatEngine(
        state, bundle.world, {"hero": bundle.heroes[0]}, registry, cfg, ctx.rng,
        controllers={"hero": ScriptedController([])},
    )
    engine.start()
    return engine


def seed_where(registry, cfg, hero_first):
    for seed in range(100):
        engine = engine_after_start(registry, cfg, seed)
        if (engine.state.initiative_order[0] == "hero") == hero_first:
            return seed
    raise AssertionError("не нашли сид с нужным порядком инициативы")


def test_advance_returns_nothing_when_hero_is_first(registry, cfg):
    from ai_dm.game.combat_flow import advance_until_player

    engine = engine_after_start(registry, cfg, seed_where(registry, cfg, hero_first=True))
    before = list(engine.state.log)
    assert advance_until_player(engine, "hero") == []
    assert engine.state.log == before
    assert engine.state.initiative_order[engine.state.turn_index] == "hero"


def test_advance_runs_npc_turns_until_hero(registry, cfg):
    from ai_dm.game.combat_flow import advance_until_player

    engine = engine_after_start(registry, cfg, seed_where(registry, cfg, hero_first=False))
    start_len = len(engine.state.log)
    lines = advance_until_player(engine, "hero")
    state = engine.state
    assert lines
    assert lines == state.log[start_len:]
    assert any("--- раунд 1, ход:" in line for line in lines)
    assert state.initiative_order[state.turn_index] == "hero"
    assert not engine.is_over


def test_advance_does_not_play_hero_turn(registry, cfg):
    from ai_dm.game.combat_flow import advance_until_player

    engine = engine_after_start(registry, cfg, seed_where(registry, cfg, hero_first=False))
    lines = advance_until_player(engine, "hero")
    assert not any("ход: Арн" in line for line in lines)
    assert engine.part("hero").turn.action is True


# старт боя в ходе вне боя

def test_start_combat_turn_leaves_active_combat(registry, cfg, tmp_path):
    rig, result = start_fight(registry, cfg, tmp_path)
    state = combat_of(rig.runner)
    assert state.id == "combat_1"
    assert state.round >= 1
    assert state.initiative_order
    assert {p.ref for p in state.participants} == {"hero", "g1", "g2"}
    assert result.narration == "Гоблины бросаются на вас."


def test_after_start_hero_is_next_to_act(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    state = combat_of(rig.runner)
    assert state.initiative_order[state.turn_index] == "hero"
    assert state.outcome is None


def test_start_combat_tool_result_carries_npc_turn_log(registry, cfg, tmp_path):
    rig, result = start_fight(registry, cfg, tmp_path)
    state = combat_of(rig.runner)
    block = rig.adapter.requests[1].messages[-1].content[0]
    body = json.loads(block.content)
    assert body["status"] == "accepted"
    assert "Бой начался" in state.log
    for line in state.log:
        assert line in body["log"]
    assert result.log == state.log


def test_start_turn_has_no_narrate_call(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    assert len(rig.adapter.requests) == 2
    assert narrate_requests(rig.adapter) == []


def test_combat_start_turn_is_recorded(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    record = rig.runner.bundle.memory.recent_turns[-1]
    assert record.requests == ["start_combat"]
    assert rig.runner.bundle.session.turn_seq == 1


# preview_turn

def test_preview_lists_hero_actions_with_end_turn_last(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    options = rig.runner.preview_turn()
    ids = [o.id for o in options]
    visible = [o.id for o in options if o.kind not in ("equip", "unequip")]
    assert visible[-1] == "end_turn"
    assert "move:hall" in ids
    assert all(o.label for o in options)
    assert len(set(ids)) == len(ids)


def test_preview_does_not_change_state_or_rng(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    before = rig.runner.bundle.model_dump_json()
    rng_before = rig.runner.bundle.world.rng
    rig.runner.preview_turn()
    assert rig.runner.bundle.model_dump_json() == before
    assert rig.runner.bundle.world.rng == rng_before


def test_preview_in_hazard_zone_leaves_no_trace(registry, cfg, tmp_path):
    # в начале хода героя в огне бросается спасбросок и пишется лог: на копии, не в бандле
    rig, _ = start_fight(registry, cfg, tmp_path, hazard=True)
    before = rig.runner.bundle.model_dump_json()
    rng_before = rig.runner.bundle.world.rng
    first = option_ids(rig.runner)
    assert option_ids(rig.runner) == first
    assert rig.runner.bundle.model_dump_json() == before
    assert rig.runner.bundle.world.rng == rng_before


def test_preview_in_hazard_zone_matches_real_turn(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.game import controllers

    rig, _ = start_fight(registry, cfg, tmp_path, hazard=True)
    preview = option_ids(rig.runner)
    seen = []
    original = controllers.PlayerController.choose

    def spy(self, options, point):
        seen.append([o.id for o in options])
        return original(self, options, point)

    monkeypatch.setattr(controllers.PlayerController, "choose", spy)
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert seen[0] == preview


def test_preview_is_repeatable(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    assert option_ids(rig.runner) == option_ids(rig.runner)


def test_preview_matches_options_of_real_turn(registry, cfg, tmp_path, monkeypatch):
    from ai_dm.game import controllers

    rig, _ = start_fight(registry, cfg, tmp_path)
    preview = option_ids(rig.runner)
    seen = []
    original = controllers.PlayerController.choose

    def spy(self, options, point):
        seen.append([o.id for o in options])
        return original(self, options, point)

    monkeypatch.setattr(controllers.PlayerController, "choose", spy)
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert seen
    assert seen[0] == preview


# ход героя номером

def test_number_turn_calls_model_only_for_narration(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    count = len(rig.adapter.requests)
    rig.runner.play(str(end_turn_number(rig.runner)))
    fresh = rig.adapter.requests[count:]
    assert len(fresh) == 1
    assert tool_names(fresh[0]) == NARRATE


def test_number_picks_the_listed_option(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    result = rig.runner.play(str(number_of(rig.runner, "move:hall")))
    assert result.committed is True
    state = combat_of(rig.runner)
    hero = [p for p in state.participants if p.ref == "hero"][0]
    assert hero.zone_id == "hall"


def test_number_turn_is_recorded_with_raw_input(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    number = end_turn_number(rig.runner)
    rig.runner.play(str(number))
    record = rig.runner.bundle.memory.recent_turns[-1]
    assert record.player_input == str(number)
    assert record.narration == "Бой идёт."
    assert rig.runner.bundle.session.turn_seq == 2


def test_after_hero_turn_npcs_act_until_hero_again(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    round_before = combat_of(rig.runner).round
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    state = combat_of(rig.runner)
    assert state.initiative_order[state.turn_index] == "hero"
    assert state.round == round_before + 1
    assert any("ход:" in line for line in result.log)
    ids = [i for i in option_ids(rig.runner) if not i.startswith(("equip:", "unequip:"))]
    assert ids[-1] == "end_turn"


def test_combat_log_of_turn_is_the_new_state_log_lines(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    before = len(combat_of(rig.runner).log)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.log == combat_of(rig.runner).log[before:]


def test_narration_follows_every_hero_turn(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    for _ in range(3):
        rig.runner.play(str(end_turn_number(rig.runner)))
    assert len(narrate_requests(rig.adapter)) == 3
    assert classify_requests(rig.adapter) == []


def test_narrate_request_carries_combat_log_of_the_turn(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    request = narrate_requests(rig.adapter)[-1]
    shown = state_of(request)["player_input"]
    assert result.log
    for line in result.log:
        assert line in shown


def test_number_turn_is_one_run_with_one_run_id(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 1
    assert records[0]["turn_status"] == "committed"


# ход героя текстом

def text_turn(registry, cfg, tmp_path, action, text="Бегу в зал", **kw):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[action], **kw)
    count = len(rig.adapter.requests)
    result = rig.runner.play(text)
    return rig, result, rig.adapter.requests[count:]


def test_text_turn_classifies_then_narrates(registry, cfg, tmp_path):
    rig, result, fresh = text_turn(
        registry, cfg, tmp_path, player_action_input(["move:hall"])
    )
    assert [tool_names(r) for r in fresh] == [CLASSIFY, CLASSIFY, NARRATE]
    assert state_of(fresh[0])["player_input"] == "Бегу в зал"
    assert result.requests[0] == "player_action"


def test_text_turn_executes_classified_steps(registry, cfg, tmp_path):
    rig, _, _ = text_turn(registry, cfg, tmp_path, player_action_input(["move:hall"]))
    hero = [p for p in combat_of(rig.runner).participants if p.ref == "hero"][0]
    assert hero.zone_id == "hall"


def test_text_turn_with_two_steps(registry, cfg, tmp_path):
    # бонусное действие и действие: оба шага выполнены в одном ходу героя, по порядку
    action = player_action_input(["second_wind", "dodge"])
    rig, result, _ = text_turn(registry, cfg, tmp_path, action)
    assert result.committed is True
    wind = [i for i, line in enumerate(result.log) if line.startswith("Арн: Второе дыхание")]
    dodge = [i for i, line in enumerate(result.log) if line == "Арн: уклонение"]
    assert wind
    assert dodge
    assert wind[0] < dodge[0]


def test_text_turn_all_calls_share_run_id(registry, cfg, tmp_path):
    rig, result, _ = text_turn(registry, cfg, tmp_path, player_action_input(["move:hall"]))
    records = run_records(rig.journal, result.run_id)
    assert len(records) == 3
    assert {r["turn_status"] for r in records} == {"committed"}


def test_text_turn_narrate_gets_player_text_and_log(registry, cfg, tmp_path):
    rig, result, fresh = text_turn(
        registry, cfg, tmp_path, player_action_input(["move:hall"])
    )
    shown = state_of(fresh[-1])["player_input"]
    assert "Бегу в зал" in shown
    for line in result.log:
        assert line in shown


def test_text_turn_improvise_goes_through_engine(registry, cfg, tmp_path):
    improvise = {
        "skill": "athletics", "category": "medium", "effect": "prone", "target": "g1",
        "zone": "",
    }
    rig, result, _ = text_turn(
        registry, cfg, tmp_path, player_action_input([], improvise=improvise),
        text="Опрокидываю бочку на гоблина",
    )
    assert result.committed is True
    assert any("импровизация (Лежит)" in line for line in combat_of(rig.runner).log)
    assert result.requests[0] == "player_action"


def test_unsupported_part_of_text_gets_missing_mechanic_tag(registry, cfg, tmp_path):
    action = player_action_input(["move:hall"])
    action["unsupported"] = "верхом на медведе"
    rig, result, _ = text_turn(registry, cfg, tmp_path, action)
    assert "missing-mechanic" in result.report_tags


# конец боя

def test_end_combat_by_master_resets_state_and_closes_scene(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    bundle = rig.runner.bundle
    assert result.committed is True
    assert bundle.session.active_combat is None
    assert bundle.world.flags["combat_ended:combat_1"] is True
    assert result.combat_outcome == "ended_by_master"
    assert saved_close_reason(tmp_path, "w1") == "combat_ended"
    assert bundle.session.current_scene.id == "scene_2"
    # P15: гоблины сдались (остались на ногах) -- опыт за всех
    from ai_dm.rules.xp import combat_xp

    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_end_combat_with_active_enemies_is_refused_and_combat_goes_on(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, end_combat=True)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert combat_of(rig.runner) is not None
    assert result.combat_outcome != "ended_by_master"
    assert "end_combat_refused" in result.report_tags


def test_end_of_combat_autosaves_closed_scene_without_combat(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert list_slots(tmp_path, "w1") == ["auto"]
    saved = load_slot(tmp_path, "w1", "auto")
    assert saved.session.active_combat is None
    assert saved.session.current_scene.closed_reason == "combat_ended"
    assert saved.world.flags["combat_ended:combat_1"] is True


def test_victory_gives_combat_xp_and_ends_fight(registry, cfg, tmp_path):
    from ai_dm.rules.xp import combat_xp

    rig, _ = start_fight(registry, cfg, tmp_path)
    results = drive(rig.runner, attack_or_move_number)
    last = results[-1]
    bundle = rig.runner.bundle
    assert all(r.committed for r in results)
    assert last.combat_outcome == "victory"
    assert bundle.session.active_combat is None
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)
    assert bundle.world.flags["combat_ended:combat_1"] is True
    assert saved_close_reason(tmp_path, "w1") == "combat_ended"
    assert list_slots(tmp_path, "w1") == ["auto"]


def test_xp_is_given_once_at_the_end_not_per_turn(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    xp = []
    for _ in range(60):
        if combat_of(rig.runner) is None:
            break
        rig.runner.play(str(attack_or_move_number(rig.runner)))
        xp.append(rig.runner.bundle.heroes[0].sheet.xp)
    assert xp[-1] == 100
    assert set(xp[:-1]) <= {0}


# поражение и смерть героя

def weaken_hero(rig):
    rig.runner.bundle.heroes[0].creature.hp_current = 1


def test_defeat_pending_requires_defeat_outcome(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, intent="capture", defeat="text_first")
    weaken_hero(rig)
    strength = rig.runner.bundle.heroes[0].sheet.abilities["str"]
    results = drive(rig.runner, end_turn_number)
    last = results[-1]
    assert last.committed is True
    assert last.combat_outcome == "defeat_pending"
    assert "defeat_outcome" in last.requests
    # первый ответ без обязательного инструмента отбракован: в запросе пояснение с именем
    notes = [
        r for r in narrate_requests(rig.adapter)
        if len(r.messages) == 3 and "defeat_outcome" in r.messages[-1].content[0].text
    ]
    assert notes
    hero = rig.runner.bundle.heroes[0]
    assert hero.scars == ["Шрам на плече"]
    assert hero.sheet.abilities["str"] == strength - 1


def test_defeat_closes_combat_and_scene(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, intent="capture")
    weaken_hero(rig)
    results = drive(rig.runner, end_turn_number)
    bundle = rig.runner.bundle
    assert results[-1].combat_outcome == "defeat_pending"
    assert bundle.session.active_combat is None
    assert bundle.world.flags["combat_ended:combat_1"] is True
    assert saved_close_reason(tmp_path, "w1") == "combat_ended"
    assert bundle.heroes[0].sheet.xp == 0


def test_defeat_without_defeat_outcome_rolls_back_the_turn(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, intent="capture", defeat="never")
    weaken_hero(rig)
    result = None
    for _ in range(60):
        before = rig.runner.bundle.model_dump_json()
        result = rig.runner.play(str(end_turn_number(rig.runner)))
        if not result.committed:
            break
    assert result.committed is False
    assert result.failure.reason == "invalid"
    assert rig.runner.bundle.model_dump_json() == before
    assert combat_of(rig.runner).outcome is None
    assert result.menu == ["retry", "switch_model", "save_and_quit"]


def test_hero_death_in_combat_is_reported(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, intent="kill")
    weaken_hero(rig)
    results = drive(rig.runner, end_turn_number)
    last = results[-1]
    assert last.committed is True
    assert last.combat_outcome == "hero_dead"
    assert last.hero_dead is True
    assert rig.runner.bundle.heroes[0].status == "dead"
    assert rig.runner.bundle.world.flags["hero_dead:hero"] is True
    assert rig.runner.bundle.session.active_combat is None
    assert rig.runner.bundle.heroes[0].sheet.xp == 0


def test_hero_alive_flag_is_false_in_normal_turns(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    assert rig.runner.play(str(end_turn_number(rig.runner))).hero_dead is False


# сейв посреди боя

def test_save_in_the_middle_of_fight_and_resume_is_identical(registry, cfg, tmp_path):
    from ai_dm.persistence.store import save_slot

    live, _ = start_fight(registry, cfg, tmp_path / "live")
    live.runner.play(str(end_turn_number(live.runner)))
    live.runner.play(str(number_of(live.runner, "move:hall")))
    assert combat_of(live.runner) is not None
    save_slot(tmp_path, live.runner.bundle, "manual-mid", saved_at=SAVED_AT)
    asked = len(live.adapter.requests)
    loaded = load_slot(tmp_path, "w1", "manual-mid")
    assert loaded.session.active_combat is not None
    mock = ReactiveAdapter()
    resumed = make_rig(registry, cfg, tmp_path / "res", mock, bundle=loaded)
    drive(live.runner, attack_or_move_number)
    drive(resumed.runner, attack_or_move_number)
    assert combat_of(live.runner) is None
    assert combat_of(resumed.runner) is None
    assert core_dump(resumed.runner.bundle) == core_dump(live.runner.bundle)
    live_requests = [r.model_dump_json() for r in live.adapter.requests[asked:]]
    assert live_requests == [r.model_dump_json() for r in mock.requests]


def test_bundle_with_active_combat_roundtrips_before_hero_turn(registry, cfg, tmp_path):
    # состояние на границе хода (решение героя) целиком лежит в сейве
    from ai_dm.persistence.store import save_slot

    rig, _ = start_fight(registry, cfg, tmp_path / "a")
    save_slot(tmp_path, rig.runner.bundle, "manual-b", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "w1", "manual-b")
    other = make_rig(registry, cfg, tmp_path / "b", ReactiveAdapter(), bundle=loaded)
    assert option_ids(other.runner) == option_ids(rig.runner)


# B1: смерть героя -- сцена не закрывается, автосейва нет

def test_hero_death_does_not_close_scene_or_autosave(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, intent="kill")
    weaken_hero(rig)
    last = drive(rig.runner, end_turn_number)[-1]
    scene = rig.runner.bundle.session.current_scene
    assert last.hero_dead is True
    assert saved_close_reason(tmp_path, "w1") is None
    assert scene.id == "scene_1"
    assert scene.closed_reason is None
    assert list_slots(tmp_path, "w1") == []


def test_hero_death_keeps_earlier_autosave_untouched(registry, cfg, tmp_path):
    from game_kit import settings

    from ai_dm.persistence.store import save_auto

    rig, _ = start_fight(registry, cfg, tmp_path, intent="kill")
    save_auto(tmp_path, rig.runner.bundle, saved_at=SAVED_AT, cfg=settings().rules)
    before = core_dump(load_slot(tmp_path, "w1", "auto"))
    weaken_hero(rig)
    drive(rig.runner, end_turn_number)
    assert rig.runner.bundle.heroes[0].status == "dead"
    assert core_dump(load_slot(tmp_path, "w1", "auto")) == before


# D1: бой не кончился за max_rounds -- откат хода и меню ошибки

def test_round_limit_is_turn_failure_with_error_menu(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    rig.runner.cfg = cfg.model_copy(deep=True)
    rig.runner.cfg.combat.max_rounds = 0
    before = rig.runner.bundle.model_dump_json()
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.committed is False
    assert result.failure.reason == "round_limit"
    assert result.menu == ["retry", "switch_model", "save_and_quit"]
    assert "tone" not in (result.hint or "")
    assert rig.runner.bundle.model_dump_json() == before
    records = run_records(rig.journal, result.run_id)
    assert {r["turn_status"] for r in records} <= {"aborted"}


# D2: нат-20 на спасброске от смерти в фазе NPC -- ход переходит к игроку

def dying_hero_engine(registry, cfg, rng, hero_controller, zones=None):
    from combat_kit import down_hero, make_engine, make_fighter, mon

    from ai_dm.combat.controllers import ScriptedController

    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], zones=zones, rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
        controllers={"hero": hero_controller, "goblin_1": ScriptedController([])},
    )
    down_hero(engine, "hero", by="goblin_1")
    return engine


def test_advance_stops_when_dying_hero_wakes_with_natural_20(registry, cfg):
    from combat_kit import ScriptedRng, hp, part

    from ai_dm.combat.controllers import ScriptedController
    from ai_dm.game.combat_flow import advance_until_player

    hero = ScriptedController([])
    rng = ScriptedRng(d20=[20])
    engine = dying_hero_engine(registry, cfg, rng, hero)
    engine.state.initiative_order = ["goblin_1", "hero"]
    advance_until_player(engine, "hero")
    state = engine.state
    assert state.initiative_order[state.turn_index] == "hero"
    assert hp(engine, "hero") == 1
    assert part(engine, "hero").status == "active"
    assert engine.is_capable("hero")
    assert hero.seen == []
    assert rng.left("d20") == 0


# D2: после пробуждения ход героя не начинается второй раз (опасная зона, заголовок, preview)

def hazard_zones():
    from combat_kit import feature, make_zones

    # СЛ 30: спасбросок опасности всегда провален -- повторный start_turn не остался бы незамеченным
    fire = feature("hazard", damage="1d4", damage_type="fire", save="dex", dc=30)
    return make_zones(hall=[fire])


def woken_hero(registry, cfg):
    from combat_kit import ScriptedRng

    from ai_dm.combat.controllers import ScriptedController
    from ai_dm.game.combat_flow import advance_until_player

    rng = ScriptedRng(d20=[20, 1, 1], d4=[1, 1, 1])
    engine = dying_hero_engine(
        registry, cfg, rng, ScriptedController([]), zones=hazard_zones()
    )
    engine.state.initiative_order = ["hero", "goblin_1"]
    advance_until_player(engine, "hero")
    return engine, rng


def header_count(engine):
    name = engine.name("hero")
    return len([
        line for line in engine.state.log
        if line.startswith("--- раунд") and f"ход: {name}" in line
    ])


def test_woken_hero_turn_is_started_once_in_hazard_zone(registry, cfg):
    from combat_kit import hp

    engine, rng = woken_hero(registry, cfg)
    assert hp(engine, "hero") == 1
    rolls_after_wake = len(rng.calls)
    engine.step()
    assert len(rng.calls) == rolls_after_wake
    assert hp(engine, "hero") == 1
    assert header_count(engine) == 1


def test_woken_hero_gets_at_most_one_hazard_check(registry, cfg):
    engine, rng = woken_hero(registry, cfg)
    engine.step()
    assert rng.calls.count("d20") <= 2
    assert rng.calls.count("d4") <= 1


def test_preview_after_wake_does_not_start_the_turn_again(registry, cfg):
    from combat_kit import hp

    from ai_dm.game.combat_flow import preview_options

    engine, _ = woken_hero(registry, cfg)
    bundle = make_woken_bundle(registry, engine)
    before = bundle.model_dump_json()
    options = [o.id for o in preview_options(bundle, registry, cfg)]
    assert "end_turn" in options
    assert hp(engine, "hero") == 1
    assert bundle.model_dump_json() == before
    assert header_count(engine) == 1


def make_woken_bundle(registry, engine):
    from protocol_kit import make_bundle

    bundle = make_bundle(registry)
    bundle.heroes = [engine.heroes["hero"].model_copy(deep=True)]
    bundle.session.active_combat = engine.state.model_copy(deep=True)
    return bundle


def test_woken_hero_after_save_and_load_keeps_the_same_turn(registry, cfg, tmp_path):
    from combat_kit import ScriptedRng

    from ai_dm.core.rng import Rng
    from ai_dm.game.combat_flow import make_engine, preview_options
    from ai_dm.game.controllers import PlayerController
    from ai_dm.persistence.store import save_slot
    from ai_dm.protocol.context import TurnContext

    engine, _ = woken_hero(registry, cfg)
    bundle = make_woken_bundle(registry, engine)
    save_slot(tmp_path, bundle, "manual-wake", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, "w1", "manual-wake")
    expected = [o.id for o in preview_options(bundle, registry, cfg)]
    assert [o.id for o in preview_options(loaded, registry, cfg)] == expected
    ctx = TurnContext(loaded, registry, cfg, ScriptedRng())
    resumed = make_engine(ctx, None, "r", "", PlayerController())
    resumed.step()
    state = loaded.session.active_combat
    name = resumed.name("hero")
    headers = [
        line for line in state.log if line.startswith("--- раунд") and f"ход: {name}" in line
    ]
    assert len(headers) == 1
    assert loaded.heroes[0].creature.hp_current == 1
    assert Rng.from_state(loaded.world.rng).draws == Rng.from_state(bundle.world.rng).draws


# D8 + P15: опыт за всех врагов (dead/down/fled/сдавшихся) при живом герое

def finished_bundle(registry, cfg, outcome, statuses):
    from master_kit import combat_ctx

    ctx = combat_ctx(registry, cfg)
    state = ctx.bundle.session.active_combat
    state.outcome = outcome
    for ref, status in statuses.items():
        [p for p in state.participants if p.ref == ref][0].status = status
    return ctx.bundle


def test_ended_by_master_gives_xp_for_dead_and_down_enemies(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.rules.xp import combat_xp

    bundle = finished_bundle(registry, cfg, "ended_by_master", {"g1": "dead", "g2": "down"})
    assert finish_combat(bundle, registry) == "ended_by_master"
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)
    assert bundle.session.active_combat is None


def test_ended_by_master_gives_xp_for_fled_enemy(registry, cfg):
    # P15: убежавший враг тоже даёт опыт
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.rules.xp import combat_xp

    bundle = finished_bundle(registry, cfg, "ended_by_master", {"g1": "dead", "g2": "fled"})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_ended_by_master_gives_xp_for_standing_enemies(registry, cfg):
    # P15: сдавшиеся (остались на ногах при ended_by_master) дают опыт
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.rules.xp import combat_xp

    bundle = finished_bundle(registry, cfg, "ended_by_master", {})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_victory_gives_xp_for_fled_enemy(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.rules.xp import combat_xp

    bundle = finished_bundle(registry, cfg, "victory", {"g1": "down", "g2": "fled"})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_all_enemies_fled_gives_xp_for_all(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.rules.xp import combat_xp

    bundle = finished_bundle(registry, cfg, "victory", {"g1": "fled", "g2": "fled"})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == combat_xp(["goblin_warrior", "goblin_warrior"], registry)


def test_defeat_pending_gives_no_xp_even_with_dead_enemies(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat

    bundle = finished_bundle(registry, cfg, "defeat_pending", {"g1": "dead", "g2": "fled"})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == 0


def test_finish_combat_remembers_defeated_for_loot(registry, cfg):
    # P16: добыча считается по врагам последнего завершённого боя
    from ai_dm.game.combat_flow import finish_combat

    bundle = finished_bundle(registry, cfg, "victory", {"g1": "dead", "g2": "fled"})
    finish_combat(bundle, registry)
    last = bundle.session.last_combat
    assert last.defeated == ["goblin_warrior", "goblin_warrior"]
    assert last.looted is False


def test_finish_combat_after_defeat_leaves_no_loot(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.state.session import LastCombat

    bundle = finished_bundle(registry, cfg, "defeat_pending", {"g1": "dead", "g2": "dead"})
    bundle.session.last_combat = LastCombat(defeated=["goblin_boss"])
    finish_combat(bundle, registry)
    assert bundle.session.last_combat is None


def test_new_combat_replaces_last_combat(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat
    from ai_dm.state.session import LastCombat

    bundle = finished_bundle(registry, cfg, "victory", {"g1": "dead", "g2": "dead"})
    bundle.session.last_combat = LastCombat(defeated=["goblin_boss"], looted=True)
    finish_combat(bundle, registry)
    assert bundle.session.last_combat.defeated == ["goblin_warrior", "goblin_warrior"]
    assert bundle.session.last_combat.looted is False


def test_dead_hero_gets_no_xp_even_with_dead_enemies(registry, cfg):
    from ai_dm.game.combat_flow import finish_combat

    bundle = finished_bundle(registry, cfg, "hero_dead", {"g1": "dead", "g2": "dead"})
    finish_combat(bundle, registry)
    assert bundle.heroes[0].sheet.xp == 0


# B4: combat.options в запросах мастера

def expected_options(runner):
    # рассказчику скрытые equip/unequip не показываются
    return [
        {"id": o.id, "label": o.label, "cost": o.cost} for o in runner.preview_turn()
        if o.kind not in ("equip", "unequip")
    ]


def test_classify_request_carries_options_of_the_boundary(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["end_turn"])])
    expected = expected_options(rig.runner)
    rig.runner.play("Жду")
    requests = classify_requests(rig.adapter)
    assert requests
    for request in requests:
        assert state_of(request)["combat"]["options"] == expected


def test_narrate_request_has_no_options_while_combat_goes_on(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert combat_of(rig.runner) is not None
    request = narrate_requests(rig.adapter)[-1]
    assert "options" not in state_of(request)["combat"]


def test_narrate_request_has_no_options_when_combat_ends(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    drive(rig.runner, attack_or_move_number)
    assert combat_of(rig.runner) is None
    assert "options" not in state_of(narrate_requests(rig.adapter)[-1])["combat"]


def test_system_prompt_has_no_options_and_prefix_is_stable(registry, cfg, tmp_path):
    actions = [player_action_input(["end_turn"]), player_action_input(["end_turn"])]
    rig, _ = start_fight(registry, cfg, tmp_path, classify=actions)
    rig.runner.play("Жду")
    rig.runner.play("Жду ещё")
    requests = classify_requests(rig.adapter)
    systems = [[b.model_dump_json() for b in r.system] for r in requests]
    assert len(systems) >= 4
    assert all(system == systems[0] for system in systems)
    assert "attack:longsword" not in "".join(systems[0])


def test_first_step_outside_options_is_retried_by_the_model(registry, cfg, tmp_path):
    # D3 на уровне хода: неизвестный первый шаг -- Invalid, модель переспрашивают и она отвечает
    def call(call_id, steps):
        return {"id": call_id, "name": "player_action", "input": player_action_input(steps)}

    steps = [
        tools_step(start_combat_call()), text_step("Гоблины бросаются на вас."),
        tools_step(call("pa-1", ["attack:longsword:ghost"])),
        tools_step(call("pa-2", ["end_turn"])), text_step("Принято."),
    ]
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps))
    rig.runner.play("Бью ногой дверь")
    result = rig.runner.play("Бью призрака")
    assert result.committed is True
    assert result.requests.count("player_action") == 1


# M5: свободный текст в бою -- ход открыт, пока основное действие не потрачено

def hero_zone_of(runner):
    return [p for p in combat_of(runner).participants if p.ref == "hero"][0].zone_id


def hero_is_up(runner):
    state = combat_of(runner)
    return state.initiative_order[state.turn_index] == "hero"


def test_text_without_action_step_keeps_turn_open(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["move:hall"])])
    round_before = combat_of(rig.runner).round
    result = rig.runner.play("Бегу в зал")
    assert result.committed is True
    assert hero_zone_of(rig.runner) == "hall"
    assert hero_is_up(rig.runner)
    assert combat_of(rig.runner).round == round_before
    assert not any("ход:" in line and "Арн" not in line for line in result.log)


def test_text_open_turn_menu_still_offers_action(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["move:hall"])])
    rig.runner.play("Бегу в зал")
    options = rig.runner.preview_turn()
    assert any(o.cost == "action" for o in options)
    assert not any(o.id == "move:hall" for o in options)
    visible = [o for o in options if o.kind not in ("equip", "unequip")]
    assert visible[-1].id == "end_turn"


def test_text_with_bonus_step_only_keeps_turn_open(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["second_wind"])])
    round_before = combat_of(rig.runner).round
    result = rig.runner.play("Перевожу дух")
    assert hero_is_up(rig.runner)
    assert combat_of(rig.runner).round == round_before
    assert not any("ход:" in line and "Арн" not in line for line in result.log)
    assert "second_wind" not in option_ids(rig.runner)


def test_text_open_turn_can_be_continued_by_number(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["move:hall"])])
    rig.runner.play("Бегу в зал")
    round_before = combat_of(rig.runner).round
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert combat_of(rig.runner).round == round_before + 1
    assert hero_is_up(rig.runner)


def test_text_with_action_step_closes_turn(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path, classify=[player_action_input(["dodge"])])
    round_before = combat_of(rig.runner).round
    result = rig.runner.play("Уклоняюсь")
    assert hero_is_up(rig.runner)
    assert combat_of(rig.runner).round == round_before + 1
    assert any("ход:" in line for line in result.log)


def test_text_move_and_action_closes_turn_with_unspent_move_left(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    rig.adapter.then.classify.append(player_action_input(["dodge", "move:hall"]))
    round_before = combat_of(rig.runner).round
    result = rig.runner.play("Уклоняюсь и отхожу")
    assert combat_of(rig.runner).round == round_before + 1
    assert any("ход:" in line for line in result.log)


def test_text_improvise_closes_turn(registry, cfg, tmp_path):
    improvise = {
        "skill": "athletics", "category": "medium", "effect": "prone", "target": "g1",
        "zone": "",
    }
    rig, _ = start_fight(
        registry, cfg, tmp_path,
        classify=[player_action_input([], improvise=improvise)],
    )
    round_before = combat_of(rig.runner).round
    result = rig.runner.play("Опрокидываю бочку на гоблина")
    assert combat_of(rig.runner).round == round_before + 1
    assert any("ход:" in line for line in result.log)


def test_number_with_bonus_step_still_keeps_turn_open(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    round_before = combat_of(rig.runner).round
    rig.runner.play(str(number_of(rig.runner, "move:hall")))
    assert hero_is_up(rig.runner)
    assert combat_of(rig.runner).round == round_before


# К1: строка концентрации с временем конца («до 14:05» -- время суток из until_s)

def held_bundle(registry, until_s):
    from protocol_kit import make_bundle

    from ai_dm.state.creature import Concentration

    bundle = make_bundle(registry)
    bundle.heroes[0].creature.concentration = Concentration(
        spell_id="hunters_mark", circle=1, until_s=until_s
    )
    return bundle


def test_concentration_line_shows_the_end_time(registry, cfg):
    from ai_dm.game.combat_flow import concentration_line

    bundle = held_bundle(registry, 14 * 3600 + 5 * 60)
    assert concentration_line(bundle, registry, cfg) == "Концентрация: Метка охотника до 14:05"


def test_concentration_line_wraps_the_end_time_to_the_day(registry, cfg):
    from ai_dm.game.combat_flow import concentration_line

    bundle = held_bundle(registry, 86400 + 3600 + 16 * 60)
    assert concentration_line(bundle, registry, cfg).endswith(" до 01:16")


def test_concentration_line_without_end_time_has_no_until(registry, cfg):
    from ai_dm.game.combat_flow import concentration_line

    bundle = held_bundle(registry, None)
    assert concentration_line(bundle, registry, cfg) == "Концентрация: Метка охотника"


def test_concentration_line_is_empty_without_concentration(registry, cfg):
    from protocol_kit import make_bundle

    from ai_dm.game.combat_flow import concentration_line

    assert concentration_line(make_bundle(registry), registry, cfg) == ""
