from fractions import Fraction
from math import ceil, floor

from ai_dm.rules.loot import rarity_exceeds_cap

DAY_S = 86400


def item_category(kind, model):
    # категория торговли; None -- не торгуется (сюжетные); снаряжение без категории -- gear
    if kind in ("weapon", "armor"):
        return kind
    if model.ammo_for:
        return "ammo"
    if model.category == "":
        return "gear"
    if model.category == "quest":
        return None
    return model.category


def merchant_sells(kind, model, preset, level, cfg) -> bool:
    category = item_category(kind, model)
    if category is None or category not in preset.categories:
        return False
    if model.cost_cp <= 0:
        return False
    if kind == "item" and model.magic:
        return preset.magic and not rarity_exceeds_cap(model, level, cfg)
    return True


def merchant_buys(kind, model, preset) -> bool:
    category = item_category(kind, model)
    return category is not None and category in preset.buys


def refuses(attitude, cfg) -> bool:
    return attitude <= cfg.trade.attitude_refuse_at


def buy_factor(attitude, cfg) -> float:
    if attitude >= cfg.trade.attitude_good_from:
        return cfg.trade.attitude_good_buy_factor
    return cfg.trade.buy_factor


def sell_factor(attitude, cfg) -> float:
    if attitude >= cfg.trade.attitude_good_from:
        return cfg.trade.attitude_good_sell_factor
    return cfg.trade.sell_factor


def day_of(now_s) -> int:
    return now_s // DAY_S


def active_haggle(profile, now_s) -> int:
    # поправка торга, если торговались сегодня; на следующий день гаснет сама
    if profile.haggle_day == day_of(now_s):
        return profile.haggle_percent
    return 0


def can_haggle(profile, now_s) -> bool:
    return profile.haggle_day != day_of(now_s)


def haggle_state(profile, now_s) -> dict:
    # для контекста мастера: ключ haggle только если сегодня уже торговались
    if can_haggle(profile, now_s):
        return {}
    return {"haggle": {"percent": active_haggle(profile, now_s)}}


def haggle_dc(attitude, cfg) -> int:
    if attitude >= cfg.trade.attitude_good_from:
        return cfg.trade.haggle_good_dc
    return cfg.trade.haggle_dc


def haggle_mode(attitude, cfg) -> str:
    if attitude < cfg.trade.haggle_hostile_below:
        return "disadvantage"
    return "normal"


def haggle_percent_for(outcome, total, dc, cfg) -> int:
    if outcome == "success" and total >= dc + cfg.trade.haggle_strong_margin:
        return cfg.trade.haggle_strong_percent
    if outcome == "success":
        return cfg.trade.haggle_success_percent
    return cfg.trade.haggle_fail_percent


def buy_factor_total(attitude, haggle, cfg) -> Fraction:
    # отношение и торг складываются по коэффициентам; итог в пределах потолка суммарной поправки
    base = Fraction(str(buy_factor(attitude, cfg)))
    wide = Fraction(str(cfg.trade.buy_factor))
    cap = cfg.trade.price_mod_cap_percent
    total = base * (100 + haggle) / 100
    return max(wide * (100 - cap) / 100, min(wide * (100 + cap) / 100, total))


def buy_quote(cost_cp, attitude, cfg, haggle=0) -> int:
    # цена покупки героем за штуку, округление вверх (в пользу торговца)
    return ceil(cost_cp * buy_factor_total(attitude, haggle, cfg))


def merchant_buy_quote(cost_cp, npc, now_s, cfg) -> int:
    return buy_quote(cost_cp, npc.attitude, cfg, active_haggle(npc.trade, now_s))


def apply_haggle(profile, percent, now_s) -> None:
    profile.haggle_percent = percent
    profile.haggle_day = day_of(now_s)


def sell_quote(cost_cp, attitude, cfg) -> int:
    # цена продажи героем за штуку, округление вниз; 0 -- ничего не стоит
    return floor(cost_cp * Fraction(str(sell_factor(attitude, cfg))))


def assortment(registry, preset, level, cfg) -> list:
    result = []
    for kind in ("weapon", "armor", "item"):
        for model in registry.all(kind):
            if merchant_sells(kind, model, preset, level, cfg):
                result.append((model.id, ceil(model.cost_cp * Fraction(str(cfg.trade.buy_factor)))))
    return result


def category_models(registry, preset, level, cfg) -> dict:
    # что торговец продаёт по категориям: {категория: [модели]}
    result = {}
    for kind in ("weapon", "armor", "item"):
        for model in registry.all(kind):
            if merchant_sells(kind, model, preset, level, cfg):
                result.setdefault(item_category(kind, model), []).append(model)
    return result


def purse_now(profile, now_s, cfg) -> int:
    # кошелёк с учётом ленивого пополнения, без изменения состояния
    if now_s >= profile.restock_at_s:
        return cfg.trade.presets[profile.kind].purse_cp
    return profile.purse_cp


def restock(profile, now_s, cfg) -> bool:
    # ленивое пополнение кошелька при обращении; stock не чистится
    if now_s < profile.restock_at_s:
        return False
    profile.purse_cp = cfg.trade.presets[profile.kind].purse_cp
    profile.restock_at_s = now_s + cfg.trade.restock_days * DAY_S
    return True
