# Ожидаемый API: ai_dm.rules.progression (registry -- ContentRegistry, см. tests/unit/conftest.py)
#   Таблицы опыта и мастерства читаются из реестра (вид "table": xp, proficiency), поэтому
#   все функции принимают registry; реестр без SRD-слоя таблиц не содержит.
#   max_level(registry) = 20                     -- наибольший ключ таблицы xp
#                                                   (К0б; MAX_LEVEL удалён)
#   xp_for_level(level: int, registry) -> int    -- порог опыта: 1:0, 2:300, 3:900, 4:2700, 5:6500;
#                                                   level вне 1..5 -> ValueError
#   level_for_xp(xp: int, registry) -> int       -- максимальный уровень, порог которого достигнут;
#                                                   не выше MAX_LEVEL; xp < 0 -> ValueError
#   proficiency_bonus(level: int, registry) -> int
#                                                -- 1-4: +2, 5-8: +3 (level вне 1..5 -> ValueError)
#   can_level_up(hero: HeroState, registry) -> bool -- sheet.xp >= xp_for_level(level + 1) и
#                                                   level < MAX_LEVEL
#   level_up(hero, registry, *, hp_method="average", rng=None) -> None  -- мутирует героя:
# sheet.primary.level += 1; HP по выбору игрока (P2): "average" (по умолчанию) -- (hit_die // 2 +
# 1)
#       + мод. ТЕЛ; "roll" -- бросок кости хитов (rng.d(hit_die), без rng -> ValueError) + мод. ТЕЛ;
#       неизвестный метод -> ValueError; в обоих случаях минимум 1; прирост прибавляется к
#       creature.hp_max и creature.hp_current; на MAX_LEVEL -> ValueError.
#       Обновляет пулы ресурсов (creature.resources): новые ячейки заклинаний появляются,
#       максимум выросших пулов растёт (second_wind остаётся 2).
#       Опыт НЕ проверяет и не меняет: хватает ли опыта, проверяет вызывающий (can_level_up).
import pytest

from ai_dm.core.rng import Rng
from ai_dm.rules.derived import proficiency
from ai_dm.rules.progression import (
    can_level_up,
    check_level,
    level_for_xp,
    level_up,
    max_level,
    proficiency_bonus,
    xp_for_level,
)
from ai_dm.state.creature import CreatureState, ResourcePool
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_fighter():
    sheet = CharacterSheet(
        species_id="human",
        classes=[ClassLevel(class_id="fighter")], level_history=["fighter"] * 1,
        background=BackgroundSpec(
            name="Солдат",
            abilities=["str", "dex", "con"],
            skills=["athletics", "intimidation"],
            tool="dice_set",
            feat="savage_attacker",
        ),
        abilities={"str": 17, "dex": 13, "con": 15, "int": 8, "wis": 10, "cha": 12},
    )
    return HeroState(
        id="h1", ordinal=1, name="Арн", sheet=sheet,
        creature=CreatureState(hp_current=12, hp_max=12),
    )


def test_max_level_is_20_from_xp_table(registry):
    assert max_level(registry) == 20


def test_max_level_is_the_largest_key_of_xp_table(registry):
    rows = registry.get("table", "xp").rows
    assert max_level(registry) == max(int(key) for key in rows)


@pytest.mark.parametrize("level", [1, 5, 6, 19, 20])
def test_check_level_accepts_levels_up_to_20(level, registry):
    check_level(level, registry)


@pytest.mark.parametrize("level", [0, -1, 21, 100])
def test_check_level_rejects_out_of_range(level, registry):
    with pytest.raises(ValueError):
        check_level(level, registry)


@pytest.mark.parametrize("level, xp", [(1, 0), (2, 300), (3, 900), (4, 2700), (5, 6500)])
def test_xp_thresholds(level, xp, registry):
    assert xp_for_level(level, registry) == xp


@pytest.mark.parametrize("level", [0, -1, 21])
def test_xp_for_level_out_of_range_raises_value_error(level, registry):
    with pytest.raises(ValueError):
        xp_for_level(level, registry)


@pytest.mark.parametrize(
    "xp, level",
    [(0, 1), (299, 1), (300, 2), (899, 2), (900, 3), (2699, 3), (2700, 4), (6499, 4), (6500, 5)],
)
def test_level_for_xp_at_thresholds(xp, level, registry):
    assert level_for_xp(xp, registry) == level


def test_level_for_xp_is_capped_at_max_level(registry):
    assert level_for_xp(1_000_000, registry) == 20


@pytest.mark.parametrize(
    "xp, level",
    [(6499, 4), (6500, 5), (14000, 6), (355000, 20), (354999, 19), (305000, 19), (304999, 18)],
)
def test_level_for_xp_above_level_5(xp, level, registry):
    assert level_for_xp(xp, registry) == level


def test_level_for_negative_xp_raises_value_error(registry):
    with pytest.raises(ValueError):
        level_for_xp(-1, registry)


@pytest.mark.parametrize("level, bonus", [(1, 2), (2, 2), (3, 2), (4, 2), (5, 3)])
def test_proficiency_bonus_by_level(level, bonus, registry):
    assert proficiency_bonus(level, registry) == bonus


@pytest.mark.parametrize(
    "level, bonus", [(8, 3), (9, 4), (12, 4), (13, 5), (16, 5), (17, 6), (20, 6)]
)
def test_proficiency_bonus_up_to_level_20(level, bonus, registry):
    assert proficiency_bonus(level, registry) == bonus


def test_proficiency_bonus_level_21_raises_value_error(registry):
    with pytest.raises(ValueError):
        proficiency_bonus(21, registry)


def test_proficiency_bonus_level_0_raises_value_error(registry):
    with pytest.raises(ValueError):
        proficiency_bonus(0, registry)


def test_can_level_up_false_below_threshold(registry):
    hero = make_fighter()
    hero.sheet.xp = 299
    assert can_level_up(hero, registry) is False


def test_can_level_up_true_at_threshold(registry):
    hero = make_fighter()
    hero.sheet.xp = 300
    assert can_level_up(hero, registry) is True


def test_can_level_up_true_at_level_5_with_enough_xp(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    hero.sheet.xp = 14000
    assert can_level_up(hero, registry) is True


def test_can_level_up_false_at_level_5_below_threshold(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    hero.sheet.xp = 13999
    assert can_level_up(hero, registry) is False


def test_can_level_up_true_at_level_19_with_enough_xp(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 19
    hero.sheet.xp = 355000
    assert can_level_up(hero, registry) is True


def test_can_level_up_false_at_max_level(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 20
    hero.sheet.xp = 10_000_000
    assert can_level_up(hero, registry) is False


def test_level_up_raises_level_by_one(registry):
    hero = make_fighter()
    level_up(hero, registry)
    assert hero.sheet.level == 2


def test_level_up_adds_average_hp_plus_con_modifier_to_max(registry):
    hero = make_fighter()
    level_up(hero, registry)
    # d10: среднее 6, мод. ТЕЛ (15) +2
    assert hero.creature.hp_max == 12 + 8


def test_level_up_adds_same_hp_to_current(registry):
    hero = make_fighter()
    hero.creature.hp_current = 5
    level_up(hero, registry)
    assert hero.creature.hp_current == 5 + 8


def test_level_up_uses_class_hit_die(registry):
    hero = make_fighter()
    hero.sheet.primary.class_id = "wizard"
    level_up(hero, registry)
    # d6: среднее 4, мод. ТЕЛ +2
    assert hero.creature.hp_max == 12 + 6


def test_level_up_does_not_change_xp(registry):
    hero = make_fighter()
    hero.sheet.xp = 300
    level_up(hero, registry)
    assert hero.sheet.xp == 300


def test_four_level_ups_reach_level_5_with_proficiency_3(registry):
    hero = make_fighter()
    for _ in range(4):
        level_up(hero, registry)
    assert hero.sheet.level == 5
    assert proficiency(hero, registry) == 3
    assert hero.creature.hp_max == 12 + 4 * 8


def test_level_up_at_max_level_raises_value_error(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 20
    with pytest.raises(ValueError):
        level_up(hero, registry)


def test_level_up_at_max_level_does_not_change_hp(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 20
    with pytest.raises(ValueError):
        level_up(hero, registry)
    assert hero.creature.hp_max == 12


def test_level_up_from_5_to_6_works(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 5
    level_up(hero, registry)
    assert hero.sheet.level == 6


def test_level_up_from_19_to_20_works(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 19
    level_up(hero, registry)
    assert hero.sheet.level == 20


# level_up обновляет пулы ресурсов

def make_wizard_with_slots():
    hero = make_fighter()
    hero.sheet.primary.class_id = "wizard"
    hero.creature.resources["spell_slot:1"] = ResourcePool(current=2, max=2)
    return hero


def test_level_up_wizard_grows_first_circle_slots(registry):
    hero = make_wizard_with_slots()
    level_up(hero, registry)
    assert hero.creature.resources["spell_slot:1"].max == 3


def test_level_up_wizard_to_level_3_adds_second_circle_pool(registry):
    hero = make_wizard_with_slots()
    level_up(hero, registry)
    level_up(hero, registry)
    assert hero.creature.resources["spell_slot:1"].max == 4
    assert hero.creature.resources["spell_slot:2"].max == 2


def test_level_up_wizard_to_level_5_has_third_circle_pool(registry):
    hero = make_wizard_with_slots()
    for _ in range(4):
        level_up(hero, registry)
    assert hero.creature.resources["spell_slot:3"].max == 2


def test_level_up_wizard_new_pool_is_not_over_max(registry):
    hero = make_wizard_with_slots()
    level_up(hero, registry)
    level_up(hero, registry)
    pool = hero.creature.resources["spell_slot:2"]
    assert 0 <= pool.current <= pool.max


def test_level_up_does_not_raise_current_above_max(registry):
    hero = make_wizard_with_slots()
    level_up(hero, registry)
    pool = hero.creature.resources["spell_slot:1"]
    assert pool.current <= pool.max


def test_level_up_fighter_creates_second_wind_pool_with_max_2(registry):
    hero = make_fighter()
    level_up(hero, registry)
    assert hero.creature.resources["second_wind"].max == 2


def test_level_up_fighter_keeps_second_wind_max_2(registry):
    hero = make_fighter()
    hero.creature.resources["second_wind"] = ResourcePool(current=1, max=2)
    level_up(hero, registry)
    assert hero.creature.resources["second_wind"].max == 2
    assert hero.creature.resources["second_wind"].current == 1


def test_level_up_fighter_gets_no_spell_slot_pools(registry):
    hero = make_fighter()
    level_up(hero, registry)
    assert not [key for key in hero.creature.resources if key.startswith("spell_slot")]


def test_level_up_does_not_check_xp(registry):
    hero = make_fighter()
    assert hero.sheet.xp == 0
    assert can_level_up(hero, registry) is False
    level_up(hero, registry)
    assert hero.sheet.level == 2


# таблицы берутся из реестра

def test_progression_needs_srd_tables_in_registry(tmp_path):
    from ai_dm.content.loader import load_registry

    empty = load_registry([tmp_path], include_srd=False)
    with pytest.raises(KeyError):
        xp_for_level(2, empty)


# выбор метода HP при повышении уровня (P2)

class ScriptedRng(Rng):
    def __init__(self, *rolls):
        super().__init__(1)
        self.rolls = list(rolls)

    def randbelow(self, n):
        sides, face = self.rolls.pop(0)
        assert sides == n
        return face - 1


def test_level_up_default_method_is_average(registry):
    hero = make_fighter()
    level_up(hero, registry)
    assert hero.creature.hp_max == 12 + 8


def test_level_up_average_explicit_matches_default(registry):
    hero = make_fighter()
    level_up(hero, registry, hp_method="average")
    assert hero.creature.hp_max == 12 + 8
    assert hero.creature.hp_current == 12 + 8


def test_level_up_average_ignores_rng(registry):
    hero = make_fighter()
    rng = ScriptedRng()
    level_up(hero, registry, hp_method="average", rng=rng)
    assert hero.creature.hp_max == 12 + 8


def test_level_up_roll_adds_die_and_con_mod(registry):
    # d10 у воина, ТЕЛ 15 -> +2
    hero = make_fighter()
    level_up(hero, registry, hp_method="roll", rng=ScriptedRng((10, 7)))
    assert hero.creature.hp_max == 12 + 9
    assert hero.creature.hp_current == 12 + 9
    assert hero.sheet.level == 2


def test_level_up_roll_max_die(registry):
    hero = make_fighter()
    level_up(hero, registry, hp_method="roll", rng=ScriptedRng((10, 10)))
    assert hero.creature.hp_max == 12 + 12


def test_level_up_roll_draws_exactly_one_die(registry):
    hero = make_fighter()
    rng = ScriptedRng((10, 4), (10, 4))
    level_up(hero, registry, hp_method="roll", rng=rng)
    assert len(rng.rolls) == 1


def test_level_up_roll_uses_class_hit_die(registry):
    hero = make_fighter()
    hero.sheet.primary.class_id = "wizard"
    level_up(hero, registry, hp_method="roll", rng=ScriptedRng((6, 3)))
    assert hero.creature.hp_max == 12 + 3 + 2


def test_level_up_roll_gain_is_at_least_one(registry):
    hero = make_fighter()
    hero.sheet.abilities["con"] = 3
    level_up(hero, registry, hp_method="roll", rng=ScriptedRng((10, 1)))
    assert hero.creature.hp_max == 12 + 1
    assert hero.creature.hp_current == 12 + 1


def test_level_up_average_gain_is_at_least_one(registry):
    hero = make_fighter()
    hero.sheet.abilities["con"] = 1
    hero.sheet.primary.class_id = "wizard"
    level_up(hero, registry)
    assert hero.creature.hp_max == 12 + 1


def test_level_up_roll_without_rng_is_error_and_changes_nothing(registry):
    hero = make_fighter()
    with pytest.raises(ValueError):
        level_up(hero, registry, hp_method="roll")
    assert hero.sheet.level == 1
    assert hero.creature.hp_max == 12


def test_level_up_unknown_method_is_error(registry):
    hero = make_fighter()
    with pytest.raises(ValueError):
        level_up(hero, registry, hp_method="max")
    assert hero.sheet.level == 1


def test_level_up_roll_at_max_level_is_error(registry):
    hero = make_fighter()
    hero.sheet.primary.level = 20
    with pytest.raises(ValueError):
        level_up(hero, registry, hp_method="roll", rng=ScriptedRng((10, 5)))
    assert hero.creature.hp_max == 12


def test_level_up_roll_is_deterministic_by_seed(registry):
    first, second = make_fighter(), make_fighter()
    level_up(first, registry, hp_method="roll", rng=Rng(11))
    level_up(second, registry, hp_method="roll", rng=Rng(11))
    assert first.creature.hp_max == second.creature.hp_max
