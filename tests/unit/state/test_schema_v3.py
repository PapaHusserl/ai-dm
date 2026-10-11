# Ожидаемый API: схема сейва v3 (этап 3, партия 1; STAGE3-PLAN A3). Новые поля -- с нейтральными
# значениями по умолчанию (пустые секции не None), модели extra="forbid". Классы создаются через
# родителя (SessionState(current_chapter={...})), чтобы не зависеть от места определения.
#   SessionState.current_chapter: ChapterState | None  {id, number, title, started_at_s,
#       scene_count, closed_reason: "end_chapter" | "scene_limit" | None}
#   SessionState.boundary_pending: bool = False
#   SceneState: summary "", title "", favor_spent {}, touched_main False,
#       hero_initiated_combat False
#   WorldState: lore{world_text}, sim{last_day, last_season, last_year,
#       nudge{scenes_off_main, stage, waiting}, world_calls_today},
#       mortality_per_day 20000, natural{chance_percent_per_season 5},
#       nudge_scenes 8, dangers [], notices [], fired []
#   Tone: violence "" | мягко | реалистично | жестоко; horror "" | нет | умеренно | сильно;
#       romance "" | нет | намёки | есть; language "" | сдержанно | грубо;
#       mood -- свободно; notes ""
#   NPC: groups [], aging_steps 0. HeroState: deity_id None, divine{frozen, debts,
#       intervention_chapter, prayer_day, curse_day_used}, birth_s None. God: servants [],
#       check_every_days 7. Trigger.kills_hero False. Secret.narrative_ok False.
#   GlobalEvent.kind: "natural" | "caused" = "caused"
#   Memory.scenes: list[SceneSummary{id, chapter_id, title, summary, at_s}],
#       Memory.chapters: list[ChapterSummary{id, number, title, summary}]
#   Chronicle.entries: list[ChronicleEntry{at_s, kind, text, refs}], kind: death | event | trigger |
#       tone | pack_update | favor | imported
import pytest
from pydantic import ValidationError

from ai_dm.core.rng import Rng
from ai_dm.state.hero import HeroState
from ai_dm.state.memory import Chronicle, Memory
from ai_dm.state.scene import SceneState
from ai_dm.state.session import SessionState
from ai_dm.state.triggers import Secret, Trigger
from ai_dm.state.world import NPC, GlobalEvent, God, Tone, WorldState

CHAPTER = {
    "id": "ch_1", "number": 1, "title": "Начало", "started_at_s": 0, "scene_count": 0,
    "closed_reason": None,
}


def make_world():
    return WorldState(world_id="w1", rng=Rng(1).state)


# сессия

def test_session_defaults():
    session = SessionState()
    assert session.current_chapter is None
    assert session.boundary_pending is False


def test_chapter_state_is_typed():
    chapter = SessionState(current_chapter=CHAPTER).current_chapter
    assert chapter.id == "ch_1"
    assert chapter.number == 1
    assert chapter.scene_count == 0
    assert chapter.closed_reason is None


@pytest.mark.parametrize("reason", ["end_chapter", "scene_limit"])
def test_chapter_closed_reasons(reason):
    chapter = SessionState(current_chapter=dict(CHAPTER, closed_reason=reason)).current_chapter
    assert chapter.closed_reason == reason


def test_chapter_unknown_reason_is_error():
    with pytest.raises(ValidationError):
        SessionState(current_chapter=dict(CHAPTER, closed_reason="устал"))


def test_chapter_free_form_dict_is_error():
    with pytest.raises(ValidationError):
        SessionState(current_chapter={"id": "c1"})


def test_chapter_extra_key_is_error():
    with pytest.raises(ValidationError):
        SessionState(current_chapter=dict(CHAPTER, bogus=1))


# сцена

def test_scene_new_fields_defaults():
    scene = SceneState(id="scene_1", started_at_s=0)
    assert scene.summary == ""
    assert scene.title == ""
    assert scene.favor_spent == {}
    assert scene.touched_main is False
    assert scene.hero_initiated_combat is False


# мир

def test_world_new_fields_defaults():
    world = make_world()
    assert world.lore.world_text == ""
    assert world.mortality_per_day == 20000
    assert world.nudge_scenes == 8
    assert world.natural.chance_percent_per_season == 5
    assert world.dangers == []
    assert world.notices == []
    assert world.fired == []


def test_world_sim_defaults():
    sim = make_world().sim
    assert sim.last_day == 0
    assert sim.world_calls_today == 0
    assert sim.nudge.scenes_off_main == 0
    assert sim.nudge.stage == 0


def test_world_new_fields_survive_json_roundtrip():
    world = make_world()
    world.mortality_per_day = 500
    world.lore.world_text = "Вейл"
    again = WorldState.model_validate_json(world.model_dump_json())
    assert again == world
    assert again.model_dump_json() == world.model_dump_json()


def test_calendar_has_holidays_and_seasons_in_world():
    calendar = make_world().clock.calendar
    assert calendar.holidays == []
    assert len(calendar.seasons) == 4


# tone

def test_tone_scales_default_to_empty():
    tone = Tone()
    assert (tone.violence, tone.horror, tone.romance, tone.language, tone.notes) == ("",) * 5


@pytest.mark.parametrize("field,value", [
    ("violence", "мягко"), ("violence", "реалистично"), ("violence", "жестоко"),
    ("horror", "нет"), ("horror", "умеренно"), ("horror", "сильно"),
    ("romance", "нет"), ("romance", "намёки"), ("romance", "чувственно"), ("romance", "откровенно"),
    ("language", "сдержанно"), ("language", "грубо"),
])
def test_tone_scale_accepts_listed_values(field, value):
    assert getattr(Tone(**{field: value}), field) == value


@pytest.mark.parametrize("field,value", [
    ("violence", "кроваво"), ("horror", "кровавый"), ("romance", "страстно"),
    ("language", "русский"),
])
def test_tone_scale_rejects_free_text(field, value):
    with pytest.raises(ValidationError):
        Tone(**{field: value})


def test_tone_mood_and_notes_are_free_text():
    tone = Tone(mood="что угодно", notes="свободный стиль")
    assert tone.mood == "что угодно"
    assert tone.notes == "свободный стиль"


# сущности

def test_npc_new_fields_defaults():
    npc = NPC(id="a", name="А", means=["меч"])
    assert npc.groups == []
    assert npc.aging_steps == 0


def test_god_new_fields_defaults():
    god = God(id="g", name="Г")
    assert god.servants == []
    assert god.check_every_days == 7


def test_trigger_kills_hero_defaults_to_false():
    assert Trigger(id="t", **{"if": {"flag": "x"}}, then="y").kills_hero is False


def test_secret_narrative_ok_defaults_to_false():
    assert Secret(id="s", text="т", reveal_if={"flag": "x"}).narrative_ok is False


def test_global_event_kind_defaults_to_caused():
    assert GlobalEvent(id="e", type="plague").kind == "caused"


def test_global_event_kind_natural_and_unknown():
    assert GlobalEvent(id="e", type="storm", kind="natural").kind == "natural"
    with pytest.raises(ValidationError):
        GlobalEvent(id="e", type="storm", kind="случайно")


def test_hero_new_fields_defaults():
    fields = HeroState.model_fields
    assert fields["deity_id"].default is None
    assert fields["birth_s"].default is None
    divine = fields["divine"].default_factory()
    assert divine.frozen == []
    assert divine.debts == []
    assert divine.intervention_chapter is None
    assert divine.prayer_day is None
    assert divine.curse_day_used is None


# память и хроника

def test_memory_scene_and_chapter_summaries_are_typed():
    memory = Memory(
        scenes=[{"id": "scene_1", "chapter_id": "ch_1", "title": "Таверна", "summary": "Гарт",
                 "at_s": 10}],
        chapters=[{"id": "ch_1", "number": 1, "title": "Начало", "summary": "Гусь"}],
    )
    assert memory.scenes[0].summary == "Гарт"
    assert memory.chapters[0].number == 1


def test_memory_free_form_scene_is_error():
    with pytest.raises(ValidationError):
        Memory(scenes=[{"anything": 1}])


@pytest.mark.parametrize("kind", [
    "death", "event", "trigger", "tone", "pack_update", "favor", "imported",
])
def test_chronicle_entry_kinds(kind):
    chronicle = Chronicle(entries=[{"at_s": 5, "kind": kind, "text": "запись"}])
    assert chronicle.entries[0].kind == kind
    assert chronicle.entries[0].refs == []


def test_chronicle_unknown_kind_is_error():
    with pytest.raises(ValidationError):
        Chronicle(entries=[{"at_s": 5, "kind": "сплетня", "text": "запись"}])


def test_chronicle_free_form_entry_is_error():
    with pytest.raises(ValidationError):
        Chronicle(entries=[{"day": 2, "text": "старая форма"}])


def test_v3_models_are_in_schema_defs():
    from ai_dm.state.save import SaveBundle

    defs = SaveBundle.model_json_schema()["$defs"]
    for name in ["ChapterState", "SceneSummary", "ChapterSummary", "ChronicleEntry"]:
        assert name in defs


def test_tone_romance_rejects_old_value_yes():
    with pytest.raises(ValidationError):
        Tone(romance="есть")
