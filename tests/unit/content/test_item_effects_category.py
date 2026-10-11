# Правило контента (TRADE-PLAN, «Т1: заметки для Т2»): предмет с effects обязан иметь category --
# иначе /inv (группа «эффекты») и торговля (gear по умолчанию) расходятся. Боеприпасы (ammo_for)
# исключены: и /inv, и торговля относят их к боеприпасам.
# Проверяются SRD и предметы встроенных кампаний (campaigns/*/content).
from pathlib import Path

import pytest

from ai_dm.content.loader import load_registry

CAMPAIGNS = Path(__file__).resolve().parents[3] / "campaigns"
LAYERS = [None] + sorted(p.parent.name for p in CAMPAIGNS.glob("*/content"))


def items_of(layer):
    if layer is None:
        return load_registry().all("item")
    return load_registry([CAMPAIGNS / layer / "content"]).all("item")


@pytest.mark.parametrize("layer", LAYERS)
def test_items_with_effects_have_a_category(layer):
    bad = [
        item.id for item in items_of(layer)
        if item.effects and not item.ammo_for and item.category == ""
    ]
    assert bad == []


def test_the_check_sees_the_campaign_layers():
    assert "drunk_dragon" in LAYERS
