# Строка о сопротивлении при damage вне боя (stage3-live-resist-line, R1/T).
# Эликсир «Каменная Кожа» Грея (campaigns/drunk_dragon): дробящее вдвое меньше.
# Строка «Сопротивление (Каменная Кожа): 7 → 3 дробящий» идёт в log решения после строки урона.
from pathlib import Path

import pytest
from protocol_kit import ScriptedRng, make_ctx, req

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def dragon(cfg):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return registry, bundle


def hazard(registry, cfg, bundle, drink):
    ctx = make_ctx(registry, cfg, ScriptedRng(d10=[7]), bundle=bundle)
    if drink:
        apply(ctx, req("use_item", item_id="stoneskin_elixir", qty=1))
    return apply(ctx, req("damage", severity="nuisance", damage_type="bludgeoning"))


def test_damage_outside_combat_shows_resist_line(dragon, cfg):
    registry, bundle = dragon
    d = hazard(registry, cfg, bundle, drink=True)
    assert "Сопротивление (Каменная Кожа): 7 → 3 дробящий" in d.log[-1]


def test_damage_outside_combat_resist_line_follows_damage_line(dragon, cfg):
    registry, bundle = dragon
    d = hazard(registry, cfg, bundle, drink=True)
    assert "Урон (опасность)" in d.log[-2]


def test_damage_outside_combat_without_resist_has_no_line(dragon, cfg):
    registry, bundle = dragon
    d = hazard(registry, cfg, bundle, drink=False)
    assert not any("Сопротивление" in line for line in d.log)
