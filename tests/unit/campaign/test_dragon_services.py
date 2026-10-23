# Услуги в паке campaigns/drunk_dragon (У1 П4, docs/plan-u1.md, решения 54–57): пак версии 2
# раздаёт услуги Гроку и Отцу Марку, новые NPC -- баня Города «Хамам от Маман», цирюльник и гадалка
# в Сером Квартале, компаньоны и бард в «Пьяном Драконе», «Мшистый Валун» в Чернолесье.
# Догрузка в живой мир (merge_new) дозаполняет пустые services и добавляет новых NPC/локацию.
import pytest
from campaign_kit import ROOT, SAVED_AT, pack_errors

from ai_dm.config.settings import load_rules_config

DRAGON_DIR = ROOT / "campaigns" / "drunk_dragon"
NEW_NPCS = ["bath_keeper_city", "barber_city", "companion_rosa", "companion_damian",
            "bard_yanek", "fortune_teller_vedana", "innkeeper_mossy_boulder"]
ROOMS = {"room_poor", "room_modest", "room_comfortable"}


def dragon_registry():
    from ai_dm.campaign.loader import pack_content_dir
    from ai_dm.content.loader import load_registry

    content = pack_content_dir(DRAGON_DIR)
    return load_registry([content] if content is not None else [])


@pytest.fixture(scope="module")
def pack():
    from ai_dm.campaign.loader import load_pack

    return load_pack(DRAGON_DIR, dragon_registry())


def by_id(pack):
    return {n.id: n for n in pack.npcs}


def children_of(pack, parent):
    return {loc.id for loc in pack.locations if loc.parent_id == parent}


def providers(pack, kind):
    return [n for n in pack.npcs if kind in n.services]


def test_pack_loads_without_errors():
    assert pack_errors(DRAGON_DIR, dragon_registry()) is None


def test_pack_version_is_two(pack):
    assert pack.manifest.version == "2"


def test_every_service_id_is_known(pack):
    kinds = set(load_rules_config().services.kinds)
    assert {s for n in pack.npcs for s in n.services} <= kinds


def test_grok_has_exactly_eight_services(pack):
    assert len(by_id(pack)["grok_innkeeper"].services) == 8


def test_grok_rents_comfortable_room(pack):
    assert "room_comfortable" in by_id(pack)["grok_innkeeper"].services


def test_father_mark_heals_and_uncurses(pack):
    assert by_id(pack)["father_mark"].services == ["heal_temple", "uncurse_temple"]


def test_city_has_a_bathhouse_child_with_bath_keeper(pack):
    places = {n.location_id for n in providers(pack, "bath")}
    assert places & children_of(pack, "city")


def test_bathhouse_is_linked_to_the_tavern(pack):
    bath = next(loc for loc in pack.locations if loc.id == "bathhouse_city")
    assert "tavern_drunken_dragon" in [c.to for c in bath.connections]


def test_chernolesye_has_bath(pack):
    assert "chernolesye" in {n.location_id for n in providers(pack, "bath")}


def test_chernolesye_has_lodging(pack):
    locs = {n.location_id for n in pack.npcs if ROOMS & set(n.services)}
    assert "chernolesye" in locs


def test_tavern_companions_are_of_different_gender(pack):
    companions = [n for n in pack.npcs if any(s.startswith("companion_") for s in n.services)]
    assert {s for n in companions for s in n.services} == {"companion_cheap", "companion_common"}
    assert {n.gender for n in companions} == {"female", "male"}
    assert {n.location_id for n in companions} == {"tavern_drunken_dragon"}


def test_tavern_has_a_bard(pack):
    assert [n.location_id for n in providers(pack, "bard_song")] == ["tavern_drunken_dragon"]


def test_fortune_is_told_in_grey_quarter(pack):
    assert "grey_quarter" in {n.location_id for n in providers(pack, "fortune")}


def test_grey_quarter_barber_cuts_and_shaves(pack):
    barbers = [n for n in pack.npcs if {"haircut", "shave"} <= set(n.services)]
    assert "grey_quarter" in {n.location_id for n in barbers}


def test_nobody_offers_fine_companion(pack):
    assert providers(pack, "companion_fine") == []


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


# догрузка в мир, собранный паком версии 1 (услуг и новых NPC нет)

def old_world(cfg, pack):
    from ai_dm.game.starter import new_world_from_pack

    bundle = new_world_from_pack(
        dragon_registry(), cfg, pack, hero="grey", seed=1, world_id="dd", saved_at=SAVED_AT,
    )
    for npc_id in NEW_NPCS:
        del bundle.world.npcs[npc_id]
    del bundle.world.locations["bathhouse_city"]
    for npc in bundle.world.npcs.values():
        npc.services = []
    bundle.world.campaign_version = "1"
    return bundle


def test_merge_gives_services_to_grok_and_mark_in_old_world(cfg, pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(cfg, pack)
    report = merge_new(bundle, pack)
    assert "services:grok_innkeeper" in report.added
    assert "services:father_mark" in report.added
    assert len(bundle.world.npcs["grok_innkeeper"].services) == 8


def test_merge_adds_new_npcs_and_bathhouse_without_conflicts(cfg, pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(cfg, pack)
    report = merge_new(bundle, pack)
    assert report.conflicts == []
    assert set(NEW_NPCS) <= set(bundle.world.npcs)
    assert "bathhouse_city" in bundle.world.locations
    assert bundle.world.campaign_version == "2"


def test_second_merge_into_old_world_is_empty(cfg, pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(cfg, pack)
    merge_new(bundle, pack)
    assert merge_new(bundle, pack).added == []


def test_merge_keeps_services_given_by_master(cfg, pack):
    from ai_dm.campaign.merge import merge_new

    bundle = old_world(cfg, pack)
    bundle.world.npcs["grok_innkeeper"].services = ["ale"]
    report = merge_new(bundle, pack)
    assert bundle.world.npcs["grok_innkeeper"].services == ["ale"]
    assert "services:grok_innkeeper" not in report.added
