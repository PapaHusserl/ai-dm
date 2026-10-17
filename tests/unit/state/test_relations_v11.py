# Ж0 подшаг 1 (docs/plan-zh0.md, пп. 7-10): модели памяти/целей/связей NPC, журнал знаний героя
# и новые поля схемы v11 (NPC, HeroState, SceneState.scene_mood, WorldSim.pending_acts).
# API: ai_dm.state.relations (NPC_EVENT_TEXT_MAX=120, NpcEvent, NpcSceneMemory, NpcGoal,
#      FamilyLink), ai_dm.state.knowledge.KnowledgeEntry; все extra="forbid";
#      открытые перечни -- str, закрытые -- Literal.
import pytest
from pydantic import ValidationError

from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState
from ai_dm.state.knowledge import KnowledgeEntry
from ai_dm.state.relations import (
    NPC_EVENT_TEXT_MAX,
    FamilyLink,
    NpcEvent,
    NpcGoal,
    NpcSceneMemory,
)
from ai_dm.state.scene import SceneState
from ai_dm.state.world import NPC, WorldSim


def event(**kwargs):
    kwargs.setdefault("kind", "spared")
    kwargs.setdefault("turn_seq", 3)
    kwargs.setdefault("text", "Пощадил")
    return NpcEvent(**kwargs)


def memory(**kwargs):
    kwargs.setdefault("scene_id", "s1")
    kwargs.setdefault("at_s", 100)
    kwargs.setdefault("weight", 5)
    kwargs.setdefault("events", [event()])
    return NpcSceneMemory(**kwargs)


def goal(**kwargs):
    kwargs.setdefault("kind", "revenge")
    kwargs.setdefault("target", "h1")
    kwargs.setdefault("since_s", 50)
    return NpcGoal(**kwargs)


def entry(**kwargs):
    kwargs.setdefault("kind", "fact")
    kwargs.setdefault("ref", "innkeeper")
    kwargs.setdefault("text", "Гарт хранит ключ")
    kwargs.setdefault("source", "told")
    kwargs.setdefault("at_s", 10)
    return KnowledgeEntry(**kwargs)


def make_npc(**kwargs):
    return NPC(id="a", name="Олдрик", means=["магия"], **kwargs)


def make_hero(**kwargs):
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"],
        background=BackgroundSpec(
            name="Солдат", abilities=["str", "dex", "con"], skills=["athletics", "intimidation"],
            tool="dice_set", feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12), **kwargs,
    )


# NpcEvent

def test_event_text_max_is_120():
    assert NPC_EVENT_TEXT_MAX == 120


def test_event_text_of_exactly_limit_is_ok():
    assert len(event(text="я" * 120).text) == 120


def test_event_text_over_limit_is_rejected():
    with pytest.raises(ValidationError):
        event(text="я" * 121)


def test_event_kind_is_open_string():
    assert event(kind="something_new").kind == "something_new"


def test_event_rejects_extra_field():
    with pytest.raises(ValidationError):
        event(foo=1)


@pytest.mark.parametrize("field", ["kind", "turn_seq", "text"])
def test_event_requires_field(field):
    data = {"kind": "gift", "turn_seq": 1, "text": "t"}
    del data[field]
    with pytest.raises(ValidationError):
        NpcEvent(**data)


# NpcSceneMemory

def test_memory_keeps_fields():
    m = memory()
    assert (m.scene_id, m.at_s, m.weight, len(m.events)) == ("s1", 100, 5, 1)


def test_memory_weight_zero_is_ok():
    assert memory(weight=0).weight == 0


def test_memory_negative_weight_is_rejected():
    with pytest.raises(ValidationError):
        memory(weight=-1)


def test_memory_empty_events_are_rejected():
    with pytest.raises(ValidationError):
        memory(events=[])


def test_memory_rejects_extra_field():
    with pytest.raises(ValidationError):
        memory(foo=1)


@pytest.mark.parametrize("field", ["scene_id", "at_s", "weight", "events"])
def test_memory_requires_field(field):
    data = {"scene_id": "s", "at_s": 1, "weight": 1, "events": [event()]}
    del data[field]
    with pytest.raises(ValidationError):
        NpcSceneMemory(**data)


def test_memory_round_trips_through_json():
    m = memory()
    assert NpcSceneMemory.model_validate_json(m.model_dump_json()) == m


# NpcGoal

def test_goal_defaults():
    g = goal()
    assert (g.status, g.text) == ("active", "")


@pytest.mark.parametrize("status", ["active", "done", "dropped"])
def test_goal_accepts_status(status):
    assert goal(status=status).status == status


def test_goal_rejects_unknown_status():
    with pytest.raises(ValidationError):
        goal(status="failed")


def test_goal_kind_is_open_string():
    assert goal(kind="vendetta").kind == "vendetta"


def test_goal_rejects_extra_field():
    with pytest.raises(ValidationError):
        goal(foo=1)


@pytest.mark.parametrize("field", ["kind", "target", "since_s"])
def test_goal_requires_field(field):
    data = {"kind": "debt", "target": "h1", "since_s": 1}
    del data[field]
    with pytest.raises(ValidationError):
        NpcGoal(**data)


# FamilyLink

@pytest.mark.parametrize("kind", ["parent", "spouse", "child"])
def test_family_accepts_kind(kind):
    assert FamilyLink(kind=kind, ref="x", ref_kind="npc").kind == kind


def test_family_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        FamilyLink(kind="sibling", ref="x", ref_kind="npc")


@pytest.mark.parametrize("ref_kind", ["npc", "hero"])
def test_family_accepts_ref_kind(ref_kind):
    assert FamilyLink(kind="parent", ref="x", ref_kind=ref_kind).ref_kind == ref_kind


def test_family_rejects_unknown_ref_kind():
    with pytest.raises(ValidationError):
        FamilyLink(kind="parent", ref="x", ref_kind="god")


def test_family_rejects_extra_field():
    with pytest.raises(ValidationError):
        FamilyLink(kind="parent", ref="x", ref_kind="npc", foo=1)


def test_family_requires_ref():
    with pytest.raises(ValidationError):
        FamilyLink(kind="parent", ref_kind="npc")


# KnowledgeEntry

def test_knowledge_from_ref_defaults_to_none():
    assert entry().from_ref is None


def test_knowledge_keeps_fields():
    e = entry(from_ref="mira")
    assert (e.kind, e.ref, e.text, e.source, e.from_ref, e.at_s) == (
        "fact", "innkeeper", "Гарт хранит ключ", "told", "mira", 10,
    )


def test_knowledge_kind_and_source_are_open_strings():
    e = entry(kind="legend", source="dream")
    assert (e.kind, e.source) == ("legend", "dream")


def test_knowledge_rejects_extra_field():
    with pytest.raises(ValidationError):
        entry(foo=1)


@pytest.mark.parametrize("field", ["kind", "ref", "text", "source", "at_s"])
def test_knowledge_requires_field(field):
    data = {"kind": "fact", "ref": "r", "text": "t", "source": "seen", "at_s": 1}
    del data[field]
    with pytest.raises(ValidationError):
        KnowledgeEntry(**data)


# NPC

def test_npc_new_fields_defaults():
    npc = make_npc()
    assert (npc.memory, npc.goals, npc.family, npc.services) == ([], [], [], [])
    assert npc.known_name is None


def test_npc_notes_default_to_empty_string():
    assert make_npc().notes == ""


def test_npc_notes_are_kept():
    assert make_npc(notes="Брат Мирры").notes == "Брат Мирры"


def test_npc_has_no_relations_text():
    assert "relations_text" not in NPC.model_fields


def test_npc_rejects_relations_text():
    with pytest.raises(ValidationError):
        make_npc(relations_text="Брат Мирры")


def test_npc_accepts_memory_goals_family_services_known_name():
    npc = make_npc(
        memory=[memory()], goals=[goal()],
        family=[FamilyLink(kind="spouse", ref="mira", ref_kind="npc")],
        services=["rest"], known_name="Гарт",
    )
    assert (len(npc.memory), len(npc.goals), len(npc.family)) == (1, 1, 1)
    assert (npc.services, npc.known_name) == (["rest"], "Гарт")


def test_npc_new_lists_are_not_shared_between_instances():
    a, b = make_npc(), make_npc()
    a.memory.append(memory())
    a.goals.append(goal())
    a.family.append(FamilyLink(kind="child", ref="x", ref_kind="hero"))
    a.services.append("rest")
    assert (b.memory, b.goals, b.family, b.services) == ([], [], [], [])


def test_npc_round_trips_with_new_fields():
    npc = make_npc(memory=[memory()], goals=[goal(status="done")], known_name="Гарт")
    assert NPC.model_validate_json(npc.model_dump_json()) == npc


def test_npc_rejects_invalid_nested_memory():
    with pytest.raises(ValidationError):
        make_npc(memory=[{"scene_id": "s", "at_s": 1, "weight": -1, "events": []}])


# HeroState, SceneState, WorldSim

def test_hero_family_and_knowledge_default_to_empty():
    hero = make_hero()
    assert (hero.family, hero.knowledge) == ([], [])


def test_hero_accepts_family_and_knowledge():
    hero = make_hero(
        family=[FamilyLink(kind="parent", ref="old_tam", ref_kind="npc")], knowledge=[entry()],
    )
    assert hero.family[0].ref == "old_tam"
    assert hero.knowledge[0].text == "Гарт хранит ключ"


def test_hero_lists_are_not_shared_between_instances():
    a, b = make_hero(), make_hero()
    a.family.append(FamilyLink(kind="parent", ref="x", ref_kind="npc"))
    a.knowledge.append(entry())
    assert (b.family, b.knowledge) == ([], [])


def test_hero_rejects_invalid_knowledge_entry():
    with pytest.raises(ValidationError):
        make_hero(knowledge=[{"kind": "fact"}])


def test_scene_mood_defaults_to_empty_string():
    assert SceneState(id="s", started_at_s=0).scene_mood == ""


def test_scene_mood_is_kept():
    assert SceneState(id="s", started_at_s=0, scene_mood="tense").scene_mood == "tense"


def test_world_sim_pending_acts_default_to_empty():
    assert WorldSim().pending_acts == []


def test_world_sim_pending_acts_are_kept():
    assert WorldSim(pending_acts=["a", "b"]).pending_acts == ["a", "b"]


def test_world_sim_pending_acts_not_shared():
    a, b = WorldSim(), WorldSim()
    a.pending_acts.append("x")
    assert b.pending_acts == []
