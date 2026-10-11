# Торговля, партия Т0 (TRADE-PLAN, разд. 1): поле trade у NPC пака (npcs.yaml).
#   npcs.yaml: trade: {kind: general} -> Pack.npcs[i].trade.kind == "general"
#   kind обязан быть пресетом [trade.presets] конфига; неизвестный -> PackError (строка с файлом,
#   id NPC и значением kind). Без trade -- NPC не торговец.
import pytest
from campaign_kit import default_files, load, pack_errors, text_of, write_pack

from ai_dm.content.loader import load_registry


@pytest.fixture(scope="module")
def registry():
    return load_registry()


def pack_with(trade, tmp_path):
    files = default_files()
    files["npcs.yaml"][1]["trade"] = trade
    return write_pack(tmp_path, files)


def npc_of(pack, npc_id):
    return next(n for n in pack.npcs if n.id == npc_id)


def test_npc_without_trade_is_not_a_merchant(tmp_path, registry):
    pack = load(write_pack(tmp_path), registry)
    assert npc_of(pack, "guard").trade is None


def test_npc_with_trade_gets_profile(tmp_path, registry):
    pack = load(pack_with({"kind": "general"}, tmp_path), registry)
    assert npc_of(pack, "guard").trade.kind == "general"


def test_other_npc_stays_not_a_merchant(tmp_path, registry):
    pack = load(pack_with({"kind": "general"}, tmp_path), registry)
    assert npc_of(pack, "aldric").trade is None


def test_every_default_preset_is_accepted(tmp_path, registry):
    for kind in ("general", "smith", "armorer", "alchemist", "fence"):
        pack = load(pack_with({"kind": kind}, tmp_path / kind), registry)
        assert npc_of(pack, "guard").trade.kind == kind


def test_unknown_preset_is_pack_error(tmp_path, registry):
    errors = pack_errors(pack_with({"kind": "wizard_bazaar"}, tmp_path), registry)
    assert errors is not None
    assert "wizard_bazaar" in text_of(errors)


def test_unknown_preset_error_names_the_npc_file(tmp_path, registry):
    errors = pack_errors(pack_with({"kind": "wizard_bazaar"}, tmp_path), registry)
    assert "/npcs.yaml: npc 'guard'" in text_of(errors)


def test_trade_without_kind_is_pack_error(tmp_path, registry):
    assert pack_errors(pack_with({}, tmp_path), registry) is not None


def test_trade_with_unknown_field_is_pack_error(tmp_path, registry):
    assert pack_errors(pack_with({"kind": "general", "bogus": 1}, tmp_path), registry) is not None


def test_valid_pack_with_trade_has_no_errors(tmp_path, registry):
    assert pack_errors(pack_with({"kind": "smith"}, tmp_path), registry) is None


def test_mini_fixture_pack_marks_mara_as_general_merchant(registry):
    from pathlib import Path

    from ai_dm.campaign.loader import load_pack

    path = Path(__file__).resolve().parents[2] / "fixtures" / "packs" / "mini"
    pack = load_pack(path, registry)
    assert npc_of(pack, "mara").trade.kind == "general"


# pack_npc_trade: id NPC -> kind для миграции сейва

def test_pack_npc_trade_lists_only_merchants(tmp_path, registry):
    from ai_dm.campaign.loader import pack_npc_trade

    assert pack_npc_trade(pack_with({"kind": "smith"}, tmp_path), registry) == {"guard": "smith"}


def test_pack_npc_trade_of_pack_without_merchants_is_empty(tmp_path, registry):
    from ai_dm.campaign.loader import pack_npc_trade

    assert pack_npc_trade(write_pack(tmp_path), registry) == {}


def test_pack_npc_trade_without_pack_dir_is_empty(registry):
    from ai_dm.campaign.loader import pack_npc_trade

    assert pack_npc_trade(None, registry) == {}


def test_pack_npc_trade_of_missing_dir_is_none(tmp_path, registry):
    from ai_dm.campaign.loader import pack_npc_trade

    assert pack_npc_trade(tmp_path / "nowhere", registry) is None


def test_pack_npc_trade_of_broken_pack_is_none(tmp_path, registry):
    from ai_dm.campaign.loader import pack_npc_trade

    path = pack_with({"kind": "wizard_bazaar"}, tmp_path)
    assert pack_npc_trade(path, registry) is None


def test_pack_npc_trade_of_mini_fixture_is_mara(registry):
    from pathlib import Path

    from ai_dm.campaign.loader import pack_npc_trade

    path = Path(__file__).resolve().parents[2] / "fixtures" / "packs" / "mini"
    assert pack_npc_trade(path, registry) == {"mara": "general"}
