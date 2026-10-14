# Партия К7д, шаг 0.1: death_saves.fatal / hit_while_down (вынесены из after_damage).
#   fatal(hero, death) -> "saved" | "dead": death = (cause, by, now_s, intervene); intervene(hero)
#     вернул бога -- "saved", героя не убиваем; иначе mark_dead (запись смерти) и "dead".
#   hit_while_down(hero, result, crit, death) -> "none" | "failure" | "dead": удар по лежащему.
#     none -- урон 0 или всё съели временные HP; dead -- урон >= hp_max или третий провал;
#     иначе стабильность снята, провал +1 (крит +2), успехи сохраняются.
import pytest
from test_death_saves import make_hero

from ai_dm.rules.damage import apply_damage
from ai_dm.rules.death_saves import fatal, hit_while_down


def death(intervene=None, cause="goal", by="g1", now_s=77):
    return (cause, by, now_s, intervene)


def blow(hero, registry, amount):
    return apply_damage(hero, amount, "slashing", registry)


def test_fatal_kills_and_records_the_death():
    hero = make_hero()
    assert fatal(hero, death()) == "dead"
    assert (hero.status, hero.death.cause, hero.death.by, hero.death.at_s) == (
        "dead", "goal", "g1", 77,
    )


def test_fatal_with_an_intervening_god_saves():
    hero = make_hero()
    assert fatal(hero, death(intervene=lambda h: "sun")) == "saved"
    assert (hero.status, hero.death) == ("active", None)


def test_fatal_when_the_god_stays_silent_kills():
    hero = make_hero()
    assert fatal(hero, death(intervene=lambda h: None)) == "dead"
    assert hero.status == "dead"


def test_hit_without_damage_is_none(registry):
    hero = make_hero()
    assert hit_while_down(hero, blow(hero, registry, 0), False, death()) == "none"
    assert hero.creature.death_saves.failures == 0


def test_hit_eaten_by_temp_hp_is_none(registry):
    hero = make_hero()
    hero.creature.hp_temp = 5
    assert hit_while_down(hero, blow(hero, registry, 3), False, death()) == "none"
    assert hero.creature.death_saves.failures == 0


def test_ordinary_hit_is_one_failure_and_drops_stability(registry):
    hero = make_hero(successes=2)
    hero.creature.death_saves.stable = True
    assert hit_while_down(hero, blow(hero, registry, 3), False, death()) == "failure"
    saves = hero.creature.death_saves
    assert (saves.failures, saves.successes, saves.stable) == (1, 2, False)


def test_critical_hit_is_two_failures(registry):
    hero = make_hero()
    assert hit_while_down(hero, blow(hero, registry, 3), True, death()) == "failure"
    assert hero.creature.death_saves.failures == 2


def test_third_failure_is_death(registry):
    hero = make_hero(failures=2)
    assert hit_while_down(hero, blow(hero, registry, 3), False, death()) == "dead"
    assert hero.status == "dead"


def test_crit_on_two_failures_is_death(registry):
    hero = make_hero(failures=1)
    assert hit_while_down(hero, blow(hero, registry, 3), True, death()) == "dead"


def test_massive_damage_is_death_at_hp_max(registry):
    hero = make_hero()
    assert hit_while_down(hero, blow(hero, registry, 12), False, death()) == "dead"


def test_damage_below_hp_max_is_not_massive(registry):
    hero = make_hero()
    assert hit_while_down(hero, blow(hero, registry, 11), False, death()) == "failure"


@pytest.mark.parametrize("amount, failures", [(12, 0), (3, 2)])
def test_god_can_save_from_either_death(registry, amount, failures):
    hero = make_hero(failures=failures)
    result = hit_while_down(hero, blow(hero, registry, amount), False, death(lambda h: "sun"))
    assert (result, hero.status) == ("saved", "active")


def test_fatal_asks_the_god_about_this_hero():
    hero = make_hero()
    assert fatal(hero, death(intervene=lambda h: "sun" if h is hero else None)) == "saved"


def test_one_point_hit_on_a_downed_hero_is_a_failure(registry):
    hero = make_hero()
    assert hit_while_down(hero, blow(hero, registry, 1), False, death()) == "failure"


def test_default_death_time_is_zero(registry):
    from ai_dm.rules.death_saves import after_damage

    hero = make_hero(hp_current=12)
    after_damage(hero, blow(hero, registry, 30), cause="goal")
    assert hero.death.at_s == 0
