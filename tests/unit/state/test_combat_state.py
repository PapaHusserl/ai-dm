# Модели боя и типизация боевой сессии (шаг 15-19, D6 batch4-review).
# Ожидаемый API: ai_dm.state.combat
# (подробный список полей -- в шапке tests/unit/combat/combat_kit.py)
#   ZoneFeature, Zone, TurnState, Participant, Group, CombatState, DecisionPoint, Intent, Outcome
#   Всё Pydantic с extra="forbid", цикл model_dump_json -> model_validate_json без потерь,
#   в схеме нет float (время -- целые секунды).
#   SessionState.active_combat: CombatState | None; SessionState.pending_decision:
#   DecisionPoint | None (D6): произвольный dict в них больше не принимается.
#   current_chapter пока остаётся dict (xfail-сторож в test_save_bundle.py).
#   Отпечаток tests/schema/save_v1.schema.json перегенерируется ОСОЗНАННО без подъёма версии
#   (правило и команда -- в шапке tests/unit/persistence/test_schema_fingerprint.py); сменил поле
#   боя -- перегенерируй, иначе test_save_bundle_schema_matches_fingerprint красный.
#   CombatState.savage_used: list[str] = [] -- герои, уже бросавшие кубики Savage Attacker в
#   текущем ходу («раз за любой ход», ревью партии 5, п. 3): поле состояния боя, не TurnState и не
#   память движка, значит переживает сейв/загрузку; сбрасывается в начале каждого хода.
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.combat import (
    CombatState,
    DecisionPoint,
    Group,
    Participant,
    TurnState,
    Zone,
    ZoneFeature,
)
from ai_dm.state.creature import CreatureState
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.world import WorldState

SCHEMA = Path(__file__).resolve().parents[2] / "schema" / "save_v1.schema.json"


def make_combat():
    return CombatState(
        id="fight_1", round=2, turn_index=1, initiative_order=["goblin_1", "hero"],
        zones=[
            Zone(id="door", name="У двери", adjacent=["hall"], exit=True),
            Zone(
                id="hall", name="Центр зала", adjacent=["door"],
                features=[ZoneFeature(kind="hazard", damage="1d6", save="dex", dc=12)],
            ),
        ],
        participants=[
            Participant(
                ref="hero", side="heroes", group_id="party", zone_id="door", initiative=11,
                controller="auto_hero", last_hit_by="goblin_1",
            ),
            Participant(
                ref="goblin_1", side="enemies", group_id="goblins", zone_id="hall",
                monster_id="goblin_warrior", initiative=14, status="active",
                turn=TurnState(action=False, move=0, disengaged=True),
            ),
        ],
        groups={
            "party": Group(leader_id="hero"),
            "goblins": Group(leader_id="goblin_1", intent="capture", lair_location_id="den"),
        },
        log=["раунд 1", "гоблин атакует"], defeat_group_id="goblins",
    )


def make_decision():
    return DecisionPoint(
        kind="intent_reconsider", actor="goblin_1", options=["keep", "intent:kill"],
        subject="hero", attacker="goblin_2",
    )


def make_bundle(session):
    return SaveBundle(
        manifest=Manifest(
            schema_version=1, engine_version="0.1.0", world_id="w1", campaign_id=None,
            slot="auto", saved_at="2026-01-01T12:00:00Z", current_hero_id=None, heroes=[],
        ),
        world=WorldState(world_id="w1", rng=Rng(7).state),
        chronicle=Chronicle(), memory=Memory(), heroes=[], session=session,
    )


# модели

def test_combat_state_survives_json_roundtrip():
    combat = make_combat()
    again = CombatState.model_validate_json(combat.model_dump_json())
    assert again == combat


def test_second_dump_is_byte_identical():
    first = make_combat().model_dump_json()
    assert CombatState.model_validate_json(first).model_dump_json() == first


def test_anonymous_monster_keeps_its_creature_through_json():
    p = Participant(
        ref="goblin_1", side="enemies", group_id="goblins", zone_id="hall",
        monster_id="goblin_warrior", name="Воин-гоблин",
        creature=CreatureState(hp_current=4, hp_max=10),
    )
    again = Participant.model_validate_json(p.model_dump_json())
    assert again.creature.hp_current == 4
    assert again.name == "Воин-гоблин"


def test_new_combat_has_sane_defaults():
    combat = CombatState(
        id="c", zones=[], participants=[], groups={},
    )
    assert combat.round == 0
    assert combat.turn_index == 0
    assert combat.initiative_order == []
    assert combat.outcome is None
    assert combat.log == []
    assert combat.budget_override_reason is None
    assert combat.defeat_group_id is None
    assert combat.savage_used == []


def test_participant_defaults():
    p = Participant(ref="hero", side="heroes", group_id="party")
    assert p.zone_id is None
    assert p.initiative is None
    assert p.status == "active"
    assert p.controller == "engine"
    assert p.monster_id is None
    assert p.intent is None
    assert p.surprised is False
    assert p.last_hit_by is None
    assert p.creature is None
    assert p.name == ""


def test_turn_state_defaults():
    turn = TurnState()
    assert (turn.action, turn.bonus, turn.reaction) == (True, True, True)
    assert turn.move == 1
    assert turn.disengaged is False


def test_zone_defaults():
    zone = Zone(id="a", name="А", adjacent=[])
    assert zone.features == []
    assert zone.exit is False


@pytest.mark.parametrize("intent", ["torture", "KILL", ""])
def test_group_rejects_unknown_intent(intent):
    with pytest.raises(ValidationError):
        Group(leader_id="x", intent=intent)


@pytest.mark.parametrize("intent", ["kill", "capture", "rob", "drive_off", "spare"])
def test_group_accepts_the_five_intents(intent):
    assert Group(leader_id="x", intent=intent).intent == intent


def test_combat_rejects_unknown_outcome():
    with pytest.raises(ValidationError):
        CombatState(id="c", zones=[], participants=[], groups={}, outcome="draw")


@pytest.mark.parametrize(
    "outcome",
    ["victory", "defeat_pending", "hero_dying", "hero_dead", "fled", "ended_by_master"],
)
def test_combat_accepts_every_documented_outcome(outcome):
    combat = CombatState(id="c", zones=[], participants=[], groups={}, outcome=outcome)
    assert combat.outcome == outcome


def test_participant_rejects_unknown_side_and_status():
    with pytest.raises(ValidationError):
        Participant(ref="x", side="neutral", group_id="g")
    with pytest.raises(ValidationError):
        Participant(ref="x", side="heroes", group_id="g", status="sleeping")


def test_models_forbid_extra_fields():
    with pytest.raises(ValidationError):
        Zone(id="a", name="А", adjacent=[], bogus=1)
    with pytest.raises(ValidationError):
        CombatState(id="c", zones=[], participants=[], groups={}, bogus=1)
    with pytest.raises(ValidationError):
        DecisionPoint(kind="turn_action", actor="x", options=[], bogus=1)


def test_decision_point_roundtrip():
    point = make_decision()
    assert DecisionPoint.model_validate_json(point.model_dump_json()) == point


def test_decision_point_rejects_unknown_kind():
    with pytest.raises(ValidationError):
        DecisionPoint(kind="chat", actor="x", options=[])


# сессия

def test_session_takes_a_typed_combat_and_decision():
    session = SessionState(active_combat=make_combat(), pending_decision=make_decision())
    assert isinstance(session.active_combat, CombatState)
    assert isinstance(session.pending_decision, DecisionPoint)


def test_session_dict_becomes_a_typed_combat():
    data = {"active_combat": json.loads(make_combat().model_dump_json())}
    session = SessionState.model_validate(data)
    assert isinstance(session.active_combat, CombatState)
    assert session.active_combat.round == 2


def test_session_rejects_an_arbitrary_dict_as_combat():
    with pytest.raises(ValidationError):
        SessionState(active_combat={"anything": "goes"})


def test_session_rejects_an_arbitrary_dict_as_decision():
    with pytest.raises(ValidationError):
        SessionState(pending_decision={"anything": "goes"})


def test_session_with_combat_survives_json_roundtrip():
    session = SessionState(active_combat=make_combat(), pending_decision=make_decision())
    again = SessionState.model_validate_json(session.model_dump_json())
    assert again == session


def test_bundle_with_a_combat_in_progress_survives_roundtrip():
    bundle = make_bundle(SessionState(active_combat=make_combat()))
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again == bundle
    assert again.session.active_combat.participants[1].turn.disengaged is True


def test_bundle_with_a_combat_dumps_the_same_bytes_twice():
    bundle = make_bundle(SessionState(active_combat=make_combat()))
    first = bundle.model_dump_json()
    assert SaveBundle.model_validate_json(first).model_dump_json() == first


def test_empty_session_still_has_no_combat():
    session = SessionState()
    assert session.active_combat is None
    assert session.pending_decision is None


def test_current_chapter_is_typed_since_stage_3():
    chapter = {"id": "ch_1", "number": 1, "title": "", "started_at_s": 0, "scene_count": 0,
               "closed_reason": None}
    session = SessionState(current_chapter=chapter)
    assert session.current_chapter.model_dump() == chapter


# отпечаток

def test_stored_fingerprint_knows_the_combat_models():
    stored = json.loads(SCHEMA.read_text(encoding="utf-8"))
    assert "CombatState" in stored["$defs"]
    assert "DecisionPoint" in stored["$defs"]


def test_schema_of_the_bundle_has_the_combat_models():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "CombatState" in defs
    assert "DecisionPoint" in defs


def test_savage_used_lives_in_the_combat_state_and_survives_json():
    combat = CombatState(id="c", zones=[], participants=[], groups={}, savage_used=["hero"])
    again = CombatState.model_validate_json(combat.model_dump_json())
    assert again.savage_used == ["hero"]


def test_savage_used_is_not_shared_between_combats():
    first = CombatState(id="a", zones=[], participants=[], groups={})
    second = CombatState(id="b", zones=[], participants=[], groups={})
    first.savage_used.append("hero")
    assert second.savage_used == []


def test_savage_used_is_not_a_turn_state_field():
    assert "savage_used" not in TurnState().model_dump()
