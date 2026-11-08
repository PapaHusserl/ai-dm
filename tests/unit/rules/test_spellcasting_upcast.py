# К1 «Апкаст» (docs/plan-k1.md, п. 3.1, В8а, В9а, В10): повышение круга у заклинаний с upcast.
#   circle_allowed(spell, circle, free) -- круг заклинания всегда; выше -- только при spell.upcast и
#     не для бесплатного применения; ниже и заговор не на 0 -- нет;
#   upcast_steps(spell, circle) -- на сколько кругов выше базового (0 без upcast и не выше);
#   upcast_dice(base, step, steps) -- «2d8» + 2 x «2d8» = «6d8», модификатор базы сохраняется,
#     разные грани -> ValueError;
#   usable_circles(hero, spell) -- [0] у заговора, иначе круги >= spell.level с ячейкой по
#     возрастанию; без upcast -- только spell.level;
#   cast_problem: bad_circle (текст про повышение), no_slot по ячейке запрошенного круга;
#   spend_cast(hero, registry, spell, free, circle) -- списывает spell_slot:<circle>;
#   roll_heal(..., circle) -- кости растут по per_slot_level.
import pytest
from combat_kit import ScriptedRng, make_wizard
from ranger_kit import make_ranger

from ai_dm.rules.cast_checks import default_cast_check_registry
from ai_dm.rules.spellcasting import (
    cast_problem,
    circle_allowed,
    roll_heal,
    spend_cast,
    upcast_dice,
    upcast_steps,
    usable_circles,
)
from ai_dm.state.creature import ResourcePool

CHECKS = default_cast_check_registry()


def caster(registry, slot1=2, slot2=2):
    hero = make_wizard(registry)
    hero.sheet.abilities["int"] = 10
    hero.sheet.prepared_of().extend(["cure_wounds", "bless", "hunters_mark", "fog_cloud"])
    pools = hero.creature.resources
    pools["spell_slot:1"] = ResourcePool(current=slot1, max=2)
    pools["spell_slot:2"] = ResourcePool(current=slot2, max=2)
    return hero


def spell_of(registry, spell_id):
    return registry.get("spell", spell_id)


def problem(registry, hero, spell_id, circle, free=False):
    spell = spell_of(registry, spell_id)
    return cast_problem(hero, spell, circle, free, registry, CHECKS)


def slot(hero, circle):
    return hero.creature.resources[f"spell_slot:{circle}"].current


# upcast_dice

def test_upcast_dice_adds_whole_steps():
    assert upcast_dice("2d8", "2d8", 2) == "6d8"


def test_upcast_dice_keeps_the_base_modifier():
    assert upcast_dice("1d4+1", "1d4", 1) == "2d4+1"


def test_upcast_dice_with_one_step():
    assert upcast_dice("3d6", "1d6", 1) == "4d6"


def test_upcast_dice_with_zero_steps_is_the_base():
    assert upcast_dice("2d8", "2d8", 0) == "2d8"


def test_upcast_dice_with_different_sides_is_an_error():
    with pytest.raises(ValueError):
        upcast_dice("1d6", "1d8", 1)


# upcast_steps

def test_steps_without_upcast_is_zero_even_for_a_higher_circle(registry):
    assert upcast_steps(spell_of(registry, "hunters_mark"), 3) == 0


def test_steps_at_the_base_circle_is_zero(registry):
    assert upcast_steps(spell_of(registry, "cure_wounds"), 1) == 0


def test_steps_counts_circles_above_the_base(registry):
    spell = spell_of(registry, "cure_wounds")
    assert upcast_steps(spell, 2) == 1
    assert upcast_steps(spell, 4) == 3


def test_steps_below_the_base_is_zero(registry):
    assert upcast_steps(spell_of(registry, "cure_wounds"), 0) == 0


# circle_allowed

def test_base_circle_is_allowed_free_or_not(registry):
    spell = spell_of(registry, "hunters_mark")
    assert circle_allowed(spell, spell.level, False)
    assert circle_allowed(spell, spell.level, True)


def test_higher_circle_is_allowed_with_upcast(registry):
    assert circle_allowed(spell_of(registry, "cure_wounds"), 2, False)


def test_higher_circle_is_not_allowed_without_upcast(registry):
    assert not circle_allowed(spell_of(registry, "hunters_mark"), 2, False)
    assert not circle_allowed(spell_of(registry, "fog_cloud"), 2, False)


def test_higher_circle_is_not_allowed_for_a_free_cast(registry):
    assert not circle_allowed(spell_of(registry, "cure_wounds"), 2, True)


def test_lower_circle_is_not_allowed(registry):
    assert not circle_allowed(spell_of(registry, "cure_wounds"), 0, False)


def test_cantrip_is_allowed_only_at_zero(registry):
    spell = spell_of(registry, "fire_bolt")
    assert circle_allowed(spell, 0, False)
    assert not circle_allowed(spell, 1, False)


# usable_circles

def test_usable_circles_of_an_upcast_spell_lists_circles_with_slots(registry):
    assert usable_circles(caster(registry), spell_of(registry, "cure_wounds")) == [1, 2]


def test_usable_circles_without_upcast_is_the_base_circle_only(registry):
    assert usable_circles(caster(registry), spell_of(registry, "hunters_mark")) == [1]


def test_usable_circles_of_a_cantrip_is_zero(registry):
    assert usable_circles(caster(registry), spell_of(registry, "fire_bolt")) == [0]


def test_usable_circles_skips_the_empty_base_circle(registry):
    hero = caster(registry, slot1=0)
    assert usable_circles(hero, spell_of(registry, "cure_wounds")) == [2]


def test_usable_circles_without_the_base_slot_for_a_plain_spell_is_empty(registry):
    hero = caster(registry, slot1=0)
    assert usable_circles(hero, spell_of(registry, "hunters_mark")) == []


def test_usable_circles_without_slots_is_empty(registry):
    hero = caster(registry, slot1=0, slot2=0)
    assert usable_circles(hero, spell_of(registry, "cure_wounds")) == []


def test_usable_circles_never_goes_below_the_spell_level(registry):
    hero = caster(registry)
    hero.creature.resources["spell_slot:2"].current = 0
    assert usable_circles(hero, spell_of(registry, "cure_wounds")) == [1]


def test_usable_circles_are_ascending_over_three_circles(registry):
    hero = caster(registry)
    hero.creature.resources["spell_slot:3"] = ResourcePool(current=1, max=1)
    assert usable_circles(hero, spell_of(registry, "cure_wounds")) == [1, 2, 3]


# cast_problem

def test_problem_none_for_an_upcast_with_a_slot(registry):
    assert problem(registry, caster(registry), "cure_wounds", 2) is None


def test_problem_bad_circle_for_a_spell_without_upcast(registry):
    code, message = problem(registry, caster(registry), "hunters_mark", 2)
    assert code == "bad_circle"
    assert "повышение" in message


def test_problem_bad_circle_text_is_exact(registry):
    assert problem(registry, caster(registry), "hunters_mark", 2) == (
        "bad_circle",
        "Метка охотника: круг 1, запрошен 2; повышение — только у "
        "заклинаний с усилением и не для бесплатного применения (0 для заговоров)",
    )


def test_problem_bad_circle_for_a_free_upcast(registry):
    hero = caster(registry)
    hero.creature.resources["favored_enemy"] = ResourcePool(current=2, max=2)
    assert problem(registry, hero, "cure_wounds", 2, free=True)[0] == "bad_circle"


def test_problem_bad_circle_for_zero_circle_of_a_leveled_spell(registry):
    assert problem(registry, caster(registry), "cure_wounds", 0)[0] == "bad_circle"


def test_problem_no_slot_names_the_requested_circle(registry):
    hero = caster(registry, slot2=0)
    code, message = problem(registry, hero, "cure_wounds", 2)
    assert code == "no_slot"
    assert "нет ячейки 2 круга" in message


def test_problem_no_slot_when_the_requested_circle_is_missing_altogether(registry):
    hero = caster(registry)
    del hero.creature.resources["spell_slot:2"]
    assert problem(registry, hero, "cure_wounds", 2)[0] == "no_slot"


def test_problem_base_circle_ignores_an_empty_higher_circle(registry):
    assert problem(registry, caster(registry, slot2=0), "cure_wounds", 1) is None


def test_problem_empty_base_circle_is_no_slot_even_with_a_higher_slot(registry):
    code, message = problem(registry, caster(registry, slot1=0), "cure_wounds", 1)
    assert code == "no_slot"
    assert "нет ячейки 1 круга" in message


def test_problem_slot_with_exactly_one_charge_is_enough(registry):
    # К3 П5, 236: последняя ячейка круга ещё позволяет сотворить
    hero = caster(registry)
    hero.creature.resources["spell_slot:1"].current = 1
    assert problem(registry, hero, "cure_wounds", 1) is None


def test_problem_known_cantrip_is_castable_and_unknown_is_not(registry):
    hero = caster(registry)
    hero.sheet.known_of()[:] = []
    expected = ("not_known", "заговор Огненный снаряд герой не знает")
    assert problem(registry, hero, "fire_bolt", 0) == expected
    hero.sheet.known_of().append("fire_bolt")
    assert problem(registry, hero, "fire_bolt", 0) is None


def test_problem_free_cast_without_charges_is_no_free_cast(registry):
    hero = make_ranger(registry)
    hero.creature.resources["favored_enemy"].current = 0
    spell = spell_of(registry, "hunters_mark")
    result = cast_problem(hero, spell, 1, True, registry, CHECKS)
    assert result == ("no_free_cast", "нет бесплатных применений для Метка охотника")


class ScriptedChecks:
    # реестр проверок заклинания с записью вызовов
    def __init__(self, *checks):
        self.checks = list(checks)
        self.calls = []

    def check(self, caster, spell_id, registry):
        self.calls.append((caster, spell_id, registry))
        return self.checks


def test_problem_asks_the_checks_about_this_hero_spell_and_registry(registry):
    hero = caster(registry)
    checks = ScriptedChecks()
    cast_problem(hero, spell_of(registry, "cure_wounds"), 1, False, registry, checks)
    assert checks.calls == [(hero, "cure_wounds", registry)]


def test_problem_forbidden_check_blocks_the_cast_with_its_reason(registry):
    from ai_dm.rules.cast_checks import CastCheck

    checks = ScriptedChecks(CastCheck(kind="forbidden", reason="отлучение"))
    result = cast_problem(
        caster(registry), spell_of(registry, "cure_wounds"), 1, False, registry, checks
    )
    assert result == ("forbidden", "Лечение ран недоступно: отлучение")


def test_problem_ability_check_does_not_block_the_cast(registry):
    from ai_dm.rules.cast_checks import CastCheck

    checks = ScriptedChecks(CastCheck(kind="ability_check", ability="wis", dc=10))
    result = cast_problem(
        caster(registry), spell_of(registry, "cure_wounds"), 1, False, registry, checks
    )
    assert result is None


# spend_cast

def test_spend_takes_the_slot_of_the_requested_circle(registry):
    hero = caster(registry)
    spend_cast(hero, registry, spell_of(registry, "cure_wounds"), False, 2)
    assert (slot(hero, 1), slot(hero, 2)) == (2, 1)


def test_spend_at_the_base_circle_leaves_the_higher_one(registry):
    hero = caster(registry)
    spend_cast(hero, registry, spell_of(registry, "cure_wounds"), False, 1)
    assert (slot(hero, 1), slot(hero, 2)) == (1, 2)


def test_spend_of_a_cantrip_takes_nothing(registry):
    hero = caster(registry)
    spend_cast(hero, registry, spell_of(registry, "fire_bolt"), False, 0)
    assert (slot(hero, 1), slot(hero, 2)) == (2, 2)


def test_spend_free_takes_the_pool_not_the_slot(registry):
    hero = make_ranger(registry)
    spend_cast(hero, registry, spell_of(registry, "hunters_mark"), True, 1)
    assert hero.creature.resources["favored_enemy"].current == 1
    assert slot(hero, 1) == 2


# roll_heal

def test_heal_at_the_base_circle_rolls_the_base_dice(registry):
    rng = ScriptedRng(d8=[3, 4])
    total, text = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng, 1)
    assert total == 7
    assert "2d8" in text


def test_heal_without_circle_rolls_the_base_dice(registry):
    rng = ScriptedRng(d8=[3, 4])
    total, _ = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng)
    assert total == 7


def test_heal_at_the_second_circle_rolls_four_dice(registry):
    rng = ScriptedRng(d8=[3, 4, 5, 6])
    total, text = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng, 2)
    assert total == 18
    assert "4d8" in text
    assert rng.left("d8") == 0


def test_heal_at_the_third_circle_rolls_six_dice(registry):
    rng = ScriptedRng(d8=[1, 1, 1, 1, 1, 1])
    total, _ = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng, 3)
    assert total == 6


# текст лечения: кости, значения, знак и подпись характеристики

def test_heal_text_shows_dice_rolls_and_a_positive_modifier(registry):
    hero = caster(registry)
    hero.sheet.abilities["int"] = 16
    rng = ScriptedRng(d8=[3, 4])
    total, text = roll_heal(spell_of(registry, "cure_wounds"), hero, registry, rng, 1)
    assert total == 10
    assert text == "2d8 (3+4) + 3 Инт = 10"


def test_heal_text_shows_a_negative_modifier(registry):
    hero = caster(registry)
    hero.sheet.abilities["int"] = 8
    rng = ScriptedRng(d8=[3, 4])
    total, text = roll_heal(spell_of(registry, "cure_wounds"), hero, registry, rng, 1)
    assert total == 6
    assert text == "2d8 (3+4) - 1 Инт = 6"


def test_heal_text_for_a_zero_modifier_has_a_plus(registry):
    rng = ScriptedRng(d8=[3, 4])
    _, text = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng, 1)
    assert text == "2d8 (3+4) + 0 Инт = 7"


def fixed_bonus_heal(registry, value, upcast=True):
    # К3 П5, 236: лечение без модификатора заклинателя -- фиксированная добавка value
    spell = spell_of(registry, "cure_wounds").model_copy(deep=True)
    spell.effects[0].add = None
    spell.effects[0].value = value
    if not upcast:
        spell.upcast = None
    return spell


@pytest.mark.parametrize(
    ("value", "tail"), [(3, " + 3 = 10"), (1, " + 1 = 8"), (-2, " - 2 = 5"), (0, " = 7")]
)
def test_heal_text_of_a_fixed_bonus_shows_sign_and_size(registry, value, tail):
    rng = ScriptedRng(d8=[3, 4])
    _, text = roll_heal(fixed_bonus_heal(registry, value), caster(registry), registry, rng, 1)
    assert text == "2d8 (3+4)" + tail


def test_heal_without_upcast_rolls_base_dice_at_the_base_circle(registry):
    rng = ScriptedRng(d8=[3, 4])
    spell = fixed_bonus_heal(registry, 0, upcast=False)
    total, text = roll_heal(spell, caster(registry), registry, rng, 1)
    assert (total, text) == (7, "2d8 (3+4) = 7")


def test_upcast_heal_text_lists_all_rolls(registry):
    rng = ScriptedRng(d8=[1, 2, 3, 4])
    _, text = roll_heal(spell_of(registry, "cure_wounds"), caster(registry), registry, rng, 2)
    assert text == "4d8 (1+2+3+4) + 0 Инт = 10"
