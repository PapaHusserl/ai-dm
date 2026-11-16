# К8с П2 (docs/plan-k8s.md, «Тесты» П2; умолчания): срок заклинания по кругу ячейки.
#   spell_seconds(spell, circle) -- ближайший ключ upcast.duration_by_circle <= круга, иначе
#     spell.duration_s: Метка охотника 1-2 круг -- 3600, 3-4 -- 28800 (8 ч), 5+ -- 86400 (24 ч);
#     заклинание без таблицы -- свой duration_s, мгновенное -- None;
#   start_concentration(hero, world, spell, circle, now_s) -- until_s по сроку круга;
#   usable_circles(hero, spell) -- у заклинания, чей апкаст -- только таблица сроков (Метка), круги:
#     базовый и ключи таблицы с ячейкой (Р-К8с-6 = а); остальные заклинания -- как было.
from ranger_kit import ranger_at

from ai_dm.core.rng import Rng
from ai_dm.rules.spellcasting import start_concentration, usable_circles
from ai_dm.state.creature import Expiry, ResourcePool
from ai_dm.state.world import WorldState

HOUR = 3600


def spell_seconds(spell, circle):
    from ai_dm.rules.spellcasting import spell_seconds as new_spell_seconds

    return new_spell_seconds(spell, circle)


def make_world():
    return WorldState(world_id="w1", rng=Rng(1).state)


def with_slots(hero, **sizes):
    for circle, size in sizes.items():
        hero.creature.resources[circle.replace("c", "spell_slot:")] = ResourcePool(
            current=size, max=max(size, 1),
        )
    return hero


# spell_seconds

def test_mark_for_circle_one_lasts_an_hour(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 1) == HOUR


def test_mark_for_circle_two_still_lasts_an_hour(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 2) == HOUR


def test_mark_for_circle_three_lasts_eight_hours(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 3) == 8 * HOUR


def test_mark_for_circle_four_lasts_eight_hours(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 4) == 8 * HOUR


def test_mark_for_circle_five_lasts_a_day(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 5) == 24 * HOUR


def test_mark_for_circle_nine_lasts_a_day(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), 9) == 24 * HOUR


def test_spell_without_a_table_keeps_its_own_duration(registry):
    assert spell_seconds(registry.get("spell", "fog_cloud"), 1) == HOUR


def test_spell_without_a_table_ignores_a_higher_circle(registry):
    assert spell_seconds(registry.get("spell", "fog_cloud"), 3) == HOUR


def test_instant_spell_has_no_duration(registry):
    assert spell_seconds(registry.get("spell", "cure_wounds"), 1) is None


# start_concentration

def test_concentration_on_a_third_circle_mark_ends_in_eight_hours(registry):
    hero = ranger_at(registry, 10)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 3, now_s=1000)
    assert hero.creature.concentration.until_s == 1000 + 8 * HOUR


def test_concentration_on_a_fifth_circle_mark_ends_in_a_day(registry):
    hero = ranger_at(registry, 10)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 5, now_s=1000)
    assert hero.creature.concentration.until_s == 1000 + 24 * HOUR


def test_concentration_on_a_first_circle_mark_ends_in_an_hour(registry):
    hero = ranger_at(registry, 10)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 1, now_s=1000)
    assert hero.creature.concentration.until_s == 1000 + HOUR


def test_concentration_keeps_the_circle_of_the_slot(registry):
    hero = ranger_at(registry, 10)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 3, now_s=1000)
    assert hero.creature.concentration.circle == 3


def test_concentration_without_now_has_no_deadline_at_any_circle(registry):
    hero = ranger_at(registry, 10)
    start_concentration(hero, make_world(), registry.get("spell", "hunters_mark"), 3)
    assert hero.creature.concentration.until_s is None


# usable_circles

def test_mark_circles_are_the_base_and_the_table_keys_with_a_slot(registry):
    hero = with_slots(ranger_at(registry, 10), c4=1, c5=1)
    assert usable_circles(hero, registry.get("spell", "hunters_mark")) == [1, 3, 5]


def test_mark_circle_four_is_not_offered_even_with_a_slot(registry):
    hero = with_slots(ranger_at(registry, 10), c4=1)
    assert 4 not in usable_circles(hero, registry.get("spell", "hunters_mark"))


def test_mark_circle_two_is_not_offered_even_with_a_slot(registry):
    hero = ranger_at(registry, 10)
    assert hero.creature.resources["spell_slot:2"].current > 0
    assert 2 not in usable_circles(hero, registry.get("spell", "hunters_mark"))


def test_mark_circle_three_needs_a_slot(registry):
    hero = with_slots(ranger_at(registry, 10), c3=0)
    assert usable_circles(hero, registry.get("spell", "hunters_mark")) == [1]


def test_mark_of_ranger_five_has_only_the_base_circle(registry):
    hero = ranger_at(registry, 5)
    assert usable_circles(hero, registry.get("spell", "hunters_mark")) == [1]


def test_spell_without_upcast_has_only_the_base_circle(registry):
    hero = ranger_at(registry, 10)
    assert usable_circles(hero, registry.get("spell", "fog_cloud")) == [1]


def test_spell_with_dice_upcast_keeps_every_circle_with_a_slot(registry):
    hero = ranger_at(registry, 10)
    assert usable_circles(hero, registry.get("spell", "cure_wounds")) == [1, 2, 3]


# add_spell_duration(hero, spell, now_s, circle=None) и spell_seconds(spell, None)

def spell_effects(hero):
    return [e for e in hero.creature.active_effects if e.kind == "spell"]


def add_duration(hero, spell, now_s, *circle):
    from ai_dm.rules.spellcasting import add_spell_duration

    add_spell_duration(hero, spell, now_s, *circle)


def test_add_duration_for_a_third_circle_mark_is_eight_hours(registry):
    hero = ranger_at(registry, 10)
    add_duration(hero, registry.get("spell", "hunters_mark"), 1000, 3)
    (effect,) = spell_effects(hero)
    assert effect.expires == Expiry(kind="seconds", value=1000 + 8 * HOUR)


def test_add_duration_for_a_first_circle_mark_is_an_hour(registry):
    hero = ranger_at(registry, 10)
    add_duration(hero, registry.get("spell", "hunters_mark"), 1000, 1)
    (effect,) = spell_effects(hero)
    assert effect.expires == Expiry(kind="seconds", value=1000 + HOUR)


def test_add_duration_without_circle_is_the_base_hour(registry):
    hero = ranger_at(registry, 10)
    add_duration(hero, registry.get("spell", "hunters_mark"), 1000)
    (effect,) = spell_effects(hero)
    assert effect.expires == Expiry(kind="seconds", value=1000 + HOUR)


def test_add_duration_of_an_instant_spell_adds_nothing(registry):
    hero = ranger_at(registry, 10)
    add_duration(hero, registry.get("spell", "cure_wounds"), 1000, 1)
    assert spell_effects(hero) == []


def test_spell_seconds_without_circle_is_the_base_duration(registry):
    assert spell_seconds(registry.get("spell", "hunters_mark"), None) == HOUR


def test_timed_circles_of_a_spell_without_upcast_is_none(registry):
    from ai_dm.rules.spellcasting import timed_circles

    assert timed_circles(registry.get("spell", "fog_cloud")) is None
