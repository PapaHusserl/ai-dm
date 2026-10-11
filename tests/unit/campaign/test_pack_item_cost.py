# inventory_extra пака: предметы ложатся с ценой из реестра (CUSTOM-ITEMS-PLAN, разд. 8, партия 0).
#   В паке запись -- {item_id, qty} без цены; цену ставит сборка героя (add_catalog_item).
from campaign_kit import default_files
from test_pack_build import build


def test_pack_extra_items_get_the_registry_price(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"].update({
        "inventory_extra": [{"item_id": "potion_of_healing", "qty": 2}],
    })
    hero = build(tmp_path, registry, cfg, files).heroes[0]
    potion = [e for e in hero.inventory if e.item_id == "potion_of_healing"]
    assert [(e.qty, e.cost_cp, e.quality) for e in potion] == [
        (2, registry.get("item", "potion_of_healing").cost_cp, None)
    ]


def test_pack_extra_item_joins_the_built_stack_of_the_same_price(tmp_path, registry, cfg):
    files = default_files()
    files["heroes/arn.yaml"].update({
        "inventory_extra": [{"item_id": "longsword", "qty": 1}],
    })
    hero = build(tmp_path, registry, cfg, files).heroes[0]
    stack = [e for e in hero.inventory if e.item_id == "longsword"]
    assert len(stack) == 1
    assert stack[0].qty == 2
