from ai_dm.rules.trade import item_category
from ai_dm.ui.tui import strings

WORN, WEAPONS, AMMO, ARMOR, CONSUMABLES, GEAR, VALUABLES, QUEST = strings.INV_TABS

SECTIONS = {
    "weapon": WEAPONS, "armor": ARMOR, "ammo": AMMO, "consumable": CONSUMABLES,
    "valuable": VALUABLES, None: QUEST,
}


def inv_section(found, worn):
    # вкладка окна /inv: надетое -- «Надето», неизвестный id и прочее -- «Снаряжение»
    if worn:
        return WORN
    if found is None:
        return GEAR
    return SECTIONS.get(item_category(*found), GEAR)


def inv_tabs(rows):
    # строки по вкладкам в порядке INV_TABS; пустые вкладки опущены
    return grouped(rows, strings.INV_TABS)


def shop_tabs(rows):
    # то же для окна /shop: порядок SHOP_TABS
    return grouped(rows, strings.SHOP_TABS)


def grouped(rows, names):
    tabs = [(name, [row for row in rows if row[3] == name]) for name in names]
    return [(name, group) for name, group in tabs if group]
