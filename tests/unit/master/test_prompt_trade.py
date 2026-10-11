# Торговля, партия Т3 (docs/TRADE-PLAN.md, разд. 4 и «Тесты» Т3): контекст мастера.
#   scene_npcs[i]["merchant"] = npc.trade.kind -- только у живых NPC с торговым профилем;
#   data["trade"] -- список торговцев сцены (живые, в локации героя), по id;
#       ключа нет, если торговца нет:
#       {"npc_id", "kind", "purse_cp", "sell_factor", "stock": [{"item_id", "price_cp",
#       "quality"?}], "categories": [{"category", "count", "min_cp", "max_cp"}]};
#   stock: не больше 25 позиций, цена по экземпляру со ступенью отношения, quality если есть;
#   categories: сводка ассортимента пресета (цены со ступенью отношения), полный список
#       категории мастер получает действием trade list.
import json

from master_kit import app_cfg, make_ctx

from ai_dm.master.prompt import PromptBuilder
from ai_dm.rules.trade import buy_quote, category_models
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.world import NPC, TradeProfile


def add_merchant(ctx, npc_id="mara", kind="general", purse=5000, stock=None, **fields):
    fields.setdefault("location_id", "vale")
    ctx.bundle.world.npcs[npc_id] = NPC(
        id=npc_id, name=npc_id.capitalize(), means=["товары"],
        trade=TradeProfile(kind=kind, purse_cp=purse, stock=stock or []),
        **fields,
    )


def data_of(ctx):
    request = PromptBuilder(app_cfg()).build(ctx, "Осматриваюсь.", "explore")
    return json.loads(request.messages[0].content[0].text)


def trade_of(ctx):
    return data_of(ctx)["trade"]


def entry(item_id, cost_cp, qty=1):
    return InventoryEntry(item_id=item_id, qty=qty, cost_cp=cost_cp)


# scene_npcs.merchant

def test_scene_npc_with_trade_has_merchant_kind(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="smith")
    npcs = {n["id"]: n for n in data_of(ctx)["scene_npcs"]}
    assert npcs["mara"]["merchant"] == "smith"


def test_scene_npc_without_trade_has_no_merchant_field(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    npcs = {n["id"]: n for n in data_of(ctx)["scene_npcs"]}
    assert "merchant" not in npcs["grakh"]


def test_dead_merchant_is_not_in_scene_npcs(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, status="dead")
    assert "mara" not in [n["id"] for n in data_of(ctx)["scene_npcs"]]


# ключ trade: когда есть

def test_no_merchant_no_trade_key(registry, cfg):
    assert "trade" not in data_of(make_ctx(registry, cfg))


def test_trade_key_with_merchant_in_scene(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    assert [t["npc_id"] for t in trade_of(ctx)] == ["mara"]


def test_dead_merchant_gives_no_trade_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, status="dead")
    assert "trade" not in data_of(ctx)


def test_merchant_in_other_location_gives_no_trade_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, location_id="forest")
    assert "trade" not in data_of(ctx)


def test_merchant_without_location_gives_no_trade_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, location_id=None)
    assert "trade" not in data_of(ctx)


def test_gone_merchant_gives_no_trade_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, status="gone")
    assert "trade" not in data_of(ctx)


def test_two_merchants_are_sorted_by_id(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, npc_id="zed", kind="smith")
    add_merchant(ctx, npc_id="mara")
    assert [t["npc_id"] for t in trade_of(ctx)] == ["mara", "zed"]


def test_only_present_merchant_among_two(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, npc_id="zed", kind="smith", location_id="forest")
    add_merchant(ctx, npc_id="mara")
    assert [t["npc_id"] for t in trade_of(ctx)] == ["mara"]


# поля записи

def test_trade_entry_has_kind_and_purse(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="smith", purse=1234)
    entry_ = trade_of(ctx)[0]
    assert (entry_["npc_id"], entry_["kind"], entry_["purse_cp"]) == ("mara", "smith", 1234)


def test_trade_entry_has_exactly_the_documented_keys(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    assert set(trade_of(ctx)[0]) == {
        "npc_id", "kind", "purse_cp", "sell_factor", "stock", "categories"
    }


def test_sell_factor_is_base_for_neutral_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=0)
    assert trade_of(ctx)[0]["sell_factor"] == cfg.trade.sell_factor


def test_sell_factor_is_better_for_good_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=60)
    assert trade_of(ctx)[0]["sell_factor"] == cfg.trade.attitude_good_sell_factor


# stock

def test_stock_is_empty_without_stock(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    assert trade_of(ctx)[0]["stock"] == []


def test_stock_position_has_item_id_and_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("longsword", 1500)])
    assert trade_of(ctx)[0]["stock"] == [{"item_id": "longsword", "price_cp": 1500}]


def test_stock_position_has_quality_when_set(registry, cfg):
    ctx = make_ctx(registry, cfg)
    worn = InventoryEntry(item_id="longsword", qty=1, cost_cp=700, quality="worn")
    add_merchant(ctx, stock=[worn, entry("longsword", 1500)])
    stock = trade_of(ctx)[0]["stock"]
    assert stock[0] == {"item_id": "longsword", "price_cp": 700, "quality": "worn"}
    assert "quality" not in stock[1]


def test_stock_price_uses_attitude_step(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=60, stock=[entry("longsword", 1500)])
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == buy_quote(1500, 60, cfg)
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == 1350


def test_stock_price_rounds_up(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=60, stock=[entry("longsword", 101)])
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == 91


def test_stock_keeps_its_order(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("longsword", 5000), entry("scimitar", 100)])
    stock = trade_of(ctx)[0]["stock"]
    assert [p["item_id"] for p in stock] == ["longsword", "scimitar"]


def test_stock_over_the_cap_is_cut_to_25(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("longsword", 1500 + i) for i in range(30)])
    assert len(trade_of(ctx)[0]["stock"]) == 25


# categories

def test_categories_have_exactly_the_documented_keys(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    categories = trade_of(ctx)[0]["categories"]
    assert categories
    assert all(set(c) == {"category", "count", "min_cp", "max_cp"} for c in categories)


def test_categories_belong_to_the_preset(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="smith")
    allowed = cfg.trade.presets["smith"].categories
    names = [c["category"] for c in trade_of(ctx)[0]["categories"]]
    assert names and set(names) <= set(allowed)


def test_categories_are_sorted_and_unique(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    names = [c["category"] for c in trade_of(ctx)[0]["categories"]]
    assert names == sorted(set(names))


def test_categories_count_and_prices_match_the_assortment(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=0)
    models = category_models(registry, cfg.trade.presets["general"], 1, cfg)
    for c in trade_of(ctx)[0]["categories"]:
        prices = [buy_quote(m.cost_cp, 0, cfg) for m in models[c["category"]]]
        assert (c["count"], c["min_cp"], c["max_cp"]) == (len(prices), min(prices), max(prices))


def test_categories_have_discount_for_good_attitude(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=0)
    add_merchant(ctx, npc_id="zed", attitude=60)
    by_id = {t["npc_id"]: t for t in trade_of(ctx)}
    assert by_id["zed"]["categories"][0]["max_cp"] <= by_id["mara"]["categories"][0]["max_cp"]
    assert sum(c["max_cp"] for c in by_id["zed"]["categories"]) < sum(
        c["max_cp"] for c in by_id["mara"]["categories"]
    )


def test_armorer_has_only_the_armor_category(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="armorer")
    names = [c["category"] for c in trade_of(ctx)[0]["categories"]]
    assert "armor" in names
    assert "weapon" not in names


def test_each_merchant_has_own_stock_and_categories(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, npc_id="mara", stock=[entry("longsword", 1500)])
    add_merchant(ctx, npc_id="zed", kind="armorer")
    by_id = {t["npc_id"]: t for t in trade_of(ctx)}
    assert by_id["mara"]["stock"][0]["item_id"] == "longsword"
    assert by_id["zed"]["stock"] == []
    assert "weapon" not in [c["category"] for c in by_id["zed"]["categories"]]


def test_categories_depend_on_hero_level_for_magic(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="alchemist")
    low = sum(c["count"] for c in trade_of(ctx)[0]["categories"])
    ctx.hero.sheet.primary.level = max(cfg.loot.rarity_cap_by_level)
    high = sum(c["count"] for c in trade_of(ctx)[0]["categories"])
    assert low <= high


# торг Убеждением (партия Т5): ключ haggle и цены с поправкой

def haggled(ctx, percent, day=0, npc_id="mara"):
    profile = ctx.bundle.world.npcs[npc_id].trade
    profile.haggle_percent = percent
    profile.haggle_day = day


def test_no_haggle_no_haggle_key(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    assert "haggle" not in trade_of(ctx)[0]


def test_haggle_key_has_percent_today(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    haggled(ctx, -10)
    assert trade_of(ctx)[0]["haggle"] == {"percent": -10}


def test_haggle_key_after_fail_is_plus(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    haggled(ctx, 10)
    assert trade_of(ctx)[0]["haggle"] == {"percent": 10}


def test_haggle_key_is_per_merchant(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, npc_id="zed", kind="smith")
    add_merchant(ctx)
    haggled(ctx, -10)
    by_id = {t["npc_id"]: t for t in trade_of(ctx)}
    assert "haggle" in by_id["mara"]
    assert "haggle" not in by_id["zed"]


def test_next_day_no_haggle_key_and_old_prices(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("scimitar", 1000)])
    haggled(ctx, -10)
    ctx.bundle.world.clock.advance(86400)
    merchant = trade_of(ctx)[0]
    assert "haggle" not in merchant
    assert merchant["stock"][0]["price_cp"] == 1000


def test_stock_price_has_the_haggle_discount(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("scimitar", 1000)])
    haggled(ctx, -10)
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == 900


def test_stock_price_has_the_haggle_markup(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, stock=[entry("scimitar", 1000)])
    haggled(ctx, 10)
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == 1100


def test_categories_prices_have_the_haggle_discount(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="smith")
    before = trade_of(ctx)[0]["categories"]
    haggled(ctx, -10)
    after = trade_of(ctx)[0]["categories"]
    assert [c["category"] for c in after] == [c["category"] for c in before]
    assert all(a["max_cp"] < b["max_cp"] for a, b in zip(after, before, strict=True))
    assert all(a["count"] == b["count"] for a, b in zip(after, before, strict=True))


def test_categories_prices_match_buy_quote_with_haggle(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, kind="smith")
    haggled(ctx, -10)
    preset = cfg.trade.presets["smith"]
    level = ctx.bundle.heroes[0].sheet.level
    models = category_models(registry, preset, level, cfg)
    for c in trade_of(ctx)[0]["categories"]:
        prices = [buy_quote(m.cost_cp, 0, cfg, -10) for m in models[c["category"]]]
        assert (c["min_cp"], c["max_cp"]) == (min(prices), max(prices))


def test_sell_factor_is_not_changed_by_haggle(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx)
    haggled(ctx, -20)
    assert trade_of(ctx)[0]["sell_factor"] == 0.5


def test_good_attitude_strong_haggle_stock_is_clamped(registry, cfg):
    ctx = make_ctx(registry, cfg)
    add_merchant(ctx, attitude=60, stock=[entry("scimitar", 1000)])
    haggled(ctx, -20)
    assert trade_of(ctx)[0]["stock"][0]["price_cp"] == 800
