# Ж0 подшаг 2 (docs/plan-zh0.md, п. 19, решение 11): мок-прогон 50 сцен с памятью NPC.
# MemoryMock(npc_memory=True): в первом ходе каждой сцены рассказчик пишет npc_update для MEMORY_NPC
# (отношение memory_delta(k), событие «Сцена k»). Окно большое, context_cap фиксирован
# (memory_script.NPC_MEMORY_*), WINDOW не подбирается. Без сети.
import json

import pytest
from memory_script import (
    MEMORY_NPC,
    TURNS_PER_SCENE,
    MemoryMock,
    memory_delta,
    new_run,
    play_memory,
)

from ai_dm.persistence.store import load_slot, save_slot

SCENES = 50
LIMIT = 20
SAVED_AT = "2026-10-03T12:00:00Z"


def fresh_mock():
    return MemoryMock(npc_memory=True)


@pytest.fixture(scope="module")
def first(registry, tmp_path_factory):
    return play_memory(
        registry, tmp_path_factory.mktemp("first"), scenes=SCENES, mock=fresh_mock()
    )


def npc_of(run):
    return run.runner.bundle.world.npcs[MEMORY_NPC]


def scene_number(entry):
    return int(entry.events[0].text.removeprefix("Сцена "))


def expected_kept():
    # 20 старших по (weight, at_s); at_s растёт вместе с номером сцены
    ranked = sorted(range(1, SCENES + 1), key=lambda k: (abs(memory_delta(k)), k))
    return sorted(ranked[-LIMIT:])


def dumps(model):
    return model.model_dump_json()


def core(bundle):
    return [dumps(x) for x in (bundle.world, bundle.chronicle, bundle.memory, bundle.session)] + [
        dumps(h) for h in bundle.heroes
    ]


def test_run_has_fifty_scene_summaries(first):
    assert len(first.runner.bundle.memory.scenes) == SCENES


def test_no_turn_failed(first):
    assert [r for r in first.results if r.failure is not None or not r.committed] == []


def test_memory_has_exactly_twenty_scenes(first):
    assert len(npc_of(first).memory) == LIMIT


def test_memory_keeps_the_twenty_senior_by_weight_then_at_s(first):
    assert sorted(scene_number(m) for m in npc_of(first).memory) == expected_kept()


def test_memory_weights_match_attitude_changes(first):
    for entry in npc_of(first).memory:
        assert entry.weight == abs(memory_delta(scene_number(entry)))


def test_memory_entries_are_ordered_by_at_s(first):
    at_s = [m.at_s for m in npc_of(first).memory]
    assert at_s == sorted(at_s)
    assert len(set(at_s)) == LIMIT


def test_memory_entries_have_one_event_each(first):
    assert [len(m.events) for m in npc_of(first).memory] == [1] * LIMIT


def test_equal_weights_at_border_drop_the_older_scene(first):
    kept = {scene_number(m) for m in npc_of(first).memory}
    border = min(abs(memory_delta(k)) for k in kept)
    same_weight = [k for k in range(1, SCENES + 1) if abs(memory_delta(k)) == border]
    dropped = [k for k in same_weight if k not in kept]
    assert dropped
    assert max(dropped) < min(k for k in same_weight if k in kept)


# бюджет

def test_no_overflow_on_any_narrator_call(first):
    records = first.narrator_records()
    assert records
    for record in records:
        context = record["meta"]["context"]
        assert context["overflow"] is False
        assert context["raised"] is False
        assert "context_overflow" not in record["report_tags"]


# память в запросе

def last_state(run):
    request = run.mock.narrator_turns[-1]
    return json.loads(request.messages[0].content[0].text)


def test_last_turn_prompt_shows_twenty_memory_scenes(first):
    [item] = [n for n in last_state(first)["scene_npcs"] if n["id"] == MEMORY_NPC]
    assert len(item["memory"]) == LIMIT


# детерминизм

def test_two_runs_give_equal_bundles(first, registry, tmp_path):
    second = play_memory(registry, tmp_path, scenes=SCENES, mock=fresh_mock())
    assert dumps(first.runner.bundle) == dumps(second.runner.bundle)


# сейв на сцене 30

def test_save_in_scene_30_load_and_continue_gives_same_memory(first, registry, tmp_path):
    before = play_memory(registry, tmp_path / "a", scenes=30, mock=fresh_mock())
    save_slot(tmp_path / "a", before.runner.bundle, "manual-s30", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path / "a", before.runner.bundle.world.world_id, "manual-s30")
    mock = MemoryMock(
        turns_done=30 * TURNS_PER_SCENE, scenes_done=30, chapters_done=2, npc_memory=True
    )
    after = new_run(registry, tmp_path / "b", bundle=loaded, mock=mock)
    after.play_scenes(SCENES - 30)
    assert npc_of(after).memory == npc_of(first).memory
    assert core(after.runner.bundle) == core(first.runner.bundle)


def test_memory_survives_save_and_load(first, registry, tmp_path):
    save_slot(tmp_path, first.runner.bundle, "manual-end", saved_at=SAVED_AT)
    loaded = load_slot(tmp_path, first.runner.bundle.world.world_id, "manual-end")
    assert loaded.world.npcs[MEMORY_NPC].memory == npc_of(first).memory
