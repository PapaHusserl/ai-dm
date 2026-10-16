# Торговля, партия Т5: сейв не менялся. Состояние торга (haggle_percent, haggle_day) лежит
# в TradeProfile с Т0; сохранение и загрузка идут без миграции.
from persist_kit import load_slot

from ai_dm.persistence.migrations import CURRENT_SCHEMA_VERSION
from ai_dm.persistence.store import save_slot
from ai_dm.state.world import NPC, TradeProfile

SAVED_AT = "2026-01-01T12:00:00Z"


def test_schema_version_is_ten():
    assert CURRENT_SCHEMA_VERSION == 10


def test_haggle_state_survives_a_save_load_cycle(saves, bundle):
    bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"],
        trade=TradeProfile(kind="general", purse_cp=5000, haggle_percent=-10, haggle_day=4),
    )
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    profile = loaded.world.npcs["mara"].trade
    assert (profile.haggle_percent, profile.haggle_day) == (-10, 4)
    assert loaded.manifest.schema_version == CURRENT_SCHEMA_VERSION


def test_haggle_day_zero_survives_a_save_load_cycle(saves, bundle):
    bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"],
        trade=TradeProfile(kind="general", haggle_percent=10, haggle_day=0),
    )
    save_slot(saves, bundle, "auto", saved_at=SAVED_AT)
    loaded = load_slot(saves, "w1", "auto")
    assert loaded.world.npcs["mara"].trade.haggle_day == 0
