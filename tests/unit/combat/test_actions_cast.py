# Заклинания (шаг 17): id варианта cast:<заклинание>:<круг>:<цель>, круг 0 у заговора.
#   Доступны: заговоры из sheet.spells_known; заклинания 1+ круга из sheet.spells_prepared и
#   только при ячейке (пул creature.resources["spell_slot:<круг>"].current > 0); ячейка тратится
#   при сотворении. Нет ячейки / не подготовлено -> варианта нет, perform -> Rejected.
#   Заклинание-атака (fire_bolt): бросок атаки заклинанием (derived.spell_attack_bonus) против КД,
#     цель в полосе до range_ft (120 фт = любая зона поля); вражеское боеспособное существо в
#     зоне заклинателя -- помеха (как у дальней атаки); событие attack mode="spell".
#   magic_missile: без броска атаки, count дротиков по 1d4+1 в одну цель (по одному d4 на дротик).
#   Площадь (burning_hands, конус 15 фт от себя): цель -- id своей или соседней зоны
#     (cast:burning_hands:1:<зона>); накрывает ВСЕХ боеспособных (и "down") существ зоны, кроме
#     заклинателя, союзников тоже; один бросок урона на всех; каждый -- спасбросок ЛОВ против
#     spell_save_dc (порядок -- как в state.participants): провал -- урон целиком, успех --
#     половина (вниз). Цель вне досягаемости конуса -- варианта нет.
#   bless (союзники в своей или соседней зоне, 30 фт; cast:bless:1:<t1>[,<t2>[,<t3>]]; бросок не
#     нужен; до targets=3 целей, многоцелевой механизм -- в test_bless.py): ячейка тратится,
#     caster.concentration = "bless"; на каждую цель ВСЕ modifier-эффекты заклинания: два
#     ActiveEffect(id="bless", source=<заклинатель>, kind="modifier", params={"target":
#     "attack_roll" | "saving_throw", "dice": "1d4"}, expires=Expiry(kind="concentration",
#     owner=<заклинатель>)) -- +1d4 к его броскам атаки и спасброскам.
#     Урон по заклинателю с концентрацией -- проверка концентрации
#     (rules.damage.concentration_check: СЛ max(10, урон // 2), спасбросок ТЕЛ);
#     провал -- end_concentration: эффект bless снят.
#   cure_wounds (касание): цель -- союзник в той же зоне; 2d8 + заклинательный модификатор;
#     лежащего на 0 HP поднимает (status -> "active", спасброски сброшены).
from combat_kit import (
    ScriptedRng,
    creature,
    down_hero,
    hp,
    make_engine,
    make_fighter,
    make_wizard,
    mon,
    option_ids,
    part,
    set_hp,
)

from ai_dm.rules.results import Rejected


def caster_engine(registry, cfg, rng, monsters=None, hero=None, **kwargs):
    if monsters is None:
        monsters = [mon("goblin_1", "goblin_warrior", "hall")]
    return make_engine(
        registry, cfg, heroes=[hero or make_wizard(registry)], rng=rng, monsters=monsters,
        hero_zone="door", **kwargs,
    )


def slots(engine):
    return engine.heroes["wiz"].creature.resources["spell_slot:1"].current


# fire_bolt

def test_fire_bolt_hit_deals_1d10_fire(registry, cfg):
    # +5 против КД 15: 10 + 5 = 15
    engine = caster_engine(registry, cfg, ScriptedRng(d20=[10], d10=[7]))
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 3


def test_fire_bolt_miss(registry, cfg):
    rng = ScriptedRng(d20=[9], d10=[7])
    engine = caster_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert hp(engine, "goblin_1") == 10
    assert rng.left("d10") == 1


def test_fire_bolt_does_not_spend_a_slot(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng(d20=[10], d10=[7]))
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert slots(engine) == 2


def test_fire_bolt_event_is_a_spell_attack(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng(d20=[10], d10=[7]))
    events = engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    attack = [e for e in events if e.type == "attack"][0]
    assert attack.data["mode"] == "spell"
    assert attack.data["weapon"] == "fire_bolt"
    assert attack.data["damage"] == 7


def test_fire_bolt_reaches_the_far_zone(registry, cfg):
    engine = caster_engine(
        registry, cfg, ScriptedRng(d20=[10], d10=[7]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    assert "cast:fire_bolt:0:goblin_1" in option_ids(engine, "wiz")


def test_fire_bolt_with_enemy_in_own_zone_has_disadvantage(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_wizard(registry)], rng=ScriptedRng(d20=[18, 2]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "balcony")],
    )
    engine.perform("wiz", "cast:fire_bolt:0:goblin_2")
    assert hp(engine, "goblin_2") == 10


def test_fire_bolt_spends_the_action(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng(d20=[1]))
    engine.perform("wiz", "cast:fire_bolt:0:goblin_1")
    assert part(engine, "wiz").turn.action is False


# magic_missile

def test_magic_missile_hits_with_three_darts(registry, cfg):
    # три дротика 1d4 + 1: (1 + 1) + (2 + 1) + (3 + 1) = 9
    rng = ScriptedRng(d4=[1, 2, 3])
    engine = caster_engine(registry, cfg, rng)
    set_hp(engine, "goblin_1", 20)
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert hp(engine, "goblin_1") == 11


def test_magic_missile_needs_no_attack_roll(registry, cfg):
    rng = ScriptedRng(d4=[1, 1, 1])
    engine = caster_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert "d20" not in rng.calls


def test_magic_missile_spends_a_slot(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng(d4=[1, 1, 1]))
    engine.perform("wiz", "cast:magic_missile:1:goblin_1")
    assert slots(engine) == 1


def test_no_slot_no_leveled_spell(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng())
    engine.heroes["wiz"].creature.resources["spell_slot:1"].current = 0
    ids = option_ids(engine, "wiz")
    assert "cast:magic_missile:1:goblin_1" not in ids
    assert "cast:fire_bolt:0:goblin_1" in ids


def test_cast_without_a_slot_is_rejected(registry, cfg):
    engine = caster_engine(registry, cfg, ScriptedRng())
    engine.heroes["wiz"].creature.resources["spell_slot:1"].current = 0
    assert isinstance(engine.perform("wiz", "cast:magic_missile:1:goblin_1"), Rejected)
    assert slots(engine) == 0


def test_unprepared_spell_is_not_available(registry, cfg):
    hero = make_wizard(registry)
    hero.sheet.prepared_of()[:] = ["burning_hands"]
    engine = caster_engine(registry, cfg, ScriptedRng(), hero=hero)
    assert "cast:magic_missile:1:goblin_1" not in option_ids(engine, "wiz")


def test_fighter_has_no_spells(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[make_fighter(registry)],
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    assert not [i for i in option_ids(engine, "hero") if i.startswith("cast:")]


# burning_hands

def hands_engine(registry, cfg, rng):
    return make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door")], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "hall")],
    )


def test_cone_can_be_aimed_at_own_or_neighbour_zone(registry, cfg):
    ids = option_ids(hands_engine(registry, cfg, ScriptedRng()), "wiz")
    assert "cast:burning_hands:1:door" in ids
    assert "cast:burning_hands:1:hall" in ids


def test_cone_cannot_be_aimed_at_a_far_zone(registry, cfg):
    ids = option_ids(hands_engine(registry, cfg, ScriptedRng()), "wiz")
    assert "cast:burning_hands:1:balcony" not in ids


def test_failed_save_takes_full_damage(registry, cfg):
    # 3d6 = 2 + 3 + 4 = 9; ЛОВ гоблина +2: 5 + 2 = 7 < 13 -- провал
    engine = hands_engine(registry, cfg, ScriptedRng(d20=[5, 5], d6=[2, 3, 4]))
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21
    assert hp(engine, "goblin_2") == 21


def test_passed_save_takes_half_rounded_down(registry, cfg):
    # 15 + 2 = 17 >= 13 -- успех; 9 // 2 = 4
    engine = hands_engine(registry, cfg, ScriptedRng(d20=[5, 15], d6=[2, 3, 4]))
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_1") == 21
    assert hp(engine, "goblin_2") == 26


def test_one_damage_roll_for_all_targets(registry, cfg):
    rng = ScriptedRng(d20=[5, 5], d6=[2, 3, 4])
    engine = hands_engine(registry, cfg, rng)
    set_hp(engine, "goblin_1", 30)
    set_hp(engine, "goblin_2", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert rng.left("d6") == 0


def test_cone_hits_allies_in_the_zone(registry, cfg):
    ally = make_fighter(registry, "ally")
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door"), (ally, "hall")],
        rng=ScriptedRng(d20=[5, 5], d6=[2, 3, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "ally") == 12 - 9


def test_cone_does_not_hit_the_caster(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "hall")],
        rng=ScriptedRng(d20=[5], d6=[2, 3, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "wiz") == 8


def test_cone_does_not_hit_other_zones(registry, cfg):
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door")],
        rng=ScriptedRng(d20=[5], d6=[2, 3, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "hall"),
                  mon("goblin_2", "goblin_warrior", "balcony")],
    )
    set_hp(engine, "goblin_1", 30)
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "goblin_2") == 10


def test_cone_spends_a_slot(registry, cfg):
    engine = hands_engine(registry, cfg, ScriptedRng(d20=[5, 5], d6=[2, 3, 4]))
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert slots(engine) == 1


def test_cone_can_kill_and_report_it(registry, cfg):
    engine = hands_engine(registry, cfg, ScriptedRng(d20=[5, 5], d6=[6, 6, 6]))
    set_hp(engine, "goblin_1", 5)
    events = engine.perform("wiz", "cast:burning_hands:1:hall")
    assert part(engine, "goblin_1").status == "dead"
    assert "monster_died" in [e.type for e in events]


def test_cone_hero_target_saves_with_hero_bonus(registry, cfg):
    # союзник-воин: ЛОВ +1; 11 + 1 = 12 < 13 -- провал
    ally = make_fighter(registry, "ally")
    engine = make_engine(
        registry, cfg, heroes=[(make_wizard(registry), "door"), (ally, "hall")],
        rng=ScriptedRng(d20=[11], d6=[2, 3, 4]),
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    engine.perform("wiz", "cast:burning_hands:1:hall")
    assert hp(engine, "ally") == 3


# cure_wounds

def cure_engine(registry, cfg, rng, ally_zone="door"):
    healer = make_wizard(registry)
    healer.sheet.prepared_of().append("cure_wounds")
    ally = make_fighter(registry, "ally")
    engine = make_engine(
        registry, cfg, heroes=[(healer, "door"), (ally, ally_zone)], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "balcony")],
    )
    return engine


def test_cure_wounds_heals_2d8_plus_modifier(registry, cfg):
    # заклинательный модификатор волшебника: ИНТ 17 -> +3; 3 + 4 + 3 = 10
    engine = cure_engine(registry, cfg, ScriptedRng(d8=[3, 4]))
    set_hp(engine, "ally", 1)
    engine.perform("wiz", "cast:cure_wounds:1:ally")
    assert hp(engine, "ally") == 11


def test_cure_wounds_needs_touch_range(registry, cfg):
    engine = cure_engine(registry, cfg, ScriptedRng(), ally_zone="hall")
    assert "cast:cure_wounds:1:ally" not in option_ids(engine, "wiz")


def test_cure_wounds_lifts_a_downed_ally(registry, cfg):
    engine = cure_engine(registry, cfg, ScriptedRng(d8=[1, 1]))
    down_hero(engine, "ally")
    engine.perform("wiz", "cast:cure_wounds:1:ally")
    assert hp(engine, "ally") == 5
    assert part(engine, "ally").status == "active"
    assert not [c for c in creature(engine, "ally").conditions if c.id == "unconscious"]


# bless и концентрация

def bless_engine(registry, cfg, rng):
    caster = make_wizard(registry)
    caster.sheet.prepared_of().append("bless")
    ally = make_fighter(registry, "ally")
    return make_engine(
        registry, cfg, heroes=[caster, ally], rng=rng,
        monsters=[mon("goblin_1", "goblin_warrior", "hall")],
    )


def test_bless_puts_an_effect_on_the_ally_and_starts_concentration(registry, cfg):
    engine = bless_engine(registry, cfg, ScriptedRng())
    engine.perform("wiz", "cast:bless:1:ally")
    effects = engine.heroes["ally"].creature.active_effects
    assert [(e.id, e.source) for e in effects] == [("bless", "wiz"), ("bless", "wiz")]
    assert sorted(e.params["target"] for e in effects) == ["attack_roll", "saving_throw"]
    assert effects[0].expires.kind == "concentration"
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bless"
    assert slots(engine) == 1


def test_bless_adds_1d4_to_the_ally_attack(registry, cfg):
    # 9 + 5 = 14 -- промах по КД 15; с благословением 14 + 2 = 16 -- попадание
    engine = bless_engine(registry, cfg, ScriptedRng(d20=[9], d4=[2], d8=[4]))
    engine.perform("wiz", "cast:bless:1:ally")
    engine.perform("ally", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 3
    assert any("1d4 (2)" in line for line in engine.state.log)


def test_ally_without_bless_misses_with_the_same_roll(registry, cfg):
    engine = bless_engine(registry, cfg, ScriptedRng(d20=[9]))
    engine.perform("ally", "attack:longsword:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_damage_to_the_caster_triggers_a_concentration_check(registry, cfg):
    # гоблин попадает (19 + 4), урон 3 + 2 = 5, СЛ 10; ТЕЛ волшебника +2: 8 + 2 = 10 -- держит
    engine = bless_engine(registry, cfg, ScriptedRng(d20=[19, 8], d6=[3]))
    engine.perform("wiz", "cast:bless:1:ally")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert hp(engine, "wiz") == 3
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bless"
    assert [e.id for e in engine.heroes["ally"].creature.active_effects] == ["bless", "bless"]


def test_failed_concentration_check_drops_bless(registry, cfg):
    # 7 + 2 = 9 < 10 -- провал
    engine = bless_engine(registry, cfg, ScriptedRng(d20=[19, 7], d6=[3]))
    engine.perform("wiz", "cast:bless:1:ally")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert engine.heroes["wiz"].creature.concentration is None
    assert engine.heroes["ally"].creature.active_effects == []


def test_miss_on_the_caster_needs_no_concentration_check(registry, cfg):
    rng = ScriptedRng(d20=[2])
    engine = bless_engine(registry, cfg, rng)
    engine.perform("wiz", "cast:bless:1:ally")
    engine.perform("goblin_1", "attack:скимитар:wiz")
    assert engine.heroes["wiz"].creature.concentration.spell_id == "bless"
    assert rng.left("d20") == 0
