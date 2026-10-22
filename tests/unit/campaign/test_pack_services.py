# Реестр услуг, партия П1 (docs/plan-u0.md): поле services у NPC пака (npcs.yaml).
#   services: [id услуг из [services.kinds] конфига] -> Pack.npcs[i].services; без поля -- [].
#   Неизвестный id -> PackError (строка с файлом, id NPC и значением). Пак campaigns/inn_test
#   (тестовый мир услуг) загружается и раздаёт только известные услуги.
import pytest
from campaign_kit import ROOT, default_files, load, pack_errors, text_of, write_pack

from ai_dm.config.settings import load_rules_config
from ai_dm.content.loader import load_registry


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def pack_with(services, tmp_path):
    files = default_files()
    files["npcs.yaml"][1]["services"] = services
    return write_pack(tmp_path, files)


def npc_of(pack, npc_id):
    return next(n for n in pack.npcs if n.id == npc_id)


def test_npc_without_services_has_empty_list(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert npc_of(pack, "guard").services == []


def test_npc_with_services_keeps_them_in_order(tmp_path, registry):
    pack = load(pack_with(["meal_modest", "room_modest"], tmp_path), registry)
    assert npc_of(pack, "guard").services == ["meal_modest", "room_modest"]


def test_other_npc_stays_without_services(tmp_path, registry):
    pack = load(pack_with(["ale"], tmp_path), registry)
    assert npc_of(pack, "aldric").services == []


def test_every_default_kind_is_accepted(tmp_path, registry):
    kinds = list(load_rules_config().services.kinds)
    pack = load(pack_with(kinds, tmp_path), registry)
    assert npc_of(pack, "guard").services == kinds


def test_unknown_service_is_pack_error(tmp_path, registry):
    errors = pack_errors(pack_with(["castle"], tmp_path), registry)
    assert errors is not None
    assert "castle" in text_of(errors)


def test_unknown_service_error_names_file_npc_and_field(tmp_path, registry):
    errors = pack_errors(pack_with(["castle"], tmp_path), registry)
    text = text_of(errors)
    assert "/npcs.yaml: npc 'guard'" in text
    assert "services" in text


def test_one_unknown_among_known_is_still_error(tmp_path, registry):
    errors = pack_errors(pack_with(["ale", "castle"], tmp_path), registry)
    assert errors is not None
    assert "castle" in text_of(errors)
    assert "'ale'" not in text_of(errors)


def test_each_unknown_service_gets_its_own_line(tmp_path, registry):
    errors = pack_errors(pack_with(["castle", "tower"], tmp_path), registry)
    text = text_of(errors)
    assert "castle" in text
    assert "tower" in text


# тестовый мир услуг

def test_inn_test_pack_loads(registry):
    assert pack_errors(ROOT / "campaigns" / "inn_test", registry) is None


def test_inn_test_has_innkeeper_temple_and_barber(registry):
    pack = load(ROOT / "campaigns" / "inn_test", registry)
    by_id = {n.id: n for n in pack.npcs}
    assert "room_modest" in by_id["innkeeper_brum"].services
    assert "ale" in by_id["innkeeper_brum"].services
    assert by_id["sister_ilda"].services == ["heal_temple"]
    assert by_id["barber_tobb"].services == ["heal_barber"]


def test_inn_test_providers_stand_in_known_locations(registry):
    pack = load(ROOT / "campaigns" / "inn_test", registry)
    locations = {loc.id for loc in pack.locations}
    providers = [n for n in pack.npcs if n.services]
    assert providers
    assert all(n.location_id in locations for n in providers)
