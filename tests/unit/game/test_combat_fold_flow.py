# Р1 «Память боя» (R1-PLAN, сквозные тесты): свёртка промежуточных ходов боя в recent_turns на
# настоящем TurnRunner/GameApp с ReactiveAdapter. Запись боя: [старт, свёртка, финал]; старт и
# финал дословно, короткие бои (< 2 промежуточных) не меняются. Решения: В6б (смерть героя тоже
# сворачивает, но сейвы не трогаются), Q1а (старт ищется по всему recent_turns).
import json

from game_kit import (
    NOW,
    SAVED_AT,
    attack_or_move_number,
    combat_of,
    drive,
    end_turn_number,
    enemies_surrender,
    make_app,
    make_bundle,
    make_rig,
    script_then_react,
    scripted,
    settings,
    start_combat_call,
    state_of,
    text_step,
    tools_step,
)
from slots_kit import list_slots, saved_close_reason
from summarizer_kit import ReactiveSummarizer, summ_fail_steps, summ_steps

from ai_dm.core.rng import Rng
from ai_dm.persistence.store import load_slot, save_auto
from ai_dm.state.scene import TurnRecord

FOLD = "Свёрнуты ходы"
FINAL = "Бой идёт."
OPEN = "Бью ногой дверь"


def start_steps(intent="kill"):
    return [tools_step(start_combat_call(intent=intent)), text_step("Гоблины бросаются на вас.")]


def start_rig(registry, cfg, tmp_path, *, intent="kill", hp=None, bundle=None, **reactive):
    bundle = bundle or make_bundle(registry)
    if hp is not None:
        bundle.heroes[0].creature.hp_current = hp
    adapter = script_then_react(start_steps(intent), **reactive)
    rig = make_rig(registry, cfg, tmp_path, adapter, bundle=bundle)
    result = rig.runner.play(OPEN)
    assert result.committed is True
    return rig


def start_app(registry, tmp_path, *, intent="kill", hp=None, **reactive):
    adapter = script_then_react(start_steps(intent), **reactive)
    app = make_app(registry, tmp_path, adapter)
    if hp is not None:
        app.bundle.heroes[0].creature.hp_current = hp
    assert app.handle(OPEN).turn.committed is True
    return app


def turns_of(rig):
    return rig.runner.bundle.memory.recent_turns


def folds_of(rig):
    return [t for t in turns_of(rig) if t.narration.startswith(FOLD)]


def win(rig):
    results = drive(rig.runner, attack_or_move_number)
    assert results[-1].combat_outcome == "victory"
    return results


# победа за много ходов

def test_victory_leaves_start_fold_final(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    results = win(rig)
    assert len(results) >= 4
    turns = turns_of(rig)
    assert len(turns) == 3
    assert "start_combat" in turns[0].requests
    assert turns[1].narration.startswith(FOLD)
    assert turns[1].requests == []


def test_victory_final_record_is_verbatim(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    results = win(rig)
    final = turns_of(rig)[-1]
    assert final.narration == results[-1].narration
    assert final.requests == results[-1].requests


def test_victory_start_record_is_verbatim(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    before = turns_of(rig)[0].model_copy(deep=True)
    win(rig)
    assert turns_of(rig)[0] == before
    assert turns_of(rig)[0].player_input == OPEN


def test_fold_turn_seq_is_the_one_before_final(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    win(rig)
    turns = turns_of(rig)
    assert turns[1].turn_seq == turns[2].turn_seq - 1
    assert turns[1].player_input == ""


def test_fold_text_has_outcome_enemies_and_rounds(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    win(rig)
    text = turns_of(rig)[1].narration
    assert "победа" in text
    assert "Воин-гоблин 1" in text
    assert "Воин-гоблин 2" in text
    assert "раундов:" in text
    assert "убит" in text


def test_fold_range_starts_after_the_start_record(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    win(rig)
    turns = turns_of(rig)
    first = turns[0].turn_seq + 1
    assert f"{FOLD} {first}–{turns[1].turn_seq}." in turns[1].narration


def test_records_before_the_fight_are_not_touched(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    old = [TurnRecord(turn_seq=i, at_s=0, player_input=f"в{i}", narration=f"р{i}",
                      scene_id="scene_1") for i in (-2, -1)]
    bundle.memory.recent_turns = [r.model_copy(deep=True) for r in old]
    rig = start_rig(registry, cfg, tmp_path, bundle=bundle)
    win(rig)
    turns = turns_of(rig)
    assert turns[:2] == old
    assert len(turns) == 5


def test_victory_fold_has_trophies_from_last_combat(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    win(rig)
    assert rig.runner.bundle.session.last_combat.gear
    assert "трофеи:" in turns_of(rig)[1].narration


def test_fold_text_notes_wounds_of_hero(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path, hp=150)
    win(rig)
    creature = rig.runner.bundle.heroes[0].creature
    assert creature.hp_current < creature.hp_max
    text = turns_of(rig)[1].narration
    assert f"потери: Арн HP {creature.hp_current}/{creature.hp_max}" in text


# короткие бои

def test_end_combat_on_first_hero_turn_has_no_fold(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.combat_outcome == "ended_by_master"
    turns = turns_of(rig)
    assert len(turns) == 2
    assert "start_combat" in turns[0].requests
    assert "end_combat" in turns[1].requests
    assert folds_of(rig) == []


def test_one_middle_turn_has_no_fold(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    rig.runner.play(str(attack_or_move_number(rig.runner)))
    rig.adapter.then.end_combat = True
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.combat_outcome == "ended_by_master"
    assert len(turns_of(rig)) == 3
    assert folds_of(rig) == []


def test_two_middle_turns_fold(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    for _ in range(2):
        rig.runner.play(str(attack_or_move_number(rig.runner)))
    rig.adapter.then.end_combat = True
    enemies_surrender(rig.runner)
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert len(turns_of(rig)) == 3
    assert len(folds_of(rig)) == 1


# конец боя в ходе исследования

def test_fight_started_and_ended_in_one_turn_is_not_folded(registry, cfg, tmp_path):
    # герой падает до своего решения (seed 6, hp 1): сворачивать нечего, старый бой не трогаем
    bundle = make_bundle(registry)
    bundle.world.rng = Rng(6).state
    old = [
        TurnRecord(turn_seq=i, at_s=0, player_input=f"в{i}", narration=f"р{i}",
                   requests=["start_combat"] if i == 1 else [], scene_id="scene_1")
        for i in (1, 2, 3)
    ]
    bundle.memory.recent_turns = [r.model_copy(deep=True) for r in old]
    bundle.heroes[0].creature.hp_current = 1
    adapter = script_then_react(start_steps())
    rig = make_rig(registry, cfg, tmp_path, adapter, bundle=bundle)
    result = rig.runner.play(OPEN)
    assert result.combat_outcome == "hero_dead"
    turns = turns_of(rig)
    assert turns[:3] == old
    assert len(turns) == 4
    assert "start_combat" in turns[3].requests
    assert folds_of(rig) == []


# завершён мастером, поражение, смерть

def test_ended_by_master_after_three_turns_names_surrendered(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    for _ in range(3):
        rig.runner.play(str(attack_or_move_number(rig.runner)))
    assert combat_of(rig.runner) is not None
    rig.adapter.then.end_combat = True
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.combat_outcome == "ended_by_master"
    turns = turns_of(rig)
    assert len(turns) == 3
    assert "завершён мастером" in turns[1].narration
    assert "сдался" in turns[1].narration
    assert "end_combat" in turns[2].requests


def test_defeat_pending_folds_without_trophies(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path, intent="capture", hp=40)
    results = drive(rig.runner, end_turn_number)
    assert results[-1].combat_outcome == "defeat_pending"
    assert len(results) >= 3
    turns = turns_of(rig)
    assert len(turns) == 3
    assert "поражение" in turns[1].narration
    assert "трофеи" not in turns[1].narration
    assert "HP 0/" in turns[1].narration or "без сознания" in turns[1].narration
    assert "defeat_outcome" in turns[2].requests


def test_hero_death_folds_in_session_memory(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path, intent="kill", hp=40)
    results = drive(rig.runner, end_turn_number)
    assert results[-1].hero_dead is True
    assert len(results) >= 3
    turns = turns_of(rig)
    assert len(turns) == 3
    assert "герой погиб" in turns[1].narration
    assert "HP 0/" in turns[1].narration


def test_hero_death_changes_neither_scene_nor_slots(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path, intent="kill", hp=40)
    drive(rig.runner, end_turn_number)
    assert rig.runner.bundle.session.current_scene.closed_reason is None
    assert list_slots(tmp_path, "w1") == []
    assert folds_of(rig)


def test_hero_death_load_last_save_returns_world_without_fold(registry, cfg, tmp_path):
    app = start_app(registry, tmp_path, intent="kill", hp=40)
    save_auto(tmp_path, app.bundle, saved_at=SAVED_AT, cfg=settings().rules)
    saved = load_slot(tmp_path, "w1", "auto").memory.recent_turns
    while app.pending is None and combat_of(app.runner) is not None:
        app.handle(str(end_turn_number(app.runner)))
    assert app.pending == "hero_dead"
    assert any(t.narration.startswith(FOLD) for t in app.bundle.memory.recent_turns)
    app.choose("load_last_save")
    loaded = app.bundle.memory.recent_turns
    assert loaded == saved
    assert not any(t.narration.startswith(FOLD) for t in loaded)
    assert len(loaded) == 1


def test_report_after_death_shows_the_fold(registry, cfg, tmp_path):
    from ai_dm.reports.markdown import recent_lines

    app = start_app(registry, tmp_path, intent="kill", hp=40)
    while app.pending is None and combat_of(app.runner) is not None:
        app.handle(str(end_turn_number(app.runner)))
    lines = recent_lines(app.runner.last_capture, 5)
    assert any(line.startswith(FOLD) for line in lines)


# Q1а: старт в прошлой сцене и обрезанный список

def test_start_in_previous_scene_after_turn_limit_boundary(registry, cfg, tmp_path):
    bundle = make_bundle(registry)
    bundle.session.current_scene.player_turns = cfg.scene.max_player_turns
    rig = start_rig(registry, cfg, tmp_path, bundle=bundle)
    start_scene = rig.runner.bundle.session.current_scene
    assert start_scene.id == "scene_2"
    win(rig)
    turns = turns_of(rig)
    assert len(folds_of(rig)) == 1
    assert [t.scene_id for t in turns] == ["scene_1", "scene_2", "scene_2"]
    assert "start_combat" in turns[0].requests
    assert turns[0].player_input == OPEN
    assert not turns[1].requests


def test_start_trimmed_by_keep_folds_whole_current_scene(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    rig.runner.app_cfg.master.recent_turns_keep = 3
    results = win(rig)
    assert len(results) >= 4
    turns = turns_of(rig)
    assert not any("start_combat" in t.requests for t in turns)
    assert len(turns) == 2
    assert turns[0].narration.startswith(FOLD)
    assert turns[1].narration == results[-1].narration


# граница после боя

def test_autosave_after_victory_holds_the_fold(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    win(rig)
    assert saved_close_reason(tmp_path, "w1") == "combat_ended"
    saved = load_slot(tmp_path, "w1", "auto").memory.recent_turns
    assert [t.narration.startswith(FOLD) for t in saved] == [False, True, False]


def summ_rig(registry, cfg, tmp_path, summarizer):
    from ai_dm.game.turn import TurnRunner
    from ai_dm.llm.cost import CostLedger
    from ai_dm.llm.journal import Journal

    app = settings().app
    bundle = make_bundle(registry)
    narrator = script_then_react(start_steps())
    journal = Journal(tmp_path, bundle.world.world_id, app.journal)
    ledger = CostLedger(tmp_path, bundle.world.world_id)
    runner = TurnRunner(
        bundle, registry, cfg, app, narrator, saves_root=tmp_path, journal=journal,
        ledger=ledger, sleeper=lambda s: None, now=lambda: NOW, run_tag="t",
        summarizer_adapter=summarizer,
    )
    assert runner.play(OPEN).committed is True
    return runner


def summarizer_turns(summarizer):
    request = next(r for r in summarizer.requests if r.role == "summarizer")
    return json.loads(request.messages[0].content[0].text)["turns"]


def test_summarizer_gets_the_fold_instead_of_middle_turns(registry, cfg, tmp_path):
    summarizer = ReactiveSummarizer()
    runner = summ_rig(registry, cfg, tmp_path, summarizer)
    results = drive(runner, attack_or_move_number)
    assert results[-1].combat_outcome == "victory"
    turns = summarizer_turns(summarizer)
    assert len(turns) == 3
    assert turns[1]["player_input"] == ""
    assert turns[1]["narration"].startswith(FOLD)
    assert turns[2]["narration"] == results[-1].narration
    assert [t["narration"] for t in turns].count(FINAL) == 1


def test_failed_boundary_bundle_already_has_fold_and_retry_keeps_one(registry, cfg, tmp_path):
    summarizer = scripted(summ_fail_steps() + summ_steps("После повтора."))
    runner = summ_rig(registry, cfg, tmp_path, summarizer)
    results = drive(runner, attack_or_move_number)
    assert results[-1].boundary_failed is True
    assert runner.bundle.session.boundary_pending is True
    assert sum(t.narration.startswith(FOLD) for t in runner.bundle.memory.recent_turns) == 1
    runner.retry()
    assert runner.bundle.session.boundary_pending is False
    assert sum(t.narration.startswith(FOLD) for t in runner.bundle.memory.recent_turns) == 1


# рассказчик видит свёртку

def test_next_narrator_request_has_start_fold_final_without_middle(registry, cfg, tmp_path):
    rig = start_rig(registry, cfg, tmp_path)
    results = win(rig)
    rig.runner.play("Осматриваюсь")
    sent = state_of(rig.adapter.requests[-1])["recent_turns"]
    narrations = [t["narration"] for t in sent]
    assert narrations[0] == "Гоблины бросаются на вас."
    assert narrations[1].startswith(FOLD)
    assert narrations[2] == results[-1].narration
    assert narrations.count(FINAL) == 1


# релевантность: имя противника остаётся в тексте после свёртки

def test_named_enemy_stays_relevant_through_the_fold_text(registry, cfg, tmp_path):
    from ai_dm.game.combat_fold import fold_fight
    from ai_dm.master.relevance import npc_reasons
    from ai_dm.state.combat import CombatState, Group, Participant
    from ai_dm.state.world import NPC

    bundle = make_bundle(registry)
    bundle.world.npcs["grakh2"] = NPC(id="grakh2", name="Гракх", named=True, means=["m"])
    bundle.memory.recent_turns = [
        TurnRecord(turn_seq=i, at_s=0, player_input="бью", narration="Удар.",
                   requests=["start_combat"] if i == 1 else [], scene_id="scene_1")
        for i in (1, 2, 3)
    ]
    state = CombatState(
        id="c", zones=[], groups={"g": Group(leader_id="b")}, round=2, outcome="victory",
        participants=[
            Participant(ref="hero", side="heroes", group_id="party", name="Арн"),
            Participant(ref="b", side="enemies", group_id="g", name="Гракх", status="dead",
                        monster_id="goblin_boss"),
        ],
    )
    assert "grakh2" not in npc_reasons(bundle)
    assert fold_fight(bundle, state, registry) is True
    assert "said" in npc_reasons(bundle)["grakh2"]


# переговоры считаются до свёртки (end_fight зовёт settle_parley с настройками)

def test_surrendered_named_npc_gets_attitude_at_the_end_of_the_fight(registry, cfg, tmp_path):
    from ai_dm.state.world import NPC

    rig = start_rig(registry, cfg, tmp_path, end_combat=True)
    bundle = rig.runner.bundle
    bundle.world.npcs["g1"] = NPC(id="g1", name="Гоблин g1", means=["бой"])
    [p for p in combat_of(rig.runner).participants if p.ref == "g1"][0].status = "surrendered"
    rig.runner.play(str(end_turn_number(rig.runner)))
    assert combat_of(rig.runner) is None
    assert rig.runner.bundle.world.npcs["g1"].attitude == cfg.parley.surrender_attitude
