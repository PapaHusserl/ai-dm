# К1 «Смена подготовленных после длинного отдыха» (docs/K1-PLAN.md, п. 4.1, 4.3; В5а, В6а, Q2а).
#   Данные класса: spellcasting.prepared_swap -- сколько подготовленных можно заменить (int), "all"
#     или None (нельзя): следопыт 1, жрец и волшебник "all", у воина и плута spellcasting нет.
#   swap_problem(hero, registry, drop, take) -> (код, сообщение) | None, порядок проверок:
#     no_spellcasting, swap_limit (целый лимит: len(drop) или len(take) больше), bad_swap (повторы),
#     unknown_spell (с «допустимые id»), not_prepared (drop: нет в prepared_of или always_prepared),
#     already_prepared, bad_spell (не из списка класса, заговор, круг выше максимального),
#     prepared_limit (len(prepared) - len(drop) + len(take) > prepared_limit).
#   swap_prepared(hero, registry, drop, take) -- убирает drop из prepared_of, добавляет take в
#     prepared_of и (если нет) в known_of; always_prepared и порядок остальных не трогает.
from combat_kit import make_fighter, make_wizard
from ranger_kit import make_class_hero, ranger_at

from ai_dm.rules.progression import level_up
from ai_dm.rules.spellcasting import swap_prepared, swap_problem

ABILITIES = {"str": 10, "dex": 10, "con": 10, "int": 10, "wis": 16, "cha": 10}


def ranger(registry, level=2):
    hero = ranger_at(registry, level)
    hero.sheet.known_of()[:] = ["cure_wounds", "fog_cloud"]
    hero.sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud"]
    return hero


def cleric(registry, level=3):
    hero = make_class_hero("cleric", ABILITIES)
    while hero.sheet.level < level:
        level_up(hero, registry, hp_method="average")
    return hero


def code_of(result):
    return None if result is None else result[0]


# данные классов

def test_ranger_swaps_one_spell(registry):
    assert registry.get("class", "ranger").spellcasting.prepared_swap == 1


def test_cleric_swaps_any_number(registry):
    assert registry.get("class", "cleric").spellcasting.prepared_swap == "all"


def test_wizard_swaps_any_number(registry):
    assert registry.get("class", "wizard").spellcasting.prepared_swap == "all"


def test_fighter_and_rogue_have_no_spellcasting(registry):
    assert registry.get("class", "fighter").spellcasting is None
    assert registry.get("class", "rogue").spellcasting is None


# swap_problem: допустимые смены

def test_ranger_swaps_one_for_one(registry):
    assert swap_problem(ranger(registry), registry, ["fog_cloud"], ["longstrider"]) is None


def test_empty_swap_is_fine(registry):
    assert swap_problem(ranger(registry), registry, [], []) is None


def test_ranger_takes_a_new_spell_into_a_free_slot(registry):
    # лимит 3 на 2 ур., подготовлено 2
    assert swap_problem(ranger(registry), registry, [], ["longstrider"]) is None


def test_ranger_drops_without_taking(registry):
    assert swap_problem(ranger(registry), registry, ["fog_cloud"], []) is None


def test_ranger_takes_a_second_circle_spell_when_the_circle_is_open(registry):
    hero = ranger(registry, 5)
    assert swap_problem(hero, registry, ["fog_cloud"], ["spike_growth"]) is None


def test_cleric_swaps_three_at_once(registry):
    hero = cleric(registry)
    take = ["bless", "cure_wounds", "lesser_restoration"]
    assert swap_problem(hero, registry, [], take) is None


def test_wizard_swaps_two_at_once(registry):
    hero = make_wizard(registry)
    hero.sheet.prepared_of()[:] = ["magic_missile", "burning_hands"]
    assert swap_problem(hero, registry, ["magic_missile", "burning_hands"],
                        ["alarm", "fog_cloud"]) is None


# swap_problem: отказы

def test_ranger_cannot_drop_two(registry):
    hero = ranger(registry)
    problem = swap_problem(hero, registry, ["fog_cloud", "cure_wounds"], ["longstrider"])
    assert code_of(problem) == "swap_limit"


def test_ranger_cannot_take_two(registry):
    hero = ranger(registry)
    problem = swap_problem(hero, registry, ["fog_cloud"], ["longstrider", "alarm"])
    assert code_of(problem) == "swap_limit"


def test_unknown_spell_lists_allowed_ids(registry):
    problem = swap_problem(ranger(registry), registry, [], ["no_such_spell"])
    assert code_of(problem) == "unknown_spell"
    assert "допустимые id" in problem[1]


def test_dropping_a_spell_that_is_not_prepared_is_not_prepared(registry):
    problem = swap_problem(ranger(registry), registry, ["longstrider"], [])
    assert code_of(problem) == "not_prepared"


def test_always_prepared_spell_cannot_be_dropped(registry):
    problem = swap_problem(ranger(registry), registry, ["hunters_mark"], [])
    assert code_of(problem) == "not_prepared"


def test_taking_an_already_prepared_spell_is_already_prepared(registry):
    problem = swap_problem(ranger(registry), registry, [], ["cure_wounds"])
    assert code_of(problem) == "already_prepared"


def test_taking_the_always_prepared_spell_is_already_prepared(registry):
    problem = swap_problem(ranger(registry), registry, [], ["hunters_mark"])
    assert code_of(problem) == "already_prepared"


def test_taking_a_spell_of_another_class_is_bad_spell(registry):
    problem = swap_problem(ranger(registry), registry, ["fog_cloud"], ["burning_hands"])
    assert code_of(problem) == "bad_spell"


def test_taking_a_spell_of_a_closed_circle_is_bad_spell(registry):
    problem = swap_problem(ranger(registry, 2), registry, ["fog_cloud"], ["spike_growth"])
    assert code_of(problem) == "bad_spell"


def test_taking_a_cantrip_is_bad_spell(registry):
    hero = make_wizard(registry)
    problem = swap_problem(hero, registry, [], ["fire_bolt"])
    assert code_of(problem) == "bad_spell"


def test_exceeding_the_prepared_limit_is_prepared_limit(registry):
    hero = ranger(registry)
    hero.sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud", "longstrider"]
    problem = swap_problem(hero, registry, [], ["alarm"])
    assert code_of(problem) == "prepared_limit"


def test_swap_at_a_full_limit_is_fine_when_the_counts_match(registry):
    hero = ranger(registry)
    hero.sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud", "longstrider"]
    assert swap_problem(hero, registry, ["longstrider"], ["alarm"]) is None


def test_fighter_has_no_spellcasting(registry):
    problem = swap_problem(make_fighter(registry), registry, [], ["bless"])
    assert code_of(problem) == "no_spellcasting"


def test_repeats_in_drop_are_bad_swap(registry):
    hero = cleric(registry)
    hero.sheet.prepared_of()[:] = ["bless"]
    problem = swap_problem(hero, registry, ["bless", "bless"], [])
    assert code_of(problem) == "bad_swap"


def test_repeats_in_take_are_bad_swap(registry):
    problem = swap_problem(cleric(registry), registry, [], ["bless", "bless"])
    assert code_of(problem) == "bad_swap"


# swap_prepared

def test_swap_replaces_the_dropped_spell(registry):
    hero = ranger(registry)
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert hero.sheet.prepared_of() == ["cure_wounds", "longstrider"]


def test_swap_puts_the_new_spell_into_known(registry):
    hero = ranger(registry)
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert "longstrider" in hero.sheet.known_of()


def test_swap_does_not_duplicate_a_known_spell(registry):
    hero = ranger(registry)
    hero.sheet.known_of().append("longstrider")
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert hero.sheet.known_of().count("longstrider") == 1


def test_swap_keeps_the_dropped_spell_in_known(registry):
    hero = ranger(registry)
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert "fog_cloud" in hero.sheet.known_of()


def test_swap_keeps_always_prepared(registry):
    hero = ranger(registry)
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert "hunters_mark" not in hero.sheet.prepared_of()
    assert hero.sheet.spells_always_prepared == []


def test_swap_keeps_the_order_of_the_rest(registry):
    hero = ranger(registry, 5)
    hero.sheet.prepared_of()[:] = ["cure_wounds", "fog_cloud", "alarm"]
    swap_prepared(hero, registry, ["fog_cloud"], ["longstrider"])
    assert hero.sheet.prepared_of() == ["cure_wounds", "alarm", "longstrider"]


def test_swap_of_several_takes_in_order(registry):
    hero = cleric(registry)
    swap_prepared(hero, registry, [], ["bless", "cure_wounds"])
    assert hero.sheet.prepared_of() == ["bless", "cure_wounds"]


def test_pure_drop_leaves_the_rest(registry):
    hero = ranger(registry)
    swap_prepared(hero, registry, ["cure_wounds"], [])
    assert hero.sheet.prepared_of() == ["fog_cloud"]


def test_unknown_spell_hint_lists_the_class_spells_of_available_circles(registry):
    problem = swap_problem(ranger(registry), registry, [], ["no_such_spell"])
    hint = problem[1].split("допустимые id: ")[1].split(", ")
    assert "longstrider" in hint
    assert "hunters_mark" in hint
    assert "spike_growth" not in hint  # круг 2 на 2 ур. недоступен
    assert "burning_hands" not in hint
    assert hint == sorted(hint)


def test_unknown_spell_hint_for_the_wizard_excludes_cantrips(registry):
    hero = make_wizard(registry)
    problem = swap_problem(hero, registry, [], ["no_such_spell"])
    hint = problem[1].split("допустимые id: ")[1].split(", ")
    assert "fire_bolt" not in hint
    assert "magic_missile" in hint
