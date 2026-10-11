# /sheet показывает экипировку и раскладку КД (docs/decisions/stage3-live-arrows.md, A1, A5).
# Грей из реального пака campaigns/drunk_dragon: Мифриловая кольчужная рубаха 13, Лов 17 (+3),
# предел среднего доспеха 2 -> КД 15. Ожидаемый формат строки:
#   «КД 15 = Мифриловая кольчужная рубаха 13 + Лов 2 (предел средн. доспеха 2)»
# эффекты -- слагаемыми: «Каменная Кожа +2 (до HH:MM)» (ActiveEffect id="stoneskin_elixir",
# kind="ac", params {"label", "amount"}, Expiry(kind="seconds", value=<момент окончания>))
import re
from pathlib import Path

import pytest
from game_kit import ReactiveAdapter, make_app

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.state.creature import ActiveEffect, Expiry

PARAMS = {"label": "Каменная Кожа", "amount": 2}
DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"


@pytest.fixture
def dragon_app(cfg, tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    return make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)


def sheet(app):
    return "\n".join(app.handle("/sheet").lines)


def test_sheet_shows_ac_breakdown(dragon_app):
    text = sheet(dragon_app)
    assert "КД 15 = Мифриловая кольчужная рубаха 13 + Лов 2 (предел средн. доспеха 2)" in text


def test_sheet_ac_matches_engine_formula(dragon_app):
    from ai_dm.rules.derived import armor_class

    hero = dragon_app.bundle.heroes[0]
    assert armor_class(hero, dragon_app.registry) == 15


def test_sheet_shows_worn_armor_and_weapon_in_hand(dragon_app):
    text = sheet(dragon_app)
    assert "Мифриловая кольчужная рубаха" in text
    assert "Клинок Северного Ветра" in text


def test_sheet_without_armor_uses_plain_dex(dragon_app):
    hero = dragon_app.bundle.heroes[0]
    hero.equipped.armor = None
    text = sheet(dragon_app)
    assert "КД 13 = Без доспеха 10 + Лов 3" in text


def test_sheet_ac_effect_is_a_separate_term(dragon_app):
    hero = dragon_app.bundle.heroes[0]
    end = dragon_app.bundle.world.clock.now_s + 3600
    hero.creature.active_effects.append(
        ActiveEffect(
            id="stoneskin_elixir", source="hero", kind="ac", params=PARAMS,
            expires=Expiry(kind="seconds", value=end),
        )
    )
    text = sheet(dragon_app)
    assert "КД 17 = " in text
    assert re.search(r"Каменная Кожа \+?2 \(до \d\d:\d\d\)", text)
