# Бой следопыта 2-5 ур. (docs/decisions/ranger-2-5-plan.md, разд. 5 п. 10, разд. 6, решения 1-7).
# Герой -- Грей из пака Вейл (ЛОВ 17, длинный лук +5 / 1d8+3 при мастерстве +2, +6 при +3;
# скимитар в рюкзаке), Savage Attacker снят (как у make_fighter); уровень, подкласс и черты
# выставляются прямо в листе героя + sync_resources. Цель -- воин-гоблин, КД 15, 10 HP.
# Ожидаемый API:
#   cast:hunters_mark:1:<цель> -- бонусное действие (turn.bonus), действие остаётся; пока
#       resources["favored_enemy"].current > 0 -- тратится оно, ячейка нет; иначе ячейка 1 круга;
# caster.concentration.spell_id == "hunters_mark"; на цели ActiveEffect(kind="mark",
# source=<герой>)
#   попадание героя по цели с Меткой: +1d6 (крит 2d6); потеря концентрации снимает метку
#   Colossus Slayer (feature_options {"hunters_prey": "colossus_slayer"}, подкласс hunter):
#       +1d8 раз за ход по цели с HP < max; Hunter's Lore (hunter, 3 ур.): при наложении Метки
#       в лог идёт лишняя строка о свойствах цели
#   Extra Attack (5 ур.): после первой атаки действие потрачено, но атаки героя (attack:...)
#       остаются доступны для второй; после второй -- нет; на 1-4 ур. вторая атака -> Rejected
#   Archery (feat archery): +2 к броску атаки дальним оружием, к ближнему -- 0
from combat_kit import (
    ScriptedRng,
    creature,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    option_ids,
    part,
    set_hp,
)

from ai_dm.game.starter import ranger_choices
from ai_dm.rules.builder import build_character
from ai_dm.rules.progression import sync_resources
from ai_dm.rules.results import Rejected

SHOOT = "attack:longbow:goblin_1"


def make_ranger(registry, level=2, subclass=None, options=None, feats=()):
    hero = build_character(ranger_choices("hero"), registry)
    hero.sheet.feats = [f for f in hero.sheet.feats if f != "savage_attacker"] + list(feats)
    hero.sheet.primary.level = level
    hero.sheet.primary.subclass_id = subclass
    hero.sheet.feature_choices = {k: [v] for k, v in (options or {}).items()}
    sync_resources(hero, registry)
    return hero


def ranger_engine(registry, cfg, rng, hero=None, monsters=None, **kwargs):
    if monsters is None:
        monsters = [mon("goblin_1", "goblin_warrior", "hall")]
    return make_engine(
        registry, cfg, heroes=[hero or make_ranger(registry)], rng=rng, monsters=monsters,
        hero_zone="door", **kwargs,
    )


def tough(engine, ref="goblin_1", current=30, maximum=40):
    creature(engine, ref).hp_max = maximum
    set_hp(engine, ref, current)


def marks(engine, ref):
    return [e for e in creature(engine, ref).active_effects if e.kind == "mark"]


def pool(engine, name):
    return engine.heroes["hero"].creature.resources[name]


# Метка охотника: выбор и экономика действий

def test_hunters_mark_is_offered_without_being_in_prepared_list(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    assert "hunters_mark" not in engine.heroes["hero"].sheet.prepared_of()
    assert "cast:hunters_mark:1:goblin_1" in option_ids(engine, "hero")


def test_hunters_mark_spends_the_bonus_action_and_keeps_the_action(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    assert part(engine, "hero").turn.bonus is False
    assert part(engine, "hero").turn.action is True


def test_hunters_mark_can_be_cast_after_the_action_is_spent(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    part(engine, "hero").turn.action = False
    assert "cast:hunters_mark:1:goblin_1" in option_ids(engine, "hero")


def test_hunters_mark_is_not_offered_when_bonus_action_is_spent(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    part(engine, "hero").turn.bonus = False
    assert "cast:hunters_mark:1:goblin_1" not in option_ids(engine, "hero")


def test_hunters_mark_spends_favored_enemy_and_not_a_slot(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    engine.perform("hero", "cast:hunters_mark:1:goblin_1:free")
    assert pool(engine, "favored_enemy").current == 1
    assert pool(engine, "spell_slot:1").current == 2


def test_hunters_mark_without_free_uses_spends_a_first_circle_slot(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    pool(engine, "favored_enemy").current = 0
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    assert pool(engine, "favored_enemy").current == 0
    assert pool(engine, "spell_slot:1").current == 1


def test_hunters_mark_is_not_offered_without_free_uses_and_slots(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng())
    pool(engine, "favored_enemy").current = 0
    pool(engine, "spell_slot:1").current = 0
    assert "cast:hunters_mark:1:goblin_1" not in option_ids(engine, "hero")


def test_hunters_mark_sets_concentration_and_mark_on_target_only(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    assert engine.heroes["hero"].creature.concentration.spell_id == "hunters_mark"
    assert [e.source for e in marks(engine, "goblin_1")] == ["hero"]
    assert marks(engine, "goblin_2") == []


# Метка: урон

def test_hit_on_marked_target_adds_1d6(registry, cfg):
    # 15 + 5 = 20 >= 15; 1d8 (5) + 3 + 1d6 (4)
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5], d6=[4]))
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 18


def test_miss_on_marked_target_does_not_roll_mark_dice(registry, cfg):
    rng = ScriptedRng(d20=[2], d6=[4])
    engine = ranger_engine(registry, cfg, rng)
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 30
    assert rng.left("d6") == 1


def test_hit_on_another_target_does_not_add_mark_damage(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[5], d6=[4])
    engine = ranger_engine(
        registry, cfg, rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )
    tough(engine, "goblin_2")
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", "attack:longbow:goblin_2")
    assert hp(engine, "goblin_2") == 22
    assert rng.left("d6") == 1


def test_critical_hit_on_marked_target_rolls_2d6(registry, cfg):
    # крит: 2d8 (5, 5) + 3 и 2d6 (4, 3) = 20
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[20], d8=[5, 5], d6=[4, 3]))
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 10


def test_mark_damage_line_is_in_the_log(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5], d6=[4]))
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    assert any("1d6" in line for line in engine.state.log)


def test_lost_concentration_removes_the_mark(registry, cfg):
    # гоблин в зоне героя попадает (19 + 4), урон 3 + 2 = 5, СЛ 10; ТЕЛ +1: 2 + 1 = 3 -- провал
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[19, 2], d6=[3]),
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("goblin_1", "attack:скимитар:hero")
    assert engine.heroes["hero"].creature.concentration is None
    assert marks(engine, "goblin_1") == []


# Hunter's Lore

def log_size_after_mark(registry, cfg, subclass):
    hero = make_ranger(registry, level=3, subclass=subclass)
    engine = ranger_engine(registry, cfg, ScriptedRng(), hero=hero)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    return len(engine.state.log)


def test_hunters_lore_adds_a_log_line_for_hunter(registry, cfg):
    assert log_size_after_mark(registry, cfg, "hunter") > log_size_after_mark(
        registry, cfg, "beast_master"
    )


# Colossus Slayer

def colossus_ranger(registry, level=3):
    return make_ranger(
        registry, level=level, subclass="hunter", options={"hunters_prey": "colossus_slayer"}
    )


def test_colossus_slayer_adds_1d8_to_wounded_target(registry, cfg):
    # 1d8 (5) + 3 + 1d8 (3)
    rng = ScriptedRng(d20=[15], d8=[5, 3])
    engine = ranger_engine(registry, cfg, rng, hero=colossus_ranger(registry))
    tough(engine)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 19


def test_colossus_slayer_does_not_work_on_full_hp_target(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[5, 3])
    engine = ranger_engine(registry, cfg, rng, hero=colossus_ranger(registry))
    tough(engine, current=40)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 32
    assert rng.left("d8") == 1


def test_colossus_slayer_works_once_per_turn(registry, cfg):
    # 5 ур., две атаки: первая 1d8 + 3 + 1d8, вторая только 1d8 + 3: 5 + 3 + 3 + 4 + 3 = 18
    rng = ScriptedRng(d20=[15, 15], d8=[5, 3, 4])
    engine = ranger_engine(registry, cfg, rng, hero=colossus_ranger(registry, level=5))
    tough(engine)
    engine.perform("hero", SHOOT)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 12


def test_colossus_slayer_is_renewed_next_turn(registry, cfg):
    rng = ScriptedRng(d20=[15, 15], d8=[5, 3, 4, 2])
    engine = ranger_engine(registry, cfg, rng, hero=colossus_ranger(registry))
    tough(engine)
    engine.perform("hero", SHOOT)
    engine.start_turn("hero")
    engine.perform("hero", SHOOT)
    # первый ход: 5 + 3 + 3 = 11, второй: 4 + 3 + 2 = 9
    assert hp(engine, "goblin_1") == 10


def test_beast_master_has_no_colossus_slayer(registry, cfg):
    rng = ScriptedRng(d20=[15], d8=[5, 3])
    hero = make_ranger(registry, level=3, subclass="beast_master")
    engine = ranger_engine(registry, cfg, rng, hero=hero)
    tough(engine)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 22
    assert rng.left("d8") == 1


# Extra Attack

def test_level_5_ranger_attacks_twice_with_one_action(registry, cfg):
    # мастерство +3: 15 + 6 >= 15; каждая 1d8 (5) + 3
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15, 15], d8=[5, 5]), hero=make_ranger(registry, level=5)
    )
    tough(engine)
    first = engine.perform("hero", SHOOT)
    assert not isinstance(first, Rejected)
    assert part(engine, "hero").turn.action is False
    assert SHOOT in option_ids(engine, "hero")
    second = engine.perform("hero", SHOOT)
    assert not isinstance(second, Rejected)
    assert hp(engine, "goblin_1") == 14


def test_level_5_ranger_has_no_third_attack(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15, 15], d8=[5, 5]), hero=make_ranger(registry, level=5)
    )
    tough(engine)
    engine.perform("hero", SHOOT)
    engine.perform("hero", SHOOT)
    assert SHOOT not in option_ids(engine, "hero")
    assert isinstance(engine.perform("hero", SHOOT), Rejected)


def test_level_5_second_attack_is_not_a_free_action_for_other_things(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15], d8=[5]), hero=make_ranger(registry, level=5)
    )
    engine.perform("hero", SHOOT)
    ids = option_ids(engine, "hero")
    assert "dash" not in ids
    assert "dodge" not in ids


def test_second_attack_is_renewed_next_turn(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15, 15], d8=[5, 5]), hero=make_ranger(registry, level=5)
    )
    tough(engine)
    engine.perform("hero", SHOOT)
    engine.perform("hero", SHOOT)
    engine.start_turn("hero")
    assert SHOOT in option_ids(engine, "hero")


def test_level_4_ranger_attacks_once(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15, 15], d8=[5, 5]), hero=make_ranger(registry, level=4)
    )
    engine.perform("hero", SHOOT)
    assert SHOOT not in option_ids(engine, "hero")
    assert isinstance(engine.perform("hero", SHOOT), Rejected)


def test_level_1_ranger_without_subclass_attacks_once_as_before(registry, cfg):
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[15, 15], d8=[5, 5]), hero=make_ranger(registry, level=1)
    )
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 2
    assert isinstance(engine.perform("hero", SHOOT), Rejected)


def test_fighter_attacks_once_as_before(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)], rng=ScriptedRng(d20=[15, 15], d8=[5, 5]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="hall",
    )
    engine.perform("hero", "attack:longsword:goblin_1")
    assert part(engine, "hero").turn.action is False
    assert not [i for i in option_ids(engine, "hero") if i.startswith("attack:")]
    assert isinstance(engine.perform("hero", "attack:longsword:goblin_1"), Rejected)


def test_wizard_cantrip_still_spends_the_action(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_wizard(registry)], rng=ScriptedRng(d20=[10], d10=[7]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="door",
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert part(engine, "wiz").turn.action is False
    assert not [i for i in option_ids(engine, "wiz") if i.startswith("cast:fire_bolt")]


# Archery

def test_archery_adds_2_to_ranged_attack(registry, cfg):
    # 8 + 3 + 2 + 2 = 15 >= 15: попадание; без стиля было бы 13
    hero = make_ranger(registry, feats=["archery"])
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[8], d8=[5]), hero=hero)
    tough(engine)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 22


def test_ranged_attack_without_archery_misses_on_the_same_roll(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[8], d8=[5]))
    tough(engine)
    engine.perform("hero", SHOOT)
    assert hp(engine, "goblin_1") == 30


def test_archery_does_not_help_melee_attack(registry, cfg):
    # скимитар: ЛОВ +3 и мастерство +2 = +5; 8 + 5 = 13 < 15 и со стилем
    hero = make_ranger(registry, feats=["archery"])
    engine = ranger_engine(
        registry, cfg, ScriptedRng(d20=[8], d6=[3]), hero=hero,
        monsters=[mon("goblin_1", "goblin_warrior", "door")],
    )
    tough(engine)
    engine.perform("hero", "attack:scimitar:goblin_1")
    assert hp(engine, "goblin_1") == 30


# заклинания без вида боя

def test_spells_without_combat_kind_are_not_offered(registry, cfg):
    hero = make_ranger(registry, level=5)
    hero.sheet.prepared_of()[:] = [
        "cure_wounds", "entangle", "fog_cloud", "goodberry",
        "speak_with_animals", "longstrider", "alarm", "pass_without_trace", "spike_growth",
        "lesser_restoration", "barkskin",
    ]
    engine = ranger_engine(registry, cfg, ScriptedRng(), hero=hero)
    spells = {i.split(":")[1] for i in option_ids(engine, "hero") if i.startswith("cast:")}
    assert spells <= {"hunters_mark", "cure_wounds"}
    assert "hunters_mark" in spells


# D2: Убийца колоссов -- раз в любой ход, в том числе в атаке по возможности

def test_colossus_slayer_works_in_opportunity_attack_on_enemy_turn(registry, cfg):
    # свой ход: скимитар 3 + 3 + 1d8 (4) = 10; ход гоблина: атака по возможности ещё 10
    hero = colossus_ranger(registry)
    give_weapon(hero, registry, "scimitar")
    rng = ScriptedRng(d20=[15, 15], d6=[3, 3], d8=[4, 4])
    engine = make_engine(
        registry, cfg, heroes=[hero], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")], hero_zone="hall",
    )
    tough(engine)
    engine.perform("hero", "attack:scimitar:goblin_1")
    assert hp(engine, "goblin_1") == 20
    engine.start_turn("goblin_1")
    engine.perform("goblin_1", "move:door")
    assert hp(engine, "goblin_1") == 10
    assert rng.left("d8") == 0


# D3: урон Метки -- отдельной записью force; Метка работает и от атаки заклинанием

def test_mark_damage_is_logged_as_force(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5], d6=[4]))
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", SHOOT)
    assert any("Метка охотника: 1d6 (4) силовой" in line for line in engine.state.log)


def test_mark_adds_damage_to_a_spell_attack(registry, cfg):
    # заговор 1d10 (6) + Метка 1d6 (4)
    hero = make_ranger(registry)
    hero.sheet.known_of()[:] = ["fire_bolt"]
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d10=[6], d6=[4]), hero=hero)
    tough(engine)
    engine.perform("hero", "cast:hunters_mark:1:goblin_1")
    engine.perform("hero", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 20


# подписи слагаемых в строках броска Грея

def test_grey_bow_attack_line_signs_every_part(registry, cfg):
    hero = make_ranger(registry, feats=("archery",))
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5]), hero=hero)
    engine.perform("hero", SHOOT)
    expected = "Атака (длинный лук): d20 (15) + 3 Лов + 2 мастерство + 2 Стрельба = 22 против КД 15"
    assert any(expected in line for line in engine.state.log)


def test_grey_bow_damage_line_has_title_part_and_type(registry, cfg):
    engine = ranger_engine(registry, cfg, ScriptedRng(d20=[15], d8=[5]))
    engine.perform("hero", SHOOT)
    assert any("Урон (длинный лук): 1d8 (5) + 3 Лов = 8 колющий" in x for x in engine.state.log)

