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


# М0 П5 (решение 47 и сверка перед П5): conditions у NPC сцены, links у known_npcs

def with_conditions(npc, *conditions):
    from ai_dm.state.creature import AppliedCondition, CreatureState

    npc.creature = CreatureState(
        hp_current=5, hp_max=5, conditions=[AppliedCondition(**c) for c in conditions]
    )


def test_scene_npc_with_bound_has_conditions(ctx, grakh):
    with_conditions(grakh, {"id": "bound", "source": "npc_update"})
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["conditions"] == ["bound"]


def test_scene_npc_with_diseased_from_pending_has_conditions(ctx, grakh):
    with_conditions(grakh, {"id": "diseased", "source": "pending"})
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["conditions"] == ["diseased"]


def test_scene_npc_conditions_list_every_id(ctx, grakh):
    with_conditions(grakh, {"id": "bound", "source": "npc_update"}, {"id": "diseased"})
    assert by_id(state(ctx)["scene_npcs"])["grakh"]["conditions"] == ["bound", "diseased"]


def test_scene_npc_conditions_have_no_implied_ones(ctx, grakh):
    with_conditions(grakh, {"id": "bound", "source": "npc_update"})
    assert "incapacitated" not in by_id(state(ctx)["scene_npcs"])["grakh"]["conditions"]


def test_scene_npc_without_creature_has_no_conditions_key(ctx, grakh):
    assert grakh.creature is None
    assert "conditions" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_scene_npc_without_conditions_has_no_conditions_key(ctx, grakh):
    with_conditions(grakh)
    assert "conditions" not in by_id(state(ctx)["scene_npcs"])["grakh"]


def test_known_npc_has_no_conditions_key(ctx, grakh):
    with_conditions(grakh, {"id": "bound", "source": "npc_update"})
    assert "conditions" not in by_id(state(ctx)["known_npcs"])["grakh"]


def add_finn(ctx, **fields):
    from ai_dm.state.world import NPC

    data = {"id": "finn", "name": "Финн", "named": True, "means": ["торгует"]} | fields
    ctx.bundle.world.npcs["finn"] = NPC(**data)


def link(grakh, npc_id="finn", text="должен денег"):
    from ai_dm.state.world import NpcLink

    grakh.links.append(NpcLink(npc_id=npc_id, text=text))


def test_known_npc_with_link_has_links_with_name_and_text(ctx, grakh):
    add_finn(ctx)
    link(grakh)
    item = by_id(state(ctx)["known_npcs"])["grakh"]
    assert item["links"] == [{"npc_id": "finn", "name": "Финн", "text": "должен денег"}]


def test_known_npc_without_links_has_no_links_key(ctx):
    assert "links" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_linked_side_has_no_links_key(ctx, grakh):
    add_finn(ctx, location_id="vale", key=True)
    link(grakh)
    assert "links" not in by_id(state(ctx)["known_npcs"])["finn"]


def test_link_to_missing_npc_is_skipped(ctx, grakh):
    link(grakh, npc_id="nobody")
    assert "links" not in by_id(state(ctx)["known_npcs"])["grakh"]


def test_link_to_missing_npc_does_not_hide_the_next_one(ctx, grakh):
    add_finn(ctx)
    link(grakh, npc_id="nobody")
    link(grakh)
    links = by_id(state(ctx)["known_npcs"])["grakh"]["links"]
    assert [x["npc_id"] for x in links] == ["finn"]


def test_link_to_dead_npc_is_shown(ctx, grakh):
    add_finn(ctx, status="dead")
    link(grakh)
    links = by_id(state(ctx)["known_npcs"])["grakh"]["links"]
    assert [x["npc_id"] for x in links] == ["finn"]


def test_scene_npc_has_no_links_key(ctx, grakh):
    add_finn(ctx)
    link(grakh)
    assert "links" not in by_id(state(ctx)["scene_npcs"])["grakh"]
