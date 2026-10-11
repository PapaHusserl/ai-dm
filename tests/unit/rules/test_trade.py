# Торговля, чистые функции (docs/TRADE-PLAN.md, разд. 2, партия Т1).
#   Т5 (торг): day_of, active_haggle, can_haggle, haggle_dc, haggle_mode, haggle_percent_for,
#       buy_factor_total, buy_quote(..., haggle=0), merchant_buy_quote, apply_haggle.
#   item_category(kind, model) -- weapon/armor; item: ammo_for -> ammo,
#       category "" -> gear, quest -> None.
#   merchant_sells / merchant_buys -- категория в пресете, цена > 0,
#       магия только при preset.magic и в пределе редкости.
#   refuses(attitude, cfg) -- attitude <= attitude_refuse_at.
#   buy_quote -- ceil(цена * buy_factor), sell_quote -- floor(цена * sell_factor);
#       при attitude >= attitude_good_from коэффициенты attitude_good_*.
#   assortment(registry, preset, level, cfg) -> [(id, цена)]: weapon, armor, item; внутри по id.
#   restock(profile, now_s, cfg) -> bool: при now_s >= restock_at_s кошелёк полный,
#       срок + restock_days суток.
from fractions import Fraction

import pytest

from ai_dm.content.models.items import Armor, Item, Weapon
from ai_dm.content.registry import ContentRegistry
from ai_dm.rules.trade import (
    DAY_S,
    active_haggle,
    apply_haggle,
    assortment,
    buy_factor,
    buy_factor_total,
    buy_quote,
    can_haggle,
    day_of,
    haggle_dc,
    haggle_mode,
    haggle_percent_for,
    item_category,
    merchant_buy_quote,
    merchant_buys,
    merchant_sells,
    purse_now,
    refuses,
    restock,
    sell_factor,
    sell_quote,
)
from ai_dm.state.hero import InventoryEntry
from ai_dm.state.world import NPC, TradeProfile


def make_weapon(id, cost_cp=1500):
    return Weapon(
        id=id,
        name=id,
        category="martial",
        kind="melee",
        damage_dice="1d8",
        damage_type="slashing",
        cost_cp=cost_cp,
    )


def make_armor(id, cost_cp=5000):
    return Armor(id=id, name=id, category="light", ac=11, cost_cp=cost_cp)


def make_item(id, cost_cp=100, **kwargs):
    return Item(id=id, name=id, cost_cp=cost_cp, **kwargs)


def make_registry():
    return ContentRegistry(
        {
            "weapon": {"longsword": make_weapon("longsword"), "dagger": make_weapon("dagger", 200)},
            "armor": {"leather": make_armor("leather")},
            "item": {
                "rope": make_item("rope"),
                "bread": make_item("bread", 5, category="consumable"),
                "cloak": make_item("cloak", 50, category="clothing"),
                "arrow": make_item("arrow", 5, ammo_for=["longbow"]),
                "ruby": make_item("ruby", 5000, category="valuable"),
                "relic": make_item("relic", 100, category="quest"),
                "free_rope": make_item("free_rope", 0),
                "potion_common": make_item(
                    "potion_common", 5000, category="consumable", magic=True, rarity="common"
                ),
                "potion_uncommon": make_item(
                    "potion_uncommon", 8000, category="consumable", magic=True, rarity="uncommon"
                ),
                "potion_rare": make_item(
                    "potion_rare", 90000, category="consumable", magic=True, rarity="rare"
                ),
            },
        }
    )


def with_trade(cfg, **update):
    return cfg.model_copy(update={"trade": cfg.trade.model_copy(update=update)})


def preset(cfg, kind):
    return cfg.trade.presets[kind]


def ids(pairs):
    return [item_id for item_id, _ in pairs]


# item_category


def test_weapon_category():
    assert item_category("weapon", make_weapon("w")) == "weapon"


def test_armor_category():
    assert item_category("armor", make_armor("a")) == "armor"


def test_ammo_category_wins_over_gear():
    assert item_category("item", make_item("a", ammo_for=["longbow"])) == "ammo"


def test_empty_category_is_gear():
    assert item_category("item", make_item("a")) == "gear"


@pytest.mark.parametrize("category", ["consumable", "clothing", "gear", "valuable"])
def test_item_category_as_is(category):
    assert item_category("item", make_item("a", category=category)) == category


def test_quest_category_is_none():
    assert item_category("item", make_item("a", category="quest")) is None


# merchant_sells


def test_general_sells_rope(cfg):
    assert merchant_sells("item", make_item("rope"), preset(cfg, "general"), 1, cfg)


def test_general_does_not_sell_weapon(cfg):
    assert not merchant_sells("weapon", make_weapon("w"), preset(cfg, "general"), 1, cfg)


def test_smith_sells_weapon_and_armor(cfg):
    assert merchant_sells("weapon", make_weapon("w"), preset(cfg, "smith"), 1, cfg)
    assert merchant_sells("armor", make_armor("a"), preset(cfg, "smith"), 1, cfg)


def test_smith_does_not_sell_potion(cfg):
    assert not merchant_sells(
        "item", make_item("p", category="consumable"), preset(cfg, "smith"), 1, cfg
    )


def test_zero_cost_not_sold(cfg):
    assert not merchant_sells("item", make_item("rope", 0), preset(cfg, "general"), 1, cfg)


def test_cost_one_is_sold(cfg):
    assert merchant_sells("item", make_item("rope", 1), preset(cfg, "general"), 1, cfg)


def test_quest_item_not_sold(cfg):
    assert not merchant_sells(
        "item", make_item("q", category="quest"), preset(cfg, "general"), 1, cfg
    )


def test_magic_not_sold_when_preset_not_magic(cfg):
    potion = make_item("p", category="consumable", magic=True, rarity="common")
    assert not merchant_sells("item", potion, preset(cfg, "general"), 1, cfg)


def test_magic_sold_when_preset_magic(cfg):
    potion = make_item("p", category="consumable", magic=True, rarity="common")
    assert merchant_sells("item", potion, preset(cfg, "alchemist"), 1, cfg)


def test_magic_at_rarity_cap_is_sold(cfg):
    potion = make_item("p", category="consumable", magic=True, rarity="uncommon")
    assert merchant_sells("item", potion, preset(cfg, "alchemist"), 1, cfg)


def test_magic_above_rarity_cap_not_sold(cfg):
    potion = make_item("p", category="consumable", magic=True, rarity="rare")
    assert not merchant_sells("item", potion, preset(cfg, "alchemist"), 1, cfg)


def test_magic_rare_sold_at_level_five(cfg):
    potion = make_item("p", category="consumable", magic=True, rarity="rare")
    assert merchant_sells("item", potion, preset(cfg, "alchemist"), 5, cfg)


def test_magic_without_rarity_sold_by_magic_preset(cfg):
    potion = make_item("p", category="consumable", magic=True)
    assert merchant_sells("item", potion, preset(cfg, "alchemist"), 1, cfg)


def test_fence_sells_valuable(cfg):
    assert merchant_sells(
        "item", make_item("ruby", 5000, category="valuable"), preset(cfg, "fence"), 1, cfg
    )


# merchant_buys


def test_general_buys_weapon(cfg):
    assert merchant_buys("weapon", make_weapon("w"), preset(cfg, "general"))


def test_general_does_not_buy_valuable(cfg):
    assert not merchant_buys(
        "item", make_item("ruby", 5000, category="valuable"), preset(cfg, "general")
    )


def test_fence_buys_valuable(cfg):
    assert merchant_buys("item", make_item("ruby", 5000, category="valuable"), preset(cfg, "fence"))


def test_armorer_buys_only_armor(cfg):
    assert merchant_buys("armor", make_armor("a"), preset(cfg, "armorer"))
    assert not merchant_buys("weapon", make_weapon("w"), preset(cfg, "armorer"))


def test_nobody_buys_quest_item(cfg):
    assert not merchant_buys("item", make_item("q", category="quest"), preset(cfg, "fence"))


def test_buys_zero_cost_item_by_category(cfg):
    # цену 0 отсекает sell_quote, не merchant_buys
    assert merchant_buys("item", make_item("rope", 0), preset(cfg, "general"))


# refuses / factors (пороги)


def test_refuses_exactly_at_threshold(cfg):
    assert refuses(-50, cfg)


def test_does_not_refuse_just_above_threshold(cfg):
    assert not refuses(-49, cfg)


def test_refuses_below_threshold(cfg):
    assert refuses(-60, cfg)


def test_refuses_follows_config(cfg):
    assert refuses(-20, with_trade(cfg, attitude_refuse_at=-20))
    assert not refuses(-19, with_trade(cfg, attitude_refuse_at=-20))


def test_good_factors_exactly_at_threshold(cfg):
    assert buy_factor(50, cfg) == 0.9
    assert sell_factor(50, cfg) == 0.6


def test_base_factors_just_below_threshold(cfg):
    assert buy_factor(49, cfg) == 1.0
    assert sell_factor(49, cfg) == 0.5


def test_base_factors_at_zero(cfg):
    assert buy_factor(0, cfg) == 1.0
    assert sell_factor(0, cfg) == 0.5


def test_good_threshold_follows_config(cfg):
    other = with_trade(cfg, attitude_good_from=30)
    assert buy_factor(30, other) == 0.9
    assert buy_factor(29, other) == 1.0


# quotes


def test_buy_longsword_full_price(cfg):
    assert buy_quote(1500, 0, cfg) == 1500


def test_sell_longsword_half(cfg):
    assert sell_quote(1500, 0, cfg) == 750


def test_sell_worn_scimitar_half(cfg):
    assert sell_quote(100, 0, cfg) == 50


def test_sell_valuable_half(cfg):
    assert sell_quote(5000, 0, cfg) == 2500


def test_sell_cost_one_is_worth_nothing(cfg):
    assert sell_quote(1, 0, cfg) == 0


def test_sell_cost_three_rounds_down(cfg):
    assert sell_quote(3, 0, cfg) == 1


def test_sell_cost_zero_is_zero(cfg):
    assert sell_quote(0, 0, cfg) == 0


def test_buy_cost_one_is_one(cfg):
    assert buy_quote(1, 0, cfg) == 1


def test_good_attitude_buy_rounds_up(cfg):
    assert buy_quote(15, 60, cfg) == 14


def test_good_attitude_buy_exact(cfg):
    assert buy_quote(1500, 60, cfg) == 1350


def test_good_attitude_buy_cost_one(cfg):
    assert buy_quote(1, 60, cfg) == 1


def test_good_attitude_sell(cfg):
    assert sell_quote(1500, 60, cfg) == 900


def test_good_attitude_sell_rounds_down(cfg):
    assert sell_quote(5, 60, cfg) == 3
    assert sell_quote(4, 60, cfg) == 2


def test_attitude_49_uses_base_quotes(cfg):
    assert buy_quote(15, 49, cfg) == 15
    assert sell_quote(1500, 49, cfg) == 750


def test_attitude_50_uses_good_quotes(cfg):
    assert buy_quote(1500, 50, cfg) == 1350
    assert sell_quote(1500, 50, cfg) == 900


def test_buy_quote_has_no_float_error(cfg):
    # 110 * 0.9 в float даёт 99.00000000000001 -> ceil 100
    assert buy_quote(110, 60, cfg) == 99


def test_quotes_match_integer_math(cfg):
    for cost in range(0, 2001):
        assert buy_quote(cost, 0, cfg) == cost
        assert sell_quote(cost, 0, cfg) == cost // 2
        assert buy_quote(cost, 60, cfg) == -((-cost * 9) // 10)
        assert sell_quote(cost, 60, cfg) == cost * 6 // 10


def test_quote_uses_config_factors(cfg):
    other = with_trade(cfg, buy_factor=1.25, sell_factor=0.4)
    assert buy_quote(10, 0, other) == 13
    assert sell_quote(10, 0, other) == 4


def test_sell_never_exceeds_buy_at_same_attitude(cfg):
    for attitude in (0, 60):
        for cost in range(1, 2001):
            assert sell_quote(cost, attitude, cfg) <= buy_quote(cost, attitude, cfg)


def test_no_arbitrage_best_sell_vs_best_buy(cfg):
    # лучшая продажа (хорошее отношение) не выше самой дешёвой покупки с максимальной скидкой 20%
    for cost in range(1, 2001):
        cheapest = buy_quote(cost, 0, cfg) * (100 - cfg.trade.price_mod_cap_percent) / 100
        assert sell_quote(cost, 60, cfg) * cfg.trade.min_margin <= cheapest + 1


# assortment


def test_general_assortment_has_rope_and_no_magic(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "general"), 1, cfg))
    assert "rope" in result
    assert "potion_common" not in result
    assert "potion_rare" not in result


def test_general_assortment_categories(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "general"), 1, cfg))
    assert result == ["arrow", "bread", "cloak", "rope"]


def test_smith_assortment(cfg):
    result = assortment(make_registry(), preset(cfg, "smith"), 1, cfg)
    assert result == [("dagger", 200), ("longsword", 1500), ("leather", 5000), ("arrow", 5)]


def test_smith_has_no_potions(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "smith"), 1, cfg))
    assert "potion_common" not in result


def test_alchemist_assortment_level_one(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "alchemist"), 1, cfg))
    assert result == ["bread", "potion_common", "potion_uncommon"]


def test_alchemist_assortment_level_five_has_rare(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "alchemist"), 5, cfg))
    assert result == ["bread", "potion_common", "potion_rare", "potion_uncommon"]


def test_fence_assortment_has_valuable_not_quest(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "fence"), 1, cfg))
    assert result == ["rope", "ruby"]


def test_assortment_skips_zero_cost(cfg):
    result = ids(assortment(make_registry(), preset(cfg, "general"), 1, cfg))
    assert "free_rope" not in result


def test_assortment_price_ignores_attitude_uses_buy_factor(cfg):
    other = with_trade(cfg, buy_factor=1.5, attitude_good_buy_factor=1.0)
    assert ("rope", 150) in assortment(make_registry(), preset(other, "general"), 1, other)


def test_assortment_price_rounds_up(cfg):
    other = with_trade(cfg, buy_factor=1.5)
    assert ("bread", 8) in assortment(make_registry(), preset(other, "general"), 1, other)


def test_assortment_real_registry_smith(cfg, registry):
    result = dict(assortment(registry, preset(cfg, "smith"), 1, cfg))
    assert result["longsword"] == 1500
    assert "potion_of_healing" not in result


def test_assortment_real_registry_general_has_no_magic(cfg, registry):
    result = ids(assortment(registry, preset(cfg, "general"), 1, cfg))
    assert "potion_of_healing" not in result
    assert result


def test_assortment_real_registry_alchemist_sells_potion(cfg, registry):
    result = dict(assortment(registry, preset(cfg, "alchemist"), 1, cfg))
    assert result["potion_of_healing"] == 5000


# restock


def make_profile(**kwargs):
    return TradeProfile(kind="general", purse_cp=10, restock_at_s=1000, **kwargs)


def test_restock_before_time_keeps_purse(cfg):
    profile = make_profile()
    assert restock(profile, 999, cfg) is False
    assert profile.purse_cp == 10
    assert profile.restock_at_s == 1000


def test_restock_exactly_at_time_refills(cfg):
    profile = make_profile()
    assert restock(profile, 1000, cfg) is True
    assert profile.purse_cp == 5000
    assert profile.restock_at_s == 1000 + 7 * DAY_S


def test_restock_after_time_shifts_from_now(cfg):
    profile = make_profile()
    assert restock(profile, 5000, cfg) is True
    assert profile.restock_at_s == 5000 + 7 * DAY_S


def test_restock_second_call_does_nothing(cfg):
    profile = make_profile()
    restock(profile, 1000, cfg)
    profile.purse_cp = 1
    assert restock(profile, 1001, cfg) is False
    assert profile.purse_cp == 1


def test_restock_uses_preset_purse(cfg):
    profile = TradeProfile(kind="smith", purse_cp=0, restock_at_s=0)
    restock(profile, 0, cfg)
    assert profile.purse_cp == 10000


def test_restock_new_profile_refills_at_zero(cfg):
    profile = TradeProfile(kind="fence")
    assert restock(profile, 0, cfg) is True
    assert profile.purse_cp == 3000


def test_restock_days_follow_config(cfg):
    profile = make_profile()
    restock(profile, 1000, with_trade(cfg, restock_days=3))
    assert profile.restock_at_s == 1000 + 3 * DAY_S


def test_restock_keeps_stock(cfg):
    profile = make_profile(stock=[InventoryEntry(item_id="longsword", qty=2, cost_cp=1500)])
    restock(profile, 1000, cfg)
    assert profile.stock == [InventoryEntry(item_id="longsword", qty=2, cost_cp=1500)]


def test_restock_unknown_kind_raises(cfg):
    profile = TradeProfile(kind="nope", restock_at_s=0)
    with pytest.raises(KeyError):
        restock(profile, 0, cfg)


def test_day_is_86400():
    assert DAY_S == 86400


def test_purse_now_before_restock_is_current_purse(cfg):
    profile = TradeProfile(kind="general", purse_cp=10, restock_at_s=1000)
    assert purse_now(profile, 999, cfg) == 10


def test_purse_now_at_restock_time_is_full_preset_purse(cfg):
    profile = TradeProfile(kind="general", purse_cp=10, restock_at_s=1000)
    assert purse_now(profile, 1000, cfg) == cfg.trade.presets["general"].purse_cp


def test_purse_now_uses_the_kind_preset(cfg):
    profile = TradeProfile(kind="smith", purse_cp=10, restock_at_s=0)
    assert purse_now(profile, 5, cfg) == cfg.trade.presets["smith"].purse_cp


def test_purse_now_does_not_change_the_profile(cfg):
    profile = TradeProfile(kind="general", purse_cp=10, restock_at_s=0)
    purse_now(profile, 5, cfg)
    assert (profile.purse_cp, profile.restock_at_s) == (10, 0)


# торг Убеждением (партия Т5)


def haggled(**kwargs):
    return TradeProfile(kind="general", purse_cp=10, restock_at_s=0, **kwargs)


def npc_with(attitude, trade):
    return NPC(id="mara", name="Mara", means=["товары"], attitude=attitude, trade=trade)


def test_day_of_zero():
    assert day_of(0) == 0


def test_day_of_last_second_of_day():
    assert day_of(86399) == 0


def test_day_of_next_day_starts_at_86400():
    assert day_of(86400) == 1


def test_active_haggle_same_day():
    assert active_haggle(haggled(haggle_percent=-10, haggle_day=3), 3 * DAY_S + 5) == -10


def test_active_haggle_next_day_is_zero():
    assert active_haggle(haggled(haggle_percent=-10, haggle_day=3), 4 * DAY_S) == 0


def test_active_haggle_without_day_is_zero():
    assert active_haggle(haggled(haggle_percent=-10, haggle_day=None), 100) == 0


def test_active_haggle_day_zero_is_valid():
    assert active_haggle(haggled(haggle_percent=-10, haggle_day=0), 100) == -10


def test_can_haggle_without_day():
    assert can_haggle(haggled(), 100) is True


def test_cannot_haggle_twice_in_a_day():
    assert can_haggle(haggled(haggle_percent=-10, haggle_day=0), 100) is False


def test_can_haggle_after_a_day():
    assert can_haggle(haggled(haggle_percent=-10, haggle_day=0), DAY_S) is True


def test_haggle_dc_indifferent(cfg):
    assert haggle_dc(0, cfg) == 15


def test_haggle_dc_just_below_good(cfg):
    assert haggle_dc(49, cfg) == 15


def test_haggle_dc_good_attitude(cfg):
    assert haggle_dc(50, cfg) == 10


def test_haggle_dc_follows_config(cfg):
    other = with_trade(cfg, haggle_dc=18, haggle_good_dc=7)
    assert (haggle_dc(0, other), haggle_dc(50, other)) == (18, 7)


def test_haggle_mode_normal_at_zero(cfg):
    assert haggle_mode(0, cfg) == "normal"


def test_haggle_mode_disadvantage_below_zero(cfg):
    assert haggle_mode(-1, cfg) == "disadvantage"


def test_haggle_mode_follows_config(cfg):
    other = with_trade(cfg, haggle_hostile_below=20)
    assert (haggle_mode(19, other), haggle_mode(20, other)) == ("disadvantage", "normal")


def test_haggle_percent_success_exactly_dc(cfg):
    assert haggle_percent_for("success", 15, 15, cfg) == -10


def test_haggle_percent_success_just_below_strong(cfg):
    assert haggle_percent_for("success", 19, 15, cfg) == -10


def test_haggle_percent_strong_at_margin(cfg):
    assert haggle_percent_for("success", 20, 15, cfg) == -20


def test_haggle_percent_fail(cfg):
    assert haggle_percent_for("fail", 14, 15, cfg) == 10


def test_haggle_percent_fail_ignores_total(cfg):
    assert haggle_percent_for("fail", 99, 15, cfg) == 10


def test_haggle_percent_follows_config(cfg):
    other = with_trade(cfg, haggle_strong_margin=2, haggle_success_percent=-5)
    assert haggle_percent_for("success", 17, 15, other) == -20
    assert haggle_percent_for("success", 16, 15, other) == -5


def test_buy_quote_default_haggle_changes_nothing(cfg):
    for attitude in (0, 60):
        for cost in (1, 7, 100, 1500):
            assert buy_quote(cost, attitude, cfg, 0) == buy_quote(cost, attitude, cfg)


def test_buy_quote_without_haggle_keeps_t1_numbers(cfg):
    assert buy_quote(1500, 0, cfg) == 1500
    assert buy_quote(10, 60, cfg) == 9


def test_buy_factor_total_is_exact_fraction(cfg):
    assert buy_factor_total(0, -10, cfg) == Fraction(9, 10)


def test_buy_factor_total_without_haggle_is_buy_factor(cfg):
    assert buy_factor_total(0, 0, cfg) == Fraction(1)
    assert buy_factor_total(60, 0, cfg) == Fraction(9, 10)


def test_haggle_success_makes_buying_10_percent_cheaper(cfg):
    assert buy_quote(1000, 0, cfg, -10) == 900


def test_haggle_strong_makes_buying_20_percent_cheaper(cfg):
    assert buy_quote(1000, 0, cfg, -20) == 800


def test_haggle_fail_makes_buying_10_percent_dearer(cfg):
    assert buy_quote(1000, 0, cfg, 10) == 1100


def test_good_attitude_with_strong_haggle_is_clamped_to_cap(cfg):
    assert buy_quote(1000, 60, cfg, -20) == 800


def test_good_attitude_with_strong_haggle_factor_is_not_072(cfg):
    assert buy_factor_total(60, -20, cfg) == Fraction(4, 5)


def test_good_attitude_with_success_haggle(cfg):
    assert buy_quote(1000, 60, cfg, -10) == 810


def test_good_attitude_with_fail_haggle(cfg):
    assert buy_quote(1000, 60, cfg, 10) == 990


def test_haggle_buy_quote_rounds_up(cfg):
    assert buy_quote(7, 0, cfg, -10) == 7


def test_haggle_buy_quote_rounds_up_exact_boundary(cfg):
    assert buy_quote(10, 0, cfg, -10) == 9


def test_haggle_upper_clamp_follows_cap(cfg):
    other = with_trade(cfg, price_mod_cap_percent=5)
    assert buy_quote(1000, 0, other, 10) == 1050


def test_haggle_lower_clamp_follows_cap(cfg):
    other = with_trade(cfg, price_mod_cap_percent=5)
    assert buy_quote(1000, 0, other, -20) == 950


def test_haggle_inside_cap_is_not_clamped(cfg):
    other = with_trade(cfg, price_mod_cap_percent=50)
    assert buy_quote(1000, 0, other, -20) == 800


def test_good_attitude_below_cap_without_haggle_is_clamped(cfg):
    # потолок суммарной скидки действует и без торга, если конфиг вышел за него
    other = with_trade(cfg, attitude_good_buy_factor=0.7, price_mod_cap_percent=20)
    assert buy_quote(1000, 60, other, 0) == 800


def test_haggled_buy_never_below_best_sell_margin(cfg):
    for attitude in (-49, 0, 49, 50, 100):
        for haggle in (-20, -10, 0, 10):
            for cost in range(1, 501):
                buy = buy_quote(cost, attitude, cfg, haggle)
                for other in (-49, 0, 49, 50, 100):
                    assert buy >= sell_quote(cost, other, cfg) * cfg.trade.min_margin


def test_haggle_does_not_change_sell_quote(cfg):
    assert sell_quote(1000, 0, cfg) == 500


def test_merchant_buy_quote_without_haggle(cfg):
    npc = npc_with(0, haggled())
    assert merchant_buy_quote(1000, npc, 100, cfg) == 1000


def test_merchant_buy_quote_with_active_haggle(cfg):
    npc = npc_with(0, haggled(haggle_percent=-10, haggle_day=0))
    assert merchant_buy_quote(1000, npc, 100, cfg) == 900


def test_merchant_buy_quote_ignores_old_haggle(cfg):
    npc = npc_with(0, haggled(haggle_percent=-10, haggle_day=0))
    assert merchant_buy_quote(1000, npc, DAY_S, cfg) == 1000


def test_merchant_buy_quote_uses_attitude(cfg):
    npc = npc_with(60, haggled(haggle_percent=-10, haggle_day=0))
    assert merchant_buy_quote(1000, npc, 100, cfg) == 810


def test_apply_haggle_writes_percent_and_day():
    profile = haggled()
    apply_haggle(profile, -20, 2 * DAY_S + 7)
    assert (profile.haggle_percent, profile.haggle_day) == (-20, 2)


def test_apply_haggle_at_day_zero_sets_day_zero():
    profile = haggled()
    apply_haggle(profile, 10, 5)
    assert profile.haggle_day == 0
