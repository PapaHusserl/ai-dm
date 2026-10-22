# Реестр услуг, партия П1 (docs/plan-u0.md, Р6): /shop показывает услуги.
#   Нет ни торговцев, ни NPC с услугами -- «Здесь никто не торгует». NPC только с услугами:
#   заголовок «<имя> — услуги» без кошелька, без ассортимента и «Продать:», затем блок
#   «  Услуги:» со строками «    <название> — <цена> / <единица>» (ночь, порция, час, раз);
#   торговец с услугами -- лавка, затем блок услуг. Цены учитывают отношение и торг
#   (в заголовке «; торг: ...»);
#   отказывающийся NPC -- «отказывается торговать»; последняя строка -- «Деньги: ...».
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.rules.inventory import add_item  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, TradeProfile  # noqa: E402

FAR = 10**9


def make_inn(registry, tmp_path, services=("room_modest", "meal_modest"), **fields):
    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    fields.setdefault("location_id", hero.location_id)
    app.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services), **fields
    )
    return app


def shop(app):
    return app.handle("/shop").lines


def row(lines, text):
    return [line for line in lines if text in line]


def test_nobody_trades_and_no_services_says_nobody_trades(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert shop(app) == ["Здесь никто не торгует"]


def test_provider_alone_replaces_the_nobody_message(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    assert "Здесь никто не торгует" not in shop(app)


def test_provider_in_other_location_is_not_shown(registry, tmp_path):
    app = make_inn(registry, tmp_path, location_id="far_away")
    assert shop(app) == ["Здесь никто не торгует"]


def test_dead_provider_is_not_shown(registry, tmp_path):
    app = make_inn(registry, tmp_path, status="dead")
    assert shop(app) == ["Здесь никто не торгует"]


def test_npc_with_empty_services_is_not_shown(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=[])
    assert shop(app) == ["Здесь никто не торгует"]


def test_provider_head_has_name_and_services_without_purse(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path))
    assert lines[0] == "Грок — услуги"
    assert not row(lines, "кошелёк")


def test_services_block_follows_head(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path))
    assert lines[1] == "  Услуги:"


def test_service_lines_have_price_and_unit(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path))
    assert "    комната (скромная) — 5 см / ночь" in lines
    assert "    еда (скромная) — 1 см / порция" in lines


def test_service_lines_follow_npc_order(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, services=["meal_modest", "room_modest"]))
    assert lines[2].startswith("    еда")
    assert lines[3].startswith("    комната")


def test_unit_words_for_hour_and_once(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, services=["bed_hour", "heal_barber"]))
    assert "    час в постели — 5 мм / час" in lines
    assert "    лечение цирюльника — 5 см / раз" in lines


def test_description_is_not_shown_in_shop(registry, tmp_path, cfg):
    lines = shop(make_inn(registry, tmp_path, services=["room_modest"]))
    assert not row(lines, cfg.services.kinds["room_modest"].description)


def test_unknown_service_id_is_skipped(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, services=["castle", "ale"]))
    assert not row(lines, "castle")
    assert "    эль (кружка) — 4 мм / порция" in lines


def test_only_unknown_services_show_no_block(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, services=["castle"]))
    assert not row(lines, "Услуги:")


def test_provider_has_no_sell_block(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert not row(shop(app), "Продать:")


def test_provider_has_no_assortment(registry, tmp_path):
    assert not row(shop(make_inn(registry, tmp_path)), "Колчан")


def test_hero_money_is_last_line(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    hero_of(app.bundle).money_cp = 700
    assert shop(app)[-1] == "Деньги: 7 зм"


def test_prices_follow_good_attitude(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, attitude=60))
    assert "    комната (скромная) — 4 см 5 мм / ночь" in lines


def test_flag_haggle_is_shown_in_head_and_prices(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.bundle.world.flags["haggle:grok"] = "0:-10"
    lines = shop(app)
    assert lines[0] == "Грок — услуги; торг: −10% до конца дня"
    assert "    комната (скромная) — 4 см 5 мм / ночь" in lines


def test_failed_haggle_is_shown_with_plus(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.bundle.world.flags["haggle:grok"] = "0:10"
    lines = shop(app)
    assert "торг: +10% до конца дня" in lines[0]
    assert "    комната (скромная) — 5 см 5 мм / ночь" in lines


def test_yesterdays_haggle_is_not_shown(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    app.bundle.world.flags["haggle:grok"] = "-1:-20"
    assert shop(app)[0] == "Грок — услуги"


def test_refusing_provider_is_marked_without_services(registry, tmp_path):
    lines = shop(make_inn(registry, tmp_path, attitude=-60))
    assert "Грок отказывается торговать" in lines
    assert not row(lines, "Услуги:")


# торговец с услугами и смешанные случаи

def add_merchant(app, **fields):
    app.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"],
        location_id=hero_of(app.bundle).location_id,
        trade=TradeProfile(kind="general", purse_cp=5000, restock_at_s=FAR),
        **fields,
    )


def test_merchant_with_services_has_shop_and_services_blocks(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=["ale"], trade=TradeProfile(
        kind="general", purse_cp=5000, restock_at_s=FAR))
    lines = shop(app)
    assert "кошелёк торговца: 50 зм" in lines[0]
    assert row(lines, "Колчан")
    assert lines.index("  Услуги:") > lines.index(row(lines, "Колчан")[0])
    assert "    эль (кружка) — 4 мм / порция" in lines


def test_merchant_with_services_is_listed_once(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=["ale"], trade=TradeProfile(
        kind="general", purse_cp=5000, restock_at_s=FAR))
    assert len(row(shop(app), "Грок")) == 1


def test_merchant_with_services_keeps_sell_block(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=["ale"], trade=TradeProfile(
        kind="general", purse_cp=5000, restock_at_s=FAR))
    hero_of(app.bundle).inventory.clear()
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert row(shop(app), "Продать:")


def test_merchant_haggle_shows_once_and_prices_services(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=["room_modest"], trade=TradeProfile(
        kind="general", purse_cp=5000, restock_at_s=FAR, haggle_percent=-10, haggle_day=0))
    lines = shop(app)
    assert "торг: −10% до конца дня" in lines[0]
    assert "    комната (скромная) — 4 см 5 мм / ночь" in lines


def test_merchant_with_services_shows_restocked_purse(registry, tmp_path):
    app = make_inn(registry, tmp_path, services=["ale"], trade=TradeProfile(
        kind="general", purse_cp=10, restock_at_s=0))
    assert "кошелёк торговца: 50 зм" in shop(app)[0]


def test_merchant_with_services_hides_stock_magic_above_rarity_cap(
    registry, tmp_path, monkeypatch
):
    stock = [InventoryEntry(item_id="potion_of_healing", qty=1, cost_cp=5000)]
    app = make_inn(registry, tmp_path, services=["ale"], trade=TradeProfile(
        kind="alchemist", purse_cp=5000, restock_at_s=FAR, stock=stock))
    monkeypatch.setattr(registry.get("item", "potion_of_healing"), "rarity", "legendary")
    assert not row(shop(app), "Зелье лечения")


def test_merchant_without_services_has_no_services_block(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    add_merchant(app)
    assert not row(shop(app), "Услуги:")


def test_merchant_comes_before_provider(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    add_merchant(app)
    lines = shop(app)
    assert lines.index(row(lines, "Мара")[0]) < lines.index("Грок — услуги")


def test_merchant_and_provider_are_both_listed_with_one_money_line(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    add_merchant(app)
    lines = shop(app)
    assert row(lines, "Мара (general)")
    assert "Грок — услуги" in lines
    assert len(row(lines, "Деньги:")) == 1


def test_command_does_not_move_time(registry, tmp_path):
    app = make_inn(registry, tmp_path)
    before = app.bundle.world.clock.now_s
    shop(app)
    assert app.bundle.world.clock.now_s == before
