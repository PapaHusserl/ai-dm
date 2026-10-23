from ai_dm.game.scene import hero_of
from ai_dm.game.sheet_text import effect_texts
from ai_dm.game.shop_text import UNIT_WORDS, sale_rows, sell_rows
from ai_dm.rules.inventory import find_item
from ai_dm.rules.money import format_cp
from ai_dm.rules.npc_names import shown_name
from ai_dm.rules.services import kinds_of, quote
from ai_dm.ui.tui import strings
from ai_dm.ui.tui.inv_sections import inv_section


def shop_action(hint, template, echo, cap):
    # действие строки /shop: команда с {qty}, эхо и потолок количества (0 -- денег не хватает)
    return ("Enter", hint, template, echo, cap)


def priced(name, qty, price):
    return f"{name} x{qty} — {format_cp(price)}" if qty > 1 else f"{name} — {format_cp(price)}"


def description_of(item):
    return item.description or effect_texts(getattr(item, "effects", []))


def goods_rows(game, npc, cap_of):
    # купить: товары торговца; потолок -- кошелёк героя и запас стека (qty 0 -- без запаса)
    hero = hero_of(game.bundle)
    registry = game.registry
    cfg = game.settings.rules
    who = shown_name(npc)
    rows = []
    goods = sale_rows(npc, game.bundle.world, registry, hero.sheet.level, cfg)
    for _, name, price, qty, _, item_id, quality in sorted(goods, key=lambda r: (r[0], r[1])):
        found = find_item(registry, item_id)
        cap = min(cap_of(price), qty) if qty > 0 else cap_of(price)
        template = f"/shop купить {npc.id} {item_id} {{qty}}" + (f" {quality}" if quality else "")
        echo = strings.SHOP_ECHO.format(verb=strings.SHOP_BUY, name=name, npc=who)
        action = shop_action(strings.SHOP_BUY, template, echo, cap)
        label = priced(name, qty, price)
        rows.append((label, description_of(found[1]), [action], inv_section(found, [])))
    return rows


def sell_tab_rows(game, npc):
    # продать: что герой может отдать торговцу; потолок -- свободные экземпляры
    registry = game.registry
    cfg = game.settings.rules
    limit = cfg.limits.give_item_max_qty
    rows = []
    for item_id, name, price, free in sell_rows(
        hero_of(game.bundle), game.bundle.world, registry, npc, cfg
    ):
        template = f"/shop продать {npc.id} {item_id} {{qty}}"
        echo = strings.SHOP_ECHO.format(verb=strings.SHOP_SELL, name=name, npc=shown_name(npc))
        action = shop_action(strings.SHOP_SELL, template, echo, min(free, limit))
        description = description_of(find_item(registry, item_id)[1])
        rows.append((priced(name, free, price), description, [action], strings.SHOP_SELL_TAB))
    return rows


def service_rows(game, npc, cap_of):
    world = game.bundle.world
    cfg = game.settings.rules
    rows = []
    for kind_id, kind in kinds_of(npc, cfg):
        price = quote(kind, npc, world, cfg)
        label = f"{kind.name} — {format_cp(price)} / {UNIT_WORDS[kind.unit]}"
        template = f"/shop услуга {npc.id} {kind_id} {{qty}}"
        echo = strings.SHOP_ECHO.format(
            verb=strings.SHOP_SERVICE, name=kind.name, npc=shown_name(npc)
        )
        # комната снимается на одну ночь, обряд снятия -- один раз
        cap = 1 if kind.effect in ("lodging", "cure") else cap_of(price)
        action = shop_action(strings.SHOP_SERVICE, template, echo, cap)
        rows.append((label, kind.description, [action], strings.SHOP_SERVICE_TAB))
    return rows


def shop_rows(game, npc):
    # строки окна /shop: (подпись, описание, [действие], вкладка); покупка, продажа и услуги --
    # подкоманды /shop, второго пути нет
    hero = hero_of(game.bundle)
    limit = game.settings.rules.limits.give_item_max_qty

    def cap_of(price):
        return min(limit, hero.money_cp // price) if price > 0 else limit

    rows = []
    if npc.trade is not None:
        rows = goods_rows(game, npc, cap_of) + sell_tab_rows(game, npc)
    return rows + service_rows(game, npc, cap_of)
