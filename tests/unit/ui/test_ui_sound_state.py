# Му-а (MU-PLAN B1, A4): ui.screen.sound_state(app) -> SoundState(location_id, tags, in_combat,
# horror,
# romance) и location_tag_chain(world, location) -- теги локации, затем родителя и дальше вверх
# по parent_id (свои первыми), без зацикливания.
from types import SimpleNamespace

import pytest

from ai_dm.audio.select import SoundState
from ai_dm.state.world import Location, Tone
from ai_dm.ui import screen


def place(id, parent=None, tags=()):
    return Location(id=id, name=id, parent_id=parent, tags=list(tags))


def world_of(*places, tone=None):
    return SimpleNamespace(
        locations={p.id: p for p in places}, tone=Tone() if tone is None else tone
    )


def make_app(world, combat=None, scene=None):
    session = SimpleNamespace(active_combat=combat, current_scene=scene)
    return SimpleNamespace(bundle=SimpleNamespace(world=world, session=session))


@pytest.fixture
def hero_at(monkeypatch):
    def put(location_id):
        hero = SimpleNamespace(location_id=location_id)

        def hero_of(bundle):
            assert hasattr(bundle, "world")
            return hero

        monkeypatch.setattr(screen, "hero_of", hero_of)

    return put


# location_tag_chain

def test_chain_own_tags_only():
    cellar = place("cellar", tags=["подвал"])
    assert screen.location_tag_chain(world_of(cellar), cellar) == ("подвал",)


def test_chain_no_tags_anywhere():
    cellar = place("cellar")
    assert screen.location_tag_chain(world_of(cellar), cellar) == ()


def test_chain_own_then_parent_then_grandparent():
    root = place("root", tags=["горы"])
    mid = place("mid", "root", ["деревня", "предгорья"])
    leaf = place("leaf", "mid", ["таверна"])
    chain = screen.location_tag_chain(world_of(root, mid, leaf), leaf)
    assert chain == ("таверна", "деревня", "предгорья", "горы")


def test_chain_skips_untagged_levels():
    root = place("root", tags=["город"])
    mid = place("mid", "root")
    leaf = place("leaf", "mid")
    assert screen.location_tag_chain(world_of(root, mid, leaf), leaf) == ("город",)


def test_chain_unknown_parent_stops():
    leaf = place("leaf", "ghost", ["лес"])
    assert screen.location_tag_chain(world_of(leaf), leaf) == ("лес",)


def test_chain_cycle_does_not_loop():
    first = place("a", "b", ["один"])
    second = place("b", "a", ["два"])
    assert screen.location_tag_chain(world_of(first, second), first) == ("один", "два")


def test_chain_self_parent_does_not_loop():
    loop = place("a", "a", ["один"])
    assert screen.location_tag_chain(world_of(loop), loop) == ("один",)


def test_chain_does_not_change_location_tags():
    root = place("root", tags=["горы"])
    leaf = place("leaf", "root", ["лес"])
    screen.location_tag_chain(world_of(root, leaf), leaf)
    assert leaf.tags == ["лес"]


# sound_state

def test_state_without_combat_collects_tags_up_the_parents(hero_at):
    hero_at("leaf")
    root = place("root", tags=["горы"])
    mid = place("mid", "root", ["деревня"])
    leaf = place("leaf", "mid", ["таверна"])
    state = screen.sound_state(make_app(world_of(root, mid, leaf)))
    assert state == SoundState("leaf", ("таверна", "деревня", "горы"), False, "", "")


def test_state_unknown_location_gives_none_and_no_tags(hero_at):
    hero_at("ghost")
    state = screen.sound_state(make_app(world_of(place("cellar", tags=["подвал"]))))
    assert state.location_id is None
    assert state.tags == ()


def test_state_in_combat(hero_at):
    hero_at("cellar")
    state = screen.sound_state(make_app(world_of(place("cellar")), combat=object()))
    assert state.in_combat is True


def test_state_not_in_combat_when_no_active_combat(hero_at):
    hero_at("cellar")
    assert screen.sound_state(make_app(world_of(place("cellar")))).in_combat is False


def test_state_tone_axes_come_from_world(hero_at):
    hero_at("cellar")
    tone = Tone(horror="сильно", romance="намёки")
    state = screen.sound_state(make_app(world_of(place("cellar"), tone=tone)))
    assert (state.horror, state.romance) == ("сильно", "намёки")


def test_state_tags_are_a_tuple(hero_at):
    hero_at("cellar")
    state = screen.sound_state(make_app(world_of(place("cellar", tags=["подвал"]))))
    assert isinstance(state.tags, tuple)


# Ж3: scene_mood из текущей сцены

def test_state_scene_mood_comes_from_current_scene(hero_at):
    hero_at("cellar")
    scene = SimpleNamespace(scene_mood="romance")
    state = screen.sound_state(make_app(world_of(place("cellar")), scene=scene))
    assert state.scene_mood == "romance"


def test_state_scene_mood_empty_without_scene(hero_at):
    hero_at("cellar")
    assert screen.sound_state(make_app(world_of(place("cellar")))).scene_mood == ""


def test_state_scene_mood_empty_when_scene_has_none(hero_at):
    hero_at("cellar")
    scene = SimpleNamespace(scene_mood="")
    state = screen.sound_state(make_app(world_of(place("cellar")), scene=scene))
    assert state.scene_mood == ""
