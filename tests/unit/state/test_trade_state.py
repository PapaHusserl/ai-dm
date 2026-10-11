# Торговля, партия Т0 (TRADE-PLAN, разд. 1, 3, 7): модели сейва.
#   ai_dm.state.world.TradeProfile(kind: str, purse_cp: int = 0, restock_at_s: int = 0,
#       stock: list[InventoryEntry] = []) -- extra=forbid
#   NPC.trade: TradeProfile | None = None
#   SceneState.trades = 0 (операций торговли за сцену), SceneState.merchants_created = 0
import pytest
from pydantic import ValidationError

from ai_dm.state.hero import InventoryEntry
from ai_dm.state.scene import SceneState
from ai_dm.state.world import NPC, TradeProfile


def npc(**extra):
    return NPC(id="mara", name="Мара", means=["товары"], **extra)


# TradeProfile

def test_profile_needs_a_kind():
    with pytest.raises(ValidationError):
        TradeProfile()


def test_profile_defaults():
    profile = TradeProfile(kind="general")
    assert (profile.kind, profile.purse_cp, profile.restock_at_s, profile.stock) == (
        "general", 0, 0, [],
    )


def test_profile_stock_is_not_shared_between_instances():
    first = TradeProfile(kind="general")
    first.stock.append(InventoryEntry(item_id="rope", qty=1, cost_cp=100))
    assert TradeProfile(kind="general").stock == []


def test_profile_keeps_stock_entries_with_price_and_quality():
    entry = InventoryEntry(item_id="scimitar", qty=2, cost_cp=100, quality="worn")
    profile = TradeProfile(kind="smith", purse_cp=10000, restock_at_s=604800, stock=[entry])
    assert profile.stock[0].cost_cp == 100
    assert profile.stock[0].quality == "worn"
    assert profile.purse_cp == 10000


def test_profile_extra_field_is_error():
    with pytest.raises(ValidationError):
        TradeProfile(kind="general", bogus=1)


def test_profile_negative_purse_is_error():
    with pytest.raises(ValidationError):
        TradeProfile(kind="general", purse_cp=-1)


def test_profile_zero_purse_is_fine():
    assert TradeProfile(kind="general", purse_cp=0).purse_cp == 0


def test_profile_haggle_defaults_mean_no_haggle_yet():
    profile = TradeProfile(kind="general")
    assert (profile.haggle_percent, profile.haggle_day) == (0, None)


def test_profile_keeps_haggle_state():
    profile = TradeProfile(kind="general", haggle_percent=-20, haggle_day=3)
    assert (profile.haggle_percent, profile.haggle_day) == (-20, 3)


def test_profile_haggle_day_zero_is_not_none():
    assert TradeProfile(kind="general", haggle_day=0).haggle_day == 0


def test_profile_round_trips_through_json():
    profile = TradeProfile(
        kind="general", purse_cp=5000, restock_at_s=10,
        stock=[InventoryEntry(item_id="rope", qty=3, cost_cp=100)],
    )
    assert TradeProfile.model_validate_json(profile.model_dump_json()) == profile


# NPC.trade

def test_npc_has_no_trade_by_default():
    assert npc().trade is None


def test_npc_accepts_trade_profile():
    assert npc(trade=TradeProfile(kind="general")).trade.kind == "general"


def test_npc_accepts_trade_as_dict():
    assert NPC.model_validate({
        "id": "mara", "name": "Мара", "means": ["товары"], "trade": {"kind": "smith"},
    }).trade.kind == "smith"


def test_npc_trade_round_trips_through_json():
    original = npc(trade=TradeProfile(kind="fence", purse_cp=3000))
    assert NPC.model_validate_json(original.model_dump_json()) == original


# SceneState

def test_scene_trade_counters_start_at_zero():
    scene = SceneState(id="s1", started_at_s=0)
    assert (scene.trades, scene.merchants_created) == (0, 0)


def test_scene_trade_counters_are_independent():
    scene = SceneState(id="s1", started_at_s=0, trades=2)
    assert (scene.trades, scene.merchants_created) == (2, 0)


def test_scene_counters_round_trip():
    scene = SceneState(id="s1", started_at_s=0, trades=4, merchants_created=1)
    assert SceneState.model_validate_json(scene.model_dump_json()) == scene
