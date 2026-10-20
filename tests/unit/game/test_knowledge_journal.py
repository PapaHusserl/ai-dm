# Ж3 (docs/plan-zh3.md, пп. 0.3, 0.6, 7): журнал знаний в игре.
#   TurnRunner.commit -> note_presence: первое посещение локации и первая встреча NPC (имя в вводе
#     или рассказе хода); строки лога note_presence в lines/outcomes не идут; откат хода журнал не
#     трогает;
#   TurnRunner.end_fight -> note_combat: бестиарий по безымянным врагам боя (оба пути fold);
#   GameApp.__init__ и GameApp.load -> ensure_journal: достройка только пустого журнала.
import shutil
from pathlib import Path

import pytest
from game_kit import (
    attack_or_move_number,
    drive,
    end_turn_number,
    enemies_surrender,
    make_app,
    make_rig,
    script_then_react,
    scripted,
    start_combat_call,
    text_step,
    tools_step,
)
from protocol_kit import make_bundle

from ai_dm.state.knowledge import KnowledgeEntry

FIXTURE_V10 = Path(__file__).resolve().parents[2] / "fixtures" / "saves" / "v10"


def journal(runner):
    return runner.bundle.heroes[0].knowledge


def texts(runner):
    return [e.text for e in journal(runner)]


def play_rig(registry, cfg, tmp_path, steps, bundle=None):
    return make_rig(registry, cfg, tmp_path, scripted(steps), bundle=bundle)


# commit: места

def test_first_turn_records_visited_location(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Смотрю")
    assert "Место: Вейл" in texts(rig.runner)


def test_location_entry_is_seen_location_with_world_time(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Смотрю")
    [place] = [e for e in journal(rig.runner) if e.kind == "location"]
    assert (place.ref, place.source) == ("vale", "seen")
    assert place.at_s == rig.runner.bundle.world.clock.now_s


def test_second_turn_does_not_repeat_location(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Тихо."), text_step("Всё ещё тихо.")])
    rig.runner.play("Смотрю")
    rig.runner.play("Жду")
    assert texts(rig.runner).count("Место: Вейл") == 1


# commit: встречи

def test_npc_named_in_narration_is_recorded(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Гракх хмуро смотрит на тебя.")])
    rig.runner.play("Смотрю")
    assert "Знакомство: Гракх" in texts(rig.runner)


def test_npc_named_in_player_input_is_recorded(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Зову Гракх")
    assert "Знакомство: Гракх" in texts(rig.runner)


def test_npc_not_named_is_not_recorded(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Тихо.")])
    rig.runner.play("Смотрю")
    assert all(e.kind != "npc" for e in journal(rig.runner))


def test_npc_elsewhere_named_is_not_recorded(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Олдрик далеко.")])
    rig.runner.play("Смотрю")
    assert all(e.ref != "aldric" for e in journal(rig.runner))


def test_meeting_is_recorded_once_over_turns(registry, cfg, tmp_path):
    steps = [text_step("Гракх кивает."), text_step("Гракх снова кивает.")]
    rig = play_rig(registry, cfg, tmp_path, steps)
    rig.runner.play("Смотрю")
    rig.runner.play("Жду")
    assert texts(rig.runner).count("Знакомство: Гракх") == 1


def test_presence_log_is_not_in_lines_or_outcomes(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [text_step("Гракх кивает.")])
    result = rig.runner.play("Смотрю")
    assert result.outcomes == []
    assert all("Журнал" not in line for line in result.lines)
    assert rig.runner.bundle.memory.recent_turns[-1].outcomes == []


def test_failed_turn_leaves_journal_untouched(registry, cfg, tmp_path):
    rig = play_rig(registry, cfg, tmp_path, [])
    with pytest.raises(Exception):  # noqa: B017  (ScriptExhausted: откат и повторный raise)
        rig.runner.play("Зову Гракх")
    assert journal(rig.runner) == []


# end_fight: бестиарий

def fight_rig(registry, cfg, tmp_path, **reactive):
    steps = [tools_step(start_combat_call()), text_step("Гоблины бросаются на вас.")]
    rig = make_rig(
        registry, cfg, tmp_path, script_then_react(steps, **reactive),
    )
    assert rig.runner.play("Бью ногой дверь").committed is True
    return rig


def creature_entries(rig):
    return [e for e in journal(rig.runner) if e.kind == "creature"]


def test_victory_writes_bestiary_entry(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    last = drive(rig.runner, attack_or_move_number)[-1]
    assert last.combat_outcome == "victory"
    [entry] = creature_entries(rig)
    assert (entry.ref, entry.source) == ("goblin_warrior", "seen")
    assert entry.text == "Бой: Воин-гоблин — победа"


def test_two_goblins_give_one_entry(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    drive(rig.runner, attack_or_move_number)
    assert len(creature_entries(rig)) == 1


def test_no_bestiary_entry_while_fight_goes_on(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path)
    assert creature_entries(rig) == []


def test_ended_by_master_writes_interrupted_entry(registry, cfg, tmp_path):
    rig = fight_rig(registry, cfg, tmp_path, end_combat=True)
    enemies_surrender(rig.runner)
    result = rig.runner.play(str(end_turn_number(rig.runner)))
    assert result.combat_outcome == "ended_by_master"
    assert [e.text for e in creature_entries(rig)] == ["Бой: Воин-гоблин — прерван"]


def test_named_enemy_is_not_in_bestiary(registry, cfg, tmp_path):
    steps = [tools_step(start_combat_call(grakh=True)), text_step("Бой.")]
    rig = make_rig(registry, cfg, tmp_path, script_then_react(steps))
    rig.runner.play("Бью ногой дверь")
    drive(rig.runner, attack_or_move_number)
    assert {e.ref for e in creature_entries(rig)} == {"goblin_warrior"}


# GameApp.__init__

def met_bundle(registry):
    bundle = make_bundle(registry)
    bundle.world.npcs["aldric"].attitude = 3
    bundle.world.locations["forest"].visited = True
    return bundle


def test_new_world_app_starts_with_empty_journal(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([]))
    assert app.bundle.heroes[0].knowledge == []


def test_init_backfills_empty_journal_of_old_world(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([]), bundle=met_bundle(registry))
    assert sorted(e.text for e in app.bundle.heroes[0].knowledge) == [
        "Знакомство: Олдрик", "Место: Лес",
    ]


def test_init_keeps_existing_journal(registry, tmp_path):
    bundle = met_bundle(registry)
    own = KnowledgeEntry(kind="situation", ref="plague", text="Чума", source="rumor", at_s=0)
    bundle.heroes[0].knowledge.append(own)
    app = make_app(registry, tmp_path, scripted([]), bundle=bundle)
    assert app.bundle.heroes[0].knowledge == [own]


def test_init_backfill_does_not_write_current_location(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([]), bundle=met_bundle(registry))
    assert all(e.ref != "vale" for e in app.bundle.heroes[0].knowledge)


def test_init_backfill_makes_no_turn_or_time(registry, tmp_path):
    bundle = met_bundle(registry)
    now = bundle.world.clock.now_s
    app = make_app(registry, tmp_path, scripted([]), bundle=bundle)
    assert app.bundle.world.clock.now_s == now
    assert app.bundle.session.turn_seq == 0


# GameApp.load

def saved_old_world(registry, tmp_path, knowledge=None):
    app = make_app(registry, tmp_path, scripted([]), bundle=met_bundle(registry))
    hero = app.bundle.heroes[0]
    hero.knowledge = [] if knowledge is None else knowledge
    app.save_current("auto")
    return app


def test_load_backfills_empty_journal(registry, tmp_path):
    app = saved_old_world(registry, tmp_path)
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    assert sorted(e.text for e in app.bundle.heroes[0].knowledge) == [
        "Знакомство: Олдрик", "Место: Лес",
    ]


def test_load_backfill_reaches_runner_bundle(registry, tmp_path):
    app = saved_old_world(registry, tmp_path)
    app.load("auto")
    assert app.runner.bundle is app.bundle
    assert len(app.runner.bundle.heroes[0].knowledge) == 2


def test_load_keeps_saved_journal_as_is(registry, tmp_path):
    own = KnowledgeEntry(kind="situation", ref="plague", text="Чума", source="rumor", at_s=0)
    app = saved_old_world(registry, tmp_path, knowledge=[own])
    app.load("auto")
    assert app.bundle.heroes[0].knowledge == [own]


def test_save_and_load_roundtrip_keeps_journal(registry, cfg, tmp_path):
    app = make_app(
        registry, tmp_path, scripted([text_step("Гракх кивает.")]), bundle=make_bundle(registry)
    )
    app.handle("Смотрю")
    before = list(app.bundle.heroes[0].knowledge)
    assert before
    app.save_current("auto")
    app.load("auto")
    assert app.bundle.heroes[0].knowledge == before


def load_v10(registry, tmp_path):
    app = make_app(registry, tmp_path, scripted([]))
    app.world_id = "zh0_world"
    shutil.copytree(FIXTURE_V10, tmp_path / "zh0_world" / "slots" / "auto")
    lines = app.load("auto")
    assert lines[0] == "Загружено: auto.", lines
    return app


def test_load_v10_fixture_backfills_met_npcs_and_visited_place(registry, tmp_path):
    app = load_v10(registry, tmp_path)
    got = sorted((e.kind, e.ref, e.text) for e in app.bundle.heroes[0].knowledge)
    assert got == [
        ("location", "lame_goose", "Место: Таверна «Хромой гусь»"),
        ("npc", "innkeeper", "Знакомство: Гарт"),
        ("npc", "mira", "Знакомство: Мирра"),
        ("npc", "old_tam", "Знакомство: Там"),
    ]


def test_load_v10_fixture_does_not_meet_unseen_npc_or_place(registry, tmp_path):
    app = load_v10(registry, tmp_path)
    refs = {e.ref for e in app.bundle.heroes[0].knowledge}
    assert not refs & {"grakh", "cellar", "vale"}


def test_load_v10_fixture_entries_are_dated_by_scene_start(registry, tmp_path):
    app = load_v10(registry, tmp_path)
    started = app.bundle.session.current_scene.started_at_s
    assert {e.at_s for e in app.bundle.heroes[0].knowledge} == {started}


def test_load_v10_fixture_all_entries_are_seen(registry, tmp_path):
    app = load_v10(registry, tmp_path)
    assert {e.source for e in app.bundle.heroes[0].knowledge} == {"seen"}


def test_load_second_time_does_not_duplicate(registry, tmp_path):
    app = saved_old_world(registry, tmp_path)
    app.load("auto")
    app.load("auto")
    assert len(app.bundle.heroes[0].knowledge) == 2
