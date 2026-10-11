# Ожидаемый API: ai_dm.rules.exhaustion (правила 2024, уровни 0..6)
#   exhaustion_penalty(level: int) -> int       -- -2 * level (0 -> 0)
#   add_exhaustion(hero, levels=1, *, now_s=0, cause) -> int     -- cause обязателен (keyword, D6):
#       без него TypeError
#       hero.creature.exhaustion += levels, не выше 6; возвращает новый уровень; levels < 1 ->
#       ValueError. Шестой уровень -- смерть (mortality_guard.mark_dead):
#       hero.status = "dead", hero.death =
#       DeathRecord(cause=cause, at_s=now_s, location_id=hero.location_id)
#   remove_exhaustion(creature: CreatureState, levels=1) -> int
#       уменьшает, не ниже 0; возвращает новый уровень (длинный отдых -- в test_rests.py)
import pytest

from ai_dm.rules.exhaustion import add_exhaustion, exhaustion_penalty, remove_exhaustion
from ai_dm.state.creature import CreatureState
from ai_dm.state.hero import BackgroundSpec, CharacterSheet, ClassLevel, HeroState


def make_hero(exhaustion=0):
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
        id="h1", ordinal=1, name="Арн", sheet=sheet, location_id="hall",
        creature=CreatureState(hp_current=12, hp_max=12, exhaustion=exhaustion),
    )


@pytest.mark.parametrize("level, penalty", [(0, 0), (1, -2), (2, -4), (3, -6), (5, -10), (6, -12)])
def test_exhaustion_penalty(level, penalty):
    assert exhaustion_penalty(level) == penalty


def test_add_exhaustion_raises_level_by_one():
    hero = make_hero()
    assert add_exhaustion(hero, cause="hazard") == 1
    assert hero.creature.exhaustion == 1


def test_add_exhaustion_several_levels():
    hero = make_hero(exhaustion=1)
    assert add_exhaustion(hero, 2, cause="hazard") == 3


def test_add_exhaustion_zero_levels_is_error():
    with pytest.raises(ValueError):
        add_exhaustion(make_hero(), 0, cause="hazard")


def test_level_5_hero_is_alive():
    hero = make_hero(exhaustion=4)
    add_exhaustion(hero, cause="hazard")
    assert hero.status == "active"
    assert hero.death is None


def test_level_6_kills_hero():
    hero = make_hero(exhaustion=5)
    add_exhaustion(hero, now_s=300, cause="hazard")
    assert hero.creature.exhaustion == 6
    assert hero.status == "dead"


def test_level_6_death_has_record_with_cause():
    hero = make_hero(exhaustion=5)
    add_exhaustion(hero, now_s=300, cause="hazard")
    assert hero.death.cause == "hazard"
    assert hero.death.at_s == 300
    assert hero.death.location_id == "hall"


def test_level_is_capped_at_6():
    hero = make_hero(exhaustion=4)
    assert add_exhaustion(hero, 5, cause="hazard") == 6
    assert hero.status == "dead"


def test_remove_exhaustion_lowers_level():
    creature = CreatureState(hp_current=7, hp_max=7, exhaustion=3)
    assert remove_exhaustion(creature) == 2
    assert creature.exhaustion == 2


def test_remove_exhaustion_not_below_zero():
    creature = CreatureState(hp_current=7, hp_max=7, exhaustion=1)
    assert remove_exhaustion(creature, 3) == 0
    assert creature.exhaustion == 0


def test_add_exhaustion_requires_cause():
    with pytest.raises(TypeError):
        add_exhaustion(make_hero())


def test_add_exhaustion_cause_is_keyword_only():
    with pytest.raises(TypeError):
        add_exhaustion(make_hero(), 1, 0, "hazard")


def test_level_6_death_keeps_given_cause_goal():
    hero = make_hero(exhaustion=5)
    add_exhaustion(hero, cause="goal")
    assert hero.death.cause == "goal"
