# Ожидаемый API: ai_dm.state.save, ai_dm.state.memory, ai_dm.state.session
#   ai_dm.state.memory
#     Chronicle(entries: list[dict] = [])
#     Memory(scenes: list[dict] = [], chapters: list[dict] = [], game_summary: str = "",
#            recent_turns: list[dict] = [])
#   ai_dm.state.session
#     SessionState(current_scene=None, current_chapter=None, active_combat=None,
#                  pending_decision=None)    -- нет обязательных полей
#   ai_dm.state.save
#     Manifest(schema_version: int, engine_version: str, world_id: str, campaign_id: str | None,
#              slot: str, saved_at: str, current_hero_id: str | None, heroes: list[str])
#     SaveBundle(manifest, world: WorldState, chronicle: Chronicle, memory: Memory,
#                heroes: list[HeroState], session: SessionState)
#   Всё -- Pydantic с extra="forbid"; цикл model_dump_json -> model_validate_json без потерь.
#   В схеме сейва нет float: SaveBundle.model_json_schema() рекурсивно не содержит
#   "type": "number" (int -- "integer"; время -- целые секунды, множители -- int).
#   Этап 2: current_scene -- SceneState | None, recent_turns -- list[TurnRecord], см. test_scene.py;
#   current_scene в стороже ниже уже обычный, strict-xfail остался только у current_chapter.
#   Сторож (D6): в SessionState нет полей типа голый dict. Партия 5 типизировала active_combat
#   (CombatState | None) и pending_decision (DecisionPoint | None) -- для них сторож обычный
#   (см. tests/unit/state/test_combat_state.py); current_scene / current_chapter остаются dict:
#   xfail(strict=True), пока их не типизируют (спецификация этапа 1 этого не требует).
#   Когда поле типизируют, strict-xfail станет XPASS=красный: снять метку.
#   Модели героя/мира -- см. test_world_models.py, триггеры -- test_triggers.py.
import typing

import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.creature import ActiveEffect, AppliedCondition, CreatureState, Expiry
from ai_dm.state.death import DeathRecord
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState, InventoryEntry
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.save import Manifest, SaveBundle
from ai_dm.state.session import SessionState
from ai_dm.state.world import NPC, GlobalEvent, Location, Tone, WorldState


def make_hero(hero_id, ordinal, name):
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id=hero_id, ordinal=ordinal, name=name, sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
        inventory=[InventoryEntry(item_id="longsword", qty=1, cost_cp=0)],
        money_cp=1235,
    )


def make_world():
    npc = NPC.model_validate(
        {
            "id": "mentor_aldric",
            "name": "Олдрик",
            "named": True,
            "key": True,
            "means": ["магия крови", "долг гильдии воров"],
            "motive": "спасти сестру",
            "attitude": 20,
            "opportunity": [
                {
                    "id": "steal_grail",
                    "if": {
                        "all": [
                            {"hero_has": "blood_grail"},
                            {"npc_status": {"id": "mentor_aldric", "is": "alive"}},
                        ]
                    },
                    "then": "выкрадет Грааль",
                    "once": True,
                },
                {"id": "sister", "if": {"narrative": "герой узнаёт тайну"}, "then": "уговорит"},
            ],
            "secrets": [
                {"id": "sister_vampire", "text": "сестра -- вампир", "reveal_if": {"flag": "found"}}
            ],
        }
    )
    world = WorldState(world_id="w1", campaign_id="vale", rng=Rng(7).state)
    world.npcs[npc.id] = npc
    world.flags["met_aldric"] = True
    world.events.append(GlobalEvent(id="grey_plague", type="plague", regions=["port_vale"]))
    world.tone = Tone(mood="мрачный", violence="реалистично", hard_limits=["насилие над детьми"])
    return world


def make_manifest(heroes):
    return Manifest(
        schema_version=1,
        engine_version="0.1.0",
        world_id="w1",
        campaign_id="vale",
        slot="slot1",
        saved_at="2026-01-01T12:00:00Z",
        current_hero_id="h1",
        heroes=heroes,
    )


def make_bundle():
    return SaveBundle(
        manifest=make_manifest(["h1", "h2"]),
        world=make_world(),
        chronicle=Chronicle(),
        memory=Memory(),
        heroes=[make_hero("h1", 1, "Арн"), make_hero("h2", 2, "Бранка")],
        session=SessionState(),
    )


def test_bundle_assembles_with_two_heroes():
    assert [h.id for h in make_bundle().heroes] == ["h1", "h2"]


def test_full_bundle_survives_json_roundtrip():
    bundle = make_bundle()
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again == bundle


def test_second_dump_is_byte_identical_to_first():
    bundle = make_bundle()
    first = bundle.model_dump_json()
    second = SaveBundle.model_validate_json(first).model_dump_json()
    assert second == first


def test_roundtrip_keeps_npc_trigger_condition():
    again = SaveBundle.model_validate_json(make_bundle().model_dump_json())
    trigger = again.world.npcs["mentor_aldric"].opportunity[0]
    assert trigger.if_.type == "all"
    assert trigger.once is True


def test_roundtrip_keeps_secret_flag_event_and_tone():
    again = SaveBundle.model_validate_json(make_bundle().model_dump_json())
    assert again.world.npcs["mentor_aldric"].secrets[0].id == "sister_vampire"
    assert again.world.flags == {"met_aldric": True}
    assert again.world.events[0].id == "grey_plague"
    assert again.world.tone.mood == "мрачный"
    assert again.world.tone.hard_limits == ["насилие над детьми"]


def test_roundtrip_keeps_hero_inventory_and_money():
    again = SaveBundle.model_validate_json(make_bundle().model_dump_json())
    assert again.heroes[0].inventory[0].item_id == "longsword"
    assert again.heroes[0].money_cp == 1235


def test_roundtrip_keeps_rng_state():
    again = SaveBundle.model_validate_json(make_bundle().model_dump_json())
    assert again.world.rng == Rng(7).state


def test_empty_session_survives_roundtrip():
    session = SessionState()
    assert SessionState.model_validate_json(session.model_dump_json()) == session


def test_empty_session_has_no_scene_chapter_or_combat():
    session = SessionState()
    assert session.current_scene is None
    assert session.current_chapter is None
    assert session.active_combat is None
    assert session.pending_decision is None


def test_empty_sections_stay_empty_after_roundtrip():
    bundle = SaveBundle(
        manifest=make_manifest([]),
        world=WorldState(world_id="w1", rng=Rng(1).state),
        chronicle=Chronicle(),
        memory=Memory(),
        heroes=[],
        session=SessionState(),
    )
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again.world.pantheon == {}
    assert again.world.events == []
    assert again.world.flags == {}
    assert again.heroes == []
    assert again.memory.scenes == []
    assert again.memory.chapters == []
    assert again.memory.recent_turns == []
    assert again.chronicle.entries == []


def test_bundle_rejects_extra_field_at_top_level():
    data = make_bundle().model_dump(mode="json")
    data["bogus"] = 1
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def test_bundle_rejects_extra_field_in_world():
    data = make_bundle().model_dump(mode="json")
    data["world"]["bogus"] = 1
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def test_bundle_rejects_extra_field_in_hero():
    data = make_bundle().model_dump(mode="json")
    data["heroes"][0]["bogus"] = 1
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def test_bundle_rejects_extra_field_in_manifest():
    data = make_bundle().model_dump(mode="json")
    data["manifest"]["bogus"] = 1
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def test_bundle_without_manifest_raises_validation_error():
    data = make_bundle().model_dump(mode="json")
    del data["manifest"]
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def test_manifest_lists_hero_ids_and_current_hero():
    manifest = make_bundle().manifest
    assert manifest.heroes == ["h1", "h2"]
    assert manifest.current_hero_id == "h1"
    assert manifest.schema_version == 1


# сторож: в сейве нет float

def find_number_types(node, path="$"):
    found = []
    if isinstance(node, dict):
        if node.get("type") == "number":
            found.append(path)
        for key, value in node.items():
            found.extend(find_number_types(value, f"{path}.{key}"))
    elif isinstance(node, list):
        for i, value in enumerate(node):
            found.extend(find_number_types(value, f"{path}[{i}]"))
    return found


def test_save_schema_has_no_float_fields():
    assert find_number_types(SaveBundle.model_json_schema()) == []


def test_number_finder_sees_a_float_field():
    from pydantic import BaseModel

    class WithFloat(BaseModel):
        x: float

    assert find_number_types(WithFloat.model_json_schema()) != []


def test_global_event_roundtrip_keeps_hazard_and_seconds():
    bundle = make_bundle()
    bundle.world.events[0] = GlobalEvent.model_validate(
        {
            "id": "grey_plague",
            "type": "plague",
            "mortality_multiplier": 2,
            "hazard": {"save": "con", "dc_category": "hard"},
            "started_s": 100,
            "ends_at_s": 9000,
            "ends_when": {"flag": "cure_found"},
        }
    )
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    event = again.world.events[0]
    assert event.mortality_multiplier == 2
    assert event.hazard.dc_category == "hard"
    assert (event.started_s, event.ends_at_s) == (100, 9000)
    assert event.ends_when.type == "flag"


def test_roundtrip_keeps_favor_death_and_conditions():
    bundle = make_bundle()
    hero = bundle.heroes[0]
    hero.favor = {"morrah": 4}
    hero.death = DeathRecord(cause="chance", at_s=77, text="упал")
    hero.creature.conditions.append(AppliedCondition(id="poisoned", source="goblin_boss"))
    hero.creature.active_effects.append(
        ActiveEffect(
            id="e1", source="bless", kind="modifier", params={"dice": "1d4"},
            expires=Expiry(kind="concentration", owner="h1"),
        )
    )
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again == bundle
    assert again.heroes[0].favor == {"morrah": 4}
    assert again.heroes[0].death.at_s == 77
    assert again.heroes[0].creature.conditions[0].source == "goblin_boss"


def test_roundtrip_keeps_location_connections_and_npc_birth():
    bundle = make_bundle()
    bundle.world.locations["port_vale"] = Location.model_validate(
        {"id": "port_vale", "name": "Порт", "connections": [{"to": "tavern", "distance_m": 300}]}
    )
    bundle.world.npcs["mentor_aldric"].birth_s = -1000
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again.world.locations["port_vale"].connections[0].distance_m == 300
    assert again.world.npcs["mentor_aldric"].birth_s == -1000


def test_roundtrip_keeps_trigger_state():
    bundle = make_bundle()
    bundle.world.npcs["mentor_aldric"].opportunity[0].state = "fired"
    again = SaveBundle.model_validate_json(bundle.model_dump_json())
    assert again.world.npcs["mentor_aldric"].opportunity[0].state == "fired"


def test_memory_accepts_typed_summaries_in_lists():
    memory = Memory(
        scenes=[{"id": "s1", "chapter_id": "ch_1", "title": "", "summary": "кратко", "at_s": 0}],
        chapters=[{"id": "ch_1", "number": 1, "title": "", "summary": "кратко"}],
    )
    assert Memory.model_validate_json(memory.model_dump_json()) == memory


def test_memory_rejects_non_dict_items():
    with pytest.raises(ValidationError):
        Memory(scenes=["просто текст"])


def test_bundle_rejects_npc_stored_under_wrong_key():
    data = make_bundle().model_dump(mode="json")
    data["world"]["npcs"] = {"wrong_key": data["world"]["npcs"]["mentor_aldric"]}
    with pytest.raises(ValidationError):
        SaveBundle.model_validate(data)


def is_bare_dict(annotation):
    parts = typing.get_args(annotation) or (annotation,)
    return any(part is dict or typing.get_origin(part) is dict and not typing.get_args(part)
               for part in parts)


def test_session_state_has_no_unexpected_bare_dict_fields():
    typed_later = {"current_chapter"}
    bare = [
        name for name, field in SessionState.model_fields.items()
        if is_bare_dict(field.annotation) and name not in typed_later
    ]
    assert bare == []


@pytest.mark.parametrize("name", ["current_scene", "active_combat", "pending_decision"])
def test_combat_session_field_is_typed(name):
    assert not is_bare_dict(SessionState.model_fields[name].annotation)


# этап 3: current_chapter типизирован (ChapterState), метка xfail снята
@pytest.mark.parametrize("name", ["current_chapter"])
def test_session_field_is_not_bare_dict(name):
    assert not is_bare_dict(SessionState.model_fields[name].annotation)


# этап 4, P1: источник выжимок, глава game_summary, сцена хода (схема v5)

def test_scene_summary_source_defaults_to_pack():
    from ai_dm.state.memory import SceneSummary

    assert SceneSummary(id="s", summary="x").source == "pack"


def test_scene_summary_source_accepts_summarizer_and_rejects_unknown():
    from ai_dm.state.memory import SceneSummary

    assert SceneSummary(id="s", summary="x", source="summarizer").source == "summarizer"
    with pytest.raises(ValidationError):
        SceneSummary(id="s", summary="x", source="bogus")


def test_chapter_summary_source_and_at_s_defaults():
    from ai_dm.state.memory import ChapterSummary

    chapter = ChapterSummary(id="c", number=1)
    assert chapter.source == "pack"
    assert chapter.at_s == 0
    assert ChapterSummary(id="c", number=1, source="concat").source == "concat"


def test_memory_game_summary_chapter_defaults_to_zero():
    assert Memory().game_summary_chapter == 0


def test_turn_record_scene_id_defaults_to_empty():
    from ai_dm.state.scene import TurnRecord

    record = TurnRecord(turn_seq=1, at_s=0, player_input="a", narration="b")
    assert record.scene_id == ""
