# Услуги в паке campaigns/dusk_academy (У1 П4, docs/plan-u1.md, решения 54–57): пак версии 3 --
# Матушка Рут кормит в чайной, купальня «Горячие источники» в Туманной Гавани, цирюльник на площади,
# гадалка на пирсе; компании (companion_*) нет (Р4в). Миграция живого сейва (v9 -> v12) автотестом
# не покрывается -- сейвы не в тестах; здесь догрузка в мир, собранный из пака без новинок.
import pytest
from campaign_kit import ROOT, pack_errors

from ai_dm.config.settings import load_rules_config

DUSK_DIR = ROOT / "campaigns" / "dusk_academy"
NEW_NPCS = ["bath_keeper_haven", "barber_haven", "fortune_teller_haven"]


def dusk_registry():
    from ai_dm.campaign.loader import pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DUSK_DIR)
    return load_registry([content] if content is not None else [])


@pytest.fixture(scope="module")
def pack():
    from ai_dm.campaign.loader import load_pack

    return load_pack(DUSK_DIR, dusk_registry())


def by_id(pack):
    return {n.id: n for n in pack.npcs}


def haven_places(pack):
    return {"misty_haven"} | {loc.id for loc in pack.locations if loc.parent_id == "misty_haven"}


def providers(pack, kind):
    return [n for n in pack.npcs if kind in n.services]


def test_pack_loads_without_errors():
    assert pack_errors(DUSK_DIR, dusk_registry()) is None


def test_pack_version_is_four(pack):
    assert pack.manifest.version == "4"


def test_every_service_id_is_known(pack):
    kinds = set(load_rules_config().services.kinds)
    assert {s for n in pack.npcs for s in n.services} <= kinds


def test_ruth_serves_meals(pack):
    assert by_id(pack)["old_ruth"].services == ["meal_poor", "meal_modest"]


def test_haven_has_bath(pack):
    assert {n.location_id for n in providers(pack, "bath")} & haven_places(pack)


def test_bathhouse_is_child_of_haven_and_linked_to_it(pack):
    bath = next(loc for loc in pack.locations if loc.id == "hot_springs_haven")
    assert bath.parent_id == "misty_haven"
    assert "misty_haven" in [c.to for c in bath.connections]


def test_haven_has_barber_with_haircut_and_shave(pack):
    barbers = [n for n in pack.npcs if {"haircut", "shave"} <= set(n.services)]
    assert {n.location_id for n in barbers} & haven_places(pack)


def test_someone_tells_fortunes(pack):
    assert providers(pack, "fortune") != []


def test_nobody_offers_companion(pack):
    assert [n for n in pack.npcs if any(s.startswith("companion_") for s in n.services)] == []


@pytest.mark.parametrize("npc_id", NEW_NPCS)
def test_new_npc_is_not_in_party_and_not_key(pack, npc_id):
    npc = by_id(pack)[npc_id]
    assert npc.follows is None
    assert npc.key is False


@pytest.mark.parametrize("npc_id", NEW_NPCS)
def test_new_npc_has_motive(pack, npc_id):
    assert by_id(pack)[npc_id].motive.strip()


@pytest.mark.parametrize("npc_id", NEW_NPCS)
def test_new_npc_name_is_unique_in_pack(pack, npc_id):
    name = by_id(pack)[npc_id].name.lower()
    assert [n.id for n in pack.npcs if n.name.lower() == name] == [npc_id]


def test_providers_stand_in_known_locations(pack):
    locations = {loc.id for loc in pack.locations}
    assert all(n.location_id in locations for n in pack.npcs if n.services)


# догрузка в мир пака версии 2 (до П4: без услуг, купальни и новых NPC)

def old_world(pack):
    from campaign_kit import bundle_from_world, world_from_pack

    bundle = bundle_from_world(world_from_pack(pack, "dusk"))
    for npc_id in NEW_NPCS:
        del bundle.world.npcs[npc_id]
    del bundle.world.locations["hot_springs_haven"]
    for npc in bundle.world.npcs.values():
        npc.services = []
    bundle.world.campaign_version = "2"
    return bundle


def test_merge_gives_ruth_meals_and_adds_new_npcs(pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(pack)
    report = merge_new(bundle, pack)
    assert "services:old_ruth" in report.added
    assert bundle.world.npcs["old_ruth"].services == ["meal_poor", "meal_modest"]
    assert set(NEW_NPCS) <= set(bundle.world.npcs)
    assert "hot_springs_haven" in bundle.world.locations
    assert report.conflicts == []
    assert bundle.world.campaign_version == "4"


def test_second_merge_into_old_world_is_empty(pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(pack)
    merge_new(bundle, pack)
    assert merge_new(bundle, pack).added == []
