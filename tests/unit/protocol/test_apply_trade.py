# Торговля, партия Т2 (docs/plan-trade.md, разд. 3, 4 и «Т1: заметки для Т2»): инструмент trade.
#   trade{npc_id, direction: buy|sell, item_id, qty, quality: junk|worn|used|new|any} -- цену
#       движок считает сам (rules/trade.py), мастер её не передаёт.
#   Проверки по порядку: бой -> Invalid in_combat; нет NPC -> unknown_npc; не alive или не в
#       локации героя -> npc_absent; npc.trade None -> not_merchant; qty < 1 -> bad_amount;
#       attitude <= attitude_refuse_at (-50) -> rejected;
#       сделок за сцену >= ops_per_scene -> rejected.
#   Перед сделкой ленивый restock кошелька.
#   buy: id из ассортимента пресета или из stock торговца, иначе Invalid not_sold (+ список id);
#       qty <= give_item_max_qty, урезается по деньгам (clamped); денег нет ->
#       rejected;
#       сюжетный с holder.ref == npc_id выкупается по holder.cost_cp.
#   sell: самый дорогой стек героя, надетый экземпляр не берётся (единственный -> rejected);
#       категория не в buys -> rejected; цена 0 -> rejected до деления на кошелёк; qty урезается до
#       наличия и purse_cp // price; SRD уходит в stock торговца, сюжетный -- держателю-NPC.
#   Результат {direction, item_id, qty, price_cp, total_cp, money_cp, purse_cp}; события
#       item_gained (покупка) и item_sold (продажа) с data item/qty.
import pytest
from protocol_kit import combat_request, dump, make_bundle, make_ctx, req

from ai_dm.master.prompt import lost_items_data
from ai_dm.protocol.apply import apply
from ai_dm.protocol.decision import Decision, Invalid
from ai_dm.rules.inventory import count_item
from ai_dm.rules.money import format_cp
from ai_dm.rules.trade import buy_quote
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.world import NPC, TradeProfile

FAR = 10**9


def add_merchant(ctx, npc_id="mara", kind="general", purse=5000, stock=None, **fields):
    fields.setdefault("location_id", "vale")
    ctx.bundle.world.npcs[npc_id] = NPC(
        id=npc_id, name=npc_id.capitalize(), means=["товары"],
        trade=TradeProfile(
            kind=kind, purse_cp=purse, restock_at_s=FAR, stock=stock or []
        ),
        **fields,
    )


def trade_ctx(registry, cfg, kind="general", purse=5000, money=1000, stock=None, **fields):
    ctx = make_ctx(registry, cfg)
    ctx.hero.money_cp = money
    add_merchant(ctx, kind=kind, purse=purse, stock=stock, **fields)
    return ctx


def trade(ctx, direction, item_id, qty=1, npc_id="mara", quality="any"):
    return apply(
        ctx, req(
            "trade", npc_id=npc_id, direction=direction, item_id=item_id, qty=qty,
            quality=quality,
        )
    )


def listing(ctx, category, npc_id="mara"):
    return apply(
        ctx, req(
            "trade", npc_id=npc_id, direction="list", item_id="", qty=0, category=category,
        )
    )


def buy(ctx, item_id, qty=1, **kwargs):
    return trade(ctx, "buy", item_id, qty, **kwargs)


def sell(ctx, item_id, qty=1, **kwargs):
    return trade(ctx, "sell", item_id, qty, **kwargs)


def stacks(ctx, item_id):
    return sorted(
        ((e.cost_cp, e.quality, e.qty) for e in ctx.hero.inventory if e.item_id == item_id),
        key=lambda s: (s[0], s[1] or ""),
    )


def hero_has(ctx, *entries):
    ctx.hero.inventory = list(entries)
    ctx.hero.equipped.armor = None
    ctx.hero.equipped.shield = None
    ctx.hero.equipped.main_hand = None
    ctx.hero.equipped.off_hand = None


def merchant(ctx, npc_id="mara"):
    return ctx.bundle.world.npcs[npc_id].trade


def stock_of(ctx, npc_id="mara"):
    return [(e.item_id, e.cost_cp, e.quality, e.qty) for e in merchant(ctx, npc_id).stock]


def scimitar(cost_cp, qty=1, quality=None):
    return InventoryEntry(item_id="scimitar", qty=qty, cost_cp=cost_cp, quality=quality)


# торговец недоступен

def test_unknown_npc_is_invalid_and_lists_merchants(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, "arrows", npc_id="nobody")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_npc"
    assert "mara" in d.message
    assert dump(ctx) == before


def test_merchant_in_another_location_is_absent(registry, cfg):
    ctx = trade_ctx(registry, cfg, location_id="forest")
    before = dump(ctx)
    d = buy(ctx, "arrows")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"
    assert dump(ctx) == before


def test_merchant_without_location_is_absent(registry, cfg):
    ctx = trade_ctx(registry, cfg, location_id=None)
    d = buy(ctx, "arrows")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


@pytest.mark.parametrize("status", ["dead", "gone"])
def test_not_alive_merchant_is_invalid(registry, cfg, status):
    ctx = trade_ctx(registry, cfg, status=status)
    before = dump(ctx)
    d = buy(ctx, "arrows")
    assert isinstance(d, Invalid)
    assert d.code in ("unknown_npc", "npc_absent")
    assert dump(ctx) == before


def test_npc_without_trade_is_not_a_merchant(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, "arrows", npc_id="grakh")
    assert isinstance(d, Invalid)
    assert d.code == "not_merchant"
    assert dump(ctx) == before


def test_trade_during_combat_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    apply(ctx, combat_request())
    before = dump(ctx)
    d = buy(ctx, "arrows")
    assert isinstance(d, Invalid)
    assert d.code == "in_combat"
    assert dump(ctx) == before


@pytest.mark.parametrize("qty", [0, -1])
def test_qty_below_one_is_bad_amount(registry, cfg, qty):
    ctx = trade_ctx(registry, cfg)
    for direction in ("buy", "sell"):
        d = trade(ctx, direction, "arrows", qty)
        assert isinstance(d, Invalid)
        assert d.code == "bad_amount"


# отношение

@pytest.mark.parametrize("attitude", [-50, -60, -100])
def test_hostile_merchant_refuses(registry, cfg, attitude):
    ctx = trade_ctx(registry, cfg, attitude=attitude)
    before = dump(ctx)
    d = buy(ctx, "arrows")
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_hostile_merchant_refuses_to_buy_from_hero_too(registry, cfg):
    ctx = trade_ctx(registry, cfg, attitude=-60)
    hero_has(ctx, scimitar(1000))
    before = dump(ctx)
    d = sell(ctx, "scimitar")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_attitude_just_above_refusal_trades(registry, cfg):
    ctx = trade_ctx(registry, cfg, attitude=-49)
    assert buy(ctx, "arrows").status == "accepted"


def test_good_attitude_makes_buying_cheaper(registry, cfg):
    ctx = trade_ctx(registry, cfg, attitude=60)
    d = buy(ctx, "arrows")
    assert d.result["price_cp"] == 90
    assert ctx.hero.money_cp == 910


def test_good_attitude_makes_selling_dearer(registry, cfg):
    ctx = trade_ctx(registry, cfg, attitude=60)
    hero_has(ctx, scimitar(1000))
    d = sell(ctx, "scimitar")
    assert d.result["price_cp"] == 600


def test_attitude_below_good_uses_base_prices(registry, cfg):
    ctx = trade_ctx(registry, cfg, attitude=49)
    assert buy(ctx, "arrows").result["price_cp"] == 100


# покупка

def test_buy_pays_and_gives_the_item_with_its_price(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx)
    d = buy(ctx, "arrows", 3)
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 700
    assert stacks(ctx, "arrows") == [(100, None, 3)]


def test_buy_result_has_all_fields(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    d = buy(ctx, "arrows", 3)
    assert d.result == {
        "direction": "buy", "item_id": "arrows", "qty": 3, "price_cp": 100, "total_cp": 300,
        "money_cp": 700, "purse_cp": 5000,
    }


def test_buy_log_names_item_and_total(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    d = buy(ctx, "arrows", 3)
    assert len(d.log) == 1
    assert d.log[0].startswith("Куплено: ")
    assert registry.get("item", "arrows").name in d.log[0]
    assert format_cp(300) in d.log[0]


def test_buy_emits_item_gained(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    buy(ctx, "arrows", 3)
    gained = [(e.data["item"], e.data["qty"]) for e in ctx.events if e.type == "item_gained"]
    assert gained == [("arrows", 3)]


def test_buy_more_than_money_is_clamped(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=1000)
    hero_has(ctx)
    d = buy(ctx, "arrows", 20)
    assert d.status == "clamped"
    assert d.signal_to_master
    assert d.report_tag == "limit-exceeded"
    assert d.result["qty"] == 10
    assert d.result["total_cp"] == 1000
    assert ctx.hero.money_cp == 0
    assert stacks(ctx, "arrows") == [(100, None, 10)]


def test_buy_without_money_is_rejected_and_changes_nothing(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    before = dump(ctx)
    d = buy(ctx, "arrows", 5)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_buy_with_money_less_than_one_item_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=99)
    before = dump(ctx)
    assert buy(ctx, "arrows").status == "rejected"
    assert dump(ctx) == before


def test_buy_exact_money_is_accepted(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=100)
    d = buy(ctx, "arrows")
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 0


def test_buy_is_capped_by_give_item_max_qty(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=100000)
    hero_has(ctx)
    d = buy(ctx, "arrows", cfg.limits.give_item_max_qty + 5)
    assert d.status == "clamped"
    assert d.result["qty"] == cfg.limits.give_item_max_qty
    assert ctx.hero.money_cp == 100000 - 100 * cfg.limits.give_item_max_qty


def test_buy_does_not_add_item_stack_with_other_price(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, InventoryEntry(item_id="arrows", qty=2, cost_cp=70))
    buy(ctx, "arrows", 1)
    assert stacks(ctx, "arrows") == [(70, None, 2), (100, None, 1)]


def test_buy_item_outside_the_preset_is_not_sold(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, "longsword")
    assert isinstance(d, Invalid)
    assert d.code == "not_sold"
    assert "допустимые id" in d.message
    assert dump(ctx) == before


def test_buy_not_sold_lists_at_most_twenty_ids(registry, cfg):
    extra = [
        registry.get("item", "arrows").model_copy(update={"id": f"thing_{n:02d}"})
        for n in range(25)
    ]
    ctx = trade_ctx(registry.with_items({"item": extra}), cfg)
    d = buy(ctx, "longsword")
    assert isinstance(d, Invalid)
    assert d.code == "not_sold"
    assert "и ещё" in d.message


def test_not_sold_message_lists_what_the_merchant_sells(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    d = buy(ctx, "arrows")
    assert "leather_armor" in d.message


def test_buy_unknown_item_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    before = dump(ctx)
    d = buy(ctx, "no_such_thing")
    assert isinstance(d, Invalid)
    assert d.code in ("not_sold", "unknown_item")
    assert dump(ctx) == before


def test_buy_magic_at_general_is_not_sold(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=10000)
    d = buy(ctx, "potion_of_healing")
    assert isinstance(d, Invalid)
    assert d.code == "not_sold"


def test_alchemist_sells_magic_within_the_rarity_cap(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="alchemist", money=10000)
    d = buy(ctx, "potion_of_healing")
    assert d.status == "accepted"
    assert d.result["price_cp"] == 5000
    assert count_item(ctx.hero, "potion_of_healing") == 1


def test_alchemist_does_not_sell_magic_above_the_rarity_cap(registry, cfg):
    rare = registry.get("item", "potion_of_healing").model_copy(
        update={"id": "potion_rare", "rarity": "rare"}
    )
    ctx = trade_ctx(registry.with_items({"item": [rare]}), cfg, kind="alchemist", money=10000)
    before = dump(ctx)
    d = buy(ctx, "potion_rare")
    assert isinstance(d, Decision)
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


# покупка из stock

def stocked(registry, cfg, **kwargs):
    stock = [InventoryEntry(item_id="scimitar", qty=2, cost_cp=100, quality="junk")]
    return trade_ctx(registry, cfg, stock=stock, **kwargs)


def test_buy_from_stock_even_outside_the_preset(registry, cfg):
    ctx = stocked(registry, cfg)
    hero_has(ctx)
    d = buy(ctx, "scimitar")
    assert d.status == "accepted"
    assert d.result["price_cp"] == 100
    assert stacks(ctx, "scimitar") == [(100, "junk", 1)]


def test_buy_from_stock_keeps_the_quality_in_the_log(registry, cfg):
    ctx = stocked(registry, cfg)
    d = buy(ctx, "scimitar")
    assert "Ржавый скимитар" in d.log[0]


def test_buy_from_stock_decreases_the_stock(registry, cfg):
    ctx = stocked(registry, cfg)
    buy(ctx, "scimitar")
    assert stock_of(ctx) == [("scimitar", 100, "junk", 1)]


def test_buy_the_last_from_stock_removes_the_entry(registry, cfg):
    ctx = stocked(registry, cfg)
    buy(ctx, "scimitar", 2)
    assert stock_of(ctx) == []


def test_buy_from_stock_rounds_the_price_up_with_good_attitude(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=15, quality="worn")]
    ctx = trade_ctx(registry, cfg, stock=stock, attitude=60)
    d = buy(ctx, "scimitar")
    assert d.result["price_cp"] == 14


# продажа

def test_sell_gives_money_and_takes_the_item(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1500, qty=2))
    d = sell(ctx, "scimitar")
    assert isinstance(d, Decision)
    assert d.status == "accepted"
    assert ctx.hero.money_cp == 750
    assert stacks(ctx, "scimitar") == [(1500, None, 1)]


def test_sell_result_has_all_fields(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1500, qty=2))
    d = sell(ctx, "scimitar", 2)
    assert d.result == {
        "direction": "sell", "item_id": "scimitar", "qty": 2, "price_cp": 750,
        "total_cp": 1500, "money_cp": 1500, "purse_cp": 3500,
    }


def test_sell_reduces_the_merchant_purse(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=5000)
    hero_has(ctx, scimitar(1500))
    sell(ctx, "scimitar")
    assert merchant(ctx).purse_cp == 4250


def test_sell_log_names_item_and_total(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(1500, qty=2, quality="worn"))
    d = sell(ctx, "scimitar", 2)
    assert len(d.log) == 1
    assert d.log[0].startswith("Продано: ")
    assert "Поношенный скимитар" in d.log[0]
    assert format_cp(1500) in d.log[0]


def test_sell_emits_item_sold(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(1500, qty=2))
    sell(ctx, "scimitar", 2)
    sold = [(e.data["item"], e.data["qty"]) for e in ctx.events if e.type == "item_sold"]
    assert sold == [("scimitar", 2)]


def test_sell_prices_round_down(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(101))
    assert sell(ctx, "scimitar").result["price_cp"] == 50


def test_sell_takes_the_dearest_stack_first(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(100, quality="junk"), scimitar(1000))
    d = sell(ctx, "scimitar")
    assert d.result["price_cp"] == 500
    assert stacks(ctx, "scimitar") == [(100, "junk", 1)]


def test_sell_takes_one_stack_per_trade(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(100, quality="junk"), scimitar(1000))
    d = sell(ctx, "scimitar", 2)
    assert d.status == "clamped"
    assert d.result["qty"] == 1
    assert stacks(ctx, "scimitar") == [(100, "junk", 1)]


def test_sell_quality_picks_that_stack(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(100, quality="junk"), scimitar(1000))
    d = sell(ctx, "scimitar", quality="junk")
    assert d.result["price_cp"] == 50
    assert stacks(ctx, "scimitar") == [(1000, None, 1)]


def test_sell_quality_new_picks_the_stack_without_quality(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1000, quality="junk"), scimitar(500))
    d = sell(ctx, "scimitar", quality="new")
    assert d.result["price_cp"] == 250
    assert stacks(ctx, "scimitar") == [(1000, "junk", 1)]


def test_sell_missing_quality_is_not_in_inventory(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(1000))
    before = dump(ctx)
    d = sell(ctx, "scimitar", quality="junk")
    assert isinstance(d, Invalid)
    assert d.code == "not_in_inventory"
    assert dump(ctx) == before


def test_sell_item_hero_does_not_have_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx)
    before = dump(ctx)
    d = sell(ctx, "scimitar")
    assert isinstance(d, Invalid)
    assert d.code == "not_in_inventory"
    assert dump(ctx) == before


def test_sell_more_than_hero_has_is_clamped(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1000, qty=2))
    d = sell(ctx, "scimitar", 5)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.result["qty"] == 2
    assert ctx.hero.money_cp == 1000


def test_sell_the_only_equipped_item_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, InventoryEntry(item_id="longsword", qty=1, cost_cp=1500))
    ctx.hero.equipped.main_hand = "longsword"
    before = dump(ctx)
    d = sell(ctx, "longsword")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_sell_the_only_equipped_armor_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, InventoryEntry(item_id="chain_mail", qty=1, cost_cp=7500))
    ctx.hero.equipped.armor = "chain_mail"
    before = dump(ctx)
    d = sell(ctx, "chain_mail")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_sell_the_only_equipped_shield_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, InventoryEntry(item_id="shield", qty=1, cost_cp=1000))
    ctx.hero.equipped.shield = "shield"
    before = dump(ctx)
    assert sell(ctx, "shield").status == "rejected"
    assert dump(ctx) == before


def test_sell_with_equipped_and_a_second_stack_sells_the_second(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(
        ctx, InventoryEntry(item_id="longsword", qty=1, cost_cp=1500),
        InventoryEntry(item_id="longsword", qty=1, cost_cp=100, quality="junk"),
    )
    ctx.hero.equipped.main_hand = "longsword"
    d = sell(ctx, "longsword")
    assert d.status == "accepted"
    assert d.result["price_cp"] == 50
    assert stacks(ctx, "longsword") == [(1500, None, 1)]
    assert ctx.hero.equipped.main_hand == "longsword"


def test_sell_two_of_equipped_stack_with_one_spare_sells_the_spare_only(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, InventoryEntry(item_id="longsword", qty=2, cost_cp=1500))
    ctx.hero.equipped.main_hand = "longsword"
    d = sell(ctx, "longsword", 2)
    assert d.status == "clamped"
    assert d.result["qty"] == 1
    assert stacks(ctx, "longsword") == [(1500, None, 1)]


# кошелёк торговца

def test_sell_above_the_purse_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=300, money=0)
    hero_has(ctx, scimitar(1500))
    before = dump(ctx)
    d = sell(ctx, "scimitar")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_sell_beyond_the_purse_is_clamped(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=1600, money=0)
    hero_has(ctx, scimitar(1500, qty=3))
    d = sell(ctx, "scimitar", 3)
    assert d.status == "clamped"
    assert d.report_tag == "limit-exceeded"
    assert d.result["qty"] == 2
    assert d.result["purse_cp"] == 100
    assert ctx.hero.money_cp == 1500
    assert stacks(ctx, "scimitar") == [(1500, None, 1)]


def test_sell_for_exactly_the_purse_is_accepted(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=750, money=0)
    hero_has(ctx, scimitar(1500))
    d = sell(ctx, "scimitar")
    assert d.status == "accepted"
    assert merchant(ctx).purse_cp == 0


def test_purse_is_refilled_lazily_when_the_time_has_come(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=0, money=0)
    merchant(ctx).restock_at_s = 0
    ctx.bundle.world.clock.advance(100)
    hero_has(ctx, scimitar(1500))
    d = sell(ctx, "scimitar")
    assert d.status == "accepted"
    assert merchant(ctx).purse_cp == 5000 - 750
    assert merchant(ctx).restock_at_s == 100 + cfg.trade.restock_days * 86400


def test_purse_stays_while_the_restock_is_not_due(registry, cfg):
    ctx = trade_ctx(registry, cfg, purse=100, money=0)
    hero_has(ctx, scimitar(150))
    d = sell(ctx, "scimitar")
    assert d.status == "accepted"
    assert merchant(ctx).purse_cp == 25


# цена ноль и категории

def test_sell_item_without_price_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(0))
    before = dump(ctx)
    d = sell(ctx, "scimitar")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_sell_item_worth_less_than_one_coin_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(1))
    before = dump(ctx)
    d = sell(ctx, "scimitar")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_sell_for_nothing_is_rejected_even_with_an_empty_purse(registry, cfg):
    # цена 0 проверяется до деления purse_cp // price
    ctx = trade_ctx(registry, cfg, purse=0)
    hero_has(ctx, scimitar(0))
    d = sell(ctx, "scimitar")
    assert isinstance(d, Decision)
    assert d.status == "rejected"


def test_sell_category_the_merchant_does_not_buy_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="smith")
    hero_has(ctx, InventoryEntry(item_id="healers_kit", qty=1, cost_cp=500))
    before = dump(ctx)
    d = sell(ctx, "healers_kit")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_sell_category_the_merchant_buys_is_accepted(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="smith")
    hero_has(ctx, scimitar(1000))
    assert sell(ctx, "scimitar").status == "accepted"


# sell -> stock -> buy

def test_sold_item_goes_to_the_stock_with_its_price_and_quality(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(100, qty=2, quality="junk"))
    sell(ctx, "scimitar", 2)
    assert stock_of(ctx) == [("scimitar", 100, "junk", 2)]


def test_sold_items_with_same_price_and_quality_merge_in_the_stock(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(100, qty=2, quality="junk"))
    sell(ctx, "scimitar")
    sell(ctx, "scimitar")
    assert stock_of(ctx) == [("scimitar", 100, "junk", 2)]


def test_sold_items_with_other_price_make_a_separate_stock_entry(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(100, quality="junk"), scimitar(1000))
    sell(ctx, "scimitar")
    sell(ctx, "scimitar")
    assert sorted(stock_of(ctx)) == [
        ("scimitar", 100, "junk", 1), ("scimitar", 1000, None, 1),
    ]


def test_sold_item_can_be_bought_back_with_a_loss(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1000))
    sell(ctx, "scimitar")
    assert ctx.hero.money_cp == 500
    d = buy(ctx, "scimitar")
    assert d.status == "rejected"
    ctx.hero.money_cp = 1000
    d = buy(ctx, "scimitar")
    assert d.status == "accepted"
    assert d.result["price_cp"] == 1000
    assert stacks(ctx, "scimitar") == [(1000, None, 1)]
    assert stock_of(ctx) == []


def test_sale_does_not_change_the_item_in_the_world_catalog(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(1000))
    sell(ctx, "scimitar")
    assert ctx.bundle.world.custom_items == {}


# лимит сделок за сцену

def test_ops_per_scene_limit_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene
    before = dump(ctx)
    d = buy(ctx, "arrows")
    assert d.status == "rejected"
    assert d.signal_to_master
    assert dump(ctx) == before


def test_each_accepted_trade_counts_in_the_scene(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    buy(ctx, "arrows")
    buy(ctx, "arrows")
    assert ctx.scene.trades == 2


def test_last_trade_under_the_limit_is_accepted(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    ctx.scene.trades = cfg.trade.ops_per_scene - 1
    assert buy(ctx, "arrows").status == "accepted"
    assert ctx.scene.trades == cfg.trade.ops_per_scene


def test_rejected_trade_is_not_counted(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    buy(ctx, "arrows")
    assert ctx.scene.trades == 0


def test_trade_works_without_a_scene(registry, cfg):
    ctx = make_ctx(registry, cfg, bundle=make_bundle(registry, with_scene=False))
    add_merchant(ctx)
    assert buy(ctx, "arrows").status == "accepted"


# сюжетные предметы (разд. 4)

def give(ctx, name="Ржавый ключ", **fields):
    data = {"description": "", "qty": 1, "weight_lb": 0, "cost_cp": 700, "quest": True}
    data.update(fields)
    return apply(ctx, req("give_custom_item", name=name, **data))


def quest_ctx(registry, cfg, qty=1, cost_cp=700, **kwargs):
    ctx = trade_ctx(registry, cfg, **kwargs)
    give(ctx, qty=qty, cost_cp=cost_cp)
    return ctx


def holder(ctx, item_id="custom_1"):
    return ctx.bundle.world.custom_items[item_id].holder


def test_selling_a_quest_item_gives_it_to_the_merchant_as_holder(registry, cfg):
    ctx = quest_ctx(registry, cfg, money=0)
    d = sell(ctx, "custom_1")
    assert d.status == "accepted"
    assert count_item(ctx.hero, "custom_1") == 0
    held = holder(ctx)
    assert held.kind == "npc"
    assert held.ref == "mara"
    assert held.label == "Mara"
    assert held.location_id == "vale"
    assert held.qty == 1
    assert held.cost_cp == 700


def test_quest_sale_pays_half_of_the_item_price(registry, cfg):
    ctx = quest_ctx(registry, cfg, money=0)
    d = sell(ctx, "custom_1")
    assert d.result["price_cp"] == 350
    assert ctx.hero.money_cp == 350
    assert merchant(ctx).purse_cp == 4650


def test_quest_sale_remembers_the_time(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    ctx.bundle.world.clock.advance(3600)
    sell(ctx, "custom_1")
    assert holder(ctx).since_s == ctx.bundle.world.clock.now_s


def test_quest_item_does_not_go_to_the_stock(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    sell(ctx, "custom_1")
    assert stock_of(ctx) == []


def test_quest_item_is_accepted_by_a_merchant_who_buys_other_things(registry, cfg):
    ctx = quest_ctx(registry, cfg, kind="armorer")
    assert sell(ctx, "custom_1").status == "accepted"


def test_sold_quest_item_shows_in_lost_items(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    sell(ctx, "custom_1")
    lost = lost_items_data(ctx.bundle.world)
    assert [(i["item_id"], i["holder"]["label"]) for i in lost] == [("custom_1", "Mara")]


def test_quest_item_without_price_cannot_be_sold(registry, cfg):
    ctx = quest_ctx(registry, cfg, cost_cp=0)
    before = dump(ctx)
    d = sell(ctx, "custom_1")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_selling_part_of_a_quest_stack_keeps_the_rest_with_the_hero(registry, cfg):
    ctx = quest_ctx(registry, cfg, qty=3)
    sell(ctx, "custom_1", 2)
    assert count_item(ctx.hero, "custom_1") == 1
    assert holder(ctx).qty == 2


def test_quest_sale_log_uses_the_item_name(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    d = sell(ctx, "custom_1")
    assert d.log[0].startswith("Продано: ")
    assert "Ржавый ключ" in d.log[0]


def test_buy_back_from_the_holder_returns_the_item_with_its_price(registry, cfg):
    ctx = quest_ctx(registry, cfg, money=0)
    sell(ctx, "custom_1")
    ctx.hero.money_cp = 1000
    d = buy(ctx, "custom_1")
    assert d.status == "accepted"
    assert d.result["price_cp"] == 700
    assert ctx.hero.money_cp == 300
    assert holder(ctx) is None
    assert stacks(ctx, "custom_1") == [(700, None, 1)]


def test_buy_back_of_a_better_attitude_costs_less(registry, cfg):
    ctx = quest_ctx(registry, cfg, attitude=60)
    sell(ctx, "custom_1")
    ctx.hero.money_cp = 1000
    assert buy(ctx, "custom_1").result["price_cp"] == 630


def test_buy_back_without_money_is_rejected_and_keeps_the_holder(registry, cfg):
    ctx = quest_ctx(registry, cfg, money=0)
    sell(ctx, "custom_1")
    ctx.hero.money_cp = 100
    before = dump(ctx)
    d = buy(ctx, "custom_1")
    assert d.status == "rejected"
    assert dump(ctx) == before
    assert holder(ctx).ref == "mara"


def test_buy_back_emits_item_gained(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    sell(ctx, "custom_1")
    ctx.hero.money_cp = 1000
    ctx.events.clear()
    buy(ctx, "custom_1")
    gained = [(e.data["item"], e.data["qty"]) for e in ctx.events if e.type == "item_gained"]
    assert gained == [("custom_1", 1)]


def test_buy_back_at_another_merchant_is_invalid(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    add_merchant(ctx, "tilda")
    sell(ctx, "custom_1")
    ctx.hero.money_cp = 1000
    before = dump(ctx)
    d = buy(ctx, "custom_1", npc_id="tilda")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before
    assert holder(ctx).ref == "mara"


def test_quest_item_with_a_robber_holder_is_not_for_sale(registry, cfg):
    ctx = quest_ctx(registry, cfg)
    apply(ctx, req("take_item", item_id="custom_1", qty=1, why="stolen"))
    ctx.hero.money_cp = 1000
    before = dump(ctx)
    d = buy(ctx, "custom_1")
    assert isinstance(d, Invalid)
    assert dump(ctx) == before


def test_selling_the_quest_item_twice_to_one_merchant_adds_up_the_holder_qty(registry, cfg):
    ctx = quest_ctx(registry, cfg, qty=2)
    sell(ctx, "custom_1")
    sell(ctx, "custom_1")
    assert holder(ctx).qty == 2
    assert holder(ctx).ref == "mara"


def test_buy_back_of_a_part_keeps_the_rest_with_the_holder(registry, cfg):
    ctx = quest_ctx(registry, cfg, qty=2)
    sell(ctx, "custom_1", 2)
    ctx.hero.money_cp = 1000
    d = buy(ctx, "custom_1")
    assert d.status == "accepted"
    assert holder(ctx).qty == 1
    assert holder(ctx).ref == "mara"
    assert count_item(ctx.hero, "custom_1") == 1


def test_buy_back_of_more_than_the_holder_has_is_clamped(registry, cfg):
    ctx = quest_ctx(registry, cfg, qty=2)
    sell(ctx, "custom_1", 2)
    ctx.hero.money_cp = 10000
    d = buy(ctx, "custom_1", 5)
    assert d.status == "clamped"
    assert d.result["qty"] == 2
    assert holder(ctx) is None
    assert stacks(ctx, "custom_1") == [(700, None, 2)]


def test_buy_back_is_clamped_by_money(registry, cfg):
    ctx = quest_ctx(registry, cfg, qty=3)
    sell(ctx, "custom_1", 3)
    ctx.hero.money_cp = 1500
    d = buy(ctx, "custom_1", 3)
    assert d.status == "clamped"
    assert d.result["qty"] == 2
    assert holder(ctx).qty == 1


def test_unknown_npc_message_lists_only_living_merchants_here(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    add_merchant(ctx, "dead_one", status="dead")
    add_merchant(ctx, "far_one", location_id="forest")
    d = buy(ctx, "arrows", npc_id="nobody")
    assert "mara" in d.message
    assert "dead_one" not in d.message
    assert "far_one" not in d.message


def test_not_sold_message_puts_the_stock_first_and_has_no_duplicates(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=100, quality="junk")]
    ctx = trade_ctx(registry, cfg, kind="smith", stock=stock)
    d = buy(ctx, "healers_kit")
    assert d.message.count("scimitar") == 1


def test_not_sold_message_includes_the_stock_outside_the_preset(registry, cfg):
    stock = [InventoryEntry(item_id="healers_kit", qty=1, cost_cp=100, quality="junk")]
    ctx = trade_ctx(registry, cfg, kind="smith", stock=stock)
    d = buy(ctx, "arrows")
    assert "healers_kit" in d.message


# добивание мутантов

def test_sell_unknown_item_is_invalid_with_the_id_list(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    before = dump(ctx)
    d = sell(ctx, "no_such_thing")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_item"
    assert "допустимые id" in d.message
    assert dump(ctx) == before


def test_sell_takes_the_dearest_stack_of_the_same_quality(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(100), scimitar(1000))
    sell(ctx, "scimitar")
    assert stacks(ctx, "scimitar") == [(100, None, 1)]


def test_sell_removes_the_chosen_quality_among_equal_prices(registry, cfg):
    ctx = trade_ctx(registry, cfg, money=0)
    hero_has(ctx, scimitar(1000, quality="junk"), scimitar(1000))
    sell(ctx, "scimitar", quality="new")
    assert stacks(ctx, "scimitar") == [(1000, "junk", 1)]
    assert stock_of(ctx) == [("scimitar", 1000, None, 1)]


def test_same_price_other_quality_is_a_separate_stock_entry(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    hero_has(ctx, scimitar(100), scimitar(100, quality="junk"))
    sell(ctx, "scimitar", quality="new")
    sell(ctx, "scimitar", quality="junk")
    assert sorted(stock_of(ctx), key=lambda s: s[2] or "") == [
        ("scimitar", 100, None, 1), ("scimitar", 100, "junk", 1),
    ]


def test_not_sold_list_of_a_magic_merchant_is_built_for_the_hero_level(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="alchemist")
    d = buy(ctx, "arrows")
    assert isinstance(d, Invalid)
    assert "potion_of_healing" in d.message


def test_buy_from_stock_filters_by_quality(registry, cfg):
    stock = [
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=100, quality="junk"),
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=300, quality="worn"),
    ]
    ctx = trade_ctx(registry, cfg, stock=stock)
    hero_has(ctx)
    d = buy(ctx, "scimitar", quality="worn")
    assert d.result["price_cp"] == 300
    assert stacks(ctx, "scimitar") == [(300, "worn", 1)]
    assert stock_of(ctx) == [("scimitar", 100, "junk", 1)]


def test_buy_from_stock_without_quality_takes_the_cheapest(registry, cfg):
    stock = [
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=300, quality="worn"),
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=100, quality="junk"),
    ]
    ctx = trade_ctx(registry, cfg, stock=stock)
    hero_has(ctx)
    d = buy(ctx, "scimitar")
    assert d.result["price_cp"] == 100
    assert stock_of(ctx) == [("scimitar", 300, "worn", 1)]


def test_buy_from_stock_of_a_too_rare_magic_item_is_rejected(registry, cfg):
    rare = registry.get("item", "potion_of_healing").model_copy(
        update={"id": "potion_rare", "rarity": "rare"}
    )
    stock = [InventoryEntry(item_id="potion_rare", qty=1, cost_cp=100)]
    ctx = trade_ctx(registry.with_items({"item": [rare]}), cfg, kind="alchemist", stock=stock)
    before = dump(ctx)
    d = buy(ctx, "potion_rare")
    assert d.status == "rejected"
    assert dump(ctx) == before


def test_buy_srd_item_with_quality_new_is_accepted(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    assert buy(ctx, "arrows", quality="new").status == "accepted"


def test_buy_srd_item_with_a_quality_that_the_merchant_lacks_is_not_sold(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    d = buy(ctx, "arrows", quality="junk")
    assert isinstance(d, Invalid)
    assert d.code == "not_sold"


def test_buy_one_coin_items_is_clamped_by_money(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=10, cost_cp=1, quality="junk")]
    ctx = trade_ctx(registry, cfg, stock=stock, money=3)
    d = buy(ctx, "scimitar", 5)
    assert d.status == "clamped"
    assert d.result["qty"] == 3
    assert ctx.hero.money_cp == 0


def test_buy_free_stock_item_does_not_divide_by_zero(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=3, cost_cp=0, quality="junk")]
    ctx = trade_ctx(registry, cfg, stock=stock, money=0)
    d = buy(ctx, "scimitar", 2)
    assert d.status == "accepted"
    assert d.result["total_cp"] == 0


def test_buy_from_a_big_stock_is_capped_by_give_item_max_qty(registry, cfg):
    stock = [InventoryEntry(item_id="scimitar", qty=50, cost_cp=1, quality="junk")]
    ctx = trade_ctx(registry, cfg, stock=stock, money=1000)
    d = buy(ctx, "scimitar", 50)
    assert d.status == "clamped"
    assert d.result["qty"] == cfg.limits.give_item_max_qty


# list: полный список категории, без сделки

def test_list_returns_all_items_of_the_category_with_prices(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    d = listing(ctx, "armor")
    assert d.status == "accepted"
    assert d.result["category"] == "armor"
    items = {i["item_id"]: i for i in d.result["items"]}
    assert "leather_armor" in items
    assert items["leather_armor"]["name"]
    assert items["leather_armor"]["price_cp"] == buy_quote(
        registry.get("armor", "leather_armor").cost_cp, 0, cfg
    )


def test_list_is_sorted_by_price(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    prices = [i["price_cp"] for i in listing(ctx, "armor").result["items"]]
    assert prices == sorted(prices)


def test_list_price_uses_the_attitude_step(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer", attitude=60)
    item = {i["item_id"]: i for i in listing(ctx, "armor").result["items"]}["leather_armor"]
    assert item["price_cp"] == buy_quote(registry.get("armor", "leather_armor").cost_cp, 60, cfg)


def test_list_unknown_category_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    d = listing(ctx, "no_such")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_category"


def test_list_category_outside_the_preset_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    d = listing(ctx, "weapon")
    assert isinstance(d, Invalid)
    assert "armor" in d.message


def test_list_does_not_spend_the_scene_limit_and_changes_nothing(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    before = dump(ctx)
    listing(ctx, "armor")
    assert ctx.scene.trades == 0
    assert dump(ctx) == before


def test_list_works_when_the_scene_limit_is_spent(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    ctx.scene.trades = cfg.trade.ops_per_scene
    assert listing(ctx, "armor").status == "accepted"


def test_list_from_a_non_merchant_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg)
    d = listing(ctx, "weapon", npc_id="grakh")
    assert isinstance(d, Invalid)


def test_list_during_combat_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    apply(ctx, combat_request())
    d = listing(ctx, "armor")
    assert isinstance(d, Invalid)
    assert d.code == "in_combat"


def test_list_from_a_dead_merchant_is_absent(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer", status="dead")
    d = listing(ctx, "armor")
    assert isinstance(d, Invalid)
    assert d.code in ("unknown_npc", "npc_absent")


def test_list_from_a_merchant_in_another_location_is_absent(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer", location_id="forest")
    d = listing(ctx, "armor")
    assert isinstance(d, Invalid)
    assert d.code == "npc_absent"


def test_list_empty_category_is_invalid(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer")
    d = listing(ctx, "")
    assert isinstance(d, Invalid)
    assert d.code == "unknown_category"


def test_list_from_a_hostile_merchant_is_rejected(registry, cfg):
    ctx = trade_ctx(registry, cfg, kind="armorer", attitude=-60)
    d = listing(ctx, "armor")
    assert d.status == "rejected"


def test_list_alchemist_category_has_magic_within_the_rarity_cap(registry, cfg):
    potion = registry.get("item", "potion_of_healing")
    rare = potion.model_copy(update={"id": "potion_rare", "rarity": "rare"})
    ctx = trade_ctx(registry.with_items({"item": [rare]}), cfg, kind="alchemist")
    d = listing(ctx, potion.category)
    assert d.status == "accepted"
    ids = [i["item_id"] for i in d.result["items"]]
    assert "potion_of_healing" in ids
    assert "potion_rare" not in ids
