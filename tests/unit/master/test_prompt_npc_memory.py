# Ж0 подшаг 2 (docs/plan-zh0.md, п. 17, Q6): память, цели и заметки NPC в состоянии промпта.
# Ожидаемый API (state_data):
#   scene_npcs[i]: "memory" = rules.npc_memory.memory_data(npc) (только если память непуста),
#       "goals" -- список целей (kind, target, text, ...; только если непусто),
#       "notes" -- NPC.notes (только если непусто);
#   known_npcs[i]: полной памяти нет; "goals" (если непусто) и "memory_last" -- последнее событие
#       самой поздней сцены памяти {kind, text, ...} (если память непуста); "memory" нет.
#   У NPC без памяти/целей/заметок этих ключей нет (экономия токенов).
import json

import pytest
from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.npc_memory import memory_data
from ai_dm.state.relations import NpcEvent, NpcGoal, NpcSceneMemory


def state(ctx, mode="explore"):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", mode)
    return json.loads(request.messages[0].content[0].text)


def by_id(items):
    return {item["id"]: item for item in items}


def scene_memory(n, weight, *events):
    return NpcSceneMemory(
        scene_id=f"scene_{n}", at_s=n * 100, weight=weight,
        events=[NpcEvent(kind=k, turn_seq=n, text=t) for k, t in events],
    )


@pytest.fixture
def ctx(registry, cfg):
    return make_ctx(registry, cfg)


@pytest.fixture
def grakh(ctx):
    return ctx.bundle.world.npcs["grakh"]


# scene_npcs

def test_scene_npc_without_memory_has_no_memory_key(ctx):
    assert "memory" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_scene_npc_without_goals_has_no_goals_key(ctx):
    assert "goals" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_scene_npc_without_notes_has_no_notes_key(ctx):
    assert "notes" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_scene_npc_memory_equals_memory_data(ctx, grakh):
    grakh.memory = [
        scene_memory(1, 5, ("helped", "помог")), scene_memory(2, 3, ("insult", "нагрубил"))
    ]
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["memory"] == memory_data(grakh)


def test_scene_npc_memory_shows_event_text(ctx, grakh):
    grakh.memory = [scene_memory(1, 5, ("promise", "обещал вернуть долг"))]
    [entry] = by_id(state(ctx)["scene_npcs"])["grakh"]["memory"]
    assert entry["events"][0]["text"] == "обещал вернуть долг"


def test_scene_npc_goals_show_kind_and_target(ctx, grakh):
    grakh.goals = [NpcGoal(kind="revenge", target="hero", text="за брата", since_s=10)]
    [goal] = by_id(state(ctx)["scene_npcs"])["grakh"]["goals"]
    assert (goal["kind"], goal["target"], goal["text"]) == ("revenge", "hero", "за брата")


def test_scene_npc_notes_are_shown(ctx, grakh):
    grakh.notes = "Вождь клана, любит эль."
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["notes"] == "Вождь клана, любит эль."


def test_scene_npc_memory_keeps_other_keys(ctx, grakh):
    grakh.memory = [scene_memory(1, 5, ("helped", "помог"))]
    item = by_id(state(ctx)["scene_npcs"])["grakh"]
    assert (item["name"], item["attitude"]) == ("Гракх", 0)


def test_scene_npc_memory_of_other_npc_not_leaked(ctx, grakh):
    grakh.memory = [scene_memory(1, 5, ("helped", "помог"))]
    ctx.bundle.world.npcs["aldric"].location_id = "vale"
    assert "memory" not in by_id(state(ctx)["scene_npcs"])["aldric"]


# known_npcs (Q6)

def test_known_npc_has_no_full_memory(ctx, grakh):
    grakh.memory = [scene_memory(1, 5, ("helped", "помог"))]
    assert "memory" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_known_npc_without_memory_has_no_memory_last(ctx):
    assert "memory_last" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_known_npc_memory_last_is_last_event_of_latest_scene(ctx, grakh):
    grakh.memory = [
        scene_memory(3, 1, ("helped", "первое"), ("gift", "последнее")),
        scene_memory(2, 9, ("insult", "старое")),
    ]
    last = by_id(state(ctx)["known_npcs"])["grakh"]["memory_last"]
    assert (last["kind"], last["text"]) == ("gift", "последнее")


def test_known_npc_goals_are_shown(ctx, grakh):
    grakh.goals = [NpcGoal(kind="life_debt", target="hero", since_s=10)]
    [goal] = by_id(state(ctx)["known_npcs"])["grakh"]["goals"]
    assert goal["kind"] == "life_debt"


def test_known_npc_notes_are_shown(ctx, grakh):
    grakh.notes = "Вождь клана, любит эль."
    assert by_id(state(ctx)["known_npcs"])["grakh"]["notes"] == "Вождь клана, любит эль."


def test_known_npc_without_notes_has_no_notes_key(ctx):
    assert "notes" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_scene_npc_inactive_goals_are_not_shown(ctx, grakh):
    grakh.goals = [
        NpcGoal(kind="revenge", target="hero", since_s=10, status="done"),
        NpcGoal(kind="life_debt", target="hero", since_s=11, status="dropped"),
    ]
    assert "goals" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_known_npc_inactive_goals_are_not_shown(ctx, grakh):
    grakh.goals = [NpcGoal(kind="revenge", target="hero", since_s=10, status="done")]
    assert "goals" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_scene_npc_only_active_goal_is_shown(ctx, grakh):
    grakh.goals = [
        NpcGoal(kind="revenge", target="hero", since_s=10, status="done"),
        NpcGoal(kind="life_debt", target="hero", since_s=11),
    ]
    goals = by_id(state(ctx)["scene_npcs"])["grakh"]["goals"]
    assert [g["kind"] for g in goals] == ["life_debt"]


def test_known_npc_without_goals_has_no_goals_key(ctx):
    assert "goals" not in by_id(state(ctx)["known_npcs"])["grakh"]
