# Му-а (MU-PLAN A5, B1): теги локаций паков vale и drunk_dragon дают тему музыки через
# location_tag_chain (свои теги, затем родителей) и пакетную таблицу audio/data/index.yaml.
# campaigns/test не трогаем (не в git).
from types import SimpleNamespace

import pytest
import yaml
from campaign_kit import ROOT

from ai_dm.audio.catalog import load_audio, theme_for_tags
from ai_dm.audio.select import SoundState, pick_theme
from ai_dm.state.world import Location
from ai_dm.ui.screen import location_tag_chain

PACKS = ["vale", "drunk_dragon"]


def world_of(pack):
    raw = yaml.safe_load((ROOT / "campaigns" / pack / "locations.yaml").read_text(encoding="utf-8"))
    places = [Location.model_validate(item) for item in raw]
    return SimpleNamespace(locations={p.id: p for p in places})


def theme_of(pack, location_id, **kw):
    world = world_of(pack)
    tags = location_tag_chain(world, world.locations[location_id])
    state = SoundState(location_id, tags, kw.get("in_combat", False), "", "")
    return pick_theme(load_audio().index, state)


def tag_theme_of(pack, location_id):
    world = world_of(pack)
    tags = location_tag_chain(world, world.locations[location_id])
    return theme_for_tags(load_audio().index, tags)


def all_locations():
    return [(pack, loc) for pack in PACKS for loc in world_of(pack).locations]


@pytest.mark.parametrize(("pack", "location_id"), all_locations())
def test_every_pack_location_gets_a_theme(pack, location_id):
    assert theme_of(pack, location_id) is not None


@pytest.mark.parametrize("location_id", ["vale", "lame_goose", "cellar"])
def test_vale_locations_are_tagged_by_data(location_id):
    assert tag_theme_of("vale", location_id) is not None


@pytest.mark.parametrize(("pack", "location_id", "theme"), [
    ("vale", "lame_goose", "tavern"),
    ("vale", "cellar", "dungeon"),
    ("vale", "vale", "nature"),
    ("drunk_dragon", "deep_shaft", "dungeon"),
    ("drunk_dragon", "tavern_drunken_dragon", "tavern"),
    ("drunk_dragon", "iron_ridge_foothills_villages", "town"),
    ("drunk_dragon", "wolf_teeth_pass", "nature"),
    ("drunk_dragon", "sanctuary_of_dawn", "town"),
    ("drunk_dragon", "city", "town"),
    ("drunk_dragon", "iron_ridge", "nature"),
    ("drunk_dragon", "heather_wastes", "nature"),
])
def test_location_theme(pack, location_id, theme):
    assert theme_of(pack, location_id) == theme


def test_deep_shaft_does_not_inherit_mountain_theme_from_parent():
    # родитель iron_ridge -- горы (nature); шахта должна дать подземелье
    assert theme_of("drunk_dragon", "deep_shaft") != theme_of("drunk_dragon", "iron_ridge")


def test_combat_overrides_pack_theme():
    assert theme_of("vale", "lame_goose", in_combat=True) == "combat"
