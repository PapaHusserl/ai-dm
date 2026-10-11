# Этап 5, P6 (п. 2, 7; В-4): чистая функция выбора рисунка без Textual.
# API: ai_dm.art.pick_picture(prev_state, state, events) -> Picture | None;
#   PictureState(location, monster, combat_id) -- Location героя, первый живой враг боя (Monster),
#   id идущего боя; prev_state None -- старт игры; events -- имена "victory", "death", "level_up";
#   Picture(kind, text): kind "event" / "monster" (временные: TUI сворачивает после следующего хода)
#   / "location"; None -- «оставить как есть».
import pytest

import ai_dm.art as art_pkg
from ai_dm.art import Picture, PictureState
from ai_dm.state.world import Location


def state(location=None, monster=None, combat_id=None):
    return PictureState(location=location, monster=monster, combat_id=combat_id)


def place(location_id):
    return Location(id=location_id, name="Место")


def pick(prev, now, events=()):
    return art_pkg.pick_picture(prev, now, set(events))


def loc_picture(location_id):
    return Picture("location", art_pkg.art_for_location(place(location_id)))


def event_picture(name):
    return Picture("event", art_pkg.art_for_event(name))


# локации

def test_first_turn_gives_location_drawing():
    assert pick(None, state(place("lame_goose"))) == loc_picture("lame_goose")


def test_first_turn_in_location_without_drawing_gives_none():
    assert pick(None, state(place("nowhere"))) is None


def test_first_turn_without_location_gives_none():
    assert pick(None, state()) is None


def test_location_change_gives_new_location_drawing():
    prev, now = state(place("lame_goose")), state(place("cellar"))
    assert pick(prev, now) == loc_picture("cellar")


def test_location_appears_after_none_gives_drawing():
    assert pick(state(), state(place("cellar"))) == loc_picture("cellar")


def test_same_location_gives_none():
    assert pick(state(place("cellar")), state(place("cellar"))) is None


def test_same_id_different_object_gives_none():
    assert pick(state(place("cellar")), state(Location(id="cellar", name="Другое"))) is None


def test_location_change_to_place_without_drawing_gives_none():
    assert pick(state(place("cellar")), state(place("nowhere"))) is None


# бой

def test_combat_start_gives_monster_drawing(registry):
    goblin = registry.get("monster", "goblin_warrior")
    prev, now = state(place("cellar")), state(place("cellar"), goblin, "c1")
    assert pick(prev, now) == Picture("monster", art_pkg.art_for_monster(goblin))


def test_combat_start_with_location_change_prefers_monster(registry):
    goblin = registry.get("monster", "goblin_boss")
    prev, now = state(place("lame_goose")), state(place("cellar"), goblin, "c1")
    assert pick(prev, now) == Picture("monster", art_pkg.art_for_monster(goblin))


def test_ongoing_combat_gives_none(registry):
    goblin = registry.get("monster", "goblin_warrior")
    prev = state(place("cellar"), goblin, "c1")
    assert pick(prev, state(place("cellar"), goblin, "c1")) is None


def test_next_combat_gives_monster_drawing(registry):
    boss = registry.get("monster", "goblin_boss")
    prev = state(place("cellar"), registry.get("monster", "goblin_warrior"), "c1")
    assert pick(prev, state(place("cellar"), boss, "c2")) == Picture(
        "monster", art_pkg.art_for_monster(boss)
    )


def test_combat_without_monster_gives_none():
    prev, now = state(place("cellar")), state(place("cellar"), None, "c1")
    assert pick(prev, now) is None


def test_combat_start_of_monster_without_drawing_gives_none(registry):
    mystery = registry.get("monster", "goblin_warrior").model_copy(
        update={"id": "mystery_x", "creature_type": "zzz_unknown"}
    )
    prev, now = state(place("cellar")), state(place("cellar"), mystery, "c1")
    assert pick(prev, now) is None


def test_combat_end_without_event_gives_none(registry):
    goblin = registry.get("monster", "goblin_warrior")
    prev = state(place("cellar"), goblin, "c1")
    assert pick(prev, state(place("cellar"))) is None


def test_first_turn_in_combat_gives_location_not_monster(registry):
    goblin = registry.get("monster", "goblin_warrior")
    assert pick(None, state(place("cellar"), goblin, "c1")) == loc_picture("cellar")


# события

@pytest.mark.parametrize("name", ["victory", "death", "level_up"])
def test_event_gives_event_drawing(name):
    prev, now = state(place("cellar")), state(place("cellar"))
    assert pick(prev, now, [name]) == event_picture(name)


@pytest.mark.parametrize("name", ["victory", "death", "level_up"])
def test_event_works_on_first_turn(name):
    assert pick(None, state(place("cellar")), [name]) == event_picture(name)


def test_event_beats_location_change():
    prev, now = state(place("lame_goose")), state(place("cellar"))
    assert pick(prev, now, ["victory"]) == event_picture("victory")


def test_event_beats_combat_start(registry):
    goblin = registry.get("monster", "goblin_warrior")
    prev, now = state(place("cellar")), state(place("cellar"), goblin, "c1")
    assert pick(prev, now, ["level_up"]) == event_picture("level_up")


@pytest.mark.parametrize("other", [["victory"], ["level_up"], ["victory", "level_up"]])
def test_death_beats_other_events(other):
    prev, now = state(place("cellar")), state(place("cellar"))
    assert pick(prev, now, ["death", *other]) == event_picture("death")


def test_victory_beats_level_up():
    prev, now = state(place("cellar")), state(place("cellar"))
    assert pick(prev, now, ["level_up", "victory"]) == event_picture("victory")


def test_event_without_drawing_falls_to_next_event(monkeypatch):
    real = art_pkg.art_for_event
    monkeypatch.setattr(
        "ai_dm.art.pick.art_for_event", lambda name: None if name == "death" else real(name)
    )
    prev, now = state(place("cellar")), state(place("cellar"))
    assert pick(prev, now, ["death", "victory"]) == event_picture("victory")


def test_event_without_any_drawing_falls_to_location(monkeypatch):
    monkeypatch.setattr("ai_dm.art.pick.art_for_event", lambda name: None)
    prev, now = state(place("lame_goose")), state(place("cellar"))
    assert pick(prev, now, ["victory"]) == loc_picture("cellar")


def test_no_events_do_not_replace_drawing():
    assert pick(state(place("cellar")), state(place("cellar")), []) is None
