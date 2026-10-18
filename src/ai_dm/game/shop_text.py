from types import SimpleNamespace

from ai_dm.game.sheet_text import INV_GROUPS, inv_group
from ai_dm.protocol.handlers.trade_pick import sellable_stacks
from ai_dm.rules import trade as trade_rules
from ai_dm.rules.inventory import entry_name, find_item
from ai_dm.rules.loot import rarity_exceeds_cap
from ai_dm.rules.money import format_cp
from ai_dm.rules.npc_names import shown_name

SHOP_ROWS_MAX = 40
NO_MERCHANT = "Здесь никто не торгует"


def merchants_here(world, location_id):
    return [
        npc for npc in world.npcs.values()
        if npc.trade is not None and npc.status == "alive" and npc.location_id == location_id
    ]


def sale_rows(npc, world, registry, level, cfg):
    # (порядок группы, имя, цена): сначала купленное у героя, затем ассортимент пресета
    rows = []
    now_s = world.clock.now_s
    for entry in npc.trade.stock:
        kind, model = find_item(registry, entry.item_id)
        if kind == "item" and model.magic and rarity_exceeds_cap(model, level, cfg):
            continue
        price = trade_rules.merchant_buy_quote(entry.cost_cp, npc, now_s, cfg)
        rows.append((-1, entry_name(entry, registry), price, entry.qty, inv_group(kind, model)))
    for custom in world.custom_items.values():
        holder = custom.holder
        if holder is None or holder.kind != "npc" or holder.ref != npc.id:
            continue
        kind, model = find_item(registry, custom.id)
        price = trade_rules.merchant_buy_quote(holder.cost_cp, npc, now_s, cfg)
        rows.append((-1, model.name, price, holder.qty, inv_group(kind, model)))
    preset = cfg.trade.presets[npc.trade.kind]
    for item_id, _base in trade_rules.assortment(registry, preset, level, cfg):
        kind, model = find_item(registry, item_id)
        price = trade_rules.merchant_buy_quote(model.cost_cp, npc, now_s, cfg)
        rows.append((0, model.name, price, 0, inv_group(kind, model)))
    return rows


def shop_item_lines(rows):
    order = [key for key, _ in INV_GROUPS]
    titles = dict(INV_GROUPS)
    rows = sorted(rows, key=lambda r: (order.index(r[4]), r[0], r[1]))
    lines = []
    group = None
    for _, name, price, qty, key in rows[:SHOP_ROWS_MAX]:
        if key != group:
            group = key
            lines.append(f"  {titles[key]}:")
        line = f"    {name}"
        if qty > 1:
            line += f" x{qty}"
        lines.append(f"{line} — {format_cp(price)}")
    if len(rows) > SHOP_ROWS_MAX:
        lines.append(f"    …и ещё {len(rows) - SHOP_ROWS_MAX}")
    return lines


def sell_lines(hero, world, registry, npc, cfg):
    # что герой может продать этому торговцу; свободные экземпляры считает sellable_stacks
    preset = cfg.trade.presets[npc.trade.kind]
    lines = []
    for entry in hero.inventory:
        found = find_item(registry, entry.item_id)
        if found is None:
            continue
        request = SimpleNamespace(item_id=entry.item_id, quality=None)
        free = next((n for stack, n in sellable_stacks(hero, request)[1] if stack is entry), 0)
        if free < 1:
            continue
        # сюжетные предметы лежат в реестре оверлеем мира; их принимают все торговцы
        custom = entry.item_id in world.custom_items
        if not custom and not trade_rules.merchant_buys(*found, preset):
            continue
        price = trade_rules.sell_quote(entry.cost_cp, npc.attitude, cfg)
        if price > 0:
            tail = f" x{free}" if free > 1 else ""
            lines.append(f"Продать: {entry_name(entry, registry)}{tail} — {format_cp(price)}")
    return sorted(lines)


def shop_lines(hero, world, registry, cfg):
    npcs = merchants_here(world, hero.location_id)
    if not npcs:
        return [NO_MERCHANT]
    lines = []
    for npc in npcs:
        if lines:
            lines.append("")
        if trade_rules.refuses(npc.attitude, cfg):
            lines.append(f"{shown_name(npc)} отказывается торговать")
            continue
        now_s = world.clock.now_s
        purse = format_cp(trade_rules.purse_now(npc.trade, now_s, cfg))
        head = f"{shown_name(npc)} ({npc.trade.kind}) — кошелёк торговца: {purse}"
        haggle = trade_rules.haggle_state(npc.trade, now_s).get("haggle")
        if haggle:
            sign = "−" if haggle["percent"] < 0 else "+"
            head += f"; торг: {sign}{abs(haggle['percent'])}% до конца дня"
        lines.append(head)
        level = hero.sheet.level
        lines += shop_item_lines(sale_rows(npc, world, registry, level, cfg))
        lines += sell_lines(hero, world, registry, npc, cfg)
    lines.append(f"Деньги: {format_cp(hero.money_cp)}")
    return lines
