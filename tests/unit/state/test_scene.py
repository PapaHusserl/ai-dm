# Ожидаемый API: ai_dm.state.scene, session, memory (этап 2, партия 1).
# Всё -- Pydantic extra="forbid", без float (время -- целые секунды игровых часов)
#   ai_dm.state.scene
#     SceneState(id: str, started_at_s: int, player_turns: int = 0, location_id: str | None = None,
#                attitude_spent: dict[str, int] = {}, closed_reason: None | Literal[...] = None)
#       id и started_at_s обязательны; attitude_spent -- npc_id -> сколько отношения уже
#       потрачено за сцену (лимит attitude.per_scene в RulesConfig);
#       closed_reason: "end_scene" | "location_changed" | "time_jump" | "combat_ended" |
#       "turn_limit" (по A5 плана: end_scene / смена локации / скачок > 1 ч / конец боя /
#       > 30 ходов); другое значение -> ValidationError
#     TurnRecord(turn_seq: int, at_s: int, player_input: str, narration: str,
#                requests: list[str] = [], rolls: list[str] = [])
#       requests -- типы запросов мастера за ход, rolls -- строки бросков (ТЗ 6)
#   ai_dm.state.session
#     SessionState.current_scene: SceneState | None = None
#     SessionState.turn_seq: int = 0            -- счётчик ходов, растёт при commit хода
#     SessionState.offered_choices: list[str] = []  -- варианты последнего offer_choices
#     current_chapter остаётся dict | None (этап 3)
#   ai_dm.state.memory
#     Memory.recent_turns: list[TurnRecord] = []
#   Цикл model_dump_json -> model_validate_json без потерь; два дампа побайтно равны.
import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.scene import SceneState, TurnRecord
from ai_dm.state.session import SessionState
from ai_dm.state.world import WorldState


def make_scene(**kwargs):
    kwargs.setdefault("id", "scene_1")
    kwargs.setdefault("started_at_s", 90000)
    return SceneState(**kwargs)


def make_turn(**kwargs):
    kwargs.setdefault("turn_seq", 1)
    kwargs.setdefault("at_s", 90000)
    kwargs.setdefault("player_input", "Осматриваюсь")
    kwargs.setdefault("narration", "Таверна гудит.")
    return TurnRecord(**kwargs)


def make_bundle(session=None, memory=None):
    return SaveBundle(
        manifest=Manifest(
            schema_version=3, engine_version="0.1.0", world_id="w1", campaign_id=None,
            slot="auto", saved_at="2026-01-01T12:00:00Z", current_hero_id=None, heroes=[],
        ),
        world=WorldState(world_id="w1", rng=Rng(7).state),
        chronicle=Chronicle(), memory=memory or Memory(), heroes=[],
        session=session or SessionState(),
    )


# SceneState

def test_scene_defaults():
    scene = make_scene()
    assert scene.player_turns == 0
    assert scene.location_id is None
    assert scene.attitude_spent == {}
    assert scene.closed_reason is None


def test_scene_requires_id_and_start_time():
    with pytest.raises(ValidationError):
        SceneState(id="s")
    with pytest.raises(ValidationError):
        SceneState(started_at_s=0)


def test_scene_keeps_given_fields():
    scene = make_scene(player_turns=3, location_id="tavern", attitude_spent={"aldric": 10})
    assert (scene.player_turns, scene.location_id) == (3, "tavern")
    assert scene.attitude_spent == {"aldric": 10}


@pytest.mark.parametrize(
    "reason", ["end_scene", "location_changed", "time_jump", "combat_ended", "turn_limit"]
)
def test_scene_accepts_known_closed_reason(reason):
    assert make_scene(closed_reason=reason).closed_reason == reason


def test_scene_rejects_unknown_closed_reason():
    with pytest.raises(ValidationError):
        make_scene(closed_reason="bored")


def test_scene_rejects_extra_field():
    with pytest.raises(ValidationError):
        make_scene(bogus=1)


def test_scene_attitude_spent_must_hold_ints():
    with pytest.raises(ValidationError):
        make_scene(attitude_spent={"aldric": "много"})


def test_scene_roundtrip():
    scene = make_scene(
        location_id="tavern", attitude_spent={"aldric": -10}, closed_reason="turn_limit",
    )
    assert SceneState.model_validate_json(scene.model_dump_json()) == scene


def test_scene_default_dict_is_not_shared_between_instances():
    first = make_scene()
    first.attitude_spent["aldric"] = 10
    assert make_scene().attitude_spent == {}


# TurnRecord

def test_turn_record_defaults():
    turn = make_turn()
    assert turn.requests == []
    assert turn.rolls == []


def test_turn_record_keeps_fields():
    turn = make_turn(requests=["skill_check", "offer_choices"], rolls=["Убеждение 17 vs СЛ 15"])
    assert (turn.turn_seq, turn.at_s) == (1, 90000)
    assert turn.player_input == "Осматриваюсь"
    assert turn.narration == "Таверна гудит."
    assert turn.requests == ["skill_check", "offer_choices"]
    assert turn.rolls == ["Убеждение 17 vs СЛ 15"]


def test_turn_record_rejects_extra_field():
    with pytest.raises(ValidationError):
        make_turn(bogus=1)


def test_turn_record_rejects_float_time():
    with pytest.raises(ValidationError):
        make_turn(at_s=1.5)


def test_turn_record_roundtrip():
    turn = make_turn(requests=["skill_check"], rolls=["д20 = 14"])
    assert TurnRecord.model_validate_json(turn.model_dump_json()) == turn


# SessionState

def test_session_defaults():
    session = SessionState()
    assert session.current_scene is None
    assert session.turn_seq == 0
    assert session.offered_choices == []


def test_session_holds_scene_model():
    session = SessionState(current_scene=make_scene())
    assert isinstance(session.current_scene, SceneState)


def test_session_accepts_scene_as_dict_of_full_form():
    session = SessionState(current_scene={"id": "s1", "started_at_s": 5})
    assert session.current_scene == make_scene(id="s1", started_at_s=5)


def test_session_rejects_old_free_form_scene_dict():
    with pytest.raises(ValidationError):
        SessionState(current_scene={"id": "tavern"})


def test_session_offered_choices_are_strings():
    session = SessionState(offered_choices=["Поговорить", "Уйти"])
    assert session.offered_choices == ["Поговорить", "Уйти"]
    with pytest.raises(ValidationError):
        SessionState(offered_choices=[1])


def test_session_roundtrip_with_scene_and_choices():
    session = SessionState(
        current_scene=make_scene(player_turns=2), turn_seq=2, offered_choices=["Да", "Нет"],
    )
    assert SessionState.model_validate_json(session.model_dump_json()) == session


def test_session_default_choices_list_is_not_shared():
    first = SessionState()
    first.offered_choices.append("x")
    assert SessionState().offered_choices == []


def test_session_current_chapter_is_typed_since_stage_3():
    chapter = {"id": "ch_1", "number": 1, "title": "", "started_at_s": 0, "scene_count": 0,
               "closed_reason": None}
    session = SessionState(current_chapter=chapter)
    assert session.current_chapter.number == 1


# Memory.recent_turns

def test_memory_recent_turns_default_is_empty():
    assert Memory().recent_turns == []


def test_memory_holds_turn_records():
    memory = Memory(recent_turns=[make_turn(), make_turn(turn_seq=2)])
    assert all(isinstance(t, TurnRecord) for t in memory.recent_turns)
    assert [t.turn_seq for t in memory.recent_turns] == [1, 2]


def test_memory_rejects_free_form_turn_dict():
    with pytest.raises(ValidationError):
        Memory(recent_turns=[{"t": 1}])


def test_memory_roundtrip_with_turns():
    memory = Memory(recent_turns=[make_turn(requests=["skill_check"])])
    assert Memory.model_validate_json(memory.model_dump_json()) == memory


# сейв целиком

def test_bundle_with_scene_turns_and_choices_survives_roundtrip():
    bundle = make_bundle(
        session=SessionState(current_scene=make_scene(), turn_seq=1, offered_choices=["Да"]),
        memory=Memory(recent_turns=[make_turn()]),
    )
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again == bundle


def test_second_dump_of_stage2_bundle_is_byte_identical():
    bundle = make_bundle(
        session=SessionState(current_scene=make_scene(attitude_spent={"a": 10}), turn_seq=1),
        memory=Memory(recent_turns=[make_turn()]),
    )
    first = bundle.model_dump_json()
    assert SaveBundle.model_validate_json(first).model_dump_json() == first


def test_bundle_schema_lists_scene_and_turn_models():
    defs = SaveBundle.model_json_schema()["$defs"]
    assert "SceneState" in defs
    assert "TurnRecord" in defs
    assert defs["SceneState"]["additionalProperties"] is False
    assert defs["TurnRecord"]["additionalProperties"] is False
