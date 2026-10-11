# give_item кладёт предмет с ценой из реестра (CUSTOM-ITEMS-PLAN, разд. 8, партия 0):
#   обработчик зовёт add_catalog_item -- запись инвентаря получает cost_cp предмета, quality None.
from protocol_kit import make_ctx, req

from ai_dm.protocol.apply import apply
from ai_dm.rules.inventory import add_item


def entries(ctx, item_id):
    return [(e.cost_cp, e.quality, e.qty) for e in ctx.hero.inventory if e.item_id == item_id]


def test_give_item_uses_the_registry_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="crowbar", qty=2))
    assert entries(ctx, "crowbar") == [(registry.get("item", "crowbar").cost_cp, None, 2)]


def test_give_item_weapon_uses_the_registry_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="scimitar", qty=1))
    assert entries(ctx, "scimitar") == [(registry.get("weapon", "scimitar").cost_cp, None, 1)]


def test_give_item_joins_the_stack_of_the_same_price(registry, cfg):
    ctx = make_ctx(registry, cfg)
    apply(ctx, req("give_item", item_id="longsword", qty=1))
    assert entries(ctx, "longsword") == [(registry.get("weapon", "longsword").cost_cp, None, 2)]


def test_give_item_beside_a_cheaper_stack_is_a_new_row(registry, cfg):
    ctx = make_ctx(registry, cfg)
    ctx.hero.inventory = []
    add_item(ctx.hero, "longsword", cost_cp=10, quality="junk")
    apply(ctx, req("give_item", item_id="longsword", qty=1))
    assert len(entries(ctx, "longsword")) == 2
