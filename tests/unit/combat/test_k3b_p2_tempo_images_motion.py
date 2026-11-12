# К3б П2 (docs/plan-k3b.md, «Тесты» П2, решения 11, 13, 15): темп, образы, движение в бою.
#   Ускорение (решения 4, 13): start_turn -- attacks_left 1 при action True, move 2; КД +2;
#     спасбросок Лов с преимуществом; две атаки оружием за ход; без вялости после конца.
#   Замедление (решение 5): Мдр провал -- без мультиатаки, без реакции, КД −2, Лов −2; раунд 2 --
#     move 0, раунд 3 -- move 1; конец хода: успех Мдр снимает все эффекты id == "slow".
#   Отражения (решение 11, SRD 5.2.1): 3 образа, 1 минута; попадание -- d6 на образ, любой 3+ --
#     образ разбит, промах; последний образ -- эффект снят.
#   Мерцание: конец хода героя d6 4-6 -- blinked; blinked не цель атак и заклинаний; начало хода
#     героя -- снято.
#   Падение пером (решение 15): герой с подготовленным заклинанием и ячейкой 1 круга при падении --
#     урон 0, ячейка и реакция потрачены; без ячейки -- обычное падение; падающий не герой -- нет.
#   Полёт: герой под Полётом парит (hovers), толчок вниз без урона.
#   Левитация: враг Тел провал -- нет движения, ближняя атака по нему невозможна, дальняя обычная.
#   Газообразная форма: нет атак и заклинаний, рубящий урон ×½, спасбросок Сил с преимуществом.
#   Увеличение/Уменьшение: размер ± шаг (target_size), урон оружием +1d4, враг -- Тел.
#   «Эффекты:» боя: game.sheet_text.combat_spell_lines -- по строке на заклинание.
#   Герой -- волшебник из test_cast_p3a.mage (ячейки 1-3 круга), в зале с гоблином.
from combat_kit import ScriptedRng, creature, hp, mon, option_ids, part
from test_cast_p3a import GOBLIN, cast_ids, conditions, effects, engine_of, idle, mage, slot
from test_falling import zones
from test_k3b_p1_zones_defense import SHOOT_WIZ, do_cast, log_has

from ai_dm.combat import falling
from ai_dm.combat.actions.attack import attack_targets, target_size
from ai_dm.combat.actions.cast_conditions import condition_targets
from ai_dm.combat.available import (
    attack_options,
    cast_options,
    move_options,
    multiattack_options,
)
from ai_dm.rules.results import Rejected
from ai_dm.state.combat import Zone
from ai_dm.state.creature import ActiveEffect, AppliedCondition, Expiry

STAFF = "attack:quarterstaff:goblin_1"
BOSS = [mon("boss_1", "goblin_boss", "hall")]


def hall_engine(registry, cfg, rng, *spells, monsters=GOBLIN, cantrips=(), zone="hall", **kwargs):
    # герой с гоблином в одном зале (ближний бой); zone="door" -- гоблин стреляет без помехи
    return idle(
        registry, cfg, mage(registry, *spells, cantrips=cantrips), rng or ScriptedRng(),
        monsters=monsters, hero_zone=zone, **kwargs,
    )


def far_zones():
    # door смежна с hall; far -- через door, не смежна с hall (куб 40 фт не достаёт)
    base = zones()
    base[0] = Zone(id="door", name="У двери", adjacent=["hall", "far"])
    return [*base, Zone(id="far", name="Дальний угол", adjacent=["door"])]


def cast_variant(engine, ref, spell_id, target, variant):
    ids = [i for i in cast_ids(engine, spell_id, ref) if i.endswith(f":{target}:v:{variant}")]
    assert ids, f"нет пункта {spell_id} → {target} ({variant}): {cast_ids(engine, spell_id, ref)}"
    assert not isinstance(engine.perform(ref, ids[0]), Rejected)


def turn(engine, ref):
    return part(engine, ref).turn


# Ускорение

def haste_engine(registry, cfg, rng=None):
    engine = hall_engine(registry, cfg, rng, "haste")
    do_cast(engine, "wiz", "haste", "wiz")
    return engine


def test_haste_gives_one_extra_attack_at_the_start_of_the_turn(registry, cfg):
    engine = haste_engine(registry, cfg)
    engine.start_turn("wiz")
    assert turn(engine, "wiz").attacks_left == 1


def test_haste_keeps_the_action_at_the_start_of_the_turn(registry, cfg):
    engine = haste_engine(registry, cfg)
    engine.start_turn("wiz")
    assert turn(engine, "wiz").action is True


def test_haste_gives_one_extra_step_at_the_start_of_the_turn(registry, cfg):
    engine = haste_engine(registry, cfg)
    engine.start_turn("wiz")
    assert turn(engine, "wiz").move == 2


def test_haste_adds_two_to_the_armor_class(registry, cfg):
    engine = hall_engine(registry, cfg, None, "haste")
    before = engine.armor_class("wiz")
    do_cast(engine, "wiz", "haste", "wiz")
    assert engine.armor_class("wiz") == before + 2


def test_haste_gives_advantage_on_dexterity_saves(registry, cfg):
    # d20 2 и 18: лучший 18 + Лов против СЛ 10 -- успех; одна кость (2) провалила бы
    rng = ScriptedRng(d20=[2, 18])
    engine = haste_engine(registry, cfg, rng)
    assert engine.save("wiz", "dex", 10).outcome == "success"
    assert rng.left("d20") == 0


def test_hasted_hero_keeps_the_attack_option_after_the_first_attack(registry, cfg):
    rng = ScriptedRng(d20=[19, 19], d8=[3, 3])
    engine = haste_engine(registry, cfg, rng)
    engine.start_turn("wiz")
    engine.perform("wiz", STAFF)
    assert STAFF in option_ids(engine, "wiz")


def test_hasted_hero_attacks_twice_with_a_weapon(registry, cfg):
    # посох 1d8 − 1: один удар с d8 = 3 снимает 2 HP, два -- 4
    rng = ScriptedRng(d20=[19, 19], d8=[3, 3])
    engine = haste_engine(registry, cfg, rng)
    engine.start_turn("wiz")
    engine.perform("wiz", STAFF)
    engine.perform("wiz", STAFF)
    assert hp(engine, "goblin_1") == 26


def test_hasted_hero_has_no_third_attack(registry, cfg):
    rng = ScriptedRng(d20=[19, 19], d8=[3, 3])
    engine = haste_engine(registry, cfg, rng)
    engine.start_turn("wiz")
    engine.perform("wiz", STAFF)
    engine.perform("wiz", STAFF)
    assert STAFF not in option_ids(engine, "wiz")


def test_unhasted_hero_has_the_usual_turn(registry, cfg):
    engine = hall_engine(registry, cfg, None, "haste")
    engine.start_turn("wiz")
    assert (turn(engine, "wiz").attacks_left, turn(engine, "wiz").move) == (0, 1)


def test_haste_ends_with_the_concentration_without_lethargy(registry, cfg):
    # Р-К3б-4 (а): после конца заклинания героя не парализует и ход не отнимается
    engine = haste_engine(registry, cfg)
    engine.drop_concentration_effects("wiz")
    engine.start_turn("wiz")
    assert (turn(engine, "wiz").move, "incapacitated" in conditions(engine, "wiz")) == (1, False)


def test_haste_extra_attack_goes_away_with_the_effect(registry, cfg):
    engine = haste_engine(registry, cfg)
    engine.drop_concentration_effects("wiz")
    engine.start_turn("wiz")
    assert turn(engine, "wiz").attacks_left == 0


# Замедление

def slow_engine(registry, cfg, rng, monsters=GOBLIN):
    # решения 20, 23: цель Замедления -- зона, куб 40 фт -- она и соседние, кроме заклинателя
    engine = hall_engine(registry, cfg, rng, "slow", monsters=monsters, zones=far_zones())
    do_cast(engine, "wiz", "slow", "hall")
    return engine


def test_slow_failed_save_takes_the_reaction(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").reaction is False


def test_slow_passed_save_leaves_the_reaction(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[18]))
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").reaction is True


def test_slowed_boss_has_no_multiattack(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]), BOSS)
    assert multiattack_options(engine, "boss_1") == []


def test_boss_with_a_passed_slow_save_keeps_the_multiattack(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[18]), BOSS)
    assert [o.id for o in multiattack_options(engine, "boss_1")] == ["multiattack"]


def test_slow_lowers_the_armor_class_by_two(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[3]), "slow")
    before = engine.armor_class("goblin_1")
    do_cast(engine, "wiz", "slow", "hall")
    assert engine.armor_class("goblin_1") == before - 2


def test_slow_passed_save_leaves_the_armor_class(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[18]), "slow")
    before = engine.armor_class("goblin_1")
    do_cast(engine, "wiz", "slow", "hall")
    assert engine.armor_class("goblin_1") == before


def test_slow_takes_two_from_dexterity_saves(registry, cfg):
    # Лов гоблина +2: 11 + 2 = 13 прошло бы СЛ 13, с −2 -- провал
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3, 11]))
    assert engine.save("goblin_1", "dex", 13).outcome == "fail"


def test_slowed_creature_has_no_movement_in_an_even_round(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.state.round = 2
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").move == 0


def test_slowed_creature_moves_in_an_odd_round(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.state.round = 3
    engine.start_turn("goblin_1")
    assert turn(engine, "goblin_1").move == 1


def end_goblin_turn(engine):
    engine.state.turn_index = engine.state.initiative_order.index("goblin_1")
    engine.next_turn()


def test_slow_repeat_save_success_removes_every_slow_effect(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3, 18]))
    end_goblin_turn(engine)
    assert effects(engine, "goblin_1", "slow") == []


def test_slow_repeat_save_success_restores_the_armor_class(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[3, 18]), "slow")
    before = engine.armor_class("goblin_1")
    do_cast(engine, "wiz", "slow", "hall")
    end_goblin_turn(engine)
    assert engine.armor_class("goblin_1") == before


def test_slow_failed_repeat_save_keeps_the_spell(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3, 4]))
    end_goblin_turn(engine)
    assert effects(engine, "goblin_1", "slow") != []


def test_slow_zone_does_not_slow_the_caster(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    assert effects(engine, "wiz", "slow") == []


def test_slow_zone_takes_every_creature_in_it(registry, cfg):
    # два гоблина в зале, оба проваливают Мдр
    two = [*GOBLIN, mon("goblin_2", "goblin_warrior", "hall")]
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3, 3]), two)
    assert [effects(engine, ref, "slow") != [] for ref in ("goblin_1", "goblin_2")] == [True, True]


def test_slow_cube_leaves_a_creature_in_a_non_adjacent_zone(registry, cfg):
    outside = [*GOBLIN, mon("goblin_2", "goblin_warrior", "far")]
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]), outside)
    assert effects(engine, "goblin_2", "slow") == []


def test_slow_cube_takes_a_creature_in_an_adjacent_zone(registry, cfg):
    # решение 23: куб 40 фт -- зона и соседние (door смежна с hall)
    near = [*GOBLIN, mon("goblin_2", "goblin_warrior", "door")]
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3, 3]), near)
    assert effects(engine, "goblin_2", "slow") != []


# Отражения

def mirror_engine(registry, cfg, rng):
    engine = hall_engine(registry, cfg, rng, "mirror_image", zone="door")
    do_cast(engine, "wiz", "mirror_image", "wiz")
    return engine


def images(engine):
    return effects(engine, "wiz", "mirror_image")[0].params["images"]


def test_mirror_image_makes_three_images(registry, cfg):
    assert images(mirror_engine(registry, cfg, ScriptedRng())) == 3


def test_mirror_image_lasts_by_the_clock_not_the_concentration(registry, cfg):
    engine = mirror_engine(registry, cfg, ScriptedRng())
    assert effects(engine, "wiz", "mirror_image")[0].expires.kind == "seconds"


def test_hit_on_a_hero_with_images_is_caught_by_an_image(registry, cfg):
    # d20 19 попадает, d6 3 -- образ разбит: герой цел
    rng = ScriptedRng(d20=[19], d6=[3, 1, 1])
    engine = mirror_engine(registry, cfg, rng)
    engine.perform("goblin_1", SHOOT_WIZ)
    assert hp(engine, "wiz") == 8


def test_broken_image_is_gone(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[3, 1, 1])
    engine = mirror_engine(registry, cfg, rng)
    engine.perform("goblin_1", SHOOT_WIZ)
    assert images(engine) == 2


def test_broken_image_is_logged_with_the_rest(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[3, 1, 1])
    engine = mirror_engine(registry, cfg, rng)
    engine.perform("goblin_1", SHOOT_WIZ)
    assert log_has(engine, "образ разбит", "осталось 2")


def test_hit_goes_through_when_every_image_die_is_below_three(registry, cfg):
    # три d6 по 1-2, затем d6 урона 4
    rng = ScriptedRng(d20=[19], d6=[1, 2, 2, 4])
    engine = mirror_engine(registry, cfg, rng)
    engine.perform("goblin_1", SHOOT_WIZ)
    assert hp(engine, "wiz") < 8


def test_missed_attack_does_not_touch_the_images(registry, cfg):
    # d20 2 -- промах, кости образов не бросаются (ScriptedRng упал бы на d6)
    engine = mirror_engine(registry, cfg, ScriptedRng(d20=[2]))
    engine.perform("goblin_1", SHOOT_WIZ)
    assert images(engine) == 3


def test_last_image_broken_removes_the_effect(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[4])
    engine = mirror_engine(registry, cfg, rng)
    effects(engine, "wiz", "mirror_image")[0].params["images"] = 1
    engine.perform("goblin_1", SHOOT_WIZ)
    assert effects(engine, "wiz", "mirror_image") == []


def test_last_image_broken_is_logged(registry, cfg):
    rng = ScriptedRng(d20=[19], d6=[4])
    engine = mirror_engine(registry, cfg, rng)
    effects(engine, "wiz", "mirror_image")[0].params["images"] = 1
    engine.perform("goblin_1", SHOOT_WIZ)
    assert log_has(engine, "образов не осталось")


# Мерцание

def blink_engine(registry, cfg, rng):
    engine = hall_engine(registry, cfg, rng, "blink")
    do_cast(engine, "wiz", "blink", "wiz")
    return engine


def test_blink_roll_of_four_sends_the_hero_to_the_ether_at_the_end_of_the_turn(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    assert "blinked" in conditions(engine, "wiz")


def test_blink_roll_of_three_keeps_the_hero_on_the_plane(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[3]))
    engine.next_turn()
    assert "blinked" not in conditions(engine, "wiz")


def test_blinked_hero_is_not_in_the_enemys_attack_options(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[6]))
    engine.next_turn()
    assert [i for i in option_ids(engine, "goblin_1") if i.endswith(":wiz")] == []


def test_hero_on_the_plane_stays_in_the_enemys_attack_options(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[3]))
    engine.next_turn()
    assert SHOOT_WIZ in option_ids(engine, "goblin_1")


def test_blinked_hero_is_not_an_attack_target(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    creature(engine, "wiz").conditions.append(AppliedCondition(id="blinked", source="blink"))
    assert "wiz" not in attack_targets(engine, "goblin_1")


def test_hero_on_the_plane_is_an_attack_target(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    assert "wiz" in attack_targets(engine, "goblin_1")


def test_blinked_creature_is_not_caught_by_an_area_condition_spell(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    creature(engine, "goblin_1").conditions.append(AppliedCondition(id="blinked", source="blink"))
    spell = registry.get("spell", "hypnotic_pattern")
    assert "goblin_1" not in condition_targets(engine, "wiz", spell, "hall")


def test_creature_on_the_plane_is_caught_by_an_area_condition_spell(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    spell = registry.get("spell", "hypnotic_pattern")
    assert "goblin_1" in condition_targets(engine, "wiz", spell, "hall")


def test_blink_ends_at_the_start_of_the_heros_next_turn(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    engine.start_turn("wiz")
    assert "blinked" not in conditions(engine, "wiz")


# Падение пером

def fall_engine(registry, cfg, rng, *spells, goblin_zone="hall", hero_zone="balcony"):
    return engine_of(
        registry, cfg, mage(registry, *spells), rng,
        monsters=[mon("goblin_1", "goblin_warrior", goblin_zone)], zones=zones(),
        hero_zone=hero_zone,
    )


def push_hero_to_the_pit(engine):
    # балкон (1) → яма (−1): два шага, 2d6
    return falling.push(engine, "goblin_1", "wiz", "pit")


def test_feather_fall_cancels_the_damage(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    push_hero_to_the_pit(engine)
    assert hp(engine, "wiz") == 8


def test_feather_fall_spends_a_first_circle_slot(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    push_hero_to_the_pit(engine)
    assert slot(engine, 1) == 3


def test_feather_fall_spends_the_reaction(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    push_hero_to_the_pit(engine)
    assert turn(engine, "wiz").reaction is False


def test_feather_fall_is_logged(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    push_hero_to_the_pit(engine)
    assert log_has(engine, "Падение пером", "мягко")


def test_feather_fall_is_not_read_in_the_silenced_zone(registry, cfg):
    # как обычный каст (cast.py:96, available.py:151): под Тишиной реакцию читать нельзя -- 2d6
    # герой держит концентрацию Тишины: после урона ещё d20 на Тел (18)
    rng = ScriptedRng(d20=[18], d6=[3, 3])
    engine = fall_engine(registry, cfg, rng, "feather_fall", "silence")
    do_cast(engine, "wiz", "silence", "balcony")
    push_hero_to_the_pit(engine)
    assert (hp(engine, "wiz"), slot(engine, 1)) == (2, 4)


def test_fall_without_a_slot_is_the_usual_one(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(d6=[3, 3]), "feather_fall")
    for circle in (1, 2, 3):
        engine.heroes["wiz"].creature.resources[f"spell_slot:{circle}"].current = 0
    push_hero_to_the_pit(engine)
    assert hp(engine, "wiz") == 2


def test_fall_without_the_prepared_spell_is_the_usual_one(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(d6=[3, 3]))
    push_hero_to_the_pit(engine)
    assert hp(engine, "wiz") == 2


def test_feather_fall_does_not_save_a_falling_enemy(registry, cfg):
    # решение 15: только сам герой; гоблин падает с балкона в зал на 1 шаг (1d6)
    engine = fall_engine(
        registry, cfg, ScriptedRng(d6=[4]), "feather_fall", goblin_zone="balcony",
        hero_zone="hall",
    )
    falling.push(engine, "wiz", "goblin_1", "hall")
    assert (hp(engine, "goblin_1"), slot(engine, 1)) == (26, 4)


# Полёт

def test_flying_hero_hovers(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "fly")
    do_cast(engine, "wiz", "fly", "wiz")
    assert falling.hovers(engine, "wiz") is True


def test_hero_without_flight_does_not_hover(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(d6=[3, 3]), "fly")
    assert falling.hovers(engine, "wiz") is False


def test_flying_hero_pushed_down_takes_no_damage(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "fly")
    do_cast(engine, "wiz", "fly", "wiz")
    push_hero_to_the_pit(engine)
    assert hp(engine, "wiz") == 8


def test_flying_hero_pushed_down_hovers_in_the_log(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "fly")
    do_cast(engine, "wiz", "fly", "wiz")
    push_hero_to_the_pit(engine)
    assert log_has(engine, "парит")


def test_gaseous_hero_pushed_down_takes_no_damage(registry, cfg):
    # решение 28: облако парит; при падении нужны были бы 2d6 (3, 3) и d20 на концентрацию
    # d20 18, 18: проверка Тел под Газообразной формой идёт с преимуществом (две кости)
    engine = fall_engine(registry, cfg, ScriptedRng(d6=[3, 3], d20=[18, 18]), "gaseous_form")
    do_cast(engine, "wiz", "gaseous_form", "wiz")
    push_hero_to_the_pit(engine)
    assert hp(engine, "wiz") == 8


def test_gaseous_hero_pushed_down_hovers_in_the_log(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(d6=[3, 3], d20=[18, 18]), "gaseous_form")
    do_cast(engine, "wiz", "gaseous_form", "wiz")
    push_hero_to_the_pit(engine)
    assert log_has(engine, "парит")


def test_levitated_enemy_pushed_down_takes_no_damage(registry, cfg):
    # решение 28: левитирующий гоблин (Тел провал d20 3) парит; при падении был бы 1d6 (4)
    engine = fall_engine(
        registry, cfg, ScriptedRng(d20=[3], d6=[4]), "levitate", hero_zone="hall",
        goblin_zone="hall",
    )
    do_cast(engine, "wiz", "levitate", "goblin_1")
    falling.push(engine, "wiz", "goblin_1", "pit")
    assert hp(engine, "goblin_1") == 30


def test_flight_ends_with_the_concentration(registry, cfg):
    engine = fall_engine(registry, cfg, ScriptedRng(), "fly")
    do_cast(engine, "wiz", "fly", "wiz")
    engine.drop_concentration_effects("wiz")
    assert falling.hovers(engine, "wiz") is False


# Левитация

def levitate_engine(registry, cfg, rng):
    engine = hall_engine(
        registry, cfg, rng, "levitate", cantrips=["fire_bolt"],
    )
    do_cast(engine, "wiz", "levitate", "goblin_1")
    return engine


def test_levitated_enemy_cannot_move(registry, cfg):
    engine = levitate_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.start_turn("goblin_1")
    assert move_options(engine, "goblin_1") == []


def test_enemy_with_a_passed_levitation_save_still_moves(registry, cfg):
    engine = levitate_engine(registry, cfg, ScriptedRng(d20=[18]))
    engine.start_turn("goblin_1")
    assert move_options(engine, "goblin_1") != []


def test_levitated_enemy_cannot_be_attacked_in_melee(registry, cfg):
    engine = levitate_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.start_turn("wiz")
    assert STAFF not in option_ids(engine, "wiz")


def test_levitated_enemy_can_be_attacked_at_range(registry, cfg):
    engine = levitate_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.start_turn("wiz")
    assert "attack:improvised_thrown:goblin_1" in option_ids(engine, "wiz")


def test_enemy_with_a_passed_levitation_save_is_attacked_in_melee(registry, cfg):
    engine = levitate_engine(registry, cfg, ScriptedRng(d20=[18]))
    engine.start_turn("wiz")
    assert STAFF in option_ids(engine, "wiz")


# Газообразная форма

def gas_engine(registry, cfg, rng=None):
    engine = hall_engine(registry, cfg, rng, "gaseous_form", cantrips=["fire_bolt"])
    do_cast(engine, "wiz", "gaseous_form", "wiz")
    engine.start_turn("wiz")
    return engine


def test_gaseous_hero_has_no_attack_options(registry, cfg):
    assert attack_options(gas_engine(registry, cfg), "wiz") == []


def test_gaseous_hero_has_no_cast_options(registry, cfg):
    assert cast_options(gas_engine(registry, cfg), "wiz") == []


def test_gaseous_hero_halves_slashing_damage(registry, cfg):
    assert gas_engine(registry, cfg).damage("wiz", 8, "slashing").final == 4


def test_gaseous_hero_has_advantage_on_strength_saves(registry, cfg):
    # d20 2 и 18: лучший 18 + Сил против СЛ 12 -- успех
    rng = ScriptedRng(d20=[2, 18])
    engine = gas_engine(registry, cfg, rng)
    assert engine.save("wiz", "str", 12).outcome == "success"
    assert rng.left("d20") == 0


# Увеличение и уменьшение

def staff_damage(registry, cfg, enlarged):
    # герой бьёт посохом: d20 19, d8 3 (+ d4 2 от Увеличения); потеря HP гоблина
    rng = ScriptedRng(d20=[19], d8=[3], d4=[2])
    engine = hall_engine(registry, cfg, rng, "enlarge_reduce")
    if enlarged:
        cast_variant(engine, "wiz", "enlarge_reduce", "wiz", "enlarge")
    engine.start_turn("wiz")
    engine.perform("wiz", STAFF)
    return 30 - hp(engine, "goblin_1")


def test_enlarge_makes_the_hero_one_size_larger(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(), "enlarge_reduce")
    before = target_size(engine, "wiz")
    cast_variant(engine, "wiz", "enlarge_reduce", "wiz", "enlarge")
    assert (before, target_size(engine, "wiz")) == ("medium", "large")


def test_enlarge_adds_a_d4_to_weapon_damage(registry, cfg):
    assert staff_damage(registry, cfg, True) == staff_damage(registry, cfg, False) + 2


def test_reduce_on_an_enemy_with_a_failed_save_shrinks_it(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[3]), "enlarge_reduce")
    before = target_size(engine, "goblin_1")
    cast_variant(engine, "wiz", "enlarge_reduce", "goblin_1", "reduce")
    assert (before, target_size(engine, "goblin_1")) == ("small", "tiny")


def test_reduce_on_an_enemy_with_a_passed_save_changes_nothing(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[18]), "enlarge_reduce")
    cast_variant(engine, "wiz", "enlarge_reduce", "goblin_1", "reduce")
    assert target_size(engine, "goblin_1") == "small"


def shrunk_goblin_hit_hp(registry, cfg, shrunk):
    # гоблин с двери стреляет в героя: d20 19, d6 4, d4 2 (штраф Уменьшения); HP героя 8;
    # герой держит концентрацию Уменьшения -- после попадания ещё d20 на Тел (18)
    rng = ScriptedRng(d20=[3, 19, 18] if shrunk else [19], d6=[4], d4=[2] if shrunk else [])
    engine = hall_engine(registry, cfg, rng, "enlarge_reduce", zone="door")
    if shrunk:
        cast_variant(engine, "wiz", "enlarge_reduce", "goblin_1", "reduce")
    engine.perform("goblin_1", SHOOT_WIZ)
    return hp(engine, "wiz")


def test_shrunk_enemy_deals_a_d4_less_weapon_damage(registry, cfg):
    assert shrunk_goblin_hit_hp(registry, cfg, True) == 4


def test_unshrunk_enemy_deals_full_weapon_damage(registry, cfg):
    assert shrunk_goblin_hit_hp(registry, cfg, False) == 2


def test_enlarge_ends_with_the_concentration(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(), "enlarge_reduce")
    cast_variant(engine, "wiz", "enlarge_reduce", "wiz", "enlarge")
    engine.drop_concentration_effects("wiz")
    assert target_size(engine, "wiz") == "medium"


# «Эффекты:» заклинаний боя

def spell_lines_of(engine):
    from ai_dm.game.sheet_text import combat_spell_lines

    return combat_spell_lines(
        engine.heroes["wiz"].creature, engine.registry, engine.world.clock.now_s
    )


def test_haste_is_one_line_with_its_armor_bonus_and_concentration(registry, cfg):
    lines = spell_lines_of(haste_engine(registry, cfg))
    assert len(lines) == 1
    assert all(word in lines[0] for word in ("Ускорение", "+2 КД", "концентрация"))


def test_mirror_image_line_names_the_images_and_the_end_time(registry, cfg):
    lines = spell_lines_of(mirror_engine(registry, cfg, ScriptedRng()))
    assert len(lines) == 1
    assert all(word in lines[0] for word in ("Отражения", "образов 3", "до "))


def test_no_spell_effects_no_lines(registry, cfg):
    assert spell_lines_of(hall_engine(registry, cfg, ScriptedRng(), "haste")) == []


# Разбор выживших мутантов П2

def expire_by_clock(engine, ref, kind, params=None):
    # эффект kind на ref, срок которого по часам мира уже вышел (value 10 < now_s 100)
    engine.world.clock.now_s = 100
    engine.creature(ref).active_effects.append(
        ActiveEffect(
            id=kind, source=ref, kind=kind, params=params or {},
            expires=Expiry(kind="seconds", value=10),
        )
    )


def test_flying_effect_past_its_clock_is_not_flying(registry, cfg):
    from ai_dm.combat import flight

    engine = hall_engine(registry, cfg, ScriptedRng())
    expire_by_clock(engine, "wiz", "flying")
    assert flight.has(engine, "wiz", "flying") is False


def test_tempo_effect_past_its_clock_is_not_active(registry, cfg):
    from ai_dm.combat import tempo

    engine = hall_engine(registry, cfg, ScriptedRng())
    expire_by_clock(engine, "wiz", "tempo", {"mode": "haste"})
    assert tempo.active(engine, "wiz", "haste") is False


def test_blink_past_its_clock_does_not_send_the_hero_to_the_ether(registry, cfg):
    from ai_dm.combat import blink

    engine = hall_engine(registry, cfg, ScriptedRng(d6=[6]))
    expire_by_clock(engine, "wiz", "blink")
    blink.end_turn(engine, "wiz")
    assert "blinked" not in conditions(engine, "wiz")


def test_blinked_state_is_marked_by_the_blink_source(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    state = [c for c in creature(engine, "wiz").conditions if c.id == "blinked"][0]
    assert state.source == "blink"


def test_blinked_state_ends_at_the_start_of_the_owners_turn(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    state = [c for c in creature(engine, "wiz").conditions if c.id == "blinked"][0]
    assert state.expires == Expiry(kind="start_of_turn", owner="wiz")


def test_blink_to_the_ether_is_logged_with_the_name(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    assert log_has(engine, f"Мерцание: {engine.name('wiz')} в Эфире")


def test_return_from_the_ether_is_logged_with_the_name(registry, cfg):
    engine = blink_engine(registry, cfg, ScriptedRng(d6=[4]))
    engine.next_turn()
    engine.start_turn("wiz")
    assert log_has(engine, f"{engine.name('wiz')} возвращается")


def test_haste_start_of_turn_is_logged_with_the_name(registry, cfg):
    engine = haste_engine(registry, cfg)
    engine.start_turn("wiz")
    assert log_has(engine, f"Ускорение: {engine.name('wiz')} — лишняя атака и шаг")


def test_haste_extra_attack_adds_to_the_attacks_left(registry, cfg):
    from ai_dm.combat import tempo

    engine = haste_engine(registry, cfg)
    turn(engine, "wiz").attacks_left = 1
    tempo.start_turn(engine, "wiz")
    assert turn(engine, "wiz").attacks_left == 2


def test_slow_in_an_even_round_is_logged_with_the_name(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    engine.state.round = 2
    engine.start_turn("goblin_1")
    assert log_has(engine, f"Замедление: {engine.name('goblin_1')} медлит")


def test_slow_armor_class_effect_is_a_labeled_magic_penalty(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    armor = [e for e in effects(engine, "goblin_1", "slow") if e.kind == "ac"][0]
    assert armor.params == {
        "label": registry.get("spell", "slow").name, "amount": -2, "magic": True,
    }


def test_slow_effects_hold_for_the_concentration_of_the_caster(registry, cfg):
    engine = slow_engine(registry, cfg, ScriptedRng(d20=[3]))
    marks = [e.expires for e in effects(engine, "goblin_1", "slow") if e.kind in ("ac", "tempo")]
    assert marks == [Expiry(kind="concentration", owner="wiz")] * 2


def test_haste_armor_class_effect_is_a_labeled_magic_bonus(registry, cfg):
    engine = haste_engine(registry, cfg)
    armor = [e for e in effects(engine, "wiz", "haste") if e.kind == "ac"][0]
    assert armor.params == {
        "label": registry.get("spell", "haste").name, "amount": 2, "magic": True,
    }


def test_haste_gives_no_advantage_on_strength_saves(registry, cfg):
    # одна кость: Сил не из спасбросков Лов, d20 18 остаётся в очереди
    rng = ScriptedRng(d20=[2, 18])
    engine = haste_engine(registry, cfg, rng)
    engine.save("wiz", "str", 10)
    assert rng.left("d20") == 1


def test_gaseous_form_gives_advantage_on_dexterity_saves(registry, cfg):
    rng = ScriptedRng(d20=[2, 18])
    engine = gas_engine(registry, cfg, rng)
    assert engine.save("wiz", "dex", 12).outcome == "success"
    assert rng.left("d20") == 0


def test_gaseous_form_gives_advantage_on_constitution_saves(registry, cfg):
    rng = ScriptedRng(d20=[2, 18])
    engine = gas_engine(registry, cfg, rng)
    assert engine.save("wiz", "con", 12).outcome == "success"
    assert rng.left("d20") == 0


def test_gaseous_form_gives_no_advantage_on_wisdom_saves(registry, cfg):
    rng = ScriptedRng(d20=[2, 18])
    engine = gas_engine(registry, cfg, rng)
    engine.save("wiz", "wis", 12)
    assert rng.left("d20") == 1


def test_reduce_places_a_size_step_of_minus_one(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng(d20=[3]), "enlarge_reduce")
    cast_variant(engine, "wiz", "enlarge_reduce", "goblin_1", "reduce")
    sizes = [e for e in creature(engine, "goblin_1").active_effects if e.kind == "size"]
    assert [e.params["step"] for e in sizes] == [-1]


def test_size_cannot_grow_above_the_largest(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    engine.creature("goblin_1").active_effects.append(
        ActiveEffect(id="enlarge_reduce", source="wiz", kind="size", params={"step": 5})
    )
    assert target_size(engine, "goblin_1") == "gargantuan"


def test_release_held_keeps_another_spell_of_the_same_caster(registry, cfg):
    from ai_dm.combat.actions.cast_conditions import release_held

    engine = hall_engine(registry, cfg, ScriptedRng())
    slow = ActiveEffect(id="slow", source="wiz", kind="tempo", params={"mode": "slow"})
    other = ActiveEffect(id="haste", source="wiz", kind="tempo", params={"mode": "haste"})
    engine.creature("goblin_1").active_effects += [slow, other]
    release_held(engine, "goblin_1", slow)
    assert [e.id for e in engine.creature("goblin_1").active_effects] == ["haste"]


def test_feather_fall_is_not_read_by_a_downed_hero(registry, cfg):
    from ai_dm.combat.actions import feather_fall

    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    engine.creature("wiz").hp_current = 0
    assert feather_fall.react(engine, "wiz", "balcony") is False


def test_feather_fall_is_not_read_by_an_incapacitated_hero(registry, cfg):
    from ai_dm.combat.actions import feather_fall

    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    engine.creature("wiz").conditions.append(AppliedCondition(id="incapacitated"))
    assert feather_fall.react(engine, "wiz", "balcony") is False


def test_feather_fall_is_read_by_a_capable_hero(registry, cfg):
    from ai_dm.combat.actions import feather_fall

    engine = fall_engine(registry, cfg, ScriptedRng(), "feather_fall")
    assert feather_fall.react(engine, "wiz", "balcony") is True


def test_spell_line_with_a_concentration_is_exact(registry, cfg):
    name = registry.get("spell", "haste").name
    assert spell_lines_of(haste_engine(registry, cfg)) == [f"{name} (+2 КД, концентрация)"]


def test_spell_line_without_details_is_the_bare_name(registry, cfg):
    engine = hall_engine(registry, cfg, ScriptedRng())
    engine.creature("wiz").active_effects.append(
        ActiveEffect(id="blink", source="wiz", kind="blink")
    )
    assert spell_lines_of(engine) == [registry.get("spell", "blink").name]


def test_spell_line_past_its_clock_is_gone(registry, cfg):
    engine = mirror_engine(registry, cfg, ScriptedRng())
    engine.world.clock.now_s += 10 * 3600
    assert spell_lines_of(engine) == []


def test_effects_line_includes_the_combat_spells(registry, cfg):
    from ai_dm.rules.inventory import effects_line

    engine = mirror_engine(registry, cfg, ScriptedRng())
    line = effects_line(engine.heroes["wiz"], registry, engine.world.clock.now_s)
    assert line.startswith("Действует: ") and "Отражения" in line
