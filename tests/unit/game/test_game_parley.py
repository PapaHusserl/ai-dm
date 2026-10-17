# Переговоры в бою через TurnRunner (docs/plan-combat-parley.md, п. 3): фраза (player_action.parley)
# и пункт меню «Переговоры» (id parley:<цель>:<навык>:<исход>) идут в engine.parley. Исход и СЛ --
# решение движка, в логе «переговоры с ...»; отказ движка --
# строка «переговоры невозможны (<причина>)».
# Броски здесь настоящие (Rng мира), поэтому проверяется только факт и трата действия.
from game_kit import combat_of, number_of, option_ids
from test_game_combat_flow import start_fight, text_turn

PARLEY = {"skill": "intimidation", "outcome": "surrender", "target": "g1"}


def action(parley):
    return {"type": "player_action", "steps": [], "unsupported": "", "parley": parley}


def test_text_turn_parley_goes_through_engine(registry, cfg, tmp_path):
    rig, result, _ = text_turn(
        registry, cfg, tmp_path, action(PARLEY), text="Сдавайтесь, или умрёте"
    )
    assert result.committed is True
    assert result.requests[0] == "player_action"
    assert any("переговоры с" in line and "Запугивание" in line for line in result.log)


def test_text_turn_parley_log_has_dc_and_outcome_word(registry, cfg, tmp_path):
    rig, result, _ = text_turn(registry, cfg, tmp_path, action(PARLEY), text="Сдавайтесь")
    line = [line for line in result.log if "переговоры с" in line][0]
    assert "СЛ " in line
    assert "сдаться" in line


def test_text_turn_parley_marks_the_target_as_tried(registry, cfg, tmp_path):
    rig, result, _ = text_turn(registry, cfg, tmp_path, action(PARLEY), text="Сдавайтесь")
    goblin = [p for p in combat_of(rig.runner).participants if p.ref == "g1"][0]
    marks = [e.id for e in goblin.creature.active_effects]
    assert "parley_tried" in marks


def test_text_turn_parley_with_unknown_target_is_logged_not_raised(registry, cfg, tmp_path):
    bad = dict(PARLEY, target="ghost")
    rig, result, _ = text_turn(registry, cfg, tmp_path, action(bad), text="Эй, ты")
    assert result.committed is True
    assert any("переговоры невозможны (target_required)" in line for line in result.log)


def test_text_turn_parley_with_not_allowed_outcome_is_logged(registry, cfg, tmp_path):
    bad = dict(PARLEY, outcome="defect")
    rig, result, _ = text_turn(registry, cfg, tmp_path, action(bad), text="Идите к нам")
    assert any("переговоры невозможны (outcome_not_allowed)" in line for line in result.log)


def test_menu_lists_parley_for_every_enemy_in_hearing(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    ids = option_ids(rig.runner)
    assert "parley:g1:intimidation:surrender" in ids
    assert "parley:g1:persuasion:defect" in ids
    assert "parley:g1:deception:flee" in ids


def test_menu_parley_number_runs_the_parley(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    result = rig.runner.play(str(number_of(rig.runner, "parley:g1:intimidation:surrender")))
    assert result.committed is True
    assert any("переговоры с" in line for line in result.log)


def test_menu_drops_the_option_after_the_attempt(registry, cfg, tmp_path):
    rig, _ = start_fight(registry, cfg, tmp_path)
    rig.runner.play(str(number_of(rig.runner, "parley:g1:intimidation:surrender")))
    assert not [i for i in option_ids(rig.runner) if i.startswith("parley:g1:")]


def test_rejected_parley_does_not_stop_the_rest_of_the_turn(registry, cfg, tmp_path):
    bad = action(dict(PARLEY, target="ghost"))
    bad["steps"] = ["second_wind"]
    rig, result, _ = text_turn(registry, cfg, tmp_path, bad, text="Эй, ты. И вдохну")
    assert any("переговоры невозможны" in line for line in result.log)
    assert any("Второе дыхание" in line for line in result.log)
