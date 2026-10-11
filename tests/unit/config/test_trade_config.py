# Торговля, партия Т0 (TRADE-PLAN, разд. 1-3): секция [trade] конфига.
# Ожидаемый API: RulesConfig.trade: TradeConfig (extra="forbid"):
#   buy_factor = 1.0, sell_factor = 0.5, full_price_categories = ["valuable"],
#   ops_per_scene = 20, new_merchants_per_scene = 1,
#   presets: dict[str, TradePreset] -- general, smith, armorer, alchemist, fence;
#   TradePreset(categories: list[str], magic: bool = False, purse_cp: int, buys: list[str])
#   Валидатор: инвариант цен (см. ниже) -- ValidationError.
import pytest
from pydantic import ValidationError

from ai_dm.config.settings import load_rules_config


def trade():
    return load_rules_config().trade


# значения по умолчанию

def test_default_factors():
    cfg = trade()
    assert (cfg.buy_factor, cfg.sell_factor) == (1.0, 0.5)


def test_default_ops_per_scene():
    assert trade().ops_per_scene == 20


def test_default_new_merchants_per_scene():
    assert trade().new_merchants_per_scene == 1


def test_default_preset_kinds():
    assert set(trade().presets) == {"general", "smith", "armorer", "alchemist", "fence"}


def test_default_purses():
    presets = trade().presets
    assert presets["general"].purse_cp == 5000
    assert presets["smith"].purse_cp == 10000
    assert presets["fence"].purse_cp == 3000


def test_general_sells_gear_but_no_magic():
    general = trade().presets["general"]
    assert "gear" in general.categories
    assert general.magic is False


def test_smith_sells_weapons_and_armor_but_no_potions():
    smith = trade().presets["smith"]
    assert {"weapon", "armor"} <= set(smith.categories)
    assert "consumable" not in smith.categories


def test_presets_have_non_empty_buys():
    assert all(preset.buys for preset in trade().presets.values())


def test_magic_defaults_to_false_for_a_new_preset():
    toml = '[trade.presets.stall]\ncategories = ["gear"]\npurse_cp = 100\nbuys = ["gear"]\n'
    assert load_rules_config(toml_text=toml).trade.presets["stall"].magic is False


# переопределения

def test_override_sell_factor_keeps_the_rest():
    cfg = load_rules_config(toml_text="[trade]\nsell_factor = 0.4\n").trade
    assert (cfg.sell_factor, cfg.buy_factor, cfg.ops_per_scene) == (0.4, 1.0, 20)


def test_override_ops_per_scene():
    assert load_rules_config(toml_text="[trade]\nops_per_scene = 5\n").trade.ops_per_scene == 5


def test_override_one_preset_keeps_other_presets():
    cfg = load_rules_config(toml_text="[trade.presets.general]\npurse_cp = 1\n").trade
    assert cfg.presets["general"].purse_cp == 1
    assert cfg.presets["smith"].purse_cp == 10000


def test_override_preset_purse_keeps_its_categories():
    cfg = load_rules_config(toml_text="[trade.presets.general]\npurse_cp = 1\n").trade
    assert "gear" in cfg.presets["general"].categories


# валидатор

def test_sell_factor_above_buy_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nsell_factor = 1.5\n")


def test_sell_factor_just_above_buy_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nsell_factor = 1.01\n")


def test_lowering_buy_factor_under_sell_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nbuy_factor = 0.4\n")


def test_unknown_key_in_trade_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nsell_factorr = 0.5\n")


def test_unknown_key_in_preset_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade.presets.general]\nbogus = 1\n")


# отношение, пополнение, торг (Т5), потолок

def test_default_attitude_steps():
    cfg = trade()
    assert cfg.attitude_good_from == 50
    assert (cfg.attitude_good_buy_factor, cfg.attitude_good_sell_factor) == (0.9, 0.6)
    assert cfg.attitude_refuse_at == -50


def test_default_restock_days():
    assert trade().restock_days == 7


def test_default_haggle_percents():
    cfg = trade()
    assert (cfg.haggle_success_percent, cfg.haggle_strong_percent, cfg.haggle_fail_percent) == (
        -10, -20, 10,
    )


def test_default_price_mod_cap():
    assert trade().price_mod_cap_percent == 20


def test_alchemist_sells_magic_and_smith_does_not():
    presets = trade().presets
    assert presets["alchemist"].magic is True
    assert presets["smith"].magic is False


def test_fence_buys_valuables_and_smith_does_not():
    presets = trade().presets
    assert "valuable" in presets["fence"].buys
    assert "valuable" not in presets["smith"].buys


def test_armorer_deals_only_in_armor():
    armorer = trade().presets["armorer"]
    assert (armorer.categories, armorer.buys) == (["armor"], ["armor"])


def test_good_attitude_sell_factor_above_buy_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nattitude_good_sell_factor = 1.0\n")


def test_unknown_category_in_preset_is_error():
    toml = '[trade.presets.general]\ncategories = ["magic_wands"]\n'
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=toml)


def test_unknown_category_in_buys_is_error():
    toml = '[trade.presets.general]\nbuys = ["magic_wands"]\n'
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=toml)


def test_override_restock_days():
    assert load_rules_config(toml_text="[trade]\nrestock_days = 1\n").trade.restock_days == 1


def test_default_min_margin():
    assert trade().min_margin == 1.3


# инвариант цен: buy_factor * (100 - cap) / 100 >= max(sell, good_sell) * min_margin

# границы без плавающей ошибки: buy 1.0, cap 0, продажа 1.0, маржа 1.0 -- ровно равно
EDGE = (
    "[trade]\nbuy_factor = 1.0\nsell_factor = 1.0\nattitude_good_buy_factor = 1.0\n"
    "attitude_good_sell_factor = 1.0\nprice_mod_cap_percent = 0\nmin_margin = 1.0\n"
)


def test_invariant_exactly_equal_is_fine():
    assert load_rules_config(toml_text=EDGE).trade.min_margin == 1.0


def test_invariant_slightly_below_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=EDGE.replace("cap_percent = 0", "cap_percent = 1"))


def test_equal_buy_and_sell_with_default_margin_is_error():
    toml = "[trade]\nsell_factor = 1.0\nattitude_good_sell_factor = 1.0\n"
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=toml)


def test_higher_cap_breaks_the_invariant():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nprice_mod_cap_percent = 30\n")


def test_higher_margin_breaks_the_invariant():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nmin_margin = 1.4\n")


def test_lower_sell_factors_with_lower_buy_factor_is_fine():
    toml = (
        "[trade]\nbuy_factor = 0.8\nsell_factor = 0.3\nattitude_good_buy_factor = 0.7\n"
        "attitude_good_sell_factor = 0.4\n"
    )
    assert load_rules_config(toml_text=toml).trade.buy_factor == 0.8


def test_good_sell_factor_decides_when_it_is_the_best_sale():
    # продажа по хорошему отношению 0.7 * 1.3 = 0.91 > 0.8
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nattitude_good_sell_factor = 0.7\n")


def test_attitude_refuse_at_must_be_below_good_from():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nattitude_refuse_at = 50\n")


def test_attitude_refuse_at_just_below_good_from_is_fine():
    cfg = load_rules_config(toml_text="[trade]\nattitude_refuse_at = 49\n").trade
    assert cfg.attitude_refuse_at == 49


def test_good_sell_factor_below_sell_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nattitude_good_sell_factor = 0.4\n")


def test_good_sell_factor_equal_to_sell_factor_is_fine():
    toml = "[trade]\nattitude_good_sell_factor = 0.5\n"
    assert load_rules_config(toml_text=toml).trade.attitude_good_sell_factor == 0.5


def test_good_buy_factor_above_buy_factor_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nattitude_good_buy_factor = 1.1\n")


# ограничения полей

BAD_FIELDS = [
    ("buy_factor", 0), ("buy_factor", -1),
    ("sell_factor", -0.1),
    ("attitude_good_buy_factor", 0),
    ("attitude_good_sell_factor", -0.1),
    ("attitude_good_from", 101), ("attitude_good_from", -101),
    ("attitude_refuse_at", 101), ("attitude_refuse_at", -101),
    ("ops_per_scene", 0),
    ("new_merchants_per_scene", -1),
    ("restock_days", 0),
    ("price_mod_cap_percent", -1), ("price_mod_cap_percent", 100),
    ("min_margin", 0.99),
]


@pytest.mark.parametrize("name,value", BAD_FIELDS)
def test_out_of_range_field_is_error(name, value):
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=f"[trade]\n{name} = {value}\n")


def test_zero_new_merchants_is_fine():
    cfg = load_rules_config(toml_text="[trade]\nnew_merchants_per_scene = 0\n").trade
    assert cfg.new_merchants_per_scene == 0


def test_one_op_per_scene_is_fine():
    assert load_rules_config(toml_text="[trade]\nops_per_scene = 1\n").trade.ops_per_scene == 1


def test_zero_cap_is_fine():
    assert load_rules_config(toml_text="[trade]\nprice_mod_cap_percent = 0\n").trade


def test_cap_99_is_fine_with_zero_sell_factors():
    toml = (
        "[trade]\nprice_mod_cap_percent = 99\nsell_factor = 0\n"
        "attitude_good_sell_factor = 0\n"
    )
    assert load_rules_config(toml_text=toml).trade.price_mod_cap_percent == 99


def test_negative_preset_purse_is_error():
    toml = "[trade.presets.general]\npurse_cp = -1\n"
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=toml)


def test_zero_preset_purse_is_fine():
    toml = "[trade.presets.general]\npurse_cp = 0\n"
    assert load_rules_config(toml_text=toml).trade.presets["general"].purse_cp == 0


# торг Убеждением (партия Т5)


def test_default_haggle_numbers():
    cfg = trade()
    assert (cfg.haggle_dc, cfg.haggle_good_dc) == (15, 10)
    assert (cfg.haggle_strong_margin, cfg.haggle_hostile_below) == (5, 0)


def test_default_haggle_percents_in_t5():
    cfg = trade()
    assert (cfg.haggle_success_percent, cfg.haggle_strong_percent) == (-10, -20)
    assert cfg.haggle_fail_percent == 10


def test_override_haggle_dc_keeps_the_rest():
    cfg = load_rules_config(toml_text="[trade]\nhaggle_dc = 18\n").trade
    assert (cfg.haggle_dc, cfg.haggle_good_dc, cfg.haggle_strong_margin) == (18, 10, 5)


def test_positive_success_percent_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nhaggle_success_percent = 5\n")


def test_zero_success_percent_is_fine():
    assert load_rules_config(toml_text="[trade]\nhaggle_success_percent = 0\n").trade


def test_strong_above_success_is_error():
    toml = "[trade]\nhaggle_strong_percent = -5\nhaggle_success_percent = -10\n"
    with pytest.raises(ValidationError):
        load_rules_config(toml_text=toml)


def test_strong_equal_to_success_is_fine():
    toml = "[trade]\nhaggle_strong_percent = -10\nhaggle_success_percent = -10\n"
    assert load_rules_config(toml_text=toml).trade


def test_negative_fail_percent_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nhaggle_fail_percent = -5\n")


def test_zero_fail_percent_is_fine():
    assert load_rules_config(toml_text="[trade]\nhaggle_fail_percent = 0\n").trade


def test_zero_strong_margin_is_error():
    with pytest.raises(ValidationError):
        load_rules_config(toml_text="[trade]\nhaggle_strong_margin = 0\n")
