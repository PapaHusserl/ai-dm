# Регрессия: воин и плут растут как раньше после изменений повышения уровня и выборов
# (docs/plan-ranger-2-5.md, разд. 7). Работает на существующем API, кроме
# required_choices (импорт внутри теста): воин и плут на 2, 3, 5 ур. выборов не требуют.
import pytest
from ranger_kit import make_class_hero

from ai_dm.rules.progression import level_up, sync_resources

SCORES = {"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12}


def pool(hero, name):
    return hero.creature.resources[name]


@pytest.mark.parametrize("class_id, gain", [("fighter", 8), ("rogue", 7)])
def test_fighter_and_rogue_hp_gain_is_unchanged(registry, class_id, gain):
    # ТЕЛ 15 (+2): среднее кости (d10 -> 6, d8 -> 5) + 2
    hero = make_class_hero(class_id, SCORES)
    for _ in range(4):
        level_up(hero, registry, hp_method="average")
    assert hero.creature.hp_max == 10 + 4 * gain


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
def test_fighter_and_rogue_level_up_keeps_second_wind_and_adds_no_ranger_pools(registry, class_id):
    hero = make_class_hero(class_id, SCORES)
    sync_resources(hero, registry)
    for _ in range(4):
        level_up(hero, registry, hp_method="average")
    assert "favored_enemy" not in hero.creature.resources
    assert not [k for k in hero.creature.resources if k.startswith("spell_slot:")]
    assert pool(hero, {"fighter": "hit_dice:d10", "rogue": "hit_dice:d8"}[class_id]).max == 5


def test_fighter_second_wind_is_three_at_level_5(registry):
    # К2, решение 27: Второе дыхание — 3 заряда с 4 ур.
    hero = make_class_hero("fighter", SCORES)
    sync_resources(hero, registry)
    for _ in range(4):
        level_up(hero, registry, hp_method="average")
    assert pool(hero, "second_wind").max == 3


@pytest.mark.parametrize("class_id", ["fighter", "rogue"])
@pytest.mark.parametrize("level, expected", [(2, set()), (3, {"subclass"}), (5, set())])
def test_fighter_and_rogue_required_choices_on_levels_2_3_5(registry, class_id, level, expected):
    # подкласс на 3 ур. (Чемпион, Вор — К2); экспертиза плута уже выбрана на 1 ур.
    from ai_dm.rules.progression import required_choices

    hero = make_class_hero(class_id, SCORES)
    hero.sheet.skill_expertise = ["athletics", "stealth"] if class_id == "rogue" else []
    hero.sheet.primary.level = level
    assert required_choices(hero, registry, level) == expected
