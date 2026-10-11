# Вес сюжетного предмета доходит до модели реестра (CUSTOM-ITEMS-PLAN, разд. 3, партия Б):
# as_item переносит CustomItem.weight_centilb в Item.weight_centilb (None -- не задан).
from ai_dm.rules.custom_items import as_item
from ai_dm.state.world import CustomItem


def test_as_item_keeps_the_weight():
    item = as_item(CustomItem(id="custom_1", name="Ключ", created_s=0, weight_centilb=150))
    assert item.weight_centilb == 150


def test_as_item_without_weight_has_none():
    item = as_item(CustomItem(id="custom_1", name="Ключ", created_s=0))
    assert item.weight_centilb is None
