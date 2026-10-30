# Боеприпасы (docs/plan-bp.md): свойство ammunition ⇔ задан weapon.ammo; предмет — category "ammo".
import pytest


def test_ammunition_property_matches_ammo_field(registry):
    for weapon in registry.all("weapon"):
        assert ("ammunition" in weapon.properties) == (weapon.ammo is not None), weapon.id


def test_weapon_ammo_points_to_ammo_item(registry):
    for weapon in registry.all("weapon"):
        if weapon.ammo is not None:
            assert registry.get("item", weapon.ammo).category == "ammo", weapon.id


@pytest.mark.parametrize(
    "item_id, cost_cp",
    [("arrows", 5), ("bolts", 5), ("needles", 2), ("sling_bullets", 1), ("firearm_bullets", 30)],
)
def test_ammo_items_are_priced_per_piece(registry, item_id, cost_cp):
    item = registry.get("item", item_id)
    assert (item.category, item.cost_cp) == ("ammo", cost_cp)
