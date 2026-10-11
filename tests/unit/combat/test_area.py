# Площади заклинаний (шаг 17, ТЗ 7): ai_dm.combat.area
#   affected_zones(zones: list[Zone], origin_id: str, shape: str, size_ft: int, target_id: str)
#       -> list[str]   -- id накрытых зон в порядке списка zones
#     "sphere" / "cube" (size_ft -- радиус): <= 20 фт -- одна зона target_id; больше -- target_id
#         и соседние с ней (круг до 20 фт = одна зона, ТЗ 7);
#     "cone" / "line" (от заклинателя): target_id -- зона заклинателя (origin_id) или соседняя
#         с ней по выбору; дальше -> ValueError; накрывает ровно target_id;
#     неизвестная форма -> ValueError.
#   Союзники в накрытой зоне задеваются наравне с врагами (проверяется в test_actions_cast.py).
import pytest
from combat_kit import make_zones

from ai_dm.combat.area import affected_zones


def test_small_sphere_covers_only_its_zone():
    assert affected_zones(make_zones(), "door", "sphere", 5, "hall") == ["hall"]


def test_sphere_of_20_ft_is_still_one_zone():
    assert affected_zones(make_zones(), "door", "sphere", 20, "hall") == ["hall"]


def test_sphere_over_20_ft_covers_zone_and_neighbours():
    assert affected_zones(make_zones(), "door", "sphere", 25, "hall") == ["door", "hall", "balcony"]


def test_big_sphere_at_the_edge_covers_edge_and_its_neighbour():
    assert affected_zones(make_zones(), "balcony", "sphere", 30, "door") == ["door", "hall"]


def test_cube_follows_the_same_rule_as_sphere():
    assert affected_zones(make_zones(), "door", "cube", 20, "hall") == ["hall"]
    assert affected_zones(make_zones(), "door", "cube", 30, "hall") == ["door", "hall", "balcony"]


def test_cone_can_target_own_zone():
    assert affected_zones(make_zones(), "hall", "cone", 15, "hall") == ["hall"]


def test_cone_can_target_neighbour_zone():
    assert affected_zones(make_zones(), "hall", "cone", 15, "balcony") == ["balcony"]


def test_cone_cannot_target_far_zone():
    with pytest.raises(ValueError):
        affected_zones(make_zones(), "door", "cone", 15, "balcony")


def test_line_works_like_cone():
    assert affected_zones(make_zones(), "door", "line", 30, "hall") == ["hall"]
    with pytest.raises(ValueError):
        affected_zones(make_zones(), "door", "line", 30, "balcony")


def test_unknown_shape_raises():
    with pytest.raises(ValueError):
        affected_zones(make_zones(), "hall", "cross", 10, "hall")
