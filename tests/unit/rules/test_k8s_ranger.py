# К8с П1: умения следопыта 6-10, скорость, пул Неутомимости, отдыхи (docs/plan-k8s.md,
# «Тесты», П1). Ожидаемый API: derived.hero_speed(hero, registry) -> int; умения roving (6),
# expertise (9), tireless (10); favored_enemy.max_by_level {1: 2, 5: 3, 9: 4, 13: 5, 17: 6};
# short_rest у героя с tireless снижает истощение на 1; long_rest обнуляет hp_temp.
import pytest
from ranger_kit import make_ranger, ranger_at

from ai_dm.core.clock import GameClock
from ai_dm.core.rng import Rng
from ai_dm.game.sheet_text import sheet_stat_lines
from ai_dm.rules.derived import hero_feature_ids, resource_maxes
from ai_dm.rules.progression import sync_resources
from ai_dm.rules.rests import long_rest, short_rest


def speed_line(hero, registry):
    lines = sheet_stat_lines(hero, registry, 80)
    return next(line for line in lines if line.startswith("Скорость"))


def tireless_hero(registry, wis, level=10):
    hero = ranger_at(registry, level)
    hero.sheet.abilities["wis"] = wis
    sync_resources(hero, registry)
    return hero


def pool(hero, name):
    return hero.creature.resources[name]


# умения по уровням

def test_roving_absent_at_level_5(registry):
    assert "roving" not in hero_feature_ids(ranger_at(registry, 5), registry)


def test_roving_present_at_level_6(registry):
    assert "roving" in hero_feature_ids(ranger_at(registry, 6), registry)


def test_expertise_present_at_level_9(registry):
    assert "expertise" in hero_feature_ids(ranger_at(registry, 9), registry)


def test_tireless_absent_at_level_9(registry):
    assert "tireless" not in hero_feature_ids(ranger_at(registry, 9), registry)


def test_tireless_present_at_level_10(registry):
    assert "tireless" in hero_feature_ids(ranger_at(registry, 10), registry)


# Избранный враг

@pytest.mark.parametrize(
    "level, uses", [(8, 3), (9, 4), (12, 4), (13, 5), (17, 6)],
)
def test_favored_enemy_pool_by_level_6_plus(registry, level, uses):
    assert resource_maxes(ranger_at(registry, level), registry)["favored_enemy"] == uses


# скорость в /sheet

def fake_effects(monkeypatch, *effects):
    from types import SimpleNamespace

    items = [SimpleNamespace(type=t, target=tg, value=v) for t, tg, v in effects]
    monkeypatch.setattr("ai_dm.rules.derived.hero_effects", lambda hero, registry: items)


def test_hero_speed_ignores_modifier_of_other_target(registry, monkeypatch):
    from ai_dm.rules.derived import hero_speed

    fake_effects(monkeypatch, ("modifier", "initiative", 5))
    assert hero_speed(ranger_at(registry, 1), registry) == 30


def test_hero_speed_ignores_non_modifier_effect_on_speed(registry, monkeypatch):
    from ai_dm.rules.derived import hero_speed

    fake_effects(monkeypatch, ("resistance", "speed", 5))
    assert hero_speed(ranger_at(registry, 1), registry) == 30


def test_hero_speed_modifier_without_value_adds_nothing(registry, monkeypatch):
    from ai_dm.rules.derived import hero_speed

    fake_effects(monkeypatch, ("modifier", "speed", None))
    assert hero_speed(ranger_at(registry, 1), registry) == 30


def test_sheet_speed_is_40_at_level_6(registry):
    assert speed_line(ranger_at(registry, 6), registry).startswith("Скорость 40 фт.")


def test_sheet_speed_is_30_at_level_5(registry):
    assert speed_line(ranger_at(registry, 5), registry).startswith("Скорость 30 фт.")


def test_sheet_speed_is_30_in_heavy_armor_at_level_6(registry):
    hero = ranger_at(registry, 6)
    hero.equipped.armor = "chain_mail"
    assert speed_line(hero, registry).startswith("Скорость 30 фт.")


# пул Неутомимости

@pytest.mark.parametrize("wis, uses", [(16, 3), (10, 1), (8, 1)])
def test_tireless_pool_max_by_wisdom(registry, wis, uses):
    hero = tireless_hero(registry, wis)
    assert (pool(hero, "tireless").current, pool(hero, "tireless").max) == (uses, uses)


def test_long_rest_restores_tireless_fully(registry, cfg):
    hero = tireless_hero(registry, 16)
    pool(hero, "tireless").current = 0
    long_rest(hero, registry, GameClock(), cfg)
    assert pool(hero, "tireless").current == 3


def test_short_rest_does_not_restore_tireless(registry, cfg):
    hero = tireless_hero(registry, 16)
    pool(hero, "tireless").current = 0
    short_rest(hero, registry, Rng(1), GameClock(), cfg=cfg)
    assert pool(hero, "tireless").current == 0


# отдыхи

def test_short_rest_lowers_exhaustion_at_level_10(registry, cfg):
    hero = tireless_hero(registry, 16)
    hero.creature.exhaustion = 2
    short_rest(hero, registry, Rng(1), GameClock(), cfg=cfg)
    assert hero.creature.exhaustion == 1


def test_short_rest_keeps_exhaustion_at_level_9(registry, cfg):
    hero = tireless_hero(registry, 16, level=9)
    hero.creature.exhaustion = 2
    short_rest(hero, registry, Rng(1), GameClock(), cfg=cfg)
    assert hero.creature.exhaustion == 2


def test_short_rest_without_exhaustion_stays_zero(registry, cfg):
    hero = tireless_hero(registry, 16)
    short_rest(hero, registry, Rng(1), GameClock(), cfg=cfg)
    assert hero.creature.exhaustion == 0


def test_long_rest_clears_temp_hp(registry, cfg):
    hero = make_ranger(registry)
    hero.creature.hp_temp = 7
    long_rest(hero, registry, GameClock(), cfg)
    assert hero.creature.hp_temp == 0
