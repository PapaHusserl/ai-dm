# К3 П2 (docs/plan-k3.md, «Тесты» П2, Р6): Магическое восстановление волшебника.
#   recover(hero, registry) -> строки лога: на коротком отдыхе возвращает ячейки суммарным кругом
#   до ⌈уровень волшебника / 2⌉ (не выше 5 круга), старший круг первым; тратит пул
#   `arcane_recovery` (1 в день, длинный отдых возвращает); пул 0 или нет пула -- пусто.
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "content"))

import pytest  # noqa: E402
from test_builder import wizard_choices  # noqa: E402
from test_class_kits import minimal_choices  # noqa: E402

from ai_dm.core.clock import GameClock  # noqa: E402
from ai_dm.core.rng import Rng  # noqa: E402
from ai_dm.rules.arcane_recovery import recover  # noqa: E402
from ai_dm.rules.builder import build_character  # noqa: E402
from ai_dm.rules.progression import level_up  # noqa: E402
from ai_dm.rules.rests import long_rest  # noqa: E402


def wizard_at(registry, level):
    hero = build_character(wizard_choices(), registry)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
    return hero


def empty_slots(hero):
    for name, pool in hero.creature.resources.items():
        if name.startswith("spell_slot:"):
            pool.current = 0


def slots(hero):
    pools = hero.creature.resources
    return {n: pools[f"spell_slot:{n}"].current for n in range(1, 6) if f"spell_slot:{n}" in pools}


def test_wizard_has_one_recovery_per_day(registry):
    assert wizard_at(registry, 1).creature.resources["arcane_recovery"].max == 1


def test_level_3_recovers_one_second_circle_slot(registry):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    log = recover(hero, registry)
    assert slots(hero) == {1: 0, 2: 1}
    assert len(log) == 1
    assert log == ["Магическое восстановление: ячейка 2 круга"]


def test_level_1_recovers_one_first_circle_slot(registry):
    hero = wizard_at(registry, 1)
    empty_slots(hero)
    recover(hero, registry)
    assert slots(hero) == {1: 1}


def test_level_2_recovers_one_first_circle_slot(registry):
    hero = wizard_at(registry, 2)
    empty_slots(hero)
    recover(hero, registry)
    assert slots(hero) == {1: 1}


def test_level_4_recovers_two_points_in_one_second_circle_slot(registry):
    hero = wizard_at(registry, 4)
    empty_slots(hero)
    recover(hero, registry)
    assert slots(hero) == {1: 0, 2: 1}


def test_level_5_recovers_the_third_circle_first(registry):
    hero = wizard_at(registry, 5)
    empty_slots(hero)
    log = recover(hero, registry)
    assert slots(hero) == {1: 0, 2: 0, 3: 1}
    assert log == ["Магическое восстановление: ячейка 3 круга"]


def test_level_5_mixes_two_and_one_when_third_circle_is_full(registry):
    hero = wizard_at(registry, 5)
    empty_slots(hero)
    full = hero.creature.resources["spell_slot:3"]
    full.current = full.max
    log = recover(hero, registry)
    assert log == ["Магическое восстановление: ячейка 2 круга, ячейка 1 круга"]
    pools = hero.creature.resources
    assert pools["spell_slot:2"].current == 1
    assert pools["spell_slot:1"].current == 1


def test_log_line_names_a_single_slot_without_multiplier(registry):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    assert recover(hero, registry) == ["Магическое восстановление: ячейка 2 круга"]


def test_log_line_repeats_equal_slots_with_multiplier(registry):
    hero = wizard_at(registry, 4)  # 2 очка, 2 круг полон -> две ячейки 1 круга
    empty_slots(hero)
    full = hero.creature.resources["spell_slot:2"]
    full.current = full.max
    assert recover(hero, registry) == ["Магическое восстановление: ячейки 1 круга ×2"]
    assert slots(hero)[1] == 2


def test_log_line_groups_circles_from_the_senior_one(registry):
    hero = wizard_at(registry, 5)  # 3 очка, 3 круг полон -> 2 круг + 1 круг
    empty_slots(hero)
    full = hero.creature.resources["spell_slot:3"]
    full.current = full.max
    assert recover(hero, registry) == [
        "Магическое восстановление: ячейка 2 круга, ячейка 1 круга"
    ]


def test_log_line_level_6_names_the_third_circle_slot(registry):
    hero = wizard_at(registry, 6)  # 3 очка: 3 круг пуст -> одна ячейка 3 круга
    empty_slots(hero)
    assert recover(hero, registry) == ["Магическое восстановление: ячейка 3 круга"]


def test_recovery_spends_the_pool(registry):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    recover(hero, registry)
    assert hero.creature.resources["arcane_recovery"].current == 0


def test_second_recovery_before_a_long_rest_gives_nothing(registry):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    recover(hero, registry)
    before = slots(hero)
    assert recover(hero, registry) == []
    assert slots(hero) == before


def test_long_rest_returns_the_pool(registry, cfg):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    recover(hero, registry)
    long_rest(hero, registry, GameClock(), cfg)
    assert hero.creature.resources["arcane_recovery"].current == 1


def test_full_slots_waste_nothing_and_keep_the_pool(registry):
    hero = wizard_at(registry, 3)
    assert recover(hero, registry) == []
    assert hero.creature.resources["arcane_recovery"].current == 1


def test_recovery_never_exceeds_max_slots(registry):
    hero = wizard_at(registry, 3)
    pools = hero.creature.resources
    pools["spell_slot:2"].current = pools["spell_slot:2"].max
    pools["spell_slot:1"].current = pools["spell_slot:1"].max - 1
    recover(hero, registry)
    assert pools["spell_slot:2"].current == pools["spell_slot:2"].max
    assert pools["spell_slot:1"].current == pools["spell_slot:1"].max


@pytest.mark.parametrize("class_id", ["cleric", "fighter", "rogue", "ranger"])
def test_other_classes_have_no_recovery(registry, class_id):
    hero = build_character(minimal_choices(class_id, "a"), registry)
    assert recover(hero, registry) == []
    assert "arcane_recovery" not in hero.creature.resources


def test_recovery_does_not_use_the_rng_or_clock(registry):
    hero = wizard_at(registry, 3)
    empty_slots(hero)
    rng, clock = Rng(1), GameClock()
    state, now = rng.state, clock.now_s
    recover(hero, registry)
    assert (rng.state, clock.now_s) == (state, now)
