# Этап 5, P6: ui.screen.picture_state(app) -> PictureState(location, monster, combat_id):
# локация героя; в бою -- первый живой враг (side enemies, status active, есть monster_id) и id боя.
from types import SimpleNamespace

import pytest

from ai_dm.state.world import Location
from ai_dm.ui import screen

PLACE = Location(id="cellar", name="Подвал")


def part(side="enemies", status="active", monster_id="goblin_warrior"):
    return SimpleNamespace(side=side, status=status, monster_id=monster_id)


def make_app(registry, combat):
    world = SimpleNamespace(locations={"cellar": PLACE})
    session = SimpleNamespace(active_combat=combat)
    return SimpleNamespace(bundle=SimpleNamespace(world=world, session=session), registry=registry)


@pytest.fixture(autouse=True)
def hero_in_cellar(monkeypatch):
    monkeypatch.setattr(screen, "hero_of", lambda bundle: SimpleNamespace(location_id="cellar"))


def fight(*parts):
    return SimpleNamespace(id="c1", participants=list(parts))


def test_no_combat_gives_location_only(registry):
    state = screen.picture_state(make_app(registry, None))
    assert (state.location, state.monster, state.combat_id) == (PLACE, None, None)


def test_unknown_location_gives_none(registry):
    app = make_app(registry, None)
    app.bundle.world.locations = {}
    assert screen.picture_state(app).location is None


def test_combat_gives_location_id_and_first_enemy(registry):
    state = screen.picture_state(make_app(registry, fight(part())))
    assert state.location == PLACE
    assert state.combat_id == "c1"
    assert state.monster.id == "goblin_warrior"


def test_combat_without_active_enemy_gives_no_monster(registry):
    state = screen.picture_state(make_app(registry, fight(part(status="dead"))))
    assert state.monster is None
    assert state.combat_id == "c1"


def test_hero_side_is_skipped(registry):
    state = screen.picture_state(make_app(registry, fight(part("heroes", monster_id="guard"))))
    assert state.monster is None


def test_enemy_without_monster_id_is_skipped(registry):
    state = screen.picture_state(make_app(registry, fight(part(monster_id=None))))
    assert state.monster is None


def test_inactive_enemy_is_skipped_for_next_active(registry):
    combat = fight(part(status="down", monster_id="guard"), part(monster_id="goblin_boss"))
    assert screen.picture_state(make_app(registry, combat)).monster.id == "goblin_boss"


def test_first_active_enemy_wins(registry):
    combat = fight(part(monster_id="guard"), part(monster_id="goblin_boss"))
    assert screen.picture_state(make_app(registry, combat)).monster.id == "guard"
