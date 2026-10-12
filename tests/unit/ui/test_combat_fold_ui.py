# Р1: после боя со свёрткой UI читает recent_turns как есть -- последняя запись остаётся
# финальным рассказом боя (В2а), поэтому продолжение мира показывает его, а не свёртку, и
# offer_is_stale смотрит на финальный ход.
from game_kit import (
    attack_or_move_number,
    drive,
    make_app,
    script_then_react,
    start_combat_call,
    text_step,
    tools_step,
)
from ui_kit import text_app
from ui_kit import text_step as ui_text_step

from ai_dm.game.combat_fold import fold_fight
from ai_dm.persistence.store import load_slot
from ai_dm.state.combat import CombatState, Group, Participant
from ai_dm.state.scene import TurnRecord

FOLD = "Свёрнуты ходы"


def fought_app(registry, tmp_path):
    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    app = make_app(registry, tmp_path, script_then_react(steps))
    app.handle("Бью ногой дверь")
    results = drive(app.runner, attack_or_move_number)
    assert results[-1].combat_outcome == "victory"
    assert len(results) >= 4
    return app, results


def loaded_app(registry, tmp_path):
    app, results = fought_app(registry, tmp_path)
    loaded = load_slot(tmp_path, "w1", "auto")
    return make_app(registry, tmp_path / "other", script_then_react([]), bundle=loaded), results


def block_texts(step):
    return [b.text for b in step.blocks if b.kind == "narration"]


def test_resumed_world_shows_final_narration_not_fold(registry, tmp_path):
    from ai_dm.ui.session import PlaySession

    app, results = loaded_app(registry, tmp_path)
    assert any(t.narration.startswith(FOLD) for t in app.bundle.memory.recent_turns)
    texts = block_texts(PlaySession(app).start())
    assert texts == [results[-1].narration]


def test_last_narration_block_is_final_turn(registry, tmp_path):
    from ai_dm.ui.session import last_narration_block

    app, results = loaded_app(registry, tmp_path)
    assert last_narration_block(app).text == results[-1].narration


def test_offer_is_stale_after_fight_without_offer_in_final(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app, _ = loaded_app(registry, tmp_path)
    assert offer_is_stale(app) is True


def finished_state():
    participants = [
        Participant(ref="hero", side="heroes", group_id="party", name="Арн"),
        Participant(ref="g1", side="enemies", group_id="g", name="Гоблин", status="dead",
                    monster_id="goblin_warrior"),
    ]
    return CombatState(
        id="c", zones=[], participants=participants, groups={"g": Group(leader_id="g1")},
        round=2, outcome="victory",
    )


def record(seq, requests=()):
    return TurnRecord(turn_seq=seq, at_s=0, player_input="x", narration="y",
                      requests=list(requests), scene_id="scene_1")


def test_offer_is_fresh_when_final_turn_after_fold_offered(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [ui_text_step()])
    app.bundle.memory.recent_turns = [record(1, ["start_combat"]), record(2), record(3)]
    assert fold_fight(app.bundle, finished_state(), registry) is True
    app.bundle.memory.recent_turns.append(record(4, ["offer_choices"]))
    assert offer_is_stale(app) is False


def test_offer_is_stale_when_final_turn_after_fold_did_not_offer(registry, tmp_path):
    from ai_dm.ui.session import offer_is_stale

    app = text_app(registry, tmp_path, [ui_text_step()])
    app.bundle.memory.recent_turns = [record(1, ["start_combat"]), record(2), record(3)]
    fold_fight(app.bundle, finished_state(), registry)
    app.bundle.memory.recent_turns.append(record(4))
    assert offer_is_stale(app) is True
