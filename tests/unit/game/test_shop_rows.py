# 164 П2: строки данных /shop для окна TUI (ai_dm.game.shop_text).
#   sale_rows -- (порядок группы, имя, цена, qty, группа, id, качество): stock -> id и качество,
#   сюжетный предмет держателя -> его id и None, ассортимент пресета -> id и None, qty 0.
#   sell_rows -- (id, имя, цена, свободных экземпляров); sell_lines строит из них текст как раньше.
#   shop_item_lines распаковывает расширенный кортеж и режет по SHOP_ROWS_MAX.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "ui"))

from ui_kit import text_app, text_step  # noqa: E402

from ai_dm.game.scene import hero_of  # noqa: E402
from ai_dm.game.shop_text import (  # noqa: E402
    SHOP_ROWS_MAX,
    sale_rows,
    sell_lines,
    sell_rows,
    shop_item_lines,
)
from ai_dm.rules.inventory import add_item, equip  # noqa: E402
from ai_dm.state.hero import InventoryEntry  # noqa: E402
from ai_dm.state.world import NPC, CustomItem, ItemHolder, TradeProfile  # noqa: E402

FAR = 10**9


def make_shop(registry, tmp_path, kind="general", stock=None, attitude=0):
    app = text_app(registry, tmp_path, [text_step()])
    hero = hero_of(app.bundle)
    hero.inventory.clear()
    app.bundle.world.npcs["mara"] = NPC(
        id="mara", name="Мара", means=["товары"], attitude=attitude, location_id=hero.location_id,
        trade=TradeProfile(kind=kind, purse_cp=5000, restock_at_s=FAR, stock=stock or []),
    )
    return app


def rows_of(app):
    npc = app.bundle.world.npcs["mara"]
    level = hero_of(app.bundle).sheet.level
    return sale_rows(npc, app.bundle.world, app.registry, level, app.settings.rules)


def sells_of(app):
    npc = app.bundle.world.npcs["mara"]
    return sell_rows(hero_of(app.bundle), app.bundle.world, app.registry, npc, app.settings.rules)


def sell_text(app):
    npc = app.bundle.world.npcs["mara"]
    return sell_lines(hero_of(app.bundle), app.bundle.world, app.registry, npc, app.settings.rules)


def by_id(rows, item_id):
    return [row for row in rows if row[5] == item_id]


# sale_rows

def test_catalog_row_has_id_no_quality_and_zero_qty(registry, tmp_path):
    row = by_id(rows_of(make_shop(registry, tmp_path)), "quiver")[0]
    assert row == (0, "Колчан", 100, 0, row[4], "quiver", None)


def test_stock_row_carries_id_quality_qty_and_price(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=2, cost_cp=300, quality="worn")]
    row = by_id(rows_of(make_shop(registry, tmp_path, kind="smith", stock=stock)), "scimitar")[0]
    assert (row[0], row[2], row[3], row[5], row[6]) == (-1, 300, 2, "scimitar", "worn")


def test_stock_row_without_quality_has_none(registry, tmp_path):
    stock = [InventoryEntry(item_id="quiver", qty=1, cost_cp=100)]
    row = by_id(rows_of(make_shop(registry, tmp_path, stock=stock)), "quiver")[0]
    assert (row[0], row[6]) == (-1, None)


def test_held_story_item_row_has_custom_id_and_its_price(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="mara", label="Мара", since_s=0, qty=2, cost_cp=400),
    )
    row = by_id(rows_of(app), "custom_1")[0]
    assert (row[0], row[1], row[2], row[3], row[6]) == (-1, "Ржавый ключ", 400, 2, None)


def test_story_item_of_another_holder_has_no_row(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
        holder=ItemHolder(kind="npc", ref="other", label="Иной", since_s=0, cost_cp=400),
    )
    assert by_id(rows_of(app), "custom_1") == []


# shop_item_lines

def test_item_lines_accept_extended_rows_and_keep_text(registry, tmp_path):
    stock = [InventoryEntry(item_id="quiver", qty=3, cost_cp=100)]
    lines = shop_item_lines(rows_of(make_shop(registry, tmp_path, stock=stock)))
    assert "    Колчан x3 — 1 зм" in lines


def test_item_lines_cut_at_the_limit(registry, tmp_path):
    stock = [InventoryEntry(item_id="scimitar", qty=1, cost_cp=100 + n) for n in range(50)]
    rows = rows_of(make_shop(registry, tmp_path, stock=stock))
    lines = shop_item_lines(rows)
    assert lines[-1] == f"    …и ещё {len(rows) - SHOP_ROWS_MAX}"


# sell_rows / sell_lines

def test_sell_row_is_id_name_price_free(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert sells_of(app) == [("quiver", "Колчан", 50, 1)]


def test_sell_row_free_counts_the_whole_stack(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    add_item(hero_of(app.bundle), "quiver", 3, cost_cp=100)
    assert sells_of(app)[0][3] == 3


def test_sell_rows_skip_what_the_merchant_does_not_buy(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert sells_of(app) == []


def test_sell_rows_skip_worthless(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    add_item(hero_of(app.bundle), "quiver", cost_cp=1)
    assert sells_of(app) == []


def test_sell_rows_leave_out_the_equipped_instance(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="smith")
    hero = hero_of(app.bundle)
    add_item(hero, "scimitar", 2, cost_cp=300)
    equip(hero, "scimitar", app.registry)
    assert sells_of(app)[0][3] == 1


def test_sell_rows_skip_an_unknown_item(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    entry = InventoryEntry(item_id="no_such_thing", qty=1, cost_cp=500)
    hero_of(app.bundle).inventory.append(entry)
    assert sells_of(app) == []


def test_sell_rows_offer_story_item_to_any_merchant(registry, tmp_path):
    app = make_shop(registry, tmp_path, kind="armorer")
    app.bundle.world.custom_items["custom_1"] = CustomItem(
        id="custom_1", name="Ржавый ключ", description="Ключ", quest=True, created_s=0,
    )
    hero_of(app.bundle).inventory.append(
        InventoryEntry(item_id="custom_1", qty=1, cost_cp=1000)
    )
    assert [row[0] for row in sells_of(app)] == ["custom_1"]


def test_sell_lines_show_quantity_only_above_one(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    add_item(hero, "quiver", 3, cost_cp=100)
    assert sell_text(app) == ["Продать: Колчан x3 — 5 см"]


def test_sell_lines_single_has_no_multiplier(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    add_item(hero_of(app.bundle), "quiver", cost_cp=100)
    assert sell_text(app) == ["Продать: Колчан — 5 см"]


def test_sell_lines_are_sorted(registry, tmp_path):
    app = make_shop(registry, tmp_path)
    hero = hero_of(app.bundle)
    add_item(hero, "quiver", cost_cp=100)
    add_item(hero, "torch", cost_cp=100)
    lines = sell_text(app)
    assert lines == sorted(lines)
