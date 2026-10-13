# К1 «Дальность» (docs/K1-PLAN.md, п. 1, В1а): одна шкала полос для оружия героя, монстров и всех
# видов заклинаний -- та же зона 10 фт, соседняя 30, через одну 60, дальше 120 (подмены
# «2 шага = 60» только в cast_targets больше нет: полоса приходит из range_band_ft).
#   range_band_ft(0..4) -> 10, 30, 60, 120, 120
#   оружие: полоса <= range_normal -- обычная, <= range_long -- помеха («дальность»),
#     иначе варианта нет
#   заклинание: цель в списке cast_targets, если полоса <= spell.range_ft
# Карта -- линия зон z0 - z1 - z2 - z3 (make_line), шагов между зонами i и j = |i - j|.
from combat_kit import (
    ScriptedRng,
    give_weapon,
    hp,
    make_engine,
    make_fighter,
    make_line,
    make_wizard,
    mon,
    option_ids,
)
from test_ranger_combat import make_ranger

from ai_dm.combat.actions.attack import attacks_of, base_label
from ai_dm.combat.zones import range_band_ft


def archer(registry, weapon):
    hero = make_fighter(registry)
    give_weapon(hero, registry, weapon)
    return hero


def line_duel(registry, cfg, hero, steps, rng=None, zones=4):
    return make_engine(
        registry, cfg, heroes=[(hero, "z0")], rng=rng, zones=make_line(zones),
        monsters=[mon("goblin_1", "goblin_warrior", f"z{steps}")],
    )


def info_of(engine, weapon):
    return [i for i in attacks_of(engine, "hero") if i.id == weapon][0]


def label(engine, weapon):
    return base_label(engine, "hero", "goblin_1", info_of(engine, weapon))


def targets(engine, spell_id, circle=0, ref="hero"):
    prefix = f"cast:{spell_id}:{circle}:"
    ids = [i for i in option_ids(engine, ref) if i.startswith(prefix) and not i.endswith(":free")]
    return [i[len(prefix):] for i in ids]


# полосы

def test_bands_by_steps():
    assert [range_band_ft(n) for n in range(5)] == [10, 30, 60, 120, 120]


# оружие героя

def test_shortbow_across_one_zone_is_a_normal_shot(registry, cfg):
    engine = line_duel(registry, cfg, archer(registry, "shortbow"), 2)
    assert label(engine, "shortbow") == ""
    assert "attack:shortbow:goblin_1" in option_ids(engine, "hero")


def test_shortbow_across_two_zones_is_labeled_range(registry, cfg):
    engine = line_duel(registry, cfg, archer(registry, "shortbow"), 3)
    assert label(engine, "shortbow") == "дальность"
    assert "attack:shortbow:goblin_1" in option_ids(engine, "hero")


def test_shortbow_across_one_zone_rolls_a_single_d20(registry, cfg):
    rng = ScriptedRng(d20=[18], d6=[4])
    engine = line_duel(registry, cfg, archer(registry, "shortbow"), 2, rng)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") == 10 - (4 + 1)


def test_shortbow_across_two_zones_takes_the_worse_of_two_d20(registry, cfg):
    rng = ScriptedRng(d20=[18, 2])
    engine = line_duel(registry, cfg, archer(registry, "shortbow"), 3, rng)
    engine.perform("hero", "attack:shortbow:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_longbow_across_two_zones_is_a_normal_shot(registry, cfg):
    engine = line_duel(registry, cfg, archer(registry, "longbow"), 3)
    assert label(engine, "longbow") == ""


def test_longbow_across_two_zones_rolls_a_single_d20(registry, cfg):
    rng = ScriptedRng(d20=[18], d8=[5])
    engine = line_duel(registry, cfg, archer(registry, "longbow"), 3, rng)
    engine.perform("hero", "attack:longbow:goblin_1")
    assert rng.left("d20") == 0
    assert hp(engine, "goblin_1") < 10


def test_dagger_stays_a_melee_attack_across_a_zone(registry, cfg):
    # кинжал в данных -- ближнее оружие со свойством thrown; броска кинжала движок не предлагает
    engine = line_duel(registry, cfg, archer(registry, "dagger"), 1)
    assert "attack:dagger:goblin_1" not in option_ids(engine, "hero")


# брошенный подручный предмет 20/60

def test_thrown_object_in_own_zone_is_within_normal_range(registry, cfg):
    # 10 фт <= 20 фт: «дальности» нет, остаётся только «враг рядом»
    engine = line_duel(registry, cfg, make_fighter(registry), 0)
    assert label(engine, "improvised_thrown") == "враг рядом"


def test_thrown_object_across_a_neighbour_zone_is_labeled_range(registry, cfg):
    engine = line_duel(registry, cfg, make_fighter(registry), 1)
    assert label(engine, "improvised_thrown") == "дальность"


def test_thrown_object_across_one_zone_is_offered_with_range_label(registry, cfg):
    engine = line_duel(registry, cfg, make_fighter(registry), 2)
    assert "attack:improvised_thrown:goblin_1" in option_ids(engine, "hero")
    assert label(engine, "improvised_thrown") == "дальность"


def test_thrown_object_across_one_zone_has_disadvantage(registry, cfg):
    # 12 + 3 = 15 попадает по КД 15, но помеха берёт меньшее из двух
    rng = ScriptedRng(d20=[12, 2], d4=[2])
    engine = line_duel(registry, cfg, make_fighter(registry), 2, rng)
    engine.perform("hero", "attack:improvised_thrown:goblin_1")
    assert hp(engine, "goblin_1") == 10


def test_thrown_object_across_two_zones_is_not_offered(registry, cfg):
    engine = line_duel(registry, cfg, make_fighter(registry), 3)
    assert "attack:improvised_thrown:goblin_1" not in option_ids(engine, "hero")


# монстры

def test_goblin_archer_across_one_zone_shoots_without_disadvantage(registry, cfg):
    rng = ScriptedRng(d20=[15], d6=[3])
    engine = line_duel(registry, cfg, make_fighter(registry), 2, rng)
    engine.perform("goblin_1", "attack:короткий_лук:hero")
    assert rng.left("d20") == 0
    assert hp(engine, "hero") == 7


def test_goblin_archer_across_two_zones_takes_the_worse_of_two_d20(registry, cfg):
    rng = ScriptedRng(d20=[15, 2], d6=[3])
    engine = line_duel(registry, cfg, make_fighter(registry), 3, rng)
    engine.perform("goblin_1", "attack:короткий_лук:hero")
    assert hp(engine, "hero") == 12


# заклинания

def test_fire_bolt_reaches_three_steps(registry, cfg):
    engine = line_duel(registry, cfg, make_wizard(registry), 3)
    assert targets(engine, "fire_bolt", ref="wiz") == ["goblin_1"]


def test_fire_bolt_reaches_two_steps(registry, cfg):
    engine = line_duel(registry, cfg, make_wizard(registry), 2)
    assert targets(engine, "fire_bolt", ref="wiz") == ["goblin_1"]


def test_hunters_mark_reaches_two_steps(registry, cfg):
    engine = line_duel(registry, cfg, make_ranger(registry), 2)
    assert targets(engine, "hunters_mark", 1) == ["goblin_1"]


def test_hunters_mark_does_not_reach_three_steps(registry, cfg):
    # 90 фт: полоса 3 шагов -- 120 фт, это мутант «band = 60» из cast_targets
    engine = line_duel(registry, cfg, make_ranger(registry), 3)
    assert targets(engine, "hunters_mark", 1) == []


def test_hunters_mark_reaches_one_step(registry, cfg):
    engine = line_duel(registry, cfg, make_ranger(registry), 1)
    assert targets(engine, "hunters_mark", 1) == ["goblin_1"]


def bless_party(registry, cfg, ally_zone):
    caster = make_wizard(registry)
    caster.sheet.prepared_of().append("bless")
    ally = make_fighter(registry, "ally")
    return make_engine(
        registry, cfg, heroes=[(caster, "z0"), (ally, ally_zone)], zones=make_line(4),
        monsters=[mon("goblin_1", "goblin_warrior", "z3")],
    )


def test_bless_reaches_a_neighbour_zone(registry, cfg):
    assert "ally" in targets(bless_party(registry, cfg, "z1"), "bless", 1, "wiz")


def test_bless_does_not_reach_across_one_zone(registry, cfg):
    # 30 фт: через одну зону уже 60 фт
    assert targets(bless_party(registry, cfg, "z2"), "bless", 1, "wiz") == ["wiz"]
