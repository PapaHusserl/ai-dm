# Торговля, партия Т4 (docs/plan-trade.md, разд. 5): команда /shop.
#   Без торговца в локации героя -- «Здесь никто не торгует». С торговцем: заголовок с именем,
#   ассортимент пресета с ценами покупки (buy_factor 1.0: колчан 1 зм), купленное у героя (stock)
#   с ценой экземпляра, кошелёк торговца, деньги героя и строки «Продать: ... — цена продажи»
#   (sell_factor 0.5). Команда вне хода: время и журнал модели не двигаются.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.rules.inventory import add_item  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, TradeProfile  # noqa: E402

FAR = 10**9


def make_shop(registry, tmp_path, kind="general", purse=5000, stock=None, attitude=0, **fields):
    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    fields.setdefault("location_id", hero.location_id)
    app.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], attitude=attitude,
        trade=TradeProfile(kind=kind, purse_cp=purse, restock_at_s=FAR, stock=stock or []),
        **fields,
    )
    return app


def shop(app):
    return app.handle("/shop").lines


def row(lines, text):
    return [line for line in lines if text in line]


def test_no_merchant_says_nobody_trades(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    assert shop(app) == ["Здесь никто не торгует"]


def test_merchant_in_other_location_is_not_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path, location_id="far_away")
    assert shop(app) == ["Здесь никто не торгует"]


def test_dead_merchant_is_not_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path, status="dead")
    assert shop(app) == ["Здесь никто не торгует"]


def test_npc_without_trade_is_not_a_merchant(registry, tmp_path):
    app = text_app(registry, tmp_path, [text_step()])
    app.bundle.world.npcs["bob"] = NPC(
        id="bob", name="Боб", means=["пиво"], location_id=hero_of(app.bundle).location_id
    )
    assert shop(app) == ["Здесь никто не торгует"]


def test_merchant_name_is_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    assert "Мара" in shop(app)[0]


def test_assortment_has_prices(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    assert row(shop(app), "Колчан")[0].endswith("— 1 зм")


def test_assortment_follows_the_preset(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    lines = shop(app)
    assert row(lines, "Щит")
    assert not row(lines, "Колчан")


def test_assortment_price_uses_good_attitude_factor(registry, tmp_path):
    app = make_shop(registry, tmp_path, attitude=60)
    # колчан 100 мм * 0.9 = 90 мм = 9 см
    assert row(shop(app), "Колчан")[0].endswith("— 9 см")


def test_stock_is_shown_with_its_price(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=2, cost_cp=300, quality="worn")]
    app = make_shop(registry, tmp_path, kind="smith", stock=stock)
    line = [x for x in shop(app) if "оношенн" in x][0]
    assert "x2" in line
    assert line.endswith("— 3 зм")


def test_stock_comes_before_the_preset_in_its_group(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=300, quality="worn")]
    app = make_shop(registry, tmp_path, kind="smith", stock=stock)
    lines = shop(app)
    stock_at = next(i for i, x in enumerate(lines) if "оношенн" in x)
    other_weapon = next(
        i for i, x in enumerate(lines) if "Кинжал" in x or "Дубинка" in x or "Топор" in x
    )
    assert stock_at < other_weapon


def test_list_is_capped_at_40_rows(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=100 + n) for n in range(50)]
    app = make_shop(registry, tmp_path, stock=stock)
    lines = shop(app)
    priced = [x for x in lines if x.startswith("    ") and "—" in x]
    assert len(priced) == 40
    assert any(x.startswith("    …и ещё ") for x in lines)


def test_list_under_the_cap_has_no_more_line(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    assert not any("…и ещё" in x for x in shop(app))


def test_purse_is_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path, purse=5000)
    assert "кошелёк торговца: 50 зм" in shop(app)[0]


def test_expired_purse_is_shown_restocked_and_not_changed(registry, tmp_path):
    app = make_shop(registry, tmp_path, purse=10)
    app.bundle.world.npcs["mara"].trade.restock_at_s = 0
    assert "кошелёк торговца: 50 зм" in shop(app)[0]
    assert app.bundle.world.npcs["mara"].trade.purse_cp == 10


def test_hero_money_is_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero_of(app.bundle).money_cp = 700
    assert shop(app)[-1] == "Деньги: 7 зм"


def test_sell_block_has_sell_prices(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero_of(app.bundle).inventory.clear()
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    sell = row(shop(app), "Продать:")
    assert any("Колчан" in x and x.endswith("— 5 см") for x in sell)


def test_sell_price_is_per_stack_price_not_full(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    add_item(hero_of(app.bundle), "scimitar", cost_cp=200, quality="worn")
    sell = row(shop(app), "Продать:")
    assert any("оношенн" in x and x.endswith("— 1 зм") for x in sell)


def test_sell_block_skips_what_merchant_does_not_buy(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    hero_of(app.bundle).inventory.clear()
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert not any("Колчан" in x for x in row(shop(app), "Продать:"))


def test_sell_block_skips_worthless(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero_of(app.bundle).inventory.clear()
    add_item(hero_of(app.bundle), "quiver", cost_cp=1)
    assert not any("Колчан" in x for x in row(shop(app), "Продать:"))


def test_sell_block_skips_the_only_worn_item(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    hero = hero_of(app.bundle)
    armor = hero.equipped.armor
    for entry in list(hero.inventory):
        if entry.item_id == armor:
            hero.inventory.remove(entry)
    add_item(hero, armor, cost_cp=1000)
    assert armor is not None
    name = app.registry.get("armor", armor).name
    assert not any(name in x for x in row(shop(app), "Продать:"))


def test_no_sell_block_without_sellable_items(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    assert not row(shop(app), "Продать:")


def test_refusing_merchant_is_marked(registry, tmp_path):
    app = make_shop(registry, tmp_path, attitude=-60)
    lines = shop(app)
    assert "отказывается торговать" in lines[0]
    assert not row(lines, "Колчан")


def test_two_merchants_are_both_listed(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    app.bundle.world.npcs["gor"] = NPC(
        id="gor", name="Гор", means=["сталь"], location_id=hero_of(app.bundle).location_id,
        trade=TradeProfile(kind="smith", purse_cp=100, restock_at_s=FAR),
    )
    lines = shop(app)
    assert row(lines, "Мара") and row(lines, "Гор")


def test_shop_does_not_spend_time_or_a_turn(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    now = app.bundle.world.clock.now_s
    reply = app.handle("/shop")
    assert reply.turn is None
    assert app.bundle.world.clock.now_s == now
    assert app.adapter.requests == []


def test_shop_does_not_change_the_state(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    before = app.bundle.world.model_dump()
    app.handle("/shop")
    assert app.bundle.world.model_dump() == before


# порядок и разметка строк ассортимента

def names_in(lines):
    return [x.strip().split(" — ")[0] for x in lines if x.startswith("    ") and " — " in x]


def test_group_headers_are_shown(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    lines = shop(app)
    assert "  Снаряжение и инструменты:" in lines
    assert "  Доспехи и одежда:" in lines


def test_stock_potion_goes_to_its_group(registry, tmp_path):
    stock = [InventoryEntry(item_id="potion_of_healing", qty=1, cost_cp=5000)]
    app = make_shop(registry, tmp_path, kind="alchemist", stock=stock)
    lines = shop(app)
    at = lines.index("  Зелья и расходники:")
    assert lines[at + 1].startswith("    Зелье лечения")


def test_group_then_stock_then_catalog_then_name(registry, tmp_path):
    stock = [
        InventoryEntry(item_id="quiver", qty=1, cost_cp=100),
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=100),
        InventoryEntry(item_id="dagger", qty=1, cost_cp=5000),
    ]
    app = make_shop(registry, tmp_path, kind="armorer", stock=stock)
    names = names_in(shop(app))
    assert names[:2] == ["Кинжал", "Скимитар"]
    assert names[-1] == "Колчан"
    assert "Щит" in names[2:-1]


def test_stock_goes_before_catalog_inside_a_group(registry, tmp_path):
    stock = [InventoryEntry(item_id="quiver", qty=1, cost_cp=100)]
    app = make_shop(registry, tmp_path, stock=stock)
    lines = shop(app)
    at = lines.index("  Снаряжение и инструменты:")
    # Колчан из stock первым, хотя по алфавиту он после «Воровских инструментов»
    assert lines[at + 1].startswith("    Колчан")
    assert lines[at + 2].startswith("    Воровские инструменты")


def test_each_group_header_appears_once_with_stock_in_two_groups(registry, tmp_path):
    stock = [
        InventoryEntry(item_id="quiver", qty=1, cost_cp=100),
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=100),
    ]
    app = make_shop(registry, tmp_path, kind="fence", stock=stock)
    lines = shop(app)
    headers = [x for x in lines if x.startswith("  ") and x[2] != " " and x.endswith(":")]
    assert len(headers) == len(set(headers))
    assert headers.count("  Оружие:") == 1
    assert headers.count("  Снаряжение и инструменты:") == 1


def test_story_item_held_by_merchant_is_listed_in_story_group(registry, tmp_path):
    from ai_dm.state.world import CustomItem, ItemHolder

    app = make_shop(registry, tmp_path)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, qty=2, cost_cp=400),
    )
    lines = shop(app)
    at = lines.index("  Сюжетное:")
    assert lines[at + 1] == "    Ржавый ключ x2 — 4 зм"
    assert at < lines.index("  Снаряжение и инструменты:")


def test_story_item_of_another_holder_is_not_listed(registry, tmp_path):
    from ai_dm.state.world import CustomItem, ItemHolder

    app = make_shop(registry, tmp_path)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="other", label="Иной", since_s=0, cost_cp=400),
    )
    app.bundle.world.custom_items["custom_2"] = CustomItem(
        id="custom_2", name="Мятый свиток", description="Свиток", quest=True, created_s=0,
        holder=ItemHolder(kind="band", ref="mara", label="Банда", since_s=0, cost_cp=400),
    )
    app.bundle.world.custom_items["custom_3"] = CustomItem(
        id="custom_3", name="Чёрный шар", description="Шар", quest=True, created_s=0,
    )
    text = " ".join(shop(app))
    assert "Ржавый ключ" not in text and "Мятый свиток" not in text and "Чёрный шар" not in text


def test_story_item_price_uses_buy_factor(registry, tmp_path):
    from ai_dm.state.world import CustomItem, ItemHolder

    app = make_shop(registry, tmp_path, attitude=60)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, cost_cp=1000),
    )
    assert row(shop(app), "Ржавый ключ")[0].endswith("— 9 зм")


def test_stock_magic_above_rarity_cap_is_hidden(registry, tmp_path, monkeypatch):
    stock = [InventoryEntry(item_id="potion_of_healing", qty=1, cost_cp=5000)]
    app = make_shop(registry, tmp_path, kind="alchemist", stock=stock)
    model = registry.get("item", "potion_of_healing")
    monkeypatch.setattr(model, "rarity", "legendary")
    assert not row(shop(app), "Зелье лечения")


def test_stock_qty_one_has_no_multiplier(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=300)]
    app = make_shop(registry, tmp_path, kind="smith", stock=stock)
    line = row(shop(app), "Скимитар")[0]
    assert " x" not in line


def test_exactly_40_rows_have_no_more_line(registry, tmp_path):
    from ai_dm.rules import trade as trade_rules

    preset = app_preset(registry, tmp_path)
    count = len(trade_rules.assortment(registry, preset, 1, preset_cfg(registry, tmp_path)))
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=100 + n) for n in range(40 - count)]
    app = make_shop(registry, tmp_path / "x", stock=stock)
    lines = shop(app)
    assert len(names_in(lines)) == 40
    assert not any("…и ещё" in x for x in lines)


def app_preset(registry, tmp_path):
    app = make_shop(registry, tmp_path / "p")
    return app.settings.rules.trade.presets["general"]


def preset_cfg(registry, tmp_path):
    return make_shop(registry, tmp_path / "c").settings.rules


def test_more_line_counts_the_hidden_rows(registry, tmp_path):
    from ai_dm.rules import trade as trade_rules

    preset = app_preset(registry, tmp_path)
    count = len(trade_rules.assortment(registry, preset, 1, preset_cfg(registry, tmp_path)))
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=100 + n) for n in range(50)]
    app = make_shop(registry, tmp_path / "x", stock=stock)
    assert f"    …и ещё {50 + count - 40}" in shop(app)


# блок «Продать»

def test_sell_block_shows_the_cheap_stack_when_worn_one_is_dearest(registry, tmp_path):
    from ai_dm.rules.inventory import equip

    app = make_shop(registry, tmp_path, kind="smith")
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "scimitar", cost_cp=300, quality="worn")
    add_item(hero, "scimitar", cost_cp=2500)
    equip(hero, "scimitar", app.registry)
    sell = row(shop(app), "Продать:")
    assert len(sell) == 1
    assert "оношенн" in sell[0]


def test_sell_block_hides_only_one_of_equal_price_stacks(registry, tmp_path):
    from ai_dm.rules.inventory import equip

    app = make_shop(registry, tmp_path, kind="smith")
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "scimitar", cost_cp=300)
    add_item(hero, "scimitar", cost_cp=300, quality="worn")
    equip(hero, "scimitar", app.registry)
    assert len(row(shop(app), "Продать:")) == 1


def test_sell_block_counts_equipped_as_one(registry, tmp_path):
    from ai_dm.rules.inventory import equip

    app = make_shop(registry, tmp_path, kind="smith")
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "scimitar", 2, cost_cp=300)
    equip(hero, "scimitar", app.registry)
    assert len(row(shop(app), "Продать:")) == 1


def test_sell_block_skips_unknown_item_but_keeps_going(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "ghost_relic", cost_cp=500)
    add_item(hero, "quiver", cost_cp=100)
    sell = row(shop(app), "Продать:")
    assert len(sell) == 1 and "Колчан" in sell[0]


def test_sell_price_of_one_copper_is_listed(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "quiver", cost_cp=2)
    assert row(shop(app), "Продать:")[0].endswith("— 1 мм")


def test_sell_block_lists_custom_item_whatever_the_preset_buys(registry, tmp_path):
    from ai_dm.state.world import CustomItem

    app = make_shop(registry, tmp_path, kind="armorer")
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Костяной свисток", description="Свистит", created_s=0
    )
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "custom_1", cost_cp=400)
    assert row(shop(app), "Продать:")[0].endswith("Костяной свисток — 2 зм")


# несколько торговцев

def test_merchants_are_separated_by_blank_line(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    app.bundle.world.npcs["gor"] = NPC(
        id="gor", name="Гор", means=["сталь"], location_id=hero_of(app.bundle).location_id,
        trade=TradeProfile(kind="smith", purse_cp=100, restock_at_s=FAR),
    )
    lines = shop(app)
    assert lines.count("") == 1
    assert lines[lines.index("") + 1].startswith("Гор")


def test_refusing_merchant_does_not_hide_the_next_one(registry, tmp_path):
    app = make_shop(registry, tmp_path, attitude=-60)
    app.bundle.world.npcs["gor"] = NPC(
        id="gor", name="Гор", means=["сталь"], location_id=hero_of(app.bundle).location_id,
        trade=TradeProfile(kind="smith", purse_cp=100, restock_at_s=FAR),
    )
    lines = shop(app)
    assert "отказывается торговать" in lines[0]
    assert row(lines, "Гор (smith)")
    assert lines[-1].startswith("Деньги:")


def test_sell_block_skips_unbought_item_but_keeps_going(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "quiver", cost_cp=100)
    add_item(hero, "shield", 2, cost_cp=1000)
    sell = row(shop(app), "Продать:")
    assert len(sell) == 1 and "Щит" in sell[0]


def test_sell_block_shows_free_count(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "quiver", 2, cost_cp=100)
    assert row(shop(app), "Продать:") == ["Продать: Колчан x2 — 5 см"]


def test_sell_block_single_item_has_no_count(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    add_item(hero, "quiver", cost_cp=100)
    assert row(shop(app), "Продать:") == ["Продать: Колчан — 5 см"]


def test_hidden_magic_stock_does_not_hide_the_next_stock_row(registry, tmp_path, monkeypatch):
    stock = [
        InventoryEntry(item_id="potion_of_healing", qty=1, cost_cp=5000),
        InventoryEntry(item_id="quiver", qty=1, cost_cp=100),
    ]
    app = make_shop(registry, tmp_path, kind="alchemist", stock=stock)
    monkeypatch.setattr(registry.get("item", "potion_of_healing"), "rarity", "legendary")
    assert row(shop(app), "Колчан")


def test_foreign_story_item_does_not_hide_the_merchants_one(registry, tmp_path):
    from ai_dm.state.world import CustomItem, ItemHolder

    app = make_shop(registry, tmp_path)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Чужой ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="other", label="Иной", since_s=0, cost_cp=400),
    )
    app.bundle.world.custom_items["custom_2"] = CustomItem(
        id="custom_2", name="Мой ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, cost_cp=400),
    )
    text = " ".join(shop(app))
    assert "Мой ключ" in text and "Чужой ключ" not in text


# торг Убеждением (партия Т5): поправка торга в ценах покупки и строка в заголовке

def haggled_shop(registry, tmp_path, percent, days_ago=0, **kwargs):
    app = make_shop(registry, tmp_path, **kwargs)
    profile = app.bundle.world.npcs["mara"].trade
    profile.haggle_percent = percent
    profile.haggle_day = app.bundle.world.clock.now_s // 86400 - days_ago
    return app


def test_haggle_discount_lowers_assortment_price(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10)
    # колчан 100 мм * 0.9 = 90 мм = 9 см
    assert row(shop(app), "Колчан")[0].endswith("— 9 см")


def test_haggle_markup_raises_assortment_price(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, 10)
    assert row(shop(app), "Колчан")[0].endswith("— 1 зм 1 см")


def test_haggle_discount_lowers_stock_price(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=1000, quality="worn")]
    app = haggled_shop(registry, tmp_path, -10, kind="smith", stock=stock)
    line = [x for x in shop(app) if "оношенн" in x][0]
    assert line.endswith("— 9 зм")


def test_haggle_discount_lowers_story_item_price(registry, tmp_path):
    from ai_dm.state.world import CustomItem, ItemHolder

    app = haggled_shop(registry, tmp_path, -10)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, cost_cp=1000),
    )
    assert row(shop(app), "Ржавый ключ")[0].endswith("— 9 зм")


def test_haggle_discount_shows_a_line_in_the_header(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10)
    assert shop(app)[0].endswith("; торг: −10% до конца дня")


def test_header_keeps_the_purse_before_the_haggle_tail(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10)
    assert "кошелёк торговца: 50 зм; торг: −10%" in shop(app)[0]


def test_haggle_fail_shows_plus(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, 10)
    assert "торг: +10% до конца дня" in shop(app)[0]


def test_strong_haggle_shows_minus_20(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -20)
    assert "торг: −20% до конца дня" in shop(app)[0]


def test_no_haggle_no_header_tail(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    assert "торг:" not in shop(app)[0]


def test_next_day_haggle_has_no_tail_and_old_price(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10, days_ago=1)
    lines = shop(app)
    assert "торг:" not in lines[0]
    assert row(lines, "Колчан")[0].endswith("— 1 зм")


def test_haggle_does_not_change_sell_prices(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10)
    hero_of(app.bundle).inventory.clear()
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    sell = row(shop(app), "Продать:")
    assert any("Колчан" in x and x.endswith("— 5 см") for x in sell)


def test_good_attitude_with_strong_haggle_is_clamped_in_the_shop(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -20, attitude=60)
    # 100 мм * 0.8 (зажим, не 0.72) = 80 мм = 8 см
    assert row(shop(app), "Колчан")[0].endswith("— 8 см")


def test_shop_with_haggle_does_not_change_the_profile(registry, tmp_path):
    app = haggled_shop(registry, tmp_path, -10)
    profile = app.bundle.world.npcs["mara"].trade
    before = profile.model_dump_json()
    shop(app)
    assert profile.model_dump_json() == before
