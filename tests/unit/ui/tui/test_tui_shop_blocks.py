# 164 П2: данные окна /shop (ai_dm.ui.tui.shop_blocks.shop_rows и части, inv_sections.shop_tabs).
#   Строка -- (подпись, описание, [действие], вкладка); действие -- (Enter, подсказка, команда с
#   {qty}, эхо «<глагол>: <имя> (<NPC>)», потолок количества cap).
#   Купить: cap = min(лимит 20, деньги // цена, запас стека); дороже кошелька -- cap 0.
#   Продать: cap = min(свободных экземпляров, лимит).
#   Услуги: комната на ночь и обряд снятия -- cap 1.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "game"))

from types import SimpleNamespace  # noqa: E402

from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.content.models.common import EffectSpec  # noqa: E402
from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.shop_text import sale_rows  # noqa: E402
from ai_dm.rules.inventory import add_item, equip  # noqa: E402
from ai_dm.rules.money import format_cp  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, CustomItem, ItemHolder, TradeProfile  # noqa: E402
from ai_dm.ui.tui import strings  # noqa: E402
from ai_dm.ui.tui.inv_sections import grouped, inv_tabs, shop_tabs  # noqa: E402
from ai_dm.ui.tui.shop_blocks import (  # noqa: E402
    description_of,
    priced,
    shop_action,
    shop_rows,
)

FAR = 10**9


def make_game(registry, tmp_path, money=1400):
    game = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(game.bundle)
    hero.money_cp = money
    hero.inventory.clear()
    return game


def add_inn(game, services=("ale", "room_modest", "bath"), **fields):
    fields.setdefault("location_id", hero_of(game.bundle).location_id)
    game.bundle.world.npcs["grok"] = NPC(
        id="grok", name="Грок", means=["трактир"], services=list(services), **fields
    )
    return game.bundle.world.npcs["grok"]


def add_mara(game, kind="general", stock=None, **fields):
    game.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], location_id=hero_of(game.bundle).location_id,
        trade=TradeProfile(kind=kind, purse_cp=5000, restock_at_s=FAR, stock=stock or []),
        **fields,
    )
    return game.bundle.world.npcs["mara"]


def rows_for(game, npc):
    return shop_rows(game, npc)


def find(rows, text):
    return next(row for row in rows if row[0].startswith(text))


def cap(row):
    return row[2][0][4]


# priced / shop_action

def test_priced_without_quantity():
    assert priced("Колчан", 0, 100) == "Колчан — 1 зм"


def test_priced_quantity_one_has_no_multiplier():
    assert priced("Колчан", 1, 100) == "Колчан — 1 зм"


def test_priced_quantity_above_one():
    assert priced("Колчан", 2, 100) == "Колчан x2 — 1 зм"


def test_shop_action_is_enter_with_hint_command_echo_cap():
    assert shop_action("Купить", "/shop купить a b {qty}", "эхо", 3) == (
        "Enter", "Купить", "/shop купить a b {qty}", "эхо", 3,
    )


# услуги

def test_services_npc_has_only_service_rows(registry, tmp_path):
    game = make_game(registry, tmp_path)
    rows = rows_for(game, add_inn(game))
    assert [row[3] for row in rows] == [strings.SHOP_SERVICE_TAB] * 3


def test_service_label_matches_the_text_block(registry, tmp_path):
    game = make_game(registry, tmp_path)
    rows = rows_for(game, add_inn(game))
    assert [row[0] for row in rows] == [
        "эль (кружка) — 4 мм / порция",
        "комната (скромная) — 5 см / ночь",
        "баня — 1 см / раз",
    ]


def test_service_row_has_one_enter_action_with_command_and_echo(registry, tmp_path):
    game = make_game(registry, tmp_path)
    row = find(rows_for(game, add_inn(game)), "баня")
    assert row[2] == [
        ("Enter", "Оплатить", "/shop услуга grok bath {qty}", "Оплатить: баня (Грок)", 20)
    ]


def test_service_description_is_the_kind_description(registry, tmp_path):
    game = make_game(registry, tmp_path)
    row = find(rows_for(game, add_inn(game)), "комната")
    assert row[1] == game.settings.rules.services.kinds["room_modest"].description


def test_service_cap_follows_money(registry, tmp_path):
    game = make_game(registry, tmp_path, money=10)
    rows = rows_for(game, add_inn(game))
    assert cap(find(rows, "эль")) == 2


def test_service_cap_is_limited_by_the_item_limit(registry, tmp_path):
    game = make_game(registry, tmp_path, money=10**6)
    assert cap(find(rows_for(game, add_inn(game)), "эль")) == 20


def test_service_cap_exact_money_for_n_units(registry, tmp_path):
    game = make_game(registry, tmp_path, money=12)
    assert cap(find(rows_for(game, add_inn(game)), "эль")) == 3


def test_service_cap_zero_without_money(registry, tmp_path):
    game = make_game(registry, tmp_path, money=0)
    assert cap(find(rows_for(game, add_inn(game)), "эль")) == 0


def test_room_for_the_night_is_capped_at_one(registry, tmp_path):
    game = make_game(registry, tmp_path, money=10**6)
    assert cap(find(rows_for(game, add_inn(game)), "комната")) == 1


def test_cure_service_is_capped_at_one(registry, tmp_path):
    game = make_game(registry, tmp_path, money=10**6)
    rows = rows_for(game, add_inn(game, services=["uncurse_temple"]))
    assert cap(rows[0]) == 1


# товары

def test_merchant_without_services_has_goods_and_no_service_tab(registry, tmp_path):
    game = make_game(registry, tmp_path)
    tabs = {row[3] for row in rows_for(game, add_mara(game))}
    assert strings.SHOP_SERVICE_TAB not in tabs


def test_catalog_row_label_command_echo_and_tab(registry, tmp_path):
    game = make_game(registry, tmp_path)
    row = find(rows_for(game, add_mara(game)), "Колчан")
    assert row[0] == "Колчан — 1 зм"
    assert row[2] == [
        ("Enter", "Купить", "/shop купить mara quiver {qty}", "Купить: Колчан (Мара)", 14)
    ]
    assert row[3] == "Снаряжение"


def test_goods_description_is_the_item_description(registry, tmp_path):
    game = make_game(registry, tmp_path)
    row = find(rows_for(game, add_mara(game)), "Колчан")
    assert row[1] == registry.get("item", "quiver").description


def test_goods_are_sorted_by_name(registry, tmp_path):
    game = make_game(registry, tmp_path)
    names = [r[0] for r in rows_for(game, add_mara(game)) if r[3] == "Снаряжение"]
    assert names == sorted(names)


def test_stock_row_command_has_quality_and_cap_by_stock(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [InventoryEntry(item_id="scimitar", qty=2, cost_cp=300, quality="worn")]
    row = [r for r in rows_for(game, add_mara(game, kind="smith", stock=stock))
           if r[2][0][2].startswith("/shop купить mara scimitar")][0]
    assert row[2][0][2] == "/shop купить mara scimitar {qty} worn"
    assert cap(row) == 2
    assert row[0].endswith("x2 — 3 зм")


def test_stock_cap_follows_money_when_stock_is_larger(registry, tmp_path):
    game = make_game(registry, tmp_path, money=700)
    stock = [InventoryEntry(item_id="scimitar", qty=5, cost_cp=300, quality="worn")]
    rows = rows_for(game, add_mara(game, kind="smith", stock=stock))
    row = [r for r in rows if r[2][0][2].endswith("worn")][0]
    assert cap(row) == 2


def test_stock_without_quality_has_no_trailing_word(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [InventoryEntry(item_id="quiver", qty=1, cost_cp=100)]
    rows = rows_for(game, add_mara(game, stock=stock))
    commands = {r[2][0][2] for r in rows if "quiver" in r[2][0][2]}
    assert commands == {"/shop купить mara quiver {qty}"}


def test_unaffordable_goods_stay_listed_with_zero_cap(registry, tmp_path):
    game = make_game(registry, tmp_path, money=100)
    row = find(rows_for(game, add_mara(game)), "Воровские инструменты")
    assert cap(row) == 0


def test_held_story_item_row(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game)
    game.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Старый ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, qty=2, cost_cp=400),
    )
    row = find(rows_for(game, mara), "Ржавый ключ")
    assert row[0] == "Ржавый ключ x2 — 4 зм"
    assert row[1] == "Старый ключ"
    assert row[2][0][2] == "/shop купить mara custom_1 {qty}"
    assert (cap(row), row[3]) == (2, "Сюжетное")


# продать

def test_sell_row_label_command_echo_and_tab(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game)
    add_item(hero_of(game.bundle), "quiver", 3, cost_cp=100)
    row = find(rows_for(game, mara), "Колчан x3")
    assert row[0] == "Колчан x3 — 5 см"
    assert row[2] == [
        ("Enter", "Продать", "/shop продать mara quiver {qty}", "Продать: Колчан (Мара)", 3)
    ]
    assert row[3] == strings.SHOP_SELL_TAB


def test_sell_description_is_the_item_description(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game)
    add_item(hero_of(game.bundle), "quiver", cost_cp=100)
    sell = [r for r in rows_for(game, mara) if r[3] == strings.SHOP_SELL_TAB]
    assert sell[0][1] == registry.get("item", "quiver").description


def test_sell_cap_is_limited_by_the_item_limit(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game)
    add_item(hero_of(game.bundle), "quiver", 25, cost_cp=100)
    sell = [r for r in rows_for(game, mara) if r[3] == strings.SHOP_SELL_TAB]
    assert cap(sell[0]) == 20


def test_sell_leaves_out_the_equipped_instance(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game, kind="smith")
    hero = hero_of(game.bundle)
    add_item(hero, "scimitar", 2, cost_cp=300)
    equip(hero, "scimitar", game.registry)
    sell = [r for r in rows_for(game, mara) if r[3] == strings.SHOP_SELL_TAB]
    assert (sell[0][0], cap(sell[0])) == ("Скимитар — 1 зм 5 см", 1)


def test_sell_tab_empty_without_sellable_items(registry, tmp_path):
    game = make_game(registry, tmp_path)
    tabs = {r[3] for r in rows_for(game, add_mara(game))}
    assert strings.SHOP_SELL_TAB not in tabs


def test_merchant_with_services_gets_goods_sell_and_services_in_order(registry, tmp_path):
    game = make_game(registry, tmp_path)
    mara = add_mara(game, services=["bath"])
    add_item(hero_of(game.bundle), "quiver", cost_cp=100)
    tabs = [r[3] for r in rows_for(game, mara)]
    first_sell = tabs.index(strings.SHOP_SELL_TAB)
    assert tabs[first_sell - 1] == "Снаряжение"
    assert tabs[-1] == strings.SHOP_SERVICE_TAB
    assert tabs.count(strings.SHOP_SERVICE_TAB) == 1


# описание

def test_description_of_prefers_the_description():
    effects = [EffectSpec(type="ac_bonus", value=1)]
    item = SimpleNamespace(description="Колчан для стрел", effects=effects)
    assert description_of(item) == "Колчан для стрел"


def test_description_of_falls_back_to_effect_texts():
    item = SimpleNamespace(description="", effects=[EffectSpec(type="ac_bonus", value=1)])
    assert description_of(item) == "+1 КД"


def test_description_of_item_without_effects_is_empty():
    assert description_of(SimpleNamespace(description="")) == ""


def test_sell_row_without_description_shows_effects(registry, tmp_path, monkeypatch):
    game = make_game(registry, tmp_path)
    mara = add_mara(game)
    add_item(hero_of(game.bundle), "quiver", cost_cp=100)
    model = registry.get("item", "quiver")
    monkeypatch.setattr(model, "description", "")
    monkeypatch.setattr(model, "effects", [EffectSpec(type="ac_bonus", value=2)], raising=False)
    sell = [r for r in rows_for(game, mara) if r[3] == strings.SHOP_SELL_TAB]
    assert sell[0][1] == "+2 КД"


def test_goods_row_without_description_shows_effects(registry, tmp_path, monkeypatch):
    game = make_game(registry, tmp_path)
    model = registry.get("item", "quiver")
    monkeypatch.setattr(model, "description", "")
    monkeypatch.setattr(model, "effects", [EffectSpec(type="ac_bonus", value=2)], raising=False)
    assert find(rows_for(game, add_mara(game)), "Колчан")[1] == "+2 КД"


# вкладки

def test_shop_tabs_follow_the_shop_order_and_skip_empty(registry, tmp_path):
    rows = [("a", "", [], "Услуги"), ("b", "", [], "Продать"), ("c", "", [], "Оружие")]
    assert [name for name, _ in shop_tabs(rows)] == ["Оружие", "Продать", "Услуги"]


def test_shop_tabs_group_rows_by_name_in_given_order():
    rows = [("a", "", [], "Продать"), ("b", "", [], "Продать")]
    assert shop_tabs(rows) == [("Продать", rows)]


def test_shop_tabs_of_services_only_is_one_tab(registry, tmp_path):
    game = make_game(registry, tmp_path)
    tabs = shop_tabs(rows_for(game, add_inn(game)))
    assert [name for name, _ in tabs] == ["Услуги"]


def test_shop_tabs_have_no_worn_tab():
    assert "Надето" not in strings.SHOP_TABS


def test_shop_tabs_empty_rows_give_no_tabs():
    assert shop_tabs([]) == []


def test_grouped_uses_given_names_and_order():
    rows = [("a", "", [], "Y"), ("b", "", [], "X"), ("c", "", [], "Z")]
    assert grouped(rows, ("X", "Y")) == [("X", [rows[1]]), ("Y", [rows[0]])]


def test_inv_tabs_use_the_inventory_order():
    rows = [("a", "", [], "Оружие"), ("b", "", [], "Надето")]
    assert [name for name, _ in inv_tabs(rows)] == ["Надето", "Оружие"]


# добивка мутантов П2

def test_stock_of_one_caps_the_purchase_at_one_with_money_to_spare(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [InventoryEntry(item_id="quiver", qty=1, cost_cp=100)]
    rows = rows_for(game, add_mara(game, stock=stock))
    row = [r for r in rows if r[2][0][2] == "/shop купить mara quiver {qty}"][0]
    assert cap(row) == 1


def test_stock_goods_come_before_the_catalog_whatever_the_name(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=300)]
    goods = [r for r in rows_for(game, add_mara(game, stock=stock)) if "купить" in r[2][0][2]]
    assert goods[0][2][0][2].startswith("/shop купить mara scimitar")
    assert len(goods) > 1


def test_same_item_stock_entries_keep_their_given_order(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=500, quality="worn"),
        InventoryEntry(item_id="scimitar", qty=1, cost_cp=300, quality="worn"),
    ]
    rows = rows_for(game, add_mara(game, kind="smith", stock=stock))
    prices = [r[0].split(" — ")[1] for r in rows if r[2][0][2].endswith(" worn")]
    npc = game.bundle.world.npcs["mara"]
    given = sale_rows(npc, game.bundle.world, game.registry, 1, game.settings.rules)
    assert prices == [format_cp(r[2]) for r in given if r[6] == "worn"]
    assert len(set(prices)) == 2


def test_magic_stock_is_offered_to_a_first_level_hero(registry, tmp_path):
    game = make_game(registry, tmp_path)
    stock = [InventoryEntry(item_id="potion_of_healing", qty=1, cost_cp=5000)]
    rows = rows_for(game, add_mara(game, stock=stock))
    assert any("potion_of_healing" in r[2][0][2] for r in rows)


def test_free_stock_item_is_capped_by_the_item_limit_only(registry, tmp_path):
    game = make_game(registry, tmp_path, money=0)
    limit = game.settings.rules.limits.give_item_max_qty
    stock = [InventoryEntry(item_id="quiver", qty=limit + 10, cost_cp=0)]
    rows = rows_for(game, add_mara(game, stock=stock))
    row = [r for r in rows if r[0].startswith(f"Колчан x{limit + 10}")][0]
    assert cap(row) == limit


def test_one_copper_item_is_capped_by_money(registry, tmp_path):
    game = make_game(registry, tmp_path, money=5)
    stock = [InventoryEntry(item_id="quiver", qty=30, cost_cp=1)]
    rows = rows_for(game, add_mara(game, stock=stock))
    row = [r for r in rows if r[0].startswith("Колчан x30")][0]
    assert cap(row) == 5
