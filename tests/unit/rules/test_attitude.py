# М0 П6а (docs/plan-m0.md, «Тесты» П6, «Умолчания» п. 29): ступени отношения.
#   tier_of(attitude, cfg) -> запись ступени (id, name): последняя, чья граница не выше числа;
#   at_least(attitude, tier_id, cfg) -- ступень не ниже tier_id; at_most -- не выше.
#   Ступени по умолчанию: enemy -100, foe -49, neutral -29, buddy 30, friend 50, close 90.
import pytest

from ai_dm.config.settings import load_rules_config
from ai_dm.rules.attitude import at_least, at_most, tier_of

IDS = ["enemy", "foe", "neutral", "buddy", "friend", "close"]

TIER_BOUNDS = [
    (-100, "enemy"), (-50, "enemy"),
    (-49, "foe"), (-30, "foe"),
    (-29, "neutral"), (0, "neutral"), (29, "neutral"),
    (30, "buddy"), (49, "buddy"),
    (50, "friend"), (89, "friend"),
    (90, "close"), (100, "close"),
]


@pytest.mark.parametrize("attitude,tier_id", TIER_BOUNDS)
def test_tier_of_default_bounds(cfg, attitude, tier_id):
    assert tier_of(attitude, cfg).id == tier_id


def test_tier_names_are_russian_words(cfg):
    names = [tier_of(a, cfg).name for a in (-100, -49, -29, 30, 50, 90)]
    assert names == ["враг", "недруг", "нейтрален", "приятель", "друг", "близкий"]


def test_default_tiers_ids_in_order(cfg):
    assert [t.id for t in cfg.attitude.tiers] == IDS


def test_tier_of_below_first_bound_is_first_tier(cfg):
    custom = load_rules_config(toml_text=TIERS_FROM_MINUS_20)
    assert tier_of(-100, custom).id == "enemy"


TIERS_FROM_MINUS_20 = (
    '[[attitude.tiers]]\nid = "enemy"\nname = "враг"\nfrom = -20\n'
    '[[attitude.tiers]]\nid = "foe"\nname = "недруг"\nfrom = 0\n'
    '[[attitude.tiers]]\nid = "neutral"\nname = "нейтрален"\nfrom = 20\n'
    '[[attitude.tiers]]\nid = "buddy"\nname = "приятель"\nfrom = 30\n'
    '[[attitude.tiers]]\nid = "friend"\nname = "друг"\nfrom = 40\n'
    '[[attitude.tiers]]\nid = "close"\nname = "близкий"\nfrom = 90\n'
)


def test_at_least_friend_includes_close(cfg):
    assert at_least(50, "friend", cfg)
    assert at_least(90, "friend", cfg)
    assert at_least(100, "friend", cfg)


def test_at_least_friend_excludes_buddy(cfg):
    assert not at_least(49, "friend", cfg)


def test_at_least_own_tier_bounds(cfg):
    assert at_least(30, "buddy", cfg)
    assert not at_least(29, "buddy", cfg)


def test_at_least_enemy_is_always_true(cfg):
    assert at_least(-100, "enemy", cfg)


def test_at_most_foe_includes_enemy(cfg):
    assert at_most(-30, "foe", cfg)
    assert at_most(-50, "foe", cfg)
    assert at_most(-100, "foe", cfg)


def test_at_most_foe_excludes_neutral(cfg):
    assert not at_most(-29, "foe", cfg)


def test_at_most_enemy_bounds(cfg):
    assert at_most(-50, "enemy", cfg)
    assert not at_most(-49, "enemy", cfg)


def test_at_most_close_is_always_true(cfg):
    assert at_most(100, "close", cfg)


def test_tiers_follow_user_config_friend_from_40():
    custom = load_rules_config(toml_text=TIERS_FROM_MINUS_20)
    assert at_least(40, "friend", custom)
    assert not at_least(39, "friend", custom)
    assert tier_of(39, custom).id == "buddy"
