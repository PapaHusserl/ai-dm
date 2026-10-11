# Эффекты видны (stage3-live-effects-visible, E1, E2, T). Грей и эликсир «Каменная Кожа» из
# campaigns/drunk_dragon. Ожидание: заголовок хода и строка состояния --
# «КД 17 (Каменная Кожа до ЧЧ:ММ)»,
# строка «Действует: Каменная Кожа (+2 КД, сопр. рубящему/дробящему) до ЧЧ:ММ»;
# повторный эликсир в меню -- «Выпить: Каменная Кожа (уже действует до ЧЧ:ММ)».
from pathlib import Path

import pytest

from ui_kit import ReactiveAdapter, make_app, play  # isort: skip
from protocol_kit import combat_request, make_ctx, req  # isort: skip

from ai_dm.campaign.loader import load_pack, pack_content_dir
from ai_dm.content.loader import load_registry
from ai_dm.game.starter import new_world_from_pack
from ai_dm.protocol.apply import apply
from ai_dm.ui.simple import status_line

DRAGON = Path(__file__).resolve().parents[3] / "campaigns" / "drunk_dragon"
DAY = 86400


@pytest.fixture
def world(cfg, tmp_path):
    registry = load_registry([pack_content_dir(DRAGON)])
    bundle = new_world_from_pack(
        registry, cfg, load_pack(DRAGON, registry), hero="grey", seed=1, world_id="w1",
        saved_at="2026-01-01T00:00:00",
    )
    app = make_app(registry, tmp_path, ReactiveAdapter(), bundle=bundle)
    return registry, cfg, bundle, app


def drink(world):
    registry, cfg, bundle, app = world
    ctx = make_ctx(registry, cfg, bundle=bundle)
    apply(ctx, req("use_item", item_id="stoneskin_elixir", qty=1))


def start_fight(world):
    registry, cfg, bundle, app = world
    apply(make_ctx(registry, cfg, bundle=bundle), combat_request())


def until(bundle):
    # ЧЧ:ММ окончания эффекта: час от «сейчас»
    minutes = (bundle.world.clock.now_s + 3600) % DAY // 60
    return f"{minutes // 60:02d}:{minutes % 60:02d}"


def test_turn_header_shows_ac_with_effect(world):
    drink(world)
    start_fight(world)
    text = play(world[3], []).text
    assert f"КД 17 (Каменная Кожа до {until(world[2])})" in text


def test_turn_header_shows_active_effects_line(world):
    drink(world)
    start_fight(world)
    text = play(world[3], []).text
    expected = f"Действует: Каменная Кожа (+2 КД, сопр. рубящему/дробящему) до {until(world[2])}"
    assert expected in text


def test_turn_header_without_effect_has_no_effects_line(world):
    start_fight(world)
    text = play(world[3], []).text
    assert "Действует:" not in text
    assert "Каменная Кожа до" not in text


def test_status_line_shows_ac_with_effect(world):
    drink(world)
    assert f"КД 17 (Каменная Кожа до {until(world[2])})" in status_line(world[3])


def test_status_line_without_effect_has_no_effect_note(world):
    assert "Каменная Кожа до" not in status_line(world[3])


def test_menu_offers_elixir_again_with_already_active_note(world):
    drink(world)
    start_fight(world)
    text = play(world[3], []).text
    assert f"Выпить: Каменная Кожа (уже действует до {until(world[2])})" in text


def test_menu_elixir_without_effect_has_no_active_note(world):
    start_fight(world)
    text = play(world[3], []).text
    assert "Выпить: Каменная Кожа" in text
    assert "уже действует" not in text
