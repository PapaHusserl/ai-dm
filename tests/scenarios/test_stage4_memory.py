# Приёмка этапа 4 (STAGE4-PLAN, P4): мок-прогон 52 сцен (4 главы + 4 сцены пятой) на мок-модели
# с фиксированным context_cap. Генератор: memory_script.py (один MemoryMock на три роли). Без сети.
import json

import pytest
from memory_script import (
    MEMORY_CONTEXT_CAP,
    SCENES,
    SCENES_PER_CHAPTER,
    TURNS_PER_SCENE,
    MemoryMock,
    new_run,
    play_memory,
)

from ai_dm.llm.replay import ReplayAdapter
from ai_dm.master.context import STAGES
from ai_dm.persistence.store import load_slot, save_slot

SAVED_AT = "2026-10-03T12:00:00Z"


@pytest.fixture(scope="module")
def first(registry, tmp_path_factory):
    return play_memory(registry, tmp_path_factory.mktemp("first"))


def stages_of(record):
    return [stage for stage, _ in record["meta"]["context"]["dropped"]]


def turn_record(run, turn_index):
    # первая запись narrator хода turn_index (у хода может быть несколько раундов)
    seen = {}
    for record in run.narrator_records():
        seen.setdefault(record["run_id"], record)
    return list(seen.values())[turn_index]


def turn_records(run):
    seen = {}
    for record in run.narrator_records():
        seen.setdefault(record["run_id"], record)
    return list(seen.values())


def dumps(model):
    return model.model_dump_json()


def core(bundle):
    return [dumps(x) for x in (bundle.world, bundle.chronicle, bundle.memory, bundle.session)] + [
        dumps(h) for h in bundle.heroes
    ]


# 52 сцены, >= 4 главы

def test_run_has_52_scene_summaries(first):
    assert len(first.runner.bundle.memory.scenes) == SCENES


def test_run_has_four_closed_chapters_by_summarizer(first):
    chapters = first.runner.bundle.memory.chapters
    assert [c.number for c in chapters] == [1, 2, 3, 4]
    assert {c.source for c in chapters} == {"summarizer"}


def test_run_is_in_fifth_chapter_after_52_scenes(first):
    chapter = first.runner.bundle.session.current_chapter
    assert chapter.number == 5
    done = [s for s in first.runner.bundle.memory.scenes if s.chapter_id == chapter.id]
    assert len(done) == SCENES - 4 * SCENES_PER_CHAPTER


def test_no_boundary_failed(first):
    assert [r for r in first.results if r.boundary_failed] == []
    assert [r for r in first.results if r.failure is not None or not r.committed] == []


def test_game_summary_is_last_chapter_fold(first):
    assert first.runner.bundle.memory.game_summary.startswith("Игра до главы 4")


def test_narrator_got_every_turn(first):
    assert len(first.mock.narrator_turns) == SCENES * TURNS_PER_SCENE


# детерминизм по сиду

def test_two_runs_give_equal_bundles_and_journals(first, registry, tmp_path):
    second = play_memory(registry, tmp_path)
    assert dumps(first.runner.bundle) == dumps(second.runner.bundle)
    assert first.journal.read_records() == second.journal.read_records()


# бюджет

def test_estimate_within_budget_and_no_overflow_on_every_narrator_call(first):
    records = first.narrator_records()
    assert records
    for record in records:
        context = record["meta"]["context"]
        assert context["estimate"] <= context["budget"], (
            f"estimate {context['estimate']} > budget {context['budget']}: "
            "подобрать MEMORY_CONTEXT_CAP в tests/scenarios/memory_script.py"
        )
        assert context["budget"] == context["static"] + MEMORY_CONTEXT_CAP
        assert context["overflow"] is False
        assert context["raised"] is False
        assert "context_overflow" not in record["report_tags"]


def test_json_length_over_2_5_within_budget_on_every_turn(first):
    for request, record in zip(first.mock.narrator_turns, turn_records(first), strict=True):
        size = len(request.model_dump_json()) / 2.5
        budget = record["meta"]["context"]["budget"]
        assert size <= budget, f"{size} > {budget}: подобрать MEMORY_CONTEXT_CAP в memory_script.py"


# память в запросе сцены 50

def test_scene_50_first_turn_has_chapter_1_and_game_summary(first):
    request = first.mock.narrator_turns[49 * TURNS_PER_SCENE]
    text = request.system[2].text
    assert "Глава 1" in text
    memory = json.loads(text)
    assert memory["chapters"][0]["summary"].startswith("Глава 1.")
    assert memory["game_summary"].startswith("Игра до главы 4")


def test_scene_50_has_all_four_chapter_summaries_and_no_old_scenes(first):
    request = first.mock.narrator_turns[49 * TURNS_PER_SCENE]
    memory = json.loads(request.system[2].text)
    assert [c["number"] for c in memory["chapters"]] == [1, 2, 3, 4]
    # выжимка сцены 49 (единственная сцена главы 5) вытеснена, блок сцен пуст
    assert memory["scenes"] == []
    record = turn_record(first, 49 * TURNS_PER_SCENE)
    assert ["scenes", "scene_49"] in record["meta"]["context"]["dropped"]


# порядок вытеснения

def test_dropped_stages_are_nondecreasing_on_every_turn(first):
    for record in first.narrator_records():
        ranks = [STAGES.index(stage) for stage in stages_of(record)]
        assert ranks == sorted(ranks)


def test_scenes_and_turns_dropped_oldest_first(first):
    for record in first.narrator_records():
        dropped = record["meta"]["context"]["dropped"]
        turns = [int(i) for s, i in dropped if s == "turns"]
        scenes = [int(i.split("_")[-1]) for s, i in dropped if s == "scenes"]
        assert turns == sorted(turns)
        assert scenes == sorted(scenes)


def test_every_stage_fires_somewhere(first):
    # 129: соседние локации у рассказчика неустранимы -- ступень locations не срабатывает
    fired = {stage for r in first.narrator_records() for stage in stages_of(r)}
    assert fired == set(STAGES) - {"locations"}


def test_one_turn_has_turns_scenes_and_npcs_dropped_together(first):
    full = [r for r in first.narrator_records() if {"turns", "scenes", "npcs"} <= set(stages_of(r))]
    assert full


# replay

def test_replay_of_whole_run_gives_same_bundle(first, registry, tmp_path):
    records = first.journal.read_records()
    roles = ("narrator", "summarizer", "world")
    adapters = tuple(ReplayAdapter(records, role=role) for role in roles)
    second = play_memory(registry, tmp_path, adapters=adapters)
    assert [r for r in second.results if r.boundary_failed] == []
    assert dumps(first.runner.bundle) == dumps(second.runner.bundle)
    assert [r["meta"] for r in second.narrator_records()] == [
        r["meta"] for r in first.narrator_records()
    ]


# сейв в сцене 30

def test_save_in_scene_30_load_and_continue_gives_same_result(first, registry, tmp_path):
    before = play_memory(registry, tmp_path / "a", scenes=30)
    save_slot(tmp_path / "a", before.runner.bundle, "manual-s30", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path / "a", before.runner.bundle.world.world_id, "manual-s30")
    mock = MemoryMock(turns_done=30 * TURNS_PER_SCENE, scenes_done=30, chapters_done=2)
    after = new_run(registry, tmp_path / "b", bundle=loaded, mock=mock)
    after.play_scenes(SCENES - 30)
    assert core(after.runner.bundle) == core(first.runner.bundle)
    assert after.mock.narrator_turns == first.mock.narrator_turns[30 * TURNS_PER_SCENE :]
